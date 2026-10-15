#!/usr/bin/env python3
"""Live monitor for one replay_bag.sh run.

Usage: monitor.py <run_dir> <rate> <start_s>

Writes into <run_dir>:
  events.csv     wall, bag_t, type, a, b, line   (tailed from mono.log / desc.log)
  keyframes.csv  wall, bag_t, kf_id               (/orb_slam3/new_keyframe_id)
  topicstats.csv wall, bag_t, topic, publisher, subscriber, delivered, dropped, window_s,
                 period_mean_s   (/statistics; needs /enable_statistics=true before nodes start)
  resources.csv  wall, bag_t, proc, pid, cpu_pct, rss_mb | gpu rows: proc=GPU, cpu_pct=util, rss_mb=mem
Bag time comes from /clock (rosbag play --clock); before the first /clock message it is
estimated from the rosbag play process start time: (wall - play_start) * rate + start_s.
Stops on SIGINT/SIGTERM or when the ROS master goes away.
"""
import sys, os, re, csv, time, threading, signal, subprocess
import psutil, rospy
from std_msgs.msg import Int32
from rosgraph_msgs.msg import Clock, TopicStatistics

RUN, RATE, START = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
stop = threading.Event()
lock = threading.Lock()
clock = {'bag_t': None, 'bag0': None}
ROSPY_TS = re.compile(r'^\[\s*\w+\]\s*\[(\d{9,}\.\d+)\]')

PATTERNS = [
    ('new_map',       re.compile(r'Creation of new map with id: (\d+)')),
    ('merge',         re.compile(r'Merge finished')),
    ('loop_detected', re.compile(r'\*Loop detected')),
    ('correction',    re.compile(r'\[STATS\].*corrections=(\d+) matchedKF=(\d+) currentKF=(\d+)')),
    ('injected',      re.compile(r'injected external candidate KF (\d+) for current KF (\d+)')),
    ('abort_near',    re.compile(r'\[ABORT-NEAR\] candidate KF (\d+) vs current KF (\d+)')),
    ('proposal',      re.compile(r'LOOP CLOSURE: KF (\d+) matches KF (\d+)')),
    ('sophus_crash',  re.compile(r'Sophus ensure failed')),
    ('lost',          re.compile(r'Fail to track|LOST|Reseting|Track Lost|Lost for a short')),
    ('reset_map',     re.compile(r'Reseting active map|Reseting current map')),
    ('new_map_kf',    re.compile(r'Creation of new map with last KF id: (\d+)')),
    ('final_stats',   re.compile(r'\[FINAL STATS\]')),
]


def bag_time():
    if clock['bag_t'] is not None:
        return clock['bag_t']
    for p in psutil.process_iter(['cmdline', 'create_time']):
        cl = p.info['cmdline'] or []
        if len(cl) > 1 and 'rosbag' in ' '.join(cl[:3]) and 'play' in cl:
            return (time.time() - p.info['create_time']) * RATE + START
    return float('nan')


def writer(name, header):
    f = open(os.path.join(RUN, name), 'w', newline='')
    w = csv.writer(f); w.writerow(header); f.flush()
    return f, w


fE, wE = writer('events.csv', ['wall', 'bag_t', 'type', 'a', 'b', 'line'])
fK, wK = writer('keyframes.csv', ['wall', 'bag_t', 'kf_id'])
fT, wT = writer('topicstats.csv', ['wall', 'bag_t', 'topic', 'publisher', 'subscriber',
                                    'delivered', 'dropped', 'window_s', 'period_mean_s'])
fR, wR = writer('resources.csv', ['wall', 'bag_t', 'proc', 'pid', 'cpu_pct', 'rss_mb'])


def tail(path):
    while not os.path.exists(path) and not stop.is_set():
        time.sleep(0.5)
    if stop.is_set():
        return
    with open(path, errors='replace') as f:
        buf = ''
        while True:
            chunk = f.read()
            if chunk:
                buf += chunk
                *lines, buf = buf.split('\n')
                now, bt = time.time(), bag_time()
                for line in lines:
                    # rospy lines carry their own wall stamp; stdout/stderr buffering reorders them
                    ms = ROSPY_TS.search(line)
                    lw, lb = (float(ms.group(1)), bt - (now - float(ms.group(1))) * RATE) if ms else (now, bt)
                    for typ, rx in PATTERNS:
                        m = rx.search(line)
                        if m:
                            g = m.groups() + (None, None)
                            with lock:
                                wE.writerow([f'{lw:.3f}', f'{lb:.3f}', typ, g[0], g[1], line.strip()[:200]])
                            break
            elif stop.is_set():
                return
            else:
                time.sleep(0.2)


def classify(p):
    cl = ' '.join(p.info['cmdline'] or [])
    if 'ORB_SLAM3/Mono' in cl or (p.info['name'] == 'Mono'):
        return 'Mono'
    if 'loop_closure' in cl:
        return 'desc'
    if 'load_only' in cl:
        return 'load'
    if 'rosbag' in cl and 'play' in cl:
        return 'rosbag_play'
    if 'topic_tools' in cl or '/drop ' in cl:
        return 'relay'
    return None


def resources():
    procs = {}
    gpu = subprocess.Popen(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used',
                            '--format=csv,noheader,nounits', '-lms', '2000'],
                           stdout=subprocess.PIPE, text=True)

    def gpu_reader():
        for line in gpu.stdout:
            try:
                u, m = [float(x) for x in line.split(',')]
            except ValueError:
                continue
            with lock:
                wR.writerow([f'{time.time():.3f}', f'{bag_time():.3f}', 'GPU', -1, u, m])
            if stop.is_set():
                break
    threading.Thread(target=gpu_reader, daemon=True).start()
    while not stop.is_set():
        for p in psutil.process_iter(['cmdline', 'name']):
            if p.pid not in procs:
                c = classify(p)
                if c:
                    procs[p.pid] = (c, p); p.cpu_percent(None)
        now, bt = time.time(), bag_time()
        for pid, (c, p) in list(procs.items()):
            try:
                cpu = p.cpu_percent(None); rss = p.memory_info().rss / 2 ** 20
            except psutil.NoSuchProcess:
                del procs[pid]; continue
            with lock:
                wR.writerow([f'{now:.3f}', f'{bt:.3f}', c, pid, f'{cpu:.1f}', f'{rss:.0f}'])
        stop.wait(2.0)
    gpu.terminate()


def on_clock(msg):
    clock['bag_t'] = msg.clock.to_sec() - clock['bag0'] if clock['bag0'] is not None else None


def on_kf(msg):
    with lock:
        wK.writerow([f'{time.time():.3f}', f'{bag_time():.3f}', msg.data])


def on_stats(m):
    with lock:
        wT.writerow([f'{time.time():.3f}', f'{bag_time():.3f}', m.topic, m.node_pub, m.node_sub,
                     m.delivered_msgs, m.dropped_msgs,
                     f'{(m.window_stop - m.window_start).to_sec():.2f}', f'{m.period_mean.to_sec():.4f}'])


def flusher():
    while not stop.wait(5.0):
        with lock:
            for f in (fE, fK, fT, fR):
                f.flush()
        if rospy.is_shutdown():
            stop.set()


signal.signal(signal.SIGTERM, lambda *a: stop.set())
signal.signal(signal.SIGINT, lambda *a: stop.set())
clock['bag0'] = float(os.environ.get('BAG_START', 'nan'))   # absolute bag start (s), for /clock -> t_rel
if clock['bag0'] != clock['bag0']:
    clock['bag0'] = None
rospy.init_node('diag_monitor', anonymous=True, disable_signals=True)
rospy.Subscriber('/clock', Clock, on_clock, queue_size=10)
rospy.Subscriber('/orb_slam3/new_keyframe_id', Int32, on_kf, queue_size=1000)
rospy.Subscriber('/statistics', TopicStatistics, on_stats, queue_size=1000)
threads = [threading.Thread(target=tail, args=(os.path.join(RUN, n),), daemon=True)
           for n in ('mono.log', 'desc.log')]
threads += [threading.Thread(target=resources, daemon=True), threading.Thread(target=flusher, daemon=True)]
for t in threads:
    t.start()
while not stop.is_set():
    stop.wait(1.0)
for t in threads[:2]:
    t.join(timeout=5.0)   # let tailers catch the last lines
with lock:
    for f in (fE, fK, fT, fR):
        f.close()

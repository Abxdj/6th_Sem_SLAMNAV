#!/usr/bin/env python3
"""H3: is camera motion rotation-dominant just before tracking is lost?

For each tracking-loss onset (first 'lost' event after >= GAP s without one) and for a set of
random base-rate windows, read bag frames in [t-3 s, t], track sparse corners (KLT) between
frames k and k+3, fit a rotation-only flow model (robust, known K) and record
  flow_med   median flow magnitude (px)
  par        median residual / median flow  (0 = pure rotation; translation + depth -> larger)
  yaw_dps    fitted yaw rate (deg/s, bag time)
Usage: motion_events.py <bag> <events.csv> <out.csv> [n_random]
"""
import sys, csv
import numpy as np, cv2, rosbag, rospy

BAG, EV, OUT = sys.argv[1:4]
NRAND = int(sys.argv[4]) if len(sys.argv) > 4 else 60
FX, FY, CX, CY = 403.0, 536.4, 320.5, 240.5
GAP, WIN, STEP = 10.0, 3.0, 3


def rot_basis(u, v):
    x = (u - CX) / FX; y = (v - CY) / FY
    A = np.zeros((2 * len(x), 3))
    A[0::2] = np.c_[FX * x * y, -FX * (1 + x ** 2), FX * y]
    A[1::2] = np.c_[FY * (1 + y ** 2), -FY * x * y, -FY * x]
    return A


def pair_stats(a, b, dt):
    p0 = cv2.goodFeaturesToTrack(a, 400, 0.01, 8)
    if p0 is None or len(p0) < 20:
        return None
    p1, st, _ = cv2.calcOpticalFlowPyrLK(a, b, p0, None, winSize=(21, 21), maxLevel=3)
    ok = st.ravel() == 1
    if ok.sum() < 20:
        return None
    p0, p1 = p0.reshape(-1, 2)[ok], p1.reshape(-1, 2)[ok]
    fl = p1 - p0
    A = rot_basis(p0[:, 0], p0[:, 1]); obs = fl.ravel()
    w = np.linalg.lstsq(A, obs, rcond=None)[0]
    for _ in range(3):   # IRLS with Huber-like weights
        r = np.linalg.norm((obs - A @ w).reshape(-1, 2), axis=1)
        s = np.median(r) + 1e-3
        wt = np.repeat(np.clip(1.5 * s / np.maximum(r, 1e-6), 0, 1), 2)
        w = np.linalg.lstsq(A * wt[:, None], obs * wt, rcond=None)[0]
    res = np.linalg.norm((obs - A @ w).reshape(-1, 2), axis=1)
    mag = np.linalg.norm(fl, axis=1)
    fm = float(np.median(mag))
    return fm, float(np.median(res) / max(fm, 1e-3)), float(np.degrees(w[1]) / dt), len(p0)


bag = rosbag.Bag(BAG); t0 = bag.get_start_time(); T = bag.get_end_time() - t0
E = list(csv.DictReader(open(EV)))
lost = sorted(float(r['bag_t']) for r in E if r['type'] == 'lost' and r['bag_t'] != 'nan')
onsets, last = [], -1e9
for t in lost:
    if t - last > GAP:
        onsets.append(t)
    last = t
rng = np.random.default_rng(1)
rand = sorted(rng.uniform(WIN, T, NRAND))
rows = []
for kind, ts in (('loss_onset', onsets), ('random', rand)):
    for tc in ts:
        frames = [(t.to_sec(), np.frombuffer(m.data, np.uint8).reshape(m.height, m.width))
                  for _, m, t in bag.read_messages(start_time=rospy.Time(t0 + tc - WIN), end_time=rospy.Time(t0 + tc))]
        st = []
        for k in range(0, len(frames) - STEP, STEP):
            r = pair_stats(frames[k][1], frames[k + STEP][1], frames[k + STEP][0] - frames[k][0])
            if r: st.append(r)
        if not st:
            rows.append([kind, f'{tc:.1f}', 0, '', '', '', '']); continue
        s = np.array(st)
        moving = s[:, 0] > 0.5
        rows.append([kind, f'{tc:.1f}', len(s), f'{np.median(s[:, 0]):.2f}',
                     f'{np.median(s[moving, 1]) if moving.any() else float("nan"):.3f}',
                     f'{np.median(np.abs(s[:, 2])):.1f}', f'{np.max(np.abs(s[:, 2])):.1f}'])
        print(rows[-1], flush=True)
with open(OUT, 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['kind', 'bag_t', 'n_pairs', 'flow_med', 'par_med_moving', 'abs_yaw_dps_med', 'abs_yaw_dps_max'])
    w.writerows(rows)

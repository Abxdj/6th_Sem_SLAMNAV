#!/usr/bin/env python3
"""Play one or more EuRoC cam0 sequences into one ORB-SLAM3 process.

Usage: euroc_session_publisher.py <speed_mult> <seq_dir> [<seq_dir> ...]
  speed_mult: wall seconds per sensor second (1.0 = real time, 2.0 = half speed; higher = slower,
  same convention as evaluation/euroc_publisher.py).
Between sequences it publishes std_msgs/Empty on /orb_slam3/new_session (ros_mono.cc calls
System::ChangeDataset(), as Examples/Monocular/mono_euroc.cc does), then waits GAP_S of wall time.
A forward timestamp jump alone does NOT start a new map for pure monocular ORB-SLAM3
(src/Tracking.cc: the jump branch only acts if the Atlas is inertial).
Publishes bgr8 on /camera/rgb/image_raw with the original EuRoC timestamps.
"""
import sys, os, time
import rospy, cv2
from sensor_msgs.msg import Image
from std_msgs.msg import Empty
from cv_bridge import CvBridge

GAP_S = 5.0


def frames_of(seq):
    out = []
    with open(os.path.join(seq, 'mav0', 'cam0', 'data.csv')) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            ts, name = line.strip().split(',')[:2]
            out.append((int(ts) / 1e9, os.path.join(seq, 'mav0', 'cam0', 'data', name.strip())))
    return out


speed = float(sys.argv[1])
seqs = [os.path.expanduser(s) for s in sys.argv[2:]]
rospy.init_node('euroc_session_publisher')
pub = rospy.Publisher('/camera/rgb/image_raw', Image, queue_size=10)
sess = rospy.Publisher('/orb_slam3/new_session', Empty, queue_size=1, latch=False)
bridge = CvBridge()
rospy.sleep(2.0)
for k, seq in enumerate(seqs):
    fr = frames_of(seq)
    if k > 0:
        rospy.sleep(1.0)
        sess.publish(Empty())
        rospy.loginfo(f'[SESSION] new_session published before {seq}')
        time.sleep(GAP_S)
    rospy.loginfo(f'[SESSION] start {k} {seq} frames={len(fr)} t0={fr[0][0]:.6f} t1={fr[-1][0]:.6f}')
    w0, t0 = time.time(), fr[0][0]
    for i, (t, path) in enumerate(fr):
        if rospy.is_shutdown():
            sys.exit(0)
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            rospy.logwarn(f'could not read {path}')
            continue
        msg = bridge.cv2_to_imgmsg(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR), encoding='bgr8')
        msg.header.stamp = rospy.Time.from_sec(t)
        pub.publish(msg)
        dt = w0 + (t - t0) * speed - time.time()
        if dt > 0:
            time.sleep(dt)
    rospy.loginfo(f'[SESSION] end {k} published={len(fr)}')
rospy.sleep(3.0)
rospy.loginfo('[SESSION] all done')

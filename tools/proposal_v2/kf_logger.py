#!/usr/bin/env python3
"""Log every keyframe ORB-SLAM3 announces on /orb_slam3/new_keyframe ([id, stamp, map id at creation]), in every arm.

CPU only, no model: it lets merges in control / load-only runs be checked against GT and descriptors be computed
offline afterwards (tools/proposal_v2/offline_descs.py). Usage: kf_logger.py <out_csv>
Columns: wall, kf_id, stamp, map_id
"""
import sys, time
import rospy
from std_msgs.msg import Float64MultiArray

f = open(sys.argv[1], 'w', buffering=1)
f.write('wall,kf_id,stamp,map_id\n')


def on_kf(msg):
    d = list(msg.data)
    f.write(f'{time.time():.3f},{int(d[0])},{d[1]:.6f},{int(d[2]) if len(d) > 2 else -1}\n')


rospy.init_node('kf_logger', disable_signals=False)
rospy.Subscriber('/orb_slam3/new_keyframe', Float64MultiArray, on_kf, queue_size=1000)
rospy.spin()
f.close()

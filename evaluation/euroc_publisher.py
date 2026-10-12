#!/usr/bin/env python3
"""
Publishes EuRoC MAV cam0 (monochrome) images to /camera/rgb/image_raw,
driving the live ORB-SLAM3 + CLAHE + loop closure pipeline.

EuRoC specifics handled here:
  - timestamps are nanoseconds (TUM uses seconds)
  - images are already single-channel greyscale
  - data listed in mav0/cam0/data.csv

Usage: python3 euroc_publisher.py <path-to-extracted-sequence> [speed_multiplier]
  e.g. python3 euroc_publisher.py ~/euroc_v1/vicon_room1/V1_01_easy/extracted 2.0
"""
import sys
import os
import time
import rospy
import cv2
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

def load_cam0_list(seq_path):
    frames = []
    csv_path = os.path.join(seq_path, "mav0", "cam0", "data.csv")
    with open(csv_path) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split(',')
            ts_ns = int(parts[0])
            fname = parts[1].strip()
            frames.append((ts_ns / 1e9, fname))
    return frames

def main():
    if len(sys.argv) < 2:
        print("Usage: euroc_publisher.py <sequence_path> [speed_multiplier]")
        sys.exit(1)

    seq_path = os.path.expanduser(sys.argv[1])
    speed_mult = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    rospy.init_node('euroc_image_publisher')
    pub = rospy.Publisher('/camera/rgb/image_raw', Image, queue_size=10)
    bridge = CvBridge()

    frames = load_cam0_list(seq_path)
    img_dir = os.path.join(seq_path, "mav0", "cam0", "data")
    rospy.loginfo(f"EuRoC publisher: {len(frames)} frames from {seq_path}")
    rospy.loginfo(f"Playback speed multiplier: {speed_mult} (higher = slower)")

    rospy.sleep(2.0)

    start_wall = time.time()
    start_ts = frames[0][0]

    for i, (t, fname) in enumerate(frames):
        if rospy.is_shutdown():
            break

        img_path = os.path.join(img_dir, fname)
        # EuRoC images are already single-channel greyscale
        frame = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if frame is None:
            rospy.logwarn(f"Could not read {img_path}")
            continue

        # Publish as bgr8 so the existing CLAHE node's cvtColor path works unchanged
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        msg = bridge.cv2_to_imgmsg(frame_bgr, encoding='bgr8')
        msg.header.stamp = rospy.Time.from_sec(t)
        pub.publish(msg)

        target_wall = start_wall + (t - start_ts) * speed_mult
        sleep_time = target_wall - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

        if i % 200 == 0:
            rospy.loginfo(f"Published frame {i}/{len(frames)}")

    rospy.loginfo("EuRoC publisher: finished all frames")
    rospy.sleep(3.0)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Publishes TUM RGB-D sequence images to /camera/rgb/image_raw as a ROS
camera feed, driving the live ORB-SLAM3 + CLAHE + loop closure pipeline
exactly as Gazebo would, but from pre-recorded TUM data.

Usage: rosrun (or python3 directly) with DATASET_PATH set below,
       or pass as a command-line argument.
"""
import sys
import os
import time
import rospy
import cv2
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

def load_rgb_list(dataset_path):
    frames = []
    with open(os.path.join(dataset_path, "rgb.txt")) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split()
            frames.append((float(parts[0]), parts[1]))
    return frames

def main():
    dataset_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/rgbd_dataset_freiburg1_desk")

    rospy.init_node('tum_image_publisher')
    pub = rospy.Publisher('/camera/rgb/image_raw', Image, queue_size=10)
    bridge = CvBridge()

    frames = load_rgb_list(dataset_path)
    rospy.loginfo(f"TUM publisher: {len(frames)} frames from {dataset_path}")

    # Wait a moment for subscribers (CLAHE node) to connect
    rospy.sleep(2.0)

    start_wall = time.time()
    start_tum = frames[0][0]

    for i, (t, rgb_path) in enumerate(frames):
        if rospy.is_shutdown():
            break

        img_path = os.path.join(dataset_path, rgb_path)
        frame = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        msg = bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = rospy.Time.from_sec(t)
        pub.publish(msg)

        # Pace playback to match TUM's recorded timing
        target_wall = start_wall + (t - start_tum)
        sleep_time = target_wall - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

        if i % 50 == 0:
            rospy.loginfo(f"Published frame {i}/{len(frames)}")

    rospy.loginfo("TUM publisher: finished all frames")
    rospy.sleep(3.0)  # grace period for pipeline to finish processing last frames

if __name__ == "__main__":
    main()

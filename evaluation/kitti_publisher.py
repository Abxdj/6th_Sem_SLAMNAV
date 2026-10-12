#!/usr/bin/env python3
"""
Publishes KITTI odometry grayscale images (image_0) to /camera/rgb/image_raw.

KITTI specifics:
  - timestamps in times.txt, seconds, starting at 0
  - images already grayscale PNG, named 000000.png ... NNNNNN.png
  - 10 Hz capture rate

Usage: python3 kitti_publisher.py <sequence_path> [speed_multiplier]
  e.g. python3 kitti_publisher.py ~/kitti/dataset/sequences/00 2.0
"""
import sys, os, time
import rospy, cv2
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

def load_times(seq_path):
    times = []
    with open(os.path.join(seq_path, "times.txt")) as f:
        for line in f:
            if line.strip():
                times.append(float(line.strip()))
    return times

def main():
    if len(sys.argv) < 2:
        print("Usage: kitti_publisher.py <sequence_path> [speed_multiplier]")
        sys.exit(1)

    seq_path = os.path.expanduser(sys.argv[1])
    speed_mult = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    rospy.init_node('kitti_image_publisher')
    pub = rospy.Publisher('/camera/rgb/image_raw', Image, queue_size=10)
    bridge = CvBridge()

    times = load_times(seq_path)
    img_dir = os.path.join(seq_path, "image_0")
    rospy.loginfo(f"KITTI publisher: {len(times)} frames from {seq_path}")
    rospy.loginfo(f"Playback speed multiplier: {speed_mult} (higher = slower)")

    rospy.sleep(2.0)
    start_wall = time.time()

    for i, t in enumerate(times):
        if rospy.is_shutdown():
            break

        img_path = os.path.join(img_dir, f"{i:06d}.png")
        frame = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if frame is None:
            rospy.logwarn(f"Could not read {img_path}")
            continue

        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        msg = bridge.cv2_to_imgmsg(frame_bgr, encoding='bgr8')
        # KITTI times start at 0; offset to avoid zero/near-zero ROS stamps
        msg.header.stamp = rospy.Time.from_sec(t + 1e6)
        pub.publish(msg)

        target_wall = start_wall + t * speed_mult
        sleep_time = target_wall - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)

        if i % 200 == 0:
            rospy.loginfo(f"Published frame {i}/{len(times)}")

    rospy.loginfo("KITTI publisher: finished all frames")
    rospy.sleep(3.0)

if __name__ == "__main__":
    main()

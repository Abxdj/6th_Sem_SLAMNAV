#!/usr/bin/env python3
"""
CLAHE preprocessing node.

Subscribes: /camera/rgb/image_raw
Publishes:  /camera/image_raw  (contrast-enhanced greyscale, mono8)

Resize behaviour is configurable so the same node works for both
Gazebo/TUM (640x480) and EuRoC (native 752x480, no resize).
  rosparam _resize_width / _resize_height ; set to 0 to disable resizing.
"""
import rospy
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

bridge = CvBridge()
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

resize_w = 0
resize_h = 0

def callback(msg):
    frame = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    if resize_w > 0 and resize_h > 0:
        frame = cv2.resize(frame, (resize_w, resize_h))

    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    enhanced = clahe.apply(grey)

    out = bridge.cv2_to_imgmsg(enhanced, encoding='mono8')
    out.header.stamp = msg.header.stamp
    pub.publish(out)

rospy.init_node('clahe_node')
resize_w = rospy.get_param('~resize_width', 640)
resize_h = rospy.get_param('~resize_height', 480)

sub = rospy.Subscriber('/camera/rgb/image_raw', Image, callback)
pub = rospy.Publisher('/camera/image_raw', Image, queue_size=1)

if resize_w > 0 and resize_h > 0:
    rospy.loginfo(f"CLAHE node started - resizing to {resize_w}x{resize_h}")
else:
    rospy.loginfo("CLAHE node started - no resizing (native resolution)")

rospy.spin()

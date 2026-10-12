#!/usr/bin/env python3
"""
ResNet18 loop closure candidate proposer with adaptive percentile thresholding.

Instead of a fixed cosine threshold (which does not transfer across
sequences), this maintains a history of observed best-match scores and
only proposes a candidate when the current score exceeds a high
percentile of that history.
"""

import rospy
import numpy as np
from sensor_msgs.msg import Image
from std_msgs.msg import Int32, Int32MultiArray
from cv_bridge import CvBridge
import torch
import torchvision.models as models
import torchvision.transforms as transforms
import torch.nn.functional as F
import cv2

model = models.resnet18(pretrained=True)
model = torch.nn.Sequential(*list(model.children())[:-1])
model.eval()
if torch.cuda.is_available():
    model = model.cuda()

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

bridge = CvBridge()
descriptor_db = []
score_history = []
latest_frame = None

SKIP_RECENT = 100        # keyframes excluded as trivially recent
PERCENTILE = 98.0        # inject only scores above this percentile of history
WARMUP = 60              # min score samples before we trust the percentile
ABS_FLOOR = 0.80         # never inject below this regardless of percentile

def extract_descriptor(frame_grey):
    frame_rgb = cv2.cvtColor(frame_grey, cv2.COLOR_GRAY2RGB)
    tensor = transform(frame_rgb).unsqueeze(0)
    if torch.cuda.is_available():
        tensor = tensor.cuda()
    with torch.no_grad():
        desc = model(tensor).squeeze()
    return F.normalize(desc, dim=0)

def image_callback(msg):
    global latest_frame
    latest_frame = bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')

def keyframe_id_callback(msg):
    global latest_frame
    if latest_frame is None:
        return

    real_kf_id = msg.data
    desc = extract_descriptor(latest_frame)

    best_score, best_id = -1.0, -1
    if len(descriptor_db) > SKIP_RECENT:
        for (kid, kd) in descriptor_db[:-SKIP_RECENT]:
            score = torch.dot(desc, kd).item()
            if score > best_score:
                best_score, best_id = score, kid

    descriptor_db.append((real_kf_id, desc))

    if best_id < 0:
        rospy.loginfo(f"KF {real_kf_id} | warmup, db_size={len(descriptor_db)}")
        return

    score_history.append(best_score)

    if len(score_history) < WARMUP:
        rospy.loginfo(f"KF {real_kf_id} | best={best_score:.3f} "
                      f"| collecting stats ({len(score_history)}/{WARMUP})")
        return

    thresh = max(np.percentile(score_history, PERCENTILE), ABS_FLOOR)

    if best_score >= thresh:
        rospy.logwarn(f"LOOP CLOSURE: KF {real_kf_id} matches KF {best_id} "
                      f"| score={best_score:.3f} | adaptive_thresh={thresh:.3f}")
        m = Int32MultiArray()
        m.data = [real_kf_id, best_id]
        candidate_pub.publish(m)
    else:
        rospy.loginfo(f"KF {real_kf_id} | best={best_score:.3f} "
                      f"| thresh={thresh:.3f} | no proposal")

rospy.init_node('loop_closure_resnet18')
img_sub = rospy.Subscriber('/camera/image_raw', Image, image_callback)
kf_sub = rospy.Subscriber('/orb_slam3/new_keyframe_id', Int32, keyframe_id_callback)
candidate_pub = rospy.Publisher('/loop_closure/candidate_kfids', Int32MultiArray, queue_size=10)
rospy.loginfo(f"ResNet18 loop closure node started - adaptive P{PERCENTILE} thresholding")
rospy.spin()

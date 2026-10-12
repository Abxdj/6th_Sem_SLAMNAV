#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import Image
from std_msgs.msg import Int32, Int32MultiArray
from cv_bridge import CvBridge
import torch
import torchvision.transforms as transforms
import torch.nn.functional as F
import cv2

# Load DINO ViT-S/8
model = torch.hub.load('facebookresearch/dino:main', 'dino_vits8')
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
descriptor_db = []   # list of (real_kf_id, descriptor)
latest_frame = None
THRESHOLD = 0.855
SKIP_RECENT = 100

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

    best_score, best_id = 0, -1
    if len(descriptor_db) > SKIP_RECENT:
        for (kid, kd) in descriptor_db[:-SKIP_RECENT]:
            score = torch.dot(desc, kd).item()
            if score > best_score:
                best_score, best_id = score, kid

    descriptor_db.append((real_kf_id, desc))

    if best_score > THRESHOLD:
        rospy.logwarn(f"LOOP CLOSURE: KF {real_kf_id} matches KF {best_id} | score={best_score:.3f}")
        candidate_msg = Int32MultiArray()
        candidate_msg.data = [real_kf_id, best_id]
        candidate_pub.publish(candidate_msg)
    else:
        rospy.loginfo(f"KF {real_kf_id} processed | best_score={best_score:.3f} | db_size={len(descriptor_db)}")

rospy.init_node('loop_closure_dino')
img_sub = rospy.Subscriber('/camera/image_raw', Image, image_callback)
kf_sub = rospy.Subscriber('/orb_slam3/new_keyframe_id', Int32, keyframe_id_callback)
candidate_pub = rospy.Publisher('/loop_closure/candidate_kfids', Int32MultiArray, queue_size=10)
rospy.loginfo("DINO ViT-S/8 loop closure node started — synced to real ORB-SLAM3 keyframe IDs")
rospy.spin()

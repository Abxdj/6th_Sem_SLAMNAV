#!/usr/bin/env python3
"""
ResNet18 loop closure candidate proposer (proposal-v2).

  * The descriptor is computed on the keyframe's own image: ORB-SLAM3 publishes [kf_id, stamp] on
    /orb_slam3/new_keyframe, and the node looks the frame up by header stamp (within 1 ms) in a
    ring buffer of the last ~2 s of /camera/image_raw. No match -> logged and skipped, never a
    silent fallback to "latest frame".
  * Recent keyframes are excluded by sensor time (~exclude_recent_s, default 30 s), not by a
    keyframe count. ~skip_recent_kf >= 0 restores the old count-based exclusion for back-comparison.
  * Adaptive threshold unchanged: propose when best >= max(P98 of past best scores, 0.80),
    after 60 scored keyframes.
  * ~dump_path: on shutdown (and every 200 KFs) saves ids, stamps and descriptors for offline
    recall analysis.
Publishes Int32MultiArray [current_kf, matched_kf] on /loop_closure/candidate_kfids.
"""
import sys, threading, time, collections
import rospy
import numpy as np
from sensor_msgs.msg import Image
from std_msgs.msg import Int32MultiArray, Float64MultiArray
from cv_bridge import CvBridge
import torch
import torchvision.models as models
import torchvision.transforms as transforms
import torch.nn.functional as F
import cv2

# stdout (loginfo) and stderr (logwarn) share one file in the harness: line-buffer both so the
# log is chronological.
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

model = models.resnet18(pretrained=True)
model = torch.nn.Sequential(*list(model.children())[:-1])
model.eval()
cuda = torch.cuda.is_available()
if cuda:
    model = model.cuda()
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

bridge = CvBridge()
buf_lock = threading.Lock()
frame_buf = collections.deque()      # (stamp_s, image), oldest first
BUF_SPAN_S = 2.0
MATCH_TOL_S = 1e-3

ids, stamps, descs = [], [], []      # descriptor database, in insertion order
db_mat = None                        # (N, 512) tensor
score_history = []
counts = collections.Counter()


def extract_descriptor(frame_grey):
    frame_rgb = cv2.cvtColor(frame_grey, cv2.COLOR_GRAY2RGB)
    tensor = transform(frame_rgb).unsqueeze(0)
    if cuda:
        tensor = tensor.cuda()
    with torch.no_grad():
        desc = model(tensor).squeeze()
    return F.normalize(desc, dim=0)


def image_callback(msg):
    img = bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')
    t = msg.header.stamp.to_sec()
    with buf_lock:
        frame_buf.append((t, img))
        while frame_buf and frame_buf[-1][0] - frame_buf[0][0] > BUF_SPAN_S:
            frame_buf.popleft()


def find_frame(t):
    with buf_lock:
        best = min(frame_buf, key=lambda e: abs(e[0] - t), default=None)
    if best is not None and abs(best[0] - t) <= MATCH_TOL_S:
        return best[1]
    return None


def dump():
    if not DUMP or not ids:
        return
    np.savez(DUMP, ids=np.array(ids), stamps=np.array(stamps),
             descs=torch.stack(descs).cpu().numpy().astype(np.float32))
    rospy.loginfo(f"dumped {len(ids)} descriptors to {DUMP}")


def keyframe_callback(msg):
    global db_mat
    if len(msg.data) < 2:
        return
    kf_id, kf_t = int(msg.data[0]), float(msg.data[1])
    counts['kf'] += 1
    img = find_frame(kf_t)
    deadline = time.time() + 0.5      # the image may still be in flight to this node
    while img is None and time.time() < deadline and not rospy.is_shutdown():
        time.sleep(0.01)
        img = find_frame(kf_t)
    if img is None:
        counts['no_frame'] += 1
        rospy.logwarn(f"KF {kf_id} | NO_FRAME for stamp {kf_t:.6f} (buffer miss #{counts['no_frame']})")
        return

    desc = extract_descriptor(img)
    best_score, best_id, best_t = -1.0, -1, 0.0
    if db_mat is not None:
        sc = db_mat @ desc
        st = torch.tensor(stamps, device=sc.device, dtype=torch.float64)
        if SKIP_RECENT_KF >= 0:
            elig = torch.zeros(len(ids), dtype=torch.bool, device=sc.device)
            if len(ids) > SKIP_RECENT_KF:
                elig[:len(ids) - SKIP_RECENT_KF] = True
        else:
            elig = (kf_t - st).abs() >= EXCLUDE_S
        if bool(elig.any()):
            sc = torch.where(elig, sc, torch.full_like(sc, -2.0))
            j = int(torch.argmax(sc))
            best_score, best_id, best_t = float(sc[j]), ids[j], stamps[j]

    ids.append(kf_id); stamps.append(kf_t); descs.append(desc)
    db_mat = desc.unsqueeze(0) if db_mat is None else torch.cat([db_mat, desc.unsqueeze(0)])
    if DUMP and len(ids) % 200 == 0:
        dump()

    if best_id < 0:
        rospy.loginfo(f"KF {kf_id} | t={kf_t:.3f} | no eligible keyframe yet, db_size={len(ids)}")
        return
    score_history.append(best_score)
    if len(score_history) < WARMUP:
        rospy.loginfo(f"KF {kf_id} | best={best_score:.3f} | collecting stats ({len(score_history)}/{WARMUP})")
        return
    thresh = max(np.percentile(score_history, PERCENTILE), ABS_FLOOR)
    if best_score >= thresh:
        counts['proposals'] += 1
        rospy.logwarn(f"LOOP CLOSURE: KF {kf_id} matches KF {best_id} | score={best_score:.3f} "
                      f"| adaptive_thresh={thresh:.3f} | dt={kf_t - best_t:.1f}s")
        m = Int32MultiArray(); m.data = [kf_id, best_id]
        candidate_pub.publish(m)
    else:
        rospy.loginfo(f"KF {kf_id} | best={best_score:.3f} | thresh={thresh:.3f} | no proposal")


rospy.init_node('loop_closure_resnet18')
EXCLUDE_S = rospy.get_param('~exclude_recent_s', 30.0)
SKIP_RECENT_KF = rospy.get_param('~skip_recent_kf', -1)     # >= 0: old keyframe-count exclusion
PERCENTILE = rospy.get_param('~percentile', 98.0)
WARMUP = rospy.get_param('~warmup', 60)
ABS_FLOOR = rospy.get_param('~abs_floor', 0.80)
DUMP = rospy.get_param('~dump_path', '')
rospy.on_shutdown(lambda: (dump(), rospy.loginfo(f"node counts: {dict(counts)}")))
img_sub = rospy.Subscriber('/camera/image_raw', Image, image_callback, queue_size=200)
kf_sub = rospy.Subscriber('/orb_slam3/new_keyframe', Float64MultiArray, keyframe_callback, queue_size=1000)
candidate_pub = rospy.Publisher('/loop_closure/candidate_kfids', Int32MultiArray, queue_size=100)
mode = f"skip_recent_kf={SKIP_RECENT_KF}" if SKIP_RECENT_KF >= 0 else f"exclude_recent_s={EXCLUDE_S}"
rospy.loginfo(f"ResNet18 proposer v2 started - adaptive P{PERCENTILE}, {mode}, keyframe-image matching")
rospy.spin()

#!/usr/bin/env python3
"""Load-only arm matching ros_nodes/loop_closure_node.py v2, with no ROS coupling.

Same per-keyframe work as the v2 node (transform + ResNet18 forward + one matmul against the whole
database + stamp mask), at a fixed keyframe rate, plus per-frame image copies into a 2 s ring buffer.
Usage: load_only_v2.py [kf_hz] [img_hz]    (defaults 1.8 and 20; set from measured rates)
"""
import sys, time, threading, collections
import numpy as np, torch, cv2
import torchvision.models as models
import torchvision.transforms as transforms
import torch.nn.functional as F

KF_HZ = float(sys.argv[1]) if len(sys.argv) > 1 else 1.8
IMG_HZ = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
model = torch.nn.Sequential(*list(models.resnet18(pretrained=True).children())[:-1]).eval()
cuda = torch.cuda.is_available()
if cuda:
    model = model.cuda()
transform = transforms.Compose([
    transforms.ToPILImage(), transforms.Resize((224, 224)), transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
frame = np.random.default_rng(0).integers(0, 255, (480, 752), dtype=np.uint8)
ring = collections.deque(maxlen=int(2 * IMG_HZ) + 1)


def images():
    buf = frame.tobytes()
    while True:
        ring.append((time.time(), np.frombuffer(buf, np.uint8).reshape(frame.shape).copy()))
        time.sleep(1.0 / IMG_HZ)


threading.Thread(target=images, daemon=True).start()
print(f'load_only_v2 started kf_hz={KF_HZ} img_hz={IMG_HZ}', flush=True)
db, stamps, n = None, [], 0
next_t = time.time()
while True:
    x = transform(cv2.cvtColor(ring[-1][1] if ring else frame, cv2.COLOR_GRAY2RGB)).unsqueeze(0)
    if cuda:
        x = x.cuda()
    with torch.no_grad():
        d = F.normalize(model(x).squeeze(), dim=0)
    t = time.time()
    if db is not None:
        sc = db @ d
        el = (t - torch.tensor(stamps, device=sc.device, dtype=torch.float64)).abs() >= 30.0
        float(torch.where(el, sc, torch.full_like(sc, -2.0)).max())
    db = d.unsqueeze(0) if db is None else torch.cat([db, d.unsqueeze(0)])
    stamps.append(t); n += 1
    if n % 100 == 0:
        print(f'load_only_v2 db={n}', flush=True)
    next_t += 1.0 / KF_HZ
    time.sleep(max(0.0, next_t - time.time()))

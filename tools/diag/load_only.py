#!/usr/bin/env python3
"""H5 load-only arm: reproduce loop_closure_node.py's CPU/GPU work with no ROS coupling.

No subscriptions, no publications. Mimics, per the node's code and the measured dry-run rates:
  * ~33 Hz image decode copies (the node converts every /camera/image_raw frame at 0.5x replay)
  * ~1.8 Hz "keyframes" (median keyframe rate measured in full_r*_resnet18_dry desc.log):
    the same transform + ResNet18 forward, then the same Python loop of torch.dot(...).item()
    over a growing database, excluding the last SKIP_RECENT entries.
"""
import time, threading
import numpy as np, torch, cv2
import torchvision.models as models
import torchvision.transforms as transforms
import torch.nn.functional as F

KF_HZ, IMG_HZ, SKIP_RECENT = 1.8, 33.0, 100
model = torch.nn.Sequential(*list(models.resnet18(pretrained=True).children())[:-1]).eval()
cuda = torch.cuda.is_available()
if cuda:
    model = model.cuda()
transform = transforms.Compose([
    transforms.ToPILImage(), transforms.Resize((224, 224)), transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
rng = np.random.default_rng(0)
frame = rng.integers(0, 255, (480, 640), dtype=np.uint8)
latest = [frame]


def images():
    buf = frame.tobytes()
    while True:
        latest[0] = np.frombuffer(buf, np.uint8).reshape(480, 640).copy()
        time.sleep(1.0 / IMG_HZ)


threading.Thread(target=images, daemon=True).start()
db = []
print('load_only started', flush=True)
next_t = time.time()
while True:
    rgb = cv2.cvtColor(latest[0], cv2.COLOR_GRAY2RGB)
    x = transform(rgb).unsqueeze(0)
    if cuda:
        x = x.cuda()
    with torch.no_grad():
        d = F.normalize(model(x).squeeze(), dim=0)
    best = -1.0
    if len(db) > SKIP_RECENT:
        for kd in db[:-SKIP_RECENT]:
            s = torch.dot(d, kd).item()
            best = max(best, s)
    db.append(d)
    if len(db) % 100 == 0:
        print(f'load_only db={len(db)} best={best:.3f}', flush=True)
    next_t += 1.0 / KF_HZ
    time.sleep(max(0.0, next_t - time.time()))

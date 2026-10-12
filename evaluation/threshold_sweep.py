"""
Derives per-descriptor loop closure thresholds from EuRoC data using
corrected ground truth (position AND orientation).

For loop closure injection, PRECISION matters more than recall:
a false positive can corrupt the pose graph, a miss just means no gain.
So we report thresholds at several precision targets.
"""
import os
import numpy as np
import cv2
import torch
import torchvision.transforms as transforms
import torchvision.models as tv_models

SEQ = os.path.expanduser("~/euroc_v1/vicon_room1/V1_01_easy/extracted")
GT  = os.path.expanduser("~/euroc_v1/V1_01_easy_groundtruth_tum.txt")

MIN_GAP = 50
POS_THRESHOLD = 0.50
ORIENT_THRESHOLD = 45
SAMPLE_STRIDE = 4

device = "cuda" if torch.cuda.is_available() else "cpu"
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def load_frames():
    fr = []
    with open(os.path.join(SEQ, "mav0", "cam0", "data.csv")) as f:
        for line in f:
            if line.startswith('#') or not line.strip(): continue
            p = line.strip().split(',')
            fr.append((int(p[0]) / 1e9, p[1].strip()))
    return fr[::SAMPLE_STRIDE]

def load_gt():
    gt = []
    with open(GT) as f:
        for line in f:
            if line.startswith('#') or not line.strip(): continue
            p = line.strip().split()
            gt.append((float(p[0]),
                       np.array([float(p[1]), float(p[2]), float(p[3])]),
                       np.array([float(p[4]), float(p[5]), float(p[6]), float(p[7])])))
    return gt

def nearest_gt(t, gt):
    b = min(gt, key=lambda g: abs(g[0] - t))
    return b[1], b[2]

def quat_angle_deg(q1, q2):
    d = min(1.0, max(-1.0, abs(float(np.dot(q1, q2)))))
    return 2.0 * np.degrees(np.arccos(d))

def build_models():
    m = {}
    r18 = tv_models.resnet18(pretrained=True)
    r18 = torch.nn.Sequential(*list(r18.children())[:-1]).to(device).eval()
    m['ResNet18'] = lambda t: r18(t).squeeze()
    import timm
    eff = timm.create_model('efficientnet_b0', pretrained=True, num_classes=0).to(device).eval()
    m['EfficientNet-B0'] = lambda t: eff(t).squeeze()
    dino = torch.hub.load('facebookresearch/dino:main', 'dino_vits8').to(device).eval()
    m['DINO-ViT-S8'] = lambda t: dino(t).squeeze()
    return m

def extract(fn, path):
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None: return None
    rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    t = transform(rgb).unsqueeze(0).to(device)
    with torch.no_grad():
        return fn(t).cpu().numpy().flatten()

def l2norm(X):
    n = np.linalg.norm(X, axis=1, keepdims=True); n[n==0]=1
    return X / n

def main():
    frames = load_frames(); gt = load_gt()
    img_dir = os.path.join(SEQ, "mav0", "cam0", "data")
    meta = []
    for idx, (t, fn) in enumerate(frames):
        xyz, q = nearest_gt(t, gt)
        meta.append((idx, t, fn, xyz, q))

    pairs, y = [], []
    N = len(meta)
    for i in range(N):
        for j in range(i+1, N):
            if meta[j][0] - meta[i][0] < MIN_GAP: continue
            dist = np.linalg.norm(meta[i][3] - meta[j][3])
            ang = quat_angle_deg(meta[i][4], meta[j][4])
            pairs.append((i, j))
            y.append(1 if (dist < POS_THRESHOLD and ang < ORIENT_THRESHOLD) else 0)
    y = np.array(y)
    print(f"{len(pairs)} pairs, {y.sum()} true loops ({100*y.mean():.1f}%)\n")

    for name, fn in build_models().items():
        X = np.vstack([extract(fn, os.path.join(img_dir, m[2])) for m in meta])
        D = l2norm(X)
        s = np.array([float(np.dot(D[i], D[j])) for (i,j) in pairs])

        print(f"=== {name} ===")
        print(f"  {'thresh':>8} {'precision':>10} {'recall':>8} {'F1':>7} {'#pred':>7}")
        best = None
        for th in np.arange(0.70, 0.999, 0.005):
            pred = (s > th).astype(int)
            tp = int(((pred==1)&(y==1)).sum()); fp = int(((pred==1)&(y==0)).sum())
            fn_ = int(((pred==0)&(y==1)).sum())
            if tp+fp == 0: continue
            p = tp/(tp+fp); r = tp/(tp+fn_) if (tp+fn_) else 0
            f1 = 2*p*r/(p+r) if (p+r) else 0
            if best is None or f1 > best[3]: best = (th, p, r, f1)
            # print rows at precision milestones
            if abs(p-0.90) < 0.02 or abs(p-0.95) < 0.02 or abs(p-0.99) < 0.01:
                print(f"  {th:8.3f} {p:10.3f} {r:8.3f} {f1:7.3f} {tp+fp:7d}")
        if best:
            print(f"  best-F1 -> thresh={best[0]:.3f} precision={best[1]:.3f} "
                  f"recall={best[2]:.3f} F1={best[3]:.3f}")
        print()

if __name__ == "__main__":
    main()

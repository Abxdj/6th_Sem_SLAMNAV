"""
Tests whether PCA whitening improves descriptor discriminability.

Compares, for each descriptor:
  - raw cosine similarity (current approach)
  - PCA-whitened cosine similarity

Reports AUC and score separation for both, on EuRoC V1_02.
"""
import os, sys, time
import numpy as np
import cv2
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms
import torchvision.models as tv_models

SEQ = os.path.expanduser("~/euroc_v1/vicon_room1/V1_02_medium/extracted")
GT  = os.path.expanduser("~/euroc_v1/V1_02_medium_groundtruth_tum.txt")

MIN_GAP = 50           # frames apart to be eligible
POS_THRESHOLD = 0.50   # metres - true loop closure if GT positions within this
ORIENT_THRESHOLD = 45  # degrees - AND orientation within this (fixes earlier GT flaw)
SAMPLE_STRIDE = 4
PCA_DIM = 128          # reduce to this many whitened dimensions

device = "cuda" if torch.cuda.is_available() else "cpu"

transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

def load_frames():
    frames = []
    with open(os.path.join(SEQ, "mav0", "cam0", "data.csv")) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            p = line.strip().split(',')
            frames.append((int(p[0]) / 1e9, p[1].strip()))
    return frames[::SAMPLE_STRIDE]

def load_gt():
    gt = []
    with open(GT) as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            p = line.strip().split()
            t = float(p[0])
            xyz = np.array([float(p[1]), float(p[2]), float(p[3])])
            quat = np.array([float(p[4]), float(p[5]), float(p[6]), float(p[7])])  # x,y,z,w
            gt.append((t, xyz, quat))
    return gt

def nearest_gt(t, gt_list):
    best = min(gt_list, key=lambda g: abs(g[0] - t))
    return best[1], best[2]

def quat_angle_deg(q1, q2):
    # angle between two orientations, quaternions as x,y,z,w
    d = abs(float(np.dot(q1, q2)))
    d = min(1.0, max(-1.0, d))
    return 2.0 * np.degrees(np.arccos(d))

def build_models():
    models = {}
    r18 = tv_models.resnet18(pretrained=True)
    r18 = torch.nn.Sequential(*list(r18.children())[:-1]).to(device).eval()
    models['ResNet18'] = lambda t: r18(t).squeeze()

    import timm
    eff = timm.create_model('efficientnet_b0', pretrained=True, num_classes=0).to(device).eval()
    models['EfficientNet-B0'] = lambda t: eff(t).squeeze()

    dino = torch.hub.load('facebookresearch/dino:main', 'dino_vits8').to(device).eval()
    models['DINO-ViT-S8'] = lambda t: dino(t).squeeze()
    return models

def extract(model_fn, img_path):
    frame = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        return None
    rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    tensor = transform(rgb).unsqueeze(0).to(device)
    with torch.no_grad():
        d = model_fn(tensor)
    return d.cpu().numpy().flatten()

def pca_whiten_fit(X, dim):
    """Fit PCA + whitening on descriptor matrix X (n_samples x n_features)."""
    mu = X.mean(axis=0)
    Xc = X - mu
    # SVD is more stable than eig on covariance for high-dim data
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    dim = min(dim, Vt.shape[0])
    components = Vt[:dim]
    # whitening scale: divide by singular values (with epsilon for stability)
    eps = 1e-6
    scale = 1.0 / (S[:dim] + eps)
    return mu, components, scale

def pca_whiten_apply(X, mu, components, scale):
    Xw = (X - mu) @ components.T * scale
    # L2 normalise after whitening
    norms = np.linalg.norm(Xw, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return Xw / norms

def l2norm(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    n[n == 0] = 1
    return X / n

def compute_auc(y_true, y_score):
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    n_pos = y_true.sum()
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float('nan')
    tpr, fpr = [0.0], [0.0]
    tp = fp = 0
    for lab in y_sorted:
        if lab == 1: tp += 1
        else: fp += 1
        tpr.append(tp / n_pos)
        fpr.append(fp / n_neg)
    return float(np.trapz(tpr, fpr))

def evaluate(name, D, y_true, pairs, label):
    scores = np.array([float(np.dot(D[i], D[j])) for (i, j) in pairs])
    auc = compute_auc(y_true, scores)
    pos = scores[y_true == 1]
    neg = scores[y_true == 0]
    sep = (pos.mean() - neg.mean()) if len(pos) and len(neg) else float('nan')
    print(f"  {label:18s} AUC={auc:.3f}  pos_mean={pos.mean():.3f}  "
          f"neg_mean={neg.mean():.3f}  separation={sep:.3f}  "
          f"range=[{scores.min():.3f}, {scores.max():.3f}]")
    return auc

def main():
    print("Loading frames and ground truth...")
    frames = load_frames()
    gt = load_gt()
    print(f"{len(frames)} sampled frames (stride={SAMPLE_STRIDE})")

    img_dir = os.path.join(SEQ, "mav0", "cam0", "data")
    models = build_models()

    # Precompute ground-truth labels for all eligible pairs (same for all models)
    print("Building ground-truth pair labels (position AND orientation)...")
    meta = []
    for idx, (t, fn) in enumerate(frames):
        xyz, q = nearest_gt(t, gt)
        meta.append((idx, t, fn, xyz, q))

    pairs, y_true = [], []
    N = len(meta)
    for i in range(N):
        for j in range(i + 1, N):
            if meta[j][0] - meta[i][0] < MIN_GAP:
                continue
            dist = np.linalg.norm(meta[i][3] - meta[j][3])
            ang = quat_angle_deg(meta[i][4], meta[j][4])
            is_loop = 1 if (dist < POS_THRESHOLD and ang < ORIENT_THRESHOLD) else 0
            pairs.append((i, j))
            y_true.append(is_loop)
    y_true = np.array(y_true)
    print(f"{len(pairs)} eligible pairs, {y_true.sum()} true loop closures "
          f"({100.0*y_true.mean():.1f}%)\n")

    for name, fn in models.items():
        print(f"=== {name} ===")
        raw = []
        for (idx, t, fname, xyz, q) in meta:
            d = extract(fn, os.path.join(img_dir, fname))
            raw.append(d)
        X = np.vstack(raw)
        print(f"  descriptor dim: {X.shape[1]}")

        # Baseline: plain L2-normalised cosine
        D_raw = l2norm(X)
        evaluate(name, D_raw, y_true, pairs, "raw cosine")

        # PCA-whitened
        mu, comp, scale = pca_whiten_fit(X, PCA_DIM)
        D_w = pca_whiten_apply(X, mu, comp, scale)
        evaluate(name, D_w, y_true, pairs, f"PCA-whitened({PCA_DIM})")
        print()

if __name__ == "__main__":
    main()

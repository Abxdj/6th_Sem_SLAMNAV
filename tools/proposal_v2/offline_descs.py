#!/usr/bin/env python3
"""Offline global descriptors for the keyframes of recorded runs, with the live nodes' exact preprocessing.

Usage: offline_descs.py <model resnet18|dino|effnet> <seq1_dir> [<seq2_dir> ...] -- <run_dir> [<run_dir> ...]
Keyframe stamps (and ids, maps) come from <run>/descs.npz if present, else <run>/kf_log.csv (tools/proposal_v2/kf_logger.py).
Image = the EuRoC cam0 frame within 1 ms of the stamp, CLAHE(2.0, 8x8) at native resolution (ros_nodes/clahe_node.py,
_resize 0 0), then GRAY2RGB -> Resize(224, 224) -> ImageNet Normalize -> model -> L2-normalise, as in
ros_nodes/loop_closure_node.py (ResNet18 avgpool, 512-d), loop_closure_dino.py (DINO ViT-S/8 CLS, 384-d) and
loop_closure_efficientnet.py (timm efficientnet_b0, num_classes=0, 1280-d).
Writes <run>/descs_<model>.npz (ids, stamps, maps, descs; KFs with no image within 1 ms get a NaN row).
"""
import sys, os, csv
import numpy as np, torch, cv2
import torch.nn.functional as F
import torchvision.transforms as transforms

name = sys.argv[1]; k = sys.argv.index('--'); seqs, runs = sys.argv[2:k], sys.argv[k + 1:]
if name == 'resnet18':
    import torchvision.models as models
    model = torch.nn.Sequential(*list(models.resnet18(pretrained=True).children())[:-1])
elif name == 'dino':
    model = torch.hub.load('facebookresearch/dino:main', 'dino_vits8')
elif name == 'effnet':
    import timm
    model = timm.create_model('efficientnet_b0', pretrained=True, num_classes=0)
else:
    sys.exit('model must be resnet18, dino or effnet')
model = model.eval().cuda()
transform = transforms.Compose([transforms.ToPILImage(), transforms.Resize((224, 224)), transforms.ToTensor(),
                                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

ts, paths = [], []
for s in seqs:
    s = os.path.expanduser(s)
    for r in csv.reader(open(os.path.join(s, 'mav0/cam0/data.csv'))):
        if r[0].startswith('#'): continue
        ts.append(int(r[0]) / 1e9); paths.append(os.path.join(s, 'mav0/cam0/data', r[1].strip()))
ts = np.array(ts); o = np.argsort(ts); ts = ts[o]; paths = [paths[i] for i in o]


def image_for(t):
    j = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1)); j = j if abs(ts[j] - t) < abs(ts[j - 1] - t) else j - 1
    return paths[j] if abs(ts[j] - t) <= 0.001 else None


for run in runs:
    if os.path.exists(f'{run}/descs.npz'):
        Z = np.load(f'{run}/descs.npz'); ids, st = Z['ids'], Z['stamps']
        mp = Z['maps'] if 'maps' in Z.files else -np.ones(len(ids))
    else:
        rows = list(csv.DictReader(open(f'{run}/kf_log.csv')))
        ids = np.array([int(r['kf_id']) for r in rows]); st = np.array([float(r['stamp']) for r in rows])
        mp = np.array([int(r['map_id']) for r in rows])
    D, miss = [], 0
    with torch.no_grad():
        for t in st:
            p = image_for(float(t))
            if p is None:
                miss += 1; D.append(None); continue
            g = clahe.apply(cv2.imread(p, cv2.IMREAD_GRAYSCALE))
            x = transform(cv2.cvtColor(g, cv2.COLOR_GRAY2RGB)).unsqueeze(0).cuda()
            D.append(F.normalize(model(x).squeeze(), dim=0).cpu().numpy())
    dim = next(len(d) for d in D if d is not None)
    X = np.stack([d if d is not None else np.full(dim, np.nan, np.float32) for d in D]).astype(np.float32)
    np.savez(f'{run}/descs_{name}.npz', ids=ids, stamps=st, maps=mp, descs=X)
    print(f'{os.path.basename(run)}: {len(st)} KFs, {miss} without image, dim {dim}', flush=True)

#!/usr/bin/env python3
"""Phase 1 offline analysis of a recorded Gazebo bag (no SLAM).

One streaming pass over the bag. Writes into OUT_DIR:
  frames.csv   every frame: idx, t_rel (bag time from bag start), header stamp, seq,
               exact-duplicate flag, mean |diff| to the previous frame (1/4 subsampled)
  samples.csv  every 20th frame: intensity stats, ORB keypoints (FAST 5 / 12 / 20),
               ORB matchability to frame idx+3 (ratio-test matches, F-RANSAC inliers)
  flow.csv     every 10th frame: dense flow idx -> idx+3, fitted rotation-only model,
               parallax (residual) magnitude
  thumbs.npz   160x120 thumbnail of every 10th frame (for contact sheets / timelines)

Usage: bag_analysis.py <bag> <out_dir>
"""
import sys, csv, hashlib, os, time
import numpy as np, cv2, rosbag

BAG, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
FX, FY, CX, CY = 403.0, 536.4, 320.5, 240.5   # config/turtlebot3_waffle.yaml
GAP = 3                                        # pair offset in frames (~42 ms of bag time)

orb = {t: cv2.ORB_create(nfeatures=2000, scaleFactor=1.2, nlevels=8, fastThreshold=t)
       for t in (5, 12, 20)}
bf = cv2.BFMatcher(cv2.NORM_HAMMING)

# rotation-only flow basis on a grid (at 320x240 flow resolution, coords in full-res px)
gy, gx = np.mgrid[8:240:16, 8:320:16]
U = gx.ravel() * 2.0; V = gy.ravel() * 2.0
xn = (U - CX) / FX; yn = (V - CY) / FY
# du = FX*( x*y*wx - (1+x^2)*wy + y*wz ); dv = FY*( (1+y^2)*wx - x*y*wy - x*wz )
A = np.zeros((2 * xn.size, 3))
A[0::2] = np.c_[FX * xn * yn, -FX * (1 + xn ** 2), FX * yn]
A[1::2] = np.c_[FY * (1 + yn ** 2), -FY * xn * yn, -FY * xn]
Apinv = np.linalg.pinv(A)


def orb_stats(img, t):
    kp, des = orb[t].detectAndCompute(img, None)
    return kp, des


def match_stats(a, b, t):
    ka, da = orb_stats(a, t)
    kb, db = orb_stats(b, t)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return len(ka), 0, 0
    good = []
    for m in bf.knnMatch(da, db, k=2):
        if len(m) == 2 and m[0].distance < 0.8 * m[1].distance:
            good.append(m[0])
    if len(good) < 8:
        return len(ka), len(good), 0
    pa = np.float32([ka[m.queryIdx].pt for m in good])
    pb = np.float32([kb[m.trainIdx].pt for m in good])
    _, mask = cv2.findFundamentalMat(pa, pb, cv2.FM_RANSAC, 1.0, 0.99)
    return len(ka), len(good), int(mask.sum()) if mask is not None else 0


def flow_stats(a, b):
    sa, sb = cv2.resize(a, (320, 240)), cv2.resize(b, (320, 240))
    f = cv2.calcOpticalFlowFarneback(sa, sb, None, 0.5, 4, 15, 3, 5, 1.1, 0)
    fl = f[gy, gx].reshape(-1, 2) * 2.0        # full-res pixels
    obs = fl.ravel()
    w = Apinv @ obs
    res = (obs - A @ w).reshape(-1, 2)
    mag = np.linalg.norm(fl, axis=1); rmag = np.linalg.norm(res, axis=1)
    return (float(np.median(mag)), float(np.median(rmag)), *map(float, w),
            float(np.median(fl[:, 0])), float(np.median(fl[:, 1])))


bag = rosbag.Bag(BAG)
t0 = bag.get_start_time()
fF = open(f'{OUT}/frames.csv', 'w', newline=''); wF = csv.writer(fF)
wF.writerow(['idx', 't_rel', 'stamp', 'seq', 'dup_exact', 'mad_prev'])
fS = open(f'{OUT}/samples.csv', 'w', newline=''); wS = csv.writer(fS)
wS.writerow(['idx', 't_rel', 'mean', 'std', 'p5', 'p95', 'lap_var', 'n_levels',
             'kp5', 'kp12', 'kp20', 'm5', 'inl5', 'm20', 'inl20'])
fW = open(f'{OUT}/flow.csv', 'w', newline=''); wW = csv.writer(fW)
wW.writerow(['idx', 't_rel', 'flow_med', 'resid_med', 'wx', 'wy', 'wz', 'u_med', 'v_med'])

thumbs, thumb_idx = [], []
pending = {}          # idx -> image awaiting its idx+GAP partner
prev_small, prev_md5 = None, None
start = time.time()
for idx, (_, msg, t) in enumerate(bag.read_messages()):
    img = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.step)[:, :msg.width]
    tr = t.to_sec() - t0
    md5 = hashlib.md5(msg.data).digest()
    small = img[::4, ::4].astype(np.int16)
    mad = float(np.abs(small - prev_small).mean()) if prev_small is not None else -1
    wF.writerow([idx, f'{tr:.4f}', f'{msg.header.stamp.to_sec():.4f}', msg.header.seq,
                 int(md5 == prev_md5), f'{mad:.4f}'])
    prev_small, prev_md5 = small, md5

    if idx % 10 == 0:
        thumbs.append(cv2.resize(img, (160, 120), interpolation=cv2.INTER_AREA)); thumb_idx.append(idx)
        pending[idx] = (tr, img.copy())
    base = idx - GAP
    if base in pending:
        btr, bimg = pending.pop(base)
        wW.writerow([base, f'{btr:.4f}', *[f'{v:.5f}' for v in flow_stats(bimg, img)]])
        if base % 20 == 0:
            k5, m5, i5 = match_stats(bimg, img, 5)
            k20, m20, i20 = match_stats(bimg, img, 20)
            k12 = len(orb[12].detect(bimg, None))
            lap = cv2.Laplacian(bimg, cv2.CV_64F).var()
            p5, p95 = np.percentile(bimg, [5, 95])
            wS.writerow([base, f'{btr:.4f}', f'{bimg.mean():.2f}', f'{bimg.std():.2f}', p5, p95,
                         f'{lap:.1f}', len(np.unique(bimg)), k5, k12, k20, m5, i5, m20, i20])
    if idx % 5000 == 0:
        print(f'{idx} frames, t_rel={tr:.0f}s, {time.time() - start:.0f}s elapsed', flush=True)
        fF.flush(); fS.flush(); fW.flush()

np.savez_compressed(f'{OUT}/thumbs.npz', thumbs=np.array(thumbs), idx=np.array(thumb_idx))
for f in (fF, fS, fW): f.close()
print('done', idx + 1, 'frames in', round(time.time() - start), 's')

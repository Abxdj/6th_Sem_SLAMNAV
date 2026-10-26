#!/usr/bin/env python3
"""Fair Gate B (offline): learned top-1 vs DBoW2 raw top-1, precision-recall at matched precision.

Usage: gate_b.py <out_prefix> <gt1> <gt2> <seq1_dir> <seq2_dir> <run_dir> [<run_dir> ...]
For each run (needs descs.npz + pub.log): the keyframes the live system created (stamps from the node's dump).
  database = session-1 KFs with a GT pose; queries = session-2 KFs with a GT pose.
  learned  : cosine of the node's live descriptors (KF's own image, CLAHE, ResNet18) -> top-1 over the database
  DBoW2    : tools/proposal_v2/dbow_query (same image, CLAHE, 600x350, ORBextractor, ORBvoc, transform(..,4),
             score()) -> raw top-1 over the same database. No covisibility exclusion (nothing is connected
             across sessions before a merge anyway), no group accumulation.
PR curve per method: sweep a threshold on the top-1 score; precision = correct top-1 / retrieved,
recall = correct top-1 / queries that have >= 1 true revisit (GT dist < r AND angle < 45 deg).
Build dbow_query: g++ -O2 -std=c++14 -o dbow_query dbow_query.cc ~/ORB_SLAM3/src/ORBextractor.cc -I ~/ORB_SLAM3/include
  -I ~/ORB_SLAM3 -I /usr/local/include/opencv4 -L /usr/local/lib -lopencv_core -lopencv_imgproc -lopencv_imgcodecs
  -lopencv_features2d ~/ORB_SLAM3/Thirdparty/DBoW2/lib/libDBoW2.so   (set DBOW_QUERY to its path)
Reports recall at precision >= 0.90 and >= 0.95 (max over thresholds) and the threshold achieving it, for r = 0.5, 1, 2 m,
pooled over runs and per run. Writes <out_prefix>.json and <out_prefix>.png.
"""
import sys, os, re, json, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DBOW = os.environ.get('DBOW_QUERY', os.path.join(HERE, 'dbow_query'))
VOC = os.path.expanduser('~/ORB_SLAM3/Vocabulary/ORBvoc.txt')
RADII, ANG, PRECS = (0.5, 1.0, 2.0), 45.0, (0.90, 0.95)
LEARNED = os.environ.get('GATEB_DESCS', 'descs.npz')   # learned descriptor file per run, e.g. descs_dino.npz (offline_descs.py)


def load_tum(p):
    a = np.loadtxt(os.path.expanduser(p)); return a[:, 0], a[:, 1:4], a[:, 4:8]


def gt_at(gt, t, tol=0.01):
    ts, P, Q = gt
    i = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1))
    j = i if abs(ts[i] - t) < abs(ts[i - 1] - t) else i - 1
    return (P[j], Q[j]) if abs(ts[j] - t) <= tol else None


def images(seq):
    rows = [l.strip().split(',') for l in open(os.path.join(os.path.expanduser(seq), 'mav0/cam0/data.csv')) if l[0] != '#']
    ts = np.array([int(r[0]) / 1e9 for r in rows])
    return ts, [os.path.join(os.path.expanduser(seq), 'mav0/cam0/data', r[1].strip()) for r in rows]


def img_at(I, t):
    ts, paths = I
    j = int(np.argmin(np.abs(ts - t)))
    return paths[j] if abs(ts[j] - t) <= 0.001 else None


def pr(scores, correct, npos):
    o = np.argsort(-scores)
    tp = np.cumsum(correct[o]); k = np.arange(1, len(o) + 1)
    prec, rec = tp / k, tp / max(npos, 1)
    out = {}
    for p in PRECS:
        ok = np.where(prec >= p)[0]
        if len(ok):
            b = ok[np.argmax(rec[ok])]
            out[f'R@P{int(p * 100)}'] = round(float(rec[b]), 3); out[f'thr@P{int(p * 100)}'] = round(float(scores[o][b]), 4)
        else:
            out[f'R@P{int(p * 100)}'] = 0.0; out[f'thr@P{int(p * 100)}'] = None
    out['R@1_unthresholded'] = round(float(tp[-1] / max(npos, 1)), 3) if len(o) else None
    out['AP'] = round(float(np.sum(prec * correct[o]) / max(npos, 1)), 3)
    return out, prec, rec


def per_run(run, G, I):
    D = np.load(f'{run}/{LEARNED}'); ids, st, X = D['ids'], D['stamps'], D['descs']
    b = [tuple(map(float, m)) for m in re.findall(r'\[SESSION\] start \d+ \S+ frames=\d+ t0=([\d.]+) t1=([\d.]+)', open(f'{run}/pub.log').read())]
    sess = [0 if b[0][0] - 1 <= t <= b[0][1] + 1 else 1 if b[1][0] - 1 <= t <= b[1][1] + 1 else -1 for t in st]
    keep = [[], []]
    for i, (s, t) in enumerate(zip(sess, st)):
        if s < 0: continue
        p, im = gt_at(G[s], t), img_at(I[s], t)
        if p is not None and im is not None:
            keep[s].append((i, p, im))
    cache = f'{run}/dbow_scores.bin'
    lst = f'{run}/dbow_list.txt'
    with open(lst + '.new', 'w') as f:
        for s in (0, 1):
            for _, _, im in keep[s]: f.write(f'{s} {im}\n')
    if not (os.path.exists(cache) and os.path.exists(lst) and open(lst).read() == open(lst + '.new').read()):
        os.replace(lst + '.new', lst)
        subprocess.run([DBOW, VOC, lst, cache], check=True, stderr=subprocess.DEVNULL)
    else:
        os.remove(lst + '.new')
    raw = np.fromfile(cache, dtype=np.float32)
    n0, n1 = raw[:2].view(np.int32)
    Sd = raw[2:].reshape(n1, n0)
    assert (n0, n1) == (len(keep[0]), len(keep[1]))
    X0 = X[[k[0] for k in keep[0]]]; X1 = X[[k[0] for k in keep[1]]]
    Sl = X1 @ X0.T
    P0 = np.array([k[1][0] for k in keep[0]]); Q0 = np.array([k[1][1] for k in keep[0]])
    res = {}
    for r in RADII:
        dist = np.linalg.norm(np.array([k[1][0] for k in keep[1]])[:, None, :] - P0[None], axis=2)
        Q1 = np.array([k[1][1] for k in keep[1]])
        ang = np.degrees(2 * np.arccos(np.clip(np.abs(Q1 @ Q0.T), 0, 1)))
        T = (dist < r) & (ang < ANG)
        res[r] = dict(npos=int(T.any(1).sum()),
                      learned=(Sl.max(1), T[np.arange(n1), Sl.argmax(1)]),
                      dbow2=(Sd.max(1), T[np.arange(n1), Sd.argmax(1)]))
    return dict(n_db=int(n0), n_q=int(n1), res=res)


def main():
    out_prefix, g1, g2, q1, q2 = sys.argv[1:6]
    G = [load_tum(g1), load_tum(g2)]; I = [images(q1), images(q2)]
    runs = {os.path.basename(r.rstrip('/')): per_run(r, G, I) for r in sys.argv[6:]}
    summary = {'definition': f'top-1 over session-1 KFs; true = dist < r and angle < {ANG} deg', 'runs': {}, 'pooled': {}}
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, len(RADII), figsize=(5 * len(RADII), 4.5))
    for ax, r in zip(axs, RADII):
        pooled = {}
        for m, c in (('learned', 'tab:blue'), ('dbow2', 'tab:red')):
            sc = np.concatenate([v['res'][r][m][0] for v in runs.values()])
            co = np.concatenate([v['res'][r][m][1] for v in runs.values()])
            npos = sum(v['res'][r]['npos'] for v in runs.values())
            st, prec, rec = pr(sc, co.astype(float), npos)
            pooled[m] = st
            ax.plot(rec, prec, c=c, label=f"{m}  R@P90={st['R@P90']} R@P95={st['R@P95']}")
        pooled['queries'] = int(sum(v['n_q'] for v in runs.values())); pooled['npos'] = int(npos)
        summary['pooled'][f'{r:g}m'] = pooled
        ax.axhline(0.9, ls=':', c='k'); ax.axhline(0.95, ls=':', c='grey')
        ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.set_xlabel('recall'); ax.set_ylabel('precision')
        ax.set_title(f'< {r:g} m, < {ANG:g} deg  (queries {pooled["queries"]}, with revisit {npos})'); ax.legend(fontsize=8, loc='lower left')
    for name, v in runs.items():
        summary['runs'][name] = {'n_db': v['n_db'], 'n_q': v['n_q']}
        for r in RADII:
            summary['runs'][name][f'{r:g}m'] = {'npos': v['res'][r]['npos'], **{m: pr(v['res'][r][m][0], v['res'][r][m][1].astype(float), v['res'][r]['npos'])[0] for m in ('learned', 'dbow2')}}
    fig.suptitle(os.path.basename(out_prefix)); fig.tight_layout(); fig.savefig(out_prefix + '.png', dpi=90)
    json.dump(summary, open(out_prefix + '.json', 'w'), indent=1)
    print(json.dumps(summary['pooled'], indent=1))


if __name__ == '__main__':
    main()

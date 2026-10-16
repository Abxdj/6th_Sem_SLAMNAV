#!/usr/bin/env python3
"""Calibrate the cross-map proposer threshold on a CALIBRATION pair (never the test pair).

Usage: calibrate_xmap.py <gt_tum_concatenated> <precision_target> <radius_m> <angle_deg> <run_dir> [<run_dir> ...]
Replays the live xmap rule causally on each run's descriptor dump (descs.npz with ids, stamps, maps):
  for each KF k (in creation order), candidates = earlier KFs with map id != map(k), |dt| >= 30 s, map id >= 0;
  proposal = top-1 cosine. A proposal is correct if GT dist < radius AND angle < angle_deg.
Pooled over runs, sweep the threshold over proposal scores; tau = the LOWEST threshold whose precision
(correct / proposals with score >= tau) is >= precision_target, i.e. the max-recall operating point at that precision.
Prints JSON with tau, precision, number of proposals/correct at tau, and the full curve summary.
"""
import sys, json
import numpy as np

EXCLUDE_S = 30.0


def load_tum(p):
    a = np.loadtxt(p); return a[:, 0], a[:, 1:4], a[:, 4:8]


def gt_at(gt, t, tol=0.01):
    ts, P, Q = gt
    i = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1))
    j = i if abs(ts[i] - t) < abs(ts[i - 1] - t) else i - 1
    return (P[j], Q[j]) if abs(ts[j] - t) <= tol else None


def proposals(run, gt, R, A):
    D = np.load(f'{run}/descs.npz'); st, X, mp = D['stamps'], D['descs'], D['maps']
    out = []
    for k in range(1, len(st)):
        if mp[k] < 0: continue
        el = np.where((np.abs(st[:k] - st[k]) >= EXCLUDE_S) & (mp[:k] != mp[k]) & (mp[:k] >= 0))[0]
        if not len(el): continue
        sc = X[el] @ X[k]; j = el[int(np.argmax(sc))]
        pq, pc = gt_at(gt, st[k]), gt_at(gt, st[j])
        if pq is None or pc is None: continue
        ang = np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(pq[1], pc[1]))))))
        out.append((float(sc.max()), bool(np.linalg.norm(pq[0] - pc[0]) < R and ang < A)))
    return out


def main():
    gt = load_tum(sys.argv[1]); P, R, A = map(float, sys.argv[2:5]); runs = sys.argv[5:]
    allp, per = [], {}
    for r in runs:
        p = proposals(r, gt, R, A); allp += p
        per[r] = {'scored_kfs': len(p), 'correct_if_all_proposed': sum(c for _, c in p)}
    s = np.array([x[0] for x in allp]); c = np.array([x[1] for x in allp], float)
    o = np.argsort(-s); tp = np.cumsum(c[o]); prec = tp / np.arange(1, len(o) + 1)
    ok = np.where(prec >= P)[0]
    res = {'precision_target': P, 'radius_m': R, 'angle_deg': A, 'runs': per, 'scored_kfs_pooled': len(s),
           'correct_pooled_if_all': int(c.sum())}
    if len(ok):
        b = ok[-1]                                   # deepest prefix still meeting the target = lowest threshold
        res.update(tau=round(float(s[o][b]), 4), proposals_at_tau=int(b + 1), correct_at_tau=int(tp[b]),
                   precision_at_tau=round(float(prec[b]), 3))
    else:
        res.update(tau=None)
    for q in (0.99, 0.95, 0.90, 0.80, 0.70):
        res[f'score_q{int(q * 100)}'] = round(float(np.quantile(s, q)), 4)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()

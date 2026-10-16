#!/usr/bin/env python3
"""T4 (Gate B): cross-session proposal recall, learned vs DBoW2, from one multi-session run.

Usage: recall_t4.py <run_dir> <gt_tum_session1> <gt_tum_session2> [pos_m=0.5] [ang_deg=45]
Needs <run_dir>/descs.npz (ids, stamps, descs from loop_closure_node.py ~dump_path),
<run_dir>/mono.log ([DBOW] cur=<id> t=<stamp> loop=a,b, merge=c,d, lines) and pub.log (session bounds).
Queries: session-2 keyframes that (a) have a GT pose and (b) have at least one true revisit among
session-1 keyframes (GT position < pos_m AND orientation < ang_deg). GT is the EuRoC body frame.
  learned R@k : a true revisit is within the top-k session-1 keyframes by cosine similarity
  DBoW2 R@3   : one of DBoW2's logged candidates (loop+merge lists, <= 3 each) is a true revisit
Reported on (i) all queries and (ii) the subset that has a [DBOW] line (DBoW2 was actually queried).
"""
import sys, re, json
import numpy as np


def load_tum(p):
    a = np.loadtxt(p)
    return a[:, 0], a[:, 1:4], a[:, 4:8]   # t, xyz, qxyzw


def gt_at(gt, t, tol=0.01):
    ts, P, Q = gt
    i = np.searchsorted(ts, t)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(ts) and abs(ts[j] - t) <= tol and (best is None or abs(ts[j] - t) < abs(ts[best] - t)):
            best = j
    return (P[best], Q[best]) if best is not None else None


def ang_deg(q1, q2):
    return np.degrees(2 * np.arccos(np.clip(abs(np.dot(q1, q2)), 0, 1)))


run, g1, g2 = sys.argv[1:4]
POS = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
ANG = float(sys.argv[5]) if len(sys.argv) > 5 else 45.0
D = np.load(f'{run}/descs.npz'); ids, st, X = D['ids'], D['stamps'], D['descs']
bounds = [tuple(map(float, m)) for m in re.findall(r'\[SESSION\] start \d+ \S+ frames=\d+ t0=([\d.]+) t1=([\d.]+)', open(f'{run}/pub.log').read())]
assert len(bounds) == 2, bounds
sess = np.array([0 if bounds[0][0] - 1 <= t <= bounds[0][1] + 1 else 1 if bounds[1][0] - 1 <= t <= bounds[1][1] + 1 else -1 for t in st])
G = [load_tum(g1), load_tum(g2)]
pose = [gt_at(G[s], t) if s >= 0 else None for s, t in zip(sess, st)]
dbow = {}
for m in re.finditer(r'\[DBOW\] cur=(\d+) t=[\d.e+]+ loop=([\d,]*) merge=([\d,]*)', open(f'{run}/mono.log').read()):
    dbow[int(m.group(1))] = [int(x) for x in (m.group(2) + m.group(3)).split(',') if x]
id2i = {int(k): i for i, k in enumerate(ids)}
S1 = [i for i in range(len(ids)) if sess[i] == 0 and pose[i] is not None]
S2 = [i for i in range(len(ids)) if sess[i] == 1 and pose[i] is not None]


def true_match(q, p):
    return np.linalg.norm(pose[q][0] - pose[p][0]) < POS and ang_deg(pose[q][1], pose[p][1]) < ANG


rows = []
for q in S2:
    truth = [p for p in S1 if true_match(q, p)]
    if not truth:
        continue
    sc = X[S1] @ X[q]
    order = [S1[j] for j in np.argsort(-sc)]
    r1, r3 = order[0] in truth, any(o in truth for o in order[:3])
    cand = dbow.get(int(ids[q]))
    dq = None if cand is None else any(id2i.get(c) in truth for c in cand if c in id2i)
    rows.append((int(ids[q]), r1, r3, cand is not None, dq))
n = len(rows)
sub = [r for r in rows if r[3]]
out = {
    'run': run, 'pos_m': POS, 'ang_deg': ANG,
    'kfs_session1_with_gt': len(S1), 'kfs_session2_with_gt': len(S2),
    'queries_with_true_revisit': n,
    'learned_R@1_all': round(sum(r[1] for r in rows) / n, 3) if n else None,
    'learned_R@3_all': round(sum(r[2] for r in rows) / n, 3) if n else None,
    'queries_with_dbow_line': len(sub),
    'learned_R@1_dbowsubset': round(sum(r[1] for r in sub) / len(sub), 3) if sub else None,
    'learned_R@3_dbowsubset': round(sum(r[2] for r in sub) / len(sub), 3) if sub else None,
    'dbow2_R@3_dbowsubset': round(sum(bool(r[4]) for r in sub) / len(sub), 3) if sub else None,
}
print(json.dumps(out, indent=1))
json.dump(out, open(f'{run}/recall_t4.json', 'w'), indent=1)

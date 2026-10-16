#!/usr/bin/env python3
"""T4 (Gate B): cross-session proposal recall, learned vs DBoW2, from one multi-session run.

Usage: recall_t4.py <run_dir> <gt_tum_session1> <gt_tum_session2> [pos_m=0.5] [ang_deg=45]
Needs <run_dir>/descs.npz (ids, stamps, descs from loop_closure_node.py ~dump_path),
<run_dir>/mono.log ([DBOW] cur=<id> t=<stamp> loop=a,b, merge=c,d, lines) and pub.log (session bounds).
Queries: session-2 keyframes that (a) have a GT pose and (b) have at least one true revisit among
session-1 keyframes (GT position < pos_m AND orientation < ang_deg). GT is the EuRoC body frame.
  learned R@k : a true revisit is within the top-k session-1 keyframes by cosine similarity
  DBoW2 R@3   : one of DBoW2's logged candidates (loop+merge lists, <= 3 each) is a true revisit
Reported on (i) all queries and (ii) the subset that has a [DBOW] line (DBoW2 was actually queried),
each split at the first accepted merge ([PROP] accepted list=merge t=...). After a merge the true revisits
are covisibly connected to the query, and DetectNBestCandidates (src/KeyFrameDatabase.cc:626) skips connected
KFs by design, so DBoW2 R@3 is only comparable on PRE-merge queries. The learned database also holds KFs that
ORB-SLAM3 culled (DBoW2's database does not), so learned R@k is also given with the database restricted to
KFs alive at the end of the run (KeyFrameTrajectory_allmaps.txt), an approximation of 'alive at query time'.
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


log = open(f'{run}/mono.log', errors='replace').read()
mt = [float(x) for x in re.findall(r'\[PROP\] accepted list=merge \S+ \S+ \S+ \S+ t=([\d.]+)', log)]
T_MERGE = min(mt) if mt else float('inf')
alive = set()
try:
    A = np.loadtxt(f'{run}/KeyFrameTrajectory_allmaps.txt', ndmin=2)
    alive = {int(round(t * 1e3)) for t in A[:, 1]}
except Exception:
    pass
S1_alive = [i for i in S1 if int(round(st[i] * 1e3)) in alive]


def ranks(q, pool, truth):
    if not pool:
        return False, False
    order = [pool[j] for j in np.argsort(-(X[pool] @ X[q]))]
    return order[0] in truth, any(o in truth for o in order[:3])


rows = []
for q in S2:
    truth = [p for p in S1 if true_match(q, p)]
    if not truth:
        continue
    r1, r3 = ranks(q, S1, truth)
    a1, a3 = ranks(q, S1_alive, truth)
    cand = dbow.get(int(ids[q]))
    dq = None if cand is None else any(id2i.get(c) in truth for c in cand if c in id2i)
    rows.append(dict(id=int(ids[q]), r1=r1, r3=r3, a1=a1, a3=a3, has_dbow=cand is not None, dbow=bool(dq),
                     pre=bool(st[q] < T_MERGE), alive_truth=any(p in S1_alive for p in truth)))


def frac(rs, k):
    return round(sum(r[k] for r in rs) / len(rs), 3) if rs else None


out = {'run': run, 'pos_m': POS, 'ang_deg': ANG, 'first_merge_t': None if mt == [] else T_MERGE,
       'kfs_session1_with_gt': len(S1), 'kfs_session1_alive_at_end': len(S1_alive), 'kfs_session2_with_gt': len(S2)}
for name, rs in (('all', rows), ('premerge', [r for r in rows if r['pre']]), ('postmerge', [r for r in rows if not r['pre']])):
    sub = [r for r in rs if r['has_dbow']]
    out[name] = {'queries_with_true_revisit': len(rs), 'learned_R@1': frac(rs, 'r1'), 'learned_R@3': frac(rs, 'r3'),
                 'learned_R@1_alivedb': frac(rs, 'a1'), 'learned_R@3_alivedb': frac(rs, 'a3'),
                 'queries_with_dbow_line': len(sub), 'learned_R@1_dbowsubset': frac(sub, 'r1'),
                 'learned_R@3_dbowsubset': frac(sub, 'r3'), 'dbow2_R@3_dbowsubset': frac(sub, 'dbow'),
                 'queries_whose_truth_survives': sum(r['alive_truth'] for r in rs)}
print(json.dumps(out, indent=1))
json.dump(out, open(f'{run}/recall_t4.json', 'w'), indent=1)

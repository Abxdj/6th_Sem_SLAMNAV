#!/usr/bin/env python3
"""POST HOC analyses of the Part E runs (not pre-registered). Reads run dirs only; changes nothing.

Usage: posthoc_e.py <pairs.json> <out_json>

1. Verification stage of every external candidate evaluated in the injection arm, with the GT distance / angle of the
   (candidate KF, current KF) pair. Stages from the C5 log lines of src/LoopClosing.cc (9aad4f8):
     0 abort_near  (covisible with current KF, discarded before any geometry)
     1 bow_fail    (< 20 BoW matches)
     2 sim3_fail stage=2  (>= 20 BoW matches, Sim3 RANSAC did not converge: < 15 inliers in 300 iterations)
     3 sim3_fail stage=3  (Sim3 converged; then one of: projection matches < 50, optimised Sim3 inliers < 20,
                           guided re-projection matches < 80, < 3 covisible KFs agreeing -- the log does not say which)
     4 geom_pass   (fully verified)
   GT-correct: distance < 2 m and angle < 45 deg (the Part A/E definition), unrounded.
2. Merged injection runs: where the session-2 error sits in time relative to the merge, in the final map.
   The final map is the only trajectory saved, so this is the post-merge, post-optimisation map.
   - s1-anchored: Sim3 fitted on session-1 KFs of the spanning map, applied to all its KFs; session-2 error per window.
   - own-fit: Sim3 fitted separately on session-2 KFs before / after the merge (shape error, and scale of each).
"""
import sys, os, re, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from analyze_pv2 import umeyama_sim3
from analyze_xmap2 import kf_stamps, gt_pose

REPO = os.path.expanduser('~/mono-slam-cnn-loop-closure')
R_GT, A_GT = 2.0, 45.0
PAT = {'abort_near': re.compile(r'^\[PROP\] abort_near cand=(\d+) curKF=(\d+)'),
       'fail': re.compile(r'^\[PROP\] (bow_fail|sim3_fail) cand=(\d+) stage=(\d+) bow=(\d+) curKF=(\d+)'),
       'pass': re.compile(r'^\[PROP\] geom_pass cand=(\d+) best=(\d+) curKF=(\d+)')}


def diff(G, t1, t2):
    a, b = gt_pose(G, t1), gt_pose(G, t2)
    if a is None or b is None: return None
    return float(np.linalg.norm(a[0] - b[0])), float(np.degrees(2 * np.arccos(min(1.0, abs(float(a[1] @ b[1]))))))


def evaluations(run, G, s2_t0):
    st = kf_stamps(run); out = []
    for l in open(f'{run}/mono.log', errors='replace'):
        m = PAT['abort_near'].match(l)
        if m: c, k, s, bow = int(m[1]), int(m[2]), 0, None
        else:
            m = PAT['fail'].match(l)
            if m: c, k, s, bow = int(m[2]), int(m[5]), (1 if m[1] == 'bow_fail' else int(m[3])), int(m[4])
            else:
                m = PAT['pass'].match(l)
                if not m: continue
                c, k, s, bow = int(m[1]), int(m[3]), 4, None
        dd = diff(G, st[c], st[k]) if c in st and k in st else None
        out.append(dict(cand=c, cur=k, stage=s, bow=bow, dist=dd[0] if dd else None, ang=dd[1] if dd else None,
                        t_into_s2=round(st[k] - s2_t0, 1) if k in st else None))
    return out


def q(x):
    x = [v for v in x if v is not None]
    return None if not x else dict(n=len(x), min=round(min(x), 2), med=round(float(np.median(x)), 2), max=round(max(x), 2))


def assoc(T, G, tol=0.01):
    gt_t = G[:, 0]; P, Q, ts = [], [], []
    for row in T:
        i = np.searchsorted(gt_t, row[0]); js = [j for j in (i - 1, i) if 0 <= j < len(gt_t)]
        j = min(js, key=lambda j: abs(gt_t[j] - row[0]))
        if abs(gt_t[j] - row[0]) <= tol: P.append(row[1:4]); Q.append(G[j, 1:4]); ts.append(row[0])
    return np.array(P), np.array(Q), np.array(ts)


def rmse(e): return round(float(np.sqrt((e ** 2).mean())), 4) if len(e) else None


def own_fit(P, Q):
    if len(P) < 10: return None, None
    s, R, t = umeyama_sim3(P, Q)
    return rmse(np.linalg.norm((s * (R @ P.T)).T + t - Q, axis=1)), round(float(s), 3)


def merge_profile(run, G, bounds, t_merge):
    A = np.loadtxt(f'{run}/KeyFrameTrajectory_allmaps.txt', ndmin=2)
    (a1, b1), (a2, b2) = bounds
    best = None
    for mid in np.unique(A[:, 0]):
        T = A[A[:, 0] == mid][:, 1:]
        n1 = ((T[:, 0] >= a1 - 1) & (T[:, 0] <= b1 + 1)).sum(); n2 = ((T[:, 0] >= a2 - 1) & (T[:, 0] <= b2 + 1)).sum()
        if n1 and n2 and (best is None or len(T) > len(best)): best = T
    if best is None: return None
    T = best[np.argsort(best[:, 0])]
    P, Q, ts = assoc(T, G)
    s1 = ts <= b1 + 1; s2 = ts >= a2 - 1
    s, R, t = umeyama_sim3(P[s1], Q[s1])
    e = np.linalg.norm((s * (R @ P.T)).T + t - Q, axis=1)
    rel = ts - t_merge
    win = {'s2_before_merge': s2 & (rel < 0), 'merge_0_5s': s2 & (rel >= 0) & (rel < 5),
           'merge_5_20s': s2 & (rel >= 5) & (rel < 20), 'merge_20s_end': s2 & (rel >= 20)}
    out = dict(n_s1=int(s1.sum()), n_s2=int(s2.sum()), s1_anchor_scale=round(float(s), 3),
               s1_anchored_err_s1=rmse(e[s1]), s1_anchored_err=dict((k, rmse(e[m])) for k, m in win.items()),
               s1_anchored_err_max_s2=round(float(e[s2].max()), 3))
    # error curve in 10 s bins of session-2 time relative to merge (s1-anchored)
    out['s1_anchored_curve'] = [[int(b0), rmse(e[s2 & (rel >= b0) & (rel < b0 + 10)])] for b0 in range(int(np.floor(rel[s2].min() / 10) * 10), int(rel[s2].max()) + 1, 10)]
    pre, post = s2 & (rel < 0), s2 & (rel >= 0)
    out['own_fit_s2_all'] = own_fit(P[s2], Q[s2]); out['own_fit_s2_pre'] = own_fit(P[pre], Q[pre]); out['own_fit_s2_post'] = own_fit(P[post], Q[post])
    out['own_fit_s1'] = own_fit(P[s1], Q[s1])
    return out


def main():
    pairs = json.load(open(sys.argv[1])); res = {'note': 'POST HOC, not pre-registered', 'stages': {}, 'merged_runs': {}}
    for pair, cfg in pairs.items():
        G = np.loadtxt(os.path.expanduser(cfg['gt']))
        runs = sorted(glob.glob(f"{REPO}/results/proposal_v2/runs/{cfg['tag']}_r*_resnet18"), key=lambda p: int(re.search(r'_r(\d+)_', p).group(1)))
        allev = []
        for r in runs:
            d = json.load(open(f'{r}/pv2_summary.json')); b = d['session_bounds']
            ev = evaluations(r, G, b[1][0]); [x.update(run=os.path.basename(r)) for x in ev]; allev += ev
            for x in d['accepted']:
                if x['list'] != 'merge': continue
                st = kf_stamps(r); c, m = int(x['curKF']), int(x['matchedKF'])
                dd = diff(G, st[m], st[c])
                mp = merge_profile(r, G, b, st[c])
                res['merged_runs'][os.path.basename(r)] = dict(pair=pair, src=x['src'], merge_dist=round(dd[0], 3), merge_ang=round(dd[1], 1),
                                                               t_into_s2=round(st[c] - b[1][0], 1), n_merges=d['counts_log']['merge'],
                                                               loops_after=sum(1 for y in d['accepted'] if y['list'] == 'loop'), **(mp or {}))
        ok = [x for x in allev if x['dist'] is not None and x['dist'] < R_GT and x['ang'] < A_GT]
        wrong = [x for x in allev if x['dist'] is not None and not (x['dist'] < R_GT and x['ang'] < A_GT)]
        S = {}
        for name, L in (('gt_correct', ok), ('gt_wrong', wrong)):
            S[name] = {'n': len(L), 'by_stage': {s: sum(1 for x in L if x['stage'] == s) for s in range(5)},
                       'per_stage': {s: dict(dist=q([x['dist'] for x in L if x['stage'] == s]), ang=q([x['ang'] for x in L if x['stage'] == s]),
                                             bow=q([x['bow'] for x in L if x['stage'] == s]), t_into_s2=q([x['t_into_s2'] for x in L if x['stage'] == s]))
                                     for s in range(5) if any(x['stage'] == s for x in L)}}
        S['no_gt'] = sum(1 for x in allev if x['dist'] is None)
        S['n_evaluations'] = len(allev)
        # GT-correct evaluations near the revisit regions: time profile
        S['gt_correct_t_into_s2_hist_10s'] = {int(k): int(v) for k, v in zip(*np.unique([int(x['t_into_s2'] // 10 * 10) for x in ok if x['t_into_s2'] is not None], return_counts=True))} if ok else {}
        res['stages'][pair] = S
    json.dump(res, open(sys.argv[2], 'w'), indent=1)
    print(json.dumps(res['stages'], indent=1)); print(json.dumps(res['merged_runs'], indent=1))


if __name__ == '__main__':
    main()

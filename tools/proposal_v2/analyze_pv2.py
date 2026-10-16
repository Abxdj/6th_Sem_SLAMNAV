#!/usr/bin/env python3
"""Per-run summary for proposal-v2 runs (EuRoC harness or replay_bag.sh).

Usage: analyze_pv2.py <gt_tum|-> <run_dir> [<run_dir> ...]   -> prints one JSON per run, writes <run>/pv2_summary.json
  - counts, keyframes, Mono input drop % : tools/diag/summarize_run.py
  - [PROP-FINAL] outcome counters (last one printed; [PROP-STATS] if FINAL is missing, flagged)
  - accepted loops/merges with attribution ([PROP] accepted list=.. src=ext|dbow2), merge wall-ordered sensor times
  - ATE per live map (KeyFrameTrajectory_allmaps.txt, Sim3 Umeyama, GT association within 10 ms),
    and for multi-session runs (pub.log has [SESSION] start lines) which sessions each map spans.
"""
import sys, os, re, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'diag'))
from summarize_run import summarize


def umeyama_sim3(src, dst):
    """Least-squares s, R, t with dst ~ s R src + t."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    U, D, Vt = np.linalg.svd(xd.T @ xs / len(src))
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    s = np.trace(np.diag(D) @ S) / xs.var(0).sum()
    return s, R, mu_d - s * R @ mu_s


def ate(traj, gt, tol=0.01):
    gt_t = gt[:, 0]
    P, G = [], []
    for row in traj:
        i = np.searchsorted(gt_t, row[0])
        js = [j for j in (i - 1, i) if 0 <= j < len(gt_t)]
        j = min(js, key=lambda j: abs(gt_t[j] - row[0]))
        if abs(gt_t[j] - row[0]) <= tol:
            P.append(row[1:4]); G.append(gt[j, 1:4])
    if len(P) < 10:
        return None, len(P)
    P, G = np.array(P), np.array(G)
    s, R, t = umeyama_sim3(P, G)
    e = np.linalg.norm((s * (R @ P.T)).T + t - G, axis=1)
    return float(np.sqrt((e ** 2).mean())), len(P)


def prop_counters(log):
    fin = re.findall(r'\[PROP-FINAL\]([^\n]*)', log)
    src, line = ('final', fin[-1]) if fin else (None, None)
    if line is None:
        st = re.findall(r'\[PROP-STATS\]([^\n]*)', log)
        if st:
            src, line = 'stats_last(no FINAL)', st[-1]
    d = {k: int(v) for k, v in re.findall(r'(\w+)=(-?\d+)', line)} if line else {}
    return src, d


def main():
    gt = None if sys.argv[1] == '-' else np.loadtxt(sys.argv[1])
    for run in sys.argv[2:]:
        out = summarize(run)
        log = open(f'{run}/mono.log', errors='replace').read()
        out['prop_src'], out['prop'] = prop_counters(log)
        out['accepted'] = [dict(re.findall(r'(\w+)=(\S+)', l)) for l in re.findall(r'\[PROP\] accepted ([^\n]*)', log)]
        out['session_events'] = re.findall(r'\[SESSION\][^\n]*', log)
        bounds = []
        if os.path.exists(f'{run}/pub.log'):
            bounds = [tuple(map(float, m)) for m in re.findall(r'\[SESSION\] start \d+ \S+ frames=\d+ t0=([\d.]+) t1=([\d.]+)', open(f'{run}/pub.log').read())]
        out['session_bounds'] = bounds
        maps = []
        p = f'{run}/KeyFrameTrajectory_allmaps.txt'
        if os.path.exists(p) and os.path.getsize(p) > 0:
            A = np.loadtxt(p, ndmin=2)
            for mid in np.unique(A[:, 0]).astype(int):
                T = A[A[:, 0] == mid][:, 1:]
                T = T[np.argsort(T[:, 0])]
                m = {'map_id': int(mid), 'kfs': len(T), 't0': round(float(T[0, 0]), 2), 't1': round(float(T[-1, 0]), 2)}
                if bounds:
                    m['kfs_per_session'] = [int(((T[:, 0] >= a - 1) & (T[:, 0] <= b + 1)).sum()) for a, b in bounds]
                if gt is not None:
                    m['ate_sim3_m'], m['ate_n'] = ate(T, gt)
                    if m['ate_sim3_m'] is not None:
                        m['ate_sim3_m'] = round(m['ate_sim3_m'], 4)
                maps.append(m)
        out['live_maps'] = maps
        print(json.dumps(out))
        json.dump(out, open(f'{run}/pv2_summary.json', 'w'), indent=1)


if __name__ == '__main__':
    main()

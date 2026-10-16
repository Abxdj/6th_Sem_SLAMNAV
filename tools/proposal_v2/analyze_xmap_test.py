#!/usr/bin/env python3
"""Pre-registered analysis of the cross-map proposer test (results/proposal_v2/PREREG.md).

Usage: analyze_xmap_test.py <tag_prefix> <gt_concat> <gt1> <gt2> <out_json>
  e.g. analyze_xmap_test.py X_MH0204 ~/euroc_mh/MH_02_MH_04_groundtruth_tum.txt ~/euroc_mh/MH_02_easy_groundtruth_tum.txt ~/euroc_mh/MH_04_difficult_groundtruth_tum.txt out.json
Primary: maps merged (>= 1 'Merge finished') per run; injection vs control and vs load-only, Fisher exact two-sided;
merge counts, Mann-Whitney U two-sided. Attribution of accepted merges (src=ext|dbow2). Injection-arm level-1
outcomes. Sim3 ATE of the live map spanning both sessions (merged runs). Descriptive extra: GT correctness of the
node's live XMAP proposals (2 m / 45 deg, the PREREG definition).
"""
import sys, os, re, glob, json, subprocess
import numpy as np
from scipy.stats import fisher_exact, mannwhitneyu

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
tag, gtc, g1, g2, outp = sys.argv[1:6]
ARMS = ['none', 'load_only', 'resnet18']
runs = {a: sorted(glob.glob(f'{REPO}/results/proposal_v2/runs/{tag}_r*_{a}'), key=lambda p: int(re.search(r'_r(\d+)_', p).group(1))) for a in ARMS}
allruns = [r for a in ARMS for r in runs[a]]
subprocess.run([sys.executable, f'{HERE}/analyze_pv2.py', os.path.expanduser(gtc)] + allruns, check=True, stdout=subprocess.DEVNULL)
S = {r: json.load(open(f'{r}/pv2_summary.json')) for r in allruns}


def load_tum(p):
    a = np.loadtxt(os.path.expanduser(p)); return a[:, 0], a[:, 1:4], a[:, 4:8]


def gt_at(G, t, tol=0.01):
    ts, P, Q = G
    i = int(np.clip(np.searchsorted(ts, t), 1, len(ts) - 1)); j = i if abs(ts[i] - t) < abs(ts[i - 1] - t) else i - 1
    return (P[j], Q[j]) if abs(ts[j] - t) <= tol else None


Gc = load_tum(gtc)
res = {'tag': tag, 'arms': {}, 'tests': {}, 'runs': {}}
for a in ARMS:
    rows = []
    for r in runs[a]:
        d = S[r]; name = os.path.basename(r)
        merges = d['counts_log']['merge']
        span = [m for m in d['live_maps'] if len(m.get('kfs_per_session', [])) == 2 and all(k > 0 for k in m['kfs_per_session'])]
        row = dict(run=name, exit=d['meta']['mono_exit'], traj=bool(d.get('traj_kfs_final_map')), merges=merges,
                   merged=merges > 0, accepted=[(x['list'], x['src'], x.get('matchedKF'), x.get('curKF')) for x in d['accepted']],
                   merge_t_into_s2=[round(float(x['t']) - d['session_bounds'][1][0], 1) for x in d['accepted'] if x['list'] == 'merge'] if len(d['session_bounds']) == 2 else None,
                   ate_spanning_map=span[0]['ate_sim3_m'] if span else None, drop_pct=d.get('mono_drop_pct'),
                   prop=d['prop'] if a == 'resnet18' else None, crash_midrun=not d.get('traj_kfs_final_map'))
        if a == 'resnet18':
            # live XMAP proposals vs GT
            st = {}
            if os.path.exists(f'{r}/descs.npz'):
                Z = np.load(f'{r}/descs.npz'); st = dict(zip(Z['ids'].astype(int).tolist(), Z['stamps'].tolist()))
            ok = n = 0
            for m in re.finditer(r'XMAP PROPOSAL: KF (\d+) \(map \d+\) matches KF (\d+)', open(f'{r}/desc.log', errors='replace').read()):
                q, c = int(m.group(1)), int(m.group(2))
                if q in st and c in st:
                    pq, pc = gt_at(Gc, st[q]), gt_at(Gc, st[c])
                    if pq is not None and pc is not None:
                        n += 1
                        ang = np.degrees(2 * np.arccos(min(1.0, abs(float(np.dot(pq[1], pc[1]))))))
                        ok += int(np.linalg.norm(pq[0] - pc[0]) < 2.0 and ang < 45)
            row['xmap_proposals_with_gt'] = n; row['xmap_proposals_correct_2m45'] = ok
        rows.append(row); res['runs'][name] = row
    m = [x['merges'] for x in rows]
    res['arms'][a] = dict(n=len(rows), merged=sum(x['merged'] for x in rows), merge_counts=m,
                          ate_merged=[x['ate_spanning_map'] for x in rows if x['merged'] and x['ate_spanning_map'] is not None],
                          src=dict(ext=sum(1 for x in rows for y in x['accepted'] if y[0] == 'merge' and y[1] == 'ext'),
                                   dbow2=sum(1 for x in rows for y in x['accepted'] if y[0] == 'merge' and y[1] == 'dbow2')),
                          midrun_crashes=sum(x['crash_midrun'] for x in rows), drop_pct=[x['drop_pct'] for x in rows])
    e = res['arms'][a]['ate_merged']
    if e:
        res['arms'][a]['ate_merged_mean'] = round(float(np.mean(e)), 4); res['arms'][a]['ate_merged_range'] = [min(e), max(e)]
inj = res['arms']['resnet18']
for b in ('none', 'load_only'):
    o = res['arms'][b]
    tab = [[inj['merged'], inj['n'] - inj['merged']], [o['merged'], o['n'] - o['merged']]]
    res['tests'][f'resnet18_vs_{b}'] = dict(fisher_table=tab, fisher_p=round(float(fisher_exact(tab)[1]), 4),
                                            mannwhitney_p=round(float(mannwhitneyu(inj['merge_counts'], o['merge_counts'], alternative='two-sided').pvalue), 4))
tot = {}
for x in res['runs'].values():
    if x['prop']:
        for k, v in x['prop'].items(): tot[k] = tot.get(k, 0) + v
res['injection_outcomes_total'] = tot
res['xmap_live_precision_2m45'] = [sum(x.get('xmap_proposals_correct_2m45', 0) for x in res['runs'].values()),
                                   sum(x.get('xmap_proposals_with_gt', 0) for x in res['runs'].values())]
json.dump(res, open(outp, 'w'), indent=1)
print(json.dumps({k: res[k] for k in ('arms', 'tests', 'injection_outcomes_total', 'xmap_live_precision_2m45')}, indent=1))

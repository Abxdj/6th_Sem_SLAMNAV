#!/usr/bin/env python3
"""Pre-registered analysis of the multi-pair cross-map test (results/proposal_v2/PREREG.md Part C).

Usage: analyze_xmap2.py <pairs.json> <out_json> [--max-block K]   (K: use runs r1..rK only, for a batch stopped early)
pairs.json: {"<PAIR>": {"tag": "X2_<PAIR>", "gt": <concatenated GT tum>, "gt1": ..., "gt2": ...}, ...}
Runs: results/proposal_v2/runs/<tag>_r<k>_<arm>, arm in none | load_only | resnet18.

Primary   : merged (>= 1 'Merge finished') yes/no, injection vs control, stratified by pair: Cochran-Mantel-Haenszel
            chi-square (1 df, no continuity correction, two-sided) and the Mantel-Haenszel common odds ratio.
            Sensitivity (small n): exact conditional stratified test of a common odds ratio of 1.
            Sensitivity (pre-registered): the same CMH / exact test on independent pairs only (pairs.json "independent").
Prediction: per pair, control rate >= 0.8 -> injection - control <= 0.2; control rate <= 0.5 -> difference >= 0.3.
Secondary : time to first merge (s into session 2, from the merge's current-KF stamp); never-merged runs censored and
            ranked last; Mann-Whitney U per pair, injection vs control and vs load-only.
Secondary : the same CMH for injection vs load-only; per pair, Fisher exact (two-sided) injection vs control and vs
            load-only, and Mann-Whitney U (two-sided) on merge counts.
Reported  : attribution of every accepted merge (src=ext|dbow2) and its GT distance / angle (KF stamps from kf_log.csv,
            every arm); level-1 proposal outcomes per injection run; Sim3 ATE per session (each session's KFs in the map
            holding most of them) and of the map spanning both sessions; cost of failed proposals from the C7 counters
            (attempts and verification time of our candidates that reached BoW matching but did not verify, stages 1-3)
            and place-recognition time per KF per arm; GT precision of the node's live proposals (2 m / 45 deg).
"""
import sys, os, re, glob, json, subprocess
import numpy as np
from scipy.stats import fisher_exact, mannwhitneyu, chi2

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
ARMS = ['none', 'load_only', 'resnet18']
ns = {'np': np}
_src = open(f'{HERE}/analyze_pv2.py').read()
exec(_src[_src.index('def umeyama_sim3'):_src.index('def prop_counters')], ns)
ate = ns['ate']


def cmh(tables):
    """tables: list of [[a, b], [c, d]] (rows: treatment, comparison; cols: merged, not merged)."""
    num = var = orn = ord_ = 0.0
    for (a, b), (c, d) in tables:
        n = a + b + c + d
        if n < 2: continue
        num += a - (a + b) * (a + c) / n
        var += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
        orn += a * d / n; ord_ += b * c / n
    if var == 0:
        return dict(chi2=None, p=None, mh_odds_ratio=None, note='no informative stratum')
    x = num * num / var
    return dict(chi2=round(x, 3), p=round(float(chi2.sf(x, 1)), 4),
                mh_odds_ratio=(round(orn / ord_, 3) if ord_ > 0 else 'inf'))


def exact_stratified(tables):
    """Exact conditional test of a common odds ratio of 1 (sum over strata of a, given all margins): convolution of the
    per-stratum hypergeometric distributions; two-sided p = total probability of outcomes no more likely than observed."""
    from scipy.stats import hypergeom
    dist, obs = np.array([1.0]), 0
    lo = 0
    for (a, b), (c, d) in tables:
        n, r1, c1 = a + b + c + d, a + b, a + c
        k = np.arange(max(0, r1 + c1 - n), min(r1, c1) + 1)
        pk = hypergeom.pmf(k, n, c1, r1)
        dist = np.convolve(dist, pk); lo += k[0]; obs += a
    po = dist[obs - lo]
    return round(float(dist[dist <= po * (1 + 1e-7)].sum()), 4)


def gt_pose(G, t, tol=0.01):
    j = int(np.argmin(np.abs(G[:, 0] - t)))
    return (G[j, 1:4], G[j, 4:8]) if abs(G[j, 0] - t) <= tol else None


def pose_diff(G, t1, t2):
    a, b = gt_pose(G, t1), gt_pose(G, t2)
    if a is None or b is None: return None
    return round(float(np.linalg.norm(a[0] - b[0])), 2), round(float(np.degrees(2 * np.arccos(min(1.0, abs(float(a[1] @ b[1])))))), 1)


def kf_stamps(run):
    st = {}
    if os.path.exists(f'{run}/kf_log.csv'):
        for l in open(f'{run}/kf_log.csv').read().splitlines()[1:]:
            w = l.split(','); st[int(w[1])] = float(w[2])
    elif os.path.exists(f'{run}/descs.npz'):
        Z = np.load(f'{run}/descs.npz'); st = dict(zip(Z['ids'].astype(int).tolist(), Z['stamps'].tolist()))
    return st


def session_ate(run, bounds, G):
    p = f'{run}/KeyFrameTrajectory_allmaps.txt'
    if not (os.path.exists(p) and os.path.getsize(p) > 0) or len(bounds) != 2: return [None, None]
    A = np.loadtxt(p, ndmin=2); out = []
    for a, b in bounds:
        ins = (A[:, 1] >= a - 1) & (A[:, 1] <= b + 1)
        if not ins.any(): out.append(None); continue
        ids, cnt = np.unique(A[ins, 0], return_counts=True); mid = ids[np.argmax(cnt)]
        T = A[ins & (A[:, 0] == mid)][:, 1:]; T = T[np.argsort(T[:, 0])]
        e, n = ate(T, G); out.append(round(e, 4) if e is not None else None)
    return out


def main():
    pairs = json.load(open(sys.argv[1])); outp = sys.argv[2]
    K = int(sys.argv[sys.argv.index('--max-block') + 1]) if '--max-block' in sys.argv else 10 ** 9
    res = {'pairs': {}, 'primary': {}, 'secondary': {}, 'max_block': (K if K < 10 ** 9 else None)}
    t_inj_ctrl, t_inj_load, t_inj_ctrl_ind = [], [], []
    for pair, cfg in pairs.items():
        G = np.loadtxt(os.path.expanduser(cfg['gt']))
        runs = {a: sorted(glob.glob(f"{REPO}/results/proposal_v2/runs/{cfg['tag']}_r*_{a}"), key=lambda p: int(re.search(r'_r(\d+)_', p).group(1))) for a in ARMS}
        runs = {a: [r for r in v if int(re.search(r'_r(\d+)_', r).group(1)) <= K] for a, v in runs.items()}
        allruns = [r for a in ARMS for r in runs[a]]
        if not allruns: continue
        subprocess.run([sys.executable, f'{HERE}/analyze_pv2.py', os.path.expanduser(cfg['gt'])] + allruns, check=True, stdout=subprocess.DEVNULL)
        P = {'arms': {}, 'runs': {}, 'tests': {}, 'independent': bool(cfg.get('independent', False))}
        arm_rows = {}
        for a in ARMS:
            rows = arm_rows[a] = []
            for r in runs[a]:
                d = json.load(open(f'{r}/pv2_summary.json')); name = os.path.basename(r); b = d['session_bounds']
                st = kf_stamps(r); pr = d.get('prop') or {}
                acc = []
                for x in d['accepted']:
                    m, c = int(x.get('matchedKF', -1)), int(x.get('curKF', -1))
                    acc.append(dict(list=x['list'], src=x['src'], matchedKF=m, curKF=c,
                                    t_into_s2=(round(st[c] - b[1][0], 1) if c in st and len(b) == 2 else None),
                                    gt_dist_ang=(pose_diff(G, st[m], st[c]) if m in st and c in st else None)))
                span = [m for m in d['live_maps'] if len(m.get('kfs_per_session', [])) == 2 and all(k > 0 for k in m['kfs_per_session'])]
                fail = {s: (pr.get(f'n_ext_stage{s}', 0), pr.get(f'us_ext_stage{s}', 0)) for s in (1, 2, 3)}
                row = dict(exit=d['meta']['mono_exit'], crash_midrun=not d.get('traj_kfs_final_map'), merges=d['counts_log']['merge'],
                           merged=d['counts_log']['merge'] > 0, accepted=acc, n_kf_logged=len(st),
                           ate_spanning_map=span[0]['ate_sim3_m'] if span else None, ate_per_session=session_ate(r, b, G),
                           drop_pct=d.get('mono_drop_pct'),
                           detect_ms_per_kf=(round(pr['us_detect_total'] / 1000 / pr['n_detect_calls'], 3) if pr.get('n_detect_calls') else None),
                           ext_failed_attempts=sum(v[0] for v in fail.values()), ext_failed_ms=round(sum(v[1] for v in fail.values()) / 1000, 1),
                           ext_failed_by_stage={s: dict(n=v[0], ms=round(v[1] / 1000, 1)) for s, v in fail.items()},
                           dbow2_eval_ms=round(sum(v for k, v in pr.items() if k.startswith('us_dbow2_stage')) / 1000, 1),
                           prop=pr if a == 'resnet18' else None)
                tm = [x['t_into_s2'] for x in acc if x['list'] == 'merge' and x['t_into_s2'] is not None]
                row['first_merge_t_into_s2'] = min(tm) if tm else None
                if a == 'resnet18' and os.path.exists(f'{r}/desc.log'):
                    ok = n = 0
                    for m in re.finditer(r'XMAP PROPOSAL: KF (\d+) \(map \d+\) matches KF (\d+)', open(f'{r}/desc.log', errors='replace').read()):
                        q, c = int(m.group(1)), int(m.group(2))
                        if q in st and c in st:
                            pd = pose_diff(G, st[q], st[c])
                            if pd: n += 1; ok += int(pd[0] < 2.0 and pd[1] < 45)
                    row['xmap_proposals_with_gt'], row['xmap_proposals_correct_2m45'] = n, ok
                rows.append(row); P['runs'][name] = row
            merged = sum(x['merged'] for x in rows)
            P['arms'][a] = dict(n=len(rows), merged=merged, merge_counts=[x['merges'] for x in rows],
                                src=dict(ext=sum(1 for x in rows for y in x['accepted'] if y['list'] == 'merge' and y['src'] == 'ext'),
                                         dbow2=sum(1 for x in rows for y in x['accepted'] if y['list'] == 'merge' and y['src'] == 'dbow2')),
                                midrun_crashes=sum(x['crash_midrun'] for x in rows),
                                ate_spanning_merged=[x['ate_spanning_map'] for x in rows if x['merged']],
                                ate_session1=[x['ate_per_session'][0] for x in rows], ate_session2=[x['ate_per_session'][1] for x in rows],
                                detect_ms_per_kf=[x['detect_ms_per_kf'] for x in rows],
                                first_merge_t_into_s2=[x['first_merge_t_into_s2'] if x['merged'] else None for x in rows],
                                ext_failed_attempts=sum(x['ext_failed_attempts'] for x in rows), ext_failed_ms=round(sum(x['ext_failed_ms'] for x in rows), 1))
        inj = P['arms']['resnet18']
        for b, store in (('none', t_inj_ctrl), ('load_only', t_inj_load)):
            o = P['arms'][b]
            tab = [[inj['merged'], inj['n'] - inj['merged']], [o['merged'], o['n'] - o['merged']]]
            store.append(tab)
            if b == 'none' and cfg.get('independent'): t_inj_ctrl_ind.append(tab)
            mw = mannwhitneyu(inj['merge_counts'], o['merge_counts'], alternative='two-sided').pvalue if inj['n'] and o['n'] else None
            P['tests'][f'resnet18_vs_{b}'] = dict(table=tab, fisher_p=round(float(fisher_exact(tab)[1]), 4),
                                                  mannwhitney_p=(round(float(mw), 4) if mw is not None and not np.isnan(mw) else None))
            # time to first merge: never-merged runs are censored and rank after every merged run (all censored at the
            # same point, the end of session 2); a merged run without a KF stamp is excluded
            cen = lambda arm: [(1e9 if not x['merged'] else x['first_merge_t_into_s2']) for x in arm_rows[arm] if not (x['merged'] and x['first_merge_t_into_s2'] is None)]
            ti, to = cen('resnet18'), cen(b)
            P['tests'][f'time_to_first_merge_resnet18_vs_{b}'] = dict(
                n=[len(ti), len(to)], mannwhitney_p=(round(float(mannwhitneyu(ti, to, alternative='two-sided').pvalue), 4) if ti and to and len(set(ti + to)) > 1 else None))
            dk = [x for x in inj['detect_ms_per_kf'] if x is not None], [x for x in o['detect_ms_per_kf'] if x is not None]
            if dk[0] and dk[1]:
                P['tests'][f'detect_ms_per_kf_resnet18_vs_{b}'] = dict(median=[float(np.median(dk[0])), float(np.median(dk[1]))],
                                                                     mannwhitney_p=round(float(mannwhitneyu(*dk, alternative='two-sided').pvalue), 4))
        tot = {}
        for x in P['runs'].values():
            for k, v in (x['prop'] or {}).items(): tot[k] = tot.get(k, 0) + v
        P['injection_outcomes_total'] = tot
        P['xmap_live_precision_2m45'] = [sum(x.get('xmap_proposals_correct_2m45', 0) for x in P['runs'].values()),
                                         sum(x.get('xmap_proposals_with_gt', 0) for x in P['runs'].values())]
        res['pairs'][pair] = P
    res['primary']['cmh_resnet18_vs_none'] = dict(tables=t_inj_ctrl, **cmh(t_inj_ctrl), exact_stratified_p=exact_stratified(t_inj_ctrl))
    res['sensitivity_independent_pairs'] = dict(pairs=[p for p, v in res['pairs'].items() if v['independent']], tables=t_inj_ctrl_ind,
                                                **cmh(t_inj_ctrl_ind), exact_stratified_p=exact_stratified(t_inj_ctrl_ind) if t_inj_ctrl_ind else None)
    pred = {}
    for p, v in res['pairs'].items():
        pc = v['arms']['none']['merged'] / max(v['arms']['none']['n'], 1); pi = v['arms']['resnet18']['merged'] / max(v['arms']['resnet18']['n'], 1)
        band = 'high' if pc >= 0.8 else 'low' if pc <= 0.5 else 'middle'
        ok = (pi - pc <= 0.2) if band == 'high' else (pi - pc >= 0.3) if band == 'low' else None
        pred[p] = dict(control_rate=round(pc, 2), injection_rate=round(pi, 2), diff=round(pi - pc, 2), band=band, prediction_holds=ok)
    res['prediction'] = pred
    res['secondary']['cmh_resnet18_vs_load_only'] = dict(tables=t_inj_load, **cmh(t_inj_load), exact_stratified_p=exact_stratified(t_inj_load))
    json.dump(res, open(outp, 'w'), indent=1)
    print(json.dumps({'primary': res['primary'], 'secondary': res['secondary'], 'sensitivity_independent_pairs': res['sensitivity_independent_pairs'], 'prediction': res['prediction'],
                      'per_pair': {p: {'merged': {a: f"{v['arms'][a]['merged']}/{v['arms'][a]['n']}" for a in ARMS},
                                       'src_inj': v['arms']['resnet18']['src'], 'tests': v['tests']} for p, v in res['pairs'].items()}}, indent=1))


if __name__ == '__main__':
    main()

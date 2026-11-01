#!/usr/bin/env python3
"""POST HOC (not pre-registered): classify every accepted merge in Parts B, C, E (and D, for reference) as
cross-session (matched KF in session 1, current KF in session 2), fragment (both KFs in session 2) or
s1-fragment (both in session 1). Reads run dirs only; changes nothing in them.

Usage: posthoc_frag.py <out_json>

Session of a KF:
  - 'stamp' method (Parts C, D, E): KF stamp from kf_log.csv, inside session 1's or session 2's stamp interval
    (+-1 s; session_bounds from pv2_summary.json). Interval membership, not 'stamp <= session-1 end' (the rule of the
    Part D breakdown), because MH_04 -> MH_02 runs backwards in time; for forward pairs the two rules agree.
  - 'id' method (Part B, no kf_log.csv): session 1 if KF id < the first session-2 KF id, which is the
    'First KF:<id>' line that follows '[SESSION] ChangeDataset requested' in mono.log. KF ids only increase.
Both methods are applied wherever both are possible, and their agreement is reported.
Merges are the '[PROP] accepted list=merge' lines of mono.log; their number is checked against 'Merge finished'.
"""
import sys, os, re, json, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from analyze_xmap2 import cmh, exact_stratified, kf_stamps
from scipy.stats import fisher_exact

RUNS = os.path.expanduser('~/mono-slam-cnn-loop-closure/results/proposal_v2/runs')
ARMS = ['none', 'load_only', 'resnet18']
PARTS = {'B': ['X_MH0204'], 'C': ['X2_MH0305', 'X2_MH0402'], 'E': ['XE_MH0205', 'XE_MH0104', 'XE_MH0105'], 'D': ['XD_V0103']}
ACC = re.compile(r'^\[PROP\] accepted list=merge src=(\S+) .*matchedKF=(\d+) curKF=(\d+)')


def first_s2_id(log):
    seen = False
    for l in log:
        if '[SESSION] ChangeDataset requested' in l: seen = True
        elif seen:
            m = re.match(r'^First KF:(\d+);', l)
            if m: return int(m[1])
    return None


def side_id(k, f2): return None if f2 is None else ('s1' if k < f2 else 's2')


def side_stamp(k, st, b):
    """Interval membership (+-1 s), so the reversed-time pair MH_04 -> MH_02 is handled."""
    if k not in st or not b or len(b) != 2: return None
    t = st[k]; i1 = b[0][0] - 1 <= t <= b[0][1] + 1; i2 = b[1][0] - 1 <= t <= b[1][1] + 1
    return 's1' if i1 and not i2 else ('s2' if i2 and not i1 else None)


def cls(a, b):
    return {('s1', 's2'): 'cross', ('s2', 's2'): 'fragment', ('s1', 's1'): 's1_fragment'}.get((a, b), 'other') if a and b else None


def run(r):
    log = open(f'{r}/mono.log', errors='replace').read().splitlines()
    f2 = first_s2_id(log)
    st = kf_stamps(r) if os.path.exists(f'{r}/kf_log.csv') else {}
    b = json.load(open(f'{r}/pv2_summary.json')).get('session_bounds') if os.path.exists(f'{r}/pv2_summary.json') else None
    merges = []
    for l in log:
        m = ACC.match(l)
        if not m: continue
        src, mk, ck = m[1], int(m[2]), int(m[3])
        by_id = cls(side_id(mk, f2), side_id(ck, f2))
        by_st = cls(side_stamp(mk, st, b), side_stamp(ck, st, b)) if st else None
        merges.append(dict(src=src, matchedKF=mk, curKF=ck, by_id=by_id, by_stamp=by_st, cls=by_st if st else by_id))
    return dict(first_s2_kf=f2, method='stamp' if st else 'id', n_merge_finished=sum('Merge finished' in l for l in log), merges=merges)


def main():
    out = {'note': 'POST HOC, not pre-registered', 'parts': {}}
    for part, tags in PARTS.items():
        P = out['parts'][part] = {'pairs': {}}
        t_ctrl, t_load = [], []
        for tag in tags:
            Q = P['pairs'][tag] = {'arms': {}, 'runs': {}}
            for a in ARMS:
                rs = sorted(glob.glob(f'{RUNS}/{tag}_r*_{a}'), key=lambda p: int(re.search(r'_r(\d+)_', p)[1]))
                rows = []
                for r in rs:
                    R = run(r); Q['runs'][os.path.basename(r)] = R
                    c = [m['cls'] for m in R['merges']]
                    rows.append(dict(any_merge=len(c) > 0, cross=('cross' in c)))
                ms = [m for r in rs for m in Q['runs'][os.path.basename(r)]['merges']]
                Q['arms'][a] = dict(n=len(rows), runs_any_merge=sum(x['any_merge'] for x in rows), runs_cross=sum(x['cross'] for x in rows),
                                    merges={f'{k}_{s}': sum(1 for m in ms if m['cls'] == k and m['src'] == s)
                                            for k in ('cross', 'fragment', 's1_fragment', 'other', None) for s in ('ext', 'dbow2')})
            A = Q['arms']
            tab = lambda b: [[A['resnet18']['runs_cross'], A['resnet18']['n'] - A['resnet18']['runs_cross']], [A[b]['runs_cross'], A[b]['n'] - A[b]['runs_cross']]]
            Q['fisher_cross_resnet18_vs_none'] = dict(table=tab('none'), p=round(float(fisher_exact(tab('none'))[1]), 4))
            Q['fisher_cross_resnet18_vs_load_only'] = dict(table=tab('load_only'), p=round(float(fisher_exact(tab('load_only'))[1]), 4))
            t_ctrl.append(tab('none')); t_load.append(tab('load_only'))
        P['cmh_cross_resnet18_vs_none'] = dict(tables=t_ctrl, **cmh(t_ctrl), exact_stratified_p=exact_stratified(t_ctrl))
        P['cmh_cross_resnet18_vs_load_only'] = dict(tables=t_load, **cmh(t_load), exact_stratified_p=exact_stratified(t_load))
    # checks
    allr = [R for P in out['parts'].values() for Q in P['pairs'].values() for R in Q['runs'].values()]
    both = [m for R in allr for m in R['merges'] if m['by_stamp'] is not None]
    out['checks'] = dict(
        runs=len(allr),
        accepted_vs_merge_finished_mismatch=[n for P in out['parts'].values() for Q in P['pairs'].values() for n, R in Q['runs'].items() if len(R['merges']) != R['n_merge_finished']],
        runs_without_first_s2_kf=[n for P in out['parts'].values() for Q in P['pairs'].values() for n, R in Q['runs'].items() if R['first_s2_kf'] is None],
        id_vs_stamp_merges_compared=len(both), id_vs_stamp_disagree=sum(1 for m in both if m['by_id'] != m['by_stamp']),
        unclassified=sum(1 for R in allr for m in R['merges'] if m['cls'] in (None, 'other')))
    json.dump(out, open(sys.argv[1], 'w'), indent=1)
    print(json.dumps(out['checks'], indent=1))
    for part, P in out['parts'].items():
        print(f'\n=== Part {part}  CMH cross vs none: {({k: v for k, v in P["cmh_cross_resnet18_vs_none"].items() if k != "tables"})}  vs load: {({k: v for k, v in P["cmh_cross_resnet18_vs_load_only"].items() if k != "tables"})}')
        for tag, Q in P['pairs'].items():
            print(tag, {a: (f"any {v['runs_any_merge']}/{v['n']}", f"cross {v['runs_cross']}/{v['n']}", {k: c for k, c in v['merges'].items() if c}) for a, v in Q['arms'].items()},
                  'fisher', Q['fisher_cross_resnet18_vs_none'], Q['fisher_cross_resnet18_vs_load_only'])


if __name__ == '__main__':
    main()

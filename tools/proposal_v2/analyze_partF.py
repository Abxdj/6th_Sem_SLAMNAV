#!/usr/bin/env python3
"""PREREG Part F analysis: >= 1 cross-session merge per run, injection vs control, Fisher exact (two-sided).

Usage: analyze_partF.py <pairs.json> <out_json> [--max-block K]   (K: use runs r1..rK only, for a batch stopped early)

Classification is tools/proposal_v2/posthoc_frag.py's run(), unchanged, frozen at md5 610bdb7a... (checked at start):
interval (stamp) method from kf_log.csv + pv2_summary.json session_bounds; the id method is reported as a check.
A run is a cross-session run if any accepted merge in its mono.log is 'cross'. mono.log is read to its end, so a run
that crashed is scored on the merges logged before the crash. Unclassified merges never count as cross-session.
pv2_summary.json (session_bounds) is regenerated first with analyze_pv2.py, as analyze_xmap2.py does.
"""
import sys, os, re, json, glob, hashlib, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
FRAG_MD5 = '610bdb7afcade9ba4d54b8db36e8d92a'
md5 = hashlib.md5(open(f'{HERE}/posthoc_frag.py', 'rb').read()).hexdigest()
if md5 != FRAG_MD5: sys.exit(f'posthoc_frag.py md5 {md5} != frozen {FRAG_MD5}')
from posthoc_frag import run
from scipy.stats import fisher_exact

REPO = os.path.expanduser('~/mono-slam-cnn-loop-closure')
ARMS = ['none', 'load_only', 'resnet18']


def main():
    pairs = json.load(open(sys.argv[1])); outp = sys.argv[2]
    K = int(sys.argv[sys.argv.index('--max-block') + 1]) if '--max-block' in sys.argv else 10 ** 9
    res = {'posthoc_frag_md5': md5, 'max_block': (K if K < 10 ** 9 else None), 'pairs': {}}
    for pair, cfg in pairs.items():
        runs = {a: sorted(glob.glob(f"{REPO}/results/proposal_v2/runs/{cfg['tag']}_r*_{a}"), key=lambda p: int(re.search(r'_r(\d+)_', p)[1])) for a in ARMS}
        runs = {a: [r for r in v if int(re.search(r'_r(\d+)_', r)[1]) <= K] for a, v in runs.items()}
        allruns = [r for a in ARMS for r in runs[a]]
        if not allruns: continue
        subprocess.run([sys.executable, f'{HERE}/analyze_pv2.py', os.path.expanduser(cfg['gt'])] + allruns, check=True, stdout=subprocess.DEVNULL)
        P = res['pairs'][pair] = {'arms': {}, 'runs': {}}
        for a in ARMS:
            rows = []
            for r in runs[a]:
                R = run(r); name = os.path.basename(r)
                meta = dict(l.strip().split('=', 1) for l in open(f'{r}/meta.txt') if '=' in l)
                R.update(cross=any(m['cls'] == 'cross' for m in R['merges']), mono_exit=meta.get('mono_exit'),
                         traj_allmaps=os.path.exists(f'{r}/KeyFrameTrajectory_allmaps.txt') and os.path.getsize(f'{r}/KeyFrameTrajectory_allmaps.txt') > 0)
                P['runs'][name] = R; rows.append(R)
            ms = [m for R in rows for m in R['merges']]
            P['arms'][a] = dict(n=len(rows), runs_cross=sum(R['cross'] for R in rows), runs_any_merge=sum(1 for R in rows if R['merges']),
                                merges={c: sum(1 for m in ms if m['cls'] == c) for c in ('cross', 'fragment', 's1_fragment', 'other', None)},
                                cross_by_src={s: sum(1 for m in ms if m['cls'] == 'cross' and m['src'] == s) for s in ('ext', 'dbow2')},
                                runs_no_allmaps_traj=sum(1 for R in rows if not R['traj_allmaps']))
        A = P['arms']
        tab = lambda b: [[A['resnet18']['runs_cross'], A['resnet18']['n'] - A['resnet18']['runs_cross']], [A[b]['runs_cross'], A[b]['n'] - A[b]['runs_cross']]]
        P['primary_fisher_resnet18_vs_none'] = dict(table=tab('none'), p=float(fisher_exact(tab('none'))[1]))
        P['secondary_fisher_resnet18_vs_load_only'] = dict(table=tab('load_only'), p=float(fisher_exact(tab('load_only'))[1]))
        ri, rc = A['resnet18']['runs_cross'] / max(A['resnet18']['n'], 1), A['none']['runs_cross'] / max(A['none']['n'], 1)
        P['prediction'] = dict(injection_rate=round(ri, 2), control_rate=round(rc, 2), diff=round(ri - rc, 2), rule='diff >= 0.3', holds=bool(ri - rc >= 0.3 - 1e-9))
        both = [m for R in P['runs'].values() for m in R['merges'] if m['by_stamp'] is not None]
        P['checks'] = dict(merge_finished_mismatch=[n for n, R in P['runs'].items() if len(R['merges']) != R['n_merge_finished']],
                           runs_without_first_s2_kf=[n for n, R in P['runs'].items() if R['first_s2_kf'] is None],
                           id_vs_stamp_compared=len(both), id_vs_stamp_disagree=sum(1 for m in both if m['by_id'] != m['by_stamp']),
                           unclassified=sum(1 for R in P['runs'].values() for m in R['merges'] if m['cls'] in (None, 'other')),
                           crashed_runs={n: R['mono_exit'] for n, R in P['runs'].items() if not R['traj_allmaps']})
    json.dump(res, open(outp, 'w'), indent=1)
    print(json.dumps({p: {k: v for k, v in P.items() if k != 'runs'} for p, P in res['pairs'].items()}, indent=1))


if __name__ == '__main__':
    main()

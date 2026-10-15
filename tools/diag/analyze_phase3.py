#!/usr/bin/env python3
"""Aggregate Phase 3 segment runs. Usage: analyze_phase3.py <segment> <out.csv> [event_times...]
Per run: loss episodes (onset bag times), maps created after the initial one, merges, loops,
keyframes, Mono drop %, CPU of Mono / descriptor-or-load process, GPU util, exit code.
For each reference event time given, records whether a loss onset fell within +-8 s."""
import sys, glob, os, re, json
import numpy as np, pandas as pd

SEG, OUT = sys.argv[1], sys.argv[2]
REF = [float(x) for x in sys.argv[3:]]
rows = []
for d in sorted(glob.glob(f'results/gazebo_ab/diag_{SEG}_*_r*_*')):
    name = os.path.basename(d)
    m = re.match(rf'diag_{SEG}_(\w+?)_r(\d+)_', name)
    arm, rep = m.group(1), int(m.group(2))
    meta = dict(l.strip().split('=', 1) for l in open(f'{d}/meta.txt') if '=' in l)
    log = open(f'{d}/mono.log', errors='replace').read()
    E = pd.read_csv(f'{d}/events.csv')
    lost = np.sort(E.loc[E.type == 'lost', 'bag_t'].dropna().values)
    onsets = [t for i, t in enumerate(lost) if i == 0 or t - lost[i - 1] > 3]
    r = dict(arm=arm, rep=rep, exit=meta.get('mono_exit'),
             new_maps=log.count('Creation of new map with id') - 1,
             merges=log.count('Merge finished'), loops=log.count('*Loop detected'),
             fail_lines=log.count('Fail to track local map'), sophus=log.count('Sophus ensure'),
             loss_onsets=';'.join(f'{t:.0f}' for t in onsets))
    for t in REF:
        r[f'loss@{t:.0f}'] = int(any(abs(o - t) < 8 for o in onsets))
    s = json.load(open(f'{d}/summary.json')) if os.path.exists(f'{d}/summary.json') else {}
    r['kf_total'] = s.get('kf_total'); r['drop_pct'] = s.get('mono_drop_pct')
    c = s.get('cpu_mean', {})
    r['cpu_mono'] = c.get('Mono'); r['cpu_desc'] = c.get('desc', c.get('load')); r['gpu_util'] = c.get('gpu_util_mean')
    rows.append(r)
D = pd.DataFrame(rows).sort_values(['arm', 'rep'])
D.to_csv(OUT, index=False)
pd.set_option('display.width', 250)
print(D.to_string(index=False))
num = ['new_maps', 'merges', 'loops', 'fail_lines', 'kf_total', 'drop_pct', 'cpu_mono', 'cpu_desc', 'gpu_util'] + [f'loss@{t:.0f}' for t in REF]
print('\nper-arm mean (n):')
print(D.groupby('arm')[num].mean().round(2).assign(n=D.groupby('arm').size()).to_string())

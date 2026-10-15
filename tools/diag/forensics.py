#!/usr/bin/env python3
"""Phase 4 forensics over existing results/gazebo_ab runs (read-only; writes nothing into them).
For each run: map segments from mono.log, KF survival in the final map (culling estimate),
proposal fate (injected / matched KF in another, unmerged map / unexplained), Sophus context.
Usage: forensics.py <out_json> <run_dir>..."""
import sys, re, os, json, numpy as np

def kf_ids_from_desc(d):
    ids = []
    p = f'{d}/desc.log'
    if os.path.exists(p):
        for l in open(p, errors='replace'):
            m = re.search(r'\[(\d+\.\d+)\]: (?:LOOP CLOSURE: )?KF (\d+)', l)
            if m: ids.append((float(m.group(1)), int(m.group(2))))
    return sorted(ids)

out = {}
for d in sys.argv[2:]:
    name = os.path.basename(d.rstrip('/'))
    lines = open(f'{d}/mono.log', errors='replace').read().split('\n')
    seq = []   # ordered events
    for i, l in enumerate(lines):
        m = re.search(r'Creation of new map with last KF id: (\d+)', l)
        if m: seq.append(('map', int(m.group(1)), i))
        if 'Merge finished' in l: seq.append(('merge', None, i))
        m = re.search(r'injected external candidate KF (\d+) for current KF (\d+)', l)
        if m: seq.append(('inj', (int(m.group(1)), int(m.group(2))), i))
    inits = [s[1] for s in seq if s[0] == 'map']
    r = {'map_init_kf': inits, 'merges': sum(s[0] == 'merge' for s in seq)}
    # KF survival in the final map: saved KFs vs ids allocated since the final map's init
    desc = kf_ids_from_desc(d)
    maxid = max([k for _, k in desc], default=None)
    if os.path.exists(f'{d}/KeyFrameTrajectory.txt') and maxid and inits:
        n = sum(1 for _ in open(f'{d}/KeyFrameTrajectory.txt'))
        r['final_map_saved_kfs'] = n
        r['final_map_ids_allocated'] = maxid + 1 - inits[-1]
    # proposals
    props = []
    for l in open(f'{d}/desc.log', errors='replace') if os.path.exists(f'{d}/desc.log') else []:
        m = re.search(r'LOOP CLOSURE: KF (\d+) matches KF (\d+)', l)
        if m: props.append((int(m.group(1)), int(m.group(2))))
    injected = {s[1][0] for s in seq if s[0] == 'inj'}
    fate = {'injected': 0, 'other_map': 0, 'unexplained': 0}
    gaps = []
    for c, mk in props:
        gaps.append(c - mk)
        cur_init = max([x for x in inits if x <= c], default=0)
        if mk in injected: fate['injected'] += 1
        elif mk < cur_init: fate['other_map'] += 1
        else: fate['unexplained'] += 1
    if props:
        g = np.array(gaps)
        r['proposals'] = len(props); r['fate'] = fate
        r['gap_kf'] = {'median': int(np.median(g)), 'n_100_220': int(((g >= 100) & (g <= 220)).sum()), 'n_gt_500': int((g > 500).sum())}
    # Sophus context: last 6 non-abort lines before the crash
    for i, l in enumerate(lines):
        if 'Sophus ensure failed' in l:
            ctx = [x for x in lines[max(0, i-60):i] if 'ABORT-NEAR' not in x and 'neighbours' not in x and x.strip()]
            r['sophus_context'] = ctx[-6:]
    r['fail_track_local_map'] = sum('Fail to track local map' in l for l in lines)
    out[name] = r
json.dump(out, open(sys.argv[1], 'w'), indent=1)
for k, v in out.items():
    print(k, {x: v.get(x) for x in ('map_init_kf', 'merges', 'final_map_saved_kfs', 'final_map_ids_allocated', 'proposals', 'fate', 'gap_kf', 'fail_track_local_map')})
    if 'sophus_context' in v: print('   SOPHUS ctx:', v['sophus_context'])

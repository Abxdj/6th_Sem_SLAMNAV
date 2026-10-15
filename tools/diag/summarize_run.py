#!/usr/bin/env python3
"""Summarise one monitored run folder. Usage: summarize_run.py <run_dir> [...]

Prints counts per event type, keyframes per map, Mono frame drops (from /statistics),
mean CPU per process and GPU use. Writes summary.json, timeline.png, trajectory.png.
Works on unmonitored (older) runs too, from mono.log alone, without bag times.
"""
import sys, os, re, json, csv
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

TYPES = ['new_map', 'merge', 'loop_detected', 'correction', 'injected', 'abort_near',
         'proposal', 'sophus_crash', 'lost', 'reset_map']
COLORS = {'new_map': 'tab:red', 'merge': 'tab:green', 'loop_detected': 'tab:blue',
          'injected': 'tab:purple', 'sophus_crash': 'black', 'lost': 'tab:orange', 'proposal': 'tab:gray'}


def read_csv(p):
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def summarize(run):
    out = {'run': os.path.basename(run.rstrip('/'))}
    meta = {}
    if os.path.exists(f'{run}/meta.txt'):
        for l in open(f'{run}/meta.txt'):
            if '=' in l:
                k, v = l.strip().split('=', 1); meta[k] = v
    out['meta'] = {k: meta.get(k) for k in ('mode', 'rate', 'start', 'duration', 'yaml', 'relay', 'mono_exit')}
    log = open(f'{run}/mono.log', errors='replace').read() if os.path.exists(f'{run}/mono.log') else ''
    out['counts_log'] = {
        'new_map': len(re.findall(r'Creation of new map with id', log)),
        'merge': len(re.findall(r'Merge finished', log)),
        'loop_detected': len(re.findall(r'\*Loop detected', log)),
        'fail_track_local_map': len(re.findall(r'Fail to track local map', log)),
        'injected': len(re.findall(r'injected external candidate', log)),
        'abort_near': len(re.findall(r'ABORT-NEAR', log)),
        'sophus_crash': len(re.findall(r'Sophus ensure failed', log)),
        'final_stats_printed': int('[FINAL STATS]' in log),
    }
    kfs = [int(x) for x in re.findall(r'Creation of new map with last KF id: (\d+)', log)]
    ev = read_csv(f'{run}/events.csv')
    kf = read_csv(f'{run}/keyframes.csv')
    ids = [int(r['kf_id']) for r in kf]
    if ids:
        kfs_end = max(ids) + 1
        bounds = kfs + [kfs_end]
        out['kfs_per_map'] = [b - a for a, b in zip(bounds[:-1], bounds[1:])]
        out['kf_total'] = len(ids)
    ts = read_csv(f'{run}/topicstats.csv')
    mono = [r for r in ts if r['subscriber'] == '/Mono' and r['topic'] == '/camera/image_raw']
    if mono:
        dl = sum(int(r['delivered']) for r in mono); dr = sum(int(r['dropped']) for r in mono)
        out['mono_image_delivered'] = dl; out['mono_image_dropped'] = dr
        out['mono_drop_pct'] = round(100.0 * dr / max(1, dl + dr), 2)
    res = read_csv(f'{run}/resources.csv')
    if res:
        out['cpu_mean'] = {}
        for proc in sorted({r['proc'] for r in res}):
            v = [float(r['cpu_pct']) for r in res if r['proc'] == proc]
            m = [float(r['rss_mb']) for r in res if r['proc'] == proc]
            key = 'gpu_util_mean' if proc == 'GPU' else proc
            out['cpu_mean'][key] = round(float(np.mean(v)), 1)
            if proc == 'GPU':
                out['gpu_mem_max_mb'] = max(m)
    if ev:
        out['counts_events'] = {t: sum(1 for r in ev if r['type'] == t) for t in TYPES}
        fig, ax = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
        for i, t in enumerate(['new_map', 'merge', 'loop_detected', 'injected', 'sophus_crash']):
            x = [float(r['bag_t']) for r in ev if r['type'] == t]
            ax[0].scatter(x, [i] * len(x), c=COLORS.get(t, 'k'), s=25, marker='|' if t != 'new_map' else 'v')
        ax[0].set_yticks(range(5)); ax[0].set_yticklabels(['new_map', 'merge', 'loop', 'injected', 'sophus'])
        x = [float(r['bag_t']) for r in ev if r['type'] == 'lost']
        if x:
            ax[1].hist(x, bins=np.arange(0, max(x) + 10, 10), color='tab:orange')
        ax[1].set_ylabel('"Fail to track"\nper 10 s')
        if kf:
            x = np.array([float(r['bag_t']) for r in kf])
            ax[2].hist(x, bins=np.arange(0, max(x) + 10, 10), color='tab:blue')
        ax[2].set_ylabel('keyframes\nper 10 s'); ax[2].set_xlabel('bag time (s)')
        ax[0].set_title(out['run'])
        fig.tight_layout(); fig.savefig(f'{run}/timeline.png', dpi=90); plt.close(fig)
    if os.path.exists(f'{run}/KeyFrameTrajectory.txt'):
        T = np.loadtxt(f'{run}/KeyFrameTrajectory.txt', ndmin=2)
        if len(T) > 1:
            fig, ax = plt.subplots(figsize=(6, 6))
            sc = ax.scatter(T[:, 1], T[:, 3], c=T[:, 0] - T[0, 0], s=4, cmap='viridis')
            ax.set_aspect('equal'); ax.set_xlabel('x'); ax.set_ylabel('z')
            ax.set_title(f"{out['run']}: final map only, {len(T)} KFs")
            plt.colorbar(sc, label='t since first KF (s)')
            fig.tight_layout(); fig.savefig(f'{run}/trajectory.png', dpi=90); plt.close(fig)
        out['traj_kfs_final_map'] = len(T)
    json.dump(out, open(f'{run}/summary.json', 'w'), indent=1)
    return out


if __name__ == '__main__':
    for r in sys.argv[1:]:
        print(json.dumps(summarize(r)))

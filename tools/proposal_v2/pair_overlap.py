#!/usr/bin/env python3
"""GT overlap of a session pair (session 1 = map, session 2 = query), for choosing test pairs.

Usage: pair_overlap.py <gt1_tum> <gt2_tum> [radius_m=2.0] [angle_deg=45] [--json]
overlap   = fraction of session-2 GT poses (10 Hz) with some session-1 pose < radius AND < angle (PREREG Part A definition).
regions   = maximal runs of overlapping session-2 time, joining gaps < 2 s, keeping runs >= 2 s.
places    = regions whose mean session-2 position is > 3 m from every earlier region's (distinct revisit places).
Each region: start/end s into session 2, duration, mean position.
"""
import sys, json
import numpy as np


def load(p):
    a = np.loadtxt(p)
    t = a[:, 0] - a[0, 0]
    keep = np.r_[0, np.where(np.diff(np.floor(t * 10)) > 0)[0] + 1]     # ~10 Hz
    return t[keep], a[keep, 1:4], a[keep, 4:8]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    g1, g2 = args[:2]; R = float(args[2]) if len(args) > 2 else 2.0; A = float(args[3]) if len(args) > 3 else 45.0
    _, P1, Q1 = load(g1); t2, P2, Q2 = load(g2)
    ok = np.zeros(len(t2), bool)
    for i in range(0, len(t2), 500):
        d = np.linalg.norm(P2[i:i + 500, None] - P1[None], axis=2)
        ang = np.degrees(2 * np.arccos(np.clip(np.abs(Q2[i:i + 500] @ Q1.T), 0, 1)))
        ok[i:i + 500] = ((d < R) & (ang < A)).any(1)
    regs, s = [], None
    for i, o in enumerate(ok):
        if o and s is None: s = i
        if s is not None and (not o or i == len(ok) - 1):
            e = i if o else i - 1
            if regs and t2[s] - regs[-1][1] < 2.0: regs[-1][1] = t2[e]; regs[-1][2].extend(range(s, e + 1))
            else: regs.append([t2[s], t2[e], list(range(s, e + 1))])
            s = None
    regs = [r for r in regs if r[1] - r[0] >= 2.0]
    out = {'gt1': g1, 'gt2': g2, 'radius_m': R, 'angle_deg': A, 'session2_s': round(float(t2[-1]), 1),
           'overlap': round(float(ok.mean()), 3), 'overlap_after_10s': round(float(ok[t2 >= 10].mean()), 3), 'regions': []}
    centres = []
    for a, b, idx in regs:
        c = P2[idx].mean(0)
        new = all(np.linalg.norm(c - x) > 3.0 for x in centres)
        if new: centres.append(c)
        out['regions'].append({'start_s': round(float(a), 1), 'end_s': round(float(b), 1), 'dur_s': round(float(b - a), 1),
                               'mean_pos': [round(float(v), 2) for v in c], 'new_place': bool(new)})
    out['n_regions'] = len(regs); out['n_places'] = len(centres)
    print(json.dumps(out, indent=None if '--json' in sys.argv else 1))


if __name__ == '__main__':
    main()

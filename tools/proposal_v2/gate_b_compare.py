#!/usr/bin/env python3
"""Descriptor ablation on fair Gate B: ResNet18 / DINO ViT-S/8 / EfficientNet-B0 / DBoW2 raw top-1 on the same keyframes.

Usage: gate_b_compare.py <out_json> <gt1> <gt2> <seq1_dir> <seq2_dir> <run_dir> [<run_dir> ...]
Needs, per run: descs.npz (live ResNet18), descs_dino.npz, descs_effnet.npz (offline_descs.py), dbow_scores.bin (gate_b.py).
Pooled R@P90, R@P95, AP per method and radius, plus a run-level bootstrap (2000 resamples of runs with replacement)
of the difference in R@P90 and AP for every method pair: 95% interval and P(diff <= 0).
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_b

FILES = {'resnet18': 'descs.npz', 'dino': 'descs_dino.npz', 'effnet': 'descs_effnet.npz'}


def main():
    outp, g1, g2, q1, q2 = sys.argv[1:6]; runs = sys.argv[6:]
    G = [gate_b.load_tum(g1), gate_b.load_tum(g2)]; I = [gate_b.images(q1), gate_b.images(q2)]
    os.environ['DBOW_QUERY'] = '/bin/false'          # DBoW2 scores must come from the cache
    per = {}                                          # per[run][method][r] = (scores, correct, npos)
    for run in runs:
        per[run] = {}
        for m, f in FILES.items():
            gate_b.LEARNED = f
            res = gate_b.per_run(run, G, I)['res']
            per[run][m] = {r: (res[r]['learned'][0], res[r]['learned'][1].astype(float), res[r]['npos']) for r in gate_b.RADII}
            per[run]['dbow2'] = {r: (res[r]['dbow2'][0], res[r]['dbow2'][1].astype(float), res[r]['npos']) for r in gate_b.RADII}
    methods = list(FILES) + ['dbow2']

    def pooled(sel, m, r):
        sc = np.concatenate([per[x][m][r][0] for x in sel]); co = np.concatenate([per[x][m][r][1] for x in sel])
        st = gate_b.pr(sc, co, sum(per[x][m][r][2] for x in sel))[0]
        return st['R@P90'], st['AP']

    rng = np.random.default_rng(0); out = {'runs': [os.path.basename(r) for r in runs], 'pooled': {}, 'bootstrap': {}}
    for r in gate_b.RADII:
        key = f'{r:g}m'
        out['pooled'][key] = {}
        for m in methods:
            sc = np.concatenate([per[x][m][r][0] for x in runs]); co = np.concatenate([per[x][m][r][1] for x in runs])
            out['pooled'][key][m] = gate_b.pr(sc, co, sum(per[x][m][r][2] for x in runs))[0]
        B = [[pooled(list(rng.choice(runs, len(runs))), m, r) for m in methods] for _ in range(2000)]
        B = np.array(B)                                # [boot, method, (R@P90, AP)]
        out['bootstrap'][key] = {}
        for i, a in enumerate(methods):
            for j, b in enumerate(methods):
                if j <= i: continue
                d = B[:, i] - B[:, j]
                out['bootstrap'][key][f'{a}-{b}'] = {
                    'R@P90_diff_ci95': [round(float(v), 3) for v in np.percentile(d[:, 0], [2.5, 97.5])],
                    'R@P90_P(diff<=0)': round(float((d[:, 0] <= 0).mean()), 3),
                    'AP_diff_ci95': [round(float(v), 3) for v in np.percentile(d[:, 1], [2.5, 97.5])],
                    'AP_P(diff<=0)': round(float((d[:, 1] <= 0).mean()), 3)}
    json.dump(out, open(outp, 'w'), indent=1)
    for key in out['pooled']:
        print(key, {m: (v['R@P90'], v['R@P95'], v['AP']) for m, v in out['pooled'][key].items()})
        for k, v in out['bootstrap'][key].items(): print('  ', k, v)


if __name__ == '__main__':
    main()

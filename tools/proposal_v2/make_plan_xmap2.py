#!/usr/bin/env python3
"""Write the interleaved run plan for the multi-pair cross-map test (PREREG Part C).

Usage: make_plan_xmap2.py <pairs.json> <n_blocks> <out_plan>
Block k (1..n) runs every pair in the order listed; within a pair the three arms follow a rotation:
k % 3 == 1: none, load_only, resnet18 ; k % 3 == 2: load_only, resnet18, none ; k % 3 == 0: resnet18, none, load_only.
So the arms are balanced over run order. Every pair gets block k before any pair gets block k+1, so stopping early
leaves all pairs with equal n.
Line format (run_batch.sh): <mode> <tag>_r<k> <speed> <seq1> <seq2>
"""
import sys, json

pairs = json.load(open(sys.argv[1])); n = int(sys.argv[2])
ROT = {1: ['none', 'load_only', 'resnet18'], 2: ['load_only', 'resnet18', 'none'], 0: ['resnet18', 'none', 'load_only']}
with open(sys.argv[3], 'w') as f:
    for k in range(1, n + 1):
        for p, c in pairs.items():
            for arm in ROT[k % 3]:
                f.write(f"{arm} {c['tag']}_r{k} 1.0 {c['seq1']} {c['seq2']}\n")

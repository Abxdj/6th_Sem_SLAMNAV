#!/usr/bin/env python3
"""
Converts EuRoC state_groundtruth_estimate0/data.csv to TUM trajectory format
for evaluation with evo.

EuRoC:  timestamp[ns], px, py, pz, qw, qx, qy, qz, (+ velocity/bias columns)
TUM:    timestamp[s]   px py pz qx qy qz qw

Usage: python3 euroc_gt_to_tum.py <sequence_path> <output.txt>
"""
import sys
import os

def main():
    if len(sys.argv) < 3:
        print("Usage: euroc_gt_to_tum.py <sequence_path> <output.txt>")
        sys.exit(1)

    seq_path = os.path.expanduser(sys.argv[1])
    out_path = os.path.expanduser(sys.argv[2])
    csv_path = os.path.join(seq_path, "mav0", "state_groundtruth_estimate0", "data.csv")

    n = 0
    with open(csv_path) as fin, open(out_path, 'w') as fout:
        for line in fin:
            if line.startswith('#') or not line.strip():
                continue
            p = line.strip().split(',')
            ts = int(p[0]) / 1e9
            px, py, pz = p[1], p[2], p[3]
            qw, qx, qy, qz = p[4], p[5], p[6], p[7]
            fout.write(f"{ts:.9f} {px} {py} {pz} {qx} {qy} {qz} {qw}\n")
            n += 1

    print(f"Wrote {n} poses to {out_path}")

if __name__ == "__main__":
    main()

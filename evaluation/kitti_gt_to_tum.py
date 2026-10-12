#!/usr/bin/env python3
"""
Converts KITTI odometry ground truth to TUM format for evo.

KITTI: poses/NN.txt has 12 floats per line = 3x4 transform (row-major),
       one line per frame, no timestamps. Times come from sequences/NN/times.txt.
TUM:   timestamp tx ty tz qx qy qz qw

Usage: python3 kitti_gt_to_tum.py <seq_path> <poses_file> <output.txt>
"""
import sys, os
import numpy as np

def rot_to_quat(R):
    """Rotation matrix to quaternion (x, y, z, w)."""
    tr = R[0,0] + R[1,1] + R[2,2]
    if tr > 0:
        S = np.sqrt(tr + 1.0) * 2
        qw = 0.25 * S
        qx = (R[2,1] - R[1,2]) / S
        qy = (R[0,2] - R[2,0]) / S
        qz = (R[1,0] - R[0,1]) / S
    elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
        S = np.sqrt(1.0 + R[0,0] - R[1,1] - R[2,2]) * 2
        qw = (R[2,1] - R[1,2]) / S
        qx = 0.25 * S
        qy = (R[0,1] + R[1,0]) / S
        qz = (R[0,2] + R[2,0]) / S
    elif R[1,1] > R[2,2]:
        S = np.sqrt(1.0 + R[1,1] - R[0,0] - R[2,2]) * 2
        qw = (R[0,2] - R[2,0]) / S
        qx = (R[0,1] + R[1,0]) / S
        qy = 0.25 * S
        qz = (R[1,2] + R[2,1]) / S
    else:
        S = np.sqrt(1.0 + R[2,2] - R[0,0] - R[1,1]) * 2
        qw = (R[1,0] - R[0,1]) / S
        qx = (R[0,2] + R[2,0]) / S
        qy = (R[1,2] + R[2,1]) / S
        qz = 0.25 * S
    return qx, qy, qz, qw

def main():
    if len(sys.argv) < 4:
        print("Usage: kitti_gt_to_tum.py <seq_path> <poses_file> <output.txt>")
        sys.exit(1)

    seq_path = os.path.expanduser(sys.argv[1])
    poses_file = os.path.expanduser(sys.argv[2])
    out_path = os.path.expanduser(sys.argv[3])

    times = []
    with open(os.path.join(seq_path, "times.txt")) as f:
        for line in f:
            if line.strip():
                times.append(float(line.strip()))

    n = 0
    with open(poses_file) as fin, open(out_path, 'w') as fout:
        for i, line in enumerate(fin):
            if not line.strip():
                continue
            if i >= len(times):
                break
            v = [float(x) for x in line.strip().split()]
            T = np.array(v).reshape(3, 4)
            R = T[:, :3]
            t = T[:, 3]
            qx, qy, qz, qw = rot_to_quat(R)
            # match the publisher's timestamp offset
            ts = times[i] + 1e6
            fout.write(f"{ts:.9f} {t[0]:.9f} {t[1]:.9f} {t[2]:.9f} "
                       f"{qx:.9f} {qy:.9f} {qz:.9f} {qw:.9f}\n")
            n += 1

    print(f"Wrote {n} poses to {out_path}")

if __name__ == "__main__":
    main()

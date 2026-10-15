#!/bin/bash
# H8: two instrumented injection replays of segment A (needs ORB_SLAM3 on branch diag-counters)
cd ~/mono-slam-cnn-loop-closure
for k in 1 2; do
  while pgrep -x rosmaster >/dev/null; do sleep 5; done
  d=results/gazebo_ab/diag_h8_segA_r${k}_resnet18
  YAML=tools/diag/configs/fast5_1.yaml MONITOR=1 ./scripts/replay_bag.sh resnet18 bags/drive1.bag diag_h8_segA_r$k 0.5 560 240 > /dev/null 2>&1
  python3 tools/diag/summarize_run.py $d > /dev/null 2>&1
  echo "$(date +%T) diag_h8_segA_r$k exit=$(grep mono_exit $d/meta.txt | cut -d= -f2) branch=$(grep orbslam_branch $d/meta.txt | cut -d= -f2)" >> results/diagnosis/phase3_runs.log
  sleep 10
done
echo H8_DONE2 >> results/diagnosis/phase3_runs.log

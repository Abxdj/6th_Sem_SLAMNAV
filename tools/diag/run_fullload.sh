#!/bin/bash
# H5 follow-up: 5 full-length load-only replays of drive1.bag at 0.5x, default yaml (same as full_r1-10),
# monitored. Compare maps/merges with full_r*_none (control) and full_r*_resnet18_dry (dry).
cd ~/mono-slam-cnn-loop-closure
LOG=results/diagnosis/fullload_runs.log; crashes=0
for k in 1 2 3 4 5; do
  free=$(df --output=avail -BG ~ | tail -1 | tr -dc 0-9)
  [ "$free" -lt 10 ] && { echo "STOP: disk ${free}G" | tee -a $LOG; exit 1; }
  while pgrep -x rosmaster >/dev/null; do sleep 5; done
  tag=diag_fullload_r$k; d=results/gazebo_ab/${tag}_load_only
  MONITOR=1 ./scripts/replay_bag.sh load_only bags/drive1.bag $tag 0.5 > /dev/null 2>&1
  python3 tools/diag/summarize_run.py $d > /dev/null 2>&1
  ex=$(grep mono_exit $d/meta.txt | cut -d= -f2)
  echo "$(date +%T) $tag exit=$ex maps=$(grep -c 'Creation of new map with id' $d/mono.log) merges=$(grep -c 'Merge finished' $d/mono.log) loops=$(grep -c '\*Loop detected' $d/mono.log) sophus=$(grep -c 'Sophus ensure' $d/mono.log) drop_pct=$(python3 -c "import json;print(json.load(open('$d/summary.json')).get('mono_drop_pct'))" 2>/dev/null)" | tee -a $LOG
  if [ "$ex" = "134" ] || [ ! -f $d/KeyFrameTrajectory.txt ]; then crashes=$((crashes+1)); else crashes=0; fi
  [ $crashes -ge 3 ] && { echo "STOP: 3 consecutive crashes" | tee -a $LOG; exit 1; }
  sleep 20
done
echo "FULLLOAD DONE $(date +%T)" | tee -a $LOG

#!/bin/bash
# Phase 3 targeted segment replays, interleaved by repetition. Logs to results/diagnosis/phase3_runs.log
# Usage: run_phase3.sh <segment_name> <start_s> <dur_s> <arms...>
#   arm := base | fast12 | fast20 | drop2 | dry | load
cd ~/mono-slam-cnn-loop-closure
SEG=$1; START=$2; DUR=$3; shift 3; ARMS="$@"
C=tools/diag/configs; LOG=results/diagnosis/phase3_runs.log; crashes=0
for k in 1 2 3; do
  for arm in $(echo $ARMS | tr ' ' '\n' | shuf --random-source=<(yes $k)); do
    free=$(df --output=avail -BG ~ | tail -1 | tr -dc 0-9)
    [ "$free" -lt 10 ] && { echo "STOP: disk ${free}G" | tee -a $LOG; exit 1; }
    mode=none; yaml=$C/fast5_1.yaml; relay=""
    case $arm in
      fast12) yaml=$C/fast12_5.yaml ;; fast20) yaml=$C/fast20_7.yaml ;;
      drop2) yaml=$C/fast5_1_fps33.yaml; relay="1 2" ;;
      dry) mode=resnet18_dry ;; load) mode=load_only ;;
    esac
    tag=diag_${SEG}_${arm}_r$k
    while pgrep -x rosmaster >/dev/null; do sleep 5; done
    YAML=$yaml MONITOR=1 RELAY=$relay ./scripts/replay_bag.sh $mode bags/drive1.bag $tag 0.5 $START $DUR > /dev/null 2>&1
    d=results/gazebo_ab/${tag}_${mode}
    python3 tools/diag/summarize_run.py $d > /dev/null 2>&1
    ex=$(grep mono_exit $d/meta.txt | cut -d= -f2)
    echo "$(date +%T) $tag mode=$mode exit=$ex maps=$(grep -c 'Creation of new map with id' $d/mono.log) fail=$(grep -c 'Fail to track local map' $d/mono.log) sophus=$(grep -c 'Sophus ensure' $d/mono.log) traj=$( [ -f $d/KeyFrameTrajectory.txt ] && echo yes || echo no)" | tee -a $LOG
    if [ "$ex" = "134" ] || [ ! -f $d/KeyFrameTrajectory.txt ]; then crashes=$((crashes+1)); else crashes=0; fi
    [ $crashes -ge 3 ] && { echo "STOP: 3 consecutive crashes" | tee -a $LOG; exit 1; }
    sleep 10
  done
done
echo "SEGMENT $SEG DONE $(date +%T)" | tee -a $LOG

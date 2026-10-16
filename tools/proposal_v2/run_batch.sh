#!/bin/bash
# Run a list of proposal-v2 EuRoC runs in sequence. Each line of the plan file: <mode> <tag> <speed> <seq...>
# Stops after 3 consecutive non-zero mid-run exits (exit != 0 and no KeyFrameTrajectory saved) or disk < 10 GB.
# Usage: run_batch.sh <plan_file> <log_file>
PLAN=${1:?plan}; LOG=${2:?log}; REPO=~/mono-slam-cnn-loop-closure; CRASH=0
while read -r MODE TAG SPEED SEQS; do
  [ -z "$MODE" ] || [[ "$MODE" == \#* ]] && continue
  FREE=$(df --output=avail -BG ~ | tail -1 | tr -dc 0-9)
  [ "$FREE" -lt 10 ] && { echo "$(date +%T) STOP disk ${FREE}G" >> $LOG; exit 1; }
  while pgrep -x rosmaster > /dev/null; do sleep 5; done
  $REPO/tools/proposal_v2/run_euroc.sh $MODE $TAG $SPEED $SEQS > /dev/null 2>&1
  OUT=$REPO/results/proposal_v2/runs/${TAG}_${MODE}
  EX=$(grep mono_exit $OUT/meta.txt | cut -d= -f2)
  if [ -s $OUT/KeyFrameTrajectory.txt ]; then CRASH=0; else CRASH=$((CRASH+1)); fi
  echo "$(date +%T) ${TAG}_${MODE} exit=$EX traj=$([ -s $OUT/KeyFrameTrajectory.txt ] && echo yes || echo NO) maps=$(grep -c 'Creation of new map with id' $OUT/mono.log) merges=$(grep -c 'Merge finished' $OUT/mono.log) loops=$(grep -c '\*Loop detected' $OUT/mono.log) accepted=$(grep '\[PROP\] accepted' $OUT/mono.log | grep -o 'list=[a-z]* src=[a-z0-9]*' | tr '\n' ';')" >> $LOG
  [ $CRASH -ge 3 ] && { echo "$(date +%T) STOP 3 consecutive crashes" >> $LOG; exit 1; }
done < $PLAN
echo "$(date +%T) BATCH DONE" >> $LOG

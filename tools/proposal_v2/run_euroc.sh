#!/bin/bash
# Headless EuRoC run: publisher -> clahe_node (native res) -> ORB-SLAM3 Mono [+ descriptor node / load].
# Usage: run_euroc.sh <none|resnet18|resnet18_dry|load_only> <run_tag> <speed_mult> <seq_dir> [seq_dir ...]
#   speed_mult: wall s per sensor s (1.0 real time; higher = slower). Several seq_dirs = one process,
#   multi-session via /orb_slam3/new_session -> ChangeDataset().
# Always monitored (topic statistics + tools/diag/monitor.py). Output: results/proposal_v2/runs/<tag>_<mode>/
MODE=${1:?mode}; TAG=${2:?tag}; SPEED=${3:?speed}; shift 3; SEQS="$@"
[ -n "$SEQS" ] || { echo "need at least one sequence"; exit 1; }
REPO=~/mono-slam-cnn-loop-closure
OUT=$REPO/results/proposal_v2/runs/${TAG}_${MODE}
YAML=${YAML:-$HOME/ORB_SLAM3/Examples/Monocular/EuRoC.yaml}
LOAD_KF_HZ=${LOAD_KF_HZ:-1.8}
NODE_ARGS=${NODE_ARGS:-}      # extra rosparams for loop_closure_node.py, e.g. "_mode:=xmap _xmap_thresh:=0.9"
if [ -e "$OUT" ]; then echo "$OUT already exists; use a new tag."; exit 1; fi
if pgrep -x rosmaster > /dev/null; then echo "A ROS master is already running."; exit 1; fi
mkdir -p "$OUT"
source /opt/ros/noetic/setup.bash
source ~/cv_bridge_ws/devel/setup.bash
export ROS_PACKAGE_PATH=${ROS_PACKAGE_PATH}:~/ORB_SLAM3/Examples_old/ROS
{
  echo "mode=$MODE"; echo "seqs=$SEQS"; echo "speed=$SPEED"; echo "yaml=$YAML"
  echo "yaml_md5=$(md5sum "$YAML" | cut -d' ' -f1)"; echo "load_kf_hz=$LOAD_KF_HZ"; echo "node_args=$NODE_ARGS"; echo "node_md5=$(md5sum $REPO/ros_nodes/loop_closure_node.py | cut -d' ' -f1)"
  echo "date=$(date -Iseconds)"
  echo "repo_sha=$(git -C $REPO rev-parse HEAD)"; echo "repo_dirty=$(git -C $REPO status --porcelain -- ros_nodes tools scripts | wc -l)"
  echo "orbslam_sha=$(git -C ~/ORB_SLAM3 rev-parse HEAD)"
  echo "orbslam_branch=$(git -C ~/ORB_SLAM3 rev-parse --abbrev-ref HEAD)"
  echo "orbslam_diff_md5=$(git -C ~/ORB_SLAM3 diff | md5sum | cut -d' ' -f1)"
  echo "mono_mtime=$(stat -c %y ~/ORB_SLAM3/Examples_old/ROS/ORB_SLAM3/Mono)"
  echo "lib_mtime=$(stat -c %y ~/ORB_SLAM3/lib/libORB_SLAM3.so)"
} > "$OUT/meta.txt"

roscore > "$OUT/roscore.log" 2>&1 &
sleep 4
rosparam set /enable_statistics true
rosparam set /statistics_window_min_size 1
rosparam set /statistics_window_max_size 2
python3 $REPO/tools/diag/monitor.py "$OUT" 1 0 > "$OUT/monitor.log" 2>&1 &
MON_PID=$!
python3 -u $REPO/ros_nodes/clahe_node.py _resize_width:=0 _resize_height:=0 > "$OUT/clahe.log" 2>&1 &
CLAHE_PID=$!
python3 -u $REPO/tools/proposal_v2/kf_logger.py "$OUT/kf_log.csv" > "$OUT/kf_logger.log" 2>&1 &
KFLOG_PID=$!
sleep 2
cd "$OUT"
rosrun ORB_SLAM3 Mono ~/ORB_SLAM3/Vocabulary/ORBvoc.txt "$YAML" > "$OUT/mono.log" 2>&1 &
MONO_PID=$!
sleep 10
DESC_PID=""
NODE=$REPO/ros_nodes/loop_closure_node.py
case $MODE in
  resnet18)     python3 -u $NODE _dump_path:=$OUT/descs.npz $NODE_ARGS > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  resnet18_dry) python3 -u $NODE _dump_path:=$OUT/descs.npz $NODE_ARGS /loop_closure/candidate_kfids:=/loop_closure/dry_run > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  load_only)    python3 -u $REPO/tools/proposal_v2/load_only_v2.py $LOAD_KF_HZ 20 > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  none)         ;;
  *) echo "unknown mode $MODE"; kill $MONO_PID $MON_PID $CLAHE_PID; pkill -x rosmaster; exit 1 ;;
esac
[ -n "$DESC_PID" ] && sleep 15
python3 -u $REPO/tools/proposal_v2/euroc_session_publisher.py $SPEED $SEQS > "$OUT/pub.log" 2>&1
sleep 5
rosnode kill /Mono > /dev/null 2>&1
wait $MONO_PID
echo "mono_exit=$?" >> "$OUT/meta.txt"
[ -n "$DESC_PID" ] && { kill -INT $DESC_PID 2>/dev/null; sleep 3; kill $DESC_PID 2>/dev/null; }
kill $CLAHE_PID $KFLOG_PID 2>/dev/null
kill $MON_PID 2>/dev/null; wait $MON_PID 2>/dev/null
pkill -x rosmaster; pkill -f roscore
sleep 3
echo "=== $TAG / $MODE: exit=$(grep mono_exit $OUT/meta.txt | cut -d= -f2) maps=$(grep -c 'Creation of new map with id' $OUT/mono.log) merges=$(grep -c 'Merge finished' $OUT/mono.log) loops=$(grep -c '\*Loop detected' $OUT/mono.log)"
grep -E "PROP-FINAL|\[PROP\] accepted" "$OUT/mono.log"

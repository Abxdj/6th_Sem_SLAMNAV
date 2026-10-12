#!/bin/bash
# Replay a recorded drive through ORB-SLAM3, with or without a descriptor node.
# Usage: ./scripts/replay_bag.sh <none|resnet18|dino|efficientnet> <bag> <run_tag> [rate] [start_s] [duration_s]
MODE=${1:?mode required}
BAG=$(realpath "${2:?bag path required}")
[ -f "$BAG" ] || { echo "bag not found: $BAG"; exit 1; }
TAG=${3:?run tag required}
RATE=${4:-0.5}
START=${5:-0}
DUR=${6:-}

REPO=~/mono-slam-cnn-loop-closure
OUT=$REPO/results/gazebo_ab/${TAG}_${MODE}
if [ -e "$OUT" ]; then echo "$OUT already exists; use a new tag."; exit 1; fi
if pgrep -f rosmaster > /dev/null; then echo "A ROS master is already running. Close Gazebo and other ROS terminals first."; exit 1; fi
mkdir -p "$OUT"

source /opt/ros/noetic/setup.bash
source ~/cv_bridge_ws/devel/setup.bash
export ROS_PACKAGE_PATH=${ROS_PACKAGE_PATH}:~/ORB_SLAM3/Examples_old/ROS

{
  echo "mode=$MODE"; echo "bag=$BAG"; echo "rate=$RATE"; echo "start=$START"; echo "duration=${DUR:-full}"
  echo "date=$(date -Iseconds)"
  echo "repo_sha=$(git -C $REPO rev-parse HEAD)"
  echo "orbslam_sha=$(git -C ~/ORB_SLAM3 rev-parse HEAD)"
  echo "orbslam_diff_md5=$(git -C ~/ORB_SLAM3 diff | md5sum | cut -d' ' -f1)"
} > "$OUT/meta.txt"

roscore > "$OUT/roscore.log" 2>&1 &
sleep 4

cd "$OUT"
rosrun ORB_SLAM3 Mono ~/ORB_SLAM3/Vocabulary/ORBvoc.txt $REPO/config/turtlebot3_waffle.yaml > "$OUT/mono.log" 2>&1 &
MONO_PID=$!
sleep 10

DESC_PID=""
case $MODE in
  resnet18)     python3 $REPO/ros_nodes/loop_closure_node.py > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  dino)         python3 $REPO/ros_nodes/loop_closure_dino.py > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  efficientnet) python3 $REPO/ros_nodes/loop_closure_efficientnet.py > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  none)         ;;
  *) echo "unknown mode $MODE"; exit 1 ;;
esac
[ -n "$DESC_PID" ] && sleep 15

PLAY_ARGS="--quiet -r $RATE -s $START"
[ -n "$DUR" ] && PLAY_ARGS="$PLAY_ARGS -u $DUR"
rosbag play $PLAY_ARGS "$BAG"
sleep 5

rosnode kill /Mono > /dev/null 2>&1
wait $MONO_PID
echo "mono_exit=$?" >> "$OUT/meta.txt"
[ -n "$DESC_PID" ] && kill $DESC_PID 2>/dev/null
pkill -f rosmaster; pkill -f roscore
sleep 3

echo "=== $TAG / $MODE ==="
grep "FINAL STATS" "$OUT/mono.log"
echo "maps created: $(grep -c 'Creation of new map with id' "$OUT/mono.log")"
echo "merges: $(grep -c 'Merge finished' "$OUT/mono.log")"
grep "matchedKF" "$OUT/mono.log"
ls -la "$OUT/KeyFrameTrajectory.txt" 2>/dev/null || echo "no trajectory saved"

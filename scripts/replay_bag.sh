#!/bin/bash
# Replay a recorded drive through ORB-SLAM3, with or without a descriptor node.
# Usage: ./scripts/replay_bag.sh <none|resnet18|resnet18_dry|load_only|dino|efficientnet> <bag> <run_tag> [rate] [start_s] [duration_s]
# Optional env (all off by default; unset = original behaviour):
#   YAML=<path>     ORB-SLAM3 settings file (default config/turtlebot3_waffle.yaml)
#   MONITOR=1       enable ROS topic statistics, rosbag --clock, and run tools/diag/monitor.py
#   RELAY="X Y"     play the bag to /camera/image_full and insert `topic_tools drop X Y`
#                   (drops X of every Y frames) in front of /camera/image_raw
MODE=${1:?mode required}
BAG=$(realpath "${2:?bag path required}")
[ -f "$BAG" ] || { echo "bag not found: $BAG"; exit 1; }
TAG=${3:?run tag required}
RATE=${4:-0.5}
START=${5:-0}
DUR=${6:-}

REPO=~/mono-slam-cnn-loop-closure
YAML=$(realpath "${YAML:-$REPO/config/turtlebot3_waffle.yaml}")
[ -f "$YAML" ] || { echo "yaml not found: $YAML"; exit 1; }
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
  echo "orbslam_branch=$(git -C ~/ORB_SLAM3 rev-parse --abbrev-ref HEAD)"
  echo "yaml=$YAML"; echo "yaml_md5=$(md5sum "$YAML" | cut -d' ' -f1)"
  echo "monitor=${MONITOR:-0}"; echo "relay=${RELAY:-none}"
} > "$OUT/meta.txt"

roscore > "$OUT/roscore.log" 2>&1 &
sleep 4

MON_PID=""
if [ "${MONITOR:-0}" = "1" ]; then
  rosparam set /enable_statistics true
  rosparam set /statistics_window_min_size 1
  rosparam set /statistics_window_max_size 2
  BAG_START=$(python3 -c "import rosbag,sys; print(rosbag.Bag(sys.argv[1]).get_start_time())" "$BAG") \
    python3 $REPO/tools/diag/monitor.py "$OUT" "$RATE" "$START" > "$OUT/monitor.log" 2>&1 &
  MON_PID=$!
  sleep 2
fi

cd "$OUT"
rosrun ORB_SLAM3 Mono ~/ORB_SLAM3/Vocabulary/ORBvoc.txt "$YAML" > "$OUT/mono.log" 2>&1 &
MONO_PID=$!
sleep 10

DESC_PID=""
case $MODE in
  resnet18)     python3 $REPO/ros_nodes/loop_closure_node.py > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  resnet18_dry) python3 $REPO/ros_nodes/loop_closure_node.py /loop_closure/candidate_kfids:=/loop_closure/dry_run > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  dino)         python3 $REPO/ros_nodes/loop_closure_dino.py > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  efficientnet) python3 $REPO/ros_nodes/loop_closure_efficientnet.py > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  load_only)    python3 $REPO/tools/diag/load_only.py > "$OUT/desc.log" 2>&1 & DESC_PID=$! ;;
  none)         ;;
  *) echo "unknown mode $MODE"; exit 1 ;;
esac
[ -n "$DESC_PID" ] && sleep 15

PLAY_ARGS="--quiet -r $RATE -s $START"
[ -n "$DUR" ] && PLAY_ARGS="$PLAY_ARGS -u $DUR"
[ "${MONITOR:-0}" = "1" ] && PLAY_ARGS="$PLAY_ARGS --clock"
RELAY_PID=""
if [ -n "${RELAY:-}" ]; then
  rosrun topic_tools drop /camera/image_full $RELAY /camera/image_raw > "$OUT/relay.log" 2>&1 &
  RELAY_PID=$!
  sleep 2
  rosbag play $PLAY_ARGS "$BAG" /camera/image_raw:=/camera/image_full
else
  rosbag play $PLAY_ARGS "$BAG"
fi
sleep 5
[ -n "$RELAY_PID" ] && kill $RELAY_PID 2>/dev/null

rosnode kill /Mono > /dev/null 2>&1
wait $MONO_PID
echo "mono_exit=$?" >> "$OUT/meta.txt"
[ -n "$DESC_PID" ] && kill $DESC_PID 2>/dev/null
[ -n "$MON_PID" ] && { kill $MON_PID 2>/dev/null; wait $MON_PID 2>/dev/null; }
pkill -f rosmaster; pkill -f roscore
sleep 3

echo "=== $TAG / $MODE ==="
grep "FINAL STATS" "$OUT/mono.log"
echo "maps created: $(grep -c 'Creation of new map with id' "$OUT/mono.log")"
echo "merges: $(grep -c 'Merge finished' "$OUT/mono.log")"
echo "proposals: $(grep -c 'LOOP CLOSURE' "$OUT/desc.log" 2>/dev/null || echo 0)  injections: $(grep -c 'injected external candidate' "$OUT/mono.log")"
grep "matchedKF" "$OUT/mono.log"
ls -la "$OUT/KeyFrameTrajectory.txt" 2>/dev/null || echo "no trajectory saved"

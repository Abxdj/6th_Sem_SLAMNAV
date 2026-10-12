#!/bin/bash
# Launch pipeline for EuRoC benchmark evaluation
# Usage: ./launch_euroc_eval.sh [resnet18|dino|efficientnet|none] [sequence_path] [speed]

MODE=${1:-resnet18}
SEQ=${2:-$HOME/euroc_v1/vicon_room1/V1_01_easy/extracted}
SPEED=${3:-2.0}

echo "EuRoC evaluation: mode=$MODE  seq=$SEQ  speed=$SPEED"

source /opt/ros/noetic/setup.bash
source ~/cv_bridge_ws/devel/setup.bash
export ROS_PACKAGE_PATH=${ROS_PACKAGE_PATH}:~/ORB_SLAM3/Examples_old/ROS

# Terminal 1 - roscore
gnome-terminal --title="roscore" -- bash -c "roscore; exec bash" &
sleep 3

# Terminal 2 - CLAHE node (no resize for EuRoC native 752x480)
gnome-terminal --title="CLAHE Node" -- bash -c "
    source /opt/ros/noetic/setup.bash
    source ~/cv_bridge_ws/devel/setup.bash
    python3 ~/mono-slam-cnn-loop-closure/ros_nodes/clahe_node.py _resize_width:=0 _resize_height:=0;
    exec bash" &
sleep 3

# Terminal 3 - ORB-SLAM3 with EuRoC calibration
gnome-terminal --title="ORB-SLAM3" -- bash -c "
    source /opt/ros/noetic/setup.bash
    source ~/cv_bridge_ws/devel/setup.bash
    export ROS_PACKAGE_PATH=\$ROS_PACKAGE_PATH:~/ORB_SLAM3/Examples_old/ROS
    cd ~/mono-slam-cnn-loop-closure && rosrun ORB_SLAM3 Mono ~/ORB_SLAM3/Vocabulary/ORBvoc.txt \
        ~/ORB_SLAM3/Examples/Monocular/EuRoC.yaml;
    exec bash" &
sleep 5

# Terminal 4 - Loop closure module (skip entirely if MODE=none)
if [ "$MODE" = "dino" ]; then
    gnome-terminal --title="Loop Closure - DINO ViT" -- bash -c "
        source /opt/ros/noetic/setup.bash
        source ~/cv_bridge_ws/devel/setup.bash
        python3 ~/mono-slam-cnn-loop-closure/ros_nodes/loop_closure_dino.py;
        exec bash" &
    sleep 2
elif [ "$MODE" = "efficientnet" ]; then
    gnome-terminal --title="Loop Closure - EfficientNet-B0" -- bash -c "
        source /opt/ros/noetic/setup.bash
        source ~/cv_bridge_ws/devel/setup.bash
        python3 ~/mono-slam-cnn-loop-closure/ros_nodes/loop_closure_efficientnet.py;
        exec bash" &
    sleep 2
elif [ "$MODE" = "none" ]; then
    echo "Control run - no loop closure descriptor node launched"
else
    gnome-terminal --title="Loop Closure - ResNet18" -- bash -c "
        source /opt/ros/noetic/setup.bash
        source ~/cv_bridge_ws/devel/setup.bash
        python3 ~/mono-slam-cnn-loop-closure/ros_nodes/loop_closure_node.py;
        exec bash" &
    sleep 2
fi

# Terminal 5 - EuRoC publisher
gnome-terminal --title="EuRoC Publisher" -- bash -c "
    source /opt/ros/noetic/setup.bash
    python3 ~/mono-slam-cnn-loop-closure/evaluation/euroc_publisher.py $SEQ $SPEED;
    exec bash" &

echo "All nodes launched."
echo "Usage: ./launch_euroc_eval.sh [resnet18|dino|efficientnet|none] [sequence_path] [speed]"

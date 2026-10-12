# Results status

## Valid (after the ros_mono.cc resize fix, 2026-10-12)
- KFT_kitti00_standalone_run{1,2,3}: mono_kitti, ATE 10.14 / 8.86 / 6.89 m (median 8.86)
- KFT_kitti00_control_noresize_run{1,2,3}: live ROS pipeline, real time, ATE 15.32 / 4.51 / 9.40 m (median 9.40)
- KFT_kitti00_control_noresize_fast2x_run1: live, 2x playback (speed arg 0.5), ATE 6.24 m
- KFT_euroc_v102_control_noresize_run{1,2,3}: ATE 0.329 (spike near 44 s) / 0.0633 / 0.0635 m
- gazebo_ab/: record/replay A/B on drive1.bag (5 control vs 5 ResNet18)

## Invalid - kept for the record
- KFT_kitti00_control_run1, KFT_kitti00_noclahe_run1: ros_mono.cc resized every frame to
  640x480, so the map fragmented (130-165 m). Bug, not a result.
- Phase 2 ATE comparisons made before LoopClosing instrumentation are void: injected
  candidates were never verified (corrections from injection = 0), so those runs measure
  run-to-run noise only.

## To be confirmed
- KFT_*_TUNED_*, KFT_room_*, KFT_mh02_*, KFT_euroc_v101_control_run1,
  KFT_euroc_v102_resnet18_run1: check whether they predate instrumentation.

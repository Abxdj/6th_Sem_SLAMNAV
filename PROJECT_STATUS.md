# SLAM project status (15 Oct 2026)

Repo: github.com/Abxdj/6th_Sem_SLAMNAV. Branches:
- `audit-snapshot`: pushed 12 Oct; contains the resize fix.
- `diagnosis`: local; push it.
- `master`: still Phase 1; merge into it only after the README update.

## Established results
- **ros_mono.cc resize bug fixed.** KITTI 00 live ROS (real time) gives 15.32 / 4.51 / 9.40 m, median 9.40. Standalone gives 10.14 / 8.86 / 6.89 m, median 8.86. Gate A passes for KITTI. DBoW2 closes 4–5 loops per run on its own.
- **EuRoC V1_02 live control:** 0.329 (spike near 44 s) / 0.0633 / 0.0635 m. The resize was not the cause of the gap to published results. Standalone `mono_euroc` x3 still to run.
- **Descriptor AUC on V1_02** (position < 0.5 m and orientation < 45°): ResNet18 0.936, EfficientNet-B0 0.953, DINO 0.969. Best-F1 thresholds don't transfer between V1_02 and V1_01.
- **Gazebo replay A/B** (drive1.bag, 0.5x):

  | Arm | Maps | Merges | Corrections |
  |---|---|---|---|
  | Control (n=10) | 5.1 | 0.2 | 2.5 |
  | Dry (n=5) | 4.2 | 1.2 | 2.0 |
  | Injection (n=5) | 4.0 | 1.6 | 2.0 |

  - Node running vs control, merges: p = 0.0014.
  - Injection vs dry, merges: p = 0.49.
  - So the effect comes from the node running, not from injection.
- **Diagnosis** (Claude Code, `results/diagnosis/DIAGNOSIS_REPORT.md`):
  - The Gazebo bag is limited by its route: blank or dark walls cause deterministic tracking loss. Not caused by FAST thresholds, duplicate frames or calibration.
  - The node-running effect is compute contention. It doubles ORB-SLAM3 input frame drops (1.8% to 3.7%), and a load-only process reproduces this.
  - **95% of proposals point at keyframes ORB-SLAM3 already culled.** The rest fail the covisibility gate. 126/128 matches are 100–220 keyframes back, just past `SKIP_RECENT=100`.
  - The bag is CLAHE'd, has no ground truth, and was recorded in turtlebot3_house. Retire it except for smoke tests.

## Next steps (in order)
1. Overnight: 5 full load-only replays (Claude Code is ready; tell it: yes to load-only, no to Gazebo, change `pgrep -f` to `pgrep -x rosmaster`).
2. Fix the proposal design:
   - ORB-SLAM3 publishes culled keyframe ids; the node deletes them from its database.
   - Exclude recent matches by time or covisibility, not by keyframe count.
   - Inject into the merge list as well, with keyframe lookup across all maps.
   - Compute descriptors on the actual keyframe image.
3. Multi-session EuRoC (MH01 to MH05), measuring Recall@1 against DBoW2.
4. Re-record Gazebo: avoid bare walls, drive forward, camera at 30 Hz, record raw images plus /odom and /gazebo/model_states.
5. README update, then merge into master. EuRoC standalone x3. Update the paper draft, whose KITTI section is outdated.

## Housekeeping
- `git -C ~/ORB_SLAM3 branch -D diag-counters`
- `git push -u origin diagnosis`
- Log frame drops (`MONITOR=1`) in all future runs, including KITTI and EuRoC.

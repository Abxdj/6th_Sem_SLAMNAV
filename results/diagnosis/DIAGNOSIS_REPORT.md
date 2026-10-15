# Gazebo mapping diagnosis: `bags/drive1.bag`

**Date:** 2026-10-15
**Repo:** `audit-snapshot` @ `039ed9b`, with uncommitted harness changes listed in §7
**ORB-SLAM3:** `4452a3c` + project patches (diff md5 `54c642ba…`), restored and verified after H8 (§7)
**Machine time used:** ≈5.2 h of the 6 h budget

**Evidence labels** used throughout:
- **confirmed**: a direct measurement that answers the question.
- **suggestive**: consistent data, but small n or p > 0.05.
- **refuted**: the data contradict the hypothesis.
- **untested**: not measured.

Every number gives its n. Interpretations are marked *(interpretation)*.

---

## 1. Verdict

ORB-SLAM3 maps this drive badly mainly because of **what the camera sees along this particular drive**, not because of the FAST thresholds, duplicate frames or calibration.

In the instrumented full control replay (n = 1, consistent with the 10 earlier controls), tracking was lost at **5 places**, and each loss started a new map. They fall into two kinds:

- **Low-texture views.** At bag t≈922 s the robot faces a plain wall. At t≈1330 s it is pressed against a dark wall (FAST-20 finds 0 corners).
  - The 1330 s loss is **deterministic**: it happened in 9 of 9 segment replays, at every FAST setting.
  - These are **confirmed** causes for those two events.
- **Fast pans along repetitive or close-up brick walls.** These are at t≈627 s and 749 s.
  - These losses are **stochastic**: at 627 s, 6 of 18 segment-A replays lost tracking (1/3 for the FAST 5/1 baseline), and 6 of 10 earlier full controls.
  - Rotation-dominant motion before losses is only **suggestive** (4/5 vs 14/34 random moving windows, p = 0.16).

Monocular ORB-SLAM3 needs parallax to re-initialise after each loss. It rarely merges the maps back: 0.2 merges per control run, n = 10. *(interpretation)* That combination produces the 4–6 maps per run.

The "node running changes behaviour" effect has a **measured mechanism, but it is not yet linked to the outcome**:
- Running the descriptor node roughly **doubles Mono's input frame drops** (1.8% → 3.7%, p = 0.024, n = 3 vs 6), and puts the GPU into a different utilisation/clock state.
- A load-only process with **no ROS connection at all** reproduces both changes exactly (dry 3.70% vs load 3.66%, p = 1.0).
- So the node acts through compute contention, not through information.
- Whether this contention is what raises merges in full runs (control 0.2 vs node 1.4, p = 0.0014, n = 10 vs 10) is **untested**: merges can't occur inside 4-minute segments.

---

## 2. Hypotheses H1–H9

| ID | Hypothesis | Verdict | Key numbers | n | Evidence |
|---|---|---|---|---|---|
| H1 | Low FAST thresholds (5/1) cause repeated tracking loss | **Refuted as the dominant cause; weakly suggestive at segment A** | Offline: FAST-5 corners are as matchable as FAST-20 (F-RANSAC inlier ratio 0.92 vs 0.93) and give *more* inliers (median 1308 vs 1010). Seg B: loss at the dark-wall event in 9/9 runs at all three settings (raising FAST makes it happen ~5 s *earlier*). Seg A: runs with ≥1 loss: 5/1 → 1/3, 12/5 → 2/3, 20/7 → 0/3 (not monotonic; Fisher p = 1.0 for 5/1 vs 20/7). FAST 20/7 crashed with a NaN-pose Sophus abort in 2/6 runs vs 1/23 replays at other settings (the 1 is an H8 injection run at 5/1). | 5,397 sampled frames; 9 + 9 replays | `phase1/samples.csv`, `phase1_timeline.png`, `phase3_segA.csv`, `phase3_segB.csv` |
| H2 | Low texture in the world | **Confirmed for 2 of 5 loss events** | Losses at 922 s (plain wall; FAST-20 kp = 24, FAST-5 = 684 in the preceding 3 s) and 1334 s (dark wall; kp = 0, image std 3.2). The 1334 s loss occurred in 9/9 seg-B replays. The other 3 losses had high texture (kp20 1211–2000). | 5 events (1 full run) + 9 replays | `loss_onsets_sheet.jpg`, `contact_sheet.jpg`, `frame_t924.png`, `frame_t1331.png` |
| H3 | Turning in place (pure rotation) causes loss | **Suggestive** | Robust rotation-only flow fit on KLT tracks; the model was validated on synthetic motion (pure yaw: parallax ratio 0.008; forward motion: 1.25). Rotation-dominant (ratio < 0.1) in the 3 s before 4/5 loss onsets, vs 14/34 random windows with motion (Fisher p = 0.16). Flow before losses is larger (median 2.1 vs 0.3 px; p = 0.13). One onset (1334 s) is the blank wall, where flow means nothing. | 5 onsets, 60 random windows | `h3_motion.csv`, `tools/diag/motion_events.py` |
| H4 | Duplicated / near-identical frames at ~67 Hz | **Refuted (duplicates); a 30 Hz decimation does not help** | 107,938 frames, 66.8 unique header stamps per sim-second, 0 repeated stamps, 0 seq gaps. **716 exact duplicates (0.66%)**, all during static periods. MAD < 0.1 for 6.7% of frames (robot stationary). Drop-1-of-2 relay + `Camera.fps 33`: runs with a loss 2/3 vs 1/3 for baseline in seg A. | full bag; 3 replays | `phase1_duplicates.png`, `phase1/frames.csv`, `phase3_segA.csv` (arm `drop2`) |
| H5 | Resource contention explains the "node running" effect | **Mechanism confirmed; effect on the outcome untested** | Mono input drop %: base 1.80 (n = 3), dry 3.70 (n = 3), load-only 3.66 (n = 3); base vs node+load p = 0.024, dry vs load p = 1.0. GPU util %: base ≈ 23, dry 5.4, load 5.2 *(interpretation: a live CUDA context raises GPU clocks, so util % drops)*. CPU of the descriptor process: dry 5.6%, load 11.2%. Segment outcomes: runs with a loss 1/3 in each of base / dry / load. Merges can't be assessed in 4-min segments. | 9 replays | `phase3_segA.csv`, per-run `resources.csv`, `topicstats.csv` |
| H6 | Is the bag already CLAHE-processed? | **Publisher confirmed; CLAHE state very likely but not provable from pixels** | The bag has one connection, `callerid=/clahe_node`, mono8 640×480. `clahe_node.py` at `2a2ac68` (the snapshot just before recording) applies `clahe.apply`. The pixel test is inconclusive (CLAHE is not idempotent; noiseless Gazebo renders leave flat tiles flat, tile range 0). Gazebo camera noise is not configured. So "CLAHE amplifies sensor noise" does not apply; CLAHE stretches render shading and texture. | 1 bag; 4 frames | `rosbag` connection header; `git show 2a2ac68:ros_nodes/clahe_node.py` |
| H7 | Sophus scale crash during merge/loop Sim3 | **Characterised: two distinct crash types** | (a) `RxSO3 … Scale factor must be greater-equal epsilon`: 1 occurrence (full_r7 dry, right after a loop correction). (b) `SO3::exp failed! omega: -nan`, i.e. a NaN pose: 4 occurrences (full_r9 dry, right after a new map; seg-A fast20_r2 at 703 s and seg-B fast20_r3 at 1431 s, neither preceded by a loop or merge; h8 injection run r1 at 782 s). Total mid-run aborts: 2/20 earlier full runs, 3/33 of my runs. All other non-zero exits (139, 133) occur **at shutdown, after the trajectory is saved**. | 51 runs | per-run `mono.log`, `events.csv` |
| H8 | Why 83% of proposals were never injected | **Confirmed: keyframe culling** | Temporary `[DIAG]` counters, seg A, 2 injection runs, **102 proposals**: 102 received (0 lost at the queue-size-1 subscriber), 0 dropped by the 50-cap, **97 (95%) matched KF already culled** (in no map), 1 in another map, 0 duplicates with DBoW2, 0 "not evaluated", 0 left in the queue at exit. **4 injected → 4/4 rejected by the covisibility gate.** Of the 50 `abortedByNearKF` in run 2, 2 were ours and 48 DBoW2's. Consistent with the old logs: in runs where nothing was merged into the final map, it keeps only 18–21% of the KF ids it allocated (213 of 1184 in full_r1, 213 of 998 in full_r4). `small_map` deferrals (18, 31) delay but don't drop. | 2 runs | `diag_h8_segA_r*/mono.log`, `h8_orbslam_backup/diag_counters.patch`, `forensics_gazebo_ab.json` |
| H9 | Calibration is correct | **Untested live (Gazebo not launched; it needs your OK). Intrinsics agree by computation; render rate contradicts the yaml.** | From the xacro (`hfov 1.3439`, 1920×1080, square pixels): fx 402.3, fy 536.4, cx 320.2, cy 240.2 after the 640×480 resize, vs yaml 403 / 536.4 / 320.5 / 240.5. **True render rate 66.8 Hz** (sim time), not 30: the `<sensor>` has no `<update_rate>`, and the plugin's `updateRate 30` evidently does not cap publication *(interpretation)*. | — | `/opt/ros/noetic/share/turtlebot3_description/urdf/turtlebot3_waffle.gazebo.xacro:146–172` |

**"The video was slowed down, so too many points were tracked."** Playback rate can't change how many corners are in a frame, because the frames are identical at any rate. What rate *does* change is whether ORB-SLAM3 keeps up. At 0.5× a frame arrives every 30 ms, and Mono's `queue_size=1` subscriber dropped:
- **15%** of frames in the first 60 s smoke test,
- **39%** in the first 30 s of the full run (while initialising),
- **2.6%** over the whole run.

So the intuition that speed matters is right, but the mechanism is dropped frames, not extra points. A useful follow-up is a 0.25× arm to see whether near-zero drops change anything (untested).

---

## 3. What this means for the earlier A/B results

- **The table in the brief reproduces exactly** from the logs:
  - maps 5.1 / 4.2 / 4.0
  - merges 0.2 / 1.2 / 1.6
  - control vs node merges, Mann-Whitney p = 0.0014; maps p = 0.015
  - injection vs dry merges p = 0.49
- **Injection added no information.** 0 corrections came from injection in any run. H8 shows why: 95% of proposals name a culled KF, and the rest are covisible neighbours. Any "injection vs control" difference is therefore a **node-running** effect.
- **The node-running effect is compute contention, not information** (H5). It is real at the level of Mono's input stream (2× frame drops) and GPU state, and a ROS-free load process reproduces it. The A/B results are therefore interpretable only as "*a GPU process alongside ORB-SLAM3 perturbs its timing*", which is not a loop-closure result.
- **The outcome is dominated by a few stochastic events.**
  - Whether the first map survives the 627 s pan: control 6/10, node arms 3/10 (Fisher p = 0.37).
  - When it survives, there is more opportunity to merge later *(interpretation)*.
  - High variance plus no ground truth means Gazebo A/B on this bag can't support an accuracy claim either way.
- **Recommendation:** treat the old A/B as a negative result for injection (no corrections) plus an unexplained timing effect. The decisive follow-up is **5 full-length load-only runs** (~4.6 h, needs your OK). If they reproduce merges ≈ 1.2–1.6, the effect is contention, full stop. If they don't, something ROS-coupled in the node matters (e.g. the extra `/camera/image_raw` subscriber), and an image-subscriber-only arm would separate it.

---

## 4. Recommended Gazebo configuration

**Can the existing bag be used?** Only for pipeline smoke tests and counter checks. It has **no ground truth** (only `/camera/image_raw`), it is already CLAHE-processed (so CLAHE can't be toggled), and its failure profile is dominated by two blank-wall views that no setting rescues. **Re-record.**

**Re-recording checklist:**
1. **World:** keep `turtlebot3_house` (it is textured; note it was *not* `turtlebot3_world`). Plan a route that never faces a bare wall closer than ~1 m: avoid 900–935 s- and 1320–1340 s-type views, or add textured models.
2. **Motion:** forward driving with gentle turns, angular speed ≤ 0.3–0.5 rad/s, no turning in place, no driving into walls. Include at least two deliberate revisits (loops) of the same corridor in the same direction.
3. **Camera rate:** add `<update_rate>30</update_rate>` inside the `<sensor>` in a *copy* of the waffle xacro, and confirm with `rostopic hz /camera/rgb/image_raw`. Set `Camera.fps` to the measured rate.
4. **Record raw plus ground truth:** `rosbag record /camera/rgb/image_raw /camera/rgb/camera_info /odom /gazebo/model_states /tf /clock`. Run CLAHE at replay time so it can be an experimental arm.
5. **ORB-SLAM3 yaml:** keep the current intrinsics (verified by computation; confirm against `camera_info` once). FAST thresholds made no consistent difference here. Keep 5/1 for continuity, or adopt the 20/7 defaults for comparability with the literature, but note the NaN-pose crashes (2/6 at 20/7 vs 1/23 at other settings).
6. **Playback:** 0.5× is adequate (≈2.6% drops). Always record Mono drops (`MONITOR=1`), and report runs with > 5% drops separately.
7. **Statistics:** ≥ 5 full runs per arm, all reported, and a load-only arm whenever a GPU node is compared against a control.

---

## 5. Every run made in this diagnosis

All runs are on `bags/drive1.bag` at rate 0.5, with outputs in `results/gazebo_ab/<tag>_<mode>/`.

- "Loss" = number of tracking-loss episodes.
- "Exit": 0 = clean; 139/133 = crash *at shutdown*, after the trajectory was saved; **134 = mid-run Sophus abort**, with no trajectory saved.

| Tag | Mode / config | Segment (bag s) | New maps | Loss | Mono drop % | Exit |
|---|---|---|---|---|---|---|
| diag_smoke | none, FAST 5/1 | 0–60 | 0 | 0 | 15.2 | 0 |
| diag_full_ctrl | none, FAST 5/1, monitored | full | 5 (+ initial) | 5 | 2.6 | 139 |
| diag_smoke_drop2 | relay drop 1/2, fps 33 | 560–590 | 0 | 0 | 0.4 | 139 |
| diag_smoke_load | load_only | 560–590 | 0 | 0 | 0.8 | 0 |
| diag_segA_base_r1–3 | none, 5/1 | 560–800 | 0 / 2 / 0 | 0 / 2 / 0 | 2.0 / 1.6 / 1.8 | 0 / 0 / 0 |
| diag_segA_fast12_r1–3 | none, 12/5 | 560–800 | 1 / 0 / 2 | 1 / 0 / 2 | 0.6 / 0.9 / 0.7 | 0 / 0 / 0 |
| diag_segA_fast20_r1–3 | none, 20/7 | 560–800 | 0 / 0 / 0 | 0 / 0 / 0 | 0.3 / 0.5 / 0.3 | 0 / **134** (703 s) / 0 |
| diag_segA_drop2_r1–3 | relay 1/2, fps 33 | 560–800 | 1 / 0 / 2 | 1 / 0 / 2 | 0.1 / 0.0 / 0.2 | 0 / 0 / 139 |
| diag_segA_dry_r1–3 | resnet18_dry | 560–800 | 1 / 0 / 0 | 1 / 0 / 0 | 3.3 / 4.6 / 3.3 | 139 / 139 / 0 |
| diag_segA_load_r1–3 | load_only | 560–800 | 2 / 0 / 0 | 2 / 0 / 0 | 3.1 / 3.7 / 4.1 | 0 / 139 / 0 |
| diag_segB_base_r1–3 | none, 5/1 | 1280–1520 | 1 / 1 / 1 | 1 / 1 / 1 | 0.1 / 0.1 / 0.1 | 139 / 139 / 0 |
| diag_segB_fast12_r1–3 | none, 12/5 | 1280–1520 | 1 / 1 / 1 | 1 / 1 / 1 | 0 / 0 / 0 | 139 / 139 / 0 |
| diag_segB_fast20_r1–3 | none, 20/7 | 1280–1520 | 1 / 2 / 1 | 1 / 2 / 1 | 0 / 0 / 0 | 139 / 0 / **134** (1431 s) |
| diag_h8_segA_r1–2 | resnet18 (injection), `diag-counters` build | 560–800 | 2 / 2 | 2 / 2 | — | **134** (782 s) / 0 |

Arms were interleaved in a seeded shuffle within each repetition (`tools/diag/run_phase3.sh`).

---

## 6. Contradictions with the facts in §1 of the brief

1. **"~67 msg/s from a camera that probably renders at 30 Hz → duplicates."** The frames are unique renders at 66.8 Hz of sim time (0 repeated stamps). Only 0.66% are byte-identical, all from a static robot.
2. **World.** `scripts/launch.sh` and the shell history (`roslaunch turtlebot3_gazebo turtlebot3_house.launch`) show the bag was recorded in **turtlebot3_house**, not `turtlebot3_world` as in H9.
3. **"Dry runs crashed 2 of 5 (one Sophus, one unknown)."** Both are Sophus aborts: r7 is the RxSO3 scale type, r9 the SO3 NaN type.
4. **"Controls crashed 0 of 10."** True of those 10, but the crash is not node-specific: two control-mode FAST 20/7 replays aborted the same way.
5. **"120 of 128 proposals matched a KF 100–220 back."** Recount: 126/128 in 100–220, and 2 > 500.
6. **Not in §1, but it matters:**
   - **Mono drops input frames**: 2.6% per full run, up to 39% while initialising.
   - Nobody was measuring this before.
7. **`desc.log` is not chronological.**
   - rospy `logwarn` (stderr) and `loginfo` (stdout, block-buffered) interleave out of order.
   - Sort by the embedded timestamp before any timing analysis. An unsorted parse produces fake 13–37-minute "stalls".
8. **Harness pitfall.** `replay_bag.sh`'s `pgrep -f rosmaster` guard matches *any* process whose command line contains the word "rosmaster", including the calling shell. That aborted four of my launches silently (no run folder was created). `pgrep -x rosmaster` would be safer (not changed).

---

## 7. Changes made (and undone)

**Project repo (uncommitted, except on branch `diagnosis`):**

`scripts/replay_bag.sh` gained opt-in features, all exact-match edits; with no env vars set it behaves as before:
- `YAML=`
- `MONITOR=1` (topic statistics, `--clock`, monitor process)
- `RELAY="X Y"` (`topic_tools drop`)
- `load_only` mode
- extra `meta.txt` fields

Note: the file already carried your uncommitted `resnet18_dry` change.

New files in `tools/diag/`:
- `bag_analysis.py`, `plot_phase1.py`, `monitor.py`, `summarize_run.py`
- `motion_events.py`, `forensics.py`, `analyze_phase3.py`
- `load_only.py`, `run_phase3.sh`, `run_h8.sh`, `h8_diag_patch.py`
- `configs/*.yaml`

**ORB-SLAM3 (H8):**
1. Before: stash list empty, branch `master`, diff md5 `54c642ba…`.
2. Created branch `diag-counters`, applied 10 print-only `[DIAG]` edits, and rebuilt. The `.so` and `Mono` mtimes advanced to 18:47, and the `.so` contained 11 `[DIAG]` strings.
3. Ran 2 replays.
4. Restored both files from backups, `git checkout master`, and rebuilt. The diff md5 is again `54c642ba…`, `git status` is byte-identical, the `.so` and `Mono` are back to their original sizes (5,121,592 / 14,509,144 bytes) with new mtimes (19:07/19:08), and they contain 0 `[DIAG]` strings.
5. The empty branch `diag-counters` (no commits) remains. Delete it with `git -C ~/ORB_SLAM3 branch -D diag-counters`.

The patch itself is saved as `h8_orbslam_backup/diag_counters.patch`.

**Not committed:** `results/diagnosis/phase1/thumbs.npz` (94 MB) and `frames.csv` (4.4 MB), which regenerate with `bag_analysis.py` in ~9 min; also the `*.pre` file backups.

# Proposal or Verification? Learned Place Recognition in ORB-SLAM3 Multi-Session Mapping

**Major Project | Dept. of Computer Science & Engineering**
**Nitte Meenakshi Institute of Technology (NMIT), Bengaluru | AY 2026–27**

> 
> **Students:** Anish Bharadwaj (1NT23CS024) · Dhanush Paturu (1NT23CS060) · Dhruva P S (1NT23CS064)

> **Status (Oct 2026):** the experiments are complete, and a paper is in preparation. The active branch is `proposal-v2`. Every claim below links to the report or result file that produced it. Pre-registered results are marked **[pre-reg]**; analyses done afterwards are marked **[post hoc]**.

---

## The question

Monocular ORB-SLAM3 corrects drift (**loop closure**) and joins maps from separate sessions (**map merging**) in two steps:

1. **Proposal.** DBoW2, a bag-of-binary-words index over ORB features, suggests a keyframe that looks like the current one.
2. **Verification.** A geometric check (Sim3 with RANSAC, then guided matching and covisibility consistency) accepts or rejects the suggestion.

Learned global image descriptors (CNN or ViT) are generally better at recognising places than DBoW2. This project asks **where ORB-SLAM3's multi-session merging actually fails, at proposal or at verification, and whether learned proposals help.**

We added a learned proposer that runs alongside ORB-SLAM3 (ResNet18 in a ROS node) and injects its candidates into ORB-SLAM3's own verification. Then we measured the effect in **pre-registered** experiments: the threshold, code, pairs, run counts and statistical tests were committed and pushed before any test run.

## Key results

Setup for every pre-registered test:
- Data: EuRoC MAV, monocular camera, real time.
- Each run feeds two flights ("sessions") to **one** ORB-SLAM3 process.
- Outcome: whether the two sessions' maps merge.
- 10 runs per arm.
- Arms:
  - **control** (plain ORB-SLAM3);
  - **load-only** (a GPU process with the same compute load, sending no candidates);
  - **injection** (our proposer, fixed threshold τ = 0.8768, calibrated beforehand on MH_01→MH_03).

| Test | Session pair | GT overlap | Control | Load-only | Injection (merges by our proposer) | Bottleneck |
|---|---|---|---|---|---|---|
| B **[pre-reg]** | MH_02→MH_04 | 0.127 | 4/10 | 2/10 | **9/10** (8) | proposal |
| C **[pre-reg]** | MH_03→MH_05 | 0.554 | 8/10 | 9/10 | 10/10 (5) | none: DBoW2 already succeeds |
| C **[pre-reg]** | MH_04→MH_02 | 0.352 | 10/10 | 10/10 | 10/10 (4) | none |
| E **[pre-reg]** | MH_02→MH_05 | 0.140 | 0/10 | 0/10 | **10/10** (9) | proposal |
| E **[pre-reg]** | MH_01→MH_04 | 0.145 | 0/10 | 0/10 | **5/10** (5) | proposal |
| E **[pre-reg]** | MH_01→MH_05 | 0.166 | 0/10 | 0/10 | 0/10 | **verification** |

Statistics:

| Test | Comparison | p |
|---|---|---|
| B | injection vs control (Fisher) | 0.057 |
| C | injection vs control (CMH) | 0.146 |
| E | injection vs control (CMH) | 7.7×10⁻⁷ |
| E | exact stratified test | 1.8×10⁻⁷ |

Reports: [`REPORT_XMAP.md`](results/proposal_v2/REPORT_XMAP.md) (B), [`REPORT_XMAP2.md`](results/proposal_v2/REPORT_XMAP2.md) (C), [`REPORT_XMAPE.md`](results/proposal_v2/REPORT_XMAPE.md) (E). Plan: [`PREREG.md`](results/proposal_v2/PREREG.md).

**What this shows**

- **Three regimes.**
  - **High overlap:** DBoW2 already merges, so there is nothing to add.
  - **Some low-overlap pairs:** DBoW2 never proposes the right match. Learned proposals let ORB-SLAM3 merge in most runs (0/60 control and load-only vs 15/30 injection in Part E).
  - **MH_01→MH_05:** about half of our proposals pointed at the right place by ground truth, yet geometric verification rejected all of them. The bottleneck there is verification.
- **Verification keeps learned proposals safe.** Across all tests, no wrong proposal led to an accepted merge.
  - Cost: up to about +0.6 ms per keyframe of verification work (measured in Part C), plus the descriptor network.
  - Part E: one DBoW2 merge joined keyframes 2.005 m apart, just outside the 2 m / 45° correctness check, and is reported as such.
- **More merging, not more accuracy.** Trajectory error (ATE) did not improve. In 4 of 15 merged injection runs in Part E, session-2 error rose to 0.25–0.52 m.
  - **[post hoc]** The merges themselves were accurate (0.03–0.04 m just after merging). The error is drift that builds 10–40 s later.
  - It appears only in merged maps; the mechanism is unresolved.
  - See [`POSTHOC_E.md`](results/proposal_v2/POSTHOC_E.md).
- **[post hoc] Why verification fails on MH_01→MH_05 isn't explained by pose difference.** The correct-but-rejected proposals were no farther or more rotated than ones that passed elsewhere. Passing appears to depend on the specific image pair.

### Limitations, stated plainly

- **One revisit place.** All four low-overlap pairs revisit the same place, about 25 s into session 2. The positive result is that this hard revisit is reliably closed. It is not shown for hard revisits in general.
- **No independent pair.** Every pair reuses a calibration or earlier test sequence. An independent pair (V1_01→V1_03, "Part D") is registered but waiting on a dataset download.
- **Narrow scope.** One dataset (EuRoC), one descriptor live (ResNet18), monocular only, desktop GPU only. No edge-hardware measurements.
- **The pre-registered prediction failed in Part E.** It required an effect on every hard pair, and MH_01→MH_05 had none.

### Supporting findings

- **Live pipeline matches standalone ORB-SLAM3 (Gate A).** KITTI 00, 3 runs each: median ATE 9.40 m live vs 8.86 m with standalone `mono_kitti`. See [`results/README.md`](results/README.md).
- **Offline, at equal precision, learned descriptors beat DBoW2's raw top-1 ranking.** ResNet18, EfficientNet-B0 and DINO ViT-S/8 are statistically tied, and DINO costs more. See [`results/proposal_v2/gate_b/`](results/proposal_v2/gate_b/).
- **Methodological lessons, each with its evidence:**

  | Lesson | Evidence |
  |---|---|
  | ORB-SLAM3 **culls keyframes**, which silently dropped 95% of external proposals until we redirected them to the surviving parent keyframe | [`DIAGNOSIS_REPORT.md`](results/diagnosis/DIAGNOSIS_REPORT.md) H8 |
  | A GPU network running beside ORB-SLAM3 changes its behaviour **through compute load alone** (input frame drops roughly doubled), so a load-matched control is needed | diagnosis H5 |
  | Similarity thresholds tuned within one session **don't transfer** across sessions, or between sequences | |
  | Monocular SLAM varies a lot between identical runs, so **single runs prove nothing** | |

## Withdrawn claims (earlier versions of this repo)

- **"CLAHE preprocessing reduces ATE by 49.5%."** Over repeated runs the effect was about 16% and not statistically significant. CLAHE is still in the pipeline but is not a contribution.
- **Phase-2 accuracy comparisons with ResNet18, DINO and EfficientNet.** Instrumentation later showed that **no injected candidate had ever been accepted**, so those comparisons measured run-to-run noise. They are kept only for the record, in `results/` (see [`results/README.md`](results/README.md)).
- **"First systematic evaluation…", and descriptor latency claims labelled "edge viable".** Withdrawn: not supported.
- **KITTI through ROS (130–165 m).** This was a bug: `ros_mono.cc` resized every frame to 640×480. It is fixed.

## Architecture

```
EuRoC publisher ──/camera/rgb/image_raw──▶ CLAHE node ──/camera/image_raw──▶ ORB-SLAM3 Mono (patched)
   │  /orb_slam3/new_session (between flights → new map)                        │
   │                                                                             ├─ /orb_slam3/new_keyframe  [id, stamp, map id]
   │                                                                             ▼
   │                                                              ResNet18 proposer (loop_closure_node.py)
   │                                                               xmap mode: top-1 cosine over other-map KFs,
   │                                                               |Δt| ≥ 30 s, score ≥ τ
   │                                                                             │
   └────────────────────────────────────────────── /loop_closure/candidate_kfids ◀┘
                                                    ▼
                         LoopClosing: redirect culled KFs → route other-map candidates to the merge list
                         → ORB-SLAM3's own verification (BoW → Sim3 RANSAC → guided matching → covisibility)
                         → one logged outcome per proposal ([PROP] lines), with attribution of each merge
```

ORB-SLAM3 changes, as commits on top of upstream `4452a3c`:

| Commit | What it adds |
|---|---|
| C1 | Redirect culled keyframes to their surviving parent |
| C2 | Look across all maps; route other-map candidates to the merge list |
| C3 | Keyframe id and timestamp topic |
| C5 | Outcome accounting for every proposal |
| C6 | Map id in the keyframe message |
| S | Session switch through `ChangeDataset` |
| C7 | Timing counters only |

Details: [`orb_slam3_patches/ORB_SLAM3_COMMIT.txt`](orb_slam3_patches/ORB_SLAM3_COMMIT.txt).

## Reproducing

### Environment (as tested)

| Component | Version |
|---|---|
| OS / ROS | Ubuntu 20.04, ROS Noetic |
| OpenCV | 4.4.0, built from source |
| cv_bridge | rebuilt against OpenCV 4.4 |
| Pangolin | v0.6 |
| Python | 3.8 |
| PyTorch | 2.4.1 + CUDA 12.1 |
| evo | 1.31.1 |
| Hardware | Intel i7 12th Gen, NVIDIA RTX 3060, 16 GB RAM |

> **cv_bridge must be rebuilt against OpenCV 4.4.** The system cv_bridge links OpenCV 4.2, and images get silently corrupted at the ROS/C++ boundary: ORB-SLAM3 waits for images forever.
> ```bash
> mkdir -p ~/cv_bridge_ws/src && cd ~/cv_bridge_ws/src
> git clone https://github.com/ros-perception/vision_opencv.git -b noetic
> cd ~/cv_bridge_ws && catkin_make -DOpenCV_DIR=/usr/local/lib/cmake/opencv4
> ```

### Build the patched ORB-SLAM3

```bash
git clone https://github.com/UZ-SLAMLab/ORB_SLAM3.git ~/ORB_SLAM3
cd ~/ORB_SLAM3 && git checkout 4452a3c
git apply ~/mono-slam-cnn-loop-closure/orb_slam3_patches/proposal_v2.patch
./build.sh                                   # core library
export ROS_PACKAGE_PATH=${ROS_PACKAGE_PATH}:~/ORB_SLAM3/Examples_old/ROS
cd Examples_old/ROS/ORB_SLAM3 && mkdir -p build && cd build && cmake .. -DROS_BUILD_TYPE=Release && make Mono
```

### Data layout

- EuRoC sequences go under `~/euroc_mh/machine_hall/<SEQ>/extracted/mav0/`.
- Ground truth is converted to TUM format with `evaluation/euroc_gt_to_tum.py`, giving `~/euroc_mh/<SEQ>_groundtruth_tum.txt`.
- Two-session ground-truth files are the two files concatenated and sorted by time.

### Run one two-session experiment

```bash
cd ~/mono-slam-cnn-loop-closure
NODE_ARGS="_mode:=xmap _xmap_thresh:=0.8768" LOAD_KF_HZ=3.55 \
  tools/proposal_v2/run_euroc.sh resnet18 MYTEST 1.0 \
  ~/euroc_mh/machine_hall/MH_02_easy/extracted ~/euroc_mh/machine_hall/MH_05_difficult/extracted
```

- **Arms:** `none` (control), `load_only`, `resnet18` (injection), `resnet18_dry` (node runs, output discarded).
- **Speed:** `1.0` is real time; higher is slower.
- **Output:** `results/proposal_v2/runs/MYTEST_<arm>/`. It contains `meta.txt` (build, node and checksum provenance), `mono.log`, `kf_log.csv` and `KeyFrameTrajectory.txt`.

### Re-run a pre-registered test, and its analysis

```bash
LOAD_KF_HZ=3.55 NODE_ARGS="_mode:=xmap _xmap_thresh:=0.8768" \
  tools/proposal_v2/run_batch.sh results/proposal_v2/plans/XMAPE_TEST.plan my_batch.log
python3 tools/proposal_v2/analyze_xmap2.py results/proposal_v2/plans/XMAPE_pairs.json my_results.json
```

The plan files contain absolute paths from the original machine, so edit them to match yours. The full Part E batch (90 runs) took about 8.3 h.

## Repository map

| Path | Contents |
|---|---|
| `ros_nodes/` | `loop_closure_node.py` (ResNet18 proposer, xmap mode); `clahe_node.py`; DINO and EfficientNet nodes (older; not used in the pre-registered tests) |
| `orb_slam3_patches/` | `proposal_v2.patch` against upstream `4452a3c`, plus full-file copies |
| `tools/proposal_v2/` | Harness (`run_euroc.sh`, `run_batch.sh`, `euroc_session_publisher.py`, `load_only_v2.py`, `kf_logger.py`), calibration, Gate B, pair overlap, and pre-registered analysis scripts |
| `tools/diag/` | Gazebo diagnosis tooling (monitor, bag analysis) |
| `results/proposal_v2/` | `PREREG.md`, reports, per-run folders `runs/`, batch logs, result JSONs |
| `results/diagnosis/` | Gazebo diagnosis report (keyframe culling, compute contention, route-limited bag) |
| `results/` (top level) | Older trajectories; validity status in `results/README.md` |
| `evaluation/`, `scripts/` | TUM, EuRoC and KITTI publishers, GT converters, earlier launch scripts |

## Licence

GPLv3, because this repository contains modified ORB-SLAM3 source. See [`LICENSE`](LICENSE).

## References

1. C. Campos et al., "ORB-SLAM3: An accurate open-source library for visual, visual-inertial, and multimap SLAM," *IEEE Trans. Robot.*, 37(6), 2021.
2. D. Gálvez-López and J. D. Tardós, "Bags of binary words for fast place recognition in image sequences," *IEEE Trans. Robot.*, 28(5), 2012.
3. M. Burri et al., "The EuRoC micro aerial vehicle datasets," *Int. J. Robot. Res.*, 35(10), 2016.
4. A. Geiger, P. Lenz, R. Urtasun, "Are we ready for autonomous driving? The KITTI vision benchmark suite," *CVPR*, 2012.
5. K. He et al., "Deep residual learning for image recognition," *CVPR*, 2016.
6. M. Tan and Q. V. Le, "EfficientNet," *ICML*, 2019.
7. M. Caron et al., "Emerging properties in self-supervised vision transformers," *ICCV*, 2021.
8. R. Arandjelović et al., "NetVLAD," *CVPR*, 2016.
9. N. Keetha et al., "AnyLoc: Towards universal visual place recognition," *IEEE RA-L*, 2024.
10. S. Lowry et al., "Visual place recognition: A survey," *IEEE Trans. Robot.*, 32(1), 2016.
11. M. Grupp, "evo: Python package for the evaluation of odometry and SLAM," 2017.

# Part C smoke run: `XMAP2SMOKE_V0102_resnet18` (2026-10-26 15:27, before the batch)

**Setup.** Injection arm (xmap, τ = 0.8768) on V1_01 → V1_02, real time. V1_02 is in no test pair. Not part of the test.

## Frozen state ([M], from `meta.txt`)

| item | value | matches Part C |
|---|---|---|
| ORB-SLAM3 sha | `9aad4f8` | yes |
| ORB-SLAM3 working-tree diff | empty (`orbslam_diff_md5` = md5 of empty input) | yes |
| node md5 | `781802e9…` | yes |
| `node_args` | `_mode:=xmap _xmap_thresh:=0.8768` | yes |
| lib mtime | 11:16:45 | yes |
| Mono mtime | 11:17:21 | yes |

- **`repo_sha=6918a21`:** the owner's `PROJECT_STATUS.md` commit on top of Part C (`b830bee`). It changes only that file.
- **`repo_dirty=1`:** a pre-existing untracked `scripts/batch_dry.sh`, which is not used.

## Patch content
`git diff d641453 9aad4f8` is 15 added lines and 0 removed, all in `src/LoopClosing.cc`:
- `#include<chrono>`;
- a timer around `NewDetectCommonRegions()`;
- a per-candidate RAII timer.

They feed `PropCount` only. There are no new print statements, and no control flow or values used by the algorithm change.

## Function ([M])

**Run health**
- Trajectory saved: 425 KFs in the final map.
- `[PROP-FINAL]` printed.
- `mono_exit=139`: the known shutdown crash, after the trajectory was saved.
- 0 "timestamp older" errors.

**Keyframe logger**
- `kf_log.csv` has 677 KFs: map 0 with 464, map 1 with 213.
- The node's own dump has 675 KFs.

**C7 counters reconcile with the C5 outcome counters**

| C7 counter | value | C5 counter | value |
|---|---|---|---|
| `n_ext_stage0` | 74 | `abort_near` | 74 |
| `n_ext_stage1` | 9 | `bow_fail` | 9 |
| `n_ext_stage2 + n_ext_stage3` | 16 + 6 = 22 | `sim3_fail` | 22 |
| `n_dbow2_stage0` | 210 | `abort_near_dbow2` | 210 |

- Ext candidates evaluated: 74 + 9 + 22 = 105.
- Received: 110 = 105 evaluated + 5 `drop_dup_with_dbow2`.

**Place-recognition time**
- `us_detect_total / n_detect_calls` = 2130.2 ms / 676 = **3.15 ms per KF**.
- Failed ext candidates (stages 1–3): 31 attempts, 75.3 ms in total.

## Timing-counter overhead ([M], offline micro-benchmark `c7bench.cc`, -O3, 10⁶ iterations × 3)
The benchmark replicates the `PropCount` mutex and `std::map<std::string,int>` increment, the string build and the two `steady_clock::now()` calls.

**Cost per call**
- Per candidate timer: **145 ns**.
- Per KF timer: **66 ns**.

**Overhead per KF**
- Candidates per KF: (105 ext + 974 DBoW2) / 676 KFs = 1.6.
- 66 + 1.6 × 145 ≈ **0.30 µs per KF**, about **0.01%** of the 3.15 ms of place recognition per KF.

The benchmark's mutex is uncontended. Contention in the live run is with `PropCount` calls from the same thread and the rare ROS-callback updates, so it is not expected to change the order of magnitude.

## Verdict
Clean. No change to the build, node or harness is needed. The batch started as pre-registered.

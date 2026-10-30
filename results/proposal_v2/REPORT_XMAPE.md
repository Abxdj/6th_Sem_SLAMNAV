# Part E report: low-overlap cross-map test (MH_02→MH_05, MH_01→MH_04, MH_01→MH_05)

**Date:** 2026-10-30.
- **Pre-registration:** PREREG Part E.
  - Selection rule `b96908c`, committed before any overlap was computed.
  - Pairs and design `aaf06b1`.
  - 9.5 h cap `b0f9e64`, pushed by the owner before the first run.
- **Analysis:** `tools/proposal_v2/analyze_xmap2.py results/proposal_v2/plans/XMAPE_pairs.json results/proposal_v2/xmapE_test_results.json`, exactly as committed (md5 `e1cc90d9…`). No `--max-block`; all 10 blocks completed.
- **Batch log:** `results/proposal_v2/XMAPE_TEST_batch.log`.

## Summary

**The primary test is positive.**
- Injection vs control, CMH stratified over the three pairs: χ² = 24.43, **p = 7.7 × 10⁻⁷**.
- Exact stratified test: **p = 1.8 × 10⁻⁷**.
- MH OR = ∞.
- The script prints both p-values rounded to 4 dp, as 0.0. The unrounded values above use the same statistics, recomputed outside the script.
- Injection vs load-only is identical, because load-only also merged 0/30.

| pair | control | load-only | injection | merges from our proposer |
|---|---|---|---|---|
| MH_02 → MH_05 | 0/10 | 0/10 | **10/10** | 9 (1 dbow2) |
| MH_01 → MH_04 | 0/10 | 0/10 | **5/10** | 5 |
| MH_01 → MH_05 | 0/10 | 0/10 | 0/10 | — |

**The pre-registered prediction fails overall.** All three pairs were applicable (control ≤ 5/10). It holds on MH0205 (d = 1.0) and MH0104 (d = 0.5) and **fails on MH0105 (d = 0.0)**. Part E's rule needs it to hold on every applicable pair.

**GT check.**
- 14 of 15 merges fall within 2 m / 45°.
- **1 merge is outside**: `XE_MH0205_r9_resnet18`, sourced from **DBoW2**, at **2.005 m**, 1.6°. It misses the pre-registered radius by 5 mm, at almost the same viewing angle. By the rule it is reported as outside the GT criterion. It is not a merge made by our proposer.
- All 14 merges made by our proposer are within the criterion.
- All 9 loops are within it (≤ 1.27 m, ≤ 9.2°).

**Merging did not reliably give a better map.**
- In 3 of the 5 MH0104 injection merges, session-2 ATE is 0.25–0.32 m. Unmerged runs median about 0.06 m.
- In 1 of the 10 MH0205 injection merges (r2), the spanning-map ATE is 0.40 m.
- The matched places are GT-correct, but the map after the merge was worse in these runs. This is descriptive; Part E pre-registers no ATE test.

## Deviation: batch interrupted by a watchdog bug (operational; no frozen item changed)
- **What happened:**
  - `run_batch.sh` has no time limit, so the 9.5 h cap was enforced by a separate watchdog process.
  - The first watchdog had a bug: an invalid `date` expression left its cap time empty, so it skipped its wait.
  - At 13:40, about 1 min after the batch started at 13:39:02, it killed the `run_batch.sh` loop.
- **Run 1 was unaffected.** Run 1 (`XE_MH0205_r1_none`) was in progress and kept running as an orphan. It completed normally at 13:44:01, with exit 0, trajectory saved and `[PROP-FINAL]` printed.
- **Resume:**
  - The batch was resumed at 13:41 with `plans/XMAPE_TEST_resume1.plan`. That is data lines 2–90 of `XMAPE_TEST.plan` in the same order, verified by `diff`. The original plan is unchanged.
  - `run_batch.sh` waits until no `rosmaster` is running before each run, so run 2 started at 13:44:08, after run 1 ended. There was never more than one ROS master.
- **Run 1's batch-log line:**
  - It was written afterwards by hand, using `run_batch.sh`'s own summary expression, and is marked as a recovery line with the run's real finish time.
  - It therefore appears after run 2's line in the log.
- **The fixed watchdog** was dry-run (cap time 23:09:02 and the process it would kill) before it was armed. It was never triggered: the batch ended at 21:57:33.

## Machine time and run health
- **Machine time:** 13:39:02 to 21:57:33, **8.3 h**, within the approved 9.5 h cap.
- **Frozen state:** `meta.txt` of all 90 runs shows:
  - `orbslam_sha=9aad4f8`, with an empty diff;
  - `node_md5=781802e9…`;
  - `node_args=_mode:=xmap _xmap_thresh:=0.8768`;
  - `lib_mtime` 11:16:45.
- **Trajectories:** saved in 90/90 runs, with 0 mid-run crashes.
- **Exit codes:**
  - 0: 80 runs.
  - 139: 10 runs, the known shutdown segfault.
- **`[PROP-FINAL]`:** printed in 89/90 runs. In `XE_MH0205_r3_resnet18` (exit 139) the segfault came after the trajectory was saved but before `[PROP-FINAL]`.
  - Its merge outcome comes from `mono.log` ("Merge finished", `[PROP] accepted`) and is unaffected.
  - Its proposal and timing counters come from the last periodic `[PROP-STATS]` line, so they may be slightly short of the full run.
- **Mono frame drops:** 0–0.02%. No timestamp errors; all pairs run forward in time.

## Primary and secondary tests

| comparison | tables (merged / not), per pair (MH0205; MH0104; MH0105) | CMH χ² | p | MH OR | exact stratified p |
|---|---|---|---|---|---|
| **injection vs control (primary)** | 10/0 vs 0/10; 5/5 vs 0/10; 0/10 vs 0/10 | 24.43 | **7.7e-7** | ∞ | **1.8e-7** |
| injection vs load-only | identical tables | 24.43 | 7.7e-7 | ∞ | 1.8e-7 |

**Sensitivity analysis on independent pairs only:** not applicable, because all three pairs are related.

MH0105 is non-informative (no merges in any arm). The pooled result rests on MH0205 and MH0104.

## Per pair

### MH_02 → MH_05 (overlap 0.140)

**Merges by arm**

| arm | merged | merge source | median ATE, session 1 / session 2 / spanning (m) | detect ms/KF, median | failed ext Sim3: attempts / ms |
|---|---|---|---|---|---|
| control | 0/10 | — | 0.038 / 0.058 / — | 4.44 | 0 / 0 |
| load-only | 0/10 | — | 0.037 / 0.055 / — | 4.90 | 0 / 0 |
| injection | 10/10 | ext 9, dbow2 1 | 0.038 / 0.062 / 0.071 | 4.52 | 261 / 727 |

**Tests and timing**
- Fisher, injection vs control: p = 1.1 × 10⁻⁵ (the script prints 0.0). The same against load-only.
- Time to first merge with injection: 31.3–32.0 s into session 2. Every control and load-only run is censored. MWU p = 0.0001 against both.
- Detect ms/KF: injection vs control p = 0.73; vs load-only p = 0.054 (injection is lower).

**Merge correctness**
- Our proposer's 9 merges are 1.36–1.98 m apart at 1.3–8.2°.
- The one DBoW2 merge, in an injection run (r9), is at 2.005 m and 1.6°, outside the radius (see Summary). DBoW2 merged in no run of the other two arms.

**ATE:** in one injection run (r2) the spanning-map ATE is 0.397 m and session 2 is 0.518 m. The other merged runs are 0.056–0.126 m.

**Proposals:** live precision vs GT = 114 / 334 = **0.34**.

| stage 0 (covisible-near) | stage 1 | stage 2 | stage 3 | verified |
|---|---|---|---|---|
| 64 | 3 | 192 | 66 | 9 |

### MH_01 → MH_04 (overlap 0.145)

**Merges by arm**

| arm | merged | merge source | median ATE, session 1 / session 2 / spanning (m) | detect ms/KF, median | failed ext Sim3: attempts / ms |
|---|---|---|---|---|---|
| control | 0/10 | — | 0.045 / 0.062 / — | 5.27 | 0 / 0 |
| load-only | 0/10 | — | 0.046 / 0.060 / — | 5.69 | 0 / 0 |
| injection | 5/10 | ext 5 | 0.046 / 0.065 / 0.225 | 5.56 | 492 / 1422 |

**Tests and timing**
- Fisher, injection vs control: p = 0.0325. MWU on merge counts: p = 0.014. The same against load-only.
- Time to first merge: 31.2–31.9 s in the 5 merged runs. MWU p = 0.015.
- Detect ms/KF: vs control p = 0.15; vs load-only p = 0.34.

**Merge correctness:** all 5 merges are 0.58–0.95 m apart at 21.2–27.9°.

**ATE after merging, per run**

| injection run | spanning ATE (m) | session-2 ATE (m) |
|---|---|---|
| r1 | 0.258 | 0.316 |
| r2 | 0.070 | 0.064 |
| r3 | 0.279 | 0.308 |
| r4 | 0.225 | 0.255 |
| r7 | 0.059 | 0.059 |

- Unmerged runs have a median session-2 ATE of about 0.06 m. One exception: unmerged injection run r10 is at 0.176 m.
- So 3 of the 5 GT-correct merges were followed by a substantially worse session-2 map.

**Proposals:** live precision = 309 / 531 = **0.58**.

| stage 0 | stage 1 | stage 2 | stage 3 | verified |
|---|---|---|---|---|
| 34 | 8 | 332 | 152 | 5 |

### MH_01 → MH_05 (overlap 0.166)

**Merges by arm:** 0/10 in all three arms.

| arm | detect ms/KF, median | failed ext Sim3: attempts / ms |
|---|---|---|
| control | 5.82 | 0 / 0 |
| load-only | 5.92 | 0 / 0 |
| injection | 6.11 | 672 / 1947 |

**Tests:** detect ms/KF, injection vs control MWU p = 0.011; vs load-only p = 0.054.

**Proposals:**
- Live precision = 355 / 672 = **0.53**. So 355 of our proposals pointed at the right place by GT, and none verified.
- Stages 2/3: 445 / 223. Stage 1: 4. Verified: 0.

**Why the prediction fails here:** proposing the right place was not enough; geometric verification never passed on this pair.

### Prediction (pre-registered)

| pair | control rate | injection rate | d | applicable (control ≤ 5/10) | result |
|---|---|---|---|---|---|
| MH0205 | 0.0 | 1.0 | 1.0 | yes | holds |
| MH0104 | 0.0 | 0.5 | 0.5 | yes | holds |
| MH0105 | 0.0 | 0.0 | 0.0 | yes | **fails** |
| **overall** | | | | | **fails** (it must hold on every applicable pair) |

## GT check of every merge and loop (all arms)
- Merges: 15. 14 are within 2 m / 45°. One DBoW2 merge is at 2.005 m and 1.6°, outside.
- Loops: 9, all within (≤ 1.27 m, ≤ 9.2°).
- Per-match values are in `xmapE_test_results.json` → `pairs.*.runs.*.accepted[].gt_dist_ang`. The script rounds them to 2 dp, so the 2.005 m value was recomputed unrounded with the script's own `gt_pose` / `kf_stamps`.

## What this changes
- **Part B plus Part E:** on 3 of the 4 low-overlap MH pairs (MH_02→MH_04, MH_02→MH_05, MH_01→MH_04), DBoW2 alone rarely or never merged, and injection did: 9/10, 10/10 and 5/10. With Part C's null result at the ceiling, the picture is consistent: the proposer adds merges only where DBoW2's own proposals fail.
- **Limits:**
  - All four low-overlap pairs revisit the **same place**: the start area of MH_04 / MH_05, as noted in Part E. So this is one place tested with different session pairings, not several places.
  - All pairs are related.
  - The fourth pair (MH0105) shows a case where correct proposals never verify.
  - Merges did not reliably improve the map: in 4 of 15 merged injection runs, map error rose a lot after merging.
- **Untested:** whether any of this transfers to a different environment. Part D (V1_01 → V1_03), the only independent pair, has not run; its download is incomplete.

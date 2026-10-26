# Part C report: cross-map test on MH_03→MH_05 and MH_04→MH_02

**Date:** 2026-10-26.
- Pre-registration: PREREG Part C (commit `b830bee`).
- Analysis: `tools/proposal_v2/analyze_xmap2.py results/proposal_v2/plans/XMAP2_pairs.json results/proposal_v2/xmap2_test_results.json`, exactly as committed. There was no `--max-block`, because all 10 blocks completed.
- Raw output: `results/proposal_v2/xmap2_test_results.json`.
- Batch log: `results/proposal_v2/XMAP2_TEST_batch.log`.
- Smoke run: `results/proposal_v2/XMAP2_SMOKE.md`.

## Summary

**The primary test is null.**
- Injection vs control, CMH stratified by pair: χ² = 2.11, **p = 0.146**.
- Exact stratified test: **p = 0.474**.
- MH common OR = ∞, because no injection run failed to merge.

**Why there is no room for an effect.** Control already merged in **8/10** runs (MH_03→MH_05) and **10/10** runs (MH_04→MH_02). These pairs have high overlap, chosen deliberately, and at that overlap DBoW2 merges by itself.

**The pre-registered prediction holds in both pairs** (d ≤ 0.2 where the control rate is ≥ 0.8). Both pairs fell in the high-control band, so the half of the prediction that says the effect is large where control rarely merges was **not tested** here. The only evidence for that half is Part B, MH_02→MH_04: control 4/10, injection 9/10.

**Correctness.**
- Every accepted merge and loop in every arm is GT-correct at 2 m / 45°: 57 merges and 19 loops.
- The 9 merges that came from our proposer are correct too.
- Wrong proposals never caused a wrong merge.

**Cost.** Injection adds measurable place-recognition time:
- **+0.56 ms per KF** on MH_03→MH_05 (median 3.78 vs 3.22 ms, MWU p = 0.0002);
- **+0.20 ms per KF** on MH_04→MH_02 (3.31 vs 3.10 ms, p = 0.0006).

This comes from Sim3 attempts on our candidates that did not verify: 862 attempts and 2.77 s over 10 runs on MH0305, and 193 attempts and 0.78 s on MH0402.

## Machine time and run health
- **Machine time:** smoke 15:27–15:32, batch 15:32:35–20:33:06. About **5.1 h** in total, within the ~8 h approved.
- **Frozen state, from `meta.txt` of all 60 runs:**
  - `orbslam_sha=9aad4f8`;
  - empty ORB-SLAM3 diff;
  - `node_md5=781802e9…`;
  - `lib_mtime` 11:16:45.
- **Shutdown:** `[PROP-FINAL]` printed and trajectory saved in **60/60** runs. 0 mid-run crashes.
- **Exit codes:**
  - 0: 45 runs.
  - 139: 13 runs, the known shutdown segfault, after the save.
  - 133: 2 runs (`X2_MH0305_r2_load_only`, `X2_MH0402_r2_load_only`). This is a GTK `BadWindow` X error raised by the viewer during shutdown. In `mono.log` it comes after both "Saving … trajectory" and `[PROP-FINAL]`, so the data are unaffected. It is a new shutdown failure mode, both in the same block and arm, and is reported, not replaced.
- **"timestamp older than previous frame" errors on MH_04→MH_02:** **0** in all 30 runs. The reversed-timestamp handling via `ChangeDataset` works as described in Part C.
- **Mono frame drops:** 0–0.16% per run.
- **Disk:** 24 GB free at the end.

## Primary and secondary tests (pooled over both pairs)

| comparison | tables (merged / not), per pair | CMH χ² | p | MH OR | exact stratified p |
|---|---|---|---|---|---|
| **injection vs control (primary)** | MH0305 10/0 vs 8/2; MH0402 10/0 vs 10/0 | 2.111 | **0.146** | ∞ | **0.474** |
| injection vs load-only | MH0305 10/0 vs 9/1; MH0402 10/0 vs 10/0 | 1.000 | 0.317 | ∞ | 1.000 |

**Sensitivity analysis on independent pairs only:** not applicable. Part C has no independent pair; V1_01→V1_03 is deferred to Part D, as pre-registered.

MH0402 is a non-informative stratum (every run merged in both arms), so the pooled test rests entirely on MH0305.

## Per pair

### MH_03 → MH_05

**Merge counts by arm**

| arm | merged | merge source | median ATE, session 1 / session 2 / spanning map (m) | detect ms/KF, median | failed ext Sim3: attempts / ms |
|---|---|---|---|---|---|
| control | 8/10 | dbow2 8 | 0.040 / 0.059 / 0.060 (n=8) | 3.22 | 0 / 0 |
| load-only | 9/10 | dbow2 9 | 0.042 / 0.075 / 0.075 (n=9) | 3.30 | 0 / 0 |
| injection | 10/10 | **ext 5**, dbow2 5 | 0.042 / 0.066 / 0.071 (n=10) | 3.78 | 862 / 2768 |

**Merge tests**

| comparison | Fisher p | MWU p, merge counts |
|---|---|---|
| injection vs control | 0.474 | 0.168 |
| injection vs load-only | 1.000 | 0.368 |

**Time to first merge** (s into session 2; never-merged runs censored)

| arm | times |
|---|---|
| control | 24.9, 24.9, 26.1, 26.6, 27.7, 27.7, 107.3, 107.3, cens, cens |
| load-only | 25.0, 25.3, 25.3, 25.8, 25.8, 25.8, 26.1, 26.1, 26.6, cens |
| injection | 24.9, 24.9, 25.0, 25.6, 25.7, 25.8, 26.0, 26.0, 26.0, 26.2 |

- Injection vs control: MWU **p = 0.020**.
- Injection vs load-only: MWU p = 0.341.

**Interpretation of time to first merge.** The p = 0.020 is driven by four control runs:
- two never merged;
- two merged only at the 107 s revisit, having missed the first revisit at about 25 s.

Load-only made the first revisit in 9/10 runs, and injection vs load-only shows no difference. So these data don't separate "injection makes the first revisit merge happen" from control-arm chance. The control arm runs without the GPU/ROS load, so the two arms differ in timing as well as in the proposer.

This is one of several secondary comparisons with no multiplicity correction (Part C §α), and I don't read it as evidence for the proposer.

**Ext-attributed merges** (r3, r6, r8, r9, r10): all GT-correct, at 0.67–1.21 m and 5.8–25.2°. They occurred at 25.6–26.2 s into session 2, the same revisit where DBoW2 merges in the other runs (24.9–26.6 s). So "src=ext" mostly means our candidate verified first at a revisit DBoW2 also catches. It does not mean a merge DBoW2 would have missed.

**Live proposal precision (2 m / 45°):** 798 / 1104 = **0.72**.

### MH_04 → MH_02

**Merge counts by arm**

| arm | merged | merge source | median ATE, session 1 / session 2 / spanning map (m) | detect ms/KF, median | failed ext Sim3: attempts / ms |
|---|---|---|---|---|---|
| control | 10/10 | dbow2 10 | 0.061 / 0.042 / 0.067 | 3.10 | 0 / 0 |
| load-only | 10/10 | dbow2 10 | 0.063 / 0.039 / 0.087 | 3.09 | 0 / 0 |
| injection | 10/10 | **ext 4**, dbow2 6 | 0.059 / 0.055 / 0.100 | 3.31 | 193 / 776 |

**Merge tests**
- Fisher p = 1.0 and MWU p = 1.0 against both control and load-only.

**Time to first merge:** 55.7–56.7 s in every run of every arm.
- Injection vs control: MWU p = 0.078.
- Injection vs load-only: p = 0.634.

All 30 merges come at the same revisit, 0.59–1.47 m and 30.7–34.8° apart. That is close to the 45° limit, but within it.

**Ext-attributed merges** (r1, r4, r6, r7): all GT-correct.

**Spanning-map ATE:** injection's median, 0.100 m, is higher than control's 0.067 m. This is descriptive only; Part C pre-registers no ATE test. ATE did not improve in Part B either.

**Live proposal precision:** 478 / 663 = **0.72**.

### Prediction (pre-registered)

| pair | control rate | injection rate | d | band | result |
|---|---|---|---|---|---|
| MH0305 | 0.8 | 1.0 | 0.2 | high (≥ 0.8) | **holds** (d ≤ 0.2) |
| MH0402 | 1.0 | 1.0 | 0.0 | high | **holds** |

The low band (control ≤ 0.5, prediction d ≥ 0.3) had no pair in Part C.

## GT check of every merge and loop (all arms)

- Each match was checked with the stamps of the matched KF and the current KF from `kf_log.csv`, against the concatenated GT.
- 57/57 merges and 19/19 loops fall within 2 m / 45°:
  - maximum distance 1.56 m for a merge, 1.79 m for a loop;
  - maximum angle 35.4° (a merge).
- The per-match values are in `xmap2_test_results.json` → `pairs.*.runs.*.accepted[].gt_dist_ang`.

## Proposal outcomes, injection arm (sum over 10 runs, MH0305)

**Totals**
- Received: 1106.
- Dropped as duplicates of a DBoW2 candidate: 43.

**Outcome of each external candidate**

| stage | outcome | count | time |
|---|---|---|---|
| 0 | aborted as covisible-near | 196 | — |
| 1 | BoW fail | 2 | — |
| 2 | RANSAC not converged | 544 | 1.01 s |
| 3 | converged but rejected later | 316 | 1.76 s |
| 4 | verified (5 accepted as merges) | 5 | — |

- Stage-2 and stage-3 rejections carry almost all of the injection cost: 2.77 s over 10 runs, or 0.28 s per run in a session about 270 s long.
- MH0402 per-stage totals are in the JSON, under `injection_outcomes_total`.

## What this changes

Part B showed the proposer adds merges where DBoW2 often fails: MH_02→MH_04, control 4/10, injection 9/10.

Part C shows that on high-overlap pairs, where DBoW2 already merges 80–100% of the time:
- the proposer adds nothing to the merge rate;
- it causes no wrong merges;
- it costs 0.2–0.6 ms per KF of extra place-recognition time.

That fits the pre-registered prediction. But Part C was designed to test that prediction in both bands, and only the "near zero at ceiling" half got tested. A positive effect still rests on one pair, MH_02→MH_04 (Part B).

**Part D (V1_01→V1_03, independent)** is the remaining pre-registered route to a second low-control pair. Whether it is low-control can only be known after its control arm runs.

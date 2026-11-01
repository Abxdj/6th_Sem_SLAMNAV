# Part D report: independent-pair cross-map test (V1_01 → V1_03)

**Date:** 2026-11-01.
- **Pre-registration:** PREREG Part D, `5e78d8b`, pushed by the owner before the first run.
- **Analysis:** `tools/proposal_v2/analyze_xmap2.py results/proposal_v2/plans/XMAPD_pairs.json results/proposal_v2/xmapD_test_results.json`, exactly as committed (md5 `e1cc90d9…`). No `--max-block`; all 10 blocks completed.
- **Batch log:** `results/proposal_v2/XMAPD_TEST_batch.log`.

## Summary

**The primary test is not significant.**
- Injection vs control (CMH, one stratum): χ² = 3.35, **p = 0.067**, MH OR = ∞.
- Exact test (Fisher, the pre-registered sensitivity analysis): **p = 0.21**.
- The independent-pairs-only analysis is the same table, so the same result.

| arm | merged (≥ 1 `Merge finished`) | merge source (merges) |
|---|---|---|
| control | 7/10 | dbow2 8 |
| load-only | 6/10 | dbow2 6 |
| injection | **10/10** | ext 7, dbow2 7 |

**The pre-registered prediction is uninformative here.** Control merged 7/10 (rate 0.7), which is in the 0.6–0.7 band that the Part C rule defines as uninformative. d = 0.3.

**GT check.**
- All 28 merges in all arms are within 2 m / 45° (≤ 1.34 m, ≤ 31.9°).
- 7 of 38 loops are outside on angle only (48.0–56.5°, ≤ 1.18 m). **All 7 are DBoW2 loops**: 4 control, 1 load-only, 2 injection.
- All 11 matches made by our proposer (7 merges, 4 loops) are within the criterion.

**A caveat about the primary outcome (descriptive; see below).** V1_03 tracking repeatedly failed and restarted, so ORB-SLAM3 made 2–4 maps per run. Most control and load-only merges join two pieces of the V1_03 session to each other, not V1_03 to the V1_01 map. The pre-registered outcome counts any merge, so it does not measure what the test was meant to measure on this pair. A post hoc breakdown is reported separately below.

## Machine time and run health
- **Machine time:** 14:50:52 to 17:22:06, **2.5 h**, within the approved 4 h cap. The watchdog (dry-run before arming, cap 18:50:52) was never triggered.
- **Frozen state:** `meta.txt` of all 30 runs shows:
  - `orbslam_sha=9aad4f8`, with an empty diff;
  - `node_md5=781802e9…`;
  - `node_args=_mode:=xmap _xmap_thresh:=0.8768`;
  - `load_kf_hz=3.55`;
  - `lib_mtime` 2026-10-26 11:16:45, `mono_mtime` 11:17:21;
  - `repo_sha=5e78d8b`. `repo_dirty=1`, as in all 90 Part E runs: there are untracked files only.
- **Exit codes:** 0 in 27 runs; 139 in 2 (`r1_none`, `r1_load_only`, the known shutdown segfault, after the trajectory was saved); **134 in 1**.
- **Mid-run crash, `XD_V0103_r4_resnet18`:**
  - It aborted on a Sophus check: `SO3::exp failed! omega: -nan -nan -nan`.
  - This came after its one merge (an external merge at 52.0 s into session 2) and after the publisher logged "all done", but before shutdown. No trajectory was saved.
  - Per PREREG it is reported, not replaced. Its merge counts toward the primary outcome, which comes from `mono.log`. It has no ATE.
  - Its proposal counters come from the last periodic `[PROP-STATS]` line, before the merge, so they are short. For example, its verified external candidate is missing from the stage table below.
- **`XD_V0103_r7_load_only` is not a crash, although the script counts it as one.**
  - It exited 0 and wrote `[PROP-FINAL]`. It saved `KeyFrameTrajectory_allmaps.txt` (670 KFs), which is what the ATE uses.
  - Only `KeyFrameTrajectory.txt`, the current map at shutdown, is empty: tracking had just been lost and a new, empty map started.
  - The script's crash flag and the batch log's `traj=NO` both look only at that file. So the load-only arm's `midrun_crashes: 1` in `xmapD_test_results.json` is this run.
- **3 consecutive crashes:** never reached.
- **Mono frame drops:** 0–0.36%.
- **No timestamp errors.** The pair runs forward in time.

## Primary and secondary tests

| comparison | table (merged / not) | CMH χ² | p | MH OR | exact p |
|---|---|---|---|---|---|
| **injection vs control (primary)** | 10/0 vs 7/3 | 3.353 | **0.067** | ∞ | **0.21** |
| injection vs load-only | 10/0 vs 6/4 | 4.750 | 0.029 | ∞ | 0.087 |

**Secondary tests**
- Fisher, injection vs control: p = 0.21. Against load-only: p = 0.087.
- MWU on merge counts: vs control p = 0.043; vs load-only p = 0.0067.
- Time to first merge into session 2: vs control p = 0.10; vs load-only p = 0.32.
  - Injection: 13.9–89.3 s, all 10 merged.
  - Control: 13.8–60.1 s in 7 runs; 3 censored.
- Detect ms per KF, median: injection 3.94, control 3.39 (p = 0.0004), load-only 3.54 (p = 0.0091). That is about **+0.4–0.5 ms per KF**.

α = 0.05 is descriptive. At that level these secondary comparisons pass: CMH and MWU against load-only, MWU on merge counts against control, and the detect-time differences. The primary test does not.

## Per arm

| arm | median ATE, session 1 / session 2 (m) | session-2 ATE range (m) | runs with a map spanning both sessions | median spanning ATE (m) |
|---|---|---|---|---|
| control | 0.095 / 0.069 | 0.062–0.207 | 2 | 0.151 |
| load-only | 0.095 / 0.119 | 0.062–1.040 | 3 | 0.414 |
| injection | 0.096 / 0.165 | 0.064–0.678 | 8 (+ r4, which crashed with no trajectory) | 0.141 |

- **ATE after merging is mixed.** Spanning-map ATE across the 8 injection runs is 0.083–0.688 m. It is high in r6 (0.688 m), r2 (0.381 m) and r7 (0.330 m). It also varies widely in the other arms; load-only r2 is at 0.914 m. As in Part E, this is descriptive; no ATE test is pre-registered.
- **Our proposer's candidates (injection arm, 10 runs):**

  | stage 0 (covisible-near) | stage 1 | stage 2 | stage 3 | verified¹ |
  |---|---|---|---|---|
  | 186 | 29 | 684 | 358 | 10 |

  ¹ *Post hoc note.* The table shows 10 verified, but 11 external matches were accepted (7 merges, 4 loops). The gap is r4: it aborted before `[PROP-FINAL]`, so its counters come from its last periodic `[PROP-STATS]` line (`mono.log:1594`). That line was printed before its external merge was verified (`Merge finished` at `mono.log:1617`). So r4's verified candidate is in the accepted list but not in the stage counts. Its other stage counts are short for the same reason.
  - Sim3 cost of failed external candidates: 1,071 attempts, 3,593 ms in total over 10 runs, about 0.36 s per run.
- **Live proposal precision vs GT: 1,368 / 1,427 = 0.96.** This is about the pair's overlap (0.962), so on this pair it says little about the descriptor: almost any session-2 KF has a correct session-1 place.

## Crash sensitivity and GT confirmation (POST HOC, added after the results)

**How r4 is scored.** PREREG's crash rule says crashed runs are "reported, not replaced". It does not say how they are scored, so the committed analysis decides:
- **Merge table:** r4 is in the injection arm's n = 10 and counts as merged. Its `Merge finished` (`mono.log:1617`) comes before the abort (`mono.log:1636`).
- **ATE:** r4 is excluded, because no trajectory was saved. Injection ATE values use 9 runs.

**Sensitivity: r4 scored as not merged.**
- Injection becomes 9/10 vs control's 7/10.
- With the committed functions, the exact test gives **p = 0.58** (the same as Fisher, two-sided), and the CMH test gives χ² = 1.19, p = 0.28.
- The primary conclusion (not significant) does not depend on how r4 is scored.

**GT check of every merge and loop in every arm (2 m / 45°), confirmed.**
- **Coverage:** every accepted match in all 30 runs has a GT distance and angle, from `kf_log.csv` stamps. None is missing, crashed r4 included.
- **The log agrees:** in every run, the `Merge finished` and `*Loop detected` lines in `mono.log` match the accepted merge and loop records one for one, 28 merges and 38 loops in total.
- **Merges: 28/28 are within the criterion** (≤ 1.34 m, ≤ 31.9°): control 8, load-only 6, injection 14. **No wrong merge was accepted in any arm.**
- **Loops: 31/38 are within; 7 are outside, on angle only** (48.0–56.5°, ≤ 1.18 m). All 7 are DBoW2 loops: 4 control, 1 load-only, 2 injection. They are reported as outside the GT criterion.
- **Our proposer:** all 11 accepted matches (7 merges, 4 loops) are within the criterion.

## Descriptive breakdown: which merges join V1_03 to V1_01 (POST HOC, not pre-registered)

The pre-registered outcome cannot tell a merge that joins the two sessions apart from a merge between two pieces of session 2. This breakdown was made after the results were seen. It is labelled post hoc and does not replace the primary test.

**Method:** a merge is **cross-session** if its matched KF's stamp, from `kf_log.csv`, falls in session 1. Otherwise it is a **fragment merge**: both KFs are in session 2.

| arm | runs with ≥ 1 cross-session merge | cross-session merges (source) | fragment merges (source) |
|---|---|---|---|
| control | **2/10** | 2 (dbow2) | 6 (dbow2) |
| load-only | **3/10** | 3 (dbow2) | 3 (dbow2) |
| injection | **9/10** | 9 (ext 6, dbow2 3) | 5 (dbow2 4, ext 1) |

- **Cross-check:** a map spanning both sessions at the end of the run was found in exactly the runs with a cross-session merge: 2 control, 3 load-only, 8 injection. The 9th injection run is r4, which crashed before saving.
- **Who made the cross-session merges in the injection arm:**
  - In 6 of the 9 runs, the cross-session merge was made by our proposer.
  - In 3 (r2, r3, r5), it was DBoW2's own merge at about 14 s into session 2. That is the same early place where 2 control and 3 load-only runs merged.
  - Our proposer's cross-session merges came at 14.2, 22.9, 52.0, 87.5, 89.3 and 89.4 s.
- **Post hoc Fisher, for information only:**
  - injection 9/10 vs control 2/10: p = 0.0055;
  - vs load-only 3/10: p = 0.020.

  These are not pre-registered tests and are not evidence in the sense of PREREG. Any claim built on them needs a new pre-registered test, with the cross-session outcome defined in advance.

## What this changes
- **On the pre-registered test, Part D is null.**
  - The one independent pair gave p = 0.067 (exact p = 0.21).
  - The prediction was uninformative, because control fell in the middle band.
- **What it does not do:** it does not replicate Parts B and E on an independent pair under the pre-registered outcome. Nothing should be pooled with Parts C or E, as registered.
- **The descriptive picture differs from the primary outcome.**
  - Counted as joins of V1_03 to V1_01, injection did so in 9/10 runs, against 2/10 for control and 3/10 for load-only.
  - That is post hoc. It is driven by V1_03's tracking failures, which made the "any merge" outcome mostly measure fragment re-merging in the control arm.
- **Cost:** about +0.5 ms per KF for place recognition, and 0.36 s per run of failed external Sim3.
- **Map quality after merging:** not reliably better, as in Part E.
- **Open question:** whether Parts B, C and E's merges include fragment merges was not checked. MH runs also create more than one map per run, for example 4 map creations in `XE_MH0205_r1_none`. Checking this would be a post hoc analysis of those parts, and is not done here.

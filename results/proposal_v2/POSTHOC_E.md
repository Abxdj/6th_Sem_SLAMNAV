# POST HOC analyses of Part E (not pre-registered)

**Status:** everything in this file is **post hoc**. It was asked for by the owner on 2026-10-31, after the Part E results (`c3cfff0`) were pushed.
- No test here was pre-registered, so no p-values are given.
- It changes no pre-registered report: `REPORT_XMAPE.md`, `xmapE_test_results.json` and PREREG are untouched.
- It reads only the existing Part E run directories. Nothing was re-run.

**Script and output**
- Script: `tools/proposal_v2/posthoc_e.py`, new. It imports `umeyama_sim3` from `analyze_pv2.py` and `kf_stamps` / `gt_pose` from `analyze_xmap2.py`, unchanged.
- Output: `results/proposal_v2/posthoc/posthoc_e.json`.
- Run: `python3 tools/proposal_v2/posthoc_e.py results/proposal_v2/plans/XMAPE_pairs.json results/proposal_v2/posthoc/posthoc_e.json`.

**Not measured.** Two things asked for are not in the logs.
1. **Sim3 inlier counts of accepted merges.** Neither `[PROP] accepted` nor `[PROP] geom_pass` prints `numOptMatches` or `numProjOptMatches`.
2. **Which check failed inside verification stage 3.** `src/LoopClosing.cc` sets one stage value for all four checks after Sim3 converges:
   - projection matches < 50;
   - optimised Sim3 inliers < 20;
   - guided re-projection matches < 80;
   - fewer than 3 covisible KFs agreeing.

So "Sim3 inliers vs guided matching" can only be split into the two levels the log records. Separating them needs a logging change to the frozen build, which needs a dated amendment.

## 1. MH_01 → MH_05: where did our GT-correct proposals fail?

**Stages** (from the C5 `[PROP]` log lines; the numbering is the C7 one):

| stage | meaning |
|---|---|
| 0 | covisible with the current KF; discarded before any geometry |
| 1 | fewer than 20 BoW matches |
| 2 | ≥ 20 BoW matches, but Sim3 RANSAC did not converge (fewer than 15 inliers in 300 iterations) |
| 3 | Sim3 converged, then one of the four later checks failed (projection, optimised inliers, guided re-projection, covisibility consistency) |
| 4 | fully verified |

**Method**
- **GT-correct** means distance < 2 m and angle < 45° between the candidate KF and the current KF, unrounded, from `kf_log.csv` stamps and the concatenated GT.
- These counts are of **evaluations**, one per (candidate, current KF) pair the loop closer tested. They are not the node's proposals, so they differ slightly from the live-precision numbers in the report (e.g. MH0105: 359 here vs 355).
- **Check:** for every pair and stage, the stage totals equal the run counters `n_ext_stage0–4` summed over the 10 injection runs. For example, MH0105 stage 2 is 185 + 260 = 445 and stage 3 is 174 + 49 = 223.

### Stage of every evaluated external candidate, injection arm (10 runs per pair)

| pair | GT-correct evaluations | stage 0 | stage 1 | stage 2 (Sim3 RANSAC) | stage 3 (after Sim3) | stage 4 (verified) |
|---|---|---|---|---|---|---|
| MH0205 | 115 | 53 | 0 | 25 | 28 | **9** |
| MH0104 | 302 | 12 | 0 | 166 | 119 | **5** |
| **MH0105** | **359** | 0 | 0 | **185** | **174** | **0** |

| pair | GT-wrong evaluations | stage 0 | stage 1 | stage 2 | stage 3 | stage 4 |
|---|---|---|---|---|---|---|
| MH0205 | 219 | 11 | 3 | 167 | 38 | 0 |
| MH0104 | 229 | 22 | 8 | 166 | 33 | 0 |
| MH0105 | 313 | 0 | 4 | 260 | 49 | 0 |

**MH0105: what we can say**
- None of the GT-correct proposals failed at BoW: every one had at least 24 matches.
- About half failed Sim3 RANSAC (185, stage 2). The other half had Sim3 converge and then failed a later check (174, stage 3), but we can't tell which check.
- Of the GT-correct evaluations that reached geometry (stage ≥ 2), the share that verified was:
  - MH0205: 9/62 = 15%;
  - MH0104: 5/290 = 1.7%;
  - MH0105: 0/359.
- **No GT-wrong evaluation verified on any pair.** That is 761 in total, 713 of which got past BoW.

### Distance and angle of GT-correct candidates vs the merges that passed

| set | n | distance m, min / median / max | angle °, min / median / max | BoW matches, median |
|---|---|---|---|---|
| MH0205: verified (stage 4) | 9 | 1.36 / 1.67 / 1.98 | 1.3 / 4.4 / 8.3 | not logged for stage 4 |
| MH0104: verified (stage 4) | 5 | 0.58 / 0.65 / 0.95 | 21.2 / 22.6 / 27.9 | not logged |
| MH0105: GT-correct, stage 2 | 185 | 0.85 / 1.62 / 2.00 | 2.7 / 12.3 / 44.7 | 46 |
| MH0105: GT-correct, stage 3 | 174 | 0.75 / 1.57 / 2.00 | 0.8 / 12.5 / 34.8 | 60 |
| MH0205: GT-correct, stage 3 (for reference) | 28 | 1.41 / 1.65 / 1.99 | 1.5 / 11.3 / 35.3 | 76 |
| MH0104: GT-correct, stage 3 (for reference) | 119 | 0.50 / 1.11 / 1.98 | 1.3 / 22.8 / 36.0 | 79 |

**Inside the ranges of the merges that passed**

| range | pair | evaluations | stage 0 / 2 / 3 / 4 | BoW median |
|---|---|---|---|---|
| MH0205's verified range (1.36–1.98 m, 1.3–8.3°) | MH0205 | 43 | 12 / 12 / 12 / **7** | 51.5 |
| | MH0104 | 50 | 2 / 36 / 12 / **0** | 49 |
| | MH0105 | 18 | 0 / 9 / 9 / **0** | 49 |
| MH0104's verified range (0.58–0.95 m, 21.2–27.9°) | MH0104 | 35 | 3 / 0 / 27 / **5** | 93 |
| | MH0205, MH0105 | 0 | — | — |

**Reading** (post hoc, descriptive):
- MH0105's GT-correct proposals were not further away or more oblique than the ones that passed. Their median, 1.6 m and 12°, lies between the two passing groups.
- Distance and angle alone don't predict verification. Within MH0205's passing range:
  - MH0205's own candidates verified 7 of 31 times once they reached geometry;
  - MH0104's verified 0 of 48;
  - MH0105's verified 0 of 18.
- On MH0104, all 5 passes come from one narrow pose range (0.6–1.0 m, 21–28°) with high BoW counts (median 93). MH0105 never proposed a pair in that range.
- What makes a pair pass seems to depend on the specific image pair. Distance and angle are too coarse to capture it.
- Because the logs don't split stage 3, we can't say which of the four checks after Sim3 rejected MH0105's 174 stage-3 candidates.

## 2. Merged injection runs: degraded vs good

**Groups**
- **Degraded (4):** the runs named in `REPORT_XMAPE.md`: MH0205 r2, MH0104 r1, r3, r4.
- **Good (11):** the other merged injection runs: MH0205 r1, r3–r10 (r9's merge came from DBoW2) and MH0104 r2, r7.
- The split is post hoc, by the ATE values already reported.

**Metrics**
- **s1-anchored error:** one Sim3 is fitted to the **session-1** KFs of the final spanning map and applied to all KFs. Session-2 error is then reported in time windows relative to the merge KF. This shows where session 2 departs from the frame of session 1.
- **Own-fit:** a separate Sim3 is fitted to session-2 KFs **before** and **after** the merge. This measures each segment's shape error and its scale.
- **Caveat:** only the final trajectory is saved, so all of this is in the **post-merge, post-optimisation** map. There is no snapshot of the map just after the merge.

### Merge pair, and error around the merge

| run | group | merge source | merge dist m / angle ° | merge at s into s2 | s1-anchored error, s2 before merge | 0–5 s after | 5–20 s after | 20 s → end | own-fit pre / post merge | own-fit scale pre → post |
|---|---|---|---|---|---|---|---|---|---|---|
| MH0205 r2 | **degraded** | ext | 1.95 / 1.5 | 31.4 | 0.235 | **0.041** | 0.138 | **0.842** | 0.019 / **0.560** | 1.379 → 1.336 |
| MH0104 r1 | **degraded** | ext | 0.63 / 22.6 | 31.9 | 0.184 | **0.035** | **0.462** | **0.668** | 0.020 / **0.252** | 4.070 → 4.331 |
| MH0104 r3 | **degraded** | ext | 0.65 / 27.9 | 31.6 | 0.102 | **0.037** | **0.514** | **0.817** | 0.012 / **0.250** | 4.115 → 4.011 |
| MH0104 r4 | **degraded** | ext | 0.95 / 21.2 | 31.2 | 0.042 | **0.039** | **0.421** | **0.646** | 0.011 / **0.205** | 3.879 → 3.909 |
| MH0104 r2 | good | ext | 0.65 / 27.9 | 31.6 | 0.093 | 0.044 | 0.087 | 0.192 | 0.012 / 0.068 | 4.092 → 4.112 |
| MH0104 r7 | good | ext | 0.58 / 21.4 | 31.7 | 0.081 | 0.037 | 0.079 | 0.147 | 0.013 / 0.058 | 3.867 → 3.844 |
| MH0205 r1 | good | ext | 1.77 / 2.2 | 31.5 | 0.086 | 0.032 | 0.090 | 0.177 | 0.015 / 0.057 | 1.409 → 1.415 |
| MH0205 r3 | good | ext | 1.51 / 6.0 | 31.8 | 0.089 | 0.033 | 0.056 | 0.134 | 0.013 / 0.055 | 1.439 → 1.436 |
| MH0205 r4 | good | ext | 1.36 / 6.1 | 31.9 | 0.078 | 0.027 | 0.096 | 0.247 | 0.014 / 0.058 | 1.373 → 1.372 |
| MH0205 r5 | good | ext | 1.49 / 1.9 | 32.0 | 0.053 | 0.036 | 0.031 | 0.125 | 0.013 / 0.058 | 1.418 → 1.416 |
| MH0205 r6 | good | ext | 1.68 / 8.2 | 31.6 | 0.091 | 0.038 | 0.152 | 0.296 | 0.016 / 0.066 | 1.390 → 1.393 |
| MH0205 r7 | good | ext | 1.36 / 4.4 | 31.9 | 0.098 | 0.037 | 0.080 | 0.151 | 0.016 / 0.055 | 1.393 → 1.396 |
| MH0205 r8 | good | ext | 1.98 / 5.7 | 31.4 | 0.076 | 0.043 | 0.052 | 0.148 | 0.013 / 0.052 | 1.411 → 1.411 |
| MH0205 r9 | good | dbow2 | 2.005 / 1.6 | 31.3 | 0.136 | 0.039 | 0.087 | 0.213 | 0.015 / 0.062 | 1.386 → 1.398 |
| MH0205 r10 | good | ext | 1.77 / 1.3 | 31.5 | 0.283 | 0.039 | 0.117 | 0.211 | 0.031 / 0.094 | 1.321 → 1.393 |

**Columns:** error columns are RMSE in m. The ATE scale differs per pair because each monocular map has its own arbitrary scale.

**s1-anchored error over time, in 10 s bins relative to the merge (m)**

| run | −30 | −20 | −10 | 0 | +10 | +20 | +30 | +40 | +50 | +60 |
|---|---|---|---|---|---|---|---|---|---|---|
| MH0104 r1 (degraded) | 0.27 | 0.27 | 0.12 | 0.18 | 0.54 | 0.78 | 0.87 | 0.50 | 0.22 | 0.26 |
| MH0104 r3 (degraded) | 0.13 | 0.13 | 0.09 | 0.22 | 0.58 | 1.03 | 1.07 | 0.50 | 0.12 | 0.13 |
| MH0104 r4 (degraded) | 0.04 | 0.04 | 0.04 | 0.14 | 0.49 | 0.77 | 0.84 | 0.50 | 0.09 | 0.05 |
| MH0104 r2 (good) | 0.14 | 0.14 | 0.06 | 0.07 | 0.09 | 0.22 | 0.24 | 0.14 | 0.10 | 0.14 |
| MH0104 r7 (good) | 0.10 | 0.11 | 0.07 | 0.05 | 0.09 | 0.16 | 0.17 | 0.13 | 0.08 | 0.11 |
| MH0205 r2 (degraded) | 0.29 | 0.30 | 0.18 | 0.08 | 0.15 | 0.47 | 1.05 | 1.45 | 0.30 | 0.16 |
| MH0205 r6 (good) | 0.12 | 0.12 | 0.07 | 0.08 | 0.17 | 0.35 | 0.43 | 0.30 | 0.11 | 0.11 |
| MH0205 r8 (good) | 0.09 | 0.10 | 0.05 | 0.05 | 0.05 | 0.18 | 0.19 | 0.15 | 0.08 | 0.07 |

All 15 curves are in `posthoc_e.json` → `merged_runs.*.s1_anchored_curve`.

**Comparison: session 2 without a merge.** All control, load-only and unmerged injection runs: own-fit RMSE of the session-2 segment after a nominal 31.5 s.
- MH0205: 20 runs, median 0.054, maximum 0.118.
- MH0104: 25 runs, median 0.063, maximum 0.168. The maximum is the unmerged injection run r10.

**Reading** (post hoc, descriptive):
1. **The merge itself was accurate in all 15 runs.** Error in the first 5 s after the merge is 0.027–0.044 m, degraded and good alike. Session 2 before the merge is also internally accurate in every run (own-fit 0.011–0.031 m).
2. **The error comes from later drift, not from the merge pose.** In the degraded runs it builds from about +10 s and peaks at +20 to +40 s (0.84–1.45 m). It then falls back to 0.05–0.3 m by +50 to +60 s, about when session 2 reaches the second revisit region, 81–98 s into session 2 (Part E, Pairs).
   - In MH0205 r2, DBoW2 closed two loops within session 2, at 82.1 s and 103.3 s, which is +51 s and +72 s after the merge. The fall in error lines up with them.
   - The good runs have the same hump with a smaller amplitude, peaking at 0.16–0.43 m.
3. **Even so, the degraded runs drifted after the merge more than any unmerged session did.** Their post-merge own-fit is 0.20–0.56 m, against at most 0.17 m in the 45 unmerged sessions on these pairs. So the merge is linked to the later distortion even though the merge alignment was accurate. The data can't show the mechanism; there is no map snapshot just after the merge and no Sim3 inlier counts.
4. **The merge pair's distance and angle don't separate degraded from good.**
   - MH0104 r3 (degraded) and r2 (good) have the **same** merge pair geometry: 0.65 m, 27.9°.
   - On MH0104, degraded runs merged at 0.63–0.95 m / 21–28°, and good ones at 0.58–0.65 m / 21–28°.
   - MH0205 r2's merge (1.95 m / 1.5°) is inside the range of the good MH0205 merges.
5. **Scale:**
   - Scale changes between the pre- and post-merge segments are small and point both ways in the degraded runs (−3.1% to +6.4%), against −0.6% to +5.5% in the good ones.
   - The largest change in a good run is MH0205 r10, +5.5% (1.321 → 1.393).
   - A scale jump at the merge doesn't explain the degradation.
6. **Not measured:** Sim3 inliers at the merge (see the top of this file). Whether merges with few inliers predict degradation can't be tested from these logs.

## What would answer the open parts (each needs a dated PREREG amendment, since it changes the frozen build)
- **Stage-3 sub-reason:** print the failing check and its count on the existing `[PROP] sim3_fail` line, plus `numProjOptMatches` on `[PROP] geom_pass` and `[PROP] accepted`. This is one log line each, with no change to control flow.
- **Error right after the merge, measured directly:** save the merged map's KF poses at `Merge finished`, as a trajectory dump, alongside the final trajectory.

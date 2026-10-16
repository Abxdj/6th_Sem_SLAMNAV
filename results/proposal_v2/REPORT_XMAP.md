# Cross-map proposer: Gate B, pre-registered calibration, live test MH_02 → MH_04

2026-10-16. Repo branch `proposal-v2`; ORB-SLAM3 branch `proposal-v2` at `d641453`. Pre-registration: `results/proposal_v2/PREREG.md` (Part A `3828a1a`, Part B with τ `87acae6`, both committed before any MH_02→MH_04 cross-map run).

Evidence labels:
- **[M]** measured and pre-registered.
- **[D]** descriptive or post hoc. These were not in the analysis plan and are reported to explain the results.

## Verdict

- **[M] Merges per arm.** The two sessions merged in **9/10 injection runs**, against **4/10 control** and **2/10 load-only**.
- **[M] Who found the merges.** **8 of the 9** injection-arm merges came from the learned proposer (`src=ext`). The ninth came from DBoW2.
- **[D] The merges are correct.** All 8 learned merges join keyframes that are genuinely close by ground truth: 0.57–0.84 m apart, 31–32°.
- **[M] Significance:**

  | comparison | Fisher exact (merged yes/no) | Mann-Whitney (merge counts) |
  |---|---|---|
  | injection vs control | p = 0.057 | p = 0.025 |
  | injection vs load-only | p = 0.0055 | p = 0.0025 |

- **The effect is reliability, not reach.** The learned proposer and DBoW2 both close the merge at the same revisit, about 32 s into MH_04. The learned proposer gets it through more often. It does not find a new place.
- **Limits of the evidence:**
  - One sequence pair.
  - Effectively one merge opportunity per run.
  - Live proposal precision of 0.54.
  - Merged-run ATE no better than control.

  So this is a positive, narrow result: the learned proposer makes cross-session map merging more reliable on one hard pair. It is not evidence of better accuracy, and not a general result yet.

## 1. Fair Gate B (offline, condition 1)

**Method.** `tools/proposal_v2/gate_b.py` together with `tools/proposal_v2/dbow_query.cc`.
- The database is the session-1 keyframes of each live run; the queries are its session-2 keyframes.
- **DBoW2 side:** raw ORBvoc score, with the same pipeline as the live system (CLAHE → 600×350 → ORBextractor(1000, 1.2, 8) → `transform(…, 4)` → `score`).
- No covisibility exclusion and no group accumulation.
- **Learned side:** top-1 cosine of the node's live ResNet18 descriptors.
- **Correct** means distance below r **and** angle below 45°.
- Recall is taken at matched precision.

### MH_02 → MH_04

6 runs, 2525 queries.

| r | queries with a true revisit | learned R@P90 | learned R@P95 | DBoW2 R@P90 | DBoW2 R@P95 | learned AP | DBoW2 AP |
|---|---|---|---|---|---|---|---|
| 0.5 m | 8 | 0 | 0 | 0 | 0 | — | — |
| 1 m | 155 | 0.032 | 0.032 | 0 | 0 | — | — |
| 2 m | 372 | 0.043 | 0.043 | 0.013 | 0.013 | 0.455 | 0.126 |

- A bootstrap over runs gives a confidence interval for the difference that excludes 0 at 1 m and 2 m.
- Learned is ahead in 5 of the 6 runs at 2 m.
- 0.5 m decides nothing: there are only 8 positives.
- **Gate B passed, narrowly**, with small absolute recall. Files: `gate_b/MH02_MH04.{json,png}`.

### V1_01 → V1_02 (1361 queries, reference)

| r | learned R@P90 | learned R@P95 | learned AP | DBoW2 R@P90 | DBoW2 R@P95 | DBoW2 AP |
|---|---|---|---|---|---|---|
| 0.5 m | 0.146 | 0.117 | 0.388 | 0.043 | 0.037 | 0.256 |
| 1 m | 0.466 | 0.375 | 0.597 | 0.306 | 0.246 | 0.502 |
| 2 m | 0.599 | 0.542 | 0.688 | 0.426 | 0.331 | 0.563 |

## 2. Threshold fixed in advance (condition 2)

- **Calibration pair:** MH_01 → MH_03, chosen by the pre-registered rule. Usable overlap at 2 m / 45° is 0.558, against 0.166 for MH_01 → MH_05.
- **Calibration runs:** 3 dry runs, `CAL_MH0103_r1..3_resnet18_dry`.
- **τ = 0.8768**, the lowest threshold with pooled precision ≥ 0.90. At τ there are 198 proposals and 179 correct (precision 0.904). File: `calibration_xmap.json`.
- Written into PREREG Part B and committed as `87acae6` before the first test run.
- **Not changed afterwards.**
  - All 30 test runs record `node_md5=781802e997edfb22b6d31bf08184ecf4`, the frozen md5.
  - All 10 injection runs record `node_args=_mode:=xmap _xmap_thresh:=0.8768`.
  - ORB-SLAM3 HEAD is still `d641453`, with a clean tracked tree.

## 3. Live test: MH_02 → MH_04, 10 runs per arm, interleaved (condition 3)

- **Invocation:** exactly as in PREREG Part B.
- **Batch window:** 13:47–16:17 (`XMAP_TEST_batch.log`).
- **Run health:** all 30 runs exited 0 and saved a trajectory. There were no mid-run crashes and Mono frame drops were 0.0% in every run.

### Merges per arm [M]

| arm | merged runs | merge counts r1..r10 | merge attribution: ext / dbow2 | Sim3 ATE of merged runs, full spanning map (m) |
|---|---|---|---|---|
| control (`none`) | **4/10** | 0 1 1 1 0 0 0 1 0 0 | 0 / 4 | 0.141, 0.171, 0.077, 0.102 (mean 0.123) |
| load-only | **2/10** | 1 0 0 0 0 1 0 0 0 0 | 0 / 2 | 0.186, 0.071 (mean 0.128) |
| injection (`resnet18`, xmap, τ = 0.8768) | **9/10** | 1 1 1 0 1 1 1 1 1 1 | **8 / 1** | 0.076, 0.090, 0.098, 0.113\*, 0.119, 0.137, 0.059, 0.703, 0.262 (mean 0.184, median 0.113) |

\* r5 is the one injection-arm merge made by DBoW2.

| test (PREREG) | Fisher exact, merged yes/no | Mann-Whitney U, merge counts |
|---|---|---|
| injection vs control | table [[9,1],[4,6]], **p = 0.057** | **p = 0.025** |
| injection vs load-only | table [[9,1],[2,8]], **p = 0.0055** | **p = 0.0025** |

Every run has 0 or 1 merges, so the Mann-Whitney test is essentially the same contrast as Fisher. Its smaller p comes from the normal approximation with ties, not from extra information. Read Fisher as the primary test.

**[D] GPU load:** control vs load-only, 4/10 vs 2/10, Fisher p = 0.63. There is no evidence that GPU load suppresses merges. Pooled control plus load-only gives 6/20, and injection vs that pool gives Fisher p = 0.0052 (post hoc).

### Proposal outcomes, injection arm [M]

Level 1 is exhaustive: in every run the outcome counts sum to the number received.

| run | received | abort_near | bow_fail | sim3_fail | geom_pass_best | accepted_merge | to merge list | to loop list |
|---|---|---|---|---|---|---|---|---|
| r1 | 23 | 5 | 0 | 17 | 1 | 1 | 18 | 5 |
| r2 | 23 | 6 | 0 | 16 | 1 | 1 | 17 | 6 |
| r3 | 27 | 4 | 0 | 22 | 1 | 1 | 23 | 4 |
| r4 | 38 | 0 | 0 | 38 | 0 | 0 | 38 | 0 |
| r5 | 33 | 4 | 0 | 29 | 0 | 0 (DBoW2 merged) | 29 | 4 |
| r6 | 24 | 4 | 0 | 19 | 1 | 1 | 20 | 4 |
| r7 | 28 | 6 | 0 | 21 | 1 | 1 | 22 | 6 |
| r8 | 25 | 4 | 0 | 20 | 1 | 1 | 20 | 5 |
| r9 | 41 | 16 | 0 | 24 | 1 | 1 | 23 | 18 |
| r10 | 26 | 5 | 0 | 20 | 1 | 1 | 21 | 5 |
| **total** | **288** | **54** | **0** | **226** | **8** | **8** | **231** | **57** |

- **Drops:** none of any kind. 100 proposals were redirected from culled KFs to a live ancestor (C1), with 129 hops in total.
- **Before the merge:** proposals go to the merge list and either fail Sim3 or are accepted. Every geometric pass that was the best candidate became an accepted merge: there were no unconfirmed or replaced merges.
- **After the merge:** both sessions are one map. Proposals are still cross-map by their creation-time map id, so C2 routes them to the loop list. There they hit `abort_near`, because the merge has already connected the two regions. That accounts for all 54 `abort_near`.
- **DBoW2 in the same runs:** `abort_near_dbow2` = 3676.

### Merge attribution and correctness [D]

GT distances come from the matched and current KF stamps in `descs.npz`. This check is available for the injection arm only, because the other arms don't dump descriptors.

| run | src | matched KF (session 1) → current KF (session 2) | GT distance | GT angle | merge time into session 2 |
|---|---|---|---|---|---|
| r1 | ext | 207 → 604 | 0.68 m | 31.6° | 31.8 s |
| r2 | ext | 207 → 608 | 0.70 m | 31.5° | 31.8 s |
| r3 | ext | 217 → 623 | 0.57 m | 32.1° | 32.0 s |
| r5 | dbow2 | 234 → 609 | 0.77 m | 8.6° | 32.9 s |
| r6 | ext | 207 → 609 | 0.68 m | 31.6° | 31.8 s |
| r7 | ext | 210 → 611 | 0.61 m | 31.9° | 32.0 s |
| r8 | ext | 200 → 601 | 0.84 m | 31.6° | 31.4 s |
| r9 | ext | 212 → 607 | 0.58 m | 32.0° | 32.0 s |
| r10 | ext | 211 → 592 | 0.59 m | 32.0° | 32.0 s |

- **Timing.** Control and load-only merges (all DBoW2) occur at 31.9–32.7 s into session 2, matching session-1 KFs 236–253. Learned merges occur at 31.4–32.0 s, matching KFs 200–217.
- **Same revisit, different anchor.** Both methods close at the **same revisit moment**. The learned proposer anchors to an earlier session-1 keyframe, about 0.6 m away with a 32° yaw difference, which it ranks highly where DBoW2 often doesn't. It does not find merges elsewhere in the sequence.
- **Where the gain comes from.** Without injection, this revisit merges in about 30% of runs (6/20 pooled). With injection it merges in 90%.

### ATE of merged runs

- **[M] Full spanning map.** Injection merged runs have mean 0.184 m and median 0.113 m. Control has mean 0.123 m and load-only 0.128 m. No test was planned.
- **[D] Per-session ATE inside the merged map.**
  - Session 1 (MH_02) is 0.034–0.040 m in every merged run of every arm.
  - Session 2 (MH_04) ranges 0.055–0.141 m, except injection r9 (0.807 m) and r10 (0.334 m).
  - For r9 and r10 the merge pair itself is GT-correct (0.58–0.59 m, 32°). The large error is drift inside MH_04 after the merge, not a wrong merge.
  - Without r9 and r10, injection merged-run ATE is 0.059–0.137 m, the same range as control.
- **Conclusion on accuracy.** Merging more often does **not** come with lower ATE. Reaching a merged map is the measured benefit; trajectory accuracy is not.

### Live proposal precision [D]

- **155 / 288 correct = 0.54** at 2 m / 45°, against 0.904 on the calibration pair.
- The pre-registration predicted this drop (test-pair overlap 0.128 vs 0.558). Wrong proposals cost only Sim3 attempts: all 226 `sim3_fail`, and no wrong merge was accepted.

## 4. Patch export (condition 4)

Commit `052323e`.
- `orb_slam3_patches/proposal_v2.patch` is `git -C ~/ORB_SLAM3 diff 4452a3c` up to `d641453`.
- Refreshed full-file copies are in `orb_slam3_patches/`, and `ros_nodes/ros_mono.cc` was created (it did not exist before).
- Verified: the patch applies to a pristine `4452a3c` worktree and reproduces every copy byte for byte.

## 5. Deviations and caveats

- **Data download (not a protocol deviation).** MH_01, MH_03 and MH_05 were not on disk. They were pulled from the ETH archive by range request, and their CRCs were checked.
- **Smoke test.** A V1_01→V1_02 xmap smoke test (`XMAPSMOKE_V0102_resnet18_dry`) ran before calibration to check the mode. It used neither the calibration pair nor the test pair. It ended with exit 139, the known shutdown crash, after the trajectory was saved.
- **Post hoc analyses.** Everything labelled [D] was added after the test. These analyses are explanatory and not pre-registered:
  - per-session ATE;
  - merge-pair GT check;
  - merge timing;
  - control vs load-only and pooled comparisons.
- **Narrow scope:**
  - One sequence pair.
  - In practice one place where the sessions can merge.
  - One descriptor (ResNet18).
  - n = 10 per arm.
  - The injection-vs-control Fisher p (0.057) is just above the descriptive α. The load-only comparison is stronger, but the load-only arm merged less often than control (not significant).
- **Next test.** A second pre-registered pair with more than one overlap region would show whether this generalises. τ stays fixed. A candidate is MH_03 → MH_05 or the V2 sequences; their overlap would have to be checked first.
- **Machine time under this approval:** about 3.0 h. That is the smoke test (5 min), calibration (19 min) and the test (2.5 h).

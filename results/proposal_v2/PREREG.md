# Pre-registration: cross-map proposer, live test on MH_02 → MH_04

Written 2026-10-16, **before** any calibration-pair or test-pair run with the cross-map proposer. Part A was committed before calibration. Part B (τ) is added in a separate commit after calibration and **before the first MH_02→MH_04 run**. Neither is changed afterwards. Any deviation will be reported as a deviation.

## Part A: rule, calibration procedure, analysis plan

### Proposer (ros_nodes/loop_closure_node.py, `_mode:=xmap _xmap_thresh:=τ`)
- **Per keyframe k:** ResNet18 (ImageNet weights) descriptor of k's own image (CLAHE output; stamp-matched within 1 ms). It is L2-normalised.
- **Candidates:** database KFs whose map id at creation (ORB-SLAM3 C6) differs from k's, with |Δt| ≥ 30 s and map id ≥ 0.
- **Propose** the top-1 by cosine if score ≥ τ. τ is a fixed absolute value, with no adaptation and no warm-up.
- **Same-map proposer: off** (`mode=xmap`), so the injection arm tests the cross-map proposer alone.
- **ORB-SLAM3 side:** unchanged from the earlier proposal-v2 runs plus C6 (map id in the KF message):
  - C1 culled-KF redirect.
  - C2 routing: other-map → merge list, same-map → loop list.
  - C5 outcome accounting.
- **No further C++ or node changes** during the test.

### Calibration (sets τ; never uses MH_02 or MH_04)
- **Calibration pair:** MH_01 → MH_03, or MH_01 → MH_05 if MH_03 has less usable overlap. Usable overlap = fraction of session-2 GT poses with a session-1 pose < 2 m and < 45°; the higher wins.
- **Runs:** 3 dry runs (`resnet18_dry`, `_mode:=xmap _xmap_thresh:=2.0`, i.e. the node logs and dumps but never proposes), real time, same harness.
- **Replay:** `tools/proposal_v2/calibrate_xmap.py <gt> 0.90 2.0 45 <runs>` replays the exact causal rule on the dumps.
- **τ** = the lowest threshold whose pooled precision is ≥ **0.90**. Correct = GT distance **< 2.0 m** and angle **< 45°** between the query KF and the proposed KF.
- **Why 2 m:** the one GT-checkable DBoW2 merge on MH_02→MH_04 joined KFs 1.82 m / 3.3° apart, so Sim3 verification accepts revisits at that distance.
- **If no threshold reaches 0.90:** τ = the score at which pooled precision is highest, and this is reported.

### Live test: MH_02 → MH_04, one ORB-SLAM3 process, `/orb_slam3/new_session` → ChangeDataset, 5 s gap, real time (speed 1.0)
- **Arms, 10 runs each, interleaved** (control, load-only, injection, ×10):
  - control (`none`)
  - load-only (`load_only_v2.py` at 3.55 KF/s, the KF rate measured on this pair earlier)
  - injection (`resnet18`, `_mode:=xmap _xmap_thresh:=τ`)
- **Primary outcome:** whether the two sessions' maps merge (≥ 1 `Merge finished`) per run.
  - Injection vs control and injection vs load-only: Fisher exact, two-sided.
  - Merge counts per run: Mann-Whitney U, two-sided.
  - No correction beyond reporting both comparisons. α = 0.05 is descriptive, not a claim threshold.
- **Attribution:** each accepted merge is `src=ext` (its matched KF came from our queue) or `src=dbow2` (C5).
- **Proposal outcomes (injection arm):** per-run table of level-1 outcomes. Columns: received, drops, abort_near, bow_fail, sim3_fail, geom_pass (best / not best). Then accepted_merge / accepted_loop / unconfirmed.
- **ATE:** Sim3 Umeyama on the map spanning both sessions, vs the concatenated GT (`analyze_pv2.py`), merged runs only. Descriptive (mean, range); no test planned.
- **Stopping:** 3 consecutive mid-run crashes, disk < 10 GB, or > ~4 h total machine time (then ask). Crashed runs are reported, not replaced.

## Part B: calibrated threshold

Filled 2026-10-16 13:45 IST. No MH_02→MH_04 run with the cross-map proposer has been started.

- **Calibration pair:** MH_01 → MH_03. GT overlap at 2 m / 45°: MH_01→MH_03 0.558, MH_01→MH_05 0.166 (rule: the higher wins).
- **Calibration runs:** `CAL_MH0103_r1..3_resnet18_dry`. All exit 0; each merged once via DBoW2. 854 scored KFs pooled, 186 of them would be correct if proposed.
- **τ = 0.8768** (`results/proposal_v2/calibration_xmap.json`). At τ: 198 proposals, 179 correct, precision 0.904. Command: `calibrate_xmap.py ~/euroc_mh/MH_01_MH_03_groundtruth_tum.txt 0.90 2.0 45 <3 runs>`.
- **Frozen code:**
  - repo commit with Part A: 3828a1a
  - `ros_nodes/loop_closure_node.py` md5 `781802e997edfb22b6d31bf08184ecf4`
  - ORB-SLAM3 `proposal-v2` HEAD `d641453` (C6)
- **Test invocation:** `LOAD_KF_HZ=3.55 NODE_ARGS="_mode:=xmap _xmap_thresh:=0.8768" tools/proposal_v2/run_batch.sh results/proposal_v2/plans/XMAP_TEST.plan results/proposal_v2/XMAP_TEST_batch.log`
- **Known limitation, stated before the test:** the test pair's GT overlap (0.128 at 2 m) is much lower than the calibration pair's (0.558). Precision at a fixed τ falls with prevalence, so live precision on MH_02→MH_04 is expected to be below 0.90. The rule is not adjusted for this.

## Part C: multi-pair cross-map test

Written 2026-10-26, **before** any run of this test, and before the V1 smoke run. Committed and pushed by the owner before the first run. Not changed afterwards; any deviation is reported as a deviation. Parts A and B are unchanged. In particular **τ = 0.8768** is not recalibrated.

### Pairs (chosen offline by GT overlap, `tools/proposal_v2/pair_overlap.py`, 2 m / 45°)

Overlap is the fraction of session-2 GT poses that have a session-1 pose within 2 m and 45°. A region is a run of revisiting session-2 time of at least 2 s, with gaps under 2 s joined. A place is a region more than 3 m from every earlier region.

| pair (session 1 → 2) | overlap | regions / distinct places | label | why |
|---|---|---|---|---|
| MH_03 → MH_05 | 0.554 | 5 / 4 | **related** | MH_03 was the session 2 of the calibration pair (MH_01 → MH_03) |
| MH_04 → MH_02 | 0.352 | 5 / 2 | **related** | the previous test pair, reversed |

Both pairs are **related**, so Part C has **no independent pair**.

**The independent pair V1_01 → V1_03 will be a separate pre-registered Part D.**
- **Why not here:** V1_03 is not on disk, and the ETH Research Collection server has returned HTTP 429 (Too Many Requests) to most requests since about 11:30 on 2026-10-26. When this was written, the resumable download had 6 of 48 chunks.
- **Part D:** written after the data arrive and the overlap is checked, and committed and pushed before its first run. Its τ (0.8768), ORB-SLAM3 build (`9aad4f8`), node md5, harness, arms, n and analysis are **frozen exactly as in Part C**; only the pair changes.
- **Not pooled:** Part D is not added to the Part C analysis afterwards.

**Candidates not chosen:**
- **MH_01 → MH_05:** overlap 0.166, 2 regions, only 1 distinct place, and MH_01 is a calibration sequence.
- **V2 (V2_01 → V2_02 / V2_03): excluded.** The same server returned HTTP 429, so the V2 data could not be fetched. If V2 is fetched later, it will be a **separate, separately pre-registered test**, not an addition to this one.

**Reversed timestamps (MH_04 → MH_02).** MH_04 was recorded after MH_02, so session-2 stamps are older than session-1 stamps.
- The publisher sends `/orb_slam3/new_session` before session 2.
- `System::ChangeDataset` → `Tracking::CreateMapInAtlas` sets `mState = NO_IMAGES_YET`, so the timestamp-order check (`src/Tracking.cc`, "older than previous frame") is skipped for the first session-2 frame.
- The node's 30 s exclusion uses |Δt|.
- This pair has not been run live before. Any "timestamp older" errors will be counted and reported.

### Frozen code
- **ORB-SLAM3** branch `proposal-v2` at **`9aad4f8`**. This is `d641453` (Part B) plus **C7**: timing counters only. The diff `d641453..9aad4f8` is 15 added lines in `src/LoopClosing.cc` and nothing removed:
  - `#include<chrono>`;
  - a steady-clock timer around `NewDetectCommonRegions()` per KF;
  - a per-candidate timer in `DetectCommonRegionsFromBoW`, keyed by source and stage.

  The timings are reported as extra `us_*` / `n_*` counters in the existing `[PROP-STATS]` / `[PROP-FINAL]` lines, with no new print statements.
  - `libORB_SLAM3.so` was rebuilt 2026-10-26 11:16:45 and `Mono` 11:17:21, with 0 errors.
  - Every run's `meta.txt` records the ORB-SLAM3 sha, a diff md5 and the lib and Mono mtimes.
- **Node** `ros_nodes/loop_closure_node.py`, md5 **`781802e997edfb22b6d31bf08184ecf4`** (unchanged since Part B), with `_mode:=xmap _xmap_thresh:=0.8768`.
- **Harness** at this commit:
  - `tools/proposal_v2/run_euroc.sh` now also starts `tools/proposal_v2/kf_logger.py` in **every arm**. It is CPU only, with no model, and logs `[kf_id, stamp, map_id]` from `/orb_slam3/new_keyframe` to `kf_log.csv`.
  - `load_only_v2.py` runs at `LOAD_KF_HZ=3.55` for all pairs, the rate measured on MH_02 → MH_04, the same as Part B.
- **Analysis:** `tools/proposal_v2/analyze_xmap2.py` at this commit, with `results/proposal_v2/plans/XMAP2_pairs.json`. It was dry-run on the Part B data, where it reproduces Fisher p = 0.0573.

### Smoke run (before the batch; not part of the test)
- **Run:** one injection-arm run on **V1_01 → V1_02**, tag `XMAP2SMOKE_V0102`. V1_02 is in no test pair of Part C or Part D.
- **Purpose:**
  - check that C7 and the KF logger work live;
  - report the **timing-counter overhead per keyframe**;
  - confirm, by the diff above, that the patch adds only timers and counters.
- **Overhead measure:** a micro-benchmark is not possible inside the run. The upper bound is (number of C7 counter updates × measured cost of one `PropCount` call with string build) per KF. The number of updates per KF comes from the run's own counters. The cost per call is timed offline in a loop of 10⁶ calls.
- **If the smoke run fails:** any fix is logged here as a deviation, with the new commit hash, before the batch. No test pair is run before the smoke run passes.

### Design
- **Arms:** control (`none`), load-only (`load_only`), injection (`resnet18`, xmap, τ = 0.8768).
- **Runs:** 10 runs per arm per pair, 60 runs in total. Real time (speed 1.0), one ORB-SLAM3 process per run, `/orb_slam3/new_session` → ChangeDataset, 5 s gap.
- **Order** (`tools/proposal_v2/make_plan_xmap2.py`, plan `results/proposal_v2/plans/XMAP2_TEST.plan`):
  - Blocks k = 1..10. Block k runs every pair before block k+1 starts, in the order MH_03→MH_05, MH_04→MH_02.
  - Within each pair the arm order rotates with k mod 3: (none, load_only, resnet18) → (load_only, resnet18, none) → (resnet18, none, load_only).
- **Tags:** `X2_MH0305_r<k>_<arm>`, `X2_MH0402_r<k>_<arm>`. Pairs config: `results/proposal_v2/plans/XMAP2_pairs.json`.
- **Invocation:** `LOAD_KF_HZ=3.55 NODE_ARGS="_mode:=xmap _xmap_thresh:=0.8768" tools/proposal_v2/run_batch.sh results/proposal_v2/plans/XMAP2_TEST.plan results/proposal_v2/XMAP2_TEST_batch.log`
- **Expected machine time:** about 5.2 min per run, about 5.2 h for the batch plus about 5 min for the smoke run.

### Outcomes and analysis (`analyze_xmap2.py`, exactly as committed)
- **Primary outcome:** maps merged (≥ 1 `Merge finished`) per run.
- **Primary test:** injection vs control, Cochran–Mantel–Haenszel χ² stratified by pair over **both pairs**. 1 df, no continuity correction, two-sided. The Mantel–Haenszel common odds ratio is reported with it.
- **Pre-registered sensitivity analyses:**
  1. The exact conditional stratified test of a common odds ratio of 1, on all pairs. With n = 10 per cell the χ² approximation is liberal; on the Part B data it gave p = 0.022 where Fisher gave 0.057.
  2. Independent pairs only: **not applicable in Part C**, which has none. The independent-pair test is Part D.
- **Secondary tests:**
  - CMH and exact stratified test, injection vs load-only.
  - Per pair: Fisher exact (two-sided), injection vs control and injection vs load-only; Mann-Whitney U (two-sided) on merge counts.
  - **Time to first merge**, in seconds into session 2, from the stamp of the current KF of the first accepted merge. Runs that never merge are **censored** and ranked after every merged run; they are all censored at the same point, the end of session 2. Compared with Mann-Whitney U per pair, injection vs control and vs load-only.
- **α:** 0.05 is descriptive. No multiplicity correction beyond reporting every comparison listed here.
- **Prediction (pre-registered):** the injection effect is largest where the control merge rate is low, and near zero where control merges in most runs.
  - Per pair, with d = injection rate − control rate:
    - control rate **≥ 0.8**: prediction holds if **d ≤ 0.2**;
    - control rate **≤ 0.5**: prediction holds if **d ≥ 0.3**;
    - control rate 0.6–0.7: the pair is uninformative for the prediction.
  - Reported per pair as holds / fails / uninformative. No test across pairs; there are only 2.
- **Reported for every pair** (descriptive):
  - per-arm merge tables;
  - attribution of every accepted merge (`src=ext` / `dbow2`);
  - **GT check of every merge in every arm**: distance and angle between the matched and current KFs, with stamps from `kf_log.csv`;
  - level-1 proposal outcomes per injection run;
  - Sim3 ATE **per session** (each session's KFs in the map holding most of them) and of the map spanning both sessions;
  - **Sim3 cost of wrong proposals**: attempts and total verification time of our candidates that reached BoW matching but did not verify (C7 stages 1–3), per run and per arm;
  - place-recognition time per KF per arm, injection vs control and vs load-only (Mann-Whitney, descriptive);
  - live proposal precision vs GT (2 m / 45°);
  - crashes and Mono drop %.
- **Offline descriptors:** they may be computed afterwards for any arm from `kf_log.csv` (`offline_descs.py`). Any analysis using them is labelled post hoc.

### Stopping
- The batch stops on any of:
  - 3 consecutive mid-run crashes (`run_batch.sh`);
  - disk below 10 GB;
  - more than about 8 h of machine time in total, counting the smoke run. The batch is expected to take about 5.3 h.
- If the batch stops early, the analysis uses the completed blocks. Interleaving keeps n equal across pairs at block boundaries, so an incomplete last block is dropped from the primary test (`--max-block K`, K = last complete block) and reported separately.
- Crashed runs are reported, not replaced.

## Part E: low-overlap cross-map test

Written 2026-10-26, after Part C finished (`bdecde1`). The selection rule below is committed **before** any overlap for Part E is computed. Pairs, design and analysis follow in a later commit, before any run. Parts A–D are unchanged. τ = 0.8768 is not recalibrated. Part D (V1_01 → V1_03) stays a separate test and is not pooled with Part E.

### Selection rule (fixed before it is applied)
- **Candidates:** every ordered pair (session 1 → session 2) of the EuRoC MH sequences on disk: MH_01, MH_02, MH_03, MH_04, MH_05. That is 20 ordered pairs.
- **Overlap measure:** `tools/proposal_v2/pair_overlap.py` at this commit, 2 m / 45°, using the `overlap` field (the fraction of all session-2 GT poses), with the region and place definitions of Part C. GT comes from `~/euroc_mh/<seq>_groundtruth_tum.txt`.
- **Eligible pairs** meet all three:
  1. 0.05 ≤ overlap ≤ 0.25;
  2. `n_regions` ≥ 1;
  3. not one of the excluded ordered pairs: **MH_02→MH_04** (Parts A/B), **MH_03→MH_05** and **MH_04→MH_02** (Part C), and **MH_01→MH_03** (calibration). The exclusion applies to these ordered pairs only. Their reverses are judged by rules 1–2 like any other pair.
- **Choice:** the eligible pairs sorted by overlap, ascending; take the first **3**, or all of them if fewer than 3. Ties are broken by more `n_places`, then by sequence names in lexical order. If no pair is eligible, Part E ends here, with no runs.
- **Label:** a pair is **independent** only if:
  - neither sequence was used to set τ (MH_01, MH_03); and
  - neither sequence was in any earlier live test pair (MH_02, MH_04, MH_05).

  Otherwise it is **related**, and the reason is given per pair.

### Pairs (selection rule applied after the commit above, `b96908c`)
- **Overlaps:** all 20 ordered pairs are in `results/proposal_v2/partE/overlap_all_ordered.jsonl`.
- **Eligible:** exactly 3 pairs, so all 3 are taken. No tie-break was needed.

| pair (session 1 → 2) | overlap | regions / places | label | why related |
|---|---|---|---|---|
| MH_02 → MH_05 | 0.140 | 2 / 1 | **related** | MH_02 was session 1 of the Part B test pair; MH_05 was session 2 of a Part C pair |
| MH_01 → MH_04 | 0.145 | 2 / 1 | **related** | MH_01 was used to set τ; MH_04 was in the Part B and Part C test pairs |
| MH_01 → MH_05 | 0.166 | 2 / 1 | **related** | MH_01 was used to set τ; MH_05 was in a Part C pair |

**Ineligible pairs:**
- Excluded by rule 3: MH_02→MH_04 (0.127) and MH_01→MH_03 (0.559). Without the rule MH_02→MH_04 would have qualified, which is why it is excluded by name.
- Every other pair is outside 0.05–0.25. The lowest of these is MH_04→MH_01 at 0.299.

**Note: all three pairs revisit the same place as Part B.**
- **The places:**
  - In all three, the first region starts 24–26 s into session 2 at about (0.3–0.9, 4.1–4.3) m.
  - A second visit comes 81–98 s in, within 3 m of the first, so it is the same place.
  - MH_02 → MH_04 (Part B) has the same structure: 25.8 s at (0.07, 4.3) m, then 81.4 s.
- **What this means:**
  - Part E is a test of whether the Part B effect recurs at that revisit with different session pairings.
  - It is not a test at new places.
  - The four low-overlap pairs share session-2 sequences: MH_04 is in Part B and MH0104; MH_05 is in MH0205 and MH0105.

All pairs run forward in time, so there are no reversed timestamps. The concatenated GT files were built with `cat` then `sort -g`, and their line counts equal the sum of their parts:
- `~/euroc_mh/MH_02_MH_05_groundtruth_tum.txt`
- `~/euroc_mh/MH_01_MH_04_groundtruth_tum.txt`
- `~/euroc_mh/MH_01_MH_05_groundtruth_tum.txt`

### Frozen (identical to Part C; nothing rebuilt)
- **ORB-SLAM3** `9aad4f8`, with an empty working-tree diff. `libORB_SLAM3.so` dated 11:16:45 and `Mono` 11:17:21.
- **Node** md5 `781802e997edfb22b6d31bf08184ecf4`, run with `_mode:=xmap _xmap_thresh:=0.8768`.
- **Harness:** `run_euroc.sh`, `run_batch.sh`, `kf_logger.py` and `load_only_v2.py` with `LOAD_KF_HZ=3.55`. `tools/` and `ros_nodes/` are unchanged since `b830bee`.
- **Analysis:** `tools/proposal_v2/analyze_xmap2.py`, md5 `e1cc90d9b4ce7b0bba3cc2d1f42c91cb`, unchanged. Inputs `results/proposal_v2/plans/XMAPE_pairs.json`; output `results/proposal_v2/xmapE_test_results.json`.
- **No smoke run.** Code and build are byte-identical to the Part C batch, which ran 60/60 with PROP-FINAL. Every run's `meta.txt` is checked against the values above before analysis. Any mismatch is reported as a deviation.

### Design (as Part C)
- **Arms:** control (`none`), load-only (`load_only`), injection (`resnet18`, xmap, τ = 0.8768).
- **Runs:** 10 runs per arm per pair, **90 runs**. Real time, one ORB-SLAM3 process per run, `/orb_slam3/new_session`, 5 s gap.
- **Plan:** `results/proposal_v2/plans/XMAPE_TEST.plan`, from `make_plan_xmap2.py XMAPE_pairs.json 10`.
  - Interleaved blocks k = 1..10, pairs in the order MH0205, MH0104, MH0105.
  - Arm order rotates with k mod 3, as in Part C.
- **Tags:** `XE_<PAIR>_r<k>_<arm>`.
- **Invocation:** `LOAD_KF_HZ=3.55 NODE_ARGS="_mode:=xmap _xmap_thresh:=0.8768" tools/proposal_v2/run_batch.sh results/proposal_v2/plans/XMAPE_TEST.plan results/proposal_v2/XMAPE_TEST_batch.log`
- **Expected machine time:** about **8.5 h**. This is (session 1 + session 2 + 60 s) per run, where 60 s is Part C's measured median overhead, times 90. That is above the ~8 h approved per batch so far, so the batch starts only after the owner explicitly approves this time.

### Outcomes and analysis (`analyze_xmap2.py`, exactly as committed)
- **Primary outcome:** maps merged (≥ 1 `Merge finished`) per run.
- **Primary test:** injection vs control, CMH χ² stratified by pair over all three pairs. 1 df, no continuity correction, two-sided. Reported with the MH common odds ratio.
- **Pre-registered sensitivity analyses:**
  1. The exact conditional stratified test, all pairs.
  2. Independent pairs only. **Not applicable:** all three pairs are related.
- **Secondary tests** (as Part C):
  - CMH and exact test, injection vs load-only.
  - Per pair: Fisher (two-sided) and MWU on merge counts, vs control and vs load-only.
  - Time to first merge into session 2, never-merged runs censored, MWU per pair.
  - Detect ms per KF, MWU per pair.
- **α:** 0.05, descriptive. No multiplicity correction beyond reporting every comparison.
- **Prediction (pre-registered):** on every pair where control merges in **≤ 5/10** runs, injection rate − control rate **≥ 0.3**.
  - Reported per pair as holds / fails.
  - A pair with control > 5/10 is **not applicable** to this prediction and is reported as such.
  - The script's `prediction` field uses the Part C bands. Its low band (≤ 0.5, d ≥ 0.3) is exactly this rule. Its high-band verdicts are reported for information and are not part of Part E's prediction.
  - Overall, the prediction **holds** if it holds on every applicable pair. If no pair is applicable, it is **untested**.
- **Reported for every pair** (as Part C):
  - merge tables and attribution (ext / dbow2);
  - GT check of every merge and loop in every arm;
  - proposal outcomes;
  - ATE per session and of the spanning map;
  - Sim3 cost of failed external candidates (C7 stages 1–3, attempts and ms);
  - live proposal precision;
  - exit codes, crashes and drop %.

### Stopping
- The batch stops on any of:
  - 3 consecutive mid-run crashes;
  - disk below 10 GB;
  - the machine-time cap the owner approves.
- If the batch stops early, the analysis uses complete blocks only (`--max-block K`). The incomplete block is reported separately.
- Crashed runs are reported, not replaced.
- **Part D** (V1_01 → V1_03) is not run or pooled with Part E.

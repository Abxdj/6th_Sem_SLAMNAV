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

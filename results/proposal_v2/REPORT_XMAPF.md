# Part F report: replication of Part D with a cross-session outcome (V1_01 → V1_03)

**Date:** 2026-11-01.
- **Pre-registration:** PREREG Part F, `f513810`, pushed by the owner before the first run. It was registered after Part D's results were seen, as that section states.
- **Primary analysis:** `tools/proposal_v2/analyze_partF.py results/proposal_v2/plans/XMAPF_pairs.json results/proposal_v2/xmapF_test_results.json`, exactly as committed.
  - md5 `c50bd2f8…` was checked, and the script confirmed the classifier `posthoc_frag.py` md5 `610bdb7a…` itself.
  - No `--max-block`: all 10 blocks completed.
- **Secondary analysis:** `tools/proposal_v2/analyze_xmap2.py results/proposal_v2/plans/XMAPF_pairs.json results/proposal_v2/xmapF_xmap2_results.json`, md5 `e1cc90d9…`.
- **Batch log:** `results/proposal_v2/XMAPF_TEST_batch.log`.

## Summary

**The primary test is not significant.**
- Runs with ≥ 1 cross-session merge: injection **7/10**, control **3/10**.
- Fisher exact, two-sided: **p = 0.18**.

**The pre-registered prediction holds.** The rate difference is 0.7 − 0.3 = **0.4**, against the registered d ≥ 0.3.

**The direction replicates, but the size of the Part D post hoc effect does not.**
- Part D post hoc: 9/10 vs 2/10.
- Part F: 7/10 vs 3/10.
- With 10 runs per arm, a 0.4 difference is not significant at α = 0.05.

**Our proposer made the cross-session merge in only 3 of the 7 injection runs.** DBoW2 made it in the other 4 (see "Who made the cross-session merges").

| arm | runs with ≥ 1 cross-session merge (primary) | cross-session merges (source) | fragment merges | runs with any merge (Part D outcome) |
|---|---|---|---|---|
| control | **3/10** | 3 (dbow2 3) | 5 | 8/10 |
| load-only | **3/10** | 3 (dbow2 3) | 6 | 9/10 |
| injection | **7/10** | 7 (ext 3, dbow2 4) | 6 (dbow2 5, ext 1) | 9/10 |

| comparison | table (cross-session / not) | Fisher p (two-sided) |
|---|---|---|
| **injection vs control (primary)** | 7/3 vs 3/7 | **0.18** |
| injection vs load-only (secondary) | 7/3 vs 3/7 | 0.18 |

## Machine time and run health
- **Machine time:** 17:54:02 to 20:25:15, **2.5 h**, within the owner's 4 h cap.
  - The watchdog was dry-run before arming (cap 21:54:02). It exited at 20:25:18 without being triggered.
- **Frozen state:** `meta.txt` of all 30 runs shows:
  - `orbslam_sha=9aad4f8`, with `orbslam_diff_md5=d41d8cd9…` (the empty diff);
  - `node_md5=781802e9…`;
  - `node_args=_mode:=xmap _xmap_thresh:=0.8768`;
  - `load_kf_hz=3.55`;
  - `yaml_md5=f4d516b5…`;
  - `lib_mtime` 2026-10-26 11:16:45, `mono_mtime` 11:17:21;
  - `repo_sha=f513810`. `repo_dirty=1`, as in Parts D and E: there are untracked files only.
  - **No deviation.**
- **Exit codes:** 0 in 25 runs.
  - **139 in 3** (`r2_resnet18`, `r6_none`, `r7_resnet18`): the known shutdown segfault.
  - **133 in 2** (`r4_load_only`, `r7_none`): a GDK `BadWindow` X error from the viewer window at shutdown. This exit code did not occur in Part D.
  - In all 5, the crash came after `Shutdown` and after both trajectories were saved.
- **Mid-run crashes: none.** All 30 runs saved a non-empty `KeyFrameTrajectory_allmaps.txt`. The crash rule was therefore not needed: every run is scored on its complete `mono.log`, and `analyze_partF.py` reports `crashed_runs: {}`.
- **`XF_V0103_r3_load_only` is not a crash.** The batch log says `traj=NO`, and `analyze_xmap2.py` counts `midrun_crashes: 1` in load-only.
  - Both look only at `KeyFrameTrajectory.txt`, which is empty because tracking was lost just before shutdown and a new, empty map was started. It exited 0.
  - Its all-maps trajectory (679 KFs) exists and is used for ATE. This is the same artefact as Part D's `r7_load_only`.
- **3 consecutive crashes:** never reached. Disk stayed at 20 GB free.
- **Mono frame drops:** 0–0.10%.

## Checks (pre-registered)
- **Merge count:** accepted merges equal `Merge finished` lines in every run: no mismatch.
- **Session boundary:** every run has a first session-2 KF id.
- **Classification:** id and stamp methods agree on **30/30** merges, and **0 merges are unclassified**.

## Who made the cross-session merges (descriptive)

| run | cross-session merge(s): source, time into session 2 |
|---|---|
| control r3, r6, r7 | dbow2 at 13.8, 13.9, 13.7 s |
| load-only r3, r6, r9 | dbow2 at 14.3, 13.9, 14.0 s |
| injection r3, r5 | **ext** at 13.2, 14.2 s |
| injection r6 | **ext** at 90.0 s |
| injection r2, r7, r9 | dbow2 at 13.8, 14.2, 13.8 s |
| injection r10 | dbow2 at 86.3 s |

**Early place (about 14 s into session 2).**
- Every cross-session merge in control and load-only is a DBoW2 merge here, as in Part D.
- In the injection arm, 5 runs merged here (ext 2, dbow2 3), against 3 in each other arm.
- Two of those five are external merges at the same place and time where DBoW2 merges in other runs. They may be merges DBoW2 would have made anyway; this data cannot tell.

**Late cross-session merges (after 80 s).**
- These occurred only in the injection arm: r6 (ext, 90.0 s) and r10 (dbow2, 86.3 s).
- In Part D, our proposer made 3 such late merges (87.5–89.4 s). Here it made 1.

**Fragment merges** (both KFs in session 2) are about as common in every arm: 5, 6 and 6.

## Secondary results (`analyze_xmap2.py`, descriptive)

**Part D's registered outcome (≥ 1 merge of any kind):**
- injection 9/10, control 8/10, load-only 9/10;
- CMH injection vs control: χ² = 0.37, p = 0.54, exact p = 1.0;
- vs load-only: p = 1.0;
- Fisher: 1.0 in both comparisons.

`analyze_xmap2.py` also prints a `prediction` field ("band high, holds"). That field is the Part C/D rule on the any-merge outcome, **not the Part F prediction**, and is not used here.

**Merge attribution, injection arm:** 13 merges, ext 4 and dbow2 9.

**GT check (2 m / 45°), all arms:**
- **Merges: 30/30 within** (≤ 0.90 m, ≤ 30.2°). No wrong merge was accepted in any arm.
- **Loops:** 31/41 within. 10 are outside on angle only (50.5–63.0°, ≤ 0.76 m), and **all 10 are DBoW2 loops**: 3 control, 4 load-only, 3 injection.
- **Our proposer:** all 7 accepted external matches (4 merges, 3 loops) are within (≤ 1.07 m, ≤ 22.3°).

**Our proposer's candidates (injection arm, 10 runs):**

| received | stage 0 (covisible-near) | stage 1 | stage 2 | stage 3 | geometric pass (best / not best) | accepted |
|---|---|---|---|---|---|---|
| 1,536 | 259 | 40 | 737 | 361 | 7 / 1 | 7 (4 merges, 3 loops) |

- **Sim3 cost of failed external candidates:** 1,138 attempts, 3,792 ms in total, about 0.38 s per run.
- **Live proposal precision vs GT:** 1,471 / 1,520 = **0.97**. As in Part D, this mostly reflects the pair's overlap (0.962).

**Timing:**
- **Detect ms per KF, median:** injection 3.94, control 3.45 (MWU p = 0.0006), load-only 3.57 (p = 0.0032). That is about **+0.4–0.5 ms per KF**, as in Part D.
- **Time to first merge into session 2** (any kind):
  - vs control p = 0.14; vs load-only p = 0.11;
  - injection 13.2–53.9 s in 9 runs; control 13.7–101.4 s in 8 runs; load-only 13.9–62.1 s in 9 runs.
- **MWU on merge counts:** vs control p = 0.12; vs load-only p = 0.20.

**ATE (m), descriptive, no test registered:**

| arm | median session 1 / session 2 | session-2 range | runs with a map spanning both sessions | median spanning ATE (range) |
|---|---|---|---|---|
| control | 0.095 / 0.122 | 0.062–0.504 | 3 | 0.085 (0.084–0.202) |
| load-only | 0.096 / 0.073 | 0.063–0.441 | 3 | 0.383 (0.149–0.442) |
| injection | 0.096 / 0.094 | 0.062–1.137 | 7 | 0.120 (0.087–0.913) |

- **Spanning maps:** a map spanning both sessions was found in exactly the cross-session runs of each arm (3, 3, 7). This independently confirms the classifier.
- **Injection r5:** its external cross-session merge at 14.2 s is GT-correct (0.22 m, 19.5°). Even so, its spanning-map ATE is 0.913 m and its session-2 ATE is 1.137 m. Map quality after merging is not reliably better, as in Parts D and E.

## What this changes
- **The cross-session effect seen post hoc in Part D is not confirmed at α = 0.05.**
  - In fresh runs with the outcome fixed in advance: 7/10 vs 3/10, p = 0.18.
  - The pre-registered prediction (d ≥ 0.3) holds, with d = 0.4. So the direction and approximate size are consistent with an effect, but this test cannot establish one.
- **The Part D post hoc estimate was optimistic.**
  - 9/10 vs 2/10 became 7/10 vs 3/10.
  - Our proposer's own share of cross-session merges fell from 6 of 9 runs to 3 of 7.
  - In 4 of the 7 injection runs, the cross-session merge came from DBoW2: 3 at the early place, the same count as control's 3, and 1 late (r10, 86.3 s). The injection arm's excess of 4 runs over control is therefore 3 runs with an external cross-session merge plus r10's late DBoW2 merge. Whether injection contributed to r10's merge cannot be told from this data.
- **Part F and Part D are not pooled,** as registered.
  - It is the same pair and the same sequences, not independent data.
  - Part D's 9/10 vs 2/10 was found post hoc and motivated this test.
- **The independent-pair evidence stays weak.**
  - Part D: null on its registered outcome.
  - Part F: null on its registered test, with the prediction met.
  - The positive results remain Parts B (p = 0.057, borderline) and E (CMH p = 7.7 × 10⁻⁷), both on Machine Hall pairs.
- **Costs and safety, unchanged from Part D:**
  - about +0.5 ms per KF and 0.38 s per run of failed external Sim3;
  - no wrong merge in any arm;
  - all external matches within GT.

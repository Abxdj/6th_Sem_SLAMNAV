# SLAM project status (30 Oct 2026)

**Repo:** github.com/Abxdj/6th_Sem_SLAMNAV, branch `proposal-v2`.
- Part E results are committed locally. **Push them first** (`git push`). If git asks for a password, use the token, not the GitHub password; it's cached for a day.

**Code state:**
- ORB-SLAM3 build `9aad4f8`, exported as `orb_slam3_patches/proposal_v2.patch`. Never push `~/ORB_SLAM3`.
- Pre-registration lives in `results/proposal_v2/PREREG.md`. Reports: `REPORT_XMAP.md` (B), `REPORT_XMAP2.md` (C), `REPORT_XMAPE.md` (E).

## Pre-registered results

Fixed settings throughout: τ = 0.8768 (calibrated on MH_01→MH_03); 10 runs per arm.

| Part | Pair | Overlap | Control | Load-only | Injection | Bottleneck |
|---|---|---|---|---|---|---|
| B | MH_02→MH_04 | 0.127 | 4/10 | 2/10 | 9/10 (8 ours) | proposal (Fisher p=0.057) |
| C | MH_03→MH_05 | 0.554 | 8/10 | 9/10 | 10/10 | none: DBoW2 suffices (CMH p=0.146) |
| C | MH_04→MH_02 | 0.352 | 10/10 | 10/10 | 10/10 | none |
| E | MH_02→MH_05 | 0.140 | 0/10 | 0/10 | 10/10 (9 ours) | proposal |
| E | MH_01→MH_04 | 0.145 | 0/10 | 0/10 | 5/10 (5 ours) | proposal |
| E | MH_01→MH_05 | 0.166 | 0/10 | 0/10 | 0/10 | **verification**: 355/672 of our proposals pointed at the right place, all rejected by geometry |

**Part E primary test:** CMH p = 7.7e-7 (exact 1.8e-7). **The pre-registered prediction fails overall,** because MH_01→MH_05 shows no effect.

**Caveats:**
- All low-overlap pairs revisit the **same place** (~25 s into session 2).
- **No independent pair yet.** Part D (V1_01→V1_03) is pending its download (42/48 chunks).
- **Merges sometimes hurt accuracy.** In 4/15 merged injection runs in Part E, session-2 ATE was 0.25–0.52 m (vs about 0.06 m). Learned merges join keyframes 1.4–2.0 m apart.
- **Safety:** thousands of wrong proposals, and no wrong merges. One DBoW2 merge sat at 2.005 m and was reported as outside the check.
- **Cost:** about +0.2–0.6 ms per keyframe of verification time.

**Other findings:**
- KITTI live matches standalone ORB-SLAM3 (Gate A).
- Single-session and easy multi-session pairs: DBoW2 saturates.
- Offline Gate B: learned descriptors beat DBoW2; ResNet18, EfficientNet and DINO are tied.
- Methodological lessons: keyframe culling drops external proposals; a load-matched control is needed; thresholds don't transfer across sessions; single runs are meaningless.

## Next session

**1.** `git push` the Part E results.

**2.** Send to Claude Code (`claude --continue` inside `tmux new -s diag`):
> Pushed. Two offline analyses, labelled post hoc in `results/proposal_v2/POSTHOC_E.md`; don't change any pre-registered report:
> 1. MH_01→MH_05 verification failure: at which stage did our ground-truth-correct proposals fail (BoW / Sim3 inliers / guided matching), and what were their distance and angle vs the passing merges on MH_02→MH_05 and MH_01→MH_04?
> 2. Merged-run accuracy: 4 degraded vs 11 good injection runs. Compare the merge pair's distance and angle, Sim3 inliers, and whether the error comes right after the merge or from later drift.
> 3. Part D: when V1_03 completes, assemble and check it, run the overlap check, and write Part D frozen as in Part C; then stop for me to push. If it isn't complete by 6 Nov, record that in PREREG and drop Part D.

**3.** Bring `POSTHOC_E.md` back to the chat. Then: the README rewrite, a reproducibility pass, and the paper outline.

## Paper

- **Title:** "Proposal or Verification? Learned Place Recognition in ORB-SLAM3 Multi-Session Mapping".
- **Story:** three regimes:
  - no bottleneck (DBoW2 suffices);
  - proposal-limited (learned proposals rescue the merge);
  - verification-limited (correct proposals, rejected by geometry).
- **Venues:**
  - IROS 2027 main track (deadline **1 Mar 2027**, Florence);
  - ICRA 2027 workshops (accepted workshops announced 31 Jan 2027; paper deadlines likely Feb–Apr; Seoul, 24–28 May);
  - arXiv in mid-Feb.
- **Plan:** draft in Dec, guide review in Jan.

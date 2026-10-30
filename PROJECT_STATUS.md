# SLAM project status (26 Oct 2026)

Repo: github.com/Abxdj/6th_Sem_SLAMNAV.
- **`proposal-v2`** is the current branch. Part C results are pushed (`bdecde1`).
- Part E is committed locally (`b96908c` rule, `aaf06b1` pairs and plan). It may already be pushed. **No Part E run has started.**

ORB-SLAM3 changes are exported as `orb_slam3_patches/proposal_v2.patch`. The current build is `9aad4f8` (adds timing counters). Never push `~/ORB_SLAM3`.

Pre-registration lives in `results/proposal_v2/PREREG.md`. Rule: **push each Part to GitHub before its first run.**

## Established results

**1. Infrastructure.**
- The `ros_mono.cc` resize bug is fixed. KITTI 00 live median ATE 9.40 m vs 8.86 m standalone.
- The culled-keyframe redirect fixed the 95% proposal loss.
- Exclusion is now time-based.
- Descriptors are computed on the keyframe image.
- Every proposal's outcome is accounted for.

**2. Single-session and easy multi-session: DBoW2 saturates.**
- KITTI: 4–5 loops per run from DBoW2 alone.
- V1_01→V1_02: 12/12 merges.

**3. Pre-registered cross-map tests** (τ=0.8768, calibrated on MH_01→MH_03; arms control / load-only / injection, 10 runs each):

| Part | Pair | Control | Load-only | Injection | Notes |
|---|---|---|---|---|---|
| B | MH_02→MH_04 (overlap 0.127) | 4/10 | 2/10 | 9/10 (8 by learned) | Fisher **p=0.057** vs control, p=0.0055 vs load-only |
| C | MH_03→MH_05 (0.554) | 8/10 | 9/10 | 10/10 (5 by learned) | **Null.** CMH p=0.146, exact p=0.474 |
| C | MH_04→MH_02 (0.352) | 10/10 | 10/10 | 10/10 (4 by learned) | Learned merges happen at the same revisit DBoW2 uses |

- The prediction ("near zero effect where control usually merges") held in Part C. The other half ("large effect where control rarely merges") rests only on Part B.
- **Safety:** about 1,280 wrong proposals across Parts B and C, and 0 wrong merges. Every merge in every arm is within 2 m / 45° of ground truth.
- **Cost:** +0.20 to +0.56 ms per keyframe of place recognition (on a baseline of about 3.2 ms), mostly failed Sim3 attempts. The GPU descriptor cost comes on top.
- **ATE:** not improved in any test.

**4. Offline (fair Gate B, matched precision).**
- Learned beats raw DBoW2 top-1.
- ResNet18, DINO and EfficientNet are statistically tied. DINO costs more for nothing.

**5. Methodological lessons.**
- A GPU node perturbs ORB-SLAM3 through compute alone, so a load-matched control is needed.
- Within-session thresholds don't transfer across sessions.
- Keyframe culling silently drops external proposals.
- The Gazebo bag is limited by its route; use it for smoke tests only.

## Next session

**1. Part E: hard-pair replication.**
- Pairs: MH_02→MH_05 (0.140), MH_01→MH_04 (0.145), MH_01→MH_05 (0.166). All are labelled related.
- Caveat: all three revisit the **same spot** as Part B (about 25 s in). So this is a replication at one place, not a test of new places.
- 90 runs, about 8.5 h. Primary test: CMH injection vs control.
- **Tell Claude Code** (`claude --continue` in the repo):
  > "Approved: the full 90-run batch with a 9.5 h stopping cap. Add one line to Part E recording that ("Owner approved 9.5 h cap, <date>"), commit it, and stop. I'll push, then you start."
- Then `git push`, then "Pushed. Start." Run it overnight with the laptop plugged in and sleep turned off.

**2. How to read Part E.**
- Injection beats control where control often fails: the paper reports a narrow positive ("reliably closes a hard revisit") plus the null on easy pairs.
- Control merges most of the time: Part B was likely luck, and the paper is a clean, mostly negative, pre-registered study.

**3. Then stop experimenting and write the paper.**
- Working title: "Proposal or Verification? Learned Place Recognition in ORB-SLAM3 Multi-Session Mapping".
- Venue: an ICRA or IROS 2027 workshop, plus arXiv.

**4. Part D (V1_01→V1_03, independent).** Run only if the ETH download ever finishes; it's stuck on HTTP 429. It's registered as separate and not pooled.

**5. Later:**
- README update, then merge into master.
- Fill in the guide's name in the docs.
- Jetson Orin request.

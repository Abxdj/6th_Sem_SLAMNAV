# SLAM project status (16 Oct 2026)

Repo: github.com/Abxdj/6th_Sem_SLAMNAV.
- **`proposal-v2`** (pushed, at `8d70ad0`): the current work.
- `diagnosis` and `audit-snapshot`: older.
- `master`: still Phase 1; merge into it only after the README update.

ORB-SLAM3 changes are exported as `orb_slam3_patches/proposal_v2.patch` (against upstream `4452a3c`). The local branch `proposal-v2` is at `d641453`. Never push `~/ORB_SLAM3`.

## Findings so far

1. **Infrastructure bugs, now fixed.**
   - The `ros_mono.cc` 640x480 resize broke KITTI: live ROS went from 130–165 m to a median of 9.40 m, against 8.86 m standalone, n=3 each.
   - ORB-SLAM3 keyframe culling silently dropped 95% of external proposals. Fixed by redirecting to the surviving parent keyframe (at most 5 hops).
   - The count-based exclusion window gave temporal near-duplicates. It's now time-based.
   - Descriptors are now computed on the actual keyframe image.
2. **Single-session and easy multi-session: DBoW2 saturates.**
   - KITTI: 4–5 loops per run from DBoW2 alone.
   - V1_02: the one accepted learned loop is the same loop DBoW2 closes.
   - V1_01→V1_02: DBoW2 merged 12/12 runs. No headroom.
3. **Hard multi-session, MH_02→MH_04 (pre-registered, τ=0.8768 calibrated on MH_01→MH_03).**

   | Arm | Runs that merged |
   |---|---|
   | Injection | 9/10 (8 of them by the learned proposer) |
   | Control | 4/10 |
   | Load-only | 2/10 |

   - Injection vs control: Fisher **p=0.057**, the primary test, just missing 0.05. Injection vs load-only: p=0.0055.
   - All learned merges are correct by ground truth (0.57–0.84 m, about 32° viewpoint difference; DBoW2's merges are at about 9°).
   - 226 of 288 learned proposals failed Sim3, and none of them led to a merge. Verification safely rejects the wrong ones.
   - It's the same merge moment, closed more reliably (30% to 90%). There's no ATE gain.
   - Interpretation: in this case **proposal is the bottleneck**, not verification.
4. **Fair Gate B, offline, at matched precision:** learned is ahead of raw DBoW2 top-1 on MH_02→MH_04 (AP 0.455 vs 0.126 at 2 m) and on V1.
5. **Methodological lessons:**
   - A GPU node perturbs ORB-SLAM3 through compute alone (input frame drops 1.8% → 3.7%), so a load-matched control is needed.
   - Within-session thresholds don't transfer across sessions.
   - The Gazebo bag is limited by its route (blank walls) and has no ground truth: smoke tests only.

## Next (tomorrow)

1. **Generalisation test, with τ frozen at 0.8768.**
   - Offline: overlap check for MH_01→MH_05, MH_03→MH_05, MH_04→MH_02, and V2 pairs.
   - Offline: DINO and EfficientNet Gate B.
   - Write PREREG Part C, then **push it to GitHub BEFORE any run.**
   - 3 arms x 10 runs per pair. Primary test: CMH injection vs control.
   - The prompt for Claude Code is in the chat ("Good work. Approved, under these conditions...").
2. Rewrite the paper around the three findings above. Target venue: an ICRA or IROS 2027 workshop, plus arXiv.
3. Later: README update and merge into master, EuRoC standalone x3, a Gazebo re-record (optional).

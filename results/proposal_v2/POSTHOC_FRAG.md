# POST HOC: cross-session vs fragment merges in Parts B, C and E

**POST HOC, not pre-registered.** Written 2026-11-01, after all results were known. It was prompted by the Part D finding that most control merges joined two pieces of the V1_03 session rather than V1_03 to V1_01 (REPORT_XMAPD.md). It changes no pre-registered report, test or conclusion. Its p-values are for information only.

- **Script:** `tools/proposal_v2/posthoc_frag.py results/proposal_v2/posthoc/posthoc_frag.json`. It reads the run directories only.
- **Runs:** all 210 runs of Parts B, C, E and D (all three arms), 115 merges in total.

## Method
- **Merges:** every `[PROP] accepted list=merge` line in `mono.log`. In every run the count equals the number of `Merge finished` lines, so no merge is missed or double-counted.
- **Classes:**
  - **cross-session:** matched KF in session 1, current KF in session 2.
  - **fragment:** both KFs in session 2.
  - **s1-fragment:** both KFs in session 1.
- **Which session a KF belongs to:**
  - **Parts C, D, E (stamp method):** the KF's stamp from `kf_log.csv`, tested against each session's stamp interval (±1 s), from `session_bounds` in `pv2_summary.json`.
    - This is interval membership. A first version used "stamp ≤ session-1 end", the rule of the Part D breakdown. That rule misclassified every MH_04 → MH_02 merge as s1-fragment, because that pair runs backwards in time.
    - For forward-time pairs the two rules are the same, and the Part D counts are reproduced exactly.
  - **Part B (id method):** Part B has no `kf_log.csv`. A KF is in session 1 if its id is below the first session-2 KF id, which is the `First KF:<id>` line following `[SESSION] ChangeDataset requested` in `mono.log`. ORB-SLAM3 KF ids only increase.
- **Check of the id method:** both methods were applied to all 100 merges in Parts C, D and E. They **agree on 100/100**. Part B's classification relies on the id method alone.
- **Coverage:** no merge was left unclassified, and every run has a first session-2 KF id.

## Results

### Part B (MH_02 → MH_04), 15 merges: all cross-session

| arm | runs with any merge (pre-registered) | runs with ≥ 1 cross-session merge | cross-session merges (source) | fragment merges |
|---|---|---|---|---|
| control | 4/10 | **4/10** | 4 (dbow2) | 0 |
| load-only | 2/10 | **2/10** | 2 (dbow2) | 0 |
| injection | 9/10 | **9/10** | 9 (ext 8, dbow2 1) | 0 |

The tables are identical, so the tests are too. Fisher injection vs control is p = 0.057, as pre-registered. Against load-only it is p = 0.0055.

**Conclusion: unchanged.**

### Part C (high-overlap pairs), 57 merges: all cross-session

| pair | arm | runs with any merge | runs with ≥ 1 cross-session merge | cross-session merges (source) | fragment merges |
|---|---|---|---|---|---|
| MH_03 → MH_05 | control | 8/10 | **8/10** | 8 (dbow2) | 0 |
| | load-only | 9/10 | **9/10** | 9 (dbow2) | 0 |
| | injection | 10/10 | **10/10** | 10 (ext 5, dbow2 5) | 0 |
| MH_04 → MH_02 | control | 10/10 | **10/10** | 10 (dbow2) | 0 |
| | load-only | 10/10 | **10/10** | 10 (dbow2) | 0 |
| | injection | 10/10 | **10/10** | 10 (ext 4, dbow2 6) | 0 |

The tables are identical, so the tests are too. CMH injection vs control: p = 0.146, exact p = 0.474, as pre-registered.

**Conclusion: unchanged.** The null result at the ceiling stands.

### Part E (low-overlap pairs), 15 merges: all cross-session

| pair | arm | runs with any merge | runs with ≥ 1 cross-session merge | cross-session merges (source) | fragment merges |
|---|---|---|---|---|---|
| MH_02 → MH_05 | control / load-only | 0/10 / 0/10 | **0/10 / 0/10** | 0 | 0 |
| | injection | 10/10 | **10/10** | 10 (ext 9, dbow2 1) | 0 |
| MH_01 → MH_04 | control / load-only | 0/10 / 0/10 | **0/10 / 0/10** | 0 | 0 |
| | injection | 5/10 | **5/10** | 5 (ext 5) | 0 |
| MH_01 → MH_05 | all arms | 0/10 | **0/10** | 0 | 0 |

The tables are identical, so the tests are too. CMH injection vs control: χ² = 24.43, p = 7.7 × 10⁻⁷, as pre-registered. The prediction still fails on MH_01 → MH_05.

**Conclusion: unchanged.**

### Part D (V1_01 → V1_03), for reference: 28 merges, 14 cross-session, 14 fragment

| arm | runs with any merge | runs with ≥ 1 cross-session merge | cross-session (source) | fragment (source) |
|---|---|---|---|---|
| control | 7/10 | **2/10** | 2 (dbow2) | 6 (dbow2) |
| load-only | 6/10 | **3/10** | 3 (dbow2) | 3 (dbow2) |
| injection | 10/10 | **9/10** | 9 (ext 6, dbow2 3) | 5 (dbow2 4, ext 1) |

These are the same as the REPORT_XMAPD breakdown.

## What this means
- **Parts B, C and E are not affected.** Every one of their 87 merges joins session 2 to session 1. Their pre-registered "any merge" outcome was in practice the cross-session outcome, and none of their conclusions changes.
- **Part D is the only part with fragment merges.** It is also the only part where V1_03's tracking failures split session 2 into pieces that were later merged back together. On this pair, and only here, "any merge" and "cross-session merge" differ. The Part D post hoc breakdown is therefore specific to that pair, not a flaw shared with the earlier parts.
- **For any future pre-registration,** the outcome should be defined as a cross-session merge, classified as here, so that it does not depend on how stable tracking is on the chosen sequences.

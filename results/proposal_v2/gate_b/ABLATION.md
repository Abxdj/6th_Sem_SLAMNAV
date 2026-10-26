# Descriptor ablation on fair Gate B (offline, no live runs)

2026-10-26. Same keyframes, same ground truth and same DBoW2 raw top-1 scores as the ResNet18 Gate B (`MH02_MH04.json`, `V101_V102.json`): the 6 `T3_*_resnet18{,_dry}` runs per pair.

**Method**
- **Descriptors** were computed offline by `tools/proposal_v2/offline_descs.py`, with the live nodes' exact preprocessing: CLAHE(2.0, 8×8) at native resolution → GRAY2RGB → 224×224 → ImageNet normalisation → model → L2.
  - DINO ViT-S/8: CLS token, 384-d (`ros_nodes/loop_closure_dino.py`).
  - EfficientNet-B0: timm, pooled, 1280-d (`ros_nodes/loop_closure_efficientnet.py`).
- **Pipeline check:** the offline ResNet18 descriptors match the live node's dump on all 914 KFs of `T3_MH0204_r1_resnet18` (min cosine 1.00000).
- **Comparison:** `tools/proposal_v2/gate_b_compare.py`. It reports pooled recall at 90% / 95% precision (top-1, correct = distance < r and angle < 45°) and AP. The bootstrap resamples the 6 runs 2000 times.
- **Outputs:** `ablation_{MH02_MH04,V101_V102}.json`, plus per-descriptor `*_{dino,effnet}.{json,png}`.

## MH_02 → MH_04 (2525 queries)

| r | revisits | ResNet18 R@P90 / R@P95 / AP | DINO | EfficientNet | DBoW2 |
|---|---|---|---|---|---|
| 0.5 m | 8 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 1 m | 155 | 0.032 / 0.032 / 0.178 | **0.065** / 0.058 / 0.132 | 0.032 / 0.032 / **0.217** | 0 / 0 / 0.063 |
| 2 m | 372 | **0.043** / 0.043 / **0.455** | 0.032 / 0.024 / 0.339 | 0.030 / 0.019 / 0.350 | 0.013 / 0.013 / 0.126 |

## V1_01 → V1_02 (1361 queries)

| r | revisits | ResNet18 | DINO | EfficientNet | DBoW2 |
|---|---|---|---|---|---|
| 0.5 m | 656 | **0.146** / 0.117 / 0.388 | 0.114 / 0.070 / 0.338 | 0.099 / 0.091 / 0.374 | 0.043 / 0.037 / 0.256 |
| 1 m | 925 | 0.466 / 0.375 / 0.597 | 0.493 / **0.444** / 0.627 | **0.517** / 0.377 / **0.657** | 0.306 / 0.246 / 0.502 |
| 2 m | 1051 | **0.599** / 0.542 / 0.688 | 0.572 / 0.517 / 0.671 | 0.588 / **0.551** / **0.715** | 0.426 / 0.331 / 0.563 |

## Bootstrap (run-level, 95% interval of the difference in R@P90)

**Each learned descriptor vs DBoW2**

| | ResNet18 | DINO | EfficientNet |
|---|---|---|---|
| MH, 1 m | ahead, [0.008, 0.051] | ahead, [0.031, 0.095] | ahead, [0.010, 0.077] |
| MH, 2 m | ahead, [0.002, 0.104] | interval includes 0, [−0.011, 0.045] | interval includes 0, [−0.015, 0.050] |
| V1, all radii | ahead | ahead | ahead |
| AP, both pairs, 1 m and 2 m | ahead | ahead | ahead |

V1 intervals for R@P90 run from about +0.09 to +0.25 at 1 m and 2 m. At 0.5 m, DINO's interval is [−0.008, 0.162] and the other two exclude 0.

**Between the learned descriptors**
- No R@P90 difference between any two of the three learned descriptors excludes 0 at any radius on either pair.
- AP differences that do exclude 0 point in different directions:
  - MH, 1 m: EfficientNet > DINO.
  - MH, 2 m: ResNet18 > DINO and ResNet18 > EfficientNet.
  - V1, 1 m: EfficientNet > ResNet18, EfficientNet > DINO, and DINO > ResNet18.
  - V1, 2 m: EfficientNet > ResNet18 and EfficientNet > DINO.

## Reading
- **Learned vs DBoW2:** all three learned descriptors beat DBoW2's raw top-1 at matched precision. The exceptions are R@P90 for DINO and EfficientNet on MH at 2 m, and for DINO on V1 at 0.5 m, where the interval includes 0. On AP, all three are ahead everywhere.
- **No descriptor is best overall.** The ranking changes with pair, radius and metric. The R@P90 differences between them are all inside the bootstrap intervals, and the AP differences outside them point in different directions. ResNet18, the descriptor used live, is not worse than the other two at 90% precision on either pair. EfficientNet has higher AP on V1, and ResNet18 has higher AP on MH at 2 m. DINO is not better despite costing more compute.
- **Small absolute recall on MH_02→MH_04** for all methods: at most 0.065 at 90% precision.
- **Caveat on the intervals.** The 6 runs per pair replay the same two sequences. The bootstrap measures variation between runs in keyframe selection, not variation between scenes, so it understates the uncertainty about generalisation.
- **Not tested here:** none of this measures live behaviour. DINO and EfficientNet were not run in the live pipeline.
- The `descs_{dino,effnet}.npz` files in the run folders are not committed (about 70 MB). `offline_descs.py` regenerates them deterministically.

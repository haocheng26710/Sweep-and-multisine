# Results Figure Plan

## 1. Governing rules

All figures come from the frozen FORMAL-4 artifact set. WRITE-1 does not regenerate plots, recompute values, select frequencies, or change visual thresholds.

The primary band is 200–4000 Hz using actual valid points. The secondary 4000–8000 Hz region must be visually distinct and labelled as secondary/sensitivity evidence.

Figure captions must separate descriptive patterns, threshold exceedance, failed confirmatory criteria, and exploratory results. No caption may state that U4ENC was proved superior or that four directions were classified reliably.

## 2. Main-text sequence

| Proposed no. | Placement | Frozen source | Source SHA-256 | Purpose | Required boundary |
|---|---|---|---|---|---|
| Figure 1 | After Results §2 | `plots/repeatability_frequency.png` | `cbecef078ab5644bbccaa6330bd4aa712e80582d9c284547146e05f365f25a7a` | Establish CONT error across frequency | CONT is technical repetition, not independent N |
| Figure 2 | After Results §3 opening | `plots/block_direction_B01.png` to `B04.png` | See panel table below | Show AS01 direction medians and repeat ranges | Four panels are blocks, not four independent experiments |
| Figure 3 | After direction-pair result | `plots/direction_pairwise_heatmap.png` | `65ab9c9ac67f13e1a83a634a39f23330b9d72d3b0b8fb80bb7b8ace57009c5ea` | Identify pairs exceeding the CONT floor | Floor exceedance does not imply classification success |
| Figure 4 | After G result | `plots/effect_to_repeatability_ratio.png` | `fbef1738f425aaf58c68d03213d1cdb7e39dc45f46de63857cef771539e0ffe8` | Relate direction effects to technical noise | Ratio is descriptive; CI rules govern confirmation |
| Figure 5 | After Results §4 | `plots/configuration_difference.png` | `628df8a1848f8f137a7f9b59252531d515725f721d8027a6712929d9d09f65d0` | Show U4ENC−U4SYM difference curves | AS01 bounded; AS02 exploratory and confounded |
| Figure 6 | After Results §7 | `plots/outlier_sensitivity.png` | `f084cfc4b38a269411394e8f6439a5267d0104ed8e9004fff5c1171a2dd7a6b5` | Compare primary and sensitivity views | Flags remain ACTIVE; no selection changed |
| Figure 7 | After Results §6 | `plots/grouped_validation_confusion_matrix.png` | `f7b82802750145780277433a46cf5ecac3951648c9b0c2453fa2a7dbe407a71a` | Report the grouped-classification negative result | BA targets were not met; no random split |

Recommended narrative order is Figure 1, Figures 2–4, Figure 5, Figure 7, then Figure 6. Numbering may follow this narrative order even though Figure 6 is discussed after classification.

## 3. Figure 2 panel assembly

| Panel | Block/configuration | Frozen source | SHA-256 |
|---|---|---|---|
| A | B01 / U4SYM / AS01 / RP01 | `plots/block_direction_B01.png` | `39289581397dade6265dcfffd9f960cef5d2482d747c44f03757480f1ea808a2` |
| B | B02 / U4SYM / AS01 / RP02 | `plots/block_direction_B02.png` | `81f010b62281313e814cde95cd2c7b12a1994fb2e2811cdf983970e5f280dd5d` |
| C | B03 / U4ENC / AS01 / RP01 | `plots/block_direction_B03.png` | `25c1ca95aef79b9efb4e771f7965f9d33c44942cf347a01ca7b504274cff729d` |
| D | B04 / U4ENC / AS01 / RP02 | `plots/block_direction_B04.png` | `27c1c8313c2a184db18a7fbfc78fe2652ad992733facdecee6613ce6fb0bc8b4` |

At thesis-layout stage, these frozen images may be arranged as one four-panel plate without altering their data, axes, or annotations. The original files and hashes remain the evidence authority.

B05 and B07 plots may appear only in supplementary material labelled “AS02 exploratory”. They should not be added to the main AS01 plate or used as confirmatory replication.

## 4. Caption drafts

### Figure 1 — Continuous-repeat measurement floor

Frequency-dependent variation among CONT technical repeats. The primary 200–4000 Hz region provides the confirmatory floor; 4000–8000 Hz is secondary. CONT repeats quantify measurement error and are not independent scientific samples.

### Figure 2 — AS01 direction spectra by block

Robust median spectra and repeat ranges for four directions in two U4SYM and two U4ENC AS01 blocks. Panels preserve REPOS/block identity. Visible separation is descriptive until assessed against the CONT floor and G confidence intervals.

### Figure 3 — Pairwise direction effects

Primary-band pairwise direction distances relative to the global CONT p95 floor. U4ENC had 6/6 stable pairs and U4SYM 3/6 across both AS01 blocks. Exceeding the floor does not demonstrate reliable direction classification.

### Figure 4 — Direction effect relative to repeatability

Demeaned direction effects divided by the CONT p95 repeatability floor. Values above one indicate effects larger than the technical floor. Confirmatory interpretation remains governed by the frozen G and ΔG confidence-interval rules.

### Figure 5 — Configuration-difference spectra

U4ENC−U4SYM spectral differences with primary and secondary bands distinguished. AS01 provides bounded block-aware evidence. AS02 contains only one block per configuration and is exploratory because assembly, block, and time are confounded.

### Figure 6 — Outlier-flag sensitivity

Frozen metrics using all 72 ACTIVE curves compared with a temporary view omitting the 10 flagged curves. No threshold conclusion changed, and no curve was removed from the ACTIVE manifest.

### Figure 7 — Grouped direction classification

AS01 leave-one-block-out confusion matrices. Balanced accuracy was 0.375 for U4SYM and 0.250 for U4ENC, below the preregistered 0.500 target. The figure documents a negative classification result.

## 5. Table plan

| Proposed table | Source in `RESULTS_DRAFT.md` | Purpose |
|---|---|---|
| Table 1 | §2 repeatability table | Freeze median, IQR, and p95 for three bands |
| Table 2 | §3 G table | Report raw, demeaned, z-score, and 95% CI together |
| Table 3 | §6 classification table | Show BA, macro-F1, chance, and target |
| Table 4 | §7 sensitivity table | Demonstrate that flags did not change frozen decisions |

Tables are preferred over extra plots for these compact numeric comparisons. This avoids duplicating information already shown in Figures 1, 4, 6, and 7.

## 6. Source root and integrity

All plot paths are relative to:

```text
outputs/formal/FORMAL-4_CORE_ANALYSIS/
```

FORMAL-4 `artifact_manifest.json` SHA-256 is `6744b7142480a20a631ff6a33f763329e852b4086ba5f05d53301beb6853d4ef`. Its 28 listed artifacts were reverified before WRITE-1.

The governing FORMAL-5 figure index SHA-256 is `09218da6db038bfc3ad7325fcfb7aba6c6069691f71e4ed610f919ffd026e58f`. WRITE-1 changes placement and captions only, not figure content.

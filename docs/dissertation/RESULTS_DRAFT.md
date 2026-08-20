# Results

## 1. Evidence set and reporting boundary

This chapter reports the frozen FORMAL-3, FORMAL-4, and FORMAL-5 outputs only. No raw REW file was re-imported, no sample was reclassified, and no final-test content was read.

The analysis set contained 72 ACTIVE measurements in six blocks. Each block contained four directions and three CONT technical repeats. [F3-RM; F3-AM]

The 19 EXCLUDED records remained outside preprocessing, statistics, and classification. [F3-RM; F3-EM]

The six ACTIVE groups were B01/B02 U4SYM-AS01, B03/B04 U4ENC-AS01, B05 U4ENC-AS02, and B07 U4SYM-AS02. Each group contributed 12 curves. The 10 FORMAL-3 outlier flags remained ACTIVE. [F3-AM; F4-O]

All 72 FeatureSets shared the FORMAL-1 logarithmic grid. Of 256 grid locations, 255 were valid; the unsupported 200 Hz endpoint remained invalid rather than extrapolated. [F4-S; F4-RM]

The primary band contained 207 valid points from 202.909 to 3973.945 Hz. The secondary band contained 48 points from 4031.747 to 7947.890 Hz. Results below use the primary band unless stated otherwise. [F4-S]

CONT repeats were treated as technical repeats, not independent experimental units. Direction inference used block-aware summaries, and classification used leave-one-block-out grouped validation. [F4-RM; F5-CB]

## 2. Continuous-repeat measurement floor

The CONT repeatability floor was estimated from all pairwise RMS dB differences within each block×direction cell. The summary therefore represents the observed repeat distribution rather than a selected best repeat. [F4-R]

| Band | Median RMS (dB) | IQR (dB) | 95th percentile (dB) | Interpretation |
|---|---:|---:|---:|---|
| Primary, 200–4000 Hz | 0.3783 | 0.2191 | 0.8793 | Confirmatory measurement floor |
| Secondary, 4000–8000 Hz | 0.7687 | 0.3357 | 1.3452 | Secondary/sensitivity floor |
| Full valid band | 0.5057 | 0.2274 | 0.9162 | Descriptive full-band floor |

The secondary-band median and p95 were higher than their primary-band counterparts. Subsequent claims therefore prioritize the primary band and treat 4–8 kHz as secondary evidence. [F4-R]

Figure 1 should show repeatability error across frequency. Its role is to establish the measurement floor before any direction or configuration comparison is introduced.

## 3. Direction-related spectral differences

Within each block, the three CONT curves at each direction were reduced to a robust median curve. All six direction pairs were then compared using raw, demeaned, and z-score representations. [F4-DP; F4-DG]

Using the primary-band CONT p95 of 0.8793 dB, all six U4ENC direction pairs exceeded the floor in both AS01 REPOS blocks. Three of six U4SYM pairs met the same cross-block condition. [F4-DP; F4-S]

This result supports a measurement-level statement: direction changes produced spectral differences larger than the technical-repeat floor. It does not establish that every direction can be classified reliably. [F5-CB; F5-HD]

| Configuration | G_raw | G_demeaned | 95% CI for G_demeaned | G_zscore |
|---|---:|---:|---:|---:|
| U4SYM, AS01 | 0.6925 | 0.6824 | 0.6105–1.2699 | 0.7034 |
| U4ENC, AS01 | 1.2619 | 1.2805 | 0.8297–1.7667 | 1.3292 |

U4ENC retained a direction-to-REPOS ratio above 1 after demeaning and z-scoring. U4SYM remained below 1 in all three point estimates. These are descriptive point-estimate patterns. [F4-DG]

The frozen primary metric was `G_demeaned`. U4ENC reached 1.2805, while U4SYM reached 0.6824. The point-estimate difference was 0.5982. [F4-DG; F4-DC]

The U4ENC 95% CI was 0.8297–1.7667, so its lower limit did not exceed the frozen threshold of 1. The difference CI was -0.1131–1.0843, so it included 0. [F4-DG; F4-DC]

Accordingly, the confirmatory criteria were not fully met. H0 was not rejected and H1 was not confirmed, even though the U4ENC point estimate was higher. [F5-CB; F5-HD]

Figures 2–4 should present the block curves, pairwise distances, and effect-to-floor ratios. Captions must distinguish “exceeded the repeatability floor” from “passed the confirmatory G and CI criteria.”

## 4. U4ENC–U4SYM configuration differences

For AS01, comparisons retained the block structure: B01/B02 represented U4SYM and B03/B04 represented U4ENC. Each configuration therefore contributed two REPOS blocks. [F4-RM; F4-C]

The primary-band demeaned U4ENC–U4SYM differences exceeded the CONT p95 floor at all four directions. The direction-specific effect/floor ratios were 1.3381, 1.9169, 1.7530, and 1.3846. [F4-C]

The median AS01 effect/floor ratio was 1.5688. This supports a bounded claim that the two configurations produced measurably different spectra under AS01. [F4-C; F4-S]

This configuration result does not demonstrate superior direction encoding. The frozen direction-gain difference CI included 0, and grouped classification remained below its practical target. [F4-DC; F4-GV; F5-CB]

Figure 5 should show the U4ENC−U4SYM difference curves and mark primary and secondary bands. The AS01 trace is the bounded main result; AS02 must be labelled exploratory.

## 5. Assembly-set observations

AS01–AS02 differences exceeded the CONT floor for both configurations. In the primary band, the U4SYM effect/floor ratios ranged from 1.6675 to 1.9703, with median 1.9354. [F4-A]

For U4ENC, the corresponding range was 1.4144–1.7737, with median 1.7412. These magnitudes are descriptive observations rather than independent assembly effects. [F4-A]

Each configuration had only one AS02 block. Assembly set, acquisition block, and time therefore changed together. An unconfounded AS01–AS02 causal comparison was not estimable. [F4-A; F4-S; F5-CB]

AS02 and all-assembly results must be labelled exploratory wherever shown. They cannot be used to confirm H1 or replace the AS01 analysis.

## 6. Grouped direction classification

Classification used primary-band demeaned block×direction median curves. Leave-one-block-out validation kept all CONT repeats from the same block×direction on one side of each split. [F4-GV; F4-RM]

| Confirmatory AS01 scope | Balanced accuracy | Macro-F1 | Chance | Practical target | Decision |
|---|---:|---:|---:|---:|---|
| U4SYM | 0.375 | 0.250 | 0.250 | 0.500 | Target not met |
| U4ENC | 0.250 | 0.183 | 0.250 | 0.500 | Target not met |

U4SYM had permutation p=0.317 and U4ENC had p=0.760. Each AS01 result was based on two folds and eight grouped predictions, so uncertainty remained substantial. [F4-GV]

Neither configuration reached the frozen 50% balanced-accuracy target. The data therefore do not support reliable four-direction classification. [F4-GV; F5-CB]

The all-assembly U4ENC result reached balanced accuracy 0.500, but it mixed assembly and acquisition time across only three blocks. FORMAL-4 classified it as exploratory, so it cannot override the AS01 result. [F4-GV; F4-S]

Figure 7 should report the AS01 confusion matrices as a negative result. The caption must state the grouped protocol, number of folds, chance level, and unmet 50% target.

## 7. Outlier-flag sensitivity

Primary analysis retained all 72 ACTIVE curves, including all 10 outlier flags. Sensitivity analysis omitted flagged curves only in a temporary analysis view and did not alter either selection manifest. [F4-O; F4-S]

| Metric | All 72 ACTIVE | Sensitivity without flagged curves | Frozen conclusion changed? |
|---|---:|---:|---|
| Primary CONT median floor | 0.3783 dB | 0.3739 dB | No |
| U4SYM G_demeaned | 0.6824 | 0.7051 | No |
| U4ENC G_demeaned | 1.2805 | 1.2790 | No |
| ΔG_demeaned | 0.5982 | 0.5739 | No |
| AS01 configuration/floor ratio | 1.5688 | 1.4423 | No |
| U4SYM grouped balanced accuracy | 0.375 | 0.375 | No |
| U4ENC grouped balanced accuracy | 0.250 | 0.250 | No |

U4SYM’s stable direction-pair count decreased from three to two in the sensitivity view. The broader descriptive conclusion—some U4SYM pairs exceeded the floor—did not change. [F4-O; F4-S]

Figure 6 should show this sensitivity comparison. It must not imply that flagged curves were deleted or moved to EXCLUDED.

## 8. Integrated result

The frozen disposition is `supported_with_limits`. The measurements support direction-related spectral differences above the technical-repeat floor and an AS01 configuration difference above that floor. [F5-CB]

The evidence does not confirm that U4ENC is superior to U4SYM. The ΔG confidence interval included 0, the U4ENC confidence interval crossed 1, and grouped classification remained below 50%. [F4-DG; F4-DC; F4-GV]

H0 therefore remains `not_rejected`, and H1 remains `not_confirmed`. AS02 and all-assembly results remain exploratory because assembly, block, and acquisition time were confounded. [F5-CB; F5-HD]

The chapter-level conclusion is:

> Under ordinary-room and limited-repeat conditions, the encoded structure produced direction-related spectral changes above the measurement-repeatability floor. Its direction-effect point estimate exceeded that of the symmetric structure, but between-configuration uncertainty and direction-classification performance did not meet the preregistered confirmatory criteria.

## Evidence keys

| Key | Frozen artifact | SHA-256 |
|---|---|---|
| F3-RM | `FORMAL-3_REAL_IMPORT_QC/run_manifest.json` | `1ecf1179d66f654f1dadd0fc58eba60cdb956f92ca9c74983d7d6fb00c27afe9` |
| F3-AM | `FORMAL-3_REAL_IMPORT_QC/active_manifest.csv` | `c5acf6fef1fe8ede8c82add2682b8a2157c44b9578b636c9aa0eec08f00e8931` |
| F3-EM | `FORMAL-3_REAL_IMPORT_QC/excluded_manifest.csv` | `6aada4786be8062c024829347d1e43ef0bc414d6c05f0c6355b2ff476e20a793` |
| F4-RM | `FORMAL-4_CORE_ANALYSIS/run_manifest.json` | `f023c703907032df6dc2956cdf698767eb834f96f2aa1d7e612021f17990efdb` |
| F4-S | `FORMAL-4_CORE_ANALYSIS/analysis_summary.json` | `676bbb71a5860c633edadb68ff34da6c3a8e51b3d8438003be8bd2e489edb71f` |
| F4-R | `FORMAL-4_CORE_ANALYSIS/repeatability_summary.csv` | `1f7166f10ce2fe3730e7d37505617202c7b56db03c952b9d2b34f1b703f1c5e1` |
| F4-DP | `FORMAL-4_CORE_ANALYSIS/direction_pairwise_effects.csv` | `b35e38bd928bca75f9509b95266fe71a06866c9e25504c99e896ecc58d726d35` |
| F4-DG | `FORMAL-4_CORE_ANALYSIS/direction_gain_summary.csv` | `8d7791041ccd55067ed4abe3f4f5d1bf6e4a7ce0167887e9d2b31ff3c02f7dbf` |
| F4-DC | `FORMAL-4_CORE_ANALYSIS/direction_gain_contrasts.csv` | `8f77db86d1e9eb7de8a6adae6215461cfe9318d1a815637e7a07e463b6827b52` |
| F4-C | `FORMAL-4_CORE_ANALYSIS/configuration_effects.csv` | `9f96888e77f2964f6d2aedee7192c79ef449f31272a3773aeb95fcebb945de39` |
| F4-A | `FORMAL-4_CORE_ANALYSIS/assembly_set_effects.csv` | `de982dd667ee5035b9716d2b709be51901dbd98ce0fa448cbb33f72a4368016a` |
| F4-GV | `FORMAL-4_CORE_ANALYSIS/grouped_validation_metrics.csv` | `c9df8527c0f0947c8fb2be75205d54d7480c28942ea1cac95870d1a1be9030da` |
| F4-O | `FORMAL-4_CORE_ANALYSIS/outlier_sensitivity.csv` | `a4f9eecd6cc4c1d8338a44c14e427fdd55048bf5836feb5df3e6df37821683f7` |
| F5-CB | `FORMAL-5_FINAL_SYNTHESIS/final_claim_boundary.json` | `ff2f4e97edb841e48e6db246f8ec64a2115fd900437e1e88af3f446ac2e8384f` |
| F5-HD | `FORMAL-5_FINAL_SYNTHESIS/hypothesis_decision_table.csv` | `93f9ebc02cc3cbc6cca14e0d1e90b7c95e95394bdc59e0f76a94b0c738329ae7` |

All paths are relative to `outputs/formal/`. The FORMAL-4 and FORMAL-5 artifact manifests verified all referenced files before this chapter was drafted.

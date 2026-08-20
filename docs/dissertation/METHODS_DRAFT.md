# Methods Draft

## 1. Study design and frozen research question

This study compared directional frequency responses from a symmetric acoustic structure (`U4SYM`) and an internally asymmetric encoded structure (`U4ENC`).

The frozen question asked whether `U4ENC` produced repeatable direction-related spectral features after accounting for technical repeats, repositioning, reassembly, and overall level.

The confirmatory directions were 0°, 90°, 180°, and 270°. Sweep measurements were the formal measurement mode. Real Multisine/P8 analysis was outside the approved scope.

The protocol was frozen as rev-002 before the formal pilot. The main question, `G_demeaned`, success thresholds, four-direction scope, and grouped-validation rules were not changed after results were observed.

The final interpretation remains `supported_with_limits`, with `H0=not_rejected` and `H1=not_confirmed`.

## 2. Structures, assembly states, and repeated measurements

`U4SYM` was the symmetric reference configuration. `U4ENC` used an internally asymmetric morphology intended to create direction-dependent spectral shaping.

`AS01` and `AS02` denoted separate assembly states. `RP01` and `RP02` denoted repositioning rounds within an assembly state.

`CONT` denoted three consecutive sweeps without changing the fixed physical state. These were technical repeats and were not counted as independent scientific samples.

`REPOS` represented a repeated placement after repositioning. `REASM` represented a separately assembled state and captured assembly reconstruction together with any unresolved session or time effects.

The preregistered plan contained 96 sweeps: two configurations, four directions, three CONT repeats, two REPOS rounds, and two assembly states.

The frozen streamlined archive contained 72 ACTIVE measurements in six complete 12-measurement blocks and 19 EXCLUDED records. It did not retroactively complete the 96-sweep plan.

| Block | Configuration | Assembly | REPOS | Session | Directions × CONT | ACTIVE curves |
|---|---|---|---|---|---|---:|
| B01 | U4SYM | AS01 | RP01 | S01 | 4 × 3 | 12 |
| B02 | U4SYM | AS01 | RP02 | S01 | 4 × 3 | 12 |
| B03 | U4ENC | AS01 | RP01 | S02 | 4 × 3 | 12 |
| B04 | U4ENC | AS01 | RP02 | S02 | 4 × 3 | 12 |
| B05 | U4ENC | AS02 | RP01 | S03 | 4 × 3 | 12 |
| B07 | U4SYM | AS02 | RP01 | S04 | 4 × 3 | 12 |

AS01 retained two REPOS blocks per configuration. AS02 retained one block per configuration, so AS02 lacked a cross-REPOS denominator and remained exploratory.

## 3. Equipment and spatial conditions

Measurements used one iMM-6C microphone and REW V5.31.3 in one ordinary room. The same source, microphone, and nominal geometry were required within the frozen acquisition design.

The source-to-device-centre distance was targeted at approximately 0.8 m. The frozen repository evidence does not provide a completed geometry record that supports reporting a more precise achieved distance.

The protocol required the loudspeaker control, open-channel count, microphone insertion depth, structure height, cable routing, and room positions to remain fixed and to be photographed.

The evidence set does not establish an anechoic environment, a laboratory-grade source chain, or an independently replicated measurement space. [CITATION NEEDED: ordinary-room reflections in acoustic response measurement]

Windows audio enhancements, AGC, EQ, and spatial effects were required to be disabled. The protocol also required acquisition to stop if device, gain, geometry, or environmental-noise conditions changed.

## 4. Microphone calibration and evidence boundary

The registered microphone calibration file was `CMM29939.txt`. Its preserved size was 3,205 bytes and its SHA-256 was `421070ec6d41c1b92cb69f0f5e4e290f9644847d92d52590994a80ea9e17a11e`.

An audited REW screenshot showed the measurement input as the iMM-6C and listed `CMM29939.txt` in the separate Mic calibration files area. The input-binding status was therefore recorded as verified.

The REW TXT exports did not contain the calibration filename in each file header. FORMAL-3 preserved this as `calibration_file_header_unavailable` for all 72 ACTIVE records rather than inferring it.

The evidence supports a calibrated microphone-input binding record. It does not establish traceable absolute sound-pressure-level calibration for the complete loudspeaker–room–microphone chain.

Traceable absolute calibration for that complete chain was not available.

The distinction between microphone sensitivity correction and absolute system-level calibration should be retained. [CITATION NEEDED: measurement-microphone calibration and absolute SPL traceability]

## 5. Frozen REW acquisition settings

The formal protocol fixed the following controls before analysis.

The level controls were Windows output volume 50 and iMM-6C input volume 100.

| Setting | Frozen value |
|---|---|
| Software | REW V5.31.3 |
| Measurement | Sweep |
| Sample rate | 48 kHz |
| Sweep length | 256k |
| Repetitions | 1 |
| Timing reference | No timing reference |
| Time origin | IR peak |
| Capture range | 200–8000 Hz |
| Sweep level | -30 dBFS |
| Windows output volume | 50 |
| iMM-6C input volume | 100 |
| Raw REW smoothing | None |

FORMAL-3 verified REW version, sweep level, timing-reference state, raw smoothing, finite values, frequency ordering, and frequency coverage from every ACTIVE TXT header and curve.

`No timing reference` precluded a common-clock absolute-phase interpretation. The formal analysis therefore used magnitude spectra and did not promote phase to a confirmatory outcome.

## 6. Frozen selection and quality control

The immutable source was the streamlined REV003 ZIP with SHA-256 `cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb`.

Its internal root retained the name REV002. This was recorded as a metadata warning; the outer REV003 filename and frozen ZIP hash remained authoritative.

ACTIVE and EXCLUDED membership came only from the frozen archive structure. Curve shape, QC status, or downstream results were not used to revise membership.

All 72 ACTIVE files were structurally parseable, finite, strictly increasing in frequency, and compatible with the frozen REW settings. Each contained 21,300 points from 199.951172 to 7999.877930 Hz.

All 72 ACTIVE files carried one non-structural warning because the per-file calibration filename was unavailable. No ACTIVE file had a structural failure.

The 19 EXCLUDED records entered only the exclusion audit. Their sample identities did not enter preprocessing, repeatability statistics, feature construction, classification, or reported results.

FORMAL-3 flagged 10 of 72 ACTIVE curves using their RMS distance from the pointwise cell median and a threshold of median plus `3 × 1.4826 × MAD`.

Flags indicated unusual within-cell dispersion. They did not change ACTIVE/EXCLUDED, trigger automatic deletion, or redefine the primary analysis.

## 7. Formal preprocessing

Each ACTIVE curve was processed by `formal_log_grid_v1`. The common grid was logarithmic from 200 to 8000 Hz at 48 points per octave.

Interpolation was limited to continuous valid source segments. Internal missing or invalid gaps caused fail-closed rejection; they were not bridged, zero-filled, or replaced by a linear grid.

Smoothing followed interpolation and used a 1/12-octave band in the dB domain. At centre frequency `f_c`, the band extended from `f_c × 2^(-1/24)` to `f_c × 2^(1/24)`.

Grid points in that interval received equal weight. A complete interior kernel contained five points at 48 points per octave. Segment edges were truncated and renormalised without crossing an invalid gap.

This processing order and fractional-octave definition require a supporting methodological source in the dissertation. [CITATION NEEDED: fractional-octave smoothing and logarithmic frequency sampling]

The source bin below 200 Hz could not support interpolation at exactly 200 Hz. That grid point remained invalid rather than being extrapolated.

The shared valid grid therefore contained 255 points: 207 primary-band points from 202.909067 to 3973.944999 Hz and 48 secondary-band points from 4031.747360 to 7947.889997 Hz.

The primary band was defined as 200–4000 Hz and the secondary band as 4000–8000 Hz. The actual valid points above were used, with no extrapolation to nominal boundaries.

The generated `dense_raw_spl` FeatureSet was smoothed but not sample-normalised. Here, `raw` meant unnormalised after formal smoothing, not an unsmoothed TXT curve.

## 8. Repeatability and direction-effect measures

Within each block × direction cell, the three CONT curves generated three pairwise differences. RMS dB difference, median absolute difference, 95th-percentile absolute difference, pointwise MAD, and sample SD were retained.

The repeatability floor used all 72 CONT pairs across 24 cells. Its primary-band summary was the median, IQR, and 95th percentile of pairwise RMS dB differences.

Each block × direction was represented by the pointwise median of its three CONT curves. Four direction representatives then generated six direction pairs per block.

Direction distances were computed on raw, sample-demeaned, and sample-z-scored curves. Demeaning removed each curve's mean level before the RMS distance was evaluated.

The primary metric was:

```text
G_demeaned = median(within-block between-direction RMS)
             / median(matched-direction cross-REPOS RMS)
```

`G_raw` and `G_zscore` used the same ratio with their corresponding representations. `ΔG_demeaned` was `G_demeaned(U4ENC) − G_demeaned(U4SYM)`.

AS01 supported this ratio because each configuration had RP01 and RP02. AS02 had only one block per configuration, so its REPOS denominator was `not_estimable`.

A direction pair exceeded the technical-repeat floor when its demeaned RMS was greater than the primary CONT p95. Stability required the same pair to exceed that floor in both AS01 REPOS blocks.

Configuration effect/floor ratio divided the AS01 U4ENC–U4SYM demeaned RMS difference by the same primary-band CONT p95 and retained block-aware configuration representatives.

## 9. Confidence intervals and grouped classification

The 95% intervals for `G_demeaned` used 2,000 prespecified block-cluster plus direction-REPOS bootstrap resamples. `ΔG_demeaned` used a separate between-configuration bootstrap.

The cluster-aware resampling preserved the repeated-measure structure rather than treating CONT curves as independent observations. [CITATION NEEDED: cluster bootstrap for hierarchical repeated measurements]

Direction classification used nearest-centroid semantics on primary-band demeaned block × direction median curves.

Validation was leave-one-block-out. All CONT curves in a block × direction cell were aggregated before splitting and could not cross training and test boundaries.

Each AS01 configuration provided two folds and eight grouped predictions. AS02 classification was `not_estimable`; all-assembly classification was exploratory.

Each estimable scope used 999 deterministic label permutations within block. Balanced accuracy, macro-F1, confusion matrices, fold coverage, and permutation results were reported.

Chance was 0.25 for four directions and the frozen practical balanced-accuracy target was 0.50. [CITATION NEEDED: balanced accuracy and macro-F1 for multiclass evaluation]

## 10. Frozen decision rules and claim boundary

The direction-effect rules required `G_demeaned(U4ENC) > 1`, a higher U4ENC value than U4SYM, and `ΔG_demeaned > 0`.

For confirmatory interpretation, the U4ENC 95% interval lower bound also had to exceed 1 and the `ΔG_demeaned` interval lower bound had to exceed 0.

Direction structure had to remain after demeaning and z-scoring. Direction effects were also intended to exceed same-direction REASM variation.

Grouped balanced accuracy had to reach 0.50 under the frozen grouped protocol. Classification was auxiliary and could not replace the physical `G_demeaned`, uncertainty, or REASM criteria.

The frozen final disposition was `supported_with_limits`. H0 remained `not_rejected`; H1 remained `not_confirmed`.

## 11. Provenance, immutability, and data isolation

The formal analysis recorded `data_origin=real_experiment`, `dataset_role=research_analysis`, and `run_purpose=research_analysis`.

Every authority bundle used explicit manifests and SHA-256 values. FORMAL-3, FORMAL-4, and FORMAL-5 artifact-manifest hashes were independently rechecked before WRITE-2 assets were generated.

The active archive, frozen membership, FeatureSets, analysis tables, figures, and final claim boundary were immutable inputs to this writing stage. WRITE-3 did not scan raw directories or regenerate any result.

Pilot, simulated, external-reference, formal research, and final-test materials remained segregated. The final-test partition remained sealed with `final_test_read=false`.

The frozen state remains `scientifically_eligible=false`. This records unmet evidential and governance gates; it does not negate the integrity of the software run or the bounded observations.

Independent external backup was not documented as configured in the frozen governance evidence. The methods therefore do not claim that such a backup existed.

## Method authority map

| Topic | Frozen authority |
|---|---|
| Research question and thresholds | `docs/experiment/RESEARCH_QUESTION_AND_DECISION_RULES.md`; `RESEARCH_PROTOCOL_REV002.md` |
| Planned acquisition | `docs/experiment/FORMAL_ACQUISITION_PLAN_REV001.md` |
| Calibration evidence | `docs/progress/FORMAL_2A_FIX_MIC_INPUT_EVIDENCE.md` |
| Selection, QC, preprocessing | `docs/progress/FORMAL_3_REAL_DATA_IMPORT_QC.md` |
| Metrics, bootstrap, classification | `docs/progress/FORMAL_4_CORE_ANALYSIS.md` |
| Final claim boundary | `docs/progress/FORMAL_5_FINAL_SYNTHESIS.md` |
| Frozen figures and result tables | `docs/dissertation/FIGURE_AND_TABLE_MANIFEST.json` |

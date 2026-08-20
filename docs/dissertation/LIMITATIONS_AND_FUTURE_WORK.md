# Limitations and Future Work

## 1. Evidence status

The final disposition is `supported_with_limits`. H0 remains `not_rejected`, H1 remains `not_confirmed`, `scientifically_eligible=false`, and `final_test_read=false`.

The results are bounded research evidence from the retained formal Sweep archive. They are not a final validation of the device, the hypothesis, a deployed classifier, or real Multisine/P8 operation.

## 2. Ordinary-room acoustics

Measurements were made in one ordinary room rather than an anechoic or standardised acoustic facility.

Reflections, standing-wave structure, background noise, and small geometry changes may have contributed to the observed direction-dependent spectra.

The same environment can make a morphology effect measurable while also limiting attribution and generalisation. [CITATION NEEDED: room reflections, standing waves, and spatial response variability]

Future work should repeat the frozen design in more than one room and, where feasible, include controlled or treated-space measurements.

Room replication should be treated as an independent factor, not as additional CONT repeats within one physical state.

## 3. Source chain and level calibration

The experiment used a consumer-level loudspeaker and Windows audio chain. The frozen settings controlled nominal output and input levels but did not establish laboratory-grade source stability.

The iMM-6C input was linked to `CMM29939.txt` through audited REW evidence. However, the per-file REW TXT header did not record that filename.

The evidence does not provide traceable absolute sound-pressure-level calibration for the full measurement chain.

Results should therefore be interpreted as relative frequency-response differences in dB, not as certified absolute SPL measurements.

Future acquisition should record source-monitor levels and calibration state with each block. [CITATION NEEDED: uncertainty in consumer audio measurement chains]

## 4. One microphone and one measurement space

Only one iMM-6C microphone and one room were represented. Microphone-specific response, placement, and local room interaction cannot be separated from the present data.

Replication with independently calibrated microphones and spatially distinct measurement sites would test whether the observed pattern transfers beyond this setup.

Such replication should preserve immutable calibration files, device identifiers, geometry records, and per-block hashes.

## 5. Sample size and repeated-measure structure

The preregistered plan contained 96 sweeps. The frozen streamlined analysis contained 72 ACTIVE measurements and 19 EXCLUDED records.

The 72 ACTIVE curves formed six blocks. Each block contained four directions and three CONT technical repeats.

AS01 had two REPOS blocks per configuration, but AS02 had only one. Missing B06 and B08 prevented an AS02 cross-REPOS denominator.

Three CONT curves improve estimation of a fixed state but do not create three independent scientific observations.

The main uncertainty is therefore governed by the small number of independent blocks, repositioning rounds, assembly states, and sessions.

Future work should prioritise more independent REPOS and REASM blocks. Increasing only the number of consecutive sweeps would not resolve this limitation.

## 6. Directional coverage

The confirmatory scope used four orthogonal directions: 0°, 90°, 180°, and 270°.

This design tested coarse directional separation, not continuous azimuth estimation or generalisation to intermediate angles.

Eight-direction or continuous-angle studies would be exploratory unless separately preregistered with their own sample plan and thresholds.

## 7. Assembly, block, and time confounding

AS01 and AS02 were acquired in different blocks and sessions. AS02 also lacked the second REPOS round for both configurations.

Observed AS01–AS02 differences therefore combine assembly state with block, session, and acquisition-time effects.

They can be described as exploratory response changes but cannot isolate reassembly as the unique cause.

A future factorial schedule should interleave assembly states and collect at least two REPOS blocks per configuration and assembly.

## 8. Outlier flags and selection boundary

FORMAL-3 marked 10 ACTIVE curves for unusual within-cell dispersion. The primary analysis retained all 10.

The sensitivity view temporarily omitted flagged curves, but it did not edit ACTIVE/EXCLUDED and did not change any frozen threshold conclusion.

This policy avoids result-dependent deletion. It also means that unusual but structurally valid curves contribute to the primary uncertainty.

Future protocols may define richer QC diagnostics before data collection, but new rules must not be applied retrospectively to improve this result.

## 9. Classification performance

AS01 grouped balanced accuracy was 0.375 for U4SYM and 0.250 for U4ENC. Both were below the frozen 0.50 practical target.

The results used two folds and eight grouped predictions per configuration, leaving substantial uncertainty and limited class coverage.

The exploratory all-assembly score cannot replace the AS01 result because it mixes assembly and time.

Future classification work needs more held-out blocks, preregistered feature choices, and group-preserving validation. [CITATION NEEDED: sample-size requirements for grouped multiclass validation]

## 10. Final-test boundary

The final-test partition remains sealed. No WRITE-3 action accessed it, and the frozen state remains `final_test_read=false`.

This thesis draft therefore does not estimate performance on a final untouched evaluation set.

Any later access would require a separate preregistered authority, immutable model and preprocessing package, and an audited one-time evaluation procedure.

## 11. Meaning of `scientifically_eligible=false`

`scientifically_eligible=false` does not mean that parsing, preprocessing, analysis, or artifact verification failed.

It records that the full evidential and governance conditions for unrestricted scientific use were not met.

The confirmatory intervals and grouped-classification target were not fully satisfied. External backup, complete geometry/environment records, and other preflight governance evidence also remained incomplete.

The material can support limited and exploratory dissertation statements when the claim boundary is explicit. It cannot be promoted to unrestricted confirmation, deployment evidence, or final-test generalisation.

## 12. Data governance limitations

The frozen governance evidence did not document an independent external backup as configured and restored successfully.

The analysis artifacts were hash-audited and immutable, but this does not substitute for a complete independent raw-data backup process.

Future acquisition should establish primary storage, two independent backup locations, media independence, hash verification, and a documented restore exercise before measurement.

## 13. Priorities for future work

1. Replicate the four-direction Sweep protocol across additional rooms and independently calibrated microphones.
2. Add balanced REPOS and REASM blocks while keeping CONT as technical repetition only.
3. Use mechanical fixtures and complete geometry, environment, calibration, and source-monitor records.
4. Preserve immutable raw data with independent backups and recovery verification.
5. Preregister any revised morphology, feature set, classifier, and frequency-selection process before evaluation.
6. Retain grouped validation and a sealed final-test authority for any later predictive claim.
7. Treat real Multisine/P8 as a separate future protocol until its real-data gate is approved.

These priorities address stability, independent coverage, and prediction performance without changing the frozen interpretation of the present data.

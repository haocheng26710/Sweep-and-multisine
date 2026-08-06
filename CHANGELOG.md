# Changelog

All notable changes are recorded here. The project follows the versions fixed in DEV-0.

## 2.0.0-dev.18 — leakage-safe tone selection (unreleased)

- Incremented configuration schema to 2.17.0 and added a strict, disabled-by-default provisional P9-A eligibility, scoring, spacing and band-quota contract.
- Added hash-identified candidate universe and selection scope, explicit persisted sweep tone-projection FeatureSet inputs, exact P2-B and optional P4-B links, fold-local training hashes, and sealed final-test policy.
- Added auditable direction/CONT/REPOS/configuration/energy/repeatability/noise/excluded-band components, variance-ratio and weighted-rank scoring, and deterministic constrained greedy selection with a complete decision trace.
- Added typed selected-tone-set lifecycle, stable CSV/JSON/hash bundles, explicit CLI, immutable output directories, CSV/JSON consistency checks, and deterministic simulated E2E validation.
- Kept all DEV-C12 outputs `software_validation_only`, scientifically ineligible, non-deployable, and forbidden from final-test evaluation. P9-B/P9-C/P9-D and scientific conclusions remain closed.

## 2.0.0-dev.17 — calibrated multisine HR readout (unreleased)

- Incremented configuration schema to 2.16.0 and FeatureSet schema to 2.3.0; added disabled-by-default provisional P6-B mapping, coverage, energy, fraction, phase, and uncertainty policy.
- Added exact-scope persisted P3-C multisine inputs, authoritative P6-A lifecycle/file-hash linkage, exact P2-B linkage, final-test/provenance gates, and no raw-data or directory discovery.
- Added nearest-tone power and gap-safe calibrated-window trapezoidal readout with detuning, collision, missing/invalid-tone, coverage, and partial/complete energy-fraction audits.
- Added per-feature quality evidence and derivation links, `hr_band_energy` and `hr_energy_fraction` FeatureSets, stable CSV/JSON/PNG bundles, manifest hashes, failure-only outputs, CLI, and deterministic E2E validation.
- Kept phase magnitude-only, uncertainty unavailable, deployment disabled, absolute cross-mode energy comparability false, and all DEV-C11 outputs simulated/software-validation/scientifically ineligible.

## 2.0.0-dev.16 — P6-A auditable sweep resonance calibration (unreleased)

- Incremented configuration schema to 2.15.0 and added a strict, disabled-by-default provisional HR calibration contract with explicit per-resonator search, bandwidth, integration, drift, and energy-fraction rules.
- Added hash-identified `HRCalibrationScope`, explicit persisted dense-FeatureSet inputs, exact canonical-ready P2-B linkage, pooling/final-test/provenance gates, and no directory or raw-data discovery.
- Added deterministic prominence-based peak selection, interpolated half-power bandwidth/Q, CONT/REPOS/REASM drift, measured-band overlap, linear-power integration, and complete/partial `q_i` handling without crossing invalid gaps.
- Added typed calibration lifecycle state, stable CSV/JSON/PNG outputs, exact file and manifest hashes, round-trip verification, explicit/failure CLI paths, and deterministic simulated E2E validation.
- Kept DEV-C10 outputs `software_validation_only`, unfrozen, and scientifically ineligible. P6-B, `hr_band_energy`, P9, real threshold freezing, final-test evaluation, and scientific conclusions remain closed.

## 2.0.0-dev.15 — P5-B leakage-safe four-protocol cross-mode validation (unreleased)

- Incremented configuration schema to 2.14.0 and added fixed cross-mode protocols, allowed shape normalizations, sample-pooled mixed training, audit-only P4-B bias, disabled calibration, and sealed final-test policy.
- Added hash-identified `CrossModeClassificationScope`, explicit persisted matched-tone FeatureSet inputs, exact P2-B/P4-B links, and atomic physical-state cross-mode groups.
- Reused the P5-A fold predictor for sweep-to-sweep, multisine-to-multisine, sweep-to-multisine, and pooled sweep-plus-multisine-to-multisine under one frozen outer-fold assignment.
- Added training-only masks/transforms, compatibility and training-composition audits, unavailable test-tone handling, fold/macro/per-class/confusion metrics, and same-cohort transfer gaps.
- Added immutable CSV/JSON/hash bundles, an explicit CLI, LOSO/LORO/LOAO and provenance regressions, and a four-direction simulated E2E validation. P4-B bias is never applied and no calibration is fitted.
- Kept `final_test` sealed and every DEV-C9 artifact simulated/software-validation/scientifically ineligible; P6/P9 and scientific conclusions remain closed.

## 2.0.0-dev.14 — P5-A leakage-safe grouped direction classification (unreleased)

- Incremented configuration schema to 2.13.0 and added a strict provisional classification contract with fixed protocols/models, fold-local standardization, disabled PCA, and sealed final-test policy.
- Added hash-identified `ClassificationScope`, explicit persisted-FeatureSet inputs, exact P2-B linkage, single-mode contract gates, and research-provenance enforcement.
- Added LOSO, REPOS-only LORO, and REASM-only LOAO folds with training-only masks, transforms, templates, centroids, and logistic regression; missing test features remain unavailable without mask shrink or filling.
- Added stable prediction/fold/per-class/aggregate/confusion/audit CSVs, typed JSON, input/output/self hashes, immutable output directories, and failure manifests.
- Added separate dense-sweep and multisine-tone software-validation E2E runs; both remain simulated and scientifically ineligible. P5-B/P6/P9 remain closed.

## 2.0.0-dev.13 — P4-B band, configuration, and cross-mode metrics (unreleased)

- Incremented configuration schema to 2.12.0 and added strict provisional frequency-band, U4 comparison, cross-mode, and REPOS reliability policy.
- Added hash-identified `ComparisonAnalysisScope` and explicit persisted-FeatureSet input manifest; P4-B never reads raw TXT/WAV or discovers measurements from directories.
- Reused P4-A direction distances, effective rank, repeat-pair rules, and morphology gain on fixed band/common-tone masks.
- Added explicit one-to-one cross-mode metrics, per-tone multisine-minus-sweep bias, development/training-only reliability, and supplemental weighted distances without tone selection or calibration.
- Added stable CSV/JSON/manifest bundles, input/output/self-hash verification, failure manifests, CLI/E2E validation, and canonical P2-B fail/pass gate tests.
- Kept all DEV-C7 validation data simulated/software-validation/scientifically ineligible; all bands and thresholds remain provisional.

## 2.0.0-dev.12 — P2-B cross-measurement dataset quality gate (unreleased)

- Incremented the configuration schema to 2.11.0 while keeping measurement and FeatureSet schemas unchanged.
- Added an explicit, hash-identified dataset scope and input manifest; P2-B never discovers measurements by scanning directories.
- Added expected-condition completeness checks, robust same-condition outlier evidence, and strictly separated CONT/REPOS/REASM repeatability checks.
- Added stable JSON/CSV dataset-QC bundles with input/output SHA-256 verification and failure-only manifests for invalid inputs.
- Required canonical cohort P4 analysis to reference an exact, canonical-ready P2-B result while retaining provisional P4-A software-validation tests.
- Kept all DEV-C6 validation data simulated/software-validation and scientifically ineligible; all dataset-QC thresholds remain provisional.

## 2.0.0-dev.3 — P8-A simulated synchronization and magnitude recovery (unreleased)

- Incremented the configuration schema to 2.2.0 while keeping measurement and feature schemas unchanged.
- Added normalized preamble cross-correlation, manifest-driven transient discard, and complete-period extraction.
- Added per-period tone FFT transfer recovery with explicit complex-spectrum or power averaging.
- Added sparse-tone `SpectrumData` output with `relative_unreliable` phase and no dense interpolation.
- Added stimulus/recording hash, tone-set, nominal sample-rate, period, and manifest-layout consistency failures.
- Added configurable non-period-aligned delay to S3 mock recordings; all P8-A inputs remain simulated software-validation data.

## 2.0.0-dev.2 — P1 REW import (unreleased)

- Incremented the measurement schema to 2.2.0 while keeping config and feature schemas unchanged.
- Added flexible, hash-checked REW frequency-response TXT import returning dense `SpectrumData`.
- Added explicit malformed-input, impedance, unknown-type, and manual-review error paths.
- Added synthetic parser fixtures and three byte-immutable external-reference regressions.
- Prevented external references from carrying fabricated experiment identity metadata.

## 2.0.0-dev.1 — provenance guard (unreleased)

- Incremented configuration and measurement schemas to 2.1.0.
- Added explicit data origin, dataset role, source hash, provenance record, and scientific-eligibility metadata.
- Added `software_validation` and `research_analysis` run purposes with a safe validation default.
- Added a research hard gate: only eligible `real_experiment` inputs can enter research analysis.
- Added structured provenance and raw-input hashes to dual-mode mock artifacts.

## 2.0.0-dev.0 — DEV-A (unreleased)

- Added canonical, versioned `MeasurementMeta`, `SpectrumData`, and `FeatureSet` objects.
- Added explicit V1 configuration migration to `measurement_mode: rew_sweep`.
- Added dual-input configuration files and metadata template.
- Added deterministic P7 Schroeder-phase multisine generation framework.
- Added S3 matching sweep/multisine mock generation from one known transfer function.
- Added initial schema, config, stimulus, and mock regression tests.

No `v1.0.0-sweep` tag exists yet because a stable sweep implementation has not been completed.

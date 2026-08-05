# Changelog

All notable changes are recorded here. The project follows the versions fixed in DEV-0.

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

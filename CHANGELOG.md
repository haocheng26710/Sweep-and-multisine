# Changelog

All notable changes are recorded here. The project follows the versions fixed in DEV-0.

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

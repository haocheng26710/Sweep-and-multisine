# Changelog

All notable changes are recorded here. The project follows the versions fixed in DEV-0.

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

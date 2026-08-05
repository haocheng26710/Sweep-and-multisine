# Migration from V1 sweep to the V2 dual-input schema

This document is intentionally incremental. DEV-B closes the tested P1 dual-input entry path; DEV-C1 adds P2-A single-measurement QC. P2-B, P3–P6, and P9 remain later stages.

## Existing V1 configuration

An unversioned configuration without `measurement_mode` is resolved in memory as:

```yaml
measurement_mode: rew_sweep
```

The source YAML is never rewritten. The resolved run configuration records a migration warning and the V2 schema versions.

An older configuration without `run_purpose` resolves in memory to the safe default:

```yaml
run_purpose: software_validation
```

`research_analysis` must be selected explicitly and is still subject to the per-measurement research hard gate.

## Measurement schema 2.0 to 2.1

Measurement schema 2.1 adds required `data_origin`, `dataset_role`, `source_sha256`, `provenance_uri`, and `eligible_for_scientific_analysis` fields. Missing provenance is never inferred. In particular, an old `rew_txt` path is ambiguous between an external parser fixture and a real experiment, so it must be reclassified from its immutable source record and hashed before import.

The only scientifically eligible origin is `real_experiment`. `external_reference` remains parser/format validation data and `simulated` remains software-validation data.

## Measurement schema 2.1 to 2.2

Measurement schema 2.2 permits experiment-identity fields to be null only for `external_reference` data and actively rejects those fields when populated on an external reference. This prevents official sample curve names from being recast as project `device_version`, `configuration`, `angle_deg`, `session_id`, `repeat_type`, `repeat_id`, grouping IDs, or `experiment_step`.

`simulated` and `real_experiment` metadata retain the original required experiment fields. Existing 2.1 external-reference artifacts must be re-created from their immutable source and provenance record rather than filled with placeholder experiment values.

## Configuration schema 2.1 to 2.2

Configuration schema 2.2 makes P8-A synchronization and period aggregation explicit. A multisine estimation block must use `synchronization_method: preamble_cross_correlation` and select `period_averaging: complex_spectrum` or `power`. No averaging mode is inferred from older multisine artifacts.

P8-A remains limited to `simulated` / `software_validation`. Existing real multisine recordings are not upgraded into research inputs by this migration; their clock relationship, provenance, sidecar linkage, and P8-B QC must be established separately.

## Configuration and measurement schema 2.2 to 2.3

Configuration schema 2.3 validates the complete `multisine_estimation.clock_drift` block. `warning_ppm` and `exclude_candidate_ppm` must be finite and satisfy `0 < warning_ppm < exclude_candidate_ppm`; `correction` must be `disabled` or `enabled`. Threshold equality is inclusive: warning begins at `warning_ppm`, and exclusion candidacy begins at `exclude_candidate_ppm`.

Measurement schema 2.3 adds the structured `SpectrumData.quality_metrics.clock_drift` view used by P8-B1. It records the signed estimate, configured thresholds, pre-correction decision, correction method and ratio, residual estimate, fit errors, pre/post magnitude change, final decision, and phase-state decision. A `drift_corrected` phase is not evidence of a shared sampling clock and is never migrated to `common_clock`.

P8-B1 remains restricted to `simulated` / `software_validation`. Existing 2.2 real recordings are not silently corrected or made scientifically eligible; they still require explicit real-experiment provenance, the research hard gate, and the remaining P8-B2 tone-quality checks.

## Configuration and measurement schema 2.3 to 2.4

Configuration schema 2.4 replaces the provisional three-key `tone_quality` block with explicit sections for FFT neighborhoods, clipping, local-bin SNR, leakage, missing-tone decisions, period stability, and non-excited energy. Every numeric threshold must be finite; bin counts and radii are validated; warning/exclusion order is enforced. Configuration 2.3 version markers are migrated to 2.4 in memory and produce a migration warning without rewriting the source YAML. A multisine configuration must still supply the full 2.4 `tone_quality` block before P8-B2 analysis.

Measurement schema 2.4 adds structured P8-B2 content under `SpectrumData.quality_metrics`: exact per-tone metrics/status/reasons, clipping counts and fractions, missing-tone summary, non-excited energy, aggregation policy, and the resolved QC configuration. CSV files remain views; the serialized `SpectrumData` is authoritative. Tone values are retained, `MeasurementMeta.valid` is not changed automatically, and `valid_mask` identifies tone-level exclusion candidates without converting sparse tones into a dense response.

P8-B2 does not make an older or simulated recording scientifically eligible. The only current P8 path remains `simulated` / `software_validation` / `eligible_for_scientific_analysis=false`; real-experiment QC thresholds must be frozen under a separate approved validation step.

## Configuration schema 2.4 to 2.5

Configuration schema 2.5 adds the canonical stimulus-root path used by the P1 multisine adapter: `paths.stimuli`. The adapter resolves `<paths.stimuli>/<stimulus_id>/stimulus_manifest.json` and rejects a non-canonical explicit manifest or stale sidecar pointer. It does not infer stimulus identity, tone set, period, or channel from the recording filename.

Configuration 2.3/measurement 2.3 and configuration 2.4/measurement 2.4 version markers migrate in memory to configuration 2.5/measurement 2.4. The source YAML is not rewritten. Measurement schema remains 2.4 because DEV-B5 changes orchestration and run-manifest contracts, not `MeasurementMeta` or `SpectrumData` fields. Pipeline version is `2.0.0-dev.6`; S3 mock schema is 1.3 because sidecars now explicitly include stable and discarded period counts.

The DEV-B run manifest has its own schema version (`1.0.0`). It records the version quartet, Git state, normalized mode, provenance, stimulus and recording identity, config/input/artifact hashes, phase/QC state, timestamps, random state, failure details, and explicit P1/P7/P8/P2-P6 stage gates.

## Configuration schema 2.5 to 2.6

Configuration schema 2.6 replaces the old placeholder `quality_control` keys with a versioned, provisional P2-A policy for both `rew_sweep` and `schroeder_multisine`. It defines minimum valid points, required frequency coverage, magnitude warning/exclusion bounds and dynamic range, phase policy, required-unavailable policy, and the P8 check IDs required by multisine aggregation. Numeric values must be finite; frequency and magnitude bounds, dynamic-range limits, and warning/exclusion ordering are validated.

Configuration 2.3/measurement 2.3, configuration 2.4/measurement 2.4, and configuration 2.5/measurement 2.4 markers migrate in memory to configuration 2.6/measurement 2.4 without rewriting source YAML. Measurement schema remains 2.4 because the new typed QC model has its own schema (`1.0.0`) and does not add fields to `MeasurementMeta` or `SpectrumData`. Pipeline version is `2.0.0-dev.7`.

Run-manifest schema 1.1 adds `qc_schema_version`, records `P2=completed` on successful import paths, and separates the remaining `P3_P6=not_implemented` gate. Canonical multisine runs rename the P8 summary view to `p8_measurement_qc.csv`; the unified P2 summary owns `measurement_qc.csv`. The shared P2 bundle also contains `quality_control.csv`, `qc_checks.csv`, and `quality_control.json`.

P2-A does not reclassify historical data, infer missing provenance, alter `MeasurementMeta.valid`, delete points/tones, or turn `exclude_candidate` into a human exclusion. Simulation thresholds remain provisional and cannot be migrated into frozen real-experiment thresholds.

## Existing sweep names and commands

Names such as `V2_U4SYM_A000_S01_CONT_R01.txt` remain valid. The sweep command remains:

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4.yaml
```

Without `--input`, the command still validates and resolves configuration only. With `--input`, `--metadata`, and `--run-id`, it routes REW through the P1 REW adapter or multisine through the P1/P8 adapter, executes shared P2-A, and writes a canonical run bundle. P3–P6 remain an explicit `not_implemented` stage gate.

## New grouping fields

Legacy rows may lack `reposition_round_id`, `assembly_id`, and `acquisition_block_id`. The migration layer must preserve these as missing and emit a warning. It must not infer them from `repeat_type`, filename order, or neighboring rows. Validation schemes that require a missing group are unavailable for that dataset.

## Outputs

V1 outputs remain read-only. DEV-C1 writes new runs under `outputs/<data_origin>/<run_purpose>/<run_id>/` (or `outputs/quarantine/<run_id>/` when metadata cannot be resolved) and refuses to overwrite an existing directory. Failure paths retain the available config, measurement/QC views, input inventory, hashes, and run manifest without writing a false success marker.

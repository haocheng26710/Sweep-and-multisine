# Migration from V1 sweep to the V2 dual-input schema

This document is intentionally incremental. DEV-A establishes compatibility rules; later stages will add tested P1 adapters.

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

## Existing sweep names and commands

Names such as `V2_U4SYM_A000_S01_CONT_R01.txt` remain valid. The sweep command remains:

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4.yaml
```

The command still validates and resolves configuration only. The P1 module now provides direct, tested REW TXT import; routing it through the complete P2–P6 run remains a later stage.

## New grouping fields

Legacy rows may lack `reposition_round_id`, `assembly_id`, and `acquisition_block_id`. The migration layer must preserve these as missing and emit a warning. It must not infer them from `repeat_type`, filename order, or neighboring rows. Validation schemes that require a missing group are unavailable for that dataset.

## Outputs

V1 outputs remain read-only. V2 will always create a new `outputs/<run_id>/` and refuse to overwrite an existing run directory.

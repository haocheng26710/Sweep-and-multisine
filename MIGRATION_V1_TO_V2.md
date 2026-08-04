# Migration from V1 sweep to the V2 dual-input schema

This document is intentionally incremental. DEV-A establishes compatibility rules; later stages will add tested P1 adapters.

## Existing V1 configuration

An unversioned configuration without `measurement_mode` is resolved in memory as:

```yaml
measurement_mode: rew_sweep
```

The source YAML is never rewritten. The resolved run configuration records a migration warning and the V2 schema versions.

## Existing sweep names and commands

Names such as `V2_U4SYM_A000_S01_CONT_R01.txt` remain valid. The sweep command remains:

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4.yaml
```

During DEV-A this command validates and resolves configuration only. P1 execution begins after real REW TXT fixtures are available.

## New grouping fields

Legacy rows may lack `reposition_round_id`, `assembly_id`, and `acquisition_block_id`. The migration layer must preserve these as missing and emit a warning. It must not infer them from `repeat_type`, filename order, or neighboring rows. Validation schemes that require a missing group are unavailable for that dataset.

## Outputs

V1 outputs remain read-only. V2 will always create a new `outputs/<run_id>/` and refuse to overwrite an existing run directory.


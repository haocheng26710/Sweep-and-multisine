# Acoustic Encoder Analysis

An auditable Python pipeline for testing whether an internal acoustic morphology helps one microphone distinguish incident directions. The software must preserve negative results and separate directional differences from continuous-repeat, repositioning, and reassembly error.

## Current stage

DEV-A is implemented. It provides the project skeleton, versioned canonical schemas, configuration validation, a deterministic P7 Schroeder-phase multisine generator, matching dual-input mock data, and initial tests.

It does **not** yet claim to analyze real measurements:

- The REW parser is deliberately not frozen before real TXT samples are supplied.
- P8 synchronization/transfer estimation begins in DEV-B.
- P2–P6 FeatureSet analysis and P9 begin in DEV-C.
- Mock data are prohibited as research evidence.

No `v1.0.0-sweep` tag exists yet because there is not yet a stable, real-sample-verified sweep implementation.

## Architecture

```text
REW TXT ----------------> dense SpectrumData ----+
                                                  +--> FeatureSet --> P4/P5/report
Multisine WAV --> P8 --> sparse SpectrumData ----+
```

`MeasurementMeta`, `SpectrumData`, and `FeatureSet` are authoritative. CSV and DataFrame outputs are views. P4 and P5 will accept only `FeatureSet`, never raw TXT or WAV.

Internal measurement modes are exactly:

- `rew_sweep`
- `schroeder_multisine`

The UI alias `schroeder_chirp` is accepted at configuration load time but is normalized before any artifact is written.

## Environment

Python 3.11 or newer is required.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

An editable package install is optional because the provided scripts add `src/` explicitly:

```powershell
python -m pip install -e .
```

## DEV-A commands

Validate the unchanged sweep command and resolved configuration:

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4.yaml --validate-only
```

Generate the broadband multisine stimulus:

```powershell
python scripts/generate_multisine.py --config config/stimulus_multisine_broadband.yaml
```

This creates `data/stimuli/<stimulus_id>/` containing:

- `stimulus.wav`
- `stimulus_manifest.json`
- `tones.csv`
- `stimulus_preview.png`
- `waveform_hash.txt`

Generate matching mock sweep and multisine inputs:

```powershell
python scripts/make_mock_data.py
```

Run tests:

```powershell
python -m pytest
```

## P7 signal definition

For `M` tones sorted by ascending frequency, tone ordinal `m = 0, ..., M-1` uses:

```text
phi_m = -pi * m * (m - 1) / M
```

Every configured tone must lie on an integer DFT bin of the configured period. The complete WAV consists of pre-silence, an optional synchronization preamble, a gap, complete settling periods, complete analysis periods, and post-silence. Fade is applied only to the preamble; no fade or window modifies an analysis period. The exact formula, sample boundaries, crest factor, target peak, schema versions, and WAV SHA-256 are written to the manifest.

## Measurement names and metadata

Legacy sweep names remain valid:

```text
V2_U4SYM_A000_S01_CONT_R01.txt
V2_U4ENC_A180_S02_REASM_R03.txt
```

Recommended multisine name:

```text
V2_U4SYM_A000_S01_REPOS_R01_MS.wav
```

Each multisine WAV should have a sidecar containing `stimulus_id`, stimulus hash, tone set, sample rate, period, stable-period count, channel, and complete experiment grouping. The authoritative metadata template is `data/metadata/measurements.csv`.

Missing `reposition_round_id`, `assembly_id`, or `acquisition_block_id` is never inferred. A validation scheme that needs a missing group is reported as unavailable.

## Real REW sample gate

Before DEV-B freezes P1, provide 1–3 real REW Frequency Response TXT exports. Prefer:

1. one export containing phase;
2. one without phase, if that occurs in practice;
3. any export showing a different real comment, delimiter, or column-name form.

Do not rename or edit these examples. The parser will use them as immutable test fixtures and will send ambiguous files to manual review rather than guessing.

## Scientific safeguards

- Raw inputs are read-only and run outputs never overwrite an existing run.
- QC reports `valid`, `warning`, or `exclude_candidate`; it never silently deletes data.
- Missing REW headroom/noise information is `unavailable`, not guessed.
- Tone selection, calibration, standardization, PCA, templates, and tuning use training data only.
- Session, reposition round, assembly, and acquisition block boundaries are explicit.
- Multisine phase is not used by default unless a common clock or recorded drift correction passes QC.

See `MIGRATION_V1_TO_V2.md` and `docs/DEV_A_TEST_AND_MOCK_PLAN.md` for migration and stage details.


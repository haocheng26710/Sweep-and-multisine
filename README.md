# Acoustic Encoder Analysis

An auditable Python pipeline for testing whether an internal acoustic morphology helps one microphone distinguish incident directions. The software must preserve negative results and separate directional differences from continuous-repeat, repositioning, and reassembly error.

## Current stage

DEV-A, the provenance guard, P1 REW import, P8-A multisine magnitude recovery, and P8-B1 clock-drift handling are implemented. They provide versioned canonical schemas, configuration validation, deterministic P7 generation, matching dual-input mock data, a research hard gate, format-validated REW import, and auditable preamble-synchronized sparse-tone transfer recovery.

It does **not** yet claim to analyze real measurements:

- The REW parser is frozen only against three external-reference exports and synthetic edge cases; no project `real_experiment` measurement has been analyzed.
- P8-B1 remains software-validation-only; clipping, tone SNR, leakage, missing-tone, and off-tone-energy QC remain in P8-B2.
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

To exercise a non-period-aligned recording start:

```powershell
python scripts/make_mock_data.py --recording-delay-samples 1379
```

To exercise signed sampling-clock drift independently of that fixed delay:

```powershell
python scripts/make_mock_data.py --recording-delay-samples 1379 --sampling-clock-drift-ppm 80
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

## P8-A/P8-B1 simulated multisine estimation

`load_multisine_measurement(recording_path, stimulus_manifest_path, meta, run_purpose=..., period_averaging=...)` uses the P7 stimulus WAV and manifest. It locates the known preamble by normalized cross-correlation, discards the manifest-declared initial periods, and extracts exactly the declared number of complete stable periods.

Each period is transformed independently. At every manifest tone bin the transfer is `H(f_k) = Y(f_k) / X(f_k)`. `period_averaging` is explicit: `complex_spectrum` averages the complex per-period transfer, while `power` returns the RMS transfer magnitude. The result is a `sparse_tones` `SpectrumData`; off-tone bins are not interpolated into a dense physical response.

P8-A verifies recording and stimulus hashes, stimulus ID, tone set, nominal sample rate, period length, and manifest layout across metadata, sidecar, WAV, and manifest. It accepts only `simulated` inputs under `software_validation`.

P8-B1 optionally accepts the resolved `multisine_estimation.clock_drift` mapping. It estimates signed drift from the phase advance between adjacent stable periods. With correction disabled, configured warning and exclusion-candidate thresholds are reported but phase remains `relative_unreliable`. With correction enabled, the recording time axis is resampled, preamble synchronization and tone estimation are repeated, and the estimated drift, correction ratio, residual drift, fit errors, and pre/post magnitude change are recorded under `SpectrumData.quality_metrics.clock_drift`. Only successful correction with residual QC below the warning threshold can produce `phase_status=drift_corrected`; this status is never represented as `common_clock`.

Missing-tone, clipping, SNR, leakage, off-tone-energy, and complete tone-quality outputs remain explicitly unavailable until P8-B2. Sparse tones are never interpolated into a dense physical response.

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

## P1 REW frequency-response import

`load_rew_measurement(path, meta, run_purpose=...)` accepts two-column frequency/magnitude and three-column frequency/magnitude/phase exports. Comment lines may begin with `*` or `#`; numeric fields may be separated by spaces, TABs, commas, or semicolons. The parser discovers the numeric block and uses semantic SPL/impedance markers rather than matching one literal REW header.

P1 requires a matching source SHA-256, at least five finite strictly increasing frequencies, consistent column count, and metadata with no unresolved manual-review reasons. Impedance exports are rejected from the acoustic SPL path. Unknown data types stop for manual review rather than being guessed from the filename.

Three user-provided exports from REW official sample measurements are copied byte-for-byte under `tests/fixtures/rew/external_reference/` and locked by `manifest.json`: `Artist 3 + Q2070Si.txt`, `REL Sub, No EQ.txt`, and `BW M1.txt`. They validate parser format only. They are not project experiments and carry no fabricated device, configuration, angle, session, repeat, or experiment-step metadata.

## Provenance and research hard gate

Every `MeasurementMeta` explicitly records one of three data origins:

- `external_reference`: official sample data used only as a `parser_fixture`;
- `simulated`: generated data used only for `software_validation`;
- `real_experiment`: experiment data declared as a `research_input`.

The metadata also records the raw input SHA-256, a provenance record URI, and `eligible_for_scientific_analysis`. These values are validated as one schema; a mock format cannot be relabelled as real data, and non-real data cannot be marked scientifically eligible.

Run purpose is independently explicit: `software_validation` is the safe default, while `research_analysis` passes the hard gate only when at least one input is present and every input is an eligible `real_experiment`. Official reference curves and simulated data can validate parsing or software behavior, but cannot support scientific conclusions.

## Scientific safeguards

- Raw inputs are read-only and run outputs never overwrite an existing run.
- QC reports `valid`, `warning`, or `exclude_candidate`; it never silently deletes data.
- Missing REW headroom/noise information is `unavailable`, not guessed.
- Tone selection, calibration, standardization, PCA, templates, and tuning use training data only.
- Session, reposition round, assembly, and acquisition block boundaries are explicit.
- Multisine phase is not used by default unless a common clock or recorded drift correction passes QC.
- Missing provenance is never inferred from a filename, source format, or neighboring metadata. Older artifacts must be reclassified from their source records before use with measurement schema 2.3.

See `MIGRATION_V1_TO_V2.md` and `docs/DEV_A_TEST_AND_MOCK_PLAN.md` for migration and stage details.

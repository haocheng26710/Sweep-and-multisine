# Acoustic Encoder Analysis

An auditable Python pipeline for testing whether an internal acoustic morphology helps one microphone distinguish incident directions. The software must preserve negative results and separate directional differences from continuous-repeat, repositioning, and reassembly error.

## Current stage

DEV-B is complete as a software-validation entry-point slice. DEV-C1 adds the shared P2-A single-measurement QC core. DEV-C2/C3 add deterministic common-grid preprocessing and auditable dense smoothing. DEV-C4 adds hash-verified matched-tone `FeatureSet` construction for sweep projection and direct P8 sparse-tone measurement without rereading TXT/WAV or recomputing P1/P2/P8.

It does **not** yet claim to analyze real measurements:

- The REW parser is frozen only against three external-reference exports and synthetic edge cases; no project `real_experiment` measurement has been analyzed.
- P8 remains software-validation-only. P8-B2 thresholds are provisional simulation thresholds and are not frozen for real experiments.
- P2-A, dense P3-A/P3-B, and paired P3-C matched-tone features are implemented. Cross-measurement P2-B, P4–P6, and P9 remain later slices.
- Mock data are prohibited as research evidence.

No `v1.0.0-sweep` tag exists yet because there is not yet a stable, real-sample-verified sweep implementation.

## Architecture

```text
REW TXT ----> P1 REW adapter ----------------> dense SpectrumData --> shared P2-A --> P3-A/P3-B --> sweep tone projection --+
                                                                                                                        +--> matched P3-C FeatureSets
WAV + sidecar + P7 manifest --> P1 adapter --> P8 --> sparse tones --> shared P2-A --> direct sparse tone alignment ------+
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

## DEV-C commands

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

Manifest schema 1.1 records both the exact `tones.csv` SHA-256 and a canonical tone-set SHA-256 over ordered `(tone_index, frequency_hz, dft_bin)` identities. Formal P3-C construction rejects legacy unhashed tone artifacts rather than silently reconstructing or sorting them.

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

Execute one canonical multisine validation run (the configured `paths.stimuli` must contain the sidecar-declared `stimulus_id`):

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4_multisine.yaml --input <recording.wav> --metadata <recording.json> --output-root outputs --run-id <run_id>
```

The mode-locked command uses the same dispatcher and executor:

```powershell
python scripts/analyze_multisine.py --config config/experiment_v2_u4_multisine.yaml --input <recording.wav> --metadata <recording.json> --output-root outputs --run-id <run_id>
```

Both commands execute P2-A. Dense sweep inputs then execute P3-A and the configured P3-B smoothing; sparse multisine inputs record both stages as `not_applicable_sparse` and are never interpolated into a dense response. With `smoothing.method=none`, `P3_B=not_requested`; with a non-none method and successful preprocessing, `P3_B=completed`. Because a single-measurement run cannot form a cross-mode pair, it records `P3_C=paired_run_required`. `P4_P6` remains `not_implemented`.

Run the deterministic paired DEV-C4 validation:

```powershell
python scripts/run_matched_tone_validation.py --run-id DEV-C4_P3C_FINAL
```

This generates only `simulated/software_validation` inputs and matched outputs. It refuses an existing run directory and never marks the result scientifically eligible.

## P7 signal definition

For `M` tones sorted by ascending frequency, tone ordinal `m = 0, ..., M-1` uses:

```text
phi_m = -pi * m * (m - 1) / M
```

Every configured tone must lie on an integer DFT bin of the configured period. The complete WAV consists of pre-silence, an optional synchronization preamble, a gap, complete settling periods, complete analysis periods, and post-silence. Fade is applied only to the preamble; no fade or window modifies an analysis period. The exact formula, sample boundaries, crest factor, target peak, schema versions, WAV SHA-256, `tones.csv` SHA-256, and canonical tone-set SHA-256 are written to the manifest. `manifest tone_index` is the sole authoritative order; CSV rows must already be contiguous in that order and their frequencies must also be strictly increasing.

## P8 simulated multisine estimation and QC

`load_multisine_measurement(recording_path, stimulus_manifest_path, meta, run_purpose=..., period_averaging=...)` uses the P7 stimulus WAV and manifest. It locates the known preamble by normalized cross-correlation, discards the manifest-declared initial periods, and extracts exactly the declared number of complete stable periods.

Each period is transformed independently. At every manifest tone bin the transfer is `H(f_k) = Y(f_k) / X(f_k)`. `period_averaging` is explicit: `complex_spectrum` averages the complex per-period transfer, while `power` returns the RMS transfer magnitude. The result is a `sparse_tones` `SpectrumData`; off-tone bins are not interpolated into a dense physical response.

P8-A verifies recording and stimulus hashes, stimulus ID, tone set, nominal sample rate, period length, and manifest layout across metadata, sidecar, WAV, and manifest. It accepts only `simulated` inputs under `software_validation`.

P8-B1 optionally accepts the resolved `multisine_estimation.clock_drift` mapping. It estimates signed drift from the phase advance between adjacent stable periods. With correction disabled, configured warning and exclusion-candidate thresholds are reported but phase remains `relative_unreliable`. With correction enabled, the recording time axis is resampled, preamble synchronization and tone estimation are repeated, and the estimated drift, correction ratio, residual drift, fit errors, and pre/post magnitude change are recorded under `SpectrumData.quality_metrics.clock_drift`. Only successful correction with residual QC below the warning threshold can produce `phase_status=drift_corrected`; this status is never represented as `common_clock`.

P8-B2 uses the final stable periods from P8-B1 and the original selected WAV channel. It counts float or integer-PCM clipping samples and runs; estimates local-bin per-tone SNR and leakage while excluding configured tone guards and other legal tones; reports complex- or power-based period variance; distinguishes missing tones from unavailable decisions; and measures non-excited-bin energy without including the preamble. QC changes neither `MeasurementMeta.valid` nor the stored tone values. Excluded candidates remain present and are identified through tone status and `SpectrumData.valid_mask`.

All P8-B2 thresholds and FFT neighborhoods are under `multisine_estimation.tone_quality` in YAML. `analyze_multisine_measurement(...)` returns the authoritative sparse `SpectrumData`, per-tone records, measurement QC, the final period estimate, and clipping evidence. The lower-level `write_multisine_qc_outputs(...)` default remains compatible with `measurement_qc.csv`; canonical pipeline runs call it with `p8_measurement_qc.csv` so the shared P2 view can own `measurement_qc.csv`. Sparse tones are never interpolated into a dense physical response.

The lower-level P8 diagnostic writer remains available for focused P8 development:

```powershell
python scripts/run_multisine_qc.py --recording <recording.wav> --stimulus-manifest <stimulus_manifest.json> --sidecar <recording.json> --output-directory outputs/<run_id>
```

It is not the canonical DEV-C run lifecycle. Canonical validation runs use `run_pipeline.py` or `analyze_multisine.py`, refuse an existing run directory, isolate output by `data_origin/run_purpose`, and write `config_snapshot.yaml`, `run_manifest.json`, input/artifact hashes, the measurement index, all P8 artifacts, the four shared P2 views, and explicit downstream stage gates.

## P2-A shared single-measurement QC

`evaluate_measurement_quality(SpectrumData, quality_control_config, run_purpose=...)` produces one immutable `MeasurementQCResult` containing typed `QCCheckResult` rows. Check status is one of `valid`, `warning`, `exclude_candidate`, or `unavailable`; measurement aggregation is order-independent with `exclude_candidate > warning > valid`. A required unavailable check is promoted to a measurement warning only when configured, while the check itself remains `unavailable`.

P2 records schema/provenance, valid-point count, frequency coverage, magnitude bounds, and phase consistency. For REW, absent headroom, noise floor, waveform, impulse-response, and window evidence remain unavailable. For multisine, P2 translates P8 clipping, drift, non-excited energy, and per-tone SNR/leakage/stability/missing-tone evidence without rerunning FFT. Manual-review reasons and `MeasurementMeta.valid` remain separate from automatic QC and are never overwritten.

All P2 thresholds live under `quality_control` in `config/default.yaml` and are explicitly provisional. Canonical runs write `quality_control.csv`, long-form `qc_checks.csv`, one-row `measurement_qc.csv`, and nested `quality_control.json` from the same result object. `SpectrumData` and `MeasurementMeta` remain authoritative; these files are audit views.

## P3-A/P3-B dense sweep features

`build_dense_feature_sets(SpectrumData, MeasurementQCResult, preprocessing_config)` accepts only `representation=dense_spectrum`. It verifies that the P2 result belongs to the same sample, mode, origin, role, and human-validity record, then carries the complete P2/manual-review provenance into every output `FeatureSet`. P3 does not automatically remove warning, exclusion-candidate, or human-invalid samples; later selection policy remains a separate responsibility.

The common grid is built from exact decimal endpoints and an exact step count, not floating-point `np.arange`. The default inclusive grid is 1000–8000 Hz at 10 Hz spacing (701 features). Linear interpolation uses only the immediate original neighbors when both are valid and their gap does not exceed `maximum_interpolation_gap_hz`; it never extrapolates or bridges an invalid point. Invalid output positions remain `valid_mask=false` with `NaN` values.

The fixed order is analysis-band target selection, common-grid interpolation, smoothing, sample-local normalization, then `FeatureSet`. Smoothing runs in dB and independently within each maximal contiguous valid segment; it never fills an invalid point with zero or borrows across a gap. `truncate` renormalizes physically available weights, `nearest` clamps to the same segment edge, and `reflect` mirrors inside the same segment without repeating its edge. A target becomes invalid when its pre-extension kernel coverage is below `minimum_kernel_coverage`.

Supported methods are `none`, `moving_average_linear_hz`, `gaussian_linear_hz`, and `fractional_octave`. Moving-average Hz widths map to a centered odd sample count. Gaussian uses explicit `sigma_hz` and `truncate_sigma`. For 1/N-octave smoothing, bounds are `fc * 2**(-1/(2*N))` and `fc * 2**(1/(2*N))`; the current fixed weighting is uniform over included points on the linear common grid in dB. Requested and effective kernels, boundary policy, coverage, and formulas are stored in the preprocessing manifest and canonical hash.

P3 emits `dense_raw_spl`, `dense_demeaned_db`, and `dense_zscore`. Here `raw` means smoothed but not normalized; it does not mean unsmoothed. Raw SPL is allowed only when `magnitude_quantity=spl`; a transfer ratio is not renamed as physical SPL, although its sample-local de-meaned and z-score views may be generated. De-meaning and z-scoring use only smoothed valid points inside `normalization_band_hz`; z-score uses population standard deviation (`ddof=0`). These are per-sample transforms, not training-set standardization.

Dense canonical runs add `processed/feature_index.csv`, `feature_schema.json`, `preprocessing_manifest.json`, `preprocessing_failures.csv`, and NPZ/JSON pairs under `processed/features/<feature_kind>/`. The stable `preprocessing_id` is a SHA-256 of the canonical semantic configuration. Artifacts are hash-audited, use no pickle, round-trip through `FeatureSet`, and refuse an existing processed directory.

## P3-C matched tone features

P3-C loads one hash-verified `ToneSetDefinition` from `stimulus_manifest.json` and its sibling `tones.csv`. `tone_index` is authoritative; rows are never silently sorted. The loader validates contiguous indices, finite strictly increasing and unique frequencies, unique integer DFT bins, the sample-rate/period bin equation, tone count, `tone_set_id`, resolved stimulus frequencies, and both tone hashes.

Sweep projection always follows `SpectrumData -> P3 common grid -> P3 smoothing -> tone extraction -> tone normalization`. `single_point_linear` reads an exact grid point or interpolates in dB between the immediate valid neighbors; it never extrapolates or crosses an invalid gap. `narrowband_integration` converts dB to linear power ratio, integrates piecewise-linear power over the configured full bandwidth, divides by actually covered bandwidth, and returns dB. Coverage, contributing points, and boundary interpolation are audited; positive-width overlap between neighboring tone bands is rejected.

Multisine tone features consume the P8 `sparse_tones SpectrumData` directly. Missing tones retain their authoritative positions as `NaN/valid_mask=false`; unexpected tones fail, and no sparse-to-dense spectrum is constructed. P8 phase status, source magnitude semantics, QC linkage, and tone-set hashes remain traceable. P8 currently provides no validated reliability-weight formula, so `reliability_weights` remains `None` rather than being filled with synthetic ones.

Both paths call the same sample-local normalization implementation: `none`, `subtract_mean_db`, or `zscore_within_sample`. Missing tones do not enter mean or population-standard-deviation calculations. Tone schema matching requires identical tone ID/hash, canonical names, order, length, units, and normalization; it never reindexes a mismatched pair. The common-valid mask is a separate AND view and does not modify either FeatureSet.

Matching schema does not imply absolute physical comparability. With `normalization=none`, absolute comparison is allowed only for compatible non-empty magnitude references or a shared explicit calibration ID with the same magnitude quantity. Normalized features remain shape-only candidates and preserve any original SPL/transfer-ratio reference mismatch. P3-C does not fit an affine calibration.

Paired output is written under `processed/features/tone_projection_from_sweep/` and `processed/features/tone_measurement_from_multisine/` with `tone_feature_index.csv`, `matched_tone_schema.json`, `matched_tone_audit.csv`, `preprocessing_failures.csv`, and a hash-audited `preprocessing_manifest.json`. The directory is immutable and the FeatureSet NPZ format uses `allow_pickle=False` on load.

## P1 multisine adapter and unified dispatcher

`acoustic_encoder.p1_adapters.load_multisine_measurement(recording_wav, sidecar_metadata, stimulus_manifest, resolved_config)` reads the sidecar, resolves `data/stimuli/<stimulus_id>/stimulus_manifest.json` from `paths.stimuli`, validates IDs, hashes, tone set, sample rate, period counts, channel, and source format, then delegates synchronization, clock drift, transfer estimation, and QC to the existing P8 implementation. It returns the same canonical `SpectrumData` type as the REW adapter, with `representation=sparse_tones`.

The dispatcher selects only from normalized `measurement_mode=rew_sweep` or `schroeder_multisine`. It never infers stimulus parameters from a WAV filename. Missing or inconsistent sidecars/manifests fail explicitly; declared manual-review reasons stop before P8. `phase_status` is authoritative in `SpectrumData`; CSV fields are derived views.

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
- Missing provenance is never inferred from a filename, source format, or neighboring metadata. Older artifacts must be reclassified from their source records before use with measurement schema 2.4.
- A completed DEV-B run is still not a scientific result. P8 accepts only `simulated/software_validation`, and official REW references remain `external_reference/parser_fixture`.

See `MIGRATION_V1_TO_V2.md` and `docs/DEV_A_TEST_AND_MOCK_PLAN.md` for migration and stage details.

# Migration from V1 sweep to the V2 dual-input schema

This document is intentionally incremental. DEV-B closes the tested P1 dual-input entry path; DEV-C1 adds P2-A single-measurement QC; DEV-C2/C3 add dense preprocessing; DEV-C4 adds matched-tone FeatureSets; DEV-C5 adds provisional P4-A descriptive metrics; DEV-C6 adds explicit-scope P2-B dataset QC; DEV-C7 adds provisional band/configuration/cross-mode P4-B metrics; DEV-C8/C9 add provisional leakage-safe P5 validation; DEV-C10/C11 add simulated P6 calibration/readout; DEV-C12 adds provisional P9-A tone selection; DEV-C13 adds simulated P9-B projection ablation and minimum-tone validation; DEV-C14 adds simulated fold-local P9-C bridge calibration; DEV-C15 adds frozen-package, persisted-P8-only offline single-measurement readout; DEV-C16 adds the final T0–T3 pre-experiment software acceptance and DEV-D entry documentation; DEV-UI1 adds the desktop orchestration shell; DEV-UI2 adds hash-audited single-measurement registration and software-validation execution; DEV-UI3 adds immutable experiment planning, explicit cohort registration, P2-B orchestration and guarded P4–P6 launchers without changing research contracts. All completed UI validation evidence remains simulated/external-reference and does not authorize deployment or scientific analysis.

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

## Configuration schema 2.6 to 2.7 and feature schema 2.0 to 2.1

Configuration schema 2.7 replaces placeholder preprocessing keys with the complete provisional P3-A contract: preprocessing schema version, exact analysis band and common-grid step, linear interpolation, maximum interpolation gap, minimum valid-grid fraction, normalization band, minimum normalization-point count, minimum z-score standard deviation, and an explicit smoothing method. The default grid has inclusive endpoints from 1000 through 8000 Hz at 10 Hz spacing. A band span that is not an exact multiple of the step is rejected.

Configuration 2.3/measurement 2.3/feature 2.0, configuration 2.4/measurement 2.4/feature 2.0, configuration 2.5/measurement 2.4/feature 2.0, and configuration 2.6/measurement 2.4/feature 2.0 markers migrate in memory to configuration 2.7/measurement 2.4/feature 2.1. Source YAML is not rewritten. The retired single `preprocessing.normalization` selector produces a migration warning because P3-A now emits raw, de-meaned, and z-score FeatureSets explicitly.

Feature schema 2.1 adds an optional, backward-compatible source-QC snapshot to `FeatureSet`: aggregate status, canonical QC hash, warning/exclusion/unavailable reasons, and downstream eligibility. A 2.0 artifact without these keys still loads with the fields unavailable. The new fields do not override `MeasurementMeta.valid` or create a second QC authority.

Run-manifest schema 1.2 records the dense preprocessing status and ID. Successful dense sweep runs record `P3_A=completed`; sparse multisine runs record `P3_A=not_applicable_sparse`. `P3_B=not_implemented` and `P4_P6=not_implemented` remain explicit. P3-A never converts sparse tones into a dense physical response.

The canonical preprocessing hash is insensitive to YAML key order and numeric presentation. P3-A permits `dense_raw_spl` only for a source explicitly labelled `magnitude_quantity=spl`; transfer-ratio data are not migrated or relabelled as SPL. All P3-A thresholds remain software-validation provisional values, not frozen real-experiment policy.

## Configuration schema 2.7 to 2.8 and preprocessing schema 1.0 to 1.1

Configuration 2.8 and preprocessing 1.1 make the smoothing domain and method-specific fields explicit. The only current domain is `db`. Supported definitions are `none`; moving average with `window_hz`; Gaussian with `sigma_hz` and `truncate_sigma`; and fractional octave with positive integer `fraction_denominator` plus `weighting_definition=rectangular_uniform_linear_grid_db`. Every non-none method also requires `boundary` and `minimum_kernel_coverage`.

The old ambiguous root key `smoothing_hz`, Gaussian `window_hz`, and fractional-octave `fraction` are rejected. A 2.7/preprocessing-1.0 configuration using `method=none` migrates in memory to 2.8/1.1 with `smoothing_domain=db` and a warning; its source YAML is not rewritten. A legacy non-none definition is rejected because no earlier non-none algorithm existed whose meaning could be preserved safely.

The order is fixed as target analysis band, common-grid interpolation, per-valid-segment smoothing, sample-local normalization, and `FeatureSet`. No boundary method crosses `valid_mask=false`. Moving requested/effective sample widths, Gaussian effective kernel span, fractional-octave analytic bounds and snapped sample counts, boundary policy, coverage rule, and dB-domain semantics are included in preprocessing manifest 1.1 and `preprocessing_id`. `dense_raw_spl` now means smoothed but unnormalized.

Pipeline version is `2.0.0-dev.9`; run-manifest schema 1.3 records P3-B as `not_requested`, `completed`/failure, or `not_applicable_sparse`. Feature and measurement schemas remain 2.1 and 2.4 because smoothing changes preprocessing semantics rather than the serialized `FeatureSet` or `SpectrumData` field layout.

## Configuration schema 2.8 to 2.9 and feature schema 2.1 to 2.2

Configuration 2.9 adds the provisional `matched_tone_features` contract. It fixes the sole authoritative order as `manifest_tone_index`, selects `single_point_linear` or explicitly defined linear-power `narrowband_integration`, selects one sample-local tone normalization, and sets minimum valid/common-tone counts. Method-specific fields are strict: single-point extraction accepts no bandwidth fields, while narrowband extraction requires a positive full bandwidth, `integration_domain=linear_power_ratio`, coverage in `(0, 1]`, and `overlap_policy=reject`.

Configurations carrying the 2.8/measurement-2.4/feature-2.1 version quartet migrate in memory to 2.9/2.4/2.2 and receive the explicit default matched-tone contract. Source YAML is not rewritten. The previous multisine-only `features.normalization` placeholder is retired in favor of the shared `matched_tone_features.normalization` block used identically by both modes.

Feature schema 2.2 adds tone-specific audit fields: canonical tone-set SHA-256, tone-schema ID, normalization method, source magnitude quantity/reference, source phase status, and reliability-weight source. Existing dense FeatureSets remain backward compatible because these fields are required only for the two tone FeatureKinds. Tone FeatureSets require a hash-verified P7 manifest/CSV pair and do not silently construct missing identity data.

P7 stimulus-manifest schema 1.1 adds `tones_sha256` and `tone_set_sha256`. The latter hashes the ordered tone identity `(tone_index, frequency_hz, dft_bin)` together with `tone_set_id`, sample rate, and period length. Legacy manifest 1.0 artifacts without these hashes are not silently upgraded for formal P3-C use; rerun P7 from the reviewed stimulus configuration. P8 now consumes the same verified tone definition and records its hashes under `SpectrumData.quality_metrics.tone_set`.

The two P3-C preprocessing IDs remain source-specific: sweep projection includes its dense P3 preprocessing ID and extraction definition, while multisine records direct sparse P8 alignment. A separate `tone_schema_id` proves that ordered names, units, tone identity, and normalization are identical across the two FeatureSets. Equal schema does not imply equal absolute physical reference.

Run-manifest schema 1.4 adds `P3_C`. Single-measurement runs record `paired_run_required`; the explicit paired validation runner owns P3-C construction. Pipeline version is `2.0.0-dev.10`. Measurement schema remains 2.4 because P3-C adds FeatureSet and preprocessing-output semantics rather than changing `MeasurementMeta` or `SpectrumData` layout.

## Configuration schema 2.9 to 2.10 and P4-A metrics schema 1.0

Configuration 2.10 adds the strict, provisional `direction_metrics` block: common-valid-feature count/fraction, minimum direction count, explicit effective-rank centering, repeatability distance, and morphology-gain distance/minimum denominator. A 2.9/measurement-2.4/feature-2.2 configuration migrates in memory to 2.10 and receives these defaults; an already explicit DEV-C3 smoothing definition is preserved exactly and the source YAML is not rewritten.

P4-A has independent version-1.0 schemas for `AnalysisScope` and `metrics_manifest.json`. It accepts only compatible, already-created `FeatureSet` objects selected by explicit sample IDs or a hash-frozen partition. It does not read source TXT/WAV, accept `SpectrumData`, discover a directory, align names, resample, or fill invalid values. Configuration, feature kind, preprocessing ID, feature schema, names/order, units, representation, provenance, and tone identity where applicable must agree.

Direction statistics use the logical intersection of all selected `valid_mask` arrays. Repeat pairs retain CONT, REPOS, and REASM as separate audited definitions. Morphology gain uses the median between-direction sample-pair distance divided by the median within-direction REPOS distance; neither CONT nor REASM can substitute for the denominator. Effective rank uses singular values directly: `p_i=sigma_i/sum(sigma)` and `exp(-sum(p_i log p_i))` over positive proportions.

Pipeline version `2.0.0-dev.11` and run-manifest schema 1.5 introduced separate `P4_A`, `P4_B`, and `P5_P6` gates. Feature and measurement schemas remained 2.2 and 2.4 because P4-A added derived metrics artifacts, not fields to `FeatureSet`, `MeasurementMeta`, or `SpectrumData`.

## Configuration schema 2.10 to 2.11 and P2-B dataset QC schema 1.0

Configuration 2.11 adds the strict provisional `dataset_quality_control` block. A 2.10/measurement-2.4/feature-2.2 configuration migrates in memory, receives P2-B defaults, records a warning, and is never rewritten. Measurement and FeatureSet schemas remain unchanged. Pipeline version is `2.0.0-dev.12`; single-measurement run-manifest schema is 1.6.

P2-B has independent version-1.0 schemas for `DatasetQCScope`, the explicit input manifest, `DatasetQCResult`, and `dataset_qc_manifest.json`. The scope must enumerate measurements, cohort roles, selection reasons, and the complete expected condition matrix. The input manifest must enumerate exact FeatureSet and P2-A paths and hashes. Directory discovery is not a migration fallback.

P2-B compares only FeatureSets with an identical feature contract. Same-condition outliers use configured coordinate-median/MAD/RMS evidence and explicit reference-role mapping; `final_test` is rejected as a reference role. CONT, REPOS, and REASM pair construction and thresholds remain separate. Missing, duplicate, unexpected, incompatible, outlier, and repeatability evidence is retained without deleting measurements or changing human validity.

AnalysisScope schema 1.1 adds `analysis_tier` and an optional P2-B reference. `canonical_cohort` requires an exact matching dataset scope ID, ordered sample IDs, result SHA-256, FeatureSet content hashes, and P2-A hashes. Schema-1.0 scopes remain provisional compatibility inputs. Metrics-manifest schema 1.1 records the analysis tier/reference; P4 mathematics are unchanged.

Successful DEV-C6 single-measurement runs reported `P2_A=completed`, `P2_B=dataset_scope_required`, and `P4_A=p2_b_dataset_qc_required`. They did not claim that a single file established experiment completeness. DEV-C7 replaces the P4-B placeholder with the explicit comparison-scope gate described below; P5/P6 and P9 remain closed.

## Configuration schema 2.11 to 2.12 and P4-B comparison schema 1.0

Configuration 2.12 adds the strict provisional `comparison_metrics` block: predefined frequency bands and boundary rules, U4 baseline/candidate and safe ratio denominator, explicit cross-mode minimum-tone/shape/bias-sign policy, and development/training REPOS reliability floor/clip/count/mean-one normalization. A 2.11/measurement-2.4/feature-2.2 configuration migrates only in memory, receives these defaults, records a warning, and is not rewritten. Measurement and FeatureSet schemas remain 2.4 and 2.2. Pipeline version is `2.0.0-dev.13`; single-measurement run-manifest schema is 1.7 and records `P4_B=comparison_scope_required` after a successful single-measurement run.

P4-B has independent version-1.0 schemas for `ComparisonAnalysisScope`, its explicit FeatureSet input manifest, `ComparisonMetricsResult`, and `metrics_manifest.json`. It accepts persisted FeatureSets only, verifies every file/content hash, and never discovers samples by scanning a directory. Canonical tier requires the exact P2-B scope/result/input audit and rejects additional unaudited FeatureSets; provisional software-validation remains explicit and cannot claim a canonical cohort.

Band metrics use one scope-fixed common-valid mask and the authoritative P4-A pair/effective-rank/morphology-gain formulas. Cross-mode metrics require explicit one-to-one `match_pair_id` and controlled metadata/state identity. Absolute bias is always multisine minus sweep and is unavailable without compatible dB normalization/reference/calibration; no calibration is learned or applied. Reliability uses qualified development/training REPOS pairs only, rejects final_test, and produces supplemental mean-one weights without selecting tones or mutating FeatureSets. Tone selection, bridge/calibration workflow, P5/P6, and scientific conclusions remain outside P4-B.

## Configuration schema 2.12 to 2.13 and P5-A classification schema 1.0

Configuration 2.13 adds an explicit provisional `classification` contract: predefined bands, LOSO/LORO/LOAO protocols, three fixed baseline models, minimum training features/per-direction samples/prediction coverage, training-fold-only standardization, disabled PCA, and sealed final-test policy. Legacy `classification.validation` migrates only in memory to `classification.protocols` with a warning; ambiguous additional fields are rejected. Measurement and FeatureSet schemas remain 2.4 and 2.2. Pipeline version is `2.0.0-dev.14`; single-measurement run-manifest schema 1.8 separates `P5_A=classification_scope_required` from the still-unimplemented P5-B and P6 gates.

P5-A introduces version-1.0 `ClassificationScope`, explicit FeatureSet input manifest, typed result, and classification manifest. Scope order, FeatureSet content hashes, P2-A links, exact P2-B result/scope hash, cohort role, provenance, measurement mode, configuration, preprocessing and tone contract are hard gates. No directory discovery or raw-data processing occurs.

Each fold fixes its feature mask from the declared frequency band and training `valid_mask` intersection. Standardization, templates, centroids and logistic regression fit only the training fold. A test sample missing a required feature becomes unavailable; no test-informed mask shrink, fill, interpolation, PCA, hyperparameter search, or band/model selection is permitted. `final_test` remains present in audit but sealed from every fold. Sweep and multisine classifications are separate single-mode runs.

## Configuration schema 2.13 to 2.14 and P5-B cross-mode classification schema 1.0

Configuration 2.14 extends the provisional `classification` contract with an exact four-protocol list, allowed shape normalizations, sample-pooled mixed-mode training, uniform sample weighting, balanced logistic class weighting, audit-only P4-B bias, and disabled calibration. A 2.13/measurement-2.4/feature-2.2 configuration migrates only in memory, receives these fixed defaults, emits a warning, and is not rewritten. Pipeline version is `2.0.0-dev.15`; single-measurement run-manifest schema 1.9 records `P5_B=cross_mode_classification_scope_required`. Measurement and FeatureSet schemas remain 2.4 and 2.2.

P5-B introduces schema-1.0 `CrossModeClassificationScope`, explicit FeatureSet input manifest, typed result, and hash manifest. The scope enumerates exact P3-C artifacts, P2-B/P4-B references, matched-tone contracts, physical-state `cross_mode_group_id` values, cohort roles, and pre-frozen LOSO/LORO/LOAO outer folds. It never reads TXT/WAV/`SpectrumData`, discovers files, reruns P3/P8, interpolates tones, fills missing values, or infers pairing from filenames.

The four protocols share the same held-out groups: sweep-to-sweep, multisine-to-multisine, sweep-to-multisine, and pooled sweep-plus-multisine-to-multisine. Both modes from every held physical state are excluded from training. Masks and fitted transformations remain training-only; missing test tones produce unavailable predictions without shrinking the mask. Raw absolute-distance transfer is unavailable when P4-B cannot establish compatible references/calibration, while allowed normalized shape contracts and correlation-only shape comparison remain explicit. P4-B bias is retained for audit and never applied. `final_test` is listed in audit but remains sealed.

P5-B produces predictions, fold and macro metrics, confusion/per-class views, training composition, compatibility and transform audits, and same-cohort transfer gaps. The outputs remain provisional software validation. No model selection, deployment model, affine calibration, tone selection, P6/P9 workflow, or scientific conclusion is introduced.

## Configuration schema 2.14 to 2.15 and P6-A sweep HR calibration schema 1.0

Configuration 2.15 adds a strict, disabled-by-default `hr_calibration` block. It fixes unnormalized `dense_raw_spl`, standard topographic prominence, the deterministic prominence/magnitude/frequency selection rule, non-overlapping explicit search bands, repeat-type-separated drift, energy-fraction completeness policy, and complete per-resonator search/bandwidth/integration definitions. A 2.14/measurement-2.4/feature-2.2 configuration migrates only in memory, receives the disabled empty-resonator contract, emits a warning, and is never rewritten. Pipeline version is `2.0.0-dev.16`; single-measurement run-manifest schema 1.10 records `P6_A=hr_calibration_scope_required` and `P6_B=not_implemented`. Measurement and FeatureSet schemas remain 2.4 and 2.2.

P6-A introduces version-1.0 `HRCalibrationScope`, explicit persisted-FeatureSet input manifest, typed calibration result, and hash manifest. Scope and input manifests enumerate exact files/content hashes, configuration, direction/session/repeat metadata, calibration and energy-fraction groups, resonator/module IDs, preprocessing, P2-B reference, final-test seal, random state, provenance, and selection/pooling reasons. No directory discovery, raw TXT/WAV reading, P1/P3 rerun, filename inference, target-frequency sampling, sparse/tone input, or final-test use is a migration fallback.

Only the existing `FeatureSet.source_magnitude_quantity`, reference, and phase-status fields are now populated for newly generated dense FeatureSets. Formal P6-A rejects older dense artifacts that lack the explicit physical quantity rather than silently upgrading their semantics. The FeatureSet schema number does not change because these optional source fields already exist in schema 2.2.

Peak prominence is evaluated inside continuous valid segments. Half-power crossings use the configured `bandwidth_drop_db` and linear interpolation in the dB-frequency plane; missing crossings and invalid gaps remain unavailable. Energy integrates `10**(dB/10)` over measured or fixed measured-peak-centred windows without bridging gaps. CONT/REPOS/REASM drift remains separated, overlap uses measured bandwidth intervals, and missing resonator energy follows the preconfigured complete/partial policy.

The four lifecycle values are `draft`, `software_validation_only`, `approved_real_calibration`, and `superseded`. DEV-C10 validation uses only simulated data and is forced to `software_validation_only`, not frozen, and scientifically ineligible. Approval requires eligible `real_experiment` inputs, `research_analysis`, the research hard gate, exact canonical-ready P2-B, calibration/training roles, a final-test seal, frozen thresholds, complete hashes, and an approval record. P6-B, `hr_band_energy`, P9, cross-mode calibration, real threshold freezing, and scientific conclusions are not introduced.

## Configuration schema 2.15 to 2.16, FeatureSet 2.2 to 2.3, and P6-B readout schema 1.0

Configuration 2.16 adds the strict, disabled-by-default provisional `hr_readout` block. It fixes the persisted input kind/representation/normalization, magnitude-only phase policy, one mapping/energy method pair per resolved configuration, tone sharing and detuning policy, window completeness/gap rules, energy-fraction completeness, and unavailable uncertainty. A 2.15/measurement-2.4/feature-2.2 configuration migrates only in memory, receives the disabled P6-B defaults, emits a warning, and is never rewritten. Pipeline version is `2.0.0-dev.17`; single-measurement run-manifest schema 1.11 records `P6_B=hr_readout_scope_required`.

FeatureSet schema 2.3 adds optional typed per-feature quality evidence and a typed derivation link. Existing schema-2.2 artifacts remain loadable with empty evidence, but formal P6-B rejects a multisine tone FeatureSet without authoritative per-tone P8/P3-C evidence. Newly generated P3-C multisine FeatureSets preserve each tone's available/missing/invalid state, reason codes, and P8 details. P6-B `hr_band_energy` and `hr_energy_fraction` FeatureSets link the exact source FeatureSet content hash, calibration semantic and exact-file hashes, P2-B result hash, readout scope/result, and scientific/deployment/comparability flags.

P6-B introduces version-1.0 `HRReadoutScope`, explicit FeatureSet input manifest, typed result, and immutable output manifest. It accepts only exact persisted P3-C multisine tone artifacts, an exact verified P6-A bundle, and the exact P2-B result. It does not read raw audio, rerun P8, rediscover files, interpolate sparse tones, recalculate sweep peaks, use final-test data, or fit cross-mode bias/calibration.

`nearest_tone` uses the nearest valid tone to the P6-A measured peak subject to configured detuning and reports linear relative tone power. `calibrated_window` integrates `10**(magnitude_db/10)` on continuous valid-tone segments with a narrowband trapezoid; it records endpoint coverage, requested/covered span, gaps, missing/invalid tones, tone count, and collisions without bridging evidence gaps. Energy fractions explicitly use `require_all` or `allow_partial`; missing values remain unavailable rather than zero. Draft and superseded calibrations are rejected. Software-validation calibration can authorize only simulated/software-validation readout. Approved real calibration additionally retains all P6-A approval, freeze, provenance, final-test-seal, P2-B, and exact-hash gates.

P6-B phase remains `magnitude_only`; uncertainty remains `unavailable` without an authoritative uncertainty source. `deployment_allowed=false` and `absolute_energy_comparable=false` are fixed for this slice. DEV-C11 validation is simulated/software-validation/scientifically ineligible and cannot support scientific conclusions. Cross-mode amplitude calibration, real HR threshold freezing, and deployment remain outside this migration.

## Configuration schema 2.16 to 2.17 and P9-A tone-selection schema 1.0

Configuration 2.17 adds a strict, disabled-by-default provisional `tone_selection` block. It declares analysis/edge/excluded bands, valid-sample/direction/CONT/REPOS coverage, raw-energy limits, U4SYM/U4ENC comparison, optional P4-B and quality evidence policy, scoring method/components/weights/missing policy, target count, Hz/bin spacing, partial policy, and non-overlapping band quotas. A 2.16/measurement-2.4/feature-2.3 configuration migrates in memory with `tone_selection.enabled=false` and a warning; it is never silently enabled or rewritten. Pipeline version is `2.0.0-dev.18`; single-measurement run-manifest schema 1.12 records `P9_A=tone_selection_scope_required`.

P9-A introduces version-1.0 `CandidateToneUniverse`, `ToneSelectionScope`, explicit persisted-FeatureSet input manifest, typed score/selection result, selected-tone-set artifact, and immutable output manifest. Candidate frequencies must exactly equal their P7-compatible DFT bin frequencies and remain unique, strictly ordered, in-band and below Nyquist. Input FeatureSets must be `tone_projection_from_sweep` and exactly match sample, metadata, tone order, content and contract hashes. Multiple declared views may separate discriminability, raw effective energy and authoritative quality evidence without using a normalized view as absolute energy.

Between-direction variance is the sample variance of per-direction medians. CONT and REPOS variance use their own valid P2/P4 repeat pairs and the median half-squared pair difference; neither repeat type substitutes for another. Configuration gain is the ratio of matched candidate/baseline direction variances. P4-B repeatability and per-tone SNR are optional exact-scope evidence; missing evidence remains unavailable. Excluded bands and safety distance are preconfigured.

The scoring layer supports an epsilon-stabilized variance ratio and a weighted average-rank sum. Weighted normalization uses only eligible candidates in the exact selection-training scope; ties use average rank, required missing components make a candidate ineligible, and optional missing components renormalize available weights with an explicit warning. Stable greedy selection applies score, required-component availability, frequency and candidate-ID ordering, followed by configured band minimum/maximum quotas and Hz/bin spacing. Every decision is retained in the trace; failure to meet the target is unavailable unless `allow_partial=true`.

`development_selection` accepts only training/development inputs. `fold_training_selection` binds an outer fold, exact training IDs/hash and held physical states; results cannot be reused across folds. Final-test IDs are sealed audit data and never FeatureSet inputs, normalization references or decision inputs. Simulated validation can produce only `software_validation_only`; approval/deployment/final-test evaluation fail closed. This P9-A migration does not itself introduce P9-C calibration, P9-D readout, P7 WAV generation or scientific conclusions.

## Configuration schema 2.17 to 2.18 and P9-B projection-ablation schema 1.0

Configuration 2.18 adds a strict, disabled-by-default `tone_projection_ablation` block. It freezes sweep-only input identity, predeclared prefix sizes, P9-A rank ordering, grouped outer/inner protocol, inner evidence minimums, P5 model/coverage, P4 retention definitions, decision thresholds, spacing/quota enforcement, sealed final-test and disabled cross-mode policy. A 2.17/measurement-2.4/feature-2.3 configuration migrates only in memory, receives `tone_projection_ablation.enabled=false`, emits a warning and is never rewritten. Pipeline version is `2.0.0-dev.19`; single-measurement run-manifest schema 1.13 adds `P9_B=projection_ablation_scope_required`. Measurement and FeatureSet schemas remain 2.4 and 2.3.

P9-B introduces version-1.0 typed scope/fold/selection-reference/subset/derivation/P4/P5/decision/result objects and a hash-audited output manifest. It accepts only explicit persisted P3-C sweep tone FeatureSets and one exact P9-A `fold_training_selection` bundle per outer fold. Global selection, held-out membership leakage, final-test reads, mismatched candidate universe/P2-B/P4-B/training/manifest hashes, multisine input and directory discovery all fail closed.

Every candidate size is an immutable prefix of the frozen P9-A selection rank. The projection slices existing P3-C columns and records source/derived hashes; it does not rerun P1/P3. P4 preservation reuses authoritative P4-A/P4-B calculations. Sweep-to-sweep classification reuses the P5-A fold predictor and fixed-label summary. Minimum tone count uses grouped inner CV inside outer-training and frozen thresholds; outer-test is evaluated only after the decision and cannot update P9-A or the minimum count.

DEV-C13 validation remains `simulated/software_validation`, scientifically and deployment ineligible, non-canonical and final-test sealed. Its minimum-tone output lifecycle is `software_validation_candidate`. P9-C/P9-D require later, independent authority and do not promote this candidate; real threshold freezing and scientific conclusions remain outside this migration.

## Configuration schema 2.18 to 2.19 and P9-C bridge schema 1.0

Configuration 2.19 adds a strict, disabled-by-default `cross_mode_bridge` block. It freezes the multisine-to-sweep mapping direction, method order, training-pair/variance/slope/residual thresholds, held-out tone coverage, direction-template metric, P5 model list and sealed final-test policy. A 2.18/measurement-2.4/feature-2.3 configuration migrates only in memory, receives `cross_mode_bridge.enabled=false`, emits a warning and is never rewritten. Pipeline version is `2.0.0-dev.20`; single-measurement run-manifest schema 1.14 adds `P9_C=cross_mode_bridge_scope_required`. Measurement and FeatureSet schemas remain 2.4 and 2.3.

P9-C introduces schema-1.0 matched-pair, fold, calibration-fit/model, held-out comparison, template, prediction, metric, result, explicit input and output-manifest objects. The formal CLI loads only the FeatureSet files explicitly named by the input manifest. Every sweep input links its P3-C preprocessing manifest; every multisine input additionally links the exact P7 stimulus manifest and P8 run/spectrum/tone-quality artifacts. It never scans, reads raw TXT/WAV, reruns P1/P3/P8 or infers pair identity from filenames.

Every outer fold is a complete LOSO/LORO/LOAO physical-state group. Both modes from a held state are excluded from training. The fold carries exact P2-B, P4-B, P9-A selection scope/artifact/manifest, P9-B result/manifest, candidate-universe, selected-subset and training-membership hashes. Global selection, missing authority, mismatched tone identity/order/index, one-to-many pairs, final-test inputs or held-state leakage fail closed.

The only mapping direction is `sweep_projection_db = slope * multisine_db + intercept_db`. Identity is an auditable no-fit baseline; bias-only and per-tone affine parameters fit only outer-training pairs. Minimum training pairs, input variance, slope bounds and residual policy come from resolved YAML. Absolute calibration is unavailable when P4 magnitude quantity/reference compatibility is absent; this does not silently manufacture a reference. Held-out tone residuals, direction-template consistency and four P5-style protocol comparisons all use the same frozen held cohort.

DEV-C14 validation creates actual simulated P7 stimuli, S3 recordings with known affine injection, P8 estimates and persisted P3-C FeatureSets before invoking P9-C. Its lifecycle is fixed to `software_validation_only`, approval is `not_approved`, and `scientifically_eligible`, `deployment_eligible`, `canonical_analysis` and `final_test_read` are false. No simulated model can be migrated into a real calibration or scientific conclusion. P9-D cannot consume ordinary outer-fold models; real calibration approval, uncertainty qualification and real threshold freezing remain outside this migration.

## Configuration schema 2.19 to 2.20 and P9-D offline-readout schema 1.0

Configuration 2.20 adds a strict, disabled-by-default `offline_fast_readout` block. It fixes the allowed frozen model, accepted QC states, required P8 checks, magnitude-only phase policy, no-imputation missing-tone behavior, optional frozen-readout calibration authority, final-test seal, and scientific/deployment restrictions. A 2.19/measurement-2.4/feature-2.3 configuration migrates only in memory, receives `offline_fast_readout.enabled=false`, emits a warning and is never rewritten. Pipeline version is `2.0.0-dev.21`; single-measurement run-manifest schema 1.15 adds `P9_D=frozen_readout_package_required`. Measurement and FeatureSet schemas remain 2.4 and 2.3.

P9-D introduces schema-1.0 `FrozenDirectionModel`, `FrozenReadoutPackage`, input/QC/feature/calibration/prediction/result objects and self-hashed package/readout manifests. Package building uses only explicit training/development FeatureSets and exact P2-B/P4-B/P5/P9 authority files. It persists the trained scaler and nearest-centroid parameters, training IDs/hashes, tone/preprocessing contracts, stimulus identity, QC policy, lifecycle and final-test seal. A temporary CV fold cannot become `frozen_inference` authority.

The formal inference command reads only an explicit persisted P8 `SpectrumData`, P2 QC, P7 manifest and verified package. It reuses P3-C tone FeatureSet construction and the shared P5 predictor math; it does not read WAV/TXT, rerun P7/P8, train, discover directories, interpolate or zero-fill missing tones. Optional P9-C calibration must be a separately frozen `frozen_readout` model matching the exact directions, tones, frequencies, magnitude/reference/normalization contracts, authority hashes and final-test seal; existing outer-fold validation models fail closed.

DEV-C15 validation builds six simulated training chains and one independent simulated readout chain, then executes persisted-only inference twice. All outputs remain `simulated/software_validation`, scientifically and deployment ineligible, non-canonical and final-test sealed. Distance and margin outputs are descriptive and are not confidence probabilities. No DEV-C15 artifact may be migrated into a real approved package without a separate governed acceptance process.

## Existing sweep names and commands

Names such as `V2_U4SYM_A000_S01_CONT_R01.txt` remain valid. The sweep command remains:

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4.yaml
```

Without `--input`, the command still validates and resolves configuration only. With `--input`, `--metadata`, and `--run-id`, it routes REW through the P1 REW adapter or multisine through the P1/P8 adapter, executes shared P2-A, and writes a single-measurement bundle. Dense REW spectra continue through P3-A/P3-B; sparse tones record both stages as not applicable. The single-measurement run records `P2_B=dataset_scope_required`, `P3_C=paired_run_required`, and `P4_A=p2_b_dataset_qc_required`. P2-B uses `python scripts/run_dataset_qc.py --scope <scope> --inputs <manifest> ...`; it never scans the preceding run directories.

## New grouping fields

Legacy rows may lack `reposition_round_id`, `assembly_id`, and `acquisition_block_id`. The migration layer must preserve these as missing and emit a warning. It must not infer them from `repeat_type`, filename order, or neighboring rows. Validation schemes that require a missing group are unavailable for that dataset.

## Outputs

V1 outputs remain read-only. DEV-C2/C3 write new runs under `outputs/<data_origin>/<run_purpose>/<run_id>/` (or `outputs/quarantine/<run_id>/` when metadata cannot be resolved) and refuse to overwrite an existing directory. Dense successful runs add an immutable `processed/` P3 bundle with complete smoothing semantics. DEV-C4 paired runs add matched FeatureSet artifacts. DEV-C6 writes dataset QC views under `outputs/<data_origin>/<run_purpose>/<run_id>/dataset_qc/`. DEV-C7 writes explicit-scope comparison views under `outputs/<data_origin>/<run_purpose>/<run_id>/comparison_metrics/`. DEV-C8 writes separate-mode grouped classification views under `outputs/<data_origin>/<run_purpose>/<run_id>/classification/`. DEV-C9 writes four-protocol results under `outputs/<data_origin>/<run_purpose>/<run_id>/cross_mode_classification/`. DEV-C10 writes P6-A results under `outputs/<data_origin>/<run_purpose>/<run_id>/hr_calibration/`. DEV-C12 writes candidate scoring and selected-tone-set views under `outputs/<data_origin>/<run_purpose>/<run_id>/tone_selection/`. DEV-C14 writes bridge scope, authority audits, held-out comparisons, calibration models, predictions, metrics and self-hashed manifests under `outputs/simulated/software_validation/<run_id>/.../cross_mode_bridge/`. DEV-C15 adds a self-contained `readout_package/` and immutable `offline_readout/` audit bundle with input/QC/feature/calibration/prediction/result views. These bundles record input/output SHA-256 and manifest self-hashes. Failure paths retain available input/failure evidence without writing a false success marker.

## DEV-C16 acceptance and DEV-D migration boundary

DEV-C16 does not change the pipeline/config/Measurement/FeatureSet versions. It adds an independent acceptance schema 1.0 and the explicit `scripts/run_pre_experiment_acceptance.py` entry point. A V1 user may continue to run `python scripts/run_pipeline.py --config config/experiment_v2_u4.yaml`; the acceptance runner verifies this command, imports all three external-reference REW fixtures, and proves that legacy YAML is migrated only in memory without rewriting its source hash.

Acceptance outputs live under `outputs/simulated/software_validation/<run-id>/acceptance/`, refuse overwrite, and bind explicit config/fixture/evidence/output hashes to a self-hashed manifest. Only all-pass T0–T3 plus all 14 V2 requirements, a sealed final-test and a clean committed tree may yield `ready_for_dev_d_diagnostic_experiment=true`. This is not a migration to research authority: real inputs must follow the separate DEV-D acquisition plan, receive real provenance/roles, rerun P2-A/P2-B/P3/P4/P5/P6/P9 using training/development only, and freeze new real authorities before final-test access. Simulated P9 selections/calibrations/models/packages are never relabelled as real.

## DEV-UI1 desktop-entry migration boundary

DEV-UI1 adds PySide6 6.7–6.8 and pytest-qt 4.x to `requirements.txt` and adds `python scripts/run_gui.py` as an optional local entry point. Existing CLI commands, pipeline/config/Measurement/FeatureSet versions, raw inputs and output schemas are unchanged. The research backend does not import PySide6.

The desktop shell delegates YAML validation to `config.load_config` and simulated acceptance to `scripts/run_pre_experiment_acceptance.py`. It does not migrate V1 metadata, infer provenance, rewrite configs, read raw measurements, or run P1–P9 experiment analysis. Existing CLI users need make no workflow change. A V1 or V2 artifact never gains scientific authority by being opened in the UI.

The twelve-step navigation is presentation state only. Its `passed`, `warning`, `manual_review`, `blocked` and `failed` labels are derived views rather than replacements for `MeasurementMeta`, QC results or manifests. Real Multisine/P8 remains blocked; final-test remains sealed. Later DEV-UI2–DEV-UI4 steps are visible only as explanations in this slice.

## DEV-UI2 import and single-run migration boundary

DEV-UI2 activates only the single-measurement import step. It introduces no pipeline/config/Measurement/FeatureSet version change and does not alter existing CLI arguments. The UI writes its own registration schema 1.0 evidence beneath ignored `outputs/ui_sessions/<sample-id>/rev-NNN/`, then invokes the existing mode-specific CLI with separate executable arguments. `run_manifest.json`, P1/P2/P8 QC, `SpectrumData` and `FeatureSet` artifacts remain backend authorities.

Four routes are explicit and non-interchangeable: official REW is `external_reference/parser_fixture/software_validation`; simulated Multisine is `simulated/software_validation`; real diagnostic REW and real Multisine registrations are `real_experiment/research_input/software_validation` with `eligible_for_scientific_analysis=false`. Switching routes clears incompatible drafts after confirmation. External-reference experiment identity remains null, and no provenance/scientific-eligibility JSON editor is exposed.

Raw TXT/WAV/manifest files are never copied or rewritten. Registration records source hashes, configuration and metadata snapshots, command arguments, revision history and human-readable reports. A second save requires an explicit correction reason and creates a new revision; a run refuses an existing output directory and rechecks all input hashes immediately before launch. Real Multisine is registration-only: both the UI control and worker reject P8 launch pending the separate DEV-D real-data gate. V1 command-line workflows remain available unchanged.

## DEV-UI3 plan and batch-orchestration migration boundary

DEV-UI3 activates plan, dataset QC and capability-gated batch-analysis pages. It introduces UI-owned plan, safety-checklist, plan-manifest and batch-snapshot schema version `1.0.0`; it does not change the pipeline/config/Measurement/FeatureSet version quartet, scientific thresholds or existing CLI arguments. Plan roles `calibration/training/development/final_test_sealed` belong only to plan/analysis scope and must never be written to `MeasurementMeta.dataset_role`.

Dataset selection is now explicit: a user chooses an immutable plan revision, a precise UI2 session manifest and an optional precise output directory. There is no recursive directory discovery. The UI writes preview scopes, input manifests and hashes, then invokes `run_dataset_qc.py`, `run_comparison_metrics.py`, `run_classification.py`, `run_cross_mode_classification.py`, `run_hr_calibration.py` or `run_hr_readout.py` only when their existing prerequisites are satisfied. Backend bundles remain authoritative.

P3-C has no generic formal CLI and therefore remains unavailable in UI3. Existing validation runners are not migrated into production entry points. P5-B/P6-B require pre-existing exact matched-tone/calibration authority and are blocked for real Multisine. Sealed final-test selection is rejected before artifact content is read and creates an incident audit; DEV-UI3 provides no unseal operation. Existing V1/V2 CLI workflows remain available unchanged.

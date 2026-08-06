# DEV-C14 / P9-C — Sweep–Multisine cross-mode bridge calibration

## Status, date, branch, and research qualification

- Status: completed, locally verified, and included with the implementation in one local commit.
- Date: 2026-08-06.
- Branch: `feature/v2-dual-input`.
- Commit boundary: `feat(bridge): add leakage-safe cross-mode calibration`.
- Qualification: `simulated / software_validation / software_validation_only / not_approved`.
- Fixed gates: `scientifically_eligible=false`, `deployment_eligible=false`, `canonical_analysis=false`, `final_test_read=false`.

Completion means that the software-validation slice and its audits pass. It is not a real calibration, a deployable bridge, or evidence for a scientific conclusion.

## Goal and acceptance criteria

P9-C compares matched sweep-projection and multisine-measurement P3-C FeatureSets on exactly the fold-specific P9-B minimum-tone subset. It optionally learns a preregistered dB-domain bridge using outer-training pairs only, then evaluates uncalibrated and calibrated values on the unchanged held cohort.

Acceptance requires explicit persisted inputs; exact P2-B/P4-B/P9-A/P9-B/tone/training/final-test authority; one-to-one metadata pairing; complete grouped outer folds; training-only fit; held-out tone, direction-template and P5-style metrics; immutable source artifacts; stable output schemas and hashes; and an actual simulated P7→S3→P8→P3-C→P9-C validation with known affine injection.

## Completed scope

- Added typed schema-1.0 matched-pair, fold, bridge scope, per-tone fit, calibration model, held-out comparison, direction-template, prediction, classification metric, fold-evaluation and result objects.
- Added a formal CLI that reads only explicit FeatureSet/lineage/authority paths and verifies file, content, contract and semantic hashes. It never discovers a measurement by scanning a directory.
- Enforced one-to-one sweep/multisine pairs and exact configuration, direction, session, repeat, reposition, assembly and acquisition-block metadata.
- Enforced complete LOSO/LORO/LOAO held physical-state groups. Both modes of a held state are excluded from training.
- Bound each fold to its exact training membership, selected P9-B subset, source indices/frequencies/names, CandidateToneUniverse, P2-B, P4-B, P9-A scope/artifact/manifest, and P9-B result/manifest hashes. Global selection and final-test inputs fail closed.
- Implemented identity, bias-only and per-tone affine arms. Bias/affine fitting uses only finite outer-training pairs and config-defined evidence, variance, slope and residual policies.
- Reused P4 absolute-comparability rules. Fitted absolute calibration is unavailable when magnitude quantity/reference contracts are incompatible; no reference is fabricated.
- Reused P5 fold predictors and fixed-label summaries for sweep→multisine raw/calibrated, sweep→sweep and multisine→multisine comparisons. Per-class precision/recall/F1/support are retained.
- Added held-out per-tone bias, RMS, MAE, maximum residual and correlation; direction-template correlation/RMS/rank; coverage; confusion matrices; classification metrics; and full reason codes.
- Added all requested CSV/JSON/model artifacts, manifest self-hash, artifact hashes, standalone model file/semantic hashes, and loader-side recomputation.
- Extended S3 with a known affine cross-mode injection that modifies the transfer before waveform synthesis, rather than changing P9-C labels or held-out data.
- Extended the matched-tone validator to retain P8 spectrum/QC/diagnostic artifacts and a hash-indexed P8 run manifest for downstream lineage.

## Explicit non-scope

- No real experiment, scientific conclusion, approved calibration, deployment model or P9-D readout.
- No raw TXT/WAV access, directory discovery, P1/P3/P8 recomputation or sparse-to-dense interpolation in the formal P9-C CLI.
- No calibration-method, tone, threshold or hyperparameter selection from outer test or sealed final test.
- No pooled/global calibration, nonlinear calibration, uncertainty qualification, phase calibration, cross-entry acquisition-bias correction or real threshold freezing.
- No changes to P4 mathematical definitions. P5 predictors/summaries are reused rather than forked.

## Mathematical and state definitions

For each selected tone `k`, the fixed direction is:

```text
sweep_projection_db[k] = slope[k] * multisine_db[k] + intercept_db[k]
```

- `identity`: `slope=1`, `intercept=0`; this is an auditable no-fit baseline. Large mismatch is a warning, not a reason to erase the raw baseline.
- `bias_only`: `slope=1`, `intercept=mean(sweep-multisine)` on outer-training pairs.
- `per_tone_affine`: ordinary least squares on outer-training pairs, with configured minimum pair count, minimum multisine variance and slope bounds.
- Raw bias sign is `multisine - sweep`; calibrated residual sign is `calibrated_multisine - sweep`.
- Fit residual policy is `valid`, `warning`, or `unavailable`. Evidence failure never returns fabricated parameters.
- Fold evaluation is unavailable below configured common-tone count or pair coverage. Multiple reasons are preserved.
- Result completion is `completed` or `completed_with_unavailable`; unavailable arms remain explicit and do not remove a tone or mutate source data.

## API and data flow

```text
explicit persisted P3-C FeatureSets
  + explicit P7/P8/P3-C lineage
  + exact fold P2-B/P4-B/P9-A/P9-B authority
  -> load_cross_mode_bridge_inputs(...)
  -> analyze_cross_mode_bridge(...)
  -> fold-local models + held-out comparisons/P5 metrics
  -> write_cross_mode_bridge_outputs(...)
  -> load_cross_mode_bridge_bundle(...) hash revalidation
```

Primary API:

```text
analyze_cross_mode_bridge(
    artifacts: Mapping[str, FeatureSet],
    scope: P9CrossModeBridgeScope,
    config: Mapping[str, Any],
) -> P9CrossModeBridgeResult
```

The formal command is `scripts/run_cross_mode_bridge.py`. The deterministic actual-chain validation command is `scripts/run_cross_mode_bridge_validation.py`.

## Schema and configuration changes

- Pipeline: `2.0.0-dev.19 -> 2.0.0-dev.20`.
- Config schema: `2.18.0 -> 2.19.0`.
- Single-measurement run manifest: `1.13.0 -> 1.14.0`, adding `P9_C=cross_mode_bridge_scope_required`.
- Measurement and FeatureSet remain `2.4.0` and `2.3.0`.
- New `cross_mode_bridge` schema 1.0 is disabled by default and marks all thresholds provisional.
- Config 2.18 migrates only in memory, forces P9-C disabled, records a warning and does not rewrite source YAML.
- New validation overlay: `config/validation_dev_c14_p9c.yaml`.

## Output schema

The bridge bundle contains at least:

- `bridge_scope.json`, `input_manifest.json`, `matched_pair_audit.csv`, `fold_assignments.csv`, `tone_authority_audit.csv`;
- `uncalibrated_tone_comparison.csv`, `calibration_parameters.csv`, `calibration_fit_diagnostics.csv`, `heldout_tone_comparison.csv`;
- `direction_template_consistency.csv`, `cross_mode_predictions.csv`, `cross_mode_fold_metrics.csv`, `cross_mode_summary.json`;
- `calibration_model.json`, per-fold/method model JSON files, `calibration_model.sha256`;
- `bridge_result.json`, `bridge_manifest.json`, and `bridge_manifest.sha256`.

CSV files are stable audit views. Typed JSON/model objects and FeatureSet artifacts remain authoritative. Existing output directories are never overwritten.

## Modified files

- Core/API: `cross_mode_bridge.py`, `classification.py`, `comparison_metrics.py`.
- Formal I/O: `cross_mode_bridge_cli.py`, `cross_mode_bridge_outputs.py`, `scripts/run_cross_mode_bridge.py`.
- Actual-chain validation: `cross_mode_bridge_validation.py`, `matched_tone_validation.py`, `mock_data.py`, `scripts/run_cross_mode_bridge_validation.py`, `validation_dev_c14_p9c.yaml`.
- Version/config/stage gate: `config.py`, `version.py`, `run_execution.py`, `config/default.yaml`, `config/schema_versions.yaml`.
- Tests: bridge core/CLI/output/actual-chain tests plus config and pipeline regressions.
- Documentation: this report, progress index, README, migration guide and changelog.

## Data source, provenance, and scientific eligibility

The persisted validation contains six explicit matched physical states: 3 sessions × 2 directions. Every state runs an actual deterministic P7 stimulus generation, S3 WAV simulation, P8 synchronization/transfer/QC and P3-C sweep/multisine FeatureSet construction. S3 injects `sweep = 1.15 * multisine + 0.8 dB` before audio estimation. P9-C receives only the resulting persisted FeatureSets and lineage manifests.

All records remain `data_origin=simulated`, `run_purpose=software_validation`, `dataset_role=software_validation`, `eligible_for_scientific_analysis=false`. The bridge lifecycle is `software_validation_only`, approval is `not_approved`, and final-test data are represented only by an unread seal. These artifacts cannot be relabelled as `real_experiment` or used for a scientific conclusion.

## Validation commands and exact results

- `pytest -q tests/test_cross_mode_bridge.py tests/test_cross_mode_bridge_cli.py tests/test_cross_mode_bridge_outputs.py tests/test_cross_mode_bridge_validation_e2e.py tests/test_classification.py tests/test_comparison_metrics.py tests/test_matched_tone_e2e.py tests/test_mock_data.py tests/test_multisine_qc.py tests/test_config.py tests/test_pipeline_e2e.py`: `251 passed in 31.59s`.
- `pytest -q tests/test_cross_mode_bridge_validation_e2e.py`: `2 passed in 5.64s`.
- `pytest -q`: `642 passed in 77.97s (0:01:17)`.
- `python -m compileall -q src scripts tests`: passed with exit code 0 and no output.
- `git diff --check`: passed with exit code 0 and no output.
- `python scripts/run_cross_mode_bridge_validation.py --project-root . --config config/validation_dev_c14_p9c.yaml --output-root outputs --run-id dev-c14-p9c-validation-20260806-v1`: succeeded as `completed_with_warnings` with 6 actual chains, 3 folds and 8 selected tones per fold. Maximum chain relation error was `0.012045439922069079 dB`; maximum recovered slope error `0.003130333277648445`; maximum recovered intercept error `0.06553842792118725 dB`; affine mean held-out RMS improved from `2.219361368055972 dB` raw to `0.00037999212947584823 dB` calibrated. Artifact and model-registry hashes revalidated. Result hash: `sha256:e8a10d9459343f555d9dcef489f6e5511292f3e3da40a147ae3d6132a47ef5ee`.
- `$env:PYTHONPATH='src'; python -c "...load_cross_mode_bridge_bundle(...)..."`: loader revalidated the manifest, every artifact, result semantic hash and 9 standalone models; manifest content hash `sha256:e9442be0968779c0b2e3b8c773456bd4762405e292e4c2141815a97d25c5bf30`.

TDD red failures during development are not counted as successful verification. Only the commands and results listed above as passed are completion evidence.

## Generated validation output

Validation root:

`outputs/simulated/software_validation/dev-c14-p9c-validation-20260806-v1/`

Bridge bundle:

`outputs/simulated/software_validation/dev-c14-p9c-validation-20260806-v1/b/simulated/software_validation/r/cross_mode_bridge/`

The root also retains six actual-chain P7/S3/P8/P3-C runs, explicit bridge inputs, fold authorities, and `validation_summary.json`. Output names are deliberately short inside the validation root to remain below legacy Windows path limits; manifest paths and hashes preserve full identity.

## Known limitations and provisional parameters

- Only 3 simulated sessions, 2 directions, one configuration and 8 selected tones are exercised. This is intentionally small software evidence.
- P9-A/P9-B authorities in the validation are typed, fold-specific software-validation artifacts/decisions; they are not approved tone sets or evidence that 8 tones are sufficient in a real experiment.
- Per-tone affine uncertainty is descriptive only. There are no confidence intervals, hierarchical effects, drift across real sessions or external replication.
- Absolute comparison is valid in the fixture only because both simulated FeatureSets receive one explicit shared synthetic quantity/reference. P9-C rejects fitted absolute calibration when this contract is absent.
- Bias-only warnings and identity mismatch are expected under an injected slope. They remain visible; affine validity does not upgrade the whole run to scientific or deployment status.
- Thresholds, slope bounds, direction set and selected count are provisional validation parameters.

## Commit and next gate

This report and the implementation belong to one local commit titled `feat(bridge): add leakage-safe cross-mode calibration`. It is not pushed by this step.

P9-D or any real calibration requires an independently approved real-experiment scope; canonical-ready P2-B; frozen P4/P5/P9-A/P9-B authority; real acquisition comparability; final-test governance; uncertainty/residual qualification; human approval and supersession records; and a separate explicit specification. DEV-C14 alone opens none of those gates.

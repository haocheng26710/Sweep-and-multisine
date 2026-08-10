from __future__ import annotations

import json
from pathlib import Path

import pytest

from acoustic_encoder.dataset_quality_cli import run_dataset_quality_cli
from acoustic_encoder.schemas import FeatureKind, artifact_sha256, save_feature_set
from acoustic_encoder.ui.batch_workflow import (
    BatchStage,
    BatchWorkflowService,
    BatchWorkflowState,
    BatchWorkflowStatus,
    DatasetQCSummary,
    InvalidBatchTransition,
)
from acoustic_encoder.ui.sample_registry import FinalTestSealedError
from acoustic_encoder.ui.experiment_plan import ExpectedSample, ExperimentRole
from acoustic_encoder.ui.sample_registry import ArtifactReference, RegisteredSample
from test_dataset_quality_control import _measurement


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _registered(
    root: Path,
    sample_id: str,
    repeat_id: str,
    expected_sample_id: str,
) -> tuple[RegisteredSample, ExpectedSample]:
    feature, qc = _measurement(sample_id, repeat_id=repeat_id)
    base = root / "processed/features/dense_raw_spl" / sample_id
    npz_path, json_path = save_feature_set(feature, base)
    qc_path = root / "quality" / sample_id / "quality_control.json"
    qc_path.parent.mkdir(parents=True, exist_ok=True)
    qc_path.write_text(json.dumps(qc.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata_path = root / "metadata" / f"{sample_id}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(feature.meta.to_dict()), encoding="utf-8")
    session_manifest = root / "sessions" / sample_id / "ui_session_manifest.json"
    session_manifest.parent.mkdir(parents=True, exist_ok=True)
    session_manifest.write_text("{}", encoding="utf-8")
    artifacts = tuple(
        ArtifactReference(path.as_posix(), artifact_sha256(path), artifact_type)
        for path, artifact_type in (
            (npz_path, "feature_set"),
            (json_path, "feature_set"),
            (qc_path, "quality_control"),
        )
    )
    registration = RegisteredSample(
        registration_id=f"reg-{sample_id}",
        source_sample_id=sample_id,
        expected_sample_id=expected_sample_id,
        session_manifest_path=session_manifest,
        metadata_path=metadata_path,
        output_directory=root,
        metadata=feature.meta,
        run_purpose="software_validation",
        analysis_status="completed",
        qc_status="valid",
        manual_review_reasons=(),
        source_hash_matches=True,
        artifact_hashes_match=True,
        feature_set_available=True,
        spectrum_data_available=True,
        artifacts=artifacts,
    )
    expected = ExpectedSample(
        sample_id=expected_sample_id,
        condition_id="c-cont",
        block_id="main",
        configuration_id=feature.meta.configuration or "U4ENC",
        direction_id="D000",
        angle_deg=float(feature.meta.angle_deg or 0.0),
        session_id=feature.meta.session_id or "S1",
        repeat_type=feature.meta.repeat_type or "CONT",
        repeat_id=feature.meta.repeat_id or repeat_id,
        reposition_round_id=feature.meta.reposition_round_id,
        assembly_id=feature.meta.assembly_id,
        acquisition_block_id=feature.meta.acquisition_block_id or "B1",
        measurement_mode=feature.meta.measurement_mode,
        experiment_role=ExperimentRole.TRAINING,
        stimulus_id=feature.meta.stimulus_id,
        tone_set_id=feature.meta.tone_set_id,
        sample_rate_hz=None,
        audio_channel=feature.meta.audio_channel,
    )
    return registration, expected


def test_batch_state_machine_forbids_skipping_plan_and_p2b() -> None:
    state = BatchWorkflowState()
    with pytest.raises(InvalidBatchTransition):
        state.transition(BatchWorkflowStatus.DATASET_QC_RUNNING)
    state.transition(BatchWorkflowStatus.PLAN_DRAFT)
    state.transition(BatchWorkflowStatus.PLAN_READY)
    state.transition(BatchWorkflowStatus.ACQUISITION_WAITING)
    state.transition(BatchWorkflowStatus.SAMPLES_COMPLETE)
    state.transition(BatchWorkflowStatus.DATASET_QC_RUNNING)
    state.transition(BatchWorkflowStatus.DATASET_QC_PASSED)
    state.transition(BatchWorkflowStatus.ANALYSIS_READY)
    state.transition(BatchWorkflowStatus.ANALYSIS_RUNNING)
    state.transition(BatchWorkflowStatus.ANALYSIS_COMPLETED)
    assert state.status is BatchWorkflowStatus.ANALYSIS_COMPLETED


def test_backend_capability_matrix_is_auditable_and_does_not_wrap_validation() -> None:
    service = BatchWorkflowService(PROJECT_ROOT)
    capabilities = {item.stage: item for item in service.capabilities()}

    assert capabilities[BatchStage.P2_B].formally_available is True
    assert capabilities[BatchStage.P2_B].script == "scripts/run_dataset_qc.py"
    assert capabilities[BatchStage.P3_C].formally_available is False
    assert capabilities[BatchStage.P3_C].script is None
    assert "validation" not in (capabilities[BatchStage.P3_C].entry_point or "")
    assert capabilities[BatchStage.P4].script == "scripts/run_comparison_metrics.py"
    assert capabilities[BatchStage.P5_A].script == "scripts/run_classification.py"
    assert capabilities[BatchStage.P5_B].requires_p3c is True
    assert capabilities[BatchStage.P6_A].supported_modes == ("rew_sweep",)
    assert capabilities[BatchStage.P6_B].real_multisine_blocked is True


def test_p2b_preview_writes_exact_scope_input_and_hashes(tmp_path: Path) -> None:
    first, expected1 = _registered(tmp_path / "inputs", "ui3-cont-01", "R01", "s-plan-01")
    second, expected2 = _registered(tmp_path / "inputs", "ui3-cont-02", "R02", "s-plan-02")
    service = BatchWorkflowService(PROJECT_ROOT)
    prepared = service.prepare_p2b(
        expected_samples=(expected1, expected2),
        registrations=(first, second),
        preview_directory=tmp_path / "P2-B preview 中文",
        config_path=PROJECT_ROOT / "config/default.yaml",
        output_root=tmp_path / "outputs with spaces",
        run_id="ui3-p2b-test",
        feature_kind=FeatureKind.DENSE_RAW_SPL,
        selection_reason="Explicitly confirmed UI3 plan samples",
    )

    scope = json.loads(prepared.scope_path.read_text(encoding="utf-8"))
    inputs = json.loads(prepared.input_manifest_path.read_text(encoding="utf-8"))
    assert [item["sample_id"] for item in scope["members"]] == ["ui3-cont-01", "ui3-cont-02"]
    assert scope["expected_conditions"][0]["expected_count"] == 2
    assert [item["sample_id"] for item in inputs["measurements"]] == ["ui3-cont-01", "ui3-cont-02"]
    assert prepared.program
    assert Path(prepared.arguments[0]).name == "run_dataset_qc.py"
    assert (prepared.preview_directory / "expected_condition_matrix.csv").is_file()
    hashes = json.loads((prepared.preview_directory / "artifact_hashes.json").read_text(encoding="utf-8"))
    assert hashes["dataset_scope.json"] == artifact_sha256(prepared.scope_path)
    assert hashes["dataset_inputs.json"] == artifact_sha256(prepared.input_manifest_path)

    with pytest.raises(FileExistsError):
        service.prepare_p2b(
            expected_samples=(expected1, expected2), registrations=(first, second),
            preview_directory=prepared.preview_directory,
            config_path=PROJECT_ROOT / "config/default.yaml", output_root=tmp_path / "out2",
            run_id="other", feature_kind=FeatureKind.DENSE_RAW_SPL,
            selection_reason="Explicit selection",
        )


def test_prepared_p2b_runs_existing_formal_cli_e2e(tmp_path: Path) -> None:
    first, expected1 = _registered(tmp_path / "inputs", "ui3-e2e-01", "R01", "s-e2e-01")
    second, expected2 = _registered(tmp_path / "inputs", "ui3-e2e-02", "R02", "s-e2e-02")
    service = BatchWorkflowService(PROJECT_ROOT)
    prepared = service.prepare_p2b(
        expected_samples=(expected1, expected2), registrations=(first, second),
        preview_directory=tmp_path / "preview", config_path=PROJECT_ROOT / "config/default.yaml",
        output_root=tmp_path / "outputs", run_id="ui3-p2b-e2e",
        feature_kind=FeatureKind.DENSE_RAW_SPL, selection_reason="Confirmed E2E cohort",
    )

    exit_code = run_dataset_quality_cli(
        prepared.arguments[1:], project_root=PROJECT_ROOT
    )
    assert exit_code == 0
    summary = service.load_p2b_summary(prepared.output_directory)
    assert summary.processing_status == "completed"
    assert summary.aggregate_status in {"valid", "warning", "exclude_candidate"}
    assert summary.scientifically_eligible is False


def test_p2b_rejects_final_test_calibration_mixed_provenance_and_missing_features(tmp_path: Path) -> None:
    registered, expected = _registered(tmp_path / "inputs", "ui3-gate-01", "R01", "s-gate-01")
    service = BatchWorkflowService(PROJECT_ROOT)
    for role in (ExperimentRole.FINAL_TEST_SEALED, ExperimentRole.CALIBRATION):
        with pytest.raises(ValueError, match="role"):
            service.prepare_p2b(
                expected_samples=(ExpectedSample.from_dict({**expected.to_dict(), "experiment_role": role.value}),),
                registrations=(registered,), preview_directory=tmp_path / role.value,
                config_path=PROJECT_ROOT / "config/default.yaml", output_root=tmp_path / "out",
                run_id=f"gate-{role.value}", feature_kind=FeatureKind.DENSE_RAW_SPL,
                selection_reason="Explicit gate test",
            )
    no_feature = RegisteredSample(
        **{**{name: getattr(registered, name) for name in registered.__dataclass_fields__}, "feature_set_available": False, "artifacts": ()}
    )
    with pytest.raises(ValueError, match="FeatureSet"):
        service.prepare_p2b(
            expected_samples=(expected,), registrations=(no_feature,), preview_directory=tmp_path / "missing-feature",
            config_path=PROJECT_ROOT / "config/default.yaml", output_root=tmp_path / "out",
            run_id="missing", feature_kind=FeatureKind.DENSE_RAW_SPL,
            selection_reason="Explicit gate test",
        )


def test_formal_stage_preview_uses_production_script_and_records_ui_report(
    tmp_path: Path, monkeypatch
) -> None:
    service = BatchWorkflowService(PROJECT_ROOT)
    scope = tmp_path / "scope.json"
    inputs = tmp_path / "inputs.json"
    p2b = tmp_path / "p2b"
    p2b.mkdir()
    (p2b / "dataset_qc.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        BatchWorkflowService,
        "load_p2b_summary",
        staticmethod(
            lambda directory: DatasetQCSummary(
                "completed", "valid", True, (), False, 0, 0, 0
            )
        ),
    )
    (p2b / "dataset_qc_manifest.json").write_text("{}", encoding="utf-8")
    scope.write_text(json.dumps({"analysis_scope": {"run_purpose": "software_validation"}}), encoding="utf-8")
    inputs.write_text(json.dumps({"data_origin": "simulated", "run_purpose": "software_validation"}), encoding="utf-8")

    prepared = service.prepare_formal_stage(
        stage=BatchStage.P4,
        scope_path=scope,
        input_manifest_path=inputs,
        preview_directory=tmp_path / "formal preview",
        config_path=PROJECT_ROOT / "config/default.yaml",
        output_root=tmp_path / "outputs",
        run_id="ui3-p4",
        dataset_qc_directory=p2b,
    )
    assert Path(prepared.arguments[0]).name == "run_comparison_metrics.py"
    assert "--dataset-qc-dir" in prepared.arguments
    snapshot = json.loads(
        (prepared.preview_directory / "ui_scope_snapshot.json").read_text(
            encoding="utf-8"
        )
    )
    assert snapshot["dataset_qc_manifest_sha256"] == artifact_sha256(
        p2b / "dataset_qc_manifest.json"
    )
    assert snapshot["dataset_qc_result_sha256"] == artifact_sha256(
        p2b / "dataset_qc.json"
    )
    log, report, html = service.record_stage_result(
        prepared, outcome="cancelled", exit_code=1, stdout="partial log", stderr="",
        result_summary={"scientifically_eligible": False},
    )
    assert log.is_file() and report.is_file() and html.is_file()
    assert "Scientifically eligible: `false`" in report.read_text(encoding="utf-8")


def test_formal_stage_blocks_final_test_before_input_manifest_read_and_real_multisine(tmp_path: Path) -> None:
    service = BatchWorkflowService(PROJECT_ROOT)
    final_scope = tmp_path / "final_scope.json"
    invalid_inputs = tmp_path / "invalid_inputs.json"
    final_scope.write_text(json.dumps({"run_purpose": "software_validation", "cohort_role": "final_test"}), encoding="utf-8")
    invalid_inputs.write_text("not JSON and must not be read", encoding="utf-8")
    with pytest.raises(FinalTestSealedError):
        service.prepare_formal_stage(
            stage=BatchStage.P5_A, scope_path=final_scope, input_manifest_path=invalid_inputs,
            preview_directory=tmp_path / "preview-final", config_path=PROJECT_ROOT / "config/default.yaml",
            output_root=tmp_path / "outputs", run_id="final-block", dataset_qc_directory=tmp_path / "p2b",
        )

    scope = tmp_path / "real_scope.json"
    inputs = tmp_path / "real_inputs.json"
    scope.write_text(json.dumps({"run_purpose": "software_validation"}), encoding="utf-8")
    inputs.write_text(json.dumps({"data_origin": "real_experiment", "run_purpose": "software_validation"}), encoding="utf-8")
    with pytest.raises(PermissionError, match="真实 Multisine"):
        service.prepare_formal_stage(
            stage=BatchStage.P6_B, scope_path=scope, input_manifest_path=inputs,
            preview_directory=tmp_path / "preview-real", config_path=PROJECT_ROOT / "config/default.yaml",
            output_root=tmp_path / "outputs", run_id="real-block", dataset_qc_directory=tmp_path / "p2b",
        )

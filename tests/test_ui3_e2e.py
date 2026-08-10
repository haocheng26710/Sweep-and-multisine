from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from acoustic_encoder.dataset_quality_cli import run_dataset_quality_cli
from acoustic_encoder.schemas import FeatureKind, artifact_sha256, save_feature_set
from acoustic_encoder.ui.batch_workflow import BatchStage, BatchWorkflowService
from acoustic_encoder.ui.experiment_plan import ExperimentPlan, ExperimentPlanService
from acoustic_encoder.ui.sample_registry import MatchStatus, SampleRegistry
from test_dataset_quality_control import _measurement
from test_ui3_experiment_plan import _plan, _ready_checklist


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _two_sample_plan() -> ExperimentPlan:
    payload = _plan().to_dict()
    payload["condition_blocks"][0].update(
        {
            "angles_deg": [0.0],
            "cont_repeats": 2,
            "repos_rounds": 0,
            "repos_repeats_per_round": 0,
            "reasm_assemblies": 0,
            "reasm_repeats_per_assembly": 0,
        }
    )
    return ExperimentPlan.from_dict(payload)


def _write_ui2_session_and_output(root: Path, expected, index: int) -> tuple[Path, Path]:
    root.mkdir(parents=True)
    source = root / f"模拟输入 {index}.txt"
    source.write_bytes(f"simulated-{index}".encode("ascii"))
    source_hash = artifact_sha256(source)
    source_sample_id = f"ui3-plan-e2e-{index:02d}"
    feature, qc = _measurement(
        source_sample_id,
        repeat_id=expected.repeat_id,
        repeat_type=expected.repeat_type,
        session_id=expected.session_id,
        angle_deg=expected.angle_deg,
        configuration=expected.configuration_id,
        reposition_round_id=expected.reposition_round_id,
        assembly_id=expected.assembly_id,
        acquisition_block_id=expected.acquisition_block_id,
    )
    metadata = replace(
        feature.meta,
        source_path=source.as_posix(),
        source_sha256=source_hash,
        provenance_uri="mock://DEV-UI3-E2E",
    )
    feature = replace(feature, feature_kind=FeatureKind.DENSE_RAW_SPL, meta=metadata)
    metadata_path = root / "measurement_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    config_path = root / "resolved_config.yaml"
    config_path.write_text("run_purpose: software_validation\n", encoding="utf-8")
    session_manifest = root / "ui_session_manifest.json"
    session_payload = {
        "ui_session_schema_version": "1.0.0",
        "sample_id": source_sample_id,
        "run_id": f"ui2-e2e-{index}",
        "revision": 1,
        "route": "simulated_practice",
        "measurement_mode": "rew_sweep",
        "data_origin": "simulated",
        "dataset_role": "software_validation",
        "run_purpose": "software_validation",
        "eligible_for_scientific_analysis": False,
        "analysis_status": "completed",
        "analysis_block_reason": None,
        "git_commit": "a" * 40,
        "created_at_utc": "2026-08-10T12:00:00+00:00",
        "source_path": source.as_posix(),
        "metadata_path": metadata_path.as_posix(),
        "config_snapshot_path": config_path.as_posix(),
        "inputs": [{"path": source.as_posix(), "sha256": source_hash, "role": "source"}],
    }
    session_manifest.write_text(
        json.dumps(session_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    session_manifest.with_suffix(".sha256").write_text(
        artifact_sha256(session_manifest), encoding="ascii"
    )

    output = root / "run output"
    feature_base = output / "processed/features/dense_raw_spl" / source_sample_id
    npz_path, feature_json = save_feature_set(feature, feature_base)
    qc_path = output / "quality/quality_control.json"
    qc_path.parent.mkdir(parents=True)
    qc_path.write_text(
        json.dumps(qc.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifacts = []
    for path in (npz_path, feature_json, qc_path):
        artifacts.append(
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": artifact_sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    (output / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_manifest_schema_version": "2.0.0",
                "processing_status": "completed",
                "success": True,
                "sample_id": source_sample_id,
                "measurement_mode": "rew_sweep",
                "data_origin": "simulated",
                "dataset_role": "software_validation",
                "run_purpose": "software_validation",
                "eligible_for_scientific_analysis": False,
                "recording_hash": source_hash,
                "qc_status": "valid",
                "artifacts": artifacts,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return session_manifest, output


def test_simulated_plan_registration_and_formal_p2b_e2e(tmp_path: Path) -> None:
    plan_service = ExperimentPlanService(tmp_path / "plans")
    saved = plan_service.save_revision(_two_sample_plan(), _ready_checklist())
    registry = SampleRegistry(tmp_path / "registry")
    registrations = []
    for index, expected in enumerate(saved.samples, start=1):
        session, output = _write_ui2_session_and_output(
            tmp_path / "sessions" / str(index), expected, index
        )
        registrations.append(
            registry.register_ui2_session(
                session, expected=expected, output_directory=output
            )
        )
    matched = registry.match(saved.samples, registrations)
    assert {row.status for row in matched.rows} == {MatchStatus.EXPECTED_AND_PRESENT}

    service = BatchWorkflowService(PROJECT_ROOT)
    invocation = service.prepare_p2b(
        expected_samples=saved.samples,
        registrations=registrations,
        preview_directory=tmp_path / "P2-B preview 中文",
        config_path=PROJECT_ROOT / "config/default.yaml",
        output_root=tmp_path / "outputs",
        run_id="ui3-plan-registration-p2b",
        feature_kind=FeatureKind.DENSE_RAW_SPL,
        selection_reason="Confirmed simulated DEV-UI3 plan E2E",
    )
    assert run_dataset_quality_cli(
        invocation.arguments[1:], project_root=PROJECT_ROOT
    ) == 0
    summary = service.load_p2b_summary(invocation.output_directory)
    assert summary.processing_status == "completed"
    assert summary.scientifically_eligible is False
    assert summary.canonical_ready is False
    scope_path = tmp_path / "formal-scope.json"
    inputs_path = tmp_path / "formal-inputs.json"
    scope_path.write_text(
        json.dumps({"run_purpose": "software_validation"}), encoding="utf-8"
    )
    inputs_path.write_text(
        json.dumps(
            {
                "data_origin": "simulated",
                "run_purpose": "software_validation",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="canonical-ready"):
        service.prepare_formal_stage(
            stage=BatchStage.P4,
            scope_path=scope_path,
            input_manifest_path=inputs_path,
            preview_directory=tmp_path / "must-not-open",
            config_path=PROJECT_ROOT / "config/default.yaml",
            output_root=tmp_path / "outputs",
            run_id="blocked-p4",
            dataset_qc_directory=invocation.output_directory,
        )
    log, report, html = service.record_stage_result(
        invocation,
        outcome="succeeded",
        exit_code=0,
        stdout="formal P2-B completed",
        stderr="",
        result_summary={
            "aggregate_status": summary.aggregate_status,
            "canonical_ready": summary.canonical_ready,
            "scientifically_eligible": summary.scientifically_eligible,
        },
    )
    assert log.is_file() and report.is_file() and html.is_file()
    assert invocation.output_directory.is_dir()

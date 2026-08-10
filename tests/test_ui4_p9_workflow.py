from __future__ import annotations

import json
from pathlib import Path

import pytest

from acoustic_encoder.ui.p9_workflow import P9WorkflowService
from acoustic_encoder.ui.runtime import RuntimeContext


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_p9a_preview_rejects_any_final_test_member_before_worker_start(tmp_path: Path) -> None:
    runtime = RuntimeContext.for_source(tmp_path, workspace_root=tmp_path / "workspace")
    service = P9WorkflowService(runtime)
    scope = _write_json(
        tmp_path / "scope.json",
        {
            "schema_version": "1.0.0",
            "members": [{"sample_id": "sealed-1", "cohort_role": "final_test"}],
            "final_test_sealed": True,
        },
    )
    inputs = _write_json(tmp_path / "inputs.json", {"features": []})
    candidates = _write_json(tmp_path / "candidates.json", {"candidates": []})
    dataset_qc = tmp_path / "dataset_qc"
    dataset_qc.mkdir()

    with pytest.raises(PermissionError, match="final-test"):
        service.prepare_p9a(
            config=tmp_path / "config.yaml",
            scope=scope,
            inputs=inputs,
            candidate_universe=candidates,
            dataset_qc_directory=dataset_qc,
            output_root=runtime.output_root,
            run_id="p9a-test",
        )


def test_p9a_preview_uses_explicit_authorities_and_formal_worker_arguments(tmp_path: Path) -> None:
    resource_root = tmp_path / "resources"
    resource_root.mkdir()
    runtime = RuntimeContext.for_source(resource_root, workspace_root=tmp_path / "workspace")
    service = P9WorkflowService(runtime)
    config = tmp_path / "config.yaml"
    config.write_text("pipeline_version: 2.0.0\n", encoding="utf-8")
    scope = _write_json(
        tmp_path / "scope.json",
        {"members": [{"sample_id": "train-1", "cohort_role": "training"}]},
    )
    inputs = _write_json(tmp_path / "inputs.json", {"features": []})
    candidates = _write_json(tmp_path / "candidates.json", {"candidates": []})
    dataset_qc = tmp_path / "dataset qc"
    dataset_qc.mkdir()
    _write_json(dataset_qc / "dataset_qc_manifest.json", {"schema_version": "1.0.0"})

    invocation = service.prepare_p9a(
        config=config,
        scope=scope,
        inputs=inputs,
        candidate_universe=candidates,
        dataset_qc_directory=dataset_qc,
        output_root=runtime.output_root,
        run_id="p9a-001",
    )

    assert invocation.stage == "P9-A"
    assert invocation.final_test_read is False
    assert invocation.scientifically_eligible is False
    assert invocation.output_directory.name == "tone_selection"
    assert "--worker" in invocation.arguments
    assert "p9a" in invocation.arguments
    assert "--dataset-qc-dir" in invocation.arguments
    assert len(invocation.input_hashes) == 5


def test_p9b_is_locked_until_explicit_p9a_fold_authority_exists(tmp_path: Path) -> None:
    runtime = RuntimeContext.for_source(tmp_path, workspace_root=tmp_path / "workspace")
    service = P9WorkflowService(runtime)
    for name in ("config.yaml", "scope.json", "inputs.json", "candidates.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")

    with pytest.raises(PermissionError, match="P9-A"):
        service.prepare_p9b(
            config=tmp_path / "config.yaml",
            scope=tmp_path / "scope.json",
            inputs=tmp_path / "inputs.json",
            candidate_universe=tmp_path / "candidates.json",
            p9a_authority_directories=(),
            output_root=runtime.output_root,
            run_id="p9b-001",
        )


def test_p9c_real_multisine_authority_remains_hard_blocked(tmp_path: Path) -> None:
    runtime = RuntimeContext.for_source(tmp_path, workspace_root=tmp_path / "workspace")
    service = P9WorkflowService(runtime)
    config = tmp_path / "config.yaml"
    config.write_text("{}", encoding="utf-8")
    scope = _write_json(
        tmp_path / "scope.json",
        {
            "data_origin": "real_experiment",
            "measurement_modes": ["rew_sweep", "schroeder_multisine"],
            "pairing_authority_sha256": "a" * 64,
        },
    )
    inputs = _write_json(tmp_path / "inputs.json", {"pairs": []})

    with pytest.raises(PermissionError, match="real Multisine/P8"):
        service.prepare_p9c(
            config=config,
            scope=scope,
            inputs=inputs,
            output_root=runtime.output_root,
            run_id="p9c-001",
        )


def test_p9d_preview_rejects_final_test_training_and_existing_package(tmp_path: Path) -> None:
    runtime = RuntimeContext.for_source(tmp_path, workspace_root=tmp_path / "workspace")
    service = P9WorkflowService(runtime)
    config = tmp_path / "config.yaml"
    config.write_text("{}", encoding="utf-8")
    training = _write_json(
        tmp_path / "training.json",
        {"training_features": [{"sample_id": "sealed", "cohort_role": "final_test"}]},
    )

    with pytest.raises(PermissionError, match="final-test"):
        service.prepare_p9d(
            config=config,
            training_manifest=training,
            output_directory=runtime.workspace_root / "packages" / "package-r1",
            approval_operator="tester",
        )


def test_p9a_manifest_preview_is_explicit_hashed_and_not_overwritten(tmp_path: Path) -> None:
    runtime = RuntimeContext.for_source(tmp_path, workspace_root=tmp_path / "workspace")
    service = P9WorkflowService(runtime)
    preview = service.write_p9a_manifest_preview(
        preview_directory=runtime.workspace_root / "staging" / "p9a-preview",
        scope={"members": [{"sample_id": "train", "cohort_role": "training"}]},
        inputs={"features": [{"sample_id": "train", "path": "chosen.json"}]},
        candidate_universe={"candidates": [{"tone_id": "t1", "frequency_hz": 1000.0}]},
        selection_reason="explicit plan member selected by operator",
    )

    assert preview.scope_path.is_file()
    assert preview.input_path.is_file()
    assert preview.candidate_path.is_file()
    assert len(preview.hashes) == 3
    with pytest.raises(FileExistsError):
        service.write_p9a_manifest_preview(
            preview_directory=preview.directory,
            scope={}, inputs={}, candidate_universe={}, selection_reason="repeat",
        )


def test_package_finalize_fails_closed_when_self_check_is_invalid(tmp_path: Path) -> None:
    runtime = RuntimeContext.for_source(tmp_path, workspace_root=tmp_path / "workspace")
    service = P9WorkflowService(runtime)
    package = tmp_path / "package"
    package.mkdir()
    _write_json(package / "package_manifest.json", {"lifecycle": "software_validation_only"})

    with pytest.raises((FileNotFoundError, ValueError)):
        service.finalize_package(package, approval_operator="tester")
    assert not (package / "freeze_approval_record.json").exists()

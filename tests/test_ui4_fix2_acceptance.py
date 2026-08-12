from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from acoustic_encoder.ui.acceptance_assets import audit_acceptance_assets
from acoustic_encoder.ui.worker_entry import run_worker_safely
from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.workers import ProcessOutcome

from test_ui_main_window import _window


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_validation_asset_closure_is_complete_and_hash_verified() -> None:
    audit = audit_acceptance_assets(PROJECT_ROOT)

    assert audit.available is True
    assert audit.hashes_verified is True
    assert audit.manifest_path == (
        PROJECT_ROOT / "validation_assets/pre_experiment_acceptance/assets_manifest.json"
    )
    fixture_manifest = json.loads(
        (PROJECT_ROOT / "tests/fixtures/rew/external_reference/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    fixture_records = {
        item.relative_path: item for item in audit.assets if item.asset_role == "rew_fixture"
    }
    assert len(fixture_records) == 3
    for expected in fixture_manifest["files"]:
        relative = (
            "validation_assets/pre_experiment_acceptance/rew/external_reference/"
            f"{expected['file_name']}"
        )
        record = fixture_records[relative]
        assert record.sha256 == expected["sha256"]
        copied = PROJECT_ROOT / relative
        assert hashlib.sha256(copied.read_bytes()).hexdigest() == expected["sha256"]

    required_configs = {
        "default.yaml",
        "validation_dev_c16_acceptance.yaml",
        "validation_dev_c4_matched_tones.yaml",
        "experiment_v2_u4.yaml",
        "experiment_v2_u4_multisine.yaml",
        "stimulus_multisine_broadband.yaml",
        "validation_dev_c13_p9b.yaml",
        "validation_dev_c14_p9c.yaml",
        "validation_dev_c15_p9d.yaml",
    }
    assert required_configs <= {
        Path(item.relative_path).name
        for item in audit.assets
        if item.asset_role == "config"
    }


def test_windows_spec_packages_explicit_validation_assets_not_source_tests() -> None:
    spec = (PROJECT_ROOT / "SweepMultisineUI.spec").read_text(encoding="utf-8")

    assert "validation_assets/pre_experiment_acceptance" in spec
    assert "tests/fixtures" not in spec
    assert "DEV-C16_PRE_EXPERIMENT_ACCEPTANCE.md" in spec
    assert "DEV_D_REAL_EXPERIMENT_ENTRY_CHECKLIST.md" in spec


def test_unexpected_frozen_worker_failure_is_structured_and_writes_technical_log(
    tmp_path: Path,
) -> None:
    error_stream = io.StringIO()
    output_root = tmp_path / "中文 工作区" / "outputs"

    def explode(*args, **kwargs) -> int:
        raise FileNotFoundError("validation_assets/missing.json")

    exit_code = run_worker_safely(
        "acceptance",
        ["--output-root", str(output_root), "--run-id", "missing-assets"],
        resource_root=tmp_path / "resources",
        workspace_root=tmp_path / "中文 工作区",
        dispatcher=explode,
        error_stream=error_stream,
    )

    assert exit_code != 0
    payload = json.loads(error_stream.getvalue())
    assert payload["status"] == "failed"
    assert payload["error_code"] == "worker_unexpected_exception"
    assert payload["exception_type"] == "FileNotFoundError"
    assert "missing.json" in payload["message"]
    assert "Traceback" in payload["traceback"]
    log = (
        output_root
        / "simulated/software_validation/missing-assets/acceptance/technical_log.txt"
    )
    assert log.is_file()
    text = log.read_text(encoding="utf-8")
    assert "FileNotFoundError" in text
    assert "validation_assets/missing.json" in text


def test_environment_pass_and_acceptance_failure_have_separate_ui_states(
    qtbot,
    tmp_path: Path,
) -> None:
    window, _, worker = _window(qtbot, tmp_path)

    window.environment_button.click()
    assert window.environment_status_label.text() == "环境检查：passed"
    assert window.state.step("environment").status.value == "passed"

    window.acceptance_button.click()
    worker.complete(ProcessOutcome.FAILED, 70)

    assert window.environment_status_label.text() == "环境检查：passed"
    assert window.acceptance_status_label.text() == "模拟验收：failed"
    assert window.environment_overall_status_label.text() == "当前阶段总体状态：failed"
    assert window.state.step("environment").status.value == "passed"
    assert window.acceptance_button.isEnabled()
    assert "T0～T3 与 V2 最低要求：尚未完成" in window.acceptance_summary.text()
    assert "模拟验收未完成：打包验证资源缺失或不可读取。" in window.result_label.text()


def test_missing_packaged_asset_returns_failure_without_uncaught_exception(
    tmp_path: Path,
) -> None:
    resources = tmp_path / "empty frozen resources"
    workspace = tmp_path / "空格 中文 工作区"
    resources.mkdir()
    workspace.mkdir()
    stderr = io.StringIO()
    run_id = "missing-real-assets"

    exit_code = run_worker_safely(
        "acceptance",
        [
            "--project-root",
            str(resources),
            "--config",
            str(resources / "config/validation_dev_c16_acceptance.yaml"),
            "--output-root",
            str(workspace / "outputs"),
            "--run-id",
            run_id,
        ],
        resource_root=resources,
        workspace_root=workspace,
        error_stream=stderr,
    )

    payload = json.loads(stderr.getvalue())
    assert exit_code == 70
    assert payload["exception_type"] == "FileNotFoundError"
    assert "missing_asset_manifest" in payload["message"]
    assert Path(payload["technical_log"]).is_file()

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from enum import Enum

from acoustic_encoder.ui.services import (
    ApplicationServices,
    EnvironmentCheckStatus,
    humanize_exception,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project with spaces"
    (project / "config").mkdir(parents=True)
    (project / "outputs").mkdir()
    for name in (
        "default.yaml",
        "experiment_v2_u4.yaml",
        "experiment_v2_u4_multisine.yaml",
    ):
        (project / "config" / name).write_text("placeholder: true\n", encoding="utf-8")
    return project


def _git_runner(args: list[str], cwd: Path) -> SimpleNamespace:
    del cwd
    if args[-1] == "HEAD":
        return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def test_environment_check_reports_success_without_writing_project(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    before = sorted(path.relative_to(project) for path in project.rglob("*"))
    service = ApplicationServices(
        project,
        required_modules=("core_ok", "PySide6"),
        module_importer=lambda name: object(),
        git_runner=_git_runner,
    )

    report = service.check_environment()

    assert report.passed
    assert report.git_commit == "abc123"
    assert report.git_worktree_clean is True
    assert report.item("outputs_writable").status is EnvironmentCheckStatus.PASSED
    assert report.item("dependency:PySide6").status is EnvironmentCheckStatus.PASSED
    assert before == sorted(path.relative_to(project) for path in project.rglob("*"))


def test_environment_check_preserves_missing_dependency_details(tmp_path: Path) -> None:
    project = _make_project(tmp_path)

    def importer(name: str) -> object:
        if name == "missing_core":
            raise ModuleNotFoundError("No module named 'missing_core'")
        return object()

    report = ApplicationServices(
        project,
        required_modules=("missing_core",),
        module_importer=importer,
        git_runner=_git_runner,
    ).check_environment()

    item = report.item("dependency:missing_core")
    assert not report.passed
    assert item.status is EnvironmentCheckStatus.FAILED
    assert "missing_core" in item.technical_detail


def test_sweep_and_multisine_validation_delegate_to_existing_config_loader() -> None:
    service = ApplicationServices(PROJECT_ROOT)

    sweep = service.validate_config(
        PROJECT_ROOT / "config/experiment_v2_u4.yaml",
        expected_mode="rew_sweep",
    )
    multisine = service.validate_config(
        PROJECT_ROOT / "config/experiment_v2_u4_multisine.yaml",
        expected_mode="schroeder_multisine",
    )

    assert sweep.success and multisine.success
    assert sweep.measurement_mode == "rew_sweep"
    assert multisine.measurement_mode == "schroeder_multisine"
    assert sweep.pipeline_version.startswith("2.0.0")
    assert sweep.schema_versions == {
        "config": "2.20.0",
        "measurement": "2.4.0",
        "feature": "2.3.0",
    }
    assert sweep.run_purpose == "software_validation"
    assert sweep.provisional is True


def test_config_mode_mismatch_is_failure_with_human_and_technical_details() -> None:
    result = ApplicationServices(PROJECT_ROOT).validate_config(
        PROJECT_ROOT / "config/experiment_v2_u4.yaml",
        expected_mode="schroeder_multisine",
    )

    assert not result.success
    assert "配置入口不匹配" in result.user_message
    assert "rew_sweep" in result.technical_detail


def test_unknown_exception_has_safe_human_message_and_keeps_technical_detail() -> None:
    user_message, technical = humanize_exception(RuntimeError("device exploded"))

    assert user_message == "发生未知错误，操作已安全停止，未写入成功标记。"
    assert "RuntimeError: device exploded" in technical


def test_acceptance_summary_exposes_t0_t3_v2_and_test_status(tmp_path: Path) -> None:
    class Status(str, Enum):
        PASS = "pass"

    acceptance = tmp_path / "acceptance"
    acceptance.mkdir()
    (acceptance / "pre_experiment_acceptance_report.md").write_text(
        "report", encoding="utf-8"
    )
    (acceptance / "leakage_and_provenance_audit.json").write_text(
        '{"supporting_validation":{"verification_commands":{"full_pytest":'
        '{"status":"pass","passed_count":700,"summary_tail":"700 passed"}}}}',
        encoding="utf-8",
    )
    result = SimpleNamespace(
        stage_checks=tuple(
            SimpleNamespace(check_id=f"T{index}", status=Status.PASS)
            for index in range(4)
        ),
        requirement_checks=tuple(
            SimpleNamespace(status=Status.PASS) for _ in range(14)
        ),
        overall_status=Status.PASS,
        software_integration_ready=True,
        ready_for_dev_d_diagnostic_experiment=True,
        scientifically_eligible=False,
    )
    manifest = {"software_integration_ready": True}
    service = ApplicationServices(
        tmp_path,
        acceptance_loader=lambda path: (result, manifest),
    )

    summary = service.load_acceptance_summary(acceptance)

    assert summary.stage_statuses == {
        "T0": "pass",
        "T1": "pass",
        "T2": "pass",
        "T3": "pass",
    }
    assert summary.v2_requirement_pass_count == 14
    assert summary.v2_requirement_total == 14
    assert summary.test_status == "pass"
    assert summary.test_passed_count == 700
    assert summary.software_integration_ready
    assert not summary.scientifically_eligible
    assert summary.report_path.name == "pre_experiment_acceptance_report.md"

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, Qt, Signal

from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.services import (
    AcceptanceSummary,
    ConfigValidationResult,
    EnvironmentCheckItem,
    EnvironmentCheckStatus,
    EnvironmentReport,
)
from acoustic_encoder.ui.state import HARD_BLOCK_REAL_MULTISINE_MESSAGE
from acoustic_encoder.ui.workers import ProcessOutcome, ProcessResult


class FakeServices:
    def __init__(self, project_root: Path, *, fail_environment: bool = False) -> None:
        self.project_root = project_root
        self.fail_environment = fail_environment
        self.validated_modes: list[str] = []

    def check_environment(self) -> EnvironmentReport:
        if self.fail_environment:
            raise RuntimeError("technical environment failure")
        return EnvironmentReport(
            project_root=self.project_root,
            python_version="3.12.4",
            git_commit="abc123",
            git_worktree_clean=True,
            checks=(
                EnvironmentCheckItem(
                    "python_version",
                    "Python 版本",
                    EnvironmentCheckStatus.PASSED,
                    "3.12.4",
                    "Python 可用。",
                ),
            ),
        )

    def validate_config(self, path: Path, *, expected_mode: str) -> ConfigValidationResult:
        self.validated_modes.append(expected_mode)
        return ConfigValidationResult(
            success=True,
            config_path=path,
            measurement_mode=expected_mode,
            pipeline_version="2.0.0-dev.21",
            schema_versions={
                "config": "2.20.0",
                "measurement": "2.4.0",
                "feature": "2.3.0",
            },
            run_purpose="software_validation",
            provisional=True,
            migration_warnings=(),
            user_message="配置已通过现有加载与 schema 验证。",
            technical_detail="provisional_blocks=quality_control",
        )

    def load_acceptance_summary(self, output: Path) -> AcceptanceSummary:
        return AcceptanceSummary(
            output_directory=output,
            report_path=output / "pre_experiment_acceptance_report.md",
            stage_statuses={f"T{index}": "pass" for index in range(4)},
            v2_requirement_pass_count=14,
            v2_requirement_total=14,
            overall_status="pass",
            test_status="pass",
            test_passed_count=700,
            test_summary="700 passed",
            software_integration_ready=True,
            ready_for_dev_d_diagnostic_experiment=True,
            scientifically_eligible=False,
        )


class FakeAcceptanceWorker(QObject):
    started = Signal(str, object)
    stdout_received = Signal(str)
    stderr_received = Signal(str)
    finished = Signal(str, object, object)

    def __init__(self, output: Path) -> None:
        super().__init__()
        self.output = output
        self.is_running = False
        self.cancel_called = False
        self.invocation = SimpleNamespace(
            run_id="fake-run",
            program="python",
            arguments=["script.py", "--run-id", "fake-run"],
            output_directory=output,
        )

    def start(self):
        self.is_running = True
        self.started.emit("fake-run", self.invocation)
        return self.invocation

    def cancel(self) -> None:
        self.cancel_called = True
        self.complete(ProcessOutcome.CANCELLED, -15)

    def complete(self, outcome: ProcessOutcome, exit_code: int) -> None:
        self.is_running = False
        result = ProcessResult(
            outcome=outcome,
            exit_code=exit_code,
            stdout="acceptance stdout",
            stderr="acceptance stderr" if exit_code else "",
            program="python",
            arguments=("script.py", "--run-id", "fake-run"),
        )
        self.finished.emit("fake-run", result, self.invocation)


def _window(qtbot, tmp_path: Path, *, fail_environment: bool = False):
    output = tmp_path / "output/acceptance"
    output.mkdir(parents=True)
    (output / "pre_experiment_acceptance_report.md").write_text(
        "report", encoding="utf-8"
    )
    services = FakeServices(tmp_path, fail_environment=fail_environment)
    worker = FakeAcceptanceWorker(output)
    window = MainWindow(tmp_path, services=services, acceptance_worker=worker)
    qtbot.addWidget(window)
    window.show()
    return window, services, worker


def test_window_smoke_defaults_to_simple_mode_and_text_statuses(qtbot, tmp_path: Path) -> None:
    window, _, _ = _window(qtbot, tmp_path)

    assert window.windowTitle()
    assert len(window.step_buttons) == 12
    assert "ready" in window.step_buttons["environment"].text()
    assert "not_started" in window.step_buttons["usage"].text()
    assert window.mode_combo.currentData() == "simple"
    assert window.professional_panel.isHidden()


def test_professional_mode_reveals_details_without_changing_gate_state(qtbot, tmp_path: Path) -> None:
    window, _, _ = _window(qtbot, tmp_path)
    before = window.state.step("single_measurement").status

    window.mode_combo.setCurrentIndex(1)

    assert window.mode_combo.currentData() == "professional"
    assert not window.professional_panel.isHidden()
    assert window.state.step("single_measurement").status is before


def test_environment_check_and_both_config_buttons_show_backend_results(qtbot, tmp_path: Path) -> None:
    window, services, _ = _window(qtbot, tmp_path)

    qtbot.mouseClick(window.environment_button, Qt.LeftButton)
    window.select_step("usage")
    qtbot.mouseClick(window.validate_sweep_button, Qt.LeftButton)
    qtbot.mouseClick(window.validate_multisine_button, Qt.LeftButton)

    assert "环境检查通过" in window.result_label.text()
    assert services.validated_modes == ["rew_sweep", "schroeder_multisine"]
    assert "schroeder_multisine" in window.config_result.toPlainText()
    assert "2.20.0" in window.config_result.toPlainText()
    assert "software_validation" in window.config_result.toPlainText()
    assert "provisional" in window.config_result.toPlainText()


def test_acceptance_success_streams_log_and_displays_t0_t3_and_v2(qtbot, tmp_path: Path) -> None:
    window, _, worker = _window(qtbot, tmp_path)

    qtbot.mouseClick(window.acceptance_button, Qt.LeftButton)
    worker.stdout_received.emit("live line\n")
    worker.complete(ProcessOutcome.SUCCEEDED, 0)

    assert "live line" in window.stdout_log.toPlainText()
    assert window.state.step("environment").status.value == "ready"
    assert window.acceptance_status_label.text() == "模拟验收：passed"
    assert "T0=pass" in window.acceptance_summary.text()
    assert "T3=pass" in window.acceptance_summary.text()
    assert "14/14" in window.acceptance_summary.text()
    assert "700 passed" in window.acceptance_summary.text()
    assert window.open_output_button.isEnabled()
    assert window.view_report_button.isEnabled()


def test_acceptance_failure_and_cancel_are_distinct(qtbot, tmp_path: Path) -> None:
    failed, _, failed_worker = _window(qtbot, tmp_path / "failed")
    qtbot.mouseClick(failed.acceptance_button, Qt.LeftButton)
    failed_worker.complete(ProcessOutcome.FAILED, 2)
    assert failed.acceptance_status_label.text() == "模拟验收：failed"
    assert "失败" in failed.result_label.text()
    assert "T0=pass" in failed.acceptance_summary.text()

    cancelled, _, cancel_worker = _window(qtbot, tmp_path / "cancelled")
    qtbot.mouseClick(cancelled.acceptance_button, Qt.LeftButton)
    qtbot.mouseClick(cancelled.cancel_button, Qt.LeftButton)
    assert cancel_worker.cancel_called
    assert cancelled.acceptance_status_label.text() == "模拟验收：cancelled"
    assert "cancelled" in cancelled.result_label.text()


def test_unimplemented_step_explains_round_preparation_and_reason(qtbot, tmp_path: Path) -> None:
    window, _, _ = _window(qtbot, tmp_path)

    window.select_step("freeze")
    qtbot.mouseClick(window.placeholder_button, Qt.LeftButton)

    text = window.result_label.text()
    assert "DEV-UI4" in text
    assert "准备" in text
    assert "暂时不能执行" in text


def test_real_multisine_hard_block_has_exact_message_and_no_bypass(qtbot, tmp_path: Path) -> None:
    window, _, _ = _window(qtbot, tmp_path)

    window.set_usage(
        data_origin="real_experiment",
        measurement_mode="schroeder_multisine",
        run_purpose="research_analysis",
    )

    assert window.state.step("single_measurement").status.value == "blocked"
    assert window.hard_block_label.text() == HARD_BLOCK_REAL_MULTISINE_MESSAGE
    assert window.real_multisine_run_button.isEnabled() is False
    assert window.findChild(QObject, "eligibleForScientificAnalysisEditor") is None


def test_technical_exception_maps_to_readable_message(qtbot, tmp_path: Path) -> None:
    window, _, _ = _window(qtbot, tmp_path, fail_environment=True)

    qtbot.mouseClick(window.environment_button, Qt.LeftButton)

    assert "发生未知错误" in window.result_label.text()
    assert "RuntimeError: technical environment failure" in window.technical_error.toPlainText()

"""PySide6 guided desktop shell for safe software validation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from acoustic_encoder.ui.services import (
    AcceptanceSummary,
    ApplicationServices,
    ConfigValidationResult,
    EnvironmentReport,
    humanize_exception,
)
from acoustic_encoder.ui.dialogs import format_unimplemented_message
from acoustic_encoder.ui.state import StepStatus, UiMode, WizardState
from acoustic_encoder.ui.workers import (
    AcceptanceInvocation,
    AcceptanceWorker,
    ProcessOutcome,
    ProcessResult,
)


class MainWindow(QMainWindow):
    """Twelve-step shell; DEV-UI1 enables only three validation operations."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        services: ApplicationServices | None = None,
        acceptance_worker: AcceptanceWorker | None = None,
    ) -> None:
        super().__init__()
        self.project_root = Path(project_root).resolve()
        self.state = WizardState()
        self.services = services or ApplicationServices(self.project_root)
        self.acceptance_worker = acceptance_worker or AcceptanceWorker(
            self.project_root, parent=self
        )
        self._current_step_id = "environment"
        self._active_invocation: AcceptanceInvocation | None = None
        self._last_acceptance_summary: AcceptanceSummary | None = None
        self.setWindowTitle("双入口声学分析向导 — 软件验证")
        self.resize(1260, 820)
        self._build_ui()
        self._connect_signals()
        self.select_step("environment")
        self._refresh_step_buttons()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        header = QHBoxLayout()
        title = QLabel("双入口声学分析向导")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(QLabel("界面模式："))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("简易模式", UiMode.SIMPLE.value)
        self.mode_combo.addItem("专业模式", UiMode.PROFESSIONAL.value)
        header.addWidget(self.mode_combo)
        root.addLayout(header)

        provenance = QLabel(
            "数据来源明确区分：simulated（模拟） / external_reference（外部参考） / "
            "real_experiment（真实实验）。当前界面不会授予科研资格。"
        )
        provenance.setWordWrap(True)
        root.addWidget(provenance)

        body = QHBoxLayout()
        step_container = QWidget()
        step_layout = QVBoxLayout(step_container)
        self.step_buttons: dict[str, QPushButton] = {}
        for index, step in enumerate(self.state.steps, start=1):
            button = QPushButton()
            button.setObjectName(f"stepButton_{step.step_id}")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, step_id=step.step_id: self.select_step(step_id)
            )
            self.step_buttons[step.step_id] = button
            step_layout.addWidget(button)
        step_layout.addStretch(1)
        step_scroll = QScrollArea()
        step_scroll.setWidgetResizable(True)
        step_scroll.setWidget(step_container)
        step_scroll.setMinimumWidth(285)
        body.addWidget(step_scroll, 0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.current_step_label = QLabel()
        self.current_step_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        content_layout.addWidget(self.current_step_label)
        self.current_status_label = QLabel()
        content_layout.addWidget(self.current_status_label)
        self.do_label = QLabel()
        self.do_label.setWordWrap(True)
        content_layout.addWidget(self.do_label)

        self.action_stack = QStackedWidget()
        self.environment_page = self._build_environment_page()
        self.usage_page = self._build_usage_page()
        self.placeholder_page = self._build_placeholder_page()
        self.action_stack.addWidget(self.environment_page)
        self.action_stack.addWidget(self.usage_page)
        self.action_stack.addWidget(self.placeholder_page)
        content_layout.addWidget(self.action_stack)

        result_box = QGroupBox("执行结果")
        result_layout = QVBoxLayout(result_box)
        self.result_label = QLabel("尚未执行。")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(
            self.result_label.textInteractionFlags()
            | self.result_label.textInteractionFlags().TextSelectableByMouse
        )
        self.next_step_label = QLabel("下一步建议：先检查软件环境。")
        self.next_step_label.setWordWrap(True)
        result_layout.addWidget(self.result_label)
        result_layout.addWidget(self.next_step_label)
        content_layout.addWidget(result_box)

        self.professional_panel = self._build_professional_panel()
        self.professional_panel.hide()
        content_layout.addWidget(self.professional_panel)
        content_layout.addStretch(1)
        body.addWidget(content, 1)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

    def _build_environment_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.environment_button = QPushButton("检查软件环境")
        self.environment_button.setObjectName("environmentButton")
        self.acceptance_button = QPushButton("运行模拟软件验收")
        self.acceptance_button.setObjectName("acceptanceButton")
        self.cancel_button = QPushButton("取消当前验收")
        self.cancel_button.setObjectName("cancelAcceptanceButton")
        self.cancel_button.setEnabled(False)
        layout.addWidget(self.environment_button)
        layout.addWidget(self.acceptance_button)
        layout.addWidget(self.cancel_button)
        self.acceptance_summary = QLabel("T0～T3 与 V2 最低要求：尚未运行。")
        self.acceptance_summary.setWordWrap(True)
        layout.addWidget(self.acceptance_summary)
        links = QHBoxLayout()
        self.open_output_button = QPushButton("打开结果文件夹")
        self.view_report_button = QPushButton("查看报告")
        self.open_output_button.setEnabled(False)
        self.view_report_button.setEnabled(False)
        links.addWidget(self.open_output_button)
        links.addWidget(self.view_report_button)
        layout.addLayout(links)
        return page

    def _build_usage_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.data_origin_combo = QComboBox()
        self.data_origin_combo.addItem("模拟数据", "simulated")
        self.data_origin_combo.addItem("外部参考", "external_reference")
        self.data_origin_combo.addItem("真实实验", "real_experiment")
        self.measurement_mode_combo = QComboBox()
        self.measurement_mode_combo.addItem("Sweep / REW", "rew_sweep")
        self.measurement_mode_combo.addItem(
            "Schroeder Multisine", "schroeder_multisine"
        )
        self.run_purpose_combo = QComboBox()
        self.run_purpose_combo.addItem("软件验证", "software_validation")
        self.run_purpose_combo.addItem("科研分析", "research_analysis")
        form.addRow("数据来源", self.data_origin_combo)
        form.addRow("测量入口", self.measurement_mode_combo)
        form.addRow("运行用途", self.run_purpose_combo)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.validate_sweep_button = QPushButton("验证 Sweep 配置")
        self.validate_multisine_button = QPushButton("验证 Multisine 配置")
        buttons.addWidget(self.validate_sweep_button)
        buttons.addWidget(self.validate_multisine_button)
        layout.addLayout(buttons)
        self.config_result = QPlainTextEdit()
        self.config_result.setReadOnly(True)
        self.config_result.setPlaceholderText("配置验证结果")
        layout.addWidget(self.config_result)
        self.hard_block_label = QLabel("")
        self.hard_block_label.setWordWrap(True)
        self.hard_block_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.hard_block_label)
        self.real_multisine_run_button = QPushButton("真实 Multisine/P8（未开放）")
        self.real_multisine_run_button.setEnabled(False)
        layout.addWidget(self.real_multisine_run_button)
        return page

    def _build_placeholder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.placeholder_button = QPushButton("查看本步骤说明")
        layout.addWidget(self.placeholder_button)
        return page

    def _build_professional_panel(self) -> QGroupBox:
        panel = QGroupBox("专业详情（只读）")
        layout = QVBoxLayout(panel)
        self.config_path_label = QLabel("配置路径：尚未选择")
        self.git_commit_label = QLabel("Git commit：尚未检查")
        self.arguments_label = QLabel("实际执行参数：尚未执行")
        self.output_path_label = QLabel("输出路径：尚未执行")
        for label in (
            self.config_path_label,
            self.git_commit_label,
            self.arguments_label,
            self.output_path_label,
        ):
            label.setWordWrap(True)
            layout.addWidget(label)
        layout.addWidget(QLabel("stdout"))
        self.stdout_log = QPlainTextEdit()
        self.stdout_log.setReadOnly(True)
        layout.addWidget(self.stdout_log)
        layout.addWidget(QLabel("stderr"))
        self.stderr_log = QPlainTextEdit()
        self.stderr_log.setReadOnly(True)
        layout.addWidget(self.stderr_log)
        layout.addWidget(QLabel("技术错误详情"))
        self.technical_error = QPlainTextEdit()
        self.technical_error.setReadOnly(True)
        layout.addWidget(self.technical_error)
        return panel

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.environment_button.clicked.connect(self._check_environment)
        self.validate_sweep_button.clicked.connect(
            lambda: self._validate_config("rew_sweep")
        )
        self.validate_multisine_button.clicked.connect(
            lambda: self._validate_config("schroeder_multisine")
        )
        self.acceptance_button.clicked.connect(self._run_acceptance)
        self.cancel_button.clicked.connect(self.acceptance_worker.cancel)
        self.placeholder_button.clicked.connect(self._show_placeholder)
        self.data_origin_combo.currentIndexChanged.connect(self._usage_changed)
        self.measurement_mode_combo.currentIndexChanged.connect(self._usage_changed)
        self.run_purpose_combo.currentIndexChanged.connect(self._usage_changed)
        self.acceptance_worker.stdout_received.connect(self._append_stdout)
        self.acceptance_worker.stderr_received.connect(self._append_stderr)
        self.acceptance_worker.finished.connect(self._acceptance_finished)
        self.open_output_button.clicked.connect(self._open_output)
        self.view_report_button.clicked.connect(self._view_report)

    def _mode_changed(self) -> None:
        value = str(self.mode_combo.currentData())
        mode = UiMode(value)
        self.state.set_mode(mode)
        self.professional_panel.setVisible(mode is UiMode.PROFESSIONAL)

    def select_step(self, step_id: str) -> None:
        self._current_step_id = step_id
        step = self.state.step(step_id)
        for candidate, button in self.step_buttons.items():
            button.setChecked(candidate == step_id)
        self.current_step_label.setText(step.title)
        self.current_status_label.setText(f"当前状态：{step.status.value}")
        self.do_label.setText(
            f"用户需要做什么：{step.preparation}\n"
            f"实现轮次：{step.implementation_round}"
        )
        if step_id == "environment":
            self.action_stack.setCurrentWidget(self.environment_page)
        elif step_id == "usage":
            self.action_stack.setCurrentWidget(self.usage_page)
        else:
            self.action_stack.setCurrentWidget(self.placeholder_page)

    def set_usage(
        self,
        *,
        data_origin: str,
        measurement_mode: str,
        run_purpose: str,
    ) -> None:
        for combo, value in (
            (self.data_origin_combo, data_origin),
            (self.measurement_mode_combo, measurement_mode),
            (self.run_purpose_combo, run_purpose),
        ):
            index = combo.findData(value)
            if index < 0:
                raise ValueError(f"unsupported UI selection: {value}")
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self._usage_changed()

    def _usage_changed(self) -> None:
        decision = self.state.select_usage(
            data_origin=str(self.data_origin_combo.currentData()),
            measurement_mode=str(self.measurement_mode_combo.currentData()),
            run_purpose=str(self.run_purpose_combo.currentData()),
        )
        self.hard_block_label.setText("" if decision.allowed else decision.reason)
        self._refresh_step_buttons()

    def _begin_step(self, step_id: str) -> None:
        status = self.state.step(step_id).status
        if status is not StepStatus.READY:
            self.state.transition(step_id, StepStatus.READY)
        self.state.transition(step_id, StepStatus.RUNNING)
        self._refresh_step_buttons()

    def _finish_step(self, step_id: str, status: StepStatus) -> None:
        if self.state.step(step_id).status is not StepStatus.RUNNING:
            self._begin_step(step_id)
        self.state.transition(step_id, status)
        self._refresh_step_buttons()
        if self._current_step_id == step_id:
            self.select_step(step_id)

    def _check_environment(self) -> None:
        try:
            self._begin_step("environment")
            report = self.services.check_environment()
        except Exception as exc:
            user_message, technical = humanize_exception(exc)
            self.technical_error.setPlainText(technical)
            self._append_result(user_message)
            self._finish_step("environment", StepStatus.FAILED)
            return
        self._show_environment_report(report)
        self._finish_step(
            "environment", StepStatus.PASSED if report.passed else StepStatus.FAILED
        )

    def _show_environment_report(self, report: EnvironmentReport) -> None:
        self.git_commit_label.setText(
            f"Git commit：{report.git_commit}; 工作树："
            f"{'clean' if report.git_worktree_clean else 'dirty'}"
        )
        lines = [
            f"{item.label}: {item.status.value} — {item.value}"
            for item in report.checks
        ]
        self._append_result(
            ("环境检查通过。" if report.passed else "环境检查失败。")
            + "\n"
            + "\n".join(lines)
        )
        self.next_step_label.setText(
            "下一步建议：验证对应入口配置，或运行模拟软件验收。"
            if report.passed
            else "下一步建议：修复失败项目后重新检查。"
        )

    def _validate_config(self, expected_mode: str) -> None:
        self._begin_step("usage")
        config_name = (
            "experiment_v2_u4.yaml"
            if expected_mode == "rew_sweep"
            else "experiment_v2_u4_multisine.yaml"
        )
        path = self.project_root / "config" / config_name
        result = self.services.validate_config(path, expected_mode=expected_mode)
        self._show_config_result(result)
        self._finish_step(
            "usage", StepStatus.PASSED if result.success else StepStatus.FAILED
        )

    def _show_config_result(self, result: ConfigValidationResult) -> None:
        self.config_path_label.setText(f"配置路径：{result.config_path}")
        self.technical_error.setPlainText(result.technical_detail)
        versions = ", ".join(
            f"{key}={value}" for key, value in result.schema_versions.items()
        ) or "unavailable"
        text = (
            f"状态: {'成功' if result.success else '失败'}\n"
            f"measurement_mode: {result.measurement_mode}\n"
            f"pipeline_version: {result.pipeline_version}\n"
            f"schema_versions: {versions}\n"
            f"run_purpose: {result.run_purpose}\n"
            f"provisional: {result.provisional}\n"
            f"说明: {result.user_message}"
        )
        self.config_result.setPlainText(text)
        self._append_result(result.user_message)
        self.next_step_label.setText(
            "下一步建议：配置通过后可继续软件验收；实验操作仍等待 DEV-UI2。"
            if result.success
            else "下一步建议：按错误详情修改配置，然后重新验证。"
        )

    def _run_acceptance(self) -> None:
        try:
            self._begin_step("environment")
            invocation = self.acceptance_worker.start()
        except Exception as exc:
            user_message, technical = humanize_exception(exc)
            self._append_result(user_message)
            self.technical_error.setPlainText(technical)
            self._finish_step("environment", StepStatus.FAILED)
            return
        self._active_invocation = invocation
        self.stdout_log.clear()
        self.stderr_log.clear()
        self.technical_error.clear()
        self.arguments_label.setText(
            "实际执行参数：program="
            + invocation.program
            + "; arguments="
            + repr(invocation.arguments)
        )
        self.output_path_label.setText(f"输出路径：{invocation.output_directory}")
        self.acceptance_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.open_output_button.setEnabled(False)
        self.view_report_button.setEnabled(False)
        self._append_result(f"模拟软件验收正在运行；run-id={invocation.run_id}")

    def _append_stdout(self, text: str) -> None:
        self.stdout_log.moveCursor(QTextCursor.End)
        self.stdout_log.insertPlainText(text)

    def _append_stderr(self, text: str) -> None:
        self.stderr_log.moveCursor(QTextCursor.End)
        self.stderr_log.insertPlainText(text)

    def _acceptance_finished(
        self,
        run_id: str,
        result: ProcessResult,
        invocation: AcceptanceInvocation,
    ) -> None:
        self.acceptance_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._active_invocation = invocation
        if result.stdout and result.stdout not in self.stdout_log.toPlainText():
            self._append_stdout(result.stdout)
        if result.stderr and result.stderr not in self.stderr_log.toPlainText():
            self._append_stderr(result.stderr)
        if result.outcome is ProcessOutcome.CANCELLED:
            self._append_result(
                f"模拟软件验收已取消；outcome=cancelled；run-id={run_id}。"
            )
            self._finish_step("environment", StepStatus.WARNING)
            return
        try:
            summary = self.services.load_acceptance_summary(
                invocation.output_directory
            )
        except Exception as exc:
            user_message, technical = humanize_exception(exc)
            self._append_result(user_message)
            self.technical_error.setPlainText(technical)
            self._finish_step("environment", StepStatus.FAILED)
            return
        self._last_acceptance_summary = summary
        self._show_acceptance_summary(
            summary,
            process_failed=result.outcome is ProcessOutcome.FAILED,
            exit_code=result.exit_code,
        )

    def _show_acceptance_summary(
        self,
        summary: AcceptanceSummary,
        *,
        process_failed: bool = False,
        exit_code: int = 0,
    ) -> None:
        stage_text = ", ".join(
            f"{key}={value}" for key, value in sorted(summary.stage_statuses.items())
        )
        self.acceptance_summary.setText(
            f"{stage_text}; V2={summary.v2_requirement_pass_count}/"
            f"{summary.v2_requirement_total}; 总测试={summary.test_status} "
            f"({summary.test_summary}); software_integration_ready="
            f"{str(summary.software_integration_ready).lower()}; "
            "scientifically_eligible=false"
        )
        self.open_output_button.setEnabled(summary.output_directory.is_dir())
        self.view_report_button.setEnabled(summary.report_path.is_file())
        if process_failed:
            status = StepStatus.FAILED
            message = (
                f"模拟软件验收进程返回失败（exit_code={exit_code}）；"
                "已保留并解析可验证的 T0～T3/V2 失败报告。"
            )
        elif summary.software_integration_ready:
            status = StepStatus.PASSED
            message = "模拟软件验收通过。该结论仅表示软件集成就绪，不授予科研资格。"
        elif summary.overall_status == "pass":
            status = StepStatus.WARNING
            message = "验收证据通过，但 readiness 门禁未全部满足；请查看报告。"
        else:
            status = StepStatus.FAILED
            message = "模拟软件验收未通过；请查看 T0～T3 和 V2 检查。"
        self._append_result(message)
        self.next_step_label.setText(
            "下一步建议：查看不可变验收报告；真实 Multisine/P8 仍保持硬阻塞。"
        )
        self._finish_step("environment", status)

    def _show_placeholder(self) -> None:
        details = self.state.unavailable_details(self._current_step_id)
        self._append_result(format_unimplemented_message(details))
        self.next_step_label.setText("下一步建议：完成准备工作，等待对应实现轮次。")

    def _append_result(self, message: str) -> None:
        existing = self.result_label.text()
        if existing == "尚未执行。":
            self.result_label.setText(message)
        else:
            self.result_label.setText(existing + "\n\n" + message)

    def _refresh_step_buttons(self) -> None:
        for index, step in enumerate(self.state.steps, start=1):
            self.step_buttons[step.step_id].setText(
                f"{index:02d}. {step.title}\n状态：{step.status.value}"
            )
        current = self.state.step(self._current_step_id)
        self.current_status_label.setText(f"当前状态：{current.status.value}")

    def _open_output(self) -> None:
        if self._last_acceptance_summary is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._last_acceptance_summary.output_directory))
            )

    def _view_report(self) -> None:
        if self._last_acceptance_summary is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._last_acceptance_summary.report_path))
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.acceptance_worker.is_running:
            choice = QMessageBox.question(
                self,
                "验收仍在运行",
                "关闭窗口会取消当前验收，但保留已经写出的证据。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if choice != QMessageBox.Yes:
                event.ignore()
                return
            self.acceptance_worker.cancel()
        event.accept()

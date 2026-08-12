"""PySide6 guided desktop shell for safe software validation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QSpinBox,
)

from acoustic_encoder.ui.services import (
    AcceptanceSummary,
    ApplicationServices,
    ConfigValidationResult,
    EnvironmentReport,
    humanize_exception,
)
from acoustic_encoder.schemas import MeasurementMode
from acoustic_encoder.ui.dialogs import format_unimplemented_message
from acoustic_encoder.ui.plan_page import ExperimentPlanPage
from acoustic_encoder.ui.dataset_page import DatasetQCPage
from acoustic_encoder.ui.analysis_page import BatchAnalysisPage
from acoustic_encoder.ui.state import StepStatus, UiMode, WizardState
from acoustic_encoder.ui.measurement_workflow import (
    MetadataFormValues,
    MeasurementDraft,
    MeasurementDraftService,
    MeasurementRunEvidence,
    MultisinePreflightResult,
    REAL_MULTISINE_BLOCK_MESSAGE,
    REWPreflightResult,
    SavedMeasurementDraft,
    UsageRoute,
)
from acoustic_encoder.ui.workers import (
    AcceptanceInvocation,
    AcceptanceWorker,
    ProcessOutcome,
    ProcessResult,
    SingleMeasurementInvocation,
    SingleMeasurementStatus,
    SingleMeasurementWorker,
)
from acoustic_encoder.ui.runtime import RuntimeContext
from acoustic_encoder.ui.runtime import (
    WorkspaceAccessError,
    WorkspaceSelectionStore,
    default_workspace_settings_path,
)
from acoustic_encoder.ui.final_delivery_page import FinalDeliveryPage


class MainWindow(QMainWindow):
    """Twelve-step DEV-UI1--UI3 shell over authoritative backend services."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        workspace_root: str | Path | None = None,
        runtime_context: RuntimeContext | None = None,
        services: ApplicationServices | None = None,
        acceptance_worker: AcceptanceWorker | None = None,
        measurement_service: MeasurementDraftService | None = None,
        single_worker: SingleMeasurementWorker | None = None,
    ) -> None:
        super().__init__()
        self.project_root = Path(project_root).resolve()
        self.runtime = runtime_context or RuntimeContext.for_source(
            self.project_root, workspace_root=workspace_root
        )
        self.workspace_root = self.runtime.workspace_root
        self.state = WizardState()
        self.services = services or ApplicationServices(
            self.project_root, workspace_root=self.workspace_root
        )
        self.acceptance_worker = acceptance_worker or AcceptanceWorker(
            self.project_root, output_root=self.runtime.output_root,
            runtime_context=self.runtime, parent=self
        )
        build_commit = None
        build_manifest = self.project_root / "build_manifest.json"
        if build_manifest.is_file():
            import json

            build_commit = str(json.loads(build_manifest.read_text(encoding="utf-8-sig"))["git_commit"])
        self.measurement_service = measurement_service or MeasurementDraftService(
            self.project_root,
            workspace_root=self.workspace_root,
            source_commit=build_commit,
        )
        self.single_worker = single_worker or SingleMeasurementWorker(
            self.project_root, output_root=self.runtime.output_root,
            runtime_context=self.runtime, parent=self
        )
        self.plan_page = ExperimentPlanPage(
            self.project_root, self, workspace_root=self.workspace_root
        )
        self.dataset_page = DatasetQCPage(
            self.project_root,
            self,
            workspace_root=self.workspace_root,
            runtime_context=self.runtime,
        )
        self.analysis_page = BatchAnalysisPage(
            self.project_root,
            self,
            workspace_root=self.workspace_root,
            runtime_context=self.runtime,
        )
        self.final_delivery_page = FinalDeliveryPage(self.runtime, self)
        self.open_p9_button = QPushButton("打开正式 P9-A～P9-C 向导")
        self.open_p9_button.setObjectName("openP9WorkflowButton")
        self.analysis_page.layout().addWidget(self.open_p9_button)
        self.open_p9_button.clicked.connect(self._show_p9_workflow)
        self._current_step_id = "environment"
        self._active_invocation: AcceptanceInvocation | None = None
        self._last_acceptance_summary: AcceptanceSummary | None = None
        self._current_route = UsageRoute.SIMULATED_PRACTICE
        self._current_preflight: REWPreflightResult | MultisinePreflightResult | None = None
        self._current_draft: MeasurementDraft | None = None
        self._current_saved: SavedMeasurementDraft | None = None
        self._active_single_invocation: SingleMeasurementInvocation | None = None
        self._last_single_evidence: MeasurementRunEvidence | None = None
        self._pending_workspace: Path | None = None
        self.setWindowTitle("双入口声学分析向导 — 软件验证")
        self.resize(1260, 820)
        self.setMinimumSize(1000, 680)
        self._build_ui()
        self._connect_signals()
        self.set_usage_route(UsageRoute.SIMULATED_PRACTICE, force=True)
        self.select_step("environment")
        self._refresh_step_buttons()

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        header = QHBoxLayout()
        title = QLabel("双入口声学分析向导")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        header.addWidget(title)
        self.workspace_label = QLabel(f"工作区：{self.workspace_root}")
        self.workspace_label.setToolTip(str(self.workspace_root))
        self.workspace_label.setMaximumWidth(420)
        header.addWidget(self.workspace_label)
        self.change_workspace_button = QPushButton("更换工作区")
        self.change_workspace_button.setObjectName("changeWorkspaceButton")
        header.addWidget(self.change_workspace_button)
        self.pending_workspace_label = QLabel()
        self.pending_workspace_label.setObjectName("pendingWorkspaceLabel")
        self.pending_workspace_label.setVisible(False)
        header.addWidget(self.pending_workspace_label)
        self.restart_workspace_button = QPushButton("立即重启")
        self.restart_workspace_button.setObjectName("restartWorkspaceButton")
        self.restart_workspace_button.setVisible(False)
        header.addWidget(self.restart_workspace_button)
        header.addStretch(1)
        header.addWidget(QLabel("界面模式："))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("简易模式", UiMode.SIMPLE.value)
        self.mode_combo.addItem("专业模式", UiMode.PROFESSIONAL.value)
        header.addWidget(self.mode_combo)
        self.about_button = QPushButton("关于")
        self.about_button.setObjectName("aboutButton")
        header.addWidget(self.about_button)
        root.addLayout(header)

        self.origin_banner = QLabel()
        self.origin_banner.setObjectName("originBanner")
        self.origin_banner.setWordWrap(True)
        self.origin_banner.setStyleSheet("font-weight: 600; padding: 6px;")
        root.addWidget(self.origin_banner)

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
        self.single_measurement_page = self._build_single_measurement_page()
        self.placeholder_page = self._build_placeholder_page()
        self.action_stack.addWidget(self.environment_page)
        self.action_stack.addWidget(self.usage_page)
        self.action_stack.addWidget(self.single_measurement_page)
        self.action_stack.addWidget(self.plan_page)
        self.action_stack.addWidget(self.dataset_page)
        self.action_stack.addWidget(self.analysis_page)
        self.action_stack.addWidget(self.final_delivery_page)
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
        navigation = QHBoxLayout()
        self.previous_button = QPushButton("上一步")
        self.next_button = QPushButton("下一步")
        self.previous_button.setObjectName("previousStepButton")
        self.next_button.setObjectName("nextStepButton")
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.next_button)
        content_layout.addLayout(navigation)
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
        self.usage_route_combo = QComboBox()
        self.usage_route_combo.addItem(
            "模拟练习", UsageRoute.SIMULATED_PRACTICE.value
        )
        self.usage_route_combo.addItem(
            "官方 REW 参考", UsageRoute.OFFICIAL_REFERENCE.value
        )
        self.usage_route_combo.addItem(
            "真实实验诊断", UsageRoute.REAL_DIAGNOSTIC.value
        )
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
        self.data_origin_combo.setEnabled(False)
        self.run_purpose_combo.setEnabled(False)
        form.addRow("使用路径", self.usage_route_combo)
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

    def _build_single_measurement_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        files = QGroupBox("只读输入")
        file_form = QFormLayout(files)
        self.source_path_edit = QLineEdit()
        self.source_path_edit.setReadOnly(True)
        self.manifest_path_edit = QLineEdit()
        self.manifest_path_edit.setReadOnly(True)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_path_edit)
        self.choose_source_button = QPushButton("选择 REW TXT / WAV")
        source_row.addWidget(self.choose_source_button)
        manifest_row = QHBoxLayout()
        manifest_row.addWidget(self.manifest_path_edit)
        self.choose_manifest_button = QPushButton("选择 stimulus_manifest.json")
        manifest_row.addWidget(self.choose_manifest_button)
        file_form.addRow("测量文件", source_row)
        file_form.addRow("刺激 manifest", manifest_row)
        self.preflight_single_button = QPushButton("只读预检并生成 metadata 草稿")
        file_form.addRow(self.preflight_single_button)
        layout.addWidget(files)

        metadata_box = QGroupBox("Metadata 助手（不直接编辑 JSON）")
        metadata_form = QFormLayout(metadata_box)
        labels = {
            "device_version": "设备版本",
            "configuration": "配置 ID",
            "angle_deg": "角度（度）",
            "session_id": "Session ID",
            "repeat_type": "重复类型",
            "repeat_id": "Repeat ID",
            "reposition_round_id": "重定位轮次",
            "assembly_id": "装配 ID",
            "acquisition_block_id": "采集块 ID",
            "experiment_step": "实验步骤",
            "date_time": "时间（含时区）",
            "provenance_uri": "Provenance 记录/引用",
        }
        self.metadata_fields: dict[str, QLineEdit] = {}
        for name, label in labels.items():
            editor = QLineEdit()
            editor.setObjectName(f"metadata_{name}")
            self.metadata_fields[name] = editor
            metadata_form.addRow(label, editor)
        self.audio_channel_spin = QSpinBox()
        self.audio_channel_spin.setMinimum(0)
        self.audio_channel_spin.setMaximum(255)
        metadata_form.addRow("音频通道（从 0 开始）", self.audio_channel_spin)
        self.sample_id_edit = QLineEdit()
        self.sample_id_edit.setReadOnly(True)
        self.run_id_edit = QLineEdit()
        self.run_id_edit.setReadOnly(True)
        sample_row = QHBoxLayout()
        sample_row.addWidget(self.sample_id_edit)
        self.copy_sample_id_button = QPushButton("复制")
        sample_row.addWidget(self.copy_sample_id_button)
        run_row = QHBoxLayout()
        run_row.addWidget(self.run_id_edit)
        self.copy_run_id_button = QPushButton("复制")
        run_row.addWidget(self.copy_run_id_button)
        metadata_form.addRow("自动 sample_id", sample_row)
        metadata_form.addRow("自动 run_id", run_row)
        layout.addWidget(metadata_box)

        self.single_hard_block_label = QLabel()
        self.single_hard_block_label.setWordWrap(True)
        self.single_hard_block_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.single_hard_block_label)
        actions = QHBoxLayout()
        self.save_metadata_button = QPushButton("保存登记与 metadata")
        self.save_metadata_button.setEnabled(False)
        self.run_single_button = QPushButton("运行单次软件验证")
        self.run_single_button.setEnabled(False)
        self.cancel_single_button = QPushButton("取消运行")
        self.cancel_single_button.setEnabled(False)
        self.new_revision_button = QPushButton("建立 metadata 修订")
        self.new_revision_button.setEnabled(False)
        actions.addWidget(self.save_metadata_button)
        actions.addWidget(self.run_single_button)
        actions.addWidget(self.cancel_single_button)
        actions.addWidget(self.new_revision_button)
        layout.addLayout(actions)
        links = QHBoxLayout()
        self.open_single_output_button = QPushButton("打开单次输出")
        self.view_single_report_button = QPushButton("查看单次报告")
        self.open_single_output_button.setEnabled(False)
        self.view_single_report_button.setEnabled(False)
        links.addWidget(self.open_single_output_button)
        links.addWidget(self.view_single_report_button)
        layout.addLayout(links)
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
        self.change_workspace_button.clicked.connect(self._choose_workspace)
        self.restart_workspace_button.clicked.connect(self._restart_with_pending_workspace)
        self.previous_button.clicked.connect(lambda: self._navigate_relative(-1))
        self.next_button.clicked.connect(lambda: self._navigate_relative(1))
        self.about_button.clicked.connect(self._show_about)
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
        self.usage_route_combo.currentIndexChanged.connect(self._route_changed)
        self.data_origin_combo.currentIndexChanged.connect(self._usage_changed)
        self.measurement_mode_combo.currentIndexChanged.connect(self._usage_changed)
        self.run_purpose_combo.currentIndexChanged.connect(self._usage_changed)
        self.acceptance_worker.stdout_received.connect(self._append_stdout)
        self.acceptance_worker.stderr_received.connect(self._append_stderr)
        self.acceptance_worker.finished.connect(self._acceptance_finished)
        self.open_output_button.clicked.connect(self._open_output)
        self.view_report_button.clicked.connect(self._view_report)
        self.choose_source_button.clicked.connect(self._choose_source)
        self.choose_manifest_button.clicked.connect(self._choose_manifest)
        self.preflight_single_button.clicked.connect(self._preflight_single)
        self.save_metadata_button.clicked.connect(self._save_single_metadata)
        self.run_single_button.clicked.connect(self._run_single_measurement)
        self.cancel_single_button.clicked.connect(self.single_worker.cancel)
        self.new_revision_button.clicked.connect(self._save_single_metadata)
        self.copy_sample_id_button.clicked.connect(
            lambda: self._copy_text(self.sample_id_edit.text())
        )
        self.copy_run_id_button.clicked.connect(
            lambda: self._copy_text(self.run_id_edit.text())
        )
        self.single_worker.stdout_received.connect(self._append_stdout)
        self.single_worker.stderr_received.connect(self._append_stderr)
        self.single_worker.finished.connect(self._single_measurement_finished)
        self.open_single_output_button.clicked.connect(self._open_single_output)
        self.view_single_report_button.clicked.connect(self._view_single_report)
        self.plan_page.plan_saved.connect(self._plan_saved)
        self.plan_page.message.connect(self._append_result)
        self.dataset_page.message.connect(self._append_result)
        self.dataset_page.p2b_ready_changed.connect(
            self.analysis_page.set_p2b_ready
        )
        self.dataset_page.workflow_status_changed.connect(
            self._dataset_workflow_status_changed
        )
        self.analysis_page.message.connect(self._append_result)
        self.analysis_page.stage_status_changed.connect(
            self._analysis_stage_status_changed
        )
        self.final_delivery_page.message.connect(self._append_result)
        self.final_delivery_page.stage_status_changed.connect(
            self._final_delivery_stage_status_changed
        )
        for field in self.metadata_fields.values():
            field.textChanged.connect(self._metadata_edited)
        self.audio_channel_spin.valueChanged.connect(self._metadata_edited)

    def _mode_changed(self) -> None:
        value = str(self.mode_combo.currentData())
        mode = UiMode(value)
        self.state.set_mode(mode)
        self.professional_panel.setVisible(mode is UiMode.PROFESSIONAL)

    def _has_running_tasks(self) -> bool:
        return bool(
            self.acceptance_worker.is_running
            or self.single_worker.is_running
            or self.dataset_page.worker.is_running
            or self.analysis_page.worker.is_running
            or self.final_delivery_page.is_running
        )

    def _choose_workspace(self) -> None:
        if self._has_running_tasks():
            QMessageBox.warning(
                self,
                "暂时不能更换工作区",
                "当前有任务正在运行。请等待任务结束或取消任务后再更换工作区，避免输出分散到不同目录。",
            )
            return
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择工作区（下次启动生效）",
            str(self.workspace_root),
        )
        if not selected:
            return
        try:
            store = WorkspaceSelectionStore(
                self.runtime.settings_path or default_workspace_settings_path()
            )
            store.save(selected)
        except WorkspaceAccessError as exc:
            QMessageBox.warning(self, "工作区不可用", str(exc))
            return
        self._pending_workspace = Path(selected).resolve()
        self.pending_workspace_label.setText("已保存新工作区（下次启动生效）")
        self.pending_workspace_label.setToolTip(str(self._pending_workspace))
        self.pending_workspace_label.setVisible(True)
        self.restart_workspace_button.setVisible(True)
        self.restart_workspace_button.setEnabled(True)
        QMessageBox.information(
            self,
            "工作区已保存",
            f"新工作区：{self._pending_workspace}\n\n"
            "当前窗口和正在显示的后端仍使用原工作区。新路径将在下次启动生效；"
            "可点击“立即重启”。旧工作区中的数据不会被移动、复制或删除。",
        )

    def _restart_with_pending_workspace(self) -> None:
        if self._pending_workspace is None:
            return
        if self._has_running_tasks():
            QMessageBox.warning(
                self,
                "暂时不能重启",
                "当前有任务正在运行。请等待任务结束或取消任务后再重启。",
            )
            return
        program, arguments = self.runtime.restart_process(self._pending_workspace)
        if not QProcess.startDetached(program, list(arguments), str(self._pending_workspace)):
            QMessageBox.warning(
                self,
                "无法立即重启",
                "工作区选择已经保存，将在下次手动启动时生效。请关闭程序后重新打开。",
            )
            return
        self.close()

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
        elif step_id == "single_measurement":
            self.action_stack.setCurrentWidget(self.single_measurement_page)
        elif step_id == "plan":
            self.action_stack.setCurrentWidget(self.plan_page)
        elif step_id == "dataset":
            self.action_stack.setCurrentWidget(self.dataset_page)
        elif step_id in {"comparison", "modeling"}:
            self.action_stack.setCurrentWidget(self.analysis_page)
        elif step_id in {"freeze", "final_test", "reports"}:
            self.final_delivery_page.set_view(step_id)
            self.action_stack.setCurrentWidget(self.final_delivery_page)
        else:
            self.action_stack.setCurrentWidget(self.placeholder_page)

        ids = [item.step_id for item in self.state.steps]
        position = ids.index(step_id)
        self.previous_button.setEnabled(position > 0)
        self.next_button.setEnabled(position < len(ids) - 1)

    def _navigate_relative(self, offset: int) -> None:
        ids = [item.step_id for item in self.state.steps]
        target = max(0, min(len(ids) - 1, ids.index(self._current_step_id) + offset))
        self.select_step(ids[target])

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "关于 Sweep / Multisine UI",
            "本地双入口声学分析向导。所有 provenance、QC、科研资格与 final-test 门禁由正式后端保持。",
        )

    def _show_p9_workflow(self) -> None:
        self.final_delivery_page.set_view("modeling")
        self.action_stack.setCurrentWidget(self.final_delivery_page)

    def _plan_saved(self, saved: object) -> None:
        self._begin_step("plan")
        ready = bool(saved.checklist.ready_for_acquisition)
        self._finish_step("plan", StepStatus.PASSED if ready else StepStatus.WARNING)
        self.dataset_page.load_plan_revision(saved.directory)
        self.analysis_page.set_plan_modes(
            tuple(
                mode.value
                for block in saved.plan.condition_blocks
                for mode in block.measurement_modes
            )
        )
        self._append_result(
            f"计划 revision 已保存：{saved.directory}；"
            f"ready_for_acquisition={str(ready).lower()}；科研资格=false。"
        )
        self.next_step_label.setText(
            "下一步建议：按计划完成外部采集，然后显式登记 UI2 sessions。"
        )

    def _dataset_workflow_status_changed(self, status: str) -> None:
        mapping = {
            "plan_draft": StepStatus.WARNING,
            "plan_ready": StepStatus.READY,
            "acquisition_waiting": StepStatus.WAITING_EXTERNAL,
            "samples_partial": StepStatus.WARNING,
            "samples_complete": StepStatus.READY,
            "dataset_qc_running": StepStatus.RUNNING,
            "dataset_qc_warning": StepStatus.WARNING,
            "dataset_qc_passed": StepStatus.PASSED,
            "analysis_ready": StepStatus.PASSED,
            "blocked": StepStatus.BLOCKED,
        }
        target = mapping.get(status)
        if target is not None:
            self.state.step("dataset").status = target
            self._refresh_step_buttons()

    def _analysis_stage_status_changed(self, stage: str, status: str) -> None:
        step_id = "comparison" if stage == "P4" else "modeling"
        mapping = {
            "running": StepStatus.RUNNING,
            "succeeded": StepStatus.PASSED,
            "cancelled": StepStatus.WARNING,
            "failed": StepStatus.FAILED,
        }
        target = mapping.get(status)
        if target is not None:
            self.state.step(step_id).status = target
            self._refresh_step_buttons()

    def _final_delivery_stage_status_changed(self, stage: str, status: str) -> None:
        step_id = {
            "P9-A": "modeling", "P9-B": "modeling", "P9-C": "modeling",
            "P9-D": "freeze", "offline-readout": "reports",
        }.get(stage, "reports")
        target = {
            "running": StepStatus.RUNNING,
            "succeeded": StepStatus.PASSED,
            "cancelled": StepStatus.WARNING,
            "failed": StepStatus.FAILED,
        }.get(status)
        if target is not None:
            self.state.step(step_id).status = target
            self._refresh_step_buttons()

    def set_usage_route(
        self, route: UsageRoute | str, *, force: bool = False
    ) -> bool:
        selected = UsageRoute(route)
        if selected is not self._current_route and self._metadata_is_dirty() and not force:
            answer = QMessageBox.question(
                self,
                "切换使用路径",
                "切换路径会清空不兼容的 metadata 草稿。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                index = self.usage_route_combo.findData(self._current_route.value)
                self.usage_route_combo.blockSignals(True)
                self.usage_route_combo.setCurrentIndex(index)
                self.usage_route_combo.blockSignals(False)
                return False
        if selected is not self._current_route or force:
            self._clear_measurement_draft()
        self._current_route = selected
        index = self.usage_route_combo.findData(selected.value)
        self.usage_route_combo.blockSignals(True)
        self.usage_route_combo.setCurrentIndex(index)
        self.usage_route_combo.blockSignals(False)
        policy = self.measurement_service.route_policy(selected)
        self._set_combo_data(self.data_origin_combo, policy.data_origin.value)
        self._set_combo_data(self.run_purpose_combo, policy.run_purpose)
        if selected is UsageRoute.SIMULATED_PRACTICE:
            self._set_combo_data(
                self.measurement_mode_combo, "schroeder_multisine"
            )
            self.measurement_mode_combo.setEnabled(False)
        elif selected is UsageRoute.OFFICIAL_REFERENCE:
            self._set_combo_data(self.measurement_mode_combo, "rew_sweep")
            self.measurement_mode_combo.setEnabled(False)
        else:
            self.measurement_mode_combo.setEnabled(True)
        identity_names = {
            "device_version",
            "configuration",
            "angle_deg",
            "session_id",
            "repeat_type",
            "repeat_id",
            "reposition_round_id",
            "assembly_id",
            "acquisition_block_id",
            "experiment_step",
            "date_time",
        }
        for name in identity_names:
            self.metadata_fields[name].setEnabled(
                selected is not UsageRoute.OFFICIAL_REFERENCE
            )
        self.origin_banner.setText(
            f"{policy.label}｜data_origin={policy.data_origin.value}｜"
            f"dataset_role={policy.dataset_role.value}｜"
            f"run_purpose={policy.run_purpose}｜科研资格=false"
        )
        self._usage_changed()
        return True

    def _route_changed(self) -> None:
        self.set_usage_route(str(self.usage_route_combo.currentData()))

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index < 0:
            raise ValueError(f"unsupported UI selection: {value}")
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _metadata_is_dirty(self) -> bool:
        return any(field.text().strip() for field in self.metadata_fields.values())

    def _metadata_edited(self) -> None:
        if self._current_draft is None and self._current_saved is None:
            return
        self._current_draft = None
        self._current_saved = None
        self.sample_id_edit.clear()
        self.run_id_edit.clear()
        self.save_metadata_button.setEnabled(False)
        self.run_single_button.setEnabled(False)
        self.new_revision_button.setEnabled(False)
        self._append_result(
            "metadata 已变更；请重新执行预检以生成稳定 ID 和 schema 草稿。"
        )

    def _clear_measurement_draft(self) -> None:
        if hasattr(self, "metadata_fields"):
            for field in self.metadata_fields.values():
                field.clear()
        if hasattr(self, "source_path_edit"):
            self.source_path_edit.clear()
            self.manifest_path_edit.clear()
            self.sample_id_edit.clear()
            self.run_id_edit.clear()
            self.save_metadata_button.setEnabled(False)
            self.run_single_button.setEnabled(False)
            self.new_revision_button.setEnabled(False)
            self.new_revision_button.setEnabled(False)
        self._current_preflight = None
        self._current_draft = None
        self._current_saved = None

    def set_usage(
        self,
        *,
        data_origin: str,
        measurement_mode: str,
        run_purpose: str,
    ) -> None:
        route = {
            "simulated": UsageRoute.SIMULATED_PRACTICE,
            "external_reference": UsageRoute.OFFICIAL_REFERENCE,
            "real_experiment": UsageRoute.REAL_DIAGNOSTIC,
        }.get(data_origin)
        if route is None:
            raise ValueError(f"unsupported UI selection: {data_origin}")
        self.set_usage_route(route, force=True)
        for combo, value in (
            (self.data_origin_combo, data_origin),
            (self.measurement_mode_combo, measurement_mode),
        ):
            index = combo.findData(value)
            if index < 0:
                raise ValueError(f"unsupported UI selection: {value}")
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
        del run_purpose  # UI route policy fixes software_validation in DEV-UI2.
        self._usage_changed()

    def _usage_changed(self) -> None:
        decision = self.state.select_usage(
            data_origin=str(self.data_origin_combo.currentData()),
            measurement_mode=str(self.measurement_mode_combo.currentData()),
            run_purpose=str(self.run_purpose_combo.currentData()),
        )
        self.hard_block_label.setText("" if decision.allowed else decision.reason)
        real_multisine = (
            self._current_route is UsageRoute.REAL_DIAGNOSTIC
            and self.measurement_mode_combo.currentData()
            == "schroeder_multisine"
        )
        self.single_hard_block_label.setText(
            REAL_MULTISINE_BLOCK_MESSAGE if real_multisine else ""
        )
        is_multisine = (
            self.measurement_mode_combo.currentData() == "schroeder_multisine"
        )
        self.choose_manifest_button.setEnabled(is_multisine)
        self.audio_channel_spin.setEnabled(is_multisine)
        self.run_single_button.setEnabled(
            self._current_saved is not None and not real_multisine
        )
        self._refresh_step_buttons()

    def _choose_source(self) -> None:
        mode = str(self.measurement_mode_combo.currentData())
        file_filter = (
            "REW frequency response (*.txt)"
            if mode == "rew_sweep"
            else "WAV recording (*.wav)"
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "选择测量文件", str(self.project_root), file_filter
        )
        if path:
            self.source_path_edit.setText(str(Path(path).resolve()))
            self._current_preflight = None
            self._current_draft = None
            self._current_saved = None
            self.save_metadata_button.setEnabled(False)
            self.run_single_button.setEnabled(False)
            self.new_revision_button.setEnabled(False)

    def _choose_manifest(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 stimulus_manifest.json",
            str(self.project_root),
            "Stimulus manifest (stimulus_manifest.json)",
        )
        if path:
            self.manifest_path_edit.setText(str(Path(path).resolve()))
            self._current_preflight = None
            self._current_draft = None
            self._current_saved = None
            self.save_metadata_button.setEnabled(False)
            self.run_single_button.setEnabled(False)

    def _metadata_form_values(self) -> MetadataFormValues:
        values = {name: field.text().strip() or None for name, field in self.metadata_fields.items()}
        return MetadataFormValues(
            **values,
            audio_channel=self.audio_channel_spin.value(),
        )

    def _preflight_single(self) -> None:
        source = Path(self.source_path_edit.text())
        try:
            mode = MeasurementMode(str(self.measurement_mode_combo.currentData()))
            if mode is MeasurementMode.REW_SWEEP:
                preflight = self.measurement_service.preflight_rew(source)
            else:
                manifest_text = self.manifest_path_edit.text().strip()
                if not manifest_text:
                    raise ValueError("Multisine 必须选择 stimulus_manifest.json")
                preflight = self.measurement_service.preflight_multisine(
                    source,
                    Path(manifest_text),
                    audio_channel=self.audio_channel_spin.value(),
                )
            draft = self.measurement_service.build_draft(
                route=self._current_route,
                measurement_mode=mode,
                preflight=preflight,
                form=self._metadata_form_values(),
            )
        except Exception as exc:
            user_message, technical = humanize_exception(exc)
            self._append_result(f"预检失败：{user_message}")
            self.technical_error.setPlainText(technical)
            self.save_metadata_button.setEnabled(False)
            return
        self._current_preflight = preflight
        self._current_draft = draft
        self.sample_id_edit.setText(draft.sample_id)
        self.run_id_edit.setText(draft.run_id)
        self.save_metadata_button.setEnabled(True)
        self.run_single_button.setEnabled(False)
        if isinstance(preflight, REWPreflightResult):
            summary = (
                f"REW 预检通过：{preflight.data_point_count} 点，"
                f"phase={'有' if preflight.has_phase else '无'}，"
                f"SHA-256={preflight.source_sha256}"
            )
        else:
            summary = (
                f"Multisine 预检通过：{preflight.sample_rate_hz} Hz，"
                f"{preflight.channel_count} 通道，stimulus_id={preflight.stimulus_id}，"
                f"recording SHA-256={preflight.recording_sha256}"
            )
        self._append_result(summary)
        self.next_step_label.setText("下一步建议：核对自动字段，然后保存版本化登记。")

    def _save_single_metadata(self) -> None:
        draft = self._current_draft
        if draft is None:
            self._append_result("请先完成只读预检。")
            return
        try:
            saved = self.measurement_service.save_draft(draft)
        except FileExistsError:
            reason, accepted = QInputDialog.getText(
                self,
                "保存 metadata 修订",
                "该 sample 已登记。请输入本次修订原因：",
            )
            if not accepted or not reason.strip():
                self._append_result("未保存：修订必须给出明确原因。")
                return
            saved = self.measurement_service.save_draft(
                draft, revision_reason=reason
            )
        except Exception as exc:
            user_message, technical = humanize_exception(exc)
            self._append_result(f"登记失败：{user_message}")
            self.technical_error.setPlainText(technical)
            return
        self._current_saved = saved
        self.run_id_edit.setText(saved.draft.run_id)
        blocked = not self.measurement_service.analysis_decision(draft).allowed
        self.run_single_button.setEnabled(not blocked)
        self.new_revision_button.setEnabled(True)
        self.view_single_report_button.setEnabled(True)
        self._append_result(
            f"登记已保存：revision={saved.revision}；{saved.session_directory}"
        )
        if blocked:
            self.single_hard_block_label.setText(REAL_MULTISINE_BLOCK_MESSAGE)
            self._append_result(REAL_MULTISINE_BLOCK_MESSAGE)
            self.next_step_label.setText("下一步建议：保留原始文件和 hash，等待 DEV-D。")
        else:
            self.next_step_label.setText("下一步建议：运行单次软件验证。")

    def _run_single_measurement(self) -> None:
        saved = self._current_saved
        if saved is None:
            self._append_result("请先保存 metadata 登记。")
            return
        summary = (
            f"即将运行单次软件验证：\n"
            f"sample_id={saved.draft.sample_id}\n"
            f"run_id={saved.draft.run_id}\n"
            f"data_origin={saved.metadata.data_origin.value}\n"
            f"measurement_mode={saved.metadata.measurement_mode.value}\n"
            f"scientifically_eligible=false\n"
            f"input={saved.metadata.source_path}\n\n"
            "是否继续？"
        )
        if (
            QMessageBox.question(
                self,
                "确认单次软件验证",
                summary,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            self._append_result("用户取消了启动；未创建运行成功标记。")
            return
        try:
            self._begin_step("single_measurement")
            invocation = self.single_worker.start(saved)
        except Exception as exc:
            user_message, technical = humanize_exception(exc)
            self._append_result(f"无法启动：{user_message}")
            self.technical_error.setPlainText(technical)
            target = (
                StepStatus.BLOCKED
                if REAL_MULTISINE_BLOCK_MESSAGE in str(exc)
                else StepStatus.FAILED
            )
            self._finish_step("single_measurement", target)
            return
        self._active_single_invocation = invocation
        self.stdout_log.clear()
        self.stderr_log.clear()
        self.arguments_label.setText(
            f"实际执行参数：program={invocation.program}; arguments={invocation.arguments!r}"
        )
        self.output_path_label.setText(f"输出路径：{invocation.output_directory}")
        self.run_single_button.setEnabled(False)
        self.cancel_single_button.setEnabled(True)
        self._append_result(f"单次软件验证正在运行：run-id={invocation.run_id}")

    def _single_measurement_finished(
        self,
        run_id: str,
        status: SingleMeasurementStatus,
        result: ProcessResult,
        invocation: SingleMeasurementInvocation,
    ) -> None:
        del run_id
        self.cancel_single_button.setEnabled(False)
        self.run_single_button.setEnabled(True)
        saved = self._current_saved
        if saved is None:
            self._append_result("单次处理结束，但 UI 登记上下文已丢失。")
            self._finish_step("single_measurement", StepStatus.FAILED)
            return
        try:
            evidence = self.measurement_service.record_run_result(
                saved,
                output_directory=invocation.output_directory,
                status=status.value,
                program=result.program,
                arguments=result.arguments,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        except Exception as exc:
            user_message, technical = humanize_exception(exc)
            self._append_result(f"结果证据记录失败：{user_message}")
            self.technical_error.setPlainText(technical)
            self._finish_step("single_measurement", StepStatus.FAILED)
            return
        self._last_single_evidence = evidence
        self.open_single_output_button.setEnabled(evidence.output_directory.is_dir())
        self.view_single_report_button.setEnabled(True)
        mapped = {
            SingleMeasurementStatus.COMPLETED: StepStatus.PASSED,
            SingleMeasurementStatus.WARNING: StepStatus.WARNING,
            SingleMeasurementStatus.MANUAL_REVIEW: StepStatus.MANUAL_REVIEW,
            SingleMeasurementStatus.BLOCKED_RESEARCH_GATE: StepStatus.BLOCKED,
            SingleMeasurementStatus.FAILED: StepStatus.FAILED,
            SingleMeasurementStatus.CANCELLED: StepStatus.WARNING,
        }[status]
        self._append_result(
            f"单次处理完成：status={status.value}，QC={evidence.qc_status}，"
            f"scientifically_eligible=false"
        )
        self.next_step_label.setText("下一步建议：查看单次报告、QC 和输出 hash。")
        self._finish_step("single_measurement", mapped)

    @staticmethod
    def _copy_text(value: str) -> None:
        QApplication.clipboard().setText(value)

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

    def _open_single_output(self) -> None:
        if self._last_single_evidence is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self._last_single_evidence.output_directory))
            )

    def _view_single_report(self) -> None:
        path: Path | None = None
        if self._last_single_evidence is not None:
            path = self._last_single_evidence.run_report_html
        elif self._current_saved is not None:
            path = self._current_saved.step_report_html
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self, event: QCloseEvent) -> None:
        running = self._has_running_tasks()
        if running:
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
            self.single_worker.cancel()
            self.dataset_page.worker.cancel()
            self.analysis_page.worker.cancel()
            self.final_delivery_page.worker.cancel()
        event.accept()

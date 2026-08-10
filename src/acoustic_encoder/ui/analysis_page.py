"""DEV-UI3 capability audit and formal P4--P6 launcher page."""

from __future__ import annotations

from pathlib import Path
import uuid

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from acoustic_encoder.ui.batch_workflow import BatchStage, BatchWorkflowService, PreparedBatchInvocation
from acoustic_encoder.ui.services import humanize_exception
from acoustic_encoder.ui.workers import BatchStageWorker, ProcessOutcome, ProcessResult


class BatchAnalysisPage(QWidget):
    message = Signal(str)
    stage_status_changed = Signal(str, str)

    def __init__(self, project_root: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()
        self.service = BatchWorkflowService(self.project_root)
        self.worker = BatchStageWorker(self)
        self.p2b_ready = False
        self.p2b_directory: Path | None = None
        self.plan_modes: frozenset[str] = frozenset()
        self.active_invocation: PreparedBatchInvocation | None = None
        self.last_completed_invocation: PreparedBatchInvocation | None = None
        self.setObjectName("batchAnalysisPage")
        self._build()
        self.worker.stdout_received.connect(self.message)
        self.worker.stderr_received.connect(self.message)
        self.worker.finished.connect(self._finished)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self.block_banner = QLabel(
            "final-test：sealed，不读取。真实 Multisine/P8 及依赖其新 FeatureSet 的阶段：blocked。"
        )
        self.block_banner.setWordWrap(True)
        layout.addWidget(self.block_banner)
        capabilities = self.service.capabilities()
        self.capability_table = QTableWidget(len(capabilities), 8)
        self.capability_table.setObjectName("backendCapabilityTable")
        self.capability_table.setHorizontalHeaderLabels(
            ("stage", "formal entry", "inputs", "scope", "P2-B", "modes", "output", "UI3 availability")
        )
        for row, item in enumerate(capabilities):
            availability = (
                "available with prerequisites"
                if item.formally_available
                else f"unavailable: {item.unavailable_reason}"
            )
            values = (
                item.stage.value,
                item.entry_point or "unavailable",
                ", ".join(item.required_inputs),
                item.required_scope,
                item.prerequisite_qc,
                ", ".join(item.supported_modes),
                item.output_bundle,
                availability,
            )
            for column, value in enumerate(values):
                self.capability_table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(self.capability_table)
        form = QFormLayout()
        self.stage_combo = QComboBox()
        for stage in (BatchStage.P4, BatchStage.P5_A, BatchStage.P5_B, BatchStage.P6_A, BatchStage.P6_B):
            self.stage_combo.addItem(stage.value, stage.value)
        self.path_fields: dict[str, QLineEdit] = {}
        form.addRow("阶段", self.stage_combo)
        for name, label, default in (
            ("config", "配置", self.project_root / "config/default.yaml"),
            ("scope", "显式 scope", ""),
            ("inputs", "显式 input manifest", ""),
            ("comparison", "P4-B bundle（P5-B）", ""),
        ):
            field = QLineEdit(str(default))
            field.setObjectName(f"batch_{name}_path")
            self.path_fields[name] = field
            row = QHBoxLayout()
            row.addWidget(field)
            browse = QPushButton("选择")
            browse.setObjectName(f"batch_{name}_browse")
            browse.clicked.connect(
                lambda checked=False, selected=name: self._browse_path(selected)
            )
            row.addWidget(browse)
            form.addRow(label, row)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.prepare_button = QPushButton("只读预览正式阶段 scope/input")
        self.run_button = QPushButton("运行正式阶段")
        self.cancel_button = QPushButton("取消")
        self.open_output_button = QPushButton("打开阶段输出")
        self.view_report_button = QPushButton("查看步骤报告")
        self.run_button.setEnabled(False)
        self.prepare_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.open_output_button.setEnabled(False)
        self.view_report_button.setEnabled(False)
        actions.addWidget(self.prepare_button)
        actions.addWidget(self.run_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.open_output_button)
        actions.addWidget(self.view_report_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.status_label = QLabel("等待 canonical-ready P2-B。P3-C 无通用正式入口。")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.prepare_button.clicked.connect(self._prepare)
        self.run_button.clicked.connect(self._run)
        self.cancel_button.clicked.connect(self.worker.cancel)
        self.open_output_button.clicked.connect(self._open_output)
        self.view_report_button.clicked.connect(self._view_report)
        self.stage_combo.currentIndexChanged.connect(self._update_availability)

    def _browse_path(self, name: str) -> None:
        if name == "config":
            path, _ = QFileDialog.getOpenFileName(
                self, "选择配置", "", "YAML (*.yaml *.yml)"
            )
        elif name in {"scope", "inputs"}:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择显式 JSON", "", "JSON (*.json)"
            )
        else:
            path = QFileDialog.getExistingDirectory(self, "选择权威输出目录")
        if path:
            self.path_fields[name].setText(path)

    def set_p2b_ready(self, ready: bool, directory: object) -> None:
        self.p2b_ready = bool(ready)
        self.p2b_directory = None if directory is None else Path(directory).resolve()
        self._update_availability()

    def set_plan_modes(self, modes: tuple[str, ...] | list[str] | set[str]) -> None:
        self.plan_modes = frozenset(str(item) for item in modes)
        self._update_availability()

    def _stage_is_applicable(self, stage: BatchStage) -> bool:
        if not self.plan_modes:
            return True
        capability = next(
            item for item in self.service.capabilities() if item.stage is stage
        )
        required = set(capability.supported_modes)
        if stage is BatchStage.P5_B:
            return required <= self.plan_modes
        return bool(required & self.plan_modes)

    def _update_availability(self) -> None:
        stage = BatchStage(self.stage_combo.currentData())
        applicable = self._stage_is_applicable(stage)
        self.prepare_button.setEnabled(self.p2b_ready and applicable)
        if not applicable:
            self.status_label.setText(
                f"{stage.value}：本计划不适用（measurement mode 不匹配）；这不是失败。"
            )
        elif self.p2b_ready:
            self.status_label.setText("P2-B 已通过，可准备满足前置条件的正式阶段。")
        else:
            self.status_label.setText("P2-B 未通过；canonical P4/P5/P6 保持锁定。")

    def prepare_current(self, *, run_id: str | None = None) -> PreparedBatchInvocation:
        if not self.p2b_ready or self.p2b_directory is None:
            raise PermissionError("canonical-ready P2-B is required")
        stage = BatchStage(self.stage_combo.currentData())
        if not self._stage_is_applicable(stage):
            raise ValueError(f"{stage.value} is not applicable to the current plan")
        selected_run_id = run_id or f"u3-{uuid.uuid4().hex[:12]}"
        invocation = self.service.prepare_formal_stage(
            stage=stage,
            scope_path=self.path_fields["scope"].text(),
            input_manifest_path=self.path_fields["inputs"].text(),
            preview_directory=self.project_root / "outputs/ui3_runs" / selected_run_id / f"{stage.value.lower()}_preview",
            config_path=self.path_fields["config"].text(),
            output_root=self.project_root / "outputs",
            run_id=selected_run_id,
            dataset_qc_directory=self.p2b_directory,
            comparison_directory=self.path_fields["comparison"].text() or None,
        )
        self.active_invocation = invocation
        self.run_button.setEnabled(True)
        self.status_label.setText(
            f"已生成只读预览：{invocation.preview_directory}。"
            "请确认样本、排除原因、scope 和 manifest 后再运行。"
        )
        return invocation

    def _prepare(self) -> None:
        try:
            self.prepare_current()
        except Exception as exc:
            message, _ = humanize_exception(exc)
            QMessageBox.warning(self, "阶段预览失败", message)

    def _run(self) -> None:
        if self.active_invocation is None:
            return
        try:
            self.worker.start(self.active_invocation)
            self.run_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.stage_status_changed.emit(self.active_invocation.stage.value, "running")
        except Exception as exc:
            message, _ = humanize_exception(exc)
            QMessageBox.warning(self, "阶段启动失败", message)

    def _finished(self, run_id: str, result: ProcessResult, invocation: PreparedBatchInvocation) -> None:
        del run_id
        self.cancel_button.setEnabled(False)
        self.service.record_stage_result(
            invocation,
            outcome=result.outcome.value,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            result_summary={"scientifically_eligible": False},
        )
        self.last_completed_invocation = invocation
        self.open_output_button.setEnabled(invocation.output_directory.exists())
        self.view_report_button.setEnabled(
            (invocation.preview_directory / "step_report.html").is_file()
        )
        self.status_label.setText(
            f"{invocation.stage.value} 状态={result.outcome.value}；"
            "模拟/参考结果仍 scientifically_ineligible；请查看权威 backend bundle。"
        )
        self.stage_status_changed.emit(invocation.stage.value, result.outcome.value)
        self.message.emit(self.status_label.text())

    def _open_output(self) -> None:
        if self.last_completed_invocation is not None:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.last_completed_invocation.output_directory))
            )

    def _view_report(self) -> None:
        if self.last_completed_invocation is None:
            return
        report = self.last_completed_invocation.preview_directory / "step_report.html"
        if report.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(report)))

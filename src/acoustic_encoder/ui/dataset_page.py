"""DEV-UI3 explicit sample registry and P2-B page."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import uuid

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from acoustic_encoder.schemas import FeatureKind
from acoustic_encoder.ui.batch_workflow import (
    BatchWorkflowService,
    BatchWorkflowState,
    BatchWorkflowStatus,
    PreparedBatchInvocation,
)
from acoustic_encoder.ui.experiment_plan import ExperimentPlanService, ExperimentRole, SavedPlanRevision
from acoustic_encoder.ui.sample_registry import (
    ManualReviewDecision,
    RegisteredSample,
    SampleMatchResult,
    SampleRegistry,
)
from acoustic_encoder.ui.services import humanize_exception
from acoustic_encoder.ui.workers import BatchStageWorker, ProcessOutcome, ProcessResult


class DatasetQCPage(QWidget):
    message = Signal(str)
    p2b_ready_changed = Signal(bool, object)
    workflow_status_changed = Signal(str)

    def __init__(self, project_root: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()
        self.plan_service = ExperimentPlanService(self.project_root / "outputs/ui_plans")
        self.batch_service = BatchWorkflowService(self.project_root)
        self.registry = SampleRegistry(self.project_root / "outputs/ui3_registry")
        self.worker = BatchStageWorker(self)
        self.workflow_state = BatchWorkflowState()
        self.saved_plan: SavedPlanRevision | None = None
        self.registrations: list[RegisteredSample] = []
        self.last_match: SampleMatchResult | None = None
        self.active_invocation: PreparedBatchInvocation | None = None
        self.last_p2b_directory: Path | None = None
        self.setObjectName("datasetQCPage")
        self._build()
        self.worker.stdout_received.connect(self.message)
        self.worker.stderr_received.connect(self.message)
        self.worker.finished.connect(self._finished)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self.plan_label = QLabel("尚未加载计划 revision。")
        self.plan_label.setWordWrap(True)
        layout.addWidget(self.plan_label)
        controls = QHBoxLayout()
        self.load_plan_button = QPushButton("选择计划 revision")
        self.load_plan_button.setObjectName("loadPlanRevisionButton")
        self.register_button = QPushButton("登记选中预期样本的 UI2 session")
        self.register_button.setObjectName("registerUi2SessionButton")
        self.manual_review_button = QPushButton("追加人工审核记录")
        controls.addWidget(self.load_plan_button)
        controls.addWidget(self.register_button)
        controls.addWidget(self.manual_review_button)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.sample_table = QTableWidget(0, 16)
        self.sample_table.setObjectName("sampleRegistryTable")
        self.sample_table.setHorizontalHeaderLabels(
            (
                "plan sample ID", "source sample ID", "origin", "mode", "configuration",
                "angle", "session", "repeat", "experiment role", "single QC",
                "manual review", "eligible", "source hash", "FeatureSet",
                "SpectrumData", "match status",
            )
        )
        layout.addWidget(self.sample_table)
        p2b_controls = QHBoxLayout()
        self.preview_p2b_button = QPushButton("预览并确认 P2-B scope/input")
        self.preview_p2b_button.setObjectName("previewP2BButton")
        self.run_p2b_button = QPushButton("运行 P2-B 数据集 QC")
        self.run_p2b_button.setObjectName("runP2BButton")
        self.cancel_p2b_button = QPushButton("取消 P2-B")
        self.open_p2b_output_button = QPushButton("打开 P2-B 结果文件夹")
        self.view_p2b_report_button = QPushButton("查看 P2-B 步骤报告")
        self.cancel_p2b_button.setEnabled(False)
        self.open_p2b_output_button.setEnabled(False)
        self.view_p2b_report_button.setEnabled(False)
        self.run_p2b_button.setEnabled(False)
        p2b_controls.addWidget(self.preview_p2b_button)
        p2b_controls.addWidget(self.run_p2b_button)
        p2b_controls.addWidget(self.cancel_p2b_button)
        p2b_controls.addWidget(self.open_p2b_output_button)
        p2b_controls.addWidget(self.view_p2b_report_button)
        p2b_controls.addStretch(1)
        layout.addLayout(p2b_controls)
        self.summary_label = QLabel("P2-B 尚未运行。")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.load_plan_button.clicked.connect(self._choose_plan)
        self.register_button.clicked.connect(self._choose_session)
        self.manual_review_button.clicked.connect(self._manual_review)
        self.preview_p2b_button.clicked.connect(self._preview_p2b)
        self.run_p2b_button.clicked.connect(self._run_p2b)
        self.cancel_p2b_button.clicked.connect(self.worker.cancel)
        self.open_p2b_output_button.clicked.connect(self._open_p2b_output)
        self.view_p2b_report_button.clicked.connect(self._view_p2b_report)

    def load_plan_revision(self, directory: str | Path) -> SavedPlanRevision:
        saved = self.plan_service.load_revision(directory)
        self.saved_plan = saved
        self.workflow_state = BatchWorkflowState()
        self.workflow_state.transition(BatchWorkflowStatus.PLAN_DRAFT)
        if saved.checklist.ready_for_acquisition:
            self.workflow_state.transition(BatchWorkflowStatus.PLAN_READY)
            self.workflow_state.transition(BatchWorkflowStatus.ACQUISITION_WAITING)
        self.workflow_status_changed.emit(self.workflow_state.status.value)
        self.plan_label.setText(
            f"计划：{saved.plan.plan_id} rev-{saved.revision:03d}｜"
            f"预期 {len(saved.samples)} 个样本｜ready_for_acquisition="
            f"{str(saved.checklist.ready_for_acquisition).lower()}｜科研资格=false"
        )
        self._refresh_table()
        return saved

    def _choose_plan(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择包含 plan_manifest.json 的 revision")
        if directory:
            try:
                self.load_plan_revision(directory)
            except Exception as exc:
                message, _ = humanize_exception(exc)
                QMessageBox.warning(self, "计划加载失败", message)

    def register_session(
        self,
        session_manifest: str | Path,
        *,
        expected_index: int,
        output_directory: str | Path | None = None,
    ) -> RegisteredSample:
        if self.saved_plan is None:
            raise RuntimeError("必须先加载计划")
        expected = self.saved_plan.samples[expected_index]
        registered = self.registry.register_ui2_session(
            session_manifest,
            expected=expected,
            output_directory=output_directory,
        )
        self.registrations.append(registered)
        self._refresh_table()
        return registered

    def _choose_session(self) -> None:
        if self.saved_plan is None:
            QMessageBox.warning(self, "无法登记", "请先加载计划 revision。")
            return
        row = self.sample_table.currentRow()
        if row < 0 or row >= len(self.saved_plan.samples):
            QMessageBox.warning(self, "无法登记", "请先选择一个预期样本行。")
            return
        manifest, _ = QFileDialog.getOpenFileName(
            self, "选择明确的 UI2 session manifest", "", "JSON (*.json)"
        )
        if not manifest:
            return
        output = QFileDialog.getExistingDirectory(
            self, "选择该样本的明确 run output；取消表示仅登记 session"
        )
        try:
            self.register_session(
                manifest,
                expected_index=row,
                output_directory=output or None,
            )
        except Exception as exc:
            message, _ = humanize_exception(exc)
            QMessageBox.warning(self, "样本登记失败", message)

    def _refresh_table(self) -> None:
        if self.saved_plan is None:
            self.sample_table.setRowCount(0)
            return
        self.last_match = self.registry.match(self.saved_plan.samples, self.registrations)
        by_expected = {
            row.expected_sample_id: row for row in self.last_match.rows if row.expected_sample_id
        }
        registration_by_expected = {
            item.expected_sample_id: item for item in self.registrations if item.expected_sample_id
        }
        self.sample_table.setRowCount(len(self.saved_plan.samples))
        for row_index, expected in enumerate(self.saved_plan.samples):
            actual = registration_by_expected.get(expected.sample_id)
            match = by_expected[expected.sample_id]
            sealed = expected.experiment_role is ExperimentRole.FINAL_TEST_SEALED
            values = (
                expected.sample_id,
                "" if actual is None else actual.source_sample_id,
                "" if actual is None else actual.metadata.data_origin.value,
                expected.measurement_mode.value,
                "sealed" if sealed else expected.configuration_id,
                "sealed" if sealed else f"{expected.angle_deg:g}",
                "sealed" if sealed else expected.session_id,
                "sealed" if sealed else f"{expected.repeat_type}/{expected.repeat_id}",
                expected.experiment_role.value,
                "" if actual is None else str(actual.qc_status or "unavailable"),
                "" if actual is None else (
                    "; ".join(actual.manual_review_reasons) or "none"
                ),
                "false" if actual is None else str(actual.metadata.eligible_for_scientific_analysis).lower(),
                "" if actual is None else actual.metadata.source_sha256,
                "unavailable" if actual is None else str(actual.feature_set_available).lower(),
                "unavailable" if actual is None else str(actual.spectrum_data_available).lower(),
                match.status.value,
            )
            for column, value in enumerate(values):
                self.sample_table.setItem(row_index, column, QTableWidgetItem(value))
        non_final = [
            row for row in self.last_match.rows
            if row.expected_sample_id is not None
            and next(item for item in self.saved_plan.samples if item.sample_id == row.expected_sample_id).experiment_role
            is not ExperimentRole.FINAL_TEST_SEALED
        ]
        present = sum(row.status.value == "expected_and_present" for row in non_final)
        complete = bool(non_final) and present == len(non_final)
        if self.workflow_state.status in {
            BatchWorkflowStatus.PLAN_DRAFT,
            BatchWorkflowStatus.ACQUISITION_WAITING,
        }:
            self.workflow_state.transition(
                BatchWorkflowStatus.SAMPLES_COMPLETE if complete else BatchWorkflowStatus.SAMPLES_PARTIAL
            )
            self.workflow_status_changed.emit(self.workflow_state.status.value)
        self.summary_label.setText(
            f"已匹配 {present}/{len(non_final)} 个非 final-test 样本；"
            f"final-test 始终密封；科研资格=false。"
        )

    def _manual_review(self) -> None:
        if not self.registrations:
            QMessageBox.information(self, "人工审核", "当前没有已登记样本。")
            return
        operator, ok = QInputDialog.getText(self, "人工审核", "操作人")
        if not ok or not operator.strip():
            return
        reason, ok = QInputDialog.getText(self, "人工审核", "理由")
        if not ok or not reason.strip():
            return
        decision, ok = QInputDialog.getText(self, "人工审核", "决定")
        if not ok or not decision.strip():
            return
        audit = self.registry.append_manual_review(
            self.registrations[-1],
            ManualReviewDecision(
                operator,
                datetime.now().astimezone().isoformat(timespec="seconds"),
                reason,
                decision,
                None,
            ),
        )
        self.message.emit(f"已追加人工审核记录 #{audit.audit_index}；原始 QC/metadata 未修改。")

    def prepare_p2b(self, *, run_id: str | None = None) -> PreparedBatchInvocation:
        if self.saved_plan is None:
            raise RuntimeError("必须先加载计划")
        selected_expected = tuple(
            item
            for item in self.saved_plan.samples
            if item.experiment_role in {ExperimentRole.TRAINING, ExperimentRole.DEVELOPMENT}
        )
        selected_ids = {item.sample_id for item in selected_expected}
        selected_registrations = tuple(
            item for item in self.registrations if item.expected_sample_id in selected_ids
        )
        selected_run_id = run_id or f"u3-{uuid.uuid4().hex[:12]}"
        invocation = self.batch_service.prepare_p2b(
            expected_samples=selected_expected,
            registrations=selected_registrations,
            preview_directory=self.project_root / "outputs/ui3_runs" / self.saved_plan.plan.plan_id / selected_run_id / "p2b_preview",
            config_path=self.project_root / "config/default.yaml",
            output_root=self.project_root / "outputs",
            run_id=selected_run_id,
            feature_kind=FeatureKind.DENSE_RAW_SPL,
            selection_reason="User-confirmed DEV-UI3 plan and explicit UI2 registrations",
        )
        self.active_invocation = invocation
        self.run_p2b_button.setEnabled(True)
        self.summary_label.setText(
            f"P2-B 只读预览已生成：{invocation.preview_directory}。执行前请复核 scope、inputs 和 hashes。"
        )
        return invocation

    def _preview_p2b(self) -> None:
        try:
            invocation = self.prepare_p2b()
            self.message.emit(f"P2-B preview={invocation.preview_directory}")
        except Exception as exc:
            message, _ = humanize_exception(exc)
            QMessageBox.warning(self, "P2-B 预览失败", message)

    def _run_p2b(self) -> None:
        if self.active_invocation is None:
            return
        try:
            if self.workflow_state.status in {
                BatchWorkflowStatus.SAMPLES_PARTIAL,
                BatchWorkflowStatus.SAMPLES_COMPLETE,
                BatchWorkflowStatus.DATASET_QC_WARNING,
            }:
                self.workflow_state.transition(BatchWorkflowStatus.DATASET_QC_RUNNING)
                self.workflow_status_changed.emit(self.workflow_state.status.value)
            self.worker.start(self.active_invocation)
            self.run_p2b_button.setEnabled(False)
            self.cancel_p2b_button.setEnabled(True)
        except Exception as exc:
            message, _ = humanize_exception(exc)
            QMessageBox.warning(self, "P2-B 启动失败", message)

    def _finished(self, run_id: str, result: ProcessResult, invocation: PreparedBatchInvocation) -> None:
        del run_id
        self.cancel_p2b_button.setEnabled(False)
        summary_payload: dict[str, object] = {"scientifically_eligible": False}
        ready = False
        if result.outcome is ProcessOutcome.SUCCEEDED:
            try:
                summary = self.batch_service.load_p2b_summary(invocation.output_directory)
                self.last_p2b_directory = invocation.output_directory
                ready = summary.canonical_ready
                summary_payload.update(
                    aggregate_status=summary.aggregate_status,
                    canonical_ready=summary.canonical_ready,
                    missing_condition_count=summary.missing_condition_count,
                    unavailable_count=summary.unavailable_count,
                )
                self.workflow_state.transition(
                    BatchWorkflowStatus.DATASET_QC_PASSED
                    if ready
                    else BatchWorkflowStatus.DATASET_QC_WARNING
                )
                if ready:
                    self.workflow_state.transition(BatchWorkflowStatus.ANALYSIS_READY)
                self.workflow_status_changed.emit(self.workflow_state.status.value)
                self.summary_label.setText(
                    f"P2-B aggregate={summary.aggregate_status}；canonical_ready={str(ready).lower()}；"
                    f"missing={summary.missing_condition_count}；科研资格=false。"
                )
            except Exception as exc:
                self.workflow_state.transition(BatchWorkflowStatus.BLOCKED)
                self.workflow_status_changed.emit(self.workflow_state.status.value)
                self.summary_label.setText(f"P2-B 输出复核失败：{exc}")
        else:
            self.workflow_state.transition(
                BatchWorkflowStatus.DATASET_QC_WARNING
                if result.outcome is ProcessOutcome.CANCELLED
                else BatchWorkflowStatus.BLOCKED
            )
            self.workflow_status_changed.emit(self.workflow_state.status.value)
            self.summary_label.setText(
                "P2-B 已取消。" if result.outcome is ProcessOutcome.CANCELLED else "P2-B 执行失败。"
            )
        self.batch_service.record_stage_result(
            invocation,
            outcome=result.outcome.value,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            result_summary=summary_payload,
        )
        self.open_p2b_output_button.setEnabled(
            self.last_p2b_directory is not None and self.last_p2b_directory.exists()
        )
        self.view_p2b_report_button.setEnabled(
            (invocation.preview_directory / "step_report.html").is_file()
        )
        self.p2b_ready_changed.emit(ready, self.last_p2b_directory)

    def _open_p2b_output(self) -> None:
        if self.last_p2b_directory is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_p2b_directory)))

    def _view_p2b_report(self) -> None:
        if self.active_invocation is None:
            return
        report = self.active_invocation.preview_directory / "step_report.html"
        if report.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(report)))

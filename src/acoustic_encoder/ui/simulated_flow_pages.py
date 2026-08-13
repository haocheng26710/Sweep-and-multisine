"""Qt pages for the explicit DEV-UI4-FIX6 simulated workflow."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from acoustic_encoder.ui.experiment_plan import SavedPlanRevision
from acoustic_encoder.ui.measurement_workflow import (
    REAL_MULTISINE_BLOCK_MESSAGE,
    UsageRoute,
)
from acoustic_encoder.ui.services import humanize_exception
from acoustic_encoder.ui.simulated_flow import (
    SimulatedAcquisitionBatch,
    SimulatedFlowService,
    StimulusFlowArtifacts,
)
from acoustic_encoder.ui.workers import (
    ProcessOutcome,
    ProcessResult,
    SimulatedBatchInvocation,
    SimulatedBatchWorker,
)
from acoustic_encoder.ui.runtime import RuntimeContext


class StimulusPage(QWidget):
    status_changed = Signal(str)
    message = Signal(str)
    stimulus_ready = Signal(object)
    plan_selected = Signal(object)

    def __init__(self, service: SimulatedFlowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.saved_plan: SavedPlanRevision | None = None
        self.artifacts: StimulusFlowArtifacts | None = None
        self.route = UsageRoute.SIMULATED_PRACTICE
        layout = QVBoxLayout(self)
        self.route_label = QLabel()
        self.route_label.setWordWrap(True)
        layout.addWidget(self.route_label)
        self.plan_label = QLabel("尚未绑定步骤03的不可变计划 revision。")
        self.plan_label.setWordWrap(True)
        layout.addWidget(self.plan_label)
        self.choose_plan_button = QPushButton("选择已保存的步骤03计划 revision")
        self.choose_plan_button.setObjectName("choosePlanForStimulusButton")
        layout.addWidget(self.choose_plan_button)
        self.generate_button = QPushButton("按计划生成并复核实验刺激")
        self.generate_button.setObjectName("generatePlannedStimulusButton")
        layout.addWidget(self.generate_button)
        self.result_label = QLabel("尚未生成。")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(
            self.result_label.textInteractionFlags()
            | self.result_label.textInteractionFlags().TextSelectableByMouse
        )
        layout.addWidget(self.result_label)
        layout.addStretch(1)
        self.generate_button.clicked.connect(self.generate)
        self.choose_plan_button.clicked.connect(self.choose_plan)
        self.set_route(UsageRoute.SIMULATED_PRACTICE)

    def set_route(self, route: UsageRoute) -> None:
        self.route = route
        if route is UsageRoute.SIMULATED_PRACTICE:
            self.route_label.setText(
                "模拟练习：使用现有 P7 配置生成计划绑定的只读验证刺激；科研资格=false。"
            )
            self.generate_button.setEnabled(self.saved_plan is not None)
        elif route is UsageRoute.OFFICIAL_REFERENCE:
            self.route_label.setText(
                "官方参考路线不生成刺激或伪造录音；后续请选择官方 REW TXT。"
            )
            self.generate_button.setEnabled(False)
        else:
            self.route_label.setText(
                "真实实验仅显示外部播放/录音准备；本页不会运行真实 Multisine/P8。"
            )
            self.generate_button.setEnabled(False)

    def set_plan(self, saved: SavedPlanRevision) -> None:
        self.saved_plan = self.service.bind_plan(saved.directory)
        self.plan_label.setText(
            f"计划：{saved.plan.plan_id} rev-{saved.revision:03d}；"
            f"预期样本 {len(saved.samples)}；计划 revision 保持不可变。"
        )
        self.generate_button.setEnabled(
            self.route is UsageRoute.SIMULATED_PRACTICE
        )

    def choose_plan(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择包含 plan_manifest.json 的不可变 revision",
            str(self.service.workspace_root / "outputs/ui_plans"),
        )
        if not directory:
            return
        try:
            saved = self.service.plan_service.load_revision(directory)
        except Exception as error:
            message, technical = humanize_exception(error)
            self.message.emit(f"计划加载失败：{message}\n{technical}")
            return
        self.set_plan(saved)
        self.plan_selected.emit(saved)

    def restore(self, artifacts: StimulusFlowArtifacts) -> None:
        self.artifacts = artifacts
        self.result_label.setText(
            f"已复核 stimulus_id={artifacts.directory.name}\n"
            f"WAV SHA-256={artifacts.waveform_sha256}\n输出：{artifacts.directory}"
        )

    def generate(self) -> None:
        if self.saved_plan is None:
            self.status_changed.emit("failed")
            self.message.emit("必须先保存并绑定步骤03计划。")
            return
        self.status_changed.emit("running")
        try:
            artifacts = self.service.generate_stimulus(self.saved_plan.directory)
        except Exception as error:
            message, technical = humanize_exception(error)
            self.status_changed.emit("failed")
            self.message.emit(f"刺激生成失败：{message}\n{technical}")
            return
        self.restore(artifacts)
        self.status_changed.emit("passed")
        self.stimulus_ready.emit(artifacts)


class AcquisitionPage(QWidget):
    status_changed = Signal(str)
    message = Signal(str)
    acquisition_ready = Signal(object)

    def __init__(self, service: SimulatedFlowService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.saved_plan: SavedPlanRevision | None = None
        self.stimulus: StimulusFlowArtifacts | None = None
        self.batch: SimulatedAcquisitionBatch | None = None
        self.route = UsageRoute.SIMULATED_PRACTICE
        layout = QVBoxLayout(self)
        self.instructions = QLabel()
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)
        self.generate_button = QPushButton("生成计划中的全部模拟录音（32 样本）")
        self.generate_button.setObjectName("generatePlannedSimulatedRecordingsButton")
        layout.addWidget(self.generate_button)
        self.result_label = QLabel("尚未生成模拟采集批次。")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        layout.addStretch(1)
        self.generate_button.clicked.connect(self.generate)
        self.set_route(UsageRoute.SIMULATED_PRACTICE)

    def set_route(self, route: UsageRoute) -> None:
        self.route = route
        if route is UsageRoute.SIMULATED_PRACTICE:
            self.instructions.setText(
                "模拟练习无需外部设备。程序严格按步骤03 expected_sample_matrix，"
                "通过现有 S3 生成 WAV、sidecar、批次 manifest 和 SHA-256。"
            )
            self.generate_button.setEnabled(
                self.saved_plan is not None and self.stimulus is not None
            )
        elif route is UsageRoute.OFFICIAL_REFERENCE:
            self.instructions.setText(
                "官方参考数据不会生成伪造录音。请在步骤06选择官方 REW TXT；"
                "其用途仅为 parser/software validation。"
            )
            self.generate_button.setEnabled(False)
        else:
            self.instructions.setText(
                "真实实验请在外部完成播放、录音与原始文件登记。\n"
                + REAL_MULTISINE_BLOCK_MESSAGE
            )
            self.generate_button.setEnabled(False)

    def set_inputs(
        self, saved: SavedPlanRevision, stimulus: StimulusFlowArtifacts | None
    ) -> None:
        self.saved_plan = saved
        self.stimulus = stimulus
        self.generate_button.setEnabled(
            stimulus is not None and self.route is UsageRoute.SIMULATED_PRACTICE
        )

    def restore(self, batch: SimulatedAcquisitionBatch) -> None:
        self.batch = batch
        self.result_label.setText(
            f"已复核 {batch.sample_count}/{batch.sample_count} 个显式模拟样本。\n"
            f"批次 manifest：{batch.manifest_path}"
        )

    def generate(self) -> None:
        if self.saved_plan is None or self.stimulus is None:
            self.status_changed.emit("failed")
            self.message.emit("必须先完成步骤03和步骤04。")
            return
        self.status_changed.emit("running")
        try:
            batch = self.service.generate_simulated_acquisition(
                self.saved_plan.directory, self.stimulus.manifest_path
            )
        except Exception as error:
            message, technical = humanize_exception(error)
            self.status_changed.emit("failed")
            self.message.emit(f"模拟录音生成失败：{message}\n{technical}")
            return
        self.restore(batch)
        self.status_changed.emit("passed")
        self.acquisition_ready.emit(batch)


class SimulatedBatchPage(QWidget):
    status_changed = Signal(str)
    message = Signal(str)
    processing_ready = Signal(str)

    def __init__(
        self,
        service: SimulatedFlowService,
        runtime: RuntimeContext,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.batch: SimulatedAcquisitionBatch | None = None
        self.worker = SimulatedBatchWorker(
            service.project_root, runtime_context=runtime, parent=self
        )
        self._stdout_buffer = ""
        layout = QVBoxLayout(self)
        self.instructions = QLabel(
            "输入只来自步骤05显式批次 manifest；不扫描目录、不从文件名推断身份。"
        )
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)
        controls = QHBoxLayout()
        self.run_button = QPushButton("一键预检并处理计划中的全部模拟样本")
        self.run_button.setObjectName("processAllPlannedSimulatedSamplesButton")
        self.cancel_button = QPushButton("安全取消批量处理")
        self.cancel_button.setObjectName("cancelSimulatedBatchButton")
        self.cancel_button.setEnabled(False)
        controls.addWidget(self.run_button)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setObjectName("simulatedBatchProgress")
        self.progress.setRange(0, 32)
        layout.addWidget(self.progress)
        self.current_label = QLabel("当前样本：尚未开始")
        self.counts_label = QLabel("成功 0；warning 0；失败 0")
        layout.addWidget(self.current_label)
        layout.addWidget(self.counts_label)
        layout.addStretch(1)
        self.run_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)
        self.worker.stdout_received.connect(self._stdout)
        self.worker.stderr_received.connect(self.message)
        self.worker.finished.connect(self._finished)

    @property
    def is_running(self) -> bool:
        return self.worker.is_running

    def set_batch(self, batch: SimulatedAcquisitionBatch) -> None:
        self.batch = batch
        self.progress.setRange(0, batch.sample_count)
        self.run_button.setEnabled(True)

    def start(self) -> None:
        if self.batch is None:
            self.status_changed.emit("failed")
            self.message.emit("必须先完成步骤05模拟采集。")
            return
        self._stdout_buffer = ""
        self.progress.setValue(0)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_changed.emit("running")
        try:
            self.worker.start(self.batch.manifest_path)
        except Exception as error:
            self.run_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.status_changed.emit("failed")
            self.message.emit(str(error))

    def cancel(self) -> None:
        self.cancel_button.setEnabled(False)
        self.current_label.setText("正在安全取消；已完成样本及审计记录将保留……")
        self.worker.cancel()

    def _stdout(self, text: str) -> None:
        self._stdout_buffer += text
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                self.message.emit(line)
                continue
            if event.get("event") in {"sample_started", "sample_finished"}:
                current = int(event.get("current", 0))
                self.progress.setValue(current)
                self.current_label.setText(
                    f"当前样本：{event.get('sample_id')}（{current}/{event.get('total')}）"
                )
                self.counts_label.setText(
                    f"已处理 {current}；warning {event.get('warning_count', 0)}；"
                    f"失败 {event.get('failed_count', 0)}"
                )

    def _finished(
        self, result: ProcessResult, invocation: SimulatedBatchInvocation
    ) -> None:
        del invocation
        self.cancel_button.setEnabled(False)
        self.run_button.setEnabled(True)
        manifest_path: str | None = None
        for line in result.stdout.splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if value.get("event") == "batch_finished":
                manifest_path = str(value["manifest_path"])
        if result.outcome is ProcessOutcome.CANCELLED:
            self.status_changed.emit("warning")
            self.message.emit("批量处理已取消；已完成部分及取消状态已写入审计 manifest。")
            return
        if result.outcome is not ProcessOutcome.SUCCEEDED or manifest_path is None:
            self.status_changed.emit("failed")
            self.message.emit("批量处理失败；未将步骤06标记为 passed。\n" + result.stderr)
            return
        self.status_changed.emit("passed")
        self.processing_ready.emit(manifest_path)
        self.message.emit(f"步骤06完成：显式处理 manifest={manifest_path}")

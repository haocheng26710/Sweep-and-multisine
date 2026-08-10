"""DEV-UI4 P9, package freeze, offline readout, and sealed final-test page."""

from __future__ import annotations

from pathlib import Path
import uuid

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from acoustic_encoder.ui.offline_workflow import OfflineReadoutService, SCORE_EXPLANATION
from acoustic_encoder.ui.p9_workflow import P9Invocation, P9WorkflowService
from acoustic_encoder.ui.runtime import RuntimeContext
from acoustic_encoder.ui.workers import ProcessOutcome, ProcessResult, ProcessTask


REAL_MULTISINE_P9_BLOCK = (
    "真实 Multisine/P8 尚未获准；依赖真实 Multisine authority 的 P9-C、冻结与 final-test 均保持 blocked。"
)


class FinalDeliveryPage(QWidget):
    message = Signal(str)
    stage_status_changed = Signal(str, str)

    def __init__(self, runtime: RuntimeContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.p9 = P9WorkflowService(runtime)
        self.offline = OfflineReadoutService(runtime)
        self.worker = ProcessTask(self)
        self.active: P9Invocation | None = None
        self.setObjectName("finalDeliveryPage")
        self._build()
        self.worker.stdout_received.connect(self.log.appendPlainText)
        self.worker.stderr_received.connect(self.log.appendPlainText)
        self.worker.finished.connect(self._finished)

    @property
    def is_running(self) -> bool:
        return self.worker.is_running

    def _edit(self, name: str, placeholder: str = "") -> QLineEdit:
        value = QLineEdit()
        value.setObjectName(name)
        value.setPlaceholderText(placeholder)
        return value

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        self.view_title = QLabel("P9 与最终交付")
        self.view_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(self.view_title)
        self.block_banner = QLabel(REAL_MULTISINE_P9_BLOCK)
        self.block_banner.setWordWrap(True)
        self.block_banner.setStyleSheet("font-weight: 600; padding: 6px;")
        layout.addWidget(self.block_banner)

        self.p9_group = QGroupBox("P9-A～P9-C（仅显式 training/development authority）")
        form = QFormLayout(self.p9_group)
        self.config_edit = self._edit("p9ConfigPath", "resolved YAML")
        self.scope_edit = self._edit("p9ScopePath", "explicit scope JSON")
        self.inputs_edit = self._edit("p9InputsPath", "explicit input manifest JSON")
        self.candidates_edit = self._edit("p9CandidatePath", "candidate universe JSON")
        self.dataset_qc_edit = self._edit("p9DatasetQCPath", "P2-B output directory")
        self.metrics_edit = self._edit("p9MetricsPath", "optional P4 metrics directory")
        self.p9a_authorities_edit = self._edit("p9AAuthorities", "P9-A fold directories separated by ;")
        self.run_id_edit = self._edit("p9RunId")
        self.run_id_edit.setText(f"ui4-{uuid.uuid4().hex[:10]}")
        for label, widget in (
            ("配置", self.config_edit), ("Scope", self.scope_edit), ("Inputs", self.inputs_edit),
            ("Candidate universe", self.candidates_edit), ("P2-B authority", self.dataset_qc_edit),
            ("P4 authority", self.metrics_edit), ("P9-A fold authorities", self.p9a_authorities_edit),
            ("Run ID", self.run_id_edit),
        ):
            form.addRow(label, widget)
        row = QHBoxLayout()
        self.p9a_button = QPushButton("运行 P9-A tone 选择")
        self.p9b_button = QPushButton("运行 P9-B 最小 tone 消融")
        self.p9c_button = QPushButton("运行 P9-C 跨模式桥接")
        row.addWidget(self.p9a_button)
        row.addWidget(self.p9b_button)
        row.addWidget(self.p9c_button)
        form.addRow(row)
        layout.addWidget(self.p9_group)

        self.freeze_group = QGroupBox("冻结分析方案（P9-D）")
        freeze_form = QFormLayout(self.freeze_group)
        self.training_manifest_edit = self._edit("trainingManifestPath", "explicit training manifest")
        self.package_output_edit = self._edit("packageOutputPath", "new immutable package directory")
        self.approval_operator_edit = self._edit("freezeApprovalOperator", "operator name")
        freeze_form.addRow("Training manifest", self.training_manifest_edit)
        freeze_form.addRow("新 package 目录", self.package_output_edit)
        freeze_form.addRow("人工批准记录：操作人", self.approval_operator_edit)
        self.freeze_warning = QLabel(
            "冻结后不能修改 tone、归一化、阈值、校准、模型或方向标签；任何变更必须创建新 revision，不能覆盖。"
        )
        self.freeze_warning.setWordWrap(True)
        freeze_form.addRow(self.freeze_warning)
        self.freeze_button = QPushButton("确认并创建新 P9-D package revision")
        freeze_form.addRow(self.freeze_button)
        layout.addWidget(self.freeze_group)

        self.final_group = QGroupBox("最终测试（默认密封）")
        final_layout = QVBoxLayout(self.final_group)
        self.final_test_state_label = QLabel("final-test 状态：sealed")
        final_layout.addWidget(self.final_test_state_label)
        warning = QLabel(
            "不可逆操作：必须具备冻结计划、通过 self-check 的真实 package、独立保管/批准记录、"
            "一致 scope、空且唯一输出、一次性规则、真实科研 authority 和已批准真实 Multisine 后端。"
        )
        warning.setWordWrap(True)
        final_layout.addWidget(warning)
        self.unseal_button = QPushButton("解封并执行一次（authority 不完整，已禁用）")
        self.unseal_button.setEnabled(False)
        final_layout.addWidget(self.unseal_button)
        layout.addWidget(self.final_group)

        self.offline_group = QGroupBox("使用冻结模型离线读取一次测量")
        offline_form = QFormLayout(self.offline_group)
        self.offline_package_edit = self._edit("offlinePackagePath")
        self.offline_input_edit = self._edit("offlineInputManifestPath")
        self.offline_output_edit = self._edit("offlineOutputPath")
        offline_form.addRow("Frozen package", self.offline_package_edit)
        offline_form.addRow("显式 input manifest", self.offline_input_edit)
        offline_form.addRow("新输出目录", self.offline_output_edit)
        explanation = QLabel(SCORE_EXPLANATION)
        explanation.setWordWrap(True)
        offline_form.addRow(explanation)
        self.offline_button = QPushButton("运行离线方向读取")
        offline_form.addRow(self.offline_button)
        layout.addWidget(self.offline_group)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.cancel_button = QPushButton("取消当前任务")
        self.cancel_button.setEnabled(False)
        layout.addWidget(self.cancel_button)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("运行日志和结构化后端结果")
        layout.addWidget(self.log)

        self.p9a_button.clicked.connect(self._start_p9a)
        self.p9b_button.clicked.connect(self._start_p9b)
        self.p9c_button.clicked.connect(self._start_p9c)
        self.freeze_button.clicked.connect(self._start_freeze)
        self.offline_button.clicked.connect(self._start_offline)
        self.cancel_button.clicked.connect(self.worker.cancel)

    def set_view(self, step_id: str) -> None:
        self.p9_group.setVisible(step_id == "modeling")
        self.freeze_group.setVisible(step_id == "freeze")
        self.final_group.setVisible(step_id == "final_test")
        self.offline_group.setVisible(step_id == "reports")
        titles = {
            "modeling": "分类、选频和校准：正式 P9 入口",
            "freeze": "冻结分析方案",
            "final_test": "最终测试：sealed",
            "reports": "离线读取与报告",
        }
        self.view_title.setText(titles.get(step_id, "P9 与最终交付"))

    def _path(self, editor: QLineEdit) -> Path:
        if not editor.text().strip():
            raise ValueError(f"必须显式填写：{editor.objectName()}")
        return Path(editor.text().strip())

    def _start(self, invocation: P9Invocation) -> None:
        if self.worker.is_running:
            raise RuntimeError("已有后台任务正在运行")
        self.active = invocation
        self.progress.setRange(0, 0)
        self.cancel_button.setEnabled(True)
        self.log.appendPlainText(f"{invocation.stage}: {invocation.program} {list(invocation.arguments)}")
        self.stage_status_changed.emit(invocation.stage, "running")
        self.worker.start(invocation.program, invocation.arguments, working_directory=self.runtime.workspace_root)

    def _guard(self, callback) -> None:
        try:
            callback()
        except Exception as exc:  # UI boundary: preserve technical detail in log.
            self.log.appendPlainText(f"{type(exc).__name__}: {exc}")
            self.message.emit(f"无法开始：{exc}")

    def _start_p9a(self) -> None:
        self._guard(lambda: self._start(self.p9.prepare_p9a(
            config=self._path(self.config_edit), scope=self._path(self.scope_edit),
            inputs=self._path(self.inputs_edit), candidate_universe=self._path(self.candidates_edit),
            dataset_qc_directory=self._path(self.dataset_qc_edit), output_root=self.runtime.output_root,
            run_id=self.run_id_edit.text().strip(),
            comparison_metrics_directory=(Path(self.metrics_edit.text()) if self.metrics_edit.text().strip() else None),
        )))

    def _start_p9b(self) -> None:
        authorities = tuple(Path(item.strip()) for item in self.p9a_authorities_edit.text().split(";") if item.strip())
        self._guard(lambda: self._start(self.p9.prepare_p9b(
            config=self._path(self.config_edit), scope=self._path(self.scope_edit),
            inputs=self._path(self.inputs_edit), candidate_universe=self._path(self.candidates_edit),
            p9a_authority_directories=authorities, output_root=self.runtime.output_root,
            run_id=self.run_id_edit.text().strip(),
        )))

    def _start_p9c(self) -> None:
        self._guard(lambda: self._start(self.p9.prepare_p9c(
            config=self._path(self.config_edit), scope=self._path(self.scope_edit),
            inputs=self._path(self.inputs_edit), output_root=self.runtime.output_root,
            run_id=self.run_id_edit.text().strip(),
        )))

    def _start_freeze(self) -> None:
        self._guard(lambda: self._start(self.p9.prepare_p9d(
            config=self._path(self.config_edit), training_manifest=self._path(self.training_manifest_edit),
            output_directory=self._path(self.package_output_edit),
            approval_operator=self.approval_operator_edit.text(),
        )))

    def _start_offline(self) -> None:
        self._guard(lambda: self._start(self.offline.prepare(
            package_directory=self._path(self.offline_package_edit),
            input_manifest=self._path(self.offline_input_edit),
            output_directory=self._path(self.offline_output_edit),
        )))

    def _finished(self, result: ProcessResult) -> None:
        invocation = self.active
        stage = invocation.stage if invocation else "UI4"
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.cancel_button.setEnabled(False)
        status = "succeeded" if result.outcome is ProcessOutcome.SUCCEEDED else result.outcome.value
        if status == "succeeded" and invocation is not None and stage == "P9-D":
            try:
                evidence = self.p9.finalize_package(
                    invocation.output_directory,
                    approval_operator=invocation.approval_operator or "",
                )
                self.log.appendPlainText(
                    f"package self-check passed: {evidence.package_semantic_sha256}"
                )
            except Exception as exc:
                status = "failed"
                self.log.appendPlainText(f"package finalize failed: {type(exc).__name__}: {exc}")
        self.stage_status_changed.emit(stage, status)
        self.message.emit(f"{stage} 后台任务：{status}；exit_code={result.exit_code}")
        self.active = None

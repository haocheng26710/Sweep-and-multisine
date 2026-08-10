"""DEV-UI3 experiment-plan form page."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
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

from acoustic_encoder.schemas import MeasurementMode
from acoustic_encoder.ui.services import humanize_exception
from acoustic_encoder.ui.experiment_plan import (
    ChecklistStatus,
    ExperimentPlan,
    ExperimentPlanService,
    ExperimentRole,
    PlanConditionBlock,
    PlanPreview,
    SafetyChecklist,
    SafetyChecklistItem,
    SavedPlanRevision,
)


class ExperimentPlanPage(QWidget):
    plan_saved = Signal(object)
    message = Signal(str)

    def __init__(self, project_root: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()
        self.service = ExperimentPlanService(self.project_root / "outputs/ui_plans")
        self.last_preview: PlanPreview | None = None
        self.last_saved: SavedPlanRevision | None = None
        self.setObjectName("experimentPlanPage")
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        basic_box = QGroupBox("实验计划基本信息")
        form = QFormLayout(basic_box)
        defaults = {
            "plan_id": "experiment-plan",
            "experiment_name": "声学方向实验",
            "research_question": "请填写研究问题",
            "operator": "",
            "plan_version": "1",
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "timezone": "Europe/London",
            "device_version": "V2",
            "device_chain": "",
            "calibration_uri": "unavailable",
            "provenance_uri": "",
            "output_root": "outputs",
        }
        labels = {
            "plan_id": "Plan ID",
            "experiment_name": "项目/实验名称",
            "research_question": "研究问题简述",
            "operator": "操作人员",
            "plan_version": "计划版本",
            "created_at": "创建时间（含时区）",
            "timezone": "时区",
            "device_version": "设备版本",
            "device_chain": "设备链说明",
            "calibration_uri": "校准记录位置",
            "provenance_uri": "Provenance record",
            "output_root": "输出根目录",
        }
        self.fields: dict[str, QLineEdit] = {}
        for name, value in defaults.items():
            field = QLineEdit(value)
            field.setObjectName(f"plan_{name}")
            self.fields[name] = field
            form.addRow(labels[name], field)
        self.revision_reason_edit = QLineEdit("")
        self.revision_reason_edit.setObjectName("planRevisionReason")
        self.revision_reason_edit.setPlaceholderText(
            "首次保存可留空；后续 revision 必须说明变更原因"
        )
        form.addRow("修订理由", self.revision_reason_edit)
        layout.addWidget(basic_box)

        conditions = QGroupBox("显式实验条件 blocks")
        conditions_layout = QVBoxLayout(conditions)
        self.condition_table = QTableWidget(1, 16)
        self.condition_table.setObjectName("planConditionTable")
        headers = (
            "block_id", "configurations", "angles_deg", "sessions", "acquisition_blocks",
            "measurement_mode", "experiment_role", "CONT", "REPOS rounds",
            "REPOS repeats", "REASM assemblies", "REASM repeats", "stimulus_id",
            "tone_set_id", "sample_rate_hz", "audio_channel",
        )
        self.condition_table.setHorizontalHeaderLabels(headers)
        defaults_row = (
            "main", "U4SYM,U4ENC", "0,90,180,270", "S01", "B01",
            "rew_sweep", "training", "2", "1", "1", "1", "1", "", "", "", "",
        )
        for column, value in enumerate(defaults_row):
            self.condition_table.setItem(0, column, QTableWidgetItem(value))
        conditions_layout.addWidget(self.condition_table)
        row_actions = QHBoxLayout()
        self.add_block_button = QPushButton("增加条件 block")
        self.remove_block_button = QPushButton("删除选中 block")
        row_actions.addWidget(self.add_block_button)
        row_actions.addWidget(self.remove_block_button)
        row_actions.addStretch(1)
        conditions_layout.addLayout(row_actions)
        layout.addWidget(conditions)

        safety = QGroupBox("安全与采集准备清单（人工声明，不授予科研资格）")
        safety_layout = QVBoxLayout(safety)
        self.safety_table = QTableWidget(len(SafetyChecklist.required_check_ids()), 6)
        self.safety_table.setObjectName("safetyChecklistTable")
        self.safety_table.setHorizontalHeaderLabels(
            ("check_id", "status", "operator", "time", "note", "evidence path")
        )
        for row, check_id in enumerate(SafetyChecklist.required_check_ids()):
            self.safety_table.setItem(row, 0, QTableWidgetItem(check_id))
            status = QComboBox()
            for item in ChecklistStatus:
                status.addItem(item.value, item.value)
            self.safety_table.setCellWidget(row, 1, status)
            for column in (2, 3, 4, 5):
                self.safety_table.setItem(row, column, QTableWidgetItem(""))
        safety_layout.addWidget(self.safety_table)
        layout.addWidget(safety)

        actions = QHBoxLayout()
        self.preview_button = QPushButton("预览样本矩阵")
        self.preview_button.setObjectName("previewPlanButton")
        self.save_button = QPushButton("保存不可变计划 revision")
        self.save_button.setObjectName("savePlanButton")
        actions.addWidget(self.preview_button)
        actions.addWidget(self.save_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.preview_label = QLabel("尚未生成矩阵。")
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

        self.add_block_button.clicked.connect(self._add_block)
        self.remove_block_button.clicked.connect(self._remove_block)
        self.preview_button.clicked.connect(self._preview_clicked)
        self.save_button.clicked.connect(self._save_clicked)

    def _add_block(self) -> None:
        row = self.condition_table.rowCount()
        self.condition_table.insertRow(row)
        values = (f"block-{row + 1}", "", "", "", "", "rew_sweep", "development") + ("0",) * 9
        for column, value in enumerate(values):
            self.condition_table.setItem(row, column, QTableWidgetItem(value))

    def _remove_block(self) -> None:
        if self.condition_table.rowCount() <= 1:
            return
        row = max(0, self.condition_table.currentRow())
        self.condition_table.removeRow(row)

    @staticmethod
    def _split(value: str) -> tuple[str, ...]:
        return tuple(item.strip() for item in value.split(",") if item.strip())

    def build_plan(self) -> ExperimentPlan:
        blocks: list[PlanConditionBlock] = []
        for row in range(self.condition_table.rowCount()):
            text = lambda column: (self.condition_table.item(row, column).text().strip() if self.condition_table.item(row, column) else "")
            mode = MeasurementMode(text(5))
            blocks.append(
                PlanConditionBlock(
                    block_id=text(0),
                    configurations=self._split(text(1)),
                    angles_deg=tuple(float(item) for item in self._split(text(2))),
                    sessions=self._split(text(3)),
                    acquisition_blocks=self._split(text(4)),
                    measurement_modes=(mode,),
                    experiment_role=ExperimentRole(text(6)),
                    cont_repeats=int(text(7)),
                    repos_rounds=int(text(8)),
                    repos_repeats_per_round=int(text(9)),
                    reasm_assemblies=int(text(10)),
                    reasm_repeats_per_assembly=int(text(11)),
                    stimulus_id=text(12) or None,
                    tone_set_id=text(13) or None,
                    sample_rate_hz=int(text(14)) if text(14) else None,
                    audio_channel=int(text(15)) if text(15) else None,
                )
            )
        values = {name: field.text().strip() for name, field in self.fields.items()}
        return ExperimentPlan(
            schema_version="1.0.0",
            condition_blocks=tuple(blocks),
            **values,
        )

    def build_checklist(self) -> SafetyChecklist:
        items: list[SafetyChecklistItem] = []
        for row in range(self.safety_table.rowCount()):
            check_id = self.safety_table.item(row, 0).text()
            status = ChecklistStatus(self.safety_table.cellWidget(row, 1).currentData())
            operator = self.safety_table.item(row, 2).text().strip() or None
            recorded_at = self.safety_table.item(row, 3).text().strip() or None
            note = self.safety_table.item(row, 4).text().strip() or None
            evidence_path = self.safety_table.item(row, 5).text().strip() or None
            items.append(
                SafetyChecklistItem(
                    check_id,
                    status,
                    operator,
                    recorded_at,
                    note,
                    evidence_path,
                    True,
                )
            )
        return SafetyChecklist("1.0.0", tuple(items))

    def preview_plan(self) -> PlanPreview:
        preview = self.service.preview(self.build_plan())
        self.last_preview = preview
        self.preview_label.setText(
            f"预计样本总数：{preview.expected_sample_count}；"
            f"大计划二次确认：{'需要' if preview.requires_large_plan_confirmation else '不需要'}；"
            "矩阵来自显式字段，未扫描目录或文件名。"
        )
        return preview

    def _preview_clicked(self) -> None:
        try:
            self.preview_plan()
        except Exception as exc:  # human-facing form boundary
            message, _ = humanize_exception(exc)
            QMessageBox.warning(self, "计划无法预览", message)

    def save_plan(self, *, revision_reason: str | None = None, large_confirmed: bool = False) -> SavedPlanRevision:
        plan = self.build_plan()
        preview = self.service.preview(plan)
        if preview.requires_large_plan_confirmation and not large_confirmed:
            raise PermissionError("异常大的计划必须再次确认")
        saved = self.service.save_revision(plan, self.build_checklist(), revision_reason=revision_reason)
        self.last_saved = saved
        self.plan_saved.emit(saved)
        self.message.emit(f"计划已保存：{saved.directory}")
        return saved

    def _save_clicked(self) -> None:
        try:
            preview = self.preview_plan()
            confirmed = True
            if preview.requires_large_plan_confirmation:
                confirmed = QMessageBox.question(
                    self,
                    "确认大计划",
                    f"计划包含 {preview.expected_sample_count} 个样本，是否继续保存？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                ) == QMessageBox.Yes
            if not confirmed:
                return
            self.save_plan(
                revision_reason=self.revision_reason_edit.text().strip() or None,
                large_confirmed=True,
            )
        except Exception as exc:
            message, _ = humanize_exception(exc)
            QMessageBox.warning(self, "计划保存失败", message)

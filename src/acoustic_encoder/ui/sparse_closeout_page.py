"""Presentation-only closeout for a verified sparse Multisine validation route."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class SparseCloseoutPage(QWidget):
    message = Signal(str)
    export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.audit_manifest: Path | None = None
        layout = QVBoxLayout(self)
        self.title_label = QLabel("Sparse Multisine 软件验证安全收尾")
        self.title_label.setStyleSheet("font-size: 17px; font-weight: 600;")
        layout.addWidget(self.title_label)
        self.summary_label = QLabel("尚未绑定显式数据集完整性审计。")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        self.audit_button = QPushButton("查看数据集完整性审计")
        self.audit_button.setObjectName("openSparseDatasetAuditButton")
        self.audit_button.setEnabled(False)
        layout.addWidget(self.audit_button)
        self.export_button = QPushButton("生成并导出软件验证总结")
        self.export_button.setObjectName("exportSoftwareValidationSummaryButton")
        self.export_button.setEnabled(False)
        layout.addWidget(self.export_button)
        self.output_label = QLabel()
        self.output_label.setWordWrap(True)
        layout.addWidget(self.output_label)
        layout.addStretch(1)
        self.audit_button.clicked.connect(self._open_audit)
        self.export_button.clicked.connect(self.export_requested)

    def bind_audit(self, manifest: str | Path) -> None:
        path = Path(manifest).resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.audit_manifest = path
        self.summary_label.setText(
            f"{payload['expected_and_present_count']}/{payload['expected_count']} "
            "expected_and_present；"
            f"P2-B={payload['p2_b_status']}；"
            f"downstream_route={payload['downstream_route']}。"
        )
        self.audit_button.setEnabled(True)
        self.export_button.setEnabled(True)

    def set_view(self, step_id: str) -> None:
        details = {
            "comparison": (
                "步骤08不适用（安全跳过）：当前没有 canonical P4/P5/P6 authority；"
                "FeatureSet-only P2-B/P4/P5/P6 控件已禁用。"
            ),
            "modeling": (
                "步骤09不适用（安全跳过）：当前没有 canonical P5/P6 authority；"
                "模拟 sparse tones 不获得分类、选频或校准资格。"
            ),
            "freeze": (
                "步骤10 blocked：没有批准的 P9-D/freeze authority；"
                "不得用模拟数据获得 deployment 或 freeze 资格。"
            ),
            "final_test": (
                "步骤11 sealed：final_test_read=false；没有读取、解封或执行入口。"
            ),
            "reports": (
                "步骤12 ready：可导出仅用于 software_validation 的总结；"
                "报告不可用于科研结论。"
            ),
        }
        self.detail_label.setText(details.get(step_id, ""))
        self.audit_button.setVisible(step_id == "comparison")
        self.export_button.setVisible(step_id == "reports")
        self.output_label.setVisible(step_id == "reports")

    def show_export(self, directory: str | Path) -> None:
        self.output_label.setText(f"软件验证总结已生成：{Path(directory).resolve()}")

    def _open_audit(self) -> None:
        if self.audit_manifest is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.audit_manifest)))

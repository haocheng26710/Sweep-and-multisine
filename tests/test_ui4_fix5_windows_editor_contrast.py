from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPalette, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QProxyStyle,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
)

from acoustic_encoder.ui.app import create_main_window


class _BlackEditorWindowsStyle(QProxyStyle):
    """Deterministic form of the native Windows 11 editor-palette defect."""

    def __init__(self) -> None:
        super().__init__("Fusion")
        self.setObjectName("windows11")

    def standardPalette(self) -> QPalette:
        palette = super().standardPalette()
        for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
            for role in (QPalette.Base, QPalette.Text):
                palette.setColor(group, role, QColor("#000000"))
        return palette


def _contrast(first: QColor, second: QColor) -> float:
    def luminance(color: QColor) -> float:
        channels = color.getRgbF()[:3]
        linear = tuple(
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        )
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _assert_palette_pair(
    palette: QPalette,
    group: QPalette.ColorGroup,
    foreground: QPalette.ColorRole,
    background: QPalette.ColorRole,
    *,
    minimum: float,
) -> None:
    foreground_color = palette.color(group, foreground)
    background_color = palette.color(group, background)
    assert foreground_color != background_color
    assert _contrast(foreground_color, background_color) >= minimum


def test_main_window_uses_readable_style_before_creating_pages(
    qtbot, tmp_path: Path,
) -> None:
    application = QApplication.instance()
    assert application is not None
    if "windows11" not in {name.casefold() for name in QStyleFactory.keys()}:
        pytest.skip("Windows 11 Qt style is unavailable on this platform")

    original_style = application.style().objectName()
    original_palette = QPalette(application.palette())
    try:
        assert application.setStyle("windows11") is not None
        assert application.style().objectName().casefold() == "windows11"

        window = create_main_window(tmp_path, workspace_root=tmp_path)
        qtbot.addWidget(window)

        assert application.style().objectName().casefold() == "fusion"
    finally:
        application.setStyle(original_style)
        application.setPalette(original_palette)


def test_black_on_black_windows11_editor_palette_is_removed_before_pages(
    qtbot, tmp_path: Path,
) -> None:
    application = QApplication.instance()
    assert application is not None
    original_style = application.style().objectName()
    original_palette = QPalette(application.palette())
    try:
        bad_style = _BlackEditorWindowsStyle()
        application.setStyle(bad_style)
        application.setPalette(bad_style.standardPalette())

        diagnostic_table = QTableWidget(1, 1)
        qtbot.addWidget(diagnostic_table)
        diagnostic_combo = QComboBox(diagnostic_table)
        diagnostic_combo.addItem("not_recorded")
        diagnostic_table.setCellWidget(0, 0, diagnostic_combo)
        assert diagnostic_combo.palette().color(QPalette.Base) == QColor("#000000")
        assert diagnostic_combo.palette().color(QPalette.Text) == QColor("#000000")
        diagnostic_table.removeCellWidget(0, 0)
        diagnostic_table.setItem(0, 0, QTableWidgetItem("diagnostic"))
        diagnostic_table.show()
        diagnostic_table.editItem(diagnostic_table.item(0, 0))
        qtbot.wait(10)
        diagnostic_editor = diagnostic_table.findChild(QLineEdit)
        assert diagnostic_editor is not None
        assert diagnostic_editor.palette().color(QPalette.Base) == QColor("#000000")
        assert diagnostic_editor.palette().color(QPalette.Text) == QColor("#000000")

        window = create_main_window(tmp_path, workspace_root=tmp_path)
        qtbot.addWidget(window)
        assert application.style().objectName().casefold() == "fusion"
        combo = window.plan_page.safety_table.cellWidget(0, 1)
        assert combo is not None
        _assert_palette_pair(
            combo.palette(), QPalette.Active,
            QPalette.ButtonText, QPalette.Button,
            minimum=4.5,
        )
    finally:
        application.setStyle(original_style)
        application.setPalette(original_palette)


def test_plan_editors_remain_readable_while_status_changes(
    qtbot, tmp_path: Path,
) -> None:
    application = QApplication.instance()
    assert application is not None
    original_style = application.style().objectName()
    original_palette = QPalette(application.palette())
    try:
        if "windows11" in {name.casefold() for name in QStyleFactory.keys()}:
            application.setStyle("windows11")
        window = create_main_window(tmp_path, workspace_root=tmp_path)
        qtbot.addWidget(window)
        window.resize(1280, 720)
        window.show()
        window.select_step("plan")
        qtbot.wait(20)

        combo = window.plan_page.safety_table.cellWidget(0, 1)
        assert combo is not None
        assert [combo.itemText(index) for index in range(combo.count())] == [
            "not_recorded",
            "declared_pass",
            "declared_unavailable",
            "declared_fail",
        ]
        for group in (QPalette.Active, QPalette.Inactive):
            _assert_palette_pair(
                combo.palette(), group, QPalette.ButtonText, QPalette.Button,
                minimum=4.5,
            )
            _assert_palette_pair(
                combo.view().palette(), group, QPalette.Text, QPalette.Base,
                minimum=4.5,
            )
            _assert_palette_pair(
                combo.view().palette(), group,
                QPalette.HighlightedText, QPalette.Highlight,
                minimum=3.0,
            )
        _assert_palette_pair(
            combo.palette(), QPalette.Disabled,
            QPalette.ButtonText, QPalette.Button,
            minimum=3.0,
        )

        combo.setFocus()
        combo.setCurrentIndex(0)
        combo.showPopup()
        qtbot.wait(10)
        popup = combo.view()
        for row in range(combo.count()):
            rect = popup.visualRect(combo.model().index(row, 0))
            assert rect.isValid() and rect.intersects(popup.viewport().rect())
        declared_pass_rect = popup.visualRect(combo.model().index(1, 0))
        qtbot.mouseClick(popup.viewport(), Qt.LeftButton, pos=declared_pass_rect.center())
        assert combo.currentText() == "declared_pass"
        qtbot.keyClick(combo, Qt.Key_Down)
        assert combo.currentText() == "declared_unavailable"
        wheel = QWheelEvent(
            QPointF(combo.rect().center()),
            QPointF(combo.mapToGlobal(combo.rect().center())),
            QPoint(), QPoint(0, -120), Qt.NoButton, Qt.NoModifier,
            Qt.ScrollUpdate, False,
        )
        QApplication.sendEvent(combo, wheel)
        assert combo.currentText() == "declared_fail"
        _assert_palette_pair(
            combo.palette(), QPalette.Active,
            QPalette.ButtonText, QPalette.Button,
            minimum=4.5,
        )

        table = window.plan_page.condition_table
        item = table.item(0, 0)
        table.scrollToItem(item)
        table.setCurrentItem(item)
        table.editItem(item)
        qtbot.wait(20)
        editor = table.findChild(QLineEdit)
        assert editor is not None and editor.isVisible()
        for group in (QPalette.Active, QPalette.Inactive):
            _assert_palette_pair(
                editor.palette(), group, QPalette.Text, QPalette.Base,
                minimum=4.5,
            )
            _assert_palette_pair(
                editor.palette(), group,
                QPalette.HighlightedText, QPalette.Highlight,
                minimum=3.0,
            )
        _assert_palette_pair(
            editor.palette(), QPalette.Disabled,
            QPalette.Text, QPalette.Base,
            minimum=3.0,
        )
    finally:
        application.setStyle(original_style)
        application.setPalette(original_palette)

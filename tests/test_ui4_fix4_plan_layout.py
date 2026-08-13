from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QAbstractItemView

from acoustic_encoder.ui.main_window import MainWindow


@pytest.mark.parametrize(
    ("width", "height", "font_scale"),
    (
        (1280, 720, 1.00),
        (1280, 720, 1.25),
        (1920, 1080, 1.50),
    ),
)
def test_simple_plan_page_keeps_core_forms_and_tables_operable(
    qtbot, tmp_path: Path, width: int, height: int, font_scale: float,
) -> None:
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    base_font = window.font()
    scaled = QFont(base_font)
    scaled.setPointSizeF(max(8.0, base_font.pointSizeF() * font_scale))
    window.setFont(scaled)
    window.resize(width, height)
    window.show()
    window.select_step("plan")
    qtbot.wait(20)

    page = window.plan_page
    assert window.professional_panel.isHidden()
    assert page.plan_scroll_area.isVisible()
    assert page.basic_box.isVisible()
    assert all(field.isVisible() for field in page.fields.values())
    assert all(
        page.basic_box.layout().labelForField(field).isVisible()
        for field in page.fields.values()
    )
    assert page.revision_reason_edit.isVisible()

    for table in (page.condition_table, page.safety_table):
        three_rows = sum(table.rowHeight(row) for row in range(3))
        required = (
            table.horizontalHeader().height()
            + three_rows
            + table.horizontalScrollBar().sizeHint().height()
            + 2 * table.frameWidth()
        )
        assert table.minimumHeight() >= required
        assert table.horizontalScrollMode() == QAbstractItemView.ScrollPerPixel
        assert table.verticalScrollMode() == QAbstractItemView.ScrollPerPixel

    assert page.safety_table.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert page.condition_table.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert page.condition_table.horizontalScrollBar().maximum() > 0
    assert page.safety_table.verticalScrollBar().maximum() > 0
    assert page.add_block_button.isVisible()
    assert page.remove_block_button.isVisible()
    assert page.condition_table.geometry().bottom() < page.add_block_button.geometry().top()
    assert page.condition_table.geometry().bottom() < page.remove_block_button.geometry().top()
    assert page.add_block_button.geometry().bottom() < page.conditions_box.height()
    assert page.remove_block_button.geometry().bottom() < page.conditions_box.height()

    for _ in range(3):
        page.add_block_button.click()
    qtbot.wait(10)
    assert page.condition_table.rowCount() == 4
    assert page.condition_table.verticalScrollBar().maximum() > 0
    assert window.action_stack.height() > window.result_box.height()
    assert window.result_scroll_area.isVisible()

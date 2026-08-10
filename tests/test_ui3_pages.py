from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from acoustic_encoder.ui.analysis_page import BatchAnalysisPage
from acoustic_encoder.ui.experiment_plan import ChecklistStatus, ExperimentRole
from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.plan_page import ExperimentPlanPage


def _complete_plan_page(page: ExperimentPlanPage) -> None:
    page.fields["operator"].setText("Operator")
    page.fields["device_chain"].setText("Interface -> amplifier -> speaker -> microphone")
    page.fields["provenance_uri"].setText("records/provenance.json")
    timestamp = "2026-08-10T12:00:00+01:00"
    for row in range(page.safety_table.rowCount()):
        combo = page.safety_table.cellWidget(row, 1)
        combo.setCurrentIndex(combo.findData(ChecklistStatus.DECLARED_PASS.value))
        page.safety_table.item(row, 2).setText("Safety Operator")
        page.safety_table.item(row, 3).setText(timestamp)
        page.safety_table.item(row, 4).setText("Checked by operator")
        page.safety_table.item(row, 5).setText("evidence/check.txt")


def test_plan_page_builds_preview_and_saves_revision(qtbot, tmp_path: Path) -> None:
    page = ExperimentPlanPage(tmp_path)
    qtbot.addWidget(page)
    _complete_plan_page(page)

    preview = page.preview_plan()
    saved = page.save_plan(large_confirmed=True)

    assert preview.expected_sample_count == 32
    assert saved.checklist.ready_for_acquisition is True
    assert saved.directory.is_dir()
    assert page.safety_table.rowCount() == 12
    assert page.safety_table.columnCount() == 6
    assert saved.checklist.items[0].note == "Checked by operator"
    assert saved.checklist.items[0].evidence_path == "evidence/check.txt"


def test_plan_revision_reason_is_explicit_in_page(qtbot, tmp_path: Path) -> None:
    page = ExperimentPlanPage(tmp_path)
    qtbot.addWidget(page)
    _complete_plan_page(page)
    first = page.save_plan(large_confirmed=True)
    page.revision_reason_edit.setText("Add second acquisition block")
    second = page.save_plan(
        revision_reason=page.revision_reason_edit.text(), large_confirmed=True
    )

    assert first.revision == 1
    assert second.revision == 2
    assert "Add second acquisition block" in (
        second.directory / "plan_manifest.json"
    ).read_text(encoding="utf-8")


def test_main_window_routes_ui3_steps_to_real_pages(qtbot, tmp_path: Path) -> None:
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)

    window.select_step("plan")
    assert window.action_stack.currentWidget() is window.plan_page
    window.select_step("dataset")
    assert window.action_stack.currentWidget() is window.dataset_page
    window.select_step("comparison")
    assert window.action_stack.currentWidget() is window.analysis_page
    window.select_step("modeling")
    assert window.action_stack.currentWidget() is window.analysis_page


def test_capability_page_shows_p3c_unavailable_and_hard_blocks(qtbot, tmp_path: Path) -> None:
    page = BatchAnalysisPage(tmp_path)
    qtbot.addWidget(page)
    rows = {
        page.capability_table.item(row, 0).text(): page.capability_table.item(row, 7).text()
        for row in range(page.capability_table.rowCount())
    }

    assert "unavailable" in rows["P3_C"]
    assert "validation" in rows["P3_C"]
    assert "final-test" in page.block_banner.text()
    assert "真实 Multisine/P8" in page.block_banner.text()
    assert page.prepare_button.isEnabled() is False


def test_batch_page_distinguishes_not_applicable_from_failure(qtbot, tmp_path: Path) -> None:
    page = BatchAnalysisPage(tmp_path)
    qtbot.addWidget(page)
    p2b = tmp_path / "p2b"
    p2b.mkdir()
    page.set_plan_modes(("rew_sweep",))
    page.set_p2b_ready(True, p2b)

    page.stage_combo.setCurrentIndex(page.stage_combo.findData("P6_B"))
    assert "本计划不适用" in page.status_label.text()
    assert page.prepare_button.isEnabled() is False

    page.stage_combo.setCurrentIndex(page.stage_combo.findData("P6_A"))
    assert "本计划不适用" not in page.status_label.text()
    assert page.prepare_button.isEnabled() is True


def test_dataset_table_exposes_required_audit_columns(qtbot, tmp_path: Path) -> None:
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    headers = {
        window.dataset_page.sample_table.horizontalHeaderItem(column).text()
        for column in range(window.dataset_page.sample_table.columnCount())
    }
    assert {"manual review", "FeatureSet", "SpectrumData"} <= headers
    assert window.dataset_page.open_p2b_output_button.isEnabled() is False
    assert window.dataset_page.view_p2b_report_button.isEnabled() is False


def test_final_test_rows_are_label_sealed_in_dataset_page(qtbot, tmp_path: Path) -> None:
    page = ExperimentPlanPage(tmp_path)
    qtbot.addWidget(page)
    _complete_plan_page(page)
    page.condition_table.item(0, 6).setText(ExperimentRole.FINAL_TEST_SEALED.value)
    saved = page.save_plan(large_confirmed=True)
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    window.dataset_page.load_plan_revision(saved.directory)

    assert window.dataset_page.sample_table.item(0, 4).text() == "sealed"
    assert window.dataset_page.sample_table.item(0, 5).text() == "sealed"
    assert window.dataset_page.sample_table.item(0, 15).text() == "final_test_sealed"


def test_simple_professional_mode_still_controls_technical_panel(qtbot, tmp_path: Path) -> None:
    window = MainWindow(tmp_path)
    qtbot.addWidget(window)
    assert window.professional_panel.isHidden()
    window.mode_combo.setCurrentIndex(1)
    assert window.professional_panel.isHidden() is False

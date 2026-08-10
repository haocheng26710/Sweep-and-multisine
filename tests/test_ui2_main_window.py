from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit

from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.measurement_workflow import (
    REAL_MULTISINE_BLOCK_MESSAGE,
    UsageRoute,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _window(qtbot) -> MainWindow:
    window = MainWindow(PROJECT_ROOT)
    qtbot.addWidget(window)
    window.show()
    return window


def test_ui2_single_measurement_page_has_three_routes_and_persistent_origin_banner(
    qtbot,
) -> None:
    window = _window(qtbot)

    assert window.usage_route_combo.count() == 3
    assert window.usage_route_combo.currentData() == UsageRoute.SIMULATED_PRACTICE.value
    assert "simulated" in window.origin_banner.text()
    assert "科研结论" in window.origin_banner.text()
    window.select_step("single_measurement")
    assert window.action_stack.currentWidget() is window.single_measurement_page
    assert window.preflight_single_button.isEnabled()
    assert window.run_single_button.isEnabled() is False


def test_route_change_clears_incompatible_metadata_and_external_identity_is_locked(
    qtbot,
) -> None:
    window = _window(qtbot)
    window.metadata_fields["device_version"].setText("V2")
    window.metadata_fields["session_id"].setText("S01")

    window.set_usage_route(UsageRoute.OFFICIAL_REFERENCE, force=True)

    assert window.metadata_fields["device_version"].text() == ""
    assert window.metadata_fields["session_id"].text() == ""
    identity_fields = {
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
    assert all(
        isinstance(window.metadata_fields[name], QLineEdit)
        and not window.metadata_fields[name].isEnabled()
        for name in identity_fields
    )
    assert window.measurement_mode_combo.currentData() == "rew_sweep"
    assert "external_reference" in window.origin_banner.text()
    assert "parser_fixture" in window.origin_banner.text()


def test_real_multisine_can_be_registered_but_run_button_is_hard_blocked(qtbot) -> None:
    window = _window(qtbot)

    window.set_usage_route(UsageRoute.REAL_DIAGNOSTIC, force=True)
    index = window.measurement_mode_combo.findData("schroeder_multisine")
    window.measurement_mode_combo.setCurrentIndex(index)
    window.select_step("single_measurement")

    assert window.save_metadata_button.isEnabled() is False
    assert window.run_single_button.isEnabled() is False
    assert window.single_hard_block_label.text() == REAL_MULTISINE_BLOCK_MESSAGE
    assert window.real_multisine_run_button.isEnabled() is False
    assert window.findChild(QLineEdit, "eligibleForScientificAnalysisEditor") is None


def test_ui2_import_controls_expose_paths_ids_reports_and_cancel(qtbot) -> None:
    window = _window(qtbot)

    assert window.source_path_edit.isReadOnly()
    assert window.manifest_path_edit.isReadOnly()
    assert window.sample_id_edit.isReadOnly()
    assert window.run_id_edit.isReadOnly()
    assert window.open_single_output_button.isEnabled() is False
    assert window.view_single_report_button.isEnabled() is False
    assert window.cancel_single_button.isEnabled() is False
    assert window.new_revision_button.isEnabled() is False
    window.sample_id_edit.setText("stable-sample-id")
    qtbot.mouseClick(window.copy_sample_id_button, Qt.LeftButton)
    assert QApplication.clipboard().text() == "stable-sample-id"

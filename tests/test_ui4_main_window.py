from __future__ import annotations

from pathlib import Path

from acoustic_encoder.ui.main_window import MainWindow


def test_ui4_pages_expose_p9_freeze_offline_and_sealed_final_test(qtbot, tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    window = MainWindow(project_root, workspace_root=tmp_path / "中文 工作区")
    qtbot.addWidget(window)

    window.select_step("modeling")
    assert window.final_delivery_page.p9a_button.text()
    assert window.final_delivery_page.p9b_button.text()
    assert window.final_delivery_page.p9c_button.text()

    window.select_step("freeze")
    assert window.final_delivery_page.freeze_button.text()

    window.select_step("final_test")
    assert window.final_delivery_page.final_test_state_label.text().endswith("sealed")
    assert window.final_delivery_page.unseal_button.isEnabled() is False

    window.select_step("reports")
    assert window.final_delivery_page.offline_button.text()
    assert str(tmp_path / "中文 工作区") in window.workspace_label.text()


def test_previous_next_navigation_and_about_are_available(qtbot, tmp_path: Path) -> None:
    window = MainWindow(Path(__file__).resolve().parents[1], workspace_root=tmp_path)
    qtbot.addWidget(window)
    window.select_step("usage")

    window.next_button.click()
    assert window._current_step_id == "plan"
    window.previous_button.click()
    assert window._current_step_id == "usage"
    assert window.about_button.text()
    assert window.minimumWidth() >= 1000

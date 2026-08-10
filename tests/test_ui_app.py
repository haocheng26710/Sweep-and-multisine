from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from acoustic_encoder.ui.app import create_main_window
from acoustic_encoder.ui.main_window import MainWindow


def test_create_main_window_minimal_smoke(qtbot) -> None:
    project_root = Path(__file__).resolve().parents[1]

    window = create_main_window(project_root)
    qtbot.addWidget(window)
    window.show()

    assert isinstance(window, MainWindow)
    assert QApplication.instance() is not None
    assert window.isVisible()

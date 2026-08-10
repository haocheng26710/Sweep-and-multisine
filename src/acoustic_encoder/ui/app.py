"""Desktop application construction and event-loop entry points."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from acoustic_encoder.ui.main_window import MainWindow


def create_main_window(project_root: str | Path) -> MainWindow:
    if QApplication.instance() is None:
        raise RuntimeError("QApplication must exist before creating MainWindow")
    return MainWindow(Path(project_root).resolve())


def run_desktop(
    project_root: str | Path,
    *,
    smoke_test: bool = False,
) -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Acoustic Encoder Analysis")
    window = create_main_window(project_root)
    window.show()
    if smoke_test:
        QTimer.singleShot(250, window.close)
    return application.exec()

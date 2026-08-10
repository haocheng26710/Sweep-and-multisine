"""Desktop application construction and event-loop entry points."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.runtime import RuntimeContext


def create_main_window(
    project_root: str | Path,
    *,
    workspace_root: str | Path | None = None,
    runtime_context: RuntimeContext | None = None,
) -> MainWindow:
    if QApplication.instance() is None:
        raise RuntimeError("QApplication must exist before creating MainWindow")
    return MainWindow(
        Path(project_root).resolve(),
        workspace_root=workspace_root,
        runtime_context=runtime_context,
    )


def run_desktop(
    project_root: str | Path,
    *,
    workspace_root: str | Path | None = None,
    smoke_test: bool = False,
) -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Acoustic Encoder Analysis")
    runtime = RuntimeContext.discover(
        project_root=project_root,
        workspace_root=workspace_root,
    )
    window = create_main_window(
        runtime.resource_root,
        workspace_root=runtime.workspace_root,
        runtime_context=runtime,
    )
    window.show()
    if smoke_test:
        QTimer.singleShot(250, window.close)
    return application.exec()

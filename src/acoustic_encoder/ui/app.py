"""Desktop application construction and event-loop entry points."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.runtime import RuntimeContext, WorkspaceAccessError


def apply_readable_application_style(application: QApplication) -> str:
    """Avoid the Windows 11 Qt editor palette that renders black on black."""
    current_style = application.style().objectName().casefold()
    if sys.platform == "win32" and current_style == "windows11":
        application.setStyle("Fusion")
        palette = application.palette()
        normal_roles = {
            QPalette.Window: "#f3f3f3",
            QPalette.WindowText: "#202020",
            QPalette.Base: "#ffffff",
            QPalette.AlternateBase: "#f5f5f5",
            QPalette.Text: "#202020",
            QPalette.Button: "#f0f0f0",
            QPalette.ButtonText: "#202020",
            QPalette.Highlight: "#0067c0",
            QPalette.HighlightedText: "#ffffff",
            QPalette.ToolTipBase: "#ffffdc",
            QPalette.ToolTipText: "#202020",
        }
        for group in (QPalette.Active, QPalette.Inactive):
            for role, color in normal_roles.items():
                palette.setColor(group, role, QColor(color))
        disabled_roles = {
            QPalette.Window: "#f3f3f3",
            QPalette.WindowText: "#595959",
            QPalette.Base: "#f7f7f7",
            QPalette.AlternateBase: "#eeeeee",
            QPalette.Text: "#595959",
            QPalette.Button: "#e5e5e5",
            QPalette.ButtonText: "#595959",
            QPalette.Highlight: "#5a6673",
            QPalette.HighlightedText: "#ffffff",
            QPalette.ToolTipBase: "#ffffdc",
            QPalette.ToolTipText: "#595959",
        }
        for role, color in disabled_roles.items():
            palette.setColor(QPalette.Disabled, role, QColor(color))
        application.setPalette(palette)
    return application.style().objectName()


def create_main_window(
    project_root: str | Path,
    *,
    workspace_root: str | Path | None = None,
    runtime_context: RuntimeContext | None = None,
) -> MainWindow:
    if QApplication.instance() is None:
        raise RuntimeError("QApplication must exist before creating MainWindow")
    apply_readable_application_style(QApplication.instance())
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
    try:
        runtime = RuntimeContext.discover(
            project_root=project_root,
            workspace_root=workspace_root,
        )
    except WorkspaceAccessError as exc:
        QMessageBox.critical(None, "工作区不可用", str(exc))
        return 2
    window = create_main_window(
        runtime.resource_root,
        workspace_root=runtime.workspace_root,
        runtime_context=runtime,
    )
    window.show()
    if smoke_test:
        # Exercise the same read-only environment check as the visible button.
        QTimer.singleShot(0, window.environment_button.click)
        QTimer.singleShot(750, window.close)
    return application.exec()

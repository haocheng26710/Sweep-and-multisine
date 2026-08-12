from __future__ import annotations

from pathlib import Path
import sys

import pytest

from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.runtime import (
    RuntimeContext,
    WorkspaceAccessError,
    WorkspaceSelectionStore,
    resolve_workspace,
)


def test_workspace_priority_is_cli_then_saved_then_localappdata_default(
    tmp_path: Path,
) -> None:
    settings = WorkspaceSelectionStore(tmp_path / "settings.json")
    saved = tmp_path / "保存 工作区"
    explicit = tmp_path / "命令行 工作区"
    local_app_data = tmp_path / "Local App Data"
    settings.save(saved)

    cli_resolution = resolve_workspace(
        explicit_workspace=explicit,
        store=settings,
        local_app_data=local_app_data,
    )
    saved_resolution = resolve_workspace(
        explicit_workspace=None,
        store=settings,
        local_app_data=local_app_data,
    )
    settings.clear()
    default_resolution = resolve_workspace(
        explicit_workspace=None,
        store=settings,
        local_app_data=local_app_data,
    )

    assert cli_resolution.path == explicit.resolve()
    assert cli_resolution.source == "command_line"
    assert saved_resolution.path == saved.resolve()
    assert saved_resolution.source == "saved"
    assert default_resolution.path == (
        local_app_data / "SweepMultisineUI" / "workspace"
    ).resolve()
    assert default_resolution.source == "default"


def test_change_workspace_button_is_available_in_simple_and_professional_modes(
    qtbot,
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    window = MainWindow(project_root, workspace_root=tmp_path / "active")
    qtbot.addWidget(window)

    assert window.change_workspace_button.text() == "更换工作区"
    assert window.change_workspace_button.isVisibleTo(window)

    window.mode_combo.setCurrentIndex(1)
    assert window.change_workspace_button.isVisibleTo(window)


def test_selected_workspace_is_persisted_for_restart_without_rebinding_live_services(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    current = tmp_path / "current"
    selected = tmp_path / "新 工作区 中文"
    selected.mkdir()
    settings = tmp_path / "settings.json"
    runtime = RuntimeContext(
        project_root,
        current.resolve(),
        False,
        project_root / "scripts/run_gui.py",
        "command_line",
        settings,
    )
    current.mkdir()
    window = MainWindow(project_root, runtime_context=runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(selected),
    )
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QMessageBox.information",
        lambda *args, **kwargs: None,
    )

    window.change_workspace_button.click()

    assert WorkspaceSelectionStore(settings).load() == selected.resolve()
    assert window.workspace_root == current.resolve()
    assert window.services.workspace_root == current.resolve()
    assert str(current.resolve()) in window.workspace_label.text()
    assert "下次启动生效" in window.pending_workspace_label.text()
    assert str(selected.resolve()) in window.pending_workspace_label.toolTip()
    assert window.restart_workspace_button.isEnabled()


def test_cancel_workspace_selection_keeps_current_workspace(qtbot, tmp_path: Path, monkeypatch) -> None:
    project_root = Path(__file__).resolve().parents[1]
    current = tmp_path / "current"
    settings = tmp_path / "settings.json"
    runtime = RuntimeContext(
        project_root,
        current.resolve(),
        False,
        project_root / "scripts/run_gui.py",
        "command_line",
        settings,
    )
    current.mkdir()
    window = MainWindow(project_root, runtime_context=runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: "",
    )

    window.change_workspace_button.click()

    assert window.workspace_root == current.resolve()
    assert WorkspaceSelectionStore(settings).load() is None
    assert window.pending_workspace_label.isHidden()


def test_unwritable_workspace_is_rejected_with_human_message(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    current = tmp_path / "current"
    current.mkdir()
    invalid = tmp_path / "not-a-directory"
    invalid.write_text("existing file", encoding="utf-8")
    settings = tmp_path / "settings.json"
    runtime = RuntimeContext(
        project_root,
        current.resolve(),
        False,
        project_root / "scripts/run_gui.py",
        "command_line",
        settings,
    )
    window = MainWindow(project_root, runtime_context=runtime)
    qtbot.addWidget(window)
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(invalid),
    )
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QMessageBox.warning",
        lambda parent, title, message: messages.append((title, message)),
    )

    window.change_workspace_button.click()

    assert WorkspaceSelectionStore(settings).load() is None
    assert messages and messages[0][0] == "工作区不可用"
    assert "不能创建或写入" in messages[0][1]
    assert invalid.read_text(encoding="utf-8") == "existing file"
    with pytest.raises(WorkspaceAccessError):
        WorkspaceSelectionStore(settings).save(invalid)


def test_runtime_and_all_pages_restore_saved_workspace_but_cli_still_wins(
    qtbot,
    tmp_path: Path,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    settings_path = tmp_path / "settings.json"
    saved = tmp_path / "保存 工作区"
    explicit = tmp_path / "CLI 工作区"
    WorkspaceSelectionStore(settings_path).save(saved)

    restored = RuntimeContext.discover(
        project_root=project_root,
        settings_path=settings_path,
        local_app_data=tmp_path / "local",
    )
    overridden = RuntimeContext.discover(
        project_root=project_root,
        workspace_root=explicit,
        settings_path=settings_path,
        local_app_data=tmp_path / "local",
    )
    window = MainWindow(project_root, runtime_context=restored)
    qtbot.addWidget(window)

    assert restored.workspace_root == saved.resolve()
    assert restored.workspace_source == "saved"
    assert overridden.workspace_root == explicit.resolve()
    assert overridden.workspace_source == "command_line"
    assert WorkspaceSelectionStore(settings_path).load() == saved.resolve()
    assert window.workspace_root == saved.resolve()
    assert window.services.workspace_root == saved.resolve()
    assert window.plan_page.workspace_root == saved.resolve()
    assert window.dataset_page.workspace_root == saved.resolve()
    assert window.analysis_page.workspace_root == saved.resolve()
    assert window.final_delivery_page.runtime.workspace_root == saved.resolve()
    assert window.acceptance_worker.runtime_context.workspace_root == saved.resolve()
    assert window.single_worker.runtime_context.workspace_root == saved.resolve()


def test_running_task_blocks_workspace_switch(qtbot, tmp_path: Path, monkeypatch) -> None:
    project_root = Path(__file__).resolve().parents[1]
    current = tmp_path / "current"
    selected = tmp_path / "selected"
    settings = tmp_path / "settings.json"
    current.mkdir()
    selected.mkdir()
    runtime = RuntimeContext(
        project_root,
        current.resolve(),
        False,
        project_root / "scripts/run_gui.py",
        "command_line",
        settings,
    )
    window = MainWindow(project_root, runtime_context=runtime)
    qtbot.addWidget(window)
    directory_dialog_opened = False
    warnings: list[str] = []

    def choose_directory(*args, **kwargs) -> str:
        nonlocal directory_dialog_opened
        directory_dialog_opened = True
        return str(selected)

    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QFileDialog.getExistingDirectory",
        choose_directory,
    )
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QMessageBox.warning",
        lambda parent, title, message: warnings.append(message),
    )
    window.final_delivery_page.worker.start(
        sys.executable,
        ["-c", "import time; time.sleep(10)"],
        working_directory=current,
    )
    qtbot.waitUntil(lambda: window.final_delivery_page.worker.is_running, timeout=3000)

    window.change_workspace_button.click()

    assert not directory_dialog_opened
    assert warnings and "任务正在运行" in warnings[0]
    assert WorkspaceSelectionStore(settings).load() is None
    window.final_delivery_page.worker.cancel()
    qtbot.waitUntil(lambda: not window.final_delivery_page.worker.is_running, timeout=3000)


def test_immediate_restart_passes_selected_workspace_without_touching_old_data(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    current = tmp_path / "旧 工作区"
    selected = tmp_path / "新 工作区"
    current.mkdir()
    selected.mkdir()
    sentinel = current / "existing-result.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    runtime = RuntimeContext(
        project_root,
        current.resolve(),
        False,
        project_root / "scripts/run_gui.py",
        "command_line",
        tmp_path / "settings.json",
    )
    window = MainWindow(project_root, runtime_context=runtime)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(selected),
    )
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QMessageBox.information",
        lambda *args, **kwargs: None,
    )
    detached: list[tuple[str, list[str], str]] = []
    monkeypatch.setattr(
        "acoustic_encoder.ui.main_window.QProcess.startDetached",
        lambda program, arguments, cwd: detached.append((program, arguments, cwd)) or True,
    )
    window.change_workspace_button.click()

    window.restart_workspace_button.click()

    assert len(detached) == 1
    program, arguments, working_directory = detached[0]
    assert program == sys.executable
    assert arguments == [
        str(project_root / "scripts/run_gui.py"),
        "--workspace",
        str(selected.resolve()),
    ]
    assert working_directory == str(selected.resolve())
    assert sentinel.read_text(encoding="utf-8") == "keep me"

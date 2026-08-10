from __future__ import annotations

from pathlib import Path
import sys

import pytest
from PySide6.QtCore import QTimer

from acoustic_encoder.ui.workers import (
    AcceptanceWorker,
    ProcessOutcome,
    ProcessTask,
)


def test_process_task_runs_without_blocking_qt_event_loop(qtbot) -> None:
    task = ProcessTask()
    observed: list[str] = []
    task.stdout_received.connect(observed.append)
    event_loop_progressed: list[bool] = []

    with qtbot.waitSignal(task.finished, timeout=5000) as blocker:
        task.start(
            sys.executable,
            [
                "-c",
                "import time; print('started', flush=True); "
                "time.sleep(0.2); print('done', flush=True)",
            ],
        )
        QTimer.singleShot(20, lambda: event_loop_progressed.append(True))

    result = blocker.args[0]
    assert event_loop_progressed == [True]
    assert result.outcome is ProcessOutcome.SUCCEEDED
    assert result.exit_code == 0
    assert "started" in "".join(observed)
    assert "done" in result.stdout


def test_process_task_reports_failure_and_preserves_stderr(qtbot) -> None:
    task = ProcessTask()

    with qtbot.waitSignal(task.finished, timeout=5000) as blocker:
        task.start(
            sys.executable,
            ["-c", "import sys; print('bad config', file=sys.stderr); sys.exit(7)"],
        )

    result = blocker.args[0]
    assert result.outcome is ProcessOutcome.FAILED
    assert result.exit_code == 7
    assert "bad config" in result.stderr


def test_process_task_cancel_is_recorded_as_cancelled(qtbot) -> None:
    task = ProcessTask()

    with qtbot.waitSignal(task.started, timeout=2000):
        task.start(sys.executable, ["-c", "import time; time.sleep(30)"])
    with qtbot.waitSignal(task.finished, timeout=5000) as blocker:
        task.cancel()

    assert blocker.args[0].outcome is ProcessOutcome.CANCELLED


def test_acceptance_worker_uses_separate_program_arguments_and_refuses_run_id_reuse(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project with spaces"
    script = project / "scripts/run_pre_experiment_acceptance.py"
    config = project / "config/validation_dev_c16_acceptance.yaml"
    script.parent.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    config.write_text("", encoding="utf-8")
    output_root = project / "outputs"
    existing = output_root / "simulated/software_validation/reused"
    existing.mkdir(parents=True)
    worker = AcceptanceWorker(project, output_root=output_root)

    with pytest.raises(FileExistsError, match="reused"):
        worker.prepare("reused")

    invocation = worker.prepare("new-run")
    assert invocation.program == sys.executable
    assert invocation.arguments[0] == str(script)
    assert invocation.arguments[-2:] == ["--run-id", "new-run"]
    assert invocation.output_directory == (
        output_root / "simulated/software_validation/new-run/acceptance"
    )


def test_acceptance_run_ids_are_unique_and_filesystem_safe(tmp_path: Path) -> None:
    worker = AcceptanceWorker(tmp_path)

    first = worker.create_run_id()
    second = worker.create_run_id()

    assert first != second
    assert first.startswith("u1-")
    assert len(first) <= 15
    assert all(character.isalnum() or character in "-_" for character in first)

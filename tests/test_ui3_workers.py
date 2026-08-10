from __future__ import annotations

from pathlib import Path
import sys

import pytest

pytest.importorskip("PySide6")

from acoustic_encoder.ui.batch_workflow import BatchStage, PreparedBatchInvocation
from acoustic_encoder.ui.workers import BatchStageWorker, ProcessOutcome


def _invocation(tmp_path: Path, *, exit_code: int = 0) -> PreparedBatchInvocation:
    preview = tmp_path / "preview"
    preview.mkdir()
    scope = preview / "scope.json"
    inputs = preview / "inputs.json"
    scope.write_text("{}", encoding="utf-8")
    inputs.write_text("{}", encoding="utf-8")
    return PreparedBatchInvocation(
        stage=BatchStage.P2_B,
        run_id="ui3-worker",
        program=sys.executable,
        arguments=("-c", f"import sys; print('batch log'); sys.exit({exit_code})"),
        preview_directory=preview,
        output_directory=tmp_path / "output",
        scope_path=scope,
        input_manifest_path=inputs,
    )


def test_batch_worker_runs_asynchronously(qtbot, tmp_path: Path) -> None:
    worker = BatchStageWorker()
    invocation = _invocation(tmp_path)
    results = []
    worker.finished.connect(lambda *items: results.append(items))

    worker.start(invocation)
    assert worker.is_running is True
    qtbot.waitUntil(lambda: bool(results), timeout=5000)

    assert results[0][0] == "ui3-worker"
    assert results[0][1].outcome is ProcessOutcome.SUCCEEDED
    assert "batch log" in results[0][1].stdout


def test_batch_worker_rejects_parallel_start_and_can_cancel(qtbot, tmp_path: Path) -> None:
    base = _invocation(tmp_path)
    invocation = PreparedBatchInvocation(
        **{
            **{name: getattr(base, name) for name in PreparedBatchInvocation.__dataclass_fields__},
            "arguments": ("-c", "import time; time.sleep(10)"),
        }
    )
    worker = BatchStageWorker()
    results = []
    worker.finished.connect(lambda *items: results.append(items))
    worker.start(invocation)
    with pytest.raises(RuntimeError, match="already running"):
        worker.start(invocation)
    worker.cancel()
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert results[0][1].outcome is ProcessOutcome.CANCELLED

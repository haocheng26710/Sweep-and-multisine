"""Qt process workers for long-running, cancellable validation tasks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
import uuid

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from acoustic_encoder.schemas import MeasurementMode
from acoustic_encoder.ui.batch_workflow import PreparedBatchInvocation
from acoustic_encoder.ui.measurement_workflow import (
    REAL_MULTISINE_BLOCK_MESSAGE,
    SavedMeasurementDraft,
    UsageRoute,
    verify_saved_input_hashes,
)


class ProcessOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SingleMeasurementStatus(str, Enum):
    COMPLETED = "completed"
    WARNING = "warning"
    MANUAL_REVIEW = "manual_review"
    BLOCKED_RESEARCH_GATE = "blocked_research_gate"
    FAILED = "failed"
    CANCELLED = "cancelled"


def map_single_measurement_status(
    outcome: ProcessOutcome, exit_code: int
) -> SingleMeasurementStatus:
    if outcome is ProcessOutcome.CANCELLED:
        return SingleMeasurementStatus.CANCELLED
    return {
        0: SingleMeasurementStatus.COMPLETED,
        2: SingleMeasurementStatus.MANUAL_REVIEW,
        3: SingleMeasurementStatus.BLOCKED_RESEARCH_GATE,
        4: SingleMeasurementStatus.WARNING,
    }.get(exit_code, SingleMeasurementStatus.FAILED)


@dataclass(frozen=True, slots=True)
class ProcessResult:
    outcome: ProcessOutcome
    exit_code: int
    stdout: str
    stderr: str
    program: str
    arguments: tuple[str, ...]


class ProcessTask(QObject):
    """Execute a program asynchronously without shell command construction."""

    started = Signal()
    stdout_received = Signal(str)
    stderr_received = Signal(str)
    finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)
        self._process.started.connect(self.started)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._stdout: list[str] = []
        self._stderr: list[str] = []
        self._program = ""
        self._arguments: tuple[str, ...] = ()
        self._cancel_requested = False
        self._reported = False

    @property
    def is_running(self) -> bool:
        return self._process.state() is not QProcess.NotRunning

    @property
    def program(self) -> str:
        return self._program

    @property
    def arguments(self) -> tuple[str, ...]:
        return self._arguments

    def start(
        self,
        program: str,
        arguments: list[str] | tuple[str, ...],
        *,
        working_directory: str | Path | None = None,
    ) -> None:
        if self.is_running:
            raise RuntimeError("a process task is already running")
        self._stdout.clear()
        self._stderr.clear()
        self._program = str(program)
        self._arguments = tuple(str(item) for item in arguments)
        self._cancel_requested = False
        self._reported = False
        if working_directory is not None:
            self._process.setWorkingDirectory(str(Path(working_directory)))
        self._process.start(self._program, list(self._arguments))

    def cancel(self) -> None:
        if not self.is_running:
            return
        self._cancel_requested = True
        self._process.terminate()
        QTimer.singleShot(2000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.is_running:
            self._process.kill()

    def _read_stdout(self) -> None:
        text = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if text:
            self._stdout.append(text)
            self.stdout_received.emit(text)

    def _read_stderr(self) -> None:
        text = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        if text:
            self._stderr.append(text)
            self.stderr_received.emit(text)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error is QProcess.FailedToStart and not self._reported:
            self._stderr.append(self._process.errorString())
            self._emit_result(ProcessOutcome.FAILED, -1)

    def _on_finished(
        self, exit_code: int, exit_status: QProcess.ExitStatus
    ) -> None:
        del exit_status
        self._read_stdout()
        self._read_stderr()
        if self._cancel_requested:
            outcome = ProcessOutcome.CANCELLED
        elif exit_code == 0:
            outcome = ProcessOutcome.SUCCEEDED
        else:
            outcome = ProcessOutcome.FAILED
        self._emit_result(outcome, exit_code)

    def _emit_result(self, outcome: ProcessOutcome, exit_code: int) -> None:
        if self._reported:
            return
        self._reported = True
        self.finished.emit(
            ProcessResult(
                outcome=outcome,
                exit_code=exit_code,
                stdout="".join(self._stdout),
                stderr="".join(self._stderr),
                program=self._program,
                arguments=self._arguments,
            )
        )


@dataclass(frozen=True, slots=True)
class AcceptanceInvocation:
    run_id: str
    program: str
    arguments: list[str]
    output_directory: Path


class AcceptanceWorker(QObject):
    """Prepare and run the existing DEV-C16 acceptance CLI."""

    started = Signal(str, object)
    stdout_received = Signal(str)
    stderr_received = Signal(str)
    finished = Signal(str, object, object)

    def __init__(
        self,
        project_root: str | Path,
        *,
        output_root: str | Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()
        self.output_root = (
            self.project_root / "outputs"
            if output_root is None
            else Path(output_root).resolve()
        )
        self.task = ProcessTask(self)
        self.task.stdout_received.connect(self.stdout_received)
        self.task.stderr_received.connect(self.stderr_received)
        self.task.finished.connect(self._on_finished)
        self._active: AcceptanceInvocation | None = None

    @property
    def is_running(self) -> bool:
        return self.task.is_running

    def create_run_id(self) -> str:
        # Keep the identifier short because the existing DEV-C16 E2E chain
        # creates deeply nested Windows paths.  48 random bits plus the
        # no-overwrite check provide uniqueness without approaching MAX_PATH.
        while True:
            candidate = f"u1-{uuid.uuid4().hex[:12]}"
            run_root = (
                self.output_root / "simulated/software_validation" / candidate
            )
            if not run_root.exists():
                return candidate

    def prepare(self, run_id: str | None = None) -> AcceptanceInvocation:
        selected = run_id or self.create_run_id()
        if not selected or any(
            not (character.isalnum() or character in "-_") for character in selected
        ):
            raise ValueError("run-id must be non-empty and filesystem safe")
        run_root = self.output_root / "simulated/software_validation" / selected
        if run_root.exists():
            raise FileExistsError(f"acceptance run-id already exists: {selected}")
        script = self.project_root / "scripts/run_pre_experiment_acceptance.py"
        config = self.project_root / "config/validation_dev_c16_acceptance.yaml"
        arguments = [
            str(script),
            "--project-root",
            str(self.project_root),
            "--config",
            str(config),
            "--output-root",
            str(self.output_root),
            "--run-id",
            selected,
        ]
        return AcceptanceInvocation(
            run_id=selected,
            program=sys.executable,
            arguments=arguments,
            output_directory=run_root / "acceptance",
        )

    def start(self, run_id: str | None = None) -> AcceptanceInvocation:
        if self.is_running:
            raise RuntimeError("acceptance is already running")
        invocation = self.prepare(run_id)
        self._active = invocation
        self.task.start(
            invocation.program,
            invocation.arguments,
            working_directory=self.project_root,
        )
        self.started.emit(invocation.run_id, invocation)
        return invocation

    def cancel(self) -> None:
        self.task.cancel()

    def _on_finished(self, result: ProcessResult) -> None:
        invocation = self._active
        if invocation is None:
            return
        self._active = None
        self.finished.emit(invocation.run_id, result, invocation)


@dataclass(frozen=True, slots=True)
class SingleMeasurementInvocation:
    run_id: str
    program: str
    arguments: tuple[str, ...]
    output_directory: Path
    session_directory: Path


class SingleMeasurementWorker(QObject):
    """Run the existing mode-specific pipeline CLI through QProcess."""

    started = Signal(str, object)
    stdout_received = Signal(str)
    stderr_received = Signal(str)
    finished = Signal(str, object, object, object)

    def __init__(
        self,
        project_root: str | Path,
        *,
        output_root: str | Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()
        self.output_root = (
            self.project_root / "outputs"
            if output_root is None
            else Path(output_root).resolve()
        )
        self.task = ProcessTask(self)
        self.task.stdout_received.connect(self.stdout_received)
        self.task.stderr_received.connect(self.stderr_received)
        self.task.finished.connect(self._on_finished)
        self._active: SingleMeasurementInvocation | None = None

    @property
    def is_running(self) -> bool:
        return self.task.is_running

    def prepare(self, saved: SavedMeasurementDraft) -> SingleMeasurementInvocation:
        draft = saved.draft
        mode = saved.metadata.measurement_mode
        if (
            draft.route is UsageRoute.REAL_DIAGNOSTIC
            and mode is MeasurementMode.SCHROEDER_MULTISINE
        ):
            raise PermissionError(REAL_MULTISINE_BLOCK_MESSAGE)
        output = (
            self.output_root
            / saved.metadata.data_origin.value
            / draft.run_purpose
            / draft.run_id
        ).resolve()
        if output.exists():
            raise FileExistsError(f"Run output already exists: {output}")
        verify_saved_input_hashes(saved)
        script_name = (
            "run_pipeline.py"
            if mode is MeasurementMode.REW_SWEEP
            else "analyze_multisine.py"
        )
        arguments = [
            str(self.project_root / "scripts" / script_name),
            "--config",
            str(saved.config_snapshot_path),
            "--input",
            saved.metadata.source_path,
            "--metadata",
            str(saved.metadata_path),
            "--output-root",
            str(self.output_root),
            "--run-id",
            draft.run_id,
        ]
        if draft.stimulus_manifest_path is not None:
            arguments.extend(
                ["--stimulus-manifest", str(draft.stimulus_manifest_path)]
            )
        return SingleMeasurementInvocation(
            run_id=draft.run_id,
            program=sys.executable,
            arguments=tuple(arguments),
            output_directory=output,
            session_directory=saved.session_directory,
        )

    def start(self, saved: SavedMeasurementDraft) -> SingleMeasurementInvocation:
        if self.is_running:
            raise RuntimeError("a single measurement is already running")
        invocation = self.prepare(saved)
        self._active = invocation
        self.task.start(
            invocation.program,
            invocation.arguments,
            working_directory=self.project_root,
        )
        self.started.emit(invocation.run_id, invocation)
        return invocation

    def cancel(self) -> None:
        self.task.cancel()

    def _on_finished(self, result: ProcessResult) -> None:
        invocation = self._active
        if invocation is None:
            return
        self._active = None
        status = map_single_measurement_status(result.outcome, result.exit_code)
        self.finished.emit(invocation.run_id, status, result, invocation)


class BatchStageWorker(QObject):
    """Execute one already-prepared formal batch-stage invocation."""

    started = Signal(str, object)
    stdout_received = Signal(str)
    stderr_received = Signal(str)
    finished = Signal(str, object, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.task = ProcessTask(self)
        self.task.stdout_received.connect(self.stdout_received)
        self.task.stderr_received.connect(self.stderr_received)
        self.task.finished.connect(self._on_finished)
        self._active: PreparedBatchInvocation | None = None

    @property
    def is_running(self) -> bool:
        return self.task.is_running

    def start(self, invocation: PreparedBatchInvocation) -> None:
        if self.is_running:
            raise RuntimeError("a batch stage is already running")
        if invocation.output_directory.exists():
            raise FileExistsError(
                f"batch output directory already exists: {invocation.output_directory}"
            )
        self._active = invocation
        self.task.start(
            invocation.program,
            invocation.arguments,
            working_directory=invocation.preview_directory.parent,
        )
        self.started.emit(invocation.run_id, invocation)

    def cancel(self) -> None:
        self.task.cancel()

    def _on_finished(self, result: ProcessResult) -> None:
        invocation = self._active
        if invocation is None:
            return
        self._active = None
        self.finished.emit(invocation.run_id, result, invocation)

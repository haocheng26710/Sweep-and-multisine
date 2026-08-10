"""Runtime path policy shared by the source and frozen desktop applications."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """Separate immutable application resources from user-owned writable data."""

    resource_root: Path
    workspace_root: Path
    is_frozen: bool
    launcher: Path

    @property
    def output_root(self) -> Path:
        return self.workspace_root / "outputs"

    @property
    def session_root(self) -> Path:
        return self.workspace_root / "sessions"

    @classmethod
    def for_source(
        cls,
        project_root: str | Path,
        *,
        workspace_root: str | Path | None = None,
    ) -> "RuntimeContext":
        resources = Path(project_root).resolve()
        workspace = Path(workspace_root or resources).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return cls(
            resource_root=resources,
            workspace_root=workspace,
            is_frozen=False,
            launcher=resources / "scripts" / "run_gui.py",
        )

    @classmethod
    def discover(
        cls,
        *,
        project_root: str | Path | None = None,
        workspace_root: str | Path | None = None,
    ) -> "RuntimeContext":
        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            resources = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
            default_workspace = (
                Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
                / "SweepMultisineUI"
                / "workspace"
            )
            workspace = Path(workspace_root or default_workspace).resolve()
            workspace.mkdir(parents=True, exist_ok=True)
            return cls(resources, workspace, True, Path(sys.executable).resolve())
        if project_root is None:
            project_root = Path(__file__).resolve().parents[3]
        return cls.for_source(project_root, workspace_root=workspace_root)

    def worker_process(self, task: str, arguments: list[str]) -> tuple[str, tuple[str, ...]]:
        """Return program/argument vectors; never construct a shell command."""
        worker_args = ("--worker", task, "--workspace", str(self.workspace_root), "--", *arguments)
        if self.is_frozen:
            return str(self.launcher), worker_args
        return sys.executable, (str(self.launcher), *worker_args)

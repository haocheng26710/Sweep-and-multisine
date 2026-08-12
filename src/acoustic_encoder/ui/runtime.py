"""Runtime path policy shared by the source and frozen desktop applications."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from uuid import uuid4


class WorkspaceAccessError(ValueError):
    """A selected workspace cannot safely hold user-owned outputs."""


@dataclass(frozen=True, slots=True)
class WorkspaceResolution:
    path: Path
    source: str


class WorkspaceSelectionStore:
    """Persist only the user's workspace choice, outside scientific artifacts."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    def load(self) -> Path | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            value = payload.get("workspace_root")
            return Path(value).resolve() if isinstance(value, str) and value.strip() else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def save(self, workspace: str | Path) -> None:
        selected = ensure_workspace_writable(workspace)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(
                    {"schema_version": "1.0.0", "workspace_root": str(selected)},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise WorkspaceAccessError(
                f"无法保存工作区设置：{self.path}。请检查目录权限。"
            ) from exc

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def local_app_data_root(value: str | Path | None = None) -> Path:
    if value is not None:
        return Path(value).resolve()
    configured = os.environ.get("LOCALAPPDATA")
    return Path(configured).resolve() if configured else (Path.home() / "AppData/Local").resolve()


def default_workspace_settings_path(local_app_data: str | Path | None = None) -> Path:
    override = os.environ.get("SWEEP_MULTISINE_UI_SETTINGS_PATH")
    if override:
        return Path(override).resolve()
    return local_app_data_root(local_app_data) / "SweepMultisineUI" / "ui_settings.json"


def ensure_workspace_writable(workspace: str | Path) -> Path:
    """Create the target if needed and prove it can create a new file."""
    selected = Path(workspace).expanduser().resolve()
    try:
        selected.mkdir(parents=True, exist_ok=True)
        if not selected.is_dir():
            raise OSError("target is not a directory")
        probe = selected / f".workspace-write-probe-{uuid4().hex}.tmp"
        with probe.open("x", encoding="utf-8") as handle:
            handle.write("workspace write probe\n")
        probe.unlink()
    except OSError as exc:
        raise WorkspaceAccessError(
            f"无法使用工作区“{selected}”：目录不能创建或写入。请改选有写入权限的文件夹。"
        ) from exc
    return selected


def resolve_workspace(
    *,
    explicit_workspace: str | Path | None,
    store: WorkspaceSelectionStore,
    local_app_data: str | Path | None = None,
) -> WorkspaceResolution:
    """Resolve command line > saved choice > LOCALAPPDATA default."""
    if explicit_workspace is not None:
        return WorkspaceResolution(ensure_workspace_writable(explicit_workspace), "command_line")
    saved = store.load()
    if saved is not None:
        return WorkspaceResolution(ensure_workspace_writable(saved), "saved")
    default = local_app_data_root(local_app_data) / "SweepMultisineUI" / "workspace"
    return WorkspaceResolution(ensure_workspace_writable(default), "default")


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """Separate immutable application resources from user-owned writable data."""

    resource_root: Path
    workspace_root: Path
    is_frozen: bool
    launcher: Path
    workspace_source: str = "explicit"
    settings_path: Path | None = None

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
        workspace = ensure_workspace_writable(workspace_root or resources)
        return cls(
            resource_root=resources,
            workspace_root=workspace,
            is_frozen=False,
            launcher=resources / "scripts" / "run_gui.py",
            workspace_source="command_line" if workspace_root is not None else "source_default",
        )

    @classmethod
    def discover(
        cls,
        *,
        project_root: str | Path | None = None,
        workspace_root: str | Path | None = None,
        settings_path: str | Path | None = None,
        local_app_data: str | Path | None = None,
    ) -> "RuntimeContext":
        selected_settings = Path(
            settings_path or default_workspace_settings_path(local_app_data)
        ).resolve()
        resolution = resolve_workspace(
            explicit_workspace=workspace_root,
            store=WorkspaceSelectionStore(selected_settings),
            local_app_data=local_app_data,
        )
        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            resources = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
            return cls(
                resources,
                resolution.path,
                True,
                Path(sys.executable).resolve(),
                resolution.source,
                selected_settings,
            )
        if project_root is None:
            project_root = Path(__file__).resolve().parents[3]
        resources = Path(project_root).resolve()
        return cls(
            resources,
            resolution.path,
            False,
            resources / "scripts" / "run_gui.py",
            resolution.source,
            selected_settings,
        )

    def worker_process(self, task: str, arguments: list[str]) -> tuple[str, tuple[str, ...]]:
        """Return program/argument vectors; never construct a shell command."""
        worker_args = ("--worker", task, "--workspace", str(self.workspace_root), "--", *arguments)
        if self.is_frozen:
            return str(self.launcher), worker_args
        return sys.executable, (str(self.launcher), *worker_args)

    def restart_process(self, workspace: str | Path) -> tuple[str, tuple[str, ...]]:
        arguments = ("--workspace", str(Path(workspace).resolve()))
        if self.is_frozen:
            return str(self.launcher), arguments
        return sys.executable, (str(self.launcher), *arguments)

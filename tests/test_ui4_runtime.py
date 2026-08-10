from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from acoustic_encoder.ui.runtime import RuntimeContext
from acoustic_encoder.ui.workers import AcceptanceWorker


def test_source_runtime_separates_resources_from_writable_workspace(tmp_path: Path) -> None:
    project_root = tmp_path / "installed resources"
    workspace = tmp_path / "用户 工作区"
    project_root.mkdir()

    runtime = RuntimeContext.for_source(project_root, workspace_root=workspace)

    assert runtime.resource_root == project_root.resolve()
    assert runtime.workspace_root == workspace.resolve()
    assert runtime.output_root == workspace.resolve() / "outputs"
    assert runtime.session_root == workspace.resolve() / "sessions"
    assert runtime.is_frozen is False
    assert workspace.is_dir()


def test_development_worker_dispatches_without_project_working_directory(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_gui.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--worker", "p9a", "--workspace", str(tmp_path), "--", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "explicit-scope P9-A" in completed.stdout


def test_frozen_worker_reuses_executable_and_never_depends_on_external_python(tmp_path: Path) -> None:
    executable = tmp_path / "SweepMultisineUI.exe"
    runtime = RuntimeContext(tmp_path / "resources", tmp_path / "工作区", True, executable)

    program, arguments = runtime.worker_process("offline", ["--package", "C:/space path/pkg"])

    assert program == str(executable)
    assert arguments[:2] == ("--worker", "offline")
    assert "scripts/run_gui.py" not in " ".join(arguments)


def test_frozen_acceptance_invocation_uses_packaged_worker(qtbot, tmp_path: Path) -> None:
    resource = tmp_path / "resources"
    (resource / "config").mkdir(parents=True)
    (resource / "config" / "validation_dev_c16_acceptance.yaml").write_text("{}", encoding="utf-8")
    runtime = RuntimeContext(resource, tmp_path / "workspace", True, tmp_path / "SweepMultisineUI.exe")
    worker = AcceptanceWorker(resource, output_root=runtime.output_root, runtime_context=runtime)

    invocation = worker.prepare("frozen-acceptance")

    assert invocation.program.endswith("SweepMultisineUI.exe")
    assert invocation.arguments[:2] == ["--worker", "acceptance"]
    assert all(not item.endswith("run_pre_experiment_acceptance.py") for item in invocation.arguments)


def test_p9d_source_scripts_run_without_editable_install_or_project_cwd(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("build_readout_package.py", "run_offline_readout.py", "run_offline_readout_validation.py"):
        completed = subprocess.run(
            [sys.executable, str(root / "scripts" / name), "--help"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, f"{name}: {completed.stderr}"

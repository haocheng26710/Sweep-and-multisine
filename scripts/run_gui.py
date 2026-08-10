from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])).resolve()
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the guided PySide6 desktop UI")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="open the window briefly and exit; intended for controlled validation",
    )
    parser.add_argument("--workspace", help="user-writable workspace directory")
    parser.add_argument(
        "--worker",
        choices=(
            "acceptance", "pipeline_sweep", "pipeline_multisine", "p2b", "p4",
            "p5a", "p5b", "p6a", "p6b", "p9a", "p9b", "p9c", "p9d", "offline",
        ),
    )
    parser.add_argument("worker_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.worker is not None:
        from acoustic_encoder.ui.runtime import RuntimeContext
        from acoustic_encoder.ui.worker_entry import dispatch_worker

        runtime = RuntimeContext.discover(
            project_root=PROJECT_ROOT,
            workspace_root=args.workspace,
        )
        worker_args = args.worker_args
        if worker_args[:1] == ["--"]:
            worker_args = worker_args[1:]
        return dispatch_worker(
            args.worker,
            worker_args,
            resource_root=runtime.resource_root,
            workspace_root=runtime.workspace_root,
        )
    try:
        from acoustic_encoder.ui.app import run_desktop
    except (ImportError, OSError) as exc:
        print(
            "无法启动桌面界面：PySide6 或其 Qt 运行库不可用。\n"
            "请在项目环境中运行：python -m pip install -r requirements.txt\n"
            f"技术详情：{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    return run_desktop(PROJECT_ROOT, workspace_root=args.workspace, smoke_test=args.smoke_test)


if __name__ == "__main__":
    raise SystemExit(main())

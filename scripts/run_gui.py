from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the guided PySide6 desktop UI")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="open the window briefly and exit; intended for controlled validation",
    )
    args = parser.parse_args()
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
    return run_desktop(PROJECT_ROOT, smoke_test=args.smoke_test)


if __name__ == "__main__":
    raise SystemExit(main())

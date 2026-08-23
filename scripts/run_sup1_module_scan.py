"""Run the isolated SUP-1 ENC-A..H single-position module analysis."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.supplemental_module_scan import run_sup1_module_scan


def _git_state(root: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root,
        check=True, capture_output=True, text=True,
    ).stdout
    return commit, not bool(status.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run SUP-1 module QC, repeat selection, and frozen-window analysis."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--raw-directory", type=Path)
    parser.add_argument("--sup0", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    data_root = root / "data" / "exported_txt" / "SUP-1_ENC_MODULE_SCAN"
    zip_path = args.zip.resolve() if args.zip else data_root / "source" / "ENC-A-H.zip"
    raw = args.raw_directory.resolve() if args.raw_directory else data_root / "raw_txt"
    sup0 = args.sup0.resolve() if args.sup0 else (
        root / "outputs" / "supplemental" / "SUP-0_FREQUENCY_LOCALIZATION"
    )
    output = args.output.resolve() if args.output else (
        root / "outputs" / "supplemental" / "SUP-1_ENC_MODULE_SCAN"
    )
    commit, clean = _git_state(root)
    try:
        result = run_sup1_module_scan(
            zip_path, raw, sup0, output,
            source_commit=commit,
            source_worktree_clean=clean,
            created_at=datetime.now(ZoneInfo("Europe/London")),
        )
    except Exception as exc:
        print(f"SUP-1 failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"output_directory={result.output_directory}")
    print(f"measurement_count={result.measurement_count}")
    print(f"primary_measurement_count={result.primary_measurement_count}")
    print(f"extra_repeat_count={result.extra_repeat_count}")
    print(f"flagged_count={result.flagged_count}")
    print(f"candidate_window_count={result.candidate_window_count}")
    print(f"artifact_count={result.artifact_count}")
    print("classification_performed=false")
    print("SUP2_or_SUP3_performed=false")
    print("final_test_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

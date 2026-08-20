"""Run FORMAL-5 from explicit immutable FORMAL-3/4 and acquisition authorities."""

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

from acoustic_encoder.formal_final_synthesis import run_formal5_final_synthesis


DEFAULT_ACQUISITION_ROOT = Path(
    r"D:\Bristol course\dissertation\formal_experiment_data\FORMAL-U4-4DIR-SWEEP-REV001"
)


def _git_commit(project_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_root,
        check=True, capture_output=True, text=True,
    )
    return completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze FORMAL-5 conclusions from explicit FORMAL-3/4 manifests only."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--formal3", type=Path)
    parser.add_argument("--formal4", type=Path)
    parser.add_argument("--acquisition-root", type=Path, default=DEFAULT_ACQUISITION_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    formal3 = (
        args.formal3.resolve() if args.formal3 is not None
        else root / "outputs" / "formal" / "FORMAL-3_REAL_IMPORT_QC"
    )
    formal4 = (
        args.formal4.resolve() if args.formal4 is not None
        else root / "outputs" / "formal" / "FORMAL-4_CORE_ANALYSIS"
    )
    output = (
        args.output.resolve() if args.output is not None
        else root / "outputs" / "formal" / "FORMAL-5_FINAL_SYNTHESIS"
    )
    try:
        result = run_formal5_final_synthesis(
            root, formal3, formal4, args.acquisition_root.resolve(), output,
            source_commit=_git_commit(root),
            created_at=datetime.now(ZoneInfo("Europe/London")),
        )
    except Exception as exc:
        print(f"FORMAL-5 failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"output_directory={result.output_directory}")
    print(f"disposition={result.disposition}")
    print(f"artifact_count={result.artifact_count}")
    print("scientifically_eligible=false")
    print("final_test_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

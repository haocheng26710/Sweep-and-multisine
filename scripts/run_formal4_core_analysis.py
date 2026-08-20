"""Run FORMAL-4 from the immutable FORMAL-3 authority directory."""

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

from acoustic_encoder.formal_core_analysis import run_formal4_core_analysis


def _git_commit(project_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_root,
        check=True, capture_output=True, text=True,
    )
    return completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run block-aware FORMAL-4 analysis from FORMAL-3 outputs only."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--permutation-iterations", type=int, default=999)
    parser.add_argument("--random-state", type=int, default=20260820)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    input_directory = (
        args.input.resolve() if args.input is not None
        else root / "outputs" / "formal" / "FORMAL-3_REAL_IMPORT_QC"
    )
    output_directory = (
        args.output.resolve() if args.output is not None
        else root / "outputs" / "formal" / "FORMAL-4_CORE_ANALYSIS"
    )
    created_at = datetime.now(ZoneInfo("Europe/London"))
    try:
        result = run_formal4_core_analysis(
            input_directory, output_directory,
            source_commit=_git_commit(root), created_at=created_at,
            bootstrap_iterations=args.bootstrap_iterations,
            permutation_iterations=args.permutation_iterations,
            random_state=args.random_state,
        )
    except Exception as exc:
        print(f"FORMAL-4 failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"output_directory={result.output_directory}")
    print(f"active_count={result.active_count}")
    print(f"excluded_count={result.excluded_count}")
    print(f"outlier_count={result.outlier_count}")
    print(f"ready_for_formal_synthesis={str(result.ready_for_formal_synthesis).lower()}")
    print(f"artifact_count={result.artifact_count}")
    print("scientifically_eligible=false")
    print("final_test_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

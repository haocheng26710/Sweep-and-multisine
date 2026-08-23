"""Run SUP-0 frequency localization from frozen FORMAL-3/4 authorities."""

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

from acoustic_encoder.supplemental_frequency_localization import (
    run_sup0_frequency_localization,
)


def _git_state(project_root: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_root,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=project_root,
        check=True, capture_output=True, text=True,
    ).stdout
    return commit, not bool(status.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze SUP-0 candidate frequency windows without reading raw/final-test data."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--formal3", type=Path)
    parser.add_argument("--formal4", type=Path)
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
        else root / "outputs" / "supplemental" / "SUP-0_FREQUENCY_LOCALIZATION"
    )
    commit, clean = _git_state(root)
    try:
        result = run_sup0_frequency_localization(
            formal3, formal4, output,
            source_commit=commit,
            source_worktree_clean=clean,
            created_at=datetime.now(ZoneInfo("Europe/London")),
        )
    except Exception as exc:
        print(f"SUP-0 failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"output_directory={result.output_directory}")
    print(f"active_count={result.active_count}")
    print(f"excluded_count={result.excluded_count}")
    print(f"outlier_count={result.outlier_count}")
    print(f"candidate_band_count={result.candidate_band_count}")
    print(f"artifact_count={result.artifact_count}")
    print("existing_FORMAL5_disposition_changed=false")
    print("scientifically_eligible=false")
    print("final_test_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

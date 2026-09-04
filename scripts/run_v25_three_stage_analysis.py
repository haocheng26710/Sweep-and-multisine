"""Run the joint V2.5 S1/S2/S3 revised-repeat analysis."""

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

from acoustic_encoder.v25_three_stage_analysis import run_v25_joint_analysis


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
        description="Run V2.5 S1/S2/S3 selection sensitivity and direction analysis."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--permutation-iterations", type=int, default=2000)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    s1 = root / "data" / "exported_txt" / "V25-S1_SINGLE_MODULE"
    s2 = root / "data" / "exported_txt" / "V25-S2_U4SYM"
    s3 = root / "data" / "exported_txt" / "V25-S3_U4HR"
    output = args.output.resolve() if args.output else (
        root / "outputs" / "supplemental" / "V25-S1_S2_S3_JOINT_ANALYSIS"
    )
    commit, clean = _git_state(root)
    try:
        result = run_v25_joint_analysis(
            s1 / "source" / "V2.5一阶段单模块.zip",
            s1 / "raw_txt", s1 / "raw_mdat",
            s2 / "source" / "V2.5二阶段.zip",
            s2 / "raw_txt", s2 / "raw_mdat",
            s3 / "source" / "V2.5三阶段.zip",
            s3 / "raw_txt", s3 / "raw_mdat",
            output,
            source_commit=commit,
            source_worktree_clean=clean,
            created_at=datetime.now(ZoneInfo("Europe/London")),
            bootstrap_iterations=args.bootstrap_iterations,
            permutation_iterations=args.permutation_iterations,
        )
    except Exception as exc:
        print(f"V25 joint analysis failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"output_directory={result.output_directory}")
    print(f"s1_txt_count={result.s1_txt_count}")
    print(f"s2_txt_count={result.s2_txt_count}")
    print(f"s3_txt_count={result.s3_txt_count}")
    print(f"primary_selected_count={result.primary_selected_count}")
    print(f"primary_drop_flag_count={result.flagged_count}")
    print(f"artifact_count={result.artifact_count}")
    print("independent_block_generalisation_tested=false")
    print("final_test_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

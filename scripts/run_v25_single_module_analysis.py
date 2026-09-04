"""Run the V2.5 stage-1 isolated single-module analysis."""

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

from acoustic_encoder.v25_single_module_analysis import run_v25_s1_analysis


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
        description="Run V2.5 S1 QC, target tracking, and block-stability analysis."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--raw-txt-directory", type=Path)
    parser.add_argument("--raw-mdat-directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    data_root = root / "data" / "exported_txt" / "V25-S1_SINGLE_MODULE"
    zip_path = args.zip.resolve() if args.zip else (
        data_root / "source" / "V2.5一阶段单模块.zip"
    )
    raw_txt = args.raw_txt_directory.resolve() if args.raw_txt_directory else (
        data_root / "raw_txt"
    )
    raw_mdat = args.raw_mdat_directory.resolve() if args.raw_mdat_directory else (
        data_root / "raw_mdat"
    )
    output = args.output.resolve() if args.output else (
        root / "outputs" / "supplemental" / "V25-S1_SINGLE_MODULE_ANALYSIS"
    )
    commit, clean = _git_state(root)
    try:
        result = run_v25_s1_analysis(
            zip_path, raw_txt, raw_mdat, output,
            source_commit=commit,
            source_worktree_clean=clean,
            created_at=datetime.now(ZoneInfo("Europe/London")),
        )
    except Exception as exc:
        print(f"V25-S1 failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(f"output_directory={result.output_directory}")
    print(f"measurement_count={result.measurement_count}")
    print(f"mdat_count={result.mdat_count}")
    print(f"structurally_valid_count={result.structurally_valid_count}")
    print(f"flagged_count={result.flagged_count}")
    print(f"stable_target_signature_count={result.stable_target_signature_count}")
    print(f"selected_u4_stable_count={result.selected_u4_stable_count}")
    print(f"artifact_count={result.artifact_count}")
    print("S2_or_S3_performed=false")
    print("classification_performed=false")
    print("final_test_read=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

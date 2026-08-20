"""Run the frozen FORMAL-3 streamlined real-data import and QC."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.formal_real_import import (  # noqa: E402
    FORMAL3_ZIP_SHA256,
    run_formal3_import_qc,
    verify_formal3_output_hashes,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import, FORMAL-1 preprocess and QC the frozen REV003 ZIP."
    )
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-zip-sha256", default=FORMAL3_ZIP_SHA256)
    parser.add_argument("--created-at")
    return parser


def _source_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    created_at = args.created_at or datetime.now().astimezone().isoformat()
    result = run_formal3_import_qc(
        args.zip_path,
        args.output,
        expected_zip_sha256=args.expected_zip_sha256,
        created_at=created_at,
        source_commit=_source_commit(),
    )
    print(
        json.dumps(
            {
                "output_directory": str(result.output_directory.resolve()),
                "ready_for_formal_analysis": result.ready_for_formal_analysis,
                "active_count": result.active_count,
                "excluded_count": result.excluded_count,
                "active_pass_count": result.active_pass_count,
                "active_warning_count": result.active_warning_count,
                "active_fail_count": result.active_fail_count,
                "hash_verification": verify_formal3_output_hashes(
                    result.output_directory
                ),
                "final_test_read": False,
                "scientifically_eligible": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

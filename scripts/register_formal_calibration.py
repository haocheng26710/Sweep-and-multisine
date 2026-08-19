"""Register FORMAL-2A calibration and explicit screenshot assessment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.formal_acquisition import (  # noqa: E402
    register_formal_calibration,
    verify_formal_package_hashes,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register CMM29939.txt without modifying its bytes."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--checked-at", required=True)
    parser.add_argument("--assessed-by", required=True)
    parser.add_argument(
        "--evidence-status",
        required=True,
        choices=(
            "verified_input_binding",
            "insufficient_input_binding_evidence",
        ),
    )
    parser.add_argument("--observation", action="append", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    calibration = args.root / "01_calibration" / "CMM29939.txt"
    screenshot = args.root / "01_calibration" / "REW_CMM29939_LOADED.png"
    result = register_formal_calibration(
        args.root,
        source_path=args.source or calibration,
        copy_path=calibration,
        screenshot_path=screenshot,
        checked_at=args.checked_at,
        input_device="iMM-6C",
        evidence_status=args.evidence_status,
        evidence_assessed_by=args.assessed_by,
        evidence_observations=tuple(args.observation),
    )
    print(
        json.dumps(
            {
                "registration_path": str(result.registration_path),
                "calibration_sha256": result.calibration_sha256,
                "screenshot_sha256": result.screenshot_sha256,
                "ready_for_B01": result.ready_for_b01,
                "unresolved_blockers": list(result.unresolved_blockers),
                "hash_verification": verify_formal_package_hashes(args.root),
                "formal_measurement_started": False,
                "final_test_read": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Create or verify the FORMAL-2 empty acquisition package."""

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
    prepare_formal_acquisition_package,
    verify_formal_package_hashes,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the immutable FORMAL-2 acquisition infrastructure."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=PROJECT_ROOT / "docs" / "experiment" / "RESEARCH_PROTOCOL_REV002.md",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=PROJECT_ROOT
        / "docs"
        / "experiment"
        / "FORMAL_ACQUISITION_PLAN_REV001.md",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        help="Explicit CMM29939.txt source; omitted means calibration_file_missing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    package = prepare_formal_acquisition_package(
        args.root,
        protocol_path=args.protocol,
        acquisition_plan_path=args.plan,
        calibration_source=args.calibration,
        backup_plan=None,
    )
    verification = verify_formal_package_hashes(package.root)
    print(
        json.dumps(
            {
                "root": str(package.root.resolve()),
                "ready_for_B01": package.ready_for_b01,
                "unresolved_blockers": list(package.unresolved_blockers),
                "hash_verification": verification,
                "final_test_read": False,
                "formal_measurement_started": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

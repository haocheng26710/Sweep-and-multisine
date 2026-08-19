"""Register the FORMAL-2A-FIX explicit iMM-6C input-calibration evidence."""

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
    supplement_formal_mic_input_evidence,
    verify_formal_package_hashes,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Register explicit REW iMM-6C microphone-input calibration evidence "
            "without modifying the calibration file or uploaded screenshot."
        )
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-screenshot", type=Path, required=True)
    parser.add_argument("--checked-at", required=True)
    parser.add_argument("--assessed-by", required=True)
    parser.add_argument("--observation", action="append", required=True)
    parser.add_argument("--rew-input-is-imm6c-microphone", action="store_true")
    parser.add_argument("--cmm-is-in-mic-calibration-files", action="store_true")
    parser.add_argument(
        "--soundcard-output-not-used-as-mic-evidence", action="store_true"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = supplement_formal_mic_input_evidence(
        args.root,
        source_screenshot_path=args.source_screenshot,
        checked_at=args.checked_at,
        assessed_by=args.assessed_by,
        observations=tuple(args.observation),
        rew_input_is_imm6c_microphone=args.rew_input_is_imm6c_microphone,
        cmm_is_in_mic_calibration_files=args.cmm_is_in_mic_calibration_files,
        soundcard_output_not_used_as_mic_evidence=(
            args.soundcard_output_not_used_as_mic_evidence
        ),
    )
    print(
        json.dumps(
            {
                "evidence_path": str(result.evidence_path),
                "canonical_screenshot_path": str(result.canonical_screenshot_path),
                "input_binding_status": result.input_binding_status,
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

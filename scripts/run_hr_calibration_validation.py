from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.hr_validation import run_hr_calibration_validation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--run-id", default="DEV-C10_P6A_FINAL")
    args = parser.parse_args()
    output = run_hr_calibration_validation(
        output_root=args.output_root,
        run_id=args.run_id,
        project_root=PROJECT_ROOT,
    )
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

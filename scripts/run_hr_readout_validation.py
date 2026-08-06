#!/usr/bin/env python
"""Run deterministic simulated DEV-C11/P6-B validation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.hr_readout_validation import run_hr_readout_validation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()
    output = run_hr_readout_validation(
        output_root=args.output_root,
        run_id=args.run_id,
        project_root=args.project_root,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

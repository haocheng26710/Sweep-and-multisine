from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.comparison_validation import (  # noqa: E402
    run_simulated_comparison_validation,
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", default="DEV-C7-P4B-VALIDATION")
    args = parser.parse_args()
    print(run_simulated_comparison_validation(
        project_root=PROJECT_ROOT,
        output_root=args.output_root,
        run_id=args.run_id,
    ))

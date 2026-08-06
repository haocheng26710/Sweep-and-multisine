from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.tone_selection_validation import run_simulated_tone_selection_validation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic DEV-C12 P9-A validation")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--config", default="config/validation_dev_c12_tone_selection.yaml")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    summary = run_simulated_tone_selection_validation(
        project_root=project_root,
        config_path=(project_root / args.config).resolve(),
        output_root=(project_root / args.output_root).resolve(),
        run_id=args.run_id,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

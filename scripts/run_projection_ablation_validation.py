from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.projection_ablation_validation import run_simulated_projection_ablation_validation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic DEV-C13 P9-B validation")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--config", default="config/validation_dev_c13_p9b.yaml")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    result = run_simulated_projection_ablation_validation(
        project_root=project_root,
        config_path=(project_root / args.config).resolve(),
        output_root=(project_root / args.output_root).resolve(),
        run_id=args.run_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

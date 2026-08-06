from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.pre_experiment_acceptance_runner import (  # noqa: E402
    run_pre_experiment_acceptance,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DEV-C16 T0-T3 pre-experiment acceptance"
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--config", type=Path,
        default=Path("config/validation_dev_c16_acceptance.yaml"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    config = args.config if args.config.is_absolute() else project / args.config
    output = args.output_root if args.output_root.is_absolute() else project / args.output_root
    summary = run_pre_experiment_acceptance(
        project_root=project, config_path=config, output_root=output,
        run_id=args.run_id,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["software_integration_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

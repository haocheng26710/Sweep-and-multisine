from __future__ import annotations

import argparse
from pathlib import Path

from acoustic_encoder.offline_readout_validation import run_offline_readout_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic DEV-C15 P9-D validation")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--config", default="config/validation_dev_c15_p9d.yaml")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    project = Path(args.project_root).resolve()
    run_offline_readout_validation(
        project_root=project, config_path=project / args.config,
        output_root=project / args.output_root, run_id=args.run_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

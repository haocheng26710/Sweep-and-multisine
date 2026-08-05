"""Run the immutable simulated DEV-C6/P2-B validation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.dataset_quality_validation import (  # noqa: E402
    run_simulated_dataset_quality_validation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config" / "validation_dev_c6_dataset_qc.yaml",
    )
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--run-id", default="DEV-C6_P2B_FINAL")
    parser.add_argument("--feature-count", type=int, default=71)
    arguments = parser.parse_args()
    validation = run_simulated_dataset_quality_validation(
        project_root=PROJECT_ROOT,
        config_path=arguments.config,
        output_root=arguments.output_root,
        run_id=arguments.run_id,
        feature_count=arguments.feature_count,
    )
    result = validation.result
    print(f"output_directory={validation.output_directory}")
    print("processing_status=completed")
    print(f"measurements={len(result.scoped_sample_ids)}")
    print(f"conditions={len(result.condition_results)}")
    print(f"aggregate_status={result.aggregate_status.value}")
    print(f"canonical_ready={str(result.canonical_ready).lower()}")
    print("scientific_use=prohibited_simulated_software_validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

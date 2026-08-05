"""Run the immutable simulated DEV-C5/P4-A direction-metrics validation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.config import load_config  # noqa: E402
from acoustic_encoder.metrics_validation import (  # noqa: E402
    run_simulated_direction_metrics_validation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "config" / "validation_dev_c5_direction_metrics.yaml",
    )
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--run-id", default="DEV-C5_P4A_FINAL")
    parser.add_argument("--feature-count", type=int, default=71)
    arguments = parser.parse_args()
    resolved = load_config(
        arguments.config,
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    result = run_simulated_direction_metrics_validation(
        output_root=arguments.output_root,
        run_id=arguments.run_id,
        metrics_config=resolved["direction_metrics"],
        random_state=int(resolved["random_state"]),
        feature_count=arguments.feature_count,
    )
    summary = result.metrics.summary
    print(f"output_directory={result.output_directory}")
    print(f"processing_status={result.metrics.processing_status}")
    print(f"directions={summary.direction_count}")
    print(f"samples={summary.sample_count}")
    print(f"common_valid_features={result.metrics.common_valid_feature_count}")
    print(f"effective_rank={result.metrics.effective_rank.value:.12g}")
    print(f"morphology_gain={result.metrics.morphology_gain.value:.12g}")
    print("scientific_use=prohibited_simulated_software_validation")
    return 0 if result.metrics.processing_status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

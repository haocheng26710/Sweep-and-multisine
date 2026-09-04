from __future__ import annotations

import argparse
from pathlib import Path

from acoustic_encoder.p04t4_baseline_followup_analysis import (
    run_p04t4_baseline_followup_analysis,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze the third P04T4 BASE batch")
    parser.add_argument(
        "--original-batch",
        type=Path,
        default=Path("data/real_experiment/P04T4_RETURN_CONTROL_CONFIRMATION"),
    )
    parser.add_argument(
        "--followup-batch",
        type=Path,
        default=Path("data/real_experiment/P04T4_BASELINE_REASSEMBLY_FOLLOWUP"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "outputs/real_experiment/research_analysis/P04T4_BASELINE_REASSEMBLY_FOLLOWUP"
        ),
    )
    args = parser.parse_args()
    result = run_p04t4_baseline_followup_analysis(
        args.original_batch, args.followup_batch, args.output
    )
    print(f"classification={result.classification}")
    print(f"measurements={result.measurement_count}")
    print(f"artifacts={result.artifact_count}")
    print(f"output={result.output_directory}")


if __name__ == "__main__":
    main()


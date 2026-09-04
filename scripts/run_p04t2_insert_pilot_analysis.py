from __future__ import annotations

import argparse
from pathlib import Path

from acoustic_encoder.p04t2_insert_pilot_analysis import run_p04t2_insert_pilot_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen P04T2 integrated-insert pilot analysis")
    parser.add_argument(
        "--batch-root",
        type=Path,
        default=Path("data/real_experiment/P04T2_INTEGRATED_INSERT_PILOT"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS"),
    )
    args = parser.parse_args()
    result = run_p04t2_insert_pilot_analysis(args.batch_root, args.output)
    print(f"classification={result.classification}")
    print(f"measurements={result.measurement_count}")
    print(f"selected={result.selected_count}")
    print(f"artifacts={result.artifact_count}")
    print(f"output={result.output_directory}")


if __name__ == "__main__":
    main()

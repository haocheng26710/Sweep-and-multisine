"""Run the immutable simulated DEV-C4 matched-tone validation bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.config import load_config  # noqa: E402
from acoustic_encoder.matched_tone_validation import (  # noqa: E402
    run_simulated_matched_tone_validation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--run-id", default="DEV-C4_P3C_FINAL")
    parser.add_argument("--random-state", type=int, default=20260805)
    parser.add_argument("--recording-delay-samples", type=int, default=1379)
    arguments = parser.parse_args()
    sweep = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c4_matched_tones.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    multisine = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    stimulus = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )["stimulus"]
    result = run_simulated_matched_tone_validation(
        output_root=arguments.output_root,
        run_id=arguments.run_id,
        sweep_config=sweep,
        multisine_config=multisine,
        stimulus_config=stimulus,
        random_state=arguments.random_state,
        recording_delay_samples=arguments.recording_delay_samples,
    )
    print(f"output_directory={result.output_directory}")
    print(f"common_valid_tones={result.view.common_valid_count}")
    print(f"maximum_matched_error_db={result.maximum_matched_error_db:.12g}")
    print("scientific_use=prohibited_simulated_software_validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

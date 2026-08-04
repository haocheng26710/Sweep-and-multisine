"""Generate deterministic P7 multisine stimulus artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.config import load_config  # noqa: E402
from acoustic_encoder.stimulus_multisine import generate_multisine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "data" / "stimuli")
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()
    config = load_config(arguments.config, default_path=PROJECT_ROOT / "config" / "default.yaml")
    if config["measurement_mode"] != "schroeder_multisine":
        parser.error("P7 stimulus config must use measurement_mode: schroeder_multisine")
    artifacts = generate_multisine(config["stimulus"], arguments.output_root, overwrite=arguments.overwrite)
    print(f"Generated stimulus: {artifacts.directory}")
    print(f"WAV SHA-256: {artifacts.waveform_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


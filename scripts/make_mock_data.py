"""Generate matching mock sweep and multisine inputs for DEV-A tests."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.config import load_config  # noqa: E402
from acoustic_encoder.mock_data import generate_dual_mode_mock  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stimulus-config",
        type=Path,
        default=PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
    )
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "data" / "mock")
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()
    config = load_config(
        arguments.stimulus_config,
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    manifest = generate_dual_mode_mock(
        arguments.output_root,
        config["stimulus"],
        random_state=int(config["random_state"]),
        overwrite=arguments.overwrite,
    )
    print(f"Generated mock manifest: {manifest}")
    print("MOCK ONLY: these files must not be used as research results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


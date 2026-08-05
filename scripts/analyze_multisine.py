"""Mode-locked multisine entry point using the unified DEV-C executor."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.pipeline_cli import pipeline_main  # noqa: E402
from acoustic_encoder.schemas import MeasurementMode  # noqa: E402


def main() -> int:
    return pipeline_main(
        required_mode=MeasurementMode.SCHROEDER_MULTISINE,
        project_root=PROJECT_ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())

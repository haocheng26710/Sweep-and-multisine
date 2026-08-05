"""Run explicit-scope P2-B dataset quality control."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.dataset_quality_cli import run_dataset_quality_cli  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run_dataset_quality_cli(project_root=PROJECT_ROOT))

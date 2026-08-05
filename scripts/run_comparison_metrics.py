from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.comparison_metrics_cli import run_comparison_metrics_cli  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(run_comparison_metrics_cli())

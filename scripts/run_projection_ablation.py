from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.projection_ablation_cli import run_projection_ablation_command  # noqa: E402


if __name__ == "__main__":
    print(run_projection_ablation_command())

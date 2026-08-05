import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from acoustic_encoder.classification_validation import run_simulated_classification_validation  # noqa: E402
from acoustic_encoder.schemas import FeatureKind  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "outputs")
    parser.add_argument("--run-id-prefix", default="DEV-C8-P5A-FINAL")
    args = parser.parse_args()
    for suffix, kind in (("SWEEP", FeatureKind.DENSE_DEMEANED_DB), ("MULTISINE", FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE)):
        print(run_simulated_classification_validation(project_root=PROJECT_ROOT, output_root=args.output_root, run_id=f"{args.run_id_prefix}-{suffix}", feature_kind=kind))

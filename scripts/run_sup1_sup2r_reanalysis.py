"""Run SUP-1 module-library completion and SUP-2R existing-data reanalysis."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.supplemental_mechanism_reanalysis import (  # noqa: E402
    run_sup1_sup2r_reanalysis,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Use existing SUP-1 and FORMAL AS01 real data for mechanism reanalysis"
    )
    parser.add_argument(
        "--formal3",
        type=Path,
        default=ROOT / "outputs" / "formal" / "FORMAL-3_REAL_IMPORT_QC",
    )
    parser.add_argument(
        "--formal4",
        type=Path,
        default=ROOT / "outputs" / "formal" / "FORMAL-4_CORE_ANALYSIS",
    )
    parser.add_argument(
        "--formal5",
        type=Path,
        default=ROOT / "outputs" / "formal" / "FORMAL-5_FINAL_SYNTHESIS",
    )
    parser.add_argument(
        "--sup0",
        type=Path,
        default=ROOT / "outputs" / "supplemental" / "SUP-0_FREQUENCY_LOCALIZATION",
    )
    parser.add_argument(
        "--sup1",
        type=Path,
        default=ROOT / "outputs" / "supplemental" / "SUP-1_ENC_MODULE_SCAN",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "supplemental" / "SUP-1_SUP-2R_MECHANISM_REANALYSIS",
    )
    args = parser.parse_args()
    result = run_sup1_sup2r_reanalysis(
        formal3_directory=args.formal3,
        formal4_directory=args.formal4,
        formal5_directory=args.formal5,
        sup0_directory=args.sup0,
        sup1_directory=args.sup1,
        output_directory=args.output,
    )
    print(f"output_directory={result.output_directory}")
    print(f"sup1_measurement_count={result.sup1_measurement_count}")
    print(f"formal_active_count={result.formal_active_count}")
    print(f"formal_as01_active_count={result.formal_as01_active_count}")
    print(f"candidate_window_count={result.candidate_window_count}")
    print(f"artifact_count={result.artifact_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

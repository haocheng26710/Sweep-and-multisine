"""Run the frozen INFO-TOP-1 real single-microphone baseline only."""

from __future__ import annotations

import argparse
from pathlib import Path

from acoustic_encoder.info_top_single_mic import run_info_top_single_mic


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--formal-zip",
        default=r"D:\Firefly\Desktop\毕业论文相关\球体修改版\正式实验_精简版_REV003.zip",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs/info_top/INFO_TOP_1_SINGLE_MIC_BASELINE"
    result = run_info_top_single_mic(root, args.formal_zip, output)
    print(f"status={result['status']}")
    print(f"level_a_curves={result['counts']['level_a_real_curves']}")
    print(f"level_b_curves={result['counts']['level_b_real_active_curves']}")


if __name__ == "__main__":
    main()

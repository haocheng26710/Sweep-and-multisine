from __future__ import annotations

from pathlib import Path

from acoustic_encoder.info_top_information_cost import run_info_top_information_cost


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs/info_top/INFO_TOP_2_INFORMATION_COST_CURVE"
    result = run_info_top_information_cost(root, output)
    print(result["status"])


if __name__ == "__main__":
    main()

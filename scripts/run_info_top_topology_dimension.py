from __future__ import annotations

from pathlib import Path

from acoustic_encoder.info_top_topology_dimension import run_top3_analysis


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs/info_top/INFO_TOP_3_TOPOLOGY_DIMENSION_MATCH"
    result = run_top3_analysis(root, output)
    print(result["status"])


if __name__ == "__main__":
    main()

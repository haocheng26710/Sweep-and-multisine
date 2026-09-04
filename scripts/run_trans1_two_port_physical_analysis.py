from __future__ import annotations

from acoustic_encoder.trans1_two_port_physical_analysis import (
    run_trans1_two_port_physical_analysis,
)


if __name__ == "__main__":
    result = run_trans1_two_port_physical_analysis(
        "data/real_experiment/TRANS1_TWO_PORT_PHYSICAL_PILOT",
        "outputs/real_experiment/research_analysis/TRANS1_TWO_PORT_PHYSICAL_PILOT",
    )
    print(result)

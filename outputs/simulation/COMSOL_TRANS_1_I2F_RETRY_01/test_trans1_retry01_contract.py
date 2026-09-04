"""Static regression gate for TRANS-1 RETRY_01 implementation identity."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_trans1_retry01.py"
AUTHORITY = HERE.parent / "COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02" / "run_trans0_retry02.py"


def main() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    authority = AUTHORITY.read_text(encoding="utf-8")
    checks = {
        "uses_retry02_authority": "COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02/run_trans0_retry02.py" in source,
        "does_not_use_failed_trans1_runner": "COMSOL_TRANS_1_I2F/run_trans1.py" not in source,
        "frozen_frequency_formula": "200.0 * 2.0 ** (np.arange(256) / 48.0)" in source,
        "six_frozen_cases": all(token in source for token in ("ISO_CODED", "ISO_SYM", "MIX_CONTROL", '"N"', '"S"')),
        "strict_gate_thresholds": all(token in source for token in ("< 0.01", "< 0.5", "<= 0.75")),
        "direct_java_study_run": 'model.java.study("std_freq").run()' in source,
        "authority_quickz": 'wp.set("quickz"' in authority,
        "authority_correct_adjacency": "geom.getAdj(2, 3, boundary)" in authority,
        "authority_ports_inside": all(token in authority for token in (
            'add_box_selection(comp, "bnd_port_N", 2, bounds_N, "inside")',
            'add_box_selection(comp, "bnd_port_S", 2, bounds_S, "inside")')),
        "authority_feature_union": 'add_union_selection(comp, "dom_hr03_cavity"' in authority
        and 'add_union_selection(comp, "dom_south_cavity"' in authority,
        "final_test_not_read": "final-test" in source and "final_test_read" in source,
    }
    checks["pass"] = all(checks.values())
    print(json.dumps(checks, indent=2))
    raise SystemExit(0 if checks["pass"] else 1)


if __name__ == "__main__":
    main()

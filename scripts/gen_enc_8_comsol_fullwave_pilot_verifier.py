"""Independent integrity and numeric checks for GEN-ENC-8 COMSOL pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_8_COMSOL_FULLWAVE_PILOT"
ORDER = ("HAND_01", "NEAR_01", "RANDOM_01", "PHYSICS_01")
EXPECTED_MPH = {
    "HAND_01_area2d_fullwave_fine.mph": "40c0ada6d441b91db69cd087e420e096a9cebf6ee29ffa9f12d632fadbba2db3",
    "HAND_01_area2d_fullwave.mph": "c8f8b0093ccd5bd94160be6ff6e161ff8ba8aa3d2ea4b9d6cc3a524ab4195230",
    "NEAR_01_area2d_fullwave.mph": "1e037d54b9300ffc138c1d4b3d3ce9698dea03234c36c4014d666c4bc37145c9",
    "PHYSICS_01_area2d_fullwave.mph": "e2594539c530da9559268ccc28f1952a37b8dcfd25ca825097f0d32bce14fb0b",
    "RANDOM_01_area2d_fullwave.mph": "518fac438ffcf4f933a3ab6e65a43d27f8d985d355dcadce634fcfe00703d8e7",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    raw = json.loads((ROOT / "raw_response_compact.json").read_text(encoding="utf-8"))
    result = json.loads((ROOT / "result_summary.json").read_text(encoding="utf-8"))
    if raw["frequency_indices"] != [0, 19, 38, 56, 75, 94, 113, 132, 151, 169, 188, 207]:
        raise RuntimeError("FREQUENCY_INDEX_FREEZE_MISMATCH")
    if tuple(raw["responses_imaginary_pa"]) != ORDER:
        raise RuntimeError("REPRESENTATIVE_ORDER_MISMATCH")
    for member_id in ORDER:
        values = np.asarray(raw["responses_imaginary_pa"][member_id], dtype=float)
        if values.shape != (4, 12) or not np.all(np.isfinite(values)):
            raise RuntimeError(f"INVALID_RESPONSE_{member_id}")
    coarse = np.asarray(raw["responses_imaginary_pa"]["HAND_01"], dtype=float)
    fine = np.asarray(raw["hand_fine_responses_imaginary_pa"], dtype=float)
    relative = float(np.linalg.norm(fine - coarse) / np.linalg.norm(fine))
    recorded = float(result["mesh_gate"]["relative_l2_response_change"])
    if not np.isclose(relative, recorded, rtol=0.0, atol=1e-15) or relative > 0.02:
        raise RuntimeError("MESH_GATE_RECOMPUTE_FAILURE")
    for filename, expected in EXPECTED_MPH.items():
        if sha256(ROOT / filename) != expected:
            raise RuntimeError(f"MPH_HASH_MISMATCH_{filename}")
    if result["terminal_state"] != "COMSOL_PILOT_NUMERICALLY_STABLE_MODEL_DISCREPANCY_OBSERVED":
        raise RuntimeError("TERMINAL_MISMATCH")
    terminal = {
        "terminal_state": "COMSOL_PILOT_INDEPENDENT_VERIFICATION_PASS",
        "checks": [
            "EXACT_FOUR_FIXED_REPRESENTATIVES_X_FOUR_PORTS_X_TWELVE_FREQUENCIES",
            "FINITE_COMPLEX_RESPONSE_WITH_ZERO_REAL_PART_RECORDED_COMPACTLY",
            "HAND_COARSE_FINE_RELATIVE_L2_RECOMPUTED_BELOW_2_PERCENT",
            "FIVE_MPH_SHA256_MATCH",
            "PRIMARY_TERMINAL_MATCH",
        ],
    }
    (ROOT / "independent_verification.json").write_text(
        json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(terminal, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

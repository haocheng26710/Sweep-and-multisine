"""Independent saved-output verifier for the GEN-ENC-7 model bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_7_MODEL_BRIDGE"
NUISANCE = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
M2B_SOURCE = REPO / "src/acoustic_encoder/gen_enc/actual_fluid_star_network.py"
RESOLVED_SOURCE = REPO / "src/acoustic_encoder/gen_enc/resolved_plenum_star_network.py"
OBSB_RESULT = REPO / "outputs/gen_enc/GEN_ENC_6_OBSB_GEOMETRY_OVERLAP/result_summary.json"
REPRESENTATIVE_PATHS = {
    "HAND_01": REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/HAND_DESIGNED/HAND_01.identity.json",
    "NEAR_01": REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/NEAR_INDEPENDENT/NEAR_01.identity.json",
    "RANDOM_01": REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/FIXED_SEED_RANDOM_DISORDERED/RANDOM_01.identity.json",
    "PHYSICS_01": REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/PHYSICS_METAMATERIAL_INSPIRED/PHYSICS_01.identity.json",
}
FRACTIONS = (0.125, 0.25, 0.5)
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distances(matrix: np.ndarray, names: list[str]) -> dict[str, Any]:
    if matrix.shape != (4, 43) or not np.all(np.isfinite(matrix)):
        raise RuntimeError("REPRESENTATIVE_SIGNATURE_FAIL")
    rows = [
        {
            "representatives": [names[left], names[right]],
            "distance": float(np.linalg.norm(matrix[left] - matrix[right])),
        }
        for left, right in PAIRS
    ]
    values = np.asarray([row["distance"] for row in rows])
    return {"minimum": float(np.min(values)), "mean": float(np.mean(values)), "pairwise": rows}


def assert_distances(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    if [row["representatives"] for row in actual["pairwise"]] != [row["representatives"] for row in expected["pairwise"]]:
        raise RuntimeError("PAIR_ORDER_FAIL")
    np.testing.assert_allclose(
        [actual["minimum"], actual["mean"]] + [row["distance"] for row in actual["pairwise"]],
        [expected["minimum"], expected["mean"]] + [row["distance"] for row in expected["pairwise"]],
        rtol=1e-13,
        atol=1e-15,
    )


def main() -> int:
    contract = load(ROOT / "diagnostic_contract.json")
    result = load(ROOT / "result_summary.json")
    if contract["schema_version"] != "gen_enc_7_model_bridge_contract_v1":
        raise RuntimeError("CONTRACT_FAIL")
    names = list(REPRESENTATIVE_PATHS)
    if contract["representatives"] != names:
        raise RuntimeError("REPRESENTATIVE_ORDER_FAIL")
    expected_hashes = {
        "nuisance": digest(NUISANCE),
        "m2b_source": digest(M2B_SOURCE),
        "resolved_source": digest(RESOLVED_SOURCE),
        "obsb_result": digest(OBSB_RESULT),
        "representatives": {name: digest(path) for name, path in REPRESENTATIVE_PATHS.items()},
    }
    if contract["input_sha256"] != expected_hashes:
        raise RuntimeError("INPUT_HASH_FAIL")
    if any(
        (
            contract["candidate_ranking_emitted"], contract["parameter_search_performed"],
            contract["validation_reads"] != 0, contract["final_test_read"], contract["m3_authorized"],
            result["candidate_ranking_emitted"], result["parameter_search_performed"],
            result["validation_reads"] != 0, result["final_test_read"], result["m3_authorized"],
        )
    ):
        raise RuntimeError("SCOPE_SEAL_FAIL")

    baseline_matrix = np.load(ROOT / "baseline_representative_signatures.npy", allow_pickle=False)
    baseline = distances(baseline_matrix, names)
    assert_distances(baseline, result["baseline_representative_distances"])
    gains = []
    recomputed = {}
    for fraction in FRACTIONS:
        token = str(fraction).replace(".", "p")
        matrix = np.load(ROOT / f"resolved_center_fraction_{token}_representative_signatures.npy", allow_pickle=False)
        units = np.load(ROOT / f"resolved_center_fraction_{token}_unit_discrepancy.npy", allow_pickle=False)
        if units.shape != (4, 16, 2) or not np.all(np.isfinite(units)):
            raise RuntimeError("UNIT_DISCREPANCY_FAIL")
        current = distances(matrix, names)
        saved = result["center_fraction_results"][str(fraction)]
        assert_distances(current, saved["representative_distances"])
        minimum_gain = float(current["minimum"] / baseline["minimum"] - 1.0)
        mean_gain = float(current["mean"] / baseline["mean"] - 1.0)
        summaries = []
        for index, name in enumerate(names):
            summaries.append(
                {
                    "representative": name,
                    "median_relative_response_change": float(np.median(units[index, :, 0])),
                    "maximum_relative_response_change": float(np.max(units[index, :, 0])),
                    "median_state_gram_shift": float(np.median(units[index, :, 1])),
                    "audit_units": 16,
                }
            )
        for actual, expected in zip(summaries, saved["representative_discrepancy"]):
            if actual["representative"] != expected["representative"] or actual["audit_units"] != expected["audit_units"]:
                raise RuntimeError("DISCREPANCY_IDENTITY_FAIL")
            np.testing.assert_allclose(
                [actual["median_relative_response_change"], actual["maximum_relative_response_change"], actual["median_state_gram_shift"]],
                [expected["median_relative_response_change"], expected["maximum_relative_response_change"], expected["median_state_gram_shift"]],
                rtol=1e-13,
                atol=1e-15,
            )
        count = int(sum(row["median_relative_response_change"] >= contract["thresholds"]["observable_median_relative_response_change"] for row in summaries))
        if count != saved["observable_representative_count"]:
            raise RuntimeError("OBSERVABLE_COUNT_FAIL")
        np.testing.assert_allclose(
            [minimum_gain, mean_gain],
            [saved["minimum_pair_distance_relative_gain"], saved["mean_pair_distance_relative_gain"]],
            rtol=1e-13,
            atol=1e-15,
        )
        gains.append(minimum_gain)
        recomputed[str(fraction)] = {"observable_representative_count": count, "minimum_pair_distance_relative_gain": minimum_gain, "mean_pair_distance_relative_gain": mean_gain}

    sign_reversal = bool(min(gains) < 0.0 < max(gains))
    primary = recomputed[str(contract["primary_center_volume_fraction"])]
    count = primary["observable_representative_count"]
    gain = primary["minimum_pair_distance_relative_gain"]
    if sign_reversal:
        terminal = "MODEL_BRIDGE_INCONCLUSIVE_DISCRETIZATION_SENSITIVE"
    elif count >= 2 and gain >= 0.20:
        terminal = "MODEL_BRIDGE_SPATIAL_RESOLUTION_RESTORES_CONTRAST"
    elif count >= 2 and gain < 0.20:
        terminal = "MODEL_BRIDGE_SPATIAL_RESOLUTION_OBSERVABLE_NO_CONTRAST_RESCUE"
    elif count < 2 and abs(gain) < 0.20:
        terminal = "MODEL_BRIDGE_FIVE_NODE_ADEQUATE_FOR_FIXED_REPRESENTATIVES"
    else:
        terminal = "MODEL_BRIDGE_INCONCLUSIVE_MIXED_SIGNAL"
    if sign_reversal != result["sensitivity_minimum_gain_sign_reversal"] or terminal != result["terminal_state"]:
        raise RuntimeError("TERMINAL_FAIL")

    report = {
        "verifier": "PASS",
        "terminal_state_recomputed": terminal,
        "four_fixed_representatives": True,
        "audit_units_per_representative_per_fraction": 16,
        "saved_signatures_verified": True,
        "saved_unit_discrepancies_verified": True,
        "fraction_results_recomputed": recomputed,
        "input_hashes_verified": True,
        "scope_seal_verified": True,
        "contract_sha256": digest(ROOT / "diagnostic_contract.json"),
        "result_sha256": digest(ROOT / "result_summary.json"),
        "validation_reads": 0,
        "final_test_read": False,
    }
    (ROOT / "independent_verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("MODEL_BRIDGE_INDEPENDENT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

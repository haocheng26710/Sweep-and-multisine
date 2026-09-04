"""Independent verifier for the OBS-A exact80 readout-bottleneck diagnosis."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_5_OBSA_READOUT_BOTTLENECK"
M2B_RESULT = REPO / "outputs/gen_enc/GEN_ENC_4_M2B_EXACT80_DEVELOPMENT/result_summary.json"
NUISANCE = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
FAMILIES = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)
LAYERS = (
    "LOCAL_FULL_CLEAN",
    "CENTRAL_RAW_CLEAN",
    "CENTRAL_DIFF_CLEAN",
    "CENTRAL_DIFF_NOISY",
)
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recompute_separation(matrix: np.ndarray) -> dict[str, Any]:
    if matrix.shape != (80, 43) or not np.all(np.isfinite(matrix)):
        raise RuntimeError("SIGNATURE_MATRIX_SHAPE_OR_FINITE_FAIL")
    scale = np.std(matrix, axis=0, ddof=1)
    usable = scale > np.finfo(float).eps
    z = (matrix[:, usable] - np.mean(matrix[:, usable], axis=0)) / scale[usable]
    centroids = np.stack([np.mean(z[i * 20 : (i + 1) * 20], axis=0) for i in range(4)])
    within = np.asarray(
        [
            math.sqrt(
                float(
                    np.mean(
                        np.sum((z[i * 20 : (i + 1) * 20] - centroids[i]) ** 2, axis=1)
                    )
                )
            )
            for i in range(4)
        ]
    )
    rows = []
    for left, right in PAIRS:
        pooled = math.sqrt(0.5 * (within[left] ** 2 + within[right] ** 2))
        rows.append(
            {
                "families": [FAMILIES[left], FAMILIES[right]],
                "ratio": float(np.linalg.norm(centroids[left] - centroids[right]) / pooled),
            }
        )
    ratios = [row["ratio"] for row in rows]
    return {
        "usable_dimensions": int(np.sum(usable)),
        "minimum_between_within_ratio": min(ratios),
        "mean_between_within_ratio": float(np.mean(ratios)),
        "pairwise": rows,
    }


def assert_layer_equal(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    if actual["usable_dimensions"] != expected["usable_dimensions"]:
        raise RuntimeError("USABLE_DIMENSION_FAIL")
    np.testing.assert_allclose(
        [actual["minimum_between_within_ratio"], actual["mean_between_within_ratio"]],
        [expected["minimum_between_within_ratio"], expected["mean_between_within_ratio"]],
        rtol=1e-13,
        atol=0.0,
    )
    if [row["families"] for row in actual["pairwise"]] != [
        row["families"] for row in expected["pairwise"]
    ]:
        raise RuntimeError("PAIR_ORDER_FAIL")
    np.testing.assert_allclose(
        [row["ratio"] for row in actual["pairwise"]],
        [row["ratio"] for row in expected["pairwise"]],
        rtol=1e-13,
        atol=0.0,
    )


def main() -> int:
    contract = load(ROOT / "diagnostic_contract.json")
    result = load(ROOT / "result_summary.json")

    if contract["schema_version"] != "gen_enc_5_obsa_contract_v1":
        raise RuntimeError("CONTRACT_VERSION_FAIL")
    if contract["members"] != 80 or contract["layers"] != list(LAYERS):
        raise RuntimeError("CONTRACT_SCOPE_FAIL")
    if len(contract["nuisance_cell_indices_zero_based"]) != 32 or contract["repeats"] != [0, 1]:
        raise RuntimeError("DEVELOPMENT_SAMPLING_FAIL")
    if contract["input_sha256"] != {
        "m2b_result": digest(M2B_RESULT),
        "nuisance": digest(NUISANCE),
    }:
        raise RuntimeError("INPUT_HASH_FAIL")
    if any(
        (
            contract["validation_reads"] != 0,
            contract["final_test_read"],
            contract["m3_authorized"],
            result["validation_reads"] != 0,
            result["final_test_read"],
            result["m3_authorized"],
            result["candidate_ranking_emitted"],
            result["parameter_search_performed"],
        )
    ):
        raise RuntimeError("SCOPE_SEAL_FAIL")

    records = result["identity_records"]
    if len(records) != 80:
        raise RuntimeError("EXACT80_COUNT_FAIL")
    expected_families = [family for family in FAMILIES for _ in range(20)]
    if [record["family_id"] for record in records] != expected_families:
        raise RuntimeError("EXACT80_FAMILY_ORDER_FAIL")
    if len({record["identity_id"] for record in records}) != 80:
        raise RuntimeError("EXACT80_IDENTITY_UNIQUENESS_FAIL")

    recomputed: dict[str, dict[str, Any]] = {}
    signature_hashes: dict[str, str] = {}
    for layer in LAYERS:
        path = ROOT / f"{layer.lower()}_identity_signatures.npy"
        recomputed[layer] = recompute_separation(np.load(path, allow_pickle=False))
        assert_layer_equal(recomputed[layer], result["layer_results"][layer])
        signature_hashes[layer] = digest(path)

    local = recomputed["LOCAL_FULL_CLEAN"]["minimum_between_within_ratio"]
    raw = recomputed["CENTRAL_RAW_CLEAN"]["minimum_between_within_ratio"]
    clean = recomputed["CENTRAL_DIFF_CLEAN"]["minimum_between_within_ratio"]
    noisy = recomputed["CENTRAL_DIFF_NOISY"]["minimum_between_within_ratio"]
    flags = {
        "H1_CENTRAL_PLENUM_PROJECTION": bool(local >= 1.0 and raw < 0.8 * local),
        "H2_FAMILY_GEOMETRY_OVERLAP": bool(local < 1.0),
        "H3_SENSOR_NOISE_GAIN": bool(noisy < 0.8 * clean),
        "H4_STATE_DIFFERENTIAL_PROJECTION": bool(clean < 0.8 * raw),
    }
    primary = next((name for name in contract["hypothesis_order"] if flags[name]), "NO_SINGLE_DOMINANT_BOTTLENECK")
    terminal = f"OBSA_PRIMARY_{primary}"
    if flags != result["hypothesis_flags"] or primary != result["primary_localisation"]:
        raise RuntimeError("LOCALISATION_FAIL")
    if terminal != result["terminal_state"]:
        raise RuntimeError("TERMINAL_FAIL")
    if result["reproduced_existing_central_collapse"] != bool(clean < 1.0 and noisy < 1.0):
        raise RuntimeError("REPRODUCTION_FLAG_FAIL")

    report = {
        "verifier": "PASS",
        "complete_identities": 80,
        "signature_shape": [80, 43],
        "input_hashes_verified": True,
        "scope_seal_verified": True,
        "layer_results_recomputed": recomputed,
        "hypothesis_flags_recomputed": flags,
        "primary_localisation_recomputed": primary,
        "terminal_state_recomputed": terminal,
        "diagnostic_contract_sha256": digest(ROOT / "diagnostic_contract.json"),
        "result_sha256": digest(ROOT / "result_summary.json"),
        "signature_sha256": signature_hashes,
        "validation_reads": 0,
        "final_test_read": False,
    }
    (ROOT / "independent_verification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("OBSA_INDEPENDENT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

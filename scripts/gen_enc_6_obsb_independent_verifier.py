"""Independent verifier for the OBS-B exact80 geometry-overlap diagnosis."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.actual_fluid_star_network import compile_member_geometry
from acoustic_encoder.gen_enc.robust_encoding_geometry import FAMILY_ORDER
from scripts.gen_enc_4_topology_preserving_m0_m1 import exact80_members


ROOT = REPO / "outputs/gen_enc/GEN_ENC_6_OBSB_GEOMETRY_OVERLAP"
OBSA_ROOT = REPO / "outputs/gen_enc/GEN_ENC_5_OBSA_READOUT_BOTTLENECK"
OBSA_RESULT = OBSA_ROOT / "result_summary.json"
OBSA_LOCAL = OBSA_ROOT / "local_full_clean_identity_signatures.npy"
MODEL_SOURCE = REPO / "src/acoustic_encoder/gen_enc/actual_fluid_star_network.py"
FAMILIES = tuple(FAMILY_ORDER)
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
GROUPS = {
    "VOLUME_ALLOCATION": np.arange(0, 4),
    "OUTER_APERTURE": np.arange(4, 8),
    "CENTRAL_WINDOW": np.arange(8, 12),
    "DISSIPATIVE_LOSS": np.arange(12, 16),
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_digest() -> str:
    hasher = hashlib.sha256()
    for _, _, path in exact80_members():
        hasher.update(path.relative_to(REPO).as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(digest(path).encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def independent_geometry_rows() -> tuple[np.ndarray, np.ndarray]:
    primary_rows = []
    realized_rows = []
    for _, member, _ in exact80_members():
        geometries = compile_member_geometry(member, spine_only=False)
        parameters = member["parameters"]
        target = np.log([item.target_volume_m3 for item in geometries])
        outer = np.log([item.outer_area_m2 for item in geometries])
        window = np.log([item.window_union_area_m2 for item in geometries])
        loss = np.asarray([parameters[f"loss_{item.angle}"] for item in geometries], dtype=float)
        root = np.asarray([item.root_length_m for item in geometries], dtype=float)
        primary = np.concatenate((target, outer, window, loss))
        primary_rows.append(primary)
        realized_rows.append(np.concatenate((primary, root)))
    return np.stack(primary_rows), np.stack(realized_rows)


def independent_separation(matrix: np.ndarray) -> dict[str, Any]:
    if matrix.shape[0] != 80 or not np.all(np.isfinite(matrix)):
        raise RuntimeError("MATRIX_SCOPE_FAIL")
    scale = np.std(matrix, axis=0, ddof=1)
    usable = scale > np.finfo(float).eps
    z = (matrix[:, usable] - np.mean(matrix[:, usable], axis=0)) / scale[usable]
    centroids = np.stack([np.mean(z[index * 20 : (index + 1) * 20], axis=0) for index in range(4)])
    within = np.asarray(
        [
            math.sqrt(
                float(
                    np.mean(
                        np.sum((z[index * 20 : (index + 1) * 20] - centroids[index]) ** 2, axis=1)
                    )
                )
            )
            for index in range(4)
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


def assert_equal(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    if actual["usable_dimensions"] != expected["usable_dimensions"]:
        raise RuntimeError("USABLE_DIMENSIONS_FAIL")
    if [row["families"] for row in actual["pairwise"]] != [row["families"] for row in expected["pairwise"]]:
        raise RuntimeError("PAIR_ORDER_FAIL")
    np.testing.assert_allclose(
        [actual["minimum_between_within_ratio"], actual["mean_between_within_ratio"]]
        + [row["ratio"] for row in actual["pairwise"]],
        [expected["minimum_between_within_ratio"], expected["mean_between_within_ratio"]]
        + [row["ratio"] for row in expected["pairwise"]],
        rtol=1e-13,
        atol=1e-15,
    )


def main() -> int:
    contract = load(ROOT / "diagnostic_contract.json")
    result = load(ROOT / "result_summary.json")
    if contract["schema_version"] != "gen_enc_6_obsb_contract_v1" or contract["members"] != 80:
        raise RuntimeError("CONTRACT_FAIL")
    expected_hashes = {
        "exact80_bundle": bundle_digest(),
        "obsa_result": digest(OBSA_RESULT),
        "obsa_local_signatures": digest(OBSA_LOCAL),
        "actual_fluid_star_model": digest(MODEL_SOURCE),
    }
    if contract["input_sha256"] != expected_hashes:
        raise RuntimeError("INPUT_HASH_FAIL")
    if any(
        (
            contract["candidate_ranking_emitted"],
            contract["parameter_search_performed"],
            contract["validation_reads"] != 0,
            contract["final_test_read"],
            contract["m3_authorized"],
            result["candidate_ranking_emitted"],
            result["parameter_search_performed"],
            result["validation_reads"] != 0,
            result["final_test_read"],
            result["m3_authorized"],
        )
    ):
        raise RuntimeError("SCOPE_SEAL_FAIL")

    geometry, realized = independent_geometry_rows()
    saved_geometry = np.load(ROOT / "primary_geometry_signatures.npy", allow_pickle=False)
    saved_realized = np.load(ROOT / "realized_geometry_with_root_signatures.npy", allow_pickle=False)
    np.testing.assert_array_equal(geometry, saved_geometry)
    np.testing.assert_array_equal(realized, saved_realized)
    if geometry.shape != (80, 16) or realized.shape != (80, 20):
        raise RuntimeError("SIGNATURE_SHAPE_FAIL")

    full = independent_separation(geometry)
    derived = independent_separation(realized)
    local = independent_separation(np.load(OBSA_LOCAL, allow_pickle=False))
    assert_equal(full, result["primary_geometry_separation"])
    assert_equal(derived, result["derived_root_sensitivity"])
    assert_equal(local, result["local_acoustic_separation_recomputed"])
    all_indices = np.arange(16)
    for name, indices in GROUPS.items():
        assert_equal(independent_separation(geometry[:, indices]), result["group_separation"][name])
        retained = np.setdiff1d(all_indices, indices, assume_unique=True)
        assert_equal(independent_separation(geometry[:, retained]), result["leave_one_group_out"][name])

    threshold = contract["thresholds"]["family_separation_ratio"]
    compression_limit = 1.0 - contract["thresholds"]["meaningful_acoustic_compression_fraction"]
    acoustic_equivalence = bool(
        full["minimum_between_within_ratio"] >= threshold
        and local["minimum_between_within_ratio"] < compression_limit * full["minimum_between_within_ratio"]
    )
    generator_overlap = bool(
        full["minimum_between_within_ratio"] < threshold
        and full["mean_between_within_ratio"] < threshold
    )
    dependency_limit = 1.0 - contract["thresholds"]["single_group_dependency_fraction"]
    dependency = {}
    for name, indices in GROUPS.items():
        retained = np.setdiff1d(all_indices, indices, assume_unique=True)
        value = independent_separation(geometry[:, retained])
        dependency[name] = bool(
            value["minimum_between_within_ratio"] < threshold
            and value["minimum_between_within_ratio"] < dependency_limit * full["minimum_between_within_ratio"]
        )
    primary = "ACOUSTIC_EQUIVALENCE" if acoustic_equivalence else "GENERATOR_OVERLAP" if generator_overlap else "MIXED_CAUSE"
    terminal = f"OBSB_PRIMARY_{primary}" if primary != "MIXED_CAUSE" else "OBSB_MIXED_CAUSE"
    flags = {
        "H1_ACOUSTIC_EQUIVALENCE": acoustic_equivalence,
        "H2_GENERATOR_OVERLAP": generator_overlap,
        "H3_MIXED_CAUSE": bool(not acoustic_equivalence and not generator_overlap),
        "H4_SINGLE_GROUP_DEPENDENCY": dependency,
    }
    if result["hypothesis_flags"] != flags or result["primary_localisation"] != primary or result["terminal_state"] != terminal:
        raise RuntimeError("LOCALISATION_OR_TERMINAL_FAIL")

    report = {
        "verifier": "PASS",
        "complete_identities": 80,
        "primary_signature_shape": [80, 16],
        "realized_signature_shape": [80, 20],
        "input_hashes_verified": True,
        "scope_seal_verified": True,
        "primary_geometry_separation_recomputed": full,
        "local_acoustic_separation_recomputed": local,
        "hypothesis_flags_recomputed": flags,
        "terminal_state_recomputed": terminal,
        "contract_sha256": digest(ROOT / "diagnostic_contract.json"),
        "result_sha256": digest(ROOT / "result_summary.json"),
        "primary_geometry_sha256": digest(ROOT / "primary_geometry_signatures.npy"),
        "realized_geometry_sha256": digest(ROOT / "realized_geometry_with_root_signatures.npy"),
        "validation_reads": 0,
        "final_test_read": False,
    }
    (ROOT / "independent_verification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("OBSB_INDEPENDENT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

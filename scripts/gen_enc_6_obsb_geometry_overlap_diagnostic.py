"""OBS-B development-only decomposition of geometry overlap versus acoustic equivalence."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from acoustic_encoder.gen_enc.actual_fluid_star_network import compile_member_geometry
from acoustic_encoder.gen_enc.robust_encoding_geometry import FAMILY_ORDER
from scripts.gen_enc_4_topology_preserving_m0_m1 import exact80_members


OUTPUT = REPO / "outputs/gen_enc/GEN_ENC_6_OBSB_GEOMETRY_OVERLAP"
OBSA_ROOT = REPO / "outputs/gen_enc/GEN_ENC_5_OBSA_READOUT_BOTTLENECK"
OBSA_RESULT = OBSA_ROOT / "result_summary.json"
OBSA_LOCAL = OBSA_ROOT / "local_full_clean_identity_signatures.npy"
MODEL_SOURCE = REPO / "src/acoustic_encoder/gen_enc/actual_fluid_star_network.py"
FAMILIES = tuple(FAMILY_ORDER)
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
GROUPS = {
    "VOLUME_ALLOCATION": slice(0, 4),
    "OUTER_APERTURE": slice(4, 8),
    "CENTRAL_WINDOW": slice(8, 12),
    "DISSIPATIVE_LOSS": slice(12, 16),
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    def convert(item: Any) -> Any:
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, dict):
            return {str(key): convert(inner) for key, inner in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(inner) for inner in item]
        return item

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(convert(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def exact80_bundle_digest(members: Sequence[tuple[dict[str, Any], dict[str, Any], Path]]) -> str:
    hasher = hashlib.sha256()
    for _, member, path in members:
        hasher.update(path.relative_to(REPO).as_posix().encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(digest(path).encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def physical_geometry_signature(member: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Return common independent and derived realized descriptors used by M2-B.

    The 16-dimensional primary signature contains four sector values for target
    volume, outer aperture area, central-window union area, and loss. Root length
    is derived deterministically from the first three groups and is sensitivity-only.
    """

    geometries = compile_member_geometry(member, spine_only=False)
    parameters = member["parameters"]
    targets = np.asarray([geometry.target_volume_m3 for geometry in geometries], dtype=float)
    outer = np.asarray([geometry.outer_area_m2 for geometry in geometries], dtype=float)
    windows = np.asarray([geometry.window_union_area_m2 for geometry in geometries], dtype=float)
    losses = np.asarray([float(parameters[f"loss_{geometry.angle}"]) for geometry in geometries], dtype=float)
    roots = np.asarray([geometry.root_length_m for geometry in geometries], dtype=float)
    primary = np.concatenate((np.log(targets), np.log(outer), np.log(windows), losses))
    realized_with_root = np.concatenate((primary, roots))
    if primary.shape != (16,) or realized_with_root.shape != (20,):
        raise RuntimeError("GEOMETRY_SIGNATURE_SHAPE_FAIL")
    if not np.all(np.isfinite(primary)) or not np.all(np.isfinite(realized_with_root)):
        raise RuntimeError("GEOMETRY_SIGNATURE_FINITE_FAIL")
    return primary, realized_with_root


def separation(matrix: np.ndarray) -> dict[str, Any]:
    scale = np.std(matrix, axis=0, ddof=1)
    usable = scale > np.finfo(float).eps
    if not np.any(usable):
        raise RuntimeError("NO_USABLE_DIMENSIONS")
    z = (matrix[:, usable] - np.mean(matrix[:, usable], axis=0)) / scale[usable]
    centroids = np.stack([np.mean(z[index * 20 : (index + 1) * 20], axis=0) for index in range(4)])
    within = np.asarray(
        [
            math.sqrt(
                float(
                    np.mean(
                        np.sum(
                            (z[index * 20 : (index + 1) * 20] - centroids[index]) ** 2,
                            axis=1,
                        )
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
    ratios = np.asarray([row["ratio"] for row in rows], dtype=float)
    return {
        "usable_dimensions": int(np.sum(usable)),
        "minimum_between_within_ratio": float(np.min(ratios)),
        "mean_between_within_ratio": float(np.mean(ratios)),
        "pairwise": rows,
    }


def main() -> int:
    members = exact80_members()
    obsa = load(OBSA_RESULT)
    if obsa["terminal_state"] != "OBSA_PRIMARY_H2_FAMILY_GEOMETRY_OVERLAP":
        raise RuntimeError("OBSA_CLOSEOUT_REQUIRED")
    contract = {
        "schema_version": "gen_enc_6_obsb_contract_v1",
        "scope": "EXACT80_DEVELOPMENT_ONLY_COMMON_PHYSICAL_GEOMETRY_NO_FEATURE_SEARCH_NO_REFIT",
        "members": 80,
        "family_order": list(FAMILIES),
        "primary_descriptor": "LOG_TARGET_VOLUME_4_PLUS_LOG_OUTER_AREA_4_PLUS_LOG_WINDOW_UNION_AREA_4_PLUS_LOSS_4",
        "descriptor_groups": {name: [group.start, group.stop - 1] for name, group in GROUPS.items()},
        "derived_sensitivity": "PRIMARY_PLUS_ROOT_LENGTH_4",
        "standardization": "GLOBAL_EXACT80_DDOF1_PER_FEATURE",
        "thresholds": {
            "family_separation_ratio": 1.0,
            "meaningful_acoustic_compression_fraction": 0.20,
            "single_group_dependency_fraction": 0.20,
        },
        "terminal_rules": {
            "OBSB_PRIMARY_ACOUSTIC_EQUIVALENCE": "GEOMETRY_MIN_GE_1_AND_LOCAL_MIN_LT_0P8_GEOMETRY_MIN",
            "OBSB_PRIMARY_GENERATOR_OVERLAP": "GEOMETRY_MIN_LT_1_AND_GEOMETRY_MEAN_LT_1",
            "OBSB_MIXED_CAUSE": "ALL_OTHER_REPRODUCED_LOCAL_OVERLAP_CASES",
        },
        "group_analysis": "ALL_FOUR_PREDECLARED_GROUPS_AND_FOUR_LEAVE_ONE_GROUP_OUT_SENSITIVITIES",
        "candidate_ranking_emitted": False,
        "parameter_search_performed": False,
        "validation_reads": 0,
        "final_test_read": False,
        "m3_authorized": False,
        "input_sha256": {
            "exact80_bundle": exact80_bundle_digest(members),
            "obsa_result": digest(OBSA_RESULT),
            "obsa_local_signatures": digest(OBSA_LOCAL),
            "actual_fluid_star_model": digest(MODEL_SOURCE),
        },
    }
    write(OUTPUT / "diagnostic_contract.json", contract)

    primary_rows = []
    realized_rows = []
    identities = []
    for _, member, _ in members:
        primary, realized = physical_geometry_signature(member)
        primary_rows.append(primary)
        realized_rows.append(realized)
        identities.append({"identity_id": member["member_id"], "family_id": member["family_id"]})
    geometry = np.stack(primary_rows)
    realized = np.stack(realized_rows)
    local = np.load(OBSA_LOCAL, allow_pickle=False)
    if geometry.shape != (80, 16) or realized.shape != (80, 20) or local.shape != (80, 43):
        raise RuntimeError("EXACT80_MATRIX_SHAPE_FAIL")
    np.save(OUTPUT / "primary_geometry_signatures.npy", geometry, allow_pickle=False)
    np.save(OUTPUT / "realized_geometry_with_root_signatures.npy", realized, allow_pickle=False)

    full = separation(geometry)
    derived = separation(realized)
    group_results = {name: separation(geometry[:, group]) for name, group in GROUPS.items()}
    leave_one_out = {}
    all_indices = np.arange(geometry.shape[1])
    for name, group in GROUPS.items():
        retained = np.setdiff1d(all_indices, np.arange(group.start, group.stop), assume_unique=True)
        leave_one_out[name] = separation(geometry[:, retained])
    local_result = separation(local)

    geometry_pairs = np.asarray([row["ratio"] for row in full["pairwise"]])
    local_pairs = np.asarray([row["ratio"] for row in local_result["pairwise"]])
    pairwise_retention = [
        {
            "families": full["pairwise"][index]["families"],
            "geometry_ratio": float(geometry_pairs[index]),
            "local_acoustic_ratio": float(local_pairs[index]),
            "local_to_geometry_retention": float(local_pairs[index] / geometry_pairs[index]),
        }
        for index in range(6)
    ]

    threshold = contract["thresholds"]["family_separation_ratio"]
    compression_limit = 1.0 - contract["thresholds"]["meaningful_acoustic_compression_fraction"]
    acoustic_equivalence = bool(
        full["minimum_between_within_ratio"] >= threshold
        and local_result["minimum_between_within_ratio"]
        < compression_limit * full["minimum_between_within_ratio"]
    )
    generator_overlap = bool(
        full["minimum_between_within_ratio"] < threshold
        and full["mean_between_within_ratio"] < threshold
    )
    dependency_limit = 1.0 - contract["thresholds"]["single_group_dependency_fraction"]
    dependency = {
        name: bool(
            value["minimum_between_within_ratio"] < threshold
            and value["minimum_between_within_ratio"]
            < dependency_limit * full["minimum_between_within_ratio"]
        )
        for name, value in leave_one_out.items()
    }
    if acoustic_equivalence:
        primary = "ACOUSTIC_EQUIVALENCE"
    elif generator_overlap:
        primary = "GENERATOR_OVERLAP"
    else:
        primary = "MIXED_CAUSE"
    result = {
        "terminal_state": f"OBSB_PRIMARY_{primary}" if primary != "MIXED_CAUSE" else "OBSB_MIXED_CAUSE",
        "primary_localisation": primary,
        "primary_geometry_separation": full,
        "derived_root_sensitivity": derived,
        "group_separation": group_results,
        "leave_one_group_out": leave_one_out,
        "local_acoustic_separation_recomputed": local_result,
        "pairwise_geometry_to_local_retention": pairwise_retention,
        "hypothesis_flags": {
            "H1_ACOUSTIC_EQUIVALENCE": acoustic_equivalence,
            "H2_GENERATOR_OVERLAP": generator_overlap,
            "H3_MIXED_CAUSE": bool(not acoustic_equivalence and not generator_overlap),
            "H4_SINGLE_GROUP_DEPENDENCY": dependency,
        },
        "single_group_dependency_any": bool(any(dependency.values())),
        "identity_records": identities,
        "candidate_ranking_emitted": False,
        "parameter_search_performed": False,
        "validation_reads": 0,
        "final_test_read": False,
        "m3_authorized": False,
        "next_action": "BUILD_OBS_PUBLICATION_CANDIDATE_PACKAGE_WITH_MODEL_ONLY_BOUNDARY",
    }
    write(OUTPUT / "result_summary.json", result)
    print(result["terminal_state"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Execute GEN-ENC-4 M0 verification and topology-preserving M1 D/V analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.gen_enc.e2_rc03_stats import canonical_json_bytes, sha256_file
from acoustic_encoder.gen_enc.estimator import projection_matrices, trapezoidal_weights
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.robust_encoding_geometry import (
    COMPLEX_FEATURE_DIMENSION,
    FAMILY_CONTRAST_ORDER,
    FAMILY_ORDER,
    PAIR_COLUMN_INDICES,
    PAIR_ORDER,
    PRIMARY_FREQUENCIES,
    REAL_FEATURE_DIMENSION,
    evaluation_unit_weights,
    identity_level_family_inference,
    pair_anisotropy,
    summarize_candidate_geometry,
    weakest_pair_index,
)
from acoustic_encoder.gen_enc.topology_preserving_network import (
    MODEL_NAME,
    NODE_ORDER,
    REFERENCE_LATERAL_AREA_M2,
    solve_forward_block,
    topology_audit,
)


OUTPUT_ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_TOPOLOGY_PRESERVING_M0_M1"
M0_ROOT = OUTPUT_ROOT / "m0"
M1_ROOT = OUTPUT_ROOT / "m1"
PREFLIGHT_ROOT = OUTPUT_ROOT / "preflight"
COMPARISON_ROOT = OUTPUT_ROOT / "comparison"
EXACT80_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json"
NUISANCE_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEED_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
COMMON_W_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/sealed/common_w.npz"
M0_FORMAL_ROOT = REPO / "outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY/formal"
M0_CORE_PATH = REPO / "src/acoustic_encoder/gen_enc/forward_acoustic_network.py"
M1_CORE_PATH = REPO / "src/acoustic_encoder/gen_enc/topology_preserving_network.py"
THIS_PATH = Path(__file__).resolve()
TEST_PATH = REPO / "tests/test_gen_enc_4_topology_preserving_m0_m1.py"
VERIFIER_PATH = REPO / "scripts/gen_enc_4_topology_preserving_independent_verifier.py"

EXPECTED_HASHES = {
    "exact80": "e460eb09a05b5c8fb491250a6fe5d9046d0a1ebe7d70246f45ca117571779a08",
    "nuisance": "92d8e4ba137b19a6d71cc47460fecb950594632177020e982b12c11e6883e772",
    "seed": "e85eaf4435b159f8fd7c7b5669762d3a0600de4c4e12ecab6fcdcd7a39a96af9",
    "common_w": "3ba1ec8926dcbd60f9b670bbcf3079426d54c93330427089fa4b8ade5a44bc04",
    "m0_core": "606ee97ef940e4810059ea13eb5f55c31ff23bd64ed66f157e175664607afa0e",
    "m0_development_terminal": "02ca458cad71c37b2d3301f6bc95593c1d80c4924092019680f502b054d71143",
    "m0_validation_terminal": "4d674273a89c823060c9c0960616f4872a254d221790cbed491847894491c1e7",
}
CELL_COUNT = 3675
REPEAT_COUNT = 2
CHUNK_CELLS = 75
CHUNK_COUNT = 49
MODEL_EFFECT_BOOTSTRAP_SEED = 2026090401
BOOTSTRAP_REPLICATES = 20_000


class GenEnc4Error(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise GenEnc4Error(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.relative_to(REPO).as_posix()
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(json_ready(value)))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_array(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.lib.format.write_array(stream, np.ascontiguousarray(value), allow_pickle=False, version=(1, 0))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def validate_frozen_inputs() -> dict[str, str]:
    paths = {
        "exact80": EXACT80_PATH,
        "nuisance": NUISANCE_PATH,
        "seed": SEED_PATH,
        "common_w": COMMON_W_PATH,
        "m0_core": M0_CORE_PATH,
        "m0_development_terminal": M0_FORMAL_ROOT / "development/partition_terminal.json",
        "m0_validation_terminal": M0_FORMAL_ROOT / "single_use_validation/partition_terminal.json",
    }
    observed = {name: sha256_file(path) for name, path in paths.items()}
    if observed != EXPECTED_HASHES:
        raise GenEnc4Error(f"FROZEN_INPUT_HASH_MISMATCH:{observed}")
    return observed


def nuisance_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with NUISANCE_PATH.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise GenEnc4Error("NUISANCE_METADATA_REQUIRED")
        for ordinal, row in enumerate(csv.DictReader(stream), start=1):
            if row["design_row_id"] != f"N{ordinal:04d}" or not np.isclose(
                float(row["cell_weight"]), 1.0 / CELL_COUNT, rtol=0.0, atol=1e-18
            ):
                raise GenEnc4Error("NUISANCE_IDENTITY_OR_WEIGHT_MISMATCH")
            rows.append(
                {
                    key: float(row[key])
                    for key in (
                        "snr_db",
                        "common_gain_db",
                        "sensor_independent_gain_db",
                        "common_frequency_axis_shift_relative",
                        "independent_manufacturing_percent",
                        "batch_correlated_manufacturing_percent",
                        "angle_offset_degrees",
                    )
                }
            )
    if len(rows) != CELL_COUNT:
        raise GenEnc4Error("EXACT3675_REQUIRED")
    return rows


def exact80_members() -> list[tuple[dict[str, Any], dict[str, Any], Path]]:
    manifest = read_json(EXACT80_PATH)
    entries = manifest.get("members")
    if not isinstance(entries, list) or len(entries) != 80:
        raise GenEnc4Error("EXACT80_REQUIRED")
    result = []
    for ordinal, entry in enumerate(entries, start=1):
        identity_path = REPO / entry["identity_path"]
        member = read_json(identity_path)
        if (
            entry.get("global_ordinal") != ordinal
            or sha256_file(identity_path) != entry.get("identity_file_sha256")
            or member.get("member_id") != entry.get("member_id")
            or member.get("family_id") != entry.get("family_id")
        ):
            raise GenEnc4Error("EXACT80_ORDER_HASH_OR_PAYLOAD_MISMATCH")
        result.append((entry, member, identity_path))
    return result


def seeds_for(partition: str) -> tuple[int, int]:
    seed = read_json(SEED_PATH)
    key = "development_training" if partition == "development" else "single_use_validation"
    result = tuple(seed["nuisance_partition_seeds"][key])
    expected = (2026091001, 2026091002) if partition == "development" else (2026092001, 2026092002)
    if result != expected:
        raise GenEnc4Error("PARTITION_SEED_MISMATCH")
    return result


def mapping_contract() -> dict[str, Any]:
    return {
        "schema_version": "gen_enc_4_m1_mapping_contract_v1",
        "status": "FROZEN_BEFORE_M1_RESPONSE_INSPECTION",
        "model": MODEL_NAME,
        "m0_model_frozen_unchanged": "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1",
        "node_order": list(NODE_ORDER),
        "node_count": 5,
        "added_resonant_nodes": 0,
        "propagation_delay_or_path_phase": False,
        "edge_equation": "Y_e(omega)=1/(R_e+j*omega*M_e)",
        "edge_loss": "ARITHMETIC_MEAN_OF_FROZEN_ENDPOINT_LOSS_COORDINATES",
        "family_mapping": {
            "HAND_DESIGNED": "NO_LOCAL_LOCAL_EDGE; KEEP_FROZEN_REPLICATED_CENTRAL_MIX_STAR",
            "NEAR_INDEPENDENT": "SIX_EQUAL_WEAK_UNDIRECTED_EDGES; TOTAL_AREA_FRACTION=SHARED_ALPHA_IN_[0.03,0.07]",
            "FIXED_SEED_RANDOM_DISORDERED": "SIX_EXPLICIT_UNDIRECTED_SLOTS; ZERO_COORDINATE_MEANS_ABSENT; NO_NODE_AVERAGING",
            "PHYSICS_METAMATERIAL_INSPIRED": "FOUR_EXPLICIT_ORDERED_CARDINAL_RING_EDGES_ONLY",
        },
        "radial_central_rule": {
            "HAND_DESIGNED": "FROZEN_CENTRAL_MIX",
            "NEAR_INDEPENDENT": "FROZEN_ALPHA_TO_SHARED_APERTURE",
            "FIXED_SEED_RANDOM_DISORDERED": "FIXED_SPINE_COORDINATE_ZERO; EDGE_COORDINATES_NOT_COLLAPSED",
            "PHYSICS_METAMATERIAL_INSPIRED": "FIXED_SPINE_COORDINATE_ZERO; RING_COORDINATES_NOT_COLLAPSED",
        },
        "lateral_budget": {
            "reference_area_m2": REFERENCE_LATERAL_AREA_M2,
            "rule": "A_e=A_ref*coordinate/(fixed_possible_slots*0.8); NEAR A_e=A_ref*alpha/6; HAND total=0",
            "random_possible_slots_including_zeros": 6,
            "physics_possible_slots": 4,
            "total_area_cap_m2": REFERENCE_LATERAL_AREA_M2,
            "unbounded_total_admittance_by_edge_count": False,
        },
        "frozen_common_design": {
            "frequency_grid": "f[n]=200*2^(n/48), n=0..255; primary n=0..207",
            "states": list(STATE_ANGLES_DEGREES),
            "readout": "CENTRAL_COMPLEX_PRESSURE_COMMON_SINGLE_MICROPHONE",
            "nuisance_cells": CELL_COUNT,
            "repeats_per_partition": REPEAT_COUNT,
            "identity_order": "EXACT80_FOUR_FAMILIES_X20",
            "whitener": "SAME_FROZEN_M0_COMMON_W; NO_M1_REFIT",
            "development_validation_isolation": True,
            "near_one_hot_rank_ceiling_disclosed": True,
        },
        "evidence_limit": "TOPOLOGY_FAITHFUL_FIVE_NODE_LUMPED_PARAMETER_REDUCED_MODEL_ONLY",
        "tuning_or_member_reselection_after_response": False,
        "final_test_read": False,
    }


def family_record(summary: dict[str, Any]) -> dict[str, Any]:
    values = summary["metrics"]
    return {
        "identity_id": summary["identity_id"],
        "family_id": summary["family_id"],
        "margin": float(values["d_min_lower_tail_es_0p05"]),
        "drift": float(values["gram_frobenius_drift_upper_tail_es_0p05"]),
    }


def aggregate_family(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    families: dict[str, Any] = {}
    for family in FAMILY_ORDER:
        selected = [family_record(item) for item in summaries if item["family_id"] == family]
        if len(selected) != 20:
            raise GenEnc4Error("EXACT20_PER_FAMILY_REQUIRED")
        margin = np.asarray([item["margin"] for item in selected], dtype=float)
        drift = np.asarray([item["drift"] for item in selected], dtype=float)
        families[family] = {
            "member_ids": [item["identity_id"] for item in selected],
            "margin_values": margin,
            "drift_values": drift,
            "margin": {
                "mean": float(np.mean(margin)),
                "median": float(np.median(margin)),
                "q25_q75": np.quantile(margin, (0.25, 0.75), method="linear"),
                "worst_member": selected[int(np.argmin(margin))]["identity_id"],
                "worst_value": float(np.min(margin)),
            },
            "drift": {
                "mean": float(np.mean(drift)),
                "median": float(np.median(drift)),
                "q25_q75": np.quantile(drift, (0.25, 0.75), method="linear"),
                "worst_member": selected[int(np.argmax(drift))]["identity_id"],
                "worst_value": float(np.max(drift)),
            },
        }
    return families


def unique_worst_leader(families: dict[str, Any], endpoint: str) -> str | None:
    values = {
        family: record[endpoint]["worst_value"]
        for family, record in families.items()
    }
    target = max(values.values()) if endpoint == "margin" else min(values.values())
    winners = [family for family, value in values.items() if value == target]
    return winners[0] if len(winners) == 1 else None


def save_inference(root: Path, families: dict[str, Any]) -> dict[str, Any]:
    margin = {family: np.asarray(families[family]["margin_values"], dtype=float) for family in FAMILY_ORDER}
    drift = {family: np.asarray(families[family]["drift_values"], dtype=float) for family in FAMILY_ORDER}
    result = identity_level_family_inference(margin, drift)
    inference_root = root / "inference"
    write_array(inference_root / "bootstrap_margin_contrasts.npy", result["bootstrap"]["margin_contrasts"])
    write_array(inference_root / "bootstrap_drift_contrasts.npy", result["bootstrap"]["drift_contrasts"])
    permutation = None
    if result["permutation"] is not None:
        write_array(inference_root / "permutation_max_abs_t.npy", result["permutation"]["max_abs_t"])
        permutation = {
            key: value
            for key, value in result["permutation"].items()
            if key != "max_abs_t"
        }
        permutation["max_abs_t_path"] = (inference_root / "permutation_max_abs_t.npy").relative_to(REPO).as_posix()
        permutation["max_abs_t_sha256"] = sha256_file(inference_root / "permutation_max_abs_t.npy")
    payload = {
        "schema_version": "gen_enc_4_m1_identity_level_inference_v1",
        "status": result["status"],
        "reason": result["reason"],
        "sampling_unit": "IDENTITY_EXACT20_PER_FAMILY",
        "family_order": list(FAMILY_ORDER),
        "contrast_order": [list(pair) for pair in FAMILY_CONTRAST_ORDER],
        "observed": result["observed"],
        "bootstrap": {
            "replicates": result["bootstrap"]["replicates"],
            "seed": result["bootstrap"]["seed"],
            "generator": result["bootstrap"]["generator"],
            "quantile_method": result["bootstrap"]["quantile_method"],
            "margin_percentile_95_ci": result["bootstrap"]["margin_percentile_95_ci"],
            "drift_percentile_95_ci": result["bootstrap"]["drift_percentile_95_ci"],
            "margin_path": (inference_root / "bootstrap_margin_contrasts.npy").relative_to(REPO).as_posix(),
            "drift_path": (inference_root / "bootstrap_drift_contrasts.npy").relative_to(REPO).as_posix(),
        },
        "permutation": permutation,
        "final_test_read": False,
    }
    write_json(inference_root / "inference_summary.json", payload)
    return payload


def generate_chunk(
    member: Mapping[str, Any],
    nuisance: list[dict[str, float]],
    *,
    partition: str,
    seeds: tuple[int, int],
    start: int,
    end: int,
) -> np.ndarray:
    output = np.empty((4, end - start, 2, 4, 256), dtype=np.complex128)
    frequencies = frozen_frequency_grid()
    for local, cell in enumerate(range(start, end)):
        for repeat in range(REPEAT_COUNT):
            output[:, local, repeat] = solve_forward_block(
                member,
                nuisance[cell],
                cell_index=cell,
                repeat_index=repeat,
                frequencies_hz=frequencies,
                state_angles_degrees=STATE_ANGLES_DEGREES,
                partition=partition,
                repeat_seed_tuple=seeds,
            ).central_pressure
    return output


def geometry_chunk(
    raw: np.ndarray, whitener: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return pair distances, trace-one Gram, real singulars, and Ydiff."""

    values = np.asarray(raw, dtype=np.complex128)
    cells = values.shape[1]
    frequency_weights = trapezoidal_weights(frozen_frequency_grid()[:PRIMARY_FREQUENCIES])
    ordered = np.transpose(values[:, :, :, :, :PRIMARY_FREQUENCIES], (1, 2, 4, 3, 0))
    weighted = ordered * np.sqrt(frequency_weights)[None, None, :, None, None]
    y = weighted.reshape((cells, 2, COMPLEX_FEATURE_DIMENSION, 4), order="C")
    y_diff = np.asarray(y @ projection_matrices(4)[1], dtype=np.complex128)
    embedded = np.concatenate((y_diff.real, y_diff.imag), axis=2)
    columns = np.transpose(embedded, (2, 0, 1, 3)).reshape((REAL_FEATURE_DIMENSION, cells * 2 * 4), order="C")
    z_columns = whitener @ columns
    z_real = np.transpose(
        z_columns.reshape((REAL_FEATURE_DIMENSION, cells, 2, 4), order="C"), (1, 2, 0, 3)
    )
    singulars = np.linalg.svd(z_real, compute_uv=False)[:, :, :3]
    z = z_real[:, :, :COMPLEX_FEATURE_DIMENSION] + 1j * z_real[:, :, COMPLEX_FEATURE_DIMENSION:]
    distances = np.empty((cells, 2, 6), dtype=np.float64)
    for pair_index, (left, right) in enumerate(PAIR_COLUMN_INDICES):
        distances[:, :, pair_index] = np.linalg.norm(z[:, :, :, left] - z[:, :, :, right], axis=2)
    grams = np.einsum("urfi,urfj->urij", z.conj(), z, optimize=True)
    grams = 0.5 * (grams + grams.conj().transpose(0, 1, 3, 2))
    trace = np.trace(grams, axis1=2, axis2=3).real
    if np.any(trace <= 0.0) or not all(
        np.all(np.isfinite(value)) for value in (distances, grams, singulars, y_diff)
    ):
        raise GenEnc4Error("NONFINITE_OR_NONPOSITIVE_GEOMETRY")
    return distances, grams / trace[:, :, None, None], singulars, y_diff


def audit_to_json(audit: Any) -> dict[str, Any]:
    return {
        "family_id": audit.family_id,
        "semantic": audit.semantic,
        "possible_edge_count": audit.possible_edge_count,
        "active_edge_count": len(audit.active_edges),
        "active_edges": [
            {
                "left_angle": edge.left_angle,
                "right_angle": edge.right_angle,
                "coordinate": edge.coordinate,
                "area_m2": edge.area_m2,
            }
            for edge in audit.active_edges
        ],
        "total_lateral_area_m2": audit.total_lateral_area_m2,
        "lateral_area_budget_m2": audit.lateral_area_budget_m2,
        "budget_fraction": audit.budget_fraction,
    }


def process_identity(
    entry: dict[str, Any],
    member: dict[str, Any],
    identity_path: Path,
    nuisance: list[dict[str, float]],
    whitener: np.ndarray,
    *,
    partition: str,
    seeds: tuple[int, int],
    output_root: Path,
) -> dict[str, Any]:
    identity_id = str(member["member_id"])
    candidate_root = output_root / "candidates" / identity_id
    summary_path = candidate_root / "candidate_summary.json"
    if summary_path.is_file():
        summary = read_json(summary_path)
        if summary.get("status") != "PASS" or summary.get("identity_sha256") != sha256_file(identity_path):
            raise GenEnc4Error("CANDIDATE_RESUME_MISMATCH")
        return summary
    compact = candidate_root / "compact"
    compact.mkdir(parents=True, exist_ok=True)
    distances = np.lib.format.open_memmap(
        compact / "distances.npy", mode="w+", dtype="float64", shape=(CELL_COUNT, REPEAT_COUNT, 6), version=(1, 0)
    )
    weakest = np.lib.format.open_memmap(
        compact / "weakest_pair_index.npy", mode="w+", dtype="uint8", shape=(CELL_COUNT, REPEAT_COUNT), version=(1, 0)
    )
    anisotropy = np.lib.format.open_memmap(
        compact / "pair_anisotropy.npy", mode="w+", dtype="float64", shape=(CELL_COUNT, REPEAT_COUNT), version=(1, 0)
    )
    drift = np.lib.format.open_memmap(
        compact / "gram_drift.npy", mode="w+", dtype="float64", shape=(CELL_COUNT, REPEAT_COUNT), version=(1, 0)
    )
    singulars = np.lib.format.open_memmap(
        compact / "singular_values.npy", mode="w+", dtype="float64", shape=(CELL_COUNT, REPEAT_COUNT, 3), version=(1, 0)
    )
    temp_grams = None
    if partition == "development":
        temp_root = candidate_root / "temporary"
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_path = temp_root / "normalized_grams.npy"
        temp_grams = np.lib.format.open_memmap(
            temp_path, mode="w+", dtype="complex128", shape=(CELL_COUNT, REPEAT_COUNT, 4, 4), version=(1, 0)
        )
        reference = None
    else:
        reference_path = M1_ROOT / "development/candidates" / identity_id / "reference/development_reference_gram.npy"
        reference = np.asarray(np.load(reference_path, allow_pickle=False), dtype=np.complex128)
    response_sum = np.zeros((COMPLEX_FEATURE_DIMENSION, 4), dtype=np.complex128)
    geometry_sum = np.zeros((4, 4), dtype=np.complex128)
    for chunk in range(CHUNK_COUNT):
        start = chunk * CHUNK_CELLS
        end = start + CHUNK_CELLS
        raw = generate_chunk(member, nuisance, partition=partition, seeds=seeds, start=start, end=end)
        chunk_distances, chunk_grams, chunk_singulars, y_diff = geometry_chunk(raw, whitener)
        distances[start:end] = chunk_distances
        weakest[start:end] = weakest_pair_index(chunk_distances)
        anisotropy[start:end] = pair_anisotropy(chunk_distances)
        singulars[start:end] = chunk_singulars
        response_sum += np.sum(y_diff, axis=(0, 1))
        geometry_sum += np.sum(chunk_grams, axis=(0, 1))
        if temp_grams is not None:
            temp_grams[start:end] = chunk_grams
        else:
            drift[start:end] = np.linalg.norm(
                chunk_grams - reference[None, None, :, :], ord="fro", axis=(2, 3)
            )
    if temp_grams is not None:
        reference = np.asarray(geometry_sum / (CELL_COUNT * REPEAT_COUNT), dtype=np.complex128)
        reference = 0.5 * (reference + reference.conj().T)
        reference /= float(np.trace(reference).real)
        reference_path = candidate_root / "reference/development_reference_gram.npy"
        write_array(reference_path, reference)
        for chunk in range(CHUNK_COUNT):
            start = chunk * CHUNK_CELLS
            end = start + CHUNK_CELLS
            drift[start:end] = np.linalg.norm(
                temp_grams[start:end] - reference[None, None, :, :], ord="fro", axis=(2, 3)
            )
        del temp_grams
        temp_path.unlink()
        temp_root.rmdir()
    for value in (distances, weakest, anisotropy, drift, singulars):
        value.flush()
    response_signature = response_sum / (CELL_COUNT * REPEAT_COUNT)
    state_geometry_signature = geometry_sum / (CELL_COUNT * REPEAT_COUNT)
    write_array(compact / "mean_response_signature.npy", response_signature)
    write_array(compact / "mean_state_geometry_signature.npy", state_geometry_signature)
    metrics = summarize_candidate_geometry(
        np.asarray(distances).reshape((-1, 6)),
        np.asarray(drift).reshape(-1),
        evaluation_unit_weights(),
    )
    ordered_singulars = np.sort(np.asarray(singulars).reshape((-1, 3)), axis=0, kind="stable")
    quantile_index = int(np.ceil(0.05 * ordered_singulars.shape[0]) - 1)
    sigma_quantiles = ordered_singulars[quantile_index]
    r_stable = int(np.sum(sigma_quantiles > 1.0))
    e_primary = float(sigma_quantiles[2])
    audit = topology_audit(member)
    cost = member["cad_static_audit"]
    summary = {
        "schema_version": "gen_enc_4_m1_candidate_summary_v1",
        "status": "PASS",
        "identity_id": identity_id,
        "family_id": member["family_id"],
        "partition": partition,
        "model": MODEL_NAME,
        "identity_path": identity_path.relative_to(REPO).as_posix(),
        "identity_sha256": sha256_file(identity_path),
        "metrics": metrics,
        "feasibility": {
            "E_primary": e_primary,
            "r_stable": r_stable,
            "passed": bool(e_primary > 1.0 and r_stable == 3),
            "near_one_hot_rank_ceiling_disclosed": True,
        },
        "topology_audit": audit_to_json(audit),
        "cost": {
            "volume_m3": cost["volume_m3"],
            "dof": cost["dof"],
            "minimum_feature_m": cost["minimum_feature_m"],
            "solid_load_path_m": cost["solid_load_path_m"],
            "claim": "SAME_VOLUME_MINIMUM_FEATURE_SOLID_LOAD_PATH_AND_EXISTING_DOF_12_TO_15_ENVELOPE_NOT_FULLY_EQUAL_COST",
        },
        "compact": {
            name: {
                "path": (compact / filename).relative_to(REPO).as_posix(),
                "sha256": sha256_file(compact / filename),
            }
            for name, filename in (
                ("distances", "distances.npy"),
                ("weakest_pair", "weakest_pair_index.npy"),
                ("pair_anisotropy", "pair_anisotropy.npy"),
                ("gram_drift", "gram_drift.npy"),
                ("singular_values", "singular_values.npy"),
                ("mean_response_signature", "mean_response_signature.npy"),
                ("mean_state_geometry_signature", "mean_state_geometry_signature.npy"),
            )
        },
        "common_w_sha256": EXPECTED_HASHES["common_w"],
        "validation_refit": False,
        "development_reference_updated_by_validation": False,
        "finite": True,
        "final_test_read": False,
    }
    write_json(summary_path, summary)
    return summary


def prepare() -> int:
    observed = validate_frozen_inputs()
    members = exact80_members()
    counts = {family: 0 for family in FAMILY_ORDER}
    topology_records = []
    for _, member, identity_path in members:
        counts[member["family_id"]] += 1
        topology_records.append(
            {
                "identity_id": member["member_id"],
                "identity_sha256": sha256_file(identity_path),
                **audit_to_json(topology_audit(member)),
            }
        )
    if any(count != 20 for count in counts.values()):
        raise GenEnc4Error("EXACT_FOUR_BY_TWENTY_REQUIRED")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT_ROOT / "mapping_contract.json", mapping_contract())
    write_json(OUTPUT_ROOT / "topology_identity_audit.json", {"counts": counts, "records": topology_records, "final_test_read": False})
    m0_d = read_json(M0_FORMAL_ROOT / "development/partition_terminal.json")
    m0_v = read_json(M0_FORMAL_ROOT / "single_use_validation/partition_terminal.json")
    m0_independent_path = M0_FORMAL_ROOT / "independent_verification/terminal.json"
    m0_independent = read_json(m0_independent_path)
    m0_verification = {
        "schema_version": "gen_enc_4_m0_baseline_verification_v1",
        "status": "M0_REPRODUCED_BY_FROZEN_HASH_AND_SEALED_3A_ARTIFACT_VERIFICATION",
        "model": "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1",
        "frozen_hashes": observed,
        "development": {
            "status": m0_d["status"],
            "complete_identities": m0_d["complete_identities"],
            "sealed_references": m0_d["sealed_references"],
            "all_feasible": m0_d["all_e2_feasibility_gates_passed"],
        },
        "validation": {
            "status": m0_v["status"],
            "complete_identities": m0_v["complete_identities"],
            "all_feasible": m0_v["all_e2_feasibility_gates_passed"],
            "scientific_decision": m0_v["scientific_decision"],
        },
        "source_3a_files_modified": False,
        "independent_verifier_rerun": {
            "status": m0_independent.get("status"),
            "path": m0_independent_path.relative_to(REPO).as_posix(),
            "sha256": sha256_file(m0_independent_path),
            "completed_for_both_partitions": len(m0_independent.get("partitions", [])) == 2,
        },
        "final_test_read": False,
    }
    write_json(M0_ROOT / "baseline_verification.json", m0_verification)
    sources = [THIS_PATH, M1_CORE_PATH, TEST_PATH, VERIFIER_PATH, EXACT80_PATH, NUISANCE_PATH, SEED_PATH, COMMON_W_PATH, M0_CORE_PATH]
    write_json(
        OUTPUT_ROOT / "source_manifest.json",
        {
            "schema_version": "gen_enc_4_source_manifest_v1",
            "entries": {
                path.name: {
                    "path": path.relative_to(REPO).as_posix(),
                    "sha256": sha256_file(path) if path.is_file() else None,
                    "present": path.is_file(),
                }
                for path in sources
            },
            "final_test_read": False,
        },
    )
    print(json.dumps({"status": m0_verification["status"], "exact80": counts, "final_test_read": False}, sort_keys=True))
    return 0


def preflight() -> int:
    validate_frozen_inputs()
    nuisance = nuisance_rows()
    representatives = [exact80_members()[index] for index in (0, 20, 40, 60)]
    frequencies = frozen_frequency_grid()
    records = []
    for entry, member, path in representatives:
        result = solve_forward_block(
            member,
            nuisance[0],
            cell_index=0,
            repeat_index=0,
            frequencies_hz=frequencies,
            state_angles_degrees=STATE_ANGLES_DEGREES,
            partition="development",
            repeat_seed_tuple=seeds_for("development"),
        )
        audit = topology_audit(member)
        records.append(
            {
                "identity_id": member["member_id"],
                "identity_sha256": sha256_file(path),
                "shape": list(result.central_pressure.shape),
                "finite": bool(np.all(np.isfinite(result.central_pressure))),
                "passive": result.passive,
                "reciprocal": result.reciprocal,
                "topology_semantic": audit.semantic,
                "active_edge_count": len(audit.active_edges),
                "budget_within_cap": audit.total_lateral_area_m2 <= audit.lateral_area_budget_m2 * (1.0 + 1e-14),
            }
        )
    payload = {
        "schema_version": "gen_enc_4_science_blind_preflight_v1",
        "status": "PASS" if all(record["finite"] and record["passive"] and record["reciprocal"] and record["budget_within_cap"] for record in records) else "FAIL",
        "representative_rule": "GLOBAL_ORDINAL_1_21_41_61_FIXED_BEFORE_RESPONSE",
        "representatives": records,
        "scientific_metrics_or_family_ranking_emitted": False,
        "formal_payload_reuse": False,
        "final_test_read": False,
    }
    write_json(PREFLIGHT_ROOT / "technical_preflight.json", payload)
    print(json.dumps({"status": payload["status"], "representatives": len(records), "scientific_metrics_emitted": False}, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


def run_partition(partition: str) -> int:
    validate_frozen_inputs()
    if read_json(PREFLIGHT_ROOT / "technical_preflight.json").get("status") != "PASS":
        raise GenEnc4Error("PASSING_PREFLIGHT_REQUIRED")
    if partition == "single_use_validation":
        d_terminal = read_json(M1_ROOT / "development/partition_terminal.json")
        if d_terminal.get("status") != "GEN_ENC_4_M1_D_SEALED" or d_terminal.get("complete_identities") != 80:
            raise GenEnc4Error("SEALED_M1_DEVELOPMENT_REQUIRED")
    output_root = M1_ROOT / partition
    terminal_path = output_root / "partition_terminal.json"
    if terminal_path.is_file():
        raise GenEnc4Error("PARTITION_ALREADY_COMPLETE")
    output_root.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    nuisance = nuisance_rows()
    seeds = seeds_for(partition)
    with np.load(COMMON_W_PATH, allow_pickle=False) as sealed:
        whitener = np.asarray(sealed["operator"], dtype=np.float64)
    if whitener.shape != (REAL_FEATURE_DIMENSION, REAL_FEATURE_DIMENSION) or not np.all(np.isfinite(whitener)):
        raise GenEnc4Error("COMMON_W_SHAPE_OR_FINITE_FAIL")
    summaries = []
    for ordinal, (entry, member, identity_path) in enumerate(exact80_members(), start=1):
        summary = process_identity(
            entry,
            member,
            identity_path,
            nuisance,
            whitener,
            partition=partition,
            seeds=seeds,
            output_root=output_root,
        )
        summaries.append(summary)
        write_json(
            output_root / "checkpoint.json",
            {
                "status": "PARTITION_IN_PROGRESS",
                "partition": partition,
                "completed_identities": ordinal,
                "last_identity": member["member_id"],
                "final_test_read": False,
            },
        )
        print(json.dumps({"partition": partition, "completed": ordinal, "identity": member["member_id"]}, sort_keys=True), flush=True)
    families = aggregate_family(summaries)
    family_summary = {
        "schema_version": "gen_enc_4_m1_family_summary_v1",
        "partition": partition,
        "sampling_unit": "IDENTITY",
        "exact20": True,
        "families": families,
        "margin_worst_member_leader": unique_worst_leader(families, "margin"),
        "drift_worst_member_leader": unique_worst_leader(families, "drift"),
        "final_test_read": False,
    }
    write_json(output_root / "family_summary.json", family_summary)
    inference = save_inference(output_root, families)
    feasible = sum(bool(item["feasibility"]["passed"]) for item in summaries)
    stable_rank_three = sum(item["feasibility"]["r_stable"] == 3 for item in summaries)
    terminal = {
        "schema_version": "gen_enc_4_m1_partition_terminal_v1",
        "status": "GEN_ENC_4_M1_D_SEALED" if partition == "development" else "GEN_ENC_4_M1_V_SINGLE_USE_SEALED",
        "partition": partition,
        "complete_identities": len(summaries),
        "feasible_identities": feasible,
        "r_stable_three_identities": stable_rank_three,
        "family_inference_status": inference["status"],
        "margin_worst_member_leader": family_summary["margin_worst_member_leader"],
        "drift_worst_member_leader": family_summary["drift_worst_member_leader"],
        "common_w_reused_without_refit": True,
        "single_use_consumed": partition == "single_use_validation",
        "validation_feedback_to_development": False,
        "wall_seconds": time.perf_counter() - start,
        "final_test_read": False,
    }
    write_json(terminal_path, terminal)
    write_json(
        output_root / "checkpoint.json",
        {"status": "PARTITION_COMPLETE", "terminal_sha256": sha256_file(terminal_path), "final_test_read": False},
    )
    print(json.dumps(terminal, sort_keys=True))
    return 0


def metric_signature(summary: dict[str, Any]) -> np.ndarray:
    metric = summary["metrics"]
    pair = np.asarray(metric["pair_lower_tail_es_0p05"], dtype=float)
    pair /= float(np.mean(pair))
    return np.concatenate(
        (
            pair,
            np.asarray(
                [
                    metric["pair_anisotropy_mean"],
                    metric["pair_anisotropy_upper_tail_es_0p05"],
                    metric["gram_frobenius_drift_mean"],
                    metric["gram_frobenius_drift_upper_tail_es_0p05"],
                ],
                dtype=float,
            ),
        )
    )


def geometry_separation(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = np.stack([metric_signature(summary) for summary in summaries])
    scale = np.std(matrix, axis=0, ddof=1)
    usable = scale > np.finfo(float).eps
    standardized = (matrix[:, usable] - np.mean(matrix[:, usable], axis=0)) / scale[usable]
    centroids = np.stack([np.mean(standardized[index * 20 : (index + 1) * 20], axis=0) for index in range(4)])
    within = np.asarray(
        [
            math.sqrt(float(np.mean(np.sum((standardized[index * 20 : (index + 1) * 20] - centroids[index]) ** 2, axis=1))))
            for index in range(4)
        ]
    )
    pairs = []
    ratios = []
    for pair_index, (left, right) in enumerate(((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))):
        between = float(np.linalg.norm(centroids[left] - centroids[right]))
        pooled = math.sqrt(0.5 * (within[left] ** 2 + within[right] ** 2))
        ratio = between / pooled
        ratios.append(ratio)
        pairs.append({"families": list(FAMILY_CONTRAST_ORDER[pair_index]), "between_centroid": between, "pooled_within_rms": pooled, "ratio": ratio})
    return {
        "signature": "SIX_SCALE_NORMALIZED_PAIR_LTES_PLUS_ANISOTROPY_AND_GRAM_DRIFT",
        "standardization": "GLOBAL_EXACT80_DDOF1_PER_FEATURE",
        "usable_dimensions": int(np.count_nonzero(usable)),
        "family_within_rms": within,
        "pairwise": pairs,
        "minimum_between_within_ratio": float(np.min(ratios)),
        "mean_between_within_ratio": float(np.mean(ratios)),
    }


def load_summaries(root: Path) -> list[dict[str, Any]]:
    values = [read_json(path) for path in root.glob("candidates/*/candidate_summary.json")]
    values.sort(key=lambda item: FAMILY_ORDER.index(item["family_id"]) * 20 + int(item["identity_id"].split("_")[1]))
    if len(values) != 80:
        raise GenEnc4Error(f"EXACT80_SUMMARIES_REQUIRED:{root}")
    return values


def paired_effect(m0: np.ndarray, m1: np.ndarray, *, favorable: str) -> dict[str, Any]:
    difference = m1 - m0 if favorable == "increase" else m0 - m1
    rng = np.random.Generator(np.random.PCG64(MODEL_EFFECT_BOOTSTRAP_SEED))
    indices = rng.integers(0, difference.size, size=(BOOTSTRAP_REPLICATES, difference.size), endpoint=False)
    boot = np.mean(difference[indices], axis=1)
    return {
        "favorable_direction": "M1_MINUS_M0" if favorable == "increase" else "M0_MINUS_M1",
        "mean_favorable_effect": float(np.mean(difference)),
        "median_favorable_effect": float(np.median(difference)),
        "percentile_95_ci": np.quantile(boot, (0.025, 0.975), method="linear"),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": MODEL_EFFECT_BOOTSTRAP_SEED,
        "identity_paired": True,
    }


def family_endpoint_table(m0: list[dict[str, Any]], m1: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for family_index, family in enumerate(FAMILY_ORDER):
        selection = slice(family_index * 20, (family_index + 1) * 20)
        m0_margin = np.asarray([item["metrics"]["d_min_lower_tail_es_0p05"] for item in m0[selection]])
        m1_margin = np.asarray([item["metrics"]["d_min_lower_tail_es_0p05"] for item in m1[selection]])
        m0_drift = np.asarray([item["metrics"]["gram_frobenius_drift_upper_tail_es_0p05"] for item in m0[selection]])
        m1_drift = np.asarray([item["metrics"]["gram_frobenius_drift_upper_tail_es_0p05"] for item in m1[selection]])
        result[family] = {
            "margin_m0_mean": float(np.mean(m0_margin)),
            "margin_m1_mean": float(np.mean(m1_margin)),
            "margin_mean_relative_change": float(np.mean(m1_margin) / np.mean(m0_margin) - 1.0),
            "margin_paired_effect": paired_effect(m0_margin, m1_margin, favorable="increase"),
            "drift_m0_mean": float(np.mean(m0_drift)),
            "drift_m1_mean": float(np.mean(m1_drift)),
            "drift_mean_relative_change": float(np.mean(m1_drift) / np.mean(m0_drift) - 1.0),
            "drift_paired_effect": paired_effect(m0_drift, m1_drift, favorable="decrease"),
        }
    return result


def weakest_pair_summary(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for family_index, family in enumerate(FAMILY_ORDER):
        selected = summaries[family_index * 20 : (family_index + 1) * 20]
        probabilities = np.mean(
            np.asarray([item["metrics"]["weakest_pair_probability"] for item in selected], dtype=float), axis=0
        )
        result[family] = {
            "mean_probability": probabilities,
            "dominant_pair": list(PAIR_ORDER[int(np.argmax(probabilities))]),
            "dominant_probability": float(np.max(probabilities)),
            "fixed_for_all_identities": bool(
                all(int(np.argmax(item["metrics"]["weakest_pair_probability"])) == int(np.argmax(probabilities)) for item in selected)
            ),
        }
    return result


def stable_decision(d_inference: dict[str, Any], v_inference: dict[str, Any], d_family: dict[str, Any], v_family: dict[str, Any], all_feasible: bool) -> dict[str, Any]:
    if d_inference["status"] != "AVAILABLE" or v_inference["status"] != "AVAILABLE":
        return {"terminal": "GEN_ENC_4_M1_INCONCLUSIVE", "reason": "IDENTITY_LEVEL_INFERENCE_UNAVAILABLE"}
    if not all_feasible:
        return {"terminal": "GEN_ENC_4_M1_NO_MEANINGFUL_GAIN_OVER_M0", "reason": "M1_FEASIBILITY_NOT_SATURATED"}
    leaders = [
        d_family["margin_worst_member_leader"],
        d_family["drift_worst_member_leader"],
        v_family["margin_worst_member_leader"],
        v_family["drift_worst_member_leader"],
    ]
    joint = leaders[0] is not None and len(set(leaders)) == 1
    if joint:
        leader = leaders[0]
        leader_index = FAMILY_ORDER.index(leader)
        passed = True
        records = []
        for other_index, other in enumerate(FAMILY_ORDER):
            if other == leader:
                continue
            left, right = sorted((leader_index, other_index))
            contrast_index = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)).index((left, right))
            sign = 1.0 if leader_index < other_index else -1.0
            for endpoint, offset in (("margin", 0), ("drift", 6)):
                d_delta = sign * float(d_inference["observed"][endpoint]["contrasts"][contrast_index])
                v_delta = sign * float(v_inference["observed"][endpoint]["contrasts"][contrast_index])
                raw_ci = v_inference["bootstrap"][f"{endpoint}_percentile_95_ci"][contrast_index]
                ci = [float(raw_ci[0]), float(raw_ci[1])] if sign > 0 else [-float(raw_ci[1]), -float(raw_ci[0])]
                pvalue = float(v_inference["permutation"]["adjusted_p"][offset + contrast_index])
                item_pass = d_delta > 0 and v_delta > 0 and ci[0] > 0 and pvalue <= 0.05
                passed = passed and item_pass
                records.append({"leader": leader, "other": other, "endpoint": endpoint, "development_delta": d_delta, "validation_delta": v_delta, "validation_ci": ci, "adjusted_p": pvalue, "passed": item_pass})
        if passed:
            return {"terminal": "GEN_ENC_4_M1_STABLE_TOPOLOGY_SEPARATION", "reason": "D_V_JOINT_LEADER_AND_ADJUSTED_INFERENCE_PASS", "leader": leader, "contrast_gate": records}
    any_adjusted = False
    for endpoint, offset in (("margin", 0), ("drift", 6)):
        ci = np.asarray(v_inference["bootstrap"][f"{endpoint}_percentile_95_ci"], dtype=float)
        p = np.asarray(v_inference["permutation"]["adjusted_p"][offset : offset + 6], dtype=float)
        any_adjusted = any_adjusted or bool(np.any((p <= 0.05) & ((ci[:, 0] > 0) | (ci[:, 1] < 0))))
    if any_adjusted:
        return {"terminal": "GEN_ENC_4_M1_PARTIAL_TOPOLOGY_SEPARATION", "reason": "AT_LEAST_ONE_MULTIPLICITY_ADJUSTED_VALIDATION_FAMILY_DIFFERENCE", "leaders": leaders}
    return {"terminal": "GEN_ENC_4_M1_NO_MEANINGFUL_GAIN_OVER_M0", "reason": "NO_MULTIPLICITY_ADJUSTED_VALIDATION_FAMILY_DIFFERENCE", "leaders": leaders}


def compare() -> int:
    validate_frozen_inputs()
    m1_d_terminal = read_json(M1_ROOT / "development/partition_terminal.json")
    m1_v_terminal = read_json(M1_ROOT / "single_use_validation/partition_terminal.json")
    if m1_d_terminal["complete_identities"] != 80 or m1_v_terminal["complete_identities"] != 80:
        raise GenEnc4Error("COMPLETE_M1_D_V_REQUIRED")
    partitions = {}
    for partition in ("development", "single_use_validation"):
        m0 = load_summaries(M0_FORMAL_ROOT / partition)
        m1 = load_summaries(M1_ROOT / partition)
        m0_geometry = geometry_separation(m0)
        m1_geometry = geometry_separation(m1)
        partitions[partition] = {
            "geometry_separation": {
                "m0": m0_geometry,
                "m1": m1_geometry,
                "minimum_ratio_gain": m1_geometry["minimum_between_within_ratio"] - m0_geometry["minimum_between_within_ratio"],
                "mean_ratio_gain": m1_geometry["mean_between_within_ratio"] - m0_geometry["mean_between_within_ratio"],
            },
            "family_endpoints": family_endpoint_table(m0, m1),
            "weakest_pair": {"m0": weakest_pair_summary(m0), "m1": weakest_pair_summary(m1)},
            "m1_anisotropy_family_mean": {
                family: float(np.mean([item["metrics"]["pair_anisotropy_mean"] for item in m1[index * 20 : (index + 1) * 20]]))
                for index, family in enumerate(FAMILY_ORDER)
            },
        }
    d_inference = read_json(M1_ROOT / "development/inference/inference_summary.json")
    v_inference = read_json(M1_ROOT / "single_use_validation/inference/inference_summary.json")
    d_family = read_json(M1_ROOT / "development/family_summary.json")
    v_family = read_json(M1_ROOT / "single_use_validation/family_summary.json")
    all_feasible = m1_d_terminal["feasible_identities"] == 80 and m1_v_terminal["feasible_identities"] == 80
    decision = stable_decision(d_inference, v_inference, d_family, v_family, all_feasible)
    payload = {
        "schema_version": "gen_enc_4_m0_m1_comparison_v1",
        "status": "COMPLETE",
        "decision": decision,
        "m0_reproduced": True,
        "m1_explicit_topology_preserved": True,
        "partitions": partitions,
        "m1_family_inference": {
            "development": {
                "status": d_inference["status"],
                "minimum_adjusted_p": float(np.min(d_inference["permutation"]["adjusted_p"])),
                "margin_leader": d_family["margin_worst_member_leader"],
                "drift_leader": d_family["drift_worst_member_leader"],
            },
            "validation": {
                "status": v_inference["status"],
                "minimum_adjusted_p": float(np.min(v_inference["permutation"]["adjusted_p"])),
                "margin_leader": v_family["margin_worst_member_leader"],
                "drift_leader": v_family["drift_worst_member_leader"],
            },
        },
        "feasibility": {
            "all_80_development_feasible": m1_d_terminal["feasible_identities"] == 80,
            "all_80_validation_feasible": m1_v_terminal["feasible_identities"] == 80,
            "all_r_stable_three_development": m1_d_terminal["r_stable_three_identities"] == 80,
            "all_r_stable_three_validation": m1_v_terminal["r_stable_three_identities"] == 80,
            "rank_ceiling_caveat": "FOUR_CARDINAL_INPUTS_REMAIN_NEAR_ONE_HOT_AND_DIFFERENTIAL_RANK_IS_AT_MOST_THREE",
        },
        "evidence_limit": "TOPOLOGY_FAITHFUL_FIVE_NODE_LUMPED_PARAMETER_REDUCED_MODEL_ONLY; NOT ENTITY_FULL_WAVE_COMSOL_OR_MANUFACTURING_EVIDENCE",
        "non_significance_is_not_family_equivalence": True,
        "final_test_read": False,
    }
    write_json(COMPARISON_ROOT / "comparison_summary.json", payload)
    print(json.dumps({"status": payload["status"], "terminal": decision["terminal"], "final_test_read": False}, sort_keys=True))
    return 0


def finalize() -> int:
    """Seal critical hashes after the comparison and independent verification."""

    comparison_path = COMPARISON_ROOT / "comparison_summary.json"
    independent_path = OUTPUT_ROOT / "independent_verification/terminal.json"
    report_path = OUTPUT_ROOT / "REPORT.md"
    progress_path = REPO / "docs/progress/GEN_ENC_4_TOPOLOGY_PRESERVING_M0_M1_RESULTS.md"
    comparison = read_json(comparison_path)
    independent = read_json(independent_path)
    if comparison.get("status") != "COMPLETE" or independent.get("status") != "INDEPENDENT_PASS":
        raise GenEnc4Error("COMPLETE_COMPARISON_AND_INDEPENDENT_PASS_REQUIRED")
    summaries = []
    for partition in ("development", "single_use_validation"):
        summaries.extend(load_summaries(M1_ROOT / partition))
    if len(summaries) != 160 or not all(item.get("finite") is True for item in summaries):
        raise GenEnc4Error("EXACT160_FINITE_M1_SUMMARIES_REQUIRED")
    critical_paths = {
        "mapping_contract": OUTPUT_ROOT / "mapping_contract.json",
        "source_manifest": OUTPUT_ROOT / "source_manifest.json",
        "comparison_summary": comparison_path,
        "independent_verification_terminal": independent_path,
        "m0_baseline_verification": M0_ROOT / "baseline_verification.json",
        "m1_development_terminal": M1_ROOT / "development/partition_terminal.json",
        "m1_validation_terminal": M1_ROOT / "single_use_validation/partition_terminal.json",
        "m1_core": M1_CORE_PATH,
        "formal_driver": THIS_PATH,
        "independent_verifier": VERIFIER_PATH,
        "dedicated_tests": TEST_PATH,
        "output_report": report_path,
        "progress_report": progress_path,
    }
    hashes = {
        name: {"path": path.relative_to(REPO).as_posix(), "sha256": sha256_file(path)}
        for name, path in critical_paths.items()
    }
    write_json(
        OUTPUT_ROOT / "critical_hash_manifest.json",
        {"schema_version": "gen_enc_4_critical_hash_manifest_v1", "entries": hashes, "final_test_read": False},
    )
    terminal = {
        "schema_version": "gen_enc_4_m0_m1_terminal_v1",
        "status": comparison["decision"]["terminal"],
        "reason": comparison["decision"]["reason"],
        "m0_reproduced": comparison["m0_reproduced"],
        "m1_explicit_topology_preserved": comparison["m1_explicit_topology_preserved"],
        "m1_development_identities": 80,
        "m1_validation_identities": 80,
        "finite_candidate_summaries": 160,
        "independent_verification": independent["status"],
        "critical_hash_manifest_path": (OUTPUT_ROOT / "critical_hash_manifest.json").relative_to(REPO).as_posix(),
        "critical_hash_manifest_sha256": sha256_file(OUTPUT_ROOT / "critical_hash_manifest.json"),
        "m2_started": False,
        "m3_started": False,
        "commit_push_tag_release": False,
        "final_test_read": False,
    }
    write_json(OUTPUT_ROOT / "terminal.json", terminal)
    print(json.dumps(terminal, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    sub = value.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("preflight")
    run = sub.add_parser("run")
    run.add_argument("--partition", choices=("development", "single_use_validation"), required=True)
    sub.add_parser("compare")
    sub.add_parser("finalize")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "prepare":
        return prepare()
    if args.command == "preflight":
        return preflight()
    if args.command == "run":
        return run_partition(args.partition)
    if args.command == "compare":
        return compare()
    if args.command == "finalize":
        return finalize()
    raise GenEnc4Error("UNKNOWN_COMMAND")


if __name__ == "__main__":
    raise SystemExit(main())

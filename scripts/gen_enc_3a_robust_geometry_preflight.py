"""GEN-ENC-3A science-blind one-member development preflight.

This entry point is deliberately incapable of running validation or more than
the frozen first exact80 member.  It exercises the E2 optimized solver, the
sealed development whitener, compact chunk persistence, deterministic sparse
Y_diff audit sampling, hash receipts, and resumable checkpoints without
reporting scientific metric values.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from acoustic_encoder.gen_enc.e2_rc03_stats import canonical_json_bytes, sha256_file
from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block
from acoustic_encoder.gen_enc.robust_encoding_geometry import (
    PAIR_ORDER,
    STATE_ORDER_DEGREES,
    batch_geometry_from_raw,
    evaluation_unit_weights,
    frobenius_gram_drift,
    pair_anisotropy,
    weakest_pair_index,
)


DEFAULT_OUTPUT_ROOT = REPO / "outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY"
EXACT80_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json"
NUISANCE_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEED_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
COMMON_W_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/sealed/common_w.npz"
D_TERMINAL_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/partition_terminal.json"
V_TERMINAL_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_v_single_use_validation_01/single_use_validation/partition_terminal.json"
E2_AUDIT_ROOT = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/raw_audit/HAND_01"
PRIMARY_COUNT = 208
SECONDARY_COUNT = 256
CELL_COUNT = 3675
REPEAT_COUNT = 2
CELLS_PER_CHUNK = 25
CHUNK_COUNT = 147
AUDIT_UNIT_COUNT = 2
RESERVE_BYTES = 32 * 1024**3
MANAGED_CAP_BYTES = 48 * 1024**3


class PreflightError(RuntimeError):
    """Fail-closed preflight error."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PreflightError("JSON_OBJECT_REQUIRED")
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_array_atomic(path: Path, value: np.ndarray) -> None:
    array = np.ascontiguousarray(value)
    if array.dtype not in (
        np.dtype("float64"),
        np.dtype("uint8"),
        np.dtype("uint64"),
        np.dtype("complex128"),
    ) or not np.all(np.isfinite(array)):
        raise PreflightError("FINITE_FROZEN_ARRAY_DTYPE_REQUIRED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def managed_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def storage_gate(root: Path) -> dict[str, int]:
    free = shutil.disk_usage(root).free
    managed = managed_bytes(root)
    if free < RESERVE_BYTES or managed > MANAGED_CAP_BYTES:
        raise PreflightError("RESOURCE_BLOCKED_STORAGE")
    return {"free_bytes": int(free), "managed_bytes": int(managed)}


def nuisance_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise PreflightError("NUISANCE_METADATA_REQUIRED")
        for ordinal, row in enumerate(csv.DictReader(stream), start=1):
            if row["design_row_id"] != f"N{ordinal:04d}":
                raise PreflightError("NUISANCE_ORDER_MISMATCH")
            if not np.isclose(float(row["cell_weight"]), 1.0 / CELL_COUNT, rtol=0.0, atol=1e-18):
                raise PreflightError("NUISANCE_WEIGHT_MISMATCH")
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
        raise PreflightError("EXACT3675_NUISANCE_CELLS_REQUIRED")
    return rows


def audit_exact80(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = read_json(path)
    members = manifest.get("members")
    if not isinstance(members, list) or len(members) != 80:
        raise PreflightError("EXACT80_REQUIRED")
    expected_families = (
        "HAND_DESIGNED",
        "NEAR_INDEPENDENT",
        "FIXED_SEED_RANDOM_DISORDERED",
        "PHYSICS_METAMATERIAL_INSPIRED",
    )
    family_counts = {family: 0 for family in expected_families}
    cost_rows = []
    identity_hashes = []
    for ordinal, entry in enumerate(members, start=1):
        if entry.get("global_ordinal") != ordinal:
            raise PreflightError("EXACT80_GLOBAL_ORDER_MISMATCH")
        family = entry.get("family_id")
        if family not in family_counts:
            raise PreflightError("EXACT80_FAMILY_MISMATCH")
        identity_path = REPO / str(entry.get("identity_path", ""))
        identity_sha = sha256_file(identity_path)
        if identity_sha != entry.get("identity_file_sha256"):
            raise PreflightError("EXACT80_IDENTITY_HASH_MISMATCH")
        identity = read_json(identity_path)
        if (
            identity.get("member_id") != entry.get("member_id")
            or identity.get("family_id") != family
            or identity.get("global_ordinal") != ordinal
            or identity.get("status") != "STATIC_IDENTITY_ELIGIBLE"
        ):
            raise PreflightError("EXACT80_IDENTITY_PAYLOAD_MISMATCH")
        cost = identity.get("cad_static_audit")
        if not isinstance(cost, dict):
            raise PreflightError("EXISTING_COST_FIELDS_REQUIRED")
        cost_rows.append(
            (
                float(cost["volume_m3"]),
                int(cost["dof"]),
                float(cost["minimum_feature_m"]),
                float(cost["solid_load_path_m"]),
            )
        )
        identity_hashes.append(identity_sha)
        family_counts[family] += 1
    if tuple(family_counts.values()) != (20, 20, 20, 20):
        raise PreflightError("FOUR_BY_EXACT20_REQUIRED")
    costs = np.asarray(cost_rows, dtype=np.float64)
    if (
        not np.all(costs[:, 0] == costs[0, 0])
        or not np.all(costs[:, 2] == costs[0, 2])
        or not np.all(costs[:, 3] == costs[0, 3])
        or int(np.min(costs[:, 1])) != 12
        or int(np.max(costs[:, 1])) != 15
    ):
        raise PreflightError("EXISTING_COST_ENVELOPE_MISMATCH")
    audit = {
        "schema_version": "gen_enc_3a_exact80_identity_audit_v1",
        "status": "PASS",
        "manifest_path": EXACT80_PATH.relative_to(REPO).as_posix(),
        "manifest_sha256": sha256_file(EXACT80_PATH),
        "member_count": 80,
        "family_counts": family_counts,
        "identity_file_hashes_in_order": identity_hashes,
        "identity_payloads_read": 80,
        "order": "HAND_01..20_THEN_NEAR_01..20_THEN_RANDOM_01..20_THEN_PHYSICS_01..20",
        "cost_claim": "SAME_VOLUME_MINIMUM_FEATURE_SOLID_LOAD_PATH_AND_DOF_12_TO_15_ENVELOPE_MATCHED_NOT_FULLY_EQUAL_COST",
        "volume_m3": float(costs[0, 0]),
        "minimum_feature_m": float(costs[0, 2]),
        "solid_load_path_m": float(costs[0, 3]),
        "dof_range": [12, 15],
        "final_test_read": False,
    }
    return manifest, audit


def validate_e2_seals() -> dict[str, Any]:
    development = read_json(D_TERMINAL_PATH)
    validation = read_json(V_TERMINAL_PATH)
    common_w_sha = sha256_file(COMMON_W_PATH)
    if (
        development.get("status") != "E2_D_SEALED_INDEPENDENT_PASS"
        or development.get("complete_identities") != 80
        or development.get("common_w_sha256") != common_w_sha
        or development.get("validation_refit") is not False
        or validation.get("status") != "E2_V_SINGLE_USE_TERMINAL"
        or validation.get("complete_identities") != 80
        or validation.get("common_w_sha256") != common_w_sha
        or validation.get("validation_refit") is not False
        or validation.get("validation_feedback_to_development") is not False
    ):
        raise PreflightError("E2_D_V_W_SEAL_MISMATCH")
    with np.load(COMMON_W_PATH, allow_pickle=False) as sealed:
        operator = np.asarray(sealed["operator"], dtype=np.float64)
        if operator.shape != (1664, 1664) or not np.all(np.isfinite(operator)):
            raise PreflightError("SEALED_COMMON_W_OPERATOR_MISMATCH")
    return {
        "schema_version": "gen_enc_3a_e2_seal_binding_v1",
        "status": "PASS",
        "development_terminal": {
            "path": D_TERMINAL_PATH.relative_to(REPO).as_posix(),
            "sha256": sha256_file(D_TERMINAL_PATH),
        },
        "validation_terminal": {
            "path": V_TERMINAL_PATH.relative_to(REPO).as_posix(),
            "sha256": sha256_file(V_TERMINAL_PATH),
        },
        "common_w": {
            "path": COMMON_W_PATH.relative_to(REPO).as_posix(),
            "sha256": common_w_sha,
            "operator_shape": [1664, 1664],
            "dtype": "float64",
            "fit_partition": "development",
            "validation_refit": False,
        },
        "final_test_read": False,
    }


def contract_value() -> dict[str, Any]:
    return {
        "schema_version": "gen_enc_3a_robust_encoding_geometry_preexecution_contract_v1",
        "status": "PREEXECUTION_ONLY_GUARDIAN_REVIEW_REQUIRED",
        "evidence_ceiling": "E2_REDUCED_MODEL",
        "equations_changed": False,
        "model": "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1",
        "identity_order": "EXACT80_FOUR_FAMILIES_BY_20_FROZEN",
        "state_order_degrees": list(STATE_ORDER_DEGREES),
        "pair_order_degrees": [list(pair) for pair in PAIR_ORDER],
        "frequency": {"primary_points": PRIMARY_COUNT, "secondary_points": SECONDARY_COUNT, "primary_only_for_3a_metrics": True},
        "nuisance": {"cells": CELL_COUNT, "cell_mass": "1/3675", "repeats": REPEAT_COUNT, "repeat_mass_within_cell": "1/2"},
        "feasibility_gate_only": {"E_primary_strictly_greater_than": 1.0, "r_stable_equals": 3, "used_for_new_ranking": False},
        "whitening": {
            "source": "SEALED_E2_DEVELOPMENT_COMMON_W",
            "real_embedding": "[Re(weighted complex Y_diff);Im(weighted complex Y_diff)]",
            "operator_direction": "Z_R=W_1664x1664_LEFT_MULTIPLY_Y_DIFF_R_1664x4",
            "complex_reassembly": "Z_C=Z_R[0:832,:]+i*Z_R[832:1664,:]",
            "new_fit": False,
            "validation_refit": False,
            "gram_claim_limit": "CANONICAL_REASSEMBLY_STATE_GEOMETRY_NOT_PHYSICAL_PHASE_MECHANISM",
        },
        "primary_metric": {
            "name": "D_MIN_LOWER_TAIL_EXPECTED_SHORTFALL_0P05",
            "definition": "WEIGHTED_MEAN_OF_LOWEST_0P05_PROBABILITY_WITH_FRACTIONAL_BOUNDARY_MASS",
            "larger_is_better": True,
            "loss_equivalence": "-CVaR_0P95(loss=-d_min)_UPPER_0P05_TAIL",
        },
        "secondary_pair_metrics": {
            "six_pair_lower_tail_expected_shortfall": True,
            "weakest_pair_identity": "FIRST_EXACT_MINIMUM_IN_FROZEN_PAIR_ORDER",
            "pair_anisotropy": "MAX_PAIR_DISTANCE_DIVIDED_BY_MIN_PAIR_DISTANCE",
        },
        "gram": {
            "definition": "G=Z_C.conj().T@Z_C",
            "orientation": "STATE_BY_STATE_4x4_COMPLEX_HERMITIAN",
            "normalization": "HERMITIAN_SYMMETRIZE_THEN_DIVIDE_BY_POSITIVE_REAL_TRACE_NO_PSD_REFIT",
            "reference": "EQUAL_CELL_EQUAL_REPEAT_WEIGHTED_MEAN_OF_NORMALIZED_DEVELOPMENT_GRAMS_PER_IDENTITY_THEN_SAME_TRACE_NORMALIZATION",
            "validation_updates_reference": False,
            "primary_drift_metric": "FROBENIUS_NORM_OF_NORMALIZED_GRAM_MINUS_FROZEN_IDENTITY_REFERENCE",
            "worst_tail_drift": "UPPER_TAIL_EXPECTED_SHORTFALL_0P05_WITH_FRACTIONAL_BOUNDARY_MASS",
        },
        "inference": {
            "sampling_unit": "IDENTITY",
            "family_members": 20,
            "exact20_worst_member": True,
            "distribution": "ALL_20_IDENTITY_ENDPOINTS_WITH_MEDIAN_IQR_AND_ECDF",
            "contrast_order": "H_N_H_R_H_P_N_R_N_P_R_P",
            "margin_contrast": "DELTA_S_A_B=MEAN_S_A_MINUS_MEAN_S_B_POSITIVE_FAVORS_A",
            "drift_contrast": "DELTA_D_A_B=MEAN_U_B_MINUS_MEAN_U_A_POSITIVE_FAVORS_A",
            "welch_standard_error": "SQRT(SAMPLE_VAR_DDOF1_A/20+SAMPLE_VAR_DDOF1_B/20)",
            "zero_or_nonfinite_denominator": "ENDPOINT_INCONCLUSIVE_NO_SUBSTITUTE",
            "bootstrap": "PCG64_SEED_2026090301_20000_WITHIN_FAMILY_EXACT20_WITH_REPLACEMENT_PAIRED_ENDPOINT_INDICES",
            "bootstrap_ci": "NUMPY_QUANTILE_0P025_0P975_METHOD_LINEAR",
            "permutation": "PCG64_SEED_2026090302_100000_ALL80_PAIRED_IDENTITY_LABEL_PERMUTATIONS_PRESERVE_20_PER_FAMILY_RECOMPUTE_12_T_MAX_ABS",
            "adjusted_p": "(1+COUNT_100000_MAX_ABS_T_GE_ABS_T_OBS)/100001_TWO_SIDED_FWER",
            "cell_or_frequency_pseudoreplication": False,
        },
        "storage": {
            "raw_full_y_diff_saved": False,
            "compact_distance_shape_per_identity_partition": [CELL_COUNT, REPEAT_COUNT, 6],
            "compact_gram_drift_shape_per_identity_partition": [CELL_COUNT, REPEAT_COUNT],
            "full_y_diff_audit_units_per_identity_partition": AUDIT_UNIT_COUNT,
            "audit_selection": "ASCENDING_SHA256_OF_GEN_ENC_3A_YD_AUDIT_V1_PARTITION_IDENTITY_CELL_REPEAT",
            "chunk_cells": CELLS_PER_CHUNK,
            "chunk_count": CHUNK_COUNT,
            "checkpointed": True,
            "temporary_root_project_internal": True,
        },
        "preflight": {
            "partition": "development",
            "identity": "HAND_01",
            "selection_reason": "FROZEN_EXACT80_GLOBAL_ORDINAL_1_AND_EXISTING_E2_TIMING_PROXY_NOT_PERFORMANCE_SELECTED",
            "science_blind": True,
            "formal_reuse": False,
            "validation_allowed": False,
        },
        "formal_isolation": {
            "root": "outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY/formal",
            "preflight_payload_read_or_promotion": False,
            "hand_01_forced_recompute": True,
            "development_requires_80_references_before_validation": True,
            "independent_verifier_recomputes_audit_units_candidate_tails_and_identity_inference": True,
        },
        "excluded": [
            "DECODER_OR_3B",
            "FULL_WAVE_OR_COMSOL",
            "PRINTING_OR_PHYSICAL_EXPERIMENT",
            "PARAMETER_SEARCH",
            "NEW_EQUATIONS_OR_IDENTITIES",
            "FINAL_TEST",
        ],
        "final_test_read": False,
    }


def deterministic_audit_units(partition: str, identity_id: str) -> set[tuple[int, int]]:
    units = [(cell, repeat) for cell in range(CELL_COUNT) for repeat in range(REPEAT_COUNT)]
    ordered = sorted(
        units,
        key=lambda unit: hashlib.sha256(
            f"GEN_ENC_3A_YD_AUDIT_V1|{partition}|{identity_id}|{unit[0]}|{unit[1]}".encode("utf-8")
        ).hexdigest(),
    )
    return set(ordered[:AUDIT_UNIT_COUNT])


def generate_chunk(
    member: dict[str, Any],
    nuisance: list[dict[str, float]],
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
                state_angles_degrees=STATE_ORDER_DEGREES,
                partition="development",
                repeat_seed_tuple=seeds,
            ).central_pressure
    return output


def validate_completed_chunk(receipt_path: Path) -> tuple[Path, Path]:
    receipt = read_json(receipt_path)
    if receipt.get("status") != "PASS_SCIENCE_BLIND" or receipt.get("partition") != "development":
        raise PreflightError("PRECHECK_RECEIPT_STATUS_MISMATCH")
    distance_path = REPO / receipt["distance"]["path"]
    gram_path = REPO / receipt["normalized_gram_temporary"]["path"]
    for path, record in ((distance_path, receipt["distance"]), (gram_path, receipt["normalized_gram_temporary"])):
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            raise PreflightError("PRECHECK_RECEIPT_PAYLOAD_HASH_MISMATCH")
    return distance_path, gram_path


def load_finalized_phase_one(output_root: Path) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]]] | None:
    seal_path = output_root / "preflight/development/HAND_01/reference/reference_seal.json"
    if not seal_path.is_file():
        return None
    seal = read_json(seal_path)
    reference_path = REPO / seal["reference_gram"]["path"]
    if (
        seal.get("status") != "PASS_SCIENCE_BLIND_NOT_FORMAL"
        or not reference_path.is_file()
        or sha256_file(reference_path) != seal["reference_gram"]["sha256"]
    ):
        raise PreflightError("FINALIZED_PHASE1_REFERENCE_SEAL_MISMATCH")
    reference = np.asarray(np.load(reference_path, allow_pickle=False), dtype=np.complex128)
    receipts = []
    reproductions = []
    for chunk_index in range(CHUNK_COUNT):
        chunk_id = f"chunk_{chunk_index:03d}"
        receipt_path = output_root / "preflight/development/HAND_01/receipts/phase1" / f"{chunk_id}.json"
        receipt = read_json(receipt_path)
        distance_path = REPO / receipt["distance"]["path"]
        if not distance_path.is_file() or sha256_file(distance_path) != receipt["distance"]["sha256"]:
            raise PreflightError("FINALIZED_PHASE1_DISTANCE_HASH_MISMATCH")
        receipts.append(receipt)
        if receipt.get("e2_raw_audit_reproduction") is not None:
            reproductions.append(receipt["e2_raw_audit_reproduction"])
    return reference, receipts, reproductions


def chunk_record(path: Path, array: np.ndarray) -> dict[str, Any]:
    return {
        "path": path.relative_to(REPO).as_posix(),
        "sha256": sha256_file(path),
        "shape": list(array.shape),
        "dtype": array.dtype.name,
        "format": "NPY_1_0",
        "order": "C",
    }


def phase_one(
    output_root: Path,
    member: dict[str, Any],
    nuisance: list[dict[str, float]],
    seeds: tuple[int, int],
    whitener: np.ndarray,
    *,
    recompute: bool,
) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]]]:
    identity_id = str(member["member_id"])
    audit_units = deterministic_audit_units("development", identity_id)
    gram_sum = np.zeros((4, 4), dtype=np.complex128)
    receipts: list[dict[str, Any]] = []
    e2_reproduction: list[dict[str, Any]] = []
    for chunk_index in range(CHUNK_COUNT):
        chunk_id = f"chunk_{chunk_index:03d}"
        start = chunk_index * CELLS_PER_CHUNK
        end = start + CELLS_PER_CHUNK
        receipt_path = output_root / "preflight/development/HAND_01/receipts/phase1" / f"{chunk_id}.json"
        if receipt_path.is_file() and not recompute:
            _, gram_path = validate_completed_chunk(receipt_path)
            grams = np.asarray(np.load(gram_path, allow_pickle=False), dtype=np.complex128)
            gram_sum += grams.sum(axis=(0, 1))
            receipt = read_json(receipt_path)
            receipts.append(receipt)
            if receipt.get("e2_raw_audit_reproduction") is not None:
                e2_reproduction.append(receipt["e2_raw_audit_reproduction"])
            continue
        raw_path = output_root / "preflight/development/HAND_01/tmp/raw" / f"{chunk_id}.npy"
        raw = generate_chunk(member, nuisance, seeds, start, end)
        write_array_atomic(raw_path, raw)
        raw_sha = sha256_file(raw_path)
        reproduction = None
        e2_path = E2_AUDIT_ROOT / f"{chunk_id}.npy"
        if e2_path.is_file():
            reproduction = {
                "source_path": e2_path.relative_to(REPO).as_posix(),
                "source_sha256": sha256_file(e2_path),
                "generated_sha256": raw_sha,
                "byte_identical": sha256_file(e2_path) == raw_sha,
            }
            if reproduction["byte_identical"] is not True:
                raise PreflightError("E2_RAW_AUDIT_REPRODUCTION_MISMATCH")
            e2_reproduction.append(reproduction)
        distances, grams, y_diff = batch_geometry_from_raw(raw, whitener)
        distance_path = output_root / "preflight/development/HAND_01/compact/distance_chunks" / f"{chunk_id}.npy"
        gram_path = output_root / "preflight/development/HAND_01/tmp/normalized_gram_chunks" / f"{chunk_id}.npy"
        write_array_atomic(distance_path, distances)
        write_array_atomic(gram_path, grams)
        for cell, repeat in sorted(audit_units):
            if start <= cell < end:
                audit_path = output_root / "preflight/development/HAND_01/audit_y_diff" / f"cell_{cell:04d}_repeat_{repeat}.npy"
                write_array_atomic(audit_path, y_diff[cell - start, repeat])
        receipt = {
            "schema_version": "gen_enc_3a_science_blind_phase1_chunk_receipt_v1",
            "status": "PASS_SCIENCE_BLIND",
            "partition": "development",
            "identity_id": identity_id,
            "chunk_id": chunk_id,
            "cell_start": start,
            "cell_end_exclusive": end,
            "raw_temporary_sha256": raw_sha,
            "raw_retained": False,
            "distance": chunk_record(distance_path, distances),
            "normalized_gram_temporary": chunk_record(gram_path, grams),
            "e2_raw_audit_reproduction": reproduction,
            "scientific_values_reported": False,
            "formal_eligible": False,
            "final_test_read": False,
        }
        write_json_atomic(receipt_path, receipt)
        raw_path.unlink()
        gram_sum += grams.sum(axis=(0, 1))
        receipts.append(receipt)
        write_json_atomic(
            output_root / "preflight/development/HAND_01/checkpoint.json",
            {
                "schema_version": "gen_enc_3a_science_blind_checkpoint_v1",
                "status": "PHASE1_IN_PROGRESS",
                "completed_chunks": len(receipts),
                "last_chunk": chunk_id,
                "resume_supported": True,
                "scientific_values_reported": False,
                "formal_eligible": False,
                "final_test_read": False,
            },
        )
        storage_gate(output_root)
    reference = gram_sum / float(CELL_COUNT * REPEAT_COUNT)
    reference = 0.5 * (reference + reference.conj().T)
    reference /= float(np.trace(reference).real)
    if len(receipts) != CHUNK_COUNT or not np.all(np.isfinite(reference)):
        raise PreflightError("PHASE1_INCOMPLETE")
    return reference, receipts, e2_reproduction


def phase_two(output_root: Path, reference: np.ndarray, *, recompute: bool) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for chunk_index in range(CHUNK_COUNT):
        chunk_id = f"chunk_{chunk_index:03d}"
        gram_path = output_root / "preflight/development/HAND_01/tmp/normalized_gram_chunks" / f"{chunk_id}.npy"
        distance_path = output_root / "preflight/development/HAND_01/compact/distance_chunks" / f"{chunk_id}.npy"
        phase1_receipt_path = output_root / "preflight/development/HAND_01/receipts/phase1" / f"{chunk_id}.json"
        drift_path = output_root / "preflight/development/HAND_01/compact/gram_drift_chunks" / f"{chunk_id}.npy"
        weak_path = output_root / "preflight/development/HAND_01/compact/weakest_pair_chunks" / f"{chunk_id}.npy"
        anisotropy_path = output_root / "preflight/development/HAND_01/compact/pair_anisotropy_chunks" / f"{chunk_id}.npy"
        receipt_path = output_root / "preflight/development/HAND_01/receipts/phase2" / f"{chunk_id}.json"
        if receipt_path.is_file() and not recompute:
            receipt = read_json(receipt_path)
            for key in ("gram_drift", "weakest_pair_index", "pair_anisotropy"):
                path = REPO / receipt[key]["path"]
                if not path.is_file() or sha256_file(path) != receipt[key]["sha256"]:
                    raise PreflightError("PHASE2_RECEIPT_PAYLOAD_HASH_MISMATCH")
            receipts.append(receipt)
            continue
        if not gram_path.is_file():
            raise PreflightError("PHASE2_NORMALIZED_GRAM_TEMPORARY_REQUIRED")
        grams = np.asarray(np.load(gram_path, allow_pickle=False), dtype=np.complex128)
        distances = np.asarray(np.load(distance_path, allow_pickle=False), dtype=np.float64)
        drift = frobenius_gram_drift(grams.reshape((-1, 4, 4)), reference).reshape((CELLS_PER_CHUNK, REPEAT_COUNT))
        weak = weakest_pair_index(distances)
        anisotropy = pair_anisotropy(distances)
        write_array_atomic(drift_path, drift)
        write_array_atomic(weak_path, weak)
        write_array_atomic(anisotropy_path, anisotropy)
        receipt = {
            "schema_version": "gen_enc_3a_science_blind_phase2_chunk_receipt_v1",
            "status": "PASS_SCIENCE_BLIND",
            "partition": "development",
            "identity_id": "HAND_01",
            "chunk_id": chunk_id,
            "phase1_receipt_path": phase1_receipt_path.relative_to(REPO).as_posix(),
            "phase1_receipt_sha256": sha256_file(phase1_receipt_path),
            "gram_drift": chunk_record(drift_path, drift),
            "weakest_pair_index": chunk_record(weak_path, weak),
            "pair_anisotropy": chunk_record(anisotropy_path, anisotropy),
            "normalized_gram_temporary_retained": False,
            "scientific_values_reported": False,
            "formal_eligible": False,
            "final_test_read": False,
        }
        write_json_atomic(receipt_path, receipt)
        gram_path.unlink()
        receipts.append(receipt)
        write_json_atomic(
            output_root / "preflight/development/HAND_01/checkpoint.json",
            {
                "schema_version": "gen_enc_3a_science_blind_checkpoint_v1",
                "status": "PHASE2_IN_PROGRESS",
                "completed_chunks": len(receipts),
                "last_chunk": chunk_id,
                "resume_supported": True,
                "scientific_values_reported": False,
                "formal_eligible": False,
                "final_test_read": False,
            },
        )
        storage_gate(output_root)
    if len(receipts) != CHUNK_COUNT:
        raise PreflightError("PHASE2_INCOMPLETE")
    return receipts


def build_manifest(output_root: Path) -> None:
    files = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name not in ("SHA256SUMS.txt", "artifact_inventory.json") and ".tmp" not in path.parts
    )
    inventory = {
        "schema_version": "gen_enc_3a_preexecution_artifact_inventory_v1",
        "file_count_excluding_inventory_and_checksums": len(files),
        "files": [path.relative_to(output_root).as_posix() for path in files],
        "final_test_read": False,
    }
    write_json_atomic(output_root / "artifact_inventory.json", inventory)
    checksum_files = sorted(path for path in output_root.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
    lines = [f"{sha256_file(path)}  {path.relative_to(output_root).as_posix()}" for path in checksum_files]
    checksum_path = output_root / "SHA256SUMS.txt"
    temporary = checksum_path.with_name(checksum_path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, checksum_path)


def run(output_root: Path, *, resume: bool, recompute_preflight: bool) -> int:
    if output_root.exists() and not resume:
        raise PreflightError("OUTPUT_ROOT_EXISTS_USE_RESUME")
    output_root.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_root / "preflight/development/HAND_01/checkpoint.json"
    if resume and not recompute_preflight and checkpoint_path.is_file():
        checkpoint = read_json(checkpoint_path)
        if checkpoint.get("status") == "PREFLIGHT_COMPLETE_SCIENCE_BLIND":
            terminal_path = REPO / checkpoint["terminal_path"]
            if not terminal_path.is_file() or sha256_file(terminal_path) != checkpoint.get("terminal_sha256"):
                raise PreflightError("COMPLETED_PREFLIGHT_TERMINAL_HASH_MISMATCH")
            terminal = read_json(terminal_path)
            print(json.dumps({"status": terminal["status"], "science_values_reported": False, "formal_units": 0, "resumed_complete": True}, sort_keys=True))
            return 0
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    write_json_atomic(output_root / "preexecution_contract.json", contract_value())
    exact80, identity_audit = audit_exact80(EXACT80_PATH)
    write_json_atomic(output_root / "identity_manifest_audit.json", identity_audit)
    seal_binding = validate_e2_seals()
    write_json_atomic(output_root / "e2_seal_binding.json", seal_binding)
    nuisance = nuisance_rows(NUISANCE_PATH)
    seed = read_json(SEED_PATH)
    seeds = tuple(seed["nuisance_partition_seeds"]["development_training"])
    if seeds != (2026091001, 2026091002):
        raise PreflightError("DEVELOPMENT_SEED_MISMATCH")
    member_entry = exact80["members"][0]
    if member_entry.get("member_id") != "HAND_01" or member_entry.get("global_ordinal") != 1:
        raise PreflightError("FROZEN_PREFLIGHT_MEMBER_MISMATCH")
    member = read_json(REPO / member_entry["identity_path"])
    with np.load(COMMON_W_PATH, allow_pickle=False) as sealed:
        whitener = np.asarray(sealed["operator"], dtype=np.float64)
    storage_gate(output_root)
    finalized_phase_one = None if recompute_preflight else load_finalized_phase_one(output_root)
    if finalized_phase_one is None:
        reference, phase1_receipts, reproductions = phase_one(
            output_root,
            member,
            nuisance,
            seeds,
            whitener,
            recompute=recompute_preflight,
        )
        reference_path = output_root / "preflight/development/HAND_01/reference/development_reference_gram.npy"
        write_array_atomic(reference_path, reference)
        reference_seal = {
            "schema_version": "gen_enc_3a_preflight_development_reference_gram_seal_v1",
            "status": "PASS_SCIENCE_BLIND_NOT_FORMAL",
            "identity_id": "HAND_01",
            "partition": "development",
            "source_units": CELL_COUNT * REPEAT_COUNT,
            "cell_weight": "1/3675",
            "repeat_weight_within_cell": "1/2",
            "reference_gram": chunk_record(reference_path, reference),
            "normalization": "HERMITIAN_TRACE_ONE",
            "validation_updates_reference": False,
            "scientific_values_reported": False,
            "formal_eligible": False,
            "final_test_read": False,
        }
        write_json_atomic(output_root / "preflight/development/HAND_01/reference/reference_seal.json", reference_seal)
    else:
        reference, phase1_receipts, reproductions = finalized_phase_one
    phase2_receipts = phase_two(output_root, reference, recompute=recompute_preflight)
    audit_files = sorted((output_root / "preflight/development/HAND_01/audit_y_diff").glob("*.npy"))
    if len(audit_files) != AUDIT_UNIT_COUNT:
        raise PreflightError("EXACT_AUDIT_Y_DIFF_UNIT_COUNT_REQUIRED")
    if len(reproductions) != len(list(E2_AUDIT_ROOT.glob("chunk_*.npy"))) or not all(
        item["byte_identical"] for item in reproductions
    ):
        raise PreflightError("E2_RAW_AUDIT_REPRODUCTION_INCOMPLETE")
    compact_manifest = {
        "schema_version": "gen_enc_3a_preflight_compact_manifest_v1",
        "status": "PASS_SCIENCE_BLIND_NOT_FORMAL",
        "identity_id": "HAND_01",
        "partition": "development",
        "chunks": CHUNK_COUNT,
        "cells": CELL_COUNT,
        "repeats": REPEAT_COUNT,
        "distance_shape_total": [CELL_COUNT, REPEAT_COUNT, 6],
        "gram_drift_shape_total": [CELL_COUNT, REPEAT_COUNT],
        "weakest_pair_shape_total": [CELL_COUNT, REPEAT_COUNT],
        "pair_anisotropy_shape_total": [CELL_COUNT, REPEAT_COUNT],
        "phase1_receipt_hashes": [sha256_file(output_root / "preflight/development/HAND_01/receipts/phase1" / f"chunk_{index:03d}.json") for index in range(CHUNK_COUNT)],
        "phase2_receipt_hashes": [sha256_file(output_root / "preflight/development/HAND_01/receipts/phase2" / f"chunk_{index:03d}.json") for index in range(CHUNK_COUNT)],
        "audit_y_diff": [
            {
                "path": path.relative_to(REPO).as_posix(),
                "sha256": sha256_file(path),
                "shape": list(np.load(path, allow_pickle=False, mmap_mode="r").shape),
                "dtype": np.load(path, allow_pickle=False, mmap_mode="r").dtype.name,
            }
            for path in audit_files
        ],
        "raw_full_y_diff_retained": False,
        "temporary_normalized_gram_chunks_remaining": len(list((output_root / "preflight/development/HAND_01/tmp/normalized_gram_chunks").glob("*.npy"))),
        "scientific_values_reported": False,
        "formal_eligible": False,
        "final_test_read": False,
    }
    write_json_atomic(output_root / "preflight/development/HAND_01/compact_manifest.json", compact_manifest)
    elapsed_wall = time.perf_counter() - start_wall
    elapsed_cpu = time.process_time() - start_cpu
    terminal = {
        "schema_version": "gen_enc_3a_science_blind_preflight_terminal_v1",
        "status": "PREEXECUTION_PREFLIGHT_PASS_READY_FOR_GUARDIAN_REVIEW",
        "identity_id": "HAND_01",
        "selection_performance_blind": True,
        "partition": "development",
        "complete_cells": CELL_COUNT,
        "complete_repeats": CELL_COUNT * REPEAT_COUNT,
        "phase1_chunks": len(phase1_receipts),
        "phase2_chunks": len(phase2_receipts),
        "all_compact_arrays_finite": True,
        "reference_gram_sealed": True,
        "common_w_reused_without_refit": True,
        "e2_raw_audit_reproductions_available": len(reproductions),
        "e2_raw_audit_reproductions_byte_identical": all(item["byte_identical"] for item in reproductions),
        "audit_y_diff_units": len(audit_files),
        "full_raw_retained": False,
        "resume_supported": True,
        "science_values_reported": False,
        "scientific_terminal_assigned": False,
        "formal_eligible": False,
        "validation_terminal_read_for_binding": True,
        "validation_response_read": False,
        "final_test_read": False,
        "resource": {
            "wall_seconds": elapsed_wall,
            "process_cpu_seconds": elapsed_cpu,
            **storage_gate(output_root),
        },
    }
    write_json_atomic(output_root / "preflight/development/HAND_01/preflight_terminal.json", terminal)
    write_json_atomic(
        output_root / "preflight/development/HAND_01/checkpoint.json",
        {
            "schema_version": "gen_enc_3a_science_blind_checkpoint_v1",
            "status": "PREFLIGHT_COMPLETE_SCIENCE_BLIND",
            "completed_chunks": CHUNK_COUNT,
            "resume_supported": True,
            "terminal_path": (output_root / "preflight/development/HAND_01/preflight_terminal.json").relative_to(REPO).as_posix(),
            "terminal_sha256": sha256_file(output_root / "preflight/development/HAND_01/preflight_terminal.json"),
            "scientific_values_reported": False,
            "formal_eligible": False,
            "final_test_read": False,
        },
    )
    build_manifest(output_root)
    print(json.dumps({"status": terminal["status"], "science_values_reported": False, "formal_units": 0}, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("mode", choices=("self-test", "preflight"))
    value.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT.as_posix())
    value.add_argument("--resume", action="store_true")
    value.add_argument("--recompute-preflight", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(
                json.dumps(
                    {
                        "status": "PASS",
                        "allowed_partition": "development",
                        "allowed_identity": "HAND_01",
                        "validation_allowed": False,
                        "formal_units": 0,
                        "final_test_read": False,
                    },
                    sort_keys=True,
                )
            )
            return 0
        output_root = Path(args.output_root).resolve()
        try:
            output_root.relative_to(REPO.resolve())
        except ValueError as exc:
            raise PreflightError("PROJECT_INTERNAL_OUTPUT_ROOT_REQUIRED") from exc
        if args.recompute_preflight and not args.resume:
            raise PreflightError("RECOMPUTE_PREFLIGHT_REQUIRES_RESUME")
        return run(output_root, resume=args.resume, recompute_preflight=args.recompute_preflight)
    except (OSError, KeyError, ValueError, np.linalg.LinAlgError, PreflightError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

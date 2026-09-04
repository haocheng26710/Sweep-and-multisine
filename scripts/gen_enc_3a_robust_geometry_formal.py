"""Resumable formal GEN-ENC-3A development and single-use validation driver."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Mapping

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
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    FAMILY_CONTRAST_ORDER,
    FAMILY_ORDER,
    PAIR_ORDER,
    PERMUTATION_REPLICATES,
    PERMUTATION_SEED,
    STATE_ORDER_DEGREES,
    batch_geometry_from_raw,
    evaluation_unit_weights,
    frobenius_gram_drift,
    identity_level_family_inference,
    pair_anisotropy,
    summarize_candidate_geometry,
    weakest_pair_index,
)


STAGE_ROOT = REPO / "outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY"
FORMAL_ROOT = STAGE_ROOT / "formal"
DEVELOPMENT_ROOT = FORMAL_ROOT / "development"
VALIDATION_ROOT = FORMAL_ROOT / "single_use_validation"
PREFLIGHT_ROOT = STAGE_ROOT / "preflight"
EXACT80_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json"
NUISANCE_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEED_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
COMMON_W_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/sealed/common_w.npz"
E2_D_CANDIDATE_ROOT = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/candidate_terminals"
E2_V_CANDIDATE_ROOT = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_v_single_use_validation_01/single_use_validation/candidate_terminals"
CONTRACT_DOC = REPO / "docs/experiment/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY_CONTRACT.md"
TEST_PATH = REPO / "tests/test_gen_enc_3a_robust_encoding_geometry.py"
FIXTURE_PATH = REPO / "tests/fixtures/gen_enc_3a_robust_geometry/synthetic_identity_inference_fixture.json"
GEOMETRY_FIXTURE_PATH = REPO / "tests/fixtures/gen_enc_3a_robust_geometry/synthetic_geometry_fixture.json"
VERIFIER_PATH = REPO / "scripts/gen_enc_3a_robust_geometry_independent_verifier.py"
MODULE_PATH = REPO / "src/acoustic_encoder/gen_enc/robust_encoding_geometry.py"

EXPECTED_HASHES = {
    "exact80": "e460eb09a05b5c8fb491250a6fe5d9046d0a1ebe7d70246f45ca117571779a08",
    "nuisance": "92d8e4ba137b19a6d71cc47460fecb950594632177020e982b12c11e6883e772",
    "seed": "e85eaf4435b159f8fd7c7b5669762d3a0600de4c4e12ecab6fcdcd7a39a96af9",
    "common_w": "3ba1ec8926dcbd60f9b670bbcf3079426d54c93330427089fa4b8ade5a44bc04",
}
CELL_COUNT = 3675
REPEAT_COUNT = 2
CELLS_PER_CHUNK = 25
CHUNK_COUNT = 147
AUDIT_UNIT_COUNT = 2
RESERVE_BYTES = 32 * 1024**3
MANAGED_CAP_BYTES = 48 * 1024**3


class FormalError(RuntimeError):
    """Fail-closed formal execution error."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalError("JSON_OBJECT_REQUIRED")
    return value


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(json_ready(value)))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_array_atomic(path: Path, value: np.ndarray) -> None:
    array = np.ascontiguousarray(value)
    if array.dtype not in (
        np.dtype("float64"),
        np.dtype("uint8"),
        np.dtype("complex128"),
    ) or not np.all(np.isfinite(array)):
        raise FormalError("FINITE_FROZEN_ARRAY_DTYPE_REQUIRED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def assert_not_preflight(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(PREFLIGHT_ROOT.resolve())
    except ValueError:
        return
    raise FormalError("PREFLIGHT_PAYLOAD_READ_OR_PROMOTION_FORBIDDEN")


def validate_frozen_hashes() -> None:
    observed = {
        "exact80": sha256_file(EXACT80_PATH),
        "nuisance": sha256_file(NUISANCE_PATH),
        "seed": sha256_file(SEED_PATH),
        "common_w": sha256_file(COMMON_W_PATH),
    }
    if observed != EXPECTED_HASHES:
        raise FormalError("FROZEN_INPUT_HASH_MISMATCH")
    for path in (EXACT80_PATH, NUISANCE_PATH, SEED_PATH, COMMON_W_PATH):
        assert_not_preflight(path)


def nuisance_rows() -> list[dict[str, float]]:
    rows = []
    with NUISANCE_PATH.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise FormalError("NUISANCE_METADATA_REQUIRED")
        for ordinal, row in enumerate(csv.DictReader(stream), start=1):
            if row["design_row_id"] != f"N{ordinal:04d}" or not np.isclose(
                float(row["cell_weight"]), 1.0 / CELL_COUNT, rtol=0.0, atol=1e-18
            ):
                raise FormalError("NUISANCE_IDENTITY_OR_WEIGHT_MISMATCH")
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
        raise FormalError("EXACT3675_REQUIRED")
    return rows


def exact80_members() -> list[tuple[dict[str, Any], dict[str, Any], Path]]:
    manifest = read_json(EXACT80_PATH)
    entries = manifest.get("members")
    if not isinstance(entries, list) or len(entries) != 80:
        raise FormalError("EXACT80_REQUIRED")
    result = []
    for ordinal, entry in enumerate(entries, start=1):
        identity_path = REPO / entry["identity_path"]
        assert_not_preflight(identity_path)
        if entry.get("global_ordinal") != ordinal or sha256_file(identity_path) != entry.get("identity_file_sha256"):
            raise FormalError("EXACT80_ORDER_OR_HASH_MISMATCH")
        member = read_json(identity_path)
        if member.get("member_id") != entry.get("member_id") or member.get("family_id") != entry.get("family_id"):
            raise FormalError("EXACT80_PAYLOAD_MISMATCH")
        result.append((entry, member, identity_path))
    return result


def managed_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def storage_gate() -> dict[str, int]:
    FORMAL_ROOT.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(FORMAL_ROOT).free
    managed = managed_bytes(FORMAL_ROOT)
    if free < RESERVE_BYTES or managed > MANAGED_CAP_BYTES:
        raise FormalError("RESOURCE_BLOCKED_STORAGE")
    return {"free_bytes": int(free), "managed_bytes": int(managed)}


def deterministic_audit_units(partition: str, identity_id: str) -> set[tuple[int, int]]:
    units = [(cell, repeat) for cell in range(CELL_COUNT) for repeat in range(REPEAT_COUNT)]
    return set(
        sorted(
            units,
            key=lambda unit: hashlib.sha256(
                f"GEN_ENC_3A_YD_AUDIT_V1|{partition}|{identity_id}|{unit[0]}|{unit[1]}".encode("utf-8")
            ).hexdigest(),
        )[:AUDIT_UNIT_COUNT]
    )


def array_slice_hash(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(array.dtype.name.encode("ascii"))
    digest.update(json.dumps(list(array.shape), separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def open_or_create_memmap(path: Path, dtype: str, shape: tuple[int, ...]) -> np.memmap:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        value = np.load(path, allow_pickle=False, mmap_mode="r+")
        if value.dtype != np.dtype(dtype) or value.shape != shape:
            raise FormalError("RESUME_MEMMAP_SHAPE_OR_DTYPE_MISMATCH")
        return value
    return np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=shape, version=(1, 0))


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
                state_angles_degrees=STATE_ORDER_DEGREES,
                partition=partition,
                repeat_seed_tuple=seeds,
            ).central_pressure
    return output


def verify_phase1_receipt(
    receipt: dict[str, Any],
    distances: np.ndarray,
    weakest: np.ndarray,
    anisotropy: np.ndarray,
    grams: np.ndarray,
    start: int,
    end: int,
) -> None:
    observed = {
        "distances": array_slice_hash(distances[start:end]),
        "weakest_pair": array_slice_hash(weakest[start:end]),
        "pair_anisotropy": array_slice_hash(anisotropy[start:end]),
        "normalized_grams_temporary": array_slice_hash(grams[start:end]),
    }
    if receipt.get("status") != "PASS" or receipt.get("payload_slice_hashes") != observed:
        raise FormalError("PHASE1_RESUME_RECEIPT_MISMATCH")


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
) -> Path:
    identity_id = str(member["member_id"])
    candidate_root = output_root / "candidates" / identity_id
    terminal_path = candidate_root / "candidate_terminal.json"
    if terminal_path.is_file():
        terminal = read_json(terminal_path)
        if (
            terminal.get("status") != "PASS"
            or terminal.get("identity_id") != identity_id
            or terminal.get("partition") != partition
            or terminal.get("preflight_reused") is not False
            or terminal.get("recomputed_from_frozen_source") is not True
        ):
            raise FormalError("COMPLETED_CANDIDATE_TERMINAL_MISMATCH")
        return terminal_path
    compact = candidate_root / "compact"
    temp = candidate_root / "tmp"
    distances_path = compact / "distances.npy"
    weakest_path = compact / "weakest_pair_index.npy"
    anisotropy_path = compact / "pair_anisotropy.npy"
    drift_path = compact / "gram_drift.npy"
    grams_path = temp / "normalized_grams.npy"
    distances = open_or_create_memmap(distances_path, "float64", (CELL_COUNT, REPEAT_COUNT, 6))
    weakest = open_or_create_memmap(weakest_path, "uint8", (CELL_COUNT, REPEAT_COUNT))
    anisotropy = open_or_create_memmap(anisotropy_path, "float64", (CELL_COUNT, REPEAT_COUNT))
    grams = open_or_create_memmap(grams_path, "complex128", (CELL_COUNT, REPEAT_COUNT, 4, 4))
    audit_units = deterministic_audit_units(partition, identity_id)
    audit_written: set[tuple[int, int]] = set()
    for chunk_index in range(CHUNK_COUNT):
        chunk_id = f"chunk_{chunk_index:03d}"
        start = chunk_index * CELLS_PER_CHUNK
        end = start + CELLS_PER_CHUNK
        receipt_path = candidate_root / "receipts/phase1" / f"{chunk_id}.json"
        if receipt_path.is_file():
            verify_phase1_receipt(read_json(receipt_path), distances, weakest, anisotropy, grams, start, end)
            for unit in audit_units:
                if start <= unit[0] < end:
                    audit_path = candidate_root / "audit_y_diff" / f"cell_{unit[0]:04d}_repeat_{unit[1]}.npy"
                    if not audit_path.is_file():
                        raise FormalError("AUDIT_Y_DIFF_MISSING_ON_RESUME")
                    audit_written.add(unit)
            continue
        raw = generate_chunk(member, nuisance, partition=partition, seeds=seeds, start=start, end=end)
        chunk_distances, chunk_grams, y_diff = batch_geometry_from_raw(raw, whitener)
        chunk_weakest = weakest_pair_index(chunk_distances)
        chunk_anisotropy = pair_anisotropy(chunk_distances)
        distances[start:end] = chunk_distances
        weakest[start:end] = chunk_weakest
        anisotropy[start:end] = chunk_anisotropy
        grams[start:end] = chunk_grams
        distances.flush()
        weakest.flush()
        anisotropy.flush()
        grams.flush()
        for cell, repeat in sorted(audit_units):
            if start <= cell < end:
                audit_path = candidate_root / "audit_y_diff" / f"cell_{cell:04d}_repeat_{repeat}.npy"
                write_array_atomic(audit_path, y_diff[cell - start, repeat])
                audit_written.add((cell, repeat))
        receipt = {
            "schema_version": "gen_enc_3a_formal_phase1_chunk_receipt_v1",
            "status": "PASS",
            "partition": partition,
            "identity_id": identity_id,
            "chunk_id": chunk_id,
            "cell_start": start,
            "cell_end_exclusive": end,
            "raw_in_memory_hash": array_slice_hash(raw),
            "raw_retained": False,
            "payload_slice_hashes": {
                "distances": array_slice_hash(distances[start:end]),
                "weakest_pair": array_slice_hash(weakest[start:end]),
                "pair_anisotropy": array_slice_hash(anisotropy[start:end]),
                "normalized_grams_temporary": array_slice_hash(grams[start:end]),
            },
            "identity_path": identity_path.relative_to(REPO).as_posix(),
            "identity_sha256": sha256_file(identity_path),
            "common_w_sha256": EXPECTED_HASHES["common_w"],
            "preflight_reused": False,
            "final_test_read": False,
        }
        write_json_atomic(receipt_path, receipt)
        write_json_atomic(
            candidate_root / "checkpoint.json",
            {
                "status": "PHASE1_IN_PROGRESS",
                "completed_chunks": chunk_index + 1,
                "last_chunk": chunk_id,
                "resume_supported": True,
                "preflight_reused": False,
                "final_test_read": False,
            },
        )
    if len(audit_written) != AUDIT_UNIT_COUNT:
        raise FormalError("EXACT_TWO_AUDIT_UNITS_REQUIRED")

    if partition == "development":
        reference = np.mean(grams, axis=(0, 1), dtype=np.complex128)
        reference = 0.5 * (reference + reference.conj().T)
        reference /= float(np.trace(reference).real)
        reference_path = candidate_root / "reference/development_reference_gram.npy"
        write_array_atomic(reference_path, reference)
        reference_seal = {
            "schema_version": "gen_enc_3a_development_reference_seal_v1",
            "status": "SEALED",
            "identity_id": identity_id,
            "source_units": CELL_COUNT * REPEAT_COUNT,
            "reference_path": reference_path.relative_to(REPO).as_posix(),
            "reference_sha256": sha256_file(reference_path),
            "common_w_sha256": EXPECTED_HASHES["common_w"],
            "normalization": "CANONICAL_COMPLEX_HERMITIAN_TRACE_ONE",
            "validation_may_update": False,
            "preflight_reused": False,
            "final_test_read": False,
        }
        write_json_atomic(candidate_root / "reference/reference_seal.json", reference_seal)
    else:
        development_reference_root = DEVELOPMENT_ROOT / "candidates" / identity_id / "reference"
        reference_seal_path = development_reference_root / "reference_seal.json"
        reference_seal = read_json(reference_seal_path)
        reference_path = REPO / reference_seal["reference_path"]
        assert_not_preflight(reference_path)
        if (
            reference_seal.get("status") != "SEALED"
            or reference_seal.get("identity_id") != identity_id
            or reference_seal.get("validation_may_update") is not False
            or sha256_file(reference_path) != reference_seal.get("reference_sha256")
        ):
            raise FormalError("DEVELOPMENT_REFERENCE_SEAL_REQUIRED")
        reference = np.asarray(np.load(reference_path, allow_pickle=False), dtype=np.complex128)
        write_json_atomic(
            candidate_root / "reference_binding.json",
            {
                "identity_id": identity_id,
                "development_reference_path": reference_path.relative_to(REPO).as_posix(),
                "development_reference_sha256": sha256_file(reference_path),
                "validation_updated_reference": False,
                "final_test_read": False,
            },
        )

    drift = open_or_create_memmap(drift_path, "float64", (CELL_COUNT, REPEAT_COUNT))
    for chunk_index in range(CHUNK_COUNT):
        chunk_id = f"chunk_{chunk_index:03d}"
        start = chunk_index * CELLS_PER_CHUNK
        end = start + CELLS_PER_CHUNK
        receipt_path = candidate_root / "receipts/phase2" / f"{chunk_id}.json"
        if receipt_path.is_file():
            receipt = read_json(receipt_path)
            if receipt.get("drift_slice_hash") != array_slice_hash(drift[start:end]):
                raise FormalError("PHASE2_RESUME_RECEIPT_MISMATCH")
            continue
        drift[start:end] = frobenius_gram_drift(grams[start:end].reshape((-1, 4, 4)), reference).reshape(
            (CELLS_PER_CHUNK, REPEAT_COUNT)
        )
        drift.flush()
        write_json_atomic(
            receipt_path,
            {
                "schema_version": "gen_enc_3a_formal_phase2_chunk_receipt_v1",
                "status": "PASS",
                "partition": partition,
                "identity_id": identity_id,
                "chunk_id": chunk_id,
                "cell_start": start,
                "cell_end_exclusive": end,
                "drift_slice_hash": array_slice_hash(drift[start:end]),
                "reference_sha256": sha256_file(reference_path),
                "preflight_reused": False,
                "final_test_read": False,
            },
        )
        write_json_atomic(
            candidate_root / "checkpoint.json",
            {
                "status": "PHASE2_IN_PROGRESS",
                "completed_chunks": chunk_index + 1,
                "last_chunk": chunk_id,
                "resume_supported": True,
                "preflight_reused": False,
                "final_test_read": False,
            },
        )

    summary = summarize_candidate_geometry(
        np.asarray(distances).reshape((-1, 6)),
        np.asarray(drift).reshape(-1),
        evaluation_unit_weights(),
    )
    e2_terminal_root = E2_D_CANDIDATE_ROOT if partition == "development" else E2_V_CANDIDATE_ROOT
    e2_terminal_path = e2_terminal_root / f"{identity_id}.json"
    assert_not_preflight(e2_terminal_path)
    e2_terminal = read_json(e2_terminal_path)
    primary = e2_terminal.get("primary", {})
    feasibility = bool(
        e2_terminal.get("scientific_status") == "PASS"
        and primary.get("E_primary", -math.inf) > 1.0
        and primary.get("r_stable") == 3
        and primary.get("stable_rank_eligible") is True
    )
    cost = member["cad_static_audit"]
    summary_value = {
        "schema_version": "gen_enc_3a_candidate_geometry_summary_v1",
        "identity_id": identity_id,
        "family_id": member["family_id"],
        "partition": partition,
        "state_order_degrees": list(STATE_ORDER_DEGREES),
        "pair_order_degrees": [list(pair) for pair in PAIR_ORDER],
        "metrics": summary,
        "e2_feasibility_gate": {
            "passed": feasibility,
            "E_primary": primary.get("E_primary"),
            "r_stable": primary.get("r_stable"),
            "used_for_3a_ranking": False,
            "source_path": e2_terminal_path.relative_to(REPO).as_posix(),
            "source_sha256": sha256_file(e2_terminal_path),
        },
        "cost": {
            "volume_m3": cost["volume_m3"],
            "dof": cost["dof"],
            "minimum_feature_m": cost["minimum_feature_m"],
            "solid_load_path_m": cost["solid_load_path_m"],
            "claim": "SAME_VOLUME_MINIMUM_FEATURE_SOLID_LOAD_PATH_AND_DOF_12_TO_15_ENVELOPE_NOT_FULLY_EQUAL_COST",
        },
        "canonical_complex_gram_claim_limit": "STATE_GEOMETRY_NOT_PHYSICAL_PHASE_MECHANISM",
        "validation_refit": False,
        "preflight_reused": False,
        "recomputed_from_frozen_source": True,
        "final_test_read": False,
    }
    summary_path = candidate_root / "candidate_summary.json"
    write_json_atomic(summary_path, summary_value)
    audit_files = sorted((candidate_root / "audit_y_diff").glob("*.npy"))
    if len(audit_files) != AUDIT_UNIT_COUNT:
        raise FormalError("EXACT_TWO_AUDIT_FILES_REQUIRED")
    compact_manifest = {
        "schema_version": "gen_enc_3a_candidate_compact_manifest_v1",
        "identity_id": identity_id,
        "partition": partition,
        "arrays": {
            "distances": {"path": distances_path.relative_to(REPO).as_posix(), "sha256": sha256_file(distances_path), "shape": [CELL_COUNT, 2, 6], "dtype": "float64"},
            "weakest_pair_index": {"path": weakest_path.relative_to(REPO).as_posix(), "sha256": sha256_file(weakest_path), "shape": [CELL_COUNT, 2], "dtype": "uint8"},
            "pair_anisotropy": {"path": anisotropy_path.relative_to(REPO).as_posix(), "sha256": sha256_file(anisotropy_path), "shape": [CELL_COUNT, 2], "dtype": "float64"},
            "gram_drift": {"path": drift_path.relative_to(REPO).as_posix(), "sha256": sha256_file(drift_path), "shape": [CELL_COUNT, 2], "dtype": "float64"},
        },
        "audit_y_diff": [
            {"path": path.relative_to(REPO).as_posix(), "sha256": sha256_file(path), "shape": [832, 4], "dtype": "complex128"}
            for path in audit_files
        ],
        "phase1_receipts": CHUNK_COUNT,
        "phase2_receipts": CHUNK_COUNT,
        "full_raw_y_diff_retained": False,
        "temporary_normalized_grams_retained": False,
        "preflight_reused": False,
        "final_test_read": False,
    }
    compact_manifest_path = candidate_root / "compact_manifest.json"
    write_json_atomic(compact_manifest_path, compact_manifest)
    terminal = {
        "schema_version": "gen_enc_3a_candidate_terminal_v1",
        "status": "PASS",
        "identity_id": identity_id,
        "family_id": member["family_id"],
        "partition": partition,
        "feasibility_gate_passed": feasibility,
        "candidate_summary_path": summary_path.relative_to(REPO).as_posix(),
        "candidate_summary_sha256": sha256_file(summary_path),
        "compact_manifest_path": compact_manifest_path.relative_to(REPO).as_posix(),
        "compact_manifest_sha256": sha256_file(compact_manifest_path),
        "reference_sha256": sha256_file(reference_path),
        "common_w_sha256": EXPECTED_HASHES["common_w"],
        "preflight_reused": False,
        "recomputed_from_frozen_source": True,
        "final_test_read": False,
    }
    write_json_atomic(terminal_path, terminal)
    if grams_path.is_file():
        grams._mmap.close()
        grams_path.unlink()
    write_json_atomic(
        candidate_root / "checkpoint.json",
        {
            "status": "CANDIDATE_COMPLETE",
            "terminal_path": terminal_path.relative_to(REPO).as_posix(),
            "terminal_sha256": sha256_file(terminal_path),
            "resume_supported": True,
            "preflight_reused": False,
            "final_test_read": False,
        },
    )
    return terminal_path


def family_distributions(candidate_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for family in FAMILY_ORDER:
        members = [value for value in candidate_summaries if value["family_id"] == family]
        if len(members) != 20:
            raise FormalError("EXACT20_FAMILY_SUMMARIES_REQUIRED")
        margins = np.asarray([value["metrics"]["d_min_lower_tail_es_0p05"] for value in members], dtype=float)
        drifts = np.asarray([value["metrics"]["gram_frobenius_drift_upper_tail_es_0p05"] for value in members], dtype=float)
        margin_worst_index = int(np.argmin(margins))
        drift_worst_index = int(np.argmax(drifts))
        result[family] = {
            "member_ids": [value["identity_id"] for value in members],
            "margin_values": margins,
            "drift_values": drifts,
            "margin": {
                "mean": float(np.mean(margins)),
                "median": float(np.median(margins)),
                "q25_q75": np.quantile(margins, (0.25, 0.75), method="linear"),
                "worst_member": members[margin_worst_index]["identity_id"],
                "worst_value": float(margins[margin_worst_index]),
            },
            "drift": {
                "mean": float(np.mean(drifts)),
                "median": float(np.median(drifts)),
                "q25_q75": np.quantile(drifts, (0.25, 0.75), method="linear"),
                "worst_member": members[drift_worst_index]["identity_id"],
                "worst_value": float(drifts[drift_worst_index]),
            },
        }
    return result


def unique_leader(families: dict[str, Any], endpoint: str) -> str | None:
    values = {
        family: record[endpoint]["worst_value"]
        for family, record in families.items()
    }
    target = max(values.values()) if endpoint == "margin" else min(values.values())
    winners = [family for family, value in values.items() if value == target]
    return winners[0] if len(winners) == 1 else None


def save_inference(output_root: Path, families: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    margin = {family: np.asarray(families[family]["margin_values"], dtype=float) for family in FAMILY_ORDER}
    drift = {family: np.asarray(families[family]["drift_values"], dtype=float) for family in FAMILY_ORDER}
    inference = identity_level_family_inference(margin, drift)
    inference_root = output_root / "inference"
    bootstrap_margin_path = inference_root / "bootstrap_margin_contrasts.npy"
    bootstrap_drift_path = inference_root / "bootstrap_drift_contrasts.npy"
    write_array_atomic(bootstrap_margin_path, inference["bootstrap"]["margin_contrasts"])
    write_array_atomic(bootstrap_drift_path, inference["bootstrap"]["drift_contrasts"])
    permutation_manifest = None
    if inference["permutation"] is not None:
        maxima_path = inference_root / "permutation_max_abs_t.npy"
        write_array_atomic(maxima_path, inference["permutation"]["max_abs_t"])
        permutation_manifest = {
            "replicates": inference["permutation"]["replicates"],
            "seed": inference["permutation"]["seed"],
            "generator": inference["permutation"]["generator"],
            "observed_twelve": inference["permutation"]["observed_twelve"],
            "adjusted_p": inference["permutation"]["adjusted_p"],
            "adjusted_p_formula_denominator": inference["permutation"]["adjusted_p_formula_denominator"],
            "statistic_count": inference["permutation"]["statistic_count"],
            "max_abs_t_path": maxima_path.relative_to(REPO).as_posix(),
            "max_abs_t_sha256": sha256_file(maxima_path),
        }
    summary = {
        "schema_version": "gen_enc_3a_identity_level_inference_v1",
        "status": inference["status"],
        "reason": inference["reason"],
        "sampling_unit": "IDENTITY",
        "family_order": list(FAMILY_ORDER),
        "contrast_order": [list(pair) for pair in FAMILY_CONTRAST_ORDER],
        "margin_direction": "MEAN_A_MINUS_MEAN_B_POSITIVE_FAVORS_A",
        "drift_direction": "MEAN_B_MINUS_MEAN_A_POSITIVE_FAVORS_A",
        "welch_se": "SQRT(DDOF1_VAR_A/20+DDOF1_VAR_B/20)",
        "observed": inference["observed"],
        "bootstrap": {
            "replicates": inference["bootstrap"]["replicates"],
            "seed": inference["bootstrap"]["seed"],
            "generator": inference["bootstrap"]["generator"],
            "quantile_method": inference["bootstrap"]["quantile_method"],
            "margin_percentile_95_ci": inference["bootstrap"]["margin_percentile_95_ci"],
            "drift_percentile_95_ci": inference["bootstrap"]["drift_percentile_95_ci"],
            "margin_contrasts_path": bootstrap_margin_path.relative_to(REPO).as_posix(),
            "margin_contrasts_sha256": sha256_file(bootstrap_margin_path),
            "drift_contrasts_path": bootstrap_drift_path.relative_to(REPO).as_posix(),
            "drift_contrasts_sha256": sha256_file(bootstrap_drift_path),
        },
        "permutation": permutation_manifest,
        "cell_repeat_frequency_resampled_or_permuted": False,
        "final_test_read": False,
    }
    summary_path = inference_root / "inference_summary.json"
    write_json_atomic(summary_path, summary)
    return summary, summary_path


def aggregate_partition(output_root: Path, *, partition: str) -> tuple[dict[str, Any], Path, Path]:
    terminal_paths = sorted((output_root / "candidates").glob("*/candidate_terminal.json"))
    if len(terminal_paths) != 80:
        raise FormalError("EXACT80_CANDIDATE_TERMINALS_REQUIRED")
    terminals = [read_json(path) for path in terminal_paths]
    if any(value.get("status") != "PASS" or value.get("partition") != partition for value in terminals):
        raise FormalError("CANDIDATE_TERMINAL_FAIL")
    summaries = [read_json(REPO / value["candidate_summary_path"]) for value in terminals]
    summaries.sort(key=lambda value: next(index for index, family in enumerate(FAMILY_ORDER) if value["family_id"] == family) * 20 + int(value["identity_id"].split("_")[1]))
    families = family_distributions(summaries)
    family_summary = {
        "schema_version": "gen_enc_3a_family_summary_v1",
        "partition": partition,
        "sampling_unit": "IDENTITY",
        "exact20": True,
        "families": families,
        "margin_worst_member_leader": unique_leader(families, "margin"),
        "drift_worst_member_leader": unique_leader(families, "drift"),
        "cost_claim": "SAME_VOLUME_MINIMUM_FEATURE_SOLID_LOAD_PATH_AND_DOF_12_TO_15_ENVELOPE_NOT_FULLY_EQUAL_COST",
        "final_test_read": False,
    }
    family_path = output_root / "family_summary.json"
    write_json_atomic(family_path, family_summary)
    inference, inference_path = save_inference(output_root, families)
    return {"family": family_summary, "inference": inference}, family_path, inference_path


def directed_contrast(inference: dict[str, Any], endpoint: str, leader: str, other: str) -> tuple[float, tuple[float, float], float]:
    if leader == other:
        raise FormalError("DISTINCT_FAMILY_CONTRAST_REQUIRED")
    left_index = FAMILY_ORDER.index(leader)
    right_index = FAMILY_ORDER.index(other)
    if left_index < right_index:
        pair = (leader, other)
        sign = 1.0
    else:
        pair = (other, leader)
        sign = -1.0
    index = FAMILY_CONTRAST_ORDER.index(pair)
    observed = float(inference["observed"][endpoint]["contrasts"][index]) * sign
    ci_key = f"{endpoint}_percentile_95_ci"
    raw_ci = inference["bootstrap"][ci_key][index]
    ci = (float(raw_ci[0]), float(raw_ci[1])) if sign > 0 else (-float(raw_ci[1]), -float(raw_ci[0]))
    offset = 0 if endpoint == "margin" else 6
    adjusted_p = float(inference["permutation"]["adjusted_p"][offset + index])
    return observed, ci, adjusted_p


def scientific_terminal(development: dict[str, Any], validation: dict[str, Any], all_feasible: bool) -> dict[str, Any]:
    d_family = development["family"]
    v_family = validation["family"]
    d_inference = development["inference"]
    v_inference = validation["inference"]
    if d_inference["status"] != "AVAILABLE" or v_inference["status"] != "AVAILABLE":
        return {"terminal": "GEN_ENC_3A_INCONCLUSIVE", "reason": "IDENTITY_LEVEL_INFERENCE_UNAVAILABLE", "recommend_3b": False}
    if not all_feasible:
        return {"terminal": "GEN_ENC_3A_NO_STABLE_FAMILY_SEPARATION", "reason": "AT_LEAST_ONE_E2_FEASIBILITY_GATE_FAILED", "recommend_3b": False}
    leaders = (
        d_family["margin_worst_member_leader"],
        d_family["drift_worst_member_leader"],
        v_family["margin_worst_member_leader"],
        v_family["drift_worst_member_leader"],
    )
    same_joint_leader = leaders[0] is not None and len(set(leaders)) == 1
    stable_contrasts = same_joint_leader
    detail = []
    if same_joint_leader:
        leader = str(leaders[0])
        for other in FAMILY_ORDER:
            if other == leader:
                continue
            for endpoint in ("margin", "drift"):
                d_observed, _, _ = directed_contrast(d_inference, endpoint, leader, other)
                v_observed, v_ci, v_p = directed_contrast(v_inference, endpoint, leader, other)
                passed = d_observed > 0.0 and v_observed > 0.0 and v_ci[0] > 0.0 and v_p <= 0.05
                stable_contrasts = stable_contrasts and passed
                detail.append({"leader": leader, "other": other, "endpoint": endpoint, "development_delta": d_observed, "validation_delta": v_observed, "validation_ci": list(v_ci), "validation_adjusted_p": v_p, "passed": passed})
    if stable_contrasts:
        return {"terminal": "GEN_ENC_3A_STABLE_FAMILY_SEPARATION_SUPPORTED", "reason": "JOINT_MARGIN_AND_DRIFT_D_V_IDENTITY_LEVEL_GATE_PASS", "leader": leaders[0], "contrast_gate": detail, "recommend_3b": True}
    any_adjusted_difference = False
    for endpoint, offset in (("margin", 0), ("drift", 6)):
        cis = np.asarray(v_inference["bootstrap"][f"{endpoint}_percentile_95_ci"], dtype=float)
        pvalues = np.asarray(v_inference["permutation"]["adjusted_p"][offset : offset + 6], dtype=float)
        any_adjusted_difference = any_adjusted_difference or bool(np.any((pvalues <= 0.05) & ((cis[:, 0] > 0.0) | (cis[:, 1] < 0.0))))
    if any_adjusted_difference:
        return {"terminal": "GEN_ENC_3A_ROBUST_GEOMETRY_DIFFERENCES_PARTIAL", "reason": "AT_LEAST_ONE_ADJUSTED_VALIDATION_FAMILY_DIFFERENCE_WITHOUT_JOINT_STABLE_LEADER", "leaders": list(leaders), "contrast_gate": detail, "recommend_3b": False}
    return {"terminal": "GEN_ENC_3A_NO_STABLE_FAMILY_SEPARATION", "reason": "NO_ADJUSTED_VALIDATION_FAMILY_DIFFERENCE_OR_UNSTABLE_LEADER", "leaders": list(leaders), "contrast_gate": detail, "recommend_3b": False}


def source_manifest() -> dict[str, Any]:
    paths = {
        "formal_driver": Path(__file__).resolve(),
        "independent_verifier": VERIFIER_PATH,
        "formula_module": MODULE_PATH,
        "contract": CONTRACT_DOC,
        "formula_tests": TEST_PATH,
        "inference_fixture": FIXTURE_PATH,
        "geometry_fixture": GEOMETRY_FIXTURE_PATH,
        "exact80": EXACT80_PATH,
        "nuisance": NUISANCE_PATH,
        "seed": SEED_PATH,
        "common_w": COMMON_W_PATH,
    }
    return {
        "schema_version": "gen_enc_3a_formal_source_manifest_v1",
        "entries": {
            name: {"path": path.relative_to(REPO).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for name, path in paths.items()
        },
        "preflight_payload_source": False,
        "final_test_read": False,
    }


def prepare() -> int:
    validate_frozen_hashes()
    if not VERIFIER_PATH.is_file():
        raise FormalError("INDEPENDENT_VERIFIER_REQUIRED")
    FORMAL_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = source_manifest()
    write_json_atomic(FORMAL_ROOT / "source_manifest.json", manifest)
    authorization = {
        "schema_version": "gen_enc_3a_formal_authority_v1",
        "status": "AUTHORIZED_AFTER_PREEXECUTION_APPROVE_WITH_CORRECTIONS",
        "top_level_task_id": "01a0366d-bb5e-7a13-a1f7-b34403664543",
        "guardian_task_id": "01a061f9-64fc-7e51-a9e6-659dd7ffe2ae",
        "corrections": ["EXECUTABLE_IDENTITY_INFERENCE", "INFERENCE_SYNTHETIC_TESTS", "FORMAL_PREFLIGHT_ISOLATION_AND_INDEPENDENT_RECOMPUTATION"],
        "development_authorized": True,
        "validation_authorized_only_after_development_seal": True,
        "preflight_reuse": False,
        "final_test_read": False,
    }
    write_json_atomic(FORMAL_ROOT / "authorization.json", authorization)
    print(json.dumps({"status": authorization["status"], "development_authorized": True, "validation_open": False}, sort_keys=True))
    return 0


def run_partition(partition: str, *, resume: bool) -> int:
    validate_frozen_hashes()
    source_path = FORMAL_ROOT / "source_manifest.json"
    authorization_path = FORMAL_ROOT / "authorization.json"
    if not source_path.is_file() or not authorization_path.is_file():
        raise FormalError("PREPARE_REQUIRED")
    expected_source = source_manifest()
    if read_json(source_path) != expected_source:
        raise FormalError("FORMAL_SOURCE_MANIFEST_MISMATCH")
    authorization = read_json(authorization_path)
    if authorization.get("status") != "AUTHORIZED_AFTER_PREEXECUTION_APPROVE_WITH_CORRECTIONS":
        raise FormalError("FORMAL_AUTHORIZATION_MISMATCH")
    output_root = DEVELOPMENT_ROOT if partition == "development" else VALIDATION_ROOT
    if output_root.exists() and not resume:
        raise FormalError("PARTITION_ROOT_EXISTS_USE_RESUME")
    if (output_root / "partition_terminal.json").is_file():
        raise FormalError("COMPLETED_PARTITION_CANNOT_REOPEN")
    if partition == "single_use_validation":
        development_terminal_path = DEVELOPMENT_ROOT / "partition_terminal.json"
        development_terminal = read_json(development_terminal_path)
        if (
            development_terminal.get("status") != "GEN_ENC_3A_D_SEALED"
            or development_terminal.get("complete_identities") != 80
            or development_terminal.get("sealed_references") != 80
            or development_terminal.get("common_w_sha256") != EXPECTED_HASHES["common_w"]
            or development_terminal.get("preflight_reused") is not False
        ):
            raise FormalError("COMPLETE_DEVELOPMENT_SEAL_REQUIRED_BEFORE_VALIDATION")
    output_root.mkdir(parents=True, exist_ok=True)
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    nuisance = nuisance_rows()
    seed = read_json(SEED_PATH)
    seed_key = "development_training" if partition == "development" else "single_use_validation"
    seeds = tuple(seed["nuisance_partition_seeds"][seed_key])
    expected_seeds = (2026091001, 2026091002) if partition == "development" else (2026092001, 2026092002)
    if seeds != expected_seeds:
        raise FormalError("PARTITION_SEED_MISMATCH")
    with np.load(COMMON_W_PATH, allow_pickle=False) as sealed:
        whitener = np.asarray(sealed["operator"], dtype=np.float64)
    members = exact80_members()
    terminal_paths = []
    for ordinal, (entry, member, identity_path) in enumerate(members, start=1):
        terminal_path = process_identity(
            entry,
            member,
            identity_path,
            nuisance,
            whitener,
            partition=partition,
            seeds=seeds,
            output_root=output_root,
        )
        terminal_paths.append(terminal_path)
        write_json_atomic(
            output_root / "checkpoint.json",
            {
                "schema_version": "gen_enc_3a_partition_checkpoint_v1",
                "status": "PARTITION_IN_PROGRESS",
                "partition": partition,
                "completed_identities": ordinal,
                "last_identity": member["member_id"],
                "resume_supported": True,
                "preflight_reused": False,
                "hand_01_recomputed": True,
                "resource": storage_gate(),
                "final_test_read": False,
            },
        )
    aggregate, family_path, inference_path = aggregate_partition(output_root, partition=partition)
    summaries = [read_json(path.parent / "candidate_summary.json") for path in terminal_paths]
    all_feasible = all(value["e2_feasibility_gate"]["passed"] for value in summaries)
    if partition == "development":
        terminal_value = {
            "schema_version": "gen_enc_3a_development_partition_terminal_v1",
            "status": "GEN_ENC_3A_D_SEALED",
            "partition": partition,
            "complete_identities": 80,
            "sealed_references": 80,
            "common_w_sha256": EXPECTED_HASHES["common_w"],
            "candidate_terminal_hashes": [sha256_file(path) for path in terminal_paths],
            "family_summary_path": family_path.relative_to(REPO).as_posix(),
            "family_summary_sha256": sha256_file(family_path),
            "inference_path": inference_path.relative_to(REPO).as_posix(),
            "inference_sha256": sha256_file(inference_path),
            "all_e2_feasibility_gates_passed": all_feasible,
            "development_decisions_sealed": True,
            "validation_opened": False,
            "validation_refit": False,
            "preflight_reused": False,
            "hand_01_recomputed": True,
            "source_manifest_sha256": sha256_file(source_path),
            "resource": {"wall_seconds": time.perf_counter() - start_wall, "process_cpu_seconds": time.process_time() - start_cpu, **storage_gate()},
            "final_test_read": False,
        }
    else:
        development_aggregate = {
            "family": read_json(DEVELOPMENT_ROOT / "family_summary.json"),
            "inference": read_json(DEVELOPMENT_ROOT / "inference/inference_summary.json"),
        }
        decision = scientific_terminal(development_aggregate, aggregate, all_feasible)
        terminal_value = {
            "schema_version": "gen_enc_3a_validation_partition_terminal_v1",
            "status": "GEN_ENC_3A_V_SINGLE_USE_SEALED",
            "partition": partition,
            "complete_identities": 80,
            "development_terminal_path": (DEVELOPMENT_ROOT / "partition_terminal.json").relative_to(REPO).as_posix(),
            "development_terminal_sha256": sha256_file(DEVELOPMENT_ROOT / "partition_terminal.json"),
            "common_w_sha256": EXPECTED_HASHES["common_w"],
            "candidate_terminal_hashes": [sha256_file(path) for path in terminal_paths],
            "family_summary_path": family_path.relative_to(REPO).as_posix(),
            "family_summary_sha256": sha256_file(family_path),
            "inference_path": inference_path.relative_to(REPO).as_posix(),
            "inference_sha256": sha256_file(inference_path),
            "all_e2_feasibility_gates_passed": all_feasible,
            "scientific_decision": decision,
            "single_use_consumed": True,
            "validation_feedback_to_development": False,
            "validation_refit": False,
            "preflight_reused": False,
            "hand_01_recomputed": True,
            "source_manifest_sha256": sha256_file(source_path),
            "resource": {"wall_seconds": time.perf_counter() - start_wall, "process_cpu_seconds": time.process_time() - start_cpu, **storage_gate()},
            "final_test_read": False,
        }
    terminal_path = output_root / "partition_terminal.json"
    write_json_atomic(terminal_path, terminal_value)
    write_json_atomic(
        output_root / "checkpoint.json",
        {
            "schema_version": "gen_enc_3a_partition_checkpoint_v1",
            "status": "PARTITION_COMPLETE",
            "partition": partition,
            "terminal_path": terminal_path.relative_to(REPO).as_posix(),
            "terminal_sha256": sha256_file(terminal_path),
            "resume_supported": True,
            "preflight_reused": False,
            "final_test_read": False,
        },
    )
    print(json.dumps({"status": terminal_value["status"], "partition": partition, "complete_identities": 80, "preflight_reused": False}, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("mode", choices=("self-test", "prepare", "development", "single-use-validation"))
    value.add_argument("--resume", action="store_true")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(json.dumps({"status": "PASS", "formal_root": FORMAL_ROOT.relative_to(REPO).as_posix(), "preflight_input_allowed": False, "final_test_read": False}, sort_keys=True))
            return 0
        if args.mode == "prepare":
            return prepare()
        partition = "development" if args.mode == "development" else "single_use_validation"
        return run_partition(partition, resume=args.resume)
    except (OSError, KeyError, ValueError, np.linalg.LinAlgError, FormalError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

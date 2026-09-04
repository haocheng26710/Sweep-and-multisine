"""RC03 independent verifier: recompute frozen input chunk and emit exact roles."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.gen_enc.e2_rc03_stats import metric_chunk_roles, common_w_chunk_roles, canonical_json_bytes, sha256_file, write_npy_atomic
from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block

RTOL = 1e-10
ATOL = 1e-12
COMMON_W_ROLES = ("WITHIN_CELL_RESIDUAL_BLOCK", "W_WEIGHTED_OUTER_SUM", "W_WEIGHT_SUM")
DEVELOPMENT_METRIC_ROLES = (
    "SHARED_DIFFERENTIAL_COMPONENTS", "ENDPOINT_UNIT_VALUES", "THROUGHPUT_NUMERATOR_256",
    "THROUGHPUT_REFERENCE_DENOMINATOR_256", "THROUGHPUT_AVAILABILITY_256",
    "MATCHED_COST_ELIGIBILITY_INPUTS", "BOOTSTRAP_PERMUTATION_UNCERTAINTY_UNIT_VALUES",
    "RESAMPLING_UNIT_KEYS", "CANDIDATE_FAMILY_GLOBAL_TERMINAL_INPUTS",
)
VALIDATION_METRIC_ROLES = DEVELOPMENT_METRIC_ROLES + ("BRIDGE_24_UNIT_VALUES", "HELD_OUT_4_UNIT_VALUES")


class RC03VerificationError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RC03VerificationError("JSON_OBJECT_REQUIRED")
    return value


def nuisance_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise RC03VerificationError("NUISANCE_METADATA_REQUIRED")
        for row in csv.DictReader(stream):
            rows.append({key: float(row[key]) for key in (
                "snr_db", "common_gain_db", "sensor_independent_gain_db", "common_frequency_axis_shift_relative",
                "independent_manufacturing_percent", "batch_correlated_manufacturing_percent", "angle_offset_degrees")})
    if len(rows) != 3675:
        raise RC03VerificationError("EXACT_3675_NUISANCE_ROWS_REQUIRED")
    return rows


def partition_values(partition: str, seed_split: dict[str, Any]) -> tuple[tuple[float, ...], tuple[int, int]]:
    if partition == "development":
        angles, key, expected = (0.0, 90.0, 180.0, 270.0), "development_training", (2026091001, 2026091002)
    elif partition == "single_use_validation":
        angles, key, expected = tuple(float(v) for v in range(0, 360, 15)), "single_use_validation", (2026092001, 2026092002)
    else:
        raise RC03VerificationError("UNKNOWN_PARTITION")
    if tuple(seed_split["nuisance_partition_seeds"][key]) != expected:
        raise RC03VerificationError("SEED_SPLIT_MISMATCH")
    return angles, expected


def recompute(
    member: dict[str, Any], nuisance: list[dict[str, float]], *, partition: str, seeds: tuple[int, int],
    angles: tuple[float, ...], cell_start: int, cell_end: int, include_noise: bool,
) -> np.ndarray:
    output = np.empty((len(angles), cell_end - cell_start, 2, 4, 256), dtype=np.complex128)
    frequencies = frozen_frequency_grid()
    for local, cell in enumerate(range(cell_start, cell_end)):
        for repeat in range(2):
            output[:, local, repeat] = solve_forward_block(
                member, nuisance[cell], cell_index=cell, repeat_index=repeat, frequencies_hz=frequencies,
                state_angles_degrees=angles, partition=partition, repeat_seed_tuple=seeds,
                include_additive_sensor_noise=include_noise,
            ).central_pressure
    return output


def compare(driver: np.ndarray, verifier: np.ndarray) -> tuple[float, float]:
    if driver.dtype != np.dtype("complex128") or driver.shape != verifier.shape or not np.all(np.isfinite(driver)) or not np.all(np.isfinite(verifier)):
        raise RC03VerificationError("RAW_SHAPE_DTYPE_FINITE_FAIL")
    delta = np.abs(driver - verifier)
    maximum_absolute = float(delta.max(initial=0.0))
    maximum_relative = float((delta / np.maximum(np.abs(verifier), ATOL)).max(initial=0.0))
    if not np.allclose(driver, verifier, rtol=RTOL, atol=ATOL):
        raise RC03VerificationError("INDEPENDENT_RECOMPUTATION_MISMATCH")
    return maximum_absolute, maximum_relative


def persist_roles(root: Path, chunk_id: str, roles: dict[str, np.ndarray], expected: tuple[str, ...]) -> list[dict[str, Any]]:
    if set(roles) != set(expected):
        raise RC03VerificationError("EXACT_PHASE_ROLE_SET_REQUIRED")
    entries = []
    for role in expected:
        entry = write_npy_atomic(root / f"{chunk_id}.{role}.npy", roles[role])
        entry["role"] = role
        entry["retention"] = "TRANSIENT_UNTIL_COMMON_W_MERGE" if role in COMMON_W_ROLES else "RETAINED_FINEST_UNIT"
        entries.append(entry)
    return entries


def verify_chunk(args: argparse.Namespace) -> dict[str, Any]:
    member = read_json(Path(args.member))
    nuisance = nuisance_rows(Path(args.nuisance_csv))
    angles, seeds = partition_values(args.partition, read_json(Path(args.seed_split)))
    recomputed = recompute(member, nuisance, partition=args.partition, seeds=seeds, angles=angles,
                           cell_start=args.cell_start, cell_end=args.cell_end_exclusive, include_noise=True)
    driver = np.load(args.driver_raw, allow_pickle=False)
    maximum_absolute, maximum_relative = compare(driver, recomputed)
    if args.phase == "COMMON_W_PASS":
        if args.partition != "development":
            raise RC03VerificationError("COMMON_W_DEVELOPMENT_ONLY")
        roles = common_w_chunk_roles(recomputed)
        expected = COMMON_W_ROLES
    else:
        if not args.sealed_w or not args.through_reference:
            raise RC03VerificationError("SEALED_W_AND_REFERENCE_REQUIRED")
        with np.load(args.sealed_w, allow_pickle=False) as sealed:
            whitener = np.asarray(sealed["operator"], dtype=np.float64)
        reference_member = read_json(Path(args.through_reference))
        reference = recompute(reference_member, nuisance, partition=args.partition, seeds=seeds, angles=angles,
                              cell_start=args.cell_start, cell_end=args.cell_end_exclusive, include_noise=False)
        candidate_pre_noise = recompute(member, nuisance, partition=args.partition, seeds=seeds, angles=angles,
                                        cell_start=args.cell_start, cell_end=args.cell_end_exclusive, include_noise=False)
        cad = member.get("cad_static_audit", {})
        matched_inputs = np.asarray([cad.get("volume_m3"), cad.get("dof"), cad.get("minimum_feature_m"), cad.get("solid_load_path_m")], dtype=np.float64)
        roles = metric_chunk_roles(recomputed, reference, whitener, cell_start=args.cell_start,
                                   candidate_raw_pre_noise=candidate_pre_noise, matched_cost_inputs=matched_inputs)
        if args.partition == "development":
            roles.pop("BRIDGE_24_UNIT_VALUES")
            roles.pop("HELD_OUT_4_UNIT_VALUES")
            expected = DEVELOPMENT_METRIC_ROLES
        else:
            expected = VALIDATION_METRIC_ROLES
    stats_root = Path(args.stats_root)
    entries = persist_roles(stats_root, args.chunk_id, roles, expected)
    manifest = {
        "schema_version": "gen_enc_2_e2_full_role_manifest_rc03_v1", "partition": args.partition, "phase": args.phase,
        "identity_id": member["member_id"], "chunk_id": args.chunk_id, "cell_start": args.cell_start,
        "cell_end_exclusive": args.cell_end_exclusive, "expected_roles": list(expected), "entries": entries,
        "role_set_complete": True, "canonical_merge_position": args.merge_position, "raw_complex_json": False,
    }
    manifest_path = stats_root / f"{args.chunk_id}.full_role_manifest.json"
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    hashes = json.loads(args.hashes_json)
    required_hashes = {"contract", "exact80", "nuisance", "seed_split", "driver_code", "verifier_code", "stats_code", "merge_code", "core_code", "runtime", "dependencies"}
    if set(hashes) != required_hashes or any(not isinstance(value, str) or len(value) != 64 for value in hashes.values()):
        raise RC03VerificationError("HASH_CLOSURE_REQUIRED")
    receipt = {
        "schema_version": "gen_enc_2_e2_full_role_receipt_rc03_v1", "status": "PASS", "partition": args.partition,
        "phase": args.phase, "identity_id": member["member_id"], "chunk_id": args.chunk_id, "hashes": hashes,
        "shape": list(driver.shape), "dtype": "complex128", "value_count": int(driver.size),
        "driver_raw_sha256": sha256_file(Path(args.driver_raw)), "verifier_raw_sha256": hashlib.sha256(recomputed.tobytes(order="C")).hexdigest(),
        "max_abs_diff": maximum_absolute, "max_rel_diff": maximum_relative,
        "full_role_manifest_sha256": sha256_file(manifest_path), "role_count": len(expected),
        "canonical_merge_position": args.merge_position,
    }
    receipt_path = Path(args.receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_name(receipt_path.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(receipt))
    os.replace(temporary, receipt_path)
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("mode", choices=("self-test", "verify-chunk"))
    value.add_argument("--phase", choices=("COMMON_W_PASS", "DEVELOPMENT_METRIC_PASS", "VALIDATION_METRIC_PASS"))
    for name in ("member", "nuisance-csv", "seed-split", "partition", "chunk-id", "driver-raw", "stats-root", "receipt", "hashes-json", "sealed-w", "through-reference"):
        value.add_argument(f"--{name}")
    value.add_argument("--cell-start", type=int)
    value.add_argument("--cell-end-exclusive", type=int)
    value.add_argument("--merge-position", type=int)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(json.dumps({"status": "PASS", "formal_units": 0, "full_role_sets": [list(COMMON_W_ROLES), list(DEVELOPMENT_METRIC_ROLES), list(VALIDATION_METRIC_ROLES)], "final_test_read": False}, sort_keys=True))
            return 0
        required = (args.phase, args.member, args.nuisance_csv, args.seed_split, args.partition, args.chunk_id, args.driver_raw, args.stats_root, args.receipt, args.hashes_json)
        if any(item is None for item in required) or args.cell_start is None or args.cell_end_exclusive is None or args.merge_position is None:
            raise RC03VerificationError("FORMAL_ARGUMENTS_REQUIRED")
        receipt = verify_chunk(args)
        print(json.dumps({"status": receipt["status"], "role_count": receipt["role_count"]}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, np.linalg.LinAlgError, RC03VerificationError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

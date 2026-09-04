"""Input-recomputing independent verifier for frozen GEN-ENC-2 E2 chunks.

The formal entrypoint receives frozen scientific inputs and a driver raw path.
It recomputes the chunk itself through the shared hash-frozen core. It never
imports the formal driver or accepts a caller-produced verifier array.
"""

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

RTOL = 1e-10
ATOL = 1e-12


class VerificationError(RuntimeError):
    """Fail-closed independent-verification error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError(f"JSON_OBJECT_REQUIRED:{path.as_posix()}")
    return value


def _nuisance_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise VerificationError("NUISANCE_METADATA_HEADER_REQUIRED")
        for row in csv.DictReader(stream):
            rows.append({
                "snr_db": float(row["snr_db"]), "common_gain_db": float(row["common_gain_db"]),
                "sensor_independent_gain_db": float(row["sensor_independent_gain_db"]),
                "common_frequency_axis_shift_relative": float(row["common_frequency_axis_shift_relative"]),
                "independent_manufacturing_percent": float(row["independent_manufacturing_percent"]),
                "batch_correlated_manufacturing_percent": float(row["batch_correlated_manufacturing_percent"]),
                "angle_offset_degrees": float(row["angle_offset_degrees"]),
            })
    if len(rows) != 3675:
        raise VerificationError("EXACT_3675_NUISANCE_ROWS_REQUIRED")
    return rows


def partition_angles(partition: str) -> tuple[float, ...]:
    if partition == "development":
        return (0.0, 90.0, 180.0, 270.0)
    if partition == "single_use_validation":
        return tuple(float(value) for value in range(0, 360, 15))
    raise VerificationError("UNKNOWN_PARTITION")


def partition_seeds(seed_split: dict[str, Any], partition: str) -> tuple[int, int]:
    key = "development_training" if partition == "development" else "single_use_validation"
    expected = (2026091001, 2026091002) if partition == "development" else (2026092001, 2026092002)
    observed = tuple(seed_split.get("nuisance_partition_seeds", {}).get(key, ()))
    if observed != expected:
        raise VerificationError("PARTITION_SEED_SPLIT_MISMATCH")
    return expected


def recompute_chunk_from_frozen_inputs(
    *, member_path: Path, nuisance_csv: Path, seed_split_path: Path,
    partition: str, cell_start: int, cell_end_exclusive: int,
) -> np.ndarray:
    """Independently load frozen inputs and recompute one canonical chunk."""

    if not 0 <= cell_start < cell_end_exclusive <= 3675 or cell_end_exclusive - cell_start > 25:
        raise VerificationError("INVALID_CELL_CHUNK")
    member = _json(member_path)
    nuisance = _nuisance_rows(nuisance_csv)
    seeds = partition_seeds(_json(seed_split_path), partition)
    angles = partition_angles(partition)
    from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block

    frequencies = frozen_frequency_grid()
    output = np.empty((len(angles), cell_end_exclusive - cell_start, 2, 4, 256), dtype=np.complex128)
    for local_cell, cell_index in enumerate(range(cell_start, cell_end_exclusive)):
        for repeat_index in range(2):
            result = solve_forward_block(
                member, nuisance[cell_index], cell_index=cell_index, repeat_index=repeat_index,
                frequencies_hz=frequencies, state_angles_degrees=angles, partition=partition,
                repeat_seed_tuple=seeds,
            )
            output[:, local_cell, repeat_index, :, :] = result.central_pressure
    if not np.all(np.isfinite(output)):
        raise VerificationError("RECOMPUTED_CHUNK_NONFINITE")
    return output


def compare_driver_raw_to_recomputed(driver_raw: np.ndarray, recomputed: np.ndarray) -> dict[str, float]:
    driver = np.asarray(driver_raw)
    verifier = np.asarray(recomputed)
    if driver.shape != verifier.shape or driver.dtype != np.dtype("complex128") or verifier.dtype != np.dtype("complex128"):
        raise VerificationError("SHAPE_OR_COMPLEX128_DTYPE_MISMATCH")
    if not np.all(np.isfinite(driver)) or not np.all(np.isfinite(verifier)):
        raise VerificationError("NONFINITE_RAW_CHUNK")
    delta = np.abs(driver - verifier)
    denominator = np.maximum(np.abs(verifier), ATOL)
    maximum_absolute = float(delta.max(initial=0.0))
    maximum_relative = float((delta / denominator).max(initial=0.0))
    if not np.allclose(driver, verifier, rtol=RTOL, atol=ATOL):
        raise VerificationError("INDEPENDENT_RAW_RECOMPUTATION_MISMATCH")
    return {"max_abs_diff": maximum_absolute, "max_rel_diff": maximum_relative}


def write_compact_stats(
    recomputed: np.ndarray, output_root: Path, chunk_id: str, *, partition: str,
    identity_id: str, cell_start: int, cell_end_exclusive: int,
) -> dict[str, Any]:
    """Persist compact NPY raw-derived statistics, never per-complex JSON."""

    output_root.mkdir(parents=True, exist_ok=True)
    power = np.sum(np.abs(recomputed) ** 2, axis=3, dtype=np.float64)
    shared = np.mean(recomputed, axis=0, keepdims=True)
    differential_energy = np.sum(np.abs(recomputed - shared) ** 2, axis=(3, 4), dtype=np.float64)
    entries: list[dict[str, Any]] = []
    for role, array in (
        ("port_power_by_frequency", np.asarray(power, dtype=np.float64)),
        ("differential_energy", np.asarray(differential_energy, dtype=np.float64)),
    ):
        final = output_root / f"{chunk_id}.{role}.npy"
        temporary = final.with_name(final.name + ".tmp")
        with temporary.open("wb") as stream:
            np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, final)
        entries.append({"role": role, "path": final.as_posix(), "sha256": sha256_file(final), "shape": list(array.shape), "dtype": "float64", "order": "C", "format": "NPY_1_0"})
    manifest = {
        "schema_version": "gen_enc_2_e2_compact_stats_manifest_freeze02_v1",
        "partition": partition, "stage": "METRIC_PASS", "identity_id": identity_id,
        "chunk_id": chunk_id, "cell_start": cell_start, "cell_end_exclusive": cell_end_exclusive,
        "format": "NPY_1_0", "entries": entries,
        "merge_algebra": "SEQUENTIAL_BINARY64_SUM_FOR_MATCHED_SHAPES_AND_C_AXIS_CONCATENATION_FOR_CANONICAL_RESAMPLING_ROWS",
        "canonical_merge_key": "PARTITION_STAGE_FAMILY_ORDINAL_MEMBER_ORDINAL_CHUNK_INDEX_ARRAY_ROLE",
        "raw_complex_json_records": False,
    }
    path = output_root / f"{chunk_id}.stats_manifest.json"
    path.write_bytes(canonical_json_bytes(manifest))
    return {"manifest_path": path.as_posix(), "sha256": sha256_file(path)}


def verify_formal_chunk(
    *, member_path: Path, nuisance_csv: Path, seed_split_path: Path, partition: str,
    cell_start: int, cell_end_exclusive: int, chunk_id: str, driver_raw_path: Path,
    stats_root: Path, receipt_path: Path, hashes: dict[str, str], merge_position: int,
) -> dict[str, Any]:
    recomputed = recompute_chunk_from_frozen_inputs(
        member_path=member_path, nuisance_csv=nuisance_csv, seed_split_path=seed_split_path,
        partition=partition, cell_start=cell_start, cell_end_exclusive=cell_end_exclusive,
    )
    driver = np.load(driver_raw_path, allow_pickle=False)
    differences = compare_driver_raw_to_recomputed(driver, recomputed)
    identity_id = _json(member_path)["member_id"]
    stats = write_compact_stats(
        recomputed, stats_root, chunk_id, partition=partition, identity_id=identity_id,
        cell_start=cell_start, cell_end_exclusive=cell_end_exclusive,
    )
    required_hashes = ("contract", "exact80", "nuisance", "seed_split", "driver_code", "verifier_code", "core_code", "runtime", "dependencies")
    if set(hashes) != set(required_hashes) or any(not isinstance(hashes[key], str) or len(hashes[key]) != 64 for key in required_hashes):
        raise VerificationError("RECEIPT_HASH_SET_MISMATCH")
    receipt = {
        "schema_version": "gen_enc_2_e2_chunk_pass_receipt_freeze02_v1", "status": "PASS",
        "partition": partition, "identity_id": identity_id, "chunk_id": chunk_id,
        "cell_start": cell_start, "cell_end_exclusive": cell_end_exclusive,
        "hashes": hashes, "value_count": int(driver.size), "shape": list(driver.shape), "dtype": "complex128",
        "driver_raw_sha256": sha256_file(driver_raw_path),
        "verifier_raw_sha256": hashlib.sha256(recomputed.tobytes(order="C")).hexdigest(),
        "max_abs_diff": differences["max_abs_diff"], "max_rel_diff": differences["max_rel_diff"],
        "sufficient_stat_manifest_sha256": stats["sha256"], "merge_position": merge_position,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_name(receipt_path.name + ".tmp")
    temporary.write_bytes(canonical_json_bytes(receipt))
    os.replace(temporary, receipt_path)
    return receipt


def self_test() -> dict[str, Any]:
    exact = np.asarray([1.0 + 2.0j], dtype=np.complex128)
    compare_driver_raw_to_recomputed(exact, exact.copy())
    detected = False
    try:
        compare_driver_raw_to_recomputed(exact + np.asarray([1e-3 + 0.0j]), exact)
    except VerificationError:
        detected = True
    if not detected:
        raise AssertionError("PERTURBATION_NOT_DETECTED")
    return {"status": "PASS", "input_recompute_api": True, "perturbation_detected": True, "formal_response_reads": 0, "final_test_read": False}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-test", "verify-chunk"))
    for name in ("member", "nuisance-csv", "seed-split", "chunk-id", "driver-raw", "stats-root", "receipt", "hashes-json"):
        parser.add_argument(f"--{name}")
    parser.add_argument("--partition", choices=("development", "single_use_validation"))
    parser.add_argument("--cell-start", type=int)
    parser.add_argument("--cell-end-exclusive", type=int)
    parser.add_argument("--merge-position", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(json.dumps(self_test(), sort_keys=True, separators=(",", ":")))
            return 0
        required = (args.member, args.nuisance_csv, args.seed_split, args.partition, args.chunk_id, args.driver_raw, args.stats_root, args.receipt, args.hashes_json)
        if any(value is None for value in required) or args.cell_start is None or args.cell_end_exclusive is None or args.merge_position is None:
            raise VerificationError("VERIFY_CHUNK_ARGUMENTS_REQUIRED")
        receipt = verify_formal_chunk(
            member_path=Path(args.member), nuisance_csv=Path(args.nuisance_csv), seed_split_path=Path(args.seed_split), partition=args.partition,
            cell_start=args.cell_start, cell_end_exclusive=args.cell_end_exclusive, chunk_id=args.chunk_id,
            driver_raw_path=Path(args.driver_raw), stats_root=Path(args.stats_root), receipt_path=Path(args.receipt),
            hashes=json.loads(args.hashes_json), merge_position=args.merge_position,
        )
        print(json.dumps({"status": receipt["status"], "receipt": args.receipt}, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, ValueError, VerificationError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

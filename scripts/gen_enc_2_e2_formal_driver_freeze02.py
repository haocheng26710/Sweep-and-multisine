"""Authorization-gated formal GEN-ENC-2 E2 streaming driver.

The first formal operation is the authorization pre-read gate. Without a valid
external authorization, no scientific input, output root, or response path is
read or created. This file creates no authorization controls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

import numpy as np
import psutil


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MANAGED_CAP_BYTES = 48 * 1024**3
START_FREE_BYTES = 80 * 1024**3
RESERVE_FLOOR_BYTES = 32 * 1024**3
CPU_STOP_SECONDS = 20.0 * 3600.0
WALL_STOP_SECONDS = 10.0 * 3600.0
MEMORY_STOP_BYTES = 8 * 1024**3
CELLS_PER_CHUNK = 25
CHUNKS_PER_IDENTITY_PARTITION = 147


class FormalDriverError(RuntimeError):
    """Fail-closed formal-driver error."""


def sha256_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def authorization_pre_read_gate(path: Path, mode: str) -> dict[str, Any]:
    """Read only the external authorization and fail before all science input."""

    if not path.is_file():
        raise FormalDriverError("EXECUTION_AUTHORIZATION_ABSENT_PRE_READ_STOP")
    value = json.loads(path.read_text(encoding="utf-8"))
    expected_stage = "E2_D" if mode == "development" else "E2_V_SINGLE_USE"
    if not isinstance(value, dict) or value.get("status") != "AUTHORIZED" or value.get("stage") != expected_stage:
        raise FormalDriverError("EXECUTION_AUTHORIZATION_INVALID_PRE_READ_STOP")
    if value.get("consumed") is not False or value.get("final_test_read") is not False:
        raise FormalDriverError("EXECUTION_AUTHORIZATION_CONSUMED_OR_FINAL_TEST_UNSEALED")
    return value


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FormalDriverError(f"JSON_OBJECT_REQUIRED:{path.as_posix()}")
    return value


def _nuisance_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise FormalDriverError("NUISANCE_METADATA_HEADER_REQUIRED")
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
        raise FormalDriverError("EXACT_3675_NUISANCE_ROWS_REQUIRED")
    return rows


def partition_spec(mode: str, seed_split: dict[str, Any]) -> tuple[str, tuple[float, ...], tuple[int, int]]:
    if mode == "development":
        partition, angles, key, expected = "development", (0.0, 90.0, 180.0, 270.0), "development_training", (2026091001, 2026091002)
    else:
        partition, angles, key, expected = "single_use_validation", tuple(float(value) for value in range(0, 360, 15)), "single_use_validation", (2026092001, 2026092002)
    if tuple(seed_split.get("nuisance_partition_seeds", {}).get(key, ())) != expected:
        raise FormalDriverError("PARTITION_SEED_SPLIT_MISMATCH")
    return partition, angles, expected


def canonical_chunk_ids() -> tuple[str, ...]:
    return tuple(f"chunk_{index:03d}" for index in range(CHUNKS_PER_IDENTITY_PARTITION))


def audit_chunks(partition: str, identity_id: str) -> frozenset[str]:
    ranked = sorted(canonical_chunk_ids(), key=lambda chunk: hashlib.sha256(f"GEN_ENC_E2_RAW_AUDIT_V1|{partition}|{identity_id}|{chunk}".encode()).hexdigest())
    return frozenset(ranked[:2])


def write_npy_atomic(path: Path, array: np.ndarray) -> None:
    if array.dtype != np.dtype("complex128") or not np.all(np.isfinite(array)):
        raise FormalDriverError("FINITE_COMPLEX128_REQUIRED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def managed_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def resource_storage_gate(root: Path, *, wall_start: float, cpu_start: float) -> dict[str, float | int]:
    process = psutil.Process()
    wall = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    peak = int(process.memory_info().rss)
    managed = managed_bytes(root)
    free = int(shutil.disk_usage(root).free)
    if cpu >= CPU_STOP_SECONDS or wall >= WALL_STOP_SECONDS or peak >= MEMORY_STOP_BYTES:
        raise FormalDriverError("RESOURCE_BLOCKED_COMPUTE_ENVELOPE")
    if managed > MANAGED_CAP_BYTES or free < RESERVE_FLOOR_BYTES:
        raise FormalDriverError("RESOURCE_BLOCKED_STORAGE_ENVELOPE")
    return {"wall_seconds": wall, "cpu_seconds": cpu, "aggregate_memory_bytes": peak, "managed_bytes": managed, "free_bytes": free}


def generate_driver_chunk(member: dict[str, Any], nuisance: list[dict[str, float]], *, partition: str, angles: tuple[float, ...], seeds: tuple[int, int], cell_start: int, cell_end: int) -> np.ndarray:
    from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block
    frequencies = frozen_frequency_grid()
    raw = np.empty((len(angles), cell_end - cell_start, 2, 4, 256), dtype=np.complex128)
    for local_cell, cell_index in enumerate(range(cell_start, cell_end)):
        for repeat_index in range(2):
            result = solve_forward_block(member, nuisance[cell_index], cell_index=cell_index, repeat_index=repeat_index, frequencies_hz=frequencies, state_angles_degrees=angles, partition=partition, repeat_seed_tuple=seeds)
            raw[:, local_cell, repeat_index, :, :] = result.central_pressure
    return raw


def process_verified_chunk(
    *, raw_path: Path, receipt_path: Path, stats_manifest_path: Path, audit_path: Path,
    quarantine_path: Path, checkpoint_path: Path, verifier_command: list[str], is_audit: bool,
    merge_position: int, resource_root: Path, wall_start: float, cpu_start: float,
) -> None:
    """Freeze the exact RC04 lifecycle and failure behavior."""

    completed = subprocess.run(verifier_command, cwd=REPO, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        quarantine_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(raw_path, quarantine_path)
        write_json_atomic(checkpoint_path, {"status": "PARTITION_STOP", "failure_chunk": quarantine_path.name, "merge_position": merge_position, "same_run_retry": False, "later_merge": False})
        raise FormalDriverError("INDEPENDENT_VERIFY_FAIL_PARTITION_STOP")
    if not receipt_path.is_file() or not stats_manifest_path.is_file():
        raise FormalDriverError("PASS_RECEIPT_OR_STATS_NOT_DURABLE")
    receipt = _json(receipt_path)
    stats_manifest = _json(stats_manifest_path)
    if receipt.get("status") != "PASS" or receipt.get("sufficient_stat_manifest_sha256") != sha256_file(stats_manifest_path):
        raise FormalDriverError("PASS_RECEIPT_STATS_HASH_MISMATCH")
    for entry in stats_manifest.get("entries", []):
        stat_path = Path(entry.get("path", ""))
        if not stat_path.is_file() or sha256_file(stat_path) != entry.get("sha256"):
            raise FormalDriverError("COMPACT_STAT_NOT_DURABLE_OR_HASH_MISMATCH")
    checkpoint = {
        "status": "PASS_VERIFIED_CHECKPOINTED", "merge_position": merge_position,
        "receipt_sha256": sha256_file(receipt_path), "stats_manifest_sha256": sha256_file(stats_manifest_path),
        "resource_storage": resource_storage_gate(resource_root, wall_start=wall_start, cpu_start=cpu_start),
    }
    write_json_atomic(checkpoint_path, checkpoint)
    if is_audit:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(raw_path, audit_path)
    else:
        raw_path.unlink()


def run_formal(args: argparse.Namespace) -> int:
    # RC01: this is deliberately the first formal call.
    authorization = authorization_pre_read_gate(Path(args.authorization), args.mode)
    binding_paths = {
        "contract_sha256": Path(args.contract),
        "exact80_sha256": Path(args.exact80),
        "nuisance_sha256": Path(args.nuisance_csv),
        "seed_split_sha256": Path(args.seed_split),
        "source_manifest_sha256": Path(args.source_manifest),
        "runtime_manifest_sha256": Path(args.runtime_manifest),
        "driver_sha256": Path(__file__),
        "verifier_sha256": Path(args.verifier),
    }
    bindings = authorization.get("bindings")
    if not isinstance(bindings, dict) or any(bindings.get(key) != sha256_file(path) for key, path in binding_paths.items()):
        raise FormalDriverError("EXECUTION_AUTHORIZATION_BINDING_MISMATCH")
    expected_root = Path(str(authorization.get("output_root", "")))
    if expected_root.as_posix() != Path(args.output_root).as_posix():
        raise FormalDriverError("EXECUTION_AUTHORIZATION_OUTPUT_ROOT_MISMATCH")
    contract = _json(Path(args.contract))
    exact80 = _json(Path(args.exact80))
    seed_split = _json(Path(args.seed_split))
    partition, angles, seeds = partition_spec(args.mode, seed_split)
    if args.mode == "single-use-validation":
        seal = _json(Path(args.development_seal))
        if seal.get("status") != "E2_D_SEALED_INDEPENDENT_PASS" or seal.get("validation_opened") is not False:
            raise FormalDriverError("DEVELOPMENT_SEAL_REQUIRED_BEFORE_VALIDATION")
    output_root = Path(args.output_root)
    if output_root.exists() and not args.resume:
        raise FormalDriverError("OUTPUT_ROOT_EXISTS_WITHOUT_VALID_RESUME")
    output_root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(output_root).free
    if free < START_FREE_BYTES:
        raise FormalDriverError("RESOURCE_BLOCKED_START_FREE_BELOW_80_GIB")
    checkpoint_path = output_root / args.checkpoint
    if checkpoint_path.exists():
        checkpoint = _json(checkpoint_path)
        if checkpoint.get("status") == "PARTITION_STOP":
            raise FormalDriverError("NO_SAME_RUN_RETRY_AFTER_FAILURE")
    nuisance = _nuisance_rows(Path(args.nuisance_csv))
    hashes = {
        "contract": sha256_file(Path(args.contract)), "exact80": sha256_file(Path(args.exact80)),
        "nuisance": sha256_file(Path(args.nuisance_csv)), "seed_split": sha256_file(Path(args.seed_split)),
        "driver_code": sha256_file(Path(__file__)),
        "verifier_code": sha256_file(Path(args.verifier)),
        "core_code": sha256_file(REPO / "src/acoustic_encoder/gen_enc/forward_acoustic_network.py"),
        "runtime": sha256_file(Path(args.runtime_manifest)), "dependencies": sha256_file(Path(args.source_manifest)),
    }
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    merge_position = 0
    for member_entry in exact80["members"]:
        member_path = Path(member_entry["identity_path"])
        member = _json(member_path)
        retained = audit_chunks(partition, member["member_id"])
        for chunk_index, chunk_id in enumerate(canonical_chunk_ids()):
            cell_start = chunk_index * CELLS_PER_CHUNK
            cell_end = min(3675, cell_start + CELLS_PER_CHUNK)
            raw_path = output_root / "temp" / member["member_id"] / f"{chunk_id}.npy"
            receipt_path = output_root / "receipts" / member["member_id"] / f"{chunk_id}.json"
            stats_root = output_root / "stats" / member["member_id"]
            stats_manifest = stats_root / f"{chunk_id}.stats_manifest.json"
            checkpoint_path = output_root / args.checkpoint
            raw = generate_driver_chunk(member, nuisance, partition=partition, angles=angles, seeds=seeds, cell_start=cell_start, cell_end=cell_end)
            write_npy_atomic(raw_path, raw)
            verifier_command = [
                sys.executable, "-B", args.verifier, "verify-chunk", "--member", member_path.as_posix(),
                "--nuisance-csv", args.nuisance_csv, "--seed-split", args.seed_split, "--partition", partition,
                "--cell-start", str(cell_start), "--cell-end-exclusive", str(cell_end), "--chunk-id", chunk_id,
                "--driver-raw", raw_path.as_posix(), "--stats-root", stats_root.as_posix(), "--receipt", receipt_path.as_posix(),
                "--hashes-json", json.dumps(hashes, separators=(",", ":")), "--merge-position", str(merge_position),
            ]
            process_verified_chunk(
                raw_path=raw_path, receipt_path=receipt_path, stats_manifest_path=stats_manifest,
                audit_path=output_root / "raw_audit" / member["member_id"] / f"{chunk_id}.npy",
                quarantine_path=output_root / "quarantine" / member["member_id"] / f"{chunk_id}.npy",
                checkpoint_path=checkpoint_path, verifier_command=verifier_command, is_audit=chunk_id in retained,
                merge_position=merge_position, resource_root=output_root, wall_start=wall_start, cpu_start=cpu_start,
            )
            merge_position += 1
    terminal = {"status": "E2_D_SEALED_INDEPENDENT_PASS" if partition == "development" else "E2_V_SINGLE_USE_TERMINAL", "partition": partition, "complete_chunks": merge_position, "validation_opened": partition != "development", "contract_sha256": sha256_file(Path(args.contract)), "final_test_read": False}
    write_json_atomic(output_root / "partition_terminal.json", terminal)
    return 0


def self_test() -> dict[str, Any]:
    chunks = canonical_chunk_ids()
    if len(chunks) != 147 or len(audit_chunks("development", "HAND_01")) != 2:
        raise AssertionError("CHUNK_OR_AUDIT_RULE")
    return {"status": "PASS", "formal_units": 0, "formal_response_reads": 0, "formal_response_writes": 0, "final_test_read": False}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-test", "development", "single-use-validation"))
    for name in ("authorization", "contract", "exact80", "nuisance-csv", "seed-split", "source-manifest", "runtime-manifest", "output-root", "checkpoint", "verifier"):
        parser.add_argument(f"--{name}")
    parser.add_argument("--development-seal")
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(json.dumps(self_test(), sort_keys=True, separators=(",", ":")))
            return 0
        required = (args.authorization, args.contract, args.exact80, args.nuisance_csv, args.seed_split, args.source_manifest, args.runtime_manifest, args.output_root, args.checkpoint, args.verifier)
        if any(value is None for value in required) or (args.mode == "single-use-validation" and args.development_seal is None):
            raise FormalDriverError("FORMAL_ARGUMENTS_REQUIRED")
        return run_formal(args)
    except (OSError, ValueError, FormalDriverError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

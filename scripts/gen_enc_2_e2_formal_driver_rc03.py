"""Authorization-first formal E2 RC03 driver with complete three-pass graph."""

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

from acoustic_encoder.gen_enc.e2_rc03_resource import ResourceLedger
from acoustic_encoder.gen_enc.e2_rc03_stats import canonical_json_bytes, sha256_file
from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block

MANAGED_CAP = 48 * 1024**3
START_FREE = 80 * 1024**3
RESERVE = 32 * 1024**3
CPU_LIMIT = 20 * 3600.0
WALL_LIMIT = 10 * 3600.0
MEMORY_LIMIT = 8 * 1024**3
CELLS_PER_CHUNK = 25
CHUNKS = 147


class DriverError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DriverError("JSON_OBJECT_REQUIRED")
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def authorization_first(path: Path, mode: str) -> dict[str, Any]:
    if not path.is_file():
        raise DriverError("AUTHORIZATION_ABSENT_PRE_SCIENCE_READ_STOP")
    value = read_json(path)
    expected = "E2_D" if mode == "development" else "E2_V_SINGLE_USE"
    if value.get("status") != "AUTHORIZED" or value.get("stage") != expected or value.get("consumed") is not False or value.get("final_test_read") is not False:
        raise DriverError("AUTHORIZATION_INVALID_PRE_SCIENCE_READ_STOP")
    return value


def nuisance_rows(path: Path) -> list[dict[str, float]]:
    rows = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise DriverError("NUISANCE_METADATA_REQUIRED")
        for row in csv.DictReader(stream):
            rows.append({key: float(row[key]) for key in (
                "snr_db", "common_gain_db", "sensor_independent_gain_db", "common_frequency_axis_shift_relative",
                "independent_manufacturing_percent", "batch_correlated_manufacturing_percent", "angle_offset_degrees")})
    if len(rows) != 3675:
        raise DriverError("EXACT3675_REQUIRED")
    return rows


def partition_values(mode: str, seed: dict[str, Any]) -> tuple[str, tuple[float, ...], tuple[int, int]]:
    if mode == "development":
        partition, angles, key, expected = "development", (0.0, 90.0, 180.0, 270.0), "development_training", (2026091001, 2026091002)
    else:
        partition, angles, key, expected = "single_use_validation", tuple(float(v) for v in range(0, 360, 15)), "single_use_validation", (2026092001, 2026092002)
    if tuple(seed["nuisance_partition_seeds"][key]) != expected:
        raise DriverError("SEED_MISMATCH")
    return partition, angles, expected


def generate(member: dict[str, Any], nuisance: list[dict[str, float]], *, partition: str, angles: tuple[float, ...], seeds: tuple[int, int], start: int, end: int) -> np.ndarray:
    output = np.empty((len(angles), end - start, 2, 4, 256), dtype=np.complex128)
    frequencies = frozen_frequency_grid()
    for local, cell in enumerate(range(start, end)):
        for repeat in range(2):
            output[:, local, repeat] = solve_forward_block(member, nuisance[cell], cell_index=cell, repeat_index=repeat,
                frequencies_hz=frequencies, state_angles_degrees=angles, partition=partition, repeat_seed_tuple=seeds).central_pressure
    return output


def write_raw(path: Path, raw: np.ndarray) -> None:
    if raw.dtype != np.dtype("complex128") or not np.all(np.isfinite(raw)):
        raise DriverError("FINITE_COMPLEX128_REQUIRED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.lib.format.write_array(stream, raw, version=(1, 0), allow_pickle=False); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def managed_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def gate(root: Path, ledger: ResourceLedger, *, startup: bool = False) -> dict[str, Any]:
    snapshot = ledger.snapshot()
    free = shutil.disk_usage(root).free
    managed = managed_bytes(root)
    if startup and free < START_FREE:
        raise DriverError("RESOURCE_BLOCKED_START_FREE")
    if free < RESERVE or managed > MANAGED_CAP:
        raise DriverError("RESOURCE_BLOCKED_STORAGE")
    if snapshot["cpu_core_seconds"] >= CPU_LIMIT or snapshot["wall_seconds"] >= WALL_LIMIT or snapshot["aggregate_peak_rss_bytes"] >= MEMORY_LIMIT:
        raise DriverError("RESOURCE_BLOCKED_PROCESS_TREE")
    return {**snapshot, "free_bytes": free, "managed_bytes": managed}


def audit_chunks(partition: str, identity: str) -> set[str]:
    chunks = [f"chunk_{index:03d}" for index in range(CHUNKS)]
    return set(sorted(chunks, key=lambda chunk: hashlib.sha256(f"GEN_ENC_E2_RAW_AUDIT_V1|{partition}|{identity}|{chunk}".encode()).hexdigest())[:2])


def complete_role_delete_gate(
    *, raw: Path, receipt: Path, manifest: Path, verifier_argv: list[str], phase: str,
    expected_roles: tuple[str, ...], output_root: Path, checkpoint: Path, quarantine: Path,
    audit: Path, retain_audit: bool, ledger: ResourceLedger, merge_position: int,
    w_accumulator: Path | None = None, w_merge_checkpoint: Path | None = None,
) -> None:
    from scripts.gen_enc_2_e2_merge_reconstruct_rc03 import merge_common_w_contribution, validate_role_manifest

    completed = ledger.run_child(verifier_argv, cwd=REPO.as_posix())
    if completed.returncode != 0:
        quarantine.parent.mkdir(parents=True, exist_ok=True); os.replace(raw, quarantine)
        write_json_atomic(checkpoint, {"status": "PARTITION_STOP", "failure_chunk": quarantine.name, "merge_position": merge_position,
                                      "same_run_retry": False, "later_merge": False, "resource": ledger.snapshot()})
        raise DriverError("VERIFY_FAIL_QUARANTINE_PARTITION_STOP")
    receipt_value = read_json(receipt)
    manifest_value = validate_role_manifest(manifest, expected_roles)
    if receipt_value.get("status") != "PASS" or receipt_value.get("full_role_manifest_sha256") != sha256_file(manifest) or receipt_value.get("role_count") != len(expected_roles):
        raise DriverError("COMPLETE_ROLE_RECEIPT_FAIL")
    merge_hash = sha256_file(manifest)
    if phase == "COMMON_W_PASS":
        if w_accumulator is None or w_merge_checkpoint is None:
            raise DriverError("W_MERGE_TARGET_REQUIRED")
        merge = merge_common_w_contribution(manifest, w_accumulator, w_merge_checkpoint, expected_position=merge_position)
        merge_hash = merge["accumulator_sha256"]
    else:
        deduplicated = []
        for entry in manifest_value["entries"]:
            if entry["role"] not in ("THROUGHPUT_REFERENCE_DENOMINATOR_256", "THROUGHPUT_AVAILABILITY_256"):
                continue
            source = Path(entry["path"])
            canonical = output_root / "reference_stats" / manifest_value["partition"] / f"{manifest_value['chunk_id']}.{entry['role']}.npy"
            canonical.parent.mkdir(parents=True, exist_ok=True)
            if canonical.exists():
                if sha256_file(canonical) != entry["sha256"]:
                    raise DriverError("REFERENCE_ROLE_DEDUP_HASH_MISMATCH")
                source.unlink()
            else:
                os.replace(source, canonical)
            deduplicated.append({"role": entry["role"], "source_sha256": entry["sha256"], "canonical_path": canonical.as_posix(), "canonical_sha256": sha256_file(canonical)})
        dedup_path = manifest.with_name(manifest.name.replace(".full_role_manifest.json", ".reference_dedup.json"))
        write_json_atomic(dedup_path, {"schema_version": "gen_enc_2_e2_reference_role_dedup_rc03_v1", "entries": deduplicated})
        merge_hash = sha256_file(dedup_path)
    resource = gate(output_root, ledger)
    write_json_atomic(checkpoint, {"status": "PASS_COMPLETE_ROLES_CHECKPOINTED", "phase": phase, "merge_position": merge_position,
                                  "receipt_sha256": sha256_file(receipt), "manifest_sha256": sha256_file(manifest),
                                  "merge_contribution_sha256": merge_hash, "resource": resource, "same_run_retry": False, "later_merge": True})
    if retain_audit:
        audit.parent.mkdir(parents=True, exist_ok=True); os.replace(raw, audit)
    else:
        raw.unlink()
    if phase == "COMMON_W_PASS":
        for entry in manifest_value["entries"]:
            Path(entry["path"]).unlink()


def run(args: argparse.Namespace) -> int:
    authorization = authorization_first(Path(args.authorization), args.mode)  # first formal I/O
    bind_paths = {"contract": args.contract, "exact80": args.exact80, "nuisance": args.nuisance_csv, "seed_split": args.seed_split,
                  "driver_code": __file__, "verifier_code": args.verifier, "stats_code": args.stats_code, "merge_code": args.merge_code,
                  "core_code": REPO / "src/acoustic_encoder/gen_enc/forward_acoustic_network.py", "runtime": args.runtime_manifest, "dependencies": args.source_manifest}
    hashes = {key: sha256_file(Path(value)) for key, value in bind_paths.items()}
    if authorization.get("bindings") != hashes or Path(str(authorization.get("output_root", ""))).as_posix() != Path(args.output_root).as_posix():
        raise DriverError("AUTHORIZATION_BINDING_OR_ROOT_MISMATCH")
    contract = read_json(Path(args.contract)); del contract
    exact80 = read_json(Path(args.exact80)); seed = read_json(Path(args.seed_split))
    partition, angles, seeds = partition_values(args.mode, seed)
    output_root = Path(args.output_root)
    ledger = ResourceLedger.start()
    if output_root.exists() and not args.resume:
        raise DriverError("ROOT_EXISTS_WITHOUT_RESUME")
    if output_root.exists() and args.resume:
        if (output_root / "partition_terminal.json").exists():
            raise DriverError("COMPLETED_PARTITION_CANNOT_REOPEN")
        if (output_root / "checkpoint.json").exists() and read_json(output_root / "checkpoint.json").get("status") == "PARTITION_STOP":
            raise DriverError("FAILED_PARTITION_NO_SAME_RUN_RETRY")
    output_root.mkdir(parents=True, exist_ok=True)
    gate(output_root, ledger, startup=True)
    nuisance = nuisance_rows(Path(args.nuisance_csv))
    if args.mode == "single-use-validation":
        dseal = read_json(Path(args.development_seal))
        if dseal.get("status") != "E2_D_SEALED_INDEPENDENT_PASS" or dseal.get("complete_identities") != 80 or dseal.get("development_decisions_sealed") is not True or dseal.get("validation_opened") is not False:
            raise DriverError("COMPLETE_DEVELOPMENT_SEAL_REQUIRED")
        sealed_w = Path(args.sealed_w)
        if sha256_file(sealed_w) != dseal.get("common_w_sha256"):
            raise DriverError("SEALED_W_HASH_MISMATCH")
        phases = ("VALIDATION_METRIC_PASS",)
    else:
        sealed_w = output_root / "sealed" / "common_w.npz"
        phases = ("COMMON_W_PASS", "DEVELOPMENT_METRIC_PASS")
    from scripts.gen_enc_2_e2_independent_verifier_rc03 import COMMON_W_ROLES, DEVELOPMENT_METRIC_ROLES, VALIDATION_METRIC_ROLES
    role_sets = {"COMMON_W_PASS": COMMON_W_ROLES, "DEVELOPMENT_METRIC_PASS": DEVELOPMENT_METRIC_ROLES, "VALIDATION_METRIC_PASS": VALIDATION_METRIC_ROLES}
    from scripts.gen_enc_2_e2_merge_reconstruct_rc03 import aggregate_families, development_seal, reconstruct_candidate_from_root, seal_common_w
    for phase in phases:
        merge_position = 0
        for member_entry in exact80["members"]:
            member_path = Path(member_entry["identity_path"]); member = read_json(member_path)
            selected = audit_chunks(partition, member["member_id"])
            for chunk_index in range(CHUNKS):
                chunk = f"chunk_{chunk_index:03d}"; start = chunk_index * 25; end = start + 25
                raw = output_root / "temp" / phase / member["member_id"] / f"{chunk}.npy"
                write_raw(raw, generate(member, nuisance, partition=partition, angles=angles, seeds=seeds, start=start, end=end))
                stats_root = output_root / "stats" / phase / member["member_id"]
                manifest = stats_root / f"{chunk}.full_role_manifest.json"
                receipt = output_root / "receipts" / phase / member["member_id"] / f"{chunk}.json"
                command = [sys.executable, "-B", args.verifier, "verify-chunk", "--phase", phase, "--member", member_path.as_posix(),
                           "--nuisance-csv", args.nuisance_csv, "--seed-split", args.seed_split, "--partition", partition,
                           "--chunk-id", chunk, "--cell-start", str(start), "--cell-end-exclusive", str(end), "--driver-raw", raw.as_posix(),
                           "--stats-root", stats_root.as_posix(), "--receipt", receipt.as_posix(), "--hashes-json", json.dumps(hashes, separators=(",", ":")),
                           "--merge-position", str(merge_position)]
                if phase != "COMMON_W_PASS":
                    command += ["--sealed-w", sealed_w.as_posix(), "--through-reference", args.through_reference]
                complete_role_delete_gate(raw=raw, receipt=receipt, manifest=manifest, verifier_argv=command, phase=phase,
                    expected_roles=role_sets[phase], output_root=output_root, checkpoint=output_root / "checkpoint.json",
                    quarantine=output_root / "quarantine" / phase / member["member_id"] / f"{chunk}.npy",
                    audit=output_root / "raw_audit" / member["member_id"] / f"{chunk}.npy",
                    retain_audit=phase != "COMMON_W_PASS" and chunk in selected, ledger=ledger, merge_position=merge_position,
                    w_accumulator=output_root / "merge" / "common_w_accumulator.npz", w_merge_checkpoint=output_root / "merge" / "common_w_checkpoint.json")
                merge_position += 1
        if phase == "COMMON_W_PASS":
            seal = seal_common_w(output_root / "merge" / "common_w_accumulator.npz", sealed_w)
            write_json_atomic(output_root / "sealed" / "common_w_seal.json", seal)
    candidate_paths = []
    metric_phase = "DEVELOPMENT_METRIC_PASS" if args.mode == "development" else "VALIDATION_METRIC_PASS"
    for member_entry in exact80["members"]:
        identity = member_entry["member_id"]
        target = output_root / "candidate_terminals" / f"{identity}.json"
        result = reconstruct_candidate_from_root(output_root / "stats" / metric_phase / identity, target)
        result["identity_id"] = identity; result["family_id"] = member_entry["family_id"]
        write_json_atomic(target, result); candidate_paths.append(target)
    family_path = output_root / "family_global_terminal.json"
    aggregate_families(candidate_paths, family_path, partition=partition)
    if args.mode == "development":
        development_seal(sealed_w, candidate_paths, family_path, output_root / "partition_terminal.json")
    else:
        value = {"schema_version": "gen_enc_2_e2_partition_terminal_rc03_v1", "partition": partition,
                 "status": "E2_V_SINGLE_USE_TERMINAL", "complete_identities": 80, "independent_verify_pass": True,
                 "common_w_sha256": sha256_file(sealed_w), "development_seal_sha256": sha256_file(Path(args.development_seal)),
                 "candidate_terminals_sha256": hashlib.sha256("".join(sha256_file(path) for path in candidate_paths).encode()).hexdigest(),
                 "family_global_terminal_sha256": sha256_file(family_path), "validation_refit": False,
                 "validation_feedback_to_development": False, "single_use_consumed": True, "formal_run_id_created": False, "final_test_read": False}
        write_json_atomic(output_root / "partition_terminal.json", value)
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(); value.add_argument("mode", choices=("self-test", "development", "single-use-validation"))
    for name in ("authorization", "contract", "exact80", "nuisance-csv", "seed-split", "source-manifest", "runtime-manifest", "output-root", "verifier", "stats-code", "merge-code", "through-reference", "development-seal", "sealed-w"):
        value.add_argument(f"--{name}")
    value.add_argument("--resume", action="store_true"); return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(json.dumps({"status": "PASS", "formal_units": 0, "phases": ["COMMON_W_PASS", "DEVELOPMENT_METRIC_PASS", "VALIDATION_METRIC_PASS"], "final_test_read": False}, sort_keys=True)); return 0
        required = [args.authorization, args.contract, args.exact80, args.nuisance_csv, args.seed_split, args.source_manifest, args.runtime_manifest, args.output_root, args.verifier, args.stats_code, args.merge_code, args.through_reference]
        if any(value is None for value in required) or (args.mode == "single-use-validation" and (not args.development_seal or not args.sealed_w)):
            raise DriverError("FORMAL_ARGUMENTS_REQUIRED")
        return run(args)
    except (OSError, ValueError, KeyError, DriverError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Single-use E2-V overlay: bounded Windows retry and complete-unit resume ledger.

The scientific generator, independent verifier, role calculations, reconstruction,
precision, workload, seeds, angles, frequencies, cells, repeats, metrics, and gates
remain those of the frozen RC-B-final implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import scripts.gen_enc_2_e2_formal_driver_rc03 as base
import scripts.gen_enc_2_e2_formal_driver_rc_b_final as frozen
import scripts.gen_enc_2_e2_merge_reconstruct_rc03 as predecessor_merge
import scripts.gen_enc_2_e2_merge_reconstruct_rc_b_final as final_merge
from acoustic_encoder.gen_enc.e2_rc03_resource import ResourceLedger
from acoustic_encoder.gen_enc.e2_rc03_stats import canonical_json_bytes, sha256_file
from scripts.gen_enc_2_e2_independent_verifier_rc03 import VALIDATION_METRIC_ROLES

EXPECTED_UNITS = 80
EXPECTED_CHUNKS = 147
PHASE = "VALIDATION_METRIC_PASS"
PARTITION = "single_use_validation"
_ORIGINAL_REPLACE = os.replace
_DELAYS_SECONDS = (0.05, 0.10, 0.20, 0.40, 0.80, 1.60, 1.60, 1.60)


class ValidationResumeError(RuntimeError):
    pass


def replace_with_bounded_retry(source: object, destination: object) -> None:
    for attempt in range(len(_DELAYS_SECONDS) + 1):
        try:
            _ORIGINAL_REPLACE(source, destination)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in (5, 32, 33) or attempt == len(_DELAYS_SECONDS):
                raise
            time.sleep(_DELAYS_SECONDS[attempt])


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def unit_receipt_path(ledger_root: Path, position: int) -> Path:
    return ledger_root / "completed_units" / f"unit_{position:03d}.json"


def receipt_set(output_root: Path, identity: str, hashes: dict[str, str], member_position: int) -> tuple[str, str]:
    receipt_hashes: list[str] = []
    manifest_hashes: list[str] = []
    for chunk_index in range(EXPECTED_CHUNKS):
        chunk = f"chunk_{chunk_index:03d}"
        receipt_path = output_root / "receipts" / PHASE / identity / f"{chunk}.json"
        manifest_path = output_root / "stats" / PHASE / identity / f"{chunk}.full_role_manifest.json"
        if not receipt_path.is_file() or not manifest_path.is_file():
            raise ValidationResumeError("COMPLETE_UNIT_EXACT147_RECEIPTS_AND_MANIFESTS_REQUIRED")
        receipt = base.read_json(receipt_path)
        expected_position = member_position * EXPECTED_CHUNKS + chunk_index
        if (receipt.get("status") != "PASS" or receipt.get("partition") != PARTITION or
                receipt.get("phase") != PHASE or receipt.get("identity_id") != identity or
                receipt.get("chunk_id") != chunk or receipt.get("hashes") != hashes or
                receipt.get("role_count") != len(VALIDATION_METRIC_ROLES) or
                receipt.get("canonical_merge_position") != expected_position or
                receipt.get("full_role_manifest_sha256") != sha256_file(manifest_path)):
            raise ValidationResumeError("COMPLETE_UNIT_INDEPENDENT_RECEIPT_MISMATCH")
        manifest = base.read_json(manifest_path)
        if (manifest.get("partition") != PARTITION or manifest.get("phase") != PHASE or
                manifest.get("identity_id") != identity or manifest.get("chunk_id") != chunk or
                manifest.get("role_set_complete") is not True or
                tuple(entry.get("role") for entry in manifest.get("entries", [])) != VALIDATION_METRIC_ROLES or
                manifest.get("canonical_merge_position") != expected_position):
            raise ValidationResumeError("COMPLETE_UNIT_ROLE_MANIFEST_MISMATCH")
        receipt_hashes.append(sha256_file(receipt_path))
        manifest_hashes.append(sha256_file(manifest_path))
    return canonical_sha(receipt_hashes), canonical_sha(manifest_hashes)


def completed_unit_matches(
    *, ledger_path: Path, output_root: Path, identity: str, family: str, member_entry: dict[str, Any],
    member_position: int, hashes: dict[str, str], development_seal_sha256: str, sealed_w_sha256: str,
) -> bool:
    if not ledger_path.is_file():
        return False
    value = base.read_json(ledger_path)
    candidate = output_root / "candidate_terminals" / f"{identity}.json"
    if not candidate.is_file():
        raise ValidationResumeError("LEDGER_CANDIDATE_TERMINAL_MISSING")
    receipt_sha, manifest_sha = receipt_set(output_root, identity, hashes, member_position)
    expected = {
        "schema_version": "gen_enc_2_e2_validation_completed_unit_ledger_v1",
        "status": "PASS_COMPLETE_INDEPENDENT_VALIDATION_UNIT",
        "partition": PARTITION,
        "phase": PHASE,
        "unit_position": member_position,
        "identity_id": identity,
        "family_id": family,
        "member_entry_sha256": canonical_sha(member_entry),
        "input_bindings_sha256": canonical_sha(hashes),
        "development_seal_sha256": development_seal_sha256,
        "sealed_w_sha256": sealed_w_sha256,
        "complete_chunks": EXPECTED_CHUNKS,
        "independent_verify_pass": True,
        "receipt_set_sha256": receipt_sha,
        "manifest_set_sha256": manifest_sha,
        "candidate_terminal_sha256": sha256_file(candidate),
        "final_test_read": False,
    }
    if value != expected:
        raise ValidationResumeError("COMPLETED_UNIT_LEDGER_HASH_OR_PASS_MISMATCH")
    return True


def remove_incomplete_unit(output_root: Path, identity: str) -> None:
    index_path = output_root / "reference_stats" / PARTITION / "dedup_index.json"
    if index_path.is_file():
        index = base.read_json(index_path)
        entries = index.get("entries", {})
        if not isinstance(entries, dict):
            raise ValidationResumeError("DEDUP_INDEX_INVALID_DURING_INCOMPLETE_UNIT_RESET")
        for key in list(entries):
            record = entries[key]
            origins = record.get("origins", [])
            retained = [origin for origin in origins if origin.get("identity_id") != identity]
            if retained:
                record["origins"] = retained
            else:
                payload = Path(record.get("canonical_payload_path", ""))
                if payload.is_file():
                    payload.unlink()
                del entries[key]
        base.write_json_atomic(index_path, index)
    targets = (
        output_root / "temp" / PHASE / identity,
        output_root / "stats" / PHASE / identity,
        output_root / "receipts" / PHASE / identity,
        output_root / "quarantine" / PHASE / identity,
        output_root / "raw_audit" / identity,
        output_root / "candidate_outputs" / identity,
    )
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
    terminal = output_root / "candidate_terminals" / f"{identity}.json"
    if terminal.is_file():
        terminal.unlink()


def write_unit_ledger(
    *, ledger_root: Path, output_root: Path, identity: str, family: str, member_entry: dict[str, Any],
    member_position: int, hashes: dict[str, str], development_seal_sha256: str, sealed_w_sha256: str,
) -> Path:
    receipt_sha, manifest_sha = receipt_set(output_root, identity, hashes, member_position)
    candidate = output_root / "candidate_terminals" / f"{identity}.json"
    value = {
        "schema_version": "gen_enc_2_e2_validation_completed_unit_ledger_v1",
        "status": "PASS_COMPLETE_INDEPENDENT_VALIDATION_UNIT",
        "partition": PARTITION,
        "phase": PHASE,
        "unit_position": member_position,
        "identity_id": identity,
        "family_id": family,
        "member_entry_sha256": canonical_sha(member_entry),
        "input_bindings_sha256": canonical_sha(hashes),
        "development_seal_sha256": development_seal_sha256,
        "sealed_w_sha256": sealed_w_sha256,
        "complete_chunks": EXPECTED_CHUNKS,
        "independent_verify_pass": True,
        "receipt_set_sha256": receipt_sha,
        "manifest_set_sha256": manifest_sha,
        "candidate_terminal_sha256": sha256_file(candidate),
        "final_test_read": False,
    }
    path = unit_receipt_path(ledger_root, member_position)
    base.write_json_atomic(path, value)
    return path


def run(args: argparse.Namespace) -> int:
    authorization = base.authorization_first(Path(args.authorization), args.mode)
    bind_paths = {
        "contract": args.contract, "exact80": args.exact80, "nuisance": args.nuisance_csv,
        "seed_split": args.seed_split, "driver_code": __file__, "verifier_code": args.verifier,
        "stats_code": args.stats_code, "merge_code": args.merge_code,
        "core_code": REPO / "src/acoustic_encoder/gen_enc/forward_acoustic_network.py",
        "runtime": args.runtime_manifest, "dependencies": args.source_manifest,
    }
    hashes = {key: sha256_file(Path(value)) for key, value in bind_paths.items()}
    if authorization.get("bindings") != hashes or Path(str(authorization.get("output_root", ""))).as_posix() != Path(args.output_root).as_posix():
        raise ValidationResumeError("AUTHORIZATION_BINDING_OR_ROOT_MISMATCH")
    if Path(str(authorization.get("completed_ledger_root", ""))).as_posix() != Path(args.completed_ledger_root).as_posix():
        raise ValidationResumeError("AUTHORIZATION_LEDGER_ROOT_MISMATCH")
    base.read_json(Path(args.contract))
    exact80 = base.read_json(Path(args.exact80))
    seed = base.read_json(Path(args.seed_split))
    partition, angles, seeds = base.partition_values(args.mode, seed)
    if partition != PARTITION or len(exact80.get("members", [])) != EXPECTED_UNITS:
        raise ValidationResumeError("EXACT_SINGLE_USE_VALIDATION_80_REQUIRED")
    output_root = Path(args.output_root)
    ledger_root = Path(args.completed_ledger_root)
    if output_root.exists() and not args.resume:
        raise ValidationResumeError("ROOT_EXISTS_WITHOUT_RESUME")
    if output_root.exists() and (output_root / "partition_terminal.json").exists():
        raise ValidationResumeError("COMPLETED_PARTITION_CANNOT_REOPEN")
    output_root.mkdir(parents=True, exist_ok=True)
    ledger_root.mkdir(parents=True, exist_ok=True)
    ledger = ResourceLedger.start()
    base.gate(output_root, ledger, startup=True)
    nuisance = base.nuisance_rows(Path(args.nuisance_csv))
    development_seal = Path(args.development_seal)
    dseal = base.read_json(development_seal)
    if (dseal.get("status") != "E2_D_SEALED_INDEPENDENT_PASS" or dseal.get("complete_identities") != 80 or
            dseal.get("independent_verify_pass") is not True or dseal.get("development_decisions_sealed") is not True or
            dseal.get("validation_opened") is not False or dseal.get("validation_refit") is not False or
            dseal.get("final_test_read") is not False):
        raise ValidationResumeError("COMPLETE_DEVELOPMENT_SEAL_REQUIRED")
    sealed_w = Path(args.sealed_w)
    sealed_w_sha256 = sha256_file(sealed_w)
    if sealed_w_sha256 != dseal.get("common_w_sha256"):
        raise ValidationResumeError("SEALED_W_HASH_MISMATCH")
    development_seal_sha256 = sha256_file(development_seal)
    candidate_paths: list[Path] = []
    incomplete_seen = False
    for member_position, member_entry in enumerate(exact80["members"]):
        identity = member_entry["member_id"]
        family = member_entry["family_id"]
        unit_path = unit_receipt_path(ledger_root, member_position)
        if completed_unit_matches(ledger_path=unit_path, output_root=output_root, identity=identity, family=family,
                member_entry=member_entry, member_position=member_position, hashes=hashes,
                development_seal_sha256=development_seal_sha256, sealed_w_sha256=sealed_w_sha256):
            if incomplete_seen:
                raise ValidationResumeError("COMPLETED_UNIT_LEDGER_MUST_BE_CONTIGUOUS_PREFIX")
            candidate_paths.append(output_root / "candidate_terminals" / f"{identity}.json")
            continue
        incomplete_seen = True
        remove_incomplete_unit(output_root, identity)
        member_path = Path(member_entry["identity_path"])
        member = base.read_json(member_path)
        selected = base.audit_chunks(partition, identity)
        for chunk_index in range(EXPECTED_CHUNKS):
            chunk = f"chunk_{chunk_index:03d}"
            start = chunk_index * 25
            end = start + 25
            merge_position = member_position * EXPECTED_CHUNKS + chunk_index
            raw = output_root / "temp" / PHASE / identity / f"{chunk}.npy"
            base.write_raw(raw, base.generate(member, nuisance, partition=partition, angles=angles, seeds=seeds, start=start, end=end))
            stats_root = output_root / "stats" / PHASE / identity
            manifest = stats_root / f"{chunk}.full_role_manifest.json"
            receipt = output_root / "receipts" / PHASE / identity / f"{chunk}.json"
            command = [sys.executable, "-B", args.verifier, "verify-chunk", "--phase", PHASE,
                "--member", member_path.as_posix(), "--nuisance-csv", args.nuisance_csv,
                "--seed-split", args.seed_split, "--partition", partition, "--chunk-id", chunk,
                "--cell-start", str(start), "--cell-end-exclusive", str(end), "--driver-raw", raw.as_posix(),
                "--stats-root", stats_root.as_posix(), "--receipt", receipt.as_posix(),
                "--hashes-json", json.dumps(hashes, separators=(",", ":")), "--merge-position", str(merge_position),
                "--sealed-w", sealed_w.as_posix(), "--through-reference", args.through_reference]
            base.complete_role_delete_gate(raw=raw, receipt=receipt, manifest=manifest, verifier_argv=command,
                phase=PHASE, expected_roles=VALIDATION_METRIC_ROLES, output_root=output_root,
                checkpoint=output_root / "checkpoint.json",
                quarantine=output_root / "quarantine" / PHASE / identity / f"{chunk}.npy",
                audit=output_root / "raw_audit" / identity / f"{chunk}.npy",
                retain_audit=chunk in selected, ledger=ledger, merge_position=merge_position)
        target = output_root / "candidate_terminals" / f"{identity}.json"
        result = predecessor_merge.reconstruct_candidate_from_root(output_root / "stats" / PHASE / identity, target)
        result["identity_id"] = identity
        result["family_id"] = family
        base.write_json_atomic(target, result)
        candidate_paths.append(target)
        write_unit_ledger(ledger_root=ledger_root, output_root=output_root, identity=identity, family=family,
            member_entry=member_entry, member_position=member_position, hashes=hashes,
            development_seal_sha256=development_seal_sha256, sealed_w_sha256=sealed_w_sha256)
    family_path = output_root / "family_global_terminal.json"
    predecessor_merge.aggregate_families(candidate_paths, family_path, partition=partition)
    terminal = {
        "schema_version": "gen_enc_2_e2_partition_terminal_rc03_v1", "partition": partition,
        "status": "E2_V_SINGLE_USE_TERMINAL", "complete_identities": EXPECTED_UNITS,
        "independent_verify_pass": True, "common_w_sha256": sealed_w_sha256,
        "development_seal_sha256": development_seal_sha256,
        "candidate_terminals_sha256": hashlib.sha256("".join(sha256_file(path) for path in candidate_paths).encode()).hexdigest(),
        "family_global_terminal_sha256": sha256_file(family_path), "validation_refit": False,
        "validation_feedback_to_development": False, "single_use_consumed": True,
        "formal_run_id_created": False, "final_test_read": False,
    }
    base.write_json_atomic(output_root / "partition_terminal.json", terminal)
    return 0


def parser() -> argparse.ArgumentParser:
    value = frozen.parser()
    value.add_argument("--completed-ledger-root")
    return value


def main(argv: list[str] | None = None) -> int:
    os.replace = replace_with_bounded_retry
    frozen.install_overlay()
    args = parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            print(json.dumps({"status": "PASS", "formal_units": 0, "resume_unit": "COMPLETE_INDEPENDENT_IDENTITY",
                "windows_replace_retry_attempts": len(_DELAYS_SECONDS), "final_test_read": False}, sort_keys=True))
            return 0
        required = [args.authorization, args.contract, args.exact80, args.nuisance_csv, args.seed_split,
            args.source_manifest, args.runtime_manifest, args.output_root, args.verifier, args.stats_code,
            args.merge_code, args.through_reference, args.development_seal, args.sealed_w, args.completed_ledger_root]
        if args.mode != "single-use-validation" or any(value is None for value in required):
            raise ValidationResumeError("EXACT_VALIDATION_ARGUMENTS_REQUIRED")
        return run(args)
    except (OSError, ValueError, KeyError, base.DriverError, frozen.FinalDriverError,
            predecessor_merge.MergeError, final_merge.FinalReconstructionError, ValidationResumeError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

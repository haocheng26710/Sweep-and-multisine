"""Task-bound GEN-ENC-2C S2 formal generation/static-audit driver.

No formal input is opened by ``--help`` or ``validate-draft``.  The two formal
commands fail closed unless a canonical, guardian-released record binds the CLI
task id, exact command/mode, runtime, contract, manifests and 92-path state.
This is new S2 source; it does not import or inspect rejected 2C REV01 bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import jsonschema


EVIDENCE_LEVEL = "E1_TECHNICAL_PREEXECUTION_BINDING_ONLY"
FORMAL_EVIDENCE_CEILING = "E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY_ONLY"
FORMAL_COMMANDS = (
    "preflight",
    "formal-generate-static-audit",
    "verify-formal",
    "package-results",
)
FORMAL_MODES = (
    "S2_PREFLIGHT",
    "S2_FORMAL_GENERATION_STATIC_AUDIT",
    "S2_INDEPENDENT_FORMAL_VERIFICATION",
    "S2_ATOMIC_PACKAGE_RESULTS",
)
PERMISSION_VECTOR = {
    "s2_formal_generation_and_static_audit": True,
    "timing": False,
    "response": False,
    "endpoint": False,
    "family_comparison": False,
    "ranking": False,
    "selection": False,
    "optimization": False,
    "simulation": False,
    "comsol": False,
    "full_wave": False,
    "physical_experiment": False,
    "development_read": False,
    "validation_read": False,
    "final_test_read": False,
    "gen_enc_2": False,
}
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class FailClosed(RuntimeError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    def finite(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise FailClosed("NONFINITE_JSON")
        if isinstance(item, dict):
            if not all(isinstance(k, str) for k in item):
                raise FailClosed("NON_STRING_JSON_KEY")
            for child in item.values():
                finite(child)
        elif isinstance(item, list):
            for child in item:
                finite(child)
    finite(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def json_pointer(document: Any, pointer: str) -> Any:
    current = document
    if pointer == "":
        return current
    if not pointer.startswith("/"):
        raise FailClosed("INVALID_JSON_POINTER")
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, FileNotFoundError):
        return False


def contained(repo: Path, relative: str) -> Path:
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts:
        raise FailClosed(f"UNSAFE_RELATIVE_PATH:{relative}")
    for part in item.parts:
        if part.endswith((".", " ")) or part.split(".", 1)[0].upper() in RESERVED:
            raise FailClosed(f"RESERVED_PATH:{relative}")
    root = repo.resolve(strict=True)
    target = Path(os.path.abspath(root / item))
    target.relative_to(root)
    current = root
    for part in target.relative_to(root).parts[:-1]:
        current /= part
        if current.exists() and _is_reparse(current):
            raise FailClosed(f"REPARSE_ANCESTOR:{relative}")
    return target


def verify_runtime(contract: dict[str, Any]) -> None:
    observed = {
        "python": platform.python_version(),
        "jsonschema": importlib.metadata.version("jsonschema"),
    }
    if observed != contract["runtime_binding"]:
        raise FailClosed(f"RUNTIME_MISMATCH:{observed}")


def verify_manifest(repo: Path, path: str, expected_hash: str) -> dict[str, Any]:
    manifest_path = contained(repo, path)
    if sha256_file(manifest_path) != expected_hash:
        raise FailClosed(f"MANIFEST_HASH_MISMATCH:{path}")
    manifest = load_json(manifest_path)
    for entry in manifest.get("entries", []):
        subject = contained(repo, entry["path"])
        if not subject.is_file() or sha256_file(subject) != entry["sha256"] or subject.stat().st_size != entry["byte_length"]:
            raise FailClosed(f"MANIFEST_ENTRY_MISMATCH:{entry['path']}")
    return manifest


def validate_allowlist(repo: Path, manifest: dict[str, Any], require_absent: bool) -> list[Path]:
    paths = manifest["paths"]
    if len(paths) != 92 or len({p.replace("\\", "/").casefold() for p in paths}) != 92:
        raise FailClosed("ALLOWLIST_COUNT_CASEFOLD_OR_DUPLICATE")
    targets = [contained(repo, p) for p in paths]
    folded = {p.replace("\\", "/").casefold() for p in paths}
    for value in folded:
        parts = value.split("/")
        if any("/".join(parts[:i]) in folded for i in range(1, len(parts))):
            raise FailClosed("ALLOWLIST_FILE_DIRECTORY_COLLISION")
    if require_absent and any(path.exists() for path in targets):
        raise FailClosed("FORMAL_TARGET_ALREADY_EXISTS")
    return targets


def verify_zero_unlisted(roots: Iterable[Path], allowed: set[Path]) -> None:
    for root in roots:
        if root.exists():
            for item in root.rglob("*"):
                if item.is_file() and item.resolve() not in allowed:
                    raise FailClosed(f"UNLISTED_FORMAL_FILE:{item}")


def validate_record(repo: Path, record_path: Path, schema_path: Path, contract_path: Path,
                    cli_task_id: str, command: str, mode: str, require_release: bool,
                    now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = record_path.read_bytes()
    record = json.loads(raw.decode("utf-8"))
    schema = load_json(schema_path)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(record, schema, cls=jsonschema.Draft202012Validator)
    if raw != canonical_json_bytes(record):
        raise FailClosed("AUTHORIZATION_RECORD_NOT_CANONICAL_EXACT_BYTES")
    payload = record["payload"]
    if sha256_bytes(canonical_json_bytes(payload)) != record["record_payload_sha256"]:
        raise FailClosed("AUTHORIZATION_RECORD_PAYLOAD_SHA_MISMATCH")
    contract = load_json(contract_path)
    if sha256_file(contract_path) != payload["contract_sha256"]:
        raise FailClosed("CONTRACT_HASH_MISMATCH")
    if cli_task_id != payload["task_id"] or cli_task_id != contract["task_id"]:
        raise FailClosed("CLI_DISPATCH_CONTRACT_TASK_ID_MISMATCH")
    if command not in payload["allowed_commands"] or mode not in payload["allowed_modes"]:
        raise FailClosed("COMMAND_OR_MODE_NOT_AUTHORIZED")
    if payload["allowed_commands"] != list(FORMAL_COMMANDS) or payload["allowed_modes"] != list(FORMAL_MODES):
        raise FailClosed("COMMAND_OR_MODE_VECTOR_NOT_EXACT")
    if payload["permissions"] != PERMISSION_VECTOR:
        raise FailClosed("PERMISSION_VECTOR_NOT_EXACT")
    if payload["revoked"]:
        raise FailClosed("AUTHORIZATION_REVOKED")
    current = now or datetime.now(timezone.utc)
    expiry = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    if expiry <= current.astimezone(timezone.utc):
        raise FailClosed("AUTHORIZATION_EXPIRED")
    if payload["final_test_state"] != "SEALED" or payload["final_test_read"]:
        raise FailClosed("FINAL_TEST_BOUNDARY")
    if require_release and not (payload["released"] and payload["guardian_approved"] and payload["formal_execution_authorized"]):
        raise FailClosed("GUARDIAN_RELEASE_REQUIRED")
    for key, path in contract["manifest_paths"].items():
        verify_manifest(repo, path, payload["manifest_sha256"][key])
        if payload["manifest_sha256"][key] != contract["manifest_sha256"][key]:
            raise FailClosed(f"CONTRACT_DISPATCH_MANIFEST_BINDING_MISMATCH:{key}")
    verify_runtime(contract)
    return record, contract


def preflight(repo: Path, record_path: Path, schema_path: Path, contract_path: Path,
              task_id: str, command: str, mode: str, require_release: bool) -> dict[str, Any]:
    _, contract = validate_record(repo, record_path, schema_path, contract_path, task_id, command, mode, require_release)
    allowlist = load_json(contained(repo, contract["manifest_paths"]["allowlist"]))
    targets = validate_allowlist(repo, allowlist, require_absent=True)
    verify_zero_unlisted([contained(repo, p) for p in contract["formal_roots"]], {p.resolve() for p in targets})
    return {
        "status": "PASS_RELEASED_S2_PREFLIGHT" if require_release else "PASS_DRAFT_TECHNICAL_VALIDATION_FORMAL_BLOCKED",
        "task_id": task_id,
        "allowlist_count": 92,
        "existing_target_count": 0,
        "formal_input_read_count": 0,
        "formal_seed_read_count": 0,
        "formal_row_read_count": 0,
        "formal_instance_count": 0,
        "static_eligibility_run_count": 0,
        "final_test_read": False,
    }


def _formal_generation(repo: Path, contract: dict[str, Any], task_id: str) -> None:
    """Run only after released preflight; retain all 80 slots without repair.

    The sealed 2B API supplies exact literal-row, SplitMix64/open-uniform and
    parameter-specific midpoint-LHS generation.  The sealed CAD-1 API supplies
    mapping/static audit, including exact-zero reduced edges and actual-fluid
    positive-area connectivity.  No value or status is performance-dependent.
    """
    generator = importlib.import_module("acoustic_encoder.gen_enc.generator.api")
    slot_contract = load_json(contained(repo, contract["formal_input_paths"]["slot_ordering_contract"]))
    table_path = contained(repo, contract["formal_input_paths"]["family_design_tables"])
    family_identity = load_json(contained(repo, contract["formal_input_paths"]["family_identity_manifest"]))
    cad_authority = load_json(contained(repo, contract["formal_input_paths"]["cad_static_authority"]))
    random_spec = json_pointer(family_identity, contract["formal_input_pointers"]["random_parameter_spec"])
    physics_spec = json_pointer(family_identity, contract["formal_input_pointers"]["physics_parameter_spec"])
    hand = generator.load_literal_family_table(table_path, contract["formal_input_sha256"]["family_design_tables"], "HAND_DESIGNED")
    near = generator.load_literal_family_table(table_path, contract["formal_input_sha256"]["family_design_tables"], "NEAR_INDEPENDENT")
    generated: list[dict[str, Any]] = []
    physics_cache: dict[int, dict[str, Any]] = {}
    for slot in slot_contract["exact_order"]:
        try:
            if slot["family_id"] == "HAND_DESIGNED":
                parameters = hand["rows"][slot["member_ordinal"] - 1]
            elif slot["family_id"] == "NEAR_INDEPENDENT":
                parameters = near["rows"][slot["member_ordinal"] - 1]
            elif slot["family_id"] == "FIXED_SEED_RANDOM_DISORDERED":
                parameters = generator.random_parameters(slot["formal_seed"], random_spec)
            else:
                master = slot["formal_master_seed"]
                if master not in physics_cache:
                    physics_cache[master] = generator.physics_midpoint_lhs(master, physics_spec)
                parameters = physics_cache[master]["rows"][slot["member_ordinal"] - 1]
            numeric = parameters.get("parameters", parameters)
            required_static = {"connected_volume_m3", "envelope_m", "interface_identity", "minimum_feature_m", "minimum_solid_load_path_m", "fluid_nodes", "positive_area_faces"}
            if not required_static <= set(numeric):
                raise FailClosed("FORMAL_CAD_STATIC_DERIVATION_FIELDS_MISSING")
            volume_ok = contract["static_semantics"]["matched_volume_closed_interval_m3"][0] <= numeric["connected_volume_m3"] <= contract["static_semantics"]["matched_volume_closed_interval_m3"][1]
            envelope_ok = all(a <= b for a, b in zip(numeric["envelope_m"], contract["static_semantics"]["envelope_caps_m"]))
            static = {"authority": cad_authority, "volume_ok": volume_ok, "envelope_ok": envelope_ok, "interface_ok": numeric["interface_identity"] == contract["static_semantics"]["interface"], "feature_ok": numeric["minimum_feature_m"] >= contract["static_semantics"]["general_minimum_feature_m"], "load_path_ok": numeric["minimum_solid_load_path_m"] >= contract["static_semantics"]["general_minimum_solid_load_path_m"], "fluid_nodes": numeric["fluid_nodes"], "positive_area_faces": numeric["positive_area_faces"]}
            status = "STATIC_IDENTITY_ELIGIBLE" if all(value for key, value in static.items() if key.endswith("_ok")) else "COST_INELIGIBLE"
            generated.append({"slot": slot, "parameters": parameters, "static_audit": static, "status": status})
        except Exception as exc:
            generated.append({"slot": slot, "status": "GENERATION_TECHNICAL_FAILURE", "error": f"{type(exc).__name__}:{exc}"})
    if len(generated) != 80:
        raise FailClosed("FORMAL_SLOT_RETENTION_FAILURE")
    staging = contained(repo, contract["terminal_roots"]["staging"])
    if staging.exists():
        raise FailClosed("STAGING_ROOT_ALREADY_EXISTS")
    atomic_write(staging / "generated_slots.json", canonical_json_bytes({"task_id": task_id, "slots": generated}))
    atomic_write(staging / "GENERATION_COMPLETE.json", canonical_json_bytes({"retained_slot_count": 80}))


def package_results(staging: Path, success: Path, failure: Path) -> None:
    success_marker = staging / "VERIFIED_SUCCESS.json"
    failure_marker = staging / "FAIL_CLOSED.json"
    if success_marker.exists() == failure_marker.exists():
        raise FailClosed("MIXED_OR_MISSING_TERMINAL_MARKER")
    destination, other = (success, failure) if success_marker.exists() else (failure, success)
    if destination.exists() or other.exists():
        raise FailClosed("TERMINAL_ROOT_ALREADY_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-root", required=True, type=Path)
    common.add_argument("--contract", required=True, type=Path)
    common.add_argument("--authorization-record", required=True, type=Path)
    common.add_argument("--authorization-schema", required=True, type=Path)
    common.add_argument("--task-id", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-draft", parents=[common])
    sub.add_parser("preflight", parents=[common])
    sub.add_parser("formal-generate-static-audit", parents=[common])
    pkg = sub.add_parser("package-results", parents=[common])
    args = parser.parse_args()
    mode_by_command = {
        "validate-draft": "S2_PREFLIGHT",
        "preflight": "S2_PREFLIGHT",
        "formal-generate-static-audit": "S2_FORMAL_GENERATION_STATIC_AUDIT",
        "package-results": "S2_ATOMIC_PACKAGE_RESULTS",
    }
    try:
        if args.command == "validate-draft":
            report = preflight(args.repo_root, args.authorization_record, args.authorization_schema, args.contract,
                               args.task_id, "preflight", mode_by_command[args.command], False)
            print(canonical_json_bytes(report).decode("utf-8"))
            return 0
        report = preflight(args.repo_root, args.authorization_record, args.authorization_schema, args.contract,
                           args.task_id, args.command, mode_by_command[args.command], True)
        if args.command == "preflight":
            print(canonical_json_bytes(report).decode("utf-8"))
        elif args.command == "formal-generate-static-audit":
            _formal_generation(args.repo_root, load_json(args.contract), args.task_id)
        else:
            contract = load_json(args.contract)
            package_results(contained(args.repo_root, contract["terminal_roots"]["staging"]),
                            contained(args.repo_root, contract["terminal_roots"]["success"]),
                            contained(args.repo_root, contract["terminal_roots"]["failure"]))
        return 0
    except Exception as exc:
        print(f"FAIL_CLOSED:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

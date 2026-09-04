"""GEN-ENC-2C REV03 staged orchestrator.

S1 exposes only technical preflight and atomic result packaging.  A later,
task-bound dispatch is required before any formal input may be opened.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import importlib
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


EVIDENCE_LEVEL = "E1_TECHNICAL_IMPLEMENTATION_CONFORMANCE_ONLY"
ADDENDUM_METADATA = {
    "new_content": "S1 staged orchestrator implementation",
    "related_legacy_files": ["docs/experiment/gen_enc/GEN_ENC_2C_PREEXECUTION_CONTRACT_ADDENDUM_REV03.md"],
    "unchanged_content": "All legacy GEN-ENC-2C bytes and scientific artifacts remain unchanged",
    "evidence_level": EVIDENCE_LEVEL,
    "overrides": False,
}
FORMAL_TARGET_COUNT = 92
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
FORBIDDEN_AST_TOKENS = {
    "response", "endpoint", "ranking", "selection", "optimization", "timing",
    "simulation", "comsol", "full_wave", "development", "validation", "final_test",
}


class PreflightError(RuntimeError):
    """Fail-closed technical precondition failure."""


def canonical_json_bytes(value: Any) -> bytes:
    def reject_nonfinite(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise PreflightError("NONFINITE_JSON_NUMBER")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise PreflightError("NON_STRING_JSON_KEY")
                reject_nonfinite(child)
        elif isinstance(item, list):
            for child in item:
                reject_nonfinite(child)

    reject_nonfinite(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def validate_json(instance: Any, schema_path: Path) -> None:
    jsonschema.Draft202012Validator.check_schema(load_json(schema_path))
    jsonschema.validate(instance=instance, schema=load_json(schema_path), cls=jsonschema.Draft202012Validator)


def _path_parts_are_safe(relative: str) -> None:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise PreflightError(f"PATH_NOT_RELATIVE_CONTAINED:{relative}")
    for part in path.parts:
        if part.endswith((".", " ")) or part.split(".", 1)[0].upper() in RESERVED:
            raise PreflightError(f"RESERVED_OR_TRAILING_COMPONENT:{relative}")


def validate_allowlist(paths: Iterable[str]) -> list[str]:
    items = list(paths)
    if len(items) != FORMAL_TARGET_COUNT:
        raise PreflightError(f"ALLOWLIST_COUNT:{len(items)}")
    for item in items:
        _path_parts_are_safe(item)
    folded = [item.replace("\\", "/").casefold() for item in items]
    if len(folded) != len(set(folded)):
        raise PreflightError("ALLOWLIST_CASEFOLD_OR_DUPLICATE_COLLISION")
    ancestors = set(folded)
    for item in folded:
        parts = item.split("/")
        for stop in range(1, len(parts)):
            if "/".join(parts[:stop]) in ancestors:
                raise PreflightError("ALLOWLIST_FILE_DIRECTORY_COLLISION")
    return items


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, FileNotFoundError):
        return False
    return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def validate_containment_and_ancestors(repo_root: Path, target: Path) -> None:
    repo = repo_root.resolve(strict=True)
    lexical = Path(os.path.abspath(target))
    try:
        lexical.relative_to(repo)
    except ValueError as exc:
        raise PreflightError(f"PATH_ESCAPE:{target}") from exc
    current = repo
    for part in lexical.relative_to(repo).parts[:-1]:
        current = current / part
        if current.exists() and _is_reparse(current):
            raise PreflightError(f"REPARSE_ANCESTOR:{current}")


def zero_unlisted_files(root: Path, allowlist: set[Path]) -> None:
    if not root.exists():
        return
    for candidate in root.rglob("*"):
        if candidate.is_file() and candidate.resolve() not in allowlist:
            raise PreflightError(f"UNLISTED_OUTPUT:{candidate}")


def audit_negative_capability(source_paths: Iterable[Path]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    for path in source_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            token = None
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                token = ast.unparse(node).casefold()
            elif isinstance(node, ast.Attribute):
                token = node.attr.casefold()
            elif isinstance(node, ast.Name):
                token = node.id.casefold()
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                token = node.name.casefold()
            if token and any(word in token for word in FORBIDDEN_AST_TOKENS):
                violations.append({"path": path.as_posix(), "token": token})
    return {"checked_source_count": len(list(source_paths)), "violation_count": len(violations), "violations": violations}


def verify_hash_manifest(repo_root: Path, manifest: dict[str, Any]) -> None:
    for entry in manifest["entries"]:
        path = repo_root / entry["path"]
        validate_containment_and_ancestors(repo_root, path)
        if not path.is_file() or sha256_file(path) != entry["sha256"]:
            raise PreflightError(f"HASH_MISMATCH_OR_MISSING:{entry['path']}")


def verify_runtime(binding: dict[str, Any]) -> None:
    observed = {
        "python": platform.python_version(),
        "jsonschema": importlib.metadata.version("jsonschema"),
    }
    for key, expected in binding["required"].items():
        if observed.get(key) != expected:
            raise PreflightError(f"RUNTIME_MISMATCH:{key}:{observed.get(key)}:{expected}")


def verify_dispatch(dispatch: dict[str, Any], source_manifest_hash: str, now: datetime) -> None:
    if dispatch["stage"] not in {"S1_TECHNICAL_FIXTURE", "S2_FORMAL_EXECUTION"}:
        raise PreflightError("DISPATCH_STAGE_INVALID")
    if not dispatch["authorized"] or dispatch["revoked"]:
        raise PreflightError("DISPATCH_NOT_AUTHORIZED_OR_REVOKED")
    expiry = datetime.fromisoformat(dispatch["expires_at"].replace("Z", "+00:00"))
    if expiry <= now.astimezone(timezone.utc):
        raise PreflightError("DISPATCH_EXPIRED")
    if dispatch["source_manifest_sha256"] != source_manifest_hash:
        raise PreflightError("DISPATCH_SOURCE_MANIFEST_HASH_MISMATCH")
    if dispatch["final_test_state"] != "SEALED" or dispatch["final_test_read"]:
        raise PreflightError("FINAL_TEST_BOUNDARY_FAILURE")
    if dispatch["stage"] == "S1_TECHNICAL_FIXTURE" and dispatch["formal_execution_authorized"]:
        raise PreflightError("S1_CANNOT_AUTHORIZE_FORMAL_EXECUTION")


def bind_sealed_generator_api(preflight_report: dict[str, Any], dispatch: dict[str, Any]) -> Any:
    """Bind the separately sealed GEN-ENC-2B API only after an S2 dispatch.

    S1 tests exercise only the rejection branch and never import this module.
    """
    if preflight_report.get("status") != "PASS_TECHNICAL_PREFLIGHT_ONLY":
        raise PreflightError("GENERATOR_BIND_BEFORE_PREFLIGHT")
    if dispatch.get("stage") != "S2_FORMAL_EXECUTION" or not dispatch.get("formal_execution_authorized"):
        raise PreflightError("GENERATOR_BIND_WITHOUT_S2_AUTHORITY")
    return importlib.import_module("acoustic_encoder.gen_enc.generator.api")


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    payload = canonical_json_bytes(value)
    with temp.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def fail_closed_record(error_code: str, observed: dict[str, int], task_id: str) -> dict[str, Any]:
    return {
        "schema_version": "gen_enc_2c_fail_closed_record_rev03_s1_v1",
        "record_kind": "TECHNICAL_FAIL_CLOSED",
        "task_id": task_id,
        "error_code": error_code,
        "observed_counts": observed,
        "evidence_level": EVIDENCE_LEVEL,
        "scientific_hypothesis_status": "NOT_TESTED",
        "formal_instance_count": 0,
        "static_eligibility_run_count": 0,
        "formal_hashes": {"member": None, "family": None, "index": None},
        "final_test_read": False,
    }


def write_fail_closed_atomic(path: Path, schema_path: Path, error_code: str, observed: dict[str, int], task_id: str) -> None:
    record = fail_closed_record(error_code, observed, task_id)
    validate_json(record, schema_path)
    atomic_write_json(path, record)


def run_preflight(repo_root: Path, contract_path: Path, dispatch_path: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    dispatch = load_json(dispatch_path)
    source_manifest_path = repo_root / contract["source_manifest_path"]
    source_hash = sha256_file(source_manifest_path)
    verify_dispatch(dispatch, source_hash, datetime.now(timezone.utc))
    source_manifest = load_json(source_manifest_path)
    verify_runtime(contract["runtime_binding"])
    verify_hash_manifest(repo_root, source_manifest)
    verify_hash_manifest(repo_root, load_json(repo_root / contract["schema_manifest_path"]))
    verify_hash_manifest(repo_root, load_json(repo_root / contract["authority_manifest_path"]))
    allowlist = validate_allowlist(load_json(repo_root / contract["path_allowlist_path"])["paths"])
    absolute = {Path(os.path.abspath(repo_root / path)).resolve() for path in allowlist}
    for path in allowlist:
        target = repo_root / path
        validate_containment_and_ancestors(repo_root, target)
        if target.exists():
            raise PreflightError(f"AUTHORIZED_TARGET_ALREADY_EXISTS:{path}")
    for root in contract["formal_output_roots"]:
        zero_unlisted_files(repo_root / root, absolute)
    audit = audit_negative_capability([repo_root / p for p in contract["negative_capability_source_paths"]])
    if audit["violation_count"]:
        raise PreflightError("NEGATIVE_CAPABILITY_VIOLATION")
    return {
        "status": "PASS_TECHNICAL_PREFLIGHT_ONLY",
        "allowlist_count": len(allowlist),
        "unlisted_count": 0,
        "negative_capability": audit,
        "formal_input_read_count": 0,
        "formal_output_write_count": 0,
        "final_test_read": False,
    }


def package_results(staging_root: Path, success_root: Path, failure_root: Path, failure_schema: Path) -> None:
    success_marker = staging_root / "SUCCESS.json"
    failure_marker = staging_root / "FAIL_CLOSED.json"
    if success_marker.exists() == failure_marker.exists():
        raise PreflightError("MIXED_OR_MISSING_TERMINAL_STATE")
    if failure_marker.exists():
        validate_json(load_json(failure_marker), failure_schema)
    destination = success_root if success_marker.exists() else failure_root
    other = failure_root if success_marker.exists() else success_root
    if destination.exists() or other.exists():
        raise PreflightError("TERMINAL_ROOT_ALREADY_EXISTS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_root, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("technical-preflight")
    pre.add_argument("--repo-root", required=True, type=Path)
    pre.add_argument("--contract", required=True, type=Path)
    pre.add_argument("--dispatch", required=True, type=Path)
    pre.add_argument("--failure-record", required=True, type=Path)
    pre.add_argument("--failure-schema", required=True, type=Path)
    pre.add_argument("--task-id", required=True)
    pkg = sub.add_parser("package-results")
    pkg.add_argument("--staging-root", required=True, type=Path)
    pkg.add_argument("--success-root", required=True, type=Path)
    pkg.add_argument("--failure-root", required=True, type=Path)
    pkg.add_argument("--failure-schema", required=True, type=Path)
    pkg.add_argument("--failure-record", required=True, type=Path)
    pkg.add_argument("--task-id", required=True)
    args = parser.parse_args()
    try:
        if args.command == "technical-preflight":
            print(canonical_json_bytes(run_preflight(args.repo_root, args.contract, args.dispatch)).decode("utf-8"))
        else:
            package_results(args.staging_root, args.success_root, args.failure_root, args.failure_schema)
    except Exception as exc:
        try:
            write_fail_closed_atomic(
                args.failure_record,
                args.failure_schema,
                f"{type(exc).__name__}:{exc}",
                {"formal_inputs_observed": 0, "formal_outputs_observed": 0},
                args.task_id,
            )
        except Exception as record_exc:
            print(f"FAIL_CLOSED_RECORD_WRITE_FAILURE:{type(record_exc).__name__}:{record_exc}", file=sys.stderr)
        print(f"FAIL_CLOSED:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

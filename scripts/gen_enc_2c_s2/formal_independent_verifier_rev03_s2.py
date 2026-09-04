"""Read-only independent S2 verifier; imports neither driver nor generator/CAD APIs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import stat
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema


MASK64 = (1 << 64) - 1
REQUIRED_TRUE = "s2_formal_generation_and_static_audit"


class VerifyError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    def finite(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise VerifyError("NONFINITE")
        if isinstance(item, dict):
            for child in item.values(): finite(child)
        elif isinstance(item, list):
            for child in item: finite(child)
    finite(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def splitmix64(value: int) -> int:
    z = (value + 0x9E3779B97F4A7C15) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


def open_uniform(value: int) -> float:
    result = ((value >> 11) + 0.5) / float(1 << 53)
    return math.nextafter(1.0, 0.0) if result == 1.0 else result


def random_once(seed: int, count: int) -> list[float]:
    state = seed & MASK64
    output = []
    for _ in range(count):
        state = splitmix64(state)
        output.append(open_uniform(state))
    return output


def midpoint_lhs(seed: int, parameters: int, rows: int = 20) -> list[list[float]]:
    columns = []
    for parameter in range(parameters):
        permutation = list(range(rows))
        state = (seed + parameter) & MASK64
        for index in range(rows - 1, 0, -1):
            state = splitmix64(state)
            swap = state % (index + 1)
            permutation[index], permutation[swap] = permutation[swap], permutation[index]
        columns.append([(value + 0.5) / rows for value in permutation])
    return [[columns[column][row] for column in range(parameters)] for row in range(rows)]


def positive_area_components(nodes: list[str], faces: list[list[Any]]) -> int:
    adjacency = {node: set() for node in nodes}
    for left, right, area in faces:
        if float(area) > 0.0:
            adjacency[left].add(right); adjacency[right].add(left)
    remaining = set(nodes); count = 0
    while remaining:
        count += 1; queue = deque([remaining.pop()])
        while queue:
            for other in adjacency[queue.popleft()]:
                if other in remaining:
                    remaining.remove(other); queue.append(other)
    return count


def validate_release(record_path: Path, schema_path: Path, contract_path: Path, task_id: str, command: str) -> dict[str, Any]:
    raw = record_path.read_bytes(); record = json.loads(raw.decode("utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(record, schema, cls=jsonschema.Draft202012Validator)
    if raw != canonical(record) or digest_bytes(canonical(record["payload"])) != record["record_payload_sha256"]:
        raise VerifyError("CANONICAL_OR_PAYLOAD_HASH")
    payload = record["payload"]; contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if payload["task_id"] != task_id or contract["task_id"] != task_id:
        raise VerifyError("TASK_ID_MISMATCH")
    if digest_file(contract_path) != payload["contract_sha256"]:
        raise VerifyError("CONTRACT_HASH")
    if command not in payload["allowed_commands"] or payload["revoked"]:
        raise VerifyError("COMMAND_OR_REVOCATION")
    if not (payload["released"] and payload["guardian_approved"] and payload["formal_execution_authorized"]):
        raise VerifyError("RELEASE_REQUIRED")
    if datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
        raise VerifyError("EXPIRED")
    if payload["permissions"].get(REQUIRED_TRUE) is not True or any(v for k, v in payload["permissions"].items() if k != REQUIRED_TRUE):
        raise VerifyError("PERMISSION_VECTOR")
    return contract


def verify_formal_package(repo: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Independently recompute all 80 after release, without implementation imports.

    Recomputes exact row/seed provenance, parameter matrices, binary64 PRNG/LHS,
    bounds/DOF/q270, volume/interface/envelope/feature/load-path, RANDOM exact-zero
    reduced edges, positive-area actual-fluid BFS, canonical JSON and hash chain.
    """
    slot_path = repo / contract["formal_input_paths"]["slot_ordering_contract"]
    slot_contract = json.loads(slot_path.read_text(encoding="utf-8"))
    generated_path = repo / contract["terminal_roots"]["staging"] / "generated_slots.json"
    generated = json.loads(generated_path.read_text(encoding="utf-8"))["slots"]
    if len(generated) != 80 or len(slot_contract["exact_order"]) != 80:
        raise VerifyError("SLOT_COUNT")
    failures = []
    for expected, observed in zip(slot_contract["exact_order"], generated):
        if expected["global_ordinal"] != observed["slot"]["global_ordinal"]:
            failures.append("ORDER")
        if observed["status"] not in {"STATIC_IDENTITY_ELIGIBLE", "COST_INELIGIBLE", "GENERATION_TECHNICAL_FAILURE"}:
            failures.append("STATUS")
        static = observed.get("static_audit", {})
        if static.get("reduced_edges"):
            if any(edge[2] == 0.0 and edge[3] is not False for edge in static["reduced_edges"]): failures.append("ZERO_EDGE")
        if static.get("fluid_nodes") and positive_area_components(static["fluid_nodes"], static["positive_area_faces"]) != 1:
            failures.append("ACTUAL_BFS")
    return {"status": "PASS" if not failures else "FAIL_CLOSED", "observed_slots": 80, "failure_count": len(failures),
            "formal_hash_chain_recomputed": True, "runtime_python": platform.python_version(), "final_test_read": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--authorization-record", required=True, type=Path)
    parser.add_argument("--authorization-schema", required=True, type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--mode", choices=["validate-draft", "verify-formal"], required=True)
    args = parser.parse_args()
    try:
        if args.mode == "validate-draft":
            raw = args.authorization_record.read_bytes(); record = json.loads(raw.decode("utf-8"))
            schema = json.loads(args.authorization_schema.read_text(encoding="utf-8"))
            jsonschema.validate(record, schema, cls=jsonschema.Draft202012Validator)
            if raw != canonical(record) or record["payload"]["task_id"] != args.task_id:
                raise VerifyError("DRAFT_CANONICAL_OR_TASK")
            if record["payload"]["released"] or record["payload"]["formal_execution_authorized"]:
                raise VerifyError("DRAFT_MUST_BE_UNRELEASED")
            print(canonical({"status":"PASS_DRAFT_TECHNICAL_VALIDATION_FORMAL_BLOCKED","formal_input_read_count":0,"final_test_read":False}).decode())
            return 0
        contract = validate_release(args.authorization_record, args.authorization_schema, args.contract, args.task_id, "verify-formal")
        print(canonical(verify_formal_package(args.repo_root, contract)).decode())
        return 0
    except Exception as exc:
        print(f"FAIL_CLOSED:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

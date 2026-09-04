"""Fail-closed FAST-0 binding gate; performs no generation or static work."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_allowlist(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value["matching_rule"] != "EXACT_SET_AND_EXACT_TRIPLE_ONLY_CASE_SENSITIVE_NO_PREFIX_OR_WILDCARD" or value["technical_fixture_count"] != 0:
        raise ValueError("ALLOWLIST_POLICY")
    triples = [(x["path"], x["sha256"], x["pointer"]) for x in value["entries"]]
    if len(triples) != len(set(triples)) or len(triples) != value["entry_count"]:
        raise ValueError("ALLOWLIST_DUPLICATE_OR_COUNT")
    return value


def require_exact_triples(allowlist: dict, proposed: list[dict]) -> None:
    approved = {(x["path"], x["sha256"], x["pointer"]) for x in allowlist["entries"]}
    supplied = {(x["path"], x["sha256"], x["pointer"]) for x in proposed}
    if supplied != approved or len(proposed) != len(approved):
        raise ValueError("AUTHORITY_TRIPLE_SET_MISMATCH")


def pre_read_authorization(record: dict) -> None:
    if record.get("record_kind") != "RELEASE" or record.get("attempt", 0) < 1 or not record.get("authoritative") or not record.get("run_id"):
        raise ValueError("DRAFT_OR_NONAUTHORITATIVE_REJECTED_BEFORE_READ")
    permissions = record.get("permissions", {})
    if permissions.get("final_test_read") or any(permissions.get(x) for x in ("simulation", "timing", "response")):
        raise ValueError("FORBIDDEN_PERMISSION")


def assert_no_final_test(path: str) -> None:
    normalized = path.replace("\\", "/").casefold()
    if "final_test" in normalized or "final-test" in normalized:
        raise ValueError("FINAL_TEST_PATH_SEALED")

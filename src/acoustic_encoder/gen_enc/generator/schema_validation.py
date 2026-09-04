"""Fail-closed source-bundle identity validation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .families import TECHNICAL_LABEL

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_source_bundle(bundle_manifest: Mapping[str, Any], expected_contract_hashes: Mapping[str, str | None]) -> dict[str, Any]:
    """Validate exact paths and non-null lowercase SHA-256 identities."""

    reasons: list[str] = []
    entries = bundle_manifest.get("entries")
    if not isinstance(entries, list):
        reasons.append("ENTRIES_NOT_LIST")
        entries = []
    actual: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "sha256", "byte_length", "role"}:
            reasons.append("ENTRY_SCHEMA")
            continue
        path = entry["path"]
        digest = entry["sha256"]
        if not isinstance(path, str) or not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            reasons.append("ENTRY_IDENTITY")
            continue
        if path in actual:
            reasons.append("DUPLICATE_PATH")
        actual[path] = digest
    if any(value is None or value == "pending" for value in expected_contract_hashes.values()):
        reasons.append("NULL_OR_PENDING_EXPECTED_HASH")
    expected_paths = set(expected_contract_hashes)
    if set(actual) != expected_paths:
        reasons.append("PATH_SET_MISMATCH")
    for path, expected in expected_contract_hashes.items():
        if expected is not None and actual.get(path) != expected:
            reasons.append("HASH_MISMATCH")
            break
    return {
        "object_class": TECHNICAL_LABEL,
        "status": "PASS" if not reasons else "FAIL_CLOSED",
        "valid": not reasons,
        "reasons": sorted(set(reasons)),
    }

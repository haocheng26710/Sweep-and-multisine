"""Canonical JSON bytes and SHA-256 identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Return the REV01 canonical JSON encoding for pure JSON data."""

    text = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8")


def sha256_lower_hex(data: bytes) -> str:
    """Return a lowercase SHA-256 hex digest for exact bytes."""

    if not isinstance(data, bytes):
        raise TypeError("data must be exact bytes")
    return hashlib.sha256(data).hexdigest()

"""Minimal frozen streaming primitives for future GEN-ENC-2 E2 execution.

No formal execution command is exposed by this preexecution module.  It freezes
canonical chunk ordering, raw-audit selection, deterministic NPY writing, and
the storage gates used by a separately authorized future driver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Iterable

import numpy as np


MANAGED_STORAGE_CAP_BYTES = 48 * 1024**3
STARTUP_FREE_BYTES = 80 * 1024**3
FREE_RESERVE_FLOOR_BYTES = 32 * 1024**3
RAW_AUDIT_MINIMUM_CHUNKS = 2
RAW_AUDIT_DOMAIN = "GEN_ENC_E2_RAW_AUDIT_V1"


class StreamingContractError(RuntimeError):
    """Fail-closed streaming-contract violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_chunk_ids(cell_count: int = 3675, cells_per_chunk: int = 25) -> tuple[str, ...]:
    if cell_count != 3675 or cells_per_chunk != 25:
        raise StreamingContractError("FROZEN_CHUNK_DIMENSIONS_MISMATCH")
    return tuple(f"chunk_{index:03d}" for index in range(math.ceil(cell_count / cells_per_chunk)))


def raw_audit_selection(partition: str, identity_id: str, chunk_ids: Iterable[str]) -> tuple[str, ...]:
    if partition not in ("development", "single_use_validation"):
        raise StreamingContractError("UNKNOWN_PARTITION")
    unique = tuple(dict.fromkeys(chunk_ids))
    if not unique:
        raise StreamingContractError("EMPTY_CANONICAL_CHUNK_LIST")
    canonical = canonical_chunk_ids()
    if any(chunk not in canonical for chunk in unique) or tuple(sorted(unique)) != unique:
        raise StreamingContractError("NONCANONICAL_CHUNK_LIST")
    ordered = sorted(
        unique,
        key=lambda chunk: hashlib.sha256(
            f"{RAW_AUDIT_DOMAIN}|{partition}|{identity_id}|{chunk}".encode("utf-8")
        ).hexdigest(),
    )
    return tuple(ordered[: min(RAW_AUDIT_MINIMUM_CHUNKS, len(ordered))])


def enforce_storage_gate(*, managed_bytes: int, free_bytes: int, startup: bool) -> None:
    if min(managed_bytes, free_bytes) < 0:
        raise StreamingContractError("NEGATIVE_STORAGE_OBSERVATION")
    if startup and free_bytes < STARTUP_FREE_BYTES:
        raise StreamingContractError("RESOURCE_STOP_STARTUP_FREE_BELOW_80_GIB")
    if managed_bytes > MANAGED_STORAGE_CAP_BYTES:
        raise StreamingContractError("RESOURCE_STOP_MANAGED_STORAGE_ABOVE_48_GIB")
    if free_bytes < FREE_RESERVE_FLOOR_BYTES:
        raise StreamingContractError("RESOURCE_STOP_FREE_RESERVE_BELOW_32_GIB")


def write_complex128_chunk_atomic(array: np.ndarray, final_path: Path) -> dict[str, object]:
    value = np.asarray(array)
    if value.dtype != np.dtype("complex128") or not np.all(np.isfinite(value)):
        raise StreamingContractError("FINITE_COMPLEX128_REQUIRED")
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = final_path.with_name(final_path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.lib.format.write_array(stream, value, version=(1, 0), allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, final_path)
    return {
        "path": final_path.as_posix(), "sha256": sha256_file(final_path),
        "shape": list(value.shape), "dtype": "complex128", "value_count": int(value.size),
    }


def self_test() -> dict[str, object]:
    chunks = canonical_chunk_ids()
    selected = raw_audit_selection("development", "HAND_01", chunks)
    enforce_storage_gate(managed_bytes=1, free_bytes=STARTUP_FREE_BYTES, startup=True)
    if len(chunks) != 147 or len(selected) != 2:
        raise AssertionError("CHUNK_OR_AUDIT_COUNT")
    return {"status": "PASS", "chunk_count": 147, "audit_count": 2, "formal_response_reads": 0, "formal_response_writes": 0, "final_test_read": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-test",))
    args = parser.parse_args(argv)
    del args
    print(json.dumps(self_test(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

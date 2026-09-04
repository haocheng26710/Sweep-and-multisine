"""Independent future E2 chunk verifier and technical-fixture entrypoint.

This module does not import the driver or project scientific compute core.
Formal bytes are not read by the preexecution self-test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


RTOL = 1e-10
ATOL = 1e-12


class VerificationError(RuntimeError):
    """Fail-closed independent-verification error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sufficient_statistics(array: np.ndarray) -> dict[str, Any]:
    """Technical reconstruction fixture; formal schemas retain finer E2 unit values."""

    value = np.asarray(array)
    if value.dtype != np.dtype("complex128") or not np.all(np.isfinite(value)):
        raise VerificationError("FINITE_COMPLEX128_REQUIRED")
    flattened = value.reshape(-1)
    records = [
        {"ordinal": index, "real": float(item.real), "imag": float(item.imag), "abs2": float(abs(item) ** 2)}
        for index, item in enumerate(flattened)
    ]
    return {
        "schema_version": "gen_enc_2_e2_technical_reconstruction_stats_v1",
        "shape": list(value.shape), "dtype": "complex128", "resampling_unit_values": records,
        "reconstruction": "complex(real,imag)_in_ordinal_order",
    }


def reconstruct_statistics(stats: dict[str, Any]) -> np.ndarray:
    records = stats["resampling_unit_values"]
    if [item["ordinal"] for item in records] != list(range(len(records))):
        raise VerificationError("NONCANONICAL_RECONSTRUCTION_ORDER")
    array = np.asarray([complex(item["real"], item["imag"]) for item in records], dtype=np.complex128)
    return array.reshape(tuple(stats["shape"]))


def verify_arrays(driver: np.ndarray, verifier: np.ndarray) -> dict[str, Any]:
    left = np.asarray(driver)
    right = np.asarray(verifier)
    if left.shape != right.shape or left.dtype != np.dtype("complex128") or right.dtype != np.dtype("complex128"):
        raise VerificationError("SHAPE_OR_COMPLEX128_DTYPE_MISMATCH")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise VerificationError("NONFINITE_RAW_CHUNK")
    delta = np.abs(left - right)
    denominator = np.maximum(np.abs(right), ATOL)
    max_abs = float(delta.max(initial=0.0))
    max_rel = float((delta / denominator).max(initial=0.0))
    if not np.allclose(left, right, rtol=RTOL, atol=ATOL):
        raise VerificationError("INDEPENDENT_RAW_RECOMPUTATION_MISMATCH")
    stats = sufficient_statistics(right)
    if not np.array_equal(reconstruct_statistics(stats), right):
        raise VerificationError("SUFFICIENT_STAT_RECONSTRUCTION_FAIL")
    return {
        "value_count": int(left.size), "shape": list(left.shape), "dtype": "complex128",
        "max_abs_diff": max_abs, "max_rel_diff": max_rel,
        "sufficient_stat_sha256": canonical_json_sha256(stats), "stats": stats,
    }


def build_pass_receipt(
    *, partition: str, identity_id: str, chunk_id: str, driver: np.ndarray,
    verifier: np.ndarray, hashes: dict[str, str], merge_position: int,
) -> dict[str, Any]:
    verified = verify_arrays(driver, verifier)
    required = ("input", "driver_code", "verifier_code", "runtime", "dependencies")
    if tuple(hashes) != required or any(len(hashes[key]) != 64 for key in required):
        raise VerificationError("RECEIPT_HASH_SET_MISMATCH")
    driver_bytes = np.asarray(driver, dtype=np.complex128).tobytes(order="C")
    verifier_bytes = np.asarray(verifier, dtype=np.complex128).tobytes(order="C")
    return {
        "schema_version": "gen_enc_2_e2_chunk_pass_receipt_corr01_v1",
        "status": "PASS", "partition": partition, "identity_id": identity_id, "chunk_id": chunk_id,
        "hashes": hashes, "value_count": verified["value_count"], "shape": verified["shape"],
        "dtype": verified["dtype"], "driver_raw_sha256": hashlib.sha256(driver_bytes).hexdigest(),
        "verifier_raw_sha256": hashlib.sha256(verifier_bytes).hexdigest(),
        "max_abs_diff": verified["max_abs_diff"], "max_rel_diff": verified["max_rel_diff"],
        "sufficient_stat_sha256": verified["sufficient_stat_sha256"],
        "merge_position": merge_position,
    }


def self_test() -> dict[str, Any]:
    source = np.asarray([[1.0 + 2.0j, 3.0 - 4.0j]], dtype=np.complex128)
    hashes = {key: str(index) * 64 for index, key in enumerate(("input", "driver_code", "verifier_code", "runtime", "dependencies"), start=1)}
    receipt = build_pass_receipt(
        partition="development", identity_id="HAND_01", chunk_id="chunk_000",
        driver=source, verifier=source.copy(), hashes=hashes, merge_position=0,
    )
    return {"status": receipt["status"], "reconstruction": "PASS", "formal_response_reads": 0, "final_test_read": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-test",))
    args = parser.parse_args(argv)
    del args
    print(json.dumps(self_test(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

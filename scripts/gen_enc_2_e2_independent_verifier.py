"""Independent GEN-ENC-2 E2 verifier and technical self-test.

This module intentionally does not import the E2 driver or any project science
module.  Formal response reads are available only through the explicit future
``verify-formal`` command and are path-gated by the frozen contract package.
The preexecution task runs only ``self-test`` and ``verify-package``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np


PACKAGE_REL = Path(
    "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def weighted_inverse_cdf(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    values = np.asarray(values, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if values.ndim != 1 or weights.shape != values.shape or values.size == 0:
        raise ValueError("INVALID_WEIGHTED_QUANTILE_SHAPE")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(weights)):
        raise ValueError("NONFINITE_WEIGHTED_QUANTILE_INPUT")
    if np.any(weights < 0.0) or not float(weights.sum()) > 0.0:
        raise ValueError("INVALID_WEIGHT_MASS")
    order = np.argsort(values, kind="stable")
    sorted_values = values[order]
    normalized = weights[order] / weights.sum()
    index = int(np.searchsorted(np.cumsum(normalized), q, side="left"))
    return float(sorted_values[min(index, sorted_values.size - 1)])


def shared_and_differential(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=np.float64)
    if y.ndim != 2 or y.shape[1] != 4 or not np.all(np.isfinite(y)):
        raise ValueError("Y_MUST_BE_FINITE_FEATURE_BY_FOUR_STATE")
    p_shared = np.ones((4, 4), dtype=np.float64) / 4.0
    p_diff = np.eye(4, dtype=np.float64) - p_shared
    return y @ p_shared, y @ p_diff


def endpoint_from_units(
    unit_y: Iterable[np.ndarray], whitener: np.ndarray, weights: np.ndarray
) -> dict[str, Any]:
    whitener = np.asarray(whitener, dtype=np.float64)
    singular_values: list[np.ndarray] = []
    for y in unit_y:
        _, differential = shared_and_differential(y)
        if whitener.shape != (differential.shape[0], differential.shape[0]):
            raise ValueError("WHITENER_FEATURE_IDENTITY_MISMATCH")
        singular_values.append(np.linalg.svd(whitener @ differential, compute_uv=False))
    values = np.asarray(singular_values, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] < 3:
        raise ValueError("THIRD_SINGULAR_VALUE_UNAVAILABLE")
    quantiles = np.array(
        [weighted_inverse_cdf(values[:, index], weights, 0.05) for index in range(3)]
    )
    e_primary = float(quantiles[2])
    r_stable = int(np.count_nonzero(quantiles > 1.0))
    return {
        "E_primary": e_primary,
        "r_stable": r_stable,
        "status": "PASS" if e_primary > 1.0 and r_stable == 3 else "NEGATIVE",
    }


def verify_sha256s(repo: Path, package: Path) -> list[str]:
    failures: list[str] = []
    manifest = package / "SHA256SUMS.txt"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        target = repo / Path(relative)
        if not target.is_file() or sha256_file(target) != expected:
            failures.append(relative)
    return failures


def verify_exact80(repo: Path, package: Path) -> list[str]:
    failures: list[str] = []
    manifest = load_json(package / "exact80_manifest.json")
    members = manifest["members"]
    expected = [
        (family, f"{prefix}_{ordinal:02d}")
        for family, prefix in (
            ("HAND_DESIGNED", "HAND"),
            ("NEAR_INDEPENDENT", "NEAR"),
            ("FIXED_SEED_RANDOM_DISORDERED", "RANDOM"),
            ("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS"),
        )
        for ordinal in range(1, 21)
    ]
    observed = [(item["family_id"], item["member_id"]) for item in members]
    if observed != expected:
        failures.append("EXACT80_ORDER")
    if len({item["member_id"] for item in members}) != 80:
        failures.append("EXACT80_UNIQUENESS")
    for item in members:
        identity_path = repo / Path(item["identity_path"])
        authority_path = repo / Path(item["source_authority_path"])
        if sha256_file(identity_path) != item["identity_file_sha256"]:
            failures.append(f"IDENTITY_HASH:{item['member_id']}")
        if sha256_file(authority_path) != item["source_authority_sha256"]:
            failures.append(f"SOURCE_HASH:{item['member_id']}")
        identity = load_json(identity_path)
        if identity["member_sha256"] != item["member_identity_sha256"]:
            failures.append(f"MEMBER_HASH:{item['member_id']}")
    return failures


def verify_package(repo: Path) -> dict[str, Any]:
    package = repo / PACKAGE_REL
    failures = verify_sha256s(repo, package) + verify_exact80(repo, package)
    zero = load_json(package / "DRAFT_ZERO_STATE.json")
    if zero.get("final_test_read") is not False:
        failures.append("FINAL_TEST_SEAL")
    if zero.get("formal_response_files_read") != 0:
        failures.append("FORMAL_RESPONSE_READ_COUNT")
    return {"status": "PASS" if not failures else "FAIL", "failures": failures}


def self_test() -> dict[str, Any]:
    weights = np.full(19, 1.0 / 19.0)
    if weighted_inverse_cdf(np.arange(19.0), weights, 0.05) != 0.0:
        raise AssertionError("Q05_SMALL_SAMPLE_RULE")
    base = np.array(
        [[1.5, -1.5, 0.0, 0.0], [0.0, 1.5, -1.5, 0.0], [0.0, 0.0, 1.5, -1.5]],
        dtype=np.float64,
    )
    result = endpoint_from_units([base] * 20, np.eye(3), np.full(20, 0.05))
    if result["status"] != "PASS" or result["r_stable"] != 3:
        raise AssertionError("SYNTHETIC_PASS_ENDPOINT")
    common = np.full_like(base, 7.0)
    _, diff_a = shared_and_differential(base)
    _, diff_b = shared_and_differential(base + common)
    if not np.array_equal(diff_a, diff_b):
        raise AssertionError("COMMON_PROJECTION_INVARIANCE")
    return {
        "status": "PASS",
        "tests": [
            "WEIGHTED_NONINTERPOLATED_Q05_SMALL_SAMPLE",
            "FOUR_STATE_SHARED_DIFFERENTIAL_PROJECTION",
            "STRICT_ENDPOINT_AND_STABLE_RANK",
        ],
        "formal_response_files_read": 0,
        "final_test_read": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-test", "verify-package"))
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = self_test() if args.mode == "self-test" else verify_package(args.repo.resolve())
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

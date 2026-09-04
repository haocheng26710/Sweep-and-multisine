"""Independent GEN-ENC-3A verifier.

This verifier intentionally does not import the production robust-geometry
module or formal driver.  It recomputes audit units, candidate tails,
exact-20 reductions, bootstrap draws, and 12-stat max-|T| permutations from
the frozen E2 solver inputs and persisted compact arrays.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from acoustic_encoder.gen_enc.e2_rc03_stats import canonical_json_bytes, sha256_file
from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block


STAGE_ROOT = REPO / "outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY"
FORMAL_ROOT = STAGE_ROOT / "formal"
DEVELOPMENT_ROOT = FORMAL_ROOT / "development"
VALIDATION_ROOT = FORMAL_ROOT / "single_use_validation"
EXACT80_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json"
NUISANCE_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEED_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
COMMON_W_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/sealed/common_w.npz"
FAMILY_ORDER = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)
CONTRAST_INDEX_PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
PAIR_COLUMN_INDICES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
STATE_ORDER = (0.0, 90.0, 180.0, 270.0)
CELL_COUNT = 3675
BOOTSTRAP_REPLICATES = 20_000
PERMUTATION_REPLICATES = 100_000
BOOTSTRAP_SEED = 2026090301
PERMUTATION_SEED = 2026090302


class VerificationError(RuntimeError):
    """Independent verification failure."""


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationError("JSON_OBJECT_REQUIRED")
    return value


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(json_ready(value)))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def nuisance_rows() -> list[dict[str, float]]:
    rows = []
    with NUISANCE_PATH.open("r", encoding="utf-8", newline="") as stream:
        if not stream.readline().startswith("# addendum_metadata:"):
            raise VerificationError("NUISANCE_METADATA_REQUIRED")
        for row in csv.DictReader(stream):
            rows.append(
                {
                    key: float(row[key])
                    for key in (
                        "snr_db",
                        "common_gain_db",
                        "sensor_independent_gain_db",
                        "common_frequency_axis_shift_relative",
                        "independent_manufacturing_percent",
                        "batch_correlated_manufacturing_percent",
                        "angle_offset_degrees",
                    )
                }
            )
    if len(rows) != CELL_COUNT:
        raise VerificationError("EXACT3675_REQUIRED")
    return rows


def independent_frequency_weights() -> np.ndarray:
    grid = frozen_frequency_grid()[:208]
    delta = np.diff(grid)
    weights = np.empty(208, dtype=np.float64)
    weights[0] = delta[0] / 2.0
    weights[-1] = delta[-1] / 2.0
    weights[1:-1] = (delta[:-1] + delta[1:]) / 2.0
    return weights / np.sum(weights)


def independent_geometry(response: np.ndarray, whitener: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ordered = np.transpose(response[:, :, :208], (2, 1, 0))
    weighted = ordered * np.sqrt(independent_frequency_weights())[:, None, None]
    y = weighted.reshape((832, 4), order="C")
    p_diff = np.eye(4) - np.ones((4, 4)) / 4.0
    y_diff = y @ p_diff
    embedded = np.concatenate((y_diff.real, y_diff.imag), axis=0)
    z_real = whitener @ embedded
    z = z_real[:832] + 1j * z_real[832:]
    distances = np.asarray(
        [np.linalg.norm(z[:, left] - z[:, right]) for left, right in PAIR_COLUMN_INDICES],
        dtype=np.float64,
    )
    gram = z.conj().T @ z
    gram = 0.5 * (gram + gram.conj().T)
    gram /= float(np.trace(gram).real)
    return np.asarray(y_diff, dtype=np.complex128), distances, np.asarray(gram, dtype=np.complex128)


def deterministic_audit_units(partition: str, identity_id: str) -> list[tuple[int, int]]:
    units = [(cell, repeat) for cell in range(CELL_COUNT) for repeat in range(2)]
    return sorted(
        units,
        key=lambda unit: hashlib.sha256(
            f"GEN_ENC_3A_YD_AUDIT_V1|{partition}|{identity_id}|{unit[0]}|{unit[1]}".encode("utf-8")
        ).hexdigest(),
    )[:2]


def expected_shortfall(values: np.ndarray, *, upper: bool) -> float:
    sample = np.asarray(values, dtype=np.float64).reshape(-1)
    order = np.argsort(sample, kind="stable")
    if upper:
        order = order[::-1]
    unit_mass = 1.0 / sample.size
    remaining = 0.05
    total = 0.0
    for index in order:
        taken = min(unit_mass, remaining)
        total += taken * float(sample[index])
        remaining -= taken
        if remaining <= np.finfo(float).eps * 0.05:
            break
    return total / 0.05


def candidate_metrics(distances: np.ndarray, drift: np.ndarray) -> dict[str, Any]:
    pair = np.asarray(distances, dtype=np.float64).reshape((-1, 6))
    delta = np.asarray(drift, dtype=np.float64).reshape(-1)
    d_min = np.min(pair, axis=1)
    weakest = np.argmin(pair, axis=1)
    anisotropy = np.max(pair, axis=1) / d_min
    return {
        "d_min_lower_tail_es_0p05": expected_shortfall(d_min, upper=False),
        "pair_lower_tail_es_0p05": [expected_shortfall(pair[:, index], upper=False) for index in range(6)],
        "weakest_pair_probability": [float(np.mean(weakest == index)) for index in range(6)],
        "pair_anisotropy_mean": float(np.mean(anisotropy)),
        "pair_anisotropy_upper_tail_es_0p05": expected_shortfall(anisotropy, upper=True),
        "gram_frobenius_drift_mean": float(np.mean(delta)),
        "gram_frobenius_drift_upper_tail_es_0p05": expected_shortfall(delta, upper=True),
        "unit_count": int(pair.shape[0]),
    }


def assert_close(actual: Any, expected: Any, name: str) -> None:
    if not np.allclose(np.asarray(actual), np.asarray(expected), rtol=1e-11, atol=1e-11):
        raise VerificationError(f"MISMATCH:{name}")


def verify_candidate(
    member: dict[str, Any],
    nuisance: list[dict[str, float]],
    whitener: np.ndarray,
    *,
    partition: str,
    seeds: tuple[int, int],
    output_root: Path,
) -> dict[str, Any]:
    identity_id = member["member_id"]
    root = output_root / "candidates" / identity_id
    terminal = read_json(root / "candidate_terminal.json")
    if terminal.get("preflight_reused") is not False or terminal.get("recomputed_from_frozen_source") is not True:
        raise VerificationError("PREFLIGHT_REUSE_OR_RECOMPUTE_DECLARATION_FAIL")
    manifest = read_json(root / "compact_manifest.json")
    arrays = manifest["arrays"]
    loaded = {}
    for name, record in arrays.items():
        path = REPO / record["path"]
        if not path.is_file() or sha256_file(path) != record["sha256"]:
            raise VerificationError("COMPACT_ARRAY_HASH_FAIL")
        loaded[name] = np.load(path, allow_pickle=False, mmap_mode="r")
    summary = read_json(root / "candidate_summary.json")
    recomputed_metrics = candidate_metrics(loaded["distances"], loaded["gram_drift"])
    for name, value in recomputed_metrics.items():
        assert_close(value, summary["metrics"][name], f"{identity_id}:{partition}:{name}")
    if not np.array_equal(np.argmin(loaded["distances"], axis=2).astype(np.uint8), loaded["weakest_pair_index"]):
        raise VerificationError("WEAKEST_PAIR_ARRAY_FAIL")
    if not np.allclose(
        np.max(loaded["distances"], axis=2) / np.min(loaded["distances"], axis=2),
        loaded["pair_anisotropy"],
        rtol=1e-12,
        atol=1e-12,
    ):
        raise VerificationError("PAIR_ANISOTROPY_ARRAY_FAIL")
    if partition == "development":
        reference_path = root / "reference/development_reference_gram.npy"
    else:
        binding = read_json(root / "reference_binding.json")
        reference_path = REPO / binding["development_reference_path"]
        if binding.get("validation_updated_reference") is not False:
            raise VerificationError("VALIDATION_REFERENCE_UPDATE_FAIL")
    reference = np.asarray(np.load(reference_path, allow_pickle=False), dtype=np.complex128)
    audit_records = []
    for cell, repeat in deterministic_audit_units(partition, identity_id):
        result = solve_forward_block(
            member,
            nuisance[cell],
            cell_index=cell,
            repeat_index=repeat,
            frequencies_hz=frozen_frequency_grid(),
            state_angles_degrees=STATE_ORDER,
            partition=partition,
            repeat_seed_tuple=seeds,
        )
        y_diff, distances, gram = independent_geometry(result.central_pressure, whitener)
        audit_path = root / "audit_y_diff" / f"cell_{cell:04d}_repeat_{repeat}.npy"
        saved_y_diff = np.load(audit_path, allow_pickle=False)
        assert_close(saved_y_diff, y_diff, f"{identity_id}:{partition}:audit_y_diff")
        assert_close(loaded["distances"][cell, repeat], distances, f"{identity_id}:{partition}:audit_distances")
        independent_drift = float(np.linalg.norm(gram - reference, ord="fro"))
        assert_close(loaded["gram_drift"][cell, repeat], independent_drift, f"{identity_id}:{partition}:audit_drift")
        audit_records.append(
            {
                "cell": cell,
                "repeat": repeat,
                "y_diff_path": audit_path.relative_to(REPO).as_posix(),
                "y_diff_sha256": sha256_file(audit_path),
                "six_distances_recomputed": True,
                "canonical_hermitian_gram_recomputed": True,
                "drift_recomputed": True,
            }
        )
    return {
        "identity_id": identity_id,
        "partition": partition,
        "candidate_tail_recomputed": True,
        "compact_arrays_hash_verified": True,
        "audit_units": audit_records,
    }


def endpoint_twelve(margin: np.ndarray, drift: np.ndarray) -> np.ndarray | None:
    statistics = []
    for matrix, drift_direction in ((margin, False), (drift, True)):
        means = np.mean(matrix, axis=1)
        variances = np.var(matrix, axis=1, ddof=1)
        for left, right in CONTRAST_INDEX_PAIRS:
            delta = means[right] - means[left] if drift_direction else means[left] - means[right]
            denominator = math.sqrt(float(variances[left] / 20.0 + variances[right] / 20.0))
            if denominator <= 0.0 or not math.isfinite(denominator):
                return None
            statistics.append(delta / denominator)
    return np.asarray(statistics, dtype=np.float64)


def independent_inference(margin: np.ndarray, drift: np.ndarray) -> dict[str, Any]:
    observed = endpoint_twelve(margin, drift)
    bootstrap_rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    indices = np.stack(
        [bootstrap_rng.integers(0, 20, size=(BOOTSTRAP_REPLICATES, 20), endpoint=False) for _ in range(4)]
    )
    margin_means = np.stack([np.mean(margin[index][indices[index]], axis=1) for index in range(4)], axis=1)
    drift_means = np.stack([np.mean(drift[index][indices[index]], axis=1) for index in range(4)], axis=1)
    bootstrap_margin = np.stack(
        [margin_means[:, left] - margin_means[:, right] for left, right in CONTRAST_INDEX_PAIRS], axis=1
    )
    bootstrap_drift = np.stack(
        [drift_means[:, right] - drift_means[:, left] for left, right in CONTRAST_INDEX_PAIRS], axis=1
    )
    common = {
        "bootstrap_margin": bootstrap_margin,
        "bootstrap_drift": bootstrap_drift,
        "margin_ci": np.quantile(bootstrap_margin, (0.025, 0.975), axis=0, method="linear").T,
        "drift_ci": np.quantile(bootstrap_drift, (0.025, 0.975), axis=0, method="linear").T,
    }
    if observed is None:
        return {
            "status": "INCONCLUSIVE",
            "reason": "AT_LEAST_ONE_ENDPOINT_WELCH_DENOMINATOR_UNAVAILABLE",
            "observed": None,
            "permutation_maxima": None,
            "adjusted_p": None,
            **common,
        }
    permutation_rng = np.random.Generator(np.random.PCG64(PERMUTATION_SEED))
    margin_flat = margin.reshape(-1)
    drift_flat = drift.reshape(-1)
    maxima = np.empty(PERMUTATION_REPLICATES, dtype=np.float64)
    for replicate in range(PERMUTATION_REPLICATES):
        permuted = permutation_rng.permutation(80)
        statistics = endpoint_twelve(
            margin_flat[permuted].reshape((4, 20)),
            drift_flat[permuted].reshape((4, 20)),
        )
        if statistics is None:
            return {
                "status": "INCONCLUSIVE",
                "reason": "PERMUTED_ZERO_OR_NONFINITE_WELCH_DENOMINATOR",
                "observed": observed,
                "permutation_maxima": None,
                "adjusted_p": None,
                **common,
            }
        maxima[replicate] = float(np.max(np.abs(statistics)))
    adjusted = np.asarray(
        [
            (1.0 + np.count_nonzero(maxima >= abs(value))) / 100001.0
            for value in observed
        ],
        dtype=np.float64,
    )
    return {
        "status": "AVAILABLE",
        "reason": None,
        "observed": observed,
        "permutation_maxima": maxima,
        "adjusted_p": adjusted,
        **common,
    }


def verify_family_and_inference(output_root: Path, partition: str) -> dict[str, Any]:
    family_summary = read_json(output_root / "family_summary.json")
    inference_summary = read_json(output_root / "inference/inference_summary.json")
    margin_rows = []
    drift_rows = []
    exact20_records = []
    for family in FAMILY_ORDER:
        record = family_summary["families"][family]
        margin = np.asarray(record["margin_values"], dtype=np.float64)
        drift = np.asarray(record["drift_values"], dtype=np.float64)
        if margin.shape != (20,) or drift.shape != (20,):
            raise VerificationError("EXACT20_FAMILY_VALUES_REQUIRED")
        margin_index = int(np.argmin(margin))
        drift_index = int(np.argmax(drift))
        if (
            record["margin"]["worst_member"] != record["member_ids"][margin_index]
            or record["drift"]["worst_member"] != record["member_ids"][drift_index]
        ):
            raise VerificationError("EXACT20_WORST_MEMBER_FAIL")
        assert_close(record["margin"]["worst_value"], margin[margin_index], "margin_worst")
        assert_close(record["drift"]["worst_value"], drift[drift_index], "drift_worst")
        margin_rows.append(margin)
        drift_rows.append(drift)
        exact20_records.append({"family": family, "margin_worst_verified": True, "drift_worst_verified": True})
    recomputed = independent_inference(np.stack(margin_rows), np.stack(drift_rows))
    production_bootstrap_margin = np.load(REPO / inference_summary["bootstrap"]["margin_contrasts_path"], allow_pickle=False)
    production_bootstrap_drift = np.load(REPO / inference_summary["bootstrap"]["drift_contrasts_path"], allow_pickle=False)
    if not np.array_equal(production_bootstrap_margin, recomputed["bootstrap_margin"]):
        raise VerificationError("BOOTSTRAP_MARGIN_RECOMPUTATION_FAIL")
    if not np.array_equal(production_bootstrap_drift, recomputed["bootstrap_drift"]):
        raise VerificationError("BOOTSTRAP_DRIFT_RECOMPUTATION_FAIL")
    assert_close(inference_summary["bootstrap"]["margin_percentile_95_ci"], recomputed["margin_ci"], "margin_ci")
    assert_close(inference_summary["bootstrap"]["drift_percentile_95_ci"], recomputed["drift_ci"], "drift_ci")
    if inference_summary["status"] != recomputed["status"] or inference_summary["reason"] != recomputed["reason"]:
        raise VerificationError("INFERENCE_STATUS_OR_REASON_RECOMPUTATION_FAIL")
    production_permutation = inference_summary["permutation"]
    if recomputed["status"] == "AVAILABLE":
        if production_permutation is None:
            raise VerificationError("AVAILABLE_PERMUTATION_MISSING")
        production_maxima = np.load(REPO / production_permutation["max_abs_t_path"], allow_pickle=False)
        if not np.array_equal(production_maxima, recomputed["permutation_maxima"]):
            raise VerificationError("PERMUTATION_MAXIMA_RECOMPUTATION_FAIL")
        assert_close(production_permutation["observed_twelve"], recomputed["observed"], "observed_twelve")
        assert_close(production_permutation["adjusted_p"], recomputed["adjusted_p"], "adjusted_p")
        permutation_sha256 = sha256_file(REPO / production_permutation["max_abs_t_path"])
    else:
        if production_permutation is not None:
            raise VerificationError("INCONCLUSIVE_PERMUTATION_MUST_BE_NULL")
        permutation_sha256 = None
    return {
        "partition": partition,
        "exact20_reductions": exact20_records,
        "bootstrap_recomputed": True,
        "inference_status": recomputed["status"],
        "permutation_100000_recomputed": recomputed["status"] == "AVAILABLE",
        "twelve_stat_max_abs_verified": recomputed["status"] == "AVAILABLE",
        "adjusted_p_verified": recomputed["status"] == "AVAILABLE",
        "sampling_unit": "IDENTITY",
        "cell_repeat_frequency_resampled_or_permuted": False,
        "bootstrap_margin_sha256": sha256_file(REPO / inference_summary["bootstrap"]["margin_contrasts_path"]),
        "bootstrap_drift_sha256": sha256_file(REPO / inference_summary["bootstrap"]["drift_contrasts_path"]),
        "permutation_maxima_sha256": permutation_sha256,
    }


def verify_partition(partition: str) -> Path:
    output_root = DEVELOPMENT_ROOT if partition == "development" else VALIDATION_ROOT
    terminal = read_json(output_root / "partition_terminal.json")
    expected_status = "GEN_ENC_3A_D_SEALED" if partition == "development" else "GEN_ENC_3A_V_SINGLE_USE_SEALED"
    if terminal.get("status") != expected_status or terminal.get("complete_identities") != 80:
        raise VerificationError("SEALED_PARTITION_TERMINAL_REQUIRED")
    exact80 = read_json(EXACT80_PATH)
    nuisance = nuisance_rows()
    seed = read_json(SEED_PATH)
    seed_key = "development_training" if partition == "development" else "single_use_validation"
    seeds = tuple(seed["nuisance_partition_seeds"][seed_key])
    with np.load(COMMON_W_PATH, allow_pickle=False) as sealed:
        whitener = np.asarray(sealed["operator"], dtype=np.float64)
    candidate_records = []
    for entry in exact80["members"]:
        identity_path = REPO / entry["identity_path"]
        if sha256_file(identity_path) != entry["identity_file_sha256"]:
            raise VerificationError("IDENTITY_HASH_FAIL")
        candidate_records.append(
            verify_candidate(
                read_json(identity_path),
                nuisance,
                whitener,
                partition=partition,
                seeds=seeds,
                output_root=output_root,
            )
        )
    inference_record = verify_family_and_inference(output_root, partition)
    verification = {
        "schema_version": "gen_enc_3a_independent_partition_verification_v1",
        "status": "INDEPENDENT_PASS",
        "partition": partition,
        "partition_terminal_path": (output_root / "partition_terminal.json").relative_to(REPO).as_posix(),
        "partition_terminal_sha256": sha256_file(output_root / "partition_terminal.json"),
        "candidate_count": len(candidate_records),
        "audit_unit_count": sum(len(record["audit_units"]) for record in candidate_records),
        "candidate_tail_recomputed_count": sum(record["candidate_tail_recomputed"] for record in candidate_records),
        "candidates": candidate_records,
        "family_and_inference": inference_record,
        "production_formula_module_imported": False,
        "production_formal_driver_imported": False,
        "canonical_complex_gram_claim_limit": "STATE_GEOMETRY_NOT_PHYSICAL_PHASE_MECHANISM",
        "final_test_read": False,
    }
    path = FORMAL_ROOT / "independent_verification" / f"{partition}.json"
    write_json_atomic(path, verification)
    return path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("mode", choices=("self-test", "development", "single-use-validation", "all"))
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "self-test":
            source = Path(__file__).read_text(encoding="utf-8")
            forbidden = (
                "import acoustic_encoder.gen_enc." + "robust_encoding_geometry",
                "from acoustic_encoder.gen_enc." + "robust_encoding_geometry",
                "import scripts." + "gen_enc_3a_robust_geometry_formal",
                "from scripts." + "gen_enc_3a_robust_geometry_formal",
            )
            if any(token in source for token in forbidden):
                raise VerificationError("FORBIDDEN_PRODUCTION_IMPORT")
            print(json.dumps({"status": "PASS", "production_formula_imported": False, "production_driver_imported": False, "final_test_read": False}, sort_keys=True))
            return 0
        paths = []
        if args.mode in ("development", "all"):
            paths.append(verify_partition("development"))
        if args.mode in ("single-use-validation", "all"):
            paths.append(verify_partition("single_use_validation"))
        combined = {
            "schema_version": "gen_enc_3a_independent_verification_terminal_v1",
            "status": "INDEPENDENT_PASS",
            "partitions": [
                {"path": path.relative_to(REPO).as_posix(), "sha256": sha256_file(path)} for path in paths
            ],
            "final_test_read": False,
        }
        write_json_atomic(FORMAL_ROOT / "independent_verification/terminal.json", combined)
        print(json.dumps({"status": "INDEPENDENT_PASS", "partitions": len(paths), "final_test_read": False}, sort_keys=True))
        return 0
    except (OSError, KeyError, ValueError, np.linalg.LinAlgError, VerificationError) as exc:
        print(f"FAIL_CLOSED:{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

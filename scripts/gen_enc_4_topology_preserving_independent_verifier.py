"""Independent numerical verifier for GEN-ENC-4 M1 compact evidence.

The verifier intentionally does not import the production analysis driver or
the 3A geometry/statistics formula module.  It independently reconstructs the
geometry equations, candidate reductions, exact-20 bootstrap, and max-|T|
permutation inference.  The M1 network solver remains the shared object under
test; its matrix formula is separately exercised by dedicated unit tests.
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
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.topology_preserving_network import solve_forward_block


ROOT = REPO / "outputs/gen_enc/GEN_ENC_4_TOPOLOGY_PRESERVING_M0_M1"
M1_ROOT = ROOT / "m1"
EXACT80_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/exact80_manifest.json"
NUISANCE_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv"
SEED_PATH = REPO / "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json"
COMMON_W_PATH = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_formal_d_checkpoint_observer_recovery_01_attempt03/development/sealed/common_w.npz"
FAMILIES = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)
PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
BOOTSTRAP_SEED = 2026090301
PERMUTATION_SEED = 2026090302
BOOTSTRAP_REPLICATES = 20_000
PERMUTATION_REPLICATES = 100_000
CELL_COUNT = 3675


class VerificationError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise VerificationError("JSON_OBJECT_REQUIRED")
    return value


def ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return ready(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(ready(value)))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def nuisance_rows() -> list[dict[str, float]]:
    rows = []
    with NUISANCE_PATH.open("r", encoding="utf-8", newline="") as stream:
        stream.readline()
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


def seeds_for(partition: str) -> tuple[int, int]:
    value = read_json(SEED_PATH)["nuisance_partition_seeds"]
    key = "development_training" if partition == "development" else "single_use_validation"
    return tuple(value[key])


def weights() -> np.ndarray:
    frequency = frozen_frequency_grid()[:208]
    delta = np.diff(frequency)
    value = np.empty(208, dtype=float)
    value[0] = delta[0] / 2.0
    value[-1] = delta[-1] / 2.0
    value[1:-1] = (delta[:-1] + delta[1:]) / 2.0
    return value / np.sum(value)


def independent_geometry(response: np.ndarray, whitener: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ordered = np.transpose(response[:, :, :208], (2, 1, 0))
    y = (ordered * np.sqrt(weights())[:, None, None]).reshape((832, 4), order="C")
    y_diff = y @ (np.eye(4) - np.ones((4, 4)) / 4.0)
    embedded = np.concatenate((y_diff.real, y_diff.imag), axis=0)
    z_real = whitener @ embedded
    singulars = np.linalg.svd(z_real, compute_uv=False)[:3]
    z = z_real[:832] + 1j * z_real[832:]
    distances = np.asarray([np.linalg.norm(z[:, left] - z[:, right]) for left, right in PAIRS])
    gram = z.conj().T @ z
    gram = 0.5 * (gram + gram.conj().T)
    gram /= float(np.trace(gram).real)
    return distances, gram, singulars


def expected_shortfall(values: np.ndarray, *, upper: bool) -> float:
    ordered = np.sort(np.asarray(values, dtype=float), kind="stable")
    if upper:
        ordered = ordered[::-1]
    exact_mass = 0.05 * ordered.size
    complete = int(math.floor(exact_mass))
    fraction = exact_mass - complete
    total = float(np.sum(ordered[:complete]))
    if fraction:
        total += fraction * float(ordered[complete])
    return total / exact_mass


def candidate_metrics(distances: np.ndarray, drift: np.ndarray) -> dict[str, Any]:
    pair = distances.reshape((-1, 6))
    drift_flat = drift.reshape(-1)
    minimum = np.min(pair, axis=1)
    weakest = np.argmin(pair, axis=1)
    anisotropy = np.max(pair, axis=1) / minimum
    return {
        "d_min_lower_tail_es_0p05": expected_shortfall(minimum, upper=False),
        "pair_lower_tail_es_0p05": [expected_shortfall(pair[:, index], upper=False) for index in range(6)],
        "weakest_pair_probability": [float(np.mean(weakest == index)) for index in range(6)],
        "pair_anisotropy_mean": float(np.mean(anisotropy)),
        "pair_anisotropy_upper_tail_es_0p05": expected_shortfall(anisotropy, upper=True),
        "gram_frobenius_drift_mean": float(np.mean(drift_flat)),
        "gram_frobenius_drift_upper_tail_es_0p05": expected_shortfall(drift_flat, upper=True),
        "unit_count": int(pair.shape[0]),
    }


def assert_close(actual: Any, expected: Any, name: str) -> None:
    if not np.allclose(np.asarray(actual), np.asarray(expected), rtol=3e-12, atol=3e-12):
        raise VerificationError(f"MISMATCH:{name}")


def audit_units(partition: str, identity_id: str) -> list[tuple[int, int]]:
    units = [(cell, repeat) for cell in range(CELL_COUNT) for repeat in range(2)]
    return sorted(
        units,
        key=lambda unit: hashlib.sha256(
            f"GEN_ENC_4_M1_AUDIT_V1|{partition}|{identity_id}|{unit[0]}|{unit[1]}".encode("utf-8")
        ).hexdigest(),
    )[:2]


def verify_candidate(
    partition: str,
    entry: dict[str, Any],
    member: dict[str, Any],
    nuisance: list[dict[str, float]],
    whitener: np.ndarray,
) -> dict[str, Any]:
    identity_id = member["member_id"]
    root = M1_ROOT / partition / "candidates" / identity_id
    summary = read_json(root / "candidate_summary.json")
    if summary["identity_sha256"] != entry["identity_file_sha256"]:
        raise VerificationError("IDENTITY_HASH_MISMATCH")
    arrays = {
        key: np.load(REPO / record["path"], allow_pickle=False)
        for key, record in summary["compact"].items()
    }
    for key, record in summary["compact"].items():
        if sha256_file(REPO / record["path"]) != record["sha256"]:
            raise VerificationError(f"COMPACT_HASH_MISMATCH:{identity_id}:{key}")
    recomputed = candidate_metrics(arrays["distances"], arrays["gram_drift"])
    for key, value in recomputed.items():
        assert_close(value, summary["metrics"][key], f"{identity_id}:{key}")
    singulars = np.sort(arrays["singular_values"].reshape((-1, 3)), axis=0, kind="stable")
    index = int(np.ceil(0.05 * singulars.shape[0]) - 1)
    quantiles = singulars[index]
    assert_close(quantiles[2], summary["feasibility"]["E_primary"], f"{identity_id}:E_primary")
    if int(np.sum(quantiles > 1.0)) != summary["feasibility"]["r_stable"]:
        raise VerificationError(f"R_STABLE_MISMATCH:{identity_id}")
    reference = np.load(
        M1_ROOT / "development/candidates" / identity_id / "reference/development_reference_gram.npy",
        allow_pickle=False,
    )
    for cell, repeat in audit_units(partition, identity_id):
        response = solve_forward_block(
            member,
            nuisance[cell],
            cell_index=cell,
            repeat_index=repeat,
            frequencies_hz=frozen_frequency_grid(),
            state_angles_degrees=STATE_ANGLES_DEGREES,
            partition=partition,
            repeat_seed_tuple=seeds_for(partition),
        ).central_pressure
        distances, gram, local_singulars = independent_geometry(response, whitener)
        assert_close(distances, arrays["distances"][cell, repeat], f"{identity_id}:audit_distance")
        assert_close(local_singulars, arrays["singular_values"][cell, repeat], f"{identity_id}:audit_singular")
        assert_close(np.linalg.norm(gram - reference, ord="fro"), arrays["gram_drift"][cell, repeat], f"{identity_id}:audit_drift")
        if int(np.argmin(distances)) != int(arrays["weakest_pair"][cell, repeat]):
            raise VerificationError(f"WEAKEST_PAIR_MISMATCH:{identity_id}")
        assert_close(np.max(distances) / np.min(distances), arrays["pair_anisotropy"][cell, repeat], f"{identity_id}:audit_anisotropy")
    return {"identity_id": identity_id, "candidate_reduction": True, "audit_units": 2, "finite": True}


def welch_twelve(margin: np.ndarray, drift: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    contrasts = []
    standard_errors = []
    statistics = []
    for matrix, drift_direction in ((margin, False), (drift, True)):
        means = np.mean(matrix, axis=1)
        variances = np.var(matrix, axis=1, ddof=1)
        for left, right in PAIRS:
            delta = means[right] - means[left] if drift_direction else means[left] - means[right]
            se = math.sqrt(float(variances[left] / 20.0 + variances[right] / 20.0))
            if se <= 0.0 or not math.isfinite(se):
                raise VerificationError("INFERENCE_DENOMINATOR_UNAVAILABLE")
            contrasts.append(delta)
            standard_errors.append(se)
            statistics.append(delta / se)
    return np.asarray(contrasts), np.asarray(standard_errors), np.asarray(statistics)


def verify_inference(partition: str, summaries: list[dict[str, Any]]) -> dict[str, Any]:
    margin = np.stack(
        [np.asarray([item["metrics"]["d_min_lower_tail_es_0p05"] for item in summaries[index * 20 : (index + 1) * 20]]) for index in range(4)]
    )
    drift = np.stack(
        [np.asarray([item["metrics"]["gram_frobenius_drift_upper_tail_es_0p05"] for item in summaries[index * 20 : (index + 1) * 20]]) for index in range(4)]
    )
    saved = read_json(M1_ROOT / partition / "inference/inference_summary.json")
    contrasts, standard_errors, observed = welch_twelve(margin, drift)
    assert_close(contrasts[:6], saved["observed"]["margin"]["contrasts"], "observed_margin_contrasts")
    assert_close(contrasts[6:], saved["observed"]["drift"]["contrasts"], "observed_drift_contrasts")
    assert_close(standard_errors[:6], saved["observed"]["margin"]["standard_errors"], "observed_margin_se")
    assert_close(standard_errors[6:], saved["observed"]["drift"]["standard_errors"], "observed_drift_se")

    rng = np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    indices = np.stack([rng.integers(0, 20, size=(BOOTSTRAP_REPLICATES, 20), endpoint=False) for _ in FAMILIES])
    margin_means = np.stack([np.mean(margin[index][indices[index]], axis=1) for index in range(4)], axis=1)
    drift_means = np.stack([np.mean(drift[index][indices[index]], axis=1) for index in range(4)], axis=1)
    margin_boot = np.stack([margin_means[:, left] - margin_means[:, right] for left, right in PAIRS], axis=1)
    drift_boot = np.stack([drift_means[:, right] - drift_means[:, left] for left, right in PAIRS], axis=1)
    saved_margin_boot = np.load(REPO / saved["bootstrap"]["margin_path"], allow_pickle=False)
    saved_drift_boot = np.load(REPO / saved["bootstrap"]["drift_path"], allow_pickle=False)
    if not np.array_equal(margin_boot, saved_margin_boot) or not np.array_equal(drift_boot, saved_drift_boot):
        raise VerificationError("BOOTSTRAP_ARRAY_MISMATCH")
    assert_close(np.quantile(margin_boot, (0.025, 0.975), axis=0, method="linear").T, saved["bootstrap"]["margin_percentile_95_ci"], "margin_ci")
    assert_close(np.quantile(drift_boot, (0.025, 0.975), axis=0, method="linear").T, saved["bootstrap"]["drift_percentile_95_ci"], "drift_ci")

    rng = np.random.Generator(np.random.PCG64(PERMUTATION_SEED))
    margin_flat = margin.reshape(-1)
    drift_flat = drift.reshape(-1)
    maxima = np.empty(PERMUTATION_REPLICATES, dtype=float)
    for replicate in range(PERMUTATION_REPLICATES):
        permutation = rng.permutation(80)
        _, _, stats = welch_twelve(margin_flat[permutation].reshape((4, 20)), drift_flat[permutation].reshape((4, 20)))
        maxima[replicate] = float(np.max(np.abs(stats)))
    saved_maxima = np.load(REPO / saved["permutation"]["max_abs_t_path"], allow_pickle=False)
    if not np.array_equal(maxima, saved_maxima):
        raise VerificationError("PERMUTATION_MAXIMA_MISMATCH")
    adjusted = np.asarray([(1.0 + np.count_nonzero(maxima >= abs(value))) / 100001.0 for value in observed])
    assert_close(adjusted, saved["permutation"]["adjusted_p"], "adjusted_p")
    return {
        "bootstrap_recomputed": True,
        "permutation_recomputed": True,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "permutation_replicates": PERMUTATION_REPLICATES,
        "minimum_adjusted_p": float(np.min(adjusted)),
    }


def verify_partition(partition: str) -> Path:
    exact80 = read_json(EXACT80_PATH)["members"]
    nuisance = nuisance_rows()
    with np.load(COMMON_W_PATH, allow_pickle=False) as sealed:
        whitener = np.asarray(sealed["operator"], dtype=float)
    records = []
    summaries = []
    for entry in exact80:
        identity_path = REPO / entry["identity_path"]
        if sha256_file(identity_path) != entry["identity_file_sha256"]:
            raise VerificationError("EXACT80_IDENTITY_HASH_MISMATCH")
        member = read_json(identity_path)
        records.append(verify_candidate(partition, entry, member, nuisance, whitener))
        summaries.append(read_json(M1_ROOT / partition / "candidates" / member["member_id"] / "candidate_summary.json"))
    inference = verify_inference(partition, summaries)
    terminal = read_json(M1_ROOT / partition / "partition_terminal.json")
    if terminal["complete_identities"] != 80 or terminal["feasible_identities"] != 80 or terminal["r_stable_three_identities"] != 80:
        raise VerificationError("PARTITION_TERMINAL_COUNTS_MISMATCH")
    payload = {
        "schema_version": "gen_enc_4_m1_independent_verification_v1",
        "status": "INDEPENDENT_PASS",
        "partition": partition,
        "verified_candidates": len(records),
        "independent_audit_units": sum(record["audit_units"] for record in records),
        "candidate_reductions_recomputed": True,
        "inference": inference,
        "production_analysis_driver_imported": False,
        "production_geometry_formula_module_imported": False,
        "final_test_read": False,
    }
    path = ROOT / "independent_verification" / f"{partition}.json"
    write_json(path, payload)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("self-test", "development", "single-use-validation", "all"))
    args = parser.parse_args(argv)
    if args.mode == "self-test":
        source = Path(__file__).read_text(encoding="utf-8")
        forbidden = (
            "import scripts." + "gen_enc_4_topology_preserving_m0_m1",
            "from scripts." + "gen_enc_4_topology_preserving_m0_m1",
            "import acoustic_encoder.gen_enc." + "robust_encoding_geometry",
            "from acoustic_encoder.gen_enc." + "robust_encoding_geometry",
        )
        if any(token in source for token in forbidden):
            raise VerificationError("FORBIDDEN_PRODUCTION_FORMULA_OR_DRIVER_IMPORT")
        print(json.dumps({"status": "PASS", "production_formula_imported": False, "production_driver_imported": False, "final_test_read": False}, sort_keys=True))
        return 0
    paths = []
    if args.mode in ("development", "all"):
        paths.append(verify_partition("development"))
    if args.mode in ("single-use-validation", "all"):
        paths.append(verify_partition("single_use_validation"))
    payload = {
        "schema_version": "gen_enc_4_m1_independent_verification_terminal_v1",
        "status": "INDEPENDENT_PASS",
        "partitions": [{"path": path.relative_to(REPO).as_posix(), "sha256": sha256_file(path)} for path in paths],
        "final_test_read": False,
    }
    write_json(ROOT / "independent_verification/terminal.json", payload)
    print(json.dumps({"status": payload["status"], "partitions": len(paths), "final_test_read": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


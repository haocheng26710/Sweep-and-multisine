"""Frozen Level-C topology-coupling and dimension-match analysis for INFO-TOP-3."""

from __future__ import annotations

from collections.abc import Sequence
import csv
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.distance import pdist
from sklearn.covariance import LedoitWolf

from .schemas import artifact_sha256, load_feature_set
from .supplemental_module_scan import verify_sup1_output_hashes


FloatArray = NDArray[np.float64]
_MODULES = ("ENC-A", "ENC-B", "ENC-D", "ENC-F")


def generate_parameter_units(count: int, seed: int) -> list[dict[str, Any]]:
    """Freeze complete module-bootstrap/coupling/noise/drift resampling atoms."""
    if count < 1:
        raise ValueError("count must be positive")
    rng = np.random.default_rng(seed)
    units: list[dict[str, Any]] = []
    for index in range(count):
        units.append(
            {
                "unit_id": f"U{index:03d}",
                "module_repeat_indices": {
                    module: rng.integers(0, 3, size=3).tolist() for module in _MODULES
                },
                "coupling_jitter_uniform": float(rng.uniform(-1.0, 1.0)),
                "state_noise_seeds": rng.integers(0, 2**31 - 1, size=4).tolist(),
                "state_drift_seeds": rng.integers(0, 2**31 - 1, size=4).tolist(),
            }
        )
    return units


def coupling_matrix(alpha: float) -> FloatArray:
    """Return the frozen row-normalized shared-mode mixing matrix."""
    value = float(alpha)
    if not 0.0 <= value <= 1.0:
        raise ValueError("alpha must be in [0, 1]")
    raw = (1.0 - value) * np.eye(4) + value * np.ones((4, 4)) / 4.0
    return raw / np.linalg.norm(raw, axis=1, keepdims=True)


def normalized_off_diagonal_energy(matrix: FloatArray) -> float:
    """Report the frozen squared-energy crosstalk definition."""
    values = np.asarray(matrix, dtype=float)
    if values.shape != (4, 4) or not np.all(np.isfinite(values)):
        raise ValueError("coupling matrix must be finite and 4x4")
    off = values.copy()
    np.fill_diagonal(off, 0.0)
    return float(np.sum(np.square(off)) / np.sum(np.square(values)))


def _state_response(signatures: FloatArray, matrix: FloatArray) -> FloatArray:
    basis = np.asarray(signatures, dtype=float)
    coupling = np.asarray(matrix, dtype=float)
    if basis.shape != (4, 16) or coupling.shape != (4, 4):
        raise ValueError("expected 4x16 signatures and a 4x4 coupling matrix")
    centered = basis - np.mean(basis, axis=0, keepdims=True)
    return np.stack([coupling @ np.roll(centered, shift=state, axis=0) for state in range(4)])


def _unit_rms_curve(seed: int, feature_count: int = 16) -> FloatArray:
    rng = np.random.default_rng(seed)
    position = np.linspace(0.0, 1.0, feature_count)
    basis = np.vstack([np.cos(np.pi * order * position) for order in range(1, 9)])
    curve = rng.normal(size=8) @ basis
    curve -= np.mean(curve)
    rms = np.sqrt(np.mean(np.square(curve)))
    return curve / rms


def simulate_observations(
    module_repeat_features: FloatArray,
    *,
    coupling_alpha: float,
    coupling_jitter_half_width: float,
    units: Sequence[dict[str, Any]],
    noise_db: float,
    drift_db: float,
    cross_sensor_correlation: float,
) -> FloatArray:
    """Simulate complete four-state parameter units from whole-module repeats."""
    repeats = np.asarray(module_repeat_features, dtype=float)
    if repeats.shape != (4, 3, 16) or not np.all(np.isfinite(repeats)):
        raise ValueError("module repeat features must be finite with shape 4x3x16")
    rho = float(cross_sensor_correlation)
    if not 0.0 <= rho <= 1.0:
        raise ValueError("cross-sensor correlation must be in [0, 1]")
    observed = np.empty((len(units), 4, 4, 16), dtype=float)
    for unit_index, unit in enumerate(units):
        signatures = np.vstack(
            [
                np.median(repeats[module_index, unit["module_repeat_indices"][module]], axis=0)
                for module_index, module in enumerate(_MODULES)
            ]
        )
        alpha = float(coupling_alpha) + float(coupling_jitter_half_width) * float(unit["coupling_jitter_uniform"])
        response = _state_response(signatures, coupling_matrix(alpha))
        for state in range(4):
            common_noise = _unit_rms_curve(int(unit["state_noise_seeds"][state]))
            sensor_noise = np.empty((4, 16), dtype=float)
            for sensor in range(4):
                independent = _unit_rms_curve(int(unit["state_noise_seeds"][state]) + 104729 * (sensor + 1))
                sensor_noise[sensor] = np.sqrt(rho) * common_noise + np.sqrt(1.0 - rho) * independent
            drift = _unit_rms_curve(int(unit["state_drift_seeds"][state]))
            observed[unit_index, state] = response[state] + float(noise_db) * sensor_noise + float(drift_db) * drift[None, :]
    return observed


def evaluate_observations(
    observed: FloatArray,
    sensor_indices: Sequence[int],
    *,
    nuisance_floor_db: float,
) -> dict[str, Any]:
    """Evaluate four-state responses with complete units as the only sample atoms."""
    values = np.asarray(observed, dtype=float)
    indices = tuple(int(index) for index in sensor_indices)
    if values.ndim != 4 or values.shape[1:] != (4, 4, 16) or not indices:
        raise ValueError("expected Ux4x4x16 observations and a sensor subset")
    selected = values[:, :, indices, :].reshape(values.shape[0], 4, -1)
    centroids = np.mean(selected, axis=0)
    centered_centroids = centroids - np.mean(centroids, axis=0, keepdims=True)
    singular = np.linalg.svd(centered_centroids, compute_uv=False)
    normalized = singular / np.sqrt(len(indices) * 16)
    stable_dimension = min(3, int(np.sum(normalized[:3] > float(nuisance_floor_db))))
    tolerance = np.finfo(float).eps * max(centered_centroids.shape) * singular[0]
    contrast_rank = min(3, int(np.sum(singular > tolerance)))
    condition = float(singular[0] / singular[2]) if contrast_rank == 3 and singular[2] > tolerance else None

    within_distances: list[float] = []
    for state in range(4):
        within_distances.extend((pdist(selected[:, state]) / np.sqrt(selected.shape[2])).tolist())
    within = float(np.median(within_distances))
    between: list[float] = []
    ratios: list[float] = []
    residuals = (selected - centroids[None, :, :]).reshape(-1, selected.shape[2])
    covariance = LedoitWolf().fit(residuals)
    inverse = np.linalg.pinv(covariance.covariance_)
    mahalanobis: list[float] = []
    for left, right in itertools.combinations(range(4), 2):
        delta = centroids[left] - centroids[right]
        distance = float(np.sqrt(np.mean(np.square(delta))))
        between.append(distance)
        ratios.append(distance / within if within > 0.0 else float("inf"))
        mahalanobis.append(float(np.sqrt(max(0.0, delta @ inverse @ delta))))
    between_scatter = np.mean(np.square(centered_centroids))
    within_scatter = np.mean(np.square(residuals))
    probabilities = np.square(singular[:3])
    probabilities = probabilities / np.sum(probabilities) if np.sum(probabilities) > 0 else probabilities
    positive = probabilities > 0.0
    effective_rank = float(np.exp(-np.sum(probabilities[positive] * np.log(probabilities[positive])))) if np.any(positive) else 0.0
    return {
        "parameter_unit_count": values.shape[0],
        "frequency_points_used_as_samples": False,
        "pair_count": 6,
        "minimum_pairwise_between_db": float(np.min(between)),
        "median_pairwise_between_db": float(np.median(between)),
        "within_pairwise_median_db": within,
        "minimum_pairwise_between_within_ratio": float(np.min(ratios)),
        "median_pairwise_between_within_ratio": float(np.median(ratios)),
        "fisher_trace_ratio": float(between_scatter / within_scatter) if within_scatter > 0.0 else float("inf"),
        "minimum_shrinkage_mahalanobis": float(np.min(mahalanobis)),
        "median_shrinkage_mahalanobis": float(np.median(mahalanobis)),
        "singular_values": singular.tolist(),
        "normalized_singular_values": normalized.tolist(),
        "interpreted_rank": contrast_rank,
        "effective_rank": effective_rank,
        "stable_contrast_dimension": stable_dimension,
        "nuisance_floor_db": float(nuisance_floor_db),
        "contrast_condition_number": condition,
        "shrinkage": float(covariance.shrinkage_),
    }


def state_response_spectrum(
    signatures: FloatArray,
    matrix: FloatArray,
    sensor_indices: Sequence[int],
) -> dict[str, Any]:
    """Return the centered noiseless spectrum with the four-state rank cap enforced."""
    indices = tuple(int(index) for index in sensor_indices)
    if not indices or len(set(indices)) != len(indices) or any(index not in range(4) for index in indices):
        raise ValueError("sensor indices must be a non-empty unique subset of 0..3")
    response = _state_response(signatures, matrix)[:, indices].reshape(4, -1)
    response -= np.mean(response, axis=0, keepdims=True)
    singular = np.linalg.svd(response, compute_uv=False)
    tolerance = np.finfo(float).eps * max(response.shape) * (singular[0] if singular.size else 0.0)
    interpreted = min(3, int(np.sum(singular > tolerance)))
    energy = np.square(singular[:3])
    probabilities = energy / np.sum(energy) if np.sum(energy) > 0.0 else energy
    positive = probabilities > 0.0
    effective_rank = float(np.exp(-np.sum(probabilities[positive] * np.log(probabilities[positive])))) if np.any(positive) else 0.0
    return {
        "singular_values": singular.tolist(),
        "normalized_singular_values": (singular / np.sqrt(len(indices) * 16)).tolist(),
        "interpreted_rank": interpreted,
        "effective_rank": effective_rank,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return "unavailable_nonfinite"
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path.name}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict, tuple)) else value
                    for key, value in row.items()
                }
            )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def extract_window_features(
    curve: FloatArray,
    frequency_hz: FloatArray,
    valid_mask: NDArray[np.bool_],
    windows: Sequence[dict[str, Any]],
) -> FloatArray:
    """Apply the frozen parent-demeaned windows only on FORMAL-1 valid points."""
    values = np.asarray(curve, dtype=float)
    frequency = np.asarray(frequency_hz, dtype=float)
    valid = np.asarray(valid_mask, dtype=bool)
    if values.shape != frequency.shape or valid.shape != frequency.shape:
        raise ValueError("curve, frequency, and valid mask must share a shape")
    result = np.empty(len(windows), dtype=float)
    for index, window in enumerate(windows):
        parent = np.asarray(window["parent_band_hz"], dtype=float)
        parent_mask = valid & (frequency >= parent[0]) & (frequency <= parent[1])
        window_mask = valid & (frequency >= window["low_hz"]) & (frequency <= window["high_hz"])
        if not np.any(parent_mask) or not np.any(window_mask):
            raise ValueError(f"unsupported frozen window: {window['id']}")
        result[index] = np.mean(values[window_mask] - np.mean(values[parent_mask]))
    if not np.all(np.isfinite(result)):
        raise ValueError("non-finite common-basis feature after valid-mask application")
    return result


def _verify_sha_manifest(root: Path, filename: str) -> dict[str, Any]:
    manifest = root / filename
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, raw_path = line.split(None, 1)
        raw_path = raw_path.strip()
        if "final-test" in raw_path.lower() or "final_test" in raw_path.lower():
            raise ValueError("refusing a SHA manifest that references final-test")
        target = Path(raw_path)
        if not target.is_absolute():
            target = root / target
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f"SHA mismatch: {target}")
        checked += 1
    return {"manifest": str(manifest).replace("\\", "/"), "verified_count": checked, "all_match": True}


def read_top1_primary_anchor(summary_path: str | Path) -> dict[str, Any]:
    """Read the frozen Level-A N/S primary anchor from the actual TOP-1 schema."""
    payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    matches = [row for row in payload["level_a"]["band_metrics"] if row["band"] == "primary" and row["comparison"] == "N_vs_S"]
    if len(matches) != 1:
        raise ValueError("TOP-1 primary N/S anchor is missing or ambiguous")
    row = matches[0]
    return {
        "between_within_ratio": row["between_within_ratio"],
        "between_shape_rms_db": row["between_shape_rms_db"],
        "within_shape_rms_median_db": row["within_shape_rms_median_db"],
        "evidence_level": "Level A",
        "pooled_with_level_c": False,
    }


def load_authoritative_common_basis(root: Path, contract: dict[str, Any]) -> tuple[FloatArray, list[dict[str, Any]]]:
    """Load the SHA-verified SUP-1 basis using its original FORMAL-1 valid mask."""
    sup1 = root / "outputs/supplemental/SUP-1_ENC_MODULE_SCAN"
    verify_sup1_output_hashes(sup1)
    index = {row["sample_id"]: row for row in _read_csv(sup1 / "feature_index.csv")}
    repeatability = {row["module_id"]: row for row in _read_csv(sup1 / "module_repeatability.csv")}
    windows = contract["common_spectral_basis"]["windows"]
    module_features: list[FloatArray] = []
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(2026082730)
    for module in _MODULES:
        sample_ids = repeatability[module]["primary_sample_ids"].split(";")
        curves: list[FloatArray] = []
        frequency: FloatArray | None = None
        valid_mask: NDArray[np.bool_] | None = None
        for sample_id in sample_ids:
            entry = index[sample_id]
            base = sup1 / Path(entry["feature_npz"]).with_suffix("")
            if artifact_sha256(base.with_suffix(".npz")) != entry["feature_npz_sha256"]:
                raise ValueError(f"SUP-1 feature hash mismatch: {sample_id}")
            if artifact_sha256(base.with_suffix(".json")) != entry["feature_json_sha256"]:
                raise ValueError(f"SUP-1 feature metadata hash mismatch: {sample_id}")
            feature = load_feature_set(base)
            current_frequency = np.asarray([float(name.removeprefix("spl_").removesuffix("_hz")) for name in feature.feature_names])
            if frequency is None:
                frequency = current_frequency
                valid_mask = np.asarray(feature.valid_mask, dtype=bool)
            elif not np.array_equal(frequency, current_frequency):
                raise ValueError("SUP-1 common frequency grid mismatch")
            elif not np.array_equal(valid_mask, feature.valid_mask):
                raise ValueError("SUP-1 common valid-mask mismatch")
            curves.append(np.asarray(feature.values, dtype=float))
        assert frequency is not None and valid_mask is not None
        repeat_vectors = np.empty((3, 16), dtype=float)
        for repeat_index, curve in enumerate(curves):
            repeat_vectors[repeat_index] = extract_window_features(curve, frequency, valid_mask, windows)
        module_features.append(repeat_vectors)
        draws = np.empty((2000, 16), dtype=float)
        for draw in range(2000):
            draws[draw] = np.median(repeat_vectors[rng.integers(0, 3, size=3)], axis=0)
        median = np.median(repeat_vectors, axis=0)
        for window_index, window in enumerate(windows):
            rows.append(
                {
                    "state_id": module,
                    "physical_mapping_deg": contract["states"]["physical_mapping_degrees"][module],
                    "window_id": window["id"],
                    "low_hz": window["low_hz"],
                    "high_hz": window["high_hz"],
                    "parent_band_hz": window["parent_band_hz"],
                    "repeat_1_db": repeat_vectors[0, window_index],
                    "repeat_2_db": repeat_vectors[1, window_index],
                    "repeat_3_db": repeat_vectors[2, window_index],
                    "signature_median_db": median[window_index],
                    "bootstrap_ci95_low_db": float(np.quantile(draws[:, window_index], 0.025)),
                    "bootstrap_ci95_high_db": float(np.quantile(draws[:, window_index], 0.975)),
                    "bootstrap_iterations": 2000,
                    "resampling_unit": "whole_SUP1_repeat_curve",
                    "source_sample_ids": sample_ids,
                }
            )
    return np.stack(module_features), rows


def freeze_top3_inputs(project_root: str | Path, output_directory: str | Path) -> dict[str, Any]:
    """Audit authority and freeze the common basis, matrices, observations, and units."""
    root = Path(project_root).resolve()
    output = Path(output_directory).resolve()
    contract_path = output / "top3_analysis_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if not contract.get("frozen_before_result_computation"):
        raise ValueError("TOP-3 contract was not frozen before results")
    mapping_audit = json.loads((root / "outputs/supplemental/SUP-1_SUP-2R_MECHANISM_REANALYSIS/input_audit.json").read_text(encoding="utf-8"))
    expected_mapping = {"0": "ENC-A", "90": "ENC-B", "180": "ENC-D", "270": "ENC-F"}
    if mapping_audit.get("physical_mapping") != expected_mapping:
        raise ValueError("INFO_TOP_3_BLOCKED_BY_COMMON_BASIS: A/B/D/F mapping mismatch")

    audit_specs = [
        ("TOP0", root / "outputs/info_top/INFO_TOP_0_RESEARCH_CONTRACT", "SHA256SUMS.txt"),
        ("TOP1", root / "outputs/info_top/INFO_TOP_1_SINGLE_MIC_BASELINE", "SHA256SUMS.txt"),
        ("TOP2", root / "outputs/info_top/INFO_TOP_2_INFORMATION_COST_CURVE", "SHA256SUMS.txt"),
        ("SUP1", root / "outputs/supplemental/SUP-1_ENC_MODULE_SCAN", "SHA256SUMS"),
        ("SUP2R", root / "outputs/supplemental/SUP-1_SUP-2R_MECHANISM_REANALYSIS", "SHA256SUMS"),
        ("FORMAL4", root / "outputs/formal/FORMAL-4_CORE_ANALYSIS", "SHA256SUMS"),
        ("FORMAL5", root / "outputs/formal/FORMAL-5_FINAL_SYNTHESIS", "SHA256SUMS"),
        ("TRANS", root / "outputs/real_experiment/research_analysis/TRANS1_TWO_PORT_PHYSICAL_PILOT", "SHA256SUMS.txt"),
        ("P04T5", root / "outputs/real_experiment/research_analysis/P04T5_PUBLICATION_SYNTHESIS", "SHA256SUMS.txt"),
    ]
    audits: list[dict[str, Any]] = []
    for stage, directory, filename in audit_specs:
        result = _verify_sha_manifest(directory, filename)
        result["stage"] = stage
        result["manifest_sha256"] = hashlib.sha256((directory / filename).read_bytes()).hexdigest()
        audits.append(result)
    direct_inputs = [
        root / "docs/experiment/INFO_TOP_RESEARCH_CONTRACT.md",
        root / "docs/prompts/info_top/SHARED_CONTEXT.md",
        root / "docs/progress/INFO_TOP_0_RESEARCH_CONTRACT_AND_ASSET_AUDIT.md",
        root / "docs/progress/INFO_TOP_1_SINGLE_MIC_BASELINE.md",
        root / "docs/progress/INFO_TOP_2_INFORMATION_COST_CURVE.md",
        contract_path,
    ]
    for path in direct_inputs:
        audits.append({"stage": "DIRECT_CONTRACT", "path": str(path).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "all_match": True})
    _write_json(output / "input_hash_audit.json", {"status": "PASS", "audits": audits, "mapping": mapping_audit, "final_test_read": False})
    _write_csv(output / "input_hash_audit.csv", audits)

    repeat_features, basis_rows = load_authoritative_common_basis(root, contract)
    np.savez_compressed(output / "common_spectral_basis.npz", module_ids=np.asarray(_MODULES), repeat_features=repeat_features)
    _write_csv(output / "common_spectral_basis.csv", basis_rows)
    _write_json(output / "common_spectral_basis.json", {"states": list(_MODULES), "windows": contract["common_spectral_basis"]["windows"], "rows": basis_rows, "repeat_feature_shape": list(repeat_features.shape), "final_test_read": False})

    matrix_rows: list[dict[str, Any]] = []
    matrix_payload: list[dict[str, Any]] = []
    for family in contract["topology_model"]["families"]:
        matrix = coupling_matrix(family["alpha"])
        matrix_payload.append({**family, "matrix": matrix.tolist()})
        for row in range(4):
            for column in range(4):
                matrix_rows.append({"topology": family["id"], "row": row, "column": column, "value": matrix[row, column], "normalized_off_diagonal_energy": normalized_off_diagonal_energy(matrix)})
    _write_csv(output / "coupling_matrices.csv", matrix_rows)
    _write_json(output / "coupling_matrices.json", {"formula": contract["topology_model"]["coupling_formula"], "families": matrix_payload})

    observations: list[dict[str, Any]] = []
    for m in (1, 2, 3, 4):
        for indices in itertools.combinations(range(4), m):
            observations.append({"M": m, "configuration_id": "OBS-" + "-".join(str(index) for index in indices), "sensor_indices": list(indices), "sensor_roles": [contract["observation_contract"]["sensor_roles"][index] for index in indices], "matrix": np.eye(4)[list(indices)].tolist()})
    _write_csv(output / "observation_matrices.csv", observations)
    _write_json(output / "observation_matrices.json", {"configurations": observations, "level": "Level C", "shared_across_topologies": True})

    unit_spec = contract["parameter_units"]
    development = generate_parameter_units(unit_spec["development_count"], unit_spec["development_seed"])
    evaluation = generate_parameter_units(unit_spec["evaluation_count"], unit_spec["evaluation_seed"])
    _write_json(output / "simulation_parameter_units.json", {"development": development, "evaluation": evaluation, "unit_is_resampling_atom": True, "paired_across_topologies": True, "frequency_points_are_samples": False})
    scenarios = [{"scenario_id": "UNPERTURBED", "noise_factor": 0.0, "drift_factor": 0.0, "rho": 0.0}]
    scenarios += [{"scenario_id": f"N{n}_D{d}_R{rho}", "noise_factor": n, "drift_factor": d, "rho": rho} for n in contract["perturbations"]["noise_factors"] for d in contract["perturbations"]["drift_factors"] for rho in contract["perturbations"]["cross_sensor_noise_correlations"]]
    cells = [{"topology": family["id"], "split": split, **scenario} for family in contract["topology_model"]["families"] for split in ("development", "evaluation") for scenario in scenarios]
    _write_csv(output / "parameter_cells.csv", cells)
    _write_json(output / "parameter_cells.json", {"cells": cells, "cell_count": len(cells)})
    return {"status": "TOP3A_INPUTS_FROZEN", "basis_shape": list(repeat_features.shape), "observation_count": len(observations), "parameter_cell_count": len(cells)}


def _primary_ratio(observed: FloatArray, indices: Sequence[int]) -> float:
    selected = observed[:, :, tuple(indices), :].reshape(observed.shape[0], 4, -1)
    centroids = np.mean(selected, axis=0)
    within = np.median(np.concatenate([pdist(selected[:, state]) / np.sqrt(selected.shape[2]) for state in range(4)]))
    between = [np.sqrt(np.mean(np.square(centroids[left] - centroids[right]))) for left, right in itertools.combinations(range(4), 2)]
    return float(np.min(between) / within) if within > 0.0 else float("inf")


def _group_readout(development: FloatArray, evaluation: FloatArray, indices: Sequence[int]) -> float:
    indices = tuple(indices)
    x_dev = development[:, :, indices, :].reshape(-1, len(indices) * 16)
    x_eval = evaluation[:, :, indices, :].reshape(-1, len(indices) * 16)
    y_dev = np.tile(np.arange(4), development.shape[0])
    y_eval = np.tile(np.arange(4), evaluation.shape[0])
    mean = np.mean(x_dev, axis=0)
    scale = np.std(x_dev, axis=0)
    scale[scale == 0.0] = 1.0
    x_dev = (x_dev - mean) / scale
    x_eval = (x_eval - mean) / scale
    centroids = np.vstack([np.mean(x_dev[y_dev == state], axis=0) for state in range(4)])
    predicted = np.argmin(np.sum(np.square(x_eval[:, None] - centroids[None, :]), axis=2), axis=1)
    return float(np.mean([np.mean(predicted[y_eval == state] == state) for state in range(4)]))


def bootstrap_match_noninferiority(
    evaluation_by_topology: dict[str, FloatArray],
    selected_specs: Sequence[dict[str, Any]],
    *,
    iterations: int,
    seed: int,
) -> float:
    """Bootstrap full-vs-incomplete coverage using paired complete evaluation units."""
    full_specs = [spec for spec in selected_specs if spec["full_coverage"]]
    incomplete_specs = [spec for spec in selected_specs if not spec["full_coverage"]]
    if not full_specs or not incomplete_specs:
        raise ValueError("both full and incomplete coverage rows are required")
    unit_counts = {values.shape[0] for values in evaluation_by_topology.values()}
    if len(unit_counts) != 1:
        raise ValueError("paired topology evaluations must share a unit count")
    count = unit_counts.pop()
    rng = np.random.default_rng(seed)
    successes = 0
    for _ in range(iterations):
        sample = rng.integers(0, count, count)
        full_score = np.median([_primary_ratio(evaluation_by_topology[spec["topology"]][sample], spec["sensor_indices"]) for spec in full_specs])
        incomplete_score = np.median([_primary_ratio(evaluation_by_topology[spec["topology"]][sample], spec["sensor_indices"]) for spec in incomplete_specs])
        successes += full_score >= incomplete_score
    return successes / iterations


def run_top3_analysis(project_root: str | Path, output_directory: str | Path) -> dict[str, Any]:
    """Execute only the frozen INFO-TOP-3 bounded Level-C comparison."""
    root = Path(project_root).resolve()
    output = Path(output_directory).resolve()
    contract = json.loads((output / "top3_analysis_contract.json").read_text(encoding="utf-8"))
    if json.loads((output / "input_hash_audit.json").read_text(encoding="utf-8"))["status"] != "PASS":
        raise ValueError("TOP-3A input audit did not pass")
    repeat_features = np.asarray(np.load(output / "common_spectral_basis.npz")["repeat_features"], dtype=float)
    signatures = np.median(repeat_features, axis=1)
    units_payload = json.loads((output / "simulation_parameter_units.json").read_text(encoding="utf-8"))
    observations = json.loads((output / "observation_matrices.json").read_text(encoding="utf-8"))["configurations"]
    perturb = contract["perturbations"]
    scenarios = [{"scenario_id": "UNPERTURBED", "noise_factor": 0.0, "drift_factor": 0.0, "rho": 0.0}]
    scenarios += [{"scenario_id": f"N{n}_D{d}_R{rho}", "noise_factor": n, "drift_factor": d, "rho": rho} for n in perturb["noise_factors"] for d in perturb["drift_factors"] for rho in perturb["cross_sensor_noise_correlations"]]
    primary = perturb["primary_reference"]
    primary_id = f"N{primary['noise_factor']}_D{primary['drift_factor']}_R{primary['cross_sensor_noise_correlation']}"
    rows: list[dict[str, Any]] = []
    spectrum_rows: list[dict[str, Any]] = []
    primary_cache: dict[str, tuple[FloatArray, FloatArray]] = {}
    selected_rows: list[dict[str, Any]] = []
    for family in contract["topology_model"]["families"]:
        topology = family["id"]
        nominal_matrix = coupling_matrix(family["alpha"])
        for configuration in observations:
            indices = tuple(configuration["sensor_indices"])
            spectrum = state_response_spectrum(signatures, nominal_matrix, indices)
            singular = spectrum["singular_values"]
            condition = singular[0] / singular[2] if singular[2] > np.finfo(float).eps * singular[0] * 64 else None
            spectrum_rows.append({"topology": topology, "M": configuration["M"], "configuration_id": configuration["configuration_id"], "sensor_roles": configuration["sensor_roles"], **spectrum, "contrast_condition_number": condition, "normalized_off_diagonal_energy": normalized_off_diagonal_energy(nominal_matrix), "rank_cap": 3})
        for scenario in scenarios:
            noise_db = perturb["noise_anchor_db"] * scenario["noise_factor"]
            drift_db = perturb["drift_anchor_db"] * scenario["drift_factor"]
            nuisance = float(np.sqrt(noise_db**2 + drift_db**2))
            dev = simulate_observations(repeat_features, coupling_alpha=family["alpha"], coupling_jitter_half_width=family["alpha_unit_jitter"][1], units=units_payload["development"], noise_db=noise_db, drift_db=drift_db, cross_sensor_correlation=scenario["rho"])
            eva = simulate_observations(repeat_features, coupling_alpha=family["alpha"], coupling_jitter_half_width=family["alpha_unit_jitter"][1], units=units_payload["evaluation"], noise_db=noise_db, drift_db=drift_db, cross_sensor_correlation=scenario["rho"])
            if scenario["scenario_id"] == primary_id:
                primary_cache[topology] = (dev, eva)
            for configuration in observations:
                indices = tuple(configuration["sensor_indices"])
                dev_metrics = evaluate_observations(dev, indices, nuisance_floor_db=nuisance)
                eva_metrics = evaluate_observations(eva, indices, nuisance_floor_db=nuisance)
                noiseless = state_response_spectrum(signatures, nominal_matrix, indices)
                stable = min(3, int(np.sum(np.asarray(noiseless["normalized_singular_values"][:3]) > nuisance)))
                row = {
                    "topology": topology,
                    "scenario_id": scenario["scenario_id"],
                    "noise_factor": scenario["noise_factor"],
                    "drift_factor": scenario["drift_factor"],
                    "cross_sensor_correlation": scenario["rho"],
                    "M": configuration["M"],
                    "configuration_id": configuration["configuration_id"],
                    "sensor_roles": configuration["sensor_roles"],
                    "development_primary_ratio": dev_metrics["minimum_pairwise_between_within_ratio"],
                    **{f"evaluation_{key}": value for key, value in eva_metrics.items() if key not in {"singular_values", "normalized_singular_values", "stable_contrast_dimension"}},
                    "noiseless_singular_values": noiseless["singular_values"],
                    "noiseless_normalized_singular_values": noiseless["normalized_singular_values"],
                    "noiseless_effective_rank": noiseless["effective_rank"],
                    "stable_contrast_dimension": stable,
                    "stable_coverage_fraction": stable / 3.0,
                    "normalized_off_diagonal_energy": normalized_off_diagonal_energy(nominal_matrix),
                }
                rows.append(row)
    zero_drift_lookup = {(row["topology"], row["noise_factor"], row["cross_sensor_correlation"], row["configuration_id"]): row["evaluation_minimum_pairwise_between_within_ratio"] for row in rows if row["drift_factor"] == 0.0}
    for row in rows:
        baseline = zero_drift_lookup.get((row["topology"], row["noise_factor"], row["cross_sensor_correlation"], row["configuration_id"]))
        row["shared_drift_robustness_retention"] = row["evaluation_minimum_pairwise_between_within_ratio"] / baseline if baseline and baseline > 0 else None
    for family in contract["topology_model"]["families"]:
        topology = family["id"]
        dev, eva = primary_cache[topology]
        for m in (1, 2, 3, 4):
            candidates = [row for row in rows if row["topology"] == topology and row["scenario_id"] == primary_id and row["M"] == m]
            chosen = sorted(candidates, key=lambda row: (-row["development_primary_ratio"], row["configuration_id"]))[0]
            indices = tuple(next(item["sensor_indices"] for item in observations if item["configuration_id"] == chosen["configuration_id"]))
            selected_rows.append({**chosen, "selection_split": "development", "evaluation_group_aware_balanced_accuracy_secondary": _group_readout(dev, eva, indices)})
    _write_csv(output / "topology_m_perturbation_metrics.csv", rows)
    _write_json(output / "topology_m_perturbation_metrics.json", {"rows": rows, "row_count": len(rows)})
    _write_csv(output / "singular_rank_stable_dimension_condition_crosstalk.csv", spectrum_rows)
    _write_json(output / "singular_rank_stable_dimension_condition_crosstalk.json", {"rows": spectrum_rows})
    _write_csv(output / "development_selected_evaluation_metrics.csv", selected_rows)
    _write_json(output / "development_selected_evaluation_metrics.json", {"rows": selected_rows})

    ablation_rows: list[dict[str, Any]] = []
    homogeneous = np.repeat(np.mean(repeat_features, axis=0, keepdims=True), 4, axis=0)
    for family in contract["topology_model"]["families"]:
        for ablation, features, alpha, half_width in (
            ("REMOVE_COMMON_MODE_KEEP_MODULE_SIGNATURES", repeat_features, 0.0, 0.0),
            ("HOMOGENIZE_MODULE_SIGNATURES_KEEP_COUPLING", homogeneous, family["alpha"], family["alpha_unit_jitter"][1]),
        ):
            eva = simulate_observations(features, coupling_alpha=alpha, coupling_jitter_half_width=half_width, units=units_payload["evaluation"], noise_db=perturb["noise_anchor_db"], drift_db=perturb["drift_anchor_db"], cross_sensor_correlation=0.5)
            for configuration in [item for item in observations if item["M"] in (1, 4)]:
                metrics = evaluate_observations(eva, configuration["sensor_indices"], nuisance_floor_db=np.sqrt(perturb["noise_anchor_db"]**2 + perturb["drift_anchor_db"]**2))
                ablation_rows.append({"topology": family["id"], "ablation": ablation, "M": configuration["M"], "configuration_id": configuration["configuration_id"], "evaluation_primary_ratio": metrics["minimum_pairwise_between_within_ratio"], "evaluation_fisher": metrics["fisher_trace_ratio"], "evaluation_median_mahalanobis": metrics["median_shrinkage_mahalanobis"]})
    _write_csv(output / "ablation_results.csv", ablation_rows)
    _write_json(output / "ablation_results.json", {"rows": ablation_rows, "only_predeclared_ablations": True})

    nominal_m1 = {family["id"]: [row for row in rows if row["topology"] == family["id"] and row["scenario_id"] == primary_id and row["M"] == 1] for family in contract["topology_model"]["families"]}
    order = ["HIGH_SHARED_COUPLING", "MEDIUM_PARTIAL_ISOLATION", "NEAR_INDEPENDENT_REFERENCE"]
    medians = {key: float(np.median([row["evaluation_minimum_pairwise_between_within_ratio"] for row in value])) for key, value in nominal_m1.items()}
    role_consistency = sum(nominal_m1[order[2]][index]["evaluation_minimum_pairwise_between_within_ratio"] > nominal_m1[order[1]][index]["evaluation_minimum_pairwise_between_within_ratio"] > nominal_m1[order[0]][index]["evaluation_minimum_pairwise_between_within_ratio"] for index in range(4))
    rng = np.random.default_rng(contract["parameter_units"]["bootstrap_seed"])
    strict_draws = 0
    reverse_draws = 0
    for _ in range(contract["parameter_units"]["bootstrap_iterations"]):
        sample = rng.integers(0, len(units_payload["evaluation"]), len(units_payload["evaluation"]))
        scores = {topology: float(np.median([_primary_ratio(primary_cache[topology][1][sample], (sensor,)) for sensor in range(4)])) for topology in order}
        strict_draws += scores[order[2]] > scores[order[1]] > scores[order[0]]
        reverse_draws += scores[order[0]] >= scores[order[2]]
    strict_probability = strict_draws / contract["parameter_units"]["bootstrap_iterations"]
    reverse_probability = reverse_draws / contract["parameter_units"]["bootstrap_iterations"]
    if medians[order[2]] > medians[order[1]] > medians[order[0]] and role_consistency >= 3 and strict_probability >= 0.75:
        h_coupling = "SUPPORTED_WITH_LIMITS"
    elif medians[order[2]] > medians[order[0]]:
        h_coupling = "PARTIALLY_SUPPORTED"
    elif medians[order[0]] >= medians[order[2]] and reverse_probability >= 0.75:
        h_coupling = "NEGATIVE"
    else:
        h_coupling = "UNCERTAIN"

    full = [row for row in selected_rows if row["stable_contrast_dimension"] == 3]
    incomplete = [row for row in selected_rows if row["stable_contrast_dimension"] < 3]
    if not full:
        h_match = "UNCERTAIN"
        match_reason = "No development-selected primary-reference row achieved stable 3/3 contrast coverage above the frozen nuisance floor."
        match_probability = None
    else:
        full_median = float(np.median([row["evaluation_minimum_pairwise_between_within_ratio"] for row in full]))
        incomplete_median = float(np.median([row["evaluation_minimum_pairwise_between_within_ratio"] for row in incomplete])) if incomplete else full_median
        observation_indices = {item["configuration_id"]: tuple(item["sensor_indices"]) for item in observations}
        selected_specs = [{"topology": row["topology"], "sensor_indices": observation_indices[row["configuration_id"]], "full_coverage": row["stable_contrast_dimension"] == 3} for row in selected_rows]
        match_probability = bootstrap_match_noninferiority(
            {topology: values[1] for topology, values in primary_cache.items()},
            selected_specs,
            iterations=contract["parameter_units"]["bootstrap_iterations"],
            seed=contract["parameter_units"]["bootstrap_seed"],
        )
        after_coverage_ok = True
        for topology in order:
            topology_rows = sorted([row for row in selected_rows if row["topology"] == topology], key=lambda row: row["M"])
            first_full = next((index for index, row in enumerate(topology_rows) if row["stable_contrast_dimension"] == 3), None)
            if first_full is None:
                continue
            reference_value = topology_rows[first_full]["evaluation_minimum_pairwise_between_within_ratio"]
            for row in topology_rows[first_full + 1 :]:
                dimension_bottleneck = row["stable_contrast_dimension"] < 3
                ill_conditioned = row["evaluation_contrast_condition_number"] is not None and row["evaluation_contrast_condition_number"] > 1e4
                if row["evaluation_minimum_pairwise_between_within_ratio"] < 0.9 * reference_value and not (dimension_bottleneck or ill_conditioned):
                    after_coverage_ok = False
        if full_median >= incomplete_median and after_coverage_ok:
            h_match = "SUPPORTED_WITH_LIMITS" if match_probability >= 0.75 else "PARTIALLY_SUPPORTED"
        else:
            h_match = "NEGATIVE" if full_median < incomplete_median and match_probability <= 0.25 else "PARTIALLY_SUPPORTED"
        match_reason = f"Full-coverage median={full_median:.6g}; incomplete-coverage median={incomplete_median:.6g}; conditioning rule applied."
    if h_coupling == "SUPPORTED_WITH_LIMITS" and h_match == "SUPPORTED_WITH_LIMITS":
        stage_status = "INFO_TOP_3_TOPOLOGY_MATCH_SUPPORTED_WITH_LIMITS"
    elif "NEGATIVE" in (h_coupling, h_match) and h_coupling == h_match:
        stage_status = "INFO_TOP_3_NEGATIVE"
    elif any(label in {"SUPPORTED_WITH_LIMITS", "PARTIALLY_SUPPORTED"} for label in (h_coupling, h_match)):
        stage_status = "INFO_TOP_3_PARTIALLY_SUPPORTED"
    else:
        stage_status = "INFO_TOP_3_INCONCLUSIVE"
    decisions = {"schema_version": "info_top_3_hypothesis_decisions_v1", "stage_status": stage_status, "technical_status": "PASS", "H_COUPLING": {"label": h_coupling, "M1_all_role_medians": medians, "strict_role_count": role_consistency, "paired_unit_bootstrap_strict_order_probability": strict_probability, "paired_unit_bootstrap_reverse_probability": reverse_probability, "causal_ceiling": "SUPPORTED_WITH_LIMITS"}, "H_MATCH": {"label": h_match, "full_coverage_row_count": len(full), "incomplete_coverage_row_count": len(incomplete), "bootstrap_noninferiority_probability": match_probability, "reason": match_reason, "causal_interpretation": False}, "final_test_read": False}
    _write_json(output / "hypothesis_decisions.json", decisions)

    top1_anchor = read_top1_primary_anchor(root / "outputs/info_top/INFO_TOP_1_SINGLE_MIC_BASELINE/analysis_summary.json")
    top2 = json.loads((root / "outputs/info_top/INFO_TOP_2_INFORMATION_COST_CURVE/analysis_summary.json").read_text(encoding="utf-8"))
    anchors = [
        {"evidence_layer": "SUP-1 real", "role": "A/B/D/F fixed-window signature and repeat uncertainty", "headline": "28/28 module pairs stable in primary band; A has weaker repeatability", "pooled_with_level_c": False},
        {"evidence_layer": "U4 real", "role": "four-state single-microphone external check", "headline": "U4SYM/U4ENC worst-case ratios 2.0437/2.5199; grouped BA 0.375/0.250", "pooled_with_level_c": False},
        {"evidence_layer": "TRANS real", "role": "two-state nuisance anchor and external check", "headline": f"TOP-1 ratio {top1_anchor['between_within_ratio']}", "pooled_with_level_c": False},
        {"evidence_layer": "TOP-2 Level C", "role": "M=1-4 method and perturbation anchor", "headline": top2["status"], "pooled_with_level_c": False},
        {"evidence_layer": "FORMAL/P04T5 real+simulation separated", "role": "shared-mode mechanism and model-credibility boundary", "headline": "shared chamber changes spectra; simplified COMSOL is trend-only", "pooled_with_level_c": False},
    ]
    _write_csv(output / "external_real_anchor_comparison.csv", anchors)
    _write_json(output / "external_real_anchor_comparison.json", {"rows": anchors, "evidence_layers_merged": False})

    import matplotlib.pyplot as plt
    plot_dir = output / "plots"
    plot_dir.mkdir(exist_ok=True)
    fig, axis = plt.subplots(figsize=(7.2, 4.5))
    for topology in order:
        points = sorted([row for row in selected_rows if row["topology"] == topology], key=lambda row: row["M"])
        axis.plot([row["M"] for row in points], [row["evaluation_minimum_pairwise_between_within_ratio"] for row in points], marker="o", label=topology.replace("_", " ").title())
    axis.set(xlabel="Microphone count M", ylabel="Minimum pairwise between/within", xticks=[1,2,3,4], title="Level-C topology and observation-dimension comparison")
    axis.legend(fontsize=7); fig.tight_layout()
    for extension in ("png", "svg"):
        fig.savefig(plot_dir / f"topology_dimension_match.{extension}", dpi=180)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(6.8, 4.2))
    axis.bar(range(3), [medians[item] for item in order], tick_label=["High shared", "Medium", "Near independent"])
    axis.set(ylabel="Median M=1 minimum pairwise ratio", title="All-role H-COUPLING primary view")
    fig.tight_layout()
    for extension in ("png", "svg"):
        fig.savefig(plot_dir / f"coupling_all_role_m1.{extension}", dpi=180)
    plt.close(fig)
    summary = {"schema_version": "info_top_3_summary_v1", "stage": "INFO-TOP-3", "status": stage_status, "technical_status": "PASS", "evidence_level": "Level C", "topologies_technically_comparable": True, "H_COUPLING": h_coupling, "H_MATCH": h_match, "metric_row_count": len(rows), "selected_row_count": len(selected_rows), "ablation_row_count": len(ablation_rows), "limited_comsol_anchor_request": False, "recommended_top4": h_coupling != "UNCERTAIN" or h_match != "UNCERTAIN", "study_run_called": False, "new_comsol_created": False, "final_test_read": False}
    _write_json(output / "analysis_summary.json", summary)
    return summary


def finalize_top3_artifacts(output_directory: str | Path, report_path: str | Path) -> dict[str, Any]:
    output = Path(output_directory).resolve()
    report = Path(report_path).resolve()
    files = sorted([path for path in output.rglob("*") if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"}] + [report])
    artifacts = [{"path": str(path).replace("\\", "/"), "size_bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files]
    inventory = {"schema_version": "info_top_3_artifact_inventory_v1", "stage": "INFO-TOP-3", "artifacts": artifacts, "final_test_read": False}
    _write_json(output / "artifact_inventory.json", inventory)
    inventory_hash = hashlib.sha256((output / "artifact_inventory.json").read_bytes()).hexdigest()
    lines = [f"{row['sha256']}  {row['path']}" for row in artifacts] + [f"{inventory_hash}  {str(output / 'artifact_inventory.json').replace(chr(92), '/')}" ]
    (output / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return inventory

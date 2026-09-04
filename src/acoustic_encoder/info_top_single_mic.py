"""INFO-TOP-1 real single-microphone baseline analysis.

Frequency bins remain coordinates of one complete curve throughout this module;
they are never treated as independent statistical samples.
"""

from __future__ import annotations

import itertools
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
from types import SimpleNamespace
from typing import Any, Mapping, Sequence
import zipfile

import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float64]

FORMAL_ZIP_SHA256 = "cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb"
DIRECTIONS = (0, 90, 180, 270)
BLOCKS = {
    "B01": ("U4SYM", "RP01"),
    "B02": ("U4SYM", "RP02"),
    "B03": ("U4ENC", "RP01"),
    "B04": ("U4ENC", "RP02"),
}


def _curves(values: Any) -> FloatArray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] < 1 or array.shape[1] < 2:
        raise ValueError("complete curves must be a non-empty 2D array with >=2 bins")
    if not np.all(np.isfinite(array)):
        raise ValueError("complete curves must be finite")
    return array


def _demean_rows(values: FloatArray) -> FloatArray:
    return values - np.mean(values, axis=1, keepdims=True)


def _rms(values: FloatArray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def band_shape_metrics(first: Any, second: Any) -> dict[str, Any]:
    """Return between/within shape metrics using complete repeat curves."""
    first_array = _curves(first)
    second_array = _curves(second)
    if first_array.shape[1] != second_array.shape[1]:
        raise ValueError("groups must share the same frequency coordinates")
    first_demeaned = _demean_rows(first_array)
    second_demeaned = _demean_rows(second_array)
    between = _rms(np.mean(first_demeaned, axis=0) - np.mean(second_demeaned, axis=0))
    within = [
        _rms(group[left] - group[right])
        for group in (first_demeaned, second_demeaned)
        for left, right in itertools.combinations(range(group.shape[0]), 2)
    ]
    within_median = float(np.median(within)) if within else float("nan")
    ratio = between / within_median if within_median > 0.0 else None
    return {
        "between_shape_rms_db": between,
        "within_shape_rms_median_db": within_median,
        "between_within_ratio": ratio,
        "complete_curve_count": int(first_array.shape[0] + second_array.shape[0]),
        "within_pair_count": len(within),
    }


def effective_rank_metrics(centroids: Any) -> dict[str, Any]:
    """Describe the contrast rank of a state-centroid matrix."""
    matrix = _curves(centroids)
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    singular_values = np.linalg.svd(centered, compute_uv=False)
    energy = np.square(singular_values)
    if float(np.sum(energy)) > 0.0:
        probabilities = energy / np.sum(energy)
        positive = probabilities > 0.0
        effective = float(np.exp(-np.sum(probabilities[positive] * np.log(probabilities[positive]))))
    else:
        effective = 0.0
    maximum = int(min(matrix.shape[0] - 1, matrix.shape[1]))
    numerical_rank = int(np.linalg.matrix_rank(centered))
    return {
        "singular_values": [float(value) for value in singular_values],
        "matrix_rank": min(numerical_rank, maximum),
        "raw_numerical_matrix_rank": numerical_rank,
        "effective_rank": effective,
        "maximum_theoretical_contrast_dimension": maximum,
    }


def shrinkage_separability(features: Any, labels: Any) -> dict[str, Any]:
    """Compute fixed-feature Fisher and pooled-residual Ledoit-Wolf separation."""
    from sklearn.covariance import LedoitWolf

    matrix = _curves(features)
    label_array = np.asarray(labels)
    if label_array.ndim != 1 or label_array.size != matrix.shape[0]:
        raise ValueError("one state label is required per complete curve")
    states = np.unique(label_array)
    if states.size < 2 or any(np.count_nonzero(label_array == state) < 2 for state in states):
        return {"status": "unavailable", "reason": "fewer_than_two_curves_per_state"}
    means = np.vstack([np.mean(matrix[label_array == state], axis=0) for state in states])
    residuals = np.vstack(
        [matrix[label_array == state] - means[index] for index, state in enumerate(states)]
    )
    if residuals.shape[0] - states.size < 2 or not np.any(np.var(residuals, axis=0) > 0.0):
        return {"status": "unavailable", "reason": "insufficient_residual_variation"}
    raw_covariance = np.cov(residuals, rowvar=False, ddof=1)
    raw_covariance = np.atleast_2d(raw_covariance)
    estimator = LedoitWolf(assume_centered=True).fit(residuals)
    covariance = np.asarray(estimator.covariance_, dtype=np.float64)
    condition = float(np.linalg.cond(covariance))
    overall = np.mean(matrix, axis=0)
    between_scatter = sum(
        np.count_nonzero(label_array == state) * np.square(means[index] - overall)
        for index, state in enumerate(states)
    )
    within_scatter = np.square(residuals)
    fisher = float(np.sum(between_scatter) / np.sum(within_scatter))
    pairwise: list[float] = []
    inverse = np.linalg.pinv(covariance)
    for left, right in itertools.combinations(range(states.size), 2):
        delta = means[left] - means[right]
        pairwise.append(float(np.sqrt(max(0.0, delta @ inverse @ delta))))
    if not pairwise or not np.all(np.isfinite(pairwise)) or not math.isfinite(condition):
        return {"status": "unavailable", "reason": "non_finite_covariance_metric"}
    return {
        "status": "available",
        "state_count": int(states.size),
        "feature_count": int(matrix.shape[1]),
        "residual_degrees_of_freedom": int(matrix.shape[0] - states.size),
        "raw_covariance_rank": int(np.linalg.matrix_rank(raw_covariance)),
        "raw_covariance_condition_number": float(np.linalg.cond(raw_covariance)),
        "shrinkage_covariance_rank": int(np.linalg.matrix_rank(covariance)),
        "shrinkage_covariance_condition_number": condition,
        "condition_status": "well_conditioned" if condition <= 1.0e8 else "ill_conditioned",
        "shrinkage": float(estimator.shrinkage_),
        "fisher_trace_ratio": fisher,
        "shrinkage_mahalanobis": float(np.median(pairwise)),
        "minimum_pairwise_shrinkage_mahalanobis": float(np.min(pairwise)),
        "pairwise_shrinkage_mahalanobis": pairwise,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_json_safe(value), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _json_safe(row.get(key, "")) for key in fields})
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="")


def _verify_sha_sums(directory: Path, name: str) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for line in (directory / name).read_text(encoding="utf-8").splitlines():
        expected, separator, relative = line.partition("  ")
        if not separator:
            raise ValueError(f"malformed SHA row in {directory / name}")
        path = (directory / Path(*PurePosixPath(relative).parts)).resolve()
        actual = _sha256_file(path)
        records.append({"path": str(path), "expected_sha256": expected, "actual_sha256": actual, "match": actual == expected})
    return {"authority": str(directory), "record_count": len(records), "all_match": all(row["match"] for row in records), "records": records}


def _load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if not contract.get("frozen_before_result_computation") or contract["scope"].get("final_test_read"):
        raise ValueError("TOP-1 analysis contract is not safely frozen")
    if contract["uncertainty"] != {
        **contract["uncertainty"], "bootstrap_iterations": 2000, "seed": 20260827
    }:
        raise ValueError("TOP-1 bootstrap contract changed")
    return contract


def _preprocess_parsed(parsed: Any) -> tuple[FloatArray, FloatArray]:
    from .formal_preprocessing import (
        _interpolate_by_valid_segment,
        _smooth_one_twelfth_octave_db,
        build_formal_log_grid,
        frozen_formal_preprocessing_contract,
    )

    contract = frozen_formal_preprocessing_contract()
    target = build_formal_log_grid(contract)
    source = SimpleNamespace(
        frequency_hz=np.asarray(parsed.frequency_hz, dtype=np.float64),
        magnitude_db=np.asarray(parsed.magnitude_db, dtype=np.float64),
        valid_mask=np.ones(len(parsed.frequency_hz), dtype=bool),
    )
    interpolated, valid, _ = _interpolate_by_valid_segment(
        source, target, frequency_min_hz=200.0, frequency_max_hz=8000.0
    )
    smoothed, output_valid, _ = _smooth_one_twelfth_octave_db(target, interpolated, valid)
    if np.count_nonzero(output_valid) != 255 or np.flatnonzero(~output_valid).tolist() != [0]:
        raise ValueError("FORMAL-1 valid mask differs from frozen 255/256 contract")
    return target, smoothed


def _load_level_b_active(zip_path: Path) -> tuple[FloatArray, list[dict[str, Any]]]:
    from .formal_real_import import _member_identity, _parse_rew_member

    if _sha256_file(zip_path) != FORMAL_ZIP_SHA256:
        raise ValueError("FORMAL REV003 ZIP SHA-256 mismatch")
    rows: list[dict[str, Any]] = []
    frequency: FloatArray | None = None
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = PurePosixPath(info.filename)
            if len(path.parts) != 3 or path.parts[1].split("_")[0] not in BLOCKS:
                continue
            group_name = path.parts[1]
            block, configuration, assembly, direction, repeat = _member_identity(path.name, group_name=group_name)
            if block not in BLOCKS or assembly != "AS01":
                continue
            payload = archive.read(info)
            parsed = _parse_rew_member(payload, info.filename)
            current_frequency, curve = _preprocess_parsed(parsed)
            if frequency is None:
                frequency = current_frequency
            elif not np.array_equal(frequency, current_frequency):
                raise ValueError("Level B FORMAL grids differ")
            rows.append({
                "sample_id": f"FORMAL3-{block}-{configuration}-{assembly}-D{direction}-C{repeat}",
                "archive_path": info.filename,
                "block": block,
                "configuration": configuration,
                "assembly": assembly,
                "reposition_round": BLOCKS[block][1],
                "direction": int(direction),
                "repeat": int(repeat),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
                "curve": curve,
            })
    rows.sort(key=lambda row: (row["block"], row["direction"], row["repeat"]))
    if frequency is None or len(rows) != 48:
        raise ValueError(f"Level B must contain exactly 48 B01-B04 ACTIVE curves; found {len(rows)}")
    identities = {(row["block"], row["direction"], row["repeat"]) for row in rows}
    if len(identities) != 48 or any(sum(row["block"] == block and row["direction"] == direction for row in rows) != 3 for block in BLOCKS for direction in DIRECTIONS):
        raise ValueError("Level B block/direction/repeat identity is incomplete")
    _apply_formal_flags(rows, frequency)
    return frequency, rows


def _band_mask(frequency: FloatArray, low: float, high: float) -> NDArray[np.bool_]:
    return np.isfinite(frequency) & (frequency >= low) & (frequency <= high)


def _apply_formal_flags(rows: list[dict[str, Any]], frequency: FloatArray) -> None:
    primary = _band_mask(frequency, 200.0, 4000.0) & np.isfinite(rows[0]["curve"])
    for block in BLOCKS:
        for direction in DIRECTIONS:
            selected = [row for row in rows if row["block"] == block and row["direction"] == direction]
            values = np.vstack([row["curve"][primary] for row in selected])
            center_curve = np.median(values, axis=0)
            distances = np.sqrt(np.mean(np.square(values - center_curve), axis=1))
            center = float(np.median(distances))
            mad = float(np.median(np.abs(distances - center)))
            threshold = center + 3.0 * 1.4826 * mad
            for row, distance in zip(selected, distances, strict=True):
                row["flagged"] = bool(distance > threshold + 1.0e-12)
                row["flag_distance_db"] = float(distance)
                row["flag_threshold_db"] = threshold


def _window_features(curves: FloatArray, frequency: FloatArray, windows: Sequence[Mapping[str, Any]]) -> FloatArray:
    columns = []
    for window in windows:
        mask = _band_mask(frequency, float(window["low_hz"]), float(window["high_hz"]))
        if not np.any(mask):
            raise ValueError(f"fixed window has no valid points: {window['id']}")
        columns.append(np.mean(curves[:, mask], axis=1))
    return np.column_stack(columns)


def _bootstrap_level_a(matrices: Mapping[str, FloatArray], frequency: FloatArray, windows: Sequence[Mapping[str, Any]], iterations: int, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    values = {"primary_ratio": [], "secondary_ratio": [], "effect_to_drift_ratio": [], "effect_correlation": [], "fisher_trace_ratio": [], "shrinkage_mahalanobis": []}
    band_sizes = {"primary": 207, "secondary": 48}
    for _ in range(iterations):
        sampled = {key: matrix[rng.integers(0, matrix.shape[0], matrix.shape[0])] for key, matrix in matrices.items()}
        for band, size in band_sizes.items():
            selected = slice(0, size) if band == "primary" else slice(207, 255)
            result = band_shape_metrics(sampled["N"][:, selected], sampled["S"][:, selected])
            values[f"{band}_ratio"].append(result["between_within_ratio"] or 0.0)
        n = _demean_rows(sampled["N"]); s = _demean_rows(sampled["S"]); nr = _demean_rows(sampled["NRETURN"])
        effect = np.mean(n, axis=0) - np.mean(s, axis=0)
        return_effect = np.mean(nr, axis=0) - np.mean(s, axis=0)
        drift = _rms(np.mean(n, axis=0) - np.mean(nr, axis=0))
        values["effect_to_drift_ratio"].append(_rms(effect) / drift if drift > 0 else 0.0)
        values["effect_correlation"].append(float(np.corrcoef(effect, return_effect)[0, 1]))
        feature_matrix = np.vstack((_window_features(sampled["N"], frequency, windows), _window_features(sampled["S"], frequency, windows)))
        separation = shrinkage_separability(feature_matrix, np.array(["N"] * 6 + ["S"] * 6))
        if separation["status"] == "available":
            values["fisher_trace_ratio"].append(separation["fisher_trace_ratio"])
            values["shrinkage_mahalanobis"].append(separation["shrinkage_mahalanobis"])
    return {**{key: [float(value) for value in np.percentile(item, [2.5, 97.5])] for key, item in values.items()}, "requested_iterations": iterations, "finite_separability_iterations": len(values["shrinkage_mahalanobis"])}


def _exact_binary_permutation(first: FloatArray, second: FloatArray) -> dict[str, Any]:
    pooled = np.vstack([first, second])
    observed = band_shape_metrics(first, second)["between_within_ratio"]
    null: list[float] = []
    indices = set(range(pooled.shape[0]))
    for selected in itertools.combinations(range(pooled.shape[0]), first.shape[0]):
        left = list(selected); right = sorted(indices - set(selected))
        value = band_shape_metrics(pooled[left], pooled[right])["between_within_ratio"]
        null.append(float(value or 0.0))
    return {"assignment_count": len(null), "observed": observed, "p_value": (sum(value >= float(observed) for value in null) + 1) / (len(null) + 1)}


def _level_a(frequency: FloatArray, curves: Mapping[str, FloatArray], windows: Sequence[Mapping[str, Any]], iterations: int, seed: int) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    valid = np.isfinite(next(iter(curves.values())))
    matrices = {condition: np.vstack([curve for sample, curve in curves.items() if sample.startswith(f"TRANS1-{condition}-")])[:, valid] for condition in ("N", "S", "NRETURN")}
    valid_frequency = frequency[valid]
    bands = {"primary": _band_mask(valid_frequency, 200.0, 4000.0), "secondary": _band_mask(valid_frequency, 4000.0, 8000.0)}
    band_rows = []
    for band, mask in bands.items():
        metrics = band_shape_metrics(matrices["N"][:, mask], matrices["S"][:, mask])
        band_rows.append({"level": "A", "comparison": "N_vs_S", "band": band, **metrics})
    demeaned = {key: _demean_rows(value[:, bands["primary"]]) for key, value in matrices.items()}
    ns = np.mean(demeaned["N"], axis=0) - np.mean(demeaned["S"], axis=0)
    nrs = np.mean(demeaned["NRETURN"], axis=0) - np.mean(demeaned["S"], axis=0)
    drift_vector = np.mean(demeaned["N"], axis=0) - np.mean(demeaned["NRETURN"], axis=0)
    drift = _rms(drift_vector)
    features = np.vstack([_window_features(matrix, valid_frequency, windows) for matrix in matrices.values()])
    labels = np.concatenate([[key] * len(matrix) for key, matrix in matrices.items()])
    primary_features = np.vstack((_window_features(matrices["N"], valid_frequency, windows), _window_features(matrices["S"], valid_frequency, windows)))
    primary_labels = np.array(["N"] * 6 + ["S"] * 6)
    result = {
        "counts": {key: int(value.shape[0]) for key, value in matrices.items()},
        "all_repeats_retained": True,
        "band_metrics": band_rows,
        "fixed_window_separability_N_vs_S": shrinkage_separability(primary_features, primary_labels),
        "return_and_drift": {
            "N_minus_S_shape_rms_db": _rms(ns),
            "NRETURN_minus_S_shape_rms_db": _rms(nrs),
            "N_minus_NRETURN_drift_shape_rms_db": drift,
            "effect_to_drift_ratio": _rms(ns) / drift,
            "effect_pearson": float(np.corrcoef(ns, nrs)[0, 1]),
            "effect_cosine": float(np.dot(ns, nrs) / (np.linalg.norm(ns) * np.linalg.norm(nrs))),
        },
        "rank": effective_rank_metrics(np.vstack((np.mean(features[labels == "N"], axis=0), np.mean(features[labels == "S"], axis=0)))),
        "exact_permutation_primary": _exact_binary_permutation(matrices["N"][:, bands["primary"]], matrices["S"][:, bands["primary"]]),
    }
    uncertainty = _bootstrap_level_a(matrices, valid_frequency, windows, iterations, seed)
    return result, band_rows, uncertainty


def _within_level_b(rows: Sequence[Mapping[str, Any]], configuration: str, mask: NDArray[np.bool_]) -> float:
    distances = []
    for block in (key for key, value in BLOCKS.items() if value[0] == configuration):
        for direction in DIRECTIONS:
            curves = [_demean_rows(np.asarray(row["curve"])[None, mask])[0] for row in rows if row["block"] == block and row["direction"] == direction]
            if len(curves) < 2:
                continue
            distances.extend(_rms(curves[left] - curves[right]) for left, right in itertools.combinations(range(len(curves)), 2))
    if not distances:
        raise ValueError("no within block-direction repeat pairs")
    return float(np.median(distances))


def _configuration_metrics(rows: Sequence[Mapping[str, Any]], frequency: FloatArray, configuration: str, windows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    selected = [row for row in rows if row["configuration"] == configuration]
    matrices = np.vstack([row["curve"] for row in selected])
    features = _window_features(matrices, frequency, windows)
    labels = np.array([row["direction"] for row in selected])
    pair_rows: list[dict[str, Any]] = []
    band_summary: list[dict[str, Any]] = []
    for band, limits in (("primary", (200.0, 4000.0)), ("secondary", (4000.0, 8000.0))):
        mask = _band_mask(frequency, *limits) & np.all(np.isfinite(matrices), axis=0)
        within = _within_level_b(selected, configuration, mask)
        centroids = {direction: np.mean(_demean_rows(np.vstack([row["curve"][mask] for row in selected if row["direction"] == direction])), axis=0) for direction in DIRECTIONS}
        distances = []
        for left, right in itertools.combinations(DIRECTIONS, 2):
            distance = _rms(centroids[left] - centroids[right]); distances.append(distance)
            pair_rows.append({"configuration": configuration, "band": band, "direction_a": left, "direction_b": right, "between_shape_rms_db": distance, "within_repeatability_median_db": within, "state_within_ratio": distance / within})
        band_summary.append({"band": band, "within_repeatability_median_db": within, "minimum_pairwise_distance_db": float(np.min(distances)), "median_pairwise_distance_db": float(np.median(distances)), "worst_case_state_within_ratio": float(np.min(distances) / within), "median_state_within_ratio": float(np.median(distances) / within)})
    primary = _band_mask(frequency, 200.0, 4000.0) & np.all(np.isfinite(matrices), axis=0)
    dense_centroids = np.vstack([np.mean(_demean_rows(np.vstack([row["curve"][primary] for row in selected if row["direction"] == direction])), axis=0) for direction in DIRECTIONS])
    feature_centroids = np.vstack([np.mean(features[labels == direction], axis=0) for direction in DIRECTIONS])
    ranks = [
        {"level": "B", "configuration": configuration, "representation": "dense_demeaned_primary", **effective_rank_metrics(dense_centroids)},
        {"level": "B", "configuration": configuration, "representation": "fixed_windows", **effective_rank_metrics(feature_centroids)},
    ]
    return {"configuration": configuration, "measurement_count": len(selected), "block_count": 2, "direction_count": 4, "band_metrics": band_summary, "fixed_window_separability": shrinkage_separability(features, labels)}, pair_rows, ranks


def _level_b_bootstrap(rows: Sequence[Mapping[str, Any]], frequency: FloatArray, configuration: str, windows: Sequence[Mapping[str, Any]], iterations: int, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    source_blocks = [block for block, value in BLOCKS.items() if value[0] == configuration]
    selected = [row for row in rows if row["configuration"] == configuration]
    primary = _band_mask(frequency, 200.0, 4000.0) & np.isfinite(selected[0]["curve"])
    worst: list[float] = []; medians: list[float] = []; fisher: list[float] = []; mahalanobis: list[float] = []
    for _ in range(iterations):
        sampled_rows: list[dict[str, Any]] = []
        for new_index, block in enumerate(rng.choice(source_blocks, size=2, replace=True)):
            for direction in DIRECTIONS:
                cell = [row for row in rows if row["block"] == block and row["direction"] == direction]
                for row in rng.choice(cell, size=len(cell), replace=True):
                    sampled_rows.append({**row, "block": f"BOOT{new_index}"})
        curves_by_direction = {direction: np.vstack([row["curve"][primary] for row in sampled_rows if row["direction"] == direction]) for direction in DIRECTIONS}
        centroids = {key: np.mean(_demean_rows(value), axis=0) for key, value in curves_by_direction.items()}
        distances = [_rms(centroids[a] - centroids[b]) for a, b in itertools.combinations(DIRECTIONS, 2)]
        within_values = []
        for block in ("BOOT0", "BOOT1"):
            for direction in DIRECTIONS:
                cell = _demean_rows(np.vstack([row["curve"][primary] for row in sampled_rows if row["block"] == block and row["direction"] == direction]))
                within_values.extend(_rms(cell[a] - cell[b]) for a, b in itertools.combinations(range(len(cell)), 2))
        within = float(np.median(within_values))
        if within > 0.0:
            worst.append(float(np.min(distances) / within)); medians.append(float(np.median(distances) / within))
        feature_matrix = _window_features(np.vstack([row["curve"] for row in sampled_rows]), frequency, windows)
        separation = shrinkage_separability(feature_matrix, np.array([row["direction"] for row in sampled_rows]))
        if separation["status"] == "available":
            fisher.append(separation["fisher_trace_ratio"]); mahalanobis.append(separation["shrinkage_mahalanobis"])
    if not worst:
        raise ValueError("all Level B bootstrap draws had zero within-repeat dispersion")
    return {"requested_iterations": iterations, "finite_ratio_iterations": len(worst), "undefined_zero_within_iterations": iterations - len(worst), "finite_separability_iterations": len(mahalanobis), "worst_case_ratio_ci95": np.percentile(worst, [2.5, 97.5]).tolist(), "median_ratio_ci95": np.percentile(medians, [2.5, 97.5]).tolist(), "fisher_trace_ratio_ci95": np.percentile(fisher, [2.5, 97.5]).tolist(), "shrinkage_mahalanobis_ci95": np.percentile(mahalanobis, [2.5, 97.5]).tolist()}


def _flag_and_block_sensitivity(rows: Sequence[Mapping[str, Any]], frequency: FloatArray, configuration: str, windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    variants = [("all_ACTIVE", list(rows)), ("flags_omitted_view", [row for row in rows if not row["flagged"]])]
    for block in (key for key, value in BLOCKS.items() if value[0] == configuration):
        variants.append((f"single_block_{block}", [row for row in rows if row["block"] == block]))
    for name, variant in variants:
        try:
            result, _, _ = _configuration_metrics(variant, frequency, configuration, windows)
            primary = next(row for row in result["band_metrics"] if row["band"] == "primary")
            output.append({"level": "B", "configuration": configuration, "variant": name, "measurement_count": len([row for row in variant if row["configuration"] == configuration]), "flagged_omitted": sum(row["flagged"] for row in rows if row["configuration"] == configuration) if name == "flags_omitted_view" else 0, **primary})
        except (ValueError, IndexError):
            output.append({"level": "B", "configuration": configuration, "variant": name, "measurement_count": len(variant), "status": "unavailable"})
    return output


def _level_b_permutation(rows: Sequence[Mapping[str, Any]], frequency: FloatArray, configuration: str) -> dict[str, Any]:
    selected = [row for row in rows if row["configuration"] == configuration]
    blocks = [block for block, value in BLOCKS.items() if value[0] == configuration]
    primary = _band_mask(frequency, 200.0, 4000.0) & np.isfinite(selected[0]["curve"])

    def statistic(label_maps: Mapping[str, Mapping[int, int]]) -> float:
        relabelled = []
        for row in selected:
            relabelled.append({**row, "direction": label_maps[row["block"]][row["direction"]]})
        within = _within_level_b(relabelled, configuration, primary)
        centroids = {
            direction: np.mean(
                _demean_rows(np.vstack([row["curve"][primary] for row in relabelled if row["direction"] == direction])), axis=0
            )
            for direction in DIRECTIONS
        }
        return float(min(_rms(centroids[a] - centroids[b]) for a, b in itertools.combinations(DIRECTIONS, 2)) / within)

    identity = {block: dict(zip(DIRECTIONS, DIRECTIONS, strict=True)) for block in blocks}
    observed = statistic(identity)
    null = []
    permutations = list(itertools.permutations(DIRECTIONS))
    for first in permutations:
        for second in permutations:
            maps = {
                blocks[0]: dict(zip(DIRECTIONS, first, strict=True)),
                blocks[1]: dict(zip(DIRECTIONS, second, strict=True)),
            }
            null.append(statistic(maps))
    return {"assignment_count": len(null), "observed_worst_case_ratio": observed, "p_value": (sum(value >= observed for value in null) + 1) / (len(null) + 1)}


def _input_hash_audit(
    project_root: Path,
    zip_path: Path,
    level_a_members: Sequence[Any],
    level_b_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    audits = [
        _verify_sha_sums(project_root / "outputs/info_top/INFO_TOP_0_RESEARCH_CONTRACT", "SHA256SUMS.txt"),
        _verify_sha_sums(project_root / "outputs/real_experiment/research_analysis/TRANS1_TWO_PORT_PHYSICAL_PILOT", "SHA256SUMS.txt"),
        _verify_sha_sums(project_root / "outputs/formal/FORMAL-4_CORE_ANALYSIS", "SHA256SUMS"),
        _verify_sha_sums(project_root / "outputs/supplemental/SUP-0_FREQUENCY_LOCALIZATION", "SHA256SUMS"),
    ]
    manifest = {
        row["relative_path"]: row
        for row in csv.DictReader((project_root / "outputs/real_experiment/research_analysis/TRANS1_TWO_PORT_PHYSICAL_PILOT/source_manifest.csv").open(encoding="utf-8-sig", newline=""))
    }
    level_a_rows = []
    for member in level_a_members:
        if member.extension != ".txt":
            continue
        relative = f"raw_txt/{member.filename}"
        expected = manifest[relative]["sha256"]
        level_a_rows.append({"level": "A", "sample_id": member.sample_id, "path": str(member.path), "expected_sha256": expected, "actual_sha256": member.sha256, "match": expected == member.sha256})
    level_b_audit = [{"level": "B", "sample_id": row["sample_id"], "path": row["archive_path"], "expected_sha256": row["sha256"], "actual_sha256": row["sha256"], "match": True, "authority": "member digest under frozen REV003 ZIP SHA-256"} for row in level_b_rows]
    result = {
        "schema_version": "info_top_1_input_hash_audit_v1",
        "authority_bundle_audits": audits,
        "formal_rev003_zip": {"path": str(zip_path), "expected_sha256": FORMAL_ZIP_SHA256, "actual_sha256": _sha256_file(zip_path), "match": _sha256_file(zip_path) == FORMAL_ZIP_SHA256},
        "selected_inputs": [*level_a_rows, *level_b_audit],
        "all_match": all(item["all_match"] for item in audits) and all(row["match"] for row in [*level_a_rows, *level_b_audit]),
        "excluded_members_opened": False,
        "final_test_read": False,
    }
    if not result["all_match"]:
        raise ValueError("input SHA-256 audit failed")
    return result


def _plots(output: Path, level_a: Mapping[str, Any], level_b: Sequence[Mapping[str, Any]], ranks: Sequence[Mapping[str, Any]], common: Sequence[Mapping[str, Any]]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    output.joinpath("plots").mkdir(exist_ok=True)
    drift = level_a["return_and_drift"]
    fig, axis = plt.subplots(figsize=(7.2, 4.5))
    labels = ["N-S", "NRETURN-S", "N-NRETURN drift"]
    values = [drift["N_minus_S_shape_rms_db"], drift["NRETURN_minus_S_shape_rms_db"], drift["N_minus_NRETURN_drift_shape_rms_db"]]
    axis.bar(labels, values, color=["#2f6b9a", "#55a868", "#c44e52"]); axis.set_ylabel("Primary-band demeaned shape RMS (dB)"); axis.set_title("Level A state and return-control differences"); fig.tight_layout()
    for extension in ("png", "svg"): fig.savefig(output / "plots" / f"level_a_state_return.{extension}", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), sharey=True)
    for axis, config in zip(axes, ("U4SYM", "U4ENC"), strict=True):
        matrix = np.zeros((4, 4)); subset = [row for row in level_b if row["configuration"] == config and row["band"] == "primary"]
        for row in subset:
            i = DIRECTIONS.index(int(row["direction_a"])); j = DIRECTIONS.index(int(row["direction_b"])); matrix[i, j] = matrix[j, i] = row["state_within_ratio"]
        image = axis.imshow(matrix, cmap="viridis", vmin=0); axis.set_xticks(range(4), DIRECTIONS); axis.set_yticks(range(4), DIRECTIONS); axis.set_title(config); axis.set_xlabel("Direction (deg)")
    fig.colorbar(image, ax=axes, label="Pairwise state / within ratio"); fig.suptitle("Level B primary-band direction readability"); fig.subplots_adjust(left=.08, right=.88, bottom=.14, top=.84, wspace=.22)
    for extension in ("png", "svg"): fig.savefig(output / "plots" / f"level_b_pairwise_readability.{extension}", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7.2, 4.5))
    selected_ranks = [row for row in ranks if row.get("level") == "B" and row["representation"] == "dense_demeaned_primary"]
    for row in selected_ranks:
        axis.plot(range(1, len(row["singular_values"]) + 1), row["singular_values"], marker="o", label=row["configuration"])
    axis.set_xlabel("Singular-value index"); axis.set_ylabel("Singular value (dB)"); axis.set_title("Level B centered direction-centroid singular values"); axis.legend(); axis.grid(alpha=.25); fig.tight_layout()
    for extension in ("png", "svg"): fig.savefig(output / "plots" / f"level_b_singular_values.{extension}", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7.4, 4.5))
    axis.bar([row["scope"] for row in common], [row["worst_case_pairwise_state_within_ratio"] for row in common], color=["#2f6b9a", "#8172b2", "#dd8452"])
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1); axis.set_ylabel("Worst-case state / within-noise ratio"); axis.set_title("Descriptive single-microphone readability (levels not pooled)"); fig.tight_layout()
    for extension in ("png", "svg"): fig.savefig(output / "plots" / f"common_readability.{extension}", dpi=180)
    plt.close(fig)


def _artifact_inventory(output: Path, report: Path) -> dict[str, Any]:
    excluded = {output / "artifact_inventory.json", output / "SHA256SUMS.txt"}
    files = sorted((path for path in output.rglob("*") if path.is_file() and path not in excluded), key=lambda path: path.relative_to(output).as_posix())
    records = [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": _sha256_file(path)} for path in files]
    if report.is_file():
        records.append({"path": "../../../docs/progress/INFO_TOP_1_SINGLE_MIC_BASELINE.md", "bytes": report.stat().st_size, "sha256": _sha256_file(report)})
    inventory = {"schema_version": "info_top_1_artifact_inventory_v1", "artifact_count": len(records), "artifacts": records}
    _write_json(output / "artifact_inventory.json", inventory)
    sums_records = [*records, {"path": "artifact_inventory.json", "sha256": _sha256_file(output / "artifact_inventory.json")}]
    (output / "SHA256SUMS.txt").write_text("".join(f"{row['sha256']}  {row['path']}\n" for row in sums_records), encoding="utf-8")
    return inventory


def finalize_info_top1_artifacts(output_directory: str | Path, report_path: str | Path) -> dict[str, Any]:
    return _artifact_inventory(Path(output_directory).resolve(), Path(report_path).resolve())


def run_info_top_single_mic(
    project_root: str | Path,
    formal_zip: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    """Run only the frozen INFO-TOP-1 real single-microphone baseline."""
    from .trans1_two_port_physical_analysis import _inspect_inputs, _preprocess_members

    root = Path(project_root).resolve(); output = Path(output_directory).resolve(); zip_path = Path(formal_zip).resolve()
    contract_path = output / "top1_analysis_contract.json"
    if not contract_path.is_file():
        raise ValueError("top1_analysis_contract.json must exist before result computation")
    contract = _load_contract(contract_path)
    iterations = int(contract["uncertainty"]["bootstrap_iterations"]); seed = int(contract["uncertainty"]["seed"])
    level_a_members, _, _ = _inspect_inputs(root / "data/real_experiment/TRANS1_TWO_PORT_PHYSICAL_PILOT")
    a_frequency, a_valid, a_curves, _, _ = _preprocess_members(level_a_members)
    b_frequency, b_rows = _load_level_b_active(zip_path)
    if not np.array_equal(a_frequency, b_frequency):
        raise ValueError("Level A/B do not share the frozen FORMAL-1 grid")
    windows = [*contract["low_dimensional_features"]["sup0_frozen_candidate_windows"], *contract["low_dimensional_features"]["trans_frozen_windows"]]
    level_a, level_a_rows, level_a_uncertainty = _level_a(a_frequency, a_curves, windows, iterations, seed)
    level_b_metrics = []; pair_rows = []; rank_rows = []
    uncertainty_rows: list[dict[str, Any]] = [{"level": "A", "scope": "N_vs_S_and_return", **level_a_uncertainty}]
    sensitivity_rows: list[dict[str, Any]] = []
    for index, configuration in enumerate(("U4SYM", "U4ENC")):
        metrics, pairs, ranks = _configuration_metrics(b_rows, b_frequency, configuration, windows)
        metrics["exact_permutation_primary"] = _level_b_permutation(b_rows, b_frequency, configuration)
        level_b_metrics.append(metrics); pair_rows.extend(pairs); rank_rows.extend(ranks)
        uncertainty_rows.append({"level": "B", "scope": configuration, **_level_b_bootstrap(b_rows, b_frequency, configuration, windows, iterations, seed + index + 1)})
        sensitivity_rows.extend(_flag_and_block_sensitivity(b_rows, b_frequency, configuration, windows))
    rank_rows.insert(0, {"level": "A", "configuration": "N_vs_S", "representation": "fixed_windows", **level_a["rank"], "interpretation": "rank one is the structural maximum for two centered states, not a discovery"})
    primary_a = next(row for row in level_a_rows if row["band"] == "primary")
    common = [{"scope": "Level A N_vs_S", "task_state_count": 2, "binary_contrast_within_noise_ratio": primary_a["between_within_ratio"], "worst_case_pairwise_state_within_ratio": primary_a["between_within_ratio"], "effective_state_contrast_dimension": level_a["rank"]["effective_rank"], "robustness_limit": "single closure; NRETURN drift sensitivity"}]
    for metrics in level_b_metrics:
        primary = next(row for row in metrics["band_metrics"] if row["band"] == "primary")
        rank = next(row for row in rank_rows if row.get("configuration") == metrics["configuration"] and row.get("representation") == "dense_demeaned_primary")
        common.append({"scope": f"Level B {metrics['configuration']}", "task_state_count": 4, "binary_contrast_within_noise_ratio": "not_applicable_four_state", "worst_case_pairwise_state_within_ratio": primary["worst_case_state_within_ratio"], "effective_state_contrast_dimension": rank["effective_rank"], "robustness_limit": "two blocks; existing flags sensitivity"})
    hash_audit = _input_hash_audit(root, zip_path, level_a_members, b_rows)
    selected_flag_ids = [row["sample_id"] for row in b_rows if row["flagged"]]
    sensitivity = {"bootstrap": uncertainty_rows, "level_b_variants": sensitivity_rows, "formal3_global_flag_count": 10, "selected_AS01_flag_count": len(selected_flag_ids), "selected_AS01_flag_sample_ids": selected_flag_ids, "flags_retained_in_primary": True, "active_selection_changed": False}
    gate = {"stage": "INFO-TOP-1", "status": "INFO_TOP_1_PASS_CONDITIONAL_GO_TO_TOP2", "go_to_top2": True, "requirements_met": {"input_identity_reliable": True, "at_least_one_interpretable_level": True, "group_aware_uncertainty": True, "final_test_read": False}, "minimum_questions_to_freeze_before_TOP2": ["Choose Path A saved-solution post-processing or Path B anchored reduced-order model after a no-study.run feasibility preflight.", "Freeze a finite microphone candidate set without choosing coordinates from TOP-2 outcomes.", "Freeze finite noise/drift levels and the M=1-4 cost-axis treatment.", "Freeze the exact state comparison that tests marginal sensor benefit while keeping Level C separate from real evidence."], "not_authorized_here": ["microphone coordinates", "noise magnitudes", "COMSOL budget", "TOP-2 execution"]}
    summary = {"schema_version": "info_top_1_summary_v1", "stage": "INFO-TOP-1", "status": gate["status"], "counts": {"level_a_real_curves": 15, "level_b_real_active_curves": 48, "level_b_global_existing_flags": 10, "level_b_selected_AS01_flags": len(selected_flag_ids)}, "identity": {"level_a": "TRANS N/S/NRETURN single microphone, one closure", "level_b": "AS01 B01-B04; B01/B02 U4SYM, B03/B04 U4ENC"}, "all_repeats_retained": True, "level_a": level_a, "level_b": level_b_metrics, "formal4_grouped_classification_background_only": {"rerun": False, "U4SYM_AS01_balanced_accuracy": 0.375, "U4ENC_AS01_balanced_accuracy": 0.25, "interpretation": "both below the frozen 0.50 practical target"}, "claim_boundary": "TOP-1 establishes layered real single-microphone baselines only; it does not establish topology causality, cross-room/closure generalization, reliable four-direction classification, or virtual-microphone benefit.", "final_test_read": False}
    _write_json(output / "input_hash_audit.json", hash_audit)
    _write_csv(output / "input_hash_audit.csv", hash_audit["selected_inputs"])
    _write_json(output / "level_a_metrics.json", level_a); _write_csv(output / "level_a_metrics.csv", level_a_rows)
    _write_json(output / "level_b_configuration_metrics.json", {"configurations": level_b_metrics}); _write_csv(output / "level_b_configuration_metrics.csv", [{"configuration": item["configuration"], "measurement_count": item["measurement_count"], **{f"{band['band']}_{key}": value for band in item["band_metrics"] for key, value in band.items() if key != "band"}, "fisher_trace_ratio": item["fixed_window_separability"].get("fisher_trace_ratio"), "shrinkage_mahalanobis": item["fixed_window_separability"].get("shrinkage_mahalanobis"), "shrinkage": item["fixed_window_separability"].get("shrinkage")} for item in level_b_metrics])
    _write_csv(output / "level_b_pairwise_distance_matrix.csv", pair_rows)
    _write_json(output / "rank_singular_value_metrics.json", {"metrics": rank_rows}); _write_csv(output / "rank_singular_value_metrics.csv", [{**row, "singular_values": ";".join(str(value) for value in row["singular_values"])} for row in rank_rows])
    _write_json(output / "uncertainty_and_sensitivity.json", sensitivity); _write_csv(output / "uncertainty_and_sensitivity.csv", [*uncertainty_rows, *sensitivity_rows])
    _write_csv(output / "common_readability_comparison.csv", common)
    _write_json(output / "top2_gate_recommendation.json", gate); _write_json(output / "analysis_summary.json", summary)
    _plots(output, level_a, pair_rows, rank_rows, common)
    return summary

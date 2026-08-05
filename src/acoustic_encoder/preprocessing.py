"""Deterministic dense-grid construction, interpolation, and smoothing for P3."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class DenseGrid:
    frequency_hz: FloatArray
    feature_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DenseSmoothingResult:
    values_db: FloatArray
    valid_mask: BoolArray
    definition: Mapping[str, Any]
    input_valid_fraction: float
    output_valid_fraction: float


def _reflect_index(index: int, size: int) -> int:
    if size == 1:
        return 0
    period = 2 * (size - 1)
    position = index % period
    return position if position < size else period - position


def fractional_octave_bounds(
    center_frequency_hz: float,
    fraction_denominator: int,
) -> tuple[float, float]:
    """Return base-two, symmetric-in-log-frequency 1/N-octave bounds."""
    factor = 2.0 ** (1.0 / (2.0 * fraction_denominator))
    return center_frequency_hz / factor, center_frequency_hz * factor


def _valid_segments(mask: BoolArray) -> tuple[tuple[int, int], ...]:
    """Return inclusive bounds for maximal contiguous true runs."""
    padded = np.concatenate(([False], mask, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return tuple(
        (int(start), int(stop - 1))
        for start, stop in zip(changes[::2], changes[1::2], strict=True)
    )


def _smooth_fixed_kernel(
    values: FloatArray,
    mask: BoolArray,
    offsets: NDArray[np.int64],
    weights: FloatArray,
    boundary: str,
    minimum_coverage: float,
) -> tuple[FloatArray, BoolArray, int]:
    output_values = np.full(values.size, np.nan, dtype=np.float64)
    output_mask = np.zeros(values.size, dtype=bool)
    segments = _valid_segments(mask & np.isfinite(values))
    for start, stop in segments:
        segment_size = stop - start + 1
        for index in range(start, stop + 1):
            candidates = index + offsets
            physically_present = (candidates >= start) & (candidates <= stop)
            coverage = float(np.sum(weights[physically_present]))
            if coverage + 1.0e-12 < minimum_coverage:
                continue
            if boundary == "truncate":
                selected_indices = candidates[physically_present]
                selected_weights = weights[physically_present] / coverage
            elif boundary == "reflect":
                selected_indices = np.asarray(
                    [
                        start + _reflect_index(int(item - start), segment_size)
                        for item in candidates
                    ],
                    dtype=np.int64,
                )
                selected_weights = weights
            elif boundary == "nearest":
                selected_indices = np.clip(candidates, start, stop)
                selected_weights = weights
            else:  # pragma: no cover - configuration validation is authoritative
                raise ValueError(f"Unsupported smoothing boundary: {boundary!r}")
            output_values[index] = float(
                np.dot(selected_weights, values[selected_indices])
            )
            output_mask[index] = True
    return output_values, output_mask, len(segments)


def smooth_dense_grid(
    frequency_hz: FloatArray,
    values_db: FloatArray,
    valid_mask: BoolArray,
    preprocessing_config: Mapping[str, Any],
) -> DenseSmoothingResult:
    """Smooth one already-interpolated common grid in the configured dB domain."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    values = np.asarray(values_db, dtype=np.float64)
    mask = np.asarray(valid_mask, dtype=bool)
    if frequency.ndim != 1 or values.ndim != 1 or mask.ndim != 1:
        raise ValueError("dense smoothing inputs must be one-dimensional")
    if not (frequency.size == values.size == mask.size) or frequency.size == 0:
        raise ValueError("dense smoothing inputs must have equal non-zero lengths")
    domain = str(preprocessing_config["smoothing_domain"])
    smoothing = preprocessing_config["smoothing"]
    if not isinstance(smoothing, Mapping):
        raise ValueError("smoothing must be a mapping")
    method = str(smoothing["method"])
    if domain != "db":
        raise ValueError(f"Unsupported smoothing domain: {domain!r}")
    differences = np.diff(frequency)
    if (
        differences.size == 0
        or np.any(~np.isfinite(frequency))
        or np.any(differences <= 0.0)
    ):
        raise ValueError(
            "dense smoothing frequency grid must be finite and strictly increasing"
        )
    if not np.allclose(
        differences,
        differences[0],
        rtol=0.0,
        atol=1.0e-12,
    ):
        raise ValueError("dense smoothing requires a uniform common grid")
    step_hz = float(differences[0])
    if method == "none":
        output_values = values.copy()
        output_mask = mask.copy()
        definition = {
            "algorithm_version": "dense_segment_smoothing_v1",
            "domain": domain,
            "method": method,
            "boundary": None,
            "minimum_kernel_coverage": None,
            "requested": {},
            "effective": {},
        }
    elif method in {"moving_average_linear_hz", "gaussian_linear_hz"}:
        boundary = str(smoothing["boundary"])
        if boundary not in {"truncate", "reflect", "nearest"}:
            raise ValueError(f"Unsupported smoothing boundary: {boundary!r}")
        minimum_coverage = float(smoothing["minimum_kernel_coverage"])
        if method == "moving_average_linear_hz":
            window_hz = float(smoothing["window_hz"])
            requested_samples = max(1, math.ceil(window_hz / step_hz))
            sample_count = (
                requested_samples
                if requested_samples % 2 == 1
                else requested_samples + 1
            )
            radius = (sample_count - 1) // 2
            weights = np.full(sample_count, 1.0 / sample_count)
            requested = {"window_hz": window_hz}
            effective = {
                "grid_step_hz": step_hz,
                "requested_sample_count_before_centering": requested_samples,
                "kernel_sample_count": sample_count,
                "kernel_radius_samples": radius,
                "effective_window_hz": sample_count * step_hz,
                "effective_support_span_hz": (sample_count - 1) * step_hz,
            }
        else:
            sigma_hz = float(smoothing["sigma_hz"])
            truncate_sigma = float(smoothing["truncate_sigma"])
            sigma_grid = sigma_hz / step_hz
            radius = math.ceil(truncate_sigma * sigma_grid)
            offsets_float = np.arange(-radius, radius + 1, dtype=np.float64)
            weights = np.exp(-0.5 * np.square(offsets_float / sigma_grid))
            weights /= np.sum(weights)
            sample_count = weights.size
            requested = {
                "sigma_hz": sigma_hz,
                "truncate_sigma": truncate_sigma,
            }
            effective = {
                "grid_step_hz": step_hz,
                "sigma_grid_samples": sigma_grid,
                "kernel_sample_count": int(sample_count),
                "kernel_radius_samples": radius,
                "effective_kernel_span_hz": 2.0 * radius * step_hz,
                "kernel_weight_sum": float(np.sum(weights)),
            }
        offsets = np.arange(-radius, radius + 1, dtype=np.int64)
        output_values, output_mask, segment_count = _smooth_fixed_kernel(
            values,
            mask,
            offsets,
            weights,
            boundary,
            minimum_coverage,
        )
        definition = {
            "algorithm_version": "dense_segment_smoothing_v1",
            "domain": domain,
            "method": method,
            "boundary": boundary,
            "minimum_kernel_coverage": minimum_coverage,
            "requested": requested,
            "effective": {**effective, "input_valid_segment_count": segment_count},
        }
    elif method == "fractional_octave":
        if np.any(frequency <= 0.0):
            raise ValueError("fractional-octave smoothing requires positive frequencies")
        denominator = int(smoothing["fraction_denominator"])
        boundary = str(smoothing["boundary"])
        minimum_coverage = float(smoothing["minimum_kernel_coverage"])
        weighting = str(smoothing["weighting_definition"])
        output_values = np.full(values.size, np.nan, dtype=np.float64)
        output_mask = np.zeros(values.size, dtype=bool)
        effective_counts = []
        for center in frequency:
            lower, upper = fractional_octave_bounds(float(center), denominator)
            lower_offset = math.ceil((lower - float(center)) / step_hz)
            upper_offset = math.floor((upper - float(center)) / step_hz)
            effective_counts.append(upper_offset - lower_offset + 1)
        segments = _valid_segments(mask & np.isfinite(values))
        for start, stop in segments:
            segment_size = stop - start + 1
            for index in range(start, stop + 1):
                center = float(frequency[index])
                lower, upper = fractional_octave_bounds(center, denominator)
                lower_offset = math.ceil((lower - center) / step_hz)
                upper_offset = math.floor((upper - center) / step_hz)
                offsets = np.arange(
                    lower_offset,
                    upper_offset + 1,
                    dtype=np.int64,
                )
                weights = np.full(offsets.size, 1.0 / offsets.size)
                candidates = index + offsets
                physically_present = (candidates >= start) & (candidates <= stop)
                coverage = float(np.sum(weights[physically_present]))
                if coverage + 1.0e-12 < minimum_coverage:
                    continue
                if boundary == "truncate":
                    selected_indices = candidates[physically_present]
                    selected_weights = weights[physically_present] / coverage
                elif boundary == "reflect":
                    selected_indices = np.asarray(
                        [
                            start + _reflect_index(int(item - start), segment_size)
                            for item in candidates
                        ],
                        dtype=np.int64,
                    )
                    selected_weights = weights
                elif boundary == "nearest":
                    selected_indices = np.clip(candidates, start, stop)
                    selected_weights = weights
                else:
                    raise ValueError(f"Unsupported smoothing boundary: {boundary!r}")
                output_values[index] = float(
                    np.dot(selected_weights, values[selected_indices])
                )
                output_mask[index] = True
        low_bounds = fractional_octave_bounds(float(frequency[0]), denominator)
        high_bounds = fractional_octave_bounds(float(frequency[-1]), denominator)
        definition = {
            "algorithm_version": "dense_segment_smoothing_v1",
            "domain": domain,
            "method": method,
            "boundary": boundary,
            "minimum_kernel_coverage": minimum_coverage,
            "weighting_definition": weighting,
            "formula": {
                "lower_hz": "fc * 2**(-1/(2*N))",
                "upper_hz": "fc * 2**(1/(2*N))",
            },
            "requested": {"fraction_denominator": denominator},
            "effective": {
                "grid_step_hz": step_hz,
                "kernel_sample_count_min": min(effective_counts),
                "kernel_sample_count_max": max(effective_counts),
                "kernel_sample_count_at_low_frequency": effective_counts[0],
                "kernel_sample_count_at_high_frequency": effective_counts[-1],
                "analytic_bounds_at_low_frequency_hz": list(low_bounds),
                "analytic_bounds_at_high_frequency_hz": list(high_bounds),
                "input_valid_segment_count": len(segments),
            },
        }
    else:
        raise NotImplementedError(f"Unsupported smoothing method: {method!r}")
    output_values.setflags(write=False)
    output_mask.setflags(write=False)
    return DenseSmoothingResult(
        values_db=output_values,
        valid_mask=output_mask,
        definition=definition,
        input_valid_fraction=float(np.mean(mask)),
        output_valid_fraction=float(np.mean(output_mask)),
    )


def _decimal(value: Any, name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal number") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be a finite decimal number")
    return parsed


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", ""} else text


def build_dense_grid(config: Mapping[str, Any]) -> DenseGrid:
    low = _decimal(config["analysis_band_hz"][0], "analysis_band_hz low")
    high = _decimal(config["analysis_band_hz"][1], "analysis_band_hz high")
    step = _decimal(config["common_grid_step_hz"], "common_grid_step_hz")
    if not (Decimal(0) < low < high and step > 0):
        raise ValueError("analysis band and grid step must be positive and ordered")
    interval_count = (high - low) / step
    if interval_count != interval_count.to_integral_value():
        raise ValueError(
            "analysis band span must be an exact multiple of common_grid_step_hz"
        )
    count = int(interval_count) + 1
    decimals = tuple(low + step * index for index in range(count))
    frequency = np.asarray([float(value) for value in decimals], dtype=np.float64)
    frequency.setflags(write=False)
    return DenseGrid(
        frequency_hz=frequency,
        feature_names=tuple(
            f"f_{_decimal_text(value)}_hz" for value in decimals
        ),
    )


def interpolate_dense_grid(
    source_frequency_hz: FloatArray,
    source_magnitude_db: FloatArray,
    source_valid_mask: BoolArray,
    target_frequency_hz: FloatArray,
    *,
    method: str,
    maximum_gap_hz: float,
) -> tuple[FloatArray, BoolArray]:
    """Interpolate only between immediate valid neighbors within the gap limit."""
    if method != "linear":
        raise ValueError(f"Unsupported dense interpolation method: {method!r}")
    values = np.full(target_frequency_hz.size, np.nan, dtype=np.float64)
    valid = np.zeros(target_frequency_hz.size, dtype=bool)
    for target_index, target in enumerate(target_frequency_hz):
        right_index = int(np.searchsorted(source_frequency_hz, target))
        if (
            right_index < source_frequency_hz.size
            and source_frequency_hz[right_index] == target
        ):
            if source_valid_mask[right_index]:
                values[target_index] = source_magnitude_db[right_index]
                valid[target_index] = True
            continue
        left_index = right_index - 1
        if left_index < 0 or right_index >= source_frequency_hz.size:
            continue
        if not (
            source_valid_mask[left_index] and source_valid_mask[right_index]
        ):
            continue
        left_frequency = float(source_frequency_hz[left_index])
        right_frequency = float(source_frequency_hz[right_index])
        gap_hz = right_frequency - left_frequency
        if gap_hz > maximum_gap_hz:
            continue
        fraction = (float(target) - left_frequency) / gap_hz
        values[target_index] = (
            float(source_magnitude_db[left_index])
            + fraction
            * (
                float(source_magnitude_db[right_index])
                - float(source_magnitude_db[left_index])
            )
        )
        valid[target_index] = True
    return values, valid


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float, Decimal)):
        return _decimal_text(_decimal(value, "preprocessing value"))
    raise ValueError(
        f"Unsupported preprocessing configuration value: {type(value).__name__}"
    )


def canonical_preprocessing_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return the complete semantic preprocessing config in stable form."""
    smoothing = config["smoothing"]
    if not isinstance(smoothing, Mapping):
        raise ValueError("smoothing must be a mapping")
    canonical_smoothing = (
        {"method": "none"}
        if smoothing.get("method") == "none"
        else _canonical_value(smoothing)
    )
    grid = build_dense_grid(config)
    smoothing_definition = dict(
        smooth_dense_grid(
            grid.frequency_hz,
            np.zeros(grid.frequency_hz.size, dtype=np.float64),
            np.ones(grid.frequency_hz.size, dtype=bool),
            config,
        ).definition
    )
    effective = dict(smoothing_definition.get("effective", {}))
    effective.pop("input_valid_segment_count", None)
    smoothing_definition["effective"] = effective
    return {
        "schema_version": str(config["schema_version"]),
        "provisional": bool(config.get("provisional", True)),
        "analysis_band_hz": [
            _decimal_text(_decimal(value, "analysis_band_hz"))
            for value in config["analysis_band_hz"]
        ],
        "common_grid_step_hz": _decimal_text(
            _decimal(config["common_grid_step_hz"], "common_grid_step_hz")
        ),
        "interpolation": str(config["interpolation"]),
        "maximum_interpolation_gap_hz": _decimal_text(
            _decimal(
                config["maximum_interpolation_gap_hz"],
                "maximum_interpolation_gap_hz",
            )
        ),
        "minimum_valid_grid_fraction": _decimal_text(
            _decimal(
                config["minimum_valid_grid_fraction"],
                "minimum_valid_grid_fraction",
            )
        ),
        "normalization_band_hz": [
            _decimal_text(_decimal(value, "normalization_band_hz"))
            for value in config["normalization_band_hz"]
        ],
        "minimum_normalization_points": _decimal_text(
            _decimal(
                config["minimum_normalization_points"],
                "minimum_normalization_points",
            )
        ),
        "minimum_zscore_std_db": _decimal_text(
            _decimal(config["minimum_zscore_std_db"], "minimum_zscore_std_db")
        ),
        "smoothing_domain": str(config["smoothing_domain"]),
        "smoothing": canonical_smoothing,
        "smoothing_definition": _canonical_value(smoothing_definition),
    }


def preprocessing_id(config: Mapping[str, Any]) -> str:
    payload = canonical_preprocessing_config(config)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

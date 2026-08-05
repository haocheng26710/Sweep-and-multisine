"""Deterministic dense-spectrum grid construction for P3."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class DenseGrid:
    frequency_hz: FloatArray
    feature_names: tuple[str, ...]


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
        "smoothing": canonical_smoothing,
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

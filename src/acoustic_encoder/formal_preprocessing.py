"""Frozen FORMAL-1 preprocessing for confirmatory REW Sweep analysis.

This module is intentionally separate from the legacy P3 linear-Hz software-
validation path.  Its contract is the rev-002 protocol, not a convenience
default: callers must provide every frozen field and any mismatch fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from .schemas import MeasurementMode, Representation, SpectrumData, artifact_sha256


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

FORMAL_PREPROCESSING_ALGORITHM_VERSION = "formal_log_grid_v1"
_MAXIMUM_INTERPOLATION_GAP_OCTAVES = 2.0 / 48.0

_FROZEN_CONTRACT: dict[str, Any] = {
    "grid_type": "logarithmic",
    "points_per_octave": 48,
    "frequency_min_hz": 200.0,
    "frequency_max_hz": 8000.0,
    "primary_band_hz": [200.0, 4000.0],
    "secondary_band_hz": [4000.0, 8000.0],
    "smoothing_fraction_octave": "1/12",
}


class FormalPreprocessingContractError(ValueError):
    """Raised when a formal-analysis caller departs from rev-002."""


@dataclass(frozen=True, slots=True)
class FormalPreprocessingResult:
    """One auditable smoothed common-grid result for a formal Sweep."""

    frequency_hz: FloatArray
    magnitude_db: FloatArray
    valid_mask: BoolArray
    primary_band_mask: BoolArray
    secondary_band_mask: BoolArray
    manifest: Mapping[str, Any]


def frozen_formal_preprocessing_contract() -> dict[str, Any]:
    """Return a mutable copy of the one accepted rev-002 contract."""
    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in _FROZEN_CONTRACT.items()
    }


def _validate_contract(contract: Mapping[str, Any]) -> None:
    missing = [key for key in _FROZEN_CONTRACT if key not in contract]
    if missing:
        raise FormalPreprocessingContractError(
            f"formal preprocessing contract missing fields: {missing}"
        )
    unexpected = sorted(set(contract) - set(_FROZEN_CONTRACT))
    if unexpected:
        raise FormalPreprocessingContractError(
            f"formal preprocessing contract has unexpected fields: {unexpected}"
        )
    for key, expected in _FROZEN_CONTRACT.items():
        if contract[key] != expected:
            raise FormalPreprocessingContractError(
                f"{key} must equal frozen rev-002 value {expected!r}; "
                f"received {contract[key]!r}"
            )


def build_formal_log_grid(contract: Mapping[str, Any]) -> FloatArray:
    """Build ``f_n = 200 * 2**(n/48)`` while ``f_n <= 8000``.

    The grid is not distorted to force 4000 or 8000 Hz onto the lattice.
    Band membership uses inclusive numeric intervals as required by rev-002.
    """
    _validate_contract(contract)
    minimum = float(contract["frequency_min_hz"])
    maximum = float(contract["frequency_max_hz"])
    points_per_octave = int(contract["points_per_octave"])
    last_index = math.floor(points_per_octave * math.log2(maximum / minimum))
    indices = np.arange(last_index + 1, dtype=np.float64)
    frequency = minimum * np.exp2(indices / points_per_octave)
    frequency.setflags(write=False)
    return frequency


def _canonical_json_bytes(value: Any) -> bytes:
    def json_default(item: Any) -> Any:
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        if hasattr(item, "value"):
            return item.value
        raise TypeError(f"not JSON serializable: {type(item).__name__}")

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=json_default,
        allow_nan=False,
    ).encode("utf-8")


def _update_array_digest(digest: Any, name: str, array: NDArray[Any]) -> None:
    normalized = np.ascontiguousarray(array)
    digest.update(name.encode("utf-8"))
    digest.update(str(normalized.dtype).encode("ascii"))
    digest.update(_canonical_json_bytes(list(normalized.shape)))
    digest.update(normalized.tobytes(order="C"))


def _input_sha256(spectrum: SpectrumData) -> str:
    digest = hashlib.sha256()
    magnitude = np.asarray(spectrum.magnitude_db, dtype="<f8").copy()
    magnitude[~spectrum.valid_mask] = np.nan
    _update_array_digest(digest, "frequency_hz", np.asarray(spectrum.frequency_hz, dtype="<f8"))
    _update_array_digest(digest, "magnitude_db", magnitude)
    _update_array_digest(digest, "valid_mask", np.asarray(spectrum.valid_mask, dtype=np.uint8))
    digest.update(
        _canonical_json_bytes(
            {
                "representation": spectrum.representation.value,
                "phase_status": spectrum.phase_status.value,
                "magnitude_quantity": spectrum.magnitude_quantity,
                "magnitude_reference": spectrum.magnitude_reference,
                "quality_metrics": spectrum.quality_metrics,
                "meta": spectrum.meta.to_dict(),
            }
        )
    )
    return digest.hexdigest()


def _output_sha256(
    frequency_hz: FloatArray,
    magnitude_db: FloatArray,
    valid_mask: BoolArray,
) -> str:
    digest = hashlib.sha256()
    normalized_magnitude = np.asarray(magnitude_db, dtype="<f8").copy()
    normalized_magnitude[~valid_mask] = np.nan
    _update_array_digest(digest, "frequency_hz", np.asarray(frequency_hz, dtype="<f8"))
    _update_array_digest(digest, "magnitude_db", normalized_magnitude)
    _update_array_digest(digest, "valid_mask", np.asarray(valid_mask, dtype=np.uint8))
    return digest.hexdigest()


def _source_segments(
    spectrum: SpectrumData,
    frequency_min_hz: float,
    frequency_max_hz: float,
) -> tuple[tuple[int, int], ...]:
    frequency = spectrum.frequency_hz
    valid = (
        spectrum.valid_mask
        & np.isfinite(spectrum.magnitude_db)
        & (frequency >= frequency_min_hz)
        & (frequency <= frequency_max_hz)
    )
    segments: list[tuple[int, int]] = []
    start: int | None = None
    previous: int | None = None
    for index in range(frequency.size):
        if not valid[index]:
            if start is not None and previous is not None:
                segments.append((start, previous))
            start = None
            previous = None
            continue
        if previous is not None:
            gap_octaves = math.log2(float(frequency[index] / frequency[previous]))
            if gap_octaves > _MAXIMUM_INTERPOLATION_GAP_OCTAVES + 1.0e-12:
                if start is not None:
                    segments.append((start, previous))
                start = index
        elif start is None:
            start = index
        previous = index
    if start is not None and previous is not None:
        segments.append((start, previous))
    return tuple(segments)


def _interpolate_by_valid_segment(
    spectrum: SpectrumData,
    target_frequency_hz: FloatArray,
    *,
    frequency_min_hz: float,
    frequency_max_hz: float,
) -> tuple[FloatArray, BoolArray, int]:
    values = np.full(target_frequency_hz.size, np.nan, dtype=np.float64)
    valid = np.zeros(target_frequency_hz.size, dtype=bool)
    segments = _source_segments(
        spectrum,
        frequency_min_hz,
        frequency_max_hz,
    )
    target_log = np.log2(target_frequency_hz)
    for start, stop in segments:
        source_frequency = spectrum.frequency_hz[start : stop + 1]
        source_values = spectrum.magnitude_db[start : stop + 1]
        if source_frequency.size == 1:
            matches = np.flatnonzero(
                np.isclose(target_frequency_hz, source_frequency[0], rtol=1.0e-12, atol=0.0)
            )
            if matches.size:
                values[matches[0]] = source_values[0]
                valid[matches[0]] = True
            continue
        selected = (target_frequency_hz >= source_frequency[0]) & (
            target_frequency_hz <= source_frequency[-1]
        )
        values[selected] = np.interp(
            target_log[selected],
            np.log2(source_frequency),
            source_values,
        )
        valid[selected] = True
    return values, valid, len(segments)


def _valid_segments(mask: BoolArray) -> tuple[tuple[int, int], ...]:
    padded = np.concatenate(([False], mask, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return tuple(
        (int(start), int(stop - 1))
        for start, stop in zip(changes[::2], changes[1::2], strict=True)
    )


def _smooth_one_twelfth_octave_db(
    frequency_hz: FloatArray,
    values_db: FloatArray,
    valid_mask: BoolArray,
) -> tuple[FloatArray, BoolArray, int]:
    """Rectangular 1/12-octave mean in dB, truncated within each valid run."""
    output = np.full(values_db.size, np.nan, dtype=np.float64)
    output_valid = np.zeros(values_db.size, dtype=bool)
    segments = _valid_segments(valid_mask & np.isfinite(values_db))
    half_width_octaves = 1.0 / 24.0
    factor = 2.0**half_width_octaves
    for start, stop in segments:
        segment_frequency = frequency_hz[start : stop + 1]
        for index in range(start, stop + 1):
            center = float(frequency_hz[index])
            local = (segment_frequency >= center / factor) & (
                segment_frequency <= center * factor
            )
            selected = values_db[start : stop + 1][local]
            if selected.size:
                output[index] = float(np.mean(selected))
                output_valid[index] = True
    return output, output_valid, len(segments)


def preprocess_formal_sweep(
    spectrum: SpectrumData,
    contract: Mapping[str, Any],
) -> FormalPreprocessingResult:
    """Interpolate and smooth one Sweep under the exact rev-002 contract."""
    target = build_formal_log_grid(contract)
    if spectrum.meta.measurement_mode is not MeasurementMode.REW_SWEEP:
        raise FormalPreprocessingContractError(
            "formal preprocessing accepts only measurement_mode='rew_sweep'"
        )
    if spectrum.representation is not Representation.DENSE_SPECTRUM:
        raise FormalPreprocessingContractError(
            "formal preprocessing accepts only representation='dense_spectrum'"
        )
    interpolated, interpolated_valid, source_segment_count = _interpolate_by_valid_segment(
        spectrum,
        target,
        frequency_min_hz=float(contract["frequency_min_hz"]),
        frequency_max_hz=float(contract["frequency_max_hz"]),
    )
    smoothed, output_valid, smoothed_segment_count = _smooth_one_twelfth_octave_db(
        target,
        interpolated,
        interpolated_valid,
    )
    primary_low, primary_high = contract["primary_band_hz"]
    secondary_low, secondary_high = contract["secondary_band_hz"]
    primary = (target >= primary_low) & (target <= primary_high)
    secondary = (target >= secondary_low) & (target <= secondary_high)
    manifest = {
        **frozen_formal_preprocessing_contract(),
        "preprocessing_algorithm_version": FORMAL_PREPROCESSING_ALGORITHM_VERSION,
        "processing_order": [
            "select_200_8000_hz",
            "interpolate_log_common_grid",
            "smooth_1_12_octave_db",
        ],
        "interpolation": {
            "domain": "log2_frequency",
            "method": "linear_magnitude_db",
            "maximum_gap_octaves": _MAXIMUM_INTERPOLATION_GAP_OCTAVES,
            "source_valid_segment_count": source_segment_count,
            "invalid_and_missing_ranges_are_barriers": True,
        },
        "smoothing": {
            "domain": "db",
            "weighting": "rectangular_equal_grid_point",
            "boundary": "truncate_within_valid_segment",
            "continuous_valid_segment_count": smoothed_segment_count,
            "lower_bound_formula": "fc * 2**(-1/24)",
            "upper_bound_formula": "fc * 2**(1/24)",
        },
        "grid_point_count": int(target.size),
        "valid_grid_point_count": int(np.count_nonzero(output_valid)),
        "input_sha256": _input_sha256(spectrum),
        "output_sha256": _output_sha256(target, smoothed, output_valid),
    }
    for array in (smoothed, output_valid, primary, secondary):
        array.setflags(write=False)
    return FormalPreprocessingResult(
        frequency_hz=target,
        magnitude_db=smoothed,
        valid_mask=output_valid,
        primary_band_mask=primary,
        secondary_band_mask=secondary,
        manifest=manifest,
    )


def write_formal_preprocessing_result(
    result: FormalPreprocessingResult,
    output_directory: str | Path,
) -> dict[str, Path]:
    """Write one immutable result directory and return its artifact paths."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"formal preprocessing output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    spectrum_path = output / "formal_spectrum.npz"
    manifest_path = output / "preprocessing_manifest.json"
    artifact_manifest_path = output / "artifact_manifest.json"
    np.savez(
        spectrum_path,
        frequency_hz=result.frequency_hz,
        magnitude_db=result.magnitude_db,
        valid_mask=result.valid_mask,
        primary_band_mask=result.primary_band_mask,
        secondary_band_mask=result.secondary_band_mask,
    )
    manifest_path.write_bytes(_canonical_json_bytes(result.manifest) + b"\n")
    artifacts = {
        "schema_version": "1.0.0",
        "artifacts": [
            {
                "path": spectrum_path.name,
                "sha256": artifact_sha256(spectrum_path),
            },
            {
                "path": manifest_path.name,
                "sha256": artifact_sha256(manifest_path),
            },
        ],
    }
    artifact_manifest_path.write_bytes(_canonical_json_bytes(artifacts) + b"\n")
    return {
        "spectrum": spectrum_path,
        "manifest": manifest_path,
        "artifact_manifest": artifact_manifest_path,
    }

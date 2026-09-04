"""Numerical excerpts from src/acoustic_encoder/formal_preprocessing.py.
Original interpolation and smoothing definitions preserved.
Dependencies: NumPy; SciPy and scikit-learn where imported. No simulation runs on import.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import csv
import math
from typing import Any
from typing import Mapping
import numpy as np
from numpy.typing import NDArray
FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]
_MAXIMUM_INTERPOLATION_GAP_OCTAVES = 2.0 / 48.0
_FROZEN_CONTRACT: dict[str, Any] = {'grid_type': 'logarithmic', 'points_per_octave': 48, 'frequency_min_hz': 200.0, 'frequency_max_hz': 8000.0, 'primary_band_hz': [200.0, 4000.0], 'secondary_band_hz': [4000.0, 8000.0], 'smoothing_fraction_octave': '1/12'}

class FormalPreprocessingContractError(ValueError):
    """Raised when a formal-analysis caller departs from rev-002."""

def _validate_contract(contract: Mapping[str, Any]) -> None:
    missing = [key for key in _FROZEN_CONTRACT if key not in contract]
    if missing:
        raise FormalPreprocessingContractError(f'formal preprocessing contract missing fields: {missing}')
    unexpected = sorted(set(contract) - set(_FROZEN_CONTRACT))
    if unexpected:
        raise FormalPreprocessingContractError(f'formal preprocessing contract has unexpected fields: {unexpected}')
    for key, expected in _FROZEN_CONTRACT.items():
        if contract[key] != expected:
            raise FormalPreprocessingContractError(f'{key} must equal frozen rev-002 value {expected!r}; received {contract[key]!r}')

def build_formal_log_grid(contract: Mapping[str, Any]) -> FloatArray:
    """Build ``f_n = 200 * 2**(n/48)`` while ``f_n <= 8000``.

    The grid is not distorted to force 4000 or 8000 Hz onto the lattice.
    Band membership uses inclusive numeric intervals as required by rev-002.
    """
    _validate_contract(contract)
    minimum = float(contract['frequency_min_hz'])
    maximum = float(contract['frequency_max_hz'])
    points_per_octave = int(contract['points_per_octave'])
    last_index = math.floor(points_per_octave * math.log2(maximum / minimum))
    indices = np.arange(last_index + 1, dtype=np.float64)
    frequency = minimum * np.exp2(indices / points_per_octave)
    frequency.setflags(write=False)
    return frequency

def _source_segments(spectrum: SpectrumData, frequency_min_hz: float, frequency_max_hz: float) -> tuple[tuple[int, int], ...]:
    frequency = spectrum.frequency_hz
    valid = spectrum.valid_mask & np.isfinite(spectrum.magnitude_db) & (frequency >= frequency_min_hz) & (frequency <= frequency_max_hz)
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
            if gap_octaves > _MAXIMUM_INTERPOLATION_GAP_OCTAVES + 1e-12:
                if start is not None:
                    segments.append((start, previous))
                start = index
        elif start is None:
            start = index
        previous = index
    if start is not None and previous is not None:
        segments.append((start, previous))
    return tuple(segments)

def _interpolate_by_valid_segment(spectrum: SpectrumData, target_frequency_hz: FloatArray, *, frequency_min_hz: float, frequency_max_hz: float) -> tuple[FloatArray, BoolArray, int]:
    values = np.full(target_frequency_hz.size, np.nan, dtype=np.float64)
    valid = np.zeros(target_frequency_hz.size, dtype=bool)
    segments = _source_segments(spectrum, frequency_min_hz, frequency_max_hz)
    target_log = np.log2(target_frequency_hz)
    for start, stop in segments:
        source_frequency = spectrum.frequency_hz[start:stop + 1]
        source_values = spectrum.magnitude_db[start:stop + 1]
        if source_frequency.size == 1:
            matches = np.flatnonzero(np.isclose(target_frequency_hz, source_frequency[0], rtol=1e-12, atol=0.0))
            if matches.size:
                values[matches[0]] = source_values[0]
                valid[matches[0]] = True
            continue
        selected = (target_frequency_hz >= source_frequency[0]) & (target_frequency_hz <= source_frequency[-1])
        values[selected] = np.interp(target_log[selected], np.log2(source_frequency), source_values)
        valid[selected] = True
    return (values, valid, len(segments))

def _valid_segments(mask: BoolArray) -> tuple[tuple[int, int], ...]:
    padded = np.concatenate(([False], mask, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return tuple(((int(start), int(stop - 1)) for start, stop in zip(changes[::2], changes[1::2], strict=True)))

def _smooth_one_twelfth_octave_db(frequency_hz: FloatArray, values_db: FloatArray, valid_mask: BoolArray) -> tuple[FloatArray, BoolArray, int]:
    """Rectangular 1/12-octave mean in dB, truncated within each valid run."""
    output = np.full(values_db.size, np.nan, dtype=np.float64)
    output_valid = np.zeros(values_db.size, dtype=bool)
    segments = _valid_segments(valid_mask & np.isfinite(values_db))
    half_width_octaves = 1.0 / 24.0
    factor = 2.0 ** half_width_octaves
    for start, stop in segments:
        segment_frequency = frequency_hz[start:stop + 1]
        for index in range(start, stop + 1):
            center = float(frequency_hz[index])
            local = (segment_frequency >= center / factor) & (segment_frequency <= center * factor)
            selected = values_db[start:stop + 1][local]
            if selected.size:
                output[index] = float(np.mean(selected))
                output_valid[index] = True
    return (output, output_valid, len(segments))

@dataclass
class SpectrumData:
    """Magnitude-only REW data used by the original interpolation functions."""
    frequency_hz: np.ndarray
    magnitude_db: np.ndarray
    valid_mask: np.ndarray

def read_rew(path):
    """Read unchanged numeric samples from an English UTF-8 REW export."""
    with Path(path).open(encoding="utf-8-sig") as handle:
        data = np.loadtxt((line for line in handle if line.strip() and not line.startswith("*")), dtype=np.float64)
    if data.ndim != 2 or data.shape[1] != 2 or not np.isfinite(data).all() or not np.all(np.diff(data[:, 0]) > 0):
        raise ValueError(f"Invalid REW magnitude export: {path}")
    return SpectrumData(data[:, 0], data[:, 1], np.ones(len(data), dtype=bool))

def preprocess_rew(path):
    """Apply the frozen log-frequency interpolation then 1/12-octave dB mean."""
    spectrum = read_rew(path)
    frequency = build_formal_log_grid(_FROZEN_CONTRACT)
    values, valid, _ = _interpolate_by_valid_segment(spectrum, frequency, frequency_min_hz=200.0, frequency_max_hz=8000.0)
    smoothed, mask, _ = _smooth_one_twelfth_octave_db(frequency, values, valid)
    return frequency, smoothed, mask

def load_measurements(data_dir):
    """Load retained curves by sample identity; selection is read from sample tables."""
    data_dir = Path(data_dir)
    with (data_dir / "samples.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    curves = {}
    for row in rows:
        if not row["file"]:
            continue
        f, y, mask = preprocess_rew(data_dir / row["file"])
        if curves and (not np.array_equal(f, frequency) or not np.array_equal(mask, valid)):
            raise ValueError("Measurement grids or masks differ")
        frequency, valid = f, mask
        curves[row["sample_id"]] = y
    return frequency, valid, curves, rows

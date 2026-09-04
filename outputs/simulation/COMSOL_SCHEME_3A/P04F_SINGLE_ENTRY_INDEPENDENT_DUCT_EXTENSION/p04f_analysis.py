"""Frozen pure analysis helpers for P04F RETRY_01."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

ORIGINAL_CHAMBER_AIR_MM3 = math.pi * 18.0**2 * 9.2
ALLOWED_EXTENSIONS_MM = (0, 5, 10)
WALL_THICKNESS_MM = 1.2
CHANNEL_HALF_WIDTH_MM = 4.0
WALL_OUTER_EDGE_MM = CHANNEL_HALF_WIDTH_MM + WALL_THICKNESS_MM
WELL_RADIUS_MM = 4.5


def _validate(extension_mm: int) -> None:
    if extension_mm not in ALLOWED_EXTENSIONS_MM:
        raise ValueError("extension outside frozen P04F states")


def wall_volume_mm3(extension_mm: int) -> float:
    _validate(extension_mm)
    return 4.0 * 2.0 * WALL_THICKNESS_MM * float(extension_mm) * 9.2


def remaining_chamber_air_mm3(extension_mm: int) -> float:
    return ORIGINAL_CHAMBER_AIR_MM3 - wall_volume_mm3(extension_mm)


def analytic_clearances_mm(extension_mm: int) -> dict[str, float]:
    _validate(extension_mm)
    mixing_radius = 17.0 - float(extension_mm)
    if extension_mm == 0:
        return {"wall_to_wall_mm": math.inf, "wall_to_well_mm": math.inf}
    return {
        "wall_to_wall_mm": math.sqrt(2.0) * (mixing_radius - WALL_OUTER_EDGE_MM),
        "wall_to_well_mm": math.hypot(CHANNEL_HALF_WIDTH_MM, mixing_radius) - WELL_RADIUS_MM,
    }


def strict_peak_indices(frequency_hz: np.ndarray, energy: np.ndarray) -> list[int]:
    if frequency_hz.size != energy.size or frequency_hz.size < 3:
        raise ValueError("peak arrays must have equal length >=3")
    values = np.log10(np.asarray(energy, dtype=float))
    return [i for i in range(1, values.size - 1) if values[i] > values[i - 1] and values[i] >= values[i + 1]]


def refine_peak(frequency_hz: np.ndarray, energy: np.ndarray, index: int) -> dict[str, Any]:
    sampled = float(frequency_hz[index])
    x = np.log2(np.asarray(frequency_hz[index - 1:index + 2], dtype=float))
    y = np.log10(np.asarray(energy[index - 1:index + 2], dtype=float))
    a, b, _ = np.polyfit(x, y, 2)
    vertex = -b / (2.0 * a) if a != 0.0 else math.nan
    accepted = bool(np.isfinite(vertex) and a < 0.0 and x[0] < vertex < x[2])
    return {"sampled_frequency_hz": sampled,
            "refined_frequency_hz": float(2.0**vertex) if accepted else sampled,
            "accepted": accepted}


def half_power_q(frequency_hz: np.ndarray, energy: np.ndarray, index: int) -> dict[str, float]:
    f = np.asarray(frequency_hz, float)
    e = np.asarray(energy, float)
    half = e[index] / 2.0
    left = next((j for j in range(index - 1, -1, -1) if e[j] <= half), None)
    right = next((j for j in range(index + 1, e.size) if e[j] <= half), None)
    if left is None or right is None:
        return {"lower_hz": math.nan, "upper_hz": math.nan, "q": math.nan}
    def crossing(a: int, b: int) -> float:
        return float(f[a] + (half - e[a]) * (f[b] - f[a]) / (e[b] - e[a]))
    lo = crossing(left, left + 1)
    hi = crossing(right, right - 1)
    return {"lower_hz": lo, "upper_hz": hi, "q": float(f[index] / (hi - lo))}


def wrap_phase_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def branch_cost(left: dict[str, float], right: dict[str, float]) -> float:
    df = min(abs(math.log2(right["frequency_hz"] / left["frequency_hz"])) / 0.5, 2.0)
    dp = min(abs(right["cavity_module_participation"] - left["cavity_module_participation"]) / 0.5, 2.0)
    dk = min(abs(right["kinetic_fraction"] - left["kinetic_fraction"]) / 0.5, 2.0)
    phase = abs(wrap_phase_deg(right["cavity_chamber_phase_deg"] - left["cavity_chamber_phase_deg"])) / 180.0
    return 0.40 * df + 0.30 * dp + 0.15 * dk + 0.15 * phase


def octave_distance(frequency_hz: float, reference_hz: float) -> float:
    return math.log2(frequency_hz / reference_hz)

"""Frozen pure analysis utilities for P04E."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

RADIUS_MM = 18.0
HEIGHT_MM = 9.2
MIN_CORRIDOR_WIDTH_MM = 8.0
WELL_DIAMETER_MM = 9.0
ORIGINAL_VOLUME_MM3 = math.pi * RADIUS_MM**2 * HEIGHT_MM
ISOLATED_FULL_TV_FINE_HZ = 1904.1942270911
BASELINE_INTEGRATED_HZ = 1650.4014917042427


def retained_plan_area_mm2(width_mm: float) -> float:
    """Area of two orthogonal strips intersected with the radius-18 disk.

    For every permitted width (>=8 mm), the diameter-9 mm well lies entirely
    inside the strip union, so it adds no separate area.
    """
    if not MIN_CORRIDOR_WIDTH_MM <= width_mm <= 2.0 * RADIUS_MM:
        raise ValueError("corridor width outside frozen geometric bounds")
    a = width_mm / 2.0
    strip_primitive = a * math.sqrt(RADIUS_MM**2 - a**2) + RADIUS_MM**2 * math.asin(a / RADIUS_MM)
    return 4.0 * strip_primitive - width_mm**2


def retained_volume_mm3(width_mm: float) -> float:
    return retained_plan_area_mm2(width_mm) * HEIGHT_MM


def solve_corridor_width(target_volume_mm3: float) -> float:
    """Deterministic monotonic bisection, independent of acoustic results."""
    # All frozen targets lie below width=R, where the strip intersection is
    # exactly the central square used by retained_plan_area_mm2().
    low, high = MIN_CORRIDOR_WIDTH_MM, RADIUS_MM
    if not retained_volume_mm3(low) <= target_volume_mm3 <= retained_volume_mm3(high):
        raise ValueError("target volume is geometrically unreachable")
    for _ in range(100):
        mid = (low + high) / 2.0
        if retained_volume_mm3(mid) < target_volume_mm3:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


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
    return {
        "sampled_frequency_hz": sampled,
        "refined_frequency_hz": float(2.0**vertex) if accepted else sampled,
        "accepted": accepted,
        "reason": "finite_concave_interior_vertex" if accepted else "sample_retained_invalid_vertex",
    }


def wrap_phase_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def branch_cost(left: dict[str, float], right: dict[str, float]) -> float:
    """Frozen continuity cost; no distance-to-1904 term is present."""
    df = min(abs(math.log2(right["frequency_hz"] / left["frequency_hz"])) / 0.5, 2.0)
    dp = min(abs(right["cavity_module_participation"] - left["cavity_module_participation"]) / 0.5, 2.0)
    dk = min(abs(right["kinetic_fraction"] - left["kinetic_fraction"]) / 0.5, 2.0)
    phase = abs(wrap_phase_deg(right["cavity_chamber_phase_deg"] - left["cavity_chamber_phase_deg"])) / 180.0
    return 0.40 * df + 0.30 * dp + 0.15 * dk + 0.15 * phase


def octave_distance(frequency_hz: float, reference_hz: float) -> float:
    return math.log2(frequency_hz / reference_hz)

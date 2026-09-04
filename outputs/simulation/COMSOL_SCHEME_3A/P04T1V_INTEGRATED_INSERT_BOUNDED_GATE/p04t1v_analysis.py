"""Frozen pure-analysis contract for the P04T1V bounded gate."""

from __future__ import annotations

import math

import numpy as np


REGULAR_HZ = np.arange(1400.0, 2100.0 + 0.1, 25.0)
PRIMARY_HZ = 1646.88357862959
SECONDARY_HZ = 1986.97249931757
FREQUENCIES_HZ = np.array(sorted(np.concatenate((REGULAR_HZ, [PRIMARY_HZ, SECONDARY_HZ]))))
REPEATABILITY_FLOOR_DB = 1.396

VARIANTS = {
    "I75": {
        "cross_width_mm": 13.52333744142368,
        "outer_radius_mm": 17.9,
        "relief_diameter_mm": 20.4,
        "relief_depth_mm": 0.7,
        "retained_air_fraction": 0.758260419817217,
    },
    "I50P": {
        "cross_width_mm": 8.6,
        "outer_radius_mm": 17.9,
        "relief_diameter_mm": 20.4,
        "relief_depth_mm": 0.7,
        "retained_air_fraction": 0.540587057876302,
    },
}


def wrap_phase_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def complex_effect(inserted: complex, baseline: complex) -> dict[str, float]:
    if abs(baseline) == 0 or not all(np.isfinite([inserted.real, inserted.imag, baseline.real, baseline.imag])):
        return {"magnitude_change_db": math.nan, "phase_difference_deg": math.nan}
    ratio = inserted / baseline
    return {
        "magnitude_change_db": 20.0 * math.log10(abs(ratio)),
        "phase_difference_deg": wrap_phase_deg(math.degrees(math.atan2(ratio.imag, ratio.real))),
    }


def classify(*, technical_i75: bool, technical_i50p: bool,
             branch_unique_i75: bool, branch_unique_i50p: bool,
             branch_hz: list[float], i75_primary_db: float,
             i75_secondary_db: float, finite: bool) -> str:
    base_hz, i75_hz, i50p_hz = branch_hz
    i75_pass = all((
        technical_i75,
        branch_unique_i75,
        finite,
        np.isfinite(base_hz),
        np.isfinite(i75_hz),
        base_hz < i75_hz,
        i75_primary_db < 0.0,
        i75_secondary_db > 0.0,
        abs(i75_primary_db) > REPEATABILITY_FLOOR_DB,
        abs(i75_secondary_db) > REPEATABILITY_FLOOR_DB,
    ))
    if not i75_pass:
        return "P04T1V PRINT_GATE_FAILED"
    i50p_pass = all((
        technical_i50p,
        branch_unique_i50p,
        finite,
        np.isfinite(i50p_hz),
        i75_hz < i50p_hz,
    ))
    if not i50p_pass:
        return "P04T1V I75_PASS_I50P_NOT_AUTHORIZED"
    return "P04T1V PASS_FOR_PRINT_AND_P04T2"

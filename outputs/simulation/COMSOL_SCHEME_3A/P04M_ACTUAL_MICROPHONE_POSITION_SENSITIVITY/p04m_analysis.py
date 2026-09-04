"""Frozen pure-analysis helpers for P04M."""

from __future__ import annotations

import math

import numpy as np


REGULAR_HZ = np.arange(1400.0, 2100.0 + 0.1, 25.0)
LANDMARKS_HZ = np.array([1646.88357862959, 1986.97249931757])
FREQUENCIES_HZ = np.array(sorted(np.concatenate((REGULAR_HZ, LANDMARKS_HZ))))
PRIMARY_HZ = 1646.88357862959
SECONDARY_HZ = 1986.97249931757
EXPERIMENTAL_LOCAL_P95_DB = 1.396

MIC_ACTUAL_Z_M = 0.001
MIC_LEGACY_Z_M = 0.007
MIC_FACE_RADIUS_M = 0.0044
MIC_FACE_AREA_M2 = math.pi * MIC_FACE_RADIUS_M**2
P03_AIR_BORE_RADIUS_M = 0.0045
P03_OUTER_NECK_RADIUS_M = 0.010
P03_RING_Z_RANGE_M = (0.003, 0.0035)
CORRIDOR_75_MM = 13.42333744142368


def p03_installed_z(local_z_mm: float) -> float:
    """Global millimetres after seating the local 3 mm flange top at z=0."""
    return local_z_mm - 3.0


def wrap_phase_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def complex_effect(inserted: complex, baseline: complex) -> dict[str, float]:
    if not all(np.isfinite([inserted.real, inserted.imag, baseline.real, baseline.imag])) or abs(baseline) == 0.0:
        return {"magnitude_change_db": math.nan, "phase_difference_deg": math.nan}
    ratio = inserted / baseline
    return {
        "magnitude_change_db": 20.0 * math.log10(abs(ratio)),
        "phase_difference_deg": wrap_phase_deg(math.degrees(math.atan2(ratio.imag, ratio.real))),
    }


def classify(branch_shift_octaves: float, primary_effect_db: float, secondary_effect_db: float,
             primary_finite_nonzero: bool) -> str:
    if not np.isfinite(branch_shift_octaves) or branch_shift_octaves <= 0.0:
        return "P04M PRINT_GATE_WITHDRAWN"
    if not primary_finite_nonzero or not np.isfinite(primary_effect_db) or primary_effect_db >= 0.0:
        return "P04M PRINT_GATE_WITHDRAWN"
    if abs(primary_effect_db) <= EXPERIMENTAL_LOCAL_P95_DB or secondary_effect_db < 0.0:
        return "P04M PRINT_GATE_WEAKENED"
    return "P04M PRINT_GATE_RETAINED"

"""Pure, frozen calculations for the P04S synthesis."""

from __future__ import annotations

import math


def signed_percent(value: float, reference: float) -> float:
    if reference == 0:
        raise ValueError("reference must be nonzero")
    return 100.0 * (value - reference) / reference


def octave_delta(value: float, reference: float) -> float:
    if value <= 0 or reference <= 0:
        raise ValueError("frequencies must be positive")
    return math.log2(value / reference)


def effect_ratio(numerator_octaves: float, denominator_octaves: float) -> float:
    if denominator_octaves == 0:
        raise ValueError("denominator effect must be nonzero")
    return abs(numerator_octaves / denominator_octaves)


def length_over_wavelength(length_mm: float, frequency_hz: float, c_m_s: float = 343.0) -> float:
    if length_mm < 0 or frequency_hz <= 0 or c_m_s <= 0:
        raise ValueError("invalid wavelength inputs")
    return (length_mm / 1000.0) * frequency_hz / c_m_s


def print_decision(gates: list[bool], provenance_complete: bool = True) -> str:
    if not provenance_complete:
        return "PRINT_DECISION_BLOCKED_BY_MISSING_PROVENANCE"
    if len(gates) != 8:
        raise ValueError("exactly eight frozen print gates are required")
    return "PRINT_ONE_P04E_75PCT_MECHANISM_INSERT" if all(gates) else "NO_PRINT_CURRENT_CANDIDATE"

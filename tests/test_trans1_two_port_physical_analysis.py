from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.trans1_two_port_physical_analysis import (
    Trans1InputError,
    classify_trans1_pilot,
    directional_contrast,
    parse_trans1_filename,
)


@pytest.mark.parametrize(
    ("name", "condition", "repeat"),
    [
        ("R TRANS_N_01.txt", "N", 1),
        ("R TRANS_S_06.mdat", "S", 6),
        ("R TRANS_NRETURN_03.txt", "NRETURN", 3),
    ],
)
def test_parse_trans1_filename(name, condition, repeat):
    assert parse_trans1_filename(name) == (condition, repeat)


def test_parse_trans1_filename_fails_closed():
    with pytest.raises(Trans1InputError):
        parse_trans1_filename("TRANS_NORTH_1.txt")


def test_directional_contrast_is_low_high_difference_of_differences():
    north = np.array([5.0, 5.0, 1.0, 1.0])
    south = np.array([2.0, 2.0, 4.0, 4.0])
    low = np.array([True, True, False, False])
    high = ~low
    assert directional_contrast(north, south, low, high) == pytest.approx(6.0)


@pytest.mark.parametrize(
    ("effect", "floor", "drift", "correlation", "window_supported", "expected"),
    [
        (2.0, 0.4, 0.5, 0.90, True, "TWO_PORT_SELECTIVE_ENCODING_SUPPORTED_WITH_LIMITS"),
        (2.0, 0.4, 2.2, 0.90, True, "TWO_PORT_EFFECT_CONFOUNDED_BY_RETURN_DRIFT"),
        (0.3, 0.4, 0.2, 0.95, True, "TWO_PORT_SELECTIVITY_NOT_SUPPORTED"),
        (2.0, 0.4, 0.5, 0.30, False, "TWO_PORT_SPECTRAL_DIFFERENCE_WITHOUT_STABLE_CODE"),
    ],
)
def test_classify_trans1_pilot(
    effect, floor, drift, correlation, window_supported, expected
):
    assert classify_trans1_pilot(
        direction_effect_rms_db=effect,
        repeatability_floor_db=floor,
        return_drift_rms_db=drift,
        return_effect_correlation=correlation,
        fixed_window_supported=window_supported,
    ) == expected

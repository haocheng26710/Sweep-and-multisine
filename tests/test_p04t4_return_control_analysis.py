from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.p04t4_return_control_analysis import (
    P04T4InputError,
    classify_return_control,
    compute_return_control_metrics,
    parse_p04t4_filename,
)


@pytest.mark.parametrize(
    ("name", "condition", "repeat"),
    [
        ("R P04T4_BASEC_R01.txt", "BASEC", 1),
        ("R P04T4_I50PC_R04.mdat", "I50PC", 4),
        ("R P04T4_BASER_R06.txt", "BASER", 6),
    ],
)
def test_parse_p04t4_filename(name, condition, repeat):
    assert parse_p04t4_filename(name) == (condition, repeat)


def test_parse_p04t4_filename_fails_closed():
    with pytest.raises(P04T4InputError):
        parse_p04t4_filename("P04T4_BASE_01.txt")


def test_compute_return_control_metrics_detects_reversible_effect():
    primary = np.ones(6, dtype=bool)
    base_c = np.array([0.0, 0.2, -0.1, 0.1, -0.2, 0.0])
    base_r = base_c + np.array([0.05, -0.05, 0.05, -0.05, 0.05, -0.05])
    intervention = np.array([3.0, -3.0, 2.5, -2.5, 3.5, -3.5])
    metrics = compute_return_control_metrics(
        {"BASEC": base_c, "I50PC": intervention, "BASER": base_r},
        primary,
    )
    assert metrics["base_return_shape_rms_db"] < 0.1
    assert metrics["i50p_bracket_shape_rms_db"] > 2.0
    assert metrics["effect_to_return_shape_ratio"] > 20.0
    assert metrics["pre_post_effect_pearson"] > 0.99


def test_classification_requires_return_and_effect_gates():
    confirmed = {
        "base_return_shape_rms_db": 0.30,
        "i50p_bracket_shape_rms_db": 2.10,
        "effect_to_return_shape_ratio": 7.0,
        "pre_post_effect_pearson": 0.90,
        "pre_post_effect_cosine": 0.90,
    }
    assert classify_return_control(confirmed, confirmed, 0.995) == (
        "P04T4 REVERSIBLE_I50P_EFFECT_CONFIRMED_WITH_LIMITS"
    )

    assembly_sensitive = dict(confirmed, base_return_shape_rms_db=1.05)
    assert classify_return_control(assembly_sensitive, assembly_sensitive, 0.995) == (
        "P04T4 RETURN_CONTROL_SUPPORTS_EFFECT_WITH_ASSEMBLY_SENSITIVITY"
    )

    confounded = dict(
        confirmed,
        base_return_shape_rms_db=1.7,
        i50p_bracket_shape_rms_db=1.8,
        effect_to_return_shape_ratio=1.06,
        pre_post_effect_pearson=0.1,
        pre_post_effect_cosine=0.1,
    )
    assert classify_return_control(confounded, confounded, 0.70) == (
        "P04T4 ASSEMBLY_OR_TIME_DRIFT_CONFOUNDED"
    )


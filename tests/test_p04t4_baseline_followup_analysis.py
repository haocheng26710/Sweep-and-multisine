from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.p04t4_baseline_followup_analysis import (
    P04T4BaselineFollowupInputError,
    classify_baseline_pattern,
    compute_baseline_followup_metrics,
    parse_p04t4_baseline_followup_filename,
)


@pytest.mark.parametrize(
    ("name", "repeat"),
    [
        ("R P04T4_BASERR_R01.txt", 1),
        ("R P04T4_BASERR_R06.mdat", 6),
    ],
)
def test_parse_followup_filename(name, repeat):
    assert parse_p04t4_baseline_followup_filename(name) == repeat


def test_parse_followup_filename_fails_closed():
    with pytest.raises(P04T4BaselineFollowupInputError):
        parse_p04t4_baseline_followup_filename("R P04T4_BASE_R01.txt")


def test_metrics_separate_return_and_i50_effects():
    primary = np.ones(6, dtype=bool)
    base_c = np.array([0.0, 0.2, -0.1, 0.1, -0.2, 0.0])
    base_r = base_c + np.array([0.7, -0.7, 0.7, -0.7, 0.7, -0.7])
    base_rr = base_c + np.array([0.08, -0.08, 0.08, -0.08, 0.08, -0.08])
    intervention = np.array([3.0, -3.0, 2.5, -2.5, 3.5, -3.5])

    metrics = compute_baseline_followup_metrics(
        {
            "BASEC": base_c,
            "BASER": base_r,
            "BASERR": base_rr,
            "I50PC": intervention,
        },
        primary,
    )

    assert metrics["basec_to_baserr_shape_rms_db"] < metrics["basec_to_baser_shape_rms_db"]
    assert metrics["i50_min_shape_rms_db"] > 2.0
    assert metrics["i50_effect_min_pairwise_pearson"] > 0.9


def test_classification_reports_recovery_without_causal_attribution():
    assert classify_baseline_pattern(
        {
            "basec_to_baser_shape_rms_db": 1.1,
            "basec_to_baserr_shape_rms_db": 0.4,
            "baser_to_baserr_shape_rms_db": 1.0,
            "i50_min_shape_rms_db": 2.0,
            "i50_effect_min_pairwise_pearson": 0.8,
        },
        within_condition_ceiling_db=0.62,
    ) == "P04T4F BASELINE_RECOVERED_WITH_I50_EFFECT_ROBUST"


from __future__ import annotations

import numpy as np

from acoustic_encoder.info_top_single_mic import (
    band_shape_metrics,
    effective_rank_metrics,
    shrinkage_separability,
)


def test_band_shape_metrics_uses_complete_curves_and_demeans_each_curve() -> None:
    first = np.array([[10.0, 11.0, 12.0], [20.0, 21.0, 22.0]])
    second = np.array([[10.0, 12.0, 14.0], [30.0, 32.0, 34.0]])

    result = band_shape_metrics(first, second)

    assert result["between_shape_rms_db"] == np.sqrt(2.0 / 3.0)
    assert result["within_shape_rms_median_db"] == 0.0
    assert result["between_within_ratio"] is None
    assert result["complete_curve_count"] == 4


def test_effective_rank_reports_the_structural_binary_limit() -> None:
    centroids = np.array([[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]])

    result = effective_rank_metrics(centroids)

    assert result["matrix_rank"] == 1
    assert result["maximum_theoretical_contrast_dimension"] == 1
    assert result["effective_rank"] == 1.0
    assert len(result["singular_values"]) == 2


def test_shrinkage_separability_reports_covariance_diagnostics() -> None:
    features = np.array(
        [
            [0.0, 0.1, 0.0],
            [0.1, 0.0, -0.1],
            [2.0, 2.1, 2.0],
            [2.1, 2.0, 1.9],
        ]
    )
    labels = np.array(["A", "A", "B", "B"])

    result = shrinkage_separability(features, labels)

    assert result["status"] == "available"
    assert result["raw_covariance_rank"] <= 2
    assert result["shrinkage"] > 0.0
    assert result["shrinkage_mahalanobis"] > 0.0
    assert result["fisher_trace_ratio"] > 0.0

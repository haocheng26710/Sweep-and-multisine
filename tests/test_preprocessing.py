from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from acoustic_encoder.preprocessing import (
    build_dense_grid,
    canonical_preprocessing_config,
    preprocessing_id,
)


def _config() -> dict:
    return {
        "schema_version": "1.1.0",
        "analysis_band_hz": [1000, 8000],
        "common_grid_step_hz": 10,
        "interpolation": "linear",
        "maximum_interpolation_gap_hz": 100,
        "minimum_valid_grid_fraction": 0.95,
        "normalization_band_hz": [1000, 8000],
        "minimum_normalization_points": 2,
        "minimum_zscore_std_db": 1.0e-9,
        "smoothing_domain": "db",
        "smoothing": {"method": "none"},
    }


def test_decimal_grid_has_inclusive_stable_endpoints_and_names() -> None:
    grid = build_dense_grid(_config())

    assert grid.frequency_hz.size == 701
    assert grid.frequency_hz[0] == 1000.0
    assert grid.frequency_hz[-1] == 8000.0
    np.testing.assert_array_equal(np.diff(grid.frequency_hz), np.full(700, 10.0))
    assert grid.feature_names[0] == "f_1000_hz"
    assert grid.feature_names[-1] == "f_8000_hz"
    assert len(set(grid.feature_names)) == 701


def test_grid_rejects_band_span_that_is_not_an_exact_step_multiple() -> None:
    config = _config()
    config["analysis_band_hz"] = [1000, 8001]

    with pytest.raises(ValueError, match="exact multiple"):
        build_dense_grid(config)


def test_preprocessing_id_is_independent_of_mapping_order_and_sensitive_to_values() -> None:
    config = _config()
    reordered = {
        key: deepcopy(config[key])
        for key in reversed(tuple(config))
    }
    changed = deepcopy(config)
    changed["maximum_interpolation_gap_hz"] = 90

    first = preprocessing_id(config)
    second = preprocessing_id(reordered)

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64
    assert preprocessing_id(changed) != first


def test_preprocessing_id_ignores_numeric_presentation_and_irrelevant_none_boundary() -> None:
    config = _config()
    reformatted = deepcopy(config)
    reformatted["common_grid_step_hz"] = 10.0
    reformatted["maximum_interpolation_gap_hz"] = "100.0"
    reformatted["smoothing"] = {"boundary": "reflect", "method": "none"}

    assert preprocessing_id(reformatted) == preprocessing_id(config)


def test_preprocessing_id_changes_with_complete_smoothing_definition() -> None:
    none = _config()
    moving = deepcopy(none)
    moving["smoothing"] = {
        "method": "moving_average_linear_hz",
        "window_hz": 50,
        "boundary": "reflect",
        "minimum_kernel_coverage": 0.5,
    }
    wider = deepcopy(moving)
    wider["smoothing"]["window_hz"] = 100
    nearest = deepcopy(moving)
    nearest["smoothing"]["boundary"] = "nearest"

    assert len(
        {
            preprocessing_id(none),
            preprocessing_id(moving),
            preprocessing_id(wider),
            preprocessing_id(nearest),
        }
    ) == 4

    reordered_smoothing = deepcopy(moving)
    reordered_smoothing["smoothing"] = {
        key: moving["smoothing"][key]
        for key in reversed(tuple(moving["smoothing"]))
    }
    assert preprocessing_id(reordered_smoothing) == preprocessing_id(moving)

    canonical = canonical_preprocessing_config(moving)
    assert canonical["smoothing_definition"]["effective"][
        "kernel_sample_count"
    ] == "5"
    assert canonical["smoothing_definition"]["effective"][
        "effective_window_hz"
    ] == "50"

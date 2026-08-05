from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.preprocessing import (
    fractional_octave_bounds,
    smooth_dense_grid,
)


def test_none_smoothing_preserves_values_and_mask_exactly() -> None:
    frequency_hz = np.array([1000.0, 1010.0, 1020.0, 1030.0])
    values_db = np.array([70.0, np.nan, 72.0, 73.0])
    valid_mask = np.array([True, False, True, True])
    config = {
        "smoothing_domain": "db",
        "smoothing": {"method": "none"},
    }

    result = smooth_dense_grid(
        frequency_hz,
        values_db,
        valid_mask,
        config,
    )

    np.testing.assert_array_equal(result.values_db, values_db)
    np.testing.assert_array_equal(result.valid_mask, valid_mask)
    assert result.definition["domain"] == "db"
    assert result.definition["method"] == "none"
    assert result.input_valid_fraction == result.output_valid_fraction == 0.75


def test_moving_average_matches_hand_calculated_three_point_result() -> None:
    result = smooth_dense_grid(
        np.arange(1000.0, 1050.0, 10.0),
        np.array([0.0, 3.0, 6.0, 9.0, 12.0]),
        np.ones(5, dtype=bool),
        {
            "smoothing_domain": "db",
            "smoothing": {
                "method": "moving_average_linear_hz",
                "window_hz": 30,
                "boundary": "truncate",
                "minimum_kernel_coverage": 0.5,
            },
        },
    )

    np.testing.assert_allclose(result.values_db, [1.5, 3.0, 6.0, 9.0, 10.5])
    np.testing.assert_array_equal(result.valid_mask, np.ones(5, dtype=bool))


def test_moving_average_records_requested_and_centered_effective_windows() -> None:
    frequency_hz = np.arange(1000.0, 1200.0, 10.0)
    values_db = np.arange(frequency_hz.size, dtype=float)
    definitions = {}
    for window_hz in (50, 100):
        result = smooth_dense_grid(
            frequency_hz,
            values_db,
            np.ones(frequency_hz.size, dtype=bool),
            {
                "smoothing_domain": "db",
                "smoothing": {
                    "method": "moving_average_linear_hz",
                    "window_hz": window_hz,
                    "boundary": "truncate",
                    "minimum_kernel_coverage": 0.5,
                },
            },
        )
        definitions[window_hz] = result.definition

    assert definitions[50]["requested"] == {"window_hz": 50.0}
    assert definitions[50]["effective"]["kernel_sample_count"] == 5
    assert definitions[50]["effective"]["effective_window_hz"] == 50.0
    assert definitions[50]["effective"]["effective_support_span_hz"] == 40.0
    assert definitions[100]["effective"][
        "requested_sample_count_before_centering"
    ] == 10
    assert definitions[100]["effective"]["kernel_sample_count"] == 11
    assert definitions[100]["effective"]["effective_window_hz"] == 110.0
    assert definitions[100]["effective"]["effective_support_span_hz"] == 100.0


def test_reflect_boundary_mirrors_without_repeating_segment_edge() -> None:
    result = smooth_dense_grid(
        np.array([1000.0, 1010.0, 1020.0]),
        np.array([1.0, 2.0, 3.0]),
        np.ones(3, dtype=bool),
        {
            "smoothing_domain": "db",
            "smoothing": {
                "method": "moving_average_linear_hz",
                "window_hz": 30,
                "boundary": "reflect",
                "minimum_kernel_coverage": 2.0 / 3.0,
            },
        },
    )

    np.testing.assert_allclose(result.values_db, [5.0 / 3.0, 2.0, 7.0 / 3.0])
    np.testing.assert_array_equal(result.valid_mask, np.ones(3, dtype=bool))


def test_nearest_boundary_repeats_segment_edge() -> None:
    result = smooth_dense_grid(
        np.array([1000.0, 1010.0, 1020.0]),
        np.array([1.0, 2.0, 3.0]),
        np.ones(3, dtype=bool),
        {
            "smoothing_domain": "db",
            "smoothing": {
                "method": "moving_average_linear_hz",
                "window_hz": 30,
                "boundary": "nearest",
                "minimum_kernel_coverage": 2.0 / 3.0,
            },
        },
    )

    np.testing.assert_allclose(result.values_db, [4.0 / 3.0, 2.0, 8.0 / 3.0])


def test_invalid_gap_is_never_crossed_by_smoothing_kernel() -> None:
    result = smooth_dense_grid(
        np.arange(1000.0, 1050.0, 10.0),
        np.array([1.0, 2.0, np.nan, 100.0, 200.0]),
        np.array([True, True, False, True, True]),
        {
            "smoothing_domain": "db",
            "smoothing": {
                "method": "moving_average_linear_hz",
                "window_hz": 50,
                "boundary": "nearest",
                "minimum_kernel_coverage": 0.4,
            },
        },
    )

    np.testing.assert_allclose(result.values_db[[0, 1]], [1.4, 1.6])
    assert np.isnan(result.values_db[2])
    np.testing.assert_allclose(result.values_db[[3, 4]], [140.0, 160.0])
    np.testing.assert_array_equal(
        result.valid_mask,
        np.array([True, True, False, True, True]),
    )


def test_gaussian_kernel_is_normalized_and_impulse_response_is_symmetric() -> None:
    result = smooth_dense_grid(
        np.arange(0.0, 70.0, 10.0),
        np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]),
        np.ones(7, dtype=bool),
        {
            "smoothing_domain": "db",
            "smoothing": {
                "method": "gaussian_linear_hz",
                "sigma_hz": 10,
                "truncate_sigma": 2,
                "boundary": "truncate",
                "minimum_kernel_coverage": 0.5,
            },
        },
    )

    np.testing.assert_allclose(result.values_db, result.values_db[::-1])
    assert result.definition["effective"]["sigma_grid_samples"] == 1.0
    assert result.definition["effective"]["kernel_radius_samples"] == 2
    assert np.isclose(result.definition["effective"]["kernel_weight_sum"], 1.0)


def test_one_third_octave_bounds_follow_base_two_center_formula() -> None:
    lower, upper = fractional_octave_bounds(1000.0, 3)

    assert np.isclose(lower, 1000.0 * 2.0 ** (-1.0 / 6.0))
    assert np.isclose(upper, 1000.0 * 2.0 ** (1.0 / 6.0))
    lower_500, upper_500 = fractional_octave_bounds(500.0, 3)
    assert upper - lower > upper_500 - lower_500


def test_fractional_octave_keeps_constant_spectrum_and_bandwidth_grows() -> None:
    frequency_hz = np.arange(100.0, 1010.0, 10.0)
    result = smooth_dense_grid(
        frequency_hz,
        np.full(frequency_hz.size, 4.25),
        np.ones(frequency_hz.size, dtype=bool),
        {
            "smoothing_domain": "db",
            "smoothing": {
                "method": "fractional_octave",
                "fraction_denominator": 3,
                "boundary": "truncate",
                "minimum_kernel_coverage": 0.4,
                "weighting_definition": "rectangular_uniform_linear_grid_db",
            },
        },
    )

    np.testing.assert_allclose(result.values_db, 4.25)
    np.testing.assert_array_equal(result.valid_mask, np.ones(frequency_hz.size, bool))
    effective = result.definition["effective"]
    assert effective["kernel_sample_count_at_low_frequency"] < effective[
        "kernel_sample_count_at_high_frequency"
    ]
    assert result.definition["formula"]["lower_hz"] == "fc * 2**(-1/(2*N))"
    assert result.definition["formula"]["upper_hz"] == "fc * 2**(1/(2*N))"


def test_minimum_kernel_coverage_is_inclusive_and_invalidates_when_below() -> None:
    base = {
        "smoothing_domain": "db",
        "smoothing": {
            "method": "moving_average_linear_hz",
            "window_hz": 30,
            "boundary": "truncate",
            "minimum_kernel_coverage": 2.0 / 3.0,
        },
    }
    inclusive = smooth_dense_grid(
        np.array([10.0, 20.0, 30.0]),
        np.array([1.0, 2.0, 3.0]),
        np.ones(3, dtype=bool),
        base,
    )
    strict = smooth_dense_grid(
        np.array([10.0, 20.0, 30.0]),
        np.array([1.0, 2.0, 3.0]),
        np.ones(3, dtype=bool),
        {
            **base,
            "smoothing": {
                **base["smoothing"],
                "minimum_kernel_coverage": 0.67,
            },
        },
    )

    np.testing.assert_array_equal(inclusive.valid_mask, [True, True, True])
    np.testing.assert_array_equal(strict.valid_mask, [False, True, False])
    assert np.isnan(strict.values_db[[0, 2]]).all()


@pytest.mark.parametrize(
    "smoothing",
    [
        {"method": "none"},
        {
            "method": "moving_average_linear_hz",
            "window_hz": 50,
            "boundary": "reflect",
            "minimum_kernel_coverage": 0.4,
        },
        {
            "method": "gaussian_linear_hz",
            "sigma_hz": 15,
            "truncate_sigma": 3,
            "boundary": "nearest",
            "minimum_kernel_coverage": 0.4,
        },
        {
            "method": "fractional_octave",
            "fraction_denominator": 3,
            "boundary": "truncate",
            "minimum_kernel_coverage": 0.4,
            "weighting_definition": "rectangular_uniform_linear_grid_db",
        },
    ],
)
def test_every_smoothing_method_preserves_a_constant_db_spectrum(
    smoothing: dict,
) -> None:
    frequency_hz = np.arange(1000.0, 1210.0, 10.0)
    result = smooth_dense_grid(
        frequency_hz,
        np.full(frequency_hz.size, 72.5),
        np.ones(frequency_hz.size, dtype=bool),
        {"smoothing_domain": "db", "smoothing": smoothing},
    )

    np.testing.assert_allclose(result.values_db[result.valid_mask], 72.5)


@pytest.mark.parametrize(
    "smoothing",
    [
        {
            "method": "gaussian_linear_hz",
            "sigma_hz": 20,
            "truncate_sigma": 2,
            "boundary": "reflect",
            "minimum_kernel_coverage": 0.2,
        },
        {
            "method": "fractional_octave",
            "fraction_denominator": 1,
            "boundary": "nearest",
            "minimum_kernel_coverage": 0.1,
            "weighting_definition": "rectangular_uniform_linear_grid_db",
        },
    ],
)
def test_gaussian_and_fractional_octave_do_not_cross_invalid_gap(
    smoothing: dict,
) -> None:
    result = smooth_dense_grid(
        np.arange(100.0, 150.0, 10.0),
        np.array([2.0, 2.0, np.nan, 100.0, 100.0]),
        np.array([True, True, False, True, True]),
        {"smoothing_domain": "db", "smoothing": smoothing},
    )

    np.testing.assert_allclose(result.values_db[:2], 2.0)
    assert np.isnan(result.values_db[2])
    np.testing.assert_allclose(result.values_db[3:], 100.0)


def test_fractional_octave_all_invalid_grid_returns_auditable_empty_result() -> None:
    frequency_hz = np.arange(100.0, 150.0, 10.0)
    result = smooth_dense_grid(
        frequency_hz,
        np.full(frequency_hz.size, np.nan),
        np.zeros(frequency_hz.size, dtype=bool),
        {
            "smoothing_domain": "db",
            "smoothing": {
                "method": "fractional_octave",
                "fraction_denominator": 3,
                "boundary": "truncate",
                "minimum_kernel_coverage": 0.5,
                "weighting_definition": "rectangular_uniform_linear_grid_db",
            },
        },
    )

    assert np.isnan(result.values_db).all()
    assert not result.valid_mask.any()
    assert result.definition["effective"]["input_valid_segment_count"] == 0


def test_smoothing_rejects_decreasing_common_grid() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        smooth_dense_grid(
            np.array([30.0, 20.0, 10.0]),
            np.array([1.0, 2.0, 3.0]),
            np.ones(3, dtype=bool),
            {
                "smoothing_domain": "db",
                "smoothing": {
                    "method": "moving_average_linear_hz",
                    "window_hz": 30,
                    "boundary": "truncate",
                    "minimum_kernel_coverage": 0.5,
                },
            },
        )

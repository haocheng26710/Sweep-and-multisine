from __future__ import annotations

import numpy as np

from acoustic_encoder.info_top_information_cost import (
    build_state_effects,
    generate_parameter_units,
    combination_metrics,
    fit_marginal_models,
    simulate_observations,
)


def test_state_effects_preserve_real_microphone_anchor_and_bound_spatial_diversity() -> None:
    real_delta = np.array([1.0, -2.0, 1.0, 0.0])
    pressure = np.array(
        [
            [1.0, 1.0, 1.0, 1.0],
            [1.0, 2.0, 1.0, 0.5],
        ],
        dtype=complex,
    )

    effects = build_state_effects(real_delta, pressure, lambda_value=0.5)

    np.testing.assert_allclose(effects[0], real_delta)
    assert effects.shape == (2, 4)
    assert np.all(np.isfinite(effects))
    assert not np.allclose(effects[1], real_delta)


def test_parameter_units_are_complete_reproducible_resampling_atoms() -> None:
    first = generate_parameter_units(count=4, seed=123)
    second = generate_parameter_units(count=4, seed=123)
    evaluation = generate_parameter_units(count=4, seed=456)

    assert first == second
    assert first != evaluation
    assert [row["unit_id"] for row in first] == ["U000", "U001", "U002", "U003"]
    assert all(-0.2 <= row["lambda_relative_jitter"] <= 0.2 for row in first)
    assert all(len(row["state_noise_seeds"]) == 2 for row in first)
    assert all(len(row["state_drift_seeds"]) == 2 for row in first)


def test_unperturbed_observations_preserve_actual_anchor_and_bounded_structure_jitter() -> None:
    effects = np.array([[1.0, -1.0], [2.0, -2.0]])
    units = generate_parameter_units(count=3, seed=123)

    observed = simulate_observations(
        effects,
        units,
        noise_db=0.0,
        drift_db=0.0,
        cross_sensor_correlation=0.5,
    )

    assert observed.shape == (3, 2, 2, 2)
    expected_actual = np.repeat(effects[None, 0] / 2.0, len(units), axis=0)
    np.testing.assert_allclose(observed[:, 0, 0], expected_actual)
    np.testing.assert_allclose(observed[:, 1, 0], -expected_actual)
    relative = observed[:, 0, 1] / (effects[1] / 2.0)
    assert np.all((relative >= 0.8) & (relative <= 1.2))
    np.testing.assert_allclose(observed[:, 1], -observed[:, 0])


def test_combination_metrics_use_complete_parameter_units() -> None:
    rng = np.random.default_rng(7)
    observed = rng.normal(scale=0.1, size=(12, 2, 2, 16))
    observed[:, 0, 0] += np.linspace(-1.0, 1.0, 16)
    observed[:, 1, 0] -= np.linspace(-1.0, 1.0, 16)

    metrics = combination_metrics(observed, (0,))

    assert metrics["parameter_unit_count"] == 12
    assert metrics["frequency_points_used_as_samples"] is False
    assert metrics["between_within_shape_ratio"] > 1.0
    assert metrics["effective_rank"] == 1.0
    assert np.isfinite(metrics["shrinkage_mahalanobis"])


def test_marginal_model_comparison_reports_all_parametric_families_and_residuals() -> None:
    rows = fit_marginal_models([1, 2, 3, 4], [1.0, 1.8, 2.2, 2.4])

    assert {row["model"] for row in rows} == {"logarithmic", "saturating", "power"}
    assert all(len(row["residuals"]) == 4 for row in rows)
    assert all(np.isfinite(row["rmse"]) for row in rows)
    assert all("identifiability" in row for row in rows)

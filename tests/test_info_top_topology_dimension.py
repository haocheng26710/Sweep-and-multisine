from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from acoustic_encoder.info_top_topology_dimension import (
    extract_window_features,
    evaluate_observations,
    coupling_matrix,
    generate_parameter_units,
    load_authoritative_common_basis,
    read_top1_primary_anchor,
    bootstrap_match_noninferiority,
    normalized_off_diagonal_energy,
    simulate_observations,
    state_response_spectrum,
)


def test_coupling_families_have_unit_rows_and_predeclared_crosstalk_order() -> None:
    high = coupling_matrix(0.8)
    medium = coupling_matrix(0.4)
    near = coupling_matrix(0.05)

    np.testing.assert_allclose(np.linalg.norm(high, axis=1), 1.0)
    np.testing.assert_allclose(np.linalg.norm(medium, axis=1), 1.0)
    np.testing.assert_allclose(np.linalg.norm(near, axis=1), 1.0)
    assert normalized_off_diagonal_energy(high) > normalized_off_diagonal_energy(medium)
    assert normalized_off_diagonal_energy(medium) > normalized_off_diagonal_energy(near)


def test_four_state_centered_response_never_reports_a_fourth_contrast() -> None:
    signatures = np.arange(64, dtype=float).reshape(4, 16)
    spectrum = state_response_spectrum(signatures, coupling_matrix(0.4), (0, 1, 2, 3))

    assert len(spectrum["singular_values"]) == 4
    assert spectrum["interpreted_rank"] <= 3
    assert spectrum["singular_values"][-1] < 1e-10


def test_parameter_units_are_reproducible_complete_module_and_state_atoms() -> None:
    first = generate_parameter_units(4, 123)
    second = generate_parameter_units(4, 123)
    evaluation = generate_parameter_units(4, 456)

    assert first == second
    assert first != evaluation
    assert [unit["unit_id"] for unit in first] == ["U000", "U001", "U002", "U003"]
    assert all(set(unit["module_repeat_indices"]) == {"ENC-A", "ENC-B", "ENC-D", "ENC-F"} for unit in first)
    assert all(len(indices) == 3 for unit in first for indices in unit["module_repeat_indices"].values())
    assert all(len(unit["state_noise_seeds"]) == 4 and len(unit["state_drift_seeds"]) == 4 for unit in first)


def test_metrics_use_complete_units_and_report_all_four_state_pair_summaries() -> None:
    repeats = np.stack(
        [np.tile(np.linspace(-1.0, 1.0, 16) * scale, (3, 1)) for scale in (1.0, -0.7, 0.4, -1.3)]
    )
    units = generate_parameter_units(12, 123)
    observed = simulate_observations(
        repeats,
        coupling_alpha=0.4,
        coupling_jitter_half_width=0.05,
        units=units,
        noise_db=0.1,
        drift_db=0.2,
        cross_sensor_correlation=0.5,
    )
    metrics = evaluate_observations(observed, (0, 1), nuisance_floor_db=0.25)

    assert observed.shape == (12, 4, 4, 16)
    assert metrics["parameter_unit_count"] == 12
    assert metrics["frequency_points_used_as_samples"] is False
    assert metrics["pair_count"] == 6
    assert metrics["stable_contrast_dimension"] <= 3
    assert np.isfinite(metrics["minimum_pairwise_between_within_ratio"])
    assert np.isfinite(metrics["median_shrinkage_mahalanobis"])


def test_common_basis_excludes_invalid_frequency_endpoint_without_changing_windows() -> None:
    frequency = np.array([200.0, 250.0, 300.0, 400.0])
    curve = np.array([np.nan, 1.0, 3.0, 5.0])
    valid = np.array([False, True, True, True])
    windows = [{"id": "W", "low_hz": 200.0, "high_hz": 300.0, "parent_band_hz": [200.0, 400.0]}]

    features = extract_window_features(curve, frequency, valid, windows)

    assert features.shape == (1,)
    assert np.isfinite(features[0])
    assert features[0] == -1.0


def test_authoritative_common_basis_retains_all_windows_and_is_finite() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads(
        (root / "outputs/info_top/INFO_TOP_3_TOPOLOGY_DIMENSION_MATCH/top3_analysis_contract.json").read_text(
            encoding="utf-8"
        )
    )

    repeat_features, rows = load_authoritative_common_basis(root, contract)

    assert repeat_features.shape == (4, 3, 16)
    assert np.all(np.isfinite(repeat_features))
    assert len(rows) == 4 * 16
    assert {row["window_id"] for row in rows} == {
        window["id"] for window in contract["common_spectral_basis"]["windows"]
    }


def test_top1_external_anchor_uses_frozen_actual_schema_without_pooling() -> None:
    root = Path(__file__).resolve().parents[1]

    anchor = read_top1_primary_anchor(
        root / "outputs/info_top/INFO_TOP_1_SINGLE_MIC_BASELINE/analysis_summary.json"
    )

    assert anchor == {
        "between_within_ratio": 3.674080161363945,
        "between_shape_rms_db": 2.0929814997005223,
        "within_shape_rms_median_db": 0.5696613595179523,
        "evidence_level": "Level A",
        "pooled_with_level_c": False,
    }


def test_match_probability_resamples_complete_paired_evaluation_units() -> None:
    rng = np.random.default_rng(9)
    weak = rng.normal(scale=1.0, size=(24, 4, 4, 16))
    strong = weak.copy()
    for state in range(4):
        strong[:, state, 0] += state * 4.0

    probability = bootstrap_match_noninferiority(
        {"FULL": strong, "INCOMPLETE": weak},
        [
            {"topology": "FULL", "sensor_indices": (0,), "full_coverage": True},
            {"topology": "INCOMPLETE", "sensor_indices": (0,), "full_coverage": False},
        ],
        iterations=500,
        seed=2026082733,
    )
    repeated = bootstrap_match_noninferiority(
        {"FULL": strong, "INCOMPLETE": weak},
        [
            {"topology": "FULL", "sensor_indices": (0,), "full_coverage": True},
            {"topology": "INCOMPLETE", "sensor_indices": (0,), "full_coverage": False},
        ],
        iterations=500,
        seed=2026082733,
    )

    assert probability > 0.9
    assert probability == repeated
    assert np.isfinite(probability)
    assert 0.0 <= probability <= 1.0

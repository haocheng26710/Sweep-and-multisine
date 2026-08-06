from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from acoustic_encoder.config import ConfigError, load_config, validate_config
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_projection_ablation_config_rejects_unsorted_subset_sizes() -> None:
    config = load_config(PROJECT_ROOT / "config" / "default.yaml")
    config["tone_projection_ablation"]["subset_sizes"] = [5, 3]
    with pytest.raises(ConfigError, match="subset_sizes"):
        validate_config(config)


def test_projection_ablation_thresholds_are_explicit_and_final_test_is_sealed() -> None:
    config = load_config(PROJECT_ROOT / "config" / "default.yaml")
    policy = config["tone_projection_ablation"]["decision_policy"]
    assert policy["minimum_p4_retention"] == pytest.approx(0.90)
    assert policy["maximum_balanced_accuracy_drop"] >= 0.0
    assert config["tone_projection_ablation"]["final_test_policy"] == "sealed"


def test_config_217_migrates_with_projection_ablation_disabled(tmp_path) -> None:
    path = tmp_path / "config-217.yaml"
    payload = {
        "pipeline_version": "2.0.0-dev.18",
        "schema_versions": {"config": "2.17.0", "measurement": "2.4.0", "feature": "2.3.0"},
        "measurement_mode": "rew_sweep", "run_purpose": "software_validation",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")
    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["tone_projection_ablation"]["enabled"] is False
    assert any("P9-B is never enabled silently" in item for item in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


def test_legacy_config_defaults_to_rew_without_rewriting(tmp_path) -> None:
    path = tmp_path / "legacy.yaml"
    original = {"random_state": 7}
    path.write_text(yaml.safe_dump(original), encoding="utf-8")
    resolved = load_config(path)
    assert resolved["measurement_mode"] == "rew_sweep"
    assert resolved["run_purpose"] == "software_validation"
    assert resolved["_runtime"]["migration_warnings"]
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == original


def test_ambiguous_smoothing_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "measurement_mode": "rew_sweep",
                "preprocessing": {
                    "analysis_band_hz": [1000, 8000],
                    "smoothing": {"method": "gaussian_linear_hz"},
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="sigma_hz"):
        load_config(path)


def test_ui_alias_is_normalized(tmp_path) -> None:
    path = tmp_path / "alias.yaml"
    path.write_text(yaml.safe_dump({"measurement_mode": "schroeder_chirp"}), encoding="utf-8")
    resolved = load_config(path)
    assert resolved["measurement_mode"] == "schroeder_multisine"


def test_unknown_run_purpose_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad-purpose.yaml"
    path.write_text(yaml.safe_dump({"run_purpose": "publish_results"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="run_purpose"):
        load_config(path)


def test_multisine_config_declares_period_averaging() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    assert resolved["multisine_estimation"]["period_averaging"] == "complex_spectrum"


def test_unknown_multisine_period_averaging_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad-multisine-average.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "measurement_mode": "schroeder_multisine",
                "multisine_estimation": {
                    "synchronization_method": "preamble_cross_correlation",
                    "period_averaging": "median_db",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="period_averaging"):
        load_config(path)


def test_unknown_multisine_synchronization_method_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad-multisine-sync.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "measurement_mode": "schroeder_multisine",
                "multisine_estimation": {
                    "synchronization_method": "first_nonzero_sample",
                    "period_averaging": "complex_spectrum",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="synchronization_method"):
        load_config(path)


def test_unknown_clock_drift_correction_mode_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad-clock-correction.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "measurement_mode": "schroeder_multisine",
                "multisine_estimation": {
                    "synchronization_method": "preamble_cross_correlation",
                    "period_averaging": "complex_spectrum",
                    "clock_drift": {
                        "warning_ppm": 20,
                        "exclude_candidate_ppm": 100,
                        "correction": "automatic",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="clock_drift.correction"):
        load_config(path)


@pytest.mark.parametrize(
    ("warning_ppm", "exclude_candidate_ppm"),
    [
        (0, 100),
        (-1, 100),
        (20, 20),
        (100, 20),
        (float("nan"), 100),
        (20, float("inf")),
    ],
)
def test_clock_drift_thresholds_must_be_finite_positive_and_ordered(
    tmp_path,
    warning_ppm: float,
    exclude_candidate_ppm: float,
) -> None:
    path = tmp_path / "bad-clock-thresholds.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "measurement_mode": "schroeder_multisine",
                "multisine_estimation": {
                    "synchronization_method": "preamble_cross_correlation",
                    "period_averaging": "complex_spectrum",
                    "clock_drift": {
                        "warning_ppm": warning_ppm,
                        "exclude_candidate_ppm": exclude_candidate_ppm,
                        "correction": "disabled",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="0 < warning_ppm < exclude_candidate_ppm"):
        load_config(path)


def test_dev_c8_uses_incremented_pipeline_and_config_versions() -> None:
    assert SCHEMA_VERSION_QUARTET == {
        "pipeline_version": "2.0.0-dev.20",
        "config_schema_version": "2.19.0",
        "measurement_schema_version": "2.4.0",
        "feature_schema_version": "2.3.0",
    }


def test_dev_c8_classification_contract_is_explicit_and_leakage_safe() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c8_classification.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    classification = resolved["classification"]
    assert classification["standardization"] == "training_fold_only"
    assert classification["pca"] == "disabled"
    assert classification["final_test_policy"] == "sealed"
    assert classification["minimum_prediction_coverage"] == 1.0


def test_dev_c9_cross_mode_classification_contract_is_fixed() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    cross_mode = resolved["classification"]["cross_mode"]
    assert cross_mode == {
        "transfer_protocols": [
            "sweep_to_sweep", "multisine_to_multisine", "sweep_to_multisine",
            "sweep_plus_multisine_to_multisine",
        ],
        "allowed_shape_normalizations": ["subtract_mean_db", "zscore_spectrum"],
        "pooling_policy": "sample_pooled",
        "sample_weighting": "uniform",
        "class_weighting": "balanced",
        "p4b_bias_policy": "audit_only",
        "calibration_policy": "disabled",
    }
    validation = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c9_cross_mode_classification.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    assert validation["pipeline_version"] == "2.0.0-dev.20"
    assert validation["schema_versions"]["config"] == "2.19.0"


def test_dev_c8_config_migrates_to_cross_mode_defaults_without_rewriting(tmp_path) -> None:
    path = tmp_path / "dev-c8.yaml"
    payload = {
        "pipeline_version": "2.0.0-dev.14",
        "schema_versions": {
            "config": "2.13.0", "measurement": "2.4.0", "feature": "2.2.0"
        },
        "measurement_mode": "rew_sweep",
        "run_purpose": "software_validation",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["classification"]["cross_mode"]["p4b_bias_policy"] == "audit_only"
    assert any("2.13.0" in item for item in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("p4b_bias_policy", "apply", "audit_only"),
        ("calibration_policy", "fit", "disabled"),
        ("pooling_policy", "best_mode", "sample_pooled"),
    ],
)
def test_cross_mode_classification_rejects_result_informed_or_calibrated_policy(
    field, value, message
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["classification"]["cross_mode"][field] = value

    with pytest.raises(ConfigError, match=message):
        validate_config(resolved)


def test_legacy_classification_validation_migrates_with_audited_warning(tmp_path) -> None:
    path = tmp_path / "legacy-classification.yaml"
    path.write_text(
        "measurement_mode: rew_sweep\nclassification:\n  validation: [leave_one_session_out]\n  models: [nearest_centroid]\n",
        encoding="utf-8",
    )
    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")
    assert resolved["classification"]["protocols"] == ["leave_one_session_out"]
    assert any("classification.validation" in item for item in resolved["_runtime"]["migration_warnings"])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("standardization", "global", "training_fold_only"),
        ("pca", "enabled", "PCA"),
        ("final_test_policy", "train", "sealed"),
        ("minimum_prediction_coverage", 0.0, "minimum_prediction_coverage"),
        ("minimum_training_samples_per_direction", 0, "minimum_training_samples_per_direction"),
    ],
)
def test_classification_rejects_leakage_prone_or_invalid_config(field, value, message) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["classification"][field] = value
    with pytest.raises(ConfigError, match=message):
        validate_config(resolved)


def test_dense_preprocessing_defaults_are_complete_and_provisional() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")

    preprocessing = resolved["preprocessing"]
    assert preprocessing == {
        "schema_version": "1.1.0",
        "provisional": True,
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


def test_dev_c3_fractional_octave_validation_config_resolves() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c3_fractional_octave.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    assert resolved["preprocessing"]["smoothing"] == {
        "method": "fractional_octave",
        "fraction_denominator": 3,
        "boundary": "truncate",
        "minimum_kernel_coverage": 0.4,
        "weighting_definition": "rectangular_uniform_linear_grid_db",
    }


def test_matched_tone_defaults_are_explicit_and_provisional() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["matched_tone_features"] == {
        "schema_version": "1.0.0",
        "provisional": True,
        "tone_ordering": "manifest_tone_index",
        "sweep_extraction": {"method": "single_point_linear"},
        "normalization": {
            "method": "subtract_mean_db",
            "minimum_valid_tones": 5,
            "minimum_std_db": 1.0e-9,
        },
        "matching": {"minimum_common_valid_tones": 5},
    }


def test_dev_c5_direction_metrics_validation_config_resolves() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c5_direction_metrics.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    assert resolved["direction_metrics"] == {
        "schema_version": "1.0.0",
        "provisional": True,
        "minimum_common_valid_features": 60,
        "minimum_common_valid_fraction": 0.8,
        "minimum_direction_count": 4,
        "center_direction_matrix": False,
        "repeatability_distance_metric": "rms",
        "morphology_gain": {
            "distance_metric": "rms",
            "minimum_denominator": 1.0e-12,
        },
    }


@pytest.mark.parametrize(
    ("section", "value", "match"),
    [
        (
            "sweep_extraction",
            {"method": "single_point_linear", "full_bandwidth_hz": 20},
            "only accepts",
        ),
        (
            "sweep_extraction",
            {
                "method": "narrowband_integration",
                "full_bandwidth_hz": 0,
                "integration_domain": "linear_power_ratio",
                "minimum_band_coverage": 0.8,
                "overlap_policy": "reject",
            },
            "full_bandwidth_hz",
        ),
        (
            "sweep_extraction",
            {
                "method": "narrowband_integration",
                "full_bandwidth_hz": 20,
                "integration_domain": "db",
                "minimum_band_coverage": 0.8,
                "overlap_policy": "reject",
            },
            "integration_domain",
        ),
        (
            "sweep_extraction",
            {
                "method": "narrowband_integration",
                "full_bandwidth_hz": 20,
                "integration_domain": "linear_power_ratio",
                "minimum_band_coverage": 1.1,
                "overlap_policy": "reject",
            },
            "minimum_band_coverage",
        ),
        (
            "normalization",
            {
                "method": "training_set_zscore",
                "minimum_valid_tones": 5,
                "minimum_std_db": 1.0e-9,
            },
            "normalization.method",
        ),
        (
            "normalization",
            {
                "method": "none",
                "minimum_valid_tones": 0,
                "minimum_std_db": 1.0e-9,
            },
            "minimum_valid_tones",
        ),
        (
            "matching",
            {"minimum_common_valid_tones": 0},
            "minimum_common_valid_tones",
        ),
    ],
)
def test_invalid_matched_tone_config_is_rejected(
    section: str,
    value: dict,
    match: str,
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["matched_tone_features"][section] = value

    with pytest.raises(ConfigError, match=match):
        validate_config(resolved)


@pytest.mark.parametrize(
    ("smoothing", "match"),
    [
        (
            {"method": "gaussian_linear_hz", "window_hz": 50, "boundary": "reflect", "minimum_kernel_coverage": 0.5},
            "sigma_hz",
        ),
        (
            {"method": "fractional_octave", "fraction": 3, "boundary": "reflect", "minimum_kernel_coverage": 0.5},
            "fraction_denominator",
        ),
        ({"method": "none", "boundary": "reflect"}, "only accepts"),
    ],
)
def test_ambiguous_or_method_incompatible_smoothing_fields_are_rejected(
    smoothing: dict,
    match: str,
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["preprocessing"]["smoothing"] = smoothing

    with pytest.raises(ConfigError, match=match):
        validate_config(resolved)


@pytest.mark.parametrize(
    ("smoothing", "match"),
    [
        (
            {"method": "moving_average_linear_hz", "window_hz": 0, "boundary": "reflect", "minimum_kernel_coverage": 0.5},
            "window_hz",
        ),
        (
            {"method": "gaussian_linear_hz", "sigma_hz": 0, "truncate_sigma": 3, "boundary": "reflect", "minimum_kernel_coverage": 0.5},
            "sigma_hz",
        ),
        (
            {"method": "gaussian_linear_hz", "sigma_hz": 20, "truncate_sigma": 0, "boundary": "reflect", "minimum_kernel_coverage": 0.5},
            "truncate_sigma",
        ),
        (
            {"method": "fractional_octave", "fraction_denominator": 0, "boundary": "reflect", "minimum_kernel_coverage": 0.5, "weighting_definition": "rectangular_uniform_linear_grid_db"},
            "fraction_denominator",
        ),
        (
            {"method": "moving_average_linear_hz", "window_hz": 50, "boundary": "wrap", "minimum_kernel_coverage": 0.5},
            "boundary",
        ),
        (
            {"method": "moving_average_linear_hz", "window_hz": 50, "boundary": "reflect", "minimum_kernel_coverage": 0},
            "minimum_kernel_coverage",
        ),
        (
            {"method": "moving_average_linear_hz", "window_hz": True, "boundary": "reflect", "minimum_kernel_coverage": 0.5},
            "window_hz",
        ),
        (
            {"method": "fractional_octave", "fraction_denominator": 3, "boundary": "reflect", "minimum_kernel_coverage": 0.5, "weighting_definition": "gaussian"},
            "weighting_definition",
        ),
    ],
)
def test_smoothing_parameter_ranges_and_enums_are_validated(
    smoothing: dict,
    match: str,
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["preprocessing"]["smoothing"] = smoothing

    with pytest.raises(ConfigError, match=match):
        validate_config(resolved)


@pytest.mark.parametrize(
    ("key", "value", "match"),
    [
        ("schema_version", "9.0.0", "schema_version"),
        ("provisional", "yes", "provisional"),
        ("analysis_band_hz", [1000, 8005], "exact multiple"),
        ("common_grid_step_hz", 0, "common_grid_step_hz"),
        ("interpolation", "cubic", "interpolation"),
        ("maximum_interpolation_gap_hz", 0, "maximum_interpolation_gap_hz"),
        ("minimum_valid_grid_fraction", 1.1, "minimum_valid_grid_fraction"),
        ("normalization_band_hz", [900, 8000], "normalization_band_hz"),
        ("minimum_normalization_points", 1, "minimum_normalization_points"),
        ("minimum_zscore_std_db", 0, "minimum_zscore_std_db"),
    ],
)
def test_invalid_dense_preprocessing_config_is_rejected(
    key: str,
    value: object,
    match: str,
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["preprocessing"][key] = value

    with pytest.raises(ConfigError, match=match):
        validate_config(resolved)


def test_shared_quality_control_thresholds_are_resolved_and_provisional() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")

    quality = resolved["quality_control"]
    assert quality["schema_version"] == "1.0.0"
    assert quality["provisional"] is True
    assert set(quality["modes"]) == {"rew_sweep", "schroeder_multisine"}
    assert quality["modes"]["rew_sweep"]["minimum_valid_points"] == 5
    assert quality["modes"]["schroeder_multisine"]["phase_policy"] == (
        "upstream_authoritative"
    )


@pytest.mark.parametrize(
    ("section", "key", "value", "match"),
    [
        ("rew_sweep", "minimum_valid_points", 0, "minimum_valid_points"),
        (
            "rew_sweep",
            "required_frequency_range_hz",
            [8000, 1000],
            "required_frequency_range_hz",
        ),
        ("rew_sweep", "phase_policy", "invented", "phase_policy"),
        (
            "schroeder_multisine",
            "unavailable_required_check_policy",
            "pass",
            "unavailable_required_check_policy",
        ),
    ],
)
def test_invalid_shared_quality_control_config_is_rejected(
    section: str,
    key: str,
    value: object,
    match: str,
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["quality_control"]["modes"][section][key] = value

    with pytest.raises(ConfigError, match=match):
        validate_config(resolved)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("warning_bounds", [-200, 60]),
        ("exclude_candidate_bounds", [-100, 50]),
        ("warning_dynamic_range_db", 200),
        ("exclude_candidate_dynamic_range_db", 50),
    ],
)
def test_shared_magnitude_warning_and_exclude_thresholds_must_be_ordered(
    key: str,
    value: object,
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["quality_control"]["modes"]["rew_sweep"]["magnitude_db"][key] = value

    with pytest.raises(ConfigError, match="magnitude_db.*not ordered"):
        validate_config(resolved)


def test_multisine_tone_quality_thresholds_are_resolved_from_yaml() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    quality = resolved["multisine_estimation"]["tone_quality"]
    assert quality["neighborhood"] == {
        "tone_guard_bins": 1,
        "leakage_radius_bins": 3,
        "noise_inner_radius_bins": 4,
        "noise_outer_radius_bins": 8,
        "minimum_noise_bins": 4,
        "minimum_leakage_bins": 2,
    }
    assert quality["snr"]["warning_below_db"] == 30
    assert quality["snr"]["exclude_candidate_below_db"] == 20
    assert quality["leakage"]["warning_ratio"] == 0.01
    assert quality["leakage"]["exclude_candidate_ratio"] == 0.05
    assert quality["non_excited_energy"]["exclude_candidate_ratio"] == 0.05


@pytest.mark.parametrize(
    ("keys", "bad_value", "match"),
    [
        (("neighborhood", "tone_guard_bins"), -1, "tone_guard_bins"),
        (("neighborhood", "leakage_radius_bins"), 1, "neighborhood radii"),
        (("neighborhood", "minimum_noise_bins"), 0, "minimum_noise_bins"),
        (
            ("clipping", "sample_threshold_fraction_full_scale"),
            1.1,
            "sample_threshold_fraction_full_scale",
        ),
        (("clipping", "warning_fraction"), 0.1, "clipping warning"),
        (("snr", "warning_below_db"), 10, "SNR warning"),
        (("leakage", "warning_ratio"), 0.1, "leakage warning"),
        (("period_stability", "minimum_periods"), 1, "minimum_periods"),
        (
            ("period_stability", "warning_variance_ratio"),
            0.1,
            "period stability warning",
        ),
        (
            ("non_excited_energy", "warning_ratio"),
            float("nan"),
            "non-excited energy",
        ),
    ],
)
def test_invalid_multisine_tone_quality_config_is_rejected(
    keys: tuple[str, str],
    bad_value: float,
    match: str,
) -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    resolved["multisine_estimation"]["tone_quality"][keys[0]][keys[1]] = bad_value

    with pytest.raises(ConfigError, match=match):
        validate_config(resolved)


@pytest.mark.parametrize(
    ("old_config", "old_measurement"),
    [
        ("2.3.0", "2.3.0"),
        ("2.4.0", "2.4.0"),
        ("2.5.0", "2.4.0"),
        ("2.6.0", "2.4.0"),
    ],
)
def test_pre_dev_c1_config_versions_migrate_without_rewriting(
    tmp_path,
    old_config,
    old_measurement,
) -> None:
    path = tmp_path / "pre-dev-b5.yaml"
    payload = {
        "measurement_mode": "rew_sweep",
        "schema_versions": {
            "config": old_config,
            "measurement": old_measurement,
            "feature": "2.0.0",
        },
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(
        path,
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    assert resolved["schema_versions"] == {
        "config": "2.19.0",
        "measurement": "2.4.0",
        "feature": "2.3.0",
    }
    assert any(old_config in warning for warning in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


def test_dev_c2_none_smoothing_migrates_explicitly_to_p3_b_schema(tmp_path) -> None:
    path = tmp_path / "dev-c2.yaml"
    payload = {
        "measurement_mode": "rew_sweep",
        "schema_versions": {
            "config": "2.7.0",
            "measurement": "2.4.0",
            "feature": "2.1.0",
        },
        "preprocessing": {
            "schema_version": "1.0.0",
            "smoothing": {"method": "none"},
        },
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["preprocessing"]["schema_version"] == "1.1.0"
    assert resolved["preprocessing"]["smoothing_domain"] == "db"
    assert resolved["preprocessing"]["smoothing"] == {"method": "none"}
    assert resolved["_runtime"]["migration_warnings"]
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


def test_dev_c3_explicit_smoothing_migrates_without_reinterpretation(
    tmp_path,
) -> None:
    path = tmp_path / "dev-c3-gaussian.yaml"
    smoothing = {
        "method": "gaussian_linear_hz",
        "sigma_hz": 35.0,
        "truncate_sigma": 3.5,
        "boundary": "reflect",
        "minimum_kernel_coverage": 0.8,
    }
    payload = {
        "measurement_mode": "rew_sweep",
        "schema_versions": {
            "config": "2.8.0",
            "measurement": "2.4.0",
            "feature": "2.1.0",
        },
        "preprocessing": {
            "schema_version": "1.1.0",
            "smoothing_domain": "db",
            "smoothing": smoothing,
        },
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["schema_versions"] == {
        "config": "2.19.0",
        "measurement": "2.4.0",
        "feature": "2.3.0",
    }
    assert resolved["preprocessing"]["smoothing"] == smoothing
    assert resolved["matched_tone_features"]["tone_ordering"] == (
        "manifest_tone_index"
    )
    assert any(
        "2.8.0" in warning for warning in resolved["_runtime"]["migration_warnings"]
    )
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


def test_dev_c4_config_migrates_to_direction_metrics_without_rewriting(
    tmp_path,
) -> None:
    path = tmp_path / "dev-c4.yaml"
    smoothing = {
        "method": "gaussian_linear_hz",
        "sigma_hz": 35.0,
        "truncate_sigma": 3.5,
        "boundary": "reflect",
        "minimum_kernel_coverage": 0.8,
    }
    payload = {
        "measurement_mode": "rew_sweep",
        "schema_versions": {
            "config": "2.9.0",
            "measurement": "2.4.0",
            "feature": "2.2.0",
        },
        "preprocessing": {
            "schema_version": "1.1.0",
            "smoothing_domain": "db",
            "smoothing": smoothing,
        },
        "matched_tone_features": {
            "schema_version": "1.0.0",
            "provisional": True,
            "tone_ordering": "manifest_tone_index",
            "sweep_extraction": {"method": "single_point_linear"},
            "normalization": {
                "method": "subtract_mean_db",
                "minimum_valid_tones": 5,
                "minimum_std_db": 1.0e-9,
            },
            "matching": {"minimum_common_valid_tones": 5},
        },
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["schema_versions"] == {
        "config": "2.19.0",
        "measurement": "2.4.0",
        "feature": "2.3.0",
    }
    assert resolved["preprocessing"]["smoothing"] == smoothing
    assert resolved["direction_metrics"] == {
        "schema_version": "1.0.0",
        "provisional": True,
        "minimum_common_valid_features": 5,
        "minimum_common_valid_fraction": 0.8,
        "minimum_direction_count": 2,
        "center_direction_matrix": False,
        "repeatability_distance_metric": "rms",
        "morphology_gain": {
            "distance_metric": "rms",
            "minimum_denominator": 1.0e-12,
        },
    }
    assert any("2.9.0" in item for item in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


def test_legacy_non_none_smoothing_is_rejected_instead_of_reinterpreted(
    tmp_path,
) -> None:
    path = tmp_path / "legacy-gaussian.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "measurement_mode": "rew_sweep",
                "schema_versions": {
                    "config": "2.7.0",
                    "measurement": "2.4.0",
                    "feature": "2.1.0",
                },
                "preprocessing": {
                    "schema_version": "1.0.0",
                    "smoothing": {
                        "method": "gaussian_linear_hz",
                        "window_hz": 50,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="cannot be migrated safely"):
        load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")


def test_legacy_root_smoothing_hz_is_explicitly_rejected() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["preprocessing"]["smoothing_hz"] = 50

    with pytest.raises(ConfigError, match="smoothing_hz is ambiguous"):
        validate_config(resolved)


def test_default_direction_metrics_contract_is_explicit_and_provisional() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["direction_metrics"] == {
        "schema_version": "1.0.0",
        "provisional": True,
        "minimum_common_valid_features": 5,
        "minimum_common_valid_fraction": 0.8,
        "minimum_direction_count": 2,
        "center_direction_matrix": False,
        "repeatability_distance_metric": "rms",
        "morphology_gain": {
            "distance_metric": "rms",
            "minimum_denominator": 1.0e-12,
        },
    }


def test_default_dataset_quality_control_contract_is_explicit_and_provisional() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")

    dataset_qc = resolved["dataset_quality_control"]
    assert dataset_qc["schema_version"] == "1.0.0"
    assert dataset_qc["provisional"] is True
    assert dataset_qc["same_condition_outliers"]["method"] == (
        "coordinate_median_mad_rms"
    )
    assert dataset_qc["same_condition_outliers"][
        "reference_role_by_evaluation_role"
    ]["final_test"] == "training"
    assert dataset_qc["repeatability"]["distance"] == "rms"
    assert set(dataset_qc["repeatability"]["thresholds_by_feature_kind"]) == {
        "dense_raw_spl",
        "dense_demeaned_db",
        "dense_zscore",
        "tone_projection_from_sweep",
        "tone_measurement_from_multisine",
    }
    assert dataset_qc["aggregation"]["canonical_block_on_required_unavailable"] is True


def test_default_comparison_metrics_contract_is_explicit_and_provisional() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")

    comparison = resolved["comparison_metrics"]
    assert comparison["schema_version"] == "1.0.0"
    assert comparison["provisional"] is True
    assert [item["band_id"] for item in comparison["frequency_bands"]] == [
        "band_1k_2k",
        "band_2k_4k",
        "band_4k_8k",
        "full_1k_8k",
    ]
    assert comparison["cross_mode"]["bias_sign"] == "multisine_minus_sweep"
    assert comparison["reliability"]["repeat_type"] == "REPOS"
    assert comparison["reliability"]["normalization"] == "mean_one"


def test_dev_c7_comparison_validation_config_resolves() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c7_comparison_metrics.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["comparison_metrics"]["provisional"] is True
    assert resolved["comparison_metrics"]["cross_mode"]["bias_sign"] == (
        "multisine_minus_sweep"
    )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda c: c["frequency_bands"].append(dict(c["frequency_bands"][0])), "band_id"),
        (lambda c: c["frequency_bands"][0].update({"f_min_hz": 3000}), "frequency band"),
        (lambda c: c["frequency_bands"][0].update({"boundary": "inclusive"}), "boundary"),
        (lambda c: c["configuration_comparison"].update({"candidate_configuration": "U4SYM"}), "candidate"),
        (lambda c: c["configuration_comparison"].update({"ratio_minimum_denominator": 0}), "denominator"),
        (lambda c: c["cross_mode"].update({"bias_sign": "sweep_minus_multisine"}), "bias_sign"),
        (lambda c: c["cross_mode"].update({"minimum_common_tones": 0}), "common_valid_tones"),
        (lambda c: c["reliability"].update({"repeat_type": "CONT"}), "REPOS"),
        (lambda c: c["reliability"].update({"allowed_scope_roles": ["development", "final_test"]}), "final_test"),
        (lambda c: c["reliability"].update({"floor_db": 0}), "variance_floor"),
        (lambda c: c["reliability"].update({"maximum_raw_weight": 0}), "maximum_raw_weight"),
        (lambda c: c["reliability"].update({"normalization": "sum_one"}), "mean_one"),
    ],
)
def test_comparison_metrics_config_rejects_invalid_values(mutator, message) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    mutator(resolved["comparison_metrics"])

    with pytest.raises(ConfigError, match=message):
        validate_config(resolved)


def test_dev_c6_config_migrates_to_p4b_defaults_without_rewriting(tmp_path) -> None:
    path = tmp_path / "dev-c6.yaml"
    payload = {
        "pipeline_version": "2.0.0-dev.12",
        "schema_versions": {
            "config": "2.11.0",
            "measurement": "2.4.0",
            "feature": "2.2.0",
        },
        "measurement_mode": "rew_sweep",
        "run_purpose": "software_validation",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["pipeline_version"] == "2.0.0-dev.20"
    assert resolved["comparison_metrics"]["schema_version"] == "1.0.0"
    assert any("2.11.0" in item for item in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


def test_dataset_quality_config_rejects_final_test_as_reference_role() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    resolved["dataset_quality_control"]["same_condition_outliers"][
        "reference_role_by_evaluation_role"
    ]["final_test"] = "final_test"

    with pytest.raises(ConfigError, match="final_test.*reference"):
        validate_config(resolved)


def test_dev_c5_config_migrates_to_p2b_defaults_without_rewriting(tmp_path) -> None:
    path = tmp_path / "dev-c5.yaml"
    payload = {
        "pipeline_version": "2.0.0-dev.11",
        "schema_versions": {
            "config": "2.10.0",
            "measurement": "2.4.0",
            "feature": "2.2.0",
        },
        "measurement_mode": "rew_sweep",
        "run_purpose": "software_validation",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(
        path,
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["pipeline_version"] == "2.0.0-dev.20"
    assert resolved["dataset_quality_control"]["schema_version"] == "1.0.0"
    assert any("2.10.0" in item for item in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("minimum_common_valid_features",), 0, "common_valid_features"),
        (("minimum_common_valid_fraction",), 0.0, "common_valid_fraction"),
        (("minimum_common_valid_fraction",), 1.1, "common_valid_fraction"),
        (("minimum_direction_count",), 0, "minimum_direction_count"),
        (("center_direction_matrix",), "false", "center_direction_matrix"),
        (("repeatability_distance_metric",), "pearson", "repeatability"),
        (("morphology_gain", "distance_metric"), "cosine", "morphology_gain"),
        (("morphology_gain", "minimum_denominator"), 0.0, "minimum_denominator"),
    ],
)
def test_direction_metrics_config_rejects_invalid_values(
    path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    target = resolved["direction_metrics"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ConfigError, match=message):
        validate_config(resolved)


def test_dev_c10_hr_validation_config_is_explicit_and_provisional() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c10_hr_calibration.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    hr = resolved["hr_calibration"]
    assert resolved["pipeline_version"] == "2.0.0-dev.20"
    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert hr["enabled"] is True
    assert hr["provisional"] is True
    assert [item["resonator_id"] for item in hr["resonators"]] == ["R1", "R2", "R3"]
    assert all(item["integration"]["method"] == "fixed_half_width_around_measured_peak" for item in hr["resonators"])


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("drift", "minimum_valid_peaks", 1), "minimum_valid_peaks"),
        (("energy_fraction", "sum_tolerance", 0.0), "tolerance"),
        (("resonators", 0, "minimum_prominence_db", -1.0), "prominence"),
        (("resonators", 0, "minimum_peak_distance_hz", 0.0), "distance"),
        (("resonators", 0, "bandwidth_drop_db", 0.0), "bandwidth_drop"),
        (("resonators", 0, "boundary", "mirror"), "boundary"),
    ],
)
def test_hr_calibration_config_rejects_invalid_values(mutation, message) -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c10_hr_calibration.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    target = resolved["hr_calibration"]
    if mutation[0] == "resonators":
        target["resonators"][mutation[1]][mutation[2]] = mutation[3]
    else:
        target[mutation[0]][mutation[1]] = mutation[2]
    with pytest.raises(ConfigError, match=message):
        validate_config(resolved)


def test_hr_readout_config_is_disabled_by_default_and_rejects_method_mismatch() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    assert resolved["hr_readout"]["enabled"] is False
    resolved["hr_readout"]["enabled"] = True
    resolved["hr_readout"]["tone_mapping"]["method"] = "calibrated_window"

    with pytest.raises(ConfigError, match="mapping.*energy"):
        validate_config(resolved)


def test_dev_c11_hr_readout_config_is_explicit_provisional_and_windowed() -> None:
    resolved = load_config(
        PROJECT_ROOT / "config" / "validation_dev_c11_hr_readout.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    readout = resolved["hr_readout"]
    assert resolved["pipeline_version"] == "2.0.0-dev.20"
    assert resolved["schema_versions"] == {
        "config": "2.19.0", "measurement": "2.4.0", "feature": "2.3.0"
    }
    assert readout["enabled"] is True
    assert readout["provisional"] is True
    assert readout["tone_mapping"]["method"] == "calibrated_window"
    assert readout["energy"]["method"] == "narrowband_trapezoid"
    assert readout["phase_policy"] == "magnitude_only"
    assert readout["uncertainty"]["method"] == "unavailable"


def test_dev_c10_config_migrates_to_disabled_p6b_without_rewriting(tmp_path) -> None:
    path = tmp_path / "dev-c10.yaml"
    payload = {
        "pipeline_version": "2.0.0-dev.16",
        "schema_versions": {
            "config": "2.15.0", "measurement": "2.4.0", "feature": "2.2.0"
        },
        "measurement_mode": "rew_sweep",
        "run_purpose": "software_validation",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["schema_versions"]["feature"] == "2.3.0"
    assert resolved["hr_readout"]["enabled"] is False
    assert any("2.15.0" in item for item in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


def test_dev_c12_tone_selection_defaults_are_disabled_and_leakage_safe() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")

    selection = resolved["tone_selection"]
    assert selection["enabled"] is False
    assert selection["provisional"] is True
    assert selection["scoring"]["optional_missing_policy"] == (
        "renormalize_available_weights_with_warning"
    )
    assert selection["selection"]["allow_partial"] is False


def test_dev_c11_config_migrates_to_disabled_p9a_without_rewriting(tmp_path) -> None:
    path = tmp_path / "dev-c11.yaml"
    payload = {
        "pipeline_version": "2.0.0-dev.17",
        "schema_versions": {
            "config": "2.16.0", "measurement": "2.4.0", "feature": "2.3.0"
        },
        "measurement_mode": "rew_sweep",
        "run_purpose": "software_validation",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["tone_selection"]["enabled"] is False
    assert any("tone_selection.enabled=false" in item for item in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload


@pytest.mark.parametrize(
    "mutator",
    [
        lambda block: block["eligibility"].update(minimum_valid_sample_fraction=0.0),
        lambda block: block["eligibility"].update(minimum_direction_count=1),
        lambda block: block["eligibility"].update(excluded_bands_hz=[[1000, 2000], [1500, 2500]]),
        lambda block: block["configuration_gain"].update(candidate_configuration="U4SYM"),
        lambda block: block["scoring"]["components"]["between_direction_variance"].update(weight=-1.0),
        lambda block: block["scoring"]["variance_ratio"].update(within_cont_weight=0.0, within_repos_weight=0.0),
        lambda block: block["selection"].update(minimum_spacing_bins=0),
        lambda block: block["selection"].update(band_quotas=[{"band_id": "a", "f_min_hz": 1000, "f_max_hz": 2000, "minimum_count": 1, "maximum_count": 2}, {"band_id": "b", "f_min_hz": 1500, "f_max_hz": 2500, "minimum_count": 1, "maximum_count": 2}]),
    ],
)
def test_tone_selection_config_rejects_invalid_threshold_weight_and_quota_contracts(mutator) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    mutator(resolved["tone_selection"])
    with pytest.raises(ConfigError, match="tone_selection"):
        validate_config(resolved)


def test_dev_c14_cross_mode_bridge_defaults_are_disabled_and_strict() -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    bridge = resolved["cross_mode_bridge"]
    assert bridge["schema_version"] == "1.0.0"
    assert bridge["enabled"] is False
    assert bridge["mapping_direction"] == "multisine_db_to_sweep_projection_db"
    assert bridge["methods"] == ["identity", "bias_only", "per_tone_affine"]
    assert bridge["final_test_policy"] == "sealed"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value["fit"].update({"minimum_pairs_per_tone": 1}),
        lambda value: value["fit"].update({"minimum_input_variance_db2": 0}),
        lambda value: value["fit"].update({"slope_bounds": [1.5, 0.5]}),
        lambda value: value["fit"]["residual_policy"].update({"warning_above_rms_db": 2.0}),
        lambda value: value.update({"methods": ["per_tone_affine", "identity"]}),
        lambda value: value.update({"final_test_policy": "read"}),
    ],
)
def test_cross_mode_bridge_rejects_ambiguous_or_unsafe_policy(mutator) -> None:
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    mutator(resolved["cross_mode_bridge"])
    with pytest.raises(ConfigError, match="cross_mode_bridge"):
        validate_config(resolved)


def test_config_218_migrates_with_cross_mode_bridge_disabled_without_rewriting(
    tmp_path,
) -> None:
    path = tmp_path / "config-218.yaml"
    payload = {
        "pipeline_version": "2.0.0-dev.19",
        "schema_versions": {
            "config": "2.18.0",
            "measurement": "2.4.0",
            "feature": "2.3.0",
        },
        "measurement_mode": "rew_sweep",
        "run_purpose": "software_validation",
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    resolved = load_config(path, default_path=PROJECT_ROOT / "config" / "default.yaml")

    assert resolved["pipeline_version"] == "2.0.0-dev.20"
    assert resolved["schema_versions"]["config"] == "2.19.0"
    assert resolved["cross_mode_bridge"]["enabled"] is False
    assert any(
        "P9-C is never enabled silently" in item
        for item in resolved["_runtime"]["migration_warnings"]
    )
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from acoustic_encoder.config import ConfigError, load_config, validate_config
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
    with pytest.raises(ConfigError, match="positive window_hz"):
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


def test_dev_c1_uses_incremented_pipeline_and_config_schema_versions() -> None:
    assert SCHEMA_VERSION_QUARTET == {
        "pipeline_version": "2.0.0-dev.7",
        "config_schema_version": "2.6.0",
        "measurement_schema_version": "2.4.0",
        "feature_schema_version": "2.0.0",
    }


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
        "config": "2.6.0",
        "measurement": "2.4.0",
        "feature": "2.0.0",
    }
    assert any(old_config in warning for warning in resolved["_runtime"]["migration_warnings"])
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == payload

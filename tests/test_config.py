from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from acoustic_encoder.config import ConfigError, load_config
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


def test_p8a_uses_incremented_config_schema_version() -> None:
    assert SCHEMA_VERSION_QUARTET == {
        "pipeline_version": "2.0.0-dev.3",
        "config_schema_version": "2.2.0",
        "measurement_schema_version": "2.2.0",
        "feature_schema_version": "2.0.0",
    }

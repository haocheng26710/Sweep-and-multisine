from __future__ import annotations

import yaml
import pytest

from acoustic_encoder.config import ConfigError, load_config


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

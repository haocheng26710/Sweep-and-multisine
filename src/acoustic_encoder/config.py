"""Versioned YAML configuration loading and validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from .research_gate import RunPurpose, normalize_run_purpose
from .schemas import MeasurementMode, normalize_measurement_mode
from .version import (
    CONFIG_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    PIPELINE_VERSION,
)


class ConfigError(ValueError):
    """Raised when a resolved configuration is internally inconsistent."""


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ConfigError(f"Configuration root must be a mapping: {path}")
    return payload


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_config(
    config_path: str | Path,
    *,
    default_path: str | Path | None = None,
) -> dict[str, Any]:
    config_path = Path(config_path).resolve()
    if default_path is None:
        candidate = config_path.parent / "default.yaml"
        default_path = candidate if candidate.is_file() and candidate != config_path else None
    defaults = _read_yaml(Path(default_path).resolve()) if default_path else {}
    provided = _read_yaml(config_path)
    migration_warnings: list[str] = []
    if "measurement_mode" not in provided and "measurement_mode" not in defaults:
        provided["measurement_mode"] = MeasurementMode.REW_SWEEP.value
        migration_warnings.append(
            "Legacy config had no measurement_mode; resolved as rew_sweep without modifying the source YAML."
        )
    resolved = deep_merge(defaults, provided)
    resolved.setdefault("run_purpose", RunPurpose.SOFTWARE_VALIDATION.value)
    resolved["measurement_mode"] = normalize_measurement_mode(
        resolved.get("measurement_mode", MeasurementMode.REW_SWEEP.value)
    ).value
    resolved.setdefault("pipeline_version", PIPELINE_VERSION)
    resolved.setdefault(
        "schema_versions",
        {
            "config": CONFIG_SCHEMA_VERSION,
            "measurement": MEASUREMENT_SCHEMA_VERSION,
            "feature": FEATURE_SCHEMA_VERSION,
        },
    )
    resolved.setdefault("_runtime", {})["migration_warnings"] = migration_warnings
    validate_config(resolved)
    return resolved


def validate_config(config: Mapping[str, Any]) -> None:
    try:
        normalize_run_purpose(config["run_purpose"])
    except (KeyError, ValueError) as exc:
        raise ConfigError(
            "run_purpose must be software_validation or research_analysis"
        ) from exc
    try:
        normalize_measurement_mode(config["measurement_mode"])
    except (KeyError, ValueError) as exc:
        raise ConfigError("measurement_mode must be rew_sweep or schroeder_multisine") from exc
    versions = config.get("schema_versions", {})
    expected = {
        "config": CONFIG_SCHEMA_VERSION,
        "measurement": MEASUREMENT_SCHEMA_VERSION,
        "feature": FEATURE_SCHEMA_VERSION,
    }
    for name, supported in expected.items():
        if versions.get(name) != supported:
            raise ConfigError(
                f"Unsupported {name} schema version {versions.get(name)!r}; expected {supported!r}"
            )
    random_state = config.get("random_state", 0)
    if not isinstance(random_state, int) or random_state < 0:
        raise ConfigError("random_state must be a non-negative integer")
    preprocessing = config.get("preprocessing", {})
    band = preprocessing.get("analysis_band_hz", [1000, 8000])
    if len(band) != 2 or not 0 < float(band[0]) < float(band[1]):
        raise ConfigError("preprocessing.analysis_band_hz must be [positive_low, high]")
    smoothing = preprocessing.get("smoothing", {"method": "none"})
    method = smoothing.get("method")
    allowed = {"none", "moving_average_linear_hz", "gaussian_linear_hz", "fractional_octave"}
    if method not in allowed:
        raise ConfigError(f"Unsupported smoothing method: {method!r}")
    if method in {"moving_average_linear_hz", "gaussian_linear_hz"}:
        if float(smoothing.get("window_hz", 0)) <= 0:
            raise ConfigError(f"{method} requires a positive window_hz")
    if method == "fractional_octave" and float(smoothing.get("fraction", 0)) <= 0:
        raise ConfigError("fractional_octave requires a positive fraction")
    if method != "none" and smoothing.get("boundary") not in {"reflect", "nearest", "truncate"}:
        raise ConfigError("smoothing boundary must be reflect, nearest, or truncate")
    if "stimulus" in config:
        validate_stimulus_config(config["stimulus"])
    if "multisine_estimation" in config:
        estimation = config["multisine_estimation"]
        if estimation.get("synchronization_method") != "preamble_cross_correlation":
            raise ConfigError(
                "multisine_estimation.synchronization_method must be "
                "preamble_cross_correlation"
            )
        if estimation.get("period_averaging") not in {"complex_spectrum", "power"}:
            raise ConfigError(
                "multisine_estimation.period_averaging must be complex_spectrum or power"
            )


def validate_stimulus_config(stimulus: Mapping[str, Any]) -> None:
    required = [
        "stimulus_id",
        "tone_set_id",
        "sample_rate_hz",
        "period_samples",
        "target_peak_dbfs",
        "stable_period_count",
        "discard_initial_period_count",
        "tones",
        "amplitude",
        "phase",
        "wav_format",
    ]
    missing = [name for name in required if name not in stimulus]
    if missing:
        raise ConfigError(f"Stimulus configuration is missing: {missing}")
    sample_rate = int(stimulus["sample_rate_hz"])
    period_samples = int(stimulus["period_samples"])
    if sample_rate <= 0 or period_samples <= 0:
        raise ConfigError("sample_rate_hz and period_samples must be positive")
    if int(stimulus["stable_period_count"]) <= 0:
        raise ConfigError("stable_period_count must be positive")
    if int(stimulus["discard_initial_period_count"]) < 0:
        raise ConfigError("discard_initial_period_count cannot be negative")
    if float(stimulus["target_peak_dbfs"]) > 0:
        raise ConfigError("target_peak_dbfs cannot exceed 0 dBFS")
    if stimulus["wav_format"] not in {"float32", "pcm16"}:
        raise ConfigError("wav_format must be float32 or pcm16")
    tone_cfg = stimulus["tones"]
    mode = tone_cfg.get("mode")
    if mode == "range":
        spacing = float(tone_cfg["spacing_hz"])
        start = float(tone_cfg["start_hz"])
        stop = float(tone_cfg["stop_hz"])
        if spacing <= 0 or stop < start:
            raise ConfigError("Tone range requires positive spacing and stop_hz >= start_hz")
        frequencies = np.arange(
            start,
            stop + 0.5 * spacing,
            spacing,
        )
    elif mode == "explicit":
        frequencies = np.asarray(tone_cfg.get("frequencies_hz", []), dtype=float)
    else:
        raise ConfigError("stimulus.tones.mode must be range or explicit")
    if frequencies.size == 0 or np.any(~np.isfinite(frequencies)):
        raise ConfigError("At least one finite tone frequency is required")
    if len(np.unique(frequencies)) != frequencies.size:
        raise ConfigError("Tone frequencies must be unique")
    if np.any(frequencies <= 0) or np.any(frequencies >= sample_rate / 2):
        raise ConfigError("Every tone must lie strictly between 0 and Nyquist")
    bins = frequencies * period_samples / sample_rate
    if not np.allclose(bins, np.rint(bins), atol=1e-9, rtol=0):
        raise ConfigError("Every tone must lie on an integer DFT bin")
    amplitude = stimulus["amplitude"]
    if amplitude.get("mode") == "explicit":
        weights = amplitude.get("weights", [])
        if len(weights) != frequencies.size or any(float(item) <= 0 for item in weights):
            raise ConfigError("Explicit amplitude weights must be positive and match tone count")
    elif amplitude.get("mode") != "equal":
        raise ConfigError("amplitude.mode must be equal or explicit")
    if stimulus["phase"].get("method") not in {"schroeder", "zero"}:
        raise ConfigError("phase.method must be schroeder or zero")
    preamble = stimulus.get("preamble", {"type": "none"})
    if preamble.get("type", "none") not in {"none", "linear_chirp"}:
        raise ConfigError("preamble.type must be none or linear_chirp")
    if preamble.get("type") == "linear_chirp":
        start_hz = float(preamble.get("start_hz", 0))
        stop_hz = float(preamble.get("stop_hz", 0))
        if not 0 < start_hz < sample_rate / 2 or not 0 < stop_hz < sample_rate / 2:
            raise ConfigError("preamble chirp frequencies must lie below Nyquist")
        if float(preamble.get("duration_s", 0)) <= 0:
            raise ConfigError("preamble chirp duration_s must be positive")

"""Versioned YAML configuration loading and validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from .preprocessing import build_dense_grid
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


_P3_PREPROCESSING_DEFAULTS: dict[str, Any] = {
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

_MATCHED_TONE_DEFAULTS: dict[str, Any] = {
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
    supplied_preprocessing = resolved.get("preprocessing", {})
    if not isinstance(supplied_preprocessing, Mapping):
        raise ConfigError("preprocessing must be a mapping")
    resolved["preprocessing"] = deep_merge(
        _P3_PREPROCESSING_DEFAULTS,
        supplied_preprocessing,
    )
    supplied_matched_tones = resolved.get("matched_tone_features", {})
    if not isinstance(supplied_matched_tones, Mapping):
        raise ConfigError("matched_tone_features must be a mapping")
    resolved["matched_tone_features"] = deep_merge(
        _MATCHED_TONE_DEFAULTS,
        supplied_matched_tones,
    )
    if "normalization" in resolved["preprocessing"]:
        legacy_normalization = resolved["preprocessing"].pop("normalization")
        migration_warnings.append(
            "Legacy preprocessing.normalization="
            f"{legacy_normalization!r} was retired; P3-A now emits raw, "
            "de-meaned, and z-score FeatureSets explicitly."
        )
    versions = resolved.get("schema_versions", {})
    prior_versions = (
        versions.get("config"),
        versions.get("measurement"),
        versions.get("feature"),
    )
    if prior_versions in {
        ("2.3.0", "2.3.0", "2.0.0"),
        ("2.4.0", "2.4.0", "2.0.0"),
        ("2.5.0", "2.4.0", "2.0.0"),
        ("2.6.0", "2.4.0", "2.0.0"),
        ("2.7.0", "2.4.0", "2.1.0"),
        ("2.8.0", "2.4.0", "2.1.0"),
    }:
        old_config_version = str(versions["config"])
        smoothing = resolved["preprocessing"].get("smoothing", {"method": "none"})
        if old_config_version != "2.8.0" and (
            not isinstance(smoothing, Mapping)
            or smoothing.get("method") != "none"
        ):
            raise ConfigError(
                "Legacy non-none smoothing was never implemented and cannot be "
                "migrated safely; choose an explicit DEV-C3 smoothing definition"
            )
        resolved["preprocessing"]["schema_version"] = "1.1.0"
        resolved["preprocessing"]["smoothing_domain"] = "db"
        resolved["pipeline_version"] = PIPELINE_VERSION
        resolved["schema_versions"] = {
            "config": CONFIG_SCHEMA_VERSION,
            "measurement": MEASUREMENT_SCHEMA_VERSION,
            "feature": FEATURE_SCHEMA_VERSION,
        }
        migration_warnings.append(
            f"Legacy config schema {old_config_version} was migrated in memory "
            f"to config schema {CONFIG_SCHEMA_VERSION} and measurement schema "
            f"{MEASUREMENT_SCHEMA_VERSION}; the source YAML was not modified."
        )
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
    paths = config.get("paths", {})
    if not isinstance(paths, Mapping):
        raise ConfigError("paths must be a mapping")
    for path_name in ("stimuli", "outputs"):
        if path_name in paths and not str(paths[path_name]).strip():
            raise ConfigError(f"paths.{path_name} must be a non-empty path")
    preprocessing = config.get("preprocessing")
    validate_preprocessing_config(preprocessing)
    validate_matched_tone_config(config.get("matched_tone_features"))
    assert isinstance(preprocessing, Mapping)
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
        clock_drift = estimation.get("clock_drift")
        if clock_drift is not None:
            if not isinstance(clock_drift, Mapping):
                raise ConfigError("multisine_estimation.clock_drift must be a mapping")
            if clock_drift.get("correction") not in {"disabled", "enabled"}:
                raise ConfigError(
                    "multisine_estimation.clock_drift.correction must be disabled or enabled"
                )
            try:
                warning_ppm = float(clock_drift["warning_ppm"])
                exclude_ppm = float(clock_drift["exclude_candidate_ppm"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ConfigError(
                    "multisine_estimation.clock_drift requires numeric warning_ppm "
                    "and exclude_candidate_ppm"
                ) from exc
            if not (
                np.isfinite(warning_ppm)
                and np.isfinite(exclude_ppm)
                and 0.0 < warning_ppm < exclude_ppm
            ):
                raise ConfigError(
                    "multisine_estimation.clock_drift requires "
                    "0 < warning_ppm < exclude_candidate_ppm"
                )
        tone_quality = estimation.get("tone_quality")
        if tone_quality is not None:
            validate_tone_quality_config(tone_quality)
    if "quality_control" in config:
        validate_quality_control_config(config["quality_control"])


def validate_matched_tone_config(value: Any) -> None:
    """Validate P3-C extraction, normalization, and pair-matching semantics."""
    if not isinstance(value, Mapping):
        raise ConfigError("matched_tone_features must be a mapping")
    required_top = {
        "schema_version",
        "provisional",
        "tone_ordering",
        "sweep_extraction",
        "normalization",
        "matching",
    }
    if set(value) != required_top:
        raise ConfigError(
            "matched_tone_features must contain exactly: "
            + ", ".join(sorted(required_top))
        )
    if value.get("schema_version") != "1.0.0":
        raise ConfigError("matched_tone_features.schema_version must be 1.0.0")
    if not isinstance(value.get("provisional"), bool):
        raise ConfigError("matched_tone_features.provisional must be boolean")
    if value.get("tone_ordering") != "manifest_tone_index":
        raise ConfigError(
            "matched_tone_features.tone_ordering must be manifest_tone_index"
        )

    extraction = value.get("sweep_extraction")
    if not isinstance(extraction, Mapping):
        raise ConfigError("matched_tone_features.sweep_extraction must be a mapping")
    method = extraction.get("method")
    if method == "single_point_linear":
        if set(extraction) != {"method"}:
            raise ConfigError("single_point_linear only accepts the method field")
    elif method == "narrowband_integration":
        required = {
            "method",
            "full_bandwidth_hz",
            "integration_domain",
            "minimum_band_coverage",
            "overlap_policy",
        }
        if set(extraction) != required:
            raise ConfigError(
                "narrowband_integration requires exactly method, full_bandwidth_hz, "
                "integration_domain, minimum_band_coverage, and overlap_policy"
            )
        bandwidth = _finite_number(
            extraction,
            "full_bandwidth_hz",
            "matched tone full_bandwidth_hz",
        )
        if bandwidth <= 0:
            raise ConfigError("matched tone full_bandwidth_hz must be positive")
        if extraction.get("integration_domain") != "linear_power_ratio":
            raise ConfigError(
                "matched tone integration_domain must be linear_power_ratio"
            )
        coverage = _finite_number(
            extraction,
            "minimum_band_coverage",
            "matched tone minimum_band_coverage",
        )
        if not 0.0 < coverage <= 1.0:
            raise ConfigError("matched tone minimum_band_coverage must lie in (0, 1]")
        if extraction.get("overlap_policy") != "reject":
            raise ConfigError("matched tone overlap_policy must be reject")
    else:
        raise ConfigError(
            "matched tone sweep_extraction.method must be single_point_linear "
            "or narrowband_integration"
        )

    normalization = value.get("normalization")
    if not isinstance(normalization, Mapping) or set(normalization) != {
        "method",
        "minimum_valid_tones",
        "minimum_std_db",
    }:
        raise ConfigError(
            "matched tone normalization requires method, minimum_valid_tones, "
            "and minimum_std_db"
        )
    if normalization.get("method") not in {
        "none",
        "subtract_mean_db",
        "zscore_within_sample",
    }:
        raise ConfigError(
            "matched tone normalization.method must be none, subtract_mean_db, "
            "or zscore_within_sample"
        )
    minimum_valid = normalization.get("minimum_valid_tones")
    if (
        isinstance(minimum_valid, bool)
        or not isinstance(minimum_valid, int)
        or minimum_valid < 1
    ):
        raise ConfigError("matched tone minimum_valid_tones must be an integer >= 1")
    minimum_std = _finite_number(
        normalization,
        "minimum_std_db",
        "matched tone minimum_std_db",
    )
    if minimum_std <= 0:
        raise ConfigError("matched tone minimum_std_db must be positive")

    matching = value.get("matching")
    if not isinstance(matching, Mapping) or set(matching) != {
        "minimum_common_valid_tones"
    }:
        raise ConfigError(
            "matched tone matching requires only minimum_common_valid_tones"
        )
    minimum_common = matching.get("minimum_common_valid_tones")
    if (
        isinstance(minimum_common, bool)
        or not isinstance(minimum_common, int)
        or minimum_common < 1
    ):
        raise ConfigError(
            "matched tone minimum_common_valid_tones must be an integer >= 1"
        )


def validate_preprocessing_config(preprocessing: Any) -> None:
    """Validate the complete, provisional dense-P3 preprocessing contract."""
    if not isinstance(preprocessing, Mapping):
        raise ConfigError("preprocessing must be a mapping")
    if preprocessing.get("schema_version") != "1.1.0":
        raise ConfigError("preprocessing.schema_version must be 1.1.0")
    if not isinstance(preprocessing.get("provisional"), bool):
        raise ConfigError("preprocessing.provisional must be boolean")
    band = preprocessing.get("analysis_band_hz")
    try:
        low, high = (float(value) for value in band)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            "preprocessing.analysis_band_hz must be [positive_low, high]"
        ) from exc
    if not (np.isfinite(low) and np.isfinite(high) and 0.0 < low < high):
        raise ConfigError(
            "preprocessing.analysis_band_hz must be [positive_low, high]"
        )
    step = _finite_number(
        preprocessing,
        "common_grid_step_hz",
        "preprocessing.common_grid_step_hz",
    )
    if step <= 0.0:
        raise ConfigError("preprocessing.common_grid_step_hz must be positive")
    try:
        build_dense_grid(preprocessing)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"preprocessing grid is invalid: {exc}") from exc
    if preprocessing.get("interpolation") != "linear":
        raise ConfigError("preprocessing.interpolation must be linear")
    maximum_gap = _finite_number(
        preprocessing,
        "maximum_interpolation_gap_hz",
        "preprocessing.maximum_interpolation_gap_hz",
    )
    if maximum_gap <= 0.0:
        raise ConfigError(
            "preprocessing.maximum_interpolation_gap_hz must be positive"
        )
    valid_fraction = _finite_number(
        preprocessing,
        "minimum_valid_grid_fraction",
        "preprocessing.minimum_valid_grid_fraction",
    )
    if not 0.0 < valid_fraction <= 1.0:
        raise ConfigError(
            "preprocessing.minimum_valid_grid_fraction must lie in (0, 1]"
        )
    normalization_band = preprocessing.get("normalization_band_hz")
    try:
        normalization_low, normalization_high = (
            float(value) for value in normalization_band
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            "preprocessing.normalization_band_hz must be [low, high]"
        ) from exc
    if not (
        np.isfinite(normalization_low)
        and np.isfinite(normalization_high)
        and low <= normalization_low < normalization_high <= high
    ):
        raise ConfigError(
            "preprocessing.normalization_band_hz must be ordered and contained "
            "in analysis_band_hz"
        )
    minimum_points = preprocessing.get("minimum_normalization_points")
    if (
        isinstance(minimum_points, bool)
        or not isinstance(minimum_points, int)
        or minimum_points < 2
    ):
        raise ConfigError(
            "preprocessing.minimum_normalization_points must be an integer >= 2"
        )
    minimum_std = _finite_number(
        preprocessing,
        "minimum_zscore_std_db",
        "preprocessing.minimum_zscore_std_db",
    )
    if minimum_std <= 0.0:
        raise ConfigError("preprocessing.minimum_zscore_std_db must be positive")
    if "smoothing_hz" in preprocessing:
        raise ConfigError(
            "preprocessing.smoothing_hz is ambiguous; choose an explicit smoothing method"
        )
    if preprocessing.get("smoothing_domain") != "db":
        raise ConfigError("preprocessing.smoothing_domain must be db")
    smoothing = preprocessing.get("smoothing")
    if not isinstance(smoothing, Mapping):
        raise ConfigError("preprocessing.smoothing must be a mapping")
    method = smoothing.get("method")
    expected_fields = {
        "none": {"method"},
        "moving_average_linear_hz": {
            "method", "window_hz", "boundary", "minimum_kernel_coverage",
        },
        "gaussian_linear_hz": {
            "method", "sigma_hz", "truncate_sigma", "boundary",
            "minimum_kernel_coverage",
        },
        "fractional_octave": {
            "method", "fraction_denominator", "boundary",
            "minimum_kernel_coverage", "weighting_definition",
        },
    }
    if method not in expected_fields:
        raise ConfigError(f"Unsupported smoothing method: {method!r}")
    actual_fields = set(smoothing)
    expected = expected_fields[str(method)]
    if actual_fields != expected:
        if method == "none":
            raise ConfigError("smoothing method none only accepts the method field")
        missing = sorted(expected - actual_fields)
        unexpected = sorted(actual_fields - expected)
        raise ConfigError(
            f"smoothing method {method} requires exact fields; "
            f"missing={missing}, unexpected={unexpected}"
        )
    if method == "none":
        return
    if smoothing.get("boundary") not in {"reflect", "nearest", "truncate"}:
        raise ConfigError("smoothing boundary must be reflect, nearest, or truncate")
    coverage = _finite_number(
        smoothing,
        "minimum_kernel_coverage",
        "smoothing.minimum_kernel_coverage",
    )
    if not 0.0 < coverage <= 1.0:
        raise ConfigError("smoothing.minimum_kernel_coverage must lie in (0, 1]")
    if method == "moving_average_linear_hz":
        if _finite_number(smoothing, "window_hz", "smoothing.window_hz") <= 0.0:
            raise ConfigError("smoothing.window_hz must be positive")
    elif method == "gaussian_linear_hz":
        if _finite_number(smoothing, "sigma_hz", "smoothing.sigma_hz") <= 0.0:
            raise ConfigError("smoothing.sigma_hz must be positive")
        if _finite_number(
            smoothing, "truncate_sigma", "smoothing.truncate_sigma"
        ) <= 0.0:
            raise ConfigError("smoothing.truncate_sigma must be positive")
    else:
        _positive_integer(
            smoothing,
            "fraction_denominator",
            "smoothing.fraction_denominator",
        )
        if smoothing.get("weighting_definition") != (
            "rectangular_uniform_linear_grid_db"
        ):
            raise ConfigError(
                "fractional_octave weighting_definition must be "
                "rectangular_uniform_linear_grid_db"
            )


def validate_quality_control_config(quality: Any) -> None:
    """Validate provisional shared P2 thresholds and aggregation policies."""
    if not isinstance(quality, Mapping):
        raise ConfigError("quality_control must be a mapping")
    if quality.get("schema_version") != "1.0.0":
        raise ConfigError("quality_control.schema_version must be 1.0.0")
    if not isinstance(quality.get("provisional"), bool):
        raise ConfigError("quality_control.provisional must be boolean")
    modes = quality.get("modes")
    if not isinstance(modes, Mapping):
        raise ConfigError("quality_control.modes must be a mapping")
    for mode in MeasurementMode:
        mode_quality = modes.get(mode.value)
        label = f"quality_control.modes.{mode.value}"
        if not isinstance(mode_quality, Mapping):
            raise ConfigError(f"{label} must be a mapping")
        minimum_points = mode_quality.get("minimum_valid_points")
        if (
            isinstance(minimum_points, bool)
            or not isinstance(minimum_points, int)
            or minimum_points <= 0
        ):
            raise ConfigError(f"{label}.minimum_valid_points must be positive")
        frequency_range = mode_quality.get("required_frequency_range_hz")
        try:
            low, high = (float(value) for value in frequency_range)
        except (TypeError, ValueError) as exc:
            raise ConfigError(
                f"{label}.required_frequency_range_hz must be [positive_low, high]"
            ) from exc
        if not (np.isfinite(low) and np.isfinite(high) and 0.0 < low < high):
            raise ConfigError(
                f"{label}.required_frequency_range_hz must be [positive_low, high]"
            )
        if mode_quality.get("unavailable_required_check_policy") not in {
            "preserve",
            "warning",
        }:
            raise ConfigError(
                f"{label}.unavailable_required_check_policy must be preserve or warning"
            )
        allowed_phase = (
            {"optional", "required_warning"}
            if mode is MeasurementMode.REW_SWEEP
            else {"upstream_authoritative"}
        )
        if mode_quality.get("phase_policy") not in allowed_phase:
            raise ConfigError(
                f"{label}.phase_policy must be one of {sorted(allowed_phase)}"
            )
        if mode_quality.get("phase_inconsistency_status") not in {
            "warning",
            "exclude_candidate",
        }:
            raise ConfigError(
                f"{label}.phase_inconsistency_status must be warning or exclude_candidate"
            )
        magnitude = mode_quality.get("magnitude_db")
        if not isinstance(magnitude, Mapping):
            raise ConfigError(f"{label}.magnitude_db must be a mapping")
        try:
            warning_low, warning_high = (
                float(value) for value in magnitude["warning_bounds"]
            )
            exclude_low, exclude_high = (
                float(value) for value in magnitude["exclude_candidate_bounds"]
            )
            warning_range = float(magnitude["warning_dynamic_range_db"])
            exclude_range = float(
                magnitude["exclude_candidate_dynamic_range_db"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"{label}.magnitude_db thresholds must be numeric") from exc
        numeric = (
            warning_low,
            warning_high,
            exclude_low,
            exclude_high,
            warning_range,
            exclude_range,
        )
        if not all(np.isfinite(value) for value in numeric) or not (
            exclude_low <= warning_low < warning_high <= exclude_high
            and 0.0 < warning_range < exclude_range
        ):
            raise ConfigError(
                f"{label}.magnitude_db warning/exclude thresholds are not ordered"
            )
        required = mode_quality.get("required_upstream_checks")
        if not isinstance(required, list) or any(
            not isinstance(item, str) or not item.strip() for item in required
        ):
            raise ConfigError(
                f"{label}.required_upstream_checks must be a list of check IDs"
            )


def _finite_number(mapping: Mapping[str, Any], key: str, label: str) -> float:
    if isinstance(mapping.get(key), bool):
        raise ConfigError(f"{label} must be numeric")
    try:
        value = float(mapping[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"{label} must be numeric") from exc
    if not np.isfinite(value):
        raise ConfigError(f"{label} must be finite")
    return value


def _positive_integer(mapping: Mapping[str, Any], key: str, label: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{label} must be a positive integer")
    return value


def _ratio_thresholds(
    mapping: Mapping[str, Any],
    *,
    warning_key: str,
    exclude_key: str,
    label: str,
    upper_bound: float | None = None,
) -> tuple[float, float]:
    warning = _finite_number(mapping, warning_key, f"{label} warning")
    exclude = _finite_number(mapping, exclude_key, f"{label} exclude_candidate")
    valid = 0.0 <= warning < exclude
    if upper_bound is not None:
        valid = valid and exclude <= upper_bound
    if not valid:
        suffix = f" <= {upper_bound:g}" if upper_bound is not None else ""
        raise ConfigError(
            f"{label} warning/exclude thresholds require "
            f"0 <= warning < exclude_candidate{suffix}"
        )
    return warning, exclude


def validate_tone_quality_config(quality: Mapping[str, Any]) -> None:
    """Validate every P8-B2 threshold and FFT-neighborhood definition."""
    if not isinstance(quality, Mapping):
        raise ConfigError("multisine_estimation.tone_quality must be a mapping")
    required_sections = (
        "neighborhood",
        "clipping",
        "snr",
        "leakage",
        "missing_tone",
        "period_stability",
        "non_excited_energy",
    )
    missing = [name for name in required_sections if not isinstance(quality.get(name), Mapping)]
    if missing:
        raise ConfigError(f"multisine_estimation.tone_quality sections are missing: {missing}")

    neighborhood = quality["neighborhood"]
    guard = neighborhood.get("tone_guard_bins")
    if isinstance(guard, bool) or not isinstance(guard, int) or guard < 0:
        raise ConfigError("tone_guard_bins must be a non-negative integer")
    leakage_radius = _positive_integer(
        neighborhood, "leakage_radius_bins", "leakage_radius_bins"
    )
    noise_inner = _positive_integer(
        neighborhood, "noise_inner_radius_bins", "noise_inner_radius_bins"
    )
    noise_outer = _positive_integer(
        neighborhood, "noise_outer_radius_bins", "noise_outer_radius_bins"
    )
    if not guard < leakage_radius < noise_inner <= noise_outer:
        raise ConfigError(
            "tone-quality neighborhood radii require "
            "tone_guard < leakage_radius < noise_inner <= noise_outer"
        )
    _positive_integer(neighborhood, "minimum_noise_bins", "minimum_noise_bins")
    _positive_integer(
        neighborhood, "minimum_leakage_bins", "minimum_leakage_bins"
    )

    clipping = quality["clipping"]
    sample_threshold = _finite_number(
        clipping,
        "sample_threshold_fraction_full_scale",
        "sample_threshold_fraction_full_scale",
    )
    if not 0.0 < sample_threshold <= 1.0:
        raise ConfigError(
            "sample_threshold_fraction_full_scale must lie in (0, 1]"
        )
    _ratio_thresholds(
        clipping,
        warning_key="warning_fraction",
        exclude_key="exclude_candidate_fraction",
        label="clipping",
        upper_bound=1.0,
    )
    if not isinstance(clipping.get("record_longest_run"), bool):
        raise ConfigError("clipping.record_longest_run must be boolean")

    snr = quality["snr"]
    if snr.get("method") != "median_local_non_excited_bin_power":
        raise ConfigError(
            "tone_quality.snr.method must be median_local_non_excited_bin_power"
        )
    snr_warning = _finite_number(snr, "warning_below_db", "SNR warning")
    snr_exclude = _finite_number(
        snr, "exclude_candidate_below_db", "SNR exclude_candidate"
    )
    if not snr_warning > snr_exclude:
        raise ConfigError(
            "SNR warning/exclude thresholds require warning_below_db > "
            "exclude_candidate_below_db"
        )

    _ratio_thresholds(
        quality["leakage"],
        warning_key="warning_ratio",
        exclude_key="exclude_candidate_ratio",
        label="leakage",
    )
    missing_tone = quality["missing_tone"]
    _finite_number(missing_tone, "minimum_snr_db", "missing-tone minimum_snr_db")
    _finite_number(
        missing_tone, "minimum_magnitude_db", "missing-tone minimum_magnitude_db"
    )

    stability = quality["period_stability"]
    if stability.get("method") not in {
        "complex_relative_variance",
        "power_relative_variance",
    }:
        raise ConfigError(
            "period_stability.method must be complex_relative_variance or "
            "power_relative_variance"
        )
    minimum_periods = _positive_integer(
        stability, "minimum_periods", "minimum_periods"
    )
    if minimum_periods < 2:
        raise ConfigError("period_stability.minimum_periods must be at least 2")
    _ratio_thresholds(
        stability,
        warning_key="warning_variance_ratio",
        exclude_key="exclude_candidate_variance_ratio",
        label="period stability",
    )

    off_tone = quality["non_excited_energy"]
    _positive_integer(off_tone, "minimum_bin_count", "non-excited minimum_bin_count")
    _ratio_thresholds(
        off_tone,
        warning_key="warning_ratio",
        exclude_key="exclude_candidate_ratio",
        label="non-excited energy",
        upper_bound=1.0,
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
    if np.any(np.diff(frequencies) <= 0):
        raise ConfigError("Tone frequencies must be strictly increasing")
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

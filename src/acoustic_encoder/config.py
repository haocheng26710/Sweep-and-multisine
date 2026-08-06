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

_TONE_SELECTION_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "enabled": False,
    "provisional": True,
    "eligibility": {
        "analysis_band_hz": [1000.0, 8000.0],
        "edge_guard_hz": 0.0,
        "minimum_valid_sample_fraction": 0.8,
        "minimum_direction_count": 4,
        "minimum_cont_pairs": 1,
        "minimum_repos_pairs": 1,
        "effective_energy_range_db": [-120.0, 160.0],
        "excluded_bands_hz": [],
        "excluded_band_safety_distance_hz": 0.0,
    },
    "configuration_gain": {
        "baseline_configuration": "U4SYM",
        "candidate_configuration": "U4ENC",
        "epsilon_db_squared": 1.0e-12,
    },
    "reliability": {
        "minimum_pairs_per_tone": 1,
        "snr_target_db": 30.0,
        "stability_scale_db": 1.0,
        "noise_scale_db": 10.0,
    },
    "scoring": {
        "method": "weighted_rank_sum",
        "epsilon_db_squared": 1.0e-12,
        "optional_missing_policy": "renormalize_available_weights_with_warning",
        "tie_method": "average",
        "components": {
            "between_direction_variance": {"required": True, "direction": "higher", "weight": 2.0},
            "within_cont_variance": {"required": True, "direction": "lower", "weight": 1.0},
            "within_repos_variance": {"required": True, "direction": "lower", "weight": 1.0},
            "configuration_gain": {"required": True, "direction": "higher", "weight": 1.0},
            "sweep_repeatability": {"required": False, "direction": "lower", "weight": 0.5},
            "effective_energy_margin": {"required": True, "direction": "higher", "weight": 0.5},
            "instability_noise_penalty": {"required": False, "direction": "lower", "weight": 0.25},
            "excluded_band_proximity": {"required": False, "direction": "lower", "weight": 0.25},
        },
        "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 1.0},
    },
    "selection": {
        "target_count": 8,
        "minimum_spacing_hz": 100.0,
        "minimum_spacing_bins": 1,
        "allow_partial": False,
        "band_quotas": [],
    },
}

_TONE_PROJECTION_ABLATION_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "enabled": False,
    "provisional": True,
    "input_feature_kind": "tone_projection_from_sweep",
    "measurement_mode": "rew_sweep",
    "subset_sizes": [3, 4, 5, 6, 8],
    "prefix_order": "p9a_selection_rank",
    "outer_protocol": "leave_one_session_out",
    "inner_protocol": "leave_one_session_out",
    "minimum_inner_groups": 2,
    "minimum_valid_inner_folds": 2,
    "model": "logistic_regression",
    "minimum_training_features": 2,
    "minimum_prediction_coverage": 1.0,
    "p4_denominator_floor": 1.0e-12,
    "p4_retention_modes": {
        "effective_rank": "higher_is_better",
        "morphology_gain": "higher_is_better",
        "mean_off_diagonal_pearson": "absolute_fidelity",
        "median_direction_rms": "higher_is_better",
        "repos_repeatability_median_rms": "lower_is_better",
        "repos_reliability_median_db": "lower_is_better",
        "repos_reliability_available_fraction": "higher_is_better",
    },
    "decision_policy": {
        "minimum_p4_retention": 0.90,
        "maximum_balanced_accuracy_drop": 0.05,
        "maximum_macro_f1_drop": 0.05,
        "minimum_prediction_coverage": 1.0,
        "require_spacing_and_band_quotas": True,
    },
    "final_test_policy": "sealed",
    "cross_mode": "disabled",
}

_CROSS_MODE_BRIDGE_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "enabled": False,
    "provisional": True,
    "mapping_direction": "multisine_db_to_sweep_projection_db",
    "methods": ["identity", "bias_only", "per_tone_affine"],
    "tone_authority": "fold_specific_p9b_minimum",
    "fit": {
        "allowed_cohort_roles": ["development", "training"],
        "minimum_pairs_per_tone": 4,
        "minimum_input_variance_db2": 1.0e-6,
        "slope_bounds": [0.5, 1.5],
        "residual_policy": {
            "warning_above_rms_db": 0.25,
            "unavailable_above_rms_db": 1.0,
        },
    },
    "evaluation": {
        "minimum_common_tones": 2,
        "minimum_pair_coverage": 1.0,
    },
    "direction_templates": {
        "metric": "pearson",
        "minimum_common_tones": 2,
    },
    "classification": {
        "models": [
            "nearest_template_correlation",
            "nearest_centroid",
            "logistic_regression",
        ],
        "minimum_training_features": 2,
        "minimum_prediction_coverage": 1.0,
    },
    "final_test_policy": "sealed",
}

_OFFLINE_FAST_READOUT_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "enabled": False,
    "provisional": True,
    "model": {
        "model_id": "nearest_centroid",
        "model_domain": "multisine",
        "valid_mask_policy": "require_all_frozen_features",
        "tie_break": "configured_direction_order",
    },
    "calibration": {"mode": "disabled", "required_on_domain_mismatch": True},
    "qc": {
        "required_tone_coverage": 1.0,
        "phase_policy": "magnitude_only_warning",
        "p8_warning_action": "warning",
        "p8_exclude_candidate_action": "invalid",
    },
    "final_test_policy": "sealed",
    "output_overwrite": "reject",
}

_DIRECTION_METRICS_DEFAULTS: dict[str, Any] = {
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

_DATASET_QUALITY_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "provisional": True,
    "condition_completeness": {
        "direction_match_tolerance_deg": 1.0e-9,
        "missing_status": "exclude_candidate",
        "duplicate_status": "exclude_candidate",
        "unexpected_status": "exclude_candidate",
    },
    "same_condition_outliers": {
        "method": "coordinate_median_mad_rms",
        "center": "coordinate_median",
        "distance": "rms",
        "scale": "median_absolute_deviation",
        "mad_scale_factor": 1.4826,
        "minimum_reference_samples": 3,
        "minimum_common_valid_features": 5,
        "minimum_common_valid_fraction": 0.8,
        "minimum_scale": 1.0e-9,
        "warning_robust_z": 3.5,
        "exclude_candidate_robust_z": 6.0,
        "incompatible_contract_status": "exclude_candidate",
        "reference_role_by_evaluation_role": {
            "development": "development",
            "training": "development",
            "final_test": "training",
        },
    },
    "repeatability": {
        "distance": "rms",
        "minimum_common_valid_features": 5,
        "minimum_common_valid_fraction": 0.8,
        "minimum_qualified_pairs": 1,
        "thresholds_by_feature_kind": {
            "dense_raw_spl": {
                "units": "dB",
                "CONT": {"warning_above": 0.5, "exclude_candidate_above": 1.0},
                "REPOS": {"warning_above": 1.0, "exclude_candidate_above": 2.0},
                "REASM": {"warning_above": 2.0, "exclude_candidate_above": 4.0},
            },
            "dense_demeaned_db": {
                "units": "dB",
                "CONT": {"warning_above": 0.5, "exclude_candidate_above": 1.0},
                "REPOS": {"warning_above": 1.0, "exclude_candidate_above": 2.0},
                "REASM": {"warning_above": 2.0, "exclude_candidate_above": 4.0},
            },
            "dense_zscore": {
                "units": "dimensionless",
                "CONT": {"warning_above": 0.05, "exclude_candidate_above": 0.1},
                "REPOS": {"warning_above": 0.1, "exclude_candidate_above": 0.2},
                "REASM": {"warning_above": 0.2, "exclude_candidate_above": 0.4},
            },
            "tone_projection_from_sweep": {
                "units": "dB",
                "CONT": {"warning_above": 0.5, "exclude_candidate_above": 1.0},
                "REPOS": {"warning_above": 1.0, "exclude_candidate_above": 2.0},
                "REASM": {"warning_above": 2.0, "exclude_candidate_above": 4.0},
            },
            "tone_measurement_from_multisine": {
                "units": "dB",
                "CONT": {"warning_above": 0.5, "exclude_candidate_above": 1.0},
                "REPOS": {"warning_above": 1.0, "exclude_candidate_above": 2.0},
                "REASM": {"warning_above": 2.0, "exclude_candidate_above": 4.0},
            },
        },
    },
    "aggregation": {
        "required_unavailable_policy": "warning",
        "canonical_allowed_statuses": ["valid", "warning"],
        "canonical_block_on_required_unavailable": True,
        "canonical_block_on_manual_review": True,
    },
}

_COMPARISON_METRICS_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "provisional": True,
    "frequency_bands": [
        {
            "band_id": "band_1k_2k",
            "f_min_hz": 1000.0,
            "f_max_hz": 2000.0,
            "boundary": "left_closed_right_open",
            "minimum_feature_count": 5,
        },
        {
            "band_id": "band_2k_4k",
            "f_min_hz": 2000.0,
            "f_max_hz": 4000.0,
            "boundary": "left_closed_right_open",
            "minimum_feature_count": 5,
        },
        {
            "band_id": "band_4k_8k",
            "f_min_hz": 4000.0,
            "f_max_hz": 8000.0,
            "boundary": "closed",
            "minimum_feature_count": 5,
        },
        {
            "band_id": "full_1k_8k",
            "f_min_hz": 1000.0,
            "f_max_hz": 8000.0,
            "boundary": "closed",
            "minimum_feature_count": 5,
        },
    ],
    "configuration_comparison": {
        "baseline_configuration": "U4SYM",
        "candidate_configuration": "U4ENC",
        "ratio_minimum_denominator": 1.0e-12,
    },
    "cross_mode": {
        "minimum_common_tones": 5,
        "allow_centered_shape_comparison": True,
        "bias_sign": "multisine_minus_sweep",
    },
    "reliability": {
        "source_feature_kind": "tone_measurement_from_multisine",
        "repeat_type": "REPOS",
        "allowed_scope_roles": ["development", "training"],
        "floor_db": 0.1,
        "maximum_raw_weight": 100.0,
        "minimum_pairs_per_tone": 1,
        "minimum_available_tones": 5,
        "normalization": "mean_one",
    },
}

_CLASSIFICATION_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "provisional": True,
    "frequency_bands": deepcopy(_COMPARISON_METRICS_DEFAULTS["frequency_bands"]),
    "protocols": [
        "leave_one_session_out",
        "leave_one_reposition_round_out",
        "leave_one_assembly_out",
    ],
    "models": [
        "nearest_template_correlation",
        "nearest_centroid",
        "logistic_regression",
    ],
    "minimum_training_features": 5,
    "minimum_training_samples_per_direction": 1,
    "minimum_prediction_coverage": 1.0,
    "standardization": "training_fold_only",
    "pca": "disabled",
    "final_test_policy": "sealed",
    "cross_mode": {
        "transfer_protocols": [
            "sweep_to_sweep",
            "multisine_to_multisine",
            "sweep_to_multisine",
            "sweep_plus_multisine_to_multisine",
        ],
        "allowed_shape_normalizations": ["subtract_mean_db", "zscore_spectrum"],
        "pooling_policy": "sample_pooled",
        "sample_weighting": "uniform",
        "class_weighting": "balanced",
        "p4b_bias_policy": "audit_only",
        "calibration_policy": "disabled",
    },
}

_HR_CALIBRATION_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "enabled": False,
    "provisional": True,
    "input_feature_kind": "dense_raw_spl",
    "normalization": "none",
    "peak_algorithm": "scipy_topographic_prominence",
    "peak_selection_rule": "prominence_then_magnitude_then_lowest_frequency",
    "search_band_overlap_policy": "reject",
    "drift": {"minimum_valid_peaks": 2, "reference": "median_peak_frequency"},
    "energy_fraction": {"missing_resonator_policy": "require_all", "sum_tolerance": 1.0e-12},
    "resonators": [],
}

_HR_READOUT_DEFAULTS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "enabled": False,
    "provisional": True,
    "input_feature_kind": "tone_measurement_from_multisine",
    "input_representation": "sparse_tones",
    "normalization": "none",
    "phase_policy": "magnitude_only",
    "tone_mapping": {
        "method": "nearest_tone",
        "allow_shared_tones": False,
        "maximum_detuning_hz": 25.0,
    },
    "coverage": {
        "minimum_valid_tones": 1,
        "minimum_coverage_fraction": 1.0,
        "maximum_tone_gap_hz": 100.0,
        "endpoint_tolerance_hz": 25.0,
        "missing_tone_policy": "unavailable",
    },
    "energy": {
        "method": "nearest_tone_power",
        "conversion": "ten_power_db_over_10",
    },
    "energy_fraction": {
        "emit_feature_set": True,
        "missing_resonator_policy": "require_all",
        "sum_tolerance": 1.0e-12,
    },
    "uncertainty": {"method": "unavailable"},
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
    legacy_classification = provided.get("classification")
    if isinstance(legacy_classification, Mapping) and "validation" in legacy_classification:
        if set(legacy_classification) != {"validation", "models"}:
            raise ConfigError("legacy classification may contain only validation and models")
        provided["classification"] = {
            "protocols": list(legacy_classification["validation"]),
            "models": list(legacy_classification["models"]),
        }
        migration_warnings.append(
            "Legacy classification.validation was migrated in memory to "
            "classification.protocols; no source YAML was modified."
        )
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
    supplied_tone_selection = resolved.get("tone_selection", {})
    if not isinstance(supplied_tone_selection, Mapping):
        raise ConfigError("tone_selection must be a mapping")
    resolved["tone_selection"] = deep_merge(
        _TONE_SELECTION_DEFAULTS,
        supplied_tone_selection,
    )
    supplied_projection_ablation = resolved.get("tone_projection_ablation", {})
    if not isinstance(supplied_projection_ablation, Mapping):
        raise ConfigError("tone_projection_ablation must be a mapping")
    resolved["tone_projection_ablation"] = deep_merge(
        _TONE_PROJECTION_ABLATION_DEFAULTS,
        supplied_projection_ablation,
    )
    supplied_bridge = resolved.get("cross_mode_bridge", {})
    if not isinstance(supplied_bridge, Mapping):
        raise ConfigError("cross_mode_bridge must be a mapping")
    resolved["cross_mode_bridge"] = deep_merge(
        _CROSS_MODE_BRIDGE_DEFAULTS,
        supplied_bridge,
    )
    supplied_offline_readout = resolved.get("offline_fast_readout", {})
    if not isinstance(supplied_offline_readout, Mapping):
        raise ConfigError("offline_fast_readout must be a mapping")
    resolved["offline_fast_readout"] = deep_merge(
        _OFFLINE_FAST_READOUT_DEFAULTS, supplied_offline_readout,
    )
    supplied_direction_metrics = resolved.get("direction_metrics", {})
    if not isinstance(supplied_direction_metrics, Mapping):
        raise ConfigError("direction_metrics must be a mapping")
    resolved["direction_metrics"] = deep_merge(
        _DIRECTION_METRICS_DEFAULTS,
        supplied_direction_metrics,
    )
    supplied_dataset_quality = resolved.get("dataset_quality_control", {})
    if not isinstance(supplied_dataset_quality, Mapping):
        raise ConfigError("dataset_quality_control must be a mapping")
    resolved["dataset_quality_control"] = deep_merge(
        _DATASET_QUALITY_DEFAULTS,
        supplied_dataset_quality,
    )
    supplied_comparison_metrics = resolved.get("comparison_metrics", {})
    if not isinstance(supplied_comparison_metrics, Mapping):
        raise ConfigError("comparison_metrics must be a mapping")
    resolved["comparison_metrics"] = deep_merge(
        _COMPARISON_METRICS_DEFAULTS,
        supplied_comparison_metrics,
    )
    supplied_classification = resolved.get("classification", {})
    if not isinstance(supplied_classification, Mapping):
        raise ConfigError("classification must be a mapping")
    resolved["classification"] = deep_merge(
        _CLASSIFICATION_DEFAULTS,
        supplied_classification,
    )
    supplied_hr = resolved.get("hr_calibration", {})
    if not isinstance(supplied_hr, Mapping):
        raise ConfigError("hr_calibration must be a mapping")
    resolved["hr_calibration"] = deep_merge(_HR_CALIBRATION_DEFAULTS, supplied_hr)
    supplied_readout = resolved.get("hr_readout", {})
    if not isinstance(supplied_readout, Mapping):
        raise ConfigError("hr_readout must be a mapping")
    resolved["hr_readout"] = deep_merge(_HR_READOUT_DEFAULTS, supplied_readout)
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
        ("2.9.0", "2.4.0", "2.2.0"),
        ("2.10.0", "2.4.0", "2.2.0"),
        ("2.11.0", "2.4.0", "2.2.0"),
        ("2.12.0", "2.4.0", "2.2.0"),
        ("2.13.0", "2.4.0", "2.2.0"),
        ("2.14.0", "2.4.0", "2.2.0"),
        ("2.15.0", "2.4.0", "2.2.0"),
        ("2.16.0", "2.4.0", "2.3.0"),
        ("2.17.0", "2.4.0", "2.3.0"),
        ("2.18.0", "2.4.0", "2.3.0"),
        ("2.19.0", "2.4.0", "2.3.0"),
    }:
        old_config_version = str(versions["config"])
        smoothing = resolved["preprocessing"].get("smoothing", {"method": "none"})
        if old_config_version not in {"2.8.0", "2.9.0"} and (
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
        if old_config_version == "2.16.0":
            migration_warnings.append(
                "DEV-C11 config was migrated with tone_selection.enabled=false; "
                "P9-A is never enabled silently and the source YAML was not modified."
            )
        if old_config_version == "2.17.0":
            migration_warnings.append(
                "The legacy config was migrated with tone_projection_ablation.enabled=false; "
                "P9-B is never enabled silently and the source YAML was not modified."
            )
        if old_config_version == "2.18.0":
            migration_warnings.append(
                "The legacy config was migrated with cross_mode_bridge.enabled=false; "
                "P9-C is never enabled silently and the source YAML was not modified."
            )
        if old_config_version == "2.19.0":
            migration_warnings.append(
                "The legacy config was migrated with offline_fast_readout.enabled=false; "
                "P9-D is never enabled silently and the source YAML was not modified."
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
    validate_tone_selection_config(config.get("tone_selection"))
    validate_tone_projection_ablation_config(config.get("tone_projection_ablation"))
    validate_cross_mode_bridge_config(config.get("cross_mode_bridge"))
    validate_offline_fast_readout_config(config.get("offline_fast_readout"))
    tone_selection = config.get("tone_selection")
    projection_ablation = config.get("tone_projection_ablation")
    assert isinstance(tone_selection, Mapping) and isinstance(projection_ablation, Mapping)
    if projection_ablation["enabled"] is True and max(projection_ablation["subset_sizes"]) > int(tone_selection["selection"]["target_count"]):
        raise ConfigError("tone_projection_ablation subset size exceeds P9-A target_count")
    validate_direction_metrics_config(config.get("direction_metrics"))
    validate_dataset_quality_control_config(config.get("dataset_quality_control"))
    validate_comparison_metrics_config(config.get("comparison_metrics"))
    validate_classification_config(config.get("classification"))
    validate_hr_calibration_config(config.get("hr_calibration"))
    validate_hr_readout_config(config.get("hr_readout"))
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


def validate_direction_metrics_config(value: Any) -> None:
    """Validate the complete provisional P4-A metrics contract."""
    required = {
        "schema_version",
        "provisional",
        "minimum_common_valid_features",
        "minimum_common_valid_fraction",
        "minimum_direction_count",
        "center_direction_matrix",
        "repeatability_distance_metric",
        "morphology_gain",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ConfigError(
            "direction_metrics must contain exactly: " + ", ".join(sorted(required))
        )
    if value.get("schema_version") != "1.0.0":
        raise ConfigError("direction_metrics.schema_version must be 1.0.0")
    if not isinstance(value.get("provisional"), bool):
        raise ConfigError("direction_metrics.provisional must be boolean")
    minimum_features = value.get("minimum_common_valid_features")
    if (
        isinstance(minimum_features, bool)
        or not isinstance(minimum_features, int)
        or minimum_features < 1
    ):
        raise ConfigError("direction_metrics.minimum_common_valid_features must be >= 1")
    minimum_fraction = _finite_number(
        value,
        "minimum_common_valid_fraction",
        "direction_metrics minimum_common_valid_fraction",
    )
    if not 0.0 < minimum_fraction <= 1.0:
        raise ConfigError(
            "direction_metrics.minimum_common_valid_fraction must lie in (0, 1]"
        )
    minimum_directions = value.get("minimum_direction_count")
    if (
        isinstance(minimum_directions, bool)
        or not isinstance(minimum_directions, int)
        or minimum_directions < 1
    ):
        raise ConfigError("direction_metrics.minimum_direction_count must be >= 1")
    if not isinstance(value.get("center_direction_matrix"), bool):
        raise ConfigError("direction_metrics.center_direction_matrix must be boolean")
    distance_metrics = {"euclidean", "rms", "median_absolute_difference"}
    if value.get("repeatability_distance_metric") not in distance_metrics:
        raise ConfigError(
            "direction_metrics.repeatability_distance_metric is unsupported"
        )
    gain = value.get("morphology_gain")
    if not isinstance(gain, Mapping) or set(gain) != {
        "distance_metric",
        "minimum_denominator",
    }:
        raise ConfigError(
            "direction_metrics.morphology_gain requires distance_metric and "
            "minimum_denominator"
        )
    if gain.get("distance_metric") not in distance_metrics:
        raise ConfigError("direction_metrics.morphology_gain.distance_metric is unsupported")
    denominator = _finite_number(
        gain,
        "minimum_denominator",
        "direction_metrics morphology_gain minimum_denominator",
    )
    if denominator <= 0.0:
        raise ConfigError(
            "direction_metrics.morphology_gain.minimum_denominator must be positive"
        )


def validate_comparison_metrics_config(value: Any) -> None:
    """Validate the complete provisional P4-B comparison contract."""
    required = {
        "schema_version",
        "provisional",
        "frequency_bands",
        "configuration_comparison",
        "cross_mode",
        "reliability",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ConfigError(
            "comparison_metrics must contain exactly: " + ", ".join(sorted(required))
        )
    if value.get("schema_version") != "1.0.0":
        raise ConfigError("comparison_metrics.schema_version must be 1.0.0")
    if not isinstance(value.get("provisional"), bool):
        raise ConfigError("comparison_metrics.provisional must be boolean")
    bands = value.get("frequency_bands")
    if not isinstance(bands, list) or not bands:
        raise ConfigError("comparison_metrics.frequency_bands must be non-empty")
    band_ids: list[str] = []
    for band in bands:
        if not isinstance(band, Mapping) or set(band) != {
            "band_id", "f_min_hz", "f_max_hz", "boundary", "minimum_feature_count"
        }:
            raise ConfigError("comparison frequency band fields are incomplete")
        band_id = str(band.get("band_id", "")).strip()
        if not band_id:
            raise ConfigError("comparison frequency band_id is required")
        band_ids.append(band_id)
        low = _finite_number(band, "f_min_hz", "comparison frequency band f_min_hz")
        high = _finite_number(band, "f_max_hz", "comparison frequency band f_max_hz")
        if low < 0.0 or low >= high:
            raise ConfigError("comparison frequency band bounds must be increasing")
        if band.get("boundary") not in {
            "closed", "left_closed_right_open", "left_open_right_closed", "open"
        }:
            raise ConfigError("comparison frequency band boundary is unsupported")
        count = band.get("minimum_feature_count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ConfigError("comparison frequency band minimum_feature_count must be >= 1")
    if len(set(band_ids)) != len(band_ids):
        raise ConfigError("comparison frequency band_id values must be unique")

    configuration = value.get("configuration_comparison")
    if not isinstance(configuration, Mapping) or set(configuration) != {
        "baseline_configuration", "candidate_configuration", "ratio_minimum_denominator"
    }:
        raise ConfigError("comparison configuration_comparison fields are incomplete")
    baseline = str(configuration.get("baseline_configuration", "")).strip()
    candidate = str(configuration.get("candidate_configuration", "")).strip()
    if not baseline or not candidate or baseline == candidate:
        raise ConfigError("comparison candidate and baseline configurations must differ")
    if _finite_number(
        configuration,
        "ratio_minimum_denominator",
        "comparison ratio minimum denominator",
    ) <= 0.0:
        raise ConfigError("comparison ratio minimum denominator must be positive")

    cross_mode = value.get("cross_mode")
    if not isinstance(cross_mode, Mapping) or set(cross_mode) != {
        "minimum_common_tones", "allow_centered_shape_comparison", "bias_sign"
    }:
        raise ConfigError("comparison cross_mode fields are incomplete")
    common_tones = cross_mode.get("minimum_common_tones")
    if isinstance(common_tones, bool) or not isinstance(common_tones, int) or common_tones < 1:
        raise ConfigError("comparison cross_mode minimum_common_valid_tones must be >= 1")
    if not isinstance(cross_mode.get("allow_centered_shape_comparison"), bool):
        raise ConfigError("comparison allow_centered_shape_comparison must be boolean")
    if cross_mode.get("bias_sign") != "multisine_minus_sweep":
        raise ConfigError("comparison cross_mode bias_sign must be multisine_minus_sweep")

    reliability = value.get("reliability")
    expected_reliability = {
        "source_feature_kind", "repeat_type", "allowed_scope_roles", "floor_db",
        "maximum_raw_weight", "minimum_pairs_per_tone", "minimum_available_tones",
        "normalization",
    }
    if not isinstance(reliability, Mapping) or set(reliability) != expected_reliability:
        raise ConfigError("comparison reliability fields are incomplete")
    if reliability.get("source_feature_kind") != "tone_measurement_from_multisine":
        raise ConfigError("comparison reliability source_feature_kind is unsupported")
    if reliability.get("repeat_type") != "REPOS":
        raise ConfigError("comparison reliability repeat_type must be REPOS")
    roles = reliability.get("allowed_scope_roles")
    if roles != ["development", "training"]:
        if isinstance(roles, list) and "final_test" in roles:
            raise ConfigError("final_test cannot be used for comparison reliability")
        raise ConfigError("comparison reliability allowed_scope_roles must be development/training")
    if _finite_number(reliability, "floor_db", "comparison reliability variance_floor") <= 0.0:
        raise ConfigError("comparison reliability variance_floor must be positive")
    if _finite_number(
        reliability, "maximum_raw_weight", "comparison reliability maximum_raw_weight"
    ) <= 0.0:
        raise ConfigError("comparison reliability maximum_raw_weight must be positive")
    for field in ("minimum_pairs_per_tone", "minimum_available_tones"):
        count = reliability.get(field)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ConfigError(f"comparison reliability {field} must be >= 1")
    if reliability.get("normalization") != "mean_one":
        raise ConfigError("comparison reliability normalization must be mean_one")


def validate_classification_config(value: Any) -> None:
    """Validate the fixed, provisional P5-A/P5-B leakage-control contract."""
    required = {
        "schema_version", "provisional", "frequency_bands", "protocols", "models",
        "minimum_training_features", "minimum_training_samples_per_direction",
        "minimum_prediction_coverage", "standardization",
        "pca", "final_test_policy",
        "cross_mode",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ConfigError("classification fields are incomplete or ambiguous")
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("provisional"), bool):
        raise ConfigError("classification requires schema_version 1.0.0 and boolean provisional")
    # Reuse the already-audited P4-B band validator by supplying inert legal sections.
    validation_shell = deepcopy(_COMPARISON_METRICS_DEFAULTS)
    validation_shell["frequency_bands"] = value.get("frequency_bands")
    validate_comparison_metrics_config(validation_shell)
    allowed_protocols = {
        "leave_one_session_out", "leave_one_reposition_round_out", "leave_one_assembly_out"
    }
    allowed_models = {
        "nearest_template_correlation", "nearest_centroid", "logistic_regression"
    }
    protocols = value.get("protocols")
    models = value.get("models")
    if not isinstance(protocols, list) or not protocols or len(set(protocols)) != len(protocols) or set(protocols) - allowed_protocols:
        raise ConfigError("classification protocols are invalid")
    if not isinstance(models, list) or not models or len(set(models)) != len(models) or set(models) - allowed_models:
        raise ConfigError("classification models are invalid")
    count = value.get("minimum_training_features")
    if isinstance(count, bool) or not isinstance(count, int) or count < 2:
        raise ConfigError("classification minimum_training_features must be an integer >= 2")
    per_direction = value.get("minimum_training_samples_per_direction")
    if isinstance(per_direction, bool) or not isinstance(per_direction, int) or per_direction < 1:
        raise ConfigError("classification minimum_training_samples_per_direction must be an integer >= 1")
    coverage = _finite_number(value, "minimum_prediction_coverage", "classification minimum_prediction_coverage")
    if not 0.0 < coverage <= 1.0:
        raise ConfigError("classification minimum_prediction_coverage must be in (0, 1]")
    if value.get("standardization") != "training_fold_only":
        raise ConfigError("classification standardization must be training_fold_only")
    if value.get("pca") != "disabled":
        raise ConfigError("classification PCA must remain disabled in P5-A")
    if value.get("final_test_policy") != "sealed":
        raise ConfigError("classification final_test_policy must be sealed")
    cross_mode = value.get("cross_mode")
    expected_cross_fields = {
        "transfer_protocols", "allowed_shape_normalizations", "pooling_policy",
        "sample_weighting", "class_weighting", "p4b_bias_policy",
        "calibration_policy",
    }
    if not isinstance(cross_mode, Mapping) or set(cross_mode) != expected_cross_fields:
        raise ConfigError("classification.cross_mode fields are incomplete or ambiguous")
    expected_transfer = {
        "sweep_to_sweep", "multisine_to_multisine", "sweep_to_multisine",
        "sweep_plus_multisine_to_multisine",
    }
    transfer = cross_mode.get("transfer_protocols")
    if not isinstance(transfer, list) or len(transfer) != 4 or set(transfer) != expected_transfer:
        raise ConfigError("classification cross-mode requires all four transfer protocols")
    shape = cross_mode.get("allowed_shape_normalizations")
    if shape != ["subtract_mean_db", "zscore_spectrum"]:
        raise ConfigError("classification cross-mode shape normalizations are fixed")
    if cross_mode.get("pooling_policy") != "sample_pooled":
        raise ConfigError("classification cross-mode pooling_policy must be sample_pooled")
    if cross_mode.get("sample_weighting") != "uniform":
        raise ConfigError("classification cross-mode sample_weighting must be uniform")
    if cross_mode.get("class_weighting") != "balanced":
        raise ConfigError("classification cross-mode class_weighting must be balanced")
    if cross_mode.get("p4b_bias_policy") != "audit_only":
        raise ConfigError("classification P4-B bias must remain audit_only")
    if cross_mode.get("calibration_policy") != "disabled":
        raise ConfigError("classification cross-mode calibration must remain disabled")


def validate_hr_calibration_config(value: Any) -> None:
    """Validate the complete provisional P6-A sweep calibration contract."""
    if not isinstance(value, Mapping):
        raise ConfigError("hr_calibration must be a mapping")
    required = {
        "schema_version", "enabled", "provisional", "input_feature_kind",
        "normalization", "peak_algorithm", "peak_selection_rule",
        "search_band_overlap_policy", "drift", "energy_fraction", "resonators",
    }
    if set(value) != required:
        raise ConfigError("hr_calibration fields are incomplete or ambiguous")
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("enabled"), bool) or not isinstance(value.get("provisional"), bool):
        raise ConfigError("hr_calibration requires schema 1.0.0 and boolean enabled/provisional")
    if value.get("input_feature_kind") != "dense_raw_spl" or value.get("normalization") != "none":
        raise ConfigError("hr_calibration accepts only unnormalized dense_raw_spl")
    if value.get("peak_algorithm") != "scipy_topographic_prominence":
        raise ConfigError("unsupported HR peak algorithm")
    if value.get("peak_selection_rule") != "prominence_then_magnitude_then_lowest_frequency":
        raise ConfigError("unsupported HR peak selection rule")
    if value.get("search_band_overlap_policy") != "reject":
        raise ConfigError("HR search band overlap policy must be reject")
    drift = value.get("drift")
    if not isinstance(drift, Mapping) or set(drift) != {"minimum_valid_peaks", "reference"}:
        raise ConfigError("hr_calibration.drift fields are incomplete")
    minimum_peaks = drift.get("minimum_valid_peaks")
    if isinstance(minimum_peaks, bool) or not isinstance(minimum_peaks, int) or minimum_peaks < 2:
        raise ConfigError("HR drift minimum_valid_peaks must be an integer >= 2")
    if drift.get("reference") != "median_peak_frequency":
        raise ConfigError("HR drift reference must be median_peak_frequency")
    fraction = value.get("energy_fraction")
    if not isinstance(fraction, Mapping) or set(fraction) != {"missing_resonator_policy", "sum_tolerance"}:
        raise ConfigError("hr_calibration.energy_fraction fields are incomplete")
    if fraction.get("missing_resonator_policy") not in {"require_all", "allow_partial"}:
        raise ConfigError("unsupported HR missing resonator policy")
    if _finite_number(fraction, "sum_tolerance", "HR energy fraction tolerance") <= 0.0:
        raise ConfigError("HR energy fraction tolerance must be positive")
    resonators = value.get("resonators")
    if not isinstance(resonators, list):
        raise ConfigError("hr_calibration.resonators must be a list")
    if value["enabled"] and not resonators:
        raise ConfigError("enabled hr_calibration requires resonators")
    ids: list[str] = []
    bands: list[tuple[float, float, str]] = []
    required_resonator = {
        "module_id", "resonator_id", "design_target_hz", "search_min_hz",
        "search_max_hz", "boundary", "minimum_prominence_db",
        "minimum_peak_distance_hz", "minimum_valid_points", "peak_selection_rule",
        "bandwidth_drop_db", "integration",
    }
    for item in resonators:
        if not isinstance(item, Mapping) or set(item) != required_resonator:
            raise ConfigError("HR resonator fields are incomplete or ambiguous")
        resonator_id = str(item.get("resonator_id", ""))
        if not resonator_id or not str(item.get("module_id", "")):
            raise ConfigError("HR module/resonator IDs are required")
        ids.append(resonator_id)
        low = _finite_number(item, "search_min_hz", "HR search minimum")
        high = _finite_number(item, "search_max_hz", "HR search maximum")
        if low < 0.0 or low >= high:
            raise ConfigError("HR search bounds must be increasing")
        boundary = str(item.get("boundary"))
        if boundary not in {"closed", "open", "left_closed_right_open", "left_open_right_closed"}:
            raise ConfigError("unsupported HR search boundary")
        bands.append((low, high, resonator_id))
        target = item.get("design_target_hz")
        if target is not None and (isinstance(target, bool) or not np.isfinite(float(target)) or float(target) <= 0.0):
            raise ConfigError("HR design target must be null or positive finite")
        if _finite_number(item, "minimum_prominence_db", "HR minimum prominence") < 0.0:
            raise ConfigError("HR minimum prominence cannot be negative")
        for key in ("minimum_peak_distance_hz", "bandwidth_drop_db"):
            if _finite_number(item, key, f"HR {key}") <= 0.0:
                raise ConfigError(f"HR {key} must be positive")
        minimum_points = item.get("minimum_valid_points")
        if isinstance(minimum_points, bool) or not isinstance(minimum_points, int) or minimum_points < 3:
            raise ConfigError("HR minimum_valid_points must be an integer >= 3")
        if item.get("peak_selection_rule") != value.get("peak_selection_rule"):
            raise ConfigError("HR resonator selection rule must match global rule")
        integration = item.get("integration")
        if not isinstance(integration, Mapping):
            raise ConfigError("HR integration configuration is required")
        method = integration.get("method")
        expected_fields = {"method", "minimum_coverage_fraction"}
        if method == "fixed_half_width_around_measured_peak":
            expected_fields.add("half_width_hz")
        if set(integration) != expected_fields or method not in {"measured_3db_band", "fixed_half_width_around_measured_peak"}:
            raise ConfigError("HR integration fields are ambiguous")
        coverage = _finite_number(integration, "minimum_coverage_fraction", "HR integration coverage")
        if not 0.0 < coverage <= 1.0:
            raise ConfigError("HR integration coverage must lie in (0, 1]")
        if method == "fixed_half_width_around_measured_peak" and _finite_number(integration, "half_width_hz", "HR integration half width") <= 0.0:
            raise ConfigError("HR integration half width must be positive")
    if len(ids) != len(set(ids)):
        raise ConfigError("HR resonator IDs must be unique")
    ordered = sorted(bands)
    for left, right in zip(ordered, ordered[1:]):
        if right[0] < left[1]:
            raise ConfigError(f"HR search bands overlap: {left[2]}, {right[2]}")


def validate_hr_readout_config(value: Any) -> None:
    """Validate the complete offline P6-B readout contract."""
    required = {
        "schema_version", "enabled", "provisional", "input_feature_kind",
        "input_representation", "normalization", "phase_policy", "tone_mapping",
        "coverage", "energy", "energy_fraction", "uncertainty",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ConfigError("hr_readout fields are incomplete or ambiguous")
    if value.get("schema_version") != "1.0.0" or not isinstance(value.get("enabled"), bool) or not isinstance(value.get("provisional"), bool):
        raise ConfigError("hr_readout requires schema 1.0.0 and boolean enabled/provisional")
    if value.get("input_feature_kind") != "tone_measurement_from_multisine" or value.get("input_representation") != "sparse_tones" or value.get("normalization") != "none":
        raise ConfigError("hr_readout accepts only unnormalized sparse multisine tone FeatureSet")
    if value.get("phase_policy") != "magnitude_only":
        raise ConfigError("hr_readout phase policy must be magnitude_only")
    mapping = value.get("tone_mapping")
    if not isinstance(mapping, Mapping) or set(mapping) != {"method", "allow_shared_tones", "maximum_detuning_hz"}:
        raise ConfigError("hr_readout tone mapping fields are incomplete")
    if mapping.get("method") not in {"nearest_tone", "calibrated_window"} or not isinstance(mapping.get("allow_shared_tones"), bool):
        raise ConfigError("unsupported HR readout tone mapping")
    if _finite_number(mapping, "maximum_detuning_hz", "HR readout detuning") <= 0.0:
        raise ConfigError("HR readout detuning must be positive")
    energy = value.get("energy")
    if not isinstance(energy, Mapping) or set(energy) != {"method", "conversion"} or energy.get("conversion") != "ten_power_db_over_10":
        raise ConfigError("hr_readout energy fields are incomplete")
    expected_energy = {
        "nearest_tone": "nearest_tone_power",
        "calibrated_window": "narrowband_trapezoid",
    }[str(mapping["method"])]
    if energy.get("method") != expected_energy:
        raise ConfigError("HR readout mapping and energy methods are incompatible")
    coverage = value.get("coverage")
    coverage_fields = {
        "minimum_valid_tones", "minimum_coverage_fraction", "maximum_tone_gap_hz",
        "endpoint_tolerance_hz", "missing_tone_policy",
    }
    if not isinstance(coverage, Mapping) or set(coverage) != coverage_fields:
        raise ConfigError("hr_readout coverage fields are incomplete")
    minimum_tones = coverage.get("minimum_valid_tones")
    minimum_required = 1 if mapping["method"] == "nearest_tone" else 2
    if isinstance(minimum_tones, bool) or not isinstance(minimum_tones, int) or minimum_tones < minimum_required:
        raise ConfigError(f"HR readout minimum_valid_tones must be >= {minimum_required}")
    coverage_fraction = _finite_number(coverage, "minimum_coverage_fraction", "HR readout coverage")
    if not 0.0 < coverage_fraction <= 1.0:
        raise ConfigError("HR readout coverage fraction must lie in (0, 1]")
    if _finite_number(coverage, "maximum_tone_gap_hz", "HR readout tone gap") <= 0.0:
        raise ConfigError("HR readout maximum tone gap must be positive")
    if _finite_number(coverage, "endpoint_tolerance_hz", "HR readout endpoint tolerance") < 0.0:
        raise ConfigError("HR readout endpoint tolerance cannot be negative")
    if coverage.get("missing_tone_policy") not in {"warning", "unavailable"}:
        raise ConfigError("unsupported HR readout missing-tone policy")
    fraction = value.get("energy_fraction")
    if not isinstance(fraction, Mapping) or set(fraction) != {"emit_feature_set", "missing_resonator_policy", "sum_tolerance"} or not isinstance(fraction.get("emit_feature_set"), bool):
        raise ConfigError("hr_readout energy_fraction fields are incomplete")
    if fraction.get("missing_resonator_policy") not in {"require_all", "allow_partial"}:
        raise ConfigError("unsupported HR readout missing resonator policy")
    if _finite_number(fraction, "sum_tolerance", "HR readout q_i tolerance") <= 0.0:
        raise ConfigError("HR readout q_i tolerance must be positive")
    uncertainty = value.get("uncertainty")
    if not isinstance(uncertainty, Mapping) or set(uncertainty) != {"method"} or uncertainty.get("method") != "unavailable":
        raise ConfigError("P6-B uncertainty must remain unavailable")


def validate_dataset_quality_control_config(value: Any) -> None:
    """Validate the complete provisional P2-B dataset quality contract."""
    required_top = {
        "schema_version",
        "provisional",
        "condition_completeness",
        "same_condition_outliers",
        "repeatability",
        "aggregation",
    }
    if not isinstance(value, Mapping) or set(value) != required_top:
        raise ConfigError(
            "dataset_quality_control must contain exactly: "
            + ", ".join(sorted(required_top))
        )
    if value.get("schema_version") != "1.0.0":
        raise ConfigError("dataset_quality_control.schema_version must be 1.0.0")
    if not isinstance(value.get("provisional"), bool):
        raise ConfigError("dataset_quality_control.provisional must be boolean")

    completeness = value.get("condition_completeness")
    expected_completeness = {
        "direction_match_tolerance_deg",
        "missing_status",
        "duplicate_status",
        "unexpected_status",
    }
    if not isinstance(completeness, Mapping) or set(completeness) != expected_completeness:
        raise ConfigError("dataset condition_completeness fields are incomplete")
    tolerance = _finite_number(
        completeness,
        "direction_match_tolerance_deg",
        "dataset condition direction tolerance",
    )
    if tolerance < 0.0:
        raise ConfigError("dataset condition direction tolerance must be >= 0")
    allowed_issue_statuses = {"warning", "exclude_candidate"}
    for name in ("missing_status", "duplicate_status", "unexpected_status"):
        if completeness.get(name) not in allowed_issue_statuses:
            raise ConfigError(f"dataset condition {name} must be warning or exclude_candidate")

    outliers = value.get("same_condition_outliers")
    expected_outliers = {
        "method",
        "center",
        "distance",
        "scale",
        "mad_scale_factor",
        "minimum_reference_samples",
        "minimum_common_valid_features",
        "minimum_common_valid_fraction",
        "minimum_scale",
        "warning_robust_z",
        "exclude_candidate_robust_z",
        "incompatible_contract_status",
        "reference_role_by_evaluation_role",
    }
    if not isinstance(outliers, Mapping) or set(outliers) != expected_outliers:
        raise ConfigError("dataset same_condition_outliers fields are incomplete")
    expected_methods = {
        "method": "coordinate_median_mad_rms",
        "center": "coordinate_median",
        "distance": "rms",
        "scale": "median_absolute_deviation",
    }
    for name, expected in expected_methods.items():
        if outliers.get(name) != expected:
            raise ConfigError(f"dataset outlier {name} must be {expected}")
    for name in ("minimum_reference_samples", "minimum_common_valid_features"):
        count = outliers.get(name)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ConfigError(f"dataset outlier {name} must be an integer >= 1")
    fraction = _finite_number(
        outliers,
        "minimum_common_valid_fraction",
        "dataset outlier minimum_common_valid_fraction",
    )
    if not 0.0 < fraction <= 1.0:
        raise ConfigError("dataset outlier minimum_common_valid_fraction must be in (0, 1]")
    for name in ("mad_scale_factor", "minimum_scale"):
        if _finite_number(outliers, name, f"dataset outlier {name}") <= 0.0:
            raise ConfigError(f"dataset outlier {name} must be positive")
    warning = _finite_number(outliers, "warning_robust_z", "dataset outlier warning")
    exclude = _finite_number(
        outliers,
        "exclude_candidate_robust_z",
        "dataset outlier exclude_candidate",
    )
    if not warning < exclude:
        raise ConfigError("dataset outlier warning/exclude thresholds are not ordered")
    if outliers.get("incompatible_contract_status") not in allowed_issue_statuses:
        raise ConfigError("dataset outlier incompatible_contract_status is invalid")
    role_mapping = outliers.get("reference_role_by_evaluation_role")
    roles = {"development", "training", "final_test"}
    if not isinstance(role_mapping, Mapping) or set(role_mapping) != roles:
        raise ConfigError("dataset outlier reference-role mapping is incomplete")
    if any(role not in roles for role in role_mapping.values()):
        raise ConfigError("dataset outlier reference role is unsupported")
    if "final_test" in role_mapping.values():
        raise ConfigError("final_test cannot be an outlier reference role")

    repeatability = value.get("repeatability")
    expected_repeatability = {
        "distance",
        "minimum_common_valid_features",
        "minimum_common_valid_fraction",
        "minimum_qualified_pairs",
        "thresholds_by_feature_kind",
    }
    if not isinstance(repeatability, Mapping) or set(repeatability) != expected_repeatability:
        raise ConfigError("dataset repeatability fields are incomplete")
    if repeatability.get("distance") != "rms":
        raise ConfigError("dataset repeatability distance must be rms")
    for name in ("minimum_common_valid_features", "minimum_qualified_pairs"):
        count = repeatability.get(name)
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ConfigError(f"dataset repeatability {name} must be an integer >= 1")
    repeat_fraction = _finite_number(
        repeatability,
        "minimum_common_valid_fraction",
        "dataset repeatability minimum_common_valid_fraction",
    )
    if not 0.0 < repeat_fraction <= 1.0:
        raise ConfigError("dataset repeatability minimum_common_valid_fraction must be in (0, 1]")
    profiles = repeatability.get("thresholds_by_feature_kind")
    expected_feature_kinds = {
        "dense_raw_spl",
        "dense_demeaned_db",
        "dense_zscore",
        "tone_projection_from_sweep",
        "tone_measurement_from_multisine",
    }
    if not isinstance(profiles, Mapping) or set(profiles) != expected_feature_kinds:
        raise ConfigError("dataset repeatability feature-kind profiles are incomplete")
    for feature_kind, profile in profiles.items():
        if not isinstance(profile, Mapping) or set(profile) != {
            "units", "CONT", "REPOS", "REASM"
        }:
            raise ConfigError(f"dataset repeatability profile {feature_kind} is incomplete")
        if not str(profile.get("units", "")).strip():
            raise ConfigError(f"dataset repeatability profile {feature_kind} units are required")
        for repeat_type in ("CONT", "REPOS", "REASM"):
            thresholds = profile.get(repeat_type)
            if not isinstance(thresholds, Mapping) or set(thresholds) != {
                "warning_above", "exclude_candidate_above"
            }:
                raise ConfigError(
                    f"dataset repeatability {feature_kind}/{repeat_type} thresholds are incomplete"
                )
            repeat_warning = _finite_number(
                thresholds,
                "warning_above",
                f"dataset repeatability {feature_kind}/{repeat_type} warning",
            )
            repeat_exclude = _finite_number(
                thresholds,
                "exclude_candidate_above",
                f"dataset repeatability {feature_kind}/{repeat_type} exclude",
            )
            if not 0.0 <= repeat_warning < repeat_exclude:
                raise ConfigError(
                    f"dataset repeatability {feature_kind}/{repeat_type} thresholds are not ordered"
                )

    aggregation = value.get("aggregation")
    expected_aggregation = {
        "required_unavailable_policy",
        "canonical_allowed_statuses",
        "canonical_block_on_required_unavailable",
        "canonical_block_on_manual_review",
    }
    if not isinstance(aggregation, Mapping) or set(aggregation) != expected_aggregation:
        raise ConfigError("dataset QC aggregation fields are incomplete")
    if aggregation.get("required_unavailable_policy") not in {"preserve", "warning"}:
        raise ConfigError("dataset QC required_unavailable_policy is invalid")
    statuses = aggregation.get("canonical_allowed_statuses")
    if (
        not isinstance(statuses, list)
        or not statuses
        or len(set(statuses)) != len(statuses)
        or any(item not in {"valid", "warning", "exclude_candidate"} for item in statuses)
    ):
        raise ConfigError("dataset QC canonical_allowed_statuses is invalid")
    for name in (
        "canonical_block_on_required_unavailable",
        "canonical_block_on_manual_review",
    ):
        if not isinstance(aggregation.get(name), bool):
            raise ConfigError(f"dataset QC aggregation {name} must be boolean")


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


def validate_tone_projection_ablation_config(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ConfigError("tone_projection_ablation must be a mapping")
    required = {
        "schema_version", "enabled", "provisional", "input_feature_kind",
        "measurement_mode", "subset_sizes", "prefix_order", "outer_protocol",
        "inner_protocol", "minimum_inner_groups", "minimum_valid_inner_folds",
        "model", "minimum_training_features", "minimum_prediction_coverage",
        "p4_denominator_floor", "p4_retention_modes", "decision_policy",
        "final_test_policy", "cross_mode",
    }
    if set(value) != required:
        raise ConfigError("tone_projection_ablation fields are incomplete or ambiguous")
    if value["schema_version"] != "1.0.0" or not isinstance(value["enabled"], bool) or not isinstance(value["provisional"], bool):
        raise ConfigError("tone_projection_ablation requires schema 1.0.0 and boolean flags")
    if value["input_feature_kind"] != "tone_projection_from_sweep" or value["measurement_mode"] != "rew_sweep":
        raise ConfigError("tone_projection_ablation accepts sweep tone projection only")
    sizes = value["subset_sizes"]
    if not isinstance(sizes, list) or not sizes or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in sizes) or sizes != sorted(set(sizes)):
        raise ConfigError("tone_projection_ablation subset_sizes must be unique increasing positive integers")
    if value["prefix_order"] != "p9a_selection_rank":
        raise ConfigError("tone_projection_ablation prefix_order is fixed")
    if value["outer_protocol"] != "leave_one_session_out" or value["inner_protocol"] != "leave_one_session_out":
        raise ConfigError("tone_projection_ablation grouped protocols must be leave_one_session_out")
    for name in ("minimum_inner_groups", "minimum_valid_inner_folds", "minimum_training_features"):
        item = value[name]
        if isinstance(item, bool) or not isinstance(item, int) or item < 2:
            raise ConfigError(f"tone_projection_ablation {name} must be an integer >= 2")
    if value["model"] not in {"nearest_template_correlation", "nearest_centroid", "logistic_regression"}:
        raise ConfigError("tone_projection_ablation model is unsupported")
    for name in ("minimum_prediction_coverage", "p4_denominator_floor"):
        item = _finite_number(value, name, f"tone_projection_ablation {name}")
        if item <= 0.0 or (name == "minimum_prediction_coverage" and item > 1.0):
            raise ConfigError(f"tone_projection_ablation {name} is out of range")
    modes = value["p4_retention_modes"]
    expected_metrics = {
        "effective_rank", "morphology_gain", "mean_off_diagonal_pearson",
        "median_direction_rms", "repos_repeatability_median_rms",
        "repos_reliability_median_db", "repos_reliability_available_fraction",
    }
    if not isinstance(modes, Mapping) or set(modes) != expected_metrics or set(modes.values()) - {"higher_is_better", "lower_is_better", "absolute_fidelity"}:
        raise ConfigError("tone_projection_ablation P4 retention modes are invalid")
    policy = value["decision_policy"]
    if not isinstance(policy, Mapping) or set(policy) != {
        "minimum_p4_retention", "maximum_balanced_accuracy_drop",
        "maximum_macro_f1_drop", "minimum_prediction_coverage",
        "require_spacing_and_band_quotas",
    }:
        raise ConfigError("tone_projection_ablation decision policy is incomplete")
    for name in ("minimum_p4_retention", "minimum_prediction_coverage"):
        item = _finite_number(policy, name, f"tone_projection_ablation decision {name}")
        if not 0.0 <= item <= 1.0:
            raise ConfigError(f"tone_projection_ablation decision {name} is out of range")
    for name in ("maximum_balanced_accuracy_drop", "maximum_macro_f1_drop"):
        if _finite_number(policy, name, f"tone_projection_ablation decision {name}") < 0.0:
            raise ConfigError(f"tone_projection_ablation decision {name} must be non-negative")
    if not isinstance(policy["require_spacing_and_band_quotas"], bool):
        raise ConfigError("tone_projection_ablation policy gate must be boolean")
    if value["final_test_policy"] != "sealed" or value["cross_mode"] != "disabled":
        raise ConfigError("tone_projection_ablation final-test/cross-mode gates are fixed")


def validate_cross_mode_bridge_config(value: Any) -> None:
    """Validate the complete provisional P9-C policy without inferred defaults."""
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version", "enabled", "provisional", "mapping_direction",
        "methods", "tone_authority", "fit", "evaluation",
        "direction_templates", "classification", "final_test_policy",
    }:
        raise ConfigError("cross_mode_bridge fields are incomplete or ambiguous")
    if value["schema_version"] != "1.0.0" or not isinstance(value["enabled"], bool) or not isinstance(value["provisional"], bool):
        raise ConfigError("cross_mode_bridge requires schema 1.0.0 and boolean flags")
    if value["mapping_direction"] != "multisine_db_to_sweep_projection_db":
        raise ConfigError("cross_mode_bridge mapping_direction is fixed")
    if value["methods"] != ["identity", "bias_only", "per_tone_affine"]:
        raise ConfigError("cross_mode_bridge methods must be preregistered in fixed order")
    if value["tone_authority"] != "fold_specific_p9b_minimum" or value["final_test_policy"] != "sealed":
        raise ConfigError("cross_mode_bridge authority/final-test policy is fixed")

    def finite(number: Any, *, positive: bool = False) -> bool:
        return (
            not isinstance(number, bool)
            and isinstance(number, (int, float))
            and np.isfinite(number)
            and (not positive or number > 0)
        )

    fit = value["fit"]
    if not isinstance(fit, Mapping) or set(fit) != {
        "allowed_cohort_roles", "minimum_pairs_per_tone",
        "minimum_input_variance_db2", "slope_bounds", "residual_policy",
    }:
        raise ConfigError("cross_mode_bridge fit fields are incomplete")
    if fit["allowed_cohort_roles"] != ["development", "training"]:
        raise ConfigError("cross_mode_bridge fit roles are fixed")
    pairs = fit["minimum_pairs_per_tone"]
    if isinstance(pairs, bool) or not isinstance(pairs, int) or pairs < 2:
        raise ConfigError("cross_mode_bridge minimum_pairs_per_tone must be >= 2")
    if not finite(fit["minimum_input_variance_db2"], positive=True):
        raise ConfigError("cross_mode_bridge minimum input variance must be positive")
    bounds = fit["slope_bounds"]
    if not isinstance(bounds, list) or len(bounds) != 2 or not all(finite(item) for item in bounds) or not 0.0 < bounds[0] < bounds[1]:
        raise ConfigError("cross_mode_bridge slope bounds must be finite increasing positive values")
    residual = fit["residual_policy"]
    if not isinstance(residual, Mapping) or set(residual) != {
        "warning_above_rms_db", "unavailable_above_rms_db"
    }:
        raise ConfigError("cross_mode_bridge residual policy is incomplete")
    warning = residual["warning_above_rms_db"]
    unavailable = residual["unavailable_above_rms_db"]
    if not finite(warning) or not finite(unavailable) or not 0.0 <= warning < unavailable:
        raise ConfigError("cross_mode_bridge residual thresholds must be finite and increasing")
    evaluation = value["evaluation"]
    if not isinstance(evaluation, Mapping) or set(evaluation) != {"minimum_common_tones", "minimum_pair_coverage"}:
        raise ConfigError("cross_mode_bridge evaluation fields are incomplete")
    minimum_tones = evaluation["minimum_common_tones"]
    coverage = evaluation["minimum_pair_coverage"]
    if isinstance(minimum_tones, bool) or not isinstance(minimum_tones, int) or minimum_tones < 2 or not finite(coverage, positive=True) or coverage > 1.0:
        raise ConfigError("cross_mode_bridge evaluation thresholds are invalid")
    templates = value["direction_templates"]
    if not isinstance(templates, Mapping) or set(templates) != {"metric", "minimum_common_tones"} or templates["metric"] != "pearson" or isinstance(templates["minimum_common_tones"], bool) or not isinstance(templates["minimum_common_tones"], int) or templates["minimum_common_tones"] < 2:
        raise ConfigError("cross_mode_bridge direction-template policy is invalid")
    classification = value["classification"]
    allowed_models = {"nearest_template_correlation", "nearest_centroid", "logistic_regression"}
    if not isinstance(classification, Mapping) or set(classification) != {"models", "minimum_training_features", "minimum_prediction_coverage"} or not isinstance(classification["models"], list) or not classification["models"] or len(classification["models"]) != len(set(classification["models"])) or set(classification["models"]) - allowed_models:
        raise ConfigError("cross_mode_bridge classification policy is invalid")
    minimum_features = classification["minimum_training_features"]
    prediction_coverage = classification["minimum_prediction_coverage"]
    if isinstance(minimum_features, bool) or not isinstance(minimum_features, int) or minimum_features < 2 or not finite(prediction_coverage, positive=True) or prediction_coverage > 1.0:
        raise ConfigError("cross_mode_bridge classification thresholds are invalid")


def validate_offline_fast_readout_config(value: Any) -> None:
    """Validate the fail-closed frozen P9-D inference contract."""
    if not isinstance(value, Mapping):
        raise ConfigError("offline_fast_readout must be a mapping")
    required = {
        "schema_version", "enabled", "provisional", "model", "calibration", "qc",
        "final_test_policy", "output_overwrite",
    }
    if set(value) != required:
        raise ConfigError("offline_fast_readout fields are incomplete or ambiguous")
    if value["schema_version"] != "1.0.0" or not isinstance(value["enabled"], bool) or not isinstance(value["provisional"], bool):
        raise ConfigError("offline_fast_readout requires schema 1.0.0 and boolean flags")
    model = value["model"]
    if not isinstance(model, Mapping) or set(model) != {"model_id", "model_domain", "valid_mask_policy", "tie_break"}:
        raise ConfigError("offline_fast_readout model fields are incomplete")
    if model["model_id"] != "nearest_centroid" or model["model_domain"] not in {"multisine", "sweep_projection"}:
        raise ConfigError("offline_fast_readout model is not preregistered")
    if model["valid_mask_policy"] != "require_all_frozen_features" or model["tie_break"] != "configured_direction_order":
        raise ConfigError("offline_fast_readout model mask/tie policy is fixed")
    calibration = value["calibration"]
    if not isinstance(calibration, Mapping) or set(calibration) != {"mode", "required_on_domain_mismatch"}:
        raise ConfigError("offline_fast_readout calibration fields are incomplete")
    if calibration["mode"] not in {"disabled", "optional_frozen"} or calibration["required_on_domain_mismatch"] is not True:
        raise ConfigError("offline_fast_readout calibration must fail closed on domain mismatch")
    qc = value["qc"]
    if not isinstance(qc, Mapping) or set(qc) != {
        "required_tone_coverage", "phase_policy", "p8_warning_action", "p8_exclude_candidate_action"
    }:
        raise ConfigError("offline_fast_readout QC fields are incomplete")
    coverage = _finite_number(qc, "required_tone_coverage", "offline_fast_readout required_tone_coverage")
    if not 0 < coverage <= 1:
        raise ConfigError("offline_fast_readout required_tone_coverage must be in (0, 1]")
    if qc["phase_policy"] != "magnitude_only_warning" or qc["p8_warning_action"] != "warning" or qc["p8_exclude_candidate_action"] != "invalid":
        raise ConfigError("offline_fast_readout QC status policy is fixed")
    if value["final_test_policy"] != "sealed" or value["output_overwrite"] != "reject":
        raise ConfigError("offline_fast_readout final-test/output policy is fixed")


def validate_tone_selection_config(value: Any) -> None:
    """Validate the complete provisional P9-A contract."""
    if not isinstance(value, Mapping):
        raise ConfigError("tone_selection must be a mapping")
    if set(value) != {
        "schema_version", "enabled", "provisional", "eligibility",
        "configuration_gain", "reliability", "scoring", "selection",
    }:
        raise ConfigError("tone_selection fields are incomplete or ambiguous")
    if value["schema_version"] != "1.0.0" or not isinstance(value["enabled"], bool) or not isinstance(value["provisional"], bool):
        raise ConfigError("tone_selection requires schema 1.0.0 and boolean enabled/provisional")

    def finite(item: Any, *, positive: bool = False, nonnegative: bool = False) -> bool:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not np.isfinite(item):
            return False
        return (not positive or item > 0) and (not nonnegative or item >= 0)

    eligibility = value["eligibility"]
    if not isinstance(eligibility, Mapping) or set(eligibility) != {
        "analysis_band_hz", "edge_guard_hz", "minimum_valid_sample_fraction",
        "minimum_direction_count", "minimum_cont_pairs", "minimum_repos_pairs",
        "effective_energy_range_db", "excluded_bands_hz", "excluded_band_safety_distance_hz",
    }:
        raise ConfigError("tone_selection.eligibility fields are incomplete")
    for name in ("analysis_band_hz", "effective_energy_range_db"):
        limits = eligibility[name]
        if not isinstance(limits, list) or len(limits) != 2 or not all(finite(item) for item in limits) or not limits[0] < limits[1]:
            raise ConfigError(f"tone_selection {name} must be finite and increasing")
    fraction = eligibility["minimum_valid_sample_fraction"]
    if not finite(fraction, positive=True) or fraction > 1:
        raise ConfigError("tone_selection minimum_valid_sample_fraction must be in (0, 1]")
    for name, minimum in (("minimum_direction_count", 2), ("minimum_cont_pairs", 0), ("minimum_repos_pairs", 0)):
        item = eligibility[name]
        if isinstance(item, bool) or not isinstance(item, int) or item < minimum:
            raise ConfigError(f"tone_selection {name} is invalid")
    if not finite(eligibility["edge_guard_hz"], nonnegative=True) or not finite(eligibility["excluded_band_safety_distance_hz"], nonnegative=True):
        raise ConfigError("tone_selection edge/excluded-band distance is invalid")
    excluded = eligibility["excluded_bands_hz"]
    if not isinstance(excluded, list):
        raise ConfigError("tone_selection excluded_bands_hz must be a list")
    ranges: list[tuple[float, float]] = []
    for band in excluded:
        if not isinstance(band, list) or len(band) != 2 or not all(finite(item) for item in band) or not band[0] < band[1]:
            raise ConfigError("tone_selection excluded band is invalid")
        ranges.append((float(band[0]), float(band[1])))
    if any(max(a[0], b[0]) < min(a[1], b[1]) for index, a in enumerate(ranges) for b in ranges[index + 1:]):
        raise ConfigError("tone_selection excluded bands must not overlap")

    gain = value["configuration_gain"]
    if not isinstance(gain, Mapping) or set(gain) != {"baseline_configuration", "candidate_configuration", "epsilon_db_squared"} or not str(gain.get("baseline_configuration", "")).strip() or not str(gain.get("candidate_configuration", "")).strip() or gain["baseline_configuration"] == gain["candidate_configuration"] or not finite(gain["epsilon_db_squared"], positive=True):
        raise ConfigError("tone_selection configuration_gain is invalid")
    reliability = value["reliability"]
    if not isinstance(reliability, Mapping) or set(reliability) != {"minimum_pairs_per_tone", "snr_target_db", "stability_scale_db", "noise_scale_db"}:
        raise ConfigError("tone_selection reliability fields are incomplete")
    if isinstance(reliability["minimum_pairs_per_tone"], bool) or not isinstance(reliability["minimum_pairs_per_tone"], int) or reliability["minimum_pairs_per_tone"] < 1 or not finite(reliability["snr_target_db"]) or not finite(reliability["stability_scale_db"], positive=True) or not finite(reliability["noise_scale_db"], positive=True):
        raise ConfigError("tone_selection reliability fields are invalid")

    scoring = value["scoring"]
    if not isinstance(scoring, Mapping) or set(scoring) != {"method", "epsilon_db_squared", "optional_missing_policy", "tie_method", "components", "variance_ratio"}:
        raise ConfigError("tone_selection scoring fields are incomplete")
    if scoring["method"] not in {"variance_ratio", "weighted_rank_sum"} or scoring["tie_method"] != "average" or scoring["optional_missing_policy"] != "renormalize_available_weights_with_warning" or not finite(scoring["epsilon_db_squared"], positive=True):
        raise ConfigError("tone_selection scoring policy is invalid")
    expected_components = {
        "between_direction_variance", "within_cont_variance", "within_repos_variance",
        "configuration_gain", "sweep_repeatability", "effective_energy_margin",
        "instability_noise_penalty", "excluded_band_proximity",
    }
    components = scoring["components"]
    if not isinstance(components, Mapping) or set(components) != expected_components:
        raise ConfigError("tone_selection scoring components are incomplete")
    total_weight = 0.0
    for component_id, definition in components.items():
        if not isinstance(definition, Mapping) or set(definition) != {"required", "direction", "weight"} or not isinstance(definition["required"], bool) or definition["direction"] not in {"higher", "lower"} or not finite(definition["weight"], nonnegative=True):
            raise ConfigError(f"tone_selection component {component_id} is invalid")
        total_weight += float(definition["weight"])
    if total_weight <= 0:
        raise ConfigError("tone_selection component weights must sum above zero")
    ratio = scoring["variance_ratio"]
    if not isinstance(ratio, Mapping) or set(ratio) != {"within_cont_weight", "within_repos_weight"} or not all(finite(item, nonnegative=True) for item in ratio.values()) or sum(float(item) for item in ratio.values()) <= 0:
        raise ConfigError("tone_selection variance-ratio weights are invalid")

    selection = value["selection"]
    if not isinstance(selection, Mapping) or set(selection) != {"target_count", "minimum_spacing_hz", "minimum_spacing_bins", "allow_partial", "band_quotas"}:
        raise ConfigError("tone_selection selection fields are incomplete")
    if isinstance(selection["target_count"], bool) or not isinstance(selection["target_count"], int) or selection["target_count"] < 1 or isinstance(selection["minimum_spacing_bins"], bool) or not isinstance(selection["minimum_spacing_bins"], int) or selection["minimum_spacing_bins"] < 1 or not finite(selection["minimum_spacing_hz"], nonnegative=True) or not isinstance(selection["allow_partial"], bool):
        raise ConfigError("tone_selection target/spacing/partial fields are invalid")
    quotas = selection["band_quotas"]
    if not isinstance(quotas, list):
        raise ConfigError("tone_selection band_quotas must be a list")
    ids: set[str] = set()
    quota_ranges: list[tuple[float, float]] = []
    for quota in quotas:
        if not isinstance(quota, Mapping) or set(quota) != {"band_id", "f_min_hz", "f_max_hz", "minimum_count", "maximum_count"} or not str(quota.get("band_id", "")).strip() or str(quota["band_id"]) in ids or not finite(quota["f_min_hz"], positive=True) or not finite(quota["f_max_hz"], positive=True) or not quota["f_min_hz"] < quota["f_max_hz"] or any(isinstance(quota[name], bool) or not isinstance(quota[name], int) for name in ("minimum_count", "maximum_count")) or not 0 <= quota["minimum_count"] <= quota["maximum_count"]:
            raise ConfigError("tone_selection band quota is invalid")
        ids.add(str(quota["band_id"]))
        quota_ranges.append((float(quota["f_min_hz"]), float(quota["f_max_hz"])))
    if any(max(a[0], b[0]) < min(a[1], b[1]) for index, a in enumerate(quota_ranges) for b in quota_ranges[index + 1:]):
        raise ConfigError("tone_selection band quotas must not overlap")

"""P9-C leakage-safe sweep-to-multisine bridge calibration.

The core consumes already constructed matched-tone values.  It never reads raw
measurement files and never chooses tones or calibration methods from held-out
results.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .classification import predict_direction_fold, summarize_direction_predictions
from .comparison_metrics import absolute_comparison_unavailable_reason
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .schemas import FeatureKind, FeatureSet, MeasurementMode
from .tone_features import ToneFeatureConstructionError, assert_matched_tone_schema


P9C_SCHEMA_VERSION = "1.0.0"


class CrossModeBridgeInputError(ValueError):
    """Raised when a P9-C input or frozen authority cannot be trusted."""


class CalibrationStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_text(value: str, label: str) -> str:
    if not str(value).strip():
        raise CrossModeBridgeInputError(f"{label} must be non-empty")
    return str(value)


def _require_sha256(value: str, label: str) -> str:
    digest = str(value).removeprefix("sha256:")
    if (
        not str(value).startswith("sha256:")
        or len(digest) != 64
        or digest != digest.lower()
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise CrossModeBridgeInputError(f"{label} must be sha256:<lowercase digest>")
    return str(value)


@dataclass(frozen=True, slots=True)
class MatchedModePair:
    match_pair_id: str
    cross_mode_group_id: str
    physical_state_id: str
    sweep_artifact_id: str
    multisine_artifact_id: str
    direction_id: str
    direction_angle_deg: float
    configuration_id: str
    session_id: str | None
    repeat_type: str | None
    repeat_id: str | None
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str | None
    cohort_role: str
    selection_reason: str

    def __post_init__(self) -> None:
        for name in (
            "match_pair_id",
            "cross_mode_group_id",
            "physical_state_id",
            "sweep_artifact_id",
            "multisine_artifact_id",
            "direction_id",
            "configuration_id",
            "selection_reason",
        ):
            _require_text(getattr(self, name), name)
        if self.cohort_role not in {"development", "training", "final_test"}:
            raise CrossModeBridgeInputError("unsupported cohort_role")
        if not np.isfinite(self.direction_angle_deg) or not 0.0 <= self.direction_angle_deg < 360.0:
            raise CrossModeBridgeInputError("direction_angle_deg must be finite in [0, 360)")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MatchedModePair":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class CrossModeFoldDefinition:
    outer_fold_id: str
    split_protocol: str
    training_pair_ids: tuple[str, ...]
    test_pair_ids: tuple[str, ...]
    held_out_cross_mode_group_ids: tuple[str, ...]
    held_out_physical_state_ids: tuple[str, ...]
    training_membership_sha256: str
    ordered_tone_ids: tuple[str, ...]
    selected_subset_sha256: str
    candidate_universe_sha256: str
    p9a_selection_scope_sha256: str
    p9a_selection_artifact_sha256: str
    p9a_manifest_sha256: str
    p9b_result_sha256: str
    p9b_manifest_sha256: str
    p2b_result_sha256: str
    p4b_result_sha256: str
    ordered_tone_feature_names: tuple[str, ...] = ()
    ordered_tone_frequencies_hz: tuple[float, ...] = ()
    ordered_tone_source_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.outer_fold_id, "outer_fold_id")
        if self.split_protocol not in {
            "leave_one_session_out",
            "leave_one_reposition_round_out",
            "leave_one_assembly_out",
        }:
            raise CrossModeBridgeInputError("unsupported outer split protocol")
        for name in (
            "training_pair_ids",
            "test_pair_ids",
            "held_out_cross_mode_group_ids",
            "held_out_physical_state_ids",
            "ordered_tone_ids",
        ):
            values = getattr(self, name)
            if not values or len(set(values)) != len(values):
                raise CrossModeBridgeInputError(f"{name} must be non-empty and unique")
        for name in (
            "training_membership_sha256",
            "selected_subset_sha256",
            "candidate_universe_sha256",
            "p9a_selection_scope_sha256",
            "p9a_selection_artifact_sha256",
            "p9a_manifest_sha256",
            "p9b_result_sha256",
            "p9b_manifest_sha256",
            "p2b_result_sha256",
            "p4b_result_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        optional_lengths = {
            len(self.ordered_tone_feature_names),
            len(self.ordered_tone_frequencies_hz),
            len(self.ordered_tone_source_indices),
        }
        if optional_lengths != {0} and optional_lengths != {len(self.ordered_tone_ids)}:
            raise CrossModeBridgeInputError("fold tone authority arrays must align")
        if self.ordered_tone_source_indices and (
            len(set(self.ordered_tone_source_indices)) != len(self.ordered_tone_source_indices)
            or any(item < 0 for item in self.ordered_tone_source_indices)
        ):
            raise CrossModeBridgeInputError("fold tone source indices must be unique and non-negative")

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in (
            "training_pair_ids",
            "test_pair_ids",
            "held_out_cross_mode_group_ids",
            "held_out_physical_state_ids",
            "ordered_tone_ids",
            "ordered_tone_feature_names",
            "ordered_tone_frequencies_hz",
            "ordered_tone_source_indices",
        ):
            payload[name] = list(payload[name])
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeFoldDefinition":
        value = dict(payload)
        for name in (
            "training_pair_ids",
            "test_pair_ids",
            "held_out_cross_mode_group_ids",
            "held_out_physical_state_ids",
            "ordered_tone_ids",
            "ordered_tone_feature_names",
            "ordered_tone_frequencies_hz",
            "ordered_tone_source_indices",
        ):
            value[name] = tuple(value[name])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class P9CrossModeBridgeScope:
    schema_version: str
    analysis_scope_id: str
    data_origin: str
    run_purpose: str
    dataset_role: str
    calibration_lifecycle: str
    approval_status: str
    scientifically_eligible: bool
    deployment_eligible: bool
    canonical_analysis: bool
    mapping_direction: str
    calibration_methods: tuple[str, ...]
    pairs: tuple[MatchedModePair, ...]
    outer_folds: tuple[CrossModeFoldDefinition, ...]
    sealed_final_test_sample_ids: tuple[str, ...]
    sealed_final_test_sha256: str
    random_state: int
    direction_order_deg: tuple[float, ...] = ()
    classification_models: tuple[str, ...] = ("nearest_template_correlation",)

    def __post_init__(self) -> None:
        if self.schema_version != P9C_SCHEMA_VERSION:
            raise CrossModeBridgeInputError("P9-C scope schema_version must be 1.0.0")
        if (self.data_origin, self.run_purpose, self.dataset_role) != (
            "simulated",
            "software_validation",
            "software_validation",
        ):
            raise CrossModeBridgeInputError("DEV-C14 is simulated software_validation only")
        if self.calibration_lifecycle != "software_validation_only":
            raise CrossModeBridgeInputError(
                "simulated calibration lifecycle must be software_validation_only"
            )
        if self.approval_status != "not_approved":
            raise CrossModeBridgeInputError("simulated calibration must remain not_approved")
        if self.scientifically_eligible or self.deployment_eligible or self.canonical_analysis:
            raise CrossModeBridgeInputError("DEV-C14 cannot claim science, deployment, or canonical status")
        if self.mapping_direction != "multisine_db_to_sweep_projection_db":
            raise CrossModeBridgeInputError("P9-C mapping direction is fixed")
        if (
            not self.calibration_methods
            or len(set(self.calibration_methods)) != len(self.calibration_methods)
            or set(self.calibration_methods)
            - {"identity", "bias_only", "per_tone_affine"}
        ):
            raise CrossModeBridgeInputError("unsupported or duplicate calibration method")
        if not self.pairs:
            raise CrossModeBridgeInputError("P9-C scope requires explicit matched pairs")
        if any(pair.cohort_role == "final_test" for pair in self.pairs):
            raise CrossModeBridgeInputError("final_test FeatureSets cannot enter P9-C scope")
        for name, values in (
            ("match_pair_id", [item.match_pair_id for item in self.pairs]),
            ("cross_mode_group_id", [item.cross_mode_group_id for item in self.pairs]),
            ("physical_state_id", [item.physical_state_id for item in self.pairs]),
            ("sweep_artifact_id", [item.sweep_artifact_id for item in self.pairs]),
            ("multisine_artifact_id", [item.multisine_artifact_id for item in self.pairs]),
        ):
            if len(values) != len(set(values)):
                raise CrossModeBridgeInputError(
                    f"cross-mode pairing must be one-to-one: duplicate {name}"
                )
        if {item.sweep_artifact_id for item in self.pairs} & {
            item.multisine_artifact_id for item in self.pairs
        }:
            raise CrossModeBridgeInputError("cross-mode pairing must be one-to-one")
        pair_by_id = {item.match_pair_id: item for item in self.pairs}
        fold_ids = [item.outer_fold_id for item in self.outer_folds]
        if not fold_ids or len(fold_ids) != len(set(fold_ids)):
            raise CrossModeBridgeInputError("outer folds must be non-empty and unique")
        known = set(pair_by_id)
        for fold in self.outer_folds:
            train, test = set(fold.training_pair_ids), set(fold.test_pair_ids)
            if train & test:
                raise CrossModeBridgeInputError("training and test pairs must be disjoint")
            if train | test != known:
                raise CrossModeBridgeInputError("each outer fold must partition all explicit pairs")
            held_states = {pair_by_id[item].physical_state_id for item in test}
            held_groups = {pair_by_id[item].cross_mode_group_id for item in test}
            if held_states != set(fold.held_out_physical_state_ids) or held_groups != set(
                fold.held_out_cross_mode_group_ids
            ):
                raise CrossModeBridgeInputError("held pair metadata does not match fold authority")
            if held_states & {pair_by_id[item].physical_state_id for item in train}:
                raise CrossModeBridgeInputError("held physical state leaked into calibration training")
            test_pairs = tuple(pair_by_id[item] for item in fold.test_pair_ids)
            if fold.split_protocol == "leave_one_session_out":
                held_keys = {item.session_id for item in test_pairs}
                if None in held_keys or len(held_keys) != 1:
                    raise CrossModeBridgeInputError("LOSO fold must hold exactly one explicit session")
                expected_test = {
                    item.match_pair_id for item in self.pairs if item.session_id in held_keys
                }
            elif fold.split_protocol == "leave_one_reposition_round_out":
                if any(
                    item.repeat_type != "REPOS" or item.reposition_round_id is None
                    for item in test_pairs
                ):
                    raise CrossModeBridgeInputError(
                        "LORO fold requires explicit REPOS session/round metadata"
                    )
                held_keys = {
                    (item.session_id, item.reposition_round_id) for item in test_pairs
                }
                if len(held_keys) != 1:
                    raise CrossModeBridgeInputError(
                        "LORO fold must hold exactly one session/reposition round"
                    )
                expected_test = {
                    item.match_pair_id
                    for item in self.pairs
                    if item.repeat_type == "REPOS"
                    and (item.session_id, item.reposition_round_id) in held_keys
                }
            else:
                if any(
                    item.repeat_type != "REASM" or item.assembly_id is None
                    for item in test_pairs
                ):
                    raise CrossModeBridgeInputError(
                        "LOAO fold requires explicit REASM session/assembly metadata"
                    )
                held_keys = {(item.session_id, item.assembly_id) for item in test_pairs}
                if len(held_keys) != 1:
                    raise CrossModeBridgeInputError(
                        "LOAO fold must hold exactly one session/assembly"
                    )
                expected_test = {
                    item.match_pair_id
                    for item in self.pairs
                    if item.repeat_type == "REASM"
                    and (item.session_id, item.assembly_id) in held_keys
                }
            if set(fold.test_pair_ids) != expected_test:
                raise CrossModeBridgeInputError(
                    "outer fold does not hold the complete physical-state group"
                )
        _require_sha256(self.sealed_final_test_sha256, "sealed_final_test_sha256")
        if not isinstance(self.random_state, int) or self.random_state < 0:
            raise CrossModeBridgeInputError("random_state must be a non-negative integer")
        if self.direction_order_deg and (
            len(set(self.direction_order_deg)) != len(self.direction_order_deg)
            or any(not np.isfinite(item) or not 0.0 <= item < 360.0 for item in self.direction_order_deg)
        ):
            raise CrossModeBridgeInputError("direction_order_deg must be finite and unique")
        if (
            not self.classification_models
            or len(set(self.classification_models)) != len(self.classification_models)
            or set(self.classification_models)
            - {"nearest_template_correlation", "nearest_centroid", "logistic_regression"}
        ):
            raise CrossModeBridgeInputError("unsupported classification model")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_scope_id": self.analysis_scope_id,
            "data_origin": self.data_origin,
            "run_purpose": self.run_purpose,
            "dataset_role": self.dataset_role,
            "calibration_lifecycle": self.calibration_lifecycle,
            "approval_status": self.approval_status,
            "scientifically_eligible": self.scientifically_eligible,
            "deployment_eligible": self.deployment_eligible,
            "canonical_analysis": self.canonical_analysis,
            "mapping_direction": self.mapping_direction,
            "calibration_methods": list(self.calibration_methods),
            "pairs": [item.to_dict() for item in self.pairs],
            "outer_folds": [item.to_dict() for item in self.outer_folds],
            "sealed_final_test_sample_ids": list(self.sealed_final_test_sample_ids),
            "sealed_final_test_sha256": self.sealed_final_test_sha256,
            "random_state": self.random_state,
            "direction_order_deg": list(self.direction_order_deg),
            "classification_models": list(self.classification_models),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "P9CrossModeBridgeScope":
        required = set(cls.__dataclass_fields__)
        if set(payload) != required:
            raise CrossModeBridgeInputError("P9-C scope fields must be explicit")
        value = dict(payload)
        value["calibration_methods"] = tuple(value["calibration_methods"])
        value["pairs"] = tuple(MatchedModePair.from_dict(item) for item in value["pairs"])
        value["outer_folds"] = tuple(
            CrossModeFoldDefinition.from_dict(item) for item in value["outer_folds"]
        )
        value["sealed_final_test_sample_ids"] = tuple(value["sealed_final_test_sample_ids"])
        value["direction_order_deg"] = tuple(value["direction_order_deg"])
        value["classification_models"] = tuple(value["classification_models"])
        return cls(**value)

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ToneCalibrationFit:
    schema_version: str
    tone_id: str
    frequency_hz: float
    method: str
    status: CalibrationStatus
    slope: float | None
    intercept_db: float | None
    training_pair_ids: tuple[str, ...]
    training_pair_count: int
    input_variance_db2: float | None
    training_residual_rms_db: float | None
    training_residual_mae_db: float | None
    uncertainty_status: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", CalibrationStatus(self.status))

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["status"] = self.status.value
        payload["training_pair_ids"] = list(self.training_pair_ids)
        payload["reason_codes"] = list(self.reason_codes)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneCalibrationFit":
        value = dict(payload)
        value["training_pair_ids"] = tuple(value["training_pair_ids"])
        value["reason_codes"] = tuple(value["reason_codes"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class CrossModeToneComparison:
    schema_version: str
    outer_fold_id: str
    tone_id: str
    frequency_hz: float
    method: str
    fit_status: CalibrationStatus
    evaluation_pair_ids: tuple[str, ...]
    pair_count: int
    valid_count: int
    missing_count: int
    raw_mean_bias_db: float | None
    raw_median_bias_db: float | None
    raw_bias_std_db: float | None
    raw_pearson_correlation: float | None
    raw_rms_difference_db: float | None
    raw_mae_db: float | None
    raw_maximum_absolute_difference_db: float | None
    calibrated_mean_residual_db: float | None
    calibrated_median_residual_db: float | None
    calibrated_residual_std_db: float | None
    calibrated_pearson_correlation: float | None
    calibrated_rms_difference_db: float | None
    calibrated_mae_db: float | None
    calibrated_maximum_absolute_residual_db: float | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fit_status", CalibrationStatus(self.fit_status))

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["fit_status"] = self.fit_status.value
        payload["evaluation_pair_ids"] = list(self.evaluation_pair_ids)
        payload["reason_codes"] = list(self.reason_codes)
        return payload


def _finite_pairs(
    multisine_db: NDArray[np.float64],
    sweep_db: NDArray[np.float64],
    pair_ids: tuple[str, ...],
) -> tuple[NDArray[np.float64], NDArray[np.float64], tuple[str, ...]]:
    left = np.asarray(multisine_db, dtype=np.float64)
    right = np.asarray(sweep_db, dtype=np.float64)
    if left.ndim != 1 or right.ndim != 1 or left.size != right.size or left.size != len(pair_ids):
        raise CrossModeBridgeInputError("paired calibration values and pair IDs must align")
    valid = np.isfinite(left) & np.isfinite(right)
    return left[valid], right[valid], tuple(
        pair_id for pair_id, keep in zip(pair_ids, valid, strict=True) if keep
    )


def fit_tone_calibration(
    *,
    tone_id: str,
    frequency_hz: float,
    method: str,
    multisine_db: NDArray[np.float64],
    sweep_db: NDArray[np.float64],
    training_pair_ids: tuple[str, ...],
    config: Mapping[str, Any],
) -> ToneCalibrationFit:
    """Fit one preregistered tone mapping from outer-training pairs only."""
    if method not in {"identity", "bias_only", "per_tone_affine"}:
        raise CrossModeBridgeInputError("unsupported calibration method")
    x, y, used_pair_ids = _finite_pairs(multisine_db, sweep_db, training_pair_ids)
    minimum = int(config["minimum_pairs_per_tone"])
    variance = float(np.var(x)) if x.size else None
    reasons: list[str] = []
    slope: float | None = None
    intercept: float | None = None
    if method == "identity":
        slope, intercept = 1.0, 0.0
    elif x.size < minimum:
        reasons.append("insufficient_training_pairs")
    elif method == "bias_only":
        slope, intercept = 1.0, float(np.mean(y - x))
    elif variance is None or variance < float(config["minimum_input_variance_db2"]):
        reasons.append("input_variance_below_minimum")
    else:
        slope = float(np.mean((x - np.mean(x)) * (y - np.mean(y))) / variance)
        intercept = float(np.mean(y) - slope * np.mean(x))
        lower, upper = (float(item) for item in config["slope_bounds"])
        if not lower <= slope <= upper:
            slope = intercept = None
            reasons.append("slope_out_of_bounds")
    residual_rms: float | None = None
    residual_mae: float | None = None
    status = CalibrationStatus.UNAVAILABLE if reasons else CalibrationStatus.VALID
    if slope is not None and intercept is not None and x.size:
        residual = slope * x + intercept - y
        residual_rms = float(np.sqrt(np.mean(np.square(residual))))
        residual_mae = float(np.mean(np.abs(residual)))
        policy = config["residual_policy"]
        if method == "identity" and residual_rms > float(policy["warning_above_rms_db"]):
            status = CalibrationStatus.WARNING
            reasons.append("identity_baseline_residual_above_threshold")
        elif residual_rms > float(policy["unavailable_above_rms_db"]):
            status = CalibrationStatus.UNAVAILABLE
            slope = intercept = None
            reasons.append("training_residual_above_unavailable_threshold")
        elif residual_rms > float(policy["warning_above_rms_db"]):
            status = CalibrationStatus.WARNING
            reasons.append("training_residual_above_warning_threshold")
    return ToneCalibrationFit(
        P9C_SCHEMA_VERSION,
        _require_text(tone_id, "tone_id"),
        float(frequency_hz),
        method,
        status,
        slope,
        intercept,
        used_pair_ids,
        len(used_pair_ids),
        variance,
        residual_rms,
        residual_mae,
        "descriptive_only" if len(used_pair_ids) >= 2 else "unavailable",
        tuple(reasons),
    )


def apply_tone_calibration(
    multisine_db: NDArray[np.float64], fit: ToneCalibrationFit
) -> NDArray[np.float64]:
    if fit.status is CalibrationStatus.UNAVAILABLE or fit.slope is None or fit.intercept_db is None:
        raise CrossModeBridgeInputError("unavailable calibration fit cannot be applied")
    result = np.asarray(multisine_db, dtype=np.float64) * fit.slope + fit.intercept_db
    result = np.array(result, copy=True)
    result.setflags(write=False)
    return result


def _pearson(left: NDArray[np.float64], right: NDArray[np.float64]) -> float | None:
    if left.size < 2 or np.std(left) <= 0.0 or np.std(right) <= 0.0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def compare_tone_values(
    *,
    outer_fold_id: str,
    evaluation_pair_ids: tuple[str, ...],
    fit: ToneCalibrationFit,
    multisine_db: NDArray[np.float64],
    sweep_db: NDArray[np.float64],
) -> CrossModeToneComparison:
    x, y, used_ids = _finite_pairs(multisine_db, sweep_db, evaluation_pair_ids)
    missing = len(evaluation_pair_ids) - len(used_ids)
    if not used_ids:
        return CrossModeToneComparison(
            P9C_SCHEMA_VERSION, outer_fold_id, fit.tone_id, fit.frequency_hz,
            fit.method, fit.status, (), len(evaluation_pair_ids), 0, missing,
            *([None] * 14), ("no_valid_heldout_pairs",),
        )
    raw = x - y
    calibrated: NDArray[np.float64] | None = None
    reasons = list(fit.reason_codes)
    if fit.status is not CalibrationStatus.UNAVAILABLE:
        calibrated = apply_tone_calibration(x, fit) - y
    else:
        reasons.append("calibration_fit_unavailable")
    raw_std = float(np.std(raw, ddof=1)) if raw.size >= 2 else None
    calibrated_std = (
        float(np.std(calibrated, ddof=1))
        if calibrated is not None and calibrated.size >= 2
        else None
    )
    return CrossModeToneComparison(
        P9C_SCHEMA_VERSION,
        outer_fold_id,
        fit.tone_id,
        fit.frequency_hz,
        fit.method,
        fit.status,
        used_ids,
        len(evaluation_pair_ids),
        len(used_ids),
        missing,
        float(np.mean(raw)),
        float(np.median(raw)),
        raw_std,
        _pearson(x, y),
        float(np.sqrt(np.mean(np.square(raw)))),
        float(np.mean(np.abs(raw))),
        float(np.max(np.abs(raw))),
        None if calibrated is None else float(np.mean(calibrated)),
        None if calibrated is None else float(np.median(calibrated)),
        calibrated_std,
        None if calibrated is None else _pearson(apply_tone_calibration(x, fit), y),
        None if calibrated is None else float(np.sqrt(np.mean(np.square(calibrated)))),
        None if calibrated is None else float(np.mean(np.abs(calibrated))),
        None if calibrated is None else float(np.max(np.abs(calibrated))),
        tuple(dict.fromkeys(reasons)),
    )


@dataclass(frozen=True, slots=True)
class CrossModeCalibrationModel:
    schema_version: str
    model_id: str
    outer_fold_id: str
    method: str
    mapping_direction: str
    ordered_tone_ids: tuple[str, ...]
    ordered_frequencies_hz: tuple[float, ...]
    tone_fits: tuple[ToneCalibrationFit, ...]
    training_pair_ids: tuple[str, ...]
    training_membership_sha256: str
    held_out_pair_ids: tuple[str, ...]
    held_out_physical_state_ids: tuple[str, ...]
    selected_subset_sha256: str
    candidate_universe_sha256: str
    p2b_result_sha256: str
    p4b_result_sha256: str
    p9a_selection_artifact_sha256: str
    p9b_result_sha256: str
    scope_sha256: str
    config_sha256: str
    input_quantity: str
    output_quantity: str
    units: str
    input_reference: str | None
    output_reference: str | None
    normalization: str
    calibration_lifecycle: str
    approval_status: str
    scientifically_eligible: bool
    deployment_eligible: bool
    final_test_read: bool

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in (
            "ordered_tone_ids", "ordered_frequencies_hz", "training_pair_ids",
            "held_out_pair_ids", "held_out_physical_state_ids",
        ):
            payload[name] = list(payload[name])
        payload["tone_fits"] = [item.to_dict() for item in self.tone_fits]
        payload["model_semantic_sha256"] = self.sha256
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeCalibrationModel":
        value = dict(payload)
        semantic = value.pop("model_semantic_sha256", None)
        for name in (
            "ordered_tone_ids", "ordered_frequencies_hz", "training_pair_ids",
            "held_out_pair_ids", "held_out_physical_state_ids",
        ):
            value[name] = tuple(value[name])
        value["tone_fits"] = tuple(ToneCalibrationFit.from_dict(item) for item in value["tone_fits"])
        result = cls(**value)
        if semantic is not None and semantic != result.sha256:
            raise CrossModeBridgeInputError("calibration model semantic hash mismatch")
        return result

    @property
    def sha256(self) -> str:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in (
            "ordered_tone_ids", "ordered_frequencies_hz", "training_pair_ids",
            "held_out_pair_ids", "held_out_physical_state_ids",
        ):
            payload[name] = list(payload[name])
        payload["tone_fits"] = [item.to_dict() for item in self.tone_fits]
        return _canonical_sha256(payload)


@dataclass(frozen=True, slots=True)
class DirectionTemplateComparison:
    schema_version: str
    outer_fold_id: str
    method: str
    direction_deg: float
    common_valid_tone_count: int
    raw_correlation: float | None
    calibrated_correlation: float | None
    raw_rms_difference_db: float | None
    calibrated_rms_difference_db: float | None
    raw_true_direction_rank: int | None
    calibrated_true_direction_rank: int | None
    raw_nearest_direction_matches: bool | None
    nearest_direction_matches: bool | None
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["reason_codes"] = list(self.reason_codes)
        return payload


@dataclass(frozen=True, slots=True)
class CalibratedCrossModePrediction:
    schema_version: str
    outer_fold_id: str
    method: str
    protocol: str
    model_id: str
    pair_id: str
    artifact_id: str
    true_direction_deg: float
    predicted_direction_deg: float | None
    second_direction_deg: float | None
    score: float | None
    margin: float | None
    available: bool
    unavailable_reason: str | None
    tone_count: int
    training_pair_ids: tuple[str, ...]
    held_out_pair_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["training_pair_ids"] = list(self.training_pair_ids)
        payload["held_out_pair_ids"] = list(self.held_out_pair_ids)
        return payload


@dataclass(frozen=True, slots=True)
class CrossModeClassificationMetric:
    schema_version: str
    outer_fold_id: str
    method: str
    protocol: str
    model_id: str
    available: bool
    balanced_accuracy: float | None
    macro_f1: float | None
    coverage: float
    confusion_matrix: tuple[tuple[int, ...], ...]
    per_class_metrics: tuple[Mapping[str, Any], ...]
    prediction_count: int
    unavailable_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["confusion_matrix"] = [list(item) for item in self.confusion_matrix]
        payload["per_class_metrics"] = [dict(item) for item in self.per_class_metrics]
        return payload


@dataclass(frozen=True, slots=True)
class CrossModeFoldEvaluation:
    schema_version: str
    outer_fold_id: str
    method: str
    status: CalibrationStatus
    tone_count: int
    available_tone_count: int
    pair_count: int
    valid_cell_count: int
    total_cell_count: int
    tone_coverage: float
    pair_coverage: float
    raw_rms_difference_db: float | None
    calibrated_rms_difference_db: float | None
    raw_mae_db: float | None
    calibrated_mae_db: float | None
    raw_correlation: float | None
    calibrated_correlation: float | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", CalibrationStatus(self.status))

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["status"] = self.status.value
        payload["reason_codes"] = list(self.reason_codes)
        return payload


@dataclass(frozen=True, slots=True)
class P9CrossModeBridgeResult:
    schema_version: str
    processing_status: str
    analysis_scope_id: str
    analysis_scope_sha256: str
    config_sha256: str
    data_origin: str
    run_purpose: str
    scientifically_eligible: bool
    deployment_eligible: bool
    canonical_analysis: bool
    calibration_lifecycle: str
    approval_status: str
    final_test_read: bool
    calibration_models: tuple[CrossModeCalibrationModel, ...]
    tone_comparisons: tuple[CrossModeToneComparison, ...]
    direction_template_comparisons: tuple[DirectionTemplateComparison, ...]
    predictions: tuple[CalibratedCrossModePrediction, ...]
    classification_metrics: tuple[CrossModeClassificationMetric, ...]
    fold_evaluations: tuple[CrossModeFoldEvaluation, ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "processing_status": self.processing_status,
            "analysis_scope_id": self.analysis_scope_id,
            "analysis_scope_sha256": self.analysis_scope_sha256,
            "config_sha256": self.config_sha256,
            "data_origin": self.data_origin,
            "run_purpose": self.run_purpose,
            "source_type": self.data_origin,
            "purpose": self.run_purpose,
            "scientifically_eligible": self.scientifically_eligible,
            "deployment_eligible": self.deployment_eligible,
            "canonical_analysis": self.canonical_analysis,
            "calibration_lifecycle": self.calibration_lifecycle,
            "approval_status": self.approval_status,
            "final_test_read": self.final_test_read,
            "calibration_models": [item.to_dict() for item in self.calibration_models],
            "tone_comparisons": [item.to_dict() for item in self.tone_comparisons],
            "direction_template_comparisons": [item.to_dict() for item in self.direction_template_comparisons],
            "predictions": [item.to_dict() for item in self.predictions],
            "classification_metrics": [item.to_dict() for item in self.classification_metrics],
            "fold_evaluations": [item.to_dict() for item in self.fold_evaluations],
            "warnings": list(self.warnings),
            "failures": list(self.failures),
        }

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _validate_pair_feature_contracts(
    artifacts: Mapping[str, FeatureSet], scope: P9CrossModeBridgeScope
) -> dict[str, str | None]:
    absolute_reasons: dict[str, str | None] = {}
    for pair in scope.pairs:
        try:
            sweep = artifacts[pair.sweep_artifact_id]
            multisine = artifacts[pair.multisine_artifact_id]
        except KeyError as exc:
            raise CrossModeBridgeInputError(f"scope references unknown FeatureSet: {exc.args[0]}") from exc
        if sweep.feature_kind is not FeatureKind.TONE_PROJECTION_FROM_SWEEP or sweep.source_measurement_mode is not MeasurementMode.REW_SWEEP:
            raise CrossModeBridgeInputError("sweep role has incompatible FeatureSet kind/mode")
        if multisine.feature_kind is not FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE or multisine.source_measurement_mode is not MeasurementMode.SCHROEDER_MULTISINE:
            raise CrossModeBridgeInputError("multisine role has incompatible FeatureSet kind/mode")
        try:
            assert_matched_tone_schema(sweep, multisine)
        except ToneFeatureConstructionError as exc:
            raise CrossModeBridgeInputError(str(exc)) from exc
        expected = {
            "configuration": pair.configuration_id,
            "angle_deg": pair.direction_angle_deg,
            "session_id": pair.session_id,
            "repeat_type": pair.repeat_type,
            "repeat_id": pair.repeat_id,
            "reposition_round_id": pair.reposition_round_id,
            "assembly_id": pair.assembly_id,
            "acquisition_block_id": pair.acquisition_block_id,
        }
        for feature in (sweep, multisine):
            mismatch = [name for name, value in expected.items() if getattr(feature.meta, name) != value]
            if mismatch:
                raise CrossModeBridgeInputError(
                    f"pair {pair.match_pair_id} metadata mismatch: {', '.join(mismatch)}"
                )
        absolute_reasons[pair.match_pair_id] = absolute_comparison_unavailable_reason(sweep, multisine)
    expected_artifacts = {
        artifact for pair in scope.pairs
        for artifact in (pair.sweep_artifact_id, pair.multisine_artifact_id)
    }
    if set(artifacts) != expected_artifacts:
        raise CrossModeBridgeInputError("FeatureSet inputs must exactly match explicit scope")
    return absolute_reasons


def _unavailable_fit(
    tone_id: str, frequency_hz: float, method: str, pair_ids: tuple[str, ...], reason: str
) -> ToneCalibrationFit:
    return ToneCalibrationFit(
        P9C_SCHEMA_VERSION, tone_id, frequency_hz, method,
        CalibrationStatus.UNAVAILABLE, None, None, pair_ids, len(pair_ids), None,
        None, None, "unavailable", (reason,),
    )


def _fold_evaluation(
    fold: CrossModeFoldDefinition,
    method: str,
    comparisons: Sequence[CrossModeToneComparison],
    *,
    minimum_common_tones: int,
    minimum_pair_coverage: float,
) -> CrossModeFoldEvaluation:
    rows = tuple(comparisons)
    available = tuple(row for row in rows if row.calibrated_rms_difference_db is not None)
    total_cells = len(rows) * len(fold.test_pair_ids)
    valid_cells = sum(row.valid_count for row in available)
    raw_rms_values = [row.raw_rms_difference_db for row in available if row.raw_rms_difference_db is not None]
    cal_rms_values = [row.calibrated_rms_difference_db for row in available if row.calibrated_rms_difference_db is not None]
    raw_mae_values = [row.raw_mae_db for row in available if row.raw_mae_db is not None]
    cal_mae_values = [row.calibrated_mae_db for row in available if row.calibrated_mae_db is not None]
    raw_corr = [row.raw_pearson_correlation for row in available if row.raw_pearson_correlation is not None]
    cal_corr = [row.calibrated_pearson_correlation for row in available if row.calibrated_pearson_correlation is not None]
    reasons_set = {reason for row in rows for reason in row.reason_codes}
    tone_coverage = len(available) / len(rows) if rows else 0.0
    pair_coverage = valid_cells / total_cells if total_cells else 0.0
    if len(available) < minimum_common_tones:
        reasons_set.add("common_tone_count_below_minimum")
    if pair_coverage < minimum_pair_coverage:
        reasons_set.add("pair_coverage_below_minimum")
    reasons = tuple(sorted(reasons_set))
    if len(available) < minimum_common_tones or pair_coverage < minimum_pair_coverage:
        status = CalibrationStatus.UNAVAILABLE
    elif len(available) == len(rows):
        status = CalibrationStatus.WARNING if any(row.fit_status is CalibrationStatus.WARNING for row in rows) else CalibrationStatus.VALID
    else:
        status = CalibrationStatus.UNAVAILABLE
    return CrossModeFoldEvaluation(
        P9C_SCHEMA_VERSION, fold.outer_fold_id, method, status, len(rows), len(available),
        len(fold.test_pair_ids), valid_cells, total_cells,
        tone_coverage,
        pair_coverage,
        None if not raw_rms_values else float(np.sqrt(np.mean(np.square(raw_rms_values)))),
        None if not cal_rms_values else float(np.sqrt(np.mean(np.square(cal_rms_values)))),
        None if not raw_mae_values else float(np.mean(raw_mae_values)),
        None if not cal_mae_values else float(np.mean(cal_mae_values)),
        None if not raw_corr else float(np.mean(raw_corr)),
        None if not cal_corr else float(np.mean(cal_corr)),
        reasons,
    )


def _direction_templates(
    *,
    artifacts: Mapping[str, FeatureSet],
    pair_by_id: Mapping[str, MatchedModePair],
    fold: CrossModeFoldDefinition,
    model: CrossModeCalibrationModel,
    indices: tuple[int, ...],
    direction_order: tuple[float, ...],
    minimum_common_tones: int,
) -> tuple[DirectionTemplateComparison, ...]:
    test_pairs = tuple(pair_by_id[item] for item in fold.test_pair_ids)
    sweep_templates: dict[float, NDArray[np.float64]] = {}
    raw_templates: dict[float, NDArray[np.float64]] = {}
    calibrated_templates: dict[float, NDArray[np.float64]] = {}
    fits = model.tone_fits
    available_positions = tuple(index for index, fit in enumerate(fits) if fit.status is not CalibrationStatus.UNAVAILABLE)
    for direction in direction_order:
        matches = tuple(item for item in test_pairs if item.direction_angle_deg == direction)
        if not matches or len(available_positions) < minimum_common_tones:
            continue
        sweep_matrix = np.vstack([
            artifacts[item.sweep_artifact_id].values[list(indices)] for item in matches
        ])[:, list(available_positions)]
        multi_matrix = np.vstack([
            artifacts[item.multisine_artifact_id].values[list(indices)] for item in matches
        ])[:, list(available_positions)]
        if not np.all(np.isfinite(sweep_matrix)) or not np.all(np.isfinite(multi_matrix)):
            continue
        sweep_templates[direction] = np.mean(sweep_matrix, axis=0)
        raw_templates[direction] = np.mean(multi_matrix, axis=0)
        calibrated_templates[direction] = np.mean(
            np.column_stack([
                apply_tone_calibration(multi_matrix[:, position], fits[fit_index])
                for position, fit_index in enumerate(available_positions)
            ]),
            axis=0,
        )
    rows: list[DirectionTemplateComparison] = []
    for direction in direction_order:
        if direction not in sweep_templates or direction not in raw_templates:
            rows.append(DirectionTemplateComparison(
                P9C_SCHEMA_VERSION, fold.outer_fold_id, model.method, direction, 0,
                None, None, None, None, None, None, None, None,
                ("direction_template_unavailable",),
            ))
            continue
        sweep = sweep_templates[direction]
        raw = raw_templates[direction]
        calibrated = calibrated_templates[direction]
        raw_scores = [(candidate, _pearson(raw, template)) for candidate, template in sweep_templates.items()]
        cal_scores = [(candidate, _pearson(calibrated, template)) for candidate, template in sweep_templates.items()]
        raw_ranked = [item[0] for item in sorted(raw_scores, key=lambda item: (-(item[1] if item[1] is not None else -np.inf), direction_order.index(item[0])))]
        cal_ranked = [item[0] for item in sorted(cal_scores, key=lambda item: (-(item[1] if item[1] is not None else -np.inf), direction_order.index(item[0])))]
        rows.append(DirectionTemplateComparison(
            P9C_SCHEMA_VERSION, fold.outer_fold_id, model.method, direction, sweep.size,
            _pearson(raw, sweep), _pearson(calibrated, sweep),
            float(np.sqrt(np.mean(np.square(raw - sweep)))),
            float(np.sqrt(np.mean(np.square(calibrated - sweep)))),
            raw_ranked.index(direction) + 1 if direction in raw_ranked else None,
            cal_ranked.index(direction) + 1 if direction in cal_ranked else None,
            bool(raw_ranked and raw_ranked[0] == direction),
            bool(cal_ranked and cal_ranked[0] == direction), (),
        ))
    return tuple(rows)


def _classification_for_model(
    *,
    artifacts: Mapping[str, FeatureSet],
    pair_by_id: Mapping[str, MatchedModePair],
    fold: CrossModeFoldDefinition,
    model: CrossModeCalibrationModel,
    indices: tuple[int, ...],
    direction_order: tuple[float, ...],
    model_ids: tuple[str, ...],
    config: Mapping[str, Any],
    random_state: int,
) -> tuple[tuple[CalibratedCrossModePrediction, ...], tuple[CrossModeClassificationMetric, ...]]:
    available_positions = tuple(index for index, fit in enumerate(model.tone_fits) if fit.status is not CalibrationStatus.UNAVAILABLE)
    selected_indices = tuple(indices[index] for index in available_positions)
    if len(selected_indices) < int(config["minimum_training_features"]):
        return (), ()
    train_pairs = tuple(pair_by_id[item] for item in fold.training_pair_ids)
    test_pairs = tuple(pair_by_id[item] for item in fold.test_pair_ids)
    protocols = (
        "sweep_to_multisine_uncalibrated", "sweep_to_multisine_calibrated",
        "sweep_to_sweep", "multisine_to_multisine",
    )
    predictions: list[CalibratedCrossModePrediction] = []
    metrics: list[CrossModeClassificationMetric] = []
    fit_by_position = tuple(model.tone_fits[index] for index in available_positions)

    def matrix(pairs: Sequence[MatchedModePair], mode: str, calibrated: bool) -> NDArray[np.float64]:
        values = np.vstack([
            artifacts[item.sweep_artifact_id if mode == "sweep" else item.multisine_artifact_id].values[list(selected_indices)]
            for item in pairs
        ])
        if calibrated:
            values = np.column_stack([
                apply_tone_calibration(values[:, index], fit_by_position[index])
                for index in range(values.shape[1])
            ])
        return values

    y_train = np.asarray([item.direction_angle_deg for item in train_pairs], dtype=float)
    y_test = np.asarray([item.direction_angle_deg for item in test_pairs], dtype=float)
    for protocol in protocols:
        train_mode = "multisine" if protocol == "multisine_to_multisine" else "sweep"
        test_mode = "sweep" if protocol == "sweep_to_sweep" else "multisine"
        calibrated = protocol == "sweep_to_multisine_calibrated"
        x_train = matrix(train_pairs, train_mode, False)
        x_test = matrix(test_pairs, test_mode, calibrated)
        for classifier in model_ids:
            reason: str | None = None
            predicted_rows: list[tuple[float, float | None, float, float | None]] = []
            if not np.all(np.isfinite(x_train)) or not np.all(np.isfinite(x_test)):
                reason = "classification_feature_missing"
            elif set(y_train) != set(direction_order):
                reason = "training_direction_coverage_incomplete"
            else:
                try:
                    predicted_rows = predict_direction_fold(
                        classifier, x_train, y_train, x_test, direction_order, random_state
                    )
                except (ValueError, RuntimeError) as exc:
                    reason = str(exc)
            if reason is not None:
                predicted_rows = [
                    (float("nan"), None, 0.0, None) for _ in test_pairs
                ]
            for pair, predicted in zip(test_pairs, predicted_rows, strict=True):
                predictions.append(CalibratedCrossModePrediction(
                    P9C_SCHEMA_VERSION, fold.outer_fold_id, model.method, protocol,
                    classifier, pair.match_pair_id,
                    pair.sweep_artifact_id if test_mode == "sweep" else pair.multisine_artifact_id,
                    pair.direction_angle_deg, predicted[0], predicted[1], predicted[2], predicted[3],
                    True, None, len(selected_indices), fold.training_pair_ids, fold.test_pair_ids,
                ))
            if reason is not None:
                for pair in test_pairs:
                    predictions.append(CalibratedCrossModePrediction(
                        P9C_SCHEMA_VERSION, fold.outer_fold_id, model.method, protocol,
                        classifier, pair.match_pair_id,
                        pair.sweep_artifact_id if test_mode == "sweep" else pair.multisine_artifact_id,
                        pair.direction_angle_deg, None, None, None, None, False, reason,
                        len(selected_indices), fold.training_pair_ids, fold.test_pair_ids,
                    ))
                metrics.append(CrossModeClassificationMetric(
                    P9C_SCHEMA_VERSION, fold.outer_fold_id, model.method, protocol, classifier,
                    False, None, None, 0.0, (), (), len(test_pairs), reason,
                ))
                continue
            summary = summarize_direction_predictions(
                y_test, [item[0] for item in predicted_rows], direction_order,
                total_prediction_count=len(test_pairs),
            )
            coverage = len(predicted_rows) / len(test_pairs) if test_pairs else 0.0
            available = coverage >= float(config["minimum_prediction_coverage"])
            metrics.append(CrossModeClassificationMetric(
                P9C_SCHEMA_VERSION, fold.outer_fold_id, model.method, protocol, classifier,
                available, summary.balanced_accuracy if available else None,
                summary.macro_f1 if available else None, coverage,
                summary.confusion_matrix if available else (),
                summary.per_class_metrics if available else (), len(test_pairs),
                None if available else "prediction_coverage_below_minimum",
            ))
    return tuple(predictions), tuple(metrics)


def analyze_cross_mode_bridge(
    artifacts: Mapping[str, FeatureSet],
    scope: P9CrossModeBridgeScope,
    config: Mapping[str, Any],
) -> P9CrossModeBridgeResult:
    """Evaluate preregistered calibration arms with fold-local fitting only."""
    absolute_reasons = _validate_pair_feature_contracts(artifacts, scope)
    pair_by_id = {item.match_pair_id: item for item in scope.pairs}
    direction_order = scope.direction_order_deg or tuple(sorted({item.direction_angle_deg for item in scope.pairs}))
    config_hash = _canonical_sha256(dict(config))
    models: list[CrossModeCalibrationModel] = []
    tone_rows: list[CrossModeToneComparison] = []
    template_rows: list[DirectionTemplateComparison] = []
    prediction_rows: list[CalibratedCrossModePrediction] = []
    metric_rows: list[CrossModeClassificationMetric] = []
    fold_rows: list[CrossModeFoldEvaluation] = []
    for fold in scope.outer_folds:
        if not fold.ordered_tone_source_indices:
            raise CrossModeBridgeInputError("fold lacks exact P9-B tone source indices")
        indices = fold.ordered_tone_source_indices
        train_pairs = tuple(pair_by_id[item] for item in fold.training_pair_ids)
        test_pairs = tuple(pair_by_id[item] for item in fold.test_pair_ids)
        first_sweep = artifacts[train_pairs[0].sweep_artifact_id]
        first_multi = artifacts[train_pairs[0].multisine_artifact_id]
        for method in scope.calibration_methods:
            fits: list[ToneCalibrationFit] = []
            for position, (tone_id, frequency, source_index) in enumerate(zip(
                fold.ordered_tone_ids, fold.ordered_tone_frequencies_hz,
                indices, strict=True,
            )):
                incompatible = tuple(
                    pair.match_pair_id for pair in train_pairs
                    if absolute_reasons[pair.match_pair_id] is not None
                )
                if method != "identity" and incompatible:
                    fit = _unavailable_fit(
                        tone_id, frequency, method, tuple(item.match_pair_id for item in train_pairs),
                        "absolute_comparison_unavailable",
                    )
                else:
                    fit = fit_tone_calibration(
                        tone_id=tone_id, frequency_hz=frequency, method=method,
                        multisine_db=np.asarray([
                            artifacts[item.multisine_artifact_id].values[source_index] for item in train_pairs
                        ]),
                        sweep_db=np.asarray([
                            artifacts[item.sweep_artifact_id].values[source_index] for item in train_pairs
                        ]),
                        training_pair_ids=tuple(item.match_pair_id for item in train_pairs),
                        config=config["fit"],
                    )
                fits.append(fit)
            model = CrossModeCalibrationModel(
                P9C_SCHEMA_VERSION, _canonical_sha256({
                    "scope": scope.sha256, "fold": fold.outer_fold_id,
                    "method": method, "subset": fold.selected_subset_sha256,
                }), fold.outer_fold_id, method, scope.mapping_direction,
                fold.ordered_tone_ids, fold.ordered_tone_frequencies_hz, tuple(fits),
                fold.training_pair_ids, fold.training_membership_sha256,
                fold.test_pair_ids, fold.held_out_physical_state_ids,
                fold.selected_subset_sha256, fold.candidate_universe_sha256,
                fold.p2b_result_sha256, fold.p4b_result_sha256,
                fold.p9a_selection_artifact_sha256, fold.p9b_result_sha256,
                scope.sha256, config_hash, first_multi.source_magnitude_quantity,
                first_sweep.source_magnitude_quantity, "dB",
                first_multi.source_magnitude_reference, first_sweep.source_magnitude_reference,
                first_sweep.normalization_method, scope.calibration_lifecycle,
                scope.approval_status, False, False, False,
            )
            models.append(model)
            comparisons: list[CrossModeToneComparison] = []
            for fit, source_index in zip(model.tone_fits, indices, strict=True):
                comparison = compare_tone_values(
                    outer_fold_id=fold.outer_fold_id,
                    evaluation_pair_ids=fold.test_pair_ids,
                    fit=fit,
                    multisine_db=np.asarray([
                        artifacts[item.multisine_artifact_id].values[source_index] for item in test_pairs
                    ]),
                    sweep_db=np.asarray([
                        artifacts[item.sweep_artifact_id].values[source_index] for item in test_pairs
                    ]),
                )
                comparisons.append(comparison)
                tone_rows.append(comparison)
            fold_rows.append(_fold_evaluation(
                fold,
                method,
                comparisons,
                minimum_common_tones=int(config["evaluation"]["minimum_common_tones"]),
                minimum_pair_coverage=float(config["evaluation"]["minimum_pair_coverage"]),
            ))
            template_rows.extend(_direction_templates(
                artifacts=artifacts, pair_by_id=pair_by_id, fold=fold, model=model,
                indices=indices, direction_order=direction_order,
                minimum_common_tones=int(config["direction_templates"]["minimum_common_tones"]),
            ))
            predictions, metrics = _classification_for_model(
                artifacts=artifacts, pair_by_id=pair_by_id, fold=fold, model=model,
                indices=indices, direction_order=direction_order,
                model_ids=scope.classification_models,
                config=config["classification"], random_state=scope.random_state,
            )
            prediction_rows.extend(predictions)
            metric_rows.extend(metrics)
    warnings = tuple(
        f"{item.outer_fold_id}:{item.method}:{','.join(item.reason_codes)}"
        for item in fold_rows if item.status is not CalibrationStatus.VALID
    )
    if any(item.status is CalibrationStatus.UNAVAILABLE for item in fold_rows):
        processing_status = "completed_with_unavailable"
    elif warnings:
        processing_status = "completed_with_warnings"
    else:
        processing_status = "completed"
    return P9CrossModeBridgeResult(
        P9C_SCHEMA_VERSION,
        processing_status,
        scope.analysis_scope_id, scope.sha256, config_hash,
        "simulated", "software_validation", False, False, False,
        "software_validation_only", "not_approved", False,
        tuple(models), tuple(tone_rows), tuple(template_rows), tuple(prediction_rows),
        tuple(metric_rows), tuple(fold_rows), warnings, (),
    )

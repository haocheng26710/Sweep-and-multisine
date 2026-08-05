"""P4-A metrics over already-constructed FeatureSet objects only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .research_gate import RunPurpose, enforce_research_gate, normalize_run_purpose
from .schemas import FeatureKind, FeatureSet, QCStatus, Representation
from .version import FEATURE_SCHEMA_VERSION


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


class MetricsInputError(ValueError):
    """Raised when P4-A input identity or scope cannot be trusted."""


class ScopeRole(str, Enum):
    DEVELOPMENT = "development"
    TRAINING = "training"
    CALIBRATION = "calibration"
    TEST = "test"
    DESCRIPTIVE = "descriptive"


def frozen_partition_sha256(
    partition_id: str,
    sample_ids: tuple[str, ...],
) -> str:
    encoded = json.dumps(
        {"partition_id": partition_id, "sample_ids": sample_ids},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class FrozenPartition:
    partition_id: str
    sample_ids: tuple[str, ...]
    partition_sha256: str

    def __post_init__(self) -> None:
        if not self.partition_id.strip():
            raise MetricsInputError("partition_id must be non-empty")
        if not self.sample_ids or len(set(self.sample_ids)) != len(self.sample_ids):
            raise MetricsInputError("partition sample IDs must be non-empty and unique")
        expected = frozen_partition_sha256(self.partition_id, self.sample_ids)
        if self.partition_sha256 != expected:
            raise MetricsInputError("partition SHA-256 mismatch")


@dataclass(frozen=True, slots=True)
class SelectionPolicy:
    policy_id: str
    require_human_valid: bool = True
    exclude_manual_review: bool = True


@dataclass(frozen=True, slots=True)
class QCInclusionPolicy:
    policy_id: str
    included_statuses: tuple[QCStatus, ...]
    missing_status: str = "exclude"
    allow_exclude_candidate: bool = False

    def __post_init__(self) -> None:
        if self.missing_status != "exclude":
            raise MetricsInputError("P4-A missing QC status policy must be 'exclude'")
        if (
            QCStatus.EXCLUDE_CANDIDATE in self.included_statuses
            and not self.allow_exclude_candidate
        ):
            raise MetricsInputError(
                "exclude_candidate requires allow_exclude_candidate=true"
            )


@dataclass(frozen=True, slots=True)
class AnalysisScope:
    schema_version: str
    analysis_scope_id: str
    run_purpose: RunPurpose
    scope_role: ScopeRole
    included_sample_ids: tuple[str, ...] | None
    partition: FrozenPartition | None
    direction_order_deg: tuple[float, ...]
    selection_policy: SelectionPolicy
    qc_inclusion_policy: QCInclusionPolicy

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0":
            raise MetricsInputError("analysis scope schema_version must be 1.0.0")
        if not self.analysis_scope_id.strip():
            raise MetricsInputError("analysis_scope_id must be non-empty")
        object.__setattr__(self, "run_purpose", normalize_run_purpose(self.run_purpose))
        if (self.included_sample_ids is None) == (self.partition is None):
            raise MetricsInputError(
                "analysis scope requires exactly one of included_sample_ids or partition"
            )
        sample_ids = self.requested_sample_ids
        if not sample_ids or len(set(sample_ids)) != len(sample_ids):
            raise MetricsInputError("analysis scope sample IDs must be non-empty and unique")
        directions = np.asarray(self.direction_order_deg, dtype=np.float64)
        if (
            directions.size == 0
            or np.any(~np.isfinite(directions))
            or np.any((directions < 0.0) | (directions >= 360.0))
            or np.unique(directions).size != directions.size
        ):
            raise MetricsInputError(
                "direction_order_deg must contain unique finite angles in [0, 360)"
            )

    @property
    def requested_sample_ids(self) -> tuple[str, ...]:
        if self.included_sample_ids is not None:
            return self.included_sample_ids
        assert self.partition is not None
        return self.partition.sample_ids


@dataclass(frozen=True, slots=True)
class SelectionAuditRecord:
    sample_id: str
    requested: bool
    selected: bool
    reasons: tuple[str, ...]
    source_sha256: str
    source_qc_sha256: str | None
    feature_content_sha256: str
    source_qc_eligible_for_downstream: bool | None
    source_qc_status: QCStatus | None
    source_qc_warning_reasons: tuple[str, ...]
    source_qc_exclude_candidate_reasons: tuple[str, ...]
    source_qc_unavailable_checks: tuple[str, ...]
    human_valid: bool
    manual_review_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DirectionTemplate:
    angle_deg: float
    direction_index: int
    sample_ids: tuple[str, ...]
    sample_count: int
    mean_values: FloatArray
    standard_deviation: FloatArray
    standard_deviation_available: bool
    valid_sample_count: NDArray[np.int64]
    session_count: int
    repeat_type_count: int
    reposition_round_count: int
    assembly_count: int
    acquisition_block_count: int


@dataclass(frozen=True, slots=True)
class MetricMatrix:
    metric: str
    angles_deg: tuple[float, ...]
    values: NDArray[np.float64]
    available: NDArray[np.bool_]
    unavailable_reasons: tuple[tuple[str | None, ...], ...]
    feature_count: int


@dataclass(frozen=True, slots=True)
class EffectiveRankResult:
    available: bool
    value: float | None
    singular_values: FloatArray
    proportions: FloatArray
    matrix_shape: tuple[int, int]
    centered: bool
    unavailable_reason: str | None


@dataclass(frozen=True, slots=True)
class PairDistanceRecord:
    pair_id: str
    pair_scope: str
    left_sample_id: str
    right_sample_id: str
    left_angle_deg: float
    right_angle_deg: float
    repeat_type: str | None
    constructed: bool
    unavailable_reason: str | None
    feature_count: int
    distances: Mapping[str, float]
    left_session_id: str | None
    right_session_id: str | None
    left_reposition_round_id: str | None
    right_reposition_round_id: str | None
    left_assembly_id: str | None
    right_assembly_id: str | None
    left_acquisition_block_id: str | None
    right_acquisition_block_id: str | None


@dataclass(frozen=True, slots=True)
class RepeatabilitySummary:
    repeat_type: str
    metric: str
    available: bool
    pair_count: int
    unavailable_candidate_count: int
    median: float | None
    mean: float | None
    standard_deviation: float | None
    interquartile_range: float | None
    minimum: float | None
    maximum: float | None
    unavailable_reason: str | None


@dataclass(frozen=True, slots=True)
class MorphologyGainResult:
    metric: str
    available: bool
    value: float | None
    numerator: float | None
    denominator: float | None
    between_pair_count: int
    reposition_pair_count: int
    minimum_denominator: float
    unavailable_reason: str | None


@dataclass(frozen=True, slots=True)
class MetricsSummary:
    direction_count: int
    sample_count: int
    feature_count: int
    maximum_off_diagonal_pearson: float | None
    mean_off_diagonal_pearson: float | None
    minimum_direction_rms: float | None
    median_direction_rms: float | None
    maximum_direction_rms: float | None
    most_similar_highest_pearson_pair: tuple[float, float] | None
    most_difficult_lowest_rms_pair: tuple[float, float] | None
    unavailable_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DirectionMetricsResult:
    processing_status: str
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    analysis_scope: AnalysisScope
    metrics_config: Mapping[str, Any]
    template_usage: str
    eligible_for_training_dictionary: bool
    tone_selection_allowed: bool
    configuration: str
    feature_kind: str
    preprocessing_id: str
    feature_schema_version: str
    source_representation: str
    data_origin: str
    dataset_role: str
    scientifically_eligible: bool
    tone_set_id: str | None
    tone_set_sha256: str | None
    tone_schema_id: str | None
    dense_frequency_range_hz: tuple[float, float] | None
    feature_names: tuple[str, ...]
    units: tuple[str, ...]
    selected_sample_ids: tuple[str, ...]
    selection_audit: tuple[SelectionAuditRecord, ...]
    common_valid_mask: BoolArray
    common_valid_feature_count: int
    common_valid_feature_fraction: float
    per_sample_missing_count: Mapping[str, int]
    direction_order_deg: tuple[float, ...]
    direction_templates: tuple[DirectionTemplate, ...]
    matrices: Mapping[str, MetricMatrix]
    effective_rank: EffectiveRankResult
    repeatability_pairs: tuple[PairDistanceRecord, ...]
    repeatability_summaries: tuple[RepeatabilitySummary, ...]
    between_direction_pairs: tuple[PairDistanceRecord, ...]
    morphology_gain: MorphologyGainResult
    summary: MetricsSummary


def _metrics_thresholds(
    config: Mapping[str, Any],
) -> tuple[int, float, int, bool, str, str, float]:
    if config.get("schema_version") != "1.0.0":
        raise MetricsInputError("metrics schema_version must be 1.0.0")
    try:
        minimum_features = int(config["minimum_common_valid_features"])
        minimum_fraction = float(config["minimum_common_valid_fraction"])
        minimum_directions = int(config["minimum_direction_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MetricsInputError("metrics common-feature thresholds are invalid") from exc
    if minimum_features < 1 or not 0.0 < minimum_fraction <= 1.0:
        raise MetricsInputError("metrics common-feature thresholds are out of range")
    if minimum_directions < 1:
        raise MetricsInputError("minimum_direction_count must be positive")
    center = config.get("center_direction_matrix")
    if not isinstance(center, bool):
        raise MetricsInputError("center_direction_matrix must be boolean")
    repeat_metric = str(config.get("repeatability_distance_metric", ""))
    gain = config.get("morphology_gain")
    if repeat_metric not in {"euclidean", "rms", "median_absolute_difference"}:
        raise MetricsInputError("repeatability_distance_metric is unsupported")
    if not isinstance(gain, Mapping):
        raise MetricsInputError("morphology_gain config must be a mapping")
    gain_metric = str(gain.get("distance_metric", ""))
    if gain_metric not in {"euclidean", "rms", "median_absolute_difference"}:
        raise MetricsInputError("morphology_gain.distance_metric is unsupported")
    try:
        minimum_denominator = float(gain["minimum_denominator"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MetricsInputError("morphology_gain.minimum_denominator is invalid") from exc
    if not np.isfinite(minimum_denominator) or minimum_denominator <= 0.0:
        raise MetricsInputError("morphology_gain.minimum_denominator must be positive")
    return (
        minimum_features,
        minimum_fraction,
        minimum_directions,
        center,
        repeat_metric,
        gain_metric,
        minimum_denominator,
    )


def feature_set_content_sha256(feature: FeatureSet) -> str:
    """Hash one in-memory FeatureSet without relying on its source artifact path."""
    payload = {
        "sample_id": feature.sample_id,
        "feature_schema_version": feature.feature_schema_version,
        "feature_kind": feature.feature_kind.value,
        "feature_names": feature.feature_names,
        "units": feature.units,
        "source_measurement_mode": feature.source_measurement_mode.value,
        "source_representation": feature.source_representation.value,
        "preprocessing_id": feature.preprocessing_id,
        "tone_set_id": feature.tone_set_id,
        "tone_set_sha256": feature.tone_set_sha256,
        "tone_schema_id": feature.tone_schema_id,
        "normalization_method": feature.normalization_method,
        "source_magnitude_quantity": feature.source_magnitude_quantity,
        "source_magnitude_reference": feature.source_magnitude_reference,
        "source_phase_status": (
            None
            if feature.source_phase_status is None
            else feature.source_phase_status.value
        ),
        "reliability_weight_source": feature.reliability_weight_source,
        "fit_scope_id": feature.fit_scope_id,
        "calibration_id": feature.calibration_id,
        "meta": feature.meta.to_dict(),
        "source_qc_status": (
            None if feature.source_qc_status is None else feature.source_qc_status.value
        ),
        "source_qc_sha256": feature.source_qc_sha256,
        "source_qc_warning_reasons": feature.source_qc_warning_reasons,
        "source_qc_exclude_candidate_reasons": (
            feature.source_qc_exclude_candidate_reasons
        ),
        "source_qc_unavailable_checks": feature.source_qc_unavailable_checks,
        "source_qc_eligible_for_downstream": (
            feature.source_qc_eligible_for_downstream
        ),
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    digest.update(np.asarray(feature.values, dtype="<f8").tobytes())
    digest.update(np.asarray(feature.valid_mask, dtype=np.uint8).tobytes())
    if feature.reliability_weights is not None:
        digest.update(np.asarray(feature.reliability_weights, dtype="<f8").tobytes())
    return f"sha256:{digest.hexdigest()}"


def _selection(
    feature_sets: Sequence[FeatureSet],
    scope: AnalysisScope,
) -> tuple[tuple[FeatureSet, ...], tuple[SelectionAuditRecord, ...]]:
    by_id: dict[str, FeatureSet] = {}
    for feature in feature_sets:
        if not isinstance(feature, FeatureSet):
            raise TypeError("P4-A accepts FeatureSet objects only")
        if feature.sample_id in by_id:
            raise MetricsInputError(f"duplicate FeatureSet sample_id: {feature.sample_id}")
        by_id[feature.sample_id] = feature
    missing = [item for item in scope.requested_sample_ids if item not in by_id]
    if missing:
        raise MetricsInputError(f"analysis scope samples are missing: {missing}")

    requested = set(scope.requested_sample_ids)
    selected_ids: list[str] = []
    audit: list[SelectionAuditRecord] = []
    for sample_id, feature in by_id.items():
        reasons: list[str] = []
        is_requested = sample_id in requested
        if not is_requested:
            reasons.append("not_requested_by_scope")
        if is_requested and scope.selection_policy.require_human_valid and not feature.meta.valid:
            reasons.append("human_valid_false")
        if (
            is_requested
            and scope.selection_policy.exclude_manual_review
            and feature.meta.manual_review_reasons
        ):
            reasons.append("manual_review_present")
        qc_status = feature.source_qc_status
        if is_requested and qc_status is None:
            reasons.append("source_qc_status_missing")
        elif is_requested and qc_status not in scope.qc_inclusion_policy.included_statuses:
            reasons.append(f"qc_status_not_included:{qc_status.value}")
        selected = is_requested and not reasons
        if selected:
            selected_ids.append(sample_id)
        audit.append(
            SelectionAuditRecord(
                sample_id=sample_id,
                requested=is_requested,
                selected=selected,
                reasons=tuple(reasons),
                source_sha256=feature.meta.source_sha256,
                source_qc_sha256=feature.source_qc_sha256,
                feature_content_sha256=feature_set_content_sha256(feature),
                source_qc_eligible_for_downstream=(
                    feature.source_qc_eligible_for_downstream
                ),
                source_qc_status=qc_status,
                source_qc_warning_reasons=feature.source_qc_warning_reasons,
                source_qc_exclude_candidate_reasons=(
                    feature.source_qc_exclude_candidate_reasons
                ),
                source_qc_unavailable_checks=feature.source_qc_unavailable_checks,
                human_valid=feature.meta.valid,
                manual_review_reasons=feature.meta.manual_review_reasons,
            )
        )
    selected_by_id = {item: by_id[item] for item in selected_ids}
    selected = tuple(
        selected_by_id[item]
        for item in scope.requested_sample_ids
        if item in selected_by_id
    )
    if not selected:
        raise MetricsInputError("analysis scope selected no FeatureSet samples")
    return selected, tuple(audit)


def _identity(selected: tuple[FeatureSet, ...]) -> tuple[str, str, str]:
    first = selected[0]
    configuration = first.meta.configuration
    if configuration is None:
        raise MetricsInputError("P4-A requires non-empty configuration metadata")
    if first.feature_schema_version != FEATURE_SCHEMA_VERSION:
        raise MetricsInputError(
            f"P4-A unsupported feature schema {first.feature_schema_version!r}; "
            f"expected {FEATURE_SCHEMA_VERSION!r}"
        )
    tone_kinds = {
        FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
    }
    expected_representations = {
        FeatureKind.DENSE_RAW_SPL: Representation.DENSE_SPECTRUM,
        FeatureKind.DENSE_DEMEANED_DB: Representation.DENSE_SPECTRUM,
        FeatureKind.DENSE_ZSCORE: Representation.DENSE_SPECTRUM,
        FeatureKind.TONE_PROJECTION_FROM_SWEEP: Representation.DENSE_SPECTRUM,
        FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE: Representation.SPARSE_TONES,
    }
    expected_representation = expected_representations.get(first.feature_kind)
    if expected_representation is None:
        raise MetricsInputError(
            f"P4-A unsupported feature_kind {first.feature_kind.value!r}"
        )
    if first.source_representation is not expected_representation:
        raise MetricsInputError(
            "P4-A feature_kind/source_representation combination is invalid"
        )
    for feature in selected[1:]:
        if feature.meta.configuration != configuration:
            raise MetricsInputError("P4-A cannot mix configurations")
        if feature.feature_kind is not first.feature_kind:
            raise MetricsInputError("P4-A cannot mix feature_kind values")
        if feature.preprocessing_id != first.preprocessing_id:
            raise MetricsInputError("P4-A cannot mix preprocessing_id values")
        if feature.feature_schema_version != first.feature_schema_version:
            raise MetricsInputError("P4-A feature schema versions are incompatible")
        if feature.feature_names != first.feature_names:
            raise MetricsInputError("P4-A feature_names/order mismatch")
        if feature.units != first.units:
            raise MetricsInputError("P4-A units mismatch")
        if feature.source_representation is not first.source_representation:
            raise MetricsInputError("P4-A cannot mix source representations")
        if feature.meta.data_origin is not first.meta.data_origin:
            raise MetricsInputError("P4-A cannot mix data origins")
        if feature.meta.dataset_role is not first.meta.dataset_role:
            raise MetricsInputError("P4-A cannot mix dataset roles")
        if first.feature_kind in tone_kinds and (
            feature.tone_set_id != first.tone_set_id
            or feature.tone_set_sha256 != first.tone_set_sha256
            or feature.tone_schema_id != first.tone_schema_id
            or feature.normalization_method != first.normalization_method
        ):
            raise MetricsInputError("P4-A tone-set identity mismatch")
    return configuration, first.feature_kind.value, first.preprocessing_id


def _dense_frequency_range(feature: FeatureSet) -> tuple[float, float] | None:
    if feature.feature_kind in {
        FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
    }:
        return None
    frequencies: list[float] = []
    for name in feature.feature_names:
        if not name.startswith("f_") or not name.endswith("_hz"):
            raise MetricsInputError(
                "dense FeatureSet names must encode frequency as f_<hz>_hz"
            )
        try:
            frequency = float(name[2:-3])
        except ValueError as exc:
            raise MetricsInputError("dense FeatureSet frequency name is invalid") from exc
        frequencies.append(frequency)
    array = np.asarray(frequencies, dtype=np.float64)
    if np.any(~np.isfinite(array)) or np.any(np.diff(array) <= 0.0):
        raise MetricsInputError("dense FeatureSet frequencies must be strictly increasing")
    return float(array[0]), float(array[-1])


def _nonempty_unique(values: Sequence[str | None]) -> int:
    return len({value for value in values if value is not None and value != ""})


def _metric_value(metric: str, left: FloatArray, right: FloatArray) -> tuple[float, str | None]:
    difference = left - right
    if metric == "euclidean":
        return float(np.linalg.norm(difference)), None
    if metric == "rms":
        return float(np.sqrt(np.mean(difference**2))), None
    if metric == "median_absolute_difference":
        return float(np.median(np.abs(difference))), None
    if metric == "cosine":
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        if denominator == 0.0:
            return np.nan, "zero_norm_vector"
        return float(np.dot(left, right) / denominator), None
    if metric == "pearson":
        centered_left = left - np.mean(left)
        centered_right = right - np.mean(right)
        denominator = float(
            np.linalg.norm(centered_left) * np.linalg.norm(centered_right)
        )
        if denominator == 0.0:
            return np.nan, "constant_vector"
        return float(np.dot(centered_left, centered_right) / denominator), None
    raise AssertionError(f"unknown metric: {metric}")


def _metric_matrices(
    templates: tuple[DirectionTemplate, ...],
    common_mask: BoolArray,
) -> Mapping[str, MetricMatrix]:
    metrics = (
        "pearson",
        "cosine",
        "euclidean",
        "rms",
        "median_absolute_difference",
    )
    angles = tuple(template.angle_deg for template in templates)
    feature_count = int(np.count_nonzero(common_mask))
    vectors = tuple(template.mean_values[common_mask] for template in templates)
    result: dict[str, MetricMatrix] = {}
    for metric in metrics:
        values = np.full((len(vectors), len(vectors)), np.nan, dtype=np.float64)
        available = np.zeros(values.shape, dtype=bool)
        reasons: list[list[str | None]] = [
            [None] * len(vectors) for _ in vectors
        ]
        for left_index, left in enumerate(vectors):
            for right_index in range(left_index, len(vectors)):
                value, reason = _metric_value(metric, left, vectors[right_index])
                values[left_index, right_index] = value
                values[right_index, left_index] = value
                is_available = reason is None
                available[left_index, right_index] = is_available
                available[right_index, left_index] = is_available
                reasons[left_index][right_index] = reason
                reasons[right_index][left_index] = reason
        values.setflags(write=False)
        available.setflags(write=False)
        result[metric] = MetricMatrix(
            metric=metric,
            angles_deg=angles,
            values=values,
            available=available,
            unavailable_reasons=tuple(tuple(row) for row in reasons),
            feature_count=feature_count,
        )
    return result


def compute_effective_rank(
    direction_matrix: FloatArray,
    *,
    center_directions: bool,
) -> EffectiveRankResult:
    """Compute entropy effective rank from singular values, never their squares."""
    matrix = np.asarray(direction_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise MetricsInputError("effective-rank matrix must be non-empty and 2-D")
    if np.any(~np.isfinite(matrix)):
        raise MetricsInputError("effective-rank matrix must be finite")
    evaluated = matrix - np.mean(matrix, axis=0) if center_directions else matrix
    singular_values = np.asarray(
        np.linalg.svd(evaluated, compute_uv=False),
        dtype=np.float64,
    )
    total = float(np.sum(singular_values))
    proportions = np.zeros(singular_values.size, dtype=np.float64)
    if total == 0.0:
        value = None
        available = False
        reason = "all_singular_values_zero"
    else:
        proportions = singular_values / total
        positive = proportions > 0.0
        value = float(
            np.exp(-np.sum(proportions[positive] * np.log(proportions[positive])))
        )
        available = True
        reason = None
    singular_values.setflags(write=False)
    proportions.setflags(write=False)
    return EffectiveRankResult(
        available=available,
        value=value,
        singular_values=singular_values,
        proportions=proportions,
        matrix_shape=(int(matrix.shape[0]), int(matrix.shape[1])),
        centered=center_directions,
        unavailable_reason=reason,
    )


def _distance_values(left: FloatArray, right: FloatArray) -> Mapping[str, float]:
    return {
        metric: _metric_value(metric, left, right)[0]
        for metric in ("euclidean", "rms", "median_absolute_difference")
    }


def _pair_record(
    left: FeatureSet,
    right: FeatureSet,
    common_mask: BoolArray,
    *,
    pair_scope: str,
    constructed: bool,
    reason: str | None,
) -> PairDistanceRecord:
    if right.sample_id < left.sample_id:
        left, right = right, left
    feature_count = int(np.count_nonzero(common_mask))
    if constructed and feature_count:
        distances = _distance_values(
            left.values[common_mask],
            right.values[common_mask],
        )
    else:
        distances = {}
        if constructed:
            constructed = False
            reason = "no_common_valid_features"
    return PairDistanceRecord(
        pair_id=f"{left.sample_id}__{right.sample_id}",
        pair_scope=pair_scope,
        left_sample_id=left.sample_id,
        right_sample_id=right.sample_id,
        left_angle_deg=float(left.meta.angle_deg),
        right_angle_deg=float(right.meta.angle_deg),
        repeat_type=left.meta.repeat_type if pair_scope == "within_direction" else None,
        constructed=constructed,
        unavailable_reason=reason,
        feature_count=feature_count,
        distances=distances,
        left_session_id=left.meta.session_id,
        right_session_id=right.meta.session_id,
        left_reposition_round_id=left.meta.reposition_round_id,
        right_reposition_round_id=right.meta.reposition_round_id,
        left_assembly_id=left.meta.assembly_id,
        right_assembly_id=right.meta.assembly_id,
        left_acquisition_block_id=left.meta.acquisition_block_id,
        right_acquisition_block_id=right.meta.acquisition_block_id,
    )


def _same_required(
    left: str | None,
    right: str | None,
    name: str,
) -> str | None:
    if not left or not right:
        return f"missing_{name}"
    if left != right:
        return f"different_{name}"
    return None


def _different_required(
    left: str | None,
    right: str | None,
    name: str,
) -> str | None:
    if not left or not right:
        return f"missing_{name}"
    if left == right:
        return f"same_{name}"
    return None


def _optional_same(
    left: str | None,
    right: str | None,
    name: str,
) -> str | None:
    if left is None and right is None:
        return None
    if not left or not right:
        return f"incomplete_{name}"
    if left != right:
        return f"different_{name}"
    return None


def _repeat_pair_reason(left: FeatureSet, right: FeatureSet) -> str | None:
    repeat_type = left.meta.repeat_type
    if repeat_type != right.meta.repeat_type:
        return "different_repeat_type"
    if left.meta.repeat_id == right.meta.repeat_id:
        return "same_repeat_id"
    if repeat_type == "CONT":
        checks = (
            _same_required(left.meta.session_id, right.meta.session_id, "session_id"),
            _same_required(
                left.meta.acquisition_block_id,
                right.meta.acquisition_block_id,
                "acquisition_block_id",
            ),
            _optional_same(left.meta.assembly_id, right.meta.assembly_id, "assembly_id"),
            _optional_same(
                left.meta.reposition_round_id,
                right.meta.reposition_round_id,
                "reposition_round_id",
            ),
        )
    elif repeat_type == "REPOS":
        checks = (
            _same_required(left.meta.session_id, right.meta.session_id, "session_id"),
            _same_required(left.meta.assembly_id, right.meta.assembly_id, "assembly_id"),
            _different_required(
                left.meta.reposition_round_id,
                right.meta.reposition_round_id,
                "reposition_round_id",
            ),
        )
    elif repeat_type == "REASM":
        checks = (
            _same_required(left.meta.session_id, right.meta.session_id, "session_id"),
            _different_required(left.meta.assembly_id, right.meta.assembly_id, "assembly_id"),
        )
    else:
        return "unsupported_repeat_type"
    return next((item for item in checks if item is not None), None)


def _repeatability_pairs(
    selected: tuple[FeatureSet, ...],
    common_mask: BoolArray,
) -> tuple[PairDistanceRecord, ...]:
    records: list[PairDistanceRecord] = []
    ordered = tuple(sorted(selected, key=lambda feature: feature.sample_id))
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            if left.meta.angle_deg != right.meta.angle_deg:
                continue
            if left.meta.repeat_type != right.meta.repeat_type:
                continue
            reason = _repeat_pair_reason(left, right)
            records.append(
                _pair_record(
                    left,
                    right,
                    common_mask,
                    pair_scope="within_direction",
                    constructed=reason is None,
                    reason=reason,
                )
            )
    return tuple(records)


def _between_direction_pairs(
    selected: tuple[FeatureSet, ...],
    common_mask: BoolArray,
) -> tuple[PairDistanceRecord, ...]:
    records: list[PairDistanceRecord] = []
    ordered = tuple(sorted(selected, key=lambda feature: feature.sample_id))
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            if left.meta.angle_deg == right.meta.angle_deg:
                continue
            records.append(
                _pair_record(
                    left,
                    right,
                    common_mask,
                    pair_scope="between_direction_sample_pair",
                    constructed=True,
                    reason=None,
                )
            )
    return tuple(records)


def _repeat_summaries(
    pairs: tuple[PairDistanceRecord, ...],
    metric: str,
) -> tuple[RepeatabilitySummary, ...]:
    summaries: list[RepeatabilitySummary] = []
    for repeat_type in ("CONT", "REPOS", "REASM"):
        candidates = tuple(pair for pair in pairs if pair.repeat_type == repeat_type)
        values = np.asarray(
            [pair.distances[metric] for pair in candidates if pair.constructed],
            dtype=np.float64,
        )
        unavailable_count = sum(not pair.constructed for pair in candidates)
        if values.size == 0:
            summaries.append(
                RepeatabilitySummary(
                    repeat_type=repeat_type,
                    metric=metric,
                    available=False,
                    pair_count=0,
                    unavailable_candidate_count=unavailable_count,
                    median=None,
                    mean=None,
                    standard_deviation=None,
                    interquartile_range=None,
                    minimum=None,
                    maximum=None,
                    unavailable_reason="no_constructed_pairs",
                )
            )
            continue
        quartiles = np.percentile(values, [25.0, 75.0], method="linear")
        summaries.append(
            RepeatabilitySummary(
                repeat_type=repeat_type,
                metric=metric,
                available=True,
                pair_count=int(values.size),
                unavailable_candidate_count=unavailable_count,
                median=float(np.median(values)),
                mean=float(np.mean(values)),
                standard_deviation=(
                    float(np.std(values, ddof=1)) if values.size >= 2 else None
                ),
                interquartile_range=float(quartiles[1] - quartiles[0]),
                minimum=float(np.min(values)),
                maximum=float(np.max(values)),
                unavailable_reason=None,
            )
        )
    return tuple(summaries)


def _morphology_gain(
    repeat_pairs: tuple[PairDistanceRecord, ...],
    between_pairs: tuple[PairDistanceRecord, ...],
    *,
    metric: str,
    minimum_denominator: float,
) -> MorphologyGainResult:
    between_values = np.asarray(
        [pair.distances[metric] for pair in between_pairs if pair.constructed],
        dtype=np.float64,
    )
    reposition_values = np.asarray(
        [
            pair.distances[metric]
            for pair in repeat_pairs
            if pair.constructed and pair.repeat_type == "REPOS"
        ],
        dtype=np.float64,
    )
    numerator = float(np.median(between_values)) if between_values.size else None
    denominator = (
        float(np.median(reposition_values)) if reposition_values.size else None
    )
    if numerator is None:
        reason = "between_direction_pairs_unavailable"
    elif denominator is None:
        reason = "reposition_pairs_unavailable"
    elif denominator < minimum_denominator:
        reason = "reposition_denominator_below_minimum"
    else:
        reason = None
    return MorphologyGainResult(
        metric=metric,
        available=reason is None,
        value=None if reason else numerator / denominator,
        numerator=numerator,
        denominator=denominator,
        between_pair_count=int(between_values.size),
        reposition_pair_count=int(reposition_values.size),
        minimum_denominator=minimum_denominator,
        unavailable_reason=reason,
    )


def _metrics_summary(
    matrices: Mapping[str, MetricMatrix],
    *,
    sample_count: int,
    feature_count: int,
) -> MetricsSummary:
    pearson = matrices["pearson"]
    rms = matrices["rms"]
    pearson_values: list[float] = []
    rms_values: list[float] = []
    maximum_pearson: float | None = None
    minimum_rms: float | None = None
    maximum_pair: tuple[float, float] | None = None
    minimum_pair: tuple[float, float] | None = None
    for left in range(len(pearson.angles_deg)):
        for right in range(left + 1, len(pearson.angles_deg)):
            pair = (pearson.angles_deg[left], pearson.angles_deg[right])
            if pearson.available[left, right]:
                value = float(pearson.values[left, right])
                pearson_values.append(value)
                if maximum_pearson is None or value > maximum_pearson:
                    maximum_pearson = value
                    maximum_pair = pair
            if rms.available[left, right]:
                value = float(rms.values[left, right])
                rms_values.append(value)
                if minimum_rms is None or value < minimum_rms:
                    minimum_rms = value
                    minimum_pair = pair
    unavailable: list[str] = []
    if not pearson_values:
        unavailable.append("off_diagonal_pearson_unavailable")
    if not rms_values:
        unavailable.append("off_diagonal_rms_unavailable")
    return MetricsSummary(
        direction_count=len(pearson.angles_deg),
        sample_count=sample_count,
        feature_count=feature_count,
        maximum_off_diagonal_pearson=maximum_pearson,
        mean_off_diagonal_pearson=(
            float(np.mean(pearson_values)) if pearson_values else None
        ),
        minimum_direction_rms=minimum_rms,
        median_direction_rms=(
            float(np.median(rms_values)) if rms_values else None
        ),
        maximum_direction_rms=(
            float(np.max(rms_values)) if rms_values else None
        ),
        most_similar_highest_pearson_pair=maximum_pair,
        most_difficult_lowest_rms_pair=minimum_pair,
        unavailable_reasons=tuple(unavailable),
    )


def analyze_direction_feature_sets(
    feature_sets: Sequence[FeatureSet],
    analysis_scope: AnalysisScope,
    metrics_config: Mapping[str, Any],
) -> DirectionMetricsResult:
    """Select and summarize one compatible, explicit FeatureSet analysis scope."""
    (
        minimum_features,
        minimum_fraction,
        minimum_directions,
        center_direction_matrix,
        repeatability_metric,
        gain_metric,
        gain_minimum_denominator,
    ) = _metrics_thresholds(metrics_config)
    selected, audit = _selection(feature_sets, analysis_scope)
    enforce_research_gate(
        analysis_scope.run_purpose,
        (feature.meta for feature in selected),
    )
    configuration, feature_kind, preprocessing_id = _identity(selected)
    first = selected[0]
    masks = np.stack([feature.valid_mask for feature in selected])
    common = np.logical_and.reduce(masks, axis=0)
    common = np.asarray(common, dtype=bool)
    common.setflags(write=False)
    common_count = int(np.count_nonzero(common))
    common_fraction = common_count / common.size
    failures: list[str] = []
    if common_count < minimum_features:
        failures.append(
            f"common valid feature count {common_count} is below {minimum_features}"
        )
    if common_fraction + 1.0e-12 < minimum_fraction:
        failures.append(
            f"common valid feature fraction {common_fraction:g} is below {minimum_fraction:g}"
        )

    expected = analysis_scope.direction_order_deg
    unexpected = sorted(
        {
            float(feature.meta.angle_deg)
            for feature in selected
            if feature.meta.angle_deg not in expected
        }
    )
    if unexpected:
        raise MetricsInputError(f"selected samples contain unexpected directions: {unexpected}")
    templates: list[DirectionTemplate] = []
    warnings: list[str] = []
    for direction_index, angle in enumerate(expected):
        members = tuple(
            feature for feature in selected if feature.meta.angle_deg == angle
        )
        if not members:
            warnings.append(f"direction {angle:g} deg is missing")
            continue
        matrix = np.stack([feature.values for feature in members])
        means = np.full(first.values.size, np.nan, dtype=np.float64)
        means[common] = np.mean(matrix[:, common], axis=0)
        std = np.full(first.values.size, np.nan, dtype=np.float64)
        std_available = len(members) >= 2
        if std_available:
            std[common] = np.std(matrix[:, common], axis=0, ddof=1)
        counts = np.zeros(first.values.size, dtype=np.int64)
        counts[common] = len(members)
        for array in (means, std, counts):
            array.setflags(write=False)
        templates.append(
            DirectionTemplate(
                angle_deg=angle,
                direction_index=direction_index,
                sample_ids=tuple(feature.sample_id for feature in members),
                sample_count=len(members),
                mean_values=means,
                standard_deviation=std,
                standard_deviation_available=std_available,
                valid_sample_count=counts,
                session_count=_nonempty_unique(
                    [feature.meta.session_id for feature in members]
                ),
                repeat_type_count=_nonempty_unique(
                    [feature.meta.repeat_type for feature in members]
                ),
                reposition_round_count=_nonempty_unique(
                    [feature.meta.reposition_round_id for feature in members]
                ),
                assembly_count=_nonempty_unique(
                    [feature.meta.assembly_id for feature in members]
                ),
                acquisition_block_count=_nonempty_unique(
                    [feature.meta.acquisition_block_id for feature in members]
                ),
            )
        )
    if len(templates) < minimum_directions:
        failures.append(
            f"direction count {len(templates)} is below {minimum_directions}"
        )
    template_tuple = tuple(templates)
    if common_count and template_tuple:
        direction_matrix = np.stack(
            [template.mean_values[common] for template in template_tuple]
        )
        effective_rank = compute_effective_rank(
            direction_matrix,
            center_directions=center_direction_matrix,
        )
    else:
        empty_values = np.asarray([], dtype=np.float64)
        empty_values.setflags(write=False)
        effective_rank = EffectiveRankResult(
            available=False,
            value=None,
            singular_values=empty_values,
            proportions=empty_values,
            matrix_shape=(len(template_tuple), common_count),
            centered=center_direction_matrix,
            unavailable_reason="no_common_direction_matrix",
        )
    repeat_pairs = _repeatability_pairs(selected, common)
    between_pairs = _between_direction_pairs(selected, common)
    matrices = _metric_matrices(template_tuple, common)
    return DirectionMetricsResult(
        processing_status="failed" if failures else "completed",
        failures=tuple(failures),
        warnings=tuple(warnings),
        analysis_scope=analysis_scope,
        metrics_config=dict(metrics_config),
        template_usage="descriptive_only",
        eligible_for_training_dictionary=False,
        tone_selection_allowed=False,
        configuration=configuration,
        feature_kind=feature_kind,
        preprocessing_id=preprocessing_id,
        feature_schema_version=first.feature_schema_version,
        source_representation=first.source_representation.value,
        data_origin=first.meta.data_origin.value,
        dataset_role=first.meta.dataset_role.value,
        scientifically_eligible=all(
            feature.meta.eligible_for_scientific_analysis for feature in selected
        ),
        tone_set_id=first.tone_set_id,
        tone_set_sha256=first.tone_set_sha256,
        tone_schema_id=first.tone_schema_id,
        dense_frequency_range_hz=_dense_frequency_range(first),
        feature_names=first.feature_names,
        units=first.units,
        selected_sample_ids=tuple(feature.sample_id for feature in selected),
        selection_audit=audit,
        common_valid_mask=common,
        common_valid_feature_count=common_count,
        common_valid_feature_fraction=common_fraction,
        per_sample_missing_count={
            feature.sample_id: int(np.count_nonzero(~feature.valid_mask))
            for feature in selected
        },
        direction_order_deg=expected,
        direction_templates=template_tuple,
        matrices=matrices,
        effective_rank=effective_rank,
        repeatability_pairs=repeat_pairs,
        repeatability_summaries=_repeat_summaries(
            repeat_pairs,
            repeatability_metric,
        ),
        between_direction_pairs=between_pairs,
        morphology_gain=_morphology_gain(
            repeat_pairs,
            between_pairs,
            metric=gain_metric,
            minimum_denominator=gain_minimum_denominator,
        ),
        summary=_metrics_summary(
            matrices,
            sample_count=len(selected),
            feature_count=common_count,
        ),
    )

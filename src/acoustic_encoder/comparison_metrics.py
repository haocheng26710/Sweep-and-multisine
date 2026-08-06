"""P4-B band, configuration, and cross-mode metrics over FeatureSet artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import itertools
import json
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .metrics import (
    AnalysisScope,
    AnalysisTier,
    DirectionMetricsResult,
    FrozenPartition,
    QCInclusionPolicy,
    ScopeRole,
    SelectionPolicy,
    analyze_direction_feature_sets,
    compute_vector_metric,
    repeat_pair_unavailable_reason,
)
from .dataset_quality_control import (
    CohortRole,
    DatasetQCInputError,
    DatasetQCReference,
    DatasetQCResult,
    feature_contract_sha256,
    feature_set_content_sha256,
    validate_dataset_qc_reference,
)
from .schemas import FeatureKind, FeatureSet, MeasurementMode
from .schemas import QCStatus
from .research_gate import RunPurpose
from .tone_features import ToneFeatureConstructionError, assert_matched_tone_schema
from .feature_axis import FeatureAxisError, feature_frequencies_hz as _shared_feature_frequencies_hz


BandBoundary = Literal[
    "closed",
    "left_closed_right_open",
    "left_open_right_closed",
    "open",
]


class ComparisonMetricsInputError(ValueError):
    """Raised when an explicit P4-B comparison contract cannot be trusted."""


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def feature_frequencies_hz(feature_names: tuple[str, ...]) -> NDArray[np.float64]:
    """Parse only the two authoritative P3 dense/tone feature-name formats."""
    try:
        return _shared_feature_frequencies_hz(feature_names)
    except FeatureAxisError as exc:
        raise ComparisonMetricsInputError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class FrequencyBand:
    band_id: str
    f_min_hz: float
    f_max_hz: float
    boundary: BandBoundary
    minimum_feature_count: int

    def __post_init__(self) -> None:
        if not self.band_id.strip():
            raise ComparisonMetricsInputError("frequency band_id must be non-empty")
        if not (
            np.isfinite(self.f_min_hz)
            and np.isfinite(self.f_max_hz)
            and self.f_min_hz >= 0.0
            and self.f_min_hz < self.f_max_hz
        ):
            raise ComparisonMetricsInputError(
                "frequency band bounds must be finite and increasing"
            )
        if self.boundary not in {
            "closed",
            "left_closed_right_open",
            "left_open_right_closed",
            "open",
        }:
            raise ComparisonMetricsInputError("frequency band boundary is unsupported")
        if (
            isinstance(self.minimum_feature_count, bool)
            or not isinstance(self.minimum_feature_count, int)
            or self.minimum_feature_count < 1
        ):
            raise ComparisonMetricsInputError(
                "frequency band minimum_feature_count must be an integer >= 1"
            )


def frequency_band_mask(
    frequency_hz: NDArray[np.float64],
    band: FrequencyBand,
) -> NDArray[np.bool_]:
    """Return the configured analytic band membership without snapping or selection."""
    frequencies = np.asarray(frequency_hz, dtype=np.float64)
    if frequencies.ndim != 1 or np.any(~np.isfinite(frequencies)):
        raise ComparisonMetricsInputError("frequency_hz must be finite and one-dimensional")
    if band.boundary in {"closed", "left_closed_right_open"}:
        lower = frequencies >= band.f_min_hz
    else:
        lower = frequencies > band.f_min_hz
    if band.boundary in {"closed", "left_open_right_closed"}:
        upper = frequencies <= band.f_max_hz
    else:
        upper = frequencies < band.f_max_hz
    mask = np.asarray(lower & upper, dtype=bool)
    mask.setflags(write=False)
    return mask


@dataclass(frozen=True, slots=True)
class BandDirectionPairResult:
    band_id: str
    configuration_id: str
    feature_kind: str
    left_direction_deg: float
    right_direction_deg: float
    feature_count: int
    pearson: float | None
    cosine: float | None
    euclidean: float | None
    rms: float | None
    median_absolute_difference: float | None
    unavailable_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BandMetricResult:
    band_id: str
    configuration_id: str
    feature_kind: str
    preprocessing_id: str
    f_min_hz: float
    f_max_hz: float
    boundary: BandBoundary
    minimum_feature_count: int
    feature_count: int
    available: bool
    unavailable_reason: str | None
    maximum_off_diagonal_pearson: float | None
    mean_off_diagonal_pearson: float | None
    most_similar_direction_pair: tuple[float, float] | None
    most_difficult_direction_pair: tuple[float, float] | None
    effective_rank: float | None
    morphology_gain: float | None
    morphology_gain_unavailable_reason: str | None
    within_cont_median: float | None
    within_repos_median: float | None
    within_reasm_median: float | None
    between_direction_median: float | None
    direction_pairs: tuple[BandDirectionPairResult, ...]


@dataclass(frozen=True, slots=True)
class CrossModePairSpec:
    match_pair_id: str
    sweep_artifact_id: str
    multisine_artifact_id: str
    direction_id: str
    direction_angle_deg: float
    configuration_id: str
    physical_state_id: str
    session_id: str | None
    repeat_type: str | None
    repeat_id: str | None
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str | None
    cohort_role: CohortRole

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_role", CohortRole(self.cohort_role))
        for name in (
            "match_pair_id",
            "sweep_artifact_id",
            "multisine_artifact_id",
            "direction_id",
            "configuration_id",
            "physical_state_id",
        ):
            if not str(getattr(self, name)).strip():
                raise ComparisonMetricsInputError(f"cross-mode {name} is required")
        if not np.isfinite(self.direction_angle_deg) or not (
            0.0 <= self.direction_angle_deg < 360.0
        ):
            raise ComparisonMetricsInputError(
                "cross-mode direction_angle_deg must be in [0, 360)"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_pair_id": self.match_pair_id,
            "sweep_artifact_id": self.sweep_artifact_id,
            "multisine_artifact_id": self.multisine_artifact_id,
            "direction_id": self.direction_id,
            "direction_angle_deg": self.direction_angle_deg,
            "configuration_id": self.configuration_id,
            "physical_state_id": self.physical_state_id,
            "session_id": self.session_id,
            "repeat_type": self.repeat_type,
            "repeat_id": self.repeat_id,
            "reposition_round_id": self.reposition_round_id,
            "assembly_id": self.assembly_id,
            "acquisition_block_id": self.acquisition_block_id,
            "cohort_role": self.cohort_role.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModePairSpec":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ScopedMeasurementContext:
    sample_id: str
    cohort_role: CohortRole
    direction_id: str
    physical_state_id: str
    selection_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_role", CohortRole(self.cohort_role))
        if any(
            not str(value).strip()
            for value in (
                self.sample_id,
                self.direction_id,
                self.physical_state_id,
                self.selection_reason,
            )
        ):
            raise ComparisonMetricsInputError(
                "comparison measurement context fields must be non-empty"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "sample_id": self.sample_id,
            "cohort_role": self.cohort_role.value,
            "direction_id": self.direction_id,
            "physical_state_id": self.physical_state_id,
            "selection_reason": self.selection_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ScopedMeasurementContext":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ScopedFeatureReference:
    artifact_id: str
    sample_id: str
    feature_kind: str
    preprocessing_id: str
    feature_content_sha256: str
    primary_for_dataset_qc: bool

    def __post_init__(self) -> None:
        if any(
            not str(value).strip()
            for value in (
                self.artifact_id,
                self.sample_id,
                self.feature_kind,
                self.preprocessing_id,
                self.feature_content_sha256,
            )
        ):
            raise ComparisonMetricsInputError(
                "comparison FeatureSet reference fields must be non-empty"
            )
        try:
            FeatureKind(self.feature_kind)
        except ValueError as exc:
            raise ComparisonMetricsInputError(
                "comparison FeatureSet reference has unsupported FeatureKind"
            ) from exc
        digest = self.feature_content_sha256.removeprefix("sha256:")
        if (
            not self.feature_content_sha256.startswith("sha256:")
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ComparisonMetricsInputError(
                "comparison FeatureSet content hash must be sha256:<digest>"
            )

    @classmethod
    def from_feature_set(
        cls,
        artifact_id: str,
        feature: FeatureSet,
        *,
        primary_for_dataset_qc: bool,
    ) -> "ScopedFeatureReference":
        return cls(
            artifact_id=artifact_id,
            sample_id=feature.sample_id,
            feature_kind=feature.feature_kind.value,
            preprocessing_id=feature.preprocessing_id,
            feature_content_sha256=feature_set_content_sha256(feature),
            primary_for_dataset_qc=primary_for_dataset_qc,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "sample_id": self.sample_id,
            "feature_kind": self.feature_kind,
            "preprocessing_id": self.preprocessing_id,
            "feature_content_sha256": self.feature_content_sha256,
            "primary_for_dataset_qc": self.primary_for_dataset_qc,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ScopedFeatureReference":
        return cls(**dict(payload))


def _analysis_scope_payload(scope: AnalysisScope) -> dict[str, Any]:
    return {
        "schema_version": scope.schema_version,
        "analysis_scope_id": scope.analysis_scope_id,
        "run_purpose": scope.run_purpose.value,
        "scope_role": scope.scope_role.value,
        "included_sample_ids": (
            None if scope.included_sample_ids is None else list(scope.included_sample_ids)
        ),
        "partition": (
            None
            if scope.partition is None
            else {
                "partition_id": scope.partition.partition_id,
                "sample_ids": list(scope.partition.sample_ids),
                "partition_sha256": scope.partition.partition_sha256,
            }
        ),
        "direction_order_deg": list(scope.direction_order_deg),
        "selection_policy": {
            "policy_id": scope.selection_policy.policy_id,
            "require_human_valid": scope.selection_policy.require_human_valid,
            "exclude_manual_review": scope.selection_policy.exclude_manual_review,
        },
        "qc_inclusion_policy": {
            "policy_id": scope.qc_inclusion_policy.policy_id,
            "included_statuses": [
                item.value for item in scope.qc_inclusion_policy.included_statuses
            ],
            "missing_status": scope.qc_inclusion_policy.missing_status,
            "allow_exclude_candidate": scope.qc_inclusion_policy.allow_exclude_candidate,
        },
        "analysis_tier": scope.analysis_tier.value,
        "dataset_qc_reference": (
            None
            if scope.dataset_qc_reference is None
            else scope.dataset_qc_reference.to_dict()
        ),
    }


def _analysis_scope_from_payload(payload: Mapping[str, Any]) -> AnalysisScope:
    partition_payload = payload.get("partition")
    partition = (
        None
        if partition_payload is None
        else FrozenPartition(
            partition_id=str(partition_payload["partition_id"]),
            sample_ids=tuple(str(item) for item in partition_payload["sample_ids"]),
            partition_sha256=str(partition_payload["partition_sha256"]),
        )
    )
    reference_payload = payload.get("dataset_qc_reference")
    reference = (
        None
        if reference_payload is None
        else DatasetQCReference(
            analysis_scope_id=str(reference_payload["analysis_scope_id"]),
            dataset_qc_result_sha256=str(
                reference_payload["dataset_qc_result_sha256"]
            ),
        )
    )
    selection = payload["selection_policy"]
    qc = payload["qc_inclusion_policy"]
    included = payload.get("included_sample_ids")
    return AnalysisScope(
        schema_version=str(payload["schema_version"]),
        analysis_scope_id=str(payload["analysis_scope_id"]),
        run_purpose=RunPurpose(payload["run_purpose"]),
        scope_role=ScopeRole(payload["scope_role"]),
        included_sample_ids=(
            None if included is None else tuple(str(item) for item in included)
        ),
        partition=partition,
        direction_order_deg=tuple(float(item) for item in payload["direction_order_deg"]),
        selection_policy=SelectionPolicy(
            policy_id=str(selection["policy_id"]),
            require_human_valid=bool(selection["require_human_valid"]),
            exclude_manual_review=bool(selection["exclude_manual_review"]),
        ),
        qc_inclusion_policy=QCInclusionPolicy(
            policy_id=str(qc["policy_id"]),
            included_statuses=tuple(QCStatus(item) for item in qc["included_statuses"]),
            missing_status=str(qc["missing_status"]),
            allow_exclude_candidate=bool(qc["allow_exclude_candidate"]),
        ),
        analysis_tier=AnalysisTier(payload["analysis_tier"]),
        dataset_qc_reference=reference,
    )


@dataclass(frozen=True, slots=True)
class ComparisonAnalysisScope:
    schema_version: str
    analysis_scope: AnalysisScope
    measurements: tuple[ScopedMeasurementContext, ...]
    feature_references: tuple[ScopedFeatureReference, ...]
    cross_mode_pairs: tuple[CrossModePairSpec, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0":
            raise ComparisonMetricsInputError(
                "ComparisonAnalysisScope schema_version must be 1.0.0"
            )
        sample_ids = tuple(item.sample_id for item in self.measurements)
        if sample_ids != self.analysis_scope.requested_sample_ids:
            raise ComparisonMetricsInputError(
                "comparison measurement order must exactly match AnalysisScope"
            )
        if len(set(sample_ids)) != len(sample_ids):
            raise ComparisonMetricsInputError("comparison measurement IDs must be unique")
        artifact_ids = [item.artifact_id for item in self.feature_references]
        if not artifact_ids or len(set(artifact_ids)) != len(artifact_ids):
            raise ComparisonMetricsInputError(
                "comparison feature artifact IDs must be non-empty and unique"
            )
        if any(item.sample_id not in set(sample_ids) for item in self.feature_references):
            raise ComparisonMetricsInputError(
                "comparison FeatureSet references an out-of-scope measurement"
            )
        known_artifacts = set(artifact_ids)
        if any(
            pair.sweep_artifact_id not in known_artifacts
            or pair.multisine_artifact_id not in known_artifacts
            for pair in self.cross_mode_pairs
        ):
            raise ComparisonMetricsInputError(
                "comparison cross-mode pair references an unknown artifact"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_scope": _analysis_scope_payload(self.analysis_scope),
            "measurements": [item.to_dict() for item in self.measurements],
            "feature_references": [item.to_dict() for item in self.feature_references],
            "cross_mode_pairs": [item.to_dict() for item in self.cross_mode_pairs],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComparisonAnalysisScope":
        required = {
            "schema_version",
            "analysis_scope",
            "measurements",
            "feature_references",
            "cross_mode_pairs",
        }
        if set(payload) != required:
            raise ComparisonMetricsInputError(
                "ComparisonAnalysisScope fields must be explicit"
            )
        return cls(
            schema_version=str(payload["schema_version"]),
            analysis_scope=_analysis_scope_from_payload(payload["analysis_scope"]),
            measurements=tuple(
                ScopedMeasurementContext.from_dict(item)
                for item in payload["measurements"]
            ),
            feature_references=tuple(
                ScopedFeatureReference.from_dict(item)
                for item in payload["feature_references"]
            ),
            cross_mode_pairs=tuple(
                CrossModePairSpec.from_dict(item) for item in payload["cross_mode_pairs"]
            ),
        )

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class CrossModePairMetric:
    match_pair_id: str
    sweep_artifact_id: str
    multisine_artifact_id: str
    direction_id: str
    direction_angle_deg: float
    configuration_id: str
    physical_state_id: str
    cohort_role: CohortRole
    common_tone_count: int
    missing_tone_count: int
    absolute_comparison_available: bool
    absolute_unavailable_reason: str | None
    shape_comparison_available: bool
    shape_unavailable_reason: str | None
    pearson_correlation: float | None
    cosine_similarity: float | None
    rms_difference_db: float | None
    euclidean_distance_db: float | None
    median_absolute_difference_db: float | None
    mean_bias_db: float | None
    median_bias_db: float | None
    centered_rms_db: float | None
    centered_cosine_similarity: float | None


@dataclass(frozen=True, slots=True)
class PerToneBiasResult:
    tone_index: int
    frequency_hz: float
    mean_bias_db: float | None
    median_bias_db: float | None
    sample_standard_deviation_db: float | None
    median_absolute_deviation_db: float | None
    interquartile_range_db: float | None
    pair_count: int
    direction_count: int
    missing_count: int
    absolute_comparison_status: str
    unavailable_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CrossModeMetricsResult:
    common_valid_mask: NDArray[np.bool_]
    total_tone_count: int
    common_tone_count: int
    missing_tone_count: int
    tone_set_id: str
    tone_set_sha256: str
    tone_schema_id: str
    pairs: tuple[CrossModePairMetric, ...]
    per_tone_bias: tuple[PerToneBiasResult, ...]


@dataclass(frozen=True, slots=True)
class ToneReliabilityResult:
    available: bool
    unavailable_reason: str | None
    repeat_type: str
    source_roles: tuple[CohortRole, ...]
    floor_db: float
    maximum_raw_weight: float
    normalization: str
    minimum_pairs_per_tone: int
    minimum_available_tones: int
    frequencies_hz: NDArray[np.float64]
    stability_db: NDArray[np.float64]
    raw_weights: NDArray[np.float64]
    clipped_weights: NDArray[np.float64]
    normalized_weights: NDArray[np.float64]
    pair_counts: NDArray[np.int64]
    available_mask: NDArray[np.bool_]
    pair_ids_by_tone: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class WeightedDistanceResult:
    feature_count: int
    weight_sum: float
    weighted_rms: float
    weighted_euclidean: float


@dataclass(frozen=True, slots=True)
class ConfigurationComparisonResult:
    band_id: str
    feature_kind: str
    metric_id: str
    baseline_configuration: str
    candidate_configuration: str
    baseline_value: float | None
    candidate_value: float | None
    delta: float | None
    ratio: float | None
    available: bool
    unavailable_reason: str | None
    ratio_unavailable_reason: str | None


@dataclass(frozen=True, slots=True)
class WeightedPairMetric:
    match_pair_id: str
    available: bool
    unavailable_reason: str | None
    feature_count: int
    weighted_rms: float | None
    weighted_euclidean: float | None


@dataclass(frozen=True, slots=True)
class ComparisonMetricsResult:
    schema_version: str
    processing_status: str
    analysis_scope_id: str
    comparison_scope_sha256: str
    analysis_tier: str
    dataset_qc_link_status: str
    p2b_canonical_ready: bool | None
    canonical_analysis: bool
    data_origin: str
    run_purpose: str
    scientifically_eligible: bool
    input_artifact_ids: tuple[str, ...]
    input_feature_content_hashes: Mapping[str, str]
    band_metrics: tuple[BandMetricResult, ...]
    configuration_comparisons: tuple[ConfigurationComparisonResult, ...]
    cross_mode_metrics: CrossModeMetricsResult | None
    tone_reliability: ToneReliabilityResult | None
    weighted_metrics: tuple[WeightedPairMetric, ...]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


def _bands_from_config(value: Any) -> tuple[FrequencyBand, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ComparisonMetricsInputError("comparison frequency_bands are required")
    bands = tuple(FrequencyBand(**dict(item)) for item in value)
    if len({item.band_id for item in bands}) != len(bands):
        raise ComparisonMetricsInputError("comparison frequency band IDs must be unique")
    return bands


def analyze_comparison_feature_sets(
    feature_artifacts: Mapping[str, FeatureSet],
    comparison_scope: ComparisonAnalysisScope,
    direction_metrics_config: Mapping[str, Any],
    comparison_metrics_config: Mapping[str, Any],
    *,
    dataset_qc_result: DatasetQCResult | None = None,
) -> ComparisonMetricsResult:
    """Run P4-B over exactly the FeatureSet artifacts declared by one scope."""
    references = {item.artifact_id: item for item in comparison_scope.feature_references}
    if set(feature_artifacts) != set(references):
        raise ComparisonMetricsInputError(
            "P4-B FeatureSet artifact IDs must exactly match ComparisonAnalysisScope"
        )
    for artifact_id, feature in feature_artifacts.items():
        reference = references[artifact_id]
        if (
            feature.sample_id != reference.sample_id
            or feature.feature_kind.value != reference.feature_kind
            or feature.preprocessing_id != reference.preprocessing_id
            or feature_set_content_sha256(feature) != reference.feature_content_sha256
        ):
            raise ComparisonMetricsInputError(
                f"P4-B FeatureSet reference mismatch: {artifact_id}"
            )
    base_scope = comparison_scope.analysis_scope
    reference = base_scope.dataset_qc_reference
    if (reference is None) != (dataset_qc_result is None):
        raise ComparisonMetricsInputError(
            "P4-B DatasetQCReference and DatasetQCResult must be supplied together"
        )
    primary_by_sample: dict[str, FeatureSet] = {}
    for item in comparison_scope.feature_references:
        if not item.primary_for_dataset_qc:
            continue
        if item.sample_id in primary_by_sample:
            raise ComparisonMetricsInputError(
                f"multiple primary P2-B artifacts for sample {item.sample_id}"
            )
        primary_by_sample[item.sample_id] = feature_artifacts[item.artifact_id]
    p2b_ready: bool | None = None
    link_status = "not_provided"
    if reference is not None and dataset_qc_result is not None:
        if set(primary_by_sample) != set(base_scope.requested_sample_ids):
            raise ComparisonMetricsInputError(
                "P4-B primary P2-B artifact mapping is incomplete"
            )
        try:
            validate_dataset_qc_reference(
                tuple(primary_by_sample[item] for item in base_scope.requested_sample_ids),
                analysis_scope_id=base_scope.analysis_scope_id,
                ordered_sample_ids=base_scope.requested_sample_ids,
                run_purpose=base_scope.run_purpose,
                reference=reference,
                result=dataset_qc_result,
                require_canonical_ready=(
                    base_scope.analysis_tier is AnalysisTier.CANONICAL_COHORT
                ),
            )
        except DatasetQCInputError as exc:
            raise ComparisonMetricsInputError(f"P4-B blocked by {exc}") from exc
        p2b_ready = dataset_qc_result.canonical_ready
        link_status = (
            "validated_canonical" if p2b_ready else "validated_noncanonical"
        )
    elif base_scope.analysis_tier is AnalysisTier.CANONICAL_COHORT:
        raise ComparisonMetricsInputError(
            "canonical P4-B requires DatasetQCReference and DatasetQCResult"
        )
    if base_scope.analysis_tier is AnalysisTier.CANONICAL_COHORT:
        non_primary = [
            item.artifact_id
            for item in comparison_scope.feature_references
            if not item.primary_for_dataset_qc
        ]
        if non_primary:
            raise ComparisonMetricsInputError(
                "canonical P4-B cannot claim unaudited additional FeatureSet artifacts"
            )

    bands = _bands_from_config(comparison_metrics_config.get("frequency_bands"))
    context_by_sample = {
        item.sample_id: item for item in comparison_scope.measurements
    }
    groups: dict[tuple[str, str, str], list[FeatureSet]] = {}
    group_artifacts: dict[tuple[str, str, str], list[str]] = {}
    for artifact_id, feature in feature_artifacts.items():
        configuration = feature.meta.configuration
        if not configuration:
            raise ComparisonMetricsInputError("P4-B requires configuration metadata")
        key = (configuration, feature.feature_kind.value, feature.preprocessing_id)
        groups.setdefault(key, []).append(feature)
        group_artifacts.setdefault(key, []).append(artifact_id)
    for key, features in groups.items():
        sample_ids = [item.sample_id for item in features]
        if len(set(sample_ids)) != len(sample_ids):
            raise ComparisonMetricsInputError(
                f"P4-B group has duplicate measurement FeatureSets: {key}"
            )

    comparison_config = comparison_metrics_config.get("configuration_comparison", {})
    baseline_configuration = str(
        comparison_config.get("baseline_configuration", "U4SYM")
    )
    candidate_configuration = str(
        comparison_config.get("candidate_configuration", "U4ENC")
    )
    ratio_minimum = float(
        comparison_config.get("ratio_minimum_denominator", 1.0e-12)
    )
    band_rows: list[BandMetricResult] = []
    by_feature_contract: dict[tuple[str, str], dict[str, tuple[str, str, str]]] = {}
    for key in groups:
        configuration, feature_kind, preprocessing_id = key
        by_feature_contract.setdefault((feature_kind, preprocessing_id), {})[
            configuration
        ] = key
    processed: set[tuple[str, str, str]] = set()
    for contract_key, configurations in sorted(by_feature_contract.items()):
        compare_keys = [
            configurations.get(baseline_configuration),
            configurations.get(candidate_configuration),
        ]
        present_compare = [item for item in compare_keys if item is not None]
        fixed: NDArray[np.bool_] | None = None
        if len(present_compare) == 2:
            def design_signature(group_key: tuple[str, str, str]) -> tuple[tuple[Any, ...], ...]:
                return tuple(
                    sorted(
                        (
                            item.meta.angle_deg,
                            item.meta.session_id,
                            item.meta.repeat_type,
                            item.meta.repeat_id,
                            item.meta.reposition_round_id,
                            item.meta.assembly_id,
                            item.meta.acquisition_block_id,
                            context_by_sample[item.sample_id].cohort_role.value,
                        )
                        for item in groups[group_key]
                    )
                )

            if design_signature(present_compare[0]) != design_signature(present_compare[1]):
                raise ComparisonMetricsInputError(
                    "U4 configuration comparison experimental design/scope mismatch"
                )
            all_features = [item for key in present_compare for item in groups[key]]
            names = all_features[0].feature_names
            if any(item.feature_names != names for item in all_features[1:]):
                raise ComparisonMetricsInputError(
                    "U4 configuration comparison feature_names/order mismatch"
                )
            fixed = np.asarray(
                np.logical_and.reduce(
                    np.stack([item.valid_mask for item in all_features]), axis=0
                ),
                dtype=bool,
            )
        for key in configurations.values():
            features = tuple(groups[key])
            group_scope = replace(
                base_scope,
                included_sample_ids=tuple(item.sample_id for item in features),
                partition=None,
            )
            band_rows.extend(
                compute_band_metrics(
                    features,
                    group_scope,
                    bands,
                    direction_metrics_config,
                    fixed_common_mask=fixed,
                )
            )
            processed.add(key)
    configuration_rows: list[ConfigurationComparisonResult] = []
    for feature_kind, preprocessing_id in sorted(by_feature_contract):
        matches = [
            item
            for item in band_rows
            if item.feature_kind == feature_kind
            and item.preprocessing_id == preprocessing_id
        ]
        baseline_rows = [
            item for item in matches if item.configuration_id == baseline_configuration
        ]
        candidate_rows = [
            item for item in matches if item.configuration_id == candidate_configuration
        ]
        if baseline_rows and candidate_rows:
            configuration_rows.extend(
                compare_configuration_band_metrics(
                    baseline_rows,
                    candidate_rows,
                    baseline_configuration=baseline_configuration,
                    candidate_configuration=candidate_configuration,
                    ratio_minimum_denominator=ratio_minimum,
                )
            )

    cross_result: CrossModeMetricsResult | None = None
    reliability: ToneReliabilityResult | None = None
    weighted_rows: list[WeightedPairMetric] = []
    if comparison_scope.cross_mode_pairs:
        for pair in comparison_scope.cross_mode_pairs:
            pair_features = (
                feature_artifacts[pair.sweep_artifact_id],
                feature_artifacts[pair.multisine_artifact_id],
            )
            for feature in pair_features:
                context = context_by_sample[feature.sample_id]
                if (
                    context.direction_id != pair.direction_id
                    or context.physical_state_id != pair.physical_state_id
                    or context.cohort_role is not pair.cohort_role
                ):
                    raise ComparisonMetricsInputError(
                        f"cross-mode pair {pair.match_pair_id} comparison-scope "
                        "direction/state/role mismatch"
                    )
        cross_config = comparison_metrics_config.get("cross_mode", {})
        cross_result = compute_cross_mode_metrics(
            feature_artifacts,
            comparison_scope.cross_mode_pairs,
            minimum_common_tones=int(cross_config["minimum_common_tones"]),
            allow_centered_shape_comparison=bool(
                cross_config["allow_centered_shape_comparison"]
            ),
        )
        reliability_config = comparison_metrics_config.get("reliability")
        if isinstance(reliability_config, Mapping):
            source_kind = FeatureKind(
                reliability_config.get(
                    "source_feature_kind", "tone_measurement_from_multisine"
                )
            )
            context_by_id = {
                item.sample_id: item for item in comparison_scope.measurements
            }
            reliability_features = tuple(
                item for item in feature_artifacts.values() if item.feature_kind is source_kind
            )
            reliability = compute_tone_reliability(
                reliability_features,
                {
                    item.sample_id: context_by_id[item.sample_id].cohort_role
                    for item in reliability_features
                },
                repeat_type=str(reliability_config["repeat_type"]),
                floor_db=float(reliability_config["floor_db"]),
                maximum_raw_weight=float(
                    reliability_config["maximum_raw_weight"]
                ),
                minimum_pairs_per_tone=int(
                    reliability_config["minimum_pairs_per_tone"]
                ),
                minimum_available_tones=int(
                    reliability_config["minimum_available_tones"]
                ),
                fixed_common_mask=cross_result.common_valid_mask,
            )
            for pair in comparison_scope.cross_mode_pairs:
                sweep = feature_artifacts[pair.sweep_artifact_id]
                multisine = feature_artifacts[pair.multisine_artifact_id]
                mask = cross_result.common_valid_mask & reliability.available_mask
                if reliability.available and np.any(mask):
                    weighted = compute_weighted_distances(
                        sweep.values[mask],
                        multisine.values[mask],
                        reliability.normalized_weights[mask],
                    )
                    weighted_rows.append(
                        WeightedPairMetric(
                            match_pair_id=pair.match_pair_id,
                            available=True,
                            unavailable_reason=None,
                            feature_count=weighted.feature_count,
                            weighted_rms=weighted.weighted_rms,
                            weighted_euclidean=weighted.weighted_euclidean,
                        )
                    )
                else:
                    weighted_rows.append(
                        WeightedPairMetric(
                            match_pair_id=pair.match_pair_id,
                            available=False,
                            unavailable_reason=(
                                None
                                if reliability is None
                                else reliability.unavailable_reason
                            )
                            or "reliability_unavailable",
                            feature_count=int(np.count_nonzero(mask)),
                            weighted_rms=None,
                            weighted_euclidean=None,
                        )
                    )

    features = tuple(feature_artifacts.values())
    origins = {item.meta.data_origin.value for item in features}
    if len(origins) != 1:
        raise ComparisonMetricsInputError("P4-B cannot mix data origins")
    band_warnings = tuple(
        f"band_unavailable:{item.configuration_id}:{item.feature_kind}:{item.band_id}"
        for item in band_rows
        if not item.available
    )
    return ComparisonMetricsResult(
        schema_version="1.0.0",
        processing_status=(
            "completed_with_unavailable" if band_warnings else "completed"
        ),
        analysis_scope_id=base_scope.analysis_scope_id,
        comparison_scope_sha256=comparison_scope.sha256,
        analysis_tier=base_scope.analysis_tier.value,
        dataset_qc_link_status=link_status,
        p2b_canonical_ready=p2b_ready,
        canonical_analysis=(
            base_scope.analysis_tier is AnalysisTier.CANONICAL_COHORT
            and p2b_ready is True
        ),
        data_origin=next(iter(origins)),
        run_purpose=base_scope.run_purpose.value,
        scientifically_eligible=all(
            item.meta.eligible_for_scientific_analysis for item in features
        ),
        input_artifact_ids=tuple(references),
        input_feature_content_hashes={
            artifact_id: references[artifact_id].feature_content_sha256
            for artifact_id in references
        },
        band_metrics=tuple(band_rows),
        configuration_comparisons=tuple(configuration_rows),
        cross_mode_metrics=cross_result,
        tone_reliability=reliability,
        weighted_metrics=tuple(weighted_rows),
        failures=(),
        warnings=band_warnings,
    )


def compare_configuration_band_metrics(
    baseline_results: Sequence[BandMetricResult],
    candidate_results: Sequence[BandMetricResult],
    *,
    baseline_configuration: str,
    candidate_configuration: str,
    ratio_minimum_denominator: float,
) -> tuple[ConfigurationComparisonResult, ...]:
    """Compare matched configuration rows without interpreting which is better."""
    if (
        not np.isfinite(ratio_minimum_denominator)
        or ratio_minimum_denominator <= 0.0
    ):
        raise ComparisonMetricsInputError(
            "ratio_minimum_denominator must be positive and finite"
        )
    baseline = {(item.band_id, item.feature_kind): item for item in baseline_results}
    candidate = {(item.band_id, item.feature_kind): item for item in candidate_results}
    if not baseline or set(baseline) != set(candidate):
        raise ComparisonMetricsInputError(
            "configuration comparison requires identical band/FeatureKind keys"
        )
    metrics = (
        "within_cont_median",
        "within_repos_median",
        "within_reasm_median",
        "between_direction_median",
        "morphology_gain",
        "effective_rank",
        "maximum_off_diagonal_pearson",
        "mean_off_diagonal_pearson",
    )
    ratio_metrics = {
        "within_cont_median",
        "within_repos_median",
        "within_reasm_median",
        "between_direction_median",
        "morphology_gain",
        "effective_rank",
    }
    rows: list[ConfigurationComparisonResult] = []
    for key in sorted(baseline):
        left = baseline[key]
        right = candidate[key]
        if (
            left.configuration_id != baseline_configuration
            or right.configuration_id != candidate_configuration
        ):
            raise ComparisonMetricsInputError(
                "configuration comparison ID does not match configured roles"
            )
        if (
            left.preprocessing_id != right.preprocessing_id
            or left.f_min_hz != right.f_min_hz
            or left.f_max_hz != right.f_max_hz
            or left.boundary != right.boundary
            or left.feature_count != right.feature_count
        ):
            raise ComparisonMetricsInputError(
                "configuration comparison scope/mask/preprocessing mismatch"
            )
        for metric in metrics:
            baseline_value = getattr(left, metric)
            candidate_value = getattr(right, metric)
            available = (
                left.available
                and right.available
                and baseline_value is not None
                and candidate_value is not None
            )
            if available:
                delta = float(candidate_value - baseline_value)
                unavailable_reason = None
            else:
                delta = None
                unavailable_reason = "configuration_metric_unavailable"
            ratio: float | None = None
            ratio_reason: str | None = None
            if metric not in ratio_metrics:
                ratio_reason = "ratio_not_defined_for_metric"
            elif not available:
                ratio_reason = "configuration_metric_unavailable"
            elif abs(float(baseline_value)) < ratio_minimum_denominator:
                ratio_reason = "baseline_below_ratio_minimum"
            else:
                ratio = float(candidate_value / baseline_value)
            rows.append(
                ConfigurationComparisonResult(
                    band_id=left.band_id,
                    feature_kind=left.feature_kind,
                    metric_id=metric,
                    baseline_configuration=baseline_configuration,
                    candidate_configuration=candidate_configuration,
                    baseline_value=baseline_value,
                    candidate_value=candidate_value,
                    delta=delta,
                    ratio=ratio,
                    available=available,
                    unavailable_reason=unavailable_reason,
                    ratio_unavailable_reason=ratio_reason,
                )
            )
    return tuple(rows)


def compute_weighted_distances(
    left: NDArray[np.float64],
    right: NDArray[np.float64],
    weights: NDArray[np.float64],
) -> WeightedDistanceResult:
    """Return supplemental weighted distances without replacing primary metrics."""
    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    weight_array = np.asarray(weights, dtype=np.float64)
    if (
        left_array.ndim != 1
        or right_array.shape != left_array.shape
        or weight_array.shape != left_array.shape
        or left_array.size == 0
        or np.any(~np.isfinite(left_array))
        or np.any(~np.isfinite(right_array))
        or np.any(~np.isfinite(weight_array))
        or np.any(weight_array <= 0.0)
    ):
        raise ComparisonMetricsInputError(
            "weighted distance inputs must be matching finite vectors with positive weights"
        )
    squared = np.square(right_array - left_array)
    weighted_sum = float(np.sum(weight_array * squared))
    weight_sum = float(np.sum(weight_array))
    return WeightedDistanceResult(
        feature_count=left_array.size,
        weight_sum=weight_sum,
        weighted_rms=float(np.sqrt(weighted_sum / weight_sum)),
        weighted_euclidean=float(np.sqrt(weighted_sum)),
    )


def compute_tone_reliability(
    feature_sets: Sequence[FeatureSet],
    cohort_roles: Mapping[str, CohortRole | str],
    *,
    repeat_type: str,
    floor_db: float,
    maximum_raw_weight: float,
    minimum_pairs_per_tone: int,
    minimum_available_tones: int,
    fixed_common_mask: NDArray[np.bool_] | None = None,
) -> ToneReliabilityResult:
    """Estimate tone reliability only from explicit development/training REPOS pairs."""
    features = tuple(feature_sets)
    if not features:
        raise ComparisonMetricsInputError("tone reliability requires FeatureSet inputs")
    if repeat_type != "REPOS":
        raise ComparisonMetricsInputError("tone reliability repeat_type must be REPOS")
    if set(cohort_roles) != {item.sample_id for item in features}:
        raise ComparisonMetricsInputError(
            "tone reliability cohort-role mapping must exactly match samples"
        )
    roles = {CohortRole(value) for value in cohort_roles.values()}
    if CohortRole.FINAL_TEST in roles:
        raise ComparisonMetricsInputError(
            "final_test cannot be a tone reliability source"
        )
    if not roles <= {CohortRole.DEVELOPMENT, CohortRole.TRAINING}:
        raise ComparisonMetricsInputError("tone reliability source role is unsupported")
    numeric = (float(floor_db), float(maximum_raw_weight))
    if any(not np.isfinite(item) or item <= 0.0 for item in numeric):
        raise ComparisonMetricsInputError("reliability floor and clip must be positive")
    for name, value in {
        "minimum_pairs_per_tone": minimum_pairs_per_tone,
        "minimum_available_tones": minimum_available_tones,
    }.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ComparisonMetricsInputError(f"{name} must be an integer >= 1")
    first = features[0]
    if first.feature_kind not in {
        FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
    }:
        raise ComparisonMetricsInputError("tone reliability requires tone FeatureSets")
    contract = feature_contract_sha256(first)
    if any(feature_contract_sha256(item) != contract for item in features[1:]):
        raise ComparisonMetricsInputError("tone reliability FeatureSet contract mismatch")
    frequencies = feature_frequencies_hz(first.feature_names)
    if fixed_common_mask is None:
        allowed_mask = np.ones(frequencies.size, dtype=bool)
    else:
        allowed_mask = np.asarray(fixed_common_mask, dtype=bool)
        if allowed_mask.ndim != 1 or allowed_mask.size != frequencies.size:
            raise ComparisonMetricsInputError("reliability fixed mask length mismatch")
    differences: list[list[float]] = [[] for _ in range(frequencies.size)]
    pair_ids: list[list[str]] = [[] for _ in range(frequencies.size)]
    ordered = tuple(sorted(features, key=lambda item: item.sample_id))
    for left, right in itertools.combinations(ordered, 2):
        if left.meta.angle_deg != right.meta.angle_deg:
            continue
        if left.meta.repeat_type != repeat_type or right.meta.repeat_type != repeat_type:
            continue
        reason = repeat_pair_unavailable_reason(left, right)
        if reason is not None:
            continue
        pair_id = f"{left.sample_id}__{right.sample_id}"
        mask = allowed_mask & left.valid_mask & right.valid_mask
        for index in np.flatnonzero(mask):
            differences[int(index)].append(
                abs(float(left.values[index] - right.values[index]))
            )
            pair_ids[int(index)].append(pair_id)
    stability = np.full(frequencies.size, np.nan, dtype=np.float64)
    raw = np.full(frequencies.size, np.nan, dtype=np.float64)
    clipped = np.full(frequencies.size, np.nan, dtype=np.float64)
    normalized = np.full(frequencies.size, np.nan, dtype=np.float64)
    counts = np.asarray([len(item) for item in differences], dtype=np.int64)
    available_mask = allowed_mask & (counts >= minimum_pairs_per_tone)
    for index in np.flatnonzero(available_mask):
        stability[index] = float(np.median(differences[int(index)]))
        raw[index] = 1.0 / max(stability[index], floor_db) ** 2
        clipped[index] = min(raw[index], maximum_raw_weight)
    if np.any(available_mask):
        mean_weight = float(np.mean(clipped[available_mask]))
        normalized[available_mask] = clipped[available_mask] / mean_weight
    available_count = int(np.count_nonzero(available_mask))
    available = available_count >= minimum_available_tones
    reason = None if available else "insufficient_reliable_tones"
    for array in (frequencies, stability, raw, clipped, normalized, counts, available_mask):
        array.setflags(write=False)
    return ToneReliabilityResult(
        available=available,
        unavailable_reason=reason,
        repeat_type=repeat_type,
        source_roles=tuple(sorted(roles, key=lambda item: item.value)),
        floor_db=float(floor_db),
        maximum_raw_weight=float(maximum_raw_weight),
        normalization="mean_one",
        minimum_pairs_per_tone=minimum_pairs_per_tone,
        minimum_available_tones=minimum_available_tones,
        frequencies_hz=frequencies,
        stability_db=stability,
        raw_weights=raw,
        clipped_weights=clipped,
        normalized_weights=normalized,
        pair_counts=counts,
        available_mask=available_mask,
        pair_ids_by_tone=tuple(tuple(item) for item in pair_ids),
    )


def _pair_metadata_mismatches(
    feature: FeatureSet,
    pair: CrossModePairSpec,
) -> tuple[str, ...]:
    meta = feature.meta
    checks = {
        "configuration_id": meta.configuration == pair.configuration_id,
        "direction_angle_deg": meta.angle_deg == pair.direction_angle_deg,
        "session_id": meta.session_id == pair.session_id,
        "repeat_type": meta.repeat_type == pair.repeat_type,
        "repeat_id": meta.repeat_id == pair.repeat_id,
        "reposition_round_id": meta.reposition_round_id == pair.reposition_round_id,
        "assembly_id": meta.assembly_id == pair.assembly_id,
        "acquisition_block_id": (
            meta.acquisition_block_id == pair.acquisition_block_id
        ),
    }
    return tuple(name for name, matches in checks.items() if not matches)


def _absolute_comparison_reason(sweep: FeatureSet, multisine: FeatureSet) -> str | None:
    if sweep.units != multisine.units or set(sweep.units) != {"dB"}:
        return "units_not_compatible_db"
    if sweep.normalization_method != "none" or multisine.normalization_method != "none":
        return "normalization_not_absolute"
    if sweep.source_magnitude_quantity != multisine.source_magnitude_quantity:
        return "magnitude_quantity_mismatch"
    if (
        sweep.calibration_id
        and sweep.calibration_id == multisine.calibration_id
    ):
        return None
    if (
        sweep.source_magnitude_reference
        and sweep.source_magnitude_reference == multisine.source_magnitude_reference
    ):
        return None
    return "magnitude_reference_or_calibration_mismatch"


def _shape_comparison_reason(sweep: FeatureSet, multisine: FeatureSet) -> str | None:
    if sweep.units != multisine.units or set(sweep.units) != {"dB"}:
        return "shape_units_not_compatible_db"
    if sweep.normalization_method != multisine.normalization_method:
        return "shape_normalization_mismatch"
    if sweep.source_magnitude_quantity != multisine.source_magnitude_quantity:
        return "shape_magnitude_quantity_mismatch"
    if sweep.calibration_id != multisine.calibration_id:
        return "shape_calibration_state_mismatch"
    return None


def compute_cross_mode_metrics(
    feature_artifacts: Mapping[str, FeatureSet],
    pair_specs: Sequence[CrossModePairSpec],
    *,
    minimum_common_tones: int,
    allow_centered_shape_comparison: bool,
) -> CrossModeMetricsResult:
    """Compute explicit one-to-one cross-mode metrics on one fixed tone mask."""
    pairs = tuple(pair_specs)
    if not pairs:
        raise ComparisonMetricsInputError("cross-mode comparison requires explicit pairs")
    if (
        isinstance(minimum_common_tones, bool)
        or not isinstance(minimum_common_tones, int)
        or minimum_common_tones < 1
    ):
        raise ComparisonMetricsInputError("minimum_common_tones must be an integer >= 1")
    pair_ids = [item.match_pair_id for item in pairs]
    sweep_ids = [item.sweep_artifact_id for item in pairs]
    multisine_ids = [item.multisine_artifact_id for item in pairs]
    if len(set(pair_ids)) != len(pair_ids):
        raise ComparisonMetricsInputError("duplicate cross-mode match_pair_id")
    if len(set(sweep_ids)) != len(sweep_ids) or len(set(multisine_ids)) != len(
        multisine_ids
    ):
        raise ComparisonMetricsInputError("cross-mode pairing must be one-to-one")
    if set(sweep_ids) & set(multisine_ids):
        raise ComparisonMetricsInputError("one artifact cannot occupy both mode roles")

    referenced: list[FeatureSet] = []
    validated: list[tuple[CrossModePairSpec, FeatureSet, FeatureSet]] = []
    for pair in pairs:
        try:
            sweep = feature_artifacts[pair.sweep_artifact_id]
            multisine = feature_artifacts[pair.multisine_artifact_id]
        except KeyError as exc:
            raise ComparisonMetricsInputError(
                f"cross-mode pair references an unknown artifact: {exc.args[0]}"
            ) from exc
        if sweep.feature_kind is not FeatureKind.TONE_PROJECTION_FROM_SWEEP:
            raise ComparisonMetricsInputError("cross-mode sweep role has wrong FeatureKind")
        if multisine.feature_kind is not FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE:
            raise ComparisonMetricsInputError(
                "cross-mode multisine role has wrong FeatureKind"
            )
        if sweep.source_measurement_mode is not MeasurementMode.REW_SWEEP:
            raise ComparisonMetricsInputError("cross-mode sweep mode metadata mismatch")
        if multisine.source_measurement_mode is not MeasurementMode.SCHROEDER_MULTISINE:
            raise ComparisonMetricsInputError("cross-mode multisine mode metadata mismatch")
        try:
            assert_matched_tone_schema(sweep, multisine)
        except ToneFeatureConstructionError as exc:
            raise ComparisonMetricsInputError(str(exc)) from exc
        for feature in (sweep, multisine):
            mismatches = _pair_metadata_mismatches(feature, pair)
            if mismatches:
                raise ComparisonMetricsInputError(
                    f"cross-mode pair {pair.match_pair_id} metadata mismatch: "
                    + ", ".join(mismatches)
                )
        referenced.extend((sweep, multisine))
        validated.append((pair, sweep, multisine))
    common = np.asarray(
        np.logical_and.reduce(np.stack([item.valid_mask for item in referenced])),
        dtype=bool,
    )
    common.setflags(write=False)
    common_count = int(np.count_nonzero(common))
    if common_count < minimum_common_tones:
        raise ComparisonMetricsInputError(
            f"common tone count {common_count} is below {minimum_common_tones}"
        )
    rows: list[CrossModePairMetric] = []
    for pair, sweep, multisine in validated:
        left = sweep.values[common]
        right = multisine.values[common]
        absolute_reason = _absolute_comparison_reason(sweep, multisine)
        shape_reason = _shape_comparison_reason(sweep, multisine)
        if not allow_centered_shape_comparison:
            shape_reason = "centered_shape_comparison_disabled"
        difference = right - left
        centered_left = left - np.mean(left)
        centered_right = right - np.mean(right)
        pearson, pearson_reason = compute_vector_metric("pearson", left, right)
        centered_cosine, centered_cosine_reason = compute_vector_metric(
            "cosine", centered_left, centered_right
        )
        if pearson_reason is not None:
            shape_reason = pearson_reason
        if centered_cosine_reason is not None and shape_reason is None:
            shape_reason = centered_cosine_reason
        if absolute_reason is None:
            cosine, cosine_reason = compute_vector_metric("cosine", left, right)
            if cosine_reason is not None:
                absolute_reason = cosine_reason
        else:
            cosine = np.nan
        absolute = absolute_reason is None
        shape = shape_reason is None
        rows.append(
            CrossModePairMetric(
                match_pair_id=pair.match_pair_id,
                sweep_artifact_id=pair.sweep_artifact_id,
                multisine_artifact_id=pair.multisine_artifact_id,
                direction_id=pair.direction_id,
                direction_angle_deg=pair.direction_angle_deg,
                configuration_id=pair.configuration_id,
                physical_state_id=pair.physical_state_id,
                cohort_role=pair.cohort_role,
                common_tone_count=common_count,
                missing_tone_count=common.size - common_count,
                absolute_comparison_available=absolute,
                absolute_unavailable_reason=absolute_reason,
                shape_comparison_available=shape,
                shape_unavailable_reason=shape_reason,
                pearson_correlation=float(pearson) if shape else None,
                cosine_similarity=float(cosine) if absolute else None,
                rms_difference_db=(
                    float(np.sqrt(np.mean(np.square(difference))))
                    if absolute
                    else None
                ),
                euclidean_distance_db=(
                    float(np.linalg.norm(difference)) if absolute else None
                ),
                median_absolute_difference_db=(
                    float(np.median(np.abs(difference))) if absolute else None
                ),
                mean_bias_db=float(np.mean(difference)) if absolute else None,
                median_bias_db=float(np.median(difference)) if absolute else None,
                centered_rms_db=(
                    float(
                        np.sqrt(
                            np.mean(np.square(centered_right - centered_left))
                        )
                    )
                    if shape
                    else None
                ),
                centered_cosine_similarity=(
                    float(centered_cosine) if shape else None
                ),
            )
        )
    first = referenced[0]
    frequencies = feature_frequencies_hz(first.feature_names)
    per_tone: list[PerToneBiasResult] = []
    for tone_index, frequency in enumerate(frequencies):
        values: list[float] = []
        directions: set[str] = set()
        reasons: set[str] = set()
        for pair, sweep, multisine in validated:
            reason = _absolute_comparison_reason(sweep, multisine)
            if reason is not None:
                reasons.add(reason)
                continue
            if not common[tone_index]:
                reasons.add("tone_not_in_fixed_common_mask")
                continue
            values.append(
                float(multisine.values[tone_index] - sweep.values[tone_index])
            )
            directions.add(pair.direction_id)
        array = np.asarray(values, dtype=np.float64)
        if array.size == len(validated):
            status = "available"
        elif array.size:
            status = "partial"
        else:
            status = "unavailable"
        median = float(np.median(array)) if array.size else None
        quartiles = (
            np.percentile(array, [25.0, 75.0], method="linear")
            if array.size
            else None
        )
        per_tone.append(
            PerToneBiasResult(
                tone_index=tone_index,
                frequency_hz=float(frequency),
                mean_bias_db=float(np.mean(array)) if array.size else None,
                median_bias_db=median,
                sample_standard_deviation_db=(
                    float(np.std(array, ddof=1)) if array.size >= 2 else None
                ),
                median_absolute_deviation_db=(
                    float(np.median(np.abs(array - median)))
                    if array.size and median is not None
                    else None
                ),
                interquartile_range_db=(
                    float(quartiles[1] - quartiles[0])
                    if quartiles is not None
                    else None
                ),
                pair_count=int(array.size),
                direction_count=len(directions),
                missing_count=len(validated) - int(array.size),
                absolute_comparison_status=status,
                unavailable_reasons=tuple(sorted(reasons)),
            )
        )
    assert first.tone_set_id is not None
    assert first.tone_set_sha256 is not None
    assert first.tone_schema_id is not None
    return CrossModeMetricsResult(
        common_valid_mask=common,
        total_tone_count=common.size,
        common_tone_count=common_count,
        missing_tone_count=common.size - common_count,
        tone_set_id=first.tone_set_id,
        tone_set_sha256=first.tone_set_sha256,
        tone_schema_id=first.tone_schema_id,
        pairs=tuple(rows),
        per_tone_bias=tuple(per_tone),
    )


def _internal_scope(scope: AnalysisScope, suffix: str) -> AnalysisScope:
    return replace(
        scope,
        schema_version="1.0.0",
        analysis_scope_id=f"{scope.analysis_scope_id}:{suffix}",
        analysis_tier=AnalysisTier.PROVISIONAL_SOFTWARE_VALIDATION,
        dataset_qc_reference=None,
    )


def _available_matrix_value(
    metrics: DirectionMetricsResult,
    metric: str,
    left: int,
    right: int,
) -> tuple[float | None, str | None]:
    matrix = metrics.matrices[metric]
    if matrix.available[left, right]:
        return float(matrix.values[left, right]), None
    return None, matrix.unavailable_reasons[left][right]


def _band_result(
    metrics: DirectionMetricsResult,
    band: FrequencyBand,
    feature_count: int,
) -> BandMetricResult:
    pair_rows: list[BandDirectionPairResult] = []
    angles = metrics.direction_order_deg
    for left in range(len(angles)):
        for right in range(left + 1, len(angles)):
            values: dict[str, float | None] = {}
            reasons: list[str] = []
            for metric in (
                "pearson",
                "cosine",
                "euclidean",
                "rms",
                "median_absolute_difference",
            ):
                value, reason = _available_matrix_value(metrics, metric, left, right)
                values[metric] = value
                if reason is not None:
                    reasons.append(f"{metric}:{reason}")
            pair_rows.append(
                BandDirectionPairResult(
                    band_id=band.band_id,
                    configuration_id=metrics.configuration,
                    feature_kind=metrics.feature_kind,
                    left_direction_deg=angles[left],
                    right_direction_deg=angles[right],
                    feature_count=feature_count,
                    pearson=values["pearson"],
                    cosine=values["cosine"],
                    euclidean=values["euclidean"],
                    rms=values["rms"],
                    median_absolute_difference=values["median_absolute_difference"],
                    unavailable_reasons=tuple(sorted(set(reasons))),
                )
            )
    repeat = {item.repeat_type: item for item in metrics.repeatability_summaries}
    between = np.asarray(
        [
            item.distances["rms"]
            for item in metrics.between_direction_pairs
            if item.constructed
        ],
        dtype=np.float64,
    )
    return BandMetricResult(
        band_id=band.band_id,
        configuration_id=metrics.configuration,
        feature_kind=metrics.feature_kind,
        preprocessing_id=metrics.preprocessing_id,
        f_min_hz=band.f_min_hz,
        f_max_hz=band.f_max_hz,
        boundary=band.boundary,
        minimum_feature_count=band.minimum_feature_count,
        feature_count=feature_count,
        available=metrics.processing_status == "completed",
        unavailable_reason=(
            None
            if metrics.processing_status == "completed"
            else "; ".join(metrics.failures) or "direction_metrics_failed"
        ),
        maximum_off_diagonal_pearson=metrics.summary.maximum_off_diagonal_pearson,
        mean_off_diagonal_pearson=metrics.summary.mean_off_diagonal_pearson,
        most_similar_direction_pair=metrics.summary.most_similar_highest_pearson_pair,
        most_difficult_direction_pair=metrics.summary.most_difficult_lowest_rms_pair,
        effective_rank=metrics.effective_rank.value,
        morphology_gain=metrics.morphology_gain.value,
        morphology_gain_unavailable_reason=metrics.morphology_gain.unavailable_reason,
        within_cont_median=repeat["CONT"].median,
        within_repos_median=repeat["REPOS"].median,
        within_reasm_median=repeat["REASM"].median,
        between_direction_median=(
            float(np.median(between)) if between.size else None
        ),
        direction_pairs=tuple(pair_rows),
    )


def compute_band_metrics(
    feature_sets: Sequence[FeatureSet],
    analysis_scope: AnalysisScope,
    bands: Sequence[FrequencyBand],
    direction_metrics_config: Mapping[str, Any],
    *,
    fixed_common_mask: NDArray[np.bool_] | None = None,
) -> tuple[BandMetricResult, ...]:
    """Evaluate every configured band with one fixed, non-expanding scope mask."""
    if not feature_sets:
        raise ComparisonMetricsInputError("band metrics require FeatureSet inputs")
    if not bands or len({item.band_id for item in bands}) != len(bands):
        raise ComparisonMetricsInputError("frequency band IDs must be non-empty and unique")
    feature_tuple = tuple(feature_sets)
    names = feature_tuple[0].feature_names
    if any(item.feature_names != names for item in feature_tuple[1:]):
        raise ComparisonMetricsInputError("band metrics feature_names/order mismatch")
    frequencies = feature_frequencies_hz(names)
    if fixed_common_mask is None:
        common = np.logical_and.reduce(
            np.stack([item.valid_mask for item in feature_tuple]), axis=0
        )
    else:
        common = np.asarray(fixed_common_mask, dtype=bool)
        if common.ndim != 1 or common.size != len(names):
            raise ComparisonMetricsInputError("fixed common mask length mismatch")
        if any(np.any(common & ~item.valid_mask) for item in feature_tuple):
            raise ComparisonMetricsInputError(
                "fixed common mask cannot enable an invalid FeatureSet entry"
            )
    results: list[BandMetricResult] = []
    for band in bands:
        mask = np.asarray(common & frequency_band_mask(frequencies, band), dtype=bool)
        count = int(np.count_nonzero(mask))
        first = feature_tuple[0]
        if count < band.minimum_feature_count:
            results.append(
                BandMetricResult(
                    band_id=band.band_id,
                    configuration_id=str(first.meta.configuration),
                    feature_kind=first.feature_kind.value,
                    preprocessing_id=first.preprocessing_id,
                    f_min_hz=band.f_min_hz,
                    f_max_hz=band.f_max_hz,
                    boundary=band.boundary,
                    minimum_feature_count=band.minimum_feature_count,
                    feature_count=count,
                    available=False,
                    unavailable_reason="minimum_feature_count_not_met",
                    maximum_off_diagonal_pearson=None,
                    mean_off_diagonal_pearson=None,
                    most_similar_direction_pair=None,
                    most_difficult_direction_pair=None,
                    effective_rank=None,
                    morphology_gain=None,
                    morphology_gain_unavailable_reason="band_unavailable",
                    within_cont_median=None,
                    within_repos_median=None,
                    within_reasm_median=None,
                    between_direction_median=None,
                    direction_pairs=(),
                )
            )
            continue
        # P4-A's minimum-common fraction is defined over its input vector.  A
        # P4-B band is therefore an immutable sliced FeatureSet view, not the
        # full vector with out-of-band entries changed to invalid.  This keeps
        # P4-A mathematics unchanged while making the denominator the declared
        # band and never fills, interpolates, or expands the fixed common mask.
        indices = np.flatnonzero(mask)
        masked = tuple(
            replace(
                item,
                feature_names=tuple(item.feature_names[index] for index in indices),
                values=np.asarray(item.values[indices], dtype=np.float64),
                valid_mask=np.ones(indices.size, dtype=bool),
                units=tuple(item.units[index] for index in indices),
                reliability_weights=(
                    None
                    if item.reliability_weights is None
                    else np.asarray(item.reliability_weights[indices], dtype=np.float64)
                ),
            )
            for item in feature_tuple
        )
        metrics = analyze_direction_feature_sets(
            masked,
            _internal_scope(analysis_scope, f"band:{band.band_id}"),
            direction_metrics_config,
        )
        results.append(_band_result(metrics, band, count))
    return tuple(results)

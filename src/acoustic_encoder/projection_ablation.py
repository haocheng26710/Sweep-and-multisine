"""Leakage-safe sweep projection ablation for DEV-C13 P9-B."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np

from .classification import predict_direction_fold, summarize_direction_predictions
from .comparison_metrics import CohortRole, compute_tone_reliability
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .metrics import (
    AnalysisScope,
    QCInclusionPolicy,
    ScopeRole,
    SelectionPolicy,
    analyze_direction_feature_sets,
)
from .schemas import FeatureKind, FeatureSet, MeasurementMode, QCStatus
from .sweep_multisine_bridge import (
    CandidateToneUniverse,
    SelectedToneSetArtifact,
    SelectionMode,
    ToneSelectionScope,
)


class ProjectionAblationInputError(ValueError):
    """Raised when an explicit P9-B contract cannot be verified."""


class AblationStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"
    POLICY_INELIGIBLE = "policy_ineligible"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class AblationScopeMember:
    sample_id: str
    physical_state_id: str
    cohort_role: str
    direction_angle_deg: float
    session_id: str
    selection_reason: str

    def __post_init__(self) -> None:
        if self.cohort_role not in {"development", "training"}:
            raise ProjectionAblationInputError("P9-B scope cannot contain final_test")
        if any(not str(getattr(self, name)).strip() for name in ("sample_id", "physical_state_id", "session_id", "selection_reason")):
            raise ProjectionAblationInputError("P9-B member fields must be explicit")
        if not np.isfinite(self.direction_angle_deg):
            raise ProjectionAblationInputError("P9-B direction must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AblationScopeMember":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class InnerFoldDefinition:
    inner_fold_id: str
    train_sample_ids: tuple[str, ...]
    validation_sample_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "inner_fold_id": self.inner_fold_id,
            "train_sample_ids": list(self.train_sample_ids),
            "validation_sample_ids": list(self.validation_sample_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "InnerFoldDefinition":
        value = dict(payload)
        value["train_sample_ids"] = tuple(value["train_sample_ids"])
        value["validation_sample_ids"] = tuple(value["validation_sample_ids"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class OuterFoldDefinition:
    outer_fold_id: str
    held_out_group: str
    training_sample_ids: tuple[str, ...]
    test_sample_ids: tuple[str, ...]
    held_out_physical_state_ids: tuple[str, ...]
    inner_folds: tuple[InnerFoldDefinition, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "outer_fold_id": self.outer_fold_id,
            "held_out_group": self.held_out_group,
            "training_sample_ids": list(self.training_sample_ids),
            "test_sample_ids": list(self.test_sample_ids),
            "held_out_physical_state_ids": list(self.held_out_physical_state_ids),
            "inner_folds": [item.to_dict() for item in self.inner_folds],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OuterFoldDefinition":
        value = dict(payload)
        for name in ("training_sample_ids", "test_sample_ids", "held_out_physical_state_ids"):
            value[name] = tuple(value[name])
        value["inner_folds"] = tuple(InnerFoldDefinition.from_dict(item) for item in value["inner_folds"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class FoldSelectionReference:
    outer_fold_id: str
    selection_scope_sha256: str
    selection_artifact_sha256: str
    training_sample_sha256: str
    candidate_universe_sha256: str
    dataset_qc_result_sha256: str
    comparison_metrics_result_sha256: str | None
    training_feature_content_sha256: str
    selection_manifest_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FoldSelectionReference":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class P9ProjectionAblationScope:
    schema_version: str
    analysis_scope_id: str
    data_origin: str
    run_purpose: str
    dataset_role: str
    members: tuple[AblationScopeMember, ...]
    outer_folds: tuple[OuterFoldDefinition, ...]
    fold_selection_references: tuple[FoldSelectionReference, ...]
    subset_sizes: tuple[int, ...]
    policy_config_sha256: str
    sealed_final_test_sample_ids: tuple[str, ...]
    sealed_final_test_sha256: str
    random_state: int

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0":
            raise ProjectionAblationInputError("P9ProjectionAblationScope schema_version must be 1.0.0")
        if (self.data_origin, self.run_purpose, self.dataset_role) != ("simulated", "software_validation", "software_validation"):
            raise ProjectionAblationInputError("DEV-C13 is simulated software_validation only")
        ids = tuple(item.sample_id for item in self.members)
        if not ids or len(set(ids)) != len(ids):
            raise ProjectionAblationInputError("P9-B scope members must be non-empty and unique")
        if tuple(sorted(set(self.subset_sizes))) != self.subset_sizes:
            raise ProjectionAblationInputError("P9-B subset sizes must be unique and increasing")
        known = set(ids)
        member_by_id = {item.sample_id: item for item in self.members}
        fold_ids = tuple(item.outer_fold_id for item in self.outer_folds)
        if len(set(fold_ids)) != len(fold_ids) or set(fold_ids) != {item.outer_fold_id for item in self.fold_selection_references}:
            raise ProjectionAblationInputError("P9-B outer folds and selection references must match")
        if known & set(self.sealed_final_test_sample_ids):
            raise ProjectionAblationInputError("final_test data was read into the P9-B scope")
        for fold in self.outer_folds:
            train, test = set(fold.training_sample_ids), set(fold.test_sample_ids)
            if train & test or train | test != known:
                raise ProjectionAblationInputError("outer fold must partition the explicit non-final cohort")
            if {member_by_id[item].session_id for item in test} != {fold.held_out_group} or fold.held_out_group in {member_by_id[item].session_id for item in train}:
                raise ProjectionAblationInputError("outer fold group membership is inconsistent")
            if set(fold.held_out_physical_state_ids) != {member_by_id[item].physical_state_id for item in test}:
                raise ProjectionAblationInputError("outer fold held physical states are inconsistent")
            for inner in fold.inner_folds:
                inner_train, inner_test = set(inner.train_sample_ids), set(inner.validation_sample_ids)
                if inner_train & inner_test or inner_train | inner_test != train:
                    raise ProjectionAblationInputError("inner fold must partition outer training only")
                inner_groups = {member_by_id[item].session_id for item in inner_test}
                if len(inner_groups) != 1 or inner_groups & {member_by_id[item].session_id for item in inner_train}:
                    raise ProjectionAblationInputError("inner fold group leaked into training")
        expected_seal = _canonical_sha256({"sealed_final_test_sample_ids": list(self.sealed_final_test_sample_ids)})
        if self.sealed_final_test_sha256 != expected_seal:
            raise ProjectionAblationInputError("P9-B final_test seal hash mismatch")
        policy_digest = self.policy_config_sha256.removeprefix("sha256:")
        if not self.policy_config_sha256.startswith("sha256:") or len(policy_digest) != 64 or any(character not in "0123456789abcdef" for character in policy_digest):
            raise ProjectionAblationInputError("P9-B policy config hash is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_scope_id": self.analysis_scope_id,
            "data_origin": self.data_origin,
            "run_purpose": self.run_purpose,
            "dataset_role": self.dataset_role,
            "members": [item.to_dict() for item in self.members],
            "outer_folds": [item.to_dict() for item in self.outer_folds],
            "fold_selection_references": [item.to_dict() for item in self.fold_selection_references],
            "subset_sizes": list(self.subset_sizes),
            "policy_config_sha256": self.policy_config_sha256,
            "sealed_final_test_sample_ids": list(self.sealed_final_test_sample_ids),
            "sealed_final_test_sha256": self.sealed_final_test_sha256,
            "random_state": self.random_state,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "P9ProjectionAblationScope":
        value = dict(payload)
        value["members"] = tuple(AblationScopeMember.from_dict(item) for item in value["members"])
        value["outer_folds"] = tuple(OuterFoldDefinition.from_dict(item) for item in value["outer_folds"])
        value["fold_selection_references"] = tuple(FoldSelectionReference.from_dict(item) for item in value["fold_selection_references"])
        value["subset_sizes"] = tuple(value["subset_sizes"])
        value["sealed_final_test_sample_ids"] = tuple(value["sealed_final_test_sample_ids"])
        return cls(**value)

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class FoldSelectionAuthority:
    scope: ToneSelectionScope
    selected_tone_set: SelectedToneSetArtifact
    selection_manifest_sha256: str


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ToneSubsetDefinition:
    schema_version: str
    outer_fold_id: str
    subset_size: int
    selection_order_candidate_ids: tuple[str, ...]
    feature_order_candidate_ids: tuple[str, ...]
    feature_order_source_indices: tuple[int, ...]
    frequencies_hz: tuple[float, ...]
    dft_bins: tuple[int, ...]
    selection_artifact_sha256: str
    status: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0":
            raise ProjectionAblationInputError("ToneSubsetDefinition schema_version must be 1.0.0")
        if self.status not in {"valid", "warning", "unavailable", "policy_ineligible", "excluded"}:
            raise ProjectionAblationInputError("unsupported tone-subset status")
        if self.subset_size != len(self.selection_order_candidate_ids):
            raise ProjectionAblationInputError("tone-subset size does not match its prefix")
        if len(self.feature_order_candidate_ids) != self.subset_size:
            raise ProjectionAblationInputError("tone-subset feature order is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outer_fold_id": self.outer_fold_id,
            "subset_size": self.subset_size,
            "selection_order_candidate_ids": list(self.selection_order_candidate_ids),
            "feature_order_candidate_ids": list(self.feature_order_candidate_ids),
            "feature_order_source_indices": list(self.feature_order_source_indices),
            "frequencies_hz": list(self.frequencies_hz),
            "dft_bins": list(self.dft_bins),
            "selection_artifact_sha256": self.selection_artifact_sha256,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneSubsetDefinition":
        value = dict(payload)
        for name in (
            "selection_order_candidate_ids", "feature_order_candidate_ids",
            "feature_order_source_indices", "frequencies_hz", "dft_bins", "reason_codes",
        ):
            value[name] = tuple(value[name])
        return cls(**value)

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class DerivedToneProjectionFeatureSet:
    schema_version: str
    outer_fold_id: str
    subset_definition_sha256: str
    selection_artifact_sha256: str
    source_feature_content_sha256: str
    source_feature_contract_sha256: str
    derivation_method: str
    feature_set: FeatureSet
    derived_feature_content_sha256: str
    derived_feature_contract_sha256: str
    selected_candidate_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outer_fold_id": self.outer_fold_id,
            "subset_definition_sha256": self.subset_definition_sha256,
            "selection_artifact_sha256": self.selection_artifact_sha256,
            "source_feature_content_sha256": self.source_feature_content_sha256,
            "source_feature_contract_sha256": self.source_feature_contract_sha256,
            "derivation_method": self.derivation_method,
            "sample_id": self.feature_set.sample_id,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "data_origin": self.feature_set.meta.data_origin.value,
            "dataset_role": self.feature_set.meta.dataset_role.value,
            "source_path": self.feature_set.meta.source_path,
            "derived_feature_content_sha256": self.derived_feature_content_sha256,
            "derived_feature_contract_sha256": self.derived_feature_contract_sha256,
        }


@dataclass(frozen=True, slots=True)
class ClassificationStabilityResult:
    schema_version: str
    outer_fold_id: str
    evaluation_stage: str
    fold_id: str
    subset_size: int
    model_id: str
    status: AblationStatus
    reason_codes: tuple[str, ...]
    broad_sample_ids: tuple[str, ...]
    sparse_sample_ids: tuple[str, ...]
    broad_balanced_accuracy: float | None
    sparse_balanced_accuracy: float | None
    balanced_accuracy_drop: float | None
    broad_macro_f1: float | None
    sparse_macro_f1: float | None
    macro_f1_drop: float | None
    broad_coverage: float
    sparse_coverage: float
    broad_confusion_matrix: tuple[tuple[int, ...], ...]
    sparse_confusion_matrix: tuple[tuple[int, ...], ...]
    prediction_count: int
    test_sample_ids: tuple[str, ...] = ()
    true_directions_deg: tuple[float, ...] = ()
    broad_predictions_deg: tuple[float, ...] = ()
    sparse_predictions_deg: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AblationStatus(self.status))

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__slots__}
        result["status"] = self.status.value
        for name in (
            "reason_codes", "broad_sample_ids", "sparse_sample_ids", "test_sample_ids",
            "true_directions_deg", "broad_predictions_deg", "sparse_predictions_deg",
        ):
            result[name] = list(result[name])
        result["broad_confusion_matrix"] = [list(item) for item in self.broad_confusion_matrix]
        result["sparse_confusion_matrix"] = [list(item) for item in self.sparse_confusion_matrix]
        return result


@dataclass(frozen=True, slots=True)
class MinimumToneCountDecision:
    schema_version: str
    outer_fold_id: str
    status: AblationStatus
    selected_subset_size: int | None
    candidate_subset_sizes: tuple[int, ...]
    passing_subset_sizes: tuple[int, ...]
    reason_codes: tuple[str, ...]
    evidence_stage: str = "inner_validation_only"
    lifecycle: str = "software_validation_candidate"

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AblationStatus(self.status))
        if self.evidence_stage != "inner_validation_only":
            raise ProjectionAblationInputError("minimum tone count must use inner validation only")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outer_fold_id": self.outer_fold_id,
            "status": self.status.value,
            "selected_subset_size": self.selected_subset_size,
            "candidate_subset_sizes": list(self.candidate_subset_sizes),
            "passing_subset_sizes": list(self.passing_subset_sizes),
            "reason_codes": list(self.reason_codes),
            "evidence_stage": self.evidence_stage,
            "lifecycle": self.lifecycle,
        }


@dataclass(frozen=True, slots=True)
class InnerToneCountEvaluation:
    schema_version: str
    outer_fold_id: str
    subset_size: int
    status: AblationStatus
    valid_inner_fold_count: int
    minimum_p4_retention: float | None
    mean_balanced_accuracy_drop: float | None
    mean_macro_f1_drop: float | None
    minimum_coverage: float | None
    inner_fold_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AblationStatus(self.status))

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__slots__}
        result["status"] = self.status.value
        result["inner_fold_ids"] = list(self.inner_fold_ids)
        result["reason_codes"] = list(self.reason_codes)
        return result


@dataclass(frozen=True, slots=True)
class OuterFoldSparseEvaluation:
    schema_version: str
    outer_fold_id: str
    selected_subset_size: int | None
    status: AblationStatus
    p4_results: tuple[P4MetricPreservationResult, ...]
    classification_result: ClassificationStabilityResult | None
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AblationStatus(self.status))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "outer_fold_id": self.outer_fold_id,
            "selected_subset_size": self.selected_subset_size,
            "status": self.status.value,
            "p4_results": [item.to_dict() for item in self.p4_results],
            "classification_result": None if self.classification_result is None else self.classification_result.to_dict(),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class P9ProjectionAblationResult:
    schema_version: str
    processing_status: str
    analysis_scope_id: str
    analysis_scope_sha256: str
    data_origin: str
    run_purpose: str
    scientifically_eligible: bool
    deployment_eligible: bool
    canonical_analysis: bool
    final_test_read: bool
    subset_definitions: tuple[ToneSubsetDefinition, ...]
    derived_features: tuple[DerivedToneProjectionFeatureSet, ...]
    p4_results: tuple[P4MetricPreservationResult, ...]
    inner_classification_results: tuple[ClassificationStabilityResult, ...]
    inner_tone_count_evaluations: tuple[InnerToneCountEvaluation, ...]
    minimum_tone_decisions: tuple[MinimumToneCountDecision, ...]
    outer_fold_evaluations: tuple[OuterFoldSparseEvaluation, ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "processing_status": self.processing_status,
            "analysis_scope_id": self.analysis_scope_id,
            "analysis_scope_sha256": self.analysis_scope_sha256,
            "data_origin": self.data_origin,
            "run_purpose": self.run_purpose,
            "scientifically_eligible": self.scientifically_eligible,
            "deployment_eligible": self.deployment_eligible,
            "canonical_analysis": self.canonical_analysis,
            "final_test_read": self.final_test_read,
            "subset_definitions": [item.to_dict() for item in self.subset_definitions],
            "derived_features": [item.to_dict() for item in self.derived_features],
            "p4_results": [item.to_dict() for item in self.p4_results],
            "inner_classification_results": [item.to_dict() for item in self.inner_classification_results],
            "inner_tone_count_evaluations": [item.to_dict() for item in self.inner_tone_count_evaluations],
            "minimum_tone_decisions": [item.to_dict() for item in self.minimum_tone_decisions],
            "outer_fold_evaluations": [item.to_dict() for item in self.outer_fold_evaluations],
            "warnings": list(self.warnings),
            "failures": list(self.failures),
        }

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class P4MetricPreservationResult:
    schema_version: str
    outer_fold_id: str
    evaluation_stage: str
    fold_id: str
    subset_size: int
    metric_id: str
    status: AblationStatus
    broad_value: float | None
    sparse_value: float | None
    absolute_delta: float | None
    relative_ratio: float | None
    retention: float | None
    retention_mode: str
    source_sample_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AblationStatus(self.status))

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__slots__}
        result["status"] = self.status.value
        result["source_sample_ids"] = list(self.source_sample_ids)
        result["reason_codes"] = list(self.reason_codes)
        return result


def _p4_values(
    features: Mapping[str, FeatureSet],
    sample_ids: tuple[str, ...],
    direction_order: tuple[float, ...],
    metrics_config: Mapping[str, Any],
    reliability_config: Mapping[str, Any],
    cohort_roles: Mapping[str, CohortRole | str],
    scope_id: str,
) -> dict[str, tuple[float | None, str | None]]:
    scope = AnalysisScope(
        "1.0.0", scope_id, "software_validation", ScopeRole.TRAINING,
        sample_ids, None, direction_order,
        SelectionPolicy("p9b-explicit", True, True),
        QCInclusionPolicy("p9b-valid-warning", (QCStatus.VALID, QCStatus.WARNING)),
    )
    metrics = analyze_direction_feature_sets(
        tuple(features[item] for item in sample_ids), scope, metrics_config,
    )
    repeat = next((item for item in metrics.repeatability_summaries if item.repeat_type == "REPOS"), None)
    values: dict[str, tuple[float | None, str | None]] = {
        "effective_rank": (metrics.effective_rank.value, metrics.effective_rank.unavailable_reason),
        "morphology_gain": (metrics.morphology_gain.value, metrics.morphology_gain.unavailable_reason),
        "mean_off_diagonal_pearson": (
            metrics.summary.mean_off_diagonal_pearson,
            None if metrics.summary.mean_off_diagonal_pearson is not None else "direction_correlation_unavailable",
        ),
        "median_direction_rms": (
            metrics.summary.median_direction_rms,
            None if metrics.summary.median_direction_rms is not None else "direction_distance_unavailable",
        ),
        "repos_repeatability_median_rms": (
            None if repeat is None else repeat.median,
            "repos_repeatability_unavailable" if repeat is None else repeat.unavailable_reason,
        ),
    }
    try:
        reliability = compute_tone_reliability(
            tuple(features[item] for item in sample_ids),
            {item: cohort_roles[item] for item in sample_ids},
            repeat_type="REPOS",
            floor_db=float(reliability_config["floor_db"]),
            maximum_raw_weight=float(reliability_config["maximum_raw_weight"]),
            minimum_pairs_per_tone=int(reliability_config["minimum_pairs_per_tone"]),
            minimum_available_tones=int(reliability_config["minimum_available_tones"]),
        )
        stability = reliability.stability_db[reliability.available_mask]
        values["repos_reliability_median_db"] = (
            float(np.median(stability)) if reliability.available and stability.size else None,
            reliability.unavailable_reason,
        )
        values["repos_reliability_available_fraction"] = (
            float(np.mean(reliability.available_mask)), None,
        )
    except (ValueError, KeyError) as exc:
        values["repos_reliability_median_db"] = (None, str(exc))
        values["repos_reliability_available_fraction"] = (None, str(exc))
    return values


def _retention(broad: float, sparse: float, mode: str, floor: float) -> float:
    if abs(sparse - broad) <= floor:
        return 1.0
    if mode == "higher_is_better":
        return float(np.clip(sparse / max(abs(broad), floor), 0.0, 1.0))
    if mode == "lower_is_better":
        return float(np.clip(broad / max(abs(sparse), floor), 0.0, 1.0))
    if mode == "absolute_fidelity":
        return float(max(0.0, 1.0 - abs(sparse - broad) / max(abs(broad), floor)))
    raise ProjectionAblationInputError(f"unsupported P4 retention mode: {mode}")


def evaluate_p4_metric_preservation(
    *,
    broad_features: Mapping[str, FeatureSet],
    sparse_features: Mapping[str, FeatureSet],
    sample_ids: Sequence[str],
    direction_order: Sequence[float],
    metrics_config: Mapping[str, Any],
    reliability_config: Mapping[str, Any],
    cohort_roles: Mapping[str, CohortRole | str],
    retention_modes: Mapping[str, str],
    denominator_floor: float,
    outer_fold_id: str,
    evaluation_stage: str,
    fold_id: str,
    subset_size: int,
) -> tuple[P4MetricPreservationResult, ...]:
    """Reuse P4-A/P4-B calculations and compare an exact same-sample cohort."""
    ordered = tuple(sample_ids)
    if set(broad_features) != set(sparse_features) or set(broad_features) != set(ordered):
        raise ProjectionAblationInputError("broad and sparse P4 cohorts must match exactly")
    directions = tuple(float(item) for item in direction_order)
    broad = _p4_values(broad_features, ordered, directions, metrics_config, reliability_config, cohort_roles, f"p9b:{outer_fold_id}:{fold_id}:broad")
    sparse = _p4_values(sparse_features, ordered, directions, metrics_config, reliability_config, cohort_roles, f"p9b:{outer_fold_id}:{fold_id}:sparse:{subset_size}")
    rows: list[P4MetricPreservationResult] = []
    for metric_id, mode in retention_modes.items():
        broad_value, broad_reason = broad.get(metric_id, (None, "metric_not_reported"))
        sparse_value, sparse_reason = sparse.get(metric_id, (None, "metric_not_reported"))
        reasons = tuple(item for item in (broad_reason, sparse_reason) if item)
        available = broad_value is not None and sparse_value is not None
        rows.append(P4MetricPreservationResult(
            "1.0.0", outer_fold_id, evaluation_stage, fold_id, subset_size, metric_id,
            AblationStatus.VALID if available else AblationStatus.UNAVAILABLE,
            broad_value, sparse_value,
            abs(sparse_value - broad_value) if available else None,
            sparse_value / broad_value if available and abs(broad_value) >= denominator_floor else None,
            _retention(broad_value, sparse_value, mode, denominator_floor) if available else None,
            mode, ordered, reasons,
        ))
    return tuple(rows)


def _classification_matrix(
    features: Mapping[str, FeatureSet],
    sample_ids: Sequence[str],
    indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.vstack([features[item].values[indices] for item in sample_ids]),
        np.asarray([features[item].meta.angle_deg for item in sample_ids], dtype=np.float64),
    )


def evaluate_classification_stability(
    *,
    broad_features: Mapping[str, FeatureSet],
    sparse_features: Mapping[str, FeatureSet],
    train_sample_ids: Sequence[str],
    test_sample_ids: Sequence[str],
    direction_order: Sequence[float],
    model_id: str,
    minimum_training_features: int,
    minimum_prediction_coverage: float,
    random_state: int,
    outer_fold_id: str,
    evaluation_stage: str,
    fold_id: str,
    subset_size: int,
) -> ClassificationStabilityResult:
    """Compare P5-A predictions on exactly the same sweep cohort and fold."""
    ordered = tuple(train_sample_ids) + tuple(test_sample_ids)
    if set(broad_features) != set(sparse_features) or set(ordered) != set(broad_features):
        raise ProjectionAblationInputError("broad and sparse classification cohorts must match exactly")
    if set(train_sample_ids) & set(test_sample_ids):
        raise ProjectionAblationInputError("classification train/test memberships overlap")
    if not train_sample_ids or not test_sample_ids:
        raise ProjectionAblationInputError("classification fold requires train and test samples")
    broad_contract = feature_contract_sha256(next(iter(broad_features.values())))
    sparse_contract = feature_contract_sha256(next(iter(sparse_features.values())))
    if any(feature_contract_sha256(item) != broad_contract for item in broad_features.values()):
        raise ProjectionAblationInputError("broad FeatureSet contract mismatch")
    if any(feature_contract_sha256(item) != sparse_contract for item in sparse_features.values()):
        raise ProjectionAblationInputError("sparse FeatureSet contract mismatch")
    broad_mask = np.logical_and.reduce([broad_features[item].valid_mask for item in train_sample_ids])
    sparse_mask = np.logical_and.reduce([sparse_features[item].valid_mask for item in train_sample_ids])
    broad_indices = np.flatnonzero(broad_mask)
    sparse_indices = np.flatnonzero(sparse_mask)
    reasons: list[str] = []
    if broad_indices.size < minimum_training_features:
        reasons.append("broad_minimum_training_features_not_met")
    if sparse_indices.size < minimum_training_features:
        reasons.append("sparse_minimum_training_features_not_met")
    if reasons:
        return ClassificationStabilityResult(
            "1.0.0", outer_fold_id, evaluation_stage, fold_id, subset_size, model_id,
            AblationStatus.UNAVAILABLE, tuple(reasons), ordered, ordered,
            None, None, None, None, None, None, 0.0, 0.0, (), (), 0,
        )
    broad_train, y_train = _classification_matrix(broad_features, train_sample_ids, broad_indices)
    broad_test, y_test = _classification_matrix(broad_features, test_sample_ids, broad_indices)
    sparse_train, sparse_y_train = _classification_matrix(sparse_features, train_sample_ids, sparse_indices)
    sparse_test, sparse_y_test = _classification_matrix(sparse_features, test_sample_ids, sparse_indices)
    if not np.array_equal(y_train, sparse_y_train) or not np.array_equal(y_test, sparse_y_test):
        raise ProjectionAblationInputError("broad and sparse direction labels differ")
    direction_tuple = tuple(float(item) for item in direction_order)
    broad_prediction = predict_direction_fold(model_id, broad_train, y_train, broad_test, direction_tuple, random_state)
    sparse_prediction = predict_direction_fold(model_id, sparse_train, y_train, sparse_test, direction_tuple, random_state)
    broad_summary = summarize_direction_predictions(y_test, [item[0] for item in broad_prediction], direction_tuple, total_prediction_count=len(test_sample_ids))
    sparse_summary = summarize_direction_predictions(y_test, [item[0] for item in sparse_prediction], direction_tuple, total_prediction_count=len(test_sample_ids))
    if broad_summary.prediction_coverage < minimum_prediction_coverage or sparse_summary.prediction_coverage < minimum_prediction_coverage:
        reasons.append("minimum_prediction_coverage_not_met")
    status = AblationStatus.WARNING if reasons else AblationStatus.VALID
    return ClassificationStabilityResult(
        "1.0.0", outer_fold_id, evaluation_stage, fold_id, subset_size, model_id,
        status, tuple(reasons), ordered, ordered,
        broad_summary.balanced_accuracy, sparse_summary.balanced_accuracy,
        broad_summary.balanced_accuracy - sparse_summary.balanced_accuracy,
        broad_summary.macro_f1, sparse_summary.macro_f1,
        broad_summary.macro_f1 - sparse_summary.macro_f1,
        broad_summary.prediction_coverage, sparse_summary.prediction_coverage,
        broad_summary.confusion_matrix, sparse_summary.confusion_matrix,
        sparse_summary.prediction_count,
        tuple(test_sample_ids), tuple(float(item) for item in y_test),
        tuple(float(item[0]) for item in broad_prediction),
        tuple(float(item[0]) for item in sparse_prediction),
    )


def decide_minimum_tone_count(
    outer_fold_id: str,
    inner_evaluations: Sequence[Mapping[str, Any]],
    *,
    minimum_p4_retention: float,
    maximum_balanced_accuracy_drop: float,
    maximum_macro_f1_drop: float,
    minimum_coverage: float,
    minimum_valid_inner_folds: int,
) -> MinimumToneCountDecision:
    """Choose the smallest preregistered prefix using inner-validation evidence only."""
    sizes = tuple(int(item["subset_size"]) for item in inner_evaluations)
    if not sizes or tuple(sorted(set(sizes))) != sizes:
        raise ProjectionAblationInputError("inner evaluations must have unique increasing subset sizes")
    passing: list[int] = []
    insufficient = False
    for item in inner_evaluations:
        if int(item.get("valid_fold_count", 0)) < minimum_valid_inner_folds:
            insufficient = True
            continue
        if str(item.get("status")) != AblationStatus.VALID.value:
            continue
        if (
            float(item["p4_retention"]) >= minimum_p4_retention
            and float(item["balanced_accuracy_drop"]) <= maximum_balanced_accuracy_drop
            and float(item["macro_f1_drop"]) <= maximum_macro_f1_drop
            and float(item["coverage"]) >= minimum_coverage
        ):
            passing.append(int(item["subset_size"]))
    if passing:
        return MinimumToneCountDecision("1.0.0", outer_fold_id, AblationStatus.VALID, min(passing), sizes, tuple(passing), ())
    reason = "insufficient_valid_inner_folds" if insufficient else "no_subset_met_frozen_thresholds"
    status = AblationStatus.UNAVAILABLE if insufficient else AblationStatus.EXCLUDED
    return MinimumToneCountDecision("1.0.0", outer_fold_id, status, None, sizes, (), (reason,))


def build_tone_subset_definitions(
    outer_fold_id: str,
    selected_tone_set: SelectedToneSetArtifact,
    universe: CandidateToneUniverse,
    subset_sizes: Sequence[int],
    *,
    band_quotas: Sequence[Mapping[str, Any]],
) -> tuple[ToneSubsetDefinition, ...]:
    """Build only deterministic nested prefixes of the frozen P9-A selection rank."""
    if selected_tone_set.outer_fold_id != outer_fold_id:
        raise ProjectionAblationInputError("selected tone set outer fold mismatch")
    if selected_tone_set.candidate_universe_sha256 != universe.sha256:
        raise ProjectionAblationInputError("selected tone set candidate-universe mismatch")
    sizes = tuple(subset_sizes)
    if not sizes or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in sizes):
        raise ProjectionAblationInputError("subset sizes must be positive integers")
    if tuple(sorted(set(sizes))) != sizes:
        raise ProjectionAblationInputError("subset sizes must be unique and strictly increasing")
    ranked = tuple(sorted(selected_tone_set.selected_tones, key=lambda item: (item.selection_rank, item.candidate_id)))
    if sizes[-1] > len(ranked):
        raise ProjectionAblationInputError("subset size exceeds the P9-A selected tone count")
    universe_by_id = {item.candidate_id: item for item in universe.candidates}
    if any(item.candidate_id not in universe_by_id for item in ranked):
        raise ProjectionAblationInputError("P9-A selection contains a tone outside the candidate universe")
    definitions: list[ToneSubsetDefinition] = []
    for size in sizes:
        prefix = ranked[:size]
        feature_order = tuple(sorted(prefix, key=lambda item: item.source_tone_index))
        reasons: list[str] = []
        for left_index, left in enumerate(feature_order):
            for right in feature_order[left_index + 1:]:
                if abs(right.frequency_hz - left.frequency_hz) < selected_tone_set.minimum_spacing_hz:
                    reasons.append("minimum_spacing_hz_not_met")
                if abs(right.dft_bin - left.dft_bin) < selected_tone_set.minimum_spacing_bins:
                    reasons.append("minimum_spacing_bins_not_met")
        for quota in band_quotas:
            count = sum(float(quota["f_min_hz"]) <= item.frequency_hz <= float(quota["f_max_hz"]) for item in prefix)
            if count < int(quota["minimum_count"]):
                reasons.append("band_minimum_not_met:" + str(quota["band_id"]))
            if count > int(quota["maximum_count"]):
                reasons.append("band_maximum_exceeded:" + str(quota["band_id"]))
        definitions.append(ToneSubsetDefinition(
            "1.0.0", outer_fold_id, size,
            tuple(item.candidate_id for item in prefix),
            tuple(item.candidate_id for item in feature_order),
            tuple(item.source_tone_index for item in feature_order),
            tuple(item.frequency_hz for item in feature_order),
            tuple(item.dft_bin for item in feature_order),
            selected_tone_set.sha256,
            "policy_ineligible" if reasons else "valid",
            tuple(dict.fromkeys(reasons)),
        ))
    return tuple(definitions)


def derive_tone_projection_feature_set(
    source: FeatureSet,
    subset: ToneSubsetDefinition,
    *,
    selection_artifact_sha256: str,
) -> DerivedToneProjectionFeatureSet:
    """Project existing tone columns without mutating or recomputing the sweep FeatureSet."""
    if source.feature_kind is not FeatureKind.TONE_PROJECTION_FROM_SWEEP or source.source_measurement_mode is not MeasurementMode.REW_SWEEP:
        raise ProjectionAblationInputError("P9-B projection accepts only sweep tone_projection_from_sweep FeatureSets")
    if selection_artifact_sha256 != subset.selection_artifact_sha256:
        raise ProjectionAblationInputError("projection selection artifact hash mismatch")
    indices = np.asarray(subset.feature_order_source_indices, dtype=np.int64)
    if np.any(indices < 0) or np.any(indices >= len(source.feature_names)):
        raise ProjectionAblationInputError("tone subset index is outside the source FeatureSet")
    selected_quality = tuple(source.feature_quality[int(index)] for index in indices) if source.feature_quality else ()
    selected_weights = None if source.reliability_weights is None else source.reliability_weights[indices]
    preprocessing_id = _canonical_sha256({
        "source_preprocessing_id": source.preprocessing_id,
        "subset_definition_sha256": subset.sha256,
        "method": "immutable_selected_tone_column_projection",
    })
    derived = replace(
        source,
        feature_names=tuple(source.feature_names[int(index)] for index in indices),
        values=source.values[indices],
        valid_mask=source.valid_mask[indices],
        units=tuple(source.units[int(index)] for index in indices),
        preprocessing_id=preprocessing_id,
        tone_set_id="p9b-subset:" + subset.sha256.removeprefix("sha256:")[:16],
        tone_set_sha256=subset.sha256,
        tone_schema_id=subset.sha256,
        reliability_weights=selected_weights,
        feature_quality=selected_quality,
        derivation=None,
    )
    return DerivedToneProjectionFeatureSet(
        "1.0.0", subset.outer_fold_id, subset.sha256, selection_artifact_sha256,
        feature_set_content_sha256(source), feature_contract_sha256(source),
        "immutable_selected_tone_column_projection", derived,
        feature_set_content_sha256(derived), feature_contract_sha256(derived),
        subset.feature_order_candidate_ids,
    )


def validate_fold_selection_scope(
    scope: ToneSelectionScope,
    *,
    outer_fold_id: str,
    ordered_training_sample_ids: Sequence[str],
    held_out_physical_state_ids: Sequence[str],
) -> None:
    """Require one P9-A selection fitted to the exact outer-training fold."""
    if scope.selection_mode is not SelectionMode.FOLD_TRAINING_SELECTION:
        raise ProjectionAblationInputError(
            "outer-fold ablation requires a P9-A fold_training_selection scope"
        )
    if scope.outer_fold_id != outer_fold_id:
        raise ProjectionAblationInputError("P9-A outer fold ID mismatch")
    if scope.fold_training_sample_ids != tuple(ordered_training_sample_ids):
        raise ProjectionAblationInputError("P9-A training membership mismatch")
    if scope.held_out_physical_state_ids != tuple(held_out_physical_state_ids):
        raise ProjectionAblationInputError("P9-A held-out physical-state mismatch")


def validate_fold_selection_authority(
    authority: FoldSelectionAuthority,
    reference: FoldSelectionReference,
    fold: OuterFoldDefinition,
    universe: CandidateToneUniverse,
    features: Mapping[str, FeatureSet],
) -> None:
    """Verify the complete persisted P9-A authority chain for one outer fold."""
    validate_fold_selection_scope(
        authority.scope,
        outer_fold_id=fold.outer_fold_id,
        ordered_training_sample_ids=fold.training_sample_ids,
        held_out_physical_state_ids=fold.held_out_physical_state_ids,
    )
    selected = authority.selected_tone_set
    discriminability_references = {
        item.sample_id: item for item in authority.scope.feature_references
        if item.view_role.value == "discriminability"
    }
    if set(discriminability_references) != set(fold.training_sample_ids):
        raise ProjectionAblationInputError("P9-A discriminability references do not match outer training")
    actual_training_hashes = tuple(
        {
            "sample_id": sample_id,
            "feature_content_sha256": feature_set_content_sha256(features[sample_id]),
        }
        for sample_id in fold.training_sample_ids
    )
    training_feature_content_sha256 = _canonical_sha256({"ordered_training_features": actual_training_hashes})
    for sample_id in fold.training_sample_ids:
        reference_item = discriminability_references[sample_id]
        actual_hash = feature_set_content_sha256(features[sample_id])
        if reference_item.feature_content_sha256 != actual_hash:
            raise ProjectionAblationInputError("P9-B P3-C FeatureSet differs from P9-A training input")
        if selected.input_feature_content_hashes.get(reference_item.artifact_id) != actual_hash:
            raise ProjectionAblationInputError("selected-tone artifact lacks exact P3-C training hash")
    expected = {
        "outer_fold_id": fold.outer_fold_id,
        "selection_scope_sha256": authority.scope.sha256,
        "selection_artifact_sha256": selected.sha256,
        "training_sample_sha256": authority.scope.training_sample_sha256,
        "candidate_universe_sha256": universe.sha256,
        "dataset_qc_result_sha256": authority.scope.dataset_qc_result_sha256,
        "comparison_metrics_result_sha256": authority.scope.comparison_metrics_result_sha256,
        "training_feature_content_sha256": training_feature_content_sha256,
        "selection_manifest_sha256": authority.selection_manifest_sha256,
    }
    if reference.to_dict() != expected:
        raise ProjectionAblationInputError("fold-specific P9-A authority hash mismatch")
    if selected.selection_scope_sha256 != authority.scope.sha256:
        raise ProjectionAblationInputError("selected tones are not bound to the supplied P9-A scope")
    if selected.training_sample_sha256 != authority.scope.training_sample_sha256:
        raise ProjectionAblationInputError("selected tones training membership hash mismatch")
    if selected.candidate_universe_sha256 != universe.sha256:
        raise ProjectionAblationInputError("selected tones candidate-universe hash mismatch")
    if selected.dataset_qc_result_sha256 != authority.scope.dataset_qc_result_sha256:
        raise ProjectionAblationInputError("selected tones P2-B hash mismatch")
    if selected.comparison_metrics_result_sha256 != authority.scope.comparison_metrics_result_sha256:
        raise ProjectionAblationInputError("selected tones P4-B hash mismatch")


def _aggregate_inner_evaluation(
    outer_fold_id: str,
    subset: ToneSubsetDefinition,
    p4_rows: Sequence[P4MetricPreservationResult],
    classification_rows: Sequence[ClassificationStabilityResult],
) -> InnerToneCountEvaluation:
    fold_ids = tuple(sorted({item.fold_id for item in classification_rows}))
    valid_classification = tuple(item for item in classification_rows if item.status is AblationStatus.VALID)
    p4_by_fold: dict[str, list[P4MetricPreservationResult]] = {}
    for row in p4_rows:
        p4_by_fold.setdefault(row.fold_id, []).append(row)
    valid_fold_ids = tuple(
        item.fold_id for item in valid_classification
        if p4_by_fold.get(item.fold_id)
        and all(row.status is AblationStatus.VALID and row.retention is not None for row in p4_by_fold[item.fold_id])
    )
    if subset.status != AblationStatus.VALID.value:
        return InnerToneCountEvaluation(
            "1.0.0", outer_fold_id, subset.subset_size, AblationStatus.POLICY_INELIGIBLE,
            0, None, None, None, None, fold_ids, subset.reason_codes,
        )
    if not valid_fold_ids:
        return InnerToneCountEvaluation(
            "1.0.0", outer_fold_id, subset.subset_size, AblationStatus.UNAVAILABLE,
            0, None, None, None, None, fold_ids, ("no_valid_inner_folds",),
        )
    valid_cls = tuple(item for item in valid_classification if item.fold_id in valid_fold_ids)
    valid_p4 = tuple(row for row in p4_rows if row.fold_id in valid_fold_ids)
    return InnerToneCountEvaluation(
        "1.0.0", outer_fold_id, subset.subset_size, AblationStatus.VALID,
        len(valid_fold_ids), min(float(item.retention) for item in valid_p4 if item.retention is not None),
        float(np.mean([item.balanced_accuracy_drop for item in valid_cls if item.balanced_accuracy_drop is not None])),
        float(np.mean([item.macro_f1_drop for item in valid_cls if item.macro_f1_drop is not None])),
        min(item.sparse_coverage for item in valid_cls), valid_fold_ids, (),
    )


def analyze_projection_ablation(
    features: Mapping[str, FeatureSet],
    scope: P9ProjectionAblationScope,
    universe: CandidateToneUniverse,
    authorities: Mapping[str, FoldSelectionAuthority],
    config: Mapping[str, Any],
    *,
    direction_metrics_config: Mapping[str, Any],
    reliability_config: Mapping[str, Any],
    band_quotas: Sequence[Mapping[str, Any]],
) -> P9ProjectionAblationResult:
    """Run leakage-safe nested sweep projection ablation over explicit artifacts."""
    if _canonical_sha256(config) != scope.policy_config_sha256:
        raise ProjectionAblationInputError("P9-B config hash does not match the frozen scope")
    if tuple(int(item) for item in config["subset_sizes"]) != scope.subset_sizes:
        raise ProjectionAblationInputError("P9-B configured subset sizes do not match scope")
    if config.get("final_test_policy") != "sealed" or config.get("cross_mode") != "disabled":
        raise ProjectionAblationInputError("P9-B final-test/cross-mode gate is not active")
    member_ids = tuple(item.sample_id for item in scope.members)
    if set(features) != set(member_ids):
        raise ProjectionAblationInputError("FeatureSet inputs must exactly match the explicit P9-B scope")
    if any(
        item.feature_kind is not FeatureKind.TONE_PROJECTION_FROM_SWEEP
        or item.source_measurement_mode is not MeasurementMode.REW_SWEEP
        for item in features.values()
    ):
        raise ProjectionAblationInputError("P9-B accepts persisted sweep tone projections only")
    if any(item.meta.data_origin.value != "simulated" or item.meta.dataset_role.value != "software_validation" for item in features.values()):
        raise ProjectionAblationInputError("P9-B inputs must remain simulated software_validation")
    if set(authorities) != {item.outer_fold_id for item in scope.outer_folds}:
        raise ProjectionAblationInputError("one fold-specific P9-A authority is required per outer fold")
    reference_by_fold = {item.outer_fold_id: item for item in scope.fold_selection_references}
    cohort_roles = {item.sample_id: item.cohort_role for item in scope.members}
    directions = tuple(sorted({item.direction_angle_deg for item in scope.members}))
    all_subsets: list[ToneSubsetDefinition] = []
    all_derived: list[DerivedToneProjectionFeatureSet] = []
    all_p4: list[P4MetricPreservationResult] = []
    all_inner_classification: list[ClassificationStabilityResult] = []
    inner_evaluations: list[InnerToneCountEvaluation] = []
    decisions: list[MinimumToneCountDecision] = []
    outer_evaluations: list[OuterFoldSparseEvaluation] = []
    for fold in scope.outer_folds:
        authority = authorities[fold.outer_fold_id]
        validate_fold_selection_authority(authority, reference_by_fold[fold.outer_fold_id], fold, universe, features)
        subsets = build_tone_subset_definitions(
            fold.outer_fold_id, authority.selected_tone_set, universe, scope.subset_sizes,
            band_quotas=band_quotas,
        )
        all_subsets.extend(subsets)
        derived_by_size: dict[int, dict[str, FeatureSet]] = {}
        for subset in subsets:
            projected: dict[str, FeatureSet] = {}
            for sample_id in member_ids:
                wrapper = derive_tone_projection_feature_set(
                    features[sample_id], subset,
                    selection_artifact_sha256=authority.selected_tone_set.sha256,
                )
                all_derived.append(wrapper)
                projected[sample_id] = wrapper.feature_set
            derived_by_size[subset.subset_size] = projected
        evaluations_by_size: list[InnerToneCountEvaluation] = []
        for subset in subsets:
            subset_p4: list[P4MetricPreservationResult] = []
            subset_classification: list[ClassificationStabilityResult] = []
            if subset.status == AblationStatus.VALID.value:
                for inner in fold.inner_folds:
                    train_ids = inner.train_sample_ids
                    p4_broad = {item: features[item] for item in train_ids}
                    p4_sparse = {item: derived_by_size[subset.subset_size][item] for item in train_ids}
                    p4_rows = evaluate_p4_metric_preservation(
                        broad_features=p4_broad, sparse_features=p4_sparse, sample_ids=train_ids,
                        direction_order=directions, metrics_config=direction_metrics_config,
                        reliability_config=reliability_config, cohort_roles=cohort_roles,
                        retention_modes=config["p4_retention_modes"],
                        denominator_floor=float(config["p4_denominator_floor"]),
                        outer_fold_id=fold.outer_fold_id, evaluation_stage="inner_validation",
                        fold_id=inner.inner_fold_id, subset_size=subset.subset_size,
                    )
                    subset_p4.extend(p4_rows)
                    cv_ids = inner.train_sample_ids + inner.validation_sample_ids
                    subset_classification.append(evaluate_classification_stability(
                        broad_features={item: features[item] for item in cv_ids},
                        sparse_features={item: derived_by_size[subset.subset_size][item] for item in cv_ids},
                        train_sample_ids=inner.train_sample_ids,
                        test_sample_ids=inner.validation_sample_ids,
                        direction_order=directions, model_id=str(config["model"]),
                        minimum_training_features=int(config["minimum_training_features"]),
                        minimum_prediction_coverage=float(config["minimum_prediction_coverage"]),
                        random_state=scope.random_state, outer_fold_id=fold.outer_fold_id,
                        evaluation_stage="inner_validation", fold_id=inner.inner_fold_id,
                        subset_size=subset.subset_size,
                    ))
            all_p4.extend(subset_p4)
            all_inner_classification.extend(subset_classification)
            aggregate = _aggregate_inner_evaluation(fold.outer_fold_id, subset, subset_p4, subset_classification)
            evaluations_by_size.append(aggregate)
            inner_evaluations.append(aggregate)
        policy = config["decision_policy"]
        decision = decide_minimum_tone_count(
            fold.outer_fold_id,
            tuple({
                "subset_size": item.subset_size,
                "status": item.status.value,
                "p4_retention": item.minimum_p4_retention if item.minimum_p4_retention is not None else 0.0,
                "balanced_accuracy_drop": item.mean_balanced_accuracy_drop if item.mean_balanced_accuracy_drop is not None else float("inf"),
                "macro_f1_drop": item.mean_macro_f1_drop if item.mean_macro_f1_drop is not None else float("inf"),
                "coverage": item.minimum_coverage if item.minimum_coverage is not None else 0.0,
                "valid_fold_count": item.valid_inner_fold_count,
            } for item in evaluations_by_size),
            minimum_p4_retention=float(policy["minimum_p4_retention"]),
            maximum_balanced_accuracy_drop=float(policy["maximum_balanced_accuracy_drop"]),
            maximum_macro_f1_drop=float(policy["maximum_macro_f1_drop"]),
            minimum_coverage=float(policy["minimum_prediction_coverage"]),
            minimum_valid_inner_folds=int(config["minimum_valid_inner_folds"]),
        )
        decisions.append(decision)
        if decision.selected_subset_size is None:
            outer_evaluations.append(OuterFoldSparseEvaluation(
                "1.0.0", fold.outer_fold_id, None, decision.status, (), None, decision.reason_codes,
            ))
            continue
        selected_size = decision.selected_subset_size
        test_ids = fold.test_sample_ids
        outer_p4 = evaluate_p4_metric_preservation(
            broad_features={item: features[item] for item in test_ids},
            sparse_features={item: derived_by_size[selected_size][item] for item in test_ids},
            sample_ids=test_ids, direction_order=directions,
            metrics_config=direction_metrics_config, reliability_config=reliability_config,
            cohort_roles=cohort_roles, retention_modes=config["p4_retention_modes"],
            denominator_floor=float(config["p4_denominator_floor"]),
            outer_fold_id=fold.outer_fold_id, evaluation_stage="outer_test",
            fold_id=fold.outer_fold_id, subset_size=selected_size,
        )
        all_p4.extend(outer_p4)
        outer_ids = fold.training_sample_ids + fold.test_sample_ids
        outer_classification = evaluate_classification_stability(
            broad_features={item: features[item] for item in outer_ids},
            sparse_features={item: derived_by_size[selected_size][item] for item in outer_ids},
            train_sample_ids=fold.training_sample_ids, test_sample_ids=fold.test_sample_ids,
            direction_order=directions, model_id=str(config["model"]),
            minimum_training_features=int(config["minimum_training_features"]),
            minimum_prediction_coverage=float(config["minimum_prediction_coverage"]),
            random_state=scope.random_state, outer_fold_id=fold.outer_fold_id,
            evaluation_stage="outer_test", fold_id=fold.outer_fold_id,
            subset_size=selected_size,
        )
        status = AblationStatus.WARNING if outer_classification.status is AblationStatus.WARNING or any(item.status is not AblationStatus.VALID for item in outer_p4) else AblationStatus.VALID
        outer_evaluations.append(OuterFoldSparseEvaluation(
            "1.0.0", fold.outer_fold_id, selected_size, status, outer_p4,
            outer_classification, (),
        ))
    failures = tuple(
        f"{item.outer_fold_id}:{','.join(item.reason_codes)}"
        for item in decisions if item.selected_subset_size is None
    )
    return P9ProjectionAblationResult(
        "1.0.0", "completed" if not failures else "completed_with_unavailable_folds",
        scope.analysis_scope_id, scope.sha256, "simulated", "software_validation",
        False, False, False, False, tuple(all_subsets), tuple(all_derived), tuple(all_p4),
        tuple(all_inner_classification), tuple(inner_evaluations), tuple(decisions),
        tuple(outer_evaluations), (), failures,
    )

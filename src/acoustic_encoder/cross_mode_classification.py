"""P5-B leakage-safe four-protocol classification over matched-tone FeatureSets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, precision_recall_fscore_support

from .classification import predict_direction_fold
from .comparison_metrics import FrequencyBand, feature_frequencies_hz, frequency_band_mask
from .dataset_quality_control import (
    CohortRole,
    DatasetQCReference,
    DatasetQCResult,
    feature_set_content_sha256,
    validate_dataset_qc_reference,
)
from .research_gate import RunPurpose, enforce_research_gate, normalize_run_purpose
from .schemas import DataOrigin, DatasetRole, FeatureKind, FeatureSet, MeasurementMode
from .tone_features import assert_matched_tone_schema


class CrossModeClassificationInputError(ValueError):
    """Raised when an explicit P5-B contract cannot be trusted."""


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _sha(value: str, label: str, *, prefix_required: bool = True) -> str:
    text = str(value)
    digest = text.removeprefix("sha256:")
    if (prefix_required and not text.startswith("sha256:")) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise CrossModeClassificationInputError(f"{label} must be a lowercase SHA-256")
    return text


def _text(value: str, label: str) -> str:
    if not str(value).strip():
        raise CrossModeClassificationInputError(f"{label} must be non-empty")
    return str(value)


@dataclass(frozen=True, slots=True)
class ComparisonMetricsReference:
    analysis_scope_id: str
    comparison_scope_sha256: str
    comparison_result_sha256: str
    comparison_manifest_sha256: str

    def __post_init__(self) -> None:
        _text(self.analysis_scope_id, "comparison analysis_scope_id")
        for name in ("comparison_scope_sha256", "comparison_result_sha256", "comparison_manifest_sha256"):
            _sha(getattr(self, name), name)

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComparisonMetricsReference":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class CrossModeFeatureReference:
    artifact_id: str
    sample_id: str
    measurement_mode: MeasurementMode
    feature_kind: FeatureKind
    feature_content_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "measurement_mode", MeasurementMode(self.measurement_mode))
        object.__setattr__(self, "feature_kind", FeatureKind(self.feature_kind))
        _text(self.artifact_id, "cross-mode artifact_id")
        _text(self.sample_id, "cross-mode sample_id")
        _sha(self.feature_content_sha256, "cross-mode FeatureSet content hash")

    def to_dict(self) -> dict[str, str]:
        return {"artifact_id": self.artifact_id, "sample_id": self.sample_id, "measurement_mode": self.measurement_mode.value, "feature_kind": self.feature_kind.value, "feature_content_sha256": self.feature_content_sha256}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeFeatureReference":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class CrossModeGroupSpec:
    cross_mode_group_id: str
    physical_state_id: str
    cohort_role: CohortRole
    configuration_id: str
    direction_id: str
    direction_angle_deg: float
    session_id: str | None
    repeat_type: str | None
    repeat_id: str | None
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str | None
    sweep_artifact_ids: tuple[str, ...]
    multisine_artifact_ids: tuple[str, ...]
    p4b_match_pair_ids: tuple[str, ...]
    selection_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_role", CohortRole(self.cohort_role))
        for name in ("cross_mode_group_id", "physical_state_id", "configuration_id", "direction_id", "selection_reason"):
            _text(getattr(self, name), name)
        if not np.isfinite(self.direction_angle_deg) or not 0 <= self.direction_angle_deg < 360:
            raise CrossModeClassificationInputError("direction_angle_deg must be in [0, 360)")
        for name in ("sweep_artifact_ids", "multisine_artifact_ids", "p4b_match_pair_ids"):
            values = getattr(self, name)
            if not values or len(set(values)) != len(values) or any(not str(x).strip() for x in values):
                raise CrossModeClassificationInputError(f"{name} must be non-empty and unique")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__slots__}
        result["cohort_role"] = self.cohort_role.value
        for name in ("sweep_artifact_ids", "multisine_artifact_ids", "p4b_match_pair_ids"):
            result[name] = list(result[name])
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeGroupSpec":
        value = dict(payload)
        for name in ("sweep_artifact_ids", "multisine_artifact_ids", "p4b_match_pair_ids"):
            value[name] = tuple(value[name])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class OuterFoldSpec:
    outer_fold_id: str
    split_protocol: str
    held_out_cross_mode_group_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.outer_fold_id, "outer_fold_id")
        if self.split_protocol not in {"leave_one_session_out", "leave_one_reposition_round_out", "leave_one_assembly_out"}:
            raise CrossModeClassificationInputError("unsupported outer split protocol")
        if not self.held_out_cross_mode_group_ids or len(set(self.held_out_cross_mode_group_ids)) != len(self.held_out_cross_mode_group_ids):
            raise CrossModeClassificationInputError("held-out group IDs must be non-empty and unique")

    def to_dict(self) -> dict[str, Any]:
        return {"outer_fold_id": self.outer_fold_id, "split_protocol": self.split_protocol, "held_out_cross_mode_group_ids": list(self.held_out_cross_mode_group_ids)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OuterFoldSpec":
        return cls(str(payload["outer_fold_id"]), str(payload["split_protocol"]), tuple(payload["held_out_cross_mode_group_ids"]))


@dataclass(frozen=True, slots=True)
class CrossModeClassificationScope:
    schema_version: str
    classification_scope_id: str
    dataset_analysis_scope_id: str
    run_purpose: RunPurpose
    analysis_tier: str
    dataset_role: DatasetRole
    cross_validation_role: CohortRole
    configuration_id: str
    direction_order_deg: tuple[float, ...]
    feature_names: tuple[str, ...]
    units: tuple[str, ...]
    tone_set_id: str
    tone_set_sha256: str
    tone_schema_id: str
    normalization_method: str
    sweep_preprocessing_id: str
    multisine_preprocessing_id: str
    feature_references: tuple[CrossModeFeatureReference, ...]
    groups: tuple[CrossModeGroupSpec, ...]
    outer_folds: tuple[OuterFoldSpec, ...]
    transfer_protocols: tuple[str, ...]
    models: tuple[str, ...]
    band_ids: tuple[str, ...]
    random_state: int
    dataset_qc_reference: DatasetQCReference
    comparison_metrics_reference: ComparisonMetricsReference

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0": raise CrossModeClassificationInputError("CrossModeClassificationScope schema_version must be 1.0.0")
        object.__setattr__(self, "run_purpose", normalize_run_purpose(self.run_purpose))
        object.__setattr__(self, "dataset_role", DatasetRole(self.dataset_role))
        object.__setattr__(self, "cross_validation_role", CohortRole(self.cross_validation_role))
        if self.analysis_tier != "canonical_cohort": raise CrossModeClassificationInputError("P5-B requires canonical_cohort")
        if self.run_purpose is not RunPurpose.SOFTWARE_VALIDATION or self.dataset_role is not DatasetRole.SOFTWARE_VALIDATION: raise CrossModeClassificationInputError("DEV-C9 P5-B is limited to software_validation")
        if self.cross_validation_role not in {CohortRole.DEVELOPMENT, CohortRole.TRAINING}: raise CrossModeClassificationInputError("cross_validation_role must be development or training")
        for name in ("classification_scope_id", "dataset_analysis_scope_id", "configuration_id", "tone_set_id", "normalization_method"):
            _text(getattr(self, name), name)
        _sha(self.tone_set_sha256, "tone_set_sha256", prefix_required=False)
        for name in ("tone_schema_id", "sweep_preprocessing_id", "multisine_preprocessing_id"):
            _sha(getattr(self, name), name)
        if not self.feature_names or len(self.feature_names) != len(self.units): raise CrossModeClassificationInputError("feature_names and units must be non-empty and aligned")
        if not self.direction_order_deg or len(set(self.direction_order_deg)) != len(self.direction_order_deg) or any(not np.isfinite(item) or not 0 <= item < 360 for item in self.direction_order_deg): raise CrossModeClassificationInputError("direction order must be finite, unique, and in [0, 360)")
        expected_protocols = {"sweep_to_sweep", "multisine_to_multisine", "sweep_to_multisine", "sweep_plus_multisine_to_multisine"}
        if set(self.transfer_protocols) != expected_protocols or len(self.transfer_protocols) != 4: raise CrossModeClassificationInputError("all four transfer protocols are required exactly once")
        if not self.models or len(set(self.models)) != len(self.models) or set(self.models) - {"nearest_template_correlation", "nearest_centroid", "logistic_regression"}: raise CrossModeClassificationInputError("unsupported or duplicate model")
        if not self.band_ids or len(set(self.band_ids)) != len(self.band_ids): raise CrossModeClassificationInputError("band_ids must be non-empty and unique")
        refs = [item.artifact_id for item in self.feature_references]
        if not refs or len(set(refs)) != len(refs): raise CrossModeClassificationInputError("FeatureSet artifact IDs must be non-empty and unique")
        if len({item.sample_id for item in self.feature_references}) != len(self.feature_references): raise CrossModeClassificationInputError("FeatureSet sample IDs must be unique")
        group_ids = [item.cross_mode_group_id for item in self.groups]
        if not group_ids or len(set(group_ids)) != len(group_ids): raise CrossModeClassificationInputError("cross-mode group IDs must be non-empty and unique")
        physical = [item.physical_state_id for item in self.groups]
        if len(set(physical)) != len(physical): raise CrossModeClassificationInputError("one physical_state_id cannot span multiple cross-mode groups")
        if any(item.configuration_id != self.configuration_id or item.direction_angle_deg not in self.direction_order_deg for item in self.groups): raise CrossModeClassificationInputError("cross-mode group configuration/direction contract mismatch")
        pair_ids = [pair for group in self.groups for pair in group.p4b_match_pair_ids]
        if len(set(pair_ids)) != len(pair_ids): raise CrossModeClassificationInputError("P4-B match pair IDs cannot span multiple cross-mode groups")
        assigned = [artifact for group in self.groups for artifact in (*group.sweep_artifact_ids, *group.multisine_artifact_ids)]
        if len(assigned) != len(set(assigned)) or set(assigned) != set(refs): raise CrossModeClassificationInputError("every artifact must map to exactly one explicit cross-mode group")
        known_groups = set(group_ids)
        fold_ids = [fold.outer_fold_id for fold in self.outer_folds]
        if not fold_ids or len(set(fold_ids)) != len(fold_ids): raise CrossModeClassificationInputError("outer fold IDs must be non-empty and unique")
        if any(set(fold.held_out_cross_mode_group_ids) - known_groups for fold in self.outer_folds): raise CrossModeClassificationInputError("outer fold references an unknown group")
        fold_partitions = [(fold.split_protocol, tuple(sorted(fold.held_out_cross_mode_group_ids))) for fold in self.outer_folds]
        if len(set(fold_partitions)) != len(fold_partitions): raise CrossModeClassificationInputError("outer folds cannot duplicate a held physical-state partition")
        if not isinstance(self.random_state, int) or self.random_state < 0: raise CrossModeClassificationInputError("random_state must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "classification_scope_id": self.classification_scope_id,
            "dataset_analysis_scope_id": self.dataset_analysis_scope_id, "run_purpose": self.run_purpose.value,
            "analysis_tier": self.analysis_tier, "dataset_role": self.dataset_role.value,
            "cross_validation_role": self.cross_validation_role.value, "configuration_id": self.configuration_id,
            "direction_order_deg": list(self.direction_order_deg), "feature_names": list(self.feature_names), "units": list(self.units),
            "tone_set_id": self.tone_set_id, "tone_set_sha256": self.tone_set_sha256, "tone_schema_id": self.tone_schema_id,
            "normalization_method": self.normalization_method, "sweep_preprocessing_id": self.sweep_preprocessing_id,
            "multisine_preprocessing_id": self.multisine_preprocessing_id,
            "feature_references": [x.to_dict() for x in self.feature_references], "groups": [x.to_dict() for x in self.groups],
            "outer_folds": [x.to_dict() for x in self.outer_folds], "transfer_protocols": list(self.transfer_protocols),
            "models": list(self.models), "band_ids": list(self.band_ids), "random_state": self.random_state,
            "dataset_qc_reference": self.dataset_qc_reference.to_dict(), "comparison_metrics_reference": self.comparison_metrics_reference.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeClassificationScope":
        required = {
            "schema_version", "classification_scope_id", "dataset_analysis_scope_id",
            "run_purpose", "analysis_tier", "dataset_role", "cross_validation_role",
            "configuration_id", "direction_order_deg", "feature_names", "units",
            "tone_set_id", "tone_set_sha256", "tone_schema_id", "normalization_method",
            "sweep_preprocessing_id", "multisine_preprocessing_id", "feature_references",
            "groups", "outer_folds", "transfer_protocols", "models", "band_ids",
            "random_state", "dataset_qc_reference", "comparison_metrics_reference",
        }
        if set(payload) != required:
            raise CrossModeClassificationInputError("CrossModeClassificationScope fields must be explicit")
        value = dict(payload)
        for name in ("direction_order_deg", "feature_names", "units", "transfer_protocols", "models", "band_ids"):
            value[name] = tuple(value[name])
        value["feature_references"] = tuple(CrossModeFeatureReference.from_dict(x) for x in value["feature_references"])
        value["groups"] = tuple(CrossModeGroupSpec.from_dict(x) for x in value["groups"])
        value["outer_folds"] = tuple(OuterFoldSpec.from_dict(x) for x in value["outer_folds"])
        d = value["dataset_qc_reference"]
        value["dataset_qc_reference"] = DatasetQCReference(str(d["analysis_scope_id"]), str(d["dataset_qc_result_sha256"]))
        value["comparison_metrics_reference"] = ComparisonMetricsReference.from_dict(value["comparison_metrics_reference"])
        return cls(**value)

    @property
    def sha256(self) -> str:
        return _hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class ProtocolFoldAudit:
    outer_fold_id: str
    split_protocol: str
    transfer_protocol: str
    held_out_cross_mode_group_ids: tuple[str, ...]
    train_artifact_ids: tuple[str, ...]
    test_artifact_ids: tuple[str, ...]
    train_modes: tuple[str, ...]
    test_mode: str
    valid: bool
    unavailable_reason: str | None = None
    sealed_final_test_artifact_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in (
            "held_out_cross_mode_group_ids",
            "train_artifact_ids",
            "test_artifact_ids",
            "train_modes",
            "sealed_final_test_artifact_ids",
        ):
            payload[name] = list(payload[name])
        return payload


@dataclass(frozen=True, slots=True)
class CrossModeFeatureMaskAudit:
    outer_fold_id: str
    transfer_protocol: str
    band_id: str
    selected_feature_indices: tuple[int, ...]
    selected_feature_names: tuple[str, ...]
    common_tone_count: int
    mask_source: str = "training_samples_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outer_fold_id": self.outer_fold_id,
            "transfer_protocol": self.transfer_protocol,
            "band_id": self.band_id,
            "selected_feature_indices": list(self.selected_feature_indices),
            "selected_feature_names": list(self.selected_feature_names),
            "common_tone_count": self.common_tone_count,
            "mask_source": self.mask_source,
        }


@dataclass(frozen=True, slots=True)
class CompatibilityAudit:
    outer_fold_id: str
    transfer_protocol: str
    band_id: str
    model_id: str
    status: str
    available: bool
    reason: str | None
    normalization_method: str
    p4b_match_pair_ids: tuple[str, ...]
    p4b_mean_bias_db_by_pair: tuple[tuple[str, float | None], ...]
    p4b_bias_applied: bool = False
    calibration_fitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["p4b_match_pair_ids"] = list(self.p4b_match_pair_ids)
        payload["p4b_mean_bias_db_by_pair"] = [
            {"match_pair_id": pair_id, "mean_bias_db": value}
            for pair_id, value in self.p4b_mean_bias_db_by_pair
        ]
        return payload


@dataclass(frozen=True, slots=True)
class TrainingCompositionRecord:
    outer_fold_id: str
    transfer_protocol: str
    measurement_mode: str
    direction_deg: float
    cross_mode_group_count: int
    sample_count: int
    pooling_policy: str
    sample_weighting: str
    class_weighting: str

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


@dataclass(frozen=True, slots=True)
class CrossModePrediction:
    outer_fold_id: str
    split_protocol: str
    transfer_protocol: str
    band_id: str
    model_id: str
    artifact_id: str
    sample_id: str
    cross_mode_group_id: str
    true_direction_deg: float
    predicted_direction_deg: float | None
    second_direction_deg: float | None
    score: float | None
    margin: float | None
    available: bool
    unavailable_reason: str | None
    train_modes: tuple[str, ...]
    test_mode: str
    train_cross_mode_group_ids: tuple[str, ...]
    held_out_cross_mode_group_ids: tuple[str, ...]
    common_tone_count: int
    compatibility_status: str
    configuration_id: str
    train_feature_kinds: tuple[str, ...]
    test_feature_kind: str

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in (
            "train_modes",
            "train_cross_mode_group_ids",
            "held_out_cross_mode_group_ids",
            "train_feature_kinds",
        ):
            payload[name] = list(payload[name])
        return payload


@dataclass(frozen=True, slots=True)
class CrossModeFoldMetric:
    outer_fold_id: str
    split_protocol: str
    transfer_protocol: str
    band_id: str
    model_id: str
    available: bool
    accuracy: float | None
    balanced_accuracy: float | None
    precision_macro: float | None
    recall_macro: float | None
    f1_macro: float | None
    prediction_coverage: float
    test_count: int
    available_prediction_count: int
    common_tone_count: int
    compatibility_status: str
    unavailable_reason: str | None
    configuration_id: str
    train_feature_kinds: tuple[str, ...]
    test_feature_kind: str

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["train_feature_kinds"] = list(self.train_feature_kinds)
        return payload


@dataclass(frozen=True, slots=True)
class TransferGapRecord:
    outer_fold_id: str
    split_protocol: str
    candidate_protocol: str
    baseline_protocol: str
    band_id: str
    model_id: str
    available: bool
    accuracy_gap: float | None
    balanced_accuracy_gap: float | None
    test_artifact_ids: tuple[str, ...]
    unavailable_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["test_artifact_ids"] = list(self.test_artifact_ids)
        return payload


@dataclass(frozen=True, slots=True)
class CrossModeClassificationResult:
    schema_version: str
    classification_scope_id: str
    scope_sha256: str
    config_sha256: str
    processing_status: str
    canonical_analysis: bool
    scientifically_eligible: bool
    p2b_canonical_ready: bool
    p4b_canonical_analysis: bool
    fold_audit: tuple[ProtocolFoldAudit, ...]
    feature_mask_audit: tuple[CrossModeFeatureMaskAudit, ...]
    compatibility_audit: tuple[CompatibilityAudit, ...]
    training_composition: tuple[TrainingCompositionRecord, ...]
    predictions: tuple[CrossModePrediction, ...]
    fold_metrics: tuple[CrossModeFoldMetric, ...]
    transfer_gaps: tuple[TransferGapRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "classification_scope_id": self.classification_scope_id,
            "scope_sha256": self.scope_sha256,
            "config_sha256": self.config_sha256,
            "processing_status": self.processing_status,
            "canonical_analysis": self.canonical_analysis,
            "scientifically_eligible": self.scientifically_eligible,
            "p2b_canonical_ready": self.p2b_canonical_ready,
            "p4b_canonical_analysis": self.p4b_canonical_analysis,
            "fold_audit": [item.to_dict() for item in self.fold_audit],
            "feature_mask_audit": [item.to_dict() for item in self.feature_mask_audit],
            "compatibility_audit": [item.to_dict() for item in self.compatibility_audit],
            "training_composition": [item.to_dict() for item in self.training_composition],
            "predictions": [item.to_dict() for item in self.predictions],
            "fold_metrics": [item.to_dict() for item in self.fold_metrics],
            "transfer_gaps": [item.to_dict() for item in self.transfer_gaps],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeClassificationResult":
        fold_audit = tuple(
            ProtocolFoldAudit(
                **{
                    **item,
                    "held_out_cross_mode_group_ids": tuple(item["held_out_cross_mode_group_ids"]),
                    "train_artifact_ids": tuple(item["train_artifact_ids"]),
                    "test_artifact_ids": tuple(item["test_artifact_ids"]),
                    "train_modes": tuple(item["train_modes"]),
                    "sealed_final_test_artifact_ids": tuple(item.get("sealed_final_test_artifact_ids", ())),
                }
            )
            for item in payload["fold_audit"]
        )
        masks = tuple(
            CrossModeFeatureMaskAudit(
                **{
                    **item,
                    "selected_feature_indices": tuple(item["selected_feature_indices"]),
                    "selected_feature_names": tuple(item["selected_feature_names"]),
                }
            )
            for item in payload["feature_mask_audit"]
        )
        compatibility = tuple(
            CompatibilityAudit(
                **{
                    **item,
                    "p4b_match_pair_ids": tuple(item["p4b_match_pair_ids"]),
                    "p4b_mean_bias_db_by_pair": tuple(
                        (entry["match_pair_id"], entry["mean_bias_db"])
                        for entry in item["p4b_mean_bias_db_by_pair"]
                    ),
                }
            )
            for item in payload["compatibility_audit"]
        )
        predictions = tuple(
            CrossModePrediction(
                **{
                    **item,
                    "train_modes": tuple(item["train_modes"]),
                    "train_cross_mode_group_ids": tuple(item["train_cross_mode_group_ids"]),
                    "held_out_cross_mode_group_ids": tuple(item["held_out_cross_mode_group_ids"]),
                    "train_feature_kinds": tuple(item["train_feature_kinds"]),
                }
            )
            for item in payload["predictions"]
        )
        gaps = tuple(
            TransferGapRecord(
                **{**item, "test_artifact_ids": tuple(item["test_artifact_ids"])}
            )
            for item in payload["transfer_gaps"]
        )
        return cls(
            schema_version=str(payload["schema_version"]),
            classification_scope_id=str(payload["classification_scope_id"]),
            scope_sha256=str(payload["scope_sha256"]),
            config_sha256=str(payload["config_sha256"]),
            processing_status=str(payload["processing_status"]),
            canonical_analysis=bool(payload["canonical_analysis"]),
            scientifically_eligible=bool(payload["scientifically_eligible"]),
            p2b_canonical_ready=bool(payload["p2b_canonical_ready"]),
            p4b_canonical_analysis=bool(payload["p4b_canonical_analysis"]),
            fold_audit=fold_audit,
            feature_mask_audit=masks,
            compatibility_audit=compatibility,
            training_composition=tuple(TrainingCompositionRecord(**item) for item in payload["training_composition"]),
            predictions=predictions,
            fold_metrics=tuple(
                CrossModeFoldMetric(**{**item, "train_feature_kinds": tuple(item["train_feature_kinds"])})
                for item in payload["fold_metrics"]
            ),
            transfer_gaps=gaps,
        )


def _ordered_features(
    artifacts: Mapping[str, FeatureSet], scope: CrossModeClassificationScope
) -> tuple[FeatureSet, ...]:
    expected = {item.artifact_id for item in scope.feature_references}
    if set(artifacts) != expected:
        raise CrossModeClassificationInputError("cross-mode FeatureSet artifact scope mismatch")
    ordered: list[FeatureSet] = []
    for reference in scope.feature_references:
        feature = artifacts[reference.artifact_id]
        if (
            feature.sample_id != reference.sample_id
            or feature.source_measurement_mode is not reference.measurement_mode
            or feature.feature_kind is not reference.feature_kind
            or feature_set_content_sha256(feature) != reference.feature_content_sha256
        ):
            raise CrossModeClassificationInputError(
                f"cross-mode FeatureSet reference mismatch: {reference.artifact_id}"
            )
        expected_kind = (
            FeatureKind.TONE_PROJECTION_FROM_SWEEP
            if reference.measurement_mode is MeasurementMode.REW_SWEEP
            else FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
        )
        expected_preprocessing = (
            scope.sweep_preprocessing_id
            if reference.measurement_mode is MeasurementMode.REW_SWEEP
            else scope.multisine_preprocessing_id
        )
        if reference.feature_kind is not expected_kind:
            raise CrossModeClassificationInputError("cross-mode measurement mode/feature kind mismatch")
        if feature.preprocessing_id != expected_preprocessing:
            raise CrossModeClassificationInputError("cross-mode preprocessing contract mismatch")
        if (
            feature.meta.configuration != scope.configuration_id
            or feature.feature_names != scope.feature_names
            or feature.units != scope.units
            or feature.tone_set_id != scope.tone_set_id
            or feature.tone_set_sha256 != scope.tone_set_sha256
            or feature.tone_schema_id != scope.tone_schema_id
            or feature.normalization_method != scope.normalization_method
        ):
            raise CrossModeClassificationInputError("cross-mode matched-tone contract mismatch")
        ordered.append(feature)
    if ordered:
        sweep = next((item for item in ordered if item.source_measurement_mode is MeasurementMode.REW_SWEEP), None)
        multisine = next((item for item in ordered if item.source_measurement_mode is MeasurementMode.SCHROEDER_MULTISINE), None)
        if sweep is None or multisine is None:
            raise CrossModeClassificationInputError("cross-mode scope requires both measurement modes")
        assert_matched_tone_schema(sweep, multisine)
    return tuple(ordered)


def _validate_comparison_reference(
    scope: CrossModeClassificationScope, comparison_bundle: Mapping[str, Any]
) -> None:
    reference = scope.comparison_metrics_reference
    result = comparison_bundle.get("result", {})
    comparison_scope = comparison_bundle.get("scope", {})
    if (
        comparison_bundle.get("manifest_sha256") != reference.comparison_manifest_sha256
        or comparison_bundle.get("result_sha256") != reference.comparison_result_sha256
        or comparison_scope.get("sha256") != reference.comparison_scope_sha256
        or result.get("analysis_scope_id") != reference.analysis_scope_id
        or result.get("comparison_scope_sha256") != reference.comparison_scope_sha256
    ):
        raise CrossModeClassificationInputError("P4-B comparison reference mismatch")
    if not result.get("canonical_analysis") or not result.get("p2b_canonical_ready"):
        raise CrossModeClassificationInputError("P4-B comparison result is not canonical-ready")
    pairs = result.get("cross_mode_metrics", {}).get("pairs", ())
    by_pair = {item.get("match_pair_id"): item for item in pairs}
    for group in scope.groups:
        for pair_id in group.p4b_match_pair_ids:
            pair = by_pair.get(pair_id)
            if pair is None:
                raise CrossModeClassificationInputError(f"P4-B match pair is missing: {pair_id}")
            if (
                pair.get("sweep_artifact_id") not in group.sweep_artifact_ids
                or pair.get("multisine_artifact_id") not in group.multisine_artifact_ids
            ):
                raise CrossModeClassificationInputError(f"P4-B match pair scope mismatch: {pair_id}")


def _mode_artifacts(group: CrossModeGroupSpec, mode: MeasurementMode) -> tuple[str, ...]:
    return group.sweep_artifact_ids if mode is MeasurementMode.REW_SWEEP else group.multisine_artifact_ids


def _protocol_modes(protocol: str) -> tuple[tuple[MeasurementMode, ...], MeasurementMode]:
    if protocol == "sweep_to_sweep":
        return (MeasurementMode.REW_SWEEP,), MeasurementMode.REW_SWEEP
    if protocol == "multisine_to_multisine":
        return (MeasurementMode.SCHROEDER_MULTISINE,), MeasurementMode.SCHROEDER_MULTISINE
    if protocol == "sweep_to_multisine":
        return (MeasurementMode.REW_SWEEP,), MeasurementMode.SCHROEDER_MULTISINE
    return (
        MeasurementMode.REW_SWEEP,
        MeasurementMode.SCHROEDER_MULTISINE,
    ), MeasurementMode.SCHROEDER_MULTISINE


def _fold_audit(scope: CrossModeClassificationScope) -> tuple[ProtocolFoldAudit, ...]:
    groups = {item.cross_mode_group_id: item for item in scope.groups}
    eligible = {
        group_id: group
        for group_id, group in groups.items()
        if group.cohort_role is scope.cross_validation_role
    }
    sealed_final = tuple(
        artifact
        for group in scope.groups
        if group.cohort_role is CohortRole.FINAL_TEST
        for artifact in (*group.sweep_artifact_ids, *group.multisine_artifact_ids)
    )
    records: list[ProtocolFoldAudit] = []
    for fold in scope.outer_folds:
        held = tuple(fold.held_out_cross_mode_group_ids)
        if set(held) - set(eligible):
            raise CrossModeClassificationInputError("outer fold may only hold out the configured development/training role")
        held_groups = tuple(eligible[group_id] for group_id in held)
        if fold.split_protocol == "leave_one_session_out":
            keys = {group.session_id for group in held_groups}
            if None in keys or len(keys) != 1:
                raise CrossModeClassificationInputError("LOSO fold must hold exactly one explicit session")
            expected = {group_id for group_id, group in eligible.items() if group.session_id in keys}
        elif fold.split_protocol == "leave_one_reposition_round_out":
            if any(group.repeat_type != "REPOS" or group.reposition_round_id is None for group in held_groups):
                raise CrossModeClassificationInputError("LORO is only defined for explicit REPOS rounds")
            keys = {(group.session_id, group.reposition_round_id) for group in held_groups}
            if len(keys) != 1:
                raise CrossModeClassificationInputError("LORO fold must hold exactly one session/round")
            expected = {
                group_id for group_id, group in eligible.items()
                if group.repeat_type == "REPOS" and (group.session_id, group.reposition_round_id) in keys
            }
        else:
            if any(group.repeat_type != "REASM" or group.assembly_id is None for group in held_groups):
                raise CrossModeClassificationInputError("LOAO is only defined for explicit REASM assemblies")
            keys = {(group.session_id, group.assembly_id) for group in held_groups}
            if len(keys) != 1:
                raise CrossModeClassificationInputError("LOAO fold must hold exactly one session/assembly")
            expected = {
                group_id for group_id, group in eligible.items()
                if group.repeat_type == "REASM" and (group.session_id, group.assembly_id) in keys
            }
        if set(held) != expected:
            raise CrossModeClassificationInputError("outer fold does not hold the complete physical-state group")
        train_groups = tuple(group for group_id, group in eligible.items() if group_id not in held)
        test_groups = held_groups
        for protocol in scope.transfer_protocols:
            train_modes, test_mode = _protocol_modes(protocol)
            train_ids = tuple(
                artifact
                for group in train_groups
                for mode in train_modes
                for artifact in _mode_artifacts(group, mode)
            )
            test_ids = tuple(
                artifact for group in test_groups for artifact in _mode_artifacts(group, test_mode)
            )
            records.append(
                ProtocolFoldAudit(
                    fold.outer_fold_id,
                    fold.split_protocol,
                    protocol,
                    held,
                    train_ids,
                    test_ids,
                    tuple(mode.value for mode in train_modes),
                    test_mode.value,
                    bool(train_ids and test_ids),
                    None if train_ids and test_ids else "empty_train_or_test_partition",
                    sealed_final,
                )
            )
    return tuple(records)


def _comparison_pairs(comparison_bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    pairs = comparison_bundle["result"]["cross_mode_metrics"]["pairs"]
    return {str(item["match_pair_id"]): item for item in pairs}


def _compatibility(
    *,
    scope: CrossModeClassificationScope,
    protocol: str,
    model_id: str,
    pair_ids: tuple[str, ...],
    pair_by_id: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
) -> tuple[str, bool, str | None]:
    if protocol in {"sweep_to_sweep", "multisine_to_multisine"}:
        return "same_mode_compatible", True, None
    pairs = tuple(pair_by_id[pair_id] for pair_id in pair_ids)
    absolute = bool(pairs) and all(bool(pair.get("absolute_comparison_available")) for pair in pairs)
    shape = bool(pairs) and all(bool(pair.get("shape_comparison_available")) for pair in pairs)
    cross = config.get("cross_mode", {})
    allowed_shape = set(cross.get("allowed_shape_normalizations", ()))
    if scope.normalization_method in allowed_shape:
        if shape:
            return "shape_compatible", True, None
        return "shape_incompatible", False, "p4b_shape_comparison_unavailable"
    if absolute:
        return "absolute_compatible", True, None
    if model_id == "nearest_template_correlation" and shape:
        return "correlation_shape_only", True, None
    return "absolute_incompatible", False, "absolute_reference_or_calibration_incompatible"


def _group_by_artifact(scope: CrossModeClassificationScope) -> dict[str, CrossModeGroupSpec]:
    return {
        artifact_id: group
        for group in scope.groups
        for artifact_id in (*group.sweep_artifact_ids, *group.multisine_artifact_ids)
    }


def _validate_group_metadata(
    artifacts: Mapping[str, FeatureSet], scope: CrossModeClassificationScope
) -> None:
    for group in scope.groups:
        for artifact_id in (*group.sweep_artifact_ids, *group.multisine_artifact_ids):
            feature = artifacts[artifact_id]
            expected = {
                "configuration": group.configuration_id,
                "angle_deg": group.direction_angle_deg,
                "session_id": group.session_id,
                "repeat_type": group.repeat_type,
                "repeat_id": group.repeat_id,
                "reposition_round_id": group.reposition_round_id,
                "assembly_id": group.assembly_id,
                "acquisition_block_id": group.acquisition_block_id,
            }
            mismatch = [name for name, value in expected.items() if getattr(feature.meta, name) != value]
            if mismatch:
                raise CrossModeClassificationInputError(
                    f"cross-mode group metadata mismatch for {artifact_id}: {', '.join(mismatch)}"
                )


def _training_composition(
    audit: ProtocolFoldAudit,
    artifacts: Mapping[str, FeatureSet],
    group_by_artifact: Mapping[str, CrossModeGroupSpec],
    config: Mapping[str, Any],
) -> tuple[TrainingCompositionRecord, ...]:
    cross = config.get("cross_mode", {})
    rows: list[TrainingCompositionRecord] = []
    keys = sorted(
        {
            (artifacts[artifact_id].source_measurement_mode.value, group_by_artifact[artifact_id].direction_angle_deg)
            for artifact_id in audit.train_artifact_ids
        }
    )
    for mode, direction in keys:
        matching = tuple(
            artifact_id for artifact_id in audit.train_artifact_ids
            if artifacts[artifact_id].source_measurement_mode.value == mode
            and group_by_artifact[artifact_id].direction_angle_deg == direction
        )
        rows.append(
            TrainingCompositionRecord(
                audit.outer_fold_id,
                audit.transfer_protocol,
                mode,
                direction,
                len({group_by_artifact[item].cross_mode_group_id for item in matching}),
                len(matching),
                str(cross.get("pooling_policy", "sample_pooled")),
                str(cross.get("sample_weighting", "uniform")),
                str(cross.get("class_weighting", "balanced")),
            )
        )
    return tuple(rows)


def _transfer_gaps(
    metrics: Sequence[CrossModeFoldMetric],
    predictions: Sequence[CrossModePrediction],
) -> tuple[TransferGapRecord, ...]:
    by_key = {
        (item.outer_fold_id, item.band_id, item.model_id, item.transfer_protocol): item
        for item in metrics
    }
    test_ids = {
        (item.outer_fold_id, item.band_id, item.model_id, item.transfer_protocol): tuple(
            sorted(
                row.artifact_id
                for row in predictions
                if (
                    row.outer_fold_id,
                    row.band_id,
                    row.model_id,
                    row.transfer_protocol,
                ) == (item.outer_fold_id, item.band_id, item.model_id, item.transfer_protocol)
            )
        )
        for item in metrics
    }
    output: list[TransferGapRecord] = []
    baseline_protocol = "multisine_to_multisine"
    candidates = ("sweep_to_multisine", "sweep_plus_multisine_to_multisine")
    for key, baseline in sorted(by_key.items()):
        fold_id, band_id, model_id, protocol = key
        if protocol != baseline_protocol:
            continue
        for candidate_protocol in candidates:
            candidate_key = (fold_id, band_id, model_id, candidate_protocol)
            candidate = by_key.get(candidate_key)
            same_test = test_ids.get(key) == test_ids.get(candidate_key)
            available = bool(candidate and baseline.available and candidate.available and same_test)
            reason = None
            if candidate is None:
                reason = "candidate_protocol_missing"
            elif not same_test:
                reason = "test_cohort_mismatch"
            elif not baseline.available or not candidate.available:
                reason = "fold_metric_unavailable"
            output.append(
                TransferGapRecord(
                    fold_id,
                    baseline.split_protocol,
                    candidate_protocol,
                    baseline_protocol,
                    band_id,
                    model_id,
                    available,
                    None if not available else float(candidate.accuracy - baseline.accuracy),
                    None if not available else float(candidate.balanced_accuracy - baseline.balanced_accuracy),
                    test_ids.get(key, ()),
                    reason,
                )
            )
    return tuple(output)


def analyze_cross_mode_classification(
    artifacts: Mapping[str, FeatureSet],
    scope: CrossModeClassificationScope,
    config: Mapping[str, Any],
    *,
    dataset_qc_result: DatasetQCResult,
    comparison_bundle: Mapping[str, Any],
) -> CrossModeClassificationResult:
    """Run four frozen transfer protocols with fold-local fitting only."""
    ordered = _ordered_features(artifacts, scope)
    _validate_group_metadata(artifacts, scope)
    validate_dataset_qc_reference(
        ordered,
        analysis_scope_id=scope.dataset_analysis_scope_id,
        ordered_sample_ids=tuple(item.sample_id for item in ordered),
        run_purpose=scope.run_purpose,
        reference=scope.dataset_qc_reference,
        result=dataset_qc_result,
        require_canonical_ready=True,
    )
    enforce_research_gate(scope.run_purpose, (feature.meta for feature in ordered))
    if scope.dataset_role is not dataset_qc_result.dataset_role:
        raise CrossModeClassificationInputError("cross-mode/P2-B dataset_role mismatch")
    if dataset_qc_result.data_origin is not DataOrigin.SIMULATED:
        raise CrossModeClassificationInputError("DEV-C9 P5-B accepts simulated validation data only")
    if any(feature.meta.data_origin is not dataset_qc_result.data_origin for feature in ordered):
        raise CrossModeClassificationInputError("cross-mode/P2-B provenance mismatch")
    role_by_sample = {item.sample_id: item.cohort_role for item in dataset_qc_result.input_audit}
    for group in scope.groups:
        for artifact_id in (*group.sweep_artifact_ids, *group.multisine_artifact_ids):
            sample_id = artifacts[artifact_id].sample_id
            if role_by_sample.get(sample_id) is not group.cohort_role:
                raise CrossModeClassificationInputError(f"P2-B cohort role mismatch: {sample_id}")
    _validate_comparison_reference(scope, comparison_bundle)
    configured_transfer = tuple(config.get("cross_mode", {}).get("transfer_protocols", scope.transfer_protocols))
    if configured_transfer != scope.transfer_protocols:
        raise CrossModeClassificationInputError("cross-mode transfer protocol config/scope mismatch")
    audit = _fold_audit(scope)
    bands_payload = config.get("frequency_bands")
    if not isinstance(bands_payload, Sequence):
        raise CrossModeClassificationInputError("classification.frequency_bands must be a sequence")
    bands = {str(item["band_id"]): FrequencyBand(**dict(item)) for item in bands_payload}
    if set(scope.band_ids) - set(bands):
        raise CrossModeClassificationInputError("cross-mode scope references an unknown frequency band")
    minimum_features = int(config.get("minimum_training_features", 2))
    minimum_per_direction = int(config.get("minimum_training_samples_per_direction", 1))
    minimum_coverage = float(config.get("minimum_prediction_coverage", 1.0))
    frequencies = feature_frequencies_hz(scope.feature_names)
    group_by_artifact = _group_by_artifact(scope)
    pair_by_id = _comparison_pairs(comparison_bundle)
    feature_masks: list[CrossModeFeatureMaskAudit] = []
    compatibility_rows: list[CompatibilityAudit] = []
    compositions: list[TrainingCompositionRecord] = []
    predictions: list[CrossModePrediction] = []
    metrics: list[CrossModeFoldMetric] = []
    for fold in audit:
        compositions.extend(_training_composition(fold, artifacts, group_by_artifact, config))
        train_group_ids = tuple(
            sorted({group_by_artifact[item].cross_mode_group_id for item in fold.train_artifact_ids})
        )
        relevant_groups = tuple(
            group for group in scope.groups
            if group.cross_mode_group_id in set((*train_group_ids, *fold.held_out_cross_mode_group_ids))
        )
        pair_ids = tuple(sorted({pair for group in relevant_groups for pair in group.p4b_match_pair_ids}))
        for band_id in scope.band_ids:
            band = bands[band_id]
            train_mask = frequency_band_mask(frequencies, band).copy()
            for artifact_id in fold.train_artifact_ids:
                train_mask &= artifacts[artifact_id].valid_mask
            indices = tuple(int(index) for index in np.flatnonzero(train_mask))
            feature_masks.append(
                CrossModeFeatureMaskAudit(
                    fold.outer_fold_id,
                    fold.transfer_protocol,
                    band_id,
                    indices,
                    tuple(scope.feature_names[index] for index in indices),
                    len(indices),
                )
            )
            y_train = np.asarray(
                [group_by_artifact[item].direction_angle_deg for item in fold.train_artifact_ids],
                dtype=float,
            )
            training_reason: str | None = fold.unavailable_reason
            if len(indices) < max(minimum_features, band.minimum_feature_count):
                training_reason = "insufficient_training_features"
            elif set(y_train) != set(scope.direction_order_deg):
                training_reason = "training_direction_coverage_incomplete"
            elif any(np.sum(y_train == direction) < minimum_per_direction for direction in scope.direction_order_deg):
                training_reason = "insufficient_training_samples_per_direction"
            x_train = (
                np.vstack([artifacts[item].values[list(indices)] for item in fold.train_artifact_ids])
                if indices else np.empty((len(fold.train_artifact_ids), 0), dtype=float)
            )
            for model_id in scope.models:
                compatibility_status, compatible, compatibility_reason = _compatibility(
                    scope=scope,
                    protocol=fold.transfer_protocol,
                    model_id=model_id,
                    pair_ids=pair_ids,
                    pair_by_id=pair_by_id,
                    config=config,
                )
                compatibility_rows.append(
                    CompatibilityAudit(
                        fold.outer_fold_id,
                        fold.transfer_protocol,
                        band_id,
                        model_id,
                        compatibility_status,
                        compatible,
                        compatibility_reason,
                        scope.normalization_method,
                        pair_ids,
                        tuple(
                            (pair_id, pair_by_id[pair_id].get("mean_bias_db"))
                            for pair_id in pair_ids
                        ),
                    )
                )
                available_test_ids = tuple(
                    artifact_id for artifact_id in fold.test_artifact_ids
                    if indices and np.all(artifacts[artifact_id].valid_mask[list(indices)])
                )
                missing_test_ids = tuple(
                    artifact_id for artifact_id in fold.test_artifact_ids
                    if artifact_id not in available_test_ids
                )
                model_rows: list[CrossModePrediction] = []

                def row(
                    artifact_id: str,
                    *,
                    predicted: tuple[float, float | None, float, float | None] | None,
                    reason: str | None,
                ) -> CrossModePrediction:
                    group = group_by_artifact[artifact_id]
                    return CrossModePrediction(
                        fold.outer_fold_id,
                        fold.split_protocol,
                        fold.transfer_protocol,
                        band_id,
                        model_id,
                        artifact_id,
                        artifacts[artifact_id].sample_id,
                        group.cross_mode_group_id,
                        group.direction_angle_deg,
                        None if predicted is None else predicted[0],
                        None if predicted is None else predicted[1],
                        None if predicted is None else predicted[2],
                        None if predicted is None else predicted[3],
                        predicted is not None,
                        reason,
                        fold.train_modes,
                        fold.test_mode,
                        train_group_ids,
                        fold.held_out_cross_mode_group_ids,
                        len(indices),
                        compatibility_status,
                        scope.configuration_id,
                        tuple(sorted({artifacts[item].feature_kind.value for item in fold.train_artifact_ids})),
                        artifacts[artifact_id].feature_kind.value,
                    )

                unavailable_reason = training_reason or (None if compatible else compatibility_reason)
                if unavailable_reason is not None:
                    model_rows.extend(
                        row(artifact_id, predicted=None, reason=unavailable_reason)
                        for artifact_id in fold.test_artifact_ids
                    )
                else:
                    model_rows.extend(
                        row(artifact_id, predicted=None, reason="test_missing_training_mask_tone")
                        for artifact_id in missing_test_ids
                    )
                    if available_test_ids:
                        x_test = np.vstack(
                            [artifacts[item].values[list(indices)] for item in available_test_ids]
                        )
                        try:
                            predicted_rows = predict_direction_fold(
                                model_id,
                                x_train,
                                y_train,
                                x_test,
                                scope.direction_order_deg,
                                scope.random_state,
                            )
                            model_rows.extend(
                                row(artifact_id, predicted=prediction, reason=None)
                                for artifact_id, prediction in zip(
                                    available_test_ids, predicted_rows, strict=True
                                )
                            )
                        except (ValueError, CrossModeClassificationInputError) as error:
                            model_rows.extend(
                                row(artifact_id, predicted=None, reason=str(error))
                                for artifact_id in available_test_ids
                            )
                model_rows.sort(key=lambda item: fold.test_artifact_ids.index(item.artifact_id))
                predictions.extend(model_rows)
                available_rows = tuple(item for item in model_rows if item.available)
                coverage = len(available_rows) / len(model_rows) if model_rows else 0.0
                metric_available = bool(available_rows) and coverage >= minimum_coverage
                if metric_available:
                    truth = [item.true_direction_deg for item in available_rows]
                    predicted = [item.predicted_direction_deg for item in available_rows]
                    accuracy = float(accuracy_score(truth, predicted))
                    balanced = float(balanced_accuracy_score(truth, predicted))
                    precision, recall, f1, _ = precision_recall_fscore_support(
                        truth,
                        predicted,
                        labels=np.asarray(scope.direction_order_deg, dtype=float),
                        average="macro",
                        zero_division=0.0,
                    )
                    metric_reason = None
                else:
                    accuracy = balanced = None
                    precision = recall = f1 = None
                    metric_reason = (
                        unavailable_reason
                        or ("prediction_coverage_below_minimum" if model_rows else "no_test_predictions")
                    )
                metrics.append(
                    CrossModeFoldMetric(
                        fold.outer_fold_id,
                        fold.split_protocol,
                        fold.transfer_protocol,
                        band_id,
                        model_id,
                        metric_available,
                        accuracy,
                        balanced,
                        None if precision is None else float(precision),
                        None if recall is None else float(recall),
                        None if f1 is None else float(f1),
                        coverage,
                        len(model_rows),
                        len(available_rows),
                        len(indices),
                        compatibility_status,
                        metric_reason,
                        scope.configuration_id,
                        tuple(sorted({artifacts[item].feature_kind.value for item in fold.train_artifact_ids})),
                        (
                            artifacts[fold.test_artifact_ids[0]].feature_kind.value
                            if fold.test_artifact_ids else "unavailable"
                        ),
                    )
                )
    gaps = _transfer_gaps(metrics, predictions)
    canonical = scope.analysis_tier == "canonical_cohort"
    scientifically_eligible = (
        canonical
        and scope.run_purpose is RunPurpose.RESEARCH_ANALYSIS
        and dataset_qc_result.scientifically_eligible
        and all(item.meta.eligible_for_scientific_analysis for item in ordered)
    )
    return CrossModeClassificationResult(
        "1.0.0",
        scope.classification_scope_id,
        scope.sha256,
        _hash(dict(config)),
        "completed" if all(item.valid for item in audit) and all(item.available for item in metrics) else "completed_with_unavailable",
        canonical,
        scientifically_eligible,
        dataset_qc_result.canonical_ready,
        True,
        audit,
        tuple(feature_masks),
        tuple(compatibility_rows),
        tuple(compositions),
        tuple(predictions),
        tuple(metrics),
        gaps,
    )

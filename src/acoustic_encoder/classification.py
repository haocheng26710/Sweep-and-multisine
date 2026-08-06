"""P5-A leakage-safe grouped direction classification over persisted FeatureSets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler

from .comparison_metrics import FrequencyBand, feature_frequencies_hz, frequency_band_mask
from .dataset_quality_control import (
    CohortRole,
    DatasetQCReference,
    DatasetQCResult,
    feature_contract_sha256,
    feature_set_content_sha256,
    validate_dataset_qc_reference,
)
from .research_gate import RunPurpose, enforce_research_gate, normalize_run_purpose
from .schemas import DatasetRole, FeatureKind, FeatureSet, MeasurementMode


CLASSIFICATION_SCOPE_SCHEMA_VERSION = "1.0.0"
CLASSIFICATION_RESULT_SCHEMA_VERSION = "1.0.0"


class ClassificationInputError(ValueError):
    """Raised when a P5-A input or leakage contract cannot be trusted."""


@dataclass(frozen=True, slots=True)
class DirectionPredictionSummary:
    balanced_accuracy: float
    macro_f1: float
    prediction_coverage: float
    prediction_count: int
    total_prediction_count: int
    confusion_matrix: tuple[tuple[int, ...], ...]


def summarize_direction_predictions(
    truth: Sequence[float],
    predictions: Sequence[float],
    direction_order: Sequence[float],
    *,
    total_prediction_count: int | None = None,
) -> DirectionPredictionSummary:
    """Summarize P5 predictions using one fixed label order and no fitted state."""
    truth_values = np.asarray(truth, dtype=np.float64)
    prediction_values = np.asarray(predictions, dtype=np.float64)
    labels = np.asarray(direction_order, dtype=np.float64)
    if truth_values.ndim != 1 or prediction_values.ndim != 1 or truth_values.size != prediction_values.size or not truth_values.size:
        raise ClassificationInputError("prediction summary requires matching non-empty 1-D truth and predictions")
    if labels.ndim != 1 or not labels.size or len(set(labels.tolist())) != labels.size:
        raise ClassificationInputError("prediction summary direction order must be non-empty and unique")
    if set(truth_values.tolist()) - set(labels.tolist()) or set(prediction_values.tolist()) - set(labels.tolist()):
        raise ClassificationInputError("prediction summary values must belong to direction_order")
    total = truth_values.size if total_prediction_count is None else total_prediction_count
    if isinstance(total, bool) or not isinstance(total, int) or total < truth_values.size:
        raise ClassificationInputError("total_prediction_count cannot be below available predictions")
    matrix = confusion_matrix(truth_values, prediction_values, labels=labels)
    return DirectionPredictionSummary(
        float(balanced_accuracy_score(truth_values, prediction_values)),
        float(f1_score(truth_values, prediction_values, labels=labels, average="macro", zero_division=0.0)),
        float(truth_values.size / total) if total else 0.0,
        int(truth_values.size),
        int(total),
        tuple(tuple(int(value) for value in row) for row in matrix),
    )


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_text(value: str, label: str) -> str:
    if not str(value).strip():
        raise ClassificationInputError(f"{label} must be non-empty")
    return str(value)


def _require_sha256(value: str, label: str) -> str:
    digest = str(value).removeprefix("sha256:")
    if not str(value).startswith("sha256:") or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ClassificationInputError(f"{label} must be sha256:<lowercase digest>")
    return str(value)


@dataclass(frozen=True, slots=True)
class ClassificationScopeMember:
    sample_id: str
    cohort_role: CohortRole
    direction_id: str
    direction_angle_deg: float
    session_id: str | None
    repeat_type: str | None
    repeat_id: str | None
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str | None
    selection_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_role", CohortRole(self.cohort_role))
        _require_text(self.sample_id, "classification sample_id")
        _require_text(self.direction_id, "classification direction_id")
        _require_text(self.selection_reason, "classification selection_reason")
        if not np.isfinite(self.direction_angle_deg) or not 0.0 <= self.direction_angle_deg < 360.0:
            raise ClassificationInputError("direction_angle_deg must be in [0, 360)")

    @classmethod
    def from_feature_set(cls, feature: FeatureSet, *, cohort_role: CohortRole | str, direction_id: str, selection_reason: str) -> "ClassificationScopeMember":
        if feature.meta.angle_deg is None:
            raise ClassificationInputError("classification FeatureSet requires angle_deg")
        return cls(
            sample_id=feature.sample_id,
            cohort_role=CohortRole(cohort_role),
            direction_id=direction_id,
            direction_angle_deg=float(feature.meta.angle_deg),
            session_id=feature.meta.session_id,
            repeat_type=feature.meta.repeat_type,
            repeat_id=feature.meta.repeat_id,
            reposition_round_id=feature.meta.reposition_round_id,
            assembly_id=feature.meta.assembly_id,
            acquisition_block_id=feature.meta.acquisition_block_id,
            selection_reason=selection_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id, "cohort_role": self.cohort_role.value,
            "direction_id": self.direction_id, "direction_angle_deg": self.direction_angle_deg,
            "session_id": self.session_id, "repeat_type": self.repeat_type,
            "repeat_id": self.repeat_id, "reposition_round_id": self.reposition_round_id,
            "assembly_id": self.assembly_id, "acquisition_block_id": self.acquisition_block_id,
            "selection_reason": self.selection_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ClassificationScopeMember":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ClassificationFeatureReference:
    artifact_id: str
    sample_id: str
    feature_content_sha256: str

    def __post_init__(self) -> None:
        _require_text(self.artifact_id, "classification artifact_id")
        _require_text(self.sample_id, "classification feature sample_id")
        _require_sha256(self.feature_content_sha256, "classification FeatureSet content hash")

    def to_dict(self) -> dict[str, str]:
        return {"artifact_id": self.artifact_id, "sample_id": self.sample_id, "feature_content_sha256": self.feature_content_sha256}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ClassificationFeatureReference":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ClassificationScope:
    schema_version: str
    classification_scope_id: str
    run_purpose: RunPurpose
    analysis_tier: str
    dataset_role: DatasetRole
    measurement_mode: MeasurementMode
    configuration_id: str
    feature_kind: str
    preprocessing_id: str
    tone_set_id: str | None
    direction_order_deg: tuple[float, ...]
    members: tuple[ClassificationScopeMember, ...]
    feature_references: tuple[ClassificationFeatureReference, ...]
    protocols: tuple[str, ...]
    models: tuple[str, ...]
    band_ids: tuple[str, ...]
    random_state: int
    dataset_qc_reference: DatasetQCReference

    def __post_init__(self) -> None:
        if self.schema_version != CLASSIFICATION_SCOPE_SCHEMA_VERSION:
            raise ClassificationInputError("ClassificationScope schema_version must be 1.0.0")
        object.__setattr__(self, "run_purpose", normalize_run_purpose(self.run_purpose))
        object.__setattr__(self, "dataset_role", DatasetRole(self.dataset_role))
        object.__setattr__(self, "measurement_mode", MeasurementMode(self.measurement_mode))
        _require_text(self.classification_scope_id, "classification_scope_id")
        _require_text(self.configuration_id, "configuration_id")
        _require_text(self.preprocessing_id, "preprocessing_id")
        try:
            FeatureKind(self.feature_kind)
        except ValueError as exc:
            raise ClassificationInputError("unsupported classification feature_kind") from exc
        if self.analysis_tier not in {"provisional_validation", "canonical_cohort"}:
            raise ClassificationInputError("analysis_tier must be provisional_validation or canonical_cohort")
        if not isinstance(self.random_state, int) or self.random_state < 0:
            raise ClassificationInputError("random_state must be a non-negative integer")
        if not self.members or not self.feature_references:
            raise ClassificationInputError("classification scope must list members and FeatureSets")
        member_ids = tuple(item.sample_id for item in self.members)
        reference_ids = tuple(item.sample_id for item in self.feature_references)
        if member_ids != reference_ids or len(set(member_ids)) != len(member_ids):
            raise ClassificationInputError("classification member and FeatureSet order must match exactly and be unique")
        if len({item.artifact_id for item in self.feature_references}) != len(self.feature_references):
            raise ClassificationInputError("classification artifact IDs must be unique")
        if not self.direction_order_deg or len(set(self.direction_order_deg)) != len(self.direction_order_deg):
            raise ClassificationInputError("direction_order_deg must be non-empty and unique")
        if any(item.direction_angle_deg not in self.direction_order_deg for item in self.members):
            raise ClassificationInputError("scope member direction is absent from direction_order_deg")
        allowed_protocols = {"leave_one_session_out", "leave_one_reposition_round_out", "leave_one_assembly_out"}
        allowed_models = {"nearest_template_correlation", "nearest_centroid", "logistic_regression"}
        if not self.protocols or set(self.protocols) - allowed_protocols:
            raise ClassificationInputError("classification protocols contain an unsupported value")
        if not self.models or set(self.models) - allowed_models:
            raise ClassificationInputError("classification models contain an unsupported value")
        if not self.band_ids or len(set(self.band_ids)) != len(self.band_ids):
            raise ClassificationInputError("classification band_ids must be non-empty and unique")

    @property
    def ordered_sample_ids(self) -> tuple[str, ...]:
        return tuple(item.sample_id for item in self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "classification_scope_id": self.classification_scope_id,
            "run_purpose": self.run_purpose.value,
            "analysis_tier": self.analysis_tier,
            "dataset_role": self.dataset_role.value,
            "measurement_mode": self.measurement_mode.value,
            "configuration_id": self.configuration_id,
            "feature_kind": self.feature_kind,
            "preprocessing_id": self.preprocessing_id,
            "tone_set_id": self.tone_set_id,
            "direction_order_deg": list(self.direction_order_deg),
            "members": [item.to_dict() for item in self.members],
            "feature_references": [item.to_dict() for item in self.feature_references],
            "protocols": list(self.protocols), "models": list(self.models),
            "band_ids": list(self.band_ids), "random_state": self.random_state,
            "dataset_qc_reference": self.dataset_qc_reference.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ClassificationScope":
        required = {"schema_version", "classification_scope_id", "run_purpose", "analysis_tier", "dataset_role", "measurement_mode", "configuration_id", "feature_kind", "preprocessing_id", "tone_set_id", "direction_order_deg", "members", "feature_references", "protocols", "models", "band_ids", "random_state", "dataset_qc_reference"}
        if set(payload) != required:
            raise ClassificationInputError("ClassificationScope fields must be explicit")
        reference = payload["dataset_qc_reference"]
        return cls(
            schema_version=str(payload["schema_version"]),
            classification_scope_id=str(payload["classification_scope_id"]),
            run_purpose=RunPurpose(payload["run_purpose"]), analysis_tier=str(payload["analysis_tier"]),
            dataset_role=DatasetRole(payload["dataset_role"]), measurement_mode=MeasurementMode(payload["measurement_mode"]),
            configuration_id=str(payload["configuration_id"]), feature_kind=str(payload["feature_kind"]),
            preprocessing_id=str(payload["preprocessing_id"]), tone_set_id=payload["tone_set_id"],
            direction_order_deg=tuple(float(x) for x in payload["direction_order_deg"]),
            members=tuple(ClassificationScopeMember.from_dict(x) for x in payload["members"]),
            feature_references=tuple(ClassificationFeatureReference.from_dict(x) for x in payload["feature_references"]),
            protocols=tuple(str(x) for x in payload["protocols"]), models=tuple(str(x) for x in payload["models"]),
            band_ids=tuple(str(x) for x in payload["band_ids"]), random_state=int(payload["random_state"]),
            dataset_qc_reference=DatasetQCReference(str(reference["analysis_scope_id"]), str(reference["dataset_qc_result_sha256"])),
        )

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class SplitAuditRecord:
    protocol: str
    fold_id: str
    held_out_group: str
    train_sample_ids: tuple[str, ...]
    test_sample_ids: tuple[str, ...]
    excluded_final_test_sample_ids: tuple[str, ...]
    valid: bool
    unavailable_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"protocol": self.protocol, "fold_id": self.fold_id, "held_out_group": self.held_out_group, "train_sample_ids": list(self.train_sample_ids), "test_sample_ids": list(self.test_sample_ids), "excluded_final_test_sample_ids": list(self.excluded_final_test_sample_ids), "valid": self.valid, "unavailable_reason": self.unavailable_reason}


@dataclass(frozen=True, slots=True)
class FeatureMaskAudit:
    protocol: str
    fold_id: str
    band_id: str
    selected_feature_indices: tuple[int, ...]
    selected_feature_names: tuple[str, ...]
    feature_count: int
    mask_source: str = "training_samples_only"

    def to_dict(self) -> dict[str, Any]:
        return {"protocol": self.protocol, "fold_id": self.fold_id, "band_id": self.band_id, "selected_feature_indices": list(self.selected_feature_indices), "selected_feature_names": list(self.selected_feature_names), "feature_count": self.feature_count, "mask_source": self.mask_source}


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    protocol: str
    fold_id: str
    band_id: str
    model_id: str
    sample_id: str
    true_direction_deg: float
    predicted_direction_deg: float | None
    second_direction_deg: float | None
    score: float | None
    margin: float | None
    available: bool
    unavailable_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__ if hasattr(self, "__dict__") else {name: getattr(self, name) for name in self.__slots__}


@dataclass(frozen=True, slots=True)
class FoldMetric:
    protocol: str
    fold_id: str
    band_id: str
    model_id: str
    available: bool
    accuracy: float | None
    balanced_accuracy: float | None
    prediction_coverage: float
    test_count: int
    available_prediction_count: int
    unavailable_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    schema_version: str
    classification_scope_id: str
    scope_sha256: str
    config_sha256: str
    processing_status: str
    canonical_analysis: bool
    scientifically_eligible: bool
    p2b_canonical_ready: bool
    split_audit: tuple[SplitAuditRecord, ...]
    feature_mask_audit: tuple[FeatureMaskAudit, ...]
    predictions: tuple[PredictionRecord, ...]
    fold_metrics: tuple[FoldMetric, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "classification_scope_id": self.classification_scope_id,
            "scope_sha256": self.scope_sha256, "config_sha256": self.config_sha256,
            "processing_status": self.processing_status, "canonical_analysis": self.canonical_analysis,
            "scientifically_eligible": self.scientifically_eligible, "p2b_canonical_ready": self.p2b_canonical_ready,
            "split_audit": [x.to_dict() for x in self.split_audit], "feature_mask_audit": [x.to_dict() for x in self.feature_mask_audit],
            "predictions": [x.to_dict() for x in self.predictions], "fold_metrics": [x.to_dict() for x in self.fold_metrics],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ClassificationResult":
        return cls(
            schema_version=str(payload["schema_version"]), classification_scope_id=str(payload["classification_scope_id"]),
            scope_sha256=str(payload["scope_sha256"]), config_sha256=str(payload["config_sha256"]),
            processing_status=str(payload["processing_status"]), canonical_analysis=bool(payload["canonical_analysis"]),
            scientifically_eligible=bool(payload["scientifically_eligible"]), p2b_canonical_ready=bool(payload["p2b_canonical_ready"]),
            split_audit=tuple(SplitAuditRecord(**{**x, "train_sample_ids": tuple(x["train_sample_ids"]), "test_sample_ids": tuple(x["test_sample_ids"]), "excluded_final_test_sample_ids": tuple(x["excluded_final_test_sample_ids"])}) for x in payload["split_audit"]),
            feature_mask_audit=tuple(FeatureMaskAudit(**{**x, "selected_feature_indices": tuple(x["selected_feature_indices"]), "selected_feature_names": tuple(x["selected_feature_names"])}) for x in payload["feature_mask_audit"]),
            predictions=tuple(PredictionRecord(**x) for x in payload["predictions"]), fold_metrics=tuple(FoldMetric(**x) for x in payload["fold_metrics"]),
        )


def _validate_inputs(features: Mapping[str, FeatureSet], scope: ClassificationScope) -> tuple[FeatureSet, ...]:
    if set(features) != {item.artifact_id for item in scope.feature_references}:
        raise ClassificationInputError("classification FeatureSet artifact scope mismatch")
    ordered: list[FeatureSet] = []
    contract: str | None = None
    member_by_id = {item.sample_id: item for item in scope.members}
    for reference in scope.feature_references:
        feature = features[reference.artifact_id]
        member = member_by_id[reference.sample_id]
        if feature.sample_id != reference.sample_id or feature_set_content_sha256(feature) != reference.feature_content_sha256:
            raise ClassificationInputError(f"classification FeatureSet content mismatch: {reference.sample_id}")
        if feature.source_measurement_mode is not scope.measurement_mode or feature.meta.measurement_mode is not scope.measurement_mode:
            raise ClassificationInputError("classification measurement_mode mismatch")
        if feature.meta.dataset_role is not scope.dataset_role:
            raise ClassificationInputError("classification dataset_role mismatch")
        if feature.meta.configuration != scope.configuration_id or feature.feature_kind.value != scope.feature_kind or feature.preprocessing_id != scope.preprocessing_id:
            raise ClassificationInputError("classification FeatureSet contract mismatch")
        if feature.tone_set_id != scope.tone_set_id:
            raise ClassificationInputError("classification tone_set_id mismatch")
        if feature.meta.angle_deg != member.direction_angle_deg:
            raise ClassificationInputError("classification direction metadata mismatch")
        current = feature_contract_sha256(feature)
        if contract is not None and current != contract:
            raise ClassificationInputError("classification FeatureSets have incompatible contracts")
        contract = current
        ordered.append(feature)
    return tuple(ordered)


def _group_value(member: ClassificationScopeMember, protocol: str) -> str | None:
    if protocol == "leave_one_session_out":
        return member.session_id
    if protocol == "leave_one_reposition_round_out":
        return None if member.repeat_type != "REPOS" else (None if member.reposition_round_id is None else f"{member.session_id}:{member.reposition_round_id}")
    return None if member.repeat_type != "REASM" else (None if member.assembly_id is None else f"{member.session_id}:{member.assembly_id}")


def _build_splits(scope: ClassificationScope, minimum_training_samples_per_direction: int) -> tuple[SplitAuditRecord, ...]:
    final_ids = tuple(m.sample_id for m in scope.members if m.cohort_role is CohortRole.FINAL_TEST)
    records: list[SplitAuditRecord] = []
    for protocol in scope.protocols:
        eligible = tuple(m for m in scope.members if m.cohort_role is not CohortRole.FINAL_TEST and _group_value(m, protocol) is not None)
        groups = tuple(sorted({_group_value(m, protocol) for m in eligible if _group_value(m, protocol) is not None}))
        if len(groups) < 2:
            records.append(SplitAuditRecord(protocol, f"{protocol}:unavailable", "", (), (), final_ids, False, "insufficient_groups"))
            continue
        for group in groups:
            train = tuple(m.sample_id for m in eligible if _group_value(m, protocol) != group)
            test = tuple(m.sample_id for m in eligible if _group_value(m, protocol) == group)
            train_labels = {m.direction_angle_deg for m in eligible if m.sample_id in train}
            test_labels = {m.direction_angle_deg for m in eligible if m.sample_id in test}
            reason = None
            if set(train) & set(test): reason = "group_leakage"
            elif len(train_labels) < 2: reason = "training_has_fewer_than_two_directions"
            elif train_labels != set(scope.direction_order_deg): reason = "training_direction_coverage_incomplete"
            elif any(sum(member.direction_angle_deg == angle for member in eligible if member.sample_id in train) < minimum_training_samples_per_direction for angle in scope.direction_order_deg): reason = "insufficient_training_samples_per_direction"
            elif not test_labels: reason = "empty_test_fold"
            elif test_labels != set(scope.direction_order_deg): reason = "test_direction_coverage_incomplete"
            fold_id = f"{protocol}:{group}"
            records.append(SplitAuditRecord(protocol, fold_id, str(group), train, test, final_ids, reason is None, reason))
    return tuple(records)


def _rank(scores: np.ndarray, labels: np.ndarray, direction_order: tuple[float, ...], *, higher_better: bool) -> tuple[float, float | None, float, float | None]:
    order_index = {angle: index for index, angle in enumerate(direction_order)}
    indices = sorted(range(len(labels)), key=lambda i: ((-scores[i] if higher_better else scores[i]), order_index[float(labels[i])]))
    first, second = indices[0], (indices[1] if len(indices) > 1 else None)
    margin = None if second is None else float((scores[first] - scores[second]) if higher_better else (scores[second] - scores[first]))
    return float(labels[first]), (None if second is None else float(labels[second])), float(scores[first]), margin


def _predict(model_id: str, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, direction_order: tuple[float, ...], random_state: int) -> list[tuple[float, float | None, float, float | None]]:
    labels = np.asarray([angle for angle in direction_order if angle in set(y_train)], dtype=float)
    if model_id == "nearest_template_correlation":
        templates = np.vstack([np.mean(x_train[y_train == label], axis=0) for label in labels])
        if np.any(np.std(templates, axis=1) <= 0):
            raise ClassificationInputError("constant_training_template")
        output = []
        for row in x_test:
            if np.std(row) <= 0: raise ClassificationInputError("constant_test_vector")
            scores = np.asarray([np.corrcoef(row, template)[0, 1] for template in templates])
            output.append(_rank(scores, labels, direction_order, higher_better=True))
        return output
    scaler = StandardScaler().fit(x_train)
    transformed_train = scaler.transform(x_train)
    transformed_test = scaler.transform(x_test)
    if model_id == "nearest_centroid":
        centroids = np.vstack([np.mean(transformed_train[y_train == label], axis=0) for label in labels])
        return [_rank(np.linalg.norm(centroids - row, axis=1), labels, direction_order, higher_better=False) for row in transformed_test]
    classifier = LogisticRegression(solver="lbfgs", C=1.0, max_iter=1000, class_weight="balanced", random_state=random_state).fit(transformed_train, y_train)
    probabilities = classifier.predict_proba(transformed_test)
    return [_rank(row, classifier.classes_.astype(float), direction_order, higher_better=True) for row in probabilities]


def predict_direction_fold(
    model_id: str,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    direction_order: tuple[float, ...],
    random_state: int,
) -> list[tuple[float, float | None, float, float | None]]:
    """P5 shared fold predictor; every fitted quantity comes from ``x_train``."""
    return _predict(
        model_id,
        np.asarray(x_train, dtype=np.float64),
        np.asarray(y_train, dtype=np.float64),
        np.asarray(x_test, dtype=np.float64),
        direction_order,
        random_state,
    )


def analyze_classification_feature_sets(
    features: Mapping[str, FeatureSet],
    scope: ClassificationScope,
    config: Mapping[str, Any],
    *,
    dataset_qc_result: DatasetQCResult,
) -> ClassificationResult:
    """Run grouped single-mode direction classification with fold-local fitting."""
    ordered = _validate_inputs(features, scope)
    validate_dataset_qc_reference(
        ordered, analysis_scope_id=scope.classification_scope_id,
        ordered_sample_ids=scope.ordered_sample_ids, run_purpose=scope.run_purpose,
        reference=scope.dataset_qc_reference, result=dataset_qc_result,
        require_canonical_ready=scope.analysis_tier == "canonical_cohort",
    )
    enforce_research_gate(scope.run_purpose, (feature.meta for feature in ordered))
    audit_roles = {item.sample_id: item.cohort_role for item in dataset_qc_result.input_audit}
    for member in scope.members:
        if audit_roles.get(member.sample_id) is not member.cohort_role:
            raise ClassificationInputError(
                f"classification/P2-B cohort role mismatch: {member.sample_id}"
            )
    if any(feature.meta.data_origin is not dataset_qc_result.data_origin for feature in ordered):
        raise ClassificationInputError("classification/P2-B provenance mismatch")
    if scope.dataset_role is not dataset_qc_result.dataset_role:
        raise ClassificationInputError("classification/P2-B dataset_role mismatch")
    bands_payload = config.get("frequency_bands")
    if not isinstance(bands_payload, Sequence):
        raise ClassificationInputError("classification.frequency_bands must be a sequence")
    bands = {str(item["band_id"]): FrequencyBand(**dict(item)) for item in bands_payload}
    if set(scope.band_ids) - set(bands):
        raise ClassificationInputError("classification scope references unknown frequency band")
    minimum_features = int(config.get("minimum_training_features", 2))
    minimum_samples_per_direction = int(config.get("minimum_training_samples_per_direction", 1))
    minimum_coverage = float(config.get("minimum_prediction_coverage", 1.0))
    split_audit = _build_splits(scope, minimum_samples_per_direction)
    member_by_id = {m.sample_id: m for m in scope.members}
    feature_by_id = {f.sample_id: f for f in ordered}
    frequencies = feature_frequencies_hz(ordered[0].feature_names)
    mask_records: list[FeatureMaskAudit] = []
    predictions: list[PredictionRecord] = []
    metrics: list[FoldMetric] = []
    for split in split_audit:
        for band_id in scope.band_ids:
            band = bands[band_id]
            if not split.valid:
                for model in scope.models:
                    metrics.append(FoldMetric(split.protocol, split.fold_id, band_id, model, False, None, None, 0.0, len(split.test_sample_ids), 0, split.unavailable_reason))
                continue
            band_mask = frequency_band_mask(frequencies, band)
            train_mask = band_mask.copy()
            for sample_id in split.train_sample_ids:
                train_mask &= feature_by_id[sample_id].valid_mask
            indices = tuple(int(i) for i in np.flatnonzero(train_mask))
            mask_records.append(FeatureMaskAudit(split.protocol, split.fold_id, band_id, indices, tuple(ordered[0].feature_names[i] for i in indices), len(indices)))
            x_train = np.vstack([feature_by_id[s].values[list(indices)] for s in split.train_sample_ids]) if indices else np.empty((len(split.train_sample_ids), 0))
            y_train = np.asarray([member_by_id[s].direction_angle_deg for s in split.train_sample_ids])
            for model in scope.models:
                available_rows: list[PredictionRecord] = []
                unavailable_rows: list[PredictionRecord] = []
                if len(indices) < max(minimum_features, band.minimum_feature_count):
                    reason = "insufficient_training_features"
                    unavailable_rows = [PredictionRecord(split.protocol, split.fold_id, band_id, model, s, member_by_id[s].direction_angle_deg, None, None, None, None, False, reason) for s in split.test_sample_ids]
                else:
                    valid_test_ids = [s for s in split.test_sample_ids if np.all(feature_by_id[s].valid_mask[list(indices)])]
                    unavailable_rows = [PredictionRecord(split.protocol, split.fold_id, band_id, model, s, member_by_id[s].direction_angle_deg, None, None, None, None, False, "test_missing_fold_feature") for s in split.test_sample_ids if s not in valid_test_ids]
                    if valid_test_ids:
                        x_test = np.vstack([feature_by_id[s].values[list(indices)] for s in valid_test_ids])
                        try:
                            predicted = _predict(model, x_train, y_train, x_test, scope.direction_order_deg, scope.random_state)
                            available_rows = [PredictionRecord(split.protocol, split.fold_id, band_id, model, s, member_by_id[s].direction_angle_deg, pred, second, score, margin, True, None) for s, (pred, second, score, margin) in zip(valid_test_ids, predicted, strict=True)]
                        except (ClassificationInputError, ValueError) as exc:
                            unavailable_rows.extend(PredictionRecord(split.protocol, split.fold_id, band_id, model, s, member_by_id[s].direction_angle_deg, None, None, None, None, False, str(exc)) for s in valid_test_ids)
                rows = tuple(sorted((*available_rows, *unavailable_rows), key=lambda x: scope.ordered_sample_ids.index(x.sample_id)))
                predictions.extend(rows)
                coverage = len(available_rows) / len(split.test_sample_ids) if split.test_sample_ids else 0.0
                metric_available = bool(available_rows) and coverage >= minimum_coverage
                if metric_available:
                    truth = [row.true_direction_deg for row in available_rows]
                    pred = [row.predicted_direction_deg for row in available_rows]
                    prediction_summary = summarize_direction_predictions(
                        truth,
                        pred,
                        scope.direction_order_deg,
                        total_prediction_count=len(split.test_sample_ids),
                    )
                    accuracy = float(accuracy_score(truth, pred)); balanced = prediction_summary.balanced_accuracy
                    reason = None
                else:
                    accuracy = balanced = None
                    reason = "prediction_coverage_below_minimum" if rows else "no_test_predictions"
                metrics.append(FoldMetric(split.protocol, split.fold_id, band_id, model, metric_available, accuracy, balanced, coverage, len(split.test_sample_ids), len(available_rows), reason))
    processing = "completed" if all(item.available for item in metrics) else "completed_with_unavailable"
    canonical = scope.analysis_tier == "canonical_cohort"
    return ClassificationResult(
        CLASSIFICATION_RESULT_SCHEMA_VERSION, scope.classification_scope_id, scope.sha256,
        _canonical_sha256(dict(config)), processing, canonical,
        canonical
        and scope.run_purpose is RunPurpose.RESEARCH_ANALYSIS
        and dataset_qc_result.scientifically_eligible
        and all(feature.meta.eligible_for_scientific_analysis for feature in ordered),
        dataset_qc_result.canonical_ready, tuple(split_audit), tuple(mask_records), tuple(predictions), tuple(metrics),
    )

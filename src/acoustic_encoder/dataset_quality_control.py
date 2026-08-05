"""P2-B cross-measurement quality control over P2-A and FeatureSet artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import itertools
import json
from typing import Any, Mapping, Sequence

import numpy as np

from .quality_control import MeasurementQCResult, measurement_qc_sha256
from .research_gate import RunPurpose, enforce_research_gate, normalize_run_purpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    FeatureSet,
    MeasurementMode,
    QCCheckStatus,
    QCStatus,
)


DATASET_QC_SCHEMA_VERSION = "1.0.0"
DATASET_QC_SCOPE_SCHEMA_VERSION = "1.0.0"


class DatasetQCInputError(ValueError):
    """Raised when an explicit P2-B input cannot be trusted."""


class CohortRole(str, Enum):
    DEVELOPMENT = "development"
    TRAINING = "training"
    FINAL_TEST = "final_test"


@dataclass(frozen=True, slots=True)
class DatasetQCReference:
    analysis_scope_id: str
    dataset_qc_result_sha256: str

    def __post_init__(self) -> None:
        if not self.analysis_scope_id.strip():
            raise DatasetQCInputError("dataset QC reference scope ID is required")
        digest = self.dataset_qc_result_sha256.removeprefix("sha256:")
        if (
            not self.dataset_qc_result_sha256.startswith("sha256:")
            or len(digest) != 64
            or digest != digest.lower()
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise DatasetQCInputError(
                "dataset_qc_result_sha256 must be sha256:<lowercase digest>"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "analysis_scope_id": self.analysis_scope_id,
            "dataset_qc_result_sha256": self.dataset_qc_result_sha256,
        }


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class ManualReviewRecord:
    review_id: str
    sample_ids: tuple[str, ...]
    reason_code: str
    status: str = "pending"
    reviewer: str | None = None
    reviewed_at_utc: str | None = None
    decision: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.review_id.strip() or not self.reason_code.strip():
            raise DatasetQCInputError("manual review ID and reason must be non-empty")
        if not self.sample_ids or len(set(self.sample_ids)) != len(self.sample_ids):
            raise DatasetQCInputError("manual review sample IDs must be non-empty and unique")
        if self.status not in {"pending", "decided"}:
            raise DatasetQCInputError("manual review status must be pending or decided")
        if self.status == "pending" and any(
            value is not None
            for value in (self.reviewer, self.reviewed_at_utc, self.decision)
        ):
            raise DatasetQCInputError("pending manual review cannot contain a decision")
        if self.status == "decided" and not all(
            value is not None and str(value).strip()
            for value in (self.reviewer, self.reviewed_at_utc, self.decision)
        ):
            raise DatasetQCInputError("decided manual review requires audit fields")

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "sample_ids": list(self.sample_ids),
            "reason_code": self.reason_code,
            "status": self.status,
            "reviewer": self.reviewer,
            "reviewed_at_utc": self.reviewed_at_utc,
            "decision": self.decision,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ManualReviewRecord":
        return cls(
            review_id=str(payload["review_id"]),
            sample_ids=tuple(str(item) for item in payload["sample_ids"]),
            reason_code=str(payload["reason_code"]),
            status=str(payload.get("status", "pending")),
            reviewer=payload.get("reviewer"),
            reviewed_at_utc=payload.get("reviewed_at_utc"),
            decision=payload.get("decision"),
            notes=payload.get("notes"),
        )


@dataclass(frozen=True, slots=True)
class DatasetScopeMember:
    sample_id: str
    cohort_role: CohortRole
    expected_condition_id: str | None
    selection_reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_role", CohortRole(self.cohort_role))
        if not self.sample_id.strip() or not self.selection_reason.strip():
            raise DatasetQCInputError("scope member ID and selection reason are required")
        if self.expected_condition_id is not None and not self.expected_condition_id.strip():
            raise DatasetQCInputError("expected_condition_id cannot be blank")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "cohort_role": self.cohort_role.value,
            "expected_condition_id": self.expected_condition_id,
            "selection_reason": self.selection_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DatasetScopeMember":
        return cls(
            sample_id=str(payload["sample_id"]),
            cohort_role=CohortRole(payload["cohort_role"]),
            expected_condition_id=payload.get("expected_condition_id"),
            selection_reason=str(payload["selection_reason"]),
        )


@dataclass(frozen=True, slots=True)
class ExpectedCondition:
    condition_id: str
    cohort_role: CohortRole
    measurement_mode: MeasurementMode
    configuration_id: str
    direction_id: str
    direction_angle_deg: float
    session_id: str
    repeat_type: str
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str | None
    expected_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_role", CohortRole(self.cohort_role))
        object.__setattr__(self, "measurement_mode", MeasurementMode(self.measurement_mode))
        for label, value in {
            "condition_id": self.condition_id,
            "configuration_id": self.configuration_id,
            "direction_id": self.direction_id,
            "session_id": self.session_id,
        }.items():
            if not str(value).strip():
                raise DatasetQCInputError(f"expected condition {label} is required")
        if self.repeat_type not in {"CONT", "REPOS", "REASM"}:
            raise DatasetQCInputError("repeat_type must be CONT, REPOS, or REASM")
        if not np.isfinite(self.direction_angle_deg) or not 0.0 <= self.direction_angle_deg < 360.0:
            raise DatasetQCInputError("direction_angle_deg must be finite and in [0, 360)")
        if isinstance(self.expected_count, bool) or not isinstance(self.expected_count, int) or self.expected_count < 1:
            raise DatasetQCInputError("expected_count must be an integer >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "cohort_role": self.cohort_role.value,
            "measurement_mode": self.measurement_mode.value,
            "configuration_id": self.configuration_id,
            "direction_id": self.direction_id,
            "direction_angle_deg": self.direction_angle_deg,
            "session_id": self.session_id,
            "repeat_type": self.repeat_type,
            "reposition_round_id": self.reposition_round_id,
            "assembly_id": self.assembly_id,
            "acquisition_block_id": self.acquisition_block_id,
            "expected_count": self.expected_count,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExpectedCondition":
        required = {
            "condition_id",
            "cohort_role",
            "measurement_mode",
            "configuration_id",
            "direction_id",
            "direction_angle_deg",
            "session_id",
            "repeat_type",
            "reposition_round_id",
            "assembly_id",
            "acquisition_block_id",
            "expected_count",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise DatasetQCInputError(
                f"expected condition fields must be explicit, including nulls: {missing}"
            )
        return cls(
            condition_id=str(payload["condition_id"]),
            cohort_role=CohortRole(payload["cohort_role"]),
            measurement_mode=MeasurementMode(payload["measurement_mode"]),
            configuration_id=str(payload["configuration_id"]),
            direction_id=str(payload["direction_id"]),
            direction_angle_deg=float(payload["direction_angle_deg"]),
            session_id=str(payload["session_id"]),
            repeat_type=str(payload["repeat_type"]),
            reposition_round_id=payload.get("reposition_round_id"),
            assembly_id=payload.get("assembly_id"),
            acquisition_block_id=payload.get("acquisition_block_id"),
            expected_count=int(payload["expected_count"]),
        )


@dataclass(frozen=True, slots=True)
class DatasetQCScope:
    schema_version: str
    analysis_scope_id: str
    run_purpose: RunPurpose
    members: tuple[DatasetScopeMember, ...]
    expected_conditions: tuple[ExpectedCondition, ...]
    manual_review_records: tuple[ManualReviewRecord, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != DATASET_QC_SCOPE_SCHEMA_VERSION:
            raise DatasetQCInputError("dataset QC scope schema_version must be 1.0.0")
        if not self.analysis_scope_id.strip():
            raise DatasetQCInputError("analysis_scope_id must be non-empty")
        object.__setattr__(self, "run_purpose", normalize_run_purpose(self.run_purpose))
        sample_ids = tuple(member.sample_id for member in self.members)
        condition_ids = tuple(item.condition_id for item in self.expected_conditions)
        if not sample_ids or len(set(sample_ids)) != len(sample_ids):
            raise DatasetQCInputError("scope sample IDs must be non-empty and unique")
        if not condition_ids or len(set(condition_ids)) != len(condition_ids):
            raise DatasetQCInputError("expected condition IDs must be non-empty and unique")
        known_conditions = set(condition_ids)
        unknown = sorted(
            {
                member.expected_condition_id
                for member in self.members
                if member.expected_condition_id is not None
                and member.expected_condition_id not in known_conditions
            }
        )
        if unknown:
            raise DatasetQCInputError(f"scope members reference unknown conditions: {unknown}")
        known_samples = set(sample_ids)
        review_unknown = sorted(
            {
                sample_id
                for review in self.manual_review_records
                for sample_id in review.sample_ids
                if sample_id not in known_samples
            }
        )
        if review_unknown:
            raise DatasetQCInputError(
                f"manual review references out-of-scope samples: {review_unknown}"
            )

    @property
    def sample_ids(self) -> tuple[str, ...]:
        return tuple(member.sample_id for member in self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_scope_id": self.analysis_scope_id,
            "run_purpose": self.run_purpose.value,
            "members": [member.to_dict() for member in self.members],
            "expected_conditions": [item.to_dict() for item in self.expected_conditions],
            "manual_review_records": [item.to_dict() for item in self.manual_review_records],
        }

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DatasetQCScope":
        return cls(
            schema_version=str(payload["schema_version"]),
            analysis_scope_id=str(payload["analysis_scope_id"]),
            run_purpose=RunPurpose(payload["run_purpose"]),
            members=tuple(
                DatasetScopeMember.from_dict(item) for item in payload["members"]
            ),
            expected_conditions=tuple(
                ExpectedCondition.from_dict(item)
                for item in payload["expected_conditions"]
            ),
            manual_review_records=tuple(
                ManualReviewRecord.from_dict(item)
                for item in payload.get("manual_review_records", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class ConditionCompletenessResult:
    condition_id: str
    cohort_role: CohortRole
    expected_count: int
    observed_count: int
    valid_count: int
    warning_count: int
    exclude_candidate_count: int
    missing_count: int
    duplicate_count: int
    unexpected_count: int
    status: QCCheckStatus
    reason_codes: tuple[str, ...]
    observed_sample_ids: tuple[str, ...]
    unexpected_sample_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "cohort_role": self.cohort_role.value,
            "expected_count": self.expected_count,
            "observed_count": self.observed_count,
            "valid_count": self.valid_count,
            "warning_count": self.warning_count,
            "exclude_candidate_count": self.exclude_candidate_count,
            "missing_count": self.missing_count,
            "duplicate_count": self.duplicate_count,
            "unexpected_count": self.unexpected_count,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "observed_sample_ids": list(self.observed_sample_ids),
            "unexpected_sample_ids": list(self.unexpected_sample_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConditionCompletenessResult":
        return cls(
            condition_id=str(payload["condition_id"]),
            cohort_role=CohortRole(payload["cohort_role"]),
            expected_count=int(payload["expected_count"]),
            observed_count=int(payload["observed_count"]),
            valid_count=int(payload["valid_count"]),
            warning_count=int(payload["warning_count"]),
            exclude_candidate_count=int(payload["exclude_candidate_count"]),
            missing_count=int(payload["missing_count"]),
            duplicate_count=int(payload["duplicate_count"]),
            unexpected_count=int(payload["unexpected_count"]),
            status=QCCheckStatus(payload["status"]),
            reason_codes=tuple(str(item) for item in payload["reason_codes"]),
            observed_sample_ids=tuple(
                str(item) for item in payload["observed_sample_ids"]
            ),
            unexpected_sample_ids=tuple(
                str(item) for item in payload["unexpected_sample_ids"]
            ),
        )


@dataclass(frozen=True, slots=True)
class SameConditionOutlierResult:
    sample_id: str
    group_id: str
    cohort_role: CohortRole
    reference_role: CohortRole
    feature_contract_sha256: str
    available: bool
    status: QCCheckStatus
    reason_code: str | None
    distance: float | None
    reference_distance_center: float | None
    reference_scale: float | None
    robust_z: float | None
    reference_sample_count: int
    common_valid_feature_count: int
    reference_sample_ids: tuple[str, ...]
    warning_threshold: float
    exclude_candidate_threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "group_id": self.group_id,
            "cohort_role": self.cohort_role.value,
            "reference_role": self.reference_role.value,
            "feature_contract_sha256": self.feature_contract_sha256,
            "available": self.available,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "distance": self.distance,
            "reference_distance_center": self.reference_distance_center,
            "reference_scale": self.reference_scale,
            "robust_z": self.robust_z,
            "reference_sample_count": self.reference_sample_count,
            "common_valid_feature_count": self.common_valid_feature_count,
            "reference_sample_ids": list(self.reference_sample_ids),
            "warning_threshold": self.warning_threshold,
            "exclude_candidate_threshold": self.exclude_candidate_threshold,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SameConditionOutlierResult":
        return cls(
            sample_id=str(payload["sample_id"]),
            group_id=str(payload["group_id"]),
            cohort_role=CohortRole(payload["cohort_role"]),
            reference_role=CohortRole(payload["reference_role"]),
            feature_contract_sha256=str(payload["feature_contract_sha256"]),
            available=bool(payload["available"]),
            status=QCCheckStatus(payload["status"]),
            reason_code=payload.get("reason_code"),
            distance=payload.get("distance"),
            reference_distance_center=payload.get("reference_distance_center"),
            reference_scale=payload.get("reference_scale"),
            robust_z=payload.get("robust_z"),
            reference_sample_count=int(payload["reference_sample_count"]),
            common_valid_feature_count=int(payload["common_valid_feature_count"]),
            reference_sample_ids=tuple(
                str(item) for item in payload["reference_sample_ids"]
            ),
            warning_threshold=float(payload["warning_threshold"]),
            exclude_candidate_threshold=float(payload["exclude_candidate_threshold"]),
        )


@dataclass(frozen=True, slots=True)
class RepeatabilityPairResult:
    pair_id: str
    left_sample_id: str
    right_sample_id: str
    qualified: bool
    available: bool
    distance: float | None
    status: QCCheckStatus
    reason_code: str | None
    common_valid_feature_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "left_sample_id": self.left_sample_id,
            "right_sample_id": self.right_sample_id,
            "qualified": self.qualified,
            "available": self.available,
            "distance": self.distance,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "common_valid_feature_count": self.common_valid_feature_count,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RepeatabilityPairResult":
        return cls(
            pair_id=str(payload["pair_id"]),
            left_sample_id=str(payload["left_sample_id"]),
            right_sample_id=str(payload["right_sample_id"]),
            qualified=bool(payload["qualified"]),
            available=bool(payload["available"]),
            distance=payload.get("distance"),
            status=QCCheckStatus(payload["status"]),
            reason_code=payload.get("reason_code"),
            common_valid_feature_count=int(payload["common_valid_feature_count"]),
        )


@dataclass(frozen=True, slots=True)
class RepeatabilityGroupResult:
    group_id: str
    cohort_role: CohortRole
    repeat_type: str
    sample_ids: tuple[str, ...]
    sample_count: int
    candidate_pair_count: int
    qualified_pair_count: int
    warning_threshold: float
    exclude_candidate_threshold: float
    units: str
    status: QCCheckStatus
    reason_codes: tuple[str, ...]
    median_distance: float | None
    mean_distance: float | None
    sample_std_distance: float | None
    iqr_distance: float | None
    minimum_distance: float | None
    maximum_distance: float | None
    pairs: tuple[RepeatabilityPairResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "cohort_role": self.cohort_role.value,
            "repeat_type": self.repeat_type,
            "sample_ids": list(self.sample_ids),
            "sample_count": self.sample_count,
            "candidate_pair_count": self.candidate_pair_count,
            "qualified_pair_count": self.qualified_pair_count,
            "warning_threshold": self.warning_threshold,
            "exclude_candidate_threshold": self.exclude_candidate_threshold,
            "units": self.units,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "median_distance": self.median_distance,
            "mean_distance": self.mean_distance,
            "sample_std_distance": self.sample_std_distance,
            "iqr_distance": self.iqr_distance,
            "minimum_distance": self.minimum_distance,
            "maximum_distance": self.maximum_distance,
            "pairs": [item.to_dict() for item in self.pairs],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RepeatabilityGroupResult":
        return cls(
            group_id=str(payload["group_id"]),
            cohort_role=CohortRole(payload["cohort_role"]),
            repeat_type=str(payload["repeat_type"]),
            sample_ids=tuple(str(item) for item in payload["sample_ids"]),
            sample_count=int(payload["sample_count"]),
            candidate_pair_count=int(payload["candidate_pair_count"]),
            qualified_pair_count=int(payload["qualified_pair_count"]),
            warning_threshold=float(payload["warning_threshold"]),
            exclude_candidate_threshold=float(payload["exclude_candidate_threshold"]),
            units=str(payload["units"]),
            status=QCCheckStatus(payload["status"]),
            reason_codes=tuple(str(item) for item in payload["reason_codes"]),
            median_distance=payload.get("median_distance"),
            mean_distance=payload.get("mean_distance"),
            sample_std_distance=payload.get("sample_std_distance"),
            iqr_distance=payload.get("iqr_distance"),
            minimum_distance=payload.get("minimum_distance"),
            maximum_distance=payload.get("maximum_distance"),
            pairs=tuple(
                RepeatabilityPairResult.from_dict(item) for item in payload["pairs"]
            ),
        )


@dataclass(frozen=True, slots=True)
class MeasurementQCRollup:
    sample_id: str
    cohort_role: CohortRole
    p2a_qc_sha256: str
    p2a_status: QCStatus
    p2b_status: QCStatus
    aggregate_status: QCStatus
    warning_reasons: tuple[str, ...]
    exclude_candidate_reasons: tuple[str, ...]
    unavailable_checks: tuple[str, ...]
    manual_review_reasons: tuple[str, ...]
    human_valid: bool
    human_exclusion_reason: str | None
    eligible_for_downstream: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "cohort_role": self.cohort_role.value,
            "p2a_qc_sha256": self.p2a_qc_sha256,
            "p2a_status": self.p2a_status.value,
            "p2b_status": self.p2b_status.value,
            "aggregate_status": self.aggregate_status.value,
            "warning_reasons": list(self.warning_reasons),
            "exclude_candidate_reasons": list(self.exclude_candidate_reasons),
            "unavailable_checks": list(self.unavailable_checks),
            "manual_review_reasons": list(self.manual_review_reasons),
            "human_valid": self.human_valid,
            "human_exclusion_reason": self.human_exclusion_reason,
            "eligible_for_downstream": self.eligible_for_downstream,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MeasurementQCRollup":
        return cls(
            sample_id=str(payload["sample_id"]),
            cohort_role=CohortRole(payload["cohort_role"]),
            p2a_qc_sha256=str(payload["p2a_qc_sha256"]),
            p2a_status=QCStatus(payload["p2a_status"]),
            p2b_status=QCStatus(payload["p2b_status"]),
            aggregate_status=QCStatus(payload["aggregate_status"]),
            warning_reasons=tuple(str(item) for item in payload["warning_reasons"]),
            exclude_candidate_reasons=tuple(
                str(item) for item in payload["exclude_candidate_reasons"]
            ),
            unavailable_checks=tuple(
                str(item) for item in payload["unavailable_checks"]
            ),
            manual_review_reasons=tuple(
                str(item) for item in payload["manual_review_reasons"]
            ),
            human_valid=bool(payload["human_valid"]),
            human_exclusion_reason=payload.get("human_exclusion_reason"),
            eligible_for_downstream=bool(payload["eligible_for_downstream"]),
        )


@dataclass(frozen=True, slots=True)
class DatasetInputAuditRecord:
    sample_id: str
    cohort_role: CohortRole
    feature_contract_sha256: str
    feature_content_sha256: str
    p2a_qc_sha256: str
    source_sha256: str
    selection_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "cohort_role": self.cohort_role.value,
            "feature_contract_sha256": self.feature_contract_sha256,
            "feature_content_sha256": self.feature_content_sha256,
            "p2a_qc_sha256": self.p2a_qc_sha256,
            "source_sha256": self.source_sha256,
            "selection_reason": self.selection_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DatasetInputAuditRecord":
        return cls(
            sample_id=str(payload["sample_id"]),
            cohort_role=CohortRole(payload["cohort_role"]),
            feature_contract_sha256=str(payload["feature_contract_sha256"]),
            feature_content_sha256=str(payload["feature_content_sha256"]),
            p2a_qc_sha256=str(payload["p2a_qc_sha256"]),
            source_sha256=str(payload["source_sha256"]),
            selection_reason=str(payload["selection_reason"]),
        )


@dataclass(frozen=True, slots=True)
class DatasetQCResult:
    schema_version: str
    analysis_scope_id: str
    scope_sha256: str
    config_sha256: str
    run_purpose: RunPurpose
    data_origin: DataOrigin
    dataset_role: DatasetRole
    scoped_sample_ids: tuple[str, ...]
    condition_results: tuple[ConditionCompletenessResult, ...]
    input_audit: tuple[DatasetInputAuditRecord, ...] = ()
    outlier_results: tuple[SameConditionOutlierResult, ...] = ()
    repeatability_results: tuple[RepeatabilityGroupResult, ...] = ()
    measurement_rollups: tuple[MeasurementQCRollup, ...] = ()
    manual_review_records: tuple[ManualReviewRecord, ...] = ()
    unavailable_required_policy: str = "warning"
    canonical_allowed_statuses: tuple[QCStatus, ...] = (QCStatus.VALID, QCStatus.WARNING)
    canonical_block_on_required_unavailable: bool = True
    canonical_block_on_manual_review: bool = True
    scientifically_eligible: bool = False

    @property
    def aggregate_status(self) -> QCStatus:
        statuses = {
            item.status
            for item in (
                *self.condition_results,
                *self.outlier_results,
                *self.repeatability_results,
            )
        }
        if QCCheckStatus.EXCLUDE_CANDIDATE in statuses:
            return QCStatus.EXCLUDE_CANDIDATE
        if QCCheckStatus.WARNING in statuses:
            return QCStatus.WARNING
        if any(item.aggregate_status is QCStatus.EXCLUDE_CANDIDATE for item in self.measurement_rollups):
            return QCStatus.EXCLUDE_CANDIDATE
        if any(item.aggregate_status is QCStatus.WARNING for item in self.measurement_rollups):
            return QCStatus.WARNING
        if self.unavailable_required_policy == "warning" and any(
            status is QCCheckStatus.UNAVAILABLE for status in statuses
        ):
            return QCStatus.WARNING
        return QCStatus.VALID

    @property
    def canonical_ready_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.aggregate_status not in self.canonical_allowed_statuses:
            reasons.append(f"dataset_status_not_allowed:{self.aggregate_status.value}")
        if any(
            item.missing_count or item.duplicate_count or item.unexpected_count
            for item in self.condition_results
        ):
            reasons.append("condition_matrix_incomplete")
        if self.canonical_block_on_required_unavailable and (
            any(item.status is QCCheckStatus.UNAVAILABLE for item in self.outlier_results)
            or any(item.status is QCCheckStatus.UNAVAILABLE for item in self.repeatability_results)
        ):
            reasons.append("required_dataset_check_unavailable")
        if self.canonical_block_on_manual_review and (
            any(item.status == "pending" for item in self.manual_review_records)
            or any(item.manual_review_reasons for item in self.measurement_rollups)
        ):
            reasons.append("manual_review_pending")
        if any(not item.human_valid for item in self.measurement_rollups):
            reasons.append("human_invalid_measurement_present")
        if any(not item.eligible_for_downstream for item in self.measurement_rollups):
            reasons.append("measurement_not_eligible_for_downstream")
        return tuple(sorted(set(reasons)))

    @property
    def canonical_ready(self) -> bool:
        return not self.canonical_ready_reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_scope_id": self.analysis_scope_id,
            "scope_sha256": self.scope_sha256,
            "config_sha256": self.config_sha256,
            "run_purpose": self.run_purpose.value,
            "data_origin": self.data_origin.value,
            "dataset_role": self.dataset_role.value,
            "scoped_sample_ids": list(self.scoped_sample_ids),
            "aggregate_status": self.aggregate_status.value,
            "canonical_ready": self.canonical_ready,
            "canonical_ready_reasons": list(self.canonical_ready_reasons),
            "condition_results": [item.to_dict() for item in self.condition_results],
            "input_audit": [item.to_dict() for item in self.input_audit],
            "outlier_results": [item.to_dict() for item in self.outlier_results],
            "repeatability_results": [
                item.to_dict() for item in self.repeatability_results
            ],
            "measurement_rollups": [item.to_dict() for item in self.measurement_rollups],
            "manual_review_records": [item.to_dict() for item in self.manual_review_records],
            "unavailable_required_policy": self.unavailable_required_policy,
            "canonical_allowed_statuses": [item.value for item in self.canonical_allowed_statuses],
            "canonical_block_on_required_unavailable": self.canonical_block_on_required_unavailable,
            "canonical_block_on_manual_review": self.canonical_block_on_manual_review,
            "scientifically_eligible": self.scientifically_eligible,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DatasetQCResult":
        result = cls(
            schema_version=str(payload["schema_version"]),
            analysis_scope_id=str(payload["analysis_scope_id"]),
            scope_sha256=str(payload["scope_sha256"]),
            config_sha256=str(payload["config_sha256"]),
            run_purpose=RunPurpose(payload["run_purpose"]),
            data_origin=DataOrigin(payload["data_origin"]),
            dataset_role=DatasetRole(payload["dataset_role"]),
            scoped_sample_ids=tuple(
                str(item) for item in payload["scoped_sample_ids"]
            ),
            condition_results=tuple(
                ConditionCompletenessResult.from_dict(item)
                for item in payload["condition_results"]
            ),
            input_audit=tuple(
                DatasetInputAuditRecord.from_dict(item)
                for item in payload.get("input_audit", ())
            ),
            outlier_results=tuple(
                SameConditionOutlierResult.from_dict(item)
                for item in payload["outlier_results"]
            ),
            repeatability_results=tuple(
                RepeatabilityGroupResult.from_dict(item)
                for item in payload["repeatability_results"]
            ),
            measurement_rollups=tuple(
                MeasurementQCRollup.from_dict(item)
                for item in payload["measurement_rollups"]
            ),
            manual_review_records=tuple(
                ManualReviewRecord.from_dict(item)
                for item in payload["manual_review_records"]
            ),
            unavailable_required_policy=str(payload["unavailable_required_policy"]),
            canonical_allowed_statuses=tuple(
                QCStatus(item) for item in payload["canonical_allowed_statuses"]
            ),
            canonical_block_on_required_unavailable=bool(
                payload["canonical_block_on_required_unavailable"]
            ),
            canonical_block_on_manual_review=bool(
                payload["canonical_block_on_manual_review"]
            ),
            scientifically_eligible=bool(payload["scientifically_eligible"]),
        )
        derived = {
            "aggregate_status": result.aggregate_status.value,
            "canonical_ready": result.canonical_ready,
            "canonical_ready_reasons": list(result.canonical_ready_reasons),
        }
        for name, expected in derived.items():
            if name in payload and payload[name] != expected:
                raise DatasetQCInputError(
                    f"serialized DatasetQCResult derived field mismatch: {name}"
                )
        return result


def dataset_qc_sha256(result: DatasetQCResult) -> str:
    """Return the stable typed P2-B result hash used by downstream gates."""
    return _canonical_sha256(result.to_dict())


def _status_from_config(value: Any, label: str) -> QCCheckStatus:
    try:
        status = QCCheckStatus(str(value))
    except ValueError as exc:
        raise DatasetQCInputError(f"{label} is not a QC status") from exc
    if status not in {QCCheckStatus.WARNING, QCCheckStatus.EXCLUDE_CANDIDATE}:
        raise DatasetQCInputError(f"{label} must be warning or exclude_candidate")
    return status


def _condition_mismatches(
    feature: FeatureSet,
    member: DatasetScopeMember,
    condition: ExpectedCondition,
    *,
    angle_tolerance: float,
) -> tuple[str, ...]:
    meta = feature.meta
    checks = {
        "cohort_role": member.cohort_role == condition.cohort_role,
        "measurement_mode": meta.measurement_mode == condition.measurement_mode,
        "configuration_id": meta.configuration == condition.configuration_id,
        "direction_angle_deg": meta.angle_deg is not None
        and abs(float(meta.angle_deg) - condition.direction_angle_deg) <= angle_tolerance,
        "session_id": meta.session_id == condition.session_id,
        "repeat_type": meta.repeat_type == condition.repeat_type,
        "reposition_round_id": meta.reposition_round_id == condition.reposition_round_id,
        "assembly_id": meta.assembly_id == condition.assembly_id,
        "acquisition_block_id": meta.acquisition_block_id == condition.acquisition_block_id,
    }
    return tuple(name for name, matches in checks.items() if not matches)


def _feature_contract_payload(feature: FeatureSet) -> dict[str, Any]:
    return {
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
    }


def feature_contract_sha256(feature: FeatureSet) -> str:
    """Hash the complete comparison contract without hashing measured values."""
    return _canonical_sha256(_feature_contract_payload(feature))


def feature_set_content_sha256(feature: FeatureSet) -> str:
    """Hash a FeatureSet's identity, metadata, values, masks, and QC audit link."""
    payload = {
        **_feature_contract_payload(feature),
        "sample_id": feature.sample_id,
        "meta": feature.meta.to_dict(),
        "source_phase_status": (
            None if feature.source_phase_status is None else feature.source_phase_status.value
        ),
        "reliability_weight_source": feature.reliability_weight_source,
        "fit_scope_id": feature.fit_scope_id,
        "calibration_id": feature.calibration_id,
        "source_qc_status": (
            None if feature.source_qc_status is None else feature.source_qc_status.value
        ),
        "source_qc_sha256": feature.source_qc_sha256,
        "source_qc_warning_reasons": feature.source_qc_warning_reasons,
        "source_qc_exclude_candidate_reasons": feature.source_qc_exclude_candidate_reasons,
        "source_qc_unavailable_checks": feature.source_qc_unavailable_checks,
        "source_qc_eligible_for_downstream": feature.source_qc_eligible_for_downstream,
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


def _physical_condition_key(condition: ExpectedCondition) -> tuple[Any, ...]:
    return (
        condition.measurement_mode.value,
        condition.configuration_id,
        condition.direction_id,
        condition.direction_angle_deg,
        condition.session_id,
        condition.repeat_type,
        condition.reposition_round_id,
        condition.assembly_id,
        condition.acquisition_block_id,
    )


def _outlier_results(
    features_by_id: Mapping[str, FeatureSet],
    scope: DatasetQCScope,
    config: Mapping[str, Any],
    condition_valid_samples: Mapping[str, tuple[str, ...]],
) -> tuple[SameConditionOutlierResult, ...]:
    outlier_config = config.get("same_condition_outliers")
    if not isinstance(outlier_config, Mapping):
        raise DatasetQCInputError("same_condition_outliers config must be a mapping")
    expected_method = {
        "method": "coordinate_median_mad_rms",
        "center": "coordinate_median",
        "distance": "rms",
        "scale": "median_absolute_deviation",
    }
    if any(outlier_config.get(key) != value for key, value in expected_method.items()):
        raise DatasetQCInputError("unsupported same-condition outlier method")
    try:
        minimum_reference = int(outlier_config["minimum_reference_samples"])
        minimum_features = int(outlier_config["minimum_common_valid_features"])
        minimum_fraction = float(outlier_config["minimum_common_valid_fraction"])
        minimum_scale = float(outlier_config["minimum_scale"])
        mad_factor = float(outlier_config["mad_scale_factor"])
        warning = float(outlier_config["warning_robust_z"])
        exclude = float(outlier_config["exclude_candidate_robust_z"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetQCInputError("outlier thresholds are invalid") from exc
    if not (
        minimum_reference >= 1
        and minimum_features >= 1
        and 0.0 < minimum_fraction <= 1.0
        and minimum_scale > 0.0
        and mad_factor > 0.0
        and warning < exclude
        and all(np.isfinite(value) for value in (minimum_fraction, minimum_scale, mad_factor, warning, exclude))
    ):
        raise DatasetQCInputError("outlier thresholds are not ordered or finite")
    incompatible_status = _status_from_config(
        outlier_config.get("incompatible_contract_status"),
        "same_condition_outliers.incompatible_contract_status",
    )
    role_mapping = outlier_config.get("reference_role_by_evaluation_role")
    if not isinstance(role_mapping, Mapping) or set(role_mapping) != {
        role.value for role in CohortRole
    }:
        raise DatasetQCInputError("outlier reference-role mapping is incomplete")
    reference_by_role = {
        CohortRole(role): CohortRole(reference)
        for role, reference in role_mapping.items()
    }
    if CohortRole.FINAL_TEST in reference_by_role.values():
        raise DatasetQCInputError("final_test cannot be an outlier reference role")

    condition_by_id = {item.condition_id: item for item in scope.expected_conditions}
    members_by_condition = {
        item.condition_id: [] for item in scope.expected_conditions
    }
    for member in scope.members:
        if member.expected_condition_id in members_by_condition:
            members_by_condition[member.expected_condition_id].append(member)
    by_physical_role: dict[tuple[Any, ...], list[str]] = {}
    for condition in scope.expected_conditions:
        key = (*_physical_condition_key(condition), condition.cohort_role.value)
        by_physical_role.setdefault(key, []).extend(
            condition_valid_samples.get(condition.condition_id, ())
        )

    results: list[SameConditionOutlierResult] = []
    for member in scope.members:
        if member.expected_condition_id is None:
            continue
        condition = condition_by_id[member.expected_condition_id]
        target = features_by_id[member.sample_id]
        contract_hash = feature_contract_sha256(target)
        reference_role = reference_by_role[member.cohort_role]
        reference_ids = list(
            by_physical_role.get(
                (*_physical_condition_key(condition), reference_role.value),
                (),
            )
        )
        if reference_role is member.cohort_role:
            reference_ids = [item for item in reference_ids if item != member.sample_id]
        compatible_ids = [
            item
            for item in reference_ids
            if feature_contract_sha256(features_by_id[item]) == contract_hash
        ]
        group_id = _canonical_sha256(
            {
                "physical_condition": _physical_condition_key(condition),
                "feature_contract_sha256": contract_hash,
            }
        )
        unavailable_reason: str | None = None
        if member.sample_id not in condition_valid_samples.get(condition.condition_id, ()):
            unavailable_reason = "condition_metadata_mismatch"
        elif reference_ids and not compatible_ids:
            unavailable_reason = "incompatible_feature_contract"
        elif len(compatible_ids) < minimum_reference:
            unavailable_reason = "insufficient_reference_samples"
        reference_features = [features_by_id[item] for item in compatible_ids]
        common_mask = np.asarray(target.valid_mask, dtype=bool).copy()
        for reference in reference_features:
            common_mask &= reference.valid_mask
        common_count = int(np.count_nonzero(common_mask))
        common_fraction = common_count / max(1, target.valid_mask.size)
        if unavailable_reason is None and (
            common_count < minimum_features or common_fraction < minimum_fraction
        ):
            unavailable_reason = "insufficient_common_valid_features"
        if unavailable_reason is not None:
            unavailable_status = (
                incompatible_status
                if unavailable_reason == "incompatible_feature_contract"
                else QCCheckStatus.UNAVAILABLE
            )
            results.append(
                SameConditionOutlierResult(
                    sample_id=member.sample_id,
                    group_id=group_id,
                    cohort_role=member.cohort_role,
                    reference_role=reference_role,
                    feature_contract_sha256=contract_hash,
                    available=False,
                    status=unavailable_status,
                    reason_code=unavailable_reason,
                    distance=None,
                    reference_distance_center=None,
                    reference_scale=None,
                    robust_z=None,
                    reference_sample_count=len(compatible_ids),
                    common_valid_feature_count=common_count,
                    reference_sample_ids=tuple(sorted(compatible_ids)),
                    warning_threshold=warning,
                    exclude_candidate_threshold=exclude,
                )
            )
            continue
        reference_matrix = np.vstack(
            [feature.values[common_mask] for feature in reference_features]
        )
        center = np.median(reference_matrix, axis=0)
        reference_distances = np.sqrt(
            np.mean(np.square(reference_matrix - center), axis=1)
        )
        distance_center = float(np.median(reference_distances))
        mad = float(np.median(np.abs(reference_distances - distance_center)))
        scale = max(mad_factor * mad, minimum_scale)
        distance = float(
            np.sqrt(np.mean(np.square(target.values[common_mask] - center)))
        )
        robust_z = (distance - distance_center) / scale
        if robust_z >= exclude:
            status = QCCheckStatus.EXCLUDE_CANDIDATE
            reason = "same_condition_severe_outlier"
        elif robust_z >= warning:
            status = QCCheckStatus.WARNING
            reason = "same_condition_possible_outlier"
        else:
            status = QCCheckStatus.VALID
            reason = None
        results.append(
            SameConditionOutlierResult(
                sample_id=member.sample_id,
                group_id=group_id,
                cohort_role=member.cohort_role,
                reference_role=reference_role,
                feature_contract_sha256=contract_hash,
                available=True,
                status=status,
                reason_code=reason,
                distance=distance,
                reference_distance_center=distance_center,
                reference_scale=scale,
                robust_z=robust_z,
                reference_sample_count=len(compatible_ids),
                common_valid_feature_count=common_count,
                reference_sample_ids=tuple(sorted(compatible_ids)),
                warning_threshold=warning,
                exclude_candidate_threshold=exclude,
            )
        )
    return tuple(sorted(results, key=lambda item: item.sample_id))


def _repeat_pair_reason(left: FeatureSet, right: FeatureSet, repeat_type: str) -> str | None:
    if left.meta.repeat_type != right.meta.repeat_type:
        return "different_repeat_type"
    if not left.meta.repeat_id or not right.meta.repeat_id:
        return "missing_repeat_id"
    if left.meta.repeat_id == right.meta.repeat_id:
        return "same_repeat_id"
    if repeat_type == "CONT":
        for name in ("acquisition_block_id",):
            if getattr(left.meta, name) != getattr(right.meta, name):
                return f"different_{name}"
        for name in ("reposition_round_id", "assembly_id"):
            left_value = getattr(left.meta, name)
            right_value = getattr(right.meta, name)
            if (left_value is None) != (right_value is None):
                return f"incomplete_{name}"
            if left_value is not None and left_value != right_value:
                return f"different_{name}"
        return None
    if repeat_type == "REPOS":
        if not left.meta.assembly_id or not right.meta.assembly_id:
            return "missing_assembly_id"
        if left.meta.assembly_id != right.meta.assembly_id:
            return "different_assembly_id"
        if not left.meta.reposition_round_id or not right.meta.reposition_round_id:
            return "missing_reposition_round_id"
        if left.meta.reposition_round_id == right.meta.reposition_round_id:
            return "same_reposition_round_id"
        return None
    if repeat_type == "REASM":
        if not left.meta.assembly_id or not right.meta.assembly_id:
            return "missing_assembly_id"
        if left.meta.assembly_id == right.meta.assembly_id:
            return "same_assembly_id"
        return None
    return "unsupported_repeat_type"


def _repeatability_results(
    features_by_id: Mapping[str, FeatureSet],
    scope: DatasetQCScope,
    config: Mapping[str, Any],
    condition_valid_samples: Mapping[str, tuple[str, ...]],
) -> tuple[RepeatabilityGroupResult, ...]:
    repeat_config = config.get("repeatability")
    if not isinstance(repeat_config, Mapping) or repeat_config.get("distance") != "rms":
        raise DatasetQCInputError("repeatability.distance must be rms")
    try:
        minimum_features = int(repeat_config["minimum_common_valid_features"])
        minimum_fraction = float(repeat_config["minimum_common_valid_fraction"])
        minimum_pairs = int(repeat_config["minimum_qualified_pairs"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetQCInputError("repeatability minimums are invalid") from exc
    if not (
        minimum_features >= 1
        and minimum_pairs >= 1
        and np.isfinite(minimum_fraction)
        and 0.0 < minimum_fraction <= 1.0
    ):
        raise DatasetQCInputError("repeatability minimums are out of range")
    thresholds = repeat_config.get("thresholds_by_feature_kind")
    if not isinstance(thresholds, Mapping):
        raise DatasetQCInputError("repeatability thresholds_by_feature_kind is required")

    condition_by_id = {item.condition_id: item for item in scope.expected_conditions}
    entries: list[tuple[DatasetScopeMember, ExpectedCondition, FeatureSet]] = []
    for member in scope.members:
        if member.expected_condition_id is None:
            continue
        if member.sample_id not in condition_valid_samples.get(member.expected_condition_id, ()):
            continue
        condition = condition_by_id[member.expected_condition_id]
        entries.append((member, condition, features_by_id[member.sample_id]))

    grouped: dict[tuple[Any, ...], list[FeatureSet]] = {}
    role_by_group: dict[tuple[Any, ...], CohortRole] = {}
    repeat_by_group: dict[tuple[Any, ...], str] = {}
    for member, condition, feature in entries:
        base = (
            member.cohort_role.value,
            condition.measurement_mode.value,
            condition.configuration_id,
            condition.direction_id,
            condition.direction_angle_deg,
            condition.session_id,
            condition.repeat_type,
        )
        if condition.repeat_type == "CONT":
            key = (*base, condition.acquisition_block_id)
        elif condition.repeat_type == "REPOS":
            key = (*base, condition.assembly_id)
        else:
            key = base
        grouped.setdefault(key, []).append(feature)
        role_by_group[key] = member.cohort_role
        repeat_by_group[key] = condition.repeat_type

    results: list[RepeatabilityGroupResult] = []
    for key, features in grouped.items():
        repeat_type = repeat_by_group[key]
        feature_kind = features[0].feature_kind.value
        profile = thresholds.get(feature_kind)
        if not isinstance(profile, Mapping):
            raise DatasetQCInputError(
                f"repeatability thresholds missing for feature kind {feature_kind}"
            )
        type_thresholds = profile.get(repeat_type)
        if not isinstance(type_thresholds, Mapping):
            raise DatasetQCInputError(
                f"repeatability thresholds missing for {feature_kind}/{repeat_type}"
            )
        try:
            warning = float(type_thresholds["warning_above"])
            exclude = float(type_thresholds["exclude_candidate_above"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DatasetQCInputError("repeatability thresholds must be numeric") from exc
        if not (np.isfinite(warning) and np.isfinite(exclude) and 0.0 <= warning < exclude):
            raise DatasetQCInputError("repeatability thresholds are not ordered")
        units = str(profile.get("units", "")).strip()
        if not units:
            raise DatasetQCInputError("repeatability threshold units are required")

        pairs: list[RepeatabilityPairResult] = []
        for left, right in itertools.combinations(sorted(features, key=lambda item: item.sample_id), 2):
            pair_id = f"{left.sample_id}__{right.sample_id}"
            reason = _repeat_pair_reason(left, right, repeat_type)
            if reason is None and feature_contract_sha256(left) != feature_contract_sha256(right):
                reason = "incompatible_feature_contract"
            common_mask = left.valid_mask & right.valid_mask
            common_count = int(np.count_nonzero(common_mask))
            common_fraction = common_count / max(1, left.valid_mask.size)
            if reason is None and (
                common_count < minimum_features or common_fraction < minimum_fraction
            ):
                reason = "insufficient_common_valid_features"
            if reason is not None:
                pairs.append(
                    RepeatabilityPairResult(
                        pair_id=pair_id,
                        left_sample_id=left.sample_id,
                        right_sample_id=right.sample_id,
                        qualified=False,
                        available=False,
                        distance=None,
                        status=QCCheckStatus.UNAVAILABLE,
                        reason_code=reason,
                        common_valid_feature_count=common_count,
                    )
                )
                continue
            distance = float(
                np.sqrt(np.mean(np.square(left.values[common_mask] - right.values[common_mask])))
            )
            if distance >= exclude:
                status = QCCheckStatus.EXCLUDE_CANDIDATE
                reason = "repeatability_exclude_candidate_threshold_reached"
            elif distance >= warning:
                status = QCCheckStatus.WARNING
                reason = "repeatability_warning_threshold_reached"
            else:
                status = QCCheckStatus.VALID
                reason = None
            pairs.append(
                RepeatabilityPairResult(
                    pair_id=pair_id,
                    left_sample_id=left.sample_id,
                    right_sample_id=right.sample_id,
                    qualified=True,
                    available=True,
                    distance=distance,
                    status=status,
                    reason_code=reason,
                    common_valid_feature_count=common_count,
                )
            )
        qualified = [item for item in pairs if item.qualified and item.available]
        distances = np.asarray(
            [float(item.distance) for item in qualified], dtype=np.float64
        )
        reasons = sorted(
            {item.reason_code for item in pairs if item.reason_code is not None}
        )
        if len(qualified) < minimum_pairs:
            status = QCCheckStatus.UNAVAILABLE
            reasons.append("insufficient_qualified_pairs")
        elif any(item.status is QCCheckStatus.EXCLUDE_CANDIDATE for item in qualified):
            status = QCCheckStatus.EXCLUDE_CANDIDATE
        elif any(item.status is QCCheckStatus.WARNING for item in qualified):
            status = QCCheckStatus.WARNING
        else:
            status = QCCheckStatus.VALID
        group_id = _canonical_sha256({"repeatability_group": key})
        results.append(
            RepeatabilityGroupResult(
                group_id=group_id,
                cohort_role=role_by_group[key],
                repeat_type=repeat_type,
                sample_ids=tuple(sorted(item.sample_id for item in features)),
                sample_count=len(features),
                candidate_pair_count=len(pairs),
                qualified_pair_count=len(qualified),
                warning_threshold=warning,
                exclude_candidate_threshold=exclude,
                units=units,
                status=status,
                reason_codes=tuple(sorted(set(reasons))),
                median_distance=float(np.median(distances)) if distances.size else None,
                mean_distance=float(np.mean(distances)) if distances.size else None,
                sample_std_distance=(
                    float(np.std(distances, ddof=1)) if distances.size >= 2 else None
                ),
                iqr_distance=(
                    float(np.percentile(distances, 75) - np.percentile(distances, 25))
                    if distances.size
                    else None
                ),
                minimum_distance=float(np.min(distances)) if distances.size else None,
                maximum_distance=float(np.max(distances)) if distances.size else None,
                pairs=tuple(pairs),
            )
        )
    return tuple(
        sorted(
            results,
            key=lambda item: (item.cohort_role.value, item.repeat_type, item.group_id),
        )
    )


def _qc_status_from_check_statuses(
    statuses: Sequence[QCCheckStatus],
    *,
    unavailable_required_policy: str,
) -> QCStatus:
    if QCCheckStatus.EXCLUDE_CANDIDATE in statuses:
        return QCStatus.EXCLUDE_CANDIDATE
    if QCCheckStatus.WARNING in statuses:
        return QCStatus.WARNING
    if (
        unavailable_required_policy == "warning"
        and QCCheckStatus.UNAVAILABLE in statuses
    ):
        return QCStatus.WARNING
    return QCStatus.VALID


def _measurement_rollups(
    measurement_qc_by_id: Mapping[str, MeasurementQCResult],
    scope: DatasetQCScope,
    condition_results: Sequence[ConditionCompletenessResult],
    outlier_results: Sequence[SameConditionOutlierResult],
    repeatability_results: Sequence[RepeatabilityGroupResult],
    *,
    unavailable_required_policy: str,
) -> tuple[MeasurementQCRollup, ...]:
    member_by_id = {item.sample_id: item for item in scope.members}
    statuses_by_id: dict[str, list[QCCheckStatus]] = {
        item: [] for item in scope.sample_ids
    }
    warning_by_id: dict[str, list[str]] = {item: [] for item in scope.sample_ids}
    exclude_by_id: dict[str, list[str]] = {item: [] for item in scope.sample_ids}
    unavailable_by_id: dict[str, list[str]] = {item: [] for item in scope.sample_ids}

    for condition in condition_results:
        affected = (*condition.observed_sample_ids, *condition.unexpected_sample_ids)
        for sample_id in affected:
            statuses_by_id[sample_id].append(condition.status)
            for reason in condition.reason_codes:
                qualified = f"condition:{condition.condition_id}:{reason}"
                if condition.status is QCCheckStatus.WARNING:
                    warning_by_id[sample_id].append(qualified)
                elif condition.status is QCCheckStatus.EXCLUDE_CANDIDATE:
                    exclude_by_id[sample_id].append(qualified)
    for outlier in outlier_results:
        statuses_by_id[outlier.sample_id].append(outlier.status)
        qualified = f"same_condition_outlier:{outlier.reason_code or 'valid'}"
        if outlier.status is QCCheckStatus.WARNING:
            warning_by_id[outlier.sample_id].append(qualified)
        elif outlier.status is QCCheckStatus.EXCLUDE_CANDIDATE:
            exclude_by_id[outlier.sample_id].append(qualified)
        elif outlier.status is QCCheckStatus.UNAVAILABLE:
            unavailable_by_id[outlier.sample_id].append(qualified)
    for group in repeatability_results:
        for sample_id in group.sample_ids:
            statuses_by_id[sample_id].append(group.status)
            prefix = f"repeatability:{group.repeat_type}:{group.group_id}"
            if group.status is QCCheckStatus.WARNING:
                warning_by_id[sample_id].extend(
                    f"{prefix}:{reason}" for reason in group.reason_codes
                )
            elif group.status is QCCheckStatus.EXCLUDE_CANDIDATE:
                exclude_by_id[sample_id].extend(
                    f"{prefix}:{reason}" for reason in group.reason_codes
                )
            elif group.status is QCCheckStatus.UNAVAILABLE:
                unavailable_by_id[sample_id].append(prefix)

    scope_review_by_id: dict[str, list[str]] = {
        item: [] for item in scope.sample_ids
    }
    for review in scope.manual_review_records:
        if review.status == "pending":
            for sample_id in review.sample_ids:
                scope_review_by_id[sample_id].append(review.reason_code)

    rollups: list[MeasurementQCRollup] = []
    for sample_id in scope.sample_ids:
        p2a = measurement_qc_by_id[sample_id]
        p2b_status = _qc_status_from_check_statuses(
            statuses_by_id[sample_id],
            unavailable_required_policy=unavailable_required_policy,
        )
        aggregate = (
            QCStatus.EXCLUDE_CANDIDATE
            if QCStatus.EXCLUDE_CANDIDATE in {p2a.aggregate_status, p2b_status}
            else QCStatus.WARNING
            if QCStatus.WARNING in {p2a.aggregate_status, p2b_status}
            else QCStatus.VALID
        )
        warnings = sorted(
            set((*p2a.warning_reasons, *warning_by_id[sample_id]))
        )
        excludes = sorted(
            set((*p2a.exclude_candidate_reasons, *exclude_by_id[sample_id]))
        )
        unavailable = sorted(
            set((*p2a.unavailable_checks, *unavailable_by_id[sample_id]))
        )
        manual = tuple(
            sorted(
                set(
                    (
                        *p2a.manual_review_reasons,
                        *scope_review_by_id[sample_id],
                    )
                )
            )
        )
        eligible = (
            p2a.human_valid
            and not manual
            and aggregate is not QCStatus.EXCLUDE_CANDIDATE
        )
        rollups.append(
            MeasurementQCRollup(
                sample_id=sample_id,
                cohort_role=member_by_id[sample_id].cohort_role,
                p2a_qc_sha256=measurement_qc_sha256(p2a),
                p2a_status=p2a.aggregate_status,
                p2b_status=p2b_status,
                aggregate_status=aggregate,
                warning_reasons=tuple(warnings),
                exclude_candidate_reasons=tuple(excludes),
                unavailable_checks=tuple(unavailable),
                manual_review_reasons=manual,
                human_valid=p2a.human_valid,
                human_exclusion_reason=p2a.human_exclusion_reason,
                eligible_for_downstream=eligible,
            )
        )
    return tuple(rollups)


def evaluate_dataset_quality(
    feature_sets: Sequence[FeatureSet],
    measurement_qc_results: Sequence[MeasurementQCResult],
    scope: DatasetQCScope,
    config: Mapping[str, Any],
) -> DatasetQCResult:
    """Evaluate explicit dataset QC without reading source TXT/WAV artifacts."""
    if config.get("schema_version") != DATASET_QC_SCHEMA_VERSION:
        raise DatasetQCInputError("dataset_quality_control.schema_version must be 1.0.0")
    if not isinstance(config.get("provisional"), bool):
        raise DatasetQCInputError("dataset_quality_control.provisional must be boolean")
    aggregation = config.get("aggregation")
    if not isinstance(aggregation, Mapping):
        raise DatasetQCInputError("dataset_quality_control.aggregation is required")
    unavailable_policy = str(aggregation.get("required_unavailable_policy"))
    if unavailable_policy not in {"preserve", "warning"}:
        raise DatasetQCInputError(
            "aggregation.required_unavailable_policy must be preserve or warning"
        )
    try:
        canonical_allowed_statuses = tuple(
            QCStatus(item) for item in aggregation["canonical_allowed_statuses"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetQCInputError("canonical_allowed_statuses is invalid") from exc
    if not canonical_allowed_statuses or len(set(canonical_allowed_statuses)) != len(
        canonical_allowed_statuses
    ):
        raise DatasetQCInputError("canonical_allowed_statuses must be non-empty and unique")
    for boolean_key in (
        "canonical_block_on_required_unavailable",
        "canonical_block_on_manual_review",
    ):
        if not isinstance(aggregation.get(boolean_key), bool):
            raise DatasetQCInputError(f"aggregation.{boolean_key} must be boolean")
    features_by_id: dict[str, FeatureSet] = {}
    for feature in feature_sets:
        if not isinstance(feature, FeatureSet):
            raise TypeError("P2-B accepts FeatureSet objects only")
        if feature.sample_id in features_by_id:
            raise DatasetQCInputError(f"duplicate FeatureSet sample_id: {feature.sample_id}")
        features_by_id[feature.sample_id] = feature
    qc_by_id: dict[str, MeasurementQCResult] = {}
    for result in measurement_qc_results:
        if not isinstance(result, MeasurementQCResult):
            raise TypeError("P2-B accepts MeasurementQCResult objects only")
        if result.sample_id in qc_by_id:
            raise DatasetQCInputError(f"duplicate MeasurementQCResult sample_id: {result.sample_id}")
        qc_by_id[result.sample_id] = result

    expected_ids = set(scope.sample_ids)
    if set(features_by_id) != expected_ids or set(qc_by_id) != expected_ids:
        raise DatasetQCInputError(
            "scope/input sample mismatch: FeatureSet and P2-A IDs must exactly match scope"
        )

    ordered_features = tuple(features_by_id[item] for item in scope.sample_ids)
    for feature in ordered_features:
        measurement_qc = qc_by_id[feature.sample_id]
        if feature.source_qc_sha256 != measurement_qc_sha256(measurement_qc):
            raise DatasetQCInputError(
                f"FeatureSet source QC hash mismatch: {feature.sample_id}"
            )
        if (
            feature.source_measurement_mode != measurement_qc.measurement_mode
            or feature.meta.data_origin != measurement_qc.data_origin
            or feature.meta.dataset_role != measurement_qc.dataset_role
            or feature.source_qc_status != measurement_qc.aggregate_status
        ):
            raise DatasetQCInputError(
                f"FeatureSet and P2-A identity mismatch: {feature.sample_id}"
            )
        if measurement_qc.run_purpose != scope.run_purpose:
            raise DatasetQCInputError(
                f"P2-A run purpose does not match scope: {feature.sample_id}"
            )

    origins = {feature.meta.data_origin for feature in ordered_features}
    roles = {feature.meta.dataset_role for feature in ordered_features}
    if len(origins) != 1 or len(roles) != 1:
        raise DatasetQCInputError("P2-B scope cannot mix provenance partitions")
    enforce_research_gate(scope.run_purpose, [feature.meta for feature in ordered_features])

    completeness_config = config.get("condition_completeness", {})
    try:
        angle_tolerance = float(completeness_config["direction_match_tolerance_deg"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetQCInputError("direction_match_tolerance_deg must be numeric") from exc
    if not np.isfinite(angle_tolerance) or angle_tolerance < 0.0:
        raise DatasetQCInputError("direction_match_tolerance_deg must be finite and >= 0")
    issue_statuses = {
        "missing": _status_from_config(completeness_config.get("missing_status"), "missing_status"),
        "duplicate": _status_from_config(completeness_config.get("duplicate_status"), "duplicate_status"),
        "unexpected": _status_from_config(completeness_config.get("unexpected_status"), "unexpected_status"),
    }
    conditions_by_id = {item.condition_id: item for item in scope.expected_conditions}
    members_by_condition: dict[str, list[DatasetScopeMember]] = {
        item.condition_id: [] for item in scope.expected_conditions
    }
    explicit_unexpected: list[DatasetScopeMember] = []
    for member in scope.members:
        if member.expected_condition_id is None:
            explicit_unexpected.append(member)
        else:
            members_by_condition[member.expected_condition_id].append(member)

    condition_results: list[ConditionCompletenessResult] = []
    condition_valid_samples: dict[str, tuple[str, ...]] = {}
    for condition in scope.expected_conditions:
        observed: list[str] = []
        unexpected: list[str] = []
        reasons: list[str] = []
        for member in members_by_condition[condition.condition_id]:
            mismatches = _condition_mismatches(
                features_by_id[member.sample_id],
                member,
                condition,
                angle_tolerance=angle_tolerance,
            )
            if mismatches:
                unexpected.append(member.sample_id)
                reasons.extend(
                    f"condition_metadata_mismatch:{member.sample_id}:{field}"
                    for field in mismatches
                )
            else:
                observed.append(member.sample_id)
        observed_count = len(observed)
        missing_count = max(condition.expected_count - observed_count, 0)
        duplicate_count = max(observed_count - condition.expected_count, 0)
        unexpected_count = len(unexpected)
        if missing_count:
            reasons.append("expected_measurements_missing")
        if duplicate_count:
            reasons.append("duplicate_measurements_observed")
        if unexpected_count:
            reasons.append("unexpected_condition_metadata")
        status = QCCheckStatus.VALID
        for issue, count in (
            ("missing", missing_count),
            ("duplicate", duplicate_count),
            ("unexpected", unexpected_count),
        ):
            candidate = issue_statuses[issue]
            if count and candidate is QCCheckStatus.EXCLUDE_CANDIDATE:
                status = QCCheckStatus.EXCLUDE_CANDIDATE
            elif count and status is QCCheckStatus.VALID:
                status = QCCheckStatus.WARNING
        qc_statuses = [qc_by_id[item].aggregate_status for item in observed]
        condition_valid_samples[condition.condition_id] = tuple(observed)
        condition_results.append(
            ConditionCompletenessResult(
                condition_id=condition.condition_id,
                cohort_role=condition.cohort_role,
                expected_count=condition.expected_count,
                observed_count=observed_count,
                valid_count=qc_statuses.count(QCStatus.VALID),
                warning_count=qc_statuses.count(QCStatus.WARNING),
                exclude_candidate_count=qc_statuses.count(QCStatus.EXCLUDE_CANDIDATE),
                missing_count=missing_count,
                duplicate_count=duplicate_count,
                unexpected_count=unexpected_count,
                status=status,
                reason_codes=tuple(sorted(set(reasons))),
                observed_sample_ids=tuple(sorted(observed)),
                unexpected_sample_ids=tuple(sorted(unexpected)),
            )
        )
    if explicit_unexpected:
        # They are kept in the typed result via one deterministic synthetic row.
        sample_ids = tuple(sorted(member.sample_id for member in explicit_unexpected))
        condition_results.append(
            ConditionCompletenessResult(
                condition_id="__unexpected__",
                cohort_role=explicit_unexpected[0].cohort_role,
                expected_count=0,
                observed_count=0,
                valid_count=0,
                warning_count=0,
                exclude_candidate_count=0,
                missing_count=0,
                duplicate_count=0,
                unexpected_count=len(sample_ids),
                status=issue_statuses["unexpected"],
                reason_codes=("sample_explicitly_declared_unexpected",),
                observed_sample_ids=(),
                unexpected_sample_ids=sample_ids,
            )
        )

    outlier_results = _outlier_results(
        features_by_id,
        scope,
        config,
        condition_valid_samples,
    )
    repeatability_results = _repeatability_results(
        features_by_id,
        scope,
        config,
        condition_valid_samples,
    )
    measurement_rollups = _measurement_rollups(
        qc_by_id,
        scope,
        condition_results,
        outlier_results,
        repeatability_results,
        unavailable_required_policy=unavailable_policy,
    )
    member_by_id = {item.sample_id: item for item in scope.members}
    input_audit = tuple(
        DatasetInputAuditRecord(
            sample_id=feature.sample_id,
            cohort_role=member_by_id[feature.sample_id].cohort_role,
            feature_contract_sha256=feature_contract_sha256(feature),
            feature_content_sha256=feature_set_content_sha256(feature),
            p2a_qc_sha256=measurement_qc_sha256(qc_by_id[feature.sample_id]),
            source_sha256=feature.meta.source_sha256,
            selection_reason=member_by_id[feature.sample_id].selection_reason,
        )
        for feature in ordered_features
    )
    return DatasetQCResult(
        schema_version=DATASET_QC_SCHEMA_VERSION,
        analysis_scope_id=scope.analysis_scope_id,
        scope_sha256=scope.sha256,
        config_sha256=_canonical_sha256(dict(config)),
        run_purpose=scope.run_purpose,
        data_origin=next(iter(origins)),
        dataset_role=next(iter(roles)),
        scoped_sample_ids=scope.sample_ids,
        condition_results=tuple(condition_results),
        input_audit=input_audit,
        outlier_results=outlier_results,
        repeatability_results=repeatability_results,
        measurement_rollups=measurement_rollups,
        manual_review_records=scope.manual_review_records,
        unavailable_required_policy=unavailable_policy,
        canonical_allowed_statuses=canonical_allowed_statuses,
        canonical_block_on_required_unavailable=bool(
            aggregation["canonical_block_on_required_unavailable"]
        ),
        canonical_block_on_manual_review=bool(
            aggregation["canonical_block_on_manual_review"]
        ),
        scientifically_eligible=all(
            feature.meta.eligible_for_scientific_analysis
            for feature in ordered_features
        ),
    )

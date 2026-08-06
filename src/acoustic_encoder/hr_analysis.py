"""P6-A auditable resonance calibration over persisted dense sweep FeatureSets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import Enum
import hashlib
import itertools
import json
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from scipy.integrate import trapezoid
from scipy.signal import find_peaks, peak_prominences

from .dataset_quality_control import (
    CohortRole,
    DatasetQCReference,
    DatasetQCResult,
    feature_contract_sha256,
    feature_set_content_sha256,
    validate_dataset_qc_reference,
)
from .feature_axis import FeatureAxisError, feature_frequencies_hz
from .metrics import ScopeRole
from .research_gate import RunPurpose, enforce_research_gate, normalize_run_purpose
from .schemas import DataOrigin, DatasetRole, FeatureKind, FeatureSet, MeasurementMode, Representation


HR_CALIBRATION_SCOPE_SCHEMA_VERSION = "1.0.0"
HR_CALIBRATION_SCHEMA_VERSION = "1.0.0"
PeakStatus = Literal["available", "unavailable"]


class CalibrationStatus(str, Enum):
    DRAFT = "draft"
    SOFTWARE_VALIDATION_ONLY = "software_validation_only"
    APPROVED_REAL_CALIBRATION = "approved_real_calibration"
    SUPERSEDED = "superseded"


class HRInputError(ValueError):
    """Raised when a P6-A scope, input, or feature contract is not trustworthy."""


def _sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_digest(value: str, name: str) -> None:
    digest = value.removeprefix("sha256:")
    if not value.startswith("sha256:") or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise HRInputError(f"{name} must be sha256:<lowercase digest>")


def _require_file_digest(value: str, name: str) -> None:
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise HRInputError(f"{name} must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class FinalTestSeal:
    sealed: bool
    excluded_sample_ids: tuple[str, ...]
    partition_sha256: str

    def __post_init__(self) -> None:
        if not self.sealed:
            raise HRInputError("P6-A requires a sealed final-test partition")
        if len(set(self.excluded_sample_ids)) != len(self.excluded_sample_ids):
            raise HRInputError("final-test excluded sample IDs must be unique")
        _require_digest(self.partition_sha256, "final-test partition hash")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sealed": self.sealed,
            "excluded_sample_ids": list(self.excluded_sample_ids),
            "partition_sha256": self.partition_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FinalTestSeal":
        return cls(bool(value["sealed"]), tuple(value["excluded_sample_ids"]), str(value["partition_sha256"]))


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_record_id: str
    approved_by: str
    approved_at_utc: str
    approval_sha256: str
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.approval_record_id.strip() or not self.approved_by.strip() or not self.approved_at_utc.strip():
            raise HRInputError("approval record identity, reviewer, and timestamp are required")
        _require_digest(self.approval_sha256, "approval record hash")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ApprovalRecord":
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class ResonatorSearchSpec:
    module_id: str
    resonator_id: str
    design_target_hz: float | None
    search_min_hz: float
    search_max_hz: float
    boundary: str
    minimum_prominence_db: float
    minimum_peak_distance_hz: float
    minimum_valid_points: int
    peak_selection_rule: str
    bandwidth_drop_db: float
    integration_method: str
    integration_half_width_hz: float | None
    minimum_integration_coverage: float

    def __post_init__(self) -> None:
        if not self.module_id.strip() or not self.resonator_id.strip():
            raise HRInputError("module_id and resonator_id are required")
        numeric = (self.search_min_hz, self.search_max_hz, self.minimum_prominence_db,
                   self.minimum_peak_distance_hz, self.bandwidth_drop_db,
                   self.minimum_integration_coverage)
        if any(not np.isfinite(item) for item in numeric):
            raise HRInputError("resonator numeric configuration must be finite")
        if self.search_min_hz < 0 or self.search_min_hz >= self.search_max_hz:
            raise HRInputError("resonator search bounds must be increasing")
        if self.boundary not in {"closed", "open", "left_closed_right_open", "left_open_right_closed"}:
            raise HRInputError("unsupported resonator search boundary")
        if self.minimum_prominence_db < 0 or self.minimum_peak_distance_hz <= 0 or self.bandwidth_drop_db <= 0:
            raise HRInputError("resonator thresholds must be positive except prominence may be zero")
        if self.minimum_valid_points < 3:
            raise HRInputError("minimum_valid_points must be >= 3")
        if self.peak_selection_rule != "prominence_then_magnitude_then_lowest_frequency":
            raise HRInputError("unsupported peak selection rule")
        if self.integration_method not in {"measured_3db_band", "fixed_half_width_around_measured_peak"}:
            raise HRInputError("unsupported integration method")
        if self.integration_method == "measured_3db_band" and self.integration_half_width_hz is not None:
            raise HRInputError("measured_3db_band cannot specify integration_half_width_hz")
        if self.integration_method.startswith("fixed_") and (
            self.integration_half_width_hz is None or self.integration_half_width_hz <= 0
        ):
            raise HRInputError("fixed integration requires a positive half width")
        if not 0 < self.minimum_integration_coverage <= 1:
            raise HRInputError("minimum integration coverage must lie in (0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResonatorSearchSpec":
        return cls(**dict(value))


@dataclass(frozen=True, slots=True)
class HRCalibrationScopeMember:
    sample_id: str
    artifact_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str
    feature_content_sha256: str
    feature_contract_sha256: str
    configuration_id: str
    direction_id: str
    direction_angle_deg: float
    session_id: str
    repeat_type: str
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str | None
    calibration_group_id: str
    energy_fraction_group_id: str
    module_ids: tuple[str, ...]
    resonator_ids: tuple[str, ...]
    cohort_role: str
    scope_role: str
    selection_reason: str
    preprocessing_id: str
    data_origin: str
    dataset_role: str

    def __post_init__(self) -> None:
        for name in ("sample_id", "artifact_id", "feature_base_path", "configuration_id", "direction_id",
                     "session_id", "calibration_group_id", "energy_fraction_group_id", "selection_reason",
                     "preprocessing_id"):
            if not str(getattr(self, name)).strip():
                raise HRInputError(f"scope member {name} is required")
        for name in ("feature_npz_sha256", "feature_json_sha256"):
            _require_file_digest(str(getattr(self, name)), name)
        for name in ("feature_content_sha256", "feature_contract_sha256"):
            _require_digest(str(getattr(self, name)), name)
        if self.repeat_type not in {"CONT", "REPOS", "REASM"}:
            raise HRInputError("scope member repeat_type must be CONT, REPOS, or REASM")
        if CohortRole(self.cohort_role) is CohortRole.FINAL_TEST:
            raise HRInputError("final_test cannot be used for HR calibration")
        if ScopeRole(self.scope_role) not in {ScopeRole.CALIBRATION, ScopeRole.TRAINING}:
            raise HRInputError("HR scope role must be calibration or training")
        DataOrigin(self.data_origin)
        DatasetRole(self.dataset_role)
        if not self.module_ids or not self.resonator_ids:
            raise HRInputError("scope member module and resonator IDs are required")

    @classmethod
    def from_feature_set(cls, feature: FeatureSet, **values: Any) -> "HRCalibrationScopeMember":
        return cls(
            sample_id=feature.sample_id,
            feature_content_sha256=feature_set_content_sha256(feature),
            feature_contract_sha256=feature_contract_sha256(feature),
            direction_angle_deg=feature.meta.angle_deg,
            session_id=feature.meta.session_id,
            repeat_type=feature.meta.repeat_type,
            reposition_round_id=feature.meta.reposition_round_id,
            assembly_id=feature.meta.assembly_id,
            acquisition_block_id=feature.meta.acquisition_block_id,
            preprocessing_id=feature.preprocessing_id,
            data_origin=feature.meta.data_origin.value,
            dataset_role=feature.meta.dataset_role.value,
            **values,
        )

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        for name in ("module_ids", "resonator_ids"):
            result[name] = list(result[name])
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRCalibrationScopeMember":
        payload = dict(value)
        payload["module_ids"] = tuple(payload["module_ids"])
        payload["resonator_ids"] = tuple(payload["resonator_ids"])
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class HRCalibrationGroupSpec:
    calibration_group_id: str
    ordered_sample_ids: tuple[str, ...]
    configuration_id: str
    direction_ids: tuple[str, ...]
    session_ids: tuple[str, ...]
    repeat_types: tuple[str, ...]
    pooling_reason: str

    def __post_init__(self) -> None:
        if not self.calibration_group_id.strip() or not self.configuration_id.strip() or not self.pooling_reason.strip():
            raise HRInputError("calibration group identity and pooling reason are required")
        if not self.ordered_sample_ids or len(set(self.ordered_sample_ids)) != len(self.ordered_sample_ids):
            raise HRInputError("calibration group sample IDs must be non-empty and unique")
        if not self.direction_ids or not self.session_ids or not self.repeat_types:
            raise HRInputError("calibration group pooling dimensions must be explicit")
        if any(item not in {"CONT", "REPOS", "REASM"} for item in self.repeat_types):
            raise HRInputError("unsupported calibration group repeat type")

    def to_dict(self) -> dict[str, Any]:
        return {
            "calibration_group_id": self.calibration_group_id,
            "ordered_sample_ids": list(self.ordered_sample_ids),
            "configuration_id": self.configuration_id,
            "direction_ids": list(self.direction_ids),
            "session_ids": list(self.session_ids),
            "repeat_types": list(self.repeat_types),
            "pooling_reason": self.pooling_reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRCalibrationGroupSpec":
        payload = dict(value)
        for name in ("ordered_sample_ids", "direction_ids", "session_ids", "repeat_types"):
            payload[name] = tuple(payload[name])
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class HRCalibrationScope:
    schema_version: str
    hr_calibration_scope_id: str
    run_purpose: RunPurpose
    data_origin: DataOrigin
    dataset_role: DatasetRole
    members: tuple[HRCalibrationScopeMember, ...]
    groups: tuple[HRCalibrationGroupSpec, ...]
    resonators: tuple[ResonatorSearchSpec, ...]
    p2b_reference: DatasetQCReference
    preprocessing_id: str
    random_state: int
    final_test_seal: FinalTestSeal
    requested_calibration_status: str = "software_validation_only"
    approval_record: ApprovalRecord | None = None
    thresholds_frozen: bool = False
    supersedes: str | None = None
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != HR_CALIBRATION_SCOPE_SCHEMA_VERSION:
            raise HRInputError("unsupported HR calibration scope schema")
        if not self.hr_calibration_scope_id.strip() or not self.preprocessing_id.strip():
            raise HRInputError("HR calibration scope ID and preprocessing ID are required")
        object.__setattr__(self, "run_purpose", normalize_run_purpose(self.run_purpose))
        object.__setattr__(self, "data_origin", DataOrigin(self.data_origin))
        object.__setattr__(self, "dataset_role", DatasetRole(self.dataset_role))
        sample_ids = tuple(item.sample_id for item in self.members)
        if not sample_ids or len(set(sample_ids)) != len(sample_ids):
            raise HRInputError("HR calibration scope sample IDs must be non-empty and unique")
        if set(sample_ids) & set(self.final_test_seal.excluded_sample_ids):
            raise HRInputError("final-test sample is present in HR calibration scope")
        if not self.groups or not self.resonators:
            raise HRInputError("HR calibration scope groups and resonators are required")
        if self.requested_calibration_status not in {"draft", "software_validation_only", "approved_real_calibration", "superseded"}:
            raise HRInputError("unsupported requested calibration status")
        if self.requested_calibration_status == "approved_real_calibration" and self.approval_record is None:
            raise HRInputError("approved real calibration requires an approval record")
        if self.requested_calibration_status == "superseded" and not self.superseded_by:
            raise HRInputError("superseded calibration requires superseded_by")
        if len({item.resonator_id for item in self.resonators}) != len(self.resonators):
            raise HRInputError("resonator IDs must be unique")
        group_members = tuple(item for group in self.groups for item in group.ordered_sample_ids)
        if sorted(group_members) != sorted(sample_ids) or len(group_members) != len(sample_ids):
            raise HRInputError("calibration groups must partition the exact scope")
        member_by_id = {item.sample_id: item for item in self.members}
        known_resonators = {item.resonator_id: item for item in self.resonators}
        ordered_specs = sorted(self.resonators, key=lambda item: (item.search_min_hz, item.search_max_hz))
        for left, right in zip(ordered_specs, ordered_specs[1:]):
            if right.search_min_hz < left.search_max_hz:
                raise HRInputError(f"resonator search bands overlap: {left.resonator_id}, {right.resonator_id}")
        for member in self.members:
            if member.preprocessing_id != self.preprocessing_id:
                raise HRInputError(f"scope preprocessing mismatch: {member.sample_id}")
            if DataOrigin(member.data_origin) is not self.data_origin or DatasetRole(member.dataset_role) is not self.dataset_role:
                raise HRInputError(f"scope member provenance mismatch: {member.sample_id}")
            unknown_resonators = set(member.resonator_ids) - set(known_resonators)
            if unknown_resonators:
                raise HRInputError(f"scope member references unknown resonators: {sorted(unknown_resonators)}")
            expected_modules = {known_resonators[item].module_id for item in member.resonator_ids}
            if set(member.module_ids) != expected_modules:
                raise HRInputError(f"scope member module/resonator mismatch: {member.sample_id}")
        for group in self.groups:
            for sample_id in group.ordered_sample_ids:
                member = member_by_id[sample_id]
                if member.calibration_group_id != group.calibration_group_id:
                    raise HRInputError(f"implicit calibration group pooling: {sample_id}")
                if member.configuration_id != group.configuration_id:
                    raise HRInputError(f"implicit cross-configuration pooling: {sample_id}")
                if member.direction_id not in group.direction_ids or member.session_id not in group.session_ids or member.repeat_type not in group.repeat_types:
                    raise HRInputError(f"undeclared calibration pooling dimension: {sample_id}")

    @property
    def ordered_sample_ids(self) -> tuple[str, ...]:
        return tuple(item.sample_id for item in self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hr_calibration_scope_id": self.hr_calibration_scope_id,
            "run_purpose": self.run_purpose.value,
            "data_origin": self.data_origin.value,
            "dataset_role": self.dataset_role.value,
            "members": [item.to_dict() for item in self.members],
            "groups": [item.to_dict() for item in self.groups],
            "resonators": [item.to_dict() for item in self.resonators],
            "p2b_reference": self.p2b_reference.to_dict(),
            "preprocessing_id": self.preprocessing_id,
            "random_state": self.random_state,
            "final_test_seal": self.final_test_seal.to_dict(),
            "requested_calibration_status": self.requested_calibration_status,
            "approval_record": None if self.approval_record is None else self.approval_record.to_dict(),
            "thresholds_frozen": self.thresholds_frozen,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }

    @property
    def sha256(self) -> str:
        return _sha256(self.to_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRCalibrationScope":
        return cls(
            schema_version=str(value["schema_version"]),
            hr_calibration_scope_id=str(value["hr_calibration_scope_id"]),
            run_purpose=RunPurpose(value["run_purpose"]),
            data_origin=DataOrigin(value["data_origin"]),
            dataset_role=DatasetRole(value["dataset_role"]),
            members=tuple(HRCalibrationScopeMember.from_dict(item) for item in value["members"]),
            groups=tuple(HRCalibrationGroupSpec.from_dict(item) for item in value["groups"]),
            resonators=tuple(ResonatorSearchSpec.from_dict(item) for item in value["resonators"]),
            p2b_reference=DatasetQCReference(**dict(value["p2b_reference"])),
            preprocessing_id=str(value["preprocessing_id"]),
            random_state=int(value["random_state"]),
            final_test_seal=FinalTestSeal.from_dict(value["final_test_seal"]),
            requested_calibration_status=str(value.get("requested_calibration_status", "software_validation_only")),
            approval_record=(ApprovalRecord.from_dict(value["approval_record"]) if value.get("approval_record") is not None else None),
            thresholds_frozen=bool(value.get("thresholds_frozen", False)),
            supersedes=value.get("supersedes"),
            superseded_by=value.get("superseded_by"),
        )


@dataclass(frozen=True, slots=True)
class PeakCandidate:
    sample_id: str
    resonator_id: str
    frequency_hz: float
    magnitude_db: float
    prominence_db: float
    prominence_eligible: bool
    distance_eligible: bool
    selected: bool


@dataclass(frozen=True, slots=True)
class DetectedPeak:
    sample_id: str
    resonator_id: str
    status: PeakStatus
    reason: str | None
    candidate_peak_count: int
    eligible_candidate_count: int
    peak_frequency_hz: float | None
    peak_magnitude_db: float | None
    prominence_db: float | None
    search_min_hz: float
    search_max_hz: float
    preprocessing_id: str


@dataclass(frozen=True, slots=True)
class PeakBandwidth:
    sample_id: str
    resonator_id: str
    status: PeakStatus
    reason: str | None
    peak_frequency_hz: float | None
    peak_magnitude_db: float | None
    bandwidth_drop_db: float
    crossing_level_db: float | None
    left_crossing_hz: float | None
    right_crossing_hz: float | None
    bandwidth_hz: float | None
    q_factor: float | None


@dataclass(frozen=True, slots=True)
class IntegratedEnergy:
    sample_id: str
    resonator_id: str
    status: Literal["available", "unavailable"]
    reason: str | None
    method: str
    integration_domain: str
    requested_low_hz: float | None
    requested_high_hz: float | None
    actual_low_hz: float | None
    actual_high_hz: float | None
    valid_point_count: int
    valid_segment_count: int
    coverage_fraction: float
    energy_linear_hz: float | None


@dataclass(frozen=True, slots=True)
class HREnergyFraction:
    energy_fraction_group_id: str
    sample_id: str
    resonator_id: str
    status: Literal["available", "partial", "unavailable"]
    reason: str | None
    q_i: float | None
    energy_linear_hz: float | None
    missing_resonator_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PeakDrift:
    calibration_group_id: str
    resonator_id: str
    repeat_type: str
    status: Literal["available", "unavailable"]
    reasons: tuple[str, ...]
    sample_count: int
    valid_peak_count: int
    unavailable_count: int
    sample_ids: tuple[str, ...]
    valid_sample_ids: tuple[str, ...]
    mean_frequency_hz: float | None
    median_frequency_hz: float | None
    sample_std_hz: float | None
    mad_hz: float | None
    iqr_hz: float | None
    minimum_frequency_hz: float | None
    maximum_frequency_hz: float | None
    peak_to_peak_hz: float | None
    peak_to_peak_percent: float | None
    peak_to_peak_ppm: float | None
    signed_deviation_ppm: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class PeakOverlap:
    sample_id: str
    left_resonator_id: str
    right_resonator_id: str
    status: Literal["available", "unavailable"]
    reason: str | None
    left_bandwidth_status: PeakStatus
    right_bandwidth_status: PeakStatus
    overlap_hz: float | None
    overlap_fraction_of_narrower: float | None


@dataclass(frozen=True, slots=True)
class ResonatorCalibrationSummary:
    calibration_group_id: str
    resonator_id: str
    status: Literal["available", "partial", "unavailable"]
    reasons: tuple[str, ...]
    source_sample_ids: tuple[str, ...]
    source_feature_content_sha256: tuple[str, ...]
    median_peak_frequency_hz: float | None
    median_prominence_db: float | None
    median_bandwidth_hz: float | None
    median_q_factor: float | None
    median_energy_linear_hz: float | None
    repeat_types_present: tuple[str, ...]
    integration_methods: tuple[str, ...]
    preprocessing_id: str
    config_sha256: str
    p2b_aggregate_status: str
    p2b_canonical_ready: bool


@dataclass(frozen=True, slots=True)
class HRCalibrationResult:
    schema_version: str
    hr_calibration_scope_id: str
    scope_sha256: str
    config_sha256: str
    p2b_result_sha256: str
    p2b_analysis_scope_id: str
    p2b_aggregate_status: str
    p2b_canonical_ready: bool
    run_purpose: str
    data_origin: str
    dataset_role: str
    calibration_status: CalibrationStatus
    calibration_usability: str
    frozen_for_research: bool
    scientifically_eligible: bool
    algorithm_version: str
    created_at_utc: str
    approval_record: ApprovalRecord | None
    supersedes: str | None
    superseded_by: str | None
    source_sample_ids: tuple[str, ...]
    source_feature_content_sha256: tuple[str, ...]
    candidates: tuple[PeakCandidate, ...]
    detected_peaks: tuple[DetectedPeak, ...]
    bandwidths: tuple[PeakBandwidth, ...]
    integrated_energies: tuple[IntegratedEnergy, ...]
    energy_fractions: tuple[HREnergyFraction, ...]
    peak_drifts: tuple[PeakDrift, ...]
    peak_overlaps: tuple[PeakOverlap, ...]
    resonator_summaries: tuple[ResonatorCalibrationSummary, ...]
    unavailable_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "calibration_status", CalibrationStatus(self.calibration_status))
        if self.calibration_usability not in {"complete", "partial", "unavailable"}:
            raise HRInputError("unsupported calibration usability")
        if self.calibration_status is CalibrationStatus.APPROVED_REAL_CALIBRATION:
            if not self.frozen_for_research or not self.scientifically_eligible or self.approval_record is None:
                raise HRInputError("approved real calibration requires frozen, eligible, approved state")
        elif self.frozen_for_research or self.scientifically_eligible:
            raise HRInputError("non-approved calibration cannot be frozen or scientifically eligible")
        if self.calibration_status is CalibrationStatus.SUPERSEDED and not self.superseded_by:
            raise HRInputError("superseded calibration requires superseded_by")

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hr_calibration_scope_id": self.hr_calibration_scope_id,
            "scope_sha256": self.scope_sha256,
            "config_sha256": self.config_sha256,
            "p2b_result_sha256": self.p2b_result_sha256,
            "p2b_analysis_scope_id": self.p2b_analysis_scope_id,
            "p2b_aggregate_status": self.p2b_aggregate_status,
            "p2b_canonical_ready": self.p2b_canonical_ready,
            "run_purpose": self.run_purpose,
            "data_origin": self.data_origin,
            "dataset_role": self.dataset_role,
            "calibration_status": self.calibration_status,
            "calibration_usability": self.calibration_usability,
            "frozen_for_research": self.frozen_for_research,
            "scientifically_eligible": self.scientifically_eligible,
            "algorithm_version": self.algorithm_version,
            "created_at_utc": self.created_at_utc,
            "approval_record": None if self.approval_record is None else self.approval_record.to_dict(),
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
            "source_sample_ids": list(self.source_sample_ids),
            "source_feature_content_sha256": list(self.source_feature_content_sha256),
            "candidates": [asdict(item) for item in self.candidates],
            "detected_peaks": [asdict(item) for item in self.detected_peaks],
            "bandwidths": [asdict(item) for item in self.bandwidths],
            "integrated_energies": [asdict(item) for item in self.integrated_energies],
            "energy_fractions": [asdict(item) for item in self.energy_fractions],
            "peak_drifts": [asdict(item) for item in self.peak_drifts],
            "peak_overlaps": [asdict(item) for item in self.peak_overlaps],
            "resonator_summaries": [asdict(item) for item in self.resonator_summaries],
            "unavailable_reasons": list(self.unavailable_reasons),
        }

    @property
    def calibration_id(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {"calibration_id": self.calibration_id, **self._payload()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRCalibrationResult":
        result = cls(
            schema_version=str(value["schema_version"]),
            hr_calibration_scope_id=str(value["hr_calibration_scope_id"]),
            scope_sha256=str(value["scope_sha256"]),
            config_sha256=str(value["config_sha256"]),
            p2b_result_sha256=str(value["p2b_result_sha256"]),
            p2b_analysis_scope_id=str(value["p2b_analysis_scope_id"]),
            p2b_aggregate_status=str(value["p2b_aggregate_status"]),
            p2b_canonical_ready=bool(value["p2b_canonical_ready"]),
            run_purpose=str(value["run_purpose"]),
            data_origin=str(value["data_origin"]),
            dataset_role=str(value["dataset_role"]),
            calibration_status=CalibrationStatus(value["calibration_status"]),
            calibration_usability=str(value["calibration_usability"]),
            frozen_for_research=bool(value["frozen_for_research"]),
            scientifically_eligible=bool(value["scientifically_eligible"]),
            algorithm_version=str(value["algorithm_version"]),
            created_at_utc=str(value["created_at_utc"]),
            approval_record=(ApprovalRecord.from_dict(value["approval_record"]) if value.get("approval_record") else None),
            supersedes=value.get("supersedes"),
            superseded_by=value.get("superseded_by"),
            source_sample_ids=tuple(value["source_sample_ids"]),
            source_feature_content_sha256=tuple(value["source_feature_content_sha256"]),
            candidates=tuple(PeakCandidate(**item) for item in value["candidates"]),
            detected_peaks=tuple(DetectedPeak(**item) for item in value["detected_peaks"]),
            bandwidths=tuple(PeakBandwidth(**item) for item in value["bandwidths"]),
            integrated_energies=tuple(IntegratedEnergy(**item) for item in value["integrated_energies"]),
            energy_fractions=tuple(HREnergyFraction(**{**item, "missing_resonator_ids": tuple(item["missing_resonator_ids"])}) for item in value["energy_fractions"]),
            peak_drifts=tuple(PeakDrift(**{**item, "reasons": tuple(item["reasons"]), "sample_ids": tuple(item["sample_ids"]), "valid_sample_ids": tuple(item["valid_sample_ids"]), "signed_deviation_ppm": tuple(item["signed_deviation_ppm"])}) for item in value["peak_drifts"]),
            peak_overlaps=tuple(PeakOverlap(**item) for item in value["peak_overlaps"]),
            resonator_summaries=tuple(ResonatorCalibrationSummary(**{**item, "reasons": tuple(item["reasons"]), "source_sample_ids": tuple(item["source_sample_ids"]), "source_feature_content_sha256": tuple(item["source_feature_content_sha256"]), "repeat_types_present": tuple(item["repeat_types_present"]), "integration_methods": tuple(item["integration_methods"])}) for item in value["resonator_summaries"]),
            unavailable_reasons=tuple(value["unavailable_reasons"]),
        )
        if value.get("calibration_id") != result.calibration_id:
            raise HRInputError("serialized HR calibration ID mismatch")
        return result


def _band_mask(frequency: np.ndarray, spec: ResonatorSearchSpec) -> np.ndarray:
    left = frequency >= spec.search_min_hz if spec.boundary in {"closed", "left_closed_right_open"} else frequency > spec.search_min_hz
    right = frequency <= spec.search_max_hz if spec.boundary in {"closed", "left_open_right_closed"} else frequency < spec.search_max_hz
    return left & right


def resonator_specs_from_config(config: Mapping[str, Any]) -> tuple[ResonatorSearchSpec, ...]:
    raw = config.get("resonators")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise HRInputError("enabled hr_calibration requires explicit resonators")
    specs: list[ResonatorSearchSpec] = []
    for item in raw:
        if not isinstance(item, Mapping) or not isinstance(item.get("integration"), Mapping):
            raise HRInputError("invalid HR resonator configuration")
        integration = item["integration"]
        specs.append(ResonatorSearchSpec(
            module_id=str(item["module_id"]),
            resonator_id=str(item["resonator_id"]),
            design_target_hz=None if item.get("design_target_hz") is None else float(item["design_target_hz"]),
            search_min_hz=float(item["search_min_hz"]),
            search_max_hz=float(item["search_max_hz"]),
            boundary=str(item["boundary"]),
            minimum_prominence_db=float(item["minimum_prominence_db"]),
            minimum_peak_distance_hz=float(item["minimum_peak_distance_hz"]),
            minimum_valid_points=int(item["minimum_valid_points"]),
            peak_selection_rule=str(item["peak_selection_rule"]),
            bandwidth_drop_db=float(item["bandwidth_drop_db"]),
            integration_method=str(integration["method"]),
            integration_half_width_hz=(None if integration.get("half_width_hz") is None else float(integration["half_width_hz"])),
            minimum_integration_coverage=float(integration["minimum_coverage_fraction"]),
        ))
    return tuple(specs)


def _segments(mask: np.ndarray) -> list[np.ndarray]:
    indices = np.flatnonzero(mask)
    if not indices.size:
        return []
    cuts = np.flatnonzero(np.diff(indices) > 1) + 1
    return [part for part in np.split(indices, cuts) if part.size]


def _validate_feature_contract(feature: FeatureSet, scope: HRCalibrationScope) -> np.ndarray:
    if feature.feature_kind is not FeatureKind.DENSE_RAW_SPL:
        raise HRInputError("P6-A requires dense_raw_spl FeatureSet")
    if feature.source_measurement_mode is not MeasurementMode.REW_SWEEP or feature.source_representation is not Representation.DENSE_SPECTRUM:
        raise HRInputError("P6-A requires dense rew_sweep FeatureSet")
    if feature.normalization_method not in {None, "none"}:
        raise HRInputError("P6-A requires normalization=none")
    if feature.source_magnitude_quantity != "spl" or set(feature.units) != {"dB"}:
        raise HRInputError("P6-A requires known SPL magnitude with dB units")
    if feature.preprocessing_id != scope.preprocessing_id:
        raise HRInputError("P6-A preprocessing contract mismatch")
    if feature.source_qc_sha256 is None or feature.source_qc_eligible_for_downstream is not True:
        raise HRInputError("P6-A requires traceable downstream-eligible P2-A evidence")
    try:
        return feature_frequencies_hz(feature.feature_names, allow_tones=False)
    except FeatureAxisError as exc:
        raise HRInputError(str(exc)) from exc


def _detect(feature: FeatureSet, frequency: np.ndarray, spec: ResonatorSearchSpec) -> tuple[list[PeakCandidate], DetectedPeak]:
    analysis_mask = feature.valid_mask & np.isfinite(feature.values) & _band_mask(frequency, spec)
    segments = _segments(analysis_mask)
    raw: list[dict[str, float]] = []
    for segment in segments:
        if segment.size < spec.minimum_valid_points:
            continue
        local, _ = find_peaks(feature.values[segment])
        if local.size:
            prominence = peak_prominences(feature.values[segment], local)[0]
            for position, value in zip(local, prominence, strict=True):
                index = int(segment[int(position)])
                raw.append({"frequency": float(frequency[index]), "magnitude": float(feature.values[index]), "prominence": float(value)})
    qualifying = [item for item in raw if item["prominence"] >= spec.minimum_prominence_db]
    ranked = sorted(qualifying, key=lambda item: (-item["prominence"], -item["magnitude"], item["frequency"]))
    retained: list[dict[str, float]] = []
    for item in ranked:
        if all(abs(item["frequency"] - previous["frequency"]) >= spec.minimum_peak_distance_hz for previous in retained):
            retained.append(item)
    selected = retained[0] if retained else None
    candidates = [
        PeakCandidate(
            feature.sample_id,
            spec.resonator_id,
            item["frequency"],
            item["magnitude"],
            item["prominence"],
            item in qualifying,
            item in retained,
            item is selected,
        )
        for item in sorted(raw, key=lambda item: item["frequency"])
    ]
    if selected is None:
        reason = "insufficient_valid_points" if not any(segment.size >= spec.minimum_valid_points for segment in segments) else "no_qualified_local_peak"
        peak = DetectedPeak(feature.sample_id, spec.resonator_id, "unavailable", reason, len(raw), len(retained), None, None, None, spec.search_min_hz, spec.search_max_hz, feature.preprocessing_id)
    else:
        peak = DetectedPeak(feature.sample_id, spec.resonator_id, "available", None, len(raw), len(retained), selected["frequency"], selected["magnitude"], selected["prominence"], spec.search_min_hz, spec.search_max_hz, feature.preprocessing_id)
    return candidates, peak


def _interpolated_crossing(
    f_inner: float,
    y_inner: float,
    f_outer: float,
    y_outer: float,
    level: float,
) -> float | None:
    if y_inner == level:
        return f_inner
    if y_outer == level:
        return f_outer
    if not ((y_inner > level and y_outer < level) or (y_inner < level and y_outer > level)):
        return None
    return float(f_inner + (level - y_inner) * (f_outer - f_inner) / (y_outer - y_inner))


def _bandwidth(
    feature: FeatureSet,
    frequency: np.ndarray,
    peak: DetectedPeak,
    spec: ResonatorSearchSpec,
) -> PeakBandwidth:
    if peak.status != "available":
        return PeakBandwidth(feature.sample_id, spec.resonator_id, "unavailable", "peak_unavailable", None, None,
                             spec.bandwidth_drop_db, None, None, None, None, None)
    assert peak.peak_frequency_hz is not None and peak.peak_magnitude_db is not None
    peak_indices = np.flatnonzero(frequency == peak.peak_frequency_hz)
    if peak_indices.size != 1:
        return PeakBandwidth(feature.sample_id, spec.resonator_id, "unavailable", "peak_index_unavailable",
                             peak.peak_frequency_hz, peak.peak_magnitude_db, spec.bandwidth_drop_db,
                             None, None, None, None, None)
    peak_index = int(peak_indices[0])
    valid = feature.valid_mask & np.isfinite(feature.values)
    segment = next((item for item in _segments(valid) if peak_index in item), None)
    level = peak.peak_magnitude_db - spec.bandwidth_drop_db
    if segment is None:
        return PeakBandwidth(feature.sample_id, spec.resonator_id, "unavailable", "peak_segment_unavailable",
                             peak.peak_frequency_hz, peak.peak_magnitude_db, spec.bandwidth_drop_db,
                             level, None, None, None, None)
    start, stop = int(segment[0]), int(segment[-1])
    left = None
    for inner in range(peak_index, start, -1):
        left = _interpolated_crossing(
            float(frequency[inner]), float(feature.values[inner]),
            float(frequency[inner - 1]), float(feature.values[inner - 1]), level,
        )
        if left is not None:
            break
    right = None
    for inner in range(peak_index, stop):
        right = _interpolated_crossing(
            float(frequency[inner]), float(feature.values[inner]),
            float(frequency[inner + 1]), float(feature.values[inner + 1]), level,
        )
        if right is not None:
            break
    if left is None or right is None:
        reason = "left_crossing_unavailable" if left is None else "right_crossing_unavailable"
        return PeakBandwidth(feature.sample_id, spec.resonator_id, "unavailable", reason,
                             peak.peak_frequency_hz, peak.peak_magnitude_db, spec.bandwidth_drop_db,
                             level, left, right, None, None)
    width = float(right - left)
    if not np.isfinite(width) or width <= 0.0:
        return PeakBandwidth(feature.sample_id, spec.resonator_id, "unavailable", "nonpositive_bandwidth",
                             peak.peak_frequency_hz, peak.peak_magnitude_db, spec.bandwidth_drop_db,
                             level, left, right, None, None)
    q_factor = float(peak.peak_frequency_hz / width)
    if not np.isfinite(q_factor) or q_factor <= 0.0:
        return PeakBandwidth(feature.sample_id, spec.resonator_id, "unavailable", "invalid_q_factor",
                             peak.peak_frequency_hz, peak.peak_magnitude_db, spec.bandwidth_drop_db,
                             level, left, right, width, None)
    return PeakBandwidth(feature.sample_id, spec.resonator_id, "available", None,
                         peak.peak_frequency_hz, peak.peak_magnitude_db, spec.bandwidth_drop_db,
                         level, left, right, width, q_factor)


def _segment_integration_points(
    frequency: np.ndarray,
    values_db: np.ndarray,
    segment: np.ndarray,
    low: float,
    high: float,
) -> tuple[np.ndarray, np.ndarray]:
    x = frequency[segment]
    y = values_db[segment]
    if x[-1] < low or x[0] > high:
        return np.array([], dtype=float), np.array([], dtype=float)
    inside = (x >= low) & (x <= high)
    result_x = x[inside].astype(float).tolist()
    result_y = y[inside].astype(float).tolist()
    if x[0] <= low <= x[-1] and (not result_x or result_x[0] > low):
        position = int(np.searchsorted(x, low))
        if position > 0:
            result_x.insert(0, low)
            result_y.insert(0, float(np.interp(low, x[position - 1:position + 1], y[position - 1:position + 1])))
    if x[0] <= high <= x[-1] and (not result_x or result_x[-1] < high):
        position = int(np.searchsorted(x, high))
        if 0 < position < x.size:
            result_x.append(high)
            result_y.append(float(np.interp(high, x[position - 1:position + 1], y[position - 1:position + 1])))
    return np.asarray(result_x, dtype=float), np.asarray(result_y, dtype=float)


def _integrate(
    feature: FeatureSet,
    frequency: np.ndarray,
    peak: DetectedPeak,
    bandwidth: PeakBandwidth,
    spec: ResonatorSearchSpec,
) -> IntegratedEnergy:
    if peak.status != "available":
        return IntegratedEnergy(feature.sample_id, spec.resonator_id, "unavailable", "peak_unavailable",
                                spec.integration_method, "linear_power_ratio", None, None, None, None, 0, 0, 0.0, None)
    assert peak.peak_frequency_hz is not None
    if spec.integration_method == "measured_3db_band":
        if bandwidth.status != "available":
            return IntegratedEnergy(feature.sample_id, spec.resonator_id, "unavailable", "bandwidth_unavailable",
                                    spec.integration_method, "linear_power_ratio", None, None, None, None, 0, 0, 0.0, None)
        assert bandwidth.left_crossing_hz is not None and bandwidth.right_crossing_hz is not None
        low, high = bandwidth.left_crossing_hz, bandwidth.right_crossing_hz
    else:
        assert spec.integration_half_width_hz is not None
        low = peak.peak_frequency_hz - spec.integration_half_width_hz
        high = peak.peak_frequency_hz + spec.integration_half_width_hz
    valid = feature.valid_mask & np.isfinite(feature.values)
    pieces: list[tuple[np.ndarray, np.ndarray]] = []
    covered = 0.0
    point_count = 0
    for segment in _segments(valid):
        x, y = _segment_integration_points(frequency, feature.values, segment, low, high)
        if x.size >= 2:
            pieces.append((x, y))
            covered += float(x[-1] - x[0])
            point_count += int(x.size)
    width = high - low
    coverage = float(min(1.0, covered / width)) if width > 0 else 0.0
    if coverage + 1e-15 < spec.minimum_integration_coverage or not pieces:
        return IntegratedEnergy(feature.sample_id, spec.resonator_id, "unavailable", "integration_coverage_insufficient",
                                spec.integration_method, "linear_power_ratio", low, high,
                                min((x[0] for x, _ in pieces), default=None), max((x[-1] for x, _ in pieces), default=None),
                                point_count, len(pieces), coverage, None)
    energy = float(sum(trapezoid(10.0 ** (y / 10.0), x=x) for x, y in pieces))
    if not np.isfinite(energy) or energy < 0.0:
        return IntegratedEnergy(feature.sample_id, spec.resonator_id, "unavailable", "invalid_integrated_energy",
                                spec.integration_method, "linear_power_ratio", low, high, low, high,
                                point_count, len(pieces), coverage, None)
    return IntegratedEnergy(feature.sample_id, spec.resonator_id, "available", None,
                            spec.integration_method, "linear_power_ratio", low, high, low, high,
                            point_count, len(pieces), coverage, energy)


def _energy_fractions(
    members: Mapping[str, HRCalibrationScopeMember],
    energies: Sequence[IntegratedEnergy],
    missing_policy: str,
    tolerance: float,
) -> tuple[HREnergyFraction, ...]:
    by_key: dict[str, list[IntegratedEnergy]] = {}
    for energy in energies:
        by_key.setdefault(members[energy.sample_id].energy_fraction_group_id, []).append(energy)
    rows: list[HREnergyFraction] = []
    for group_id in sorted(by_key):
        group = by_key[group_id]
        expected = sorted({rid for item in group for rid in members[item.sample_id].resonator_ids})
        available = {item.resonator_id: item for item in group if item.status == "available" and item.energy_linear_hz is not None}
        missing = tuple(item for item in expected if item not in available)
        if missing and missing_policy == "require_all":
            rows.extend(HREnergyFraction(group_id, item.sample_id, item.resonator_id, "unavailable",
                                         "required_resonator_energy_unavailable", None, item.energy_linear_hz, missing)
                        for item in group)
            continue
        total = float(sum(item.energy_linear_hz for item in available.values() if item.energy_linear_hz is not None))
        if not np.isfinite(total) or total <= 0.0:
            rows.extend(HREnergyFraction(group_id, item.sample_id, item.resonator_id, "unavailable",
                                         "nonpositive_energy_sum", None, item.energy_linear_hz, missing)
                        for item in group)
            continue
        status = "partial" if missing else "available"
        for item in group:
            q_i = None if item.resonator_id not in available else float(available[item.resonator_id].energy_linear_hz / total)  # type: ignore[operator]
            rows.append(HREnergyFraction(group_id, item.sample_id, item.resonator_id, status,
                                         "missing_resonators" if missing else None, q_i, item.energy_linear_hz, missing))
        q_sum = sum(item.q_i for item in rows if item.energy_fraction_group_id == group_id and item.q_i is not None)
        if abs(q_sum - 1.0) > tolerance:
            raise HRInputError("HR energy fractions do not sum to one within configured tolerance")
    return tuple(rows)


def _peak_drifts(
    scope: HRCalibrationScope,
    peaks: Sequence[DetectedPeak],
    minimum_valid_peaks: int,
) -> tuple[PeakDrift, ...]:
    member_by_id = {item.sample_id: item for item in scope.members}
    peak_by_key = {(item.sample_id, item.resonator_id): item for item in peaks}
    rows: list[PeakDrift] = []
    for group in sorted(scope.groups, key=lambda item: item.calibration_group_id):
        resonator_ids = sorted({rid for sample_id in group.ordered_sample_ids for rid in member_by_id[sample_id].resonator_ids})
        for resonator_id in resonator_ids:
            for repeat_type in ("CONT", "REPOS", "REASM"):
                sample_ids = tuple(
                    sample_id for sample_id in group.ordered_sample_ids
                    if member_by_id[sample_id].repeat_type == repeat_type
                    and resonator_id in member_by_id[sample_id].resonator_ids
                )
                if not sample_ids:
                    continue
                available = tuple(
                    peak_by_key[(sample_id, resonator_id)] for sample_id in sample_ids
                    if peak_by_key[(sample_id, resonator_id)].status == "available"
                )
                valid_ids = tuple(item.sample_id for item in available)
                values = np.asarray([item.peak_frequency_hz for item in available], dtype=float)
                if values.size < minimum_valid_peaks:
                    rows.append(PeakDrift(
                        group.calibration_group_id, resonator_id, repeat_type, "unavailable",
                        ("insufficient_valid_peaks",), len(sample_ids), int(values.size),
                        len(sample_ids) - int(values.size), sample_ids, valid_ids,
                        None, None, None, None, None, None, None, None, None, None, (),
                    ))
                    continue
                mean = float(np.mean(values))
                median = float(np.median(values))
                standard_deviation = float(np.std(values, ddof=1)) if values.size >= 2 else None
                mad = float(np.median(np.abs(values - median)))
                iqr = float(np.percentile(values, 75) - np.percentile(values, 25))
                minimum = float(np.min(values))
                maximum = float(np.max(values))
                span = maximum - minimum
                relative_percent = float(100.0 * span / median) if median > 0 else None
                relative_ppm = float(1.0e6 * span / median) if median > 0 else None
                signed = tuple(float(1.0e6 * (value - median) / median) for value in values) if median > 0 else ()
                rows.append(PeakDrift(
                    group.calibration_group_id, resonator_id, repeat_type, "available", (),
                    len(sample_ids), int(values.size), len(sample_ids) - int(values.size), sample_ids, valid_ids,
                    mean, median, standard_deviation, mad, iqr, minimum, maximum, span,
                    relative_percent, relative_ppm, signed,
                ))
    return tuple(rows)


def _peak_overlaps(
    members: Mapping[str, HRCalibrationScopeMember],
    bandwidths: Sequence[PeakBandwidth],
) -> tuple[PeakOverlap, ...]:
    by_key = {(item.sample_id, item.resonator_id): item for item in bandwidths}
    rows: list[PeakOverlap] = []
    for sample_id in sorted(members):
        resonator_ids = tuple(sorted(members[sample_id].resonator_ids))
        for left_id, right_id in itertools.combinations(resonator_ids, 2):
            left = by_key[(sample_id, left_id)]
            right = by_key[(sample_id, right_id)]
            if left.status != "available" or right.status != "available":
                rows.append(PeakOverlap(sample_id, left_id, right_id, "unavailable", "bandwidth_unavailable",
                                        left.status, right.status, None, None))
                continue
            assert left.left_crossing_hz is not None and left.right_crossing_hz is not None and left.bandwidth_hz is not None
            assert right.left_crossing_hz is not None and right.right_crossing_hz is not None and right.bandwidth_hz is not None
            overlap = float(max(0.0, min(left.right_crossing_hz, right.right_crossing_hz) - max(left.left_crossing_hz, right.left_crossing_hz)))
            narrower = min(left.bandwidth_hz, right.bandwidth_hz)
            fraction = float(overlap / narrower) if narrower > 0.0 else None
            if fraction is None or not np.isfinite(fraction):
                rows.append(PeakOverlap(sample_id, left_id, right_id, "unavailable", "invalid_bandwidth",
                                        left.status, right.status, None, None))
            else:
                rows.append(PeakOverlap(sample_id, left_id, right_id, "available", None,
                                        left.status, right.status, overlap, fraction))
    return tuple(rows)


def _median_or_none(values: Sequence[float | None]) -> float | None:
    available = np.asarray([item for item in values if item is not None and np.isfinite(item)], dtype=float)
    return None if not available.size else float(np.median(available))


def _resonator_summaries(
    scope: HRCalibrationScope,
    p2b: DatasetQCResult,
    config_sha256: str,
    peaks: Sequence[DetectedPeak],
    bandwidths: Sequence[PeakBandwidth],
    energies: Sequence[IntegratedEnergy],
) -> tuple[ResonatorCalibrationSummary, ...]:
    members = {item.sample_id: item for item in scope.members}
    peak_map = {(item.sample_id, item.resonator_id): item for item in peaks}
    bandwidth_map = {(item.sample_id, item.resonator_id): item for item in bandwidths}
    energy_map = {(item.sample_id, item.resonator_id): item for item in energies}
    rows: list[ResonatorCalibrationSummary] = []
    for group in sorted(scope.groups, key=lambda item: item.calibration_group_id):
        resonator_ids = sorted({rid for sid in group.ordered_sample_ids for rid in members[sid].resonator_ids})
        for resonator_id in resonator_ids:
            sample_ids = tuple(sid for sid in group.ordered_sample_ids if resonator_id in members[sid].resonator_ids)
            selected = [peak_map[(sid, resonator_id)] for sid in sample_ids]
            selected_bw = [bandwidth_map[(sid, resonator_id)] for sid in sample_ids]
            selected_energy = [energy_map[(sid, resonator_id)] for sid in sample_ids]
            unavailable = sorted({
                reason for collection in (selected, selected_bw, selected_energy)
                for item in collection for reason in ([item.reason] if item.reason else [])
            })
            available_count = sum(item.status == "available" for item in selected_energy)
            status = "available" if available_count == len(sample_ids) else ("partial" if available_count else "unavailable")
            rows.append(ResonatorCalibrationSummary(
                group.calibration_group_id,
                resonator_id,
                status,
                tuple(unavailable),
                sample_ids,
                tuple(members[sid].feature_content_sha256 for sid in sample_ids),
                _median_or_none([item.peak_frequency_hz for item in selected]),
                _median_or_none([item.prominence_db for item in selected]),
                _median_or_none([item.bandwidth_hz for item in selected_bw]),
                _median_or_none([item.q_factor for item in selected_bw]),
                _median_or_none([item.energy_linear_hz for item in selected_energy]),
                tuple(item for item in ("CONT", "REPOS", "REASM") if item in {members[sid].repeat_type for sid in sample_ids}),
                tuple(sorted({item.method for item in selected_energy})),
                scope.preprocessing_id,
                config_sha256,
                p2b.aggregate_status.value,
                p2b.canonical_ready,
            ))
    return tuple(rows)


def analyze_sweep_hr_calibration(
    feature_sets: Sequence[FeatureSet],
    scope: HRCalibrationScope,
    dataset_qc_result: DatasetQCResult,
    config: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
) -> HRCalibrationResult:
    """Analyze one explicit sweep calibration scope without reading raw inputs."""
    if config.get("schema_version") != HR_CALIBRATION_SCHEMA_VERSION or config.get("enabled") is not True:
        raise HRInputError("hr_calibration schema 1.0.0 must be explicitly enabled")
    configured_resonators = resonator_specs_from_config(config)
    if configured_resonators != scope.resonators:
        raise HRInputError("HR scope/config resonator search definitions mismatch")
    features = tuple(feature_sets)
    if tuple(item.sample_id for item in features) != scope.ordered_sample_ids:
        raise HRInputError("FeatureSet order must exactly match HR calibration scope")
    frequencies = [_validate_feature_contract(item, scope) for item in features]
    first_contract = feature_contract_sha256(features[0])
    if any(feature_contract_sha256(item) != first_contract for item in features[1:]):
        raise HRInputError("P6-A FeatureSet contract mismatch")
    members = {item.sample_id: item for item in scope.members}
    for feature in features:
        member = members[feature.sample_id]
        if member.feature_content_sha256 != feature_set_content_sha256(feature):
            raise HRInputError(f"scope FeatureSet content mismatch: {feature.sample_id}")
        if member.feature_contract_sha256 != feature_contract_sha256(feature):
            raise HRInputError(f"scope FeatureSet contract mismatch: {feature.sample_id}")
        if member.configuration_id != feature.meta.configuration or member.session_id != feature.meta.session_id or member.repeat_type != feature.meta.repeat_type:
            raise HRInputError(f"scope metadata mismatch: {feature.sample_id}")
        if DataOrigin(member.data_origin) is not feature.meta.data_origin or DatasetRole(member.dataset_role) is not feature.meta.dataset_role:
            raise HRInputError(f"scope provenance mismatch: {feature.sample_id}")
    try:
        validate_dataset_qc_reference(
            features,
            analysis_scope_id=scope.p2b_reference.analysis_scope_id,
            ordered_sample_ids=scope.ordered_sample_ids,
            run_purpose=scope.run_purpose,
            reference=scope.p2b_reference,
            result=dataset_qc_result,
            require_canonical_ready=True,
        )
    except ValueError as exc:
        raise HRInputError(f"P2-B gate failed: {exc}") from exc
    if any(item.meta.data_origin is not scope.data_origin or item.meta.dataset_role is not scope.dataset_role for item in features):
        raise HRInputError("scope provenance does not match FeatureSets")
    candidates: list[PeakCandidate] = []
    peaks: list[DetectedPeak] = []
    bandwidths: list[PeakBandwidth] = []
    energies: list[IntegratedEnergy] = []
    resonators = {item.resonator_id: item for item in scope.resonators}
    for feature, frequency in zip(features, frequencies, strict=True):
        for resonator_id in members[feature.sample_id].resonator_ids:
            found_candidates, peak = _detect(feature, frequency, resonators[resonator_id])
            candidates.extend(found_candidates)
            peaks.append(peak)
            bandwidth = _bandwidth(feature, frequency, peak, resonators[resonator_id])
            bandwidths.append(bandwidth)
            energies.append(_integrate(feature, frequency, peak, bandwidth, resonators[resonator_id]))
    fraction_config = config.get("energy_fraction")
    if not isinstance(fraction_config, Mapping):
        raise HRInputError("hr_calibration energy_fraction configuration is required")
    missing_policy = str(fraction_config.get("missing_resonator_policy"))
    if missing_policy not in {"require_all", "allow_partial"}:
        raise HRInputError("unsupported missing resonator policy")
    tolerance = float(fraction_config.get("sum_tolerance", 0.0))
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise HRInputError("energy fraction sum tolerance must be positive")
    fractions = _energy_fractions(members, energies, missing_policy, tolerance)
    drift_config = config.get("drift")
    if not isinstance(drift_config, Mapping):
        raise HRInputError("hr_calibration drift configuration is required")
    minimum_valid_peaks = drift_config.get("minimum_valid_peaks")
    if isinstance(minimum_valid_peaks, bool) or not isinstance(minimum_valid_peaks, int) or minimum_valid_peaks < 2:
        raise HRInputError("drift minimum_valid_peaks must be an integer >= 2")
    if drift_config.get("reference") != "median_peak_frequency":
        raise HRInputError("drift reference must be median_peak_frequency")
    drifts = _peak_drifts(scope, peaks, minimum_valid_peaks)
    overlaps = _peak_overlaps(members, bandwidths)
    config_sha256 = _sha256(dict(config))
    summaries = _resonator_summaries(scope, dataset_qc_result, config_sha256, peaks, bandwidths, energies)
    unavailable_reasons = tuple(sorted({reason for item in summaries for reason in item.reasons}))
    available_summaries = sum(item.status == "available" for item in summaries)
    usability = "complete" if available_summaries == len(summaries) else ("partial" if available_summaries else "unavailable")
    if scope.requested_calibration_status == "approved_real_calibration":
        if scope.run_purpose is not RunPurpose.RESEARCH_ANALYSIS:
            raise HRInputError("approved real calibration requires research_analysis")
        if scope.data_origin is not DataOrigin.REAL_EXPERIMENT or scope.dataset_role is not DatasetRole.RESEARCH_INPUT:
            raise HRInputError("approved real calibration requires real_experiment research_input")
        if not scope.thresholds_frozen or scope.approval_record is None:
            raise HRInputError("approved real calibration requires frozen thresholds and approval")
        try:
            enforce_research_gate(scope.run_purpose, (item.meta for item in features))
        except ValueError as exc:
            raise HRInputError(f"research hard gate failed: {exc}") from exc
        status = CalibrationStatus.APPROVED_REAL_CALIBRATION
        frozen_for_research = True
        scientifically_eligible = True
    else:
        if scope.requested_calibration_status != "software_validation_only":
            raise HRInputError("analysis may create only software_validation_only or approved_real_calibration")
        if scope.run_purpose is not RunPurpose.SOFTWARE_VALIDATION or scope.data_origin is not DataOrigin.SIMULATED:
            raise HRInputError("software-validation calibration requires simulated/software_validation")
        status = CalibrationStatus.SOFTWARE_VALIDATION_ONLY
        frozen_for_research = False
        scientifically_eligible = False
    return HRCalibrationResult(
        schema_version=HR_CALIBRATION_SCHEMA_VERSION,
        hr_calibration_scope_id=scope.hr_calibration_scope_id,
        scope_sha256=scope.sha256,
        config_sha256=config_sha256,
        p2b_result_sha256=scope.p2b_reference.dataset_qc_result_sha256,
        p2b_analysis_scope_id=scope.p2b_reference.analysis_scope_id,
        p2b_aggregate_status=dataset_qc_result.aggregate_status.value,
        p2b_canonical_ready=dataset_qc_result.canonical_ready,
        run_purpose=scope.run_purpose.value,
        data_origin=scope.data_origin.value,
        dataset_role=scope.dataset_role.value,
        calibration_status=status,
        calibration_usability=usability,
        frozen_for_research=frozen_for_research,
        scientifically_eligible=scientifically_eligible,
        algorithm_version="p6a-sweep-1.0.0",
        created_at_utc=created_at_utc or datetime.now(UTC).isoformat(),
        approval_record=scope.approval_record,
        supersedes=scope.supersedes,
        superseded_by=scope.superseded_by,
        source_sample_ids=scope.ordered_sample_ids,
        source_feature_content_sha256=tuple(item.feature_content_sha256 for item in scope.members),
        candidates=tuple(candidates),
        detected_peaks=tuple(peaks),
        bandwidths=tuple(bandwidths),
        integrated_energies=tuple(energies),
        energy_fractions=fractions,
        peak_drifts=drifts,
        peak_overlaps=overlaps,
        resonator_summaries=summaries,
        unavailable_reasons=unavailable_reasons,
    )

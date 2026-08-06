"""P6-B calibrated multisine HR readout over persisted tone FeatureSets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import hashlib
import json
from typing import Any, Mapping, Sequence

import numpy as np

from .dataset_quality_control import (
    DatasetQCReference,
    DatasetQCResult,
    feature_contract_sha256,
    feature_set_content_sha256,
    validate_dataset_qc_reference,
)
from .hr_analysis import (
    CalibrationStatus,
    FinalTestSeal,
    HRCalibrationResult,
    HRCalibrationScope,
    resonator_specs_from_config,
    _sha256 as calibration_config_sha256,
)
from .feature_axis import FeatureAxisError, feature_frequencies_hz
from .research_gate import RunPurpose, normalize_run_purpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureDerivation,
    FeatureQualityRecord,
    FeatureSet,
    MeasurementMode,
    Representation,
    QCStatus,
)
from .version import FEATURE_SCHEMA_VERSION


HR_READOUT_SCHEMA_VERSION = "1.0.0"
HR_READOUT_SCOPE_SCHEMA_VERSION = "1.0.0"


class HRReadoutInputError(ValueError):
    """Raised when a P6-B input or authority link cannot be trusted."""


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=lambda value: value.item() if isinstance(value, np.generic) else str(value),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _require_digest(value: str, name: str, *, prefixed: bool) -> None:
    digest = value.removeprefix("sha256:")
    if prefixed and not value.startswith("sha256:"):
        raise HRReadoutInputError(f"{name} must start with sha256:")
    if (
        len(digest) != 64
        or digest != digest.lower()
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise HRReadoutInputError(f"{name} must contain a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class HRCalibrationReference:
    calibration_id: str
    calibration_json_path: str
    calibration_json_sha256: str
    calibration_manifest_path: str
    calibration_manifest_sha256: str
    calibration_manifest_digest_path: str
    calibration_manifest_digest_sha256: str

    def __post_init__(self) -> None:
        _require_digest(self.calibration_id, "calibration_id", prefixed=True)
        for name in (
            "calibration_json_sha256",
            "calibration_manifest_sha256",
            "calibration_manifest_digest_sha256",
        ):
            _require_digest(str(getattr(self, name)), name, prefixed=False)
        for name in (
            "calibration_json_path",
            "calibration_manifest_path",
            "calibration_manifest_digest_path",
        ):
            if not str(getattr(self, name)).strip():
                raise HRReadoutInputError(f"{name} is required")

    def to_dict(self) -> dict[str, str]:
        return {
            name: str(getattr(self, name))
            for name in self.__dataclass_fields__
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRCalibrationReference":
        return cls(**{name: str(value[name]) for name in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class HRReadoutScopeMember:
    sample_id: str
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
    dataset_role: DatasetRole
    selection_reason: str
    tone_set_id: str
    tone_set_sha256: str
    stimulus_id: str
    stimulus_sha256: str
    magnitude_quantity: str
    magnitude_reference: str
    cohort_role: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_role", DatasetRole(self.dataset_role))
        for name in (
            "sample_id", "feature_base_path", "configuration_id", "direction_id",
            "session_id", "repeat_type", "selection_reason", "tone_set_id",
            "stimulus_id", "magnitude_quantity", "magnitude_reference", "cohort_role",
        ):
            if not str(getattr(self, name)).strip():
                raise HRReadoutInputError(f"scope member {name} is required")
        if self.repeat_type not in {"CONT", "REPOS", "REASM"}:
            raise HRReadoutInputError("repeat_type must be CONT, REPOS, or REASM")
        if self.cohort_role not in {"development", "training"}:
            raise HRReadoutInputError("P6-B scope cannot contain final_test")
        if not np.isfinite(self.direction_angle_deg) or not 0 <= self.direction_angle_deg < 360:
            raise HRReadoutInputError("direction_angle_deg must lie in [0, 360)")
        for name in ("feature_npz_sha256", "feature_json_sha256", "tone_set_sha256", "stimulus_sha256"):
            _require_digest(str(getattr(self, name)), name, prefixed=False)
        for name in ("feature_content_sha256", "feature_contract_sha256"):
            _require_digest(str(getattr(self, name)), name, prefixed=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name != "dataset_role"
            },
            "dataset_role": self.dataset_role.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRReadoutScopeMember":
        fields = {name: value[name] for name in cls.__dataclass_fields__}
        fields["dataset_role"] = DatasetRole(fields["dataset_role"])
        return cls(**fields)


@dataclass(frozen=True, slots=True)
class HRReadoutScope:
    schema_version: str
    hr_readout_scope_id: str
    members: tuple[HRReadoutScopeMember, ...]
    calibration_reference: HRCalibrationReference
    calibration_group_id: str
    resonator_ids: tuple[str, ...]
    mapping_method: str
    integration_method: str
    p2b_reference: DatasetQCReference
    final_test_seal: FinalTestSeal
    run_purpose: RunPurpose
    data_origin: DataOrigin
    dataset_role: DatasetRole
    random_state: int

    def __post_init__(self) -> None:
        if self.schema_version != HR_READOUT_SCOPE_SCHEMA_VERSION:
            raise HRReadoutInputError("HR readout scope schema_version must be 1.0.0")
        object.__setattr__(self, "run_purpose", normalize_run_purpose(self.run_purpose))
        object.__setattr__(self, "data_origin", DataOrigin(self.data_origin))
        object.__setattr__(self, "dataset_role", DatasetRole(self.dataset_role))
        if not self.hr_readout_scope_id.strip() or not self.calibration_group_id.strip():
            raise HRReadoutInputError("scope and calibration group IDs are required")
        sample_ids = self.ordered_sample_ids
        if not sample_ids or len(sample_ids) != len(set(sample_ids)):
            raise HRReadoutInputError("scope sample IDs must be non-empty and unique")
        if not self.resonator_ids or len(self.resonator_ids) != len(set(self.resonator_ids)):
            raise HRReadoutInputError("resonator IDs must be non-empty and unique")
        if self.mapping_method not in {"nearest_tone", "calibrated_window"}:
            raise HRReadoutInputError("unsupported mapping method")
        expected = {
            "nearest_tone": "nearest_tone_power",
            "calibrated_window": "narrowband_trapezoid",
        }[self.mapping_method]
        if self.integration_method != expected:
            raise HRReadoutInputError("mapping and integration methods are incompatible")
        if isinstance(self.random_state, bool) or not isinstance(self.random_state, int) or self.random_state < 0:
            raise HRReadoutInputError("random_state must be a non-negative integer")
        if not self.final_test_seal.sealed:
            raise HRReadoutInputError("P6-B requires a sealed final-test partition")
        excluded = set(self.final_test_seal.excluded_sample_ids)
        if excluded.intersection(sample_ids):
            raise HRReadoutInputError("P6-B scope contains a sealed final-test sample")
        if any(member.dataset_role is not self.dataset_role for member in self.members):
            raise HRReadoutInputError("scope member dataset roles mismatch")

    @property
    def ordered_sample_ids(self) -> tuple[str, ...]:
        return tuple(member.sample_id for member in self.members)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hr_readout_scope_id": self.hr_readout_scope_id,
            "members": [member.to_dict() for member in self.members],
            "calibration_reference": self.calibration_reference.to_dict(),
            "calibration_group_id": self.calibration_group_id,
            "resonator_ids": list(self.resonator_ids),
            "mapping_method": self.mapping_method,
            "integration_method": self.integration_method,
            "p2b_reference": self.p2b_reference.to_dict(),
            "final_test_seal": self.final_test_seal.to_dict(),
            "run_purpose": self.run_purpose.value,
            "data_origin": self.data_origin.value,
            "dataset_role": self.dataset_role.value,
            "random_state": self.random_state,
        }

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRReadoutScope":
        p2b = value["p2b_reference"]
        return cls(
            schema_version=str(value["schema_version"]),
            hr_readout_scope_id=str(value["hr_readout_scope_id"]),
            members=tuple(HRReadoutScopeMember.from_dict(item) for item in value["members"]),
            calibration_reference=HRCalibrationReference.from_dict(value["calibration_reference"]),
            calibration_group_id=str(value["calibration_group_id"]),
            resonator_ids=tuple(str(item) for item in value["resonator_ids"]),
            mapping_method=str(value["mapping_method"]),
            integration_method=str(value["integration_method"]),
            p2b_reference=DatasetQCReference(
                str(p2b["analysis_scope_id"]), str(p2b["dataset_qc_result_sha256"])
            ),
            final_test_seal=FinalTestSeal.from_dict(value["final_test_seal"]),
            run_purpose=RunPurpose(value["run_purpose"]),
            data_origin=DataOrigin(value["data_origin"]),
            dataset_role=DatasetRole(value["dataset_role"]),
            random_state=int(value["random_state"]),
        )


@dataclass(frozen=True, slots=True)
class CalibrationResonatorWindow:
    resonator_id: str
    measured_peak_frequency_hz: float
    window_low_hz: float
    window_high_hz: float
    window_source: str

    def __post_init__(self) -> None:
        values = (
            self.measured_peak_frequency_hz,
            self.window_low_hz,
            self.window_high_hz,
        )
        if not self.resonator_id or not all(np.isfinite(value) for value in values):
            raise HRReadoutInputError("calibration resonator window must be finite")
        if self.window_low_hz > self.measured_peak_frequency_hz or self.measured_peak_frequency_hz > self.window_high_hz:
            raise HRReadoutInputError("measured peak must lie inside its calibration window")


@dataclass(frozen=True, slots=True)
class ToneMappingResult:
    sample_id: str
    resonator_id: str
    method: str
    status: str
    reasons: tuple[str, ...]
    measured_peak_frequency_hz: float
    selected_tone_ids: tuple[str, ...]
    selected_tone_frequencies_hz: tuple[float, ...]
    signed_detuning_hz: float | None
    absolute_detuning_hz: float | None
    shared_assignment: bool = False


@dataclass(frozen=True, slots=True)
class ToneCoverageResult:
    sample_id: str
    resonator_id: str
    status: str
    reasons: tuple[str, ...]
    expected_low_hz: float
    expected_high_hz: float
    available_tone_count: int
    valid_tone_count: int
    missing_tone_ids: tuple[str, ...]
    invalid_tone_ids: tuple[str, ...]
    first_covered_frequency_hz: float | None
    last_covered_frequency_hz: float | None
    covered_span_hz: float
    requested_span_hz: float
    coverage_fraction: float
    maximum_valid_tone_gap_hz: float | None
    nearest_tone_detuning_hz: float | None
    integration_segments_hz: tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class HRBandEnergyResult:
    sample_id: str
    resonator_id: str
    status: str
    reasons: tuple[str, ...]
    method: str
    energy_value: float | None
    units: str
    actual_integration_bounds_hz: tuple[tuple[float, float], ...]
    valid_tone_count: int
    coverage_fraction: float
    absolute_energy_comparable: bool = False
    absolute_comparability_reason: str = "no_cross_mode_amplitude_calibration"


@dataclass(frozen=True, slots=True)
class HRReadoutEnergyFraction:
    sample_id: str
    energy_fraction_group_id: str
    resonator_id: str
    status: str
    reasons: tuple[str, ...]
    q_i: float | None
    energy_value: float | None
    denominator: float | None
    used_resonator_ids: tuple[str, ...]
    missing_resonator_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SampleHRReadout:
    sample_id: str
    mappings: tuple[ToneMappingResult, ...]
    coverages: tuple[ToneCoverageResult, ...]
    band_energies: tuple[HRBandEnergyResult, ...]
    energy_fractions: tuple[HRReadoutEnergyFraction, ...]
    aggregate_status: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CalibrationAuthority:
    result: HRCalibrationResult
    scope: HRCalibrationScope
    config: Mapping[str, Any]
    calibration_json_sha256: str
    calibration_manifest_sha256: str

    def __post_init__(self) -> None:
        _require_digest(self.calibration_json_sha256, "calibration_json_sha256", prefixed=False)
        _require_digest(self.calibration_manifest_sha256, "calibration_manifest_sha256", prefixed=False)
        if self.result.scope_sha256 != self.scope.sha256:
            raise HRReadoutInputError("calibration result/scope mismatch")
        if self.result.config_sha256 != calibration_config_sha256(dict(self.config)):
            raise HRReadoutInputError("calibration result/config mismatch")


@dataclass(frozen=True, slots=True)
class HRReadoutResult:
    schema_version: str
    hr_readout_scope_id: str
    scope_sha256: str
    config_sha256: str
    calibration_id: str
    calibration_json_sha256: str
    calibration_manifest_sha256: str
    calibration_status: str
    p2b_result_sha256: str
    p2b_analysis_scope_id: str
    p2b_aggregate_status: str
    p2b_canonical_ready: bool
    run_purpose: str
    data_origin: str
    dataset_role: str
    readout_status: str
    frozen_for_research: bool
    scientifically_eligible: bool
    deployment_allowed: bool
    absolute_energy_comparable: bool
    absolute_comparability_reason: str
    phase_policy: str
    uncertainty_status: str
    created_at_utc: str
    source_sample_ids: tuple[str, ...]
    source_feature_content_sha256: tuple[str, ...]
    sample_readouts: tuple[SampleHRReadout, ...]
    unavailable_reasons: tuple[str, ...]

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hr_readout_scope_id": self.hr_readout_scope_id,
            "scope_sha256": self.scope_sha256,
            "config_sha256": self.config_sha256,
            "calibration_id": self.calibration_id,
            "calibration_json_sha256": self.calibration_json_sha256,
            "calibration_manifest_sha256": self.calibration_manifest_sha256,
            "calibration_status": self.calibration_status,
            "p2b_result_sha256": self.p2b_result_sha256,
            "p2b_analysis_scope_id": self.p2b_analysis_scope_id,
            "p2b_aggregate_status": self.p2b_aggregate_status,
            "p2b_canonical_ready": self.p2b_canonical_ready,
            "run_purpose": self.run_purpose,
            "data_origin": self.data_origin,
            "dataset_role": self.dataset_role,
            "readout_status": self.readout_status,
            "frozen_for_research": self.frozen_for_research,
            "scientifically_eligible": self.scientifically_eligible,
            "deployment_allowed": self.deployment_allowed,
            "absolute_energy_comparable": self.absolute_energy_comparable,
            "absolute_comparability_reason": self.absolute_comparability_reason,
            "phase_policy": self.phase_policy,
            "uncertainty_status": self.uncertainty_status,
            "created_at_utc": self.created_at_utc,
            "source_sample_ids": list(self.source_sample_ids),
            "source_feature_content_sha256": list(self.source_feature_content_sha256),
            "sample_readouts": [asdict(item) for item in self.sample_readouts],
            "unavailable_reasons": list(self.unavailable_reasons),
        }

    @property
    def readout_id(self) -> str:
        return _canonical_sha256(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return _json_safe({"readout_id": self.readout_id, **self._payload()})

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRReadoutResult":
        readouts = []
        for item in value["sample_readouts"]:
            readouts.append(
                SampleHRReadout(
                    sample_id=str(item["sample_id"]),
                    mappings=tuple(ToneMappingResult(**{**row, "reasons": tuple(row["reasons"]), "selected_tone_ids": tuple(row["selected_tone_ids"]), "selected_tone_frequencies_hz": tuple(row["selected_tone_frequencies_hz"])}) for row in item["mappings"]),
                    coverages=tuple(ToneCoverageResult(**{**row, "reasons": tuple(row["reasons"]), "missing_tone_ids": tuple(row["missing_tone_ids"]), "invalid_tone_ids": tuple(row["invalid_tone_ids"]), "integration_segments_hz": tuple(tuple(pair) for pair in row["integration_segments_hz"])}) for row in item["coverages"]),
                    band_energies=tuple(HRBandEnergyResult(**{**row, "reasons": tuple(row["reasons"]), "actual_integration_bounds_hz": tuple(tuple(pair) for pair in row["actual_integration_bounds_hz"])}) for row in item["band_energies"]),
                    energy_fractions=tuple(HRReadoutEnergyFraction(**{**row, "reasons": tuple(row["reasons"]), "used_resonator_ids": tuple(row["used_resonator_ids"]), "missing_resonator_ids": tuple(row["missing_resonator_ids"])}) for row in item["energy_fractions"]),
                    aggregate_status=str(item["aggregate_status"]),
                    reasons=tuple(item["reasons"]),
                )
            )
        result = cls(
            schema_version=str(value["schema_version"]),
            hr_readout_scope_id=str(value["hr_readout_scope_id"]),
            scope_sha256=str(value["scope_sha256"]),
            config_sha256=str(value["config_sha256"]),
            calibration_id=str(value["calibration_id"]),
            calibration_json_sha256=str(value["calibration_json_sha256"]),
            calibration_manifest_sha256=str(value["calibration_manifest_sha256"]),
            calibration_status=str(value["calibration_status"]),
            p2b_result_sha256=str(value["p2b_result_sha256"]),
            p2b_analysis_scope_id=str(value["p2b_analysis_scope_id"]),
            p2b_aggregate_status=str(value["p2b_aggregate_status"]),
            p2b_canonical_ready=bool(value["p2b_canonical_ready"]),
            run_purpose=str(value["run_purpose"]),
            data_origin=str(value["data_origin"]),
            dataset_role=str(value["dataset_role"]),
            readout_status=str(value["readout_status"]),
            frozen_for_research=bool(value["frozen_for_research"]),
            scientifically_eligible=bool(value["scientifically_eligible"]),
            deployment_allowed=bool(value["deployment_allowed"]),
            absolute_energy_comparable=bool(value["absolute_energy_comparable"]),
            absolute_comparability_reason=str(value["absolute_comparability_reason"]),
            phase_policy=str(value["phase_policy"]),
            uncertainty_status=str(value["uncertainty_status"]),
            created_at_utc=str(value["created_at_utc"]),
            source_sample_ids=tuple(value["source_sample_ids"]),
            source_feature_content_sha256=tuple(value["source_feature_content_sha256"]),
            sample_readouts=tuple(readouts),
            unavailable_reasons=tuple(value["unavailable_reasons"]),
        )
        if value.get("readout_id") != result.readout_id:
            raise HRReadoutInputError("serialized HR readout ID mismatch")
        return result


@dataclass(frozen=True, slots=True)
class HRReadoutAnalysis:
    result: HRReadoutResult
    hr_band_energy_features: tuple[FeatureSet, ...]
    hr_energy_fraction_features: tuple[FeatureSet, ...]


def _readout_feature_contract(feature: FeatureSet) -> np.ndarray:
    if feature.feature_kind is not FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE:
        raise HRReadoutInputError("P6-B requires tone_measurement_from_multisine")
    if (
        feature.source_measurement_mode is not MeasurementMode.SCHROEDER_MULTISINE
        or feature.source_representation is not Representation.SPARSE_TONES
    ):
        raise HRReadoutInputError("P6-B requires sparse schroeder_multisine FeatureSet")
    if feature.normalization_method != "none" or set(feature.units) != {"dB"}:
        raise HRReadoutInputError("P6-B requires unnormalized dB tone values")
    if not feature.source_magnitude_quantity or not feature.source_magnitude_reference:
        raise HRReadoutInputError("P6-B magnitude semantics are incomplete")
    if len(feature.feature_quality) != len(feature.feature_names):
        raise HRReadoutInputError("feature_quality_evidence_required")
    try:
        return feature_frequencies_hz(feature.feature_names, allow_tones=True)
    except FeatureAxisError as exc:
        raise HRReadoutInputError(str(exc)) from exc


def _severity(status: str) -> int:
    return {"valid": 0, "warning": 1, "unavailable": 2, "exclude_candidate": 3}[status]


def _partition_valid_indices(
    window_indices: list[int], valid_indices: list[int], frequency: np.ndarray, maximum_gap: float
) -> list[list[int]]:
    if not valid_indices:
        return []
    position = {index: offset for offset, index in enumerate(window_indices)}
    segments: list[list[int]] = [[valid_indices[0]]]
    for previous, current in zip(valid_indices, valid_indices[1:]):
        adjacent_authority = position[current] == position[previous] + 1
        within_gap = float(frequency[current] - frequency[previous]) <= maximum_gap
        if adjacent_authority and within_gap:
            segments[-1].append(current)
        else:
            segments.append([current])
    return segments


def _one_readout(
    feature: FeatureSet,
    frequency: np.ndarray,
    window: CalibrationResonatorWindow,
    config: Mapping[str, Any],
) -> tuple[ToneMappingResult, ToneCoverageResult, HRBandEnergyResult]:
    mapping_config = config["tone_mapping"]
    coverage_config = config["coverage"]
    method = str(mapping_config["method"])
    valid = np.asarray(feature.valid_mask, dtype=bool) & np.isfinite(feature.values)
    names = feature.feature_names
    quality = feature.feature_quality
    detuning = frequency - window.measured_peak_frequency_hz
    valid_indices_all = np.flatnonzero(valid).tolist()
    nearest_valid = (
        min(valid_indices_all, key=lambda index: (abs(detuning[index]), frequency[index]))
        if valid_indices_all else None
    )
    nearest_detuning = None if nearest_valid is None else float(detuning[nearest_valid])
    maximum_detuning = float(mapping_config["maximum_detuning_hz"])

    if method == "nearest_tone":
        reasons: list[str] = []
        selected: list[int] = []
        neighborhood = np.flatnonzero(np.abs(detuning) <= maximum_detuning).tolist()
        missing_ids = tuple(
            names[index] for index in neighborhood
            if quality[index].availability == "missing"
        )
        invalid_ids = tuple(
            names[index] for index in neighborhood
            if quality[index].availability in {"invalid", "unavailable"}
        )
        if nearest_valid is None:
            reasons.append("no_valid_tone")
        elif abs(float(detuning[nearest_valid])) > maximum_detuning:
            reasons.append("maximum_detuning_exceeded")
        else:
            selected.append(nearest_valid)
        status = "unavailable" if reasons else "valid"
        selected_frequency = tuple(float(frequency[index]) for index in selected)
        mapping = ToneMappingResult(
            feature.sample_id, window.resonator_id, method, status, tuple(reasons),
            window.measured_peak_frequency_hz,
            tuple(names[index] for index in selected), selected_frequency,
            nearest_detuning, None if nearest_detuning is None else abs(nearest_detuning),
        )
        coverage = ToneCoverageResult(
            feature.sample_id, window.resonator_id, status, tuple(reasons),
            window.measured_peak_frequency_hz, window.measured_peak_frequency_hz,
            sum(quality[index].availability != "missing" for index in neighborhood),
            sum(valid[index] for index in neighborhood), missing_ids, invalid_ids,
            selected_frequency[0] if selected else None,
            selected_frequency[0] if selected else None,
            0.0, 0.0, 1.0 if selected else 0.0, 0.0 if selected else None,
            nearest_detuning,
            tuple((value, value) for value in selected_frequency),
        )
        energy_value = (
            float(10.0 ** (float(feature.values[selected[0]]) / 10.0))
            if selected else None
        )
        energy = HRBandEnergyResult(
            feature.sample_id, window.resonator_id, status, tuple(reasons),
            "nearest_tone_power", energy_value, "relative_tone_power",
            coverage.integration_segments_hz, len(selected), coverage.coverage_fraction,
        )
        return mapping, coverage, energy

    window_indices = np.flatnonzero(
        (frequency >= window.window_low_hz) & (frequency <= window.window_high_hz)
    ).tolist()
    valid_indices = [index for index in window_indices if valid[index]]
    missing = tuple(
        names[index] for index in window_indices if quality[index].availability == "missing"
    )
    invalid = tuple(
        names[index]
        for index in window_indices
        if quality[index].availability in {"invalid", "unavailable"}
    )
    segments = _partition_valid_indices(
        window_indices, valid_indices, frequency, float(coverage_config["maximum_tone_gap_hz"])
    )
    integration_segments = tuple(
        (float(frequency[segment[0]]), float(frequency[segment[-1]]))
        for segment in segments if len(segment) >= 2
    )
    covered_span = float(sum(high - low for low, high in integration_segments))
    requested_span = float(window.window_high_hz - window.window_low_hz)
    coverage_fraction = covered_span / requested_span if requested_span > 0 else 0.0
    adjacent_gaps = np.diff(frequency[valid_indices]) if len(valid_indices) >= 2 else np.array([])
    maximum_gap = float(np.max(adjacent_gaps)) if adjacent_gaps.size else None
    first = float(frequency[valid_indices[0]]) if valid_indices else None
    last = float(frequency[valid_indices[-1]]) if valid_indices else None
    reasons = []
    warning = False
    if missing or invalid:
        if coverage_config["missing_tone_policy"] == "warning":
            warning = True
            reasons.append("missing_or_invalid_tone_warning")
        else:
            reasons.append("missing_or_invalid_tone")
    if len(valid_indices) < int(coverage_config["minimum_valid_tones"]):
        reasons.append("minimum_valid_tones_not_met")
    if coverage_fraction < float(coverage_config["minimum_coverage_fraction"]):
        reasons.append("minimum_coverage_fraction_not_met")
    if maximum_gap is not None and maximum_gap > float(coverage_config["maximum_tone_gap_hz"]):
        reasons.append("maximum_tone_gap_exceeded")
    tolerance = float(coverage_config["endpoint_tolerance_hz"])
    if first is None or first - window.window_low_hz > tolerance or window.window_high_hz - last > tolerance:
        reasons.append("endpoint_coverage_not_met")
    hard_reasons = [reason for reason in reasons if not reason.endswith("_warning")]
    status = "unavailable" if hard_reasons else ("warning" if warning else "valid")
    selected_frequency = tuple(float(frequency[index]) for index in valid_indices)
    mapping = ToneMappingResult(
        feature.sample_id, window.resonator_id, method, status, tuple(reasons),
        window.measured_peak_frequency_hz,
        tuple(names[index] for index in valid_indices), selected_frequency,
        nearest_detuning, None if nearest_detuning is None else abs(nearest_detuning),
    )
    coverage = ToneCoverageResult(
        feature.sample_id, window.resonator_id, status, tuple(reasons),
        window.window_low_hz, window.window_high_hz,
        sum(quality[index].availability != "missing" for index in window_indices),
        len(valid_indices), missing, invalid, first, last, covered_span, requested_span,
        coverage_fraction, maximum_gap, nearest_detuning, integration_segments,
    )
    energy_value: float | None = None
    if status != "unavailable":
        energy_value = 0.0
        for segment in segments:
            if len(segment) < 2:
                continue
            x = frequency[segment]
            power = np.power(10.0, np.asarray(feature.values[segment]) / 10.0)
            energy_value += float(np.sum((power[:-1] + power[1:]) * 0.5 * np.diff(x)))
        if not integration_segments:
            energy_value = None
            status = "unavailable"
            reasons.append("single_tone_cannot_be_integrated")
            mapping = replace(mapping, status=status, reasons=tuple(reasons))
            coverage = replace(coverage, status=status, reasons=tuple(reasons))
    energy = HRBandEnergyResult(
        feature.sample_id, window.resonator_id, status, tuple(reasons),
        "narrowband_trapezoid", energy_value, "relative_power_ratio_hz",
        integration_segments, len(valid_indices), coverage_fraction,
    )
    return mapping, coverage, energy


def readout_multisine_feature(
    feature: FeatureSet,
    resonator_windows: tuple[CalibrationResonatorWindow, ...],
    config: Mapping[str, Any],
) -> SampleHRReadout:
    """Map one persisted P3-C tone FeatureSet without interpolation or raw I/O."""
    frequency = _readout_feature_contract(feature)
    if not resonator_windows:
        raise HRReadoutInputError("P6-B requires calibrated resonator windows")
    rows = [_one_readout(feature, frequency, window, config) for window in resonator_windows]
    mappings = [item[0] for item in rows]
    coverages = [item[1] for item in rows]
    energies = [item[2] for item in rows]

    owners: dict[str, list[int]] = {}
    for index, mapping in enumerate(mappings):
        for tone_id in mapping.selected_tone_ids:
            owners.setdefault(tone_id, []).append(index)
    conflicts = {tone_id: indices for tone_id, indices in owners.items() if len(indices) > 1}
    if conflicts:
        if bool(config["tone_mapping"]["allow_shared_tones"]):
            affected = {index for indices in conflicts.values() for index in indices}
            mappings = [
                replace(item, shared_assignment=True) if index in affected else item
                for index, item in enumerate(mappings)
            ]
        else:
            affected = {index for indices in conflicts.values() for index in indices}
            for index in affected:
                reason = tuple((*mappings[index].reasons, "tone_assignment_conflict"))
                mappings[index] = replace(mappings[index], status="unavailable", reasons=reason)
                coverages[index] = replace(coverages[index], status="unavailable", reasons=reason)
                energies[index] = replace(
                    energies[index], status="unavailable", reasons=reason, energy_value=None
                )

    if feature.source_qc_status is QCStatus.EXCLUDE_CANDIDATE:
        reason = "upstream_qc_exclude_candidate"
        mappings = [replace(item, status="exclude_candidate", reasons=tuple((*item.reasons, reason))) for item in mappings]
        coverages = [replace(item, status="exclude_candidate", reasons=tuple((*item.reasons, reason))) for item in coverages]
        energies = [replace(item, status="exclude_candidate", reasons=tuple((*item.reasons, reason))) for item in energies]
    elif feature.source_qc_status is QCStatus.WARNING:
        reason = "upstream_qc_warning"
        mappings = [replace(item, status="warning", reasons=tuple((*item.reasons, reason))) if item.status == "valid" else item for item in mappings]
        coverages = [replace(item, status="warning", reasons=tuple((*item.reasons, reason))) if item.status == "valid" else item for item in coverages]
        energies = [replace(item, status="warning", reasons=tuple((*item.reasons, reason))) if item.status == "valid" else item for item in energies]

    fraction_config = config["energy_fraction"]
    available = [
        item for item in energies
        if item.status in {"valid", "warning"}
        and item.energy_value is not None
        and np.isfinite(item.energy_value)
        and item.energy_value >= 0.0
    ]
    missing_ids = tuple(item.resonator_id for item in energies if item not in available)
    policy = str(fraction_config["missing_resonator_policy"])
    denominator = float(sum(item.energy_value for item in available)) if available else 0.0
    usable = denominator > 0.0 and (not missing_ids or policy == "allow_partial")
    used_ids = tuple(item.resonator_id for item in available) if usable else ()
    fractions: list[HRReadoutEnergyFraction] = []
    for item in energies:
        if usable and item in available:
            q_i = float(item.energy_value / denominator)
            status = "partial" if missing_ids else "available"
            reasons = ("partial_energy_fraction",) if missing_ids else ()
        else:
            q_i = None
            status = "unavailable"
            reasons = ("required_resonator_energy_unavailable",)
        fractions.append(
            HRReadoutEnergyFraction(
                feature.sample_id, feature.sample_id, item.resonator_id, status,
                reasons, q_i, item.energy_value, denominator if usable else None,
                used_ids, missing_ids,
            )
        )
    if usable:
        q_sum = sum(item.q_i for item in fractions if item.q_i is not None)
        if abs(q_sum - 1.0) > float(fraction_config["sum_tolerance"]):
            raise HRReadoutInputError("energy fractions do not sum to one")
    statuses = [item.status for item in energies]
    aggregate = max(statuses, key=_severity)
    reasons = tuple(sorted({reason for item in energies for reason in item.reasons}))
    return SampleHRReadout(
        feature.sample_id, tuple(mappings), tuple(coverages), tuple(energies),
        tuple(fractions), aggregate, reasons,
    )


def calibrated_resonator_windows(
    authority: CalibrationAuthority,
    calibration_group_id: str,
    resonator_ids: tuple[str, ...],
) -> tuple[CalibrationResonatorWindow, ...]:
    groups = {
        item.calibration_group_id: item for item in authority.scope.groups
    }
    if calibration_group_id not in groups:
        raise HRReadoutInputError("unknown calibration group")
    group = groups[calibration_group_id]
    summaries = {
        (item.calibration_group_id, item.resonator_id): item
        for item in authority.result.resonator_summaries
    }
    specs = {
        item.resonator_id: item
        for item in resonator_specs_from_config(authority.config)
    }
    scope_order = tuple(
        item.resonator_id
        for item in authority.scope.resonators
        if item.resonator_id in resonator_ids
    )
    if scope_order != resonator_ids:
        raise HRReadoutInputError("readout resonator order must match calibration")
    rows: list[CalibrationResonatorWindow] = []
    for resonator_id in resonator_ids:
        summary = summaries.get((calibration_group_id, resonator_id))
        spec = specs.get(resonator_id)
        if summary is None or spec is None or summary.status != "available" or summary.median_peak_frequency_hz is None:
            raise HRReadoutInputError(f"calibration resonator unavailable: {resonator_id}")
        peak = float(summary.median_peak_frequency_hz)
        if spec.integration_method == "fixed_half_width_around_measured_peak":
            assert spec.integration_half_width_hz is not None
            low = peak - float(spec.integration_half_width_hz)
            high = peak + float(spec.integration_half_width_hz)
            source = "p6a_fixed_half_width_around_median_measured_peak"
        else:
            bandwidths = [
                item for item in authority.result.bandwidths
                if item.sample_id in group.ordered_sample_ids
                and item.resonator_id == resonator_id
                and item.status == "available"
                and item.left_crossing_hz is not None
                and item.right_crossing_hz is not None
            ]
            if not bandwidths:
                raise HRReadoutInputError(f"calibration 3 dB window unavailable: {resonator_id}")
            low = float(np.median([item.left_crossing_hz for item in bandwidths]))
            high = float(np.median([item.right_crossing_hz for item in bandwidths]))
            source = "p6a_median_measured_3db_crossings"
        rows.append(CalibrationResonatorWindow(resonator_id, peak, low, high, source))
    return tuple(rows)


def _validate_calibration_lifecycle(
    authority: CalibrationAuthority, scope: HRReadoutScope
) -> None:
    result = authority.result
    if scope.calibration_reference.calibration_id != result.calibration_id:
        raise HRReadoutInputError("calibration semantic ID mismatch")
    if scope.calibration_reference.calibration_json_sha256 != authority.calibration_json_sha256:
        raise HRReadoutInputError("calibration exact-file hash mismatch")
    if scope.calibration_reference.calibration_manifest_sha256 != authority.calibration_manifest_sha256:
        raise HRReadoutInputError("calibration manifest hash mismatch")
    if result.calibration_status is CalibrationStatus.DRAFT:
        raise HRReadoutInputError("draft calibration cannot be used for readout")
    if result.calibration_status is CalibrationStatus.SUPERSEDED:
        raise HRReadoutInputError(
            f"superseded calibration cannot be used; superseded_by={result.superseded_by}"
        )
    if result.calibration_status is CalibrationStatus.SOFTWARE_VALIDATION_ONLY:
        if (
            scope.data_origin is not DataOrigin.SIMULATED
            or scope.run_purpose is not RunPurpose.SOFTWARE_VALIDATION
            or result.data_origin != DataOrigin.SIMULATED.value
            or result.run_purpose != RunPurpose.SOFTWARE_VALIDATION.value
        ):
            raise HRReadoutInputError("software-validation calibration cannot authorize real readout")
    elif result.calibration_status is CalibrationStatus.APPROVED_REAL_CALIBRATION:
        if (
            not result.frozen_for_research
            or not result.scientifically_eligible
            or result.approval_record is None
            or result.calibration_usability != "complete"
            or result.data_origin != DataOrigin.REAL_EXPERIMENT.value
            or result.run_purpose != RunPurpose.RESEARCH_ANALYSIS.value
            or result.dataset_role != DatasetRole.RESEARCH_INPUT.value
            or authority.scope.data_origin is not DataOrigin.REAL_EXPERIMENT
            or authority.scope.run_purpose is not RunPurpose.RESEARCH_ANALYSIS
            or authority.scope.dataset_role is not DatasetRole.RESEARCH_INPUT
            or scope.data_origin is not DataOrigin.REAL_EXPERIMENT
            or scope.run_purpose is not RunPurpose.RESEARCH_ANALYSIS
        ):
            raise HRReadoutInputError("approved-real calibration hard gate failed")
    else:
        raise HRReadoutInputError("unsupported calibration lifecycle")
    if scope.final_test_seal.partition_sha256 != authority.scope.final_test_seal.partition_sha256:
        raise HRReadoutInputError("readout/calibration final-test seal mismatch")


def _validate_scope_features(
    features: tuple[FeatureSet, ...], scope: HRReadoutScope
) -> None:
    if tuple(item.sample_id for item in features) != scope.ordered_sample_ids:
        raise HRReadoutInputError("FeatureSet order must exactly match HR readout scope")
    for feature, member in zip(features, scope.members, strict=True):
        _readout_feature_contract(feature)
        if feature_set_content_sha256(feature) != member.feature_content_sha256:
            raise HRReadoutInputError(f"scope FeatureSet content mismatch: {feature.sample_id}")
        if feature_contract_sha256(feature) != member.feature_contract_sha256:
            raise HRReadoutInputError(f"scope FeatureSet contract mismatch: {feature.sample_id}")
        meta = feature.meta
        checks = {
            "configuration": meta.configuration == member.configuration_id,
            "direction": meta.angle_deg == member.direction_angle_deg,
            "session": meta.session_id == member.session_id,
            "repeat": meta.repeat_type == member.repeat_type,
            "tone_set_id": feature.tone_set_id == member.tone_set_id,
            "tone_set_sha256": feature.tone_set_sha256 == member.tone_set_sha256,
            "stimulus_id": meta.stimulus_id == member.stimulus_id,
            "stimulus_hash": meta.stimulus_hash == member.stimulus_sha256,
            "magnitude_quantity": feature.source_magnitude_quantity == member.magnitude_quantity,
            "magnitude_reference": feature.source_magnitude_reference == member.magnitude_reference,
            "data_origin": meta.data_origin is scope.data_origin,
            "dataset_role": meta.dataset_role is scope.dataset_role,
        }
        mismatched = [name for name, valid in checks.items() if not valid]
        if mismatched:
            raise HRReadoutInputError(
                f"scope FeatureSet metadata mismatch {feature.sample_id}: {', '.join(mismatched)}"
            )


def _feature_quality_from_energy(
    feature_name: str, energy: HRBandEnergyResult, coverage: ToneCoverageResult
) -> FeatureQualityRecord:
    usable = energy.status in {"valid", "warning"} and energy.energy_value is not None
    return FeatureQualityRecord(
        feature_name=feature_name,
        availability="available" if usable else "unavailable",
        valid=usable,
        reason_codes=energy.reasons,
        source_module="P6_B",
        details={
            **asdict(coverage),
            "energy_method": energy.method,
            "energy_status": energy.status,
            "absolute_energy_comparable": energy.absolute_energy_comparable,
            "absolute_comparability_reason": energy.absolute_comparability_reason,
            "uncertainty_status": "unavailable",
        },
    )


def build_hr_feature_sets(
    features: tuple[FeatureSet, ...],
    result: HRReadoutResult,
    scope: HRReadoutScope,
    config: Mapping[str, Any],
) -> tuple[tuple[FeatureSet, ...], tuple[FeatureSet, ...]]:
    preprocessing_id = _canonical_sha256(
        {
            "schema_version": HR_READOUT_SCHEMA_VERSION,
            "calibration_id": result.calibration_id,
            "scope_id": scope.hr_readout_scope_id,
            "config": dict(config),
        }
    )
    energy_features: list[FeatureSet] = []
    fraction_features: list[FeatureSet] = []
    for source, sample in zip(features, result.sample_readouts, strict=True):
        derivation = FeatureDerivation(
            schema_version="1.0.0",
            stage_id="P6_B",
            scope_id=scope.hr_readout_scope_id,
            result_id=result.readout_id,
            source_feature_content_sha256=feature_set_content_sha256(source),
            calibration_id=result.calibration_id,
            calibration_json_sha256=result.calibration_json_sha256,
            calibration_manifest_sha256=result.calibration_manifest_sha256,
            p2b_result_sha256=result.p2b_result_sha256,
            scientifically_eligible=result.scientifically_eligible,
            deployment_allowed=result.deployment_allowed,
            absolute_energy_comparable=result.absolute_energy_comparable,
        )
        energy_names = tuple(
            f"hr_{item.resonator_id}_band_energy" for item in sample.band_energies
        )
        energy_values = np.asarray([
            np.nan if item.energy_value is None else item.energy_value
            for item in sample.band_energies
        ])
        energy_mask = np.asarray([
            item.status in {"valid", "warning"} and item.energy_value is not None
            for item in sample.band_energies
        ])
        units = tuple(item.units for item in sample.band_energies)
        energy_quality = tuple(
            _feature_quality_from_energy(name, energy, coverage)
            for name, energy, coverage in zip(
                energy_names, sample.band_energies, sample.coverages, strict=True
            )
        )
        common = dict(
            sample_id=source.sample_id,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            source_measurement_mode=source.source_measurement_mode,
            source_representation=source.source_representation,
            preprocessing_id=preprocessing_id,
            meta=source.meta,
            tone_set_id=source.tone_set_id,
            tone_set_sha256=source.tone_set_sha256,
            tone_schema_id=source.tone_schema_id,
            normalization_method="none",
            source_magnitude_quantity=source.source_magnitude_quantity,
            source_magnitude_reference=source.source_magnitude_reference,
            source_phase_status=source.source_phase_status,
            fit_scope_id=scope.hr_readout_scope_id,
            calibration_id=result.calibration_id,
            source_qc_status=source.source_qc_status,
            source_qc_sha256=source.source_qc_sha256,
            source_qc_warning_reasons=source.source_qc_warning_reasons,
            source_qc_exclude_candidate_reasons=source.source_qc_exclude_candidate_reasons,
            source_qc_unavailable_checks=source.source_qc_unavailable_checks,
            source_qc_eligible_for_downstream=source.source_qc_eligible_for_downstream,
            derivation=derivation,
        )
        energy_features.append(FeatureSet(
            feature_kind=FeatureKind.HR_BAND_ENERGY,
            feature_names=energy_names,
            values=energy_values,
            valid_mask=energy_mask,
            units=units,
            feature_quality=energy_quality,
            **common,
        ))
        fraction_names = tuple(
            f"hr_{item.resonator_id}_energy_fraction" for item in sample.energy_fractions
        )
        fraction_values = np.asarray([
            np.nan if item.q_i is None else item.q_i for item in sample.energy_fractions
        ])
        fraction_mask = np.asarray([item.q_i is not None for item in sample.energy_fractions])
        fraction_quality = tuple(
            FeatureQualityRecord(
                feature_name=name,
                availability="available" if item.q_i is not None else "unavailable",
                valid=item.q_i is not None,
                reason_codes=item.reasons,
                source_module="P6_B",
                details=asdict(item),
            )
            for name, item in zip(fraction_names, sample.energy_fractions, strict=True)
        )
        fraction_features.append(FeatureSet(
            feature_kind=FeatureKind.HR_ENERGY_FRACTION,
            feature_names=fraction_names,
            values=fraction_values,
            valid_mask=fraction_mask,
            units=("dimensionless",) * len(fraction_names),
            feature_quality=fraction_quality,
            **common,
        ))
    return tuple(energy_features), tuple(fraction_features)


def analyze_multisine_hr_readout(
    feature_sets: Sequence[FeatureSet],
    scope: HRReadoutScope,
    dataset_qc_result: DatasetQCResult,
    calibration: CalibrationAuthority,
    config: Mapping[str, Any],
    *,
    created_at_utc: str | None = None,
) -> HRReadoutAnalysis:
    """Run P6-B from exact persisted artifacts without raw audio or interpolation."""
    if config.get("schema_version") != HR_READOUT_SCHEMA_VERSION or config.get("enabled") is not True:
        raise HRReadoutInputError("hr_readout schema 1.0.0 must be explicitly enabled")
    if (
        config.get("tone_mapping", {}).get("method") != scope.mapping_method
        or config.get("energy", {}).get("method") != scope.integration_method
    ):
        raise HRReadoutInputError("HR readout scope/config method mismatch")
    _validate_calibration_lifecycle(calibration, scope)
    features = tuple(feature_sets)
    _validate_scope_features(features, scope)
    try:
        validate_dataset_qc_reference(
            features,
            analysis_scope_id=scope.p2b_reference.analysis_scope_id,
            ordered_sample_ids=scope.ordered_sample_ids,
            run_purpose=scope.run_purpose,
            reference=scope.p2b_reference,
            result=dataset_qc_result,
            require_canonical_ready=(scope.run_purpose is RunPurpose.RESEARCH_ANALYSIS),
        )
    except ValueError as exc:
        raise HRReadoutInputError(f"P2-B gate failed: {exc}") from exc
    group = next(
        item for item in calibration.scope.groups
        if item.calibration_group_id == scope.calibration_group_id
    )
    if any(member.configuration_id != group.configuration_id for member in scope.members):
        raise HRReadoutInputError("readout/calibration configuration mismatch")
    windows = calibrated_resonator_windows(
        calibration, scope.calibration_group_id, scope.resonator_ids
    )
    readouts = tuple(readout_multisine_feature(feature, windows, config) for feature in features)
    unavailable = tuple(sorted({reason for item in readouts for reason in item.reasons}))
    approved = calibration.result.calibration_status is CalibrationStatus.APPROVED_REAL_CALIBRATION
    all_valid = all(item.aggregate_status == "valid" for item in readouts)
    scientifically_eligible = bool(
        approved
        and dataset_qc_result.canonical_ready
        and dataset_qc_result.scientifically_eligible
        and all_valid
        and all(item.meta.eligible_for_scientific_analysis for item in features)
    )
    result = HRReadoutResult(
        schema_version=HR_READOUT_SCHEMA_VERSION,
        hr_readout_scope_id=scope.hr_readout_scope_id,
        scope_sha256=scope.sha256,
        config_sha256=_canonical_sha256(dict(config)),
        calibration_id=calibration.result.calibration_id,
        calibration_json_sha256=calibration.calibration_json_sha256,
        calibration_manifest_sha256=calibration.calibration_manifest_sha256,
        calibration_status=calibration.result.calibration_status.value,
        p2b_result_sha256=scope.p2b_reference.dataset_qc_result_sha256,
        p2b_analysis_scope_id=scope.p2b_reference.analysis_scope_id,
        p2b_aggregate_status=dataset_qc_result.aggregate_status.value,
        p2b_canonical_ready=dataset_qc_result.canonical_ready,
        run_purpose=scope.run_purpose.value,
        data_origin=scope.data_origin.value,
        dataset_role=scope.dataset_role.value,
        readout_status="approved_real_readout" if scientifically_eligible else "software_validation_only",
        frozen_for_research=bool(approved and calibration.result.frozen_for_research),
        scientifically_eligible=scientifically_eligible,
        deployment_allowed=False,
        absolute_energy_comparable=False,
        absolute_comparability_reason="no_cross_mode_amplitude_calibration",
        phase_policy="magnitude_only",
        uncertainty_status="unavailable",
        created_at_utc=created_at_utc or datetime.now(UTC).isoformat(),
        source_sample_ids=scope.ordered_sample_ids,
        source_feature_content_sha256=tuple(
            feature_set_content_sha256(item) for item in features
        ),
        sample_readouts=readouts,
        unavailable_reasons=unavailable,
    )
    energy_features, fraction_features = build_hr_feature_sets(features, result, scope, config)
    return HRReadoutAnalysis(result, energy_features, fraction_features)

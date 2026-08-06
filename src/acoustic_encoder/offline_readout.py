"""P9-D frozen-package offline single-measurement direction readout."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

import numpy as np

from .cross_mode_bridge import CrossModeCalibrationModel, apply_tone_calibration
from .dataset_quality_control import feature_set_content_sha256
from .direction_models import (
    FrozenDirectionModel,
    predict_frozen_direction_model,
)
from .quality_control import MeasurementQCResult
from .schemas import DataOrigin, DatasetRole, MeasurementMode, PhaseStatus, Representation, SpectrumData
from .tone_features import ToneFeatureConstructionError, build_multisine_tone_feature_set
from .tone_sets import ToneSetDefinition


READOUT_SCHEMA_VERSION = "1.0.0"


class OfflineReadoutError(ValueError):
    """Raised when a frozen readout artifact cannot be trusted."""


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def normalize_sha256(value: str) -> str:
    text = str(value)
    return text if text.startswith("sha256:") else "sha256:" + text


def require_sha256(value: str, label: str) -> str:
    normalized = normalize_sha256(value)
    digest = normalized.removeprefix("sha256:")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise OfflineReadoutError(f"{label} must contain a lowercase SHA-256 digest")
    return normalized


@dataclass(frozen=True, slots=True)
class ReadoutInputReference:
    schema_version: str
    sample_id: str
    spectrum_json_sha256: str
    spectrum_npz_sha256: str
    p8_manifest_sha256: str
    tone_quality_sha256: str
    measurement_qc_sha256: str
    metadata_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != READOUT_SCHEMA_VERSION or not self.sample_id:
            raise OfflineReadoutError("ReadoutInputReference requires schema 1.0.0 and sample_id")
        for name in self.__slots__[2:]:
            require_sha256(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReadoutInputReference":
        return cls(**{name: payload[name] for name in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class FrozenReadoutPackage:
    schema_version: str
    package_id: str
    lifecycle: str
    created_utc: str
    data_origin: str
    run_purpose: str
    stimulus_id: str
    stimulus_waveform_sha256: str
    stimulus_manifest_file_sha256: str
    stimulus_manifest_semantic_sha256: str
    tone_set_id: str
    tone_set_sha256: str
    tones_sha256: str
    ordered_tone_ids: tuple[str, ...]
    ordered_frequencies_hz: tuple[float, ...]
    sample_rate_hz: int
    period_samples: int
    stable_period_count: int
    discard_initial_period_count: int
    p3_preprocessing_snapshot: Mapping[str, Any]
    p3_preprocessing_snapshot_sha256: str
    expected_preprocessing_id: str
    feature_kind: str
    units: tuple[str, ...]
    normalization_method: str
    magnitude_quantity: str
    magnitude_reference: str | None
    model_id: str
    model_domain: str
    model_semantic_sha256: str
    model_file_sha256: str
    authority_hashes: Mapping[str, str]
    qc_policy_snapshot: Mapping[str, Any]
    qc_policy_snapshot_sha256: str
    calibration_required: bool
    calibration_model_semantic_sha256: str | None
    calibration_mapping_direction: str | None
    pipeline_version: str
    config_schema_version: str
    measurement_schema_version: str
    feature_schema_version: str
    training_sample_ids: tuple[str, ...]
    training_aggregate_sha256: str
    sealed_final_test_sample_ids: tuple[str, ...]
    sealed_final_test_sha256: str
    final_test_read: bool
    scientifically_eligible: bool
    deployment_eligible: bool
    canonical_analysis: bool

    def __post_init__(self) -> None:
        if self.schema_version != READOUT_SCHEMA_VERSION or not self.package_id:
            raise OfflineReadoutError("FrozenReadoutPackage requires schema 1.0.0 and package_id")
        if (self.lifecycle, self.data_origin, self.run_purpose) != (
            "software_validation_only", "simulated", "software_validation"
        ):
            raise OfflineReadoutError("DEV-C15 package is simulated software_validation_only")
        if self.final_test_read or self.scientifically_eligible or self.deployment_eligible or self.canonical_analysis:
            raise OfflineReadoutError("simulated package cannot claim final-test/science/deployment/canonical status")
        if not self.ordered_tone_ids or len(self.ordered_tone_ids) != len(self.ordered_frequencies_hz):
            raise OfflineReadoutError("package ordered tones must be non-empty and aligned")
        if len(self.units) != len(self.ordered_tone_ids):
            raise OfflineReadoutError("package units must align with ordered tones")
        for name in (
            "stimulus_waveform_sha256", "stimulus_manifest_file_sha256",
            "stimulus_manifest_semantic_sha256", "tone_set_sha256", "tones_sha256",
            "p3_preprocessing_snapshot_sha256", "expected_preprocessing_id",
            "model_semantic_sha256", "qc_policy_snapshot_sha256",
            "model_file_sha256",
            "training_aggregate_sha256", "sealed_final_test_sha256",
        ):
            require_sha256(getattr(self, name), name)
        if self.sample_rate_hz <= 0 or self.period_samples <= 0 or self.stable_period_count <= 0 or self.discard_initial_period_count < 0:
            raise OfflineReadoutError("package sample-rate and period counts are invalid")
        for name, value in self.authority_hashes.items():
            require_sha256(value, f"authority_hashes.{name}")
        if self.calibration_model_semantic_sha256 is not None:
            require_sha256(self.calibration_model_semantic_sha256, "calibration_model_semantic_sha256")

    @classmethod
    def create(
        cls, *, package_id: str, created_utc: str, stimulus_id: str,
        stimulus_waveform_sha256: str, stimulus_manifest_file_sha256: str,
        stimulus_manifest_semantic_sha256: str, tone_set: ToneSetDefinition,
        model: FrozenDirectionModel, matched_tone_config: Mapping[str, Any],
        qc_policy: Mapping[str, Any], authority_hashes: Mapping[str, str],
        pipeline_version: str, config_schema_version: str,
        measurement_schema_version: str, feature_schema_version: str,
        stable_period_count: int,
        discard_initial_period_count: int,
        calibration_model_semantic_sha256: str | None = None,
        calibration_mapping_direction: str | None = None,
    ) -> "FrozenReadoutPackage":
        p3_hash = canonical_sha256(dict(matched_tone_config))
        qc_hash = canonical_sha256(dict(qc_policy))
        model_file_bytes = (json.dumps(model.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        model_file_sha256 = "sha256:" + hashlib.sha256(model_file_bytes).hexdigest()
        return cls(
            READOUT_SCHEMA_VERSION, package_id, "software_validation_only", created_utc,
            "simulated", "software_validation", stimulus_id,
            normalize_sha256(stimulus_waveform_sha256), normalize_sha256(stimulus_manifest_file_sha256),
            normalize_sha256(stimulus_manifest_semantic_sha256), tone_set.tone_set_id,
            normalize_sha256(tone_set.tone_set_sha256), normalize_sha256(tone_set.tones_sha256),
            tone_set.feature_names, tuple(float(item) for item in tone_set.frequency_hz),
            tone_set.sample_rate_hz, tone_set.period_samples, int(stable_period_count),
            int(discard_initial_period_count), dict(matched_tone_config), p3_hash,
            model.preprocessing_id, model.feature_kind, model.units, model.normalization_method,
            model.magnitude_quantity, model.magnitude_reference, model.model_id, model.model_domain,
            model.semantic_sha256, model_file_sha256, dict(authority_hashes), dict(qc_policy), qc_hash,
            model.model_domain != "multisine", calibration_model_semantic_sha256,
            calibration_mapping_direction, pipeline_version, config_schema_version,
            measurement_schema_version, feature_schema_version, model.training_sample_ids,
            model.training_aggregate_sha256, model.sealed_final_test_sample_ids,
            model.sealed_final_test_sha256, False, False, False, False,
        )

    def _semantic_payload(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in (
            "ordered_tone_ids", "ordered_frequencies_hz", "units", "training_sample_ids",
            "sealed_final_test_sample_ids",
        ):
            payload[name] = list(payload[name])
        payload["p3_preprocessing_snapshot"] = dict(self.p3_preprocessing_snapshot)
        payload["qc_policy_snapshot"] = dict(self.qc_policy_snapshot)
        payload["authority_hashes"] = dict(sorted(self.authority_hashes.items()))
        return payload

    @property
    def semantic_sha256(self) -> str:
        return canonical_sha256(self._semantic_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._semantic_payload()
        payload["package_semantic_sha256"] = self.semantic_sha256
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FrozenReadoutPackage":
        value = dict(payload)
        expected = value.pop("package_semantic_sha256", None)
        for name in (
            "ordered_tone_ids", "ordered_frequencies_hz", "units", "training_sample_ids",
            "sealed_final_test_sample_ids",
        ):
            value[name] = tuple(value[name])
        result = cls(**value)
        if expected is not None and expected != result.semantic_sha256:
            raise OfflineReadoutError("frozen readout package semantic hash mismatch")
        return result


@dataclass(frozen=True, slots=True)
class ReadoutQCAudit:
    status: str
    required_tone_count: int
    valid_tone_count: int
    required_tone_coverage: float
    phase_status: str
    phase_used: bool
    synchronization_status: str
    clock_drift_status: str
    clipping_status: str
    p8_aggregate_status: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["reasons"] = list(self.reasons)
        payload["warnings"] = list(self.warnings)
        payload["details"] = dict(self.details)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReadoutQCAudit":
        value = dict(payload)
        value["reasons"] = tuple(value["reasons"])
        value["warnings"] = tuple(value["warnings"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ReadoutFeatureAudit:
    available: bool
    feature_set_sha256: str | None
    preprocessing_id: str | None
    feature_names: tuple[str, ...]
    valid_mask: tuple[bool, ...]
    normalization_method: str | None
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        for name in ("feature_names", "valid_mask", "reason_codes"):
            payload[name] = list(payload[name])
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReadoutFeatureAudit":
        value = dict(payload)
        for name in ("feature_names", "valid_mask", "reason_codes"):
            value[name] = tuple(value[name])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ReadoutCalibrationAudit:
    requested: bool
    applied: bool
    model_semantic_sha256: str | None
    mapping_direction: str | None
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["reason_codes"] = list(self.reason_codes)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReadoutCalibrationAudit":
        value = dict(payload)
        value["reason_codes"] = tuple(value["reason_codes"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ReadoutPrediction:
    available: bool
    predicted_direction_deg: float | None
    second_direction_deg: float | None
    score: float | None
    second_score: float | None
    margin: float | None
    score_kind: str
    higher_is_better: bool
    confidence_status: str
    qc_status: str
    unavailable_reason: str | None
    model_id: str
    model_version: str
    model_sha256: str
    tone_set_id: str
    tone_set_sha256: str
    calibration_applied: bool
    calibration_model_sha256: str | None
    feature_set_sha256: str | None
    input_p8_sha256: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["warnings"] = list(self.warnings)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReadoutPrediction":
        value = dict(payload)
        value["warnings"] = tuple(value["warnings"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class OfflineReadoutResult:
    schema_version: str
    package_id: str
    package_semantic_sha256: str
    sample_id: str
    processing_status: str
    input_reference: ReadoutInputReference
    qc_audit: ReadoutQCAudit
    feature_audit: ReadoutFeatureAudit
    calibration_audit: ReadoutCalibrationAudit
    prediction: ReadoutPrediction
    failure_reasons: tuple[str, ...]
    scientifically_eligible: bool
    deployment_eligible: bool
    canonical_analysis: bool
    final_test_read: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version, "package_id": self.package_id,
            "package_semantic_sha256": self.package_semantic_sha256, "sample_id": self.sample_id,
            "processing_status": self.processing_status, "input_reference": self.input_reference.to_dict(),
            "qc_audit": self.qc_audit.to_dict(), "feature_audit": self.feature_audit.to_dict(),
            "calibration_audit": self.calibration_audit.to_dict(), "prediction": self.prediction.to_dict(),
            "failure_reasons": list(self.failure_reasons),
            "scientifically_eligible": self.scientifically_eligible,
            "deployment_eligible": self.deployment_eligible, "canonical_analysis": self.canonical_analysis,
            "final_test_read": self.final_test_read,
        }

    @property
    def semantic_sha256(self) -> str:
        return canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OfflineReadoutResult":
        return cls(
            schema_version=str(payload["schema_version"]), package_id=str(payload["package_id"]),
            package_semantic_sha256=str(payload["package_semantic_sha256"]),
            sample_id=str(payload["sample_id"]), processing_status=str(payload["processing_status"]),
            input_reference=ReadoutInputReference.from_dict(payload["input_reference"]),
            qc_audit=ReadoutQCAudit.from_dict(payload["qc_audit"]),
            feature_audit=ReadoutFeatureAudit.from_dict(payload["feature_audit"]),
            calibration_audit=ReadoutCalibrationAudit.from_dict(payload["calibration_audit"]),
            prediction=ReadoutPrediction.from_dict(payload["prediction"]),
            failure_reasons=tuple(payload["failure_reasons"]),
            scientifically_eligible=bool(payload["scientifically_eligible"]),
            deployment_eligible=bool(payload["deployment_eligible"]),
            canonical_analysis=bool(payload["canonical_analysis"]),
            final_test_read=bool(payload["final_test_read"]),
        )


def _unavailable_prediction(
    package: FrozenReadoutPackage, model: FrozenDirectionModel,
    input_reference: ReadoutInputReference, qc_status: str, reason: str,
    warnings: tuple[str, ...], feature_sha256: str | None = None,
) -> ReadoutPrediction:
    return ReadoutPrediction(
        False, None, None, None, None, None, model.score_kind, model.higher_is_better,
        "unavailable", qc_status, reason, model.model_id, model.schema_version,
        model.semantic_sha256, package.tone_set_id, package.tone_set_sha256, False, None,
        feature_sha256, input_reference.spectrum_json_sha256, warnings,
    )


def run_offline_readout(
    spectrum: SpectrumData,
    measurement_qc: MeasurementQCResult,
    tone_set: ToneSetDefinition,
    matched_tone_config: Mapping[str, Any],
    package: FrozenReadoutPackage,
    model: FrozenDirectionModel,
    input_reference: ReadoutInputReference,
    *,
    calibration_model: CrossModeCalibrationModel | None,
) -> OfflineReadoutResult:
    """Audit and infer one persisted P8 result; this function never fits state."""
    blocked: list[str] = []
    warnings: list[str] = []
    if input_reference.sample_id != spectrum.meta.sample_id or measurement_qc.sample_id != spectrum.meta.sample_id:
        blocked.append("sample_identity_mismatch")
    if spectrum.meta.measurement_mode is not MeasurementMode.SCHROEDER_MULTISINE or spectrum.representation is not Representation.SPARSE_TONES:
        blocked.append("invalid_input_representation")
    if spectrum.meta.data_origin is not DataOrigin.SIMULATED or measurement_qc.run_purpose.value != "software_validation":
        blocked.append("provenance_mismatch")
    if spectrum.meta.dataset_role is not DatasetRole.SOFTWARE_VALIDATION or spectrum.meta.eligible_for_scientific_analysis:
        blocked.append("scientific_eligibility_mismatch")
    if spectrum.meta.stimulus_id != package.stimulus_id or normalize_sha256(spectrum.meta.stimulus_hash or "") != package.stimulus_waveform_sha256:
        blocked.append("stimulus_lineage_mismatch")
    if tone_set.tone_set_id != package.tone_set_id or normalize_sha256(tone_set.tone_set_sha256) != package.tone_set_sha256:
        blocked.append("tone-set_authority_mismatch")
    if tuple(tone_set.feature_names) != package.ordered_tone_ids or tuple(tone_set.frequency_hz) != package.ordered_frequencies_hz:
        blocked.append("tone-set_order_mismatch")
    if canonical_sha256(dict(matched_tone_config)) != package.p3_preprocessing_snapshot_sha256:
        blocked.append("preprocessing_snapshot_mismatch")
    if model.semantic_sha256 != package.model_semantic_sha256 or model.model_id != package.model_id:
        blocked.append("model_authority_mismatch")
    if dict(model.authority_hashes) != dict(package.authority_hashes):
        blocked.append("model_package_authority_mismatch")
    requested_calibration = package.calibration_required or calibration_model is not None
    calibration_reasons: list[str] = []
    if package.calibration_required and calibration_model is None:
        blocked.append("calibration_required")
        calibration_reasons.append("calibration_required")
    if calibration_model is not None:
        if calibration_model.outer_fold_id != "frozen_readout":
            blocked.append("cv_fold_calibration_forbidden")
            calibration_reasons.append("cv_fold_calibration_forbidden")
        if calibration_model.mapping_direction != "multisine_db_to_sweep_projection_db":
            blocked.append("calibration_mapping_mismatch")
            calibration_reasons.append("calibration_mapping_mismatch")
        if (
            calibration_model.ordered_tone_ids != package.ordered_tone_ids
            or calibration_model.ordered_frequencies_hz != package.ordered_frequencies_hz
            or calibration_model.units != "dB"
            or calibration_model.input_quantity != spectrum.magnitude_quantity
            or calibration_model.output_quantity != model.magnitude_quantity
            or calibration_model.input_reference != spectrum.magnitude_reference
            or calibration_model.output_reference != model.magnitude_reference
            or calibration_model.normalization != model.normalization_method
        ):
            blocked.append("calibration_tone_or_magnitude_contract_mismatch")
            calibration_reasons.append("calibration_tone_or_magnitude_contract_mismatch")
        if package.calibration_model_semantic_sha256 != calibration_model.sha256:
            blocked.append("calibration_hash_mismatch")
            calibration_reasons.append("calibration_hash_mismatch")
        if calibration_model.calibration_lifecycle != "software_validation_only" or calibration_model.final_test_read:
            blocked.append("calibration_lifecycle_mismatch")
            calibration_reasons.append("calibration_lifecycle_mismatch")
        if calibration_model.held_out_pair_ids or set(calibration_model.training_pair_ids) & set(package.sealed_final_test_sample_ids):
            blocked.append("calibration_training_or_final_test_authority_mismatch")
            calibration_reasons.append("calibration_training_or_final_test_authority_mismatch")

    coverage = float(np.count_nonzero(spectrum.valid_mask) / len(package.ordered_tone_ids))
    minimum_coverage = float(package.qc_policy_snapshot["required_tone_coverage"])
    p8 = spectrum.quality_metrics
    sync_status = "valid" if p8.get("synchronization_method") == "preamble_cross_correlation" else "invalid"
    drift = p8.get("clock_drift", {})
    drift_status = str(drift.get("final_decision", drift.get("status", "unavailable")))
    clipping = p8.get("clipping", {})
    clipping_status = str(clipping.get("status", "unavailable"))
    p8_status = str(p8.get("p8_qc", {}).get("aggregate_status", measurement_qc.aggregate_status.value))
    qc_reasons: list[str] = []
    if sync_status != "valid": qc_reasons.append("synchronization_invalid")
    if drift_status in {"exclude_candidate", "invalid"}: qc_reasons.append("clock_drift_invalid")
    if clipping_status in {"exclude_candidate", "invalid"}: qc_reasons.append("clipping_invalid")
    if p8_status == "exclude_candidate": qc_reasons.append("p8_exclude_candidate")
    if drift_status == "warning": warnings.append("clock_drift_warning")
    if clipping_status == "warning": warnings.append("clipping_warning")
    if p8_status == "warning": warnings.append("p8_warning")
    if p8.get("period_samples") != package.period_samples:
        qc_reasons.append("period_samples_mismatch")
    if p8.get("stable_period_count") != package.stable_period_count:
        qc_reasons.append("stable_period_count_mismatch")
    discarded = p8.get("discarded_period_count")
    if discarded is not None and discarded != package.discard_initial_period_count:
        qc_reasons.append("discard_period_count_mismatch")
    if not measurement_qc.human_valid or measurement_qc.manual_review_reasons:
        qc_reasons.append("human_or_manual_review_gate")
    if spectrum.phase_status in {PhaseStatus.UNAVAILABLE, PhaseStatus.RELATIVE_UNRELIABLE}:
        warnings.append("phase_unavailable_or_relative_unreliable_phase_not_used")
    if coverage < minimum_coverage:
        qc_reasons.append("required_tone_coverage_below_policy")
    qc_status = (
        "invalid" if any(reason != "required_tone_coverage_below_policy" for reason in qc_reasons)
        else "unavailable" if qc_reasons
        else "warning" if warnings
        else "valid"
    )
    qc_audit = ReadoutQCAudit(
        qc_status, len(package.ordered_tone_ids), int(np.count_nonzero(spectrum.valid_mask)), coverage,
        spectrum.phase_status.value, False, sync_status, drift_status, clipping_status, p8_status,
        tuple(qc_reasons), tuple(dict.fromkeys(warnings)),
        {"period_samples": p8.get("period_samples"), "stable_period_count": p8.get("stable_period_count"),
         "source_qc_status": measurement_qc.aggregate_status.value},
    )
    empty_feature = ReadoutFeatureAudit(False, None, None, (), (), None, ())
    calibration_audit = ReadoutCalibrationAudit(
        requested_calibration, False,
        None if calibration_model is None else calibration_model.sha256,
        package.calibration_mapping_direction, tuple(calibration_reasons),
    )
    if blocked:
        prediction = _unavailable_prediction(
            package, model, input_reference, "blocked", "|".join(blocked), tuple(warnings)
        )
        return OfflineReadoutResult(
            READOUT_SCHEMA_VERSION, package.package_id, package.semantic_sha256,
            spectrum.meta.sample_id, "blocked", input_reference, qc_audit, empty_feature,
            calibration_audit, prediction, tuple(blocked), False, False, False, False,
        )
    try:
        processed = build_multisine_tone_feature_set(spectrum, measurement_qc, tone_set, matched_tone_config)
    except ToneFeatureConstructionError as exc:
        qc_reasons.append(str(exc))
        processed = None
    feature = None if processed is None else processed.feature_set
    if feature is None:
        reasons = tuple(qc_reasons or (() if processed is None else processed.failures) or ("p3c_feature_unavailable",))
        prediction = _unavailable_prediction(package, model, input_reference, "unavailable", "|".join(reasons), tuple(warnings))
        return OfflineReadoutResult(
            READOUT_SCHEMA_VERSION, package.package_id, package.semantic_sha256, spectrum.meta.sample_id,
            "unavailable", input_reference, qc_audit, empty_feature, calibration_audit, prediction,
            reasons, False, False, False, False,
        )
    feature_sha = feature_set_content_sha256(feature)
    feature_reasons: list[str] = []
    if feature.preprocessing_id != package.expected_preprocessing_id: feature_reasons.append("preprocessing_id_mismatch")
    if feature.feature_names != model.feature_names: feature_reasons.append("frozen_feature_order_mismatch")
    if feature.units != model.units: feature_reasons.append("frozen_feature_units_mismatch")
    feature_audit = ReadoutFeatureAudit(
        not feature_reasons and bool(np.all(feature.valid_mask)), feature_sha, feature.preprocessing_id,
        feature.feature_names, tuple(bool(item) for item in feature.valid_mask), feature.normalization_method,
        tuple(feature_reasons),
    )
    if qc_status in {"invalid", "unavailable"} or feature_reasons or not np.all(feature.valid_mask):
        reasons = tuple(qc_reasons + feature_reasons)
        if not np.all(feature.valid_mask) and "required_tone_coverage_below_policy" not in reasons:
            reasons += ("required_tone_coverage_below_policy",)
        prediction = _unavailable_prediction(
            package, model, input_reference, qc_status if qc_status != "valid" else "unavailable",
            "|".join(reasons), tuple(warnings), feature_sha,
        )
        return OfflineReadoutResult(
            READOUT_SCHEMA_VERSION, package.package_id, package.semantic_sha256, spectrum.meta.sample_id,
            "unavailable" if qc_status != "invalid" else "invalid", input_reference, qc_audit,
            feature_audit, calibration_audit, prediction, reasons, False, False, False, False,
        )
    values = np.asarray(feature.values, dtype=np.float64)
    if calibration_model is not None:
        values = np.asarray([
            apply_tone_calibration(np.asarray([value]), fit)[0]
            for value, fit in zip(values, calibration_model.tone_fits, strict=True)
        ])
        calibration_audit = ReadoutCalibrationAudit(True, True, calibration_model.sha256,
                                                     calibration_model.mapping_direction, ())
    ranked = predict_frozen_direction_model(model, values)[0]
    prediction = ReadoutPrediction(
        True, ranked.predicted_direction_deg, ranked.second_direction_deg, ranked.score,
        ranked.second_score, ranked.margin, ranked.score_kind, ranked.higher_is_better,
        "descriptive_margin_only", qc_status, None, model.model_id, model.schema_version,
        model.semantic_sha256, package.tone_set_id, package.tone_set_sha256,
        calibration_audit.applied, calibration_audit.model_semantic_sha256, feature_sha,
        input_reference.spectrum_json_sha256, tuple(dict.fromkeys(warnings)),
    )
    return OfflineReadoutResult(
        READOUT_SCHEMA_VERSION, package.package_id, package.semantic_sha256, spectrum.meta.sample_id,
        "completed_with_warnings" if warnings else "completed", input_reference, qc_audit,
        feature_audit, calibration_audit, prediction, (), False, False, False, False,
    )

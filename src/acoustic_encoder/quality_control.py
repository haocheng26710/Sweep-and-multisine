"""Typed P2 single-measurement quality control over canonical spectra."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

import numpy as np

from .research_gate import RunPurpose, enforce_research_gate, normalize_run_purpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMode,
    PhaseStatus,
    QCCheckStatus,
    QCStatus,
    SpectrumData,
)
from .version import SCHEMA_VERSION_QUARTET


QC_SCHEMA_VERSION = "1.0.0"
_SEVERITY = {
    QCCheckStatus.VALID: 0,
    QCCheckStatus.WARNING: 1,
    QCCheckStatus.EXCLUDE_CANDIDATE: 2,
}


class QCScope(str, Enum):
    METADATA = "metadata"
    MEASUREMENT = "measurement"
    SPECTRUM = "spectrum"
    TONE = "tone"


class QCSourceStage(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P8 = "P8"


class UnavailablePolicy(str, Enum):
    PRESERVE = "preserve"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class QCCheckResult:
    check_id: str
    scope: QCScope
    status: QCCheckStatus
    source_stage: QCSourceStage
    source_module: str
    measured_value: int | float | str | bool | None = None
    threshold: Mapping[str, Any] | None = None
    units: str | None = None
    reason: str | None = None
    required: bool = False
    frequency_hz: float | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.source_module.strip():
            raise ValueError("QC check_id and source_module must be non-empty")
        if self.status is not QCCheckStatus.VALID and not self.reason:
            raise ValueError("Non-valid QC checks require a reason")

    @property
    def available(self) -> bool:
        return self.status is not QCCheckStatus.UNAVAILABLE

    @property
    def severity_rank(self) -> int | None:
        return _SEVERITY.get(self.status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "scope": self.scope.value,
            "status": self.status.value,
            "severity_rank": self.severity_rank,
            "available": self.available,
            "source_stage": self.source_stage.value,
            "source_module": self.source_module,
            "measured_value": self.measured_value,
            "threshold": None if self.threshold is None else dict(self.threshold),
            "units": self.units,
            "reason": self.reason,
            "required": self.required,
            "frequency_hz": self.frequency_hz,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "QCCheckResult":
        return cls(
            check_id=str(payload["check_id"]),
            scope=QCScope(payload["scope"]),
            status=QCCheckStatus(payload["status"]),
            source_stage=QCSourceStage(payload["source_stage"]),
            source_module=str(payload["source_module"]),
            measured_value=payload.get("measured_value"),
            threshold=payload.get("threshold"),
            units=payload.get("units"),
            reason=payload.get("reason"),
            required=bool(payload.get("required", False)),
            frequency_hz=payload.get("frequency_hz"),
            details=payload.get("details", {}),
        )


@dataclass(frozen=True, slots=True)
class MeasurementQCResult:
    qc_schema_version: str
    sample_id: str
    measurement_mode: MeasurementMode
    data_origin: DataOrigin
    dataset_role: DatasetRole
    run_purpose: RunPurpose
    checks: tuple[QCCheckResult, ...]
    unavailable_required_policy: UnavailablePolicy
    manual_review_reasons: tuple[str, ...]
    human_valid: bool
    human_exclusion_reason: str | None
    scientifically_eligible: bool

    @property
    def aggregate_status(self) -> QCStatus:
        severity = 0
        for check in self.checks:
            if check.status is QCCheckStatus.UNAVAILABLE:
                if (
                    check.required
                    and self.unavailable_required_policy is UnavailablePolicy.WARNING
                ):
                    severity = max(severity, 1)
                continue
            severity = max(severity, int(check.severity_rank or 0))
        return (
            QCStatus.EXCLUDE_CANDIDATE
            if severity == 2
            else QCStatus.WARNING
            if severity == 1
            else QCStatus.VALID
        )

    @property
    def warning_reasons(self) -> tuple[str, ...]:
        return tuple(
            check.reason or check.check_id
            for check in self.checks
            if check.status is QCCheckStatus.WARNING
            or (
                check.status is QCCheckStatus.UNAVAILABLE
                and check.required
                and self.unavailable_required_policy is UnavailablePolicy.WARNING
            )
        )

    @property
    def exclude_candidate_reasons(self) -> tuple[str, ...]:
        return tuple(
            check.reason or check.check_id
            for check in self.checks
            if check.status is QCCheckStatus.EXCLUDE_CANDIDATE
        )

    @property
    def unavailable_checks(self) -> tuple[str, ...]:
        return tuple(
            check.check_id
            for check in self.checks
            if check.status is QCCheckStatus.UNAVAILABLE
        )

    @property
    def eligible_for_downstream(self) -> bool:
        return (
            self.human_valid
            and not self.manual_review_reasons
            and self.aggregate_status is not QCStatus.EXCLUDE_CANDIDATE
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "qc_schema_version": self.qc_schema_version,
            "sample_id": self.sample_id,
            "measurement_mode": self.measurement_mode.value,
            "data_origin": self.data_origin.value,
            "dataset_role": self.dataset_role.value,
            "run_purpose": self.run_purpose.value,
            "aggregate_status": self.aggregate_status.value,
            "checks": [check.to_dict() for check in self.checks],
            "warning_reasons": list(self.warning_reasons),
            "exclude_candidate_reasons": list(
                self.exclude_candidate_reasons
            ),
            "unavailable_checks": list(self.unavailable_checks),
            "unavailable_required_policy": (
                self.unavailable_required_policy.value
            ),
            "manual_review_reasons": list(self.manual_review_reasons),
            "human_valid": self.human_valid,
            "human_exclusion_reason": self.human_exclusion_reason,
            "scientifically_eligible": self.scientifically_eligible,
            "eligible_for_downstream": self.eligible_for_downstream,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MeasurementQCResult":
        result = cls(
            qc_schema_version=str(payload["qc_schema_version"]),
            sample_id=str(payload["sample_id"]),
            measurement_mode=MeasurementMode(payload["measurement_mode"]),
            data_origin=DataOrigin(payload["data_origin"]),
            dataset_role=DatasetRole(payload["dataset_role"]),
            run_purpose=RunPurpose(payload["run_purpose"]),
            checks=tuple(
                QCCheckResult.from_dict(item) for item in payload["checks"]
            ),
            unavailable_required_policy=UnavailablePolicy(
                payload["unavailable_required_policy"]
            ),
            manual_review_reasons=tuple(
                str(item) for item in payload.get("manual_review_reasons", ())
            ),
            human_valid=bool(payload["human_valid"]),
            human_exclusion_reason=payload.get("human_exclusion_reason"),
            scientifically_eligible=bool(payload["scientifically_eligible"]),
        )
        expected_derived = {
            "aggregate_status": result.aggregate_status.value,
            "warning_reasons": list(result.warning_reasons),
            "exclude_candidate_reasons": list(
                result.exclude_candidate_reasons
            ),
            "unavailable_checks": list(result.unavailable_checks),
            "eligible_for_downstream": result.eligible_for_downstream,
        }
        for name, expected in expected_derived.items():
            if name in payload and payload[name] != expected:
                raise ValueError(f"Serialized QC derived field mismatch: {name}")
        return result


def _check(
    check_id: str,
    status: QCCheckStatus,
    *,
    scope: QCScope = QCScope.SPECTRUM,
    measured_value: int | float | str | bool | None = None,
    threshold: Mapping[str, Any] | None = None,
    units: str | None = None,
    reason: str | None = None,
    required: bool = True,
    details: Mapping[str, Any] | None = None,
) -> QCCheckResult:
    return QCCheckResult(
        check_id=check_id,
        scope=scope,
        status=status,
        source_stage=QCSourceStage.P2,
        source_module="acoustic_encoder.quality_control",
        measured_value=measured_value,
        threshold=threshold,
        units=units,
        reason=reason,
        required=required,
        details={} if details is None else details,
    )


def _magnitude_status(values: np.ndarray, config: Mapping[str, Any]) -> QCCheckStatus:
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    dynamic_range = maximum - minimum
    warning = tuple(float(value) for value in config["warning_bounds"])
    exclude = tuple(float(value) for value in config["exclude_candidate_bounds"])
    if (
        minimum < exclude[0]
        or maximum > exclude[1]
        or dynamic_range >= float(config["exclude_candidate_dynamic_range_db"])
    ):
        return QCCheckStatus.EXCLUDE_CANDIDATE
    if (
        minimum < warning[0]
        or maximum > warning[1]
        or dynamic_range >= float(config["warning_dynamic_range_db"])
    ):
        return QCCheckStatus.WARNING
    return QCCheckStatus.VALID


def _rew_quality_checks(spectrum: SpectrumData) -> tuple[QCCheckResult, ...]:
    checks: list[QCCheckResult] = []
    for name in (
        "headroom",
        "noise_floor",
        "raw_waveform",
        "impulse_response",
        "window",
    ):
        value = spectrum.quality_metrics.get(name)
        if value == QCCheckStatus.UNAVAILABLE.value:
            checks.append(
                QCCheckResult(
                    check_id=f"p1.rew.{name}",
                    scope=QCScope.MEASUREMENT,
                    status=QCCheckStatus.UNAVAILABLE,
                    source_stage=QCSourceStage.P1,
                    source_module="acoustic_encoder.io_rew",
                    reason=f"rew_{name}_unavailable",
                    required=False,
                    details={"reported_value": value},
                )
            )
    return tuple(checks)


def _p8_check(
    check_id: str,
    status: str | QCCheckStatus,
    *,
    scope: QCScope = QCScope.MEASUREMENT,
    measured_value: int | float | str | bool | None = None,
    threshold: Mapping[str, Any] | None = None,
    units: str | None = None,
    reason: str | None = None,
    required: bool,
    frequency_hz: float | None = None,
    details: Mapping[str, Any] | None = None,
) -> QCCheckResult:
    normalized = QCCheckStatus(status)
    if normalized is not QCCheckStatus.VALID and reason is None:
        reason = f"{check_id.replace('.', '_')}_{normalized.value}"
    return QCCheckResult(
        check_id=check_id,
        scope=scope,
        status=normalized,
        source_stage=QCSourceStage.P8,
        source_module="acoustic_encoder.multisine_qc",
        measured_value=measured_value,
        threshold=threshold,
        units=units,
        reason=reason,
        required=required,
        frequency_hz=frequency_hz,
        details={} if details is None else details,
    )


def _multisine_quality_checks(
    spectrum: SpectrumData,
    mode_config: Mapping[str, Any],
) -> tuple[QCCheckResult, ...]:
    """Translate P8 evidence into P2 checks without recomputing audio metrics."""
    metrics = spectrum.quality_metrics
    required_ids = set(mode_config.get("required_upstream_checks", ()))
    checks: list[QCCheckResult] = []

    p8_qc = metrics.get("p8_qc")
    if isinstance(p8_qc, Mapping):
        checks.append(
            _p8_check(
                "p8.aggregate",
                str(p8_qc["status"]),
                measured_value=str(p8_qc["status"]),
                required="p8.aggregate" in required_ids,
                details={
                    "qc_schema_version": p8_qc.get("qc_schema_version"),
                    "unavailable_items": list(p8_qc.get("unavailable_items", ())),
                    "valid_tone_count": p8_qc.get("valid_tone_count"),
                    "warning_tone_count": p8_qc.get("warning_tone_count"),
                    "exclude_candidate_tone_count": p8_qc.get(
                        "exclude_candidate_tone_count"
                    ),
                },
            )
        )
    else:
        checks.append(
            _p8_check(
                "p8.aggregate",
                QCCheckStatus.UNAVAILABLE,
                reason="p8_aggregate_unavailable",
                required="p8.aggregate" in required_ids,
            )
        )

    clipping = metrics.get("clipping")
    if isinstance(clipping, Mapping):
        checks.append(
            _p8_check(
                "p8.clipping",
                str(clipping["status"]),
                measured_value=float(clipping["fraction"]),
                threshold={
                    "warning_fraction": clipping.get("warning_fraction"),
                    "exclude_candidate_fraction": clipping.get(
                        "exclude_candidate_fraction"
                    ),
                },
                units="fraction",
                required="p8.clipping" in required_ids,
                details=dict(clipping),
            )
        )
    else:
        checks.append(
            _p8_check(
                "p8.clipping",
                QCCheckStatus.UNAVAILABLE,
                reason="p8_clipping_unavailable",
                required="p8.clipping" in required_ids,
            )
        )

    drift = metrics.get("clock_drift")
    if isinstance(drift, Mapping):
        thresholds = drift.get("thresholds")
        if not isinstance(thresholds, Mapping):
            thresholds = {
                "warning_ppm": drift.get("warning_ppm"),
                "exclude_candidate_ppm": drift.get("exclude_candidate_ppm"),
            }
        post = drift.get("post_correction") or drift.get("residual")
        pre = drift.get("pre_correction")
        value_source = post if isinstance(post, Mapping) else pre
        value = (
            value_source.get("signed_drift_ppm")
            if isinstance(value_source, Mapping)
            else None
        )
        checks.append(
            _p8_check(
                "p8.clock_drift",
                str(drift["final_decision"]),
                measured_value=value,
                threshold=dict(thresholds),
                units="ppm",
                required="p8.clock_drift" in required_ids,
                details=dict(drift),
            )
        )
    else:
        checks.append(
            _p8_check(
                "p8.clock_drift",
                QCCheckStatus.UNAVAILABLE,
                reason="p8_clock_drift_unavailable",
                required="p8.clock_drift" in required_ids,
            )
        )

    non_excited = metrics.get("non_excited_energy")
    if isinstance(non_excited, Mapping):
        checks.append(
            _p8_check(
                "p8.non_excited_energy",
                str(non_excited["status"]),
                measured_value=non_excited.get("energy_ratio"),
                units="ratio",
                required="p8.non_excited_energy" in required_ids,
                details=dict(non_excited),
            )
        )
    else:
        checks.append(
            _p8_check(
                "p8.non_excited_energy",
                QCCheckStatus.UNAVAILABLE,
                reason="p8_non_excited_energy_unavailable",
                required="p8.non_excited_energy" in required_ids,
            )
        )

    tone_quality = metrics.get("tone_quality")
    if not isinstance(tone_quality, list):
        tone_quality = []
    for record in tone_quality:
        if not isinstance(record, Mapping):
            continue
        frequency = float(record["frequency_hz"])
        common_details = {"qc_reasons": list(record.get("qc_reasons", ()))}
        checks.extend(
            (
                _p8_check(
                    "p8.tone.snr",
                    str(record["snr_status"]),
                    scope=QCScope.TONE,
                    measured_value=record.get("snr_db"),
                    units="dB",
                    required="p8.tone.snr" in required_ids,
                    frequency_hz=frequency,
                    details={
                        **common_details,
                        "method": record.get("snr_method"),
                        "noise_bin_count": record.get("snr_noise_bin_count"),
                    },
                ),
                _p8_check(
                    "p8.tone.leakage",
                    str(record["leakage_status"]),
                    scope=QCScope.TONE,
                    measured_value=record.get("leakage_ratio"),
                    units="ratio",
                    required="p8.tone.leakage" in required_ids,
                    frequency_hz=frequency,
                    details={
                        **common_details,
                        "method": record.get("leakage_method"),
                        "bin_count": record.get("leakage_bin_count"),
                        "guard_bins": record.get("leakage_guard_bins"),
                        "radius_bins": record.get("leakage_radius_bins"),
                    },
                ),
                _p8_check(
                    "p8.tone.period_variance",
                    str(record["period_variance_status"]),
                    scope=QCScope.TONE,
                    measured_value=record.get("period_variance"),
                    units="ratio",
                    required="p8.tone.period_variance" in required_ids,
                    frequency_hz=frequency,
                    details={
                        **common_details,
                        "method": record.get("period_variance_method"),
                        "period_count": record.get("period_count"),
                        "magnitude_variance_db2": record.get(
                            "magnitude_variance_db2"
                        ),
                        "phase_circular_variance": record.get(
                            "phase_circular_variance"
                        ),
                    },
                ),
                _p8_check(
                    "p8.tone.missing_tone",
                    (
                        QCCheckStatus.UNAVAILABLE
                        if record.get("missing_tone") is None
                        else QCCheckStatus.EXCLUDE_CANDIDATE
                        if bool(record.get("missing_tone"))
                        else QCCheckStatus.VALID
                    ),
                    scope=QCScope.TONE,
                    measured_value=record.get("missing_tone"),
                    reason=(
                        "missing_tone_detection_unavailable"
                        if record.get("missing_tone") is None
                        else "missing_tone"
                        if bool(record.get("missing_tone"))
                        else None
                    ),
                    required="p8.tone.missing_tone" in required_ids,
                    frequency_hz=frequency,
                    details={
                        **common_details,
                        "valid_tone": record.get("valid_tone"),
                        "tone_qc_status": record.get("qc_status"),
                    },
                ),
            )
        )
    return tuple(checks)


def evaluate_measurement_quality(
    spectrum: SpectrumData,
    config: Mapping[str, Any],
    *,
    run_purpose: str | RunPurpose,
    upstream_checks: Iterable[QCCheckResult] = (),
) -> MeasurementQCResult:
    """Evaluate shared P2 checks without reading or changing the raw input."""
    purpose = normalize_run_purpose(run_purpose)
    enforce_research_gate(purpose, [spectrum.meta])
    mode_config = config["modes"][spectrum.meta.measurement_mode.value]
    valid_frequency = spectrum.frequency_hz[spectrum.valid_mask]
    valid_magnitude = spectrum.magnitude_db[spectrum.valid_mask]
    minimum_points = int(mode_config["minimum_valid_points"])
    required_low, required_high = (
        float(value) for value in mode_config["required_frequency_range_hz"]
    )
    point_count = int(valid_frequency.size)
    point_status = (
        QCCheckStatus.VALID
        if point_count >= minimum_points
        else QCCheckStatus.EXCLUDE_CANDIDATE
    )
    coverage_ok = bool(
        point_count
        and valid_frequency[0] <= required_low
        and valid_frequency[-1] >= required_high
    )
    magnitude_status = (
        _magnitude_status(valid_magnitude, mode_config["magnitude_db"])
        if point_count
        else QCCheckStatus.UNAVAILABLE
    )
    has_phase = spectrum.phase_rad is not None
    phase_consistent = (
        (spectrum.phase_status is PhaseStatus.UNAVAILABLE and not has_phase)
        or (spectrum.phase_status is not PhaseStatus.UNAVAILABLE and has_phase)
    )
    phase_inconsistency = QCCheckStatus(
        mode_config["phase_inconsistency_status"]
    )
    phase_policy = str(mode_config["phase_policy"])
    if has_phase:
        phase_availability_status = QCCheckStatus.VALID
        phase_required = phase_policy == "required_warning"
    elif phase_policy == "required_warning":
        phase_availability_status = QCCheckStatus.WARNING
        phase_required = True
    else:
        phase_availability_status = QCCheckStatus.UNAVAILABLE
        phase_required = False
    actual_versions = {
        "pipeline_version": spectrum.meta.pipeline_version,
        "config_schema_version": spectrum.meta.config_schema_version,
        "measurement_schema_version": spectrum.meta.measurement_schema_version,
        "feature_schema_version": spectrum.meta.feature_schema_version,
    }
    versions_compatible = actual_versions == SCHEMA_VERSION_QUARTET
    mode_fields = (
        {
            "stimulus_id": spectrum.meta.stimulus_id,
            "stimulus_hash": spectrum.meta.stimulus_hash,
            "tone_set_id": spectrum.meta.tone_set_id,
            "sidecar_path": spectrum.meta.sidecar_path,
            "audio_channel": spectrum.meta.audio_channel,
        }
        if spectrum.meta.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE
        else {"source_format": spectrum.meta.source_format.value}
    )
    checks = (
        QCCheckResult(
            check_id="p1.adapter.aggregate",
            scope=QCScope.MEASUREMENT,
            status=QCCheckStatus(spectrum.meta.qc_status.value),
            source_stage=QCSourceStage.P1,
            source_module="acoustic_encoder.p1_adapters",
            measured_value=spectrum.meta.qc_status.value,
            reason=(
                None
                if spectrum.meta.qc_status is QCStatus.VALID
                else f"adapter_reported_{spectrum.meta.qc_status.value}"
            ),
        ),
        _check(
            "p2.metadata.required_fields",
            QCCheckStatus.VALID,
            scope=QCScope.METADATA,
            measured_value=True,
            details={
                "validated_by": "MeasurementMeta.__post_init__",
                "sample_id": spectrum.meta.sample_id,
                "measurement_mode": spectrum.meta.measurement_mode.value,
            },
        ),
        _check(
            "p2.metadata.mode_fields",
            QCCheckStatus.VALID,
            scope=QCScope.METADATA,
            measured_value=True,
            details={
                "validated_by": "MeasurementMeta.__post_init__",
                "fields": mode_fields,
            },
        ),
        _check(
            "p2.provenance.integrity",
            QCCheckStatus.VALID,
            scope=QCScope.METADATA,
            measured_value=spectrum.meta.data_origin.value,
            details={
                "source_path": spectrum.meta.source_path,
                "source_sha256": spectrum.meta.source_sha256,
                "provenance_uri": spectrum.meta.provenance_uri,
                "dataset_role": spectrum.meta.dataset_role.value,
                "scientifically_eligible": (
                    spectrum.meta.eligible_for_scientific_analysis
                ),
                "research_gate_run_purpose": purpose.value,
                "validated_by": [
                    "MeasurementMeta.__post_init__",
                    "research_gate.enforce_research_gate",
                ],
            },
        ),
        _check(
            "p2.schema.compatibility",
            (
                QCCheckStatus.VALID
                if versions_compatible
                else QCCheckStatus.EXCLUDE_CANDIDATE
            ),
            scope=QCScope.METADATA,
            measured_value=versions_compatible,
            threshold=dict(SCHEMA_VERSION_QUARTET),
            reason=(
                None
                if versions_compatible
                else "unsupported_schema_or_pipeline_version"
            ),
            details={"actual": actual_versions},
        ),
        _check(
            "p2.spectrum.schema_invariants",
            QCCheckStatus.VALID,
            measured_value=True,
            details={
                "guarantees": [
                    "one_dimensional_arrays",
                    "nonempty_finite_strictly_increasing_frequency",
                    "matching_array_lengths",
                    "finite_valid_magnitude",
                ]
            },
        ),
        _check(
            "p2.spectrum.valid_point_count",
            point_status,
            measured_value=point_count,
            threshold={"minimum": minimum_points},
            units="points",
            reason=(None if point_status is QCCheckStatus.VALID else "insufficient_valid_points"),
        ),
        _check(
            "p2.spectrum.frequency_coverage",
            QCCheckStatus.VALID if coverage_ok else QCCheckStatus.WARNING,
            measured_value=(
                f"{valid_frequency[0]:g}..{valid_frequency[-1]:g}"
                if point_count
                else None
            ),
            threshold={"required_range_hz": [required_low, required_high]},
            units="Hz",
            reason=None if coverage_ok else "required_frequency_range_not_covered",
        ),
        _check(
            "p2.spectrum.magnitude_bounds",
            magnitude_status,
            measured_value=(
                float(np.max(valid_magnitude) - np.min(valid_magnitude))
                if point_count
                else None
            ),
            threshold=dict(mode_config["magnitude_db"]),
            units="dB",
            reason=(
                None
                if magnitude_status is QCCheckStatus.VALID
                else "magnitude_outside_configured_bounds"
                if magnitude_status is not QCCheckStatus.UNAVAILABLE
                else "no_valid_magnitude_points"
            ),
            details=(
                {
                    "minimum_db": float(np.min(valid_magnitude)),
                    "maximum_db": float(np.max(valid_magnitude)),
                }
                if point_count
                else {}
            ),
        ),
        _check(
            "p2.phase.consistency",
            QCCheckStatus.VALID if phase_consistent else phase_inconsistency,
            measured_value=spectrum.phase_status.value,
            reason=None if phase_consistent else "phase_status_and_phase_array_disagree",
            details={"has_phase_rad": has_phase},
        ),
        _check(
            "p2.phase.availability",
            phase_availability_status,
            measured_value=has_phase,
            threshold={"phase_policy": phase_policy},
            reason=(
                None
                if phase_availability_status is QCCheckStatus.VALID
                else "phase_not_available"
            ),
            required=phase_required,
            details={"phase_status": spectrum.phase_status.value},
        ),
    )
    if has_phase:
        finite_phase_count = int(
            np.count_nonzero(np.isfinite(spectrum.phase_rad[spectrum.valid_mask]))
        )
        phase_finite = finite_phase_count == point_count
        checks += (
            _check(
                "p2.phase.finite",
                QCCheckStatus.VALID if phase_finite else phase_inconsistency,
                measured_value=finite_phase_count,
                threshold={"required_finite_valid_points": point_count},
                units="points",
                reason=None if phase_finite else "nonfinite_phase_at_valid_points",
            ),
        )
    if spectrum.meta.measurement_mode is MeasurementMode.REW_SWEEP:
        checks += _rew_quality_checks(spectrum)
    elif spectrum.meta.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE:
        checks += _multisine_quality_checks(spectrum, mode_config)
    checks += tuple(upstream_checks)
    return MeasurementQCResult(
        qc_schema_version=QC_SCHEMA_VERSION,
        sample_id=spectrum.meta.sample_id,
        measurement_mode=spectrum.meta.measurement_mode,
        data_origin=spectrum.meta.data_origin,
        dataset_role=spectrum.meta.dataset_role,
        run_purpose=purpose,
        checks=checks,
        unavailable_required_policy=UnavailablePolicy(
            mode_config["unavailable_required_check_policy"]
        ),
        manual_review_reasons=spectrum.meta.manual_review_reasons,
        human_valid=spectrum.meta.valid,
        human_exclusion_reason=spectrum.meta.exclusion_reason,
        scientifically_eligible=spectrum.meta.eligible_for_scientific_analysis,
    )

"""Canonical, versioned data objects for every measurement mode.

DataFrames and CSV files are deliberately export views. These dataclasses are
the authoritative in-memory representation shared by P1-P9.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from .version import FEATURE_SCHEMA_VERSION, MEASUREMENT_SCHEMA_VERSION

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


class MeasurementMode(str, Enum):
    REW_SWEEP = "rew_sweep"
    SCHROEDER_MULTISINE = "schroeder_multisine"


class Representation(str, Enum):
    DENSE_SPECTRUM = "dense_spectrum"
    SPARSE_TONES = "sparse_tones"


class PhaseStatus(str, Enum):
    UNAVAILABLE = "unavailable"
    RELATIVE_UNRELIABLE = "relative_unreliable"
    DRIFT_CORRECTED = "drift_corrected"
    COMMON_CLOCK = "common_clock"


class QCStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    EXCLUDE_CANDIDATE = "exclude_candidate"


class QCCheckStatus(str, Enum):
    VALID = "valid"
    WARNING = "warning"
    EXCLUDE_CANDIDATE = "exclude_candidate"
    UNAVAILABLE = "unavailable"


class FeatureKind(str, Enum):
    DENSE_RAW_SPL = "dense_raw_spl"
    DENSE_DEMEANED_DB = "dense_demeaned_db"
    DENSE_ZSCORE = "dense_zscore"
    TONE_PROJECTION_FROM_SWEEP = "tone_projection_from_sweep"
    TONE_MEASUREMENT_FROM_MULTISINE = "tone_measurement_from_multisine"
    HR_BAND_ENERGY = "hr_band_energy"
    HR_ENERGY_FRACTION = "hr_energy_fraction"


class SourceFormat(str, Enum):
    REW_TXT = "rew_txt"
    MULTISINE_WAV = "multisine_wav"
    MOCK_DENSE = "mock_dense"
    MOCK_AUDIO = "mock_audio"


class DataOrigin(str, Enum):
    EXTERNAL_REFERENCE = "external_reference"
    SIMULATED = "simulated"
    REAL_EXPERIMENT = "real_experiment"


class DatasetRole(str, Enum):
    PARSER_FIXTURE = "parser_fixture"
    SOFTWARE_VALIDATION = "software_validation"
    RESEARCH_INPUT = "research_input"
    RESEARCH_ANALYSIS = "research_analysis"


def normalize_measurement_mode(value: str | MeasurementMode) -> MeasurementMode:
    """Normalize the sole accepted UI alias without leaking it into artifacts."""
    if isinstance(value, MeasurementMode):
        return value
    if value == "schroeder_chirp":
        return MeasurementMode.SCHROEDER_MULTISINE
    return MeasurementMode(value)


def _readonly_1d(value: Any, dtype: Any, name: str) -> NDArray[Any]:
    array = np.asarray(value, dtype=dtype)
    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional array")
    array = np.array(array, dtype=dtype, copy=True)
    array.setflags(write=False)
    return array


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class MeasurementMeta:
    sample_id: str
    pipeline_version: str
    config_schema_version: str
    measurement_schema_version: str
    feature_schema_version: str
    device_version: str | None
    configuration: str | None
    angle_deg: float | None
    session_id: str | None
    repeat_type: str | None
    repeat_id: str | None
    experiment_step: str | None
    measurement_mode: MeasurementMode
    source_format: SourceFormat
    source_path: str
    data_origin: DataOrigin
    dataset_role: DatasetRole
    source_sha256: str
    provenance_uri: str
    eligible_for_scientific_analysis: bool
    reposition_round_id: str | None = None
    assembly_id: str | None = None
    acquisition_block_id: str | None = None
    stimulus_id: str | None = None
    stimulus_hash: str | None = None
    tone_set_id: str | None = None
    sidecar_path: str | None = None
    date_time: datetime | None = None
    audio_channel: int | None = None
    valid: bool = True
    qc_status: QCStatus = QCStatus.VALID
    exclusion_reason: str | None = None
    manual_review_reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        required_text = {
            "sample_id": self.sample_id,
            "pipeline_version": self.pipeline_version,
            "config_schema_version": self.config_schema_version,
            "measurement_schema_version": self.measurement_schema_version,
            "feature_schema_version": self.feature_schema_version,
            "source_path": self.source_path,
            "provenance_uri": self.provenance_uri,
        }
        missing = [name for name, value in required_text.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"MeasurementMeta required fields are empty: {missing}")
        experiment_identity = {
            "device_version": self.device_version,
            "configuration": self.configuration,
            "angle_deg": self.angle_deg,
            "session_id": self.session_id,
            "repeat_type": self.repeat_type,
            "repeat_id": self.repeat_id,
            "reposition_round_id": self.reposition_round_id,
            "assembly_id": self.assembly_id,
            "acquisition_block_id": self.acquisition_block_id,
            "experiment_step": self.experiment_step,
        }
        if self.data_origin is DataOrigin.EXTERNAL_REFERENCE:
            present = [name for name, value in experiment_identity.items() if value is not None]
            if present:
                raise ValueError(
                    "external_reference must not contain experiment identity fields: "
                    f"{present}"
                )
        else:
            required_experiment_text = {
                name: value
                for name, value in experiment_identity.items()
                if name
                in {
                    "device_version",
                    "configuration",
                    "session_id",
                    "repeat_type",
                    "repeat_id",
                    "experiment_step",
                }
            }
            missing_experiment = [
                name
                for name, value in required_experiment_text.items()
                if value is None or not str(value).strip()
            ]
            if missing_experiment:
                raise ValueError(
                    "MeasurementMeta experiment fields are required: "
                    f"{missing_experiment}"
                )
            if self.angle_deg is None or not np.isfinite(self.angle_deg):
                raise ValueError("angle_deg must be finite and in [0, 360)")
            if not 0.0 <= self.angle_deg < 360.0:
                raise ValueError("angle_deg must be finite and in [0, 360)")
        if self.date_time is not None and self.date_time.tzinfo is None:
            raise ValueError("date_time must include a timezone")
        if not self.valid and not self.exclusion_reason:
            raise ValueError("exclusion_reason is required when valid is false")
        if (
            len(self.source_sha256) != 64
            or self.source_sha256 != self.source_sha256.lower()
            or any(character not in "0123456789abcdef" for character in self.source_sha256)
        ):
            raise ValueError("source_sha256 must be a lowercase 64-character SHA-256 digest")
        expected_roles = {
            DataOrigin.EXTERNAL_REFERENCE: {DatasetRole.PARSER_FIXTURE},
            DataOrigin.SIMULATED: {DatasetRole.SOFTWARE_VALIDATION},
            DataOrigin.REAL_EXPERIMENT: {
                DatasetRole.RESEARCH_INPUT,
                DatasetRole.RESEARCH_ANALYSIS,
            },
        }
        if self.dataset_role not in expected_roles.get(self.data_origin, set()):
            raise ValueError(
                f"dataset_role {self.dataset_role!r} is incompatible with "
                f"data_origin {self.data_origin!r}"
            )
        mode_formats = {
            MeasurementMode.REW_SWEEP: {SourceFormat.REW_TXT, SourceFormat.MOCK_DENSE},
            MeasurementMode.SCHROEDER_MULTISINE: {
                SourceFormat.MULTISINE_WAV,
                SourceFormat.MOCK_AUDIO,
            },
        }
        if self.source_format not in mode_formats[self.measurement_mode]:
            raise ValueError(
                f"source_format {self.source_format.value!r} is incompatible with "
                f"measurement_mode {self.measurement_mode.value!r}"
            )
        allowed_formats = {
            DataOrigin.EXTERNAL_REFERENCE: {SourceFormat.REW_TXT},
            DataOrigin.SIMULATED: {SourceFormat.MOCK_DENSE, SourceFormat.MOCK_AUDIO},
            DataOrigin.REAL_EXPERIMENT: {SourceFormat.REW_TXT, SourceFormat.MULTISINE_WAV},
        }
        if self.source_format not in allowed_formats[self.data_origin]:
            raise ValueError(
                f"source_format {self.source_format.value!r} is incompatible with "
                f"data_origin {self.data_origin.value!r}"
            )
        if (
            self.eligible_for_scientific_analysis
            and self.data_origin is not DataOrigin.REAL_EXPERIMENT
        ):
            raise ValueError(
                "eligible_for_scientific_analysis requires data_origin='real_experiment'"
            )
        if self.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE:
            required_multisine = {
                "stimulus_id": self.stimulus_id,
                "stimulus_hash": self.stimulus_hash,
                "tone_set_id": self.tone_set_id,
                "sidecar_path": self.sidecar_path,
                "audio_channel": self.audio_channel,
            }
            missing_ms = [name for name, value in required_multisine.items() if value is None]
            if missing_ms:
                raise ValueError(f"multisine metadata fields are required: {missing_ms}")

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MeasurementMeta":
        values = dict(payload)
        values["measurement_mode"] = normalize_measurement_mode(values["measurement_mode"])
        values["source_format"] = SourceFormat(values["source_format"])
        values["data_origin"] = DataOrigin(values["data_origin"])
        values["dataset_role"] = DatasetRole(values["dataset_role"])
        values["qc_status"] = QCStatus(values.get("qc_status", QCStatus.VALID.value))
        if values.get("date_time"):
            values["date_time"] = datetime.fromisoformat(values["date_time"])
        values["manual_review_reasons"] = tuple(values.get("manual_review_reasons", ()))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class SpectrumData:
    frequency_hz: FloatArray
    magnitude_db: FloatArray
    valid_mask: BoolArray
    representation: Representation
    phase_status: PhaseStatus
    quality_metrics: Mapping[str, Any]
    meta: MeasurementMeta
    magnitude_linear: FloatArray | None = None
    magnitude_quantity: str = "uncalibrated_level"
    magnitude_reference: str | None = None
    phase_rad: FloatArray | None = None

    def __post_init__(self) -> None:
        frequency = _readonly_1d(self.frequency_hz, np.float64, "frequency_hz")
        magnitude = _readonly_1d(self.magnitude_db, np.float64, "magnitude_db")
        mask = _readonly_1d(self.valid_mask, np.bool_, "valid_mask")
        if not (frequency.size == magnitude.size == mask.size):
            raise ValueError("frequency_hz, magnitude_db, and valid_mask lengths must match")
        if frequency.size == 0 or not np.all(np.isfinite(frequency)):
            raise ValueError("frequency_hz must be non-empty and finite")
        if not np.all(np.diff(frequency) > 0):
            raise ValueError("frequency_hz must be strictly increasing and unique")
        if np.any(~np.isfinite(magnitude[mask])):
            raise ValueError("valid magnitude_db entries must be finite")
        object.__setattr__(self, "frequency_hz", frequency)
        object.__setattr__(self, "magnitude_db", magnitude)
        object.__setattr__(self, "valid_mask", mask)
        for name in ("magnitude_linear", "phase_rad"):
            value = getattr(self, name)
            if value is not None:
                array = _readonly_1d(value, np.float64, name)
                if array.size != frequency.size:
                    raise ValueError(f"{name} length must match frequency_hz")
                object.__setattr__(self, name, array)
        if self.representation is Representation.SPARSE_TONES and not self.meta.tone_set_id:
            raise ValueError("sparse_tones requires meta.tone_set_id")


@dataclass(frozen=True, slots=True)
class FeatureQualityRecord:
    feature_name: str
    availability: str
    valid: bool
    reason_codes: tuple[str, ...]
    source_module: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.feature_name.strip() or not self.source_module.strip():
            raise ValueError("feature quality name and source_module are required")
        if self.availability not in {"available", "missing", "invalid", "unavailable"}:
            raise ValueError("unsupported feature quality availability")
        if self.valid != (self.availability == "available"):
            raise ValueError("feature quality valid must match availability")
        try:
            json.dumps(_jsonable(self.details), sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError("feature quality details must be JSON serializable") from exc

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FeatureQualityRecord":
        return cls(
            feature_name=str(payload["feature_name"]),
            availability=str(payload["availability"]),
            valid=bool(payload["valid"]),
            reason_codes=tuple(str(item) for item in payload.get("reason_codes", ())),
            source_module=str(payload["source_module"]),
            details=dict(payload.get("details", {})),
        )


@dataclass(frozen=True, slots=True)
class FeatureDerivation:
    schema_version: str
    stage_id: str
    scope_id: str
    result_id: str
    source_feature_content_sha256: str
    calibration_id: str
    calibration_json_sha256: str
    calibration_manifest_sha256: str
    p2b_result_sha256: str
    scientifically_eligible: bool
    deployment_allowed: bool
    absolute_energy_comparable: bool

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0" or not self.stage_id or not self.scope_id:
            raise ValueError("feature derivation requires schema 1.0.0, stage, and scope")
        prefixed = {
            "result_id": self.result_id,
            "source_feature_content_sha256": self.source_feature_content_sha256,
            "calibration_id": self.calibration_id,
            "p2b_result_sha256": self.p2b_result_sha256,
        }
        bare = {
            "calibration_json_sha256": self.calibration_json_sha256,
            "calibration_manifest_sha256": self.calibration_manifest_sha256,
        }
        for name, value in prefixed.items():
            if not value.startswith("sha256:"):
                raise ValueError(f"{name} must start with sha256:")
            _validate_lower_digest(value.removeprefix("sha256:"), name)
        for name, value in bare.items():
            _validate_lower_digest(value, name)
        if self.deployment_allowed and not self.scientifically_eligible:
            raise ValueError("deployment cannot exceed scientific eligibility")

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FeatureDerivation":
        return cls(**{name: payload[name] for name in cls.__dataclass_fields__})


def _validate_lower_digest(value: str, name: str) -> None:
    if (
        len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must contain a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class FeatureSet:
    sample_id: str
    feature_schema_version: str
    feature_kind: FeatureKind
    feature_names: tuple[str, ...]
    values: FloatArray
    valid_mask: BoolArray
    units: tuple[str, ...]
    source_measurement_mode: MeasurementMode
    source_representation: Representation
    preprocessing_id: str
    meta: MeasurementMeta
    tone_set_id: str | None = None
    tone_set_sha256: str | None = None
    tone_schema_id: str | None = None
    normalization_method: str | None = None
    source_magnitude_quantity: str | None = None
    source_magnitude_reference: str | None = None
    source_phase_status: PhaseStatus | None = None
    reliability_weights: FloatArray | None = None
    reliability_weight_source: str | None = None
    fit_scope_id: str | None = None
    calibration_id: str | None = None
    source_qc_status: QCStatus | None = None
    source_qc_sha256: str | None = None
    source_qc_warning_reasons: tuple[str, ...] = field(default_factory=tuple)
    source_qc_exclude_candidate_reasons: tuple[str, ...] = field(
        default_factory=tuple
    )
    source_qc_unavailable_checks: tuple[str, ...] = field(default_factory=tuple)
    source_qc_eligible_for_downstream: bool | None = None
    feature_quality: tuple[FeatureQualityRecord, ...] = field(default_factory=tuple)
    derivation: FeatureDerivation | None = None

    def __post_init__(self) -> None:
        values = _readonly_1d(self.values, np.float64, "values")
        mask = _readonly_1d(self.valid_mask, np.bool_, "valid_mask")
        size = values.size
        if not (size == len(self.feature_names) == mask.size == len(self.units)):
            raise ValueError("FeatureSet values, names, mask, and units lengths must match")
        if self.sample_id != self.meta.sample_id:
            raise ValueError("FeatureSet sample_id must equal meta.sample_id")
        if np.any(~np.isfinite(values[mask])):
            raise ValueError("valid feature values must be finite")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "valid_mask", mask)
        if self.feature_quality:
            if len(self.feature_quality) != size:
                raise ValueError("feature_quality length must match FeatureSet")
            if tuple(item.feature_name for item in self.feature_quality) != self.feature_names:
                raise ValueError("feature_quality order must match feature_names")
        if self.reliability_weights is not None:
            weights = _readonly_1d(self.reliability_weights, np.float64, "reliability_weights")
            if (
                weights.size != size
                or np.any(~np.isfinite(weights))
                or np.any((weights < 0) | (weights > 1))
            ):
                raise ValueError("reliability_weights must match values and lie in [0, 1]")
            object.__setattr__(self, "reliability_weights", weights)
        tone_kinds = {
            FeatureKind.TONE_PROJECTION_FROM_SWEEP,
            FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        }
        if self.feature_kind in tone_kinds:
            required_tone_fields = {
                "tone_set_id": self.tone_set_id,
                "tone_set_sha256": self.tone_set_sha256,
                "tone_schema_id": self.tone_schema_id,
                "normalization_method": self.normalization_method,
                "source_magnitude_quantity": self.source_magnitude_quantity,
                "source_phase_status": self.source_phase_status,
            }
            missing = [name for name, value in required_tone_fields.items() if value is None]
            if missing:
                raise ValueError(f"tone FeatureSet requires fields: {missing}")
            for name, value in {
                "tone_set_sha256": self.tone_set_sha256,
                "tone_schema_id": self.tone_schema_id,
            }.items():
                assert value is not None
                digest = value.removeprefix("sha256:")
                if (
                    len(digest) != 64
                    or digest != digest.lower()
                    or any(character not in "0123456789abcdef" for character in digest)
                ):
                    raise ValueError(f"{name} must contain a lowercase SHA-256 digest")
            if self.reliability_weights is None and self.reliability_weight_source is not None:
                raise ValueError(
                    "reliability_weight_source requires reliability_weights"
                )
            if self.reliability_weights is not None and not self.reliability_weight_source:
                raise ValueError(
                    "tone reliability_weights require reliability_weight_source"
                )
        if self.source_qc_sha256 is not None and (
            not self.source_qc_sha256.startswith("sha256:")
            or len(self.source_qc_sha256) != len("sha256:") + 64
            or any(
                character not in "0123456789abcdef"
                for character in self.source_qc_sha256.removeprefix("sha256:")
            )
        ):
            raise ValueError("source_qc_sha256 must be sha256:<lowercase digest>")


def _artifact_paths(base_path: str | Path) -> tuple[Path, Path]:
    base = Path(base_path)
    if base.suffix:
        base = base.with_suffix("")
    return base.with_suffix(".npz"), base.with_suffix(".json")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def artifact_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_spectrum(data: SpectrumData, base_path: str | Path) -> tuple[Path, Path]:
    array_path, metadata_path = _artifact_paths(base_path)
    array_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        array_path,
        frequency_hz=data.frequency_hz,
        magnitude_db=data.magnitude_db,
        valid_mask=data.valid_mask,
        magnitude_linear=np.array([]) if data.magnitude_linear is None else data.magnitude_linear,
        phase_rad=np.array([]) if data.phase_rad is None else data.phase_rad,
    )
    payload = {
        "measurement_schema_version": MEASUREMENT_SCHEMA_VERSION,
        "representation": data.representation,
        "phase_status": data.phase_status,
        "quality_metrics": data.quality_metrics,
        "magnitude_quantity": data.magnitude_quantity,
        "magnitude_reference": data.magnitude_reference,
        "has_magnitude_linear": data.magnitude_linear is not None,
        "has_phase_rad": data.phase_rad is not None,
        "meta": data.meta.to_dict(),
        "array_sha256": artifact_sha256(array_path),
    }
    _write_json(metadata_path, payload)
    return array_path, metadata_path


def load_spectrum(base_path: str | Path) -> SpectrumData:
    array_path, metadata_path = _artifact_paths(base_path)
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if artifact_sha256(array_path) != payload["array_sha256"]:
        raise ValueError(f"Spectrum array hash mismatch: {array_path}")
    with np.load(array_path, allow_pickle=False) as arrays:
        return SpectrumData(
            frequency_hz=arrays["frequency_hz"],
            magnitude_db=arrays["magnitude_db"],
            valid_mask=arrays["valid_mask"],
            representation=Representation(payload["representation"]),
            phase_status=PhaseStatus(payload["phase_status"]),
            quality_metrics=payload["quality_metrics"],
            meta=MeasurementMeta.from_dict(payload["meta"]),
            magnitude_linear=arrays["magnitude_linear"] if payload["has_magnitude_linear"] else None,
            phase_rad=arrays["phase_rad"] if payload["has_phase_rad"] else None,
            magnitude_quantity=payload["magnitude_quantity"],
            magnitude_reference=payload["magnitude_reference"],
        )


def save_feature_set(data: FeatureSet, base_path: str | Path) -> tuple[Path, Path]:
    array_path, metadata_path = _artifact_paths(base_path)
    array_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        array_path,
        values=data.values,
        valid_mask=data.valid_mask,
        reliability_weights=(
            np.array([]) if data.reliability_weights is None else data.reliability_weights
        ),
    )
    payload = {
        "feature_schema_version": data.feature_schema_version,
        "sample_id": data.sample_id,
        "feature_kind": data.feature_kind,
        "feature_names": data.feature_names,
        "units": data.units,
        "source_measurement_mode": data.source_measurement_mode,
        "source_representation": data.source_representation,
        "tone_set_id": data.tone_set_id,
        "tone_set_sha256": data.tone_set_sha256,
        "tone_schema_id": data.tone_schema_id,
        "normalization_method": data.normalization_method,
        "source_magnitude_quantity": data.source_magnitude_quantity,
        "source_magnitude_reference": data.source_magnitude_reference,
        "source_phase_status": data.source_phase_status,
        "preprocessing_id": data.preprocessing_id,
        "fit_scope_id": data.fit_scope_id,
        "calibration_id": data.calibration_id,
        "reliability_weight_source": data.reliability_weight_source,
        "source_qc_status": data.source_qc_status,
        "source_qc_sha256": data.source_qc_sha256,
        "source_qc_warning_reasons": data.source_qc_warning_reasons,
        "source_qc_exclude_candidate_reasons": (
            data.source_qc_exclude_candidate_reasons
        ),
        "source_qc_unavailable_checks": data.source_qc_unavailable_checks,
        "source_qc_eligible_for_downstream": (
            data.source_qc_eligible_for_downstream
        ),
        "feature_quality": [item.to_dict() for item in data.feature_quality],
        "derivation": None if data.derivation is None else data.derivation.to_dict(),
        "has_reliability_weights": data.reliability_weights is not None,
        "meta": data.meta.to_dict(),
        "array_sha256": artifact_sha256(array_path),
    }
    _write_json(metadata_path, payload)
    return array_path, metadata_path


def load_feature_set(base_path: str | Path) -> FeatureSet:
    array_path, metadata_path = _artifact_paths(base_path)
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if artifact_sha256(array_path) != payload["array_sha256"]:
        raise ValueError(f"Feature array hash mismatch: {array_path}")
    with np.load(array_path, allow_pickle=False) as arrays:
        return FeatureSet(
            sample_id=payload["sample_id"],
            feature_schema_version=payload.get("feature_schema_version", FEATURE_SCHEMA_VERSION),
            feature_kind=FeatureKind(payload["feature_kind"]),
            feature_names=tuple(payload["feature_names"]),
            values=arrays["values"],
            valid_mask=arrays["valid_mask"],
            units=tuple(payload["units"]),
            source_measurement_mode=MeasurementMode(payload["source_measurement_mode"]),
            source_representation=Representation(payload["source_representation"]),
            tone_set_id=payload["tone_set_id"],
            tone_set_sha256=payload.get("tone_set_sha256"),
            tone_schema_id=payload.get("tone_schema_id"),
            normalization_method=payload.get("normalization_method"),
            source_magnitude_quantity=payload.get("source_magnitude_quantity"),
            source_magnitude_reference=payload.get("source_magnitude_reference"),
            source_phase_status=(
                PhaseStatus(payload["source_phase_status"])
                if payload.get("source_phase_status") is not None
                else None
            ),
            preprocessing_id=payload["preprocessing_id"],
            fit_scope_id=payload["fit_scope_id"],
            calibration_id=payload["calibration_id"],
            reliability_weight_source=payload.get("reliability_weight_source"),
            source_qc_status=(
                QCStatus(payload["source_qc_status"])
                if payload.get("source_qc_status") is not None
                else None
            ),
            source_qc_sha256=payload.get("source_qc_sha256"),
            source_qc_warning_reasons=tuple(
                payload.get("source_qc_warning_reasons", ())
            ),
            source_qc_exclude_candidate_reasons=tuple(
                payload.get("source_qc_exclude_candidate_reasons", ())
            ),
            source_qc_unavailable_checks=tuple(
                payload.get("source_qc_unavailable_checks", ())
            ),
            source_qc_eligible_for_downstream=payload.get(
                "source_qc_eligible_for_downstream"
            ),
            feature_quality=tuple(
                FeatureQualityRecord.from_dict(item)
                for item in payload.get("feature_quality", ())
            ),
            derivation=(
                FeatureDerivation.from_dict(payload["derivation"])
                if payload.get("derivation") is not None
                else None
            ),
            reliability_weights=(
                arrays["reliability_weights"] if payload["has_reliability_weights"] else None
            ),
            meta=MeasurementMeta.from_dict(payload["meta"]),
        )

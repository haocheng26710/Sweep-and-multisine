"""Leakage-safe P9-A tone scoring and constrained selection.

The public interface consumes only persisted sweep tone FeatureSets plus explicit,
hash-bound scope objects.  It never reads raw measurement files or classification
and HR results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import itertools
import json
from typing import Any, Mapping, Sequence

import numpy as np

from .dataset_quality_control import (
    CohortRole,
    DatasetQCReference,
    DatasetQCResult,
    DatasetQCInputError,
    feature_contract_sha256,
    feature_set_content_sha256,
    validate_dataset_qc_reference,
)
from .metrics import repeat_pair_unavailable_reason
from .research_gate import RunPurpose, normalize_run_purpose
from .schemas import DataOrigin, DatasetRole, FeatureKind, FeatureSet, MeasurementMode
from .tone_sets import canonical_frequency_text


TONE_SELECTION_SCHEMA_VERSION = "1.0.0"


class ToneSelectionInputError(ValueError):
    """Raised when a P9-A input cannot be trusted."""


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ToneSelectionInputError(f"{name} is required")


def _require_sha256(value: str, name: str) -> None:
    digest = value.removeprefix("sha256:")
    if (
        len(digest) != 64
        or digest != digest.lower()
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ToneSelectionInputError(f"{name} must contain a lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class CandidateTone:
    candidate_id: str
    tone_index: int
    frequency_hz: float
    dft_bin: int

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        if isinstance(self.tone_index, bool) or not isinstance(self.tone_index, int) or self.tone_index < 0:
            raise ToneSelectionInputError("tone_index must be a non-negative integer")
        if not np.isfinite(self.frequency_hz) or self.frequency_hz <= 0:
            raise ToneSelectionInputError("candidate frequency must be finite and positive")
        if isinstance(self.dft_bin, bool) or not isinstance(self.dft_bin, int) or self.dft_bin <= 0:
            raise ToneSelectionInputError("dft_bin must be a positive integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "tone_index": self.tone_index,
            "frequency_hz": self.frequency_hz,
            "dft_bin": self.dft_bin,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CandidateTone":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class CandidateToneUniverse:
    schema_version: str
    candidate_universe_id: str
    source_tone_set_id: str
    source_tone_set_sha256: str
    sample_rate_hz: int
    period_samples: int
    analysis_band_hz: tuple[float, float]
    candidates: tuple[CandidateTone, ...]

    def __post_init__(self) -> None:
        if self.schema_version != TONE_SELECTION_SCHEMA_VERSION:
            raise ToneSelectionInputError("CandidateToneUniverse schema_version must be 1.0.0")
        _require_text(self.candidate_universe_id, "candidate_universe_id")
        _require_text(self.source_tone_set_id, "source_tone_set_id")
        _require_sha256(self.source_tone_set_sha256, "source_tone_set_sha256")
        for name in ("sample_rate_hz", "period_samples"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ToneSelectionInputError(f"{name} must be a positive integer")
        if (
            len(self.analysis_band_hz) != 2
            or not all(np.isfinite(item) for item in self.analysis_band_hz)
            or not 0 < self.analysis_band_hz[0] < self.analysis_band_hz[1]
        ):
            raise ToneSelectionInputError("analysis_band_hz must be finite and increasing")
        if not self.candidates:
            raise ToneSelectionInputError("candidate universe must be non-empty")
        ids = [item.candidate_id for item in self.candidates]
        indices = [item.tone_index for item in self.candidates]
        frequencies = [item.frequency_hz for item in self.candidates]
        bins = [item.dft_bin for item in self.candidates]
        if len(set(ids)) != len(ids):
            raise ToneSelectionInputError("candidate IDs must be unique")
        if indices != list(range(len(indices))):
            raise ToneSelectionInputError("tone indices must be contiguous and ordered")
        if frequencies != sorted(frequencies) or len(set(frequencies)) != len(frequencies):
            raise ToneSelectionInputError("candidate frequencies must be unique and strictly increasing")
        if bins != sorted(bins) or len(set(bins)) != len(bins):
            raise ToneSelectionInputError("candidate DFT bins must be unique and strictly increasing")
        lower, upper = self.analysis_band_hz
        for candidate in self.candidates:
            expected = candidate.dft_bin * self.sample_rate_hz / self.period_samples
            if not np.isclose(candidate.frequency_hz, expected, rtol=0.0, atol=1e-12):
                raise ToneSelectionInputError("candidate violates the exact DFT-bin equation")
            if candidate.frequency_hz >= self.sample_rate_hz / 2:
                raise ToneSelectionInputError("candidate must be below Nyquist")
            if not lower <= candidate.frequency_hz <= upper:
                raise ToneSelectionInputError("candidate is outside the analysis band")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_universe_id": self.candidate_universe_id,
            "source_tone_set_id": self.source_tone_set_id,
            "source_tone_set_sha256": self.source_tone_set_sha256,
            "sample_rate_hz": self.sample_rate_hz,
            "period_samples": self.period_samples,
            "analysis_band_hz": list(self.analysis_band_hz),
            "candidates": [item.to_dict() for item in self.candidates],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CandidateToneUniverse":
        required = {
            "schema_version",
            "candidate_universe_id",
            "source_tone_set_id",
            "source_tone_set_sha256",
            "sample_rate_hz",
            "period_samples",
            "analysis_band_hz",
            "candidates",
        }
        if set(payload) != required:
            raise ToneSelectionInputError("CandidateToneUniverse fields must be explicit")
        value = dict(payload)
        value["analysis_band_hz"] = tuple(value["analysis_band_hz"])
        value["candidates"] = tuple(CandidateTone.from_dict(item) for item in value["candidates"])
        return cls(**value)

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


class SelectionMode(str, Enum):
    DEVELOPMENT_SELECTION = "development_selection"
    FOLD_TRAINING_SELECTION = "fold_training_selection"


class FeatureViewRole(str, Enum):
    DISCRIMINABILITY = "discriminability"
    EFFECTIVE_ENERGY = "effective_energy"
    QUALITY_RELIABILITY = "quality_reliability"


@dataclass(frozen=True, slots=True)
class ToneSelectionFeatureReference:
    artifact_id: str
    sample_id: str
    view_role: FeatureViewRole
    feature_content_sha256: str
    feature_contract_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "view_role", FeatureViewRole(self.view_role))
        _require_text(self.artifact_id, "artifact_id")
        _require_text(self.sample_id, "sample_id")
        _require_sha256(self.feature_content_sha256, "feature_content_sha256")
        _require_sha256(self.feature_contract_sha256, "feature_contract_sha256")

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "sample_id": self.sample_id,
            "view_role": self.view_role.value,
            "feature_content_sha256": self.feature_content_sha256,
            "feature_contract_sha256": self.feature_contract_sha256,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneSelectionFeatureReference":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ToneSelectionMember:
    sample_id: str
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "cohort_role", CohortRole(self.cohort_role))
        for name in ("sample_id", "physical_state_id", "configuration_id", "direction_id"):
            _require_text(getattr(self, name), name)
        if not np.isfinite(self.direction_angle_deg) or not 0 <= self.direction_angle_deg < 360:
            raise ToneSelectionInputError("direction_angle_deg must be in [0, 360)")
        if self.repeat_type is not None and self.repeat_type not in {"CONT", "REPOS", "REASM"}:
            raise ToneSelectionInputError("repeat_type must be CONT, REPOS, or REASM")
        for name in (
            "session_id",
            "repeat_id",
            "reposition_round_id",
            "assembly_id",
            "acquisition_block_id",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_text(value, name)

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__slots__}
        result["cohort_role"] = self.cohort_role.value
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneSelectionMember":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ToneSelectionScope:
    schema_version: str
    selection_scope_id: str
    selection_mode: SelectionMode
    run_purpose: RunPurpose
    data_origin: DataOrigin
    dataset_role: DatasetRole
    candidate_universe_id: str
    candidate_universe_sha256: str
    tone_set_id: str
    tone_set_sha256: str
    members: tuple[ToneSelectionMember, ...]
    feature_references: tuple[ToneSelectionFeatureReference, ...]
    selection_roles: tuple[CohortRole, ...]
    target_count: int
    minimum_spacing_hz: float
    minimum_spacing_bins: int
    allow_partial: bool
    outer_fold_id: str | None
    fold_training_sample_ids: tuple[str, ...]
    held_out_physical_state_ids: tuple[str, ...]
    sealed_final_test_sample_ids: tuple[str, ...]
    sealed_final_test_sha256: str | None
    dataset_qc_analysis_scope_id: str
    dataset_qc_result_sha256: str
    comparison_metrics_result_sha256: str | None
    random_state: int
    selection_reason: str

    def __post_init__(self) -> None:
        if self.schema_version != TONE_SELECTION_SCHEMA_VERSION:
            raise ToneSelectionInputError("ToneSelectionScope schema_version must be 1.0.0")
        object.__setattr__(self, "selection_mode", SelectionMode(self.selection_mode))
        object.__setattr__(self, "run_purpose", normalize_run_purpose(self.run_purpose))
        object.__setattr__(self, "data_origin", DataOrigin(self.data_origin))
        object.__setattr__(self, "dataset_role", DatasetRole(self.dataset_role))
        object.__setattr__(
            self,
            "selection_roles",
            tuple(CohortRole(item) for item in self.selection_roles),
        )
        for name in (
            "selection_scope_id",
            "candidate_universe_id",
            "tone_set_id",
            "dataset_qc_analysis_scope_id",
            "selection_reason",
        ):
            _require_text(getattr(self, name), name)
        for name in (
            "candidate_universe_sha256",
            "tone_set_sha256",
            "dataset_qc_result_sha256",
        ):
            _require_sha256(getattr(self, name), name)
        if self.comparison_metrics_result_sha256 is not None:
            _require_sha256(self.comparison_metrics_result_sha256, "comparison_metrics_result_sha256")
        if self.data_origin is not DataOrigin.SIMULATED or self.run_purpose is not RunPurpose.SOFTWARE_VALIDATION or self.dataset_role is not DatasetRole.SOFTWARE_VALIDATION:
            raise ToneSelectionInputError("DEV-C12 is limited to simulated software_validation")
        if not self.members:
            raise ToneSelectionInputError("selection scope members are required")
        member_ids = [item.sample_id for item in self.members]
        if len(set(member_ids)) != len(member_ids):
            raise ToneSelectionInputError("scope member IDs must be unique")
        artifact_ids = [item.artifact_id for item in self.feature_references]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ToneSelectionInputError("FeatureSet artifact IDs must be unique")
        known_ids = set(member_ids)
        if any(item.sample_id not in known_ids for item in self.feature_references):
            raise ToneSelectionInputError("FeatureSet reference is outside the explicit scope")
        final_ids = {item.sample_id for item in self.members if item.cohort_role is CohortRole.FINAL_TEST}
        if set(self.sealed_final_test_sample_ids) != final_ids:
            raise ToneSelectionInputError("final_test IDs must be explicit and sealed")
        if final_ids:
            if self.sealed_final_test_sha256 is None:
                raise ToneSelectionInputError("sealed final_test hash is required")
            _require_sha256(self.sealed_final_test_sha256, "sealed_final_test_sha256")
        if any(item.sample_id in final_ids for item in self.feature_references):
            raise ToneSelectionInputError("final_test FeatureSets must remain sealed")
        if not self.selection_roles or set(self.selection_roles) - {CohortRole.DEVELOPMENT, CohortRole.TRAINING}:
            raise ToneSelectionInputError("selection roles must be development and/or training")
        selected_members = [item for item in self.members if item.cohort_role in self.selection_roles]
        selected_ids = {item.sample_id for item in selected_members}
        reference_ids = {item.sample_id for item in self.feature_references}
        if reference_ids != selected_ids:
            raise ToneSelectionInputError("FeatureSet inputs must exactly match selection-role samples")
        if isinstance(self.target_count, bool) or not isinstance(self.target_count, int) or self.target_count < 1:
            raise ToneSelectionInputError("target_count must be an integer >= 1")
        if not np.isfinite(self.minimum_spacing_hz) or self.minimum_spacing_hz < 0:
            raise ToneSelectionInputError("minimum_spacing_hz must be finite and non-negative")
        if isinstance(self.minimum_spacing_bins, bool) or not isinstance(self.minimum_spacing_bins, int) or self.minimum_spacing_bins < 1:
            raise ToneSelectionInputError("minimum_spacing_bins must be an integer >= 1")
        if not isinstance(self.allow_partial, bool):
            raise ToneSelectionInputError("allow_partial must be boolean")
        if isinstance(self.random_state, bool) or not isinstance(self.random_state, int) or self.random_state < 0:
            raise ToneSelectionInputError("random_state must be a non-negative integer")
        if self.selection_mode is SelectionMode.FOLD_TRAINING_SELECTION:
            if not self.outer_fold_id or not self.fold_training_sample_ids:
                raise ToneSelectionInputError("fold selection requires outer_fold_id and training sample IDs")
            if tuple(item.sample_id for item in selected_members) != self.fold_training_sample_ids:
                raise ToneSelectionInputError("fold training IDs must exactly match ordered selection samples")
            if any(item.cohort_role is not CohortRole.TRAINING for item in selected_members):
                raise ToneSelectionInputError("fold selection accepts only training samples")
            if {item.physical_state_id for item in selected_members} & set(self.held_out_physical_state_ids):
                raise ToneSelectionInputError("held-out physical state leaked into fold training")
        elif self.outer_fold_id is not None or self.fold_training_sample_ids or self.held_out_physical_state_ids:
            raise ToneSelectionInputError("development selection cannot carry fold-only fields")

    @property
    def dataset_qc_reference(self) -> DatasetQCReference:
        return DatasetQCReference(
            self.dataset_qc_analysis_scope_id,
            self.dataset_qc_result_sha256,
        )

    @property
    def training_sample_sha256(self) -> str:
        ids = self.fold_training_sample_ids or tuple(
            item.sample_id for item in self.members if item.cohort_role in self.selection_roles
        )
        return _canonical_sha256({"ordered_sample_ids": list(ids)})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "selection_scope_id": self.selection_scope_id,
            "selection_mode": self.selection_mode.value,
            "run_purpose": self.run_purpose.value,
            "data_origin": self.data_origin.value,
            "dataset_role": self.dataset_role.value,
            "candidate_universe_id": self.candidate_universe_id,
            "candidate_universe_sha256": self.candidate_universe_sha256,
            "tone_set_id": self.tone_set_id,
            "tone_set_sha256": self.tone_set_sha256,
            "members": [item.to_dict() for item in self.members],
            "feature_references": [item.to_dict() for item in self.feature_references],
            "selection_roles": [item.value for item in self.selection_roles],
            "target_count": self.target_count,
            "minimum_spacing_hz": self.minimum_spacing_hz,
            "minimum_spacing_bins": self.minimum_spacing_bins,
            "allow_partial": self.allow_partial,
            "outer_fold_id": self.outer_fold_id,
            "fold_training_sample_ids": list(self.fold_training_sample_ids),
            "held_out_physical_state_ids": list(self.held_out_physical_state_ids),
            "sealed_final_test_sample_ids": list(self.sealed_final_test_sample_ids),
            "sealed_final_test_sha256": self.sealed_final_test_sha256,
            "dataset_qc_analysis_scope_id": self.dataset_qc_analysis_scope_id,
            "dataset_qc_result_sha256": self.dataset_qc_result_sha256,
            "comparison_metrics_result_sha256": self.comparison_metrics_result_sha256,
            "random_state": self.random_state,
            "selection_reason": self.selection_reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneSelectionScope":
        expected = set(cls.__dataclass_fields__)
        if set(payload) != expected:
            raise ToneSelectionInputError("ToneSelectionScope fields must be explicit")
        value = dict(payload)
        value["members"] = tuple(ToneSelectionMember.from_dict(item) for item in value["members"])
        value["feature_references"] = tuple(
            ToneSelectionFeatureReference.from_dict(item) for item in value["feature_references"]
        )
        for name in (
            "selection_roles",
            "fold_training_sample_ids",
            "held_out_physical_state_ids",
            "sealed_final_test_sample_ids",
        ):
            value[name] = tuple(value[name])
        return cls(**value)

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ToneComponentResult:
    component_id: str
    available: bool
    value: float | None
    units: str
    direction: str
    source_sample_count: int
    source_pair_count: int
    status: str
    reason: str | None = None
    source_sample_ids: tuple[str, ...] = ()
    source_pair_ids: tuple[str, ...] = ()
    details: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "available": self.available,
            "value": self.value,
            "units": self.units,
            "direction": self.direction,
            "source_sample_count": self.source_sample_count,
            "source_pair_count": self.source_pair_count,
            "status": self.status,
            "reason": self.reason,
            "source_sample_ids": list(self.source_sample_ids),
            "source_pair_ids": list(self.source_pair_ids),
            "details": {} if self.details is None else dict(self.details),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneComponentResult":
        value = dict(payload)
        value["source_sample_ids"] = tuple(value["source_sample_ids"])
        value["source_pair_ids"] = tuple(value["source_pair_ids"])
        if value.get("details") == {}:
            value["details"] = None
        return cls(**value)


@dataclass(frozen=True, slots=True)
class CandidateScoreResult:
    candidate_id: str
    tone_index: int
    frequency_hz: float
    dft_bin: int
    eligible: bool
    eligibility_reasons: tuple[str, ...]
    components: Mapping[str, ToneComponentResult]
    final_score: float | None
    scoring_method: str
    warnings: tuple[str, ...] = ()
    normalized_components: Mapping[str, float] | None = None
    weighted_contributions: Mapping[str, float] | None = None
    normalization_details: Mapping[str, Mapping[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "tone_index": self.tone_index,
            "frequency_hz": self.frequency_hz,
            "dft_bin": self.dft_bin,
            "eligible": self.eligible,
            "eligibility_reasons": list(self.eligibility_reasons),
            "components": {
                key: value.to_dict() for key, value in sorted(self.components.items())
            },
            "final_score": self.final_score,
            "scoring_method": self.scoring_method,
            "warnings": list(self.warnings),
            "normalized_components": dict(self.normalized_components or {}),
            "weighted_contributions": dict(self.weighted_contributions or {}),
            "normalization_details": {
                key: dict(value) for key, value in sorted((self.normalization_details or {}).items())
            },
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CandidateScoreResult":
        value = dict(payload)
        value["eligibility_reasons"] = tuple(value["eligibility_reasons"])
        value["warnings"] = tuple(value["warnings"])
        value["components"] = {
            key: ToneComponentResult.from_dict(item) for key, item in value["components"].items()
        }
        value["normalized_components"] = dict(value["normalized_components"])
        value["weighted_contributions"] = dict(value["weighted_contributions"])
        value["normalization_details"] = (
            None
            if value["normalization_details"] == {}
            else {key: dict(item) for key, item in value["normalization_details"].items()}
        )
        return cls(**value)


@dataclass(frozen=True, slots=True)
class ToneReliabilityEvidence:
    schema_version: str
    comparison_metrics_result_sha256: str
    source_feature_content_hashes: Mapping[str, str]
    tone_set_id: str
    tone_set_sha256: str
    frequencies_hz: tuple[float, ...]
    stability_db: tuple[float | None, ...]
    pair_counts: tuple[int, ...]
    pair_ids_by_tone: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if self.schema_version != TONE_SELECTION_SCHEMA_VERSION:
            raise ToneSelectionInputError("ToneReliabilityEvidence schema_version must be 1.0.0")
        _require_sha256(self.comparison_metrics_result_sha256, "comparison_metrics_result_sha256")
        _require_text(self.tone_set_id, "reliability tone_set_id")
        _require_sha256(self.tone_set_sha256, "reliability tone_set_sha256")
        for digest in self.source_feature_content_hashes.values():
            _require_sha256(digest, "reliability source FeatureSet hash")
        size = len(self.frequencies_hz)
        if not size or not (size == len(self.stability_db) == len(self.pair_counts) == len(self.pair_ids_by_tone)):
            raise ToneSelectionInputError("reliability tone arrays must be non-empty and aligned")
        if any(not np.isfinite(item) or item <= 0 for item in self.frequencies_hz):
            raise ToneSelectionInputError("reliability frequencies must be finite and positive")
        if any(item is not None and (not np.isfinite(item) or item < 0) for item in self.stability_db):
            raise ToneSelectionInputError("reliability stability values are invalid")
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in self.pair_counts):
            raise ToneSelectionInputError("reliability pair counts are invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "comparison_metrics_result_sha256": self.comparison_metrics_result_sha256,
            "source_feature_content_hashes": dict(sorted(self.source_feature_content_hashes.items())),
            "tone_set_id": self.tone_set_id,
            "tone_set_sha256": self.tone_set_sha256,
            "frequencies_hz": list(self.frequencies_hz),
            "stability_db": list(self.stability_db),
            "pair_counts": list(self.pair_counts),
            "pair_ids_by_tone": [list(item) for item in self.pair_ids_by_tone],
        }


def _candidate_feature_names(universe: CandidateToneUniverse) -> tuple[str, ...]:
    return tuple(
        f"tone_{item.tone_index:06d}_{canonical_frequency_text(item.frequency_hz)}_hz"
        for item in universe.candidates
    )


def _validate_feature_inputs(
    feature_artifacts: Mapping[str, FeatureSet],
    scope: ToneSelectionScope,
    universe: CandidateToneUniverse,
) -> dict[FeatureViewRole, tuple[FeatureSet, ...]]:
    if scope.candidate_universe_id != universe.candidate_universe_id or scope.candidate_universe_sha256 != universe.sha256:
        raise ToneSelectionInputError("candidate universe ID/hash mismatch")
    if scope.tone_set_id != universe.source_tone_set_id or scope.tone_set_sha256.removeprefix("sha256:") != universe.source_tone_set_sha256.removeprefix("sha256:"):
        raise ToneSelectionInputError("source tone-set ID/hash mismatch")
    references = {item.artifact_id: item for item in scope.feature_references}
    if set(feature_artifacts) != set(references):
        raise ToneSelectionInputError("FeatureSet artifact inputs must exactly match the scope")
    members = {item.sample_id: item for item in scope.members}
    expected_names = _candidate_feature_names(universe)
    grouped: dict[FeatureViewRole, list[FeatureSet]] = {}
    for artifact_id, feature in feature_artifacts.items():
        reference = references[artifact_id]
        member = members[reference.sample_id]
        if feature.sample_id != reference.sample_id:
            raise ToneSelectionInputError("FeatureSet sample ID mismatch")
        if feature_set_content_sha256(feature) != reference.feature_content_sha256:
            raise ToneSelectionInputError("FeatureSet content hash mismatch")
        if feature_contract_sha256(feature) != reference.feature_contract_sha256:
            raise ToneSelectionInputError("FeatureSet contract hash mismatch")
        if feature.feature_kind is not FeatureKind.TONE_PROJECTION_FROM_SWEEP or feature.source_measurement_mode is not MeasurementMode.REW_SWEEP:
            raise ToneSelectionInputError("P9-A accepts only sweep tone-projection FeatureSets")
        if feature.feature_names != expected_names:
            raise ToneSelectionInputError("FeatureSet tone order does not match candidate universe")
        if feature.tone_set_id != scope.tone_set_id or (feature.tone_set_sha256 or "").removeprefix("sha256:") != scope.tone_set_sha256.removeprefix("sha256:"):
            raise ToneSelectionInputError("FeatureSet tone-set contract mismatch")
        metadata = feature.meta
        checks = {
            "configuration_id": metadata.configuration == member.configuration_id,
            "direction_angle_deg": metadata.angle_deg == member.direction_angle_deg,
            "session_id": metadata.session_id == member.session_id,
            "repeat_type": metadata.repeat_type == member.repeat_type,
            "repeat_id": metadata.repeat_id == member.repeat_id,
            "reposition_round_id": metadata.reposition_round_id == member.reposition_round_id,
            "assembly_id": metadata.assembly_id == member.assembly_id,
            "acquisition_block_id": metadata.acquisition_block_id == member.acquisition_block_id,
        }
        failed = [name for name, valid in checks.items() if not valid]
        if failed:
            raise ToneSelectionInputError("FeatureSet metadata scope mismatch: " + ", ".join(failed))
        grouped.setdefault(reference.view_role, []).append(feature)
    ordered_ids = [item.sample_id for item in scope.members if item.cohort_role in scope.selection_roles]
    result: dict[FeatureViewRole, tuple[FeatureSet, ...]] = {}
    for role, features in grouped.items():
        by_id = {item.sample_id: item for item in features}
        if set(by_id) != set(ordered_ids):
            raise ToneSelectionInputError(f"{role.value} view does not align to all selection samples")
        result[role] = tuple(by_id[sample_id] for sample_id in ordered_ids)
    if FeatureViewRole.DISCRIMINABILITY not in result:
        raise ToneSelectionInputError("discriminability FeatureSet view is required")
    return result


def _unavailable_component(
    component_id: str,
    units: str,
    direction: str,
    reason: str,
    *,
    samples: Sequence[str] = (),
    pairs: Sequence[str] = (),
) -> ToneComponentResult:
    return ToneComponentResult(
        component_id,
        False,
        None,
        units,
        direction,
        len(samples),
        len(pairs),
        "unavailable",
        reason,
        tuple(samples),
        tuple(pairs),
    )


def _between_direction_component(
    features: Sequence[FeatureSet],
    tone_index: int,
    minimum_directions: int,
    configuration: str | None = None,
) -> ToneComponentResult:
    by_direction: dict[float, list[tuple[str, float]]] = {}
    for feature in features:
        if configuration is not None and feature.meta.configuration != configuration:
            continue
        if feature.valid_mask[tone_index]:
            assert feature.meta.angle_deg is not None
            by_direction.setdefault(float(feature.meta.angle_deg), []).append(
                (feature.sample_id, float(feature.values[tone_index]))
            )
    sample_ids = tuple(sorted(sample for values in by_direction.values() for sample, _ in values))
    if len(by_direction) < minimum_directions:
        return _unavailable_component(
            "between_direction_variance",
            "dB^2",
            "higher",
            "insufficient_direction_coverage",
            samples=sample_ids,
        )
    centers = np.asarray(
        [np.median([value for _, value in by_direction[key]]) for key in sorted(by_direction)],
        dtype=np.float64,
    )
    return ToneComponentResult(
        "between_direction_variance",
        True,
        float(np.var(centers, ddof=1)),
        "dB^2",
        "higher",
        len(sample_ids),
        0,
        "available",
        None,
        sample_ids,
        (),
        {"center": "median", "direction_count": len(by_direction), "aggregation": "sample_variance", "configuration": configuration},
    )


def _within_repeat_component(
    features: Sequence[FeatureSet],
    tone_index: int,
    repeat_type: str,
    minimum_pairs: int,
) -> ToneComponentResult:
    if minimum_pairs == 0:
        return _unavailable_component(
            f"within_{repeat_type.lower()}_variance",
            "dB^2",
            "lower",
            f"{repeat_type.lower()}_component_not_required",
        )
    estimates: list[float] = []
    pair_ids: list[str] = []
    source_ids: set[str] = set()
    ordered = tuple(sorted(features, key=lambda item: item.sample_id))
    for left, right in itertools.combinations(ordered, 2):
        if left.meta.angle_deg != right.meta.angle_deg:
            continue
        if left.meta.repeat_type != repeat_type or right.meta.repeat_type != repeat_type:
            continue
        if repeat_pair_unavailable_reason(left, right) is not None:
            continue
        if not (left.valid_mask[tone_index] and right.valid_mask[tone_index]):
            continue
        estimates.append(float((left.values[tone_index] - right.values[tone_index]) ** 2 / 2.0))
        pair_ids.append(f"{left.sample_id}__{right.sample_id}")
        source_ids.update((left.sample_id, right.sample_id))
    component_id = f"within_{repeat_type.lower()}_variance"
    if len(estimates) < minimum_pairs:
        return _unavailable_component(
            component_id,
            "dB^2",
            "lower",
            f"insufficient_{repeat_type.lower()}_pairs",
            samples=tuple(sorted(source_ids)),
            pairs=pair_ids,
        )
    return ToneComponentResult(
        component_id,
        True,
        float(np.median(estimates)),
        "dB^2",
        "lower",
        len(source_ids),
        len(pair_ids),
        "available",
        None,
        tuple(sorted(source_ids)),
        tuple(pair_ids),
        {"estimator": "median_half_squared_pair_difference", "repeat_type": repeat_type},
    )


def score_tone_candidates(
    feature_artifacts: Mapping[str, FeatureSet],
    scope: ToneSelectionScope,
    universe: CandidateToneUniverse,
    config: Mapping[str, Any],
    *,
    reliability_evidence: ToneReliabilityEvidence | None = None,
) -> tuple[CandidateScoreResult, ...]:
    """Score candidates using only the explicitly scoped persisted FeatureSets."""
    views = _validate_feature_inputs(feature_artifacts, scope, universe)
    features = views[FeatureViewRole.DISCRIMINABILITY]
    energy_features = views.get(FeatureViewRole.EFFECTIVE_ENERGY)
    quality_features = views.get(FeatureViewRole.QUALITY_RELIABILITY)
    if energy_features is not None and any(
        feature.normalization_method != "none" or set(feature.units) != {"dB"}
        for feature in energy_features
    ):
        raise ToneSelectionInputError("effective_energy view must be unnormalized dB")
    eligibility = config["eligibility"]
    scoring = config["scoring"]
    gain_config = config.get("configuration_gain")
    candidate_configuration = None if gain_config is None else str(gain_config["candidate_configuration"])
    analysis_features = tuple(
        feature for feature in features
        if candidate_configuration is None or feature.meta.configuration == candidate_configuration
    )
    if not analysis_features:
        raise ToneSelectionInputError("candidate configuration has no scoped FeatureSets")
    method = str(scoring["method"])
    if method not in {"variance_ratio", "weighted_rank_sum"}:
        raise ToneSelectionInputError("unsupported tone-selection scoring method")
    minimum_fraction = float(eligibility["minimum_valid_sample_fraction"])
    minimum_directions = int(eligibility["minimum_direction_count"])
    minimum_cont = int(eligibility["minimum_cont_pairs"])
    minimum_repos = int(eligibility["minimum_repos_pairs"])
    epsilon = float(scoring["epsilon_db_squared"])
    if not 0 < minimum_fraction <= 1 or minimum_directions < 2 or minimum_cont < 0 or minimum_repos < 0 or not np.isfinite(epsilon) or epsilon <= 0:
        raise ToneSelectionInputError("invalid tone scoring threshold")
    raw_results: list[CandidateScoreResult] = []
    analysis_band = tuple(float(item) for item in eligibility.get("analysis_band_hz", universe.analysis_band_hz))
    edge_guard_hz = float(eligibility.get("edge_guard_hz", 0.0))
    excluded_bands = tuple(tuple(float(value) for value in item) for item in eligibility.get("excluded_bands_hz", ()))
    safety_distance = float(eligibility.get("excluded_band_safety_distance_hz", 0.0))
    energy_range_value = eligibility.get("effective_energy_range_db")
    energy_range = None if energy_range_value is None else tuple(float(item) for item in energy_range_value)
    reliability_config = config.get("reliability", {})
    if reliability_evidence is not None:
        if scope.comparison_metrics_result_sha256 != reliability_evidence.comparison_metrics_result_sha256:
            raise ToneSelectionInputError("P4-B reliability result hash mismatch")
        expected_source_hashes = {
            feature.sample_id: feature_set_content_sha256(feature) for feature in features
        }
        if dict(reliability_evidence.source_feature_content_hashes) != expected_source_hashes:
            raise ToneSelectionInputError("P4-B reliability source FeatureSet hash mismatch")
        if reliability_evidence.tone_set_id != universe.source_tone_set_id or reliability_evidence.tone_set_sha256.removeprefix("sha256:") != universe.source_tone_set_sha256.removeprefix("sha256:"):
            raise ToneSelectionInputError("P4-B reliability tone-set hash mismatch")
        if not np.array_equal(np.asarray(reliability_evidence.frequencies_hz), np.asarray([item.frequency_hz for item in universe.candidates])):
            raise ToneSelectionInputError("P4-B reliability frequency order mismatch")
    elif scope.comparison_metrics_result_sha256 is not None:
        raise ToneSelectionInputError("scope requires exact P4-B reliability evidence")
    for candidate in universe.candidates:
        index = candidate.tone_index
        valid_fraction = float(np.mean([feature.valid_mask[index] for feature in analysis_features]))
        components: dict[str, ToneComponentResult] = {}
        components["between_direction_variance"] = _between_direction_component(
            analysis_features, index, minimum_directions, candidate_configuration
        )
        components["within_cont_variance"] = _within_repeat_component(
            analysis_features, index, "CONT", minimum_cont
        )
        components["within_repos_variance"] = _within_repeat_component(
            analysis_features, index, "REPOS", minimum_repos
        )
        if gain_config is None:
            components["configuration_gain"] = _unavailable_component(
                "configuration_gain", "ratio", "higher", "configuration_gain_not_configured"
            )
        else:
            baseline_configuration = str(gain_config["baseline_configuration"])
            baseline = _between_direction_component(
                features, index, minimum_directions, baseline_configuration
            )
            candidate_between = components["between_direction_variance"]
            if not baseline.available or not candidate_between.available:
                components["configuration_gain"] = _unavailable_component(
                    "configuration_gain", "ratio", "higher", "matched_configuration_variance_unavailable",
                    samples=tuple(sorted(set(baseline.source_sample_ids) | set(candidate_between.source_sample_ids))),
                )
            else:
                gain_epsilon = float(gain_config["epsilon_db_squared"])
                assert baseline.value is not None and candidate_between.value is not None
                gain_value = (candidate_between.value + gain_epsilon) / (baseline.value + gain_epsilon)
                components["configuration_gain"] = ToneComponentResult(
                    "configuration_gain", True, float(gain_value), "ratio", "higher",
                    baseline.source_sample_count + candidate_between.source_sample_count, 0, "available", None,
                    tuple(sorted(set(baseline.source_sample_ids) | set(candidate_between.source_sample_ids))), (),
                    {"baseline_configuration": baseline_configuration, "candidate_configuration": candidate_configuration, "epsilon_db_squared": gain_epsilon},
                )
        inside_excluded = any(lower <= candidate.frequency_hz <= upper for lower, upper in excluded_bands)
        if inside_excluded:
            proximity = 1.0
        elif excluded_bands and safety_distance > 0:
            distance = min(
                min(abs(candidate.frequency_hz - lower), abs(candidate.frequency_hz - upper))
                for lower, upper in excluded_bands
            )
            proximity = max(0.0, 1.0 - distance / safety_distance)
        else:
            proximity = 0.0
        components["excluded_band_proximity"] = ToneComponentResult(
            "excluded_band_proximity",
            True,
            proximity,
            "ratio",
            "lower",
            0,
            0,
            "available",
            None,
            (),
            (),
            {
                "excluded_bands_hz": [list(item) for item in excluded_bands],
                "safety_distance_hz": safety_distance,
            },
        )
        if energy_features is None:
            components["effective_energy"] = _unavailable_component(
                "effective_energy", "dB", "target_range", "unnormalized_energy_view_not_provided"
            )
            components["effective_energy_margin"] = _unavailable_component(
                "effective_energy_margin", "dB", "higher", "unnormalized_energy_view_not_provided"
            )
        else:
            energy_values = [
                float(feature.values[index])
                for feature in energy_features
                if feature.valid_mask[index]
            ]
            energy_ids = tuple(
                feature.sample_id for feature in energy_features if feature.valid_mask[index]
            )
            if len(energy_values) / len(energy_features) < minimum_fraction:
                components["effective_energy"] = _unavailable_component(
                    "effective_energy", "dB", "target_range", "insufficient_energy_view_coverage", samples=energy_ids
                )
                components["effective_energy_margin"] = _unavailable_component(
                    "effective_energy_margin", "dB", "higher", "insufficient_energy_view_coverage", samples=energy_ids
                )
            else:
                energy_db = float(np.median(energy_values))
                components["effective_energy"] = ToneComponentResult(
                    "effective_energy", True, energy_db, "dB", "target_range", len(energy_ids), 0,
                    "available", None, energy_ids, (), {"estimator": "median"}
                )
                if energy_range is None:
                    components["effective_energy_margin"] = _unavailable_component(
                        "effective_energy_margin", "dB", "higher", "effective_energy_range_not_configured", samples=energy_ids
                    )
                else:
                    margin = min(energy_db - energy_range[0], energy_range[1] - energy_db)
                    components["effective_energy_margin"] = ToneComponentResult(
                        "effective_energy_margin", True, float(margin), "dB", "higher", len(energy_ids), 0,
                        "available", None, energy_ids, (), {"range_db": list(energy_range)}
                    )
        minimum_reliability_pairs = int(reliability_config.get("minimum_pairs_per_tone", 1))
        if reliability_evidence is None or reliability_evidence.stability_db[index] is None or reliability_evidence.pair_counts[index] < minimum_reliability_pairs:
            components["sweep_repeatability"] = _unavailable_component(
                "sweep_repeatability", "dB", "lower", "matching_p4b_reliability_not_provided"
            )
        else:
            components["sweep_repeatability"] = ToneComponentResult(
                "sweep_repeatability", True, float(reliability_evidence.stability_db[index]), "dB", "lower",
                len(reliability_evidence.source_feature_content_hashes), reliability_evidence.pair_counts[index], "available", None,
                tuple(sorted(reliability_evidence.source_feature_content_hashes)), reliability_evidence.pair_ids_by_tone[index],
                {"source": "P4_B_ToneReliabilityResult", "comparison_metrics_result_sha256": reliability_evidence.comparison_metrics_result_sha256},
            )
        snr_values: list[float] = []
        snr_sample_ids: list[str] = []
        if quality_features is not None:
            for feature in quality_features:
                if len(feature.feature_quality) <= index:
                    continue
                snr = feature.feature_quality[index].details.get("snr_db")
                if isinstance(snr, (int, float)) and not isinstance(snr, bool) and np.isfinite(snr):
                    snr_values.append(float(snr))
                    snr_sample_ids.append(feature.sample_id)
        if not snr_values:
            components["instability_noise_penalty"] = _unavailable_component(
                "instability_noise_penalty", "ratio", "lower", "authoritative_snr_or_noise_evidence_unavailable"
            )
        else:
            median_snr = float(np.median(snr_values))
            target_snr = float(reliability_config.get("snr_target_db", 30.0))
            noise_scale = float(reliability_config.get("noise_scale_db", 10.0))
            penalty = max(0.0, target_snr - median_snr) / noise_scale
            components["instability_noise_penalty"] = ToneComponentResult(
                "instability_noise_penalty", True, float(penalty), "ratio", "lower",
                len(snr_values), 0, "available", None, tuple(snr_sample_ids), (),
                {"median_snr_db": median_snr, "snr_target_db": target_snr, "noise_scale_db": noise_scale, "source": "FeatureQualityRecord"},
            )
        reasons: list[str] = []
        if valid_fraction < minimum_fraction:
            reasons.append("insufficient_valid_sample_fraction")
        if not components["between_direction_variance"].available:
            reasons.append("between_direction_variance_unavailable")
        if not analysis_band[0] + edge_guard_hz <= candidate.frequency_hz <= analysis_band[1] - edge_guard_hz:
            reasons.append("analysis_band_edge_guard")
        if inside_excluded:
            reasons.append("excluded_frequency_band")
        if energy_range is not None:
            energy_component = components["effective_energy"]
            if not energy_component.available:
                reasons.append("effective_energy_unavailable")
            elif not energy_range[0] <= float(energy_component.value) <= energy_range[1]:
                reasons.append("effective_energy_out_of_range")
        score: float | None = None
        if method == "variance_ratio" and not reasons:
            ratio = scoring["variance_ratio"]
            cont_weight = float(ratio["within_cont_weight"])
            repos_weight = float(ratio["within_repos_weight"])
            denominator = 0.0
            for component_id, weight in (
                ("within_cont_variance", cont_weight),
                ("within_repos_variance", repos_weight),
            ):
                component = components[component_id]
                if weight > 0 and not component.available:
                    reasons.append(component_id + "_unavailable")
                elif weight > 0:
                    assert component.value is not None
                    denominator += weight * component.value
            if not reasons:
                between = components["between_direction_variance"].value
                assert between is not None
                score = float(between / (denominator + epsilon))
        raw_results.append(
            CandidateScoreResult(
                candidate.candidate_id,
                candidate.tone_index,
                candidate.frequency_hz,
                candidate.dft_bin,
                not reasons,
                tuple(reasons),
                components,
                score,
                method,
            )
        )
    if method == "weighted_rank_sum":
        return _weighted_rank_scores(raw_results, scoring)
    return tuple(raw_results)


def _weighted_rank_scores(
    candidates: Sequence[CandidateScoreResult],
    scoring: Mapping[str, Any],
) -> tuple[CandidateScoreResult, ...]:
    definitions = scoring.get("components")
    if not isinstance(definitions, Mapping) or not definitions:
        raise ToneSelectionInputError("weighted_rank_sum component definitions are required")
    if scoring.get("tie_method") != "average":
        raise ToneSelectionInputError("weighted_rank_sum tie_method must be average")
    if scoring.get("optional_missing_policy") != "renormalize_available_weights_with_warning":
        raise ToneSelectionInputError("unsupported optional component missing policy")
    parsed: dict[str, tuple[bool, str, float]] = {}
    weight_sum = 0.0
    for component_id, definition_value in definitions.items():
        if component_id not in candidates[0].components:
            raise ToneSelectionInputError(f"unknown scoring component: {component_id}")
        if not isinstance(definition_value, Mapping):
            raise ToneSelectionInputError("component definition must be a mapping")
        required = definition_value.get("required")
        direction = definition_value.get("direction")
        weight = definition_value.get("weight")
        if not isinstance(required, bool) or direction not in {"higher", "lower"}:
            raise ToneSelectionInputError("component required/direction fields are invalid")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not np.isfinite(weight) or weight < 0:
            raise ToneSelectionInputError("component weights must be finite and non-negative")
        parsed[str(component_id)] = (required, str(direction), float(weight))
        weight_sum += float(weight)
    if weight_sum <= 0:
        raise ToneSelectionInputError("weighted_rank_sum weights must sum to more than zero")

    eligibility_reasons: dict[str, list[str]] = {
        item.candidate_id: list(item.eligibility_reasons) for item in candidates
    }
    for candidate in candidates:
        for component_id, (required, _direction, weight) in parsed.items():
            if required and weight > 0 and not candidate.components[component_id].available:
                eligibility_reasons[candidate.candidate_id].append(
                    component_id + "_required_unavailable"
                )
    eligible_ids = {
        item.candidate_id
        for item in candidates
        if not eligibility_reasons[item.candidate_id]
    }
    normalized: dict[str, dict[str, float]] = {item.candidate_id: {} for item in candidates}
    normalization_details: dict[str, Mapping[str, Any]] = {}
    for component_id, (_required, direction, weight) in parsed.items():
        if weight == 0:
            continue
        reference = [
            item
            for item in candidates
            if item.candidate_id in eligible_ids and item.components[component_id].available
        ]
        reference.sort(
            key=lambda item: (
                -float(item.components[component_id].value)
                if direction == "higher"
                else float(item.components[component_id].value),
                item.candidate_id,
            )
        )
        if not reference:
            continue
        reference_ids = tuple(item.candidate_id for item in reference)
        normalization_details[component_id] = {
            "direction": direction,
            "tie_method": "average",
            "reference_candidate_ids": list(reference_ids),
            "reference_candidate_sha256": _canonical_sha256({"candidate_ids": list(reference_ids)}),
            "reference_candidate_count": len(reference_ids),
            "rank_denominator": max(0, len(reference_ids) - 1),
        }
        index = 0
        while index < len(reference):
            value = reference[index].components[component_id].value
            end = index + 1
            while end < len(reference) and reference[end].components[component_id].value == value:
                end += 1
            average_rank = ((index + 1) + end) / 2.0
            percentile = 1.0 if len(reference) == 1 else 1.0 - (average_rank - 1.0) / (len(reference) - 1.0)
            for item in reference[index:end]:
                normalized[item.candidate_id][component_id] = float(percentile)
            index = end

    results: list[CandidateScoreResult] = []
    for candidate in candidates:
        reasons = tuple(dict.fromkeys(eligibility_reasons[candidate.candidate_id]))
        warnings = list(candidate.warnings)
        contributions: dict[str, float] = {}
        available_weight = 0.0
        if not reasons:
            for component_id, (required, _direction, weight) in parsed.items():
                if weight == 0:
                    continue
                value = normalized[candidate.candidate_id].get(component_id)
                if value is None:
                    if required:
                        reasons = (*reasons, component_id + "_normalization_unavailable")
                    else:
                        warnings.append(component_id + "_optional_unavailable")
                    continue
                contributions[component_id] = weight * value
                available_weight += weight
        final_score = None
        if not reasons and available_weight > 0:
            final_score = float(sum(contributions.values()) / available_weight)
        elif not reasons:
            reasons = ("no_available_weighted_components",)
        results.append(
            CandidateScoreResult(
                candidate.candidate_id,
                candidate.tone_index,
                candidate.frequency_hz,
                candidate.dft_bin,
                not reasons,
                tuple(reasons),
                candidate.components,
                final_score,
                candidate.scoring_method,
                tuple(warnings),
                normalized[candidate.candidate_id],
                contributions,
                normalization_details,
            )
        )
    return tuple(results)


@dataclass(frozen=True, slots=True)
class SelectionTraceRecord:
    rank: int
    candidate_id: str
    frequency_hz: float
    dft_bin: int
    final_score: float | None
    decision: str
    reason: str
    blocking_candidate_id: str | None = None
    spacing_hz: float | None = None
    spacing_bins: int | None = None
    band_id: str | None = None
    phase: str = "global_fill"

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SelectionTraceRecord":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class GreedySelectionResult:
    processing_status: str
    lifecycle: str
    target_count: int
    selected_candidate_ids: tuple[str, ...]
    trace: tuple[SelectionTraceRecord, ...]
    failures: tuple[str, ...]
    algorithm: str = "deterministic_constrained_greedy_not_globally_optimal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "processing_status": self.processing_status,
            "lifecycle": self.lifecycle,
            "target_count": self.target_count,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "trace": [item.to_dict() for item in self.trace],
            "failures": list(self.failures),
            "algorithm": self.algorithm,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GreedySelectionResult":
        value = dict(payload)
        value["selected_candidate_ids"] = tuple(value["selected_candidate_ids"])
        value["trace"] = tuple(SelectionTraceRecord.from_dict(item) for item in value["trace"])
        value["failures"] = tuple(value["failures"])
        return cls(**value)


def select_tones_greedy(
    scores: Sequence[CandidateScoreResult],
    scope: ToneSelectionScope,
    universe: CandidateToneUniverse,
    config: Mapping[str, Any],
) -> GreedySelectionResult:
    """Apply stable spacing/quota constraints without claiming global optimality."""
    universe_by_id = {item.candidate_id: item for item in universe.candidates}
    if {item.candidate_id for item in scores} != set(universe_by_id):
        raise ToneSelectionInputError("candidate scores must cover the exact universe")
    component_definitions = config.get("scoring", {}).get("components", {})
    required_component_ids = {
        str(component_id)
        for component_id, definition in component_definitions.items()
        if isinstance(definition, Mapping)
        and definition.get("required") is True
        and float(definition.get("weight", 0.0)) > 0
    }

    def required_availability(candidate: CandidateScoreResult) -> int:
        return sum(
            candidate.components[component_id].available
            for component_id in required_component_ids
            if component_id in candidate.components
        )

    ordered = sorted(
        scores,
        key=lambda item: (
            -(item.final_score if item.final_score is not None else -np.inf),
            -required_availability(item),
            item.frequency_hz,
            item.candidate_id,
        ),
    )
    rank_by_id = {item.candidate_id: index for index, item in enumerate(ordered, start=1)}
    quotas_value = config.get("selection", {}).get("band_quotas", ())
    quotas = tuple(
        sorted(
            (dict(item) for item in quotas_value),
            key=lambda item: (float(item["f_min_hz"]), float(item["f_max_hz"]), str(item["band_id"])),
        )
    )
    for left, right in itertools.combinations(quotas, 2):
        if max(float(left["f_min_hz"]), float(right["f_min_hz"])) < min(float(left["f_max_hz"]), float(right["f_max_hz"])):
            raise ToneSelectionInputError("selection band quotas must not overlap")
    selected: list[CandidateScoreResult] = []
    trace_by_id: dict[str, SelectionTraceRecord] = {}

    def band_for(candidate: CandidateScoreResult) -> Mapping[str, Any] | None:
        return next(
            (
                band for band in quotas
                if float(band["f_min_hz"]) <= candidate.frequency_hz <= float(band["f_max_hz"])
            ),
            None,
        )

    def selected_in_band(band: Mapping[str, Any]) -> int:
        return sum(
            float(band["f_min_hz"]) <= item.frequency_hz <= float(band["f_max_hz"])
            for item in selected
        )

    def consider(candidate: CandidateScoreResult, phase: str, required_band: Mapping[str, Any] | None = None) -> bool:
        rank = rank_by_id[candidate.candidate_id]
        if len(selected) >= scope.target_count:
            trace_by_id[candidate.candidate_id] = (
                SelectionTraceRecord(
                    rank,
                    candidate.candidate_id,
                    candidate.frequency_hz,
                    candidate.dft_bin,
                    candidate.final_score,
                    "skipped",
                    "target_count_reached",
                    phase=phase,
                )
            )
            return False
        if not candidate.eligible or candidate.final_score is None:
            trace_by_id[candidate.candidate_id] = (
                SelectionTraceRecord(
                    rank,
                    candidate.candidate_id,
                    candidate.frequency_hz,
                    candidate.dft_bin,
                    candidate.final_score,
                    "skipped",
                    "candidate_ineligible:" + "|".join(candidate.eligibility_reasons),
                    phase=phase,
                )
            )
            return False
        band = band_for(candidate)
        if required_band is not None and band is not required_band:
            return False
        if band is not None and selected_in_band(band) >= int(band["maximum_count"]):
            trace_by_id[candidate.candidate_id] = SelectionTraceRecord(
                rank,
                candidate.candidate_id,
                candidate.frequency_hz,
                candidate.dft_bin,
                candidate.final_score,
                "skipped",
                "band_maximum_quota",
                band_id=str(band["band_id"]),
                phase=phase,
            )
            return False
        blocker: CandidateScoreResult | None = None
        blocker_reason: str | None = None
        spacing_hz: float | None = None
        spacing_bins: int | None = None
        for chosen in selected:
            hz = abs(candidate.frequency_hz - chosen.frequency_hz)
            bins = abs(candidate.dft_bin - chosen.dft_bin)
            if hz < scope.minimum_spacing_hz:
                blocker, blocker_reason, spacing_hz, spacing_bins = chosen, "minimum_spacing_hz", hz, bins
                break
            if bins < scope.minimum_spacing_bins:
                blocker, blocker_reason, spacing_hz, spacing_bins = chosen, "minimum_spacing_bins", hz, bins
                break
        if blocker is not None:
            trace_by_id[candidate.candidate_id] = (
                SelectionTraceRecord(
                    rank,
                    candidate.candidate_id,
                    candidate.frequency_hz,
                    candidate.dft_bin,
                    candidate.final_score,
                    "skipped",
                    str(blocker_reason),
                    blocker.candidate_id,
                    spacing_hz,
                    spacing_bins,
                    None if band is None else str(band["band_id"]),
                    phase,
                )
            )
            return False
        selected.append(candidate)
        trace_by_id[candidate.candidate_id] = (
            SelectionTraceRecord(
                rank,
                candidate.candidate_id,
                candidate.frequency_hz,
                candidate.dft_bin,
                candidate.final_score,
                "selected",
                "eligible_highest_remaining_score",
                band_id=None if band is None else str(band["band_id"]),
                phase=phase,
            )
        )
        return True

    for band in quotas:
        minimum = int(band["minimum_count"])
        maximum = int(band["maximum_count"])
        if minimum < 0 or maximum < minimum:
            raise ToneSelectionInputError("band quota count order is invalid")
        while selected_in_band(band) < minimum:
            added = False
            for candidate in ordered:
                if candidate in selected or candidate.candidate_id in trace_by_id:
                    continue
                if band_for(candidate) is band and consider(candidate, "band_minimum", band):
                    added = True
                    break
            if not added:
                break
    for candidate in ordered:
        if candidate in selected or candidate.candidate_id in trace_by_id:
            continue
        consider(candidate, "global_fill")
    trace = [trace_by_id[item.candidate_id] for item in ordered]
    complete = len(selected) == scope.target_count
    if complete:
        status, lifecycle, failures = "completed", "software_validation_only", ()
    elif scope.allow_partial and selected:
        status, lifecycle = "partial", "draft"
        failures = (f"selected_{len(selected)}_of_{scope.target_count}",)
    else:
        status, lifecycle = "unavailable", "draft"
        failures = (f"insufficient_eligible_candidates:{len(selected)}_of_{scope.target_count}",)
        selected = []
    return GreedySelectionResult(
        status,
        lifecycle,
        scope.target_count,
        tuple(item.candidate_id for item in selected),
        tuple(trace),
        failures,
    )


@dataclass(frozen=True, slots=True)
class SelectedToneRecord:
    selected_order: int
    selection_rank: int
    candidate_id: str
    source_tone_index: int
    frequency_hz: float
    dft_bin: int
    final_score: float

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


@dataclass(frozen=True, slots=True)
class SelectedToneSetArtifact:
    schema_version: str
    selection_id: str
    lifecycle: str
    selection_complete: bool
    selection_scope_id: str
    selection_scope_sha256: str
    config_sha256: str
    candidate_universe_id: str
    candidate_universe_sha256: str
    source_tone_set_id: str
    source_tone_set_sha256: str
    sample_rate_hz: int
    period_samples: int
    selected_tones: tuple[SelectedToneRecord, ...]
    target_count: int
    minimum_spacing_hz: float
    minimum_spacing_bins: int
    training_sample_ids: tuple[str, ...]
    training_sample_sha256: str
    outer_fold_id: str | None
    sealed_final_test_sample_ids: tuple[str, ...]
    sealed_final_test_sha256: str | None
    dataset_qc_result_sha256: str
    comparison_metrics_result_sha256: str | None
    data_origin: str
    run_purpose: str
    scientifically_eligible: bool
    deployment_allowed: bool
    final_test_evaluated: bool
    approval_record: Mapping[str, Any] | None = None
    superseded_by: str | None = None
    scoring_method: str = ""
    component_definitions: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    band_quotas: tuple[Mapping[str, Any], ...] = ()
    selection_trace_sha256: str | None = None
    input_feature_content_hashes: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version != TONE_SELECTION_SCHEMA_VERSION:
            raise ToneSelectionInputError("SelectedToneSetArtifact schema_version must be 1.0.0")
        if self.lifecycle not in {"draft", "software_validation_only", "approved_deployment_tone_set", "superseded"}:
            raise ToneSelectionInputError("unsupported selected tone-set lifecycle")
        if self.data_origin == "simulated" and self.lifecycle == "approved_deployment_tone_set":
            raise ToneSelectionInputError("simulated selection cannot be approved for deployment")
        if self.lifecycle == "approved_deployment_tone_set" and not self.approval_record:
            raise ToneSelectionInputError("approved tone set requires a human approval record")
        if self.lifecycle == "superseded" and not self.superseded_by:
            raise ToneSelectionInputError("superseded tone set requires superseded_by")
        if self.scientifically_eligible or self.deployment_allowed or self.final_test_evaluated:
            raise ToneSelectionInputError("DEV-C12 selection cannot claim science, deployment, or final-test evaluation")
        if self.selection_trace_sha256 is not None:
            _require_sha256(self.selection_trace_sha256, "selection_trace_sha256")
        frequencies = [item.frequency_hz for item in self.selected_tones]
        bins = [item.dft_bin for item in self.selected_tones]
        if frequencies != sorted(frequencies) or len(frequencies) != len(set(frequencies)):
            raise ToneSelectionInputError("selected tones must be unique and frequency ordered")
        if bins != sorted(bins) or len(bins) != len(set(bins)):
            raise ToneSelectionInputError("selected DFT bins must be unique and ordered")

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__slots__}
        result["selected_tones"] = [item.to_dict() for item in self.selected_tones]
        result["training_sample_ids"] = list(self.training_sample_ids)
        result["sealed_final_test_sample_ids"] = list(self.sealed_final_test_sample_ids)
        result["approval_record"] = None if self.approval_record is None else dict(self.approval_record)
        result["component_definitions"] = {
            key: dict(value) for key, value in sorted(self.component_definitions.items())
        }
        result["band_quotas"] = [dict(item) for item in self.band_quotas]
        result["input_feature_content_hashes"] = dict(sorted(self.input_feature_content_hashes.items()))
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SelectedToneSetArtifact":
        expected = set(cls.__dataclass_fields__)
        if set(payload) != expected:
            raise ToneSelectionInputError("SelectedToneSetArtifact fields must be explicit")
        value = dict(payload)
        value["selected_tones"] = tuple(SelectedToneRecord(**item) for item in value["selected_tones"])
        value["training_sample_ids"] = tuple(value["training_sample_ids"])
        value["sealed_final_test_sample_ids"] = tuple(value["sealed_final_test_sample_ids"])
        value["band_quotas"] = tuple(dict(item) for item in value["band_quotas"])
        return cls(**value)

    @property
    def sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ToneSelectionAnalysisResult:
    schema_version: str
    processing_status: str
    selection_id: str
    selection_scope_id: str
    selection_scope_sha256: str
    config_sha256: str
    candidate_universe_sha256: str
    dataset_qc_result_sha256: str
    comparison_metrics_result_sha256: str | None
    data_origin: str
    run_purpose: str
    scientifically_eligible: bool
    deployment_allowed: bool
    final_test_evaluated: bool
    candidate_scores: tuple[CandidateScoreResult, ...]
    selection: GreedySelectionResult
    selected_tone_set: SelectedToneSetArtifact | None
    failures: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "processing_status": self.processing_status,
            "selection_id": self.selection_id,
            "selection_scope_id": self.selection_scope_id,
            "selection_scope_sha256": self.selection_scope_sha256,
            "config_sha256": self.config_sha256,
            "candidate_universe_sha256": self.candidate_universe_sha256,
            "dataset_qc_result_sha256": self.dataset_qc_result_sha256,
            "comparison_metrics_result_sha256": self.comparison_metrics_result_sha256,
            "data_origin": self.data_origin,
            "run_purpose": self.run_purpose,
            "scientifically_eligible": self.scientifically_eligible,
            "deployment_allowed": self.deployment_allowed,
            "final_test_evaluated": self.final_test_evaluated,
            "candidate_scores": [item.to_dict() for item in self.candidate_scores],
            "selection": self.selection.to_dict(),
            "selected_tone_set": None if self.selected_tone_set is None else self.selected_tone_set.to_dict(),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneSelectionAnalysisResult":
        if set(payload) != set(cls.__dataclass_fields__):
            raise ToneSelectionInputError("ToneSelectionAnalysisResult fields must be explicit")
        value = dict(payload)
        value["candidate_scores"] = tuple(CandidateScoreResult.from_dict(item) for item in value["candidate_scores"])
        value["selection"] = GreedySelectionResult.from_dict(value["selection"])
        value["selected_tone_set"] = None if value["selected_tone_set"] is None else SelectedToneSetArtifact.from_dict(value["selected_tone_set"])
        value["failures"] = tuple(value["failures"])
        value["warnings"] = tuple(value["warnings"])
        return cls(**value)


def analyze_tone_selection(
    feature_artifacts: Mapping[str, FeatureSet],
    scope: ToneSelectionScope,
    universe: CandidateToneUniverse,
    config: Mapping[str, Any],
    *,
    dataset_qc_result: DatasetQCResult | None,
    reliability_evidence: ToneReliabilityEvidence | None = None,
) -> ToneSelectionAnalysisResult:
    """Run the complete P9-A core after exact P2-B linkage validation."""
    if dataset_qc_result is None:
        raise ToneSelectionInputError("P2-B result is required")
    if config.get("schema_version") != TONE_SELECTION_SCHEMA_VERSION or not isinstance(config.get("provisional"), bool):
        raise ToneSelectionInputError("tone-selection config schema/provisional fields are invalid")
    views = _validate_feature_inputs(feature_artifacts, scope, universe)
    discriminability = views[FeatureViewRole.DISCRIMINABILITY]
    ordered_ids = tuple(item.sample_id for item in discriminability)
    try:
        validate_dataset_qc_reference(
            discriminability,
            analysis_scope_id=scope.dataset_qc_analysis_scope_id,
            ordered_sample_ids=ordered_ids,
            run_purpose=scope.run_purpose,
            reference=scope.dataset_qc_reference,
            result=dataset_qc_result,
            require_canonical_ready=True,
        )
    except DatasetQCInputError as exc:
        raise ToneSelectionInputError(f"P2-B reference validation failed: {exc}") from exc
    selection_config = config.get("selection", {})
    for field, expected in {
        "target_count": scope.target_count,
        "minimum_spacing_hz": scope.minimum_spacing_hz,
        "minimum_spacing_bins": scope.minimum_spacing_bins,
        "allow_partial": scope.allow_partial,
    }.items():
        if field in selection_config and selection_config[field] != expected:
            raise ToneSelectionInputError(f"scope/config mismatch for {field}")
    scores = score_tone_candidates(
        feature_artifacts,
        scope,
        universe,
        config,
        reliability_evidence=reliability_evidence,
    )
    selection = select_tones_greedy(scores, scope, universe, config)
    config_sha256 = _canonical_sha256(dict(config))
    selection_id = _canonical_sha256(
        {
            "schema_version": TONE_SELECTION_SCHEMA_VERSION,
            "selection_scope_sha256": scope.sha256,
            "config_sha256": config_sha256,
            "candidate_universe_sha256": universe.sha256,
            "candidate_scores": [item.to_dict() for item in scores],
            "selection": selection.to_dict(),
        }
    )
    selected_artifact: SelectedToneSetArtifact | None = None
    if selection.selected_candidate_ids:
        score_by_id = {item.candidate_id: item for item in scores}
        trace_by_id = {item.candidate_id: item for item in selection.trace}
        selected = sorted(
            (score_by_id[item] for item in selection.selected_candidate_ids),
            key=lambda item: (item.frequency_hz, item.candidate_id),
        )
        selected_records = tuple(
            SelectedToneRecord(
                selected_order=index,
                selection_rank=trace_by_id[item.candidate_id].rank,
                candidate_id=item.candidate_id,
                source_tone_index=item.tone_index,
                frequency_hz=item.frequency_hz,
                dft_bin=item.dft_bin,
                final_score=float(item.final_score),
            )
            for index, item in enumerate(selected)
        )
        selected_artifact = SelectedToneSetArtifact(
            TONE_SELECTION_SCHEMA_VERSION,
            selection_id,
            selection.lifecycle,
            selection.processing_status == "completed",
            scope.selection_scope_id,
            scope.sha256,
            config_sha256,
            universe.candidate_universe_id,
            universe.sha256,
            universe.source_tone_set_id,
            universe.source_tone_set_sha256,
            universe.sample_rate_hz,
            universe.period_samples,
            selected_records,
            scope.target_count,
            scope.minimum_spacing_hz,
            scope.minimum_spacing_bins,
            tuple(item.sample_id for item in discriminability),
            scope.training_sample_sha256,
            scope.outer_fold_id,
            scope.sealed_final_test_sample_ids,
            scope.sealed_final_test_sha256,
            scope.dataset_qc_result_sha256,
            scope.comparison_metrics_result_sha256,
            scope.data_origin.value,
            scope.run_purpose.value,
            False,
            False,
            False,
            scoring_method=scores[0].scoring_method,
            component_definitions={key: dict(value) for key, value in config.get("scoring", {}).get("components", {}).items()},
            band_quotas=tuple(dict(item) for item in config.get("selection", {}).get("band_quotas", ())),
            selection_trace_sha256=_canonical_sha256({"trace": [item.to_dict() for item in selection.trace]}),
            input_feature_content_hashes={item.artifact_id: item.feature_content_sha256 for item in scope.feature_references},
        )
    return ToneSelectionAnalysisResult(
        TONE_SELECTION_SCHEMA_VERSION,
        selection.processing_status,
        selection_id,
        scope.selection_scope_id,
        scope.sha256,
        config_sha256,
        universe.sha256,
        scope.dataset_qc_result_sha256,
        scope.comparison_metrics_result_sha256,
        scope.data_origin.value,
        scope.run_purpose.value,
        False,
        False,
        False,
        scores,
        selection,
        selected_artifact,
        selection.failures,
        tuple(warning for item in scores for warning in item.warnings),
    )


def validate_selected_tone_set_for_p7(
    selected_tone_set: SelectedToneSetArtifact,
    stimulus_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Reject an incompatible selection without generating or mutating a WAV."""
    stimulus = stimulus_config.get("stimulus", stimulus_config)
    sample_rate = stimulus.get("sample_rate_hz")
    period_samples = stimulus.get("period_samples")
    if sample_rate != selected_tone_set.sample_rate_hz or period_samples != selected_tone_set.period_samples:
        raise ToneSelectionInputError("selected tone set is incompatible with P7 sample-rate/period constraints")
    if selected_tone_set.selection_complete and len(selected_tone_set.selected_tones) != selected_tone_set.target_count:
        raise ToneSelectionInputError("complete selected tone set does not meet target_count")
    for tone in selected_tone_set.selected_tones:
        expected = tone.dft_bin * sample_rate / period_samples
        if not np.isclose(tone.frequency_hz, expected, rtol=0.0, atol=1e-12):
            raise ToneSelectionInputError("selected tone violates P7 DFT-bin equation")
        if tone.frequency_hz >= sample_rate / 2:
            raise ToneSelectionInputError("selected tone violates P7 Nyquist constraint")
    for left, right in itertools.combinations(selected_tone_set.selected_tones, 2):
        if abs(right.frequency_hz - left.frequency_hz) < selected_tone_set.minimum_spacing_hz:
            raise ToneSelectionInputError("selected tone set violates P7 Hz spacing")
        if abs(right.dft_bin - left.dft_bin) < selected_tone_set.minimum_spacing_bins:
            raise ToneSelectionInputError("selected tone set violates P7 bin spacing")
    return {
        "compatible": True,
        "tone_count": len(selected_tone_set.selected_tones),
        "waveform_generated": False,
    }

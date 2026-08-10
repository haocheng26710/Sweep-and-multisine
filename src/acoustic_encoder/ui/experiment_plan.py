"""Immutable experiment-plan artifacts for the desktop application.

These objects describe acquisition intent and human declarations.  They do not
grant scientific eligibility and are deliberately separate from
``MeasurementMeta.dataset_role``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from acoustic_encoder.schemas import MeasurementMode, artifact_sha256


PLAN_SCHEMA_VERSION = "1.0.0"
SAFETY_CHECKLIST_SCHEMA_VERSION = "1.0.0"
PLAN_MANIFEST_SCHEMA_VERSION = "1.0.0"


class ExperimentRole(str, Enum):
    CALIBRATION = "calibration"
    TRAINING = "training"
    DEVELOPMENT = "development"
    FINAL_TEST_SEALED = "final_test_sealed"


class ChecklistStatus(str, Enum):
    NOT_RECORDED = "not_recorded"
    DECLARED_PASS = "declared_pass"
    DECLARED_UNAVAILABLE = "declared_unavailable"
    DECLARED_FAIL = "declared_fail"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_slug(value: str, *, maximum: int = 24) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return (slug or "plan")[:maximum].rstrip("-")


def _require_timezone(value: str, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")


def _non_empty(values: tuple[str, ...], label: str) -> None:
    if not values or any(not str(item).strip() for item in values):
        raise ValueError(f"{label} must contain non-empty values")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} values must be unique")


@dataclass(frozen=True, slots=True)
class PlanConditionBlock:
    block_id: str
    configurations: tuple[str, ...]
    angles_deg: tuple[float, ...]
    sessions: tuple[str, ...]
    acquisition_blocks: tuple[str, ...]
    measurement_modes: tuple[MeasurementMode, ...]
    experiment_role: ExperimentRole
    cont_repeats: int
    repos_rounds: int
    repos_repeats_per_round: int
    reasm_assemblies: int
    reasm_repeats_per_assembly: int
    stimulus_id: str | None = None
    tone_set_id: str | None = None
    sample_rate_hz: int | None = None
    audio_channel: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "measurement_modes",
            tuple(MeasurementMode(item) for item in self.measurement_modes),
        )
        object.__setattr__(self, "experiment_role", ExperimentRole(self.experiment_role))
        if not self.block_id.strip():
            raise ValueError("condition block ID is required")
        _non_empty(self.configurations, "configurations")
        _non_empty(self.sessions, "sessions")
        _non_empty(self.acquisition_blocks, "acquisition blocks")
        if not self.angles_deg or len(set(self.angles_deg)) != len(self.angles_deg):
            raise ValueError("angles_deg must be non-empty and unique")
        if any(not 0.0 <= float(item) < 360.0 for item in self.angles_deg):
            raise ValueError("angles_deg must lie in [0, 360)")
        if not self.measurement_modes or len(set(self.measurement_modes)) != len(
            self.measurement_modes
        ):
            raise ValueError("measurement modes must be non-empty and unique")
        counts = (
            self.cont_repeats,
            self.repos_rounds,
            self.repos_repeats_per_round,
            self.reasm_assemblies,
            self.reasm_repeats_per_assembly,
        )
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts):
            raise ValueError("repeat counts must be non-negative integers")
        repeat_total = (
            self.cont_repeats
            + self.repos_rounds * self.repos_repeats_per_round
            + self.reasm_assemblies * self.reasm_repeats_per_assembly
        )
        if repeat_total < 1:
            raise ValueError("a condition block must define at least one repeat")
        if any(
            mode is MeasurementMode.SCHROEDER_MULTISINE
            for mode in self.measurement_modes
        ):
            required = {
                "stimulus_id": self.stimulus_id,
                "tone_set_id": self.tone_set_id,
                "sample_rate_hz": self.sample_rate_hz,
                "audio_channel": self.audio_channel,
            }
            missing = [name for name, value in required.items() if value is None or value == ""]
            if missing:
                raise ValueError(
                    "multisine condition block fields are required: "
                    + ", ".join(missing)
                )
        if self.sample_rate_hz is not None and self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.audio_channel is not None and self.audio_channel < 0:
            raise ValueError("audio_channel must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "configurations": list(self.configurations),
            "angles_deg": list(self.angles_deg),
            "sessions": list(self.sessions),
            "acquisition_blocks": list(self.acquisition_blocks),
            "measurement_modes": [item.value for item in self.measurement_modes],
            "experiment_role": self.experiment_role.value,
            "cont_repeats": self.cont_repeats,
            "repos_rounds": self.repos_rounds,
            "repos_repeats_per_round": self.repos_repeats_per_round,
            "reasm_assemblies": self.reasm_assemblies,
            "reasm_repeats_per_assembly": self.reasm_repeats_per_assembly,
            "stimulus_id": self.stimulus_id,
            "tone_set_id": self.tone_set_id,
            "sample_rate_hz": self.sample_rate_hz,
            "audio_channel": self.audio_channel,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PlanConditionBlock":
        return cls(
            block_id=str(value["block_id"]),
            configurations=tuple(str(item) for item in value["configurations"]),
            angles_deg=tuple(float(item) for item in value["angles_deg"]),
            sessions=tuple(str(item) for item in value["sessions"]),
            acquisition_blocks=tuple(
                str(item) for item in value["acquisition_blocks"]
            ),
            measurement_modes=tuple(
                MeasurementMode(item) for item in value["measurement_modes"]
            ),
            experiment_role=ExperimentRole(value["experiment_role"]),
            cont_repeats=int(value["cont_repeats"]),
            repos_rounds=int(value["repos_rounds"]),
            repos_repeats_per_round=int(value["repos_repeats_per_round"]),
            reasm_assemblies=int(value["reasm_assemblies"]),
            reasm_repeats_per_assembly=int(value["reasm_repeats_per_assembly"]),
            stimulus_id=value.get("stimulus_id"),
            tone_set_id=value.get("tone_set_id"),
            sample_rate_hz=(
                None if value.get("sample_rate_hz") is None else int(value["sample_rate_hz"])
            ),
            audio_channel=(
                None if value.get("audio_channel") is None else int(value["audio_channel"])
            ),
        )


@dataclass(frozen=True, slots=True)
class ExperimentPlan:
    schema_version: str
    plan_id: str
    experiment_name: str
    research_question: str
    operator: str
    plan_version: str
    created_at: str
    timezone: str
    device_version: str
    device_chain: str
    calibration_uri: str
    provenance_uri: str
    output_root: str
    condition_blocks: tuple[PlanConditionBlock, ...]

    def __post_init__(self) -> None:
        if self.schema_version != PLAN_SCHEMA_VERSION:
            raise ValueError(f"plan schema_version must be {PLAN_SCHEMA_VERSION}")
        for name in (
            "plan_id",
            "experiment_name",
            "research_question",
            "operator",
            "plan_version",
            "timezone",
            "device_version",
            "device_chain",
            "calibration_uri",
            "provenance_uri",
            "output_root",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"plan {name} is required")
        _require_timezone(self.created_at, "created_at")
        if not self.condition_blocks:
            raise ValueError("plan must contain at least one condition block")
        block_ids = tuple(item.block_id for item in self.condition_blocks)
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("condition block IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "experiment_name": self.experiment_name,
            "research_question": self.research_question,
            "operator": self.operator,
            "plan_version": self.plan_version,
            "created_at": self.created_at,
            "timezone": self.timezone,
            "device_version": self.device_version,
            "device_chain": self.device_chain,
            "calibration_uri": self.calibration_uri,
            "provenance_uri": self.provenance_uri,
            "output_root": self.output_root,
            "condition_blocks": [item.to_dict() for item in self.condition_blocks],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentPlan":
        return cls(
            schema_version=str(value["schema_version"]),
            plan_id=str(value["plan_id"]),
            experiment_name=str(value["experiment_name"]),
            research_question=str(value["research_question"]),
            operator=str(value["operator"]),
            plan_version=str(value["plan_version"]),
            created_at=str(value["created_at"]),
            timezone=str(value["timezone"]),
            device_version=str(value["device_version"]),
            device_chain=str(value["device_chain"]),
            calibration_uri=str(value["calibration_uri"]),
            provenance_uri=str(value["provenance_uri"]),
            output_root=str(value["output_root"]),
            condition_blocks=tuple(
                PlanConditionBlock.from_dict(item)
                for item in value["condition_blocks"]
            ),
        )


@dataclass(frozen=True, slots=True)
class ExpectedSample:
    sample_id: str
    condition_id: str
    block_id: str
    configuration_id: str
    direction_id: str
    angle_deg: float
    session_id: str
    repeat_type: str
    repeat_id: str
    reposition_round_id: str | None
    assembly_id: str | None
    acquisition_block_id: str
    measurement_mode: MeasurementMode
    experiment_role: ExperimentRole
    stimulus_id: str | None
    tone_set_id: str | None
    sample_rate_hz: int | None
    audio_channel: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name not in {"measurement_mode", "experiment_role"}
            },
            "measurement_mode": self.measurement_mode.value,
            "experiment_role": self.experiment_role.value,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExpectedSample":
        fields = {name: value[name] for name in cls.__dataclass_fields__}
        fields["measurement_mode"] = MeasurementMode(fields["measurement_mode"])
        fields["experiment_role"] = ExperimentRole(fields["experiment_role"])
        fields["angle_deg"] = float(fields["angle_deg"])
        return cls(**fields)


@dataclass(frozen=True, slots=True)
class PlanPreview:
    samples: tuple[ExpectedSample, ...]
    expected_sample_count: int
    requires_large_plan_confirmation: bool


@dataclass(frozen=True, slots=True)
class SafetyChecklistItem:
    check_id: str
    status: ChecklistStatus
    operator: str | None
    recorded_at: str | None
    note: str | None
    evidence_path: str | None
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", ChecklistStatus(self.status))
        if not self.check_id.strip():
            raise ValueError("safety checklist check_id is required")
        if self.status is not ChecklistStatus.NOT_RECORDED:
            if not self.operator or not self.recorded_at:
                raise ValueError("recorded safety declarations require operator and time")
            _require_timezone(self.recorded_at, "safety checklist recorded_at")

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status.value,
            "operator": self.operator,
            "recorded_at": self.recorded_at,
            "note": self.note,
            "evidence_path": self.evidence_path,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SafetyChecklistItem":
        return cls(
            check_id=str(value["check_id"]),
            status=ChecklistStatus(value["status"]),
            operator=value.get("operator"),
            recorded_at=value.get("recorded_at"),
            note=value.get("note"),
            evidence_path=value.get("evidence_path"),
            required=bool(value.get("required", True)),
        )


@dataclass(frozen=True, slots=True)
class SafetyChecklist:
    schema_version: str
    items: tuple[SafetyChecklistItem, ...]

    @staticmethod
    def required_check_ids() -> tuple[str, ...]:
        return (
            "device_chain",
            "channel_polarity",
            "sample_rate_bit_depth",
            "dsp_agc_eq",
            "safe_spl_power",
            "stimulus_manifest",
            "raw_data_read_only",
            "sha256_and_backup",
            "operator_record",
            "calibration_record",
            "final_test_custodian",
            "stop_conditions",
        )

    def __post_init__(self) -> None:
        if self.schema_version != SAFETY_CHECKLIST_SCHEMA_VERSION:
            raise ValueError(
                "safety checklist schema_version must be "
                f"{SAFETY_CHECKLIST_SCHEMA_VERSION}"
            )
        ids = tuple(item.check_id for item in self.items)
        if len(ids) != len(set(ids)):
            raise ValueError("safety checklist item IDs must be unique")

    @property
    def missing_required_check_ids(self) -> tuple[str, ...]:
        by_id = {item.check_id: item for item in self.items}
        return tuple(
            check_id
            for check_id in self.required_check_ids()
            if check_id not in by_id
            or by_id[check_id].status is not ChecklistStatus.DECLARED_PASS
        )

    @property
    def ready_for_acquisition(self) -> bool:
        return not self.missing_required_check_ids

    @property
    def scientific_eligibility_granted(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "items": [item.to_dict() for item in self.items],
            "ready_for_acquisition": self.ready_for_acquisition,
            "scientific_eligibility_granted": False,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SafetyChecklist":
        return cls(
            schema_version=str(value["schema_version"]),
            items=tuple(SafetyChecklistItem.from_dict(item) for item in value["items"]),
        )


@dataclass(frozen=True, slots=True)
class SavedPlanRevision:
    directory: Path
    revision: int
    plan: ExperimentPlan
    checklist: SafetyChecklist
    samples: tuple[ExpectedSample, ...]
    artifact_hashes: tuple[tuple[str, str], ...]


class ExperimentPlanService:
    def __init__(self, plan_root: str | Path, *, large_plan_threshold: int = 500) -> None:
        if large_plan_threshold < 1:
            raise ValueError("large_plan_threshold must be positive")
        self.plan_root = Path(plan_root).resolve()
        self.large_plan_threshold = int(large_plan_threshold)

    def preview(self, plan: ExperimentPlan) -> PlanPreview:
        samples: list[ExpectedSample] = []
        plan_slug = _safe_slug(plan.plan_id)
        for block in sorted(plan.condition_blocks, key=lambda item: item.block_id):
            repeats: list[tuple[str, str, str | None, str | None]] = []
            repeats.extend(
                ("CONT", f"CONT-{index:03d}", None, None)
                for index in range(1, block.cont_repeats + 1)
            )
            for round_index in range(1, block.repos_rounds + 1):
                for repeat_index in range(1, block.repos_repeats_per_round + 1):
                    repeats.append(
                        (
                            "REPOS",
                            f"REPOS-{round_index:03d}-{repeat_index:03d}",
                            f"RP-{round_index:03d}",
                            None,
                        )
                    )
            for assembly_index in range(1, block.reasm_assemblies + 1):
                for repeat_index in range(1, block.reasm_repeats_per_assembly + 1):
                    repeats.append(
                        (
                            "REASM",
                            f"REASM-{assembly_index:03d}-{repeat_index:03d}",
                            None,
                            f"AS-{assembly_index:03d}",
                        )
                    )
            for mode in sorted(block.measurement_modes, key=lambda item: item.value):
                for configuration in sorted(block.configurations):
                    for angle in sorted(float(item) for item in block.angles_deg):
                        for session in sorted(block.sessions):
                            for acquisition_block in sorted(block.acquisition_blocks):
                                for repeat_type, repeat_id, reposition, assembly in repeats:
                                    identity = {
                                        "plan_id": plan.plan_id,
                                        "block_id": block.block_id,
                                        "configuration_id": configuration,
                                        "angle_deg": angle,
                                        "session_id": session,
                                        "repeat_type": repeat_type,
                                        "repeat_id": repeat_id,
                                        "reposition_round_id": reposition,
                                        "assembly_id": assembly,
                                        "acquisition_block_id": acquisition_block,
                                        "measurement_mode": mode.value,
                                        "experiment_role": block.experiment_role.value,
                                        "stimulus_id": block.stimulus_id,
                                        "tone_set_id": block.tone_set_id,
                                        "sample_rate_hz": block.sample_rate_hz,
                                        "audio_channel": block.audio_channel,
                                    }
                                    digest = _canonical_sha256(identity)
                                    condition_identity = {
                                        name: value
                                        for name, value in identity.items()
                                        if name != "repeat_id"
                                    }
                                    samples.append(
                                        ExpectedSample(
                                            sample_id=f"s-{plan_slug}-{digest[:16]}",
                                            condition_id=f"c-{_canonical_sha256(condition_identity)[:16]}",
                                            block_id=block.block_id,
                                            configuration_id=configuration,
                                            direction_id=f"D{angle:g}",
                                            angle_deg=angle,
                                            session_id=session,
                                            repeat_type=repeat_type,
                                            repeat_id=repeat_id,
                                            reposition_round_id=reposition,
                                            assembly_id=assembly,
                                            acquisition_block_id=acquisition_block,
                                            measurement_mode=mode,
                                            experiment_role=block.experiment_role,
                                            stimulus_id=block.stimulus_id,
                                            tone_set_id=block.tone_set_id,
                                            sample_rate_hz=block.sample_rate_hz,
                                            audio_channel=block.audio_channel,
                                        )
                                    )
        ordered = tuple(samples)
        if len({item.sample_id for item in ordered}) != len(ordered):
            raise ValueError("expected sample identities are not unique")
        return PlanPreview(
            samples=ordered,
            expected_sample_count=len(ordered),
            requires_large_plan_confirmation=len(ordered) > self.large_plan_threshold,
        )

    def save_revision(
        self,
        plan: ExperimentPlan,
        checklist: SafetyChecklist,
        *,
        revision_reason: str | None = None,
        forced_revision: int | None = None,
    ) -> SavedPlanRevision:
        plan_digest = _canonical_sha256({"plan_id": plan.plan_id})[:8]
        plan_directory = self.plan_root / f"{_safe_slug(plan.plan_id)}-{plan_digest}"
        existing = sorted(
            int(path.name.removeprefix("rev-"))
            for path in plan_directory.glob("rev-[0-9][0-9][0-9]")
            if path.is_dir()
        ) if plan_directory.is_dir() else []
        revision = forced_revision if forced_revision is not None else (max(existing, default=0) + 1)
        if revision < 1:
            raise ValueError("plan revision must be positive")
        output = plan_directory / f"rev-{revision:03d}"
        if output.exists():
            raise FileExistsError(f"plan revision already exists: {output}")
        if existing and not revision_reason:
            raise ValueError("a new plan revision requires revision_reason")
        preview = self.preview(plan)
        output.mkdir(parents=True, exist_ok=False)
        plan_path = output / "acquisition_plan.json"
        plan_path.write_text(
            json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        checklist_path = output / "safety_checklist.json"
        checklist_path.write_text(
            json.dumps(checklist.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        matrix_path = output / "expected_sample_matrix.csv"
        rows = [item.to_dict() for item in preview.samples]
        with matrix_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        markdown_path = output / "acquisition_plan.md"
        markdown_path.write_text(
            self._markdown(plan, checklist, preview), encoding="utf-8"
        )
        primary_paths = (plan_path, markdown_path, matrix_path, checklist_path)
        primary_hashes = {
            path.name: artifact_sha256(path) for path in primary_paths
        }
        manifest = {
            "schema_version": PLAN_MANIFEST_SCHEMA_VERSION,
            "plan_id": plan.plan_id,
            "plan_version": plan.plan_version,
            "revision": revision,
            "revision_reason": revision_reason,
            "created_at": plan.created_at,
            "expected_sample_count": preview.expected_sample_count,
            "large_plan_confirmation_threshold": self.large_plan_threshold,
            "ready_for_acquisition": checklist.ready_for_acquisition,
            "scientific_eligibility_granted": False,
            "artifacts": [
                {"path": name, "sha256": digest}
                for name, digest in sorted(primary_hashes.items())
            ],
        }
        manifest_path = output / "plan_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        all_hashes = {
            **primary_hashes,
            manifest_path.name: artifact_sha256(manifest_path),
        }
        hashes_path = output / "hashes.json"
        hashes_path.write_text(
            json.dumps(all_hashes, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        return SavedPlanRevision(
            output.resolve(),
            revision,
            plan,
            checklist,
            preview.samples,
            tuple(sorted(all_hashes.items())),
        )

    def load_revision(self, directory: str | Path) -> SavedPlanRevision:
        root = Path(directory).resolve()
        plan = ExperimentPlan.from_dict(
            json.loads((root / "acquisition_plan.json").read_text(encoding="utf-8"))
        )
        checklist = SafetyChecklist.from_dict(
            json.loads((root / "safety_checklist.json").read_text(encoding="utf-8"))
        )
        manifest_path = root / "plan_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hashes = json.loads((root / "hashes.json").read_text(encoding="ascii"))
        for name, expected in hashes.items():
            path = root / name
            if not path.is_file() or artifact_sha256(path) != expected:
                raise ValueError(f"plan artifact hash mismatch: {path}")
        preview = self.preview(plan)
        if preview.expected_sample_count != int(manifest["expected_sample_count"]):
            raise ValueError("plan manifest sample count mismatch")
        return SavedPlanRevision(
            root,
            int(manifest["revision"]),
            plan,
            checklist,
            preview.samples,
            tuple(sorted((str(name), str(value)) for name, value in hashes.items())),
        )

    @staticmethod
    def _markdown(
        plan: ExperimentPlan, checklist: SafetyChecklist, preview: PlanPreview
    ) -> str:
        return (
            f"# Acquisition plan: {plan.experiment_name}\n\n"
            f"- Plan ID: `{plan.plan_id}`\n"
            f"- Plan version: `{plan.plan_version}`\n"
            f"- Operator: `{plan.operator}`\n"
            f"- Created: `{plan.created_at}` ({plan.timezone})\n"
            f"- Expected samples: `{preview.expected_sample_count}`\n"
            f"- Ready for acquisition: `{str(checklist.ready_for_acquisition).lower()}`\n"
            "- Scientific eligibility granted by this checklist: `false`\n\n"
            "## Research question\n\n"
            f"{plan.research_question}\n\n"
            "The matrix is preregistered from explicit form fields. No condition "
            "was inferred from files or directories.\n"
        )

"""Explicit UI2 sample registration and plan matching.

No API in this module discovers files recursively.  Every loaded session,
manifest and output directory must be selected explicitly by the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from acoustic_encoder.schemas import (
    DataOrigin,
    MeasurementMeta,
    MeasurementMode,
    artifact_sha256,
)
from acoustic_encoder.ui.experiment_plan import ExpectedSample, ExperimentRole
from acoustic_encoder.ui.state import GateDecision, HARD_BLOCK_REAL_MULTISINE_MESSAGE


class FinalTestSealedError(PermissionError):
    """Raised before any selected final-test artifact is opened."""


class MatchStatus(str, Enum):
    EXPECTED_AND_PRESENT = "expected_and_present"
    EXPECTED_BUT_MISSING = "expected_but_missing"
    UNEXPECTED_SAMPLE = "unexpected_sample"
    DUPLICATE_IDENTITY = "duplicate_identity"
    METADATA_MISMATCH = "metadata_mismatch"
    HASH_MISMATCH = "hash_mismatch"
    BLOCKED = "blocked"
    FINAL_TEST_SEALED = "final_test_sealed"


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    path: str
    sha256: str
    artifact_type: str


@dataclass(frozen=True, slots=True)
class RegisteredSample:
    registration_id: str
    source_sample_id: str
    expected_sample_id: str | None
    session_manifest_path: Path
    metadata_path: Path
    output_directory: Path | None
    metadata: MeasurementMeta
    run_purpose: str
    analysis_status: str
    qc_status: str | None
    manual_review_reasons: tuple[str, ...]
    source_hash_matches: bool
    artifact_hashes_match: bool
    feature_set_available: bool
    spectrum_data_available: bool
    artifacts: tuple[ArtifactReference, ...]


@dataclass(frozen=True, slots=True)
class SampleMatchRow:
    expected_sample_id: str | None
    source_sample_ids: tuple[str, ...]
    status: MatchStatus
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SampleMatchResult:
    rows: tuple[SampleMatchRow, ...]

    @property
    def complete(self) -> bool:
        return bool(self.rows) and all(
            row.status is MatchStatus.EXPECTED_AND_PRESENT
            for row in self.rows
            if row.expected_sample_id is not None
        ) and not any(
            row.status is MatchStatus.UNEXPECTED_SAMPLE for row in self.rows
        )


@dataclass(frozen=True, slots=True)
class ManualReviewDecision:
    operator: str
    recorded_at: str
    reason: str
    decision: str
    note: str | None

    def __post_init__(self) -> None:
        for name in ("operator", "recorded_at", "reason", "decision"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"manual review {name} is required")
        parsed = datetime.fromisoformat(self.recorded_at)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("manual review recorded_at must include a timezone")


@dataclass(frozen=True, slots=True)
class ManualReviewAudit:
    audit_index: int
    registration_id: str
    source_sample_id: str
    decision: ManualReviewDecision


def _read_json_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _resolve_path(value: str, parent: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


class SampleRegistry:
    def __init__(self, registry_directory: str | Path) -> None:
        self.registry_directory = Path(registry_directory).resolve()

    def mode_gate(
        self, *, data_origin: DataOrigin | str, expected: ExpectedSample
    ) -> GateDecision:
        if (
            DataOrigin(data_origin) is DataOrigin.REAL_EXPERIMENT
            and expected.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE
        ):
            return GateDecision(False, HARD_BLOCK_REAL_MULTISINE_MESSAGE)
        return GateDecision(True, "当前样本未触发真实 Multisine/P8 硬门禁。")

    def register_ui2_session(
        self,
        session_manifest_path: str | Path,
        *,
        expected: ExpectedSample | None = None,
        output_directory: str | Path | None = None,
    ) -> RegisteredSample:
        manifest_path = Path(session_manifest_path).resolve()
        if expected is not None and expected.experiment_role is ExperimentRole.FINAL_TEST_SEALED:
            self._record_final_test_incident(manifest_path, expected.sample_id)
            raise FinalTestSealedError(
                "final_test_sealed artifact selection was blocked before content read"
            )
        manifest = _read_json_mapping(manifest_path)
        if manifest.get("ui_session_schema_version") != "1.0.0":
            raise ValueError("unsupported UI2 session manifest schema")
        digest_path = manifest_path.with_suffix(".sha256")
        if not digest_path.is_file():
            raise FileNotFoundError(digest_path)
        expected_digest = digest_path.read_text(encoding="ascii").strip().split()[0]
        if artifact_sha256(manifest_path) != expected_digest:
            raise ValueError("UI2 session manifest hash mismatch")
        metadata_path = _resolve_path(str(manifest["metadata_path"]), manifest_path.parent)
        metadata_payload = _read_json_mapping(metadata_path)
        allowed = set(MeasurementMeta.__dataclass_fields__)
        metadata = MeasurementMeta.from_dict(
            {name: value for name, value in metadata_payload.items() if name in allowed}
        )
        if metadata.sample_id != str(manifest["sample_id"]):
            raise ValueError("UI2 session/metadata sample ID mismatch")
        if metadata.measurement_mode.value != str(manifest["measurement_mode"]):
            raise ValueError("UI2 session/metadata measurement mode mismatch")
        if metadata.data_origin.value != str(manifest["data_origin"]):
            raise ValueError("UI2 session/metadata data origin mismatch")
        source_path = Path(metadata.source_path).resolve()
        source_matches = source_path.is_file() and artifact_sha256(source_path) == metadata.source_sha256
        artifacts: list[ArtifactReference] = []
        artifact_hashes_match = True
        qc_status: str | None = None
        analysis_status = str(manifest.get("analysis_status", "unknown"))
        selected_output = None if output_directory is None else Path(output_directory).resolve()
        if selected_output is not None:
            run_manifest_path = selected_output / "run_manifest.json"
            run_manifest = _read_json_mapping(run_manifest_path)
            if str(run_manifest.get("sample_id")) != metadata.sample_id:
                raise ValueError("run output sample ID does not match UI2 session")
            if str(run_manifest.get("recording_hash")) != metadata.source_sha256:
                artifact_hashes_match = False
            if str(run_manifest.get("measurement_mode")) != metadata.measurement_mode.value:
                raise ValueError("run output measurement mode mismatch")
            qc_status = None if run_manifest.get("qc_status") is None else str(run_manifest["qc_status"])
            analysis_status = str(run_manifest.get("processing_status", analysis_status))
            for item in run_manifest.get("artifacts", ()):  # exact manifest list only
                relative = Path(str(item["path"]))
                path = relative.resolve() if relative.is_absolute() else (selected_output / relative).resolve()
                expected_hash = str(item["sha256"])
                matches = path.is_file() and artifact_sha256(path) == expected_hash
                artifact_hashes_match = artifact_hashes_match and matches
                artifacts.append(
                    ArtifactReference(
                        path=path.as_posix(),
                        sha256=expected_hash,
                        artifact_type=self._artifact_type(path),
                    )
                )
        registration_identity = {
            "manifest_path": manifest_path.as_posix(),
            "manifest_sha256": artifact_sha256(manifest_path),
            "expected_sample_id": None if expected is None else expected.sample_id,
            "output_directory": None if selected_output is None else selected_output.as_posix(),
        }
        import hashlib

        registration_id = "reg-" + hashlib.sha256(
            json.dumps(registration_identity, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return RegisteredSample(
            registration_id=registration_id,
            source_sample_id=metadata.sample_id,
            expected_sample_id=None if expected is None else expected.sample_id,
            session_manifest_path=manifest_path,
            metadata_path=metadata_path,
            output_directory=selected_output,
            metadata=metadata,
            run_purpose=str(manifest["run_purpose"]),
            analysis_status=analysis_status,
            qc_status=qc_status,
            manual_review_reasons=tuple(metadata.manual_review_reasons),
            source_hash_matches=source_matches,
            artifact_hashes_match=artifact_hashes_match,
            feature_set_available=any(item.artifact_type == "feature_set" for item in artifacts),
            spectrum_data_available=any(item.artifact_type == "spectrum_data" for item in artifacts),
            artifacts=tuple(artifacts),
        )

    @staticmethod
    def _artifact_type(path: Path) -> str:
        normalized = path.as_posix().lower()
        if "spectrum_data" in path.name.lower():
            return "spectrum_data"
        if "/processed/" in normalized and path.suffix.lower() in {".json", ".npz"}:
            return "feature_set"
        if "quality_control" in path.name.lower() or "measurement_qc" in path.name.lower():
            return "quality_control"
        return "other"

    def match(
        self,
        expected_samples: Sequence[ExpectedSample],
        registrations: Sequence[RegisteredSample],
    ) -> SampleMatchResult:
        expected = tuple(expected_samples)
        actual = tuple(registrations)
        expected_ids = tuple(item.sample_id for item in expected)
        if len(expected_ids) != len(set(expected_ids)):
            raise ValueError("expected sample IDs must be unique")
        by_hint: dict[str, list[RegisteredSample]] = {}
        for item in actual:
            if item.expected_sample_id is not None:
                by_hint.setdefault(item.expected_sample_id, []).append(item)
        rows: list[SampleMatchRow] = []
        for target in expected:
            if target.experiment_role is ExperimentRole.FINAL_TEST_SEALED:
                rows.append(
                    SampleMatchRow(target.sample_id, (), MatchStatus.FINAL_TEST_SEALED, ("final_test_content_not_read",))
                )
                continue
            matches = by_hint.get(target.sample_id, [])
            if not matches:
                rows.append(
                    SampleMatchRow(target.sample_id, (), MatchStatus.EXPECTED_BUT_MISSING, ("expected_sample_not_registered",))
                )
                continue
            ids = tuple(item.source_sample_id for item in matches)
            if len(matches) > 1:
                rows.append(
                    SampleMatchRow(target.sample_id, ids, MatchStatus.DUPLICATE_IDENTITY, ("multiple_registrations_for_expected_identity",))
                )
                continue
            item = matches[0]
            if not item.source_hash_matches or not item.artifact_hashes_match:
                rows.append(
                    SampleMatchRow(target.sample_id, ids, MatchStatus.HASH_MISMATCH, ("registered_input_or_artifact_hash_mismatch",))
                )
                continue
            mismatches = self._metadata_mismatches(target, item.metadata)
            if mismatches:
                rows.append(
                    SampleMatchRow(target.sample_id, ids, MatchStatus.METADATA_MISMATCH, mismatches)
                )
                continue
            gate = self.mode_gate(data_origin=item.metadata.data_origin, expected=target)
            if not gate.allowed or item.analysis_status in {"blocked", "failed"}:
                reasons = (gate.reason,) if not gate.allowed else (f"analysis_status_{item.analysis_status}",)
                rows.append(SampleMatchRow(target.sample_id, ids, MatchStatus.BLOCKED, reasons))
                continue
            rows.append(
                SampleMatchRow(target.sample_id, ids, MatchStatus.EXPECTED_AND_PRESENT, ())
            )
        for item in actual:
            if item.expected_sample_id is None or item.expected_sample_id not in set(expected_ids):
                rows.append(
                    SampleMatchRow(
                        None,
                        (item.source_sample_id,),
                        MatchStatus.UNEXPECTED_SAMPLE,
                        ("registration_not_bound_to_expected_plan_identity",),
                    )
                )
        return SampleMatchResult(tuple(rows))

    @staticmethod
    def _metadata_mismatches(
        expected: ExpectedSample, metadata: MeasurementMeta
    ) -> tuple[str, ...]:
        comparisons = {
            "measurement_mode": metadata.measurement_mode is expected.measurement_mode,
            "configuration": metadata.configuration == expected.configuration_id,
            "angle_deg": metadata.angle_deg == expected.angle_deg,
            "session_id": metadata.session_id == expected.session_id,
            "repeat_type": metadata.repeat_type == expected.repeat_type,
            "repeat_id": metadata.repeat_id == expected.repeat_id,
            "reposition_round_id": metadata.reposition_round_id == expected.reposition_round_id,
            "assembly_id": metadata.assembly_id == expected.assembly_id,
            "acquisition_block_id": metadata.acquisition_block_id == expected.acquisition_block_id,
            "stimulus_id": metadata.stimulus_id == expected.stimulus_id,
            "tone_set_id": metadata.tone_set_id == expected.tone_set_id,
            "audio_channel": metadata.audio_channel == expected.audio_channel,
        }
        return tuple(f"metadata_{name}_mismatch" for name, matches in comparisons.items() if not matches)

    def append_manual_review(
        self, sample: RegisteredSample, decision: ManualReviewDecision
    ) -> ManualReviewAudit:
        existing = self.load_manual_reviews()
        audit = ManualReviewAudit(
            audit_index=len(existing) + 1,
            registration_id=sample.registration_id,
            source_sample_id=sample.source_sample_id,
            decision=decision,
        )
        self.registry_directory.mkdir(parents=True, exist_ok=True)
        path = self.registry_directory / "manual_review_audit.jsonl"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    {
                        "audit_index": audit.audit_index,
                        "registration_id": audit.registration_id,
                        "source_sample_id": audit.source_sample_id,
                        "operator": decision.operator,
                        "recorded_at": decision.recorded_at,
                        "reason": decision.reason,
                        "decision": decision.decision,
                        "note": decision.note,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            )
        return audit

    def load_manual_reviews(self) -> tuple[dict[str, Any], ...]:
        path = self.registry_directory / "manual_review_audit.jsonl"
        if not path.is_file():
            return ()
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    def _record_final_test_incident(
        self, selected_path: Path, expected_sample_id: str
    ) -> None:
        self.registry_directory.mkdir(parents=True, exist_ok=True)
        path = self.registry_directory / "final_test_incidents.jsonl"
        record = {
            "incident_id": f"fti-{int(datetime.now(UTC).timestamp() * 1_000_000)}",
            "recorded_at_utc": datetime.now(UTC).isoformat(),
            "expected_sample_id": expected_sample_id,
            "selected_path": selected_path.as_posix(),
            "content_read": False,
            "scope_valid": False,
            "manual_review_required": True,
        }
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    def load_final_test_incidents(self) -> tuple[dict[str, Any], ...]:
        path = self.registry_directory / "final_test_incidents.jsonl"
        if not path.is_file():
            return ()
        return tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

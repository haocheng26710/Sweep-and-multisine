"""Explicit, UI-owned orchestration for the simulated steps 04--07.

The service never discovers measurements by scanning an output tree.  Every
transition is bound to one immutable plan revision and one explicitly recorded
manifest path.  Scientific algorithms remain in the existing P7/S3/P8 modules.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
import csv
import json
import hashlib
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping

import numpy as np
from scipy.io import wavfile

from acoustic_encoder.config import load_config
from acoustic_encoder.mock_data import (
    known_transfer_db,
    simulate_multisine_recording_waveform,
)
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    QCStatus,
    SourceFormat,
    artifact_sha256,
)
from acoustic_encoder.stimulus_multisine import generate_multisine
from acoustic_encoder.run_execution import execute_measurement_run
from acoustic_encoder.ui.experiment_plan import (
    ExperimentPlanService,
    SavedPlanRevision,
)
from acoustic_encoder.ui.measurement_workflow import (
    MeasurementDraftService,
    MetadataFormValues,
    UsageRoute,
)
from acoustic_encoder.ui.sample_registry import MatchStatus, SampleRegistry
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


SIMULATED_FLOW_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class StimulusFlowArtifacts:
    directory: Path
    wav_path: Path
    manifest_path: Path
    tones_path: Path
    hashes_path: Path
    waveform_sha256: str


@dataclass(frozen=True, slots=True)
class SimulatedAcquisitionBatch:
    directory: Path
    manifest_path: Path
    manifest_hash_path: Path
    sample_count: int


@dataclass(frozen=True, slots=True)
class SimulatedProcessingBatch:
    directory: Path
    manifest_path: Path
    manifest_hash_path: Path
    status: str
    processed_count: int


@dataclass(frozen=True, slots=True)
class SimulatedDatasetAudit:
    directory: Path
    manifest_path: Path
    manifest_hash_path: Path
    status: str


@dataclass(frozen=True, slots=True)
class SoftwareValidationSummary:
    directory: Path
    markdown_path: Path
    manifest_path: Path
    manifest_hash_path: Path


class SimulatedFlowService:
    """Coordinate immutable simulated artifacts without becoming their authority."""

    def __init__(self, project_root: str | Path, workspace_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.workspace_root = Path(workspace_root).resolve()
        self.flow_root = self.workspace_root / "outputs/ui_simulated_flow"
        self.state_path = self.flow_root / "workflow_state.json"
        self.state_hash_path = self.flow_root / "workflow_state.sha256"
        self.plan_service = ExperimentPlanService(
            self.workspace_root / "outputs/ui_plans"
        )

    def _load_plan(self, directory: str | Path) -> SavedPlanRevision:
        return self.plan_service.load_revision(directory)

    def _source_commit(self) -> str:
        for candidate in (
            self.project_root / "build_manifest.json",
            self.project_root.parent / "build_manifest.json",
            self.project_root
            / "validation_assets/pre_experiment_acceptance/build_verification.json",
        ):
            if candidate.is_file():
                payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
                commit = payload.get("git_commit", payload.get("source_commit"))
                if isinstance(commit, str) and commit:
                    return commit
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.project_root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    @staticmethod
    def _stimulus_contract(saved: SavedPlanRevision) -> tuple[str, str, int, int]:
        contracts = {
            (
                str(sample.stimulus_id),
                str(sample.tone_set_id),
                int(sample.sample_rate_hz or 0),
                int(sample.audio_channel or 0),
            )
            for sample in saved.samples
            if sample.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE
        }
        if len(contracts) != 1 or len(saved.samples) != sum(
            sample.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE
            for sample in saved.samples
        ):
            raise ValueError(
                "simulated flow requires one explicit multisine stimulus contract"
            )
        stimulus_id, tone_set_id, sample_rate_hz, audio_channel = next(
            iter(contracts)
        )
        if not stimulus_id or stimulus_id == "None" or not tone_set_id or tone_set_id == "None":
            raise ValueError("plan multisine stimulus_id and tone_set_id are required")
        if sample_rate_hz <= 0 or audio_channel < 0:
            raise ValueError("plan multisine sample rate/channel are invalid")
        return stimulus_id, tone_set_id, sample_rate_hz, audio_channel

    def _read_state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {
                "schema_version": SIMULATED_FLOW_SCHEMA_VERSION,
                "route": "simulated_practice",
                "data_origin": "simulated",
                "dataset_role": "software_validation",
                "run_purpose": "software_validation",
                "scientifically_eligible": False,
                "final_test_read": False,
                "steps": {},
                "artifacts": {},
            }
        if not self.state_hash_path.is_file():
            raise FileNotFoundError(self.state_hash_path)
        expected = self.state_hash_path.read_text(encoding="ascii").strip()
        if artifact_sha256(self.state_path) != expected:
            raise ValueError("simulated workflow state hash mismatch")
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SIMULATED_FLOW_SCHEMA_VERSION:
            raise ValueError("unsupported simulated workflow state schema")
        return payload

    def _write_state(self, payload: Mapping[str, Any]) -> None:
        self.flow_root.mkdir(parents=True, exist_ok=True)
        value = dict(payload)
        value["updated_at_utc"] = datetime.now(UTC).isoformat()
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
        self.state_hash_path.write_text(
            artifact_sha256(self.state_path), encoding="ascii"
        )

    def bind_plan(self, directory: str | Path) -> SavedPlanRevision:
        saved = self._load_plan(directory)
        state = self._read_state()
        previous_plan = state.get("plan_revision_path")
        plan_changed = bool(previous_plan and previous_plan != saved.directory.as_posix())
        if plan_changed:
            # A new immutable revision supersedes UI workflow pointers only.  Raw
            # artifacts remain untouched and can never be claimed by the new plan.
            state["artifacts"] = {}
            state.pop("closeout", None)
            preserved = {
                key: value
                for key, value in dict(state.get("steps", {})).items()
                if key in {"environment", "usage"}
            }
            state["steps"] = {
                **preserved,
                "plan": (
                    "passed" if saved.checklist.ready_for_acquisition else "warning"
                ),
                "stimulus": "ready",
                "external_acquisition": "not_started",
                "single_measurement": "not_started",
                "dataset_qc": "not_started",
                "comparison": "not_started",
                "modeling": "not_started",
                "freeze": "not_started",
                "final_test": "not_started",
                "reports": "not_started",
            }
        state["plan_revision_path"] = saved.directory.as_posix()
        state["plan_manifest_sha256"] = artifact_sha256(
            saved.directory / "plan_manifest.json"
        )
        state["expected_sample_count"] = len(saved.samples)
        if not plan_changed:
            state["steps"] = {
                **dict(state.get("steps", {})),
                "plan": "passed" if saved.checklist.ready_for_acquisition else "warning",
                **(
                    {"stimulus": "ready"}
                    if "stimulus" not in dict(state.get("steps", {}))
                    else {}
                ),
            }
        self._write_state(state)
        return saved

    def generate_stimulus(self, plan_revision: str | Path) -> StimulusFlowArtifacts:
        saved = self._load_plan(plan_revision)
        stimulus_id, tone_set_id, sample_rate_hz, _ = self._stimulus_contract(saved)
        resolved = load_config(
            self.project_root / "config/stimulus_multisine_broadband.yaml",
            default_path=self.project_root / "config/default.yaml",
        )
        stimulus = dict(resolved["stimulus"])
        expected = {
            "stimulus_id": stimulus_id,
            "tone_set_id": tone_set_id,
            "sample_rate_hz": sample_rate_hz,
        }
        actual = {name: stimulus.get(name) for name in expected}
        if actual != expected:
            field = next(name for name in expected if actual[name] != expected[name])
            raise ValueError(
                "plan/P7 stimulus contract mismatch: "
                f"field={field} expected={expected[field]!r} actual={actual[field]!r}"
            )
        directory = self.flow_root / "stimuli" / stimulus_id
        hashes_path = directory / "artifact_hashes.json"
        if directory.exists():
            if not hashes_path.is_file():
                raise FileExistsError(
                    f"stimulus ID already has incomplete or different content: {directory}"
                )
            payload = json.loads(hashes_path.read_text(encoding="utf-8"))
            # The immutable stimulus may be reused by a newer plan revision only
            # when its P7 contract and every recorded artifact hash still match.
            # Keep the original creation binding unchanged for provenance.
            records = tuple(payload.get("artifacts", ()))
            required_names = {
                "stimulus.wav", "stimulus_manifest.json", "tones.csv",
                "stimulus_preview.png", "waveform_hash.txt",
            }
            if {Path(str(item.get("path"))).name for item in records} != required_names:
                raise ValueError("stimulus artifact hash index is incomplete")
            for record in records:
                path = directory / str(record["path"])
                if not path.is_file() or artifact_sha256(path) != str(record["sha256"]):
                    raise ValueError(f"stimulus artifact hash mismatch: {path}")
        else:
            generated = generate_multisine(
                stimulus,
                self.flow_root / "stimuli",
                overwrite=False,
            )
            primary = (
                generated.wav_path,
                generated.manifest_path,
                generated.tones_path,
                generated.preview_path,
                generated.hash_path,
            )
            payload = {
                "schema_version": SIMULATED_FLOW_SCHEMA_VERSION,
                "step": "04_stimulus",
                "plan_revision_path": saved.directory.as_posix(),
                "plan_manifest_sha256": artifact_sha256(
                    saved.directory / "plan_manifest.json"
                ),
                "data_origin": "simulated",
                "run_purpose": "software_validation",
                "scientifically_eligible": False,
                "artifacts": [
                    {
                        "path": path.relative_to(directory).as_posix(),
                        "sha256": artifact_sha256(path),
                    }
                    for path in primary
                ],
            }
            hashes_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
        manifest_path = directory / "stimulus_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if any(str(manifest[name]) != str(value) for name, value in expected.items()):
            raise ValueError("generated stimulus manifest does not match plan contract")
        result = StimulusFlowArtifacts(
            directory=directory.resolve(),
            wav_path=(directory / "stimulus.wav").resolve(),
            manifest_path=manifest_path.resolve(),
            tones_path=(directory / "tones.csv").resolve(),
            hashes_path=hashes_path.resolve(),
            waveform_sha256=str(manifest["waveform_sha256"]),
        )
        state = self._read_state()
        state.update(
            plan_revision_path=saved.directory.as_posix(),
            plan_manifest_sha256=artifact_sha256(saved.directory / "plan_manifest.json"),
            expected_sample_count=len(saved.samples),
        )
        state["artifacts"] = {
            **dict(state.get("artifacts", {})),
            "stimulus_hashes": {
                "path": hashes_path.resolve().as_posix(),
                "sha256": artifact_sha256(hashes_path),
            },
        }
        state["steps"] = {
            **dict(state.get("steps", {})),
            "plan": "passed" if saved.checklist.ready_for_acquisition else "warning",
            "stimulus": "passed",
        }
        self._write_state(state)
        return result

    def generate_simulated_acquisition(
        self,
        plan_revision: str | Path,
        stimulus_manifest: str | Path,
        *,
        random_state: int = 20260813,
        recording_delay_samples: int = 1379,
        additive_noise_std: float = 2.0e-5,
    ) -> SimulatedAcquisitionBatch:
        """Generate exactly the samples in one immutable plan revision."""
        saved = self._load_plan(plan_revision)
        stimulus = Path(stimulus_manifest).resolve()
        expected_stimulus = self.generate_stimulus(saved.directory)
        if stimulus != expected_stimulus.manifest_path:
            raise ValueError("stimulus manifest is not the one bound to this plan")
        stimulus_payload = json.loads(stimulus.read_text(encoding="utf-8"))
        stimulus_id, tone_set_id, sample_rate_hz, audio_channel = (
            self._stimulus_contract(saved)
        )
        contract = {
            "stimulus_id": stimulus_id,
            "tone_set_id": tone_set_id,
            "sample_rate_hz": sample_rate_hz,
        }
        if any(stimulus_payload.get(key) != value for key, value in contract.items()):
            raise ValueError("stimulus manifest/plan contract mismatch")
        plan_hash = artifact_sha256(saved.directory / "plan_manifest.json")
        batch_id = f"batch-{plan_hash[:12]}-seed-{int(random_state)}"
        directory = self.flow_root / "acquisitions" / batch_id
        manifest_path = directory / "acquisition_manifest.json"
        manifest_hash_path = directory / "acquisition_manifest.sha256"
        if directory.exists():
            if not manifest_path.is_file() or not manifest_hash_path.is_file():
                raise FileExistsError(f"existing acquisition is incomplete: {directory}")
            return self.load_acquisition_batch(manifest_path)

        directory.mkdir(parents=True, exist_ok=False)
        tone_rows: list[dict[str, str]] = []
        with expected_stimulus.tones_path.open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            tone_rows = list(csv.DictReader(handle))
        tone_frequency = np.asarray(
            [float(row["frequency_hz"]) for row in tone_rows], dtype=np.float64
        )
        records: list[dict[str, Any]] = []
        ordered_samples = tuple(sorted(saved.samples, key=lambda item: item.sample_id))
        for index, expected in enumerate(ordered_samples):
            if (
                expected.measurement_mode is not MeasurementMode.SCHROEDER_MULTISINE
                or expected.stimulus_id != stimulus_id
                or expected.tone_set_id != tone_set_id
                or expected.sample_rate_hz != sample_rate_hz
                or expected.audio_channel != audio_channel
            ):
                raise ValueError(
                    f"sample identity/stimulus contract mismatch: {expected.sample_id}"
                )
            sample_directory = directory / "samples" / expected.sample_id
            sample_directory.mkdir(parents=True, exist_ok=False)
            recording_path = sample_directory / "recording.wav"
            sidecar_path = sample_directory / "sidecar.json"
            truth_path = sample_directory / "known_transfer.csv"
            actual_rate, recording = simulate_multisine_recording_waveform(
                expected_stimulus.wav_path,
                stimulus_payload,
                angle_deg=expected.angle_deg,
                configuration=expected.configuration_id,
                random_state=int(random_state) + index,
                recording_delay_samples=recording_delay_samples,
                additive_noise_std=additive_noise_std,
            )
            if actual_rate != sample_rate_hz:
                raise ValueError("S3 recording sample rate differs from plan")
            if audio_channel:
                channels = np.zeros(
                    (recording.size, audio_channel + 1), dtype=np.float32
                )
                channels[:, audio_channel] = recording.astype(np.float32)
                wav_values = channels
            else:
                wav_values = recording.astype(np.float32)
            wavfile.write(recording_path, actual_rate, wav_values)
            recording_hash = artifact_sha256(recording_path)
            transfer = known_transfer_db(
                tone_frequency,
                angle_deg=expected.angle_deg,
                configuration=expected.configuration_id,
            )
            with truth_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("frequency_hz", "known_transfer_db"))
                writer.writerows(zip(tone_frequency, transfer, strict=True))
            metadata = MeasurementMeta(
                sample_id=expected.sample_id,
                **SCHEMA_VERSION_QUARTET,
                device_version=saved.plan.device_version,
                configuration=expected.configuration_id,
                angle_deg=expected.angle_deg,
                session_id=expected.session_id,
                repeat_type=expected.repeat_type,
                repeat_id=expected.repeat_id,
                reposition_round_id=expected.reposition_round_id,
                assembly_id=expected.assembly_id,
                acquisition_block_id=expected.acquisition_block_id,
                experiment_step="DEV_UI4_FIX6_SIMULATED_ACQUISITION",
                measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
                stimulus_id=stimulus_id,
                stimulus_hash=expected_stimulus.waveform_sha256,
                tone_set_id=tone_set_id,
                source_format=SourceFormat.MOCK_AUDIO,
                source_path=recording_path.resolve().as_posix(),
                data_origin=DataOrigin.SIMULATED,
                dataset_role=DatasetRole.SOFTWARE_VALIDATION,
                source_sha256=recording_hash,
                provenance_uri=manifest_path.resolve().as_posix(),
                eligible_for_scientific_analysis=False,
                sidecar_path=sidecar_path.resolve().as_posix(),
                date_time=datetime.fromisoformat(saved.plan.created_at),
                audio_channel=audio_channel,
                qc_status=QCStatus.VALID,
            )
            sidecar_payload = {
                **metadata.to_dict(),
                "mock_only": True,
                "run_purpose": "software_validation",
                "sample_rate_hz": actual_rate,
                "period_samples": int(stimulus_payload["period_samples"]),
                "stable_period_count": int(
                    stimulus_payload["stable_period_count"]
                ),
                "discard_initial_period_count": int(
                    stimulus_payload["discard_initial_period_count"]
                ),
                "recording_delay_samples": int(recording_delay_samples),
                "sampling_clock_drift_ppm": 0.0,
                "recording_wav_format": "float32",
                "additive_noise_std": float(additive_noise_std),
                "common_sampling_clock": False,
                "stimulus_manifest": stimulus.as_posix(),
                "recording_sha256": recording_hash,
                "known_transfer_csv": truth_path.resolve().as_posix(),
            }
            sidecar_path.write_text(
                json.dumps(
                    sidecar_payload, indent=2, sort_keys=True, ensure_ascii=False
                )
                + "\n",
                encoding="utf-8",
            )
            records.append(
                {
                    "expected_sample": expected.to_dict(),
                    "recording_path": recording_path.relative_to(directory).as_posix(),
                    "recording_sha256": recording_hash,
                    "sidecar_path": sidecar_path.relative_to(directory).as_posix(),
                    "sidecar_sha256": artifact_sha256(sidecar_path),
                    "known_transfer_path": truth_path.relative_to(directory).as_posix(),
                    "known_transfer_sha256": artifact_sha256(truth_path),
                }
            )
        manifest_payload = {
            **SCHEMA_VERSION_QUARTET,
            "simulated_flow_schema_version": SIMULATED_FLOW_SCHEMA_VERSION,
            "batch_id": batch_id,
            "status": "completed",
            "plan_revision_path": saved.directory.as_posix(),
            "plan_manifest_sha256": plan_hash,
            "stimulus_manifest_path": stimulus.as_posix(),
            "stimulus_manifest_sha256": artifact_sha256(stimulus),
            "stimulus_waveform_sha256": expected_stimulus.waveform_sha256,
            "expected_sample_count": len(saved.samples),
            "generated_sample_count": len(records),
            "data_origin": "simulated",
            "dataset_role": "software_validation",
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
            "final_test_read": False,
            "random_state": int(random_state),
            "recording_delay_samples": int(recording_delay_samples),
            "samples": records,
        }
        manifest_path.write_text(
            json.dumps(
                manifest_payload, indent=2, sort_keys=True, ensure_ascii=False
            )
            + "\n",
            encoding="utf-8",
        )
        manifest_hash_path.write_text(
            artifact_sha256(manifest_path), encoding="ascii"
        )
        result = self.load_acquisition_batch(manifest_path)
        state = self._read_state()
        state["artifacts"] = {
            **dict(state.get("artifacts", {})),
            "acquisition_manifest": {
                "path": manifest_path.resolve().as_posix(),
                "sha256": artifact_sha256(manifest_path),
            },
        }
        state["steps"] = {
            **dict(state.get("steps", {})),
            "external_acquisition": "passed",
        }
        self._write_state(state)
        return result

    def load_acquisition_batch(
        self, manifest_path: str | Path
    ) -> SimulatedAcquisitionBatch:
        """Verify one explicit batch manifest and all of its declared assets."""
        manifest = Path(manifest_path).resolve()
        hash_path = manifest.with_suffix(".sha256")
        if not manifest.is_file() or not hash_path.is_file():
            raise FileNotFoundError(f"acquisition manifest/hash missing: {manifest}")
        if artifact_sha256(manifest) != hash_path.read_text(encoding="ascii").strip():
            raise ValueError("acquisition manifest hash mismatch")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if payload.get("simulated_flow_schema_version") != SIMULATED_FLOW_SCHEMA_VERSION:
            raise ValueError("unsupported acquisition manifest schema")
        if (
            payload.get("status") != "completed"
            or payload.get("data_origin") != "simulated"
            or payload.get("dataset_role") != "software_validation"
            or payload.get("run_purpose") != "software_validation"
            or payload.get("scientifically_eligible") is not False
            or payload.get("final_test_read") is not False
        ):
            raise ValueError("acquisition provenance/status hard gate failed")
        saved = self._load_plan(payload["plan_revision_path"])
        if artifact_sha256(saved.directory / "plan_manifest.json") != payload.get(
            "plan_manifest_sha256"
        ):
            raise ValueError("acquisition plan hash mismatch")
        rows = list(payload.get("samples", ()))
        expected_by_id = {sample.sample_id: sample for sample in saved.samples}
        actual_ids = [str(row.get("expected_sample", {}).get("sample_id")) for row in rows]
        if (
            len(actual_ids) != len(set(actual_ids))
            or set(actual_ids) != set(expected_by_id)
            or payload.get("expected_sample_count") != len(expected_by_id)
            or payload.get("generated_sample_count") != len(rows)
        ):
            raise ValueError("acquisition sample set is missing, duplicate, or unexpected")
        directory = manifest.parent
        for row in rows:
            expected = expected_by_id[str(row["expected_sample"]["sample_id"])]
            if row["expected_sample"] != expected.to_dict():
                raise ValueError(f"sample identity mismatch: {expected.sample_id}")
            for path_key, hash_key in (
                ("recording_path", "recording_sha256"),
                ("sidecar_path", "sidecar_sha256"),
                ("known_transfer_path", "known_transfer_sha256"),
            ):
                path = (directory / str(row[path_key])).resolve()
                if not path.is_file() or artifact_sha256(path) != row[hash_key]:
                    raise ValueError(f"acquisition artifact hash mismatch: {path}")
            sidecar_path = directory / str(row["sidecar_path"])
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            metadata = MeasurementMeta.from_dict(
                {key: sidecar[key] for key in MeasurementMeta.__dataclass_fields__}
            )
            if (
                metadata.sample_id != expected.sample_id
                or metadata.configuration != expected.configuration_id
                or metadata.angle_deg != expected.angle_deg
                or metadata.session_id != expected.session_id
                or metadata.repeat_type != expected.repeat_type
                or metadata.repeat_id != expected.repeat_id
                or metadata.reposition_round_id != expected.reposition_round_id
                or metadata.assembly_id != expected.assembly_id
                or metadata.acquisition_block_id != expected.acquisition_block_id
                or metadata.source_sha256 != row["recording_sha256"]
                or metadata.data_origin is not DataOrigin.SIMULATED
                or metadata.eligible_for_scientific_analysis
            ):
                raise ValueError(f"sidecar identity/provenance mismatch: {expected.sample_id}")
        return SimulatedAcquisitionBatch(
            directory=directory,
            manifest_path=manifest,
            manifest_hash_path=hash_path,
            sample_count=len(rows),
        )

    def process_simulated_batch(
        self,
        acquisition_manifest: str | Path,
        *,
        processing_id: str | None = None,
        cancel_requested: Callable[[], bool] | None = None,
        progress: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> SimulatedProcessingBatch:
        """Run P1/P8/P2-A for every explicitly declared acquisition row."""
        batch = self.load_acquisition_batch(acquisition_manifest)
        acquisition_hash = artifact_sha256(batch.manifest_path)
        identifier = processing_id or f"process-{acquisition_hash[:16]}"
        if Path(identifier).name != identifier or not identifier.strip():
            raise ValueError("processing_id must be one non-empty path component")
        directory = self.flow_root / "processing" / identifier
        if directory.exists():
            raise FileExistsError(f"processing output already exists: {directory}")
        directory.mkdir(parents=True, exist_ok=False)
        manifest_path = directory / "processing_manifest.json"
        hash_path = directory / "processing_manifest.sha256"
        acquisition = json.loads(batch.manifest_path.read_text(encoding="utf-8"))
        saved_plan = self._load_plan(acquisition["plan_revision_path"])
        expected_by_id = {sample.sample_id: sample for sample in saved_plan.samples}
        stimulus_manifest = Path(acquisition["stimulus_manifest_path"]).resolve()
        draft_service = MeasurementDraftService(
            self.project_root,
            workspace_root=self.workspace_root,
            source_commit=self._source_commit(),
        )
        rows: list[dict[str, Any]] = []
        warning_count = 0
        failed_count = 0
        cancelled = False
        first_failure: dict[str, Any] | None = None

        for index, record in enumerate(acquisition["samples"], start=1):
            if cancel_requested is not None and cancel_requested():
                cancelled = True
                break
            expected = expected_by_id[record["expected_sample"]["sample_id"]]
            current = {
                "event": "sample_started",
                "current": index,
                "total": len(acquisition["samples"]),
                "sample_id": expected.sample_id,
            }
            if progress is not None:
                progress(current)
            try:
                recording = batch.directory / record["recording_path"]
                preflight = draft_service.preflight_multisine(
                    recording,
                    stimulus_manifest,
                    audio_channel=int(expected.audio_channel or 0),
                    expected_stimulus_id=expected.stimulus_id,
                    expected_stimulus_hash=acquisition["stimulus_waveform_sha256"],
                    expected_tone_set_id=expected.tone_set_id,
                )
                form = MetadataFormValues(
                    device_version=saved_plan.plan.device_version,
                    configuration=expected.configuration_id,
                    angle_deg=expected.angle_deg,
                    session_id=expected.session_id,
                    repeat_type=expected.repeat_type,
                    repeat_id=expected.repeat_id,
                    reposition_round_id=expected.reposition_round_id,
                    assembly_id=expected.assembly_id,
                    acquisition_block_id=expected.acquisition_block_id,
                    experiment_step="DEV_UI4_FIX6_SIMULATED_PROCESSING",
                    date_time=saved_plan.plan.created_at,
                    audio_channel=expected.audio_channel,
                    provenance_uri=batch.manifest_path.as_posix(),
                )
                draft = draft_service.build_draft(
                    route=UsageRoute.SIMULATED_PRACTICE,
                    measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
                    preflight=preflight,
                    form=form,
                )
                run_digest = hashlib.sha256(
                    f"{acquisition_hash}:{expected.sample_id}".encode("utf-8")
                ).hexdigest()
                metadata_filename = f"{expected.sample_id}.sidecar.json"
                session_directory = (
                    self.workspace_root
                    / "outputs/ui_sessions"
                    / expected.sample_id
                    / "rev-001"
                )
                metadata = replace(
                    draft.metadata,
                    sample_id=expected.sample_id,
                    sidecar_path=(session_directory / metadata_filename).as_posix(),
                )
                draft = replace(
                    draft,
                    sample_id=expected.sample_id,
                    run_id=f"u6-{run_digest[:16]}",
                    metadata_filename=metadata_filename,
                    sidecar_filename=metadata_filename,
                    session_directory=session_directory,
                    metadata_path=session_directory / metadata_filename,
                    metadata=metadata,
                )
                saved = draft_service.save_draft(draft)
                resolved = load_config(saved.config_snapshot_path)
                result = execute_measurement_run(
                    recording,
                    saved.metadata_path,
                    resolved,
                    output_root=self.workspace_root / "outputs/ui_pipeline_runs",
                    run_id=saved.draft.run_id,
                    stimulus_manifest=stimulus_manifest,
                )
                draft_service.record_run_result(
                    saved,
                    output_directory=result.output_directory,
                    status=("completed" if result.processing_status == "completed" else "failed"),
                    program="acoustic_encoder.run_execution.execute_measurement_run",
                    arguments=(recording.as_posix(), saved.metadata_path.as_posix()),
                    exit_code=0 if result.processing_status == "completed" else 1,
                    stdout=json.dumps(dict(result.run_manifest), ensure_ascii=False),
                    stderr="" if result.processing_status == "completed" else str(result.run_manifest.get("failure")),
                )
                session_manifest = saved.session_directory / "ui_session_manifest.json"
                spectrum_json = result.output_directory / "spectrum_data.json"
                spectrum_npz = result.output_directory / "spectrum_data.npz"
                if not spectrum_json.is_file() or not spectrum_npz.is_file():
                    raise FileNotFoundError("P8 sparse SpectrumData serialization is missing")
                qc = str(result.run_manifest.get("qc_status", "unavailable"))
                if qc == "warning":
                    warning_count += 1
                if result.processing_status != "completed":
                    failed_count += 1
                rows.append(
                    {
                        "sample_id": expected.sample_id,
                        "expected_sample": expected.to_dict(),
                        "status": result.processing_status,
                        "qc_status": qc,
                        "ui_session_manifest_path": session_manifest.resolve().as_posix(),
                        "ui_session_manifest_sha256": artifact_sha256(session_manifest),
                        "output_directory": result.output_directory.resolve().as_posix(),
                        "run_manifest_sha256": artifact_sha256(
                            result.output_directory / "run_manifest.json"
                        ),
                        "spectrum_json_sha256": artifact_sha256(spectrum_json),
                        "spectrum_npz_sha256": artifact_sha256(spectrum_npz),
                        "feature_set_status": "not_applicable_sparse",
                        "scientifically_eligible": False,
                    }
                )
            except Exception as error:  # per-sample audit boundary
                failed_count += 1
                first_failure = {
                    "sample_id": expected.sample_id,
                    "exception_type": type(error).__name__,
                    "message": str(error),
                }
                rows.append(
                    {
                        "sample_id": expected.sample_id,
                        "expected_sample": expected.to_dict(),
                        "status": "failed",
                        "failure": first_failure,
                        "feature_set_status": "not_applicable_sparse",
                        "scientifically_eligible": False,
                    }
                )
                break
            if progress is not None:
                progress(
                    {
                        "event": "sample_finished",
                        "current": index,
                        "total": len(acquisition["samples"]),
                        "sample_id": expected.sample_id,
                        "warning_count": warning_count,
                        "failed_count": failed_count,
                    }
                )
        status = (
            "cancelled"
            if cancelled
            else "failed"
            if failed_count
            else "passed"
            if len(rows) == len(acquisition["samples"])
            else "failed"
        )
        payload = {
            **SCHEMA_VERSION_QUARTET,
            "simulated_flow_schema_version": SIMULATED_FLOW_SCHEMA_VERSION,
            "processing_id": identifier,
            "status": status,
            "cancelled": cancelled,
            "acquisition_manifest_path": batch.manifest_path.as_posix(),
            "acquisition_manifest_sha256": acquisition_hash,
            "plan_revision_path": saved_plan.directory.as_posix(),
            "plan_manifest_sha256": acquisition["plan_manifest_sha256"],
            "expected_sample_count": len(saved_plan.samples),
            "processed_sample_count": len(rows),
            "registered_sample_count": sum(
                "ui_session_manifest_path" in row for row in rows
            ),
            "warning_count": warning_count,
            "failed_count": failed_count,
            "failure": first_failure,
            "data_origin": "simulated",
            "dataset_role": "software_validation",
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
            "final_test_read": False,
            "samples": rows,
        }
        manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        hash_path.write_text(artifact_sha256(manifest_path), encoding="ascii")
        state = self._read_state()
        state["artifacts"] = {
            **dict(state.get("artifacts", {})),
            "processing_manifest": {
                "path": manifest_path.resolve().as_posix(),
                "sha256": artifact_sha256(manifest_path),
            },
        }
        state["steps"] = {
            **dict(state.get("steps", {})),
            "single_measurement": status,
        }
        self._write_state(state)
        return SimulatedProcessingBatch(
            directory=directory,
            manifest_path=manifest_path,
            manifest_hash_path=hash_path,
            status=status,
            processed_count=len(rows),
        )

    def verify_processed_dataset(
        self,
        processing_manifest: str | Path,
        *,
        audit_id: str | None = None,
    ) -> SimulatedDatasetAudit:
        """Audit the one explicit processing registration; never discover outputs."""
        manifest = Path(processing_manifest).resolve()
        digest_path = manifest.with_suffix(".sha256")
        if not manifest.is_file() or not digest_path.is_file():
            raise FileNotFoundError(f"processing manifest/hash missing: {manifest}")
        if artifact_sha256(manifest) != digest_path.read_text(encoding="ascii").strip():
            raise ValueError("processing manifest hash mismatch")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if (
            payload.get("simulated_flow_schema_version") != SIMULATED_FLOW_SCHEMA_VERSION
            or payload.get("status") != "passed"
            or payload.get("data_origin") != "simulated"
            or payload.get("dataset_role") != "software_validation"
            or payload.get("run_purpose") != "software_validation"
            or payload.get("scientifically_eligible") is not False
            or payload.get("final_test_read") is not False
        ):
            raise ValueError("processing manifest status/provenance gate failed")
        acquisition = self.load_acquisition_batch(payload["acquisition_manifest_path"])
        if artifact_sha256(acquisition.manifest_path) != payload.get(
            "acquisition_manifest_sha256"
        ):
            raise ValueError("processing/acquisition hash mismatch")
        saved_plan = self._load_plan(payload["plan_revision_path"])
        expected_by_id = {item.sample_id: item for item in saved_plan.samples}
        rows = list(payload.get("samples", ()))
        actual_ids = [str(row.get("sample_id")) for row in rows]
        duplicate_ids = sorted(
            identifier for identifier in set(actual_ids) if actual_ids.count(identifier) > 1
        )
        if duplicate_ids:
            raise ValueError(f"duplicate processed sample identity: {duplicate_ids}")
        missing_ids = sorted(set(expected_by_id).difference(actual_ids))
        unexpected_ids = sorted(set(actual_ids).difference(expected_by_id))
        if missing_ids:
            raise ValueError(f"missing processed samples: {missing_ids}")
        if unexpected_ids:
            raise ValueError(f"unexpected processed samples: {unexpected_ids}")
        if (
            payload.get("expected_sample_count") != len(expected_by_id)
            or payload.get("registered_sample_count") != len(rows)
        ):
            raise ValueError("processing registration counts do not match the plan")

        registry = SampleRegistry(self.flow_root / "dataset_registry")
        registrations = []
        qc_counts = {"valid": 0, "warning": 0, "exclude_candidate": 0, "unavailable": 0}
        for row in rows:
            expected = expected_by_id[row["sample_id"]]
            if row.get("expected_sample") != expected.to_dict():
                raise ValueError(f"processed sample identity mismatch: {expected.sample_id}")
            if row.get("feature_set_status") != "not_applicable_sparse":
                raise ValueError("sparse multisine must not claim a dense FeatureSet")
            session_manifest = Path(row["ui_session_manifest_path"]).resolve()
            if artifact_sha256(session_manifest) != row["ui_session_manifest_sha256"]:
                raise ValueError(f"UI session hash mismatch: {expected.sample_id}")
            output = Path(row["output_directory"]).resolve()
            run_manifest = output / "run_manifest.json"
            if artifact_sha256(run_manifest) != row["run_manifest_sha256"]:
                raise ValueError(f"run manifest hash mismatch: {expected.sample_id}")
            spectrum_json = output / "spectrum_data.json"
            spectrum_npz = output / "spectrum_data.npz"
            if (
                artifact_sha256(spectrum_json) != row["spectrum_json_sha256"]
                or artifact_sha256(spectrum_npz) != row["spectrum_npz_sha256"]
            ):
                raise ValueError(f"SpectrumData hash mismatch: {expected.sample_id}")
            if (output / "processed").exists():
                raise ValueError("sparse multisine output unexpectedly contains dense features")
            registered = registry.register_ui2_session(
                session_manifest,
                expected=expected,
                output_directory=output,
            )
            if not registered.spectrum_data_available or registered.feature_set_available:
                raise ValueError(
                    f"sparse artifact contract mismatch: {expected.sample_id}"
                )
            registrations.append(registered)
            qc = registered.qc_status or "unavailable"
            qc_counts[qc] = qc_counts.get(qc, 0) + 1
        matched = registry.match(saved_plan.samples, registrations)
        match_counts = {status.value: 0 for status in MatchStatus}
        for row in matched.rows:
            match_counts[row.status.value] += 1
        complete_count = match_counts[MatchStatus.EXPECTED_AND_PRESENT.value]
        if not matched.complete or complete_count != len(saved_plan.samples):
            raise ValueError(f"dataset match is incomplete: {match_counts}")
        status = (
            "failed"
            if qc_counts.get("exclude_candidate", 0)
            else "warning"
            if qc_counts.get("warning", 0) or qc_counts.get("unavailable", 0)
            else "passed"
        )
        selected_id = audit_id or f"dataset-{artifact_sha256(manifest)[:16]}"
        if Path(selected_id).name != selected_id or not selected_id.strip():
            raise ValueError("audit_id must be one non-empty path component")
        directory = self.flow_root / "dataset_audits" / selected_id
        if directory.exists():
            raise FileExistsError(f"dataset audit already exists: {directory}")
        directory.mkdir(parents=True, exist_ok=False)
        audit_manifest = directory / "dataset_flow_manifest.json"
        audit_hash = directory / "dataset_flow_manifest.sha256"
        audit_payload = {
            **SCHEMA_VERSION_QUARTET,
            "simulated_flow_schema_version": SIMULATED_FLOW_SCHEMA_VERSION,
            "audit_id": selected_id,
            "status": status,
            "processing_manifest_path": manifest.as_posix(),
            "processing_manifest_sha256": artifact_sha256(manifest),
            "plan_revision_path": saved_plan.directory.as_posix(),
            "plan_manifest_sha256": payload["plan_manifest_sha256"],
            "expected_count": len(saved_plan.samples),
            "expected_and_present_count": complete_count,
            "missing_count": match_counts[MatchStatus.EXPECTED_BUT_MISSING.value],
            "duplicate_count": match_counts[MatchStatus.DUPLICATE_IDENTITY.value],
            "unexpected_count": match_counts[MatchStatus.UNEXPECTED_SAMPLE.value],
            "metadata_mismatch_count": match_counts[MatchStatus.METADATA_MISMATCH.value],
            "hash_mismatch_count": match_counts[MatchStatus.HASH_MISMATCH.value],
            "qc_counts": qc_counts,
            "p2_b_status": "not_applicable_sparse",
            "p2_b_reason": "P2-B requires compatible FeatureSet; this plan contains authoritative sparse P8 tones",
            "downstream_route": "tone_p8_dataset_quality",
            "data_origin": "simulated",
            "dataset_role": "software_validation",
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
            "final_test_read": False,
            "registrations": [
                {
                    "sample_id": item.source_sample_id,
                    "registration_id": item.registration_id,
                    "session_manifest_path": item.session_manifest_path.as_posix(),
                    "session_manifest_sha256": artifact_sha256(item.session_manifest_path),
                    "output_directory": item.output_directory.as_posix(),
                    "qc_status": item.qc_status,
                    "spectrum_data_available": item.spectrum_data_available,
                    "feature_set_available": item.feature_set_available,
                }
                for item in registrations
            ],
        }
        audit_manifest.write_text(
            json.dumps(audit_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        audit_hash.write_text(artifact_sha256(audit_manifest), encoding="ascii")
        state = self._read_state()
        state["artifacts"] = {
            **dict(state.get("artifacts", {})),
            "dataset_audit": {
                "path": audit_manifest.resolve().as_posix(),
                "sha256": artifact_sha256(audit_manifest),
            },
        }
        state["steps"] = {
            **dict(state.get("steps", {})),
            "dataset_qc": status,
        }
        self._write_state(state)
        return SimulatedDatasetAudit(
            directory=directory,
            manifest_path=audit_manifest,
            manifest_hash_path=audit_hash,
            status=status,
        )

    def load_state(self) -> dict[str, Any]:
        """Load the one explicit state pointer; never search output directories."""
        return self._read_state()

    def record_ui_step(self, step_id: str, status: str) -> None:
        """Persist presentation state without granting scientific authority."""
        if step_id not in {
            "environment", "usage", "plan", "stimulus", "external_acquisition",
            "single_measurement", "dataset_qc",
        }:
            raise ValueError(f"unsupported persisted UI step: {step_id}")
        state = self._read_state()
        state["steps"] = {**dict(state.get("steps", {})), step_id: status}
        self._write_state(state)

    def load_dataset_audit(self, manifest_path: str | Path) -> SimulatedDatasetAudit:
        manifest = Path(manifest_path).resolve()
        digest = manifest.with_suffix(".sha256")
        if not manifest.is_file() or not digest.is_file():
            raise FileNotFoundError(f"dataset audit manifest/hash missing: {manifest}")
        if artifact_sha256(manifest) != digest.read_text(encoding="ascii").strip():
            raise ValueError("dataset audit manifest hash mismatch")
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if (
            payload.get("simulated_flow_schema_version") != SIMULATED_FLOW_SCHEMA_VERSION
            or payload.get("data_origin") != "simulated"
            or payload.get("dataset_role") != "software_validation"
            or payload.get("scientifically_eligible") is not False
            or payload.get("final_test_read") is not False
        ):
            raise ValueError("dataset audit provenance gate failed")
        return SimulatedDatasetAudit(
            directory=manifest.parent,
            manifest_path=manifest,
            manifest_hash_path=digest,
            status=str(payload["status"]),
        )

    def apply_sparse_closeout(self, audit_manifest: str | Path) -> dict[str, Any]:
        """Route one verified sparse-only audit to safe UI terminal states."""
        audit = self.load_dataset_audit(audit_manifest)
        payload = json.loads(audit.manifest_path.read_text(encoding="utf-8"))
        expected = int(payload.get("expected_count", -1))
        present = int(payload.get("expected_and_present_count", -1))
        qc_counts = dict(payload.get("qc_counts", {}))
        if (
            audit.status != "passed"
            or expected <= 0
            or present != expected
            or int(payload.get("missing_count", -1)) != 0
            or int(payload.get("duplicate_count", -1)) != 0
            or int(payload.get("unexpected_count", -1)) != 0
            or int(qc_counts.get("warning", -1)) != 0
            or int(qc_counts.get("exclude_candidate", -1)) != 0
            or payload.get("p2_b_status") != "not_applicable_sparse"
            or payload.get("downstream_route") != "tone_p8_dataset_quality"
        ):
            raise ValueError("dataset audit is not a clean sparse Multisine closeout")
        state = self._read_state()
        state["steps"] = {
            **dict(state.get("steps", {})),
            "comparison": "not_applicable",
            "modeling": "not_applicable",
            "freeze": "blocked",
            "final_test": "sealed",
            "reports": "ready",
        }
        state["artifacts"] = {
            **dict(state.get("artifacts", {})),
            "dataset_audit": {
                "path": audit.manifest_path.as_posix(),
                "sha256": artifact_sha256(audit.manifest_path),
            },
        }
        state["closeout"] = {
            "route": "sparse_multisine_software_validation",
            "p2_b_status": "not_applicable_sparse",
            "downstream_route": "tone_p8_dataset_quality",
            "comparison_reason": "no_canonical_p4_authority",
            "modeling_reason": "no_canonical_p5_p6_authority",
            "freeze_reason": "missing_approved_p9d_freeze_authority",
            "final_test_status": "sealed",
            "reports_status": "ready",
        }
        state["scientifically_eligible"] = False
        state["final_test_read"] = False
        self._write_state(state)
        return self._read_state()

    def export_software_validation_summary(
        self, *, report_id: str | None = None
    ) -> SoftwareValidationSummary:
        """Export a non-scientific summary from the one hashed state chain."""
        state = self._read_state()
        required_steps = {
            "environment": "passed",
            "usage": "passed",
            "plan": "passed",
            "stimulus": "passed",
            "external_acquisition": "passed",
            "single_measurement": "passed",
            "dataset_qc": "passed",
            "comparison": "not_applicable",
            "modeling": "not_applicable",
            "freeze": "blocked",
            "final_test": "sealed",
            "reports": "ready",
        }
        if any(state.get("steps", {}).get(key) != value for key, value in required_steps.items()):
            raise ValueError("workflow state is not ready for sparse validation closeout")
        if (
            state.get("data_origin") != "simulated"
            or state.get("run_purpose") != "software_validation"
            or state.get("scientifically_eligible") is not False
            or state.get("final_test_read") is not False
        ):
            raise ValueError("software validation provenance/final-test gate failed")

        saved = self._load_plan(state["plan_revision_path"])
        plan_manifest = saved.directory / "plan_manifest.json"
        if artifact_sha256(plan_manifest) != state.get("plan_manifest_sha256"):
            raise ValueError("workflow plan manifest hash mismatch")
        artifacts = dict(state.get("artifacts", {}))

        def reference(name: str) -> tuple[Path, str]:
            item = artifacts.get(name)
            if not isinstance(item, dict):
                raise ValueError(f"workflow state is missing explicit artifact: {name}")
            path = Path(str(item.get("path"))).resolve()
            expected_hash = str(item.get("sha256"))
            if not path.is_file() or artifact_sha256(path) != expected_hash:
                raise ValueError(f"workflow artifact hash mismatch: {name}")
            return path, expected_hash

        stimulus_hashes, _ = reference("stimulus_hashes")
        stimulus_index = json.loads(stimulus_hashes.read_text(encoding="utf-8"))
        stimulus_record = next(
            (
                item for item in stimulus_index.get("artifacts", ())
                if Path(str(item.get("path"))).name == "stimulus_manifest.json"
            ),
            None,
        )
        if stimulus_record is None:
            raise ValueError("stimulus hash index lacks stimulus_manifest.json")
        stimulus_manifest = (
            stimulus_hashes.parent / str(stimulus_record["path"])
        ).resolve()
        stimulus_hash = str(stimulus_record["sha256"])
        if artifact_sha256(stimulus_manifest) != stimulus_hash:
            raise ValueError("stimulus manifest hash mismatch")
        acquisition_manifest, acquisition_hash = reference("acquisition_manifest")
        processing_manifest, processing_hash = reference("processing_manifest")
        dataset_audit, audit_hash = reference("dataset_audit")
        processing = json.loads(processing_manifest.read_text(encoding="utf-8"))
        audit = json.loads(dataset_audit.read_text(encoding="utf-8"))
        if (
            audit.get("expected_count") != 32
            or audit.get("expected_and_present_count") != 32
            or audit.get("p2_b_status") != "not_applicable_sparse"
            or audit.get("downstream_route") != "tone_p8_dataset_quality"
            or int(processing.get("warning_count", -1)) != 0
            or int(processing.get("failed_count", -1)) != 0
        ):
            raise ValueError("explicit sparse manifests do not meet closeout counts")

        selected_id = report_id or (
            "summary-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        )
        if Path(selected_id).name != selected_id or not selected_id.strip():
            raise ValueError("report_id must be one non-empty path component")
        directory = self.flow_root / "closeout_reports" / selected_id
        if directory.exists():
            raise FileExistsError(f"software validation report exists: {directory}")
        directory.mkdir(parents=True, exist_ok=False)
        markdown = directory / "software_validation_summary.md"
        manifest = directory / "software_validation_summary.json"
        manifest_hash = directory / "software_validation_summary.sha256"
        artifact_rows = (
            ("workflow_state", self.state_path, artifact_sha256(self.state_path)),
            ("plan_manifest", plan_manifest, artifact_sha256(plan_manifest)),
            ("stimulus_manifest", stimulus_manifest, stimulus_hash),
            ("acquisition_manifest", acquisition_manifest, acquisition_hash),
            ("processing_manifest", processing_manifest, processing_hash),
            ("dataset_audit", dataset_audit, audit_hash),
        )
        step_rows = {
            "01_environment": "passed",
            "02_usage": "passed",
            "03_plan": "passed",
            "04_stimulus": "passed",
            "05_external_acquisition": "passed",
            "06_single_measurement": "passed",
            "07_dataset_qc": "passed",
            "08_comparison": "not_applicable",
            "09_modeling": "not_applicable",
            "10_freeze": "blocked",
            "11_final_test": "sealed",
            "12_reports": "ready",
        }
        markdown_text = (
            "# Sparse Multisine 软件验证总结\n\n"
            "> 仅用于 software_validation；不可用于科研结论。\n\n"
            + "## 步骤状态\n\n"
            + "\n".join(f"- {key}: `{value}`" for key, value in step_rows.items())
            + "\n\n## 数据集\n\n"
            + "- 32/32 expected_and_present\n- warning=0\n- failed=0\n"
            + f"- plan rev-{saved.revision:03d}\n"
            + "- P2-B=not_applicable_sparse\n"
            + "- downstream_route=tone_p8_dataset_quality\n\n"
            + "## Provenance 与安全边界\n\n"
            + "- data_origin=simulated\n- run_purpose=software_validation\n"
            + "- scientifically_eligible=false\n- final_test_read=false\n"
            + "- canonical/deployment/freeze authority：未授予\n\n"
            + "## 显式 artifacts\n\n"
            + "\n".join(
                f"- {role}: `{path.as_posix()}` — `{digest}`"
                for role, path, digest in artifact_rows
            )
            + "\n"
        )
        markdown.write_text(markdown_text, encoding="utf-8")
        payload = {
            "schema_version": "1.0.0",
            "report_id": selected_id,
            "report_kind": "sparse_multisine_software_validation_summary",
            "steps": step_rows,
            "plan": {
                "plan_id": saved.plan.plan_id,
                "revision": saved.revision,
                "revision_label": f"rev-{saved.revision:03d}",
                "path": saved.directory.as_posix(),
            },
            "dataset_counts": {
                "expected": 32,
                "expected_and_present": 32,
                "warning": 0,
                "failed": 0,
            },
            "p2_b_status": "not_applicable_sparse",
            "downstream_route": "tone_p8_dataset_quality",
            "data_origin": "simulated",
            "dataset_role": "software_validation",
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
            "eligible_for_research_conclusions": False,
            "canonical_analysis": False,
            "deployment_eligible": False,
            "freeze_authority_approved": False,
            "final_test_read": False,
            "warning": "不可用于科研结论。",
            "markdown": {
                "path": markdown.as_posix(),
                "sha256": artifact_sha256(markdown),
            },
            "artifacts": [
                {"role": role, "path": path.as_posix(), "sha256": digest}
                for role, path, digest in artifact_rows
            ],
        }
        manifest.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        manifest_hash.write_text(artifact_sha256(manifest), encoding="ascii")
        return SoftwareValidationSummary(
            directory=directory,
            markdown_path=markdown,
            manifest_path=manifest,
            manifest_hash_path=manifest_hash,
        )

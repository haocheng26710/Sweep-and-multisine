"""UI-owned import drafts that delegate validation to authoritative schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime
from enum import Enum
from html import escape
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from scipy.io import wavfile
import yaml

from acoustic_encoder.config import load_config
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    SourceFormat,
    artifact_sha256,
)
from acoustic_encoder.io_rew import REWPreflightResult, inspect_rew_frequency_response


class UsageRoute(str, Enum):
    SIMULATED_PRACTICE = "simulated_practice"
    OFFICIAL_REFERENCE = "official_reference"
    REAL_DIAGNOSTIC = "real_diagnostic"


REAL_MULTISINE_BLOCK_MESSAGE = (
    "当前 P8-A 后端只接受 simulated/software_validation。\n"
    "本录音已登记但尚未分析。请保留原始 WAV、manifest、sidecar\n"
    "和 hash，等待 DEV-D 真实 Multisine 门禁实现与批准。"
)


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    route: UsageRoute
    data_origin: DataOrigin
    dataset_role: DatasetRole
    run_purpose: str
    eligible_for_scientific_analysis: bool
    label: str


@dataclass(frozen=True, slots=True)
class AnalysisDecision:
    allowed: bool
    status: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class MetadataFormValues:
    device_version: str | None = None
    configuration: str | None = None
    angle_deg: str | float | None = None
    session_id: str | None = None
    repeat_type: str | None = None
    repeat_id: str | None = None
    reposition_round_id: str | None = None
    assembly_id: str | None = None
    acquisition_block_id: str | None = None
    experiment_step: str | None = None
    date_time: str | None = None
    audio_channel: int | None = None
    provenance_uri: str | None = None


@dataclass(frozen=True, slots=True)
class MultisinePreflightResult:
    recording_path: Path
    manifest_path: Path
    recording_sha256: str
    manifest_sha256: str
    stimulus_id: str
    stimulus_hash: str
    tone_set_id: str
    sample_rate_hz: int
    channel_count: int
    audio_channel: int
    period_samples: int
    stable_period_count: int
    discard_initial_period_count: int


@dataclass(frozen=True, slots=True)
class MeasurementDraft:
    route: UsageRoute
    run_purpose: str
    sample_id: str
    run_id: str
    metadata_filename: str
    sidecar_filename: str | None
    session_directory: Path
    metadata_path: Path
    config_path: Path
    stimulus_manifest_path: Path | None
    metadata: MeasurementMeta
    sidecar_extras: dict[str, Any]
    git_commit: str


@dataclass(frozen=True, slots=True)
class SavedMeasurementDraft:
    draft: MeasurementDraft
    revision: int
    session_directory: Path
    metadata_path: Path
    config_snapshot_path: Path
    input_hashes_path: Path
    step_report_markdown: Path
    step_report_html: Path
    technical_log_path: Path
    revision_record_path: Path
    metadata: MeasurementMeta


@dataclass(frozen=True, slots=True)
class MeasurementRunEvidence:
    status: str
    success: bool
    qc_status: str
    output_directory: Path
    run_result_json: Path
    run_report_markdown: Path
    run_report_html: Path
    stdout_log: Path
    stderr_log: Path
    output_hashes_json: Path


def verify_saved_input_hashes(saved: SavedMeasurementDraft) -> None:
    records = json.loads(saved.input_hashes_path.read_text(encoding="utf-8"))
    mismatches = []
    for record in records:
        path = Path(str(record["path"]))
        actual = artifact_sha256(path) if path.is_file() else None
        if actual != record["sha256"]:
            mismatches.append(
                {
                    "role": record["role"],
                    "path": path.as_posix(),
                    "expected": record["sha256"],
                    "actual": actual,
                }
            )
    if mismatches:
        raise ValueError(f"input hash mismatch: {mismatches}")


_POLICIES = {
    UsageRoute.SIMULATED_PRACTICE: RoutePolicy(
        UsageRoute.SIMULATED_PRACTICE,
        DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION,
        "software_validation",
        False,
        "模拟数据：不能用于科研结论",
    ),
    UsageRoute.OFFICIAL_REFERENCE: RoutePolicy(
        UsageRoute.OFFICIAL_REFERENCE,
        DataOrigin.EXTERNAL_REFERENCE,
        DatasetRole.PARSER_FIXTURE,
        "software_validation",
        False,
        "官方参考：仅用于格式和软件验证",
    ),
    UsageRoute.REAL_DIAGNOSTIC: RoutePolicy(
        UsageRoute.REAL_DIAGNOSTIC,
        DataOrigin.REAL_EXPERIMENT,
        DatasetRole.RESEARCH_INPUT,
        "software_validation",
        False,
        "真实实验诊断：尚未自动获得科研资格",
    ),
}


class MeasurementDraftService:
    def __init__(
        self,
        project_root: str | Path,
        *,
        workspace_root: str | Path | None = None,
        source_commit: str | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.workspace_root = Path(workspace_root or self.project_root).resolve()
        self.source_commit = source_commit

    def route_policy(self, route: UsageRoute | str) -> RoutePolicy:
        return _POLICIES[UsageRoute(route)]

    def analysis_decision(self, draft: MeasurementDraft) -> AnalysisDecision:
        if (
            draft.route is UsageRoute.REAL_DIAGNOSTIC
            and draft.metadata.measurement_mode
            is MeasurementMode.SCHROEDER_MULTISINE
        ):
            return AnalysisDecision(False, "blocked", REAL_MULTISINE_BLOCK_MESSAGE)
        return AnalysisDecision(True, "ready")

    def with_session_root(
        self, draft: MeasurementDraft, session_root: str | Path
    ) -> MeasurementDraft:
        session_directory = (
            Path(session_root).resolve() / draft.sample_id / "rev-001"
        )
        metadata_path = session_directory / draft.metadata_filename
        metadata = draft.metadata
        if metadata.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE:
            metadata = replace(metadata, sidecar_path=metadata_path.as_posix())
        return replace(
            draft,
            session_directory=session_directory,
            metadata_path=metadata_path,
            metadata=metadata,
        )

    def save_draft(
        self,
        draft: MeasurementDraft,
        *,
        revision_reason: str | None = None,
    ) -> SavedMeasurementDraft:
        """Write UI-owned metadata evidence without copying or changing raw input."""
        session_base = draft.session_directory.parent
        existing = sorted(
            path
            for path in session_base.glob("rev-[0-9][0-9][0-9]")
            if path.is_dir()
        ) if session_base.exists() else []
        if existing and not (revision_reason and revision_reason.strip()):
            raise FileExistsError(
                f"sample {draft.sample_id} is already registered; "
                "save an explicit revision instead"
            )
        revision = len(existing) + 1
        active_run_id = (
            draft.run_id
            if revision == 1
            else f"{draft.run_id}-r{revision:03d}"
        )
        active_draft = replace(draft, run_id=active_run_id)
        target = session_base / f"rev-{revision:03d}"
        if target.exists():
            raise FileExistsError(f"UI session revision already exists: {target}")
        target.mkdir(parents=True)

        metadata_path = target / draft.metadata_filename
        metadata = draft.metadata
        if metadata.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE:
            metadata = replace(metadata, sidecar_path=metadata_path.as_posix())
        metadata_payload = metadata.to_dict()
        metadata_payload.update(draft.sidecar_extras)
        metadata_path.write_text(
            json.dumps(metadata_payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )

        resolved = load_config(
            draft.config_path,
            default_path=self.project_root / "config/default.yaml",
        )
        if draft.stimulus_manifest_path is not None:
            resolved["paths"]["stimuli"] = (
                draft.stimulus_manifest_path.parent.parent.resolve().as_posix()
            )
            resolved["stimulus_id"] = metadata.stimulus_id
            resolved["tone_set_id"] = metadata.tone_set_id
            resolved["sample_rate_hz"] = int(draft.sidecar_extras["sample_rate_hz"])
            resolved["multisine_estimation"]["stable_period_count"] = int(
                draft.sidecar_extras["stable_period_count"]
            )
            resolved["multisine_estimation"]["discard_initial_period_count"] = int(
                draft.sidecar_extras["discard_initial_period_count"]
            )
        config_snapshot = target / "resolved_config.yaml"
        config_snapshot.write_text(
            yaml.safe_dump(resolved, sort_keys=True, allow_unicode=True),
            encoding="utf-8",
        )

        inputs = self._input_hash_records(draft)
        input_hashes = target / "input_hashes.json"
        input_hashes.write_text(
            json.dumps(inputs, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        decision = self.analysis_decision(replace(active_draft, metadata=metadata))
        created_at = datetime.now(UTC).isoformat()
        revision_record = target / "revision_record.json"
        revision_record.write_text(
            json.dumps(
                {
                    "sample_id": draft.sample_id,
                    "revision": revision,
                    "supersedes_revision": revision - 1 if revision > 1 else None,
                    "reason": revision_reason.strip() if revision_reason else "initial registration",
                    "created_at_utc": created_at,
                },
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        manifest_path = target / "ui_session_manifest.json"
        manifest = {
            "ui_session_schema_version": "1.0.0",
            "sample_id": draft.sample_id,
            "run_id": active_run_id,
            "revision": revision,
            "route": draft.route.value,
            "measurement_mode": metadata.measurement_mode.value,
            "data_origin": metadata.data_origin.value,
            "dataset_role": metadata.dataset_role.value,
            "run_purpose": draft.run_purpose,
            "eligible_for_scientific_analysis": False,
            "analysis_status": decision.status,
            "analysis_block_reason": decision.reason,
            "git_commit": draft.git_commit,
            "created_at_utc": created_at,
            "source_path": metadata.source_path,
            "metadata_path": metadata_path.as_posix(),
            "config_snapshot_path": config_snapshot.as_posix(),
            "inputs": inputs,
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (target / "ui_session_manifest.sha256").write_text(
            artifact_sha256(manifest_path), encoding="ascii"
        )
        technical_log = target / "technical_log.txt"
        technical_log.write_text(
            "\n".join(
                (
                    f"created_at_utc={created_at}",
                    f"sample_id={draft.sample_id}",
                    f"run_id={active_run_id}",
                    f"route={draft.route.value}",
                    f"measurement_mode={metadata.measurement_mode.value}",
                    f"analysis_status={decision.status}",
                    f"git_commit={draft.git_commit}",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        report_md = target / "step_report.md"
        block_text = decision.reason or "无；该登记可进入软件验证单次处理。"
        report_text = (
            f"# DEV-UI2 单次测量登记：{draft.sample_id}\n\n"
            f"- 状态：{decision.status}\n"
            f"- 使用路径：{draft.route.value}\n"
            f"- 测量模式：{metadata.measurement_mode.value}\n"
            f"- 数据来源：{metadata.data_origin.value}\n"
            f"- 数据角色：{metadata.dataset_role.value}\n"
            f"- 运行用途：{draft.run_purpose}\n"
            f"- 科研资格：false\n"
            f"- sample_id：{draft.sample_id}\n"
            f"- run_id：{active_run_id}\n"
            f"- revision：{revision}\n"
            f"- 原始输入：{metadata.source_path}\n"
            f"- 输入 SHA-256：{metadata.source_sha256}\n"
            f"- 实验身份：device={metadata.device_version}, configuration={metadata.configuration}, "
            f"angle_deg={metadata.angle_deg}, session={metadata.session_id}, "
            f"repeat={metadata.repeat_type}/{metadata.repeat_id}\n"
            f"- metadata：{metadata_path.as_posix()}\n"
            f"- 配置快照：{config_snapshot.as_posix()}\n"
            f"- 阻塞/说明：{block_text}\n"
            f"- 下一步：{'保留登记证据并等待 DEV-D。' if not decision.allowed else '运行单次软件验证。'}\n"
        )
        report_md.write_text(report_text, encoding="utf-8")
        report_html = target / "step_report.html"
        report_html.write_text(
            "<!doctype html><meta charset=\"utf-8\"><title>DEV-UI2 report</title>"
            f"<pre>{escape(report_text)}</pre>\n",
            encoding="utf-8",
        )
        return SavedMeasurementDraft(
            draft=active_draft,
            revision=revision,
            session_directory=target,
            metadata_path=metadata_path,
            config_snapshot_path=config_snapshot,
            input_hashes_path=input_hashes,
            step_report_markdown=report_md,
            step_report_html=report_html,
            technical_log_path=technical_log,
            revision_record_path=revision_record,
            metadata=metadata,
        )

    def record_run_result(
        self,
        saved: SavedMeasurementDraft,
        *,
        output_directory: str | Path,
        status: str,
        program: str,
        arguments: tuple[str, ...] | list[str],
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> MeasurementRunEvidence:
        """Capture process and backend evidence without inventing success state."""
        result_path = saved.session_directory / "run_result.json"
        if result_path.exists():
            raise FileExistsError(
                f"run result is already recorded: {result_path}"
            )
        output = Path(output_directory).resolve()
        manifest_path = output / "run_manifest.json"
        manifest: dict[str, Any] = {}
        if manifest_path.is_file():
            digest_path = output / "run_manifest.sha256"
            if digest_path.is_file():
                expected = digest_path.read_text(encoding="ascii").strip()
                if artifact_sha256(manifest_path) != expected:
                    raise ValueError("run manifest SHA-256 mismatch")
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("run manifest must contain a JSON object")
            manifest = payload
        output_records = [
            {
                "path": path.resolve().as_posix(),
                "sha256": artifact_sha256(path),
            }
            for path in sorted(output.rglob("*"))
            if path.is_file()
        ] if output.is_dir() else []
        output_hashes = saved.session_directory / "output_hashes.json"
        output_hashes.write_text(
            json.dumps(output_records, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        stdout_path = saved.session_directory / "stdout.log"
        stderr_path = saved.session_directory / "stderr.log"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        manifest_status = str(manifest.get("processing_status", status))
        qc_status = str(manifest.get("qc_status", "unavailable"))
        success = bool(manifest.get("success", False))
        qc_details: dict[str, Any] = {}
        qc_path = output / "quality_control.json"
        if qc_path.is_file():
            parsed_qc = json.loads(qc_path.read_text(encoding="utf-8"))
            if isinstance(parsed_qc, dict):
                qc_details = {
                    name: parsed_qc.get(name, [])
                    for name in (
                        "warning_reasons",
                        "exclude_candidate_reasons",
                        "manual_review_reasons",
                        "unavailable_checks",
                    )
                }
        result_payload = {
            "ui_run_result_schema_version": "1.0.0",
            "sample_id": saved.draft.sample_id,
            "run_id": saved.draft.run_id,
            "revision": saved.revision,
            "ui_status": status,
            "backend_processing_status": manifest_status,
            "success": success,
            "qc_status": qc_status,
            "phase_status": manifest.get("phase_status", "unavailable"),
            "eligible_for_scientific_analysis": bool(
                manifest.get("eligible_for_scientific_analysis", False)
            ),
            "exit_code": int(exit_code),
            "program": program,
            "arguments": list(arguments),
            "output_directory": output.as_posix(),
            "run_manifest_path": (
                manifest_path.as_posix() if manifest_path.is_file() else None
            ),
            "stage_gate": manifest.get("stage_gate", {}),
            "qc_reasons": qc_details,
            "failure": manifest.get("failure"),
            "recorded_at_utc": datetime.now(UTC).isoformat(),
        }
        result_path.write_text(
            json.dumps(result_payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        (saved.session_directory / "run_result.sha256").write_text(
            artifact_sha256(result_path), encoding="ascii"
        )
        technical_log = saved.technical_log_path.read_text(encoding="utf-8")
        saved.technical_log_path.write_text(
            technical_log
            + f"run_status={status}\n"
            + f"backend_processing_status={manifest_status}\n"
            + f"exit_code={exit_code}\n"
            + f"program={program}\n"
            + f"arguments={json.dumps(list(arguments), ensure_ascii=False)}\n"
            + f"output_directory={output.as_posix()}\n",
            encoding="utf-8",
        )
        report_md = saved.session_directory / "run_report.md"
        report = (
            f"# DEV-UI2 单次处理结果：{saved.draft.sample_id}\n\n"
            f"- UI 状态：{status}\n"
            f"- 后端状态：{manifest_status}\n"
            f"- 成功：{str(success).lower()}\n"
            f"- QC：{qc_status}\n"
            f"- QC/warning/manual-review 原因：{json.dumps(qc_details, ensure_ascii=False)}\n"
            f"- 失败/阻塞原因：{json.dumps(manifest.get('failure'), ensure_ascii=False)}\n"
            f"- 科研资格：{str(result_payload['eligible_for_scientific_analysis']).lower()}\n"
            f"- 退出码：{exit_code}\n"
            f"- 命令程序：{program}\n"
            f"- 参数：{json.dumps(list(arguments), ensure_ascii=False)}\n"
            f"- 输出目录：{output.as_posix()}\n"
            f"- 生成物：{json.dumps([row['path'] for row in output_records], ensure_ascii=False)}\n"
            f"- 下一步：{'检查 warning/manual review 后再决定。' if not success else '查看 QC 和 FeatureSet；科研资格仍由后端门禁决定。'}\n"
        )
        report_md.write_text(report, encoding="utf-8")
        report_html = saved.session_directory / "run_report.html"
        report_html.write_text(
            "<!doctype html><meta charset=\"utf-8\"><title>DEV-UI2 run</title>"
            f"<pre>{escape(report)}</pre>\n",
            encoding="utf-8",
        )
        return MeasurementRunEvidence(
            status=status,
            success=success,
            qc_status=qc_status,
            output_directory=output,
            run_result_json=result_path,
            run_report_markdown=report_md,
            run_report_html=report_html,
            stdout_log=stdout_path,
            stderr_log=stderr_path,
            output_hashes_json=output_hashes,
        )

    @staticmethod
    def _input_hash_records(draft: MeasurementDraft) -> list[dict[str, str]]:
        records = [
            {
                "role": (
                    "recording"
                    if draft.metadata.measurement_mode
                    is MeasurementMode.SCHROEDER_MULTISINE
                    else "measurement"
                ),
                "path": Path(draft.metadata.source_path).resolve().as_posix(),
                "sha256": draft.metadata.source_sha256,
            }
        ]
        if draft.stimulus_manifest_path is not None:
            records.append(
                {
                    "role": "stimulus_manifest",
                    "path": draft.stimulus_manifest_path.resolve().as_posix(),
                    "sha256": str(draft.sidecar_extras["stimulus_manifest_sha256"]),
                }
            )
            payload = json.loads(
                draft.stimulus_manifest_path.read_text(encoding="utf-8")
            )
            stimulus = (
                draft.stimulus_manifest_path.parent / str(payload["wav_file"])
            ).resolve()
            records.append(
                {
                    "role": "stimulus_wav",
                    "path": stimulus.as_posix(),
                    "sha256": artifact_sha256(stimulus),
                }
            )
        return records

    def validate_form_for_route(
        self, route: UsageRoute | str, form: MetadataFormValues
    ) -> None:
        if UsageRoute(route) is not UsageRoute.OFFICIAL_REFERENCE:
            return
        identity_names = tuple(
            field.name
            for field in fields(MetadataFormValues)
            if field.name
            not in {"audio_channel", "provenance_uri"}
        )
        present = [
            name
            for name in identity_names
            if getattr(form, name) not in (None, "")
        ]
        if present:
            raise ValueError(
                "external_reference must not contain experiment identity fields: "
                f"{present}"
            )

    def preflight_rew(self, path: str | Path) -> REWPreflightResult:
        return inspect_rew_frequency_response(path)

    def preflight_multisine(
        self,
        recording_wav: str | Path,
        stimulus_manifest: str | Path,
        *,
        audio_channel: int,
        expected_stimulus_id: str | None = None,
        expected_stimulus_hash: str | None = None,
        expected_tone_set_id: str | None = None,
    ) -> MultisinePreflightResult:
        recording = Path(recording_wav).resolve()
        manifest_path = Path(stimulus_manifest).resolve()
        if not recording.is_file():
            raise FileNotFoundError(f"Multisine recording does not exist: {recording}")
        if recording.suffix.casefold() != ".wav":
            raise ValueError(f"Multisine recording must use the .wav extension: {recording}")
        if recording.stat().st_size == 0:
            raise ValueError(f"Multisine recording is empty: {recording}")
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Stimulus manifest does not exist: {manifest_path}")
        if manifest_path.name != "stimulus_manifest.json":
            raise ValueError("Stimulus manifest must be named stimulus_manifest.json")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid stimulus manifest: {manifest_path}") from exc
        required = {
            "stimulus_id",
            "tone_set_id",
            "sample_rate_hz",
            "period_samples",
            "stable_period_count",
            "discard_initial_period_count",
            "wav_file",
            "waveform_sha256",
        }
        missing = sorted(required.difference(manifest))
        if missing:
            raise ValueError(f"Stimulus manifest fields are missing: {missing}")
        expectations = (
            ("stimulus_id", expected_stimulus_id),
            ("waveform_sha256", expected_stimulus_hash),
            ("tone_set_id", expected_tone_set_id),
        )
        for field_name, expected in expectations:
            if expected is not None and str(manifest[field_name]) != expected:
                raise ValueError(
                    f"Multisine {field_name} mismatch: selected={manifest[field_name]!r}, "
                    f"expected={expected!r}"
                )
        stimulus_wav = (manifest_path.parent / str(manifest["wav_file"])).resolve()
        if not stimulus_wav.is_file():
            raise FileNotFoundError(f"Stimulus WAV does not exist: {stimulus_wav}")
        actual_stimulus_hash = artifact_sha256(stimulus_wav)
        if actual_stimulus_hash != str(manifest["waveform_sha256"]):
            raise ValueError("Stimulus WAV SHA-256 does not match stimulus manifest")
        try:
            sample_rate, values = wavfile.read(recording, mmap=True)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Recording WAV cannot be read: {recording}") from exc
        channel_count = 1 if values.ndim == 1 else int(values.shape[1])
        if isinstance(audio_channel, bool) or not isinstance(audio_channel, int):
            raise ValueError("audio_channel must be an integer")
        if not 0 <= audio_channel < channel_count:
            raise ValueError(
                f"WAV channel {audio_channel} does not exist; available channels: "
                f"0..{channel_count - 1}"
            )
        manifest_rate = int(manifest["sample_rate_hz"])
        if int(sample_rate) != manifest_rate:
            raise ValueError(
                f"Recording sample rate mismatch: WAV={sample_rate}, manifest={manifest_rate}"
            )
        return MultisinePreflightResult(
            recording_path=recording,
            manifest_path=manifest_path,
            recording_sha256=artifact_sha256(recording),
            manifest_sha256=artifact_sha256(manifest_path),
            stimulus_id=str(manifest["stimulus_id"]),
            stimulus_hash=str(manifest["waveform_sha256"]),
            tone_set_id=str(manifest["tone_set_id"]),
            sample_rate_hz=manifest_rate,
            channel_count=channel_count,
            audio_channel=audio_channel,
            period_samples=int(manifest["period_samples"]),
            stable_period_count=int(manifest["stable_period_count"]),
            discard_initial_period_count=int(
                manifest["discard_initial_period_count"]
            ),
        )

    def build_draft(
        self,
        *,
        route: UsageRoute | str,
        measurement_mode: MeasurementMode | str,
        preflight: REWPreflightResult | MultisinePreflightResult,
        form: MetadataFormValues,
    ) -> MeasurementDraft:
        selected_route = UsageRoute(route)
        mode = MeasurementMode(measurement_mode)
        policy = self.route_policy(selected_route)
        self.validate_form_for_route(selected_route, form)
        allowed = {
            UsageRoute.OFFICIAL_REFERENCE: {MeasurementMode.REW_SWEEP},
            UsageRoute.SIMULATED_PRACTICE: {
                MeasurementMode.SCHROEDER_MULTISINE
            },
            UsageRoute.REAL_DIAGNOSTIC: {
                MeasurementMode.REW_SWEEP,
                MeasurementMode.SCHROEDER_MULTISINE,
            },
        }
        if mode not in allowed[selected_route]:
            raise ValueError(
                f"route {selected_route.value} does not allow {mode.value}"
            )
        if mode is MeasurementMode.REW_SWEEP and not isinstance(
            preflight, REWPreflightResult
        ):
            raise TypeError("rew_sweep requires REW preflight")
        if mode is MeasurementMode.SCHROEDER_MULTISINE and not isinstance(
            preflight, MultisinePreflightResult
        ):
            raise TypeError("schroeder_multisine requires Multisine preflight")
        config_name = (
            "experiment_v2_u4.yaml"
            if mode is MeasurementMode.REW_SWEEP
            else "experiment_v2_u4_multisine.yaml"
        )
        config_path = self.project_root / "config" / config_name
        resolved = load_config(
            config_path,
            default_path=self.project_root / "config/default.yaml",
        )
        source_path = preflight.source_path if isinstance(
            preflight, REWPreflightResult
        ) else preflight.recording_path
        source_sha256 = preflight.source_sha256 if isinstance(
            preflight, REWPreflightResult
        ) else preflight.recording_sha256
        identity_payload = {
            "route": selected_route.value,
            "measurement_mode": mode.value,
            "source_sha256": source_sha256,
            "form": asdict(form),
            "stimulus_id": (
                preflight.stimulus_id
                if isinstance(preflight, MultisinePreflightResult)
                else None
            ),
            "tone_set_id": (
                preflight.tone_set_id
                if isinstance(preflight, MultisinePreflightResult)
                else None
            ),
        }
        encoded = json.dumps(
            identity_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        route_code = {
            UsageRoute.OFFICIAL_REFERENCE: "ref",
            UsageRoute.SIMULATED_PRACTICE: "sim",
            UsageRoute.REAL_DIAGNOSTIC: "real",
        }[selected_route]
        mode_code = "rew" if mode is MeasurementMode.REW_SWEEP else "ms"
        sample_id = f"{route_code}-{mode_code}-{digest[:12]}"
        run_id = f"u2-{digest[12:24]}"
        session_directory = (
            self.workspace_root
            / "outputs/ui_sessions"
            / sample_id
            / "rev-001"
        )
        metadata_filename = (
            f"{sample_id}.metadata.json"
            if mode is MeasurementMode.REW_SWEEP
            else f"{sample_id}.sidecar.json"
        )
        metadata_path = session_directory / metadata_filename
        if self.source_commit is not None:
            git_commit = self.source_commit
        else:
            git_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        values = {
            name: self._none_if_blank(getattr(form, name))
            for name in (
                "device_version",
                "configuration",
                "session_id",
                "repeat_type",
                "repeat_id",
                "reposition_round_id",
                "assembly_id",
                "acquisition_block_id",
                "experiment_step",
            )
        }
        angle = self._none_if_blank(form.angle_deg)
        date_time = self._none_if_blank(form.date_time)
        provenance_uri = self._none_if_blank(form.provenance_uri)
        if provenance_uri is None:
            raise ValueError("provenance record/reference is required")
        if selected_route is UsageRoute.OFFICIAL_REFERENCE:
            values = {name: None for name in values}
            angle = None
            date_time = None
        source_format = {
            (UsageRoute.OFFICIAL_REFERENCE, MeasurementMode.REW_SWEEP): SourceFormat.REW_TXT,
            (UsageRoute.REAL_DIAGNOSTIC, MeasurementMode.REW_SWEEP): SourceFormat.REW_TXT,
            (UsageRoute.REAL_DIAGNOSTIC, MeasurementMode.SCHROEDER_MULTISINE): SourceFormat.MULTISINE_WAV,
            (UsageRoute.SIMULATED_PRACTICE, MeasurementMode.SCHROEDER_MULTISINE): SourceFormat.MOCK_AUDIO,
        }[(selected_route, mode)]
        metadata = MeasurementMeta(
            sample_id=sample_id,
            pipeline_version=str(resolved["pipeline_version"]),
            config_schema_version=str(resolved["schema_versions"]["config"]),
            measurement_schema_version=str(
                resolved["schema_versions"]["measurement"]
            ),
            feature_schema_version=str(resolved["schema_versions"]["feature"]),
            device_version=values["device_version"],
            configuration=values["configuration"],
            angle_deg=None if angle is None else float(angle),
            session_id=values["session_id"],
            repeat_type=values["repeat_type"],
            repeat_id=values["repeat_id"],
            reposition_round_id=values["reposition_round_id"],
            assembly_id=values["assembly_id"],
            acquisition_block_id=values["acquisition_block_id"],
            experiment_step=values["experiment_step"],
            measurement_mode=mode,
            source_format=source_format,
            source_path=source_path.as_posix(),
            data_origin=policy.data_origin,
            dataset_role=policy.dataset_role,
            source_sha256=source_sha256,
            provenance_uri=str(provenance_uri),
            eligible_for_scientific_analysis=False,
            stimulus_id=(preflight.stimulus_id if isinstance(preflight, MultisinePreflightResult) else None),
            stimulus_hash=(preflight.stimulus_hash if isinstance(preflight, MultisinePreflightResult) else None),
            tone_set_id=(preflight.tone_set_id if isinstance(preflight, MultisinePreflightResult) else None),
            sidecar_path=(metadata_path.as_posix() if isinstance(preflight, MultisinePreflightResult) else None),
            date_time=(datetime.fromisoformat(str(date_time)) if date_time is not None else None),
            audio_channel=(preflight.audio_channel if isinstance(preflight, MultisinePreflightResult) else None),
        )
        extras: dict[str, Any] = {}
        manifest_path: Path | None = None
        if isinstance(preflight, MultisinePreflightResult):
            manifest_path = preflight.manifest_path
            extras = {
                "sample_rate_hz": preflight.sample_rate_hz,
                "period_samples": preflight.period_samples,
                "stable_period_count": preflight.stable_period_count,
                "discard_initial_period_count": preflight.discard_initial_period_count,
                "stimulus_manifest": preflight.manifest_path.as_posix(),
                "recording_sha256": preflight.recording_sha256,
                "stimulus_manifest_sha256": preflight.manifest_sha256,
            }
        return MeasurementDraft(
            route=selected_route,
            run_purpose=policy.run_purpose,
            sample_id=sample_id,
            run_id=run_id,
            metadata_filename=metadata_filename,
            sidecar_filename=(metadata_filename if mode is MeasurementMode.SCHROEDER_MULTISINE else None),
            session_directory=session_directory,
            metadata_path=metadata_path,
            config_path=config_path,
            stimulus_manifest_path=manifest_path,
            metadata=metadata,
            sidecar_extras=extras,
            git_commit=git_commit,
        )

    @staticmethod
    def _none_if_blank(value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

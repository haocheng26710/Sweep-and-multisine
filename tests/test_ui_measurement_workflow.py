from __future__ import annotations

from pathlib import Path
import hashlib
import json

import numpy as np
import pytest
from scipy.io import wavfile

from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
)
from acoustic_encoder.io_rew import REWImportError, UnsupportedREWDataTypeError
from acoustic_encoder.ui.measurement_workflow import (
    MetadataFormValues,
    MeasurementDraftService,
    REAL_MULTISINE_BLOCK_MESSAGE,
    UsageRoute,
)
from acoustic_encoder.ui.workers import (
    ProcessOutcome,
    SingleMeasurementStatus,
    SingleMeasurementWorker,
    map_single_measurement_status,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_route_policies_fix_origin_role_purpose_and_scientific_eligibility() -> None:
    service = MeasurementDraftService(PROJECT_ROOT)

    official = service.route_policy(UsageRoute.OFFICIAL_REFERENCE)
    simulated = service.route_policy(UsageRoute.SIMULATED_PRACTICE)
    real = service.route_policy(UsageRoute.REAL_DIAGNOSTIC)

    assert (official.data_origin, official.dataset_role) == (
        DataOrigin.EXTERNAL_REFERENCE,
        DatasetRole.PARSER_FIXTURE,
    )
    assert (simulated.data_origin, simulated.dataset_role) == (
        DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION,
    )
    assert (real.data_origin, real.dataset_role) == (
        DataOrigin.REAL_EXPERIMENT,
        DatasetRole.RESEARCH_INPUT,
    )
    assert all(
        policy.run_purpose == "software_validation"
        and policy.eligible_for_scientific_analysis is False
        for policy in (official, simulated, real)
    )


def test_official_reference_rejects_experiment_identity_instead_of_hiding_it() -> None:
    service = MeasurementDraftService(PROJECT_ROOT)

    with pytest.raises(ValueError, match="external_reference.*device_version"):
        service.validate_form_for_route(
            UsageRoute.OFFICIAL_REFERENCE,
            MetadataFormValues(device_version="V2"),
        )
    with pytest.raises(ValueError, match="external_reference.*date_time"):
        service.validate_form_for_route(
            UsageRoute.OFFICIAL_REFERENCE,
            MetadataFormValues(date_time="2026-08-10T12:00:00+01:00"),
        )


@pytest.mark.parametrize(
    ("fixture", "has_phase"),
    [("no_phase.txt", False), ("comma_with_phase.txt", True)],
)
def test_rew_preflight_reuses_parser_and_preserves_source_bytes(
    fixture: str, has_phase: bool
) -> None:
    source = PROJECT_ROOT / "tests/fixtures/rew/synthetic" / fixture
    before = source.read_bytes()

    result = MeasurementDraftService(PROJECT_ROOT).preflight_rew(source)

    assert result.data_point_count >= 5
    assert result.has_phase is has_phase
    assert result.source_sha256 == hashlib.sha256(before).hexdigest()
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    ("fixture", "error_type", "message"),
    [
        ("impedance.txt", UnsupportedREWDataTypeError, "impedance"),
        ("decreasing_frequency.txt", REWImportError, "strictly increasing"),
        ("too_short.txt", REWImportError, "at least 5"),
    ],
)
def test_rew_preflight_rejects_non_spl_or_invalid_frequency_data(
    fixture: str, error_type: type[Exception], message: str
) -> None:
    source = PROJECT_ROOT / "tests/fixtures/rew/synthetic" / fixture

    with pytest.raises(error_type, match=message):
        MeasurementDraftService(PROJECT_ROOT).preflight_rew(source)


def _multisine_files(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "含 中文 spaces" / "stimuli" / "stim-1"
    root.mkdir(parents=True)
    stimulus = root / "stimulus.wav"
    recording = tmp_path / "含 中文 spaces" / "recording.wav"
    values = np.zeros((480, 2), dtype=np.float32)
    wavfile.write(stimulus, 48000, values[:, 0])
    wavfile.write(recording, 48000, values)
    manifest = root / "stimulus_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "stimulus_id": "stim-1",
                "tone_set_id": "tones-1",
                "sample_rate_hz": 48000,
                "period_samples": 120,
                "stable_period_count": 2,
                "discard_initial_period_count": 1,
                "wav_file": stimulus.name,
                "waveform_sha256": hashlib.sha256(stimulus.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return recording, manifest


def test_multisine_preflight_reads_manifest_wav_channel_and_hashes_without_mutation(
    tmp_path: Path,
) -> None:
    recording, manifest = _multisine_files(tmp_path)
    recording_before = recording.read_bytes()
    manifest_before = manifest.read_bytes()

    result = MeasurementDraftService(PROJECT_ROOT).preflight_multisine(
        recording, manifest, audio_channel=1
    )

    assert result.sample_rate_hz == 48000
    assert result.channel_count == 2
    assert result.audio_channel == 1
    assert result.stimulus_id == "stim-1"
    assert result.tone_set_id == "tones-1"
    assert result.recording_sha256 == hashlib.sha256(recording_before).hexdigest()
    assert result.manifest_sha256 == hashlib.sha256(manifest_before).hexdigest()
    assert recording.read_bytes() == recording_before
    assert manifest.read_bytes() == manifest_before


def test_multisine_preflight_rejects_channel_rate_stimulus_and_hash_mismatches(
    tmp_path: Path,
) -> None:
    recording, manifest = _multisine_files(tmp_path)
    service = MeasurementDraftService(PROJECT_ROOT)

    with pytest.raises(ValueError, match="channel 2 does not exist"):
        service.preflight_multisine(recording, manifest, audio_channel=2)
    with pytest.raises(ValueError, match="stimulus_id mismatch"):
        service.preflight_multisine(
            recording, manifest, audio_channel=0, expected_stimulus_id="other"
        )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["sample_rate_hz"] = 44100
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="sample rate mismatch"):
        service.preflight_multisine(recording, manifest, audio_channel=0)

    payload["sample_rate_hz"] = 48000
    payload["waveform_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        service.preflight_multisine(recording, manifest, audio_channel=0)


def test_official_reference_metadata_is_schema_valid_round_trip_and_ids_are_stable() -> None:
    service = MeasurementDraftService(PROJECT_ROOT)
    source = PROJECT_ROOT / "tests/fixtures/rew/external_reference/BW M1.txt"
    preflight = service.preflight_rew(source)
    form = MetadataFormValues(
        provenance_uri="tests/fixtures/rew/external_reference/manifest.json"
    )

    first = service.build_draft(
        route=UsageRoute.OFFICIAL_REFERENCE,
        measurement_mode=MeasurementMode.REW_SWEEP,
        preflight=preflight,
        form=form,
    )
    second = service.build_draft(
        route=UsageRoute.OFFICIAL_REFERENCE,
        measurement_mode=MeasurementMode.REW_SWEEP,
        preflight=preflight,
        form=form,
    )

    restored = MeasurementMeta.from_dict(first.metadata.to_dict())
    assert restored == first.metadata
    assert restored.data_origin is DataOrigin.EXTERNAL_REFERENCE
    assert restored.dataset_role is DatasetRole.PARSER_FIXTURE
    assert restored.device_version is None and restored.angle_deg is None
    assert restored.eligible_for_scientific_analysis is False
    assert first.sample_id == second.sample_id
    assert first.run_id == second.run_id
    assert first.metadata_filename.endswith(".metadata.json")
    assert "/" not in first.run_id and "\\" not in first.run_id


def _real_form(**changes) -> MetadataFormValues:
    values = {
        "device_version": "V2",
        "configuration": "U4ENC",
        "angle_deg": "90",
        "session_id": "S01",
        "repeat_type": "CONT",
        "repeat_id": "R01",
        "reposition_round_id": "P01",
        "assembly_id": "A01",
        "acquisition_block_id": "B01",
        "experiment_step": "DIAGNOSTIC",
        "date_time": "2026-08-10T12:00:00+01:00",
        "provenance_uri": "lab://diagnostic/acquisition-001",
    }
    values.update(changes)
    return MetadataFormValues(**values)


def test_real_rew_diagnostic_forces_software_validation_and_ineligible_metadata() -> None:
    service = MeasurementDraftService(PROJECT_ROOT)
    source = PROJECT_ROOT / "tests/fixtures/rew/external_reference/BW M1.txt"

    draft = service.build_draft(
        route=UsageRoute.REAL_DIAGNOSTIC,
        measurement_mode=MeasurementMode.REW_SWEEP,
        preflight=service.preflight_rew(source),
        form=_real_form(),
    )

    assert draft.run_purpose == "software_validation"
    assert draft.metadata.data_origin is DataOrigin.REAL_EXPERIMENT
    assert draft.metadata.dataset_role is DatasetRole.RESEARCH_INPUT
    assert draft.metadata.eligible_for_scientific_analysis is False
    assert draft.metadata.date_time is not None
    assert draft.metadata.date_time.utcoffset() is not None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"angle_deg": "361"}, "angle_deg"),
        ({"date_time": "2026-08-10T12:00:00"}, "timezone"),
        ({"session_id": ""}, "session_id"),
    ],
)
def test_real_metadata_uses_authoritative_schema_validation(change, message: str) -> None:
    service = MeasurementDraftService(PROJECT_ROOT)
    source = PROJECT_ROOT / "tests/fixtures/rew/external_reference/BW M1.txt"

    with pytest.raises(ValueError, match=message):
        service.build_draft(
            route=UsageRoute.REAL_DIAGNOSTIC,
            measurement_mode=MeasurementMode.REW_SWEEP,
            preflight=service.preflight_rew(source),
            form=_real_form(**change),
        )


def test_simulated_and_real_multisine_drafts_keep_distinct_locked_provenance(
    tmp_path: Path,
) -> None:
    recording, manifest = _multisine_files(tmp_path)
    service = MeasurementDraftService(PROJECT_ROOT)
    preflight = service.preflight_multisine(recording, manifest, audio_channel=0)

    simulated = service.build_draft(
        route=UsageRoute.SIMULATED_PRACTICE,
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        preflight=preflight,
        form=_real_form(
            audio_channel=0,
            experiment_step="SIMULATED_PRACTICE",
            provenance_uri="ui://simulated-practice",
        ),
    )
    real = service.build_draft(
        route=UsageRoute.REAL_DIAGNOSTIC,
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        preflight=preflight,
        form=_real_form(audio_channel=0),
    )

    assert simulated.metadata.data_origin is DataOrigin.SIMULATED
    assert simulated.metadata.source_format.value == "mock_audio"
    assert real.metadata.data_origin is DataOrigin.REAL_EXPERIMENT
    assert real.metadata.source_format.value == "multisine_wav"
    assert real.metadata.eligible_for_scientific_analysis is False
    assert MeasurementMeta.from_dict(simulated.metadata.to_dict()) == simulated.metadata
    assert MeasurementMeta.from_dict(real.metadata.to_dict()) == real.metadata


def test_real_multisine_is_registered_but_always_blocked_before_analysis(
    tmp_path: Path,
) -> None:
    recording, manifest = _multisine_files(tmp_path)
    service = MeasurementDraftService(PROJECT_ROOT)
    draft = service.build_draft(
        route=UsageRoute.REAL_DIAGNOSTIC,
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        preflight=service.preflight_multisine(recording, manifest, audio_channel=0),
        form=_real_form(audio_channel=0),
    )

    decision = service.analysis_decision(draft)

    assert decision.allowed is False
    assert decision.status == "blocked"
    assert decision.reason == REAL_MULTISINE_BLOCK_MESSAGE
    saved = service.save_draft(
        service.with_session_root(draft, tmp_path / "real_multisine_registration")
    )
    assert saved.metadata_path.is_file()
    with pytest.raises(PermissionError, match="P8-A"):
        SingleMeasurementWorker(
            PROJECT_ROOT, output_root=tmp_path / "runs"
        ).prepare(saved)


def test_saving_draft_creates_versioned_ui_session_reports_without_copying_raw(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("* SPL\n1000 1\n2000 2\n3000 3\n4000 4\n5000 5\n", encoding="utf-8")
    before = source.read_bytes()
    service = MeasurementDraftService(PROJECT_ROOT)
    draft = service.build_draft(
        route=UsageRoute.OFFICIAL_REFERENCE,
        measurement_mode=MeasurementMode.REW_SWEEP,
        preflight=service.preflight_rew(source),
        form=MetadataFormValues(provenance_uri="https://example.invalid/reference"),
    )

    draft = service.with_session_root(draft, tmp_path / "ui_sessions")
    saved = service.save_draft(draft)

    assert saved.revision == 1
    assert saved.session_directory.name == "rev-001"
    assert saved.metadata_path.is_file()
    assert saved.config_snapshot_path.is_file()
    assert saved.step_report_markdown.is_file()
    assert saved.step_report_html.is_file()
    assert saved.input_hashes_path.is_file()
    assert saved.technical_log_path.is_file()
    assert (
        saved.session_directory / "ui_session_manifest.sha256"
    ).read_text(encoding="ascii") == hashlib.sha256(
        (saved.session_directory / "ui_session_manifest.json").read_bytes()
    ).hexdigest()
    assert source.read_bytes() == before
    hashes = json.loads(saved.input_hashes_path.read_text(encoding="utf-8"))
    assert hashes[0]["sha256"] == hashlib.sha256(before).hexdigest()
    assert MeasurementMeta.from_dict(
        json.loads(saved.metadata_path.read_text(encoding="utf-8"))
    ) == saved.metadata

    worker = SingleMeasurementWorker(PROJECT_ROOT, output_root=tmp_path / "runs")
    invocation = worker.prepare(saved)
    assert invocation.program
    assert invocation.arguments[0].endswith("run_pipeline.py")
    assert invocation.arguments[1::2] == (
        "--config",
        "--input",
        "--metadata",
        "--output-root",
        "--run-id",
    )
    assert invocation.output_directory == (
        tmp_path
        / "runs/external_reference/software_validation"
        / saved.draft.run_id
    )
    invocation.output_directory.mkdir(parents=True)
    with pytest.raises(FileExistsError, match="already exists"):
        worker.prepare(saved)

    invocation.output_directory.rmdir()
    source.write_text("* changed after registration", encoding="utf-8")
    with pytest.raises(ValueError, match="input hash mismatch"):
        worker.prepare(saved)

    with pytest.raises(FileExistsError, match="already registered"):
        service.save_draft(draft)

    first_metadata_bytes = saved.metadata_path.read_bytes()
    revised = service.save_draft(draft, revision_reason="operator correction")
    assert revised.revision == 2
    assert revised.session_directory.name == "rev-002"
    assert revised.draft.run_id == f"{saved.draft.run_id}-r002"
    assert saved.metadata_path.read_bytes() == first_metadata_bytes
    revision_record = json.loads(
        revised.revision_record_path.read_text(encoding="utf-8")
    )
    assert revision_record["supersedes_revision"] == 1
    assert revision_record["reason"] == "operator correction"


def test_multisine_saved_snapshot_canonically_points_to_selected_manifest(
    tmp_path: Path,
) -> None:
    recording, manifest = _multisine_files(tmp_path)
    service = MeasurementDraftService(PROJECT_ROOT)
    draft = service.build_draft(
        route=UsageRoute.SIMULATED_PRACTICE,
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        preflight=service.preflight_multisine(recording, manifest, audio_channel=0),
        form=_real_form(
            audio_channel=0,
            experiment_step="SIMULATED_PRACTICE",
            provenance_uri="ui://simulated-practice",
        ),
    )
    # Redirect only UI staging so this test cannot collide with repository outputs.
    draft = service.with_session_root(draft, tmp_path / "ui_sessions")

    saved = service.save_draft(draft)

    import yaml

    snapshot = yaml.safe_load(saved.config_snapshot_path.read_text(encoding="utf-8"))
    assert Path(snapshot["paths"]["stimuli"]).resolve() == manifest.parent.parent.resolve()
    assert snapshot["stimulus_id"] == "stim-1"
    assert snapshot["tone_set_id"] == "tones-1"
    sidecar = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
    assert Path(sidecar["sidecar_path"]).resolve() == saved.metadata_path.resolve()
    assert sidecar["recording_sha256"] == hashlib.sha256(recording.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("outcome", "exit_code", "expected"),
    [
        (ProcessOutcome.SUCCEEDED, 0, SingleMeasurementStatus.COMPLETED),
        (ProcessOutcome.FAILED, 1, SingleMeasurementStatus.FAILED),
        (ProcessOutcome.FAILED, 2, SingleMeasurementStatus.MANUAL_REVIEW),
        (ProcessOutcome.FAILED, 3, SingleMeasurementStatus.BLOCKED_RESEARCH_GATE),
        (ProcessOutcome.FAILED, 4, SingleMeasurementStatus.WARNING),
        (ProcessOutcome.CANCELLED, 15, SingleMeasurementStatus.CANCELLED),
    ],
)
def test_single_measurement_exit_status_mapping(outcome, exit_code, expected) -> None:
    assert map_single_measurement_status(outcome, exit_code) is expected


def test_run_result_report_uses_backend_manifest_as_authority_and_hashes_outputs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("* SPL\n1000 1\n2000 2\n3000 3\n4000 4\n5000 5\n", encoding="utf-8")
    service = MeasurementDraftService(PROJECT_ROOT)
    draft = service.with_session_root(
        service.build_draft(
            route=UsageRoute.OFFICIAL_REFERENCE,
            measurement_mode=MeasurementMode.REW_SWEEP,
            preflight=service.preflight_rew(source),
            form=MetadataFormValues(provenance_uri="https://example.invalid/ref"),
        ),
        tmp_path / "sessions",
    )
    saved = service.save_draft(draft)
    output = tmp_path / "run output"
    output.mkdir()
    artifact = output / "quality_control.csv"
    artifact.write_text("status\nwarning\n", encoding="utf-8")
    manifest = {
        "processing_status": "completed",
        "success": False,
        "qc_status": "warning",
        "phase_status": "unavailable",
        "eligible_for_scientific_analysis": False,
        "stage_gate": {"P1": "passed", "P2_A": "warning"},
    }
    manifest_path = output / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (output / "run_manifest.sha256").write_text(
        hashlib.sha256(manifest_path.read_bytes()).hexdigest(), encoding="ascii"
    )

    result = service.record_run_result(
        saved,
        output_directory=output,
        status="warning",
        program="python",
        arguments=("run_pipeline.py", "--config", "resolved config.yaml"),
        exit_code=4,
        stdout="structured output",
        stderr="stage gate note",
    )

    assert result.status == "warning"
    assert result.success is False
    assert result.qc_status == "warning"
    assert result.run_result_json.is_file()
    assert (
        saved.session_directory / "run_result.sha256"
    ).read_text(encoding="ascii") == hashlib.sha256(
        result.run_result_json.read_bytes()
    ).hexdigest()
    assert result.run_report_markdown.is_file()
    assert result.run_report_html.is_file()
    assert result.stdout_log.read_text(encoding="utf-8") == "structured output"
    hashes = json.loads(result.output_hashes_json.read_text(encoding="utf-8"))
    assert any(row["path"].endswith("quality_control.csv") for row in hashes)
    with pytest.raises(FileExistsError, match="already recorded"):
        service.record_run_result(
            saved,
            output_directory=output,
            status="warning",
            program="python",
            arguments=(),
            exit_code=4,
            stdout="",
            stderr="",
        )

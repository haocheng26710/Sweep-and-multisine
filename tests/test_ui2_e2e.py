from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess

from acoustic_encoder.config import load_config
from acoustic_encoder.mock_data import generate_dual_mode_mock
from acoustic_encoder.schemas import MeasurementMode
from acoustic_encoder.ui.measurement_workflow import (
    MetadataFormValues,
    MeasurementDraftService,
    UsageRoute,
)
from acoustic_encoder.ui.workers import (
    ProcessOutcome,
    SingleMeasurementWorker,
    map_single_measurement_status,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _execute(saved, output_root: Path):
    worker = SingleMeasurementWorker(PROJECT_ROOT, output_root=output_root)
    invocation = worker.prepare(saved)
    completed = subprocess.run(
        [invocation.program, *invocation.arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    outcome = (
        ProcessOutcome.SUCCEEDED
        if completed.returncode == 0
        else ProcessOutcome.FAILED
    )
    return invocation, completed, map_single_measurement_status(
        outcome, completed.returncode
    )


def test_official_rew_ui_registration_to_pipeline_e2e(tmp_path: Path) -> None:
    source = PROJECT_ROOT / "tests/fixtures/rew/external_reference/BW M1.txt"
    service = MeasurementDraftService(PROJECT_ROOT)
    draft = service.with_session_root(
        service.build_draft(
            route=UsageRoute.OFFICIAL_REFERENCE,
            measurement_mode=MeasurementMode.REW_SWEEP,
            preflight=service.preflight_rew(source),
            form=MetadataFormValues(
                provenance_uri=(
                    PROJECT_ROOT
                    / "tests/fixtures/rew/external_reference/manifest.json"
                ).as_posix()
            ),
        ),
        tmp_path / "sessions",
    )
    saved = service.save_draft(draft)

    invocation, completed, status = _execute(saved, tmp_path / "outputs")

    assert completed.returncode == 0, completed.stderr
    assert status.value == "completed"
    manifest = json.loads(
        (invocation.output_directory / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["data_origin"] == "external_reference"
    assert manifest["dataset_role"] == "parser_fixture"
    assert manifest["eligible_for_scientific_analysis"] is False
    assert (invocation.output_directory / "spectrum_data.json").is_file()


def test_simulated_multisine_ui_registration_to_p8_e2e(tmp_path: Path) -> None:
    stimulus = load_config(
        PROJECT_ROOT / "config/stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config/default.yaml",
    )["stimulus"]
    mock_root = tmp_path / "mock with spaces"
    mock_manifest_path = generate_dual_mode_mock(
        mock_root,
        deepcopy(stimulus),
        configurations=["U4ENC"],
        angles_deg=[90],
        random_state=20260810,
        recording_delay_samples=1379,
    )
    mock_manifest = json.loads(mock_manifest_path.read_text(encoding="utf-8"))
    sample = next(
        item
        for item in mock_manifest["samples"]
        if item["measurement_mode"] == "schroeder_multisine"
    )
    recording = Path(sample["source_path"])
    stimulus_manifest = next(
        (mock_root / "stimuli").glob("*/stimulus_manifest.json")
    )
    service = MeasurementDraftService(PROJECT_ROOT)
    draft = service.with_session_root(
        service.build_draft(
            route=UsageRoute.SIMULATED_PRACTICE,
            measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
            preflight=service.preflight_multisine(
                recording, stimulus_manifest, audio_channel=0
            ),
            form=MetadataFormValues(
                device_version="V2",
                configuration="U4ENC",
                angle_deg="90",
                session_id="S01",
                repeat_type="CONT",
                repeat_id="R01",
                reposition_round_id="P01",
                assembly_id="A01",
                acquisition_block_id="B01",
                experiment_step="SIMULATED_PRACTICE",
                date_time="2026-08-10T12:00:00+01:00",
                audio_channel=0,
                provenance_uri=mock_manifest_path.as_posix(),
            ),
        ),
        tmp_path / "sessions",
    )
    saved = service.save_draft(draft)

    invocation, completed, status = _execute(saved, tmp_path / "outputs")

    assert completed.returncode == 0, completed.stderr
    assert status.value == "completed"
    manifest = json.loads(
        (invocation.output_directory / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["data_origin"] == "simulated"
    assert manifest["run_purpose"] == "software_validation"
    assert manifest["eligible_for_scientific_analysis"] is False
    assert manifest["stage_gate"]["P8"] == "completed"
    for name in (
        "transfer_tones.csv",
        "tone_quality.csv",
        "clock_drift_qc.csv",
        "measurement_qc.csv",
        "spectrum_data.json",
    ):
        assert (invocation.output_directory / name).is_file()

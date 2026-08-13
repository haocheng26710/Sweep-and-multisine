from __future__ import annotations

import json
from pathlib import Path

from acoustic_encoder.schemas import MeasurementMode, artifact_sha256
from acoustic_encoder.ui.experiment_plan import (
    ChecklistStatus,
    ExperimentPlan,
    ExperimentPlanService,
    ExperimentRole,
    PlanConditionBlock,
    SafetyChecklist,
    SafetyChecklistItem,
)
from acoustic_encoder.ui.simulated_flow import SimulatedFlowService
from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.ui.measurement_workflow import UsageRoute


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ready_checklist() -> SafetyChecklist:
    return SafetyChecklist(
        schema_version="1.0.0",
        items=tuple(
            SafetyChecklistItem(
                check_id=check_id,
                status=ChecklistStatus.DECLARED_PASS,
                operator="FIX6 Operator",
                recorded_at="2026-08-13T10:00:00+01:00",
                note="simulated software-validation declaration",
                evidence_path=f"evidence/{check_id}.txt",
            )
            for check_id in SafetyChecklist.required_check_ids()
        ),
    )


def _multisine_plan() -> ExperimentPlan:
    return ExperimentPlan(
        schema_version="1.0.0",
        plan_id="fix6 simulated 32",
        experiment_name="FIX6 simulated route",
        research_question="Software workflow validation only",
        operator="FIX6 Operator",
        plan_version="1",
        created_at="2026-08-13T10:00:00+01:00",
        timezone="Europe/London",
        device_version="V2",
        device_chain="simulator -> P8",
        calibration_uri="mock://calibration-not-applicable",
        provenance_uri="mock://DEV-UI4-FIX6",
        output_root="outputs/ui_simulated_flow",
        condition_blocks=(
            PlanConditionBlock(
                block_id="main",
                configurations=("U4SYM", "U4ENC"),
                angles_deg=(0.0, 90.0, 180.0, 270.0),
                sessions=("S01",),
                acquisition_blocks=("B01",),
                measurement_modes=(MeasurementMode.SCHROEDER_MULTISINE,),
                experiment_role=ExperimentRole.TRAINING,
                cont_repeats=2,
                repos_rounds=1,
                repos_repeats_per_round=1,
                reasm_assemblies=1,
                reasm_repeats_per_assembly=1,
                stimulus_id="ms_broadband_1k_8k_100hz_v1",
                tone_set_id="broadband_1k_8k_100hz_v1",
                sample_rate_hz=48000,
                audio_channel=0,
            ),
        ),
    )


def _saved_plan(tmp_path: Path):
    service = ExperimentPlanService(tmp_path / "plans")
    saved = service.save_revision(_multisine_plan(), _ready_checklist())
    assert len(saved.samples) == 32
    return saved


def test_step04_generates_and_reverifies_immutable_plan_bound_stimulus(
    tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")

    generated = service.generate_stimulus(saved.directory)
    verified = service.generate_stimulus(saved.directory)
    manifest = json.loads(generated.manifest_path.read_text(encoding="utf-8"))
    hashes = json.loads(generated.hashes_path.read_text(encoding="utf-8"))

    assert verified == generated
    assert manifest["stimulus_id"] == saved.samples[0].stimulus_id
    assert manifest["tone_set_id"] == saved.samples[0].tone_set_id
    assert manifest["sample_rate_hz"] == saved.samples[0].sample_rate_hz
    assert generated.wav_path.is_file()
    assert generated.tones_path.is_file()
    assert hashes["plan_revision_path"] == saved.directory.as_posix()
    assert hashes["scientifically_eligible"] is False
    for artifact in hashes["artifacts"]:
        path = generated.directory / artifact["path"]
        assert artifact_sha256(path) == artifact["sha256"]


def test_step05_generates_all_32_explicit_simulated_recordings(
    tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    stimulus = service.generate_stimulus(saved.directory)

    batch = service.generate_simulated_acquisition(
        saved.directory,
        stimulus.manifest_path,
        random_state=20260813,
    )
    verified = service.load_acquisition_batch(batch.manifest_path)
    payload = json.loads(batch.manifest_path.read_text(encoding="utf-8"))

    assert verified.manifest_path == batch.manifest_path
    assert payload["expected_sample_count"] == 32
    assert payload["generated_sample_count"] == 32
    assert payload["data_origin"] == "simulated"
    assert payload["dataset_role"] == "software_validation"
    assert payload["run_purpose"] == "software_validation"
    assert payload["scientifically_eligible"] is False
    assert {row["expected_sample"]["repeat_type"] for row in payload["samples"]} == {
        "CONT", "REPOS", "REASM",
    }
    assert {row["expected_sample"]["configuration_id"] for row in payload["samples"]} == {
        "U4SYM", "U4ENC",
    }
    assert {row["expected_sample"]["angle_deg"] for row in payload["samples"]} == {
        0.0, 90.0, 180.0, 270.0,
    }
    assert {row["expected_sample"]["sample_id"] for row in payload["samples"]} == {
        sample.sample_id for sample in saved.samples
    }
    for row in payload["samples"]:
        recording = batch.directory / row["recording_path"]
        sidecar = batch.directory / row["sidecar_path"]
        assert artifact_sha256(recording) == row["recording_sha256"]
        assert artifact_sha256(sidecar) == row["sidecar_sha256"]
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        assert metadata["sample_id"] == row["expected_sample"]["sample_id"]
        assert metadata["eligible_for_scientific_analysis"] is False


def test_step06_processes_and_registers_all_32_without_dense_fabrication(
    tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    stimulus = service.generate_stimulus(saved.directory)
    batch = service.generate_simulated_acquisition(
        saved.directory, stimulus.manifest_path, random_state=20260813
    )

    processed = service.process_simulated_batch(batch.manifest_path)
    payload = json.loads(processed.manifest_path.read_text(encoding="utf-8"))

    assert processed.status == "passed"
    assert processed.processed_count == 32
    assert payload["registered_sample_count"] == 32
    assert payload["failed_count"] == 0
    assert payload["cancelled"] is False
    assert payload["scientifically_eligible"] is False
    assert payload["final_test_read"] is False
    assert {row["feature_set_status"] for row in payload["samples"]} == {
        "not_applicable_sparse"
    }
    for row in payload["samples"]:
        session_manifest = Path(row["ui_session_manifest_path"])
        output = Path(row["output_directory"])
        assert artifact_sha256(session_manifest) == row["ui_session_manifest_sha256"]
        assert (output / "spectrum_data.json").is_file()
        assert (output / "spectrum_data.npz").is_file()
        assert not (output / "processed").exists()


def test_step06_cancel_records_partial_audit_without_pass(
    tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    stimulus = service.generate_stimulus(saved.directory)
    batch = service.generate_simulated_acquisition(saved.directory, stimulus.manifest_path)
    calls = 0

    def cancel_after_first() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    result = service.process_simulated_batch(
        batch.manifest_path,
        processing_id="cancel-test",
        cancel_requested=cancel_after_first,
    )
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.status == "cancelled"
    assert 0 < result.processed_count < 32
    assert payload["cancelled"] is True
    assert payload["status"] == "cancelled"
    assert payload["registered_sample_count"] == result.processed_count


def test_step07_explicit_sparse_dataset_is_complete_and_routes_away_from_p2b(
    tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    stimulus = service.generate_stimulus(saved.directory)
    batch = service.generate_simulated_acquisition(saved.directory, stimulus.manifest_path)
    processed = service.process_simulated_batch(batch.manifest_path)

    audit = service.verify_processed_dataset(processed.manifest_path)
    payload = json.loads(audit.manifest_path.read_text(encoding="utf-8"))

    assert audit.status == "passed"
    assert payload["expected_count"] == 32
    assert payload["expected_and_present_count"] == 32
    assert payload["missing_count"] == 0
    assert payload["duplicate_count"] == 0
    assert payload["unexpected_count"] == 0
    assert payload["p2_b_status"] == "not_applicable_sparse"
    assert payload["downstream_route"] == "tone_p8_dataset_quality"
    assert payload["scientifically_eligible"] is False
    assert payload["final_test_read"] is False


def test_step07_rejects_missing_duplicate_identity_and_hash_tamper(
    tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    stimulus = service.generate_stimulus(saved.directory)
    batch = service.generate_simulated_acquisition(saved.directory, stimulus.manifest_path)
    processed = service.process_simulated_batch(batch.manifest_path)
    original = json.loads(processed.manifest_path.read_text(encoding="utf-8"))

    missing = {**original, "samples": original["samples"][:-1]}
    processed.manifest_path.write_text(
        json.dumps(missing, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    processed.manifest_hash_path.write_text(
        artifact_sha256(processed.manifest_path), encoding="ascii"
    )
    try:
        service.verify_processed_dataset(processed.manifest_path, audit_id="missing")
    except ValueError as error:
        assert "missing" in str(error).lower()
    else:
        raise AssertionError("missing sample was accepted")

    duplicate = {**original, "samples": [*original["samples"], original["samples"][0]]}
    processed.manifest_path.write_text(
        json.dumps(duplicate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    processed.manifest_hash_path.write_text(
        artifact_sha256(processed.manifest_path), encoding="ascii"
    )
    try:
        service.verify_processed_dataset(processed.manifest_path, audit_id="duplicate")
    except ValueError as error:
        assert "duplicate" in str(error).lower()
    else:
        raise AssertionError("duplicate sample was accepted")

    processed.manifest_path.write_text(
        json.dumps(original, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Deliberately retain the previous digest to exercise the outer integrity gate.
    try:
        service.verify_processed_dataset(processed.manifest_path, audit_id="tamper")
    except ValueError as error:
        assert "hash" in str(error).lower()
    else:
        raise AssertionError("tampered processing manifest was accepted")


def test_steps04_to06_pages_are_real_route_aware_controls(
    qtbot, tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    window = MainWindow(PROJECT_ROOT, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window)
    window._plan_saved(saved)

    window.select_step("stimulus")
    assert window.action_stack.currentWidget() is window.stimulus_page
    assert window.stimulus_page.generate_button.isEnabled()
    window.stimulus_page.generate()
    assert window.state.step("stimulus").status.value == "passed"

    window.select_step("external_acquisition")
    assert window.action_stack.currentWidget() is window.acquisition_page
    window.acquisition_page.generate()
    assert window.state.step("external_acquisition").status.value == "passed"
    assert window.simulated_batch_page.batch is not None

    window.select_step("single_measurement")
    assert window.action_stack.currentWidget() is window.simulated_batch_page
    assert window.simulated_batch_page.run_button.isEnabled()

    window.set_usage_route(UsageRoute.OFFICIAL_REFERENCE, force=True)
    window.select_step("stimulus")
    assert not window.stimulus_page.generate_button.isEnabled()
    assert "不生成刺激" in window.stimulus_page.route_label.text()
    window.select_step("single_measurement")
    assert window.action_stack.currentWidget() is window.single_measurement_page

    window.set_usage_route(UsageRoute.REAL_DIAGNOSTIC, force=True)
    window.select_step("external_acquisition")
    assert not window.acquisition_page.generate_button.isEnabled()
    assert "P8-A" in window.acquisition_page.instructions.text()


def test_qt_step03_to07_32_sample_e2e_uses_background_worker(
    qtbot, tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    window = MainWindow(PROJECT_ROOT, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window)
    window._plan_saved(saved)
    window.stimulus_page.generate()
    window.acquisition_page.generate()

    window.simulated_batch_page.start()
    qtbot.waitUntil(
        lambda: not window.simulated_batch_page.is_running,
        timeout=90000,
    )

    state = service_state = window.simulated_flow_service.load_state()
    processing_ref = service_state["artifacts"].get("processing_manifest")
    assert processing_ref is not None, window.result_label.text()
    assert Path(processing_ref["path"]).is_file()
    assert window.state.step("single_measurement").status.value == "passed"
    assert window.state.step("dataset").status.value == "passed"
    assert window.simulated_batch_page.progress.value() == 32
    assert len(window.dataset_page.registrations) == 32
    assert "32/32 expected_and_present" in window.dataset_page.summary_label.text()
    assert "not_applicable_sparse" in window.dataset_page.summary_label.text()
    assert not window.dataset_page.run_p2b_button.isEnabled()

    window.simulated_flow_service.record_ui_step("environment", "passed")
    window.simulated_flow_service.record_ui_step("usage", "passed")
    window.close()
    restored = MainWindow(PROJECT_ROOT, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(restored)
    assert [
        restored.state.step(step_id).status.value
        for step_id in (
            "environment", "usage", "plan", "stimulus",
            "external_acquisition", "single_measurement", "dataset",
        )
    ] == ["passed"] * 7
    assert len(restored.dataset_page.registrations) == 32
    assert restored.simulated_flow_service.load_state()["final_test_read"] is False


def test_qt_batch_cancel_is_cooperative_and_audited(
    qtbot, tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    window = MainWindow(PROJECT_ROOT, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window)
    window._plan_saved(saved)
    window.stimulus_page.generate()
    window.acquisition_page.generate()

    window.simulated_batch_page.start()
    window.simulated_batch_page.cancel()
    qtbot.waitUntil(
        lambda: not window.simulated_batch_page.is_running,
        timeout=30000,
    )

    state = window.simulated_flow_service.load_state()
    processing = Path(state["artifacts"]["processing_manifest"]["path"])
    payload = json.loads(processing.read_text(encoding="utf-8"))
    assert payload["status"] == "cancelled"
    assert payload["cancelled"] is True
    assert window.state.step("single_measurement").status.value == "warning"
    assert window.state.step("dataset").status.value != "passed"


def test_acquisition_gate_rejects_missing_duplicate_identity_and_file_tamper(
    tmp_path: Path,
) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    stimulus = service.generate_stimulus(saved.directory)
    batch = service.generate_simulated_acquisition(saved.directory, stimulus.manifest_path)
    original_text = batch.manifest_path.read_text(encoding="utf-8")
    original = json.loads(original_text)

    cases = []
    missing = {**original, "samples": original["samples"][:-1]}
    cases.append((missing, "missing"))
    duplicate = {**original, "samples": [*original["samples"], original["samples"][0]]}
    cases.append((duplicate, "duplicate"))
    identity = json.loads(original_text)
    identity["samples"][0]["expected_sample"]["configuration_id"] = "WRONG"
    cases.append((identity, "identity"))
    for payload, reason in cases:
        batch.manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        batch.manifest_hash_path.write_text(
            artifact_sha256(batch.manifest_path), encoding="ascii"
        )
        try:
            service.load_acquisition_batch(batch.manifest_path)
        except ValueError as error:
            assert reason in str(error).lower()
        else:
            raise AssertionError(f"{reason} acquisition was accepted")

    batch.manifest_path.write_text(original_text, encoding="utf-8")
    batch.manifest_hash_path.write_text(
        artifact_sha256(batch.manifest_path), encoding="ascii"
    )
    recording = batch.directory / original["samples"][0]["recording_path"]
    with recording.open("ab") as handle:
        handle.write(b"tamper")
    try:
        service.load_acquisition_batch(batch.manifest_path)
    except ValueError as error:
        assert "hash" in str(error).lower()
    else:
        raise AssertionError("tampered WAV was accepted")


def test_processing_refuses_an_existing_output_directory(tmp_path: Path) -> None:
    saved = _saved_plan(tmp_path)
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    stimulus = service.generate_stimulus(saved.directory)
    batch = service.generate_simulated_acquisition(saved.directory, stimulus.manifest_path)
    acquisition_hash = artifact_sha256(batch.manifest_path)
    existing = service.flow_root / "processing" / f"process-{acquisition_hash[:16]}"
    existing.mkdir(parents=True)

    try:
        service.process_simulated_batch(batch.manifest_path)
    except FileExistsError as error:
        assert str(existing) in str(error)
    else:
        raise AssertionError("existing processing directory was overwritten")

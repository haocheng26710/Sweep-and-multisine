from __future__ import annotations

from pathlib import Path
import json

from acoustic_encoder.ui.main_window import MainWindow
from acoustic_encoder.schemas import artifact_sha256
from acoustic_encoder.ui.services import humanize_exception
from acoustic_encoder.ui.simulated_flow import SimulatedFlowService
from acoustic_encoder.ui.state import StepStatus, WizardState
from test_ui4_fix6_simulated_flow import _multisine_plan, _ready_checklist


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ui_state_supports_not_applicable_and_sealed_as_terminal_safe_states() -> None:
    state = WizardState()

    state.transition("comparison", StepStatus.NOT_APPLICABLE)
    state.transition("modeling", StepStatus.NOT_APPLICABLE)
    state.transition("final_test", StepStatus.SEALED)
    state.transition("reports", StepStatus.READY)
    state.transition("reports", StepStatus.NOT_APPLICABLE)

    assert state.step("comparison").status is StepStatus.NOT_APPLICABLE
    assert state.step("modeling").status is StepStatus.NOT_APPLICABLE
    assert state.step("final_test").status is StepStatus.SEALED
    assert state.step("reports").status is StepStatus.NOT_APPLICABLE
    assert StepStatus.display_text(StepStatus.NOT_APPLICABLE) == "不适用（安全跳过）"
    assert StepStatus.display_text(StepStatus.SEALED) == "已封存（未读取）"


def test_sidebar_uses_human_readable_sparse_terminal_statuses(qtbot, tmp_path: Path) -> None:
    window = MainWindow(PROJECT_ROOT, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window)
    window.state.step("comparison").status = StepStatus.NOT_APPLICABLE
    window.state.step("modeling").status = StepStatus.NOT_APPLICABLE
    window.state.step("final_test").status = StepStatus.SEALED
    window._refresh_step_buttons()

    assert "不适用（安全跳过）" in window.step_buttons["comparison"].text()
    assert "不适用（安全跳过）" in window.step_buttons["modeling"].text()
    assert "已封存（未读取）" in window.step_buttons["final_test"].text()


def _explicit_sparse_audit(service: SimulatedFlowService, tmp_path: Path) -> Path:
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    manifest = audit_dir / "dataset_flow_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "simulated_flow_schema_version": "1.0.0",
                "status": "passed",
                "expected_count": 32,
                "expected_and_present_count": 32,
                "missing_count": 0,
                "duplicate_count": 0,
                "unexpected_count": 0,
                "qc_counts": {
                    "valid": 32,
                    "warning": 0,
                    "exclude_candidate": 0,
                    "unavailable": 0,
                },
                "p2_b_status": "not_applicable_sparse",
                "downstream_route": "tone_p8_dataset_quality",
                "data_origin": "simulated",
                "dataset_role": "software_validation",
                "run_purpose": "software_validation",
                "scientifically_eligible": False,
                "final_test_read": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest.with_suffix(".sha256").write_text(
        artifact_sha256(manifest), encoding="ascii"
    )
    return manifest


def test_explicit_sparse_audit_sets_safe_downstream_states(tmp_path: Path) -> None:
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    audit = _explicit_sparse_audit(service, tmp_path)

    state = service.apply_sparse_closeout(audit)

    assert state["steps"] == {
        "comparison": "not_applicable",
        "modeling": "not_applicable",
        "freeze": "blocked",
        "final_test": "sealed",
        "reports": "ready",
    }
    assert state["final_test_read"] is False
    assert state["scientifically_eligible"] is False
    assert state["closeout"]["freeze_reason"] == "missing_approved_p9d_freeze_authority"


def test_sparse_closeout_pages_disable_feature_only_actions_and_keep_final_sealed(
    qtbot, tmp_path: Path,
) -> None:
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    audit = _explicit_sparse_audit(service, tmp_path)
    window = MainWindow(PROJECT_ROOT, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window)

    window.activate_sparse_closeout(audit)

    assert window.state.step("comparison").status is StepStatus.NOT_APPLICABLE
    assert window.state.step("modeling").status is StepStatus.NOT_APPLICABLE
    assert window.state.step("freeze").status is StepStatus.BLOCKED
    assert window.state.step("final_test").status is StepStatus.SEALED
    assert window.state.step("reports").status is StepStatus.READY
    window.select_step("comparison")
    assert window.action_stack.currentWidget() is window.sparse_closeout_page
    assert "32/32 expected_and_present" in window.sparse_closeout_page.summary_label.text()
    assert "not_applicable_sparse" in window.sparse_closeout_page.summary_label.text()
    assert "tone_p8_dataset_quality" in window.sparse_closeout_page.summary_label.text()
    assert window.sparse_closeout_page.audit_button.isEnabled()
    assert not window.dataset_page.preview_p2b_button.isEnabled()
    assert not window.dataset_page.run_p2b_button.isEnabled()
    assert not window.analysis_page.prepare_button.isEnabled()
    assert not window.analysis_page.run_button.isEnabled()
    for button in (
        window.final_delivery_page.p9a_button,
        window.final_delivery_page.p9b_button,
        window.final_delivery_page.p9c_button,
        window.final_delivery_page.freeze_button,
        window.final_delivery_page.unseal_button,
    ):
        assert not button.isEnabled()
    window.select_step("final_test")
    assert "sealed" in window.sparse_closeout_page.detail_label.text()
    assert service.load_state()["final_test_read"] is False


def test_software_validation_summary_uses_only_hashed_explicit_chain_and_rev002(
    qtbot, tmp_path: Path,
) -> None:
    service = SimulatedFlowService(PROJECT_ROOT, tmp_path / "workspace")
    revision_1 = service.plan_service.save_revision(
        _multisine_plan(), _ready_checklist()
    )
    revision_2 = service.plan_service.save_revision(
        _multisine_plan(), _ready_checklist(), revision_reason="FIX7 UAT revision"
    )
    assert revision_1.revision == 1
    assert revision_2.revision == 2
    service.record_ui_step("environment", "passed")
    service.record_ui_step("usage", "passed")
    stimulus = service.generate_stimulus(revision_2.directory)
    batch = service.generate_simulated_acquisition(
        revision_2.directory, stimulus.manifest_path
    )
    processed = service.process_simulated_batch(batch.manifest_path)
    audit = service.verify_processed_dataset(processed.manifest_path)
    service.apply_sparse_closeout(audit.manifest_path)
    decoy = service.workspace_root / "outputs" / "unreferenced-decoy"
    decoy.mkdir(parents=True)
    (decoy / "dataset_flow_manifest.json").write_text(
        '{"scientifically_eligible": true}\n', encoding="utf-8"
    )

    exported = service.export_software_validation_summary(report_id="fix7-summary")
    manifest = json.loads(exported.manifest_path.read_text(encoding="utf-8"))

    assert exported.markdown_path.is_file()
    assert artifact_sha256(exported.manifest_path) == exported.manifest_hash_path.read_text(
        encoding="ascii"
    ).strip()
    assert manifest["steps"] == {
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
    assert manifest["plan"]["revision"] == 2
    assert manifest["plan"]["revision_label"] == "rev-002"
    assert manifest["dataset_counts"] == {
        "expected": 32,
        "expected_and_present": 32,
        "warning": 0,
        "failed": 0,
    }
    assert {item["role"] for item in manifest["artifacts"]} == {
        "workflow_state",
        "plan_manifest",
        "stimulus_manifest",
        "acquisition_manifest",
        "processing_manifest",
        "dataset_audit",
    }
    assert manifest["data_origin"] == "simulated"
    assert manifest["run_purpose"] == "software_validation"
    assert manifest["scientifically_eligible"] is False
    assert manifest["final_test_read"] is False
    assert manifest["eligible_for_research_conclusions"] is False
    assert all("unreferenced-decoy" not in item["path"] for item in manifest["artifacts"])

    window = MainWindow(PROJECT_ROOT, workspace_root=service.workspace_root)
    qtbot.addWidget(window)
    expected_statuses = {
        "environment": StepStatus.PASSED,
        "usage": StepStatus.PASSED,
        "plan": StepStatus.PASSED,
        "stimulus": StepStatus.PASSED,
        "external_acquisition": StepStatus.PASSED,
        "single_measurement": StepStatus.PASSED,
        "dataset": StepStatus.PASSED,
        "comparison": StepStatus.NOT_APPLICABLE,
        "modeling": StepStatus.NOT_APPLICABLE,
        "freeze": StepStatus.BLOCKED,
        "final_test": StepStatus.SEALED,
        "reports": StepStatus.READY,
    }
    assert {
        step_id: window.state.step(step_id).status for step_id in expected_statuses
    } == expected_statuses
    assert window.stimulus_page.saved_plan is not None
    assert window.stimulus_page.saved_plan.revision == 2
    window.select_step("reports")
    window.sparse_closeout_page.export_button.click()
    assert "software_validation_summary.md" in window.sparse_closeout_page.output_label.text()
    assert len(list((service.flow_root / "closeout_reports").iterdir())) == 2
    assert service.load_state()["final_test_read"] is False


def test_new_plan_revision_rebinds_step04_and_clears_stale_downstream_state(
    qtbot, tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    service = SimulatedFlowService(PROJECT_ROOT, workspace)
    revision_1 = service.plan_service.save_revision(
        _multisine_plan(), _ready_checklist()
    )
    revision_2 = service.plan_service.save_revision(
        _multisine_plan(), _ready_checklist(), revision_reason="correct UAT plan"
    )
    service.bind_plan(revision_1.directory)
    first_stimulus = service.generate_stimulus(revision_1.directory)
    service.record_ui_step("stimulus", "failed")
    state = service.bind_plan(revision_2.directory)

    assert state.revision == 2
    restored = service.load_state()
    assert restored["plan_revision_path"] == revision_2.directory.as_posix()
    assert restored["steps"]["plan"] == "passed"
    assert restored["steps"]["stimulus"] == "ready"
    assert "stimulus_hashes" not in restored["artifacts"]
    assert restored["final_test_read"] is False

    window = MainWindow(PROJECT_ROOT, workspace_root=workspace)
    qtbot.addWidget(window)
    assert window.stimulus_page.saved_plan is not None
    assert window.stimulus_page.saved_plan.revision == 2
    assert window.state.step("stimulus").status is StepStatus.READY
    rebound_stimulus = service.generate_stimulus(revision_2.directory)
    assert rebound_stimulus.waveform_sha256 == first_stimulus.waveform_sha256


def test_plan_revision_reason_and_p7_contract_errors_are_precise() -> None:
    revision_message, _ = humanize_exception(
        ValueError("a new plan revision requires revision_reason")
    )
    contract_message, _ = humanize_exception(
        ValueError(
            "plan/P7 stimulus contract mismatch: "
            "field=tone_set_id expected='tone-a' actual='tone-b'"
        )
    )

    assert "revision_reason" in revision_message
    assert "修订理由" in revision_message
    assert "field=tone_set_id" in contract_message
    assert "expected='tone-a'" in contract_message


def test_failed_stimulus_does_not_suggest_continuing_external_acquisition(
    qtbot, tmp_path: Path,
) -> None:
    window = MainWindow(PROJECT_ROOT, workspace_root=tmp_path / "workspace")
    qtbot.addWidget(window)

    window._simulated_step_status("stimulus", "failed")

    assert "修复" in window.next_step_label.text()
    assert "不要继续外部采集" in window.next_step_label.text()

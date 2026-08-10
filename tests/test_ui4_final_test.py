from __future__ import annotations

import json
from pathlib import Path
from dataclasses import replace

from acoustic_encoder.ui.final_test import (
    FinalTestGateRequest,
    FinalTestSafetyService,
    FinalTestState,
)


def _blocked_request() -> FinalTestGateRequest:
    return FinalTestGateRequest(
        plan_id="plan-1",
        entered_plan_id="plan-1",
        package_semantic_sha256="sha256:" + "a" * 64,
        entered_hash_fragment="aaaaaaaa",
        plan_frozen=True,
        package_frozen=True,
        package_self_check_passed=True,
        scope_matches_plan=True,
        training_development_complete=True,
        custodian="",
        approver="",
        approval_time_utc="",
        one_time_rule_confirmed=True,
        output_directory_empty=True,
        version_match=True,
        real_research_authority=False,
        unresolved_incidents=0,
        real_multisine_backend_approved=False,
        approval_record_path=None,
        operator="tester",
    )


def test_final_test_defaults_to_sealed_and_records_blocked_attempt_without_reading_data(tmp_path: Path) -> None:
    service = FinalTestSafetyService(tmp_path / "audit")
    sealed_file = tmp_path / "must-not-be-opened.final"

    decision = service.request_unseal(_blocked_request(), sealed_input=sealed_file)

    assert decision.allowed is False
    assert decision.state is FinalTestState.SEALED
    assert "real_research_authority" in decision.failed_checks
    assert "real_multisine_backend_approved" in decision.failed_checks
    assert sealed_file.exists() is False
    incidents = list((tmp_path / "audit").glob("final_test_access_incident_*.json"))
    assert len(incidents) == 1
    incident = json.loads(incidents[0].read_text(encoding="utf-8"))
    assert incident["content_read"] is False
    assert incident["final_test_path"] == str(sealed_file.resolve())


def test_final_test_approval_is_one_time_and_has_irreversible_state_transitions(tmp_path: Path) -> None:
    approval = tmp_path / "approval.json"
    approval.write_text("{}", encoding="utf-8")
    request = replace(
        _blocked_request(),
        custodian="custodian",
        approver="independent approver",
        approval_time_utc="2026-08-10T12:00:00+00:00",
        real_research_authority=True,
        real_multisine_backend_approved=True,
        approval_record_path=approval,
    )
    service = FinalTestSafetyService(tmp_path / "audit")

    first = service.request_unseal(request, sealed_input=tmp_path / "sealed.fixture")
    second = service.request_unseal(request, sealed_input=tmp_path / "sealed.fixture")
    service.mark_running()
    service.mark_completed()

    assert first.allowed is True
    assert first.state is FinalTestState.APPROVED_ONCE
    assert second.allowed is False
    assert second.failed_checks == ("one_time_evaluation_already_started",)
    assert service.state is FinalTestState.COMPLETED

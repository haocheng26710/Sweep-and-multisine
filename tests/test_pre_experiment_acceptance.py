from __future__ import annotations

from acoustic_encoder.pre_experiment_acceptance import (
    AcceptanceCheck,
    AcceptanceResult,
    AcceptanceStatus,
    ScenarioEvidence,
)


def _passing_checks(prefix: str, count: int) -> tuple[AcceptanceCheck, ...]:
    return tuple(
        AcceptanceCheck(
            check_id=f"{prefix}-{index}",
            status=AcceptanceStatus.PASS,
            required=True,
            reason="verified",
            evidence_files=(f"evidence/{prefix}-{index}.json",),
            verification="loader_verified",
        )
        for index in range(1, count + 1)
    )


def test_all_required_gates_and_clean_sealed_tree_are_diagnostic_ready() -> None:
    result = AcceptanceResult.build(
        acceptance_scope_id="dev-c16-scope",
        stage_checks=_passing_checks("T", 4),
        requirement_checks=_passing_checks("V2", 14),
        final_test_read=False,
        git_commit="a" * 40,
        git_dirty=False,
    )

    assert result.overall_status is AcceptanceStatus.PASS
    assert result.software_integration_ready is True
    assert result.ready_for_dev_d_diagnostic_experiment is True
    assert result.scientifically_eligible is False
    assert result.canonical_analysis is False
    assert result.deployment_eligible is False
    assert result.approved_real_calibration is False
    assert result.final_tone_set_frozen is False
    assert result.final_test_read is False


def test_expected_qc_rejection_counts_as_scenario_pass_without_hiding_failure() -> None:
    expected_rejection = ScenarioEvidence.evaluate(
        scenario_id="over-policy-drift",
        expected_status="exclude_candidate",
        actual_status="exclude_candidate",
        evidence={"signed_drift_ppm": 120.0, "final_decision": "exclude_candidate"},
    )
    unexpected_warning = ScenarioEvidence.evaluate(
        scenario_id="hash-tamper",
        expected_status="blocked",
        actual_status="warning",
        evidence={"reason": "hash mismatch"},
    )

    assert expected_rejection.expectation_matched is True
    assert expected_rejection.acceptance_status is AcceptanceStatus.PASS
    assert unexpected_warning.expectation_matched is False
    assert unexpected_warning.acceptance_status is AcceptanceStatus.FAIL


def test_final_test_read_is_audited_as_failed_and_never_ready() -> None:
    result = AcceptanceResult.build(
        acceptance_scope_id="dev-c16-scope",
        stage_checks=_passing_checks("T", 4),
        requirement_checks=_passing_checks("V2", 14),
        final_test_read=True,
        git_commit="a" * 40,
        git_dirty=False,
    )

    assert result.overall_status is AcceptanceStatus.FAIL
    assert result.final_test_read is True
    assert result.software_integration_ready is False
    assert result.ready_for_dev_d_diagnostic_experiment is False
    assert result.scientifically_eligible is False
    assert result.deployment_eligible is False

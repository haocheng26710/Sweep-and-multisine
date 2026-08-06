from __future__ import annotations

from pathlib import Path

from acoustic_encoder.pre_experiment_acceptance_runner import (
    run_t0_mathematical_consistency,
    run_t1_robustness_scenarios,
    run_t2_selection_classification,
    run_t3_end_to_end,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_t0_actual_identity_chain_preserves_tone_contract_and_known_h(tmp_path: Path) -> None:
    result = run_t0_mathematical_consistency(
        project_root=PROJECT_ROOT,
        evidence_root=tmp_path / "evidence",
        config_path=PROJECT_ROOT / "config" / "validation_dev_c16_acceptance.yaml",
    )

    assert result["status"] == "pass"
    assert result["identity_calibration_applied"] is False
    assert result["common_tone_count"] >= 5
    assert result["maximum_absolute_error_db"] <= result["configured_tolerance_db"]
    assert result["mean_absolute_error_db"] <= result["configured_tolerance_db"]
    assert result["rms_error_db"] <= result["configured_tolerance_db"]
    assert result["feature_names_identical"] is True
    assert result["tone_hash_identical"] is True
    assert result["quantity_unit_reference_identical"] is True
    assert result["no_interpolation_reorder_or_zero_fill"] is True
    assert result["artifact_hashes_verified"] is True
    assert result["data_origin"] == "simulated"
    assert result["run_purpose"] == "software_validation"
    assert result["scientifically_eligible"] is False


def test_t3_actual_persisted_chain_reaches_frozen_readout_and_audited_failure(tmp_path: Path) -> None:
    result = run_t3_end_to_end(
        project_root=PROJECT_ROOT,
        evidence_root=tmp_path / "e",
        config_path=PROJECT_ROOT / "config" / "validation_dev_c16_acceptance.yaml",
    )

    assert result["status"] == "pass"
    assert result["actual_persisted_chain"] == (
        "P7->S3->P8->P3-C->P4->P5->P9-C->P9-D->acceptance_report"
    )
    assert result["p4_metric_artifact_verified"] is True
    assert result["p5_prediction_artifact_verified"] is True
    assert result["p9_bridge_artifacts_verified"] is True
    assert result["readout_artifacts_verified"] is True
    assert result["predicted_direction_deg"] == 90.0
    assert result["second_direction_deg"] is not None
    assert result["margin"] is not None and result["margin"] >= 0.0
    assert result["readout_deterministic_repeat"] is True
    assert result["failure_path_status"] == "blocked"
    assert result["failure_path_prediction_available"] is False
    assert result["source_artifacts_unchanged"] is True
    assert result["final_test_read"] is False
    assert result["scientifically_eligible"] is False
    assert result["canonical_analysis"] is False
    assert result["deployment_eligible"] is False


def test_t1_preregistered_scenarios_match_recovery_and_qc_expectations(tmp_path: Path) -> None:
    result = run_t1_robustness_scenarios(
        project_root=PROJECT_ROOT,
        evidence_root=tmp_path / "evidence",
        config_path=PROJECT_ROOT / "config" / "validation_dev_c16_acceptance.yaml",
    )

    assert result["status"] == "pass"
    assert result["scenario_count"] == 9
    assert result["expectation_matched_count"] == 9
    assert result["all_artifact_hashes_verified"] is True
    by_id = {item["scenario_id"]: item for item in result["scenarios"]}
    assert by_id["correctable_drift"]["phase_status"] == "drift_corrected"
    assert by_id["over_policy_drift"]["actual_status"] == "exclude_candidate"
    assert by_id["clipping_warning"]["actual_status"] == "exclude_candidate"
    assert by_id["clipping_warning"]["clipping_status"] == "warning"
    assert by_id["missing_tone"]["missing_tone_count"] == 1
    assert by_id["relative_phase"]["phase_status"] == "relative_unreliable"
    assert by_id["relative_phase"]["magnitude_recovered"] is True


def test_t2_four_direction_fold_local_selection_and_classification_are_sealed(tmp_path: Path) -> None:
    result = run_t2_selection_classification(
        project_root=PROJECT_ROOT,
        evidence_root=tmp_path / "evidence",
        config_path=PROJECT_ROOT / "config" / "validation_dev_c16_acceptance.yaml",
    )

    assert result["status"] == "pass"
    assert result["direction_count"] == 4
    assert result["outer_fold_count"] == 3
    assert result["inner_fold_count"] == 6
    assert all(item["selected_tone_ids"] for item in result["folds"])
    assert all(item["training_held_disjoint"] for item in result["folds"])
    assert all(item["minimum_tone_status"] == "valid" for item in result["folds"])
    assert result["minimum_p4_retention"] >= 0.8
    assert result["minimum_sparse_balanced_accuracy"] >= 0.9
    assert result["minimum_sparse_macro_f1"] >= 0.9
    assert result["minimum_prediction_coverage"] == 1.0
    assert result["leakage_audit_passed"] is True
    assert result["final_test_read"] is False
    assert result["selection_lifecycle"] == "software_validation_candidate"
    assert result["artifact_hashes_verified"] is True

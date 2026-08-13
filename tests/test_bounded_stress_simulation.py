from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from acoustic_encoder.simulation.bounded_stress import (
    FROZEN_SCENARIO_IDS,
    assert_safe_simulation_path,
    build_sample_matrix,
    execute_prepared_simulation,
    frozen_scenarios,
    frozen_seeds,
    prepare_simulation_run,
    should_run_s3_64,
    simulate_scenario_seed,
    verify_prepared_manifests,
    verify_artifact_inventory,
    write_artifact_inventory,
)


def test_frozen_scenarios_and_seeds_match_sim0_rev001() -> None:
    scenarios = frozen_scenarios()
    seeds = frozen_seeds()

    assert tuple(item.scenario_id for item in scenarios) == FROZEN_SCENARIO_IDS
    assert len(scenarios) == 6
    assert seeds == tuple(range(2026090101, 2026090151))
    assert len(seeds) == len(set(seeds)) == 50


def test_32_and_64_sample_matrices_have_stable_unique_explicit_identity() -> None:
    small = build_sample_matrix(32)
    large = build_sample_matrix(64)

    assert len(small) == len({item.sample_id for item in small}) == 32
    assert len(large) == len({item.sample_id for item in large}) == 64
    assert {item.configuration_id for item in small} == {"U4ENC", "U4SYM"}
    assert {item.angle_deg for item in small} == {0.0, 90.0, 180.0, 270.0}
    assert {item.repeat_type for item in small} == {"CONT", "REPOS", "REASM"}
    assert build_sample_matrix(32) == small


def test_same_seed_is_reconstructable_and_different_seed_has_distinct_identity() -> None:
    scenario = frozen_scenarios()[2]
    first = simulate_scenario_seed(scenario, 2026090101, sample_count=32)
    rebuilt = simulate_scenario_seed(scenario, 2026090101, sample_count=32)
    other = simulate_scenario_seed(scenario, 2026090102, sample_count=32)

    assert first.to_dict() == rebuilt.to_dict()
    assert first.result_sha256 == rebuilt.result_sha256
    assert first.run_id != other.run_id
    assert first.result_sha256 != other.result_sha256


def test_null_and_level_only_injection_semantics_are_explicit() -> None:
    null = simulate_scenario_seed(frozen_scenarios()[0], 2026090101, sample_count=32)
    level = simulate_scenario_seed(frozen_scenarios()[1], 2026090101, sample_count=32)

    assert null.injection_audit["direction_shape_scale"] == {"U4ENC": 0.0, "U4SYM": 0.0}
    assert null.injection_audit["direction_level_offsets_db"] == [0.0, 0.0, 0.0, 0.0]
    assert level.injection_audit["direction_shape_scale"] == {"U4ENC": 0.0, "U4SYM": 0.0}
    assert level.injection_audit["direction_level_offsets_db"] == [-1.5, -0.5, 0.5, 1.5]
    assert level.metrics["U4ENC"]["G_raw"] > level.metrics["U4ENC"]["G_demeaned"]


def test_positive_moderate_reassembly_and_quality_scenarios_keep_frozen_semantics() -> None:
    scenarios = {item.scenario_id: item for item in frozen_scenarios()}

    assert scenarios["S2_POSITIVE_CONTROL"].direction_shape_scale_enc == 1.0
    assert scenarios["S3_MODERATE_REALISTIC"].direction_shape_scale_enc == 0.35
    assert scenarios["S3_MODERATE_REALISTIC"].waveform_noise_std_fs == 0.00050
    assert scenarios["S4_REASSEMBLY_STRESS"].repos_shape_sd_db == scenarios["S3_MODERATE_REALISTIC"].repos_shape_sd_db
    assert scenarios["S4_REASSEMBLY_STRESS"].reasm_shape_sd_db > scenarios["S3_MODERATE_REALISTIC"].reasm_shape_sd_db

    quality = simulate_scenario_seed(
        scenarios["S5_DATA_QUALITY_STRESS"], 2026090101, sample_count=32
    )
    assert quality.qc["injected_anomaly_count"] == 8
    assert quality.qc["detected_or_safely_downgraded_count"] == 8
    assert quality.qc["scientific_pass_blocked_by_qc"] is True
    assert {item["kind"] for item in quality.injection_audit["anomalies"]} == {
        "missing_tone", "noise", "clock_drift", "clipping"
    }


def test_scenario_parameters_cannot_be_changed_at_execution() -> None:
    altered = replace(frozen_scenarios()[3], repos_shape_sd_db=0.49)
    with pytest.raises(ValueError, match="frozen SIM-0"):
        simulate_scenario_seed(altered, 2026090101, sample_count=32)


def test_grouped_validation_has_no_sample_or_group_leakage() -> None:
    result = simulate_scenario_seed(
        frozen_scenarios()[2], 2026090101, sample_count=32
    )
    for fold in result.grouped_validation_audit:
        assert fold["group_leakage"] is False
        assert not set(fold["train_sample_ids"]) & set(fold["test_sample_ids"])


def test_64_sample_branch_uses_only_frozen_trigger_boundaries() -> None:
    eligible = {
        "S0_NULL": 0.10,
        "S1_LEVEL_ONLY": 0.10,
        "S2_POSITIVE_CONTROL": 0.90,
        "S3_MODERATE_REALISTIC": 0.79,
        "S5_DATA_QUALITY_STRESS": 0.95,
    }
    assert should_run_s3_64(eligible) is True
    assert should_run_s3_64({**eligible, "S3_MODERATE_REALISTIC": 0.80}) is False
    assert should_run_s3_64({**eligible, "S3_MODERATE_REALISTIC": 0.49}) is False
    assert should_run_s3_64({**eligible, "S2_POSITIVE_CONTROL": 0.89}) is False
    assert should_run_s3_64({**eligible, "S0_NULL": 0.11}) is False


def test_prepared_manifests_freeze_all_inputs_before_results(tmp_path: Path) -> None:
    output = tmp_path / "outputs" / "simulated" / "software_validation" / "bounded_stress" / "SIM-1_TEST"
    prepared = prepare_simulation_run(
        output_directory=output,
        project_root=Path(__file__).resolve().parents[1],
        source_commit="a" * 40,
        git_dirty=False,
        created_at="2026-08-13T12:00:00+01:00",
        timezone="Europe/London",
    )

    assert prepared.output_directory == output
    assert {path.name for path in prepared.manifest_paths} == {
        "scenario_manifest.json", "seed_manifest.json", "simulation_run_plan.json"
    }
    assert not (output / "run_results.csv").exists()
    plan = json.loads((output / "simulation_run_plan.json").read_text(encoding="utf-8"))
    assert len(plan["base_runs"]) == 300
    assert len(plan["conditional_s3_64_runs"]) == 50
    assert plan["maximum_valid_run_count"] == 350
    assert plan["final_test_read"] is False
    assert verify_prepared_manifests(output) == prepared.manifest_sha256


def test_dirty_source_and_final_test_paths_are_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="clean Git worktree"):
        prepare_simulation_run(
            output_directory=tmp_path / "dirty",
            project_root=Path(__file__).resolve().parents[1],
            source_commit="b" * 40,
            git_dirty=True,
            created_at="2026-08-13T12:00:00+01:00",
            timezone="Europe/London",
        )
    with pytest.raises(ValueError, match="final-test"):
        assert_safe_simulation_path(tmp_path / "final_test" / "sealed.json")


def test_checkpoint_resume_skips_hash_verified_completed_seed(tmp_path: Path) -> None:
    output = tmp_path / "outputs" / "simulated" / "software_validation" / "bounded_stress" / "SIM-1_RESUME"
    prepare_simulation_run(
        output_directory=output,
        project_root=Path(__file__).resolve().parents[1],
        source_commit="c" * 40,
        git_dirty=False,
        created_at="2026-08-13T12:00:00+01:00",
        timezone="Europe/London",
    )
    first = execute_prepared_simulation(output, maximum_new_runs=2)
    first_paths = tuple(sorted(output.glob("per-scenario/*/n32/*.json")))
    first_hashes = {path: path.read_bytes() for path in first_paths}
    resumed = execute_prepared_simulation(output, maximum_new_runs=2)
    all_paths = tuple(sorted(output.glob("per-scenario/*/n32/*.json")))

    assert first.completed_run_count == 2
    assert resumed.completed_run_count == 4
    assert len(all_paths) == 4
    assert all(path.read_bytes() == payload for path, payload in first_hashes.items())
    assert len({json.loads(path.read_text(encoding="utf-8"))["run_id"] for path in all_paths}) == 4


def test_artifact_inventory_revalidates_every_hash_and_detects_tamper(tmp_path: Path) -> None:
    output = tmp_path / "outputs" / "simulated" / "software_validation" / "bounded_stress" / "SIM-1_HASH"
    prepare_simulation_run(
        output_directory=output,
        project_root=Path(__file__).resolve().parents[1],
        source_commit="d" * 40,
        git_dirty=False,
        created_at="2026-08-13T12:00:00+01:00",
        timezone="Europe/London",
    )
    execute_prepared_simulation(output, maximum_new_runs=1)
    write_artifact_inventory(output)
    verified = verify_artifact_inventory(output)
    assert "scenario_manifest.json" in verified
    result_path = next(output.glob("per-scenario/*/n32/*.json"))
    result_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_artifact_inventory(output)

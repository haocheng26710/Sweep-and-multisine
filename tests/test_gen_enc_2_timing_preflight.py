from __future__ import annotations

import json
import hashlib
import importlib.util
from pathlib import Path
import subprocess

import numpy as np
import pytest
from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]
HAND_01 = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/HAND_DESIGNED/HAND_01.identity.json"
FIXTURE = REPO / "tests/fixtures/gen_enc_2_timing_preflight/workload_contract.json"
INSTANCE_ROOT = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances"


def _member() -> dict:
    return json.loads(HAND_01.read_text(encoding="utf-8"))


def _neutral_nuisance() -> dict[str, float]:
    return {
        "snr_db": 40.0,
        "common_gain_db": 0.0,
        "sensor_independent_gain_db": 0.0,
        "common_frequency_axis_shift_relative": 0.0,
        "independent_manufacturing_percent": 0.0,
        "batch_correlated_manufacturing_percent": 0.0,
        "angle_offset_degrees": 0.0,
    }


def test_public_forward_core_solves_frozen_hand01_block() -> None:
    from acoustic_encoder.gen_enc.forward_acoustic_network import (
        MODEL_NAME,
        frozen_frequency_grid,
        solve_forward_block,
    )

    result = solve_forward_block(
        _member(),
        _neutral_nuisance(),
        cell_index=0,
        repeat_index=0,
        frequencies_hz=frozen_frequency_grid(),
        state_angles_degrees=(0.0, 90.0, 180.0, 270.0),
    )

    assert result.model_name == MODEL_NAME == "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1"
    assert result.central_pressure.shape == (4, 4, 256)
    assert np.all(np.isfinite(result.central_pressure))
    assert result.passive is True
    assert result.reciprocal is True
    assert result.solvable is True
    assert result.numerically_valid is True


def test_every_frozen_nuisance_axis_and_repeat_enters_forward_core() -> None:
    from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block

    member = _member()
    grid = frozen_frequency_grid()
    states = (0.0, 90.0, 180.0, 270.0)
    baseline_nuisance = _neutral_nuisance()
    baseline = solve_forward_block(
        member,
        baseline_nuisance,
        cell_index=17,
        repeat_index=0,
        frequencies_hz=grid,
        state_angles_degrees=states,
    ).central_pressure
    variants = {
        "snr_db": 20.0,
        "common_gain_db": 1.0,
        "sensor_independent_gain_db": -1.0,
        "common_frequency_axis_shift_relative": 0.005,
        "independent_manufacturing_percent": 2.0,
        "batch_correlated_manufacturing_percent": -2.0,
        "angle_offset_degrees": 5.0,
    }
    for axis, value in variants.items():
        nuisance = dict(baseline_nuisance)
        nuisance[axis] = value
        changed = solve_forward_block(
            member,
            nuisance,
            cell_index=17,
            repeat_index=0,
            frequencies_hz=grid,
            state_angles_degrees=states,
        ).central_pressure
        assert changed.tobytes() != baseline.tobytes(), axis
        assert np.all(np.isfinite(changed))

    repeated = solve_forward_block(
        member,
        baseline_nuisance,
        cell_index=17,
        repeat_index=1,
        frequencies_hz=grid,
        state_angles_degrees=states,
    ).central_pressure
    assert repeated.tobytes() != baseline.tobytes()


def test_cli_contract_check_freezes_exact_workload_without_response_artifacts(tmp_path: Path) -> None:
    command = [
        r"D:\Anaconda3\python.exe",
        "-B",
        "scripts/run_gen_enc_2_timing_preflight.py",
        "timing-preflight",
        "--contract-check-only",
        "--member",
        HAND_01.as_posix(),
        "--final92-review",
        "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_FINAL92_INTEGRATION_STAGE_TERMINAL_SCOPE_EVIDENCE_REVIEW.json",
        "--profile",
        "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/revised_recommended_profile.json",
        "--matched-cost",
        "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/matched_cost_manifest_rev01.json",
        "--frequency-contract",
        "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/primary_secondary_frequency_contract.json",
        "--nuisance-contract",
        "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/reduced_factorial_nuisance_contract.json",
        "--nuisance-csv",
        "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv",
        "--seed-split",
        "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json",
        "--output-root",
        str(tmp_path),
        "--checkpoint",
        "checkpoint.json",
        "--frequency-block-size",
        "32",
        "--checkpoint-unit-interval",
        "25",
    ]
    completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    report = json.loads((tmp_path / "contract_check.json").read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert report["complete_units"] == fixture["complete_units"]
    assert report["nuisance_cells"] == fixture["nuisance_cells"]
    assert report["repeats_per_cell"] == fixture["repeats_per_cell"]
    assert report["states"] == len(fixture["states_degrees"])
    assert report["ports"] == fixture["ports"]
    assert report["computed_frequencies"] == fixture["computed_frequencies"]
    assert report["representative_complex_value_count"] == fixture["representative_complex_value_count"]
    assert report["frequency_block_size"] == fixture["frequency_block_size"]
    assert report["frequency_blocks_per_unit"] == fixture["frequency_blocks_per_unit"]
    assert report["projection_multiplier"] == fixture["projection_multiplier"]
    assert report["forbidden_artifact_count"] == 0
    assert report["timing_executed"] is False
    assert {path.name for path in tmp_path.iterdir()} == {"contract_check.json"}
    forbidden = ("pressure", "response", "endpoint", "score", "ranking", "family_performance")
    assert not any(token in json.dumps(report).lower() for token in forbidden)


def test_frequency_blocks_are_contiguous_and_equal_full_core_result() -> None:
    from acoustic_encoder.gen_enc.forward_acoustic_network import frozen_frequency_grid, solve_forward_block

    grid = frozen_frequency_grid()
    kwargs = {
        "member": _member(),
        "nuisance": _neutral_nuisance(),
        "cell_index": 3,
        "repeat_index": 1,
        "state_angles_degrees": (0.0, 90.0, 180.0, 270.0),
    }
    full = solve_forward_block(**kwargs, frequencies_hz=grid, frequency_start_index=0).central_pressure
    pieces = [
        solve_forward_block(
            **kwargs,
            frequencies_hz=grid[start : start + 32],
            frequency_start_index=start,
        ).central_pressure
        for start in range(0, 256, 32)
    ]
    assert all(piece.shape == (4, 4, 32) for piece in pieces)
    assert np.array_equal(np.concatenate(pieces, axis=2), full)


def test_result_schema_is_science_blind_and_feasible_is_consistent() -> None:
    schema_path = REPO / "outputs/gen_enc/GEN_ENC_2_TIMING_PREFLIGHT/contract_freeze_02/timing_preflight_result.schema.json"
    validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
    digest = "0" * 64
    result = {
        "schema_version": "gen_enc_2_timing_preflight_result_freeze_02_v1",
        "record_kind": "DEVELOPMENT_ONLY_TIMING_PREFLIGHT_RESULT",
        "model_name": "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1",
        "member_id": "HAND_01",
        "contract_sha256": digest,
        "source_manifest_sha256": digest,
        "command_manifest_sha256": digest,
        "completion": {"complete_units": 7350, "expected_units": 7350, "states": 4, "computed_frequencies": 256},
        "resources": {"wall_time_seconds": 1.0, "cpu_time_seconds": 1.0, "cpu_utilization_percent": 100.0, "aggregate_peak_memory_gib": 1.0},
        "projection": {"multiplier": 560, "cpu_core_hours": 0.2, "serial_wall_hours": 0.2, "aggregate_peak_memory_gib": 1.0, "within_all_hard_stops": True},
        "numerical": {"valid": True, "converged": True, "nan_inf_absent": True, "solver_exit_code": 0},
        "license": {"available": True, "status": "STDLIB_NUMPY_NO_EXTERNAL_LICENSE"},
        "verdict": "FEASIBLE",
        "claim_limit": "FINAL92_GLOBAL_ORDINAL_1_PROXY_AND_560X_SERIAL_PROJECTION_ONLY_NOT_ALL80_GUARANTEE",
        "gen_enc_2_e2_authorized": False,
        "run_id": None,
        "final_test_read": False,
    }
    validator.validate(result)
    forbidden = dict(result)
    forbidden["pressure"] = [1.0]
    assert list(validator.iter_errors(forbidden))
    contradictory = json.loads(json.dumps(result))
    contradictory["numerical"]["valid"] = False
    assert list(validator.iter_errors(contradictory))


def test_formal_command_fails_closed_without_guardian_authorization(tmp_path: Path) -> None:
    output_root = tmp_path / "formal-output-must-not-exist"
    package = REPO / "outputs/gen_enc/GEN_ENC_2_TIMING_PREFLIGHT/contract_freeze_04"
    command = [
        r"D:\Anaconda3\python.exe",
        "-B",
        "scripts/run_gen_enc_2_timing_preflight.py",
        "timing-preflight",
        "--member", HAND_01.as_posix(),
        "--final92-review", "outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/reviews/GEN_ENC_FINAL92_INTEGRATION_STAGE_TERMINAL_SCOPE_EVIDENCE_REVIEW.json",
        "--profile", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/revised_recommended_profile.json",
        "--matched-cost", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/matched_cost_manifest_rev01.json",
        "--frequency-contract", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/primary_secondary_frequency_contract.json",
        "--nuisance-contract", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/reduced_factorial_nuisance_contract.json",
        "--nuisance-csv", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/nuisance_design_table.csv",
        "--seed-split", "outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REV01/seed_split_rev01.json",
        "--contract", str(package / "contract_revision.json"),
        "--source-manifest", str(package / "source_manifest.json"),
        "--command-manifest", str(package / "command_manifest.json"),
        "--result-schema", str(REPO / "outputs/gen_enc/GEN_ENC_2_TIMING_PREFLIGHT/contract_freeze_03/timing_preflight_result.schema.json"),
        "--authorization", str(tmp_path / "missing-guardian-authorization.json"),
        "--output-root", str(output_root),
        "--checkpoint", "checkpoint.json",
        "--resume",
        "--frequency-block-size", "32",
        "--checkpoint-unit-interval", "25",
    ]
    completed = subprocess.run(command, cwd=REPO, text=True, capture_output=True, check=False)
    assert completed.returncode == 2
    assert "authorization" in completed.stderr.lower()
    assert not output_root.exists()


def test_same_five_node_core_supports_all_four_frozen_families() -> None:
    from acoustic_encoder.gen_enc.forward_acoustic_network import ForwardCoreError, frozen_frequency_grid, solve_forward_block

    cases = (
        ("HAND_DESIGNED/HAND_01.identity.json", "central_mix", 0.15),
        ("NEAR_INDEPENDENT/NEAR_01.identity.json", "shared_alpha", 0.04),
        ("FIXED_SEED_RANDOM_DISORDERED/RANDOM_01.identity.json", "edge_0_180", 0.2),
        ("PHYSICS_METAMATERIAL_INSPIRED/PHYSICS_01.identity.json", "ring_0_90", 0.4),
    )
    for relative, coordinate, replacement in cases:
        member = json.loads((INSTANCE_ROOT / relative).read_text(encoding="utf-8"))
        baseline = solve_forward_block(
            member, _neutral_nuisance(), cell_index=0, repeat_index=0,
            frequencies_hz=frozen_frequency_grid()[:2], state_angles_degrees=(0.0, 90.0, 180.0, 270.0),
        )
        assert baseline.central_pressure.shape == (4, 4, 2)
        assert baseline.passive and baseline.reciprocal and baseline.solvable and baseline.numerically_valid

        changed_member = json.loads(json.dumps(member))
        changed_member["parameters"][coordinate] = replacement
        changed = solve_forward_block(
            changed_member, _neutral_nuisance(), cell_index=0, repeat_index=0,
            frequencies_hz=frozen_frequency_grid()[:2], state_angles_degrees=(0.0, 90.0, 180.0, 270.0),
        )
        assert changed.central_pressure.tobytes() != baseline.central_pressure.tobytes(), relative

    missing = json.loads((INSTANCE_ROOT / "NEAR_INDEPENDENT/NEAR_01.identity.json").read_text(encoding="utf-8"))
    del missing["parameters"]["shared_alpha"]
    with pytest.raises(ForwardCoreError, match="INVALID_SHARED_ALPHA"):
        solve_forward_block(
            missing, _neutral_nuisance(), cell_index=0, repeat_index=0,
            frequencies_hz=frozen_frequency_grid()[:1], state_angles_degrees=(0.0, 90.0, 180.0, 270.0),
        )


def test_optimization_freeze_binds_transitive_project_import_closure() -> None:
    manifest_path = REPO / "outputs/gen_enc/GEN_ENC_2_TIMING_PREFLIGHT/contract_freeze_04/source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["import_closure_check"]["status"] == "PASS"
    entries = {entry["path"]: entry for entry in manifest["entries"]}
    for relative in (
        "src/acoustic_encoder/gen_enc/forward_acoustic_network.py",
        "src/acoustic_encoder/gen_enc/generator/prng.py",
    ):
        entry = entries[relative]
        content = (REPO / relative).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
        assert len(content) == entry["bytes"]


def test_formal_result_is_schema_validated_before_atomic_publication(tmp_path: Path) -> None:
    script_path = REPO / "scripts/run_gen_enc_2_timing_preflight.py"
    spec = importlib.util.spec_from_file_location("timing_preflight_cli", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema = REPO / "outputs/gen_enc/GEN_ENC_2_TIMING_PREFLIGHT/contract_freeze_03/timing_preflight_result.schema.json"
    digest = "0" * 64
    valid = {
        "schema_version": "gen_enc_2_timing_preflight_result_freeze_03_v1",
        "record_kind": "DEVELOPMENT_ONLY_TIMING_PREFLIGHT_RESULT",
        "model_name": "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1",
        "member_id": "HAND_01",
        "contract_sha256": digest,
        "source_manifest_sha256": digest,
        "command_manifest_sha256": digest,
        "completion": {"complete_units": 7350, "expected_units": 7350, "states": 4, "ports": 4, "computed_frequencies": 256, "representative_complex_value_count": 30105600},
        "resources": {"wall_time_seconds": 1.0, "cpu_time_seconds": 1.0, "cpu_utilization_percent": 100.0, "aggregate_peak_memory_gib": 1.0},
        "projection": {"multiplier": 560, "formal_complex_value_count": 16859136000, "derivation": "(4_FAMILIES*20_MEMBERS*(4_DEVELOPMENT+24_VALIDATION_ANGLES)*4_PORTS)/(1_MEMBER*4_DEVELOPMENT_STATES*4_PORTS)=560", "cpu_core_hours": 0.2, "serial_wall_hours": 0.2, "aggregate_peak_memory_gib": 1.0, "within_all_hard_stops": True},
        "numerical": {"valid": True, "converged": True, "nan_inf_absent": True, "solver_exit_code": 0},
        "license": {"available": True, "status": "STDLIB_NUMPY_NO_EXTERNAL_LICENSE"},
        "verdict": "FEASIBLE",
        "claim_limit": "HAND_01_ONLY_DEVELOPMENT_SIDE_TIMING_AND_NUMERICAL_FEASIBILITY_ON_FROZEN_RUNTIME_AND_HARD_STOPS_NOT_OTHER_FAMILIES_NOT_ALL80_NOT_WORST_CASE_NOT_FULL_E2",
        "gen_enc_2_e2_authorized": False,
        "run_id": None,
        "final_test_read": False,
    }
    valid_path = tmp_path / "valid.json"
    module.validate_and_publish_terminal_result(valid, schema, valid_path)
    assert json.loads(valid_path.read_text(encoding="utf-8")) == valid

    forbidden = dict(valid, pressure=[1.0])
    forbidden_path = tmp_path / "forbidden.json"
    with pytest.raises(module.PreflightError, match="RESULT_SCHEMA_VALIDATION_FAILED"):
        module.validate_and_publish_terminal_result(forbidden, schema, forbidden_path)
    assert not forbidden_path.exists()

    contradictory = json.loads(json.dumps(valid))
    contradictory["numerical"]["valid"] = False
    contradictory_path = tmp_path / "contradictory.json"
    with pytest.raises(module.PreflightError, match="RESULT_SCHEMA_VALIDATION_FAILED"):
        module.validate_and_publish_terminal_result(contradictory, schema, contradictory_path)
    assert not contradictory_path.exists()


def test_freeze03_contract_permanently_limits_hand01_inference() -> None:
    package = REPO / "outputs/gen_enc/GEN_ENC_2_TIMING_PREFLIGHT/contract_freeze_03"
    contract = json.loads((package / "contract_revision.json").read_text(encoding="utf-8"))
    schema = json.loads((package / "timing_preflight_result.schema.json").read_text(encoding="utf-8"))
    ceiling = "HAND_01_ONLY_DEVELOPMENT_SIDE_TIMING_AND_NUMERICAL_FEASIBILITY_ON_FROZEN_RUNTIME_AND_HARD_STOPS_NOT_OTHER_FAMILIES_NOT_ALL80_NOT_WORST_CASE_NOT_FULL_E2"
    assert contract["representative_inference_ceiling"] == ceiling
    assert schema["properties"]["claim_limit"]["const"] == ceiling
    assert contract["preflight_pass_authorizes_e2"] is False
    assert contract["other_family_hard_stop_behavior"] == "MAY_RETURN_RESOURCE_BLOCKED_IN_LATER_E2"


def test_batched_core_is_equivalent_to_frozen_scalar_reference() -> None:
    from acoustic_encoder.gen_enc.forward_acoustic_network import (
        frozen_frequency_grid,
        solve_forward_block,
        solve_forward_block_reference,
    )

    nuisance = {
        "snr_db": 30.0,
        "common_gain_db": 1.0,
        "sensor_independent_gain_db": -1.0,
        "common_frequency_axis_shift_relative": 0.005,
        "independent_manufacturing_percent": 2.0,
        "batch_correlated_manufacturing_percent": -2.0,
        "angle_offset_degrees": 3.0,
    }
    members = (
        "HAND_DESIGNED/HAND_01.identity.json",
        "NEAR_INDEPENDENT/NEAR_01.identity.json",
        "FIXED_SEED_RANDOM_DISORDERED/RANDOM_01.identity.json",
        "PHYSICS_METAMATERIAL_INSPIRED/PHYSICS_01.identity.json",
    )
    frequencies = frozen_frequency_grid()[32:48]
    for relative in members:
        member = json.loads((INSTANCE_ROOT / relative).read_text(encoding="utf-8"))
        kwargs = dict(
            member=member, nuisance=nuisance, cell_index=37, repeat_index=1,
            frequencies_hz=frequencies, frequency_start_index=32,
            state_angles_degrees=(0.0, 90.0, 180.0, 270.0),
        )
        reference = solve_forward_block_reference(**kwargs)
        optimized = solve_forward_block(**kwargs)
        assert optimized.model_name == reference.model_name
        assert (optimized.passive, optimized.reciprocal, optimized.solvable, optimized.numerically_valid) == (
            reference.passive, reference.reciprocal, reference.solvable, reference.numerically_valid
        )
        np.testing.assert_allclose(optimized.central_pressure, reference.central_pressure, rtol=1e-12, atol=1e-12)


def test_development_benchmark_persists_only_equivalence_and_timing_aggregates(tmp_path: Path) -> None:
    report_path = tmp_path / "benchmark.json"
    completed = subprocess.run(
        [
            r"D:\Anaconda3\python.exe", "-B", "scripts/benchmark_gen_enc_2_timing_core.py",
            "--fixture", "tests/fixtures/gen_enc_2_timing_preflight/optimization_benchmark_fixture.json",
            "--output", str(report_path),
        ],
        cwd=REPO, text=True, capture_output=True, check=False,
        env={**dict(__import__("os").environ), "OMP_NUM_THREADS":"1", "MKL_NUM_THREADS":"1", "OPENBLAS_NUM_THREADS":"1"},
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["equivalence"]["status"] == "PASS"
    assert report["equivalence"]["rtol"] == 1e-12 and report["equivalence"]["atol"] == 1e-12
    assert report["benchmark"]["formal_preflight"] is False
    assert report["benchmark"]["response_artifacts"] == 0
    assert report["benchmark"]["scalar_wall_seconds"] > 0 and report["benchmark"]["optimized_wall_seconds"] > 0
    assert report["benchmark"]["scalar_cpu_seconds"] > 0 and report["benchmark"]["optimized_cpu_seconds"] > 0
    forbidden = ("central_pressure", "response_values", "endpoint", "score", "ranking", "performance")
    assert not any(token in json.dumps(report).lower() for token in forbidden)

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rc_a_full_role_sets_are_exact_by_phase() -> None:
    verifier = _load("rc03_verifier_roles", "scripts/gen_enc_2_e2_independent_verifier_rc03.py")
    assert verifier.COMMON_W_ROLES == ("WITHIN_CELL_RESIDUAL_BLOCK", "W_WEIGHTED_OUTER_SUM", "W_WEIGHT_SUM")
    assert len(verifier.DEVELOPMENT_METRIC_ROLES) == 9
    assert verifier.VALIDATION_METRIC_ROLES == verifier.DEVELOPMENT_METRIC_ROLES + ("BRIDGE_24_UNIT_VALUES", "HELD_OUT_4_UNIT_VALUES")
    assert len(set(verifier.VALIDATION_METRIC_ROLES)) == 11


def test_rc_b_synthetic_full_role_endpoint_reconstruction_matches_direct() -> None:
    from acoustic_encoder.gen_enc.e2_rc03_stats import reconstruct_candidate

    chunks = []
    direct = []
    for chunk in range(147):
        values = np.empty((25, 2, 6), dtype=np.float64)
        for cell in range(25):
            global_cell = chunk * 25 + cell
            sigma = np.asarray([1.4, 1.2, 0.8 + global_cell / 10_000.0], dtype=np.float64)
            values[cell, :, :3] = sigma
            values[cell, :, 3:] = sigma > 1.0
            direct.extend([sigma.copy(), sigma.copy()])
        chunks.append(values)
    reconstructed = reconstruct_candidate(chunks)
    ordered = np.sort(np.asarray(direct), axis=0, kind="stable")
    direct_q = ordered[int(np.ceil(0.05 * 7350) - 1)]
    np.testing.assert_array_equal(reconstructed["sigma_quantiles"], direct_q)
    assert reconstructed["E_primary"] == direct_q[2]
    assert reconstructed["r_stable"] == int(np.sum(direct_q > 1.0))


def test_rc_b_common_w_synthetic_accumulator_and_oas_are_direct() -> None:
    from acoustic_encoder.gen_enc.e2_rc03_stats import oas_whitener_from_accumulator

    covariance = np.asarray([[2.0, 0.25], [0.25, 1.0]], dtype=np.float64)
    sealed = oas_whitener_from_accumulator(covariance, 1.0)
    identity = sealed["operator"] @ sealed["shrunk"] @ sealed["operator"].T
    np.testing.assert_allclose(identity, np.eye(2), rtol=1e-11, atol=1e-11)
    assert sealed["effective_n"] == 2_352_000.0


def test_rc_b_validation_full_role_fixture_matches_direct_components() -> None:
    from acoustic_encoder.gen_enc.e2_rc03_stats import feature_matrix, metric_chunk_roles, projection_matrices

    generator = np.random.default_rng(20260829)
    noisy = (generator.normal(size=(24, 1, 2, 4, 256)) + 1j * generator.normal(size=(24, 1, 2, 4, 256))).astype(np.complex128)
    pre_noise = noisy - (0.01 + 0.02j)
    reference = np.full(noisy.shape, 2.0 + 0.5j, dtype=np.complex128)
    whitener = np.eye(1664, dtype=np.float64)
    roles = metric_chunk_roles(noisy, reference, whitener, cell_start=100, candidate_raw_pre_noise=pre_noise)
    verifier = _load("rc03_verifier_full_fixture", "scripts/gen_enc_2_e2_independent_verifier_rc03.py")
    assert set(roles) == set(verifier.VALIDATION_METRIC_ROLES)
    direct_numerator = np.sum(np.abs(pre_noise) ** 2, axis=3)
    direct_denominator = np.sum(np.abs(reference) ** 2, axis=3)
    np.testing.assert_allclose(roles["THROUGHPUT_NUMERATOR_256"], direct_numerator, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(roles["THROUGHPUT_REFERENCE_DENOMINATOR_256"], direct_denominator, rtol=0.0, atol=0.0)
    assert np.all(np.unpackbits(roles["THROUGHPUT_AVAILABILITY_256"], bitorder="little")[: direct_numerator.size] == 1)
    y = feature_matrix(noisy[:, 0, 0], (0, 6, 12, 18))
    differential = y @ projection_matrices(4)[1]
    singular = np.linalg.svd(differential, compute_uv=False)[:3]
    np.testing.assert_allclose(roles["ENDPOINT_UNIT_VALUES"][0, 0, :3], singular)
    np.testing.assert_array_equal(roles["HELD_OUT_4_UNIT_VALUES"][0, 0], roles["BRIDGE_24_UNIT_VALUES"][0, 0, [3, 9, 15, 21]][:, [1, 2, 3, 5]])
    np.testing.assert_array_equal(roles["RESAMPLING_UNIT_KEYS"][0, 0], [100, 0, 0, 0])


def test_rc_c_storage_ledger_is_derived_from_roles_and_below_cap() -> None:
    builder = _load("rc03_builder_storage", "scripts/build_gen_enc_2_e2_rc03_final_closure.py")
    ledger = builder.storage_ledger()
    assert ledger["derivation_kind"] == "MECHANICAL_FROM_ROLE_SHAPES_DTYPES_COUNTS"
    assert ledger["worst_case_retained_bytes"] == sum(ledger["components_bytes"].values())
    assert ledger["worst_case_retained_bytes"] <= 48 * 1024**3
    assert ledger["audit_raw_chunks"] == 320


def test_rc_d_process_tree_accounts_child_cpu_and_aggregate_rss() -> None:
    from acoustic_encoder.gen_enc.e2_rc03_resource import ResourceLedger

    ledger = ResourceLedger.start()
    baseline = ledger.snapshot()["aggregate_peak_rss_bytes"]
    code = "import time; x=bytearray(24*1024*1024); t=time.process_time()+0.15\nwhile time.process_time()<t: sum(i*i for i in range(2000))\nprint(len(x))"
    completed = ledger.run_child([sys.executable, "-c", code], cwd=REPO.as_posix())
    snapshot = ledger.snapshot()
    assert completed.returncode == 0
    assert snapshot["cpu_core_seconds"] > 0.0
    assert snapshot["aggregate_peak_rss_bytes"] > baseline + 8 * 1024**2
    assert snapshot["method_version"] == "PSUTIL_WINDOWS_PROCESS_TREE_SAMPLE_10MS_V1"


def test_rc_e_development_and_validation_terminal_obligations_are_disjoint(tmp_path: Path) -> None:
    merge = _load("rc03_merge_terminal", "scripts/gen_enc_2_e2_merge_reconstruct_rc03.py")
    w = tmp_path / "w.npz"
    np.savez(w, operator=np.eye(2))
    family = tmp_path / "family.json"; family.write_text("{}\n", encoding="utf-8")
    candidates = []
    for index in range(80):
        path = tmp_path / f"candidate_{index:02d}.json"; path.write_text("{}\n", encoding="utf-8"); candidates.append(path)
    seal_path = tmp_path / "development_terminal.json"
    seal = merge.development_seal(w, candidates, family, seal_path)
    assert seal["complete_identities"] == 80
    assert seal["development_decisions_sealed"] is True
    assert seal["validation_opened"] is False
    assert seal["validation_refit"] is False
    schema = json.loads((REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_02_rc03_closure/partition_terminal.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(seal)
    validation = {
        "schema_version": "gen_enc_2_e2_partition_terminal_rc03_v1", "partition": "single_use_validation",
        "status": "E2_V_SINGLE_USE_TERMINAL", "complete_identities": 80, "independent_verify_pass": True,
        "common_w_sha256": "1" * 64, "development_seal_sha256": "2" * 64,
        "candidate_terminals_sha256": "3" * 64, "family_global_terminal_sha256": "4" * 64,
        "validation_refit": False, "validation_feedback_to_development": False, "single_use_consumed": True,
        "formal_run_id_created": False, "final_test_read": False,
    }
    Draft202012Validator(schema).validate(validation)

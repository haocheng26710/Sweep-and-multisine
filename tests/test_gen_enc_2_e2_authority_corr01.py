from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator


REPO = Path(__file__).resolve().parents[1]


def _load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_angle_mapping_cardinal_adjacent_l2_phase_and_offset_order() -> None:
    from acoustic_encoder.gen_enc.e2_authority import directional_port_weights

    for index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
        expected = np.zeros(4)
        expected[index] = 1.0
        np.testing.assert_array_equal(directional_port_weights(angle, 0.0), expected)
    middle = directional_port_weights(45.0, 0.0)
    assert np.flatnonzero(middle).tolist() == [0, 1]
    assert np.linalg.norm(middle) == pytest.approx(1.0, abs=1e-15)
    assert np.all(np.isreal(middle)) and np.all(middle >= 0.0)
    np.testing.assert_allclose(
        directional_port_weights(45.0, 45.0),
        directional_port_weights(90.0, 0.0), rtol=0.0, atol=0.0,
    )


def test_partition_seed_routing_is_exact_and_has_no_fallback() -> None:
    from acoustic_encoder.gen_enc.e2_authority import E2AuthorityError, resolve_partition_repeat_seeds

    assert resolve_partition_repeat_seeds("development", (2026091001, 2026091002)) == (2026091001, 2026091002)
    assert resolve_partition_repeat_seeds("single_use_validation", (2026092001, 2026092002)) == (2026092001, 2026092002)
    with pytest.raises(E2AuthorityError, match="MISMATCH"):
        resolve_partition_repeat_seeds("single_use_validation", (2026091001, 2026091002))


def test_common_w_weight_measure_audits_exact_expected_mass_and_dimensions() -> None:
    from acoustic_encoder.gen_enc.e2_authority import common_w_weight_audit

    audit = common_w_weight_audit()
    assert audit["members"] == 80
    assert audit["total_residual_rows"] == 2_352_000
    assert audit["primary_feature_dimension"] == 1664
    assert audit["total_mass"] == pytest.approx(1.0)
    assert audit["global_residual_row_mass"] == pytest.approx(1.0 / 2_352_000)


def test_neutral_through_reference_uses_same_core_before_additive_noise() -> None:
    from acoustic_encoder.gen_enc.forward_acoustic_network import (
        frozen_frequency_grid, solve_forward_block, solve_forward_block_reference,
    )

    identity_path = REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_authority_addendum_01/THROUGH_REFERENCE_U4_IDENTITY_V1.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    nuisance = {
        "snr_db": 40.0, "common_gain_db": 0.0, "sensor_independent_gain_db": 0.0,
        "common_frequency_axis_shift_relative": 0.0, "independent_manufacturing_percent": 0.0,
        "batch_correlated_manufacturing_percent": 0.0, "angle_offset_degrees": 0.0,
    }
    result = solve_forward_block(
        identity, nuisance, cell_index=0, repeat_index=0,
        frequencies_hz=frozen_frequency_grid()[:1], state_angles_degrees=(0.0, 45.0),
        partition="single_use_validation", repeat_seed_tuple=(2026092001, 2026092002),
        include_additive_sensor_noise=False,
    )
    assert result.central_pressure.shape == (2, 4, 1)
    assert np.all(np.isfinite(result.central_pressure))
    reference = solve_forward_block_reference(
        identity, nuisance, cell_index=0, repeat_index=0,
        frequencies_hz=frozen_frequency_grid()[:1], state_angles_degrees=(0.0, 45.0),
        partition="single_use_validation", repeat_seed_tuple=(2026092001, 2026092002),
        include_additive_sensor_noise=False,
    )
    np.testing.assert_allclose(result.central_pressure, reference.central_pressure, rtol=1e-12, atol=1e-12)


def test_streaming_receipt_reconstruction_audit_selection_and_storage_caps() -> None:
    driver = _load_script("e2_driver_corr01_test", "scripts/gen_enc_2_e2_streaming_driver_corr01.py")
    verifier = _load_script("e2_verifier_corr01_test", "scripts/gen_enc_2_e2_streaming_independent_verifier_corr01.py")
    chunks = driver.canonical_chunk_ids()
    selected = driver.raw_audit_selection("development", "HAND_01", chunks)
    assert len(chunks) == 147 and len(selected) == 2
    assert selected == driver.raw_audit_selection("development", "HAND_01", chunks)
    driver.enforce_storage_gate(managed_bytes=48 * 1024**3, free_bytes=80 * 1024**3, startup=True)
    with pytest.raises(driver.StreamingContractError, match="48_GIB"):
        driver.enforce_storage_gate(managed_bytes=48 * 1024**3 + 1, free_bytes=80 * 1024**3, startup=False)
    with pytest.raises(driver.StreamingContractError, match="32_GIB"):
        driver.enforce_storage_gate(managed_bytes=1, free_bytes=32 * 1024**3 - 1, startup=False)
    value = np.asarray([[1.0 + 2.0j, 3.0 - 4.0j]], dtype=np.complex128)
    verified = verifier.verify_arrays(value, value.copy())
    assert np.array_equal(verifier.reconstruct_statistics(verified["stats"]), value)
    hashes = {
        key: str(index) * 64
        for index, key in enumerate(("input", "driver_code", "verifier_code", "runtime", "dependencies"), start=1)
    }
    receipt = verifier.build_pass_receipt(
        partition="development", identity_id="HAND_01", chunk_id="chunk_000",
        driver=value, verifier=value.copy(), hashes=hashes, merge_position=0,
    )
    schema = json.loads(
        (REPO / "outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_preexecution_contract_freeze_01_corr01/chunk_pass_receipt.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(receipt)

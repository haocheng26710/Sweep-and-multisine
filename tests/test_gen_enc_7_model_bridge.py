from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from acoustic_encoder.gen_enc.actual_fluid_star_network import solve_clean_node_pressure_block
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.resolved_plenum_star_network import (
    CENTRAL_VOLUME_M3,
    assemble_resolved_system_matrices,
    solve_resolved_clean_block,
)
from scripts.gen_enc_7_model_bridge_diagnostic import response_discrepancy


REPO = Path(__file__).resolve().parents[1]
IDENTITY = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/HAND_DESIGNED/HAND_01.identity.json"
SEEDS = (2026091001, 2026091002)


def nuisance() -> dict[str, float]:
    return {
        "snr_db": 30.0,
        "common_gain_db": 0.0,
        "sensor_independent_gain_db": 0.0,
        "common_frequency_axis_shift_relative": 0.0,
        "independent_manufacturing_percent": 0.0,
        "batch_correlated_manufacturing_percent": 0.0,
        "angle_offset_degrees": 0.0,
    }


def test_resolved_plenum_is_nine_node_passive_reciprocal_and_volume_conserving() -> None:
    member = json.loads(IDENTITY.read_text(encoding="utf-8"))
    frequencies = frozen_frequency_grid()[:8]
    matrices, passive, reciprocal = assemble_resolved_system_matrices(
        member,
        nuisance(),
        cell_index=0,
        repeat_index=0,
        frequencies_hz=frequencies,
        partition="development",
        repeat_seed_tuple=SEEDS,
    )
    result = solve_resolved_clean_block(
        member,
        nuisance(),
        cell_index=0,
        repeat_index=0,
        frequencies_hz=frequencies,
        state_angles_degrees=STATE_ANGLES_DEGREES,
        partition="development",
        repeat_seed_tuple=SEEDS,
    )
    assert matrices.shape == (8, 9, 9)
    assert passive and reciprocal
    assert result.central_pressure.shape == (4, 4, 8)
    assert np.all(np.isfinite(result.central_pressure))
    assert np.isclose(result.total_central_volume_m3, CENTRAL_VOLUME_M3, rtol=0.0, atol=1e-18)


def test_resolved_plenum_converges_to_collapsed_star_under_strong_internal_coupling() -> None:
    member = json.loads(IDENTITY.read_text(encoding="utf-8"))
    frequencies = frozen_frequency_grid()[:8]
    kwargs = dict(
        member=member,
        nuisance=nuisance(),
        cell_index=0,
        repeat_index=0,
        frequencies_hz=frequencies,
        state_angles_degrees=STATE_ANGLES_DEGREES,
        partition="development",
        repeat_seed_tuple=SEEDS,
    )
    collapsed = solve_clean_node_pressure_block(**kwargs, spine_only=False)[..., 4]
    resolved = solve_resolved_clean_block(**kwargs, plenum_link_length_scale=1e-6).central_pressure
    relative_error = np.linalg.norm(resolved - collapsed) / np.linalg.norm(collapsed)
    assert relative_error < 1e-7


def test_response_discrepancy_does_not_mutate_inputs() -> None:
    reference = np.arange(1, 17, dtype=float).reshape(4, 4).astype(np.complex128)
    alternative = reference * (1.0 + 0.01j)
    reference_before = reference.copy()
    alternative_before = alternative.copy()
    relative, gram = response_discrepancy(reference, alternative)
    assert relative > 0.0
    assert gram >= 0.0
    np.testing.assert_array_equal(reference, reference_before)
    np.testing.assert_array_equal(alternative, alternative_before)

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.gen_enc.actual_fluid_star_network import CENTRAL_VOLUME_M3, compile_member_geometry, assemble_system_matrices, solve_forward_block
from acoustic_encoder.gen_enc.forward_acoustic_network import STATE_ANGLES_DEGREES, TOTAL_VOLUME_M3, frozen_frequency_grid


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances"
SEEDS = (2026091001, 2026091002)


def member(family: str, name: str) -> dict:
    return json.loads((ROOT / family / name).read_text(encoding="utf-8"))


def nuisance() -> dict[str, float]:
    return {"snr_db": 30.0, "common_gain_db": 0.0, "sensor_independent_gain_db": 0.0, "common_frequency_axis_shift_relative": 0.0, "independent_manufacturing_percent": 0.0, "batch_correlated_manufacturing_percent": 0.0, "angle_offset_degrees": 0.0}


@pytest.mark.parametrize(("family", "name"), [("HAND_DESIGNED", "HAND_01.identity.json"), ("NEAR_INDEPENDENT", "NEAR_01.identity.json"), ("FIXED_SEED_RANDOM_DISORDERED", "RANDOM_01.identity.json"), ("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json")])
def test_baseline_and_spine_only_preserve_each_sector_target_and_total_volume(family: str, name: str) -> None:
    candidate = member(family, name)
    for spine_only in (False, True):
        geometry = compile_member_geometry(candidate, spine_only=spine_only)
        np.testing.assert_allclose([g.segment_volume_m3 for g in geometry], [g.target_volume_m3 for g in geometry], atol=1e-12, rtol=0.0)
        assert sum(g.segment_volume_m3 for g in geometry) + CENTRAL_VOLUME_M3 == pytest.approx(TOTAL_VOLUME_M3, abs=1e-12)
        assert all(len(g.segments_outer_to_central) == 9 for g in geometry)


def test_spine_only_entry_is_fixed_and_root_compensates() -> None:
    candidate = member("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json")
    baseline = compile_member_geometry(candidate, spine_only=False)
    ablated = compile_member_geometry(candidate, spine_only=True)
    assert all(g.window_union_area_m2 == pytest.approx(4e-6) for g in ablated)
    assert all(b.window_union_area_m2 > a.window_union_area_m2 for b, a in zip(baseline, ablated))
    assert all(a.root_length_m > b.root_length_m for b, a in zip(baseline, ablated))


def test_near_upper_binary64_endpoint_uses_frozen_m1_clamp() -> None:
    geometry = compile_member_geometry(member("NEAR_INDEPENDENT", "NEAR_20.identity.json"), spine_only=False)
    assert all(g.window_union_area_m2 == pytest.approx(16e-6) for g in geometry)


def test_piecewise_star_is_passive_reciprocal_finite_and_solvable() -> None:
    candidate = member("FIXED_SEED_RANDOM_DISORDERED", "RANDOM_01.identity.json")
    frequencies = frozen_frequency_grid()[:32]
    for spine_only in (False, True):
        matrices, _, passive, reciprocal = assemble_system_matrices(candidate, nuisance(), cell_index=0, repeat_index=0, frequencies_hz=frequencies, partition="development", repeat_seed_tuple=SEEDS, spine_only=spine_only)
        assert passive and reciprocal and np.all(np.isfinite(matrices))
        np.testing.assert_allclose(matrices, matrices.transpose(0, 2, 1), atol=1e-11, rtol=0.0)
        response = solve_forward_block(candidate, nuisance(), cell_index=0, repeat_index=0, frequencies_hz=frequencies, state_angles_degrees=STATE_ANGLES_DEGREES, partition="development", repeat_seed_tuple=SEEDS, spine_only=spine_only, include_additive_sensor_noise=False)
        assert response.numerically_valid and np.all(np.isfinite(response.central_pressure))

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from acoustic_encoder.gen_enc.distributed_channel_network import assemble_system_matrices, distributed_edge_two_ports, solve_forward_block as solve_m2a
from acoustic_encoder.gen_enc.forward_acoustic_network import BRANCH_LENGTH_M, STATE_ANGLES_DEGREES, frozen_frequency_grid
from acoustic_encoder.gen_enc.topology_preserving_network import lateral_edge_admittances, solve_forward_block as solve_m1


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances"
SEEDS = (2026091001, 2026091002)


def member(family: str, name: str) -> dict[str, object]:
    return json.loads((ROOT / family / name).read_text(encoding="utf-8"))


def nuisance() -> dict[str, float]:
    return {"snr_db": 30.0, "common_gain_db": 0.0, "sensor_independent_gain_db": 0.0, "common_frequency_axis_shift_relative": 0.0, "independent_manufacturing_percent": 0.0, "batch_correlated_manufacturing_percent": 0.0, "angle_offset_degrees": 0.0}


def test_distributed_line_is_reciprocal_passive_and_volume_conserving() -> None:
    candidate = member("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json")
    matrices, audit, passive, reciprocal, lumped_volumes = assemble_system_matrices(candidate, nuisance(), cell_index=0, repeat_index=0, frequencies_hz=frozen_frequency_grid()[:8], partition="development", repeat_seed_tuple=SEEDS, path_length_m=0.058926678767398356)
    _, _, _, edge_volumes = distributed_edge_two_ports(candidate, nuisance(), frozen_frequency_grid()[:8], path_length_m=0.058926678767398356)
    assert passive and reciprocal and np.all(np.isfinite(matrices))
    assert np.all(lumped_volumes > 0.0)
    assert len(audit.active_edges) == len(edge_volumes)
    np.testing.assert_allclose(matrices, matrices.transpose(0, 2, 1), atol=1e-12, rtol=0.0)
    from acoustic_encoder.gen_enc.forward_acoustic_network import TOTAL_VOLUME_M3
    np.testing.assert_allclose(lumped_volumes.sum() + edge_volumes.sum(), TOTAL_VOLUME_M3, rtol=1e-14)


def test_short_line_mutual_admittance_converges_to_m1_edge() -> None:
    candidate = member("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json")
    frequency = np.asarray([1e-3])
    _, _, mutual, _ = distributed_edge_two_ports(candidate, nuisance(), frequency, path_length_m=BRANCH_LENGTH_M)
    _, lumped = lateral_edge_admittances(candidate, nuisance(), frequency)
    np.testing.assert_allclose(mutual, lumped, rtol=1e-7, atol=0.0)


def test_hand_negative_control_matches_m1_exactly() -> None:
    candidate = member("HAND_DESIGNED", "HAND_01.identity.json")
    kwargs = dict(cell_index=2, repeat_index=1, frequencies_hz=frozen_frequency_grid()[:16], state_angles_degrees=STATE_ANGLES_DEGREES, partition="development", repeat_seed_tuple=SEEDS, frequency_start_index=0, include_additive_sensor_noise=False)
    m1 = solve_m1(candidate, nuisance(), **kwargs)
    m2a = solve_m2a(candidate, nuisance(), path_length_m=0.058926678767398356, **kwargs)
    np.testing.assert_allclose(m2a.central_pressure, m1.central_pressure, rtol=1e-13, atol=1e-13)

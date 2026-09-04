from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.gen_enc.e2_authority import directional_port_weights
from acoustic_encoder.gen_enc.forward_acoustic_network import (
    STATE_ANGLES_DEGREES,
    frozen_frequency_grid,
    solve_forward_block as solve_m0,
)
from acoustic_encoder.gen_enc.robust_encoding_geometry import batch_geometry_from_raw
from acoustic_encoder.gen_enc.topology_preserving_network import (
    ALL_UNDIRECTED_EDGES,
    MODEL_NAME,
    REFERENCE_LATERAL_AREA_M2,
    RING_EDGES,
    assemble_system_matrices,
    lateral_edge_admittances,
    solve_forward_block as solve_m1,
    topology_audit,
)
from scripts.gen_enc_4_topology_preserving_m0_m1 import geometry_chunk


REPO = Path(__file__).resolve().parents[1]
IDENTITY_ROOT = (
    REPO
    / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances"
)
SEEDS = (2026091001, 2026091002)


def member(family: str, name: str) -> dict[str, object]:
    return json.loads((IDENTITY_ROOT / family / name).read_text(encoding="utf-8"))


def nuisance(**overrides: float) -> dict[str, float]:
    result = {
        "snr_db": 30.0,
        "common_gain_db": 0.0,
        "sensor_independent_gain_db": 0.0,
        "common_frequency_axis_shift_relative": 0.0,
        "independent_manufacturing_percent": 0.0,
        "batch_correlated_manufacturing_percent": 0.0,
        "angle_offset_degrees": 0.0,
    }
    result.update(overrides)
    return result


def test_family_graphs_are_explicit_and_auditable() -> None:
    hand = topology_audit(member("HAND_DESIGNED", "HAND_01.identity.json"))
    near = topology_audit(member("NEAR_INDEPENDENT", "NEAR_01.identity.json"))
    random = topology_audit(member("FIXED_SEED_RANDOM_DISORDERED", "RANDOM_01.identity.json"))
    physics = topology_audit(member("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json"))

    assert hand.active_edges == ()
    assert hand.semantic == "FROZEN_REPLICATED_CENTRAL_MIX_STAR_NO_LOCAL_LOCAL_EDGE"
    assert [(edge.left_angle, edge.right_angle) for edge in near.active_edges] == list(ALL_UNDIRECTED_EDGES)
    assert near.budget_fraction == pytest.approx(0.03)
    assert [(edge.left_angle, edge.right_angle) for edge in random.active_edges] == [(0, 90), (180, 270)]
    assert [(edge.left_angle, edge.right_angle) for edge in physics.active_edges] == list(RING_EDGES)
    assert all(edge.coordinate > 0.0 for edge in random.active_edges)


@pytest.mark.parametrize(
    ("family", "name"),
    [
        ("HAND_DESIGNED", "HAND_01.identity.json"),
        ("NEAR_INDEPENDENT", "NEAR_20.identity.json"),
        ("FIXED_SEED_RANDOM_DISORDERED", "RANDOM_03.identity.json"),
        ("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json"),
    ],
)
def test_total_lateral_channel_budget_is_bounded(family: str, name: str) -> None:
    audit = topology_audit(member(family, name))
    assert 0.0 <= audit.total_lateral_area_m2 <= REFERENCE_LATERAL_AREA_M2 * (1.0 + 1e-14)
    assert audit.lateral_area_budget_m2 == REFERENCE_LATERAL_AREA_M2


def test_edge_admittance_is_frequency_dependent_passive_and_finite() -> None:
    frequencies = frozen_frequency_grid()[[0, 100, 207]]
    audit, admittance = lateral_edge_admittances(
        member("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json"), nuisance(), frequencies
    )
    assert admittance.shape == (3, len(audit.active_edges))
    assert np.all(np.isfinite(admittance))
    assert np.all(admittance.real > 0.0)
    assert np.all(admittance.imag < 0.0)
    assert np.all(np.abs(admittance[0]) > np.abs(admittance[-1]))


def test_five_node_matrix_is_reciprocal_passive_and_lateral_laplacian_conserves_flow() -> None:
    candidate = member("FIXED_SEED_RANDOM_DISORDERED", "RANDOM_03.identity.json")
    frequencies = frozen_frequency_grid()[10:14]
    matrices, audit, passive, reciprocal = assemble_system_matrices(
        candidate,
        nuisance(),
        cell_index=0,
        repeat_index=0,
        frequencies_hz=frequencies,
        partition="development",
        repeat_seed_tuple=SEEDS,
    )
    assert matrices.shape == (4, 5, 5)
    assert passive and reciprocal
    np.testing.assert_allclose(matrices, matrices.transpose(0, 2, 1), rtol=0.0, atol=1e-12)

    _, values = lateral_edge_admittances(candidate, nuisance(), frequencies)
    angle_to_index = {angle: index for index, angle in enumerate((0, 90, 180, 270))}
    laplacian = np.zeros((frequencies.size, 4, 4), dtype=np.complex128)
    for edge, value in zip(audit.active_edges, values.T):
        left, right = angle_to_index[edge.left_angle], angle_to_index[edge.right_angle]
        laplacian[:, left, left] += value
        laplacian[:, right, right] += value
        laplacian[:, left, right] -= value
        laplacian[:, right, left] -= value
    np.testing.assert_allclose(laplacian.sum(axis=2), 0.0, rtol=0.0, atol=1e-18)
    hermitian_real = 0.5 * (laplacian.real + laplacian.real.transpose(0, 2, 1))
    assert np.min(np.linalg.eigvalsh(hermitian_real)) >= -1e-15


def test_hand_m1_exactly_reproduces_frozen_m0_because_it_has_no_lateral_edge() -> None:
    candidate = member("HAND_DESIGNED", "HAND_01.identity.json")
    kwargs = dict(
        cell_index=19,
        repeat_index=1,
        frequencies_hz=frozen_frequency_grid()[30:50],
        state_angles_degrees=STATE_ANGLES_DEGREES,
        partition="development",
        repeat_seed_tuple=SEEDS,
        frequency_start_index=30,
        include_additive_sensor_noise=True,
    )
    m0 = solve_m0(candidate, nuisance(angle_offset_degrees=3.0), **kwargs)
    m1 = solve_m1(candidate, nuisance(angle_offset_degrees=3.0), **kwargs)
    assert m1.model_name == MODEL_NAME
    np.testing.assert_allclose(m1.central_pressure, m0.central_pressure, rtol=1e-13, atol=1e-13)


def test_solver_matches_direct_five_by_five_solve_without_noise() -> None:
    candidate = member("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json")
    frequency = frozen_frequency_grid()[17:18]
    matrices, _, _, _ = assemble_system_matrices(
        candidate,
        nuisance(angle_offset_degrees=5.0),
        cell_index=3,
        repeat_index=0,
        frequencies_hz=frequency,
        partition="development",
        repeat_seed_tuple=SEEDS,
    )
    result = solve_m1(
        candidate,
        nuisance(angle_offset_degrees=5.0),
        cell_index=3,
        repeat_index=0,
        frequencies_hz=frequency,
        state_angles_degrees=STATE_ANGLES_DEGREES,
        partition="development",
        repeat_seed_tuple=SEEDS,
        frequency_start_index=17,
        include_additive_sensor_noise=False,
    )
    expected = np.empty((4, 4), dtype=np.complex128)
    for state_index, state in enumerate(STATE_ANGLES_DEGREES):
        weights = directional_port_weights(state, 5.0)
        for port in range(4):
            source = np.zeros(5, dtype=np.complex128)
            source[port] = weights[port]
            expected[state_index, port] = np.linalg.solve(matrices[0], source)[4]
    np.testing.assert_allclose(result.central_pressure[:, :, 0], expected, rtol=1e-13, atol=1e-13)


def test_m1_contains_no_propagation_phase_or_added_resonant_nodes() -> None:
    source = (REPO / "src/acoustic_encoder/gen_enc/topology_preserving_network.py").read_text(encoding="utf-8")
    assert "path_phase" not in source
    assert "propagation_delay" not in source
    assert "added_resonator" not in source
    matrices, _, _, _ = assemble_system_matrices(
        member("PHYSICS_METAMATERIAL_INSPIRED", "PHYSICS_01.identity.json"),
        nuisance(),
        cell_index=0,
        repeat_index=0,
        frequencies_hz=frozen_frequency_grid()[:2],
        partition="development",
        repeat_seed_tuple=SEEDS,
    )
    assert matrices.shape[1:] == (5, 5)


def test_m1_geometry_chunk_matches_frozen_3a_geometry_formulas() -> None:
    rng = np.random.Generator(np.random.PCG64(2026090400))
    raw = rng.normal(size=(4, 2, 2, 4, 256)) + 1j * rng.normal(size=(4, 2, 2, 4, 256))
    whitener = np.eye(1664, dtype=float)
    distances, grams, singulars, y_diff = geometry_chunk(raw, whitener)
    expected_distances, expected_grams, expected_y_diff = batch_geometry_from_raw(raw, whitener)
    np.testing.assert_allclose(distances, expected_distances, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(grams, expected_grams, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(y_diff, expected_y_diff, rtol=1e-13, atol=1e-13)
    assert singulars.shape == (2, 2, 3)
    assert np.all(np.diff(singulars, axis=2) <= 0.0)

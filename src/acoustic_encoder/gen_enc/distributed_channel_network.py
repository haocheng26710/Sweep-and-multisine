"""GEN-ENC-4 M2-A passive distributed-channel mechanism preflight.

This is intentionally not a new candidate-family analysis.  It replaces each
M1 local-to-local lumped edge by a reciprocal lossy uniform-line two-port and
returns the line volume from the adjacent lumped compliances.
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .e2_authority import angle_global_ordinal, directional_port_weights, resolve_partition_repeat_seeds, validate_frozen_angles
from .forward_acoustic_network import (
    BRANCH_LENGTH_M,
    RHO_KG_M3,
    SPEED_OF_SOUND_M_S,
    ForwardBlockResult,
    ForwardCoreError,
    _number,
    _substream_uniform_array,
    _volume_partition,
    frozen_frequency_grid,
)
from .topology_preserving_network import ANGLE_ORDER, _radial_branch_parameters, topology_audit


MODEL_NAME = "PASSIVE_RECIPROCAL_5_NODE_DISTRIBUTED_CHANNEL_M2A_V1"


def distributed_edge_two_ports(
    member: Mapping[str, object],
    nuisance: Mapping[str, object],
    frequencies_hz: Sequence[float],
    *,
    path_length_m: float,
) -> tuple[object, NDArray[np.complex128], NDArray[np.complex128], NDArray[np.float64]]:
    """Return line diagonal/mutual admittances and physical edge volumes."""

    if not math.isfinite(path_length_m) or path_length_m <= 0.0:
        raise ForwardCoreError("POSITIVE_FINITE_PATH_LENGTH_REQUIRED")
    audit = topology_audit(member)
    parameters = member.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError("MISSING_PARAMETERS")
    frequencies = np.asarray(frequencies_hz, dtype=float)
    if frequencies.ndim != 1 or frequencies.size < 1 or np.any(frequencies <= 0.0) or not np.all(np.isfinite(frequencies)):
        raise ForwardCoreError("POSITIVE_FINITE_FREQUENCIES_REQUIRED")
    batch = 1.0 + _number(nuisance, "batch_correlated_manufacturing_percent") / 100.0
    omega = 2.0 * math.pi * frequencies
    diagonal = np.empty((frequencies.size, len(audit.active_edges)), dtype=np.complex128)
    mutual = np.empty_like(diagonal)
    volumes = np.empty(len(audit.active_edges), dtype=float)
    for edge_index, edge in enumerate(audit.active_edges):
        area = edge.area_m2 * batch
        loss = 0.5 * (_number(parameters, f"loss_{edge.left_angle}") + _number(parameters, f"loss_{edge.right_angle}"))
        if area <= 0.0 or loss < 0.0:
            raise ForwardCoreError("INVALID_DISTRIBUTED_EDGE_PARAMETER")
        # R' is anchored so L=BRANCH_LENGTH_M has the same total R as M1.
        series_per_m = loss * RHO_KG_M3 * SPEED_OF_SOUND_M_S / (area * BRANCH_LENGTH_M) + 1j * omega * RHO_KG_M3 / area
        shunt_per_m = 1j * omega * area / (RHO_KG_M3 * SPEED_OF_SOUND_M_S**2)
        gamma = np.sqrt(series_per_m * shunt_per_m)
        characteristic_admittance = np.sqrt(shunt_per_m / series_per_m)
        gl = gamma * path_length_m
        sinh_gl = np.sinh(gl)
        diagonal[:, edge_index] = characteristic_admittance * np.cosh(gl) / sinh_gl
        mutual[:, edge_index] = characteristic_admittance / sinh_gl
        volumes[edge_index] = area * path_length_m
    if not np.all(np.isfinite(diagonal)) or not np.all(np.isfinite(mutual)) or not np.all(np.isfinite(volumes)):
        raise ForwardCoreError("NONFINITE_DISTRIBUTED_EDGE")
    return audit, diagonal, mutual, volumes


def assemble_system_matrices(
    member: Mapping[str, object],
    nuisance: Mapping[str, object],
    *,
    cell_index: int,
    repeat_index: int,
    frequencies_hz: Sequence[float],
    partition: str,
    repeat_seed_tuple: Sequence[int],
    path_length_m: float,
) -> tuple[NDArray[np.complex128], object, bool, bool, NDArray[np.float64]]:
    parameters = member.get("parameters")
    family_id = member.get("family_id")
    if not isinstance(parameters, Mapping) or not isinstance(family_id, str):
        raise ForwardCoreError("MISSING_MEMBER_FIELDS")
    repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    shift = _number(nuisance, "common_frequency_axis_shift_relative")
    shifted = frequencies * (1.0 + shift)
    audit, edge_diag, edge_mutual, edge_volumes = distributed_edge_two_ports(
        member, nuisance, shifted, path_length_m=path_length_m
    )
    volumes = _volume_partition(parameters)
    angle_to_index = {angle: index for index, angle in enumerate(ANGLE_ORDER)}
    for edge, volume in zip(audit.active_edges, edge_volumes):
        volumes[angle_to_index[edge.left_angle]] -= 0.5 * volume
        volumes[angle_to_index[edge.right_angle]] -= 0.5 * volume
    if np.any(volumes <= 0.0):
        raise ForwardCoreError("DISTRIBUTED_VOLUME_EXCEEDS_LOCAL_VOLUME")
    compliances = volumes / (RHO_KG_M3 * SPEED_OF_SOUND_M_S**2)
    masses, resistances = _radial_branch_parameters(
        family_id, parameters, nuisance, cell_index, repeat_index, repeat_seeds[repeat_index]
    )
    omega = 2.0 * math.pi * shifted
    radial = 1.0 / (resistances[None, :] + 1j * omega[:, None] * masses[None, :])
    matrices = np.zeros((frequencies.size, 5, 5), dtype=np.complex128)
    idx = np.arange(5)
    matrices[:, idx, idx] = 1j * omega[:, None] * compliances[None, :]
    local = np.arange(4)
    matrices[:, local, local] += radial
    matrices[:, 4, 4] += radial.sum(axis=1)
    matrices[:, local, 4] -= radial
    matrices[:, 4, local] -= radial
    for edge_index, edge in enumerate(audit.active_edges):
        left, right = angle_to_index[edge.left_angle], angle_to_index[edge.right_angle]
        matrices[:, left, left] += edge_diag[:, edge_index]
        matrices[:, right, right] += edge_diag[:, edge_index]
        matrices[:, left, right] -= edge_mutual[:, edge_index]
        matrices[:, right, left] -= edge_mutual[:, edge_index]
    reciprocal = bool(np.allclose(matrices, matrices.transpose(0, 2, 1), rtol=0.0, atol=1e-12))
    hermitian_real = 0.5 * (matrices.real + matrices.real.transpose(0, 2, 1))
    passive = bool(np.min(np.linalg.eigvalsh(hermitian_real)) >= -1e-12)
    return matrices, audit, passive, reciprocal, volumes


def solve_forward_block(
    member: Mapping[str, object],
    nuisance: Mapping[str, object],
    *,
    cell_index: int,
    repeat_index: int,
    frequencies_hz: Sequence[float],
    state_angles_degrees: Sequence[float],
    partition: str,
    repeat_seed_tuple: Sequence[int],
    path_length_m: float,
    frequency_start_index: int = 0,
    include_additive_sensor_noise: bool = True,
) -> ForwardBlockResult:
    frequencies = np.asarray(frequencies_hz, dtype=float)
    states = validate_frozen_angles(partition, state_angles_degrees)
    repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    if not isinstance(cell_index, int) or cell_index < 0 or repeat_index not in (0, 1):
        raise ForwardCoreError("INVALID_CELL_OR_REPEAT")
    if frequency_start_index < 0 or frequency_start_index + frequencies.size > 256 or not np.allclose(
        frequencies, frozen_frequency_grid()[frequency_start_index:frequency_start_index + frequencies.size], rtol=1e-12, atol=0.0
    ):
        raise ForwardCoreError("FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED")
    snr_db = _number(nuisance, "snr_db")
    angle_offset = _number(nuisance, "angle_offset_degrees")
    matrices, _, passive, reciprocal, _ = assemble_system_matrices(
        member, nuisance, cell_index=cell_index, repeat_index=repeat_index, frequencies_hz=frequencies,
        partition=partition, repeat_seed_tuple=repeat_seed_tuple, path_length_m=path_length_m
    )
    sources = np.zeros((5, len(states) * 4), dtype=np.complex128)
    for state_index, state in enumerate(states):
        weights = directional_port_weights(state, angle_offset)
        for port in range(4):
            sources[port, state_index * 4 + port] = weights[port]
    solutions = np.linalg.solve(matrices, np.broadcast_to(sources, (frequencies.size, 5, len(states) * 4)))
    pressure = solutions[:, 4, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    pressure *= 10.0 ** ((_number(nuisance, "common_gain_db") + _number(nuisance, "sensor_independent_gain_db")) / 20.0)
    if include_additive_sensor_noise:
        global_frequency_indices = np.arange(frequency_start_index, frequency_start_index + frequencies.size, dtype=np.uint64)
        global_angle_indices = np.asarray([angle_global_ordinal(partition, value) for value in states], dtype=np.uint64)
        flat = ((global_angle_indices[:, None, None] * np.uint64(4) + np.arange(4, dtype=np.uint64)[None, :, None]) * np.uint64(256) + global_frequency_indices[None, None, :])
        uniforms = _substream_uniform_array(repeat_seeds[repeat_index], cell_index, repeat_index, np.uint64(8) + flat)
        phases = 2.0 * math.pi * uniforms
        pressure += 10.0 ** (-snr_db / 20.0) * (np.cos(phases) + 1j * np.sin(phases))
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError("NETWORK_NUMERIC_VALIDITY_FAIL")
    return ForwardBlockResult(MODEL_NAME, pressure, passive, reciprocal, True, valid)

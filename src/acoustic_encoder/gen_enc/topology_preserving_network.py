"""GEN-ENC-4 M1 topology-preserving five-node acoustic network.

This module deliberately leaves ``forward_acoustic_network.py`` unchanged.
The only scientific extension over that frozen M0 core is a reciprocal
local-to-local edge Laplacian whose entries are frequency-dependent lumped
admittances.  It adds neither propagation phase nor resonant state nodes.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .e2_authority import (
    E2AuthorityError,
    angle_global_ordinal,
    directional_port_weights,
    resolve_partition_repeat_seeds,
    validate_frozen_angles,
)
from .forward_acoustic_network import (
    BRANCH_HEIGHT_M,
    BRANCH_LENGTH_M,
    RHO_KG_M3,
    SPEED_OF_SOUND_M_S,
    STATE_ANGLES_DEGREES,
    SUPPORTED_FAMILIES,
    ForwardBlockResult,
    ForwardCoreError,
    _aperture_area,
    _number,
    _substream_uniform,
    _substream_uniform_array,
    _volume_partition,
    frozen_frequency_grid,
)


MODEL_NAME = "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_TOPOLOGY_PRESERVING_M1_V1"
NODE_ORDER = ("local_0", "local_90", "local_180", "local_270", "central")
ANGLE_ORDER = (0, 90, 180, 270)
ALL_UNDIRECTED_EDGES = ((0, 90), (0, 180), (0, 270), (90, 180), (90, 270), (180, 270))
RING_EDGES = ((0, 90), (90, 180), (180, 270), (270, 0))

# Result-blind budget contract.  The total positive lateral channel area is
# capped by one mid-coordinate channel.  RANDOM and PHYSICS divide this cap by
# their fixed possible-slot count, including zero slots.  NEAR's alpha is an
# explicit weak fraction of the same cap.  HAND has no local-local channel:
# its frozen manual coupling is the replicated central-mix star aperture.
REFERENCE_LATERAL_AREA_M2 = BRANCH_HEIGHT_M * (0.002 + 0.006 * 0.5)
RANDOM_SLOT_COUNT = 6
PHYSICS_SLOT_COUNT = 4
MAX_EDGE_COORDINATE = 0.8


@dataclass(frozen=True)
class EdgeChannel:
    left_angle: int
    right_angle: int
    coordinate: float
    area_m2: float


@dataclass(frozen=True)
class TopologyAudit:
    family_id: str
    semantic: str
    possible_edge_count: int
    active_edges: tuple[EdgeChannel, ...]
    total_lateral_area_m2: float
    lateral_area_budget_m2: float
    budget_fraction: float


def _validate_member(member: Mapping[str, object]) -> tuple[str, Mapping[str, object]]:
    family_id = member.get("family_id")
    if member.get("status") != "STATIC_IDENTITY_ELIGIBLE" or family_id not in SUPPORTED_FAMILIES:
        raise ForwardCoreError("UNSUPPORTED_OR_INELIGIBLE_MEMBER")
    parameters = member.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError("MISSING_PARAMETERS")
    return str(family_id), parameters


def topology_audit(member: Mapping[str, object]) -> TopologyAudit:
    """Map frozen identity coordinates to explicit undirected edge channels."""

    family_id, parameters = _validate_member(member)
    channels: list[EdgeChannel] = []
    possible = 0
    semantic: str
    if family_id == "HAND_DESIGNED":
        central_mix = _number(parameters, "central_mix")
        if not 0.1 <= central_mix <= 0.3:
            raise ForwardCoreError("HAND_CENTRAL_MIX_OUT_OF_RANGE")
        semantic = "FROZEN_REPLICATED_CENTRAL_MIX_STAR_NO_LOCAL_LOCAL_EDGE"
    elif family_id == "NEAR_INDEPENDENT":
        alpha = _number(parameters, "shared_alpha")
        if not 0.03 <= alpha <= 0.07:
            raise ForwardCoreError("NEAR_SHARED_ALPHA_OUT_OF_RANGE")
        possible = len(ALL_UNDIRECTED_EDGES)
        per_edge_area = REFERENCE_LATERAL_AREA_M2 * alpha / possible
        channels = [EdgeChannel(left, right, alpha / 4.0, per_edge_area) for left, right in ALL_UNDIRECTED_EDGES]
        semantic = "FROZEN_K0_ALPHA_WEAK_COMPLETE_GRAPH"
    elif family_id == "FIXED_SEED_RANDOM_DISORDERED":
        possible = RANDOM_SLOT_COUNT
        for left, right in ALL_UNDIRECTED_EDGES:
            coordinate = _number(parameters, f"edge_{left}_{right}")
            if not 0.0 <= coordinate <= MAX_EDGE_COORDINATE:
                raise ForwardCoreError("RANDOM_EDGE_COORDINATE_OUT_OF_RANGE")
            if coordinate > 0.0:
                area = REFERENCE_LATERAL_AREA_M2 * coordinate / (possible * MAX_EDGE_COORDINATE)
                channels.append(EdgeChannel(left, right, coordinate, area))
        semantic = "FIXED_SEED_SPARSE_UNDIRECTED_GRAPH_ZERO_EDGES_ABSENT"
    else:
        possible = PHYSICS_SLOT_COUNT
        for left, right in RING_EDGES:
            coordinate = _number(parameters, f"ring_{left}_{right}")
            if not 0.2 <= coordinate <= MAX_EDGE_COORDINATE:
                raise ForwardCoreError("PHYSICS_RING_COORDINATE_OUT_OF_RANGE")
            area = REFERENCE_LATERAL_AREA_M2 * coordinate / (possible * MAX_EDGE_COORDINATE)
            channels.append(EdgeChannel(left, right, coordinate, area))
        semantic = "ORDERED_RECIPROCAL_CARDINAL_RING"
    total_area = float(sum(channel.area_m2 for channel in channels))
    if total_area > REFERENCE_LATERAL_AREA_M2 * (1.0 + 1e-14):
        raise ForwardCoreError("LATERAL_CHANNEL_BUDGET_EXCEEDED")
    return TopologyAudit(
        family_id=family_id,
        semantic=semantic,
        possible_edge_count=possible,
        active_edges=tuple(channels),
        total_lateral_area_m2=total_area,
        lateral_area_budget_m2=REFERENCE_LATERAL_AREA_M2,
        budget_fraction=total_area / REFERENCE_LATERAL_AREA_M2,
    )


def _radial_branch_parameters(
    family_id: str,
    parameters: Mapping[str, object],
    nuisance: Mapping[str, object],
    cell_index: int,
    repeat_index: int,
    repeat_seed: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return local-central branch M/R without averaging lateral edges."""

    if family_id == "HAND_DESIGNED":
        central_mix = _number(parameters, "central_mix")
        if not 0.1 <= central_mix <= 0.3:
            raise ForwardCoreError("HAND_CENTRAL_MIX_OUT_OF_RANGE")
        central_coordinates = np.full(4, central_mix, dtype=float)
    elif family_id == "NEAR_INDEPENDENT":
        alpha = _number(parameters, "shared_alpha")
        if not 0.03 <= alpha <= 0.07:
            raise ForwardCoreError("NEAR_SHARED_ALPHA_OUT_OF_RANGE")
        normalized = min(1.0, max(0.0, (alpha - 0.03) / 0.04))
        central_coordinates = np.full(4, normalized, dtype=float)
    else:
        # RANDOM/PHYSICS local-edge coordinates are not collapsed into a
        # shared coordinate.  Their central connection is the frozen spine.
        central_coordinates = np.zeros(4, dtype=float)

    independent_percent = _number(nuisance, "independent_manufacturing_percent")
    batch_percent = _number(nuisance, "batch_correlated_manufacturing_percent")
    if not -2.0 <= independent_percent <= 2.0 or not -2.0 <= batch_percent <= 2.0:
        raise ForwardCoreError("MANUFACTURING_PERCENT_OUT_OF_RANGE")
    batch_factor = 1.0 + batch_percent / 100.0
    mix_areas = np.asarray([_aperture_area(value) for value in central_coordinates]) * batch_factor
    masses = np.empty(4, dtype=float)
    resistances = np.empty(4, dtype=float)
    for index, angle in enumerate(ANGLE_ORDER):
        signed_unit = 2.0 * _substream_uniform(repeat_seed, cell_index, repeat_index, index) - 1.0
        independent_factor = 1.0 + independent_percent * signed_unit / 100.0
        external_area = _aperture_area(_number(parameters, f"external_{angle}")) * batch_factor * independent_factor
        mix_area = mix_areas[index]
        equivalent_area = 2.0 / (1.0 / external_area + 1.0 / mix_area)
        loss = _number(parameters, f"loss_{angle}")
        if loss < 0.0:
            raise ForwardCoreError("NEGATIVE_LOSS")
        masses[index] = RHO_KG_M3 * BRANCH_LENGTH_M * (1.0 / external_area + 1.0 / mix_area)
        resistances[index] = loss * RHO_KG_M3 * SPEED_OF_SOUND_M_S / equivalent_area
    return masses, resistances


def lateral_edge_admittances(
    member: Mapping[str, object],
    nuisance: Mapping[str, object],
    frequencies_hz: Sequence[float],
) -> tuple[TopologyAudit, NDArray[np.complex128]]:
    """Return per-frequency explicit edge admittances ``1/(R+j*w*M)``."""

    audit = topology_audit(member)
    _, parameters = _validate_member(member)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    if frequencies.ndim != 1 or frequencies.size < 1 or not np.all(np.isfinite(frequencies)) or np.any(frequencies <= 0):
        raise ForwardCoreError("POSITIVE_FINITE_FREQUENCIES_REQUIRED")
    batch_percent = _number(nuisance, "batch_correlated_manufacturing_percent")
    if not -2.0 <= batch_percent <= 2.0:
        raise ForwardCoreError("MANUFACTURING_PERCENT_OUT_OF_RANGE")
    batch_factor = 1.0 + batch_percent / 100.0
    omega = 2.0 * math.pi * frequencies
    values = np.empty((frequencies.size, len(audit.active_edges)), dtype=np.complex128)
    for index, edge in enumerate(audit.active_edges):
        area = edge.area_m2 * batch_factor
        left_loss = _number(parameters, f"loss_{edge.left_angle}")
        right_loss = _number(parameters, f"loss_{edge.right_angle}")
        edge_loss = 0.5 * (left_loss + right_loss)
        if edge_loss < 0.0:
            raise ForwardCoreError("NEGATIVE_EDGE_LOSS")
        mass = RHO_KG_M3 * BRANCH_LENGTH_M / area
        resistance = edge_loss * RHO_KG_M3 * SPEED_OF_SOUND_M_S / area
        values[:, index] = 1.0 / (resistance + 1j * omega * mass)
    if not np.all(np.isfinite(values)) or np.any(values.real < -1e-15):
        raise ForwardCoreError("INVALID_LATERAL_EDGE_ADMITTANCE")
    return audit, values


def assemble_system_matrices(
    member: Mapping[str, object],
    nuisance: Mapping[str, object],
    *,
    cell_index: int,
    repeat_index: int,
    frequencies_hz: Sequence[float],
    partition: str,
    repeat_seed_tuple: Sequence[int],
) -> tuple[NDArray[np.complex128], TopologyAudit, bool, bool]:
    """Assemble the five-node system, including the explicit edge Laplacian."""

    family_id, parameters = _validate_member(member)
    try:
        repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    except E2AuthorityError as exc:
        raise ForwardCoreError(str(exc)) from exc
    frequencies = np.asarray(frequencies_hz, dtype=float)
    shift = _number(nuisance, "common_frequency_axis_shift_relative")
    if not -0.005 <= shift <= 0.005:
        raise ForwardCoreError("FREQUENCY_SHIFT_OUT_OF_RANGE")
    shifted = frequencies * (1.0 + shift)
    volumes = _volume_partition(parameters)
    compliances = volumes / (RHO_KG_M3 * SPEED_OF_SOUND_M_S**2)
    masses, resistances = _radial_branch_parameters(
        family_id, parameters, nuisance, cell_index, repeat_index, repeat_seeds[repeat_index]
    )
    omega = 2.0 * math.pi * shifted
    radial_admittance = 1.0 / (resistances[None, :] + 1j * omega[:, None] * masses[None, :])
    matrices = np.zeros((frequencies.size, 5, 5), dtype=np.complex128)
    diagonal = np.arange(5)
    matrices[:, diagonal, diagonal] = 1j * omega[:, None] * compliances[None, :]
    local = np.arange(4)
    matrices[:, local, local] += radial_admittance
    matrices[:, 4, 4] += radial_admittance.sum(axis=1)
    matrices[:, local, 4] -= radial_admittance
    matrices[:, 4, local] -= radial_admittance

    audit, edge_admittance = lateral_edge_admittances(member, nuisance, shifted)
    angle_to_index = {angle: index for index, angle in enumerate(ANGLE_ORDER)}
    for edge_index, edge in enumerate(audit.active_edges):
        left = angle_to_index[edge.left_angle]
        right = angle_to_index[edge.right_angle]
        admittance = edge_admittance[:, edge_index]
        matrices[:, left, left] += admittance
        matrices[:, right, right] += admittance
        matrices[:, left, right] -= admittance
        matrices[:, right, left] -= admittance

    reciprocal = bool(np.allclose(matrices, matrices.transpose(0, 2, 1), rtol=0.0, atol=1e-12))
    passive = bool(
        np.all(compliances > 0.0)
        and np.all(resistances >= 0.0)
        and np.all(edge_admittance.real >= -1e-15)
    )
    return matrices, audit, passive, reciprocal


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
    frequency_start_index: int = 0,
    include_additive_sensor_noise: bool = True,
) -> ForwardBlockResult:
    """Solve the M1 five-node network for one nuisance cell/repeat block."""

    if not isinstance(cell_index, int) or cell_index < 0 or not isinstance(repeat_index, int) or repeat_index not in (0, 1):
        raise ForwardCoreError("INVALID_CELL_OR_REPEAT")
    frequencies = np.asarray(frequencies_hz, dtype=float)
    try:
        states = validate_frozen_angles(partition, state_angles_degrees)
        repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    except E2AuthorityError as exc:
        raise ForwardCoreError(str(exc)) from exc
    if (
        not isinstance(frequency_start_index, int)
        or frequency_start_index < 0
        or frequencies.ndim != 1
        or frequencies.size < 1
        or frequency_start_index + frequencies.size > 256
        or not np.allclose(
            frequencies,
            frozen_frequency_grid()[frequency_start_index : frequency_start_index + frequencies.size],
            rtol=1e-12,
            atol=0.0,
        )
    ):
        raise ForwardCoreError("FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED")
    snr_db = _number(nuisance, "snr_db")
    angle_offset = _number(nuisance, "angle_offset_degrees")
    if snr_db not in (20.0, 30.0, 40.0):
        raise ForwardCoreError("SNR_LEVEL_NOT_FROZEN")
    if angle_offset not in (-5.0, -3.0, -1.0, 0.0, 1.0, 3.0, 5.0):
        raise ForwardCoreError("ANGLE_OFFSET_LEVEL_NOT_FROZEN")
    matrices, _, passive, reciprocal = assemble_system_matrices(
        member,
        nuisance,
        cell_index=cell_index,
        repeat_index=repeat_index,
        frequencies_hz=frequencies,
        partition=partition,
        repeat_seed_tuple=repeat_seed_tuple,
    )
    sources = np.zeros((5, len(states) * 4), dtype=np.complex128)
    for state_index, state_angle in enumerate(states):
        weights = directional_port_weights(state_angle, angle_offset)
        for port_index in range(4):
            sources[port_index, state_index * 4 + port_index] = weights[port_index]
    try:
        rhs = np.broadcast_to(sources, (frequencies.size, 5, len(states) * 4))
        solutions = np.linalg.solve(matrices, rhs)
    except np.linalg.LinAlgError as exc:
        raise ForwardCoreError("NETWORK_NOT_SOLVABLE") from exc
    pressure = solutions[:, 4, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    common_gain = 10.0 ** (_number(nuisance, "common_gain_db") / 20.0)
    sensor_gain = 10.0 ** (_number(nuisance, "sensor_independent_gain_db") / 20.0)
    pressure *= common_gain * sensor_gain
    if include_additive_sensor_noise:
        global_frequency_indices = np.arange(
            frequency_start_index, frequency_start_index + frequencies.size, dtype=np.uint64
        )
        global_angle_indices = np.asarray(
            [angle_global_ordinal(partition, value) for value in states], dtype=np.uint64
        )
        flat = (
            (global_angle_indices[:, None, None] * np.uint64(4) + np.arange(4, dtype=np.uint64)[None, :, None])
            * np.uint64(256)
            + global_frequency_indices[None, None, :]
        )
        uniforms = _substream_uniform_array(
            repeat_seeds[repeat_index], cell_index, repeat_index, np.uint64(8) + flat
        )
        phases = 2.0 * math.pi * uniforms
        pressure += 10.0 ** (-snr_db / 20.0) * (np.cos(phases) + 1j * np.sin(phases))
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError("NETWORK_NUMERIC_VALIDITY_FAIL")
    return ForwardBlockResult(MODEL_NAME, pressure, passive, reciprocal, True, valid)

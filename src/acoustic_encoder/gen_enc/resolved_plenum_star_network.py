"""Nine-node spatially resolved central-plenum bridge for GEN-ENC diagnostics.

Four local sector nodes connect to four boundary control volumes inside the
central plenum.  Those boundary volumes connect to a central microphone control
volume.  No direct sector-to-sector fluid path is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .actual_fluid_star_network import (
    CENTRAL_VOLUME_M3,
    Segment,
    _cascade_two_port,
    compile_member_geometry,
)
from .e2_authority import directional_port_weights, resolve_partition_repeat_seeds, validate_frozen_angles
from .forward_acoustic_network import (
    RHO_KG_M3,
    SPEED_OF_SOUND_M_S,
    ForwardCoreError,
    _number,
    _substream_uniform,
    frozen_frequency_grid,
)


MODEL_NAME = "PASSIVE_RECIPROCAL_9_NODE_SPATIALLY_RESOLVED_PLENUM_STAR_BRIDGE_V1"
PLENUM_HALF_SIDE_M = 0.0181026649639184
PLENUM_HEIGHT_M = 0.0092
PRIMARY_CENTER_VOLUME_FRACTION = 0.25
PLENUM_LINK_LENGTH_M = 0.75 * PLENUM_HALF_SIDE_M
PLENUM_LINK_AREA_M2 = PLENUM_HALF_SIDE_M * PLENUM_HEIGHT_M


@dataclass(frozen=True)
class ResolvedPlenumBlockResult:
    model_name: str
    central_pressure: NDArray[np.complex128]
    passive: bool
    reciprocal: bool
    numerically_valid: bool
    total_central_volume_m3: float


def assemble_resolved_system_matrices(
    member: Mapping[str, object],
    nuisance: Mapping[str, object],
    *,
    cell_index: int,
    repeat_index: int,
    frequencies_hz: Sequence[float],
    partition: str,
    repeat_seed_tuple: Sequence[int],
    center_volume_fraction: float = PRIMARY_CENTER_VOLUME_FRACTION,
    plenum_link_length_scale: float = 1.0,
) -> tuple[NDArray[np.complex128], bool, bool]:
    if not 0.0 < center_volume_fraction < 1.0:
        raise ForwardCoreError("CENTER_VOLUME_FRACTION_OUT_OF_RANGE")
    if not math.isfinite(plenum_link_length_scale) or plenum_link_length_scale <= 0.0:
        raise ForwardCoreError("PLENUM_LINK_LENGTH_SCALE_INVALID")
    parameters = member.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError("MISSING_PARAMETERS")
    repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    shifted = frequencies * (1.0 + _number(nuisance, "common_frequency_axis_shift_relative"))
    omega = 2.0 * math.pi * shifted
    geometries = compile_member_geometry(member, spine_only=False)
    matrices = np.zeros((frequencies.size, 9, 9), dtype=np.complex128)

    center_volume = center_volume_fraction * CENTRAL_VOLUME_M3
    boundary_volume = (1.0 - center_volume_fraction) * CENTRAL_VOLUME_M3 / 4.0
    compliances = np.asarray([boundary_volume] * 4 + [center_volume], dtype=float) / (
        RHO_KG_M3 * SPEED_OF_SOUND_M_S**2
    )
    for offset, compliance in enumerate(compliances, start=4):
        matrices[:, offset, offset] += 1j * omega * compliance

    batch = 1.0 + _number(nuisance, "batch_correlated_manufacturing_percent") / 100.0
    independent = _number(nuisance, "independent_manufacturing_percent")
    for local, geometry in enumerate(geometries):
        signed = 2.0 * _substream_uniform(repeat_seeds[repeat_index], cell_index, repeat_index, local) - 1.0
        outer_factor = 1.0 + independent * signed / 100.0
        perturbed = tuple(
            Segment(
                segment.name,
                segment.length_m,
                segment.area_m2
                * (
                    batch
                    if segment.name == "SPINE_WINDOW_ENTRY"
                    else outer_factor
                    if segment.name == "OUTER_CONNECTOR"
                    else 1.0
                ),
            )
            for segment in geometry.segments_outer_to_central
        )
        y_local, y_mutual, y_boundary = _cascade_two_port(
            shifted, perturbed, _number(parameters, f"loss_{geometry.angle}")
        )
        boundary = 4 + local
        matrices[:, local, local] += y_local
        matrices[:, boundary, boundary] += y_boundary
        matrices[:, local, boundary] -= y_mutual
        matrices[:, boundary, local] -= y_mutual

    link_length = PLENUM_LINK_LENGTH_M * plenum_link_length_scale
    link_mass = RHO_KG_M3 * link_length / PLENUM_LINK_AREA_M2
    link_admittance = 1.0 / (1j * omega * link_mass)
    for boundary in range(4, 8):
        matrices[:, boundary, boundary] += link_admittance
        matrices[:, 8, 8] += link_admittance
        matrices[:, boundary, 8] -= link_admittance
        matrices[:, 8, boundary] -= link_admittance

    reciprocal = bool(np.allclose(matrices, matrices.transpose(0, 2, 1), rtol=0.0, atol=1e-11))
    hermitian = 0.5 * (matrices.real + matrices.real.transpose(0, 2, 1))
    passive = bool(np.min(np.linalg.eigvalsh(hermitian)) >= -1e-10)
    return matrices, passive, reciprocal


def solve_resolved_clean_block(
    member: Mapping[str, object],
    nuisance: Mapping[str, object],
    *,
    cell_index: int,
    repeat_index: int,
    frequencies_hz: Sequence[float],
    state_angles_degrees: Sequence[float],
    partition: str,
    repeat_seed_tuple: Sequence[int],
    center_volume_fraction: float = PRIMARY_CENTER_VOLUME_FRACTION,
    plenum_link_length_scale: float = 1.0,
    frequency_start_index: int = 0,
) -> ResolvedPlenumBlockResult:
    frequencies = np.asarray(frequencies_hz, dtype=float)
    states = validate_frozen_angles(partition, state_angles_degrees)
    if not np.allclose(
        frequencies,
        frozen_frequency_grid()[frequency_start_index : frequency_start_index + frequencies.size],
        rtol=1e-12,
        atol=0.0,
    ):
        raise ForwardCoreError("FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED")
    matrices, passive, reciprocal = assemble_resolved_system_matrices(
        member,
        nuisance,
        cell_index=cell_index,
        repeat_index=repeat_index,
        frequencies_hz=frequencies,
        partition=partition,
        repeat_seed_tuple=repeat_seed_tuple,
        center_volume_fraction=center_volume_fraction,
        plenum_link_length_scale=plenum_link_length_scale,
    )
    sources = np.zeros((9, len(states) * 4), dtype=np.complex128)
    offset = _number(nuisance, "angle_offset_degrees")
    for state_index, state in enumerate(states):
        weights = directional_port_weights(state, offset)
        for port in range(4):
            sources[port, state_index * 4 + port] = weights[port]
    solutions = np.linalg.solve(matrices, np.broadcast_to(sources, (frequencies.size, 9, len(states) * 4)))
    pressure = solutions[:, 8, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError("RESOLVED_PLENUM_NUMERIC_VALIDITY_FAIL")
    return ResolvedPlenumBlockResult(
        MODEL_NAME,
        pressure,
        passive,
        reciprocal,
        valid,
        CENTRAL_VOLUME_M3,
    )

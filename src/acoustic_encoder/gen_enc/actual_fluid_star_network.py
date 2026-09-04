"""Piecewise distributed actual-fluid star model for GEN-ENC-4 M2-B."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .e2_authority import angle_global_ordinal, directional_port_weights, resolve_partition_repeat_seeds, validate_frozen_angles
from .forward_acoustic_network import (
    RHO_KG_M3, SPEED_OF_SOUND_M_S, TOTAL_VOLUME_M3, ForwardBlockResult, ForwardCoreError,
    _number, _substream_uniform, _substream_uniform_array, frozen_frequency_grid,
)


MODEL_NAME = "PASSIVE_RECIPROCAL_PIECEWISE_ACTUAL_FLUID_STAR_M2B_V1"
ANGLES = (0, 90, 180, 270)
CENTRAL_VOLUME_M3 = 0.40 * TOTAL_VOLUME_M3
ROOT_SPAN_M = 0.058926678767398356
ROOT_BOUNDS_M = (0.002, 0.030)
FIXED_VOLUME_M3 = 2.1848e-6
INNER_AREA_M2 = 4.0e-6
CAVITY_AREA_M2 = 1.054e-4
REFERENCE_LOSS_LENGTH_M = 0.002


@dataclass(frozen=True)
class Segment:
    name: str
    length_m: float
    area_m2: float


@dataclass(frozen=True)
class SectorGeometry:
    angle: int
    root_length_m: float
    target_volume_m3: float
    segment_volume_m3: float
    window_union_area_m2: float
    outer_area_m2: float
    segments_outer_to_central: tuple[Segment, ...]


def _width(coordinate: float) -> float:
    if not 0.0 <= coordinate <= 1.0:
        raise ForwardCoreError("APERTURE_COORDINATE_OUT_OF_RANGE")
    return 0.002 + 0.006 * coordinate


def _family_parameters(member: Mapping[str, object]) -> tuple[str, Mapping[str, object]]:
    family = member.get("family_id")
    parameters = member.get("parameters")
    if member.get("status") != "STATIC_IDENTITY_ELIGIBLE" or not isinstance(family, str) or not isinstance(parameters, Mapping):
        raise ForwardCoreError("UNSUPPORTED_OR_INELIGIBLE_MEMBER")
    return family, parameters


def _sector_slot_widths(family: str, p: Mapping[str, object], angle: int, spine_only: bool) -> tuple[float, float, float]:
    if spine_only:
        return 0.0, 0.002, 0.0
    if family == "HAND_DESIGNED":
        return 0.0, _width(_number(p, "central_mix")), 0.0
    if family == "NEAR_INDEPENDENT":
        normalized = min(1.0, max(0.0, (_number(p, "shared_alpha") - 0.03) / 0.04))
        return 0.0, _width(normalized), 0.0
    if family == "FIXED_SEED_RANDOM_DISORDERED":
        keys = {
            0: ("edge_0_90", "edge_0_180", "edge_0_270"),
            90: ("edge_0_90", "edge_90_180", "edge_90_270"),
            180: ("edge_0_180", "edge_90_180", "edge_180_270"),
            270: ("edge_0_270", "edge_90_270", "edge_180_270"),
        }[angle]
        return tuple(0.0 if _number(p, key) == 0.0 else _width(_number(p, key)) for key in keys)  # type: ignore[return-value]
    if family == "PHYSICS_METAMATERIAL_INSPIRED":
        keys = {
            0: ("ring_0_90", "ring_270_0"), 90: ("ring_0_90", "ring_90_180"),
            180: ("ring_90_180", "ring_180_270"), 270: ("ring_180_270", "ring_270_0"),
        }[angle]
        return _width(_number(p, keys[0])), _width(_number(p, keys[1])), 0.0
    raise ForwardCoreError("UNSUPPORTED_FAMILY")


def _outer_area(family: str, p: Mapping[str, object], angle: int) -> float:
    coordinate = 0.5 if family == "FIXED_SEED_RANDOM_DISORDERED" else _number(p, f"external_{angle}")
    return 0.002 * _width(coordinate)


def _root_for_target(target: float, outer_area: float, window_volume: float) -> float:
    def volume(length: float) -> float:
        return FIXED_VOLUME_M3 + (INNER_AREA_M2 + outer_area) * (ROOT_SPAN_M - length) / 2.0 + CAVITY_AREA_M2 * length + window_volume
    low, high = ROOT_BOUNDS_M
    if not volume(low) <= target <= volume(high):
        raise ForwardCoreError("SECTOR_ROOT_NOT_BRACKETED")
    for _ in range(80):
        mid = (low + high) / 2.0
        if volume(mid) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def compile_member_geometry(member: Mapping[str, object], *, spine_only: bool) -> tuple[SectorGeometry, ...]:
    family, p = _family_parameters(member)
    weights = np.exp(np.asarray([_number(p, f"q{angle}") for angle in ANGLES]))
    targets = 0.60 * TOTAL_VOLUME_M3 * weights / weights.sum()
    result = []
    for angle, target in zip(ANGLES, targets):
        w1, w2, w3 = _sector_slot_widths(family, p, angle, spine_only)
        union_width = w1 + max(0.002, w2) + w3
        entry_area = 0.002 * union_width
        outer_area = _outer_area(family, p, angle)
        root = _root_for_target(float(target), outer_area, entry_area * 0.002)
        connector = (ROOT_SPAN_M - root) / 2.0
        segments = (
            Segment("COLLAR", 0.002, 0.016 * 0.0092),
            Segment("OUTER_STEP_3", 0.004, 0.016 * 0.0082),
            Segment("OUTER_STEP_2", 0.005, 0.012 * 0.0082),
            Segment("OUTER_STEP_1", 0.006, 0.008 * 0.0082),
            Segment("OUTER_CONNECTOR", connector, outer_area),
            Segment("CAVITY", root, CAVITY_AREA_M2),
            Segment("INNER_CONNECTOR", connector, INNER_AREA_M2),
            Segment("COLLECTOR", 0.008, 0.030 * 0.002),
            Segment("SPINE_WINDOW_ENTRY", 0.002, entry_area),
        )
        segment_volume = float(sum(item.length_m * item.area_m2 for item in segments))
        if not math.isclose(segment_volume, float(target), rel_tol=0.0, abs_tol=1e-12):
            raise ForwardCoreError("SEGMENT_VOLUME_TARGET_MISMATCH")
        result.append(SectorGeometry(angle, root, float(target), segment_volume, entry_area, outer_area, segments))
    return tuple(result)


def _cascade_two_port(frequencies_hz: NDArray[np.float64], segments: Sequence[Segment], loss: float) -> tuple[NDArray[np.complex128], NDArray[np.complex128], NDArray[np.complex128]]:
    omega = 2.0 * math.pi * frequencies_hz
    total = np.broadcast_to(np.eye(2, dtype=np.complex128), (frequencies_hz.size, 2, 2)).copy()
    for segment in segments:
        series = loss * RHO_KG_M3 * SPEED_OF_SOUND_M_S / (segment.area_m2 * REFERENCE_LOSS_LENGTH_M) + 1j * omega * RHO_KG_M3 / segment.area_m2
        shunt = 1j * omega * segment.area_m2 / (RHO_KG_M3 * SPEED_OF_SOUND_M_S**2)
        gamma = np.sqrt(series * shunt)
        impedance = np.sqrt(series / shunt)
        gl = gamma * segment.length_m
        matrix = np.empty_like(total)
        matrix[:, 0, 0] = np.cosh(gl)
        matrix[:, 0, 1] = impedance * np.sinh(gl)
        matrix[:, 1, 0] = np.sinh(gl) / impedance
        matrix[:, 1, 1] = np.cosh(gl)
        total = total @ matrix
    a, b, d = total[:, 0, 0], total[:, 0, 1], total[:, 1, 1]
    return d / b, 1.0 / b, a / b


def assemble_system_matrices(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], spine_only: bool, geometry_override: tuple[SectorGeometry, ...] | None = None) -> tuple[NDArray[np.complex128], tuple[SectorGeometry, ...], bool, bool]:
    _, p = _family_parameters(member)
    repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    shifted = frequencies * (1.0 + _number(nuisance, "common_frequency_axis_shift_relative"))
    geometries = geometry_override if geometry_override is not None else compile_member_geometry(member, spine_only=spine_only)
    if len(geometries) != 4:
        raise ForwardCoreError("EXACT_FOUR_SECTOR_GEOMETRIES_REQUIRED")
    matrices = np.zeros((frequencies.size, 5, 5), dtype=np.complex128)
    matrices[:, 4, 4] = 1j * 2.0 * math.pi * shifted * CENTRAL_VOLUME_M3 / (RHO_KG_M3 * SPEED_OF_SOUND_M_S**2)
    batch = 1.0 + _number(nuisance, "batch_correlated_manufacturing_percent") / 100.0
    independent = _number(nuisance, "independent_manufacturing_percent")
    for local, geometry in enumerate(geometries):
        signed = 2.0 * _substream_uniform(repeat_seeds[repeat_index], cell_index, repeat_index, local) - 1.0
        outer_factor = 1.0 + independent * signed / 100.0
        perturbed = tuple(Segment(s.name, s.length_m, s.area_m2 * (batch if s.name == "SPINE_WINDOW_ENTRY" else outer_factor if s.name == "OUTER_CONNECTOR" else 1.0)) for s in geometry.segments_outer_to_central)
        y_local, y_mutual, y_central = _cascade_two_port(shifted, perturbed, _number(p, f"loss_{geometry.angle}"))
        matrices[:, local, local] += y_local
        matrices[:, 4, 4] += y_central
        matrices[:, local, 4] -= y_mutual
        matrices[:, 4, local] -= y_mutual
    reciprocal = bool(np.allclose(matrices, matrices.transpose(0, 2, 1), rtol=0.0, atol=1e-11))
    hermitian = 0.5 * (matrices.real + matrices.real.transpose(0, 2, 1))
    passive = bool(np.min(np.linalg.eigvalsh(hermitian)) >= -1e-10)
    return matrices, geometries, passive, reciprocal


def solve_forward_block(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], state_angles_degrees: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], spine_only: bool, frequency_start_index: int = 0, include_additive_sensor_noise: bool = True, geometry_override: tuple[SectorGeometry, ...] | None = None) -> ForwardBlockResult:
    frequencies = np.asarray(frequencies_hz, dtype=float)
    states = validate_frozen_angles(partition, state_angles_degrees)
    seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    if not np.allclose(frequencies, frozen_frequency_grid()[frequency_start_index:frequency_start_index + frequencies.size], rtol=1e-12, atol=0.0):
        raise ForwardCoreError("FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED")
    matrices, _, passive, reciprocal = assemble_system_matrices(member, nuisance, cell_index=cell_index, repeat_index=repeat_index, frequencies_hz=frequencies, partition=partition, repeat_seed_tuple=repeat_seed_tuple, spine_only=spine_only, geometry_override=geometry_override)
    sources = np.zeros((5, len(states) * 4), dtype=np.complex128)
    offset = _number(nuisance, "angle_offset_degrees")
    for state_index, state in enumerate(states):
        weights = directional_port_weights(state, offset)
        for port in range(4):
            sources[port, state_index * 4 + port] = weights[port]
    solutions = np.linalg.solve(matrices, np.broadcast_to(sources, (frequencies.size, 5, len(states) * 4)))
    pressure = solutions[:, 4, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    pressure *= 10.0 ** ((_number(nuisance, "common_gain_db") + _number(nuisance, "sensor_independent_gain_db")) / 20.0)
    if include_additive_sensor_noise:
        gf = np.arange(frequency_start_index, frequency_start_index + frequencies.size, dtype=np.uint64)
        ga = np.asarray([angle_global_ordinal(partition, x) for x in states], dtype=np.uint64)
        flat = ((ga[:, None, None] * np.uint64(4) + np.arange(4, dtype=np.uint64)[None, :, None]) * np.uint64(256) + gf[None, None, :])
        phases = 2.0 * math.pi * _substream_uniform_array(seeds[repeat_index], cell_index, repeat_index, np.uint64(8) + flat)
        pressure += 10.0 ** (-_number(nuisance, "snr_db") / 20.0) * (np.cos(phases) + 1j * np.sin(phases))
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError("NETWORK_NUMERIC_VALIDITY_FAIL")
    return ForwardBlockResult(MODEL_NAME, pressure, passive, reciprocal, True, valid)


def solve_clean_node_pressure_block(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], state_angles_degrees: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], spine_only: bool, frequency_start_index: int = 0, geometry_override: tuple[SectorGeometry, ...] | None = None) -> NDArray[np.complex128]:
    """OBS-A instrumentation: return clean pressure at all four ports and plenum.

    Shape is ``state, excitation_port, frequency, node``.  This leaves the
    established central-microphone solver and its noise semantics unchanged.
    """

    frequencies = np.asarray(frequencies_hz, dtype=float)
    states = validate_frozen_angles(partition, state_angles_degrees)
    if not np.allclose(frequencies, frozen_frequency_grid()[frequency_start_index:frequency_start_index + frequencies.size], rtol=1e-12, atol=0.0):
        raise ForwardCoreError("FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED")
    matrices, _, passive, reciprocal = assemble_system_matrices(member, nuisance, cell_index=cell_index, repeat_index=repeat_index, frequencies_hz=frequencies, partition=partition, repeat_seed_tuple=repeat_seed_tuple, spine_only=spine_only, geometry_override=geometry_override)
    sources = np.zeros((5, len(states) * 4), dtype=np.complex128)
    offset = _number(nuisance, "angle_offset_degrees")
    for state_index, state in enumerate(states):
        weights = directional_port_weights(state, offset)
        for port in range(4):
            sources[port, state_index * 4 + port] = weights[port]
    solutions = np.linalg.solve(matrices, np.broadcast_to(sources, (frequencies.size, 5, len(states) * 4)))
    nodes = solutions.reshape(frequencies.size, 5, len(states), 4).transpose(2, 3, 0, 1).copy()
    if not passive or not reciprocal or not np.all(np.isfinite(nodes)):
        raise ForwardCoreError("NODE_INSTRUMENTATION_VALIDITY_FAIL")
    return nodes

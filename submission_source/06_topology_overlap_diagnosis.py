"""Topology overlap diagnosis.
Numerical functions and frozen parameters used in Draft 18.
Run this script to calculate the bounded example from its supplied datasets.
Additional original numerical functions are available for explicit use.
Requirements: Python 3.11+ and NumPy; SciPy/scikit-learn where imported.
"""
from __future__ import annotations
from pathlib import Path
import json
import csv
from dataclasses import dataclass
from numpy.typing import NDArray
from typing import Any
from typing import Mapping
from typing import Sequence
import math
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "06_topology_overlap_diagnosis"


# E2 authority

PORT_ANGLES_DEGREES = (0.0, 90.0, 180.0, 270.0)

DEVELOPMENT_ANGLES_DEGREES = PORT_ANGLES_DEGREES

VALIDATION_ANGLES_DEGREES = tuple((float(value) for value in range(0, 360, 15)))

DEVELOPMENT_REPEAT_SEEDS = (2026091001, 2026091002)

SINGLE_USE_VALIDATION_REPEAT_SEEDS = (2026092001, 2026092002)

PARTITION_REPEAT_SEEDS = {'development': DEVELOPMENT_REPEAT_SEEDS, 'single_use_validation': SINGLE_USE_VALIDATION_REPEAT_SEEDS}

class E2AuthorityError(ValueError):
    """Fail-closed authority-rule violation."""

def resolve_partition_repeat_seeds(partition: str, repeat_seeds: Sequence[int]) -> tuple[int, int]:
    """Require the exact immutable two-seed tuple for the named partition."""
    if partition not in PARTITION_REPEAT_SEEDS:
        raise E2AuthorityError('UNKNOWN_E2_PARTITION')
    if isinstance(repeat_seeds, (str, bytes)):
        raise E2AuthorityError('REPEAT_SEED_TUPLE_REQUIRED')
    observed = tuple(repeat_seeds)
    expected = PARTITION_REPEAT_SEEDS[partition]
    if observed != expected:
        raise E2AuthorityError('PARTITION_REPEAT_SEED_TUPLE_MISMATCH')
    return expected

def validate_frozen_angles(partition: str, angles_degrees: Sequence[float]) -> tuple[float, ...]:
    """Validate a nonempty canonical-order subset of a partition's frozen angles."""
    if partition not in PARTITION_REPEAT_SEEDS:
        raise E2AuthorityError('UNKNOWN_E2_PARTITION')
    allowed = DEVELOPMENT_ANGLES_DEGREES if partition == 'development' else VALIDATION_ANGLES_DEGREES
    angles = tuple((float(value) for value in angles_degrees))
    if not angles or any((not math.isfinite(value) for value in angles)):
        raise E2AuthorityError('FINITE_FROZEN_ANGLE_SUBSET_REQUIRED')
    indices: list[int] = []
    for value in angles:
        try:
            indices.append(allowed.index(value))
        except ValueError as exc:
            raise E2AuthorityError('ANGLE_OUTSIDE_FROZEN_PARTITION_GRID') from exc
    if indices != sorted(set(indices)):
        raise E2AuthorityError('FROZEN_ANGLE_CANONICAL_ORDER_REQUIRED')
    return angles

def angle_global_ordinal(partition: str, angle_degrees: float) -> int:
    if partition not in PARTITION_REPEAT_SEEDS:
        raise E2AuthorityError('UNKNOWN_E2_PARTITION')
    allowed = DEVELOPMENT_ANGLES_DEGREES if partition == 'development' else VALIDATION_ANGLES_DEGREES
    try:
        return allowed.index(float(angle_degrees))
    except ValueError as exc:
        raise E2AuthorityError('ANGLE_OUTSIDE_FROZEN_PARTITION_GRID') from exc

def directional_port_weights(angle_degrees: float, angle_offset_degrees: float) -> NDArray[np.float64]:
    """Return the L2-normalized, common-zero-phase angle-to-port vector."""
    theta = float(angle_degrees)
    offset = float(angle_offset_degrees)
    if not math.isfinite(theta) or not math.isfinite(offset):
        raise E2AuthorityError('FINITE_ANGLE_AND_OFFSET_REQUIRED')
    theta_effective = (theta + offset) % 360.0
    radians = np.deg2rad(theta_effective - np.asarray(PORT_ANGLES_DEGREES, dtype=np.float64))
    raw = np.maximum(0.0, np.cos(radians))
    raw[np.abs(raw) < 1e-15] = 0.0
    norm = float(np.linalg.norm(raw, ord=2))
    if not math.isfinite(norm) or norm <= 0.0:
        raise E2AuthorityError('ANGLE_TO_PORT_VECTOR_UNAVAILABLE')
    weights = raw / norm
    weights[np.abs(weights) < 1e-15] = 0.0
    return weights


# Prng

MASK64 = (1 << 64) - 1

GOLDEN_GAMMA = 11400714819323198485

def _uint64(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError('uint64 input must be an integer')
    return value & MASK64

def splitmix64(x: int) -> int:
    """Apply the exact REV01 SplitMix64 function to one uint64 input."""
    z = _uint64(x) + GOLDEN_GAMMA & MASK64
    z = (z ^ z >> 30) * 13787848793156543929 & MASK64
    z = (z ^ z >> 27) * 10723151780598845931 & MASK64
    return (z ^ z >> 31) & MASK64

def open_interval_uniform53(z: int) -> float:
    """Map one uint64 word to the frozen 53-bit open-interval uniform."""
    value = _uint64(z)
    result = ((value >> 11) + 0.5) / float(1 << 53)
    if result == 1.0:
        result = math.nextafter(1.0, 0.0)
    if not 0.0 < result < 1.0:
        raise ArithmeticError('uniform conversion left the open interval')
    return result


# Forward acoustic network

RHO_KG_M3 = 1.2041

SPEED_OF_SOUND_M_S = 343.0

TOTAL_VOLUME_M3 = 3.014899604922098e-05

BRANCH_HEIGHT_M = 0.0092

BRANCH_LENGTH_M = 0.002

SUPPORTED_FAMILIES = ('HAND_DESIGNED', 'NEAR_INDEPENDENT', 'FIXED_SEED_RANDOM_DISORDERED', 'PHYSICS_METAMATERIAL_INSPIRED')

class ForwardCoreError(RuntimeError):
    """Fail-closed invalid-input or numerical-core error."""

@dataclass(frozen=True)
class ForwardBlockResult:
    model_name: str
    central_pressure: NDArray[np.complex128]
    passive: bool
    reciprocal: bool
    solvable: bool
    numerically_valid: bool

def frozen_frequency_grid() -> NDArray[np.float64]:
    """Return exact f[n]=200*2**(n/48), n=0..255."""
    return 200.0 * np.power(2.0, np.arange(256, dtype=np.float64) / 48.0)

def _number(mapping: Mapping[str, object], name: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (not math.isfinite(value)):
        raise ForwardCoreError(f'INVALID_{name.upper()}')
    return float(value)

def _aperture_area(coordinate: float) -> float:
    if not 0.0 <= coordinate <= 1.0:
        raise ForwardCoreError('APERTURE_COORDINATE_OUT_OF_RANGE')
    return BRANCH_HEIGHT_M * (0.002 + 0.006 * coordinate)

def _volume_partition(parameters: Mapping[str, object]) -> NDArray[np.float64]:
    q = np.array([_number(parameters, f'q{angle}') for angle in (0, 90, 180, 270)], dtype=float)
    if np.any(q < -0.12) or np.any(q > 0.12):
        raise ForwardCoreError('VOLUME_LOGIT_OUT_OF_RANGE')
    weights = np.exp(q)
    local = 0.6 * TOTAL_VOLUME_M3 * weights / weights.sum()
    return np.concatenate((local, np.array([0.4 * TOTAL_VOLUME_M3])))

def _substream_uniform(base_seed: int, cell_index: int, repeat_index: int, substream: int) -> float:
    x = base_seed + GOLDEN_GAMMA * (1 + 64 * cell_index + 32 * repeat_index + substream) & MASK64
    return open_interval_uniform53(splitmix64(x))

def _substream_uniform_array(base_seed: int, cell_index: int, repeat_index: int, substreams: NDArray[np.uint64]) -> NDArray[np.float64]:
    """Vectorized exact SplitMix64/open-interval transform used by the scalar reference."""
    with np.errstate(over='ignore'):
        x = np.uint64(base_seed) + np.uint64(GOLDEN_GAMMA) * (np.uint64(1 + 64 * cell_index + 32 * repeat_index) + substreams)
        z = x + np.uint64(GOLDEN_GAMMA)
        z = (z ^ z >> np.uint64(30)) * np.uint64(13787848793156543929)
        z = (z ^ z >> np.uint64(27)) * np.uint64(10723151780598845931)
        z = z ^ z >> np.uint64(31)
    return ((z >> np.uint64(11)).astype(np.float64) + 0.5) / float(1 << 53)


# Actual fluid star network

ANGLES = (0, 90, 180, 270)

CENTRAL_VOLUME_M3 = 0.4 * TOTAL_VOLUME_M3

ROOT_SPAN_M = 0.058926678767398356

ROOT_BOUNDS_M = (0.002, 0.03)

FIXED_VOLUME_M3 = 2.1848e-06

INNER_AREA_M2 = 4e-06

CAVITY_AREA_M2 = 0.0001054

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
        raise ForwardCoreError('APERTURE_COORDINATE_OUT_OF_RANGE')
    return 0.002 + 0.006 * coordinate

def _family_parameters(member: Mapping[str, object]) -> tuple[str, Mapping[str, object]]:
    family = member.get('family_id')
    parameters = member.get('parameters')
    if member.get('status') != 'STATIC_IDENTITY_ELIGIBLE' or not isinstance(family, str) or (not isinstance(parameters, Mapping)):
        raise ForwardCoreError('UNSUPPORTED_OR_INELIGIBLE_MEMBER')
    return (family, parameters)

def _sector_slot_widths(family: str, p: Mapping[str, object], angle: int, spine_only: bool) -> tuple[float, float, float]:
    if spine_only:
        return (0.0, 0.002, 0.0)
    if family == 'HAND_DESIGNED':
        return (0.0, _width(_number(p, 'central_mix')), 0.0)
    if family == 'NEAR_INDEPENDENT':
        normalized = min(1.0, max(0.0, (_number(p, 'shared_alpha') - 0.03) / 0.04))
        return (0.0, _width(normalized), 0.0)
    if family == 'FIXED_SEED_RANDOM_DISORDERED':
        keys = {0: ('edge_0_90', 'edge_0_180', 'edge_0_270'), 90: ('edge_0_90', 'edge_90_180', 'edge_90_270'), 180: ('edge_0_180', 'edge_90_180', 'edge_180_270'), 270: ('edge_0_270', 'edge_90_270', 'edge_180_270')}[angle]
        return tuple((0.0 if _number(p, key) == 0.0 else _width(_number(p, key)) for key in keys))
    if family == 'PHYSICS_METAMATERIAL_INSPIRED':
        keys = {0: ('ring_0_90', 'ring_270_0'), 90: ('ring_0_90', 'ring_90_180'), 180: ('ring_90_180', 'ring_180_270'), 270: ('ring_180_270', 'ring_270_0')}[angle]
        return (_width(_number(p, keys[0])), _width(_number(p, keys[1])), 0.0)
    raise ForwardCoreError('UNSUPPORTED_FAMILY')

def _outer_area(family: str, p: Mapping[str, object], angle: int) -> float:
    coordinate = 0.5 if family == 'FIXED_SEED_RANDOM_DISORDERED' else _number(p, f'external_{angle}')
    return 0.002 * _width(coordinate)

def _root_for_target(target: float, outer_area: float, window_volume: float) -> float:

    def volume(length: float) -> float:
        return FIXED_VOLUME_M3 + (INNER_AREA_M2 + outer_area) * (ROOT_SPAN_M - length) / 2.0 + CAVITY_AREA_M2 * length + window_volume
    low, high = ROOT_BOUNDS_M
    if not volume(low) <= target <= volume(high):
        raise ForwardCoreError('SECTOR_ROOT_NOT_BRACKETED')
    for _ in range(80):
        mid = (low + high) / 2.0
        if volume(mid) < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0

def compile_member_geometry(member: Mapping[str, object], *, spine_only: bool) -> tuple[SectorGeometry, ...]:
    family, p = _family_parameters(member)
    weights = np.exp(np.asarray([_number(p, f'q{angle}') for angle in ANGLES]))
    targets = 0.6 * TOTAL_VOLUME_M3 * weights / weights.sum()
    result = []
    for angle, target in zip(ANGLES, targets):
        w1, w2, w3 = _sector_slot_widths(family, p, angle, spine_only)
        union_width = w1 + max(0.002, w2) + w3
        entry_area = 0.002 * union_width
        outer_area = _outer_area(family, p, angle)
        root = _root_for_target(float(target), outer_area, entry_area * 0.002)
        connector = (ROOT_SPAN_M - root) / 2.0
        segments = (Segment('COLLAR', 0.002, 0.016 * 0.0092), Segment('OUTER_STEP_3', 0.004, 0.016 * 0.0082), Segment('OUTER_STEP_2', 0.005, 0.012 * 0.0082), Segment('OUTER_STEP_1', 0.006, 0.008 * 0.0082), Segment('OUTER_CONNECTOR', connector, outer_area), Segment('CAVITY', root, CAVITY_AREA_M2), Segment('INNER_CONNECTOR', connector, INNER_AREA_M2), Segment('COLLECTOR', 0.008, 0.03 * 0.002), Segment('SPINE_WINDOW_ENTRY', 0.002, entry_area))
        segment_volume = float(sum((item.length_m * item.area_m2 for item in segments)))
        if not math.isclose(segment_volume, float(target), rel_tol=0.0, abs_tol=1e-12):
            raise ForwardCoreError('SEGMENT_VOLUME_TARGET_MISMATCH')
        result.append(SectorGeometry(angle, root, float(target), segment_volume, entry_area, outer_area, segments))
    return tuple(result)

def _cascade_two_port(frequencies_hz: NDArray[np.float64], segments: Sequence[Segment], loss: float) -> tuple[NDArray[np.complex128], NDArray[np.complex128], NDArray[np.complex128]]:
    omega = 2.0 * math.pi * frequencies_hz
    total = np.broadcast_to(np.eye(2, dtype=np.complex128), (frequencies_hz.size, 2, 2)).copy()
    for segment in segments:
        series = loss * RHO_KG_M3 * SPEED_OF_SOUND_M_S / (segment.area_m2 * REFERENCE_LOSS_LENGTH_M) + 1j * omega * RHO_KG_M3 / segment.area_m2
        shunt = 1j * omega * segment.area_m2 / (RHO_KG_M3 * SPEED_OF_SOUND_M_S ** 2)
        gamma = np.sqrt(series * shunt)
        impedance = np.sqrt(series / shunt)
        gl = gamma * segment.length_m
        matrix = np.empty_like(total)
        matrix[:, 0, 0] = np.cosh(gl)
        matrix[:, 0, 1] = impedance * np.sinh(gl)
        matrix[:, 1, 0] = np.sinh(gl) / impedance
        matrix[:, 1, 1] = np.cosh(gl)
        total = total @ matrix
    a, b, d = (total[:, 0, 0], total[:, 0, 1], total[:, 1, 1])
    return (d / b, 1.0 / b, a / b)

def fluid_assemble_system_matrices(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], spine_only: bool, geometry_override: tuple[SectorGeometry, ...] | None=None) -> tuple[NDArray[np.complex128], tuple[SectorGeometry, ...], bool, bool]:
    _, p = _family_parameters(member)
    repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    shifted = frequencies * (1.0 + _number(nuisance, 'common_frequency_axis_shift_relative'))
    geometries = geometry_override if geometry_override is not None else compile_member_geometry(member, spine_only=spine_only)
    if len(geometries) != 4:
        raise ForwardCoreError('EXACT_FOUR_SECTOR_GEOMETRIES_REQUIRED')
    matrices = np.zeros((frequencies.size, 5, 5), dtype=np.complex128)
    matrices[:, 4, 4] = 1j * 2.0 * math.pi * shifted * CENTRAL_VOLUME_M3 / (RHO_KG_M3 * SPEED_OF_SOUND_M_S ** 2)
    batch = 1.0 + _number(nuisance, 'batch_correlated_manufacturing_percent') / 100.0
    independent = _number(nuisance, 'independent_manufacturing_percent')
    for local, geometry in enumerate(geometries):
        signed = 2.0 * _substream_uniform(repeat_seeds[repeat_index], cell_index, repeat_index, local) - 1.0
        outer_factor = 1.0 + independent * signed / 100.0
        perturbed = tuple((Segment(s.name, s.length_m, s.area_m2 * (batch if s.name == 'SPINE_WINDOW_ENTRY' else outer_factor if s.name == 'OUTER_CONNECTOR' else 1.0)) for s in geometry.segments_outer_to_central))
        y_local, y_mutual, y_central = _cascade_two_port(shifted, perturbed, _number(p, f'loss_{geometry.angle}'))
        matrices[:, local, local] += y_local
        matrices[:, 4, 4] += y_central
        matrices[:, local, 4] -= y_mutual
        matrices[:, 4, local] -= y_mutual
    reciprocal = bool(np.allclose(matrices, matrices.transpose(0, 2, 1), rtol=0.0, atol=1e-11))
    hermitian = 0.5 * (matrices.real + matrices.real.transpose(0, 2, 1))
    passive = bool(np.min(np.linalg.eigvalsh(hermitian)) >= -1e-10)
    return (matrices, geometries, passive, reciprocal)

def solve_clean_node_pressure_block(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], state_angles_degrees: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], spine_only: bool, frequency_start_index: int=0, geometry_override: tuple[SectorGeometry, ...] | None=None) -> NDArray[np.complex128]:
    """OBS-A instrumentation: return clean pressure at all four ports and plenum.

    Shape is ``state, excitation_port, frequency, node``.  This leaves the
    established central-microphone solver and its noise semantics unchanged.
    """
    frequencies = np.asarray(frequencies_hz, dtype=float)
    states = validate_frozen_angles(partition, state_angles_degrees)
    if not np.allclose(frequencies, frozen_frequency_grid()[frequency_start_index:frequency_start_index + frequencies.size], rtol=1e-12, atol=0.0):
        raise ForwardCoreError('FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED')
    matrices, _, passive, reciprocal = fluid_assemble_system_matrices(member, nuisance, cell_index=cell_index, repeat_index=repeat_index, frequencies_hz=frequencies, partition=partition, repeat_seed_tuple=repeat_seed_tuple, spine_only=spine_only, geometry_override=geometry_override)
    sources = np.zeros((5, len(states) * 4), dtype=np.complex128)
    offset = _number(nuisance, 'angle_offset_degrees')
    for state_index, state in enumerate(states):
        weights = directional_port_weights(state, offset)
        for port in range(4):
            sources[port, state_index * 4 + port] = weights[port]
    solutions = np.linalg.solve(matrices, np.broadcast_to(sources, (frequencies.size, 5, len(states) * 4)))
    nodes = solutions.reshape(frequencies.size, 5, len(states), 4).transpose(2, 3, 0, 1).copy()
    if not passive or not reciprocal or (not np.all(np.isfinite(nodes))):
        raise ForwardCoreError('NODE_INSTRUMENTATION_VALIDITY_FAIL')
    return nodes


# Resolved plenum star network

plenum_MODEL_NAME = 'PASSIVE_RECIPROCAL_9_NODE_SPATIALLY_RESOLVED_PLENUM_STAR_BRIDGE_V1'

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

def assemble_resolved_system_matrices(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], center_volume_fraction: float=PRIMARY_CENTER_VOLUME_FRACTION, plenum_link_length_scale: float=1.0) -> tuple[NDArray[np.complex128], bool, bool]:
    if not 0.0 < center_volume_fraction < 1.0:
        raise ForwardCoreError('CENTER_VOLUME_FRACTION_OUT_OF_RANGE')
    if not math.isfinite(plenum_link_length_scale) or plenum_link_length_scale <= 0.0:
        raise ForwardCoreError('PLENUM_LINK_LENGTH_SCALE_INVALID')
    parameters = member.get('parameters')
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError('MISSING_PARAMETERS')
    repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    shifted = frequencies * (1.0 + _number(nuisance, 'common_frequency_axis_shift_relative'))
    omega = 2.0 * math.pi * shifted
    geometries = compile_member_geometry(member, spine_only=False)
    matrices = np.zeros((frequencies.size, 9, 9), dtype=np.complex128)
    center_volume = center_volume_fraction * CENTRAL_VOLUME_M3
    boundary_volume = (1.0 - center_volume_fraction) * CENTRAL_VOLUME_M3 / 4.0
    compliances = np.asarray([boundary_volume] * 4 + [center_volume], dtype=float) / (RHO_KG_M3 * SPEED_OF_SOUND_M_S ** 2)
    for offset, compliance in enumerate(compliances, start=4):
        matrices[:, offset, offset] += 1j * omega * compliance
    batch = 1.0 + _number(nuisance, 'batch_correlated_manufacturing_percent') / 100.0
    independent = _number(nuisance, 'independent_manufacturing_percent')
    for local, geometry in enumerate(geometries):
        signed = 2.0 * _substream_uniform(repeat_seeds[repeat_index], cell_index, repeat_index, local) - 1.0
        outer_factor = 1.0 + independent * signed / 100.0
        perturbed = tuple((Segment(segment.name, segment.length_m, segment.area_m2 * (batch if segment.name == 'SPINE_WINDOW_ENTRY' else outer_factor if segment.name == 'OUTER_CONNECTOR' else 1.0)) for segment in geometry.segments_outer_to_central))
        y_local, y_mutual, y_boundary = _cascade_two_port(shifted, perturbed, _number(parameters, f'loss_{geometry.angle}'))
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
    return (matrices, passive, reciprocal)

def solve_resolved_clean_block(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], state_angles_degrees: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], center_volume_fraction: float=PRIMARY_CENTER_VOLUME_FRACTION, plenum_link_length_scale: float=1.0, frequency_start_index: int=0) -> ResolvedPlenumBlockResult:
    frequencies = np.asarray(frequencies_hz, dtype=float)
    states = validate_frozen_angles(partition, state_angles_degrees)
    if not np.allclose(frequencies, frozen_frequency_grid()[frequency_start_index:frequency_start_index + frequencies.size], rtol=1e-12, atol=0.0):
        raise ForwardCoreError('FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED')
    matrices, passive, reciprocal = assemble_resolved_system_matrices(member, nuisance, cell_index=cell_index, repeat_index=repeat_index, frequencies_hz=frequencies, partition=partition, repeat_seed_tuple=repeat_seed_tuple, center_volume_fraction=center_volume_fraction, plenum_link_length_scale=plenum_link_length_scale)
    sources = np.zeros((9, len(states) * 4), dtype=np.complex128)
    offset = _number(nuisance, 'angle_offset_degrees')
    for state_index, state in enumerate(states):
        weights = directional_port_weights(state, offset)
        for port in range(4):
            sources[port, state_index * 4 + port] = weights[port]
    solutions = np.linalg.solve(matrices, np.broadcast_to(sources, (frequencies.size, 9, len(states) * 4)))
    pressure = solutions[:, 8, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError('RESOLVED_PLENUM_NUMERIC_VALIDITY_FAIL')
    return ResolvedPlenumBlockResult(plenum_MODEL_NAME, pressure, passive, reciprocal, valid, CENTRAL_VOLUME_M3)


# Robust encoding geometry

FAMILY_ORDER = ('HAND_DESIGNED', 'NEAR_INDEPENDENT', 'FIXED_SEED_RANDOM_DISORDERED', 'PHYSICS_METAMATERIAL_INSPIRED')

FAMILY_CONTRAST_ORDER = tuple(((FAMILY_ORDER[left], FAMILY_ORDER[right]) for left in range(len(FAMILY_ORDER)) for right in range(left + 1, len(FAMILY_ORDER))))


# Topology preserving network

topology_MODEL_NAME = 'PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_TOPOLOGY_PRESERVING_M1_V1'

ANGLE_ORDER = (0, 90, 180, 270)

ALL_UNDIRECTED_EDGES = ((0, 90), (0, 180), (0, 270), (90, 180), (90, 270), (180, 270))

RING_EDGES = ((0, 90), (90, 180), (180, 270), (270, 0))

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
    family_id = member.get('family_id')
    if member.get('status') != 'STATIC_IDENTITY_ELIGIBLE' or family_id not in SUPPORTED_FAMILIES:
        raise ForwardCoreError('UNSUPPORTED_OR_INELIGIBLE_MEMBER')
    parameters = member.get('parameters')
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError('MISSING_PARAMETERS')
    return (str(family_id), parameters)

def topology_audit(member: Mapping[str, object]) -> TopologyAudit:
    """Map frozen identity coordinates to explicit undirected edge channels."""
    family_id, parameters = _validate_member(member)
    channels: list[EdgeChannel] = []
    possible = 0
    semantic: str
    if family_id == 'HAND_DESIGNED':
        central_mix = _number(parameters, 'central_mix')
        if not 0.1 <= central_mix <= 0.3:
            raise ForwardCoreError('HAND_CENTRAL_MIX_OUT_OF_RANGE')
        semantic = 'FROZEN_REPLICATED_CENTRAL_MIX_STAR_NO_LOCAL_LOCAL_EDGE'
    elif family_id == 'NEAR_INDEPENDENT':
        alpha = _number(parameters, 'shared_alpha')
        if not 0.03 <= alpha <= 0.07:
            raise ForwardCoreError('NEAR_SHARED_ALPHA_OUT_OF_RANGE')
        possible = len(ALL_UNDIRECTED_EDGES)
        per_edge_area = REFERENCE_LATERAL_AREA_M2 * alpha / possible
        channels = [EdgeChannel(left, right, alpha / 4.0, per_edge_area) for left, right in ALL_UNDIRECTED_EDGES]
        semantic = 'FROZEN_K0_ALPHA_WEAK_COMPLETE_GRAPH'
    elif family_id == 'FIXED_SEED_RANDOM_DISORDERED':
        possible = RANDOM_SLOT_COUNT
        for left, right in ALL_UNDIRECTED_EDGES:
            coordinate = _number(parameters, f'edge_{left}_{right}')
            if not 0.0 <= coordinate <= MAX_EDGE_COORDINATE:
                raise ForwardCoreError('RANDOM_EDGE_COORDINATE_OUT_OF_RANGE')
            if coordinate > 0.0:
                area = REFERENCE_LATERAL_AREA_M2 * coordinate / (possible * MAX_EDGE_COORDINATE)
                channels.append(EdgeChannel(left, right, coordinate, area))
        semantic = 'FIXED_SEED_SPARSE_UNDIRECTED_GRAPH_ZERO_EDGES_ABSENT'
    else:
        possible = PHYSICS_SLOT_COUNT
        for left, right in RING_EDGES:
            coordinate = _number(parameters, f'ring_{left}_{right}')
            if not 0.2 <= coordinate <= MAX_EDGE_COORDINATE:
                raise ForwardCoreError('PHYSICS_RING_COORDINATE_OUT_OF_RANGE')
            area = REFERENCE_LATERAL_AREA_M2 * coordinate / (possible * MAX_EDGE_COORDINATE)
            channels.append(EdgeChannel(left, right, coordinate, area))
        semantic = 'ORDERED_RECIPROCAL_CARDINAL_RING'
    total_area = float(sum((channel.area_m2 for channel in channels)))
    if total_area > REFERENCE_LATERAL_AREA_M2 * (1.0 + 1e-14):
        raise ForwardCoreError('LATERAL_CHANNEL_BUDGET_EXCEEDED')
    return TopologyAudit(family_id=family_id, semantic=semantic, possible_edge_count=possible, active_edges=tuple(channels), total_lateral_area_m2=total_area, lateral_area_budget_m2=REFERENCE_LATERAL_AREA_M2, budget_fraction=total_area / REFERENCE_LATERAL_AREA_M2)

def _radial_branch_parameters(family_id: str, parameters: Mapping[str, object], nuisance: Mapping[str, object], cell_index: int, repeat_index: int, repeat_seed: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return local-central branch M/R without averaging lateral edges."""
    if family_id == 'HAND_DESIGNED':
        central_mix = _number(parameters, 'central_mix')
        if not 0.1 <= central_mix <= 0.3:
            raise ForwardCoreError('HAND_CENTRAL_MIX_OUT_OF_RANGE')
        central_coordinates = np.full(4, central_mix, dtype=float)
    elif family_id == 'NEAR_INDEPENDENT':
        alpha = _number(parameters, 'shared_alpha')
        if not 0.03 <= alpha <= 0.07:
            raise ForwardCoreError('NEAR_SHARED_ALPHA_OUT_OF_RANGE')
        normalized = min(1.0, max(0.0, (alpha - 0.03) / 0.04))
        central_coordinates = np.full(4, normalized, dtype=float)
    else:
        central_coordinates = np.zeros(4, dtype=float)
    independent_percent = _number(nuisance, 'independent_manufacturing_percent')
    batch_percent = _number(nuisance, 'batch_correlated_manufacturing_percent')
    if not -2.0 <= independent_percent <= 2.0 or not -2.0 <= batch_percent <= 2.0:
        raise ForwardCoreError('MANUFACTURING_PERCENT_OUT_OF_RANGE')
    batch_factor = 1.0 + batch_percent / 100.0
    mix_areas = np.asarray([_aperture_area(value) for value in central_coordinates]) * batch_factor
    masses = np.empty(4, dtype=float)
    resistances = np.empty(4, dtype=float)
    for index, angle in enumerate(ANGLE_ORDER):
        signed_unit = 2.0 * _substream_uniform(repeat_seed, cell_index, repeat_index, index) - 1.0
        independent_factor = 1.0 + independent_percent * signed_unit / 100.0
        external_area = _aperture_area(_number(parameters, f'external_{angle}')) * batch_factor * independent_factor
        mix_area = mix_areas[index]
        equivalent_area = 2.0 / (1.0 / external_area + 1.0 / mix_area)
        loss = _number(parameters, f'loss_{angle}')
        if loss < 0.0:
            raise ForwardCoreError('NEGATIVE_LOSS')
        masses[index] = RHO_KG_M3 * BRANCH_LENGTH_M * (1.0 / external_area + 1.0 / mix_area)
        resistances[index] = loss * RHO_KG_M3 * SPEED_OF_SOUND_M_S / equivalent_area
    return (masses, resistances)

def lateral_edge_admittances(member: Mapping[str, object], nuisance: Mapping[str, object], frequencies_hz: Sequence[float]) -> tuple[TopologyAudit, NDArray[np.complex128]]:
    """Return per-frequency explicit edge admittances ``1/(R+j*w*M)``."""
    audit = topology_audit(member)
    _, parameters = _validate_member(member)
    frequencies = np.asarray(frequencies_hz, dtype=float)
    if frequencies.ndim != 1 or frequencies.size < 1 or (not np.all(np.isfinite(frequencies))) or np.any(frequencies <= 0):
        raise ForwardCoreError('POSITIVE_FINITE_FREQUENCIES_REQUIRED')
    batch_percent = _number(nuisance, 'batch_correlated_manufacturing_percent')
    if not -2.0 <= batch_percent <= 2.0:
        raise ForwardCoreError('MANUFACTURING_PERCENT_OUT_OF_RANGE')
    batch_factor = 1.0 + batch_percent / 100.0
    omega = 2.0 * math.pi * frequencies
    values = np.empty((frequencies.size, len(audit.active_edges)), dtype=np.complex128)
    for index, edge in enumerate(audit.active_edges):
        area = edge.area_m2 * batch_factor
        left_loss = _number(parameters, f'loss_{edge.left_angle}')
        right_loss = _number(parameters, f'loss_{edge.right_angle}')
        edge_loss = 0.5 * (left_loss + right_loss)
        if edge_loss < 0.0:
            raise ForwardCoreError('NEGATIVE_EDGE_LOSS')
        mass = RHO_KG_M3 * BRANCH_LENGTH_M / area
        resistance = edge_loss * RHO_KG_M3 * SPEED_OF_SOUND_M_S / area
        values[:, index] = 1.0 / (resistance + 1j * omega * mass)
    if not np.all(np.isfinite(values)) or np.any(values.real < -1e-15):
        raise ForwardCoreError('INVALID_LATERAL_EDGE_ADMITTANCE')
    return (audit, values)

def topology_assemble_system_matrices(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int]) -> tuple[NDArray[np.complex128], TopologyAudit, bool, bool]:
    """Assemble the five-node system, including the explicit edge Laplacian."""
    family_id, parameters = _validate_member(member)
    try:
        repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    except E2AuthorityError as exc:
        raise ForwardCoreError(str(exc)) from exc
    frequencies = np.asarray(frequencies_hz, dtype=float)
    shift = _number(nuisance, 'common_frequency_axis_shift_relative')
    if not -0.005 <= shift <= 0.005:
        raise ForwardCoreError('FREQUENCY_SHIFT_OUT_OF_RANGE')
    shifted = frequencies * (1.0 + shift)
    volumes = _volume_partition(parameters)
    compliances = volumes / (RHO_KG_M3 * SPEED_OF_SOUND_M_S ** 2)
    masses, resistances = _radial_branch_parameters(family_id, parameters, nuisance, cell_index, repeat_index, repeat_seeds[repeat_index])
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
    passive = bool(np.all(compliances > 0.0) and np.all(resistances >= 0.0) and np.all(edge_admittance.real >= -1e-15))
    return (matrices, audit, passive, reciprocal)

def solve_forward_block(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], state_angles_degrees: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], frequency_start_index: int=0, include_additive_sensor_noise: bool=True) -> ForwardBlockResult:
    """Solve the M1 five-node network for one nuisance cell/repeat block."""
    if not isinstance(cell_index, int) or cell_index < 0 or (not isinstance(repeat_index, int)) or (repeat_index not in (0, 1)):
        raise ForwardCoreError('INVALID_CELL_OR_REPEAT')
    frequencies = np.asarray(frequencies_hz, dtype=float)
    try:
        states = validate_frozen_angles(partition, state_angles_degrees)
        repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    except E2AuthorityError as exc:
        raise ForwardCoreError(str(exc)) from exc
    if not isinstance(frequency_start_index, int) or frequency_start_index < 0 or frequencies.ndim != 1 or (frequencies.size < 1) or (frequency_start_index + frequencies.size > 256) or (not np.allclose(frequencies, frozen_frequency_grid()[frequency_start_index:frequency_start_index + frequencies.size], rtol=1e-12, atol=0.0)):
        raise ForwardCoreError('FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED')
    snr_db = _number(nuisance, 'snr_db')
    angle_offset = _number(nuisance, 'angle_offset_degrees')
    if snr_db not in (20.0, 30.0, 40.0):
        raise ForwardCoreError('SNR_LEVEL_NOT_FROZEN')
    if angle_offset not in (-5.0, -3.0, -1.0, 0.0, 1.0, 3.0, 5.0):
        raise ForwardCoreError('ANGLE_OFFSET_LEVEL_NOT_FROZEN')
    matrices, _, passive, reciprocal = topology_assemble_system_matrices(member, nuisance, cell_index=cell_index, repeat_index=repeat_index, frequencies_hz=frequencies, partition=partition, repeat_seed_tuple=repeat_seed_tuple)
    sources = np.zeros((5, len(states) * 4), dtype=np.complex128)
    for state_index, state_angle in enumerate(states):
        weights = directional_port_weights(state_angle, angle_offset)
        for port_index in range(4):
            sources[port_index, state_index * 4 + port_index] = weights[port_index]
    try:
        rhs = np.broadcast_to(sources, (frequencies.size, 5, len(states) * 4))
        solutions = np.linalg.solve(matrices, rhs)
    except np.linalg.LinAlgError as exc:
        raise ForwardCoreError('NETWORK_NOT_SOLVABLE') from exc
    pressure = solutions[:, 4, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    common_gain = 10.0 ** (_number(nuisance, 'common_gain_db') / 20.0)
    sensor_gain = 10.0 ** (_number(nuisance, 'sensor_independent_gain_db') / 20.0)
    pressure *= common_gain * sensor_gain
    if include_additive_sensor_noise:
        global_frequency_indices = np.arange(frequency_start_index, frequency_start_index + frequencies.size, dtype=np.uint64)
        global_angle_indices = np.asarray([angle_global_ordinal(partition, value) for value in states], dtype=np.uint64)
        flat = (global_angle_indices[:, None, None] * np.uint64(4) + np.arange(4, dtype=np.uint64)[None, :, None]) * np.uint64(256) + global_frequency_indices[None, None, :]
        uniforms = _substream_uniform_array(repeat_seeds[repeat_index], cell_index, repeat_index, np.uint64(8) + flat)
        phases = 2.0 * math.pi * uniforms
        pressure += 10.0 ** (-snr_db / 20.0) * (np.cos(phases) + 1j * np.sin(phases))
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError('NETWORK_NUMERIC_VALIDITY_FAIL')
    return ForwardBlockResult(topology_MODEL_NAME, pressure, passive, reciprocal, True, valid)


# Gen enc 4 topology preserving m0 m1

MODEL_EFFECT_BOOTSTRAP_SEED = 2026090401

BOOTSTRAP_REPLICATES = 20000

def metric_signature(summary: dict[str, Any]) -> np.ndarray:
    metric = summary['metrics']
    pair = np.asarray(metric['pair_lower_tail_es_0p05'], dtype=float)
    pair /= float(np.mean(pair))
    return np.concatenate((pair, np.asarray([metric['pair_anisotropy_mean'], metric['pair_anisotropy_upper_tail_es_0p05'], metric['gram_frobenius_drift_mean'], metric['gram_frobenius_drift_upper_tail_es_0p05']], dtype=float)))

def geometry_separation(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = np.stack([metric_signature(summary) for summary in summaries])
    scale = np.std(matrix, axis=0, ddof=1)
    usable = scale > np.finfo(float).eps
    standardized = (matrix[:, usable] - np.mean(matrix[:, usable], axis=0)) / scale[usable]
    centroids = np.stack([np.mean(standardized[index * 20:(index + 1) * 20], axis=0) for index in range(4)])
    within = np.asarray([math.sqrt(float(np.mean(np.sum((standardized[index * 20:(index + 1) * 20] - centroids[index]) ** 2, axis=1)))) for index in range(4)])
    pairs = []
    ratios = []
    for pair_index, (left, right) in enumerate(((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))):
        between = float(np.linalg.norm(centroids[left] - centroids[right]))
        pooled = math.sqrt(0.5 * (within[left] ** 2 + within[right] ** 2))
        ratio = between / pooled
        ratios.append(ratio)
        pairs.append({'families': list(FAMILY_CONTRAST_ORDER[pair_index]), 'between_centroid': between, 'pooled_within_rms': pooled, 'ratio': ratio})
    return {'signature': 'SIX_SCALE_NORMALIZED_PAIR_LTES_PLUS_ANISOTROPY_AND_GRAM_DRIFT', 'standardization': 'GLOBAL_EXACT80_DDOF1_PER_FEATURE', 'usable_dimensions': int(np.count_nonzero(usable)), 'family_within_rms': within, 'pairwise': pairs, 'minimum_between_within_ratio': float(np.min(ratios)), 'mean_between_within_ratio': float(np.mean(ratios))}

def paired_effect(m0: np.ndarray, m1: np.ndarray, *, favorable: str) -> dict[str, Any]:
    difference = m1 - m0 if favorable == 'increase' else m0 - m1
    rng = np.random.Generator(np.random.PCG64(MODEL_EFFECT_BOOTSTRAP_SEED))
    indices = rng.integers(0, difference.size, size=(BOOTSTRAP_REPLICATES, difference.size), endpoint=False)
    boot = np.mean(difference[indices], axis=1)
    return {'favorable_direction': 'M1_MINUS_M0' if favorable == 'increase' else 'M0_MINUS_M1', 'mean_favorable_effect': float(np.mean(difference)), 'median_favorable_effect': float(np.median(difference)), 'percentile_95_ci': np.quantile(boot, (0.025, 0.975), method='linear'), 'bootstrap_replicates': BOOTSTRAP_REPLICATES, 'bootstrap_seed': MODEL_EFFECT_BOOTSTRAP_SEED, 'identity_paired': True}


# Gen enc 5 obsa readout bottleneck diagnostic

readout_PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))

def state_signature(response: np.ndarray, *, center: bool) -> np.ndarray:
    x = np.asarray(response, dtype=np.complex128).reshape(4, -1)
    contrast_fraction = float(np.linalg.norm(x - np.mean(x, axis=0, keepdims=True)) / np.linalg.norm(x))
    if center:
        x = x - np.mean(x, axis=0, keepdims=True)
    norm = float(np.linalg.norm(x))
    if norm <= 0 or not math.isfinite(norm):
        raise RuntimeError('ZERO_OR_NONFINITE_LAYER_RESPONSE')
    x = x / norm
    gram = x @ x.conj().T
    gram = 0.5 * (gram + gram.conj().T)
    distances = np.asarray([np.linalg.norm(x[left] - x[right]) for left, right in readout_PAIRS], dtype=float)
    singular = np.linalg.svd(np.concatenate((x.real, x.imag), axis=1), compute_uv=False)
    singular = singular / singular.sum()
    return np.concatenate((gram.real.reshape(-1), gram.imag.reshape(-1), distances, singular, np.asarray([contrast_fraction])))

def readout_separation(matrix: np.ndarray) -> dict[str, Any]:
    scale = np.std(matrix, axis=0, ddof=1)
    usable = scale > np.finfo(float).eps
    z = (matrix[:, usable] - np.mean(matrix[:, usable], axis=0)) / scale[usable]
    centroids = np.stack([np.mean(z[i * 20:(i + 1) * 20], axis=0) for i in range(4)])
    within = np.asarray([math.sqrt(float(np.mean(np.sum((z[i * 20:(i + 1) * 20] - centroids[i]) ** 2, axis=1)))) for i in range(4)])
    rows = []
    for left, right in readout_PAIRS:
        pooled = math.sqrt(0.5 * (within[left] ** 2 + within[right] ** 2))
        rows.append({'families': [FAMILY_ORDER[left], FAMILY_ORDER[right]], 'ratio': float(np.linalg.norm(centroids[left] - centroids[right]) / pooled)})
    ratios = [x['ratio'] for x in rows]
    return {'usable_dimensions': int(np.sum(usable)), 'minimum_between_within_ratio': min(ratios), 'mean_between_within_ratio': float(np.mean(ratios)), 'pairwise': rows}


# Gen enc 6 obsb geometry overlap diagnostic

FAMILIES = tuple(FAMILY_ORDER)

physical_geometry_PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))

def physical_geometry_signature(member: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Return common independent and derived realized descriptors used by M2-B.

    The 16-dimensional primary signature contains four sector values for target
    volume, outer aperture area, central-window union area, and loss. Root length
    is derived deterministically from the first three groups and is sensitivity-only.
    """
    geometries = compile_member_geometry(member, spine_only=False)
    parameters = member['parameters']
    targets = np.asarray([geometry.target_volume_m3 for geometry in geometries], dtype=float)
    outer = np.asarray([geometry.outer_area_m2 for geometry in geometries], dtype=float)
    windows = np.asarray([geometry.window_union_area_m2 for geometry in geometries], dtype=float)
    losses = np.asarray([float(parameters[f'loss_{geometry.angle}']) for geometry in geometries], dtype=float)
    roots = np.asarray([geometry.root_length_m for geometry in geometries], dtype=float)
    primary = np.concatenate((np.log(targets), np.log(outer), np.log(windows), losses))
    realized_with_root = np.concatenate((primary, roots))
    if primary.shape != (16,) or realized_with_root.shape != (20,):
        raise RuntimeError('GEOMETRY_SIGNATURE_SHAPE_FAIL')
    if not np.all(np.isfinite(primary)) or not np.all(np.isfinite(realized_with_root)):
        raise RuntimeError('GEOMETRY_SIGNATURE_FINITE_FAIL')
    return (primary, realized_with_root)

def physical_geometry_separation(matrix: np.ndarray) -> dict[str, Any]:
    scale = np.std(matrix, axis=0, ddof=1)
    usable = scale > np.finfo(float).eps
    if not np.any(usable):
        raise RuntimeError('NO_USABLE_DIMENSIONS')
    z = (matrix[:, usable] - np.mean(matrix[:, usable], axis=0)) / scale[usable]
    centroids = np.stack([np.mean(z[index * 20:(index + 1) * 20], axis=0) for index in range(4)])
    within = np.asarray([math.sqrt(float(np.mean(np.sum((z[index * 20:(index + 1) * 20] - centroids[index]) ** 2, axis=1)))) for index in range(4)])
    rows = []
    for left, right in physical_geometry_PAIRS:
        pooled = math.sqrt(0.5 * (within[left] ** 2 + within[right] ** 2))
        rows.append({'families': [FAMILIES[left], FAMILIES[right]], 'ratio': float(np.linalg.norm(centroids[left] - centroids[right]) / pooled)})
    ratios = np.asarray([row['ratio'] for row in rows], dtype=float)
    return {'usable_dimensions': int(np.sum(usable)), 'minimum_between_within_ratio': float(np.min(ratios)), 'mean_between_within_ratio': float(np.mean(ratios)), 'pairwise': rows}


# Gen enc 7 model bridge diagnostic

bridge_PAIRS = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))

def response_discrepancy(reference: np.ndarray, alternative: np.ndarray) -> tuple[float, float]:
    ref = np.asarray(reference, dtype=np.complex128).reshape(4, -1).copy()
    alt = np.asarray(alternative, dtype=np.complex128).reshape(4, -1).copy()
    relative = float(np.linalg.norm(alt - ref) / np.linalg.norm(ref))
    ref /= np.linalg.norm(ref)
    alt /= np.linalg.norm(alt)
    ref_gram = ref @ ref.conj().T
    alt_gram = alt @ alt.conj().T
    gram_shift = float(np.linalg.norm(alt_gram - ref_gram, ord='fro'))
    return (relative, gram_shift)

def representative_distances(signatures: np.ndarray, names: list[str]) -> dict[str, Any]:
    rows = []
    for left, right in bridge_PAIRS:
        rows.append({'representatives': [names[left], names[right]], 'distance': float(np.linalg.norm(signatures[left] - signatures[right]))})
    values = np.asarray([row['distance'] for row in rows])
    return {'minimum': float(np.min(values)), 'mean': float(np.mean(values)), 'pairwise': rows}


def paper_example():
    """Recompute family-overlap ratios from archived identity-level numerical data.

    Model inputs for the topology/fluid/plenum solvers are shared with experiment
    05. Signature rows follow signature_labels.json, grouped in the frozen family
    order. Archived validation endpoints are consumed without rerunning selection.
    """
    peer = DATA_DIR.parent / '05_five_node_family_comparison'
    ratios = {}
    for label, folder in (('five_node', peer), ('topology', DATA_DIR)):
        archived = json.loads((folder / 'archived_geometry_metrics.json').read_text(encoding='utf-8'))
        rows = [r for r in archived if r['partition'] == 'single_use_validation']
        rows.sort(key=lambda r: (FAMILY_ORDER.index(r['family_id']), r['identity_id']))
        ratios[label] = geometry_separation(rows)['minimum_between_within_ratio']
    geometry = np.load(DATA_DIR / 'primary_geometry_signatures.npy', allow_pickle=False)
    local = np.load(DATA_DIR / 'local_full_clean_identity_signatures.npy', allow_pickle=False)
    central = np.load(DATA_DIR / 'central_raw_clean_identity_signatures.npy', allow_pickle=False)
    discrepancy = np.load(DATA_DIR / 'resolved_center_fraction_0p25_unit_discrepancy.npy', allow_pickle=False)
    return {'family_geometry_ratios': ratios,
            'effective_geometry_minimum_ratio': physical_geometry_separation(geometry)['minimum_between_within_ratio'],
            'local_acoustics_minimum_ratio': readout_separation(local)['minimum_between_within_ratio'],
            'central_readout_minimum_ratio': readout_separation(central)['minimum_between_within_ratio'],
            'plenum_unit_discrepancy_shape': list(discrepancy.shape)}

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))


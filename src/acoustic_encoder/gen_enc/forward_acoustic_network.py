"""Frozen reduced GEN-ENC forward acoustic-network compute core.

The core returns central complex pressure in memory for later E2 callers.  The
timing harness is responsible for discarding those values and exposing only
resource and numerical-validity aggregates.
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
from .generator.prng import GOLDEN_GAMMA, MASK64, open_interval_uniform53, splitmix64


MODEL_NAME = "PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1"
RHO_KG_M3 = 1.2041
SPEED_OF_SOUND_M_S = 343.0
TOTAL_VOLUME_M3 = 3.014899604922098e-5
BRANCH_HEIGHT_M = 0.0092
BRANCH_LENGTH_M = 0.002
STATE_ANGLES_DEGREES = (0.0, 90.0, 180.0, 270.0)
SUPPORTED_FAMILIES = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)
THROUGH_REFERENCE_ID = "THROUGH_REFERENCE_U4_IDENTITY_V1"


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
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ForwardCoreError(f"INVALID_{name.upper()}")
    return float(value)


def _aperture_area(coordinate: float) -> float:
    if not 0.0 <= coordinate <= 1.0:
        raise ForwardCoreError("APERTURE_COORDINATE_OUT_OF_RANGE")
    return BRANCH_HEIGHT_M * (0.002 + 0.006 * coordinate)


def _volume_partition(parameters: Mapping[str, object]) -> NDArray[np.float64]:
    q = np.array([_number(parameters, f"q{angle}") for angle in (0, 90, 180, 270)], dtype=float)
    if np.any(q < -0.12) or np.any(q > 0.12):
        raise ForwardCoreError("VOLUME_LOGIT_OUT_OF_RANGE")
    weights = np.exp(q)
    local = 0.60 * TOTAL_VOLUME_M3 * weights / weights.sum()
    return np.concatenate((local, np.array([0.40 * TOTAL_VOLUME_M3])))


def _substream_uniform(base_seed: int, cell_index: int, repeat_index: int, substream: int) -> float:
    x = (base_seed + GOLDEN_GAMMA * (1 + 64 * cell_index + 32 * repeat_index + substream)) & MASK64
    return open_interval_uniform53(splitmix64(x))


def _branch_parameters(
    family_id: str,
    parameters: Mapping[str, object],
    nuisance: Mapping[str, object],
    cell_index: int,
    repeat_index: int,
    repeat_seed: int,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    angles = (0, 90, 180, 270)
    if family_id == "HAND_DESIGNED":
        central_mix = _number(parameters, "central_mix")
        if not 0.1 <= central_mix <= 0.3:
            raise ForwardCoreError("HAND_CENTRAL_MIX_OUT_OF_RANGE")
        shared_coordinates = np.full(4, central_mix, dtype=float)
    elif family_id == "NEAR_INDEPENDENT":
        alpha = _number(parameters, "shared_alpha")
        if not 0.03 <= alpha <= 0.07:
            raise ForwardCoreError("NEAR_SHARED_ALPHA_OUT_OF_RANGE")
        normalized_coordinate = (alpha - 0.03) / 0.04
        normalized_coordinate = min(1.0, max(0.0, normalized_coordinate))
        shared_coordinates = np.full(4, normalized_coordinate, dtype=float)
    elif family_id == "FIXED_SEED_RANDOM_DISORDERED":
        edge_coordinates: dict[tuple[int, int], float] = {}
        for left, right in ((0, 90), (0, 180), (0, 270), (90, 180), (90, 270), (180, 270)):
            value = _number(parameters, f"edge_{left}_{right}")
            if not 0.0 <= value <= 0.8:
                raise ForwardCoreError("RANDOM_EDGE_COORDINATE_OUT_OF_RANGE")
            edge_coordinates[(left, right)] = value
        shared_coordinates = np.array(
            [
                sum(value for edge, value in edge_coordinates.items() if angle in edge) / 3.0
                for angle in angles
            ],
            dtype=float,
        )
    elif family_id == "PHYSICS_METAMATERIAL_INSPIRED":
        ring_coordinates: dict[tuple[int, int], float] = {}
        for left, right in ((0, 90), (90, 180), (180, 270), (270, 0)):
            value = _number(parameters, f"ring_{left}_{right}")
            if not 0.2 <= value <= 0.8:
                raise ForwardCoreError("PHYSICS_RING_COORDINATE_OUT_OF_RANGE")
            ring_coordinates[(left, right)] = value
        shared_coordinates = np.array(
            [
                sum(value for edge, value in ring_coordinates.items() if angle in edge) / 2.0
                for angle in angles
            ],
            dtype=float,
        )
    elif family_id == THROUGH_REFERENCE_ID:
        central_mix = _number(parameters, "central_mix")
        if central_mix != 0.5:
            raise ForwardCoreError("THROUGH_REFERENCE_CENTRAL_MIX_MISMATCH")
        shared_coordinates = np.full(4, 0.5, dtype=float)
    else:
        raise ForwardCoreError(f"FAMILY_GRAPH_MAPPING_UNAVAILABLE:{family_id}")
    independent_percent = _number(nuisance, "independent_manufacturing_percent")
    batch_percent = _number(nuisance, "batch_correlated_manufacturing_percent")
    if not -2.0 <= independent_percent <= 2.0 or not -2.0 <= batch_percent <= 2.0:
        raise ForwardCoreError("MANUFACTURING_PERCENT_OUT_OF_RANGE")
    batch_factor = 1.0 + batch_percent / 100.0
    mix_areas = np.array([_aperture_area(value) for value in shared_coordinates]) * batch_factor
    masses = np.empty(4, dtype=float)
    resistances = np.empty(4, dtype=float)
    for index, angle in enumerate(angles):
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


def solve_forward_block_reference(
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
    """Scalar reference solve for frozen angles and four weighted input ports."""

    family_id = member.get("family_id")
    ordinary_member = member.get("status") == "STATIC_IDENTITY_ELIGIBLE" and family_id in SUPPORTED_FAMILIES
    through_reference = member.get("status") == "THROUGH_REFERENCE_STATIC_IDENTITY" and family_id == THROUGH_REFERENCE_ID
    if not ordinary_member and not through_reference:
        raise ForwardCoreError("UNSUPPORTED_OR_INELIGIBLE_MEMBER")
    if not isinstance(cell_index, int) or cell_index < 0 or not isinstance(repeat_index, int) or repeat_index not in (0, 1):
        raise ForwardCoreError("INVALID_CELL_OR_REPEAT")
    parameters = member.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError("MISSING_PARAMETERS")
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
    shift = _number(nuisance, "common_frequency_axis_shift_relative")
    common_gain = 10.0 ** (_number(nuisance, "common_gain_db") / 20.0)
    sensor_gain = 10.0 ** (_number(nuisance, "sensor_independent_gain_db") / 20.0)
    snr_db = _number(nuisance, "snr_db")
    angle_offset = _number(nuisance, "angle_offset_degrees")
    if snr_db not in (20.0, 30.0, 40.0):
        raise ForwardCoreError("SNR_LEVEL_NOT_FROZEN")
    if angle_offset not in (-5.0, -3.0, -1.0, 0.0, 1.0, 3.0, 5.0):
        raise ForwardCoreError("ANGLE_OFFSET_LEVEL_NOT_FROZEN")
    if not -0.005 <= shift <= 0.005:
        raise ForwardCoreError("FREQUENCY_SHIFT_OUT_OF_RANGE")

    volumes = _volume_partition(parameters)
    compliances = volumes / (RHO_KG_M3 * SPEED_OF_SOUND_M_S**2)
    masses, resistances = _branch_parameters(
        str(family_id), parameters, nuisance, cell_index, repeat_index, repeat_seeds[repeat_index]
    )
    pressure = np.empty((len(states), 4, frequencies.size), dtype=np.complex128)
    reciprocal = True
    passive = bool(np.all(resistances >= 0.0) and np.all(compliances > 0.0))
    try:
        for state_index, state_angle in enumerate(states):
            weights = directional_port_weights(state_angle, angle_offset)
            for frequency_index, frequency in enumerate(frequencies * (1.0 + shift)):
                omega = 2.0 * math.pi * frequency
                impedance = resistances + 1j * omega * masses
                branch_admittance = 1.0 / impedance
                matrix = np.diag(1j * omega * compliances).astype(np.complex128)
                for local in range(4):
                    admittance = branch_admittance[local]
                    matrix[local, local] += admittance
                    matrix[4, 4] += admittance
                    matrix[local, 4] -= admittance
                    matrix[4, local] -= admittance
                reciprocal = reciprocal and bool(np.allclose(matrix, matrix.T, rtol=0.0, atol=1e-12))
                for port_index in range(4):
                    source = np.zeros(5, dtype=np.complex128)
                    source[port_index] = weights[port_index]
                    pressure[state_index, port_index, frequency_index] = np.linalg.solve(matrix, source)[4]
    except np.linalg.LinAlgError as exc:
        raise ForwardCoreError("NETWORK_NOT_SOLVABLE") from exc
    pressure *= common_gain * sensor_gain
    if include_additive_sensor_noise:
        noise_amplitude_pa = 10.0 ** (-snr_db / 20.0)
        seed = repeat_seeds[repeat_index]
        for state_index, state_angle in enumerate(states):
            global_angle_index = angle_global_ordinal(partition, state_angle)
            for port_index in range(4):
                for local_frequency_index in range(frequencies.size):
                    global_frequency_index = frequency_start_index + local_frequency_index
                    global_flat_index = (global_angle_index * 4 + port_index) * 256 + global_frequency_index
                    phase = 2.0 * math.pi * _substream_uniform(
                        seed, cell_index, repeat_index, 8 + global_flat_index
                    )
                    pressure[state_index, port_index, local_frequency_index] += noise_amplitude_pa * complex(
                        math.cos(phase), math.sin(phase)
                    )
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError("NETWORK_NUMERIC_VALIDITY_FAIL")
    return ForwardBlockResult(MODEL_NAME, pressure, passive, reciprocal, True, valid)


def _substream_uniform_array(
    base_seed: int,
    cell_index: int,
    repeat_index: int,
    substreams: NDArray[np.uint64],
) -> NDArray[np.float64]:
    """Vectorized exact SplitMix64/open-interval transform used by the scalar reference."""

    with np.errstate(over="ignore"):
        x = (
            np.uint64(base_seed)
            + np.uint64(GOLDEN_GAMMA)
            * (np.uint64(1 + 64 * cell_index + 32 * repeat_index) + substreams)
        )
        z = x + np.uint64(GOLDEN_GAMMA)
        z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        z = z ^ (z >> np.uint64(31))
    return ((z >> np.uint64(11)).astype(np.float64) + 0.5) / float(1 << 53)


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
    """Batched, semantically equivalent solve for one frozen workload block."""

    family_id = member.get("family_id")
    ordinary_member = member.get("status") == "STATIC_IDENTITY_ELIGIBLE" and family_id in SUPPORTED_FAMILIES
    through_reference = member.get("status") == "THROUGH_REFERENCE_STATIC_IDENTITY" and family_id == THROUGH_REFERENCE_ID
    if not ordinary_member and not through_reference:
        raise ForwardCoreError("UNSUPPORTED_OR_INELIGIBLE_MEMBER")
    if not isinstance(cell_index, int) or cell_index < 0 or not isinstance(repeat_index, int) or repeat_index not in (0, 1):
        raise ForwardCoreError("INVALID_CELL_OR_REPEAT")
    parameters = member.get("parameters")
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError("MISSING_PARAMETERS")
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
    shift = _number(nuisance, "common_frequency_axis_shift_relative")
    common_gain = 10.0 ** (_number(nuisance, "common_gain_db") / 20.0)
    sensor_gain = 10.0 ** (_number(nuisance, "sensor_independent_gain_db") / 20.0)
    snr_db = _number(nuisance, "snr_db")
    angle_offset = _number(nuisance, "angle_offset_degrees")
    if snr_db not in (20.0, 30.0, 40.0):
        raise ForwardCoreError("SNR_LEVEL_NOT_FROZEN")
    if angle_offset not in (-5.0, -3.0, -1.0, 0.0, 1.0, 3.0, 5.0):
        raise ForwardCoreError("ANGLE_OFFSET_LEVEL_NOT_FROZEN")
    if not -0.005 <= shift <= 0.005:
        raise ForwardCoreError("FREQUENCY_SHIFT_OUT_OF_RANGE")

    volumes = _volume_partition(parameters)
    compliances = volumes / (RHO_KG_M3 * SPEED_OF_SOUND_M_S**2)
    masses, resistances = _branch_parameters(
        str(family_id), parameters, nuisance, cell_index, repeat_index, repeat_seeds[repeat_index]
    )
    passive = bool(np.all(resistances >= 0.0) and np.all(compliances > 0.0))
    omega = 2.0 * math.pi * frequencies * (1.0 + shift)
    impedance = resistances[None, :] + 1j * omega[:, None] * masses[None, :]
    branch_admittance = 1.0 / impedance
    matrices = np.zeros((frequencies.size, 5, 5), dtype=np.complex128)
    diagonal = np.arange(5)
    matrices[:, diagonal, diagonal] = 1j * omega[:, None] * compliances[None, :]
    local = np.arange(4)
    matrices[:, local, local] += branch_admittance
    matrices[:, 4, 4] += branch_admittance.sum(axis=1)
    matrices[:, local, 4] -= branch_admittance
    matrices[:, 4, local] -= branch_admittance
    reciprocal = bool(np.allclose(matrices, matrices.transpose(0, 2, 1), rtol=0.0, atol=1e-12))

    sources = np.zeros((5, len(states) * 4), dtype=np.complex128)
    for state_index, state_angle in enumerate(states):
        weights = directional_port_weights(state_angle, angle_offset)
        for port_index in range(4):
            column = state_index * 4 + port_index
            sources[port_index, column] = weights[port_index]
    try:
        rhs = np.broadcast_to(sources, (frequencies.size, 5, len(states) * 4))
        solutions = np.linalg.solve(matrices, rhs)
    except np.linalg.LinAlgError as exc:
        raise ForwardCoreError("NETWORK_NOT_SOLVABLE") from exc
    pressure = solutions[:, 4, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    pressure *= common_gain * sensor_gain

    global_frequency_indices = np.arange(
        frequency_start_index,
        frequency_start_index + frequencies.size,
        dtype=np.uint64,
    )
    global_angle_indices = np.asarray(
        [angle_global_ordinal(partition, value) for value in states], dtype=np.uint64
    )
    flat = (
        (global_angle_indices[:, None, None] * np.uint64(4)
         + np.arange(4, dtype=np.uint64)[None, :, None])
        * np.uint64(256)
        + global_frequency_indices[None, None, :]
    )
    if include_additive_sensor_noise:
        uniforms = _substream_uniform_array(
            repeat_seeds[repeat_index], cell_index, repeat_index, np.uint64(8) + flat
        )
        phases = 2.0 * math.pi * uniforms
        pressure += 10.0 ** (-snr_db / 20.0) * (np.cos(phases) + 1j * np.sin(phases))
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError("NETWORK_NUMERIC_VALIDITY_FAIL")
    return ForwardBlockResult(MODEL_NAME, pressure, passive, reciprocal, True, valid)

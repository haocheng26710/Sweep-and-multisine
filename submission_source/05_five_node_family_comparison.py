"""Five node family comparison.
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
from numpy.typing import ArrayLike
from numpy.typing import NDArray
from typing import Mapping
from typing import Sequence
import math
import numpy as np

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "05_five_node_family_comparison"


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


# Estimator

@dataclass(frozen=True)
class WhitenerResult:
    status: str
    reason: str | None
    operator: NDArray[np.float64] | None
    empirical_covariance: NDArray[np.float64] | None
    covariance: NDArray[np.float64] | None
    shrinkage: float | None
    eigenvalue_floor: float | None
    effective_sample_size: float | None
    source_partitions: tuple[str, ...] = ('train', 'development')

@dataclass(frozen=True)
class CandidateResult:
    level: str
    technical_status: str
    scientific_status: str
    reason: str | None
    primary_endpoint: float | None
    stable_rank: int | None
    singular_value_quantiles: tuple[float, ...]
    evaluation_unit_count: int
    nuisance_cell_count: int
    small_sample_disclosure: str | None
    threshold: float = 1.0

def trapezoidal_weights(frequency: ArrayLike) -> NDArray[np.float64]:
    """Normalized composite-trapezoidal weights on a shared strict grid."""
    grid = np.asarray(frequency, dtype=float)
    if grid.ndim != 1 or grid.size < 2 or (not np.all(np.isfinite(grid))):
        raise ValueError('frequency grid must contain at least two finite points')
    delta = np.diff(grid)
    if np.any(delta <= 0):
        raise ValueError('frequency grid must be strictly increasing')
    weights = np.empty_like(grid)
    weights[0] = delta[0] / 2.0
    weights[-1] = delta[-1] / 2.0
    if grid.size > 2:
        weights[1:-1] = (delta[:-1] + delta[1:]) / 2.0
    return weights / weights.sum()

def projection_matrices(state_count: int=4) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if state_count < 1:
        raise ValueError('state_count must be positive')
    shared = np.ones((state_count, state_count), dtype=float) / state_count
    return (shared, np.eye(state_count, dtype=float) - shared)

def _cell_residual_rows(repeats: ArrayLike) -> NDArray[np.float64]:
    values = np.asarray(repeats, dtype=float)
    if values.ndim != 3 or values.shape[0] < 2 or values.shape[2] != 4:
        raise ValueError('each cell must be repeats-by-features-by-four-states with at least two repeats')
    if not np.all(np.isfinite(values)):
        raise ValueError('residual input contains nonfinite values')
    differential = projection_matrices(4)[1]
    projected = values @ differential
    residual = projected - projected.mean(axis=0, keepdims=True)
    return residual.transpose(0, 2, 1).reshape((-1, values.shape[1]))

def _oas(empirical: NDArray[np.float64], effective_n: float) -> tuple[NDArray[np.float64], float]:
    dimension = empirical.shape[0]
    trace = float(np.trace(empirical))
    tau = trace / dimension
    alpha = float(np.mean(empirical ** 2))
    denominator = (effective_n + 1.0) * (alpha - tau ** 2 / dimension)
    if denominator <= 0.0:
        shrinkage = 1.0
    else:
        shrinkage = min((alpha + tau ** 2) / denominator, 1.0)
    shrunk = (1.0 - shrinkage) * empirical + shrinkage * tau * np.eye(dimension)
    return (shrunk, float(shrinkage))

def fit_whitener(train_cells: Mapping[str, ArrayLike], development_cells: Mapping[str, ArrayLike], required_cells: Sequence[str]) -> WhitenerResult:
    """Fit the common whitener from train/development cells only.

    Each required nuisance cell receives equal total covariance weight; rows
    within a cell receive equal weight.  There is intentionally no validation
    argument.
    """
    required = tuple(required_cells)
    if not required or len(set(required)) != len(required):
        return WhitenerResult('UNAVAILABLE', 'INVALID_REQUIRED_CELL_IDENTITY', None, None, None, None, None, None)
    rows_by_cell: list[NDArray[np.float64]] = []
    try:
        for cell in required:
            pieces = []
            for source in (train_cells, development_cells):
                if cell not in source:
                    raise KeyError(cell)
                pieces.append(_cell_residual_rows(source[cell]))
            combined = np.concatenate(pieces, axis=0)
            rows_by_cell.append(combined)
    except (KeyError, ValueError, np.linalg.LinAlgError) as exc:
        return WhitenerResult('UNAVAILABLE', f'RESIDUAL_INPUT:{exc}', None, None, None, None, None, None)
    dimensions = {rows.shape[1] for rows in rows_by_cell}
    if len(dimensions) != 1:
        return WhitenerResult('UNAVAILABLE', 'FEATURE_IDENTITY_MISMATCH', None, None, None, None, None, None)
    cell_count = len(rows_by_cell)
    covariance = np.zeros((next(iter(dimensions)), next(iter(dimensions))), dtype=float)
    squared_weight_sum = 0.0
    for rows in rows_by_cell:
        row_weight = 1.0 / (cell_count * rows.shape[0])
        covariance += rows.T @ rows / (cell_count * rows.shape[0])
        squared_weight_sum += rows.shape[0] * row_weight ** 2
    effective_n = 1.0 / squared_weight_sum
    if not np.all(np.isfinite(covariance)) or effective_n < 2.0:
        return WhitenerResult('UNAVAILABLE', 'COVARIANCE_UNAVAILABLE', None, covariance, None, None, None, effective_n)
    shrunk, shrinkage = _oas(covariance, effective_n)
    try:
        eigenvalues, eigenvectors = np.linalg.eigh(shrunk)
    except np.linalg.LinAlgError as exc:
        return WhitenerResult('UNAVAILABLE', f'EIGENDECOMPOSITION:{exc}', None, covariance, shrunk, None, None, effective_n)
    lambda_max = float(eigenvalues[-1])
    if not np.isfinite(lambda_max) or lambda_max <= 0.0:
        return WhitenerResult('UNAVAILABLE', 'NONPOSITIVE_COVARIANCE', None, covariance, shrunk, shrinkage, None, effective_n)
    floor = float(np.finfo(float).eps * shrunk.shape[0] * lambda_max)
    floored = np.maximum(eigenvalues, floor)
    operator = eigenvectors * floored ** (-0.5) @ eigenvectors.T
    if not np.all(np.isfinite(operator)):
        return WhitenerResult('UNAVAILABLE', 'WHITENER_NONFINITE', None, covariance, shrunk, shrinkage, floor, effective_n)
    return WhitenerResult('AVAILABLE', None, operator, covariance, shrunk, shrinkage, floor, effective_n)

def weighted_empirical_quantile(values: ArrayLike, weights: ArrayLike, quantile: float=0.05) -> float:
    """Weighted inverse empirical CDF with no interpolation."""
    sample = np.asarray(values, dtype=float)
    mass = np.asarray(weights, dtype=float)
    if sample.ndim != 1 or mass.shape != sample.shape or sample.size == 0:
        raise ValueError('values and weights must be nonempty one-dimensional arrays of equal shape')
    if not np.all(np.isfinite(sample)) or not np.all(np.isfinite(mass)) or np.any(mass < 0):
        raise ValueError('values and weights must be finite with nonnegative weights')
    if not 0.0 < quantile <= 1.0 or mass.sum() <= 0.0:
        raise ValueError('quantile and weights are not normalizable')
    order = np.argsort(sample, kind='stable')
    cumulative = np.cumsum(mass[order] / mass.sum())
    index = min(int(np.searchsorted(cumulative, quantile, side='left')), sample.size - 1)
    return float(sample[order[index]])

def _unavailable(reason: str, cells: int=0, units: int=0) -> CandidateResult:
    return CandidateResult('CANDIDATE', 'UNAVAILABLE', 'NOT_TESTED', reason, None, None, (), units, cells, None)

def evaluate_candidate(units_by_cell: Mapping[str, Sequence[ArrayLike]], required_cells: Sequence[str], whitener: WhitenerResult) -> CandidateResult:
    """Evaluate one frozen candidate; this function does not aggregate families."""
    required = tuple(required_cells)
    if whitener.status != 'AVAILABLE' or whitener.operator is None:
        return _unavailable('W_UNAVAILABLE')
    if not required or any((cell not in units_by_cell for cell in required)):
        return _unavailable('MISSING_PREREGISTERED_NUISANCE_CELL')
    singular_values: list[NDArray[np.float64]] = []
    weights: list[float] = []
    try:
        for cell in required:
            units = units_by_cell[cell]
            if not units:
                return _unavailable('INCOMPLETE_NUISANCE_CELL', len(required), len(singular_values))
            cell_weight = 1.0 / len(required)
            for unit in units:
                y = np.asarray(unit, dtype=float)
                if y.ndim != 2 or y.shape[1] != 4 or y.shape[0] != whitener.operator.shape[1]:
                    return _unavailable('FEATURE_OR_STATE_IDENTITY_MISMATCH', len(required), len(singular_values))
                if not np.all(np.isfinite(y)):
                    return _unavailable('NONFINITE_EVALUATION_UNIT', len(required), len(singular_values))
                differential = y @ projection_matrices(4)[1]
                sv = np.linalg.svd(whitener.operator @ differential, compute_uv=False)
                if sv.size < 3 or not np.all(np.isfinite(sv)):
                    return _unavailable('THIRD_SINGULAR_VALUE_UNAVAILABLE', len(required), len(singular_values))
                singular_values.append(sv)
                weights.append(cell_weight / len(units))
    except np.linalg.LinAlgError as exc:
        return _unavailable(f'SVD_UNAVAILABLE:{exc}', len(required), len(singular_values))
    width = min((sv.size for sv in singular_values))
    quantiles = tuple((weighted_empirical_quantile([sv[index] for sv in singular_values], weights, 0.05) for index in range(width)))
    stable_rank = sum((value > 1.0 for value in quantiles))
    primary = quantiles[2]
    passed = primary > 1.0 and stable_rank == 3
    equal_unit_weights = np.allclose(weights, np.full(len(weights), 1.0 / len(weights)))
    disclosure = None
    if len(weights) < 20 and equal_unit_weights:
        disclosure = 'CONSERVATIVE_AND_SINGLE_UNIT_DOMINATED_Q_0.05_EQUALS_MINIMUM'
    return CandidateResult('CANDIDATE', 'PASS', 'PASS' if passed else 'NEGATIVE', None, primary, stable_rank, quantiles, len(singular_values), len(required), disclosure)


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

MODEL_NAME = 'PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1'

RHO_KG_M3 = 1.2041

SPEED_OF_SOUND_M_S = 343.0

TOTAL_VOLUME_M3 = 3.014899604922098e-05

BRANCH_HEIGHT_M = 0.0092

BRANCH_LENGTH_M = 0.002

SUPPORTED_FAMILIES = ('HAND_DESIGNED', 'NEAR_INDEPENDENT', 'FIXED_SEED_RANDOM_DISORDERED', 'PHYSICS_METAMATERIAL_INSPIRED')

THROUGH_REFERENCE_ID = 'THROUGH_REFERENCE_U4_IDENTITY_V1'

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

def _branch_parameters(family_id: str, parameters: Mapping[str, object], nuisance: Mapping[str, object], cell_index: int, repeat_index: int, repeat_seed: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    angles = (0, 90, 180, 270)
    if family_id == 'HAND_DESIGNED':
        central_mix = _number(parameters, 'central_mix')
        if not 0.1 <= central_mix <= 0.3:
            raise ForwardCoreError('HAND_CENTRAL_MIX_OUT_OF_RANGE')
        shared_coordinates = np.full(4, central_mix, dtype=float)
    elif family_id == 'NEAR_INDEPENDENT':
        alpha = _number(parameters, 'shared_alpha')
        if not 0.03 <= alpha <= 0.07:
            raise ForwardCoreError('NEAR_SHARED_ALPHA_OUT_OF_RANGE')
        normalized_coordinate = (alpha - 0.03) / 0.04
        normalized_coordinate = min(1.0, max(0.0, normalized_coordinate))
        shared_coordinates = np.full(4, normalized_coordinate, dtype=float)
    elif family_id == 'FIXED_SEED_RANDOM_DISORDERED':
        edge_coordinates: dict[tuple[int, int], float] = {}
        for left, right in ((0, 90), (0, 180), (0, 270), (90, 180), (90, 270), (180, 270)):
            value = _number(parameters, f'edge_{left}_{right}')
            if not 0.0 <= value <= 0.8:
                raise ForwardCoreError('RANDOM_EDGE_COORDINATE_OUT_OF_RANGE')
            edge_coordinates[left, right] = value
        shared_coordinates = np.array([sum((value for edge, value in edge_coordinates.items() if angle in edge)) / 3.0 for angle in angles], dtype=float)
    elif family_id == 'PHYSICS_METAMATERIAL_INSPIRED':
        ring_coordinates: dict[tuple[int, int], float] = {}
        for left, right in ((0, 90), (90, 180), (180, 270), (270, 0)):
            value = _number(parameters, f'ring_{left}_{right}')
            if not 0.2 <= value <= 0.8:
                raise ForwardCoreError('PHYSICS_RING_COORDINATE_OUT_OF_RANGE')
            ring_coordinates[left, right] = value
        shared_coordinates = np.array([sum((value for edge, value in ring_coordinates.items() if angle in edge)) / 2.0 for angle in angles], dtype=float)
    elif family_id == THROUGH_REFERENCE_ID:
        central_mix = _number(parameters, 'central_mix')
        if central_mix != 0.5:
            raise ForwardCoreError('THROUGH_REFERENCE_CENTRAL_MIX_MISMATCH')
        shared_coordinates = np.full(4, 0.5, dtype=float)
    else:
        raise ForwardCoreError(f'FAMILY_GRAPH_MAPPING_UNAVAILABLE:{family_id}')
    independent_percent = _number(nuisance, 'independent_manufacturing_percent')
    batch_percent = _number(nuisance, 'batch_correlated_manufacturing_percent')
    if not -2.0 <= independent_percent <= 2.0 or not -2.0 <= batch_percent <= 2.0:
        raise ForwardCoreError('MANUFACTURING_PERCENT_OUT_OF_RANGE')
    batch_factor = 1.0 + batch_percent / 100.0
    mix_areas = np.array([_aperture_area(value) for value in shared_coordinates]) * batch_factor
    masses = np.empty(4, dtype=float)
    resistances = np.empty(4, dtype=float)
    for index, angle in enumerate(angles):
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

def _substream_uniform_array(base_seed: int, cell_index: int, repeat_index: int, substreams: NDArray[np.uint64]) -> NDArray[np.float64]:
    """Vectorized exact SplitMix64/open-interval transform used by the scalar reference."""
    with np.errstate(over='ignore'):
        x = np.uint64(base_seed) + np.uint64(GOLDEN_GAMMA) * (np.uint64(1 + 64 * cell_index + 32 * repeat_index) + substreams)
        z = x + np.uint64(GOLDEN_GAMMA)
        z = (z ^ z >> np.uint64(30)) * np.uint64(13787848793156543929)
        z = (z ^ z >> np.uint64(27)) * np.uint64(10723151780598845931)
        z = z ^ z >> np.uint64(31)
    return ((z >> np.uint64(11)).astype(np.float64) + 0.5) / float(1 << 53)

def solve_forward_block(member: Mapping[str, object], nuisance: Mapping[str, object], *, cell_index: int, repeat_index: int, frequencies_hz: Sequence[float], state_angles_degrees: Sequence[float], partition: str, repeat_seed_tuple: Sequence[int], frequency_start_index: int=0, include_additive_sensor_noise: bool=True) -> ForwardBlockResult:
    """Batched, semantically equivalent solve for one frozen workload block."""
    family_id = member.get('family_id')
    ordinary_member = member.get('status') == 'STATIC_IDENTITY_ELIGIBLE' and family_id in SUPPORTED_FAMILIES
    through_reference = member.get('status') == 'THROUGH_REFERENCE_STATIC_IDENTITY' and family_id == THROUGH_REFERENCE_ID
    if not ordinary_member and (not through_reference):
        raise ForwardCoreError('UNSUPPORTED_OR_INELIGIBLE_MEMBER')
    if not isinstance(cell_index, int) or cell_index < 0 or (not isinstance(repeat_index, int)) or (repeat_index not in (0, 1)):
        raise ForwardCoreError('INVALID_CELL_OR_REPEAT')
    parameters = member.get('parameters')
    if not isinstance(parameters, Mapping):
        raise ForwardCoreError('MISSING_PARAMETERS')
    frequencies = np.asarray(frequencies_hz, dtype=float)
    try:
        states = validate_frozen_angles(partition, state_angles_degrees)
        repeat_seeds = resolve_partition_repeat_seeds(partition, repeat_seed_tuple)
    except E2AuthorityError as exc:
        raise ForwardCoreError(str(exc)) from exc
    if not isinstance(frequency_start_index, int) or frequency_start_index < 0 or frequencies.ndim != 1 or (frequencies.size < 1) or (frequency_start_index + frequencies.size > 256) or (not np.allclose(frequencies, frozen_frequency_grid()[frequency_start_index:frequency_start_index + frequencies.size], rtol=1e-12, atol=0.0)):
        raise ForwardCoreError('FROZEN_CONTIGUOUS_FREQUENCY_BLOCK_REQUIRED')
    shift = _number(nuisance, 'common_frequency_axis_shift_relative')
    common_gain = 10.0 ** (_number(nuisance, 'common_gain_db') / 20.0)
    sensor_gain = 10.0 ** (_number(nuisance, 'sensor_independent_gain_db') / 20.0)
    snr_db = _number(nuisance, 'snr_db')
    angle_offset = _number(nuisance, 'angle_offset_degrees')
    if snr_db not in (20.0, 30.0, 40.0):
        raise ForwardCoreError('SNR_LEVEL_NOT_FROZEN')
    if angle_offset not in (-5.0, -3.0, -1.0, 0.0, 1.0, 3.0, 5.0):
        raise ForwardCoreError('ANGLE_OFFSET_LEVEL_NOT_FROZEN')
    if not -0.005 <= shift <= 0.005:
        raise ForwardCoreError('FREQUENCY_SHIFT_OUT_OF_RANGE')
    volumes = _volume_partition(parameters)
    compliances = volumes / (RHO_KG_M3 * SPEED_OF_SOUND_M_S ** 2)
    masses, resistances = _branch_parameters(str(family_id), parameters, nuisance, cell_index, repeat_index, repeat_seeds[repeat_index])
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
        raise ForwardCoreError('NETWORK_NOT_SOLVABLE') from exc
    pressure = solutions[:, 4, :].reshape(frequencies.size, len(states), 4).transpose(1, 2, 0).copy()
    pressure *= common_gain * sensor_gain
    global_frequency_indices = np.arange(frequency_start_index, frequency_start_index + frequencies.size, dtype=np.uint64)
    global_angle_indices = np.asarray([angle_global_ordinal(partition, value) for value in states], dtype=np.uint64)
    flat = (global_angle_indices[:, None, None] * np.uint64(4) + np.arange(4, dtype=np.uint64)[None, :, None]) * np.uint64(256) + global_frequency_indices[None, None, :]
    if include_additive_sensor_noise:
        uniforms = _substream_uniform_array(repeat_seeds[repeat_index], cell_index, repeat_index, np.uint64(8) + flat)
        phases = 2.0 * math.pi * uniforms
        pressure += 10.0 ** (-snr_db / 20.0) * (np.cos(phases) + 1j * np.sin(phases))
    valid = bool(passive and reciprocal and np.all(np.isfinite(pressure)))
    if not valid:
        raise ForwardCoreError('NETWORK_NUMERIC_VALIDITY_FAIL')
    return ForwardBlockResult(MODEL_NAME, pressure, passive, reciprocal, True, valid)


# Robust encoding geometry

PAIR_COLUMN_INDICES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))

PRIMARY_FREQUENCIES = 208

COMPLEX_FEATURE_DIMENSION = PRIMARY_FREQUENCIES * 4

REAL_FEATURE_DIMENSION = COMPLEX_FEATURE_DIMENSION * 2

LOWER_TAIL_MASS = 0.05

FAMILY_ORDER = ('HAND_DESIGNED', 'NEAR_INDEPENDENT', 'FIXED_SEED_RANDOM_DISORDERED', 'PHYSICS_METAMATERIAL_INSPIRED')

BOOTSTRAP_SEED = 2026090301

PERMUTATION_SEED = 2026090302

BOOTSTRAP_REPLICATES = 20000

PERMUTATION_REPLICATES = 100000

class RobustGeometryError(ValueError):
    """Fail-closed formula or identity error."""

def trace_normalized_gram(gram: ArrayLike) -> NDArray[np.complex128]:
    """Hermitian-symmetrize and normalize by the real trace, without PSD refit."""
    value = np.asarray(gram, dtype=np.complex128)
    if value.shape != (4, 4) or not np.all(np.isfinite(value)):
        raise RobustGeometryError('FINITE_4_BY_4_GRAM_REQUIRED')
    hermitian = 0.5 * (value + value.conj().T)
    trace = float(np.trace(hermitian).real)
    if not math.isfinite(trace) or trace <= 0.0:
        raise RobustGeometryError('STRICTLY_POSITIVE_REAL_GRAM_TRACE_REQUIRED')
    normalized = np.asarray(hermitian / trace, dtype=np.complex128)
    if not np.all(np.isfinite(normalized)):
        raise RobustGeometryError('FINITE_NORMALIZED_GRAM_REQUIRED')
    return normalized

def development_reference_gram(normalized_grams: ArrayLike, weights: ArrayLike) -> NDArray[np.complex128]:
    """Construct one identity's frozen reference from development units only."""
    grams = np.asarray(normalized_grams, dtype=np.complex128)
    mass = _normalized_weights(weights, grams.shape[0] if grams.ndim == 3 else -1)
    if grams.ndim != 3 or grams.shape[1:] != (4, 4) or (not np.all(np.isfinite(grams))):
        raise RobustGeometryError('FINITE_UNIT_BY_4_BY_4_NORMALIZED_GRAMS_REQUIRED')
    reference = np.tensordot(mass, grams, axes=(0, 0))
    return trace_normalized_gram(reference)

def frobenius_gram_drift(normalized_grams: ArrayLike, reference_gram: ArrayLike) -> NDArray[np.float64]:
    """Return dimensionless Frobenius drift for each unit."""
    grams = np.asarray(normalized_grams, dtype=np.complex128)
    reference = np.asarray(reference_gram, dtype=np.complex128)
    if grams.ndim != 3 or grams.shape[1:] != (4, 4) or (not np.all(np.isfinite(grams))):
        raise RobustGeometryError('FINITE_UNIT_BY_4_BY_4_NORMALIZED_GRAMS_REQUIRED')
    if reference.shape != (4, 4) or not np.all(np.isfinite(reference)):
        raise RobustGeometryError('FINITE_4_BY_4_REFERENCE_GRAM_REQUIRED')
    drift = np.linalg.norm(grams - reference[None, :, :], ord='fro', axis=(1, 2))
    return np.asarray(drift, dtype=np.float64)

def pair_anisotropy(distances: ArrayLike) -> NDArray[np.float64]:
    """Return ``max(d_ab) / min(d_ab)``; one denotes pairwise isotropy."""
    value = np.asarray(distances, dtype=np.float64)
    if value.ndim < 1 or value.shape[-1] != 6 or (not np.all(np.isfinite(value))):
        raise RobustGeometryError('FINITE_SIX_PAIR_DISTANCES_REQUIRED')
    minimum = np.min(value, axis=-1)
    if np.any(minimum <= 0.0):
        raise RobustGeometryError('STRICTLY_POSITIVE_D_MIN_REQUIRED_FOR_ANISOTROPY')
    return np.asarray(np.max(value, axis=-1) / minimum, dtype=np.float64)

def weakest_pair_index(distances: ArrayLike) -> NDArray[np.uint8]:
    """Return first exact minimum in frozen pair order (deterministic tie break)."""
    value = np.asarray(distances, dtype=np.float64)
    if value.ndim < 1 or value.shape[-1] != 6 or (not np.all(np.isfinite(value))):
        raise RobustGeometryError('FINITE_SIX_PAIR_DISTANCES_REQUIRED')
    return np.asarray(np.argmin(value, axis=-1), dtype=np.uint8)

def weighted_lower_tail_expected_shortfall(values: ArrayLike, weights: ArrayLike, tail_mass: float=LOWER_TAIL_MASS) -> float:
    """Mean of the lowest ``tail_mass`` probability, with fractional boundary."""
    return _weighted_tail_expected_shortfall(values, weights, tail_mass, upper=False)

def weighted_upper_tail_expected_shortfall(values: ArrayLike, weights: ArrayLike, tail_mass: float=LOWER_TAIL_MASS) -> float:
    """Mean of the highest ``tail_mass`` probability, with fractional boundary."""
    return _weighted_tail_expected_shortfall(values, weights, tail_mass, upper=True)

def _normalized_weights(weights: ArrayLike, expected_size: int) -> NDArray[np.float64]:
    mass = np.asarray(weights, dtype=np.float64)
    if mass.ndim != 1 or mass.size != expected_size or (not np.all(np.isfinite(mass))) or np.any(mass < 0.0):
        raise RobustGeometryError('FINITE_NONNEGATIVE_ONE_DIMENSIONAL_WEIGHTS_REQUIRED')
    total = float(mass.sum())
    if total <= 0.0 or not math.isfinite(total):
        raise RobustGeometryError('POSITIVE_FINITE_WEIGHT_SUM_REQUIRED')
    return np.asarray(mass / total, dtype=np.float64)

def _weighted_tail_expected_shortfall(values: ArrayLike, weights: ArrayLike, tail_mass: float, *, upper: bool) -> float:
    sample = np.asarray(values, dtype=np.float64)
    if sample.ndim != 1 or sample.size == 0 or (not np.all(np.isfinite(sample))):
        raise RobustGeometryError('FINITE_NONEMPTY_ONE_DIMENSIONAL_VALUES_REQUIRED')
    if not 0.0 < tail_mass <= 1.0 or not math.isfinite(tail_mass):
        raise RobustGeometryError('TAIL_MASS_IN_OPEN_CLOSED_UNIT_INTERVAL_REQUIRED')
    mass = _normalized_weights(weights, sample.size)
    order = np.argsort(sample, kind='stable')
    if upper:
        order = order[::-1]
    remaining = float(tail_mass)
    integral = 0.0
    for index in order:
        taken = min(float(mass[index]), remaining)
        integral += taken * float(sample[index])
        remaining -= taken
        if remaining <= np.finfo(np.float64).eps * tail_mass:
            break
    if remaining > 1e-14:
        raise RobustGeometryError('TAIL_MASS_NOT_FILLED')
    return float(integral / tail_mass)

def summarize_candidate_geometry(distances: ArrayLike, gram_drift: ArrayLike, weights: ArrayLike) -> dict[str, object]:
    """Return the frozen candidate summaries from finest-unit compact arrays."""
    pair = np.asarray(distances, dtype=np.float64)
    drift = np.asarray(gram_drift, dtype=np.float64)
    if pair.ndim != 2 or pair.shape[1] != 6 or (not np.all(np.isfinite(pair))):
        raise RobustGeometryError('FINITE_UNIT_BY_SIX_DISTANCES_REQUIRED')
    if drift.shape != (pair.shape[0],) or not np.all(np.isfinite(drift)) or np.any(drift < 0.0):
        raise RobustGeometryError('FINITE_NONNEGATIVE_UNIT_DRIFT_REQUIRED')
    mass = _normalized_weights(weights, pair.shape[0])
    minimum = np.min(pair, axis=1)
    weak = weakest_pair_index(pair)
    weakest_mass = [float(mass[weak == index].sum()) for index in range(6)]
    anisotropy = pair_anisotropy(pair)
    return {'d_min_lower_tail_es_0p05': weighted_lower_tail_expected_shortfall(minimum, mass), 'pair_lower_tail_es_0p05': [weighted_lower_tail_expected_shortfall(pair[:, index], mass) for index in range(6)], 'weakest_pair_probability': weakest_mass, 'pair_anisotropy_mean': float(np.sum(mass * anisotropy)), 'pair_anisotropy_upper_tail_es_0p05': weighted_upper_tail_expected_shortfall(anisotropy, mass), 'gram_frobenius_drift_mean': float(np.sum(mass * drift)), 'gram_frobenius_drift_upper_tail_es_0p05': weighted_upper_tail_expected_shortfall(drift, mass), 'unit_count': int(pair.shape[0])}

def batch_geometry_from_raw(raw: ArrayLike, whitener: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.complex128], NDArray[np.complex128]]:
    """Vectorized compact geometry for an E2 raw chunk.

    Input is ``state x cell x repeat x port x frequency``.  Outputs are
    ``distances[cell,repeat,6]``, ``normalized_gram[cell,repeat,4,4]`` and
    ``Y_diff[cell,repeat,832,4]``.  The last output is intended only for the
    deterministic, sparse audit sampler and must not be retained wholesale.
    """
    values = np.asarray(raw, dtype=np.complex128)
    operator = np.asarray(whitener, dtype=np.float64)
    if values.ndim != 5 or values.shape[0] != 4 or values.shape[2:] != (2, 4, 256) or (not np.all(np.isfinite(values))):
        raise RobustGeometryError('FINITE_E2_RAW_CHUNK_SHAPE_REQUIRED')
    if operator.shape != (REAL_FEATURE_DIMENSION, REAL_FEATURE_DIMENSION) or not np.all(np.isfinite(operator)):
        raise RobustGeometryError('FINITE_FROZEN_COMMON_W_1664_SQUARE_REQUIRED')
    cells = values.shape[1]
    weights = trapezoidal_weights(frozen_frequency_grid()[:PRIMARY_FREQUENCIES])
    ordered = np.transpose(values[:, :, :, :, :PRIMARY_FREQUENCIES], (1, 2, 4, 3, 0))
    weighted = ordered * np.sqrt(weights)[None, None, :, None, None]
    y = weighted.reshape((cells, 2, COMPLEX_FEATURE_DIMENSION, 4), order='C')
    y_diff = np.asarray(y @ projection_matrices(4)[1], dtype=np.complex128)
    embedded = np.concatenate((y_diff.real, y_diff.imag), axis=2)
    columns = np.transpose(embedded, (2, 0, 1, 3)).reshape((REAL_FEATURE_DIMENSION, cells * 2 * 4), order='C')
    z_columns = operator @ columns
    z_real = np.transpose(z_columns.reshape((REAL_FEATURE_DIMENSION, cells, 2, 4), order='C'), (1, 2, 0, 3))
    z = z_real[:, :, :COMPLEX_FEATURE_DIMENSION] + 1j * z_real[:, :, COMPLEX_FEATURE_DIMENSION:]
    distances = np.empty((cells, 2, 6), dtype=np.float64)
    for pair_index, (left, right) in enumerate(PAIR_COLUMN_INDICES):
        distances[:, :, pair_index] = np.linalg.norm(z[:, :, :, left] - z[:, :, :, right], axis=2)
    grams = np.einsum('urfi,urfj->urij', z.conj(), z, optimize=True)
    grams = 0.5 * (grams + grams.conj().transpose(0, 1, 3, 2))
    trace = np.trace(grams, axis1=2, axis2=3).real
    if np.any(trace <= 0.0) or not np.all(np.isfinite(trace)):
        raise RobustGeometryError('STRICTLY_POSITIVE_FINITE_BATCH_GRAM_TRACE_REQUIRED')
    normalized = grams / trace[:, :, None, None]
    if not np.all(np.isfinite(distances)) or not np.all(np.isfinite(normalized)):
        raise RobustGeometryError('NONFINITE_BATCH_GEOMETRY')
    return (distances, np.asarray(normalized, dtype=np.complex128), y_diff)

def _family_endpoint_matrix(values_by_family: Mapping[str, ArrayLike]) -> NDArray[np.float64]:
    if set(values_by_family) != set(FAMILY_ORDER):
        raise RobustGeometryError('EXACT_FOUR_FAMILY_KEYS_REQUIRED')
    rows = []
    for family in FAMILY_ORDER:
        values = np.asarray(values_by_family[family], dtype=np.float64)
        if values.shape != (20,) or not np.all(np.isfinite(values)):
            raise RobustGeometryError('EXACT20_FINITE_IDENTITY_VALUES_PER_FAMILY_REQUIRED')
        rows.append(values)
    return np.stack(rows)

def _six_contrasts(means: NDArray[np.float64], *, drift_direction: bool) -> NDArray[np.float64]:
    contrasts = []
    for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)):
        contrasts.append(means[right] - means[left] if drift_direction else means[left] - means[right])
    return np.asarray(contrasts, dtype=np.float64)

def _welch_twelve(margin: NDArray[np.float64], drift: NDArray[np.float64]) -> tuple[dict[str, object], NDArray[np.float64] | None]:
    endpoint_records: dict[str, object] = {}
    statistics: list[float] = []
    for name, matrix, drift_direction in (('margin', margin, False), ('drift', drift, True)):
        means = np.mean(matrix, axis=1)
        variances = np.var(matrix, axis=1, ddof=1)
        contrasts = _six_contrasts(means, drift_direction=drift_direction)
        standard_errors = []
        for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)):
            standard_errors.append(math.sqrt(float(variances[left] / 20.0 + variances[right] / 20.0)))
        standard_error = np.asarray(standard_errors, dtype=np.float64)
        if np.any(standard_error <= 0.0) or not np.all(np.isfinite(standard_error)):
            endpoint_records[name] = {'status': 'INCONCLUSIVE', 'reason': 'ZERO_OR_NONFINITE_WELCH_STANDARD_ERROR', 'contrasts': contrasts, 'standard_errors': standard_error, 'statistics': None}
            continue
        endpoint_t = contrasts / standard_error
        if not np.all(np.isfinite(endpoint_t)):
            endpoint_records[name] = {'status': 'INCONCLUSIVE', 'reason': 'NONFINITE_WELCH_T', 'contrasts': contrasts, 'standard_errors': standard_error, 'statistics': None}
            continue
        endpoint_records[name] = {'status': 'AVAILABLE', 'reason': None, 'contrasts': contrasts, 'standard_errors': standard_error, 'statistics': endpoint_t}
        statistics.extend((float(value) for value in endpoint_t))
    if len(statistics) != 12:
        return (endpoint_records, None)
    return (endpoint_records, np.asarray(statistics, dtype=np.float64))

def identity_level_family_inference(margin_by_family: Mapping[str, ArrayLike], drift_by_family: Mapping[str, ArrayLike], *, bootstrap_replicates: int=BOOTSTRAP_REPLICATES, permutation_replicates: int=PERMUTATION_REPLICATES, bootstrap_seed: int=BOOTSTRAP_SEED, permutation_seed: int=PERMUTATION_SEED) -> dict[str, object]:
    """Run the frozen exact20 identity-level bootstrap and 12-stat max-|T| test.

    Margin contrast is ``mean(S_A)-mean(S_B)``.  Drift contrast is
    ``mean(U_B)-mean(U_A)``.  Thus positive values favor family A for both.
    The same within-family bootstrap indices and the same all-80 label
    permutation are applied to the paired margin/drift identity records.
    """
    if bootstrap_replicates < 1 or permutation_replicates < 1:
        raise RobustGeometryError('POSITIVE_INFERENCE_REPLICATE_COUNTS_REQUIRED')
    margin = _family_endpoint_matrix(margin_by_family)
    drift = _family_endpoint_matrix(drift_by_family)
    observed, observed_twelve = _welch_twelve(margin, drift)
    bootstrap_rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    bootstrap_indices = np.stack([bootstrap_rng.integers(0, 20, size=(bootstrap_replicates, 20), endpoint=False) for _ in FAMILY_ORDER])
    margin_means = np.stack([np.mean(margin[family][bootstrap_indices[family]], axis=1) for family in range(4)], axis=1)
    drift_means = np.stack([np.mean(drift[family][bootstrap_indices[family]], axis=1) for family in range(4)], axis=1)
    margin_bootstrap = np.stack([margin_means[:, left] - margin_means[:, right] for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))], axis=1)
    drift_bootstrap = np.stack([drift_means[:, right] - drift_means[:, left] for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))], axis=1)
    margin_ci = np.quantile(margin_bootstrap, (0.025, 0.975), axis=0, method='linear').T
    drift_ci = np.quantile(drift_bootstrap, (0.025, 0.975), axis=0, method='linear').T
    if observed_twelve is None:
        return {'status': 'INCONCLUSIVE', 'reason': 'AT_LEAST_ONE_ENDPOINT_WELCH_DENOMINATOR_UNAVAILABLE', 'observed': observed, 'bootstrap': {'replicates': bootstrap_replicates, 'seed': bootstrap_seed, 'generator': 'PCG64', 'quantile_method': 'linear', 'margin_contrasts': margin_bootstrap, 'drift_contrasts': drift_bootstrap, 'margin_percentile_95_ci': margin_ci, 'drift_percentile_95_ci': drift_ci}, 'permutation': None}
    permutation_rng = np.random.Generator(np.random.PCG64(permutation_seed))
    margin_flat = margin.reshape(-1)
    drift_flat = drift.reshape(-1)
    maxima = np.empty(permutation_replicates, dtype=np.float64)
    for replicate in range(permutation_replicates):
        indices = permutation_rng.permutation(80)
        permuted_margin = margin_flat[indices].reshape((4, 20))
        permuted_drift = drift_flat[indices].reshape((4, 20))
        _, statistics = _welch_twelve(permuted_margin, permuted_drift)
        if statistics is None:
            return {'status': 'INCONCLUSIVE', 'reason': 'PERMUTED_ZERO_OR_NONFINITE_WELCH_DENOMINATOR', 'observed': observed, 'bootstrap': {'replicates': bootstrap_replicates, 'seed': bootstrap_seed, 'generator': 'PCG64', 'quantile_method': 'linear', 'margin_contrasts': margin_bootstrap, 'drift_contrasts': drift_bootstrap, 'margin_percentile_95_ci': margin_ci, 'drift_percentile_95_ci': drift_ci}, 'permutation': None}
        maxima[replicate] = float(np.max(np.abs(statistics)))
    adjusted = np.asarray([(1.0 + float(np.count_nonzero(maxima >= abs(observed_value)))) / float(permutation_replicates + 1) for observed_value in observed_twelve], dtype=np.float64)
    return {'status': 'AVAILABLE', 'reason': None, 'observed': observed, 'bootstrap': {'replicates': bootstrap_replicates, 'seed': bootstrap_seed, 'generator': 'PCG64', 'quantile_method': 'linear', 'margin_contrasts': margin_bootstrap, 'drift_contrasts': drift_bootstrap, 'margin_percentile_95_ci': margin_ci, 'drift_percentile_95_ci': drift_ci}, 'permutation': {'replicates': permutation_replicates, 'seed': permutation_seed, 'generator': 'PCG64', 'observed_twelve': observed_twelve, 'max_abs_t': maxima, 'adjusted_p': adjusted, 'adjusted_p_formula_denominator': permutation_replicates + 1, 'statistic_count': 12}}


def load_model_inputs():
    """Load the 80 archived member identities, nuisance cells and frozen readout."""
    members = json.loads((DATA_DIR / 'model_members.json').read_text(encoding='utf-8'))
    with (DATA_DIR / 'nuisance_design_table.csv').open(encoding='utf-8', newline='') as handle:
        nuisance = [{k: (v if k == 'design_row_id' else float(v)) for k, v in row.items()} for row in csv.DictReader(handle)]
    operator = np.load(DATA_DIR / 'common_whitening_operator.npy', allow_pickle=False)
    return members, nuisance, operator

def paper_example():
    """Evaluate one development cell for HAND_01, using the frozen operator.

    This bounded example uses both original development repeat seeds and the
    original 256-point grid. Full-library rank and family statistics are preserved
    as archived numerical data. Single-use validation is read only as archived
    results; this example does not rerun validation or fit a new operator.
    """
    members, nuisance, operator = load_model_inputs()
    frequency = frozen_frequency_grid()
    blocks = [solve_forward_block(members[0], nuisance[0], cell_index=0, repeat_index=r,
              frequencies_hz=frequency, state_angles_degrees=DEVELOPMENT_ANGLES_DEGREES,
              partition='development', repeat_seed_tuple=DEVELOPMENT_REPEAT_SEEDS) for r in range(2)]
    raw = np.stack([b.central_pressure for b in blocks], axis=1)[:, None, :, :, :]
    distances, grams, _ = batch_geometry_from_raw(raw, operator)
    with (DATA_DIR / 'archived_rank_metrics.csv').open(encoding='utf-8', newline='') as handle:
        rank = list(csv.DictReader(handle))
    return {'member_count': len(members), 'nuisance_cell_count': len(nuisance), 'operator_shape': list(operator.shape),
            'example_member': members[0]['member_id'], 'development_cell': 0,
            'pair_distances_by_repeat': distances[0].tolist(), 'gram_traces': np.trace(grams[0], axis1=1, axis2=2).real.tolist(),
            'archived_rank_pass_counts': {partition: sum(row['partition'] == partition and row['scientific_status'] == 'PASS' for row in rank) for partition in ('development', 'single_use_validation')}}

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))


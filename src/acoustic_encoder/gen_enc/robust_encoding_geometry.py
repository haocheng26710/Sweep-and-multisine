"""Frozen GEN-ENC-3A robust encoding-geometry primitives.

The E2 whitener is a real 1664-by-1664 operator fitted to the ordered
``[Re(weighted complex features); Im(weighted complex features)]`` embedding.
This module applies that exact operator first and only then reassembles the
whitened rows into complex coordinates.  Reassembly is an isometry, not a
new fit or a new whitening convention.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .estimator import projection_matrices, trapezoidal_weights
from .forward_acoustic_network import frozen_frequency_grid


STATE_ORDER_DEGREES = (0, 90, 180, 270)
PAIR_ORDER = ((0, 90), (0, 180), (0, 270), (90, 180), (90, 270), (180, 270))
PAIR_COLUMN_INDICES = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
PRIMARY_FREQUENCIES = 208
COMPLEX_FEATURE_DIMENSION = PRIMARY_FREQUENCIES * 4
REAL_FEATURE_DIMENSION = COMPLEX_FEATURE_DIMENSION * 2
LOWER_TAIL_MASS = 0.05
FAMILY_ORDER = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)
FAMILY_CONTRAST_ORDER = tuple(
    (FAMILY_ORDER[left], FAMILY_ORDER[right])
    for left in range(len(FAMILY_ORDER))
    for right in range(left + 1, len(FAMILY_ORDER))
)
BOOTSTRAP_SEED = 2026090301
PERMUTATION_SEED = 2026090302
BOOTSTRAP_REPLICATES = 20_000
PERMUTATION_REPLICATES = 100_000


class RobustGeometryError(ValueError):
    """Fail-closed formula or identity error."""


def primary_complex_differential(response: ArrayLike) -> NDArray[np.complex128]:
    """Return primary weighted complex ``Y_diff`` with shape ``(832, 4)``.

    ``response`` has the E2 unit orientation ``state x port x frequency``.
    Rows are ordered frequency-major and then port-major.  The four columns
    retain the frozen physical state order 0/90/180/270 degrees.
    """

    values = np.asarray(response, dtype=np.complex128)
    if values.shape != (4, 4, 256) or not np.all(np.isfinite(values)):
        raise RobustGeometryError("FINITE_E2_UNIT_SHAPE_4_4_256_REQUIRED")
    weights = trapezoidal_weights(frozen_frequency_grid()[:PRIMARY_FREQUENCIES])
    frequency_port_state = np.transpose(values[:, :, :PRIMARY_FREQUENCIES], (2, 1, 0))
    weighted = frequency_port_state * np.sqrt(weights)[:, None, None]
    y = weighted.reshape((COMPLEX_FEATURE_DIMENSION, 4), order="C")
    return np.asarray(y @ projection_matrices(4)[1], dtype=np.complex128)


def real_embed_complex(value: ArrayLike) -> NDArray[np.float64]:
    """Apply the frozen E2 row convention ``[Re; Im]``."""

    array = np.asarray(value, dtype=np.complex128)
    if array.ndim != 2 or array.shape[0] != COMPLEX_FEATURE_DIMENSION or not np.all(np.isfinite(array)):
        raise RobustGeometryError("FINITE_COMPLEX_FEATURE_BY_STATE_MATRIX_REQUIRED")
    return np.concatenate((array.real, array.imag), axis=0)


def complex_unembed_real(value: ArrayLike) -> NDArray[np.complex128]:
    """Isometrically reassemble frozen real-embedded rows into complex rows."""

    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] != REAL_FEATURE_DIMENSION or not np.all(np.isfinite(array)):
        raise RobustGeometryError("FINITE_REAL_EMBEDDED_FEATURE_BY_STATE_MATRIX_REQUIRED")
    return np.asarray(
        array[:COMPLEX_FEATURE_DIMENSION] + 1j * array[COMPLEX_FEATURE_DIMENSION:],
        dtype=np.complex128,
    )


def whitened_complex_differential(
    response: ArrayLike,
    whitener: ArrayLike,
) -> tuple[NDArray[np.complex128], NDArray[np.complex128], NDArray[np.float64]]:
    """Return ``(Y_diff_complex, Z_complex, Z_real)`` for one E2 unit."""

    operator = np.asarray(whitener, dtype=np.float64)
    if operator.shape != (REAL_FEATURE_DIMENSION, REAL_FEATURE_DIMENSION) or not np.all(np.isfinite(operator)):
        raise RobustGeometryError("FINITE_FROZEN_COMMON_W_1664_SQUARE_REQUIRED")
    y_diff = primary_complex_differential(response)
    z_real = np.asarray(operator @ real_embed_complex(y_diff), dtype=np.float64)
    z_complex = complex_unembed_real(z_real)
    return y_diff, z_complex, z_real


def pair_distances(z_complex: ArrayLike) -> NDArray[np.float64]:
    """Return the six frozen state-pair distances in whitening-noise units."""

    z = np.asarray(z_complex, dtype=np.complex128)
    if z.ndim != 2 or z.shape[1] != 4 or not np.all(np.isfinite(z)):
        raise RobustGeometryError("FINITE_COMPLEX_FEATURE_BY_FOUR_STATES_REQUIRED")
    distances = np.asarray(
        [np.linalg.norm(z[:, left] - z[:, right]) for left, right in PAIR_COLUMN_INDICES],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(distances)) or np.any(distances < 0.0):
        raise RobustGeometryError("FINITE_NONNEGATIVE_PAIR_DISTANCES_REQUIRED")
    return distances


def hermitian_gram(z_complex: ArrayLike) -> NDArray[np.complex128]:
    """Return the state Gram ``G = Z.conj().T @ Z`` in frozen state order."""

    z = np.asarray(z_complex, dtype=np.complex128)
    if z.ndim != 2 or z.shape[1] != 4 or not np.all(np.isfinite(z)):
        raise RobustGeometryError("FINITE_COMPLEX_FEATURE_BY_FOUR_STATES_REQUIRED")
    gram = np.asarray(z.conj().T @ z, dtype=np.complex128)
    if not np.all(np.isfinite(gram)):
        raise RobustGeometryError("FINITE_GRAM_REQUIRED")
    return gram


def trace_normalized_gram(gram: ArrayLike) -> NDArray[np.complex128]:
    """Hermitian-symmetrize and normalize by the real trace, without PSD refit."""

    value = np.asarray(gram, dtype=np.complex128)
    if value.shape != (4, 4) or not np.all(np.isfinite(value)):
        raise RobustGeometryError("FINITE_4_BY_4_GRAM_REQUIRED")
    hermitian = 0.5 * (value + value.conj().T)
    trace = float(np.trace(hermitian).real)
    if not math.isfinite(trace) or trace <= 0.0:
        raise RobustGeometryError("STRICTLY_POSITIVE_REAL_GRAM_TRACE_REQUIRED")
    normalized = np.asarray(hermitian / trace, dtype=np.complex128)
    if not np.all(np.isfinite(normalized)):
        raise RobustGeometryError("FINITE_NORMALIZED_GRAM_REQUIRED")
    return normalized


def development_reference_gram(
    normalized_grams: ArrayLike,
    weights: ArrayLike,
) -> NDArray[np.complex128]:
    """Construct one identity's frozen reference from development units only."""

    grams = np.asarray(normalized_grams, dtype=np.complex128)
    mass = _normalized_weights(weights, grams.shape[0] if grams.ndim == 3 else -1)
    if grams.ndim != 3 or grams.shape[1:] != (4, 4) or not np.all(np.isfinite(grams)):
        raise RobustGeometryError("FINITE_UNIT_BY_4_BY_4_NORMALIZED_GRAMS_REQUIRED")
    reference = np.tensordot(mass, grams, axes=(0, 0))
    return trace_normalized_gram(reference)


def frobenius_gram_drift(
    normalized_grams: ArrayLike,
    reference_gram: ArrayLike,
) -> NDArray[np.float64]:
    """Return dimensionless Frobenius drift for each unit."""

    grams = np.asarray(normalized_grams, dtype=np.complex128)
    reference = np.asarray(reference_gram, dtype=np.complex128)
    if grams.ndim != 3 or grams.shape[1:] != (4, 4) or not np.all(np.isfinite(grams)):
        raise RobustGeometryError("FINITE_UNIT_BY_4_BY_4_NORMALIZED_GRAMS_REQUIRED")
    if reference.shape != (4, 4) or not np.all(np.isfinite(reference)):
        raise RobustGeometryError("FINITE_4_BY_4_REFERENCE_GRAM_REQUIRED")
    drift = np.linalg.norm(grams - reference[None, :, :], ord="fro", axis=(1, 2))
    return np.asarray(drift, dtype=np.float64)


def pair_anisotropy(distances: ArrayLike) -> NDArray[np.float64]:
    """Return ``max(d_ab) / min(d_ab)``; one denotes pairwise isotropy."""

    value = np.asarray(distances, dtype=np.float64)
    if value.ndim < 1 or value.shape[-1] != 6 or not np.all(np.isfinite(value)):
        raise RobustGeometryError("FINITE_SIX_PAIR_DISTANCES_REQUIRED")
    minimum = np.min(value, axis=-1)
    if np.any(minimum <= 0.0):
        raise RobustGeometryError("STRICTLY_POSITIVE_D_MIN_REQUIRED_FOR_ANISOTROPY")
    return np.asarray(np.max(value, axis=-1) / minimum, dtype=np.float64)


def weakest_pair_index(distances: ArrayLike) -> NDArray[np.uint8]:
    """Return first exact minimum in frozen pair order (deterministic tie break)."""

    value = np.asarray(distances, dtype=np.float64)
    if value.ndim < 1 or value.shape[-1] != 6 or not np.all(np.isfinite(value)):
        raise RobustGeometryError("FINITE_SIX_PAIR_DISTANCES_REQUIRED")
    return np.asarray(np.argmin(value, axis=-1), dtype=np.uint8)


def weighted_lower_tail_expected_shortfall(
    values: ArrayLike,
    weights: ArrayLike,
    tail_mass: float = LOWER_TAIL_MASS,
) -> float:
    """Mean of the lowest ``tail_mass`` probability, with fractional boundary."""

    return _weighted_tail_expected_shortfall(values, weights, tail_mass, upper=False)


def weighted_upper_tail_expected_shortfall(
    values: ArrayLike,
    weights: ArrayLike,
    tail_mass: float = LOWER_TAIL_MASS,
) -> float:
    """Mean of the highest ``tail_mass`` probability, with fractional boundary."""

    return _weighted_tail_expected_shortfall(values, weights, tail_mass, upper=True)


def _normalized_weights(weights: ArrayLike, expected_size: int) -> NDArray[np.float64]:
    mass = np.asarray(weights, dtype=np.float64)
    if mass.ndim != 1 or mass.size != expected_size or not np.all(np.isfinite(mass)) or np.any(mass < 0.0):
        raise RobustGeometryError("FINITE_NONNEGATIVE_ONE_DIMENSIONAL_WEIGHTS_REQUIRED")
    total = float(mass.sum())
    if total <= 0.0 or not math.isfinite(total):
        raise RobustGeometryError("POSITIVE_FINITE_WEIGHT_SUM_REQUIRED")
    return np.asarray(mass / total, dtype=np.float64)


def _weighted_tail_expected_shortfall(
    values: ArrayLike,
    weights: ArrayLike,
    tail_mass: float,
    *,
    upper: bool,
) -> float:
    sample = np.asarray(values, dtype=np.float64)
    if sample.ndim != 1 or sample.size == 0 or not np.all(np.isfinite(sample)):
        raise RobustGeometryError("FINITE_NONEMPTY_ONE_DIMENSIONAL_VALUES_REQUIRED")
    if not 0.0 < tail_mass <= 1.0 or not math.isfinite(tail_mass):
        raise RobustGeometryError("TAIL_MASS_IN_OPEN_CLOSED_UNIT_INTERVAL_REQUIRED")
    mass = _normalized_weights(weights, sample.size)
    order = np.argsort(sample, kind="stable")
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
        raise RobustGeometryError("TAIL_MASS_NOT_FILLED")
    return float(integral / tail_mass)


def evaluation_unit_weights(cell_count: int = 3675, repeats: int = 2) -> NDArray[np.float64]:
    """Return cell-equal, repeat-equal weights in cell-major/repeat-minor order."""

    if cell_count < 1 or repeats < 1:
        raise RobustGeometryError("POSITIVE_CELL_AND_REPEAT_COUNTS_REQUIRED")
    return np.full(cell_count * repeats, 1.0 / (cell_count * repeats), dtype=np.float64)


def summarize_candidate_geometry(
    distances: ArrayLike,
    gram_drift: ArrayLike,
    weights: ArrayLike,
) -> dict[str, object]:
    """Return the frozen candidate summaries from finest-unit compact arrays."""

    pair = np.asarray(distances, dtype=np.float64)
    drift = np.asarray(gram_drift, dtype=np.float64)
    if pair.ndim != 2 or pair.shape[1] != 6 or not np.all(np.isfinite(pair)):
        raise RobustGeometryError("FINITE_UNIT_BY_SIX_DISTANCES_REQUIRED")
    if drift.shape != (pair.shape[0],) or not np.all(np.isfinite(drift)) or np.any(drift < 0.0):
        raise RobustGeometryError("FINITE_NONNEGATIVE_UNIT_DRIFT_REQUIRED")
    mass = _normalized_weights(weights, pair.shape[0])
    minimum = np.min(pair, axis=1)
    weak = weakest_pair_index(pair)
    weakest_mass = [float(mass[weak == index].sum()) for index in range(6)]
    anisotropy = pair_anisotropy(pair)
    return {
        "d_min_lower_tail_es_0p05": weighted_lower_tail_expected_shortfall(minimum, mass),
        "pair_lower_tail_es_0p05": [
            weighted_lower_tail_expected_shortfall(pair[:, index], mass) for index in range(6)
        ],
        "weakest_pair_probability": weakest_mass,
        "pair_anisotropy_mean": float(np.sum(mass * anisotropy)),
        "pair_anisotropy_upper_tail_es_0p05": weighted_upper_tail_expected_shortfall(anisotropy, mass),
        "gram_frobenius_drift_mean": float(np.sum(mass * drift)),
        "gram_frobenius_drift_upper_tail_es_0p05": weighted_upper_tail_expected_shortfall(drift, mass),
        "unit_count": int(pair.shape[0]),
    }


def batch_geometry_from_raw(
    raw: ArrayLike,
    whitener: ArrayLike,
) -> tuple[NDArray[np.float64], NDArray[np.complex128], NDArray[np.complex128]]:
    """Vectorized compact geometry for an E2 raw chunk.

    Input is ``state x cell x repeat x port x frequency``.  Outputs are
    ``distances[cell,repeat,6]``, ``normalized_gram[cell,repeat,4,4]`` and
    ``Y_diff[cell,repeat,832,4]``.  The last output is intended only for the
    deterministic, sparse audit sampler and must not be retained wholesale.
    """

    values = np.asarray(raw, dtype=np.complex128)
    operator = np.asarray(whitener, dtype=np.float64)
    if values.ndim != 5 or values.shape[0] != 4 or values.shape[2:] != (2, 4, 256) or not np.all(np.isfinite(values)):
        raise RobustGeometryError("FINITE_E2_RAW_CHUNK_SHAPE_REQUIRED")
    if operator.shape != (REAL_FEATURE_DIMENSION, REAL_FEATURE_DIMENSION) or not np.all(np.isfinite(operator)):
        raise RobustGeometryError("FINITE_FROZEN_COMMON_W_1664_SQUARE_REQUIRED")
    cells = values.shape[1]
    weights = trapezoidal_weights(frozen_frequency_grid()[:PRIMARY_FREQUENCIES])
    # cell, repeat, frequency, port, state -> cell, repeat, complex feature, state
    ordered = np.transpose(values[:, :, :, :, :PRIMARY_FREQUENCIES], (1, 2, 4, 3, 0))
    weighted = ordered * np.sqrt(weights)[None, None, :, None, None]
    y = weighted.reshape((cells, 2, COMPLEX_FEATURE_DIMENSION, 4), order="C")
    y_diff = np.asarray(y @ projection_matrices(4)[1], dtype=np.complex128)
    embedded = np.concatenate((y_diff.real, y_diff.imag), axis=2)
    columns = np.transpose(embedded, (2, 0, 1, 3)).reshape((REAL_FEATURE_DIMENSION, cells * 2 * 4), order="C")
    z_columns = operator @ columns
    z_real = np.transpose(
        z_columns.reshape((REAL_FEATURE_DIMENSION, cells, 2, 4), order="C"),
        (1, 2, 0, 3),
    )
    z = z_real[:, :, :COMPLEX_FEATURE_DIMENSION] + 1j * z_real[:, :, COMPLEX_FEATURE_DIMENSION:]
    distances = np.empty((cells, 2, 6), dtype=np.float64)
    for pair_index, (left, right) in enumerate(PAIR_COLUMN_INDICES):
        distances[:, :, pair_index] = np.linalg.norm(z[:, :, :, left] - z[:, :, :, right], axis=2)
    grams = np.einsum("urfi,urfj->urij", z.conj(), z, optimize=True)
    grams = 0.5 * (grams + grams.conj().transpose(0, 1, 3, 2))
    trace = np.trace(grams, axis1=2, axis2=3).real
    if np.any(trace <= 0.0) or not np.all(np.isfinite(trace)):
        raise RobustGeometryError("STRICTLY_POSITIVE_FINITE_BATCH_GRAM_TRACE_REQUIRED")
    normalized = grams / trace[:, :, None, None]
    if not np.all(np.isfinite(distances)) or not np.all(np.isfinite(normalized)):
        raise RobustGeometryError("NONFINITE_BATCH_GEOMETRY")
    return distances, np.asarray(normalized, dtype=np.complex128), y_diff


def _family_endpoint_matrix(values_by_family: Mapping[str, ArrayLike]) -> NDArray[np.float64]:
    if set(values_by_family) != set(FAMILY_ORDER):
        raise RobustGeometryError("EXACT_FOUR_FAMILY_KEYS_REQUIRED")
    rows = []
    for family in FAMILY_ORDER:
        values = np.asarray(values_by_family[family], dtype=np.float64)
        if values.shape != (20,) or not np.all(np.isfinite(values)):
            raise RobustGeometryError("EXACT20_FINITE_IDENTITY_VALUES_PER_FAMILY_REQUIRED")
        rows.append(values)
    return np.stack(rows)


def _six_contrasts(means: NDArray[np.float64], *, drift_direction: bool) -> NDArray[np.float64]:
    contrasts = []
    for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)):
        contrasts.append(means[right] - means[left] if drift_direction else means[left] - means[right])
    return np.asarray(contrasts, dtype=np.float64)


def _welch_twelve(
    margin: NDArray[np.float64],
    drift: NDArray[np.float64],
) -> tuple[dict[str, object], NDArray[np.float64] | None]:
    endpoint_records: dict[str, object] = {}
    statistics: list[float] = []
    for name, matrix, drift_direction in (
        ("margin", margin, False),
        ("drift", drift, True),
    ):
        means = np.mean(matrix, axis=1)
        variances = np.var(matrix, axis=1, ddof=1)
        contrasts = _six_contrasts(means, drift_direction=drift_direction)
        standard_errors = []
        for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)):
            standard_errors.append(math.sqrt(float(variances[left] / 20.0 + variances[right] / 20.0)))
        standard_error = np.asarray(standard_errors, dtype=np.float64)
        if np.any(standard_error <= 0.0) or not np.all(np.isfinite(standard_error)):
            endpoint_records[name] = {
                "status": "INCONCLUSIVE",
                "reason": "ZERO_OR_NONFINITE_WELCH_STANDARD_ERROR",
                "contrasts": contrasts,
                "standard_errors": standard_error,
                "statistics": None,
            }
            continue
        endpoint_t = contrasts / standard_error
        if not np.all(np.isfinite(endpoint_t)):
            endpoint_records[name] = {
                "status": "INCONCLUSIVE",
                "reason": "NONFINITE_WELCH_T",
                "contrasts": contrasts,
                "standard_errors": standard_error,
                "statistics": None,
            }
            continue
        endpoint_records[name] = {
            "status": "AVAILABLE",
            "reason": None,
            "contrasts": contrasts,
            "standard_errors": standard_error,
            "statistics": endpoint_t,
        }
        statistics.extend(float(value) for value in endpoint_t)
    if len(statistics) != 12:
        return endpoint_records, None
    return endpoint_records, np.asarray(statistics, dtype=np.float64)


def identity_level_family_inference(
    margin_by_family: Mapping[str, ArrayLike],
    drift_by_family: Mapping[str, ArrayLike],
    *,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
    permutation_replicates: int = PERMUTATION_REPLICATES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    permutation_seed: int = PERMUTATION_SEED,
) -> dict[str, object]:
    """Run the frozen exact20 identity-level bootstrap and 12-stat max-|T| test.

    Margin contrast is ``mean(S_A)-mean(S_B)``.  Drift contrast is
    ``mean(U_B)-mean(U_A)``.  Thus positive values favor family A for both.
    The same within-family bootstrap indices and the same all-80 label
    permutation are applied to the paired margin/drift identity records.
    """

    if bootstrap_replicates < 1 or permutation_replicates < 1:
        raise RobustGeometryError("POSITIVE_INFERENCE_REPLICATE_COUNTS_REQUIRED")
    margin = _family_endpoint_matrix(margin_by_family)
    drift = _family_endpoint_matrix(drift_by_family)
    observed, observed_twelve = _welch_twelve(margin, drift)

    bootstrap_rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    bootstrap_indices = np.stack(
        [bootstrap_rng.integers(0, 20, size=(bootstrap_replicates, 20), endpoint=False) for _ in FAMILY_ORDER]
    )
    margin_means = np.stack(
        [np.mean(margin[family][bootstrap_indices[family]], axis=1) for family in range(4)], axis=1
    )
    drift_means = np.stack(
        [np.mean(drift[family][bootstrap_indices[family]], axis=1) for family in range(4)], axis=1
    )
    margin_bootstrap = np.stack(
        [
            margin_means[:, left] - margin_means[:, right]
            for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
        ],
        axis=1,
    )
    drift_bootstrap = np.stack(
        [
            drift_means[:, right] - drift_means[:, left]
            for left, right in ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
        ],
        axis=1,
    )
    margin_ci = np.quantile(margin_bootstrap, (0.025, 0.975), axis=0, method="linear").T
    drift_ci = np.quantile(drift_bootstrap, (0.025, 0.975), axis=0, method="linear").T

    if observed_twelve is None:
        return {
            "status": "INCONCLUSIVE",
            "reason": "AT_LEAST_ONE_ENDPOINT_WELCH_DENOMINATOR_UNAVAILABLE",
            "observed": observed,
            "bootstrap": {
                "replicates": bootstrap_replicates,
                "seed": bootstrap_seed,
                "generator": "PCG64",
                "quantile_method": "linear",
                "margin_contrasts": margin_bootstrap,
                "drift_contrasts": drift_bootstrap,
                "margin_percentile_95_ci": margin_ci,
                "drift_percentile_95_ci": drift_ci,
            },
            "permutation": None,
        }

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
            return {
                "status": "INCONCLUSIVE",
                "reason": "PERMUTED_ZERO_OR_NONFINITE_WELCH_DENOMINATOR",
                "observed": observed,
                "bootstrap": {
                    "replicates": bootstrap_replicates,
                    "seed": bootstrap_seed,
                    "generator": "PCG64",
                    "quantile_method": "linear",
                    "margin_contrasts": margin_bootstrap,
                    "drift_contrasts": drift_bootstrap,
                    "margin_percentile_95_ci": margin_ci,
                    "drift_percentile_95_ci": drift_ci,
                },
                "permutation": None,
            }
        maxima[replicate] = float(np.max(np.abs(statistics)))
    adjusted = np.asarray(
        [
            (1.0 + float(np.count_nonzero(maxima >= abs(observed_value))))
            / float(permutation_replicates + 1)
            for observed_value in observed_twelve
        ],
        dtype=np.float64,
    )
    return {
        "status": "AVAILABLE",
        "reason": None,
        "observed": observed,
        "bootstrap": {
            "replicates": bootstrap_replicates,
            "seed": bootstrap_seed,
            "generator": "PCG64",
            "quantile_method": "linear",
            "margin_contrasts": margin_bootstrap,
            "drift_contrasts": drift_bootstrap,
            "margin_percentile_95_ci": margin_ci,
            "drift_percentile_95_ci": drift_ci,
        },
        "permutation": {
            "replicates": permutation_replicates,
            "seed": permutation_seed,
            "generator": "PCG64",
            "observed_twelve": observed_twelve,
            "max_abs_t": maxima,
            "adjusted_p": adjusted,
            "adjusted_p_formula_denominator": permutation_replicates + 1,
            "statistic_count": 12,
        },
    }

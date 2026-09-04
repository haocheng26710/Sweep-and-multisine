"""Frozen GEN-ENC-1 stable-rank estimator for deterministic fixtures.

This module has no data-loading entry point.  In particular, ``fit_whitener``
accepts only train and development cells, so validation cannot participate in
the covariance estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray


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
    source_partitions: tuple[str, ...] = ("train", "development")


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
    if grid.ndim != 1 or grid.size < 2 or not np.all(np.isfinite(grid)):
        raise ValueError("frequency grid must contain at least two finite points")
    delta = np.diff(grid)
    if np.any(delta <= 0):
        raise ValueError("frequency grid must be strictly increasing")
    weights = np.empty_like(grid)
    weights[0] = delta[0] / 2.0
    weights[-1] = delta[-1] / 2.0
    if grid.size > 2:
        weights[1:-1] = (delta[:-1] + delta[1:]) / 2.0
    return weights / weights.sum()


def embed_complex_responses(responses: ArrayLike, frequency_weights: ArrayLike) -> NDArray[np.float64]:
    """Embed weighted complex responses as [Re features; Im features].

    The first axis is frequency and the last axis is state.  All intervening
    axes retain C-order (port then sensor under the frozen caller schema).
    """

    values = np.asarray(responses, dtype=np.complex128)
    weights = np.asarray(frequency_weights, dtype=float)
    if values.ndim < 2 or values.shape[0] != weights.size:
        raise ValueError("responses must have frequency first and state last")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(weights)):
        raise ValueError("responses and weights must be finite")
    if np.any(weights < 0) or not np.isclose(weights.sum(), 1.0):
        raise ValueError("frequency weights must be nonnegative and sum to one")
    scale_shape = (weights.size,) + (1,) * (values.ndim - 1)
    weighted = values * np.sqrt(weights).reshape(scale_shape)
    flattened = weighted.reshape((-1, values.shape[-1]), order="C")
    return np.concatenate((flattened.real, flattened.imag), axis=0)


def projection_matrices(state_count: int = 4) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if state_count < 1:
        raise ValueError("state_count must be positive")
    shared = np.ones((state_count, state_count), dtype=float) / state_count
    return shared, np.eye(state_count, dtype=float) - shared


def project_modes(y: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    values = np.asarray(y, dtype=float)
    if values.ndim != 2 or not np.all(np.isfinite(values)):
        raise ValueError("Y must be a finite feature-by-state matrix")
    shared, differential = projection_matrices(values.shape[1])
    return values @ shared, values @ differential


def _cell_residual_rows(repeats: ArrayLike) -> NDArray[np.float64]:
    values = np.asarray(repeats, dtype=float)
    if values.ndim != 3 or values.shape[0] < 2 or values.shape[2] != 4:
        raise ValueError("each cell must be repeats-by-features-by-four-states with at least two repeats")
    if not np.all(np.isfinite(values)):
        raise ValueError("residual input contains nonfinite values")
    differential = projection_matrices(4)[1]
    projected = values @ differential
    residual = projected - projected.mean(axis=0, keepdims=True)
    return residual.transpose(0, 2, 1).reshape((-1, values.shape[1]))


def _oas(empirical: NDArray[np.float64], effective_n: float) -> tuple[NDArray[np.float64], float]:
    dimension = empirical.shape[0]
    trace = float(np.trace(empirical))
    tau = trace / dimension
    alpha = float(np.mean(empirical**2))
    denominator = (effective_n + 1.0) * (alpha - (tau**2) / dimension)
    if denominator <= 0.0:
        shrinkage = 1.0
    else:
        shrinkage = min((alpha + tau**2) / denominator, 1.0)
    shrunk = (1.0 - shrinkage) * empirical + shrinkage * tau * np.eye(dimension)
    return shrunk, float(shrinkage)


def fit_whitener(
    train_cells: Mapping[str, ArrayLike],
    development_cells: Mapping[str, ArrayLike],
    required_cells: Sequence[str],
) -> WhitenerResult:
    """Fit the common whitener from train/development cells only.

    Each required nuisance cell receives equal total covariance weight; rows
    within a cell receive equal weight.  There is intentionally no validation
    argument.
    """

    required = tuple(required_cells)
    if not required or len(set(required)) != len(required):
        return WhitenerResult("UNAVAILABLE", "INVALID_REQUIRED_CELL_IDENTITY", None, None, None, None, None, None)
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
        return WhitenerResult("UNAVAILABLE", f"RESIDUAL_INPUT:{exc}", None, None, None, None, None, None)
    dimensions = {rows.shape[1] for rows in rows_by_cell}
    if len(dimensions) != 1:
        return WhitenerResult("UNAVAILABLE", "FEATURE_IDENTITY_MISMATCH", None, None, None, None, None, None)
    cell_count = len(rows_by_cell)
    covariance = np.zeros((next(iter(dimensions)), next(iter(dimensions))), dtype=float)
    squared_weight_sum = 0.0
    for rows in rows_by_cell:
        row_weight = 1.0 / (cell_count * rows.shape[0])
        covariance += (rows.T @ rows) / (cell_count * rows.shape[0])
        squared_weight_sum += rows.shape[0] * row_weight**2
    effective_n = 1.0 / squared_weight_sum
    if not np.all(np.isfinite(covariance)) or effective_n < 2.0:
        return WhitenerResult("UNAVAILABLE", "COVARIANCE_UNAVAILABLE", None, covariance, None, None, None, effective_n)
    shrunk, shrinkage = _oas(covariance, effective_n)
    try:
        eigenvalues, eigenvectors = np.linalg.eigh(shrunk)
    except np.linalg.LinAlgError as exc:
        return WhitenerResult("UNAVAILABLE", f"EIGENDECOMPOSITION:{exc}", None, covariance, shrunk, None, None, effective_n)
    lambda_max = float(eigenvalues[-1])
    if not np.isfinite(lambda_max) or lambda_max <= 0.0:
        return WhitenerResult("UNAVAILABLE", "NONPOSITIVE_COVARIANCE", None, covariance, shrunk, shrinkage, None, effective_n)
    floor = float(np.finfo(float).eps * shrunk.shape[0] * lambda_max)
    floored = np.maximum(eigenvalues, floor)
    operator = (eigenvectors * floored**-0.5) @ eigenvectors.T
    if not np.all(np.isfinite(operator)):
        return WhitenerResult("UNAVAILABLE", "WHITENER_NONFINITE", None, covariance, shrunk, shrinkage, floor, effective_n)
    return WhitenerResult("AVAILABLE", None, operator, covariance, shrunk, shrinkage, floor, effective_n)


def weighted_empirical_quantile(values: ArrayLike, weights: ArrayLike, quantile: float = 0.05) -> float:
    """Weighted inverse empirical CDF with no interpolation."""

    sample = np.asarray(values, dtype=float)
    mass = np.asarray(weights, dtype=float)
    if sample.ndim != 1 or mass.shape != sample.shape or sample.size == 0:
        raise ValueError("values and weights must be nonempty one-dimensional arrays of equal shape")
    if not np.all(np.isfinite(sample)) or not np.all(np.isfinite(mass)) or np.any(mass < 0):
        raise ValueError("values and weights must be finite with nonnegative weights")
    if not 0.0 < quantile <= 1.0 or mass.sum() <= 0.0:
        raise ValueError("quantile and weights are not normalizable")
    order = np.argsort(sample, kind="stable")
    cumulative = np.cumsum(mass[order] / mass.sum())
    index = min(int(np.searchsorted(cumulative, quantile, side="left")), sample.size - 1)
    return float(sample[order[index]])


def _unavailable(reason: str, cells: int = 0, units: int = 0) -> CandidateResult:
    return CandidateResult("CANDIDATE", "UNAVAILABLE", "NOT_TESTED", reason, None, None, (), units, cells, None)


def evaluate_candidate(
    units_by_cell: Mapping[str, Sequence[ArrayLike]],
    required_cells: Sequence[str],
    whitener: WhitenerResult,
) -> CandidateResult:
    """Evaluate one frozen candidate; this function does not aggregate families."""

    required = tuple(required_cells)
    if whitener.status != "AVAILABLE" or whitener.operator is None:
        return _unavailable("W_UNAVAILABLE")
    if not required or any(cell not in units_by_cell for cell in required):
        return _unavailable("MISSING_PREREGISTERED_NUISANCE_CELL")
    singular_values: list[NDArray[np.float64]] = []
    weights: list[float] = []
    try:
        for cell in required:
            units = units_by_cell[cell]
            if not units:
                return _unavailable("INCOMPLETE_NUISANCE_CELL", len(required), len(singular_values))
            cell_weight = 1.0 / len(required)
            for unit in units:
                y = np.asarray(unit, dtype=float)
                if y.ndim != 2 or y.shape[1] != 4 or y.shape[0] != whitener.operator.shape[1]:
                    return _unavailable("FEATURE_OR_STATE_IDENTITY_MISMATCH", len(required), len(singular_values))
                if not np.all(np.isfinite(y)):
                    return _unavailable("NONFINITE_EVALUATION_UNIT", len(required), len(singular_values))
                differential = y @ projection_matrices(4)[1]
                sv = np.linalg.svd(whitener.operator @ differential, compute_uv=False)
                if sv.size < 3 or not np.all(np.isfinite(sv)):
                    return _unavailable("THIRD_SINGULAR_VALUE_UNAVAILABLE", len(required), len(singular_values))
                singular_values.append(sv)
                weights.append(cell_weight / len(units))
    except np.linalg.LinAlgError as exc:
        return _unavailable(f"SVD_UNAVAILABLE:{exc}", len(required), len(singular_values))
    width = min(sv.size for sv in singular_values)
    quantiles = tuple(
        weighted_empirical_quantile([sv[index] for sv in singular_values], weights, 0.05) for index in range(width)
    )
    stable_rank = sum(value > 1.0 for value in quantiles)
    primary = quantiles[2]
    passed = primary > 1.0 and stable_rank == 3
    equal_unit_weights = np.allclose(weights, np.full(len(weights), 1.0 / len(weights)))
    disclosure = None
    if len(weights) < 20 and equal_unit_weights:
        disclosure = "CONSERVATIVE_AND_SINGLE_UNIT_DOMINATED_Q_0.05_EQUALS_MINIMUM"
    return CandidateResult(
        "CANDIDATE",
        "PASS",
        "PASS" if passed else "NEGATIVE",
        None,
        primary,
        stable_rank,
        quantiles,
        len(singular_values),
        len(required),
        disclosure,
    )

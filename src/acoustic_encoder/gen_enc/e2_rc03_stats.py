"""Frozen RC03 sufficient-stat and deterministic reconstruction primitives."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from numpy.typing import NDArray

from .estimator import embed_complex_responses, projection_matrices, trapezoidal_weights
from .forward_acoustic_network import frozen_frequency_grid


FEATURE_DIMENSION = 1664
PRIMARY_FREQUENCIES = 208
GLOBAL_W_ROWS = 2_352_000
ENDPOINT_COLUMNS = ("sigma1", "sigma2", "sigma3", "gt1_sigma1", "gt1_sigma2", "gt1_sigma3")
BRIDGE_COLUMNS = ("response_angle", "derivative_inner", "differential_margin", "next_chord", "held_out_required", "finite")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_npy_atomic(path: Path, value: NDArray[np.generic]) -> dict[str, Any]:
    array = np.ascontiguousarray(value)
    if array.dtype not in (np.dtype("float64"), np.dtype("uint64"), np.dtype("uint8")) or not np.all(np.isfinite(array)):
        raise ValueError("FINITE_FLOAT64_UINT64_OR_UINT8_REQUIRED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as stream:
        np.lib.format.write_array(stream, array, version=(1, 0), allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return {"path": path.as_posix(), "sha256": sha256_file(path), "shape": list(array.shape), "dtype": array.dtype.name, "format": "NPY_1_0", "order": "C", "payload_bytes": int(array.nbytes)}


def _cardinal_indices(angle_count: int) -> tuple[int, int, int, int]:
    if angle_count == 4:
        return (0, 1, 2, 3)
    if angle_count == 24:
        return (0, 6, 12, 18)
    raise ValueError("FROZEN_4_OR_24_ANGLE_COUNT_REQUIRED")


def feature_matrix(response: NDArray[np.complex128], angle_indices: Iterable[int]) -> NDArray[np.float64]:
    """Map angle x port x frequency response to 1664-feature x state Y."""

    values = np.asarray(response, dtype=np.complex128)
    indices = tuple(angle_indices)
    selected = values[np.asarray(indices), :, :PRIMARY_FREQUENCIES]
    frequency_first = np.transpose(selected, (2, 1, 0))
    weights = trapezoidal_weights(frozen_frequency_grid()[:PRIMARY_FREQUENCIES])
    embedded = embed_complex_responses(frequency_first, weights)
    if embedded.shape != (FEATURE_DIMENSION, len(indices)):
        raise ValueError("FEATURE_SHAPE_MISMATCH")
    return embedded


def common_w_chunk_roles(raw: NDArray[np.complex128]) -> dict[str, NDArray[np.generic]]:
    values = np.asarray(raw, dtype=np.complex128)
    if values.ndim != 5 or values.shape[0] != 4 or values.shape[2:] != (2, 4, 256) or not np.all(np.isfinite(values)):
        raise ValueError("DEVELOPMENT_RAW_SHAPE_REQUIRED")
    cells = values.shape[1]
    residual = np.empty((cells, 2, 4, FEATURE_DIMENSION), dtype=np.float64)
    pdiff = projection_matrices(4)[1]
    for cell in range(cells):
        y = np.stack([feature_matrix(values[:, cell, repeat], range(4)) for repeat in range(2)], axis=0)
        projected = y @ pdiff
        block = projected - projected.mean(axis=0, keepdims=True)
        residual[cell] = np.transpose(block, (0, 2, 1))
    rows = residual.reshape((-1, FEATURE_DIMENSION))
    weight = 1.0 / GLOBAL_W_ROWS
    return {
        "WITHIN_CELL_RESIDUAL_BLOCK": residual,
        "W_WEIGHTED_OUTER_SUM": np.asarray((rows.T @ rows) * weight, dtype=np.float64),
        "W_WEIGHT_SUM": np.asarray([rows.shape[0] * weight], dtype=np.float64),
    }


def oas_whitener_from_accumulator(covariance: NDArray[np.float64], weight_sum: float) -> dict[str, Any]:
    empirical = np.asarray(covariance, dtype=np.float64)
    if empirical.shape[0] != empirical.shape[1] or empirical.shape[0] < 2 or not np.all(np.isfinite(empirical)):
        raise ValueError("FINITE_SQUARE_COVARIANCE_REQUIRED")
    if not np.isclose(weight_sum, 1.0, rtol=0.0, atol=2e-12):
        raise ValueError("COMMON_W_TOTAL_WEIGHT_NOT_ONE")
    dimension = empirical.shape[0]
    trace = float(np.trace(empirical))
    tau = trace / dimension
    alpha = float(np.mean(empirical**2))
    denominator = (GLOBAL_W_ROWS + 1.0) * (alpha - tau**2 / dimension)
    shrinkage = 1.0 if denominator <= 0.0 else min((alpha + tau**2) / denominator, 1.0)
    shrunk = (1.0 - shrinkage) * empirical + shrinkage * tau * np.eye(dimension)
    eigenvalues, eigenvectors = np.linalg.eigh(shrunk)
    maximum = float(eigenvalues[-1])
    if maximum <= 0.0:
        raise ValueError("COMMON_W_NONPOSITIVE")
    floor = float(np.finfo(float).eps * dimension * maximum)
    operator = (eigenvectors * np.maximum(eigenvalues, floor) ** -0.5) @ eigenvectors.T
    if not np.all(np.isfinite(operator)):
        raise ValueError("COMMON_W_NONFINITE")
    return {"operator": operator, "empirical": empirical, "shrunk": shrunk, "shrinkage": shrinkage, "eigenvalue_floor": floor, "effective_n": float(GLOBAL_W_ROWS)}


def _bridge_units(z: NDArray[np.float64]) -> NDArray[np.float64]:
    if z.shape[1] != 24:
        raise ValueError("BRIDGE_REQUIRES_24_ANGLES")
    angles = np.deg2rad(np.arange(0.0, 360.0, 15.0))
    a = np.sum(z * np.cos(angles)[None, :], axis=1)
    b = np.sum(z * np.sin(angles)[None, :], axis=1)
    gram = np.asarray([[a @ a, a @ b], [b @ a, b @ b]], dtype=np.float64)
    coordinates = np.linalg.solve(gram, np.vstack((a @ z, b @ z)))
    response_angle = np.arctan2(coordinates[1], coordinates[0])
    step = np.deg2rad(15.0)
    derivative = (np.roll(z, -1, axis=1) - np.roll(z, 1, axis=1)) / (2.0 * step)
    tangent = -a[:, None] * np.sin(angles)[None, :] + b[:, None] * np.cos(angles)[None, :]
    derivative_inner = np.sum(derivative * tangent, axis=0)
    margin = np.linalg.norm(z - z.mean(axis=1, keepdims=True), axis=0)
    chord = np.linalg.norm(np.roll(z, -1, axis=1) - z, axis=0)
    held = np.isin(np.arange(24), np.asarray([3, 9, 15, 21])).astype(np.float64)
    finite = np.isfinite(response_angle + derivative_inner + margin + chord).astype(np.float64)
    return np.stack((response_angle, derivative_inner, margin, chord, held, finite), axis=1)


def metric_chunk_roles(
    raw: NDArray[np.complex128], reference_raw_pre_noise: NDArray[np.complex128], whitener: NDArray[np.float64],
    *, cell_start: int, candidate_raw_pre_noise: NDArray[np.complex128] | None = None,
    matched_cost_inputs: NDArray[np.float64] | None = None,
) -> dict[str, NDArray[np.generic]]:
    values = np.asarray(raw, dtype=np.complex128)
    reference = np.asarray(reference_raw_pre_noise, dtype=np.complex128)
    throughput_source = values if candidate_raw_pre_noise is None else np.asarray(candidate_raw_pre_noise, dtype=np.complex128)
    w = np.asarray(whitener, dtype=np.float64)
    if values.shape != reference.shape or throughput_source.shape != values.shape or values.ndim != 5 or values.shape[2:] != (2, 4, 256):
        raise ValueError("METRIC_RAW_SHAPE_MISMATCH")
    if w.shape != (FEATURE_DIMENSION, FEATURE_DIMENSION) or not np.all(np.isfinite(w)):
        raise ValueError("SEALED_COMMON_W_SHAPE_REQUIRED")
    angles, cells = values.shape[:2]
    cardinal = _cardinal_indices(angles)
    components = np.empty((cells, 2, 2, 4, 4), dtype=np.float64)
    endpoint = np.empty((cells, 2, 6), dtype=np.float64)
    bridge = np.empty((cells, 2, 24, 6), dtype=np.float64) if angles == 24 else np.empty((cells, 2, 0, 6), dtype=np.float64)
    heldout = np.empty((cells, 2, 4, 4), dtype=np.float64) if angles == 24 else np.empty((cells, 2, 0, 4), dtype=np.float64)
    keys = np.empty((cells, 2, 4), dtype=np.uint64)
    pdiff = projection_matrices(4)[1]
    pshared = projection_matrices(4)[0]
    for cell in range(cells):
        for repeat in range(2):
            y = feature_matrix(values[:, cell, repeat], cardinal)
            shared = w @ (y @ pshared)
            differential = w @ (y @ pdiff)
            components[cell, repeat, 0] = shared.T @ shared
            components[cell, repeat, 1] = differential.T @ differential
            singular = np.linalg.svd(differential, compute_uv=False)[:3]
            endpoint[cell, repeat] = np.concatenate((singular, (singular > 1.0).astype(np.float64)))
            keys[cell, repeat] = np.asarray([cell_start + cell, repeat, 0, 0], dtype=np.uint64)
            if angles == 24:
                y24 = feature_matrix(values[:, cell, repeat], range(24))
                z24 = w @ (y24 - y24.mean(axis=1, keepdims=True))
                bridge[cell, repeat] = _bridge_units(z24)
                heldout[cell, repeat] = bridge[cell, repeat, [3, 9, 15, 21]][:, [1, 2, 3, 5]]
    numerator = np.sum(np.abs(throughput_source) ** 2, axis=3, dtype=np.float64)
    denominator = np.sum(np.abs(reference) ** 2, axis=3, dtype=np.float64)
    availability = np.packbits(
        (np.isfinite(numerator) & np.isfinite(denominator) & (denominator > 0.0)).reshape(-1),
        bitorder="little",
    ).astype(np.uint8)
    matched_vector = np.ones(4, dtype=np.float64) if matched_cost_inputs is None else np.asarray(matched_cost_inputs, dtype=np.float64)
    if matched_vector.shape != (4,) or not np.all(np.isfinite(matched_vector)):
        raise ValueError("MATCHED_COST_INPUT_VECTOR_REQUIRED")
    matched = np.broadcast_to(matched_vector, (cells, 2, 4)).copy()
    terminal_inputs = np.concatenate((endpoint, np.min(endpoint, axis=(0, 1), keepdims=True).repeat(cells, 0).repeat(2, 1)), axis=2)
    return {
        "SHARED_DIFFERENTIAL_COMPONENTS": components,
        "ENDPOINT_UNIT_VALUES": endpoint,
        "THROUGHPUT_NUMERATOR_256": numerator,
        "THROUGHPUT_REFERENCE_DENOMINATOR_256": denominator,
        "THROUGHPUT_AVAILABILITY_256": availability,
        "BRIDGE_24_UNIT_VALUES": bridge,
        "HELD_OUT_4_UNIT_VALUES": heldout,
        "MATCHED_COST_ELIGIBILITY_INPUTS": matched,
        "BOOTSTRAP_PERMUTATION_UNCERTAINTY_UNIT_VALUES": endpoint.copy(),
        "RESAMPLING_UNIT_KEYS": keys,
        "CANDIDATE_FAMILY_GLOBAL_TERMINAL_INPUTS": terminal_inputs,
    }


def reconstruct_candidate(endpoint_chunks: Iterable[NDArray[np.float64]]) -> dict[str, Any]:
    values = np.concatenate([np.asarray(chunk, dtype=np.float64).reshape((-1, 6)) for chunk in endpoint_chunks], axis=0)
    if values.shape[0] != 7350 or not np.all(np.isfinite(values)):
        raise ValueError("EXACT_7350_ENDPOINT_UNITS_REQUIRED")
    ordered = np.sort(values[:, :3], axis=0, kind="stable")
    index = int(np.ceil(0.05 * ordered.shape[0]) - 1)
    quantiles = ordered[index]
    stable_rank = int(np.sum(quantiles > 1.0))
    return {"E_primary": float(quantiles[2]), "r_stable": stable_rank, "sigma_quantiles": quantiles.tolist(),
            "scientific_status": "PASS" if quantiles[2] > 1.0 and stable_rank == 3 else "NEGATIVE", "unit_count": int(values.shape[0])}

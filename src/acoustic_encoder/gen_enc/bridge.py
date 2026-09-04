"""Frozen 15-degree sampled bridge metrics for deterministic fixtures only."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


FROZEN_ANGLES_DEGREES = np.arange(0.0, 360.0, 15.0)
MANDATORY_HELD_OUT_DEGREES = (45.0, 135.0, 225.0, 315.0)


@dataclass(frozen=True)
class BridgeResult:
    technical_status: str
    scientific_status: str
    reason: str | None
    angular_order_pass: bool | None
    derivative_orientation_pass: bool | None
    differential_margin_pass: bool | None
    circular_continuity_pass: bool | None
    mandatory_held_out_pass: bool | None
    sampled_grid_step_degrees: float = 15.0
    mathematical_continuum_proof: bool = False
    physical_entity_generalization: bool = False


def _unavailable(reason: str) -> BridgeResult:
    return BridgeResult("UNAVAILABLE", "NOT_TESTED", reason, None, None, None, None, None)


def evaluate_sampled_bridge(z_theta: ArrayLike, angles_degrees: ArrayLike = FROZEN_ANGLES_DEGREES) -> BridgeResult:
    """Evaluate the preregistered 24-point sampled bridge.

    ``z_theta`` is features-by-angle and is already whitened.  The calculation
    is an implementation test, not evidence of performance or continuity over
    a mathematical continuum.
    """

    z = np.asarray(z_theta, dtype=float)
    angles = np.asarray(angles_degrees, dtype=float)
    if z.ndim != 2 or angles.ndim != 1 or z.shape[1] != angles.size:
        return _unavailable("ANGLE_OR_FEATURE_SHAPE_MISMATCH")
    if angles.shape != FROZEN_ANGLES_DEGREES.shape or not np.array_equal(angles, FROZEN_ANGLES_DEGREES):
        return _unavailable("FROZEN_15_DEGREE_GRID_REQUIRED")
    if not np.all(np.isfinite(z)):
        return _unavailable("NONFINITE_RESPONSE")
    radians = np.deg2rad(angles)
    a = np.sum(z * np.cos(radians)[None, :], axis=1)
    b = np.sum(z * np.sin(radians)[None, :], axis=1)
    gram = np.array([[a @ a, a @ b], [b @ a, b @ b]], dtype=float)
    if np.linalg.matrix_rank(gram) < 2:
        return _unavailable("GRAM_A_B_NOT_INVERTIBLE")
    coordinates = np.linalg.solve(gram, np.vstack((a @ z, b @ z)))
    response_angles = np.arctan2(coordinates[1], coordinates[0])
    unwrapped = np.unwrap(response_angles)
    increments = np.diff(np.concatenate((unwrapped, [unwrapped[0] + 2.0 * np.pi])))
    angular_pass = bool(np.all((increments > 0.0) & (increments < np.pi)))

    step = np.deg2rad(15.0)
    centered_difference = (np.roll(z, -1, axis=1) - np.roll(z, 1, axis=1)) / (2.0 * step)
    tangent = -a[:, None] * np.sin(radians)[None, :] + b[:, None] * np.cos(radians)[None, :]
    derivative_inner = np.sum(centered_difference * tangent, axis=0)
    derivative_pass = bool(np.all(derivative_inner > 0.0))

    centered = z - z.mean(axis=1, keepdims=True)
    margins = np.linalg.norm(centered, axis=0)
    margin_pass = bool(np.all(margins > 1.0))

    chord = np.linalg.norm(np.roll(z, -1, axis=1) - z, axis=0)
    continuity_pass = bool(chord[-1] <= np.max(chord[:-1]))
    held_indices = [int(angle / 15.0) for angle in MANDATORY_HELD_OUT_DEGREES]
    held_out_pass = bool(
        angular_pass
        and np.all(derivative_inner[held_indices] > 0.0)
        and np.all(margins[held_indices] > 1.0)
        and continuity_pass
    )
    passed = angular_pass and derivative_pass and margin_pass and continuity_pass and held_out_pass
    return BridgeResult(
        "PASS",
        "PASS" if passed else "BRIDGE_FAIL",
        None,
        angular_pass,
        derivative_pass,
        margin_pass,
        continuity_pass,
        held_out_pass,
    )

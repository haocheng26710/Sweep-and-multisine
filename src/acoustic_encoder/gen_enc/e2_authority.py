"""Top-level-authorized GEN-ENC-2 E2 angle, seed, and common-W rules."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from numpy.typing import NDArray


PORT_ANGLES_DEGREES = (0.0, 90.0, 180.0, 270.0)
DEVELOPMENT_ANGLES_DEGREES = PORT_ANGLES_DEGREES
VALIDATION_ANGLES_DEGREES = tuple(float(value) for value in range(0, 360, 15))
DEVELOPMENT_REPEAT_SEEDS = (2026091001, 2026091002)
SINGLE_USE_VALIDATION_REPEAT_SEEDS = (2026092001, 2026092002)
PARTITION_REPEAT_SEEDS = {
    "development": DEVELOPMENT_REPEAT_SEEDS,
    "single_use_validation": SINGLE_USE_VALIDATION_REPEAT_SEEDS,
}
SUBSTREAM_K_REGISTRY = {
    "independent_manufacturing_by_port": (0, 1, 2, 3),
    "reserved": (4, 5, 6, 7),
    "additive_sensor_noise_start": 8,
}


class E2AuthorityError(ValueError):
    """Fail-closed authority-rule violation."""


def resolve_partition_repeat_seeds(partition: str, repeat_seeds: Sequence[int]) -> tuple[int, int]:
    """Require the exact immutable two-seed tuple for the named partition."""

    if partition not in PARTITION_REPEAT_SEEDS:
        raise E2AuthorityError("UNKNOWN_E2_PARTITION")
    if isinstance(repeat_seeds, (str, bytes)):
        raise E2AuthorityError("REPEAT_SEED_TUPLE_REQUIRED")
    observed = tuple(repeat_seeds)
    expected = PARTITION_REPEAT_SEEDS[partition]
    if observed != expected:
        raise E2AuthorityError("PARTITION_REPEAT_SEED_TUPLE_MISMATCH")
    return expected


def validate_frozen_angles(partition: str, angles_degrees: Sequence[float]) -> tuple[float, ...]:
    """Validate a nonempty canonical-order subset of a partition's frozen angles."""

    if partition not in PARTITION_REPEAT_SEEDS:
        raise E2AuthorityError("UNKNOWN_E2_PARTITION")
    allowed = DEVELOPMENT_ANGLES_DEGREES if partition == "development" else VALIDATION_ANGLES_DEGREES
    angles = tuple(float(value) for value in angles_degrees)
    if not angles or any(not math.isfinite(value) for value in angles):
        raise E2AuthorityError("FINITE_FROZEN_ANGLE_SUBSET_REQUIRED")
    indices: list[int] = []
    for value in angles:
        try:
            indices.append(allowed.index(value))
        except ValueError as exc:
            raise E2AuthorityError("ANGLE_OUTSIDE_FROZEN_PARTITION_GRID") from exc
    if indices != sorted(set(indices)):
        raise E2AuthorityError("FROZEN_ANGLE_CANONICAL_ORDER_REQUIRED")
    return angles


def angle_global_ordinal(partition: str, angle_degrees: float) -> int:
    if partition not in PARTITION_REPEAT_SEEDS:
        raise E2AuthorityError("UNKNOWN_E2_PARTITION")
    allowed = DEVELOPMENT_ANGLES_DEGREES if partition == "development" else VALIDATION_ANGLES_DEGREES
    try:
        return allowed.index(float(angle_degrees))
    except ValueError as exc:
        raise E2AuthorityError("ANGLE_OUTSIDE_FROZEN_PARTITION_GRID") from exc


def directional_port_weights(angle_degrees: float, angle_offset_degrees: float) -> NDArray[np.float64]:
    """Return the L2-normalized, common-zero-phase angle-to-port vector."""

    theta = float(angle_degrees)
    offset = float(angle_offset_degrees)
    if not math.isfinite(theta) or not math.isfinite(offset):
        raise E2AuthorityError("FINITE_ANGLE_AND_OFFSET_REQUIRED")
    theta_effective = (theta + offset) % 360.0
    radians = np.deg2rad(theta_effective - np.asarray(PORT_ANGLES_DEGREES, dtype=np.float64))
    raw = np.maximum(0.0, np.cos(radians))
    raw[np.abs(raw) < 1e-15] = 0.0
    norm = float(np.linalg.norm(raw, ord=2))
    if not math.isfinite(norm) or norm <= 0.0:
        raise E2AuthorityError("ANGLE_TO_PORT_VECTOR_UNAVAILABLE")
    weights = raw / norm
    weights[np.abs(weights) < 1e-15] = 0.0
    return weights


def common_w_weight_audit(
    *, families: int = 4, members_per_family: int = 20, cells: int = 3675,
    repeats: int = 2, states: int = 4, primary_features: int = 1664,
) -> dict[str, int | float]:
    """Audit the exact development-only common-W residual-row measure."""

    expected = (4, 20, 3675, 2, 4, 1664)
    observed = (families, members_per_family, cells, repeats, states, primary_features)
    if observed != expected:
        raise E2AuthorityError("COMMON_W_EXPECTED_DIMENSIONS_MISMATCH")
    residual_rows_per_member_cell = repeats * states
    total_residual_rows = families * members_per_family * cells * residual_rows_per_member_cell
    row_mass = 1.0 / float(total_residual_rows)
    return {
        "families": families,
        "members": families * members_per_family,
        "cells_per_member": cells,
        "residual_rows_per_member_cell": residual_rows_per_member_cell,
        "total_residual_rows": total_residual_rows,
        "primary_feature_dimension": primary_features,
        "family_mass": 1.0 / families,
        "member_mass_within_family": 1.0 / members_per_family,
        "global_member_mass": 1.0 / (families * members_per_family),
        "cell_mass_within_member": 1.0 / cells,
        "row_mass_within_member_cell": 1.0 / residual_rows_per_member_cell,
        "global_residual_row_mass": row_mass,
        "total_mass": row_mass * total_residual_rows,
    }

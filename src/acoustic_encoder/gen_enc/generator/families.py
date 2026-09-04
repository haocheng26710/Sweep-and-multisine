"""RANDOM and PHYSICS technical parameter algorithms."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .prng import GOLDEN_GAMMA, MASK64, open_interval_uniform53, splitmix64

TECHNICAL_LABEL = "TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY"
RANDOM_PARAMETER_ORDER = (
    "q0",
    "q90",
    "q180",
    "edge_0_90",
    "edge_0_180",
    "edge_0_270",
    "edge_90_180",
    "edge_90_270",
    "edge_180_270",
    "loss_0",
    "loss_90",
    "loss_180",
    "loss_270",
)
PHYSICS_PARAMETER_ORDER = (
    "q0",
    "q90",
    "q180",
    "external_0",
    "external_90",
    "external_180",
    "external_270",
    "ring_0_90",
    "ring_90_180",
    "ring_180_270",
    "ring_270_0",
    "loss_0",
    "loss_90",
    "loss_180",
    "loss_270",
)


def _require_order(spec: Mapping[str, Any], expected: Sequence[str]) -> None:
    if tuple(spec.get("parameter_order", ())) != tuple(expected):
        raise ValueError("parameter order does not match the frozen contract")


def _random_inverse_cdf(index: int, u: float) -> float:
    if index < 3:
        return -0.12 + 0.24 * u
    if index < 9:
        return 0.0 if u < 0.5 else 0.2 + 0.6 * (2.0 * u - 1.0)
    return 0.02 + 0.06 * u


def random_parameters(member_seed: int, frozen_parameter_spec: Mapping[str, Any]) -> dict[str, Any]:
    """Generate one labelled technical RANDOM parameter record exactly once."""

    _require_order(frozen_parameter_spec, RANDOM_PARAMETER_ORDER)
    words: list[int] = []
    uniforms: list[float] = []
    values: list[float] = []
    for index in range(len(RANDOM_PARAMETER_ORDER)):
        x = (member_seed + GOLDEN_GAMMA * (index + 1)) & MASK64
        word = splitmix64(x)
        uniform = open_interval_uniform53(word)
        value = _random_inverse_cdf(index, uniform)
        if not math.isfinite(value):
            raise ArithmeticError("nonfinite inverse-CDF result")
        words.append(word)
        uniforms.append(uniform)
        values.append(value)

    parameters = dict(zip(RANDOM_PARAMETER_ORDER, values, strict=True))
    edge_pairs = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
    edge_matrix = [[0.0] * 4 for _ in range(4)]
    for name, (left, right) in zip(RANDOM_PARAMETER_ORDER[3:9], edge_pairs, strict=True):
        edge_matrix[left][right] = parameters[name]
        edge_matrix[right][left] = parameters[name]

    return {
        "object_class": TECHNICAL_LABEL,
        "algorithm": "RANDOM_SENTINEL_TECHNICAL_CONFORMANCE",
        "seed": member_seed,
        "parameter_order": list(RANDOM_PARAMETER_ORDER),
        "splitmix64_words_hex": [f"{word:016x}" for word in words],
        "uniforms": uniforms,
        "parameters": parameters,
        "edge_matrix": edge_matrix,
        "draw_count": len(RANDOM_PARAMETER_ORDER),
        "redraw_count": 0,
    }


def physics_midpoint_lhs(master_seed: int, frozen_parameter_spec: Mapping[str, Any]) -> dict[str, Any]:
    """Generate a labelled 20-by-15 technical midpoint-LHS matrix."""

    _require_order(frozen_parameter_spec, PHYSICS_PARAMETER_ORDER)
    bounds = frozen_parameter_spec.get("bounds")
    if not isinstance(bounds, Sequence) or len(bounds) != len(PHYSICS_PARAMETER_ORDER):
        raise ValueError("exactly 15 bounds pairs are required")

    permutations: list[list[int]] = []
    for parameter_index in range(len(PHYSICS_PARAMETER_ORDER)):
        permutation = list(range(20))
        for i in range(19, 0, -1):
            x = (
                master_seed
                + GOLDEN_GAMMA * (1 + 32 * parameter_index + (19 - i))
            ) & MASK64
            j = splitmix64(x) % (i + 1)
            permutation[i], permutation[j] = permutation[j], permutation[i]
        permutations.append(permutation)

    rows: list[dict[str, Any]] = []
    for row_index in range(20):
        values: dict[str, float] = {}
        for parameter_index, name in enumerate(PHYSICS_PARAMETER_ORDER):
            lower, upper = bounds[parameter_index]
            if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
                raise ValueError("bounds must be finite and strictly increasing")
            stratum = permutations[parameter_index][row_index]
            values[name] = lower + (upper - lower) * (stratum + 0.5) / 20.0
        rows.append(
            {
                "object_class": TECHNICAL_LABEL,
                "technical_row_index": row_index,
                "parameters": values,
            }
        )

    return {
        "object_class": TECHNICAL_LABEL,
        "algorithm": "PHYSICS_SENTINEL_TECHNICAL_CONFORMANCE",
        "master_seed": master_seed,
        "parameter_order": list(PHYSICS_PARAMETER_ORDER),
        "permutations": permutations,
        "rows": rows,
        "jitter": False,
    }

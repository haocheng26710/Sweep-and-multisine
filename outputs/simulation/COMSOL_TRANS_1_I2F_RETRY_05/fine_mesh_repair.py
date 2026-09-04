"""Hard gates shared by the bounded RETRY_05 fine-mesh repair."""

from __future__ import annotations

import math
from typing import Any


def require_positive_volume_mesh(stats: dict[str, Any]) -> dict[str, Any]:
    required = ("elements", "vertices", "minimum_quality", "mean_quality")
    valid = all(
        key in stats
        and isinstance(stats[key], (int, float))
        and math.isfinite(float(stats[key]))
        and float(stats[key]) > 0
        for key in required
    )
    if not valid:
        raise RuntimeError(f"Expected a positive volume mesh before study.run(); got {stats}")
    return {**stats, "hard_gate_pass": True}

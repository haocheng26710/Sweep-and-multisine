"""Common REV01 connected-volume partition."""

from __future__ import annotations

import math
from typing import Any

from .families import TECHNICAL_LABEL


def map_volume_partition(q0: float, q90: float, q180: float, target_m3: float) -> dict[str, Any]:
    """Map three independent logits to four local and one central partition."""

    values = (q0, q90, q180, target_m3)
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
        raise ValueError("volume inputs must be finite numbers")
    if target_m3 <= 0.0:
        raise ValueError("target volume must be positive")
    if not all(-0.12 <= value <= 0.12 for value in (q0, q90, q180)):
        raise ValueError("independent logits are outside frozen bounds")

    q270 = -(q0 + q90 + q180) / 3.0
    logits = (q0, q90, q180, q270)
    exponentials = [math.exp(value) for value in logits]
    denominator = math.fsum(exponentials)
    local_shares = [0.60 * value / denominator for value in exponentials]
    central_share = 0.40
    shares = local_shares + [central_share]
    volumes = [share * target_m3 for share in shares]
    if not math.isclose(math.fsum(local_shares), 0.60, rel_tol=0.0, abs_tol=2e-16):
        raise ArithmeticError("local share invariant failed")
    if not math.isclose(math.fsum(shares), 1.0, rel_tol=0.0, abs_tol=2e-16):
        raise ArithmeticError("total share invariant failed")
    return {
        "object_class": TECHNICAL_LABEL,
        "q270": q270,
        "local_shares": local_shares,
        "central_share": central_share,
        "partition_volumes_m3": volumes,
        "target_m3": target_m3,
    }

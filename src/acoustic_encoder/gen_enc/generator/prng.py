"""Frozen SplitMix64 and open-interval uniform conversion."""

from __future__ import annotations

import math

MASK64 = (1 << 64) - 1
GOLDEN_GAMMA = 0x9E3779B97F4A7C15


def _uint64(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("uint64 input must be an integer")
    return value & MASK64


def splitmix64(x: int) -> int:
    """Apply the exact REV01 SplitMix64 function to one uint64 input."""

    z = (_uint64(x) + GOLDEN_GAMMA) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return (z ^ (z >> 31)) & MASK64


def open_interval_uniform53(z: int) -> float:
    """Map one uint64 word to the frozen 53-bit open-interval uniform."""

    value = _uint64(z)
    result = ((value >> 11) + 0.5) / float(1 << 53)
    if result == 1.0:
        # The exact rational for the largest word is 1 - 2^-54, which is a
        # binary64 halfway case that rounds to 1.0.  Preserve the contract's
        # strict open interval with the adjacent representable value below 1.
        result = math.nextafter(1.0, 0.0)
    if not 0.0 < result < 1.0:
        raise ArithmeticError("uniform conversion left the open interval")
    return result

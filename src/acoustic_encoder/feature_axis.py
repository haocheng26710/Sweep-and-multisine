"""Shared parsing for authoritative persisted FeatureSet frequency axes."""

from __future__ import annotations

import re

import numpy as np
from numpy.typing import NDArray


class FeatureAxisError(ValueError):
    """Raised when persisted feature names do not encode a trustworthy axis."""


_DENSE_NAME = re.compile(r"^f_([0-9]+(?:\.[0-9]+)?)_hz$")
_TONE_NAME = re.compile(r"^tone_[0-9]{6}_([0-9]+(?:\.[0-9]+)?)_hz$")


def feature_frequencies_hz(
    feature_names: tuple[str, ...], *, allow_tones: bool = True
) -> NDArray[np.float64]:
    """Parse the two P3 frequency-name formats without inferring an axis."""
    values: list[float] = []
    for name in feature_names:
        match = _DENSE_NAME.fullmatch(name)
        if match is None and allow_tones:
            match = _TONE_NAME.fullmatch(name)
        if match is None:
            raise FeatureAxisError(f"FeatureSet frequency name is not authoritative: {name!r}")
        values.append(float(match.group(1)))
    result = np.asarray(values, dtype=np.float64)
    if result.size == 0 or np.any(~np.isfinite(result)) or np.any(np.diff(result) <= 0.0):
        raise FeatureAxisError("FeatureSet frequencies must be non-empty and strictly increasing")
    result.setflags(write=False)
    return result

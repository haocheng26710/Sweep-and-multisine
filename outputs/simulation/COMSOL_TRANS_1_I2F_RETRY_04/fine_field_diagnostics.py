"""Shape-preserving summaries for bounded COMSOL field-extraction probes."""

from __future__ import annotations

from typing import Any

import numpy as np


def summarize_array(values: Any, expected_size: int | None = None) -> dict[str, Any]:
    """Describe a raw MPh result without flattening or silently normalizing it."""
    array = np.asarray(values)
    finite = np.isfinite(array)
    size = int(array.size)
    finite_count = int(np.count_nonzero(finite))
    summary: dict[str, Any] = {
        "shape": [int(value) for value in array.shape],
        "ndim": int(array.ndim),
        "size": size,
        "dtype": str(array.dtype),
        "finite_count": finite_count,
        "nonfinite_count": size - finite_count,
        "all_finite": bool(size > 0 and finite_count == size),
        "all_zero": bool(size > 0 and finite_count == size and np.allclose(array, 0.0)),
    }
    if expected_size is not None:
        summary["expected_size"] = int(expected_size)
        summary["size_matches_expected"] = bool(size == expected_size)
    if size and finite_count:
        magnitudes = np.abs(array[finite])
        summary["finite_magnitude_min"] = float(np.min(magnitudes))
        summary["finite_magnitude_max"] = float(np.max(magnitudes))
    return summary

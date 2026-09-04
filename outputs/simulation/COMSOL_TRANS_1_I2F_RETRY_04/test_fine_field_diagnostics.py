from __future__ import annotations

import numpy as np

from fine_field_diagnostics import summarize_array


def test_summary_preserves_multidimensional_shape_instead_of_flattening():
    values = np.asarray([[1 + 2j, 3 + 4j, 5 + 6j, 7 + 8j]])

    summary = summarize_array(values)

    assert summary["shape"] == [1, 4]
    assert summary["size"] == 4
    assert summary["finite_count"] == 4
    assert summary["all_finite"] is True
    assert summary["all_zero"] is False


def test_summary_distinguishes_wrong_length_from_nonfinite():
    values = np.asarray([1.0, np.nan, 3.0])

    summary = summarize_array(values, expected_size=4)

    assert summary["size_matches_expected"] is False
    assert summary["all_finite"] is False
    assert summary["nonfinite_count"] == 1


def test_summary_handles_empty_results_without_claiming_success():
    summary = summarize_array(np.asarray([]), expected_size=4)

    assert summary["shape"] == [0]
    assert summary["size"] == 0
    assert summary["all_finite"] is False
    assert summary["size_matches_expected"] is False

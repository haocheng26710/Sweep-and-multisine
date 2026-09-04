from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.p04t2_insert_pilot_analysis import (
    P04T2InputError,
    contiguous_frequency_bands,
    parse_p04t2_filename,
    select_closest_repeats,
)


@pytest.mark.parametrize(
    ("name", "condition", "assembly", "repeat"),
    [
        ("R P04T2_BASE0_A01_01.txt", "BASE0", "A01", 1),
        ("R P04T2_BASE1_A04_06.mdat", "BASE1", "A04", 6),
        ("R P04T2_I75A_A02_03.txt", "I75A", "A02", 3),
        ("R P04T2_I50PA_A03_05.mdat", "I50PA", "A03", 5),
    ],
)
def test_parse_p04t2_filename(name, condition, assembly, repeat):
    assert parse_p04t2_filename(name) == (condition, assembly, repeat)


def test_parse_p04t2_filename_fails_closed():
    with pytest.raises(P04T2InputError):
        parse_p04t2_filename("P04T2_I50_01.txt")


def test_select_closest_repeats_is_objective_and_stable():
    frequency = np.array([500.0, 1000.0, 2000.0])
    curves = np.array([
        [0.0, 0.0, 0.0],
        [0.1, 0.1, 0.1],
        [-0.1, -0.1, -0.1],
        [0.2, 0.2, 0.2],
        [2.0, 2.0, 2.0],
        [-3.0, -3.0, -3.0],
    ])
    selected, flagged, distances = select_closest_repeats(
        curves,
        repeat_numbers=np.arange(1, 7),
        analysis_mask=(frequency >= 200.0) & (frequency <= 4000.0),
        keep=4,
    )
    assert selected.tolist() == [1, 2, 3, 4]
    assert flagged.tolist() == [5, 6]
    assert distances.shape == (6,)


def test_contiguous_frequency_bands_requires_two_bins():
    frequency = np.array([200.0, 210.0, 220.0, 300.0, 310.0])
    mask = np.array([True, True, False, True, False])
    assert contiguous_frequency_bands(frequency, mask, minimum_bins=2) == [
        {"low_hz": 200.0, "high_hz": 210.0, "bin_count": 2}
    ]

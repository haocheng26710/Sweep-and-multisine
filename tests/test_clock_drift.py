from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.clock_drift import (
    ClockDriftEstimationError,
    classify_clock_drift,
    estimate_clock_drift,
)
from acoustic_encoder.schemas import QCStatus


def _period_transfers_for_drift(
    signed_ppm: float,
    *,
    period_count: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    frequency_hz = np.arange(1000.0, 8000.0 + 100.0, 100.0)
    period_samples = 4800
    sample_rate_hz = 48000
    tone_bins = frequency_hz * period_samples / sample_rate_hz
    clock_ratio = 1.0 + signed_ppm * 1.0e-6
    phase_step_per_bin = 2.0 * np.pi * (1.0 / clock_ratio - 1.0)
    period_index = np.arange(period_count, dtype=np.float64)[:, None]
    static_transfer = np.exp(1j * np.linspace(-1.0, 1.0, frequency_hz.size))
    transfer_by_period = static_transfer[None, :] * np.exp(
        1j * period_index * phase_step_per_bin * tone_bins[None, :]
    )
    return frequency_hz, transfer_by_period


def test_clock_drift_estimator_recovers_positive_signed_ppm() -> None:
    frequency_hz, transfer_by_period = _period_transfers_for_drift(50.0)

    estimate = estimate_clock_drift(
        transfer_by_period,
        frequency_hz,
        sample_rate_hz=48000,
        period_samples=4800,
    )

    assert estimate.signed_ppm == pytest.approx(50.0, abs=1.0e-6)


def test_clock_drift_estimator_recovers_negative_signed_ppm() -> None:
    frequency_hz, transfer_by_period = _period_transfers_for_drift(-80.0)

    estimate = estimate_clock_drift(
        transfer_by_period,
        frequency_hz,
        sample_rate_hz=48000,
        period_samples=4800,
    )

    assert estimate.signed_ppm == pytest.approx(-80.0, abs=1.0e-6)


@pytest.mark.parametrize(
    ("signed_ppm", "expected"),
    [
        (0.0, QCStatus.VALID),
        (np.nextafter(20.0, 0.0), QCStatus.VALID),
        (20.0, QCStatus.WARNING),
        (-20.0, QCStatus.WARNING),
        (np.nextafter(100.0, 0.0), QCStatus.WARNING),
        (100.0, QCStatus.EXCLUDE_CANDIDATE),
        (-100.0, QCStatus.EXCLUDE_CANDIDATE),
    ],
)
def test_clock_drift_thresholds_use_absolute_inclusive_boundaries(
    signed_ppm: float,
    expected: QCStatus,
) -> None:
    assert classify_clock_drift(
        signed_ppm,
        warning_ppm=20.0,
        exclude_candidate_ppm=100.0,
    ) is expected


def test_clock_drift_estimator_rejects_a_single_period_instead_of_returning_zero() -> None:
    frequency_hz, transfer_by_period = _period_transfers_for_drift(
        0.0,
        period_count=1,
    )

    with pytest.raises(ClockDriftEstimationError, match="at least two complete periods"):
        estimate_clock_drift(
            transfer_by_period,
            frequency_hz,
            sample_rate_hz=48000,
            period_samples=4800,
        )


def test_clock_drift_estimator_rejects_zero_observation_instead_of_returning_zero() -> None:
    frequency_hz = np.arange(1000.0, 8000.0 + 100.0, 100.0)

    with pytest.raises(ClockDriftEstimationError, match="observable tone energy"):
        estimate_clock_drift(
            np.zeros((8, frequency_hz.size), dtype=np.complex128),
            frequency_hz,
            sample_rate_hz=48000,
            period_samples=4800,
        )

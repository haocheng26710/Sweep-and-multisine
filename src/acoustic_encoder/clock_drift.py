"""Signed sampling-clock drift estimation for periodic multisine recordings."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates

from .schemas import QCStatus

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


class ClockDriftEstimationError(ValueError):
    """Raised when an auditable drift estimate cannot be formed."""


@dataclass(frozen=True, slots=True)
class ClockDriftEstimate:
    signed_ppm: float
    absolute_ppm: float
    period_timing_error_samples: float
    phase_fit_rmse_rad: float
    period_count: int
    tone_count: int


def classify_clock_drift(
    signed_ppm: float,
    *,
    warning_ppm: float,
    exclude_candidate_ppm: float,
) -> QCStatus:
    """Map absolute drift to inclusive, configuration-owned QC thresholds."""
    absolute_ppm = abs(signed_ppm)
    if absolute_ppm >= exclude_candidate_ppm:
        return QCStatus.EXCLUDE_CANDIDATE
    if absolute_ppm >= warning_ppm:
        return QCStatus.WARNING
    return QCStatus.VALID


def correct_recording_time_axis(
    recording: FloatArray,
    *,
    signed_drift_ppm: float,
) -> tuple[FloatArray, float]:
    """Resample a recording onto the stimulus clock using an estimated ratio."""
    audio = np.asarray(recording, dtype=np.float64)
    clock_ratio = 1.0 + signed_drift_ppm * 1.0e-6
    if audio.ndim != 1 or audio.size < 2 or not np.isfinite(clock_ratio):
        raise ClockDriftEstimationError(
            "Clock drift correction requires finite mono audio"
        )
    if clock_ratio <= 0.0:
        raise ClockDriftEstimationError(
            "Clock drift correction requires a positive clock ratio"
        )
    correction_ratio = 1.0 / clock_ratio
    output_count = int(np.floor((audio.size - 1) * correction_ratio)) + 1
    source_coordinate = np.arange(output_count, dtype=np.float64) / correction_ratio
    corrected = map_coordinates(
        audio,
        source_coordinate[None, :],
        order=5,
        mode="constant",
        cval=0.0,
        prefilter=True,
    )
    return np.asarray(corrected, dtype=np.float64), correction_ratio


def estimate_clock_drift(
    transfer_by_period: ComplexArray,
    frequency_hz: FloatArray,
    *,
    sample_rate_hz: int,
    period_samples: int,
) -> ClockDriftEstimate:
    """Estimate output/input clock-ratio error from adjacent-period phase advance."""
    transfers = np.asarray(transfer_by_period, dtype=np.complex128)
    frequencies = np.asarray(frequency_hz, dtype=np.float64)
    if transfers.ndim != 2 or transfers.shape[0] < 2:
        raise ClockDriftEstimationError(
            "Clock drift estimation requires at least two complete periods"
        )
    if frequencies.ndim != 1 or transfers.shape[1] != frequencies.size:
        raise ClockDriftEstimationError(
            "Clock drift tone frequencies must match the transfer matrix"
        )
    adjacent = transfers[1:] * np.conj(transfers[:-1])
    phase_step = np.angle(np.sum(adjacent, axis=0))
    weights = np.sum(np.abs(adjacent), axis=0)
    if not np.all(np.isfinite(weights)) or float(np.sum(weights)) <= 0.0:
        raise ClockDriftEstimationError(
            "Clock drift estimation requires observable tone energy"
        )
    tone_bins = frequencies * float(period_samples) / float(sample_rate_hz)
    slope = float(
        np.sum(weights * tone_bins * phase_step)
        / np.sum(weights * tone_bins**2)
    )
    clock_ratio = 1.0 / (1.0 + slope / (2.0 * np.pi))
    signed_ppm = (clock_ratio - 1.0) * 1.0e6
    residual = phase_step - slope * tone_bins
    fit_rmse = float(np.sqrt(np.average(residual**2, weights=weights)))
    return ClockDriftEstimate(
        signed_ppm=signed_ppm,
        absolute_ppm=abs(signed_ppm),
        period_timing_error_samples=period_samples * (clock_ratio - 1.0),
        phase_fit_rmse_rad=fit_rmse,
        period_count=int(transfers.shape[0]),
        tone_count=int(transfers.shape[1]),
    )

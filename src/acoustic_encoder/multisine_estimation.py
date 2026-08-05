"""P8 synchronization and per-period transfer estimation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray
from scipy.signal import correlate

from .tone_sets import ToneSetDefinition

FloatArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]
IntArray = NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class PeriodTransferEstimate:
    frequency_hz: FloatArray
    tone_bins: IntArray
    transfer_by_period: ComplexArray
    spectrum_by_period: ComplexArray
    analysis_periods: FloatArray
    normalized_correlation: FloatArray
    preamble_start_sample: int
    first_period_start_sample: int
    analysis_start_sample: int
    period_samples: int
    discarded_period_count: int
    stable_period_count: int


def _tone_frequencies(manifest: Mapping[str, Any]) -> FloatArray:
    tones = manifest["resolved_stimulus_config"]["tones"]
    if tones["mode"] == "range":
        spacing = float(tones["spacing_hz"])
        return np.arange(
            float(tones["start_hz"]),
            float(tones["stop_hz"]) + 0.5 * spacing,
            spacing,
            dtype=np.float64,
        )
    return np.asarray(tones["frequencies_hz"], dtype=np.float64)


def estimate_period_transfers(
    recording: FloatArray,
    stimulus: FloatArray,
    manifest: Mapping[str, Any],
    *,
    tone_set: ToneSetDefinition | None = None,
) -> PeriodTransferEstimate:
    """Locate the preamble and calculate complex transfer at every tone/period."""
    preamble_offset = int(manifest["pre_silence_samples"])
    preamble_samples = int(manifest["preamble_samples"])
    preamble = stimulus[preamble_offset : preamble_offset + preamble_samples]
    if preamble.size != preamble_samples or recording.size < preamble_samples:
        raise ValueError("recording and stimulus must contain the complete preamble")
    correlation = correlate(recording, preamble, mode="valid", method="fft")
    cumulative_energy = np.concatenate(
        [np.zeros(1, dtype=np.float64), np.cumsum(recording**2)]
    )
    window_energy = np.maximum(
        cumulative_energy[preamble_samples:] - cumulative_energy[:-preamble_samples],
        0.0,
    )
    denominator = np.linalg.norm(preamble) * np.sqrt(window_energy)
    normalized_correlation = np.divide(
        np.abs(correlation),
        denominator,
        out=np.zeros_like(correlation, dtype=np.float64),
        where=denominator > 0,
    )
    preamble_start = int(np.argmax(normalized_correlation))

    period_samples = int(manifest["period_samples"])
    discarded_periods = int(manifest["discard_initial_period_count"])
    stable_periods = int(manifest["stable_period_count"])
    first_period_start = (
        preamble_start
        + preamble_samples
        + int(manifest["preamble_gap_samples"])
    )
    analysis_start = first_period_start + discarded_periods * period_samples
    analysis_stop = analysis_start + stable_periods * period_samples
    if analysis_stop > recording.size:
        raise ValueError("recording does not contain all stable periods")
    periods = recording[analysis_start:analysis_stop].reshape(
        stable_periods,
        period_samples,
    )

    reference_start = int(manifest["analysis_start_sample"])
    reference_period = stimulus[reference_start : reference_start + period_samples]
    if reference_period.size != period_samples:
        raise ValueError("stimulus does not contain a complete reference period")
    sample_rate = int(manifest["sample_rate_hz"])
    if tone_set is None:
        # Explicit compatibility path for low-level legacy callers. Formal P1/P8
        # loading always passes a hash-verified ToneSetDefinition.
        frequencies = _tone_frequencies(manifest)
        bins = np.rint(frequencies * period_samples / sample_rate).astype(int)
    else:
        if (
            tone_set.sample_rate_hz != sample_rate
            or tone_set.period_samples != period_samples
            or tone_set.tone_set_id != str(manifest["tone_set_id"])
        ):
            raise ValueError("verified tone set does not match stimulus manifest")
        frequencies = tone_set.frequency_hz
        bins = tone_set.dft_bins
    reference_fft = np.fft.rfft(reference_period)[bins]
    spectrum_by_period = np.fft.rfft(periods, axis=1)
    recording_fft = spectrum_by_period[:, bins]
    return PeriodTransferEstimate(
        frequency_hz=frequencies,
        tone_bins=bins,
        transfer_by_period=recording_fft / reference_fft[None, :],
        spectrum_by_period=spectrum_by_period,
        analysis_periods=periods,
        normalized_correlation=normalized_correlation,
        preamble_start_sample=preamble_start,
        first_period_start_sample=first_period_start,
        analysis_start_sample=analysis_start,
        period_samples=period_samples,
        discarded_period_count=discarded_periods,
        stable_period_count=stable_periods,
    )

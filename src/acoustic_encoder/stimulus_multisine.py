"""P7: deterministic Schroeder-phase multisine stimulus generation."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray
from scipy.io import wavfile
from scipy.signal import chirp

from .config import validate_stimulus_config
from .tone_sets import (
    ToneDefinition,
    canonical_frequency_text,
    canonical_tone_set_sha256,
)
from .version import SCHEMA_VERSION_QUARTET

FloatArray = NDArray[np.float64]
SCHROEDER_FORMULA = "phi_m = -pi*m*(m-1)/M, m=0..M-1"


@dataclass(frozen=True, slots=True)
class StimulusArtifacts:
    directory: Path
    wav_path: Path
    manifest_path: Path
    tones_path: Path
    preview_path: Path
    hash_path: Path
    waveform_sha256: str
    tones_sha256: str
    tone_set_sha256: str


def _tone_frequencies(stimulus: Mapping[str, Any]) -> FloatArray:
    tone_config = stimulus["tones"]
    if tone_config["mode"] == "range":
        spacing = float(tone_config["spacing_hz"])
        values = np.arange(
            float(tone_config["start_hz"]),
            float(tone_config["stop_hz"]) + 0.5 * spacing,
            spacing,
            dtype=np.float64,
        )
    else:
        values = np.asarray(tone_config["frequencies_hz"], dtype=np.float64)
    return values


def _amplitude_weights(stimulus: Mapping[str, Any], tone_count: int) -> FloatArray:
    amplitude = stimulus["amplitude"]
    if amplitude["mode"] == "equal":
        return np.ones(tone_count, dtype=np.float64)
    return np.asarray(amplitude["weights"], dtype=np.float64)


def _phases(stimulus: Mapping[str, Any], tone_count: int) -> FloatArray:
    method = stimulus["phase"]["method"]
    if method == "zero":
        return np.zeros(tone_count, dtype=np.float64)
    ordinal = np.arange(tone_count, dtype=np.float64)
    return -np.pi * ordinal * (ordinal - 1.0) / tone_count


def _make_preamble(stimulus: Mapping[str, Any]) -> FloatArray:
    preamble = stimulus.get("preamble", {"type": "none"})
    sample_rate = int(stimulus["sample_rate_hz"])
    if preamble.get("type", "none") == "none":
        return np.array([], dtype=np.float64)
    if preamble.get("type") != "linear_chirp":
        raise ValueError("preamble.type must be none or linear_chirp")
    sample_count = int(round(float(preamble["duration_s"]) * sample_rate))
    if sample_count <= 1:
        raise ValueError("preamble duration must contain at least two samples")
    time = np.arange(sample_count, dtype=np.float64) / sample_rate
    marker = chirp(
        time,
        f0=float(preamble["start_hz"]),
        f1=float(preamble["stop_hz"]),
        t1=float(preamble["duration_s"]),
        method="linear",
        phi=-90.0,
    )
    # This fade affects only the synchronization marker, never analysis periods.
    marker *= np.sin(np.linspace(0.0, np.pi, sample_count, endpoint=True)) ** 2
    marker *= float(preamble.get("relative_amplitude", 0.35))
    return marker


def synthesize_multisine(stimulus: Mapping[str, Any]) -> tuple[FloatArray, dict[str, Any]]:
    """Build the complete waveform and deterministic manifest-ready metrics."""
    validate_stimulus_config(stimulus)
    sample_rate = int(stimulus["sample_rate_hz"])
    period_samples = int(stimulus["period_samples"])
    frequencies = _tone_frequencies(stimulus)
    weights = _amplitude_weights(stimulus, frequencies.size)
    phases = _phases(stimulus, frequencies.size)
    bins = np.rint(frequencies * period_samples / sample_rate).astype(int)

    time = np.arange(period_samples, dtype=np.float64) / sample_rate
    angles = 2.0 * np.pi * frequencies[:, None] * time[None, :] + phases[:, None]
    period = np.sum(weights[:, None] * np.cos(angles), axis=0)
    period /= math.sqrt(float(np.sum(weights**2)))

    pre_silence_samples = int(round(float(stimulus.get("pre_silence_s", 0.0)) * sample_rate))
    post_silence_samples = int(round(float(stimulus.get("post_silence_s", 0.0)) * sample_rate))
    preamble = _make_preamble(stimulus)
    gap_samples = int(
        round(float(stimulus.get("preamble", {}).get("gap_after_s", 0.0)) * sample_rate)
    )
    discard_periods = int(stimulus["discard_initial_period_count"])
    stable_periods = int(stimulus["stable_period_count"])
    total_periods = discard_periods + stable_periods
    analysis_start = pre_silence_samples + preamble.size + gap_samples + discard_periods * period_samples
    analysis_sample_count = stable_periods * period_samples
    waveform = np.concatenate(
        [
            np.zeros(pre_silence_samples, dtype=np.float64),
            preamble,
            np.zeros(gap_samples, dtype=np.float64),
            np.tile(period, total_periods),
            np.zeros(post_silence_samples, dtype=np.float64),
        ]
    )

    target_peak = 10.0 ** (float(stimulus["target_peak_dbfs"]) / 20.0)
    unscaled_peak = float(np.max(np.abs(waveform)))
    if unscaled_peak == 0:
        raise ValueError("Generated waveform is silent")
    scale = target_peak / unscaled_peak
    waveform *= scale
    scaled_period = period * scale
    rms = float(np.sqrt(np.mean(scaled_period**2)))
    peak = float(np.max(np.abs(scaled_period)))
    crest_factor = peak / rms
    metrics = {
        "sample_rate_hz": sample_rate,
        "period_samples": period_samples,
        "period_duration_s": period_samples / sample_rate,
        "dft_bin_spacing_hz": sample_rate / period_samples,
        "tone_count": int(frequencies.size),
        "tone_frequencies_hz": frequencies,
        "tone_bins": bins,
        "amplitude_weights": weights,
        "phases_rad": phases,
        "phase_method": stimulus["phase"]["method"],
        "phase_formula": SCHROEDER_FORMULA if stimulus["phase"]["method"] == "schroeder" else "phi_m = 0",
        "normalization_scale": scale,
        "target_peak_dbfs": float(stimulus["target_peak_dbfs"]),
        "waveform_peak": float(np.max(np.abs(waveform))),
        "period_peak": peak,
        "period_rms": rms,
        "crest_factor_linear": crest_factor,
        "crest_factor_db": 20.0 * math.log10(crest_factor),
        "pre_silence_samples": pre_silence_samples,
        "preamble_samples": int(preamble.size),
        "preamble_gap_samples": gap_samples,
        "discard_initial_period_count": discard_periods,
        "stable_period_count": stable_periods,
        "analysis_start_sample": analysis_start,
        "analysis_sample_count": analysis_sample_count,
        "post_silence_samples": post_silence_samples,
        "total_samples": int(waveform.size),
    }
    return waveform, metrics


def _write_wav(path: Path, sample_rate: int, waveform: FloatArray, wav_format: str) -> None:
    if wav_format == "float32":
        wavfile.write(path, sample_rate, waveform.astype(np.float32))
    else:
        pcm = np.rint(np.clip(waveform, -1.0, 1.0) * np.iinfo(np.int16).max).astype(np.int16)
        wavfile.write(path, sample_rate, pcm)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preview(path: Path, waveform: FloatArray, metrics: Mapping[str, Any]) -> None:
    sample_rate = int(metrics["sample_rate_hz"])
    start = int(metrics["analysis_start_sample"])
    period_samples = int(metrics["period_samples"])
    period = waveform[start : start + period_samples]
    time_ms = np.arange(period_samples) / sample_rate * 1000.0
    spectrum = np.fft.rfft(period)
    frequencies = np.fft.rfftfreq(period_samples, d=1.0 / sample_rate)
    magnitude = 20.0 * np.log10(np.maximum(np.abs(spectrum), np.finfo(float).tiny))

    figure, axes = plt.subplots(2, 1, figsize=(10, 7), constrained_layout=True)
    axes[0].plot(time_ms, period, linewidth=0.8)
    axes[0].set(title="One unchanged analysis period", xlabel="Time (ms)", ylabel="Amplitude")
    axes[0].grid(alpha=0.25)
    axes[1].plot(frequencies, magnitude, linewidth=0.8)
    axes[1].set(
        title="Analysis-period spectrum",
        xlabel="Frequency (Hz)",
        ylabel="Magnitude (dB, FFT units)",
        xlim=(0, min(sample_rate / 2, max(metrics["tone_frequencies_hz"]) * 1.1)),
    )
    axes[1].grid(alpha=0.25)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def generate_multisine(
    stimulus: Mapping[str, Any],
    output_root: str | Path,
    *,
    overwrite: bool = False,
) -> StimulusArtifacts:
    """Generate P7 artifacts under ``output_root/<stimulus_id>``."""
    waveform, metrics = synthesize_multisine(stimulus)
    directory = Path(output_root) / str(stimulus["stimulus_id"])
    wav_path = directory / "stimulus.wav"
    manifest_path = directory / "stimulus_manifest.json"
    tones_path = directory / "tones.csv"
    preview_path = directory / "stimulus_preview.png"
    hash_path = directory / "waveform_hash.txt"
    artifacts = (wav_path, manifest_path, tones_path, preview_path, hash_path)
    if any(path.exists() for path in artifacts) and not overwrite:
        raise FileExistsError(f"Stimulus artifacts already exist in {directory}; use overwrite explicitly")
    directory.mkdir(parents=True, exist_ok=True)

    _write_wav(wav_path, int(metrics["sample_rate_hz"]), waveform, str(stimulus["wav_format"]))
    waveform_sha256 = _sha256(wav_path)
    with tones_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tone_index", "frequency_hz", "dft_bin", "amplitude_weight", "phase_rad"])
        for index, values in enumerate(
            zip(
                metrics["tone_frequencies_hz"],
                metrics["tone_bins"],
                metrics["amplitude_weights"],
                metrics["phases_rad"],
                strict=True,
            )
        ):
            frequency, dft_bin, weight, phase = values
            writer.writerow(
                [
                    index,
                    canonical_frequency_text(float(frequency)),
                    int(dft_bin),
                    f"{weight:.17g}",
                    f"{phase:.17g}",
                ]
            )
    tones_sha256 = _sha256(tones_path)
    tone_definitions = tuple(
        ToneDefinition(
            tone_index=index,
            frequency_hz=float(frequency),
            frequency_text=canonical_frequency_text(float(frequency)),
            dft_bin=int(dft_bin),
            amplitude_weight=float(weight),
            phase_rad=float(phase),
        )
        for index, (frequency, dft_bin, weight, phase) in enumerate(
            zip(
                metrics["tone_frequencies_hz"],
                metrics["tone_bins"],
                metrics["amplitude_weights"],
                metrics["phases_rad"],
                strict=True,
            )
        )
    )
    tone_set_sha256 = canonical_tone_set_sha256(
        str(stimulus["tone_set_id"]),
        int(metrics["sample_rate_hz"]),
        int(metrics["period_samples"]),
        tone_definitions,
    )
    manifest = {
        **SCHEMA_VERSION_QUARTET,
        "manifest_schema_version": "1.1.0",
        "stimulus_id": stimulus["stimulus_id"],
        "tone_set_id": stimulus["tone_set_id"],
        "tones_sha256": tones_sha256,
        "tone_set_sha256": tone_set_sha256,
        "waveform_sha256": waveform_sha256,
        "wav_format": stimulus["wav_format"],
        "tone_source": stimulus["tones"].get("source", "unspecified"),
        "fade_policy": "Fade is applied only to the synchronization preamble; analysis periods are unchanged.",
        **{key: value for key, value in metrics.items() if key not in {"tone_frequencies_hz", "tone_bins", "amplitude_weights", "phases_rad"}},
        "tones_file": "tones.csv",
        "wav_file": "stimulus.wav",
        "resolved_stimulus_config": stimulus,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    hash_path.write_text(waveform_sha256 + "\n", encoding="ascii")
    _preview(preview_path, waveform, metrics)
    return StimulusArtifacts(
        directory=directory,
        wav_path=wav_path,
        manifest_path=manifest_path,
        tones_path=tones_path,
        preview_path=preview_path,
        hash_path=hash_path,
        waveform_sha256=waveform_sha256,
        tones_sha256=tones_sha256,
        tone_set_sha256=tone_set_sha256,
    )

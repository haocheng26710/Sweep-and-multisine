"""S3 mock inputs for development; never valid as scientific evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline
from scipy.io import wavfile

from .schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    QCStatus,
    SourceFormat,
)
from .stimulus_multisine import generate_multisine
from .version import SCHEMA_VERSION_QUARTET

FloatArray = NDArray[np.float64]


def known_transfer_db(
    frequency_hz: FloatArray,
    *,
    angle_deg: float,
    configuration: str,
) -> FloatArray:
    """Deterministic, direction-dependent transfer function for test fixtures."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    log_frequency = np.log(np.maximum(frequency, 1.0))
    common = -24.0 + 1.2 * np.sin(2.7 * log_frequency) + 0.7 * np.cos(5.3 * log_frequency)
    direction_index = int(round(angle_deg / 90.0)) % 4
    if configuration.upper() == "U4SYM":
        direction = 0.18 * np.cos(np.deg2rad(angle_deg)) * np.sin(frequency / 510.0)
    elif configuration.upper() == "U4ENC":
        centers = np.array([1450.0, 2600.0, 4300.0, 6500.0])
        widths = np.array([180.0, 260.0, 360.0, 480.0])
        signs = np.array(
            [
                [1.0, -0.4, 0.2, -0.3],
                [-0.3, 1.0, -0.5, 0.2],
                [0.2, -0.3, 1.0, -0.5],
                [-0.5, 0.2, -0.3, 1.0],
            ]
        )[direction_index]
        gaussian_bank = np.exp(-0.5 * ((frequency[:, None] - centers) / widths) ** 2)
        direction = 4.0 * (gaussian_bank @ signs)
    else:
        raise ValueError(f"Unknown mock configuration: {configuration}")
    return common + direction


def _write_mock_rew_txt(
    path: Path,
    frequency_hz: FloatArray,
    magnitude_db: FloatArray,
    phase_deg: FloatArray,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("# MOCK ONLY - not experimental evidence\n")
        handle.write("* Deliberately resembles, but does not define, a REW export format\n")
        writer = csv.writer(handle)
        writer.writerow(["Frequency (Hz)", "Magnitude (dB)", "Phase (deg)"])
        for row in zip(frequency_hz, magnitude_db, phase_deg, strict=True):
            writer.writerow([f"{row[0]:.6f}", f"{row[1]:.8f}", f"{row[2]:.8f}"])


def _read_wav_float(path: Path) -> tuple[int, FloatArray]:
    sample_rate, values = wavfile.read(path)
    if np.issubdtype(values.dtype, np.integer):
        scale = max(abs(np.iinfo(values.dtype).min), np.iinfo(values.dtype).max)
        audio = values.astype(np.float64) / scale
    else:
        audio = values.astype(np.float64)
    if audio.ndim != 1:
        raise ValueError("DEV-A mock expects a mono P7 stimulus")
    return int(sample_rate), audio


def _simulate_recording(
    stimulus_wav: Path,
    stimulus_manifest: Mapping[str, Any],
    *,
    angle_deg: float,
    configuration: str,
    random_state: int,
    recording_delay_samples: int,
    sampling_clock_drift_ppm: float,
    additive_noise_std: float,
    missing_tone_frequencies_hz: tuple[float, ...],
    interference_tones_dbfs: Mapping[float, float],
    stable_period_gain_db: tuple[float, ...] | None,
    stable_period_shift_samples: tuple[int, ...] | None,
    clipping_run_samples: int,
) -> tuple[int, FloatArray]:
    sample_rate, audio = _read_wav_float(stimulus_wav)
    frequency = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    transfer_db = known_transfer_db(frequency, angle_deg=angle_deg, configuration=configuration)
    transfer_linear = 10.0 ** (transfer_db / 20.0)
    recording = np.fft.irfft(np.fft.rfft(audio) * transfer_linear, n=audio.size)
    period_samples = int(stimulus_manifest["period_samples"])
    analysis_start = int(stimulus_manifest["analysis_start_sample"])
    stable_period_count = int(stimulus_manifest["stable_period_count"])
    discarded_period_count = int(stimulus_manifest["discard_initial_period_count"])
    first_period_start = analysis_start - discarded_period_count * period_samples
    tone_bins_to_remove = {
        int(round(frequency_hz * period_samples / sample_rate))
        for frequency_hz in missing_tone_frequencies_hz
    }
    if tone_bins_to_remove:
        for period_index in range(discarded_period_count + stable_period_count):
            start = first_period_start + period_index * period_samples
            stop = start + period_samples
            period_spectrum = np.fft.rfft(recording[start:stop])
            for tone_bin in tone_bins_to_remove:
                if tone_bin <= 0 or tone_bin >= period_spectrum.size:
                    raise ValueError(
                        "missing_tone_frequencies_hz must resolve inside the WAV band"
                    )
                period_spectrum[tone_bin] = 0.0
            recording[start:stop] = np.fft.irfft(period_spectrum, n=period_samples)
    generator = np.random.default_rng(random_state)
    if not np.isfinite(additive_noise_std) or additive_noise_std < 0.0:
        raise ValueError("additive_noise_std must be finite and non-negative")
    recording += generator.normal(0.0, additive_noise_std, size=recording.size)

    stable_stop = analysis_start + stable_period_count * period_samples
    stable_sample_index = np.arange(
        stable_period_count * period_samples,
        dtype=np.float64,
    )
    for interference_hz, level_dbfs in interference_tones_dbfs.items():
        if not np.isfinite(interference_hz) or not 0.0 < interference_hz < sample_rate / 2:
            raise ValueError("interference frequencies must be finite and below Nyquist")
        if not np.isfinite(level_dbfs) or level_dbfs > 0.0:
            raise ValueError("interference levels must be finite and at or below 0 dBFS")
        amplitude = 10.0 ** (level_dbfs / 20.0)
        recording[analysis_start:stable_stop] += amplitude * np.sin(
            2.0 * np.pi * interference_hz * stable_sample_index / sample_rate
        )

    if stable_period_gain_db is not None:
        if len(stable_period_gain_db) != stable_period_count:
            raise ValueError("stable_period_gain_db must have one value per stable period")
        if not all(np.isfinite(value) for value in stable_period_gain_db):
            raise ValueError("stable_period_gain_db values must be finite")
    if stable_period_shift_samples is not None:
        if len(stable_period_shift_samples) != stable_period_count:
            raise ValueError(
                "stable_period_shift_samples must have one value per stable period"
            )
        if not all(isinstance(value, int) for value in stable_period_shift_samples):
            raise ValueError("stable_period_shift_samples values must be integers")
    for period_index in range(stable_period_count):
        start = analysis_start + period_index * period_samples
        stop = start + period_samples
        period = recording[start:stop].copy()
        if stable_period_shift_samples is not None:
            period = np.roll(period, stable_period_shift_samples[period_index])
        if stable_period_gain_db is not None:
            period *= 10.0 ** (stable_period_gain_db[period_index] / 20.0)
        recording[start:stop] = period
    if not np.isfinite(sampling_clock_drift_ppm):
        raise ValueError("sampling_clock_drift_ppm must be finite")
    clock_ratio = 1.0 + sampling_clock_drift_ppm * 1.0e-6
    if clock_ratio <= 0.0:
        raise ValueError("sampling_clock_drift_ppm produces a non-positive clock ratio")
    if sampling_clock_drift_ppm != 0.0:
        output_count = int(np.floor((recording.size - 1) * clock_ratio)) + 1
        source_coordinate = np.arange(output_count, dtype=np.float64) / clock_ratio
        recording = CubicSpline(
            np.arange(recording.size, dtype=np.float64),
            recording,
            bc_type="natural",
        )(source_coordinate)
    if np.max(np.abs(recording)) >= 1.0:
        raise RuntimeError("Mock recording clipped; lower the synthetic transfer gain")
    if recording_delay_samples < 0:
        raise ValueError("recording_delay_samples cannot be negative")
    recording = np.pad(recording, (recording_delay_samples, 0))
    if not isinstance(clipping_run_samples, int) or clipping_run_samples < 0:
        raise ValueError("clipping_run_samples must be a non-negative integer")
    if clipping_run_samples:
        clipping_start = min(
            recording.size - clipping_run_samples,
            recording_delay_samples + analysis_start + period_samples // 2,
        )
        if clipping_start < 0:
            raise ValueError("clipping_run_samples exceeds the recording length")
        recording[clipping_start : clipping_start + clipping_run_samples] = 1.0
    return sample_rate, recording


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_dual_mode_mock(
    output_root: str | Path,
    stimulus_config: Mapping[str, Any],
    *,
    configurations: Iterable[str] = ("U4SYM", "U4ENC"),
    angles_deg: Iterable[int] = (0, 90, 180, 270),
    random_state: int = 20260804,
    recording_delay_samples: int = 0,
    sampling_clock_drift_ppm: float = 0.0,
    recording_wav_format: str = "float32",
    additive_noise_std: float = 2.0e-5,
    missing_tone_frequencies_hz: Iterable[float] = (),
    interference_tones_dbfs: Mapping[float, float] | None = None,
    stable_period_gain_db: Iterable[float] | None = None,
    stable_period_shift_samples: Iterable[int] | None = None,
    clipping_run_samples: int = 0,
    overwrite: bool = False,
) -> Path:
    """Generate matching mock sweep TXT and multisine WAV inputs."""
    root = Path(output_root)
    manifest_path = root / "mock_manifest.json"
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(f"Mock output already exists: {root}")
    root.mkdir(parents=True, exist_ok=True)
    stimulus_artifacts = generate_multisine(
        stimulus_config,
        root / "stimuli",
        overwrite=overwrite,
    )
    stimulus_manifest = json.loads(
        stimulus_artifacts.manifest_path.read_text(encoding="utf-8")
    )
    if recording_wav_format not in {"float32", "pcm16"}:
        raise ValueError("recording_wav_format must be float32 or pcm16")
    missing_frequencies = tuple(float(value) for value in missing_tone_frequencies_hz)
    interference = {
        float(frequency): float(level)
        for frequency, level in (interference_tones_dbfs or {}).items()
    }
    gain_jitter = (
        None
        if stable_period_gain_db is None
        else tuple(float(value) for value in stable_period_gain_db)
    )
    shift_jitter = (
        None
        if stable_period_shift_samples is None
        else tuple(stable_period_shift_samples)
    )
    sweep_root = root / "rew"
    audio_root = root / "multisine"
    truth_root = root / "truth"
    truth_root.mkdir(parents=True, exist_ok=True)
    dense_frequency = np.arange(300.0, 10000.0 + 10.0, 10.0)
    sample_records: list[dict[str, Any]] = []
    sample_counter = 0

    for configuration in configurations:
        for angle in angles_deg:
            base_name = f"V2_{configuration}_A{int(angle):03d}_S01_CONT_R01"
            sweep_sample_id = f"mock_{base_name}_SW"
            multisine_sample_id = f"mock_{base_name}_MS"
            transfer_db = known_transfer_db(
                dense_frequency,
                angle_deg=float(angle),
                configuration=configuration,
            )
            phase_deg = -360.0 * dense_frequency * 0.001
            sweep_path = sweep_root / f"{base_name}.txt"
            _write_mock_rew_txt(sweep_path, dense_frequency, transfer_db, phase_deg)

            truth_path = truth_root / f"{base_name}_known_H.csv"
            with truth_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["frequency_hz", "known_transfer_db"])
                writer.writerows(zip(dense_frequency, transfer_db, strict=True))

            sample_rate, recording = _simulate_recording(
                stimulus_artifacts.wav_path,
                stimulus_manifest,
                angle_deg=float(angle),
                configuration=configuration,
                random_state=random_state + sample_counter,
                recording_delay_samples=recording_delay_samples,
                sampling_clock_drift_ppm=sampling_clock_drift_ppm,
                additive_noise_std=additive_noise_std,
                missing_tone_frequencies_hz=missing_frequencies,
                interference_tones_dbfs=interference,
                stable_period_gain_db=gain_jitter,
                stable_period_shift_samples=shift_jitter,
                clipping_run_samples=clipping_run_samples,
            )
            audio_path = audio_root / f"{base_name}_MS.wav"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            if recording_wav_format == "float32":
                wav_values = recording.astype(np.float32)
            else:
                wav_values = np.rint(
                    np.clip(recording, -1.0, 1.0) * np.iinfo(np.int16).max
                ).astype(np.int16)
            wavfile.write(audio_path, sample_rate, wav_values)
            audio_sha256 = _sha256(audio_path)
            sidecar_path = audio_path.with_suffix(".json")
            multisine_meta = MeasurementMeta(
                sample_id=multisine_sample_id,
                **SCHEMA_VERSION_QUARTET,
                device_version="V2",
                configuration=configuration,
                angle_deg=float(angle),
                session_id="S01",
                repeat_type="CONT",
                repeat_id="R01",
                acquisition_block_id="B01",
                experiment_step="MOCK_DEV_A",
                measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
                stimulus_id=str(stimulus_config["stimulus_id"]),
                stimulus_hash=stimulus_artifacts.waveform_sha256,
                tone_set_id=str(stimulus_config["tone_set_id"]),
                source_format=SourceFormat.MOCK_AUDIO,
                source_path=audio_path.as_posix(),
                data_origin=DataOrigin.SIMULATED,
                dataset_role=DatasetRole.SOFTWARE_VALIDATION,
                source_sha256=audio_sha256,
                provenance_uri=manifest_path.as_posix(),
                eligible_for_scientific_analysis=False,
                sidecar_path=sidecar_path.as_posix(),
                audio_channel=0,
                qc_status=QCStatus.VALID,
            )
            sidecar = {
                **multisine_meta.to_dict(),
                "mock_only": True,
                "sample_rate_hz": sample_rate,
                "period_samples": int(stimulus_config["period_samples"]),
                "recording_delay_samples": recording_delay_samples,
                "sampling_clock_drift_ppm": sampling_clock_drift_ppm,
                "recording_wav_format": recording_wav_format,
                "additive_noise_std": additive_noise_std,
                "missing_tone_frequencies_hz": missing_frequencies,
                "interference_tones_dbfs": interference,
                "stable_period_gain_db": gain_jitter,
                "stable_period_shift_samples": shift_jitter,
                "clipping_run_samples": clipping_run_samples,
                "clock_drift_simulation_method": (
                    "none"
                    if sampling_clock_drift_ppm == 0.0
                    else "cubic_spline_time_axis_resampling"
                ),
                "common_sampling_clock": False,
                "stimulus_manifest": stimulus_artifacts.manifest_path.as_posix(),
                "recording_sha256": audio_sha256,
                "known_transfer_csv": truth_path.as_posix(),
            }
            sidecar_path.write_text(
                json.dumps(sidecar, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            sweep_meta = MeasurementMeta(
                sample_id=sweep_sample_id,
                **SCHEMA_VERSION_QUARTET,
                device_version="V2",
                configuration=configuration,
                angle_deg=float(angle),
                session_id="S01",
                repeat_type="CONT",
                repeat_id="R01",
                acquisition_block_id="B01",
                experiment_step="MOCK_DEV_A",
                measurement_mode=MeasurementMode.REW_SWEEP,
                source_format=SourceFormat.MOCK_DENSE,
                source_path=sweep_path.as_posix(),
                data_origin=DataOrigin.SIMULATED,
                dataset_role=DatasetRole.SOFTWARE_VALIDATION,
                source_sha256=_sha256(sweep_path),
                provenance_uri=manifest_path.as_posix(),
                eligible_for_scientific_analysis=False,
                qc_status=QCStatus.VALID,
            )
            sample_records.extend([sweep_meta.to_dict(), multisine_meta.to_dict()])
            sample_counter += 1

    manifest = {
        **SCHEMA_VERSION_QUARTET,
        "mock_schema_version": "1.2.0",
        "mock_only": True,
        "scientific_use": "PROHIBITED: generated data only validate software behavior.",
        "known_system": "known_transfer_db in acoustic_encoder.mock_data",
        "recording_delay_samples": recording_delay_samples,
        "sampling_clock_drift_ppm": sampling_clock_drift_ppm,
        "recording_wav_format": recording_wav_format,
        "additive_noise_std": additive_noise_std,
        "missing_tone_frequencies_hz": missing_frequencies,
        "interference_tones_dbfs": interference,
        "stable_period_gain_db": gain_jitter,
        "stable_period_shift_samples": shift_jitter,
        "clipping_run_samples": clipping_run_samples,
        "stimulus_manifest": stimulus_artifacts.manifest_path.as_posix(),
        "samples": sample_records,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path

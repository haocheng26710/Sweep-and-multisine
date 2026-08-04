"""S3 mock inputs for development; never valid as scientific evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import NDArray
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
    *,
    angle_deg: float,
    configuration: str,
    random_state: int,
    recording_delay_samples: int,
) -> tuple[int, FloatArray]:
    sample_rate, audio = _read_wav_float(stimulus_wav)
    frequency = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    transfer_db = known_transfer_db(frequency, angle_deg=angle_deg, configuration=configuration)
    transfer_linear = 10.0 ** (transfer_db / 20.0)
    recording = np.fft.irfft(np.fft.rfft(audio) * transfer_linear, n=audio.size)
    generator = np.random.default_rng(random_state)
    recording += generator.normal(0.0, 2.0e-5, size=recording.size)
    if np.max(np.abs(recording)) >= 1.0:
        raise RuntimeError("Mock recording clipped; lower the synthetic transfer gain")
    if recording_delay_samples < 0:
        raise ValueError("recording_delay_samples cannot be negative")
    recording = np.pad(recording, (recording_delay_samples, 0))
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
                angle_deg=float(angle),
                configuration=configuration,
                random_state=random_state + sample_counter,
                recording_delay_samples=recording_delay_samples,
            )
            audio_path = audio_root / f"{base_name}_MS.wav"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            wavfile.write(audio_path, sample_rate, recording.astype(np.float32))
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
        "mock_schema_version": "1.0.0",
        "mock_only": True,
        "scientific_use": "PROHIBITED: generated data only validate software behavior.",
        "known_system": "known_transfer_db in acoustic_encoder.mock_data",
        "recording_delay_samples": recording_delay_samples,
        "stimulus_manifest": stimulus_artifacts.manifest_path.as_posix(),
        "samples": sample_records,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path

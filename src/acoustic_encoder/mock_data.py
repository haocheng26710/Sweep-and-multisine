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
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCStatus,
    Representation,
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
        writer.writerow(["Frequency (Hz)", "Acoustic SPL (dB)", "Phase (deg)"])
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
    multisine_to_sweep_slope: float,
    multisine_to_sweep_intercept_db: float,
) -> tuple[int, FloatArray]:
    sample_rate, audio = _read_wav_float(stimulus_wav)
    frequency = np.fft.rfftfreq(audio.size, d=1.0 / sample_rate)
    transfer_db = known_transfer_db(frequency, angle_deg=angle_deg, configuration=configuration)
    if (
        not np.isfinite(multisine_to_sweep_slope)
        or multisine_to_sweep_slope <= 0.0
        or not np.isfinite(multisine_to_sweep_intercept_db)
    ):
        raise ValueError("cross-mode affine injection must have finite positive slope")
    transfer_db = (
        transfer_db - float(multisine_to_sweep_intercept_db)
    ) / float(multisine_to_sweep_slope)
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
    multisine_to_sweep_slope: float = 1.0,
    multisine_to_sweep_intercept_db: float = 0.0,
    session_id: str = "S01",
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

    if not session_id.strip() or any(character in session_id for character in "/\\"):
        raise ValueError("session_id must be one non-empty path-safe identifier")
    for configuration in configurations:
        for angle in angles_deg:
            base_name = f"V2_{configuration}_A{int(angle):03d}_{session_id}_CONT_R01"
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
                multisine_to_sweep_slope=multisine_to_sweep_slope,
                multisine_to_sweep_intercept_db=multisine_to_sweep_intercept_db,
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
                session_id=session_id,
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
                "stable_period_count": int(stimulus_config["stable_period_count"]),
                "discard_initial_period_count": int(
                    stimulus_config["discard_initial_period_count"]
                ),
                "recording_delay_samples": recording_delay_samples,
                "sampling_clock_drift_ppm": sampling_clock_drift_ppm,
                "recording_wav_format": recording_wav_format,
                "additive_noise_std": additive_noise_std,
                "missing_tone_frequencies_hz": missing_frequencies,
                "interference_tones_dbfs": interference,
                "stable_period_gain_db": gain_jitter,
                "stable_period_shift_samples": shift_jitter,
                "clipping_run_samples": clipping_run_samples,
                "multisine_to_sweep_slope": multisine_to_sweep_slope,
                "multisine_to_sweep_intercept_db": multisine_to_sweep_intercept_db,
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
                session_id=session_id,
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
        "mock_schema_version": "1.3.0",
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
        "multisine_to_sweep_slope": multisine_to_sweep_slope,
        "multisine_to_sweep_intercept_db": multisine_to_sweep_intercept_db,
        "session_id": session_id,
        "stimulus_manifest": stimulus_artifacts.manifest_path.as_posix(),
        "samples": sample_records,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def generate_directional_feature_set_mock(
    *,
    configuration: str = "U4ENC",
    direction_order_deg: Iterable[float] = (0.0, 90.0, 180.0, 270.0),
    feature_count: int = 71,
    random_state: int = 20260805,
    rank_mode: str = "directional",
    feature_kind: FeatureKind = FeatureKind.DENSE_DEMEANED_DB,
    repeat_noise_scale: float = 1.0,
    included_repeat_types: Iterable[str] = ("CONT", "REPOS", "REASM"),
    missing_feature_indices_by_sample: Mapping[str, Iterable[int]] | None = None,
) -> tuple[FeatureSet, ...]:
    """Build controlled P4 FeatureSets without creating raw TXT/WAV/SpectrumData."""
    if not isinstance(feature_count, int) or feature_count < 2:
        raise ValueError("feature_count must be an integer >= 2")
    directions = tuple(float(value) for value in direction_order_deg)
    if (
        not directions
        or any(not np.isfinite(value) or not 0.0 <= value < 360.0 for value in directions)
        or len(set(directions)) != len(directions)
    ):
        raise ValueError("direction_order_deg must contain unique angles in [0, 360)")
    repeat_types = tuple(str(value).upper() for value in included_repeat_types)
    unsupported = set(repeat_types) - {"CONT", "REPOS", "REASM"}
    if unsupported:
        raise ValueError(f"unsupported repeat types: {sorted(unsupported)}")
    if rank_mode not in {"directional", "rank_one", "orthogonal", "identical", "zero"}:
        raise ValueError(f"unsupported rank_mode: {rank_mode}")
    try:
        feature_kind = FeatureKind(feature_kind)
    except ValueError as exc:
        raise ValueError(f"unsupported feature_kind: {feature_kind!r}") from exc
    supported_feature_kinds = {
        FeatureKind.DENSE_RAW_SPL,
        FeatureKind.DENSE_DEMEANED_DB,
        FeatureKind.DENSE_ZSCORE,
        FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
    }
    if feature_kind not in supported_feature_kinds:
        raise ValueError(f"unsupported P4-A mock feature_kind: {feature_kind.value}")
    try:
        repeat_noise_scale = float(repeat_noise_scale)
    except (TypeError, ValueError) as exc:
        raise ValueError("repeat_noise_scale must be finite and non-negative") from exc
    if not np.isfinite(repeat_noise_scale) or repeat_noise_scale < 0.0:
        raise ValueError("repeat_noise_scale must be finite and non-negative")
    if rank_mode == "orthogonal" and feature_count < len(directions):
        raise ValueError("orthogonal rank_mode requires one feature per direction")

    frequency_hz = 1000.0 + 10.0 * np.arange(feature_count, dtype=np.float64)
    tone_kind = feature_kind in {
        FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
    }
    if tone_kind:
        feature_names = tuple(
            f"tone_{index:06d}_{int(frequency) if frequency.is_integer() else frequency:g}_hz"
            for index, frequency in enumerate(frequency_hz)
        )
        tone_set_id = f"DEV-C5-S3-TONES-{feature_count}"
        tone_set_sha256 = hashlib.sha256(
            np.asarray(frequency_hz, dtype="<f8").tobytes()
        ).hexdigest()
        tone_schema_id = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(feature_names, separators=(",", ":")).encode("ascii")
            ).hexdigest()
        )
    else:
        feature_names = tuple(
            f"f_{int(frequency) if frequency.is_integer() else frequency:g}_hz"
            for frequency in frequency_hz
        )
        tone_set_id = None
        tone_set_sha256 = None
        tone_schema_id = None
    missing_map = {
        str(sample_id): tuple(int(index) for index in indices)
        for sample_id, indices in (missing_feature_indices_by_sample or {}).items()
    }
    generator = np.random.default_rng(random_state)
    repeat_specs = (
        ("CONT", "S01", "R01", "P01", "AS01", "B01", 0.005),
        ("CONT", "S01", "R02", "P01", "AS01", "B01", 0.005),
        ("CONT", "S02", "R01", "P01", "AS01", "B02", 0.005),
        ("CONT", "S02", "R02", "P01", "AS01", "B02", 0.005),
        ("REPOS", "S01", "R01", "P01", "AS01", "B03", 0.04),
        ("REPOS", "S01", "R02", "P02", "AS01", "B04", 0.04),
        ("REASM", "S01", "R01", "P01", "AS01", "B05", 0.08),
        ("REASM", "S01", "R02", "P01", "AS02", "B06", 0.08),
    )
    features: list[FeatureSet] = []
    for direction_index, angle in enumerate(directions):
        if rank_mode == "directional":
            base = known_transfer_db(
                frequency_hz,
                angle_deg=angle,
                configuration=configuration,
            )
            base = base - np.mean(base)
        elif rank_mode == "rank_one":
            base = (direction_index + 1.0) * np.linspace(-1.0, 1.0, feature_count)
        elif rank_mode == "orthogonal":
            base = np.zeros(feature_count, dtype=np.float64)
            base[direction_index] = 1.0
        elif rank_mode == "identical":
            base = np.linspace(-1.0, 1.0, feature_count)
        else:
            base = np.zeros(feature_count, dtype=np.float64)

        for repeat_type, session, repeat_id, reposition, assembly, block, noise in repeat_specs:
            if repeat_type not in repeat_types:
                continue
            sample_id = (
                f"mock_{configuration}_A{int(round(angle)):03d}_{session}_"
                f"{repeat_type}_{repeat_id}_{reposition}_{assembly}_{block}"
            )
            values = np.asarray(
                base
                + generator.normal(
                    0.0,
                    noise * repeat_noise_scale,
                    feature_count,
                ),
                dtype=np.float64,
            )
            valid_mask = np.ones(feature_count, dtype=bool)
            for index in missing_map.get(sample_id, ()):
                if index < 0 or index >= feature_count:
                    raise ValueError(
                        f"missing feature index {index} is outside sample {sample_id}"
                    )
                valid_mask[index] = False
                values[index] = np.nan
            identity_payload = json.dumps(
                {
                    "sample_id": sample_id,
                    "random_state": random_state,
                    "rank_mode": rank_mode,
                    "values": values.tolist(),
                    "valid_mask": valid_mask.tolist(),
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            source_sha256 = hashlib.sha256(identity_payload).hexdigest()
            meta = MeasurementMeta(
                sample_id=sample_id,
                **SCHEMA_VERSION_QUARTET,
                device_version="V2",
                configuration=configuration,
                angle_deg=angle,
                session_id=session,
                repeat_type=repeat_type,
                repeat_id=repeat_id,
                reposition_round_id=reposition,
                assembly_id=assembly,
                acquisition_block_id=block,
                experiment_step="DEV_C5_P4A_MOCK",
                measurement_mode=(
                    MeasurementMode.SCHROEDER_MULTISINE
                    if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                    else MeasurementMode.REW_SWEEP
                ),
                source_format=(
                    SourceFormat.MOCK_AUDIO
                    if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                    else SourceFormat.MOCK_DENSE
                ),
                source_path=f"mock-feature://{sample_id}",
                data_origin=DataOrigin.SIMULATED,
                dataset_role=DatasetRole.SOFTWARE_VALIDATION,
                source_sha256=source_sha256,
                provenance_uri="mock-feature://DEV-C5-P4A",
                eligible_for_scientific_analysis=False,
                stimulus_id=(
                    "DEV-C5-S3-STIMULUS"
                    if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                    else None
                ),
                stimulus_hash=(
                    tone_set_sha256
                    if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                    else None
                ),
                tone_set_id=(
                    tone_set_id
                    if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                    else None
                ),
                sidecar_path=(
                    f"mock-feature://{sample_id}.json"
                    if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                    else None
                ),
                audio_channel=(
                    0
                    if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                    else None
                ),
                qc_status=QCStatus.VALID,
            )
            features.append(
                FeatureSet(
                    sample_id=sample_id,
                    feature_schema_version=SCHEMA_VERSION_QUARTET[
                        "feature_schema_version"
                    ],
                    feature_kind=feature_kind,
                    feature_names=feature_names,
                    values=values,
                    valid_mask=valid_mask,
                    units=("dB",) * feature_count,
                    source_measurement_mode=(
                        MeasurementMode.SCHROEDER_MULTISINE
                        if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                        else MeasurementMode.REW_SWEEP
                    ),
                    source_representation=(
                        Representation.SPARSE_TONES
                        if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                        else Representation.DENSE_SPECTRUM
                    ),
                    preprocessing_id=(
                        "sha256:"
                        + hashlib.sha256(
                            (
                                f"DEV-C5:{feature_count}:{rank_mode}:"
                                f"{feature_kind.value}:{repeat_noise_scale:.17g}"
                            ).encode("ascii")
                        ).hexdigest()
                    ),
                    meta=meta,
                    tone_set_id=tone_set_id,
                    tone_set_sha256=tone_set_sha256,
                    tone_schema_id=tone_schema_id,
                    normalization_method=("subtract_mean_db" if tone_kind else None),
                    source_magnitude_quantity=("transfer_gain" if tone_kind else None),
                    source_phase_status=(
                        PhaseStatus.RELATIVE_UNRELIABLE
                        if feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
                        else PhaseStatus.UNAVAILABLE if tone_kind else None
                    ),
                    source_qc_status=QCStatus.VALID,
                    source_qc_sha256=(
                        "sha256:"
                        + hashlib.sha256(f"QC:{sample_id}".encode("utf-8")).hexdigest()
                    ),
                    source_qc_eligible_for_downstream=True,
                )
            )
    return tuple(features)

"""P1/P8 adapter for synchronized multisine transfer estimation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from .multisine_estimation import estimate_period_transfers
from .research_gate import RunPurpose, normalize_run_purpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    PhaseStatus,
    Representation,
    SpectrumData,
    artifact_sha256,
)


class MultisineImportError(ValueError):
    """Raised when multisine artifacts cannot form a valid tone spectrum."""


class MultisineConsistencyError(MultisineImportError):
    """Raised when recording, metadata, and stimulus artifacts disagree."""


class MultisineSynchronizationError(MultisineImportError):
    """Raised when complete stable periods cannot be synchronized."""


def _require_p8a_scope(
    run_purpose: str | RunPurpose,
    meta: MeasurementMeta,
) -> None:
    purpose = normalize_run_purpose(run_purpose)
    if (
        purpose is not RunPurpose.SOFTWARE_VALIDATION
        or meta.data_origin is not DataOrigin.SIMULATED
        or meta.dataset_role is not DatasetRole.SOFTWARE_VALIDATION
        or meta.eligible_for_scientific_analysis
    ):
        raise MultisineImportError(
            "P8-A accepts only simulated inputs for software_validation"
        )


def _validate_manifest_layout(manifest: dict) -> None:
    period_samples = int(manifest["period_samples"])
    if int(manifest["preamble_samples"]) <= 0:
        raise MultisineSynchronizationError(
            "P8-A synchronization requires a known preamble"
        )
    expected_analysis_start = (
        int(manifest["pre_silence_samples"])
        + int(manifest["preamble_samples"])
        + int(manifest["preamble_gap_samples"])
        + int(manifest["discard_initial_period_count"]) * period_samples
    )
    expected_analysis_count = int(manifest["stable_period_count"]) * period_samples
    if (
        int(manifest["analysis_start_sample"]) != expected_analysis_start
        or int(manifest["analysis_sample_count"]) != expected_analysis_count
    ):
        raise MultisineConsistencyError(
            "Multisine manifest period layout is inconsistent"
        )


def _validate_artifact_linkage(
    recording: Path,
    stimulus: Path,
    manifest: dict,
    sidecar: dict,
    meta: MeasurementMeta,
) -> None:
    comparisons = (
        ("period_samples", int(sidecar["period_samples"]), int(manifest["period_samples"])),
        ("sample rate", int(sidecar["sample_rate_hz"]), int(manifest["sample_rate_hz"])),
        ("tone_set_id", sidecar["tone_set_id"], manifest["tone_set_id"]),
        ("stimulus hash", sidecar["stimulus_hash"], manifest["waveform_sha256"]),
        ("stimulus_id", meta.stimulus_id, manifest["stimulus_id"]),
        ("tone_set_id", meta.tone_set_id, manifest["tone_set_id"]),
    )
    for label, actual, expected in comparisons:
        if actual != expected:
            raise MultisineConsistencyError(f"Multisine {label} mismatch")

    recording_hash = artifact_sha256(recording)
    if (
        recording_hash != meta.source_sha256
        or recording_hash != sidecar["recording_sha256"]
    ):
        raise MultisineConsistencyError(f"Multisine recording hash mismatch: {recording}")
    stimulus_hash = artifact_sha256(stimulus)
    if (
        stimulus_hash != manifest["waveform_sha256"]
        or stimulus_hash != meta.stimulus_hash
    ):
        raise MultisineConsistencyError("Multisine stimulus hash mismatch")


def _aggregate_period_transfers(
    transfer_by_period: np.ndarray,
    period_averaging: str,
) -> tuple[np.ndarray, np.ndarray | None]:
    if period_averaging == "complex_spectrum":
        averaged = np.mean(transfer_by_period, axis=0)
        return np.abs(averaged), np.angle(averaged)
    magnitude = np.sqrt(np.mean(np.abs(transfer_by_period) ** 2, axis=0))
    return magnitude, None


def _read_wav_float(path: Path) -> tuple[int, np.ndarray]:
    sample_rate, values = wavfile.read(path)
    if np.issubdtype(values.dtype, np.integer):
        scale = max(abs(np.iinfo(values.dtype).min), np.iinfo(values.dtype).max)
        audio = values.astype(np.float64) / scale
    else:
        audio = values.astype(np.float64)
    if audio.ndim != 1:
        raise MultisineImportError(f"Multisine WAV must be mono: {path}")
    return int(sample_rate), audio


def load_multisine_measurement(
    recording_path: str | Path,
    stimulus_manifest_path: str | Path,
    meta: MeasurementMeta,
    *,
    run_purpose: str | RunPurpose,
    period_averaging: str,
) -> SpectrumData:
    """Return a software-validation sparse tone transfer from one recording."""
    _require_p8a_scope(run_purpose, meta)
    if period_averaging not in {"complex_spectrum", "power"}:
        raise MultisineImportError(
            f"Unsupported period_averaging for P8-A: {period_averaging!r}"
        )

    recording = Path(recording_path)
    manifest_path = Path(stimulus_manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sidecar_path = Path(meta.sidecar_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    stimulus_path = manifest_path.parent / str(manifest["wav_file"])
    _validate_manifest_layout(manifest)
    _validate_artifact_linkage(recording, stimulus_path, manifest, sidecar, meta)

    recording_rate, recording_audio = _read_wav_float(recording)
    stimulus_rate, stimulus_audio = _read_wav_float(stimulus_path)
    manifest_rate = int(manifest["sample_rate_hz"])
    if recording_rate != stimulus_rate or recording_rate != manifest_rate:
        raise MultisineConsistencyError("Multisine sample rate mismatch")
    try:
        estimate = estimate_period_transfers(
            recording_audio,
            stimulus_audio,
            manifest,
        )
    except ValueError as exc:
        raise MultisineSynchronizationError(
            "Multisine recording does not contain complete stable periods"
        ) from exc

    magnitude_linear, phase_rad = _aggregate_period_transfers(
        estimate.transfer_by_period,
        period_averaging,
    )
    return SpectrumData(
        frequency_hz=estimate.frequency_hz,
        magnitude_db=20.0 * np.log10(magnitude_linear),
        magnitude_linear=magnitude_linear,
        magnitude_quantity="transfer_ratio",
        magnitude_reference=f"sha256:{manifest['waveform_sha256']}",
        phase_rad=phase_rad,
        valid_mask=np.ones(estimate.frequency_hz.size, dtype=bool),
        representation=Representation.SPARSE_TONES,
        phase_status=PhaseStatus.RELATIVE_UNRELIABLE,
        quality_metrics={
            "synchronization_method": "preamble_cross_correlation",
            "preamble_start_sample": estimate.preamble_start_sample,
            "first_period_start_sample": estimate.first_period_start_sample,
            "analysis_start_sample": estimate.analysis_start_sample,
            "period_samples": estimate.period_samples,
            "discarded_period_count": estimate.discarded_period_count,
            "stable_period_count": estimate.stable_period_count,
            "period_averaging": period_averaging,
            "clock_drift": "unavailable",
            "missing_tones": "unavailable",
            "clipping": "unavailable",
            "leakage": "unavailable",
        },
        meta=meta,
    )

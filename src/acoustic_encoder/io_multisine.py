"""P1/P8 adapter for synchronized multisine transfer estimation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import wavfile

from .clock_drift import (
    ClockDriftEstimate,
    ClockDriftEstimationError,
    classify_clock_drift,
    correct_recording_time_axis,
    estimate_clock_drift,
)
from .multisine_estimation import PeriodTransferEstimate, estimate_period_transfers
from .multisine_qc import (
    MultisineQCAnalysis,
    analyze_clipping,
    evaluate_tone_and_audio_quality,
)
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


class MultisineClockDriftError(MultisineImportError):
    """Raised when clock drift cannot be estimated or corrected auditably."""


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


@dataclass(frozen=True, slots=True)
class _DecodedWav:
    sample_rate_hz: int
    audio: np.ndarray
    sample_format: str


@dataclass(frozen=True, slots=True)
class _BaseMultisineAnalysis:
    spectrum: SpectrumData
    estimate: PeriodTransferEstimate
    recording_audio: np.ndarray
    recording_sample_format: str


def _read_wav_float(path: Path, *, channel: int = 0) -> _DecodedWav:
    sample_rate, values = wavfile.read(path)
    sample_format = values.dtype.name
    if values.ndim == 2:
        if channel < 0 or channel >= values.shape[1]:
            raise MultisineImportError(
                f"Multisine WAV channel {channel} is unavailable: {path}"
            )
        values = values[:, channel]
    elif values.ndim != 1:
        raise MultisineImportError(f"Unsupported Multisine WAV layout: {path}")
    if np.issubdtype(values.dtype, np.unsignedinteger):
        midpoint = (float(np.iinfo(values.dtype).max) + 1.0) / 2.0
        audio = (values.astype(np.float64) - midpoint) / midpoint
    elif np.issubdtype(values.dtype, np.signedinteger):
        scale = max(abs(np.iinfo(values.dtype).min), np.iinfo(values.dtype).max)
        audio = values.astype(np.float64) / scale
    else:
        audio = values.astype(np.float64)
    return _DecodedWav(int(sample_rate), audio, sample_format)


def _clock_drift_snapshot(
    estimate: ClockDriftEstimate,
    *,
    decision: str,
    residual: bool = False,
) -> dict[str, Any]:
    prefix = "residual_" if residual else ""
    return {
        f"signed_{prefix}drift_ppm": estimate.signed_ppm,
        f"absolute_{prefix}drift_ppm": estimate.absolute_ppm,
        "period_timing_error_samples": estimate.period_timing_error_samples,
        "phase_fit_rmse_rad": estimate.phase_fit_rmse_rad,
        "period_count": estimate.period_count,
        "tone_count": estimate.tone_count,
        "decision": decision,
    }


def _process_multisine_measurement(
    recording_path: str | Path,
    stimulus_manifest_path: str | Path,
    meta: MeasurementMeta,
    *,
    run_purpose: str | RunPurpose,
    period_averaging: str,
    clock_drift_config: Mapping[str, Any] | None = None,
) -> _BaseMultisineAnalysis:
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

    recording_wav = _read_wav_float(recording, channel=int(meta.audio_channel))
    stimulus_wav = _read_wav_float(stimulus_path)
    recording_rate = recording_wav.sample_rate_hz
    recording_audio = recording_wav.audio
    stimulus_rate = stimulus_wav.sample_rate_hz
    stimulus_audio = stimulus_wav.audio
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
    phase_status = PhaseStatus.RELATIVE_UNRELIABLE
    clock_drift_metrics: str | dict[str, Any] = "unavailable"
    if clock_drift_config is not None:
        correction_mode = str(clock_drift_config["correction"])
        if correction_mode not in {"disabled", "enabled"}:
            raise MultisineImportError(
                f"Unsupported clock drift correction mode: {correction_mode!r}"
            )
        warning_ppm = float(clock_drift_config["warning_ppm"])
        exclude_ppm = float(clock_drift_config["exclude_candidate_ppm"])
        try:
            pre_drift = estimate_clock_drift(
                estimate.transfer_by_period,
                estimate.frequency_hz,
                sample_rate_hz=manifest_rate,
                period_samples=estimate.period_samples,
            )
        except ClockDriftEstimationError as exc:
            raise MultisineClockDriftError(str(exc)) from exc
        pre_decision = classify_clock_drift(
            pre_drift.signed_ppm,
            warning_ppm=warning_ppm,
            exclude_candidate_ppm=exclude_ppm,
        )
        correction_metrics: dict[str, Any] = {
            "mode": correction_mode,
            "applied": False,
            "successful": None,
            "method": None,
            "ratio": None,
            "input_sample_count": int(recording_audio.size),
            "output_sample_count": None,
            "failure_reason": None,
        }
        post_metrics: dict[str, Any] | None = None
        final_decision = pre_decision
        if correction_mode == "enabled":
            try:
                corrected_audio, correction_ratio = correct_recording_time_axis(
                    recording_audio,
                    signed_drift_ppm=pre_drift.signed_ppm,
                )
                corrected_estimate = estimate_period_transfers(
                    corrected_audio,
                    stimulus_audio,
                    manifest,
                )
                residual_drift = estimate_clock_drift(
                    corrected_estimate.transfer_by_period,
                    corrected_estimate.frequency_hz,
                    sample_rate_hz=manifest_rate,
                    period_samples=corrected_estimate.period_samples,
                )
            except (ClockDriftEstimationError, ValueError) as exc:
                raise MultisineClockDriftError(
                    f"Clock drift correction could not be re-estimated: {exc}"
                ) from exc
            post_decision = classify_clock_drift(
                residual_drift.signed_ppm,
                warning_ppm=warning_ppm,
                exclude_candidate_ppm=exclude_ppm,
            )
            corrected_magnitude, corrected_phase = _aggregate_period_transfers(
                corrected_estimate.transfer_by_period,
                period_averaging,
            )
            pre_magnitude_db = 20.0 * np.log10(
                np.maximum(magnitude_linear, np.finfo(float).tiny)
            )
            post_magnitude_db = 20.0 * np.log10(
                np.maximum(corrected_magnitude, np.finfo(float).tiny)
            )
            magnitude_change_db = post_magnitude_db - pre_magnitude_db
            correction_successful = post_decision.value == "valid"
            correction_metrics = {
                "mode": correction_mode,
                "applied": True,
                "successful": correction_successful,
                "method": "quintic_spline_time_axis_resampling",
                "ratio": correction_ratio,
                "input_sample_count": int(recording_audio.size),
                "output_sample_count": int(corrected_audio.size),
                "failure_reason": (
                    None
                    if correction_successful
                    else "residual_drift_not_below_warning_threshold"
                ),
            }
            post_metrics = {
                **_clock_drift_snapshot(
                    residual_drift,
                    decision=post_decision.value,
                    residual=True,
                ),
                "magnitude_change_max_abs_db": float(
                    np.max(np.abs(magnitude_change_db))
                ),
                "magnitude_change_rms_db": float(
                    np.sqrt(np.mean(magnitude_change_db**2))
                ),
            }
            final_decision = post_decision
            estimate = corrected_estimate
            magnitude_linear = corrected_magnitude
            phase_rad = corrected_phase
            if correction_successful and period_averaging == "complex_spectrum":
                phase_status = PhaseStatus.DRIFT_CORRECTED
        clock_drift_metrics = {
            "qc_schema_version": "1.0.0",
            "estimator_method": "adjacent_period_cross_phase_slope",
            "thresholds": {
                "warning_ppm": warning_ppm,
                "exclude_candidate_ppm": exclude_ppm,
                "boundary_policy": "absolute_ppm_greater_than_or_equal",
            },
            "pre_correction": _clock_drift_snapshot(
                pre_drift,
                decision=pre_decision.value,
            ),
            "correction": correction_metrics,
            "post_correction": post_metrics,
            "final_decision": final_decision.value,
            "phase_status": phase_status.value,
        }
    spectrum = SpectrumData(
        frequency_hz=estimate.frequency_hz,
        magnitude_db=20.0 * np.log10(magnitude_linear),
        magnitude_linear=magnitude_linear,
        magnitude_quantity="transfer_ratio",
        magnitude_reference=f"sha256:{manifest['waveform_sha256']}",
        phase_rad=phase_rad,
        valid_mask=np.ones(estimate.frequency_hz.size, dtype=bool),
        representation=Representation.SPARSE_TONES,
        phase_status=phase_status,
        quality_metrics={
            "synchronization_method": "preamble_cross_correlation",
            "preamble_start_sample": estimate.preamble_start_sample,
            "first_period_start_sample": estimate.first_period_start_sample,
            "analysis_start_sample": estimate.analysis_start_sample,
            "period_samples": estimate.period_samples,
            "discarded_period_count": estimate.discarded_period_count,
            "stable_period_count": estimate.stable_period_count,
            "period_averaging": period_averaging,
            "clock_drift": clock_drift_metrics,
            "missing_tones": "unavailable",
            "clipping": "unavailable",
            "leakage": "unavailable",
        },
        meta=meta,
    )
    return _BaseMultisineAnalysis(
        spectrum=spectrum,
        estimate=estimate,
        recording_audio=recording_audio,
        recording_sample_format=recording_wav.sample_format,
    )


def load_multisine_measurement(
    recording_path: str | Path,
    stimulus_manifest_path: str | Path,
    meta: MeasurementMeta,
    *,
    run_purpose: str | RunPurpose,
    period_averaging: str,
    clock_drift_config: Mapping[str, Any] | None = None,
) -> SpectrumData:
    """Return a software-validation sparse tone transfer from one recording."""
    return _process_multisine_measurement(
        recording_path,
        stimulus_manifest_path,
        meta,
        run_purpose=run_purpose,
        period_averaging=period_averaging,
        clock_drift_config=clock_drift_config,
    ).spectrum


def analyze_multisine_measurement(
    recording_path: str | Path,
    stimulus_manifest_path: str | Path,
    meta: MeasurementMeta,
    *,
    run_purpose: str | RunPurpose,
    period_averaging: str,
    clock_drift_config: Mapping[str, Any] | None,
    tone_quality_config: Mapping[str, Any],
) -> MultisineQCAnalysis:
    """Return the sparse transfer plus non-destructive P8-B2 QC evidence."""
    base = _process_multisine_measurement(
        recording_path,
        stimulus_manifest_path,
        meta,
        run_purpose=run_purpose,
        period_averaging=period_averaging,
        clock_drift_config=clock_drift_config,
    )
    clipping_metrics = analyze_clipping(
        base.recording_audio,
        tone_quality_config["clipping"],
        channel=int(meta.audio_channel),
        sample_format=base.recording_sample_format,
    )
    records, measurement_qc, valid_mask = evaluate_tone_and_audio_quality(
        base.estimate,
        base.spectrum.magnitude_db,
        tone_quality_config,
        clipping_metrics=clipping_metrics,
        clock_drift_metrics=base.spectrum.quality_metrics["clock_drift"],
    )
    quality_metrics = dict(base.spectrum.quality_metrics)
    quality_metrics.update(
        {
            "p8_qc": measurement_qc,
            "tone_quality": [record.to_dict() for record in records],
            "clipping": clipping_metrics,
            "missing_tones": {
                "count": measurement_qc["missing_tone_count"],
                "unavailable_count": measurement_qc[
                    "missing_tone_unavailable_count"
                ],
            },
            "leakage": {
                "method": "local_non_excited_bin_energy_over_tone_bin_energy",
                "guard_bins": int(
                    tone_quality_config["neighborhood"]["tone_guard_bins"]
                ),
                "radius_bins": int(
                    tone_quality_config["neighborhood"]["leakage_radius_bins"]
                ),
            },
            "non_excited_energy": measurement_qc["non_excited_energy"],
        }
    )
    spectrum = SpectrumData(
        frequency_hz=base.spectrum.frequency_hz,
        magnitude_db=base.spectrum.magnitude_db,
        magnitude_linear=base.spectrum.magnitude_linear,
        magnitude_quantity=base.spectrum.magnitude_quantity,
        magnitude_reference=base.spectrum.magnitude_reference,
        phase_rad=base.spectrum.phase_rad,
        valid_mask=valid_mask,
        representation=base.spectrum.representation,
        phase_status=base.spectrum.phase_status,
        quality_metrics=quality_metrics,
        meta=base.spectrum.meta,
    )
    return MultisineQCAnalysis(
        spectrum=spectrum,
        tone_quality=records,
        measurement_qc=measurement_qc,
        estimate=base.estimate,
        clipping_metrics=clipping_metrics,
    )

"""P1 adapters that normalize both measurement modes to ``SpectrumData``."""

from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
from typing import Any, Mapping

from .io_multisine import MultisineImportError, analyze_multisine_measurement
from .multisine_qc import MultisineQCAnalysis
from .research_gate import enforce_research_gate
from .schemas import (
    MeasurementMeta,
    MeasurementMode,
    SourceFormat,
    SpectrumData,
)


class P1AdapterError(ValueError):
    """Raised when measurement artifacts cannot enter a P1 adapter."""


class P1ManualReviewRequired(P1AdapterError):
    """Raised when metadata explicitly requires human review."""

    def __init__(self, message: str, *, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__(message)


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise P1AdapterError(f"Missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P1AdapterError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise P1AdapterError(f"{label} must contain a JSON object: {path}")
    return payload


def _measurement_meta_from_sidecar(
    sidecar: Mapping[str, Any],
    sidecar_path: Path,
) -> MeasurementMeta:
    names = {field.name for field in fields(MeasurementMeta)}
    try:
        meta = MeasurementMeta.from_dict(
            {name: value for name, value in sidecar.items() if name in names}
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise P1AdapterError(f"Invalid multisine sidecar metadata: {sidecar_path}") from exc
    if meta.manual_review_reasons:
        raise P1ManualReviewRequired(
            f"Multisine sidecar requires manual review: {sidecar_path}",
            reasons=meta.manual_review_reasons,
        )
    return meta


def analyze_multisine_adapter(
    recording_wav: str | Path,
    sidecar_metadata: str | Path,
    stimulus_manifest: str | Path | None,
    resolved_config: Mapping[str, Any],
) -> MultisineQCAnalysis:
    """Validate P1 linkage once, then delegate all signal work to P8."""
    recording = Path(recording_wav).resolve()
    sidecar_path = Path(sidecar_metadata).resolve()
    if not recording.is_file():
        raise P1AdapterError(f"Missing multisine recording: {recording}")
    sidecar = _read_json_mapping(sidecar_path, "multisine sidecar")
    required = {
        "stimulus_id",
        "stimulus_hash",
        "tone_set_id",
        "sample_rate_hz",
        "period_samples",
        "stable_period_count",
        "discard_initial_period_count",
        "audio_channel",
        "source_format",
    }
    missing = sorted(name for name in required if name not in sidecar)
    if missing:
        raise P1AdapterError(f"Multisine sidecar fields are missing: {missing}")
    audio_channel = sidecar["audio_channel"]
    if (
        isinstance(audio_channel, bool)
        or not isinstance(audio_channel, int)
        or audio_channel < 0
    ):
        raise P1AdapterError("Multisine audio_channel must be a non-negative integer")
    meta = _measurement_meta_from_sidecar(sidecar, sidecar_path)
    if meta.measurement_mode is not MeasurementMode.SCHROEDER_MULTISINE:
        raise P1AdapterError("Multisine adapter requires schroeder_multisine metadata")
    if meta.source_format not in {SourceFormat.MOCK_AUDIO, SourceFormat.MULTISINE_WAV}:
        raise P1AdapterError(
            f"Unsupported multisine source_format: {meta.source_format.value}"
        )
    if Path(meta.source_path).resolve() != recording:
        raise P1AdapterError("Multisine sidecar source_path does not match recording")
    if Path(str(meta.sidecar_path)).resolve() != sidecar_path:
        raise P1AdapterError("Multisine metadata sidecar_path does not match sidecar")
    enforce_research_gate(resolved_config["run_purpose"], [meta])

    stimulus_id = str(sidecar["stimulus_id"])
    try:
        stimulus_root = Path(resolved_config["paths"]["stimuli"]).resolve()
    except (KeyError, TypeError) as exc:
        raise P1AdapterError("Resolved config requires paths.stimuli") from exc
    canonical_manifest = (
        stimulus_root / stimulus_id / "stimulus_manifest.json"
    ).resolve()
    sidecar_manifest = sidecar.get("stimulus_manifest")
    if (
        sidecar_manifest is not None
        and Path(str(sidecar_manifest)).resolve() != canonical_manifest
    ):
        raise P1AdapterError("Multisine sidecar stimulus_manifest mismatch")
    manifest_path = (
        canonical_manifest
        if stimulus_manifest is None
        else Path(stimulus_manifest).resolve()
    )
    if manifest_path != canonical_manifest:
        raise P1AdapterError(
            "Explicit stimulus manifest does not match the canonical stimulus_id path"
        )
    manifest = _read_json_mapping(manifest_path, "stimulus manifest")

    estimation = resolved_config.get("multisine_estimation")
    if not isinstance(estimation, Mapping):
        raise P1AdapterError("Resolved config requires multisine_estimation")
    try:
        comparisons = (
            ("stimulus_id", sidecar["stimulus_id"], manifest["stimulus_id"]),
            ("stimulus hash", sidecar["stimulus_hash"], manifest["waveform_sha256"]),
            ("tone_set_id", sidecar["tone_set_id"], manifest["tone_set_id"]),
            (
                "configured stimulus_id",
                resolved_config["stimulus_id"],
                manifest["stimulus_id"],
            ),
            (
                "configured tone_set_id",
                resolved_config["tone_set_id"],
                manifest["tone_set_id"],
            ),
            (
                "configured sample rate",
                int(resolved_config["sample_rate_hz"]),
                int(manifest["sample_rate_hz"]),
            ),
            (
                "sample rate",
                int(sidecar["sample_rate_hz"]),
                int(manifest["sample_rate_hz"]),
            ),
            (
                "period_samples",
                int(sidecar["period_samples"]),
                int(manifest["period_samples"]),
            ),
            (
                "stable period count",
                int(sidecar["stable_period_count"]),
                int(manifest["stable_period_count"]),
            ),
            (
                "discard period count",
                int(sidecar["discard_initial_period_count"]),
                int(manifest["discard_initial_period_count"]),
            ),
            (
                "configured stable period count",
                int(estimation["stable_period_count"]),
                int(manifest["stable_period_count"]),
            ),
            (
                "configured discard period count",
                int(estimation["discard_initial_period_count"]),
                int(manifest["discard_initial_period_count"]),
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise P1AdapterError(
            "Invalid multisine manifest/config linkage fields"
        ) from exc
    for label, actual, expected in comparisons:
        if actual != expected:
            raise P1AdapterError(f"Multisine {label} mismatch")

    try:
        return analyze_multisine_measurement(
            recording,
            manifest_path,
            meta,
            run_purpose=resolved_config["run_purpose"],
            period_averaging=str(estimation["period_averaging"]),
            clock_drift_config=estimation.get("clock_drift"),
            tone_quality_config=estimation["tone_quality"],
        )
    except MultisineImportError as exc:
        raise P1AdapterError(str(exc)) from exc


def load_multisine_measurement(
    recording_wav: str | Path,
    sidecar_metadata: str | Path,
    stimulus_manifest: str | Path | None,
    resolved_config: Mapping[str, Any],
) -> SpectrumData:
    """Return the canonical sparse spectrum from the P1 multisine adapter."""
    return analyze_multisine_adapter(
        recording_wav,
        sidecar_metadata,
        stimulus_manifest,
        resolved_config,
    ).spectrum

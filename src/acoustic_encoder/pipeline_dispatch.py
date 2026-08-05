"""Unified P1 dispatcher for V2 sweep and multisine measurements."""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
from pathlib import Path
from typing import Any, Mapping

from .io_rew import load_rew_measurement
from .multisine_qc import MultisineQCAnalysis
from .p1_adapters import P1AdapterError, analyze_multisine_adapter
from .schemas import MeasurementMeta, MeasurementMode, SpectrumData


@dataclass(frozen=True, slots=True)
class AdapterResult:
    spectrum: SpectrumData
    multisine_analysis: MultisineQCAnalysis | None


def read_measurement_meta(path: str | Path) -> MeasurementMeta:
    path = Path(path).resolve()
    if not path.is_file():
        raise P1AdapterError(f"Missing measurement metadata: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P1AdapterError(f"Invalid measurement metadata: {path}") from exc
    if not isinstance(payload, dict):
        raise P1AdapterError(f"Measurement metadata must be a JSON object: {path}")
    names = {field.name for field in fields(MeasurementMeta)}
    try:
        return MeasurementMeta.from_dict(
            {name: value for name, value in payload.items() if name in names}
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise P1AdapterError(f"Invalid measurement metadata schema: {path}") from exc


def dispatch_measurement(
    source_path: str | Path,
    metadata_path: str | Path,
    resolved_config: Mapping[str, Any],
    *,
    stimulus_manifest: str | Path | None = None,
) -> AdapterResult:
    """Route one measurement through the matching P1 adapter exactly once."""
    source = Path(source_path).resolve()
    metadata = Path(metadata_path).resolve()
    meta = read_measurement_meta(metadata)
    configured_mode = MeasurementMode(str(resolved_config["measurement_mode"]))
    if meta.measurement_mode is not configured_mode:
        raise P1AdapterError(
            "Configured measurement_mode does not match measurement metadata"
        )
    if configured_mode is MeasurementMode.REW_SWEEP:
        spectrum = load_rew_measurement(
            source,
            meta,
            run_purpose=resolved_config["run_purpose"],
        )
        return AdapterResult(spectrum=spectrum, multisine_analysis=None)
    analysis = analyze_multisine_adapter(
        source,
        metadata,
        stimulus_manifest,
        resolved_config,
    )
    return AdapterResult(
        spectrum=analysis.spectrum,
        multisine_analysis=analysis,
    )

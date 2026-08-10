"""P1 adapter for REW frequency-response TXT exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np

from .research_gate import RunPurpose, enforce_research_gate
from .schemas import (
    MeasurementMeta,
    PhaseStatus,
    Representation,
    SpectrumData,
    artifact_sha256,
)

_REW_UNAVAILABLE_QC = {
    "headroom": "unavailable",
    "noise_floor": "unavailable",
    "raw_waveform": "unavailable",
    "impulse_response": "unavailable",
    "window": "unavailable",
}


class REWImportError(ValueError):
    """Raised when a REW TXT file cannot form a valid frequency response."""


class UnsupportedREWDataTypeError(REWImportError):
    """Raised when a non-acoustic REW export reaches the SPL adapter."""


class REWManualReviewRequired(REWImportError):
    """Raised when a REW export is too ambiguous for automatic import."""

    def __init__(self, message: str, *, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class REWPreflightResult:
    source_path: Path
    source_sha256: str
    data_point_count: int
    column_count: int
    has_phase: bool
    minimum_frequency_hz: float
    maximum_frequency_hz: float


def inspect_rew_frequency_response(path: str | Path) -> REWPreflightResult:
    """Read-only preflight using the canonical REW parser and type checks."""
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"REW TXT file does not exist: {source}")
    if source.suffix.casefold() != ".txt":
        raise REWImportError(f"REW input must use the .txt extension: {source}")
    if source.stat().st_size == 0:
        raise REWImportError(f"REW TXT file is empty: {source}")
    values, descriptor_text = _parse_numeric_rows(source)
    _require_acoustic_spl(descriptor_text, source)
    _validate_frequency(values, source)
    return REWPreflightResult(
        source_path=source,
        source_sha256=artifact_sha256(source),
        data_point_count=int(values.shape[0]),
        column_count=int(values.shape[1]),
        has_phase=values.shape[1] == 3,
        minimum_frequency_hz=float(values[0, 0]),
        maximum_frequency_hz=float(values[-1, 0]),
    )


def _parse_numeric_rows(source: Path) -> tuple[np.ndarray, str]:
    rows: list[list[float]] = []
    descriptors: list[str] = []
    expected_columns: int | None = None
    for line_number, line in enumerate(
        source.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("*", "#")):
            descriptors.append(stripped[1:].strip())
            continue
        fields = re.split(r"[\s,;]+", stripped)
        try:
            parsed_row = [float(value) for value in fields]
        except ValueError as exc:
            if not rows:
                descriptors.append(stripped)
                continue
            raise REWImportError(
                f"REW TXT has non-numeric data at line {line_number}: {source}"
            ) from exc
        if len(fields) not in {2, 3}:
            raise REWImportError(
                f"REW TXT data must have 2 or 3 columns at line {line_number}: {source}"
            )
        if expected_columns is None:
            expected_columns = len(fields)
        elif len(fields) != expected_columns:
            raise REWImportError(
                f"REW TXT has inconsistent column count at line {line_number}: {source}"
            )
        rows.append(parsed_row)
    if not rows:
        raise REWImportError(f"REW TXT contains no numeric data: {source}")
    descriptor_text = re.sub(r"[_\W]+", " ", " ".join(descriptors).casefold())
    return np.asarray(rows, dtype=np.float64), descriptor_text


def _require_acoustic_spl(descriptor_text: str, source: Path) -> None:
    if re.search(r"\bimpedance\b|\bohms?\b", descriptor_text):
        raise UnsupportedREWDataTypeError(
            f"REW impedance data cannot enter the acoustic SPL path: {source}"
        )
    acoustic_spl_confirmed = bool(re.search(r"\bspl\b", descriptor_text)) or (
        "acoustic" in descriptor_text and bool(re.search(r"\bdb\b", descriptor_text))
    )
    if not acoustic_spl_confirmed:
        raise REWManualReviewRequired(
            f"REW TXT cannot confirm acoustic SPL data type: {source}",
            reasons=("unconfirmed_rew_data_type",),
        )


def _validate_frequency(values: np.ndarray, source: Path) -> None:
    if values.shape[0] < 5:
        raise REWImportError(f"REW TXT requires at least 5 data points: {source}")
    frequency = values[:, 0]
    if not np.all(np.isfinite(frequency)):
        raise REWImportError(f"REW frequencies must be finite: {source}")
    if not np.all(np.diff(frequency) > 0):
        raise REWImportError(
            f"REW frequencies must be strictly increasing and unique: {source}"
        )


def load_rew_measurement(
    path: str | Path,
    meta: MeasurementMeta,
    *,
    run_purpose: str | RunPurpose,
) -> SpectrumData:
    """Load one REW frequency-response export through the canonical P1 interface."""
    source = Path(path)
    if meta.manual_review_reasons:
        raise REWManualReviewRequired(
            f"REW metadata requires manual review before import: {source}",
            reasons=meta.manual_review_reasons,
        )
    enforce_research_gate(run_purpose, [meta])
    if artifact_sha256(source) != meta.source_sha256:
        raise REWImportError(f"REW source hash mismatch: {source}")

    values, descriptor_text = _parse_numeric_rows(source)
    _require_acoustic_spl(descriptor_text, source)
    _validate_frequency(values, source)
    has_phase = values.shape[1] == 3
    return SpectrumData(
        frequency_hz=values[:, 0],
        magnitude_db=values[:, 1],
        phase_rad=np.deg2rad(values[:, 2]) if has_phase else None,
        valid_mask=np.ones(values.shape[0], dtype=bool),
        representation=Representation.DENSE_SPECTRUM,
        phase_status=(
            PhaseStatus.RELATIVE_UNRELIABLE if has_phase else PhaseStatus.UNAVAILABLE
        ),
        quality_metrics=dict(_REW_UNAVAILABLE_QC),
        magnitude_quantity="spl",
        meta=meta,
    )

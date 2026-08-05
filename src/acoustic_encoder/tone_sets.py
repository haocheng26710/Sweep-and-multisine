"""Authoritative, hash-verified multisine tone-set definitions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import NDArray

from .schemas import artifact_sha256


FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


class ToneSetValidationError(ValueError):
    """Raised when manifest and tone artifacts cannot prove one tone set."""


@dataclass(frozen=True, slots=True)
class ToneDefinition:
    tone_index: int
    frequency_hz: float
    frequency_text: str
    dft_bin: int
    amplitude_weight: float
    phase_rad: float


@dataclass(frozen=True, slots=True)
class ToneSetDefinition:
    tone_set_id: str
    sample_rate_hz: int
    period_samples: int
    tones: tuple[ToneDefinition, ...]
    tones_sha256: str
    tone_set_sha256: str
    manifest_sha256: str
    manifest_path: Path
    tones_path: Path
    verified_artifacts: bool

    @property
    def frequency_hz(self) -> FloatArray:
        return np.asarray(
            [tone.frequency_hz for tone in self.tones], dtype=np.float64
        )

    @property
    def dft_bins(self) -> IntArray:
        return np.asarray([tone.dft_bin for tone in self.tones], dtype=np.int64)

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(
            f"tone_{tone.tone_index:06d}_{tone.frequency_text}_hz"
            for tone in self.tones
        )


def canonical_frequency_text(value: str | float | Decimal) -> str:
    """Return a locale-independent, non-exponent decimal tone frequency."""
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise ToneSetValidationError(f"Invalid tone frequency: {value!r}") from exc
    if not decimal.is_finite() or decimal <= 0:
        raise ToneSetValidationError("tone frequency must be finite and positive")
    text = format(decimal.normalize(), "f")
    return "0" if text == "-0" else text


def _canonical_tone_set_payload(
    tone_set_id: str,
    sample_rate_hz: int,
    period_samples: int,
    tones: Iterable[ToneDefinition],
) -> dict[str, Any]:
    return {
        "tone_set_id": tone_set_id,
        "sample_rate_hz": sample_rate_hz,
        "period_samples": period_samples,
        "authoritative_ordering": "manifest_tone_index",
        "tones": [
            {
                "tone_index": tone.tone_index,
                "frequency_hz": tone.frequency_text,
                "dft_bin": tone.dft_bin,
            }
            for tone in tones
        ],
    }


def canonical_tone_set_sha256(
    tone_set_id: str,
    sample_rate_hz: int,
    period_samples: int,
    tones: Iterable[ToneDefinition],
) -> str:
    payload = _canonical_tone_set_payload(
        tone_set_id,
        sample_rate_hz,
        period_samples,
        tones,
    )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolved_frequencies(config: Mapping[str, Any]) -> FloatArray:
    tones = config["tones"]
    if tones["mode"] == "range":
        spacing = float(tones["spacing_hz"])
        return np.arange(
            float(tones["start_hz"]),
            float(tones["stop_hz"]) + 0.5 * spacing,
            spacing,
            dtype=np.float64,
        )
    return np.asarray(tones["frequencies_hz"], dtype=np.float64)


def _parse_tones(path: Path) -> tuple[ToneDefinition, ...]:
    required = (
        "tone_index",
        "frequency_hz",
        "dft_bin",
        "amplitude_weight",
        "phase_rad",
    )
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != required:
            raise ToneSetValidationError(
                "tones.csv columns must be exactly " + ", ".join(required)
            )
        rows = list(reader)
    if not rows:
        raise ToneSetValidationError("tones.csv contains no tones")

    tones: list[ToneDefinition] = []
    for expected_index, row in enumerate(rows):
        try:
            tone_index = int(row["tone_index"])
            dft_bin = int(row["dft_bin"])
            frequency_text = canonical_frequency_text(row["frequency_hz"])
            frequency = float(frequency_text)
            amplitude_weight = float(row["amplitude_weight"])
            phase_rad = float(row["phase_rad"])
        except (TypeError, ValueError) as exc:
            raise ToneSetValidationError(
                f"Invalid tones.csv row {expected_index}"
            ) from exc
        if tone_index != expected_index:
            raise ToneSetValidationError(
                "tones.csv tone_index order must be contiguous 0..N-1"
            )
        if dft_bin <= 0:
            raise ToneSetValidationError("tone dft_bin must be positive")
        if not math.isfinite(amplitude_weight) or amplitude_weight <= 0:
            raise ToneSetValidationError("tone amplitude_weight must be finite and positive")
        if not math.isfinite(phase_rad):
            raise ToneSetValidationError("tone phase_rad must be finite")
        tones.append(
            ToneDefinition(
                tone_index=tone_index,
                frequency_hz=frequency,
                frequency_text=frequency_text,
                dft_bin=dft_bin,
                amplitude_weight=amplitude_weight,
                phase_rad=phase_rad,
            )
        )
    frequencies = np.asarray([tone.frequency_hz for tone in tones])
    bins = np.asarray([tone.dft_bin for tone in tones])
    if np.any(~np.isfinite(frequencies)) or np.any(np.diff(frequencies) <= 0):
        raise ToneSetValidationError(
            "tone frequencies must be finite, unique, and strictly increasing in tone_index order"
        )
    if np.unique(bins).size != bins.size:
        raise ToneSetValidationError("tone dft_bin values must be unique")
    return tuple(tones)


def load_tone_set(
    manifest_path: str | Path,
    *,
    require_artifact_hashes: bool = True,
) -> ToneSetDefinition:
    """Load and cross-check a P7 manifest plus its authoritative tones.csv."""
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    tone_reference = Path(str(manifest.get("tones_file", "")))
    if not tone_reference.name or tone_reference.is_absolute() or len(tone_reference.parts) != 1:
        raise ToneSetValidationError("manifest tones_file must name a sibling artifact")
    tones_path = path.parent / tone_reference
    if not tones_path.is_file():
        raise ToneSetValidationError(f"tone artifact is missing: {tones_path}")

    actual_tones_sha256 = artifact_sha256(tones_path)
    declared_tones_sha256 = manifest.get("tones_sha256")
    declared_tone_set_sha256 = manifest.get("tone_set_sha256")
    if require_artifact_hashes and (
        not declared_tones_sha256 or not declared_tone_set_sha256
    ):
        raise ToneSetValidationError(
            "formal tone-set loading requires tones_sha256 and tone_set_sha256"
        )
    if declared_tones_sha256 is not None and declared_tones_sha256 != actual_tones_sha256:
        raise ToneSetValidationError("tones.csv SHA-256 mismatch")

    tones = _parse_tones(tones_path)
    tone_set_id = str(manifest.get("tone_set_id", ""))
    if not tone_set_id:
        raise ToneSetValidationError("manifest tone_set_id is required")
    sample_rate_hz = int(manifest["sample_rate_hz"])
    period_samples = int(manifest["period_samples"])
    if int(manifest.get("tone_count", -1)) != len(tones):
        raise ToneSetValidationError("manifest tone_count does not match tones.csv")

    expected_frequency = np.asarray(
        [tone.dft_bin * sample_rate_hz / period_samples for tone in tones],
        dtype=np.float64,
    )
    actual_frequency = np.asarray([tone.frequency_hz for tone in tones])
    tolerance = np.maximum(1.0e-9, np.abs(expected_frequency) * 1.0e-12)
    if np.any(np.abs(actual_frequency - expected_frequency) > tolerance):
        raise ToneSetValidationError(
            "tone frequency and DFT bin are inconsistent with sample rate/period"
        )

    resolved = manifest.get("resolved_stimulus_config")
    if not isinstance(resolved, Mapping):
        raise ToneSetValidationError("manifest resolved_stimulus_config is required")
    if str(resolved.get("tone_set_id", "")) != tone_set_id:
        raise ToneSetValidationError(
            "manifest tone_set_id does not match resolved stimulus config"
        )
    resolved_frequency = _resolved_frequencies(resolved)
    if resolved_frequency.size != actual_frequency.size or np.any(
        np.abs(resolved_frequency - actual_frequency) > tolerance
    ):
        raise ToneSetValidationError(
            "resolved stimulus tones do not match authoritative tones.csv"
        )

    actual_tone_set_sha256 = canonical_tone_set_sha256(
        tone_set_id,
        sample_rate_hz,
        period_samples,
        tones,
    )
    if (
        declared_tone_set_sha256 is not None
        and declared_tone_set_sha256 != actual_tone_set_sha256
    ):
        raise ToneSetValidationError("canonical tone_set SHA-256 mismatch")
    return ToneSetDefinition(
        tone_set_id=tone_set_id,
        sample_rate_hz=sample_rate_hz,
        period_samples=period_samples,
        tones=tones,
        tones_sha256=actual_tones_sha256,
        tone_set_sha256=actual_tone_set_sha256,
        manifest_sha256=artifact_sha256(path),
        manifest_path=path,
        tones_path=tones_path,
        verified_artifacts=(
            declared_tones_sha256 == actual_tones_sha256
            and declared_tone_set_sha256 == actual_tone_set_sha256
        ),
    )

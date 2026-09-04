"""V2.5 S1 single-entry HR01--HR08 calibration analysis.

The raw ZIP and extracted TXT/MDAT copies are immutable inputs.  TXT files are
preprocessed with the frozen FORMAL-1 200--8000 Hz, 48 PPo, 1/12-octave dB
contract.  Repeat suffixes 01--03 are user-declared block B01 and 04--06 are
block B02; no curve is automatically deleted.
"""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any, Mapping, Sequence
import zipfile

import numpy as np
from numpy.typing import NDArray

from .formal_preprocessing import (
    FORMAL_PREPROCESSING_ALGORITHM_VERSION,
    frozen_formal_preprocessing_contract,
    preprocess_formal_sweep,
)
from .formal_real_import import _header_contract, _parse_rew_member
from .schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCStatus,
    Representation,
    SourceFormat,
    SpectrumData,
    artifact_sha256,
)
from .version import (
    CONFIG_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    PIPELINE_VERSION,
)


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

V25S1_SCHEMA_VERSION = "v25_s1_single_module_v1"
V25S1_ZIP_SHA256 = "d14d373ec2019f9f692ecbbd845fb955a7bb3b61313aef4fe187cb563442fe42"
HISTORICAL_PRIMARY_FLOOR_P95_DB = 0.8792543414488713
HISTORICAL_SECONDARY_FLOOR_P95_DB = 1.345171254352607
_CONDITIONS = ("base", *(f"HR{index:02d}" for index in range(1, 9)))
_MODULES = tuple(condition for condition in _CONDITIONS if condition != "base")
_TARGETS_HZ = {
    "HR01": 1200.0, "HR02": 1500.0, "HR03": 1850.0, "HR04": 2250.0,
    "HR05": 2700.0, "HR06": 3200.0, "HR07": 3800.0, "HR08": 4500.0,
}
_PREDICTED_HZ = {
    "HR01": 1201.7, "HR02": 1501.7, "HR03": 1853.1, "HR04": 2254.5,
    "HR05": 2708.0, "HR06": 3212.9, "HR07": 3820.7, "HR08": 4527.3,
}
_NAME = re.compile(
    r"^R V2\.5_(?P<condition>base|HR0[1-8])_(?P<repeat>0[1-6])"
    r"(?P<extension>\.txt|\.mdat)$"
)


class V25S1InputError(ValueError):
    """Raised when V2.5 S1 identity, provenance or analysis contracts fail."""


@dataclass(frozen=True, slots=True)
class V25S1Member:
    archive_path: str
    filename: str
    condition_id: str
    repeat_number: int
    block_id: str
    block_repeat_number: int
    extension: str
    sha256: str
    size_bytes: int

    @property
    def sample_id(self) -> str:
        return (
            f"V25S1-{self.condition_id.upper()}-{self.block_id}-"
            f"R{self.block_repeat_number:02d}"
        )


@dataclass(frozen=True, slots=True)
class V25S1Inventory:
    zip_path: Path
    zip_sha256: str
    txt_members: tuple[V25S1Member, ...]
    mdat_members: tuple[V25S1Member, ...]
    condition_counts: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class V25S1RunResult:
    output_directory: Path
    measurement_count: int
    mdat_count: int
    structurally_valid_count: int
    flagged_count: int
    stable_target_signature_count: int
    selected_u4_stable_count: int
    artifact_count: int


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_v25_s1_filename(filename: str) -> tuple[str, int, str, int]:
    """Return condition, global repeat, user-frozen block and within-block repeat."""
    match = _NAME.fullmatch(filename)
    if match is None:
        raise V25S1InputError(f"cannot reliably identify V2.5 condition/repeat: {filename}")
    repeat = int(match.group("repeat"))
    block = "B01" if repeat <= 3 else "B02"
    block_repeat = repeat if repeat <= 3 else repeat - 3
    return match.group("condition"), repeat, block, block_repeat


def inspect_v25_s1_archive(
    zip_path: str | Path,
    *,
    expected_zip_sha256: str = V25S1_ZIP_SHA256,
    extracted_txt_directory: str | Path | None = None,
    extracted_mdat_directory: str | Path | None = None,
) -> V25S1Inventory:
    """Inventory the exact 54 TXT + 54 MDAT V2.5 S1 archive and verify copies."""
    source = Path(zip_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"V2.5 S1 ZIP does not exist: {source}")
    actual_zip_sha = _sha256_file(source)
    if actual_zip_sha != expected_zip_sha256:
        raise V25S1InputError(
            f"V2.5 S1 ZIP SHA-256 mismatch: expected {expected_zip_sha256}, "
            f"found {actual_zip_sha}"
        )
    members: list[V25S1Member] = []
    with zipfile.ZipFile(source, "r") as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in files]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise V25S1InputError(f"duplicate V2.5 archive paths: {duplicates}")
        for info in files:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts:
                raise V25S1InputError(f"unsafe V2.5 member path: {info.filename}")
            try:
                condition, repeat, block, block_repeat = parse_v25_s1_filename(path.name)
            except V25S1InputError as exc:
                raise V25S1InputError(
                    f"cannot reliably identify V2.5 archive member: {info.filename}"
                ) from exc
            payload = archive.read(info)
            members.append(V25S1Member(
                archive_path=info.filename,
                filename=path.name,
                condition_id=condition,
                repeat_number=repeat,
                block_id=block,
                block_repeat_number=block_repeat,
                extension=path.suffix.casefold(),
                sha256=_sha256_bytes(payload),
                size_bytes=len(payload),
            ))
    txt = sorted(
        (member for member in members if member.extension == ".txt"),
        key=lambda item: (_CONDITIONS.index(item.condition_id), item.repeat_number),
    )
    mdat = sorted(
        (member for member in members if member.extension == ".mdat"),
        key=lambda item: (_CONDITIONS.index(item.condition_id), item.repeat_number),
    )
    if len(txt) != 54 or len(mdat) != 54 or len(members) != 108:
        raise V25S1InputError(
            f"V2.5 S1 requires 54 TXT + 54 MDAT; found {len(txt)} + {len(mdat)}"
        )
    txt_ids = {(item.condition_id, item.repeat_number) for item in txt}
    mdat_ids = {(item.condition_id, item.repeat_number) for item in mdat}
    expected_ids = {(condition, repeat) for condition in _CONDITIONS for repeat in range(1, 7)}
    if txt_ids != expected_ids or mdat_ids != expected_ids:
        raise V25S1InputError("V2.5 TXT/MDAT condition-repeat pairing is incomplete")
    counts = Counter(item.condition_id for item in txt)
    expected_counts = {condition: 6 for condition in _CONDITIONS}
    if dict(counts) != expected_counts:
        raise V25S1InputError(f"V2.5 condition counts mismatch: {dict(counts)}")
    if len({item.sha256 for item in txt}) != len(txt):
        raise V25S1InputError("duplicate V2.5 TXT content")

    def verify_extracted(directory: str | Path, expected: Sequence[V25S1Member]) -> None:
        root = Path(directory).resolve()
        expected_names = sorted(item.filename for item in expected)
        actual_names = sorted(path.name for path in root.iterdir() if path.is_file())
        if actual_names != expected_names:
            raise V25S1InputError(f"extracted inventory differs from ZIP: {root}")
        for member in expected:
            path = root / member.filename
            if _sha256_file(path) != member.sha256:
                raise V25S1InputError(f"extracted raw hash mismatch: {member.filename}")

    if extracted_txt_directory is not None:
        verify_extracted(extracted_txt_directory, txt)
    if extracted_mdat_directory is not None:
        verify_extracted(extracted_mdat_directory, mdat)
    return V25S1Inventory(source, actual_zip_sha, tuple(txt), tuple(mdat), expected_counts)


def _preprocessing_id() -> str:
    payload = {
        **frozen_formal_preprocessing_contract(),
        "preprocessing_algorithm_version": FORMAL_PREPROCESSING_ALGORITHM_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _meta(member: V25S1Member, inventory: V25S1Inventory, reasons: Sequence[str]) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="V2.5_HR_single_module_fixture",
        configuration=member.condition_id.upper(),
        angle_deg=0.0,
        session_id="V25-S1",
        repeat_type="CONT",
        repeat_id=f"R{member.block_repeat_number:02d}",
        experiment_step="V25-S1_SINGLE_MODULE",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=f"zip://{inventory.zip_path.as_posix()}!/{member.archive_path}",
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=f"sha256:{inventory.zip_sha256}#member={member.sha256}",
        eligible_for_scientific_analysis=False,
        assembly_id=f"V25-S1-{member.block_id}",
        acquisition_block_id=member.block_id,
        valid=True,
        qc_status=QCStatus.WARNING if reasons else QCStatus.VALID,
        manual_review_reasons=tuple(reasons),
    )


def _qc_and_preprocess(
    inventory: V25S1Inventory,
) -> tuple[
    dict[str, FloatArray], FloatArray, BoolArray, list[dict[str, Any]],
    dict[str, Mapping[str, Any]], dict[str, str],
]:
    curves: dict[str, FloatArray] = {}
    qc_rows: list[dict[str, Any]] = []
    manifests: dict[str, Mapping[str, Any]] = {}
    dated: dict[str, str] = {}
    frequency: FloatArray | None = None
    valid_mask: BoolArray | None = None
    contract = frozen_formal_preprocessing_contract()
    with zipfile.ZipFile(inventory.zip_path, "r") as archive:
        for member in inventory.txt_members:
            payload = archive.read(member.archive_path)
            if _sha256_bytes(payload) != member.sha256:
                raise V25S1InputError(f"ZIP member changed after inventory: {member.filename}")
            parsed = _parse_rew_member(payload, member.archive_path)
            header, failures = _header_contract(parsed)
            all_headers = parsed.headers["all"]
            format_ok = bool(re.search(
                r"Format:\s*256k Log Swept Sine,\s*1 sweep at -30\.0 dBFS with no timing reference",
                all_headers, re.I,
            ))
            identity = re.search(
                r"Measurement:\s*R V2\.5_(?P<condition>base|HR0[1-8])_"
                r"(?P<repeat>0[1-6])\b",
                all_headers, re.I,
            )
            identity_ok = bool(
                identity
                and identity.group("condition").casefold() == member.condition_id.casefold()
                and int(identity.group("repeat")) == member.repeat_number
            )
            note = parsed.headers.get("note", "")
            note_ok = all(re.search(pattern, note, re.I) for pattern in (
                r"1 acoustic channels open", r"Windows out=50", r"mic input=100",
                r"distance=0\.8 m",
            ))
            source_ok = "iMM-6C" in parsed.headers.get("source", "")
            differences = np.diff(parsed.frequency_hz)
            inferred_sample_rate = float(np.median(differences) * 131072.0)
            inferred_48k = abs(inferred_sample_rate - 48000.0) <= 2.0
            if not format_ok:
                failures.append("rew_format_contract_mismatch")
            if not identity_ok:
                failures.append("measurement_header_identity_mismatch")
            if not note_ok:
                failures.append("fixed_note_settings_mismatch")
            if not source_ok:
                failures.append("microphone_source_not_iMM6C")
            if not inferred_48k:
                failures.append("sample_rate_not_consistent_with_48khz")
            warnings = [
                "calibration_filename_header_unavailable",
                "t0_at_ir_peak_header_unavailable",
                "clipping_unavailable_from_frequency_response_txt",
            ]
            reasons = sorted(set(failures if failures else warnings))
            meta = _meta(member, inventory, reasons)
            spectrum = SpectrumData(
                frequency_hz=parsed.frequency_hz,
                magnitude_db=parsed.magnitude_db,
                valid_mask=np.ones(parsed.frequency_hz.size, dtype=bool),
                representation=Representation.DENSE_SPECTRUM,
                phase_status=PhaseStatus.UNAVAILABLE,
                quality_metrics={
                    "v25_s1_qc_reasons": reasons,
                    "calibration_external_declaration": "CMM29939.txt",
                    "set_t0_external_declaration": "IR peak",
                    "inferred_sample_rate_hz": inferred_sample_rate,
                },
                meta=meta,
                magnitude_quantity="spl",
                magnitude_reference="REW frequency-response export",
            )
            result = preprocess_formal_sweep(spectrum, contract)
            if np.flatnonzero(~result.valid_mask).tolist() != [0]:
                raise V25S1InputError(f"FORMAL-1 valid mask mismatch: {member.sample_id}")
            if frequency is None:
                frequency = result.frequency_hz.copy()
                valid_mask = result.valid_mask.copy()
            elif not np.array_equal(frequency, result.frequency_hz):
                raise V25S1InputError("preprocessed frequency grids differ")
            curves[member.sample_id] = result.magnitude_db.copy()
            manifests[member.sample_id] = result.manifest
            dated[member.sample_id] = parsed.headers.get("dated", "").removeprefix("Dated:").strip()
            qc_rows.append({
                "sample_id": member.sample_id,
                "filename": member.filename,
                "condition_id": member.condition_id.upper(),
                "global_repeat_number": member.repeat_number,
                "block_id": member.block_id,
                "block_repeat_number": member.block_repeat_number,
                "dated_header": dated[member.sample_id] or "unavailable",
                "file_sha256": member.sha256,
                "size_bytes": member.size_bytes,
                "qc_status": "fail" if failures else "warning",
                "structural_valid": not failures,
                "reason_codes": reasons,
                "raw_point_count": int(parsed.frequency_hz.size),
                "frequency_min_hz": float(parsed.frequency_hz[0]),
                "frequency_max_hz": float(parsed.frequency_hz[-1]),
                "rew_version": header["rew_version"] or "unavailable",
                "format_256k_1rep_minus30_no_timing": format_ok,
                "raw_smoothing": header["raw_smoothing"] or "unavailable",
                "measurement_identity_matches_filename": identity_ok,
                "fixed_note_settings_match": note_ok,
                "source_mentions_iMM6C": source_ok,
                "inferred_sample_rate_hz": inferred_sample_rate,
                "inferred_sample_rate_is_48khz": inferred_48k,
                "calibration_external_declaration": "CMM29939.txt",
                "t0_external_declaration": "IR peak",
                "clipping_check": "unavailable_from_frequency_response_txt",
                "automatic_exclusion": False,
                "final_test_read": False,
            })
    if any(not row["structural_valid"] for row in qc_rows):
        bad = [row["sample_id"] for row in qc_rows if not row["structural_valid"]]
        raise V25S1InputError(f"V2.5 S1 structural QC failed: {bad}")
    if frequency is None or valid_mask is None:
        raise V25S1InputError("V2.5 S1 preprocessing produced no curves")
    return curves, frequency, valid_mask, qc_rows, manifests, dated


def _sample_id(condition: str, block: str, repeat: int) -> str:
    return f"V25S1-{condition.upper()}-{block}-R{repeat:02d}"


def _rms(values: FloatArray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def _demean(values: FloatArray) -> FloatArray:
    return values - float(np.mean(values))


def _local_residual(frequency: FloatArray, values: FloatArray) -> FloatArray:
    x = np.log2(frequency)
    if values.size < 3:
        return values - float(np.mean(values))
    edge_count = max(1, int(math.ceil(values.size * 0.15)))
    edge_indices = np.r_[0:edge_count, values.size - edge_count:values.size]
    coefficients = np.polyfit(x[edge_indices], values[edge_indices], deg=1)
    return values - np.polyval(coefficients, x)


def extract_target_feature(
    frequency_hz: FloatArray,
    block_deltas: Mapping[str, FloatArray],
    *,
    target_hz: float,
    local_floor_db: float,
) -> dict[str, Any]:
    """Extract a target-driven local peak/notch after edge-linear detrending."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    lower = target_hz * 2.0 ** (-1.0 / 6.0)
    upper = target_hz * 2.0 ** (1.0 / 6.0)
    mask = (frequency >= lower) & (frequency <= upper)
    if np.count_nonzero(mask) < 5:
        raise V25S1InputError(f"insufficient target-window bins around {target_hz} Hz")
    local_frequency = frequency[mask]
    residuals = {
        block: _local_residual(local_frequency, np.asarray(delta)[mask])
        for block, delta in block_deltas.items()
    }
    combined = np.mean(np.vstack(list(residuals.values())), axis=0)
    peak_index = int(np.argmax(np.abs(combined)))
    contrast = float(combined[peak_index])
    polarity = "peak" if contrast >= 0.0 else "notch"
    orientation = 1.0 if contrast >= 0.0 else -1.0
    oriented = orientation * combined
    threshold = abs(contrast) / 2.0
    left = peak_index
    right = peak_index
    while left > 0 and oriented[left - 1] >= threshold:
        left -= 1
    while right + 1 < oriented.size and oriented[right + 1] >= threshold:
        right += 1
    bandwidth = float(local_frequency[right] - local_frequency[left])
    effective_q = (
        float(local_frequency[peak_index] / bandwidth) if bandwidth > 0.0 else float("nan")
    )
    block_frequency: dict[str, float] = {}
    block_contrast: dict[str, float] = {}
    block_effect: dict[str, float] = {}
    for block, residual in residuals.items():
        index = int(np.argmax(np.abs(residual)))
        block_frequency[block] = float(local_frequency[index])
        block_contrast[block] = float(residual[index])
        block_effect[block] = _rms(residual)
    signs = [int(np.sign(value)) for value in block_contrast.values() if value != 0.0]
    sign_consistent = len(signs) == len(block_contrast) and len(set(signs)) == 1
    frequencies = list(block_frequency.values())
    frequency_consistent = (
        max(frequencies) / min(frequencies) <= 2.0 ** (1.0 / 12.0)
    )
    measured = float(local_frequency[peak_index])
    return {
        "target_window_low_hz": lower,
        "target_window_high_hz": upper,
        "measured_feature_hz": measured,
        "frequency_error_hz": measured - target_hz,
        "frequency_error_percent": 100.0 * (measured / target_hz - 1.0),
        "frequency_error_octaves": math.log2(measured / target_hz),
        "polarity": polarity,
        "signed_contrast_db": contrast,
        "absolute_contrast_db": abs(contrast),
        "contrast_bandwidth_hz": bandwidth,
        "effective_q": effective_q,
        "at_search_boundary": peak_index in {0, 1, combined.size - 2, combined.size - 1},
        "block1_feature_hz": block_frequency.get("B01", float("nan")),
        "block2_feature_hz": block_frequency.get("B02", float("nan")),
        "block1_signed_contrast_db": block_contrast.get("B01", float("nan")),
        "block2_signed_contrast_db": block_contrast.get("B02", float("nan")),
        "block1_window_rms_db": block_effect.get("B01", float("nan")),
        "block2_window_rms_db": block_effect.get("B02", float("nan")),
        "local_base_technical_p95_db": local_floor_db,
        "block_sign_consistent": sign_consistent,
        "block_frequency_consistent": frequency_consistent,
        "both_blocks_effect_above_floor": all(
            value > local_floor_db for value in block_effect.values()
        ),
    }


def _block_representatives(curves: Mapping[str, FloatArray]) -> dict[tuple[str, str], FloatArray]:
    return {
        (condition, block): np.median(np.vstack([
            curves[_sample_id(condition, block, repeat)] for repeat in range(1, 4)
        ]), axis=0)
        for condition in _CONDITIONS
        for block in ("B01", "B02")
    }


def _finite_band_mask(
    curves: Mapping[str, FloatArray], frequency: FloatArray, lower: float, upper: float,
) -> BoolArray:
    finite = np.logical_and.reduce([np.isfinite(curve) for curve in curves.values()])
    return finite & (frequency >= lower) & (frequency <= upper)


def _repeatability_rows(
    curves: Mapping[str, FloatArray], frequency: FloatArray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    primary = _finite_band_mask(curves, frequency, 200.0, 4000.0)
    secondary = _finite_band_mask(curves, frequency, 4000.0, 8000.0)
    rows: list[dict[str, Any]] = []
    for condition in _CONDITIONS:
        for block in ("B01", "B02"):
            ids = [_sample_id(condition, block, repeat) for repeat in range(1, 4)]
            primary_raw: list[float] = []
            primary_shape: list[float] = []
            secondary_raw: list[float] = []
            for left, right in itertools.combinations(ids, 2):
                difference = curves[left] - curves[right]
                primary_raw.append(_rms(difference[primary]))
                primary_shape.append(_rms(_demean(difference[primary])))
                secondary_raw.append(_rms(difference[secondary]))
            rows.append({
                "condition_id": condition.upper(),
                "block_id": block,
                "technical_pair_count": 3,
                "primary_raw_pair_rms_median_db": float(np.median(primary_raw)),
                "primary_raw_pair_rms_max_db": float(np.max(primary_raw)),
                "primary_shape_pair_rms_median_db": float(np.median(primary_shape)),
                "primary_shape_pair_rms_max_db": float(np.max(primary_shape)),
                "secondary_raw_pair_rms_median_db": float(np.median(secondary_raw)),
                "secondary_raw_pair_rms_max_db": float(np.max(secondary_raw)),
                "historical_primary_floor_p95_db": HISTORICAL_PRIMARY_FLOOR_P95_DB,
                "primary_max_exceeds_historical_floor": (
                    float(np.max(primary_raw)) > HISTORICAL_PRIMARY_FLOOR_P95_DB
                ),
            })
    representatives = _block_representatives(curves)
    cross_rows: list[dict[str, Any]] = []
    for condition in _CONDITIONS:
        difference = representatives[(condition, "B02")] - representatives[(condition, "B01")]
        cross_rows.append({
            "condition_id": condition.upper(),
            "primary_raw_block_centroid_rms_db": _rms(difference[primary]),
            "primary_shape_block_centroid_rms_db": _rms(_demean(difference[primary])),
            "secondary_raw_block_centroid_rms_db": _rms(difference[secondary]),
            "historical_primary_floor_p95_db": HISTORICAL_PRIMARY_FLOOR_P95_DB,
            "primary_raw_exceeds_historical_floor": (
                _rms(difference[primary]) > HISTORICAL_PRIMARY_FLOOR_P95_DB
            ),
        })
    base_pairs: list[float] = []
    for block in ("B01", "B02"):
        ids = [_sample_id("base", block, repeat) for repeat in range(1, 4)]
        for left, right in itertools.combinations(ids, 2):
            base_pairs.append(_rms((curves[left] - curves[right])[primary]))
    floors = {
        "base_technical_primary_descriptive_p95_db": float(np.quantile(base_pairs, 0.95)),
        "base_cross_block_primary_centroid_rms_db": next(
            float(row["primary_raw_block_centroid_rms_db"])
            for row in cross_rows if row["condition_id"] == "BASE"
        ),
        "historical_cont_primary_p95_db": HISTORICAL_PRIMARY_FLOOR_P95_DB,
    }
    return rows, cross_rows, floors


def _base_local_floor(
    curves: Mapping[str, FloatArray], frequency: FloatArray, target_hz: float,
) -> float:
    mask = (
        (frequency >= target_hz * 2.0 ** (-1.0 / 6.0))
        & (frequency <= target_hz * 2.0 ** (1.0 / 6.0))
    )
    values: list[float] = []
    for block in ("B01", "B02"):
        ids = [_sample_id("base", block, repeat) for repeat in range(1, 4)]
        for left, right in itertools.combinations(ids, 2):
            difference = curves[left][mask] - curves[right][mask]
            values.append(_rms(_local_residual(frequency[mask], difference)))
    return float(np.quantile(values, 0.95))


def _curve_flags(
    curves: Mapping[str, FloatArray], frequency: FloatArray,
) -> dict[str, dict[str, Any]]:
    primary = _finite_band_mask(curves, frequency, 200.0, 4000.0)
    states: dict[str, dict[str, Any]] = {}
    for condition in _CONDITIONS:
        for block in ("B01", "B02"):
            ids = [_sample_id(condition, block, repeat) for repeat in range(1, 4)]
            representative = np.median(np.vstack([curves[item] for item in ids]), axis=0)
            distances = {
                item: _rms((curves[item] - representative)[primary]) for item in ids
            }
            ordered = sorted(distances.values())
            for item, distance in distances.items():
                flag = (
                    distance > HISTORICAL_PRIMARY_FLOOR_P95_DB
                    and distance > 2.0 * max(ordered[1], 1.0e-12)
                )
                states[item] = {
                    "curve_to_block_median_primary_rms_db": distance,
                    "curve_outlier_flag": flag,
                    "outlier_rule": "distance_gt_historical_floor_and_gt_2x_second_largest",
                    "automatic_exclusion": False,
                }
    return states


def _analyse(
    curves: Mapping[str, FloatArray], frequency: FloatArray,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]],
    list[dict[str, Any]], list[dict[str, Any]], dict[str, Any],
]:
    representatives = _block_representatives(curves)
    primary = _finite_band_mask(curves, frequency, 200.0, 4000.0)
    secondary = _finite_band_mask(curves, frequency, 4000.0, 8000.0)
    target_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    deltas: dict[str, dict[str, FloatArray]] = {}
    local_floors: dict[str, float] = {}
    for module in _MODULES:
        block_deltas = {
            block: representatives[(module, block)] - representatives[("base", block)]
            for block in ("B01", "B02")
        }
        deltas[module] = block_deltas
        target = _TARGETS_HZ[module]
        local_floor = _base_local_floor(curves, frequency, target)
        local_floors[module] = local_floor
        feature = extract_target_feature(
            frequency, block_deltas, target_hz=target, local_floor_db=local_floor,
        )
        average_delta = np.mean(np.vstack(list(block_deltas.values())), axis=0)
        primary_effect = _rms(_demean(average_delta[primary]))
        secondary_effect = _rms(_demean(average_delta[secondary]))
        stable = bool(
            feature["both_blocks_effect_above_floor"]
            and feature["block_sign_consistent"]
            and feature["block_frequency_consistent"]
            and not feature["at_search_boundary"]
        )
        target_rows.append({
            "module_id": module,
            "target_hz": target,
            "package_predicted_hz": _PREDICTED_HZ[module],
            **feature,
            "primary_shape_effect_vs_base_db": primary_effect,
            "primary_effect_to_historical_floor_ratio": (
                primary_effect / HISTORICAL_PRIMARY_FLOOR_P95_DB
            ),
            "secondary_shape_effect_vs_base_db": secondary_effect,
            "stable_target_signature": stable,
            "interpretation": (
                "stable_target_local_feature" if stable
                else "target_local_feature_repeat_or_boundary_limited"
            ),
        })
        for block in ("B01", "B02"):
            block_rows.append({
                "module_id": module,
                "block_id": block,
                "target_hz": target,
                "block_feature_hz": feature[
                    "block1_feature_hz" if block == "B01" else "block2_feature_hz"
                ],
                "block_signed_contrast_db": feature[
                    "block1_signed_contrast_db" if block == "B01"
                    else "block2_signed_contrast_db"
                ],
                "block_window_rms_db": feature[
                    "block1_window_rms_db" if block == "B01" else "block2_window_rms_db"
                ],
                "local_base_technical_p95_db": local_floor,
                "effect_to_local_floor_ratio": float(feature[
                    "block1_window_rms_db" if block == "B01" else "block2_window_rms_db"
                ]) / local_floor,
            })

    channel_rows: list[dict[str, Any]] = []
    for module in _MODULES:
        average_delta = np.mean(np.vstack(list(deltas[module].values())), axis=0)
        module_values: list[tuple[str, float]] = []
        pending: list[dict[str, Any]] = []
        for channel in _MODULES:
            target = _TARGETS_HZ[channel]
            mask = (
                (frequency >= target * 2.0 ** (-1.0 / 6.0))
                & (frequency <= target * 2.0 ** (1.0 / 6.0))
            )
            residual = _local_residual(frequency[mask], average_delta[mask])
            effect = _rms(residual)
            module_values.append((channel, effect))
            pending.append({
                "module_id": module,
                "target_channel": channel,
                "target_hz": target,
                "window_rms_contrast_db": effect,
                "local_base_technical_p95_db": local_floors[channel],
                "effect_to_local_floor_ratio": effect / local_floors[channel],
                "own_target_channel": module == channel,
            })
        ordered = sorted(module_values, key=lambda item: item[1], reverse=True)
        ranks = {channel: index + 1 for index, (channel, _) in enumerate(ordered)}
        off = [effect for channel, effect in module_values if channel != module]
        for row in pending:
            row["within_module_effect_rank"] = ranks[str(row["target_channel"])]
            if row["own_target_channel"]:
                row["own_to_median_off_target_ratio"] = (
                    float(row["window_rms_contrast_db"]) / float(np.median(off))
                )
            else:
                row["own_to_median_off_target_ratio"] = ""
            channel_rows.append(row)

    similarity_rows: list[dict[str, Any]] = []
    similarity_mask = (frequency >= 800.0) & (frequency <= 5000.0)
    average_shapes = {
        module: _demean(np.mean(np.vstack(list(deltas[module].values())), axis=0)[similarity_mask])
        for module in _MODULES
    }
    for left, right in itertools.combinations(_MODULES, 2):
        a, b = average_shapes[left], average_shapes[right]
        pearson = float(np.corrcoef(a, b)[0, 1])
        cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        similarity_rows.append({
            "module_a": left, "module_b": right,
            "pearson_800_5000hz": pearson,
            "cosine_800_5000hz": cosine,
        })

    target_by_module = {str(row["module_id"]): row for row in target_rows}
    u4_modules = ("HR01", "HR03", "HR05", "HR07")
    separation_rows: list[dict[str, Any]] = []
    for left, right in itertools.combinations(u4_modules, 2):
        a, b = target_by_module[left], target_by_module[right]
        denominator = float(a["contrast_bandwidth_hz"]) / 2.0 + float(
            b["contrast_bandwidth_hz"]
        ) / 2.0
        separation = (
            abs(float(a["measured_feature_hz"]) - float(b["measured_feature_hz"]))
            / denominator if denominator > 0.0 else float("nan")
        )
        separation_rows.append({
            "module_a": left, "module_b": right,
            "measured_frequency_a_hz": a["measured_feature_hz"],
            "measured_frequency_b_hz": b["measured_feature_hz"],
            "half_power_nonoverlap_index": separation,
            "nonoverlapping_by_index_gt_1": bool(separation > 1.0),
        })

    stable_count = sum(bool(row["stable_target_signature"]) for row in target_rows)
    selected_stable = sum(
        bool(target_by_module[module]["stable_target_signature"]) for module in u4_modules
    )
    u4_nonoverlap = sum(
        bool(row["nonoverlapping_by_index_gt_1"]) for row in separation_rows
    )
    own_ranks = {
        row["module_id"]: int(row["within_module_effect_rank"])
        for row in channel_rows if row["own_target_channel"]
    }
    selected_top2 = sum(own_ranks[module] <= 2 for module in u4_modules)
    if selected_stable == 4 and u4_nonoverlap >= 5 and selected_top2 >= 3:
        stage3_prediction = "promising_but_common_chamber_coupling_untested"
        continue_s3 = True
        contingency = "continue_S2_S3_no_redesign_yet"
    elif selected_stable >= 2 and selected_top2 >= 2:
        stage3_prediction = "mixed_diagnostic_value_more_likely_than_strong_four_direction_result"
        continue_s3 = True
        contingency = "continue_S2_S3_to_distinguish_plan_3A_from_3B"
    else:
        stage3_prediction = "low_probability_of_ideal_frequency_code"
        continue_s3 = False
        contingency = "pause_before_S3_and_enter_plan_2_after_QC"
    decision = {
        "stable_target_signature_count_of_8": stable_count,
        "selected_u4_stable_count_of_4": selected_stable,
        "selected_u4_nonoverlap_pairs_of_6": u4_nonoverlap,
        "selected_u4_own_channel_top2_count_of_4": selected_top2,
        "continue_stage2": True,
        "continue_stage3": continue_s3,
        "stage3_prediction": stage3_prediction,
        "contingency_route": contingency,
        "decision_scope": (
            "S1 can establish isolated transfer-function tuning only; it cannot test "
            "common-chamber code preservation or angular gating"
        ),
    }
    return target_rows, block_rows, channel_rows, similarity_rows, separation_rows, decision


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return ";".join(str(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fields})


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _json_safe(payload), ensure_ascii=False, indent=2,
            sort_keys=True, allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )


def _write_plots(
    output: Path,
    curves: Mapping[str, FloatArray],
    frequency: FloatArray,
    target_rows: Sequence[Mapping[str, Any]],
    channel_rows: Sequence[Mapping[str, Any]],
    repeat_rows: Sequence[Mapping[str, Any]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plot_dir = output / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)
    representatives = _block_representatives(curves)
    overall = {
        condition: np.mean(np.vstack([
            representatives[(condition, "B01")], representatives[(condition, "B02")]
        ]), axis=0)
        for condition in _CONDITIONS
    }

    fig, axis = plt.subplots(figsize=(11, 6.5))
    for condition in _CONDITIONS:
        axis.plot(frequency, overall[condition], label=condition.upper(),
                  linewidth=2.2 if condition == "base" else 1.2)
    axis.set_xscale("log")
    axis.set_xlim(200, 8000)
    axis.axvline(4000, color="black", linestyle=":", linewidth=1)
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel("Smoothed level (dB SPL)")
    axis.set_title("V2.5 S1 representative spectra (two-block mean)")
    axis.grid(alpha=0.2)
    axis.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(plot_dir / "representative_spectra.png", dpi=200)
    fig.savefig(plot_dir / "representative_spectra.svg")
    plt.close(fig)

    fig, axes = plt.subplots(4, 2, figsize=(12, 14), sharex=True)
    for axis, module in zip(axes.flat, _MODULES, strict=True):
        for block, color in (("B01", "#2a9d8f"), ("B02", "#e76f51")):
            delta = representatives[(module, block)] - representatives[("base", block)]
            axis.plot(frequency, delta, label=block, color=color, linewidth=1.2)
        row = next(item for item in target_rows if item["module_id"] == module)
        axis.axvline(_TARGETS_HZ[module], color="black", linestyle="--", linewidth=1,
                     label="CAD target")
        axis.axvline(float(row["measured_feature_hz"]), color="#264653", linestyle=":",
                     linewidth=1.2, label="measured local feature")
        axis.axhline(0, color="grey", linewidth=0.7)
        axis.set_xscale("log")
        axis.set_xlim(700, 6000)
        axis.set_title(
            f"{module}: target {_TARGETS_HZ[module]:.0f} Hz, "
            f"feature {float(row['measured_feature_hz']):.0f} Hz"
        )
        axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=7, ncol=2)
    for axis in axes[-1, :]:
        axis.set_xlabel("Frequency (Hz)")
    for axis in axes[:, 0]:
        axis.set_ylabel("HR - P05 (dB)")
    fig.suptitle("V2.5 target-module contrasts by independent block", y=0.995)
    fig.tight_layout()
    fig.savefig(plot_dir / "target_module_contrasts.png", dpi=200)
    fig.savefig(plot_dir / "target_module_contrasts.svg")
    plt.close(fig)

    target_values = np.asarray([float(row["target_hz"]) for row in target_rows])
    measured_values = np.asarray([float(row["measured_feature_hz"]) for row in target_rows])
    stable = np.asarray([bool(row["stable_target_signature"]) for row in target_rows])
    fig, axis = plt.subplots(figsize=(7, 6.2))
    axis.plot([1000, 5000], [1000, 5000], color="black", linestyle="--", label="1:1")
    axis.scatter(target_values[~stable], measured_values[~stable], color="#e9c46a",
                 s=75, label="limited")
    axis.scatter(target_values[stable], measured_values[stable], color="#2a9d8f",
                 s=75, label="stable")
    for row in target_rows:
        axis.annotate(str(row["module_id"]),
                      (float(row["target_hz"]), float(row["measured_feature_hz"])),
                      xytext=(4, 4), textcoords="offset points", fontsize=8)
    axis.set_xlabel("CAD target (Hz)")
    axis.set_ylabel("Measured local contrast feature (Hz)")
    axis.set_title("Designed versus measured V2.5 local feature")
    axis.grid(alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "designed_vs_measured_frequency.png", dpi=200)
    fig.savefig(plot_dir / "designed_vs_measured_frequency.svg")
    plt.close(fig)

    matrix = np.zeros((8, 8), dtype=float)
    for row in channel_rows:
        i = _MODULES.index(str(row["module_id"]))
        j = _MODULES.index(str(row["target_channel"]))
        matrix[i, j] = float(row["effect_to_local_floor_ratio"])
    fig, axis = plt.subplots(figsize=(8.3, 7.0))
    image = axis.imshow(matrix, cmap="magma", vmin=0)
    axis.set_xticks(range(8), _MODULES, rotation=45, ha="right")
    axis.set_yticks(range(8), _MODULES)
    axis.set_xlabel("Target-centred channel")
    axis.set_ylabel("Measured module")
    axis.set_title("Local contrast / contemporaneous P05 technical p95")
    for i in range(8):
        for j in range(8):
            axis.text(j, i, f"{matrix[i,j]:.1f}", ha="center", va="center",
                      color="white" if matrix[i,j] > np.max(matrix) * 0.45 else "black",
                      fontsize=7)
    fig.colorbar(image, ax=axis, label="Effect / local floor")
    fig.tight_layout()
    fig.savefig(plot_dir / "target_channel_code_matrix.png", dpi=200)
    fig.savefig(plot_dir / "target_channel_code_matrix.svg")
    plt.close(fig)

    labels = [f"{row['condition_id']}-{row['block_id']}" for row in repeat_rows]
    values = [float(row["primary_raw_pair_rms_max_db"]) for row in repeat_rows]
    fig, axis = plt.subplots(figsize=(12, 5.5))
    axis.bar(np.arange(len(labels)), values, color="#457b9d")
    axis.axhline(HISTORICAL_PRIMARY_FLOOR_P95_DB, color="black", linestyle="--",
                 label="historical CONT p95 0.8793 dB")
    axis.set_xticks(np.arange(len(labels)), labels, rotation=55, ha="right")
    axis.set_ylabel("Maximum within-block primary RMS (dB)")
    axis.set_title("V2.5 S1 technical repeatability")
    axis.grid(axis="y", alpha=0.2)
    axis.legend()
    fig.tight_layout()
    fig.savefig(plot_dir / "technical_repeatability.png", dpi=200)
    fig.savefig(plot_dir / "technical_repeatability.svg")
    plt.close(fig)


def _write_artifact_manifests(output: Path) -> int:
    files = sorted(
        path for path in output.rglob("*")
        if path.is_file() and path.name not in {"artifact_manifest.json", "SHA256SUMS"}
    )
    artifacts = [{
        "path": path.relative_to(output).as_posix(),
        "sha256": artifact_sha256(path),
        "bytes": path.stat().st_size,
    } for path in files]
    _write_json(output / "artifact_manifest.json", {
        "schema_version": "v25_s1_artifact_manifest_v1",
        "algorithm": "SHA-256",
        "artifacts": artifacts,
    })
    sums = [*artifacts, {
        "path": "artifact_manifest.json",
        "sha256": artifact_sha256(output / "artifact_manifest.json"),
        "bytes": (output / "artifact_manifest.json").stat().st_size,
    }]
    (output / "SHA256SUMS").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in sums), encoding="utf-8"
    )
    return len(artifacts)


def verify_v25_s1_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise V25S1InputError("V2.5 S1 artifact manifest is empty")
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if not separator:
            raise V25S1InputError("invalid V2.5 S1 SHA256SUMS line")
        sums[relative] = digest
    for entry in artifacts:
        relative = str(entry["path"])
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise V25S1InputError("V2.5 artifact path escapes output") from exc
        if not path.is_file() or artifact_sha256(path) != entry["sha256"]:
            raise V25S1InputError(f"V2.5 artifact hash mismatch: {relative}")
        if sums.get(relative) != entry["sha256"]:
            raise V25S1InputError(f"V2.5 SHA256SUMS mismatch: {relative}")
    manifest_sha = artifact_sha256(root / "artifact_manifest.json")
    if sums.get("artifact_manifest.json") != manifest_sha:
        raise V25S1InputError("V2.5 manifest is not bound by SHA256SUMS")
    return {"all_match": True, "artifact_count": len(artifacts),
            "artifact_manifest_sha256": manifest_sha}


def run_v25_s1_analysis(
    zip_path: str | Path,
    raw_txt_directory: str | Path,
    raw_mdat_directory: str | Path,
    output_directory: str | Path,
    *,
    source_commit: str,
    source_worktree_clean: bool,
    created_at: str | datetime,
    expected_zip_sha256: str = V25S1_ZIP_SHA256,
) -> V25S1RunResult:
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise V25S1InputError("source_commit must be a full lowercase Git SHA")
    timestamp = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at)
    parsed_time = datetime.fromisoformat(timestamp)
    if parsed_time.tzinfo is None:
        raise V25S1InputError("created_at must include timezone")
    output = Path(output_directory).resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite V2.5 S1 output: {output}")
    inventory = inspect_v25_s1_archive(
        zip_path,
        expected_zip_sha256=expected_zip_sha256,
        extracted_txt_directory=raw_txt_directory,
        extracted_mdat_directory=raw_mdat_directory,
    )
    staging = output.with_name(output.name + ".staging")
    if staging.exists():
        raise FileExistsError(f"refusing to overwrite V2.5 S1 staging output: {staging}")
    staging.mkdir(parents=True)
    try:
        curves, frequency, valid, qc_rows, manifests, dated = _qc_and_preprocess(inventory)
        states = _curve_flags(curves, frequency)
        for row in qc_rows:
            row.update(states[str(row["sample_id"])])
        repeat_rows, cross_rows, floors = _repeatability_rows(curves, frequency)
        target_rows, block_rows, channel_rows, similarity_rows, separation_rows, decision = (
            _analyse(curves, frequency)
        )

        mdat_by_id = {
            (member.condition_id, member.repeat_number): member
            for member in inventory.mdat_members
        }
        inventory_rows = []
        for member in inventory.txt_members:
            mdat = mdat_by_id[(member.condition_id, member.repeat_number)]
            inventory_rows.append({
                "sample_id": member.sample_id,
                "condition_id": member.condition_id.upper(),
                "global_repeat_number": member.repeat_number,
                "block_id": member.block_id,
                "block_repeat_number": member.block_repeat_number,
                "txt_filename": member.filename,
                "txt_sha256": member.sha256,
                "txt_bytes": member.size_bytes,
                "mdat_filename": mdat.filename,
                "mdat_sha256": mdat.sha256,
                "mdat_bytes": mdat.size_bytes,
                "data_origin": "real_experiment",
                "dataset_role": "supplemental_research_analysis",
                "experiment_step": "V25-S1",
                "source_zip_sha256": inventory.zip_sha256,
                "mdat_analysis_role": "preserved_provenance_not_parsed",
            })
        _write_csv(staging / "data_inventory.csv", inventory_rows, tuple(inventory_rows[0]))
        _write_csv(staging / "file_qc.csv", qc_rows, tuple(qc_rows[0]))
        _write_csv(staging / "technical_repeatability.csv", repeat_rows, tuple(repeat_rows[0]))
        _write_csv(staging / "cross_block_repeatability.csv", cross_rows, tuple(cross_rows[0]))
        _write_csv(staging / "target_feature_summary.csv", target_rows, tuple(target_rows[0]))
        _write_csv(staging / "block_target_effects.csv", block_rows, tuple(block_rows[0]))
        _write_csv(staging / "target_channel_code_matrix.csv", channel_rows, tuple(channel_rows[0]))
        _write_csv(staging / "module_signature_similarity.csv", similarity_rows,
                   tuple(similarity_rows[0]))
        _write_csv(staging / "selected_u4_feature_separation.csv", separation_rows,
                   tuple(separation_rows[0]))

        for member in inventory.txt_members:
            directory = staging / "preprocessed" / member.sample_id
            directory.mkdir(parents=True)
            np.savez(
                directory / "formal_spectrum.npz",
                frequency_hz=frequency,
                magnitude_db=curves[member.sample_id],
                valid_mask=valid,
            )
            _write_json(directory / "preprocessing_manifest.json",
                        dict(manifests[member.sample_id]))

        _write_plots(staging, curves, frequency, target_rows, channel_rows, repeat_rows)
        flagged = [row for row in qc_rows if row["curve_outlier_flag"]]
        target_errors = np.asarray([abs(float(row["frequency_error_octaves"]))
                                    for row in target_rows])
        target_percent_errors = np.asarray([
            abs(float(row["frequency_error_percent"])) for row in target_rows
        ])
        correlations = np.asarray([float(row["pearson_800_5000hz"])
                                   for row in similarity_rows])
        summary = {
            "schema_version": V25S1_SCHEMA_VERSION,
            "created_at": timestamp,
            "status": "V25-S1_analysis_complete",
            "inventory": {
                "txt_measurement_count": 54,
                "mdat_count": 54,
                "condition_counts": inventory.condition_counts,
                "block_mapping": {"01-03": "B01", "04-06": "B02"},
                "source_zip_sha256": inventory.zip_sha256,
                "raw_copies_hash_verified": True,
                "mdat_preserved_not_parsed": True,
            },
            "qc": {
                "structural_fail_count": 0,
                "warning_count": len(qc_rows),
                "warning_reason": (
                    "calibration filename, t0-at-IR-peak and clipping unavailable from TXT; "
                    "fixed settings externally declared"
                ),
                "curve_outlier_flag_count": len(flagged),
                "curve_outlier_sample_ids": [row["sample_id"] for row in flagged],
                "automatic_exclusion": False,
            },
            "preprocessing": {
                **frozen_formal_preprocessing_contract(),
                "preprocessing_algorithm_version": FORMAL_PREPROCESSING_ALGORITHM_VERSION,
                "preprocessing_id": _preprocessing_id(),
            },
            "repeatability": floors,
            "target_tracking": {
                "stable_target_signature_count_of_8": decision[
                    "stable_target_signature_count_of_8"
                ],
                "median_absolute_frequency_error_octaves": float(np.median(target_errors)),
                "maximum_absolute_frequency_error_octaves": float(np.max(target_errors)),
                "median_absolute_frequency_error_percent": float(
                    np.median(target_percent_errors)
                ),
                "maximum_absolute_frequency_error_percent": float(
                    np.max(target_percent_errors)
                ),
                "modules": [{
                    "module_id": row["module_id"],
                    "target_hz": row["target_hz"],
                    "measured_feature_hz": row["measured_feature_hz"],
                    "polarity": row["polarity"],
                    "absolute_contrast_db": row["absolute_contrast_db"],
                    "stable_target_signature": row["stable_target_signature"],
                } for row in target_rows],
            },
            "signature_similarity": {
                "median_pearson_800_5000hz": float(np.median(correlations)),
                "minimum_pearson_800_5000hz": float(np.min(correlations)),
                "maximum_pearson_800_5000hz": float(np.max(correlations)),
            },
            "stage_decision": decision,
            "claim_boundary": {
                "S2_or_S3_data_analysed": False,
                "common_chamber_code_preservation_tested": False,
                "angular_gating_tested": False,
                "classification_performed": False,
                "final_test_read": False,
                "H1_confirmed": False,
            },
        }
        _write_json(staging / "analysis_summary.json", summary)
        _write_json(staging / "run_manifest.json", {
            "schema_version": V25S1_SCHEMA_VERSION,
            "created_at": timestamp,
            "source_commit": source_commit,
            "source_worktree_clean": source_worktree_clean,
            "source_zip": str(inventory.zip_path),
            "source_zip_sha256": inventory.zip_sha256,
            "raw_txt_directory": str(Path(raw_txt_directory).resolve()),
            "raw_mdat_directory": str(Path(raw_mdat_directory).resolve()),
            "data_origin": "real_experiment",
            "dataset_role": "supplemental_research_analysis",
            "analysis_code": "acoustic_encoder.v25_single_module_analysis",
            "analysis_scope": "V25-S1 only",
            "final_test_read": False,
        })
        artifact_count = _write_artifact_manifests(staging)
        staging.rename(output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    verified = verify_v25_s1_output_hashes(output)
    if not verified["all_match"]:
        raise V25S1InputError("V2.5 S1 output verification failed")
    return V25S1RunResult(
        output_directory=output,
        measurement_count=54,
        mdat_count=54,
        structurally_valid_count=54,
        flagged_count=len(flagged),
        stable_target_signature_count=int(decision["stable_target_signature_count_of_8"]),
        selected_u4_stable_count=int(decision["selected_u4_stable_count_of_4"]),
        artifact_count=artifact_count,
    )

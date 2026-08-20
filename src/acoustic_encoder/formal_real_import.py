"""Fail-closed FORMAL-3 import and QC for the frozen streamlined REW ZIP."""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import itertools
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any, Literal
import zipfile

import numpy as np
from numpy.typing import NDArray

from .formal_preprocessing import (
    FORMAL_PREPROCESSING_ALGORITHM_VERSION,
    frozen_formal_preprocessing_contract,
    preprocess_formal_sweep,
)
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
    SpectrumData,
    artifact_sha256,
    save_feature_set,
)
from .version import (
    CONFIG_SCHEMA_VERSION,
    FEATURE_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    PIPELINE_VERSION,
)


FORMAL3_ZIP_SHA256 = (
    "cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb"
)

_ACTIVE_GROUPS = {
    "B01_U4SYM_AS01": ("B01", "U4SYM", "AS01"),
    "B02_U4SYM_AS01": ("B02", "U4SYM", "AS01"),
    "B03_U4ENC_AS01": ("B03", "U4ENC", "AS01"),
    "B04_U4ENC_AS01": ("B04", "U4ENC", "AS01"),
    "B05_U4ENC_AS02": ("B05", "U4ENC", "AS02"),
    "B07_U4SYM_AS02": ("B07", "U4SYM", "AS02"),
}
_BLOCK_IDENTITIES = {value[0]: value for value in _ACTIVE_GROUPS.values()}
_STANDARD_NAME = re.compile(
    r"^R (?P<block>B\d{2})_(?P<configuration>U4(?:SYM|ENC))_"
    r"(?:S\d{2}_)?A(?P<direction>000|090|180|270)_C(?P<repeat>\d{2})\.txt$"
)
_B01_NAME = re.compile(
    r"^R C(?P<direction>000|090|180|270)_(?P<repeat>\d{2})\.txt$"
)


class Formal3ImportError(ValueError):
    """Raised when the frozen archive contract or measurement structure fails."""


@dataclass(frozen=True, slots=True)
class Formal3ArchiveMember:
    archive_path: str
    filename: str
    selection_status: Literal["ACTIVE", "EXCLUDED"]
    group_id: str
    block_id: str
    configuration: str
    assembly_id: str
    direction_id: str
    repeat_id: str
    sha256: str
    size_bytes: int

    @property
    def sample_id(self) -> str:
        return (
            f"FORMAL3-{self.block_id}-{self.configuration}-{self.assembly_id}-"
            f"D{self.direction_id}-C{self.repeat_id}"
        )

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        return (
            self.block_id,
            self.configuration,
            self.assembly_id,
            self.direction_id,
            self.repeat_id,
        )


@dataclass(frozen=True, slots=True)
class Formal3ArchiveInventory:
    zip_path: Path
    zip_sha256: str
    internal_root: str
    active: tuple[Formal3ArchiveMember, ...]
    excluded: tuple[Formal3ArchiveMember, ...]
    active_group_counts: dict[str, int]
    selection_record_path: str
    selection_record_sha256: str
    warning_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Formal3FileQC:
    sample_id: str
    archive_path: str
    selection_status: Literal["ACTIVE", "EXCLUDED"]
    analysis_included: bool
    group_id: str
    block_id: str
    configuration: str
    assembly_id: str
    direction_id: str
    repeat_id: str
    file_sha256: str
    size_bytes: int
    text_encoding: str
    status: Literal["pass", "warning", "fail"]
    structural_valid: bool
    reason_codes: tuple[str, ...]
    raw_point_count: int
    frequency_min_hz: float
    frequency_max_hz: float
    rew_version: str | None
    sweep_level_dbfs: float | None
    timing_reference: str | None
    raw_smoothing: str | None
    calibration_file: str | None
    source_header: str | None
    format_header: str | None
    measurement_header: str | None
    dated_header: str | None
    note_header: str | None


@dataclass(frozen=True, slots=True)
class Formal3QCAudit:
    records: tuple[Formal3FileQC, ...]
    active_pass_count: int
    active_warning_count: int
    active_fail_count: int


@dataclass(frozen=True, slots=True)
class Formal3RunResult:
    output_directory: Path
    ready_for_formal_analysis: bool
    active_count: int
    excluded_count: int
    active_pass_count: int
    active_warning_count: int
    active_fail_count: int
    artifact_count: int


@dataclass(frozen=True, slots=True)
class _ParsedREWMember:
    frequency_hz: NDArray[np.float64]
    magnitude_db: NDArray[np.float64]
    encoding: str
    headers: dict[str, str]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _member_identity(
    filename: str,
    *,
    group_name: str | None,
) -> tuple[str, str, str, str, str]:
    standard = _STANDARD_NAME.fullmatch(filename)
    if standard is not None:
        block = standard.group("block")
        if block not in _BLOCK_IDENTITIES:
            raise Formal3ImportError(f"unknown frozen block in measurement name: {filename}")
        expected_block, expected_configuration, assembly = _BLOCK_IDENTITIES[block]
        configuration = standard.group("configuration")
        if configuration != expected_configuration:
            raise Formal3ImportError(
                f"configuration disagrees with frozen block identity: {filename}"
            )
        identity = (
            expected_block,
            configuration,
            assembly,
            standard.group("direction"),
            standard.group("repeat"),
        )
    else:
        b01 = _B01_NAME.fullmatch(filename)
        if b01 is None:
            raise Formal3ImportError(f"cannot parse frozen measurement identity: {filename}")
        identity = ("B01", "U4SYM", "AS01", b01.group("direction"), b01.group("repeat"))
    if group_name is not None and identity[:3] != _ACTIVE_GROUPS[group_name]:
        raise Formal3ImportError(
            f"measurement identity disagrees with ACTIVE group {group_name}: {filename}"
        )
    return identity


def inspect_formal3_archive(
    zip_path: str | Path,
    *,
    expected_zip_sha256: str = FORMAL3_ZIP_SHA256,
) -> Formal3ArchiveInventory:
    """Inspect the frozen archive without extracting or altering any member."""
    source = Path(zip_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"FORMAL-3 ZIP does not exist: {source}")
    actual_zip_sha = _sha256_file(source)
    if actual_zip_sha != expected_zip_sha256:
        raise Formal3ImportError(
            "FORMAL-3 ZIP SHA-256 mismatch: "
            f"expected {expected_zip_sha256}, found {actual_zip_sha}"
        )
    with zipfile.ZipFile(source, "r") as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        names = [item.filename for item in files]
        duplicates = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicates:
            raise Formal3ImportError(f"duplicate ZIP member paths: {duplicates}")
        paths = [PurePosixPath(name) for name in names]
        if any(path.is_absolute() or ".." in path.parts for path in paths):
            raise Formal3ImportError("FORMAL-3 ZIP contains an unsafe member path")
        roots = {path.parts[0] for path in paths if path.parts}
        if len(roots) != 1:
            raise Formal3ImportError("FORMAL-3 ZIP must contain exactly one internal root")
        internal_root = next(iter(roots))
        warning_codes = (
            ("internal_rev002_name_under_rev003_authority",)
            if internal_root.endswith("REV002")
            else ()
        )
        if not warning_codes:
            raise Formal3ImportError(
                "FORMAL-3 frozen archive must retain the known internal REV002 root"
            )

        active: list[Formal3ArchiveMember] = []
        excluded: list[Formal3ArchiveMember] = []
        selection_records: list[tuple[str, str]] = []
        for info, path in zip(files, paths, strict=True):
            relative_parts = path.parts[1:]
            payload = archive.read(info)
            if len(relative_parts) == 1:
                selection_records.append((info.filename, _sha256_bytes(payload)))
                continue
            if len(relative_parts) != 2 or path.suffix.casefold() != ".txt":
                raise Formal3ImportError(f"unexpected FORMAL-3 ZIP member: {info.filename}")
            parent, filename = relative_parts
            if parent == "EXCLUDED":
                selection_status: Literal["ACTIVE", "EXCLUDED"] = "EXCLUDED"
                group_name = None
            elif parent in _ACTIVE_GROUPS:
                selection_status = "ACTIVE"
                group_name = parent
            else:
                raise Formal3ImportError(
                    f"measurement is outside frozen ACTIVE/EXCLUDED membership: {info.filename}"
                )
            block, configuration, assembly, direction, repeat = _member_identity(
                filename,
                group_name=group_name,
            )
            member = Formal3ArchiveMember(
                archive_path=info.filename,
                filename=filename,
                selection_status=selection_status,
                group_id=parent if group_name is not None else f"EXCLUDED_{block}",
                block_id=block,
                configuration=configuration,
                assembly_id=assembly,
                direction_id=direction,
                repeat_id=repeat,
                sha256=_sha256_bytes(payload),
                size_bytes=len(payload),
            )
            (active if selection_status == "ACTIVE" else excluded).append(member)

    if len(selection_records) != 1:
        raise Formal3ImportError("FORMAL-3 ZIP requires exactly one selection record")
    if len(active) != 72 or len(excluded) != 19:
        raise Formal3ImportError(
            f"frozen membership must be ACTIVE=72 and EXCLUDED=19; "
            f"found ACTIVE={len(active)}, EXCLUDED={len(excluded)}"
        )
    group_counts = Counter(member.group_id for member in active)
    expected_counts = {group: 12 for group in _ACTIVE_GROUPS}
    if dict(group_counts) != expected_counts:
        raise Formal3ImportError(
            f"ACTIVE group counts differ from frozen 12-per-group contract: {dict(group_counts)}"
        )
    active_identities = [member.identity for member in active]
    excluded_identities = [member.identity for member in excluded]
    if len(set(active_identities)) != len(active_identities):
        raise Formal3ImportError("duplicate ACTIVE measurement identity")
    if len(set(excluded_identities)) != len(excluded_identities):
        raise Formal3ImportError("duplicate EXCLUDED measurement identity")
    overlap = set(active_identities) & set(excluded_identities)
    if overlap:
        raise Formal3ImportError(f"ACTIVE and EXCLUDED identities overlap: {sorted(overlap)}")
    content_hashes = Counter(member.sha256 for member in (*active, *excluded))
    repeated_content = sorted(digest for digest, count in content_hashes.items() if count > 1)
    if repeated_content:
        raise Formal3ImportError(
            f"duplicate measurement file content detected: {repeated_content}"
        )

    active.sort(key=lambda member: (member.group_id, member.direction_id, member.repeat_id))
    excluded.sort(key=lambda member: member.identity)
    selection_path, selection_sha = selection_records[0]
    return Formal3ArchiveInventory(
        zip_path=source,
        zip_sha256=actual_zip_sha,
        internal_root=internal_root,
        active=tuple(active),
        excluded=tuple(excluded),
        active_group_counts=expected_counts,
        selection_record_path=selection_path,
        selection_record_sha256=selection_sha,
        warning_codes=warning_codes,
    )


def _decode_rew_bytes(payload: bytes, source_name: str) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise Formal3ImportError(f"REW TXT is not UTF-8 or GB18030: {source_name}")


def _parse_rew_member(payload: bytes, source_name: str) -> _ParsedREWMember:
    text, encoding = _decode_rew_bytes(payload, source_name)
    header_lines: list[str] = []
    rows: list[tuple[float, float]] = []
    numeric_started = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("*", "#")):
            if numeric_started:
                raise Formal3ImportError(
                    f"header appears after numeric data at line {line_number}: {source_name}"
                )
            header_lines.append(stripped.lstrip("*#").strip())
            continue
        fields = re.split(r"[\s,;]+", stripped)
        try:
            values = tuple(float(value) for value in fields)
        except ValueError as exc:
            if not numeric_started:
                header_lines.append(stripped)
                continue
            raise Formal3ImportError(
                f"non-numeric REW data at line {line_number}: {source_name}"
            ) from exc
        if len(values) not in {2, 3}:
            raise Formal3ImportError(
                f"REW data must have two or three columns at line {line_number}: "
                f"{source_name}"
            )
        numeric_started = True
        rows.append((values[0], values[1]))
    if len(rows) < 5:
        raise Formal3ImportError(f"REW TXT requires at least five points: {source_name}")
    numeric = np.asarray(rows, dtype=np.float64)
    if not np.all(np.isfinite(numeric)):
        raise Formal3ImportError(f"REW numeric values must be finite: {source_name}")
    if not np.all(np.diff(numeric[:, 0]) > 0.0):
        raise Formal3ImportError(
            f"REW frequencies must be strictly increasing and unique: {source_name}"
        )
    final_step_hz = float(numeric[-1, 0] - numeric[-2, 0])
    if numeric[0, 0] > 200.0 or numeric[-1, 0] + final_step_hz < 8000.0:
        raise Formal3ImportError(
            f"REW frequency coverage must include 200-8000 Hz: {source_name}"
        )
    prefixes = {
        "source": "Source:",
        "format": "Format:",
        "measurement": "Measurement:",
        "dated": "Dated:",
        "note": "Note:",
        "smoothing": "Smoothing:",
    }
    headers = {
        key: next(
            (line for line in header_lines if line.casefold().startswith(prefix.casefold())),
            "",
        )
        for key, prefix in prefixes.items()
    }
    headers["all"] = "\n".join(header_lines)
    return _ParsedREWMember(
        frequency_hz=numeric[:, 0],
        magnitude_db=numeric[:, 1],
        encoding=encoding,
        headers=headers,
    )


def _header_contract(parsed: _ParsedREWMember) -> tuple[dict[str, Any], list[str]]:
    all_headers = parsed.headers["all"]
    version_match = re.search(r"\bREW V(\d+\.\d+\.\d+)\b", all_headers)
    level_match = re.search(r"\bat\s+(-?\d+(?:\.\d+)?)\s+dBFS\b", all_headers)
    smoothing_match = re.search(
        r"^Smoothing:\s*(.+?)\s*$",
        all_headers,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    calibration_match = re.search(r"\b(CMM\d+\.txt)\b", all_headers, re.IGNORECASE)
    values: dict[str, Any] = {
        "rew_version": version_match.group(1) if version_match else None,
        "sweep_level_dbfs": float(level_match.group(1)) if level_match else None,
        "timing_reference": (
            "none" if re.search(r"\bno timing reference\b", all_headers, re.I) else None
        ),
        "raw_smoothing": smoothing_match.group(1) if smoothing_match else None,
        "calibration_file": calibration_match.group(1) if calibration_match else None,
    }
    failures: list[str] = []
    if values["rew_version"] != "5.31.3":
        failures.append("rew_version_mismatch")
    if values["sweep_level_dbfs"] != -30.0:
        failures.append("sweep_level_mismatch")
    if values["timing_reference"] != "none":
        failures.append("timing_reference_mismatch")
    if values["raw_smoothing"] != "None":
        failures.append("raw_smoothing_not_none")
    return values, failures


def inspect_formal3_measurements(inventory: Formal3ArchiveInventory) -> Formal3QCAudit:
    """Run read-only structural/header QC on ACTIVE and EXCLUDED members."""
    members = (*inventory.active, *inventory.excluded)
    records: list[Formal3FileQC] = []
    with zipfile.ZipFile(inventory.zip_path, "r") as archive:
        for member in members:
            payload = archive.read(member.archive_path)
            if _sha256_bytes(payload) != member.sha256:
                raise Formal3ImportError(
                    f"ZIP member changed after inventory: {member.archive_path}"
                )
            try:
                parsed = _parse_rew_member(payload, member.archive_path)
                header_values, failures = _header_contract(parsed)
                warnings = (
                    []
                    if header_values["calibration_file"] is not None
                    else ["calibration_file_header_unavailable"]
                )
                structural_valid = not failures
                reason_codes = tuple(failures if failures else warnings)
                status: Literal["pass", "warning", "fail"] = (
                    "fail" if failures else "warning" if warnings else "pass"
                )
                point_count = int(parsed.frequency_hz.size)
                minimum = float(parsed.frequency_hz[0])
                maximum = float(parsed.frequency_hz[-1])
                encoding = parsed.encoding
                headers = parsed.headers
            except Formal3ImportError as exc:
                structural_valid = False
                reason_codes = ("rew_structural_parse_failure", str(exc))
                status = "fail"
                point_count = 0
                minimum = float("nan")
                maximum = float("nan")
                encoding = "unavailable"
                headers = {key: "" for key in ("source", "format", "measurement", "dated", "note")}
                header_values = {
                    "rew_version": None,
                    "sweep_level_dbfs": None,
                    "timing_reference": None,
                    "raw_smoothing": None,
                    "calibration_file": None,
                }
            records.append(
                Formal3FileQC(
                    sample_id=member.sample_id,
                    archive_path=member.archive_path,
                    selection_status=member.selection_status,
                    analysis_included=member.selection_status == "ACTIVE",
                    group_id=member.group_id,
                    block_id=member.block_id,
                    configuration=member.configuration,
                    assembly_id=member.assembly_id,
                    direction_id=member.direction_id,
                    repeat_id=member.repeat_id,
                    file_sha256=member.sha256,
                    size_bytes=member.size_bytes,
                    text_encoding=encoding,
                    status=status,
                    structural_valid=structural_valid,
                    reason_codes=reason_codes,
                    raw_point_count=point_count,
                    frequency_min_hz=minimum,
                    frequency_max_hz=maximum,
                    rew_version=header_values["rew_version"],
                    sweep_level_dbfs=header_values["sweep_level_dbfs"],
                    timing_reference=header_values["timing_reference"],
                    raw_smoothing=header_values["raw_smoothing"],
                    calibration_file=header_values["calibration_file"],
                    source_header=headers.get("source") or None,
                    format_header=headers.get("format") or None,
                    measurement_header=headers.get("measurement") or None,
                    dated_header=headers.get("dated") or None,
                    note_header=headers.get("note") or None,
                )
            )
    active_records = [record for record in records if record.analysis_included]
    return Formal3QCAudit(
        records=tuple(records),
        active_pass_count=sum(record.status == "pass" for record in active_records),
        active_warning_count=sum(record.status == "warning" for record in active_records),
        active_fail_count=sum(record.status == "fail" for record in active_records),
    )


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="")


def _qc_row(record: Formal3FileQC, outlier: dict[str, Any] | None = None) -> dict[str, Any]:
    outlier_values = outlier or {}
    return {
        "sample_id": record.sample_id,
        "archive_path": record.archive_path,
        "selection_status": record.selection_status,
        "analysis_included": str(record.analysis_included).lower(),
        "group_id": record.group_id,
        "block_id": record.block_id,
        "configuration": record.configuration,
        "assembly_id": record.assembly_id,
        "direction_id": record.direction_id,
        "repeat_id": record.repeat_id,
        "file_sha256": record.file_sha256,
        "size_bytes": record.size_bytes,
        "text_encoding": record.text_encoding,
        "qc_status": record.status,
        "structural_valid": str(record.structural_valid).lower(),
        "reason_codes": ";".join(record.reason_codes),
        "raw_point_count": record.raw_point_count,
        "frequency_min_hz": record.frequency_min_hz,
        "frequency_max_hz": record.frequency_max_hz,
        "rew_version": record.rew_version or "unavailable",
        "sweep_level_dbfs": (
            "unavailable" if record.sweep_level_dbfs is None else record.sweep_level_dbfs
        ),
        "timing_reference": record.timing_reference or "unavailable",
        "raw_smoothing": record.raw_smoothing or "unavailable",
        "calibration_file": record.calibration_file or "unavailable",
        "curve_outlier_flag": str(bool(outlier_values.get("flag", False))).lower(),
        "curve_distance_to_group_median_db": outlier_values.get("distance_db", ""),
        "curve_outlier_threshold_db": outlier_values.get("threshold_db", ""),
        "source_header": record.source_header or "",
        "format_header": record.format_header or "",
        "measurement_header": record.measurement_header or "",
        "dated_header": record.dated_header or "",
        "note_header": record.note_header or "",
    }


_QC_FIELDS = (
    "sample_id",
    "archive_path",
    "selection_status",
    "analysis_included",
    "group_id",
    "block_id",
    "configuration",
    "assembly_id",
    "direction_id",
    "repeat_id",
    "file_sha256",
    "size_bytes",
    "text_encoding",
    "qc_status",
    "structural_valid",
    "reason_codes",
    "raw_point_count",
    "frequency_min_hz",
    "frequency_max_hz",
    "rew_version",
    "sweep_level_dbfs",
    "timing_reference",
    "raw_smoothing",
    "calibration_file",
    "curve_outlier_flag",
    "curve_distance_to_group_median_db",
    "curve_outlier_threshold_db",
    "source_header",
    "format_header",
    "measurement_header",
    "dated_header",
    "note_header",
)


def _member_manifest_row(member: Formal3ArchiveMember) -> dict[str, Any]:
    return {
        "sample_id": member.sample_id,
        "archive_path": member.archive_path,
        "selection_status": member.selection_status,
        "analysis_included": str(member.selection_status == "ACTIVE").lower(),
        "group_id": member.group_id,
        "block_id": member.block_id,
        "configuration": member.configuration,
        "assembly_id": member.assembly_id,
        "direction_id": member.direction_id,
        "repeat_id": member.repeat_id,
        "file_sha256": member.sha256,
        "size_bytes": member.size_bytes,
        "selection_authority": "frozen_REV003_zip_membership",
    }


_MEMBER_FIELDS = (
    "sample_id",
    "archive_path",
    "selection_status",
    "analysis_included",
    "group_id",
    "block_id",
    "configuration",
    "assembly_id",
    "direction_id",
    "repeat_id",
    "file_sha256",
    "size_bytes",
    "selection_authority",
)


def _measurement_meta(
    member: Formal3ArchiveMember,
    record: Formal3FileQC,
    inventory: Formal3ArchiveInventory,
) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=member.sample_id,
        pipeline_version=PIPELINE_VERSION,
        config_schema_version=CONFIG_SCHEMA_VERSION,
        measurement_schema_version=MEASUREMENT_SCHEMA_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        device_version="U4",
        configuration=member.configuration,
        angle_deg=float(member.direction_id),
        session_id=member.block_id,
        repeat_type="CONT",
        repeat_id=member.repeat_id,
        experiment_step="FORMAL-3_REAL_IMPORT_QC",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=(
            f"zip://{inventory.zip_path.as_posix()}!/{member.archive_path}"
        ),
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_ANALYSIS,
        source_sha256=member.sha256,
        provenance_uri=(
            f"sha256:{inventory.zip_sha256}#member={member.sha256}"
        ),
        eligible_for_scientific_analysis=False,
        assembly_id=member.assembly_id,
        acquisition_block_id=member.block_id,
        valid=True,
        qc_status=(QCStatus.VALID if record.status == "pass" else QCStatus.WARNING),
        manual_review_reasons=tuple(record.reason_codes),
    )


def _preprocessing_id() -> str:
    semantic = {
        **frozen_formal_preprocessing_contract(),
        "preprocessing_algorithm_version": FORMAL_PREPROCESSING_ALGORITHM_VERSION,
    }
    return "sha256:" + hashlib.sha256(_json_bytes(semantic)).hexdigest()


def _feature_from_result(
    result: Any,
    meta: MeasurementMeta,
    record: Formal3FileQC,
) -> FeatureSet:
    qc_sha = hashlib.sha256(_json_bytes(_qc_row(record))).hexdigest()
    return FeatureSet(
        sample_id=meta.sample_id,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_kind=FeatureKind.DENSE_RAW_SPL,
        feature_names=tuple(f"spl_{value:.9f}_hz" for value in result.frequency_hz),
        values=result.magnitude_db,
        valid_mask=result.valid_mask,
        units=tuple("dB SPL" for _ in result.frequency_hz),
        source_measurement_mode=MeasurementMode.REW_SWEEP,
        source_representation=Representation.DENSE_SPECTRUM,
        preprocessing_id=_preprocessing_id(),
        meta=meta,
        normalization_method="none",
        source_magnitude_quantity="spl",
        source_magnitude_reference="REW frequency-response export",
        source_phase_status=PhaseStatus.UNAVAILABLE,
        source_qc_status=meta.qc_status,
        source_qc_sha256="sha256:" + qc_sha,
        source_qc_warning_reasons=(
            record.reason_codes if record.status == "warning" else ()
        ),
        source_qc_exclude_candidate_reasons=(),
        source_qc_unavailable_checks=(
            ("calibration_file_header",)
            if record.calibration_file is None
            else ()
        ),
        source_qc_eligible_for_downstream=record.structural_valid,
    )


def _repeatability_rows(
    features: dict[str, FeatureSet],
    active: tuple[Formal3ArchiveMember, ...],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    groups: dict[tuple[str, str], list[Formal3ArchiveMember]] = {}
    for member in active:
        groups.setdefault((member.group_id, member.direction_id), []).append(member)
    rows: list[dict[str, Any]] = []
    outliers: dict[str, dict[str, Any]] = {}
    for (group_id, direction), members in sorted(groups.items()):
        members.sort(key=lambda member: member.repeat_id)
        selected_features = [features[member.sample_id] for member in members]
        common = np.logical_and.reduce([feature.valid_mask for feature in selected_features])
        frequency = np.asarray(
            [float(name.removeprefix("spl_").removesuffix("_hz")) for name in selected_features[0].feature_names]
        )
        common &= (frequency >= 200.0) & (frequency <= 4000.0)
        if not np.any(common):
            raise Formal3ImportError(
                f"no common valid primary-band features for {group_id}/{direction}"
            )
        values = np.vstack([feature.values for feature in selected_features])[:, common]
        pair_distances = [
            float(np.sqrt(np.mean(np.square(values[left] - values[right]))))
            for left, right in itertools.combinations(range(len(members)), 2)
        ]
        group_median = np.median(values, axis=0)
        curve_distances = np.sqrt(np.mean(np.square(values - group_median), axis=1))
        center = float(np.median(curve_distances))
        mad = float(np.median(np.abs(curve_distances - center)))
        threshold = center + 3.0 * 1.4826 * mad
        flags = curve_distances > threshold + 1.0e-12
        for member, distance, flag in zip(
            members,
            curve_distances,
            flags,
            strict=True,
        ):
            outliers[member.sample_id] = {
                "flag": bool(flag),
                "distance_db": float(distance),
                "threshold_db": threshold,
            }
        rows.append(
            {
                "group_id": group_id,
                "direction_id": direction,
                "sample_count": len(members),
                "pair_count": len(pair_distances),
                "sample_ids": ";".join(member.sample_id for member in members),
                "pair_ids": ";".join(
                    f"{members[left].sample_id}|{members[right].sample_id}"
                    for left, right in itertools.combinations(range(len(members)), 2)
                ),
                "median_pairwise_rms_db": float(np.median(pair_distances)),
                "maximum_pairwise_rms_db": float(np.max(pair_distances)),
                "outlier_method": "curve_rms_to_group_median_gt_median_plus_3_scaled_MAD",
                "outlier_threshold_db": threshold,
                "outlier_sample_ids": ";".join(
                    member.sample_id
                    for member, flag in zip(members, flags, strict=True)
                    if flag
                ),
                "status": "warning" if np.any(flags) else "pass",
                "automatic_exclusion": "false",
            }
        )
    return rows, outliers


def _write_qc_plots(
    output: Path,
    inventory: Formal3ArchiveInventory,
    repeatability_rows: list[dict[str, Any]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    group_names = list(inventory.active_group_counts)
    counts = [inventory.active_group_counts[name] for name in group_names]
    figure, axis = plt.subplots(figsize=(10, 4.8))
    axis.bar(group_names, counts, color="#4472c4")
    axis.axhline(12, color="#c00000", linestyle="--", label="frozen expected=12")
    axis.set_ylabel("ACTIVE measurements")
    axis.set_title("FORMAL-3 frozen group coverage")
    axis.tick_params(axis="x", rotation=25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output / "group_coverage.png", dpi=150)
    plt.close(figure)

    labels = [f"{row['group_id']}/D{row['direction_id']}" for row in repeatability_rows]
    values = [float(row["median_pairwise_rms_db"]) for row in repeatability_rows]
    figure, axis = plt.subplots(figsize=(12, 5.5))
    axis.plot(range(len(values)), values, marker="o", linewidth=1.0)
    axis.set_xticks(range(len(labels)), labels, rotation=70, ha="right")
    axis.set_ylabel("Median pairwise RMS difference (dB)")
    axis.set_title("FORMAL-3 within block/direction repeat dispersion")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(output / "repeat_dispersion.png", dpi=150)
    plt.close(figure)


def _write_artifact_manifests(output: Path) -> int:
    artifact_manifest_path = output / "artifact_manifest.json"
    sums_path = output / "SHA256SUMS"
    excluded = {artifact_manifest_path.resolve(), sums_path.resolve()}
    files = sorted(
        (
            path
            for path in output.rglob("*")
            if path.is_file() and path.resolve() not in excluded
        ),
        key=lambda path: path.relative_to(output).as_posix(),
    )
    records = [
        {
            "path": path.relative_to(output).as_posix(),
            "sha256": artifact_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in files
    ]
    _write_json(
        artifact_manifest_path,
        {
            "schema_version": "formal3_artifact_manifest_v1",
            "algorithm": "SHA-256",
            "artifacts": records,
        },
    )
    sums_files = [*files, artifact_manifest_path]
    sums_path.write_text(
        "".join(
            f"{artifact_sha256(path)}  {path.relative_to(output).as_posix()}\n"
            for path in sums_files
        ),
        encoding="utf-8",
    )
    return len(records)


def verify_formal3_output_hashes(output_directory: str | Path) -> dict[str, Any]:
    output = Path(output_directory)
    manifest_path = output / "artifact_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "formal3_artifact_manifest_v1":
        raise Formal3ImportError("unsupported FORMAL-3 artifact manifest schema")
    verified: list[str] = []
    for record in payload.get("artifacts", []):
        relative = PurePosixPath(str(record["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise Formal3ImportError("FORMAL-3 artifact path escapes output root")
        path = output / Path(*relative.parts)
        if not path.is_file() or artifact_sha256(path) != record["sha256"]:
            raise Formal3ImportError(f"FORMAL-3 artifact hash mismatch: {relative}")
        verified.append(relative.as_posix())
    if not verified:
        raise Formal3ImportError("FORMAL-3 artifact manifest is empty")
    sums_path = output / "SHA256SUMS"
    sums_records: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative_text = line.partition("  ")
        if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise Formal3ImportError("malformed FORMAL-3 SHA256SUMS row")
        relative = PurePosixPath(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            raise Formal3ImportError("FORMAL-3 SHA256SUMS path escapes output root")
        path = output / Path(*relative.parts)
        if relative.as_posix() in sums_records:
            raise Formal3ImportError("duplicate FORMAL-3 SHA256SUMS path")
        if not path.is_file() or artifact_sha256(path) != digest:
            raise Formal3ImportError(f"FORMAL-3 SHA256SUMS mismatch: {relative}")
        sums_records[relative.as_posix()] = digest
    expected_sums = {*verified, "artifact_manifest.json"}
    if set(sums_records) != expected_sums:
        raise Formal3ImportError("FORMAL-3 SHA256SUMS inventory is incomplete or unexpected")
    return {
        "verified": True,
        "artifact_count": len(verified),
        "verified_paths": verified,
        "artifact_manifest_sha256": artifact_sha256(manifest_path),
        "sha256sums_sha256": artifact_sha256(output / "SHA256SUMS"),
    }


def run_formal3_import_qc(
    zip_path: str | Path,
    output_directory: str | Path,
    *,
    expected_zip_sha256: str = FORMAL3_ZIP_SHA256,
    created_at: str,
    source_commit: str,
) -> Formal3RunResult:
    """Run frozen import/QC/FORMAL-1 preprocessing without scientific analysis."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite FORMAL-3 output: {output}")
    parsed_created_at = datetime.fromisoformat(created_at)
    if parsed_created_at.tzinfo is None:
        raise Formal3ImportError("FORMAL-3 created_at must include a timezone")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise Formal3ImportError("FORMAL-3 source_commit must be a lowercase Git SHA-1")
    inventory = inspect_formal3_archive(
        zip_path,
        expected_zip_sha256=expected_zip_sha256,
    )
    audit = inspect_formal3_measurements(inventory)
    if audit.active_fail_count:
        raise Formal3ImportError(
            f"FORMAL-3 has {audit.active_fail_count} structurally invalid ACTIVE files"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        _write_csv(
            staging / "active_manifest.csv",
            _MEMBER_FIELDS,
            [_member_manifest_row(member) for member in inventory.active],
        )
        _write_csv(
            staging / "excluded_manifest.csv",
            _MEMBER_FIELDS,
            [_member_manifest_row(member) for member in inventory.excluded],
        )

        qc_by_sample = {record.sample_id: record for record in audit.records}
        features: dict[str, FeatureSet] = {}
        boundary_invalid_by_sample: dict[str, list[int]] = {}
        feature_rows: list[dict[str, Any]] = []
        contract = frozen_formal_preprocessing_contract()
        with zipfile.ZipFile(inventory.zip_path, "r") as archive:
            for member in inventory.active:
                parsed = _parse_rew_member(
                    archive.read(member.archive_path),
                    member.archive_path,
                )
                record = qc_by_sample[member.sample_id]
                meta = _measurement_meta(member, record, inventory)
                spectrum = SpectrumData(
                    frequency_hz=parsed.frequency_hz,
                    magnitude_db=parsed.magnitude_db,
                    valid_mask=np.ones(parsed.frequency_hz.size, dtype=bool),
                    representation=Representation.DENSE_SPECTRUM,
                    phase_status=PhaseStatus.UNAVAILABLE,
                    quality_metrics={
                        "formal3_file_qc_status": record.status,
                        "formal3_reason_codes": record.reason_codes,
                        "raw_point_count": record.raw_point_count,
                        "calibration_file_header": record.calibration_file or "unavailable",
                    },
                    meta=meta,
                    magnitude_quantity="spl",
                    magnitude_reference="REW frequency-response export",
                )
                preprocessed = preprocess_formal_sweep(spectrum, contract)
                invalid_indices = np.flatnonzero(~preprocessed.valid_mask)
                interior_invalid = invalid_indices[
                    (invalid_indices > 0)
                    & (invalid_indices < preprocessed.valid_mask.size - 1)
                ]
                if interior_invalid.size:
                    raise Formal3ImportError(
                        "FORMAL-1 output contains an internal invalid grid point: "
                        f"{member.sample_id}, indices={interior_invalid.tolist()}"
                    )
                boundary_invalid_by_sample[member.sample_id] = invalid_indices.tolist()
                feature = _feature_from_result(preprocessed, meta, record)
                features[member.sample_id] = feature
                base = staging / "preprocessed" / "features" / member.sample_id
                array_path, metadata_path = save_feature_set(feature, base)
                manifest_path = (
                    staging
                    / "preprocessed"
                    / "manifests"
                    / f"{member.sample_id}.json"
                )
                _write_json(
                    manifest_path,
                    {
                        **preprocessed.manifest,
                        "formal3_boundary_invalid_policy": {
                            "allowed_indices": [
                                0,
                                int(preprocessed.valid_mask.size - 1),
                            ],
                            "actual_invalid_indices": invalid_indices.tolist(),
                            "actual_invalid_frequency_hz": [
                                float(preprocessed.frequency_hz[index])
                                for index in invalid_indices
                            ],
                            "interior_invalid_is_failure": True,
                            "fill_or_extrapolation_performed": False,
                        },
                    },
                )
                feature_rows.append(
                    {
                        "sample_id": member.sample_id,
                        "group_id": member.group_id,
                        "direction_id": member.direction_id,
                        "feature_kind": feature.feature_kind.value,
                        "grid_point_count": len(feature.values),
                        "valid_point_count": int(np.count_nonzero(feature.valid_mask)),
                        "preprocessing_id": feature.preprocessing_id,
                        "feature_npz": array_path.relative_to(staging).as_posix(),
                        "feature_json": metadata_path.relative_to(staging).as_posix(),
                        "preprocessing_manifest": manifest_path.relative_to(staging).as_posix(),
                        "feature_npz_sha256": artifact_sha256(array_path),
                        "feature_json_sha256": artifact_sha256(metadata_path),
                        "preprocessing_manifest_sha256": artifact_sha256(manifest_path),
                    }
                )

        repeatability_rows, outlier_by_sample = _repeatability_rows(
            features,
            inventory.active,
        )
        _write_csv(
            staging / "file_qc.csv",
            _QC_FIELDS,
            [
                _qc_row(record, outlier_by_sample.get(record.sample_id))
                for record in audit.records
            ],
        )
        group_rows: list[dict[str, Any]] = []
        for group_id in inventory.active_group_counts:
            members = [member for member in inventory.active if member.group_id == group_id]
            records = [qc_by_sample[member.sample_id] for member in members]
            group_rows.append(
                {
                    "group_id": group_id,
                    "block_id": members[0].block_id,
                    "configuration": members[0].configuration,
                    "assembly_id": members[0].assembly_id,
                    "expected_count": 12,
                    "observed_count": len(members),
                    "direction_count": len({member.direction_id for member in members}),
                    "minimum_repeats_per_direction": min(
                        sum(item.direction_id == direction for item in members)
                        for direction in ("000", "090", "180", "270")
                    ),
                    "pass_count": sum(record.status == "pass" for record in records),
                    "warning_count": sum(record.status == "warning" for record in records),
                    "fail_count": sum(record.status == "fail" for record in records),
                    "status": (
                        "fail"
                        if any(record.status == "fail" for record in records)
                        else "warning"
                        if any(record.status == "warning" for record in records)
                        else "pass"
                    ),
                }
            )
        _write_csv(
            staging / "group_qc.csv",
            (
                "group_id",
                "block_id",
                "configuration",
                "assembly_id",
                "expected_count",
                "observed_count",
                "direction_count",
                "minimum_repeats_per_direction",
                "pass_count",
                "warning_count",
                "fail_count",
                "status",
            ),
            group_rows,
        )
        _write_csv(
            staging / "repeatability_summary.csv",
            (
                "group_id",
                "direction_id",
                "sample_count",
                "pair_count",
                "sample_ids",
                "pair_ids",
                "median_pairwise_rms_db",
                "maximum_pairwise_rms_db",
                "outlier_method",
                "outlier_threshold_db",
                "outlier_sample_ids",
                "status",
                "automatic_exclusion",
            ),
            repeatability_rows,
        )
        _write_csv(
            staging / "feature_index.csv",
            (
                "sample_id",
                "group_id",
                "direction_id",
                "feature_kind",
                "grid_point_count",
                "valid_point_count",
                "preprocessing_id",
                "feature_npz",
                "feature_json",
                "preprocessing_manifest",
                "feature_npz_sha256",
                "feature_json_sha256",
                "preprocessing_manifest_sha256",
            ),
            feature_rows,
        )
        _write_qc_plots(staging, inventory, repeatability_rows)
        ready = audit.active_fail_count == 0 and len(features) == 72
        _write_json(
            staging / "run_manifest.json",
            {
                "schema_version": "formal3_real_import_qc_v1",
                "created_at": parsed_created_at.isoformat(),
                "source_commit": source_commit,
                "pipeline_version": PIPELINE_VERSION,
                "config_schema_version": CONFIG_SCHEMA_VERSION,
                "measurement_schema_version": MEASUREMENT_SCHEMA_VERSION,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "input_zip": {
                    "path": str(inventory.zip_path),
                    "filename_authority": "outer_REV003_filename_plus_frozen_SHA256",
                    "sha256": inventory.zip_sha256,
                    "bytes": inventory.zip_path.stat().st_size,
                    "internal_root": inventory.internal_root,
                    "warning_codes": inventory.warning_codes,
                    "content_modified_or_repacked": False,
                },
                "selection": {
                    "authority": "human_frozen_archive_membership",
                    "active_count": len(inventory.active),
                    "excluded_count": len(inventory.excluded),
                    "selection_record_path": inventory.selection_record_path,
                    "selection_record_sha256": inventory.selection_record_sha256,
                    "active_group_counts": inventory.active_group_counts,
                    "automatic_selection_change_allowed": False,
                    "excluded_entered_features_statistics_training_or_results": False,
                },
                "qc": {
                    "active_pass_count": audit.active_pass_count,
                    "active_warning_count": audit.active_warning_count,
                    "active_fail_count": audit.active_fail_count,
                    "calibration_header_unavailable_is_warning": True,
                    "frequency_coverage_rule": (
                        "first_bin<=200 and last_bin+last_local_step>=8000"
                    ),
                    "curve_outlier_method": (
                        "RMS_to_group_median > median + 3*1.4826*MAD; flag_only"
                    ),
                    "formal1_boundary_invalid_policy": {
                        "only_first_or_last_grid_point_may_remain_invalid": True,
                        "interior_invalid_is_failure": True,
                        "fill_or_extrapolation_performed": False,
                        "sample_count_with_boundary_invalid": sum(
                            bool(indices)
                            for indices in boundary_invalid_by_sample.values()
                        ),
                        "invalid_indices_by_sample": boundary_invalid_by_sample,
                    },
                    "automatic_deletion": False,
                    "automatic_remeasurement": False,
                },
                "formal_preprocessing_contract": contract,
                "preprocessing_algorithm_version": (
                    FORMAL_PREPROCESSING_ALGORITHM_VERSION
                ),
                "preprocessed_feature_count": len(features),
                "provenance": {
                    "data_origin": "real_experiment",
                    "dataset_role": "research_analysis",
                    "run_purpose": "research_analysis",
                    "scientifically_eligible": False,
                },
                "research_gate_status": "import_qc_only_scientific_eligibility_not_granted",
                "ready_for_formal_analysis": ready,
                "ready_reason": (
                    "all_72_active_structurally_valid_and_formal1_preprocessed"
                    if ready
                    else "structural_or_preprocessing_failure"
                ),
                "classification_executed": False,
                "direction_decision_executed": False,
                "hypothesis_test_executed": False,
                "scientific_conclusion_generated": False,
                "final_test_read": False,
            },
        )
        _write_artifact_manifests(staging)
        verification = verify_formal3_output_hashes(staging)
        staging.rename(output)
        return Formal3RunResult(
            output_directory=output,
            ready_for_formal_analysis=ready,
            active_count=len(inventory.active),
            excluded_count=len(inventory.excluded),
            active_pass_count=audit.active_pass_count,
            active_warning_count=audit.active_warning_count,
            active_fail_count=audit.active_fail_count,
            artifact_count=int(verification["artifact_count"]),
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

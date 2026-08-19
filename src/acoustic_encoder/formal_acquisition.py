"""Fail-closed FORMAL-2 acquisition-package preparation.

The frozen Markdown acquisition plan is the only sample-identity authority.
This module prepares empty acquisition infrastructure; it never reads a
measurement, pilot dataset, or final-test artifact.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
from typing import Any, Mapping


class FormalAcquisitionError(ValueError):
    """Raised when frozen inputs or package evidence are inconsistent."""


@dataclass(frozen=True, slots=True)
class FormalSample:
    sequence: int
    sample_id: str
    configuration: str
    direction_deg: int
    continuation_id: str
    reposition_id: str
    reassembly_id: str
    session: str
    block: str
    role: str


@dataclass(frozen=True, slots=True)
class FormalAcquisitionPackage:
    root: Path
    sample_manifest: Path
    b01_sheet: Path
    preflight_checklist: Path
    preflight_status: Path
    backup_verification: Path
    sha256_json: Path
    sha256_text: Path
    ready_for_b01: bool
    unresolved_blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BackupGateResult:
    ready: bool
    status: str
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CalibrationRegistrationResult:
    registration_path: Path
    preflight_status_path: Path
    ready_for_b01: bool
    unresolved_blockers: tuple[str, ...]
    calibration_sha256: str
    screenshot_sha256: str


_PLAN_HEADERS = (
    "sequence",
    "sample_id",
    "configuration",
    "direction_deg",
    "CONT",
    "REPOS",
    "REASM",
    "session",
    "block",
    "role",
)

_SAMPLE_ID_PATTERN = re.compile(
    r"^F002-SWEEP-(U4SYM|U4ENC)-D(000|090|180|270)-"
    r"(AS0[12])-(RP0[12])-(C0[123])-(S0[1-4])-(B0[1-8])$"
)

_DIRECTORIES = (
    "00_protocol_and_manifests",
    "01_calibration",
    "02_photos_and_geometry",
    "03_environment_logs",
    "07_hashes",
    "08_deviations_and_manual_review",
    *(f"04_raw_rew_mdat/S0{index}" for index in range(1, 5)),
    *(f"05_exported_rew_txt/S0{index}" for index in range(1, 5)),
    *(f"06_metadata_sidecars/S0{index}" for index in range(1, 5)),
)


def _markdown_cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def load_frozen_sample_plan(plan_path: str | Path) -> tuple[FormalSample, ...]:
    """Load and validate the sole 96-row identity table from the frozen plan."""
    lines = Path(plan_path).read_text(encoding="utf-8").splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if tuple(_markdown_cells(line)) == _PLAN_HEADERS
        ),
        None,
    )
    if header_index is None:
        raise FormalAcquisitionError("frozen 96-sample table header was not found")
    samples: list[FormalSample] = []
    for line in lines[header_index + 2 :]:
        if not line.strip().startswith("|"):
            break
        cells = _markdown_cells(line)
        if len(cells) != len(_PLAN_HEADERS):
            raise FormalAcquisitionError("frozen sample row has the wrong column count")
        samples.append(
            FormalSample(
                sequence=int(cells[0]),
                sample_id=cells[1],
                configuration=cells[2],
                direction_deg=int(cells[3]),
                continuation_id=cells[4],
                reposition_id=cells[5],
                reassembly_id=cells[6],
                session=cells[7],
                block=cells[8],
                role=cells[9],
            )
        )
    if len(samples) != 96:
        raise FormalAcquisitionError(
            f"frozen sample plan must contain exactly 96 rows; found {len(samples)}"
        )
    if [sample.sequence for sample in samples] != list(range(1, 97)):
        raise FormalAcquisitionError("frozen sample sequence must be exactly 001 through 096")
    identities = [sample.sample_id for sample in samples]
    if len(set(identities)) != len(identities):
        raise FormalAcquisitionError("frozen sample plan contains duplicate sample_id values")
    combinations = [
        (
            sample.configuration,
            sample.direction_deg,
            sample.continuation_id,
            sample.reposition_id,
            sample.reassembly_id,
        )
        for sample in samples
    ]
    if len(set(combinations)) != 96:
        raise FormalAcquisitionError(
            "frozen sample plan contains a duplicate or missing condition combination"
        )
    expected_combinations = {
        (configuration, direction, continuation, reposition, reassembly)
        for configuration in ("U4SYM", "U4ENC")
        for direction in (0, 90, 180, 270)
        for continuation in ("C01", "C02", "C03")
        for reposition in ("RP01", "RP02")
        for reassembly in ("AS01", "AS02")
    }
    if set(combinations) != expected_combinations:
        raise FormalAcquisitionError("frozen sample plan does not contain the exact 96 conditions")
    for sample in samples:
        match = _SAMPLE_ID_PATTERN.fullmatch(sample.sample_id)
        if match is None:
            raise FormalAcquisitionError(f"invalid frozen sample_id: {sample.sample_id}")
        encoded = match.groups()
        expected = (
            sample.configuration,
            f"{sample.direction_deg:03d}",
            sample.reassembly_id,
            sample.reposition_id,
            sample.continuation_id,
            sample.session,
            sample.block,
        )
        if encoded != expected:
            raise FormalAcquisitionError(
                f"sample_id identity does not match row fields: {sample.sample_id}"
            )
        if sample.role != "development/formal_pilot":
            raise FormalAcquisitionError("formal sample role must remain development/formal_pilot")
    return tuple(samples)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_immutable(path: Path, payload: bytes) -> None:
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise FileExistsError(
                f"refusing to overwrite existing formal acquisition artifact: {path}"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _csv_bytes(fieldnames: tuple[str, ...], rows: list[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _manifest_rows(samples: tuple[FormalSample, ...]) -> list[dict[str, Any]]:
    return [
        {
            "sequence": f"{sample.sequence:03d}",
            "sample_id": sample.sample_id,
            "measurement_mode": "rew_sweep",
            "data_origin": "real_experiment",
            "dataset_role": "development",
            "experiment_role": "formal_pilot",
            "configuration": sample.configuration,
            "direction_deg": sample.direction_deg,
            "CONT": sample.continuation_id,
            "REPOS": sample.reposition_id,
            "REASM": sample.reassembly_id,
            "session": sample.session,
            "block": sample.block,
            "expected_count": 1,
            "eligible_for_scientific_analysis": "false",
            "final_test": "false",
        }
        for sample in samples
    ]


def _preflight_checklist() -> bytes:
    checks = (
        "REW version is exactly 5.31.3",
        "Sample rate is exactly 48 kHz",
        "Sweep length is exactly 256k",
        "Repetitions is exactly 1",
        "Timing reference is No timing reference",
        "t=0 is IR peak",
        "Capture frequency is exactly 200–8000 Hz",
        "Sweep level is exactly -30 dBFS",
        "Windows output volume is exactly 50",
        "iMM-6C input volume is exactly 100",
        "Windows audio enhancements are off",
        "AGC is off",
        "EQ is off",
        "Spatial audio is off",
        "CMM29939.txt hash is verified and the file is loaded in REW",
        "Loudspeaker control positions are recorded and photographed",
        "Loudspeaker-to-device-centre distance is measured and recorded",
        "Microphone insertion depth and height are measured and recorded",
        "The 0-degree reference is recorded and photographed",
        "Open-channel count and identity are recorded",
        "Cable routing is recorded and photographed",
        "Room state and unusual noise sources are recorded",
        "Low-level mute/signal-chain test passed without clipping",
        "Hearing protection and safe listening procedure are confirmed",
        "Protocol, acquisition, safety, and data-custodian signatures are complete",
        "Primary, backup A, and backup B paths and physical media are verified",
        "Backup copy/hash/restore drill passed",
        "Diagnostic pilot remains isolated",
        "Final-test remains sealed and unread",
        "B01 start is explicitly approved by a human",
    )
    body = [
        "# FORMAL-2 acquisition preflight checklist",
        "",
        "All boxes are deliberately blank. Software must not sign or infer a pass.",
        "",
    ]
    body.extend(f"- [ ] {check}" for check in checks)
    body.extend(
        (
            "",
            "Operator: ____________________",
            "Reviewer: ____________________",
            "Date/time (Europe/London): ____________________",
            "Evidence paths / notes: ____________________",
            "",
        )
    )
    return "\n".join(body).encode("utf-8")


def _metadata_template() -> dict[str, Any]:
    return {
        "schema_version": "formal_measurement_metadata_template_v1",
        "sample_id": None,
        "measurement_mode": "rew_sweep",
        "source_format": "rew_txt",
        "data_origin": "real_experiment",
        "dataset_role": "development",
        "experiment_role": "formal_pilot",
        "eligible_for_scientific_analysis": False,
        "configuration": None,
        "direction_deg": None,
        "CONT": None,
        "REPOS": None,
        "REASM": None,
        "session": None,
        "block": None,
        "raw_mdat_path": None,
        "raw_mdat_sha256": None,
        "rew_txt_path": None,
        "rew_txt_sha256": None,
        "calibration_sha256": None,
        "calibration_loaded_evidence": None,
        "operator": None,
        "acquired_at": None,
        "manual_valid": None,
        "manual_review_reasons": [],
        "final_test": False,
        "final_test_read": False,
    }


def _backup_template() -> dict[str, Any]:
    location = {
        "path": None,
        "physical_medium_id": None,
        "device_or_provider": None,
        "is_different_physical_medium": None,
        "copy_sha256_verified": False,
        "restore_sha256_verified": False,
        "verified_by": None,
        "verified_at": None,
    }
    return {
        "schema_version": "formal_backup_verification_v1",
        "status": "not_configured",
        "primary": dict(location),
        "backup_A": dict(location),
        "backup_B": dict(location),
        "github_allowed_for_raw_formal_data": False,
        "test_file_sha256": None,
        "restored_file_sha256": None,
        "restore_drill_passed": False,
        "ready_for_B01": False,
        "unresolved_blockers": [
            "external_backup_not_configured",
            "backup_restore_drill_not_completed",
        ],
    }


def validate_backup_plan(backup_plan: Mapping[str, Any] | None) -> BackupGateResult:
    """Validate paths and physical media without inferring device independence."""
    if backup_plan is None or backup_plan.get("status") == "not_configured":
        return BackupGateResult(
            ready=False,
            status="not_configured",
            blockers=(
                "backup_restore_drill_not_completed",
                "external_backup_not_configured",
            ),
        )
    blockers: list[str] = []
    locations: dict[str, Mapping[str, Any]] = {}
    for name in ("primary", "backup_A", "backup_B"):
        value = backup_plan.get(name)
        if not isinstance(value, Mapping):
            blockers.append(f"{name}_not_configured")
            continue
        locations[name] = value
        if not str(value.get("path") or "").strip():
            blockers.append(f"{name}_path_missing")
        if not str(value.get("physical_medium_id") or "").strip():
            blockers.append(f"{name}_physical_medium_id_missing")
        combined = " ".join(
            str(value.get(field) or "")
            for field in ("path", "device_or_provider")
        ).lower()
        if "github" in combined:
            blockers.append("github_prohibited_for_formal_raw_data")
    if len(locations) == 3:
        normalized_paths = [
            str(locations[name].get("path") or "").strip().replace("\\", "/").lower().rstrip("/")
            for name in ("primary", "backup_A", "backup_B")
        ]
        if len(set(normalized_paths)) != 3:
            blockers.append("backup_paths_not_distinct")
        media = [
            str(locations[name].get("physical_medium_id") or "").strip().lower()
            for name in ("primary", "backup_A", "backup_B")
        ]
        if not media[1] or not media[2] or media[1] == media[2]:
            blockers.append("backup_locations_not_physically_independent")
        if media[1] == media[0] and media[2] == media[0]:
            blockers.append("no_backup_on_different_physical_medium")
    if backup_plan.get("restore_drill_passed") is not True:
        blockers.append("backup_restore_drill_not_completed")
    unique = tuple(sorted(set(blockers)))
    return BackupGateResult(
        ready=not unique,
        status="verified" if not unique else "blocked",
        blockers=unique,
    )


def perform_backup_restore_drill(
    source_file: str | Path,
    backup_a_file: str | Path,
    backup_b_file: str | Path,
    restored_file: str | Path,
) -> dict[str, Any]:
    """Copy one non-experiment test file, verify hashes, and restore from A."""
    source = Path(source_file)
    targets = (Path(backup_a_file), Path(backup_b_file), Path(restored_file))
    if not source.is_file():
        raise FileNotFoundError(f"backup drill source file is missing: {source}")
    resolved = [source.resolve(), *(target.resolve() for target in targets)]
    if len(set(resolved)) != 4:
        raise FormalAcquisitionError("backup drill source and targets must be distinct paths")
    existing = [target for target in targets if target.exists()]
    if existing:
        raise FileExistsError(f"backup drill target already exists: {existing[0]}")
    backup_a, backup_b, restored = targets
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, backup_a)
    shutil.copyfile(source, backup_b)
    shutil.copyfile(backup_a, restored)
    hashes = {
        "primary": _sha256(source),
        "backup_A": _sha256(backup_a),
        "backup_B": _sha256(backup_b),
        "restored": _sha256(restored),
    }
    if len(set(hashes.values())) != 1:
        raise FormalAcquisitionError("backup drill SHA-256 verification failed")
    return {
        "schema_version": "formal_backup_restore_drill_v1",
        "status": "passed",
        "data_origin": "simulated",
        "dataset_role": "software_validation",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "source_file": str(source),
        "backup_A_file": str(backup_a),
        "backup_B_file": str(backup_b),
        "restored_file": str(restored),
        "sha256_by_copy": hashes,
    }


def verify_formal_package_hashes(root: str | Path) -> dict[str, Any]:
    """Verify every artifact explicitly listed by the FORMAL-2 hash manifest."""
    root_path = Path(root)
    manifest_path = root_path / "07_hashes" / "SHA256SUMS.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "formal_sha256_manifest_v1":
        raise FormalAcquisitionError("unsupported formal SHA-256 manifest schema")
    records = payload.get("artifacts")
    if not isinstance(records, list) or not records:
        raise FormalAcquisitionError("formal SHA-256 manifest has no artifacts")
    checked: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise FormalAcquisitionError("invalid formal SHA-256 artifact record")
        relative = Path(str(record.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise FormalAcquisitionError("formal SHA-256 artifact path escapes package root")
        artifact = root_path / relative
        if not artifact.is_file():
            raise FileNotFoundError(f"formal package artifact is missing: {relative}")
        actual = _sha256(artifact)
        if actual != record.get("sha256"):
            raise FormalAcquisitionError(f"SHA-256 mismatch: {relative}")
        checked.append(relative.as_posix())
    return {
        "verified": True,
        "artifact_count": len(checked),
        "verified_paths": checked,
    }


def _validate_calibration_content(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    sensitivity_header = next(
        (line.strip() for line in lines if line.strip().lower().startswith("*1000hz")),
        None,
    )
    if sensitivity_header is None:
        raise FormalAcquisitionError("calibration file is missing the *1000Hz header")
    frequencies: list[float] = []
    corrections: list[float] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(("*", "#")):
            continue
        fields = re.split(r"[\s,;]+", stripped)
        if len(fields) < 2:
            raise FormalAcquisitionError("calibration file contains a malformed data row")
        try:
            frequency = float(fields[0])
            correction = float(fields[1])
        except ValueError as exc:
            raise FormalAcquisitionError(
                "calibration file contains a non-numeric data row"
            ) from exc
        if not (math.isfinite(frequency) and math.isfinite(correction)):
            raise FormalAcquisitionError("calibration values must be finite")
        frequencies.append(frequency)
        corrections.append(correction)
    if len(frequencies) < 5:
        raise FormalAcquisitionError("calibration file must contain at least five data rows")
    if any(right <= left for left, right in zip(frequencies, frequencies[1:])):
        raise FormalAcquisitionError(
            "calibration frequencies must be strictly increasing and unique"
        )
    if frequencies[0] <= 0.0:
        raise FormalAcquisitionError("calibration frequencies must be positive")
    return {
        "sensitivity_header": sensitivity_header,
        "data_row_count": len(frequencies),
        "frequency_min_hz": frequencies[0],
        "frequency_max_hz": frequencies[-1],
    }


def _atomic_replace(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"temporary formal artifact already exists: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _refresh_formal_hash_manifest(root: Path) -> tuple[Path, Path]:
    hashes_dir = root / "07_hashes"
    json_path = hashes_dir / "SHA256SUMS.json"
    text_path = hashes_dir / "SHA256SUMS.txt"
    excluded = {json_path.resolve(), text_path.resolve()}
    artifacts = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.resolve() not in excluded
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in artifacts
    ]
    json_payload = _json_bytes(
        {
            "schema_version": "formal_sha256_manifest_v1",
            "algorithm": "SHA-256",
            "artifacts": records,
        }
    )
    text_payload = "".join(
        f"{record['sha256']}  {record['path']}\n" for record in records
    ).encode("utf-8")
    _atomic_replace(json_path, json_payload)
    _atomic_replace(text_path, text_payload)
    return json_path, text_path


def register_formal_calibration(
    root: str | Path,
    *,
    source_path: str | Path,
    copy_path: str | Path,
    screenshot_path: str | Path,
    checked_at: str,
    input_device: str,
    evidence_status: str,
    evidence_assessed_by: str,
    evidence_observations: tuple[str, ...],
) -> CalibrationRegistrationResult:
    """Register immutable calibration evidence and update only its blockers."""
    root_path = Path(root)
    source = Path(source_path)
    copied = Path(copy_path)
    screenshot = Path(screenshot_path)
    expected_copy = root_path / "01_calibration" / "CMM29939.txt"
    expected_screenshot = root_path / "01_calibration" / "REW_CMM29939_LOADED.png"
    if copied.resolve() != expected_copy.resolve():
        raise FormalAcquisitionError(
            f"calibration copy_path must be the formal package path: {expected_copy}"
        )
    if screenshot.resolve() != expected_screenshot.resolve():
        raise FormalAcquisitionError(
            f"calibration screenshot_path must be: {expected_screenshot}"
        )
    if not source.is_file() or not copied.is_file():
        raise FileNotFoundError("CMM29939.txt source or formal copy is missing")
    if not screenshot.is_file():
        raise FileNotFoundError("REW_CMM29939_LOADED.png is missing")
    screenshot_bytes = screenshot.read_bytes()
    if len(screenshot_bytes) <= 8 or not screenshot_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise FormalAcquisitionError("calibration load evidence must be a readable PNG file")
    if input_device != "iMM-6C":
        raise FormalAcquisitionError("formal calibration input_device must be iMM-6C")
    allowed_evidence = {
        "verified_input_binding",
        "insufficient_input_binding_evidence",
    }
    if evidence_status not in allowed_evidence:
        raise FormalAcquisitionError("unsupported calibration evidence_status")
    if not evidence_assessed_by.strip() or not evidence_observations:
        raise FormalAcquisitionError(
            "calibration screenshot assessment requires assessor and observations"
        )
    parsed_checked_at = datetime.fromisoformat(checked_at)
    if parsed_checked_at.tzinfo is None:
        raise FormalAcquisitionError("calibration checked_at must include a timezone")
    source_sha = _sha256(source)
    copied_sha = _sha256(copied)
    if source_sha != copied_sha:
        raise FormalAcquisitionError("calibration source and formal copy SHA-256 differ")
    calibration_definition = _validate_calibration_content(copied)
    screenshot_sha = _sha256(screenshot)

    status_path = root_path / "00_protocol_and_manifests" / "preflight_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("final_test_read") is not False:
        raise FormalAcquisitionError("formal calibration registration requires sealed final-test")
    if status.get("formal_measurement_started") is not False:
        raise FormalAcquisitionError(
            "formal calibration registration must precede formal measurement"
        )
    history_dir = root_path / "07_hashes" / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    old_hash_json = root_path / "07_hashes" / "SHA256SUMS.json"
    old_hash_text = root_path / "07_hashes" / "SHA256SUMS.txt"
    history_json = history_dir / "FORMAL_2_BASELINE_SHA256SUMS.json"
    history_text = history_dir / "FORMAL_2_BASELINE_SHA256SUMS.txt"
    if not history_json.exists():
        _write_immutable(history_json, old_hash_json.read_bytes())
    if not history_text.exists():
        _write_immutable(history_text, old_hash_text.read_bytes())
    status_history = (
        root_path
        / "00_protocol_and_manifests"
        / "preflight_status_history"
        / "FORMAL_2_PREFLIGHT_STATUS.json"
    )
    if not status_history.exists():
        _write_immutable(status_history, status_path.read_bytes())

    evidence_verified = evidence_status == "verified_input_binding"
    registration = {
        "schema_version": "formal_calibration_registration_v1",
        "checked_at": parsed_checked_at.isoformat(),
        "calibration_file": {
            "filename": copied.name,
            "sha256": copied_sha,
            "bytes": copied.stat().st_size,
            "source_path": str(source.resolve()),
            "copy_path": str(copied.resolve()),
            "registered_in_place": source.resolve() == copied.resolve(),
            "content_modified_by_registration": False,
            "format_validation": calibration_definition,
        },
        "load_evidence": {
            "path": str(screenshot.resolve()),
            "sha256": screenshot_sha,
            "bytes": screenshot.stat().st_size,
            "status": evidence_status,
            "assessed_by": evidence_assessed_by,
            "observations": list(evidence_observations),
        },
        "input_device_binding": {
            "device_name": input_device,
            "role": "formal_acquisition_input",
            "calibration_filename": copied.name,
            "calibration_sha256": copied_sha,
            "status": "verified" if evidence_verified else "pending_evidence",
        },
        "data_origin": "real_experiment_infrastructure",
        "formal_measurement_started": False,
        "scientifically_eligible": False,
        "final_test_read": False,
    }
    registration_path = root_path / "01_calibration" / "calibration_registration.json"
    _write_immutable(registration_path, _json_bytes(registration))

    blockers = set(str(item) for item in status.get("unresolved_blockers", ()))
    blockers.discard("calibration_file_missing")
    if evidence_verified:
        blockers.discard("calibration_load_evidence_missing")
    else:
        blockers.add("calibration_load_evidence_missing")
    updated_status = {
        **status,
        "calibration_status": (
            "verified_for_iMM-6C_input"
            if evidence_verified
            else "file_registered_input_binding_evidence_insufficient"
        ),
        "calibration_registration_path": registration_path.relative_to(root_path).as_posix(),
        "calibration_sha256": copied_sha,
        "calibration_evidence_sha256": screenshot_sha,
        "ready_for_B01": False,
        "unresolved_blockers": sorted(blockers),
    }
    updated_bytes = _json_bytes(updated_status)
    if status_path.read_bytes() != updated_bytes:
        _atomic_replace(status_path, updated_bytes)
    _refresh_formal_hash_manifest(root_path)
    verify_formal_package_hashes(root_path)
    if _sha256(copied) != copied_sha:
        raise FormalAcquisitionError("calibration file changed during registration")
    return CalibrationRegistrationResult(
        registration_path=registration_path,
        preflight_status_path=status_path,
        ready_for_b01=False,
        unresolved_blockers=tuple(sorted(blockers)),
        calibration_sha256=copied_sha,
        screenshot_sha256=screenshot_sha,
    )


def _external_backup_checklist() -> bytes:
    return """# 后续启用外置备份操作清单

本轮状态为 `not_configured`，以下项目均未执行、未签署。

- [ ] 填写 primary 的绝对路径、设备/介质名称与物理介质 ID。
- [ ] 填写 backup_A 的绝对路径、设备/介质名称与物理介质 ID。
- [ ] 填写 backup_B 的绝对路径、设备/介质名称与物理介质 ID。
- [ ] 确认 backup_A 与 backup_B 是独立位置，不是同一磁盘的文件夹或分区。
- [ ] 确认至少一个 backup 位于不同物理介质。
- [ ] 确认 GitHub 不承载正式原始 `.mdat`、REW TXT、sidecar 或照片。
- [ ] 创建不含实验数据的小型测试文件，记录主副本 SHA-256。
- [ ] 分别复制到 backup_A 与 backup_B，并逐份复核 SHA-256。
- [ ] 从至少一个外置备份恢复到新的空路径并复核 SHA-256。
- [ ] 由数据保管人与采集负责人记录时间、签名和证据路径。
- [ ] 重新运行备份门禁；只有全部通过才可移除相关 blocker。
""".encode("utf-8")


def prepare_formal_acquisition_package(
    root: str | Path,
    *,
    protocol_path: str | Path,
    acquisition_plan_path: str | Path,
    calibration_source: str | Path | None,
    backup_plan: Mapping[str, Any] | None,
) -> FormalAcquisitionPackage:
    """Create or verify the empty, immutable FORMAL-2 acquisition package."""
    if backup_plan is not None:
        raise FormalAcquisitionError(
            "configured backup plans require explicit validation before package readiness"
        )
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    for relative in _DIRECTORIES:
        (root_path / relative).mkdir(parents=True, exist_ok=True)

    protocol = Path(protocol_path)
    plan = Path(acquisition_plan_path)
    samples = load_frozen_sample_plan(plan)
    manifest_dir = root_path / "00_protocol_and_manifests"
    hashes_dir = root_path / "07_hashes"
    protocol_copy = manifest_dir / protocol.name
    plan_copy = manifest_dir / plan.name
    _write_immutable(protocol_copy, protocol.read_bytes())
    _write_immutable(plan_copy, plan.read_bytes())

    manifest_fields = (
        "sequence",
        "sample_id",
        "measurement_mode",
        "data_origin",
        "dataset_role",
        "experiment_role",
        "configuration",
        "direction_deg",
        "CONT",
        "REPOS",
        "REASM",
        "session",
        "block",
        "expected_count",
        "eligible_for_scientific_analysis",
        "final_test",
    )
    sample_manifest = manifest_dir / "formal_sample_manifest.csv"
    manifest_rows = _manifest_rows(samples)
    _write_immutable(sample_manifest, _csv_bytes(manifest_fields, manifest_rows))

    preflight_checklist = manifest_dir / "preflight_checklist.md"
    _write_immutable(preflight_checklist, _preflight_checklist())
    geometry = root_path / "02_photos_and_geometry" / "geometry_record.csv"
    _write_immutable(
        geometry,
        _csv_bytes(
            (
                "session",
                "recorded_at",
                "operator",
                "speaker_to_device_centre_mm",
                "microphone_insertion_depth_mm",
                "microphone_height_mm",
                "device_height_mm",
                "zero_degree_reference",
                "open_channels",
                "speaker_controls",
                "cable_routing",
                "photo_paths",
                "photo_sha256",
                "review_status",
                "reviewer",
                "notes",
            ),
            [],
        ),
    )
    environment = root_path / "03_environment_logs" / "environment_log.csv"
    _write_immutable(
        environment,
        _csv_bytes(
            (
                "session",
                "block",
                "recorded_at",
                "temperature_c",
                "relative_humidity_percent",
                "background_noise_observation",
                "unusual_noise_sources",
                "room_state",
                "operator",
                "notes",
            ),
            [],
        ),
    )
    session_log = root_path / "03_environment_logs" / "session_log.csv"
    _write_immutable(
        session_log,
        _csv_bytes(
            (
                "session",
                "block",
                "started_at",
                "ended_at",
                "operator",
                "planned_first_sequence",
                "planned_last_sequence",
                "completed_sample_ids",
                "stopped",
                "deviation_ids",
                "human_review_status",
                "notes",
            ),
            [],
        ),
    )
    deviation = root_path / "08_deviations_and_manual_review" / "deviation_log.csv"
    _write_immutable(
        deviation,
        _csv_bytes(
            (
                "deviation_id",
                "recorded_at",
                "session",
                "block",
                "affected_sample_ids",
                "reason",
                "files_preserved",
                "disposition",
                "approved_by",
                "approval_time",
                "notes",
            ),
            [],
        ),
    )
    metadata = manifest_dir / "measurement_metadata_template.json"
    _write_immutable(metadata, _json_bytes(_metadata_template()))
    backup_verification = hashes_dir / "backup_verification.json"
    _write_immutable(backup_verification, _json_bytes(_backup_template()))
    backup_checklist = hashes_dir / "ENABLE_EXTERNAL_BACKUP_CHECKLIST_ZH.md"
    _write_immutable(backup_checklist, _external_backup_checklist())

    b01_fields = tuple(manifest_fields) + (
        "acquisition_status",
        "operator",
        "acquired_at",
        "raw_mdat_path",
        "raw_mdat_sha256",
        "rew_txt_path",
        "rew_txt_sha256",
        "sidecar_path",
        "sidecar_sha256",
        "clipping_observed",
        "manual_review_status",
        "notes",
    )
    b01_rows = [
        {
            **row,
            **{field: "" for field in b01_fields if field not in row},
        }
        for row in manifest_rows[:12]
    ]
    b01_sheet = manifest_dir / "B01_ACQUISITION_SHEET.csv"
    _write_immutable(b01_sheet, _csv_bytes(b01_fields, b01_rows))

    blockers = [
        "protocol_signatures_missing",
        "preflight_manual_checks_incomplete",
        "geometry_record_incomplete",
        "environment_record_incomplete",
        "calibration_load_evidence_missing",
        "external_backup_not_configured",
        "backup_restore_drill_not_completed",
        "B01_manual_authorization_missing",
    ]
    calibration_destination = root_path / "01_calibration" / "CMM29939.txt"
    if calibration_source is None or not Path(calibration_source).is_file():
        blockers.append("calibration_file_missing")
    else:
        source = Path(calibration_source)
        if calibration_destination.exists():
            if _sha256(calibration_destination) != _sha256(source):
                raise FileExistsError(
                    "refusing to overwrite a different calibration file in formal package"
                )
        else:
            shutil.copyfile(source, calibration_destination)

    preflight_payload = {
        "schema_version": "formal_preflight_status_v1",
        "plan_id": "FORMAL-U4-4DIR-SWEEP-REV001",
        "protocol_revision": "rev-002",
        "package_purpose": "acquisition_infrastructure_only",
        "formal_measurement_started": False,
        "real_data_imported_or_analyzed": False,
        "final_test_read": False,
        "backup_status": "not_configured",
        "manual_checks_complete": False,
        "ready_for_B01": False,
        "unresolved_blockers": sorted(blockers),
    }
    preflight_status = manifest_dir / "preflight_status.json"
    _write_immutable(preflight_status, _json_bytes(preflight_payload))

    hashed_paths = sorted(
        (
            path
            for path in root_path.rglob("*")
            if path.is_file() and path.parent != hashes_dir
        ),
        key=lambda path: path.relative_to(root_path).as_posix(),
    )
    hashed_paths.extend(
        sorted(
            (
                path
                for path in hashes_dir.iterdir()
                if path.is_file() and path.name not in {"SHA256SUMS.json", "SHA256SUMS.txt"}
            ),
            key=lambda path: path.name,
        )
    )
    records = [
        {
            "path": path.relative_to(root_path).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in hashed_paths
    ]
    sha256_json = hashes_dir / "SHA256SUMS.json"
    sha256_text = hashes_dir / "SHA256SUMS.txt"
    _write_immutable(
        sha256_json,
        _json_bytes(
            {
                "schema_version": "formal_sha256_manifest_v1",
                "algorithm": "SHA-256",
                "artifacts": records,
            }
        ),
    )
    _write_immutable(
        sha256_text,
        (
            "".join(f"{record['sha256']}  {record['path']}\n" for record in records)
        ).encode("utf-8"),
    )
    return FormalAcquisitionPackage(
        root=root_path,
        sample_manifest=sample_manifest,
        b01_sheet=b01_sheet,
        preflight_checklist=preflight_checklist,
        preflight_status=preflight_status,
        backup_verification=backup_verification,
        sha256_json=sha256_json,
        sha256_text=sha256_text,
        ready_for_b01=False,
        unresolved_blockers=tuple(sorted(blockers)),
    )

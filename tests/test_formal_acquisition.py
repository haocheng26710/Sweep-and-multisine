from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from acoustic_encoder.formal_acquisition import (
    load_frozen_sample_plan,
    perform_backup_restore_drill,
    prepare_formal_acquisition_package,
    validate_backup_plan,
    verify_formal_package_hashes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = PROJECT_ROOT / "docs" / "experiment" / "FORMAL_ACQUISITION_PLAN_REV001.md"
PROTOCOL_PATH = PROJECT_ROOT / "docs" / "experiment" / "RESEARCH_PROTOCOL_REV002.md"


def test_frozen_plan_loads_exact_96_rows_and_b01_order() -> None:
    samples = load_frozen_sample_plan(PLAN_PATH)

    assert len(samples) == 96
    assert len({sample.sample_id for sample in samples}) == 96
    assert [sample.sequence for sample in samples] == list(range(1, 97))
    assert [sample.direction_deg for sample in samples[:12]] == [
        0,
        0,
        0,
        90,
        90,
        90,
        180,
        180,
        180,
        270,
        270,
        270,
    ]
    assert {
        (sample.configuration, sample.reassembly_id, sample.reposition_id, sample.block)
        for sample in samples[:12]
    } == {("U4SYM", "AS01", "RP01", "B01")}


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_package_creation_is_idempotent_and_blocked_when_evidence_is_blank(
    tmp_path: Path,
) -> None:
    root = tmp_path / "FORMAL-U4-4DIR-SWEEP-REV001"

    result = prepare_formal_acquisition_package(
        root,
        protocol_path=PROTOCOL_PATH,
        acquisition_plan_path=PLAN_PATH,
        calibration_source=None,
        backup_plan=None,
    )

    expected_directories = {
        "00_protocol_and_manifests",
        "01_calibration",
        "02_photos_and_geometry",
        "03_environment_logs",
        "07_hashes",
        "08_deviations_and_manual_review",
        *(f"04_raw_rew_mdat/S0{index}" for index in range(1, 5)),
        *(f"05_exported_rew_txt/S0{index}" for index in range(1, 5)),
        *(f"06_metadata_sidecars/S0{index}" for index in range(1, 5)),
    }
    assert expected_directories <= {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir()
    }
    with result.sample_manifest.open(encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    with result.b01_sheet.open(encoding="utf-8", newline="") as handle:
        b01_rows = list(csv.DictReader(handle))
    assert len(manifest_rows) == 96
    assert len({row["sample_id"] for row in manifest_rows}) == 96
    assert len(b01_rows) == 12
    assert [row["sample_id"] for row in b01_rows] == [
        row["sample_id"] for row in manifest_rows[:12]
    ]
    assert {row["data_origin"] for row in manifest_rows} == {"real_experiment"}
    assert {row["eligible_for_scientific_analysis"] for row in manifest_rows} == {
        "false"
    }
    status = json.loads(result.preflight_status.read_text(encoding="utf-8"))
    backup = json.loads(result.backup_verification.read_text(encoding="utf-8"))
    assert status["ready_for_B01"] is False
    assert "calibration_file_missing" in status["unresolved_blockers"]
    assert "external_backup_not_configured" in status["unresolved_blockers"]
    assert backup["status"] == "not_configured"
    assert backup["ready_for_B01"] is False
    checklist = result.preflight_checklist.read_text(encoding="utf-8")
    assert "- [x]" not in checklist.lower()
    assert "- [ ] REW version is exactly 5.31.3" in checklist
    first_hashes = _tree_hashes(root)

    repeated = prepare_formal_acquisition_package(
        root,
        protocol_path=PROTOCOL_PATH,
        acquisition_plan_path=PLAN_PATH,
        calibration_source=None,
        backup_plan=None,
    )

    assert repeated.preflight_status == result.preflight_status
    assert _tree_hashes(root) == first_hashes


def test_backup_gate_rejects_different_folders_on_the_same_physical_disk() -> None:
    result = validate_backup_plan(
        {
            "status": "configured",
            "primary": {
                "path": "D:/formal-primary",
                "physical_medium_id": "disk-001",
            },
            "backup_A": {
                "path": "D:/backup-a",
                "physical_medium_id": "disk-001",
            },
            "backup_B": {
                "path": "D:/backup-b",
                "physical_medium_id": "disk-001",
            },
            "restore_drill_passed": True,
        }
    )

    assert result.ready is False
    assert "backup_locations_not_physically_independent" in result.blockers


def test_backup_drill_copies_hashes_restores_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    source = tmp_path / "primary" / "synthetic-backup-test.bin"
    source.parent.mkdir()
    source.write_bytes(b"FORMAL-2 synthetic software-validation backup drill\n")
    backup_a = tmp_path / "medium-a" / source.name
    backup_b = tmp_path / "medium-b" / source.name
    restored = tmp_path / "restore-empty" / source.name

    evidence = perform_backup_restore_drill(source, backup_a, backup_b, restored)

    assert evidence["status"] == "passed"
    assert evidence["data_origin"] == "simulated"
    assert evidence["run_purpose"] == "software_validation"
    assert len(set(evidence["sha256_by_copy"].values())) == 1
    assert restored.read_bytes() == source.read_bytes()
    with pytest.raises(FileExistsError, match="already exists"):
        perform_backup_restore_drill(source, backup_a, backup_b, restored)


def test_backup_gate_accepts_only_verified_independent_media_and_rejects_github() -> None:
    verified = {
        "status": "configured",
        "primary": {"path": "D:/formal-primary", "physical_medium_id": "disk-001"},
        "backup_A": {"path": "E:/formal-a", "physical_medium_id": "usb-002"},
        "backup_B": {"path": "F:/formal-b", "physical_medium_id": "nas-003"},
        "restore_drill_passed": True,
    }

    assert validate_backup_plan(verified).ready is True
    verified["backup_B"] = {
        "path": "https://github.com/example/formal-raw",
        "physical_medium_id": "github",
    }
    rejected = validate_backup_plan(verified)
    assert rejected.ready is False
    assert "github_prohibited_for_formal_raw_data" in rejected.blockers


def test_package_hash_verification_detects_tampering_and_generator_will_not_overwrite(
    tmp_path: Path,
) -> None:
    root = tmp_path / "formal"
    package = prepare_formal_acquisition_package(
        root,
        protocol_path=PROTOCOL_PATH,
        acquisition_plan_path=PLAN_PATH,
        calibration_source=None,
        backup_plan=None,
    )

    verified = verify_formal_package_hashes(root)
    assert verified["verified"] is True
    assert verified["artifact_count"] >= 10
    package.preflight_checklist.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_formal_package_hashes(root)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare_formal_acquisition_package(
            root,
            protocol_path=PROTOCOL_PATH,
            acquisition_plan_path=PLAN_PATH,
            calibration_source=None,
            backup_plan=None,
        )


def test_frozen_plan_rejects_missing_and_duplicate_rows(tmp_path: Path) -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    row_001 = next(line for line in text.splitlines() if line.startswith("| 001 |"))
    row_002 = next(line for line in text.splitlines() if line.startswith("| 002 |"))
    missing = tmp_path / "missing.md"
    missing.write_text(text.replace(row_002 + "\n", "", 1), encoding="utf-8")
    duplicate = tmp_path / "duplicate.md"
    duplicate_row = row_002.replace(
        "F002-SWEEP-U4SYM-D000-AS01-RP01-C02-S01-B01",
        "F002-SWEEP-U4SYM-D000-AS01-RP01-C01-S01-B01",
    )
    duplicate.write_text(text.replace(row_002, duplicate_row, 1), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly 96 rows"):
        load_frozen_sample_plan(missing)
    with pytest.raises(ValueError, match="duplicate sample_id"):
        load_frozen_sample_plan(duplicate)


def test_explicit_calibration_is_copied_byte_for_byte_and_hashed(tmp_path: Path) -> None:
    calibration = tmp_path / "source" / "CMM29939.txt"
    calibration.parent.mkdir()
    calibration.write_bytes(b"synthetic calibration fixture; not for experiment\n")
    root = tmp_path / "formal"

    package = prepare_formal_acquisition_package(
        root,
        protocol_path=PROTOCOL_PATH,
        acquisition_plan_path=PLAN_PATH,
        calibration_source=calibration,
        backup_plan=None,
    )

    copied = root / "01_calibration" / "CMM29939.txt"
    assert copied.read_bytes() == calibration.read_bytes()
    assert "calibration_file_missing" not in package.unresolved_blockers
    assert "calibration_load_evidence_missing" in package.unresolved_blockers
    assert verify_formal_package_hashes(root)["verified"] is True

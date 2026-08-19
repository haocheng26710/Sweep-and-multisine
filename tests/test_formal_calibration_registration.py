from __future__ import annotations

import json
from pathlib import Path

import pytest

from acoustic_encoder.formal_acquisition import (
    prepare_formal_acquisition_package,
    register_formal_calibration,
    verify_formal_package_hashes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = PROJECT_ROOT / "docs" / "experiment" / "FORMAL_ACQUISITION_PLAN_REV001.md"
PROTOCOL_PATH = PROJECT_ROOT / "docs" / "experiment" / "RESEARCH_PROTOCOL_REV002.md"


def _package(tmp_path: Path) -> Path:
    root = tmp_path / "formal"
    prepare_formal_acquisition_package(
        root,
        protocol_path=PROTOCOL_PATH,
        acquisition_plan_path=PLAN_PATH,
        calibration_source=None,
        backup_plan=None,
    )
    return root


def _add_calibration_evidence(root: Path) -> tuple[Path, Path, bytes]:
    calibration = root / "01_calibration" / "CMM29939.txt"
    original = (
        b"*1000Hz\t-36.2\n\n"
        b"20.00\t2.0\n40.00\t1.0\n80.00\t0.5\n160.00\t0.0\n320.00\t-0.5\n"
    )
    calibration.write_bytes(original)
    screenshot = root / "01_calibration" / "REW_CMM29939_LOADED.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-software-validation-image")
    return calibration, screenshot, original


def test_insufficient_screenshot_keeps_load_blocker_and_all_other_blockers(
    tmp_path: Path,
) -> None:
    root = _package(tmp_path)
    calibration, screenshot, original = _add_calibration_evidence(root)
    before = json.loads(
        (root / "00_protocol_and_manifests" / "preflight_status.json").read_text(
            encoding="utf-8"
        )
    )

    result = register_formal_calibration(
        root,
        source_path=calibration,
        copy_path=calibration,
        screenshot_path=screenshot,
        checked_at="2026-08-19T20:00:00+01:00",
        input_device="iMM-6C",
        evidence_status="insufficient_input_binding_evidence",
        evidence_assessed_by="software-validation-test",
        evidence_observations=("Screenshot does not prove microphone calibration binding.",),
    )

    assert calibration.read_bytes() == original
    assert result.ready_for_b01 is False
    assert "calibration_file_missing" not in result.unresolved_blockers
    assert "calibration_load_evidence_missing" in result.unresolved_blockers
    assert "external_backup_not_configured" in result.unresolved_blockers
    assert set(before["unresolved_blockers"]) - {"calibration_file_missing"} == set(
        result.unresolved_blockers
    )
    registration = json.loads(result.registration_path.read_text(encoding="utf-8"))
    assert registration["input_device_binding"]["device_name"] == "iMM-6C"
    assert registration["input_device_binding"]["status"] == "pending_evidence"
    assert registration["calibration_file"]["bytes"] == len(original)
    assert verify_formal_package_hashes(root)["verified"] is True


def test_verified_input_binding_clears_only_two_calibration_blockers(
    tmp_path: Path,
) -> None:
    root = _package(tmp_path)
    calibration, screenshot, _ = _add_calibration_evidence(root)

    result = register_formal_calibration(
        root,
        source_path=calibration,
        copy_path=calibration,
        screenshot_path=screenshot,
        checked_at="2026-08-19T20:01:00+01:00",
        input_device="iMM-6C",
        evidence_status="verified_input_binding",
        evidence_assessed_by="software-validation-test",
        evidence_observations=("Synthetic fixture explicitly proves input binding.",),
    )

    assert "calibration_file_missing" not in result.unresolved_blockers
    assert "calibration_load_evidence_missing" not in result.unresolved_blockers
    assert "external_backup_not_configured" in result.unresolved_blockers
    assert result.ready_for_b01 is False
    registration = json.loads(result.registration_path.read_text(encoding="utf-8"))
    assert registration["input_device_binding"]["status"] == "verified"


def test_malformed_calibration_fails_without_changing_preflight(tmp_path: Path) -> None:
    root = _package(tmp_path)
    calibration = root / "01_calibration" / "CMM29939.txt"
    calibration.write_text("not a calibration file\n", encoding="utf-8")
    screenshot = root / "01_calibration" / "REW_CMM29939_LOADED.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic")
    status = root / "00_protocol_and_manifests" / "preflight_status.json"
    before = status.read_bytes()

    with pytest.raises(ValueError, match="1000Hz"):
        register_formal_calibration(
            root,
            source_path=calibration,
            copy_path=calibration,
            screenshot_path=screenshot,
            checked_at="2026-08-19T20:02:00+01:00",
            input_device="iMM-6C",
            evidence_status="verified_input_binding",
            evidence_assessed_by="software-validation-test",
            evidence_observations=("Synthetic claim.",),
        )

    assert status.read_bytes() == before
    assert not (root / "01_calibration" / "calibration_registration.json").exists()

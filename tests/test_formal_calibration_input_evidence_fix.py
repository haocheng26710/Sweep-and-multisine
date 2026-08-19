from __future__ import annotations

import json
from pathlib import Path

import pytest

from acoustic_encoder.formal_acquisition import (
    prepare_formal_acquisition_package,
    register_formal_calibration,
    supplement_formal_mic_input_evidence,
    verify_formal_package_hashes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = PROJECT_ROOT / "docs" / "experiment" / "FORMAL_ACQUISITION_PLAN_REV001.md"
PROTOCOL_PATH = PROJECT_ROOT / "docs" / "experiment" / "RESEARCH_PROTOCOL_REV002.md"


def _pending_package(tmp_path: Path) -> tuple[Path, Path, bytes]:
    root = tmp_path / "formal"
    prepare_formal_acquisition_package(
        root,
        protocol_path=PROTOCOL_PATH,
        acquisition_plan_path=PLAN_PATH,
        calibration_source=None,
        backup_plan=None,
    )
    calibration = root / "01_calibration" / "CMM29939.txt"
    calibration.write_bytes(
        b"*1000Hz\t-36.2\n\n"
        b"20\t2\n40\t1\n80\t0.5\n160\t0\n320\t-0.5\n"
    )
    old_screenshot = root / "01_calibration" / "REW_CMM29939_LOADED.png"
    old_screenshot.write_bytes(b"\x89PNG\r\n\x1a\nold-insufficient-evidence")
    register_formal_calibration(
        root,
        source_path=calibration,
        copy_path=calibration,
        screenshot_path=old_screenshot,
        checked_at="2026-08-19T20:00:00+01:00",
        input_device="iMM-6C",
        evidence_status="insufficient_input_binding_evidence",
        evidence_assessed_by="software-validation-test",
        evidence_observations=("Old screenshot shows only output calibration.",),
    )
    uploaded = root / "01_calibration" / "REW_CMM29939_MIC_INPUT_LOADED.png.png"
    image_bytes = b"\x89PNG\r\n\x1a\nnew-explicit-mic-input-evidence"
    uploaded.write_bytes(image_bytes)
    return root, uploaded, image_bytes


def test_verified_mic_input_evidence_is_canonicalized_and_clears_only_load_blocker(
    tmp_path: Path,
) -> None:
    root, uploaded, image_bytes = _pending_package(tmp_path)
    status_path = root / "00_protocol_and_manifests" / "preflight_status.json"
    before = json.loads(status_path.read_text(encoding="utf-8"))

    result = supplement_formal_mic_input_evidence(
        root,
        source_screenshot_path=uploaded,
        checked_at="2026-08-19T20:10:00+01:00",
        assessed_by="software-validation-test",
        observations=("Explicit iMM-6C input and Mic calibration files are visible.",),
        rew_input_is_imm6c_microphone=True,
        cmm_is_in_mic_calibration_files=True,
        soundcard_output_not_used_as_mic_evidence=True,
    )

    canonical = root / "01_calibration" / "REW_CMM29939_MIC_INPUT_LOADED.png"
    assert uploaded.read_bytes() == image_bytes
    assert canonical.read_bytes() == image_bytes
    assert result.input_binding_status == "verified"
    assert result.ready_for_b01 is False
    assert "calibration_load_evidence_missing" not in result.unresolved_blockers
    assert "calibration_file_missing" not in result.unresolved_blockers
    assert "external_backup_not_configured" in result.unresolved_blockers
    assert set(before["unresolved_blockers"]) - {
        "calibration_load_evidence_missing"
    } == set(result.unresolved_blockers)
    updated = json.loads(status_path.read_text(encoding="utf-8"))
    assert updated["calibration_input_binding_status"] == "verified"
    assert verify_formal_package_hashes(root)["verified"] is True


def test_mic_input_fix_fails_closed_unless_all_visual_requirements_are_true(
    tmp_path: Path,
) -> None:
    root, uploaded, _ = _pending_package(tmp_path)
    status = root / "00_protocol_and_manifests" / "preflight_status.json"
    before = status.read_bytes()

    with pytest.raises(ValueError, match="all three explicit visual requirements"):
        supplement_formal_mic_input_evidence(
            root,
            source_screenshot_path=uploaded,
            checked_at="2026-08-19T20:10:00+01:00",
            assessed_by="software-validation-test",
            observations=("Ambiguous screenshot.",),
            rew_input_is_imm6c_microphone=True,
            cmm_is_in_mic_calibration_files=False,
            soundcard_output_not_used_as_mic_evidence=True,
        )

    assert status.read_bytes() == before
    assert not (
        root / "01_calibration" / "REW_CMM29939_MIC_INPUT_LOADED.png"
    ).exists()

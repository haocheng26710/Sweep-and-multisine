from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import zipfile

import pytest

from acoustic_encoder.formal_real_import import (
    Formal3ImportError,
    inspect_formal3_archive,
    inspect_formal3_measurements,
    run_formal3_import_qc,
    verify_formal3_output_hashes,
)
from acoustic_encoder.research_gate import ResearchGateError, enforce_research_gate
from acoustic_encoder.schemas import load_feature_set


ACTIVE_GROUPS = {
    "B01_U4SYM_AS01": "B01_U4SYM_AS01",
    "B02_U4SYM_AS01": "B02_U4SYM_AS01",
    "B03_U4ENC_AS01": "B03_U4ENC_AS01",
    "B04_U4ENC_AS01": "B04_U4ENC_AS01",
    "B05_U4ENC_AS02": "B05_U4ENC_AS02",
    "B07_U4SYM_AS02": "B07_U4SYM_AS02",
}

EXCLUDED_FILENAMES = (
    "R B03_U4ENC_A000_C04.txt",
    "R B03_U4ENC_A090_C04.txt",
    "R B03_U4ENC_A180_C04.txt",
    "R B03_U4ENC_A270_C01.txt",
    "R B04_U4ENC_A000_C04.txt",
    "R B04_U4ENC_A090_C04.txt",
    "R B04_U4ENC_A180_C04.txt",
    "R B04_U4ENC_A270_C04.txt",
    "R B05_U4ENC_A000_C02.txt",
    "R B05_U4ENC_A090_C01.txt",
    "R B05_U4ENC_A180_C03.txt",
    "R B05_U4ENC_A270_C02.txt",
    "R B07_U4SYM_S02_A000_C04.txt",
    "R B07_U4SYM_S02_A090_C04.txt",
    "R B07_U4SYM_S02_A180_C01.txt",
    "R B07_U4SYM_S02_A270_C04.txt",
    "R C270_01.txt",
    "R C270_02.txt",
    "R C270_03.txt",
)


def _measurement_text(measurement_name: str) -> bytes:
    lines = [
        "* Measurement data measured by REW V5.31.3",
        "* Source: iMM-6C microphone",
        "* Format: 256k Log Swept Sine, 1 sweep at -30.0 dBFS with no timing reference",
        "* Measurement: " + measurement_name,
        "* Smoothing: None",
        "* Mic/Meter Cal: CMM29939.txt",
        "* Freq(Hz) SPL(dB)",
    ]
    last_index = math.floor(48.0 * math.log2(8000.0 / 200.0))
    frequencies = (
        199.9,
        *(200.0 * 2.0 ** (index / 48.0) for index in range(1, last_index + 1)),
        7999.9,
    )
    lines.extend(
        f"{frequency:.17g} {70.0 + index / 1000.0:.3f}"
        for index, frequency in enumerate(frequencies)
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_frozen_shape_zip(path: Path, *, first_active_override: bytes | None = None) -> str:
    root = "正式实验_精简版_REV002"
    selected_repeats = {
        "B01_U4SYM_AS01": {"270": ("04", "05", "06")},
        "B03_U4ENC_AS01": {"270": ("02", "03", "04")},
        "B05_U4ENC_AS02": {
            "000": ("01", "03", "04"),
            "090": ("02", "03", "04"),
            "180": ("01", "02", "04"),
            "270": ("01", "03", "04"),
        },
        "B07_U4SYM_AS02": {"180": ("02", "03", "04")},
    }
    first_active_written = False
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for group in ACTIVE_GROUPS:
            block, configuration, assembly = group.split("_")
            for direction in ("000", "090", "180", "270"):
                repeats = selected_repeats.get(group, {}).get(
                    direction,
                    ("01", "02", "03"),
                )
                for repeat in repeats:
                    if block == "B01":
                        filename = f"R C{direction}_{repeat}.txt"
                    elif block == "B07":
                        filename = (
                            f"R {block}_{configuration}_S02_A{direction}_C{repeat}.txt"
                        )
                    else:
                        filename = (
                            f"R {block}_{configuration}_A{direction}_C{repeat}.txt"
                        )
                    archive.writestr(
                        f"{root}/{group}/{filename}",
                        (
                            first_active_override
                            if first_active_override is not None and not first_active_written
                            else _measurement_text(filename.removesuffix(".txt"))
                        ),
                    )
                    first_active_written = True
        for filename in EXCLUDED_FILENAMES:
            archive.writestr(
                f"{root}/EXCLUDED/{filename}",
                _measurement_text(filename.removesuffix(".txt")),
            )
        archive.writestr(f"{root}/数据选择记录.txt", "selection frozen\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_archive_inventory_locks_hash_membership_groups_and_rev002_warning(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "正式实验_精简版_REV003.zip"
    expected_hash = _write_frozen_shape_zip(archive_path)

    inventory = inspect_formal3_archive(
        archive_path,
        expected_zip_sha256=expected_hash,
    )

    assert inventory.zip_sha256 == expected_hash
    assert len(inventory.active) == 72
    assert len(inventory.excluded) == 19
    assert inventory.active_group_counts == {
        group: 12 for group in ACTIVE_GROUPS
    }
    assert inventory.internal_root == "正式实验_精简版_REV002"
    assert inventory.warning_codes == ("internal_rev002_name_under_rev003_authority",)
    assert {member.direction_id for member in inventory.active} == {
        "000",
        "090",
        "180",
        "270",
    }


def test_archive_rejects_wrong_hash_and_duplicate_member_path(tmp_path: Path) -> None:
    archive_path = tmp_path / "正式实验_精简版_REV003.zip"
    _write_frozen_shape_zip(archive_path)
    with pytest.raises(Formal3ImportError, match="SHA-256 mismatch"):
        inspect_formal3_archive(archive_path, expected_zip_sha256="0" * 64)

    with zipfile.ZipFile(archive_path, "a") as archive:
        duplicate_name = archive.infolist()[0].filename
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr(duplicate_name, b"duplicate")
    duplicate_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    with pytest.raises(Formal3ImportError, match="duplicate ZIP member paths"):
        inspect_formal3_archive(
            archive_path,
            expected_zip_sha256=duplicate_hash,
        )


def test_per_file_qc_checks_rew_contract_numeric_data_and_excluded_is_audit_only(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "正式实验_精简版_REV003.zip"
    expected_hash = _write_frozen_shape_zip(archive_path)
    inventory = inspect_formal3_archive(
        archive_path,
        expected_zip_sha256=expected_hash,
    )

    audit = inspect_formal3_measurements(inventory)

    assert len(audit.records) == 91
    assert audit.active_pass_count == 72
    assert audit.active_warning_count == 0
    assert audit.active_fail_count == 0
    first = audit.records[0]
    assert first.rew_version == "5.31.3"
    assert first.sweep_level_dbfs == -30.0
    assert first.timing_reference == "none"
    assert first.raw_smoothing == "None"
    assert first.calibration_file == "CMM29939.txt"
    assert first.raw_point_count == 257
    assert first.frequency_min_hz == 199.9
    assert first.frequency_max_hz == 7999.9
    assert all(
        not record.analysis_included
        for record in audit.records
        if record.selection_status == "EXCLUDED"
    )


@pytest.mark.parametrize(
    ("replacement", "expected_reason"),
    [
        (b"* Measurement data measured by REW V5.31.2\n1 1\n2 2\n3 3\n4 4\n5 5\n", "rew_structural_parse_failure"),
        (b"* Measurement data measured by REW V5.31.3\n199 1\n200 2\n200 3\n8000 4\n9000 5\n", "rew_structural_parse_failure"),
        (b"* Measurement data measured by REW V5.31.3\n199 1\n200 nan\n300 3\n8000 4\n9000 5\n", "rew_structural_parse_failure"),
        (b"* Measurement data measured by REW V5.31.3\n200.1 1\n300 2\n400 3\n8000 4\n9000 5\n", "rew_structural_parse_failure"),
    ],
)
def test_structural_numeric_failures_are_recorded_fail_closed(
    tmp_path: Path,
    replacement: bytes,
    expected_reason: str,
) -> None:
    archive_path = tmp_path / "正式实验_精简版_REV003.zip"
    expected_hash = _write_frozen_shape_zip(
        archive_path,
        first_active_override=replacement,
    )
    inventory = inspect_formal3_archive(
        archive_path,
        expected_zip_sha256=expected_hash,
    )

    audit = inspect_formal3_measurements(inventory)

    assert audit.active_fail_count == 1
    failed = next(record for record in audit.records if record.status == "fail")
    assert failed.structural_valid is False
    assert expected_reason in failed.reason_codes


def test_internal_missing_frequency_gap_fails_before_output_is_published(
    tmp_path: Path,
) -> None:
    baseline_lines = _measurement_text("gap-fixture").decode("utf-8").splitlines()
    numeric_indices = [
        index
        for index, line in enumerate(baseline_lines)
        if line and not line.startswith("*")
    ]
    removed = set(numeric_indices[100:110])
    gap_payload = (
        "\n".join(
            line for index, line in enumerate(baseline_lines) if index not in removed
        )
        + "\n"
    ).encode("utf-8")
    archive_path = tmp_path / "正式实验_精简版_REV003.zip"
    expected_hash = _write_frozen_shape_zip(
        archive_path,
        first_active_override=gap_payload,
    )
    output = tmp_path / "FORMAL-3_REAL_IMPORT_QC"

    with pytest.raises(Formal3ImportError, match="internal invalid grid point"):
        run_formal3_import_qc(
            archive_path,
            output,
            expected_zip_sha256=expected_hash,
            created_at="2026-08-20T16:00:00+01:00",
            source_commit="a" * 40,
        )

    assert not output.exists()


def test_end_to_end_writes_only_active_formal1_features_and_hashed_qc_outputs(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "正式实验_精简版_REV003.zip"
    expected_hash = _write_frozen_shape_zip(archive_path)
    output = tmp_path / "FORMAL-3_REAL_IMPORT_QC"

    result = run_formal3_import_qc(
        archive_path,
        output,
        expected_zip_sha256=expected_hash,
        created_at="2026-08-20T16:00:00+01:00",
        source_commit="a" * 40,
    )

    assert result.ready_for_formal_analysis is True
    assert result.active_count == 72
    assert result.excluded_count == 19
    assert len(list((output / "preprocessed" / "features").glob("*.npz"))) == 72
    assert len(list((output / "preprocessed" / "features").glob("*.json"))) == 72
    run_manifest = json.loads((output / "run_manifest.json").read_text("utf-8"))
    assert run_manifest["provenance"] == {
        "data_origin": "real_experiment",
        "dataset_role": "research_analysis",
        "run_purpose": "research_analysis",
        "scientifically_eligible": False,
    }
    assert run_manifest["final_test_read"] is False
    assert run_manifest["formal_preprocessing_contract"]["grid_type"] == "logarithmic"
    assert run_manifest["formal_preprocessing_contract"]["points_per_octave"] == 48
    feature_index = (output / "feature_index.csv").read_text("utf-8")
    excluded_manifest = (output / "excluded_manifest.csv").read_text("utf-8")
    assert "EXCLUDED" not in feature_index
    assert "analysis_included" in excluded_manifest
    first_feature_base = next((output / "preprocessed" / "features").glob("*.json"))
    first_feature = load_feature_set(first_feature_base.with_suffix(""))
    assert first_feature.meta.dataset_role.value == "research_analysis"
    assert first_feature.meta.eligible_for_scientific_analysis is False
    with pytest.raises(ResearchGateError, match="eligible=False"):
        enforce_research_gate("research_analysis", [first_feature.meta])
    assert verify_formal3_output_hashes(output)["verified"] is True
    assert (output / "group_coverage.png").is_file()
    assert (output / "repeat_dispersion.png").is_file()
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        run_formal3_import_qc(
            archive_path,
            output,
            expected_zip_sha256=expected_hash,
            created_at="2026-08-20T16:00:00+01:00",
            source_commit="a" * 40,
        )
    (output / "active_manifest.csv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(Formal3ImportError, match="artifact hash mismatch"):
        verify_formal3_output_hashes(output)

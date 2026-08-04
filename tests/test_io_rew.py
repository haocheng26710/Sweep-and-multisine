from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.io_rew import (
    REWImportError,
    REWManualReviewRequired,
    UnsupportedREWDataTypeError,
    load_rew_measurement,
)
from acoustic_encoder.research_gate import ResearchGateError, RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    Representation,
    SourceFormat,
    artifact_sha256,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET

EXTERNAL_REFERENCE_ROOT = Path(__file__).parent / "fixtures" / "rew" / "external_reference"
SYNTHETIC_ROOT = Path(__file__).parent / "fixtures" / "rew" / "synthetic"
EXTERNAL_REFERENCE_MANIFEST = json.loads(
    (EXTERNAL_REFERENCE_ROOT / "manifest.json").read_text(encoding="utf-8")
)


def real_rew_meta(path) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id="real-rew-test-001",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=90.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="E8",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=path.as_posix(),
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_INPUT,
        source_sha256=artifact_sha256(path),
        provenance_uri="experiment_logs/E8.json",
        eligible_for_scientific_analysis=True,
    )


def external_reference_meta(path) -> MeasurementMeta:
    return MeasurementMeta(
        sample_id=f"rew-reference-{artifact_sha256(path)[:12]}",
        **SCHEMA_VERSION_QUARTET,
        device_version=None,
        configuration=None,
        angle_deg=None,
        session_id=None,
        repeat_type=None,
        repeat_id=None,
        experiment_step=None,
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.REW_TXT,
        source_path=path.as_posix(),
        data_origin=DataOrigin.EXTERNAL_REFERENCE,
        dataset_role=DatasetRole.PARSER_FIXTURE,
        source_sha256=artifact_sha256(path),
        provenance_uri="tests/fixtures/rew/external_reference/manifest.json",
        eligible_for_scientific_analysis=False,
    )


def test_space_separated_three_column_rew_returns_dense_spectrum() -> None:
    path = SYNTHETIC_ROOT / "space_with_phase.txt"

    spectrum = load_rew_measurement(
        path,
        real_rew_meta(path),
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
    )

    assert spectrum.representation is Representation.DENSE_SPECTRUM
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert spectrum.magnitude_quantity == "spl"
    np.testing.assert_allclose(spectrum.frequency_hz, [100, 200, 300, 400, 500])
    np.testing.assert_allclose(spectrum.magnitude_db, [70, 71, 72, 73, 74])
    np.testing.assert_allclose(spectrum.phase_rad, np.deg2rad([-20, -10, 0, 10, 20]))
    assert np.all(spectrum.valid_mask)


@pytest.mark.parametrize(
    "file_name",
    ["tab_with_phase.txt", "comma_with_phase.txt", "semicolon_with_phase.txt"],
)
def test_rew_accepts_hash_star_comments_and_common_delimiters(file_name) -> None:
    path = SYNTHETIC_ROOT / file_name

    spectrum = load_rew_measurement(
        path,
        real_rew_meta(path),
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
    )

    assert spectrum.frequency_hz.size == 5
    np.testing.assert_allclose(spectrum.magnitude_db, [70, 71, 72, 73, 74])


def test_rew_accepts_semantic_header_without_exact_literal_match(tmp_path) -> None:
    path = tmp_path / "variable-header.txt"
    path.write_text(
        "Frequency_Hz, Acoustic_Magnitude_dB, Angle_Phase_deg\n"
        "100,70,-20\n"
        "200,71,-10\n"
        "300,72,0\n"
        "400,73,10\n"
        "500,74,20\n",
        encoding="utf-8",
    )

    spectrum = load_rew_measurement(
        path,
        real_rew_meta(path),
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
    )

    assert spectrum.frequency_hz.size == 5
    assert spectrum.phase_rad is not None


def test_two_column_rew_marks_phase_and_unavailable_qc_explicitly() -> None:
    path = SYNTHETIC_ROOT / "no_phase.txt"

    spectrum = load_rew_measurement(
        path,
        real_rew_meta(path),
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
    )

    assert spectrum.phase_rad is None
    assert spectrum.phase_status is PhaseStatus.UNAVAILABLE
    assert spectrum.quality_metrics == {
        "headroom": "unavailable",
        "noise_floor": "unavailable",
        "raw_waveform": "unavailable",
    }


def test_empty_rew_file_is_rejected_with_domain_error() -> None:
    path = SYNTHETIC_ROOT / "empty.txt"

    with pytest.raises(REWImportError, match="no numeric data"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_bad_data_line_is_rejected_with_line_number() -> None:
    path = SYNTHETIC_ROOT / "bad_line.txt"

    with pytest.raises(REWImportError, match="line 4"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_rew_rejects_data_rows_outside_two_or_three_columns(tmp_path) -> None:
    path = tmp_path / "extra-column.txt"
    path.write_text(
        "# Frequency Hz, acoustic SPL dB, phase degrees\n"
        "100 70 -20 999\n"
        "200 71 -10\n"
        "300 72 0\n"
        "400 73 10\n"
        "500 74 20\n",
        encoding="utf-8",
    )

    with pytest.raises(REWImportError, match="2 or 3 columns.*line 2"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_rew_rejects_mixed_phase_column_presence(tmp_path) -> None:
    path = tmp_path / "mixed-columns.txt"
    path.write_text(
        "# Frequency Hz, acoustic SPL dB, optional phase degrees\n"
        "100 70 -20\n"
        "200 71 -10\n"
        "300 72\n"
        "400 73 10\n"
        "500 74 20\n",
        encoding="utf-8",
    )

    with pytest.raises(REWImportError, match="inconsistent column count.*line 4"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_rew_rejects_duplicate_frequency() -> None:
    path = SYNTHETIC_ROOT / "duplicate_frequency.txt"

    with pytest.raises(REWImportError, match="strictly increasing"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_rew_rejects_decreasing_frequency() -> None:
    path = SYNTHETIC_ROOT / "decreasing_frequency.txt"

    with pytest.raises(REWImportError, match="strictly increasing"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_rew_rejects_nonfinite_frequency() -> None:
    path = SYNTHETIC_ROOT / "nonfinite_frequency.txt"

    with pytest.raises(REWImportError, match="frequencies must be finite"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_rew_requires_at_least_five_data_points() -> None:
    path = SYNTHETIC_ROOT / "too_short.txt"

    with pytest.raises(REWImportError, match="at least 5"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_impedance_export_is_rejected_from_acoustic_spl_path() -> None:
    path = SYNTHETIC_ROOT / "impedance.txt"

    with pytest.raises(UnsupportedREWDataTypeError, match="impedance.*acoustic SPL"):
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_unknown_rew_data_type_requires_manual_review() -> None:
    path = SYNTHETIC_ROOT / "unknown_type.txt"

    with pytest.raises(REWManualReviewRequired, match="cannot confirm acoustic SPL") as error:
        load_rew_measurement(
            path,
            real_rew_meta(path),
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )
    assert error.value.reasons == ("unconfirmed_rew_data_type",)


def test_unconfirmed_metadata_stops_at_manual_review(tmp_path) -> None:
    path = tmp_path / "ambiguous-name.txt"
    path.write_text(
        "# Frequency Hz, acoustic SPL dB\n"
        "100 70\n"
        "200 71\n"
        "300 72\n"
        "400 73\n"
        "500 74\n",
        encoding="utf-8",
    )
    meta = replace(
        real_rew_meta(path),
        manual_review_reasons=("unconfirmed_filename_metadata",),
    )

    with pytest.raises(REWManualReviewRequired) as error:
        load_rew_measurement(
            path,
            meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )
    assert error.value.reasons == ("unconfirmed_filename_metadata",)


def test_rew_source_hash_mismatch_is_rejected(tmp_path) -> None:
    path = tmp_path / "changed.txt"
    path.write_text(
        "# Frequency Hz, acoustic SPL dB\n"
        "100 70\n"
        "200 71\n"
        "300 72\n"
        "400 73\n"
        "500 74\n",
        encoding="utf-8",
    )
    wrong_hash_meta = replace(real_rew_meta(path), source_sha256="0" * 64)

    with pytest.raises(REWImportError, match="source hash mismatch"):
        load_rew_measurement(
            path,
            wrong_hash_meta,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        )


def test_external_reference_import_preserves_absent_experiment_metadata(tmp_path) -> None:
    path = tmp_path / "official-reference.txt"
    path.write_text(
        "* Freq Hz, SPL dB\n"
        "100 70\n"
        "200 71\n"
        "300 72\n"
        "400 73\n"
        "500 74\n",
        encoding="utf-8",
    )

    spectrum = load_rew_measurement(
        path,
        external_reference_meta(path),
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
    )

    assert spectrum.meta.data_origin is DataOrigin.EXTERNAL_REFERENCE
    assert spectrum.meta.configuration is None
    assert spectrum.meta.angle_deg is None
    assert spectrum.meta.session_id is None
    assert spectrum.meta.repeat_type is None
    assert spectrum.meta.repeat_id is None


def test_external_reference_is_rejected_from_research_analysis(tmp_path) -> None:
    path = tmp_path / "official-reference.txt"
    path.write_text(
        "* Freq Hz, SPL dB\n"
        "100 70\n"
        "200 71\n"
        "300 72\n"
        "400 73\n"
        "500 74\n",
        encoding="utf-8",
    )

    with pytest.raises(ResearchGateError, match="external_reference"):
        load_rew_measurement(
            path,
            external_reference_meta(path),
            run_purpose=RunPurpose.RESEARCH_ANALYSIS,
        )


@pytest.mark.parametrize("fixture", EXTERNAL_REFERENCE_MANIFEST["files"])
def test_official_rew_export_is_immutable_format_regression(fixture) -> None:
    path = EXTERNAL_REFERENCE_ROOT / fixture["file_name"]

    assert artifact_sha256(path) == fixture["sha256"]
    spectrum = load_rew_measurement(
        path,
        external_reference_meta(path),
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
    )

    assert spectrum.meta.sample_id == fixture["sample_id"]
    assert spectrum.frequency_hz.size == fixture["expected_point_count"]
    assert spectrum.frequency_hz[0] == fixture["first_frequency_hz"]
    assert spectrum.frequency_hz[-1] == fixture["last_frequency_hz"]
    assert spectrum.phase_rad is not None
    assert spectrum.phase_status is PhaseStatus.RELATIVE_UNRELIABLE
    assert spectrum.meta.data_origin is DataOrigin.EXTERNAL_REFERENCE
    assert spectrum.meta.eligible_for_scientific_analysis is False

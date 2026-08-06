from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json

import numpy as np
import pytest

from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureDerivation,
    FeatureQualityRecord,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCStatus,
    Representation,
    SourceFormat,
    SpectrumData,
    load_feature_set,
    load_spectrum,
    save_feature_set,
    save_spectrum,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def sweep_meta() -> MeasurementMeta:
    return MeasurementMeta(
        sample_id="sample-sweep-001",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=90.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        acquisition_block_id="B01",
        experiment_step="E8",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path="data/mock/example.txt",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="0" * 64,
        provenance_uri="data/mock/mock_manifest.json",
        eligible_for_scientific_analysis=False,
        date_time=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
    )


def external_reference_meta() -> MeasurementMeta:
    return MeasurementMeta(
        sample_id="rew-official-reference-001",
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
        source_path="tests/fixtures/rew/reference.txt",
        data_origin=DataOrigin.EXTERNAL_REFERENCE,
        dataset_role=DatasetRole.PARSER_FIXTURE,
        source_sha256="0" * 64,
        provenance_uri="tests/fixtures/rew/external_reference/manifest.json",
        eligible_for_scientific_analysis=False,
    )


def test_spectrum_and_feature_round_trip(tmp_path) -> None:
    meta = sweep_meta()
    frequency = np.array([1000.0, 1010.0, 1020.0])
    spectrum = SpectrumData(
        frequency_hz=frequency,
        magnitude_db=np.array([-20.0, -19.0, -21.0]),
        valid_mask=np.ones(3, dtype=bool),
        representation=Representation.DENSE_SPECTRUM,
        phase_status=PhaseStatus.UNAVAILABLE,
        quality_metrics={"headroom": "unavailable"},
        meta=meta,
        magnitude_quantity="transfer_ratio",
    )
    save_spectrum(spectrum, tmp_path / "spectrum")
    restored_spectrum = load_spectrum(tmp_path / "spectrum")
    np.testing.assert_allclose(restored_spectrum.magnitude_db, spectrum.magnitude_db)
    assert restored_spectrum.meta == meta

    feature = FeatureSet(
        sample_id=meta.sample_id,
        feature_schema_version=meta.feature_schema_version,
        feature_kind=FeatureKind.DENSE_DEMEANED_DB,
        feature_names=("f_1000_hz", "f_1010_hz", "f_1020_hz"),
        values=np.array([-0.5, 0.5, 0.0]),
        valid_mask=np.ones(3, dtype=bool),
        units=("dB", "dB", "dB"),
        source_measurement_mode=meta.measurement_mode,
        source_representation=spectrum.representation,
        preprocessing_id="prep-sha256-placeholder",
        meta=meta,
        source_qc_status=QCStatus.WARNING,
        source_qc_sha256="sha256:" + "a" * 64,
        source_qc_warning_reasons=("fixture_warning",),
        source_qc_eligible_for_downstream=True,
    )
    save_feature_set(feature, tmp_path / "feature")
    restored_feature = load_feature_set(tmp_path / "feature")
    np.testing.assert_allclose(restored_feature.values, feature.values)
    assert restored_feature.feature_names == feature.feature_names
    assert restored_feature.source_qc_status is QCStatus.WARNING
    assert restored_feature.source_qc_sha256 == "sha256:" + "a" * 64
    assert restored_feature.source_qc_warning_reasons == ("fixture_warning",)

    legacy_path = tmp_path / "feature.json"
    legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8"))
    for key in tuple(legacy_payload):
        if key.startswith("source_qc_"):
            legacy_payload.pop(key)
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")
    restored_legacy = load_feature_set(tmp_path / "feature")
    assert restored_legacy.source_qc_status is None
    assert restored_legacy.source_qc_sha256 is None
    assert restored_legacy.source_qc_warning_reasons == ()


def test_tone_feature_round_trip_preserves_reference_and_schema_audit(tmp_path) -> None:
    meta = sweep_meta()
    feature = FeatureSet(
        sample_id=meta.sample_id,
        feature_schema_version=meta.feature_schema_version,
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        feature_names=("tone_000000_1000_hz", "tone_000001_1100_hz"),
        values=np.array([1.0, np.nan]),
        valid_mask=np.array([True, False]),
        units=("dB", "dB"),
        source_measurement_mode=meta.measurement_mode,
        source_representation=Representation.DENSE_SPECTRUM,
        preprocessing_id="sha256:" + "a" * 64,
        meta=meta,
        tone_set_id="tone-set-round-trip",
        tone_set_sha256="b" * 64,
        tone_schema_id="sha256:" + "c" * 64,
        normalization_method="none",
        source_magnitude_quantity="spl",
        source_magnitude_reference="20uPa",
        source_phase_status=PhaseStatus.UNAVAILABLE,
        reliability_weights=None,
        reliability_weight_source=None,
    )

    save_feature_set(feature, tmp_path / "tone-feature")
    restored = load_feature_set(tmp_path / "tone-feature")

    assert restored.tone_set_sha256 == "b" * 64
    assert restored.tone_schema_id == "sha256:" + "c" * 64
    assert restored.normalization_method == "none"
    assert restored.source_magnitude_quantity == "spl"
    assert restored.source_magnitude_reference == "20uPa"
    assert restored.source_phase_status is PhaseStatus.UNAVAILABLE
    assert restored.reliability_weights is None
    assert restored.reliability_weight_source is None


def test_feature_round_trip_preserves_per_feature_quality_and_derivation(tmp_path) -> None:
    meta = sweep_meta()
    feature = FeatureSet(
        sample_id=meta.sample_id,
        feature_schema_version=meta.feature_schema_version,
        feature_kind=FeatureKind.HR_BAND_ENERGY,
        feature_names=("hr_R1_band_energy", "hr_R2_band_energy"),
        values=np.array([4.0, np.nan]),
        valid_mask=np.array([True, False]),
        units=("relative_tone_power", "relative_tone_power"),
        source_measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        source_representation=Representation.SPARSE_TONES,
        preprocessing_id="sha256:" + "1" * 64,
        meta=meta,
        calibration_id="sha256:" + "2" * 64,
        feature_quality=(
            FeatureQualityRecord(
                feature_name="hr_R1_band_energy",
                availability="available",
                valid=True,
                reason_codes=(),
                source_module="P6_B",
                details={"coverage_fraction": 1.0},
            ),
            FeatureQualityRecord(
                feature_name="hr_R2_band_energy",
                availability="unavailable",
                valid=False,
                reason_codes=("detuning_exceeded",),
                source_module="P6_B",
                details={"coverage_fraction": 0.0},
            ),
        ),
        derivation=FeatureDerivation(
            schema_version="1.0.0",
            stage_id="P6_B",
            scope_id="scope-1",
            result_id="sha256:" + "3" * 64,
            source_feature_content_sha256="sha256:" + "4" * 64,
            calibration_id="sha256:" + "2" * 64,
            calibration_json_sha256="5" * 64,
            calibration_manifest_sha256="6" * 64,
            p2b_result_sha256="sha256:" + "7" * 64,
            scientifically_eligible=False,
            deployment_allowed=False,
            absolute_energy_comparable=False,
        ),
    )

    save_feature_set(feature, tmp_path / "hr-feature")
    restored = load_feature_set(tmp_path / "hr-feature")

    assert restored.feature_quality == feature.feature_quality
    assert restored.derivation == feature.derivation


def test_feature_schema_2_2_artifact_loads_with_empty_optional_2_3_evidence(tmp_path) -> None:
    meta = sweep_meta()
    feature = FeatureSet(
        sample_id=meta.sample_id,
        feature_schema_version="2.2.0",
        feature_kind=FeatureKind.DENSE_RAW_SPL,
        feature_names=("f_1000_hz", "f_1010_hz"),
        values=np.asarray([80.0, 81.0]),
        valid_mask=np.asarray([True, True]),
        units=("dB", "dB"),
        source_measurement_mode=MeasurementMode.REW_SWEEP,
        source_representation=Representation.DENSE_SPECTRUM,
        preprocessing_id="sha256:" + "8" * 64,
        meta=meta,
    )
    _, metadata_path = save_feature_set(feature, tmp_path / "legacy-feature")
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload.pop("feature_quality")
    payload.pop("derivation")
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    restored = load_feature_set(tmp_path / "legacy-feature")

    assert restored.feature_schema_version == "2.2.0"
    assert restored.feature_quality == ()
    assert restored.derivation is None


def test_multisine_meta_requires_manifest_linkage() -> None:
    with pytest.raises(ValueError, match="multisine metadata fields"):
        MeasurementMeta(
            sample_id="bad-ms",
            **SCHEMA_VERSION_QUARTET,
            device_version="V2",
            configuration="U4ENC",
            angle_deg=0.0,
            session_id="S01",
            repeat_type="CONT",
            repeat_id="R01",
            experiment_step="E8",
            measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
            source_format=SourceFormat.MULTISINE_WAV,
            source_path="recording.wav",
            data_origin=DataOrigin.REAL_EXPERIMENT,
            dataset_role=DatasetRole.RESEARCH_INPUT,
            source_sha256="0" * 64,
            provenance_uri="experiment_log/E8.json",
            eligible_for_scientific_analysis=True,
        )


def test_spectrum_rejects_unsorted_frequency() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        SpectrumData(
            frequency_hz=np.array([1000.0, 990.0]),
            magnitude_db=np.array([0.0, 0.0]),
            valid_mask=np.ones(2, dtype=bool),
            representation=Representation.DENSE_SPECTRUM,
            phase_status=PhaseStatus.UNAVAILABLE,
            quality_metrics={},
            meta=sweep_meta(),
        )


def test_simulated_measurement_cannot_be_scientifically_eligible() -> None:
    with pytest.raises(ValueError, match="real_experiment"):
        MeasurementMeta(
            sample_id="bad-simulated-eligibility",
            **SCHEMA_VERSION_QUARTET,
            device_version="V2",
            configuration="U4ENC",
            angle_deg=0.0,
            session_id="S01",
            repeat_type="CONT",
            repeat_id="R01",
            experiment_step="MOCK_DEV_A",
            measurement_mode=MeasurementMode.REW_SWEEP,
            source_format=SourceFormat.MOCK_DENSE,
            source_path="data/mock/example.txt",
            data_origin=DataOrigin.SIMULATED,
            dataset_role=DatasetRole.SOFTWARE_VALIDATION,
            source_sha256="0" * 64,
            provenance_uri="mock_manifest.json",
            eligible_for_scientific_analysis=True,
        )


def test_provenance_fields_use_current_measurement_schema() -> None:
    payload = sweep_meta().to_dict()
    assert payload["measurement_schema_version"] == "2.4.0"
    assert payload["data_origin"] == "simulated"
    assert payload["dataset_role"] == "software_validation"
    assert payload["source_sha256"] == "0" * 64
    assert payload["eligible_for_scientific_analysis"] is False


def test_measurement_mode_rejects_incompatible_source_format() -> None:
    with pytest.raises(ValueError, match="measurement_mode"):
        replace(sweep_meta(), source_format=SourceFormat.MOCK_AUDIO)


def test_external_reference_has_no_experiment_identity_metadata() -> None:
    meta = external_reference_meta()

    assert meta.configuration is None
    assert meta.angle_deg is None
    assert meta.session_id is None
    assert meta.repeat_type is None
    assert meta.repeat_id is None


def test_external_reference_rejects_fabricated_experiment_identity() -> None:
    with pytest.raises(ValueError, match="external_reference.*experiment identity"):
        replace(external_reference_meta(), configuration="U4ENC")

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from acoustic_encoder.schemas import (
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
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
        date_time=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
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
    )
    save_feature_set(feature, tmp_path / "feature")
    restored_feature = load_feature_set(tmp_path / "feature")
    np.testing.assert_allclose(restored_feature.values, feature.values)
    assert restored_feature.feature_names == feature.feature_names


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


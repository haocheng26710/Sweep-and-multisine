from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from acoustic_encoder.feature_outputs import write_dense_feature_outputs
from acoustic_encoder.features import build_dense_feature_sets
from acoustic_encoder.quality_control import MeasurementQCResult, UnavailablePolicy
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    Representation,
    SourceFormat,
    SpectrumData,
    artifact_sha256,
    load_feature_set,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _case(magnitude_db: np.ndarray | None = None):
    meta = MeasurementMeta(
        sample_id="p3-output-fixture",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_C2",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path="synthetic-output-spectrum.txt",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="4" * 64,
        provenance_uri="software-validation-fixture",
        eligible_for_scientific_analysis=False,
    )
    spectrum = SpectrumData(
        frequency_hz=np.arange(1000.0, 1040.0 + 10.0, 10.0),
        magnitude_db=(
            np.array([70.0, 71.0, 72.0, 73.0, 74.0])
            if magnitude_db is None
            else magnitude_db
        ),
        valid_mask=np.ones(5, dtype=bool),
        representation=Representation.DENSE_SPECTRUM,
        phase_status=PhaseStatus.UNAVAILABLE,
        quality_metrics={},
        magnitude_quantity="spl",
        meta=meta,
    )
    qc = MeasurementQCResult(
        qc_schema_version="1.0.0",
        sample_id=meta.sample_id,
        measurement_mode=meta.measurement_mode,
        data_origin=meta.data_origin,
        dataset_role=meta.dataset_role,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        checks=(),
        unavailable_required_policy=UnavailablePolicy.WARNING,
        manual_review_reasons=(),
        human_valid=True,
        human_exclusion_reason=None,
        scientifically_eligible=False,
    )
    config = {
        "schema_version": "1.0.0",
        "analysis_band_hz": [1000, 1040],
        "common_grid_step_hz": 10,
        "interpolation": "linear",
        "maximum_interpolation_gap_hz": 20,
        "minimum_valid_grid_fraction": 0.8,
        "normalization_band_hz": [1000, 1040],
        "minimum_normalization_points": 2,
        "minimum_zscore_std_db": 1.0e-9,
        "smoothing": {"method": "none"},
    }
    return build_dense_feature_sets(spectrum, qc, config)


def test_dense_feature_output_bundle_round_trips_and_hashes_every_artifact(
    tmp_path,
) -> None:
    result = _case()

    artifacts = write_dense_feature_outputs(result, tmp_path / "processed")

    for kind in FeatureKind.DENSE_RAW_SPL, FeatureKind.DENSE_DEMEANED_DB, FeatureKind.DENSE_ZSCORE:
        base = tmp_path / "processed" / "features" / kind.value / result.sample_id
        restored = load_feature_set(base)
        np.testing.assert_array_equal(
            restored.values,
            result.feature_sets[kind].values,
        )
    required = {
        "feature_index_csv",
        "feature_schema_json",
        "preprocessing_manifest_json",
        "preprocessing_manifest_sha256",
        "preprocessing_failures_csv",
    }
    assert required.issubset(artifacts)
    with artifacts["feature_index_csv"].open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert {row["processing_status"] for row in rows} == {"success"}

    manifest = json.loads(
        artifacts["preprocessing_manifest_json"].read_text(encoding="utf-8")
    )
    assert manifest["preprocessing_id"] == result.preprocessing_id
    assert manifest["input"]["sample_id"] == result.sample_id
    assert manifest["source_magnitude"]["quantity"] == "spl"
    assert manifest["provenance"]["data_origin"] == "simulated"
    assert manifest["provenance"]["run_purpose"] == "software_validation"
    assert manifest["provenance"]["eligible_for_scientific_analysis"] is False
    assert manifest["source_qc"]["sha256"] == result.feature_sets[
        FeatureKind.DENSE_RAW_SPL
    ].source_qc_sha256
    for item in manifest["artifacts"]:
        assert artifact_sha256(tmp_path / "processed" / item["path"]) == item["sha256"]
    assert artifact_sha256(artifacts["preprocessing_manifest_json"]) == (
        artifacts["preprocessing_manifest_sha256"].read_text(encoding="ascii").strip()
    )


def test_dense_feature_output_refuses_existing_processed_directory(tmp_path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        write_dense_feature_outputs(_case(), processed)


def test_partial_feature_failure_is_indexed_without_fabricated_artifact(
    tmp_path,
) -> None:
    result = _case(np.full(5, 72.0))

    artifacts = write_dense_feature_outputs(result, tmp_path / "processed")

    with artifacts["feature_index_csv"].open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = {row["feature_kind"]: row for row in csv.DictReader(handle)}
    failed = rows[FeatureKind.DENSE_ZSCORE.value]
    assert failed["processing_status"] == "failed"
    assert failed["failure_reason"] == "zscore_standard_deviation_too_small"
    assert failed["npz_path"] == ""
    assert failed["json_path"] == ""
    with artifacts["preprocessing_failures_csv"].open(
        encoding="utf-8", newline=""
    ) as handle:
        failures = list(csv.DictReader(handle))
    assert failures == [
        {
            "sample_id": result.sample_id,
            "feature_kind": FeatureKind.DENSE_ZSCORE.value,
            "reason": "zscore_standard_deviation_too_small",
            "message": result.failures[0].message,
        }
    ]
    assert not (
        tmp_path
        / "processed"
        / "features"
        / FeatureKind.DENSE_ZSCORE.value
    ).exists()

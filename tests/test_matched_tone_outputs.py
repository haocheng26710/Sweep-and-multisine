from __future__ import annotations

import csv
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.matched_tone_outputs import write_matched_tone_outputs
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    Representation,
    SourceFormat,
    artifact_sha256,
    load_feature_set,
)
from acoustic_encoder.tone_features import (
    MatchedToneView,
    ToneExtractionRecord,
    ToneFeatureProcessingResult,
)
from acoustic_encoder.tone_sets import ToneDefinition, ToneSetDefinition
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _meta(mode: MeasurementMode) -> MeasurementMeta:
    common = dict(
        sample_id="sweep" if mode is MeasurementMode.REW_SWEEP else "multisine",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_C4",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="1" * 64,
        provenance_uri="mock_manifest.json",
        eligible_for_scientific_analysis=False,
    )
    if mode is MeasurementMode.REW_SWEEP:
        return MeasurementMeta(
            measurement_mode=mode,
            source_format=SourceFormat.MOCK_DENSE,
            source_path="sweep.txt",
            **common,
        )
    return MeasurementMeta(
        measurement_mode=mode,
        source_format=SourceFormat.MOCK_AUDIO,
        source_path="recording.wav",
        stimulus_id="stimulus",
        stimulus_hash="2" * 64,
        tone_set_id="tone-set",
        sidecar_path="recording.json",
        audio_channel=0,
        **common,
    )


def _tone_set() -> ToneSetDefinition:
    return ToneSetDefinition(
        tone_set_id="tone-set",
        sample_rate_hz=48000,
        period_samples=4800,
        tones=(
            ToneDefinition(0, 1000.0, "1000", 100, 1.0, 0.0),
            ToneDefinition(1, 1100.0, "1100", 110, 1.0, 0.0),
        ),
        tones_sha256="3" * 64,
        tone_set_sha256="4" * 64,
        manifest_sha256="5" * 64,
        manifest_path=Path("stimulus_manifest.json"),
        tones_path=Path("tones.csv"),
        verified_artifacts=True,
    )


def _feature_result(kind: FeatureKind) -> ToneFeatureProcessingResult:
    tone_set = _tone_set()
    mode = (
        MeasurementMode.REW_SWEEP
        if kind is FeatureKind.TONE_PROJECTION_FROM_SWEEP
        else MeasurementMode.SCHROEDER_MULTISINE
    )
    representation = (
        Representation.DENSE_SPECTRUM
        if mode is MeasurementMode.REW_SWEEP
        else Representation.SPARSE_TONES
    )
    meta = _meta(mode)
    feature = FeatureSet(
        sample_id=meta.sample_id,
        feature_schema_version=meta.feature_schema_version,
        feature_kind=kind,
        feature_names=tone_set.feature_names,
        values=np.array([1.0, 2.0]),
        valid_mask=np.ones(2, dtype=bool),
        units=("dB", "dB"),
        source_measurement_mode=mode,
        source_representation=representation,
        preprocessing_id="sha256:" + ("6" if mode is MeasurementMode.REW_SWEEP else "7") * 64,
        meta=meta,
        tone_set_id=tone_set.tone_set_id,
        tone_set_sha256=tone_set.tone_set_sha256,
        tone_schema_id="sha256:" + "8" * 64,
        normalization_method="none",
        source_magnitude_quantity="spl",
        source_magnitude_reference="20uPa",
        source_phase_status=(
            PhaseStatus.UNAVAILABLE
            if mode is MeasurementMode.REW_SWEEP
            else PhaseStatus.RELATIVE_UNRELIABLE
        ),
    )
    records = tuple(
        ToneExtractionRecord(
            tone_index=tone.tone_index,
            frequency_hz=tone.frequency_hz,
            feature_name=name,
            method=(
                "single_point_linear"
                if mode is MeasurementMode.REW_SWEEP
                else "direct_sparse_tone_alignment"
            ),
            valid=True,
            value_db=float(feature.values[tone.tone_index]),
            reason=None,
            source_indices=(tone.tone_index,),
            source_frequency_hz=(tone.frequency_hz,),
            source_weights=(1.0,),
        )
        for tone, name in zip(tone_set.tones, tone_set.feature_names, strict=True)
    )
    return ToneFeatureProcessingResult(
        sample_id=meta.sample_id,
        feature_kind=kind,
        processing_status="completed",
        feature_set=feature,
        preprocessing_id=feature.preprocessing_id,
        tone_schema_id=feature.tone_schema_id or "",
        extraction_records=records,
        failures=(),
        dense_preprocessing_id=("sha256:" + "9" * 64 if mode is MeasurementMode.REW_SWEEP else None),
        normalization=None,
        run_purpose="software_validation",
    )


def _view() -> MatchedToneView:
    return MatchedToneView(
        processing_status="completed",
        failure_reason=None,
        common_valid_mask=np.ones(2, dtype=bool),
        sweep_invalid_count=0,
        multisine_missing_count=0,
        multisine_other_invalid_count=0,
        common_valid_count=2,
        minimum_common_valid_tones=2,
        source_reference_status="compatible_reference",
        comparison_status="absolute_comparable",
        cross_mode_absolute_comparable=True,
    )


def test_matched_tone_outputs_round_trip_and_hashes(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    written = write_matched_tone_outputs(
        _feature_result(FeatureKind.TONE_PROJECTION_FROM_SWEEP),
        _feature_result(FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE),
        _view(),
        _tone_set(),
        {
            "schema_version": "1.0.0",
            "provisional": True,
            "tone_ordering": "manifest_tone_index",
            "sweep_extraction": {"method": "single_point_linear"},
            "normalization": {
                "method": "none",
                "minimum_valid_tones": 2,
                "minimum_std_db": 1.0e-9,
            },
            "matching": {"minimum_common_valid_tones": 2},
        },
        processed,
    )

    required = {
        "tone_feature_index_csv",
        "matched_tone_schema_json",
        "matched_tone_audit_csv",
        "preprocessing_failures_csv",
        "preprocessing_manifest_json",
        "preprocessing_manifest_sha256",
    }
    assert required <= set(written)
    sweep = load_feature_set(
        processed / "features" / "tone_projection_from_sweep" / "sweep"
    )
    multisine = load_feature_set(
        processed / "features" / "tone_measurement_from_multisine" / "multisine"
    )
    assert sweep.feature_names == multisine.feature_names
    manifest = json.loads(
        written["preprocessing_manifest_json"].read_text(encoding="utf-8")
    )
    assert manifest["provenance"]["data_origin"] == "simulated"
    assert manifest["provenance"]["run_purpose"] == "software_validation"
    assert manifest["comparison"]["cross_mode_absolute_comparable"] is True
    for record in manifest["artifacts"]:
        path = processed / record["path"]
        assert artifact_sha256(path) == record["sha256"]


def test_matched_tone_outputs_refuse_existing_directory(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()

    with pytest.raises(FileExistsError, match="already exists"):
        write_matched_tone_outputs(
            _feature_result(FeatureKind.TONE_PROJECTION_FROM_SWEEP),
            _feature_result(FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE),
            _view(),
            _tone_set(),
            {},
            processed,
        )


def test_failed_sample_is_retained_in_index_audit_and_failure_output(
    tmp_path: Path,
) -> None:
    failed_sweep = replace(
        _feature_result(FeatureKind.TONE_PROJECTION_FROM_SWEEP),
        processing_status="failed",
        feature_set=None,
        failures=("minimum_valid_tones_not_met",),
    )
    view = replace(
        _view(),
        processing_status="failed",
        failure_reason="common valid tone count 0 is below minimum 2",
        common_valid_mask=np.zeros(2, dtype=bool),
        sweep_invalid_count=2,
        common_valid_count=0,
    )
    processed = tmp_path / "processed"

    written = write_matched_tone_outputs(
        failed_sweep,
        _feature_result(FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE),
        view,
        _tone_set(),
        {
            "normalization": {"method": "none"},
            "matching": {"minimum_common_valid_tones": 2},
        },
        processed,
    )

    with written["tone_feature_index_csv"].open(
        encoding="utf-8", newline=""
    ) as handle:
        index = list(csv.DictReader(handle))
    with written["matched_tone_audit_csv"].open(
        encoding="utf-8", newline=""
    ) as handle:
        audit = list(csv.DictReader(handle))
    failures = written["preprocessing_failures_csv"].read_text(encoding="utf-8")
    assert index[0]["feature_kind"] == "tone_projection_from_sweep"
    assert index[0]["processing_status"] == "failed"
    assert len(audit) == 2
    assert {row["common_valid"] for row in audit} == {"false"}
    assert "minimum_valid_tones_not_met" in failures
    assert "common valid tone count" in failures

from __future__ import annotations

import json
from pathlib import Path

from acoustic_encoder.config import load_config
from acoustic_encoder.pipeline_dispatch import dispatch_measurement
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    Representation,
    SourceFormat,
    artifact_sha256,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_unified_dispatcher_routes_rew_sweep_to_dense_spectrum(tmp_path) -> None:
    source = tmp_path / "sweep.txt"
    source.write_text(
        "# Frequency Hz, acoustic SPL dB\n"
        "100 70\n200 71\n300 72\n400 73\n500 74\n",
        encoding="utf-8",
    )
    meta = MeasurementMeta(
        sample_id="dispatch-rew-001",
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id="R01",
        experiment_step="DEV_B5",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path=source.as_posix(),
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=artifact_sha256(source),
        provenance_uri="software-validation-fixture",
        eligible_for_scientific_analysis=False,
    )
    metadata_path = tmp_path / "sweep.json"
    metadata_path.write_text(
        json.dumps(meta.to_dict(), indent=2),
        encoding="utf-8",
    )
    resolved = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )

    result = dispatch_measurement(source, metadata_path, resolved)

    assert result.spectrum.representation is Representation.DENSE_SPECTRUM
    assert result.spectrum.meta.measurement_mode is MeasurementMode.REW_SWEEP
    assert result.multisine_analysis is None

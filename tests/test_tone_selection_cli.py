from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from acoustic_encoder.dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from acoustic_encoder.schemas import (
    DataOrigin, DatasetRole, FeatureKind, FeatureSet, MeasurementMeta, MeasurementMode,
    PhaseStatus, Representation, SourceFormat, artifact_sha256, save_feature_set,
)
from acoustic_encoder.sweep_multisine_bridge import (
    CandidateTone, CandidateToneUniverse, ToneSelectionFeatureReference,
    ToneSelectionMember, ToneSelectionScope,
    ToneSelectionInputError,
)
from acoustic_encoder.tone_selection_cli import (
    ToneSelectionInputArtifact,
    ToneSelectionInputManifest,
    load_explicit_tone_selection_inputs,
)


def _feature() -> FeatureSet:
    meta = MeasurementMeta(
        "sample-1", "test", "2.16.0", "2.4.0", "2.3.0", "fixture", "U4ENC", 0.0,
        "S1", "CONT", "R1", "fixture", MeasurementMode.REW_SWEEP, SourceFormat.MOCK_DENSE,
        "fixture/sample-1", DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION, "1" * 64,
        "synthetic://tone-selection", False, assembly_id="A1", acquisition_block_id="B1",
    )
    return FeatureSet(
        "sample-1", "2.3.0", FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        ("tone_000000_1000_hz",), np.asarray((1.0,)), np.asarray((True,)), ("dB",),
        MeasurementMode.REW_SWEEP, Representation.DENSE_SPECTRUM, "sha256:" + "2" * 64, meta,
        tone_set_id="source", tone_set_sha256="a" * 64, tone_schema_id="sha256:" + "3" * 64,
        normalization_method="subtract_mean_db", source_magnitude_quantity="spl_db",
        source_phase_status=PhaseStatus.UNAVAILABLE,
    )


def test_explicit_input_manifest_loads_only_declared_feature_artifacts(tmp_path: Path) -> None:
    feature = _feature()
    base = tmp_path / "declared" / "sample-1"
    npz_path, json_path = save_feature_set(feature, base)
    # This unrelated file must not be discovered or adopted.
    (tmp_path / "rogue.json").write_text("{}", encoding="utf-8")
    universe = CandidateToneUniverse("1.0.0", "universe", "source", "a" * 64, 48_000, 4_800, (1_000.0, 8_000.0), (CandidateTone("tone-a", 0, 1_000.0, 100),))
    reference = ToneSelectionFeatureReference("artifact-1", "sample-1", "discriminability", feature_set_content_sha256(feature), feature_contract_sha256(feature))
    scope = ToneSelectionScope(
        "1.0.0", "scope", "development_selection", "software_validation", "simulated", "software_validation",
        "universe", universe.sha256, "source", "a" * 64,
        (ToneSelectionMember("sample-1", "state-1", "development", "U4ENC", "D0", 0.0, "S1", "CONT", "R1", None, "A1", "B1"),),
        (reference,), ("development",), 1, 0.0, 1, False, None, (), (), (), None,
        "p2b", "sha256:" + "4" * 64, None, 1, "explicit fixture",
    )
    manifest = ToneSelectionInputManifest(
        "1.0.0", "scope", "universe", universe.sha256,
        (ToneSelectionInputArtifact(
            "artifact-1", "sample-1", "discriminability", base.as_posix(),
            artifact_sha256(npz_path), artifact_sha256(json_path),
            feature_set_content_sha256(feature), feature_contract_sha256(feature),
        ),),
    )
    manifest_path = tmp_path / "inputs.json"
    manifest_path.write_text(json.dumps(manifest.to_dict()), encoding="utf-8")

    loaded = load_explicit_tone_selection_inputs(manifest_path, scope, universe)

    assert set(loaded) == {"artifact-1"}
    assert loaded["artifact-1"].sample_id == "sample-1"
    npz_path.write_bytes(b"tampered")
    with pytest.raises(ToneSelectionInputError, match="file hash mismatch"):
        load_explicit_tone_selection_inputs(manifest_path, scope, universe)


def test_select_tones_script_exposes_only_explicit_file_arguments() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/select_tones.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "--scope" in completed.stdout
    assert "--inputs" in completed.stdout
    assert "--candidate-universe" in completed.stdout
    assert "--scan-directory" not in completed.stdout

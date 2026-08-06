from __future__ import annotations

from dataclasses import replace
import json

import pytest

from acoustic_encoder.dataset_quality_control import (
    DatasetQCReference,
    feature_contract_sha256,
    feature_set_content_sha256,
)
from acoustic_encoder.hr_analysis import FinalTestSeal
from acoustic_encoder.hr_readout import (
    HRCalibrationReference,
    HRReadoutScope,
    HRReadoutScopeMember,
)
from acoustic_encoder.hr_readout_cli import (
    HRReadoutInputEntry,
    HRReadoutInputManifest,
    load_explicit_hr_readout_inputs,
)
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    artifact_sha256,
    save_feature_set,
)
from test_hr_readout import _digest, _tone_feature


def _inputs(tmp_path):
    feature = _tone_feature((990.0, 1000.0, 1010.0), (0.0, 3.0, 0.0))
    base = tmp_path / "features" / feature.sample_id
    npz_path, json_path = save_feature_set(feature, base)
    member = HRReadoutScopeMember(
        feature.sample_id, base.as_posix(), artifact_sha256(npz_path),
        artifact_sha256(json_path), feature_set_content_sha256(feature),
        feature_contract_sha256(feature), feature.meta.configuration, "A000", 0.0,
        feature.meta.session_id, feature.meta.repeat_type,
        DatasetRole.SOFTWARE_VALIDATION, "explicit fixture", feature.tone_set_id,
        feature.tone_set_sha256, feature.meta.stimulus_id, feature.meta.stimulus_hash,
        feature.source_magnitude_quantity, feature.source_magnitude_reference,
        "development",
    )
    reference = HRCalibrationReference(
        _digest("7"), "cal/hr_calibration.json", "8" * 64,
        "cal/hr_calibration_manifest.json", "9" * 64,
        "cal/hr_calibration_manifest.sha256", "a" * 64,
    )
    scope = HRReadoutScope(
        "1.0.0", "P6B-CLI", (member,), reference, "G1", ("R1",),
        "nearest_tone", "nearest_tone_power",
        DatasetQCReference("P2B-P6B", _digest("b")),
        FinalTestSeal(True, ("final-1",), _digest("c")),
        RunPurpose.SOFTWARE_VALIDATION, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION, 20260806,
    )
    entry = HRReadoutInputEntry(
        feature.sample_id, base.as_posix(), artifact_sha256(npz_path),
        artifact_sha256(json_path), feature_set_content_sha256(feature),
        feature_contract_sha256(feature),
    )
    manifest = HRReadoutInputManifest(
        "1.0.0", scope.hr_readout_scope_id, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION, (entry,),
    )
    path = tmp_path / "hr_readout_inputs.json"
    path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return feature, scope, path


def test_explicit_hr_readout_manifest_loads_only_declared_feature_and_verifies_hash(tmp_path) -> None:
    feature, scope, path = _inputs(tmp_path)
    unlisted = replace(feature, sample_id="unlisted", meta=replace(feature.meta, sample_id="unlisted"))
    save_feature_set(unlisted, tmp_path / "features" / "unlisted")

    loaded, audit, manifest = load_explicit_hr_readout_inputs(path, scope)

    assert tuple(item.sample_id for item in loaded) == (feature.sample_id,)
    assert feature_set_content_sha256(loaded[0]) == feature_set_content_sha256(feature)
    assert manifest.measurements[0].sample_id == feature.sample_id
    assert {row["artifact_role"] for row in audit} == {
        "feature_npz", "feature_json", "hr_readout_input_manifest",
    }
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["measurements"][0]["feature_content_sha256"] = _digest("0")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="scope/input manifest mismatch"):
        load_explicit_hr_readout_inputs(path, scope)

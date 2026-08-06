from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest
import yaml

from acoustic_encoder.config import load_config
from acoustic_encoder.dataset_quality_control import (
    CohortRole,
    ConditionCompletenessResult,
    DatasetQCReference,
    DatasetQCScope,
    DatasetScopeMember,
    ExpectedCondition,
    MeasurementQCRollup,
    dataset_qc_sha256,
)
from acoustic_encoder.dataset_quality_outputs import write_dataset_quality_outputs
from acoustic_encoder.hr_cli import (
    HRCalibrationInputEntry,
    HRCalibrationInputManifest,
    execute_hr_calibration,
    load_explicit_hr_calibration_inputs,
)
from acoustic_encoder.hr_outputs import load_hr_calibration_bundle
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import DataOrigin, DatasetRole, QCCheckStatus, QCStatus, artifact_sha256, save_feature_set

from test_hr_analysis import _config, _feature, _p2b, _scope


PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def _write_explicit_inputs(tmp_path):
    feature = _feature()
    reference, p2b = _p2b("P2B-HR-CLI", (feature,))
    base = tmp_path / "persisted" / feature.sample_id
    npz_path, json_path = save_feature_set(feature, base)
    original_scope = _scope(feature, reference)
    member = replace(
        original_scope.members[0],
        feature_base_path=base.as_posix(),
        feature_npz_sha256=artifact_sha256(npz_path),
        feature_json_sha256=artifact_sha256(json_path),
    )
    scope = replace(original_scope, members=(member,))
    scope_path = tmp_path / "hr_scope.json"
    scope_path.write_text(json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    entry = HRCalibrationInputEntry(
        feature.sample_id,
        base.as_posix(),
        artifact_sha256(npz_path),
        artifact_sha256(json_path),
        member.feature_content_sha256,
    )
    manifest = HRCalibrationInputManifest(
        "1.0.0", scope.hr_calibration_scope_id, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION, (entry,),
    )
    input_path = tmp_path / "hr_inputs.json"
    input_path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return feature, p2b, scope, scope_path, input_path


def test_explicit_hr_input_manifest_loads_only_listed_feature_and_verifies_hash(tmp_path) -> None:
    feature, _, scope, _, input_path = _write_explicit_inputs(tmp_path)
    unlisted = replace(feature, sample_id="unlisted", meta=replace(feature.meta, sample_id="unlisted"))
    save_feature_set(unlisted, tmp_path / "persisted" / "unlisted")

    loaded, audit, manifest = load_explicit_hr_calibration_inputs(input_path, scope)

    assert [item.sample_id for item in loaded] == [feature.sample_id]
    assert manifest.measurements[0].sample_id == feature.sample_id
    assert {item["artifact_role"] for item in audit} == {"feature_npz", "feature_json", "hr_scope", "hr_input_manifest"}

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload["measurements"][0]["feature_json_sha256"] = "sha256:" + "0" * 64
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_explicit_hr_calibration_inputs(input_path, scope)


def test_hr_calibration_cli_e2e_writes_simulated_ineligible_bundle(tmp_path) -> None:
    feature, p2b, initial_scope, scope_path, input_path = _write_explicit_inputs(tmp_path)
    dataset_scope = DatasetQCScope(
        "1.0.0",
        p2b.analysis_scope_id,
        RunPurpose.SOFTWARE_VALIDATION,
        (DatasetScopeMember(feature.sample_id, CohortRole.DEVELOPMENT, "condition-1", "explicit HR fixture"),),
        (ExpectedCondition(
            "condition-1", CohortRole.DEVELOPMENT, feature.source_measurement_mode,
            feature.meta.configuration, "A000", feature.meta.angle_deg,
            feature.meta.session_id, feature.meta.repeat_type,
            feature.meta.reposition_round_id, feature.meta.assembly_id,
            feature.meta.acquisition_block_id, 1,
        ),),
    )
    resolved = load_config(PROJECT_ROOT / "config" / "default.yaml")
    p2_config = resolved["dataset_quality_control"]
    p2_config_hash = "sha256:" + hashlib.sha256(json.dumps(p2_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    p2b = replace(
        p2b,
        scope_sha256=dataset_scope.sha256,
        config_sha256=p2_config_hash,
        condition_results=(ConditionCompletenessResult(
            "condition-1", CohortRole.DEVELOPMENT, 1, 1, 1, 0, 0,
            0, 0, 0, QCCheckStatus.VALID, (), (feature.sample_id,), (),
        ),),
        measurement_rollups=(MeasurementQCRollup(
            feature.sample_id, CohortRole.DEVELOPMENT, feature.source_qc_sha256,
            QCStatus.VALID, QCStatus.VALID, QCStatus.VALID,
            (), (), (), (), True, None, True,
        ),),
    )
    reference = DatasetQCReference(p2b.analysis_scope_id, dataset_qc_sha256(p2b))
    scope = replace(initial_scope, p2b_reference=reference)
    scope_path.write_text(json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    p2_input = tmp_path / "p2-input.json"
    p2_input.write_text("{}\n", encoding="utf-8")
    p2_dir = tmp_path / "dataset_qc"
    write_dataset_quality_outputs(
        p2b, dataset_scope, p2_config, p2_dir,
        input_artifacts=({"sample_id": feature.sample_id, "artifact_role": "fixture", "path": p2_input.as_posix(), "sha256": artifact_sha256(p2_input)},),
        git_commit="fixture", random_state=20260806,
    )
    config_path = tmp_path / "hr-config.yaml"
    config_path.write_text(yaml.safe_dump({
        "pipeline_version": "2.0.0-dev.16",
        "schema_versions": {"config": "2.15.0", "measurement": "2.4.0", "feature": "2.2.0"},
        "measurement_mode": "rew_sweep",
        "run_purpose": "software_validation",
        "random_state": 20260806,
        "hr_calibration": _config(scope.resonators),
    }, sort_keys=False), encoding="utf-8")

    output = execute_hr_calibration(
        config_path=config_path,
        scope_path=scope_path,
        input_manifest_path=input_path,
        dataset_qc_directory=p2_dir,
        output_root=tmp_path / "outputs",
        run_id="DEV-C10-CLI",
        project_root=PROJECT_ROOT,
    )

    assert output.parts[-4:] == ("simulated", "software_validation", "DEV-C10-CLI", "hr_calibration")
    result = load_hr_calibration_bundle(output)
    assert result.calibration_status == "software_validation_only"
    assert result.scientifically_eligible is False
    with pytest.raises(FileExistsError):
        execute_hr_calibration(
            config_path=config_path, scope_path=scope_path, input_manifest_path=input_path,
            dataset_qc_directory=p2_dir, output_root=tmp_path / "outputs",
            run_id="DEV-C10-CLI", project_root=PROJECT_ROOT,
        )

from __future__ import annotations

import json

import pytest

from acoustic_encoder.offline_readout import run_offline_readout
from acoustic_encoder.offline_readout_outputs import (
    load_offline_readout_bundle,
    load_readout_package_bundle,
    write_offline_readout_outputs,
    write_offline_readout_failure_outputs,
    write_readout_package,
)
from test_offline_readout import (
    _input_reference, _matched_config, _package_and_model, _qc, _spectrum, _tone_set,
)


def test_package_and_readout_bundles_round_trip_all_hashes(tmp_path) -> None:
    package, model = _package_and_model()
    package_dir = tmp_path / "package"
    package_manifest = write_readout_package(
        package_dir, package, model,
        package_input_manifest={
            "schema_version": "1.0.0",
            "explicit_training_sample_ids": list(model.training_sample_ids),
            "sealed_final_test_sample_ids": list(model.sealed_final_test_sample_ids),
            "final_test_files_read": [],
            "authority_hashes": dict(model.authority_hashes),
        },
    )
    restored_package, restored_model, restored_manifest = load_readout_package_bundle(package_dir)

    assert restored_package == package
    assert restored_model == model
    assert restored_manifest == package_manifest
    assert package_manifest["artifact_count"] == 5
    assert (package_dir / "package_manifest.sha256").is_file()

    result = run_offline_readout(
        _spectrum(), _qc(), _tone_set(), _matched_config(), package, model,
        _input_reference(), calibration_model=None,
    )
    readout_dir = tmp_path / "readout"
    readout_manifest = write_offline_readout_outputs(readout_dir, result)
    restored_result, restored_readout_manifest = load_offline_readout_bundle(readout_dir)

    assert restored_result.to_dict() == result.to_dict()
    assert restored_result.semantic_sha256 == result.semantic_sha256
    assert restored_readout_manifest == readout_manifest
    assert (readout_dir / "qc_audit.csv").is_file()
    assert (readout_dir / "feature_audit.csv").is_file()
    assert (readout_dir / "readout_manifest.sha256").is_file()


def test_outputs_refuse_overwrite_and_loader_detects_tamper(tmp_path) -> None:
    package, model = _package_and_model()
    package_dir = tmp_path / "package"
    write_readout_package(package_dir, package, model, package_input_manifest={"schema_version": "1.0.0"})
    with pytest.raises(FileExistsError, match="already exists"):
        write_readout_package(package_dir, package, model, package_input_manifest={"schema_version": "1.0.0"})

    model_path = package_dir / "frozen_direction_model.json"
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    payload["centroids"][0][0] += 0.25
    model_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_readout_package_bundle(package_dir)


def test_unavailable_readout_still_writes_complete_audit_without_success_marker(tmp_path) -> None:
    package, model = _package_and_model()
    result = run_offline_readout(
        _spectrum(mask=(True, False, True)), _qc(), _tone_set(), _matched_config(),
        package, model, _input_reference(), calibration_model=None,
    )
    output = tmp_path / "failed-readout"
    write_offline_readout_outputs(output, result)

    required = {
        "input_audit.json", "qc_audit.csv", "qc_audit.json", "feature_audit.csv",
        "feature_audit.json", "calibration_audit.json", "prediction.json",
        "readout_result.json", "readout_manifest.json", "readout_manifest.sha256",
    }
    assert required <= {path.name for path in output.iterdir()}
    assert not (output / "SUCCESS").exists()
    assert json.loads((output / "prediction.json").read_text(encoding="utf-8"))["available"] is False


def test_pre_core_hash_failure_still_writes_blocked_audit_bundle(tmp_path) -> None:
    output = tmp_path / "blocked"
    manifest = write_offline_readout_failure_outputs(
        output, reason="stimulus manifest hash mismatch",
        input_evidence={"input_manifest_sha256": "sha256:" + "1" * 64},
    )

    assert manifest["processing_status"] == "blocked"
    assert manifest["prediction_available"] is False
    assert (output / "input_audit.json").is_file()
    assert (output / "readout_manifest.sha256").is_file()
    assert not (output / "SUCCESS").exists()

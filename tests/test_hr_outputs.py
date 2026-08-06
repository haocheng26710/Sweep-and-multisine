from __future__ import annotations

import json

import pytest

from acoustic_encoder.hr_analysis import HRCalibrationResult, analyze_sweep_hr_calibration
from acoustic_encoder.hr_outputs import (
    load_hr_calibration_authority,
    load_hr_calibration_bundle,
    write_hr_calibration_outputs,
)
from acoustic_encoder.schemas import artifact_sha256

from test_hr_analysis import _config, _feature, _p2b, _scope


def _result_bundle():
    feature = _feature()
    reference, p2b = _p2b("P2B-HR-OUTPUT", (feature,))
    scope = _scope(feature, reference)
    result = analyze_sweep_hr_calibration(
        (feature,), scope, p2b, _config(), created_at_utc="2026-08-06T12:00:00+00:00"
    )
    return result, scope


def test_hr_result_json_round_trip_and_calibration_id_tamper_detection() -> None:
    result, _ = _result_bundle()

    restored = HRCalibrationResult.from_dict(result.to_dict())

    assert restored == result
    payload = result.to_dict()
    payload["detected_peaks"][0]["peak_frequency_hz"] = 1600.0
    with pytest.raises(ValueError, match="calibration ID mismatch"):
        HRCalibrationResult.from_dict(payload)


def test_hr_output_bundle_hashes_csv_json_and_refuses_overwrite(tmp_path) -> None:
    result, scope = _result_bundle()
    input_path = tmp_path / "input.feature.json"
    input_path.write_text('{"fixture": true}\n', encoding="utf-8")
    output = tmp_path / "hr_calibration"
    inputs = ({
        "sample_id": result.source_sample_ids[0],
        "artifact_role": "feature_json",
        "path": input_path.as_posix(),
        "sha256": artifact_sha256(input_path),
    },)

    paths = write_hr_calibration_outputs(
        result,
        scope,
        _config(),
        output,
        input_artifacts=inputs,
        git_commit="abc123",
        random_state=20260806,
        created_at_utc="2026-08-06T12:00:00+00:00",
    )

    expected = {
        "peak_candidates.csv", "detected_peaks.csv", "peak_bandwidths.csv",
        "peak_drift.csv", "peak_overlap.csv", "integrated_energy.csv",
        "hr_energy_fractions.csv", "calibration_scope_audit.csv",
        "calibration_input_audit.csv", "hr_calibration.json",
        "hr_calibration.sha256", "hr_calibration_manifest.json",
        "hr_calibration_manifest.sha256", "peak_detection_diagnostic.png",
    }
    assert expected <= set(paths)
    loaded = load_hr_calibration_bundle(output)
    assert loaded == result
    authority = load_hr_calibration_authority(output)
    assert authority.result == result
    assert authority.scope == scope
    assert authority.calibration_json_sha256 == artifact_sha256(output / "hr_calibration.json")
    assert authority.calibration_manifest_sha256 == artifact_sha256(
        output / "hr_calibration_manifest.json"
    )
    manifest = json.loads((output / "hr_calibration_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provenance"]["scientifically_eligible"] is False
    assert manifest["calibration_status"] == "software_validation_only"
    assert all((output / item["path"]).is_file() for item in manifest["artifacts"])
    with pytest.raises(FileExistsError):
        write_hr_calibration_outputs(
            result, scope, _config(), output, input_artifacts=inputs,
            git_commit="abc123", random_state=20260806,
        )


def test_hr_bundle_loader_rejects_tampered_artifact(tmp_path) -> None:
    result, scope = _result_bundle()
    input_path = tmp_path / "input.feature.json"
    input_path.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "hr_calibration"
    write_hr_calibration_outputs(
        result, scope, _config(), output,
        input_artifacts=({"sample_id": result.source_sample_ids[0], "artifact_role": "feature_json",
                          "path": input_path.as_posix(), "sha256": artifact_sha256(input_path)},),
        git_commit="abc123", random_state=20260806,
    )
    (output / "detected_peaks.csv").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        load_hr_calibration_bundle(output)

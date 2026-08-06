from __future__ import annotations

import json
from pathlib import Path

import pytest

from acoustic_encoder.hr_readout_outputs import load_hr_readout_bundle
from acoustic_encoder.hr_readout_cli import execute_hr_readout
from acoustic_encoder.hr_readout_validation import run_hr_readout_validation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_hr_readout_validation_recovers_known_fractions_and_provenance(tmp_path) -> None:
    output = run_hr_readout_validation(
        output_root=tmp_path / "outputs",
        run_id="DEV-C11-TEST",
        project_root=PROJECT_ROOT,
    )

    analysis = load_hr_readout_bundle(output)
    assert output.parts[-4:] == (
        "simulated", "software_validation", "DEV-C11-TEST", "hr_readout"
    )
    assert analysis.result.scientifically_eligible is False
    assert analysis.result.deployment_allowed is False
    assert analysis.result.phase_policy == "magnitude_only"
    assert analysis.result.uncertainty_status == "unavailable"
    assert [round(item.q_i, 12) for item in analysis.result.sample_readouts[0].energy_fractions] == [
        round(4 / 7, 12), round(2 / 7, 12), round(1 / 7, 12),
    ]
    summary = json.loads((output.parent / "validation_summary.json").read_text(encoding="utf-8"))
    assert summary["maximum_energy_fraction_error"] < 1e-12
    assert summary["signed_peak_detuning_hz"] == {"R1": 2.0, "R2": -5.0, "R3": 8.0}
    with pytest.raises(FileExistsError):
        run_hr_readout_validation(
            output_root=tmp_path / "outputs",
            run_id="DEV-C11-TEST",
            project_root=PROJECT_ROOT,
        )


def test_hr_readout_cli_failure_writes_failure_only_manifest(tmp_path) -> None:
    root = tmp_path / "outputs"
    output = run_hr_readout_validation(
        output_root=root, run_id="DEV-C11-SOURCE", project_root=PROJECT_ROOT
    )
    run_base = output.parent
    inputs = run_base / "hr_readout_inputs.json"
    payload = json.loads(inputs.read_text(encoding="utf-8"))
    payload["measurements"][0]["feature_json_sha256"] = "0" * 64
    bad_inputs = run_base / "bad_hr_readout_inputs.json"
    bad_inputs.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="scope/input manifest mismatch"):
        execute_hr_readout(
            config_path=PROJECT_ROOT / "config" / "validation_dev_c11_hr_readout.yaml",
            scope_path=run_base / "hr_readout_scope.json",
            input_manifest_path=bad_inputs,
            dataset_qc_directory=run_base / "dataset_qc",
            output_root=root,
            run_id="DEV-C11-FAILED",
            project_root=PROJECT_ROOT,
        )

    failed = root / "simulated" / "software_validation" / "DEV-C11-FAILED" / "hr_readout"
    manifest = json.loads(
        (failed / "hr_readout_failure_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["success"] is False
    assert manifest["scientifically_eligible"] is False
    assert not (failed / "hr_readout_manifest.json").exists()

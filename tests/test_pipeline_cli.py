from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import yaml

from acoustic_encoder.config import load_config
from acoustic_encoder.mock_data import generate_dual_mode_mock
from acoustic_encoder.schemas import load_spectrum

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_sweep_config_command_remains_a_successful_stage_gate() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_pipeline.py"),
            "--config",
            str(PROJECT_ROOT / "config" / "experiment_v2_u4.yaml"),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"measurement_mode": "rew_sweep"' in completed.stdout
    assert "P1/P2-A/P8 plus dense P3-A/P3-B" in completed.stderr
    assert "P2-B requires an explicit dataset scope" in completed.stderr
    assert "canonical P4-A additionally requires the matching P2-B result/hash" in completed.stderr
    assert "P4-B/P5/P6/P9 remain not implemented" in completed.stderr


def test_analyze_multisine_and_run_pipeline_use_identical_execution_path(
    tmp_path,
) -> None:
    stimulus = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )["stimulus"]
    mock_root = tmp_path / "mock"
    mock_manifest_path = generate_dual_mode_mock(
        mock_root,
        deepcopy(stimulus),
        configurations=["U4ENC"],
        angles_deg=[0],
        random_state=123,
        recording_delay_samples=1379,
    )
    mock_manifest = json.loads(mock_manifest_path.read_text(encoding="utf-8"))
    sample = next(
        item
        for item in mock_manifest["samples"]
        if item["measurement_mode"] == "schroeder_multisine"
    )
    config = yaml.safe_load(
        (PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml").read_text(
            encoding="utf-8"
        )
    )
    config["paths"] = {"stimuli": (mock_root / "stimuli").as_posix()}
    config_path = tmp_path / "multisine.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    common = [
        "--config",
        str(config_path),
        "--input",
        sample["source_path"],
        "--metadata",
        sample["sidecar_path"],
    ]
    unified = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_pipeline.py"),
            *common,
            "--output-root",
            str(tmp_path / "unified"),
            "--run-id",
            "run-pipeline",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    dedicated = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "analyze_multisine.py"),
            *common,
            "--output-root",
            str(tmp_path / "dedicated"),
            "--run-id",
            "analyze-multisine",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert unified.returncode == 0, unified.stderr
    assert dedicated.returncode == 0, dedicated.stderr
    first = load_spectrum(
        tmp_path
        / "unified"
        / "simulated"
        / "software_validation"
        / "run-pipeline"
        / "spectrum_data"
    )
    second = load_spectrum(
        tmp_path
        / "dedicated"
        / "simulated"
        / "software_validation"
        / "analyze-multisine"
        / "spectrum_data"
    )
    np.testing.assert_array_equal(first.frequency_hz, second.frequency_hz)
    np.testing.assert_allclose(first.magnitude_db, second.magnitude_db, atol=0, rtol=0)
    assert first.phase_status is second.phase_status
    assert first.quality_metrics == second.quality_metrics

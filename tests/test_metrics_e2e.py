from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from acoustic_encoder.metrics_validation import (
    run_simulated_direction_metrics_validation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict:
    return {
        "schema_version": "1.0.0",
        "provisional": True,
        "minimum_common_valid_features": 8,
        "minimum_common_valid_fraction": 1.0,
        "minimum_direction_count": 4,
        "center_direction_matrix": False,
        "repeatability_distance_metric": "rms",
        "morphology_gain": {
            "distance_metric": "rms",
            "minimum_denominator": 1.0e-12,
        },
    }


def test_controlled_direction_feature_sets_run_p4a_end_to_end(tmp_path) -> None:
    result = run_simulated_direction_metrics_validation(
        output_root=tmp_path,
        run_id="DEV-C5-P4A-E2E",
        metrics_config=_config(),
        random_state=20260805,
        feature_count=8,
    )

    assert result.metrics.processing_status == "completed"
    assert result.metrics.summary.direction_count == 4
    assert result.metrics.summary.sample_count == 32
    assert result.metrics.common_valid_feature_count == 8
    assert result.metrics.effective_rank.available
    assert result.metrics.morphology_gain.available
    assert result.output_directory == (
        tmp_path / "simulated" / "software_validation" / "DEV-C5-P4A-E2E"
    )
    manifest = json.loads(
        (result.output_directory / "metrics" / "metrics_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["provenance"]["scientific_use"] == (
        "prohibited_simulated_software_validation"
    )
    assert manifest["identity"]["configuration"] == "U4ENC"
    assert manifest["effective_rank"]["matrix_shape"] == [4, 8]

    with pytest.raises(FileExistsError, match="already exists"):
        run_simulated_direction_metrics_validation(
            output_root=tmp_path,
            run_id="DEV-C5-P4A-E2E",
            metrics_config=_config(),
            random_state=20260805,
            feature_count=8,
        )


def test_direction_metrics_validation_cli_uses_same_immutable_runner(tmp_path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "run_direction_metrics_validation.py"),
            "--output-root",
            str(tmp_path),
            "--run-id",
            "DEV-C5-P4A-CLI",
            "--feature-count",
            "71",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "processing_status=completed" in completed.stdout
    assert "directions=4" in completed.stdout
    assert "samples=32" in completed.stdout
    assert "common_valid_features=71" in completed.stdout
    assert "scientific_use=prohibited_simulated_software_validation" in completed.stdout
    assert (
        tmp_path
        / "simulated"
        / "software_validation"
        / "DEV-C5-P4A-CLI"
        / "metrics"
        / "metrics_manifest.json"
    ).is_file()

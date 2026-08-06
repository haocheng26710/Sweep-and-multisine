from __future__ import annotations

from pathlib import Path

import pytest

from acoustic_encoder.cross_mode_bridge_validation import (
    run_simulated_cross_mode_bridge_validation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_actual_p7_s3_p8_p3c_p9c_validation_recovers_known_affine(
    tmp_path: Path,
) -> None:
    result = run_simulated_cross_mode_bridge_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c14_p9c.yaml",
        output_root=tmp_path / "o",
        run_id="v",
    )

    assert result["actual_chain"] == "P7->S3->P8->P3-C->P9-C"
    assert result["actual_chain_count"] == 6
    assert result["processing_status"] == "completed_with_warnings"
    assert result["maximum_chain_relation_error_db"] < 0.02
    assert result["maximum_recovered_slope_error"] < 0.005
    assert result["maximum_recovered_intercept_error_db"] < 0.08
    assert result["mean_calibrated_rms_db"] < 0.001
    assert result["mean_calibrated_rms_db"] < result["mean_raw_rms_db"]
    assert result["artifact_hashes_verified"] is True
    assert result["model_registry_hash_verified"] is True
    assert result["scientifically_eligible"] is False
    assert result["deployment_eligible"] is False
    assert result["canonical_analysis"] is False
    assert result["final_test_read"] is False


def test_validation_refuses_existing_output(tmp_path: Path) -> None:
    existing = tmp_path / "o" / "simulated" / "software_validation" / "v"
    existing.mkdir(parents=True)

    with pytest.raises(FileExistsError, match="already exists"):
        run_simulated_cross_mode_bridge_validation(
            project_root=PROJECT_ROOT,
            config_path=PROJECT_ROOT / "config" / "validation_dev_c14_p9c.yaml",
            output_root=tmp_path / "o",
            run_id="v",
        )

from __future__ import annotations

from pathlib import Path

from acoustic_encoder.offline_readout_validation import run_offline_readout_validation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_actual_p7_s3_p8_to_frozen_readout_chain(tmp_path) -> None:
    summary = run_offline_readout_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c15_p9d.yaml",
        output_root=tmp_path,
        run_id="r",
    )

    assert summary["true_direction_deg"] == 90.0
    assert summary["predicted_direction_deg"] == 90.0
    assert summary["second_direction_deg"] is not None
    assert summary["margin"] is not None and summary["margin"] >= 0.0
    assert summary["training_sample_count"] == 6
    assert summary["tone_count"] == 5
    assert summary["qc_status"] in {"valid", "warning"}
    assert summary["calibration_applied"] is False
    assert summary["deterministic_repeat"] is True
    assert summary["final_test_read"] is False
    assert summary["scientifically_eligible"] is False
    assert summary["deployment_eligible"] is False

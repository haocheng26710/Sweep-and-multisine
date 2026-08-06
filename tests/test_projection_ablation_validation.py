from __future__ import annotations

from pathlib import Path

from acoustic_encoder.projection_ablation_outputs import load_projection_ablation_bundle
from acoustic_encoder.projection_ablation_validation import run_simulated_projection_ablation_validation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_fold_specific_projection_ablation_e2e(tmp_path) -> None:
    summary = run_simulated_projection_ablation_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c13_p9b.yaml",
        output_root=tmp_path,
        run_id="dev-c13-test",
    )
    assert summary["selected_subset_sizes"] == {
        "outer-S1": 3, "outer-S2": 3, "outer-S3": 3,
    }
    assert summary["artifact_hashes_verified"] is True
    assert summary["final_test_read"] is False
    assert summary["scientifically_eligible"] is False
    bundle = load_projection_ablation_bundle(summary["output_directory"])
    assert bundle["manifest"]["canonical_analysis"] is False

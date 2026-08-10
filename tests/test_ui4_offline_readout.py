from __future__ import annotations

import json
from pathlib import Path

from acoustic_encoder.ui.offline_workflow import OfflineReadoutService
from acoustic_encoder.ui.runtime import RuntimeContext


def test_blocked_offline_result_never_exposes_a_prediction(tmp_path: Path) -> None:
    runtime = RuntimeContext.for_source(tmp_path, workspace_root=tmp_path / "workspace")
    output = tmp_path / "blocked readout"
    output.mkdir()
    (output / "readout_manifest.json").write_text(
        json.dumps(
            {
                "processing_status": "blocked",
                "prediction_available": False,
                "failure_reasons": ["QC is exclude_candidate"],
                "scientifically_eligible": False,
                "deployment_eligible": False,
            }
        ),
        encoding="utf-8",
    )
    (output / "prediction.json").write_text(
        json.dumps({"available": False, "predicted_direction_deg": None}),
        encoding="utf-8",
    )

    summary = OfflineReadoutService(runtime).summarize(output)

    assert summary.processing_status == "blocked"
    assert summary.prediction_available is False
    assert summary.predicted_direction_deg is None
    assert "QC is exclude_candidate" in summary.reasons
    assert summary.score_explanation.startswith("nearest-centroid score")

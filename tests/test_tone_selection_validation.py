from __future__ import annotations

from pathlib import Path
import json
import pytest

from acoustic_encoder.tone_selection_outputs import load_tone_selection_bundle
from acoustic_encoder.tone_selection_cli import run_tone_selection_command
from acoustic_encoder.sweep_multisine_bridge import ToneSelectionInputError
from acoustic_encoder.tone_selection_validation import run_simulated_tone_selection_validation


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_deterministic_p9a_e2e_selects_only_development_sweep_features(tmp_path: Path) -> None:
    summary = run_simulated_tone_selection_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c12_tone_selection.yaml",
        output_root=tmp_path,
        run_id="P9A-E2E",
    )
    output = tmp_path / "simulated" / "software_validation" / "P9A-E2E" / "tone_selection"
    bundle = load_tone_selection_bundle(output)

    assert summary["processing_status"] == "completed"
    assert summary["selected_count"] == 5
    assert summary["final_test_read"] is False
    assert summary["scientifically_eligible"] is False
    assert bundle["selected_tone_set"].lifecycle == "software_validation_only"
    assert bundle["selected_tone_set"].deployment_allowed is False

    second_summary = run_simulated_tone_selection_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c12_tone_selection.yaml",
        output_root=tmp_path,
        run_id="P9A-E2E-REPEAT",
    )
    second_output = tmp_path / "simulated" / "software_validation" / "P9A-E2E-REPEAT" / "tone_selection"
    second_bundle = load_tone_selection_bundle(second_output)
    assert second_bundle["analysis"].selection.selected_candidate_ids == bundle["analysis"].selection.selected_candidate_ids
    assert [item.final_score for item in second_bundle["analysis"].candidate_scores] == [
        item.final_score for item in bundle["analysis"].candidate_scores
    ]


def test_e2e_rejects_tampered_exact_p2b_reference(tmp_path: Path) -> None:
    run_simulated_tone_selection_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c12_tone_selection.yaml",
        output_root=tmp_path,
        run_id="P9A-P2B-GATE",
    )
    inputs = tmp_path / "simulated" / "software_validation" / "P9A-P2B-GATE" / "inputs"
    scope_payload = json.loads((inputs / "tone_selection_scope.json").read_text(encoding="utf-8"))
    scope_payload["dataset_qc_result_sha256"] = "sha256:" + "0" * 64
    bad_scope = inputs / "tampered_scope.json"
    bad_scope.write_text(json.dumps(scope_payload), encoding="utf-8")

    with pytest.raises(ToneSelectionInputError, match="P2-B reference validation failed"):
        run_tone_selection_command([
            "--config", str(PROJECT_ROOT / "config" / "validation_dev_c12_tone_selection.yaml"),
            "--scope", str(bad_scope),
            "--inputs", str(inputs / "tone_selection_inputs.json"),
            "--candidate-universe", str(inputs / "candidate_universe.json"),
            "--dataset-qc-dir", str(inputs / "dataset_qc"),
            "--output-root", str(tmp_path),
            "--run-id", "P9A-P2B-GATE-TAMPERED",
            "--project-root", str(PROJECT_ROOT),
        ])

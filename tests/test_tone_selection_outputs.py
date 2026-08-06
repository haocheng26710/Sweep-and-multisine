from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import pytest

from acoustic_encoder.sweep_multisine_bridge import (
    CandidateScoreResult,
    CandidateTone,
    CandidateToneUniverse,
    GreedySelectionResult,
    SelectedToneRecord,
    SelectedToneSetArtifact,
    SelectionTraceRecord,
    ToneComponentResult,
    ToneSelectionAnalysisResult,
    ToneSelectionFeatureReference,
    ToneSelectionInputError,
    ToneSelectionMember,
    ToneSelectionScope,
    validate_selected_tone_set_for_p7,
)
from acoustic_encoder.tone_selection_outputs import (
    load_tone_selection_bundle,
    write_tone_selection_outputs,
)


def _bundle_fixture() -> tuple[ToneSelectionAnalysisResult, ToneSelectionScope, CandidateToneUniverse, dict]:
    universe = CandidateToneUniverse(
        "1.0.0", "universe", "source", "a" * 64, 48_000, 4_800,
        (1_000.0, 8_000.0), (CandidateTone("tone-a", 0, 1_000.0, 100),),
    )
    member = ToneSelectionMember("sample-1", "state-1", "development", "U4ENC", "D0", 0.0, "S1", "CONT", "R1", None, "A1", "B1")
    reference = ToneSelectionFeatureReference("artifact-1", "sample-1", "discriminability", "sha256:" + "b" * 64, "sha256:" + "c" * 64)
    scope = ToneSelectionScope(
        "1.0.0", "scope", "development_selection", "software_validation", "simulated", "software_validation",
        "universe", universe.sha256, "source", "a" * 64, (member,), (reference,), ("development",),
        1, 0.0, 1, False, None, (), (), (), None, "p2b", "sha256:" + "d" * 64, None, 7, "fixture",
    )
    component = ToneComponentResult("between_direction_variance", True, 2.0, "dB^2", "higher", 4, 0, "available")
    score = CandidateScoreResult("tone-a", 0, 1_000.0, 100, True, (), {component.component_id: component}, 1.0, "weighted_rank_sum", (), {component.component_id: 1.0}, {component.component_id: 1.0})
    trace = SelectionTraceRecord(1, "tone-a", 1_000.0, 100, 1.0, "selected", "eligible_highest_remaining_score")
    greedy = GreedySelectionResult("completed", "software_validation_only", 1, ("tone-a",), (trace,), ())
    selected = SelectedToneSetArtifact(
        "1.0.0", "sha256:" + "e" * 64, "software_validation_only", True, "scope", scope.sha256,
        "sha256:" + "f" * 64, "universe", universe.sha256, "source", "a" * 64, 48_000, 4_800,
        (SelectedToneRecord(0, 1, "tone-a", 0, 1_000.0, 100, 1.0),), 1, 0.0, 1,
        ("sample-1",), scope.training_sample_sha256, None, (), None, "sha256:" + "d" * 64, None,
        "simulated", "software_validation", False, False, False,
    )
    result = ToneSelectionAnalysisResult(
        "1.0.0", "completed", selected.selection_id, "scope", scope.sha256, selected.config_sha256,
        universe.sha256, "sha256:" + "d" * 64, None, "simulated", "software_validation", False, False, False,
        (score,), greedy, selected, (), (),
    )
    return result, scope, universe, {"schema_version": "1.0.0", "provisional": True}


def test_output_bundle_writes_required_audits_and_round_trips_hashes(tmp_path: Path) -> None:
    result, scope, universe, config = _bundle_fixture()
    output = tmp_path / "tone_selection"

    paths = write_tone_selection_outputs(
        result,
        scope,
        universe,
        config,
        output,
        input_file_hashes={"scope.json": "1" * 64},
        git_commit="0" * 40,
        created_at="2026-08-06T12:00:00+00:00",
    )
    loaded = load_tone_selection_bundle(output)

    required = {
        "candidate_universe_audit.csv", "sample_scope_audit.csv", "component_raw_values.csv",
        "component_normalization.csv", "candidate_scores.csv", "candidate_eligibility.csv",
        "selection_trace.csv", "selected_tones.csv", "selection_summary.csv",
        "selected_tone_set.json", "selected_tone_set.sha256", "tone_selection_result.json",
        "tone_selection_manifest.json", "tone_selection_manifest.sha256",
    }
    assert required <= {path.name for path in paths}
    assert loaded["selected_tone_set"] == result.selected_tone_set
    assert loaded["analysis"] == result
    assert loaded["result"]["selection_id"] == result.selection_id


def test_selected_tone_set_passes_p7_grid_constraints_without_generating_wav() -> None:
    result, _scope, _universe, _config = _bundle_fixture()
    assert result.selected_tone_set is not None

    audit = validate_selected_tone_set_for_p7(
        result.selected_tone_set,
        {"sample_rate_hz": 48_000, "period_samples": 4_800},
    )

    assert audit == {"compatible": True, "tone_count": 1, "waveform_generated": False}


def test_output_bundle_refuses_overwrite_and_detects_artifact_tampering(tmp_path: Path) -> None:
    result, scope, universe, config = _bundle_fixture()
    output = tmp_path / "tone_selection"
    arguments = (result, scope, universe, config, output)
    keywords = {"input_file_hashes": {}, "git_commit": "0" * 40, "created_at": "2026-08-06T12:00:00+00:00"}
    write_tone_selection_outputs(*arguments, **keywords)

    with pytest.raises(FileExistsError, match="already exists"):
        write_tone_selection_outputs(*arguments, **keywords)
    (output / "candidate_scores.csv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ToneSelectionInputError, match="artifact hash mismatch"):
        load_tone_selection_bundle(output)


def test_output_bundle_rejects_csv_that_disagrees_with_typed_json_even_when_hashes_are_resealed(tmp_path: Path) -> None:
    result, scope, universe, config = _bundle_fixture()
    output = tmp_path / "tone-selection"
    write_tone_selection_outputs(
        result,
        scope,
        universe,
        config,
        output,
        input_file_hashes={"scope.json": "a" * 64},
        git_commit="deadbeef",
        created_at="2026-08-06T00:00:00+00:00",
    )

    selected_csv = output / "selected_tones.csv"
    rows = list(csv.DictReader(selected_csv.open(newline="", encoding="utf-8")))
    rows[0]["candidate_id"] = "tampered-candidate"
    with selected_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    manifest_path = output / "tone_selection_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_hashes"]["selected_tones.csv"] = hashlib.sha256(selected_csv.read_bytes()).hexdigest()
    semantic = dict(manifest)
    semantic.pop("manifest_content_sha256")
    manifest["manifest_content_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(semantic, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "tone_selection_manifest.sha256").write_text(
        hashlib.sha256(manifest_path.read_bytes()).hexdigest() + "  tone_selection_manifest.json\n",
        encoding="utf-8",
    )

    with pytest.raises(ToneSelectionInputError, match="selected_tones.csv disagrees"):
        load_tone_selection_bundle(output)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"lifecycle": "approved_deployment_tone_set", "approval_record": {"reviewer": "fixture"}}, "simulated selection cannot be approved"),
        ({"final_test_evaluated": True}, "cannot claim science, deployment, or final-test"),
        ({"lifecycle": "superseded", "superseded_by": None}, "requires superseded_by"),
    ],
)
def test_selected_tone_set_lifecycle_fails_closed(changes, message) -> None:
    from dataclasses import replace

    result, _scope, _universe, _config = _bundle_fixture()
    assert result.selected_tone_set is not None
    with pytest.raises(ToneSelectionInputError, match=message):
        replace(result.selected_tone_set, **changes)

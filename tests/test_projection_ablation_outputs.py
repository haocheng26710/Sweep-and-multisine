from __future__ import annotations

import json
import hashlib

import pytest

from acoustic_encoder.projection_ablation import (
    AblationScopeMember,
    FoldSelectionReference,
    OuterFoldDefinition,
    P9ProjectionAblationResult,
    P9ProjectionAblationScope,
)
from acoustic_encoder.projection_ablation_outputs import (
    load_projection_ablation_bundle,
    write_projection_ablation_outputs,
)


def _scope() -> P9ProjectionAblationScope:
    seal = "sha256:" + hashlib.sha256(
        json.dumps({"sealed_final_test_sample_ids": ["sealed"]}, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return P9ProjectionAblationScope(
        "1.0.0", "scope", "simulated", "software_validation", "software_validation",
        (
            AblationScopeMember("a", "pa", "training", 0.0, "S1", "fixture"),
            AblationScopeMember("b", "pb", "training", 90.0, "S2", "fixture"),
        ),
        (OuterFoldDefinition("outer-1", "S2", ("a",), ("b",), ("pb",), ()),),
        (FoldSelectionReference("outer-1", "sha256:" + "1" * 64, "sha256:" + "2" * 64, "sha256:" + "3" * 64, "sha256:" + "4" * 64, "sha256:" + "5" * 64, None, "sha256:" + "9" * 64, "6" * 64),),
        (1,), "sha256:" + "7" * 64, ("sealed",), seal, 7,
    )


def _result(scope: P9ProjectionAblationScope) -> P9ProjectionAblationResult:
    return P9ProjectionAblationResult(
        "1.0.0", "completed", scope.analysis_scope_id, scope.sha256,
        "simulated", "software_validation", False, False, False, False,
        (), (), (), (), (), (), (), (), (),
    )


def test_outputs_are_complete_hash_verified_and_never_overwritten(tmp_path) -> None:
    scope = _scope()
    output = tmp_path / "projection_ablation"
    paths = write_projection_ablation_outputs(
        _result(scope), scope, {"enabled": True}, output,
        input_file_hashes={"input.json": "a" * 64}, git_commit="abc123",
        git_dirty=True, created_at="2026-08-06T12:00:00+00:00",
    )

    names = {item.name for item in paths}
    assert {
        "ablation_scope.json", "fold_selection_references.csv",
        "tone_subset_definitions.csv", "derived_feature_index.csv",
        "p4_metric_preservation.csv", "inner_classification_metrics.csv",
        "minimum_tone_decisions.csv", "outer_fold_predictions.csv",
        "outer_fold_metrics.csv", "projection_fidelity_summary.json",
        "ablation_manifest.json", "ablation_manifest.sha256",
    } <= names
    bundle = load_projection_ablation_bundle(output)
    assert bundle["manifest"]["scientifically_eligible"] is False
    assert bundle["manifest"]["git_dirty"] is True
    repeated = tmp_path / "projection_ablation_repeated"
    write_projection_ablation_outputs(
        _result(scope), scope, {"enabled": True}, repeated,
        input_file_hashes={"input.json": "a" * 64}, git_commit="abc123",
        git_dirty=True, created_at="2026-08-06T12:00:00+00:00",
    )
    assert (output / "ablation_manifest.json").read_bytes() == (repeated / "ablation_manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        write_projection_ablation_outputs(
            _result(scope), scope, {}, output,
            input_file_hashes={}, git_commit="abc123", git_dirty=True,
        )

    summary = json.loads((output / "projection_fidelity_summary.json").read_text(encoding="utf-8"))
    assert summary["final_test_read"] is False

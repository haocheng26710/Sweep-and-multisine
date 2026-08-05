from __future__ import annotations

import json
from pathlib import Path

import pytest

from acoustic_encoder.comparison_metrics import (
    ComparisonAnalysisScope,
    ScopedFeatureReference,
    ScopedMeasurementContext,
    analyze_comparison_feature_sets,
)
from acoustic_encoder.comparison_metrics_outputs import (
    load_comparison_metrics_bundle,
    write_comparison_metrics_outputs,
)
from acoustic_encoder.config import load_config
from acoustic_encoder.dataset_quality_control import CohortRole
from acoustic_encoder.metrics import AnalysisScope, QCInclusionPolicy, ScopeRole, SelectionPolicy
from acoustic_encoder.mock_data import generate_directional_feature_set_mock
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import QCStatus, artifact_sha256


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fixture():
    features = generate_directional_feature_set_mock(
        direction_order_deg=(0.0, 90.0),
        feature_count=8,
        included_repeat_types=("REPOS",),
        repeat_noise_scale=0.0,
    )
    base = AnalysisScope(
        schema_version="1.1.0",
        analysis_scope_id="DEV-C7:output-test",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=tuple(item.sample_id for item in features),
        partition=None,
        direction_order_deg=(0.0, 90.0),
        selection_policy=SelectionPolicy("explicit-test"),
        qc_inclusion_policy=QCInclusionPolicy(
            "valid-warning", (QCStatus.VALID, QCStatus.WARNING)
        ),
    )
    artifacts = {f"feature-{index:03d}": item for index, item in enumerate(features)}
    scope = ComparisonAnalysisScope(
        schema_version="1.0.0",
        analysis_scope=base,
        measurements=tuple(
            ScopedMeasurementContext(
                item.sample_id,
                CohortRole.DEVELOPMENT,
                f"A{int(item.meta.angle_deg):03d}",
                "fixture-state",
                "explicit output test",
            )
            for item in features
        ),
        feature_references=tuple(
            ScopedFeatureReference.from_feature_set(
                artifact_id, feature, primary_for_dataset_qc=True
            )
            for artifact_id, feature in artifacts.items()
        ),
        cross_mode_pairs=(),
    )
    config = load_config(PROJECT_ROOT / "config" / "default.yaml")
    result = analyze_comparison_feature_sets(
        artifacts,
        scope,
        config["direction_metrics"],
        config["comparison_metrics"],
    )
    return artifacts, scope, config, result


def test_comparison_output_bundle_is_complete_hashed_and_round_trips(tmp_path) -> None:
    artifacts, scope, config, result = _fixture()
    output = tmp_path / "comparison"

    written = write_comparison_metrics_outputs(
        result,
        scope,
        output,
        comparison_config=config["comparison_metrics"],
        input_artifacts=tuple(
            {
                "artifact_id": artifact_id,
                "artifact_role": "feature_set_content",
                "path": f"memory://{artifact_id}",
                "sha256": result.input_feature_content_hashes[artifact_id],
            }
            for artifact_id in artifacts
        ),
        git_commit="0" * 40,
        random_state=20260804,
        created_at_utc="2026-08-05T00:00:00+00:00",
    )

    expected = {
        "band_metrics.csv", "band_direction_pairs.csv",
        "configuration_comparison.csv", "morphology_gain_comparison.csv",
        "matched_pair_audit.csv", "cross_mode_pair_metrics.csv",
        "cross_mode_summary.csv", "per_tone_bias.csv", "tone_reliability.csv",
        "weighted_metrics.csv", "matched_effective_rank.csv",
        "comparison_status.csv", "comparison_metrics.json", "metrics_manifest.json",
        "metrics_manifest.sha256",
    }
    assert {path.name for path in written.values()} == expected
    loaded = load_comparison_metrics_bundle(output)
    assert loaded["result"]["analysis_scope_id"] == result.analysis_scope_id
    assert loaded["scope"] == scope.to_dict()
    manifest = loaded["manifest"]
    assert manifest["success"] is False
    assert manifest["provenance"]["scientifically_eligible"] is False
    for item in manifest["artifacts"]:
        assert artifact_sha256(output / item["path"]) == item["sha256"]
    assert artifact_sha256(output / "metrics_manifest.json") == (
        output / "metrics_manifest.sha256"
    ).read_text(encoding="ascii").strip()

    with pytest.raises(FileExistsError):
        write_comparison_metrics_outputs(
            result,
            scope,
            output,
            comparison_config=config["comparison_metrics"],
            input_artifacts=(),
            git_commit="0" * 40,
            random_state=0,
        )


def test_scope_json_round_trip_is_exact() -> None:
    _, scope, _, _ = _fixture()
    restored = ComparisonAnalysisScope.from_dict(
        json.loads(json.dumps(scope.to_dict()))
    )
    assert restored == scope
    assert restored.sha256 == scope.sha256

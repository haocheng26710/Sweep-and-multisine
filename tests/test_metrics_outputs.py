from __future__ import annotations

import csv
import hashlib
import json

import pytest

from acoustic_encoder.metrics import (
    AnalysisScope,
    QCInclusionPolicy,
    ScopeRole,
    SelectionPolicy,
    analyze_direction_feature_sets,
)
from acoustic_encoder.metrics_outputs import write_direction_metrics_outputs
from acoustic_encoder.mock_data import generate_directional_feature_set_mock
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import QCStatus


def _config() -> dict:
    return {
        "schema_version": "1.0.0",
        "provisional": True,
        "minimum_common_valid_features": 4,
        "minimum_common_valid_fraction": 0.75,
        "minimum_direction_count": 4,
        "center_direction_matrix": False,
        "repeatability_distance_metric": "rms",
        "morphology_gain": {
            "distance_metric": "rms",
            "minimum_denominator": 1.0e-12,
        },
    }


def _result():
    features = generate_directional_feature_set_mock(feature_count=8)
    scope = AnalysisScope(
        schema_version="1.0.0",
        analysis_scope_id="dev-c5-output",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=tuple(feature.sample_id for feature in features),
        partition=None,
        direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        selection_policy=SelectionPolicy(
            policy_id="human-valid-no-review",
            require_human_valid=True,
            exclude_manual_review=True,
        ),
        qc_inclusion_policy=QCInclusionPolicy(
            policy_id="valid-warning",
            included_statuses=(QCStatus.VALID, QCStatus.WARNING),
            missing_status="exclude",
            allow_exclude_candidate=False,
        ),
    )
    return analyze_direction_feature_sets(features, scope, _config())


def test_metrics_outputs_are_long_form_hash_audited_and_immutable(tmp_path) -> None:
    output = tmp_path / "processed"

    written = write_direction_metrics_outputs(_result(), output)

    expected = {
        "direction_statistics.csv",
        "direction_templates.csv",
        "correlation_matrix.csv",
        "cosine_matrix.csv",
        "euclidean_distance_matrix.csv",
        "rms_distance_matrix.csv",
        "median_absolute_difference_matrix.csv",
        "repeatability_pairs.csv",
        "repeatability_summary.csv",
        "between_direction_pairs.csv",
        "singular_values.csv",
        "metrics_summary.csv",
        "selection_audit.csv",
        "metrics_manifest.json",
        "metrics_manifest.sha256",
    }
    assert {path.name for path in written.values()} == expected
    assert all(path.is_file() for path in written.values())

    with written["correlation_matrix"].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 16
    assert set(rows[0]) == {
        "row_direction_index",
        "row_angle_deg",
        "column_direction_index",
        "column_angle_deg",
        "value",
        "available",
        "unavailable_reason",
        "feature_count",
    }
    assert {row["feature_count"] for row in rows} == {"8"}

    with written["selection_audit"].open(encoding="utf-8", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    assert {
        "source_qc_warning_reasons",
        "source_qc_exclude_candidate_reasons",
        "source_qc_unavailable_checks",
    }.issubset(audit_rows[0])

    manifest = json.loads(written["metrics_manifest"].read_text(encoding="utf-8"))
    assert manifest["processing_status"] == "completed"
    assert manifest["scope"]["analysis_scope_id"] == "dev-c5-output"
    assert manifest["provenance"] == {
        "data_origin": "simulated",
        "dataset_role": "software_validation",
        "eligible_for_scientific_analysis": False,
        "run_purpose": "software_validation",
        "scientific_use": "prohibited_simulated_software_validation",
    }
    assert manifest["template_usage"] == {
        "eligible_for_training_dictionary": False,
        "tone_selection_allowed": False,
        "usage": "descriptive_only",
    }
    assert len(manifest["inputs"]) == 32
    assert all(item["feature_content_sha256"].startswith("sha256:") for item in manifest["inputs"])
    assert len(manifest["artifacts"]) == 13
    for artifact in manifest["artifacts"]:
        path = output / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    assert written["metrics_manifest_sha256"].read_text(encoding="ascii").strip() == (
        hashlib.sha256(written["metrics_manifest"].read_bytes()).hexdigest()
    )

    with pytest.raises(FileExistsError, match="already exists"):
        write_direction_metrics_outputs(_result(), output)

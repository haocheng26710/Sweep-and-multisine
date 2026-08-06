from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import yaml

from acoustic_encoder.cross_mode_classification import ComparisonMetricsReference
from acoustic_encoder.cross_mode_classification_cli import run_cross_mode_classification_cli
from acoustic_encoder.dataset_quality_control import (
    CohortRole,
    ConditionCompletenessResult,
    DatasetQCScope,
    DatasetQCReference,
    DatasetScopeMember,
    ExpectedCondition,
    MeasurementQCRollup,
    dataset_qc_sha256,
)
from acoustic_encoder.quality_control import QCCheckStatus
from acoustic_encoder.dataset_quality_outputs import write_dataset_quality_outputs
from acoustic_encoder.schemas import QCStatus, artifact_sha256, save_feature_set

from test_cross_mode_classification import _fixture


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _canonical_hash(payload) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def test_cross_mode_cli_runs_from_explicit_hashed_artifacts(tmp_path) -> None:
    artifacts, classification_scope, p2b, comparison, fixture_config = _fixture()
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    entries = []
    p2_inputs = []
    for artifact_id, feature in artifacts.items():
        base = input_root / artifact_id
        npz_path, json_path = save_feature_set(feature, base)
        entries.append(
            {
                "artifact_id": artifact_id, "sample_id": feature.sample_id,
                "feature_base_path": base.as_posix(),
                "feature_npz_sha256": artifact_sha256(npz_path),
                "feature_json_sha256": artifact_sha256(json_path),
            }
        )
        p2_inputs.extend(
            {
                "sample_id": feature.sample_id, "artifact_role": role,
                "path": path.as_posix(), "sha256": artifact_sha256(path),
            }
            for role, path in (("feature_set_npz", npz_path), ("feature_set_json", json_path))
        )

    p2_scope = DatasetQCScope(
        "1.0.0", classification_scope.dataset_analysis_scope_id, "software_validation",
        tuple(
            DatasetScopeMember(
                feature.sample_id, "development", f"condition-{index:03d}", "explicit CLI fixture"
            )
            for index, feature in enumerate(artifacts.values())
        ),
        tuple(
            ExpectedCondition(
                f"condition-{index:03d}", "development", feature.source_measurement_mode,
                "U4ENC", f"A{int(feature.meta.angle_deg):03d}", float(feature.meta.angle_deg),
                feature.meta.session_id, feature.meta.repeat_type,
                feature.meta.reposition_round_id, feature.meta.assembly_id,
                feature.meta.acquisition_block_id, 1,
            )
            for index, feature in enumerate(artifacts.values())
        ),
    )
    dataset_config = {"cli_fixture": True}
    p2b = replace(
        p2b,
        scope_sha256=p2_scope.sha256,
        config_sha256=_canonical_hash(dataset_config),
        condition_results=tuple(
            ConditionCompletenessResult(
                f"condition-{index:03d}", CohortRole.DEVELOPMENT, 1, 1, 1, 0, 0, 0, 0, 0,
                QCCheckStatus.VALID, (), (feature.sample_id,), (),
            )
            for index, feature in enumerate(artifacts.values())
        ),
        measurement_rollups=tuple(
            MeasurementQCRollup(
                audit.sample_id, CohortRole.DEVELOPMENT, audit.p2a_qc_sha256,
                QCStatus.VALID, QCStatus.VALID, QCStatus.VALID,
                (), (), (), (), True, None, True,
            )
            for audit in p2b.input_audit
        ),
    )
    p2_dir = tmp_path / "p2b"
    write_dataset_quality_outputs(
        p2b, p2_scope, dataset_config, p2_dir,
        input_artifacts=p2_inputs, git_commit="0" * 40, random_state=20260806,
        created_at_utc="2026-08-06T00:00:00+00:00",
    )

    comparison_dir = tmp_path / "p4b"
    comparison_dir.mkdir()
    comparison_path = comparison_dir / "comparison_metrics.json"
    comparison_path.write_text(json.dumps({
        "schema_version": "1.0.0", "result_sha256": comparison["result_sha256"],
        "scope": comparison["scope"], "result": comparison["result"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    comparison_manifest_path = comparison_dir / "metrics_manifest.json"
    comparison_manifest_path.write_text(json.dumps({
        "schema_version": "1.0.0", "result_sha256": comparison["result_sha256"],
        "artifacts": [{"path": "comparison_metrics.json", "sha256": artifact_sha256(comparison_path)}],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (comparison_dir / "metrics_manifest.sha256").write_text(
        artifact_sha256(comparison_manifest_path) + "\n", encoding="ascii"
    )

    classification_scope = replace(
        classification_scope,
        dataset_qc_reference=DatasetQCReference(
            classification_scope.dataset_analysis_scope_id, dataset_qc_sha256(p2b)
        ),
        comparison_metrics_reference=ComparisonMetricsReference(
            classification_scope.dataset_analysis_scope_id,
            comparison["scope"]["sha256"], comparison["result_sha256"],
            "sha256:" + artifact_sha256(comparison_manifest_path),
        ),
    )
    scope_path = input_root / "cross_mode_scope.json"
    scope_path.write_text(json.dumps(classification_scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    inputs_path = input_root / "cross_mode_inputs.json"
    inputs_path.write_text(json.dumps({
        "schema_version": "1.0.0", "classification_scope_id": classification_scope.classification_scope_id,
        "data_origin": "simulated", "run_purpose": "software_validation", "features": entries,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "measurement_mode": "rew_sweep", "run_purpose": "software_validation",
        "classification": {"frequency_bands": fixture_config["frequency_bands"]},
    }, sort_keys=False), encoding="utf-8")

    status = run_cross_mode_classification_cli(
        (
            "--config", str(config_path), "--scope", str(scope_path),
            "--inputs", str(inputs_path), "--dataset-qc-dir", str(p2_dir),
            "--comparison-dir", str(comparison_dir), "--output-root", str(tmp_path / "outputs"),
            "--run-id", "DEV-C9-cli",
        ),
        project_root=PROJECT_ROOT,
    )

    assert status == 0
    output = tmp_path / "outputs" / "simulated" / "software_validation" / "DEV-C9-cli" / "cross_mode_classification"
    manifest = json.loads((output / "classification_manifest.json").read_text(encoding="utf-8"))
    assert manifest["success"] is True
    assert manifest["provenance"]["scientifically_eligible"] is False

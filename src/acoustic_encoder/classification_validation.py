"""Formal deterministic P5-A software-validation runs for each input mode."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from .classification import ClassificationFeatureReference, ClassificationScope, ClassificationScopeMember
from .classification_cli import run_classification_cli
from .dataset_quality_control import DatasetQCReference, dataset_qc_sha256, feature_set_content_sha256
from .dataset_quality_validation import run_simulated_dataset_quality_validation
from .schemas import FeatureKind, artifact_sha256, load_feature_set


def run_simulated_classification_validation(*, project_root: Path, output_root: Path, run_id: str, feature_kind: FeatureKind) -> Path:
    """Create P2-B-qualified FeatureSets and exercise the persisted-input P5-A CLI."""
    p2_run_id = "DEV-C8-P2B-" + hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:10]
    p2b = run_simulated_dataset_quality_validation(
        project_root=project_root,
        config_path=project_root / "config" / "validation_dev_c6_dataset_qc.yaml",
        output_root=output_root,
        run_id=p2_run_id,
        feature_count=21,
        canonical_ready_fixture=True,
        feature_kind=feature_kind,
    )
    p2_inputs = json.loads(p2b.input_manifest_path.read_text(encoding="utf-8"))
    features = tuple(load_feature_set(Path(item["feature_base_path"])) for item in p2_inputs["measurements"])
    scope_id = p2b.result.analysis_scope_id
    scope = ClassificationScope(
        "1.0.0", scope_id, "software_validation", "canonical_cohort", "software_validation",
        features[0].source_measurement_mode, str(features[0].meta.configuration), features[0].feature_kind.value,
        features[0].preprocessing_id, features[0].tone_set_id, (0.0, 90.0, 180.0, 270.0),
        tuple(ClassificationScopeMember.from_feature_set(item, cohort_role="development", direction_id=f"A{int(item.meta.angle_deg):03d}", selection_reason="formal DEV-C8 simulated validation") for item in features),
        tuple(ClassificationFeatureReference(f"feature-{index:03d}", item.sample_id, feature_set_content_sha256(item)) for index, item in enumerate(features)),
        ("leave_one_session_out", "leave_one_reposition_round_out", "leave_one_assembly_out"),
        ("nearest_template_correlation", "nearest_centroid", "logistic_regression"),
        ("validation_1k_1p2k",), 20260806,
        DatasetQCReference(scope_id, dataset_qc_sha256(p2b.result)),
    )
    inputs_root = output_root / "simulated" / "software_validation" / run_id / "inputs"
    inputs_root.mkdir(parents=True, exist_ok=False)
    scope_path = inputs_root / "classification_scope.json"
    scope_path.write_text(json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    feature_entries = []
    for index, (feature, item) in enumerate(zip(features, p2_inputs["measurements"], strict=True)):
        base = Path(item["feature_base_path"])
        feature_entries.append({"artifact_id": f"feature-{index:03d}", "sample_id": feature.sample_id, "feature_base_path": base.as_posix(), "feature_npz_sha256": artifact_sha256(base.with_suffix(".npz")), "feature_json_sha256": artifact_sha256(base.with_suffix(".json"))})
    inputs_path = inputs_root / "classification_inputs.json"
    inputs_path.write_text(json.dumps({"schema_version": "1.0.0", "classification_scope_id": scope_id, "data_origin": "simulated", "run_purpose": "software_validation", "features": feature_entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status = run_classification_cli(("--config", str(project_root / "config" / "validation_dev_c8_classification.yaml"), "--scope", str(scope_path), "--inputs", str(inputs_path), "--dataset-qc-dir", str(p2b.output_directory), "--output-root", str(output_root), "--run-id", run_id), project_root=project_root)
    if status != 0:
        raise RuntimeError(f"simulated classification validation failed: {status}")
    return output_root / "simulated" / "software_validation" / run_id / "classification"

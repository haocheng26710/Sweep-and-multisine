"""Stable, hash-audited DEV-C13 P9-B artifacts."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .projection_ablation import P9ProjectionAblationResult, P9ProjectionAblationScope
from .schemas import artifact_sha256, load_feature_set, save_feature_set
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .version import SCHEMA_VERSION_QUARTET


PROJECTION_ABLATION_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fields})


def write_projection_ablation_outputs(
    result: P9ProjectionAblationResult,
    scope: P9ProjectionAblationScope,
    config: Mapping[str, Any],
    output_directory: str | Path,
    *,
    input_file_hashes: Mapping[str, str],
    git_commit: str,
    git_dirty: bool,
    created_at: str | None = None,
) -> tuple[Path, ...]:
    """Write a complete P9-B directory once, including every derivation hash."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"projection-ablation output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    paths: list[Path] = []

    scope_path = output / "ablation_scope.json"
    _write_json(scope_path, scope.to_dict())
    paths.append(scope_path)

    def csv_file(name: str, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
        path = output / name
        _write_csv(path, fields, rows)
        paths.append(path)

    csv_file(
        "fold_selection_references.csv",
        tuple(scope.fold_selection_references[0].to_dict()) if scope.fold_selection_references else ("outer_fold_id",),
        (item.to_dict() for item in scope.fold_selection_references),
    )
    subset_fields = tuple(result.subset_definitions[0].to_dict()) if result.subset_definitions else (
        "schema_version", "outer_fold_id", "subset_size", "selection_order_candidate_ids",
        "feature_order_candidate_ids", "feature_order_source_indices", "frequencies_hz", "dft_bins",
        "selection_artifact_sha256", "status", "reason_codes",
    )
    csv_file(
        "tone_subset_definitions.csv", subset_fields,
        ({**item.to_dict(), **{name: json.dumps(item.to_dict()[name], separators=(",", ":")) for name in ("selection_order_candidate_ids", "feature_order_candidate_ids", "feature_order_source_indices", "frequencies_hz", "dft_bins", "reason_codes")}} for item in result.subset_definitions),
    )
    derived_rows: list[dict[str, Any]] = []
    for item in sorted(result.derived_features, key=lambda value: (value.outer_fold_id, value.feature_set.tone_set_id or "", value.feature_set.sample_id)):
        subset_tag = item.feature_set.tone_set_id or item.subset_definition_sha256
        safe_subset = subset_tag.replace(":", "_")
        base = output / "derived_features" / item.outer_fold_id / safe_subset / item.feature_set.sample_id
        npz_path, json_path = save_feature_set(item.feature_set, base)
        derivation_path = base.with_name(base.name + ".derivation.json")
        _write_json(derivation_path, item.to_dict())
        paths.extend((npz_path, json_path, derivation_path))
        derived_rows.append({
            **item.to_dict(),
            "feature_base_path": base.relative_to(output).as_posix(),
            "feature_npz_sha256": artifact_sha256(npz_path),
            "feature_json_sha256": artifact_sha256(json_path),
            "derivation_json_sha256": artifact_sha256(derivation_path),
        })
    derived_fields = (
        "schema_version", "outer_fold_id", "subset_definition_sha256", "selection_artifact_sha256",
        "source_feature_content_sha256", "source_feature_contract_sha256", "derivation_method", "sample_id",
        "selected_candidate_ids", "data_origin", "dataset_role", "source_path",
        "derived_feature_content_sha256", "derived_feature_contract_sha256", "feature_base_path",
        "feature_npz_sha256", "feature_json_sha256", "derivation_json_sha256",
    )
    csv_file("derived_feature_index.csv", derived_fields, (
        {**row, "selected_candidate_ids": json.dumps(row["selected_candidate_ids"], separators=(",", ":"))}
        for row in derived_rows
    ))
    p4_fields = tuple(result.p4_results[0].to_dict()) if result.p4_results else (
        "schema_version", "outer_fold_id", "evaluation_stage", "fold_id", "subset_size", "metric_id",
        "status", "broad_value", "sparse_value", "absolute_delta", "relative_ratio", "retention",
        "retention_mode", "source_sample_ids", "reason_codes",
    )
    csv_file(
        "p4_metric_preservation.csv", p4_fields,
        ({**item.to_dict(), "source_sample_ids": json.dumps(item.source_sample_ids, separators=(",", ":")), "reason_codes": json.dumps(item.reason_codes, separators=(",", ":"))} for item in result.p4_results),
    )
    classification_fields = tuple(result.inner_classification_results[0].to_dict()) if result.inner_classification_results else (
        "schema_version", "outer_fold_id", "evaluation_stage", "fold_id", "subset_size", "model_id", "status",
        "reason_codes", "broad_sample_ids", "sparse_sample_ids", "broad_balanced_accuracy", "sparse_balanced_accuracy",
        "balanced_accuracy_drop", "broad_macro_f1", "sparse_macro_f1", "macro_f1_drop", "broad_coverage",
        "sparse_coverage", "broad_confusion_matrix", "sparse_confusion_matrix", "prediction_count", "test_sample_ids",
        "true_directions_deg", "broad_predictions_deg", "sparse_predictions_deg",
    )
    csv_file(
        "inner_classification_metrics.csv", classification_fields,
        ({name: (json.dumps(value, separators=(",", ":")) if isinstance(value, list) else value) for name, value in item.to_dict().items()} for item in result.inner_classification_results),
    )
    decision_fields = tuple(result.minimum_tone_decisions[0].to_dict()) if result.minimum_tone_decisions else (
        "schema_version", "outer_fold_id", "status", "selected_subset_size", "candidate_subset_sizes",
        "passing_subset_sizes", "reason_codes", "evidence_stage", "lifecycle",
    )
    csv_file(
        "minimum_tone_decisions.csv", decision_fields,
        ({name: (json.dumps(value, separators=(",", ":")) if isinstance(value, list) else value) for name, value in item.to_dict().items()} for item in result.minimum_tone_decisions),
    )
    prediction_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    for outer in result.outer_fold_evaluations:
        classification = outer.classification_result
        if classification is not None:
            for sample_id, truth, broad, sparse in zip(
                classification.test_sample_ids, classification.true_directions_deg,
                classification.broad_predictions_deg, classification.sparse_predictions_deg, strict=True,
            ):
                prediction_rows.append({
                    "outer_fold_id": outer.outer_fold_id, "subset_size": outer.selected_subset_size,
                    "sample_id": sample_id, "true_direction_deg": truth,
                    "broad_prediction_deg": broad, "sparse_prediction_deg": sparse,
                })
            metric_rows.append({
                "outer_fold_id": outer.outer_fold_id, "subset_size": outer.selected_subset_size,
                "status": outer.status.value, "balanced_accuracy_broad": classification.broad_balanced_accuracy,
                "balanced_accuracy_sparse": classification.sparse_balanced_accuracy,
                "balanced_accuracy_drop": classification.balanced_accuracy_drop,
                "macro_f1_broad": classification.broad_macro_f1, "macro_f1_sparse": classification.sparse_macro_f1,
                "macro_f1_drop": classification.macro_f1_drop, "coverage": classification.sparse_coverage,
                "confusion_matrix_broad": json.dumps(classification.broad_confusion_matrix, separators=(",", ":")),
                "confusion_matrix_sparse": json.dumps(classification.sparse_confusion_matrix, separators=(",", ":")),
                "prediction_count": classification.prediction_count,
            })
        else:
            metric_rows.append({"outer_fold_id": outer.outer_fold_id, "subset_size": outer.selected_subset_size, "status": outer.status.value})
    csv_file(
        "outer_fold_predictions.csv",
        ("outer_fold_id", "subset_size", "sample_id", "true_direction_deg", "broad_prediction_deg", "sparse_prediction_deg"),
        prediction_rows,
    )
    csv_file(
        "outer_fold_metrics.csv",
        ("outer_fold_id", "subset_size", "status", "balanced_accuracy_broad", "balanced_accuracy_sparse", "balanced_accuracy_drop", "macro_f1_broad", "macro_f1_sparse", "macro_f1_drop", "coverage", "confusion_matrix_broad", "confusion_matrix_sparse", "prediction_count"),
        metric_rows,
    )
    summary = {
        "schema_version": "1.0.0",
        "result_sha256": result.sha256,
        "processing_status": result.processing_status,
        "analysis_scope_id": result.analysis_scope_id,
        "analysis_scope_sha256": result.analysis_scope_sha256,
        "data_origin": result.data_origin,
        "run_purpose": result.run_purpose,
        "scientifically_eligible": result.scientifically_eligible,
        "deployment_eligible": result.deployment_eligible,
        "canonical_analysis": result.canonical_analysis,
        "final_test_read": result.final_test_read,
        "minimum_tone_decisions": [item.to_dict() for item in result.minimum_tone_decisions],
        "outer_fold_evaluations": [item.to_dict() for item in result.outer_fold_evaluations],
        "warnings": list(result.warnings),
        "failures": list(result.failures),
    }
    summary_path = output / "projection_fidelity_summary.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)

    artifact_hashes = {
        path.relative_to(output).as_posix(): artifact_sha256(path)
        for path in sorted(paths, key=lambda value: value.as_posix())
    }
    manifest = {
        "schema_version": PROJECTION_ABLATION_MANIFEST_SCHEMA_VERSION,
        **SCHEMA_VERSION_QUARTET,
        "analysis_scope_id": scope.analysis_scope_id,
        "analysis_scope_sha256": scope.sha256,
        "result_sha256": result.sha256,
        "config_sha256": _canonical_sha256(config),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "random_state": scope.random_state,
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "deployment_eligible": False,
        "canonical_analysis": False,
        "final_test_read": False,
        "sealed_final_test_sample_ids": list(scope.sealed_final_test_sample_ids),
        "sealed_final_test_sha256": scope.sealed_final_test_sha256,
        "input_file_hashes": dict(sorted(input_file_hashes.items())),
        "fold_selection_artifact_hashes": {
            item.outer_fold_id: item.selection_artifact_sha256 for item in scope.fold_selection_references
        },
        "derived_feature_content_hashes": {
            f"{item.outer_fold_id}/{item.feature_set.tone_set_id}/{item.feature_set.sample_id}": item.derived_feature_content_sha256
            for item in result.derived_features
        },
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
    }
    manifest["manifest_content_sha256"] = _canonical_sha256(manifest)
    manifest_path = output / "ablation_manifest.json"
    _write_json(manifest_path, manifest)
    paths.append(manifest_path)
    sidecar = output / "ablation_manifest.sha256"
    sidecar.write_text(artifact_sha256(manifest_path) + "  ablation_manifest.json\n", encoding="utf-8")
    paths.append(sidecar)
    return tuple(paths)


def load_projection_ablation_bundle(output_directory: str | Path) -> dict[str, Any]:
    """Recompute manifest, artifact, and derived FeatureSet hashes."""
    output = Path(output_directory)
    manifest_path = output / "ablation_manifest.json"
    expected_file = (output / "ablation_manifest.sha256").read_text(encoding="utf-8").split()[0]
    if artifact_sha256(manifest_path) != expected_file:
        raise ValueError("projection-ablation manifest file hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    semantic = dict(manifest)
    expected_content = semantic.pop("manifest_content_sha256")
    if _canonical_sha256(semantic) != expected_content:
        raise ValueError("projection-ablation manifest content hash mismatch")
    for relative, digest in manifest["artifact_hashes"].items():
        if artifact_sha256(output / relative) != digest:
            raise ValueError(f"projection-ablation artifact hash mismatch: {relative}")
    rows = list(csv.DictReader((output / "derived_feature_index.csv").open(encoding="utf-8", newline="")))
    for row in rows:
        base = output / row["feature_base_path"]
        feature = load_feature_set(base)
        if artifact_sha256(base.with_suffix(".npz")) != row["feature_npz_sha256"] or artifact_sha256(base.with_suffix(".json")) != row["feature_json_sha256"]:
            raise ValueError("derived FeatureSet file hash mismatch")
        if feature_set_content_sha256(feature) != row["derived_feature_content_sha256"] or feature_contract_sha256(feature) != row["derived_feature_contract_sha256"]:
            raise ValueError("derived FeatureSet semantic hash mismatch")
    return {
        "manifest": manifest,
        "scope": json.loads((output / "ablation_scope.json").read_text(encoding="utf-8")),
        "summary": json.loads((output / "projection_fidelity_summary.json").read_text(encoding="utf-8")),
    }

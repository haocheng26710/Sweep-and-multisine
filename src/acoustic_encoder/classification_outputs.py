"""Stable CSV/JSON serialization for P5-A classification results."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from .classification import ClassificationResult
from .schemas import artifact_sha256


def _json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _value(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return json.dumps(list(value), separators=(",", ":"), ensure_ascii=False)
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _csv(path: Path, rows: Iterable[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _value(row.get(column)) for column in columns})


def _prediction_groups(result: ClassificationResult) -> dict[tuple[str, str, str], list[Any]]:
    groups: dict[tuple[str, str, str], list[Any]] = {}
    for item in result.predictions:
        groups.setdefault((item.protocol, item.band_id, item.model_id), []).append(item)
    return groups


def _derived_tables(result: ClassificationResult) -> dict[str, list[dict[str, Any]]]:
    aggregate: list[dict[str, Any]] = []
    per_class: list[dict[str, Any]] = []
    confusion: list[dict[str, Any]] = []
    difficult: list[dict[str, Any]] = []
    for key, rows in sorted(_prediction_groups(result).items()):
        protocol, band_id, model_id = key
        available = [row for row in rows if row.available]
        fold_rows = [row for row in result.fold_metrics if (row.protocol, row.band_id, row.model_id) == key and row.available]
        accuracy_values = np.asarray([row.accuracy for row in fold_rows], dtype=float)
        balanced_values = np.asarray([row.balanced_accuracy for row in fold_rows], dtype=float)
        aggregate.append({
            "protocol": protocol, "band_id": band_id, "model_id": model_id,
            "available_fold_count": len(fold_rows), "total_fold_count": len({row.fold_id for row in rows}),
            "accuracy_mean": None if not len(accuracy_values) else float(np.mean(accuracy_values)),
            "accuracy_median": None if not len(accuracy_values) else float(np.median(accuracy_values)),
            "accuracy_std": None if len(accuracy_values) < 2 else float(np.std(accuracy_values, ddof=1)),
            "accuracy_min": None if not len(accuracy_values) else float(np.min(accuracy_values)),
            "accuracy_max": None if not len(accuracy_values) else float(np.max(accuracy_values)),
            "balanced_accuracy_mean": None if not len(balanced_values) else float(np.mean(balanced_values)),
            "prediction_coverage": (len(available) / len(rows)) if rows else 0.0,
        })
        if not available:
            continue
        truth = np.asarray([row.true_direction_deg for row in available], dtype=float)
        predicted = np.asarray([row.predicted_direction_deg for row in available], dtype=float)
        labels = np.asarray(sorted(set(truth) | set(predicted)), dtype=float)
        precision, recall, f1, support = precision_recall_fscore_support(truth, predicted, labels=labels, zero_division=np.nan)
        matrix = np.zeros((len(labels), len(labels)), dtype=int)
        label_index = {label: index for index, label in enumerate(labels)}
        for true, pred in zip(truth, predicted, strict=True):
            matrix[label_index[true], label_index[pred]] += 1
        for index, label in enumerate(labels):
            per_class.append({"protocol": protocol, "band_id": band_id, "model_id": model_id, "direction_deg": label, "precision": precision[index], "recall": recall[index], "f1": f1[index], "support": int(support[index])})
            for predicted_index, predicted_label in enumerate(labels):
                confusion.append({"protocol": protocol, "band_id": band_id, "model_id": model_id, "true_direction_deg": label, "predicted_direction_deg": predicted_label, "count": int(matrix[index, predicted_index])})
        pair_counts: dict[tuple[float, float], int] = {}
        for true, pred in zip(truth, predicted, strict=True):
            if true != pred:
                pair = tuple(sorted((float(true), float(pred))))
                pair_counts[pair] = pair_counts.get(pair, 0) + 1
        for pair, count in sorted(pair_counts.items(), key=lambda item: (-item[1], item[0])):
            difficult.append({"protocol": protocol, "band_id": band_id, "model_id": model_id, "direction_a_deg": pair[0], "direction_b_deg": pair[1], "confusion_count": count})
    return {"aggregate": aggregate, "per_class": per_class, "confusion": confusion, "difficult": difficult}


def write_classification_outputs(
    result: ClassificationResult,
    output_directory: str | Path,
    *,
    provenance: Mapping[str, Any],
    input_artifacts: Sequence[Mapping[str, Any]],
    versions: Mapping[str, str],
) -> Path:
    """Write one immutable P5-A result bundle and its hash manifest."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"classification output directory already exists: {output}")
    output.mkdir(parents=True)
    result_path = output / "classification_result.json"
    _json(result_path, result.to_dict())
    split_rows = [item.to_dict() for item in result.split_audit]
    _csv(output / "split_audit.csv", split_rows, ("protocol", "fold_id", "held_out_group", "train_sample_ids", "test_sample_ids", "excluded_final_test_sample_ids", "valid", "unavailable_reason"))
    assignment_rows = []
    for split in result.split_audit:
        assignment_rows.extend({"protocol": split.protocol, "fold_id": split.fold_id, "sample_id": sample_id, "assignment": assignment} for assignment, ids in (("train", split.train_sample_ids), ("test", split.test_sample_ids), ("sealed_final_test", split.excluded_final_test_sample_ids)) for sample_id in ids)
    _csv(output / "fold_assignments.csv", assignment_rows, ("protocol", "fold_id", "sample_id", "assignment"))
    prediction_rows = [item.to_dict() for item in result.predictions]
    _csv(output / "predictions.csv", prediction_rows, tuple(PredictionColumns))
    metric_rows = [item.to_dict() for item in result.fold_metrics]
    _csv(output / "fold_metrics.csv", metric_rows, tuple(FoldMetricColumns))
    mask_rows = [item.to_dict() for item in result.feature_mask_audit]
    _csv(output / "feature_mask_audit.csv", mask_rows, ("protocol", "fold_id", "band_id", "selected_feature_indices", "selected_feature_names", "feature_count", "mask_source"))
    transform_rows = [{"protocol": item.protocol, "fold_id": item.fold_id, "band_id": item.band_id, "model_id": model, "fit_scope": "training_fold_only", "transform": ("none" if model == "nearest_template_correlation" else "standard_scaler")} for item in result.feature_mask_audit for model in sorted({metric.model_id for metric in result.fold_metrics})]
    _csv(output / "training_transform_audit.csv", transform_rows, ("protocol", "fold_id", "band_id", "model_id", "fit_scope", "transform"))
    model_rows = [{"model_id": model, "parameters_json": json.dumps(({"similarity": "pearson"} if model == "nearest_template_correlation" else {"distance": "euclidean", "standardization": "training_fold_only"} if model == "nearest_centroid" else {"solver": "lbfgs", "C": 1.0, "max_iter": 1000, "class_weight": "balanced", "standardization": "training_fold_only"}), sort_keys=True, separators=(",", ":"))} for model in sorted({metric.model_id for metric in result.fold_metrics})]
    _csv(output / "model_parameters.csv", model_rows, ("model_id", "parameters_json"))
    derived = _derived_tables(result)
    _csv(output / "aggregate_metrics.csv", derived["aggregate"], ("protocol", "band_id", "model_id", "available_fold_count", "total_fold_count", "accuracy_mean", "accuracy_median", "accuracy_std", "accuracy_min", "accuracy_max", "balanced_accuracy_mean", "prediction_coverage"))
    _csv(output / "per_class_metrics.csv", derived["per_class"], ("protocol", "band_id", "model_id", "direction_deg", "precision", "recall", "f1", "support"))
    _csv(output / "confusion_matrix.csv", derived["confusion"], ("protocol", "band_id", "model_id", "true_direction_deg", "predicted_direction_deg", "count"))
    _csv(output / "difficult_direction_pairs.csv", derived["difficult"], ("protocol", "band_id", "model_id", "direction_a_deg", "direction_b_deg", "confusion_count"))
    artifact_paths = sorted(path for path in output.iterdir() if path.name != "classification_manifest.json")
    manifest = {
        "schema_version": "1.0.0", "processing_status": result.processing_status,
        "success": result.processing_status == "completed", "classification_scope_id": result.classification_scope_id,
        "scope_sha256": result.scope_sha256, "config_sha256": result.config_sha256,
        "versions": dict(versions), "provenance": dict(provenance),
        "input_artifacts": list(input_artifacts),
        "artifacts": [{"path": path.name, "sha256": "sha256:" + artifact_sha256(path)} for path in artifact_paths],
    }
    manifest_path = output / "classification_manifest.json"
    _json(manifest_path, manifest)
    (output / "classification_manifest.json.sha256").write_text("sha256:" + artifact_sha256(manifest_path) + "\n", encoding="ascii")
    return output


PredictionColumns = ("protocol", "fold_id", "band_id", "model_id", "sample_id", "true_direction_deg", "predicted_direction_deg", "second_direction_deg", "score", "margin", "available", "unavailable_reason")
FoldMetricColumns = ("protocol", "fold_id", "band_id", "model_id", "available", "accuracy", "balanced_accuracy", "prediction_coverage", "test_count", "available_prediction_count", "unavailable_reason")


def load_classification_bundle(output_directory: str | Path) -> dict[str, Any]:
    """Verify every persisted digest and return the typed JSON payloads."""
    output = Path(output_directory)
    manifest_path = output / "classification_manifest.json"
    expected = (output / "classification_manifest.json.sha256").read_text(encoding="ascii").strip().removeprefix("sha256:")
    if artifact_sha256(manifest_path) != expected:
        raise ValueError("classification manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        if "sha256:" + artifact_sha256(output / item["path"]) != item["sha256"]:
            raise ValueError(f"classification artifact hash mismatch: {item['path']}")
    result_payload = json.loads((output / "classification_result.json").read_text(encoding="utf-8"))
    ClassificationResult.from_dict(result_payload)
    return {"manifest": manifest, "result": result_payload}

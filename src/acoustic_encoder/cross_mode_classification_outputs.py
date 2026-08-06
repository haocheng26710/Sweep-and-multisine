"""Immutable CSV/JSON bundle for leakage-safe P5-B validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from .cross_mode_classification import (
    CrossModeClassificationResult,
    CrossModeClassificationScope,
)
from .schemas import artifact_sha256


def _json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _cell(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return json.dumps(list(value), separators=(",", ":"), ensure_ascii=False)
    if value is None or isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _csv(
    path: Path, rows: Iterable[Mapping[str, Any]], columns: Sequence[str]
) -> None:
    materialized = list(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in materialized:
            writer.writerow({column: _cell(row.get(column)) for column in columns})


def _prediction_tables(result: CrossModeClassificationResult) -> dict[str, list[dict[str, Any]]]:
    per_class: list[dict[str, Any]] = []
    confusion: list[dict[str, Any]] = []
    difficult: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str, tuple[str, ...], str, str, str], list[Any]] = {}
    for row in result.predictions:
        groups.setdefault(
            (
                row.split_protocol, row.transfer_protocol, row.configuration_id,
                row.train_feature_kinds, row.test_feature_kind, row.band_id, row.model_id,
            ), []
        ).append(row)
    for key, rows in sorted(groups.items()):
        available = [row for row in rows if row.available]
        if not available:
            continue
        truth = np.asarray([row.true_direction_deg for row in available], dtype=float)
        predicted = np.asarray([row.predicted_direction_deg for row in available], dtype=float)
        labels = np.asarray(sorted(set(truth) | set(predicted)), dtype=float)
        precision, recall, f1, support = precision_recall_fscore_support(
            truth, predicted, labels=labels, zero_division=np.nan
        )
        split, protocol, configuration, train_kinds, test_kind, band, model = key
        pair_counts: dict[tuple[float, float], int] = {}
        for index, label in enumerate(labels):
            per_class.append(
                {
                    "split_protocol": split, "transfer_protocol": protocol,
                    "configuration_id": configuration,
                    "train_feature_kinds": train_kinds, "test_feature_kind": test_kind,
                    "band_id": band, "model_id": model, "direction_deg": label,
                    "precision": precision[index], "recall": recall[index],
                    "f1": f1[index], "support": int(support[index]),
                }
            )
            for predicted_label in labels:
                count = int(np.sum((truth == label) & (predicted == predicted_label)))
                confusion.append(
                    {
                        "split_protocol": split, "transfer_protocol": protocol,
                        "configuration_id": configuration,
                        "train_feature_kinds": train_kinds, "test_feature_kind": test_kind,
                        "band_id": band, "model_id": model,
                        "true_direction_deg": label,
                        "predicted_direction_deg": predicted_label, "count": count,
                    }
                )
                if label != predicted_label and count:
                    pair = tuple(sorted((float(label), float(predicted_label))))
                    pair_counts[pair] = pair_counts.get(pair, 0) + count
        for pair, count in sorted(pair_counts.items(), key=lambda item: (-item[1], item[0])):
            difficult.append(
                {
                    "split_protocol": split, "transfer_protocol": protocol,
                    "configuration_id": configuration,
                    "train_feature_kinds": train_kinds, "test_feature_kind": test_kind,
                    "band_id": band, "model_id": model,
                    "direction_a_deg": pair[0], "direction_b_deg": pair[1],
                    "confusion_count": count,
                }
            )
    return {"per_class": per_class, "confusion": confusion, "difficult": difficult}


def _protocol_summary(result: CrossModeClassificationResult) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, tuple[str, ...], str, str, str], list[Any]] = {}
    for item in result.fold_metrics:
        groups.setdefault(
            (
                item.split_protocol, item.transfer_protocol, item.configuration_id,
                item.train_feature_kinds, item.test_feature_kind, item.band_id, item.model_id,
            ), []
        ).append(item)
    rows: list[dict[str, Any]] = []
    for key, metrics in sorted(groups.items()):
        available = [item for item in metrics if item.available]
        rows.append(
            {
                "split_protocol": key[0], "transfer_protocol": key[1],
                "configuration_id": key[2], "train_feature_kinds": key[3],
                "test_feature_kind": key[4], "band_id": key[5], "model_id": key[6],
                "valid_fold_count": len(available), "total_fold_count": len(metrics),
                "accuracy_mean": None if not available else float(np.mean([item.accuracy for item in available])),
                "balanced_accuracy_mean": None if not available else float(np.mean([item.balanced_accuracy for item in available])),
                "precision_macro_mean": None if not available else float(np.mean([item.precision_macro for item in available])),
                "recall_macro_mean": None if not available else float(np.mean([item.recall_macro for item in available])),
                "f1_macro_mean": None if not available else float(np.mean([item.f1_macro for item in available])),
                "prediction_coverage": float(np.mean([item.prediction_coverage for item in metrics])),
            }
        )
    return rows


def write_cross_mode_classification_outputs(
    result: CrossModeClassificationResult,
    scope: CrossModeClassificationScope,
    output_directory: str | Path,
    *,
    provenance: Mapping[str, Any],
    input_artifacts: Sequence[Mapping[str, Any]],
    versions: Mapping[str, str],
) -> Path:
    """Write one immutable P5-B bundle; P4-B bias remains audit-only."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"cross-mode classification output directory already exists: {output}")
    output.mkdir(parents=True)
    _json(output / "classification_result.json", result.to_dict())
    _csv(
        output / "protocol_scope_audit.csv",
        [item.to_dict() for item in result.fold_audit],
        ("outer_fold_id", "split_protocol", "transfer_protocol", "held_out_cross_mode_group_ids", "train_artifact_ids", "test_artifact_ids", "train_modes", "test_mode", "sealed_final_test_artifact_ids", "valid", "unavailable_reason"),
    )
    _csv(
        output / "cross_mode_group_audit.csv",
        [item.to_dict() for item in scope.groups],
        tuple(scope.groups[0].to_dict()) if scope.groups else ("cross_mode_group_id",),
    )
    assignments = [
        {
            "outer_fold_id": fold.outer_fold_id, "split_protocol": fold.split_protocol,
            "transfer_protocol": fold.transfer_protocol, "artifact_id": artifact_id,
            "assignment": assignment,
        }
        for fold in result.fold_audit
        for assignment, artifact_ids in (
            ("train", fold.train_artifact_ids), ("test", fold.test_artifact_ids),
            ("sealed_final_test", fold.sealed_final_test_artifact_ids),
        )
        for artifact_id in artifact_ids
    ]
    _csv(output / "fold_assignments.csv", assignments, ("outer_fold_id", "split_protocol", "transfer_protocol", "artifact_id", "assignment"))
    _csv(output / "training_composition.csv", [item.to_dict() for item in result.training_composition], tuple(result.training_composition[0].to_dict()) if result.training_composition else ("outer_fold_id",))
    _csv(output / "compatibility_audit.csv", [item.to_dict() for item in result.compatibility_audit], tuple(result.compatibility_audit[0].to_dict()) if result.compatibility_audit else ("outer_fold_id",))
    _csv(output / "cross_mode_predictions.csv", [item.to_dict() for item in result.predictions], tuple(result.predictions[0].to_dict()) if result.predictions else ("outer_fold_id",))
    _csv(output / "protocol_fold_metrics.csv", [item.to_dict() for item in result.fold_metrics], tuple(result.fold_metrics[0].to_dict()) if result.fold_metrics else ("outer_fold_id",))
    _csv(output / "protocol_summary.csv", _protocol_summary(result), ("split_protocol", "transfer_protocol", "configuration_id", "train_feature_kinds", "test_feature_kind", "band_id", "model_id", "valid_fold_count", "total_fold_count", "accuracy_mean", "balanced_accuracy_mean", "precision_macro_mean", "recall_macro_mean", "f1_macro_mean", "prediction_coverage"))
    _csv(output / "transfer_gap.csv", [item.to_dict() for item in result.transfer_gaps], tuple(result.transfer_gaps[0].to_dict()) if result.transfer_gaps else ("outer_fold_id",))
    derived = _prediction_tables(result)
    _csv(output / "per_class_metrics.csv", derived["per_class"], ("split_protocol", "transfer_protocol", "configuration_id", "train_feature_kinds", "test_feature_kind", "band_id", "model_id", "direction_deg", "precision", "recall", "f1", "support"))
    _csv(output / "confusion_matrices.csv", derived["confusion"], ("split_protocol", "transfer_protocol", "configuration_id", "train_feature_kinds", "test_feature_kind", "band_id", "model_id", "true_direction_deg", "predicted_direction_deg", "count"))
    _csv(output / "difficult_direction_pairs.csv", derived["difficult"], ("split_protocol", "transfer_protocol", "configuration_id", "train_feature_kinds", "test_feature_kind", "band_id", "model_id", "direction_a_deg", "direction_b_deg", "confusion_count"))
    _csv(output / "feature_mask_audit.csv", [item.to_dict() for item in result.feature_mask_audit], tuple(result.feature_mask_audit[0].to_dict()) if result.feature_mask_audit else ("outer_fold_id",))
    transforms = [
        {
            "outer_fold_id": item.outer_fold_id, "transfer_protocol": item.transfer_protocol,
            "band_id": item.band_id, "model_id": model,
            "fit_scope": "training_fold_only",
            "transform": "none" if model == "nearest_template_correlation" else "standard_scaler",
        }
        for item in result.feature_mask_audit for model in scope.models
    ]
    _csv(output / "training_transform_audit.csv", transforms, ("outer_fold_id", "transfer_protocol", "band_id", "model_id", "fit_scope", "transform"))
    artifact_paths = sorted(path for path in output.iterdir())
    provenance_payload = dict(provenance)
    provenance_payload["scientifically_eligible"] = result.scientifically_eligible
    manifest = {
        "schema_version": "1.0.0", "processing_status": result.processing_status,
        "success": result.processing_status == "completed",
        "classification_scope_id": result.classification_scope_id,
        "scope_sha256": result.scope_sha256, "config_sha256": result.config_sha256,
        "dataset_qc_reference": scope.dataset_qc_reference.to_dict(),
        "comparison_metrics_reference": scope.comparison_metrics_reference.to_dict(),
        "random_state": scope.random_state, "versions": dict(versions),
        "provenance": provenance_payload, "input_artifacts": list(input_artifacts),
        "artifacts": [
            {"path": path.name, "sha256": "sha256:" + artifact_sha256(path)}
            for path in artifact_paths
        ],
    }
    manifest_path = output / "classification_manifest.json"
    _json(manifest_path, manifest)
    (output / "classification_manifest.sha256").write_text(
        "sha256:" + artifact_sha256(manifest_path) + "\n", encoding="ascii"
    )
    return output


def load_cross_mode_classification_bundle(output_directory: str | Path) -> dict[str, Any]:
    """Verify all bundle hashes and reconstruct the typed result."""
    output = Path(output_directory)
    manifest_path = output / "classification_manifest.json"
    expected = (output / "classification_manifest.sha256").read_text(encoding="ascii").strip().removeprefix("sha256:")
    if artifact_sha256(manifest_path) != expected:
        raise ValueError("cross-mode classification manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        if "sha256:" + artifact_sha256(output / item["path"]) != item["sha256"]:
            raise ValueError(f"cross-mode classification artifact hash mismatch: {item['path']}")
    result = json.loads((output / "classification_result.json").read_text(encoding="utf-8"))
    CrossModeClassificationResult.from_dict(result)
    return {"manifest": manifest, "result": result}

"""Stable CSV/JSON/model outputs for DEV-C14 P9-C."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .cross_mode_bridge import (
    CrossModeCalibrationModel,
    P9CrossModeBridgeResult,
    P9CrossModeBridgeScope,
    _canonical_sha256,
)
from .schemas import artifact_sha256
from .version import SCHEMA_VERSION_QUARTET


BRIDGE_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _cell(value: Any) -> Any:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _cell(row.get(field)) for field in fields})


def _mean(values: Iterable[float | None]) -> float | None:
    present = [float(item) for item in values if item is not None]
    return None if not present else sum(present) / len(present)


def write_cross_mode_bridge_outputs(
    result: P9CrossModeBridgeResult,
    scope: P9CrossModeBridgeScope,
    config: Mapping[str, Any],
    input_manifest: Mapping[str, Any],
    output_directory: str | Path,
    *,
    input_file_hashes: Mapping[str, str],
    git_commit: str,
    git_dirty: bool,
    created_at: str | None = None,
) -> tuple[Path, ...]:
    """Write the complete bridge bundle once; source artifacts remain untouched."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"cross-mode bridge output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    paths: list[Path] = []

    scope_path = output / "bridge_scope.json"
    input_path = output / "input_manifest.json"
    _write_json(scope_path, scope.to_dict())
    _write_json(input_path, dict(input_manifest))
    paths.extend((scope_path, input_path))

    pair_rows = [item.to_dict() for item in sorted(scope.pairs, key=lambda item: item.match_pair_id)]
    pair_path = output / "matched_pair_audit.csv"
    _write_csv(pair_path, pair_rows, tuple(pair_rows[0]) if pair_rows else ("match_pair_id",))
    paths.append(pair_path)

    fold_rows = []
    tone_authority_rows = []
    for fold in sorted(scope.outer_folds, key=lambda item: item.outer_fold_id):
        fold_rows.append({
            "outer_fold_id": fold.outer_fold_id,
            "split_protocol": fold.split_protocol,
            "training_pair_ids": fold.training_pair_ids,
            "test_pair_ids": fold.test_pair_ids,
            "held_out_cross_mode_group_ids": fold.held_out_cross_mode_group_ids,
            "held_out_physical_state_ids": fold.held_out_physical_state_ids,
            "training_membership_sha256": fold.training_membership_sha256,
        })
        tone_authority_rows.append({
            "outer_fold_id": fold.outer_fold_id,
            "ordered_tone_ids": fold.ordered_tone_ids,
            "ordered_tone_feature_names": fold.ordered_tone_feature_names,
            "ordered_tone_frequencies_hz": fold.ordered_tone_frequencies_hz,
            "ordered_tone_source_indices": fold.ordered_tone_source_indices,
            "selected_subset_sha256": fold.selected_subset_sha256,
            "candidate_universe_sha256": fold.candidate_universe_sha256,
            "p9a_selection_scope_sha256": fold.p9a_selection_scope_sha256,
            "p9a_selection_artifact_sha256": fold.p9a_selection_artifact_sha256,
            "p9a_manifest_sha256": fold.p9a_manifest_sha256,
            "p9b_result_sha256": fold.p9b_result_sha256,
            "p9b_manifest_sha256": fold.p9b_manifest_sha256,
            "p2b_result_sha256": fold.p2b_result_sha256,
            "p4b_result_sha256": fold.p4b_result_sha256,
        })
    fold_path = output / "fold_assignments.csv"
    authority_path = output / "tone_authority_audit.csv"
    _write_csv(fold_path, fold_rows, tuple(fold_rows[0]) if fold_rows else ("outer_fold_id",))
    _write_csv(authority_path, tone_authority_rows, tuple(tone_authority_rows[0]) if tone_authority_rows else ("outer_fold_id",))
    paths.extend((fold_path, authority_path))

    tone_rows = [item.to_dict() for item in sorted(
        result.tone_comparisons,
        key=lambda item: (item.outer_fold_id, item.method, item.frequency_hz),
    )]
    raw_fields = (
        "schema_version", "outer_fold_id", "tone_id", "frequency_hz", "method",
        "evaluation_pair_ids", "pair_count", "valid_count", "missing_count",
        "raw_mean_bias_db", "raw_median_bias_db", "raw_bias_std_db",
        "raw_pearson_correlation", "raw_rms_difference_db", "raw_mae_db",
        "raw_maximum_absolute_difference_db", "reason_codes",
    )
    raw_path = output / "uncalibrated_tone_comparison.csv"
    held_path = output / "heldout_tone_comparison.csv"
    _write_csv(raw_path, tone_rows, raw_fields)
    _write_csv(held_path, tone_rows, tuple(tone_rows[0]) if tone_rows else raw_fields)
    paths.extend((raw_path, held_path))

    parameter_rows = []
    diagnostic_rows = []
    model_entries = []
    for model in sorted(result.calibration_models, key=lambda item: (item.outer_fold_id, item.method)):
        safe_method = model.method.replace("/", "_")
        model_path = output / "calibration_models" / model.outer_fold_id / f"{safe_method}.json"
        _write_json(model_path, model.to_dict())
        paths.append(model_path)
        model_entries.append({
            "outer_fold_id": model.outer_fold_id,
            "method": model.method,
            "model_id": model.model_id,
            "model_semantic_sha256": model.sha256,
            "model_path": model_path.relative_to(output).as_posix(),
            "model_file_sha256": artifact_sha256(model_path),
            "model": model.to_dict(),
        })
        for fit in model.tone_fits:
            base = {
                "model_id": model.model_id,
                "outer_fold_id": model.outer_fold_id,
                "method": model.method,
                **fit.to_dict(),
            }
            parameter_rows.append(base)
            diagnostic_rows.append({
                "model_id": model.model_id,
                "outer_fold_id": model.outer_fold_id,
                "method": model.method,
                "tone_id": fit.tone_id,
                "frequency_hz": fit.frequency_hz,
                "status": fit.status.value,
                "training_pair_count": fit.training_pair_count,
                "input_variance_db2": fit.input_variance_db2,
                "training_residual_rms_db": fit.training_residual_rms_db,
                "training_residual_mae_db": fit.training_residual_mae_db,
                "uncertainty_status": fit.uncertainty_status,
                "reason_codes": fit.reason_codes,
            })
    parameters_path = output / "calibration_parameters.csv"
    diagnostics_path = output / "calibration_fit_diagnostics.csv"
    _write_csv(parameters_path, parameter_rows, tuple(parameter_rows[0]) if parameter_rows else ("model_id",))
    _write_csv(diagnostics_path, diagnostic_rows, tuple(diagnostic_rows[0]) if diagnostic_rows else ("model_id",))
    paths.extend((parameters_path, diagnostics_path))

    model_registry = {
        "schema_version": "1.0.0",
        "analysis_scope_id": scope.analysis_scope_id,
        "analysis_scope_sha256": scope.sha256,
        "calibration_lifecycle": "software_validation_only",
        "approval_status": "not_approved",
        "scientifically_eligible": False,
        "deployment_eligible": False,
        "models": model_entries,
    }
    model_registry["registry_semantic_sha256"] = _canonical_sha256(model_registry)
    model_registry_path = output / "calibration_model.json"
    _write_json(model_registry_path, model_registry)
    model_sidecar = output / "calibration_model.sha256"
    model_sidecar.write_text(
        artifact_sha256(model_registry_path) + "  calibration_model.json\n", encoding="utf-8"
    )
    paths.extend((model_registry_path, model_sidecar))

    template_rows = [item.to_dict() for item in sorted(
        result.direction_template_comparisons,
        key=lambda item: (item.outer_fold_id, item.method, item.direction_deg),
    )]
    template_path = output / "direction_template_consistency.csv"
    _write_csv(template_path, template_rows, tuple(template_rows[0]) if template_rows else ("outer_fold_id",))
    paths.append(template_path)

    prediction_rows = [item.to_dict() for item in sorted(
        result.predictions,
        key=lambda item: (item.outer_fold_id, item.method, item.protocol, item.model_id, item.pair_id),
    )]
    prediction_path = output / "cross_mode_predictions.csv"
    _write_csv(prediction_path, prediction_rows, tuple(prediction_rows[0]) if prediction_rows else ("outer_fold_id",))
    paths.append(prediction_path)

    metric_rows = [
        {"record_type": "classification", **item.to_dict()}
        for item in result.classification_metrics
    ] + [
        {"record_type": "fold_comparison", **item.to_dict()}
        for item in result.fold_evaluations
    ]
    metric_fields = tuple(dict.fromkeys(field for row in metric_rows for field in row))
    metric_path = output / "cross_mode_fold_metrics.csv"
    _write_csv(metric_path, metric_rows, metric_fields or ("record_type",))
    paths.append(metric_path)

    summary = {
        "schema_version": "1.0.0",
        "processing_status": result.processing_status,
        "result_semantic_sha256": result.sha256,
        "matched_pair_count": len(scope.pairs),
        "outer_fold_count": len(scope.outer_folds),
        "model_count": len(result.calibration_models),
        "mean_raw_rms_db": _mean(item.raw_rms_difference_db for item in result.fold_evaluations),
        "mean_calibrated_rms_db": _mean(item.calibrated_rms_difference_db for item in result.fold_evaluations),
        "mean_raw_template_correlation": _mean(item.raw_correlation for item in result.direction_template_comparisons),
        "mean_calibrated_template_correlation": _mean(item.calibrated_correlation for item in result.direction_template_comparisons),
        "sealed_final_test_sample_ids": list(scope.sealed_final_test_sample_ids),
        "sealed_final_test_sha256": scope.sealed_final_test_sha256,
        "scientifically_eligible": False,
        "deployment_eligible": False,
        "canonical_analysis": False,
        "final_test_read": False,
    }
    summary_path = output / "cross_mode_summary.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)

    result_payload = result.to_dict()
    result_payload["result_semantic_sha256"] = result.sha256
    result_path = output / "bridge_result.json"
    _write_json(result_path, result_payload)
    paths.append(result_path)

    artifact_hashes = {
        path.relative_to(output).as_posix(): artifact_sha256(path)
        for path in sorted(paths, key=lambda item: item.as_posix())
    }
    manifest = {
        "schema_version": BRIDGE_MANIFEST_SCHEMA_VERSION,
        **SCHEMA_VERSION_QUARTET,
        "analysis_scope_id": scope.analysis_scope_id,
        "analysis_scope_sha256": scope.sha256,
        "result_sha256": result.sha256,
        "config_sha256": result.config_sha256,
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "random_state": scope.random_state,
        "data_origin": "simulated",
        "source_type": "simulated",
        "run_purpose": "software_validation",
        "purpose": "software_validation",
        "calibration_lifecycle": "software_validation_only",
        "approval_status": "not_approved",
        "scientifically_eligible": False,
        "deployment_eligible": False,
        "canonical_analysis": False,
        "final_test_read": False,
        "sealed_final_test_sample_ids": list(scope.sealed_final_test_sample_ids),
        "sealed_final_test_sha256": scope.sealed_final_test_sha256,
        "input_file_hashes": dict(sorted(input_file_hashes.items())),
        "model_registry_file_sha256": artifact_sha256(model_registry_path),
        "model_semantic_hashes": {
            f"{item.outer_fold_id}/{item.method}": item.sha256
            for item in result.calibration_models
        },
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
    }
    manifest["manifest_content_sha256"] = _canonical_sha256(manifest)
    manifest_path = output / "bridge_manifest.json"
    _write_json(manifest_path, manifest)
    sidecar = output / "bridge_manifest.sha256"
    sidecar.write_text(
        artifact_sha256(manifest_path) + "  bridge_manifest.json\n", encoding="utf-8"
    )
    paths.extend((manifest_path, sidecar))
    return tuple(paths)


def load_cross_mode_bridge_bundle(output_directory: str | Path) -> dict[str, Any]:
    """Verify manifest, artifacts, scope, result and every standalone model."""
    output = Path(output_directory)
    manifest_path = output / "bridge_manifest.json"
    expected_file = (output / "bridge_manifest.sha256").read_text(encoding="utf-8").split()[0]
    if artifact_sha256(manifest_path) != expected_file:
        raise ValueError("cross-mode bridge manifest file hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    semantic = dict(manifest)
    expected_content = semantic.pop("manifest_content_sha256")
    if _canonical_sha256(semantic) != expected_content:
        raise ValueError("cross-mode bridge manifest content hash mismatch")
    for relative, digest in manifest["artifact_hashes"].items():
        if artifact_sha256(output / relative) != digest:
            raise ValueError(f"cross-mode bridge artifact hash mismatch: {relative}")
    scope = P9CrossModeBridgeScope.from_dict(
        json.loads((output / "bridge_scope.json").read_text(encoding="utf-8"))
    )
    if scope.sha256 != manifest["analysis_scope_sha256"]:
        raise ValueError("cross-mode bridge scope hash mismatch")
    result = json.loads((output / "bridge_result.json").read_text(encoding="utf-8"))
    result_semantic = dict(result)
    expected_result = result_semantic.pop("result_semantic_sha256")
    if (
        _canonical_sha256(result_semantic) != expected_result
        or expected_result != manifest["result_sha256"]
    ):
        raise ValueError("cross-mode bridge result hash mismatch")
    registry_path = output / "calibration_model.json"
    sidecar_digest = (output / "calibration_model.sha256").read_text(encoding="utf-8").split()[0]
    if artifact_sha256(registry_path) != sidecar_digest:
        raise ValueError("calibration model registry hash mismatch")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_semantic = dict(registry)
    expected_registry = registry_semantic.pop("registry_semantic_sha256")
    if _canonical_sha256(registry_semantic) != expected_registry:
        raise ValueError("calibration model registry semantic hash mismatch")
    models: list[CrossModeCalibrationModel] = []
    for entry in registry["models"]:
        model_path = output / entry["model_path"]
        if artifact_sha256(model_path) != entry["model_file_sha256"]:
            raise ValueError("standalone calibration model file hash mismatch")
        model = CrossModeCalibrationModel.from_dict(
            json.loads(model_path.read_text(encoding="utf-8"))
        )
        if model.sha256 != entry["model_semantic_sha256"]:
            raise ValueError("standalone calibration model semantic hash mismatch")
        models.append(model)
    return {
        "manifest": manifest,
        "scope": scope,
        "result": result,
        "models": tuple(models),
        "input_manifest": json.loads((output / "input_manifest.json").read_text(encoding="utf-8")),
    }

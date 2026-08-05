"""Stable P4-B CSV/JSON views and an auditable artifact manifest."""

from __future__ import annotations

import csv
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .comparison_metrics import ComparisonAnalysisScope, ComparisonMetricsResult
from .schemas import artifact_sha256
from .version import SCHEMA_VERSION_QUARTET


COMPARISON_METRICS_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        _jsonable(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def comparison_metrics_result_payload(
    result: ComparisonMetricsResult,
    scope: ComparisonAnalysisScope,
) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "result_sha256": _canonical_sha256(result),
        "scope": scope.to_dict(),
        "result": _jsonable(result),
    }


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value)


def _csv_text(rows: Sequence[Mapping[str, Any]], fallback: Sequence[str]) -> str:
    fieldnames = tuple(rows[0]) if rows else tuple(fallback)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _cell(row.get(name)) for name in fieldnames})
    return stream.getvalue()


def _without(mapping: Mapping[str, Any], *names: str) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if key not in names}


def _views(
    result: ComparisonMetricsResult,
    scope: ComparisonAnalysisScope,
) -> dict[str, tuple[list[dict[str, Any]], tuple[str, ...]]]:
    band_rows = [_without(_jsonable(item), "direction_pairs") for item in result.band_metrics]
    direction_rows: list[dict[str, Any]] = []
    for band in result.band_metrics:
        for pair in band.direction_pairs:
            direction_rows.append(_jsonable(pair))
    configuration_rows = [_jsonable(item) for item in result.configuration_comparisons]
    morphology_rows = [
        item for item in configuration_rows if item["metric_id"] == "morphology_gain"
    ]
    pair_audit = [
        {
            **pair.to_dict(),
            "audit_status": "accepted",
            "state_contract": "explicit_physical_state_and_acquisition_metadata",
        }
        for pair in scope.cross_mode_pairs
    ]
    cross = result.cross_mode_metrics
    cross_pairs = [] if cross is None else [_jsonable(item) for item in cross.pairs]
    cross_summary = (
        []
        if cross is None
        else [
            {
                "tone_set_id": cross.tone_set_id,
                "tone_set_sha256": cross.tone_set_sha256,
                "tone_schema_id": cross.tone_schema_id,
                "total_tone_count": cross.total_tone_count,
                "common_tone_count": cross.common_tone_count,
                "missing_tone_count": cross.missing_tone_count,
                "pair_count": len(cross.pairs),
                "common_valid_mask": cross.common_valid_mask.tolist(),
            }
        ]
    )
    tone_bias = [] if cross is None else [_jsonable(item) for item in cross.per_tone_bias]
    reliability_rows: list[dict[str, Any]] = []
    reliability = result.tone_reliability
    if reliability is not None:
        for index, frequency in enumerate(reliability.frequencies_hz):
            reliability_rows.append(
                {
                    "tone_index": index,
                    "frequency_hz": float(frequency),
                    "available": bool(reliability.available_mask[index]),
                    "stability_db": float(reliability.stability_db[index]) if reliability.available_mask[index] else None,
                    "raw_weight": float(reliability.raw_weights[index]) if reliability.available_mask[index] else None,
                    "clipped_weight": float(reliability.clipped_weights[index]) if reliability.available_mask[index] else None,
                    "normalized_weight": float(reliability.normalized_weights[index]) if reliability.available_mask[index] else None,
                    "pair_count": int(reliability.pair_counts[index]),
                    "pair_ids": reliability.pair_ids_by_tone[index],
                    "repeat_type": reliability.repeat_type,
                    "source_roles": tuple(item.value for item in reliability.source_roles),
                    "floor_db": reliability.floor_db,
                    "maximum_raw_weight": reliability.maximum_raw_weight,
                    "normalization": reliability.normalization,
                    "result_available": reliability.available,
                    "unavailable_reason": reliability.unavailable_reason,
                }
            )
    weighted_rows = [_jsonable(item) for item in result.weighted_metrics]
    rank_rows = [
        {
            "band_id": item.band_id,
            "configuration_id": item.configuration_id,
            "feature_kind": item.feature_kind,
            "preprocessing_id": item.preprocessing_id,
            "effective_rank": item.effective_rank,
            "available": item.available,
            "unavailable_reason": item.unavailable_reason,
            "feature_count": item.feature_count,
        }
        for item in result.band_metrics
        if item.feature_kind in {
            "tone_projection_from_sweep", "tone_measurement_from_multisine"
        }
    ]
    status_rows = [
        {
            "schema_version": result.schema_version,
            "processing_status": result.processing_status,
            "analysis_scope_id": result.analysis_scope_id,
            "comparison_scope_sha256": result.comparison_scope_sha256,
            "analysis_tier": result.analysis_tier,
            "dataset_qc_link_status": result.dataset_qc_link_status,
            "p2b_canonical_ready": result.p2b_canonical_ready,
            "canonical_analysis": result.canonical_analysis,
            "data_origin": result.data_origin,
            "run_purpose": result.run_purpose,
            "scientifically_eligible": result.scientifically_eligible,
            "failures": result.failures,
            "warnings": result.warnings,
        }
    ]
    return {
        "band_metrics.csv": (band_rows, ("band_id", "available", "unavailable_reason")),
        "band_direction_pairs.csv": (direction_rows, ("band_id", "configuration_id", "feature_kind")),
        "configuration_comparison.csv": (configuration_rows, ("band_id", "feature_kind", "metric_id")),
        "morphology_gain_comparison.csv": (morphology_rows, ("band_id", "feature_kind", "metric_id")),
        "matched_pair_audit.csv": (pair_audit, ("match_pair_id", "audit_status")),
        "cross_mode_pair_metrics.csv": (cross_pairs, ("match_pair_id", "common_tone_count")),
        "cross_mode_summary.csv": (cross_summary, ("tone_set_id", "pair_count")),
        "per_tone_bias.csv": (tone_bias, ("tone_index", "frequency_hz", "absolute_comparison_status")),
        "tone_reliability.csv": (reliability_rows, ("tone_index", "frequency_hz", "available")),
        "weighted_metrics.csv": (weighted_rows, ("match_pair_id", "available")),
        "matched_effective_rank.csv": (rank_rows, ("band_id", "configuration_id", "feature_kind")),
        "comparison_status.csv": (status_rows, tuple(status_rows[0])),
    }


def write_comparison_metrics_outputs(
    result: ComparisonMetricsResult,
    scope: ComparisonAnalysisScope,
    output_directory: str | Path,
    *,
    comparison_config: Mapping[str, Any],
    input_artifacts: Sequence[Mapping[str, Any]],
    git_commit: str,
    random_state: int,
    created_at_utc: str | None = None,
) -> dict[str, Path]:
    """Write one immutable P4-B bundle; the directory must not exist."""
    output = Path(output_directory)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(f"comparison output directory already exists: {output}") from exc
    written: dict[str, Path] = {}
    artifact_paths: list[Path] = []
    for name, (rows, fallback) in _views(result, scope).items():
        path = output / name
        path.write_text(_csv_text(rows, fallback), encoding="utf-8", newline="")
        written[name] = path
        artifact_paths.append(path)
    result_path = output / "comparison_metrics.json"
    result_path.write_text(
        json.dumps(
            comparison_metrics_result_payload(result, scope),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    written[result_path.name] = result_path
    artifact_paths.append(result_path)
    created = created_at_utc or datetime.now(UTC).isoformat()
    manifest = {
        "schema_version": COMPARISON_METRICS_MANIFEST_SCHEMA_VERSION,
        "processing_status": result.processing_status,
        "success": result.processing_status == "completed",
        "analysis_scope_id": result.analysis_scope_id,
        "comparison_scope_sha256": scope.sha256,
        "result_sha256": _canonical_sha256(result),
        "schema_versions": SCHEMA_VERSION_QUARTET,
        "comparison_config": _jsonable(comparison_config),
        "comparison_config_sha256": _canonical_sha256(comparison_config),
        "git_commit": git_commit,
        "random_state": random_state,
        "created_at_utc": created,
        "analysis_tier": result.analysis_tier,
        "dataset_qc": {
            "link_status": result.dataset_qc_link_status,
            "canonical_ready": result.p2b_canonical_ready,
            "canonical_analysis": result.canonical_analysis,
        },
        "provenance": {
            "data_origin": result.data_origin,
            "run_purpose": result.run_purpose,
            "scientifically_eligible": result.scientifically_eligible,
        },
        "inputs": sorted(
            [_jsonable(dict(item)) for item in input_artifacts],
            key=lambda item: (str(item.get("artifact_id", "")), str(item.get("artifact_role", ""))),
        ),
        "artifacts": [
            {
                "path": path.name,
                "sha256": artifact_sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(artifact_paths, key=lambda item: item.name)
        ],
    }
    manifest["manifest_payload_sha256"] = _canonical_sha256(manifest)
    manifest_path = output / "metrics_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_hash = output / "metrics_manifest.sha256"
    manifest_hash.write_text(artifact_sha256(manifest_path) + "\n", encoding="ascii")
    written[manifest_path.name] = manifest_path
    written[manifest_hash.name] = manifest_hash
    return written


def load_comparison_metrics_bundle(output_directory: str | Path) -> dict[str, Any]:
    """Load and cryptographically verify a previously written P4-B bundle."""
    output = Path(output_directory)
    manifest_path = output / "metrics_manifest.json"
    expected_manifest = (output / "metrics_manifest.sha256").read_text(
        encoding="ascii"
    ).strip()
    if artifact_sha256(manifest_path) != expected_manifest:
        raise ValueError("comparison metrics manifest hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        path = output / item["path"]
        if artifact_sha256(path) != item["sha256"]:
            raise ValueError(f"comparison artifact hash mismatch: {path}")
    payload = json.loads((output / "comparison_metrics.json").read_text(encoding="utf-8"))
    if payload["result_sha256"] != manifest["result_sha256"]:
        raise ValueError("comparison result hash mismatch")
    return {"manifest": manifest, **payload}

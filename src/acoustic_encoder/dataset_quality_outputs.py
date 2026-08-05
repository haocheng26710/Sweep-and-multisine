"""Stable CSV/JSON/manifest outputs for the typed P2-B dataset result."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
import io
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .dataset_quality_control import (
    DATASET_QC_SCHEMA_VERSION,
    DatasetQCScope,
    DatasetQCResult,
    dataset_qc_sha256,
)
from .schemas import artifact_sha256
from .version import SCHEMA_VERSION_QUARTET


DATASET_QC_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return str(value)


def _csv_text(fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> str:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(
        handle,
        fieldnames=list(fieldnames),
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({name: _json_cell(row.get(name)) for name in fieldnames})
    return handle.getvalue()


def _views(
    result: DatasetQCResult,
    scope: DatasetQCScope,
) -> dict[str, tuple[tuple[str, ...], list[dict[str, Any]]]]:
    common = {
        "analysis_scope_id": result.analysis_scope_id,
        "data_origin": result.data_origin.value,
        "dataset_role": result.dataset_role.value,
        "run_purpose": result.run_purpose.value,
    }
    summary_rows = [
        {
            **common,
            "dataset_qc_schema_version": result.schema_version,
            "scope_sha256": result.scope_sha256,
            "config_sha256": result.config_sha256,
            "dataset_qc_result_sha256": dataset_qc_sha256(result),
            "aggregate_status": result.aggregate_status.value,
            "canonical_ready": result.canonical_ready,
            "canonical_ready_reasons": result.canonical_ready_reasons,
            "measurement_count": len(result.scoped_sample_ids),
            "condition_count": len(result.condition_results),
            "outlier_check_count": len(result.outlier_results),
            "repeatability_group_count": len(result.repeatability_results),
            "scientifically_eligible": result.scientifically_eligible,
            "scientific_use": (
                "eligible_real_experiment_research_analysis"
                if result.scientifically_eligible
                and result.run_purpose.value == "research_analysis"
                else f"prohibited_{result.data_origin.value}_{result.run_purpose.value}"
            ),
        }
    ]

    expected_by_id = {item.condition_id: item for item in scope.expected_conditions}
    condition_rows: list[dict[str, Any]] = []
    for item in sorted(result.condition_results, key=lambda row: row.condition_id):
        expected = expected_by_id.get(item.condition_id)
        condition_rows.append(
            {
                **common,
                "condition_id": item.condition_id,
                "cohort_role": item.cohort_role.value,
                "measurement_mode": None if expected is None else expected.measurement_mode.value,
                "configuration_id": None if expected is None else expected.configuration_id,
                "direction_id": None if expected is None else expected.direction_id,
                "direction_angle_deg": None if expected is None else expected.direction_angle_deg,
                "session_id": None if expected is None else expected.session_id,
                "repeat_type": None if expected is None else expected.repeat_type,
                "reposition_round_id": None if expected is None else expected.reposition_round_id,
                "assembly_id": None if expected is None else expected.assembly_id,
                "acquisition_block_id": None if expected is None else expected.acquisition_block_id,
                "expected_count": item.expected_count,
                "observed_count": item.observed_count,
                "valid_count": item.valid_count,
                "warning_count": item.warning_count,
                "exclude_candidate_count": item.exclude_candidate_count,
                "missing_count": item.missing_count,
                "duplicate_count": item.duplicate_count,
                "unexpected_count": item.unexpected_count,
                "completeness_status": item.status.value,
                "reason_codes": item.reason_codes,
                "observed_sample_ids": item.observed_sample_ids,
                "unexpected_sample_ids": item.unexpected_sample_ids,
            }
        )

    outlier_rows = [
        {
            **common,
            **item.to_dict(),
        }
        for item in sorted(result.outlier_results, key=lambda row: row.sample_id)
    ]

    repeat_rows: list[dict[str, Any]] = []
    for group in sorted(
        result.repeatability_results,
        key=lambda row: (row.cohort_role.value, row.repeat_type, row.group_id),
    ):
        group_values = {
            **common,
            "group_id": group.group_id,
            "cohort_role": group.cohort_role.value,
            "repeat_type": group.repeat_type,
            "group_sample_ids": group.sample_ids,
            "group_sample_count": group.sample_count,
            "candidate_pair_count": group.candidate_pair_count,
            "qualified_pair_count": group.qualified_pair_count,
            "warning_threshold": group.warning_threshold,
            "exclude_candidate_threshold": group.exclude_candidate_threshold,
            "units": group.units,
            "group_status": group.status.value,
            "group_reason_codes": group.reason_codes,
            "median_distance": group.median_distance,
            "mean_distance": group.mean_distance,
            "sample_std_distance": group.sample_std_distance,
            "iqr_distance": group.iqr_distance,
            "minimum_distance": group.minimum_distance,
            "maximum_distance": group.maximum_distance,
        }
        pair_rows = group.pairs or (None,)
        for pair in pair_rows:
            repeat_rows.append(
                {
                    **group_values,
                    "pair_id": None if pair is None else pair.pair_id,
                    "left_sample_id": None if pair is None else pair.left_sample_id,
                    "right_sample_id": None if pair is None else pair.right_sample_id,
                    "pair_qualified": None if pair is None else pair.qualified,
                    "pair_available": None if pair is None else pair.available,
                    "pair_distance": None if pair is None else pair.distance,
                    "pair_status": None if pair is None else pair.status.value,
                    "pair_reason_code": None if pair is None else pair.reason_code,
                    "common_valid_feature_count": (
                        None if pair is None else pair.common_valid_feature_count
                    ),
                }
            )

    rollup_rows = [
        {**common, **item.to_dict()}
        for item in sorted(result.measurement_rollups, key=lambda row: row.sample_id)
    ]

    review_rows: list[dict[str, Any]] = []
    represented: set[tuple[str, str]] = set()
    for review in sorted(result.manual_review_records, key=lambda row: row.review_id):
        for sample_id in review.sample_ids:
            represented.add((sample_id, review.reason_code))
        review_rows.append(
            {
                **common,
                **review.to_dict(),
            }
        )
    for rollup in sorted(result.measurement_rollups, key=lambda row: row.sample_id):
        for reason in rollup.manual_review_reasons:
            if (rollup.sample_id, reason) in represented:
                continue
            review_rows.append(
                {
                    **common,
                    "review_id": f"inherited:{rollup.sample_id}:{reason}",
                    "sample_ids": (rollup.sample_id,),
                    "reason_code": reason,
                    "status": "pending",
                    "reviewer": None,
                    "reviewed_at_utc": None,
                    "decision": None,
                    "notes": "inherited from MeasurementMeta/P2-A",
                }
            )
    review_rows.sort(key=lambda row: str(row["review_id"]))

    views = {
        "dataset_qc_summary.csv": summary_rows,
        "condition_completeness.csv": condition_rows,
        "same_condition_outliers.csv": outlier_rows,
        "repeatability_qc.csv": repeat_rows,
        "measurement_qc_rollup.csv": rollup_rows,
        "manual_review_queue.csv": review_rows,
    }
    return {
        name: (tuple(rows[0]) if rows else _empty_view_fields(name), rows)
        for name, rows in views.items()
    }


def _empty_view_fields(name: str) -> tuple[str, ...]:
    common = ("analysis_scope_id", "data_origin", "dataset_role", "run_purpose")
    fields = {
        "same_condition_outliers.csv": common
        + (
            "sample_id", "group_id", "cohort_role", "reference_role",
            "feature_contract_sha256", "available", "status", "reason_code",
            "distance", "reference_distance_center", "reference_scale", "robust_z",
            "reference_sample_count", "common_valid_feature_count",
            "reference_sample_ids", "warning_threshold", "exclude_candidate_threshold",
        ),
        "repeatability_qc.csv": common
        + (
            "group_id", "cohort_role", "repeat_type", "group_sample_ids",
            "group_sample_count", "candidate_pair_count", "qualified_pair_count",
            "warning_threshold", "exclude_candidate_threshold", "units", "group_status",
            "group_reason_codes", "median_distance", "mean_distance",
            "sample_std_distance", "iqr_distance", "minimum_distance", "maximum_distance",
            "pair_id", "left_sample_id", "right_sample_id", "pair_qualified",
            "pair_available", "pair_distance", "pair_status", "pair_reason_code",
            "common_valid_feature_count",
        ),
        "manual_review_queue.csv": common
        + (
            "review_id", "sample_ids", "reason_code", "status", "reviewer",
            "reviewed_at_utc", "decision", "notes",
        ),
    }
    return fields[name]


def _verified_inputs(records: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    verified: list[dict[str, str]] = []
    for item in records:
        required = {"sample_id", "artifact_role", "path", "sha256"}
        if set(item) != required:
            raise ValueError("input artifact records require sample_id, artifact_role, path, sha256")
        path = Path(str(item["path"]))
        if not path.is_file():
            raise FileNotFoundError(f"explicit dataset QC input is missing: {path}")
        actual = artifact_sha256(path)
        if actual != str(item["sha256"]):
            raise ValueError(f"explicit dataset QC input hash mismatch: {path}")
        verified.append(
            {
                "sample_id": str(item["sample_id"]),
                "artifact_role": str(item["artifact_role"]),
                "path": path.resolve().as_posix(),
                "sha256": actual,
            }
        )
    return sorted(
        verified,
        key=lambda row: (row["sample_id"], row["artifact_role"], row["path"]),
    )


def write_dataset_quality_outputs(
    result: DatasetQCResult,
    scope: DatasetQCScope,
    dataset_quality_config: Mapping[str, Any],
    output_directory: str | Path,
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    git_commit: str,
    random_state: int,
    created_at_utc: str | None = None,
) -> dict[str, Path]:
    """Write one immutable P2-B bundle and refuse an existing directory."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"Dataset QC output directory already exists: {output}")
    if result.analysis_scope_id != scope.analysis_scope_id or result.scope_sha256 != scope.sha256:
        raise ValueError("DatasetQCResult does not correspond to DatasetQCScope")
    if result.config_sha256 != _config_sha256(dataset_quality_config):
        raise ValueError("DatasetQCResult does not correspond to dataset QC config")
    verified_inputs = _verified_inputs(input_artifacts)
    output.mkdir(parents=True, exist_ok=False)

    paths: dict[str, Path] = {}
    for name, (fieldnames, rows) in _views(result, scope).items():
        path = output / name
        path.write_text(_csv_text(fieldnames, rows), encoding="utf-8", newline="")
        paths[name] = path
    result_path = output / "dataset_qc.json"
    result_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths[result_path.name] = result_path

    artifact_records = [
        {
            "path": path.name,
            "sha256": artifact_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(paths.values(), key=lambda item: item.name)
    ]
    manifest = {
        "schema_version": DATASET_QC_MANIFEST_SCHEMA_VERSION,
        "dataset_qc_schema_version": DATASET_QC_SCHEMA_VERSION,
        "created_at_utc": created_at_utc or datetime.now(UTC).isoformat(),
        "versions": dict(SCHEMA_VERSION_QUARTET),
        "git_commit": git_commit,
        "random_state": random_state,
        "analysis_scope_id": result.analysis_scope_id,
        "scope_sha256": result.scope_sha256,
        "scope": scope.to_dict(),
        "dataset_quality_config": dict(dataset_quality_config),
        "config_sha256": result.config_sha256,
        "dataset_qc_result_sha256": dataset_qc_sha256(result),
        "processing_status": "completed",
        "aggregate_status": result.aggregate_status.value,
        "canonical_ready": result.canonical_ready,
        "canonical_ready_reasons": list(result.canonical_ready_reasons),
        "provenance": {
            "data_origin": result.data_origin.value,
            "dataset_role": result.dataset_role.value,
            "run_purpose": result.run_purpose.value,
            "scientifically_eligible": result.scientifically_eligible,
        },
        "inputs": verified_inputs,
        "artifacts": artifact_records,
    }
    manifest_path = output / "dataset_qc_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths[manifest_path.name] = manifest_path
    digest_path = output / "dataset_qc_manifest.sha256"
    digest_path.write_text(
        f"{artifact_sha256(manifest_path)}  {manifest_path.name}\n",
        encoding="ascii",
    )
    paths[digest_path.name] = digest_path
    return paths


def _config_sha256(config: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(config),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    import hashlib

    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def load_dataset_quality_bundle(output_directory: str | Path) -> DatasetQCResult:
    """Load the authoritative JSON and verify every CSV and declared hash."""
    output = Path(output_directory)
    manifest_path = output / "dataset_qc_manifest.json"
    digest_tokens = (output / "dataset_qc_manifest.sha256").read_text(
        encoding="ascii"
    ).split()
    if len(digest_tokens) != 2 or digest_tokens[0] != artifact_sha256(manifest_path):
        raise ValueError("dataset QC manifest SHA-256 mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != DATASET_QC_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported dataset QC manifest schema")
    for artifact in manifest["artifacts"]:
        path = output / artifact["path"]
        if artifact_sha256(path) != artifact["sha256"]:
            raise ValueError(f"dataset QC artifact hash mismatch: {path.name}")
    result = DatasetQCResult.from_dict(
        json.loads((output / "dataset_qc.json").read_text(encoding="utf-8"))
    )
    scope = DatasetQCScope.from_dict(manifest["scope"])
    if dataset_qc_sha256(result) != manifest["dataset_qc_result_sha256"]:
        raise ValueError("dataset QC result hash mismatch")
    if result.scope_sha256 != scope.sha256:
        raise ValueError("dataset QC scope hash mismatch")
    for name, (fieldnames, rows) in _views(result, scope).items():
        expected = _csv_text(fieldnames, rows)
        actual = (output / name).read_text(encoding="utf-8")
        if actual != expected:
            raise ValueError(f"dataset QC CSV/JSON consistency mismatch: {name}")
    return result

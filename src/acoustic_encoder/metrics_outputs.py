"""Immutable CSV/JSON views for one P4-A DirectionMetricsResult."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .metrics import DirectionMetricsResult, MetricMatrix, PairDistanceRecord
from .schemas import artifact_sha256


METRICS_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        return "" if not np.isfinite(value) else format(float(value), ".17g")
    if isinstance(value, (bool, np.bool_)):
        return str(bool(value)).lower()
    return value


def _json_cell(values: Iterable[Any]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _write_csv(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    fieldnames: tuple[str, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _cell(row.get(name)) for name in fieldnames})


def _matrix_rows(matrix: MetricMatrix) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index, row_angle in enumerate(matrix.angles_deg):
        for column_index, column_angle in enumerate(matrix.angles_deg):
            rows.append(
                {
                    "row_direction_index": row_index,
                    "row_angle_deg": row_angle,
                    "column_direction_index": column_index,
                    "column_angle_deg": column_angle,
                    "value": (
                        float(matrix.values[row_index, column_index])
                        if matrix.available[row_index, column_index]
                        else None
                    ),
                    "available": bool(matrix.available[row_index, column_index]),
                    "unavailable_reason": matrix.unavailable_reasons[row_index][
                        column_index
                    ],
                    "feature_count": matrix.feature_count,
                }
            )
    return rows


def _pair_rows(pairs: Iterable[PairDistanceRecord]) -> list[dict[str, Any]]:
    return [
        {
            "pair_id": pair.pair_id,
            "pair_scope": pair.pair_scope,
            "repeat_type": pair.repeat_type,
            "left_sample_id": pair.left_sample_id,
            "right_sample_id": pair.right_sample_id,
            "left_angle_deg": pair.left_angle_deg,
            "right_angle_deg": pair.right_angle_deg,
            "constructed": pair.constructed,
            "unavailable_reason": pair.unavailable_reason,
            "feature_count": pair.feature_count,
            "euclidean_distance": pair.distances.get("euclidean"),
            "rms_distance": pair.distances.get("rms"),
            "median_absolute_difference": pair.distances.get(
                "median_absolute_difference"
            ),
            "left_session_id": pair.left_session_id,
            "right_session_id": pair.right_session_id,
            "left_reposition_round_id": pair.left_reposition_round_id,
            "right_reposition_round_id": pair.right_reposition_round_id,
            "left_assembly_id": pair.left_assembly_id,
            "right_assembly_id": pair.right_assembly_id,
            "left_acquisition_block_id": pair.left_acquisition_block_id,
            "right_acquisition_block_id": pair.right_acquisition_block_id,
        }
        for pair in pairs
    ]


def _artifact(path: Path, root: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": artifact_sha256(path),
    }


def _scope_payload(result: DirectionMetricsResult) -> dict[str, Any]:
    scope = result.analysis_scope
    if scope.included_sample_ids is not None:
        selector = {
            "kind": "explicit_sample_ids",
            "included_sample_ids": list(scope.included_sample_ids),
        }
    else:
        assert scope.partition is not None
        selector = {
            "kind": "frozen_partition",
            "partition_id": scope.partition.partition_id,
            "sample_ids": list(scope.partition.sample_ids),
            "partition_sha256": scope.partition.partition_sha256,
        }
    return {
        "schema_version": scope.schema_version,
        "analysis_scope_id": scope.analysis_scope_id,
        "run_purpose": scope.run_purpose.value,
        "scope_role": scope.scope_role.value,
        "selector": selector,
        "direction_order_deg": list(scope.direction_order_deg),
        "selection_policy": {
            "policy_id": scope.selection_policy.policy_id,
            "require_human_valid": scope.selection_policy.require_human_valid,
            "exclude_manual_review": scope.selection_policy.exclude_manual_review,
        },
        "qc_inclusion_policy": {
            "policy_id": scope.qc_inclusion_policy.policy_id,
            "included_statuses": [
                status.value for status in scope.qc_inclusion_policy.included_statuses
            ],
            "missing_status": scope.qc_inclusion_policy.missing_status,
            "allow_exclude_candidate": (
                scope.qc_inclusion_policy.allow_exclude_candidate
            ),
        },
    }


def write_direction_metrics_outputs(
    result: DirectionMetricsResult,
    output_directory: str | Path,
) -> dict[str, Path]:
    """Write one complete P4-A view bundle and refuse any existing directory."""
    output = Path(output_directory)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(f"metrics output directory already exists: {output}") from exc

    written: dict[str, Path] = {}
    artifacts: list[Path] = []

    direction_statistics = output / "direction_statistics.csv"
    _write_csv(
        direction_statistics,
        (
            {
                "direction_index": template.direction_index,
                "angle_deg": template.angle_deg,
                "sample_count": template.sample_count,
                "sample_ids": _json_cell(template.sample_ids),
                "standard_deviation_available": (
                    template.standard_deviation_available
                ),
                "session_count": template.session_count,
                "repeat_type_count": template.repeat_type_count,
                "reposition_round_count": template.reposition_round_count,
                "assembly_count": template.assembly_count,
                "acquisition_block_count": template.acquisition_block_count,
                "common_valid_feature_count": result.common_valid_feature_count,
                "common_valid_feature_fraction": result.common_valid_feature_fraction,
            }
            for template in result.direction_templates
        ),
        (
            "direction_index",
            "angle_deg",
            "sample_count",
            "sample_ids",
            "standard_deviation_available",
            "session_count",
            "repeat_type_count",
            "reposition_round_count",
            "assembly_count",
            "acquisition_block_count",
            "common_valid_feature_count",
            "common_valid_feature_fraction",
        ),
    )
    written["direction_statistics"] = direction_statistics
    artifacts.append(direction_statistics)

    direction_templates = output / "direction_templates.csv"
    template_rows: list[dict[str, Any]] = []
    for template in result.direction_templates:
        for feature_index, (name, unit) in enumerate(
            zip(result.feature_names, result.units, strict=True)
        ):
            common = bool(result.common_valid_mask[feature_index])
            template_rows.append(
                {
                    "direction_index": template.direction_index,
                    "angle_deg": template.angle_deg,
                    "feature_index": feature_index,
                    "feature_name": name,
                    "units": unit,
                    "common_valid": common,
                    "mean_value": template.mean_values[feature_index] if common else None,
                    "standard_deviation": (
                        template.standard_deviation[feature_index]
                        if common and template.standard_deviation_available
                        else None
                    ),
                    "standard_deviation_available": (
                        common and template.standard_deviation_available
                    ),
                    "valid_sample_count": template.valid_sample_count[feature_index],
                }
            )
    _write_csv(
        direction_templates,
        template_rows,
        (
            "direction_index",
            "angle_deg",
            "feature_index",
            "feature_name",
            "units",
            "common_valid",
            "mean_value",
            "standard_deviation",
            "standard_deviation_available",
            "valid_sample_count",
        ),
    )
    written["direction_templates"] = direction_templates
    artifacts.append(direction_templates)

    matrix_files = {
        "pearson": ("correlation_matrix", "correlation_matrix.csv"),
        "cosine": ("cosine_matrix", "cosine_matrix.csv"),
        "euclidean": ("euclidean_distance_matrix", "euclidean_distance_matrix.csv"),
        "rms": ("rms_distance_matrix", "rms_distance_matrix.csv"),
        "median_absolute_difference": (
            "median_absolute_difference_matrix",
            "median_absolute_difference_matrix.csv",
        ),
    }
    matrix_fields = (
        "row_direction_index",
        "row_angle_deg",
        "column_direction_index",
        "column_angle_deg",
        "value",
        "available",
        "unavailable_reason",
        "feature_count",
    )
    for metric, (key, filename) in matrix_files.items():
        path = output / filename
        _write_csv(path, _matrix_rows(result.matrices[metric]), matrix_fields)
        written[key] = path
        artifacts.append(path)

    pair_fields = (
        "pair_id",
        "pair_scope",
        "repeat_type",
        "left_sample_id",
        "right_sample_id",
        "left_angle_deg",
        "right_angle_deg",
        "constructed",
        "unavailable_reason",
        "feature_count",
        "euclidean_distance",
        "rms_distance",
        "median_absolute_difference",
        "left_session_id",
        "right_session_id",
        "left_reposition_round_id",
        "right_reposition_round_id",
        "left_assembly_id",
        "right_assembly_id",
        "left_acquisition_block_id",
        "right_acquisition_block_id",
    )
    repeatability_pairs = output / "repeatability_pairs.csv"
    _write_csv(
        repeatability_pairs,
        _pair_rows(result.repeatability_pairs),
        pair_fields,
    )
    written["repeatability_pairs"] = repeatability_pairs
    artifacts.append(repeatability_pairs)

    repeatability_summary = output / "repeatability_summary.csv"
    _write_csv(
        repeatability_summary,
        (
            {
                "repeat_type": item.repeat_type,
                "metric": item.metric,
                "available": item.available,
                "pair_count": item.pair_count,
                "unavailable_candidate_count": item.unavailable_candidate_count,
                "median": item.median,
                "mean": item.mean,
                "standard_deviation": item.standard_deviation,
                "interquartile_range": item.interquartile_range,
                "minimum": item.minimum,
                "maximum": item.maximum,
                "unavailable_reason": item.unavailable_reason,
            }
            for item in result.repeatability_summaries
        ),
        (
            "repeat_type",
            "metric",
            "available",
            "pair_count",
            "unavailable_candidate_count",
            "median",
            "mean",
            "standard_deviation",
            "interquartile_range",
            "minimum",
            "maximum",
            "unavailable_reason",
        ),
    )
    written["repeatability_summary"] = repeatability_summary
    artifacts.append(repeatability_summary)

    between_pairs = output / "between_direction_pairs.csv"
    _write_csv(
        between_pairs,
        _pair_rows(result.between_direction_pairs),
        pair_fields,
    )
    written["between_direction_pairs"] = between_pairs
    artifacts.append(between_pairs)

    singular_values = output / "singular_values.csv"
    _write_csv(
        singular_values,
        (
            {
                "singular_index": index,
                "singular_value": singular,
                "proportion": result.effective_rank.proportions[index],
                "effective_rank_available": result.effective_rank.available,
                "centered": result.effective_rank.centered,
                "matrix_rows": result.effective_rank.matrix_shape[0],
                "matrix_columns": result.effective_rank.matrix_shape[1],
                "unavailable_reason": result.effective_rank.unavailable_reason,
            }
            for index, singular in enumerate(result.effective_rank.singular_values)
        ),
        (
            "singular_index",
            "singular_value",
            "proportion",
            "effective_rank_available",
            "centered",
            "matrix_rows",
            "matrix_columns",
            "unavailable_reason",
        ),
    )
    written["singular_values"] = singular_values
    artifacts.append(singular_values)

    metrics_summary = output / "metrics_summary.csv"
    summary = result.summary
    gain = result.morphology_gain
    _write_csv(
        metrics_summary,
        [
            {
                "analysis_scope_id": result.analysis_scope.analysis_scope_id,
                "configuration": result.configuration,
                "feature_kind": result.feature_kind,
                "preprocessing_id": result.preprocessing_id,
                "processing_status": result.processing_status,
                "direction_count": summary.direction_count,
                "sample_count": summary.sample_count,
                "feature_count": summary.feature_count,
                "effective_rank": result.effective_rank.value,
                "effective_rank_available": result.effective_rank.available,
                "maximum_off_diagonal_pearson": summary.maximum_off_diagonal_pearson,
                "mean_off_diagonal_pearson": summary.mean_off_diagonal_pearson,
                "minimum_direction_rms": summary.minimum_direction_rms,
                "median_direction_rms": summary.median_direction_rms,
                "maximum_direction_rms": summary.maximum_direction_rms,
                "most_similar_highest_pearson_pair": _json_cell(
                    summary.most_similar_highest_pearson_pair or ()
                ),
                "most_difficult_lowest_rms_pair": _json_cell(
                    summary.most_difficult_lowest_rms_pair or ()
                ),
                "morphology_gain": gain.value,
                "morphology_gain_available": gain.available,
                "morphology_gain_metric": gain.metric,
                "morphology_gain_numerator": gain.numerator,
                "morphology_gain_denominator": gain.denominator,
                "between_pair_count": gain.between_pair_count,
                "reposition_pair_count": gain.reposition_pair_count,
                "unavailable_reasons": _json_cell(
                    (*summary.unavailable_reasons, *result.failures)
                ),
            }
        ],
        (
            "analysis_scope_id",
            "configuration",
            "feature_kind",
            "preprocessing_id",
            "processing_status",
            "direction_count",
            "sample_count",
            "feature_count",
            "effective_rank",
            "effective_rank_available",
            "maximum_off_diagonal_pearson",
            "mean_off_diagonal_pearson",
            "minimum_direction_rms",
            "median_direction_rms",
            "maximum_direction_rms",
            "most_similar_highest_pearson_pair",
            "most_difficult_lowest_rms_pair",
            "morphology_gain",
            "morphology_gain_available",
            "morphology_gain_metric",
            "morphology_gain_numerator",
            "morphology_gain_denominator",
            "between_pair_count",
            "reposition_pair_count",
            "unavailable_reasons",
        ),
    )
    written["metrics_summary"] = metrics_summary
    artifacts.append(metrics_summary)

    selection_audit = output / "selection_audit.csv"
    _write_csv(
        selection_audit,
        (
            {
                "sample_id": item.sample_id,
                "requested": item.requested,
                "selected": item.selected,
                "selection_reasons": _json_cell(item.reasons),
                "source_sha256": item.source_sha256,
                "source_qc_sha256": item.source_qc_sha256,
                "feature_content_sha256": item.feature_content_sha256,
                "source_qc_status": (
                    None if item.source_qc_status is None else item.source_qc_status.value
                ),
                "source_qc_eligible_for_downstream": (
                    item.source_qc_eligible_for_downstream
                ),
                "source_qc_warning_reasons": _json_cell(
                    item.source_qc_warning_reasons
                ),
                "source_qc_exclude_candidate_reasons": _json_cell(
                    item.source_qc_exclude_candidate_reasons
                ),
                "source_qc_unavailable_checks": _json_cell(
                    item.source_qc_unavailable_checks
                ),
                "human_valid": item.human_valid,
                "manual_review_reasons": _json_cell(item.manual_review_reasons),
            }
            for item in result.selection_audit
        ),
        (
            "sample_id",
            "requested",
            "selected",
            "selection_reasons",
            "source_sha256",
            "source_qc_sha256",
            "feature_content_sha256",
            "source_qc_status",
            "source_qc_eligible_for_downstream",
            "source_qc_warning_reasons",
            "source_qc_exclude_candidate_reasons",
            "source_qc_unavailable_checks",
            "human_valid",
            "manual_review_reasons",
        ),
    )
    written["selection_audit"] = selection_audit
    artifacts.append(selection_audit)

    manifest_path = output / "metrics_manifest.json"
    scientific_use = (
        "eligible_real_experiment_research_analysis"
        if result.scientifically_eligible
        and result.analysis_scope.run_purpose.value == "research_analysis"
        else f"prohibited_{result.data_origin}_{result.analysis_scope.run_purpose.value}"
    )
    manifest = {
        "schema_version": METRICS_MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processing_status": result.processing_status,
        "failures": list(result.failures),
        "warnings": list(result.warnings),
        "scope": _scope_payload(result),
        "metrics_config": dict(result.metrics_config),
        "identity": {
            "configuration": result.configuration,
            "feature_kind": result.feature_kind,
            "feature_schema_version": result.feature_schema_version,
            "preprocessing_id": result.preprocessing_id,
            "source_representation": result.source_representation,
            "tone_set_id": result.tone_set_id,
            "tone_set_sha256": result.tone_set_sha256,
            "tone_schema_id": result.tone_schema_id,
            "dense_frequency_range_hz": result.dense_frequency_range_hz,
        },
        "template_usage": {
            "usage": result.template_usage,
            "eligible_for_training_dictionary": (
                result.eligible_for_training_dictionary
            ),
            "tone_selection_allowed": result.tone_selection_allowed,
        },
        "common_valid_features": {
            "count": result.common_valid_feature_count,
            "fraction": result.common_valid_feature_fraction,
            "indices": np.flatnonzero(result.common_valid_mask).tolist(),
            "names": [
                name
                for name, valid in zip(
                    result.feature_names,
                    result.common_valid_mask,
                    strict=True,
                )
                if valid
            ],
            "per_sample_missing_count": dict(result.per_sample_missing_count),
        },
        "direction_order_deg": list(result.direction_order_deg),
        "pair_definitions": {
            "canonical_pair": "lexicographic_sample_id_i_less_than_j_no_self_pair",
            "CONT": "same angle/repeat type/session/acquisition block; different repeat_id; optional physical-state IDs equal",
            "REPOS": "same angle/repeat type/session/assembly; different non-empty reposition_round_id and repeat_id",
            "REASM": "same angle/repeat type/session; different non-empty assembly_id and repeat_id",
            "between_sample_pair": "different angle; all selected unordered sample pairs",
        },
        "metric_definitions": {
            "pearson": "centered dot product divided by centered L2 norms; constant vector unavailable",
            "cosine": "dot product divided by L2 norms; zero norm unavailable",
            "euclidean": "sqrt(sum((x-y)^2))",
            "rms": "sqrt(mean((x-y)^2))",
            "median_absolute_difference": "median(abs(x-y))",
            "effective_rank": "exp(-sum(p_i*log(p_i))), p_i=sigma_i/sum(sigma), p_i>0 only",
            "morphology_gain": "median between-direction sample-pair distance / median within-direction REPOS distance",
        },
        "effective_rank": {
            "matrix_shape": result.effective_rank.matrix_shape,
            "centered": result.effective_rank.centered,
            "available": result.effective_rank.available,
            "value": result.effective_rank.value,
            "unavailable_reason": result.effective_rank.unavailable_reason,
        },
        "morphology_gain": {
            "metric": result.morphology_gain.metric,
            "available": result.morphology_gain.available,
            "value": result.morphology_gain.value,
            "numerator": result.morphology_gain.numerator,
            "denominator": result.morphology_gain.denominator,
            "between_pair_count": result.morphology_gain.between_pair_count,
            "reposition_pair_count": result.morphology_gain.reposition_pair_count,
            "minimum_denominator": result.morphology_gain.minimum_denominator,
            "unavailable_reason": result.morphology_gain.unavailable_reason,
        },
        "inputs": [
            {
                "sample_id": item.sample_id,
                "requested": item.requested,
                "selected": item.selected,
                "selection_reasons": list(item.reasons),
                "source_sha256": item.source_sha256,
                "source_qc_sha256": item.source_qc_sha256,
                "feature_content_sha256": item.feature_content_sha256,
                "source_qc_status": (
                    None
                    if item.source_qc_status is None
                    else item.source_qc_status.value
                ),
                "source_qc_warning_reasons": list(
                    item.source_qc_warning_reasons
                ),
                "source_qc_exclude_candidate_reasons": list(
                    item.source_qc_exclude_candidate_reasons
                ),
                "source_qc_unavailable_checks": list(
                    item.source_qc_unavailable_checks
                ),
                "source_qc_eligible_for_downstream": (
                    item.source_qc_eligible_for_downstream
                ),
            }
            for item in result.selection_audit
        ],
        "provenance": {
            "data_origin": result.data_origin,
            "dataset_role": result.dataset_role,
            "eligible_for_scientific_analysis": result.scientifically_eligible,
            "run_purpose": result.analysis_scope.run_purpose.value,
            "scientific_use": scientific_use,
        },
        "artifacts": [_artifact(path, output) for path in sorted(artifacts)],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written["metrics_manifest"] = manifest_path
    manifest_hash = output / "metrics_manifest.sha256"
    manifest_hash.write_text(artifact_sha256(manifest_path) + "\n", encoding="ascii")
    written["metrics_manifest_sha256"] = manifest_hash
    return written

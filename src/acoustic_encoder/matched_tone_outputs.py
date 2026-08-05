"""Immutable, auditable output bundle for paired P3-C tone features."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .schemas import FeatureKind, FeatureSet, artifact_sha256, save_feature_set
from .tone_features import (
    MatchedToneView,
    ToneExtractionRecord,
    ToneFeatureProcessingResult,
)
from .tone_sets import ToneSetDefinition


MATCHED_TONE_MANIFEST_SCHEMA_VERSION = "1.0.0"
MATCHED_TONE_AUDIT_SCHEMA_VERSION = "1.0.0"


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_bytes(_json_bytes(payload))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _artifact(path: Path, root: Path) -> dict[str, str]:
    return {"path": _relative(path, root), "sha256": artifact_sha256(path)}


def _json_cell(values: Iterable[Any]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _write_feature(
    result: ToneFeatureProcessingResult,
    output: Path,
) -> tuple[Path | None, Path | None]:
    feature = result.feature_set
    if feature is None:
        return None, None
    base = output / "features" / feature.feature_kind.value / feature.sample_id
    return save_feature_set(feature, base)


def _feature_index_row(
    result: ToneFeatureProcessingResult,
    array_path: Path | None,
    metadata_path: Path | None,
    output: Path,
) -> dict[str, Any]:
    feature = result.feature_set
    meta = feature.meta if feature is not None else None
    return {
        "sample_id": result.sample_id,
        "feature_kind": (
            feature.feature_kind.value if feature is not None else result.feature_kind.value
        ),
        "processing_status": result.processing_status,
        "failure_reasons": " | ".join(result.failures),
        "tone_set_id": "" if feature is None else feature.tone_set_id,
        "tone_set_sha256": "" if feature is None else feature.tone_set_sha256,
        "tone_schema_id": result.tone_schema_id,
        "preprocessing_id": result.preprocessing_id,
        "dense_preprocessing_id": result.dense_preprocessing_id or "",
        "normalization_method": (
            "" if feature is None else feature.normalization_method
        ),
        "feature_count": "" if feature is None else feature.values.size,
        "valid_feature_count": (
            "" if feature is None else int(np.count_nonzero(feature.valid_mask))
        ),
        "units": "" if feature is None else feature.units[0],
        "source_magnitude_quantity": (
            "" if feature is None else feature.source_magnitude_quantity
        ),
        "source_magnitude_reference": (
            "" if feature is None else feature.source_magnitude_reference or ""
        ),
        "calibration_id": "" if feature is None else feature.calibration_id or "",
        "source_phase_status": (
            "" if feature is None else feature.source_phase_status.value
        ),
        "source_qc_status": (
            ""
            if feature is None or feature.source_qc_status is None
            else feature.source_qc_status.value
        ),
        "reliability_weight_source": (
            "" if feature is None else feature.reliability_weight_source or ""
        ),
        "data_origin": "" if meta is None else meta.data_origin.value,
        "dataset_role": "" if meta is None else meta.dataset_role.value,
        "run_purpose": result.run_purpose,
        "eligible_for_scientific_analysis": (
            "" if meta is None else str(meta.eligible_for_scientific_analysis).lower()
        ),
        "npz_path": "" if array_path is None else _relative(array_path, output),
        "npz_sha256": "" if array_path is None else artifact_sha256(array_path),
        "json_path": (
            "" if metadata_path is None else _relative(metadata_path, output)
        ),
        "json_sha256": (
            "" if metadata_path is None else artifact_sha256(metadata_path)
        ),
    }


def _record_by_index(
    records: tuple[ToneExtractionRecord, ...],
) -> dict[int, ToneExtractionRecord]:
    return {record.tone_index: record for record in records}


def _audit_rows(
    sweep: ToneFeatureProcessingResult,
    multisine: ToneFeatureProcessingResult,
    view: MatchedToneView,
    tone_set: ToneSetDefinition,
) -> list[dict[str, Any]]:
    sweep_records = _record_by_index(sweep.extraction_records)
    multisine_records = _record_by_index(multisine.extraction_records)
    sweep_feature = sweep.feature_set
    multisine_feature = multisine.feature_set
    rows: list[dict[str, Any]] = []
    for tone, feature_name in zip(
        tone_set.tones,
        tone_set.feature_names,
        strict=True,
    ):
        sweep_record = sweep_records.get(tone.tone_index)
        multisine_record = multisine_records.get(tone.tone_index)
        rows.append(
            {
                "scope": "tone",
                "tone_index": tone.tone_index,
                "frequency_hz": tone.frequency_text,
                "dft_bin": tone.dft_bin,
                "feature_name": feature_name,
                "sweep_value": (
                    ""
                    if sweep_feature is None
                    or not sweep_feature.valid_mask[tone.tone_index]
                    else format(float(sweep_feature.values[tone.tone_index]), ".17g")
                ),
                "sweep_valid": (
                    ""
                    if sweep_feature is None
                    else str(bool(sweep_feature.valid_mask[tone.tone_index])).lower()
                ),
                "sweep_method": "" if sweep_record is None else sweep_record.method,
                "sweep_reason": "" if sweep_record is None else sweep_record.reason or "",
                "sweep_source_indices": (
                    "" if sweep_record is None else _json_cell(sweep_record.source_indices)
                ),
                "sweep_source_frequency_hz": (
                    ""
                    if sweep_record is None
                    else _json_cell(sweep_record.source_frequency_hz)
                ),
                "sweep_source_weights": (
                    "" if sweep_record is None else _json_cell(sweep_record.source_weights)
                ),
                "requested_bandwidth_hz": (
                    ""
                    if sweep_record is None or sweep_record.requested_bandwidth_hz is None
                    else format(sweep_record.requested_bandwidth_hz, ".17g")
                ),
                "covered_bandwidth_hz": (
                    ""
                    if sweep_record is None or sweep_record.covered_bandwidth_hz is None
                    else format(sweep_record.covered_bandwidth_hz, ".17g")
                ),
                "coverage_fraction": (
                    ""
                    if sweep_record is None or sweep_record.coverage_fraction is None
                    else format(sweep_record.coverage_fraction, ".17g")
                ),
                "valid_source_point_count": (
                    ""
                    if sweep_record is None or sweep_record.valid_source_point_count is None
                    else sweep_record.valid_source_point_count
                ),
                "multisine_value": (
                    ""
                    if multisine_feature is None
                    or not multisine_feature.valid_mask[tone.tone_index]
                    else format(
                        float(multisine_feature.values[tone.tone_index]), ".17g"
                    )
                ),
                "multisine_valid": (
                    ""
                    if multisine_feature is None
                    else str(
                        bool(multisine_feature.valid_mask[tone.tone_index])
                    ).lower()
                ),
                "multisine_reason": (
                    "" if multisine_record is None else multisine_record.reason or ""
                ),
                "multisine_source_indices": (
                    ""
                    if multisine_record is None
                    else _json_cell(multisine_record.source_indices)
                ),
                "common_valid": str(bool(view.common_valid_mask[tone.tone_index])).lower(),
            }
        )
    return rows


def write_matched_tone_outputs(
    sweep_result: ToneFeatureProcessingResult,
    multisine_result: ToneFeatureProcessingResult,
    view: MatchedToneView,
    tone_set: ToneSetDefinition,
    matched_config: Mapping[str, Any],
    processed_directory: str | Path,
) -> dict[str, Path]:
    """Write one paired P3-C bundle, refusing any existing target directory."""
    output = Path(processed_directory)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"Matched-tone processed output directory already exists: {output}"
        ) from exc

    written: dict[str, Path] = {}
    artifacts: list[Path] = []
    feature_paths: list[tuple[Path | None, Path | None]] = []
    for result in (sweep_result, multisine_result):
        paths = _write_feature(result, output)
        feature_paths.append(paths)
        artifacts.extend(path for path in paths if path is not None)

    index_rows = [
        _feature_index_row(result, *paths, output)
        for result, paths in zip(
            (sweep_result, multisine_result),
            feature_paths,
            strict=True,
        )
    ]
    index_path = output / "tone_feature_index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(index_rows[0]))
        writer.writeheader()
        writer.writerows(index_rows)
    written["tone_feature_index_csv"] = index_path

    schema_path = output / "matched_tone_schema.json"
    feature = sweep_result.feature_set or multisine_result.feature_set
    _write_json(
        schema_path,
        {
            "schema_version": MATCHED_TONE_AUDIT_SCHEMA_VERSION,
            "authoritative_ordering": "manifest_tone_index",
            "tone_set_id": tone_set.tone_set_id,
            "tone_set_sha256": tone_set.tone_set_sha256,
            "tones_sha256": tone_set.tones_sha256,
            "tone_schema_id": sweep_result.tone_schema_id,
            "normalization": dict(matched_config.get("normalization", {})),
            "units": [] if feature is None else list(feature.units),
            "tones": [
                {
                    "tone_index": tone.tone_index,
                    "frequency_hz": tone.frequency_text,
                    "dft_bin": tone.dft_bin,
                    "feature_name": name,
                }
                for tone, name in zip(
                    tone_set.tones,
                    tone_set.feature_names,
                    strict=True,
                )
            ],
        },
    )
    written["matched_tone_schema_json"] = schema_path

    audit_rows = _audit_rows(sweep_result, multisine_result, view, tone_set)
    audit_path = output / "matched_tone_audit.csv"
    with audit_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)
    written["matched_tone_audit_csv"] = audit_path

    failures_path = output / "preprocessing_failures.csv"
    failure_rows = [
        {
            "sample_id": result.sample_id,
            "feature_kind": (
                result.feature_set.feature_kind.value
                if result.feature_set is not None
                else result.feature_kind.value
            ),
            "scope": "measurement",
            "tone_index": "",
            "reason": reason,
        }
        for result in (sweep_result, multisine_result)
        for reason in result.failures
    ]
    if view.failure_reason:
        failure_rows.append(
            {
                "sample_id": f"{sweep_result.sample_id}|{multisine_result.sample_id}",
                "feature_kind": "matched_pair",
                "scope": "measurement",
                "tone_index": "",
                "reason": view.failure_reason,
            }
        )
    fields = ("sample_id", "feature_kind", "scope", "tone_index", "reason")
    with failures_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(failure_rows)
    written["preprocessing_failures_csv"] = failures_path

    artifacts.extend((index_path, schema_path, audit_path, failures_path))
    source_features = [
        result.feature_set
        for result in (sweep_result, multisine_result)
        if result.feature_set is not None
    ]
    data_origins = {item.meta.data_origin.value for item in source_features}
    run_purposes = {sweep_result.run_purpose, multisine_result.run_purpose}
    manifest_path = output / "preprocessing_manifest.json"
    manifest = {
        "schema_version": MATCHED_TONE_MANIFEST_SCHEMA_VERSION,
        "processing_status": view.processing_status,
        "processing_order": {
            "sweep": [
                "SpectrumData",
                "P3_common_grid",
                "P3_smoothing",
                "tone_extraction",
                "tone_normalization",
                "FeatureSet",
            ],
            "multisine": [
                "P8_sparse_tones_SpectrumData",
                "direct_authoritative_tone_alignment",
                "tone_normalization",
                "FeatureSet",
            ],
        },
        "tone_authority": {
            "tone_set_id": tone_set.tone_set_id,
            "tone_set_sha256": tone_set.tone_set_sha256,
            "tones_sha256": tone_set.tones_sha256,
            "stimulus_manifest_sha256": tone_set.manifest_sha256,
            "stimulus_manifest_path": tone_set.manifest_path.as_posix(),
            "tones_path": tone_set.tones_path.as_posix(),
            "authoritative_ordering": "manifest_tone_index",
            "verified_artifacts": tone_set.verified_artifacts,
        },
        "configuration": dict(matched_config),
        "feature_processing": {
            "sweep_preprocessing_id": sweep_result.preprocessing_id,
            "dense_preprocessing_id": sweep_result.dense_preprocessing_id,
            "multisine_preprocessing_id": multisine_result.preprocessing_id,
            "tone_schema_id": sweep_result.tone_schema_id,
        },
        "source_magnitude": [
            {
                "sample_id": item.sample_id,
                "measurement_mode": item.source_measurement_mode.value,
                "quantity": item.source_magnitude_quantity,
                "reference": item.source_magnitude_reference,
                "calibration_id": item.calibration_id,
                "phase_status": item.source_phase_status.value,
            }
            for item in source_features
        ],
        "comparison": {
            "source_reference_status": view.source_reference_status,
            "comparison_status": view.comparison_status,
            "cross_mode_absolute_comparable": (
                view.cross_mode_absolute_comparable
            ),
            "sweep_invalid_count": view.sweep_invalid_count,
            "multisine_missing_count": view.multisine_missing_count,
            "multisine_other_invalid_count": view.multisine_other_invalid_count,
            "common_valid_tone_count": view.common_valid_count,
            "minimum_common_valid_tones": view.minimum_common_valid_tones,
        },
        "reliability_weights": {
            "available": any(item.reliability_weights is not None for item in source_features),
            "sources": [item.reliability_weight_source for item in source_features],
            "formula": None,
        },
        "provenance": {
            "data_origin": next(iter(data_origins)) if len(data_origins) == 1 else "mixed",
            "run_purpose": next(iter(run_purposes)) if len(run_purposes) == 1 else "mixed",
            "eligible_for_scientific_analysis": all(
                item.meta.eligible_for_scientific_analysis for item in source_features
            ),
            "sources": [
                {
                    "sample_id": item.sample_id,
                    "data_origin": item.meta.data_origin.value,
                    "dataset_role": item.meta.dataset_role.value,
                    "source_path": item.meta.source_path,
                    "source_sha256": item.meta.source_sha256,
                }
                for item in source_features
            ],
        },
        "failures": failure_rows,
        "artifacts": [
            _artifact(path, output)
            for path in sorted(artifacts, key=lambda item: _relative(item, output))
        ],
    }
    _write_json(manifest_path, manifest)
    written["preprocessing_manifest_json"] = manifest_path
    manifest_sha_path = output / "preprocessing_manifest.sha256"
    manifest_sha_path.write_text(artifact_sha256(manifest_path) + "\n", encoding="ascii")
    written["preprocessing_manifest_sha256"] = manifest_sha_path
    return written

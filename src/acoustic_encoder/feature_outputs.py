"""Auditable, non-overwriting output bundle for dense P3-A features."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .features import DenseFeatureProcessingResult
from .preprocessing import canonical_preprocessing_config
from .schemas import FeatureKind, artifact_sha256, save_feature_set

PREPROCESSING_MANIFEST_SCHEMA_VERSION = "1.0.0"
FEATURE_INDEX_SCHEMA_VERSION = "1.0.0"

_KINDS = (
    FeatureKind.DENSE_RAW_SPL,
    FeatureKind.DENSE_DEMEANED_DB,
    FeatureKind.DENSE_ZSCORE,
)


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_bytes(_json_bytes(payload))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _artifact_record(path: Path, root: Path) -> dict[str, str]:
    return {
        "path": _relative(path, root),
        "sha256": artifact_sha256(path),
    }


def _join(values: tuple[str, ...]) -> str:
    return " | ".join(values)


def write_dense_feature_outputs(
    result: DenseFeatureProcessingResult,
    processed_directory: str | Path,
) -> dict[str, Path]:
    """Write one immutable P3-A output bundle and return its named paths."""
    output = Path(processed_directory)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"P3-A processed output directory already exists: {output}"
        ) from exc

    written: dict[str, Path] = {}
    feature_artifacts: list[Path] = []
    index_rows: list[dict[str, Any]] = []
    failures_by_kind = {
        failure.feature_kind: failure for failure in result.failures
    }
    for kind in _KINDS:
        feature = result.feature_sets.get(kind)
        failure = failures_by_kind.get(kind)
        array_path: Path | None = None
        metadata_path: Path | None = None
        if feature is not None:
            base = output / "features" / kind.value / result.sample_id
            array_path, metadata_path = save_feature_set(feature, base)
            feature_artifacts.extend((array_path, metadata_path))
            written[f"{kind.value}_npz"] = array_path
            written[f"{kind.value}_json"] = metadata_path
        index_rows.append(
            {
                "sample_id": result.sample_id,
                "feature_kind": kind.value,
                "processing_status": "success" if feature is not None else "failed",
                "failure_reason": "" if failure is None else failure.reason,
                "failure_message": "" if failure is None else failure.message,
                "preprocessing_id": result.preprocessing_id,
                "valid_grid_fraction": format(result.valid_grid_fraction, ".17g"),
                "feature_count": "" if feature is None else str(feature.values.size),
                "valid_feature_count": (
                    "" if feature is None else str(int(feature.valid_mask.sum()))
                ),
                "npz_path": "" if array_path is None else _relative(array_path, output),
                "npz_sha256": "" if array_path is None else artifact_sha256(array_path),
                "json_path": (
                    "" if metadata_path is None else _relative(metadata_path, output)
                ),
                "json_sha256": (
                    "" if metadata_path is None else artifact_sha256(metadata_path)
                ),
                "source_qc_status": result.measurement_qc.aggregate_status.value,
                "source_qc_warning_reasons": _join(
                    result.measurement_qc.warning_reasons
                ),
                "source_qc_exclude_candidate_reasons": _join(
                    result.measurement_qc.exclude_candidate_reasons
                ),
                "source_qc_unavailable_checks": _join(
                    result.measurement_qc.unavailable_checks
                ),
                "human_valid": str(result.measurement_qc.human_valid).lower(),
                "manual_review_reasons": _join(
                    result.measurement_qc.manual_review_reasons
                ),
                "eligible_for_downstream": str(
                    result.measurement_qc.eligible_for_downstream
                ).lower(),
                "data_origin": result.meta.data_origin.value,
                "dataset_role": result.meta.dataset_role.value,
                "run_purpose": result.measurement_qc.run_purpose.value,
            }
        )

    index_path = output / "feature_index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(index_rows[0]))
        writer.writeheader()
        writer.writerows(index_rows)
    written["feature_index_csv"] = index_path

    failures_path = output / "preprocessing_failures.csv"
    failure_fields = ("sample_id", "feature_kind", "reason", "message")
    with failures_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=failure_fields)
        writer.writeheader()
        writer.writerows(
            {
                "sample_id": result.sample_id,
                "feature_kind": failure.feature_kind.value,
                "reason": failure.reason,
                "message": failure.message,
            }
            for failure in result.failures
        )
    written["preprocessing_failures_csv"] = failures_path

    schema_path = output / "feature_schema.json"
    _write_json(
        schema_path,
        {
            "schema_version": FEATURE_INDEX_SCHEMA_VERSION,
            "feature_schema_version": result.meta.feature_schema_version,
            "representation": "dense_spectrum",
            "grid_frequency_hz": result.grid_frequency_hz.tolist(),
            "feature_names": list(result.feature_names),
            "feature_kinds": [kind.value for kind in _KINDS],
            "units_by_kind": {
                FeatureKind.DENSE_RAW_SPL.value: "dB",
                FeatureKind.DENSE_DEMEANED_DB.value: "dB",
                FeatureKind.DENSE_ZSCORE.value: "dimensionless",
            },
        },
    )
    written["feature_schema_json"] = schema_path

    qc_payload = json.dumps(
        result.measurement_qc.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    qc_sha256 = f"sha256:{hashlib.sha256(qc_payload).hexdigest()}"
    artifact_paths = feature_artifacts + [index_path, failures_path, schema_path]
    manifest_path = output / "preprocessing_manifest.json"
    manifest = {
        "schema_version": PREPROCESSING_MANIFEST_SCHEMA_VERSION,
        "processing_status": result.processing_status,
        "preprocessing_id": result.preprocessing_id,
        "preprocessing_config": canonical_preprocessing_config(
            result.preprocessing_config
        ),
        "version_quartet": {
            "pipeline_version": result.meta.pipeline_version,
            "config_schema_version": result.meta.config_schema_version,
            "measurement_schema_version": result.meta.measurement_schema_version,
            "feature_schema_version": result.meta.feature_schema_version,
        },
        "input": {
            "sample_id": result.sample_id,
            "source_path": result.meta.source_path,
            "source_sha256": result.meta.source_sha256,
            "measurement_mode": result.meta.measurement_mode.value,
            "representation": "dense_spectrum",
        },
        "source_magnitude": {
            "quantity": result.magnitude_quantity,
            "reference": result.magnitude_reference,
        },
        "provenance": {
            "data_origin": result.meta.data_origin.value,
            "dataset_role": result.meta.dataset_role.value,
            "run_purpose": result.measurement_qc.run_purpose.value,
            "eligible_for_scientific_analysis": (
                result.meta.eligible_for_scientific_analysis
            ),
            "scientifically_eligible_after_qc": (
                result.measurement_qc.scientifically_eligible
            ),
        },
        "source_qc": {
            "sha256": qc_sha256,
            **result.measurement_qc.to_dict(),
        },
        "grid": {
            "endpoint_policy": "inclusive_exact_decimal",
            "frequency_hz": result.grid_frequency_hz.tolist(),
            "feature_names": list(result.feature_names),
            "valid_grid_fraction": result.valid_grid_fraction,
        },
        "normalization": {
            "demean_formula": "x - mean(valid normalization-band x)",
            "zscore_formula": "(x - mean) / population_std",
            "standard_deviation_ddof": 0,
        },
        "warnings": list(result.warnings),
        "failures": [
            {
                "feature_kind": failure.feature_kind.value,
                "reason": failure.reason,
                "message": failure.message,
            }
            for failure in result.failures
        ],
        "artifacts": [
            _artifact_record(path, output)
            for path in sorted(artifact_paths, key=lambda item: _relative(item, output))
        ],
    }
    _write_json(manifest_path, manifest)
    written["preprocessing_manifest_json"] = manifest_path
    manifest_sha_path = output / "preprocessing_manifest.sha256"
    manifest_sha_path.write_text(
        artifact_sha256(manifest_path) + "\n",
        encoding="ascii",
    )
    written["preprocessing_manifest_sha256"] = manifest_sha_path
    return written

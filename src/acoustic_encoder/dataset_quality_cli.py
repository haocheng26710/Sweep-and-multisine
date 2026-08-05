"""Explicit-scope CLI orchestration for P2-B dataset quality control."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

import yaml

from .config import load_config
from .dataset_quality_control import (
    DatasetQCInputError,
    DatasetQCScope,
    evaluate_dataset_quality,
    measurement_qc_sha256,
)
from .dataset_quality_outputs import write_dataset_quality_outputs
from .quality_control import MeasurementQCResult
from .quality_control_outputs import load_quality_control_json
from .schemas import (
    DataOrigin,
    DatasetRole,
    FeatureSet,
    artifact_sha256,
    load_feature_set,
)


DATASET_QC_INPUT_MANIFEST_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class DatasetQCInputEntry:
    sample_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str
    measurement_qc_path: str
    measurement_qc_file_sha256: str
    measurement_qc_result_sha256: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DatasetQCInputEntry":
        required = {
            "sample_id",
            "feature_base_path",
            "feature_npz_sha256",
            "feature_json_sha256",
            "measurement_qc_path",
            "measurement_qc_file_sha256",
            "measurement_qc_result_sha256",
        }
        if set(payload) != required:
            raise DatasetQCInputError(
                "dataset QC input entry fields must be explicit: "
                + ", ".join(sorted(required))
            )
        entry = cls(**{name: str(payload[name]) for name in required})
        if not all(str(getattr(entry, name)).strip() for name in required):
            raise DatasetQCInputError("dataset QC input entry values cannot be blank")
        return entry


@dataclass(frozen=True, slots=True)
class DatasetQCInputManifest:
    schema_version: str
    analysis_scope_id: str
    data_origin: DataOrigin
    dataset_role: DatasetRole
    measurements: tuple[DatasetQCInputEntry, ...]

    def __post_init__(self) -> None:
        if self.schema_version != DATASET_QC_INPUT_MANIFEST_SCHEMA_VERSION:
            raise DatasetQCInputError("dataset QC input manifest schema_version must be 1.0.0")
        if not self.analysis_scope_id.strip():
            raise DatasetQCInputError("dataset QC input manifest scope ID is required")
        sample_ids = tuple(item.sample_id for item in self.measurements)
        if not sample_ids or len(set(sample_ids)) != len(sample_ids):
            raise DatasetQCInputError("dataset QC input sample IDs must be non-empty and unique")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DatasetQCInputManifest":
        return cls(
            schema_version=str(payload["schema_version"]),
            analysis_scope_id=str(payload["analysis_scope_id"]),
            data_origin=DataOrigin(payload["data_origin"]),
            dataset_role=DatasetRole(payload["dataset_role"]),
            measurements=tuple(
                DatasetQCInputEntry.from_dict(item) for item in payload["measurements"]
            ),
        )


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DatasetQCInputError(f"expected a mapping in {path}")
    return payload


def _resolved_path(value: str, parent: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def load_explicit_dataset_qc_inputs(
    input_manifest_path: str | Path,
    scope: DatasetQCScope,
) -> tuple[
    tuple[FeatureSet, ...],
    tuple[MeasurementQCResult, ...],
    tuple[dict[str, str], ...],
    DatasetQCInputManifest,
]:
    """Load exactly the files listed by the immutable input manifest."""
    manifest_path = Path(input_manifest_path).resolve()
    manifest = DatasetQCInputManifest.from_dict(_read_mapping(manifest_path))
    if manifest.analysis_scope_id != scope.analysis_scope_id:
        raise DatasetQCInputError("dataset QC input manifest scope ID mismatch")
    if tuple(item.sample_id for item in manifest.measurements) != scope.sample_ids:
        raise DatasetQCInputError(
            "dataset QC input manifest sample order must exactly match scope"
        )
    features: list[FeatureSet] = []
    measurement_results: list[MeasurementQCResult] = []
    artifacts: list[dict[str, str]] = []
    for entry in manifest.measurements:
        base = _resolved_path(entry.feature_base_path, manifest_path.parent)
        if base.suffix:
            base = base.with_suffix("")
        npz_path = base.with_suffix(".npz")
        json_path = base.with_suffix(".json")
        qc_path = _resolved_path(entry.measurement_qc_path, manifest_path.parent)
        expected_paths = (
            (npz_path, entry.feature_npz_sha256, "feature_npz"),
            (json_path, entry.feature_json_sha256, "feature_json"),
            (qc_path, entry.measurement_qc_file_sha256, "measurement_qc_json"),
        )
        for path, expected_hash, role in expected_paths:
            if not path.is_file():
                raise FileNotFoundError(f"explicit dataset QC input is missing: {path}")
            actual = artifact_sha256(path)
            if actual != expected_hash:
                raise DatasetQCInputError(
                    f"explicit dataset QC input hash mismatch: {path}"
                )
            artifacts.append(
                {
                    "sample_id": entry.sample_id,
                    "artifact_role": role,
                    "path": path.as_posix(),
                    "sha256": actual,
                }
            )
        feature = load_feature_set(base)
        measurement_qc = load_quality_control_json(qc_path)
        if feature.sample_id != entry.sample_id or measurement_qc.sample_id != entry.sample_id:
            raise DatasetQCInputError(
                f"dataset QC serialized sample ID mismatch: {entry.sample_id}"
            )
        if measurement_qc_sha256(measurement_qc) != entry.measurement_qc_result_sha256:
            raise DatasetQCInputError(
                f"dataset QC P2-A result hash mismatch: {entry.sample_id}"
            )
        if (
            feature.meta.data_origin is not manifest.data_origin
            or feature.meta.dataset_role is not manifest.dataset_role
        ):
            raise DatasetQCInputError(
                f"dataset QC input provenance mismatch: {entry.sample_id}"
            )
        features.append(feature)
        measurement_results.append(measurement_qc)
    return tuple(features), tuple(measurement_results), tuple(artifacts), manifest


def _git_commit(project_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_failure_manifest(
    output: Path,
    *,
    scope: DatasetQCScope,
    input_manifest: DatasetQCInputManifest,
    scope_path: Path,
    inputs_path: Path,
    project_root: Path,
    random_state: int,
    error: Exception,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    partial_artifacts = []
    for path in sorted(output.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name not in {
            "dataset_qc_manifest.json",
            "dataset_qc_manifest.sha256",
        }:
            partial_artifacts.append(
                {
                    "path": path.name,
                    "sha256": artifact_sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    payload = {
        "schema_version": "1.0.0",
        "processing_status": "failed",
        "success": False,
        "analysis_scope_id": scope.analysis_scope_id,
        "scope_sha256": scope.sha256,
        "scope": scope.to_dict(),
        "git_commit": _git_commit(project_root),
        "random_state": random_state,
        "provenance": {
            "data_origin": input_manifest.data_origin.value,
            "dataset_role": input_manifest.dataset_role.value,
            "run_purpose": scope.run_purpose.value,
            "scientifically_eligible": False,
        },
        "known_inputs": [
            {
                "artifact_role": "dataset_scope",
                "path": scope_path.as_posix(),
                "sha256": artifact_sha256(scope_path),
            },
            {
                "artifact_role": "dataset_input_manifest",
                "path": inputs_path.as_posix(),
                "sha256": artifact_sha256(inputs_path),
            },
        ],
        "artifacts": partial_artifacts,
        "failure": {
            "exception_type": type(error).__name__,
            "message": str(error),
        },
    }
    manifest_path = output / "dataset_qc_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output / "dataset_qc_manifest.sha256").write_text(
        f"{artifact_sha256(manifest_path)}  {manifest_path.name}\n",
        encoding="ascii",
    )


def run_dataset_quality_cli(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path | None = None,
) -> int:
    project_root = (
        Path(project_root).resolve()
        if project_root is not None
        else Path(__file__).resolve().parents[2]
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    arguments = parser.parse_args(argv)
    resolved = load_config(
        arguments.config,
        default_path=project_root / "config" / "default.yaml",
    )
    scope_path = arguments.scope.resolve()
    inputs_path = arguments.inputs.resolve()
    scope = DatasetQCScope.from_dict(_read_mapping(scope_path))
    if scope.run_purpose.value != resolved["run_purpose"]:
        raise DatasetQCInputError("dataset scope run_purpose does not match resolved config")
    input_manifest = DatasetQCInputManifest.from_dict(_read_mapping(inputs_path))
    output = (
        arguments.output_root.resolve()
        / input_manifest.data_origin.value
        / scope.run_purpose.value
        / arguments.run_id
        / "dataset_qc"
    )
    if output.exists():
        raise FileExistsError(f"Dataset QC output directory already exists: {output}")
    try:
        features, measurement_results, artifacts, manifest = load_explicit_dataset_qc_inputs(
            inputs_path,
            scope,
        )
        result = evaluate_dataset_quality(
            features,
            measurement_results,
            scope,
            resolved["dataset_quality_control"],
        )
    except Exception as error:
        _write_failure_manifest(
            output,
            scope=scope,
            input_manifest=input_manifest,
            scope_path=scope_path,
            inputs_path=inputs_path,
            project_root=project_root,
            random_state=int(resolved["random_state"]),
            error=error,
        )
        print(
            json.dumps(
                {
                    "output_directory": output.as_posix(),
                    "processing_status": "failed",
                    "success": False,
                    "error": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    scope_input_artifacts = (
        {
            "sample_id": "__dataset__",
            "artifact_role": "dataset_scope",
            "path": scope_path.as_posix(),
            "sha256": artifact_sha256(scope_path),
        },
        {
            "sample_id": "__dataset__",
            "artifact_role": "dataset_input_manifest",
            "path": inputs_path.as_posix(),
            "sha256": artifact_sha256(inputs_path),
        },
    )
    write_dataset_quality_outputs(
        result,
        scope,
        resolved["dataset_quality_control"],
        output,
        input_artifacts=(*artifacts, *scope_input_artifacts),
        git_commit=_git_commit(project_root),
        random_state=int(resolved["random_state"]),
    )
    print(
        json.dumps(
            {
                "output_directory": output.as_posix(),
                "processing_status": "completed",
                "aggregate_status": result.aggregate_status.value,
                "canonical_ready": result.canonical_ready,
                "scientifically_eligible": result.scientifically_eligible,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0

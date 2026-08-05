"""Explicit persisted-FeatureSet CLI for P4-B comparison metrics."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

import yaml

from .comparison_metrics import (
    ComparisonAnalysisScope,
    ComparisonMetricsInputError,
    analyze_comparison_feature_sets,
)
from .comparison_metrics_outputs import write_comparison_metrics_outputs
from .config import load_config
from .dataset_quality_outputs import load_dataset_quality_bundle
from .schemas import DataOrigin, artifact_sha256, load_feature_set


COMPARISON_INPUT_MANIFEST_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class ComparisonInputEntry:
    artifact_id: str
    sample_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComparisonInputEntry":
        required = {
            "artifact_id", "sample_id", "feature_base_path",
            "feature_npz_sha256", "feature_json_sha256",
        }
        if set(payload) != required:
            raise ComparisonMetricsInputError(
                "comparison input FeatureSet fields must be explicit"
            )
        entry = cls(**{name: str(payload[name]) for name in required})
        if any(not str(getattr(entry, name)).strip() for name in required):
            raise ComparisonMetricsInputError("comparison input fields cannot be blank")
        return entry


@dataclass(frozen=True, slots=True)
class ComparisonInputManifest:
    schema_version: str
    analysis_scope_id: str
    data_origin: DataOrigin
    run_purpose: str
    features: tuple[ComparisonInputEntry, ...]

    def __post_init__(self) -> None:
        if self.schema_version != COMPARISON_INPUT_MANIFEST_SCHEMA_VERSION:
            raise ComparisonMetricsInputError(
                "comparison input manifest schema_version must be 1.0.0"
            )
        ids = tuple(item.artifact_id for item in self.features)
        if not ids or len(set(ids)) != len(ids):
            raise ComparisonMetricsInputError(
                "comparison input artifact IDs must be non-empty and unique"
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ComparisonInputManifest":
        required = {
            "schema_version", "analysis_scope_id", "data_origin", "run_purpose", "features"
        }
        if set(payload) != required:
            raise ComparisonMetricsInputError(
                "comparison input manifest fields must be explicit"
            )
        return cls(
            schema_version=str(payload["schema_version"]),
            analysis_scope_id=str(payload["analysis_scope_id"]),
            data_origin=DataOrigin(payload["data_origin"]),
            run_purpose=str(payload["run_purpose"]),
            features=tuple(ComparisonInputEntry.from_dict(item) for item in payload["features"]),
        )


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.suffix.lower() == ".json"
        else yaml.safe_load(path.read_text(encoding="utf-8"))
    )
    if not isinstance(payload, dict):
        raise ComparisonMetricsInputError(f"expected mapping in {path}")
    return payload


def _resolved(value: str, parent: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def load_explicit_comparison_inputs(
    manifest_path: str | Path,
    scope: ComparisonAnalysisScope,
) -> tuple[dict[str, Any], tuple[dict[str, str], ...], ComparisonInputManifest]:
    path = Path(manifest_path).resolve()
    manifest = ComparisonInputManifest.from_dict(_read_mapping(path))
    if manifest.analysis_scope_id != scope.analysis_scope.analysis_scope_id:
        raise ComparisonMetricsInputError("comparison input/scope ID mismatch")
    expected_ids = tuple(item.artifact_id for item in scope.feature_references)
    if tuple(item.artifact_id for item in manifest.features) != expected_ids:
        raise ComparisonMetricsInputError(
            "comparison input FeatureSet order must exactly match scope references"
        )
    features: dict[str, Any] = {}
    records: list[dict[str, str]] = []
    references = {item.artifact_id: item for item in scope.feature_references}
    for entry in manifest.features:
        base = _resolved(entry.feature_base_path, path.parent)
        if base.suffix:
            base = base.with_suffix("")
        for artifact_path, expected_hash, role in (
            (base.with_suffix(".npz"), entry.feature_npz_sha256, "feature_set_npz"),
            (base.with_suffix(".json"), entry.feature_json_sha256, "feature_set_json"),
        ):
            if not artifact_path.is_file():
                raise FileNotFoundError(f"explicit comparison input is missing: {artifact_path}")
            actual = artifact_sha256(artifact_path)
            if actual != expected_hash:
                raise ComparisonMetricsInputError(
                    f"explicit comparison input hash mismatch: {artifact_path}"
                )
            records.append(
                {
                    "artifact_id": entry.artifact_id,
                    "artifact_role": role,
                    "path": artifact_path.as_posix(),
                    "sha256": actual,
                }
            )
        feature = load_feature_set(base)
        reference = references[entry.artifact_id]
        if feature.sample_id != entry.sample_id or reference.sample_id != entry.sample_id:
            raise ComparisonMetricsInputError(
                f"comparison serialized sample ID mismatch: {entry.artifact_id}"
            )
        if feature.meta.data_origin is not manifest.data_origin:
            raise ComparisonMetricsInputError("comparison input provenance mismatch")
        features[entry.artifact_id] = feature
    return features, tuple(records), manifest


def _git_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True,
    )
    return completed.stdout.strip()


def _write_failure_manifest(
    output: Path,
    *,
    scope: ComparisonAnalysisScope,
    manifest: ComparisonInputManifest,
    error: Exception,
    known_inputs: Sequence[Mapping[str, str]],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "processing_status": "failed",
        "success": False,
        "analysis_scope_id": scope.analysis_scope.analysis_scope_id,
        "comparison_scope_sha256": scope.sha256,
        "analysis_tier": scope.analysis_scope.analysis_tier.value,
        "provenance": {
            "data_origin": manifest.data_origin.value,
            "run_purpose": manifest.run_purpose,
            "scientifically_eligible": False,
        },
        "known_inputs": list(known_inputs),
        "failure": {"exception_type": type(error).__name__, "message": str(error)},
    }
    path = output / "metrics_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "metrics_manifest.sha256").write_text(
        artifact_sha256(path) + "\n", encoding="ascii"
    )


def run_comparison_metrics_cli(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path | None = None,
) -> int:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--dataset-qc-dir", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    resolved = load_config(args.config, default_path=root / "config" / "default.yaml")
    scope_path = args.scope.resolve()
    inputs_path = args.inputs.resolve()
    scope = ComparisonAnalysisScope.from_dict(_read_mapping(scope_path))
    input_manifest = ComparisonInputManifest.from_dict(_read_mapping(inputs_path))
    if input_manifest.run_purpose != resolved["run_purpose"]:
        raise ComparisonMetricsInputError("comparison input run_purpose/config mismatch")
    if scope.analysis_scope.run_purpose.value != resolved["run_purpose"]:
        raise ComparisonMetricsInputError("comparison scope run_purpose/config mismatch")
    output = (
        args.output_root.resolve() / input_manifest.data_origin.value /
        input_manifest.run_purpose / args.run_id / "comparison_metrics"
    )
    if output.exists():
        raise FileExistsError(f"comparison output directory already exists: {output}")
    known = (
        {"artifact_id": "__scope__", "artifact_role": "comparison_scope", "path": scope_path.as_posix(), "sha256": artifact_sha256(scope_path)},
        {"artifact_id": "__inputs__", "artifact_role": "comparison_input_manifest", "path": inputs_path.as_posix(), "sha256": artifact_sha256(inputs_path)},
    )
    try:
        features, feature_records, manifest = load_explicit_comparison_inputs(
            inputs_path, scope
        )
        qc_result = None
        if scope.analysis_scope.dataset_qc_reference is not None:
            if args.dataset_qc_dir is None:
                raise ComparisonMetricsInputError(
                    "comparison scope requires --dataset-qc-dir"
                )
            qc_result = load_dataset_quality_bundle(args.dataset_qc_dir)
        elif args.dataset_qc_dir is not None:
            raise ComparisonMetricsInputError(
                "dataset QC bundle supplied but scope has no DatasetQCReference"
            )
        result = analyze_comparison_feature_sets(
            features,
            scope,
            resolved["direction_metrics"],
            resolved["comparison_metrics"],
            dataset_qc_result=qc_result,
        )
        write_comparison_metrics_outputs(
            result,
            scope,
            output,
            comparison_config=resolved["comparison_metrics"],
            input_artifacts=(*feature_records, *known),
            git_commit=_git_commit(root),
            random_state=int(resolved["random_state"]),
        )
    except Exception as error:
        _write_failure_manifest(
            output,
            scope=scope,
            manifest=input_manifest,
            error=error,
            known_inputs=known,
        )
        print(json.dumps({
            "output_directory": output.as_posix(), "processing_status": "failed",
            "success": False, "error": str(error),
        }, indent=2, sort_keys=True))
        return 1
    print(json.dumps({
        "output_directory": output.as_posix(),
        "processing_status": result.processing_status,
        "success": result.processing_status == "completed",
        "canonical_analysis": result.canonical_analysis,
        "scientifically_eligible": result.scientifically_eligible,
    }, indent=2, sort_keys=True))
    return 0

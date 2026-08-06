"""Explicit persisted-FeatureSet CLI for P5-B four-protocol validation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from .comparison_metrics_outputs import load_comparison_metrics_bundle
from .config import load_config
from .cross_mode_classification import (
    CrossModeClassificationInputError,
    CrossModeClassificationScope,
    analyze_cross_mode_classification,
)
from .cross_mode_classification_outputs import write_cross_mode_classification_outputs
from .dataset_quality_outputs import load_dataset_quality_bundle
from .schemas import DataOrigin, artifact_sha256, load_feature_set


@dataclass(frozen=True, slots=True)
class CrossModeInputEntry:
    artifact_id: str
    sample_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeInputEntry":
        required = {
            "artifact_id", "sample_id", "feature_base_path",
            "feature_npz_sha256", "feature_json_sha256",
        }
        if set(payload) != required:
            raise CrossModeClassificationInputError("cross-mode input FeatureSet fields must be explicit")
        return cls(**{name: str(payload[name]) for name in required})


@dataclass(frozen=True, slots=True)
class CrossModeInputManifest:
    schema_version: str
    classification_scope_id: str
    data_origin: DataOrigin
    run_purpose: str
    features: tuple[CrossModeInputEntry, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeInputManifest":
        required = {
            "schema_version", "classification_scope_id", "data_origin",
            "run_purpose", "features",
        }
        if set(payload) != required or payload.get("schema_version") != "1.0.0":
            raise CrossModeClassificationInputError("cross-mode input manifest fields/schema are invalid")
        result = cls(
            str(payload["schema_version"]), str(payload["classification_scope_id"]),
            DataOrigin(payload["data_origin"]), str(payload["run_purpose"]),
            tuple(CrossModeInputEntry.from_dict(item) for item in payload["features"]),
        )
        artifact_ids = tuple(item.artifact_id for item in result.features)
        if not artifact_ids or len(set(artifact_ids)) != len(artifact_ids):
            raise CrossModeClassificationInputError("cross-mode input artifact IDs must be non-empty and unique")
        return result


def _read(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise CrossModeClassificationInputError(f"expected mapping in {path}")
    return payload


def _resolve(value: str, parent: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def load_explicit_cross_mode_inputs(
    path: Path, scope: CrossModeClassificationScope
) -> tuple[dict[str, Any], tuple[dict[str, str], ...], CrossModeInputManifest]:
    manifest = CrossModeInputManifest.from_dict(_read(path))
    if manifest.classification_scope_id != scope.classification_scope_id:
        raise CrossModeClassificationInputError("cross-mode input/scope ID mismatch")
    if tuple(item.artifact_id for item in manifest.features) != tuple(
        item.artifact_id for item in scope.feature_references
    ):
        raise CrossModeClassificationInputError("cross-mode input order must exactly match scope")
    features: dict[str, Any] = {}
    records: list[dict[str, str]] = []
    for entry in manifest.features:
        base = _resolve(entry.feature_base_path, path.parent)
        if base.suffix:
            base = base.with_suffix("")
        for artifact, expected, role in (
            (base.with_suffix(".npz"), entry.feature_npz_sha256, "feature_set_npz"),
            (base.with_suffix(".json"), entry.feature_json_sha256, "feature_set_json"),
        ):
            if not artifact.is_file():
                raise FileNotFoundError(artifact)
            actual = artifact_sha256(artifact)
            if actual != expected.removeprefix("sha256:"):
                raise CrossModeClassificationInputError(f"cross-mode input hash mismatch: {artifact}")
            records.append(
                {
                    "artifact_id": entry.artifact_id, "artifact_role": role,
                    "path": artifact.as_posix(), "sha256": "sha256:" + actual,
                }
            )
        feature = load_feature_set(base)
        if feature.sample_id != entry.sample_id or feature.meta.data_origin is not manifest.data_origin:
            raise CrossModeClassificationInputError("cross-mode serialized identity/provenance mismatch")
        features[entry.artifact_id] = feature
    return features, tuple(records), manifest


def _failure(
    output: Path,
    scope: CrossModeClassificationScope,
    manifest: CrossModeInputManifest,
    error: Exception,
    known: Sequence[Mapping[str, str]],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0", "processing_status": "failed", "success": False,
        "classification_scope_id": scope.classification_scope_id,
        "scope_sha256": scope.sha256,
        "provenance": {
            "data_origin": manifest.data_origin.value,
            "run_purpose": manifest.run_purpose,
            "scientifically_eligible": False,
        },
        "known_inputs": list(known),
        "failure": {"exception_type": type(error).__name__, "message": str(error)},
    }
    path = output / "classification_manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "classification_manifest.sha256").write_text(
        "sha256:" + artifact_sha256(path) + "\n", encoding="ascii"
    )


def run_cross_mode_classification_cli(
    argv: Sequence[str] | None = None, *, project_root: Path | None = None
) -> int:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--dataset-qc-dir", type=Path, required=True)
    parser.add_argument("--comparison-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    resolved = load_config(args.config, default_path=root / "config" / "default.yaml")
    scope_path = args.scope.resolve()
    inputs_path = args.inputs.resolve()
    scope = CrossModeClassificationScope.from_dict(_read(scope_path))
    input_manifest = CrossModeInputManifest.from_dict(_read(inputs_path))
    if scope.run_purpose.value != resolved["run_purpose"] or input_manifest.run_purpose != resolved["run_purpose"]:
        raise CrossModeClassificationInputError("cross-mode run_purpose/config mismatch")
    output = (
        args.output_root.resolve() / input_manifest.data_origin.value /
        input_manifest.run_purpose / args.run_id / "cross_mode_classification"
    )
    if output.exists():
        raise FileExistsError(f"cross-mode classification output directory already exists: {output}")
    known: list[dict[str, str]] = [
        {"artifact_id": "__scope__", "artifact_role": "classification_scope", "path": scope_path.as_posix(), "sha256": "sha256:" + artifact_sha256(scope_path)},
        {"artifact_id": "__inputs__", "artifact_role": "classification_input_manifest", "path": inputs_path.as_posix(), "sha256": "sha256:" + artifact_sha256(inputs_path)},
    ]
    for artifact_id, role, path in (
        ("__dataset_qc__", "dataset_qc_manifest", args.dataset_qc_dir.resolve() / "dataset_qc_manifest.json"),
        ("__comparison__", "comparison_metrics_manifest", args.comparison_dir.resolve() / "metrics_manifest.json"),
    ):
        if path.is_file():
            known.append({"artifact_id": artifact_id, "artifact_role": role, "path": path.as_posix(), "sha256": "sha256:" + artifact_sha256(path)})
    try:
        features, feature_records, manifest = load_explicit_cross_mode_inputs(inputs_path, scope)
        known.extend(feature_records)
        p2b = load_dataset_quality_bundle(args.dataset_qc_dir)
        comparison = load_comparison_metrics_bundle(args.comparison_dir)
        comparison_manifest = args.comparison_dir.resolve() / "metrics_manifest.json"
        comparison["manifest_sha256"] = "sha256:" + artifact_sha256(comparison_manifest)
        result = analyze_cross_mode_classification(
            features, scope, resolved["classification"],
            dataset_qc_result=p2b, comparison_bundle=comparison,
        )
        write_cross_mode_classification_outputs(
            result, scope, output,
            provenance={
                "data_origin": manifest.data_origin.value,
                "run_purpose": manifest.run_purpose,
                "scientifically_eligible": result.scientifically_eligible,
            },
            input_artifacts=tuple(known),
            versions={
                "pipeline": resolved["pipeline_version"],
                "config": resolved["schema_versions"]["config"],
                "measurement": resolved["schema_versions"]["measurement"],
                "feature": resolved["schema_versions"]["feature"],
            },
        )
    except Exception as error:
        _failure(output, scope, input_manifest, error, known)
        print(json.dumps({"output_directory": output.as_posix(), "processing_status": "failed", "success": False, "error": str(error)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps({"output_directory": output.as_posix(), "processing_status": result.processing_status, "success": result.processing_status == "completed", "canonical_analysis": result.canonical_analysis, "scientifically_eligible": result.scientifically_eligible}, indent=2, sort_keys=True))
    return 0

"""Explicit-input CLI orchestration for P6-A sweep HR calibration."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

import yaml

from .config import load_config
from .dataset_quality_outputs import load_dataset_quality_bundle
from .hr_analysis import (
    HRCalibrationScope,
    HRInputError,
    analyze_sweep_hr_calibration,
)
from .hr_outputs import write_hr_calibration_outputs
from .schemas import DataOrigin, DatasetRole, FeatureSet, artifact_sha256, load_feature_set


HR_CALIBRATION_INPUT_MANIFEST_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class HRCalibrationInputEntry:
    sample_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str
    feature_content_sha256: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRCalibrationInputEntry":
        required = {"sample_id", "feature_base_path", "feature_npz_sha256", "feature_json_sha256", "feature_content_sha256"}
        if set(value) != required:
            raise HRInputError("HR calibration input entry fields must be explicit")
        return cls(**{name: str(value[name]) for name in required})

    def to_dict(self) -> dict[str, str]:
        return {
            "sample_id": self.sample_id,
            "feature_base_path": self.feature_base_path,
            "feature_npz_sha256": self.feature_npz_sha256,
            "feature_json_sha256": self.feature_json_sha256,
            "feature_content_sha256": self.feature_content_sha256,
        }


@dataclass(frozen=True, slots=True)
class HRCalibrationInputManifest:
    schema_version: str
    hr_calibration_scope_id: str
    data_origin: DataOrigin
    dataset_role: DatasetRole
    measurements: tuple[HRCalibrationInputEntry, ...]

    def __post_init__(self) -> None:
        if self.schema_version != HR_CALIBRATION_INPUT_MANIFEST_SCHEMA_VERSION:
            raise HRInputError("unsupported HR calibration input manifest schema")
        if not self.hr_calibration_scope_id.strip():
            raise HRInputError("HR calibration input manifest scope ID is required")
        sample_ids = tuple(item.sample_id for item in self.measurements)
        if not sample_ids or len(sample_ids) != len(set(sample_ids)):
            raise HRInputError("HR calibration input sample IDs must be non-empty and unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hr_calibration_scope_id": self.hr_calibration_scope_id,
            "data_origin": self.data_origin.value,
            "dataset_role": self.dataset_role.value,
            "measurements": [item.to_dict() for item in self.measurements],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRCalibrationInputManifest":
        return cls(
            str(value["schema_version"]),
            str(value["hr_calibration_scope_id"]),
            DataOrigin(value["data_origin"]),
            DatasetRole(value["dataset_role"]),
            tuple(HRCalibrationInputEntry.from_dict(item) for item in value["measurements"]),
        )


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HRInputError(f"expected mapping in {path}")
    return value


def _resolved(value: str, parent: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def load_explicit_hr_calibration_inputs(
    input_manifest_path: str | Path,
    scope: HRCalibrationScope,
) -> tuple[tuple[FeatureSet, ...], tuple[dict[str, str], ...], HRCalibrationInputManifest]:
    """Load only the exact FeatureSet paths declared by the immutable manifest."""
    manifest_path = Path(input_manifest_path).resolve()
    manifest = HRCalibrationInputManifest.from_dict(_read_mapping(manifest_path))
    if manifest.hr_calibration_scope_id != scope.hr_calibration_scope_id:
        raise HRInputError("HR input manifest scope ID mismatch")
    if tuple(item.sample_id for item in manifest.measurements) != scope.ordered_sample_ids:
        raise HRInputError("HR input manifest order must exactly match scope")
    if manifest.data_origin is not scope.data_origin or manifest.dataset_role is not scope.dataset_role:
        raise HRInputError("HR input manifest provenance mismatch")
    scope_members = {item.sample_id: item for item in scope.members}
    features: list[FeatureSet] = []
    audit: list[dict[str, str]] = []
    for entry in manifest.measurements:
        base = _resolved(entry.feature_base_path, manifest_path.parent)
        if base.suffix:
            base = base.with_suffix("")
        paths = (
            (base.with_suffix(".npz"), entry.feature_npz_sha256, "feature_npz"),
            (base.with_suffix(".json"), entry.feature_json_sha256, "feature_json"),
        )
        for path, expected, role in paths:
            if not path.is_file():
                raise FileNotFoundError(f"explicit HR calibration input is missing: {path}")
            actual = artifact_sha256(path)
            if actual != expected:
                raise HRInputError(f"HR calibration input hash mismatch: {path}")
            audit.append({"sample_id": entry.sample_id, "artifact_role": role, "path": path.as_posix(), "sha256": actual})
        member = scope_members[entry.sample_id]
        if (
            member.feature_base_path != entry.feature_base_path
            or member.feature_npz_sha256 != entry.feature_npz_sha256
            or member.feature_json_sha256 != entry.feature_json_sha256
            or member.feature_content_sha256 != entry.feature_content_sha256
        ):
            raise HRInputError(f"HR scope/input manifest mismatch: {entry.sample_id}")
        feature = load_feature_set(base)
        from .dataset_quality_control import feature_set_content_sha256
        if feature.sample_id != entry.sample_id or feature_set_content_sha256(feature) != entry.feature_content_sha256:
            raise HRInputError(f"HR serialized FeatureSet identity mismatch: {entry.sample_id}")
        features.append(feature)
    audit.extend((
        {"sample_id": "__scope__", "artifact_role": "hr_scope", "path": "", "sha256": ""},
        {"sample_id": "__scope__", "artifact_role": "hr_input_manifest", "path": manifest_path.as_posix(), "sha256": artifact_sha256(manifest_path)},
    ))
    return tuple(features), tuple(audit), manifest


def _git_commit(project_root: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root, check=True, capture_output=True, text=True).stdout.strip()


def execute_hr_calibration(
    *,
    config_path: str | Path,
    scope_path: str | Path,
    input_manifest_path: str | Path,
    dataset_qc_directory: str | Path,
    output_root: str | Path,
    run_id: str,
    project_root: str | Path,
) -> Path:
    """Execute one explicit P6-A calibration and return its isolated bundle path."""
    config = load_config(config_path)
    scope_file = Path(scope_path).resolve()
    inputs_file = Path(input_manifest_path).resolve()
    scope = HRCalibrationScope.from_dict(_read_mapping(scope_file))
    output = Path(output_root).resolve() / scope.data_origin.value / scope.run_purpose.value / run_id / "hr_calibration"
    if output.exists():
        raise FileExistsError(f"HR calibration output directory already exists: {output}")
    try:
        features, audit, _ = load_explicit_hr_calibration_inputs(inputs_file, scope)
        audit = tuple(
            ({**item, "path": scope_file.as_posix(), "sha256": artifact_sha256(scope_file)} if item["artifact_role"] == "hr_scope" else item)
            for item in audit
        )
        p2b = load_dataset_quality_bundle(dataset_qc_directory)
        result = analyze_sweep_hr_calibration(features, scope, p2b, config["hr_calibration"])
        write_hr_calibration_outputs(
            result,
            scope,
            config["hr_calibration"],
            output,
            input_artifacts=audit,
            git_commit=_git_commit(Path(project_root).resolve()),
            random_state=int(config["random_state"]),
        )
    except Exception as exc:
        if not output.exists():
            output.mkdir(parents=True, exist_ok=False)
        partial = []
        for path in sorted(output.iterdir(), key=lambda item: item.name):
            if path.is_file() and path.name not in {"hr_calibration_manifest.json", "hr_calibration_manifest.sha256"}:
                partial.append({"path": path.name, "sha256": artifact_sha256(path), "size_bytes": path.stat().st_size})
        known_inputs = []
        for role, path in (("hr_scope", scope_file), ("hr_input_manifest", inputs_file)):
            if path.is_file():
                known_inputs.append({"artifact_role": role, "path": path.as_posix(), "sha256": artifact_sha256(path)})
        payload = {
            "schema_version": "1.0.0",
            "processing_status": "failed",
            "success": False,
            "hr_calibration_scope_id": scope.hr_calibration_scope_id,
            "scope_sha256": scope.sha256,
            "calibration_status": None,
            "frozen_for_research": False,
            "scientifically_eligible": False,
            "provenance": {"data_origin": scope.data_origin.value, "dataset_role": scope.dataset_role.value, "run_purpose": scope.run_purpose.value},
            "known_inputs": known_inputs,
            "artifacts": partial,
            "failure": {"exception_type": type(exc).__name__, "message": str(exc)},
        }
        manifest_path = output / "hr_calibration_manifest.json"
        manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        (output / "hr_calibration_manifest.sha256").write_text(
            f"{artifact_sha256(manifest_path)}  {manifest_path.name}\n", encoding="ascii"
        )
        raise
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--dataset-qc-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    execute_hr_calibration(
        config_path=args.config,
        scope_path=args.scope,
        input_manifest_path=args.inputs,
        dataset_qc_directory=args.dataset_qc_dir,
        output_root=args.output_root,
        run_id=args.run_id,
        project_root=args.project_root,
    )
    return 0

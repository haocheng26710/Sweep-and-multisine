"""Explicit-input CLI orchestration for offline P6-B multisine HR readout."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

import yaml

from .config import load_config
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .dataset_quality_outputs import load_dataset_quality_bundle
from .hr_outputs import load_hr_calibration_authority
from .hr_readout import (
    HRReadoutInputError,
    HRReadoutScope,
    analyze_multisine_hr_readout,
)
from .hr_readout_outputs import write_hr_readout_outputs
from .schemas import (
    DataOrigin,
    DatasetRole,
    FeatureSet,
    artifact_sha256,
    load_feature_set,
)


HR_READOUT_INPUT_MANIFEST_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class HRReadoutInputEntry:
    sample_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str
    feature_content_sha256: str
    feature_contract_sha256: str

    def __post_init__(self) -> None:
        if not all(str(getattr(self, name)).strip() for name in self.__dataclass_fields__):
            raise HRReadoutInputError("HR readout input entry fields are required")

    def to_dict(self) -> dict[str, str]:
        return {name: str(getattr(self, name)) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRReadoutInputEntry":
        expected = set(cls.__dataclass_fields__)
        if set(value) != expected:
            raise HRReadoutInputError("HR readout input entry fields must be explicit")
        return cls(**{name: str(value[name]) for name in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class HRReadoutInputManifest:
    schema_version: str
    hr_readout_scope_id: str
    data_origin: DataOrigin
    dataset_role: DatasetRole
    measurements: tuple[HRReadoutInputEntry, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_origin", DataOrigin(self.data_origin))
        object.__setattr__(self, "dataset_role", DatasetRole(self.dataset_role))
        if self.schema_version != HR_READOUT_INPUT_MANIFEST_SCHEMA_VERSION:
            raise HRReadoutInputError("unsupported HR readout input manifest schema")
        if not self.hr_readout_scope_id.strip():
            raise HRReadoutInputError("HR readout input manifest scope ID is required")
        sample_ids = tuple(item.sample_id for item in self.measurements)
        if not sample_ids or len(sample_ids) != len(set(sample_ids)):
            raise HRReadoutInputError("HR readout input sample IDs must be non-empty and unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "hr_readout_scope_id": self.hr_readout_scope_id,
            "data_origin": self.data_origin.value,
            "dataset_role": self.dataset_role.value,
            "measurements": [item.to_dict() for item in self.measurements],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "HRReadoutInputManifest":
        expected = {
            "schema_version", "hr_readout_scope_id", "data_origin",
            "dataset_role", "measurements",
        }
        if set(value) != expected:
            raise HRReadoutInputError("HR readout input manifest fields must be explicit")
        return cls(
            str(value["schema_version"]),
            str(value["hr_readout_scope_id"]),
            DataOrigin(value["data_origin"]),
            DatasetRole(value["dataset_role"]),
            tuple(HRReadoutInputEntry.from_dict(item) for item in value["measurements"]),
        )


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    text = path.read_text(encoding="utf-8")
    value = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    if not isinstance(value, dict):
        raise HRReadoutInputError(f"expected mapping in {path}")
    return value


def _resolved(value: str, parent: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (parent / path).resolve()


def load_explicit_hr_readout_inputs(
    input_manifest_path: str | Path,
    scope: HRReadoutScope,
) -> tuple[tuple[FeatureSet, ...], tuple[dict[str, str], ...], HRReadoutInputManifest]:
    """Load only exact persisted P3-C FeatureSets listed by the manifest."""
    manifest_path = Path(input_manifest_path).resolve()
    manifest = HRReadoutInputManifest.from_dict(_read_mapping(manifest_path))
    if manifest.hr_readout_scope_id != scope.hr_readout_scope_id:
        raise HRReadoutInputError("HR readout input manifest scope ID mismatch")
    if manifest.data_origin is not scope.data_origin or manifest.dataset_role is not scope.dataset_role:
        raise HRReadoutInputError("HR readout input manifest provenance mismatch")
    if tuple(item.sample_id for item in manifest.measurements) != scope.ordered_sample_ids:
        raise HRReadoutInputError("HR readout input order must exactly match scope")
    members = {item.sample_id: item for item in scope.members}
    features: list[FeatureSet] = []
    audit: list[dict[str, str]] = []
    for entry in manifest.measurements:
        member = members[entry.sample_id]
        comparable = (
            "feature_base_path", "feature_npz_sha256", "feature_json_sha256",
            "feature_content_sha256", "feature_contract_sha256",
        )
        if any(getattr(entry, name) != getattr(member, name) for name in comparable):
            raise HRReadoutInputError(
                f"HR readout scope/input manifest mismatch: {entry.sample_id}"
            )
        base = _resolved(entry.feature_base_path, manifest_path.parent)
        if base.suffix:
            base = base.with_suffix("")
        for role, path, expected in (
            ("feature_npz", base.with_suffix(".npz"), entry.feature_npz_sha256),
            ("feature_json", base.with_suffix(".json"), entry.feature_json_sha256),
        ):
            if not path.is_file():
                raise FileNotFoundError(f"explicit HR readout input is missing: {path}")
            actual = artifact_sha256(path)
            if actual != expected:
                raise HRReadoutInputError(f"HR readout input hash mismatch: {path}")
            audit.append({
                "sample_id": entry.sample_id,
                "artifact_role": role,
                "path": path.as_posix(),
                "sha256": actual,
            })
        feature = load_feature_set(base)
        if (
            feature.sample_id != entry.sample_id
            or feature_set_content_sha256(feature) != entry.feature_content_sha256
            or feature_contract_sha256(feature) != entry.feature_contract_sha256
        ):
            raise HRReadoutInputError(
                f"HR readout serialized FeatureSet identity mismatch: {entry.sample_id}"
            )
        features.append(feature)
    audit.append({
        "sample_id": "__scope__",
        "artifact_role": "hr_readout_input_manifest",
        "path": manifest_path.as_posix(),
        "sha256": artifact_sha256(manifest_path),
    })
    return tuple(features), tuple(audit), manifest


def _load_exact_calibration(scope: HRReadoutScope, scope_parent: Path):
    reference = scope.calibration_reference
    paths = {
        "calibration_json": _resolved(reference.calibration_json_path, scope_parent),
        "calibration_manifest": _resolved(reference.calibration_manifest_path, scope_parent),
        "calibration_manifest_digest": _resolved(
            reference.calibration_manifest_digest_path, scope_parent
        ),
    }
    expected = {
        "calibration_json": reference.calibration_json_sha256,
        "calibration_manifest": reference.calibration_manifest_sha256,
        "calibration_manifest_digest": reference.calibration_manifest_digest_sha256,
    }
    for role, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        if artifact_sha256(path) != expected[role]:
            raise HRReadoutInputError(f"HR calibration exact-file hash mismatch: {path}")
    directory = paths["calibration_manifest"].parent
    standard = {
        "calibration_json": directory / "hr_calibration.json",
        "calibration_manifest": directory / "hr_calibration_manifest.json",
        "calibration_manifest_digest": directory / "hr_calibration_manifest.sha256",
    }
    if paths != {name: path.resolve() for name, path in standard.items()}:
        raise HRReadoutInputError("calibration reference must identify one standard P6-A bundle")
    authority = load_hr_calibration_authority(directory)
    if authority.result.calibration_id != reference.calibration_id:
        raise HRReadoutInputError("calibration semantic ID mismatch")
    audit = tuple({
        "sample_id": "__calibration__",
        "artifact_role": role,
        "path": path.as_posix(),
        "sha256": artifact_sha256(path),
    } for role, path in sorted(paths.items()))
    return authority, audit


def _git_commit(project_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def execute_hr_readout(
    *,
    config_path: str | Path,
    scope_path: str | Path,
    input_manifest_path: str | Path,
    dataset_qc_directory: str | Path,
    output_root: str | Path,
    run_id: str,
    project_root: str | Path,
) -> Path:
    """Execute one immutable, explicit P6-B run without raw WAV access."""
    config = load_config(config_path)
    scope_file = Path(scope_path).resolve()
    input_file = Path(input_manifest_path).resolve()
    scope = HRReadoutScope.from_dict(_read_mapping(scope_file))
    output = (
        Path(output_root).resolve() / scope.data_origin.value /
        scope.run_purpose.value / run_id / "hr_readout"
    )
    if output.exists():
        raise FileExistsError(f"HR readout output directory already exists: {output}")
    try:
        if scope.random_state != int(config["random_state"]):
            raise HRReadoutInputError("HR readout scope/config random_state mismatch")
        features, feature_audit, _ = load_explicit_hr_readout_inputs(input_file, scope)
        authority, calibration_audit = _load_exact_calibration(scope, scope_file.parent)
        p2b = load_dataset_quality_bundle(dataset_qc_directory)
        analysis = analyze_multisine_hr_readout(
            features, scope, p2b, authority, config["hr_readout"]
        )
        p2_dir = Path(dataset_qc_directory).resolve()
        input_artifacts = [
            *feature_audit,
            *calibration_audit,
            {"sample_id": "__scope__", "artifact_role": "hr_readout_scope",
             "path": scope_file.as_posix(), "sha256": artifact_sha256(scope_file)},
        ]
        for role, name in (
            ("dataset_qc_result", "dataset_qc.json"),
            ("dataset_qc_manifest", "dataset_qc_manifest.json"),
            ("dataset_qc_manifest_digest", "dataset_qc_manifest.sha256"),
        ):
            path = p2_dir / name
            input_artifacts.append({
                "sample_id": "__p2b__", "artifact_role": role,
                "path": path.as_posix(), "sha256": artifact_sha256(path),
            })
        write_hr_readout_outputs(
            analysis, scope, config["hr_readout"], output,
            input_artifacts=input_artifacts,
            git_commit=_git_commit(Path(project_root).resolve()),
            random_state=int(config["random_state"]),
        )
    except Exception as exc:
        if not output.exists():
            output.mkdir(parents=True, exist_ok=False)
        for success_marker in (
            output / "hr_readout_manifest.json",
            output / "hr_readout_manifest.sha256",
        ):
            if success_marker.is_file():
                success_marker.unlink()
        partial_artifacts = [
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": artifact_sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(output.rglob("*"), key=lambda item: item.as_posix())
            if path.is_file()
            and path.name not in {
                "hr_readout_failure_manifest.json",
                "hr_readout_failure_manifest.sha256",
            }
        ]
        known_inputs = []
        for role, path in (
            ("hr_readout_scope", scope_file),
            ("hr_readout_input_manifest", input_file),
        ):
            if path.is_file():
                known_inputs.append({
                    "artifact_role": role, "path": path.as_posix(),
                    "sha256": artifact_sha256(path),
                })
        payload = {
            "schema_version": "1.0.0",
            "processing_status": "failed",
            "success": False,
            "hr_readout_scope_id": scope.hr_readout_scope_id,
            "scope_sha256": scope.sha256,
            "scientifically_eligible": False,
            "deployment_allowed": False,
            "provenance": {
                "data_origin": scope.data_origin.value,
                "dataset_role": scope.dataset_role.value,
                "run_purpose": scope.run_purpose.value,
            },
            "known_inputs": known_inputs,
            "partial_artifacts": partial_artifacts,
            "failure": {"exception_type": type(exc).__name__, "message": str(exc)},
        }
        manifest_path = output / "hr_readout_failure_manifest.json"
        manifest_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output / "hr_readout_failure_manifest.sha256").write_text(
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
    execute_hr_readout(
        config_path=args.config,
        scope_path=args.scope,
        input_manifest_path=args.inputs,
        dataset_qc_directory=args.dataset_qc_dir,
        output_root=args.output_root,
        run_id=args.run_id,
        project_root=args.project_root,
    )
    return 0

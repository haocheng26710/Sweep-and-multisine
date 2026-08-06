"""Explicit-file CLI for DEV-C14 P9-C cross-mode bridge calibration."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from .config import load_config
from .cross_mode_bridge import (
    CrossModeBridgeInputError,
    P9CrossModeBridgeScope,
    analyze_cross_mode_bridge,
)
from .cross_mode_bridge_outputs import write_cross_mode_bridge_outputs
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .schemas import FeatureSet, MeasurementMode, artifact_sha256, load_feature_set


@dataclass(frozen=True, slots=True)
class LineageArtifactReference:
    role: str
    path: str
    file_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LineageArtifactReference":
        if set(payload) != set(cls.__dataclass_fields__):
            raise CrossModeBridgeInputError("lineage fields must be explicit")
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class BridgeFeatureInput:
    artifact_id: str
    sample_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str
    feature_content_sha256: str
    feature_contract_sha256: str
    lineage: tuple[LineageArtifactReference, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in self.__slots__}
        payload["lineage"] = [item.to_dict() for item in self.lineage]
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BridgeFeatureInput":
        if set(payload) != set(cls.__dataclass_fields__):
            raise CrossModeBridgeInputError("bridge FeatureSet fields must be explicit")
        value = dict(payload)
        value["lineage"] = tuple(LineageArtifactReference.from_dict(item) for item in value["lineage"])
        return cls(**value)


@dataclass(frozen=True, slots=True)
class FoldAuthorityInput:
    outer_fold_id: str
    role: str
    path: str
    file_sha256: str
    authority_semantic_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FoldAuthorityInput":
        if set(payload) != set(cls.__dataclass_fields__):
            raise CrossModeBridgeInputError("fold authority fields must be explicit")
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class CrossModeInputManifest:
    schema_version: str
    analysis_scope_id: str
    analysis_scope_sha256: str
    sealed_final_test_sample_ids: tuple[str, ...]
    sealed_final_test_sha256: str
    features: tuple[BridgeFeatureInput, ...]
    fold_authorities: tuple[FoldAuthorityInput, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0":
            raise CrossModeBridgeInputError("CrossModeInputManifest schema_version must be 1.0.0")
        artifact_ids = [item.artifact_id for item in self.features]
        if not artifact_ids or len(artifact_ids) != len(set(artifact_ids)):
            raise CrossModeBridgeInputError("input FeatureSet artifact IDs must be non-empty and unique")
        authority_keys = [(item.outer_fold_id, item.role) for item in self.fold_authorities]
        if not authority_keys or len(authority_keys) != len(set(authority_keys)):
            raise CrossModeBridgeInputError("fold authority roles must be non-empty and unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_scope_id": self.analysis_scope_id,
            "analysis_scope_sha256": self.analysis_scope_sha256,
            "sealed_final_test_sample_ids": list(self.sealed_final_test_sample_ids),
            "sealed_final_test_sha256": self.sealed_final_test_sha256,
            "features": [item.to_dict() for item in self.features],
            "fold_authorities": [item.to_dict() for item in self.fold_authorities],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CrossModeInputManifest":
        if set(payload) != set(cls.__dataclass_fields__):
            raise CrossModeBridgeInputError("CrossModeInputManifest fields must be explicit")
        value = dict(payload)
        value["sealed_final_test_sample_ids"] = tuple(value["sealed_final_test_sample_ids"])
        value["features"] = tuple(BridgeFeatureInput.from_dict(item) for item in value["features"])
        value["fold_authorities"] = tuple(FoldAuthorityInput.from_dict(item) for item in value["fold_authorities"])
        return cls(**value)


_SWEEP_LINEAGE = {"p3c_preprocessing_manifest"}
_MULTISINE_LINEAGE = _SWEEP_LINEAGE | {
    "p7_stimulus_manifest",
    "p8_run_manifest",
    "p8_spectrum_npz",
    "p8_spectrum_json",
    "p8_tone_quality",
}
_AUTHORITY_ROLES = {
    "p2b_result": "p2b_result_sha256",
    "p4b_result": "p4b_result_sha256",
    "p9a_selection_scope": "p9a_selection_scope_sha256",
    "p9a_selection_artifact": "p9a_selection_artifact_sha256",
    "p9a_manifest": "p9a_manifest_sha256",
    "p9b_result": "p9b_result_sha256",
    "p9b_manifest": "p9b_manifest_sha256",
}


def load_cross_mode_bridge_inputs(
    manifest_path: str | Path,
    scope: P9CrossModeBridgeScope,
) -> tuple[dict[str, FeatureSet], dict[str, str], CrossModeInputManifest]:
    """Load only explicitly listed FeatureSets and hash-check upstream lineage."""
    path = Path(manifest_path)
    manifest = CrossModeInputManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if manifest.analysis_scope_id != scope.analysis_scope_id or manifest.analysis_scope_sha256 != scope.sha256:
        raise CrossModeBridgeInputError("input manifest P9-C scope mismatch")
    if (
        manifest.sealed_final_test_sample_ids != scope.sealed_final_test_sample_ids
        or manifest.sealed_final_test_sha256 != scope.sealed_final_test_sha256
    ):
        raise CrossModeBridgeInputError("input manifest final_test seal mismatch")
    expected_artifacts = {
        artifact for pair in scope.pairs
        for artifact in (pair.sweep_artifact_id, pair.multisine_artifact_id)
    }
    if {item.artifact_id for item in manifest.features} != expected_artifacts:
        raise CrossModeBridgeInputError("input manifest FeatureSets must exactly match scope")
    hashes = {str(path.resolve()): artifact_sha256(path)}
    features: dict[str, FeatureSet] = {}
    for item in manifest.features:
        base = Path(item.feature_base_path)
        npz_path, json_path = base.with_suffix(".npz"), base.with_suffix(".json")
        if artifact_sha256(npz_path) != item.feature_npz_sha256 or artifact_sha256(json_path) != item.feature_json_sha256:
            raise CrossModeBridgeInputError("P3-C FeatureSet file hash mismatch")
        feature = load_feature_set(base)
        if (
            feature.sample_id != item.sample_id
            or feature_set_content_sha256(feature) != item.feature_content_sha256
            or feature_contract_sha256(feature) != item.feature_contract_sha256
        ):
            raise CrossModeBridgeInputError("P3-C FeatureSet semantic hash mismatch")
        expected_lineage = (
            _MULTISINE_LINEAGE
            if feature.source_measurement_mode is MeasurementMode.SCHROEDER_MULTISINE
            else _SWEEP_LINEAGE
        )
        roles = [reference.role for reference in item.lineage]
        if set(roles) != expected_lineage or len(roles) != len(set(roles)):
            raise CrossModeBridgeInputError(
                f"{item.artifact_id} lineage roles are incomplete or duplicated"
            )
        for reference in item.lineage:
            lineage_path = Path(reference.path)
            if artifact_sha256(lineage_path) != reference.file_sha256:
                raise CrossModeBridgeInputError(f"lineage hash mismatch: {reference.role}")
            hashes[str(lineage_path.resolve())] = reference.file_sha256
        features[item.artifact_id] = feature
        hashes[str(npz_path.resolve())] = item.feature_npz_sha256
        hashes[str(json_path.resolve())] = item.feature_json_sha256

    authorities = {(item.outer_fold_id, item.role): item for item in manifest.fold_authorities}
    for fold in scope.outer_folds:
        required = {(fold.outer_fold_id, role) for role in _AUTHORITY_ROLES}
        if required - set(authorities):
            raise CrossModeBridgeInputError(f"fold authority is incomplete: {fold.outer_fold_id}")
        for role, field in _AUTHORITY_ROLES.items():
            reference = authorities[(fold.outer_fold_id, role)]
            authority_path = Path(reference.path)
            if artifact_sha256(authority_path) != reference.file_sha256:
                raise CrossModeBridgeInputError(f"authority hash mismatch: {role}")
            if reference.authority_semantic_sha256 != getattr(fold, field):
                raise CrossModeBridgeInputError(f"authority semantic hash mismatch: {role}")
            snapshot = json.loads(authority_path.read_text(encoding="utf-8"))
            if (
                snapshot.get("authority_role") != role
                or snapshot.get("outer_fold_id") != fold.outer_fold_id
                or snapshot.get("authority_semantic_sha256") != getattr(fold, field)
            ):
                raise CrossModeBridgeInputError(f"authority snapshot mismatch: {role}")
            if snapshot.get("selection_scope_role") != "fold_training_selection":
                raise CrossModeBridgeInputError("global selection cannot be used for outer-fold P9-C")
            if tuple(snapshot.get("training_pair_ids", ())) != fold.training_pair_ids:
                raise CrossModeBridgeInputError("authority training membership mismatch")
            if tuple(snapshot.get("held_out_physical_state_ids", ())) != fold.held_out_physical_state_ids:
                raise CrossModeBridgeInputError("authority held physical-state mismatch")
            if tuple(snapshot.get("ordered_tone_ids", ())) != fold.ordered_tone_ids:
                raise CrossModeBridgeInputError("authority ordered tone IDs mismatch")
            if snapshot.get("selected_subset_sha256") != fold.selected_subset_sha256:
                raise CrossModeBridgeInputError("authority selected subset hash mismatch")
            if snapshot.get("candidate_universe_sha256") != fold.candidate_universe_sha256:
                raise CrossModeBridgeInputError("authority CandidateToneUniverse hash mismatch")
            hashes[str(authority_path.resolve())] = reference.file_sha256
    if set(authorities) != {
        (fold.outer_fold_id, role) for fold in scope.outer_folds for role in _AUTHORITY_ROLES
    }:
        raise CrossModeBridgeInputError("unexpected fold authority record")
    return features, hashes, manifest


def _safe_run_id(run_id: str) -> str:
    candidate = Path(run_id)
    if not run_id.strip() or candidate.name != run_id or run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
        raise CrossModeBridgeInputError("run_id must be one non-empty path component")
    return run_id


def _git_state(project_root: Path) -> tuple[str, bool]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project_root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=project_root, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return commit, dirty


def run_cross_mode_bridge_command(argv: Sequence[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run explicit-scope P9-C cross-mode bridge calibration")
    parser.add_argument("--config", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config).resolve()
    scope_path = Path(args.scope).resolve()
    inputs_path = Path(args.inputs).resolve()
    resolved = load_config(config_path, default_path=project_root / "config" / "default.yaml")
    bridge_config = resolved["cross_mode_bridge"]
    if bridge_config["enabled"] is not True:
        raise CrossModeBridgeInputError("cross_mode_bridge.enabled must be true")
    scope = P9CrossModeBridgeScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    if tuple(bridge_config["methods"]) != scope.calibration_methods:
        raise CrossModeBridgeInputError("config/scope calibration methods mismatch")
    if tuple(bridge_config["classification"]["models"]) != scope.classification_models:
        raise CrossModeBridgeInputError("config/scope classification models mismatch")
    features, input_hashes, manifest = load_cross_mode_bridge_inputs(inputs_path, scope)
    input_hashes.update({
        str(config_path): artifact_sha256(config_path),
        str(scope_path): artifact_sha256(scope_path),
        str(inputs_path): artifact_sha256(inputs_path),
    })
    result = analyze_cross_mode_bridge(features, scope, bridge_config)
    output = (
        Path(args.output_root).resolve() / "simulated" / "software_validation"
        / _safe_run_id(args.run_id) / "cross_mode_bridge"
    )
    commit, dirty = _git_state(project_root)
    paths = write_cross_mode_bridge_outputs(
        result, scope, bridge_config, manifest.to_dict(), output,
        input_file_hashes=input_hashes, git_commit=commit, git_dirty=dirty,
    )
    return {
        "output_directory": str(output),
        "processing_status": result.processing_status,
        "result_sha256": result.sha256,
        "artifact_count": len(paths),
        "matched_pair_count": len(scope.pairs),
        "outer_fold_count": len(scope.outer_folds),
        "tone_counts_by_fold": {
            item.outer_fold_id: len(item.ordered_tone_ids) for item in scope.outer_folds
        },
        "scientifically_eligible": False,
        "deployment_eligible": False,
        "canonical_analysis": False,
        "final_test_read": False,
    }


def main() -> None:
    print(json.dumps(run_cross_mode_bridge_command(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

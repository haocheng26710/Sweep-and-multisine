"""Explicit-file CLI for DEV-C13 P9-B projection ablation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from .config import load_config
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .projection_ablation import (
    FoldSelectionAuthority,
    P9ProjectionAblationScope,
    ProjectionAblationInputError,
    analyze_projection_ablation,
)
from .projection_ablation_outputs import write_projection_ablation_outputs
from .schemas import FeatureSet, artifact_sha256, load_feature_set
from .sweep_multisine_bridge import CandidateToneUniverse, ToneSelectionScope
from .tone_selection_outputs import load_tone_selection_bundle


@dataclass(frozen=True, slots=True)
class ProjectionFeatureInput:
    sample_id: str
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str
    feature_content_sha256: str
    feature_contract_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProjectionFeatureInput":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class FoldSelectionInput:
    outer_fold_id: str
    selection_scope_path: str
    selection_scope_file_sha256: str
    tone_selection_directory: str
    tone_selection_manifest_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in self.__slots__}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FoldSelectionInput":
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ProjectionAblationInputManifest:
    schema_version: str
    analysis_scope_id: str
    analysis_scope_sha256: str
    candidate_universe_id: str
    candidate_universe_sha256: str
    features: tuple[ProjectionFeatureInput, ...]
    fold_selections: tuple[FoldSelectionInput, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0" or not self.features or not self.fold_selections:
            raise ProjectionAblationInputError("projection-ablation input manifest is incomplete")
        if len({item.sample_id for item in self.features}) != len(self.features):
            raise ProjectionAblationInputError("projection-ablation feature IDs must be unique")
        if len({item.outer_fold_id for item in self.fold_selections}) != len(self.fold_selections):
            raise ProjectionAblationInputError("projection-ablation fold inputs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "analysis_scope_id": self.analysis_scope_id,
            "analysis_scope_sha256": self.analysis_scope_sha256,
            "candidate_universe_id": self.candidate_universe_id,
            "candidate_universe_sha256": self.candidate_universe_sha256,
            "features": [item.to_dict() for item in self.features],
            "fold_selections": [item.to_dict() for item in self.fold_selections],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProjectionAblationInputManifest":
        value = dict(payload)
        value["features"] = tuple(ProjectionFeatureInput.from_dict(item) for item in value["features"])
        value["fold_selections"] = tuple(FoldSelectionInput.from_dict(item) for item in value["fold_selections"])
        return cls(**value)


def load_projection_ablation_inputs(
    manifest_path: str | Path,
    scope: P9ProjectionAblationScope,
    universe: CandidateToneUniverse,
) -> tuple[dict[str, FeatureSet], dict[str, FoldSelectionAuthority], dict[str, str]]:
    """Load exactly listed FeatureSets and P9-A bundles; never discover directories."""
    path = Path(manifest_path)
    manifest = ProjectionAblationInputManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if manifest.analysis_scope_id != scope.analysis_scope_id or manifest.analysis_scope_sha256 != scope.sha256:
        raise ProjectionAblationInputError("input manifest P9-B scope mismatch")
    if manifest.candidate_universe_id != universe.candidate_universe_id or manifest.candidate_universe_sha256 != universe.sha256:
        raise ProjectionAblationInputError("input manifest candidate universe mismatch")
    if {item.sample_id for item in manifest.features} != {item.sample_id for item in scope.members}:
        raise ProjectionAblationInputError("input manifest FeatureSets must exactly match scope")
    hashes: dict[str, str] = {str(path.resolve()): artifact_sha256(path)}
    features: dict[str, FeatureSet] = {}
    for item in manifest.features:
        base = Path(item.feature_base_path)
        npz_path, json_path = base.with_suffix(".npz"), base.with_suffix(".json")
        if artifact_sha256(npz_path) != item.feature_npz_sha256 or artifact_sha256(json_path) != item.feature_json_sha256:
            raise ProjectionAblationInputError("P3-C FeatureSet file hash mismatch")
        feature = load_feature_set(base)
        if feature.sample_id != item.sample_id or feature_set_content_sha256(feature) != item.feature_content_sha256 or feature_contract_sha256(feature) != item.feature_contract_sha256:
            raise ProjectionAblationInputError("P3-C FeatureSet semantic hash mismatch")
        features[item.sample_id] = feature
        hashes[str(npz_path.resolve())] = item.feature_npz_sha256
        hashes[str(json_path.resolve())] = item.feature_json_sha256
    authorities: dict[str, FoldSelectionAuthority] = {}
    for item in manifest.fold_selections:
        scope_path = Path(item.selection_scope_path)
        selection_dir = Path(item.tone_selection_directory)
        manifest_file = selection_dir / "tone_selection_manifest.json"
        if artifact_sha256(scope_path) != item.selection_scope_file_sha256 or artifact_sha256(manifest_file) != item.tone_selection_manifest_sha256:
            raise ProjectionAblationInputError("P9-A scope/manifest file hash mismatch")
        selection_scope = ToneSelectionScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
        bundle = load_tone_selection_bundle(selection_dir)
        selected = bundle["selected_tone_set"]
        if selected is None:
            raise ProjectionAblationInputError("P9-A fold has no selected tone-set artifact")
        authorities[item.outer_fold_id] = FoldSelectionAuthority(selection_scope, selected, item.tone_selection_manifest_sha256)
        hashes[str(scope_path.resolve())] = item.selection_scope_file_sha256
        hashes[str(manifest_file.resolve())] = item.tone_selection_manifest_sha256
    return features, authorities, hashes


def _git_state(project_root: Path) -> tuple[str, bool]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root, check=True, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=project_root, check=True, capture_output=True, text=True).stdout.strip())
    return commit, dirty


def run_projection_ablation_command(argv: Sequence[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run explicit-scope P9-B sweep projection ablation")
    parser.add_argument("--config", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--candidate-universe", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config).resolve()
    scope_path = Path(args.scope).resolve()
    inputs_path = Path(args.inputs).resolve()
    universe_path = Path(args.candidate_universe).resolve()
    resolved = load_config(config_path, default_path=project_root / "config" / "default.yaml")
    config = resolved["tone_projection_ablation"]
    if config["enabled"] is not True:
        raise ProjectionAblationInputError("tone_projection_ablation.enabled must be true")
    scope = P9ProjectionAblationScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    universe = CandidateToneUniverse.from_dict(json.loads(universe_path.read_text(encoding="utf-8")))
    features, authorities, input_hashes = load_projection_ablation_inputs(inputs_path, scope, universe)
    input_hashes.update({str(config_path): artifact_sha256(config_path), str(scope_path): artifact_sha256(scope_path), str(universe_path): artifact_sha256(universe_path)})
    result = analyze_projection_ablation(
        features, scope, universe, authorities, config,
        direction_metrics_config=resolved["direction_metrics"],
        reliability_config=resolved["comparison_metrics"]["reliability"],
        band_quotas=resolved["tone_selection"]["selection"]["band_quotas"],
    )
    output = Path(args.output_root).resolve() / "simulated" / "software_validation" / args.run_id / "projection_ablation"
    git_commit, git_dirty = _git_state(project_root)
    paths = write_projection_ablation_outputs(
        result, scope, config, output, input_file_hashes=input_hashes,
        git_commit=git_commit, git_dirty=git_dirty,
    )
    return {
        "output_directory": str(output),
        "processing_status": result.processing_status,
        "result_sha256": result.sha256,
        "selected_subset_sizes": {item.outer_fold_id: item.selected_subset_size for item in result.minimum_tone_decisions},
        "artifact_count": len(paths),
        "scientifically_eligible": False,
        "deployment_eligible": False,
        "final_test_read": False,
    }

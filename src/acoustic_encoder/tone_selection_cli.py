"""Explicit-file CLI boundary for leakage-safe P9-A tone selection."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping, Sequence

from .comparison_metrics_outputs import load_comparison_metrics_bundle
from .config import load_config
from .dataset_quality_outputs import load_dataset_quality_bundle
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .schemas import FeatureSet, artifact_sha256, load_feature_set
from .sweep_multisine_bridge import (
    CandidateToneUniverse,
    FeatureViewRole,
    ToneReliabilityEvidence,
    ToneSelectionFeatureReference,
    ToneSelectionInputError,
    ToneSelectionScope,
    analyze_tone_selection,
)
from .tone_selection_outputs import write_tone_selection_outputs


@dataclass(frozen=True, slots=True)
class ToneSelectionInputArtifact:
    artifact_id: str
    sample_id: str
    view_role: FeatureViewRole
    feature_base_path: str
    feature_npz_sha256: str
    feature_json_sha256: str
    feature_content_sha256: str
    feature_contract_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "view_role", FeatureViewRole(self.view_role))
        for name in ("artifact_id", "sample_id", "feature_base_path"):
            if not str(getattr(self, name)).strip():
                raise ToneSelectionInputError(f"input manifest {name} is required")
        for name in ("feature_npz_sha256", "feature_json_sha256"):
            digest = str(getattr(self, name))
            if len(digest) != 64 or digest != digest.lower() or any(character not in "0123456789abcdef" for character in digest):
                raise ToneSelectionInputError(f"input manifest {name} is invalid")
        for name in ("feature_content_sha256", "feature_contract_sha256"):
            digest = str(getattr(self, name)).removeprefix("sha256:")
            if len(digest) != 64 or digest != digest.lower() or any(character not in "0123456789abcdef" for character in digest):
                raise ToneSelectionInputError(f"input manifest {name} is invalid")

    def to_dict(self) -> dict[str, str]:
        result = {name: getattr(self, name) for name in self.__slots__}
        result["view_role"] = self.view_role.value
        return result

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneSelectionInputArtifact":
        if set(payload) != set(cls.__dataclass_fields__):
            raise ToneSelectionInputError("tone-selection input artifact fields must be explicit")
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ToneSelectionInputManifest:
    schema_version: str
    selection_scope_id: str
    candidate_universe_id: str
    candidate_universe_sha256: str
    artifacts: tuple[ToneSelectionInputArtifact, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0.0":
            raise ToneSelectionInputError("ToneSelectionInputManifest schema_version must be 1.0.0")
        if not self.selection_scope_id or not self.candidate_universe_id or not self.artifacts:
            raise ToneSelectionInputError("tone-selection input manifest is incomplete")
        artifact_ids = [item.artifact_id for item in self.artifacts]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ToneSelectionInputError("tone-selection input artifact IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "selection_scope_id": self.selection_scope_id,
            "candidate_universe_id": self.candidate_universe_id,
            "candidate_universe_sha256": self.candidate_universe_sha256,
            "artifacts": [item.to_dict() for item in self.artifacts],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToneSelectionInputManifest":
        if set(payload) != set(cls.__dataclass_fields__):
            raise ToneSelectionInputError("ToneSelectionInputManifest fields must be explicit")
        value = dict(payload)
        value["artifacts"] = tuple(ToneSelectionInputArtifact.from_dict(item) for item in value["artifacts"])
        return cls(**value)

    @property
    def sha256(self) -> str:
        encoded = json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load_explicit_tone_selection_inputs(
    manifest_path: str | Path,
    scope: ToneSelectionScope,
    universe: CandidateToneUniverse,
) -> dict[str, FeatureSet]:
    """Load exactly the files listed in one manifest; never discover a directory."""
    path = Path(manifest_path)
    manifest = ToneSelectionInputManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))
    if manifest.selection_scope_id != scope.selection_scope_id:
        raise ToneSelectionInputError("input manifest selection scope mismatch")
    if manifest.candidate_universe_id != universe.candidate_universe_id or manifest.candidate_universe_sha256 != universe.sha256:
        raise ToneSelectionInputError("input manifest candidate universe mismatch")
    references = {item.artifact_id: item for item in scope.feature_references}
    artifacts = {item.artifact_id: item for item in manifest.artifacts}
    if set(artifacts) != set(references):
        raise ToneSelectionInputError("input manifest artifacts must exactly match the scope")
    loaded: dict[str, FeatureSet] = {}
    for artifact_id in sorted(artifacts):
        item = artifacts[artifact_id]
        reference: ToneSelectionFeatureReference = references[artifact_id]
        if item.sample_id != reference.sample_id or item.view_role is not reference.view_role:
            raise ToneSelectionInputError("input manifest FeatureSet identity mismatch")
        base = Path(item.feature_base_path)
        npz_path, json_path = base.with_suffix(".npz"), base.with_suffix(".json")
        if artifact_sha256(npz_path) != item.feature_npz_sha256 or artifact_sha256(json_path) != item.feature_json_sha256:
            raise ToneSelectionInputError("input manifest FeatureSet file hash mismatch")
        feature = load_feature_set(base)
        if feature_set_content_sha256(feature) != item.feature_content_sha256 or item.feature_content_sha256 != reference.feature_content_sha256:
            raise ToneSelectionInputError("input manifest FeatureSet content hash mismatch")
        if feature_contract_sha256(feature) != item.feature_contract_sha256 or item.feature_contract_sha256 != reference.feature_contract_sha256:
            raise ToneSelectionInputError("input manifest FeatureSet contract hash mismatch")
        loaded[artifact_id] = feature
    return loaded


def _load_reliability_evidence(
    directory: str | Path,
    expected_result_sha256: str,
) -> ToneReliabilityEvidence:
    bundle = load_comparison_metrics_bundle(directory)
    if bundle["result_sha256"] != expected_result_sha256:
        raise ToneSelectionInputError("P4-B bundle result hash mismatch")
    result = bundle["result"]
    reliability = result.get("tone_reliability")
    if not isinstance(reliability, Mapping):
        raise ToneSelectionInputError("P4-B bundle has no tone reliability evidence")
    source_kind = bundle["manifest"]["comparison_config"]["reliability"]["source_feature_kind"]
    references = {
        item["artifact_id"]: item
        for item in bundle["scope"]["feature_references"]
        if item["feature_kind"] == source_kind
    }
    input_hashes = result["input_feature_content_hashes"]
    source_hashes = {
        item["sample_id"]: input_hashes[artifact_id]
        for artifact_id, item in references.items()
    }
    available_mask = reliability["available_mask"]
    stability = tuple(
        float(value) if bool(available) else None
        for value, available in zip(reliability["stability_db"], available_mask, strict=True)
    )
    first_reference = next(iter(references.values()), None)
    if first_reference is None:
        raise ToneSelectionInputError("P4-B reliability source FeatureSets are missing")
    # The exact tone contract is recorded in the comparison scope.
    return ToneReliabilityEvidence(
        "1.0.0",
        bundle["result_sha256"],
        source_hashes,
        bundle["scope"]["tone_set_id"],
        bundle["scope"]["tone_set_sha256"],
        tuple(float(item) for item in reliability["frequencies_hz"]),
        stability,
        tuple(int(item) for item in reliability["pair_counts"]),
        tuple(tuple(str(pair) for pair in item) for item in reliability["pair_ids_by_tone"]),
    )


def _git_commit(project_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def run_tone_selection_command(argv: Sequence[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run explicit-scope P9-A tone selection")
    parser.add_argument("--config", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--candidate-universe", required=True)
    parser.add_argument("--dataset-qc-dir", required=True)
    parser.add_argument("--comparison-metrics-dir")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config).resolve()
    resolved = load_config(config_path, default_path=project_root / "config" / "default.yaml")
    selection_config = resolved["tone_selection"]
    if selection_config["enabled"] is not True:
        raise ToneSelectionInputError("tone_selection.enabled must be true for the P9-A CLI")
    scope_path = Path(args.scope).resolve()
    inputs_path = Path(args.inputs).resolve()
    universe_path = Path(args.candidate_universe).resolve()
    scope = ToneSelectionScope.from_dict(json.loads(scope_path.read_text(encoding="utf-8")))
    universe = CandidateToneUniverse.from_dict(json.loads(universe_path.read_text(encoding="utf-8")))
    features = load_explicit_tone_selection_inputs(inputs_path, scope, universe)
    dataset_qc_result = load_dataset_quality_bundle(args.dataset_qc_dir)
    reliability = None
    if scope.comparison_metrics_result_sha256 is not None:
        if args.comparison_metrics_dir is None:
            raise ToneSelectionInputError("scope requires --comparison-metrics-dir")
        reliability = _load_reliability_evidence(
            args.comparison_metrics_dir,
            scope.comparison_metrics_result_sha256,
        )
    elif args.comparison_metrics_dir is not None:
        raise ToneSelectionInputError("comparison metrics were supplied but are absent from scope")
    result = analyze_tone_selection(
        features,
        scope,
        universe,
        selection_config,
        dataset_qc_result=dataset_qc_result,
        reliability_evidence=reliability,
    )
    output = (
        Path(args.output_root).resolve()
        / scope.data_origin.value
        / scope.run_purpose.value
        / args.run_id
        / "tone_selection"
    )
    input_hashes = {
        str(path): artifact_sha256(path)
        for path in (config_path, scope_path, inputs_path, universe_path)
    }
    p2_manifest = Path(args.dataset_qc_dir).resolve() / "dataset_qc_manifest.json"
    input_hashes[str(p2_manifest)] = artifact_sha256(p2_manifest)
    if args.comparison_metrics_dir is not None:
        p4_manifest = Path(args.comparison_metrics_dir).resolve() / "metrics_manifest.json"
        input_hashes[str(p4_manifest)] = artifact_sha256(p4_manifest)
    paths = write_tone_selection_outputs(
        result,
        scope,
        universe,
        selection_config,
        output,
        input_file_hashes=input_hashes,
        git_commit=_git_commit(project_root),
    )
    return {
        "processing_status": result.processing_status,
        "selection_id": result.selection_id,
        "output_directory": str(output),
        "selected_count": len(result.selection.selected_candidate_ids),
        "artifact_count": len(paths),
        "scientifically_eligible": result.scientifically_eligible,
        "deployment_allowed": result.deployment_allowed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    summary = run_tone_selection_command(argv)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0

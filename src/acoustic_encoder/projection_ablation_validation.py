"""Deterministic simulated DEV-C13 fold-specific P9-A -> P9-B validation."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import load_config
from .dataset_quality_control import (
    CohortRole,
    DatasetQCScope,
    DatasetScopeMember,
    ExpectedCondition,
    dataset_qc_sha256,
    evaluate_dataset_quality,
    feature_contract_sha256,
    feature_set_content_sha256,
)
from .dataset_quality_outputs import write_dataset_quality_outputs
from .projection_ablation import (
    AblationScopeMember,
    FoldSelectionReference,
    InnerFoldDefinition,
    OuterFoldDefinition,
    P9ProjectionAblationScope,
)
from .projection_ablation_cli import (
    FoldSelectionInput,
    ProjectionAblationInputManifest,
    ProjectionFeatureInput,
    run_projection_ablation_command,
)
from .projection_ablation_outputs import load_projection_ablation_bundle
from .quality_control import MeasurementQCResult, UnavailablePolicy, measurement_qc_sha256
from .research_gate import RunPurpose
from .schemas import (
    DataOrigin, DatasetRole, FeatureKind, FeatureSet, MeasurementMeta,
    MeasurementMode, PhaseStatus, Representation, SourceFormat,
    artifact_sha256, save_feature_set,
)
from .sweep_multisine_bridge import (
    CandidateTone, CandidateToneUniverse, ToneSelectionFeatureReference,
    ToneSelectionMember, ToneSelectionScope,
)
from .tone_selection_cli import ToneSelectionInputArtifact, ToneSelectionInputManifest, run_tone_selection_command
from .tone_selection_outputs import load_tone_selection_bundle


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _make_features(resolved: dict[str, Any], universe: CandidateToneUniverse) -> tuple[dict[str, FeatureSet], dict[str, FeatureSet], dict[str, MeasurementQCResult]]:
    names = tuple(f"tone_{item.tone_index:06d}_{int(item.frequency_hz)}_hz" for item in universe.candidates)
    frequencies = np.asarray([item.frequency_hz for item in universe.candidates])
    discriminability: dict[str, FeatureSet] = {}
    energy: dict[str, FeatureSet] = {}
    qcs: dict[str, MeasurementQCResult] = {}
    for session_index, session_id in enumerate(("S1", "S2", "S3")):
        for direction_index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
            radians = np.deg2rad(angle)
            base = np.asarray([
                4.0 * np.cos(radians - (index % 4) * np.pi / 2.0) * (1.0 - 0.025 * index)
                for index in range(len(frequencies))
            ])
            for repeat_type, repeats in (
                ("CONT", (("C1", None, 0.00), ("C2", None, 0.03))),
                ("REPOS", (("P1", "RP1", -0.04), ("P2", "RP2", 0.05))),
            ):
                for repeat_id, reposition_id, repeat_offset in repeats:
                    sample_id = f"{session_id}-{int(angle):03d}-{repeat_type}-{repeat_id}"
                    values = base + session_index * 0.02 + repeat_offset
                    meta = MeasurementMeta(
                        sample_id, resolved["pipeline_version"], resolved["schema_versions"]["config"],
                        resolved["schema_versions"]["measurement"], resolved["schema_versions"]["feature"],
                        "DEV-C13-SYNTHETIC", "U4ENC", angle, session_id, repeat_type, repeat_id,
                        "DEV_C13_P9B_SIMULATED", MeasurementMode.REW_SWEEP, SourceFormat.MOCK_DENSE,
                        f"synthetic://{sample_id}", DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
                        hashlib.sha256(sample_id.encode()).hexdigest(), "synthetic://dev-c13", False,
                        reposition_round_id=reposition_id, assembly_id="A1", acquisition_block_id=f"B-{session_id}",
                    )
                    qc = MeasurementQCResult(
                        "1.0.0", sample_id, MeasurementMode.REW_SWEEP, DataOrigin.SIMULATED,
                        DatasetRole.SOFTWARE_VALIDATION, RunPurpose.SOFTWARE_VALIDATION, (),
                        UnavailablePolicy.PRESERVE, (), True, None, False,
                    )
                    qcs[sample_id] = qc
                    common = dict(
                        sample_id=sample_id, feature_schema_version=resolved["schema_versions"]["feature"],
                        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP, feature_names=names,
                        valid_mask=np.ones(len(names), dtype=bool), units=("dB",) * len(names),
                        source_measurement_mode=MeasurementMode.REW_SWEEP,
                        source_representation=Representation.DENSE_SPECTRUM,
                        meta=meta, tone_set_id=universe.source_tone_set_id,
                        tone_set_sha256=universe.source_tone_set_sha256,
                        tone_schema_id="sha256:" + "b" * 64,
                        source_magnitude_quantity="spl_db", source_phase_status=PhaseStatus.UNAVAILABLE,
                        source_qc_sha256=measurement_qc_sha256(qc), source_qc_status=qc.aggregate_status,
                        source_qc_eligible_for_downstream=True,
                    )
                    discriminability[sample_id] = FeatureSet(
                        values=np.asarray(values), preprocessing_id="sha256:" + "c" * 64,
                        normalization_method="subtract_mean_db", **common,
                    )
                    energy[sample_id] = FeatureSet(
                        values=np.asarray(70.0 + values), preprocessing_id="sha256:" + "d" * 64,
                        normalization_method="none", **common,
                    )
    return discriminability, energy, qcs


def run_simulated_projection_ablation_validation(
    *, project_root: Path, config_path: Path, output_root: Path, run_id: str,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    run_root = output_root / "simulated" / "software_validation" / run_id
    if run_root.exists():
        raise FileExistsError(f"projection-ablation validation run already exists: {run_root}")
    inputs_root = run_root / "inputs"
    inputs_root.mkdir(parents=True, exist_ok=False)
    resolved = load_config(config_path, default_path=project_root / "config" / "default.yaml")
    frequencies = tuple(float(value) for value in range(1000, 8001, 500))
    universe = CandidateToneUniverse(
        "1.0.0", "dev-c13-universe", "dev-c13-tone-set", "a" * 64,
        48_000, 4_800, (1_000.0, 8_000.0),
        tuple(CandidateTone(f"candidate-{index:03d}", index, value, int(value / 10)) for index, value in enumerate(frequencies)),
    )
    broad, energy, qcs = _make_features(resolved, universe)
    persisted: dict[str, tuple[Path, Path]] = {}
    projection_inputs: list[ProjectionFeatureInput] = []
    for sample_id, feature in sorted(broad.items()):
        base = inputs_root / "features" / "discriminability" / sample_id
        npz_path, json_path = save_feature_set(feature, base)
        persisted[sample_id] = (npz_path, json_path)
        projection_inputs.append(ProjectionFeatureInput(
            sample_id, base.as_posix(), artifact_sha256(npz_path), artifact_sha256(json_path),
            feature_set_content_sha256(feature), feature_contract_sha256(feature),
        ))
    universe_path = inputs_root / "candidate_universe.json"
    universe_path.write_text(json.dumps(universe.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    sessions = ("S1", "S2", "S3")
    outer_folds: list[OuterFoldDefinition] = []
    fold_references: list[FoldSelectionReference] = []
    fold_inputs: list[FoldSelectionInput] = []
    sealed_ids = ("sealed-final-1",)
    sealed_sha = _canonical_hash({"sealed_final_test_sample_ids": list(sealed_ids)})
    for held_session in sessions:
        outer_fold_id = f"outer-{held_session}"
        train_ids = tuple(item for item in broad if broad[item].meta.session_id != held_session)
        test_ids = tuple(item for item in broad if broad[item].meta.session_id == held_session)
        inner_folds = tuple(
            InnerFoldDefinition(
                f"{outer_fold_id}-inner-{inner_session}",
                tuple(item for item in train_ids if broad[item].meta.session_id != inner_session),
                tuple(item for item in train_ids if broad[item].meta.session_id == inner_session),
            )
            for inner_session in sessions if inner_session != held_session
        )
        outer_folds.append(OuterFoldDefinition(
            outer_fold_id, held_session, train_ids, test_ids,
            tuple(f"state-{item}" for item in test_ids), inner_folds,
        ))
        condition_groups: dict[tuple[Any, ...], list[str]] = {}
        for sample_id in train_ids:
            meta = broad[sample_id].meta
            key = (meta.angle_deg, meta.session_id, meta.repeat_type, meta.reposition_round_id)
            condition_groups.setdefault(key, []).append(sample_id)
        condition_ids = {key: f"{outer_fold_id}-condition-{index:03d}" for index, key in enumerate(sorted(condition_groups, key=str))}
        p2_scope = DatasetQCScope(
            "1.0.0", f"{outer_fold_id}:p2b", RunPurpose.SOFTWARE_VALIDATION,
            tuple(DatasetScopeMember(item, CohortRole.TRAINING, condition_ids[(broad[item].meta.angle_deg, broad[item].meta.session_id, broad[item].meta.repeat_type, broad[item].meta.reposition_round_id)], "DEV-C13 outer-training only") for item in train_ids),
            tuple(ExpectedCondition(
                condition_ids[key], CohortRole.TRAINING, MeasurementMode.REW_SWEEP, "U4ENC",
                f"D{int(key[0]):03d}", float(key[0]), str(key[1]), str(key[2]), key[3], "A1",
                f"B-{key[1]}", len(sample_ids),
            ) for key, sample_ids in sorted(condition_groups.items(), key=lambda value: condition_ids[value[0]])),
        )
        p2_result = evaluate_dataset_quality(
            [broad[item] for item in train_ids], [qcs[item] for item in train_ids], p2_scope,
            resolved["dataset_quality_control"],
        )
        p2_dir = inputs_root / "folds" / outer_fold_id / "dataset_qc"
        p2_records = []
        for item in train_ids:
            npz_path, json_path = persisted[item]
            for role, artifact in (("feature_npz", npz_path), ("feature_json", json_path)):
                p2_records.append({"sample_id": item, "artifact_role": role, "path": str(artifact), "sha256": artifact_sha256(artifact)})
        write_dataset_quality_outputs(
            p2_result, p2_scope, resolved["dataset_quality_control"], p2_dir,
            input_artifacts=p2_records, git_commit="validation", random_state=int(resolved["random_state"]),
            created_at_utc="2026-08-06T12:00:00+00:00",
        )
        p2_hash = dataset_qc_sha256(p2_result)
        members = tuple(ToneSelectionMember(
            item, f"state-{item}", "training", "U4ENC",
            f"D{int(broad[item].meta.angle_deg or 0):03d}", float(broad[item].meta.angle_deg or 0),
            broad[item].meta.session_id, broad[item].meta.repeat_type, broad[item].meta.repeat_id,
            broad[item].meta.reposition_round_id, broad[item].meta.assembly_id, broad[item].meta.acquisition_block_id,
        ) for item in train_ids)
        final_member = ToneSelectionMember("sealed-final-1", "sealed-state-1", "final_test", "U4ENC", "D000", 0.0, "SF", "CONT", "F1", None, "AF", "BF")
        references: list[ToneSelectionFeatureReference] = []
        artifacts: list[ToneSelectionInputArtifact] = []
        for sample_id in train_ids:
            for view_role, feature in (("discriminability", broad[sample_id]), ("effective_energy", energy[sample_id])):
                base = inputs_root / "folds" / outer_fold_id / "features" / view_role / sample_id
                if view_role == "discriminability":
                    npz_path, json_path = persisted[sample_id]
                    base = npz_path.with_suffix("")
                else:
                    npz_path, json_path = save_feature_set(feature, base)
                artifact_id = f"{sample_id}:{view_role}"
                content_hash = feature_set_content_sha256(feature)
                contract_hash = feature_contract_sha256(feature)
                references.append(ToneSelectionFeatureReference(artifact_id, sample_id, view_role, content_hash, contract_hash))
                artifacts.append(ToneSelectionInputArtifact(
                    artifact_id, sample_id, view_role, base.as_posix(), artifact_sha256(npz_path),
                    artifact_sha256(json_path), content_hash, contract_hash,
                ))
        selection_scope = ToneSelectionScope(
            "1.0.0", f"{outer_fold_id}:selection", "fold_training_selection", "software_validation",
            "simulated", "software_validation", universe.candidate_universe_id, universe.sha256,
            universe.source_tone_set_id, universe.source_tone_set_sha256, (*members, final_member),
            tuple(references), ("training",), int(resolved["tone_selection"]["selection"]["target_count"]),
            float(resolved["tone_selection"]["selection"]["minimum_spacing_hz"]),
            int(resolved["tone_selection"]["selection"]["minimum_spacing_bins"]),
            bool(resolved["tone_selection"]["selection"]["allow_partial"]), outer_fold_id, train_ids,
            tuple(f"state-{item}" for item in test_ids), sealed_ids, sealed_sha,
            p2_scope.analysis_scope_id, p2_hash, None, int(resolved["random_state"]),
            "DEV-C13 fold-specific outer-training selection",
        )
        fold_root = inputs_root / "folds" / outer_fold_id
        scope_path = fold_root / "tone_selection_scope.json"
        input_path = fold_root / "tone_selection_inputs.json"
        scope_path.write_text(json.dumps(selection_scope.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        input_path.write_text(json.dumps(ToneSelectionInputManifest(
            "1.0.0", selection_scope.selection_scope_id, universe.candidate_universe_id,
            universe.sha256, tuple(artifacts),
        ).to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        p9_output_root = inputs_root / "p9a_outputs"
        p9_summary = run_tone_selection_command([
            "--config", str(config_path), "--scope", str(scope_path), "--inputs", str(input_path),
            "--candidate-universe", str(universe_path), "--dataset-qc-dir", str(p2_dir),
            "--output-root", str(p9_output_root), "--run-id", outer_fold_id,
            "--project-root", str(project_root),
        ])
        p9_dir = Path(p9_summary["output_directory"])
        p9_bundle = load_tone_selection_bundle(p9_dir)
        selected = p9_bundle["selected_tone_set"]
        assert selected is not None
        p9_manifest_path = p9_dir / "tone_selection_manifest.json"
        p9_manifest_file_sha = artifact_sha256(p9_manifest_path)
        fold_references.append(FoldSelectionReference(
            outer_fold_id, selection_scope.sha256, selected.sha256, selection_scope.training_sample_sha256,
            universe.sha256, p2_hash, None,
            _canonical_hash({"ordered_training_features": [
                {"sample_id": item, "feature_content_sha256": feature_set_content_sha256(broad[item])}
                for item in train_ids
            ]}),
            p9_manifest_file_sha,
        ))
        fold_inputs.append(FoldSelectionInput(
            outer_fold_id, scope_path.as_posix(), artifact_sha256(scope_path),
            p9_dir.as_posix(), p9_manifest_file_sha,
        ))
    ablation_config = resolved["tone_projection_ablation"]
    ablation_scope = P9ProjectionAblationScope(
        "1.0.0", f"{run_id}:p9b", "simulated", "software_validation", "software_validation",
        tuple(AblationScopeMember(
            sample_id, f"state-{sample_id}", "training", float(feature.meta.angle_deg or 0),
            feature.meta.session_id, "explicit DEV-C13 software-validation cohort",
        ) for sample_id, feature in broad.items()),
        tuple(outer_folds), tuple(fold_references), tuple(ablation_config["subset_sizes"]),
        _canonical_hash(ablation_config), sealed_ids, sealed_sha, int(resolved["random_state"]),
    )
    scope_path = inputs_root / "ablation_scope.json"
    inputs_path = inputs_root / "ablation_inputs.json"
    scope_path.write_text(json.dumps(ablation_scope.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    inputs_path.write_text(json.dumps(ProjectionAblationInputManifest(
        "1.0.0", ablation_scope.analysis_scope_id, ablation_scope.sha256,
        universe.candidate_universe_id, universe.sha256, tuple(projection_inputs), tuple(fold_inputs),
    ).to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    summary = run_projection_ablation_command([
        "--config", str(config_path), "--scope", str(scope_path), "--inputs", str(inputs_path),
        "--candidate-universe", str(universe_path), "--output-root", str(output_root),
        "--run-id", run_id, "--project-root", str(project_root),
    ])
    bundle = load_projection_ablation_bundle(summary["output_directory"])
    validation = {
        **summary,
        "artifact_hashes_verified": True,
        "manifest_content_sha256": bundle["manifest"]["manifest_content_sha256"],
        "outer_fold_count": len(outer_folds),
        "final_test_sealed": not bundle["manifest"]["final_test_read"],
    }
    validation_path = run_root / "validation_summary.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    return validation

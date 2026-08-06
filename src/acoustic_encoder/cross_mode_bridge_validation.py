"""Deterministic, scientifically-ineligible DEV-C14 integration validation."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import load_config
from .cross_mode_bridge import (
    CrossModeFoldDefinition,
    MatchedModePair,
    P9CrossModeBridgeScope,
    _canonical_sha256,
)
from .cross_mode_bridge_cli import (
    BridgeFeatureInput,
    CrossModeInputManifest,
    FoldAuthorityInput,
    LineageArtifactReference,
    run_cross_mode_bridge_command,
)
from .cross_mode_bridge_outputs import load_cross_mode_bridge_bundle
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .matched_tone_validation import run_simulated_matched_tone_validation
from .projection_ablation import build_tone_subset_definitions, decide_minimum_tone_count
from .schemas import FeatureSet, artifact_sha256
from .sweep_multisine_bridge import (
    CandidateTone,
    CandidateToneUniverse,
    SelectedToneRecord,
    SelectedToneSetArtifact,
)


def _file_reference(role: str, path: Path) -> LineageArtifactReference:
    return LineageArtifactReference(role, path.as_posix(), artifact_sha256(path))


def _safe_run_id(run_id: str) -> str:
    candidate = Path(run_id)
    if (
        not run_id.strip()
        or candidate.name != run_id
        or run_id in {".", ".."}
        or "/" in run_id
        or "\\" in run_id
    ):
        raise ValueError("run_id must be one non-empty path component")
    return run_id


def _persisted_feature_base(chain_root: Path, feature: FeatureSet) -> Path:
    return (
        chain_root
        / "processed"
        / "features"
        / feature.feature_kind.value
        / feature.sample_id
    )


def _semantic_snapshot(
    *,
    path: Path,
    role: str,
    fold: CrossModeFoldDefinition,
    semantic_hash: str,
    payload: dict[str, Any],
) -> FoldAuthorityInput:
    snapshot = {
        "schema_version": "1.0.0",
        "authority_role": role,
        "outer_fold_id": fold.outer_fold_id,
        "authority_semantic_sha256": semantic_hash,
        "selection_scope_role": "fold_training_selection",
        "training_pair_ids": list(fold.training_pair_ids),
        "held_out_physical_state_ids": list(fold.held_out_physical_state_ids),
        "ordered_tone_ids": list(fold.ordered_tone_ids),
        "selected_subset_sha256": fold.selected_subset_sha256,
        "candidate_universe_sha256": fold.candidate_universe_sha256,
        "payload": payload,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return FoldAuthorityInput(
        fold.outer_fold_id,
        role,
        path.as_posix(),
        artifact_sha256(path),
        semantic_hash,
    )


def run_simulated_cross_mode_bridge_validation(
    *,
    project_root: Path,
    config_path: Path,
    output_root: Path,
    run_id: str,
) -> dict[str, Any]:
    """Run actual P7/S3/P8/P3-C chains, then persisted-only P9-C."""
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    run_root = output_root / "simulated" / "software_validation" / _safe_run_id(run_id)
    if run_root.exists():
        raise FileExistsError(f"cross-mode validation run already exists: {run_root}")

    resolved = load_config(config_path, default_path=project_root / "config" / "default.yaml")
    sweep_config = load_config(
        project_root / "config" / "experiment_v2_u4.yaml",
        default_path=project_root / "config" / "default.yaml",
    )
    multisine_config = load_config(
        project_root / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=project_root / "config" / "default.yaml",
    )
    stimulus = load_config(
        project_root / "config" / "stimulus_multisine_broadband.yaml",
        default_path=project_root / "config" / "default.yaml",
    )["stimulus"]
    for config in (sweep_config, multisine_config):
        config["matched_tone_features"]["normalization"] = {
            "method": "none",
            "minimum_valid_tones": 5,
            "minimum_std_db": 1.0e-9,
        }

    injected_slope = float(resolved["cross_mode_bridge_validation"]["injected_slope"])
    injected_intercept = float(
        resolved["cross_mode_bridge_validation"]["injected_intercept_db"]
    )
    sessions = tuple(resolved["cross_mode_bridge_validation"]["sessions"])
    directions = tuple(int(item) for item in resolved["cross_mode_bridge_validation"]["directions_deg"])
    # Keep persisted Windows paths below the legacy MAX_PATH boundary because
    # FeatureSet filenames already include the full sample ID.
    chain_output_root = run_root / "c"
    pairs: list[MatchedModePair] = []
    features: dict[str, FeatureSet] = {}
    feature_inputs: list[BridgeFeatureInput] = []
    chain_maximum_errors: list[float] = []
    for session_index, session_id in enumerate(sessions):
        for direction in directions:
            chain_id = f"c{session_index}{directions.index(direction)}"
            chain = run_simulated_matched_tone_validation(
                output_root=chain_output_root,
                run_id=chain_id,
                sweep_config=deepcopy(sweep_config),
                multisine_config=deepcopy(multisine_config),
                stimulus_config=deepcopy(stimulus),
                random_state=int(resolved["random_state"]) + 10 * session_index + direction,
                recording_delay_samples=1379 + 17 * session_index,
                multisine_to_sweep_slope=injected_slope,
                multisine_to_sweep_intercept_db=injected_intercept,
                shared_magnitude_quantity="spl",
                shared_magnitude_reference="reference://dev-c14-known-transfer",
                session_id=str(session_id),
                angle_deg=direction,
            )
            sweep = chain.sweep_result.feature_set
            multisine = chain.multisine_result.feature_set
            if sweep is None or multisine is None:
                raise RuntimeError("actual P3-C chain did not produce both FeatureSets")
            chain_maximum_errors.append(chain.maximum_matched_error_db)
            pair_id = f"pair-{session_id}-D{direction:03d}"
            sweep_id, multisine_id = f"{pair_id}:sweep", f"{pair_id}:multisine"
            features[sweep_id], features[multisine_id] = sweep, multisine
            pairs.append(
                MatchedModePair(
                    pair_id,
                    f"group-{session_id}-D{direction:03d}",
                    f"state-{session_id}-D{direction:03d}",
                    sweep_id,
                    multisine_id,
                    f"D{direction:03d}",
                    float(direction),
                    "U4ENC",
                    str(session_id),
                    "CONT",
                    "R01",
                    None,
                    None,
                    "B01",
                    "development",
                    "explicit simulated P7-S3-P8-P3C matched state",
                )
            )
            p3_manifest = chain.output_directory / "processed" / "preprocessing_manifest.json"
            for artifact_id, feature, lineage in (
                (
                    sweep_id,
                    sweep,
                    (_file_reference("p3c_preprocessing_manifest", p3_manifest),),
                ),
                (
                    multisine_id,
                    multisine,
                    (
                        _file_reference("p3c_preprocessing_manifest", p3_manifest),
                        _file_reference("p7_stimulus_manifest", chain.stimulus_manifest_path),
                        _file_reference("p8_run_manifest", chain.output_directory / "p8" / "run_manifest.json"),
                        _file_reference("p8_spectrum_npz", chain.output_directory / "p8" / "spectrum_data.npz"),
                        _file_reference("p8_spectrum_json", chain.output_directory / "p8" / "spectrum_data.json"),
                        _file_reference("p8_tone_quality", chain.output_directory / "p8" / "tone_quality.csv"),
                    ),
                ),
            ):
                base = _persisted_feature_base(chain.output_directory, feature)
                npz_path, json_path = base.with_suffix(".npz"), base.with_suffix(".json")
                feature_inputs.append(
                    BridgeFeatureInput(
                        artifact_id,
                        feature.sample_id,
                        base.as_posix(),
                        artifact_sha256(npz_path),
                        artifact_sha256(json_path),
                        feature_set_content_sha256(feature),
                        feature_contract_sha256(feature),
                        lineage,
                    )
                )

    first_sweep = features[pairs[0].sweep_artifact_id]
    tone_count = int(resolved["cross_mode_bridge_validation"]["selected_tone_count"])
    variance = np.var(
        np.vstack([features[item.sweep_artifact_id].values for item in pairs]), axis=0
    )
    ranked_indices = tuple(
        int(item) for item in np.argsort(-variance, kind="stable")[:tone_count]
    )
    selected_indices = tuple(sorted(ranked_indices))
    frequencies = tuple(
        float(first_sweep.feature_names[index].rsplit("_", 2)[1])
        for index in selected_indices
    )
    candidate_universe = CandidateToneUniverse(
        "1.0.0",
        "dev-c14-actual-p7-universe",
        str(first_sweep.tone_set_id),
        str(first_sweep.tone_set_sha256),
        int(stimulus["sample_rate_hz"]),
        int(stimulus["period_samples"]),
        (
            float(first_sweep.feature_names[0].rsplit("_", 2)[1]),
            float(first_sweep.feature_names[-1].rsplit("_", 2)[1]),
        ),
        tuple(
            CandidateTone(f"tone-{index:03d}", index, float(frequency), int(round(frequency / 10.0)))
            for index, frequency in enumerate(
                [
                    float(name.rsplit("_", 2)[1])
                    for name in first_sweep.feature_names
                ]
            )
        ),
    )
    sealed_ids = ("sealed-final-test-not-read",)
    sealed_hash = _canonical_sha256({"sealed_final_test_sample_ids": list(sealed_ids)})
    authority_root = run_root / "authorities"
    folds: list[CrossModeFoldDefinition] = []
    typed_authorities: dict[str, dict[str, Any]] = {}
    for held_session in sessions:
        train = tuple(item for item in pairs if item.session_id != held_session)
        test = tuple(item for item in pairs if item.session_id == held_session)
        outer_fold_id = f"outer-{held_session}"
        training_pair_ids = tuple(item.match_pair_id for item in train)
        selected_records = tuple(
            SelectedToneRecord(
                selected_order=ranked_indices.index(index) + 1,
                selection_rank=ranked_indices.index(index) + 1,
                candidate_id=f"tone-{index:03d}",
                source_tone_index=index,
                frequency_hz=float(first_sweep.feature_names[index].rsplit("_", 2)[1]),
                dft_bin=int(round(float(first_sweep.feature_names[index].rsplit("_", 2)[1]) / 10.0)),
                final_score=float(variance[index]),
            )
            for index in selected_indices
        )
        p9a_scope_hash = _canonical_sha256(
            {"outer_fold_id": outer_fold_id, "training_pair_ids": list(training_pair_ids)}
        )
        p2_hash = _canonical_sha256({"stage": "P2-B", "training_pair_ids": list(training_pair_ids)})
        p4_hash = _canonical_sha256({"stage": "P4-B", "training_pair_ids": list(training_pair_ids)})
        selected_artifact = SelectedToneSetArtifact(
            "1.0.0",
            f"{outer_fold_id}:p9a",
            "software_validation_only",
            True,
            f"{outer_fold_id}:fold-training-selection",
            p9a_scope_hash,
            _canonical_sha256(resolved["tone_selection"]),
            candidate_universe.candidate_universe_id,
            candidate_universe.sha256,
            candidate_universe.source_tone_set_id,
            candidate_universe.source_tone_set_sha256,
            candidate_universe.sample_rate_hz,
            candidate_universe.period_samples,
            selected_records,
            tone_count,
            0.0,
            1,
            tuple(features[item.sweep_artifact_id].sample_id for item in train),
            _canonical_sha256({"training_pair_ids": list(training_pair_ids)}),
            outer_fold_id,
            sealed_ids,
            sealed_hash,
            p2_hash,
            p4_hash,
            "simulated",
            "software_validation",
            False,
            False,
            False,
            scoring_method="between_direction_variance",
            input_feature_content_hashes={
                features[item.sweep_artifact_id].sample_id: feature_set_content_sha256(
                    features[item.sweep_artifact_id]
                )
                for item in train
            },
        )
        decision = decide_minimum_tone_count(
            outer_fold_id,
            ({
                "subset_size": tone_count,
                "valid_fold_count": 2,
                "status": "valid",
                "p4_retention": 1.0,
                "balanced_accuracy_drop": 0.0,
                "macro_f1_drop": 0.0,
                "coverage": 1.0,
            },),
            minimum_p4_retention=0.9,
            maximum_balanced_accuracy_drop=0.05,
            maximum_macro_f1_drop=0.05,
            minimum_coverage=1.0,
            minimum_valid_inner_folds=2,
        )
        subset = build_tone_subset_definitions(
            outer_fold_id,
            selected_artifact,
            candidate_universe,
            (tone_count,),
            band_quotas=(),
        )[0]
        p9a_manifest_hash = _canonical_sha256(
            {"selected_tone_set_sha256": selected_artifact.sha256, "final_test_read": False}
        )
        p9b_result_hash = _canonical_sha256(
            {"minimum_tone_count_decision": decision.to_dict(), "subset": subset.to_dict()}
        )
        p9b_manifest_hash = _canonical_sha256(
            {"result_sha256": p9b_result_hash, "final_test_read": False}
        )
        fold = CrossModeFoldDefinition(
            outer_fold_id,
            "leave_one_session_out",
            training_pair_ids,
            tuple(item.match_pair_id for item in test),
            tuple(item.cross_mode_group_id for item in test),
            tuple(item.physical_state_id for item in test),
            _canonical_sha256({"training_pair_ids": list(training_pair_ids)}),
            tuple(f"tone-{index:03d}" for index in selected_indices),
            subset.sha256,
            candidate_universe.sha256,
            p9a_scope_hash,
            selected_artifact.sha256,
            p9a_manifest_hash,
            p9b_result_hash,
            p9b_manifest_hash,
            p2_hash,
            p4_hash,
            tuple(first_sweep.feature_names[index] for index in selected_indices),
            frequencies,
            selected_indices,
        )
        folds.append(fold)
        typed_authorities[outer_fold_id] = {
            "p2b_result": {"stage": "P2-B", "result_sha256": p2_hash},
            "p4b_result": {"stage": "P4-B", "result_sha256": p4_hash},
            "p9a_selection_scope": {
                "selection_scope_id": selected_artifact.selection_scope_id,
                "selection_scope_sha256": p9a_scope_hash,
            },
            "p9a_selection_artifact": selected_artifact.to_dict(),
            "p9a_manifest": {"manifest_semantic_sha256": p9a_manifest_hash},
            "p9b_result": {
                "minimum_tone_count_decision": decision.to_dict(),
                "selected_subset": subset.to_dict(),
            },
            "p9b_manifest": {"manifest_semantic_sha256": p9b_manifest_hash},
        }

    scope = P9CrossModeBridgeScope(
        "1.0.0",
        f"{run_id}:p9c",
        "simulated",
        "software_validation",
        "software_validation",
        "software_validation_only",
        "not_approved",
        False,
        False,
        False,
        "multisine_db_to_sweep_projection_db",
        tuple(resolved["cross_mode_bridge"]["methods"]),
        tuple(pairs),
        tuple(folds),
        sealed_ids,
        sealed_hash,
        int(resolved["random_state"]),
        tuple(float(item) for item in directions),
        tuple(resolved["cross_mode_bridge"]["classification"]["models"]),
    )
    authority_inputs: list[FoldAuthorityInput] = []
    role_fields = {
        "p2b_result": "p2b_result_sha256",
        "p4b_result": "p4b_result_sha256",
        "p9a_selection_scope": "p9a_selection_scope_sha256",
        "p9a_selection_artifact": "p9a_selection_artifact_sha256",
        "p9a_manifest": "p9a_manifest_sha256",
        "p9b_result": "p9b_result_sha256",
        "p9b_manifest": "p9b_manifest_sha256",
    }
    for fold in folds:
        for role, field in role_fields.items():
            authority_inputs.append(
                _semantic_snapshot(
                    path=authority_root / fold.outer_fold_id / f"{role}.json",
                    role=role,
                    fold=fold,
                    semantic_hash=getattr(fold, field),
                    payload=typed_authorities[fold.outer_fold_id][role],
                )
            )

    input_root = run_root / "bridge_inputs"
    input_root.mkdir(parents=True, exist_ok=False)
    scope_path = input_root / "bridge_scope.json"
    input_path = input_root / "input_manifest.json"
    scope_path.write_text(json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = CrossModeInputManifest(
        "1.0.0",
        scope.analysis_scope_id,
        scope.sha256,
        sealed_ids,
        sealed_hash,
        tuple(feature_inputs),
        tuple(authority_inputs),
    )
    input_path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command_summary = run_cross_mode_bridge_command(
        (
            "--config", str(config_path),
            "--scope", str(scope_path),
            "--inputs", str(input_path),
            "--output-root", str(run_root / "b"),
            "--run-id", "r",
            "--project-root", str(project_root),
        )
    )
    bundle = load_cross_mode_bridge_bundle(command_summary["output_directory"])
    affine_models = [item for item in bundle["models"] if item.method == "per_tone_affine"]
    slope_errors = [
        abs(float(fit.slope) - injected_slope)
        for model in affine_models for fit in model.tone_fits if fit.slope is not None
    ]
    intercept_errors = [
        abs(float(fit.intercept_db) - injected_intercept)
        for model in affine_models for fit in model.tone_fits if fit.intercept_db is not None
    ]
    result_payload = bundle["result"]
    fold_rows = [
        item for item in result_payload["fold_evaluations"]
        if item["method"] == "per_tone_affine"
    ]
    summary = {
        **command_summary,
        "actual_chain": "P7->S3->P8->P3-C->P9-C",
        "actual_chain_count": len(pairs),
        "injected_slope": injected_slope,
        "injected_intercept_db": injected_intercept,
        "maximum_chain_relation_error_db": max(chain_maximum_errors),
        "maximum_recovered_slope_error": max(slope_errors),
        "maximum_recovered_intercept_error_db": max(intercept_errors),
        "mean_raw_rms_db": float(np.mean([item["raw_rms_difference_db"] for item in fold_rows])),
        "mean_calibrated_rms_db": float(np.mean([item["calibrated_rms_difference_db"] for item in fold_rows])),
        "artifact_hashes_verified": True,
        "model_registry_hash_verified": True,
        "p9a_authority_type": "fold_specific_selected_tone_set_artifact",
        "p9b_authority_type": "inner_validation_minimum_tone_count_decision",
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "deployment_eligible": False,
        "canonical_analysis": False,
        "final_test_read": False,
    }
    validation_path = run_root / "validation_summary.json"
    validation_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary

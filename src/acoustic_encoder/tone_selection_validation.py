"""Deterministic simulated DEV-C12 P9-A validation fixture."""

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
from .quality_control import MeasurementQCResult, UnavailablePolicy, measurement_qc_sha256
from .research_gate import RunPurpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    Representation,
    SourceFormat,
    artifact_sha256,
    save_feature_set,
)
from .sweep_multisine_bridge import (
    CandidateTone,
    CandidateToneUniverse,
    ToneSelectionFeatureReference,
    ToneSelectionMember,
    ToneSelectionScope,
)
from .tone_selection_cli import (
    ToneSelectionInputArtifact,
    ToneSelectionInputManifest,
    run_tone_selection_command,
)


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _condition_key(feature: FeatureSet) -> tuple[Any, ...]:
    meta = feature.meta
    return (
        meta.configuration, meta.angle_deg, meta.session_id, meta.repeat_type,
        meta.reposition_round_id, meta.assembly_id, meta.acquisition_block_id,
    )


def run_simulated_tone_selection_validation(
    *,
    project_root: Path,
    config_path: Path,
    output_root: Path,
    run_id: str,
) -> dict[str, Any]:
    """Create explicit inputs and exercise the same CLI boundary used by P9-A."""
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    run_root = output_root / "simulated" / "software_validation" / run_id
    if run_root.exists():
        raise FileExistsError(f"tone-selection validation run already exists: {run_root}")
    inputs_root = run_root / "inputs"
    inputs_root.mkdir(parents=True, exist_ok=False)
    resolved = load_config(config_path, default_path=project_root / "config" / "default.yaml")
    frequencies = tuple(float(value) for value in range(1000, 8001, 500))
    universe = CandidateToneUniverse(
        "1.0.0",
        "dev-c12-broadband-universe",
        "dev-c12-broadband-source",
        "a" * 64,
        48_000,
        4_800,
        (1_000.0, 8_000.0),
        tuple(
            CandidateTone(f"candidate-{index:03d}", index, frequency, int(frequency / 10.0))
            for index, frequency in enumerate(frequencies)
        ),
    )
    feature_names = tuple(
        f"tone_{candidate.tone_index:06d}_{int(candidate.frequency_hz)}_hz"
        for candidate in universe.candidates
    )
    features: list[FeatureSet] = []
    qcs: list[MeasurementQCResult] = []
    member_rows: list[dict[str, Any]] = []
    for configuration in ("U4SYM", "U4ENC"):
        for direction_index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
            for repeat_type, repeats in (
                ("CONT", (("C1", None, 0.00), ("C2", None, 0.05))),
                ("REPOS", (("P1", "RP1", 0.00), ("P2", "RP2", 0.20))),
            ):
                for repeat_id, reposition_id, repeat_offset in repeats:
                    sample_id = f"{configuration}-{int(angle):03d}-{repeat_type}-{repeat_id}"
                    direction_strength = 3.0 if configuration == "U4ENC" else 1.0
                    coefficients = np.asarray((3.0, 2.6, 2.2, 1.8, 1.4, 1.1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1))
                    values = direction_index * direction_strength * coefficients
                    values += repeat_offset
                    # Known unstable candidate; expectations never use classifier accuracy.
                    values[4] += (4.0 if repeat_id in {"C2", "P2"} else 0.0)
                    raw_values = 70.0 + values
                    raw_values[5] = -150.0
                    meta = MeasurementMeta(
                        sample_id, resolved["pipeline_version"], resolved["schema_versions"]["config"],
                        resolved["schema_versions"]["measurement"], resolved["schema_versions"]["feature"],
                        "DEV-C12-SYNTHETIC", configuration, angle, "S1", repeat_type, repeat_id,
                        "DEV_C12_P9A_SIMULATED", MeasurementMode.REW_SWEEP, SourceFormat.MOCK_DENSE,
                        f"synthetic://{sample_id}", DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
                        hashlib.sha256(sample_id.encode()).hexdigest(), "synthetic://dev-c12", False,
                        reposition_round_id=reposition_id, assembly_id="A1", acquisition_block_id="B1",
                    )
                    qc = MeasurementQCResult(
                        "1.0.0", sample_id, MeasurementMode.REW_SWEEP, DataOrigin.SIMULATED,
                        DatasetRole.SOFTWARE_VALIDATION, RunPurpose.SOFTWARE_VALIDATION, (),
                        UnavailablePolicy.PRESERVE, (), True, None, False,
                    )
                    qcs.append(qc)
                    common = dict(
                        sample_id=sample_id,
                        feature_schema_version=resolved["schema_versions"]["feature"],
                        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
                        feature_names=feature_names,
                        valid_mask=np.ones(len(frequencies), dtype=bool),
                        units=("dB",) * len(frequencies),
                        source_measurement_mode=MeasurementMode.REW_SWEEP,
                        source_representation=Representation.DENSE_SPECTRUM,
                        meta=meta,
                        tone_set_id=universe.source_tone_set_id,
                        tone_set_sha256=universe.source_tone_set_sha256,
                        tone_schema_id="sha256:" + "b" * 64,
                        source_magnitude_quantity="spl_db",
                        source_phase_status=PhaseStatus.UNAVAILABLE,
                        source_qc_sha256=measurement_qc_sha256(qc),
                        source_qc_status=qc.aggregate_status,
                        source_qc_eligible_for_downstream=True,
                    )
                    discriminability = FeatureSet(
                        values=values,
                        preprocessing_id="sha256:" + "c" * 64,
                        normalization_method="subtract_mean_db",
                        **common,
                    )
                    energy = FeatureSet(
                        values=raw_values,
                        preprocessing_id="sha256:" + "d" * 64,
                        normalization_method="none",
                        **common,
                    )
                    features.append(discriminability)
                    member_rows.append({"feature": discriminability, "energy": energy, "configuration": configuration, "direction_index": direction_index})

    conditions: dict[tuple[Any, ...], list[str]] = {}
    for feature in features:
        conditions.setdefault(_condition_key(feature), []).append(feature.sample_id)
    condition_ids = {key: f"condition-{index:03d}" for index, key in enumerate(sorted(conditions, key=str))}
    p2_scope = DatasetQCScope(
        "1.0.0",
        f"{run_id}:p2b",
        RunPurpose.SOFTWARE_VALIDATION,
        tuple(DatasetScopeMember(feature.sample_id, CohortRole.DEVELOPMENT, condition_ids[_condition_key(feature)], "DEV-C12 explicit selection cohort") for feature in features),
        tuple(
            ExpectedCondition(
                condition_ids[key], CohortRole.DEVELOPMENT, MeasurementMode.REW_SWEEP,
                str(key[0]), f"D{int(key[1]):03d}", float(key[1]), str(key[2]), str(key[3]),
                key[4], key[5], key[6], len(sample_ids),
            )
            for key, sample_ids in sorted(conditions.items(), key=lambda item: condition_ids[item[0]])
        ),
    )
    dataset_config = resolved["dataset_quality_control"]
    p2_result = evaluate_dataset_quality(features, qcs, p2_scope, dataset_config)
    p2_dir = inputs_root / "dataset_qc"
    p2_input_records: list[dict[str, str]] = []
    persisted: dict[str, tuple[Path, Path]] = {}
    qc_by_id = {item.sample_id: item for item in qcs}
    for row in member_rows:
        feature = row["feature"]
        base = inputs_root / "features" / "discriminability" / feature.sample_id
        npz_path, json_path = save_feature_set(feature, base)
        persisted[feature.sample_id] = (npz_path, json_path)
        qc_path = inputs_root / "p2a" / (feature.sample_id + ".json")
        qc_path.parent.mkdir(parents=True, exist_ok=True)
        qc_path.write_text(json.dumps(qc_by_id[feature.sample_id].to_dict(), sort_keys=True), encoding="utf-8")
        for role, path in (("feature_npz", npz_path), ("feature_json", json_path), ("p2a_qc", qc_path)):
            p2_input_records.append({"sample_id": feature.sample_id, "artifact_role": role, "path": str(path), "sha256": artifact_sha256(path)})
    write_dataset_quality_outputs(
        p2_result, p2_scope, dataset_config, p2_dir,
        input_artifacts=p2_input_records, git_commit="validation", random_state=int(resolved["random_state"]),
        created_at_utc="2026-08-06T12:00:00+00:00",
    )

    p2_hash = dataset_qc_sha256(p2_result)
    selection_members = tuple(
        ToneSelectionMember(
            feature.sample_id, f"{feature.meta.configuration}-{feature.meta.angle_deg}-{feature.meta.repeat_type}-{feature.meta.repeat_id}",
            "development", str(feature.meta.configuration), f"D{int(feature.meta.angle_deg or 0):03d}",
            float(feature.meta.angle_deg or 0), feature.meta.session_id, feature.meta.repeat_type,
            feature.meta.repeat_id, feature.meta.reposition_round_id, feature.meta.assembly_id,
            feature.meta.acquisition_block_id,
        )
        for feature in features
    )
    final_members = (
        ToneSelectionMember("sealed-final-1", "final-state-1", "final_test", "U4ENC", "D000", 0.0, "SF", "CONT", "F1", None, "AF", "BF"),
    )
    references: list[ToneSelectionFeatureReference] = []
    input_artifacts: list[ToneSelectionInputArtifact] = []
    for row in member_rows:
        for view_role, feature in (("discriminability", row["feature"]), ("effective_energy", row["energy"])):
            base = inputs_root / "features" / view_role / feature.sample_id
            if view_role == "discriminability":
                npz_path, json_path = persisted[feature.sample_id]
            else:
                npz_path, json_path = save_feature_set(feature, base)
            artifact_id = f"{feature.sample_id}:{view_role}"
            content_hash = feature_set_content_sha256(feature)
            contract_hash = feature_contract_sha256(feature)
            references.append(ToneSelectionFeatureReference(artifact_id, feature.sample_id, view_role, content_hash, contract_hash))
            input_artifacts.append(ToneSelectionInputArtifact(artifact_id, feature.sample_id, view_role, base.as_posix(), artifact_sha256(npz_path), artifact_sha256(json_path), content_hash, contract_hash))
    scope = ToneSelectionScope(
        "1.0.0", f"{run_id}:tone-selection", "development_selection", "software_validation",
        "simulated", "software_validation", universe.candidate_universe_id, universe.sha256,
        universe.source_tone_set_id, universe.source_tone_set_sha256,
        (*selection_members, *final_members), tuple(references), ("development",),
        int(resolved["tone_selection"]["selection"]["target_count"]),
        float(resolved["tone_selection"]["selection"]["minimum_spacing_hz"]),
        int(resolved["tone_selection"]["selection"]["minimum_spacing_bins"]),
        bool(resolved["tone_selection"]["selection"]["allow_partial"]),
        None, (), (), ("sealed-final-1",), _canonical_hash({"sealed_final_test_sample_ids": ["sealed-final-1"]}),
        p2_scope.analysis_scope_id, p2_hash, None, int(resolved["random_state"]),
        "deterministic DEV-C12 simulated development selection",
    )
    scope_path = inputs_root / "tone_selection_scope.json"
    universe_path = inputs_root / "candidate_universe.json"
    manifest_path = inputs_root / "tone_selection_inputs.json"
    scope_path.write_text(json.dumps(scope.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    universe_path.write_text(json.dumps(universe.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    input_manifest = ToneSelectionInputManifest("1.0.0", scope.selection_scope_id, universe.candidate_universe_id, universe.sha256, tuple(input_artifacts))
    manifest_path.write_text(json.dumps(input_manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    summary = run_tone_selection_command(
        [
            "--config", str(config_path), "--scope", str(scope_path), "--inputs", str(manifest_path),
            "--candidate-universe", str(universe_path), "--dataset-qc-dir", str(p2_dir),
            "--output-root", str(output_root), "--run-id", run_id, "--project-root", str(project_root),
        ]
    )
    validation_summary = {
        **summary,
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "final_test_read": False,
        "candidate_count": len(universe.candidates),
    }
    summary_path = run_root / "validation_summary.json"
    summary_path.write_text(json.dumps(validation_summary, indent=2, sort_keys=True), encoding="utf-8")
    return validation_summary

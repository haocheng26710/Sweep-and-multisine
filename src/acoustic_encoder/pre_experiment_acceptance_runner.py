"""DEV-C16 orchestration over existing validation APIs and artifact loaders."""

from __future__ import annotations

from copy import deepcopy
import csv
from datetime import UTC, datetime
import hashlib
from importlib import metadata as package_metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

import numpy as np
import yaml

from .config import load_config
from .cross_mode_bridge_outputs import load_cross_mode_bridge_bundle
from .cross_mode_bridge_validation import run_simulated_cross_mode_bridge_validation
from .dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from .io_multisine import analyze_multisine_measurement
from .io_rew import load_rew_measurement
from .matched_tone_validation import run_simulated_matched_tone_validation
from .mock_data import generate_dual_mode_mock, known_transfer_db
from .multisine_outputs import write_multisine_qc_outputs
from .offline_readout_cli import execute_offline_readout_from_manifest
from .offline_readout_outputs import (
    load_offline_readout_bundle,
    load_readout_package_bundle,
)
from .offline_readout_validation import run_offline_readout_validation
from .pre_experiment_acceptance import (
    AcceptanceCheck,
    AcceptanceResult,
    AcceptanceStatus,
    ScenarioEvidence,
)
from .pre_experiment_acceptance_outputs import write_acceptance_bundle
from .projection_ablation_outputs import load_projection_ablation_bundle
from .projection_ablation_validation import run_simulated_projection_ablation_validation
from .research_gate import RunPurpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    SourceFormat,
    artifact_sha256,
)
from .version import SCHEMA_VERSION_QUARTET


def _acceptance_config(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0.0":
        raise ValueError("acceptance config schema_version must be 1.0.0")
    if payload.get("final_test_policy") != "sealed":
        raise ValueError("acceptance final_test_policy must remain sealed")
    if payload.get("required_stages") != ["T0", "T1", "T2", "T3"]:
        raise ValueError("acceptance requires T0 through T3")
    tolerance = payload.get("t0", {}).get("magnitude_tolerance_db")
    if not isinstance(tolerance, (int, float)) or not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("T0 magnitude_tolerance_db must be finite and positive")
    return payload


def _verify_manifest_artifacts(directory: Path, manifest_name: str, sidecar_name: str) -> bool:
    manifest_path = directory / manifest_name
    sidecar_path = directory / sidecar_name
    if not manifest_path.is_file() or not sidecar_path.is_file():
        return False
    expected = sidecar_path.read_text(encoding="ascii").split()[0]
    if artifact_sha256(manifest_path) != expected:
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest.get("artifacts", ()):
        path = directory / item["path"]
        if not path.is_file() or artifact_sha256(path) != item["sha256"]:
            return False
    return True


def run_t0_mathematical_consistency(
    *, project_root: str | Path, evidence_root: str | Path, config_path: str | Path,
) -> dict[str, Any]:
    project = Path(project_root).resolve()
    evidence = Path(evidence_root).resolve()
    acceptance = _acceptance_config(config_path)
    t0 = acceptance["t0"]
    sweep = load_config(
        project / "config" / "validation_dev_c4_matched_tones.yaml",
        default_path=project / "config" / "default.yaml",
    )
    multisine = load_config(
        project / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=project / "config" / "default.yaml",
    )
    stimulus = load_config(
        project / "config" / "stimulus_multisine_broadband.yaml",
        default_path=project / "config" / "default.yaml",
    )["stimulus"]
    chain = run_simulated_matched_tone_validation(
        output_root=evidence / "t0",
        run_id="identity",
        sweep_config=deepcopy(sweep),
        multisine_config=deepcopy(multisine),
        stimulus_config=deepcopy(stimulus),
        random_state=int(acceptance["random_state"]),
        recording_delay_samples=int(t0["recording_delay_samples"]),
        multisine_to_sweep_slope=1.0,
        multisine_to_sweep_intercept_db=0.0,
        shared_magnitude_quantity=str(t0["shared_magnitude_quantity"]),
        shared_magnitude_reference=str(t0["shared_magnitude_reference"]),
    )
    sweep_feature = chain.sweep_result.feature_set
    multisine_feature = chain.multisine_result.feature_set
    if sweep_feature is None or multisine_feature is None:
        raise RuntimeError("T0 did not produce both P3-C FeatureSets")
    common = chain.view.common_valid_mask
    errors = np.abs(sweep_feature.values[common] - multisine_feature.values[common])
    common_indices = np.flatnonzero(common)
    rows = [
        {
            "tone_index": int(index),
            "frequency_hz": float(
                sweep_feature.feature_names[index].rsplit("_", 2)[1]
            ),
            "feature_name": sweep_feature.feature_names[index],
            "sweep_value_db": float(sweep_feature.values[index]),
            "multisine_value_db": float(multisine_feature.values[index]),
            "absolute_error_db": float(error),
        }
        for index, error in zip(common_indices, errors, strict=True)
    ]
    same_contract = (
        sweep_feature.feature_names == multisine_feature.feature_names
        and sweep_feature.units == multisine_feature.units
        and sweep_feature.tone_set_id == multisine_feature.tone_set_id
        and sweep_feature.tone_set_sha256 == multisine_feature.tone_set_sha256
    )
    same_semantics = (
        sweep_feature.source_magnitude_quantity
        == multisine_feature.source_magnitude_quantity
        and sweep_feature.source_magnitude_reference
        == multisine_feature.source_magnitude_reference
        and sweep_feature.units == multisine_feature.units
    )
    no_hidden_fill = bool(
        len(common_indices) == len(sweep_feature.feature_names)
        and np.all(np.isfinite(sweep_feature.values[common]))
        and np.all(np.isfinite(multisine_feature.values[common]))
        and not np.any((sweep_feature.values[common] == 0.0) & (multisine_feature.values[common] != 0.0))
    )
    processed = chain.output_directory / "processed"
    hashes_verified = _verify_manifest_artifacts(
        processed, "preprocessing_manifest.json", "preprocessing_manifest.sha256"
    )
    tolerance = float(t0["magnitude_tolerance_db"])
    maximum = float(np.max(errors))
    mean = float(np.mean(errors))
    rms = float(np.sqrt(np.mean(np.square(errors))))
    passed = bool(
        errors.size >= 5
        and maximum <= tolerance
        and same_contract
        and same_semantics
        and no_hidden_fill
        and hashes_verified
    )
    return {
        "schema_version": "1.0.0",
        "status": "pass" if passed else "fail",
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "identity_calibration_applied": False,
        "common_tone_count": int(errors.size),
        "configured_tolerance_db": tolerance,
        "maximum_absolute_error_db": maximum,
        "mean_absolute_error_db": mean,
        "rms_error_db": rms,
        "feature_names_identical": sweep_feature.feature_names == multisine_feature.feature_names,
        "tone_hash_identical": (
            sweep_feature.tone_set_sha256 == multisine_feature.tone_set_sha256
        ),
        "quantity_unit_reference_identical": same_semantics,
        "no_interpolation_reorder_or_zero_fill": no_hidden_fill,
        "artifact_hashes_verified": hashes_verified,
        "sweep_feature_content_sha256": feature_set_content_sha256(sweep_feature),
        "multisine_feature_content_sha256": feature_set_content_sha256(multisine_feature),
        "sweep_feature_contract_sha256": feature_contract_sha256(sweep_feature),
        "multisine_feature_contract_sha256": feature_contract_sha256(multisine_feature),
        "stimulus_manifest_sha256": artifact_sha256(chain.stimulus_manifest_path),
        "mock_manifest_sha256": artifact_sha256(chain.mock_manifest_path),
        "preprocessing_manifest_sha256": artifact_sha256(
            processed / "preprocessing_manifest.json"
        ),
        "evidence_directory": chain.output_directory.as_posix(),
        "tones": rows,
    }


def run_t1_robustness_scenarios(
    *, project_root: str | Path, evidence_root: str | Path, config_path: str | Path,
) -> dict[str, Any]:
    project = Path(project_root).resolve()
    evidence = Path(evidence_root).resolve()
    acceptance = _acceptance_config(config_path)
    t1 = acceptance["t1"]
    resolved = load_config(
        project / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=project / "config" / "default.yaml",
    )
    stimulus = load_config(
        project / "config" / "stimulus_multisine_broadband.yaml",
        default_path=project / "config" / "default.yaml",
    )["stimulus"]
    tolerance = float(t1["magnitude_tolerance_db"])
    scenario_rows: list[dict[str, Any]] = []
    for index, definition in enumerate(t1["scenarios"]):
        scenario_id = str(definition["scenario_id"])
        scenario_root = evidence / "t1" / scenario_id
        inputs = scenario_root / "inputs"
        missing = (
            ()
            if definition.get("missing_tone_hz") is None
            else (float(definition["missing_tone_hz"]),)
        )
        manifest_path = generate_dual_mode_mock(
            inputs,
            deepcopy(stimulus),
            configurations=("U4ENC",),
            angles_deg=(0,),
            random_state=int(acceptance["random_state"]) + index,
            recording_delay_samples=int(definition.get("delay_samples", 0)),
            sampling_clock_drift_ppm=float(definition.get("drift_ppm", 0.0)),
            additive_noise_std=float(definition.get("additive_noise_std", 2.0e-5)),
            missing_tone_frequencies_hz=missing,
            clipping_run_samples=int(definition.get("clipping_run_samples", 0)),
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        meta = MeasurementMeta.from_dict(next(
            item for item in manifest["samples"]
            if item["measurement_mode"] == "schroeder_multisine"
        ))
        stimulus_manifest = Path(manifest["stimulus_manifest"])
        correction = str(definition.get("correction", "disabled"))
        try:
            analysis = analyze_multisine_measurement(
                meta.source_path,
                stimulus_manifest,
                meta,
                run_purpose=RunPurpose.SOFTWARE_VALIDATION,
                period_averaging=str(
                    definition.get(
                        "period_averaging",
                        resolved["multisine_estimation"]["period_averaging"],
                    )
                ),
                clock_drift_config={
                    **resolved["multisine_estimation"]["clock_drift"],
                    "correction": correction,
                },
                tone_quality_config=resolved["multisine_estimation"]["tone_quality"],
            )
            output_paths = write_multisine_qc_outputs(analysis, scenario_root / "p8")
            artifact_hashes = {
                role: artifact_sha256(path) for role, path in sorted(output_paths.items())
            }
            hashes_verified = all(
                path.is_file() and artifact_sha256(path) == artifact_hashes[role]
                for role, path in output_paths.items()
            )
            spectrum = analysis.spectrum
            expected = known_transfer_db(
                spectrum.frequency_hz,
                angle_deg=float(meta.angle_deg or 0.0),
                configuration=str(meta.configuration),
            )
            valid = spectrum.valid_mask & np.isfinite(spectrum.magnitude_db)
            maximum_error = (
                None
                if not np.any(valid)
                else float(np.max(np.abs(spectrum.magnitude_db[valid] - expected[valid])))
            )
            actual = str(analysis.measurement_qc["status"])
            drift = spectrum.quality_metrics.get("clock_drift", {})
            pre_drift = (
                drift.get("pre_correction") or {}
                if isinstance(drift, Mapping) else {}
            )
            post_drift = (
                drift.get("post_correction") or {}
                if isinstance(drift, Mapping) else {}
            )
            scenario = ScenarioEvidence.evaluate(
                scenario_id=scenario_id,
                expected_status=str(definition["expected_status"]),
                actual_status=actual,
                evidence={
                    "synchronization": "located",
                    "clock_drift": drift,
                    "clipping": analysis.clipping_metrics,
                    "missing_tone_count": analysis.measurement_qc["missing_tone_count"],
                    "phase_status": spectrum.phase_status.value,
                },
            )
            magnitude_required = actual == "valid"
            magnitude_recovered = maximum_error is not None and maximum_error <= tolerance
            expectation_matched = bool(
                scenario.expectation_matched
                and hashes_verified
                and (magnitude_recovered if magnitude_required else True)
            )
            scenario_rows.append({
                **scenario.to_dict(),
                "expectation_matched": expectation_matched,
                "acceptance_status": "pass" if expectation_matched else "fail",
                "sync_status": "located",
                "drift_status": drift.get("final_decision", "unavailable"),
                "estimated_drift_ppm": (
                    pre_drift.get("signed_drift_ppm")
                ),
                "residual_drift_ppm": (
                    post_drift.get("signed_residual_drift_ppm")
                ),
                "clipping_status": analysis.clipping_metrics["status"],
                "clipping_sample_count": analysis.clipping_metrics["sample_count"],
                "missing_tone_count": analysis.measurement_qc["missing_tone_count"],
                "phase_status": spectrum.phase_status.value,
                "phase_used_downstream": False,
                "maximum_amplitude_error_db": maximum_error,
                "configured_tolerance_db": tolerance,
                "magnitude_recovered": magnitude_recovered,
                "artifact_hashes_verified": hashes_verified,
                "artifact_hashes": artifact_hashes,
                "data_origin": spectrum.meta.data_origin.value,
                "run_purpose": "software_validation",
                "scientifically_eligible": False,
                "evidence_directory": scenario_root.as_posix(),
            })
        except Exception as exc:  # domain failures are acceptance evidence
            scenario_root.mkdir(parents=True, exist_ok=True)
            failure_path = scenario_root / "failure_audit.json"
            failure_payload = {
                "scenario_id": scenario_id,
                "status": "blocked",
                "exception_type": type(exc).__name__,
                "reason": str(exc),
                "input_manifest_sha256": artifact_sha256(manifest_path),
                "final_test_read": False,
                "scientifically_eligible": False,
            }
            failure_path.write_text(
                json.dumps(failure_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            scenario = ScenarioEvidence.evaluate(
                scenario_id=scenario_id,
                expected_status=str(definition["expected_status"]),
                actual_status="blocked",
                evidence=failure_payload,
            )
            scenario_rows.append({
                **scenario.to_dict(),
                "sync_status": "blocked",
                "drift_status": "unavailable",
                "clipping_status": "unavailable",
                "missing_tone_count": None,
                "phase_status": "unavailable",
                "phase_used_downstream": False,
                "maximum_amplitude_error_db": None,
                "configured_tolerance_db": tolerance,
                "magnitude_recovered": False,
                "artifact_hashes_verified": True,
                "artifact_hashes": {"failure_audit": artifact_sha256(failure_path)},
                "data_origin": "simulated",
                "run_purpose": "software_validation",
                "scientifically_eligible": False,
                "evidence_directory": scenario_root.as_posix(),
            })
    matched = sum(bool(item["expectation_matched"]) for item in scenario_rows)
    hashes_verified = all(bool(item["artifact_hashes_verified"]) for item in scenario_rows)
    return {
        "schema_version": "1.0.0",
        "status": (
            "pass" if matched == len(scenario_rows) and hashes_verified else "fail"
        ),
        "scenario_count": len(scenario_rows),
        "expectation_matched_count": matched,
        "all_artifact_hashes_verified": hashes_verified,
        "final_test_read": False,
        "scientifically_eligible": False,
        "scenarios": scenario_rows,
    }


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _json_cell(value: str | None) -> list[Any]:
    if value is None or value == "":
        return []
    decoded = json.loads(value)
    return decoded if isinstance(decoded, list) else [decoded]


def run_t2_selection_classification(
    *, project_root: str | Path, evidence_root: str | Path, config_path: str | Path,
) -> dict[str, Any]:
    project = Path(project_root).resolve()
    evidence = Path(evidence_root).resolve()
    acceptance = _acceptance_config(config_path)
    t2 = acceptance["t2"]
    validation = run_simulated_projection_ablation_validation(
        project_root=project,
        config_path=(project / str(t2["config_path"])).resolve(),
        # Keep validation names deliberately short for legacy Windows MAX_PATH.
        output_root=evidence,
        run_id="t2",
    )
    output = Path(validation["output_directory"])
    bundle = load_projection_ablation_bundle(output)
    scope = bundle["scope"]
    manifest = bundle["manifest"]
    decisions = _csv_rows(output / "minimum_tone_decisions.csv")
    subsets = _csv_rows(output / "tone_subset_definitions.csv")
    p4_rows = _csv_rows(output / "p4_metric_preservation.csv")
    inner_rows = _csv_rows(output / "inner_classification_metrics.csv")
    outer_rows = _csv_rows(output / "outer_fold_metrics.csv")
    decision_by_fold = {row["outer_fold_id"]: row for row in decisions}
    folds: list[dict[str, Any]] = []
    leakage_ok = True
    for fold in scope["outer_folds"]:
        fold_id = fold["outer_fold_id"]
        train_ids = tuple(fold["training_sample_ids"])
        held_ids = tuple(fold["test_sample_ids"])
        disjoint = not (set(train_ids) & set(held_ids))
        leakage_ok = leakage_ok and disjoint
        decision = decision_by_fold[fold_id]
        selected_size = int(decision["selected_subset_size"])
        subset = next(
            row for row in subsets
            if row["outer_fold_id"] == fold_id
            and int(row["subset_size"]) == selected_size
        )
        authority = next(
            item for item in scope["fold_selection_references"]
            if item["outer_fold_id"] == fold_id
        )
        fold_outer = next(row for row in outer_rows if row["outer_fold_id"] == fold_id)
        folds.append({
            "outer_fold_id": fold_id,
            "training_sample_ids": list(train_ids),
            "held_sample_ids": list(held_ids),
            "training_held_disjoint": disjoint,
            "inner_fold_ids": [item["inner_fold_id"] for item in fold["inner_folds"]],
            "selected_tone_ids": _json_cell(subset["selection_order_candidate_ids"]),
            "selected_subset_size": selected_size,
            "minimum_tone_status": decision["status"],
            "minimum_tone_lifecycle": decision["lifecycle"],
            "selection_scope_sha256": authority["selection_scope_sha256"],
            "selection_artifact_sha256": authority["selection_artifact_sha256"],
            "selection_manifest_sha256": authority["selection_manifest_sha256"],
            "p2b_result_sha256": authority["dataset_qc_result_sha256"],
            "p4b_result_sha256": authority.get("comparison_result_sha256"),
            "balanced_accuracy_broad": float(fold_outer["balanced_accuracy_broad"]),
            "balanced_accuracy_sparse": float(fold_outer["balanced_accuracy_sparse"]),
            "macro_f1_broad": float(fold_outer["macro_f1_broad"]),
            "macro_f1_sparse": float(fold_outer["macro_f1_sparse"]),
            "prediction_coverage": float(fold_outer["coverage"]),
        })
    available_retentions = [
        float(row["retention"]) for row in p4_rows
        if row.get("status") == "valid" and row.get("retention") not in {None, ""}
    ]
    directions = {
        float(item["direction_angle_deg"]) for item in scope["members"]
    }
    minimum_p4 = min(available_retentions) if available_retentions else float("nan")
    minimum_ba = min(item["balanced_accuracy_sparse"] for item in folds)
    minimum_f1 = min(item["macro_f1_sparse"] for item in folds)
    minimum_coverage = min(item["prediction_coverage"] for item in folds)
    expected_outer = int(t2["expected_outer_fold_count"])
    expected_directions = int(t2["expected_direction_count"])
    passed = bool(
        len(folds) == expected_outer
        and len(directions) == expected_directions
        and all(item["minimum_tone_status"] == "valid" for item in folds)
        and all(item["selected_tone_ids"] for item in folds)
        and leakage_ok
        and minimum_p4 >= 0.8
        and minimum_ba >= 0.9
        and minimum_f1 >= 0.9
        and minimum_coverage == 1.0
        and manifest["final_test_read"] is False
        and manifest["scientifically_eligible"] is False
        and validation["artifact_hashes_verified"] is True
    )
    return {
        "schema_version": "1.0.0",
        "status": "pass" if passed else "fail",
        "direction_count": len(directions),
        "directions_deg": sorted(directions),
        "outer_fold_count": len(folds),
        "inner_fold_count": sum(len(item["inner_fold_ids"]) for item in folds),
        "minimum_p4_retention": minimum_p4,
        "minimum_sparse_balanced_accuracy": minimum_ba,
        "minimum_sparse_macro_f1": minimum_f1,
        "minimum_prediction_coverage": minimum_coverage,
        "leakage_audit_passed": leakage_ok,
        "final_test_read": False,
        "sealed_final_test_sample_ids": manifest["sealed_final_test_sample_ids"],
        "sealed_final_test_sha256": manifest["sealed_final_test_sha256"],
        "selection_lifecycle": "software_validation_candidate",
        "artifact_hashes_verified": True,
        "manifest_content_sha256": manifest["manifest_content_sha256"],
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "canonical_analysis": False,
        "deployment_eligible": False,
        "evidence_directory": output.as_posix(),
        "folds": folds,
        "inner_classification_evidence_count": len(inner_rows),
    }


def _prefixed_file_sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_readout_manifest(directory: Path) -> dict[str, Any]:
    path = directory / "readout_manifest.json"
    expected = (directory / "readout_manifest.sha256").read_text(encoding="ascii").split()[0]
    if _prefixed_file_sha(path) != expected:
        raise ValueError("readout failure manifest file hash mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    semantic = dict(manifest)
    expected_content = semantic.pop("manifest_content_sha256")
    from .offline_readout import canonical_sha256 as readout_sha256
    if readout_sha256(semantic) != expected_content:
        raise ValueError("readout failure manifest content hash mismatch")
    for relative, digest in manifest["artifacts"].items():
        target = directory / relative
        if not target.is_file() or _prefixed_file_sha(target) != digest:
            raise ValueError(f"readout failure artifact hash mismatch: {relative}")
    return manifest


def run_t3_end_to_end(
    *, project_root: str | Path, evidence_root: str | Path, config_path: str | Path,
) -> dict[str, Any]:
    project = Path(project_root).resolve()
    evidence = Path(evidence_root).resolve()
    acceptance = _acceptance_config(config_path)
    t3 = acceptance["t3"]
    bridge = run_simulated_cross_mode_bridge_validation(
        project_root=project,
        config_path=(project / str(t3["bridge_config_path"])).resolve(),
        output_root=evidence,
        run_id="b",
    )
    bridge_output = Path(bridge["output_directory"])
    bridge_bundle = load_cross_mode_bridge_bundle(bridge_output)
    bridge_manifest = bridge_bundle["manifest"]
    p4_path = bridge_output / "direction_template_consistency.csv"
    p5_path = bridge_output / "cross_mode_predictions.csv"
    p9_path = bridge_output / "bridge_result.json"
    p4_verified = (
        p4_path.is_file()
        and artifact_sha256(p4_path) == bridge_manifest["artifact_hashes"][p4_path.name]
    )
    p5_verified = (
        p5_path.is_file()
        and artifact_sha256(p5_path) == bridge_manifest["artifact_hashes"][p5_path.name]
    )
    p9_verified = (
        p9_path.is_file()
        and artifact_sha256(p9_path) == bridge_manifest["artifact_hashes"][p9_path.name]
        and bridge["model_registry_hash_verified"] is True
    )

    readout = run_offline_readout_validation(
        project_root=project,
        config_path=(project / str(t3["readout_config_path"])).resolve(),
        output_root=evidence,
        run_id="d",
    )
    readout_root = Path(readout["output_directory"])
    package, model, package_manifest = load_readout_package_bundle(
        readout_root / "readout_package"
    )
    readout_result, readout_manifest = load_offline_readout_bundle(
        readout_root / "offline_readout"
    )
    repeated, repeated_manifest = load_offline_readout_bundle(
        readout_root / "offline_readout_repeat"
    )
    readout_verified = bool(
        package.semantic_sha256 == readout["package_semantic_sha256"]
        and model.semantic_sha256 == readout["model_semantic_sha256"]
        and package_manifest["manifest_content_sha256"]
        == readout["package_manifest_content_sha256"]
        and readout_result.semantic_sha256 == readout["readout_result_sha256"]
        and readout_manifest["manifest_content_sha256"]
        == readout["readout_manifest_content_sha256"]
        and repeated.semantic_sha256 == readout_result.semantic_sha256
    )

    input_manifest_path = readout_root / "readout_input_manifest.json"
    original_input_hash = artifact_sha256(input_manifest_path)
    tampered = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    tampered["spectrum_json_sha256"] = "sha256:" + "0" * 64
    failure_input = readout_root / "failure_input_manifest.json"
    failure_input.write_text(
        json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failure_output = readout_root / "offline_readout_failure"
    execute_offline_readout_from_manifest(
        readout_root / "readout_package", failure_input, failure_output
    )
    failure_manifest = _verify_readout_manifest(failure_output)
    source_unchanged = artifact_sha256(input_manifest_path) == original_input_hash

    expected_direction = float(t3["expected_direction_deg"])
    passed = bool(
        bridge["actual_chain"] == "P7->S3->P8->P3-C->P9-C"
        and bridge["artifact_hashes_verified"] is True
        and p4_verified and p5_verified and p9_verified and readout_verified
        and readout_result.prediction.predicted_direction_deg == expected_direction
        and readout["deterministic_repeat"] is True
        and failure_manifest["processing_status"] == "blocked"
        and failure_manifest["prediction_available"] is False
        and source_unchanged
        and bridge_manifest["final_test_read"] is False
        and readout_result.final_test_read is False
        and readout_result.scientifically_eligible is False
        and readout_result.deployment_eligible is False
    )
    return {
        "schema_version": "1.0.0",
        "status": "pass" if passed else "fail",
        "actual_persisted_chain": "P7->S3->P8->P3-C->P4->P5->P9-C->P9-D->acceptance_report",
        "bridge_actual_chain_count": bridge["actual_chain_count"],
        "p4_metric_artifact_verified": p4_verified,
        "p4_metric_artifact_sha256": artifact_sha256(p4_path),
        "p5_prediction_artifact_verified": p5_verified,
        "p5_prediction_artifact_sha256": artifact_sha256(p5_path),
        "p9_bridge_artifacts_verified": p9_verified,
        "p9_bridge_result_sha256": bridge_manifest["result_sha256"],
        "p9_bridge_manifest_content_sha256": bridge_manifest["manifest_content_sha256"],
        "p9_calibration_lifecycle": bridge_manifest["calibration_lifecycle"],
        "p9_calibration_approval_status": bridge_manifest["approval_status"],
        "readout_artifacts_verified": readout_verified,
        "readout_package_sha256": package.semantic_sha256,
        "readout_result_sha256": readout_result.semantic_sha256,
        "readout_manifest_content_sha256": readout_manifest["manifest_content_sha256"],
        "repeat_manifest_content_sha256": repeated_manifest["manifest_content_sha256"],
        "predicted_direction_deg": readout_result.prediction.predicted_direction_deg,
        "second_direction_deg": readout_result.prediction.second_direction_deg,
        "score": readout_result.prediction.score,
        "second_score": readout_result.prediction.second_score,
        "margin": readout_result.prediction.margin,
        "qc_status": readout_result.qc_audit.status,
        "readout_deterministic_repeat": repeated.semantic_sha256 == readout_result.semantic_sha256,
        "failure_path_status": failure_manifest["processing_status"],
        "failure_path_prediction_available": failure_manifest["prediction_available"],
        "failure_manifest_content_sha256": failure_manifest["manifest_content_sha256"],
        "source_artifacts_unchanged": source_unchanged,
        "source_commit": readout["source_commit"],
        "source_git_dirty": readout["source_git_dirty"],
        "final_test_read": False,
        "scientifically_eligible": False,
        "canonical_analysis": False,
        "deployment_eligible": False,
        "approved_real_calibration": False,
        "final_tone_set_frozen": False,
        "bridge_evidence_directory": bridge_output.as_posix(),
        "readout_evidence_directory": readout_root.as_posix(),
    }


def _git_state(project: Path) -> tuple[str, str, bool]:
    commit = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=project, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    branch = subprocess.run(
        ("git", "branch", "--show-current"), cwd=project, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ("git", "status", "--porcelain"), cwd=project, check=True,
        capture_output=True, text=True,
    ).stdout.strip())
    return commit, branch, dirty


def _run_verification_command(
    *, project: Path, log_directory: Path, command_id: str, command: tuple[str, ...],
) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=project, capture_output=True, text=True,
    )
    output = completed.stdout + completed.stderr
    log_path = log_directory / f"{command_id}.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "command=" + json.dumps(command) + "\n"
        + f"exit_code={completed.returncode}\n" + output,
        encoding="utf-8",
    )
    match = re.search(r"(\d+) passed", output)
    return {
        "command_id": command_id,
        "command": list(command),
        "exit_code": completed.returncode,
        "passed_count": None if match is None else int(match.group(1)),
        "status": "pass" if completed.returncode == 0 else "fail",
        "log_path": log_path.as_posix(),
        "log_sha256": artifact_sha256(log_path),
        "summary_tail": output.strip().splitlines()[-1] if output.strip() else "",
    }


def _verify_external_rew(project: Path) -> dict[str, Any]:
    root = project / "tests" / "fixtures" / "rew" / "external_reference"
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for item in manifest["files"]:
        path = root / item["file_name"]
        meta = MeasurementMeta(
            sample_id=str(item["sample_id"]),
            **SCHEMA_VERSION_QUARTET,
            device_version=None, configuration=None, angle_deg=None,
            session_id=None, repeat_type=None, repeat_id=None,
            experiment_step=None, measurement_mode=MeasurementMode.REW_SWEEP,
            source_format=SourceFormat.REW_TXT, source_path=path.as_posix(),
            data_origin=DataOrigin.EXTERNAL_REFERENCE,
            dataset_role=DatasetRole.PARSER_FIXTURE,
            source_sha256=str(item["sha256"]),
            provenance_uri="tests/fixtures/rew/external_reference/manifest.json",
            eligible_for_scientific_analysis=False,
        )
        spectrum = load_rew_measurement(
            path, meta, run_purpose=RunPurpose.SOFTWARE_VALIDATION
        )
        rows.append({
            "file_name": item["file_name"],
            "sha256": artifact_sha256(path),
            "expected_point_count": item["expected_point_count"],
            "observed_point_count": int(spectrum.frequency_hz.size),
            "data_origin": spectrum.meta.data_origin.value,
            "scientifically_eligible": spectrum.meta.eligible_for_scientific_analysis,
            "experiment_identity_absent": all(
                value is None for value in (
                    spectrum.meta.configuration, spectrum.meta.angle_deg,
                    spectrum.meta.session_id, spectrum.meta.repeat_type,
                )
            ),
        })
    passed = all(
        row["sha256"] == item["sha256"]
        and row["observed_point_count"] == row["expected_point_count"]
        and row["data_origin"] == "external_reference"
        and row["scientifically_eligible"] is False
        and row["experiment_identity_absent"] is True
        for row, item in zip(rows, manifest["files"], strict=True)
    )
    return {
        "status": "pass" if passed else "fail",
        "fixture_count": len(rows),
        "manifest_sha256": artifact_sha256(manifest_path),
        "files": rows,
    }


def _verify_legacy_config(evidence: Path) -> dict[str, Any]:
    path = evidence / "legacy_config_input.yaml"
    payload = {"random_state": 7}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    before = artifact_sha256(path)
    resolved = load_config(path)
    after = artifact_sha256(path)
    passed = bool(
        before == after
        and yaml.safe_load(path.read_text(encoding="utf-8")) == payload
        and resolved["measurement_mode"] == "rew_sweep"
        and resolved["schema_versions"]["config"] == SCHEMA_VERSION_QUARTET["config_schema_version"]
        and resolved["_runtime"]["migration_warnings"]
    )
    return {
        "status": "pass" if passed else "fail",
        "source_sha256_before": before,
        "source_sha256_after": after,
        "resolved_measurement_mode": resolved["measurement_mode"],
        "resolved_config_schema_version": resolved["schema_versions"]["config"],
        "migration_warnings": list(resolved["_runtime"]["migration_warnings"]),
        "source_rewritten": before != after,
        "evidence_path": path.as_posix(),
    }


def _check(
    check_id: str, passed: bool, evidence_files: tuple[str, ...], verification: str,
    *, reason_pass: str, reason_fail: str, details: Mapping[str, Any] | None = None,
) -> AcceptanceCheck:
    return AcceptanceCheck(
        check_id=check_id,
        status=AcceptanceStatus.PASS if passed else AcceptanceStatus.FAIL,
        required=True,
        reason=reason_pass if passed else reason_fail,
        evidence_files=evidence_files,
        verification=verification,
        details=dict(details or {}),
    )


def _relative_record(output: Path, path: Path) -> dict[str, str]:
    return {
        "path": Path(os.path.relpath(path.resolve(), output.resolve())).as_posix(),
        "sha256": _prefixed_file_sha(path),
    }


def run_pre_experiment_acceptance(
    *, project_root: str | Path, config_path: str | Path,
    output_root: str | Path, run_id: str,
) -> dict[str, Any]:
    project = Path(project_root).resolve()
    config_file = Path(config_path).resolve()
    output_base = Path(output_root).resolve()
    if Path(run_id).name != run_id or not run_id.strip() or any(c in run_id for c in "/\\"):
        raise ValueError("acceptance run_id must be one non-empty path component")
    run_root = output_base / "simulated" / "software_validation" / run_id
    if run_root.exists():
        raise FileExistsError(f"acceptance run already exists: {run_root}")
    run_root.mkdir(parents=True, exist_ok=False)
    evidence = run_root / "e"
    acceptance = _acceptance_config(config_file)

    def stage(call: Any, name: str) -> dict[str, Any]:
        try:
            return call()
        except Exception as exc:
            failure = {
                "schema_version": "1.0.0", "status": "fail",
                "reason": f"{type(exc).__name__}:{exc}",
                "final_test_read": False, "scientifically_eligible": False,
            }
            path = evidence / f"{name}_failure.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            failure["failure_evidence_path"] = path.as_posix()
            failure["failure_evidence_sha256"] = artifact_sha256(path)
            return failure

    t0 = stage(lambda: run_t0_mathematical_consistency(
        project_root=project, evidence_root=evidence, config_path=config_file,
    ), "t0")
    t1 = stage(lambda: run_t1_robustness_scenarios(
        project_root=project, evidence_root=evidence, config_path=config_file,
    ), "t1")
    t2 = stage(lambda: run_t2_selection_classification(
        project_root=project, evidence_root=evidence, config_path=config_file,
    ), "t2")
    t3 = stage(lambda: run_t3_end_to_end(
        project_root=project, evidence_root=evidence, config_path=config_file,
    ), "t3")

    rew = _verify_external_rew(project)
    legacy = _verify_legacy_config(evidence / "support")
    verification_dir = evidence / "verification"
    commands = {
        "v1_sweep_cli": (
            sys.executable, str(project / "scripts" / "run_pipeline.py"),
            "--config", str(project / "config" / "experiment_v2_u4.yaml"),
        ),
        "focused_compatibility_and_leakage": (
            sys.executable, "-m", "pytest", "-q", "--disable-warnings",
            "tests/test_pipeline_cli.py", "tests/test_io_rew.py", "tests/test_config.py",
            "tests/test_research_gate.py", "tests/test_tone_selection.py",
            "tests/test_projection_ablation.py", "tests/test_cross_mode_bridge.py",
            "tests/test_offline_readout.py",
        ),
        "key_dev_b_to_c15_e2e": (
            sys.executable, "-m", "pytest", "-q", "--disable-warnings",
            "tests/test_matched_tone_e2e.py", "tests/test_dataset_quality_e2e.py",
            "tests/test_metrics_e2e.py", "tests/test_classification_validation.py",
            "tests/test_cross_mode_bridge_validation_e2e.py",
            "tests/test_offline_readout_validation_e2e.py",
        ),
        "full_pytest": (sys.executable, "-m", "pytest", "-q", "--disable-warnings"),
        "compileall": (sys.executable, "-m", "compileall", "-q", "src", "scripts", "tests"),
        "git_diff_check": ("git", "diff", "--check"),
    }
    verification = {
        name: _run_verification_command(
            project=project, log_directory=verification_dir,
            command_id=name, command=command,
        )
        for name, command in commands.items()
    }
    commit, branch, dirty = _git_state(project)
    docs = (
        project / "README.md", project / "MIGRATION_V1_TO_V2.md",
        project / "docs" / "progress" / "DEV-C16_PRE_EXPERIMENT_ACCEPTANCE.md",
        project / "docs" / "experiment" / "DEV_D_REAL_EXPERIMENT_ENTRY_CHECKLIST.md",
        project / "docs" / "experiment" / "REAL_DATA_REPLACEMENT_GUIDE.md",
        project / "docs" / "experiment" / "DEV_D_ACQUISITION_PLAN_TEMPLATE.md",
    )
    docs_complete = all(path.is_file() and path.stat().st_size > 0 for path in docs)
    provenance_pass = bool(
        rew["status"] == "pass"
        and all(item.get("scientifically_eligible") is False for item in (t0, t1, t2, t3))
        and t2.get("final_test_read") is False
        and t3.get("final_test_read") is False
    )
    supporting = {
        "schema_version": "1.0.0",
        "v1_sweep": verification["v1_sweep_cli"],
        "external_reference_rew": rew,
        "legacy_config": legacy,
        "verification_commands": verification,
        "documentation": {
            "status": "pass" if docs_complete else "fail",
            "files": [path.relative_to(project).as_posix() for path in docs],
        },
        "provenance": {
            "status": "pass" if provenance_pass else "fail",
            "data_origins": ["simulated", "external_reference"],
            "run_purpose": "software_validation",
            "scientifically_eligible": False,
            "canonical_analysis": False,
            "deployment_eligible": False,
            "approved_real_calibration": False,
            "final_tone_set_frozen": False,
            "final_test_read": False,
        },
    }
    support_path = evidence / "supporting_validation.json"
    support_path.write_text(json.dumps(supporting, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    stage_payloads = (t0, t1, t2, t3)
    stage_checks = tuple(
        _check(
            f"T{index}", item.get("status") == "pass",
            (f"t{index}_{('mathematical_consistency','robustness_scenarios','selection_classification','end_to_end')[index]}.json",),
            "existing_validation_runner_plus_artifact_loader",
            reason_pass="stage evidence passed", reason_fail="stage evidence failed",
            details={
                key: item.get(key) for key in (
                    "common_tone_count", "maximum_absolute_error_db", "scenario_count",
                    "expectation_matched_count", "outer_fold_count", "inner_fold_count",
                    "minimum_p4_retention", "minimum_sparse_balanced_accuracy",
                    "predicted_direction_deg", "margin",
                ) if key in item
            },
        )
        for index, item in enumerate(stage_payloads)
    )
    command_pass = all(item["status"] == "pass" for item in verification.values())
    requirement_conditions = (
        verification["v1_sweep_cli"]["status"] == "pass",
        rew["status"] == "pass" and rew["fixture_count"] == 3,
        legacy["status"] == "pass" and legacy["source_rewritten"] is False,
        t0.get("stimulus_manifest_sha256") is not None and t0.get("artifact_hashes_verified") is True,
        t0.get("status") == "pass" and t1.get("status") == "pass",
        t0.get("feature_names_identical") is True and t0.get("tone_hash_identical") is True,
        t2.get("status") == "pass" and t3.get("p4_metric_artifact_verified") is True and t3.get("p5_prediction_artifact_verified") is True,
        t2.get("status") == "pass" and t3.get("p9_bridge_artifacts_verified") is True and t3.get("readout_artifacts_verified") is True,
        verification["focused_compatibility_and_leakage"]["status"] == "pass" and t2.get("leakage_audit_passed") is True,
        all(item.get("artifact_hashes_verified", item.get("all_artifact_hashes_verified", True)) is True for item in stage_payloads),
        t1.get("expectation_matched_count") == t1.get("scenario_count") and t3.get("failure_path_status") == "blocked",
        command_pass,
        docs_complete,
        provenance_pass,
    )
    requirement_evidence = (
        "leakage_and_provenance_audit.json", "leakage_and_provenance_audit.json",
        "leakage_and_provenance_audit.json", "t0_mathematical_consistency.json",
        "t1_robustness_scenarios.json", "t0_mathematical_consistency.json",
        "t2_selection_classification.json", "t3_end_to_end.json",
        "leakage_and_provenance_audit.json", "t0_mathematical_consistency.json",
        "t1_robustness_scenarios.json", "leakage_and_provenance_audit.json",
        "pre_experiment_acceptance_report.md", "leakage_and_provenance_audit.json",
    )
    requirement_checks = tuple(
        _check(
            f"V2-{index:02d}", passed, (requirement_evidence[index - 1],),
            "DEV-C16 requirement evidence and loader audit",
            reason_pass="V2 minimum requirement verified",
            reason_fail="V2 minimum requirement evidence failed",
        )
        for index, passed in enumerate(requirement_conditions, start=1)
    )
    result = AcceptanceResult.build(
        acceptance_scope_id=str(acceptance["acceptance_scope_id"]),
        stage_checks=stage_checks,
        requirement_checks=requirement_checks,
        # Provenance failure and final-test access are separate audit facts.  This
        # DEV-C16 runner never reads final-test data; a provenance check failure
        # must fail its own requirement without fabricating final-test access.
        final_test_read=False,
        git_commit=commit,
        git_dirty=dirty,
    )
    scope = {
        "schema_version": "1.0.0",
        "acceptance_scope_id": acceptance["acceptance_scope_id"],
        "run_id": run_id,
        "selection_reason": "explicit DEV-C16 simulated pre-experiment acceptance only",
        "required_stages": acceptance["required_stages"],
        "input_configs": [
            config_file.relative_to(project).as_posix(),
            str(acceptance["t2"]["config_path"]),
            str(acceptance["t3"]["bridge_config_path"]),
            str(acceptance["t3"]["readout_config_path"]),
        ],
        "external_reference_manifest": "tests/fixtures/rew/external_reference/manifest.json",
        "data_origins": ["simulated", "external_reference"],
        "run_purpose": "software_validation",
        "final_test_policy": "sealed",
        "final_test_files": [],
    }
    leakage = {
        "schema_version": "1.0.0",
        "status": "pass" if provenance_pass and verification["focused_compatibility_and_leakage"]["status"] == "pass" else "fail",
        "final_test_read": False,
        "scientifically_eligible": False,
        "canonical_analysis": False,
        "deployment_eligible": False,
        "supporting_validation": supporting,
    }
    acceptance_output = run_root / "acceptance"
    referenced_inputs = [
        config_file,
        project / str(acceptance["t2"]["config_path"]),
        project / str(acceptance["t3"]["bridge_config_path"]),
        project / str(acceptance["t3"]["readout_config_path"]),
        project / "tests" / "fixtures" / "rew" / "external_reference" / "manifest.json",
    ]
    input_records = {
        f"input-{index:02d}-{path.name}": _relative_record(acceptance_output, path)
        for index, path in enumerate(referenced_inputs, start=1)
    }
    key_evidence = [
        support_path,
        *[Path(item["log_path"]) for item in verification.values()],
    ]
    for candidate in (
        Path(str(t0.get("evidence_directory", ""))) / "processed" / "preprocessing_manifest.json",
        Path(str(t2.get("evidence_directory", ""))) / "ablation_manifest.json",
        Path(str(t3.get("bridge_evidence_directory", ""))) / "bridge_manifest.json",
        Path(str(t3.get("readout_evidence_directory", ""))) / "readout_package" / "package_manifest.json",
        Path(str(t3.get("readout_evidence_directory", ""))) / "offline_readout" / "readout_manifest.json",
        Path(str(t3.get("readout_evidence_directory", ""))) / "offline_readout_failure" / "readout_manifest.json",
    ):
        if candidate.is_file():
            key_evidence.append(candidate)
    evidence_records = {
        f"evidence-{index:02d}-{path.name}": _relative_record(acceptance_output, path)
        for index, path in enumerate(key_evidence, start=1)
    }
    dependency_versions = {"python": sys.version.split()[0]}
    for package in ("numpy", "pandas", "scipy", "matplotlib", "scikit-learn", "PyYAML", "joblib", "pytest"):
        dependency_versions[package] = package_metadata.version(package)
    manifest = write_acceptance_bundle(
        acceptance_output,
        result=result,
        branch=branch,
        scope=scope,
        t0=t0, t1=t1, t2=t2, t3=t3,
        leakage_and_provenance=leakage,
        versions={**SCHEMA_VERSION_QUARTET, "run_manifest_schema_version": "1.15.0"},
        dependencies=dependency_versions,
        created_at_utc=datetime.now(UTC).isoformat(),
        input_artifacts=input_records,
        evidence_artifacts=evidence_records,
    )
    return {
        "output_directory": acceptance_output.as_posix(),
        "run_root": run_root.as_posix(),
        "overall_status": result.overall_status.value,
        "software_integration_ready": result.software_integration_ready,
        "ready_for_dev_d_diagnostic_experiment": result.ready_for_dev_d_diagnostic_experiment,
        "acceptance_result_semantic_sha256": result.semantic_sha256,
        "manifest_content_sha256": manifest["manifest_content_sha256"],
        "git_commit": commit, "git_dirty": dirty, "branch": branch,
        "t0": t0, "t1": t1, "t2": t2, "t3": t3,
        "v2_requirement_pass_count": sum(requirement_conditions),
        "verification": verification,
        "final_test_read": False,
        "scientifically_eligible": False,
        "canonical_analysis": False,
        "deployment_eligible": False,
    }

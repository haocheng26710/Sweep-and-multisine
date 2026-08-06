"""Deterministic simulated DEV-C10/P6-A validation fixture and runner."""

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
    ConditionCompletenessResult,
    DatasetInputAuditRecord,
    DatasetQCReference,
    DatasetQCResult,
    DatasetQCScope,
    DatasetScopeMember,
    ExpectedCondition,
    MeasurementQCRollup,
    dataset_qc_sha256,
    feature_contract_sha256,
    feature_set_content_sha256,
)
from .dataset_quality_outputs import write_dataset_quality_outputs
from .hr_analysis import (
    FinalTestSeal,
    HRCalibrationGroupSpec,
    HRCalibrationScope,
    HRCalibrationScopeMember,
    resonator_specs_from_config,
)
from .hr_cli import HRCalibrationInputEntry, HRCalibrationInputManifest, execute_hr_calibration
from .quality_control import MeasurementQCResult, UnavailablePolicy, measurement_qc_sha256
from .research_gate import RunPurpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    QCCheckStatus,
    QCStatus,
    Representation,
    SourceFormat,
    artifact_sha256,
    save_feature_set,
)
from .version import SCHEMA_VERSION_QUARTET


def _feature(sample_id: str, repeat_type: str, shift_hz: float) -> FeatureSet:
    frequency = np.arange(1100.0, 2501.0, 1.0)
    centers = np.asarray([1500.0, 1680.0, 2200.0]) + shift_hz
    peak_db = np.asarray([10.0, 6.989700043360188, 3.979400086720376])
    shapes = np.stack([peak - np.abs(frequency - center) * 0.03 for center, peak in zip(centers, peak_db, strict=True)])
    values = np.maximum(-20.0, np.max(shapes, axis=0))
    source_digest = hashlib.sha256(sample_id.encode()).hexdigest()
    qc = MeasurementQCResult(
        "1.0.0", sample_id, MeasurementMode.REW_SWEEP, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION, RunPurpose.SOFTWARE_VALIDATION, (),
        UnavailablePolicy.PRESERVE, (), True, None, False,
    )
    meta = MeasurementMeta(
        sample_id=sample_id,
        **SCHEMA_VERSION_QUARTET,
        device_version="V2.5-SIMULATED",
        configuration="HR-SIM",
        angle_deg=0.0,
        session_id="S01",
        repeat_type=repeat_type,
        repeat_id=sample_id,
        experiment_step="DEV_C10_P6A_VALIDATION",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path=f"mock://misleading-design-target/{sample_id}",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=source_digest,
        provenance_uri="mock://DEV-C10-P6A/known-resonances",
        eligible_for_scientific_analysis=False,
        acquisition_block_id="B01",
    )
    return FeatureSet(
        sample_id, SCHEMA_VERSION_QUARTET["feature_schema_version"], FeatureKind.DENSE_RAW_SPL,
        tuple(f"f_{item:g}_hz" for item in frequency), values, np.ones(values.size, dtype=bool),
        ("dB",) * values.size, MeasurementMode.REW_SWEEP, Representation.DENSE_SPECTRUM,
        "sha256:" + "c" * 64, meta,
        normalization_method=None, source_magnitude_quantity="spl",
        source_qc_status=QCStatus.VALID, source_qc_sha256=measurement_qc_sha256(qc),
        source_qc_eligible_for_downstream=True,
    )


def run_hr_calibration_validation(
    *, output_root: str | Path, run_id: str, project_root: str | Path
) -> Path:
    """Build explicit simulated inputs and execute the public P6-A CLI path."""
    root = Path(output_root).resolve()
    project = Path(project_root).resolve()
    run_base = root / "simulated" / "software_validation" / run_id
    if run_base.exists():
        raise FileExistsError(f"DEV-C10 validation run already exists: {run_base}")
    run_base.mkdir(parents=True)
    config_path = project / "config" / "validation_dev_c10_hr_calibration.yaml"
    config = load_config(config_path, default_path=project / "config" / "default.yaml")
    definitions = (("CONT", -1.0), ("CONT", 1.0), ("REPOS", -5.0), ("REPOS", 5.0), ("REASM", -10.0), ("REASM", 10.0))
    features = tuple(_feature(f"hr-{repeat.lower()}-{index + 1}", repeat, shift) for index, (repeat, shift) in enumerate(definitions))
    feature_dir = run_base / "inputs" / "features"
    persisted: list[tuple[FeatureSet, Path, Path, Path]] = []
    for feature in features:
        base = feature_dir / feature.sample_id
        npz_path, json_path = save_feature_set(feature, base)
        persisted.append((feature, base, npz_path, json_path))

    dataset_scope = DatasetQCScope(
        "1.0.0", f"{run_id}-P2B", RunPurpose.SOFTWARE_VALIDATION,
        tuple(DatasetScopeMember(item.sample_id, CohortRole.DEVELOPMENT, f"condition-{index:02d}", "explicit simulated HR calibration") for index, item in enumerate(features)),
        tuple(ExpectedCondition(
            f"condition-{index:02d}", CohortRole.DEVELOPMENT, MeasurementMode.REW_SWEEP,
            "HR-SIM", "A000", 0.0, item.meta.session_id, item.meta.repeat_type,
            item.meta.reposition_round_id, item.meta.assembly_id, item.meta.acquisition_block_id, 1,
        ) for index, item in enumerate(features)),
    )
    p2_config = config["dataset_quality_control"]
    p2_config_sha = "sha256:" + hashlib.sha256(json.dumps(p2_config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    p2_result = DatasetQCResult(
        "1.0.0", dataset_scope.analysis_scope_id, dataset_scope.sha256, p2_config_sha,
        RunPurpose.SOFTWARE_VALIDATION, DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
        tuple(item.sample_id for item in features),
        tuple(ConditionCompletenessResult(
            f"condition-{index:02d}", CohortRole.DEVELOPMENT, 1, 1, 1, 0, 0, 0, 0, 0,
            QCCheckStatus.VALID, (), (item.sample_id,), (),
        ) for index, item in enumerate(features)),
        input_audit=tuple(DatasetInputAuditRecord(
            item.sample_id, CohortRole.DEVELOPMENT, feature_contract_sha256(item),
            feature_set_content_sha256(item), item.source_qc_sha256, item.meta.source_sha256,
            "explicit simulated HR calibration",
        ) for item in features),
        measurement_rollups=tuple(MeasurementQCRollup(
            item.sample_id, CohortRole.DEVELOPMENT, item.source_qc_sha256,
            QCStatus.VALID, QCStatus.VALID, QCStatus.VALID, (), (), (), (), True, None, True,
        ) for item in features),
    )
    p2_dir = run_base / "dataset_qc"
    p2_inputs = tuple({"sample_id": item.sample_id, "artifact_role": "feature_json", "path": json_path.as_posix(), "sha256": artifact_sha256(json_path)} for item, _, _, json_path in persisted)
    write_dataset_quality_outputs(p2_result, dataset_scope, p2_config, p2_dir, input_artifacts=p2_inputs, git_commit="validation-fixture", random_state=int(config["random_state"]))
    p2_reference = DatasetQCReference(p2_result.analysis_scope_id, dataset_qc_sha256(p2_result))
    specs = resonator_specs_from_config(config["hr_calibration"])
    members = tuple(HRCalibrationScopeMember.from_feature_set(
        item, artifact_id=f"feature-{item.sample_id}", feature_base_path=base.as_posix(),
        feature_npz_sha256=artifact_sha256(npz_path), feature_json_sha256=artifact_sha256(json_path),
        configuration_id="HR-SIM", direction_id="A000", calibration_group_id="G1",
        energy_fraction_group_id=item.sample_id, module_ids=("simulated_hr_module",),
        resonator_ids=tuple(spec.resonator_id for spec in specs), cohort_role="development",
        scope_role="calibration", selection_reason="explicit simulated HR validation",
    ) for item, base, npz_path, json_path in persisted)
    group = HRCalibrationGroupSpec(
        "G1", tuple(item.sample_id for item in features), "HR-SIM", ("A000",), ("S01",),
        ("CONT", "REPOS", "REASM"), "explicitly pool repeat types for separate drift summaries",
    )
    scope = HRCalibrationScope(
        "1.0.0", f"{run_id}-P6A", RunPurpose.SOFTWARE_VALIDATION, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION, members, (group,), specs, p2_reference,
        features[0].preprocessing_id, int(config["random_state"]),
        FinalTestSeal(True, ("sealed-final-test-sample",), "sha256:" + "f" * 64),
    )
    scope_path = run_base / "hr_calibration_scope.json"
    scope_path.write_text(json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = HRCalibrationInputManifest(
        "1.0.0", scope.hr_calibration_scope_id, DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
        tuple(HRCalibrationInputEntry(item.sample_id, base.as_posix(), artifact_sha256(npz_path), artifact_sha256(json_path), feature_set_content_sha256(item)) for item, base, npz_path, json_path in persisted),
    )
    input_path = run_base / "hr_calibration_inputs.json"
    input_path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return execute_hr_calibration(
        config_path=config_path, scope_path=scope_path, input_manifest_path=input_path,
        dataset_qc_directory=p2_dir, output_root=root, run_id=run_id, project_root=project,
    )

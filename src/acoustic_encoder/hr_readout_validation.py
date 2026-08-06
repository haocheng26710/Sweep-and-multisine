"""Deterministic simulated DEV-C11/P6-B validation fixture and runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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
from .hr_analysis import FinalTestSeal
from .hr_outputs import load_hr_calibration_authority
from .hr_readout import HRCalibrationReference, HRReadoutScope, HRReadoutScopeMember
from .hr_readout_cli import (
    HRReadoutInputEntry,
    HRReadoutInputManifest,
    execute_hr_readout,
)
from .hr_readout_outputs import load_hr_readout_bundle
from .hr_validation import run_hr_calibration_validation
from .quality_control import MeasurementQCResult, UnavailablePolicy, measurement_qc_sha256
from .research_gate import RunPurpose
from .schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureQualityRecord,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCCheckStatus,
    QCStatus,
    Representation,
    SourceFormat,
    artifact_sha256,
    save_feature_set,
)
from .version import SCHEMA_VERSION_QUARTET


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tone_feature(sample_id: str, gain_db: float) -> FeatureSet:
    frequencies = np.asarray([
        1470.0, 1502.0, 1530.0,
        1650.0, 1675.0, 1710.0,
        2170.0, 2208.0, 2230.0,
    ])
    base_db = np.repeat(np.asarray([6.020599913279624, 3.010299956639812, 0.0]), 3)
    values = base_db + gain_db
    names = tuple(
        f"tone_{index:06d}_{frequency:g}_hz"
        for index, frequency in enumerate(frequencies)
    )
    source_qc = MeasurementQCResult(
        "1.0.0", sample_id, MeasurementMode.SCHROEDER_MULTISINE,
        DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
        RunPurpose.SOFTWARE_VALIDATION, (), UnavailablePolicy.PRESERVE,
        (), True, None, False,
    )
    meta = MeasurementMeta(
        sample_id=sample_id,
        **SCHEMA_VERSION_QUARTET,
        device_version="V2.5-SIMULATED",
        configuration="HR-SIM",
        angle_deg=0.0,
        session_id="S01",
        repeat_type="CONT",
        repeat_id=sample_id,
        experiment_step="DEV_C11_P6B_VALIDATION",
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        source_format=SourceFormat.MOCK_AUDIO,
        source_path=f"mock://DEV-C11/{sample_id}",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=_digest(sample_id),
        provenance_uri="mock://DEV-C11-P6B/known-tone-energy",
        eligible_for_scientific_analysis=False,
        stimulus_id="DEV-C11-HR-STIMULUS",
        stimulus_hash=_digest("DEV-C11-HR-STIMULUS"),
        tone_set_id="DEV-C11-HR-TONES",
        sidecar_path=f"mock://DEV-C11/{sample_id}.json",
        audio_channel=0,
        acquisition_block_id="B01",
    )
    quality = tuple(
        FeatureQualityRecord(
            name, "available", True, (), "P8_P3_C",
            {
                "frequency_hz": float(frequency), "missing_tone": False,
                "snr_db": 60.0, "snr_status": "valid",
                "leakage_status": "valid", "period_variance_status": "valid",
            },
        )
        for name, frequency in zip(names, frequencies, strict=True)
    )
    return FeatureSet(
        sample_id, SCHEMA_VERSION_QUARTET["feature_schema_version"],
        FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE, names, values,
        np.ones(values.size, dtype=bool), ("dB",) * values.size,
        MeasurementMode.SCHROEDER_MULTISINE, Representation.SPARSE_TONES,
        "sha256:" + _digest("DEV-C11-P3C"), meta,
        tone_set_id="DEV-C11-HR-TONES", tone_set_sha256=_digest("DEV-C11-HR-TONES"),
        tone_schema_id="sha256:" + _digest("DEV-C11-HR-TONE-SCHEMA"),
        normalization_method="none", source_magnitude_quantity="transfer_ratio",
        source_magnitude_reference="sha256:" + _digest("DEV-C11-H-REF"),
        source_phase_status=PhaseStatus.RELATIVE_UNRELIABLE,
        source_qc_status=QCStatus.VALID,
        source_qc_sha256=measurement_qc_sha256(source_qc),
        source_qc_eligible_for_downstream=True,
        feature_quality=quality,
    )


def run_hr_readout_validation(
    *, output_root: str | Path, run_id: str, project_root: str | Path
) -> Path:
    """Execute P6-A authority creation then the public P6-B CLI path."""
    root = Path(output_root).resolve()
    project = Path(project_root).resolve()
    run_base = root / "simulated" / "software_validation" / run_id
    if run_base.exists():
        raise FileExistsError(f"DEV-C11 validation run already exists: {run_base}")

    calibration_run_id = f"{run_id}-P6A-AUTHORITY"
    calibration_dir = run_hr_calibration_validation(
        output_root=root, run_id=calibration_run_id, project_root=project
    )
    calibration = load_hr_calibration_authority(calibration_dir)
    run_base.mkdir(parents=True, exist_ok=False)
    config_path = project / "config" / "validation_dev_c11_hr_readout.yaml"
    config = load_config(config_path, default_path=project / "config" / "default.yaml")

    features = (
        _tone_feature("hr-ms-1", 0.0),
        _tone_feature("hr-ms-2", 1.0),
    )
    feature_dir = run_base / "inputs" / "features"
    persisted = []
    for feature in features:
        base = feature_dir / feature.sample_id
        npz_path, json_path = save_feature_set(feature, base)
        persisted.append((feature, base, npz_path, json_path))

    dataset_scope = DatasetQCScope(
        "1.0.0", f"{run_id}-P2B", RunPurpose.SOFTWARE_VALIDATION,
        tuple(
            DatasetScopeMember(
                feature.sample_id, CohortRole.DEVELOPMENT,
                f"condition-{index:02d}", "explicit simulated P6-B validation",
            )
            for index, feature in enumerate(features)
        ),
        tuple(
            ExpectedCondition(
                f"condition-{index:02d}", CohortRole.DEVELOPMENT,
                MeasurementMode.SCHROEDER_MULTISINE, "HR-SIM", "A000", 0.0,
                "S01", "CONT", None, None, "B01", 1,
            )
            for index, _ in enumerate(features)
        ),
    )
    p2_config = config["dataset_quality_control"]
    p2_config_sha = "sha256:" + hashlib.sha256(
        json.dumps(p2_config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    p2_result = DatasetQCResult(
        "1.0.0", dataset_scope.analysis_scope_id, dataset_scope.sha256,
        p2_config_sha, RunPurpose.SOFTWARE_VALIDATION, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION, tuple(item.sample_id for item in features),
        tuple(
            ConditionCompletenessResult(
                f"condition-{index:02d}", CohortRole.DEVELOPMENT,
                1, 1, 1, 0, 0, 0, 0, 0, QCCheckStatus.VALID, (),
                (feature.sample_id,), (),
            )
            for index, feature in enumerate(features)
        ),
        input_audit=tuple(
            DatasetInputAuditRecord(
                feature.sample_id, CohortRole.DEVELOPMENT,
                feature_contract_sha256(feature), feature_set_content_sha256(feature),
                feature.source_qc_sha256, feature.meta.source_sha256,
                "explicit simulated P6-B validation",
            )
            for feature in features
        ),
        measurement_rollups=tuple(
            MeasurementQCRollup(
                feature.sample_id, CohortRole.DEVELOPMENT, feature.source_qc_sha256,
                QCStatus.VALID, QCStatus.VALID, QCStatus.VALID,
                (), (), (), (), True, None, True,
            )
            for feature in features
        ),
    )
    p2_dir = run_base / "dataset_qc"
    p2_inputs = tuple(
        {
            "sample_id": feature.sample_id, "artifact_role": "feature_json",
            "path": json_path.as_posix(), "sha256": artifact_sha256(json_path),
        }
        for feature, _, _, json_path in persisted
    )
    write_dataset_quality_outputs(
        p2_result, dataset_scope, p2_config, p2_dir,
        input_artifacts=p2_inputs, git_commit="validation-fixture",
        random_state=int(config["random_state"]),
    )

    calibration_reference = HRCalibrationReference(
        calibration.result.calibration_id,
        (calibration_dir / "hr_calibration.json").as_posix(),
        artifact_sha256(calibration_dir / "hr_calibration.json"),
        (calibration_dir / "hr_calibration_manifest.json").as_posix(),
        artifact_sha256(calibration_dir / "hr_calibration_manifest.json"),
        (calibration_dir / "hr_calibration_manifest.sha256").as_posix(),
        artifact_sha256(calibration_dir / "hr_calibration_manifest.sha256"),
    )
    members = tuple(
        HRReadoutScopeMember(
            feature.sample_id, base.as_posix(), artifact_sha256(npz_path),
            artifact_sha256(json_path), feature_set_content_sha256(feature),
            feature_contract_sha256(feature), "HR-SIM", "A000", 0.0, "S01",
            "CONT", DatasetRole.SOFTWARE_VALIDATION,
            "explicit simulated P6-B validation", feature.tone_set_id,
            feature.tone_set_sha256, feature.meta.stimulus_id,
            feature.meta.stimulus_hash, feature.source_magnitude_quantity,
            feature.source_magnitude_reference, "development",
        )
        for feature, base, npz_path, json_path in persisted
    )
    scope = HRReadoutScope(
        "1.0.0", f"{run_id}-P6B", members, calibration_reference, "G1",
        ("R1", "R2", "R3"), "calibrated_window", "narrowband_trapezoid",
        DatasetQCReference(p2_result.analysis_scope_id, dataset_qc_sha256(p2_result)),
        calibration.scope.final_test_seal, RunPurpose.SOFTWARE_VALIDATION,
        DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION,
        int(config["random_state"]),
    )
    scope_path = run_base / "hr_readout_scope.json"
    scope_path.write_text(
        json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = HRReadoutInputManifest(
        "1.0.0", scope.hr_readout_scope_id, DataOrigin.SIMULATED,
        DatasetRole.SOFTWARE_VALIDATION,
        tuple(
            HRReadoutInputEntry(
                feature.sample_id, base.as_posix(), artifact_sha256(npz_path),
                artifact_sha256(json_path), feature_set_content_sha256(feature),
                feature_contract_sha256(feature),
            )
            for feature, base, npz_path, json_path in persisted
        ),
    )
    input_path = run_base / "hr_readout_inputs.json"
    input_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output = execute_hr_readout(
        config_path=config_path, scope_path=scope_path,
        input_manifest_path=input_path, dataset_qc_directory=p2_dir,
        output_root=root, run_id=run_id, project_root=project,
    )
    result = load_hr_readout_bundle(output).result
    expected_q = np.asarray([4.0 / 7.0, 2.0 / 7.0, 1.0 / 7.0])
    for sample in result.sample_readouts:
        actual_q = np.asarray([item.q_i for item in sample.energy_fractions])
        if not np.allclose(actual_q, expected_q, atol=1e-12, rtol=0.0):
            raise AssertionError("DEV-C11 known energy fractions were not recovered")
    summary = {
        "schema_version": "1.0.0",
        "processing_status": "completed",
        "data_origin": "simulated",
        "run_purpose": "software_validation",
        "scientifically_eligible": False,
        "deployment_allowed": False,
        "absolute_energy_comparable": False,
        "expected_energy_fractions": expected_q.tolist(),
        "maximum_energy_fraction_error": max(
            abs(item.q_i - expected)
            for sample in result.sample_readouts
            for item, expected in zip(sample.energy_fractions, expected_q, strict=True)
        ),
        "signed_peak_detuning_hz": {
            item.resonator_id: item.signed_detuning_hz
            for item in result.sample_readouts[0].mappings
        },
        "hr_readout_output": output.as_posix(),
        "calibration_output": calibration_dir.as_posix(),
    }
    summary_path = run_base / "validation_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output

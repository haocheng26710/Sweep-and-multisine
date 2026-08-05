"""Deterministic simulated P2-B validation fixture and explicit artifact setup."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .config import load_config
from .dataset_quality_cli import run_dataset_quality_cli
from .dataset_quality_control import (
    CohortRole,
    DatasetQCScope,
    DatasetScopeMember,
    ExpectedCondition,
    DatasetQCResult,
)
from .dataset_quality_outputs import load_dataset_quality_bundle
from .mock_data import generate_directional_feature_set_mock
from .quality_control import (
    MeasurementQCResult,
    UnavailablePolicy,
    measurement_qc_sha256,
)
from .research_gate import RunPurpose
from .schemas import artifact_sha256, save_feature_set


@dataclass(frozen=True, slots=True)
class DatasetQCValidationResult:
    output_directory: Path
    result: DatasetQCResult
    scope_path: Path
    input_manifest_path: Path


def _condition_key(feature: Any) -> tuple[Any, ...]:
    meta = feature.meta
    return (
        meta.measurement_mode.value,
        str(meta.configuration),
        float(meta.angle_deg),
        str(meta.session_id),
        str(meta.repeat_type),
        meta.reposition_round_id,
        meta.assembly_id,
        meta.acquisition_block_id,
    )


def run_simulated_dataset_quality_validation(
    *,
    project_root: Path,
    config_path: Path,
    output_root: Path,
    run_id: str,
    feature_count: int = 71,
    canonical_ready_fixture: bool = False,
) -> DatasetQCValidationResult:
    """Create explicit simulated inputs, then exercise the same P2-B CLI."""
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    run_root = output_root / "simulated" / "software_validation" / run_id
    if run_root.exists():
        raise FileExistsError(f"validation run already exists: {run_root}")
    resolved = load_config(
        config_path,
        default_path=project_root / "config" / "default.yaml",
    )
    features = generate_directional_feature_set_mock(
        feature_count=feature_count,
        random_state=int(resolved["random_state"]),
        repeat_noise_scale=0.5,
    )
    if canonical_ready_fixture:
        grouped_features: dict[tuple[Any, ...], list[Any]] = {}
        for feature in features:
            grouped_features.setdefault(_condition_key(feature), []).append(feature)
        expanded = []
        for key in sorted(
            grouped_features,
            key=lambda item: tuple(str(value) for value in item),
        ):
            group = grouped_features[key]
            prototype = group[0]
            center = np.asarray(prototype.values, dtype=np.float64)
            for index in range(4):
                if index < len(group):
                    source = group[index]
                else:
                    source = prototype
                sample_id = f"{prototype.sample_id}_CANON_{index + 1:02d}"
                digest = hashlib.sha256(
                    sample_id.encode("utf-8") + np.asarray(center, dtype="<f8").tobytes()
                ).hexdigest()
                meta = replace(
                    source.meta,
                    sample_id=sample_id,
                    repeat_id=f"CANON-{index + 1:02d}",
                    source_path=f"mock-feature://{sample_id}",
                    source_sha256=digest,
                    experiment_step="DEV_C7_P4B_CANONICAL_GATE_MOCK",
                )
                expanded.append(
                    replace(
                        source,
                        sample_id=sample_id,
                        meta=meta,
                        values=center.copy(),
                    )
                )
        features = tuple(expanded)
    qcs = tuple(
        MeasurementQCResult(
            qc_schema_version="1.0.0",
            sample_id=feature.sample_id,
            measurement_mode=feature.source_measurement_mode,
            data_origin=feature.meta.data_origin,
            dataset_role=feature.meta.dataset_role,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            checks=(),
            unavailable_required_policy=UnavailablePolicy.PRESERVE,
            manual_review_reasons=feature.meta.manual_review_reasons,
            human_valid=feature.meta.valid,
            human_exclusion_reason=feature.meta.exclusion_reason,
            scientifically_eligible=False,
        )
        for feature in features
    )
    features = tuple(
        replace(
            feature,
            source_qc_sha256=measurement_qc_sha256(qc),
            source_qc_eligible_for_downstream=qc.eligible_for_downstream,
        )
        for feature, qc in zip(features, qcs, strict=True)
    )

    grouped: dict[tuple[Any, ...], list[str]] = {}
    for feature in features:
        grouped.setdefault(_condition_key(feature), []).append(feature.sample_id)
    condition_id_by_key = {
        key: f"condition-{index:03d}"
        for index, key in enumerate(sorted(grouped, key=lambda item: tuple(str(value) for value in item)))
    }
    conditions = []
    for key in sorted(grouped, key=lambda item: condition_id_by_key[item]):
        mode, configuration, angle, session, repeat_type, reposition, assembly, block = key
        conditions.append(
            ExpectedCondition(
                condition_id=condition_id_by_key[key],
                cohort_role=CohortRole.DEVELOPMENT,
                measurement_mode=mode,
                configuration_id=configuration,
                direction_id=f"A{int(round(angle)):03d}",
                direction_angle_deg=angle,
                session_id=session,
                repeat_type=repeat_type,
                reposition_round_id=reposition,
                assembly_id=assembly,
                acquisition_block_id=block,
                expected_count=len(grouped[key]),
            )
        )
    scope = DatasetQCScope(
        schema_version="1.0.0",
        analysis_scope_id=f"{run_id}:simulated-p2b",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        members=tuple(
            DatasetScopeMember(
                sample_id=feature.sample_id,
                cohort_role=CohortRole.DEVELOPMENT,
                expected_condition_id=condition_id_by_key[_condition_key(feature)],
                selection_reason="deterministic DEV-C6 software-validation fixture",
            )
            for feature in features
        ),
        expected_conditions=tuple(conditions),
    )

    inputs_root = run_root / "inputs"
    inputs_root.mkdir(parents=True, exist_ok=False)
    scope_path = inputs_root / "dataset_scope.yaml"
    scope_path.write_text(
        yaml.safe_dump(scope.to_dict(), sort_keys=False),
        encoding="utf-8",
    )
    measurements: list[dict[str, Any]] = []
    for feature, qc in zip(features, qcs, strict=True):
        feature_base = inputs_root / "features" / feature.sample_id
        npz_path, json_path = save_feature_set(feature, feature_base)
        qc_path = inputs_root / "p2a" / feature.sample_id / "quality_control.json"
        qc_path.parent.mkdir(parents=True, exist_ok=True)
        qc_path.write_text(
            json.dumps(qc.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        measurements.append(
            {
                "sample_id": feature.sample_id,
                "feature_base_path": feature_base.as_posix(),
                "feature_npz_sha256": artifact_sha256(npz_path),
                "feature_json_sha256": artifact_sha256(json_path),
                "measurement_qc_path": qc_path.as_posix(),
                "measurement_qc_file_sha256": artifact_sha256(qc_path),
                "measurement_qc_result_sha256": measurement_qc_sha256(qc),
            }
        )
    input_manifest_path = inputs_root / "dataset_inputs.json"
    input_manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "analysis_scope_id": scope.analysis_scope_id,
                "data_origin": "simulated",
                "dataset_role": "software_validation",
                "measurements": measurements,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    exit_code = run_dataset_quality_cli(
        (
            "--config",
            str(config_path),
            "--scope",
            str(scope_path),
            "--inputs",
            str(input_manifest_path),
            "--output-root",
            str(output_root),
            "--run-id",
            run_id,
        ),
        project_root=project_root,
    )
    if exit_code != 0:
        raise RuntimeError(f"simulated dataset QC validation failed with exit code {exit_code}")
    output = run_root / "dataset_qc"
    return DatasetQCValidationResult(
        output_directory=output,
        result=load_dataset_quality_bundle(output),
        scope_path=scope_path,
        input_manifest_path=input_manifest_path,
    )

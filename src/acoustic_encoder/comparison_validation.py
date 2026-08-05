"""Deterministic simulated DEV-C7 validation fixture over persisted FeatureSets."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import numpy as np

from .comparison_metrics import (
    ComparisonAnalysisScope,
    CrossModePairSpec,
    ScopedFeatureReference,
    ScopedMeasurementContext,
)
from .comparison_metrics_cli import run_comparison_metrics_cli
from .config import load_config
from .dataset_quality_control import CohortRole
from .metrics import AnalysisScope, QCInclusionPolicy, ScopeRole, SelectionPolicy
from .mock_data import generate_directional_feature_set_mock
from .research_gate import RunPurpose
from .schemas import FeatureKind, QCStatus, artifact_sha256, save_feature_set


def _state_id(feature: Any) -> str:
    meta = feature.meta
    return (
        f"{meta.configuration}:A{int(meta.angle_deg):03d}:{meta.session_id}:"
        f"{meta.repeat_type}:{meta.repeat_id}:{meta.reposition_round_id}:"
        f"{meta.assembly_id}:{meta.acquisition_block_id}"
    )


def run_simulated_comparison_validation(
    *,
    project_root: str | Path,
    output_root: str | Path,
    run_id: str,
    feature_count: int = 701,
) -> Path:
    """Persist explicit inputs and execute the real P4-B CLI without raw data."""
    root = Path(project_root).resolve()
    output_root = Path(output_root).resolve()
    run_root = output_root / "simulated" / "software_validation" / run_id
    if run_root.exists():
        raise FileExistsError(f"comparison validation run already exists: {run_root}")
    input_root = run_root / "comparison_inputs"
    input_root.mkdir(parents=True)
    resolved = load_config(root / "config" / "default.yaml")
    configurations = ("U4SYM", "U4ENC")
    directions = (0.0, 90.0)
    features: dict[str, Any] = {}
    contexts: dict[str, ScopedMeasurementContext] = {}
    sweep_by_key: dict[tuple[Any, ...], tuple[str, Any]] = {}
    multisine_by_key: dict[tuple[Any, ...], tuple[str, Any]] = {}

    def register(artifact_id: str, feature: Any) -> None:
        features[artifact_id] = feature
        contexts.setdefault(
            feature.sample_id,
            ScopedMeasurementContext(
                sample_id=feature.sample_id,
                cohort_role=CohortRole.DEVELOPMENT,
                direction_id=f"A{int(feature.meta.angle_deg):03d}",
                physical_state_id=_state_id(feature),
                selection_reason="deterministic DEV-C7 software validation fixture",
            ),
        )

    for configuration in configurations:
        for kind in (
            FeatureKind.DENSE_RAW_SPL,
            FeatureKind.DENSE_DEMEANED_DB,
            FeatureKind.DENSE_ZSCORE,
        ):
            for index, feature in enumerate(
                generate_directional_feature_set_mock(
                    configuration=configuration,
                    direction_order_deg=directions,
                    feature_count=feature_count,
                    feature_kind=kind,
                    random_state=20260805,
                )
            ):
                register(f"{configuration}-{kind.value}-{index:03d}", feature)
        sweep_features = generate_directional_feature_set_mock(
            configuration=configuration,
            direction_order_deg=directions,
            feature_count=feature_count,
            feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
            included_repeat_types=("REPOS",),
            random_state=20260805,
        )
        multisine_features = generate_directional_feature_set_mock(
            configuration=configuration,
            direction_order_deg=directions,
            feature_count=feature_count,
            feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
            included_repeat_types=("REPOS",),
            random_state=20260805,
        )
        known_bias = np.linspace(-0.25, 0.75, feature_count, dtype=np.float64)
        for index, (sweep, multisine) in enumerate(zip(sweep_features, multisine_features, strict=True)):
            sweep = replace(
                sweep,
                normalization_method="none",
                source_magnitude_reference="mock-reference://DEV-C7/shared-db",
            )
            multi_meta = replace(
                multisine.meta,
                sample_id=f"{multisine.sample_id}-MS",
                source_path=f"{multisine.meta.source_path}-MS",
            )
            multisine = replace(
                multisine,
                sample_id=multi_meta.sample_id,
                meta=multi_meta,
                values=np.asarray(sweep.values + known_bias, dtype=np.float64),
                normalization_method="none",
                source_magnitude_reference="mock-reference://DEV-C7/shared-db",
            )
            sweep_id = f"{configuration}-tone-sweep-{index:03d}"
            multi_id = f"{configuration}-tone-multisine-{index:03d}"
            register(sweep_id, sweep)
            register(multi_id, multisine)
            key = (
                configuration, sweep.meta.angle_deg, sweep.meta.session_id,
                sweep.meta.repeat_type, sweep.meta.repeat_id,
                sweep.meta.reposition_round_id, sweep.meta.assembly_id,
                sweep.meta.acquisition_block_id,
            )
            sweep_by_key[key] = (sweep_id, sweep)
            multisine_by_key[key] = (multi_id, multisine)

    sample_ids = tuple(contexts)
    base_scope = AnalysisScope(
        schema_version="1.1.0",
        analysis_scope_id=f"DEV-C7:{run_id}",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=sample_ids,
        partition=None,
        direction_order_deg=directions,
        selection_policy=SelectionPolicy("explicit-persisted-features-only"),
        qc_inclusion_policy=QCInclusionPolicy(
            "valid-warning", (QCStatus.VALID, QCStatus.WARNING)
        ),
    )
    pairs: list[CrossModePairSpec] = []
    for pair_index, key in enumerate(sorted(sweep_by_key, key=str)):
        sweep_id, sweep = sweep_by_key[key]
        multi_id, _ = multisine_by_key[key]
        pairs.append(
            CrossModePairSpec(
                match_pair_id=f"match-{pair_index:03d}",
                sweep_artifact_id=sweep_id,
                multisine_artifact_id=multi_id,
                direction_id=f"A{int(sweep.meta.angle_deg):03d}",
                direction_angle_deg=float(sweep.meta.angle_deg),
                configuration_id=str(sweep.meta.configuration),
                physical_state_id=_state_id(sweep),
                session_id=sweep.meta.session_id,
                repeat_type=sweep.meta.repeat_type,
                repeat_id=sweep.meta.repeat_id,
                reposition_round_id=sweep.meta.reposition_round_id,
                assembly_id=sweep.meta.assembly_id,
                acquisition_block_id=sweep.meta.acquisition_block_id,
                cohort_role=CohortRole.DEVELOPMENT,
            )
        )
    scope = ComparisonAnalysisScope(
        schema_version="1.0.0",
        analysis_scope=base_scope,
        measurements=tuple(contexts.values()),
        feature_references=tuple(
            ScopedFeatureReference.from_feature_set(
                artifact_id, feature, primary_for_dataset_qc=False
            )
            for artifact_id, feature in features.items()
        ),
        cross_mode_pairs=tuple(pairs),
    )
    entries: list[dict[str, str]] = []
    for artifact_id, feature in features.items():
        base = input_root / "features" / artifact_id
        npz_path, json_path = save_feature_set(feature, base)
        entries.append(
            {
                "artifact_id": artifact_id,
                "sample_id": feature.sample_id,
                "feature_base_path": base.as_posix(),
                "feature_npz_sha256": artifact_sha256(npz_path),
                "feature_json_sha256": artifact_sha256(json_path),
            }
        )
    scope_path = input_root / "comparison_scope.json"
    scope_path.write_text(
        json.dumps(scope.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path = input_root / "comparison_inputs.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "analysis_scope_id": base_scope.analysis_scope_id,
                "data_origin": "simulated",
                "run_purpose": "software_validation",
                "features": entries,
            },
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    status = run_comparison_metrics_cli(
        [
            "--config", str(root / "config" / "default.yaml"),
            "--scope", str(scope_path),
            "--inputs", str(manifest_path),
            "--output-root", str(output_root),
            "--run-id", run_id,
        ],
        project_root=root,
    )
    if status != 0:
        raise RuntimeError(f"DEV-C7 validation CLI failed with status {status}")
    return run_root / "comparison_metrics"

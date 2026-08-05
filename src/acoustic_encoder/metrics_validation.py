"""Deterministic simulated FeatureSet-only P4-A validation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .metrics import (
    AnalysisScope,
    DirectionMetricsResult,
    QCInclusionPolicy,
    ScopeRole,
    SelectionPolicy,
    analyze_direction_feature_sets,
)
from .metrics_outputs import write_direction_metrics_outputs
from .mock_data import generate_directional_feature_set_mock
from .research_gate import RunPurpose
from .schemas import QCStatus


@dataclass(frozen=True, slots=True)
class SimulatedDirectionMetricsValidationResult:
    output_directory: Path
    metrics: DirectionMetricsResult


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


def run_simulated_direction_metrics_validation(
    *,
    output_root: str | Path,
    run_id: str,
    metrics_config: Mapping[str, Any],
    random_state: int = 20260805,
    feature_count: int = 71,
) -> SimulatedDirectionMetricsValidationResult:
    """Run a four-direction, multi-repeat P4-A software validation."""
    output_directory = (
        Path(output_root)
        / "simulated"
        / "software_validation"
        / _safe_run_id(run_id)
    )
    try:
        output_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"direction metrics validation output already exists: {output_directory}"
        ) from exc

    features = generate_directional_feature_set_mock(
        configuration="U4ENC",
        direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        feature_count=feature_count,
        random_state=random_state,
    )
    scope = AnalysisScope(
        schema_version="1.0.0",
        analysis_scope_id=f"{run_id}:U4ENC:dense_demeaned_db",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=tuple(feature.sample_id for feature in features),
        partition=None,
        direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        selection_policy=SelectionPolicy(
            policy_id="explicit-human-valid-no-manual-review",
            require_human_valid=True,
            exclude_manual_review=True,
        ),
        qc_inclusion_policy=QCInclusionPolicy(
            policy_id="valid-and-warning",
            included_statuses=(QCStatus.VALID, QCStatus.WARNING),
            missing_status="exclude",
            allow_exclude_candidate=False,
        ),
    )
    metrics = analyze_direction_feature_sets(features, scope, metrics_config)
    write_direction_metrics_outputs(
        metrics,
        output_directory / "metrics",
    )
    return SimulatedDirectionMetricsValidationResult(
        output_directory=output_directory,
        metrics=metrics,
    )

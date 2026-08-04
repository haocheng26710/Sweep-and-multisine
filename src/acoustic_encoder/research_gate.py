"""Run-purpose gate preventing validation data from becoming research evidence."""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from .schemas import DataOrigin, MeasurementMeta


class RunPurpose(str, Enum):
    SOFTWARE_VALIDATION = "software_validation"
    RESEARCH_ANALYSIS = "research_analysis"


class ResearchGateError(ValueError):
    """Raised when a research run contains provenance-ineligible input."""


def normalize_run_purpose(value: str | RunPurpose) -> RunPurpose:
    if isinstance(value, RunPurpose):
        return value
    return RunPurpose(value)


def enforce_research_gate(
    run_purpose: str | RunPurpose,
    measurements: Iterable[MeasurementMeta],
) -> tuple[MeasurementMeta, ...]:
    """Return materialized metadata after enforcing research provenance rules."""
    purpose = normalize_run_purpose(run_purpose)
    materialized = tuple(measurements)
    if purpose is RunPurpose.SOFTWARE_VALIDATION:
        return materialized
    if not materialized:
        raise ResearchGateError("research_analysis requires at least one measurement")
    violations = [
        meta
        for meta in materialized
        if (
            meta.data_origin is not DataOrigin.REAL_EXPERIMENT
            or not meta.eligible_for_scientific_analysis
        )
    ]
    if violations:
        details = ", ".join(
            f"{meta.sample_id} ({meta.data_origin.value}, "
            f"eligible={meta.eligible_for_scientific_analysis})"
            for meta in violations
        )
        raise ResearchGateError(
            "research_analysis accepts only eligible real_experiment data; "
            f"rejected: {details}"
        )
    return materialized

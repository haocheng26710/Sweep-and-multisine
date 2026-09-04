"""Typed decision-level boundaries frozen by GEN-ENC-1 PHASE A."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .estimator import CandidateResult, weighted_empirical_quantile


REQUIRED_FAMILIES = (
    "HAND_DESIGNED",
    "NEAR_INDEPENDENT",
    "FIXED_SEED_RANDOM_DISORDERED",
    "PHYSICS_METAMATERIAL_INSPIRED",
)


@dataclass(frozen=True)
class CandidateDecision:
    level: str
    result: CandidateResult

    def __post_init__(self) -> None:
        if self.level != "CANDIDATE":
            raise ValueError("candidate decision level is fixed")


@dataclass(frozen=True)
class FamilyDecision:
    level: str
    family_id: str
    technical_status: str
    scientific_status: str
    family_endpoint: float | None
    claim_limit: str = "PREREGISTERED_ENSEMBLE_ONLY"

    @classmethod
    def from_candidates(cls, family_id: str, candidates: Sequence[CandidateResult]) -> "FamilyDecision":
        if not candidates or any(item.level != "CANDIDATE" for item in candidates):
            return cls("FAMILY", family_id, "UNAVAILABLE", "NOT_TESTED", None)
        if any(item.technical_status != "PASS" or item.primary_endpoint is None for item in candidates):
            return cls("FAMILY", family_id, "UNAVAILABLE", "NOT_TESTED", None)
        endpoint = weighted_empirical_quantile(
            [item.primary_endpoint for item in candidates], [1.0] * len(candidates), 0.05
        )
        passed = endpoint > 1.0 and all(item.stable_rank == 3 for item in candidates)
        return cls("FAMILY", family_id, "PASS", "PASS" if passed else "NEGATIVE", endpoint)


@dataclass(frozen=True)
class GlobalDecision:
    level: str
    technical_status: str
    outcome: str
    family_ids: tuple[str, ...]
    scalar_global_pass: None = None
    claim_limit: str = "PREREGISTERED_INSTANCES_OR_ENSEMBLES_ONLY"

    @classmethod
    def from_families(cls, families: Mapping[str, FamilyDecision]) -> "GlobalDecision":
        if set(families) != set(REQUIRED_FAMILIES):
            return cls("GLOBAL", "UNAVAILABLE", "UNAVAILABLE", tuple(sorted(families)))
        if any(item.technical_status != "PASS" for item in families.values()):
            return cls("GLOBAL", "UNAVAILABLE", "UNAVAILABLE", REQUIRED_FAMILIES)
        statuses = {item.scientific_status for item in families.values()}
        outcome = "BOUNDED_COMPARATIVE_RESULT" if len(statuses) == 1 else "MIXED"
        return cls("GLOBAL", "PASS", outcome, REQUIRED_FAMILIES)

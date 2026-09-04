"""GEN-ENC E1 methods.

The package implements only the frozen identifiability and deterministic
synthetic-fixture contract.  It does not load project data or generate
topologies.
"""

from .bridge import BridgeResult, evaluate_sampled_bridge
from .decisions import CandidateDecision, FamilyDecision, GlobalDecision
from .estimator import (
    CandidateResult,
    WhitenerResult,
    embed_complex_responses,
    evaluate_candidate,
    fit_whitener,
    projection_matrices,
    trapezoidal_weights,
    weighted_empirical_quantile,
)
from .identifiability import gauge_transform, observable_operator

__all__ = [
    "BridgeResult",
    "CandidateDecision",
    "CandidateResult",
    "FamilyDecision",
    "GlobalDecision",
    "WhitenerResult",
    "embed_complex_responses",
    "evaluate_candidate",
    "evaluate_sampled_bridge",
    "fit_whitener",
    "gauge_transform",
    "observable_operator",
    "projection_matrices",
    "trapezoidal_weights",
    "weighted_empirical_quantile",
]

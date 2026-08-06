"""Typed DEV-C16 pre-experiment acceptance decisions.

This module aggregates evidence produced by existing P1--P9 validators.  It does
not implement measurement, feature, metric, selection, or classification math.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Iterable, Mapping


ACCEPTANCE_SCHEMA_VERSION = "1.0.0"


class AcceptanceStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    check_id: str
    status: AcceptanceStatus
    required: bool
    reason: str
    evidence_files: tuple[str, ...] = ()
    verification: str = ""
    evidence_sha256: str | None = None
    limitations: tuple[str, ...] = ()
    details: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.reason.strip():
            raise ValueError("acceptance check_id and reason are required")
        if self.status is AcceptanceStatus.PASS and not self.evidence_files:
            raise ValueError("passing acceptance checks require evidence files")

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "status": self.status.value,
            "required": self.required,
            "reason": self.reason,
            "evidence_files": list(self.evidence_files),
            "verification": self.verification,
            "evidence_sha256": self.evidence_sha256,
            "limitations": list(self.limitations),
            "details": dict(self.details or {}),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AcceptanceCheck":
        return cls(
            check_id=str(payload["check_id"]),
            status=AcceptanceStatus(str(payload["status"])),
            required=bool(payload["required"]),
            reason=str(payload["reason"]),
            evidence_files=tuple(str(item) for item in payload.get("evidence_files", ())),
            verification=str(payload.get("verification", "")),
            evidence_sha256=(
                None
                if payload.get("evidence_sha256") is None
                else str(payload["evidence_sha256"])
            ),
            limitations=tuple(str(item) for item in payload.get("limitations", ())),
            details=dict(payload.get("details", {})),
        )


@dataclass(frozen=True, slots=True)
class ScenarioEvidence:
    scenario_id: str
    expected_status: str
    actual_status: str
    expectation_matched: bool
    acceptance_status: AcceptanceStatus
    evidence: Mapping[str, Any]
    reason: str

    @classmethod
    def evaluate(
        cls,
        *,
        scenario_id: str,
        expected_status: str,
        actual_status: str,
        evidence: Mapping[str, Any],
    ) -> "ScenarioEvidence":
        matched = expected_status == actual_status
        return cls(
            scenario_id=scenario_id,
            expected_status=expected_status,
            actual_status=actual_status,
            expectation_matched=matched,
            acceptance_status=(AcceptanceStatus.PASS if matched else AcceptanceStatus.FAIL),
            evidence=dict(evidence),
            reason=("expectation_matched" if matched else "unexpected_scenario_status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "expectation_matched": self.expectation_matched,
            "acceptance_status": self.acceptance_status.value,
            "evidence": dict(self.evidence),
            "reason": self.reason,
        }


def _aggregate(checks: Iterable[AcceptanceCheck]) -> AcceptanceStatus:
    required = tuple(item for item in checks if item.required)
    if any(item.status is AcceptanceStatus.FAIL for item in required):
        return AcceptanceStatus.FAIL
    if any(item.status is AcceptanceStatus.UNAVAILABLE for item in required):
        return AcceptanceStatus.UNAVAILABLE
    return AcceptanceStatus.PASS


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    schema_version: str
    acceptance_scope_id: str
    stage_checks: tuple[AcceptanceCheck, ...]
    requirement_checks: tuple[AcceptanceCheck, ...]
    overall_status: AcceptanceStatus
    git_commit: str
    git_dirty: bool
    final_test_read: bool
    software_integration_ready: bool
    ready_for_dev_d_diagnostic_experiment: bool
    scientifically_eligible: bool = False
    canonical_analysis: bool = False
    deployment_eligible: bool = False
    approved_real_calibration: bool = False
    final_tone_set_frozen: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != ACCEPTANCE_SCHEMA_VERSION:
            raise ValueError("unsupported acceptance schema version")
        if not self.acceptance_scope_id.strip():
            raise ValueError("acceptance_scope_id is required")
        if len(self.stage_checks) != 4:
            raise ValueError("acceptance requires exactly T0 through T3 stage checks")
        if len(self.requirement_checks) != 14:
            raise ValueError("acceptance requires exactly 14 V2 requirement checks")
        unsafe = (
            self.scientifically_eligible
            or self.canonical_analysis
            or self.deployment_eligible
            or self.approved_real_calibration
            or self.final_tone_set_frozen
        )
        if unsafe:
            raise ValueError("DEV-C16 cannot upgrade scientific or deployment state")
        expected_ready = (
            self.overall_status is AcceptanceStatus.PASS
            and not self.git_dirty
            and not self.final_test_read
        )
        if self.software_integration_ready != expected_ready:
            raise ValueError("software integration readiness is inconsistent with gates")
        if self.ready_for_dev_d_diagnostic_experiment != expected_ready:
            raise ValueError("DEV-D readiness is inconsistent with gates")

    @classmethod
    def build(
        cls,
        *,
        acceptance_scope_id: str,
        stage_checks: Iterable[AcceptanceCheck],
        requirement_checks: Iterable[AcceptanceCheck],
        final_test_read: bool,
        git_commit: str,
        git_dirty: bool,
    ) -> "AcceptanceResult":
        stages = tuple(stage_checks)
        requirements = tuple(requirement_checks)
        gate_status = _aggregate((*stages, *requirements))
        if final_test_read:
            gate_status = AcceptanceStatus.FAIL
        ready = gate_status is AcceptanceStatus.PASS and not git_dirty and not final_test_read
        return cls(
            schema_version=ACCEPTANCE_SCHEMA_VERSION,
            acceptance_scope_id=acceptance_scope_id,
            stage_checks=stages,
            requirement_checks=requirements,
            overall_status=gate_status,
            git_commit=git_commit,
            git_dirty=git_dirty,
            final_test_read=final_test_read,
            software_integration_ready=ready,
            ready_for_dev_d_diagnostic_experiment=ready,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "acceptance_scope_id": self.acceptance_scope_id,
            "stage_checks": [item.to_dict() for item in self.stage_checks],
            "requirement_checks": [item.to_dict() for item in self.requirement_checks],
            "overall_status": self.overall_status.value,
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "final_test_read": self.final_test_read,
            "software_integration_ready": self.software_integration_ready,
            "ready_for_dev_d_diagnostic_experiment": self.ready_for_dev_d_diagnostic_experiment,
            "scientifically_eligible": self.scientifically_eligible,
            "canonical_analysis": self.canonical_analysis,
            "deployment_eligible": self.deployment_eligible,
            "approved_real_calibration": self.approved_real_calibration,
            "final_tone_set_frozen": self.final_tone_set_frozen,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AcceptanceResult":
        return cls(
            schema_version=str(payload["schema_version"]),
            acceptance_scope_id=str(payload["acceptance_scope_id"]),
            stage_checks=tuple(
                AcceptanceCheck.from_dict(item) for item in payload["stage_checks"]
            ),
            requirement_checks=tuple(
                AcceptanceCheck.from_dict(item)
                for item in payload["requirement_checks"]
            ),
            overall_status=AcceptanceStatus(str(payload["overall_status"])),
            git_commit=str(payload["git_commit"]),
            git_dirty=bool(payload["git_dirty"]),
            final_test_read=bool(payload["final_test_read"]),
            software_integration_ready=bool(payload["software_integration_ready"]),
            ready_for_dev_d_diagnostic_experiment=bool(
                payload["ready_for_dev_d_diagnostic_experiment"]
            ),
            scientifically_eligible=bool(payload["scientifically_eligible"]),
            canonical_analysis=bool(payload["canonical_analysis"]),
            deployment_eligible=bool(payload["deployment_eligible"]),
            approved_real_calibration=bool(payload["approved_real_calibration"]),
            final_tone_set_frozen=bool(payload["final_tone_set_frozen"]),
        )

    @property
    def semantic_sha256(self) -> str:
        payload = self.to_dict()
        for key in ("git_commit", "git_dirty"):
            payload.pop(key)
        payload["software_integration_ready"] = None
        payload["ready_for_dev_d_diagnostic_experiment"] = None
        return canonical_sha256(payload)

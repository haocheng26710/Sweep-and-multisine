"""Sealed-by-default final-test gate used by the desktop application."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import uuid


class FinalTestState(str, Enum):
    SEALED = "sealed"
    APPROVED_ONCE = "approved_once"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class FinalTestGateRequest:
    plan_id: str
    entered_plan_id: str
    package_semantic_sha256: str
    entered_hash_fragment: str
    plan_frozen: bool
    package_frozen: bool
    package_self_check_passed: bool
    scope_matches_plan: bool
    training_development_complete: bool
    custodian: str
    approver: str
    approval_time_utc: str
    one_time_rule_confirmed: bool
    output_directory_empty: bool
    version_match: bool
    real_research_authority: bool
    unresolved_incidents: int
    real_multisine_backend_approved: bool
    approval_record_path: Path | None
    operator: str


@dataclass(frozen=True, slots=True)
class FinalTestDecision:
    allowed: bool
    state: FinalTestState
    failed_checks: tuple[str, ...]
    incident_path: Path | None


class FinalTestSafetyService:
    """Evaluate every authority before touching a sealed final-test path."""

    def __init__(self, audit_directory: str | Path) -> None:
        self.audit_directory = Path(audit_directory).resolve()
        self.state = FinalTestState.SEALED

    @staticmethod
    def failed_checks(request: FinalTestGateRequest) -> tuple[str, ...]:
        expected_fragment = request.package_semantic_sha256.removeprefix("sha256:")[-8:]
        checks = {
            "plan_frozen": request.plan_frozen,
            "package_frozen": request.package_frozen,
            "package_self_check_passed": request.package_self_check_passed,
            "scope_matches_plan": request.scope_matches_plan,
            "training_development_complete": request.training_development_complete,
            "custodian": bool(request.custodian.strip()),
            "approver": bool(request.approver.strip()),
            "approval_time_utc": bool(request.approval_time_utc.strip()),
            "approval_record": request.approval_record_path is not None and Path(request.approval_record_path).is_file(),
            "plan_id_confirmation": request.entered_plan_id == request.plan_id,
            "package_hash_confirmation": request.entered_hash_fragment.lower() == expected_fragment.lower(),
            "one_time_rule_confirmed": request.one_time_rule_confirmed,
            "output_directory_empty": request.output_directory_empty,
            "version_match": request.version_match,
            "real_research_authority": request.real_research_authority,
            "no_unresolved_incidents": request.unresolved_incidents == 0,
            "real_multisine_backend_approved": request.real_multisine_backend_approved,
            "operator": bool(request.operator.strip()),
        }
        return tuple(name for name, passed in checks.items() if not passed)

    def request_unseal(
        self,
        request: FinalTestGateRequest,
        *,
        sealed_input: str | Path,
    ) -> FinalTestDecision:
        if self.state is not FinalTestState.SEALED:
            return FinalTestDecision(False, self.state, ("one_time_evaluation_already_started",), None)
        failures = self.failed_checks(request)
        if failures:
            incident = self._write_incident(request, Path(sealed_input), failures)
            return FinalTestDecision(False, FinalTestState.SEALED, failures, incident)
        self.state = FinalTestState.APPROVED_ONCE
        return FinalTestDecision(True, self.state, (), None)

    def mark_running(self) -> None:
        if self.state is not FinalTestState.APPROVED_ONCE:
            raise RuntimeError("final-test can run only after one-time approval")
        self.state = FinalTestState.RUNNING

    def mark_completed(self) -> None:
        if self.state is not FinalTestState.RUNNING:
            raise RuntimeError("final-test can complete only from running")
        self.state = FinalTestState.COMPLETED

    def _write_incident(
        self,
        request: FinalTestGateRequest,
        sealed_input: Path,
        failures: tuple[str, ...],
    ) -> Path:
        self.audit_directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.audit_directory / f"final_test_access_incident_{stamp}_{uuid.uuid4().hex[:8]}.json"
        payload = {
            "schema_version": "1.0.0",
            "event": "blocked_final_test_access_attempt",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "operator": request.operator,
            "plan_id": request.plan_id,
            "package_semantic_sha256": request.package_semantic_sha256,
            "final_test_path": str(sealed_input.resolve()),
            "failed_checks": list(failures),
            "content_read": False,
            "metadata_read": False,
            "hash_computed": False,
            "request_snapshot": {
                key: (str(value) if isinstance(value, Path) else value)
                for key, value in asdict(request).items()
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

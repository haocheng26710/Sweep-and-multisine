from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import pytest

from acoustic_encoder.pre_experiment_acceptance import (
    AcceptanceCheck,
    AcceptanceResult,
    AcceptanceStatus,
)
from acoustic_encoder.pre_experiment_acceptance_outputs import (
    load_acceptance_bundle,
    write_acceptance_bundle,
)


def _result() -> AcceptanceResult:
    stage_evidence = (
        "t0_mathematical_consistency.json", "t1_robustness_scenarios.json",
        "t2_selection_classification.json", "t3_end_to_end.json",
    )
    stages = tuple(
        AcceptanceCheck(
            f"T{index}", AcceptanceStatus.PASS, True, "verified",
            (stage_evidence[index],), "loader_verified",
        )
        for index in range(4)
    )
    requirements = tuple(
        AcceptanceCheck(
            f"V2-{index}", AcceptanceStatus.PASS, True, "verified",
            ("acceptance_scope.json",), "loader_verified",
        )
        for index in range(1, 15)
    )

    return AcceptanceResult.build(
        acceptance_scope_id="scope-1",
        stage_checks=stages,
        requirement_checks=requirements,
        final_test_read=False,
        git_commit="a" * 40,
        git_dirty=False,
    )


def test_acceptance_bundle_writes_required_views_and_round_trips(tmp_path: Path) -> None:
    output = tmp_path / "acceptance"
    result = _result()
    manifest = write_acceptance_bundle(
        output,
        result=result,
        branch="feature/v2-dual-input",
        scope={"schema_version": "1.0.0", "acceptance_scope_id": "scope-1"},
        t0={"status": "pass", "maximum_error_db": 0.01},
        t1={"status": "pass", "scenarios": []},
        t2={"status": "pass", "outer_fold_count": 3},
        t3={"status": "pass", "predicted_direction_deg": 90.0},
        leakage_and_provenance={"status": "pass", "final_test_read": False},
        versions={"pipeline_version": "2.0.0-dev.21"},
        dependencies={"python": "3.11"},
        created_at_utc="2026-08-06T12:00:00+00:00",
    )

    required = {
        "acceptance_scope.json", "acceptance_matrix.csv",
        "t0_mathematical_consistency.json", "t0_mathematical_consistency.csv",
        "t1_robustness_scenarios.json", "t1_robustness_scenarios.csv",
        "t2_selection_classification.json", "t2_selection_classification.csv",
        "t3_end_to_end.json", "v2_requirement_audit.csv",
        "leakage_and_provenance_audit.json", "artifact_hash_audit.csv",
        "experiment_readiness.json", "pre_experiment_acceptance_report.md",
        "acceptance_manifest.json", "acceptance_manifest.sha256",
    }
    assert required == {item.name for item in output.iterdir()}
    loaded, loaded_manifest = load_acceptance_bundle(output)
    assert loaded.semantic_sha256 == result.semantic_sha256
    assert loaded.software_integration_ready is True
    assert manifest["manifest_content_sha256"] == loaded_manifest["manifest_content_sha256"]
    assert loaded_manifest["git_commit"] == "a" * 40
    assert loaded_manifest["git_dirty"] is False
    with (output / "v2_requirement_audit.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        requirement_rows = list(csv.DictReader(handle))
    assert len(requirement_rows) == 14
    assert all(row["evidence_sha256"].startswith("sha256:") for row in requirement_rows)


def test_missing_passing_evidence_is_rejected_instead_of_written_as_pass(tmp_path: Path) -> None:
    valid = _result()
    missing = replace(
        valid,
        stage_checks=(replace(valid.stage_checks[0], evidence_files=("missing.json",)), *valid.stage_checks[1:]),
    )
    with pytest.raises(ValueError, match="missing acceptance evidence"):
        write_acceptance_bundle(
            tmp_path / "missing",
            result=missing,
            branch="feature/v2-dual-input",
            scope={"schema_version": "1.0.0", "acceptance_scope_id": "scope-1"},
            t0={"status": "pass"}, t1={"status": "pass", "scenarios": []},
            t2={"status": "pass"}, t3={"status": "pass"},
            leakage_and_provenance={"status": "pass", "final_test_read": False},
            versions={}, dependencies={}, created_at_utc="2026-08-06T12:00:00+00:00",
        )


def test_writer_rejects_circular_hash_audit_as_requirement_evidence(tmp_path: Path) -> None:
    valid = _result()
    result = replace(
        valid,
        requirement_checks=(
            *valid.requirement_checks[:9],
            replace(valid.requirement_checks[9], evidence_files=("artifact_hash_audit.csv",)),
            *valid.requirement_checks[10:],
        ),
    )

    with pytest.raises(ValueError, match="acceptance evidence was not written"):
        write_acceptance_bundle(
            tmp_path / "self-evidence",
            result=result,
            branch="feature/v2-dual-input",
            scope={"schema_version": "1.0.0", "acceptance_scope_id": "scope-1"},
            t0={"status": "pass"}, t1={"status": "pass", "scenarios": []},
            t2={"status": "pass"}, t3={"status": "pass"},
            leakage_and_provenance={"status": "pass", "final_test_read": False},
            versions={}, dependencies={}, created_at_utc="2026-08-06T12:00:00+00:00",
        )

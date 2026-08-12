"""Immutable, hash-verified DEV-C16 acceptance bundle views."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from .pre_experiment_acceptance import AcceptanceResult, canonical_sha256


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_bytes(_json_bytes(payload))


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _windows_extended_path(path: Path) -> Path:
    value = str(path.resolve())
    if os.name == "nt" and not value.startswith("\\\\?\\"):
        return Path("\\\\?\\" + value)
    return Path(value)


def _encoded(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return value


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fallback_fields: tuple[str, ...]) -> None:
    materialized = [dict(row) for row in rows]
    fields = tuple(materialized[0]) if materialized else fallback_fields
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        for row in materialized:
            writer.writerow({name: _encoded(row.get(name)) for name in fields})


def _report(result: AcceptanceResult, t0: Mapping[str, Any], t1: Mapping[str, Any], t2: Mapping[str, Any], t3: Mapping[str, Any]) -> str:
    return (
        "# Pre-experiment acceptance report\n\n"
        f"- Overall: `{result.overall_status.value}`\n"
        f"- Software integration ready: `{str(result.software_integration_ready).lower()}`\n"
        f"- Ready for DEV-D diagnostic experiment: `{str(result.ready_for_dev_d_diagnostic_experiment).lower()}`\n"
        f"- Git commit: `{result.git_commit}`\n"
        f"- Git dirty: `{str(result.git_dirty).lower()}`\n"
        f"- Final test read: `{str(result.final_test_read).lower()}`\n\n"
        "## T0--T3\n\n"
        f"- T0: `{t0.get('status', 'unavailable')}`\n"
        f"- T1: `{t1.get('status', 'unavailable')}`\n"
        f"- T2: `{t2.get('status', 'unavailable')}`\n"
        f"- T3: `{t3.get('status', 'unavailable')}`\n\n"
        "This report authorizes only controlled DEV-D diagnostic preparation. "
        "It does not authorize scientific, canonical, calibration, tone-set, final-test, or deployment claims.\n"
    )


def _check_row_with_evidence_digest(
    output: Path, check: Any
) -> dict[str, Any]:
    row = check.to_dict()
    evidence_hashes: dict[str, str] = {}
    for relative in check.evidence_files:
        evidence_path = output / relative
        if not evidence_path.is_file():
            raise ValueError(
                f"acceptance evidence was not written for {check.check_id}: {relative}"
            )
        evidence_hashes[relative] = _file_sha256(evidence_path)
    row["evidence_sha256"] = canonical_sha256(evidence_hashes)
    return row


def write_acceptance_bundle(
    output_directory: str | Path,
    *,
    result: AcceptanceResult,
    branch: str,
    scope: Mapping[str, Any],
    t0: Mapping[str, Any],
    t1: Mapping[str, Any],
    t2: Mapping[str, Any],
    t3: Mapping[str, Any],
    leakage_and_provenance: Mapping[str, Any],
    versions: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    created_at_utc: str,
    input_artifacts: Mapping[str, Mapping[str, str]] | None = None,
    evidence_artifacts: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"acceptance output already exists: {output}")
    planned_evidence = {
        "acceptance_scope.json", "acceptance_matrix.csv",
        "t0_mathematical_consistency.json", "t0_mathematical_consistency.csv",
        "t1_robustness_scenarios.json", "t1_robustness_scenarios.csv",
        "t2_selection_classification.json", "t2_selection_classification.csv",
        "t3_end_to_end.json", "v2_requirement_audit.csv",
        "leakage_and_provenance_audit.json", "artifact_hash_audit.csv",
        "experiment_readiness.json",
        "pre_experiment_acceptance_report.md",
    }
    for check in (*result.stage_checks, *result.requirement_checks):
        if check.status.value == "pass":
            missing = sorted(set(check.evidence_files) - planned_evidence)
            if missing:
                raise ValueError(
                    f"missing acceptance evidence for {check.check_id}: {missing}"
                )
    output.mkdir(parents=True, exist_ok=False)

    readiness = {**result.to_dict(), "acceptance_result_semantic_sha256": result.semantic_sha256}
    json_payloads = {
        "acceptance_scope.json": dict(scope),
        "t0_mathematical_consistency.json": dict(t0),
        "t1_robustness_scenarios.json": dict(t1),
        "t2_selection_classification.json": dict(t2),
        "t3_end_to_end.json": dict(t3),
        "leakage_and_provenance_audit.json": dict(leakage_and_provenance),
        "experiment_readiness.json": readiness,
    }
    for name, payload in json_payloads.items():
        _write_json(output / name, payload)

    _write_csv(
        output / "t0_mathematical_consistency.csv",
        t0.get("tones", ({key: value for key, value in t0.items() if key != "tones"},)),
        ("status",),
    )
    _write_csv(
        output / "t1_robustness_scenarios.csv",
        t1.get("scenarios", ()),
        ("scenario_id", "expected_status", "actual_status", "expectation_matched"),
    )
    _write_csv(
        output / "t2_selection_classification.csv",
        t2.get("folds", ({key: value for key, value in t2.items() if key != "folds"},)),
        ("outer_fold_id", "status"),
    )
    (output / "pre_experiment_acceptance_report.md").write_text(
        _report(result, t0, t1, t2, t3), encoding="utf-8"
    )

    stage_rows = [
        _check_row_with_evidence_digest(output, item) for item in result.stage_checks
    ]
    requirement_rows = [
        _check_row_with_evidence_digest(output, item)
        for item in result.requirement_checks
    ]
    matrix_rows = [
        {"category": "stage", **item} for item in stage_rows
    ] + [
        {"category": "requirement", **item} for item in requirement_rows
    ]
    _write_csv(
        output / "acceptance_matrix.csv", matrix_rows,
        ("category", "check_id", "status"),
    )
    _write_csv(
        output / "v2_requirement_audit.csv", requirement_rows,
        ("check_id", "status"),
    )

    audit_targets = sorted(
        path for path in output.iterdir() if path.name != "artifact_hash_audit.csv"
    )
    audit_rows = [
        {"artifact_type": "bundle", "artifact": path.name, "path": path.name,
         "sha256": _file_sha256(path), "size_bytes": path.stat().st_size}
        for path in audit_targets
    ]
    for artifact_type, records in (
        ("input", input_artifacts or {}), ("evidence", evidence_artifacts or {}),
    ):
        for artifact_id, record in sorted(records.items()):
            target = (output / record["path"]).resolve()
            target_io = _windows_extended_path(target)
            if not target_io.is_file() or _file_sha256(target_io) != record["sha256"]:
                raise ValueError(f"{artifact_type} artifact hash mismatch: {artifact_id}")
            audit_rows.append({
                "artifact_type": artifact_type, "artifact": artifact_id,
                "path": record["path"], "sha256": record["sha256"],
                "size_bytes": target_io.stat().st_size,
            })
    _write_csv(
        output / "artifact_hash_audit.csv", audit_rows,
        ("artifact_type", "artifact", "path", "sha256", "size_bytes"),
    )

    artifacts = {
        path.name: _file_sha256(path)
        for path in sorted(output.iterdir(), key=lambda item: item.name)
    }
    manifest = {
        "schema_version": "1.0.0",
        "acceptance_scope_id": result.acceptance_scope_id,
        "acceptance_result_semantic_sha256": result.semantic_sha256,
        "git_commit": result.git_commit,
        "git_dirty": result.git_dirty,
        "branch": branch,
        "versions": dict(versions),
        "dependencies": dict(dependencies),
        "created_at_utc": created_at_utc,
        "t0_status": t0.get("status", "unavailable"),
        "t1_status": t1.get("status", "unavailable"),
        "t2_status": t2.get("status", "unavailable"),
        "t3_status": t3.get("status", "unavailable"),
        "v2_requirement_pass_count": sum(
            item.status.value == "pass" for item in result.requirement_checks
        ),
        "final_test_read": result.final_test_read,
        "software_integration_ready": result.software_integration_ready,
        "ready_for_dev_d_diagnostic_experiment": result.ready_for_dev_d_diagnostic_experiment,
        "scientifically_eligible": False,
        "canonical_analysis": False,
        "deployment_eligible": False,
        "input_artifacts": dict(sorted((input_artifacts or {}).items())),
        "evidence_artifacts": dict(sorted((evidence_artifacts or {}).items())),
        "artifacts": artifacts,
    }
    manifest["manifest_content_sha256"] = canonical_sha256(manifest)
    manifest_path = output / "acceptance_manifest.json"
    _write_json(manifest_path, manifest)
    (output / "acceptance_manifest.sha256").write_text(
        _file_sha256(manifest_path) + "  acceptance_manifest.json\n", encoding="ascii"
    )
    return manifest


def load_acceptance_bundle(output_directory: str | Path) -> tuple[AcceptanceResult, dict[str, Any]]:
    output = Path(output_directory)
    manifest_path = output / "acceptance_manifest.json"
    expected_file = (output / "acceptance_manifest.sha256").read_text(encoding="ascii").split()[0]
    if _file_sha256(manifest_path) != expected_file:
        raise ValueError("acceptance manifest file hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    semantic = dict(manifest)
    expected_content = semantic.pop("manifest_content_sha256")
    if canonical_sha256(semantic) != expected_content:
        raise ValueError("acceptance manifest content hash mismatch")
    for relative, digest in manifest["artifacts"].items():
        target = output / relative
        if not target.is_file() or _file_sha256(target) != digest:
            raise ValueError(f"acceptance artifact hash mismatch: {relative}")
    for category in ("input_artifacts", "evidence_artifacts"):
        for artifact_id, record in manifest.get(category, {}).items():
            target = (output / record["path"]).resolve()
            if not target.is_file() or _file_sha256(target) != record["sha256"]:
                raise ValueError(f"acceptance {category} hash mismatch: {artifact_id}")
    readiness = json.loads((output / "experiment_readiness.json").read_text(encoding="utf-8"))
    expected_result = readiness.pop("acceptance_result_semantic_sha256")
    result = AcceptanceResult.from_dict(readiness)
    if result.semantic_sha256 != expected_result or result.semantic_sha256 != manifest["acceptance_result_semantic_sha256"]:
        raise ValueError("acceptance result semantic hash mismatch")
    if manifest["software_integration_ready"] != result.software_integration_ready:
        raise ValueError("acceptance manifest readiness mismatch")
    return result, manifest

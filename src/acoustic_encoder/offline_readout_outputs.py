"""Immutable JSON/CSV bundles for P9-D packages and single readouts."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .direction_models import FrozenDirectionModel
from .offline_readout import FrozenReadoutPackage, OfflineReadoutResult, canonical_sha256


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_bytes(_json_bytes(payload))


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, row: Mapping[str, Any]) -> None:
    encoded = {
        key: (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            if isinstance(value, (list, tuple, dict)) else value
        )
        for key, value in row.items()
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(encoded))
        writer.writeheader()
        writer.writerow(encoded)


def _write_manifest(output: Path, name: str, sidecar_name: str, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["manifest_content_sha256"] = canonical_sha256(manifest)
    path = output / name
    _write_json(path, manifest)
    (output / sidecar_name).write_text(_file_sha256(path) + f"  {name}\n", encoding="ascii")
    return manifest


def _verify_manifest(output: Path, name: str, sidecar_name: str) -> dict[str, Any]:
    path = output / name
    expected_file = (output / sidecar_name).read_text(encoding="ascii").split()[0]
    if _file_sha256(path) != expected_file:
        raise ValueError(f"{name} file hash mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    semantic = dict(manifest)
    expected_content = semantic.pop("manifest_content_sha256")
    if canonical_sha256(semantic) != expected_content:
        raise ValueError(f"{name} content hash mismatch")
    for relative, digest in manifest["artifacts"].items():
        target = output / relative
        if not target.is_file() or _file_sha256(target) != digest:
            raise ValueError(f"artifact hash mismatch: {relative}")
    return manifest


def write_readout_package(
    output_directory: str | Path,
    package: FrozenReadoutPackage,
    model: FrozenDirectionModel,
    *,
    package_input_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"readout package output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    paths = {
        "readout_package.json": package.to_dict(),
        "package_input_manifest.json": dict(package_input_manifest),
        "frozen_direction_model.json": model.to_dict(),
        "preprocessing_snapshot.json": dict(package.p3_preprocessing_snapshot),
        "qc_policy_snapshot.json": dict(package.qc_policy_snapshot),
    }
    for name, payload in paths.items():
        _write_json(output / name, payload)
    artifacts = {name: _file_sha256(output / name) for name in sorted(paths)}
    manifest = {
        "schema_version": "1.0.0", "package_id": package.package_id,
        "package_semantic_sha256": package.semantic_sha256,
        "model_semantic_sha256": model.semantic_sha256,
        "artifact_count": len(artifacts), "artifacts": artifacts,
        "lifecycle": package.lifecycle, "final_test_read": package.final_test_read,
        "scientifically_eligible": package.scientifically_eligible,
        "deployment_eligible": package.deployment_eligible,
    }
    return _write_manifest(output, "package_manifest.json", "package_manifest.sha256", manifest)


def load_readout_package_bundle(
    output_directory: str | Path,
) -> tuple[FrozenReadoutPackage, FrozenDirectionModel, dict[str, Any]]:
    output = Path(output_directory)
    manifest = _verify_manifest(output, "package_manifest.json", "package_manifest.sha256")
    package = FrozenReadoutPackage.from_dict(json.loads((output / "readout_package.json").read_text(encoding="utf-8")))
    model = FrozenDirectionModel.from_dict(json.loads((output / "frozen_direction_model.json").read_text(encoding="utf-8")))
    if package.semantic_sha256 != manifest["package_semantic_sha256"]:
        raise ValueError("package semantic hash mismatch")
    if model.semantic_sha256 != manifest["model_semantic_sha256"] or model.semantic_sha256 != package.model_semantic_sha256:
        raise ValueError("model semantic hash mismatch")
    if _file_sha256(output / "frozen_direction_model.json") != package.model_file_sha256:
        raise ValueError("model exact-file hash mismatch")
    if canonical_sha256(json.loads((output / "preprocessing_snapshot.json").read_text(encoding="utf-8"))) != package.p3_preprocessing_snapshot_sha256:
        raise ValueError("preprocessing snapshot hash mismatch")
    if canonical_sha256(json.loads((output / "qc_policy_snapshot.json").read_text(encoding="utf-8"))) != package.qc_policy_snapshot_sha256:
        raise ValueError("QC policy snapshot hash mismatch")
    return package, model, manifest


def write_offline_readout_outputs(
    output_directory: str | Path,
    result: OfflineReadoutResult,
) -> dict[str, Any]:
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"offline readout output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    json_payloads = {
        "input_audit.json": result.input_reference.to_dict(),
        "qc_audit.json": result.qc_audit.to_dict(),
        "feature_audit.json": result.feature_audit.to_dict(),
        "calibration_audit.json": result.calibration_audit.to_dict(),
        "prediction.json": result.prediction.to_dict(),
        "readout_result.json": {**result.to_dict(), "result_semantic_sha256": result.semantic_sha256},
    }
    for name, payload in json_payloads.items():
        _write_json(output / name, payload)
    _write_csv(output / "qc_audit.csv", result.qc_audit.to_dict())
    _write_csv(output / "feature_audit.csv", result.feature_audit.to_dict())
    artifact_names = sorted((*json_payloads, "qc_audit.csv", "feature_audit.csv"))
    artifacts = {name: _file_sha256(output / name) for name in artifact_names}
    manifest = {
        "schema_version": "1.0.0", "package_id": result.package_id,
        "sample_id": result.sample_id, "processing_status": result.processing_status,
        "result_semantic_sha256": result.semantic_sha256,
        "prediction_available": result.prediction.available,
        "artifact_count": len(artifacts), "artifacts": artifacts,
        "scientifically_eligible": result.scientifically_eligible,
        "deployment_eligible": result.deployment_eligible,
        "final_test_read": result.final_test_read,
    }
    return _write_manifest(output, "readout_manifest.json", "readout_manifest.sha256", manifest)


def load_offline_readout_bundle(
    output_directory: str | Path,
) -> tuple[OfflineReadoutResult, dict[str, Any]]:
    output = Path(output_directory)
    manifest = _verify_manifest(output, "readout_manifest.json", "readout_manifest.sha256")
    payload = json.loads((output / "readout_result.json").read_text(encoding="utf-8"))
    expected = payload.pop("result_semantic_sha256")
    result = OfflineReadoutResult.from_dict(payload)
    if result.semantic_sha256 != expected or result.semantic_sha256 != manifest["result_semantic_sha256"]:
        raise ValueError("readout result semantic hash mismatch")
    return result, manifest


def write_offline_readout_failure_outputs(
    output_directory: str | Path,
    *,
    reason: str,
    input_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist the evidence available before a typed readout result can exist."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"offline readout output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    payloads = {
        "input_audit.json": {"available_evidence": dict(input_evidence), "status": "blocked", "reason": reason},
        "qc_audit.json": {"status": "blocked", "available": False, "reasons": [reason]},
        "feature_audit.json": {"available": False, "reason_codes": ["blocked_before_feature_construction"]},
        "calibration_audit.json": {"requested": None, "applied": False, "reason_codes": ["blocked_before_calibration"]},
        "prediction.json": {"available": False, "unavailable_reason": reason, "confidence_status": "unavailable"},
        "readout_result.json": {
            "schema_version": "1.0.0", "processing_status": "blocked",
            "failure_reasons": [reason], "scientifically_eligible": False,
            "deployment_eligible": False, "canonical_analysis": False, "final_test_read": False,
        },
    }
    for name, payload in payloads.items():
        _write_json(output / name, payload)
    _write_csv(output / "qc_audit.csv", payloads["qc_audit.json"])
    _write_csv(output / "feature_audit.csv", payloads["feature_audit.json"])
    artifact_names = sorted((*payloads, "qc_audit.csv", "feature_audit.csv"))
    artifacts = {name: _file_sha256(output / name) for name in artifact_names}
    manifest = {
        "schema_version": "1.0.0", "processing_status": "blocked",
        "prediction_available": False, "failure_reasons": [reason],
        "artifact_count": len(artifacts), "artifacts": artifacts,
        "scientifically_eligible": False, "deployment_eligible": False,
        "final_test_read": False,
    }
    return _write_manifest(output, "readout_manifest.json", "readout_manifest.sha256", manifest)

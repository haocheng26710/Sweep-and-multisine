"""Immutable CSV/JSON/hash output bundle for P6-A sweep calibration."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import csv
import io
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .hr_analysis import (
    HR_CALIBRATION_SCHEMA_VERSION,
    HRCalibrationResult,
    HRCalibrationScope,
)
from .schemas import artifact_sha256
from .version import SCHEMA_VERSION_QUARTET


HR_CALIBRATION_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return value


def _csv_text(rows: Sequence[Mapping[str, Any]], *, empty_fields: Sequence[str]) -> str:
    materialized = [dict(row) for row in rows]
    fieldnames = list(materialized[0]) if materialized else list(empty_fields)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in materialized:
        writer.writerow({name: _cell(row.get(name)) for name in fieldnames})
    return stream.getvalue()


def _row(item: Any) -> dict[str, Any]:
    return asdict(item)


def _views(
    result: HRCalibrationResult,
    scope: HRCalibrationScope,
    input_artifacts: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[list[dict[str, Any]], tuple[str, ...]]]:
    return {
        "peak_candidates.csv": ([
            _row(item) for item in sorted(result.candidates, key=lambda x: (x.sample_id, x.resonator_id, x.frequency_hz))
        ], ("sample_id", "resonator_id")),
        "detected_peaks.csv": ([
            _row(item) for item in sorted(result.detected_peaks, key=lambda x: (x.sample_id, x.resonator_id))
        ], ("sample_id", "resonator_id", "status")),
        "peak_bandwidths.csv": ([
            _row(item) for item in sorted(result.bandwidths, key=lambda x: (x.sample_id, x.resonator_id))
        ], ("sample_id", "resonator_id", "status")),
        "peak_drift.csv": ([
            _row(item) for item in sorted(result.peak_drifts, key=lambda x: (x.calibration_group_id, x.resonator_id, x.repeat_type))
        ], ("calibration_group_id", "resonator_id", "repeat_type", "status")),
        "peak_overlap.csv": ([
            _row(item) for item in sorted(result.peak_overlaps, key=lambda x: (x.sample_id, x.left_resonator_id, x.right_resonator_id))
        ], ("sample_id", "left_resonator_id", "right_resonator_id", "status")),
        "integrated_energy.csv": ([
            _row(item) for item in sorted(result.integrated_energies, key=lambda x: (x.sample_id, x.resonator_id))
        ], ("sample_id", "resonator_id", "status")),
        "hr_energy_fractions.csv": ([
            _row(item) for item in sorted(result.energy_fractions, key=lambda x: (x.energy_fraction_group_id, x.sample_id, x.resonator_id))
        ], ("energy_fraction_group_id", "sample_id", "resonator_id", "status")),
        "calibration_scope_audit.csv": ([
            item.to_dict() for item in scope.members
        ], ("sample_id", "artifact_id")),
        "calibration_input_audit.csv": ([
            {name: item[name] for name in ("sample_id", "artifact_role", "path", "sha256")}
            for item in sorted(input_artifacts, key=lambda x: (str(x["sample_id"]), str(x["artifact_role"]), str(x["path"])))
        ], ("sample_id", "artifact_role", "path", "sha256")),
    }


def _verified_inputs(input_artifacts: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    verified: list[dict[str, str]] = []
    ordered_fields = ("sample_id", "artifact_role", "path", "sha256")
    for item in input_artifacts:
        if set(item) != set(ordered_fields):
            raise ValueError("HR calibration input audit fields must be explicit")
        path = Path(str(item["path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = artifact_sha256(path)
        if actual != item["sha256"]:
            raise ValueError(f"HR calibration input hash mismatch: {path}")
        verified.append({name: str(item[name]) for name in ordered_fields})
    return tuple(sorted(verified, key=lambda row: (row["sample_id"], row["artifact_role"], row["path"])))


def _plot_candidates(result: HRCalibrationResult, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(8, 4), constrained_layout=True)
    if result.candidates:
        axis.scatter(
            [item.frequency_hz for item in result.candidates],
            [item.magnitude_db for item in result.candidates],
            c=["#d62728" if item.selected else "#4c78a8" for item in result.candidates],
            s=[35 if item.selected else 16 for item in result.candidates],
        )
    axis.set_xlabel("Frequency (Hz)")
    axis.set_ylabel("Candidate magnitude (dB)")
    axis.set_title("P6-A peak candidate audit")
    axis.grid(True, alpha=0.25)
    figure.savefig(path, dpi=120, metadata={"Software": "acoustic-encoder-p6a"})
    plt.close(figure)


def write_hr_calibration_outputs(
    result: HRCalibrationResult,
    scope: HRCalibrationScope,
    config: Mapping[str, Any],
    output_directory: str | Path,
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    git_commit: str,
    random_state: int,
    created_at_utc: str | None = None,
) -> dict[str, Path]:
    """Write one immutable P6-A bundle and refuse an existing directory."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"HR calibration output directory already exists: {output}")
    if result.scope_sha256 != scope.sha256 or result.hr_calibration_scope_id != scope.hr_calibration_scope_id:
        raise ValueError("HR calibration result/scope mismatch")
    from .hr_analysis import _sha256
    if result.config_sha256 != _sha256(dict(config)):
        raise ValueError("HR calibration result/config mismatch")
    verified_inputs = _verified_inputs(input_artifacts)
    output.mkdir(parents=True, exist_ok=False)
    paths: dict[str, Path] = {}
    for name, (rows, empty_fields) in _views(result, scope, verified_inputs).items():
        path = output / name
        path.write_text(_csv_text(rows, empty_fields=empty_fields), encoding="utf-8", newline="")
        paths[name] = path
    calibration_path = output / "hr_calibration.json"
    calibration_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    paths[calibration_path.name] = calibration_path
    calibration_digest = output / "hr_calibration.sha256"
    calibration_digest.write_text(f"{artifact_sha256(calibration_path)}  {calibration_path.name}\n", encoding="ascii")
    paths[calibration_digest.name] = calibration_digest
    plot_path = output / "peak_detection_diagnostic.png"
    _plot_candidates(result, plot_path)
    paths[plot_path.name] = plot_path
    artifacts = [
        {"path": path.name, "sha256": artifact_sha256(path), "size_bytes": path.stat().st_size}
        for path in sorted(paths.values(), key=lambda item: item.name)
    ]
    manifest = {
        "schema_version": HR_CALIBRATION_MANIFEST_SCHEMA_VERSION,
        "hr_calibration_schema_version": HR_CALIBRATION_SCHEMA_VERSION,
        "created_at_utc": created_at_utc or datetime.now(UTC).isoformat(),
        "versions": dict(SCHEMA_VERSION_QUARTET),
        "git_commit": git_commit,
        "random_state": random_state,
        "processing_status": "completed",
        "success": True,
        "calibration_id": result.calibration_id,
        "calibration_status": result.calibration_status,
        "calibration_usability": result.calibration_usability,
        "scope": scope.to_dict(),
        "scope_sha256": scope.sha256,
        "config": dict(config),
        "config_sha256": result.config_sha256,
        "p2b_reference": scope.p2b_reference.to_dict(),
        "provenance": {
            "data_origin": result.data_origin,
            "dataset_role": result.dataset_role,
            "run_purpose": result.run_purpose,
            "scientifically_eligible": result.scientifically_eligible,
            "frozen_for_research": result.frozen_for_research,
        },
        "inputs": list(verified_inputs),
        "artifacts": artifacts,
    }
    manifest_path = output / "hr_calibration_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    paths[manifest_path.name] = manifest_path
    manifest_digest = output / "hr_calibration_manifest.sha256"
    manifest_digest.write_text(f"{artifact_sha256(manifest_path)}  {manifest_path.name}\n", encoding="ascii")
    paths[manifest_digest.name] = manifest_digest
    return paths


def _verify_digest_file(path: Path, target: Path) -> None:
    tokens = path.read_text(encoding="ascii").split()
    if len(tokens) != 2 or tokens[1] != target.name or tokens[0] != artifact_sha256(target):
        raise ValueError(f"HR calibration digest mismatch: {target.name}")


def load_hr_calibration_bundle(output_directory: str | Path) -> HRCalibrationResult:
    """Verify all hashes and CSV/JSON views, then return the typed calibration."""
    output = Path(output_directory)
    manifest_path = output / "hr_calibration_manifest.json"
    _verify_digest_file(output / "hr_calibration_manifest.sha256", manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != HR_CALIBRATION_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported HR calibration manifest schema")
    for artifact in manifest["artifacts"]:
        path = output / artifact["path"]
        if artifact_sha256(path) != artifact["sha256"]:
            raise ValueError(f"HR calibration artifact hash mismatch: {path.name}")
    calibration_path = output / "hr_calibration.json"
    _verify_digest_file(output / "hr_calibration.sha256", calibration_path)
    result = HRCalibrationResult.from_dict(json.loads(calibration_path.read_text(encoding="utf-8")))
    scope = HRCalibrationScope.from_dict(manifest["scope"])
    if result.scope_sha256 != scope.sha256 or result.calibration_id != manifest["calibration_id"]:
        raise ValueError("HR calibration manifest identity mismatch")
    for name, (rows, fields) in _views(result, scope, manifest["inputs"]).items():
        expected = _csv_text(rows, empty_fields=fields)
        if (output / name).read_text(encoding="utf-8") != expected:
            raise ValueError(f"HR calibration CSV/JSON consistency mismatch: {name}")
    return result


def load_hr_calibration_authority(output_directory: str | Path):
    """Return P6-A result plus its verified scope/config/exact-file hashes for P6-B."""
    output = Path(output_directory)
    result = load_hr_calibration_bundle(output)
    manifest_path = output / "hr_calibration_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scope = HRCalibrationScope.from_dict(manifest["scope"])
    provenance = manifest.get("provenance", {})
    expected = {
        "calibration_status": result.calibration_status.value,
        "calibration_usability": result.calibration_usability,
        "calibration_id": result.calibration_id,
    }
    mismatched = [name for name, value in expected.items() if manifest.get(name) != value]
    if provenance.get("data_origin") != result.data_origin or provenance.get("run_purpose") != result.run_purpose:
        mismatched.append("provenance")
    if mismatched:
        raise ValueError("HR calibration authority manifest mismatch: " + ", ".join(mismatched))
    from .hr_readout import CalibrationAuthority
    return CalibrationAuthority(
        result=result,
        scope=scope,
        config=manifest["config"],
        calibration_json_sha256=artifact_sha256(output / "hr_calibration.json"),
        calibration_manifest_sha256=artifact_sha256(manifest_path),
    )

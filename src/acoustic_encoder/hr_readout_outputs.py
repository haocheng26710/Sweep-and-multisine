"""Immutable CSV/JSON/FeatureSet output bundle for P6-B."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import csv
import io
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .hr_readout import (
    HRReadoutAnalysis,
    HRReadoutResult,
    HRReadoutScope,
)
from .schemas import artifact_sha256, load_feature_set, save_feature_set
from .version import SCHEMA_VERSION_QUARTET


HR_READOUT_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return value


def _csv_text(rows: Sequence[Mapping[str, Any]], empty_fields: Sequence[str]) -> str:
    fields = list(rows[0]) if rows else list(empty_fields)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _cell(row.get(key)) for key in fields})
    return output.getvalue()


def _views(result: HRReadoutResult) -> dict[str, tuple[list[dict[str, Any]], tuple[str, ...]]]:
    mappings = [asdict(row) for sample in result.sample_readouts for row in sample.mappings]
    coverages = [asdict(row) for sample in result.sample_readouts for row in sample.coverages]
    energies = [asdict(row) for sample in result.sample_readouts for row in sample.band_energies]
    fractions = [asdict(row) for sample in result.sample_readouts for row in sample.energy_fractions]
    qc = [
        {
            "sample_id": sample.sample_id,
            "aggregate_status": sample.aggregate_status,
            "reasons": sample.reasons,
            "p2b_status": result.p2b_aggregate_status,
            "p2b_canonical_ready": result.p2b_canonical_ready,
            "calibration_status": result.calibration_status,
            "phase_policy": result.phase_policy,
            "scientifically_eligible": result.scientifically_eligible,
            "deployment_allowed": result.deployment_allowed,
        }
        for sample in result.sample_readouts
    ]
    uncertainty = [
        {
            "sample_id": sample.sample_id,
            "resonator_id": energy.resonator_id,
            "uncertainty_status": result.uncertainty_status,
            "uncertainty_value": None,
            "reason": "authoritative_per_tone_uncertainty_unavailable",
        }
        for sample in result.sample_readouts for energy in sample.band_energies
    ]
    calibration = [{
        "calibration_id": result.calibration_id,
        "calibration_json_sha256": result.calibration_json_sha256,
        "calibration_manifest_sha256": result.calibration_manifest_sha256,
        "calibration_status": result.calibration_status,
        "frozen_for_research": result.frozen_for_research,
        "absolute_energy_comparable": result.absolute_energy_comparable,
        "absolute_comparability_reason": result.absolute_comparability_reason,
    }]
    return {
        "calibration_reference_audit.csv": (calibration, tuple(calibration[0])),
        "tone_mapping.csv": (mappings, ("sample_id", "resonator_id")),
        "tone_coverage.csv": (coverages, ("sample_id", "resonator_id")),
        "hr_band_energy.csv": (energies, ("sample_id", "resonator_id")),
        "hr_energy_fractions.csv": (fractions, ("sample_id", "resonator_id")),
        "hr_readout_qc.csv": (qc, ("sample_id", "aggregate_status")),
        "uncertainty_audit.csv": (uncertainty, ("sample_id", "resonator_id")),
    }


def _plot_readout(result: HRReadoutResult, path: Path) -> None:
    rows = [row for sample in result.sample_readouts for row in sample.band_energies]
    labels = [f"{row.sample_id}:{row.resonator_id}" for row in rows]
    values = [0.0 if row.energy_value is None else row.energy_value for row in rows]
    figure, axis = plt.subplots(figsize=(max(6.0, len(rows) * 0.55), 3.5))
    axis.bar(range(len(rows)), values)
    axis.set_xticks(range(len(rows)), labels, rotation=45, ha="right")
    axis.set_ylabel("Relative HR readout")
    axis.set_title("P6-B calibrated multisine HR readout")
    axis.grid(True, axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=120, metadata={"Software": "acoustic-encoder-p6b"})
    plt.close(figure)


def _verified_inputs(input_artifacts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in input_artifacts:
        path = Path(str(item["path"]))
        expected = str(item["sha256"])
        if not path.is_file() or artifact_sha256(path) != expected:
            raise ValueError(f"HR readout input hash mismatch: {path}")
        rows.append({**dict(item), "path": path.resolve().as_posix(), "sha256": expected})
    return sorted(rows, key=lambda row: (str(row.get("sample_id", "")), str(row.get("artifact_role", "")), row["path"]))


def write_hr_readout_outputs(
    analysis: HRReadoutAnalysis,
    scope: HRReadoutScope,
    config: Mapping[str, Any],
    output_directory: str | Path,
    *,
    input_artifacts: Sequence[Mapping[str, Any]],
    git_commit: str,
    random_state: int,
    created_at_utc: str | None = None,
) -> dict[str, Path]:
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"HR readout output directory already exists: {output}")
    if analysis.result.scope_sha256 != scope.sha256:
        raise ValueError("HR readout result/scope mismatch")
    verified_inputs = _verified_inputs(input_artifacts)
    output.mkdir(parents=True, exist_ok=False)
    paths: dict[str, Path] = {}
    for name, (rows, fields) in _views(analysis.result).items():
        path = output / name
        path.write_text(_csv_text(rows, fields), encoding="utf-8", newline="")
        paths[name] = path

    feature_rows: list[dict[str, Any]] = []
    feature_entries: list[dict[str, Any]] = []
    collections = (
        ("hr_band_energy", analysis.hr_band_energy_features),
        ("hr_energy_fraction", analysis.hr_energy_fraction_features),
    )
    for kind, features in collections:
        for feature in features:
            base = output / "processed" / "features" / kind / feature.sample_id
            npz_path, json_path = save_feature_set(feature, base)
            for artifact_role, path in (("feature_npz", npz_path), ("feature_json", json_path)):
                paths[path.relative_to(output).as_posix()] = path
                feature_entries.append({
                    "sample_id": feature.sample_id,
                    "feature_kind": kind,
                    "artifact_role": artifact_role,
                    "path": path.relative_to(output).as_posix(),
                    "sha256": artifact_sha256(path),
                })
            feature_rows.append({
                "sample_id": feature.sample_id,
                "feature_kind": kind,
                "feature_count": len(feature.feature_names),
                "valid_count": int(feature.valid_mask.sum()),
                "units": tuple(sorted(set(feature.units))),
                "calibration_id": feature.calibration_id,
                "scope_id": feature.fit_scope_id,
                "source_feature_content_sha256": feature.derivation.source_feature_content_sha256 if feature.derivation else None,
                "npz_path": npz_path.relative_to(output).as_posix(),
                "json_path": json_path.relative_to(output).as_posix(),
            })
    feature_index = output / "feature_index.csv"
    feature_index.write_text(
        _csv_text(feature_rows, ("sample_id", "feature_kind")), encoding="utf-8", newline=""
    )
    paths[feature_index.name] = feature_index
    result_path = output / "hr_readout_result.json"
    result_path.write_text(
        json.dumps(analysis.result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths[result_path.name] = result_path
    plot_path = output / "hr_readout_diagnostic.png"
    _plot_readout(analysis.result, plot_path)
    paths[plot_path.name] = plot_path
    artifacts = [
        {
            "path": path.relative_to(output).as_posix(),
            "sha256": artifact_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(set(paths.values()), key=lambda item: item.relative_to(output).as_posix())
    ]
    manifest = {
        "schema_version": HR_READOUT_MANIFEST_SCHEMA_VERSION,
        "created_at_utc": created_at_utc or datetime.now(UTC).isoformat(),
        "versions": dict(SCHEMA_VERSION_QUARTET),
        "git_commit": git_commit,
        "random_state": random_state,
        "processing_status": "completed",
        "success": True,
        "readout_id": analysis.result.readout_id,
        "scope": scope.to_dict(),
        "scope_sha256": scope.sha256,
        "config": dict(config),
        "config_sha256": analysis.result.config_sha256,
        "calibration_id": analysis.result.calibration_id,
        "p2b_reference": scope.p2b_reference.to_dict(),
        "provenance": {
            "data_origin": analysis.result.data_origin,
            "dataset_role": analysis.result.dataset_role,
            "run_purpose": analysis.result.run_purpose,
            "scientifically_eligible": analysis.result.scientifically_eligible,
            "deployment_allowed": analysis.result.deployment_allowed,
        },
        "inputs": verified_inputs,
        "feature_sets": feature_entries,
        "artifacts": artifacts,
    }
    manifest_path = output / "hr_readout_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths[manifest_path.name] = manifest_path
    digest_path = output / "hr_readout_manifest.sha256"
    digest_path.write_text(
        f"{artifact_sha256(manifest_path)}  {manifest_path.name}\n", encoding="ascii"
    )
    paths[digest_path.name] = digest_path
    return paths


def load_hr_readout_bundle(output_directory: str | Path) -> HRReadoutAnalysis:
    output = Path(output_directory)
    manifest_path = output / "hr_readout_manifest.json"
    tokens = (output / "hr_readout_manifest.sha256").read_text(encoding="ascii").split()
    if len(tokens) != 2 or tokens[1] != manifest_path.name or tokens[0] != artifact_sha256(manifest_path):
        raise ValueError("HR readout manifest digest mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != HR_READOUT_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported HR readout manifest schema")
    for artifact in manifest["artifacts"]:
        path = output / artifact["path"]
        if not path.is_file() or artifact_sha256(path) != artifact["sha256"]:
            raise ValueError(f"HR readout artifact hash mismatch: {path}")
    result = HRReadoutResult.from_dict(
        json.loads((output / "hr_readout_result.json").read_text(encoding="utf-8"))
    )
    if result.readout_id != manifest["readout_id"]:
        raise ValueError("HR readout result identity mismatch")
    energy = []
    fractions = []
    for entry in manifest["feature_sets"]:
        if entry["artifact_role"] != "feature_json":
            continue
        feature = load_feature_set(output / Path(entry["path"]).with_suffix(""))
        if feature.derivation is None or feature.derivation.result_id != result.readout_id:
            raise ValueError("HR FeatureSet derivation mismatch")
        if entry["feature_kind"] == "hr_band_energy":
            energy.append(feature)
        else:
            fractions.append(feature)
    return HRReadoutAnalysis(result, tuple(energy), tuple(fractions))

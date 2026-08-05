"""Auditable shared run lifecycle for P1/P8, P2, and dense P3-A."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

import yaml

from .feature_outputs import write_dense_feature_outputs
from .features import build_dense_feature_sets
from .io_rew import REWManualReviewRequired
from .multisine_outputs import write_multisine_qc_outputs
from .p1_adapters import P1AdapterError, P1ManualReviewRequired
from .pipeline_dispatch import dispatch_measurement, read_measurement_meta
from .quality_control import QC_SCHEMA_VERSION, evaluate_measurement_quality
from .quality_control_outputs import write_quality_control_outputs
from .research_gate import ResearchGateError
from .schemas import (
    MeasurementMeta,
    Representation,
    SpectrumData,
    artifact_sha256,
    save_spectrum,
)


RUN_MANIFEST_SCHEMA_VERSION = "1.2.0"


@dataclass(frozen=True, slots=True)
class RunResult:
    output_directory: Path
    processing_status: str
    success: bool
    spectrum: SpectrumData | None
    run_manifest: Mapping[str, Any]


def _git_state(project_root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def _write_measurement_index(path: Path, spectrum: SpectrumData) -> None:
    row = spectrum.meta.to_dict()
    row["manual_review_reasons"] = ";".join(
        spectrum.meta.manual_review_reasons
    )
    row["phase_status"] = spectrum.phase_status.value
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)


def _write_failure_views(
    output: Path,
    *,
    source: Path,
    metadata: Path,
    meta: MeasurementMeta | None,
    processing_status: str,
    category: str,
    message: str,
) -> None:
    if meta is None:
        row: dict[str, Any] = {
            "sample_id": "",
            "measurement_mode": "",
            "source_path": source.as_posix(),
            "metadata_path": metadata.as_posix(),
            "data_origin": "unresolved",
            "eligible_for_scientific_analysis": False,
            "phase_status": "unavailable",
            "processing_status": processing_status,
        }
    else:
        row = meta.to_dict()
        row["manual_review_reasons"] = ";".join(meta.manual_review_reasons)
        row["phase_status"] = "unavailable"
        row["processing_status"] = processing_status
    with (output / "measurements.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    qc_row = {
        "status": processing_status,
        "failure_category": category,
        "message": message,
    }
    with (output / "measurement_qc.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(qc_row))
        writer.writeheader()
        writer.writerow(qc_row)


def _known_inputs(
    source: Path,
    metadata: Path,
    *,
    meta: MeasurementMeta | None = None,
    resolved_config: Mapping[str, Any] | None = None,
    stimulus_manifest: str | Path | None = None,
) -> list[dict[str, Any]]:
    source_role = "recording" if source.suffix.lower() == ".wav" else "measurement"
    metadata_role = "sidecar" if source.suffix.lower() == ".wav" else "metadata"
    candidates: list[tuple[str, Path]] = [
        (source_role, source),
        (metadata_role, metadata),
    ]
    if meta is not None and meta.stimulus_id is not None and resolved_config is not None:
        manifest = (
            Path(stimulus_manifest).resolve()
            if stimulus_manifest is not None
            else (
                Path(resolved_config["paths"]["stimuli"])
                / meta.stimulus_id
                / "stimulus_manifest.json"
            ).resolve()
        )
        candidates.append(("stimulus_manifest", manifest))
        if manifest.is_file():
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                wav_name = payload.get("wav_file")
                if isinstance(wav_name, str) and wav_name:
                    candidates.append(("stimulus_wav", manifest.parent / wav_name))
            except (OSError, json.JSONDecodeError):
                pass
    items = []
    for role, path in candidates:
        exists = path.is_file()
        items.append(
            {
                "role": role,
                "path": path.resolve().as_posix(),
                "exists": exists,
                "sha256": artifact_sha256(path) if exists else None,
            }
        )
    return items


def _artifact_records(output: Path) -> list[dict[str, str]]:
    return [
        {
            "role": path.stem,
            "path": path.relative_to(output).as_posix(),
            "sha256": artifact_sha256(path),
        }
        for path in sorted(output.rglob("*"))
        if path.is_file()
        and path.name not in {"run_manifest.json", "run_manifest.sha256"}
    ]


def _write_run_manifest(output: Path, manifest: Mapping[str, Any]) -> None:
    manifest_path = output / "run_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output / "run_manifest.sha256").write_text(
        artifact_sha256(manifest_path),
        encoding="ascii",
    )


def _failure_disposition(error: Exception) -> tuple[str, str]:
    if isinstance(error, (P1ManualReviewRequired, REWManualReviewRequired)):
        return "manual_review_required", "manual_review"
    if isinstance(error, ResearchGateError):
        return "blocked_research_gate", "research_gate"
    message = str(error).casefold()
    if "missing" in message:
        return "failed", "missing_input"
    if "hash" in message:
        return "failed", "integrity_mismatch"
    if "mismatch" in message:
        return "failed", "artifact_mismatch"
    return "failed", "validation_error"


def execute_measurement_run(
    source_path: str | Path,
    metadata_path: str | Path,
    resolved_config: Mapping[str, Any],
    *,
    output_root: str | Path,
    run_id: str,
    stimulus_manifest: str | Path | None = None,
) -> RunResult:
    """Execute shared import/QC plus representation-aware P3-A once."""
    run_component = Path(run_id)
    if (
        not run_id.strip()
        or run_id in {".", ".."}
        or run_component.name != run_id
        or "/" in run_id
        or "\\" in run_id
    ):
        raise ValueError("run_id must be one non-empty path component")
    created_at = datetime.now(UTC)
    source = Path(source_path).resolve()
    metadata = Path(metadata_path).resolve()
    meta: MeasurementMeta | None = None
    metadata_error: Exception | None = None
    try:
        meta = read_measurement_meta(metadata)
    except Exception as exc:  # normalized into an auditable failure below
        metadata_error = exc
    purpose = str(resolved_config["run_purpose"])
    isolation = "quarantine" if meta is None else meta.data_origin.value
    output = (
        Path(output_root)
        / isolation
        / purpose
        / run_id
    ).resolve()
    if isolation == "quarantine":
        output = (Path(output_root) / "quarantine" / run_id).resolve()
    if output.exists():
        raise FileExistsError(f"Run output already exists: {output}")
    output.mkdir(parents=True)

    config_snapshot = output / "config_snapshot.yaml"
    config_snapshot.write_text(
        yaml.safe_dump(dict(resolved_config), sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )
    project_root = Path(__file__).resolve().parents[2]
    if metadata_error is not None:
        processing_status, category = _failure_disposition(metadata_error)
        _write_failure_views(
            output,
            source=source,
            metadata=metadata,
            meta=None,
            processing_status=processing_status,
            category=category,
            message=str(metadata_error),
        )
        manifest = {
            "run_manifest_schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "qc_schema_version": QC_SCHEMA_VERSION,
            "run_id": run_id,
            "processing_status": processing_status,
            "success": False,
            "created_at_utc": created_at.isoformat(),
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "versions": {
                "pipeline": resolved_config["pipeline_version"],
                "config_schema": resolved_config["schema_versions"]["config"],
                "measurement_schema": resolved_config["schema_versions"]["measurement"],
                "feature_schema": resolved_config["schema_versions"]["feature"],
            },
            "git": _git_state(project_root),
            "measurement_mode": str(resolved_config["measurement_mode"]),
            "run_purpose": purpose,
            "data_origin": "unresolved",
            "dataset_role": "unresolved",
            "eligible_for_scientific_analysis": False,
            "sample_id": None,
            "stimulus_id": None,
            "stimulus_hash": None,
            "tone_set_id": None,
            "recording_hash": artifact_sha256(source) if source.is_file() else None,
            "sidecar_hash": None,
            "config_hash": artifact_sha256(config_snapshot),
            "inputs": _known_inputs(source, metadata),
            "phase_status": "unavailable",
            "qc_status": "unavailable",
            "random_state": int(resolved_config["random_state"]),
            "artifacts": _artifact_records(output),
            "stage_gate": {
                "P1": "failed",
                "P7": "not_run",
                "P8": "not_run",
                "P2": "not_run",
                "P3_A": "not_run",
                "P3_B": "not_implemented",
                "P4_P6": "not_implemented",
            },
            "failure": {
                "category": category,
                "exception_type": type(metadata_error).__name__,
                "message": str(metadata_error),
                "manual_review_reasons": [],
            },
        }
        _write_run_manifest(output, manifest)
        return RunResult(
            output_directory=output,
            processing_status=processing_status,
            success=False,
            spectrum=None,
            run_manifest=manifest,
        )

    try:
        adapter = dispatch_measurement(
            source,
            metadata,
            resolved_config,
            stimulus_manifest=stimulus_manifest,
        )
    except Exception as error:
        processing_status, category = _failure_disposition(error)
        _write_failure_views(
            output,
            source=source,
            metadata=metadata,
            meta=meta,
            processing_status=processing_status,
            category=category,
            message=str(error),
        )
        failure_manifest = {
            "run_manifest_schema_version": RUN_MANIFEST_SCHEMA_VERSION,
            "qc_schema_version": QC_SCHEMA_VERSION,
            "run_id": run_id,
            "processing_status": processing_status,
            "success": False,
            "created_at_utc": created_at.isoformat(),
            "finished_at_utc": datetime.now(UTC).isoformat(),
            "versions": {
                "pipeline": meta.pipeline_version,
                "config_schema": meta.config_schema_version,
                "measurement_schema": meta.measurement_schema_version,
                "feature_schema": meta.feature_schema_version,
            },
            "git": _git_state(project_root),
            "measurement_mode": meta.measurement_mode.value,
            "run_purpose": purpose,
            "data_origin": meta.data_origin.value,
            "dataset_role": meta.dataset_role.value,
            "eligible_for_scientific_analysis": meta.eligible_for_scientific_analysis,
            "sample_id": meta.sample_id,
            "stimulus_id": meta.stimulus_id,
            "stimulus_hash": meta.stimulus_hash,
            "tone_set_id": meta.tone_set_id,
            "recording_hash": meta.source_sha256,
            "sidecar_hash": artifact_sha256(metadata),
            "config_hash": artifact_sha256(config_snapshot),
            "inputs": _known_inputs(
                source,
                metadata,
                meta=meta,
                resolved_config=resolved_config,
                stimulus_manifest=stimulus_manifest,
            ),
            "phase_status": "unavailable",
            "qc_status": "unavailable",
            "random_state": int(resolved_config["random_state"]),
            "artifacts": _artifact_records(output),
            "stage_gate": {
                "P1": processing_status,
                "P7": "not_run",
                "P8": "not_run",
                "P2": "not_run",
                "P3_A": "not_run",
                "P3_B": "not_implemented",
                "P4_P6": "not_implemented",
            },
            "failure": {
                "category": category,
                "exception_type": type(error).__name__,
                "message": str(error),
                "manual_review_reasons": list(
                    getattr(error, "reasons", ())
                ),
            },
        }
        _write_run_manifest(output, failure_manifest)
        return RunResult(
            output_directory=output,
            processing_status=processing_status,
            success=False,
            spectrum=None,
            run_manifest=failure_manifest,
        )

    spectrum = adapter.spectrum
    _write_measurement_index(output / "measurements.csv", spectrum)
    if adapter.multisine_analysis is not None:
        write_multisine_qc_outputs(
            adapter.multisine_analysis,
            output,
            measurement_summary_filename="p8_measurement_qc.csv",
        )
    else:
        save_spectrum(spectrum, output / "spectrum_data")
    qc_result = evaluate_measurement_quality(
        spectrum,
        resolved_config["quality_control"],
        run_purpose=purpose,
    )
    write_quality_control_outputs(qc_result, output)
    qc_status = qc_result.aggregate_status.value
    dense_processing = None
    if spectrum.representation is Representation.DENSE_SPECTRUM:
        dense_processing = build_dense_feature_sets(
            spectrum,
            qc_result,
            resolved_config["preprocessing"],
        )
        write_dense_feature_outputs(dense_processing, output / "processed")
        p3_status = dense_processing.processing_status
        p3_success = p3_status == "completed"
    else:
        p3_status = "not_applicable_sparse"
        p3_success = True
    success = qc_status == "valid" and p3_success

    inputs = _known_inputs(
        source,
        metadata,
        meta=spectrum.meta,
        resolved_config=resolved_config,
        stimulus_manifest=stimulus_manifest,
    )
    artifacts = _artifact_records(output)
    manifest: dict[str, Any] = {
        "run_manifest_schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "qc_schema_version": QC_SCHEMA_VERSION,
        "run_id": run_id,
        "processing_status": "completed",
        "success": success,
        "created_at_utc": created_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "versions": {
            "pipeline": spectrum.meta.pipeline_version,
            "config_schema": spectrum.meta.config_schema_version,
            "measurement_schema": spectrum.meta.measurement_schema_version,
            "feature_schema": spectrum.meta.feature_schema_version,
        },
        "git": _git_state(project_root),
        "measurement_mode": spectrum.meta.measurement_mode.value,
        "run_purpose": str(resolved_config["run_purpose"]),
        "data_origin": spectrum.meta.data_origin.value,
        "dataset_role": spectrum.meta.dataset_role.value,
        "eligible_for_scientific_analysis": (
            spectrum.meta.eligible_for_scientific_analysis
        ),
        "sample_id": spectrum.meta.sample_id,
        "stimulus_id": spectrum.meta.stimulus_id,
        "stimulus_hash": spectrum.meta.stimulus_hash,
        "tone_set_id": spectrum.meta.tone_set_id,
        "recording_hash": spectrum.meta.source_sha256,
        "sidecar_hash": artifact_sha256(metadata),
        "config_hash": artifact_sha256(config_snapshot),
        "inputs": inputs,
        "phase_status": spectrum.phase_status.value,
        "qc_status": qc_status,
        "preprocessing": (
            {
                "processing_status": dense_processing.processing_status,
                "preprocessing_id": dense_processing.preprocessing_id,
                "valid_grid_fraction": dense_processing.valid_grid_fraction,
                "feature_kinds_written": sorted(
                    kind.value for kind in dense_processing.feature_sets
                ),
                "failure_reasons": [
                    failure.reason for failure in dense_processing.failures
                ],
            }
            if dense_processing is not None
            else {
                "processing_status": "not_applicable_sparse",
                "preprocessing_id": None,
                "valid_grid_fraction": None,
                "feature_kinds_written": [],
                "failure_reasons": [],
            }
        ),
        "random_state": int(resolved_config["random_state"]),
        "artifacts": artifacts,
        "stage_gate": {
            "P1": "completed",
            "P7": (
                "validated_existing_artifact"
                if spectrum.meta.stimulus_id is not None
                else "not_applicable"
            ),
            "P8": (
                "completed"
                if adapter.multisine_analysis is not None
                else "not_applicable"
            ),
            "P2": "completed",
            "P3_A": p3_status,
            "P3_B": "not_implemented",
            "P4_P6": "not_implemented",
        },
        "failure": None,
    }
    _write_run_manifest(output, manifest)
    return RunResult(
        output_directory=output,
        processing_status="completed",
        success=success,
        spectrum=spectrum,
        run_manifest=manifest,
    )

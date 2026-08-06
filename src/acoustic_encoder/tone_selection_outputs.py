"""Stable, hash-audited outputs for DEV-C12 P9-A tone selection."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .sweep_multisine_bridge import (
    CandidateToneUniverse,
    SelectedToneSetArtifact,
    ToneSelectionAnalysisResult,
    ToneSelectionInputError,
    ToneSelectionScope,
)
from .version import SCHEMA_VERSION_QUARTET


TONE_SELECTION_MANIFEST_SCHEMA_VERSION = "1.0.0"


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_bytes(_json_bytes(payload))


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name) for name in fieldnames})


def write_tone_selection_outputs(
    result: ToneSelectionAnalysisResult,
    scope: ToneSelectionScope,
    universe: CandidateToneUniverse,
    config: Mapping[str, Any],
    output_directory: str | Path,
    *,
    input_file_hashes: Mapping[str, str],
    git_commit: str,
    created_at: str | None = None,
) -> tuple[Path, ...]:
    """Write all P9-A artifacts once; an existing directory is never overwritten."""
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError(f"tone-selection output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    score_by_id = {item.candidate_id: item for item in result.candidate_scores}
    paths: list[Path] = []

    def csv_file(name: str, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
        path = output / name
        _write_csv(path, fields, rows)
        paths.append(path)

    csv_file(
        "candidate_universe_audit.csv",
        ("candidate_id", "tone_index", "frequency_hz", "dft_bin", "sample_rate_hz", "period_samples", "analysis_band_min_hz", "analysis_band_max_hz", "eligible", "eligibility_reasons", "source_tone_set_id", "source_tone_set_sha256", "candidate_universe_id", "candidate_universe_sha256"),
        (
            {
                **candidate.to_dict(),
                "sample_rate_hz": universe.sample_rate_hz,
                "period_samples": universe.period_samples,
                "analysis_band_min_hz": universe.analysis_band_hz[0],
                "analysis_band_max_hz": universe.analysis_band_hz[1],
                "eligible": score_by_id[candidate.candidate_id].eligible,
                "eligibility_reasons": json.dumps(score_by_id[candidate.candidate_id].eligibility_reasons, separators=(",", ":")),
                "source_tone_set_id": universe.source_tone_set_id,
                "source_tone_set_sha256": universe.source_tone_set_sha256,
                "candidate_universe_id": universe.candidate_universe_id,
                "candidate_universe_sha256": universe.sha256,
            }
            for candidate in universe.candidates
        ),
    )
    reference_by_sample: dict[str, list[Any]] = {}
    for reference in scope.feature_references:
        reference_by_sample.setdefault(reference.sample_id, []).append(reference)
    csv_file(
        "sample_scope_audit.csv",
        ("sample_id", "physical_state_id", "cohort_role", "configuration_id", "direction_id", "direction_angle_deg", "session_id", "repeat_type", "repeat_id", "reposition_round_id", "assembly_id", "acquisition_block_id", "feature_artifact_ids", "view_roles", "selection_included", "final_test_sealed"),
        (
            {
                **member.to_dict(),
                "feature_artifact_ids": json.dumps([item.artifact_id for item in reference_by_sample.get(member.sample_id, [])], separators=(",", ":")),
                "view_roles": json.dumps([item.view_role.value for item in reference_by_sample.get(member.sample_id, [])], separators=(",", ":")),
                "selection_included": member.cohort_role in scope.selection_roles,
                "final_test_sealed": member.sample_id in scope.sealed_final_test_sample_ids,
            }
            for member in scope.members
        ),
    )
    component_rows = []
    normalization_rows = []
    for score in result.candidate_scores:
        for component_id, component in sorted(score.components.items()):
            component_rows.append(
                {
                    "candidate_id": score.candidate_id,
                    **component.to_dict(),
                    "source_sample_ids": json.dumps(component.source_sample_ids, separators=(",", ":")),
                    "source_pair_ids": json.dumps(component.source_pair_ids, separators=(",", ":")),
                    "details": json.dumps(component.details or {}, sort_keys=True, separators=(",", ":")),
                }
            )
        for component_id, normalized in sorted((score.normalized_components or {}).items()):
            audit = (score.normalization_details or {}).get(component_id, {})
            normalization_rows.append(
                {
                    "candidate_id": score.candidate_id,
                    "component_id": component_id,
                    "normalized_value": normalized,
                    "weighted_contribution": (score.weighted_contributions or {}).get(component_id),
                    "normalization_scope_sha256": scope.training_sample_sha256,
                    "tie_method": config.get("scoring", {}).get("tie_method"),
                    "missing_policy": config.get("scoring", {}).get("optional_missing_policy"),
                    "reference_candidate_ids": json.dumps(audit.get("reference_candidate_ids", []), separators=(",", ":")),
                    "reference_candidate_sha256": audit.get("reference_candidate_sha256"),
                    "reference_candidate_count": audit.get("reference_candidate_count"),
                    "rank_denominator": audit.get("rank_denominator"),
                }
            )
    csv_file(
        "component_raw_values.csv",
        ("candidate_id", "component_id", "available", "value", "units", "direction", "source_sample_count", "source_pair_count", "status", "reason", "source_sample_ids", "source_pair_ids", "details"),
        component_rows,
    )
    csv_file(
        "component_normalization.csv",
        ("candidate_id", "component_id", "normalized_value", "weighted_contribution", "normalization_scope_sha256", "tie_method", "missing_policy", "reference_candidate_ids", "reference_candidate_sha256", "reference_candidate_count", "rank_denominator"),
        normalization_rows,
    )
    csv_file(
        "candidate_scores.csv",
        ("candidate_id", "tone_index", "frequency_hz", "dft_bin", "eligible", "final_score", "scoring_method", "warnings"),
        (
            {**item.to_dict(), "warnings": json.dumps(item.warnings, separators=(",", ":"))}
            for item in result.candidate_scores
        ),
    )
    csv_file(
        "candidate_eligibility.csv",
        ("candidate_id", "eligible", "reason_codes"),
        ({"candidate_id": item.candidate_id, "eligible": item.eligible, "reason_codes": json.dumps(item.eligibility_reasons, separators=(",", ":"))} for item in result.candidate_scores),
    )
    csv_file(
        "selection_trace.csv",
        tuple(result.selection.trace[0].to_dict()) if result.selection.trace else ("rank", "candidate_id", "decision", "reason"),
        (item.to_dict() for item in result.selection.trace),
    )
    selected_rows = () if result.selected_tone_set is None else (item.to_dict() for item in result.selected_tone_set.selected_tones)
    csv_file(
        "selected_tones.csv",
        ("selected_order", "selection_rank", "candidate_id", "source_tone_index", "frequency_hz", "dft_bin", "final_score"),
        selected_rows,
    )
    csv_file(
        "selection_summary.csv",
        ("selection_id", "processing_status", "lifecycle", "target_count", "selected_count", "scientifically_eligible", "deployment_allowed", "final_test_evaluated", "failures", "warnings"),
        ({
            "selection_id": result.selection_id,
            "processing_status": result.processing_status,
            "lifecycle": result.selection.lifecycle,
            "target_count": result.selection.target_count,
            "selected_count": len(result.selection.selected_candidate_ids),
            "scientifically_eligible": result.scientifically_eligible,
            "deployment_allowed": result.deployment_allowed,
            "final_test_evaluated": result.final_test_evaluated,
            "failures": json.dumps(result.failures, separators=(",", ":")),
            "warnings": json.dumps(result.warnings, separators=(",", ":")),
        },),
    )
    if result.selected_tone_set is not None:
        selected_path = output / "selected_tone_set.json"
        _write_json(selected_path, result.selected_tone_set.to_dict())
        paths.append(selected_path)
        selected_sha = output / "selected_tone_set.sha256"
        selected_sha.write_text(_file_sha256(selected_path) + "  selected_tone_set.json\n", encoding="utf-8")
        paths.append(selected_sha)
    result_path = output / "tone_selection_result.json"
    _write_json(result_path, result.to_dict())
    paths.append(result_path)
    artifact_hashes = {path.name: _file_sha256(path) for path in paths}
    manifest = {
        "schema_version": TONE_SELECTION_MANIFEST_SCHEMA_VERSION,
        **SCHEMA_VERSION_QUARTET,
        "selection_id": result.selection_id,
        "processing_status": result.processing_status,
        "selection_scope_id": scope.selection_scope_id,
        "selection_scope_sha256": scope.sha256,
        "candidate_universe_id": universe.candidate_universe_id,
        "candidate_universe_sha256": universe.sha256,
        "config_sha256": result.config_sha256,
        "dataset_qc_result_sha256": result.dataset_qc_result_sha256,
        "comparison_metrics_result_sha256": result.comparison_metrics_result_sha256,
        "training_sample_sha256": scope.training_sample_sha256,
        "outer_fold_id": scope.outer_fold_id,
        "sealed_final_test_sha256": scope.sealed_final_test_sha256,
        "data_origin": result.data_origin,
        "run_purpose": result.run_purpose,
        "scientifically_eligible": result.scientifically_eligible,
        "deployment_allowed": result.deployment_allowed,
        "final_test_evaluated": result.final_test_evaluated,
        "git_commit": git_commit,
        "random_state": scope.random_state,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "input_file_hashes": dict(sorted(input_file_hashes.items())),
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
    }
    manifest["manifest_content_sha256"] = _canonical_sha256(manifest)
    manifest_path = output / "tone_selection_manifest.json"
    _write_json(manifest_path, manifest)
    paths.append(manifest_path)
    manifest_sha = output / "tone_selection_manifest.sha256"
    manifest_sha.write_text(_file_sha256(manifest_path) + "  tone_selection_manifest.json\n", encoding="utf-8")
    paths.append(manifest_sha)
    return tuple(paths)


def load_tone_selection_bundle(output_directory: str | Path) -> dict[str, Any]:
    """Verify every recorded hash before returning the P9-A output bundle."""
    output = Path(output_directory)
    manifest_path = output / "tone_selection_manifest.json"
    manifest_sidecar = output / "tone_selection_manifest.sha256"
    expected_manifest = manifest_sidecar.read_text(encoding="utf-8").split()[0]
    if _file_sha256(manifest_path) != expected_manifest:
        raise ToneSelectionInputError("tone-selection manifest file hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    semantic = dict(manifest)
    expected_content = semantic.pop("manifest_content_sha256")
    if _canonical_sha256(semantic) != expected_content:
        raise ToneSelectionInputError("tone-selection manifest content hash mismatch")
    for relative, digest in manifest["artifact_hashes"].items():
        if _file_sha256(output / relative) != digest:
            raise ToneSelectionInputError(f"tone-selection artifact hash mismatch: {relative}")
    result = json.loads((output / "tone_selection_result.json").read_text(encoding="utf-8"))
    analysis = ToneSelectionAnalysisResult.from_dict(result)
    selected_path = output / "selected_tone_set.json"
    selected = None
    if selected_path.exists():
        sidecar_digest = (output / "selected_tone_set.sha256").read_text(encoding="utf-8").split()[0]
        if _file_sha256(selected_path) != sidecar_digest:
            raise ToneSelectionInputError("selected tone-set file hash mismatch")
        selected = SelectedToneSetArtifact.from_dict(json.loads(selected_path.read_text(encoding="utf-8")))
    if analysis.selected_tone_set != selected:
        raise ToneSelectionInputError("typed result and selected tone-set artifact disagree")
    selected_csv_rows = list(csv.DictReader((output / "selected_tones.csv").open(newline="", encoding="utf-8")))
    expected_selected = () if selected is None else selected.selected_tones
    if len(selected_csv_rows) != len(expected_selected) or any(
        row["candidate_id"] != record.candidate_id
        or int(row["selected_order"]) != record.selected_order
        or int(row["selection_rank"]) != record.selection_rank
        or int(row["source_tone_index"]) != record.source_tone_index
        or float(row["frequency_hz"]) != record.frequency_hz
        or int(row["dft_bin"]) != record.dft_bin
        or float(row["final_score"]) != record.final_score
        for row, record in zip(selected_csv_rows, expected_selected, strict=True)
    ):
        raise ToneSelectionInputError("selected_tones.csv disagrees with typed selected tone-set")
    score_csv_rows = list(csv.DictReader((output / "candidate_scores.csv").open(newline="", encoding="utf-8")))

    def optional_float_matches(raw: str, expected: float | None) -> bool:
        return (raw == "" and expected is None) or (raw != "" and expected is not None and float(raw) == expected)

    if len(score_csv_rows) != len(analysis.candidate_scores) or any(
        row["candidate_id"] != score.candidate_id
        or int(row["tone_index"]) != score.tone_index
        or float(row["frequency_hz"]) != score.frequency_hz
        or int(row["dft_bin"]) != score.dft_bin
        or (row["eligible"].lower() == "true") != score.eligible
        or not optional_float_matches(row["final_score"], score.final_score)
        or row["scoring_method"] != score.scoring_method
        for row, score in zip(score_csv_rows, analysis.candidate_scores, strict=True)
    ):
        raise ToneSelectionInputError("candidate_scores.csv disagrees with typed analysis result")
    return {"manifest": manifest, "result": result, "analysis": analysis, "selected_tone_set": selected}

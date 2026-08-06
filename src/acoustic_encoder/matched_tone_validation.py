"""Deterministic simulated P7→S3→P8→P3-C validation orchestration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .io_rew import load_rew_measurement
from .matched_tone_outputs import write_matched_tone_outputs
from .multisine_outputs import write_multisine_qc_outputs
from .mock_data import generate_dual_mode_mock
from .p1_adapters import analyze_multisine_adapter
from .quality_control import evaluate_measurement_quality
from .schemas import MeasurementMeta, MeasurementMode, artifact_sha256
from .version import SCHEMA_VERSION_QUARTET
from .tone_features import (
    MatchedToneView,
    ToneFeatureProcessingResult,
    build_matched_tone_view,
    build_multisine_tone_feature_set,
    build_sweep_tone_feature_set,
)
from .tone_sets import load_tone_set


@dataclass(frozen=True, slots=True)
class SimulatedMatchedToneValidationResult:
    output_directory: Path
    sweep_result: ToneFeatureProcessingResult
    multisine_result: ToneFeatureProcessingResult
    view: MatchedToneView
    maximum_matched_error_db: float
    stimulus_manifest_path: Path
    mock_manifest_path: Path


def _safe_run_id(run_id: str) -> str:
    candidate = Path(run_id)
    if (
        not run_id.strip()
        or candidate.name != run_id
        or run_id in {".", ".."}
        or "/" in run_id
        or "\\" in run_id
    ):
        raise ValueError("run_id must be one non-empty path component")
    return run_id


def _canonical_mapping(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def run_simulated_matched_tone_validation(
    *,
    output_root: str | Path,
    run_id: str,
    sweep_config: Mapping[str, Any],
    multisine_config: Mapping[str, Any],
    stimulus_config: Mapping[str, Any],
    random_state: int = 20260805,
    recording_delay_samples: int = 1379,
    multisine_to_sweep_slope: float = 1.0,
    multisine_to_sweep_intercept_db: float = 0.0,
    shared_magnitude_quantity: str | None = None,
    shared_magnitude_reference: str | None = None,
    session_id: str = "S01",
    angle_deg: int = 0,
) -> SimulatedMatchedToneValidationResult:
    """Run one immutable, scientifically-ineligible known-H matched validation."""
    run_directory = (
        Path(output_root)
        / "simulated"
        / "software_validation"
        / _safe_run_id(run_id)
    )
    try:
        run_directory.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise FileExistsError(
            f"Matched-tone validation output already exists: {run_directory}"
        ) from exc

    sweep_resolved = deepcopy(dict(sweep_config))
    multisine_resolved = deepcopy(dict(multisine_config))
    sweep_matched = sweep_resolved["matched_tone_features"]
    multisine_matched = multisine_resolved["matched_tone_features"]
    if _canonical_mapping(sweep_matched) != _canonical_mapping(multisine_matched):
        raise ValueError("sweep and multisine matched_tone_features config mismatch")

    inputs_directory = run_directory / "inputs"
    mock_manifest_path = generate_dual_mode_mock(
        inputs_directory,
        stimulus_config,
        configurations=("U4ENC",),
        angles_deg=(angle_deg,),
        random_state=random_state,
        recording_delay_samples=recording_delay_samples,
        multisine_to_sweep_slope=multisine_to_sweep_slope,
        multisine_to_sweep_intercept_db=multisine_to_sweep_intercept_db,
        session_id=session_id,
    )
    mock_manifest = json.loads(mock_manifest_path.read_text(encoding="utf-8"))
    samples = [MeasurementMeta.from_dict(item) for item in mock_manifest["samples"]]
    sweep_meta = next(
        item for item in samples if item.measurement_mode is MeasurementMode.REW_SWEEP
    )
    multisine_meta = next(
        item
        for item in samples
        if item.measurement_mode is MeasurementMode.SCHROEDER_MULTISINE
    )
    stimulus_manifest_path = Path(mock_manifest["stimulus_manifest"])
    tone_set = load_tone_set(stimulus_manifest_path)

    sweep_spectrum = load_rew_measurement(
        sweep_meta.source_path,
        sweep_meta,
        run_purpose=sweep_resolved["run_purpose"],
    )
    multisine_resolved["paths"]["stimuli"] = (
        inputs_directory / "stimuli"
    ).as_posix()
    multisine_analysis = analyze_multisine_adapter(
        multisine_meta.source_path,
        multisine_meta.sidecar_path,
        stimulus_manifest_path,
        multisine_resolved,
    )
    multisine_spectrum = multisine_analysis.spectrum
    p8_directory = run_directory / "p8"
    p8_artifacts = write_multisine_qc_outputs(multisine_analysis, p8_directory)
    p8_run_manifest_path = p8_directory / "run_manifest.json"
    p8_run_manifest_path.write_text(
        json.dumps(
            {
                **SCHEMA_VERSION_QUARTET,
                "run_manifest_schema_version": "1.15.0",
                "processing_status": "completed",
                "measurement_mode": "schroeder_multisine",
                "sample_id": multisine_spectrum.meta.sample_id,
                "data_origin": "simulated",
                "run_purpose": "software_validation",
                "eligible_for_scientific_analysis": False,
                "artifacts": {
                    name: {
                        "path": path.as_posix(),
                        "sha256": artifact_sha256(path),
                    }
                    for name, path in sorted(p8_artifacts.items())
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if (shared_magnitude_quantity is None) != (shared_magnitude_reference is None):
        raise ValueError("shared simulated magnitude quantity/reference must be supplied together")
    if shared_magnitude_quantity is not None and shared_magnitude_reference is not None:
        sweep_spectrum = replace(
            sweep_spectrum,
            magnitude_quantity=shared_magnitude_quantity,
            magnitude_reference=shared_magnitude_reference,
        )
        multisine_spectrum = replace(
            multisine_spectrum,
            magnitude_quantity=shared_magnitude_quantity,
            magnitude_reference=shared_magnitude_reference,
        )

    sweep_qc = evaluate_measurement_quality(
        sweep_spectrum,
        sweep_resolved["quality_control"],
        run_purpose=sweep_resolved["run_purpose"],
    )
    multisine_qc = evaluate_measurement_quality(
        multisine_spectrum,
        multisine_resolved["quality_control"],
        run_purpose=multisine_resolved["run_purpose"],
    )
    sweep_result = build_sweep_tone_feature_set(
        sweep_spectrum,
        sweep_qc,
        sweep_resolved["preprocessing"],
        tone_set,
        sweep_matched,
    )
    multisine_result = build_multisine_tone_feature_set(
        multisine_spectrum,
        multisine_qc,
        tone_set,
        multisine_matched,
    )
    view = build_matched_tone_view(
        sweep_result,
        multisine_result,
        sweep_matched,
    )
    if sweep_result.feature_set is None or multisine_result.feature_set is None:
        raise ValueError("known-H validation did not construct both FeatureSets")
    common = view.common_valid_mask
    if not np.any(common):
        raise ValueError("known-H validation has no common valid tones")
    maximum_error = float(
        np.max(
            np.abs(
                sweep_result.feature_set.values[common]
                - (
                    multisine_to_sweep_slope
                    * multisine_result.feature_set.values[common]
                    + multisine_to_sweep_intercept_db
                )
            )
        )
    )
    write_matched_tone_outputs(
        sweep_result,
        multisine_result,
        view,
        tone_set,
        sweep_matched,
        run_directory / "processed",
    )
    return SimulatedMatchedToneValidationResult(
        output_directory=run_directory,
        sweep_result=sweep_result,
        multisine_result=multisine_result,
        view=view,
        maximum_matched_error_db=maximum_error,
        stimulus_manifest_path=stimulus_manifest_path,
        mock_manifest_path=mock_manifest_path,
    )

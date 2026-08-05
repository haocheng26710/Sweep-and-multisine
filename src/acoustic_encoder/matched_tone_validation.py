"""Deterministic simulated P7→S3→P8→P3-C validation orchestration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .io_rew import load_rew_measurement
from .matched_tone_outputs import write_matched_tone_outputs
from .mock_data import generate_dual_mode_mock
from .p1_adapters import analyze_multisine_adapter
from .quality_control import evaluate_measurement_quality
from .schemas import MeasurementMeta, MeasurementMode
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
        angles_deg=(0,),
        random_state=random_state,
        recording_delay_samples=recording_delay_samples,
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
                - multisine_result.feature_set.values[common]
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

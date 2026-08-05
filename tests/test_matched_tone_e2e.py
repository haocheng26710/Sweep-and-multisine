from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from acoustic_encoder.config import load_config
from acoustic_encoder.matched_tone_validation import (
    run_simulated_matched_tone_validation,
)
from acoustic_encoder.schemas import DataOrigin, DatasetRole, FeatureKind


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_known_h_dual_input_matched_tone_e2e(tmp_path: Path) -> None:
    sweep_config = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    multisine_config = load_config(
        PROJECT_ROOT / "config" / "experiment_v2_u4_multisine.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )
    stimulus = load_config(
        PROJECT_ROOT / "config" / "stimulus_multisine_broadband.yaml",
        default_path=PROJECT_ROOT / "config" / "default.yaml",
    )["stimulus"]

    result = run_simulated_matched_tone_validation(
        output_root=tmp_path / "outputs",
        run_id="known-h",
        sweep_config=deepcopy(sweep_config),
        multisine_config=deepcopy(multisine_config),
        stimulus_config=deepcopy(stimulus),
        random_state=123,
        recording_delay_samples=1379,
    )

    assert result.output_directory == (
        tmp_path / "outputs" / "simulated" / "software_validation" / "known-h"
    )
    assert result.view.processing_status == "completed"
    assert result.view.common_valid_count == 71
    assert result.maximum_matched_error_db <= 0.10
    sweep = result.sweep_result.feature_set
    multisine = result.multisine_result.feature_set
    assert sweep is not None and multisine is not None
    assert sweep.feature_kind is FeatureKind.TONE_PROJECTION_FROM_SWEEP
    assert multisine.feature_kind is FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE
    assert sweep.feature_names == multisine.feature_names
    assert sweep.units == multisine.units
    assert sweep.tone_set_id == multisine.tone_set_id
    assert sweep.meta.data_origin is DataOrigin.SIMULATED
    assert multisine.meta.data_origin is DataOrigin.SIMULATED
    assert sweep.meta.dataset_role is DatasetRole.SOFTWARE_VALIDATION
    assert multisine.meta.eligible_for_scientific_analysis is False
    assert result.view.source_reference_status == "quantity_mismatch"
    assert result.view.comparison_status == "normalized_shape_only_candidate"
    assert result.view.cross_mode_absolute_comparable is False
    assert (result.output_directory / "processed" / "preprocessing_manifest.json").is_file()


def test_matched_tone_validation_refuses_existing_run(tmp_path: Path) -> None:
    output = tmp_path / "outputs" / "simulated" / "software_validation" / "same"
    output.mkdir(parents=True)

    try:
        run_simulated_matched_tone_validation(
            output_root=tmp_path / "outputs",
            run_id="same",
            sweep_config={},
            multisine_config={},
            stimulus_config={},
        )
    except FileExistsError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("existing validation output must not be overwritten")

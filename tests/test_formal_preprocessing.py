from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.formal_preprocessing import (
    FormalPreprocessingContractError,
    build_formal_log_grid,
    frozen_formal_preprocessing_contract,
    preprocess_formal_sweep,
    write_formal_preprocessing_result,
)
from acoustic_encoder.preprocessing import build_dense_grid
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    Representation,
    SourceFormat,
    SpectrumData,
    artifact_sha256,
)


def _synthetic_sweep(
    frequency_hz: np.ndarray,
    magnitude_db: np.ndarray,
    valid_mask: np.ndarray | None = None,
) -> SpectrumData:
    return SpectrumData(
        frequency_hz=frequency_hz,
        magnitude_db=magnitude_db,
        valid_mask=(
            np.ones(frequency_hz.size, dtype=bool)
            if valid_mask is None
            else valid_mask
        ),
        representation=Representation.DENSE_SPECTRUM,
        phase_status=PhaseStatus.UNAVAILABLE,
        quality_metrics={"fixture": "synthetic/software_validation"},
        meta=MeasurementMeta(
            sample_id="formal-1-synthetic",
            pipeline_version="test",
            config_schema_version="test",
            measurement_schema_version="2.0.0",
            feature_schema_version="2.0.0",
            device_version="synthetic-device",
            configuration="synthetic-configuration",
            angle_deg=0.0,
            session_id="synthetic-session",
            repeat_type="CONT",
            repeat_id="synthetic-repeat",
            experiment_step="FORMAL-1-software-validation",
            measurement_mode=MeasurementMode.REW_SWEEP,
            source_format=SourceFormat.MOCK_DENSE,
            source_path="synthetic://formal-1",
            data_origin=DataOrigin.SIMULATED,
            dataset_role=DatasetRole.SOFTWARE_VALIDATION,
            source_sha256="1" * 64,
            provenance_uri="synthetic://formal-1",
            eligible_for_scientific_analysis=False,
        ),
    )


def test_frozen_formal_log_grid_follows_protocol_formula_and_bounds() -> None:
    contract = frozen_formal_preprocessing_contract()

    grid = build_formal_log_grid(contract)

    assert grid[0] == 200.0
    assert np.all(np.diff(grid) > 0.0)
    assert np.allclose(grid[1:] / grid[:-1], 2.0 ** (1.0 / 48.0))
    assert grid[-1] <= 8000.0
    assert grid[-1] * 2.0 ** (1.0 / 48.0) > 8000.0
    assert grid.size == math.floor(48.0 * math.log2(8000.0 / 200.0)) + 1


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("grid_type", "linear_hz"),
        ("points_per_octave", 24),
        ("frequency_min_hz", 100.0),
        ("frequency_max_hz", 4000.0),
        ("primary_band_hz", [200.0, 3000.0]),
        ("secondary_band_hz", [3000.0, 8000.0]),
        ("smoothing_fraction_octave", "1/6"),
    ],
)
def test_formal_grid_rejects_every_non_frozen_contract_value(
    field: str,
    wrong_value: object,
) -> None:
    contract = frozen_formal_preprocessing_contract()
    contract[field] = wrong_value

    with pytest.raises(FormalPreprocessingContractError, match=field):
        build_formal_log_grid(contract)


def test_formal_preprocessing_is_deterministic_and_hashes_content() -> None:
    contract = frozen_formal_preprocessing_contract()
    frequency = build_formal_log_grid(contract)
    spectrum = _synthetic_sweep(frequency, 70.0 + np.log2(frequency / 200.0))

    first = preprocess_formal_sweep(spectrum, contract)
    second = preprocess_formal_sweep(spectrum, contract)

    assert np.array_equal(first.frequency_hz, second.frequency_hz)
    assert np.array_equal(first.magnitude_db, second.magnitude_db)
    assert np.array_equal(first.valid_mask, second.valid_mask)
    assert first.manifest == second.manifest
    assert len(first.manifest["input_sha256"]) == 64
    assert len(first.manifest["output_sha256"]) == 64


def test_invalid_run_is_not_interpolated_or_smoothed_across() -> None:
    contract = frozen_formal_preprocessing_contract()
    frequency = build_formal_log_grid(contract)
    values = np.concatenate(
        (
            np.zeros(100),
            np.full(10, np.nan),
            np.full(frequency.size - 110, 100.0),
        )
    )
    valid = np.ones(frequency.size, dtype=bool)
    valid[100:110] = False

    result = preprocess_formal_sweep(
        _synthetic_sweep(frequency, values, valid),
        contract,
    )

    assert not np.any(result.valid_mask[100:110])
    assert result.magnitude_db[99] == pytest.approx(0.0)
    assert result.magnitude_db[110] == pytest.approx(100.0)


def test_missing_frequency_discontinuity_is_not_interpolated_across() -> None:
    contract = frozen_formal_preprocessing_contract()
    target = build_formal_log_grid(contract)
    source = np.delete(target, np.s_[100:110])
    values = np.where(np.arange(source.size) < 100, 0.0, 100.0)

    result = preprocess_formal_sweep(_synthetic_sweep(source, values), contract)

    assert not np.any(result.valid_mask[100:110])
    assert result.magnitude_db[99] == pytest.approx(0.0)
    assert result.magnitude_db[110] == pytest.approx(100.0)


@pytest.mark.filterwarnings("error")
def test_out_of_band_source_rows_are_selected_out_before_log_interpolation() -> None:
    contract = frozen_formal_preprocessing_contract()
    target = build_formal_log_grid(contract)
    baseline = preprocess_formal_sweep(
        _synthetic_sweep(target, np.full(target.size, 42.0)),
        contract,
    )
    frequency = np.concatenate(([0.0, 100.0], target, [9000.0]))
    values = np.concatenate(([-999.0, -999.0], np.full(target.size, 42.0), [999.0]))

    result = preprocess_formal_sweep(_synthetic_sweep(frequency, values), contract)

    assert np.array_equal(result.magnitude_db, baseline.magnitude_db)
    assert np.array_equal(result.valid_mask, baseline.valid_mask)


def test_constant_spectrum_is_unchanged_by_one_twelfth_octave_smoothing() -> None:
    contract = frozen_formal_preprocessing_contract()
    frequency = build_formal_log_grid(contract)

    result = preprocess_formal_sweep(
        _synthetic_sweep(frequency, np.full(frequency.size, 63.25)),
        contract,
    )

    assert np.all(result.valid_mask)
    assert np.allclose(result.magnitude_db, 63.25)
    assert result.manifest["processing_order"] == [
        "select_200_8000_hz",
        "interpolate_log_common_grid",
        "smooth_1_12_octave_db",
    ]


def test_one_twelfth_octave_kernel_is_five_48ppo_points_interior() -> None:
    contract = frozen_formal_preprocessing_contract()
    frequency = build_formal_log_grid(contract)
    values = np.zeros(frequency.size)
    values[120] = 5.0

    result = preprocess_formal_sweep(_synthetic_sweep(frequency, values), contract)

    assert result.magnitude_db[120] == pytest.approx(1.0)
    assert np.count_nonzero(result.magnitude_db) == 5


def test_primary_and_secondary_band_masks_use_frozen_numeric_intervals() -> None:
    contract = frozen_formal_preprocessing_contract()
    frequency = build_formal_log_grid(contract)
    result = preprocess_formal_sweep(
        _synthetic_sweep(frequency, np.zeros(frequency.size)),
        contract,
    )

    assert np.array_equal(
        result.primary_band_mask,
        (frequency >= 200.0) & (frequency <= 4000.0),
    )
    assert np.array_equal(
        result.secondary_band_mask,
        (frequency >= 4000.0) & (frequency <= 8000.0),
    )
    assert np.all(result.primary_band_mask | result.secondary_band_mask)


def test_manifest_contains_complete_frozen_contract_and_algorithm_version() -> None:
    contract = frozen_formal_preprocessing_contract()
    frequency = build_formal_log_grid(contract)

    manifest = preprocess_formal_sweep(
        _synthetic_sweep(frequency, np.zeros(frequency.size)),
        contract,
    ).manifest

    assert {
        "grid_type",
        "points_per_octave",
        "frequency_min_hz",
        "frequency_max_hz",
        "primary_band_hz",
        "secondary_band_hz",
        "smoothing_fraction_octave",
        "preprocessing_algorithm_version",
        "input_sha256",
        "output_sha256",
    } <= manifest.keys()


def test_formal_result_writer_refuses_overwrite_and_hashes_artifacts(
    tmp_path: Path,
) -> None:
    contract = frozen_formal_preprocessing_contract()
    frequency = build_formal_log_grid(contract)
    result = preprocess_formal_sweep(
        _synthetic_sweep(frequency, np.zeros(frequency.size)),
        contract,
    )
    destination = tmp_path / "formal-output"

    paths = write_formal_preprocessing_result(result, destination)

    assert paths["spectrum"].is_file()
    assert paths["manifest"].is_file()
    assert paths["artifact_manifest"].is_file()
    artifact_manifest = json.loads(paths["artifact_manifest"].read_text("utf-8"))
    by_name = {item["path"]: item["sha256"] for item in artifact_manifest["artifacts"]}
    assert by_name[paths["spectrum"].name] == artifact_sha256(paths["spectrum"])
    assert by_name[paths["manifest"].name] == artifact_sha256(paths["manifest"])
    with pytest.raises(FileExistsError, match="already exists"):
        write_formal_preprocessing_result(result, destination)


def test_legacy_linear_software_validation_grid_remains_available() -> None:
    grid = build_dense_grid(
        {"analysis_band_hz": [200, 400], "common_grid_step_hz": 10}
    )

    assert np.array_equal(grid.frequency_hz, np.arange(200.0, 401.0, 10.0))

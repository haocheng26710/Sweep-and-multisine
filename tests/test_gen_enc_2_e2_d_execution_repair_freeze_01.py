from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.gen_enc import forward_acoustic_network as core


def _near_parameters(alpha: float) -> dict[str, float]:
    parameters = {f"external_{angle}": 0.5 for angle in (0, 90, 180, 270)}
    parameters.update({f"loss_{angle}": 0.065 for angle in (0, 90, 180, 270)})
    parameters.update({f"q{angle}": 0.0 for angle in (0, 90, 180, 270)})
    parameters["shared_alpha"] = alpha
    return parameters


def _zero_nuisance() -> dict[str, float]:
    return {
        "independent_manufacturing_percent": 0.0,
        "batch_correlated_manufacturing_percent": 0.0,
    }


@pytest.mark.parametrize(
    ("alpha", "expected_coordinate"),
    ((0.03, 0.0), (0.07, 1.0)),
)
def test_near_closed_interval_endpoints_map_to_exact_coordinates(
    monkeypatch: pytest.MonkeyPatch,
    alpha: float,
    expected_coordinate: float,
) -> None:
    observed: list[float] = []

    def record_aperture_coordinate(coordinate: float) -> float:
        observed.append(coordinate)
        return 1.0

    monkeypatch.setattr(core, "_aperture_area", record_aperture_coordinate)
    core._branch_parameters(
        "NEAR_INDEPENDENT",
        _near_parameters(alpha),
        _zero_nuisance(),
        cell_index=0,
        repeat_index=0,
        repeat_seed=2026091001,
    )

    assert observed[:4] == [expected_coordinate] * 4


@pytest.mark.parametrize(
    "alpha",
    (
        np.nextafter(0.03, -math.inf),
        np.nextafter(0.07, math.inf),
    ),
)
def test_near_values_outside_closed_interval_remain_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    alpha: float,
) -> None:
    aperture_called = False

    def unexpected_aperture_call(coordinate: float) -> float:
        nonlocal aperture_called
        aperture_called = True
        return coordinate

    monkeypatch.setattr(core, "_aperture_area", unexpected_aperture_call)
    with pytest.raises(core.ForwardCoreError, match="NEAR_SHARED_ALPHA_OUT_OF_RANGE"):
        core._branch_parameters(
            "NEAR_INDEPENDENT",
            _near_parameters(float(alpha)),
            _zero_nuisance(),
            cell_index=0,
            repeat_index=0,
            repeat_seed=2026091001,
        )

    assert aperture_called is False


def test_near_exact20_interior_mapping_is_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[float] = []

    def record_aperture_coordinate(coordinate: float) -> float:
        observed.append(coordinate)
        return 1.0

    monkeypatch.setattr(core, "_aperture_area", record_aperture_coordinate)
    for ordinal in range(2, 20):
        alpha = 0.03 + (ordinal - 1) * 0.04 / 19.0
        core._branch_parameters(
            "NEAR_INDEPENDENT",
            _near_parameters(alpha),
            _zero_nuisance(),
            cell_index=0,
            repeat_index=0,
            repeat_seed=2026091001,
        )
        assert observed[-8:-4] == [(alpha - 0.03) / 0.04] * 4


def test_near20_endpoint_original_repro_matches_scalar_reference() -> None:
    repo = Path(__file__).resolve().parents[1]
    member = json.loads(
        (
            repo
            / "outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/instances/NEAR_INDEPENDENT/NEAR_20.identity.json"
        ).read_text(encoding="utf-8")
    )
    nuisance = {
        "snr_db": 30.0,
        "common_gain_db": 0.0,
        "sensor_independent_gain_db": 0.0,
        "common_frequency_axis_shift_relative": 0.0,
        "independent_manufacturing_percent": 0.0,
        "batch_correlated_manufacturing_percent": 0.0,
        "angle_offset_degrees": 0.0,
    }
    kwargs = {
        "member": member,
        "nuisance": nuisance,
        "cell_index": 0,
        "repeat_index": 0,
        "frequencies_hz": core.frozen_frequency_grid()[:4],
        "state_angles_degrees": (0.0, 90.0, 180.0, 270.0),
        "partition": "development",
        "repeat_seed_tuple": (2026091001, 2026091002),
    }

    optimized = core.solve_forward_block(**kwargs)
    reference = core.solve_forward_block_reference(**kwargs)

    assert optimized.numerically_valid is True
    np.testing.assert_allclose(
        optimized.central_pressure,
        reference.central_pressure,
        rtol=1e-12,
        atol=1e-12,
    )

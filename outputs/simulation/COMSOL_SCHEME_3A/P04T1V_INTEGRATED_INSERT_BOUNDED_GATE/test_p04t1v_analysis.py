import importlib.util
from pathlib import Path

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("p04t1v_analysis", HERE / "p04t1v_analysis.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def test_frozen_frequency_grid_is_exact():
    assert len(analysis.FREQUENCIES_HZ) == 31
    assert np.array_equal(analysis.REGULAR_HZ, np.arange(1400.0, 2100.1, 25.0))
    assert analysis.PRIMARY_HZ in analysis.FREQUENCIES_HZ
    assert analysis.SECONDARY_HZ in analysis.FREQUENCIES_HZ


def test_frozen_integrated_geometry_contract():
    assert analysis.VARIANTS["I75"]["cross_width_mm"] == pytest.approx(13.52333744142368)
    assert analysis.VARIANTS["I75"]["retained_air_fraction"] == pytest.approx(0.758260419817217)
    assert analysis.VARIANTS["I50P"]["cross_width_mm"] == pytest.approx(8.6)
    assert analysis.VARIANTS["I50P"]["retained_air_fraction"] == pytest.approx(0.540587057876302)
    for item in analysis.VARIANTS.values():
        assert item["outer_radius_mm"] == 17.9
        assert item["relief_diameter_mm"] == 20.4
        assert item["relief_depth_mm"] == 0.7


def test_full_pass_classification():
    result = analysis.classify(
        technical_i75=True, technical_i50p=True,
        branch_unique_i75=True, branch_unique_i50p=True,
        branch_hz=[1651.3, 1684.0, 1748.0],
        i75_primary_db=-2.0, i75_secondary_db=2.1,
        finite=True,
    )
    assert result == "P04T1V PASS_FOR_PRINT_AND_P04T2"


def test_i50p_failure_does_not_revoke_passing_i75():
    result = analysis.classify(
        technical_i75=True, technical_i50p=False,
        branch_unique_i75=True, branch_unique_i50p=False,
        branch_hz=[1651.3, 1684.0, np.nan],
        i75_primary_db=-2.0, i75_secondary_db=2.1,
        finite=True,
    )
    assert result == "P04T1V I75_PASS_I50P_NOT_AUTHORIZED"


@pytest.mark.parametrize("primary,secondary", [(0.1, 2.0), (-1.0, 2.0), (-2.0, -0.1)])
def test_i75_primary_gate_failure(primary, secondary):
    result = analysis.classify(
        technical_i75=True, technical_i50p=True,
        branch_unique_i75=True, branch_unique_i50p=True,
        branch_hz=[1651.3, 1684.0, 1748.0],
        i75_primary_db=primary, i75_secondary_db=secondary,
        finite=True,
    )
    assert result == "P04T1V PRINT_GATE_FAILED"

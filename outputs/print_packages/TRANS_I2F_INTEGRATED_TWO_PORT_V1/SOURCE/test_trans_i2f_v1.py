from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("generate_trans_i2f_v1.py")
SPEC = importlib.util.spec_from_file_location("trans_i2f_generator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_frozen_dimensions_and_frequency_order():
    geometry = MODULE.build_geometry()
    hr03 = MODULE.predicted_two_neck(MODULE.HR_SPECS["HR03"], geometry["hr03_cavity"])
    hr07 = MODULE.predicted_two_neck(MODULE.HR_SPECS["HR07"], geometry["hr07_cavity"])
    assert MODULE.APOTHEM == 105.0
    assert MODULE.AIR_HEIGHT == 6.4
    assert MODULE.PORT_EXTENSION == 12.0
    assert hr03["engineering_estimate_hz"] < hr07["engineering_estimate_hz"]


def test_branches_only_meet_at_microplenum():
    geometry = MODULE.build_geometry()
    overlap = geometry["north_branch"].difference(geometry["plenum"].buffer(0.001)).intersection(
        geometry["south_branch"].difference(geometry["plenum"].buffer(0.001))
    )
    assert overlap.area < 1e-6
    assert geometry["airspace"].geom_type == "Polygon"


def test_fasteners_and_turntable_clear_airspace():
    geometry = MODULE.build_geometry()
    assert geometry["screw_holes"].intersection(geometry["airspace"]).area < 1e-6
    assert geometry["mount_recesses"].intersection(geometry["airspace"]).area < 1e-6


def test_p1s_bed_fit_and_plenum_reduction():
    geometry = MODULE.build_geometry()
    xmin, ymin, xmax, ymax = geometry["outer"].bounds
    assert xmax - xmin + 10.0 <= 256.0
    assert ymax - ymin + 10.0 <= 256.0
    old_volume = 3.141592653589793 * 18.0**2 * 9.2
    new_volume = geometry["plenum"].area * MODULE.AIR_HEIGHT
    assert new_volume / old_volume < 0.10

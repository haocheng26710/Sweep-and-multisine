import importlib.util
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("p04t0_preflight", HERE / "p04t0_preflight.py")
MODULE = importlib.util.module_from_spec(SPEC)


def load_module():
    SPEC.loader.exec_module(MODULE)
    return MODULE


def test_frozen_air_fraction_and_insert_volume_are_exact():
    module = load_module()
    geometry = module.frozen_geometry()
    assert math.isclose(geometry["remaining_fraction"], 0.75, rel_tol=0.0, abs_tol=2e-15)
    assert math.isclose(geometry["insert_volume_mm3"], 2341.114845455112, rel_tol=0.0, abs_tol=2e-9)


def test_four_lobes_are_disconnected_and_keep_cross_and_mic_clear():
    module = load_module()
    audit = module.clearance_invariants()
    assert audit["insert_connected_component_count"] == 4
    assert audit["insert_intersects_retained_cross"] is False
    assert audit["insert_intersects_microphone_well"] is False
    assert audit["insert_intersects_fixed_channel_mouths"] is False


def test_nominal_z_stack_has_no_bridge_or_bond_allowance():
    module = load_module()
    stack = module.z_stack()
    assert stack["air_bottom_z_mm"] == 3.0
    assert stack["air_top_z_mm"] == 12.2
    assert stack["insert_nominal_height_mm"] == 9.2
    assert stack["unallocated_z_clearance_mm"] == 0.0


def test_reference_stl_dimensions_imply_millimetres():
    module = load_module()
    audits = module.audit_reference_stls(HERE / "reference_stl")
    by_part = {row["part"]: row for row in audits}
    assert by_part["P01"]["units_inference"] == "mm"
    assert by_part["P02"]["units_inference"] == "mm"
    assert by_part["P03"]["units_inference"] == "mm"
    assert math.isclose(by_part["P01"]["extent_z"], 12.2, abs_tol=1e-5)
    assert math.isclose(by_part["P02"]["extent_z"], 5.0, abs_tol=1e-5)
    assert math.isclose(by_part["P03"]["extent_z"], 6.5, abs_tol=1e-5)

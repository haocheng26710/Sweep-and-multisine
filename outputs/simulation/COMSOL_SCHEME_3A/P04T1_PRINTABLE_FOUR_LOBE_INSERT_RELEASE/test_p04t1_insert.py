import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "generate_p04t1_insert.py"


def load_module():
    spec = importlib.util.spec_from_file_location("p04t1", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generated():
    mod = load_module()
    result = mod.generate_package(HERE)
    return mod, result


def test_ideal_75_percent_volume_reproduction(generated):
    mod, _ = generated
    assert mod.ideal_solid_volume() == pytest.approx(2341.114845455112, abs=1e-9)
    assert mod.ideal_retained_air_fraction() == pytest.approx(0.75, abs=1e-12)


def test_quadrant_identity_maps(generated):
    _, result = generated
    expected = {
        "L1_NE": (1, 1),
        "L2_SE": (1, -1),
        "L3_SW": (-1, -1),
        "L4_NW": (-1, 1),
    }
    for name, signs in expected.items():
        bounds = result["mesh_validation"]["files"][f"P04T1_{name}.stl"]["bounding_box_mm"]
        assert bounds[0][0] * signs[0] > 0
        assert bounds[0][1] * signs[1] > 0
        assert bounds[1][0] * signs[0] > 0
        assert bounds[1][1] * signs[1] > 0


def test_frozen_print_clearances_and_relief(generated):
    _, result = generated
    contract = result["design_contract"]
    assert contract["printable_geometry_mm"]["outer_radius"] == pytest.approx(17.90)
    assert contract["printable_geometry_mm"]["straight_edge_half_width"] == pytest.approx(6.76166872071184)
    assert contract["printable_geometry_mm"]["relief_radius"] == pytest.approx(10.20)
    assert contract["printable_geometry_mm"]["relief_depth"] == pytest.approx(0.70)
    assert contract["printable_geometry_mm"]["height"] == pytest.approx(9.20)
    assert result["mesh_validation"]["relief_z_extent_mm"] == pytest.approx([0.0, 0.70])


def test_retained_air_and_fixed_channel_gates(generated):
    _, result = generated
    audit = result["acoustic_fidelity_audit"]
    assert 0.750 <= audit["equivalent_retained_air_fraction"] <= 0.761
    assert audit["retained_cross_width_mm"] >= 13.42333744142368
    assert audit["fixed_channel_min_lateral_margin_mm"] > 0
    assert audit["all_fixed_channel_paths_open"] is True


def test_stl_reload_watertight_manifold_and_volume(generated):
    _, result = generated
    files = result["mesh_validation"]["files"]
    for name, audit in files.items():
        assert audit["reload_pass"] is True, name
        assert audit["watertight"] is True, name
        assert audit["winding_consistent"] is True, name
        assert audit["degenerate_face_count"] == 0, name
        assert audit["self_intersection_free"] is True, name
        assert audit["positive_volume"] is True, name
    assert files["P04T1_FOUR_LOBE_PRINT_PLATE.stl"]["connected_components"] == 4
    for name in ("P04T1_L1_NE.stl", "P04T1_L2_SE.stl", "P04T1_L3_SW.stl", "P04T1_L4_NW.stl", "P04T1_ONE_LOBE_PRINT_X4.stl"):
        assert files[name]["connected_components"] == 1


def test_sha_manifest_is_self_consistent(generated):
    _, _result = generated
    manifest = HERE / "SHA256SUMS.txt"
    rows = manifest.read_text(encoding="utf-8").splitlines()
    assert rows
    for row in rows:
        expected, relative = row.split(None, 1)
        actual = hashlib.sha256((HERE / relative).read_bytes()).hexdigest()
        assert actual == expected, relative


def test_terminal_classification(generated):
    _, result = generated
    classification = json.loads((HERE / "terminal_classification.json").read_text(encoding="utf-8"))
    assert classification["classification"] == "P04T1 PRINT_PACKAGE_READY"
    assert result["all_release_gates_pass"] is True

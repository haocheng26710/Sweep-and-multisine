"""Focused regression tests for the P04T1R integrated P09 insert release."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "generate_p04t1r_integrated_insert.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("p04t1r_generator", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_frozen_ideal_air_fractions_and_printable_crosses():
    g = load_generator()
    assert g.ideal_retained_air_fraction(g.I75_IDEAL_HALF_WIDTH) == pytest.approx(0.75, abs=1e-12)
    assert g.ideal_retained_air_fraction(g.I50_IDEAL_HALF_WIDTH) == pytest.approx(0.50, abs=2e-12)
    assert g.print_cross_width("I75") == pytest.approx(13.52333744142368)
    assert g.print_cross_width("I50P") == pytest.approx(8.60)
    assert (g.print_cross_width("I50P") - g.FIXED_CHANNEL_WIDTH) / 2.0 >= 0.30 - 1e-12


@pytest.mark.parametrize("variant", ["I75", "I50P"])
def test_integrated_part_is_one_closed_printable_body(variant):
    g = load_generator()
    result = g.build_variant(variant)
    mesh = result["mesh"]
    audit = result["audit"]
    assert mesh.is_watertight
    assert mesh.is_winding_consistent
    assert g.mesh_component_count(mesh) == 1
    assert mesh.volume > 0
    assert audit["p09_nominal_geometry_preserved"] is True
    assert audit["connector_inside_original_dummy_channel"] is True
    assert audit["open_cardinal_channel_intrusion_mm2"] == pytest.approx(0.0, abs=1e-9)
    assert audit["p03_relief_radial_clearance_mm"] >= 0.10
    assert audit["p03_relief_axial_clearance_mm"] >= 0.19


def test_realised_air_fraction_and_primary_secondary_roles():
    g = load_generator()
    i75 = g.build_variant("I75")["audit"]
    i50 = g.build_variant("I50P")["audit"]
    assert 0.75 <= i75["realised_retained_air_fraction"] <= 0.761
    assert 0.53 < i50["realised_retained_air_fraction"] < 0.55
    assert i75["scientific_role"] == "primary_confirmatory_mechanism_insert"
    assert i50["scientific_role"] == "secondary_exploratory_dose_point"
    assert i50["realised_retained_air_fraction"] < i75["realised_retained_air_fraction"]


def test_print_plates_have_expected_component_counts(tmp_path):
    g = load_generator()
    outputs = g.generate_release(tmp_path, make_figures=False, write_documents=False)
    i75 = g.trimesh.load_mesh(outputs["i75_plate"], process=False)
    i50 = g.trimesh.load_mesh(outputs["i50p_plate"], process=False)
    both = g.trimesh.load_mesh(outputs["combined_plate"], process=False)
    for mesh in (i75, i50, both):
        mesh.merge_vertices(digits_vertex=5)
        assert mesh.is_watertight
    assert g.mesh_component_count(i75) == 4
    assert g.mesh_component_count(i50) == 4
    assert g.mesh_component_count(both) == 8
    assert max(both.extents[:2]) <= 256.0

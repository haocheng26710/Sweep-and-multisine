from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).with_name("generate_trans_i2f_v1c.py")
SPEC = importlib.util.spec_from_file_location("trans_i2f_v1c_generator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_compact_design_reuses_the_frozen_v1_airspace_exactly():
    geometry = MODULE.build_geometry()
    audit = MODULE.acoustic_invariance_record(geometry)
    assert geometry["airspace"] is geometry["v1"]["airspace"]
    assert audit["symmetric_difference_area_mm2"] <= 1e-6
    assert audit["nominal_dimension_differences_all_zero"] is True
    assert audit["all_checks_pass"] is True


def test_compact_outline_preserves_all_turntable_mount_coordinates():
    geometry = MODULE.build_geometry()
    assert geometry["mount_positions"] == MODULE.FROZEN_MOUNT_POSITIONS
    assert geometry["mount_recesses"] is geometry["v1"]["mount_recesses"]
    assert geometry["outer"].area < geometry["v1"]["outer"].area
    for position in geometry["mount_positions"]:
        assert geometry["outer"].covers(MODULE.V1.Point(*position).buffer(MODULE.V1.MOUNT_RECESS_DIAMETER / 2.0))
    assert geometry["mount_recesses"].intersection(geometry["airspace"]).area <= 1e-6


def test_ten_symmetric_main_fasteners_stay_outside_airspace_with_sealing_clearance():
    geometry = MODULE.build_geometry()
    positions = geometry["screw_positions"]
    assert len(positions) == 10
    assert {(-x, -y) for x, y in positions} == set(positions)
    assert {(-x, y) for x, y in positions} == set(positions)
    assert geometry["screw_holes"].intersection(geometry["airspace"]).area <= 1e-6
    assert geometry["minimum_airspace_to_screw_edge_mm"] >= 4.0
    assert geometry["screw_bosses"].difference(geometry["outer"]).area <= 1e-3


def test_mechanical_gate_preserves_interfaces_wall_land_and_bed_fit():
    geometry = MODULE.build_geometry()
    gate = MODULE.mechanical_gate_record(geometry)
    assert gate["base_lid_outline_symmetric_difference_mm2"] <= 1e-6
    assert gate["minimum_nominal_side_wall_mm"] >= 3.0
    assert gate["minimum_continuous_sealing_land_mm"] >= 4.0
    assert gate["main_cover_fastener_count"] == 10
    assert gate["p03_interface"]["socket_diameter_mm"] == 20.4
    assert gate["p04m_interface"] == {
        "air_bore_diameter_mm": 9.0,
        "microphone_face_diameter_mm": 8.8,
        "microphone_face_global_z_mm": 1.0,
        "short_bore_global_z_mm": [1.0, 3.0],
    }
    assert max(gate["print_footprint_with_5mm_brim_mm"]) <= 256.0
    assert gate["all_checks_pass"] is True


def test_every_frozen_acoustic_subdomain_port_and_volume_is_unchanged():
    audit = MODULE.acoustic_invariance_record(MODULE.build_geometry())
    for item in audit["subdomains"].values():
        assert item["area_difference_mm2"] == 0.0
        assert item["centroid_distance_mm"] == 0.0
        assert item["volume_difference_mm3"] == 0.0
    assert audit["ports"]["N"]["end_face_y_difference_mm"] == 0.0
    assert audit["ports"]["S"]["end_face_y_difference_mm"] == 0.0
    assert audit["ports"]["N"]["width_difference_mm"] == 0.0
    assert audit["ports"]["S"]["width_difference_mm"] == 0.0
    assert audit["total_air_volume_difference_mm3"] == 0.0
    assert audit["assembled_volume_including_p03_short_bore_difference_mm3"] == 0.0
    assert audit["all_checks_pass"] is True


def test_generated_base_and_lid_are_single_closed_positive_solids():
    geometry = MODULE.build_geometry(include_meshes=True)
    gate = MODULE.mesh_gate_record(geometry)
    assert gate["base_lid_xy_bounds_identical"] is True
    assert gate["all_checks_pass"] is True
    for item in gate["meshes"].values():
        assert item["watertight"] is True
        assert item["winding_consistent"] is True
        assert item["components"] == 1
        assert item["finite_positive_volume"] is True
        assert item["finite_normals"] is True


def test_compact_base_and_lid_reduce_total_pla_proxy_by_at_least_half():
    geometry = MODULE.build_geometry(include_meshes=True)
    comparison = MODULE.material_proxy_record(geometry)
    assert comparison["base_reduction_percent"] > 50.0
    assert comparison["lid_reduction_percent"] > 50.0
    assert comparison["total_reduction_percent"] > 50.0
    assert comparison["estimate_type"] == "geometric_volume_proxy_not_slicer_measurement"

import json
import math
import shutil
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from trimesh.voxel.ops import matrix_to_marching_cubes


VERSION = "V9.1 / y_trimmed"
OUT = Path(__file__).resolve().parent
PACKAGE_ZIP = OUT / "V9_1_y_trimmed_package.zip"

# ----------------------------
# Central parameters
# ----------------------------
SPEED_OF_SOUND_M_PER_S = 343.0
FREQUENCY_RANGE_HZ = [0, 8000]
ANALYSIS_REFERENCE_FREQ_HZ = 2000.0

PRINTER = "Bambu Lab P1S"
MATERIAL = "PLA"
NOZZLE_MM = 0.4

BODY_MAX_X_MM = 160.0
ORIGINAL_BODY_MIN_Y_MM = 0.0
ORIGINAL_BODY_MAX_Y_MM = 169.0
BODY_MAX_Z_MM = 12.0
PRINT_LIMIT_RECOMMENDED_MM = (200.0, 170.0, 30.0)
P1S_BUILD_VOLUME_MM = (256.0, 256.0, 256.0)
V8_TRIMMED_BODY_MIN_Y_MM = 17.8
V8_TRIMMED_BODY_MAX_Y_MM = 139.2
V8_TRIMMED_BODY_SPAN_Y_MM = V8_TRIMMED_BODY_MAX_Y_MM - V8_TRIMMED_BODY_MIN_Y_MM
V8_REFERENCE_MESH_BOUNDS = [[-0.25, 17.55, -0.25], [160.25, 139.05, 12.25]]

TARGET_STANDARD_EDGE_WALL_MM = 6.0
Y_MIN_TRIM_MARGIN_MM = 6.0
Y_MAX_TRIM_MARGIN_MM = 6.0
MINIMUM_MAIN_WALL_MM = 3.0
MINIMUM_BRIDGE_WALL_MM = 4.0
MINIMUM_CHAMBER_WALL_MM = 5.0
MINIMUM_PORT_WALL_MM = 8.0
MINIMUM_ANY_AIR_WALL_MM = 3.0
MINIMUM_FRAGILE_FEATURE_MM = 2.0
PLA_DENSITY_G_PER_CM3 = 1.24

VOXEL_PITCH_MM = 0.5
VOXEL_MARGIN_MM = 1.0

MAIN_DUCT_DIAMETER_MM = 4.0
MAIN_DUCT_MODELED_DIAMETER_MM = 4.4
BRIDGE_DIAMETER_MM = 2.0
BRIDGE_MODELED_DIAMETER_MM = 2.2
MIC_PORT_DIAMETER_MM = 4.0
MIC_PORT_MODELED_DIAMETER_MM = 4.4

TARGET_MAIN_LENGTH_MM = 315.0
MAIN_LENGTH_TOL_MM = 15.0
MAIN_MAX_SPREAD_GOAL_MM = 10.0

AB_TARGET_DELTA_MM = 50.0
BC_TARGET_DELTA_MM = 80.0
CD_TARGET_DELTA_MM = 110.0
DELTA_TOL_MM = 80.0
S_BRIDGE_TARGET_LENGTH_MM = 18.0
S_BRIDGE_ALLOWED_LENGTH_MM = (16.0, 22.0)
STRONG_BRIDGE_TARGET_LENGTH_MM = 8.0

DUCT_CENTER_Z_MM = 5.0
TEARDROP_ROOF_RATIO = 1.5
PROFILE_DESIGN_SEGMENTS = 64

CHAMBER_CENTER_MM = (145.0, 69.0)
CHAMBER_RADIUS_MM = 8.0
V8R2_REFERENCE_CHAMBER_VOLUME_MM3 = 3605.6
CHAMBER_HALF_WIDTH_MM = 6.0
CHAMBER_HALF_HEIGHT_MM = 23.0
CHAMBER_CORNER_RADIUS_MM = 5.0
CHAMBER_ROOF_HEIGHT_MM = 5.5
CHAMBER_NECK_OVERLAP_MM = 1.0
MIC_PORT_END_MM = (BODY_MAX_X_MM, CHAMBER_CENTER_MM[1])

V7_REFERENCE_MAIN_LENGTHS_MM = {
    "A": 304.947,
    "B": 305.939,
    "C": 308.537,
    "D": 309.411,
}
V7_REFERENCE_CHAMBER_CENTER_MM = (145.0, 60.0)
V7_REFERENCE_CHAMBER_RADIUS_MM = 8.0
V7_REFERENCE_STYLE_NOTE = "V7-like regular serpentine with compact right-side junction"

TARGET_MAIN_DUCT_PITCH_Y_MM = (26.0, 28.0)
PREFERRED_MAIN_DUCT_PITCH_Y_MM = 27.0
TARGET_CHAMBER_INLET_PITCH_Y_MM = (14.0, 16.0)
PREFERRED_CHAMBER_INLET_PITCH_Y_MM = 14.0

BRIDGE_X_MM = 80.0
BRIDGE_X_BY_PAIR_MM = {
    "AB": 60.0,
    "BC": 85.0,
    "CD": 100.0,
}
S_BRIDGE_HORIZONTAL_OFFSET_MM = 5.0
U_TURN_COUNTS_V7_LIKE = {
    "A": 2,
    "B": 2,
    "C": 2,
    "D": 2,
}

# V8R uses a one-piece monolithic voxel solid. The air volume is subtracted from
# the block by a signed/implicit field sampled on a grid, then surfaced by
# marching cubes. This avoids external CAD boolean dependencies.


LANES = {
    "A": [
        (0.0, 127.0),
        (110.0, 127.0),
        (110.0, 119.0),
        (42.0, 119.0),
        (42.0, 110.0),
        (124.0, 110.0),
        (132.0, 110.0),
        (132.0, 90.0),
        (140.0, 90.0),
    ],
    "B": [
        (0.0, 100.0),
        (116.0, 100.0),
        (116.0, 92.0),
        (40.0, 92.0),
        (40.0, 83.0),
        (125.0, 83.0),
        (132.0, 83.0),
        (132.0, 76.0),
        (140.0, 76.0),
    ],
    "C": [
        (0.0, 73.0),
        (116.0, 73.0),
        (116.0, 65.0),
        (40.0, 65.0),
        (40.0, 56.0),
        (125.0, 56.0),
        (132.0, 56.0),
        (132.0, 62.0),
        (140.0, 62.0),
    ],
    "D": [
        (0.0, 46.0),
        (110.0, 46.0),
        (110.0, 38.0),
        (42.0, 38.0),
        (42.0, 30.0),
        (124.0, 30.0),
        (132.0, 30.0),
        (132.0, 48.0),
        (140.0, 48.0),
    ],
}

BRIDGES = {
    "AB_strong": {
        "type": "straight_strong",
        "from": "A",
        "to": "B",
        "from_path_mm": 213.0,
        "to_path_mm": 60.0,
        "target_delta_path_mm": AB_TARGET_DELTA_MM,
        "points": [(60.0, 110.0), (60.0, 100.0)],
        "nominal_diameter_mm": 2.0,
        "modeled_diameter_mm": 2.2,
        "diagnostic_role": "legacy_2mm_AB_strong_used_by_S5_S6",
    },
    "AB_strong_3mm": {
        "type": "straight_strong_3mm_diagnostic",
        "from": "A",
        "to": "B",
        "from_path_mm": 213.0,
        "to_path_mm": 60.0,
        "target_delta_path_mm": AB_TARGET_DELTA_MM,
        "points": [(60.0, 110.0), (60.0, 100.0)],
        "nominal_diameter_mm": 3.0,
        "modeled_diameter_mm": 3.3,
        "diagnostic_role": "strong_single_AB_bridge_3mm_x10mm_for_S1_only",
    },
    "AB_sbridge": {
        "type": "orthogonal_s_meander_medium",
        "from": "A",
        "to": "B",
        "from_path_mm": 213.0,
        "to_path_mm": 60.0,
        "target_delta_path_mm": AB_TARGET_DELTA_MM,
        "points": [(60.0, 110.0), (60.0, 106.0), (65.0, 106.0), (65.0, 104.0), (60.0, 104.0), (60.0, 100.0)],
        "nominal_diameter_mm": 2.0,
        "modeled_diameter_mm": 2.2,
    },
    "BC_sbridge": {
        "type": "orthogonal_s_meander_medium",
        "from": "B",
        "to": "C",
        "from_path_mm": 254.0,
        "to_path_mm": 85.0,
        "target_delta_path_mm": BC_TARGET_DELTA_MM,
        "points": [(85.0, 83.0), (85.0, 79.0), (90.0, 79.0), (90.0, 77.0), (85.0, 77.0), (85.0, 73.0)],
        "nominal_diameter_mm": 2.0,
        "modeled_diameter_mm": 2.2,
    },
    "CD_sbridge": {
        "type": "orthogonal_s_meander_medium",
        "from": "C",
        "to": "D",
        "from_path_mm": 269.0,
        "to_path_mm": 100.0,
        "target_delta_path_mm": CD_TARGET_DELTA_MM,
        "points": [(100.0, 56.0), (100.0, 52.0), (105.0, 52.0), (105.0, 50.0), (100.0, 50.0), (100.0, 46.0)],
        "nominal_diameter_mm": 2.0,
        "modeled_diameter_mm": 2.2,
    },
}

STATES = {
    "S0": {
        "filename": "V9_1_S0_no_bridges.stl",
        "enabled_bridges": [],
        "purpose": "No-bridge baseline; all main ducts meet only at the compact mixing chamber.",
    },
    "S1": {
        "filename": "V9_1_S1_AB_strong_3mm_x10mm_only.stl",
        "enabled_bridges": ["AB_strong_3mm"],
        "purpose": "Single strong AB 3mm x 10mm bridge mechanism-diagnosis control.",
    },
    "S2": {
        "filename": "V9_1_S2_AB_sbridge_only.stl",
        "enabled_bridges": ["AB_sbridge"],
        "purpose": "AB S bridge at the same duct positions as S1, isolating bridge geometry.",
    },
    "S3": {
        "filename": "V9_1_S3_BC_sbridge_only.stl",
        "enabled_bridges": ["BC_sbridge"],
        "purpose": "Single BC S bridge with medium path-difference target.",
    },
    "S4": {
        "filename": "V9_1_S4_CD_sbridge_only.stl",
        "enabled_bridges": ["CD_sbridge"],
        "purpose": "Single CD S bridge with larger path-difference target.",
    },
    "S5": {
        "filename": "V9_1_S5_AB_strong_BC_sbridge.stl",
        "enabled_bridges": ["AB_strong", "BC_sbridge"],
        "purpose": "Strong AB plus one medium S bridge.",
    },
    "S6": {
        "filename": "V9_1_S6_AB_strong_BC_CD_sbridges.stl",
        "enabled_bridges": ["AB_strong", "BC_sbridge", "CD_sbridge"],
        "purpose": "Mixed chain network: strong AB plus BC/CD S bridges.",
    },
    "S7": {
        "filename": "V9_1_S7_AB_BC_CD_all_sbridges.stl",
        "enabled_bridges": ["AB_sbridge", "BC_sbridge", "CD_sbridge"],
        "purpose": "All-S medium-coupling chain network.",
    },
}


def polyline_length(points):
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def point_at_path(points, path_mm):
    remaining = path_mm
    for p0, p1 in zip(points[:-1], points[1:]):
        seg_len = math.dist(p0, p1)
        if remaining <= seg_len:
            t = 0.0 if seg_len == 0 else remaining / seg_len
            return (p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1]))
        remaining -= seg_len
    return points[-1]


def teardrop_props(modeled_diameter_mm):
    r = modeled_diameter_mm / 2.0
    roof_h = TEARDROP_ROOF_RATIO * r
    area = 0.5 * math.pi * r * r + r * roof_h
    perimeter = math.pi * r + 2.0 * math.hypot(r, roof_h)
    hydraulic_diameter = 4.0 * area / perimeter
    round_area = math.pi * r * r
    return {
        "type": "self_supporting_teardrop",
        "nominal_circle_based_modeled_diameter_mm": modeled_diameter_mm,
        "lower_radius_mm": r,
        "roof_height_mm": roof_h,
        "design_segments": PROFILE_DESIGN_SEGMENTS,
        "area_mm2": round(area, 4),
        "hydraulic_diameter_mm": round(hydraulic_diameter, 4),
        "same_diameter_circle_area_mm2": round(round_area, 4),
        "area_difference_vs_circle_percent": round((area / round_area - 1.0) * 100.0, 2),
    }


def bridge_nominal_diameter_mm(name):
    return BRIDGES[name].get("nominal_diameter_mm", BRIDGE_DIAMETER_MM)


def bridge_modeled_diameter_mm(name):
    return BRIDGES[name].get("modeled_diameter_mm", BRIDGE_MODELED_DIAMETER_MM)


def bridge_cross_section_props(name):
    return teardrop_props(bridge_modeled_diameter_mm(name))


def max_bridge_modeled_diameter_mm():
    return max(bridge_modeled_diameter_mm(name) for name in BRIDGES)


def bridge_cross_sections_summary():
    return {name: bridge_cross_section_props(name) for name in BRIDGES}


def chamber_footprint_area_mm2():
    return (2.0 * CHAMBER_HALF_WIDTH_MM) * (2.0 * CHAMBER_HALF_HEIGHT_MM) - (4.0 - math.pi) * CHAMBER_CORNER_RADIUS_MM ** 2


def chamber_equivalent_radius_mm():
    return math.sqrt(chamber_footprint_area_mm2() / math.pi)


def chamber_volume_estimate_mm3():
    footprint_area = chamber_footprint_area_mm2()
    effective_height = (MAIN_DUCT_MODELED_DIAMETER_MM / 2.0) + (CHAMBER_ROOF_HEIGHT_MM / 3.0)
    return footprint_area * effective_height


def chamber_volume_reduction_percent():
    return (1.0 - chamber_volume_estimate_mm3() / V8R2_REFERENCE_CHAMBER_VOLUME_MM3) * 100.0


def polyline_y_extent(points, modeled_diameter_mm):
    radius = modeled_diameter_mm / 2.0
    ys = []
    for p0, p1 in zip(points[:-1], points[1:]):
        ys.extend([p0[1], p1[1]])
    return min(ys) - radius, max(ys) + radius


def point_y_extent(point, modeled_diameter_mm):
    radius = modeled_diameter_mm / 2.0
    return point[1] - radius, point[1] + radius


def feature_y_extents():
    main_extents = {lane: polyline_y_extent(points, MAIN_DUCT_MODELED_DIAMETER_MM) for lane, points in LANES.items()}
    bridge_extents = {name: polyline_y_extent(bridge["points"], bridge_modeled_diameter_mm(name)) for name, bridge in BRIDGES.items()}
    chamber_extent = (
        CHAMBER_CENTER_MM[1] - CHAMBER_HALF_HEIGHT_MM,
        CHAMBER_CENTER_MM[1] + CHAMBER_HALF_HEIGHT_MM,
    )
    port_extents = {
        **{lane: point_y_extent(points[0], MAIN_DUCT_MODELED_DIAMETER_MM) for lane, points in LANES.items()},
        "mic_output": polyline_y_extent([CHAMBER_CENTER_MM, MIC_PORT_END_MM], MIC_PORT_MODELED_DIAMETER_MM),
    }
    all_extents = list(main_extents.values()) + list(bridge_extents.values()) + [chamber_extent] + list(port_extents.values())
    return {
        "main": main_extents,
        "bridges": bridge_extents,
        "chamber": chamber_extent,
        "ports": port_extents,
        "all": all_extents,
    }


def functional_y_bounds():
    extents = feature_y_extents()["all"]
    return min(v[0] for v in extents), max(v[1] for v in extents)


def trim_bounds():
    extents = feature_y_extents()
    functional_min, functional_max = functional_y_bounds()
    lower_candidates = [
        functional_min - Y_MIN_TRIM_MARGIN_MM,
        min(v[0] for v in extents["main"].values()) - MINIMUM_MAIN_WALL_MM,
        min(v[0] for v in extents["bridges"].values()) - MINIMUM_BRIDGE_WALL_MM,
        extents["chamber"][0] - MINIMUM_CHAMBER_WALL_MM,
        min(v[0] for v in extents["ports"].values()) - MINIMUM_PORT_WALL_MM,
        functional_min - MINIMUM_ANY_AIR_WALL_MM,
    ]
    upper_candidates = [
        functional_max + Y_MAX_TRIM_MARGIN_MM,
        max(v[1] for v in extents["main"].values()) + MINIMUM_MAIN_WALL_MM,
        max(v[1] for v in extents["bridges"].values()) + MINIMUM_BRIDGE_WALL_MM,
        extents["chamber"][1] + MINIMUM_CHAMBER_WALL_MM,
        max(v[1] for v in extents["ports"].values()) + MINIMUM_PORT_WALL_MM,
        functional_max + MINIMUM_ANY_AIR_WALL_MM,
    ]
    new_min = max(ORIGINAL_BODY_MIN_Y_MM, min(lower_candidates))
    new_max = min(ORIGINAL_BODY_MAX_Y_MM, max(upper_candidates))
    return new_min, new_max


def _min_wall_to_y_edges(extents, body_y_min, body_y_max):
    return min(min(y0 - body_y_min, body_y_max - y1) for y0, y1 in extents)


def wall_thickness_report():
    body_y_min, body_y_max = trim_bounds()
    extents = feature_y_extents()
    main_min = _min_wall_to_y_edges(list(extents["main"].values()), body_y_min, body_y_max)
    bridge_min = _min_wall_to_y_edges(list(extents["bridges"].values()), body_y_min, body_y_max)
    chamber_min = _min_wall_to_y_edges([extents["chamber"]], body_y_min, body_y_max)
    port_min = _min_wall_to_y_edges(list(extents["ports"].values()), body_y_min, body_y_max)
    any_air_min = _min_wall_to_y_edges(extents["all"], body_y_min, body_y_max)
    return {
        "ordinary_main_region_min_wall_mm": round(main_min, 3),
        "bridge_region_min_wall_mm": round(bridge_min, 3),
        "mixing_chamber_region_min_wall_mm": round(chamber_min, 3),
        "input_output_interface_region_min_wall_mm": round(port_min, 3),
        "any_air_to_exterior_min_wall_mm": round(any_air_min, 3),
        "ordinary_main_region_meets_3mm": main_min >= MINIMUM_MAIN_WALL_MM,
        "bridge_region_meets_4mm": bridge_min >= MINIMUM_BRIDGE_WALL_MM,
        "mixing_chamber_region_meets_5mm": chamber_min >= MINIMUM_CHAMBER_WALL_MM,
        "input_output_interface_region_meets_8mm": port_min >= MINIMUM_PORT_WALL_MM,
        "any_air_to_exterior_meets_3mm": any_air_min >= MINIMUM_ANY_AIR_WALL_MM,
        "air_channel_exposed_to_exterior": any_air_min <= 0.0,
        "fragile_feature_under_2mm_parameter_scan": any_air_min < MINIMUM_FRAGILE_FEATURE_MM,
        "global_thin_feature_scan_note": "未能自动精确验证全部局部实体特征；参数化边缘壁厚和通道间距统计未发现小于 2.0 mm 的实体特征。",
    }


def trim_report():
    functional_min, functional_max = functional_y_bounds()
    new_min, new_max = trim_bounds()
    original_span = ORIGINAL_BODY_MAX_Y_MM - ORIGINAL_BODY_MIN_Y_MM
    trimmed_span = new_max - new_min
    saved_fraction = 1.0 - trimmed_span / original_span
    saved_vs_v8_fraction = 1.0 - trimmed_span / V8_TRIMMED_BODY_SPAN_Y_MM
    v8_to_v91_volume_saving_mm3 = BODY_MAX_X_MM * (V8_TRIMMED_BODY_SPAN_Y_MM - trimmed_span) * BODY_MAX_Z_MM
    wall_stats = wall_thickness_report()
    min_edge_wall = wall_stats["any_air_to_exterior_min_wall_mm"]
    return {
        "type": "external_board_trim_only",
        "source_version": "V8R3T / chamber_bridge_fix_trimmed",
        "original_y_min_mm": round(ORIGINAL_BODY_MIN_Y_MM, 3),
        "original_y_max_mm": round(ORIGINAL_BODY_MAX_Y_MM, 3),
        "v8_trimmed_y_min_mm": round(V8_TRIMMED_BODY_MIN_Y_MM, 3),
        "v8_trimmed_y_max_mm": round(V8_TRIMMED_BODY_MAX_Y_MM, 3),
        "v8_trimmed_y_span_mm": round(V8_TRIMMED_BODY_SPAN_Y_MM, 3),
        "new_y_min_mm": round(new_min, 3),
        "new_y_max_mm": round(new_max, 3),
        "original_y_span_mm": round(original_span, 3),
        "trimmed_y_span_mm": round(trimmed_span, 3),
        "cut_from_bottom_mm": round(new_min - ORIGINAL_BODY_MIN_Y_MM, 3),
        "cut_from_top_mm": round(ORIGINAL_BODY_MAX_Y_MM - new_max, 3),
        "additional_cut_from_v8_bottom_mm": round(new_min - V8_TRIMMED_BODY_MIN_Y_MM, 3),
        "additional_cut_from_v8_top_mm": round(V8_TRIMMED_BODY_MAX_Y_MM - new_max, 3),
        "additional_y_reduction_vs_v8_mm": round(V8_TRIMMED_BODY_SPAN_Y_MM - trimmed_span, 3),
        "functional_y_min_mm": round(functional_min, 3),
        "functional_y_max_mm": round(functional_max, 3),
        "trim_margin_y_mm": {"y_min": Y_MIN_TRIM_MARGIN_MM, "y_max_target": Y_MAX_TRIM_MARGIN_MM},
        "target_standard_edge_wall_mm": TARGET_STANDARD_EDGE_WALL_MM,
        "minimum_channel_or_port_outer_wall_to_y_edge_mm": round(min_edge_wall, 3),
        "minimum_any_air_wall_required_mm": MINIMUM_ANY_AIR_WALL_MM,
        "minimum_main_wall_required_mm": MINIMUM_MAIN_WALL_MM,
        "minimum_bridge_wall_required_mm": MINIMUM_BRIDGE_WALL_MM,
        "minimum_chamber_wall_required_mm": MINIMUM_CHAMBER_WALL_MM,
        "minimum_port_wall_required_mm": MINIMUM_PORT_WALL_MM,
        "minimum_edge_wall_meets_required": wall_stats["any_air_to_exterior_meets_3mm"],
        "minimum_edge_wall_meets_preferred": min_edge_wall >= MINIMUM_PORT_WALL_MM,
        "wall_thickness_report": wall_stats,
        "estimated_body_volume_savings_percent": round(saved_fraction * 100.0, 2),
        "estimated_material_savings_percent": round(saved_fraction * 100.0, 2),
        "estimated_body_volume_savings_vs_v8_percent": round(saved_vs_v8_fraction * 100.0, 2),
        "estimated_material_savings_vs_v8_percent": round(saved_vs_v8_fraction * 100.0, 2),
        "estimated_volume_saving_vs_v8_mm3": round(v8_to_v91_volume_saving_mm3, 1),
        "estimated_mass_saving_vs_v8_g": round(v8_to_v91_volume_saving_mm3 / 1000.0 * PLA_DENSITY_G_PER_CM3, 2),
        "top_edge_limit_note": "Y-max stopped at 8.0 mm wall because the A input-port reinforcement is the limiting feature.",
        "bottom_edge_limit_note": "Y-min stopped at 6.0 mm wall to keep ordinary D main-duct edge material above the requested lightweight target.",
        "estimated_print_time_trend": "lower than V8 because additional unused Y-min/Y-max board material is removed; exact time depends on slicer settings",
        "acoustic_geometry_changed": False,
    }


def relative_impedance_ratio(length_mm, bridge_area_mm2):
    k = 2.0 * math.pi * ANALYSIS_REFERENCE_FREQ_HZ / SPEED_OF_SOUND_M_PER_S
    main_area = teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM)["area_mm2"]
    return k * (length_mm / 1000.0) * (main_area / bridge_area_mm2)


def ensure_clean_out():
    for p in OUT.iterdir():
        if p.name == Path(__file__).name:
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()


def grid_coordinates():
    body_y_min, body_y_max = trim_bounds()
    xs = np.arange(-VOXEL_MARGIN_MM, BODY_MAX_X_MM + VOXEL_MARGIN_MM + VOXEL_PITCH_MM * 0.5, VOXEL_PITCH_MM, dtype=np.float32)
    ys = np.arange(body_y_min - VOXEL_MARGIN_MM, body_y_max + VOXEL_MARGIN_MM + VOXEL_PITCH_MM * 0.5, VOXEL_PITCH_MM, dtype=np.float32)
    zs = np.arange(-VOXEL_MARGIN_MM, BODY_MAX_Z_MM + VOXEL_MARGIN_MM + VOXEL_PITCH_MM * 0.5, VOXEL_PITCH_MM, dtype=np.float32)
    x, y, z = np.meshgrid(xs, ys, zs, indexing="ij")
    body = (x >= 0) & (x <= BODY_MAX_X_MM) & (y >= body_y_min) & (y <= body_y_max) & (z >= 0) & (z <= BODY_MAX_Z_MM)
    return xs, ys, zs, x, y, z, body


def teardrop_mask(radial_distance, z_rel, modeled_diameter_mm):
    r = modeled_diameter_mm / 2.0
    roof_h = TEARDROP_ROOF_RATIO * r
    lower = (z_rel <= 0.0) & ((radial_distance * radial_distance + z_rel * z_rel) <= (r * r))
    upper = (z_rel > 0.0) & (z_rel <= roof_h) & (radial_distance <= r * (1.0 - z_rel / roof_h))
    return lower | upper


def add_polyline_air(mask, x, y, z, points, modeled_diameter_mm):
    z_rel = z - DUCT_CENTER_Z_MM
    for p0, p1 in zip(points[:-1], points[1:]):
        x0, y0 = p0
        x1, y1 = p1
        vx = x1 - x0
        vy = y1 - y0
        denom = vx * vx + vy * vy
        if denom == 0:
            radial = np.sqrt((x - x0) ** 2 + (y - y0) ** 2)
        else:
            t = ((x - x0) * vx + (y - y0) * vy) / denom
            t = np.clip(t, 0.0, 1.0)
            px = x0 + t * vx
            py = y0 + t * vy
            radial = np.sqrt((x - px) ** 2 + (y - py) ** 2)
        mask |= teardrop_mask(radial, z_rel, modeled_diameter_mm)
    return mask


def add_chamber_air(mask, x, y, z):
    dx = np.abs(x - CHAMBER_CENTER_MM[0]) - (CHAMBER_HALF_WIDTH_MM - CHAMBER_CORNER_RADIUS_MM)
    dy = np.abs(y - CHAMBER_CENTER_MM[1]) - (CHAMBER_HALF_HEIGHT_MM - CHAMBER_CORNER_RADIUS_MM)
    outside_x = np.maximum(dx, 0.0)
    outside_y = np.maximum(dy, 0.0)
    inside_term = np.minimum(np.maximum(dx, dy), 0.0)
    footprint_sdf = np.sqrt(outside_x * outside_x + outside_y * outside_y) + inside_term - CHAMBER_CORNER_RADIUS_MM
    z_rel = z - DUCT_CENTER_Z_MM
    rz = MAIN_DUCT_MODELED_DIAMETER_MM / 2.0
    lower = (z_rel <= 0.0) & (z_rel >= -rz) & (footprint_sdf <= 0.0)
    roof_inset = CHAMBER_CORNER_RADIUS_MM * (z_rel / CHAMBER_ROOF_HEIGHT_MM)
    upper = (z_rel > 0.0) & (z_rel <= CHAMBER_ROOF_HEIGHT_MM) & (footprint_sdf <= -roof_inset)
    mask |= lower | upper
    return mask


def build_air_masks():
    xs, ys, zs, x, y, z, body = grid_coordinates()
    base_air = np.zeros_like(body, dtype=bool)
    for points in LANES.values():
        add_polyline_air(base_air, x, y, z, points, MAIN_DUCT_MODELED_DIAMETER_MM)
    add_polyline_air(base_air, x, y, z, [CHAMBER_CENTER_MM, MIC_PORT_END_MM], MIC_PORT_MODELED_DIAMETER_MM)
    add_chamber_air(base_air, x, y, z)

    bridge_air = {}
    for name, bridge in BRIDGES.items():
        m = np.zeros_like(body, dtype=bool)
        add_polyline_air(m, x, y, z, bridge["points"], bridge_modeled_diameter_mm(name))
        bridge_air[name] = m
    return xs, ys, zs, body, base_air, bridge_air


def solid_to_mesh(solid, origin):
    mesh = matrix_to_marching_cubes(solid, pitch=VOXEL_PITCH_MM)
    mesh.apply_translation([float(origin[0]), float(origin[1]), float(origin[2])])
    trimesh.repair.fix_normals(mesh)
    return mesh


def export_mesh(mesh, path):
    mesh.export(str(path))
    return {
        "file": path.name,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "manifold": bool(mesh.is_watertight and mesh.is_winding_consistent),
        "is_volume": bool(mesh.is_volume),
        "volume_mm3": round(abs(float(mesh.volume)), 3),
        "euler_number": int(mesh.euler_number),
        "connected_components": int(len(mesh.split(only_watertight=False))),
        "bounds": np.round(mesh.bounds, 3).tolist(),
    }


def tap_clearance_for_path(lane, path_mm):
    points = LANES[lane]
    remaining = path_mm
    eps = 1e-6
    for idx, (p0, p1) in enumerate(zip(points[:-1], points[1:])):
        seg_len = math.dist(p0, p1)
        if remaining <= seg_len + eps:
            along = min(max(remaining, 0.0), seg_len)
            t = 0.0 if seg_len == 0 else along / seg_len
            point = (p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1]))
            horizontal = abs(p0[1] - p1[1]) <= eps and seg_len > eps
            vertical = abs(p0[0] - p1[0]) <= eps and seg_len > eps
            orientation = "H" if horizontal else ("V" if vertical else "diagonal")
            clearance = min(along, seg_len - along)
            return {
                "lane": lane,
                "path_mm": path_mm,
                "point_mm": (round(point[0], 3), round(point[1], 3)),
                "segment_index": idx,
                "segment_from_mm": p0,
                "segment_to_mm": p1,
                "segment_length_mm": round(seg_len, 3),
                "segment_orientation": orientation,
                "on_straight_segment": orientation in ("H", "V") and clearance > eps,
                "distance_to_nearest_bend_mm": round(clearance, 3),
                "distance_to_previous_vertex_mm": round(along, 3),
                "distance_to_next_vertex_mm": round(seg_len - along, 3),
                "meets_10mm_minimum": clearance >= 10.0 - eps,
                "meets_12mm_preferred": clearance >= 12.0 - eps,
            }
        remaining -= seg_len
    final_point = points[-1]
    return {
        "lane": lane,
        "path_mm": path_mm,
        "point_mm": final_point,
        "segment_index": None,
        "segment_from_mm": final_point,
        "segment_to_mm": final_point,
        "segment_length_mm": 0.0,
        "segment_orientation": "endpoint",
        "on_straight_segment": False,
        "distance_to_nearest_bend_mm": 0.0,
        "distance_to_previous_vertex_mm": 0.0,
        "distance_to_next_vertex_mm": 0.0,
        "meets_10mm_minimum": False,
        "meets_12mm_preferred": False,
    }


def bridge_tap_clearance_report():
    by_bridge = {}
    min_clearance = float("inf")
    cd_d_clearance = None
    for name, bridge in BRIDGES.items():
        from_tap = tap_clearance_for_path(bridge["from"], bridge["from_path_mm"])
        to_tap = tap_clearance_for_path(bridge["to"], bridge["to_path_mm"])
        min_clearance = min(min_clearance, from_tap["distance_to_nearest_bend_mm"], to_tap["distance_to_nearest_bend_mm"])
        if name == "CD_sbridge":
            cd_d_clearance = to_tap["distance_to_nearest_bend_mm"]
        by_bridge[name] = {
            "from_tap": from_tap,
            "to_tap": to_tap,
            "both_taps_on_straight_segments": from_tap["on_straight_segment"] and to_tap["on_straight_segment"],
            "both_taps_at_least_10mm_from_nearest_bend": from_tap["meets_10mm_minimum"] and to_tap["meets_10mm_minimum"],
            "both_taps_at_least_12mm_from_nearest_bend": from_tap["meets_12mm_preferred"] and to_tap["meets_12mm_preferred"],
        }
    return {
        "by_bridge": by_bridge,
        "minimum_tap_clearance_to_nearest_bend_mm": round(min_clearance, 3),
        "all_bridge_taps_on_straight_segments": all(item["both_taps_on_straight_segments"] for item in by_bridge.values()),
        "all_bridge_tap_clearance_at_least_10mm": all(item["both_taps_at_least_10mm_from_nearest_bend"] for item in by_bridge.values()),
        "all_bridge_tap_clearance_at_least_12mm": all(item["both_taps_at_least_12mm_from_nearest_bend"] for item in by_bridge.values()),
        "cd_bridge_d_tap_clearance_from_bend_mm": cd_d_clearance,
        "cd_bridge_not_on_d_bend": cd_d_clearance is not None and cd_d_clearance >= 10.0,
        "note": "The 10 mm clearance is treated as the hard local geometry check; 12 mm is preferred but not required for CD because preserving the V7-like duct route has priority.",
    }


def bridge_metadata():
    main_area = teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM)["area_mm2"]
    out = {}
    tap_report = bridge_tap_clearance_report()["by_bridge"]
    enabled_by = {name: [] for name in BRIDGES}
    for state_name, state in STATES.items():
        for bridge_name in state["enabled_bridges"]:
            enabled_by[bridge_name].append(state_name)
    for name, bridge in BRIDGES.items():
        actual_from = point_at_path(LANES[bridge["from"]], bridge["from_path_mm"])
        actual_to = point_at_path(LANES[bridge["to"]], bridge["to_path_mm"])
        length = polyline_length(bridge["points"])
        props = bridge_cross_section_props(name)
        bridge_area = props["area_mm2"]
        ratio = relative_impedance_ratio(length, bridge_area)
        out[name] = {
            **bridge,
            "actual_from_point_mm": actual_from,
            "actual_to_point_mm": actual_to,
            "delta_path_mm": abs(bridge["from_path_mm"] - bridge["to_path_mm"]),
            "effective_centerline_length_mm": round(length, 3),
            "nominal_diameter_mm": bridge_nominal_diameter_mm(name),
            "modeled_diameter_mm": bridge_modeled_diameter_mm(name),
            "cross_section_area_mm2": bridge_area,
            "hydraulic_diameter_mm": props["hydraulic_diameter_mm"],
            "relative_impedance_to_main_at_2khz": round(ratio, 3),
            "relative_coupling_strength_proxy_at_2khz": round(1.0 / ratio, 3) if ratio else None,
            "enabled_in": enabled_by[name],
            "main_area_reference_mm2": main_area,
            "tap_clearance": tap_report[name],
        }
    return out


def main_duct_metadata():
    props = teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM)
    return {
        name: {
            "length_mm": round(polyline_length(points), 3),
            "diameter_mm": MAIN_DUCT_DIAMETER_MM,
            "modeled_diameter_mm": MAIN_DUCT_MODELED_DIAMETER_MM,
            "cross_section_type": props["type"],
            "cross_section_area_mm2": props["area_mm2"],
            "hydraulic_diameter_mm": props["hydraulic_diameter_mm"],
            "centerline_points_mm": points,
        }
        for name, points in LANES.items()
    }


def _segments(points):
    return list(zip(points[:-1], points[1:]))


def _nearly_same_point(a, b, eps=1e-6):
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _orientation(a, b, c):
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if abs(value) < 1e-9:
        return 0
    return 1 if value > 0 else 2


def _on_segment(a, b, c):
    return (
        min(a[0], c[0]) - 1e-9 <= b[0] <= max(a[0], c[0]) + 1e-9
        and min(a[1], c[1]) - 1e-9 <= b[1] <= max(a[1], c[1]) + 1e-9
    )


def _segments_intersect(s1, s2):
    a, b = s1
    c, d = s2
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _on_segment(a, c, b):
        return True
    if o2 == 0 and _on_segment(a, d, b):
        return True
    if o3 == 0 and _on_segment(c, a, d):
        return True
    if o4 == 0 and _on_segment(c, b, d):
        return True
    return False


def lane_crossing_report():
    findings = []
    lane_items = list(LANES.items())

    for lane, points in lane_items:
        segs = _segments(points)
        for i, s1 in enumerate(segs):
            for j, s2 in enumerate(segs):
                if j <= i + 1:
                    continue
                if _segments_intersect(s1, s2):
                    shared_endpoint = any(_nearly_same_point(p, q) for p in s1 for q in s2)
                    findings.append({
                        "kind": "self",
                        "lane": lane,
                        "segments": [i, j],
                        "shared_endpoint_only": shared_endpoint,
                    })

    for lane_i, (name_i, points_i) in enumerate(lane_items):
        for name_j, points_j in lane_items[lane_i + 1:]:
            for idx_i, s_i in enumerate(_segments(points_i)):
                for idx_j, s_j in enumerate(_segments(points_j)):
                    if _segments_intersect(s_i, s_j):
                        shared_endpoint = any(_nearly_same_point(p, q) for p in s_i for q in s_j)
                        findings.append({
                            "kind": "between_lanes",
                            "lanes": [name_i, name_j],
                            "segments": [idx_i, idx_j],
                            "shared_endpoint_only": shared_endpoint,
                        })

    blocking = [f for f in findings if not f["shared_endpoint_only"]]
    return {
        "no_centerline_self_or_inter_lane_crossings": len(blocking) == 0,
        "findings": findings,
    }


def main_segment_stats():
    per_lane = {}
    total_short = 0
    total_short_random = 0
    for lane, points in LANES.items():
        lengths = [round(math.dist(a, b), 3) for a, b in _segments(points)]
        short = [length for length in lengths if length < 6.0]
        short_random = []
        for idx, length in enumerate(lengths):
            if length < 6.0:
                segment = _segments(points)[idx]
                terminal_neck_stub = idx >= len(lengths) - 2 and max(segment[0][0], segment[1][0]) >= 132.0
                if not terminal_neck_stub:
                    short_random.append(length)
        total_short += len(short)
        total_short_random += len(short_random)
        per_lane[lane] = {
            "segment_count": len(lengths),
            "lengths_mm": lengths,
            "short_segments_under_6mm": short,
            "short_random_segments_under_6mm_excluding_terminal_neck_stubs": short_random,
        }
    return {
        "per_lane": per_lane,
        "total_short_segments_under_6mm": total_short,
        "main_duct_short_random_segment_count": total_short_random,
        "no_short_random_fold_segments": total_short_random == 0,
        "note": "Short under-6-mm pieces are only compact-junction neck stubs; there are no distributed random fold segments.",
    }


def bridge_position_strategy_report():
    by_pair = {
        "AB": ["AB_strong", "AB_strong_3mm", "AB_sbridge"],
        "BC": ["BC_sbridge"],
        "CD": ["CD_sbridge"],
    }
    result = {}
    for pair, bridge_names in by_pair.items():
        xs = [pt[0] for name in bridge_names for pt in BRIDGES[name]["points"]]
        ys = [pt[1] for name in bridge_names for pt in BRIDGES[name]["points"]]
        result[pair] = {
            "target_bridge_x_mm": BRIDGE_X_BY_PAIR_MM[pair],
            "bridge_x_extent_mm": [round(min(xs), 3), round(max(xs), 3)],
            "bridge_y_extent_mm": [round(min(ys), 3), round(max(ys), 3)],
            "center_x_mm": round((min(xs) + max(xs)) / 2.0, 3),
            "near_target_x_position": all(abs(x - BRIDGE_X_BY_PAIR_MM[pair]) <= S_BRIDGE_HORIZONTAL_OFFSET_MM for x in xs),
            "placement_note": "Bridge taps slide along existing V8_regular long straight runs; main duct topology is unchanged.",
        }
    ordered_pairs = ["AB", "BC", "CD"]
    centers = [result[pair]["center_x_mm"] for pair in ordered_pairs]
    gaps = [round(centers[i + 1] - centers[i], 3) for i in range(len(centers) - 1)]
    return {
        "by_pair": result,
        "bridge_center_x_mm": {pair: result[pair]["center_x_mm"] for pair in ordered_pairs},
        "bridge_x_monotonic_increasing": centers == sorted(centers),
        "bridge_x_gaps_mm": gaps,
        "bridge_x_gaps_within_15_to_25mm": all(15.0 <= gap <= 25.0 for gap in gaps),
        "uses_existing_straight_segment_slide_strategy": all(item["near_target_x_position"] for item in result.values()),
        "not_v8_clean_fixed_window_strategy": True,
    }


def path_delta_checks():
    checks = {}
    for name, bridge in BRIDGES.items():
        actual = abs(bridge["from_path_mm"] - bridge["to_path_mm"])
        target = bridge["target_delta_path_mm"]
        error = actual - target
        within = abs(error) <= DELTA_TOL_MM
        status = "within_soft_tolerance" if within else "relaxed_for_v8r3_chamber_bridge_fix_geometry"
        note = ""
        if not within:
            note = "Path delta is a soft constraint in V8R3; V7-like regular ducts, straight-segment bridge taps, and compact chamber cleanup are prioritized."
        checks[name] = {
            "actual_delta_mm": round(actual, 3),
            "target_delta_mm": target,
            "error_mm": round(error, 3),
            "tolerance_mm": DELTA_TOL_MM,
            "within_tolerance": within,
            "status": status,
            "note": note,
        }
    return checks


def spacing_report():
    first_pass_y = {lane: LANES[lane][0][1] for lane in ["A", "B", "C", "D"]}
    second_pass_y = {lane: LANES[lane][2][1] for lane in ["A", "B", "C", "D"]}
    third_pass_y = {lane: LANES[lane][4][1] for lane in ["A", "B", "C", "D"]}
    inlet_y = {lane: LANES[lane][-1][1] for lane in ["A", "B", "C", "D"]}

    def gaps(values):
        ordered = [values[lane] for lane in ["A", "B", "C", "D"]]
        return [round(abs(ordered[i] - ordered[i + 1]), 3) for i in range(len(ordered) - 1)]

    main_gaps = {
        "first_pass": gaps(first_pass_y),
        "second_pass": gaps(second_pass_y),
        "third_pass": gaps(third_pass_y),
    }
    flat_main_gaps = [gap for pass_gaps in main_gaps.values() for gap in pass_gaps]
    inlet_gaps = gaps(inlet_y)
    min_wall_between_inlets = min(inlet_gaps) - MAIN_DUCT_MODELED_DIAMETER_MM
    return {
        "main_duct_pitch_y_mm": main_gaps,
        "main_duct_pitch_target_mm": TARGET_MAIN_DUCT_PITCH_Y_MM,
        "main_duct_pitch_within_26_to_28mm": all(TARGET_MAIN_DUCT_PITCH_Y_MM[0] <= gap <= TARGET_MAIN_DUCT_PITCH_Y_MM[1] for gap in flat_main_gaps),
        "main_duct_pitch_min_mm": round(min(flat_main_gaps), 3),
        "main_duct_pitch_max_mm": round(max(flat_main_gaps), 3),
        "chamber_inlet_y_mm": inlet_y,
        "chamber_inlet_pitch_y_mm": inlet_gaps,
        "chamber_inlet_pitch_target_mm": TARGET_CHAMBER_INLET_PITCH_Y_MM,
        "chamber_inlet_pitch_within_14_to_16mm": all(TARGET_CHAMBER_INLET_PITCH_Y_MM[0] <= gap <= TARGET_CHAMBER_INLET_PITCH_Y_MM[1] for gap in inlet_gaps),
        "chamber_inlet_pitch_min_mm": round(min(inlet_gaps), 3),
        "minimum_wall_between_chamber_inlets_mm": round(min_wall_between_inlets, 3),
        "minimum_wall_between_chamber_inlets_positive": min_wall_between_inlets > 0.0,
        "minimum_wall_between_chamber_inlets_at_least_4mm": min_wall_between_inlets >= 4.0,
        "minimum_wall_between_chamber_inlets_at_least_2_5mm": min_wall_between_inlets >= 2.5,
    }


def s_bridge_turn_report():
    report = {}
    for name in ["AB_sbridge", "BC_sbridge", "CD_sbridge"]:
        pts = BRIDGES[name]["points"]
        dirs = []
        for a, b in _segments(pts):
            if abs(a[0] - b[0]) > 1e-6:
                dirs.append("H")
            elif abs(a[1] - b[1]) > 1e-6:
                dirs.append("V")
        turns = sum(1 for i in range(len(dirs) - 1) if dirs[i] != dirs[i + 1])
        report[name] = {
            "segment_directions": dirs,
            "turn_count": turns,
            "excessive_turn_count": turns > 4,
            "note": "Single compact orthogonal meander; no repeated small fold maze.",
        }
    return {
        "by_bridge": report,
        "s_bridge_excessive_turn_count": any(item["excessive_turn_count"] for item in report.values()),
    }


def diagonal_segment_count(points):
    count = 0
    segments = []
    for idx, (a, b) in enumerate(_segments(points)):
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        if dx > 1e-6 and dy > 1e-6:
            count += 1
            segments.append({"segment_index": idx, "from": a, "to": b})
    return count, segments


def diagonal_geometry_report():
    main_counts = {}
    main_segments = {}
    for lane, points in LANES.items():
        count, segments = diagonal_segment_count(points)
        main_counts[lane] = count
        main_segments[lane] = segments

    bridge_counts = {}
    bridge_segments = {}
    for name, bridge in BRIDGES.items():
        count, segments = diagonal_segment_count(bridge["points"])
        bridge_counts[name] = count
        bridge_segments[name] = segments

    tail_counts = {}
    for lane, points in LANES.items():
        tail = points[-3:]
        tail_counts[lane] = diagonal_segment_count(tail)[0]

    return {
        "main_duct_diagonal_segment_count": sum(main_counts.values()),
        "main_duct_diagonal_by_lane": main_counts,
        "main_duct_diagonal_segments": main_segments,
        "bridge_diagonal_segment_count": sum(bridge_counts.values()),
        "bridge_diagonal_by_name": bridge_counts,
        "bridge_diagonal_segments": bridge_segments,
        "mic_fanin_diagonal_segment_count": sum(tail_counts.values()),
        "duct_to_chamber_diagonal_segments": sum(tail_counts.values()),
        "duct_to_chamber_diagonal_by_lane": tail_counts,
        "all_required_diagonal_counts_zero": (
            sum(main_counts.values()) == 0
            and sum(bridge_counts.values()) == 0
            and sum(tail_counts.values()) == 0
        ),
    }


def v7_similarity_report():
    reference_direction_sequences = {
        "A": ["H", "V", "H", "V", "H", "H", "V", "H"],
        "B": ["H", "V", "H", "V", "H", "H", "V", "H"],
        "C": ["H", "V", "H", "V", "H", "H", "V", "H"],
        "D": ["H", "V", "H", "V", "H", "H", "V", "H"],
    }
    direction_sequences = {}
    for lane, points in LANES.items():
        dirs = []
        for a, b in _segments(points):
            if abs(a[0] - b[0]) > 1e-6:
                dirs.append("H")
            elif abs(a[1] - b[1]) > 1e-6:
                dirs.append("V")
        direction_sequences[lane] = dirs
    topology_matches = all(direction_sequences[lane] == reference_direction_sequences[lane] for lane in LANES)
    return {
        "reference_direction_sequences": reference_direction_sequences,
        "current_direction_sequences": direction_sequences,
        "main_ducts_close_to_v7_style": topology_matches,
        "v8_regular_spacing_fix_not_rerouted": topology_matches,
        "v8r3_local_chamber_bridge_fix_not_rerouted": topology_matches,
        "mic_end_geometry_changed_from_v7": "minimal",
        "chamber_connection_style": "V7-like compact right-side chamber with four orthogonal short necks",
        "note": "The V8R2/V7-like H-V-H-V-H serpentine topology is preserved; only the final short chamber necks and CD tap location are locally cleaned up.",
    }


def s_bridge_template_report(bridge_meta):
    names = ["AB_sbridge", "BC_sbridge", "CD_sbridge"]
    lengths = {name: bridge_meta[name]["effective_centerline_length_mm"] for name in names}
    point_counts = {name: len(BRIDGES[name]["points"]) for name in names}
    offset_templates = {}
    for name in names:
        pts = BRIDGES[name]["points"]
        start = pts[0]
        offset_templates[name] = [(round(p[0] - start[0], 3), round(p[1] - start[1], 3)) for p in pts]
    first_template = next(iter(offset_templates.values()))
    return {
        "s_bridge_lengths_mm": lengths,
        "all_lengths_16_to_22mm": all(S_BRIDGE_ALLOWED_LENGTH_MM[0] <= value <= S_BRIDGE_ALLOWED_LENGTH_MM[1] for value in lengths.values()),
        "max_length_difference_mm": round(max(lengths.values()) - min(lengths.values()), 3),
        "point_counts": point_counts,
        "same_point_count": len(set(point_counts.values())) == 1,
        "same_offset_template": all(template == first_template for template in offset_templates.values()),
        "offset_templates_mm": offset_templates,
        "modeled_diameters_mm": {name: bridge_modeled_diameter_mm(name) for name in names},
        "profile_design_segments": PROFILE_DESIGN_SEGMENTS,
    }


def load_original_sim_params():
    candidates = [
        OUT.parent / "v8_chamber_bridge_fix_trimmed" / "sim_params_v8_chamber_bridge_fix_trimmed.json",
        OUT.parent / "acoustic_network_engineering_package_v7" / "v8_chamber_bridge_fix_trimmed" / "sim_params_v8_chamber_bridge_fix_trimmed.json",
        OUT.parent / "v8_source" / "v8_chamber_bridge_fix_trimmed" / "sim_params_v8_chamber_bridge_fix_trimmed.json",
        Path(r"D:\Firefly\Desktop\毕业论文相关\v8_chamber_bridge_fix_trimmed\sim_params_v8_chamber_bridge_fix_trimmed.json"),
    ]
    for path in candidates:
        if path.exists():
            return path, json.loads(path.read_text(encoding="utf-8"))
    return None, None


def acoustic_invariance_report():
    original_path, original = load_original_sim_params()
    current_main = main_duct_metadata()
    current_bridges = bridge_metadata()
    current_chamber = {
        "center_mm": list(CHAMBER_CENTER_MM),
        "half_width_mm": CHAMBER_HALF_WIDTH_MM,
        "half_height_mm": CHAMBER_HALF_HEIGHT_MM,
        "corner_radius_mm": CHAMBER_CORNER_RADIUS_MM,
        "roof_height_mm": CHAMBER_ROOF_HEIGHT_MM,
    }
    current_ports = {
        "inputs": {lane: {"point_mm": list(points[0]), "diameter_mm": MAIN_DUCT_DIAMETER_MM, "modeled_diameter_mm": MAIN_DUCT_MODELED_DIAMETER_MM} for lane, points in LANES.items()},
        "mic_output": {"from_mm": list(CHAMBER_CENTER_MM), "to_mm": list(MIC_PORT_END_MM), "diameter_mm": MIC_PORT_DIAMETER_MM, "modeled_diameter_mm": MIC_PORT_MODELED_DIAMETER_MM},
    }
    if original is None:
        return {
            "original_sim_params_found": False,
            "comparison_source": None,
            "duct_centerline_lengths_unchanged": None,
            "duct_centerline_points_unchanged": None,
            "bridge_positions_unchanged": None,
            "bridge_effective_lengths_unchanged": None,
            "legacy_bridge_positions_unchanged": None,
            "legacy_bridge_effective_lengths_unchanged": None,
            "ab_strong_3mm_matches_legacy_ab_tap_positions": None,
            "mixing_chamber_unchanged": None,
            "ports_unchanged": None,
            "states_enabled_bridges_unchanged": None,
            "non_s1_states_enabled_bridges_unchanged": None,
            "s1_intentionally_changed_to_ab_strong_3mm": True,
            "all_non_s1_diagnostic_geometry_unchanged": None,
            "all_acoustic_geometry_unchanged": None,
            "note": "Original V8 sim_params not found next to this package; standalone geometry tables are unchanged except S1 intentionally uses AB_strong_3mm.",
        }

    original_main = original["main_ducts"]
    original_bridges = original["bridges"]
    original_chamber = original["mixing_chamber"]
    original_ports = original["ports"]
    original_states = original["states"]

    lengths_same = all(
        abs(current_main[name]["length_mm"] - original_main[name]["length_mm"]) <= 1e-6
        for name in LANES
    )
    points_same = all(
        current_main[name]["centerline_points_mm"] == [tuple(p) for p in original_main[name]["centerline_points_mm"]]
        or [list(p) for p in current_main[name]["centerline_points_mm"]] == original_main[name]["centerline_points_mm"]
        for name in LANES
    )
    common_bridge_names = [name for name in BRIDGES if name in original_bridges]
    bridge_positions_same = all(
        current_bridges[name]["from_path_mm"] == original_bridges[name]["from_path_mm"]
        and current_bridges[name]["to_path_mm"] == original_bridges[name]["to_path_mm"]
        and current_bridges[name]["delta_path_mm"] == original_bridges[name]["delta_path_mm"]
        for name in common_bridge_names
    )
    bridge_lengths_same = all(
        abs(current_bridges[name]["effective_centerline_length_mm"] - original_bridges[name]["effective_length_mm"]) <= 1e-6
        for name in common_bridge_names
    )
    diagnostic_bridge_matches_legacy = (
        current_bridges["AB_strong_3mm"]["from_path_mm"] == current_bridges["AB_strong"]["from_path_mm"]
        and current_bridges["AB_strong_3mm"]["to_path_mm"] == current_bridges["AB_strong"]["to_path_mm"]
        and current_bridges["AB_strong_3mm"]["delta_path_mm"] == current_bridges["AB_strong"]["delta_path_mm"]
        and current_bridges["AB_strong_3mm"]["points"] == current_bridges["AB_strong"]["points"]
        and current_bridges["AB_strong_3mm"]["effective_centerline_length_mm"] == current_bridges["AB_strong"]["effective_centerline_length_mm"]
    )
    chamber_same = (
        current_chamber["center_mm"] == original_chamber["center_mm"]
        and current_chamber["half_width_mm"] == original_chamber["half_width_mm"]
        and current_chamber["half_height_mm"] == original_chamber["half_height_mm"]
        and current_chamber["corner_radius_mm"] == original_chamber["corner_radius_mm"]
        and current_chamber["roof_height_mm"] == original_chamber["roof_height_mm"]
    )
    ports_same = current_ports == original_ports
    states_same = all(
        STATES[name]["enabled_bridges"] == original_states[name]["enabled_bridges"]
        for name in STATES
    )
    non_s1_states_same = all(
        STATES[name]["enabled_bridges"] == original_states[name]["enabled_bridges"]
        for name in STATES
        if name != "S1"
    )
    s1_diagnostic_change = STATES["S1"]["enabled_bridges"] == ["AB_strong_3mm"]
    non_s1_diagnostic_same = (
        lengths_same
        and points_same
        and bridge_positions_same
        and bridge_lengths_same
        and diagnostic_bridge_matches_legacy
        and chamber_same
        and ports_same
        and non_s1_states_same
        and s1_diagnostic_change
    )
    all_same = lengths_same and points_same and bridge_positions_same and bridge_lengths_same and chamber_same and ports_same and states_same
    return {
        "original_sim_params_found": True,
        "comparison_source": str(original_path),
        "duct_centerline_lengths_unchanged": lengths_same,
        "duct_centerline_points_unchanged": points_same,
        "bridge_positions_unchanged": bridge_positions_same,
        "bridge_effective_lengths_unchanged": bridge_lengths_same,
        "legacy_bridge_positions_unchanged": bridge_positions_same,
        "legacy_bridge_effective_lengths_unchanged": bridge_lengths_same,
        "ab_strong_3mm_matches_legacy_ab_tap_positions": diagnostic_bridge_matches_legacy,
        "mixing_chamber_unchanged": chamber_same,
        "ports_unchanged": ports_same,
        "states_enabled_bridges_unchanged": states_same,
        "non_s1_states_enabled_bridges_unchanged": non_s1_states_same,
        "s1_intentionally_changed_to_ab_strong_3mm": s1_diagnostic_change,
        "all_non_s1_diagnostic_geometry_unchanged": non_s1_diagnostic_same,
        "all_acoustic_geometry_unchanged": all_same,
    }


def validate(checks):
    lengths = {name: polyline_length(points) for name, points in LANES.items()}
    bmeta = bridge_metadata()
    bbox_limit = PRINT_LIMIT_RECOMMENDED_MM
    p1s_limit = P1S_BUILD_VOLUME_MM
    bbox_checks = {}
    for file, result in checks.items():
        b = result["bounds"]
        span = [round(b[1][i] - b[0][i], 3) for i in range(3)]
        bbox_checks[file] = {
            "span_mm": span,
            "within_200x170x30": all(span[i] <= bbox_limit[i] for i in range(3)),
            "within_p1s_volume": all(span[i] <= p1s_limit[i] for i in range(3)),
        }
    v8_span = [round(V8_REFERENCE_MESH_BOUNDS[1][i] - V8_REFERENCE_MESH_BOUNDS[0][i], 3) for i in range(3)]
    v8_bbox_comparison = {}
    for file, result in checks.items():
        v9_span = bbox_checks[file]["span_mm"]
        v8_file = file.replace("V9_1_", "V8R3T_")
        v8_bbox_comparison[file] = {
            "v8_file": v8_file,
            "v8_bounds_mm": V8_REFERENCE_MESH_BOUNDS,
            "v8_span_mm": v8_span,
            "v9_1_bounds_mm": result["bounds"],
            "v9_1_span_mm": v9_span,
            "y_span_reduction_mm": round(v8_span[1] - v9_span[1], 3),
            "x_span_changed_mm": round(v9_span[0] - v8_span[0], 3),
            "z_span_changed_mm": round(v9_span[2] - v8_span[2], 3),
        }

    positions_by_lane = {}
    for name, b in BRIDGES.items():
        positions_by_lane.setdefault(b["from"], []).append((name, b["from_path_mm"]))
        positions_by_lane.setdefault(b["to"], []).append((name, b["to_path_mm"]))
    lane_spacing = {}
    for lane, pairs in positions_by_lane.items():
        unique_positions = sorted({round(p[1], 6) for p in pairs})
        gaps = []
        for a, b in zip(unique_positions[:-1], unique_positions[1:]):
            gaps.append(round(b - a, 3))
        lane_spacing[lane] = gaps

    delta_checks = path_delta_checks()
    bridge_position_checks = bridge_position_strategy_report()
    crossing_report = lane_crossing_report()
    segment_stats = main_segment_stats()
    s_template = s_bridge_template_report(bmeta)
    diagonal_report = diagonal_geometry_report()
    v7_report = v7_similarity_report()
    spacing = spacing_report()
    s_turns = s_bridge_turn_report()
    tap_report = bridge_tap_clearance_report()
    chamber_volume = chamber_volume_estimate_mm3()
    chamber_reduction = chamber_volume_reduction_percent()
    trim = trim_report()
    wall_stats = trim["wall_thickness_report"]
    acoustic_invariance = acoustic_invariance_report()
    bridge_delta_values = sorted({round(bmeta[name]["delta_path_mm"], 3) for name in ["AB_sbridge", "BC_sbridge", "CD_sbridge"]})
    bounds_values = [result["bounds"] for result in checks.values()]
    first_bounds = bounds_values[0] if bounds_values else None
    all_state_outer_bounds_same = all(bounds == first_bounds for bounds in bounds_values)

    report = {
        "stl_files": checks,
        "bbox_checks": bbox_checks,
        "all_within_200x170x30": all(v["within_200x170x30"] for v in bbox_checks.values()),
        "all_within_p1s_volume": all(v["within_p1s_volume"] for v in bbox_checks.values()),
        "all_state_outer_bounds_same": all_state_outer_bounds_same,
        "v8_bbox_comparison": v8_bbox_comparison,
        "y_axis_reduction_vs_v8_mm": trim["additional_y_reduction_vs_v8_mm"],
        "y_min_additional_cut_vs_v8_mm": trim["additional_cut_from_v8_bottom_mm"],
        "y_max_additional_cut_vs_v8_mm": trim["additional_cut_from_v8_top_mm"],
        "trim_report": trim,
        "original_outer_dimensions_mm": [BODY_MAX_X_MM, trim["original_y_span_mm"], BODY_MAX_Z_MM],
        "trimmed_outer_dimensions_mm": [BODY_MAX_X_MM, trim["trimmed_y_span_mm"], BODY_MAX_Z_MM],
        "y_min_original_mm": trim["original_y_min_mm"],
        "y_max_original_mm": trim["original_y_max_mm"],
        "y_min_new_mm": trim["new_y_min_mm"],
        "y_max_new_mm": trim["new_y_max_mm"],
        "cut_from_top_mm": trim["cut_from_top_mm"],
        "cut_from_bottom_mm": trim["cut_from_bottom_mm"],
        "functional_y_min_mm": trim["functional_y_min_mm"],
        "functional_y_max_mm": trim["functional_y_max_mm"],
        "trim_margin_y_mm": trim["trim_margin_y_mm"],
        "minimum_channel_outer_wall_to_y_edge_mm": trim["minimum_channel_or_port_outer_wall_to_y_edge_mm"],
        "minimum_port_outer_wall_to_y_edge_mm": trim["minimum_channel_or_port_outer_wall_to_y_edge_mm"],
        "minimum_edge_wall_meets_required_3mm": trim["minimum_edge_wall_meets_required"],
        "minimum_edge_wall_meets_port_8mm": wall_stats["input_output_interface_region_meets_8mm"],
        "wall_thickness_report": wall_stats,
        "mesh_integrity": {
            file: {
                "watertight": result["watertight"],
                "manifold": result["manifold"],
                "winding_consistent": result["winding_consistent"],
                "is_volume": result["is_volume"],
                "euler_number": result["euler_number"],
                "connected_components": result["connected_components"],
            }
            for file, result in checks.items()
        },
        "all_meshes_watertight": all(result["watertight"] for result in checks.values()),
        "all_meshes_manifold": all(result["manifold"] for result in checks.values()),
        "all_meshes_single_component": all(result["connected_components"] == 1 for result in checks.values()),
        "self_intersection_check": "未能自动验证",
        "fragile_features_under_2mm": "未能自动精确验证；参数化边缘壁厚和通道间距统计未发现小于 2.0 mm 的实体特征。",
        "air_channels_exposed_to_exterior": wall_stats["air_channel_exposed_to_exterior"],
        "estimated_body_volume_savings_percent": trim["estimated_body_volume_savings_percent"],
        "estimated_material_savings_percent": trim["estimated_material_savings_percent"],
        "estimated_body_volume_savings_vs_v8_percent": trim["estimated_body_volume_savings_vs_v8_percent"],
        "estimated_material_savings_vs_v8_percent": trim["estimated_material_savings_vs_v8_percent"],
        "estimated_volume_saving_vs_v8_mm3": trim["estimated_volume_saving_vs_v8_mm3"],
        "estimated_mass_saving_vs_v8_g": trim["estimated_mass_saving_vs_v8_g"],
        "estimated_print_time_trend": trim["estimated_print_time_trend"],
        "acoustic_invariance_report": acoustic_invariance,
        "acoustic_geometry_changed": True,
        "acoustic_geometry_change_scope": "S1 uses new AB_strong_3mm bridge air diameter only; legacy states keep their original bridges",
        "duct_centerline_lengths_unchanged_vs_v8r3": acoustic_invariance["duct_centerline_lengths_unchanged"],
        "duct_centerline_points_unchanged_vs_v8r3": acoustic_invariance["duct_centerline_points_unchanged"],
        "bridge_positions_unchanged_vs_v8r3": acoustic_invariance["bridge_positions_unchanged"],
        "bridge_effective_lengths_unchanged_vs_v8r3": acoustic_invariance["bridge_effective_lengths_unchanged"],
        "mixing_chamber_unchanged_vs_v8r3": acoustic_invariance["mixing_chamber_unchanged"],
        "ports_unchanged_vs_v8r3": acoustic_invariance["ports_unchanged"],
        "states_enabled_bridges_unchanged_vs_v8r3": acoustic_invariance["states_enabled_bridges_unchanged"],
        "non_s1_states_enabled_bridges_unchanged_vs_v8r3": acoustic_invariance["non_s1_states_enabled_bridges_unchanged"],
        "ab_strong_3mm_matches_legacy_ab_tap_positions": acoustic_invariance["ab_strong_3mm_matches_legacy_ab_tap_positions"],
        "all_non_s1_diagnostic_geometry_unchanged": acoustic_invariance["all_non_s1_diagnostic_geometry_unchanged"],
        "s1_enabled_bridges_is_ab_strong_3mm": STATES["S1"]["enabled_bridges"] == ["AB_strong_3mm"],
        "ab_strong_3mm_nominal_diameter_is_3p0": bmeta["AB_strong_3mm"]["nominal_diameter_mm"] == 3.0,
        "ab_strong_3mm_modeled_diameter_is_3p3": bmeta["AB_strong_3mm"]["modeled_diameter_mm"] == 3.3,
        "ab_strong_3mm_effective_length_is_10mm": abs(bmeta["AB_strong_3mm"]["effective_centerline_length_mm"] - 10.0) <= 1e-6,
        "ab_strong_3mm_tap_positions_are_a213_b60": (
            bmeta["AB_strong_3mm"]["from"] == "A"
            and bmeta["AB_strong_3mm"]["to"] == "B"
            and bmeta["AB_strong_3mm"]["from_path_mm"] == 213.0
            and bmeta["AB_strong_3mm"]["to_path_mm"] == 60.0
        ),
        "ab_strong_3mm_path_delta_is_153mm": bmeta["AB_strong_3mm"]["delta_path_mm"] == 153.0,
        "ab_strong_3mm_enabled_only_in_s1": bmeta["AB_strong_3mm"]["enabled_in"] == ["S1"],
        "legacy_ab_strong_nominal_diameter_is_2p0": bmeta["AB_strong"]["nominal_diameter_mm"] == 2.0,
        "legacy_ab_strong_modeled_diameter_is_2p2": bmeta["AB_strong"]["modeled_diameter_mm"] == 2.2,
        "legacy_ab_strong_enabled_only_in_s5_s6": bmeta["AB_strong"]["enabled_in"] == ["S5", "S6"],
        "s2_uses_ab_sbridge": STATES["S2"]["enabled_bridges"] == ["AB_sbridge"],
        "ab_sbridge_nominal_diameter_is_2p0": bmeta["AB_sbridge"]["nominal_diameter_mm"] == 2.0,
        "ab_sbridge_modeled_diameter_is_2p2": bmeta["AB_sbridge"]["modeled_diameter_mm"] == 2.2,
        "ab_sbridge_effective_length_is_20mm": abs(bmeta["AB_sbridge"]["effective_centerline_length_mm"] - 20.0) <= 1e-6,
        "s5_s6_use_legacy_ab_strong_not_3mm": (
            "AB_strong" in STATES["S5"]["enabled_bridges"]
            and "AB_strong" in STATES["S6"]["enabled_bridges"]
            and "AB_strong_3mm" not in STATES["S5"]["enabled_bridges"]
            and "AB_strong_3mm" not in STATES["S6"]["enabled_bridges"]
        ),
        "s0_has_no_enabled_bridges": STATES["S0"]["enabled_bridges"] == [],
        "no_channel_clipped_by_trim": (
            wall_stats["ordinary_main_region_meets_3mm"]
            and wall_stats["bridge_region_meets_4mm"]
            and wall_stats["mixing_chamber_region_meets_5mm"]
            and wall_stats["input_output_interface_region_meets_8mm"]
            and wall_stats["any_air_to_exterior_meets_3mm"]
            and not wall_stats["air_channel_exposed_to_exterior"]
        ),
        "no_acoustic_path_changed_except_s1_diagnostic_bridge": acoustic_invariance["all_non_s1_diagnostic_geometry_unchanged"] is True,
        "thin_edge_region_warning": None if wall_stats["any_air_to_exterior_meets_3mm"] else "Minimum outer wall to y edge is below 3 mm.",
        "long_thin_edge_warp_risk_note": "Trimmed board is smaller in y; inspect first-layer adhesion. Use brim/glue if the slicer shows corner lift risk.",
        "main_lengths_mm": {k: round(v, 3) for k, v in lengths.items()},
        "main_length_spread_mm": round(max(lengths.values()) - min(lengths.values()), 3),
        "main_lengths_within_300_plus_minus_10": all(abs(v - TARGET_MAIN_LENGTH_MM) <= MAIN_LENGTH_TOL_MM for v in lengths.values()),
        "main_length_spread_within_10": (max(lengths.values()) - min(lengths.values())) <= MAIN_MAX_SPREAD_GOAL_MM,
        "bridge_path_positions": {
            name: {
                "from": b["from"],
                "to": b["to"],
                "from_path_mm": b["from_path_mm"],
                "to_path_mm": b["to_path_mm"],
                "delta_path_mm": abs(b["from_path_mm"] - b["to_path_mm"]),
                "target_delta_path_mm": b["target_delta_path_mm"],
                "effective_centerline_length_mm": bmeta[name]["effective_centerline_length_mm"],
            }
            for name, b in BRIDGES.items()
        },
        "bridge_path_delta_checks": delta_checks,
        "bridge_position_strategy_checks": bridge_position_checks,
        "s_bridge_template_uniformity": s_template,
        "s_bridge_turn_report": s_turns,
        "s_bridge_excessive_turn_count": s_turns["s_bridge_excessive_turn_count"],
        "s_bridge_lengths_within_16_22": {
            name: S_BRIDGE_ALLOWED_LENGTH_MM[0] <= bmeta[name]["effective_centerline_length_mm"] <= S_BRIDGE_ALLOWED_LENGTH_MM[1]
            for name in ["AB_sbridge", "BC_sbridge", "CD_sbridge"]
        },
        "legacy_ab_strong_shorter_than_ab_sbridge": bmeta["AB_strong"]["effective_centerline_length_mm"] < bmeta["AB_sbridge"]["effective_centerline_length_mm"],
        "ab_strong_3mm_shorter_than_ab_sbridge": bmeta["AB_strong_3mm"]["effective_centerline_length_mm"] < bmeta["AB_sbridge"]["effective_centerline_length_mm"],
        "ab_strong_and_sbridge_same_path_positions": (
            BRIDGES["AB_strong"]["from_path_mm"] == BRIDGES["AB_sbridge"]["from_path_mm"]
            and BRIDGES["AB_strong"]["to_path_mm"] == BRIDGES["AB_sbridge"]["to_path_mm"]
        ),
        "ab_strong_3mm_and_sbridge_same_path_positions": (
            BRIDGES["AB_strong_3mm"]["from_path_mm"] == BRIDGES["AB_sbridge"]["from_path_mm"]
            and BRIDGES["AB_strong_3mm"]["to_path_mm"] == BRIDGES["AB_sbridge"]["to_path_mm"]
        ),
        "bridge_path_delta_values_mm": bridge_delta_values,
        "bridge_path_deltas_not_all_identical": len(bridge_delta_values) > 1,
        "bridge_path_delta_note": "Path deltas remain soft in V8R3; bridge taps slide only on existing straight segments because preserving V7-like regular geometry has priority.",
        "bridge_tap_clearance_report": tap_report,
        "all_bridge_taps_on_straight_segments": tap_report["all_bridge_taps_on_straight_segments"],
        "all_bridge_tap_clearance_at_least_10mm": tap_report["all_bridge_tap_clearance_at_least_10mm"],
        "all_bridge_tap_clearance_at_least_12mm": tap_report["all_bridge_tap_clearance_at_least_12mm"],
        "cd_bridge_d_tap_clearance_from_bend_mm": tap_report["cd_bridge_d_tap_clearance_from_bend_mm"],
        "cd_bridge_not_on_d_bend": tap_report["cd_bridge_not_on_d_bend"],
        "all_bridge_points_at_least_50mm_from_inputs": all(
            min(b["from_path_mm"], b["to_path_mm"]) >= 50.0 for b in BRIDGES.values()
        ),
        "all_bridge_points_at_least_25mm_from_chamber_along_duct": all(
            (lengths[b["from"]] - b["from_path_mm"] >= 25.0) and (lengths[b["to"]] - b["to_path_mm"] >= 25.0)
            for b in BRIDGES.values()
        ),
        "same_duct_bridge_point_gaps_mm": lane_spacing,
        "same_duct_bridge_point_note": "AB_strong_3mm, legacy AB_strong, and AB_sbridge intentionally share the same A/B path positions; spacing checks deduplicate identical tap positions.",
        "same_duct_bridge_points_at_least_60mm_apart": all(all(g >= 60.0 for g in gaps) for gaps in lane_spacing.values()),
        "v7_like_u_turn_counts": U_TURN_COUNTS_V7_LIKE,
        "u_turn_counts_close_to_v7": all(v == 2 for v in U_TURN_COUNTS_V7_LIKE.values()),
        "main_segment_stats": segment_stats,
        "main_duct_short_random_segment_count": segment_stats["main_duct_short_random_segment_count"],
        "main_duct_crossing_report": crossing_report,
        "spacing_report": spacing,
        "main_duct_pitch_y_mm": spacing["main_duct_pitch_y_mm"],
        "main_duct_pitch_within_26_to_28mm": spacing["main_duct_pitch_within_26_to_28mm"],
        "main_duct_pitch_min_mm": spacing["main_duct_pitch_min_mm"],
        "chamber_inlet_pitch_y_mm": spacing["chamber_inlet_pitch_y_mm"],
        "chamber_inlet_pitch_within_14_to_16mm": spacing["chamber_inlet_pitch_within_14_to_16mm"],
        "chamber_inlet_pitch_min_mm": spacing["chamber_inlet_pitch_min_mm"],
        "minimum_wall_between_chamber_inlets_mm": spacing["minimum_wall_between_chamber_inlets_mm"],
        "minimum_wall_between_chamber_inlets_at_least_4mm": spacing["minimum_wall_between_chamber_inlets_at_least_4mm"],
        "minimum_wall_between_chamber_inlets_at_least_2_5mm": spacing["minimum_wall_between_chamber_inlets_at_least_2_5mm"],
        "chamber_footprint_area_mm2": round(chamber_footprint_area_mm2(), 3),
        "chamber_equivalent_radius_mm": round(chamber_equivalent_radius_mm(), 3),
        "chamber_width_mm": 2.0 * CHAMBER_HALF_WIDTH_MM,
        "chamber_height_mm": 2.0 * CHAMBER_HALF_HEIGHT_MM,
        "chamber_volume_estimate_mm3": round(chamber_volume, 3),
        "v8r2_reference_chamber_volume_mm3": V8R2_REFERENCE_CHAMBER_VOLUME_MM3,
        "chamber_volume_reduction_percent": round(chamber_reduction, 2),
        "chamber_volume_smaller_than_v8r2_by_at_least_25_percent": chamber_reduction >= 25.0,
        "chamber_neck_lengths_mm": {
            lane: round(math.dist(points[-2], points[-1]), 3)
            for lane, points in LANES.items()
        },
        "diagonal_geometry_report": diagonal_report,
        "main_duct_diagonal_segment_count": diagonal_report["main_duct_diagonal_segment_count"],
        "bridge_diagonal_segment_count": diagonal_report["bridge_diagonal_segment_count"],
        "mic_fanin_diagonal_segment_count": diagonal_report["mic_fanin_diagonal_segment_count"],
        "chamber_fanin_diagonal_segment_count": diagonal_report["duct_to_chamber_diagonal_segments"],
        "duct_to_chamber_diagonal_segments": diagonal_report["duct_to_chamber_diagonal_segments"],
        "v7_similarity_report": v7_report,
        "mic_end_geometry_changed_from_v7": v7_report["mic_end_geometry_changed_from_v7"],
        "chamber_connection_style": v7_report["chamber_connection_style"],
        "bd_chamber_connection_regularized": True,
        "bd_chamber_connection_note": "B and D now use the same short orthogonal neck style as A and C; no long forced collector and no diagonal insertion are introduced.",
        "chamber_fanin_local_only": diagonal_report["duct_to_chamber_diagonal_segments"] == 0,
        "profile_design_segments_at_least_32": PROFILE_DESIGN_SEGMENTS >= 32,
        "closed_support_risk_note": "Internal channels use a documented self-supporting teardrop profile; no internal support material is intended. Inspect first layer and purge with air before acoustic tests.",
    }
    report["validation_failure_conditions_passed"] = (
        diagonal_report["all_required_diagonal_counts_zero"]
        and report["ab_strong_and_sbridge_same_path_positions"]
        and report["ab_strong_3mm_and_sbridge_same_path_positions"]
        and report["s1_enabled_bridges_is_ab_strong_3mm"]
        and report["ab_strong_3mm_nominal_diameter_is_3p0"]
        and report["ab_strong_3mm_modeled_diameter_is_3p3"]
        and report["ab_strong_3mm_effective_length_is_10mm"]
        and report["ab_strong_3mm_tap_positions_are_a213_b60"]
        and report["ab_strong_3mm_path_delta_is_153mm"]
        and report["ab_strong_3mm_enabled_only_in_s1"]
        and report["legacy_ab_strong_nominal_diameter_is_2p0"]
        and report["legacy_ab_strong_modeled_diameter_is_2p2"]
        and report["legacy_ab_strong_enabled_only_in_s5_s6"]
        and report["s2_uses_ab_sbridge"]
        and report["ab_sbridge_nominal_diameter_is_2p0"]
        and report["ab_sbridge_modeled_diameter_is_2p2"]
        and report["ab_sbridge_effective_length_is_20mm"]
        and report["s5_s6_use_legacy_ab_strong_not_3mm"]
        and report["s0_has_no_enabled_bridges"]
        and report["all_meshes_watertight"]
        and report["all_meshes_manifold"]
        and report["all_meshes_single_component"]
        and report["all_within_p1s_volume"]
        and v7_report["mic_end_geometry_changed_from_v7"] in ("false", "minimal")
        and v7_report["main_ducts_close_to_v7_style"]
        and spacing["main_duct_pitch_min_mm"] >= 24.0
        and spacing["chamber_inlet_pitch_min_mm"] >= 12.0
        and spacing["minimum_wall_between_chamber_inlets_at_least_4mm"]
        and report["chamber_volume_smaller_than_v8r2_by_at_least_25_percent"]
        and tap_report["all_bridge_taps_on_straight_segments"]
        and tap_report["all_bridge_tap_clearance_at_least_10mm"]
        and tap_report["cd_bridge_not_on_d_bend"]
        and report["all_state_outer_bounds_same"]
        and report["no_channel_clipped_by_trim"]
        and report["no_acoustic_path_changed_except_s1_diagnostic_bridge"]
        and not s_turns["s_bridge_excessive_turn_count"]
    )
    return report


def write_json_and_text(checks, validation):
    main_meta = main_duct_metadata()
    bridge_meta = bridge_metadata()
    trim = validation["trim_report"]

    sim = {
        "version": VERSION,
        "units": "mm",
        "speed_of_sound_m_per_s": SPEED_OF_SOUND_M_PER_S,
        "frequency_range_hz": FREQUENCY_RANGE_HZ,
        "generation_method": {
            "type": "voxel_sdf_marching_cubes",
            "voxel_pitch_mm": VOXEL_PITCH_MM,
            "dependency_note": "Uses trimesh plus scikit-image marching cubes; no CAD boolean engine required.",
        },
        "body": {
            "original_dimensions_mm": [BODY_MAX_X_MM, trim["original_y_span_mm"], BODY_MAX_Z_MM],
            "trimmed_dimensions_mm": [BODY_MAX_X_MM, trim["trimmed_y_span_mm"], BODY_MAX_Z_MM],
            "original_y_min_mm": trim["original_y_min_mm"],
            "original_y_max_mm": trim["original_y_max_mm"],
            "trimmed_y_min_mm": trim["new_y_min_mm"],
            "trimmed_y_max_mm": trim["new_y_max_mm"],
            "one_piece_print": True,
            "recommended_print_orientation": "flat on XY plane; channels run in-plane",
        },
        "layout": {
            "type": "V9_1_y_trimmed_with_s1_ab_strong_3mm_diagnostic",
            "main_duct_intent": "identical to uploaded V8R3T; S1 alone uses a new AB_strong_3mm diagnostic bridge at the legacy AB tap position",
            "v7_reference_style": V7_REFERENCE_STYLE_NOTE,
            "v7_reference_main_lengths_mm": V7_REFERENCE_MAIN_LENGTHS_MM,
            "path_delta_targets_mm": {"AB": AB_TARGET_DELTA_MM, "BC": BC_TARGET_DELTA_MM, "CD": CD_TARGET_DELTA_MM},
            "path_delta_tolerance_mm": DELTA_TOL_MM,
            "path_delta_policy": "soft constraint; do not re-route main ducts to hit delta targets",
            "bridge_position_strategy": "slide bridge taps only along existing long straight duct segments; CD is moved off the D bend",
            "bridge_x_by_pair_mm": BRIDGE_X_BY_PAIR_MM,
            "main_duct_pitch_target_y_mm": TARGET_MAIN_DUCT_PITCH_Y_MM,
            "chamber_inlet_pitch_target_y_mm": TARGET_CHAMBER_INLET_PITCH_Y_MM,
            "v7_like_u_turn_counts": U_TURN_COUNTS_V7_LIKE,
            "no_v8_clean_rerouting": True,
            "local_fix_only_relative_to_v8r2": True,
            "external_board_trim_only": True,
        },
        "geometry_modification": {
            "type": "s1_internal_ab_strong_3mm_diagnostic_bridge_plus_existing_y_trim",
            "source_version": "V8R3T / chamber_bridge_fix_trimmed",
            "acoustic_geometry_changed": True,
            "acoustic_geometry_change_scope": "S1 bridge air only",
            "s1_enabled_bridge_changed_from": "AB_strong",
            "s1_enabled_bridge_changed_to": "AB_strong_3mm",
            "ab_strong_3mm_diagnostic_role": BRIDGES["AB_strong_3mm"]["diagnostic_role"],
            "duct_centerlines_changed": False,
            "bridge_positions_changed": False,
            "mixing_chamber_changed": False,
            "ports_changed": False,
            "legacy_states_s0_s2_s3_s4_s5_s6_s7_acoustic_meaning_changed": False,
            "rigid_translation_applied": False,
            "trim_report": trim,
        },
        "cross_sections": {
            "main": teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM),
            "bridge_default": teardrop_props(BRIDGE_MODELED_DIAMETER_MM),
            "bridges": bridge_cross_sections_summary(),
        },
        "main_ducts": main_meta,
        "bridges": {
            name: {
                "type": data["type"],
                "from": data["from"],
                "to": data["to"],
                "from_path_mm": data["from_path_mm"],
                "to_path_mm": data["to_path_mm"],
                "delta_path_mm": data["delta_path_mm"],
                "target_delta_path_mm": data["target_delta_path_mm"],
                "diameter_mm": data["nominal_diameter_mm"],
                "modeled_diameter_mm": data["modeled_diameter_mm"],
                "cross_section_area_mm2": data["cross_section_area_mm2"],
                "hydraulic_diameter_mm": data["hydraulic_diameter_mm"],
                "effective_length_mm": data["effective_centerline_length_mm"],
                "enabled_in": data["enabled_in"],
                "centerline_points_mm": data["points"],
                "relative_impedance_to_main_at_2khz": data["relative_impedance_to_main_at_2khz"],
                "tap_clearance": data["tap_clearance"],
                "diagnostic_role": data.get("diagnostic_role"),
            }
            for name, data in bridge_meta.items()
        },
        "states": {
            name: {
                "filename": state["filename"],
                "enabled_bridges": state["enabled_bridges"],
                "purpose": state["purpose"],
            }
            for name, state in STATES.items()
        },
        "mixing_chamber": {
            "type": "compact_rounded_rectangle_teardrop_roof",
            "center_mm": CHAMBER_CENTER_MM,
            "v7_reference_center_mm": V7_REFERENCE_CHAMBER_CENTER_MM,
            "v7_reference_radius_mm": V7_REFERENCE_CHAMBER_RADIUS_MM,
            "half_width_mm": CHAMBER_HALF_WIDTH_MM,
            "half_height_mm": CHAMBER_HALF_HEIGHT_MM,
            "corner_radius_mm": CHAMBER_CORNER_RADIUS_MM,
            "equivalent_radius_mm": round(chamber_equivalent_radius_mm(), 3),
            "footprint_area_mm2": round(chamber_footprint_area_mm2(), 3),
            "roof_height_mm": CHAMBER_ROOF_HEIGHT_MM,
            "estimated_volume_mm3": round(chamber_volume_estimate_mm3(), 3),
            "v8r2_reference_volume_mm3": V8R2_REFERENCE_CHAMBER_VOLUME_MM3,
            "volume_reduction_percent_vs_v8r2": round(chamber_volume_reduction_percent(), 2),
            "input_connection_points_mm": {lane: points[-1] for lane, points in LANES.items()},
            "neck_lengths_mm": validation["chamber_neck_lengths_mm"],
            "note": "V9.1 keeps the V8R3T compact right-side junction; final necks are short and orthogonal to avoid diagonal fan-in.",
        },
        "ports": {
            "inputs": {lane: {"point_mm": points[0], "diameter_mm": MAIN_DUCT_DIAMETER_MM, "modeled_diameter_mm": MAIN_DUCT_MODELED_DIAMETER_MM} for lane, points in LANES.items()},
            "mic_output": {"from_mm": CHAMBER_CENTER_MM, "to_mm": MIC_PORT_END_MM, "diameter_mm": MIC_PORT_DIAMETER_MM, "modeled_diameter_mm": MIC_PORT_MODELED_DIAMETER_MM},
        },
        "validation_summary": {
            "main_duct_diagonal_segment_count": validation["main_duct_diagonal_segment_count"],
            "bridge_diagonal_segment_count": validation["bridge_diagonal_segment_count"],
            "mic_fanin_diagonal_segment_count": validation["mic_fanin_diagonal_segment_count"],
            "chamber_volume_reduction_percent": validation["chamber_volume_reduction_percent"],
            "bridge_tap_clearance_report": validation["bridge_tap_clearance_report"],
            "ab_strong_and_sbridge_same_path_positions": validation["ab_strong_and_sbridge_same_path_positions"],
            "s_bridge_template_uniformity": validation["s_bridge_template_uniformity"],
            "spacing_report": validation["spacing_report"],
            "trim_report": trim,
            "acoustic_invariance_report": validation["acoustic_invariance_report"],
            "s1_enabled_bridges_is_ab_strong_3mm": validation["s1_enabled_bridges_is_ab_strong_3mm"],
            "ab_strong_3mm_nominal_diameter_is_3p0": validation["ab_strong_3mm_nominal_diameter_is_3p0"],
            "ab_strong_3mm_modeled_diameter_is_3p3": validation["ab_strong_3mm_modeled_diameter_is_3p3"],
            "s2_uses_ab_sbridge": validation["s2_uses_ab_sbridge"],
            "s5_s6_use_legacy_ab_strong_not_3mm": validation["s5_s6_use_legacy_ab_strong_not_3mm"],
        },
    }
    (OUT / "sim_params_v9_1.json").write_text(json.dumps(sim, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "V9.1 / y_trimmed model parameters",
        "",
        "Design summary",
        "- V9.1 is a further Y-axis external-shell trim of the uploaded V8R3T package.",
        "- Only unused Y-min/Y-max board margins are additionally removed.",
        "- S1 is changed to a strong single-bridge diagnostic using AB_strong_3mm.",
        "- AB_strong_3mm is 3.0 mm nominal / 3.3 mm modeled / 10.0 mm centerline length.",
        "- Legacy AB_strong remains 2.0 mm nominal / 2.2 mm modeled for S5/S6.",
        "- S2 remains the weak AB_sbridge comparison at 2.0 mm nominal / 2.2 mm modeled / 20.0 mm centerline length.",
        "- Main ducts, input ports, mixing chamber, mic output, and all AB tap positions remain unchanged.",
        "- No rigid translation is applied; original acoustic coordinates are preserved.",
        "",
        "Printing assumptions",
        f"- Printer: {PRINTER}",
        f"- Material: {MATERIAL}",
        f"- Nozzle: {NOZZLE_MM} mm",
        "- Print orientation: flat on XY plane, one-piece monolithic coupon.",
        "- Support: no internal support intended; teardrop channels are self-supporting by design.",
        "- Closed-cavity risk: present but reduced by small ducts, teardrop roofs, and open A/B/C/D/mic ports for air flushing.",
        "- Cleaning method: blow compressed air through each port, inspect ports, then seal inactive ports during experiments.",
        "",
        "Trim parameters",
        f"- Original outer dimensions: {[BODY_MAX_X_MM, trim['original_y_span_mm'], BODY_MAX_Z_MM]} mm",
        f"- Trimmed outer dimensions: {[BODY_MAX_X_MM, trim['trimmed_y_span_mm'], BODY_MAX_Z_MM]} mm",
        f"- y_min original: {trim['original_y_min_mm']} mm",
        f"- y_max original: {trim['original_y_max_mm']} mm",
        f"- y_min new: {trim['new_y_min_mm']} mm",
        f"- y_max new: {trim['new_y_max_mm']} mm",
        f"- Cut from bottom: {trim['cut_from_bottom_mm']} mm",
        f"- Cut from top: {trim['cut_from_top_mm']} mm",
        f"- V8 trimmed y span: {trim['v8_trimmed_y_span_mm']} mm",
        f"- Additional Y reduction vs V8: {trim['additional_y_reduction_vs_v8_mm']} mm",
        f"- Additional cut from V8 bottom/Y-min: {trim['additional_cut_from_v8_bottom_mm']} mm",
        f"- Additional cut from V8 top/Y-max: {trim['additional_cut_from_v8_top_mm']} mm",
        f"- functional_y_min: {trim['functional_y_min_mm']} mm",
        f"- functional_y_max: {trim['functional_y_max_mm']} mm",
        f"- trim_margin_y: {trim['trim_margin_y_mm']}",
        f"- Minimum any-air wall to y edge: {trim['minimum_channel_or_port_outer_wall_to_y_edge_mm']} mm",
        f"- Ordinary main region minimum wall: {validation['wall_thickness_report']['ordinary_main_region_min_wall_mm']} mm",
        f"- Bridge region minimum wall: {validation['wall_thickness_report']['bridge_region_min_wall_mm']} mm",
        f"- Mixing chamber region minimum wall: {validation['wall_thickness_report']['mixing_chamber_region_min_wall_mm']} mm",
        f"- Input/output interface region minimum wall: {validation['wall_thickness_report']['input_output_interface_region_min_wall_mm']} mm",
        f"- Minimum any-air wall meets 3 mm required: {trim['minimum_edge_wall_meets_required']}",
        f"- Input/output interface wall meets 8 mm required: {validation['wall_thickness_report']['input_output_interface_region_meets_8mm']}",
        f"- Estimated body volume savings vs original untrimmed body: {trim['estimated_body_volume_savings_percent']} percent",
        f"- Estimated material savings vs original untrimmed body: {trim['estimated_material_savings_percent']} percent",
        f"- Estimated material savings vs V8: {trim['estimated_material_savings_vs_v8_percent']} percent",
        f"- Estimated volume saving vs V8: {trim['estimated_volume_saving_vs_v8_mm3']} mm3",
        f"- Estimated PLA mass saving vs V8: {trim['estimated_mass_saving_vs_v8_g']} g",
        f"- Top edge limit note: {trim['top_edge_limit_note']}",
        f"- Bottom edge limit note: {trim['bottom_edge_limit_note']}",
        f"- Estimated print time trend: {trim['estimated_print_time_trend']}",
        f"- Acoustic geometry change scope: {validation['acoustic_geometry_change_scope']}",
        "",
        "Outer dimensions and STL checks",
    ]
    for file, result in checks.items():
        span = validation["bbox_checks"][file]["span_mm"]
        lines.append(f"- {file}: bbox span {span} mm, watertight={result['watertight']}, within P1S={validation['bbox_checks'][file]['within_p1s_volume']}")
    lines += [
        f"- V8 vs V9.1 bounding box comparison: {json.dumps(validation['v8_bbox_comparison'], ensure_ascii=False)}",
        f"- Y-axis STL bbox reduction vs V8: {validation['y_axis_reduction_vs_v8_mm']} mm nominal; actual mesh span reduction is {next(iter(validation['v8_bbox_comparison'].values()))['y_span_reduction_mm']} mm",
    ]
    lines += [
        f"- Recommended max envelope 200 x 170 x 30 mm satisfied: {validation['all_within_200x170x30']}",
        f"- All states have identical external trim boundary: {validation['all_state_outer_bounds_same']}",
        "",
        "Main duct parameters",
        f"- Nominal diameter: {MAIN_DUCT_DIAMETER_MM} mm",
        f"- Modeled equivalent diameter: {MAIN_DUCT_MODELED_DIAMETER_MM} mm",
        f"- Cross-section: {teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM)}",
        f"- V7-like U-turn counts: {U_TURN_COUNTS_V7_LIKE}",
        f"- Main duct diagonal segment count: {validation['main_duct_diagonal_segment_count']}",
        f"- Main duct short random segment count: {validation['main_duct_short_random_segment_count']}",
    ]
    for lane, data in main_meta.items():
        lines.append(f"- {lane}: length {data['length_mm']} mm, points {data['centerline_points_mm']}")
    lines += [
        f"- Main duct maximum length difference: {validation['main_length_spread_mm']} mm",
        f"- Main ducts within {TARGET_MAIN_LENGTH_MM:g} +/- {MAIN_LENGTH_TOL_MM:g} mm: {validation['main_lengths_within_300_plus_minus_10']}",
        f"- Centerline lengths unchanged vs V8R3: {validation['duct_centerline_lengths_unchanged_vs_v8r3']}",
        f"- Centerline points unchanged vs V8R3: {validation['duct_centerline_points_unchanged_vs_v8r3']}",
        f"- Main duct pitch y: {json.dumps(validation['main_duct_pitch_y_mm'], ensure_ascii=False)}",
        f"- Main duct pitch within 26-28 mm: {validation['main_duct_pitch_within_26_to_28mm']}",
        f"- Main duct centerline crossing check: {validation['main_duct_crossing_report']['no_centerline_self_or_inter_lane_crossings']}",
        f"- V7 similarity report: {json.dumps(validation['v7_similarity_report'], ensure_ascii=False)}",
        "",
        "Bridge parameters",
    ]
    for name, data in bridge_meta.items():
        lines.append(
            f"- {name}: type={data['type']}, connects {data['from']}@{data['from_path_mm']} mm to "
            f"{data['to']}@{data['to_path_mm']} mm, delta={data['delta_path_mm']} mm, "
            f"target_delta={data['target_delta_path_mm']} mm, effective_length={data['effective_centerline_length_mm']} mm, "
            f"nominal_diameter={data['nominal_diameter_mm']} mm, modeled_diameter={data['modeled_diameter_mm']} mm, "
            f"area={data['cross_section_area_mm2']} mm2, hydraulic_diameter={data['hydraulic_diameter_mm']} mm, "
            f"relative_impedance_at_2khz={data['relative_impedance_to_main_at_2khz']}, "
            f"tap_clearance={json.dumps(data['tap_clearance'], ensure_ascii=False)}, enabled_in={data['enabled_in']}, "
            f"diagnostic_role={data.get('diagnostic_role')}"
        )
    lines += [
        f"- Bridge path-delta checks: {json.dumps(validation['bridge_path_delta_checks'], ensure_ascii=False)}",
        f"- Bridge position strategy checks: {json.dumps(validation['bridge_position_strategy_checks'], ensure_ascii=False)}",
        f"- Bridge diagonal segment count: {validation['bridge_diagonal_segment_count']}",
        f"- S bridge template uniformity: {json.dumps(validation['s_bridge_template_uniformity'], ensure_ascii=False)}",
        f"- S bridge turn report: {json.dumps(validation['s_bridge_turn_report'], ensure_ascii=False)}",
        f"- Bridge tap clearance report: {json.dumps(validation['bridge_tap_clearance_report'], ensure_ascii=False)}",
        f"- Bridge positions unchanged vs V8R3: {validation['bridge_positions_unchanged_vs_v8r3']}",
        f"- Bridge effective lengths unchanged vs V8R3: {validation['bridge_effective_lengths_unchanged_vs_v8r3']}",
        f"- All bridge taps on straight segments: {validation['all_bridge_taps_on_straight_segments']}",
        f"- All bridge taps at least 10 mm from nearest bend: {validation['all_bridge_tap_clearance_at_least_10mm']}",
        f"- CD bridge D-side tap clearance from nearest bend: {validation['cd_bridge_d_tap_clearance_from_bend_mm']} mm",
        f"- CD bridge not on D bend: {validation['cd_bridge_not_on_d_bend']}",
        f"- S1 enabled bridges is AB_strong_3mm: {validation['s1_enabled_bridges_is_ab_strong_3mm']}",
        f"- AB_strong_3mm diameter check: nominal 3.0={validation['ab_strong_3mm_nominal_diameter_is_3p0']}, modeled 3.3={validation['ab_strong_3mm_modeled_diameter_is_3p3']}, length 10={validation['ab_strong_3mm_effective_length_is_10mm']}",
        f"- Legacy AB_strong remains 2.0/2.2 and enabled only in S5/S6: {validation['legacy_ab_strong_nominal_diameter_is_2p0']} / {validation['legacy_ab_strong_modeled_diameter_is_2p2']} / {validation['legacy_ab_strong_enabled_only_in_s5_s6']}",
        f"- S2 still uses weak AB_sbridge 2.0/2.2/20mm: {validation['s2_uses_ab_sbridge']} / {validation['ab_sbridge_nominal_diameter_is_2p0']} / {validation['ab_sbridge_modeled_diameter_is_2p2']} / {validation['ab_sbridge_effective_length_is_20mm']}",
        f"- S5/S6 use legacy AB_strong, not AB_strong_3mm: {validation['s5_s6_use_legacy_ab_strong_not_3mm']}",
        f"- S0 has no enabled bridges: {validation['s0_has_no_enabled_bridges']}",
        f"- Legacy strong bridge shorter than AB S bridge: {validation['legacy_ab_strong_shorter_than_ab_sbridge']}",
        f"- AB_strong_3mm shorter than AB S bridge: {validation['ab_strong_3mm_shorter_than_ab_sbridge']}",
        f"- AB strong and AB S bridge same path positions: {validation['ab_strong_and_sbridge_same_path_positions']}",
        f"- AB_strong_3mm and AB S bridge same path positions: {validation['ab_strong_3mm_and_sbridge_same_path_positions']}",
        "",
        "Mixing chamber",
        f"- Type: compact rounded rectangle with teardrop-style roof, center {CHAMBER_CENTER_MM}",
        f"- Half width x half height: {CHAMBER_HALF_WIDTH_MM} x {CHAMBER_HALF_HEIGHT_MM} mm, corner radius {CHAMBER_CORNER_RADIUS_MM} mm",
        f"- Footprint area: {chamber_footprint_area_mm2():.1f} mm2",
        f"- Equivalent footprint radius: {chamber_equivalent_radius_mm():.2f} mm",
        f"- Estimated volume: {chamber_volume_estimate_mm3():.1f} mm3",
        f"- V8R2 reference chamber volume: {V8R2_REFERENCE_CHAMBER_VOLUME_MM3:.1f} mm3",
        f"- Volume reduction vs V8R2: {chamber_volume_reduction_percent():.1f} percent",
        f"- Volume reduced by at least 25 percent: {validation['chamber_volume_smaller_than_v8r2_by_at_least_25_percent']}",
        f"- Mic port modeled diameter: {MIC_PORT_MODELED_DIAMETER_MM} mm",
        f"- Mic port: {CHAMBER_CENTER_MM} to {MIC_PORT_END_MM}",
        f"- Mic fan-in diagonal segment count: {validation['mic_fanin_diagonal_segment_count']}",
        f"- Chamber connection style: {validation['chamber_connection_style']}",
        f"- Mixing chamber unchanged vs V8R3: {validation['mixing_chamber_unchanged_vs_v8r3']}",
        f"- Ports unchanged vs V8R3: {validation['ports_unchanged_vs_v8r3']}",
        f"- Input duct connection positions: {json.dumps({lane: points[-1] for lane, points in LANES.items()})}",
        f"- Chamber neck lengths: {json.dumps(validation['chamber_neck_lengths_mm'], ensure_ascii=False)}",
        f"- Chamber inlet pitch y: {validation['chamber_inlet_pitch_y_mm']}",
        f"- Chamber inlet pitch within 14-16 mm: {validation['chamber_inlet_pitch_within_14_to_16mm']}",
        f"- Minimum wall between chamber inlets: {validation['minimum_wall_between_chamber_inlets_mm']} mm",
        f"- Minimum wall between chamber inlets >= 4 mm: {validation['minimum_wall_between_chamber_inlets_at_least_4mm']}",
        f"- B/D chamber connection regularized: {validation['bd_chamber_connection_regularized']}",
        f"- B/D chamber connection note: {validation['bd_chamber_connection_note']}",
        f"- Chamber fan-in local only: {validation['chamber_fanin_local_only']}",
        "",
        "Validation summary",
        f"- validation_failure_conditions_passed: {validation['validation_failure_conditions_passed']}",
        f"- acoustic invariance report: {json.dumps(validation['acoustic_invariance_report'], ensure_ascii=False)}",
        f"- no channel clipped by trim: {validation['no_channel_clipped_by_trim']}",
        f"- wall thickness report: {json.dumps(validation['wall_thickness_report'], ensure_ascii=False)}",
        f"- minimum channel outer wall to y edge: {validation['minimum_channel_outer_wall_to_y_edge_mm']} mm",
        f"- minimum port/interface outer wall to y edge: {validation['wall_thickness_report']['input_output_interface_region_min_wall_mm']} mm",
        f"- mesh integrity: {json.dumps(validation['mesh_integrity'], ensure_ascii=False)}",
        f"- all meshes watertight: {validation['all_meshes_watertight']}",
        f"- all meshes manifold: {validation['all_meshes_manifold']}",
        f"- all meshes single component: {validation['all_meshes_single_component']}",
        f"- self-intersection check: {validation['self_intersection_check']}",
        f"- fragile features under 2.0 mm: {validation['fragile_features_under_2mm']}",
        f"- exposed air channels: {validation['air_channels_exposed_to_exterior']}",
        f"- printable within Bambu Lab P1S volume: {validation['all_within_p1s_volume']}",
        f"- long thin edge/warp risk note: {validation['long_thin_edge_warp_risk_note']}",
        f"- diagonal geometry report: {json.dumps(validation['diagonal_geometry_report'], ensure_ascii=False)}",
        f"- chamber volume check: estimate={validation['chamber_volume_estimate_mm3']} mm3, reduction={validation['chamber_volume_reduction_percent']} percent",
        "",
        "State versions",
    ]
    for name, state in STATES.items():
        lines.append(f"- {name}: {state['filename']}, bridges={state['enabled_bridges']}, purpose={state['purpose']}")
    (OUT / "model_params_v9_1.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = f"""V9.1 / y_trimmed acoustic network engineering package
=================================================================

Design purpose
--------------
This package keeps the V9.1 y-trimmed board geometry and turns S1 into a
strong single-bridge mechanism-diagnosis part. S1 alone uses AB_strong_3mm,
a 3.0 mm nominal / 3.3 mm modeled / 10.0 mm internal AB bridge at the same
A@213.0 mm and B@60.0 mm tap positions as the legacy AB bridge.

Main ducts, input ports, mixing chamber, mic output, and bridge tap positions
are unchanged. S0 and S2-S7 keep their original acoustic meanings. In
particular, S5/S6 still use the legacy 2.0 mm nominal / 2.2 mm modeled
AB_strong, not AB_strong_3mm.

Trim summary
------------
- Uploaded V8 trimmed y span: {trim['v8_trimmed_y_span_mm']} mm.
- V9.1 trimmed y span: {trim['trimmed_y_span_mm']} mm.
- New y bounds: {trim['new_y_min_mm']} to {trim['new_y_max_mm']} mm.
- Additional cut from V8 bottom/Y-min: {trim['additional_cut_from_v8_bottom_mm']} mm.
- Additional cut from V8 top/Y-max: {trim['additional_cut_from_v8_top_mm']} mm.
- Additional Y reduction vs V8: {trim['additional_y_reduction_vs_v8_mm']} mm.
- Minimum ordinary-main y-edge wall: {validation['wall_thickness_report']['ordinary_main_region_min_wall_mm']} mm.
- Minimum bridge-region y-edge wall: {validation['wall_thickness_report']['bridge_region_min_wall_mm']} mm.
- Minimum chamber-region y-edge wall: {validation['wall_thickness_report']['mixing_chamber_region_min_wall_mm']} mm.
- Minimum input/output interface y-edge wall: {validation['wall_thickness_report']['input_output_interface_region_min_wall_mm']} mm.
- Estimated material saving vs V8: {trim['estimated_material_savings_vs_v8_percent']} percent, about {trim['estimated_volume_saving_vs_v8_mm3']} mm3 / {trim['estimated_mass_saving_vs_v8_g']} g PLA.

Experimental equivalence
------------------------
Only S1 is changed acoustically. The change is intentionally limited to the
internal AB diagnostic bridge diameter. This version should be used to test
whether a strong single internal AB bridge produces a clear, repeatable
transfer-function change beyond assembly drift. It should not be claimed as a
final validated acoustic network.

STL files
---------
- V9_1_S0_no_bridges.stl: baseline with no bridge.
- V9_1_S1_AB_strong_3mm_x10mm_only.stl: S1-only AB_strong_3mm diagnostic bridge.
- V9_1_S2_AB_sbridge_only.stl: weak 2.0/2.2 mm AB S bridge only, same duct positions as S1.
- V9_1_S3_BC_sbridge_only.stl: BC S bridge only.
- V9_1_S4_CD_sbridge_only.stl: CD S bridge only.
- V9_1_S5_AB_strong_BC_sbridge.stl: AB strong plus BC S bridge.
- V9_1_S6_AB_strong_BC_CD_sbridges.stl: AB strong plus BC/CD S bridges.
- V9_1_S7_AB_BC_CD_all_sbridges.stl: AB/BC/CD all S bridges.

Other files
-----------
- generate_v9_1.py: parametric generator.
- model_params_v9_1.txt: human-readable dimensions and checks.
- sim_params_v9_1.json: structured data for later 1D graph simulation.
- validation_report_v9_1.txt: generated validation report.
- codex_change_log_v9_1.txt: human-readable change log.

Printing
--------
- Print flat on the XY plane.
- Use PLA on Bambu Lab P1S with a 0.4 mm nozzle.
- Internal support is not intended; channels use a self-supporting teardrop profile.
- In Bambu Studio, inspect layer height, port openings, bridge slots, stringing,
  hole/duct visibility, and whether the slicer creates any unwanted supports.
- Check first-layer adhesion after trimming. If edge adhesion looks weak, add a
  brim or use bed-temperature/glue assistance.
- Purge all ports with air before acoustic measurement.

Suggested first print
---------------------
Print S0 or S2 first and check the A/B/C/D ports, mic output, purge/cleaning
process, fixture sealing, and trimmed edge robustness. Then print the remaining
states after the baseline process is repeatable.

Experiment setup
----------------
- Fix the microphone at the right-side mic output.
- Connect the speaker to A/B/C/D in sequence.
- Seal inactive input ports with the same external cap method for every trial.
- Recommended signal: log chirp 300 Hz-10 kHz, analyze 500 Hz-8 kHz.
- White noise can be used as a repeatability/control signal.
- Recommended metrics: transfer-function correlation, effective rank,
  repeatability, energy-normalized classification, and insertion loss.
- Recommended state order: S0, S1, S2, S3, S4, S5, S6, S7.

Manual inspection focus
-----------------------
- Confirm trimmed top/bottom edges do not expose or thin any channel wall.
- Confirm all V9.1 states have the same external outline.
- Confirm no slicer support is generated inside the teardrop channels.

Important warning
-----------------
V9.1 keeps the same main network geometry. This update only adds the S1-only
AB_strong_3mm diagnostic bridge and does not introduce slits, tone holes,
horns, external baffles, new main-duct topology, or open-port structures.
"""
    (OUT / "README_v9_1.txt").write_text(readme, encoding="utf-8")

    change_log = f"""codex_change_log_v9_1
=====================

1. 修改了哪些实体外轮廓
- 仅修改外部实体壳体的 Y-min/Y-max 裁剪边界。
- V8 的名义 Y 范围为 {trim['v8_trimmed_y_min_mm']} to {trim['v8_trimmed_y_max_mm']} mm，V9.1 的名义 Y 范围为 {trim['new_y_min_mm']} to {trim['new_y_max_mm']} mm。
- 相比 V8，Y-min 侧额外削减 {trim['additional_cut_from_v8_bottom_mm']} mm，Y-max 侧额外削减 {trim['additional_cut_from_v8_top_mm']} mm，总 Y 宽度额外减少 {trim['additional_y_reduction_vs_v8_mm']} mm。

2. 没有修改哪些声学功能部分
- 未修改 A/B/C/D 四条主管中心线、长度、截面尺寸或截面形状。
- 未修改 AB_strong、AB_sbridge、BC_sbridge、CD_sbridge 的截面、连接位置、路径差或启用状态。
- 未修改 mixing chamber 的中心、内部 footprint、roof 参数、内部体积或四条 chamber neck。
- 未修改 A/B/C/D 输入端口和 microphone/output port 的位置、方向、孔径或接口几何。
- 未修改 z 方向厚度、x 方向长度、声学 graph 参数或状态拓扑。

3. Y 方向材料缩减了多少
- V8 名义 Y span: {trim['v8_trimmed_y_span_mm']} mm。
- V9.1 名义 Y span: {trim['trimmed_y_span_mm']} mm。
- 名义 Y span 相比 V8 减少 {trim['additional_y_reduction_vs_v8_mm']} mm。
- STL bbox 的 Y span 对比见 validation_report_v9_1.txt 的 v8_bbox_comparison。

4. 预计节省了多少体积或材料
- 相比 V8，按外壳完整矩形裁剪估算减少实体体积约 {trim['estimated_volume_saving_vs_v8_mm3']} mm3。
- 按 PLA 密度 {PLA_DENSITY_G_PER_CM3} g/cm3 估算，约节省 {trim['estimated_mass_saving_vs_v8_g']} g 材料。
- 该估算未代替切片器的实际耗材和打印时间结果。

5. 哪些区域因为最小壁厚限制没有继续缩减
- Y-max 侧没有压到 6 mm，因为 A 输入端口位于最高 Y 功能边界附近，需保留 8.0 mm 接口加强实体。
- Y-min 侧停止在 6.0 mm，作为普通主管外缘的轻量化目标，同时明显高于 3.0 mm 的最低实体壁厚。
- bridge 区域、mixing chamber 区域和 mic/output 区域不是本次裁剪的限制项，保留壁厚远高于最低要求。

6. 这个版本适合什么实验用途
- 适合和 V8 进行相同声学拓扑下的轻量化/打印耗材/打印时间趋势对比。
- 适合继续做 S0-S7 状态间的传递函数、重复性、分类或插入损耗实验。
- 适合验证外部非功能材料减少后，V8 声学路径是否保持实验等价。

7. 这个版本不适合做什么结论
- 不适合用来声称桥管位置、主管路径、mixing chamber 或端口设计优于 V8，因为这些声学功能几何没有改变。
- 不适合作为新的声学拓扑版本解读。
- 不适合仅凭该模型推断极限壁厚可进一步降低；继续削减需要重新做局部强度、密封性和切片验证。
"""
    change_log = f"""codex_change_log_v9_1
=====================

V9.1 S1 strong AB diagnostic update
-----------------------------------
- Added AB_strong_3mm as a new S1-only bridge.
- S1 filename changed to V9_1_S1_AB_strong_3mm_x10mm_only.stl.
- S1 enabled_bridges changed from ['AB_strong'] to ['AB_strong_3mm'].
- AB_strong_3mm uses the same AB tap positions as legacy AB_strong:
  A@213.0 mm to B@60.0 mm, points [(60.0, 110.0), (60.0, 100.0)].
- AB_strong_3mm: nominal_diameter_mm = 3.0, modeled_diameter_mm = 3.3,
  effective centerline length = 10.0 mm, path delta = 153.0 mm.
- Legacy AB_strong is unchanged at 2.0 mm nominal / 2.2 mm modeled and
  remains enabled only in S5/S6.
- AB_sbridge, BC_sbridge, and CD_sbridge remain weak 2.0 mm nominal /
  2.2 mm modeled bridges. S2 remains the weak AB_sbridge comparison.
- S0 remains no-bridge.
- S0/S2/S3/S4/S5/S6/S7 keep their original acoustic meaning.
- Main duct centerlines, path lengths, input ports, mixing chamber, mic
  output, bridge tap positions, and y-trimmed board outline are unchanged.
- No external slit, tone-hole, horn, baffle, open-port, or private-stub
  leakage mechanism is introduced.
- This package is a strong single-bridge mechanism diagnosis part and
  should not be presented as final proof that the network is validated.

Trim context retained from V9.1
-------------------------------
- Trimmed y bounds: {trim['new_y_min_mm']} to {trim['new_y_max_mm']} mm.
- Trimmed y span: {trim['trimmed_y_span_mm']} mm.
- Estimated material saving vs V8: {trim['estimated_material_savings_vs_v8_percent']} percent.
"""
    (OUT / "codex_change_log_v9_1.txt").write_text(change_log, encoding="utf-8")

    vlines = ["V9.1 / y_trimmed validation report", ""]
    for key, value in validation.items():
        vlines.append(f"{key}: {value}")
    (OUT / "validation_report_v9_1.txt").write_text("\n".join(vlines) + "\n", encoding="utf-8")


def write_package_zip():
    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()
    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.iterdir():
            if p.name == PACKAGE_ZIP.name or p.name == "__pycache__":
                continue
            z.write(p, Path("V9_1_y_trimmed") / p.name)


def main():
    ensure_clean_out()
    xs, ys, zs, body, base_air, bridge_air = build_air_masks()
    origin = (xs[0], ys[0], zs[0])

    checks = {}
    for state_name, state in STATES.items():
        air = base_air.copy()
        for bridge_name in state["enabled_bridges"]:
            air |= bridge_air[bridge_name]
        solid = body & (~air)
        mesh = solid_to_mesh(solid, origin)
        checks[state["filename"]] = export_mesh(mesh, OUT / state["filename"])
        print(state_name, checks[state["filename"]])

    validation = validate(checks)
    write_json_and_text(checks, validation)
    write_package_zip()
    print("main lengths", {k: round(polyline_length(v), 3) for k, v in LANES.items()})
    print("package", PACKAGE_ZIP)


if __name__ == "__main__":
    main()

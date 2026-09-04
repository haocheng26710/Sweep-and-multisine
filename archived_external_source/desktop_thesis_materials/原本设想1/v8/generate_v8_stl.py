import json
import math
import shutil
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from trimesh.voxel.ops import matrix_to_marching_cubes


VERSION = "V8"
OUT = Path(__file__).resolve().parent
PACKAGE_ZIP = OUT / "v8_package.zip"

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
BODY_MAX_Y_MM = 145.0
BODY_MAX_Z_MM = 12.0
PRINT_LIMIT_RECOMMENDED_MM = (200.0, 160.0, 30.0)
P1S_BUILD_VOLUME_MM = (256.0, 256.0, 256.0)

VOXEL_PITCH_MM = 0.5
VOXEL_MARGIN_MM = 1.0

MAIN_DUCT_DIAMETER_MM = 4.0
MAIN_DUCT_MODELED_DIAMETER_MM = 4.4
BRIDGE_DIAMETER_MM = 2.0
BRIDGE_MODELED_DIAMETER_MM = 2.2
MIC_PORT_DIAMETER_MM = 4.0
MIC_PORT_MODELED_DIAMETER_MM = 4.4

TARGET_MAIN_LENGTH_MM = 300.0
MAIN_LENGTH_TOL_MM = 10.0
MAIN_MAX_SPREAD_GOAL_MM = 10.0

AB_TARGET_DELTA_MM = 90.0
BC_TARGET_DELTA_MM = 135.0
CD_TARGET_DELTA_MM = 180.0
S_BRIDGE_TARGET_LENGTH_MM = 18.0
S_BRIDGE_ALLOWED_LENGTH_MM = (15.0, 22.0)
STRONG_BRIDGE_TARGET_LENGTH_MM = 8.0

DUCT_CENTER_Z_MM = 5.0
TEARDROP_ROOF_RATIO = 1.5
PROFILE_DESIGN_SEGMENTS = 64

CHAMBER_CENTER_MM = (122.0, 75.0)
CHAMBER_RADIUS_MM = 8.0
CHAMBER_ROOF_HEIGHT_MM = 5.5
CHAMBER_NECK_OVERLAP_MM = 1.0
MIC_PORT_END_MM = (BODY_MAX_X_MM, CHAMBER_CENTER_MM[1])

# V8 uses a one-piece monolithic voxel solid. The air volume is subtracted from
# the block by a signed/implicit field sampled on a grid, then surfaced by
# marching cubes. This avoids external CAD boolean dependencies.


LANES = {
    "A": [
        (0.0, 120.0),
        (30.0, 120.0),
        (30.0, 133.5),
        (45.0, 133.5),
        (45.0, 120.0),
        (100.0, 120.0),
        (100.0, 102.0),
        (75.0, 102.0),  # A @ 170 mm
        (90.0, 102.0),
        (90.0, 116.9),
        (100.0, 116.9),
        (100.0, 102.0),
        (135.0, 102.0),
        (135.0, 87.7),
        (116.083, 87.689),
        (119.042, 81.345),
    ],
    "B": [
        (0.0, 94.0),
        (35.0, 94.0),
        (35.0, 96.5),
        (40.0, 96.5),
        (40.0, 94.0),
        (75.0, 94.0),  # B @ 80 mm
        (95.0, 94.0),
        (95.0, 112.0),
        (105.0, 112.0),
        (105.0, 94.0),
        (135.0, 94.0),
        (135.0, 82.0),
        (88.0, 82.0),  # B @ 235 mm
        (105.0, 82.0),
        (105.0, 98.5),
        (113.0, 98.5),
        (113.0, 82.0),
        (108.844, 79.788),
        (115.422, 77.394),
    ],
    "C": [
        (0.0, 68.0),
        (40.0, 68.0),
        (40.0, 74.0),
        (46.0, 74.0),
        (46.0, 68.0),
        (88.0, 68.0),  # C @ 100 mm
        (105.0, 68.0),
        (105.0, 82.0),
        (113.0, 82.0),
        (113.0, 68.0),
        (140.0, 68.0),
        (140.0, 58.0),
        (75.0, 58.0),  # C @ 255 mm
        (109.876, 68.0),
        (115.938, 71.5),
    ],
    "D": [
        (0.0, 44.0),
        (75.0, 44.0),  # D @ 75 mm
        (135.0, 44.0),
        (135.0, 32.0),
        (70.0, 32.0),
        (70.0, 52.0),
        (116.083, 52.0),
        (116.083, 62.311),
        (119.042, 68.655),
    ],
}

BRIDGES = {
    "AB_strong": {
        "type": "straight_strong",
        "from": "A",
        "to": "B",
        "from_path_mm": 170.0,
        "to_path_mm": 80.0,
        "target_delta_path_mm": AB_TARGET_DELTA_MM,
        "points": [(75.0, 102.0), (75.0, 94.0)],
    },
    "AB_sbridge": {
        "type": "s_shaped_medium",
        "from": "A",
        "to": "B",
        "from_path_mm": 170.0,
        "to_path_mm": 80.0,
        "target_delta_path_mm": AB_TARGET_DELTA_MM,
        "points": [(75.0, 102.0), (79.0, 100.0), (71.0, 96.0), (75.0, 94.0)],
    },
    "BC_sbridge": {
        "type": "s_shaped_medium",
        "from": "B",
        "to": "C",
        "from_path_mm": 235.0,
        "to_path_mm": 100.0,
        "target_delta_path_mm": BC_TARGET_DELTA_MM,
        "points": [(88.0, 82.0), (91.5, 78.5), (84.5, 71.5), (88.0, 68.0)],
    },
    "CD_sbridge": {
        "type": "s_shaped_medium",
        "from": "C",
        "to": "D",
        "from_path_mm": 255.0,
        "to_path_mm": 75.0,
        "target_delta_path_mm": CD_TARGET_DELTA_MM,
        "points": [(75.0, 58.0), (78.5, 54.5), (71.5, 47.5), (75.0, 44.0)],
    },
}

STATES = {
    "S0": {
        "filename": "V8_S0_no_bridges.stl",
        "enabled_bridges": [],
        "purpose": "No-bridge baseline; all main ducts meet only at the compact mixing chamber.",
    },
    "S1": {
        "filename": "V8_S1_AB_strong_only.stl",
        "enabled_bridges": ["AB_strong"],
        "purpose": "Single strong AB straight bridge control.",
    },
    "S2": {
        "filename": "V8_S2_AB_sbridge_only.stl",
        "enabled_bridges": ["AB_sbridge"],
        "purpose": "AB S bridge at the same duct positions as S1, isolating bridge geometry.",
    },
    "S3": {
        "filename": "V8_S3_BC_sbridge_only.stl",
        "enabled_bridges": ["BC_sbridge"],
        "purpose": "Single BC S bridge with medium path-difference target.",
    },
    "S4": {
        "filename": "V8_S4_CD_sbridge_only.stl",
        "enabled_bridges": ["CD_sbridge"],
        "purpose": "Single CD S bridge with larger path-difference target.",
    },
    "S5": {
        "filename": "V8_S5_AB_strong_BC_sbridge.stl",
        "enabled_bridges": ["AB_strong", "BC_sbridge"],
        "purpose": "Strong AB plus one medium S bridge.",
    },
    "S6": {
        "filename": "V8_S6_AB_strong_BC_CD_sbridges.stl",
        "enabled_bridges": ["AB_strong", "BC_sbridge", "CD_sbridge"],
        "purpose": "Mixed chain network: strong AB plus BC/CD S bridges.",
    },
    "S7": {
        "filename": "V8_S7_AB_BC_CD_all_sbridges.stl",
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


def chamber_volume_estimate_mm3():
    lower_half_ellipsoid = (2.0 / 3.0) * math.pi * CHAMBER_RADIUS_MM * CHAMBER_RADIUS_MM * (MAIN_DUCT_MODELED_DIAMETER_MM / 2.0)
    upper_cone = (1.0 / 3.0) * math.pi * CHAMBER_RADIUS_MM * CHAMBER_RADIUS_MM * CHAMBER_ROOF_HEIGHT_MM
    return lower_half_ellipsoid + upper_cone


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
    xs = np.arange(-VOXEL_MARGIN_MM, BODY_MAX_X_MM + VOXEL_MARGIN_MM + VOXEL_PITCH_MM * 0.5, VOXEL_PITCH_MM, dtype=np.float32)
    ys = np.arange(-VOXEL_MARGIN_MM, BODY_MAX_Y_MM + VOXEL_MARGIN_MM + VOXEL_PITCH_MM * 0.5, VOXEL_PITCH_MM, dtype=np.float32)
    zs = np.arange(-VOXEL_MARGIN_MM, BODY_MAX_Z_MM + VOXEL_MARGIN_MM + VOXEL_PITCH_MM * 0.5, VOXEL_PITCH_MM, dtype=np.float32)
    x, y, z = np.meshgrid(xs, ys, zs, indexing="ij")
    body = (x >= 0) & (x <= BODY_MAX_X_MM) & (y >= 0) & (y <= BODY_MAX_Y_MM) & (z >= 0) & (z <= BODY_MAX_Z_MM)
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
    q = np.sqrt((x - CHAMBER_CENTER_MM[0]) ** 2 + (y - CHAMBER_CENTER_MM[1]) ** 2)
    z_rel = z - DUCT_CENTER_Z_MM
    rz = MAIN_DUCT_MODELED_DIAMETER_MM / 2.0
    lower = (z_rel <= 0.0) & (((q / CHAMBER_RADIUS_MM) ** 2 + (z_rel / rz) ** 2) <= 1.0)
    upper = (z_rel > 0.0) & (z_rel <= CHAMBER_ROOF_HEIGHT_MM) & (q <= CHAMBER_RADIUS_MM * (1.0 - z_rel / CHAMBER_ROOF_HEIGHT_MM))
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
        add_polyline_air(m, x, y, z, bridge["points"], BRIDGE_MODELED_DIAMETER_MM)
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
        "bounds": np.round(mesh.bounds, 3).tolist(),
    }


def bridge_metadata():
    main_area = teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM)["area_mm2"]
    bridge_area = teardrop_props(BRIDGE_MODELED_DIAMETER_MM)["area_mm2"]
    out = {}
    enabled_by = {name: [] for name in BRIDGES}
    for state_name, state in STATES.items():
        for bridge_name in state["enabled_bridges"]:
            enabled_by[bridge_name].append(state_name)
    for name, bridge in BRIDGES.items():
        actual_from = point_at_path(LANES[bridge["from"]], bridge["from_path_mm"])
        actual_to = point_at_path(LANES[bridge["to"]], bridge["to_path_mm"])
        length = polyline_length(bridge["points"])
        ratio = relative_impedance_ratio(length, bridge_area)
        out[name] = {
            **bridge,
            "actual_from_point_mm": actual_from,
            "actual_to_point_mm": actual_to,
            "delta_path_mm": abs(bridge["from_path_mm"] - bridge["to_path_mm"]),
            "effective_centerline_length_mm": round(length, 3),
            "nominal_diameter_mm": BRIDGE_DIAMETER_MM,
            "modeled_diameter_mm": BRIDGE_MODELED_DIAMETER_MM,
            "cross_section_area_mm2": bridge_area,
            "hydraulic_diameter_mm": teardrop_props(BRIDGE_MODELED_DIAMETER_MM)["hydraulic_diameter_mm"],
            "relative_impedance_to_main_at_2khz": round(ratio, 3),
            "relative_coupling_strength_proxy_at_2khz": round(1.0 / ratio, 3) if ratio else None,
            "enabled_in": enabled_by[name],
            "main_area_reference_mm2": main_area,
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
            "within_200x160x30": all(span[i] <= bbox_limit[i] for i in range(3)),
            "within_p1s_volume": all(span[i] <= p1s_limit[i] for i in range(3)),
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

    report = {
        "stl_files": checks,
        "bbox_checks": bbox_checks,
        "all_within_200x160x30": all(v["within_200x160x30"] for v in bbox_checks.values()),
        "all_within_p1s_volume": all(v["within_p1s_volume"] for v in bbox_checks.values()),
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
        "s_bridge_lengths_within_15_22": {
            name: S_BRIDGE_ALLOWED_LENGTH_MM[0] <= bmeta[name]["effective_centerline_length_mm"] <= S_BRIDGE_ALLOWED_LENGTH_MM[1]
            for name in ["AB_sbridge", "BC_sbridge", "CD_sbridge"]
        },
        "ab_strong_shorter_than_ab_sbridge": bmeta["AB_strong"]["effective_centerline_length_mm"] < bmeta["AB_sbridge"]["effective_centerline_length_mm"],
        "ab_strong_and_sbridge_same_path_positions": (
            BRIDGES["AB_strong"]["from_path_mm"] == BRIDGES["AB_sbridge"]["from_path_mm"]
            and BRIDGES["AB_strong"]["to_path_mm"] == BRIDGES["AB_sbridge"]["to_path_mm"]
        ),
        "bc_and_cd_delta_different": bmeta["BC_sbridge"]["delta_path_mm"] != bmeta["CD_sbridge"]["delta_path_mm"],
        "all_bridge_points_at_least_50mm_from_inputs": all(
            min(b["from_path_mm"], b["to_path_mm"]) >= 50.0 for b in BRIDGES.values()
        ),
        "all_bridge_points_at_least_40mm_from_chamber_along_duct": all(
            (lengths[b["from"]] - b["from_path_mm"] >= 40.0) and (lengths[b["to"]] - b["to_path_mm"] >= 40.0)
            for b in BRIDGES.values()
        ),
        "same_duct_bridge_point_gaps_mm": lane_spacing,
        "same_duct_bridge_point_note": "AB_strong and AB_sbridge intentionally share the same A/B path positions for the strict S1-vs-S2 control and are deduplicated for spacing checks.",
        "same_duct_bridge_points_at_least_60mm_apart": all(all(g >= 60.0 for g in gaps) for gaps in lane_spacing.values()),
        "profile_design_segments_at_least_32": PROFILE_DESIGN_SEGMENTS >= 32,
        "closed_support_risk_note": "Internal channels use a documented self-supporting teardrop profile; no internal support material is intended. Inspect first layer and purge with air before acoustic tests.",
    }
    return report


def write_json_and_text(checks, validation):
    main_meta = main_duct_metadata()
    bridge_meta = bridge_metadata()
    main_lengths = {k: v["length_mm"] for k, v in main_meta.items()}
    bridge_area = teardrop_props(BRIDGE_MODELED_DIAMETER_MM)["area_mm2"]
    main_area = teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM)["area_mm2"]

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
            "dimensions_mm": [BODY_MAX_X_MM, BODY_MAX_Y_MM, BODY_MAX_Z_MM],
            "one_piece_print": True,
            "recommended_print_orientation": "flat on XY plane; channels run in-plane",
        },
        "cross_sections": {
            "main": teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM),
            "bridge": teardrop_props(BRIDGE_MODELED_DIAMETER_MM),
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
                "diameter_mm": BRIDGE_DIAMETER_MM,
                "modeled_diameter_mm": BRIDGE_MODELED_DIAMETER_MM,
                "cross_section_area_mm2": data["cross_section_area_mm2"],
                "hydraulic_diameter_mm": data["hydraulic_diameter_mm"],
                "effective_length_mm": data["effective_centerline_length_mm"],
                "enabled_in": data["enabled_in"],
                "centerline_points_mm": data["points"],
                "relative_impedance_to_main_at_2khz": data["relative_impedance_to_main_at_2khz"],
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
            "type": "compact_teardrop_dome",
            "center_mm": CHAMBER_CENTER_MM,
            "equatorial_radius_mm": CHAMBER_RADIUS_MM,
            "roof_height_mm": CHAMBER_ROOF_HEIGHT_MM,
            "estimated_volume_mm3": round(chamber_volume_estimate_mm3(), 3),
            "input_connection_points_mm": {lane: points[-1] for lane, points in LANES.items()},
            "note": "Small compact chamber intended to reduce output-end coupling relative to the old V6 large chamber.",
        },
        "ports": {
            "inputs": {lane: {"point_mm": points[0], "diameter_mm": MAIN_DUCT_DIAMETER_MM, "modeled_diameter_mm": MAIN_DUCT_MODELED_DIAMETER_MM} for lane, points in LANES.items()},
            "mic_output": {"from_mm": CHAMBER_CENTER_MM, "to_mm": MIC_PORT_END_MM, "diameter_mm": MIC_PORT_DIAMETER_MM, "modeled_diameter_mm": MIC_PORT_MODELED_DIAMETER_MM},
        },
    }
    (OUT / "sim_params_v8.json").write_text(json.dumps(sim, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "V8 acoustic network model parameters",
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
        "Outer dimensions and STL checks",
    ]
    for file, result in checks.items():
        span = validation["bbox_checks"][file]["span_mm"]
        lines.append(f"- {file}: bbox span {span} mm, watertight={result['watertight']}, within P1S={validation['bbox_checks'][file]['within_p1s_volume']}")
    lines += [
        f"- Recommended max envelope satisfied: {validation['all_within_200x160x30']}",
        "",
        "Main duct parameters",
        f"- Nominal diameter: {MAIN_DUCT_DIAMETER_MM} mm",
        f"- Modeled equivalent diameter: {MAIN_DUCT_MODELED_DIAMETER_MM} mm",
        f"- Cross-section: {teardrop_props(MAIN_DUCT_MODELED_DIAMETER_MM)}",
    ]
    for lane, data in main_meta.items():
        lines.append(f"- {lane}: length {data['length_mm']} mm, points {data['centerline_points_mm']}")
    lines += [
        f"- Main duct maximum length difference: {validation['main_length_spread_mm']} mm",
        "",
        "Bridge parameters",
    ]
    for name, data in bridge_meta.items():
        lines.append(
            f"- {name}: type={data['type']}, connects {data['from']}@{data['from_path_mm']} mm to "
            f"{data['to']}@{data['to_path_mm']} mm, delta={data['delta_path_mm']} mm, "
            f"target_delta={data['target_delta_path_mm']} mm, effective_length={data['effective_centerline_length_mm']} mm, "
            f"area={bridge_area} mm2, hydraulic_diameter={data['hydraulic_diameter_mm']} mm, "
            f"relative_impedance_at_2khz={data['relative_impedance_to_main_at_2khz']}, enabled_in={data['enabled_in']}"
        )
    lines += [
        "",
        "Mixing chamber",
        f"- Type: compact teardrop dome, center {CHAMBER_CENTER_MM}, equatorial radius {CHAMBER_RADIUS_MM} mm",
        f"- Estimated volume: {chamber_volume_estimate_mm3():.1f} mm3",
        f"- Mic port modeled diameter: {MIC_PORT_MODELED_DIAMETER_MM} mm",
        f"- Input duct connection positions: {json.dumps({lane: points[-1] for lane, points in LANES.items()})}",
        "",
        "State versions",
    ]
    for name, state in STATES.items():
        lines.append(f"- {name}: {state['filename']}, bridges={state['enabled_bridges']}, purpose={state['purpose']}")
    (OUT / "model_params_v8.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    rationale = f"""V8 design rationale
===================

Purpose
-------
V8 is an early mechanism-validation prototype for asking whether internal
interconnects improve spatial/frequency coding from four input ports A/B/C/D to
one microphone output. It is not a final optimized acoustic product.

Main duct length scale
----------------------
The main ducts are kept near 300 mm to create several observable frequency-domain
features in the 0-8 kHz range. A rough modal spacing estimate is:

delta_f ~= c / (2L)

with c = 343 m/s and L ~= 0.30 m:

delta_f ~= 343 / (2 * 0.30) ~= 572 Hz

This gives multiple peaks/valleys across 0-8 kHz, supporting transfer-function
coding experiments.

Bridge choices
--------------
AB_strong is retained as a short direct bridge to test whether strong coupling
helps separability or over-mixes the ports. AB_sbridge connects the exact same
A@170 mm and B@80 mm duct positions, but replaces the short bridge with an
S-shaped medium-coupling bridge. S1 vs S2 is therefore a strict geometry-type
comparison at the same path-difference target.

BC_sbridge and CD_sbridge are generated as single-bridge controls so that the
effect of different path differences can be tested independently. S6 and S7
compare a mixed strong+S chain against an all-S chain:

- S6 = AB_strong + BC_sbridge + CD_sbridge
- S7 = AB_sbridge + BC_sbridge + CD_sbridge

This asks whether the strong bridge is necessary or instead causes excessive
coupling.

Path-difference targets
-----------------------
The chosen targets are AB=90 mm, BC=135 mm, CD=180 mm. Their approximate
interference-period scales are:

- delta_L = 90 mm  -> delta_f ~= 343 / 0.090 ~= 3.81 kHz
- delta_L = 135 mm -> delta_f ~= 343 / 0.135 ~= 2.54 kHz
- delta_L = 180 mm -> delta_f ~= 343 / 0.180 ~= 1.91 kHz

Using different path differences reduces repeated spectral structure and should
make the four port transfer functions less correlated if the coupling mechanism
is useful.

Bridge impedance estimate
-------------------------
Bridge inertance can be approximated as:

Z_bridge ~= j * omega * rho * L_bridge / A_bridge

The main duct characteristic impedance is roughly:

Z_main ~= rho * c / A_main

So:

|Z_bridge| / Z_main ~= k * L_bridge * A_main / A_bridge

where k = 2*pi*f/c. Increasing bridge length increases impedance and reduces
coupling strength. The S bridges increase effective length relative to the short
AB_strong bridge, turning the bridge from strong coupling into medium coupling.

No DA bridge
------------
V8 preserves the chain A--B--C--D and avoids DA closure to prevent a strongly
closed loop from dominating the early mechanism-validation experiment.

Manufacturing interpretation
----------------------------
The one-piece V8 STL uses self-supporting near-circular teardrop channels rather
than unsupported horizontal circular tunnels. The cross-section areas and
hydraulic diameters are recorded in model_params_v8.txt and sim_params_v8.json.
"""
    (OUT / "design_rationale_v8.txt").write_text(rationale, encoding="utf-8")

    readme = """V8 acoustic network engineering package
=======================================

Design purpose
--------------
V8 is a one-piece early mechanism-validation coupon for comparing no bridge,
single strong bridge, single S bridge, different S-bridge path differences,
mixed strong+S networks, and all-S networks.

STL files
---------
- V8_S0_no_bridges.stl: baseline with no bridge.
- V8_S1_AB_strong_only.stl: AB strong straight bridge only.
- V8_S2_AB_sbridge_only.stl: AB S bridge only, same duct positions as S1.
- V8_S3_BC_sbridge_only.stl: BC S bridge only.
- V8_S4_CD_sbridge_only.stl: CD S bridge only.
- V8_S5_AB_strong_BC_sbridge.stl: AB strong plus BC S bridge.
- V8_S6_AB_strong_BC_CD_sbridges.stl: AB strong plus BC/CD S bridges.
- V8_S7_AB_BC_CD_all_sbridges.stl: AB/BC/CD all S bridges.

Printing
--------
- Print flat on the XY plane.
- Use PLA on Bambu Lab P1S with a 0.4 mm nozzle.
- Internal support is not intended; channels use a self-supporting teardrop profile.
- Inspect the sliced preview carefully for port blockage, stringing, and thin features.
- Purge all ports with air before acoustic measurement.

Experiment setup
----------------
- Fix the microphone at the right-side mic output.
- Connect the speaker to A/B/C/D in sequence.
- Seal inactive input ports with the same external cap method for every trial.
- Recommended signal: log chirp 300 Hz-10 kHz, analyze 500 Hz-8 kHz.
- White noise can be used as a repeatability/control signal.

Recommended state order
-----------------------
S0, S1, S2, S3, S4, S5, S6, S7.

Primary metrics
---------------
- Transfer-function correlation matrix.
- Maximum off-diagonal correlation.
- Effective rank.
- Energy-normalized nearest-neighbor classification.
- Repeatability.
- Insertion loss.

Important warning
-----------------
V8 is not a final acoustic optimization. It has not yet been experimentally
validated for print cleanliness, leakage, or measured transfer functions.
"""
    (OUT / "README_v8.txt").write_text(readme, encoding="utf-8")

    vlines = ["V8 validation report", ""]
    for key, value in validation.items():
        vlines.append(f"{key}: {value}")
    (OUT / "validation_report_v8.txt").write_text("\n".join(vlines) + "\n", encoding="utf-8")


def write_package_zip():
    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()
    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.iterdir():
            if p.name == PACKAGE_ZIP.name or p.name == "__pycache__":
                continue
            z.write(p, p.relative_to(OUT.parent))


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

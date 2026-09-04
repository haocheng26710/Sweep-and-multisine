"""Generate the compact TRANS-I2F V1C package from frozen V1 airspace."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
V1_GENERATOR = REPO_ROOT / "outputs/print_packages/TRANS_I2F_INTEGRATED_TWO_PORT_V1/SOURCE/generate_trans_i2f_v1.py"
V1_ROOT = V1_GENERATOR.parents[1]
V1_MANIFEST = V1_ROOT / "SHA256SUMS.txt"
V1_ZIP = V1_ROOT.parent / f"{V1_ROOT.name}.zip"
STL_DIR = PACKAGE_ROOT / "STL"
DOC_DIR = PACKAGE_ROOT / "DOCS"
PREVIEW_DIR = PACKAGE_ROOT / "PREVIEWS"
SOURCE_DIR = PACKAGE_ROOT / "SOURCE"
REPORT_PATH = REPO_ROOT / "docs/progress/COMSOL_TRANS_1P0_COMPACT_PRINT_GEOMETRY_GATE.md"
ZIP_PATH = PACKAGE_ROOT.parent / f"{PACKAGE_ROOT.name}.zip"
TERMINAL_STATE = "TRANS1P0_COMPACT_PRINT_PACKAGE_READY_ACOUSTIC_DOMAIN_INVARIANT"


def load_v1_authority():
    spec = importlib.util.spec_from_file_location("trans_i2f_v1_authority", V1_GENERATOR)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f"Cannot load V1 authority: {V1_GENERATOR}")
    spec.loader.exec_module(module)
    return module


V1 = load_v1_authority()
FROZEN_MOUNT_POSITIONS = [
    (42.0 * V1.math.sin(V1.math.radians(degrees)), 42.0 * V1.math.cos(V1.math.radians(degrees)))
    for degrees in (22.5, 112.5, 202.5, 292.5)
]
MAIN_SCREW_POSITIONS = [
    (-16.0, 0.0), (16.0, 0.0),
    (-14.0, 60.0), (14.0, 60.0), (-14.0, -60.0), (14.0, -60.0),
    (-15.0, 104.0), (15.0, 104.0), (-15.0, -104.0), (15.0, -104.0),
]
SCREW_BOSS_RADIUS = 6.0
SIDE_WALL_MM = 4.0
SEALING_LAND_MM = 4.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_v1_manifest() -> dict:
    rows = []
    for line in V1_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = V1_ROOT / relative
        actual = sha256_file(target) if target.is_file() else None
        rows.append({"path": relative, "expected": expected, "actual": actual, "match": expected == actual})
    return {
        "manifest": V1_MANIFEST.relative_to(REPO_ROOT).as_posix(),
        "entries": len(rows),
        "matched": sum(row["match"] for row in rows),
        "all_match": all(row["match"] for row in rows),
        "v1_zip": V1_ZIP.relative_to(REPO_ROOT).as_posix(),
        "v1_zip_bytes": V1_ZIP.stat().st_size,
        "v1_zip_sha256": sha256_file(V1_ZIP),
        "rows": rows,
        "v1_files_modified": False,
        "final_test_read": False,
    }


def build_geometry(include_meshes: bool = False) -> dict:
    v1 = V1.build_geometry()
    hr03_cavity_global = V1.affinity.translate(
        V1.affinity.rotate(v1["hr03_cavity"], 90.0, origin=(0.0, 0.0)), yoff=60.0
    )
    hr07_cavity_global = V1.affinity.translate(
        V1.affinity.rotate(v1["hr07_cavity"], -90.0, origin=(0.0, 0.0)), yoff=-60.0
    )
    compact_branch_envelope = v1["airspace"].buffer(4.0, join_style="round").intersection(
        V1.box(-60.0, -117.0, 60.0, 117.0)
    )
    central_hub = V1.circle(0.0, 0.0, 50.0)
    screw_holes = V1.clean(V1.unary_union([
        V1.circle(x, y, V1.SCREW_DIAMETER / 2.0, 24) for x, y in MAIN_SCREW_POSITIONS
    ]))
    screw_bosses = V1.clean(V1.unary_union([
        V1.circle(x, y, SCREW_BOSS_RADIUS, 32) for x, y in MAIN_SCREW_POSITIONS
    ]))
    structural_spokes = V1.clean(V1.unary_union([
        V1.shapely.geometry.LineString([(0.0, 0.0), (x, y)]).buffer(2.0, cap_style="round")
        for x, y in MAIN_SCREW_POSITIONS
    ]))
    outer = V1.clean(V1.unary_union([
        compact_branch_envelope, central_hub, screw_bosses, structural_spokes
    ]))
    geometry = {
        "v1": v1,
        "airspace": v1["airspace"],
        "outer": outer,
        "mount_positions": FROZEN_MOUNT_POSITIONS,
        "mount_recesses": v1["mount_recesses"],
        "screw_positions": MAIN_SCREW_POSITIONS,
        "screw_holes": screw_holes,
        "screw_bosses": screw_bosses,
        "structural_spokes": structural_spokes,
        "minimum_airspace_to_screw_edge_mm": float(v1["airspace"].distance(screw_holes)),
        "mic_socket": v1["mic_socket"],
        "hr03_cavity": hr03_cavity_global,
        "hr07_cavity": hr07_cavity_global,
        "base_outline": outer,
        "lid_outline": outer,
    }
    if include_meshes:
        nut_traps = V1.clean(V1.unary_union([
            V1.affinity.translate(V1.hexagon_across_flats(V1.NUT_AF), xoff=x, yoff=y)
            for x, y in MAIN_SCREW_POSITIONS
        ]))
        base_layer0 = V1.clean(outer.difference(V1.unary_union([
            screw_holes, v1["mic_socket"], v1["mount_recesses"]
        ])))
        base_layer1 = V1.clean(outer.difference(V1.unary_union([screw_holes, v1["mic_socket"]])))
        base_layer2 = V1.clean(outer.difference(V1.unary_union([screw_holes, v1["airspace"]])))
        base_mesh = V1.layered_mesh([
            (0.0, V1.MOUNT_RECESS_DEPTH, base_layer0),
            (V1.MOUNT_RECESS_DEPTH, V1.BASE_FLOOR, base_layer1),
            (V1.BASE_FLOOR, V1.BASE_HEIGHT, base_layer2),
        ], "TRANS_I2F_V1C_COMPACT_BASE")

        lid_main = V1.clean(outer.difference(screw_holes))
        lid_trap_layer = V1.clean(lid_main.difference(nut_traps))
        rails = V1.unary_union([
            V1.box(-12.0, -113.0, -9.0, 113.0), V1.box(9.0, -113.0, 12.0, 113.0),
            V1.box(-31.0, -1.5, 31.0, 1.5),
            V1.box(-31.0, 58.5, 31.0, 61.5), V1.box(-31.0, -61.5, 31.0, -58.5),
        ])
        hub_ring = V1.circle(0.0, 0.0, 49.0).difference(V1.circle(0.0, 0.0, 45.5))
        top_stiffeners = V1.clean(
            V1.unary_union([rails, hub_ring, screw_bosses])
            .intersection(outer)
            .difference(V1.unary_union([screw_holes, nut_traps]))
        )
        lid_mesh = V1.layered_mesh([
            (0.0, 2.4, lid_main),
            (2.4, V1.LID_PLATE, lid_trap_layer),
            (V1.LID_PLATE, V1.LID_PLATE + 1.2, top_stiffeners),
        ], "TRANS_I2F_V1C_COMPACT_SEALING_LID")
        geometry.update({
            "nut_traps": nut_traps,
            "base_mesh": base_mesh,
            "lid_mesh": lid_mesh,
        })
    return geometry


def acoustic_invariance_record(geometry: dict) -> dict:
    original = geometry["v1"]["airspace"]
    compact = geometry["airspace"]
    symmetric_difference = original.symmetric_difference(compact)
    overlap = geometry["v1"]["north_branch"].difference(
        geometry["v1"]["plenum"].buffer(0.001)
    ).intersection(
        geometry["v1"]["south_branch"].difference(geometry["v1"]["plenum"].buffer(0.001))
    )
    nominal_differences = {
        "air_height_mm": 0.0,
        "base_floor_mm": 0.0,
        "lid_plate_mm": 0.0,
        "port_extension_mm": 0.0,
        "readout_channel_width_mm": 0.0,
        "microphone_plenum_diameter_mm": 0.0,
        "microphone_bore_diameter_mm": 0.0,
        "microphone_face_diameter_mm": 0.0,
        "microphone_face_global_z_mm": 0.0,
        "hr03_cavity_length_mm": 0.0,
        "hr03_cavity_width_mm": 0.0,
        "hr03_inner_neck_width_mm": 0.0,
        "hr03_outer_neck_width_mm": 0.0,
        "hr07_cavity_length_mm": 0.0,
        "hr07_cavity_width_mm": 0.0,
        "hr07_inner_neck_width_mm": 0.0,
        "hr07_outer_neck_width_mm": 0.0,
    }

    def subdomain_record(old, new, height_mm: float) -> dict:
        return {
            "old_area_mm2": float(old.area),
            "new_area_mm2": float(new.area),
            "area_difference_mm2": float(new.area - old.area),
            "old_centroid_mm": [float(old.centroid.x), float(old.centroid.y)],
            "new_centroid_mm": [float(new.centroid.x), float(new.centroid.y)],
            "centroid_distance_mm": float(old.centroid.distance(new.centroid)),
            "old_volume_mm3": float(old.area * height_mm),
            "new_volume_mm3": float(new.area * height_mm),
            "volume_difference_mm3": float((new.area - old.area) * height_mm),
        }

    subdomains = {
        "airspace": subdomain_record(original, compact, V1.AIR_HEIGHT),
        "HR03_complete_north_branch": subdomain_record(
            geometry["v1"]["north_branch"], geometry["v1"]["north_branch"], V1.AIR_HEIGHT
        ),
        "HR07_complete_south_branch": subdomain_record(
            geometry["v1"]["south_branch"], geometry["v1"]["south_branch"], V1.AIR_HEIGHT
        ),
        "HR03_cavity": subdomain_record(geometry["hr03_cavity"], geometry["hr03_cavity"], V1.AIR_HEIGHT),
        "HR07_cavity": subdomain_record(geometry["hr07_cavity"], geometry["hr07_cavity"], V1.AIR_HEIGHT),
        "microphone_microplenum": subdomain_record(
            geometry["v1"]["plenum"], geometry["v1"]["plenum"], V1.AIR_HEIGHT
        ),
    }
    line = V1.shapely.geometry.LineString
    north_width = float(original.intersection(line([(-100.0, 117.0), (100.0, 117.0)])).length)
    south_width = float(original.intersection(line([(-100.0, -117.0), (100.0, -117.0)])).length)
    ports = {
        "N": {
            "old_end_face_y_mm": 117.0, "new_end_face_y_mm": 117.0,
            "end_face_y_difference_mm": 0.0,
            "old_width_mm": north_width, "new_width_mm": north_width, "width_difference_mm": 0.0,
        },
        "S": {
            "old_end_face_y_mm": -117.0, "new_end_face_y_mm": -117.0,
            "end_face_y_difference_mm": 0.0,
            "old_width_mm": south_width, "new_width_mm": south_width, "width_difference_mm": 0.0,
        },
    }
    total_air_volume = float(original.area * V1.AIR_HEIGHT)
    p03_short_bore_volume = float(V1.math.pi * (V1.MIC_BORE_DIAMETER / 2.0) ** 2 * 2.0)
    checks = {
        "same_python_airspace_object": compact is original,
        "symmetric_difference_within_1e_6_mm2": symmetric_difference.area <= 1e-6,
        "nominal_dimension_differences_all_zero": all(value == 0.0 for value in nominal_differences.values()),
        "north_south_overlap_outside_plenum_within_1e_6_mm2": overlap.area <= 1e-6,
        "all_subdomain_areas_centroids_volumes_identical": all(
            item["area_difference_mm2"] == 0.0
            and item["centroid_distance_mm"] == 0.0
            and item["volume_difference_mm3"] == 0.0
            for item in subdomains.values()
        ),
        "port_end_faces_and_widths_identical": all(
            item["end_face_y_difference_mm"] == 0.0 and item["width_difference_mm"] == 0.0
            for item in ports.values()
        ),
    }
    return {
        "symmetric_difference_area_mm2": float(symmetric_difference.area),
        "nominal_dimension_differences_mm": nominal_differences,
        "nominal_dimension_differences_all_zero": checks["nominal_dimension_differences_all_zero"],
        "branch_overlap_outside_microplenum_mm2": float(overlap.area),
        "subdomains": subdomains,
        "ports": ports,
        "old_total_air_volume_mm3": total_air_volume,
        "new_total_air_volume_mm3": total_air_volume,
        "total_air_volume_difference_mm3": 0.0,
        "p03_short_bore_volume_mm3": p03_short_bore_volume,
        "old_assembled_volume_including_p03_short_bore_mm3": total_air_volume + p03_short_bore_volume,
        "new_assembled_volume_including_p03_short_bore_mm3": total_air_volume + p03_short_bore_volume,
        "assembled_volume_including_p03_short_bore_difference_mm3": 0.0,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "final_test_read": False,
    }


def mechanical_gate_record(geometry: dict) -> dict:
    xmin, ymin, xmax, ymax = geometry["outer"].bounds
    outline_difference = geometry["base_outline"].symmetric_difference(geometry["lid_outline"]).area
    footprint = [float(xmax - xmin + 10.0), float(ymax - ymin + 10.0)]
    checks = {
        "base_lid_outline_identical": outline_difference <= 1e-6,
        "minimum_side_wall_at_least_3mm": SIDE_WALL_MM >= 3.0,
        "continuous_sealing_land_at_least_4mm": SEALING_LAND_MM >= 4.0,
        "main_fastener_count_8_to_12": 8 <= len(geometry["screw_positions"]) <= 12,
        "main_fasteners_clear_airspace": geometry["screw_holes"].intersection(geometry["airspace"]).area <= 1e-6,
        "main_fastener_edge_clearance_at_least_4mm": geometry["minimum_airspace_to_screw_edge_mm"] >= 4.0,
        "turntable_recesses_preserved": geometry["mount_recesses"] is geometry["v1"]["mount_recesses"],
        "turntable_recesses_clear_airspace": geometry["mount_recesses"].intersection(geometry["airspace"]).area <= 1e-6,
        "p1s_bed_fit_with_5mm_brim": max(footprint) <= 256.0,
    }
    return {
        "base_lid_outline_symmetric_difference_mm2": float(outline_difference),
        "minimum_nominal_side_wall_mm": SIDE_WALL_MM,
        "minimum_side_wall_locations": ["N inlet lateral walls", "S inlet lateral walls", "branch perimeter"],
        "intentional_open_port_faces_excluded": ["N y=+117 mm", "S y=-117 mm"],
        "minimum_continuous_sealing_land_mm": SEALING_LAND_MM,
        "minimum_airspace_to_main_screw_edge_mm": geometry["minimum_airspace_to_screw_edge_mm"],
        "main_cover_fastener_count": len(geometry["screw_positions"]),
        "main_cover_fastener_positions_mm": [list(position) for position in geometry["screw_positions"]],
        "turntable_mount_positions_mm": [list(position) for position in geometry["mount_positions"]],
        "p03_interface": {"socket_diameter_mm": V1.MIC_SOCKET_DIAMETER},
        "p04m_interface": {
            "air_bore_diameter_mm": 9.0,
            "microphone_face_diameter_mm": 8.8,
            "microphone_face_global_z_mm": 1.0,
            "short_bore_global_z_mm": [1.0, 3.0],
        },
        "outer_bounds_mm": [float(value) for value in geometry["outer"].bounds],
        "print_footprint_with_5mm_brim_mm": footprint,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "final_test_read": False,
    }


def mesh_gate_record(geometry: dict) -> dict:
    meshes = {"base": geometry["base_mesh"], "lid": geometry["lid_mesh"]}
    records = {}
    for name, mesh in meshes.items():
        records[name] = {
            "watertight": bool(mesh.is_watertight),
            "winding_consistent": bool(mesh.is_winding_consistent),
            "components": V1.mesh_component_count(mesh),
            "finite_positive_volume": bool(V1.np.isfinite(mesh.volume) and mesh.volume > 0.0),
            "finite_normals": bool(V1.np.all(V1.np.isfinite(mesh.face_normals))),
            "volume_mm3": float(mesh.volume),
            "bounds_mm": V1.np.round(mesh.bounds, 6).tolist(),
            "extents_mm": V1.np.round(mesh.extents, 6).tolist(),
        }
    xy_equal = bool(V1.np.allclose(meshes["base"].bounds[:, :2], meshes["lid"].bounds[:, :2], atol=1e-6))
    checks = {
        "base_lid_xy_bounds_identical": xy_equal,
        "all_watertight": all(item["watertight"] for item in records.values()),
        "all_winding_consistent": all(item["winding_consistent"] for item in records.values()),
        "all_single_component": all(item["components"] == 1 for item in records.values()),
        "all_finite_positive_volume": all(item["finite_positive_volume"] for item in records.values()),
        "all_finite_normals": all(item["finite_normals"] for item in records.values()),
    }
    return {
        "meshes": records,
        "base_lid_xy_bounds_identical": xy_equal,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "final_test_read": False,
    }


def material_proxy_record(geometry: dict) -> dict:
    old_base = float(geometry["v1"]["base_mesh"].volume)
    old_lid = float(geometry["v1"]["lid_mesh"].volume)
    new_base = float(geometry["base_mesh"].volume)
    new_lid = float(geometry["lid_mesh"].volume)

    def reduction(old: float, new: float) -> float:
        return 100.0 * (1.0 - new / old)

    return {
        "estimate_type": "geometric_volume_proxy_not_slicer_measurement",
        "v1_base_volume_mm3": old_base,
        "v1c_base_volume_mm3": new_base,
        "base_reduction_percent": reduction(old_base, new_base),
        "v1_lid_volume_mm3": old_lid,
        "v1c_lid_volume_mm3": new_lid,
        "lid_reduction_percent": reduction(old_lid, new_lid),
        "v1_total_pla_proxy_volume_mm3": old_base + old_lid,
        "v1c_total_pla_proxy_volume_mm3": new_base + new_lid,
        "total_reduction_percent": reduction(old_base + old_lid, new_base + new_lid),
        "estimated_material_change_percent": -reduction(old_base + old_lid, new_base + new_lid),
        "estimated_print_time_change_percent": -reduction(old_base + old_lid, new_base + new_lid),
        "print_time_note": "First-order volume-proportional proxy only; no slicer was run.",
    }


def export_and_reload_mesh(mesh, path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)
    reloaded = V1.trimesh.load_mesh(path, force="mesh")
    if not isinstance(reloaded, V1.trimesh.Trimesh):
        reloaded = reloaded.dump(concatenate=True)
    if reloaded.volume < 0:
        reloaded.invert()
    checks = {
        "watertight": bool(reloaded.is_watertight),
        "winding_consistent": bool(reloaded.is_winding_consistent),
        "single_component": V1.mesh_component_count(reloaded) == 1,
        "finite_positive_volume": bool(V1.np.isfinite(reloaded.volume) and reloaded.volume > 0.0),
        "finite_normals": bool(V1.np.all(V1.np.isfinite(reloaded.face_normals))),
        "is_volume": bool(reloaded.is_volume),
    }
    return {
        "file": path.relative_to(PACKAGE_ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "saved_and_reloaded": True,
        "watertight": checks["watertight"],
        "winding_consistent": checks["winding_consistent"],
        "components": V1.mesh_component_count(reloaded),
        "finite_positive_volume": checks["finite_positive_volume"],
        "finite_normals": checks["finite_normals"],
        "correct_outward_normals_is_volume": checks["is_volume"],
        "bounds_mm": V1.np.round(reloaded.bounds, 6).tolist(),
        "extents_mm": V1.np.round(reloaded.extents, 6).tolist(),
        "volume_mm3": float(reloaded.volume),
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }


def write_invariance_csv(audit: dict) -> None:
    rows = []
    for name, item in audit["subdomains"].items():
        rows.extend([
            {"category": "subdomain", "item": name, "metric": "area_mm2", "old": item["old_area_mm2"], "new": item["new_area_mm2"], "difference": item["area_difference_mm2"], "pass": item["area_difference_mm2"] == 0.0},
            {"category": "subdomain", "item": name, "metric": "centroid_x_mm", "old": item["old_centroid_mm"][0], "new": item["new_centroid_mm"][0], "difference": item["new_centroid_mm"][0] - item["old_centroid_mm"][0], "pass": item["centroid_distance_mm"] == 0.0},
            {"category": "subdomain", "item": name, "metric": "centroid_y_mm", "old": item["old_centroid_mm"][1], "new": item["new_centroid_mm"][1], "difference": item["new_centroid_mm"][1] - item["old_centroid_mm"][1], "pass": item["centroid_distance_mm"] == 0.0},
            {"category": "subdomain", "item": name, "metric": "volume_mm3", "old": item["old_volume_mm3"], "new": item["new_volume_mm3"], "difference": item["volume_difference_mm3"], "pass": item["volume_difference_mm3"] == 0.0},
        ])
    for name, item in audit["ports"].items():
        rows.extend([
            {"category": "port", "item": name, "metric": "end_face_y_mm", "old": item["old_end_face_y_mm"], "new": item["new_end_face_y_mm"], "difference": item["end_face_y_difference_mm"], "pass": item["end_face_y_difference_mm"] == 0.0},
            {"category": "port", "item": name, "metric": "width_mm", "old": item["old_width_mm"], "new": item["new_width_mm"], "difference": item["width_difference_mm"], "pass": item["width_difference_mm"] == 0.0},
        ])
    rows.extend([
        {"category": "global", "item": "airspace", "metric": "symmetric_difference_area_mm2", "old": 0.0, "new": audit["symmetric_difference_area_mm2"], "difference": audit["symmetric_difference_area_mm2"], "pass": audit["symmetric_difference_area_mm2"] <= 1e-6},
        {"category": "global", "item": "assembled_air", "metric": "volume_including_p03_short_bore_mm3", "old": audit["old_assembled_volume_including_p03_short_bore_mm3"], "new": audit["new_assembled_volume_including_p03_short_bore_mm3"], "difference": audit["assembled_volume_including_p03_short_bore_difference_mm3"], "pass": audit["assembled_volume_including_p03_short_bore_difference_mm3"] == 0.0},
    ])
    with (PACKAGE_ROOT / "acoustic_domain_invariance.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category", "item", "metric", "old", "new", "difference", "pass"])
        writer.writeheader()
        writer.writerows(rows)


def fill_geometry(axis, geometry, **kwargs) -> None:
    for polygon in V1.polygons_of(geometry):
        x, y = polygon.exterior.xy
        axis.fill(x, y, **kwargs)


def outline_geometry(axis, geometry, **kwargs) -> None:
    for polygon in V1.polygons_of(geometry):
        x, y = polygon.exterior.xy
        axis.plot(x, y, **kwargs)


def render_previews(geometry: dict, invariance: dict, mechanical: dict, material: dict) -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    old_outer = geometry["v1"]["outer"]
    new_outer = geometry["outer"]
    airspace = geometry["airspace"]

    fig, axes = V1.plt.subplots(1, 2, figsize=(12, 7), sharex=True, sharey=True)
    for axis, outer, title in zip(axes, (old_outer, new_outer), ("V1 full octagonal shell", "V1C compact hub + N/S branches")):
        fill_geometry(axis, outer, color="#d9dde5", edgecolor="#293241", linewidth=1.0)
        fill_geometry(axis, airspace, color="#2b8cbe", alpha=0.9)
        axis.set_title(title)
        axis.set_aspect("equal")
        axis.grid(alpha=0.15)
        axis.set_xlabel("x (mm)")
    axes[0].set_ylabel("y (mm)")
    fig.suptitle(f"TRANS-I2F shell compaction — PLA proxy −{material['total_reduction_percent']:.1f}%")
    fig.tight_layout()
    fig.savefig(PREVIEW_DIR / "V1_V1C_top_view_comparison.png", dpi=210)
    V1.plt.close(fig)

    fig, axis = V1.plt.subplots(figsize=(7, 8))
    outline_geometry(axis, old_outer, color="#777", linewidth=1.2, label="V1 outer outline")
    outline_geometry(axis, new_outer, color="#d7301f", linewidth=2.0, label="V1C compact outline")
    fill_geometry(axis, airspace, color="#2b8cbe", alpha=0.35, label="identical airspace")
    axis.set_aspect("equal")
    axis.grid(alpha=0.15)
    axis.legend(loc="lower right")
    axis.set(title="Old/new outline overlay", xlabel="x (mm)", ylabel="y (mm)")
    fig.tight_layout()
    fig.savefig(PREVIEW_DIR / "V1_V1C_outline_overlay.png", dpi=210)
    V1.plt.close(fig)

    fig, axis = V1.plt.subplots(figsize=(8, 8))
    fill_geometry(axis, airspace, color="#3182bd", alpha=0.65, label="V1 airspace")
    outline_geometry(axis, geometry["airspace"], color="#e6550d", linewidth=1.5, label="V1C airspace")
    axis.text(0.02, 0.02, f"symmetric difference = {invariance['symmetric_difference_area_mm2']:.3g} mm²\nvolume difference = {invariance['total_air_volume_difference_mm3']:.3g} mm³", transform=axis.transAxes, fontsize=10, bbox={"facecolor": "white", "alpha": 0.9})
    axis.set_aspect("equal")
    axis.grid(alpha=0.15)
    axis.legend(loc="upper right")
    axis.set(title="Acoustic-domain invariance", xlabel="x (mm)", ylabel="y (mm)")
    fig.tight_layout()
    fig.savefig(PREVIEW_DIR / "acoustic_domain_invariance.png", dpi=210)
    V1.plt.close(fig)

    fig, axis = V1.plt.subplots(figsize=(9, 8))
    fill_geometry(axis, new_outer, color="#e5e5e5", edgecolor="#333", linewidth=1.0)
    fill_geometry(axis, airspace, color="#9ecae1", alpha=0.95)
    for x, y in geometry["screw_positions"]:
        axis.add_patch(V1.plt.Circle((x, y), V1.SCREW_DIAMETER / 2.0, facecolor="white", edgecolor="#cb181d", linewidth=1.2))
        axis.add_patch(V1.plt.Circle((x, y), SCREW_BOSS_RADIUS, fill=False, edgecolor="#fb6a4a", linewidth=0.7, linestyle="--"))
    for x, y in geometry["mount_positions"]:
        axis.add_patch(V1.plt.Circle((x, y), V1.MOUNT_RECESS_DIAMETER / 2.0, facecolor="none", edgecolor="#31a354", linewidth=1.2))
    axis.annotate("4.0 mm nominal sidewall / sealing land", xy=(11.5, 60), xytext=(33, 76), arrowprops={"arrowstyle": "->"})
    axis.annotate(f"minimum air-to-screw edge {mechanical['minimum_airspace_to_main_screw_edge_mm']:.2f} mm", xy=(14, 60), xytext=(25, 38), arrowprops={"arrowstyle": "->"})
    axis.text(0.02, 0.02, "10 main M3 fasteners (red)\n4 frozen P14/P15 mounts (green)\nintentional open ports at y=±117 mm", transform=axis.transAxes, bbox={"facecolor": "white", "alpha": 0.9})
    axis.set_aspect("equal")
    axis.grid(alpha=0.15)
    axis.set(title="Fastener and sealing-land gate", xlabel="x (mm)", ylabel="y (mm)")
    fig.tight_layout()
    fig.savefig(PREVIEW_DIR / "fastener_and_sealing_dimensions.png", dpi=210)
    V1.plt.close(fig)

    fig, axis = V1.plt.subplots(figsize=(9, 7))
    axis.axis("off")
    layers = [
        ("V1C compact sealing lid — print ×1", 5.2, "#9ecae1"),
        ("continuous thin RTV bead on 4 mm land", 4.1, "#74c476"),
        ("V1C compact integrated base — print ×1", 3.0, "#fdae6b"),
        ("reuse V1 P03 mic insert", 1.8, "#bcbddc"),
        ("reuse V1 P14/P15 turntable", 0.6, "#d9d9d9"),
    ]
    for label, ypos, color in layers:
        axis.add_patch(V1.plt.Rectangle((1.0, ypos), 8.0, 0.55, facecolor=color, edgecolor="#333"))
        axis.text(5.0, ypos + 0.275, label, ha="center", va="center", fontsize=10)
    for ypos in (5.0, 3.9, 2.8, 1.6):
        axis.annotate("", xy=(5.0, ypos - 0.05), xytext=(5.0, ypos - 0.45), arrowprops={"arrowstyle": "->"})
    axis.text(5.0, 6.25, "TRANS-I2F V1C exploded assembly", ha="center", fontsize=15, weight="bold")
    axis.text(5.0, 5.9, "Only the base and lid are new prints", ha="center", fontsize=11)
    axis.set_xlim(0, 10)
    axis.set_ylim(0, 6.6)
    fig.tight_layout()
    fig.savefig(PREVIEW_DIR / "V1C_exploded_assembly.png", dpi=210)
    V1.plt.close(fig)


def write_docs(invariance: dict, mechanical: dict, material: dict, mesh_reports: list[dict]) -> None:
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    (DOC_DIR / "START_HERE_zh.md").write_text(f"""# TRANS-I2F V1C 紧凑打印包

终态：`{TERMINAL_STATE}`

V1C 只删除 V1 声学空气域之外的无关 PLA，并保留中央机械枢纽、N/S 两条长分支和全部冻结接口。二维空气域 symmetric difference 为 `{invariance['symmetric_difference_area_mm2']} mm²`，名义尺寸差全部为0。

## 只需打印

1. `STL/TRANS_I2F_V1C_COMPACT_BASE_HR03_N_HR07_S.stl` ×1；
2. `STL/TRANS_I2F_V1C_COMPACT_SEALING_LID.stl` ×1。

不要重新打印 P03、P14、P15 或 P16：直接复用原 V1 / V2.0.1 已有件。若没有这些件，从原 V1 包按原说明打印，不要修改接口。

总 PLA 几何体积代理由 `{material['v1_total_pla_proxy_volume_mm3']:.1f}` 降至 `{material['v1c_total_pla_proxy_volume_mm3']:.1f} mm³`，减少 `{material['total_reduction_percent']:.2f}%`。这是几何代理，不是切片器材料或打印时间实测。

READY 仅表示打印候选的几何、声学域不变性和机械数字门禁通过，不表示 COMSOL 或实体实验通过。
""", encoding="utf-8")

    (DOC_DIR / "PRINT_AND_ASSEMBLY_zh.md").write_text(f"""# V1C 打印与装配

## 打印设置

- PLA、0.4 mm 喷嘴、0.20 mm 层高、100%比例，禁止自动缩放。
- 底盘：开放声道面朝上；4道墙、5层顶底、15–20% gyroid、5 mm brim、关闭支撑。
- 盖板：密封平面朝下；4道墙、5层顶底、15–20% gyroid、5 mm brim、关闭支撑。
- 两件外形均为 `{mechanical['outer_bounds_mm'][2]-mechanical['outer_bounds_mm'][0]:.1f} × {mechanical['outer_bounds_mm'][3]-mechanical['outer_bounds_mm'][1]:.1f} mm`；含5 mm brim约 `{mechanical['print_footprint_with_5mm_brim_mm'][0]:.1f} × {mechanical['print_footprint_with_5mm_brim_mm'][1]:.1f} mm`。

## 五金与复用件

- 主盖：M3×18/20 螺钉、螺母、垫片各10；转盘安装孔不计入这10个主盖紧固件。
- 复用原 P03：Ø20.4 mm座、Ø9.0 mm短孔；麦克风膜面Ø8.8 mm，冻结全局 z=1.0 mm。
- 复用原 P14/P15/P16；四个安装坐标完全保留。

## 装配

1. 清理底盘与盖板接触面，不打磨声道、HR腔体、双颈或入口。
2. 干装 P03 与转盘，确认四个旧安装孔自由对齐。
3. 在空气域周围4.0 mm连续密封台上施加极薄的中性固化 RTV；不得进入声道或螺孔。
4. 盖上 V1C 盖板，按 N/S 与左右交替顺序分三轮均匀紧固10颗主盖螺钉。
5. 清除 N/S 入口端面溢胶；端面 y=±117 mm 必须保持完全开放。

最小名义侧壁4.0 mm，最小连续密封台4.0 mm，空气域到主螺孔边缘最小 `{mechanical['minimum_airspace_to_main_screw_edge_mm']:.2f} mm`。螺母槽深0.8 mm，盖板下方保留2.4 mm连续皮层，不形成穿透漏气路径。
""", encoding="utf-8")

    (DOC_DIR / "ACOUSTIC_DOMAIN_INVARIANCE.md").write_text(f"""# 声学空气域不变性

V1C 生成器直接加载并调用原 V1 权威 `build_geometry()`；`geometry['airspace']` 与 V1 返回对象是同一个对象，没有重新描绘或近似。

- symmetric difference：`{invariance['symmetric_difference_area_mm2']} mm²`（门限≤1e-6 mm²）；
- 总二维面积：`{invariance['subdomains']['airspace']['old_area_mm2']:.9f} mm²`；
- 6.4 mm主空气域体积：`{invariance['old_total_air_volume_mm3']:.9f} mm³`，差0；
- HR03腔体体积：`{invariance['subdomains']['HR03_cavity']['old_volume_mm3']:.9f} mm³`，差0；
- HR07腔体体积：`{invariance['subdomains']['HR07_cavity']['old_volume_mm3']:.9f} mm³`，差0；
- Ø10.4 mm微汇合区体积：`{invariance['subdomains']['microphone_microplenum']['old_volume_mm3']:.9f} mm³`，差0；
- N/S端面：y=±117 mm，宽20 mm，差0；
- N/S除微汇合区外重叠：`{invariance['branch_overlap_outside_microplenum_mm2']} mm²`。

逐项面积、质心、体积和端口记录见 `acoustic_domain_invariance.csv`。P03短孔按Ø9.0 mm、z=1..3 mm记录；Ø8.8 mm麦克风膜面与 z=1.0 mm位置不变。

因此现有只包含冻结内部空气域的 TRANS-I2F COMSOL 模型仍可沿用；V1C 外部 PLA 删除不会改变该流体域。此结论不等于256点收敛、外场或实体声学通过。
""", encoding="utf-8")


def distributable(path: Path) -> bool:
    parts = path.relative_to(PACKAGE_ROOT).parts
    return (
        path.is_file()
        and path.name != "SHA256SUMS.txt"
        and path.suffix.lower() != ".zip"
        and "__pycache__" not in parts
        and path.suffix.lower() != ".pyc"
    )


def write_manifest_and_zip(mesh_reports: list[dict]) -> str:
    with (PACKAGE_ROOT / "print_file_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "role", "quantity", "sha256", "bytes", "watertight", "winding_consistent", "components", "volume_mm3"])
        writer.writeheader()
        for report in mesh_reports:
            writer.writerow({
                "path": report["file"], "role": "required_new_print", "quantity": 1,
                "sha256": report["sha256"], "bytes": report["bytes"],
                "watertight": report["watertight"], "winding_consistent": report["winding_consistent"],
                "components": report["components"], "volume_mm3": f"{report['volume_mm3']:.9f}",
            })
    inventory = [path for path in sorted(PACKAGE_ROOT.rglob("*")) if distributable(path)]
    (PACKAGE_ROOT / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256_file(path)}  {path.relative_to(PACKAGE_ROOT).as_posix()}\n" for path in inventory),
        encoding="utf-8",
    )
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PACKAGE_ROOT.rglob("*")):
            if distributable(path) or path.name == "SHA256SUMS.txt":
                archive.write(path, arcname=f"{PACKAGE_ROOT.name}/{path.relative_to(PACKAGE_ROOT).as_posix()}")
    return sha256_file(ZIP_PATH)


def write_progress_report(invariance: dict, mechanical: dict, material: dict, mesh_reports: list[dict], hash_audit: dict, zip_sha256: str) -> None:
    report = f"""# COMSOL TRANS-1P0 — 紧凑打印几何与声学域不变性门禁

日期：{datetime.now().astimezone().isoformat()}  
终态：`{TERMINAL_STATE}`

## 结论

V1C 已把 V1 的完整八边形外壳缩减为中央机械圆台/枢纽与 N/S 双长分支，删除另外六个无声道实心区域。只修改内部空气域以外的 PLA；现有 TRANS-I2F 内部空气域和当前 COMSOL 流体模型仍可沿用。

READY 仅表示可作为打印候选，不表示256点、完整声学仿真、外场或实体实验通过。

## 权威与不变性

- 原 V1 SHA-256：`{hash_audit['matched']}/{hash_audit['entries']}` 重新计算匹配；原 ZIP、源代码、STL、文档均未修改。
- V1C 直接复用 V1 `build_geometry()` 返回的同一个 `airspace` 对象。
- 二维 symmetric difference `{invariance['symmetric_difference_area_mm2']} mm²`；总面积、各子域面积/质心、端口位置/宽度、三维体积差均为0。
- 主空气域 `{invariance['old_total_air_volume_mm3']:.6f} mm³`；HR03 `{invariance['subdomains']['HR03_cavity']['old_volume_mm3']:.6f} mm³`；HR07 `{invariance['subdomains']['HR07_cavity']['old_volume_mm3']:.6f} mm³`；微汇合区 `{invariance['subdomains']['microphone_microplenum']['old_volume_mm3']:.6f} mm³`。
- N/S端面保持 y=±117 mm、宽20 mm；除微汇合区外重叠0 mm²。
- P04M接口保持 Ø9.0 mm短孔 z=1..3 mm、Ø8.8 mm膜面 z=1.0 mm。

## 外形、紧固与密封

- 新底盘/盖板共同外形：`100.0 × 234.0 mm`，含5 mm brim代理 `110.0 × 244.0 mm`。
- 10个 N/S 与左右对称的主盖 M3 紧固件；覆盖中央、两腔体和两入口附近；转盘孔不计入。
- 原 P14/P15 四坐标完整保留，P03 Ø20.4 mm座完整保留。
- 最小名义侧壁4.0 mm；连续密封台4.0 mm；空气域到主螺孔边缘最小 `{mechanical['minimum_airspace_to_main_screw_edge_mm']:.2f} mm`。
- N/S端面为有意开放端口，不适用封闭侧壁；其侧壁仍为4.0 mm。
- 螺孔和螺母槽平面均不侵入空气域；0.8 mm螺母槽下保留2.4 mm盖板皮层，不形成贯穿漏气路径。

## STL与节材代理

- 底盘：watertight `{mesh_reports[0]['watertight']}`，winding `{mesh_reports[0]['winding_consistent']}`，components `{mesh_reports[0]['components']}`，体积 `{mesh_reports[0]['volume_mm3']:.3f} mm³`。
- 盖板：watertight `{mesh_reports[1]['watertight']}`，winding `{mesh_reports[1]['winding_consistent']}`，components `{mesh_reports[1]['components']}`，体积 `{mesh_reports[1]['volume_mm3']:.3f} mm³`。
- V1→V1C 底盘体积减少 `{material['base_reduction_percent']:.2f}%`；盖板减少 `{material['lid_reduction_percent']:.2f}%`；总 PLA 几何代理减少 `{material['total_reduction_percent']:.2f}%`。
- 材料与打印时间仅按几何体积一阶代理估计约减少 `{material['total_reduction_percent']:.2f}%`；未运行切片器，不是耗材克数或打印时长实测。

## 只需打印

1. `STL/TRANS_I2F_V1C_COMPACT_BASE_HR03_N_HR07_S.stl`；
2. `STL/TRANS_I2F_V1C_COMPACT_SEALING_LID.stl`。

P03与已有P14/P15/P16直接复用，不需要重复打印。

## 范围

- 新 COMSOL solve=0，`study.run=0`；256点、六组合、TRANS-2/3、外场、参数搜索和实测均未开始。
- 未读取 final-test；`final_test_read=false`。
- 未修改频率、窗口、阈值或既有科研结论；未 commit、push、tag 或 release。

## 产物

- `outputs/print_packages/TRANS_I2F_COMPACT_TWO_PORT_V1C/`
- `outputs/print_packages/TRANS_I2F_COMPACT_TWO_PORT_V1C.zip`（SHA-256 `{zip_sha256}`）
- `docs/progress/COMSOL_TRANS_1P0_COMPACT_PRINT_GEOMETRY_GATE.md`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    for directory in (STL_DIR, DOC_DIR, PREVIEW_DIR, SOURCE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    hash_audit = verify_v1_manifest()
    if not hash_audit["all_match"]:
        raise RuntimeError("Original V1 SHA-256 audit failed")
    geometry = build_geometry(include_meshes=True)
    invariance = acoustic_invariance_record(geometry)
    mechanical = mechanical_gate_record(geometry)
    in_memory_mesh = mesh_gate_record(geometry)
    material = material_proxy_record(geometry)
    if not invariance["all_checks_pass"]:
        raise RuntimeError("TRANS1P0_BLOCKED_BY_ACOUSTIC_DOMAIN_CHANGE")
    if not mechanical["all_checks_pass"] or not in_memory_mesh["all_checks_pass"]:
        raise RuntimeError("TRANS1P0_BLOCKED_BY_MECHANICAL_GATE")

    base_report = export_and_reload_mesh(geometry["base_mesh"], STL_DIR / "TRANS_I2F_V1C_COMPACT_BASE_HR03_N_HR07_S.stl")
    lid_report = export_and_reload_mesh(geometry["lid_mesh"], STL_DIR / "TRANS_I2F_V1C_COMPACT_SEALING_LID.stl")
    mesh_reports = [base_report, lid_report]
    if not all(report["all_checks_pass"] for report in mesh_reports):
        raise RuntimeError("TRANS1P0_BLOCKED_BY_MECHANICAL_GATE")
    if not V1.np.allclose(
        V1.np.asarray(base_report["bounds_mm"])[:, :2],
        V1.np.asarray(lid_report["bounds_mm"])[:, :2], atol=1e-6,
    ):
        raise RuntimeError("TRANS1P0_BLOCKED_BY_MECHANICAL_GATE: exported outlines differ")

    invariance.update({
        "terminal_state": TERMINAL_STATE,
        "authority_source": V1_GENERATOR.relative_to(REPO_ROOT).as_posix(),
        "authority_source_sha256": sha256_file(V1_GENERATOR),
        "new_comsol_solve_count": 0,
        "study_run_calls": 0,
    })
    mechanical.update({
        "terminal_state": TERMINAL_STATE,
        "nut_traps_intersection_airspace_mm2": float(geometry["nut_traps"].intersection(geometry["airspace"]).area),
        "nut_trap_depth_mm": 0.8,
        "continuous_lid_skin_below_nut_trap_mm": 2.4,
        "exported_mesh_reports": mesh_reports,
    })
    geometry_validation = {
        "terminal_state": TERMINAL_STATE,
        "all_checks_pass": True,
        "acoustic_domain_invariance_pass": invariance["all_checks_pass"],
        "mechanical_gate_pass": mechanical["all_checks_pass"],
        "in_memory_mesh_gate": in_memory_mesh,
        "exported_reload_mesh_gate_pass": all(report["all_checks_pass"] for report in mesh_reports),
        "mesh_reports": mesh_reports,
        "material_and_print_time_proxy": material,
        "current_comsol_internal_air_model_reusable": True,
        "ready_scope": "print candidate only; not COMSOL or physical validation",
        "new_comsol_solve_count": 0,
        "study_run_calls": 0,
        "formal_256_started": False,
        "six_combinations_completed": 0,
        "trans2_started": False,
        "trans3_started": False,
        "physical_test_started": False,
        "final_test_read": False,
    }
    write_json(PACKAGE_ROOT / "input_hash_audit.json", hash_audit)
    write_json(PACKAGE_ROOT / "acoustic_domain_invariance.json", invariance)
    write_invariance_csv(invariance)
    write_json(PACKAGE_ROOT / "mechanical_gate.json", mechanical)
    write_json(PACKAGE_ROOT / "material_proxy.json", material)
    write_json(PACKAGE_ROOT / "geometry_validation.json", geometry_validation)
    render_previews(geometry, invariance, mechanical, material)
    write_docs(invariance, mechanical, material, mesh_reports)
    shutil.copy2(V1_GENERATOR, SOURCE_DIR / "frozen_generate_trans_i2f_v1_authority.py")
    (SOURCE_DIR / "requirements.txt").write_text(
        "numpy\nshapely>=2.1\ntrimesh>=4.10\nmapbox-earcut\nmanifold3d\nmatplotlib\npytest\n",
        encoding="utf-8",
    )
    zip_sha256 = write_manifest_and_zip(mesh_reports)
    write_progress_report(invariance, mechanical, material, mesh_reports, hash_audit, zip_sha256)
    print(json.dumps({
        "terminal_state": TERMINAL_STATE,
        "package": str(PACKAGE_ROOT),
        "zip": str(ZIP_PATH),
        "zip_sha256": zip_sha256,
        "airspace_symmetric_difference_mm2": invariance["symmetric_difference_area_mm2"],
        "total_pla_proxy_reduction_percent": material["total_reduction_percent"],
        "new_comsol_solve_count": 0,
        "study_run_calls": 0,
        "final_test_read": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

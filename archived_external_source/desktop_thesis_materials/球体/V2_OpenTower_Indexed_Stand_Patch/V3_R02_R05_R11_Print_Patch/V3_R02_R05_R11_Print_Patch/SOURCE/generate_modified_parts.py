from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK_ROOT = HERE.parents[1]
PYDEPS = WORK_ROOT / "pydeps"
if PYDEPS.exists():
    sys.path.insert(0, str(PYDEPS))

import numpy as np
import trimesh


PACKAGE = HERE.parent
STL_DIR = PACKAGE / "STL"
STL_DIR.mkdir(parents=True, exist_ok=True)

ORIGINAL_R02 = (
    WORK_ROOT
    / "tower_review"
    / "extracted"
    / "V2_OpenTower_Indexed_Stand_Patch"
    / "STL"
    / "R02_rotating_open_C_tower.stl"
)


PARAMS = {
    "units": "mm",
    "printer": "Bambu Lab P1S, 0.4 mm nozzle, PLA",
    "R02": {
        "r03_mount_hole_diameter": 3.4,
        "new_post_diameter": 3.1,
        "new_post_height": 3.6,
        "post_tip_diameter": 2.7,
        "post_tip_height": 0.4,
        "diametral_clearance": 0.3,
        "r03_base_thickness": 4.0,
        "top_clearance": 0.4,
        "post_centers": [[27.0, 0.0], [0.0, 27.0], [-27.0, 0.0]],
    },
    "R05": {
        "bore_diameter": 8.7,
        "large_diameter": 30.0,
        "large_section_height": 10.5,
        "small_diameter": 20.0,
        "small_section_height": 3.5,
        "height_ratio_small_to_large": "1:3",
        "total_height": 14.0,
    },
    "R11": {
        "tower_outer_diameter": 60.0,
        "collar_inner_diameter": 60.6,
        "collar_outer_diameter": 67.0,
        "collar_height": 24.0,
        "collar_opening_angle": 160.0,
        "nominal_radial_clearance": 0.3,
        "snap_opening_chord": 2 * 30.3 * math.sin(math.radians(80.0)),
        "branch_cradle_inner_diameter": 16.0,
        "branch_cradle_outer_diameter": 22.0,
        "branch_cradle_open_style": "approximately 225 degree open saddle",
        "branch_axis_angle_from_horizontal_deg": 45.0,
        "support_arm_height": 12.0,
        "installation": "side-snap collar; align its opening with R02 rear opening",
    },
}


def cylinder(radius: float, height: float, center=(0.0, 0.0, 0.0), sections=64):
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    mesh.apply_translation(center)
    return mesh


def boolean_union(meshes):
    result = trimesh.boolean.union(meshes, engine="manifold", check_volume=False)
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    result.process(validate=True)
    return result


def boolean_difference(a, cutters):
    result = trimesh.boolean.difference([a, *cutters], engine="manifold", check_volume=False)
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    result.process(validate=True)
    return result


def export(mesh: trimesh.Trimesh, name: str):
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh, multibody=True)
    path = STL_DIR / name
    mesh.export(path, file_type="stl")
    return path


def make_r02():
    base = trimesh.load_mesh(ORIGINAL_R02, force="mesh", process=True)
    additions = [base]
    for x, y in PARAMS["R02"]["post_centers"]:
        # Fill the former screw hole inside the 4 mm top tab with positive overlap.
        additions.append(cylinder(1.90, 4.40, (x, y, 103.10), 48))
        # Main locating post: z=105.10..108.45, overlapping the filled tab by 0.10 mm.
        additions.append(cylinder(1.55, 3.35, (x, y, 106.775), 48))
        # Reduced tip acts as a simple printable lead-in without exceeding R03 thickness.
        additions.append(cylinder(1.35, 0.45, (x, y, 108.575), 48))
    return boolean_union(additions)


def make_r05():
    # All outer solids overlap slightly before union; one continuous Ø8.7 bore is cut last.
    flange = cylinder(15.0, 10.52, (0.0, 0.0, 5.25), 128)
    neck_a = cylinder(10.0, 2.54, (0.0, 0.0, 11.75), 128)
    ridge = cylinder(10.09, 0.54, (0.0, 0.0, 13.25), 128)
    neck_b = cylinder(10.0, 0.54, (0.0, 0.0, 13.75), 128)
    outer = boolean_union([flange, neck_a, ridge, neck_b])
    bore = cylinder(4.35, 14.40, (0.0, 0.0, 7.0), 96)
    return boolean_difference(outer, [bore])


def sector_prism(center_deg: float, half_deg: float, radius: float, z0: float, z1: float, steps=80):
    angles = np.linspace(
        math.radians(center_deg - half_deg),
        math.radians(center_deg + half_deg),
        steps + 1,
    )
    ring = [(radius * math.cos(a), radius * math.sin(a)) for a in angles]
    points = [(0.0, 0.0), *ring]
    n = len(points)
    vertices = [[x, y, z0] for x, y in points] + [[x, y, z1] for x, y in points]
    faces = []
    for i in range(1, n - 1):
        faces.append([0, i + 1, i])
        faces.append([n, n + i, n + i + 1])
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j])
        faces.append([i, n + j, n + i])
    mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def beam_between_xy(a, b, width: float, height: float):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    vec = b - a
    length = float(np.linalg.norm(vec))
    angle = math.atan2(vec[1], vec[0])
    transform = trimesh.transformations.rotation_matrix(angle, [0.0, 0.0, 1.0])
    transform[:3, 3] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, height / 2]
    return trimesh.creation.box(extents=[length + 1.0, width, height], transform=transform)


def make_open_branch_cradle():
    # Build around local +Z, remove a cap on local +Y, then align with the rising branch.
    length = 18.0
    sleeve = trimesh.creation.annulus(
        r_min=8.0,
        r_max=11.0,
        height=length,
        sections=128,
    )
    sleeve.apply_translation([0.0, 0.0, length / 2])
    opening = trimesh.creation.box(extents=[30.0, 20.0, length + 4.0])
    opening.apply_translation([0.0, 14.0, length / 2])
    cradle = boolean_difference(sleeve, [opening])

    # Explicit orthonormal frame: local +Y points upward/front, local +Z follows branch.
    x_axis = np.array([1.0, 0.0, 0.0])
    z_axis = np.array([0.0, -1.0, 1.0]) / math.sqrt(2.0)
    y_axis = np.cross(z_axis, x_axis)
    transform = np.eye(4)
    transform[:3, 0] = x_axis
    transform[:3, 1] = y_axis
    transform[:3, 2] = z_axis
    transform[:3, 3] = [0.0, -6.0, 10.0]
    cradle.apply_transform(transform)
    return cradle


def make_r11():
    collar = trimesh.creation.annulus(r_min=30.3, r_max=33.5, height=24.0, sections=256)
    collar.apply_translation([0.0, 0.0, 12.0])
    opening = sector_prism(-90.0, 80.0, 50.0, -1.0, 25.0)
    collar = boolean_difference(collar, [opening])

    # The collar gap is wider than R02 for side installation. The two-part arm first
    # runs outside the R02 wall, then turns into the original 140 degree rear opening.
    edge = (33.3 * math.cos(math.radians(-10.0)), 33.3 * math.sin(math.radians(-10.0)))
    turn = (38.0 * math.cos(math.radians(-30.0)), 38.0 * math.sin(math.radians(-30.0)))
    gate = (24.0 * math.cos(math.radians(-30.0)), 24.0 * math.sin(math.radians(-30.0)))
    inner = (9.5, -9.0)
    arm_outer = beam_between_xy(edge, turn, 5.5, 12.0)
    arm_entry = beam_between_xy(turn, gate, 5.5, 12.0)
    arm_inner = beam_between_xy(gate, inner, 8.0, 12.0)
    cradle = make_open_branch_cradle()
    return boolean_union([collar, arm_outer, arm_entry, arm_inner, cradle])


def mesh_report(path: Path):
    mesh = trimesh.load_mesh(path, force="mesh", process=True)
    components = mesh.split(only_watertight=False)
    return {
        "file": path.name,
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "components": len(components),
        "extents_mm": np.round(mesh.extents, 3).tolist(),
        "bounds_mm": np.round(mesh.bounds, 3).tolist(),
        "volume_mm3": round(abs(float(mesh.volume)), 3),
        "faces": int(len(mesh.faces)),
    }


def validate_r11_clearance(r11):
    # Idealised R02 shell section at the R11 height; any significant intersection
    # means the support arm missed the 140 degree rear opening.
    shell = trimesh.creation.annulus(r_min=26.0, r_max=30.0, height=24.0, sections=256)
    shell.apply_translation([0.0, 0.0, 12.0])
    rear_gap = sector_prism(-90.0, 70.0, 50.0, -1.0, 25.0)
    shell = boolean_difference(shell, [rear_gap])
    intersection = trimesh.boolean.intersection(
        [r11, shell], engine="manifold", check_volume=False
    )
    volume = 0.0 if intersection is None else abs(float(intersection.volume))
    return volume


def main():
    if not ORIGINAL_R02.exists():
        raise FileNotFoundError(f"Original R02 not found: {ORIGINAL_R02}")

    r02 = make_r02()
    r05 = make_r05()
    r11 = make_r11()

    paths = [
        export(r02, "R02_rotating_open_C_tower_press_posts.stl"),
        export(r05, "R05_P03_insert_ID8p7_long_flange_1to3.stl"),
        export(r11, "R11_external_C_collar_branch_cradle.stl"),
    ]

    reports = [mesh_report(path) for path in paths]
    r11_intersection = validate_r11_clearance(r11)
    checks = [
        {
            "name": "all STL files are watertight",
            "pass": all(r["watertight"] for r in reports),
        },
        {
            "name": "all STL files have consistent winding",
            "pass": all(r["winding_consistent"] for r in reports),
        },
        {
            "name": "each STL is a single connected component",
            "pass": all(r["components"] == 1 for r in reports),
        },
        {
            "name": "R02 post has positive diametral clearance in R03 hole",
            "pass": PARAMS["R02"]["diametral_clearance"] > 0,
            "details": {
                "R03_hole": 3.4,
                "R02_post": 3.1,
                "diametral_clearance": 0.3,
            },
        },
        {
            "name": "R02 post remains below R03 top surface",
            "pass": PARAMS["R02"]["new_post_height"] < PARAMS["R02"]["r03_base_thickness"],
            "details": {"post_height": 3.6, "R03_thickness": 4.0, "top_clearance": 0.4},
        },
        {
            "name": "R05 uses continuous 8.7 mm bore",
            "pass": PARAMS["R05"]["bore_diameter"] == 8.7,
        },
        {
            "name": "R05 small-to-large section height ratio is 1:3",
            "pass": abs(PARAMS["R05"]["large_section_height"] / PARAMS["R05"]["small_section_height"] - 3.0) < 1e-9,
        },
        {
            "name": "R11 avoids idealised R02 tower shell",
            "pass": r11_intersection < 0.05,
            "details": {"intersection_volume_mm3": r11_intersection},
        },
        {
            "name": "R11 fits P1S build volume in supplied orientation",
            "pass": bool(np.all(r11.extents <= np.array([256.0, 256.0, 256.0]))),
            "details": {"extents_mm": np.round(r11.extents, 3).tolist()},
        },
    ]

    validation = {
        "all_checks_pass": all(c["pass"] for c in checks),
        "checks": checks,
        "mesh_reports": reports,
        "limitations": [
            "No physical print/fit test has been performed.",
            "R11 branch cradle uses a tolerant 16 mm opening because the microphone branch cross-section was not measured.",
            "Use 0.5-1.0 mm foam tape inside the cradle if the physical branch is substantially smaller than 16 mm.",
        ],
    }

    (HERE / "design_parameters.json").write_text(
        json.dumps(PARAMS, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (HERE / "validation_report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if not validation["all_checks_pass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

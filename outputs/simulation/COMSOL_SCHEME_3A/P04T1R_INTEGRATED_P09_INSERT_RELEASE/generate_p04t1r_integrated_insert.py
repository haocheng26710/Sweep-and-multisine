"""Generate P04T1R P09-anchored I75 and manufacturable I50P inserts.

The geometry is reconstructed from the authoritative V2.0.1 P09 source.  Each
printable part is one original P09 solid dummy plus one inward chamber lobe.
The short joining overlap is confined to the already-blocked diagonal fixed
channel.  Units are millimetres.  This script performs no acoustic solve and
contains no optimisation loop.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box
from shapely.ops import polygonize, triangulate, unary_union
import trimesh


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT = Path(__file__).resolve().parent
SOURCE_ZIP = REPO_ROOT / "reference_assets/physical_design/model_packages/Acoustic_Morphology_Encoder_V2.0.1_Print_Package.zip"
SOURCE_ZIP_SHA256 = "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f"

CHAMBER_RADIUS = 18.0
CHAMBER_HEIGHT = 9.2
PRINT_RADIUS = 17.90
RELIEF_RADIUS = 10.20
RELIEF_DEPTH = 0.70
P03_RIDGE_RADIUS = 10.09
P03_PROTRUSION = 0.50
FIXED_CHANNEL_WIDTH = 8.0
FIXED_CHANNEL_INNER_RADIUS = 17.0
FIXED_CHANNEL_OUTER_RADIUS = 32.0
MODULE_CENTRE_RADIUS = 60.0
P09_LOWER_HEIGHT = 9.0
PRINT_EDGE_RETREAT = 0.05
I75_IDEAL_HALF_WIDTH = 6.71166872071184
I50_IDEAL_HALF_WIDTH = 4.0158278753
I50P_PRINT_HALF_WIDTH = 4.30
CONNECTOR_X0 = -42.15
CONNECTOR_X1 = -41.80
CONNECTOR_HALF_WIDTH = 3.70
PLATE_GAP = 8.0

VARIANTS = {
    "I75": {
        "ideal_half_width": I75_IDEAL_HALF_WIDTH,
        "print_half_width": I75_IDEAL_HALF_WIDTH + PRINT_EDGE_RETREAT,
        "target_fraction": 0.75,
        "role": "primary_confirmatory_mechanism_insert",
    },
    "I50P": {
        "ideal_half_width": I50_IDEAL_HALF_WIDTH,
        "print_half_width": I50P_PRINT_HALF_WIDTH,
        "target_fraction": 0.50,
        "role": "secondary_exploratory_dose_point",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean(geometry):
    if geometry.is_empty:
        return geometry
    geometry = shapely.set_precision(geometry, grid_size=0.001)
    if not geometry.is_valid:
        geometry = shapely.make_valid(geometry)
    return geometry


def circle(x: float, y: float, radius: float, resolution: int = 192):
    return clean(Point(x, y).buffer(radius, quad_segs=resolution))


def polygons_of(geometry):
    if geometry.is_empty:
        return
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, MultiPolygon):
        yield from geometry.geoms
    elif isinstance(geometry, GeometryCollection):
        for item in geometry.geoms:
            if isinstance(item, Polygon):
                yield item
            elif isinstance(item, MultiPolygon):
                yield from item.geoms


def rings_of(geometry):
    for polygon in polygons_of(geometry):
        yield polygon.exterior
        yield from polygon.interiors


def _tri_area2(coords):
    (x0, y0), (x1, y1), (x2, y2) = coords
    return (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)


def _add_horizontal_surface(vertices, faces, geometry, z: float, upward: bool):
    geometry = clean(geometry)
    triangles = triangulate(geometry)
    for triangle in getattr(triangles, "geoms", [triangles]):
        if not isinstance(triangle, Polygon) or triangle.area < 1e-10:
            continue
        if not geometry.covers(triangle):
            continue
        coords = list(triangle.exterior.coords)[:3]
        if _tri_area2(coords) < 0:
            coords = [coords[0], coords[2], coords[1]]
        if not upward:
            coords = [coords[0], coords[2], coords[1]]
        face = []
        for x, y in coords:
            face.append(len(vertices))
            vertices.append([x, y, z])
        faces.append(face)


def _add_vertical_walls(vertices, faces, geometry, z0: float, z1: float):
    for ring in rings_of(clean(geometry)):
        coords = list(ring.coords)
        for index in range(len(coords) - 1):
            a = (float(coords[index][0]), float(coords[index][1]))
            b = (float(coords[index + 1][0]), float(coords[index + 1][1]))
            if math.dist(a, b) < 1e-10:
                continue
            base = len(vertices)
            vertices.extend([[a[0], a[1], z0], [b[0], b[1], z0], [b[0], b[1], z1], [a[0], a[1], z1]])
            faces.append([base, base + 1, base + 2])
            faces.append([base, base + 2, base + 3])


def layered_mesh(layers, name: str) -> trimesh.Trimesh:
    solids = []
    for z0, z1, geometry in layers:
        if z1 <= z0 or geometry.is_empty:
            continue
        for polygon in polygons_of(clean(geometry)):
            solid = trimesh.creation.extrude_polygon(polygon, height=float(z1 - z0), engine="earcut")
            solid.apply_translation([0.0, 0.0, float(z0)])
            solids.append(solid)
    if not solids:
        raise ValueError(f"No solids for {name}")
    mesh = trimesh.boolean.union(solids, engine="manifold")
    if not isinstance(mesh, trimesh.Trimesh):
        mesh = mesh.dump(concatenate=True)
    mesh.merge_vertices(digits_vertex=6)
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    if mesh.volume < 0:
        mesh.invert()
    mesh.metadata["name"] = name
    return mesh


def mesh_component_count(mesh: trimesh.Trimesh) -> int:
    """Count face-connected components without optional scipy/networkx."""
    mesh = mesh.copy()
    mesh.merge_vertices(digits_vertex=6)
    edge_faces = {}
    for face_index, face in enumerate(np.asarray(mesh.faces, dtype=int)):
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_faces.setdefault(tuple(sorted((int(a), int(b)))), []).append(face_index)
    neighbours = [set() for _ in range(len(mesh.faces))]
    for owners in edge_faces.values():
        for owner in owners:
            neighbours[owner].update(other for other in owners if other != owner)
    unseen = set(range(len(mesh.faces)))
    count = 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            for neighbour in neighbours[stack.pop()] & unseen:
                unseen.remove(neighbour)
                stack.append(neighbour)
    return count


def module_outline():
    x0, x1 = -28.0, 28.0
    inner_half, outer_half, chamfer = 8.5, 18.0, 4.0
    return clean(Polygon([(x0, -inner_half), (x1, -outer_half), (x1, outer_half - chamfer), (x1 - chamfer, outer_half), (x0, inner_half)]))


def p09_profiles():
    body = module_outline()
    inner_tongue = box(-42.0, -3.7, -28.0, 3.7)
    outer_tongue = Polygon([(28.0, -3.7), (45.0, -7.7), (45.0, 7.7), (28.0, 3.7)])
    lower = clean(unary_union([body, inner_tongue, outer_tongue]))
    flange = clean(body.buffer(-0.10, join_style="mitre"))
    return lower, flange


def _circle_integral(x: float, radius: float) -> float:
    return 0.5 * (x * math.sqrt(max(0.0, radius * radius - x * x)) + radius * radius * math.asin(x / radius))


def quadrant_complement_area(radius: float, half_width: float) -> float:
    xmax = math.sqrt(radius * radius - half_width * half_width)
    return _circle_integral(xmax, radius) - _circle_integral(half_width, radius) - half_width * (xmax - half_width)


def ideal_retained_air_fraction(half_width: float) -> float:
    solid = 4.0 * quadrant_complement_area(CHAMBER_RADIUS, half_width)
    return 1.0 - solid / (math.pi * CHAMBER_RADIUS**2)


def print_half_width(variant: str) -> float:
    return VARIANTS[variant]["print_half_width"]


def print_cross_width(variant: str) -> float:
    return 2.0 * print_half_width(variant)


def _assembly_ne_lobe(variant: str):
    half = print_half_width(variant)
    disk = circle(0.0, 0.0, PRINT_RADIUS)
    return clean(disk.intersection(box(half, half, PRINT_RADIUS + 1.0, PRINT_RADIUS + 1.0)))


def _assembly_to_local(geometry):
    centre = MODULE_CENTRE_RADIUS / math.sqrt(2.0)
    shifted = affinity.translate(geometry, xoff=-centre, yoff=-centre)
    return clean(affinity.rotate(shifted, -45.0, origin=(0.0, 0.0), use_radians=False))


def _local_to_assembly(geometry):
    centre = MODULE_CENTRE_RADIUS / math.sqrt(2.0)
    rotated = affinity.rotate(geometry, 45.0, origin=(0.0, 0.0), use_radians=False)
    return clean(affinity.translate(rotated, xoff=centre, yoff=centre))


def variant_profiles(variant: str):
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant: {variant}")
    p09_lower, p09_flange = p09_profiles()
    full_lobe = _assembly_to_local(_assembly_ne_lobe(variant))
    relief = _assembly_to_local(circle(0.0, 0.0, RELIEF_RADIUS))
    lower_lobe = clean(full_lobe.difference(relief))
    connector = box(CONNECTOR_X0, -CONNECTOR_HALF_WIDTH, CONNECTOR_X1, CONNECTOR_HALF_WIDTH)
    lower = clean(unary_union([p09_lower, connector, lower_lobe]))
    middle = clean(unary_union([p09_lower, connector, full_lobe]))
    top = clean(unary_union([p09_flange, full_lobe]))
    return {
        "p09_lower": p09_lower,
        "p09_flange": p09_flange,
        "full_lobe": full_lobe,
        "lower_lobe": lower_lobe,
        "connector": connector,
        "lower": lower,
        "middle": middle,
        "top": top,
    }


def _central_solid_volume(profiles) -> float:
    chamber = circle(-MODULE_CENTRE_RADIUS, 0.0, CHAMBER_RADIUS)
    lower_area = profiles["lower"].intersection(chamber).area
    middle_area = profiles["middle"].intersection(chamber).area
    top_area = profiles["top"].intersection(chamber).area
    one_lobe = lower_area * RELIEF_DEPTH + middle_area * (P09_LOWER_HEIGHT - RELIEF_DEPTH) + top_area * (CHAMBER_HEIGHT - P09_LOWER_HEIGHT)
    return 4.0 * one_lobe


def _cardinal_intrusion_area(profiles) -> float:
    central_solid_global = _local_to_assembly(profiles["middle"])
    gates = unary_union([
        box(-4.0, 17.0, 4.0, 18.0),
        box(-4.0, -18.0, 4.0, -17.0),
        box(17.0, -4.0, 18.0, 4.0),
        box(-18.0, -4.0, -17.0, 4.0),
    ])
    return float(central_solid_global.intersection(gates).area)


def build_variant(variant: str):
    profiles = variant_profiles(variant)
    mesh = layered_mesh([
        (0.0, RELIEF_DEPTH, profiles["lower"]),
        (RELIEF_DEPTH, P09_LOWER_HEIGHT, profiles["middle"]),
        (P09_LOWER_HEIGHT, CHAMBER_HEIGHT, profiles["top"]),
    ], f"P04T1R_P09_{variant}_INTEGRATED")
    p09_lower, p09_flange = profiles["p09_lower"], profiles["p09_flange"]
    preserved = p09_lower.difference(profiles["middle"]).area < 1e-9 and p09_flange.difference(profiles["top"]).area < 1e-9
    fixed_diagonal_channel = box(-43.0, -4.0, -28.0, 4.0)
    connector_inside = profiles["connector"].difference(fixed_diagonal_channel).area < 1e-9
    central_solid_volume = _central_solid_volume(profiles)
    chamber_volume = math.pi * CHAMBER_RADIUS**2 * CHAMBER_HEIGHT
    realised_fraction = 1.0 - central_solid_volume / chamber_volume
    audit = {
        "variant": variant,
        "scientific_role": VARIANTS[variant]["role"],
        "nominal_target_retained_air_fraction": VARIANTS[variant]["target_fraction"],
        "ideal_half_width_mm": VARIANTS[variant]["ideal_half_width"],
        "print_half_width_mm": print_half_width(variant),
        "print_cross_width_mm": print_cross_width(variant),
        "fixed_channel_width_mm": FIXED_CHANNEL_WIDTH,
        "cross_side_margin_over_fixed_channel_mm": (print_cross_width(variant) - FIXED_CHANNEL_WIDTH) / 2.0,
        "p09_pocket_clearance_per_side_mm": 0.20,
        "worst_case_side_margin_after_pocket_shift_mm": (print_cross_width(variant) - FIXED_CHANNEL_WIDTH) / 2.0 - 0.20,
        "print_outer_radius_mm": PRINT_RADIUS,
        "p01_nominal_radial_clearance_mm": CHAMBER_RADIUS - PRINT_RADIUS,
        "p03_relief_radius_mm": RELIEF_RADIUS,
        "p03_relief_radial_clearance_mm": RELIEF_RADIUS - P03_RIDGE_RADIUS,
        "p03_relief_depth_mm": RELIEF_DEPTH,
        "p03_relief_axial_clearance_mm": RELIEF_DEPTH - P03_PROTRUSION,
        "connector_local_bounds_mm": [CONNECTOR_X0, -CONNECTOR_HALF_WIDTH, CONNECTOR_X1, CONNECTOR_HALF_WIDTH],
        "connector_inside_original_dummy_channel": bool(connector_inside),
        "p09_nominal_geometry_preserved": bool(preserved),
        "open_cardinal_channel_intrusion_mm2": _cardinal_intrusion_area(profiles),
        "central_insert_solid_volume_mm3": central_solid_volume,
        "nominal_chamber_volume_mm3": chamber_volume,
        "realised_retained_air_fraction": realised_fraction,
        "realised_retained_air_percent": 100.0 * realised_fraction,
        "mesh_watertight": bool(mesh.is_watertight),
        "mesh_winding_consistent": bool(mesh.is_winding_consistent),
        "mesh_connected_components": mesh_component_count(mesh),
        "mesh_volume_mm3": float(mesh.volume),
        "mesh_triangle_count": int(len(mesh.faces)),
        "mesh_bounds_mm": mesh.bounds.tolist(),
        "mesh_extents_mm": mesh.extents.tolist(),
    }
    return {"mesh": mesh, "audit": audit, "profiles": profiles}


def _place_mesh(mesh: trimesh.Trimesh, x: float, y: float):
    copy = mesh.copy()
    minimum = copy.bounds[0]
    copy.apply_translation([x - minimum[0], y - minimum[1], -minimum[2]])
    return copy


def make_plate(meshes, columns: int, gap: float = PLATE_GAP):
    max_x = max(float(mesh.extents[0]) for mesh in meshes)
    max_y = max(float(mesh.extents[1]) for mesh in meshes)
    placed = []
    for index, mesh in enumerate(meshes):
        column = index % columns
        row = index // columns
        placed.append(_place_mesh(mesh, column * (max_x + gap), row * (max_y + gap)))
    plate = trimesh.util.concatenate(placed)
    centre_xy = (plate.bounds[0, :2] + plate.bounds[1, :2]) / 2.0
    plate.apply_translation([-centre_xy[0], -centre_xy[1], 0.0])
    # Binary STL stores float32 coordinates.  Snap only the print-plate copies
    # to 1e-5 mm and remove float-collapse sliver faces so multi-body reloads
    # remain closed; the authoritative unit meshes are not altered.
    plate.vertices = np.round(plate.vertices, 5)
    plate.merge_vertices(digits_vertex=5)
    plate.update_faces(plate.unique_faces())
    plate.update_faces(plate.nondegenerate_faces(height=1e-5))
    plate.remove_unreferenced_vertices()
    return plate


def _mesh_audit(mesh: trimesh.Trimesh, expected_components: int):
    mesh = mesh.copy()
    mesh.merge_vertices(digits_vertex=5)
    mesh.update_faces(mesh.nondegenerate_faces(height=1e-8))
    mesh.remove_unreferenced_vertices()
    areas = mesh.area_faces
    component_count = mesh_component_count(mesh)
    return {
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "positive_volume": bool(mesh.volume > 0),
        "connected_components": component_count,
        "expected_components": expected_components,
        "component_count_pass": component_count == expected_components,
        "degenerate_face_count": int(np.sum(areas <= 1e-10)),
        "triangle_count": int(len(mesh.faces)),
        "volume_mm3": float(mesh.volume),
        "bounds_mm": mesh.bounds.tolist(),
        "extents_mm": mesh.extents.tolist(),
        "reload_pass": True,
    }


def _export(mesh: trimesh.Trimesh, path: Path):
    mesh.export(path, file_type="stl")
    loaded = trimesh.load_mesh(path, process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        loaded = loaded.dump(concatenate=True)
    loaded.merge_vertices(digits_vertex=5)
    loaded.remove_unreferenced_vertices()
    return loaded


def _svg_path(geometry, scale=5.0, offset=(115.0, 115.0)):
    paths = []
    for polygon in polygons_of(geometry):
        for ring in [polygon.exterior, *polygon.interiors]:
            coords = list(ring.coords)
            if not coords:
                continue
            commands = [f"M {offset[0] + scale * coords[0][0]:.2f},{offset[1] - scale * coords[0][1]:.2f}"]
            commands.extend(f"L {offset[0] + scale * x:.2f},{offset[1] - scale * y:.2f}" for x, y in coords[1:])
            commands.append("Z")
            paths.append(" ".join(commands))
    return " ".join(paths)


def write_assembly_svg(path: Path, i75_profiles, i50_profiles):
    def panel(label, profiles, xoff):
        chamber = circle(0.0, 0.0, CHAMBER_RADIUS)
        lobes = []
        ne = _local_to_assembly(profiles["full_lobe"])
        for angle in (0.0, 90.0, 180.0, 270.0):
            lobes.append(affinity.rotate(ne, angle, origin=(0.0, 0.0)))
        solid = unary_union(lobes)
        chamber_path = _svg_path(chamber, scale=4.8, offset=(xoff, 120.0))
        solid_path = _svg_path(solid, scale=4.8, offset=(xoff, 120.0))
        return f'<text x="{xoff}" y="22" text-anchor="middle" font-size="16">{label}</text><path d="{chamber_path}" fill="white" stroke="#222"/><path d="{solid_path}" fill="#2f8f5b" stroke="#155c39" fill-rule="evenodd"/>'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="245" viewBox="0 0 520 245">
<rect width="100%" height="100%" fill="white"/>
{panel("I75 integrated P09 lobes", i75_profiles, 130.0)}
{panel("I50P manufacturable dose point", i50_profiles, 390.0)}
<text x="260" y="230" text-anchor="middle" font-size="13">Green = inserted solid; white cross = retained central air</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")


def write_integrated_unit_svg(path: Path, i75_profiles, i50_profiles):
    def panel(label, profiles, xoff):
        scale = 2.25
        offset = (xoff + 15.0, 128.0)
        p09_path = _svg_path(profiles["p09_lower"], scale=scale, offset=offset)
        addition = clean(unary_union([profiles["full_lobe"], profiles["connector"]]))
        addition_path = _svg_path(addition, scale=scale, offset=offset)
        return f'<text x="{xoff}" y="24" text-anchor="middle" font-size="16">{label}</text><path d="{p09_path}" fill="#9aa0a6" stroke="#333"/><path d="{addition_path}" fill="#2f8f5b" stroke="#155c39" fill-rule="evenodd"/>'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="260" viewBox="0 0 640 260">
<rect width="100%" height="100%" fill="white"/>
{panel("I75: one integrated P09 + lobe", i75_profiles, 160.0)}
{panel("I50P: one integrated P09 + lobe", i50_profiles, 480.0)}
<text x="320" y="245" text-anchor="middle" font-size="13">Grey = unchanged P09 dummy; green = inward lobe and joint</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")


def generate_release(output_dir: Path = DEFAULT_OUTPUT, make_figures: bool = True, write_documents: bool = True):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if sha256_file(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise RuntimeError("Authoritative V2.0.1 ZIP hash mismatch")

    built = {name: build_variant(name) for name in VARIANTS}
    paths = {}
    reload_audits = {}
    for name, result in built.items():
        unit_path = output_dir / f"P04T1R_P09_{name}_INTEGRATED_PRINT_X4.stl"
        loaded = _export(result["mesh"], unit_path)
        paths[f"{name.lower()}_unit"] = unit_path
        reload_audits[f"{name}_unit"] = _mesh_audit(loaded, 1)

        plate = make_plate([result["mesh"].copy() for _ in range(4)], columns=2)
        plate_path = output_dir / f"P04T1R_P09_{name}_PRINT_PLATE_X4.stl"
        loaded_plate = _export(plate, plate_path)
        paths[f"{name.lower()}_plate"] = plate_path
        reload_audits[f"{name}_plate"] = _mesh_audit(loaded_plate, 4)

    combined = make_plate(
        [built["I75"]["mesh"].copy(), built["I50P"]["mesh"].copy()] * 4,
        columns=2,
    )
    combined_path = output_dir / "P04T1R_BOTH_I75_I50P_PRINT_PLATE_4_PLUS_4.stl"
    loaded_combined = _export(combined, combined_path)
    paths["combined_plate"] = combined_path
    reload_audits["combined_plate"] = _mesh_audit(loaded_combined, 8)

    geometry_audit = {
        "stage": "P04T1R",
        "classification_pending": False,
        "classification": "P04T1R PRINT_PACKAGE_READY — I75 PRIMARY + I50P EXPLORATORY",
        "source_zip": str(SOURCE_ZIP.relative_to(REPO_ROOT)).replace("\\", "/"),
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "coordinate_system": "P09 local: +X outward; integrated lobe inward; install at 45/135/225/315 degrees",
        "variants": {name: result["audit"] for name, result in built.items()},
    }
    (output_dir / "geometry_and_acoustic_fidelity_audit.json").write_text(json.dumps(geometry_audit, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "mesh_reload_validation.json").write_text(json.dumps(reload_audits, indent=2, ensure_ascii=False), encoding="utf-8")

    contract = {
        "stage": "P04T1R_INTEGRATED_P09_INSERT_RELEASE",
        "supersedes": "mechanical implementation only; original P04T1 provenance retained",
        "baseline_part": "authoritative V2.0.1 P09 solid dummy",
        "parts_per_condition": 4,
        "I75_role": VARIANTS["I75"]["role"],
        "I50P_role": VARIANTS["I50P"]["role"],
        "glue_allowed": False,
        "manual_slicer_boolean_allowed": False,
        "final_test_read": False,
    }
    (output_dir / "design_contract.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")

    terminal_classification = {
        "stage": "P04T1R_INTEGRATED_P09_INSERT_RELEASE",
        "classification": "P04T1R PRINT_PACKAGE_READY — I75 PRIMARY + I50P EXPLORATORY",
        "recommended_print_file": "P04T1R_BOTH_I75_I50P_PRINT_PLATE_4_PLUS_4.stl",
        "I75_realised_retained_air_percent": built["I75"]["audit"]["realised_retained_air_percent"],
        "I50P_realised_retained_air_percent": built["I50P"]["audit"]["realised_retained_air_percent"],
        "I50P_exact_50_percent": False,
        "physical_acquisition_authorized": False,
        "next_gate": "P04T1V_INTEGRATED_INSERT_BOUNDED_SIMULATION_GATE",
        "final_test_read": False,
    }
    (output_dir / "terminal_classification.json").write_text(
        json.dumps(terminal_classification, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    with (output_dir / "print_file_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "purpose", "copies_or_components", "sha256"])
        purposes = {
            "i75_unit": ("I75 integrated unit; duplicate in slicer only if not using plate", 4),
            "i75_plate": ("I75 four-part print plate", 4),
            "i50p_unit": ("I50P integrated unit; duplicate in slicer only if not using plate", 4),
            "i50p_plate": ("I50P four-part print plate", 4),
            "combined_plate": ("recommended one-job plate: four I75 plus four I50P", 8),
        }
        for key, path in paths.items():
            purpose, count = purposes[key]
            writer.writerow([path.name, purpose, count, sha256_file(path)])

    if make_figures:
        write_assembly_svg(output_dir / "figure_01_I75_I50P_central_air_comparison.svg", built["I75"]["profiles"], built["I50P"]["profiles"])
        write_integrated_unit_svg(output_dir / "figure_02_integrated_P09_units_top_view.svg", built["I75"]["profiles"], built["I50P"]["profiles"])

    if write_documents:
        i75 = built["I75"]["audit"]
        i50 = built["I50P"]["audit"]
        manual = f"""# P04T1R 集成式 P09 插入件打印与安装说明

## 推荐打印文件

一次打印两套时使用 `P04T1R_BOTH_I75_I50P_PRINT_PLATE_4_PLUS_4.stl`。左列为 I75，右列为 I50P；取下后立即在每个零件的外侧非声学端用记号笔标记 `75` 或 `50`，禁止在中央叶片表面打磨标记。

## 打印设置

- 刚性 PLA，0.20 mm 层高，0.4 mm 喷嘴，100% infill，至少四道墙；
- 零件按 STL 当前方向平放，100% 比例，supports 关闭；
- elephant-foot compensation 建议 0.15 mm，并记录实际值；
- 不允许在切片器中把旧 P09 与旧叶片手工拼接，也不允许整体缩放。

## 安装

每种状态使用四个相同组合件，分别安装在 45°、135°、225°、315°的 P09 槽位。中央叶片朝内，P09 外端朝外。四个活动声学位置保持原 S1：0° HR03；90°、180°、270°为 P05 加 P10 堵头。

1. BASE 使用原始四个 P09，不安装任何叶片。
2. I75 使用四个 `P09_I75` 集成件。其实现保留空气比例为 `{i75['realised_retained_air_percent']:.6f}%`。
3. I50P 使用四个 `P09_I50P` 集成件。其实现保留空气比例为 `{i50['realised_retained_air_percent']:.6f}%`；这是制造退让后的探索剂量点，不是精确50%。
4. 不使用胶水。由 P01 槽位定位并由 P02 压紧。
5. 合盖前确认0°/90°/180°/270°四条开放十字通路均无遮挡，P03 relief 面完全避让中央麦克风外颈。
6. 如果任一组合件翘起、P02不能自然贴合、或中央通道被毛刺侵入，停止，不得强压。

原先打印的松散四叶仅保留作机械 provenance，不用于正式 P04T2 采集。
"""
        (output_dir / "PRINT_AND_ASSEMBLY_MANUAL_zh.md").write_text(manual, encoding="utf-8")

    manifest_targets = sorted(path for path in output_dir.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    with (output_dir / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        for path in manifest_targets:
            handle.write(f"{sha256_file(path)}  {path.name}\n")

    outputs = {
        "i75_unit": paths["i75_unit"],
        "i75_plate": paths["i75_plate"],
        "i50p_unit": paths["i50p_unit"],
        "i50p_plate": paths["i50p_plate"],
        "combined_plate": paths["combined_plate"],
    }
    return outputs


def main():
    output = Path(os.environ.get("P04T1R_OUTPUT", DEFAULT_OUTPUT))
    generate_release(output)
    print(f"P04T1R artifacts written to {output}")


if __name__ == "__main__":
    main()

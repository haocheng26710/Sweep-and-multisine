#!/usr/bin/env python3
"""Create a labelled, layered exploded V2 U4-Encoded assembly.

The script opens the verified assembled ``.blend`` and saves a separate exploded
project, leaving the assembled source project unchanged.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_v2_u4_encoded as common  # noqa: E402


MM = 0.001
ASSEMBLY_NAME = "V2_U4_ENCODED_HEAD"
EXPLODED_NAME = "V2_U4_ENCODED_LAYERED_EXPLODED"

EXPLODED_Z_MM = {
    "P03": -35.0,
    "P01": 0.0,
    "TRAYS_DUMMIES": 30.0,
    "MODULE_GASKETS": 55.0,
    "MODULE_LIDS": 78.0,
    "PRESSURE_PADS": 101.0,
    "P11": 124.0,
    "P02": 150.0,
}


def parse_args() -> argparse.Namespace:
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--input-blend", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(blender_args)


def set_object_z_mm(obj: bpy.types.Object, z_mm: float, layer: str) -> None:
    assembled_translation = list(obj.get("translation_mm", [value / MM for value in obj.location]))
    obj["assembled_translation_mm"] = assembled_translation
    obj.location.z = z_mm * MM
    exploded_translation = [obj.location.x / MM, obj.location.y / MM, z_mm]
    obj["exploded_translation_mm"] = exploded_translation
    obj["explosion_layer"] = layer


def make_line_material(name: str, rgba: tuple[float, float, float, float]) -> bpy.types.Material:
    material = common.make_material(name, rgba, roughness=0.55)
    return material


def make_polyline(
    name: str,
    points: list[Vector],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    bevel_depth: float,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(f"{name}_CURVE", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coordinate in zip(spline.points, points):
        point.co = (*coordinate, 1.0)
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    return obj


def write_manifest(output_dir: Path, objects: list[bpy.types.Object]) -> None:
    layer_order = [
        {"order": 1, "layer": "P03", "label": "P03 Microphone insert", "z_origin_mm": EXPLODED_Z_MM["P03"]},
        {"order": 2, "layer": "P01", "label": "P01 Eight-slot base", "z_origin_mm": EXPLODED_Z_MM["P01"]},
        {"order": 3, "layer": "TRAYS_DUMMIES", "label": "P06 A/B/D/F trays + P09 dummies", "z_origin_mm": EXPLODED_Z_MM["TRAYS_DUMMIES"]},
        {"order": 4, "layer": "MODULE_GASKETS", "label": "P08 Module gaskets", "z_origin_mm": EXPLODED_Z_MM["MODULE_GASKETS"]},
        {"order": 5, "layer": "MODULE_LIDS", "label": "P07 Module lids", "z_origin_mm": EXPLODED_Z_MM["MODULE_LIDS"]},
        {"order": 6, "layer": "PRESSURE_PADS", "label": "P08B Pressure pads", "z_origin_mm": EXPLODED_Z_MM["PRESSURE_PADS"]},
        {"order": 7, "layer": "P11", "label": "P11 Main-lid gasket", "z_origin_mm": EXPLODED_Z_MM["P11"]},
        {"order": 8, "layer": "P02", "label": "P02 Main lid", "z_origin_mm": EXPLODED_Z_MM["P02"]},
    ]
    records = []
    for obj in sorted(objects, key=lambda item: item.name):
        records.append(
            {
                "object_name": obj.name,
                "source_stl": obj.get("source_stl"),
                "source_sha256": obj.get("source_sha256"),
                "explosion_layer": obj.get("explosion_layer"),
                "assembled_translation_mm": list(obj.get("assembled_translation_mm", [])),
                "exploded_translation_mm": list(obj.get("exploded_translation_mm", [])),
                "rotation_xyz_deg": list(obj.get("rotation_xyz_deg", [])),
            }
        )
    payload = {
        "presentation": EXPLODED_NAME,
        "assembly_source": ASSEMBLY_NAME,
        "units": "mm",
        "excluded": ["P14/P15/P16 turntable", "V2.5 corner baffles"],
        "layer_order": layer_order,
        "objects": records,
    }
    (output_dir / "v2_u4_encoded_exploded_pose_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "v2_u4_encoded_exploded_pose_manifest.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "object_name",
                "source_stl",
                "source_sha256",
                "explosion_layer",
                "assembled_tx_mm",
                "assembled_ty_mm",
                "assembled_tz_mm",
                "exploded_tx_mm",
                "exploded_ty_mm",
                "exploded_tz_mm",
                "rx_deg",
                "ry_deg",
                "rz_deg",
            ]
        )
        for record in records:
            writer.writerow(
                [
                    record["object_name"],
                    record["source_stl"],
                    record["source_sha256"],
                    record["explosion_layer"],
                    *record["assembled_translation_mm"],
                    *record["exploded_translation_mm"],
                    *record["rotation_xyz_deg"],
                ]
            )


def main() -> None:
    args = parse_args()
    repo_root = (args.repo_root or SCRIPT_DIR.parents[1]).resolve()
    input_blend = (
        args.input_blend
        or repo_root
        / "outputs"
        / "blender_visualization"
        / "v2_u4_encoded"
        / "V2_U4_Encoded_Head.blend"
    ).resolve()
    output_dir = (
        args.output_dir
        or repo_root / "outputs" / "blender_visualization" / "v2_u4_encoded_exploded"
    ).resolve()
    if not input_blend.is_file():
        raise FileNotFoundError(input_blend)
    output_dir.mkdir(parents=True, exist_ok=True)

    if Path(bpy.data.filepath).resolve() != input_blend:
        bpy.ops.wm.open_mainfile(filepath=str(input_blend))
    scene = bpy.context.scene
    if scene.get("assembly_name") != ASSEMBLY_NAME:
        raise RuntimeError(f"Unexpected source assembly: {scene.get('assembly_name')}")
    source_blend_sha256 = common.sha256_file(input_blend)

    original_annotations = bpy.data.collections.get("08_ANNOTATIONS")
    if original_annotations is not None:
        original_annotations.hide_render = True
        original_annotations.hide_viewport = True

    source_objects = [obj for obj in bpy.data.objects if obj.get("source_stl")]
    if len(source_objects) != 28:
        raise RuntimeError(f"Expected 28 source objects, found {len(source_objects)}")

    set_object_z_mm(bpy.data.objects["P03_IMM6C_INSERT"], EXPLODED_Z_MM["P03"], "P03")
    set_object_z_mm(bpy.data.objects["P01_UNIVERSAL_8SLOT_BASE"], EXPLODED_Z_MM["P01"], "P01")
    for obj in bpy.data.collections["02_TRAYS_AND_DUMMIES"].objects:
        set_object_z_mm(obj, EXPLODED_Z_MM["TRAYS_DUMMIES"], "TRAYS_DUMMIES")
    for obj in bpy.data.collections["03_MODULE_GASKETS"].objects:
        set_object_z_mm(obj, EXPLODED_Z_MM["MODULE_GASKETS"], "MODULE_GASKETS")
    for obj in bpy.data.collections["04_MODULE_LIDS"].objects:
        set_object_z_mm(obj, EXPLODED_Z_MM["MODULE_LIDS"], "MODULE_LIDS")
    for obj in bpy.data.collections["05_PRESSURE_PADS"].objects:
        set_object_z_mm(obj, EXPLODED_Z_MM["PRESSURE_PADS"], "PRESSURE_PADS")
    set_object_z_mm(bpy.data.objects["P11_MAIN_LID_GASKET"], EXPLODED_Z_MM["P11"], "P11")
    set_object_z_mm(bpy.data.objects["P02_MAIN_LID"], EXPLODED_Z_MM["P02"], "P02")

    root_collection = bpy.data.collections[ASSEMBLY_NAME]
    annotation_collection = common.new_collection("09_EXPLODED_LABELS_AND_GUIDES", root_collection)
    label_material = common.make_material("MAT_EXPLODED_LABEL", (0.018, 0.03, 0.055, 1.0), roughness=0.52)
    leader_material = make_line_material("MAT_EXPLODED_LEADER", (0.12, 0.20, 0.32, 0.85))
    guide_material = make_line_material("MAT_EXPLODED_GUIDE", (0.20, 0.46, 0.72, 0.28))

    camera = bpy.data.objects.get("CAMERA_TECHNICAL")
    if camera is None:
        raise RuntimeError("Missing CAMERA_TECHNICAL")
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 0.46
    camera.location = (0.34, -0.42, 0.31)
    common.look_at(camera, (0.0, 0.0, 0.060))
    scene.camera = camera

    camera_rotation = camera.matrix_world.to_quaternion()
    screen_right = camera_rotation @ Vector((1.0, 0.0, 0.0))

    label_specs = [
        ("LBL_P03", "P03  Microphone insert", -31.75, 0.018),
        ("LBL_P01", "P01  Eight-slot base", 6.10, 0.110),
        ("LBL_P06_P09", "P06 A/B/D/F trays + P09 dummies", 33.80, 0.110),
        ("LBL_P08", "P08  Module gaskets", 55.20, 0.110),
        ("LBL_P07", "P07  Module lids", 78.60, 0.110),
        ("LBL_P08B", "P08B  Pressure pads", 101.30, 0.110),
        ("LBL_P11", "P11  Main-lid gasket", 124.30, 0.110),
        ("LBL_P02", "P02  Main lid", 152.50, 0.110),
    ]
    for name, body, centre_z_mm, anchor_radius_m in label_specs:
        centre = Vector((0.0, 0.0, centre_z_mm * MM))
        anchor = centre + screen_right * anchor_radius_m
        leader_end = centre + screen_right * 0.130
        label_location = centre + screen_right * 0.158
        make_polyline(
            f"{name}_LEADER",
            [anchor, leader_end],
            annotation_collection,
            leader_material,
            0.00028,
        )
        label = common.make_text(
            name,
            body,
            tuple(label_location),
            annotation_collection,
            label_material,
        )
        label.data.size = 0.0056
        label.data.extrude = 0.000035
        label.rotation_euler = camera.rotation_euler

    guide_xy_mm = ((0.0, 60.0), (60.0, 0.0), (0.0, -60.0), (-60.0, 0.0))
    for index, (x_mm, y_mm) in enumerate(guide_xy_mm):
        make_polyline(
            f"EXPLOSION_GUIDE_{index + 1:02d}",
            [
                Vector((x_mm * MM, y_mm * MM, 12.5 * MM)),
                Vector((x_mm * MM, y_mm * MM, 149.5 * MM)),
            ],
            annotation_collection,
            guide_material,
            0.00018,
        )

    p02_material = bpy.data.materials.get("MAT_P02_TRANSLUCENT")
    if p02_material is not None:
        rgba = list(p02_material.diffuse_color)
        rgba[3] = 0.38
        p02_material.diffuse_color = rgba
        shader = p02_material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Alpha"].default_value = 0.38

    light_targets = {
        "KEY_AREA": ((0.27, -0.30, 0.38), 68.0),
        "FILL_AREA": ((-0.28, -0.12, 0.28), 34.0),
        "RIM_AREA": ((0.02, 0.30, 0.37), 48.0),
    }
    for name, (location, energy) in light_targets.items():
        light = bpy.data.objects.get(name)
        if light is not None:
            light.location = location
            light.data.energy = energy
            common.look_at(light, (0.0, 0.0, 0.065))

    scene.render.resolution_x = 1800
    scene.render.resolution_y = 2000
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene["assembly_name"] = EXPLODED_NAME
    scene["assembled_source_blend"] = str(input_blend)
    scene["assembled_source_blend_sha256"] = source_blend_sha256
    scene["explosion_axis"] = "+Z"
    scene["explosion_layer_count"] = 8

    write_manifest(output_dir, source_objects)

    labelled_path = output_dir / "v2_u4_encoded_exploded_layered.png"
    scene.render.filepath = str(labelled_path)
    bpy.ops.render.render(write_still=True)

    annotation_collection.hide_render = True
    clean_path = output_dir / "v2_u4_encoded_exploded_clean.png"
    scene.render.filepath = str(clean_path)
    bpy.ops.render.render(write_still=True)
    annotation_collection.hide_render = False

    blend_path = output_dir / "V2_U4_Encoded_Layered_Exploded.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(
        json.dumps(
            {
                "blend": str(blend_path),
                "labelled_png": str(labelled_path),
                "clean_png": str(clean_path),
                "manifest_json": str(output_dir / "v2_u4_encoded_exploded_pose_manifest.json"),
                "manifest_csv": str(output_dir / "v2_u4_encoded_exploded_pose_manifest.csv"),
                "source_object_count": len(source_objects),
                "layer_count": 8,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

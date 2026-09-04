#!/usr/bin/env python3
"""Build the V2 U4-Encoded head assembly in Blender.

Run with Blender, for example::

    blender --background --factory-startup \
      --python scripts/blender/build_v2_u4_encoded.py -- \
      --repo-root <repository> --output-dir <output-directory>

Source STL files are imported read-only.  Geometry is converted from millimetres
to Blender metres with object scale 0.001; the documented CAD axes are retained.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


MM = 0.001
PACKAGE_SHA256 = "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f"
ASSEMBLY_NAME = "V2_U4_ENCODED_HEAD"


def parse_args() -> argparse.Namespace:
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(blender_args)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)


def new_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    if parent is None:
        bpy.context.scene.collection.children.link(collection)
    else:
        parent.children.link(collection)
    return collection


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def make_material(
    name: str,
    rgba: tuple[float, float, float, float],
    roughness: float = 0.45,
    metallic: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = rgba
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = rgba
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Alpha"].default_value = rgba[3]
    if rgba[3] < 0.999:
        if hasattr(material, "surface_render_method"):
            material.surface_render_method = "DITHERED"
        material.use_transparency_overlap = False
    return material


def assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj.color = material.diffuse_color


def import_stl(
    path: Path,
    object_name: str,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
) -> bpy.types.Object:
    if not path.is_file():
        raise FileNotFoundError(path)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.wm.stl_import(
        filepath=str(path),
        global_scale=MM,
        use_scene_unit=False,
        use_facet_normal=True,
        use_mesh_validate=True,
        forward_axis="Y",
        up_axis="Z",
    )
    obj = bpy.context.object
    obj.name = object_name
    obj.data.name = f"{object_name}_MESH"
    move_to_collection(obj, collection)
    assign_material(obj, material)
    obj["source_stl"] = path.name
    obj["source_sha256"] = sha256_file(path)
    obj["source_units"] = "mm"
    obj["assembly_state"] = ASSEMBLY_NAME
    return obj


def set_pose(
    obj: bpy.types.Object,
    translation_mm: tuple[float, float, float],
    rotation_xyz_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    obj.location = tuple(value * MM for value in translation_mm)
    obj.rotation_euler = tuple(math.radians(value) for value in rotation_xyz_deg)
    obj["translation_mm"] = list(translation_mm)
    obj["rotation_xyz_deg"] = list(rotation_xyz_deg)


def slot_pose(theta_deg: float, z_mm: float) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    theta = math.radians(theta_deg)
    translation = (60.0 * math.sin(theta), 60.0 * math.cos(theta), z_mm)
    rotation = (0.0, 0.0, 90.0 - theta_deg)
    return translation, rotation


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_text(
    name: str,
    body: str,
    location_m: tuple[float, float, float],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(f"{name}_CURVE", "FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = 0.008
    curve.extrude = 0.00006
    curve.bevel_depth = 0.000015
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.location = location_m
    return obj


def add_area_light(
    name: str,
    location: tuple[float, float, float],
    energy: float,
    size: float,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    light_obj = bpy.data.objects.new(name, light_data)
    collection.objects.link(light_obj)
    light_obj.location = location
    look_at(light_obj, (0.0, 0.0, 0.006))
    return light_obj


def configure_scene(scene: bpy.types.Scene) -> None:
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1400
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    scene.render.use_file_extension = True
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -1.15
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.045, 0.055, 0.075, 1.0)
    background.inputs["Strength"].default_value = 0.08
    scene["assembly_name"] = ASSEMBLY_NAME
    scene["source_package_sha256"] = PACKAGE_SHA256
    scene["source_units"] = "mm"
    scene["p02_pose_assumption"] = "uncompressed 0.6 mm P08B/P11; P02 origin z=12.8 mm"


def pose_record(
    obj: bpy.types.Object,
    role: str,
    source_root: Path,
    source_path: Path,
    theta_deg: float | None = None,
    note: str = "",
) -> dict[str, object]:
    return {
        "object_name": obj.name,
        "role": role,
        "source_stl": source_path.relative_to(source_root).as_posix(),
        "source_sha256": obj["source_sha256"],
        "theta_deg": theta_deg,
        "translation_mm": list(obj["translation_mm"]),
        "rotation_xyz_deg": list(obj["rotation_xyz_deg"]),
        "object_scale": list(obj.scale),
        "note": note,
    }


def write_pose_outputs(output_dir: Path, records: list[dict[str, object]]) -> None:
    payload = {
        "assembly": ASSEMBLY_NAME,
        "units": "mm",
        "blender_unit_conversion": "STL object scale = 0.001 m/mm",
        "device_frame": {
            "origin": "P01 centre on base bottom plane",
            "+x": "90 deg / East",
            "+y": "0 deg / North",
            "+z": "up",
        },
        "configuration": {
            "0": "A / P06_01",
            "45": "P09 dummy",
            "90": "B / P06_02",
            "135": "P09 dummy",
            "180": "D / P06_04",
            "225": "P09 dummy",
            "270": "F / P06_06",
            "315": "P09 dummy",
        },
        "excluded": ["P14/P15/P16 turntable", "V2.5 corner baffles"],
        "assumptions": [
            "P02 is shown at z=12.8 mm for an uncompressed, non-intersecting 0.6 mm gasket/pad stack.",
            "Fasteners and the physical microphone body are not present because the package supplies no corresponding assembly STL.",
        ],
        "objects": records,
    }
    json_path = output_dir / "v2_u4_encoded_pose_manifest.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    csv_path = output_dir / "v2_u4_encoded_pose_manifest.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "object_name",
                "role",
                "source_stl",
                "source_sha256",
                "theta_deg",
                "tx_mm",
                "ty_mm",
                "tz_mm",
                "rx_deg",
                "ry_deg",
                "rz_deg",
                "note",
            ]
        )
        for record in records:
            translation = record["translation_mm"]
            rotation = record["rotation_xyz_deg"]
            writer.writerow(
                [
                    record["object_name"],
                    record["role"],
                    record["source_stl"],
                    record["source_sha256"],
                    record["theta_deg"],
                    *translation,
                    *rotation,
                    record["note"],
                ]
            )


def main() -> None:
    args = parse_args()
    script_path = Path(__file__).resolve()
    repo_root = (args.repo_root or script_path.parents[2]).resolve()
    source_root = (
        args.source_root
        or repo_root
        / "work"
        / "blender_visualization"
        / "source_packages"
        / "v2_0_1"
        / "Acoustic_Morphology_Encoder_V2.0.1"
        / "STL"
    ).resolve()
    output_dir = (
        args.output_dir
        or repo_root / "outputs" / "blender_visualization" / "v2_u4_encoded"
    ).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Missing V2 STL directory: {source_root}")
    output_dir.mkdir(parents=True, exist_ok=True)

    clear_scene()
    scene = bpy.context.scene
    configure_scene(scene)

    root = new_collection(ASSEMBLY_NAME)
    collections = {
        "structure": new_collection("01_STRUCTURE", root),
        "trays": new_collection("02_TRAYS_AND_DUMMIES", root),
        "gaskets": new_collection("03_MODULE_GASKETS", root),
        "lids": new_collection("04_MODULE_LIDS", root),
        "pads": new_collection("05_PRESSURE_PADS", root),
        "main_gasket": new_collection("06_MAIN_GASKET", root),
        "main_lid": new_collection("07_MAIN_LID", root),
        "annotations": new_collection("08_ANNOTATIONS", root),
        "camera_lights": new_collection("99_CAMERAS_LIGHTS", root),
    }

    materials = {
        "base": make_material("MAT_P01_WARM_GREY", (0.54, 0.58, 0.63, 1.0), roughness=0.55),
        "mic": make_material("MAT_P03_CHARCOAL", (0.055, 0.065, 0.08, 1.0), roughness=0.34),
        "dummy": make_material("MAT_P09_DUMMY", (0.17, 0.19, 0.22, 1.0), roughness=0.62),
        "A": make_material("MAT_MODULE_A", (0.08, 0.34, 0.72, 1.0), roughness=0.38),
        "B": make_material("MAT_MODULE_B", (0.08, 0.55, 0.24, 1.0), roughness=0.38),
        "D": make_material("MAT_MODULE_D", (0.43, 0.21, 0.69, 1.0), roughness=0.38),
        "F": make_material("MAT_MODULE_F", (0.72, 0.12, 0.52, 1.0), roughness=0.38),
        "gasket": make_material("MAT_GASKET_DARK", (0.025, 0.035, 0.045, 0.82), roughness=0.8),
        "pad": make_material("MAT_PRESSURE_PAD", (0.94, 0.58, 0.15, 0.45), roughness=0.68),
        "main_gasket": make_material("MAT_MAIN_GASKET", (0.055, 0.075, 0.095, 0.68), roughness=0.82),
        "lid": make_material("MAT_P02_TRANSLUCENT", (0.72, 0.83, 0.94, 0.22), roughness=0.22),
        "label": make_material("MAT_LABEL", (0.018, 0.025, 0.04, 1.0), roughness=0.5),
    }

    records: list[dict[str, object]] = []

    p01_path = source_root / "P01_universal_8slot_base.stl"
    p01 = import_stl(p01_path, "P01_UNIVERSAL_8SLOT_BASE", collections["structure"], materials["base"])
    set_pose(p01, (0.0, 0.0, 0.0))
    records.append(pose_record(p01, "head_base", source_root, p01_path))

    p03_path = source_root / "P03_mic_insert_ID9_0_for_Dayton_iMM6C.stl"
    p03 = import_stl(p03_path, "P03_IMM6C_INSERT", collections["structure"], materials["mic"])
    set_pose(p03, (0.0, 0.0, -3.0))
    records.append(
        pose_record(
            p03,
            "microphone_insert",
            source_root,
            p03_path,
            note="3 mm flange below P01; nominal microphone tip reaches device z=7 mm",
        )
    )

    module_specs = {
        0.0: {
            "code": "A",
            "tray": "P06_01_A_short_straight_tray.stl",
            "gasket": "P08_01_A_short_straight_module_gasket_TPU.stl",
            "lid": "P07_01_A_short_straight_lid.stl",
        },
        90.0: {
            "code": "B",
            "tray": "P06_02_B_long_serpentine_tray.stl",
            "gasket": "P08_02_B_long_serpentine_module_gasket_TPU.stl",
            "lid": "P07_02_B_long_serpentine_lid.stl",
        },
        180.0: {
            "code": "D",
            "tray": "P06_04_D_straight_stub29_tray.stl",
            "gasket": "P08_04_D_straight_stub29_module_gasket_TPU.stl",
            "lid": "P07_04_D_straight_stub29_lid.stl",
        },
        270.0: {
            "code": "F",
            "tray": "P06_06_F_expansion_stub14_tray.stl",
            "gasket": "P08_06_F_expansion_stub14_module_gasket_TPU.stl",
            "lid": "P07_06_F_expansion_stub14_lid.stl",
        },
    }
    pad_path = source_root / "P08B_universal_module_top_pressure_pad_PRINT_8_TPU.stl"

    for theta_deg, spec in module_specs.items():
        code = spec["code"]
        tray_path = source_root / spec["tray"]
        tray = import_stl(
            tray_path,
            f"SLOT_{int(theta_deg):03d}_{code}_TRAY",
            collections["trays"],
            materials[code],
        )
        translation, rotation = slot_pose(theta_deg, 3.0)
        set_pose(tray, translation, rotation)
        tray["theta_deg"] = theta_deg
        records.append(pose_record(tray, f"module_{code}_tray", source_root, tray_path, theta_deg))

        gasket_path = source_root / spec["gasket"]
        gasket = import_stl(
            gasket_path,
            f"SLOT_{int(theta_deg):03d}_{code}_GASKET",
            collections["gaskets"],
            materials["gasket"],
        )
        translation, rotation = slot_pose(theta_deg, 10.6)
        set_pose(gasket, translation, rotation)
        gasket["theta_deg"] = theta_deg
        records.append(pose_record(gasket, f"module_{code}_gasket", source_root, gasket_path, theta_deg))

        lid_path = source_root / spec["lid"]
        lid = import_stl(
            lid_path,
            f"SLOT_{int(theta_deg):03d}_{code}_LID",
            collections["lids"],
            materials[code],
        )
        translation, rotation = slot_pose(theta_deg, 11.0)
        set_pose(lid, translation, rotation)
        lid["theta_deg"] = theta_deg
        records.append(pose_record(lid, f"module_{code}_lid", source_root, lid_path, theta_deg))

        pad = import_stl(
            pad_path,
            f"SLOT_{int(theta_deg):03d}_{code}_PRESSURE_PAD",
            collections["pads"],
            materials["pad"],
        )
        translation, rotation = slot_pose(theta_deg, 12.2)
        set_pose(pad, translation, rotation)
        pad["theta_deg"] = theta_deg
        records.append(pose_record(pad, "module_pressure_pad", source_root, pad_path, theta_deg))

    dummy_path = source_root / "P09_solid_dummy_module_PRINT_4.stl"
    for theta_deg in (45.0, 135.0, 225.0, 315.0):
        dummy = import_stl(
            dummy_path,
            f"SLOT_{int(theta_deg):03d}_P09_DUMMY",
            collections["trays"],
            materials["dummy"],
        )
        translation, rotation = slot_pose(theta_deg, 3.0)
        set_pose(dummy, translation, rotation)
        dummy["theta_deg"] = theta_deg
        records.append(pose_record(dummy, "P09_dummy", source_root, dummy_path, theta_deg))

        pad = import_stl(
            pad_path,
            f"SLOT_{int(theta_deg):03d}_DUMMY_PRESSURE_PAD",
            collections["pads"],
            materials["pad"],
        )
        translation, rotation = slot_pose(theta_deg, 12.2)
        set_pose(pad, translation, rotation)
        pad["theta_deg"] = theta_deg
        records.append(pose_record(pad, "dummy_pressure_pad", source_root, pad_path, theta_deg))

    p11_path = source_root / "P11_main_lid_gasket_universal_8piece_TPU.stl"
    p11 = import_stl(p11_path, "P11_MAIN_LID_GASKET", collections["main_gasket"], materials["main_gasket"])
    set_pose(p11, (0.0, 0.0, 12.2))
    records.append(pose_record(p11, "main_lid_gasket", source_root, p11_path))

    p02_path = source_root / "P02_main_lid_with_captive_nut_traps.stl"
    p02 = import_stl(p02_path, "P02_MAIN_LID", collections["main_lid"], materials["lid"])
    set_pose(p02, (0.0, 0.0, 12.8))
    records.append(
        pose_record(
            p02,
            "main_lid",
            source_root,
            p02_path,
            note="uncompressed nominal gasket/pad stack; avoids visual intersection",
        )
    )

    for name, body, location in (
        ("LABEL_N_A", "0° / N · A", (0.0, 0.126, 0.021)),
        ("LABEL_E_B", "90° / E · B", (0.126, 0.0, 0.021)),
        ("LABEL_S_D", "180° / S · D", (0.0, -0.126, 0.021)),
        ("LABEL_W_F", "270° / W · F", (-0.126, 0.0, 0.021)),
    ):
        make_text(name, body, location, collections["annotations"], materials["label"])

    camera_data = bpy.data.cameras.new("CAMERA_TECHNICAL")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 0.34
    camera_data.lens = 52
    camera = bpy.data.objects.new("CAMERA_TECHNICAL", camera_data)
    collections["camera_lights"].objects.link(camera)
    scene.camera = camera

    add_area_light("KEY_AREA", (0.22, -0.24, 0.34), 55.0, 0.24, collections["camera_lights"])
    add_area_light("FILL_AREA", (-0.24, -0.10, 0.22), 28.0, 0.20, collections["camera_lights"])
    add_area_light("RIM_AREA", (0.02, 0.26, 0.30), 38.0, 0.18, collections["camera_lights"])

    write_pose_outputs(output_dir, records)

    camera.location = (0.26, -0.30, 0.255)
    camera.data.ortho_scale = 0.335
    look_at(camera, (0.0, 0.0, 0.0065))
    scene.render.filepath = str(output_dir / "v2_u4_encoded_assembled_isometric.png")
    bpy.ops.render.render(write_still=True)

    hidden_for_cutaway = []
    for obj in (p02, p11):
        hidden_for_cutaway.append((obj, obj.hide_render))
        obj.hide_render = True
    for collection_key in ("gaskets", "lids", "pads"):
        for obj in collections[collection_key].objects:
            hidden_for_cutaway.append((obj, obj.hide_render))
            obj.hide_render = True

    camera.location = (0.0, 0.0, 0.50)
    camera.data.ortho_scale = 0.31
    look_at(camera, (0.0, 0.0, 0.0))
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.filepath = str(output_dir / "v2_u4_encoded_internal_top.png")
    bpy.ops.render.render(write_still=True)

    for obj, original_hidden in hidden_for_cutaway:
        obj.hide_render = original_hidden
    camera.location = (0.26, -0.30, 0.255)
    camera.data.ortho_scale = 0.335
    look_at(camera, (0.0, 0.0, 0.0065))
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1400

    blend_path = output_dir / "V2_U4_Encoded_Head.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(json.dumps({
        "blend": str(blend_path),
        "isometric": str(output_dir / "v2_u4_encoded_assembled_isometric.png"),
        "internal_top": str(output_dir / "v2_u4_encoded_internal_top.png"),
        "pose_json": str(output_dir / "v2_u4_encoded_pose_manifest.json"),
        "pose_csv": str(output_dir / "v2_u4_encoded_pose_manifest.csv"),
        "object_count": len(records),
    }, indent=2))


if __name__ == "__main__":
    main()

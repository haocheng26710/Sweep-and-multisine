#!/usr/bin/env python3
"""Build the V2.5 U4-HR head assembly without turntable or corner baffles."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_v2_u4_encoded as common  # noqa: E402


ASSEMBLY_NAME = "V2_5_U4_HR_HEAD"
V2_PACKAGE_SHA256 = "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f"
V25_PACKAGE_SHA256 = "849566111d121bdcf581018a31ec1759ad39646001a258e367732c21a85b401f"


def parse_args() -> argparse.Namespace:
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--v2-source-root", type=Path)
    parser.add_argument("--v25-source-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args(blender_args)


def add_pose_record(
    records: list[dict[str, object]],
    obj: bpy.types.Object,
    role: str,
    package_name: str,
    source_root: Path,
    source_path: Path,
    theta_deg: float | None = None,
    note: str = "",
) -> None:
    record = common.pose_record(obj, role, source_root, source_path, theta_deg, note)
    record["source_package"] = package_name
    records.append(record)


def write_pose_outputs(output_dir: Path, records: list[dict[str, object]]) -> None:
    payload = {
        "assembly": ASSEMBLY_NAME,
        "units": "mm",
        "blender_unit_conversion": "STL object scale = 0.001 m/mm",
        "source_packages": {
            "V2.0.1 shared hardware": V2_PACKAGE_SHA256,
            "V2.5 HR patch": V25_PACKAGE_SHA256,
        },
        "device_frame": {
            "origin": "P01 centre on base bottom plane",
            "+x": "90 deg / East",
            "+y": "0 deg / North",
            "+z": "up",
        },
        "configuration": {
            "0": "HR01 / 1200 Hz",
            "45": "V2 P09 dummy",
            "90": "HR03 / 1850 Hz",
            "135": "V2 P09 dummy",
            "180": "HR05 / 2700 Hz",
            "225": "V2 P09 dummy",
            "270": "HR07 / 3800 Hz",
            "315": "V2 P09 dummy",
        },
        "excluded": ["P14/P15/P16 turntable", "V2.5 corner baffles"],
        "assumptions": [
            "P02 is shown at z=12.8 mm for an uncompressed, non-intersecting 0.6 mm gasket/pad stack.",
            "Fasteners and the physical microphone body are not present because the packages supply no corresponding assembly STL.",
            "V2.5 HR tray/gasket/lid files replace V2 P06/P08/P07 only at the four active U4 cardinal slots.",
        ],
        "objects": records,
    }
    json_path = output_dir / "v2_5_u4_hr_pose_manifest.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    csv_path = output_dir / "v2_5_u4_hr_pose_manifest.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "object_name",
                "role",
                "source_package",
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
            writer.writerow(
                [
                    record["object_name"],
                    record["role"],
                    record["source_package"],
                    record["source_stl"],
                    record["source_sha256"],
                    record["theta_deg"],
                    *record["translation_mm"],
                    *record["rotation_xyz_deg"],
                    record["note"],
                ]
            )


def main() -> None:
    args = parse_args()
    repo_root = (args.repo_root or SCRIPT_DIR.parents[1]).resolve()
    v2_root = (
        args.v2_source_root
        or repo_root
        / "work"
        / "blender_visualization"
        / "source_packages"
        / "v2_0_1"
        / "Acoustic_Morphology_Encoder_V2.0.1"
        / "STL"
    ).resolve()
    v25_root = (
        args.v25_source_root
        or repo_root
        / "work"
        / "blender_visualization"
        / "source_packages"
        / "v2_5_patch"
        / "Acoustic_Morphology_Encoder_V2.5_Patch"
        / "Acoustic_Morphology_Encoder_V2.5_Patch"
        / "STL"
    ).resolve()
    output_dir = (
        args.output_dir
        or repo_root / "outputs" / "blender_visualization" / "v2_5_u4_hr"
    ).resolve()
    for root in (v2_root, v25_root):
        if not root.is_dir():
            raise FileNotFoundError(root)
    output_dir.mkdir(parents=True, exist_ok=True)

    common.ASSEMBLY_NAME = ASSEMBLY_NAME
    common.PACKAGE_SHA256 = V25_PACKAGE_SHA256
    common.clear_scene()
    scene = bpy.context.scene
    common.configure_scene(scene)
    scene["source_v2_package_sha256"] = V2_PACKAGE_SHA256
    scene["source_v25_package_sha256"] = V25_PACKAGE_SHA256
    scene["configuration"] = "V2.5 U4-HR: HR01/HR03/HR05/HR07 at cardinal slots"
    scene["excluded_hardware"] = "P14/P15/P16 turntable; V2.5 corner baffles"

    root = common.new_collection(ASSEMBLY_NAME)
    collections = {
        "structure": common.new_collection("01_V2_SHARED_STRUCTURE", root),
        "trays": common.new_collection("02_HR_TRAYS_AND_V2_DUMMIES", root),
        "gaskets": common.new_collection("03_HR_GASKETS", root),
        "lids": common.new_collection("04_HR_LIDS", root),
        "pads": common.new_collection("05_V2_PRESSURE_PADS", root),
        "main_gasket": common.new_collection("06_V2_MAIN_GASKET", root),
        "main_lid": common.new_collection("07_V2_MAIN_LID", root),
        "annotations": common.new_collection("08_ANNOTATIONS", root),
        "camera_lights": common.new_collection("99_CAMERAS_LIGHTS", root),
    }

    materials = {
        "base": common.make_material("MAT_V2_SHARED_BASE", (0.34, 0.39, 0.46, 1.0), roughness=0.56),
        "mic": common.make_material("MAT_P03_CHARCOAL", (0.045, 0.06, 0.08, 1.0), roughness=0.34),
        "dummy": common.make_material("MAT_P09_DUMMY", (0.13, 0.15, 0.18, 1.0), roughness=0.64),
        "HR01": common.make_material("MAT_HR01_1200HZ", (0.035, 0.25, 0.80, 1.0), roughness=0.36),
        "HR03": common.make_material("MAT_HR03_1850HZ", (0.00, 0.56, 0.55, 1.0), roughness=0.36),
        "HR05": common.make_material("MAT_HR05_2700HZ", (0.95, 0.43, 0.06, 1.0), roughness=0.36),
        "HR07": common.make_material("MAT_HR07_3800HZ", (0.72, 0.06, 0.46, 1.0), roughness=0.36),
        "gasket": common.make_material("MAT_HR_GASKET", (0.02, 0.03, 0.045, 0.84), roughness=0.82),
        "pad": common.make_material("MAT_V2_PRESSURE_PAD", (0.95, 0.62, 0.16, 0.46), roughness=0.70),
        "main_gasket": common.make_material("MAT_V2_MAIN_GASKET", (0.045, 0.065, 0.09, 0.70), roughness=0.84),
        "lid": common.make_material("MAT_V2_MAIN_LID_TRANSLUCENT", (0.65, 0.79, 0.94, 0.21), roughness=0.24),
        "label": common.make_material("MAT_LABEL", (0.015, 0.022, 0.04, 1.0), roughness=0.5),
    }

    records: list[dict[str, object]] = []

    p01_path = v2_root / "P01_universal_8slot_base.stl"
    p01 = common.import_stl(p01_path, "P01_UNIVERSAL_8SLOT_BASE", collections["structure"], materials["base"])
    common.set_pose(p01, (0.0, 0.0, 0.0))
    add_pose_record(records, p01, "head_base", "V2.0.1", v2_root, p01_path)

    p03_path = v2_root / "P03_mic_insert_ID9_0_for_Dayton_iMM6C.stl"
    p03 = common.import_stl(p03_path, "P03_IMM6C_INSERT", collections["structure"], materials["mic"])
    common.set_pose(p03, (0.0, 0.0, -3.0))
    add_pose_record(
        records,
        p03,
        "microphone_insert",
        "V2.0.1",
        v2_root,
        p03_path,
        note="3 mm flange below P01; nominal microphone tip reaches device z=7 mm",
    )

    module_specs = {
        0.0: {
            "id": "HR01",
            "target_hz": 1200,
            "tray": "V25_HR01_1200Hz_HR_tray.stl",
            "gasket": "V25_HR01_1200Hz_HR_gasket_TPU.stl",
            "lid": "V25_HR01_1200Hz_HR_lid.stl",
        },
        90.0: {
            "id": "HR03",
            "target_hz": 1850,
            "tray": "V25_HR03_1850Hz_HR_tray.stl",
            "gasket": "V25_HR03_1850Hz_HR_gasket_TPU.stl",
            "lid": "V25_HR03_1850Hz_HR_lid.stl",
        },
        180.0: {
            "id": "HR05",
            "target_hz": 2700,
            "tray": "V25_HR05_2700Hz_HR_tray.stl",
            "gasket": "V25_HR05_2700Hz_HR_gasket_TPU.stl",
            "lid": "V25_HR05_2700Hz_HR_lid.stl",
        },
        270.0: {
            "id": "HR07",
            "target_hz": 3800,
            "tray": "V25_HR07_3800Hz_HR_tray.stl",
            "gasket": "V25_HR07_3800Hz_HR_gasket_TPU.stl",
            "lid": "V25_HR07_3800Hz_HR_lid.stl",
        },
    }
    pad_path = v2_root / "P08B_universal_module_top_pressure_pad_PRINT_8_TPU.stl"

    for theta_deg, spec in module_specs.items():
        module_id = spec["id"]
        note = f"V2.5 two-neck HR module; target {spec['target_hz']} Hz"

        tray_path = v25_root / spec["tray"]
        tray = common.import_stl(
            tray_path,
            f"SLOT_{int(theta_deg):03d}_{module_id}_TRAY",
            collections["trays"],
            materials[module_id],
        )
        translation, rotation = common.slot_pose(theta_deg, 3.0)
        common.set_pose(tray, translation, rotation)
        tray["theta_deg"] = theta_deg
        tray["target_hz"] = spec["target_hz"]
        add_pose_record(records, tray, f"{module_id}_tray", "V2.5", v25_root, tray_path, theta_deg, note)

        gasket_path = v25_root / spec["gasket"]
        gasket = common.import_stl(
            gasket_path,
            f"SLOT_{int(theta_deg):03d}_{module_id}_GASKET",
            collections["gaskets"],
            materials["gasket"],
        )
        translation, rotation = common.slot_pose(theta_deg, 10.6)
        common.set_pose(gasket, translation, rotation)
        gasket["theta_deg"] = theta_deg
        gasket["target_hz"] = spec["target_hz"]
        add_pose_record(records, gasket, f"{module_id}_gasket", "V2.5", v25_root, gasket_path, theta_deg, note)

        lid_path = v25_root / spec["lid"]
        lid = common.import_stl(
            lid_path,
            f"SLOT_{int(theta_deg):03d}_{module_id}_LID",
            collections["lids"],
            materials[module_id],
        )
        translation, rotation = common.slot_pose(theta_deg, 11.0)
        common.set_pose(lid, translation, rotation)
        lid["theta_deg"] = theta_deg
        lid["target_hz"] = spec["target_hz"]
        add_pose_record(records, lid, f"{module_id}_lid", "V2.5", v25_root, lid_path, theta_deg, note)

        pad = common.import_stl(
            pad_path,
            f"SLOT_{int(theta_deg):03d}_{module_id}_PRESSURE_PAD",
            collections["pads"],
            materials["pad"],
        )
        translation, rotation = common.slot_pose(theta_deg, 12.2)
        common.set_pose(pad, translation, rotation)
        pad["theta_deg"] = theta_deg
        add_pose_record(records, pad, "module_pressure_pad", "V2.0.1", v2_root, pad_path, theta_deg)

    dummy_path = v2_root / "P09_solid_dummy_module_PRINT_4.stl"
    for theta_deg in (45.0, 135.0, 225.0, 315.0):
        dummy = common.import_stl(
            dummy_path,
            f"SLOT_{int(theta_deg):03d}_P09_DUMMY",
            collections["trays"],
            materials["dummy"],
        )
        translation, rotation = common.slot_pose(theta_deg, 3.0)
        common.set_pose(dummy, translation, rotation)
        dummy["theta_deg"] = theta_deg
        add_pose_record(records, dummy, "P09_dummy", "V2.0.1", v2_root, dummy_path, theta_deg)

        pad = common.import_stl(
            pad_path,
            f"SLOT_{int(theta_deg):03d}_DUMMY_PRESSURE_PAD",
            collections["pads"],
            materials["pad"],
        )
        translation, rotation = common.slot_pose(theta_deg, 12.2)
        common.set_pose(pad, translation, rotation)
        pad["theta_deg"] = theta_deg
        add_pose_record(records, pad, "dummy_pressure_pad", "V2.0.1", v2_root, pad_path, theta_deg)

    p11_path = v2_root / "P11_main_lid_gasket_universal_8piece_TPU.stl"
    p11 = common.import_stl(p11_path, "P11_MAIN_LID_GASKET", collections["main_gasket"], materials["main_gasket"])
    common.set_pose(p11, (0.0, 0.0, 12.2))
    add_pose_record(records, p11, "main_lid_gasket", "V2.0.1", v2_root, p11_path)

    p02_path = v2_root / "P02_main_lid_with_captive_nut_traps.stl"
    p02 = common.import_stl(p02_path, "P02_MAIN_LID", collections["main_lid"], materials["lid"])
    common.set_pose(p02, (0.0, 0.0, 12.8))
    add_pose_record(
        records,
        p02,
        "main_lid",
        "V2.0.1",
        v2_root,
        p02_path,
        note="uncompressed nominal gasket/pad stack; avoids visual intersection",
    )

    for name, body, location in (
        ("LABEL_N_HR01", "0° / N · HR01\n1.20 kHz", (0.0, 0.128, 0.021)),
        ("LABEL_E_HR03", "90° / E · HR03\n1.85 kHz", (0.128, 0.0, 0.021)),
        ("LABEL_S_HR05", "180° / S · HR05\n2.70 kHz", (0.0, -0.128, 0.021)),
        ("LABEL_W_HR07", "270° / W · HR07\n3.80 kHz", (-0.128, 0.0, 0.021)),
    ):
        label = common.make_text(name, body, location, collections["annotations"], materials["label"])
        label.data.size = 0.0064

    camera_data = bpy.data.cameras.new("CAMERA_TECHNICAL")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 0.35
    camera = bpy.data.objects.new("CAMERA_TECHNICAL", camera_data)
    collections["camera_lights"].objects.link(camera)
    scene.camera = camera

    common.add_area_light("KEY_AREA", (0.22, -0.24, 0.34), 55.0, 0.24, collections["camera_lights"])
    common.add_area_light("FILL_AREA", (-0.24, -0.10, 0.22), 28.0, 0.20, collections["camera_lights"])
    common.add_area_light("RIM_AREA", (0.02, 0.26, 0.30), 38.0, 0.18, collections["camera_lights"])

    write_pose_outputs(output_dir, records)

    camera.location = (0.26, -0.30, 0.255)
    camera.data.ortho_scale = 0.35
    common.look_at(camera, (0.0, 0.0, 0.0065))
    scene.render.filepath = str(output_dir / "v2_5_u4_hr_assembled_isometric.png")
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
    camera.data.ortho_scale = 0.335
    common.look_at(camera, (0.0, 0.0, 0.0))
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1600
    scene.render.filepath = str(output_dir / "v2_5_u4_hr_internal_top.png")
    bpy.ops.render.render(write_still=True)

    for obj, original_hidden in hidden_for_cutaway:
        obj.hide_render = original_hidden
    camera.location = (0.26, -0.30, 0.255)
    camera.data.ortho_scale = 0.35
    common.look_at(camera, (0.0, 0.0, 0.0065))
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1400

    blend_path = output_dir / "V2_5_U4_HR_Head.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(
        json.dumps(
            {
                "blend": str(blend_path),
                "isometric": str(output_dir / "v2_5_u4_hr_assembled_isometric.png"),
                "internal_top": str(output_dir / "v2_5_u4_hr_internal_top.png"),
                "pose_json": str(output_dir / "v2_5_u4_hr_pose_manifest.json"),
                "pose_csv": str(output_dir / "v2_5_u4_hr_pose_manifest.csv"),
                "object_count": len(records),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

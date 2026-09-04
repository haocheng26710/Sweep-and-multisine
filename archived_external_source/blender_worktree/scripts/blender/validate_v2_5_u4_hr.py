#!/usr/bin/env python3
"""Validate the generated V2.5 U4-HR Blender assembly and renders."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_v2_u4_encoded import MM, check_png, close, slot_translation, vector_close  # noqa: E402


V2_SHA256 = "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f"
V25_SHA256 = "849566111d121bdcf581018a31ec1759ad39646001a258e367732c21a85b401f"


def parse_args() -> argparse.Namespace:
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(blender_args)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, details: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    scene = bpy.context.scene
    record("assembly name", scene.get("assembly_name") == "V2_5_U4_HR_HEAD", scene.get("assembly_name"))
    record("source units", scene.get("source_units") == "mm", scene.get("source_units"))
    record("V2 source package hash", scene.get("source_v2_package_sha256") == V2_SHA256, scene.get("source_v2_package_sha256"))
    record("V2.5 source package hash", scene.get("source_v25_package_sha256") == V25_SHA256, scene.get("source_v25_package_sha256"))
    record(
        "P02 assumption recorded",
        "z=12.8 mm" in scene.get("p02_pose_assumption", ""),
        scene.get("p02_pose_assumption"),
    )

    source_objects = [obj for obj in bpy.data.objects if obj.get("source_stl")]
    record("source object count", len(source_objects) == 28, len(source_objects))
    record(
        "all source objects use millimetres",
        all(obj.get("source_units") == "mm" for obj in source_objects),
        sorted({obj.get("source_units") for obj in source_objects}),
    )
    record(
        "all STL imports use 0.001 object scale",
        all(vector_close(obj.scale, (MM, MM, MM)) for obj in source_objects),
        {obj.name: list(obj.scale) for obj in source_objects if not vector_close(obj.scale, (MM, MM, MM))},
    )

    forbidden = [
        obj.name
        for obj in bpy.data.objects
        if any(token in obj.name.upper() for token in ("P14", "P15", "P16", "BAFFLE"))
    ]
    record("turntable and baffles excluded", not forbidden, forbidden)

    fixed_poses = {
        "P01_UNIVERSAL_8SLOT_BASE": (0.0, 0.0, 0.0),
        "P03_IMM6C_INSERT": (0.0, 0.0, -3.0 * MM),
        "P11_MAIN_LID_GASKET": (0.0, 0.0, 12.2 * MM),
        "P02_MAIN_LID": (0.0, 0.0, 12.8 * MM),
    }
    for name, expected in fixed_poses.items():
        obj = bpy.data.objects.get(name)
        record(
            f"{name} pose",
            obj is not None and vector_close(obj.location, expected),
            None if obj is None else list(obj.location),
        )

    hr_expectations = {
        "SLOT_000_HR01_TRAY": (0.0, 1200, "V25_HR01_1200Hz_HR_tray.stl"),
        "SLOT_090_HR03_TRAY": (90.0, 1850, "V25_HR03_1850Hz_HR_tray.stl"),
        "SLOT_180_HR05_TRAY": (180.0, 2700, "V25_HR05_2700Hz_HR_tray.stl"),
        "SLOT_270_HR07_TRAY": (270.0, 3800, "V25_HR07_3800Hz_HR_tray.stl"),
    }
    for name, (theta_deg, target_hz, source_stl) in hr_expectations.items():
        obj = bpy.data.objects.get(name)
        expected_location = slot_translation(theta_deg, 3.0)
        expected_rotation_z = math.radians(90.0 - theta_deg)
        passed = (
            obj is not None
            and vector_close(obj.location, expected_location)
            and close(float(obj.rotation_euler.z), expected_rotation_z)
            and obj.get("target_hz") == target_hz
            and obj.get("source_stl") == source_stl
        )
        record(
            f"{name} HR slot identity and transform",
            passed,
            None
            if obj is None
            else {
                "location": list(obj.location),
                "rotation_z": float(obj.rotation_euler.z),
                "target_hz": obj.get("target_hz"),
                "source_stl": obj.get("source_stl"),
            },
        )

    for theta_deg in (45.0, 135.0, 225.0, 315.0):
        name = f"SLOT_{int(theta_deg):03d}_P09_DUMMY"
        obj = bpy.data.objects.get(name)
        expected_rotation_z = math.radians(90.0 - theta_deg)
        passed = (
            obj is not None
            and vector_close(obj.location, slot_translation(theta_deg, 3.0))
            and close(float(obj.rotation_euler.z), expected_rotation_z)
            and obj.get("source_stl") == "P09_solid_dummy_module_PRINT_4.stl"
        )
        record(
            f"{name} dummy transform",
            passed,
            None if obj is None else {"location": list(obj.location), "rotation_z": float(obj.rotation_euler.z)},
        )

    expected_collections = {
        "V2_5_U4_HR_HEAD",
        "01_V2_SHARED_STRUCTURE",
        "02_HR_TRAYS_AND_V2_DUMMIES",
        "03_HR_GASKETS",
        "04_HR_LIDS",
        "05_V2_PRESSURE_PADS",
        "06_V2_MAIN_GASKET",
        "07_V2_MAIN_LID",
        "08_ANNOTATIONS",
        "99_CAMERAS_LIGHTS",
    }
    actual_collections = set(bpy.data.collections.keys())
    record("collection structure", expected_collections.issubset(actual_collections), sorted(expected_collections - actual_collections))

    pose_path = output_dir / "v2_5_u4_hr_pose_manifest.json"
    pose_payload = json.loads(pose_path.read_text(encoding="utf-8"))
    pose_objects = pose_payload.get("objects", [])
    package_counts = Counter(item.get("source_package") for item in pose_objects)
    record("pose manifest object count", len(pose_objects) == 28, len(pose_objects))
    record("pose manifest package split", package_counts == {"V2.0.1": 16, "V2.5": 12}, dict(package_counts))
    record(
        "pose manifest exclusions",
        pose_payload.get("excluded") == ["P14/P15/P16 turntable", "V2.5 corner baffles"],
        pose_payload.get("excluded"),
    )

    render_checks = [
        check_png(output_dir / "v2_5_u4_hr_assembled_isometric.png", (1800, 1400)),
        check_png(output_dir / "v2_5_u4_hr_internal_top.png", (1600, 1600)),
    ]
    for render in render_checks:
        record(
            f"render {Path(render['path']).name}",
            bool(render["size_ok"] and render["rgba_ok"] and render["transparent_corners_ok"]),
            render,
        )

    report = {
        "assembly": "V2_5_U4_HR_HEAD",
        "blend_file": bpy.data.filepath,
        "passed": all(check["passed"] for check in checks),
        "check_count": len(checks),
        "failed_count": sum(not check["passed"] for check in checks),
        "checks": checks,
    }
    report_path = output_dir / "v2_5_u4_hr_validation_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate the generated V2 U4-Encoded Blender assembly and render outputs."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy


MM = 0.001
TOLERANCE = 1e-6


def parse_args() -> argparse.Namespace:
    blender_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(blender_args)


def close(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def vector_close(actual, expected, tolerance: float = TOLERANCE) -> bool:
    return all(close(float(a), float(e), tolerance) for a, e in zip(actual, expected))


def slot_translation(theta_deg: float, z_mm: float) -> tuple[float, float, float]:
    theta = math.radians(theta_deg)
    return (
        60.0 * math.sin(theta) * MM,
        60.0 * math.cos(theta) * MM,
        z_mm * MM,
    )


def check_png(path: Path, expected_size: tuple[int, int]) -> dict[str, object]:
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    corner_pixels = ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))
    corner_alpha = [float(image.pixels[(y * width + x) * 4 + 3]) for x, y in corner_pixels]
    result = {
        "path": str(path),
        "size": [width, height],
        "channels": image.channels,
        "corner_alpha": corner_alpha,
        "size_ok": (width, height) == expected_size,
        "rgba_ok": image.channels == 4,
        "transparent_corners_ok": all(alpha <= 1e-6 for alpha in corner_alpha),
    }
    bpy.data.images.remove(image)
    return result


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, details: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "details": details})

    scene = bpy.context.scene
    record("assembly name", scene.get("assembly_name") == "V2_U4_ENCODED_HEAD", scene.get("assembly_name"))
    record("source units", scene.get("source_units") == "mm", scene.get("source_units"))
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

    slot_expectations = {
        "SLOT_000_A_TRAY": (0.0, 3.0),
        "SLOT_090_B_TRAY": (90.0, 3.0),
        "SLOT_180_D_TRAY": (180.0, 3.0),
        "SLOT_270_F_TRAY": (270.0, 3.0),
        "SLOT_045_P09_DUMMY": (45.0, 3.0),
        "SLOT_135_P09_DUMMY": (135.0, 3.0),
        "SLOT_225_P09_DUMMY": (225.0, 3.0),
        "SLOT_315_P09_DUMMY": (315.0, 3.0),
    }
    for name, (theta_deg, z_mm) in slot_expectations.items():
        obj = bpy.data.objects.get(name)
        expected_location = slot_translation(theta_deg, z_mm)
        expected_rotation_z = math.radians(90.0 - theta_deg)
        passed = (
            obj is not None
            and vector_close(obj.location, expected_location)
            and close(float(obj.rotation_euler.z), expected_rotation_z)
        )
        record(
            f"{name} slot transform",
            passed,
            None
            if obj is None
            else {"location": list(obj.location), "rotation_z": float(obj.rotation_euler.z)},
        )

    expected_collections = {
        "V2_U4_ENCODED_HEAD",
        "01_STRUCTURE",
        "02_TRAYS_AND_DUMMIES",
        "03_MODULE_GASKETS",
        "04_MODULE_LIDS",
        "05_PRESSURE_PADS",
        "06_MAIN_GASKET",
        "07_MAIN_LID",
        "08_ANNOTATIONS",
        "99_CAMERAS_LIGHTS",
    }
    actual_collections = set(bpy.data.collections.keys())
    record(
        "collection structure",
        expected_collections.issubset(actual_collections),
        sorted(expected_collections - actual_collections),
    )

    pose_json = output_dir / "v2_u4_encoded_pose_manifest.json"
    pose_payload = json.loads(pose_json.read_text(encoding="utf-8"))
    record("pose manifest object count", len(pose_payload.get("objects", [])) == 28, len(pose_payload.get("objects", [])))
    record(
        "pose manifest exclusions",
        pose_payload.get("excluded") == ["P14/P15/P16 turntable", "V2.5 corner baffles"],
        pose_payload.get("excluded"),
    )

    render_checks = [
        check_png(output_dir / "v2_u4_encoded_assembled_isometric.png", (1800, 1400)),
        check_png(output_dir / "v2_u4_encoded_internal_top.png", (1600, 1600)),
    ]
    for render in render_checks:
        record(
            f"render {Path(render['path']).name}",
            bool(render["size_ok"] and render["rgba_ok"] and render["transparent_corners_ok"]),
            render,
        )

    report = {
        "assembly": "V2_U4_ENCODED_HEAD",
        "blend_file": bpy.data.filepath,
        "passed": all(check["passed"] for check in checks),
        "check_count": len(checks),
        "failed_count": sum(not check["passed"] for check in checks),
        "checks": checks,
    }
    report_path = output_dir / "v2_u4_encoded_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

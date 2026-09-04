#!/usr/bin/env python3
"""Validate the V2 U4-Encoded layered exploded Blender deliverable."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


MM = 0.001
TOLERANCE = 1e-6
EXPECTED_Z_MM = {
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
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(blender_args)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def check_png(path: Path, expected_size: tuple[int, int]) -> dict[str, object]:
    image = bpy.data.images.load(str(path), check_existing=False)
    width, height = image.size
    corners = ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))
    corner_alpha = [float(image.pixels[(y * width + x) * 4 + 3]) for x, y in corners]
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
    record(
        "presentation name",
        scene.get("assembly_name") == "V2_U4_ENCODED_LAYERED_EXPLODED",
        scene.get("assembly_name"),
    )
    record("explosion axis", scene.get("explosion_axis") == "+Z", scene.get("explosion_axis"))
    record("layer count", scene.get("explosion_layer_count") == 8, scene.get("explosion_layer_count"))

    source_objects = [obj for obj in bpy.data.objects if obj.get("source_stl")]
    record("source object count", len(source_objects) == 28, len(source_objects))
    forbidden = [
        obj.name
        for obj in bpy.data.objects
        if any(token in obj.name.upper() for token in ("P14", "P15", "P16", "BAFFLE"))
    ]
    record("turntable and baffles excluded", not forbidden, forbidden)

    missing_layer_metadata: list[str] = []
    pose_errors: dict[str, object] = {}
    orientation_errors: dict[str, object] = {}
    for obj in source_objects:
        layer = obj.get("explosion_layer")
        assembled = list(obj.get("assembled_translation_mm", []))
        exploded = list(obj.get("exploded_translation_mm", []))
        if layer not in EXPECTED_Z_MM or len(assembled) != 3 or len(exploded) != 3:
            missing_layer_metadata.append(obj.name)
            continue
        expected_z = EXPECTED_Z_MM[layer]
        actual_mm = [float(value) / MM for value in obj.location]
        expected_mm = [float(assembled[0]), float(assembled[1]), expected_z]
        if not all(close(a, e, 1e-4) for a, e in zip(actual_mm, expected_mm)):
            pose_errors[obj.name] = {"actual_mm": actual_mm, "expected_mm": expected_mm}
        if not all(close(a, e, 1e-4) for a, e in zip(exploded, expected_mm)):
            pose_errors[f"{obj.name}:metadata"] = {
                "exploded_translation_mm": exploded,
                "expected_mm": expected_mm,
            }
        recorded_rotation = list(obj.get("rotation_xyz_deg", []))
        actual_rotation = [float(value) * 180.0 / 3.141592653589793 for value in obj.rotation_euler]
        if len(recorded_rotation) != 3 or not all(
            close(a, e, 1e-4) for a, e in zip(actual_rotation, recorded_rotation)
        ):
            orientation_errors[obj.name] = {
                "actual_deg": actual_rotation,
                "recorded_deg": recorded_rotation,
            }
    record("all source objects have layer metadata", not missing_layer_metadata, missing_layer_metadata)
    record("exploded poses preserve XY and use layer Z", not pose_errors, pose_errors)
    record("source orientations unchanged", not orientation_errors, orientation_errors)

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
        "09_EXPLODED_LABELS_AND_GUIDES",
        "99_CAMERAS_LIGHTS",
    }
    actual_collections = set(bpy.data.collections.keys())
    record(
        "collection structure",
        expected_collections.issubset(actual_collections),
        sorted(expected_collections - actual_collections),
    )
    annotation_collection = bpy.data.collections.get("09_EXPLODED_LABELS_AND_GUIDES")
    annotation_names = set() if annotation_collection is None else {obj.name for obj in annotation_collection.objects}
    expected_labels = {
        "LBL_P03",
        "LBL_P01",
        "LBL_P06_P09",
        "LBL_P08",
        "LBL_P07",
        "LBL_P08B",
        "LBL_P11",
        "LBL_P02",
    }
    record("all eight layer labels present", expected_labels.issubset(annotation_names), sorted(expected_labels - annotation_names))
    expected_guides = {f"EXPLOSION_GUIDE_{index:02d}" for index in range(1, 5)}
    record("four alignment guides present", expected_guides.issubset(annotation_names), sorted(expected_guides - annotation_names))

    source_blend = Path(scene.get("assembled_source_blend", ""))
    source_hash = scene.get("assembled_source_blend_sha256")
    source_hash_actual = sha256_file(source_blend) if source_blend.is_file() else None
    record(
        "assembled source remains unchanged",
        source_hash_actual is not None and source_hash_actual == source_hash,
        {"path": str(source_blend), "recorded_sha256": source_hash, "actual_sha256": source_hash_actual},
    )

    manifest_path = output_dir / "v2_u4_encoded_exploded_pose_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record("manifest object count", len(manifest.get("objects", [])) == 28, len(manifest.get("objects", [])))
    record("manifest layer count", len(manifest.get("layer_order", [])) == 8, len(manifest.get("layer_order", [])))
    record(
        "manifest exclusions",
        manifest.get("excluded") == ["P14/P15/P16 turntable", "V2.5 corner baffles"],
        manifest.get("excluded"),
    )

    csv_path = output_dir / "v2_u4_encoded_exploded_pose_manifest.csv"
    csv_line_count = len(csv_path.read_text(encoding="utf-8-sig").splitlines())
    record("CSV contains header plus 28 objects", csv_line_count == 29, csv_line_count)

    for filename in (
        "v2_u4_encoded_exploded_layered.png",
        "v2_u4_encoded_exploded_clean.png",
    ):
        render = check_png(output_dir / filename, (1800, 2000))
        record(
            f"render {filename}",
            bool(render["size_ok"] and render["rgba_ok"] and render["transparent_corners_ok"]),
            render,
        )

    report = {
        "presentation": "V2_U4_ENCODED_LAYERED_EXPLODED",
        "blend_file": bpy.data.filepath,
        "passed": all(check["passed"] for check in checks),
        "check_count": len(checks),
        "failed_count": sum(not check["passed"] for check in checks),
        "checks": checks,
    }
    report_path = output_dir / "v2_u4_encoded_exploded_validation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

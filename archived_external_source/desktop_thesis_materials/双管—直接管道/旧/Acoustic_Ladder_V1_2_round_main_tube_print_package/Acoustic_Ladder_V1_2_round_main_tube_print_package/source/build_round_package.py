"""Build a complete V1.2 print package with equal-area round main lumens."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import trimesh

import v1_params as p
from assemblies import save_all_assemblies
from build_v1 import make_records
from geometry_utils import bbox_tuple, export_step, export_stl, print_oriented
from parts.main_tubes import all_main_tubes_round, equal_area_round_lumen_diameter
from validation import validate


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
BUILD_ROOT = ROOT / "round_variant_build"
EXPORTS = BUILD_ROOT / "exports"
STEP_DIR = EXPORTS / "step"
STL_DIR = EXPORTS / "stl"
ASSEMBLY_DIR = EXPORTS / "assemblies"
REPORT_DIR = EXPORTS / "reports"
PRINT_PLATE_DIR = EXPORTS / "print_plates"
PACKAGE_NAME = "Acoustic_Ladder_V1_2_round_main_tube_print_package"
STAGE = WORKSPACE / "outputs" / PACKAGE_NAME
ZIP_PATH = WORKSPACE / "outputs" / f"{PACKAGE_NAME}.zip"

TUBE_NAMES = (
    "ALV1_TX_front_0_200",
    "ALV1_TX_rear_200_400",
    "ALV1_RX_front_0_200",
    "ALV1_RX_rear_200_400",
)


def _safe_recreate(directory: Path) -> None:
    resolved = directory.resolve()
    allowed_parents = {ROOT.resolve(), (WORKSPACE / "outputs").resolve()}
    if resolved.parent not in allowed_parents:
        raise RuntimeError(f"Refusing to recreate unexpected path: {resolved}")
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)


def _round_records():
    records = make_records(include_coupons=True)
    round_shapes = all_main_tubes_round()
    for name in TUBE_NAMES:
        record = records[name]
        record.shape = round_shapes[name]
        # Put the tube axis along printer Z.  The socket/collar end is grounded;
        # the split male cone never becomes a first-layer feature.
        record.print_axis = (0, 1, 0)
        record.print_degrees = -90.0
    return records


def _export(records) -> None:
    for directory in (STEP_DIR, STL_DIR, ASSEMBLY_DIR, REPORT_DIR, PRINT_PLATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records.values(), start=1):
        print(f"[{index:02d}/{len(records):02d}] {record.name}", flush=True)
        export_step(record.shape, STEP_DIR / f"{record.name}_assembly.step")
        printable = print_oriented(
            record.shape, record.print_axis, record.print_degrees
        )
        stl_path = STL_DIR / f"{record.name}_print.stl"
        export_stl(
            printable,
            stl_path,
            p.STL_LINEAR_TOLERANCE,
            p.STL_ANGULAR_TOLERANCE,
        )
        if record.category == "coupon":
            shutil.copy2(stl_path, PRINT_PLATE_DIR / stl_path.name)

    parts = {name: record.shape for name, record in records.items()}
    save_all_assemblies(parts, ASSEMBLY_DIR)


def _copy_base_reports() -> None:
    source = ROOT / "exports" / "reports"
    if source.exists():
        for path in source.iterdir():
            if path.is_file():
                shutil.copy2(path, REPORT_DIR / path.name)


def _write_round_reports(records, validation_result) -> None:
    radius = p.MAIN_INNER_RADIUS
    teardrop_area = 0.5 * math.pi * radius ** 2 + radius * p.MAIN_ROOF_HEIGHT
    diameter = equal_area_round_lumen_diameter()
    parameters = {
        "variant": "V1.2 equal-area round main lumen",
        "round_lumen_target_diameter_mm": diameter,
        "round_lumen_area_mm2": math.pi * diameter ** 2 / 4.0,
        "round_lumen_perimeter_mm": math.pi * diameter,
        "round_lumen_hydraulic_diameter_mm": diameter,
        "reference_teardrop_area_mm2": teardrop_area,
        "external_interfaces": "unchanged from V1.1",
        "tube_print_orientation": "axis along printer Z; -90 deg about global Y",
        "validation": {
            "pass": validation_result["pass"],
            "warning": validation_result["warning"],
            "fail": validation_result["fail"],
        },
    }
    (REPORT_DIR / "round_tube_parameters_v1_2.json").write_text(
        json.dumps(parameters, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print_rows = []
    all_ok = True
    for name in TUBE_NAMES:
        record = records[name]
        printable = print_oriented(record.shape, record.print_axis, record.print_degrees)
        dimensions = bbox_tuple(printable)
        mesh = trimesh.load_mesh(str(STL_DIR / f"{name}_print.stl"), process=True)
        fits = (
            dimensions[0] <= p.MAX_BUILD_X
            and dimensions[1] <= p.MAX_BUILD_Y
            and dimensions[2] <= p.MAX_BUILD_Z
        )
        ok = record.shape.val().isValid() and mesh.is_watertight and fits
        all_ok = all_ok and ok
        print_rows.append(
            {
                "part": name,
                "print_x_mm": round(dimensions[0], 3),
                "print_y_mm": round(dimensions[1], 3),
                "print_z_mm": round(dimensions[2], 3),
                "brep_valid": record.shape.val().isValid(),
                "stl_watertight": bool(mesh.is_watertight),
                "single_shell": len(mesh.split(only_watertight=False)) == 1,
                "fits_256mm_build_volume": fits,
            }
        )
    (REPORT_DIR / "round_tube_print_validation_v1_2.json").write_text(
        json.dumps(print_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not all_ok:
        raise RuntimeError("Round tube print validation failed")

    original_validation = REPORT_DIR / "validation_report_v1.txt"
    if original_validation.exists():
        shutil.copy2(
            original_validation,
            REPORT_DIR / "validation_report_round_v1_2.txt",
        )


def _renamed(filename: str, kind: str) -> str:
    for name in TUBE_NAMES:
        suffix = "_print.stl" if kind == "stl" else "_assembly.step"
        if filename == f"{name}{suffix}":
            return f"{name}_round{suffix}"
    if kind == "assembly" and filename.endswith(".step"):
        return filename[:-5] + "_round.step"
    return filename


def _write_package_readme() -> None:
    diameter = equal_area_round_lumen_diameter()
    text = f"""# Acoustic Ladder V1.2 圆形主管打印包

本包将四段主管的内部水滴形流道替换为等截面积圆形流道，目标内径为
`{diameter:.4f} mm`。主管外轮廓、六个节点锥座、中间拼接接口、端部锥座、
锁耳与支撑配合尺寸全部保持 V1.1 不变，因此其余模块和附件可直接通用。

## 圆形主管文件

- `ALV1_TX_front_0_200_round_print.stl`
- `ALV1_TX_rear_200_400_round_print.stl`
- `ALV1_RX_front_0_200_round_print.stl`
- `ALV1_RX_rear_200_400_round_print.stl`

四个 STL 已预先将主管轴线沿打印机 Z 轴竖直摆放，并将较宽的锥孔/加强套端
置于平台侧，避免中间拼接公头成为第一层。不要再次使用切片器“自动朝向”。

## 建议切片设置

- PLA/PLA+，0.4 mm 喷嘴，0.16--0.20 mm 层高，5 道壁；
- 外裙边 15--25 mm，象脚补偿约 0.20 mm；
- 只允许外部支撑，禁止支撑进入主管内孔和节点喉道；
- Z 缝放在主管背面并避开六个节点；
- 首次正式打印前先用短圆孔试件确认实际孔径。

## 兼容性

`stl/` 内除四段主管外的零件与 V1.1 相同。圆形主管与水滴形主管机械上可以
拼接，但会产生内部截面突变，不建议在同一组声学对照实验中混装。

## 验证

圆形主管已检查 OCCT BREP 有效性、STL 水密性、单壳体、256 mm 构建空间以及
V1.1 全套机械装配关系。详细结果见 `reports/`。
"""
    (STAGE / "README_圆形主管打印说明.md").write_text(text, encoding="utf-8")


def _stage_package() -> None:
    _safe_recreate(STAGE)
    for folder in ("stl", "step", "assemblies", "print_plates", "reports", "source"):
        (STAGE / folder).mkdir(parents=True, exist_ok=True)

    for path in STL_DIR.glob("*.stl"):
        shutil.copy2(path, STAGE / "stl" / _renamed(path.name, "stl"))
    for path in STEP_DIR.glob("*.step"):
        shutil.copy2(path, STAGE / "step" / _renamed(path.name, "step"))
    for path in ASSEMBLY_DIR.glob("*.step"):
        shutil.copy2(path, STAGE / "assemblies" / _renamed(path.name, "assembly"))
    for path in PRINT_PLATE_DIR.glob("*.stl"):
        shutil.copy2(path, STAGE / "print_plates" / path.name)
    for path in REPORT_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, STAGE / "reports" / path.name)

    shutil.copy2(ROOT / "parts" / "main_tubes.py", STAGE / "source" / "main_tubes.py")
    shutil.copy2(Path(__file__), STAGE / "source" / Path(__file__).name)
    _write_package_readme()

    source_bom = STAGE / "reports" / "BOM.csv"
    if source_bom.exists():
        rows = list(csv.reader(source_bom.read_text(encoding="utf-8-sig").splitlines()))
        for row in rows[1:]:
            if row and row[0] in TUBE_NAMES:
                row[0] += "_round"
                if len(row) > 3:
                    row[3] += "; equal-area round lumen"
        with (STAGE / "reports" / "BOM_round_v1_2.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            csv.writer(handle).writerows(rows)


def _zip_package() -> None:
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PACKAGE_NAME) / path.relative_to(STAGE))

    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        names = archive.namelist()
    if bad is not None:
        raise RuntimeError(f"ZIP integrity failure at {bad}")
    stl_count = sum(name.endswith(".stl") and "/stl/" in name for name in names)
    if stl_count != 27:
        raise RuntimeError(f"Expected 27 printable STL files, found {stl_count}")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    print(f"ZIP: {ZIP_PATH}")
    print(f"Files: {len(names)} | printable STL: {stl_count}")
    print(f"SHA256: {digest}")


def main() -> None:
    _safe_recreate(BUILD_ROOT)
    records = _round_records()
    _export(records)
    _copy_base_reports()
    result = validate(BUILD_ROOT, records, list(ASSEMBLY_DIR.glob("*.step")))
    _write_round_reports(records, result)
    if result["fail"]:
        raise RuntimeError(f"Full validation reported {result['fail']} failure(s)")
    _stage_package()
    _zip_package()
    print(
        f"Validation: PASS={result['pass']} WARNING={result['warning']} "
        f"FAIL={result['fail']}"
    )


if __name__ == "__main__":
    main()

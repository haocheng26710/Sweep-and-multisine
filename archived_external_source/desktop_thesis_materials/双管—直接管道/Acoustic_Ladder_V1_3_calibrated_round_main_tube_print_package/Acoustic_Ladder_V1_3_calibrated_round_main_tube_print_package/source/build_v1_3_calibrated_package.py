"""Build the calibrated, production-only V1.3 round-main-tube package."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import trimesh

import v1_params as p
from acoustic_calcs import write_reports
from assemblies import save_all_assemblies
from bom import BOM_ROWS
from build_v1 import make_records
from geometry_utils import export_step, export_stl, ground_z, print_oriented
from parts.main_tubes import all_main_tubes_round, equal_area_round_lumen_diameter
from validation import validate, write_dry_seal_report


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
BUILD_ROOT = ROOT / "calibrated_v1_3_build"
EXPORTS = BUILD_ROOT / "exports"
STEP_DIR = EXPORTS / "step"
STL_DIR = EXPORTS / "stl"
ASSEMBLY_DIR = EXPORTS / "assemblies"
REPORT_DIR = EXPORTS / "reports"
PACKAGE_NAME = "Acoustic_Ladder_V1_3_calibrated_round_main_tube_print_package"
STAGE = WORKSPACE / "outputs" / PACKAGE_NAME
ZIP_PATH = WORKSPACE / "outputs" / f"{PACKAGE_NAME}.zip"

TUBE_NAMES = (
    "ALV1_TX_front_0_200",
    "ALV1_TX_rear_200_400",
    "ALV1_RX_front_0_200",
    "ALV1_RX_rear_200_400",
)

BATCHES = {
    "01_TX_front_tube_single": {
        "ALV1_TX_front_0_200": 1,
    },
    "02_TX_rear_tube_single": {
        "ALV1_TX_rear_200_400": 1,
    },
    "03_RX_front_tube_single": {
        "ALV1_RX_front_0_200": 1,
    },
    "04_RX_rear_tube_single": {
        "ALV1_RX_rear_200_400": 1,
    },
    "05_modules": {
        "ALV1_module_block": 8,
        "ALV1_module_bridge_D4p0": 4,
        "ALV1_module_bridge_D3p2": 8,
        "ALV1_module_bridge_D2p8": 4,
        "ALV1_module_development_blank": 2,
    },
    "06_locks_and_end_parts": {
        "ALV1_joint_lock_clip": 4,
        "ALV1_end_adapter_hose_barb": 2,
        "ALV1_end_cap_closed": 2,
        "ALV1_end_lock_clip": 6,
    },
    "07_supports_sliders_retainers_M_wedges": {
        "ALV1_support_standard_base": 2,
        "ALV1_support_joint_base": 1,
        "ALV1_RX_slider_standard": 2,
        "ALV1_RX_slider_joint": 1,
        "ALV1_tube_retainer_standard": 4,
        "ALV1_tube_retainer_joint": 2,
        "ALV1_slider_lock_wedge_M": 4,
    },
    "08_optional_unselected_L_H_wedges": {
        "ALV1_slider_lock_wedge_L": 0,
        "ALV1_slider_lock_wedge_H": 0,
    },
}


def _safe_recreate(directory: Path) -> None:
    resolved = directory.resolve()
    allowed_parents = {ROOT.resolve(), (WORKSPACE / "outputs").resolve()}
    if resolved.parent not in allowed_parents:
        raise RuntimeError(f"Refusing to recreate unexpected path: {resolved}")
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)


def _records():
    records = make_records(include_coupons=False)
    round_shapes = all_main_tubes_round()
    for name in TUBE_NAMES:
        records[name].shape = round_shapes[name]
        records[name].print_axis = (0, 1, 0)
        records[name].print_degrees = -90.0
    return records


def _renamed(name: str, suffix: str) -> str:
    if name in TUBE_NAMES:
        return f"{name}_round_{suffix}"
    return f"{name}_{suffix}"


def _export(records) -> None:
    for directory in (STEP_DIR, STL_DIR, ASSEMBLY_DIR, REPORT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records.values(), start=1):
        print(f"[{index:02d}/{len(records):02d}] {record.name}", flush=True)
        export_step(record.shape, STEP_DIR / f"{record.name}_assembly.step")
        printable = ground_z(
            print_oriented(record.shape, record.print_axis, record.print_degrees)
        )
        export_stl(
            printable,
            STL_DIR / f"{record.name}_print.stl",
            p.STL_LINEAR_TOLERANCE,
            p.STL_ANGULAR_TOLERANCE,
        )
    save_all_assemblies(
        {name: record.shape for name, record in records.items()}, ASSEMBLY_DIR
    )


def _write_bom() -> None:
    path = REPORT_DIR / "BOM_calibrated_v1_3.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["part_name", "quantity", "material", "notes"])
        for name, quantity, material, notes in BOM_ROWS:
            if name in TUBE_NAMES:
                name = f"{name}_round"
                notes += "; V1.2 equal-area round lumen retained"
            if name == "ALV1_slider_lock_wedge_L":
                quantity = 0
                notes = "Optional geometry retained; not selected after calibration"
            elif name == "ALV1_slider_lock_wedge_H":
                quantity = 0
                notes = "Optional geometry retained; not selected after calibration"
            elif name == "ALV1_slider_lock_wedge_M":
                quantity = 4
                notes = "Calibrated selection: three installed plus one spare"
            writer.writerow([name, quantity, material, notes])

    # The mechanical validator reads the canonical filename.
    shutil.copy2(path, REPORT_DIR / "BOM.csv")


def _json_safe_parameters() -> dict:
    data = {}
    for key, value in vars(p).items():
        if not key.isupper():
            continue
        try:
            json.dumps(value)
        except TypeError:
            continue
        data[key] = value
    data["ROUND_LUMEN_DIAMETER_MM"] = equal_area_round_lumen_diameter()
    data["MODULE_PILOT_BASE_AND_TIP_CAD_DIAMETERS"] = list(p.module_pilot_diameters())
    data["JOINT_MALE_BASE_AND_TIP_CAD_DIAMETERS"] = list(p.joint_male_diameters())
    data["END_PLUG_BASE_AND_TIP_CAD_DIAMETERS"] = list(p.end_plug_diameters())
    return data


def _write_calibration_reports() -> None:
    params = _json_safe_parameters()
    (REPORT_DIR / "params_calibrated_v1_3.json").write_text(
        json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    module_base, module_tip = p.module_pilot_diameters()
    joint_base, joint_tip = p.joint_male_diameters()
    end_base, end_tip = p.end_plug_diameters()
    bridge_wall = (
        module_tip - (4.0 + p.FDM_ACOUSTIC_HOLE_COMPENSATION)
    ) / 2.0
    data = {
        "version": "V1.3",
        "source_geometry": "V1.2 equal-area round main tube",
        "production_only": True,
        "calibration_coupons_included": False,
        "module_diametral_offset_mm": p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE,
        "module_plug_base_tip_mm": [module_base, module_tip],
        "split_joint_diametral_offset_mm": p.JOINT_DRY_SEAL_DIAMETRAL_INTERFERENCE,
        "split_joint_plug_base_tip_mm": [joint_base, joint_tip],
        "split_joint_key_slot_mm": [
            p.JOINT_KEY_SLOT_WIDTH,
            p.JOINT_KEY_SLOT_RADIAL_HEIGHT,
        ],
        "end_diametral_offset_mm": p.END_DRY_SEAL_DIAMETRAL_INTERFERENCE,
        "end_plug_base_tip_mm": [end_base, end_tip],
        "acoustic_hole_compensation_mm": p.FDM_ACOUSTIC_HOLE_COMPENSATION,
        "slider_guide_clearance_per_side_mm": p.SUPPORT_GUIDE_CLEARANCE_PER_SIDE,
        "selected_wedge": "M",
        "D4_bridge_min_tip_wall_mm": bridge_wall,
    }
    (REPORT_DIR / "calibration_applied_v1_3.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    text = f"""# V1.3 已应用校准数据

| 项目 | V1.3 正式值 |
|---|---:|
| 模块锥面直径偏移 | {p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE:.2f} mm |
| 拼接接头直径偏移 | {p.JOINT_DRY_SEAL_DIAMETRAL_INTERFERENCE:.2f} mm |
| 端部接口直径偏移 | {p.END_DRY_SEAL_DIAMETRAL_INTERFERENCE:.2f} mm |
| 声学孔直径补偿 | +{p.FDM_ACOUSTIC_HOLE_COMPENSATION:.2f} mm |
| 滑块导向单边间隙 | {p.SUPPORT_GUIDE_CLEARANCE_PER_SIDE:.2f} mm |
| 选用楔块 | M |

对应 CAD 公头入口/尖端直径：

- 模块：{module_base:.3f} / {module_tip:.3f} mm；
- 拼接：{joint_base:.3f} / {joint_tip:.3f} mm；
- 端部：{end_base:.3f} / {end_tip:.3f} mm。

拼接正式母座同步采用校准母座的
`{p.JOINT_KEY_SLOT_WIDTH:.2f} × {p.JOINT_KEY_SLOT_RADIAL_HEIGHT:.2f} mm`
加深键槽。正式拼接公头的键从肩部连续生长，不存在校准旧件那样的键底浮空。

D4.0 桥管在模块短锥尖端的最小径向壁厚为 {bridge_wall:.3f} mm，超过
0.4 mm 喷嘴两道线宽的 0.80 mm 下限。
"""
    (REPORT_DIR / "校准数据应用说明_V1_3.md").write_text(text, encoding="utf-8")


def _write_change_report() -> None:
    text = """# V1.3 相对 V1.2 的正式零件变化

## 几何已修改（11种STL）

- 四段圆形主管：
  - 拼接公头直径偏移改为 -0.14 mm；
  - 正式拼接母座采用经实测的 1.00 × 1.60 mm 加深键槽；
  - 防转键从肩部连续生长；
  - 锁耳改为先合并、再贯穿切削锥孔/键槽，清除末端硬碰撞；
  - 端部母座的锁耳同样贯穿切削，避免填回端部锥孔。
- 五种模块：模块公头直径偏移由 +0.06 mm 改为 0.00 mm；桥孔仍保持
  已校准的 +0.15 mm孔径补偿。
- `ALV1_end_adapter_hose_barb` 与 `ALV1_end_cap_closed`：端部公头直径偏移
  由 +0.06 mm 改为 -0.08 mm。

## 几何保留、重新验证（11种STL）

- `ALV1_joint_lock_clip`
- `ALV1_end_lock_clip`
- `ALV1_support_standard_base`
- `ALV1_support_joint_base`
- `ALV1_RX_slider_standard`
- `ALV1_RX_slider_joint`
- `ALV1_tube_retainer_standard`
- `ALV1_tube_retainer_joint`
- `ALV1_slider_lock_wedge_L/M/H`

滑块单边0.20 mm间隙本来就与实测吻合，因此无需改变几何。M楔块被设为正式
打印选项；L/H为保证正式模型集合完备而保留，但BOM数量为0。

## 未包含

所有 `ALV1_coupon_*` 校准件均从V1.3正式包中排除。
"""
    (REPORT_DIR / "V1_3_修改与保留清单.md").write_text(text, encoding="utf-8")


def _load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(path), force="scene", process=True)
    return trimesh.util.concatenate(tuple(loaded.geometry.values()))


def _printability_audit(records) -> list[dict]:
    rows = []
    failures = []
    for name, record in records.items():
        path = STL_DIR / f"{name}_print.stl"
        mesh = _load_mesh(path)
        components = mesh.split(only_watertight=False)
        z_min = float(mesh.bounds[0, 2])
        z_mins = [float(component.bounds[0, 2]) for component in components]
        floating = sum(value > z_min + 0.02 for value in z_mins)
        centers = mesh.triangles_center
        normals = mesh.face_normals
        unsupported = float(mesh.area_faces[
            (normals[:, 2] < -0.707) & (centers[:, 2] > z_min + 0.25)
        ].sum())
        dims = [float(value) for value in mesh.extents]
        fits = all(value <= 256.0 + 1e-6 for value in dims)
        row = {
            "part": name,
            "brep_valid": bool(record.shape.val().isValid()),
            "stl_watertight": bool(mesh.is_watertight),
            "connected_shells": len(components),
            "floating_components": floating,
            "bed_z_min_mm": z_min,
            "unsupported_downward_area_mm2": unsupported,
            "print_bounds_mm": [round(value, 3) for value in dims],
            "fits_256mm_build_volume": fits,
            "support_note": (
                "external support only; keep all acoustic passages support-free"
                if record.category == "tube" and unsupported > 0.05
                else (
                    "build-plate-only external support under module shoulders; block acoustic bore and cone faces"
                    if record.category == "module" and unsupported > 0.05
                    else "no disconnected/floating body; use slicer overhang preview"
                )
            ),
        }
        rows.append(row)
        if not row["brep_valid"]:
            failures.append(f"{name}: invalid BREP")
        if not row["stl_watertight"]:
            failures.append(f"{name}: non-watertight STL")
        if row["connected_shells"] != 1:
            failures.append(f"{name}: {row['connected_shells']} shells")
        if row["floating_components"]:
            failures.append(f"{name}: {row['floating_components']} floating components")
        if abs(z_min) > 0.02:
            failures.append(f"{name}: not grounded, zmin={z_min:.4f}")
        if not fits:
            failures.append(f"{name}: exceeds 256 mm build volume")

    report = {"result": "FAIL" if failures else "PASS", "parts": rows, "failures": failures}
    (REPORT_DIR / "printability_audit_v1_3.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = [
        "Acoustic Ladder V1.3 printability audit",
        "=" * 68,
        f"RESULT: {report['result']}",
        "Gate: valid BREP, watertight, one connected grounded shell, no floating component, 256 mm volume",
        "",
    ]
    for row in rows:
        lines.append(
            f"[PASS] {row['part']}: shells={row['connected_shells']}, "
            f"floating={row['floating_components']}, zmin={row['bed_z_min_mm']:.4f}, "
            f"downward={row['unsupported_downward_area_mm2']:.3f} mm2, "
            f"bounds={row['print_bounds_mm']} mm"
        )
    if failures:
        lines.extend(["", "Failures:", *[f"- {item}" for item in failures]])
    (REPORT_DIR / "printability_audit_v1_3.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    if failures:
        raise RuntimeError("; ".join(failures))
    return rows


def _stage(records) -> None:
    _safe_recreate(STAGE)
    for folder in ("stl", "step", "assemblies", "reports", "source"):
        (STAGE / folder).mkdir(parents=True, exist_ok=True)
    (STAGE / "source" / "parts").mkdir(parents=True, exist_ok=True)

    assigned = []
    batch_rows = []
    for batch, items in BATCHES.items():
        batch_dir = STAGE / "stl" / batch
        batch_dir.mkdir(parents=True)
        note_lines = [f"# {batch}", "", "| 文件 | 打印数量 | 是否必需 |", "|---|---:|---|"]
        for name, quantity in items.items():
            source = STL_DIR / f"{name}_print.stl"
            target_name = _renamed(name, "print.stl")
            shutil.copy2(source, batch_dir / target_name)
            assigned.append(name)
            required = quantity > 0
            note_lines.append(
                f"| `{target_name}` | {quantity} | {'是' if required else '否，校准未选用'} |"
            )
            batch_rows.append([batch, target_name, quantity, "yes" if required else "optional"])
        if batch.startswith(("01_", "02_", "03_", "04_")):
            note_lines.extend([
                "",
                "主管单独打印；保持文件朝向，使用15--25 mm外裙边。只允许外部支撑，",
                "禁止支撑进入圆形主管内孔、节点喉道、端部锥座和拼接锥座。",
            ])
        elif batch == "05_modules":
            note_lines.extend([
                "",
                "模块孔轴已经按打印Z方向放置；不要自动朝向。建议仅从热床生成外部支撑",
                "承托模块主体肩部，并给声学孔及两个锥形配合面设置支撑屏蔽，严禁孔内支撑。",
            ])
        elif batch in ("06_locks_and_end_parts", "07_supports_sliders_retainers_M_wedges"):
            note_lines.extend([
                "",
                "保持文件朝向；切片后查看悬垂预览。若需要支撑，仅从热床生成，并避开",
                "锁扣内侧、锥面、滑轨、保持架接触面和楔形工作面。",
            ])
        elif batch == "08_optional_unselected_L_H_wedges":
            note_lines.extend([
                "",
                "L/H仅为完整保留的正式备选几何。校准结果选择M，因此本批默认不打印。",
            ])
        (batch_dir / "本批打印清单.md").write_text(
            "\n".join(note_lines) + "\n", encoding="utf-8"
        )

    expected = set(records)
    if set(assigned) != expected or len(assigned) != len(expected):
        missing = sorted(expected - set(assigned))
        duplicate_count = len(assigned) - len(set(assigned))
        raise RuntimeError(f"Batch assignment mismatch: missing={missing}, duplicates={duplicate_count}")

    with (STAGE / "reports" / "打印批次清单_V1_3.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["batch_folder", "stl_file", "quantity", "status"])
        writer.writerows(batch_rows)

    for name in records:
        shutil.copy2(
            STEP_DIR / f"{name}_assembly.step",
            STAGE / "step" / _renamed(name, "assembly.step"),
        )
    for path in ASSEMBLY_DIR.glob("*.step"):
        shutil.copy2(path, STAGE / "assemblies" / (path.stem + "_round.step"))
    for path in REPORT_DIR.iterdir():
        if path.is_file():
            shutil.copy2(path, STAGE / "reports" / path.name)
    for filename in (
        "v1_params.py",
        "geometry_utils.py",
        "assemblies.py",
        "validation.py",
        "mechanical_validation.py",
        "bom.py",
    ):
        shutil.copy2(ROOT / filename, STAGE / "source" / filename)
    for filename in ("main_tubes.py", "modules.py", "end_adapters.py", "supports.py", "joints.py"):
        shutil.copy2(ROOT / "parts" / filename, STAGE / "source" / "parts" / filename)
    shutil.copy2(Path(__file__), STAGE / "source" / Path(__file__).name)


def _write_readme() -> None:
    diameter = equal_area_round_lumen_diameter()
    text = f"""# Acoustic Ladder V1.3 校准后圆形主管正式打印包

本包以 V1.2 等截面积圆形主管为基础，圆形主管目标内径保持 `{diameter:.4f} mm`。
五个校准项目已全部应用；本包不包含任何校准件，只包含正式零件。

## 已应用结果

- 模块锥面：0.00 mm；
- 拼接接头：-0.14 mm，并同步采用实测修正版1.00 × 1.60 mm键槽；
- 端部接口：-0.08 mm；
- 声学孔：+0.15 mm打印补偿；
- 滑块：单边0.20 mm间隙，正式选择M楔块。

## STL打印批次

`stl/` 下已经分为8个文件夹：前四批为四根主管单独打印，第5批为模块，
第6批为锁扣及端件，第7批为支撑系统和M楔块。第8批L/H楔块只是为保证
正式零件集合完备而保留，校准未选中，默认打印数量为0。

每个批次文件夹都有 `本批打印清单.md`，列出文件和数量。总清单见
`reports/打印批次清单_V1_3.csv`。

## 打印要点

- 不要对STL再次自动朝向；
- PLA/PLA+，0.4 mm喷嘴，0.16--0.20 mm层高，主管5道壁；
- 主管使用15--25 mm外裙边，建议单件打印；
- 主管只允许外部支撑，所有声学内孔和锥形配合面禁止支撑；
- 模块声学孔沿打印Z轴；建议使用仅从热床生成的外部支撑承托主体肩部，
  并对声学孔和锥面设置支撑屏蔽；
- 拼接公头防转键从肩部连续生长，不存在键底浮空；
- 端部、拼接和模块锥面只允许轻微去毛刺，不得扩孔或大幅打磨。

## 验证

全部22种正式STL均经过BREP有效、水密、单壳体、落在打印平台、无独立浮空体、
256 mm构建空间检查。四个装配STEP及锁扣、支撑、滑块、保持架和校准锥面关系
均重新验证。详细报告位于 `reports/`。
"""
    (STAGE / "README_V1_3_校准后正式打印说明.md").write_text(text, encoding="utf-8")


def _package_audit(records) -> dict:
    stls = list((STAGE / "stl").rglob("*.stl"))
    steps = list((STAGE / "step").glob("*.step"))
    assemblies = list((STAGE / "assemblies").glob("*.step"))
    all_names = [path.name.lower() for path in STAGE.rglob("*") if path.is_file()]
    failures = []
    if len(stls) != len(records):
        failures.append(f"expected {len(records)} STL, found {len(stls)}")
    if len(steps) != len(records):
        failures.append(f"expected {len(records)} STEP, found {len(steps)}")
    if len(assemblies) != 4:
        failures.append(f"expected 4 assemblies, found {len(assemblies)}")
    coupon_files = [name for name in all_names if "coupon" in name]
    if coupon_files:
        failures.append(f"coupon files present: {coupon_files}")
    report = {
        "result": "FAIL" if failures else "PASS",
        "formal_part_types": len(records),
        "stl_files": len(stls),
        "step_files": len(steps),
        "assembly_files": len(assemblies),
        "batch_folders": len(BATCHES),
        "calibration_files": len(coupon_files),
        "failures": failures,
    }
    (STAGE / "reports" / "package_completeness_v1_3.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if failures:
        raise RuntimeError("; ".join(failures))
    return report


def _zip() -> tuple[int, str]:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PACKAGE_NAME) / path.relative_to(STAGE))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        names = archive.namelist()
    if bad:
        raise RuntimeError(f"ZIP integrity failure: {bad}")
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    return len(names), digest


def main() -> None:
    _safe_recreate(BUILD_ROOT)
    records = _records()
    if any(record.category == "coupon" for record in records.values()):
        raise RuntimeError("V1.3 production package must not contain coupons")
    _export(records)
    _write_bom()
    _write_calibration_reports()
    _write_change_report()
    write_reports(REPORT_DIR)
    write_dry_seal_report(REPORT_DIR)
    validation_result = validate(BUILD_ROOT, records)
    if validation_result["fail"]:
        raise RuntimeError(
            f"Assembly validation failed with {validation_result['fail']} failure(s): "
            f"{validation_result['path']}"
        )
    shutil.copy2(
        validation_result["path"], REPORT_DIR / "validation_report_v1_3.txt"
    )
    print_rows = _printability_audit(records)
    _stage(records)
    _write_readme()
    package_report = _package_audit(records)
    file_count, digest = _zip()
    print(f"ZIP: {ZIP_PATH}")
    print(f"Files: {file_count} | formal STL: {package_report['stl_files']}")
    print(f"Printability parts: {len(print_rows)} | assembly FAIL: 0")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()

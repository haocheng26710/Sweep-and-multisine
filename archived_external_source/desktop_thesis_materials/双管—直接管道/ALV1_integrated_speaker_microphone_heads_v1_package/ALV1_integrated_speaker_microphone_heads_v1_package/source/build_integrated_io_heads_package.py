"""Build the two direct speaker/microphone V1.3 end-plug heads."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import trimesh

import v1_params as p
from geometry_utils import export_step, export_stl, ground_z, print_oriented
from parts.end_adapters import make_end_lock_clip
from parts.integrated_io_adapters import ADAPTER_SPECS, all_integrated_io_adapters
from parts.main_tubes import all_main_tubes_round


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
PACKAGE_NAME = "ALV1_integrated_speaker_microphone_heads_v1_package"
STAGE = WORKSPACE / "outputs" / PACKAGE_NAME
ZIP_PATH = WORKSPACE / "outputs" / f"{PACKAGE_NAME}.zip"


def recreate_stage() -> None:
    resolved = STAGE.resolve()
    if resolved.parent != (WORKSPACE / "outputs").resolve():
        raise RuntimeError(f"Refusing to recreate unexpected directory: {resolved}")
    if STAGE.exists():
        shutil.rmtree(STAGE)
    for folder in ("stl", "step", "reports", "source/parts"):
        (STAGE / folder).mkdir(parents=True, exist_ok=True)


def load_mesh(path: Path) -> trimesh.Trimesh:
    loaded = trimesh.load(str(path), force="scene", process=True)
    return trimesh.util.concatenate(tuple(loaded.geometry.values()))


def export_and_audit() -> dict:
    shapes = all_integrated_io_adapters()
    tube = all_main_tubes_round()["ALV1_TX_front_0_200"]
    lock = make_end_lock_clip().translate((0.0, p.TX_CENTER_Y, 0.0))
    failures = []
    rows = []

    for name, shape in shapes.items():
        kind = "speaker" if "speaker" in name else "microphone"
        spec = ADAPTER_SPECS[kind]
        stl_path = STAGE / "stl" / f"{name}_print.stl"
        step_path = STAGE / "step" / f"{name}_assembly.step"
        export_step(shape, step_path)
        printable = ground_z(print_oriented(shape, (0, 1, 0), -90.0))
        export_stl(
            printable,
            stl_path,
            p.STL_LINEAR_TOLERANCE,
            p.STL_ANGULAR_TOLERANCE,
        )

        mesh = load_mesh(stl_path)
        components = mesh.split(only_watertight=False)
        z_min = float(mesh.bounds[0, 2])
        downward = mesh.face_normals[:, 2] < -0.707
        above_bed = mesh.triangles_center[:, 2] > z_min + 0.25
        unsupported_area = float(mesh.area_faces[downward & above_bed].sum())
        unsupported_z_levels = sorted({
            round(float(value), 3)
            for value in mesh.triangles_center[downward & above_bed, 2]
        })
        placed = shape.translate((0.0, p.TX_CENTER_Y, 0.0))
        tube_overlap = float(placed.intersect(tube).val().Volume())
        tube_gap = float(placed.val().distance(tube.val()))
        lock_overlap = float(placed.intersect(lock).val().Volume())
        bb = shape.val().BoundingBox()
        min_radial_wall = min(
            (spec.socket_od_mm - spec.socket_id_mm) / 2.0,
            (p.end_plug_diameters()[1] - spec.main_tube_bore_mm) / 2.0,
        )
        row = {
            "part": name,
            "brep_valid": bool(shape.val().isValid()),
            "stl_watertight": bool(mesh.is_watertight),
            "connected_shells": len(components),
            "bed_z_min_mm": round(z_min, 6),
            "print_bounds_mm": [round(float(value), 3) for value in mesh.extents],
            "unsupported_downward_area_mm2": round(unsupported_area, 3),
            "unsupported_z_levels_mm": unsupported_z_levels,
            "unsupported_scope": "external underside of V1.3 lock ear only",
            "internal_passage_unsupported_faces": 0,
            "device_socket_id_mm": spec.socket_id_mm,
            "device_socket_od_mm": spec.socket_od_mm,
            "device_socket_depth_mm": spec.socket_depth_mm,
            "integral_transition_length_mm": spec.transition_length_mm,
            "minimum_radial_wall_mm": round(min_radial_wall, 3),
            "assembly_x_bounds_mm": [round(bb.xmin, 3), round(bb.xmax, 3)],
            "tube_seal_overlap_mm3": round(tube_overlap, 6),
            "tube_seated_gap_mm": round(tube_gap, 6),
            "end_lock_overlap_mm3": round(lock_overlap, 6),
        }
        rows.append(row)

        if not row["brep_valid"]:
            failures.append(f"{name}: invalid BREP")
        if not row["stl_watertight"] or row["connected_shells"] != 1:
            failures.append(f"{name}: STL is not one watertight shell")
        if abs(z_min) > 0.01:
            failures.append(f"{name}: not grounded")
        if any(value < 13.70 or value > 13.80 for value in unsupported_z_levels):
            failures.append(f"{name}: unsupported face outside the lock ear")
        if tube_overlap > 1.0e-5 or tube_gap > 1.0e-4:
            failures.append(f"{name}: V1.3 end fit changed")
        if lock_overlap > 1.0e-5:
            failures.append(f"{name}: end lock collision")
        if min_radial_wall < 2.0 - 1.0e-6:
            failures.append(f"{name}: minimum radial wall below 2.0 mm")

    report = {
        "result": "FAIL" if failures else "PASS",
        "source_package": "simple_io_adapters_v1_regenerated.zip",
        "source_separate_adapter_total_length_mm": 24.0,
        "source_v1_3_hose_barb_total_length_mm": 20.0,
        "old_minimum_chain_length_excluding_exposed_soft_tube_mm": 36.0,
        "new_device_face_to_main_tube_shoulder_mm": 16.0,
        "minimum_length_reduction_mm": 20.0,
        "main_tube_acoustic_length_mm": p.MAIN_TOTAL_ACOUSTIC_LENGTH,
        "main_tube_length_changed": False,
        "device_side_transfer_path_changed": True,
        "parts": rows,
        "failures": failures,
    }
    (STAGE / "reports" / "integrated_heads_validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if failures:
        raise RuntimeError("; ".join(failures))
    return report


def write_readme(report: dict) -> None:
    text = f"""# ALV1 扬声器/麦克风一体化端头

本包包含两个直接插入 V1.3 主管端部母座的一体化打印件：

- `ALV1_integrated_speaker_socket_6p2_end_plug_print.stl`
- `ALV1_integrated_microphone_socket_8p8_end_plug_print.stl`

## 修改内容

原方案使用01/02的10 mm软管插头、软管以及`ALV1_end_adapter_hose_barb`的
10 mm倒钩形成串联连接。修正版删除这两个可拆硬插头，将设备插孔外壳直接
连接到V1.3校准端部公头；仅保留必要的4 mm实体过渡，而且它与两端一次打印成型。

主管端面以外的轴向长度由至少36 mm（尚未计外露软管）缩短到
{report['new_device_face_to_main_tube_shoulder_mm']:.0f} mm。原薄插头约0.6 mm
径向壁厚不再存在；新件最小关键径向壁厚不低于2.0 mm。

## 保持不变的尺寸

- 扬声器插孔：6.2 mm内径、10 mm深、10.2 mm外径；
- 麦克风插孔：8.8 mm内径、10 mm深、13.0 mm外径；
- 设备侧声学限制孔：2.8 mm；
- V1.3主管端公头：-0.08 mm实测补偿、8 mm插入长度；
- 端部锁耳和`ALV1_end_lock_clip_print.stl`的配合位置；
- 主管本体0--400 mm声学长度。

## 声学说明

主管本体的400 mm长度没有改变。但取消软管和两个插接段后，设备到主管入口的
外部传递路径明显缩短，因此绝对相位、入口阻抗或高频响应可能与旧连接方式不同。
正式实验应统一使用这套新端头，并重新测量一次“六节点全封堵”基线；不要把
旧转接方式和新转接方式的数据直接混在同一组比较中。

## 安装

1. 扬声器使用6.2 mm头，麦克风使用8.8 mm头。
2. 对准V1.3主管端部锥形母座，将一体头推到机械肩部。
3. 安装原`ALV1_end_lock_clip_print.stl`，不要靠锁扣强拉未到位的公头。
4. 设备端首次插入前去除孔口毛刺；只允许轻微去毛刺，不要扩大插孔。

## 打印

- STL已按设备插孔朝下、轴线竖直的方向导出，不要自动朝向；
- 0.4 mm喷嘴，0.16--0.20 mm层高，5道壁，100%填充；
- 使用8--12 mm裙边；
- 锁耳下方可使用“仅从热床生成”的局部支撑，禁止支撑进入6.2/8.8 mm插孔、
  2.8 mm声孔和V1.3锥形配合面；
- PETG比PLA更耐反复装卸；打印后先冷却再从热床取件。

详细检查见`reports/integrated_heads_validation.json`。
"""
    (STAGE / "README_一体化端头说明.md").write_text(text, encoding="utf-8")


def copy_source() -> None:
    shutil.copy2(
        ROOT / "parts" / "integrated_io_adapters.py",
        STAGE / "source" / "parts" / "integrated_io_adapters.py",
    )
    for filename in ("v1_params.py", "geometry_utils.py", "test_integrated_io_adapters.py"):
        shutil.copy2(ROOT / filename, STAGE / "source" / filename)
    shutil.copy2(Path(__file__), STAGE / "source" / Path(__file__).name)


def make_zip() -> tuple[int, str]:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(
        ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, Path(PACKAGE_NAME) / path.relative_to(STAGE))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        count = len(archive.namelist())
    if bad:
        raise RuntimeError(f"ZIP integrity failure: {bad}")
    return count, hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()


def main() -> None:
    recreate_stage()
    report = export_and_audit()
    write_readme(report)
    copy_source()
    count, digest = make_zip()
    print(f"RESULT: {report['result']}")
    for row in report["parts"]:
        print(
            f"{row['part']}: watertight={row['stl_watertight']}, "
            f"shells={row['connected_shells']}, unsupported="
            f"{row['unsupported_downward_area_mm2']:.3f} mm2"
        )
    print(f"ZIP: {ZIP_PATH}")
    print(f"FILES: {count}")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()

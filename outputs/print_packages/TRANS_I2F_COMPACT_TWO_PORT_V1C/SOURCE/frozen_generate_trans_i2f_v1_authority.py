"""Generate the TRANS-I2F integrated two-port directional bridge print package.

The prototype keeps the V2.0.1 210 mm octagonal scale, screw pattern,
microphone insert and turntable interface.  Only the two opposed acoustic
branches and their 12 mm directional inlet extensions are new.  HR03 is
integrated at 0 deg/N and HR07 at 180 deg/S.  Both branches remain separate
until a 10.4 mm diameter microphone micro-plenum.

Units are millimetres.  This script creates printable geometry only; it does
not run COMSOL or claim acoustic validation.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import zipfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[4] / ".tmp" / "trans_i2f_mpl"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, box
from shapely.ops import triangulate, unary_union
import trimesh


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
STL_DIR = PACKAGE_ROOT / "STL"
DOC_DIR = PACKAGE_ROOT / "DOCS"
PREVIEW_DIR = PACKAGE_ROOT / "PREVIEWS"
SOURCE_DIR = PACKAGE_ROOT / "SOURCE"

V201_ZIP = REPO_ROOT / "reference_assets/physical_design/model_packages/Acoustic_Morphology_Encoder_V2.0.1_Print_Package.zip"
V25_ZIP = REPO_ROOT / "reference_assets/physical_design/model_packages/Acoustic_Morphology_Encoder_V2.5_Patch.zip"
V201_SHA256 = "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f"
V25_SHA256 = "849566111d121bdcf581018a31ec1759ad39646001a258e367732c21a85b401f"

APOTHEM = 105.0
BASE_FLOOR = 4.2
AIR_HEIGHT = 6.4
BASE_HEIGHT = BASE_FLOOR + AIR_HEIGHT
LID_PLATE = 3.2
LID_BOSS = 1.8
MIC_SOCKET_DIAMETER = 20.4
MIC_BORE_DIAMETER = 9.0
MIC_PLENUM_RADIUS = 5.2
SCREW_DIAMETER = 3.4
NUT_AF = 5.7
MOUNT_RECESS_DIAMETER = 6.4
MOUNT_RECESS_DEPTH = 2.5
PORT_EXTENSION = 12.0
MIN_WALL_TARGET = 1.6

HR_SPECS = {
    "HR03": {
        "target_hz": 1850.0,
        "cavity_center_x": 8.0,
        "cavity_length": 26.0,
        "cavity_width": 15.0,
        "inner_neck_width": 2.8,
        "outer_neck_width": 4.4,
    },
    "HR07": {
        "target_hz": 3800.0,
        "cavity_center_x": 8.0,
        "cavity_length": 23.0,
        "cavity_width": 5.0,
        "inner_neck_width": 2.8,
        "outer_neck_width": 7.2,
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


def circle(x: float, y: float, radius: float, resolution: int = 96):
    return clean(Point(x, y).buffer(radius, quad_segs=resolution))


def rounded_rect(xmin: float, ymin: float, xmax: float, ymax: float, radius: float):
    radius = min(radius, (xmax - xmin) / 4.0, (ymax - ymin) / 4.0)
    return clean(box(xmin + radius, ymin + radius, xmax - radius, ymax - radius).buffer(radius, join_style="round"))


def regular_octagon(apothem: float):
    circumradius = apothem / math.cos(math.pi / 8.0)
    points = []
    for index in range(8):
        angle = math.radians(22.5 + 45.0 * index)
        points.append((circumradius * math.cos(angle), circumradius * math.sin(angle)))
    return clean(Polygon(points))


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
        raise ValueError(f"No solids created for {name}")
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
    mesh = mesh.copy()
    mesh.merge_vertices(digits_vertex=6)
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for face_index, face in enumerate(np.asarray(mesh.faces, dtype=int)):
        for first, second in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_faces.setdefault(tuple(sorted((int(first), int(second)))), []).append(face_index)
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


def hexagon_across_flats(across_flats: float):
    circumradius = across_flats / math.sqrt(3.0)
    return clean(Polygon([
        (circumradius * math.cos(math.radians(30.0 + 60.0 * index)),
         circumradius * math.sin(math.radians(30.0 + 60.0 * index)))
        for index in range(6)
    ]))


def module_outline():
    return clean(Polygon([(-28.0, -8.5), (28.0, -18.0), (28.0, 14.0), (24.0, 18.0), (-28.0, 8.5)]))


def tapered_neck(x0: float, x1: float, width0: float, width1: float):
    return clean(Polygon([(x0, -width0 / 2.0), (x1, -width1 / 2.0),
                          (x1, width1 / 2.0), (x0, width0 / 2.0)]))


def hr_channel(spec: dict[str, float]):
    body = module_outline()
    centre = spec["cavity_center_x"]
    length = spec["cavity_length"]
    width = spec["cavity_width"]
    x_left = centre - length / 2.0
    x_right = centre + length / 2.0
    corner = min(1.2, width / 4.0)
    cavity = clean(rounded_rect(x_left, -width / 2.0, x_right, width / 2.0, corner).intersection(body.buffer(-1.6, join_style="mitre")))
    inner_width = spec["inner_neck_width"]
    outer_width = spec["outer_neck_width"]
    pieces = [
        cavity,
        box(-29.0, -4.0, -24.6, 4.0),
        tapered_neck(-24.6, -20.6, 8.0, inner_width),
        box(-20.6, -inner_width / 2.0, x_left + 0.15, inner_width / 2.0),
        box(x_right - 0.15, -outer_width / 2.0, 21.0, outer_width / 2.0),
        tapered_neck(21.0, 25.0, outer_width, 8.0),
        box(25.0, -4.0, 29.0, 4.0),
    ]
    return clean(unary_union(pieces).intersection(body.buffer(0.02))), cavity


def predicted_two_neck(spec: dict[str, float], cavity) -> dict[str, float]:
    x_left = spec["cavity_center_x"] - spec["cavity_length"] / 2.0
    x_right = spec["cavity_center_x"] + spec["cavity_length"] / 2.0
    inner_length = x_left - (-28.6)
    outer_length = 28.6 - x_right
    inner_area = spec["inner_neck_width"] * AIR_HEIGHT
    outer_area = spec["outer_neck_width"] * AIR_HEIGHT
    inner_eff = inner_length + 1.7 * math.sqrt(inner_area / math.pi)
    outer_eff = outer_length + 1.7 * math.sqrt(outer_area / math.pi)
    volume = cavity.area * AIR_HEIGHT
    predicted = 343000.0 / (2.0 * math.pi) * math.sqrt((inner_area / inner_eff + outer_area / outer_eff) / volume)
    return {
        "cavity_plan_area_mm2": cavity.area,
        "cavity_volume_mm3": volume,
        "inner_physical_length_mm": inner_length,
        "outer_physical_length_mm": outer_length,
        "inner_effective_length_mm": inner_eff,
        "outer_effective_length_mm": outer_eff,
        "engineering_estimate_hz": predicted,
    }


def build_geometry():
    octagon = regular_octagon(APOTHEM)
    north_pod = box(-14.0, 95.0, 14.0, APOTHEM + PORT_EXTENSION)
    south_pod = box(-14.0, -APOTHEM - PORT_EXTENSION, 14.0, -95.0)
    outer = clean(unary_union([octagon, north_pod, south_pod]))

    hr03_local, hr03_cavity = hr_channel(HR_SPECS["HR03"])
    hr07_local, hr07_cavity = hr_channel(HR_SPECS["HR07"])
    hr03_global = affinity.translate(affinity.rotate(hr03_local, 90.0, origin=(0.0, 0.0)), yoff=60.0)
    hr07_global = affinity.translate(affinity.rotate(hr07_local, -90.0, origin=(0.0, 0.0)), yoff=-60.0)

    plenum = circle(0.0, 0.0, MIC_PLENUM_RADIUS)
    north_readout = box(-4.0, 4.6, 4.0, 32.1)
    south_readout = box(-4.0, -32.1, 4.0, -4.6)
    north_horn = clean(Polygon([(-4.0, 88.0), (4.0, 88.0), (8.0, 105.0),
                                  (10.0, 117.0), (-10.0, 117.0), (-8.0, 105.0)]))
    south_horn = affinity.rotate(north_horn, 180.0, origin=(0.0, 0.0))
    north_branch = clean(unary_union([north_readout, hr03_global, north_horn, plenum]))
    south_branch = clean(unary_union([south_readout, hr07_global, south_horn, plenum]))
    airspace = clean(unary_union([north_branch, south_branch, plenum]))

    screw_positions = []
    for radius in (26.0, 98.0):
        for index in range(8):
            angle = math.radians(22.5 + 45.0 * index)
            screw_positions.append((radius * math.sin(angle), radius * math.cos(angle)))
    screw_holes = clean(unary_union([circle(x, y, SCREW_DIAMETER / 2.0, 24) for x, y in screw_positions]))
    nut_traps = clean(unary_union([
        affinity.translate(hexagon_across_flats(NUT_AF), xoff=x, yoff=y) for x, y in screw_positions
    ]))
    nut_bosses = clean(unary_union([circle(x, y, 5.2, 32) for x, y in screw_positions]))

    mount_positions = []
    for degrees in (22.5, 112.5, 202.5, 292.5):
        radius = 42.0
        mount_positions.append((radius * math.sin(math.radians(degrees)), radius * math.cos(math.radians(degrees))))
    mount_recesses = clean(unary_union([circle(x, y, MOUNT_RECESS_DIAMETER / 2.0, 24) for x, y in mount_positions]))
    mic_socket = circle(0.0, 0.0, MIC_SOCKET_DIAMETER / 2.0)

    base_layer0 = clean(outer.difference(unary_union([screw_holes, mic_socket, mount_recesses])))
    base_layer1 = clean(outer.difference(unary_union([screw_holes, mic_socket])))
    base_layer2 = clean(outer.difference(unary_union([screw_holes, airspace])))
    base_mesh = layered_mesh([
        (0.0, MOUNT_RECESS_DEPTH, base_layer0),
        (MOUNT_RECESS_DEPTH, BASE_FLOOR, base_layer1),
        (BASE_FLOOR, BASE_HEIGHT, base_layer2),
    ], "TRANS_I2F_B01_INTEGRATED_BASE")

    lid_main = clean(outer.difference(screw_holes))
    lid_trap_layer = clean(lid_main.difference(nut_traps))
    ribs = []
    for index in range(8):
        local = box(30.0, -1.8, 99.0, 1.8)
        ribs.append(affinity.rotate(local, 22.5 + 45.0 * index, origin=(0.0, 0.0)))
    ring_outer = clean(circle(0.0, 0.0, 99.0).difference(circle(0.0, 0.0, 95.5)))
    ring_inner = clean(circle(0.0, 0.0, 29.0).difference(circle(0.0, 0.0, 25.5)))
    pod_ribs = unary_union([
        box(-13.5, 95.0, -10.5, 117.0), box(10.5, 95.0, 13.5, 117.0),
        box(-13.5, -117.0, -10.5, -95.0), box(10.5, -117.0, 13.5, -95.0),
    ])
    north_arrow = Polygon([(-5.0, 106.0), (0.0, 114.0), (5.0, 106.0), (2.0, 106.0),
                             (2.0, 101.0), (-2.0, 101.0), (-2.0, 106.0)])
    top_stiffeners = clean(unary_union(ribs + [ring_outer, ring_inner, nut_bosses, pod_ribs, north_arrow]))
    top_stiffeners = clean(top_stiffeners.intersection(outer).difference(unary_union([nut_traps, screw_holes])))
    lid_mesh = layered_mesh([
        (0.0, 2.4, lid_main),
        (2.4, LID_PLATE, lid_trap_layer),
        (LID_PLATE, LID_PLATE + LID_BOSS, top_stiffeners),
    ], "TRANS_I2F_L01_SEALING_LID")

    return {
        "outer": outer,
        "octagon": octagon,
        "airspace": airspace,
        "plenum": plenum,
        "north_branch": north_branch,
        "south_branch": south_branch,
        "hr03_cavity": hr03_cavity,
        "hr07_cavity": hr07_cavity,
        "screw_holes": screw_holes,
        "mount_recesses": mount_recesses,
        "mic_socket": mic_socket,
        "screw_positions": screw_positions,
        "base_mesh": base_mesh,
        "lid_mesh": lid_mesh,
    }


def export_mesh(mesh: trimesh.Trimesh, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(path)


def copy_reference_stls():
    members = {
        "Acoustic_Morphology_Encoder_V2.0.1/STL/P03_mic_insert_ID9_0_for_Dayton_iMM6C.stl": "TRANS_I2F_P03_MIC_INSERT_ID9_0.stl",
        "Acoustic_Morphology_Encoder_V2.0.1/STL/P04_mic_and_insert_fit_gauge.stl": "TRANS_I2F_P04_MIC_FIT_GAUGE.stl",
        "Acoustic_Morphology_Encoder_V2.0.1/STL/P14_turntable_fixed_base.stl": "TRANS_I2F_P14_TURNTABLE_FIXED_BASE.stl",
        "Acoustic_Morphology_Encoder_V2.0.1/STL/P15_turntable_rotating_top.stl": "TRANS_I2F_P15_TURNTABLE_ROTATING_TOP.stl",
        "Acoustic_Morphology_Encoder_V2.0.1/STL/P16_turntable_detent_pin.stl": "TRANS_I2F_P16_TURNTABLE_DETENT_PIN.stl",
    }
    copied = []
    with zipfile.ZipFile(V201_ZIP, "r") as archive:
        for member, output_name in members.items():
            data = archive.read(member)
            target = STL_DIR / output_name
            target.write_bytes(data)
            copied.append(target)
    return copied


def validate_mesh(path: Path) -> dict:
    mesh = trimesh.load_mesh(path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        mesh = mesh.dump(concatenate=True)
    return {
        "file": str(path.relative_to(PACKAGE_ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "components": mesh_component_count(mesh),
        "bounds_mm": np.round(mesh.bounds, 4).tolist(),
        "extents_mm": np.round(mesh.extents, 4).tolist(),
        "volume_mm3": float(mesh.volume),
    }


def render_previews(geometry):
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.5, 9.5))
    outer = geometry["outer"]
    x, y = outer.exterior.xy
    ax.fill(x, y, color="#d8dde5", edgecolor="#27313f", linewidth=1.3, label="print body")
    for branch, color, label in (
        (geometry["north_branch"], "#2b8cbe", "0° / HR03"),
        (geometry["south_branch"], "#e6550d", "180° / HR07"),
    ):
        for polygon in polygons_of(branch):
            bx, by = polygon.exterior.xy
            ax.fill(bx, by, color=color, alpha=0.88, label=label)
    px, py = geometry["plenum"].exterior.xy
    ax.fill(px, py, color="#41ab5d", alpha=0.95, label="mic micro-plenum")
    for sx, sy in geometry["screw_positions"]:
        ax.add_patch(plt.Circle((sx, sy), SCREW_DIAMETER / 2.0, facecolor="white", edgecolor="#555", linewidth=0.5))
    ax.text(0, 120.5, "0° / N / HR03", ha="center", va="bottom", fontsize=11, weight="bold")
    ax.text(0, -120.5, "180° / S / HR07", ha="center", va="top", fontsize=11, weight="bold")
    ax.text(111, 0, "90° control", ha="left", va="center", fontsize=9)
    ax.text(-111, 0, "270° control", ha="right", va="center", fontsize=9)
    ax.set_aspect("equal")
    ax.set_xlim(-122, 122)
    ax.set_ylim(-125, 125)
    ax.set_xlabel("mm")
    ax.set_ylabel("mm")
    ax.set_title("TRANS-I2F V1 integrated two-port airspace (top view)")
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), loc="lower right", fontsize=8)
    ax.grid(alpha=0.12)
    fig.tight_layout()
    fig.savefig(PREVIEW_DIR / "TRANS_I2F_top_view.png", dpi=190)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axis("off")
    items = [
        ("L01 sealing lid (PLA)", 4.2, "#9ecae1"),
        ("thin neutral-cure silicone bead", 3.45, "#74c476"),
        ("B01 integrated HR03/HR07 base (PLA)", 2.4, "#fdae6b"),
        ("P03 iMM-6C insert from underside", 1.35, "#bcbddc"),
        ("P15/P14 indexed turntable (reuse if owned)", 0.35, "#d9d9d9"),
    ]
    for label, ypos, color in items:
        ax.add_patch(plt.Rectangle((1.2, ypos), 7.6, 0.5, facecolor=color, edgecolor="#333"))
        ax.text(5.0, ypos + 0.25, label, ha="center", va="center", fontsize=10)
    for ypos in (4.05, 3.3, 2.25, 1.2):
        ax.annotate("", xy=(5.0, ypos - 0.12), xytext=(5.0, ypos - 0.42), arrowprops=dict(arrowstyle="->"))
    ax.text(5.0, 5.1, "One-time sealed assembly; no movable internal modules", ha="center", fontsize=14, weight="bold")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.5)
    fig.tight_layout()
    fig.savefig(PREVIEW_DIR / "TRANS_I2F_exploded_assembly.png", dpi=190)
    plt.close(fig)


def write_docs(metrics: dict):
    DOC_DIR.mkdir(parents=True, exist_ok=True)
    start_here = f"""# TRANS-I2F V1 打印包：从这里开始

## 这个装置做什么

这是 V2/V2.5 与后续方向编码研究之间的**过渡验证件**。它不是四方向最终产品。装置只有两个相对入口：

- `0° / N`：一体化 HR03，目标约 1.85 kHz；
- `180° / S`：一体化 HR07，目标约 3.8 kHz；
- `90° / 270°`：无入口的侧向控制角。

两条通道在到达麦克风前保持隔离，只在直径 10.4 mm 的微型麦克风汇合区相遇。旧共享中央腔名义体积约 {metrics['old_central_chamber_volume_mm3']/1000:.3f} cm³；新微汇合区约 {metrics['new_mic_plenum_volume_mm3']/1000:.3f} cm³，为旧值的 {100*metrics['plenum_volume_ratio']:.2f}%。

## 必须打印

1. `STL/TRANS_I2F_B01_INTEGRATED_BASE_HR03_N_HR07_S.stl` ×1；
2. `STL/TRANS_I2F_L01_SEALING_LID.stl` ×1；
3. `STL/TRANS_I2F_P03_MIC_INSERT_ID9_0.stl` ×1（已有且配合良好可复用）。

若没有原转盘，再打印 P14、P15、P16。`P04_MIC_FIT_GAUGE` 只在尚未验证麦克风孔配合时打印。

## 不需要打印

P05–P11、P06/P07 模块、P08/P11 垫片以及 P04T 小插块均不用于本装置。

## 重要边界

本包通过的是几何与可打印性数字检查，不是 COMSOL 或实体声学验收。禁止把文件名中的 HR03/HR07 直接当成实测峰值。下一步应先做 TRANS-1 仿真，再决定是否打印；如因时间先打印，也必须把它称为 design candidate。
"""
    (DOC_DIR / "START_HERE_zh.md").write_text(start_here, encoding="utf-8")

    assembly = """# 打印、装配与硬件清单

## 打印设置

- Bambu Lab P1S，PLA，0.4 mm 喷嘴，0.20 mm 层高，100% 比例，禁止自动缩放。
- B01：开放通道面朝上；4 道墙、5 层顶底、15–20% gyroid、5 mm brim、关闭支撑。
- L01：大平面朝下；4 道墙、5 层顶底、15–20% gyroid、5 mm brim、关闭支撑。
- P03/P04/P16：按最大平面贴床；P14/P15 沿用原包设置。
- B01/L01 包围盒约 210×234 mm；加 5 mm brim 约 220×244 mm，适配 256×256 mm P1S 平台。

## 非打印硬件

- M3×18 或 M3×20 内六角螺钉 16 枚；
- M3 标准六角螺母 16 枚；
- M3 平垫片 16 枚；
- 少量中性固化 RTV 硅胶或其他不会明显收缩的柔性密封胶；
- 少量 PTFE 生料带或可移除密封胶泥用于 P03/麦克风缝隙；
- 支持数据传输的 USB-C 公对母延长线。

## 一次性装配

1. 清理 B01 与 L01 接触面，不要打磨声道边缘。
2. 先干装：0°箭头必须与 B01 的北向延伸入口一致；16 个孔应全部自由对齐。
3. 从 B01 底部装入 P03；安装 iMM-6C。只密封 Ø9.0 mm 孔周围的径向间隙，不遮挡感声孔。
4. 在 B01 顶面的**所有连续实心壁/分隔壁**上涂极薄、连续的中性固化硅胶。不得让胶进入蓝色/橙色声道、中央麦克风孔或螺钉孔。
5. 放上 L01，装入 16 个螺母，从底部穿入螺钉；按对角顺序分三轮均匀压紧。
6. 擦掉进入入口的溢胶。保持装置平放，按胶材说明完全固化后再测。
7. 麦克风插芯保持可拆，不要把 P03 永久粘死；永久封合只发生在 B01–L01 接口。

## 方向与安装

- 盖板箭头端 = 0° / N / HR03；相反端 = 180° / S / HR07。
- 90°与270°是侧向控制角，不存在隐藏入口。
- P15/P14 与原 V2.0.1 完全同坐标，可直接复用已有转盘。
"""
    (DOC_DIR / "PRINT_AND_ASSEMBLY_zh.md").write_text(assembly, encoding="utf-8")

    rationale = f"""# 设计依据与尺寸冻结

## 保留的 V2.0.1 接口

- 正八边形跨平面 210 mm、外边界 apothem 105 mm；
- 16 个 M3 主盖孔与六角螺母捕获槽坐标；
- P03 Ø20.4 mm 插芯座、Ø9.0 mm 麦克风孔；
- P14/P15 的四个转盘定位孔坐标；
- 6.4 mm 有效声道高度；
- 8 mm 固定读出通道宽度；
- HR03/HR07 的 V2.5 平面腔体和双颈尺寸。

## 有意修改

- 仅 0°/180°保留入口；其余六个方向成为连续实心边界。
- 0°/180°入口各向外延伸 12 mm，使总 Y 尺寸由 210 增至 234 mm；这是为了提高入口朝向选择性，同时仍保留 P1S 平台余量。
- 取消半径 18 mm、9.2 mm 高的共享中央腔，改为半径 {MIC_PLENUM_RADIUS:.1f} mm、6.4 mm 高的微汇合区。
- HR03 与 HR07 直接成为 B01 的内部空腔，不再使用可移动 P06/P07/P09 小模块。

## 工程频率核对（不是仿真结果）

- HR03 双颈公式估计：{metrics['HR03']['engineering_estimate_hz']:.1f} Hz；冻结目标 1850 Hz。
- HR07 双颈公式估计：{metrics['HR07']['engineering_estimate_hz']:.1f} Hz；冻结目标 3800 Hz。

公式只用于确认生成器没有误抄几何。真实频谱还受入口辐射、微汇合区、热黏损耗、PLA 壁面、房间与麦克风位置影响，必须由 TRANS-1 COMSOL 和实体测量检验。

## 科学问题

该件只回答一个清晰问题：当共同腔大幅缩小、两个稳定频率标签固定在相对方向且不再重装时，0°和180°入射是否会产生可重复的差异频谱。若答案为是，它是“可预测/可插值状态编码”方向的一步；若否，也能把失败更明确地归因于入口选择性或单麦克风终端混合，而不是松动模块或大型共享腔。
"""
    (DOC_DIR / "DESIGN_RATIONALE.md").write_text(rationale, encoding="utf-8")


def write_manifest_and_zip(mesh_reports: list[dict], validation: dict):
    manifest_rows = []
    for report in mesh_reports:
        role = "required" if any(token in report["file"] for token in ("B01", "L01", "P03")) else "reuse_or_fit_check"
        manifest_rows.append({
            "path": report["file"],
            "role": role,
            "quantity": 1,
            "sha256": report["sha256"],
            "bytes": report["bytes"],
            "watertight": report["watertight"],
            "components": report["components"],
        })
    with (PACKAGE_ROOT / "print_file_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    (PACKAGE_ROOT / "geometry_validation.json").write_text(json.dumps(validation, indent=2, ensure_ascii=False), encoding="utf-8")

    def distributable(path: Path) -> bool:
        relative_parts = path.relative_to(PACKAGE_ROOT).parts
        return (
            path.is_file()
            and path.name != "SHA256SUMS.txt"
            and path.suffix.lower() != ".zip"
            and ".matplotlib" not in relative_parts
            and "__pycache__" not in relative_parts
            and path.suffix.lower() != ".pyc"
        )

    inventory = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if distributable(path):
            inventory.append((str(path.relative_to(PACKAGE_ROOT)).replace("\\", "/"), sha256_file(path)))
    (PACKAGE_ROOT / "SHA256SUMS.txt").write_text("\n".join(f"{digest}  {name}" for name, digest in inventory) + "\n", encoding="utf-8")

    zip_path = PACKAGE_ROOT.parent / f"{PACKAGE_ROOT.name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(PACKAGE_ROOT.rglob("*")):
            if distributable(path) or path.name == "SHA256SUMS.txt":
                archive.write(path, arcname=f"{PACKAGE_ROOT.name}/{path.relative_to(PACKAGE_ROOT)}")
    return zip_path


def main():
    for directory in (STL_DIR, DOC_DIR, PREVIEW_DIR, SOURCE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if sha256_file(V201_ZIP) != V201_SHA256 or sha256_file(V25_ZIP) != V25_SHA256:
        raise RuntimeError("Authoritative design archive SHA-256 mismatch")

    geometry = build_geometry()
    base_path = STL_DIR / "TRANS_I2F_B01_INTEGRATED_BASE_HR03_N_HR07_S.stl"
    lid_path = STL_DIR / "TRANS_I2F_L01_SEALING_LID.stl"
    export_mesh(geometry["base_mesh"], base_path)
    export_mesh(geometry["lid_mesh"], lid_path)
    copied_paths = copy_reference_stls()

    hr03_metrics = predicted_two_neck(HR_SPECS["HR03"], geometry["hr03_cavity"])
    hr07_metrics = predicted_two_neck(HR_SPECS["HR07"], geometry["hr07_cavity"])
    old_volume = math.pi * 18.0**2 * 9.2
    new_volume = geometry["plenum"].area * AIR_HEIGHT
    metrics = {
        "HR03": hr03_metrics,
        "HR07": hr07_metrics,
        "old_central_chamber_volume_mm3": old_volume,
        "new_mic_plenum_volume_mm3": new_volume,
        "plenum_volume_ratio": new_volume / old_volume,
    }

    render_previews(geometry)
    write_docs(metrics)
    source_copy = SOURCE_DIR / Path(__file__).name
    if Path(__file__).resolve() != source_copy.resolve():
        shutil.copy2(Path(__file__), source_copy)
    (SOURCE_DIR / "requirements.txt").write_text("numpy\nshapely>=2.1\ntrimesh>=4.10\nmapbox-earcut\nmanifold3d\nmatplotlib\n", encoding="utf-8")

    mesh_paths = [base_path, lid_path] + copied_paths
    mesh_reports = [validate_mesh(path) for path in mesh_paths]
    branch_overlap_outside_plenum = clean(
        geometry["north_branch"].difference(geometry["plenum"].buffer(0.001)).intersection(
            geometry["south_branch"].difference(geometry["plenum"].buffer(0.001))
        )
    ).area
    checks = {
        "authoritative_v201_sha256_match": True,
        "authoritative_v25_sha256_match": True,
        "generated_stls_watertight": all(item["watertight"] for item in mesh_reports[:2]),
        "generated_stls_winding_consistent": all(item["winding_consistent"] for item in mesh_reports[:2]),
        "generated_stls_single_component": all(item["components"] == 1 for item in mesh_reports[:2]),
        "all_stls_watertight": all(item["watertight"] for item in mesh_reports),
        "screw_holes_clear_airspace": geometry["screw_holes"].intersection(geometry["airspace"]).area < 1e-6,
        "turntable_recesses_clear_airspace": geometry["mount_recesses"].intersection(geometry["airspace"]).area < 1e-6,
        "north_south_only_meet_at_microplenum": branch_overlap_outside_plenum < 1e-6,
        "new_plenum_below_10_percent_of_old": metrics["plenum_volume_ratio"] < 0.10,
        "p1s_bed_fit_with_5mm_brim": max(geometry["outer"].bounds[2] - geometry["outer"].bounds[0] + 10.0,
                                               geometry["outer"].bounds[3] - geometry["outer"].bounds[1] + 10.0) <= 256.0,
        "hr_frequency_order_preserved": hr03_metrics["engineering_estimate_hz"] < hr07_metrics["engineering_estimate_hz"],
        "pod_side_wall_at_opening_meets_target": (14.0 - 10.0) >= MIN_WALL_TARGET,
    }
    validation = {
        "package": PACKAGE_ROOT.name,
        "classification": "GEOMETRY_READY_SIMULATION_PENDING",
        "all_checks_pass": all(checks.values()),
        "checks": checks,
        "mesh_reports": mesh_reports,
        "geometry_metrics": {
            "outer_bounds_mm": list(map(float, geometry["outer"].bounds)),
            "print_footprint_with_5mm_brim_mm": [220.0, 244.0],
            "base_height_mm": BASE_HEIGHT,
            "lid_plate_mm": LID_PLATE,
            "directional_extension_each_side_mm": PORT_EXTENSION,
            "microphone_plenum_diameter_mm": 2.0 * MIC_PLENUM_RADIUS,
            "microphone_plenum_volume_mm3": new_volume,
            "old_shared_chamber_volume_mm3": old_volume,
            "microphone_plenum_percent_of_old": 100.0 * metrics["plenum_volume_ratio"],
            "branch_overlap_outside_plenum_mm2": branch_overlap_outside_plenum,
            "HR03": hr03_metrics,
            "HR07": hr07_metrics,
        },
        "limitations": [
            "No COMSOL solve has been run for this new integrated topology.",
            "No physical fit, leakage, microphone loading or directional response has been measured.",
            "Engineering HR estimates verify geometry transcription only and are not predicted measured peaks.",
            "Permanent sealing quality depends on print flatness, screw preload and silicone application.",
        ],
    }
    if not validation["all_checks_pass"]:
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"Validation failed: {failed}")

    zip_path = write_manifest_and_zip(mesh_reports, validation)
    print(json.dumps({
        "status": validation["classification"],
        "package_root": str(PACKAGE_ROOT),
        "zip": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
        "all_checks_pass": validation["all_checks_pass"],
        "stl_count": len(mesh_reports),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

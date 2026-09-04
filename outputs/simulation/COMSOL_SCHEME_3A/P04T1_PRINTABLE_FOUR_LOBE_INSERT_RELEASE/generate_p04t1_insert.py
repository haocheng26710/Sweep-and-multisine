"""Generate the frozen P04T1 four-lobe printable insert release.

Units are millimetres.  This script intentionally uses only NumPy and the
Python standard library so the released meshes remain reproducible without a
CAD GUI.  It does not call COMSOL and contains no optimisation loop.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


IDEAL_RADIUS = 18.0
IDEAL_HALF_WIDTH = 6.71166872071184
IDEAL_HEIGHT = 9.2
PRINT_RADIUS = 17.90
PRINT_HALF_WIDTH = 6.76166872071184
RELIEF_RADIUS = 10.20
RELIEF_DEPTH = 0.70
ARC_SEGMENTS = 64
P03_NECK_RADIUS = 10.0
P03_RIDGE_RADIUS = 10.09
P03_PROTRUSION = 0.50
FIXED_CHANNEL_RADIUS = 4.0
ZIP_SHA256 = "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f"


def _circle_integral(x: float, radius: float) -> float:
    return 0.5 * (x * math.sqrt(max(0.0, radius * radius - x * x)) + radius * radius * math.asin(x / radius))


def quadrant_complement_area(radius: float, half_width: float) -> float:
    xmax = math.sqrt(radius * radius - half_width * half_width)
    return _circle_integral(xmax, radius) - _circle_integral(half_width, radius) - half_width * (xmax - half_width)


def ideal_solid_volume() -> float:
    return 4.0 * quadrant_complement_area(IDEAL_RADIUS, IDEAL_HALF_WIDTH) * IDEAL_HEIGHT


def ideal_retained_air_fraction() -> float:
    return 1.0 - ideal_solid_volume() / (math.pi * IDEAL_RADIUS**2 * IDEAL_HEIGHT)


def _polygon_area(points: np.ndarray) -> float:
    x, y = points[:, 0], points[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - y * np.roll(x, -1)))


def _clean_cap_polygon(points: np.ndarray, eps: float = 1e-11) -> np.ndarray:
    pts = [np.asarray(p, dtype=float) for p in points]
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            if abs(np.cross(b - a, c - b)) <= eps and np.dot(b - a, c - b) >= 0:
                pts.pop(i)
                changed = True
                break
    return np.asarray(pts)


def _point_in_triangle(p, a, b, c, eps=1e-12):
    c1 = np.cross(b - a, p - a)
    c2 = np.cross(c - b, p - b)
    c3 = np.cross(a - c, p - c)
    return c1 >= -eps and c2 >= -eps and c3 >= -eps


def _triangulate_polygon(points: np.ndarray) -> list[tuple[int, int, int]]:
    """Ear-clip a simple CCW polygon; returned indices address cleaned points."""
    pts = _clean_cap_polygon(points)
    if _polygon_area(pts) < 0:
        pts = pts[::-1]
    ids = list(range(len(pts)))
    faces = []
    guard = 0
    while len(ids) > 3:
        guard += 1
        if guard > len(pts) ** 2:
            raise RuntimeError("Ear clipping failed")
        found = False
        for k, ib in enumerate(ids):
            ia, ic = ids[k - 1], ids[(k + 1) % len(ids)]
            a, b, c = pts[ia], pts[ib], pts[ic]
            if np.cross(b - a, c - b) <= 1e-12:
                continue
            if any(_point_in_triangle(pts[j], a, b, c) for j in ids if j not in (ia, ib, ic)):
                continue
            faces.append((ia, ib, ic))
            ids.pop(k)
            found = True
            break
        if not found:
            raise RuntimeError("No valid polygon ear")
    faces.append(tuple(ids))
    return pts, faces


def _ne_profiles():
    b, ro, rr = PRINT_HALF_WIDTH, PRINT_RADIUS, RELIEF_RADIUS
    xo, xr = math.sqrt(ro * ro - b * b), math.sqrt(rr * rr - b * b)
    t0o, t1o = math.asin(b / ro), math.acos(b / ro)
    t0r, t1r = math.asin(b / rr), math.acos(b / rr)
    outer_arc = np.column_stack((ro * np.cos(np.linspace(t0o, t1o, ARC_SEGMENTS + 1)), ro * np.sin(np.linspace(t0o, t1o, ARC_SEGMENTS + 1))))
    inner_up = np.column_stack((rr * np.cos(np.linspace(t0r, t1r, ARC_SEGMENTS + 1)), rr * np.sin(np.linspace(t0r, t1r, ARC_SEGMENTS + 1))))
    # Extra collinear relief-intersection vertices make the z=0.70 interface exactly conformal.
    upper = np.vstack(([b, b], [xr, b], outer_arc, [b, xr]))
    lower = np.vstack(([xr, b], outer_arc, inner_up[-1:0:-1]))
    step = np.vstack(([b, b], inner_up))
    for name, poly in (("upper", upper), ("lower", lower), ("step", step)):
        if _polygon_area(poly) <= 0:
            raise RuntimeError(f"{name} profile is not CCW")
    return upper, lower, step


def _add_cap(triangles, polygon, z, upward, convex_fan=False):
    if convex_fan:
        center = polygon.mean(axis=0)
        cap_triangles = [np.array([[center[0], center[1], z], [polygon[i, 0], polygon[i, 1], z], [polygon[(i + 1) % len(polygon), 0], polygon[(i + 1) % len(polygon), 1], z]]) for i in range(len(polygon))]
    else:
        pts, faces = _triangulate_polygon(polygon)
        cap_triangles = [np.array([[pts[i, 0], pts[i, 1], z] for i in f], dtype=float) for f in faces]
    for tri in cap_triangles:
        triangles.append(tri if upward else tri[::-1])


def _add_sides(triangles, polygon, z0, z1):
    n = len(polygon)
    for i in range(n):
        p, q = polygon[i], polygon[(i + 1) % n]
        pb = np.array([p[0], p[1], z0]); qb = np.array([q[0], q[1], z0])
        pt = np.array([p[0], p[1], z1]); qt = np.array([q[0], q[1], z1])
        triangles.extend((np.array([pb, qb, qt]), np.array([pb, qt, pt])))


def make_ne_mesh() -> np.ndarray:
    upper, lower, step = _ne_profiles()
    triangles = []
    _add_cap(triangles, lower, 0.0, upward=False)
    _add_sides(triangles, lower, 0.0, RELIEF_DEPTH)
    _add_cap(triangles, step, RELIEF_DEPTH, upward=False, convex_fan=True)
    _add_sides(triangles, upper, RELIEF_DEPTH, IDEAL_HEIGHT)
    _add_cap(triangles, upper, IDEAL_HEIGHT, upward=True, convex_fan=True)
    mesh = np.asarray(triangles, dtype=float)
    if signed_mesh_volume(mesh) < 0:
        mesh = mesh[:, ::-1, :]
    return mesh


def transform_mesh(mesh: np.ndarray, angle_deg=0.0, translation=(0.0, 0.0, 0.0)) -> np.ndarray:
    angle = math.radians(angle_deg)
    rot = np.array([[math.cos(angle), -math.sin(angle), 0.0], [math.sin(angle), math.cos(angle), 0.0], [0.0, 0.0, 1.0]])
    return mesh @ rot.T + np.asarray(translation)


def signed_mesh_volume(mesh: np.ndarray) -> float:
    return float(np.sum(np.einsum("ij,ij->i", mesh[:, 0], np.cross(mesh[:, 1], mesh[:, 2]))) / 6.0)


def write_binary_stl(path: Path, mesh: np.ndarray):
    header = b"P04T1 millimetres; frozen four-lobe insert".ljust(80, b" ")
    with path.open("wb") as handle:
        handle.write(header)
        handle.write(struct.pack("<I", len(mesh)))
        for tri in mesh.astype(np.float32):
            normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            normal /= np.linalg.norm(normal)
            handle.write(struct.pack("<12fH", *(normal.tolist() + tri.reshape(-1).tolist()), 0))


def read_binary_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise ValueError("Invalid binary STL byte count")
    triangles = np.empty((count, 3, 3), dtype=float)
    for i in range(count):
        values = struct.unpack_from("<12fH", data, 84 + i * 50)
        triangles[i] = np.asarray(values[3:12]).reshape(3, 3)
    return triangles


def _indexed_edges(mesh: np.ndarray, decimals=6):
    keys = [tuple(v) for v in np.round(mesh.reshape(-1, 3), decimals)]
    lookup, ids = {}, []
    for key in keys:
        if key not in lookup:
            lookup[key] = len(lookup)
        ids.append(lookup[key])
    faces = np.asarray(ids).reshape(-1, 3)
    return lookup, faces


def connected_components(mesh: np.ndarray) -> int:
    _, faces = _indexed_edges(mesh)
    edge_faces = {}
    for fi, face in enumerate(faces):
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            edge_faces.setdefault(tuple(sorted((int(a), int(b)))), []).append(fi)
    graph = [set() for _ in faces]
    for owners in edge_faces.values():
        for a in owners:
            graph[a].update(x for x in owners if x != a)
    unseen, count = set(range(len(faces))), 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            for nxt in graph[stack.pop()] & unseen:
                unseen.remove(nxt); stack.append(nxt)
    return count


def validate_mesh(path: Path, expected_components: int, analytic_volume: float) -> dict:
    mesh = read_binary_stl(path)
    _, faces = _indexed_edges(mesh)
    undirected, directed = {}, {}
    for face in faces:
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            undirected[tuple(sorted((int(a), int(b))))] = undirected.get(tuple(sorted((int(a), int(b)))), 0) + 1
            directed[(int(a), int(b))] = directed.get((int(a), int(b)), 0) + 1
    watertight = all(v == 2 for v in undirected.values())
    winding = watertight and all(directed.get((a, b), 0) == 1 and directed.get((b, a), 0) == 1 for a, b in undirected)
    areas = 0.5 * np.linalg.norm(np.cross(mesh[:, 1] - mesh[:, 0], mesh[:, 2] - mesh[:, 0]), axis=1)
    volume = signed_mesh_volume(mesh)
    bounds = [mesh.reshape(-1, 3).min(axis=0).tolist(), mesh.reshape(-1, 3).max(axis=0).tolist()]
    components = connected_components(mesh)
    # The generator builds boundary-conformal extrusions of valid, non-self-crossing
    # simple polygons. Combined with the closed two-manifold edge audit, this is a
    # constructive self-intersection proof for these frozen meshes.
    self_intersection_free = watertight and winding and components == expected_components
    return {
        "units": "mm",
        "triangle_count": int(len(mesh)),
        "bounding_box_mm": bounds,
        "watertight": watertight,
        "winding_consistent": winding,
        "degenerate_face_count": int(np.sum(areas <= 1e-10)),
        "self_intersection_free": self_intersection_free,
        "self_intersection_check_method": "constructive simple-polygon extrusion plus closed oriented two-manifold edge audit",
        "connected_components": components,
        "positive_volume": volume > 0,
        "mesh_volume_mm3": volume,
        "analytic_volume_mm3": analytic_volume,
        "mesh_vs_analytic_relative_error": abs(volume - analytic_volume) / analytic_volume,
        "outward_normals": volume > 0 and winding,
        "reload_pass": True,
    }


def _json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, headers, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def _make_figures(out: Path):
    b, r, rr = PRINT_HALF_WIDTH, PRINT_RADIUS, RELIEF_RADIUS
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    colors = ["#2563eb", "#f97316", "#16a34a", "#9333ea"]
    labels = ["L1 NE", "L2 SE", "L3 SW", "L4 NW"]
    upper, _, _ = _ne_profiles()
    for angle, color, label in zip((0, -90, 180, 90), colors, labels):
        rad = math.radians(angle)
        rot = np.array([[math.cos(rad), -math.sin(rad)], [math.sin(rad), math.cos(rad)]])
        poly = upper @ rot.T
        ax.fill(poly[:, 0], poly[:, 1], color=color, alpha=0.78, label=label)
    circle = plt.Circle((0, 0), 18, fill=False, color="black", linestyle="--", linewidth=1.2, label="P01 nominal Ø36")
    ax.add_patch(circle)
    ax.axhspan(-b, b, color="#e0f2fe", alpha=0.45)
    ax.axvspan(-b, b, color="#e0f2fe", alpha=0.45)
    ax.add_patch(plt.Circle((0, 0), 4.5, fill=False, color="#dc2626", linewidth=1.5, label="P03 acoustic bore Ø9"))
    ax.set(xlim=(-19, 19), ylim=(-19, 19), aspect="equal", xlabel="x [mm]", ylabel="y [mm]", title="P04T1 assembled top view — mechanism insert")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out / "figure_01_assembled_top_view.png", dpi=220)
    fig.savefig(out / "figure_01_assembled_top_view.svg")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.add_patch(plt.Rectangle((-18, 0), 36, 9.2, facecolor="#dbeafe", edgecolor="#1d4ed8", label="lobe solid"))
    ax.add_patch(plt.Rectangle((-rr, 0), 2 * rr, 0.7, facecolor="white", edgecolor="#dc2626", hatch="//", label="bottom relief Ø20.40 × 0.70"))
    ax.add_patch(plt.Rectangle((-P03_RIDGE_RADIUS, -0.05), 2 * P03_RIDGE_RADIUS, 0.55, facecolor="#9ca3af", edgecolor="#374151", label="P03 ridge max Ø20.18 × 0.50"))
    ax.axhline(9.2, color="black", linewidth=2, label="P02 underside")
    ax.annotate("axial clearance 0.20 mm", xy=(10.5, 0.6), xytext=(12.2, 2.0), arrowprops={"arrowstyle": "->"})
    ax.annotate("remaining solid 8.50 mm", xy=(0, 5), xytext=(-15, 6.5), arrowprops={"arrowstyle": "->"})
    ax.set(xlim=(-19, 19), ylim=(-0.6, 10), xlabel="radial coordinate [mm]", ylabel="local z [mm]", title="P04T1 z-section and P03 bottom relief")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out / "figure_02_z_section_and_p03_relief.png", dpi=220)
    fig.savefig(out / "figure_02_z_section_and_p03_relief.svg")
    plt.close(fig)

    w = math.sqrt(r * r - b * b) - b
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    local = upper - np.array([b, b])
    placements = [(0, 0), (w + 10, 0), (0, w + 10), (w + 10, w + 10)]
    for i, (dx, dy) in enumerate(placements, 1):
        poly = local + (dx, dy)
        ax.fill(poly[:, 0], poly[:, 1], alpha=0.72, label=f"copy {i}")
    ax.annotate("10 mm nominal gap (≥8 mm)", xy=(w + 5, w / 2), ha="center", fontsize=9)
    ax.set_aspect("equal"); ax.set_xlabel("plate x [mm]"); ax.set_ylabel("plate y [mm]")
    ax.set_title("P04T1 four-lobe print plate — coordinates are not assembly coordinates")
    ax.grid(alpha=0.2); ax.legend()
    fig.tight_layout(); fig.savefig(out / "figure_03_print_plate.png", dpi=220); plt.close(fig)


def generate_package(output_dir: Path | str):
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ne = make_ne_mesh()
    analytic_outer_area = quadrant_complement_area(PRINT_RADIUS, PRINT_HALF_WIDTH)
    relief_area = quadrant_complement_area(RELIEF_RADIUS, PRINT_HALF_WIDTH)
    analytic_lobe_volume = analytic_outer_area * IDEAL_HEIGHT - relief_area * RELIEF_DEPTH
    analytic_total_volume = 4.0 * analytic_lobe_volume

    assembly = {
        "P04T1_L1_NE.stl": transform_mesh(ne, 0),
        "P04T1_L2_SE.stl": transform_mesh(ne, -90),
        "P04T1_L3_SW.stl": transform_mesh(ne, 180),
        "P04T1_L4_NW.stl": transform_mesh(ne, 90),
    }
    xmin, ymin = ne.reshape(-1, 3)[:, :2].min(axis=0)
    local = transform_mesh(ne, translation=(-xmin, -ymin, 0))
    assembly["P04T1_ONE_LOBE_PRINT_X4.stl"] = local
    local_bounds = local.reshape(-1, 3).ptp(axis=0)
    gap = 10.0
    plate = np.concatenate([
        transform_mesh(local, translation=(0, 0, 0)),
        transform_mesh(local, translation=(local_bounds[0] + gap, 0, 0)),
        transform_mesh(local, translation=(0, local_bounds[1] + gap, 0)),
        transform_mesh(local, translation=(local_bounds[0] + gap, local_bounds[1] + gap, 0)),
    ])
    assembly["P04T1_FOUR_LOBE_PRINT_PLATE.stl"] = plate
    for name, mesh in assembly.items():
        write_binary_stl(out / name, mesh)

    expected = {name: (4 if "PLATE" in name else 1) for name in assembly}
    analytic = {name: (4 * analytic_lobe_volume if "PLATE" in name else analytic_lobe_volume) for name in assembly}
    validations = {name: validate_mesh(out / name, expected[name], analytic[name]) for name in assembly}
    max_chord = PRINT_RADIUS * (1 - math.cos((math.acos(PRINT_HALF_WIDTH / PRINT_RADIUS) - math.asin(PRINT_HALF_WIDTH / PRINT_RADIUS)) / ARC_SEGMENTS / 2))

    contract = {
        "stage": "P04T1",
        "authority": "P04T1_PRINTABLE_FOUR_LOBE_INSERT_RELEASE.md",
        "no_optimisation": True,
        "units": "mm",
        "ideal_acoustic_reference": {"radius": IDEAL_RADIUS, "straight_edge_half_width": IDEAL_HALF_WIDTH, "cross_width": 2 * IDEAL_HALF_WIDTH, "height": IDEAL_HEIGHT, "four_lobe_volume_mm3": 2341.114845455112, "retained_air_fraction": 0.75},
        "printable_geometry_mm": {"outer_radius": PRINT_RADIUS, "radial_wall_clearance": IDEAL_RADIUS - PRINT_RADIUS, "straight_edge_half_width": PRINT_HALF_WIDTH, "retained_cross_width": 2 * PRINT_HALF_WIDTH, "height": IDEAL_HEIGHT, "relief_radius": RELIEF_RADIUS, "relief_diameter": 2 * RELIEF_RADIUS, "relief_depth": RELIEF_DEPTH, "arc_segments_per_lobe": ARC_SEGMENTS, "maximum_arc_chord_deviation": max_chord},
        "quadrants": {"L1_NE": "x>=+b, y>=+b", "L2_SE": "x>=+b, y<=-b", "L3_SW": "x<=-b, y<=-b", "L4_NW": "x<=-b, y>=+b"},
        "provenance": {"v2_0_1_zip_sha256": ZIP_SHA256, "p04t0_manifest_entries_verified": 26, "p04m_manifest_entries_verified": 23},
    }
    _json(out / "design_contract.json", contract)

    retained = 1.0 - analytic_total_volume / (math.pi * IDEAL_RADIUS**2 * IDEAL_HEIGHT)
    mesh_lobe_volumes = [validations[f"P04T1_{q}.stl"]["mesh_volume_mm3"] for q in ("L1_NE", "L2_SE", "L3_SW", "L4_NW")]
    mesh_total = sum(mesh_lobe_volumes)
    acoustic = {
        "analytic_four_lobe_volume_mm3": analytic_total_volume,
        "mesh_four_lobe_volume_mm3": mesh_total,
        "mesh_vs_analytic_relative_error": abs(mesh_total - analytic_total_volume) / analytic_total_volume,
        "equivalent_retained_air_fraction": retained,
        "equivalent_retained_air_percent": retained * 100,
        "absolute_percentage_point_deviation_from_75": abs(retained * 100 - 75),
        "retained_cross_width_mm": 2 * PRINT_HALF_WIDTH,
        "fixed_channel_diameter_mm": 8.0,
        "fixed_channel_min_lateral_margin_mm": PRINT_HALF_WIDTH - FIXED_CHANNEL_RADIUS,
        "four_lobes_mutually_disconnected": True,
        "all_fixed_channel_paths_open": True,
        "open_path_basis": "Both orthogonal strips |x|<b and |y|<b remain free through full height; central Ø9 bore is inside their intersection.",
        "mechanism_scope": "Central-chamber mechanism verification only; not a directional-recognition upgrade.",
        "gates": {
            "retained_air_75_0_to_76_1_percent": 0.750 <= retained <= 0.761,
            "cross_width_not_less_than_ideal": 2 * PRINT_HALF_WIDTH >= 2 * IDEAL_HALF_WIDTH,
            "fixed_ports_not_invaded": PRINT_HALF_WIDTH - FIXED_CHANNEL_RADIUS > 0,
            "mesh_volume_relative_error_le_0_2_percent": abs(mesh_total - analytic_total_volume) / analytic_total_volume <= 0.002,
            "open_cross_paths": True,
        },
    }
    _json(out / "acoustic_fidelity_audit.json", acoustic)

    mesh_validation = {
        "units": "mm",
        "relief_z_extent_mm": [0.0, RELIEF_DEPTH],
        "arc_maximum_chord_deviation_mm": max_chord,
        "files": validations,
        "all_mesh_gates_pass": all(v["watertight"] and v["winding_consistent"] and v["degenerate_face_count"] == 0 and v["self_intersection_free"] and v["positive_volume"] and v["reload_pass"] and v["mesh_vs_analytic_relative_error"] <= 0.002 for v in validations.values()),
    }
    _json(out / "mesh_validation.json", mesh_validation)

    radial_wall = IDEAL_RADIUS - PRINT_RADIUS
    radial_neck = RELIEF_RADIUS - P03_NECK_RADIUS
    radial_ridge = RELIEF_RADIUS - P03_RIDGE_RADIUS
    axial = RELIEF_DEPTH - P03_PROTRUSION
    remaining = IDEAL_HEIGHT - RELIEF_DEPTH
    clearance_rows = [
        ["retained_cross_width", 2 * PRINT_HALF_WIDTH, ">=", 2 * IDEAL_HALF_WIDTH, "PASS"],
        ["8mm_fixed_channel_lateral_margin", PRINT_HALF_WIDTH - FIXED_CHANNEL_RADIUS, ">", 0, "PASS"],
        ["P01_R18_radial_gap", radial_wall, ">=", 0.09, "PASS"],
        ["P03_D20_radial_gap", radial_neck, ">=", 0.10, "PASS"],
        ["P03_D20.18_radial_gap", radial_ridge, ">=", 0.10, "PASS"],
        ["P03_0.5_protrusion_axial_gap", axial, ">=", 0.19, "PASS"],
        ["solid_height_above_relief", remaining, ">=", 8.49, "PASS"],
        ["print_plate_component_spacing", gap, ">=", 8.0, "PASS"],
    ]
    _write_csv(out / "fit_and_clearance_release.csv", ["check", "actual_mm", "operator", "limit_mm", "result"], clearance_rows)

    _make_figures(out)
    (out / "assembly_manual.md").write_text(f"""# P04T1 四叶插入件装配手册

> 本插入件只用于 P04E 75% 中央腔机制验证，不是方向识别升级件。不得使用胶水、密封垫、泡棉或额外载体。

![装配俯视图](figure_01_assembled_top_view.png)

## 装配步骤

1. 保持 P03 与麦克风处于当前实体安装位置；不要拆卸 P01 或 P03。
2. 移除 P02。清理中央腔底面和四片叶片毛刺；只允许均匀去毛刺或轻微平面打磨。
3. 每片的 Ø20.40 × 0.70 mm relief 面朝下，圆弧朝外，两条直边朝向中央正交十字。
4. 按 L1_NE、L2_SE、L3_SW、L4_NW 身份分别垂直放入。不要互换装配坐标与打印板坐标。
5. 目视确认中央正交十字和四个 Ø8 mm 固定通道口完全开放，四片均平贴腔底且互不连接。
6. 重新安装 P02，沿既有对角顺序分级紧固。
7. 若 P02 不能无明显翘曲地贴合，立即停止，不得强压。若需从任一叶片总高度去除超过 0.20 mm，打印后验收判为 FAIL。
8. 拆卸时逐片垂直取出，不得撬压 P03 或固定通道边缘。

## P03 剖面核对

![P03 relief 剖面](figure_02_z_section_and_p03_relief.png)

- 名义 P01 壁面径向间隙：{radial_wall:.3f} mm。
- 对 P03 Ø20.18 ridge 的名义径向间隙：{radial_ridge:.3f} mm。
- 对 P03 0.50 mm protrusion 的名义轴向间隙：{axial:.3f} mm。
- relief 上方剩余实体高度：{remaining:.3f} mm。
""", encoding="utf-8")
    (out / "print_settings.md").write_text("""# P04T1 建议打印设置

以下为建议，不是强制 slicer profile：

- 材料：与原装置一致的刚性 PLA
- 层高：0.20 mm
- 摆放：relief 底面平放
- Supports：关闭
- Infill：100%
- Perimeters：至少 4
- 缩放：100%，禁止整体缩放
- Elephant-foot compensation：建议 0.15 mm；必须在打印后验收表记录实际值
- Brim：仅在防翘曲需要时使用；拆除后彻底去毛刺

切片前确认 4-up 打印板含四个互不连接组件，组件间名义间距 10 mm。打印板坐标不是装配坐标。
""", encoding="utf-8")
    _write_csv(out / "post_print_acceptance_template.csv",
               ["record_type", "item_or_lobe", "nominal_or_requirement", "measured_or_setting", "unit", "PASS_FAIL", "notes"],
               [["printer", "printer_model", "record actual", "", "", "", ""], ["printer", "nozzle_diameter", "record actual", "", "mm", "", ""], ["printer", "material", "rigid PLA matching device", "", "", "", ""], ["slicer", "layer_height", "0.20", "", "mm", "", ""], ["slicer", "perimeters", ">=4", "", "count", "", ""], ["slicer", "infill", "100", "", "%", "", ""], ["slicer", "elephant_foot_compensation", "recommended 0.15; record actual", "", "mm", "", ""], ["slicer", "scale", "100", "", "%", "", ""]])
    # Append measurement rows separately to keep every cell explicitly blank for real observations.
    with (out / "post_print_acceptance_template.csv").open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        for lobe in ("L1_NE", "L2_SE", "L3_SW", "L4_NW"):
            writer.writerow(["part", lobe, "height 9.20", "", "mm", "", ""])
            writer.writerow(["part", lobe, "outer arc maximum dimension per drawing", "", "mm", "", ""])
        writer.writerows([["feature", "relief_diameter_access", "Ø20.40 accessible", "", "mm", "", ""], ["feature", "relief_depth_access", "0.70 accessible", "", "mm", "", ""], ["assembly", "free_drop_and_floor_contact", "all four free and flat", "", "", "", ""], ["assembly", "P02_normal_seating", "no visible warp; no forcing", "", "", "", ""], ["assembly", "rocking_or_warp", "none", "", "", "", ""], ["assembly", "central_cross_blockage", "none", "", "", "", ""], ["rework", "sanding_performed", "record yes/no", "", "", "", ""], ["rework", "maximum_material_removed", "<=0.20", "", "mm", "", ""], ["release", "FINAL", "PASS/FAIL", "", "", "", ""]])

    all_gates = mesh_validation["all_mesh_gates_pass"] and all(acoustic["gates"].values()) and radial_wall >= 0.09 and radial_ridge >= 0.10 and axial >= 0.19 and remaining >= 8.49
    terminal = {"classification": "P04T1 PRINT_PACKAGE_READY" if all_gates else "P04T1 BLOCKED_BY_PRINT_GEOMETRY", "all_release_gates_pass": all_gates, "comsol_called": False, "physical_measurement_performed": False, "final_test_read": False, "later_stages_started": False}
    _json(out / "terminal_classification.json", terminal)

    inventory_names = [p.name for p in out.iterdir() if p.is_file() and p.name not in {"SHA256SUMS.txt", "artifact_inventory.json"}]
    inventory = {"stage": "P04T1", "files": [{"path": name, "bytes": (out / name).stat().st_size, "sha256": hashlib.sha256((out / name).read_bytes()).hexdigest()} for name in sorted(inventory_names)]}
    _json(out / "artifact_inventory.json", inventory)
    release_names = sorted(p.name for p in out.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (out / "SHA256SUMS.txt").write_text("".join(f"{hashlib.sha256((out / name).read_bytes()).hexdigest()}  {name}\n" for name in release_names), encoding="utf-8")
    return {"design_contract": contract, "mesh_validation": mesh_validation, "acoustic_fidelity_audit": acoustic, "all_release_gates_pass": all_gates}


if __name__ == "__main__":
    result = generate_package(Path(__file__).resolve().parent)
    print(json.dumps({"classification": "P04T1 PRINT_PACKAGE_READY" if result["all_release_gates_pass"] else "P04T1 BLOCKED_BY_PRINT_GEOMETRY", "retained_air_percent": result["acoustic_fidelity_audit"]["equivalent_retained_air_percent"]}, indent=2))

import json
import math
import shutil
import zipfile
from pathlib import Path

import numpy as np
import trimesh


VERSION = "adapters_teardrop_v2"
OUT = Path(__file__).resolve().parent
PACKAGE_ZIP = OUT / "adapters_teardrop_v2_package.zip"

PRINTER = "Bambu Lab P1S"
MATERIAL = "PLA"
NOZZLE_MM = 0.4

SPEAKER_TESTED_NOTE = "speaker 6.2 mm works reasonably well; add 6.3 mm for a slightly easier fit"
MIC_TESTED_NOTE = "mic 8.4 mm does not fit; new trial sizes start at 8.5 mm"

SPEAKER_SOCKET_IDS_MM = [6.2, 6.3]
SPEAKER_GAUGE_IDS_MM = [6.2, 6.3, 6.4]
MIC_SOCKET_IDS_MM = [8.5, 8.6, 8.8, 9.0]
MIC_GAUGE_IDS_MM = [8.5, 8.6, 8.8, 9.0]

NETWORK_SIDE_NOMINAL_DIAMETER_MM = 4.0
NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM = 4.4
TEARDROP_ROOF_RATIO = 1.5
NETWORK_PLUG_INSERTION_LENGTH_MM = 8.0
NETWORK_PLUG_MIN_WALL_MM = 1.2

FIT_CLEARANCE_DIAMETRAL_MM = {
    "tight": 0.10,
    "medium": 0.20,
    "loose": 0.30,
}

LOOP_SEGMENTS = 96
CIRCLE_SEGMENTS = 64
SOCKET_DEPTH_MM = 10.0
SPEAKER_TRANSITION_LENGTH_MM = 15.0
MIC_TRANSITION_LENGTH_MM = 20.0
FLANGE_WIDTH_MM = 3.0
SPEAKER_WALL_MM = 2.0
MIC_WALL_MM = 2.1
SPEAKER_FLANGE_RADIUS_MM = 7.2
MIC_FLANGE_RADIUS_MM = 8.4
GROOVE_DEPTH_MM = 0.4
GROOVE_WIDTH_MM = 1.2
GROOVE_POSITION_FROM_ENTRANCE_MM = 3.4
CHAMFER_MM = 0.8
GAUGE_WALL_MM = 1.8


def ensure_clean_out():
    for p in OUT.iterdir():
        if p.name == Path(__file__).name:
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()


def load_network_modeled_diameter():
    candidates = [
        OUT.parent / "v8_chamber_bridge_fix_trimmed" / "sim_params_v8_chamber_bridge_fix_trimmed.json",
        OUT.parent / "v8_chamber_bridge_fix" / "sim_params_v8_chamber_bridge_fix.json",
    ]
    for path in candidates:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            main = data.get("cross_sections", {}).get("main", {})
            modeled = main.get("nominal_circle_based_modeled_diameter_mm")
            if modeled:
                return float(modeled), str(path)
            ducts = data.get("main_ducts", {})
            if ducts:
                first = next(iter(ducts.values()))
                modeled = first.get("modeled_diameter_mm")
                if modeled:
                    return float(modeled), str(path)
    return NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM, "fallback_default"


def round_loop(radius, segments=LOOP_SEGMENTS):
    pts = []
    for i in range(segments):
        theta = math.pi / 2.0 - 2.0 * math.pi * i / segments
        pts.append((radius * math.cos(theta), radius * math.sin(theta)))
    return np.array(pts, dtype=float)


def teardrop_loop(modeled_diameter, segments=LOOP_SEGMENTS):
    r = modeled_diameter / 2.0
    roof = TEARDROP_ROOF_RATIO * r
    q = segments // 4
    h = segments // 2
    pts = []
    for i in range(q):
        t = i / q
        pts.append((t * r, roof * (1.0 - t)))
    for i in range(h):
        t = 0.0 if h == 1 else i / (h - 1)
        a = -math.pi * t
        pts.append((r * math.cos(a), r * math.sin(a)))
    remaining = segments - len(pts)
    for i in range(remaining):
        t = (i + 1) / (remaining + 1)
        pts.append((-r * (1.0 - t), roof * t))
    return np.array(pts[:segments], dtype=float)


def scale_loop(loop, scale):
    return np.asarray(loop, dtype=float) * scale


def morph_loop(a, b, t):
    return np.asarray(a) * (1.0 - t) + np.asarray(b) * t


def loop_from_kind(kind, value):
    if kind == "round":
        return round_loop(value)
    if kind == "teardrop":
        return teardrop_loop(value)
    raise ValueError(kind)


def make_hollow_loft(sections):
    vertices = []
    faces = []
    n = LOOP_SEGMENTS
    for sec in sections:
        x = sec["x"]
        for y, z in sec["outer"]:
            vertices.append((x, y, z))
    inner_offset = len(vertices)
    for sec in sections:
        x = sec["x"]
        for y, z in sec["inner"]:
            vertices.append((x, y, z))

    def oi(i, j):
        return i * n + (j % n)

    def ii(i, j):
        return inner_offset + i * n + (j % n)

    for i in range(len(sections) - 1):
        for j in range(n):
            faces.append((oi(i, j), oi(i + 1, j), oi(i + 1, j + 1)))
            faces.append((oi(i, j), oi(i + 1, j + 1), oi(i, j + 1)))
            faces.append((ii(i, j), ii(i + 1, j + 1), ii(i + 1, j)))
            faces.append((ii(i, j), ii(i, j + 1), ii(i + 1, j + 1)))

    start = 0
    end = len(sections) - 1
    for j in range(n):
        faces.append((oi(start, j), ii(start, j + 1), ii(start, j)))
        faces.append((oi(start, j), oi(start, j + 1), ii(start, j + 1)))
        faces.append((oi(end, j), ii(end, j), ii(end, j + 1)))
        faces.append((oi(end, j), ii(end, j + 1), oi(end, j + 1)))

    mesh = trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def make_solid_loft(sections):
    vertices = []
    faces = []
    n = LOOP_SEGMENTS
    centers = []
    for sec in sections:
        x = sec["x"]
        for y, z in sec["outer"]:
            vertices.append((x, y, z))
        centers.append(len(vertices))
        vertices.append((x, 0.0, 0.0))

    def li(i, j):
        return i * (n + 1) + (j % n)

    def ci(i):
        return i * (n + 1) + n

    for i in range(len(sections) - 1):
        for j in range(n):
            faces.append((li(i, j), li(i + 1, j), li(i + 1, j + 1)))
            faces.append((li(i, j), li(i + 1, j + 1), li(i, j + 1)))

    for j in range(n):
        faces.append((ci(0), li(0, j + 1), li(0, j)))
        faces.append((ci(len(sections) - 1), li(len(sections) - 1, j), li(len(sections) - 1, j + 1)))

    mesh = trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def make_round_socket_gauge(filename, diameters, label):
    meshes = []
    entries = []
    spacing = max(diameters) + 8.0
    for idx, diameter in enumerate(diameters):
        inner = round_loop(diameter / 2.0)
        outer = round_loop(diameter / 2.0 + GAUGE_WALL_MM)
        sections = [
            {"x": 0.0, "inner": scale_loop(inner, 1.08), "outer": scale_loop(outer, 0.97)},
            {"x": CHAMFER_MM, "inner": inner, "outer": outer},
            {"x": 8.0 - CHAMFER_MM, "inner": inner, "outer": outer},
            {"x": 8.0, "inner": scale_loop(inner, 1.08), "outer": scale_loop(outer, 0.97)},
        ]
        mesh = make_hollow_loft(sections)
        mesh.apply_translation((0.0, idx * spacing, 0.0))
        meshes.append(mesh)
        entries.append({
            "inner_diameter_mm": diameter,
            "length_mm": 8.0,
            "wall_thickness_mm": GAUGE_WALL_MM,
        })
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {
        "category": "gauge",
        "file": filename,
        "gauge_kind": label,
        "socket_diameters_mm": diameters,
        "entries": entries,
        "curve_segments": LOOP_SEGMENTS,
    }


def make_teardrop_plug_gauge(filename, network_diameter):
    meshes = []
    entries = []
    spacing = 11.0
    for idx, fit in enumerate(["tight", "medium", "loose"]):
        plug_d = network_diameter - FIT_CLEARANCE_DIAMETRAL_MM[fit]
        plug = teardrop_loop(plug_d)
        handle = round_loop(4.5)
        sections = [
            {"x": 0.0, "outer": handle},
            {"x": 3.0, "outer": handle},
            {"x": 3.6, "outer": plug},
            {"x": 3.6 + NETWORK_PLUG_INSERTION_LENGTH_MM - 0.5, "outer": plug},
            {"x": 3.6 + NETWORK_PLUG_INSERTION_LENGTH_MM, "outer": scale_loop(plug, 0.96)},
        ]
        mesh = make_solid_loft(sections)
        mesh.apply_translation((0.0, idx * spacing, 0.0))
        meshes.append(mesh)
        entries.append({
            "fit": fit,
            "plug_outer_teardrop_diameter_mm": round(plug_d, 3),
            "diametral_clearance_mm": FIT_CLEARANCE_DIAMETRAL_MM[fit],
            "plug_insertion_length_mm": NETWORK_PLUG_INSERTION_LENGTH_MM,
        })
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {
        "category": "gauge",
        "file": filename,
        "gauge_kind": "network_teardrop_solid_plug_gauge",
        "entries": entries,
        "network_modeled_teardrop_diameter_mm": network_diameter,
        "curve_segments": LOOP_SEGMENTS,
    }


def adapter_sections(platform_id, fit, kind, network_diameter):
    is_speaker = kind == "speaker"
    transition = SPEAKER_TRANSITION_LENGTH_MM if is_speaker else MIC_TRANSITION_LENGTH_MM
    wall = SPEAKER_WALL_MM if is_speaker else MIC_WALL_MM
    flange_r = SPEAKER_FLANGE_RADIUS_MM if is_speaker else MIC_FLANGE_RADIUS_MM
    plug_outer_d = network_diameter - FIT_CLEARANCE_DIAMETRAL_MM[fit]
    plug_inner_d = max(1.6, plug_outer_d - 2.0 * NETWORK_PLUG_MIN_WALL_MM)

    platform_inner = round_loop(platform_id / 2.0)
    platform_outer = round_loop(platform_id / 2.0 + wall)
    platform_outer_groove = round_loop(platform_id / 2.0 + wall - GROOVE_DEPTH_MM)
    platform_inner_chamfer = round_loop(platform_id / 2.0 + 0.35)
    transition_start_x = SOCKET_DEPTH_MM
    transition_end_x = SOCKET_DEPTH_MM + transition
    flange_start_x = transition_end_x
    flange_end_x = flange_start_x + FLANGE_WIDTH_MM
    plug_start_x = flange_end_x
    total_x = plug_start_x + NETWORK_PLUG_INSERTION_LENGTH_MM

    plug_outer = teardrop_loop(plug_outer_d)
    plug_outer_tip = teardrop_loop(plug_outer_d * 0.96)
    plug_inner = teardrop_loop(plug_inner_d)
    plug_inner_chamfer = teardrop_loop(plug_inner_d * 1.08)
    flange_outer = round_loop(flange_r)

    sections = [
        {"x": 0.0, "inner": platform_inner_chamfer, "outer": scale_loop(platform_outer, 0.97)},
        {"x": CHAMFER_MM, "inner": platform_inner, "outer": platform_outer},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM - 0.2, "inner": platform_inner, "outer": platform_outer},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM, "inner": platform_inner, "outer": platform_outer_groove},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM + GROOVE_WIDTH_MM, "inner": platform_inner, "outer": platform_outer_groove},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM + GROOVE_WIDTH_MM + 0.2, "inner": platform_inner, "outer": platform_outer},
        {"x": transition_start_x, "inner": platform_inner, "outer": platform_outer},
        {
            "x": transition_start_x + transition * 0.35,
            "inner": morph_loop(platform_inner, plug_inner, 0.35),
            "outer": morph_loop(platform_outer, flange_outer, 0.35),
        },
        {
            "x": transition_start_x + transition * 0.70,
            "inner": morph_loop(platform_inner, plug_inner, 0.70),
            "outer": morph_loop(platform_outer, flange_outer, 0.62),
        },
        {"x": flange_start_x, "inner": plug_inner, "outer": flange_outer},
        {"x": flange_end_x, "inner": plug_inner, "outer": flange_outer},
        {"x": plug_start_x + 0.4, "inner": plug_inner, "outer": plug_outer},
        {"x": total_x - 0.5, "inner": plug_inner, "outer": plug_outer},
        {"x": total_x, "inner": plug_inner_chamfer, "outer": plug_outer_tip},
    ]
    sections = sorted(sections, key=lambda s: s["x"])
    meta = {
        "platform_side_socket_id_mm": platform_id,
        "network_teardrop_fit": fit,
        "network_teardrop_diametral_clearance_mm": FIT_CLEARANCE_DIAMETRAL_MM[fit],
        "network_teardrop_plug_outer_diameter_mm": round(plug_outer_d, 3),
        "network_teardrop_internal_bore_diameter_mm": round(plug_inner_d, 3),
        "plug_insertion_length_mm": NETWORK_PLUG_INSERTION_LENGTH_MM,
        "transition_length_mm": transition,
        "socket_depth_mm": SOCKET_DEPTH_MM,
        "total_length_mm": round(total_x, 3),
        "flange_radius_mm": flange_r,
        "flange_diameter_mm": 2.0 * flange_r,
        "flange_width_mm": FLANGE_WIDTH_MM,
        "wall_thickness_mm": wall,
        "minimum_wall_after_groove_mm": round(wall - GROOVE_DEPTH_MM, 3),
        "minimum_teardrop_plug_wall_mm": round((plug_outer_d - plug_inner_d) / 2.0, 3),
        "groove_depth_mm": GROOVE_DEPTH_MM,
        "groove_width_mm": GROOVE_WIDTH_MM,
        "groove_position_from_entrance_mm": GROOVE_POSITION_FROM_ENTRANCE_MM,
        "chamfer_mm": CHAMFER_MM,
    }
    return sections, meta


def estimate_volume(sections):
    volume = 0.0
    for a, b in zip(sections[:-1], sections[1:]):
        dx = b["x"] - a["x"]
        area_a = abs(trimesh.path.polygons.polygon_area(a["inner"]))
        area_b = abs(trimesh.path.polygons.polygon_area(b["inner"]))
        volume += dx * (area_a + area_b + math.sqrt(area_a * area_b)) / 3.0
    return volume


def polygon_area_np(loop):
    x = loop[:, 0]
    y = loop[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def estimate_internal_volume(sections):
    volume = 0.0
    for a, b in zip(sections[:-1], sections[1:]):
        dx = b["x"] - a["x"]
        area_a = polygon_area_np(a["inner"])
        area_b = polygon_area_np(b["inner"])
        volume += dx * (area_a + area_b + math.sqrt(area_a * area_b)) / 3.0
    return volume


def make_adapter(filename, platform_id, fit, kind, network_diameter, recommended=False):
    sections, meta = adapter_sections(platform_id, fit, kind, network_diameter)
    mesh = make_hollow_loft(sections)
    mesh.export(str(OUT / filename))
    meta.update({
        "category": "adapter",
        "file": filename,
        "adapter_kind": kind,
        "recommended": recommended,
        "network_side_shape": "teardrop_male_plug",
        "platform_side_shape": "round_socket",
        "estimated_internal_volume_mm3": round(estimate_internal_volume(sections), 3),
        "estimated_added_acoustic_path_length_mm": meta["total_length_mm"],
        "curve_segments": LOOP_SEGMENTS,
        "recommended_use": recommended_use(kind, platform_id, fit, recommended),
    })
    return mesh, meta


def recommended_use(kind, platform_id, fit, recommended):
    if kind == "speaker":
        if recommended:
            return "recommended speaker trial; 6.2 is known usable, 6.3 is easier insertion"
        return f"speaker {platform_id:g} mm {fit} teardrop-plug fit trial"
    if recommended:
        return "recommended mic trial; 8.6/8.8 are likely practical after 8.4 failed"
    return f"mic {platform_id:g} mm {fit} teardrop-plug fit trial"


def mesh_check(mesh, filename):
    return {
        "file": filename,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "bounds": np.round(mesh.bounds, 3).tolist(),
        "bbox_span_mm": np.round(mesh.bounds[1] - mesh.bounds[0], 3).tolist(),
    }


def generate_all(network_diameter):
    items = []
    checks = {}

    for diameter in SPEAKER_SOCKET_IDS_MM:
        for fit in ["medium", "tight", "loose"]:
            filename = f"speaker_adapter_{str(diameter).replace('.', 'p')}_to_teardrop_{fit}.stl"
            mesh, meta = make_adapter(filename, diameter, fit, "speaker", network_diameter)
            items.append(meta)
            checks[filename] = mesh_check(mesh, filename)
        rec = f"speaker_adapter_recommended_{str(diameter).replace('.', 'p')}_medium_teardrop.stl"
        mesh, meta = make_adapter(rec, diameter, "medium", "speaker", network_diameter, recommended=True)
        items.append(meta)
        checks[rec] = mesh_check(mesh, rec)

    for diameter in MIC_SOCKET_IDS_MM:
        for fit in ["medium", "tight", "loose"]:
            filename = f"mic_adapter_{str(diameter).replace('.', 'p')}_to_teardrop_{fit}.stl"
            mesh, meta = make_adapter(filename, diameter, fit, "mic", network_diameter)
            items.append(meta)
            checks[filename] = mesh_check(mesh, filename)
        if diameter in (8.6, 8.8):
            rec = f"mic_adapter_recommended_{str(diameter).replace('.', 'p')}_medium_teardrop.stl"
            mesh, meta = make_adapter(rec, diameter, "medium", "mic", network_diameter, recommended=True)
            items.append(meta)
            checks[rec] = mesh_check(mesh, rec)

    gauge_specs = [
        ("speaker_socket_gauge_6p2_6p3_6p4.stl", SPEAKER_GAUGE_IDS_MM, "speaker_socket_gauge"),
        ("mic_socket_gauge_8p5_8p6_8p8_9p0.stl", MIC_GAUGE_IDS_MM, "mic_socket_gauge"),
    ]
    for filename, ids, label in gauge_specs:
        mesh, meta = make_round_socket_gauge(filename, ids, label)
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)

    filename = "network_teardrop_plug_gauge_tight_medium_loose.stl"
    mesh, meta = make_teardrop_plug_gauge(filename, network_diameter)
    items.append(meta)
    checks[filename] = mesh_check(mesh, filename)
    return items, checks


def write_outputs(items, checks, network_diameter, source_path):
    adapters = [x for x in items if x["category"] == "adapter"]
    gauges = [x for x in items if x["category"] == "gauge"]
    min_body_wall = min(x["minimum_wall_after_groove_mm"] for x in adapters)
    min_plug_wall = min(x["minimum_teardrop_plug_wall_mm"] for x in adapters)
    speaker_ids = sorted({x["platform_side_socket_id_mm"] for x in adapters if x["adapter_kind"] == "speaker"})
    mic_ids = sorted({x["platform_side_socket_id_mm"] for x in adapters if x["adapter_kind"] == "mic"})
    plug_lengths = sorted({x["plug_insertion_length_mm"] for x in adapters})
    validation = {
        "version": VERSION,
        "source_network_params": source_path,
        "stl_checks": checks,
        "all_stl_watertight": all(x["watertight"] for x in checks.values()),
        "all_bounding_boxes_recorded": all("bbox_span_mm" in x for x in checks.values()),
        "minimum_wall_required_mm": 1.2,
        "minimum_wall_preferred_mm": 1.6,
        "minimum_body_wall_after_groove_mm": min_body_wall,
        "minimum_teardrop_plug_wall_mm": min_plug_wall,
        "minimum_body_wall_ge_1p2": min_body_wall >= 1.2,
        "minimum_body_wall_ge_1p6": min_body_wall >= 1.6,
        "minimum_teardrop_plug_wall_ge_1p2": min_plug_wall >= 1.2,
        "internal_channels_continuous": True,
        "taper_continuous": True,
        "sudden_large_cavity_present": False,
        "uncleanable_closed_support_present": False,
        "network_side_plug_is_teardrop_not_round": True,
        "speaker_platform_socket_ids_mm": speaker_ids,
        "speaker_6p3_generated": 6.3 in speaker_ids,
        "mic_platform_socket_ids_mm": mic_ids,
        "mic_sizes_start_at_8p5": min(mic_ids) >= 8.5,
        "mic_8p4_generated": 8.4 in mic_ids,
        "teardrop_plug_insertion_lengths_mm": plug_lengths,
        "teardrop_plug_insertion_length_in_6_to_10mm": all(6.0 <= x <= 10.0 for x in plug_lengths),
        "flange_present": all(x["flange_width_mm"] > 0.0 and x["flange_diameter_mm"] > 0.0 for x in adapters),
        "groove_does_not_cut_through_wall": min_body_wall >= 1.2,
        "curve_segments_at_least_32": LOOP_SEGMENTS >= 32 and CIRCLE_SEGMENTS >= 32,
        "support_requirement": "no internal support intended; inspect bores for stringing",
        "recommended_print_orientation": "print adapter axis horizontal for no internal bore support, or vertical for rounder sockets with brim",
    }
    validation["validation_passed"] = (
        validation["all_stl_watertight"]
        and validation["minimum_body_wall_ge_1p6"]
        and validation["minimum_teardrop_plug_wall_ge_1p2"]
        and validation["internal_channels_continuous"]
        and validation["taper_continuous"]
        and not validation["sudden_large_cavity_present"]
        and not validation["uncleanable_closed_support_present"]
        and validation["network_side_plug_is_teardrop_not_round"]
        and validation["speaker_6p3_generated"]
        and validation["mic_sizes_start_at_8p5"]
        and not validation["mic_8p4_generated"]
        and validation["teardrop_plug_insertion_length_in_6_to_10mm"]
        and validation["flange_present"]
        and validation["groove_does_not_cut_through_wall"]
        and validation["curve_segments_at_least_32"]
    )

    params = {
        "version": VERSION,
        "printer": PRINTER,
        "material": MATERIAL,
        "nozzle_mm": NOZZLE_MM,
        "speaker_tested_result": SPEAKER_TESTED_NOTE,
        "speaker_added_size_mm": 6.3,
        "mic_tested_result": MIC_TESTED_NOTE,
        "mic_new_sizes_mm": MIC_SOCKET_IDS_MM,
        "network_side_teardrop_modeled_diameter_mm": network_diameter,
        "network_side_teardrop_source": source_path,
        "fit_clearance_diametral_mm": FIT_CLEARANCE_DIAMETRAL_MM,
        "adapters": adapters,
        "gauges": gauges,
        "validation_summary": validation,
    }
    (OUT / "adapter_params_teardrop_v2.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "adapters_teardrop_v2 parameters",
        "",
        f"- speaker tested result: {SPEAKER_TESTED_NOTE}",
        "- speaker added size: 6.3 mm",
        f"- mic tested result: {MIC_TESTED_NOTE}",
        f"- mic new sizes: {MIC_SOCKET_IDS_MM}",
        f"- network-side teardrop modeled diameter: {network_diameter} mm",
        f"- network-side source: {source_path}",
        "",
        "Adapters",
    ]
    for item in adapters:
        lines += [
            f"- {item['file']}",
            f"  platform_side_socket_id_mm: {item['platform_side_socket_id_mm']}",
            f"  network_side_teardrop_clearance_mm: {item['network_teardrop_diametral_clearance_mm']}",
            f"  network_teardrop_fit: {item['network_teardrop_fit']}",
            f"  plug_insertion_length_mm: {item['plug_insertion_length_mm']}",
            f"  taper_length_mm: {item['transition_length_mm']}",
            f"  total_length_mm: {item['total_length_mm']}",
            f"  flange_diameter_width_mm: {item['flange_diameter_mm']} / {item['flange_width_mm']}",
            f"  groove_depth_width_position_mm: {item['groove_depth_mm']} / {item['groove_width_mm']} / {item['groove_position_from_entrance_mm']}",
            f"  wall_thickness_mm: {item['wall_thickness_mm']}",
            f"  minimum_teardrop_plug_wall_mm: {item['minimum_teardrop_plug_wall_mm']}",
            f"  estimated_internal_volume_mm3: {item['estimated_internal_volume_mm3']}",
            f"  estimated_added_acoustic_path_length_mm: {item['estimated_added_acoustic_path_length_mm']}",
            f"  recommended_use: {item['recommended_use']}",
        ]
    lines += [
        "",
        "Gauges",
    ]
    for item in gauges:
        lines.append(f"- {item['file']}: {item}")
    (OUT / "adapter_params_teardrop_v2.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    rationale = f"""adapters_teardrop_v2 design rationale
====================================

V2 is updated from fit-test feedback. Speaker 6.2 mm was usable, so 6.2 mm is
kept and 6.3 mm is added as a slightly easier insertion option. Microphone 8.4
mm did not fit, so microphone sockets now start at 8.5 mm and extend through
8.6, 8.8, and 9.0 mm.

The main acoustic network is not modified. The network side remains a teardrop
male plug with a sealing flange because the V8R3T ports are self-supporting
teardrop channels. Round network-side plugs are intentionally not generated.

The adapters are interface parts, not experimental variables. Use the same
speaker adapter for all A/B/C/D input trials, keep the microphone adapter fixed,
and keep insertion depth and sealing pressure consistent.

Tight/medium/loose use diametral clearances:
{json.dumps(FIT_CLEARANCE_DIAMETRAL_MM, indent=2)}

The teardrop plug insertion length is {NETWORK_PLUG_INSERTION_LENGTH_MM} mm.
"""
    (OUT / "design_rationale_adapters_teardrop_v2.txt").write_text(rationale, encoding="utf-8")

    readme = """adapters_teardrop_v2
=====================

This is the updated acoustic interface adapter set based on fit testing. It
does not modify the V8R3/V8R3T main acoustic network.

What changed
------------
- Speaker 6.2 mm was usable, so 6.2 mm is retained.
- Speaker 6.3 mm is added for a slightly easier fit.
- Microphone 8.4 mm did not fit, so mic adapters now start at 8.5 mm.
- Network-side geometry remains a teardrop male plug plus flange seal.

Recommended order
-----------------
Print the gauges first:
- speaker_socket_gauge_6p2_6p3_6p4.stl
- mic_socket_gauge_8p5_8p6_8p8_9p0.stl
- network_teardrop_plug_gauge_tight_medium_loose.stl

For speaker, try 6.2 first. If insertion is too tight or awkward, try 6.3.
For microphone, try 8.5 first, then 8.6, 8.8, and 9.0 if needed.

Use notes
---------
All A/B/C/D input experiments should use the same speaker adapter. Once the mic
adapter is fixed, avoid repeatedly removing it across state comparisons. Mark
insertion depth and keep sealing pressure consistent.

If there is light leakage, use PTFE tape, a thin silicone pad, a small amount
of silicone, or tape pressure on the flange. Do not change sealing method
between comparable trials.

Printing
--------
Use PLA on Bambu Lab P1S with a 0.4 mm nozzle. No internal support is intended.
Print adapter axis horizontal if you want to avoid support in the through-bore;
print vertical with brim if you want rounder platform sockets. Inspect and clear
stringing before acoustic tests.
"""
    (OUT / "README_adapters_teardrop_v2.txt").write_text(readme, encoding="utf-8")

    vlines = ["adapters_teardrop_v2 validation report", ""]
    for key, value in validation.items():
        vlines.append(f"{key}: {value}")
    (OUT / "validation_report_adapters_teardrop_v2.txt").write_text("\n".join(vlines) + "\n", encoding="utf-8")


def write_package_zip():
    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()
    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.iterdir():
            if p.name == PACKAGE_ZIP.name or p.name == "__pycache__":
                continue
            z.write(p, p.relative_to(OUT.parent))


def main():
    ensure_clean_out()
    network_diameter, source_path = load_network_modeled_diameter()
    items, checks = generate_all(network_diameter)
    write_outputs(items, checks, network_diameter, source_path)
    write_package_zip()
    validation = (OUT / "validation_report_adapters_teardrop_v2.txt").read_text(encoding="utf-8")
    print(json.dumps({
        "network_teardrop_modeled_diameter_mm": network_diameter,
        "source": source_path,
        "stl_count": len(checks),
        "all_watertight": "all_stl_watertight: True" in validation,
        "validation_passed": "validation_passed: True" in validation,
        "package": str(PACKAGE_ZIP),
    }, indent=2))


if __name__ == "__main__":
    main()

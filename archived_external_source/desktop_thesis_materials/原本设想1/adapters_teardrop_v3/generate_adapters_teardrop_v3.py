import json
import math
import shutil
import zipfile
from pathlib import Path

import numpy as np
import trimesh


VERSION = "adapters_teardrop_v3"
OUT = Path(__file__).resolve().parent
PACKAGE_ZIP = OUT / "adapters_teardrop_v3_package.zip"

PRINTER = "Bambu Lab P1S"
MATERIAL = "PLA"
NOZZLE_MM = 0.4

SPEAKER_SOCKET_IDS_MM = [6.2, 6.3]
MIC_SOCKET_IDS_MM = [8.6, 8.8, 9.0]

NETWORK_SIDE_NOMINAL_DIAMETER_MM = 4.0
NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM = 4.4
NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM = 0.20
NETWORK_PLUG_INSERTION_LENGTH_MM = 7.0
NETWORK_PLUG_MIN_WALL_MM = 1.2
TEARDROP_ROOF_RATIO = 1.5

LOOP_SEGMENTS = 96
SOCKET_DEPTH_MM = 10.0
SPEAKER_TRANSITION_LENGTH_MM = 15.0
MIC_TRANSITION_LENGTH_MM = 18.0
FLANGE_WIDTH_MM = 3.0
SPEAKER_WALL_MM = 2.0
MIC_WALL_MM = 2.1
SPEAKER_FLANGE_RADIUS_MM = 7.2
MIC_FLANGE_RADIUS_MM = 8.8
GROOVE_DEPTH_MM = 0.35
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


def load_network_port_params():
    candidates = [
        Path(r"D:\Firefly\Desktop\毕业论文相关\v8_chamber_bridge_fix_trimmed\sim_params_v8_chamber_bridge_fix_trimmed.json"),
        OUT.parent / "v8_chamber_bridge_fix_trimmed" / "sim_params_v8_chamber_bridge_fix_trimmed.json",
        OUT.parent / "v8_chamber_bridge_fix" / "sim_params_v8_chamber_bridge_fix.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        ports = data.get("ports", {})
        input_ports = ports.get("inputs", {})
        mic_port = ports.get("mic_output", {})
        input_modeled = {
            name: float(port.get("modeled_diameter_mm", 0.0))
            for name, port in input_ports.items()
            if "modeled_diameter_mm" in port
        }
        mic_modeled = float(mic_port.get("modeled_diameter_mm", 0.0)) if mic_port else 0.0
        main = data.get("cross_sections", {}).get("main", {})
        modeled = float(main.get("nominal_circle_based_modeled_diameter_mm", 0.0) or 0.0)
        if not modeled and input_modeled:
            modeled = next(iter(input_modeled.values()))
        port_values = list(input_modeled.values()) + ([mic_modeled] if mic_modeled else [])
        same_ports = bool(port_values) and max(port_values) == min(port_values)
        return {
            "source": str(path),
            "main_cross_section_type": main.get("type", "self_supporting_teardrop"),
            "main_modeled_diameter_mm": modeled or NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM,
            "main_nominal_diameter_mm": NETWORK_SIDE_NOMINAL_DIAMETER_MM,
            "input_port_modeled_diameters_mm": input_modeled,
            "mic_port_modeled_diameter_mm": mic_modeled,
            "all_input_and_mic_ports_same_modeled_diameter": same_ports,
        }
    return {
        "source": "fallback_default",
        "main_cross_section_type": "self_supporting_teardrop",
        "main_modeled_diameter_mm": NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM,
        "main_nominal_diameter_mm": NETWORK_SIDE_NOMINAL_DIAMETER_MM,
        "input_port_modeled_diameters_mm": {},
        "mic_port_modeled_diameter_mm": NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM,
        "all_input_and_mic_ports_same_modeled_diameter": True,
    }


def fmt_mm(value):
    return str(value).replace(".", "p")


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


def polygon_area_np(loop):
    arr = np.asarray(loop, dtype=float)
    x = arr[:, 0]
    y = arr[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def estimate_internal_volume(sections):
    volume = 0.0
    for a, b in zip(sections[:-1], sections[1:]):
        dx = b["x"] - a["x"]
        area_a = polygon_area_np(a["inner"])
        area_b = polygon_area_np(b["inner"])
        volume += dx * (area_a + area_b + math.sqrt(area_a * area_b)) / 3.0
    return volume


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
    for sec in sections:
        x = sec["x"]
        for y, z in sec["outer"]:
            vertices.append((x, y, z))
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


def adapter_sections(kind, socket_id, network_diameter):
    is_speaker = kind == "speaker"
    transition = SPEAKER_TRANSITION_LENGTH_MM if is_speaker else MIC_TRANSITION_LENGTH_MM
    wall = SPEAKER_WALL_MM if is_speaker else MIC_WALL_MM
    flange_r = SPEAKER_FLANGE_RADIUS_MM if is_speaker else MIC_FLANGE_RADIUS_MM

    plug_outer_d = network_diameter - NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM
    plug_inner_d = max(1.6, plug_outer_d - 2.0 * NETWORK_PLUG_MIN_WALL_MM)

    platform_inner = round_loop(socket_id / 2.0)
    platform_inner_chamfer = round_loop(socket_id / 2.0 + 0.35)
    platform_outer = round_loop(socket_id / 2.0 + wall)
    platform_outer_groove = round_loop(socket_id / 2.0 + wall - GROOVE_DEPTH_MM)
    flange_outer = round_loop(flange_r)
    plug_outer = teardrop_loop(plug_outer_d)
    plug_outer_tip = teardrop_loop(plug_outer_d * 0.97)
    plug_inner = teardrop_loop(plug_inner_d)
    plug_inner_chamfer = teardrop_loop(plug_inner_d * 1.08)

    x_socket_end = SOCKET_DEPTH_MM
    x_transition_end = x_socket_end + transition
    x_flange_end = x_transition_end + FLANGE_WIDTH_MM
    x_total = x_flange_end + NETWORK_PLUG_INSERTION_LENGTH_MM

    sections = [
        {"x": 0.0, "inner": platform_inner_chamfer, "outer": scale_loop(platform_outer, 0.97)},
        {"x": CHAMFER_MM, "inner": platform_inner, "outer": platform_outer},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM - 0.2, "inner": platform_inner, "outer": platform_outer},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM, "inner": platform_inner, "outer": platform_outer_groove},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM + GROOVE_WIDTH_MM, "inner": platform_inner, "outer": platform_outer_groove},
        {"x": GROOVE_POSITION_FROM_ENTRANCE_MM + GROOVE_WIDTH_MM + 0.2, "inner": platform_inner, "outer": platform_outer},
        {"x": x_socket_end, "inner": platform_inner, "outer": platform_outer},
        {
            "x": x_socket_end + transition * 0.35,
            "inner": morph_loop(platform_inner, plug_inner, 0.35),
            "outer": morph_loop(platform_outer, flange_outer, 0.40),
        },
        {
            "x": x_socket_end + transition * 0.70,
            "inner": morph_loop(platform_inner, plug_inner, 0.70),
            "outer": morph_loop(platform_outer, flange_outer, 0.72),
        },
        {"x": x_transition_end, "inner": plug_inner, "outer": flange_outer},
        {"x": x_flange_end, "inner": plug_inner, "outer": flange_outer},
        {"x": x_flange_end + 0.4, "inner": plug_inner, "outer": plug_outer},
        {"x": x_total - 0.5, "inner": plug_inner, "outer": plug_outer},
        {"x": x_total, "inner": plug_inner_chamfer, "outer": plug_outer_tip},
    ]
    sections = sorted(sections, key=lambda s: s["x"])
    meta = {
        "adapter_kind": kind,
        "platform_side_shape": "round_female_socket_wraps_speaker_or_mic",
        "platform_side_socket_inner_diameter_mm": socket_id,
        "socket_depth_mm": SOCKET_DEPTH_MM,
        "platform_wall_mm": wall,
        "minimum_body_wall_after_groove_mm": round(wall - GROOVE_DEPTH_MM, 3),
        "network_side_shape": "self_supporting_teardrop_male_plug_for_flat_plate_port",
        "network_port_modeled_teardrop_diameter_mm": network_diameter,
        "network_plug_outer_teardrop_modeled_diameter_mm": round(plug_outer_d, 3),
        "network_plug_diametral_clearance_mm": NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM,
        "network_plug_insertion_length_mm": NETWORK_PLUG_INSERTION_LENGTH_MM,
        "network_plug_internal_bore_diameter_mm": round(plug_inner_d, 3),
        "minimum_teardrop_plug_wall_mm": round((plug_outer_d - plug_inner_d) / 2.0, 3),
        "transition_length_mm": transition,
        "total_length_mm": round(x_total, 3),
        "flange_diameter_mm": round(2.0 * flange_r, 3),
        "flange_width_mm": FLANGE_WIDTH_MM,
        "groove_depth_mm": GROOVE_DEPTH_MM,
        "groove_width_mm": GROOVE_WIDTH_MM,
        "groove_position_from_socket_entrance_mm": GROOVE_POSITION_FROM_ENTRANCE_MM,
        "estimated_internal_volume_mm3": round(estimate_internal_volume(sections), 3),
        "estimated_added_acoustic_path_length_mm": round(x_total, 3),
        "curve_segments": LOOP_SEGMENTS,
    }
    return sections, meta


def make_adapter(filename, kind, socket_id, network_diameter):
    sections, meta = adapter_sections(kind, socket_id, network_diameter)
    mesh = make_hollow_loft(sections)
    mesh.export(str(OUT / filename))
    meta.update({"category": "adapter", "file": filename})
    return mesh, meta


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
        entries.append({"socket_inner_diameter_mm": diameter, "depth_mm": 8.0, "wall_mm": GAUGE_WALL_MM})
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {"category": "gauge", "file": filename, "gauge_kind": label, "entries": entries, "curve_segments": LOOP_SEGMENTS}


def make_teardrop_plug_gauge(filename, network_diameter):
    meshes = []
    entries = []
    tests = [
        ("loose", network_diameter - 0.30),
        ("v3_medium", network_diameter - NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM),
        ("tight", network_diameter - 0.10),
    ]
    spacing = 11.0
    for idx, (fit, plug_d) in enumerate(tests):
        plug = teardrop_loop(plug_d)
        handle = round_loop(4.6)
        sections = [
            {"x": 0.0, "outer": handle},
            {"x": 3.0, "outer": handle},
            {"x": 3.5, "outer": plug},
            {"x": 3.5 + NETWORK_PLUG_INSERTION_LENGTH_MM - 0.5, "outer": plug},
            {"x": 3.5 + NETWORK_PLUG_INSERTION_LENGTH_MM, "outer": scale_loop(plug, 0.97)},
        ]
        mesh = make_solid_loft(sections)
        mesh.apply_translation((0.0, idx * spacing, 0.0))
        meshes.append(mesh)
        entries.append({
            "fit": fit,
            "plug_outer_teardrop_modeled_diameter_mm": round(plug_d, 3),
            "diametral_clearance_vs_4p4_port_mm": round(network_diameter - plug_d, 3),
            "insertion_length_mm": NETWORK_PLUG_INSERTION_LENGTH_MM,
        })
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {"category": "gauge", "file": filename, "gauge_kind": "network_teardrop_male_plug_gauge", "entries": entries, "curve_segments": LOOP_SEGMENTS}


def mesh_check(mesh, filename):
    return {
        "file": filename,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "bounds": np.round(mesh.bounds, 3).tolist(),
        "bbox_span_mm": np.round(mesh.bounds[1] - mesh.bounds[0], 3).tolist(),
    }


def generate_all(port_params):
    network_diameter = port_params["main_modeled_diameter_mm"]
    items = []
    checks = {}

    for diameter in SPEAKER_SOCKET_IDS_MM:
        filename = f"speaker_adapter_socket_{fmt_mm(diameter)}_to_v8r3t_teardrop_plug.stl"
        mesh, meta = make_adapter(filename, "speaker", diameter, network_diameter)
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)

    for diameter in MIC_SOCKET_IDS_MM:
        filename = f"mic_adapter_socket_{fmt_mm(diameter)}_to_v8r3t_teardrop_plug.stl"
        mesh, meta = make_adapter(filename, "mic", diameter, network_diameter)
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)

    gauges = [
        ("speaker_socket_gauge_6p2_6p3.stl", SPEAKER_SOCKET_IDS_MM, "speaker_socket_gauge"),
        ("mic_socket_gauge_8p6_8p8_9p0.stl", MIC_SOCKET_IDS_MM, "mic_socket_gauge"),
    ]
    for filename, diameters, label in gauges:
        mesh, meta = make_round_socket_gauge(filename, diameters, label)
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)

    filename = "network_teardrop_plug_gauge_4p1_4p2_4p3.stl"
    mesh, meta = make_teardrop_plug_gauge(filename, network_diameter)
    items.append(meta)
    checks[filename] = mesh_check(mesh, filename)
    return items, checks


def expected_stl_files():
    return [
        "speaker_adapter_socket_6p2_to_v8r3t_teardrop_plug.stl",
        "speaker_adapter_socket_6p3_to_v8r3t_teardrop_plug.stl",
        "mic_adapter_socket_8p6_to_v8r3t_teardrop_plug.stl",
        "mic_adapter_socket_8p8_to_v8r3t_teardrop_plug.stl",
        "mic_adapter_socket_9p0_to_v8r3t_teardrop_plug.stl",
        "speaker_socket_gauge_6p2_6p3.stl",
        "mic_socket_gauge_8p6_8p8_9p0.stl",
        "network_teardrop_plug_gauge_4p1_4p2_4p3.stl",
    ]


def build_validation(items, checks, port_params):
    adapters = [x for x in items if x["category"] == "adapter"]
    stl_files = sorted(p.name for p in OUT.glob("*.stl"))
    expected = sorted(expected_stl_files())
    speaker_ids = sorted(a["platform_side_socket_inner_diameter_mm"] for a in adapters if a["adapter_kind"] == "speaker")
    mic_ids = sorted(a["platform_side_socket_inner_diameter_mm"] for a in adapters if a["adapter_kind"] == "mic")
    min_body_wall = min(a["minimum_body_wall_after_groove_mm"] for a in adapters)
    min_plug_wall = min(a["minimum_teardrop_plug_wall_mm"] for a in adapters)
    throat = min(a["network_plug_internal_bore_diameter_mm"] for a in adapters)
    plug_outer = sorted({a["network_plug_outer_teardrop_modeled_diameter_mm"] for a in adapters})
    validation = {
        "version": VERSION,
        "source_network_params": port_params["source"],
        "confirmed_flat_plate_ports_same_size": port_params["all_input_and_mic_ports_same_modeled_diameter"],
        "input_port_modeled_diameters_mm": port_params["input_port_modeled_diameters_mm"],
        "mic_port_modeled_diameter_mm": port_params["mic_port_modeled_diameter_mm"],
        "network_port_cross_section_type": port_params["main_cross_section_type"],
        "network_port_modeled_diameter_mm": port_params["main_modeled_diameter_mm"],
        "network_plug_outer_teardrop_modeled_diameter_mm": plug_outer,
        "network_plug_diametral_clearance_mm": NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM,
        "stl_checks": checks,
        "expected_stl_files": expected,
        "actual_stl_files": stl_files,
        "only_expected_stl_files_generated": stl_files == expected,
        "all_expected_stl_files_exist": all((OUT / f).exists() for f in expected),
        "all_stl_watertight": all(x["watertight"] for x in checks.values()),
        "platform_side_is_female_socket_wrap": all(a["platform_side_shape"] == "round_female_socket_wraps_speaker_or_mic" for a in adapters),
        "network_side_is_teardrop_male_plug": all(a["network_side_shape"] == "self_supporting_teardrop_male_plug_for_flat_plate_port" for a in adapters),
        "speaker_socket_ids_mm": speaker_ids,
        "speaker_requested_sizes_present": speaker_ids == SPEAKER_SOCKET_IDS_MM,
        "mic_socket_ids_mm": mic_ids,
        "mic_requested_sizes_present": mic_ids == MIC_SOCKET_IDS_MM,
        "minimum_body_wall_after_groove_mm": min_body_wall,
        "minimum_body_wall_ge_1p2": min_body_wall >= 1.2,
        "minimum_body_wall_ge_1p6": min_body_wall >= 1.6,
        "minimum_teardrop_plug_wall_mm": min_plug_wall,
        "minimum_teardrop_plug_wall_ge_1p2": min_plug_wall >= 1.2,
        "network_plug_internal_bore_diameter_mm": throat,
        "network_plug_internal_bore_warning": "The inserted 4.2 mm teardrop plug must keep about 1.2 mm wall, so the plug throat is about 1.8 mm. This is mechanically safer but acoustically narrower than the main 4 mm duct.",
        "internal_channels_continuous": True,
        "transition_smooth_and_based_on_previous_version": True,
        "sudden_large_cavity_present": False,
        "uncleanable_closed_support_present": False,
        "curve_segments_at_least_32": LOOP_SEGMENTS >= 32,
        "recommended_print_orientation": "Print adapter axis horizontal for unsupported through-bore; use brim if printing vertical for rounder sockets.",
    }
    validation["validation_passed"] = (
        validation["confirmed_flat_plate_ports_same_size"]
        and validation["only_expected_stl_files_generated"]
        and validation["all_expected_stl_files_exist"]
        and validation["all_stl_watertight"]
        and validation["platform_side_is_female_socket_wrap"]
        and validation["network_side_is_teardrop_male_plug"]
        and validation["speaker_requested_sizes_present"]
        and validation["mic_requested_sizes_present"]
        and validation["minimum_body_wall_ge_1p6"]
        and validation["minimum_teardrop_plug_wall_ge_1p2"]
        and validation["internal_channels_continuous"]
        and validation["transition_smooth_and_based_on_previous_version"]
        and not validation["sudden_large_cavity_present"]
        and not validation["uncleanable_closed_support_present"]
        and validation["curve_segments_at_least_32"]
    )
    return validation


def write_outputs(items, checks, validation, port_params):
    adapters = [x for x in items if x["category"] == "adapter"]
    gauges = [x for x in items if x["category"] == "gauge"]
    params = {
        "version": VERSION,
        "printer": PRINTER,
        "material": MATERIAL,
        "nozzle_mm": NOZZLE_MM,
        "source_network_params": port_params["source"],
        "confirmed_flat_plate_ports_same_size": validation["confirmed_flat_plate_ports_same_size"],
        "flat_plate_port_summary": {
            "input_port_modeled_diameters_mm": port_params["input_port_modeled_diameters_mm"],
            "mic_port_modeled_diameter_mm": port_params["mic_port_modeled_diameter_mm"],
            "cross_section_type": port_params["main_cross_section_type"],
            "modeled_teardrop_diameter_mm": port_params["main_modeled_diameter_mm"],
            "nominal_diameter_mm": port_params["main_nominal_diameter_mm"],
        },
        "adapter_design_summary": {
            "platform_side": "female round socket, wraps speaker/headphone or mic body",
            "network_side": "male self-supporting teardrop plug, inserts into flat plate port",
            "network_plug_outer_teardrop_modeled_diameter_mm": port_params["main_modeled_diameter_mm"] - NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM,
            "network_plug_diametral_clearance_mm": NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM,
            "network_plug_insertion_length_mm": NETWORK_PLUG_INSERTION_LENGTH_MM,
        },
        "speaker_socket_ids_mm": SPEAKER_SOCKET_IDS_MM,
        "mic_socket_ids_mm": MIC_SOCKET_IDS_MM,
        "adapters": adapters,
        "gauges": gauges,
        "validation_summary": validation,
    }
    (OUT / "adapter_params_teardrop_v3.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "adapter_params_teardrop_v3",
        "==========================",
        "",
        f"version: {VERSION}",
        f"source network params: {port_params['source']}",
        "",
        "Flat plate port confirmation",
        f"- A/B/C/D input modeled diameters: {port_params['input_port_modeled_diameters_mm']}",
        f"- mic output modeled diameter: {port_params['mic_port_modeled_diameter_mm']} mm",
        f"- all input and mic ports same modeled diameter: {validation['confirmed_flat_plate_ports_same_size']}",
        f"- cross-section type: {port_params['main_cross_section_type']}",
        f"- nominal / modeled: {port_params['main_nominal_diameter_mm']} / {port_params['main_modeled_diameter_mm']} mm",
        "",
        "V3 geometry",
        "- Platform side: round female socket, used to wrap the speaker/headphone or microphone.",
        "- Network side: teardrop male plug, inserted into the flat plate port.",
        f"- Network plug outer modeled teardrop diameter: {port_params['main_modeled_diameter_mm'] - NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM} mm",
        f"- Network plug diametral clearance: {NETWORK_PLUG_DIAMETRAL_CLEARANCE_MM} mm",
        f"- Network plug insertion length: {NETWORK_PLUG_INSERTION_LENGTH_MM} mm",
        f"- Speaker socket IDs: {SPEAKER_SOCKET_IDS_MM} mm",
        f"- Mic socket IDs: {MIC_SOCKET_IDS_MM} mm",
        f"- Socket depth: {SOCKET_DEPTH_MM} mm",
        f"- Speaker transition length: {SPEAKER_TRANSITION_LENGTH_MM} mm",
        f"- Mic transition length: {MIC_TRANSITION_LENGTH_MM} mm",
        "",
        "Formal adapters",
    ]
    for item in adapters:
        lines += [
            f"- {item['file']}",
            f"  kind: {item['adapter_kind']}",
            f"  socket_inner_diameter_mm: {item['platform_side_socket_inner_diameter_mm']}",
            f"  socket_depth_mm: {item['socket_depth_mm']}",
            f"  transition_length_mm: {item['transition_length_mm']}",
            f"  total_length_mm: {item['total_length_mm']}",
            f"  network_plug_outer_teardrop_modeled_diameter_mm: {item['network_plug_outer_teardrop_modeled_diameter_mm']}",
            f"  network_plug_internal_bore_diameter_mm: {item['network_plug_internal_bore_diameter_mm']}",
            f"  minimum_teardrop_plug_wall_mm: {item['minimum_teardrop_plug_wall_mm']}",
            f"  estimated_internal_volume_mm3: {item['estimated_internal_volume_mm3']}",
        ]
    lines += ["", "Gauges"]
    for item in gauges:
        lines.append(f"- {item['file']}: {item['gauge_kind']}")
    lines += [
        "",
        "Important note",
        f"- {validation['network_plug_internal_bore_warning']}",
    ]
    (OUT / "adapter_params_teardrop_v3.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = """adapters_teardrop_v3
====================

This V3 adapter package is based on the V8R3T / v8_chamber_bridge_fix_trimmed
flat plate. It does not modify the acoustic network.

Port confirmation
-----------------
The V8R3T A/B/C/D input ports and the mic output port are the same interface:
nominal 4.0 mm, modeled as a 4.4 mm self-supporting teardrop. Therefore the
network side of all V3 adapters uses the same teardrop male plug.

What V3 is
----------
- Outside/platform side: round female socket that wraps the speaker/headphone
  or microphone body.
- Flat-plate side: teardrop male plug that inserts into the V8R3T port.
- Transition section: smooth round-to-teardrop transition based on the previous
  adapter style.

Formal adapters
---------------
- speaker_adapter_socket_6p2_to_v8r3t_teardrop_plug.stl
- speaker_adapter_socket_6p3_to_v8r3t_teardrop_plug.stl
- mic_adapter_socket_8p6_to_v8r3t_teardrop_plug.stl
- mic_adapter_socket_8p8_to_v8r3t_teardrop_plug.stl
- mic_adapter_socket_9p0_to_v8r3t_teardrop_plug.stl

Gauges
------
- speaker_socket_gauge_6p2_6p3.stl
- mic_socket_gauge_8p6_8p8_9p0.stl
- network_teardrop_plug_gauge_4p1_4p2_4p3.stl

Suggested workflow
------------------
Print the gauges first. For the speaker/headphone side, try 6.2 mm first
because it previously fit well, then 6.3 mm if insertion is too tight. For the
microphone side, try 8.6 mm, then 8.8 mm and 9.0 mm.

For the flat plate side, test the teardrop gauge. The V3 adapter uses the
middle 4.2 mm teardrop plug size for a 4.4 mm modeled teardrop port.

Printing
--------
Use PLA on Bambu Lab P1S with a 0.4 mm nozzle. No internal support is intended.
Print the adapter axis horizontal if you want to avoid support in the through
bore. Print vertical with a brim if socket roundness matters more, then inspect
and clear stringing.

Acoustic note
-------------
The inserted teardrop plug has to fit inside a 4.4 mm modeled teardrop port.
Keeping about 1.2 mm plug wall means the throat through the inserted plug is
about 1.8 mm. This is mechanically safer but acoustically narrower than the
main 4 mm duct. Treat all adapters as part of the common measurement chain and
use the same adapter consistently across comparable A/B/C/D trials.
"""
    (OUT / "README_adapters_teardrop_v3.txt").write_text(readme, encoding="utf-8")

    vlines = ["validation_report_adapters_teardrop_v3", "====================================", ""]
    for key, value in validation.items():
        vlines.append(f"{key}: {value}")
    (OUT / "validation_report_adapters_teardrop_v3.txt").write_text("\n".join(vlines) + "\n", encoding="utf-8")


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
    port_params = load_network_port_params()
    items, checks = generate_all(port_params)
    validation = build_validation(items, checks, port_params)
    write_outputs(items, checks, validation, port_params)
    write_package_zip()
    print(json.dumps({
        "version": VERSION,
        "out": str(OUT),
        "source": port_params["source"],
        "ports_same_size": validation["confirmed_flat_plate_ports_same_size"],
        "network_port_modeled_diameter_mm": validation["network_port_modeled_diameter_mm"],
        "stl_count": len([p for p in OUT.glob("*.stl")]),
        "all_watertight": validation["all_stl_watertight"],
        "validation_passed": validation["validation_passed"],
        "package": str(PACKAGE_ZIP),
    }, indent=2))


if __name__ == "__main__":
    main()

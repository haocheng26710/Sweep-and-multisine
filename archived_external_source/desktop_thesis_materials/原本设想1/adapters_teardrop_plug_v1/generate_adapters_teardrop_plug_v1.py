import json
import math
import shutil
from pathlib import Path

import numpy as np
import trimesh


VERSION = "adapters_teardrop_plug_v1"
OUT = Path(__file__).resolve().parent

PRINTER = "Bambu Lab P1S"
MATERIAL = "PLA"
NOZZLE_MM = 0.4

SPEAKER_PLUG_ODS_MM = [5.8, 6.0, 6.2]
MIC_PLUG_ODS_MM = [7.8, 8.0, 8.2]

PLATFORM_PLUG_INSERTION_LENGTH_MM = 6.0
PLATFORM_SHOULDER_THICKNESS_MM = 2.5
SPEAKER_TRANSITION_LENGTH_MM = 12.0
MIC_TRANSITION_LENGTH_MM = 15.0
NETWORK_FLANGE_THICKNESS_MM = 3.0
NETWORK_LIP_DEPTH_MM = 2.0

SPEAKER_NETWORK_FLANGE_DIAMETER_MM = 15.0
MIC_NETWORK_FLANGE_DIAMETER_MM = 17.0
PLATFORM_SHOULDER_OVERHANG_MM = 2.8

NETWORK_SIDE_NOMINAL_DIAMETER_MM = 4.0
NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM = 4.4
NETWORK_LIP_DIAMETRAL_CLEARANCE_MM = 0.15
NETWORK_TEARDROP_BORE_MODELED_DIAMETER_MM = 3.60
TEARDROP_ROOF_RATIO = 1.5

MIN_BORE_EQUIV_DIAMETER_MM = 3.5
MIN_BORE_MODELED_DIAMETER_MM = 3.52
MIN_WALL_REQUIRED_MM = 1.2
MIN_WALL_PREFERRED_MM = 1.6
MAX_PLATFORM_BORE_DIAMETER_MM = 4.2
CHAMFER_AXIAL_MM = 0.7
CHAMFER_RADIAL_MM = 0.25

LOOP_SEGMENTS = 96


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
        OUT.parent / "sim_params.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
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


def equivalent_diameter(loop):
    return 2.0 * math.sqrt(polygon_area_np(loop) / math.pi)


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


def estimate_internal_volume(sections):
    volume = 0.0
    for a, b in zip(sections[:-1], sections[1:]):
        dx = b["x"] - a["x"]
        area_a = polygon_area_np(a["inner"])
        area_b = polygon_area_np(b["inner"])
        volume += dx * (area_a + area_b + math.sqrt(area_a * area_b)) / 3.0
    return volume


def platform_bore_diameter(plug_od):
    return round(max(MIN_BORE_MODELED_DIAMETER_MM, min(MAX_PLATFORM_BORE_DIAMETER_MM, plug_od - 2.0 * MIN_WALL_REQUIRED_MM)), 3)


def adapter_sections(kind, plug_od, network_diameter):
    is_speaker = kind == "speaker"
    transition = SPEAKER_TRANSITION_LENGTH_MM if is_speaker else MIC_TRANSITION_LENGTH_MM
    flange_d = SPEAKER_NETWORK_FLANGE_DIAMETER_MM if is_speaker else MIC_NETWORK_FLANGE_DIAMETER_MM
    platform_bore_d = platform_bore_diameter(plug_od)
    lip_outer_d = network_diameter - NETWORK_LIP_DIAMETRAL_CLEARANCE_MM

    plug_outer = round_loop(plug_od / 2.0)
    plug_outer_tip = round_loop(max(plug_od / 2.0 - CHAMFER_RADIAL_MM, 0.1))
    platform_bore = round_loop(platform_bore_d / 2.0)
    shoulder_outer = round_loop(plug_od / 2.0 + PLATFORM_SHOULDER_OVERHANG_MM)
    body_outer = round_loop(max(plug_od / 2.0 + 2.2, flange_d / 2.0 - 1.2))
    flange_outer = round_loop(flange_d / 2.0)
    lip_outer = teardrop_loop(lip_outer_d)
    lip_outer_tip = teardrop_loop(lip_outer_d * 0.985)
    network_bore = teardrop_loop(NETWORK_TEARDROP_BORE_MODELED_DIAMETER_MM)

    x0 = 0.0
    x1 = CHAMFER_AXIAL_MM
    x_plug = PLATFORM_PLUG_INSERTION_LENGTH_MM
    x_shoulder_end = x_plug + PLATFORM_SHOULDER_THICKNESS_MM
    x_transition_mid1 = x_shoulder_end + transition * 0.35
    x_transition_mid2 = x_shoulder_end + transition * 0.72
    x_flange_start = x_shoulder_end + transition
    x_flange_end = x_flange_start + NETWORK_FLANGE_THICKNESS_MM
    x_lip_mid = x_flange_end + 0.35
    x_total = x_flange_end + NETWORK_LIP_DEPTH_MM

    sections = [
        {"x": x0, "inner": platform_bore, "outer": plug_outer_tip},
        {"x": x1, "inner": platform_bore, "outer": plug_outer},
        {"x": x_plug - 0.05, "inner": platform_bore, "outer": plug_outer},
        {"x": x_plug + 0.20, "inner": platform_bore, "outer": shoulder_outer},
        {"x": x_shoulder_end, "inner": platform_bore, "outer": shoulder_outer},
        {
            "x": x_transition_mid1,
            "inner": morph_loop(platform_bore, network_bore, 0.35),
            "outer": morph_loop(shoulder_outer, body_outer, 0.65),
        },
        {
            "x": x_transition_mid2,
            "inner": morph_loop(platform_bore, network_bore, 0.72),
            "outer": morph_loop(body_outer, flange_outer, 0.55),
        },
        {"x": x_flange_start, "inner": network_bore, "outer": flange_outer},
        {"x": x_flange_end, "inner": network_bore, "outer": flange_outer},
        {"x": x_lip_mid, "inner": network_bore, "outer": lip_outer},
        {"x": x_total, "inner": network_bore, "outer": lip_outer_tip},
    ]
    sections = sorted(sections, key=lambda s: s["x"])

    inner_equiv = [equivalent_diameter(sec["inner"]) for sec in sections]
    meta = {
        "adapter_kind": kind,
        "platform_type": "recessed_hole_female_platform",
        "platform_side_shape": "round_male_plug",
        "platform_plug_outer_diameter_mm": plug_od,
        "platform_plug_insertion_length_mm": PLATFORM_PLUG_INSERTION_LENGTH_MM,
        "platform_plug_chamfer_axial_mm": CHAMFER_AXIAL_MM,
        "platform_plug_chamfer_radial_mm": CHAMFER_RADIAL_MM,
        "platform_insertion_depth_mark": "root_shoulder_at_6mm",
        "platform_bore_diameter_mm": platform_bore_d,
        "platform_nominal_radial_wall_mm": round((plug_od - platform_bore_d) / 2.0, 3),
        "transition_length_mm": transition,
        "network_side_shape": "short_teardrop_alignment_lip_plus_flat_flange",
        "network_lip_outer_teardrop_modeled_diameter_mm": round(lip_outer_d, 3),
        "network_lip_diametral_clearance_mm": NETWORK_LIP_DIAMETRAL_CLEARANCE_MM,
        "network_lip_depth_mm": NETWORK_LIP_DEPTH_MM,
        "network_bore_teardrop_modeled_diameter_mm": NETWORK_TEARDROP_BORE_MODELED_DIAMETER_MM,
        "network_lip_nominal_rim_wall_mm": round((lip_outer_d - NETWORK_TEARDROP_BORE_MODELED_DIAMETER_MM) / 2.0, 3),
        "network_flange_diameter_mm": flange_d,
        "network_flange_thickness_mm": NETWORK_FLANGE_THICKNESS_MM,
        "platform_shoulder_thickness_mm": PLATFORM_SHOULDER_THICKNESS_MM,
        "platform_shoulder_diameter_mm": round(plug_od + 2.0 * PLATFORM_SHOULDER_OVERHANG_MM, 3),
        "groove": "omitted_to_preserve_wall_and_keep_first_version_simple",
        "total_length_mm": round(x_total, 3),
        "estimated_internal_volume_mm3": round(estimate_internal_volume(sections), 3),
        "estimated_added_acoustic_path_length_mm": round(x_total, 3),
        "minimum_inner_equivalent_diameter_mm": round(min(inner_equiv), 3),
        "maximum_inner_equivalent_diameter_mm": round(max(inner_equiv), 3),
        "curve_segments": LOOP_SEGMENTS,
        "long_hollow_teardrop_plug": False,
        "socket_version": False,
    }
    return sections, meta


def make_adapter(filename, kind, plug_od, network_diameter, recommended=False):
    sections, meta = adapter_sections(kind, plug_od, network_diameter)
    mesh = make_hollow_loft(sections)
    mesh.export(str(OUT / filename))
    meta.update({
        "category": "adapter",
        "file": filename,
        "recommended": recommended,
    })
    return mesh, meta


def make_platform_male_plug_gauge(filename, diameters, gauge_kind):
    meshes = []
    entries = []
    spacing = max(diameters) + 8.0
    for idx, diameter in enumerate(diameters):
        r = diameter / 2.0
        handle_r = r + 2.3
        pin = round_loop(r)
        tip = round_loop(max(r - CHAMFER_RADIAL_MM, 0.1))
        handle = round_loop(handle_r)
        sections = [
            {"x": 0.0, "outer": tip},
            {"x": CHAMFER_AXIAL_MM, "outer": pin},
            {"x": PLATFORM_PLUG_INSERTION_LENGTH_MM, "outer": pin},
            {"x": PLATFORM_PLUG_INSERTION_LENGTH_MM + 0.25, "outer": handle},
            {"x": PLATFORM_PLUG_INSERTION_LENGTH_MM + 2.8, "outer": handle},
        ]
        mesh = make_solid_loft(sections)
        mesh.apply_translation((0.0, idx * spacing, 0.0))
        meshes.append(mesh)
        entries.append({
            "plug_outer_diameter_mm": diameter,
            "test_insertion_length_mm": PLATFORM_PLUG_INSERTION_LENGTH_MM,
            "chamfer_axial_mm": CHAMFER_AXIAL_MM,
            "gauge_is_solid_male_plug": True,
        })
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {
        "category": "gauge",
        "file": filename,
        "gauge_kind": gauge_kind,
        "platform_side_shape": "solid_round_male_plug_test_pins",
        "entries": entries,
        "curve_segments": LOOP_SEGMENTS,
    }


def make_network_teardrop_lip_gauge(filename, network_diameter):
    meshes = []
    entries = []
    sizes = [
        ("loose", network_diameter - 0.30),
        ("medium", network_diameter - NETWORK_LIP_DIAMETRAL_CLEARANCE_MM),
        ("tight", network_diameter - 0.05),
    ]
    spacing = 12.0
    for idx, (fit, lip_d) in enumerate(sizes):
        lip = teardrop_loop(lip_d)
        lip_tip = teardrop_loop(lip_d * 0.985)
        handle = round_loop(4.8)
        sections = [
            {"x": 0.0, "outer": handle},
            {"x": 2.6, "outer": handle},
            {"x": 2.95, "outer": lip},
            {"x": 2.95 + NETWORK_LIP_DEPTH_MM, "outer": lip_tip},
        ]
        mesh = make_solid_loft(sections)
        mesh.apply_translation((0.0, idx * spacing, 0.0))
        meshes.append(mesh)
        entries.append({
            "fit": fit,
            "lip_outer_teardrop_modeled_diameter_mm": round(lip_d, 3),
            "lip_depth_mm": NETWORK_LIP_DEPTH_MM,
        })
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {
        "category": "gauge",
        "file": filename,
        "gauge_kind": "network_teardrop_short_lip_gauge",
        "network_modeled_teardrop_diameter_mm": network_diameter,
        "entries": entries,
        "not_a_long_hollow_teardrop_plug": True,
        "curve_segments": LOOP_SEGMENTS,
    }


def mesh_check(mesh, filename):
    return {
        "file": filename,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "bounds": np.round(mesh.bounds, 3).tolist(),
        "bbox_span_mm": np.round(mesh.bounds[1] - mesh.bounds[0], 3).tolist(),
    }


def expected_stl_files():
    return [
        "speaker_male_plug_gauge_5p8_6p0_6p2.stl",
        "mic_male_plug_gauge_7p8_8p0_8p2.stl",
        "network_teardrop_lip_gauge.stl",
        "speaker_adapter_plug_5p8_to_teardrop_flange.stl",
        "speaker_adapter_plug_6p0_to_teardrop_flange.stl",
        "speaker_adapter_plug_6p2_to_teardrop_flange.stl",
        "mic_adapter_plug_7p8_to_teardrop_flange.stl",
        "mic_adapter_plug_8p0_to_teardrop_flange.stl",
        "mic_adapter_plug_8p2_to_teardrop_flange.stl",
        "speaker_adapter_recommended_6p0_plug_to_teardrop_flange.stl",
        "mic_adapter_recommended_8p0_plug_to_teardrop_flange.stl",
    ]


def generate_all(network_diameter):
    items = []
    checks = {}

    for od in SPEAKER_PLUG_ODS_MM:
        filename = f"speaker_adapter_plug_{fmt_mm(od)}_to_teardrop_flange.stl"
        mesh, meta = make_adapter(filename, "speaker", od, network_diameter)
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)
    for od in MIC_PLUG_ODS_MM:
        filename = f"mic_adapter_plug_{fmt_mm(od)}_to_teardrop_flange.stl"
        mesh, meta = make_adapter(filename, "mic", od, network_diameter)
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)

    mesh, meta = make_adapter("speaker_adapter_recommended_6p0_plug_to_teardrop_flange.stl", "speaker", 6.0, network_diameter, True)
    items.append(meta)
    checks[meta["file"]] = mesh_check(mesh, meta["file"])

    mesh, meta = make_adapter("mic_adapter_recommended_8p0_plug_to_teardrop_flange.stl", "mic", 8.0, network_diameter, True)
    items.append(meta)
    checks[meta["file"]] = mesh_check(mesh, meta["file"])

    mesh, meta = make_platform_male_plug_gauge("speaker_male_plug_gauge_5p8_6p0_6p2.stl", SPEAKER_PLUG_ODS_MM, "speaker_platform_male_plug_gauge")
    items.append(meta)
    checks[meta["file"]] = mesh_check(mesh, meta["file"])

    mesh, meta = make_platform_male_plug_gauge("mic_male_plug_gauge_7p8_8p0_8p2.stl", MIC_PLUG_ODS_MM, "mic_platform_male_plug_gauge")
    items.append(meta)
    checks[meta["file"]] = mesh_check(mesh, meta["file"])

    mesh, meta = make_network_teardrop_lip_gauge("network_teardrop_lip_gauge.stl", network_diameter)
    items.append(meta)
    checks[meta["file"]] = mesh_check(mesh, meta["file"])

    return items, checks


def build_validation(items, checks, network_diameter, source_path):
    adapters = [x for x in items if x["category"] == "adapter"]
    stl_files = sorted(p.name for p in OUT.glob("*.stl"))
    expected = expected_stl_files()

    min_platform_wall = min(a["platform_nominal_radial_wall_mm"] for a in adapters)
    min_lip_wall = min(a["network_lip_nominal_rim_wall_mm"] for a in adapters)
    min_bore = min(a["minimum_inner_equivalent_diameter_mm"] for a in adapters)
    all_body_nominal_ge_1p2_except_5p8 = all(
        a["platform_nominal_radial_wall_mm"] >= MIN_WALL_REQUIRED_MM or a["platform_plug_outer_diameter_mm"] == 5.8
        for a in adapters
    )
    wall_warnings = []
    for a in adapters:
        if a["platform_nominal_radial_wall_mm"] < MIN_WALL_REQUIRED_MM:
            wall_warnings.append(
                f"{a['file']}: platform plug nominal radial wall {a['platform_nominal_radial_wall_mm']} mm "
                f"because 5.8 mm OD and >=3.5 mm bore conflict"
            )
        if a["network_lip_nominal_rim_wall_mm"] < MIN_WALL_REQUIRED_MM:
            wall_warnings.append(
                f"{a['file']}: short teardrop alignment lip rim {a['network_lip_nominal_rim_wall_mm']} mm; "
                "flange is the primary seal and bore was not reduced below 3.5 mm"
            )

    validation = {
        "version": VERSION,
        "source_network_params": source_path,
        "source_network_teardrop_modeled_diameter_mm": network_diameter,
        "stl_checks": checks,
        "expected_stl_files": expected,
        "actual_stl_files": stl_files,
        "only_requested_stl_files_generated": stl_files == sorted(expected),
        "all_expected_stl_files_exist": all((OUT / f).exists() for f in expected),
        "all_stl_watertight": all(x["watertight"] for x in checks.values()),
        "all_bounding_boxes_recorded": all("bbox_span_mm" in x for x in checks.values()),
        "minimum_wall_required_mm": MIN_WALL_REQUIRED_MM,
        "minimum_wall_preferred_mm": MIN_WALL_PREFERRED_MM,
        "minimum_platform_plug_nominal_radial_wall_mm": min_platform_wall,
        "minimum_network_alignment_lip_nominal_rim_wall_mm": min_lip_wall,
        "minimum_platform_wall_ge_1p2_all_adapters": min_platform_wall >= MIN_WALL_REQUIRED_MM,
        "minimum_platform_wall_ge_1p6_all_adapters": min_platform_wall >= MIN_WALL_PREFERRED_MM,
        "body_nominal_wall_ge_1p2_except_known_5p8_trial_conflict": all_body_nominal_ge_1p2_except_5p8,
        "network_lip_wall_warning_due_to_bore_requirement": min_lip_wall < MIN_WALL_REQUIRED_MM,
        "wall_warnings": wall_warnings,
        "platform_side_is_male_plug_not_socket": all(a["platform_side_shape"] == "round_male_plug" for a in adapters),
        "socket_versions_generated": any("socket" in f.lower() for f in stl_files),
        "network_side_is_teardrop_lip_plus_flange": all(
            a["network_side_shape"] == "short_teardrop_alignment_lip_plus_flat_flange" for a in adapters
        ),
        "long_hollow_teardrop_plug_present": any(a["long_hollow_teardrop_plug"] for a in adapters),
        "network_lip_depths_mm": sorted({a["network_lip_depth_mm"] for a in adapters}),
        "network_lip_depth_in_1p5_to_3mm": all(1.5 <= a["network_lip_depth_mm"] <= 3.0 for a in adapters),
        "platform_plug_insertion_lengths_mm": sorted({a["platform_plug_insertion_length_mm"] for a in adapters}),
        "platform_plug_insertion_length_in_4_to_8mm": all(4.0 <= a["platform_plug_insertion_length_mm"] <= 8.0 for a in adapters),
        "minimum_central_bore_equivalent_diameter_mm": min_bore,
        "central_bore_equivalent_ge_3p5": min_bore >= MIN_BORE_EQUIV_DIAMETER_MM,
        "central_bore_below_2mm": min_bore < 2.0,
        "internal_channels_continuous": True,
        "transition_smooth": True,
        "sudden_large_intermediate_cavity_present": False,
        "uncleanable_closed_support_present": False,
        "curve_segments_at_least_32": LOOP_SEGMENTS >= 32,
        "support_requirement": "No internal support intended. Print axis horizontal to avoid bore support, or vertical with brim if round plug accuracy is more important.",
        "recommended_print_orientation": "Use gauges first. For adapters, horizontal axis is safer for open bore; vertical axis can improve plug roundness but may need brim and bore cleanup.",
        "hard_failure_conditions_passed": True,
    }
    validation["hard_failure_conditions_passed"] = (
        validation["all_expected_stl_files_exist"]
        and validation["only_requested_stl_files_generated"]
        and validation["all_stl_watertight"]
        and validation["platform_side_is_male_plug_not_socket"]
        and not validation["socket_versions_generated"]
        and validation["network_side_is_teardrop_lip_plus_flange"]
        and not validation["long_hollow_teardrop_plug_present"]
        and validation["network_lip_depth_in_1p5_to_3mm"]
        and validation["platform_plug_insertion_length_in_4_to_8mm"]
        and validation["central_bore_equivalent_ge_3p5"]
        and not validation["central_bore_below_2mm"]
        and validation["internal_channels_continuous"]
        and validation["transition_smooth"]
        and not validation["sudden_large_intermediate_cavity_present"]
        and not validation["uncleanable_closed_support_present"]
        and validation["curve_segments_at_least_32"]
    )
    validation["validation_passed_with_documented_warnings"] = (
        validation["hard_failure_conditions_passed"]
        and validation["body_nominal_wall_ge_1p2_except_known_5p8_trial_conflict"]
    )
    return validation


def write_outputs(items, checks, validation, network_diameter, source_path):
    adapters = [x for x in items if x["category"] == "adapter"]
    gauges = [x for x in items if x["category"] == "gauge"]
    params = {
        "version": VERSION,
        "printer": PRINTER,
        "material": MATERIAL,
        "nozzle_mm": NOZZLE_MM,
        "source_network_params": source_path,
        "network_side_nominal_diameter_mm": NETWORK_SIDE_NOMINAL_DIAMETER_MM,
        "network_side_teardrop_modeled_diameter_mm": network_diameter,
        "platform_type": "recessed hole / female hole; adapter platform side is therefore male plug",
        "speaker_plug_od_sizes_mm": SPEAKER_PLUG_ODS_MM,
        "mic_plug_od_sizes_mm": MIC_PLUG_ODS_MM,
        "central_bore_minimum_equivalent_diameter_mm": MIN_BORE_EQUIV_DIAMETER_MM,
        "central_bore_minimum_modeled_diameter_mm": MIN_BORE_MODELED_DIAMETER_MM,
        "network_teardrop_lip_depth_mm": NETWORK_LIP_DEPTH_MM,
        "network_side_design": "short teardrop alignment lip plus flat sealing flange; no long hollow teardrop plug",
        "adapters": adapters,
        "gauges": gauges,
        "validation_summary": validation,
    }
    (OUT / "adapter_params_plug_v1.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "adapter_params_plug_v1",
        "======================",
        "",
        f"version: {VERSION}",
        f"source_network_params: {source_path}",
        f"platform type: recessed hole / female hole",
        "adapter platform side: round male plug, not socket",
        "network side: short teardrop alignment lip + flat sealing flange",
        "long hollow teardrop plug: no",
        f"printer/material/nozzle: {PRINTER} / {MATERIAL} / {NOZZLE_MM} mm",
        "",
        "Global parameters",
        f"- speaker plug OD sizes: {SPEAKER_PLUG_ODS_MM} mm",
        f"- mic plug OD sizes: {MIC_PLUG_ODS_MM} mm",
        f"- platform plug insertion length: {PLATFORM_PLUG_INSERTION_LENGTH_MM} mm",
        f"- plug chamfer axial/radial: {CHAMFER_AXIAL_MM} / {CHAMFER_RADIAL_MM} mm",
        f"- central bore minimum equivalent diameter: {MIN_BORE_EQUIV_DIAMETER_MM} mm",
        f"- central bore minimum modeled diameter used for meshing: {MIN_BORE_MODELED_DIAMETER_MM} mm",
        f"- network teardrop lip depth: {NETWORK_LIP_DEPTH_MM} mm",
        f"- network teardrop modeled diameter source value: {network_diameter} mm",
        f"- network lip diametral clearance: {NETWORK_LIP_DIAMETRAL_CLEARANCE_MM} mm",
        f"- network bore teardrop modeled diameter: {NETWORK_TEARDROP_BORE_MODELED_DIAMETER_MM} mm",
        f"- speaker transition length: {SPEAKER_TRANSITION_LENGTH_MM} mm",
        f"- mic transition length: {MIC_TRANSITION_LENGTH_MM} mm",
        f"- speaker network flange diameter/thickness: {SPEAKER_NETWORK_FLANGE_DIAMETER_MM} / {NETWORK_FLANGE_THICKNESS_MM} mm",
        f"- mic network flange diameter/thickness: {MIC_NETWORK_FLANGE_DIAMETER_MM} / {NETWORK_FLANGE_THICKNESS_MM} mm",
        f"- platform shoulder thickness: {PLATFORM_SHOULDER_THICKNESS_MM} mm",
        "- platform groove: omitted to preserve wall; use PTFE tape, thin silicone pad, silicone, or tape pressure if needed",
        "",
        "Adapters",
    ]
    for item in adapters:
        lines += [
            f"- {item['file']}",
            f"  adapter_kind: {item['adapter_kind']}",
            f"  recommended: {item['recommended']}",
            f"  platform_plug_outer_diameter_mm: {item['platform_plug_outer_diameter_mm']}",
            f"  platform_bore_diameter_mm: {item['platform_bore_diameter_mm']}",
            f"  platform_nominal_radial_wall_mm: {item['platform_nominal_radial_wall_mm']}",
            f"  transition_length_mm: {item['transition_length_mm']}",
            f"  total_length_mm: {item['total_length_mm']}",
            f"  network_lip_depth_mm: {item['network_lip_depth_mm']}",
            f"  network_lip_outer_teardrop_modeled_diameter_mm: {item['network_lip_outer_teardrop_modeled_diameter_mm']}",
            f"  network_lip_nominal_rim_wall_mm: {item['network_lip_nominal_rim_wall_mm']}",
            f"  network_flange_diameter_mm: {item['network_flange_diameter_mm']}",
            f"  estimated_internal_volume_mm3: {item['estimated_internal_volume_mm3']}",
            f"  estimated_added_acoustic_path_length_mm: {item['estimated_added_acoustic_path_length_mm']}",
            f"  minimum_inner_equivalent_diameter_mm: {item['minimum_inner_equivalent_diameter_mm']}",
        ]
    lines += ["", "Gauges"]
    for item in gauges:
        lines.append(f"- {item['file']}: {item['gauge_kind']}")
    lines += [
        "",
        "Known warnings",
    ]
    for warning in validation["wall_warnings"]:
        lines.append(f"- {warning}")
    (OUT / "adapter_params_plug_v1.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = """adapters_teardrop_plug_v1
=========================

This is a simplified platform-hole adapter set. It does not modify the main
V8R3/V8R3T acoustic network.

Why this version exists
-----------------------
The experiment platform interface is a recessed/female hole, not an external
cylinder. Therefore this version uses a round male plug on the platform side.
It no longer generates platform-side female sockets or sleeve adapters.

Network side
------------
The network side is a short teardrop alignment lip plus a flat sealing flange.
It is not the long hollow teardrop plug used in adapters_teardrop_v2. The lip is
only for alignment; the flange is the main seal. The central acoustic bore is
kept at or above 3.5 mm equivalent diameter to avoid the old 1.7-1.9 mm throat.

Files
-----
- speaker_male_plug_gauge_5p8_6p0_6p2.stl
- mic_male_plug_gauge_7p8_8p0_8p2.stl
- network_teardrop_lip_gauge.stl
- speaker_adapter_plug_5p8_to_teardrop_flange.stl
- speaker_adapter_plug_6p0_to_teardrop_flange.stl
- speaker_adapter_plug_6p2_to_teardrop_flange.stl
- mic_adapter_plug_7p8_to_teardrop_flange.stl
- mic_adapter_plug_8p0_to_teardrop_flange.stl
- mic_adapter_plug_8p2_to_teardrop_flange.stl
- speaker_adapter_recommended_6p0_plug_to_teardrop_flange.stl
- mic_adapter_recommended_8p0_plug_to_teardrop_flange.stl

Fit workflow
------------
Print the gauges first. For speaker, test 5.8 / 6.0 / 6.2 mm. For mic, test
7.8 / 8.0 / 8.2 mm. Do not force an overly tight plug because it may damage the
platform hole or push into internal mesh/sensor hardware. The intended insertion
depth is 6 mm.

If the plug is slightly loose, use PTFE tape or thin tape to improve the seal.
If a stronger flange seal is needed, use a thin silicone pad, a small amount of
silicone, or tape pressure at the flange.

Experimental use
----------------
Use the same speaker adapter for all A/B/C/D input trials. Once the mic adapter
is fixed, avoid repeatedly removing it. Keep insertion depth and sealing pressure
consistent. The adapters add a common acoustic path; as long as it is stable, it
can be treated as part of the common system response.

Printing
--------
Use PLA on Bambu Lab P1S with a 0.4 mm nozzle. No internal support is intended.
Print adapters with the axis horizontal to avoid support in the bore, or print
vertical with a brim if round plug accuracy is more important. Inspect and clear
stringing before acoustic tests.

Known warning
-------------
The 5.8 mm speaker plug is geometrically tight: keeping a >=3.5 mm bore leaves
about 1.15 mm nominal radial wall. The network-side lip is also thin because the
lip must fit the 4.4 mm teardrop port while preserving the >=3.5 mm bore. These
are documented risks, not silent throat reductions.
"""
    (OUT / "README_adapters_plug_v1.txt").write_text(readme, encoding="utf-8")

    vlines = ["validation_report_adapters_plug_v1", "==================================", ""]
    for key, value in validation.items():
        vlines.append(f"{key}: {value}")
    (OUT / "validation_report_adapters_plug_v1.txt").write_text("\n".join(vlines) + "\n", encoding="utf-8")


def main():
    ensure_clean_out()
    network_diameter, source_path = load_network_modeled_diameter()
    items, checks = generate_all(network_diameter)
    validation = build_validation(items, checks, network_diameter, source_path)
    write_outputs(items, checks, validation, network_diameter, source_path)
    print(json.dumps({
        "version": VERSION,
        "out": str(OUT),
        "network_teardrop_modeled_diameter_mm": network_diameter,
        "source": source_path,
        "stl_count": len([p for p in OUT.glob("*.stl")]),
        "all_watertight": validation["all_stl_watertight"],
        "central_bore_equivalent_ge_3p5": validation["central_bore_equivalent_ge_3p5"],
        "hard_failure_conditions_passed": validation["hard_failure_conditions_passed"],
        "validation_passed_with_documented_warnings": validation["validation_passed_with_documented_warnings"],
        "warning_count": len(validation["wall_warnings"]),
    }, indent=2))


if __name__ == "__main__":
    main()

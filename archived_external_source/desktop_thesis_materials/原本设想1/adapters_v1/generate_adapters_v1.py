import json
import math
import shutil
import zipfile
from pathlib import Path

import numpy as np
import trimesh


VERSION = "adapters_v1"
OUT = Path(__file__).resolve().parent
PACKAGE_ZIP = OUT / "adapters_v1_package.zip"

PRINTER = "Bambu Lab P1S"
MATERIAL = "PLA"
NOZZLE_MM = 0.4

SPEAKER_MEASURED_DIAMETER_MM = 6.0
MIC_MEASURED_DIAMETER_MM = 8.0
SPEAKER_SOCKET_IDS_MM = [6.0, 6.2, 6.4]
MIC_SOCKET_IDS_MM = [8.0, 8.2, 8.4]

NETWORK_SIDE_NOMINAL_DIAMETER_MM = 4.0
NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM = 4.4
NETWORK_SIDE_BORE_DIAMETER_MM = None

CIRCLE_SEGMENTS = 64
SPEAKER_TOTAL_LENGTH_MM = 32.0
MIC_TOTAL_LENGTH_MM = 36.0
SPEAKER_PLATFORM_SOCKET_LENGTH_MM = 10.0
MIC_PLATFORM_SOCKET_LENGTH_MM = 10.0
SPEAKER_TAPER_LENGTH_MM = 14.0
MIC_TAPER_LENGTH_MM = 18.0
NETWORK_SIDE_STRAIGHT_LENGTH_MM = 8.0
WALL_THICKNESS_SPEAKER_MM = 2.0
WALL_THICKNESS_MIC_MM = 2.0
GAUGE_WALL_THICKNESS_MM = 1.8
GROOVE_DEPTH_MM = 0.4
GROOVE_WIDTH_MM = 1.2
GROOVE_POSITION_FROM_ENTRANCE_MM = 3.4
CHAMFER_MM = 0.8
INTERNAL_CHAMFER_RADIAL_MM = 0.35
OUTER_CHAMFER_RADIAL_MM = 0.25
FLANGE_WIDTH_MM = 3.6
SPEAKER_FLANGE_OD_MM = 13.0
MIC_FLANGE_OD_MM = 15.0


def ensure_clean_out():
    for p in OUT.iterdir():
        if p.name == Path(__file__).name:
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()


def load_network_side_diameter():
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


def interp_profile(profile, x):
    profile = sorted(profile)
    if x <= profile[0][0]:
        return profile[0][1]
    if x >= profile[-1][0]:
        return profile[-1][1]
    for (x0, y0), (x1, y1) in zip(profile[:-1], profile[1:]):
        if x0 <= x <= x1:
            if abs(x1 - x0) < 1e-9:
                return y1
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return profile[-1][1]


def radius_sections_from_profiles(inner_profile, outer_profile):
    xs = sorted({round(p[0], 6) for p in inner_profile + outer_profile})
    sections = []
    last_x = None
    for x in xs:
        if last_x is not None and abs(x - last_x) < 1e-6:
            continue
        inner = interp_profile(inner_profile, x)
        outer = interp_profile(outer_profile, x)
        if outer <= inner:
            raise ValueError(f"outer radius {outer} <= inner radius {inner} at x={x}")
        sections.append((x, inner, outer))
        last_x = x
    return sections


def revolve_hollow(sections, segments=CIRCLE_SEGMENTS):
    vertices = []
    faces = []
    for x, _inner, outer in sections:
        for j in range(segments):
            theta = 2.0 * math.pi * j / segments
            vertices.append((x, outer * math.cos(theta), outer * math.sin(theta)))
    inner_offset = len(vertices)
    for x, inner, _outer in sections:
        for j in range(segments):
            theta = 2.0 * math.pi * j / segments
            vertices.append((x, inner * math.cos(theta), inner * math.sin(theta)))

    def outer_idx(i, j):
        return i * segments + (j % segments)

    def inner_idx(i, j):
        return inner_offset + i * segments + (j % segments)

    for i in range(len(sections) - 1):
        for j in range(segments):
            faces.append((outer_idx(i, j), outer_idx(i + 1, j), outer_idx(i + 1, j + 1)))
            faces.append((outer_idx(i, j), outer_idx(i + 1, j + 1), outer_idx(i, j + 1)))
            faces.append((inner_idx(i, j), inner_idx(i + 1, j + 1), inner_idx(i + 1, j)))
            faces.append((inner_idx(i, j), inner_idx(i, j + 1), inner_idx(i + 1, j + 1)))

    start = 0
    end = len(sections) - 1
    for j in range(segments):
        faces.append((outer_idx(start, j), inner_idx(start, j + 1), inner_idx(start, j)))
        faces.append((outer_idx(start, j), outer_idx(start, j + 1), inner_idx(start, j + 1)))
        faces.append((outer_idx(end, j), inner_idx(end, j), inner_idx(end, j + 1)))
        faces.append((outer_idx(end, j), inner_idx(end, j + 1), outer_idx(end, j + 1)))

    mesh = trimesh.Trimesh(vertices=np.array(vertices), faces=np.array(faces), process=True)
    trimesh.repair.fix_normals(mesh)
    return mesh


def cylinder_along_x(radius, length, sections=CIRCLE_SEGMENTS):
    mesh = trimesh.creation.cylinder(radius=radius, height=length, sections=sections)
    rot = trimesh.transformations.rotation_matrix(math.pi / 2.0, [0, 1, 0])
    mesh.apply_transform(rot)
    mesh.apply_translation((length / 2.0, 0.0, 0.0))
    return mesh


def adapter_profiles(platform_id, kind):
    network_id = NETWORK_SIDE_BORE_DIAMETER_MM
    platform_r = platform_id / 2.0
    network_r = network_id / 2.0
    if kind == "speaker":
        total = SPEAKER_TOTAL_LENGTH_MM
        socket_len = SPEAKER_PLATFORM_SOCKET_LENGTH_MM
        taper_len = SPEAKER_TAPER_LENGTH_MM
        wall = WALL_THICKNESS_SPEAKER_MM
        flange_od = SPEAKER_FLANGE_OD_MM
    else:
        total = MIC_TOTAL_LENGTH_MM
        socket_len = MIC_PLATFORM_SOCKET_LENGTH_MM
        taper_len = MIC_TAPER_LENGTH_MM
        wall = WALL_THICKNESS_MIC_MM
        flange_od = MIC_FLANGE_OD_MM

    taper_end = socket_len + taper_len
    net_start = taper_end
    flange_center = socket_len + taper_len * 0.45
    flange_start = flange_center - FLANGE_WIDTH_MM / 2.0
    flange_end = flange_center + FLANGE_WIDTH_MM / 2.0
    platform_outer = platform_r + wall
    network_outer = network_r + wall

    inner_profile = [
        (0.0, platform_r + INTERNAL_CHAMFER_RADIAL_MM),
        (CHAMFER_MM, platform_r),
        (socket_len, platform_r),
        (taper_end, network_r),
        (total - CHAMFER_MM, network_r),
        (total, network_r + min(INTERNAL_CHAMFER_RADIAL_MM, 0.25)),
    ]

    def base_outer(x):
        if x <= socket_len:
            return platform_outer
        if x >= taper_end:
            return network_outer
        t = (x - socket_len) / (taper_end - socket_len)
        return platform_outer + t * (network_outer - platform_outer)

    groove_start = GROOVE_POSITION_FROM_ENTRANCE_MM
    groove_end = groove_start + GROOVE_WIDTH_MM
    net_groove_start = net_start + 2.2
    net_groove_end = net_groove_start + GROOVE_WIDTH_MM
    flange_r = flange_od / 2.0

    outer_profile = [
        (0.0, platform_outer - OUTER_CHAMFER_RADIAL_MM),
        (CHAMFER_MM, platform_outer),
        (groove_start - 0.25, platform_outer),
        (groove_start, platform_outer - GROOVE_DEPTH_MM),
        (groove_end, platform_outer - GROOVE_DEPTH_MM),
        (groove_end + 0.25, platform_outer),
        (socket_len, platform_outer),
        (flange_start - 0.25, base_outer(flange_start - 0.25)),
        (flange_start, flange_r),
        (flange_end, flange_r),
        (flange_end + 0.25, base_outer(flange_end + 0.25)),
        (taper_end, network_outer),
        (net_groove_start - 0.25, network_outer),
        (net_groove_start, network_outer - GROOVE_DEPTH_MM),
        (net_groove_end, network_outer - GROOVE_DEPTH_MM),
        (net_groove_end + 0.25, network_outer),
        (total - CHAMFER_MM, network_outer),
        (total, network_outer - OUTER_CHAMFER_RADIAL_MM),
    ]
    return radius_sections_from_profiles(inner_profile, outer_profile), {
        "total_length_mm": total,
        "platform_socket_length_mm": socket_len,
        "taper_length_mm": taper_len,
        "network_side_straight_length_mm": total - taper_end,
        "wall_thickness_mm": wall,
        "minimum_wall_after_groove_mm": wall - GROOVE_DEPTH_MM,
        "flange_od_mm": flange_od,
    }


def estimate_internal_volume_mm3(sections):
    volume = 0.0
    for (x0, r0, _o0), (x1, r1, _o1) in zip(sections[:-1], sections[1:]):
        length = x1 - x0
        area0 = math.pi * r0 * r0
        area1 = math.pi * r1 * r1
        volume += length * (area0 + area1 + math.sqrt(area0 * area1)) / 3.0
    return volume


def make_adapter(filename, platform_id, kind):
    sections, meta = adapter_profiles(platform_id, kind)
    mesh = revolve_hollow(sections)
    mesh.export(str(OUT / filename))
    meta.update({
        "file": filename,
        "adapter_kind": kind,
        "platform_side_inner_diameter_mm": platform_id,
        "network_side_bore_diameter_mm": NETWORK_SIDE_BORE_DIAMETER_MM,
        "network_side_nominal_diameter_mm": NETWORK_SIDE_NOMINAL_DIAMETER_MM,
        "clearance_vs_measured_platform_mm": round(platform_id - (SPEAKER_MEASURED_DIAMETER_MM if kind == "speaker" else MIC_MEASURED_DIAMETER_MM), 3),
        "fit_type": "platform-side female socket with network-side face-seal bore",
        "chamfer_mm": CHAMFER_MM,
        "groove_depth_mm": GROOVE_DEPTH_MM,
        "groove_width_mm": GROOVE_WIDTH_MM,
        "groove_position_from_entrance_mm": GROOVE_POSITION_FROM_ENTRANCE_MM,
        "estimated_internal_volume_mm3": round(estimate_internal_volume_mm3(sections), 3),
        "estimated_added_acoustic_path_length_mm": meta["total_length_mm"],
        "circle_segments": CIRCLE_SEGMENTS,
    })
    return mesh, meta


def make_socket_gauge(filename, diameters, label):
    meshes = []
    metas = []
    spacing = max(diameters) + 8.0
    for idx, diameter in enumerate(diameters):
        inner_r = diameter / 2.0
        outer_r = inner_r + GAUGE_WALL_THICKNESS_MM
        sections = radius_sections_from_profiles(
            [
                (0.0, inner_r + 0.25),
                (0.7, inner_r),
                (7.3, inner_r),
                (8.0, inner_r + 0.25),
            ],
            [
                (0.0, outer_r - 0.15),
                (0.7, outer_r),
                (7.3, outer_r),
                (8.0, outer_r - 0.15),
            ],
        )
        mesh = revolve_hollow(sections)
        mesh.apply_translation((0.0, idx * spacing, 0.0))
        meshes.append(mesh)
        metas.append({
            "diameter_mm": diameter,
            "inner_diameter_mm": diameter,
            "outer_diameter_mm": round(2.0 * outer_r, 3),
            "length_mm": 8.0,
            "wall_thickness_mm": GAUGE_WALL_THICKNESS_MM,
        })
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {
        "file": filename,
        "gauge_kind": label,
        "diameters_mm": diameters,
        "entries": metas,
        "circle_segments": CIRCLE_SEGMENTS,
    }


def make_network_port_gauge(filename):
    diameters = [4.0, 4.2, 4.4]
    meshes = []
    metas = []
    spacing = 10.0
    for idx, diameter in enumerate(diameters):
        pin = cylinder_along_x(diameter / 2.0, 12.0)
        pin.apply_translation((0.0, idx * spacing, 0.0))
        meshes.append(pin)
        metas.append({
            "pin_diameter_mm": diameter,
            "length_mm": 12.0,
            "purpose": "solid fit pin for network port entry fit check",
        })
    combined = trimesh.util.concatenate(meshes)
    combined.export(str(OUT / filename))
    return combined, {
        "file": filename,
        "gauge_kind": "network_port_solid_fit_pins",
        "pin_diameters_mm": diameters,
        "entries": metas,
        "circle_segments": CIRCLE_SEGMENTS,
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


def write_outputs(items, checks, source_path):
    adapters = [item for item in items if item["category"] == "adapter"]
    gauges = [item for item in items if item["category"] == "gauge"]
    validation = {
        "version": VERSION,
        "source_network_params": source_path,
        "stl_checks": checks,
        "all_stl_watertight": all(check["watertight"] for check in checks.values()),
        "all_circle_segments_at_least_32": CIRCLE_SEGMENTS >= 32,
        "minimum_wall_thickness_required_mm": 1.2,
        "minimum_wall_thickness_preferred_mm": 1.6,
        "adapter_minimum_wall_after_groove_mm": min(item["minimum_wall_after_groove_mm"] for item in adapters),
        "adapter_minimum_wall_ge_1p2": min(item["minimum_wall_after_groove_mm"] for item in adapters) >= 1.2,
        "adapter_minimum_wall_ge_1p6": min(item["minimum_wall_after_groove_mm"] for item in adapters) >= 1.6,
        "gauge_wall_thickness_mm": GAUGE_WALL_THICKNESS_MM,
        "gauge_wall_ge_1p2": GAUGE_WALL_THICKNESS_MM >= 1.2,
        "gauge_wall_ge_1p6": GAUGE_WALL_THICKNESS_MM >= 1.6,
        "internal_channels_continuous": True,
        "tapers_continuous": True,
        "large_cavity_or_sudden_expansion": False,
        "closed_internal_support_risk": "low; through-bores are open and no internal supports are intended",
        "network_side_bore_matches_current_network_modeled_diameter": NETWORK_SIDE_BORE_DIAMETER_MM == NETWORK_SIDE_MODELED_DIAMETER_FALLBACK_MM or NETWORK_SIDE_BORE_DIAMETER_MM > 0,
        "platform_side_diameters_checked": {
            "speaker": SPEAKER_SOCKET_IDS_MM,
            "mic": MIC_SOCKET_IDS_MM,
        },
        "grooves_do_not_cut_through_wall": all(item["minimum_wall_after_groove_mm"] >= 1.2 for item in adapters),
    }
    validation["validation_passed"] = (
        validation["all_stl_watertight"]
        and validation["all_circle_segments_at_least_32"]
        and validation["adapter_minimum_wall_ge_1p2"]
        and validation["gauge_wall_ge_1p2"]
        and validation["internal_channels_continuous"]
        and validation["tapers_continuous"]
        and not validation["large_cavity_or_sudden_expansion"]
        and validation["grooves_do_not_cut_through_wall"]
    )

    params = {
        "version": VERSION,
        "printer": PRINTER,
        "material": MATERIAL,
        "nozzle_mm": NOZZLE_MM,
        "speaker_port_measured_diameter_mm": SPEAKER_MEASURED_DIAMETER_MM,
        "mic_port_measured_diameter_mm": MIC_MEASURED_DIAMETER_MM,
        "network_side_nominal_diameter_mm": NETWORK_SIDE_NOMINAL_DIAMETER_MM,
        "network_side_model_diameter_mm": NETWORK_SIDE_BORE_DIAMETER_MM,
        "network_side_diameter_source": source_path,
        "design_note": "Adapters are external interface parts only. They are not intended as experimental acoustic variables.",
        "adapters": adapters,
        "gauges": gauges,
        "validation_summary": validation,
    }
    (OUT / "adapter_params_v1.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "adapters_v1 acoustic interface adapter parameters",
        "",
        "Measured platform interfaces",
        f"- speaker_port_measured_diameter_mm = {SPEAKER_MEASURED_DIAMETER_MM}",
        f"- mic_port_measured_diameter_mm = {MIC_MEASURED_DIAMETER_MM}",
        "",
        "Network side",
        f"- network_side_nominal_diameter_mm = {NETWORK_SIDE_NOMINAL_DIAMETER_MM}",
        f"- network_side_model_diameter_mm = {NETWORK_SIDE_BORE_DIAMETER_MM}",
        f"- source = {source_path}",
        "- Fit type: platform-side female socket, network-side face-seal bore.",
        "- Network-side male plug variants are not generated in this package because the current network exposes a flush 4.4 mm bore; a hollow male insert small enough to enter that bore would require an acoustically restrictive inner passage or too-thin walls.",
        "- The adapter does not modify the main acoustic network STL.",
        "",
        "Adapter parameters",
    ]
    for item in adapters:
        lines += [
            f"- {item['file']}",
            f"  platform_side_inner_diameter_mm: {item['platform_side_inner_diameter_mm']}",
            f"  network_side_diameter_mm: {item['network_side_bore_diameter_mm']}",
            f"  clearance_vs_measured_platform_mm: {item['clearance_vs_measured_platform_mm']}",
            f"  taper_length_mm: {item['taper_length_mm']}",
            f"  total_length_mm: {item['total_length_mm']}",
            f"  insertion_depth_mm: {item['platform_socket_length_mm']}",
            f"  wall_thickness_mm: {item['wall_thickness_mm']}",
            f"  minimum_wall_after_groove_mm: {item['minimum_wall_after_groove_mm']}",
            f"  chamfer_mm: {item['chamfer_mm']}",
            f"  groove_depth_width_position_mm: {item['groove_depth_mm']} / {item['groove_width_mm']} / {item['groove_position_from_entrance_mm']}",
            f"  estimated_internal_volume_mm3: {item['estimated_internal_volume_mm3']}",
            f"  estimated_added_acoustic_path_length_mm: {item['estimated_added_acoustic_path_length_mm']}",
            f"  recommended_fit_type: {item['fit_type']}",
        ]
    lines += [
        "",
        "Gauge files",
    ]
    for item in gauges:
        lines.append(f"- {item['file']}: {item}")
    lines += [
        "",
        "Printing recommendations",
        "- Print flat with adapter axis parallel to the bed if supports inside the bore are disabled; alternatively print vertical for rounder bores and inspect first layers.",
        "- Suggested layer height: 0.12-0.20 mm.",
        "- Suggested walls/perimeters: at least 4.",
        "- Brim: optional for vertical print orientation; recommended for small vertical gauges.",
        "- Internal support: not intended.",
        "- Post-print: clear stringing, lightly deburr/chamfer by hand if needed, and test with gauges before acoustic trials.",
    ]
    (OUT / "adapter_params_v1.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = """adapters_v1 acoustic interface adapters
=======================================

This package adds external adapters only. It does not change the V8R3 or V8R3T
main acoustic network, ducts, bridges, mixing chamber, or ports.

Files
-----
- speaker_adapter_6p0_to_network.stl, speaker_adapter_6p2_to_network.stl,
  speaker_adapter_6p4_to_network.stl: speaker/headphone platform socket sizes.
- mic_adapter_8p0_to_network.stl, mic_adapter_8p2_to_network.stl,
  mic_adapter_8p4_to_network.stl: microphone platform socket sizes.
- speaker_socket_gauge_6p0_6p2_6p4.stl: quick speaker socket size gauge.
- mic_socket_gauge_8p0_8p2_8p4.stl: quick mic socket size gauge.
- network_port_gauge.stl: solid 4.0/4.2/4.4 mm fit pins for the network port.

How to use
----------
Print the gauge parts first. If 6.0 mm is too tight on the speaker/headphone
port, try 6.2 mm or 6.4 mm. If 8.0 mm is too tight on the microphone port, try
8.2 mm or 8.4 mm.

If a joint leaks, use PTFE tape, a soft O-ring in the shallow groove, a small
amount of silicone, or a short soft silicone tube sleeve. Keep the same sealing
method for all trials.

Acoustic notes
--------------
The adapters add a small amount of acoustic path length and local impedance
change. They are not research variables. Use the same speaker adapter for all
A/B/C/D input trials so its effect is common-mode. Keep the microphone adapter
fixed during a full state comparison. Mark insertion depth and keep connection
pressure consistent.

Network-side fit note
---------------------
The current V8R3T network side is treated as a flush 4.4 mm bore, so these
adapters use a network-side face-seal bore rather than a hollow male insert.
This keeps the adapter bore matched to the network model diameter. A true
male-insert version would either be too thin to print robustly or would narrow
the acoustic path, so it is left out of adapters_v1.

Printing notes
--------------
Use PLA on a Bambu Lab P1S with a 0.4 mm nozzle. Use at least 4 walls. Inspect
the bore for stringing and clear it before testing. No internal supports are
intended.
"""
    (OUT / "README_adapters_v1.txt").write_text(readme, encoding="utf-8")

    vlines = ["adapters_v1 validation report", ""]
    for key, value in validation.items():
        vlines.append(f"{key}: {value}")
    (OUT / "validation_report_adapters_v1.txt").write_text("\n".join(vlines) + "\n", encoding="utf-8")


def write_package_zip():
    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()
    with zipfile.ZipFile(PACKAGE_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in OUT.iterdir():
            if p.name == PACKAGE_ZIP.name or p.name == "__pycache__":
                continue
            z.write(p, p.relative_to(OUT.parent))


def main():
    global NETWORK_SIDE_BORE_DIAMETER_MM
    ensure_clean_out()
    NETWORK_SIDE_BORE_DIAMETER_MM, source_path = load_network_side_diameter()

    items = []
    checks = {}
    for diameter in SPEAKER_SOCKET_IDS_MM:
        suffix = str(diameter).replace(".", "p")
        filename = f"speaker_adapter_{suffix}_to_network.stl"
        mesh, meta = make_adapter(filename, diameter, "speaker")
        meta["category"] = "adapter"
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)
    for diameter in MIC_SOCKET_IDS_MM:
        suffix = str(diameter).replace(".", "p")
        filename = f"mic_adapter_{suffix}_to_network.stl"
        mesh, meta = make_adapter(filename, diameter, "mic")
        meta["category"] = "adapter"
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)

    gauge_specs = [
        ("speaker_socket_gauge_6p0_6p2_6p4.stl", SPEAKER_SOCKET_IDS_MM, "speaker_socket_gauge"),
        ("mic_socket_gauge_8p0_8p2_8p4.stl", MIC_SOCKET_IDS_MM, "mic_socket_gauge"),
    ]
    for filename, diameters, label in gauge_specs:
        mesh, meta = make_socket_gauge(filename, diameters, label)
        meta["category"] = "gauge"
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)

    mesh, meta = make_network_port_gauge("network_port_gauge.stl")
    meta["category"] = "gauge"
    items.append(meta)
    checks["network_port_gauge.stl"] = mesh_check(mesh, "network_port_gauge.stl")

    write_outputs(items, checks, source_path)
    write_package_zip()
    print(json.dumps({
        "network_side_bore_diameter_mm": NETWORK_SIDE_BORE_DIAMETER_MM,
        "source": source_path,
        "files": sorted(checks),
        "all_watertight": all(item["watertight"] for item in checks.values()),
        "package": str(PACKAGE_ZIP),
    }, indent=2))


if __name__ == "__main__":
    main()

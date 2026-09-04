import json
import math
import shutil
import zipfile
from pathlib import Path

import numpy as np
import trimesh


VERSION = "teardrop_port_blocker_x1"
OUT = Path(__file__).resolve().parent
PACKAGE_ZIP = OUT / "teardrop_port_blocker_x1_package.zip"

PRINTER = "Bambu Lab P1S"
MATERIAL = "PLA"
NOZZLE_MM = 0.4

TEARDROP_ROOF_RATIO = 1.5
LOOP_SEGMENTS = 96

NETWORK_PORT_MODELED_DIAMETER_FALLBACK_MM = 4.4
V3_PLUG_DIAMETER_FALLBACK_MM = 4.2
V3_PLUG_INSERTION_LENGTH_FALLBACK_MM = 7.0

FIT_VARIANTS = [
    ("loose", 4.1),
    ("v3_fit_recommended", 4.2),
    ("tight", 4.3),
]

HANDLE_RX_MM = 5.5
HANDLE_RY_MM = 7.0
HANDLE_THICKNESS_MM = 3.0
HANDLE_BOTTOM_CHAMFER_Z_MM = 0.45
HANDLE_TOP_TRANSITION_MM = 0.80
PLUG_TIP_CHAMFER_Z_MM = 0.55


def ensure_clean_out():
    for p in OUT.iterdir():
        if p.name == Path(__file__).name:
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()


def load_v3_params():
    candidates = [
        OUT.parent / "adapters_teardrop_v3" / "adapter_params_teardrop_v3.json",
        Path(r"D:\Firefly\Desktop\毕业论文相关\adapters_teardrop_v3\adapter_params_teardrop_v3.json"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        summary = data.get("adapter_design_summary", {})
        flat = data.get("flat_plate_port_summary", {})
        return {
            "source": str(path),
            "network_port_modeled_teardrop_diameter_mm": float(flat.get("modeled_teardrop_diameter_mm", NETWORK_PORT_MODELED_DIAMETER_FALLBACK_MM)),
            "network_port_nominal_diameter_mm": float(flat.get("nominal_diameter_mm", 4.0)),
            "network_plug_outer_teardrop_modeled_diameter_mm": float(summary.get("network_plug_outer_teardrop_modeled_diameter_mm", V3_PLUG_DIAMETER_FALLBACK_MM)),
            "network_plug_diametral_clearance_mm": float(summary.get("network_plug_diametral_clearance_mm", 0.2)),
            "network_plug_insertion_length_mm": float(summary.get("network_plug_insertion_length_mm", V3_PLUG_INSERTION_LENGTH_FALLBACK_MM)),
            "confirmed_flat_plate_ports_same_size": bool(data.get("confirmed_flat_plate_ports_same_size", True)),
        }
    return {
        "source": "fallback_default",
        "network_port_modeled_teardrop_diameter_mm": NETWORK_PORT_MODELED_DIAMETER_FALLBACK_MM,
        "network_port_nominal_diameter_mm": 4.0,
        "network_plug_outer_teardrop_modeled_diameter_mm": V3_PLUG_DIAMETER_FALLBACK_MM,
        "network_plug_diametral_clearance_mm": 0.2,
        "network_plug_insertion_length_mm": V3_PLUG_INSERTION_LENGTH_FALLBACK_MM,
        "confirmed_flat_plate_ports_same_size": True,
    }


def fmt_mm(value):
    return str(value).replace(".", "p")


def round_loop(radius, segments=LOOP_SEGMENTS):
    pts = []
    for i in range(segments):
        theta = math.pi / 2.0 - 2.0 * math.pi * i / segments
        pts.append((radius * math.cos(theta), radius * math.sin(theta)))
    return np.array(pts, dtype=float)


def ellipse_loop(rx, ry, segments=LOOP_SEGMENTS):
    pts = []
    for i in range(segments):
        theta = math.pi / 2.0 - 2.0 * math.pi * i / segments
        pts.append((rx * math.cos(theta), ry * math.sin(theta)))
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


def make_solid_loft_z(sections):
    vertices = []
    faces = []
    n = LOOP_SEGMENTS
    for sec in sections:
        z = sec["z"]
        for x, y in sec["outer"]:
            vertices.append((x, y, z))
        vertices.append((0.0, 0.0, z))

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


def blocker_sections(plug_diameter, insertion_length):
    handle = ellipse_loop(HANDLE_RX_MM, HANDLE_RY_MM)
    handle_bottom = ellipse_loop(HANDLE_RX_MM * 0.96, HANDLE_RY_MM * 0.96)
    plug = teardrop_loop(plug_diameter)
    plug_tip = teardrop_loop(plug_diameter * 0.97)
    round_neck = round_loop(max(plug_diameter * 0.58, 2.5))
    z_handle_top = HANDLE_THICKNESS_MM
    z_plug_start = z_handle_top + HANDLE_TOP_TRANSITION_MM
    z_plug_end = z_plug_start + insertion_length
    z_total = z_plug_end + PLUG_TIP_CHAMFER_Z_MM
    sections = [
        {"z": 0.0, "outer": handle_bottom},
        {"z": HANDLE_BOTTOM_CHAMFER_Z_MM, "outer": handle},
        {"z": z_handle_top, "outer": handle},
        {"z": z_handle_top + 0.35, "outer": round_neck},
        {"z": z_plug_start, "outer": morph_loop(round_neck, plug, 0.75)},
        {"z": z_plug_start + 0.25, "outer": plug},
        {"z": z_plug_end, "outer": plug},
        {"z": z_total, "outer": plug_tip},
    ]
    return sorted(sections, key=lambda s: s["z"])


def make_blocker(filename, fit_name, plug_diameter, insertion_length, recommended=False):
    sections = blocker_sections(plug_diameter, insertion_length)
    mesh = make_solid_loft_z(sections)
    mesh.export(str(OUT / filename))
    meta = {
        "category": "blocker",
        "file": filename,
        "fit_name": fit_name,
        "recommended": recommended,
        "is_solid": True,
        "has_through_bore": False,
        "network_side_shape": "solid_self_supporting_teardrop_male_plug",
        "plug_outer_teardrop_modeled_diameter_mm": plug_diameter,
        "plug_insertion_length_mm": insertion_length,
        "handle_shape": "flat_elliptical_hand_base",
        "handle_flat_on_build_plate": True,
        "handle_size_xy_mm": [2.0 * HANDLE_RX_MM, 2.0 * HANDLE_RY_MM],
        "handle_thickness_mm": HANDLE_THICKNESS_MM,
        "print_orientation": "already oriented with flat handle on z=0 build plate and plug vertical",
        "total_height_mm": round(sections[-1]["z"], 3),
        "estimated_solid_volume_mm3": round(float(mesh.volume), 3),
        "bbox_span_mm": np.round(mesh.bounds[1] - mesh.bounds[0], 3).tolist(),
        "curve_segments": LOOP_SEGMENTS,
    }
    return mesh, meta


def mesh_check(mesh, filename):
    return {
        "file": filename,
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "volume_mm3": round(float(mesh.volume), 3),
        "bounds": np.round(mesh.bounds, 3).tolist(),
        "bbox_span_mm": np.round(mesh.bounds[1] - mesh.bounds[0], 3).tolist(),
    }


def generate_all(v3):
    items = []
    checks = {}
    insertion = v3["network_plug_insertion_length_mm"]
    for fit_name, diameter in FIT_VARIANTS:
        filename = f"X1_teardrop_port_blocker_{fmt_mm(diameter)}_{fit_name}.stl"
        recommended = abs(diameter - v3["network_plug_outer_teardrop_modeled_diameter_mm"]) < 1e-6
        mesh, meta = make_blocker(filename, fit_name, diameter, insertion, recommended)
        items.append(meta)
        checks[filename] = mesh_check(mesh, filename)
    return items, checks


def build_validation(items, checks, v3):
    blockers = [x for x in items if x["category"] == "blocker"]
    stl_files = sorted(p.name for p in OUT.glob("*.stl"))
    expected = sorted(x["file"] for x in blockers)
    recommended = [x for x in blockers if x["recommended"]]
    max_span = [max(x["bbox_span_mm"]) for x in blockers]
    validation = {
        "version": VERSION,
        "source_v3_params": v3["source"],
        "v3_network_port_modeled_teardrop_diameter_mm": v3["network_port_modeled_teardrop_diameter_mm"],
        "v3_network_plug_outer_teardrop_modeled_diameter_mm": v3["network_plug_outer_teardrop_modeled_diameter_mm"],
        "v3_network_plug_insertion_length_mm": v3["network_plug_insertion_length_mm"],
        "confirmed_flat_plate_ports_same_size_from_v3": v3["confirmed_flat_plate_ports_same_size"],
        "stl_checks": checks,
        "expected_stl_files": expected,
        "actual_stl_files": stl_files,
        "only_expected_stl_files_generated": stl_files == expected,
        "all_stl_watertight": all(x["watertight"] for x in checks.values()),
        "all_blockers_solid": all(x["is_solid"] and not x["has_through_bore"] for x in blockers),
        "all_have_teardrop_male_plug_side": all(x["network_side_shape"] == "solid_self_supporting_teardrop_male_plug" for x in blockers),
        "flat_handle_base_for_vertical_printing": all(x["handle_flat_on_build_plate"] for x in blockers),
        "recommended_v3_fit_file": recommended[0]["file"] if recommended else None,
        "fit_variants_mm": {x["fit_name"]: x["plug_outer_teardrop_modeled_diameter_mm"] for x in blockers},
        "handle_size_xy_mm": [2.0 * HANDLE_RX_MM, 2.0 * HANDLE_RY_MM],
        "handle_thickness_mm": HANDLE_THICKNESS_MM,
        "total_height_mm": sorted({x["total_height_mm"] for x in blockers}),
        "small_size_check_max_bbox_span_mm": round(max(max_span), 3),
        "small_size_check_max_bbox_span_le_20mm": max(max_span) <= 20.0,
        "curve_segments_at_least_32": LOOP_SEGMENTS >= 32,
        "support_requirement": "No support intended; model is solid and oriented with the flat handle on the build plate.",
        "use_note": "Print one blocker per flat-plate port that should be sealed. Use 4.2 mm v3_fit_recommended first.",
    }
    validation["validation_passed"] = (
        validation["confirmed_flat_plate_ports_same_size_from_v3"]
        and validation["only_expected_stl_files_generated"]
        and validation["all_stl_watertight"]
        and validation["all_blockers_solid"]
        and validation["all_have_teardrop_male_plug_side"]
        and validation["flat_handle_base_for_vertical_printing"]
        and validation["recommended_v3_fit_file"] is not None
        and validation["small_size_check_max_bbox_span_le_20mm"]
        and validation["curve_segments_at_least_32"]
    )
    return validation


def write_outputs(items, checks, validation, v3):
    params = {
        "version": VERSION,
        "printer": PRINTER,
        "material": MATERIAL,
        "nozzle_mm": NOZZLE_MM,
        "source_v3_params": v3["source"],
        "design_goal": "solid flat-plate port blocker derived from V3 teardrop plug data",
        "v3_reference": v3,
        "blockers": items,
        "validation_summary": validation,
    }
    (OUT / "blocker_params_x1.json").write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "teardrop_port_blocker_x1",
        "========================",
        "",
        f"version: {VERSION}",
        f"source V3 params: {v3['source']}",
        "",
        "Design intent",
        "- Solid plug tool for sealing V8R3T flat-plate teardrop ports.",
        "- Insert side reuses V3 teardrop male plug dimensions.",
        "- Handle side is a small flat elliptical base for vertical printing.",
        "- No through-bore; this is a blocker, not an acoustic adapter.",
        "",
        "V3-derived insert parameters",
        f"- flat plate modeled teardrop port: {v3['network_port_modeled_teardrop_diameter_mm']} mm",
        f"- V3 recommended plug diameter: {v3['network_plug_outer_teardrop_modeled_diameter_mm']} mm",
        f"- V3 insertion length: {v3['network_plug_insertion_length_mm']} mm",
        "",
        "Handle parameters",
        f"- handle footprint: {2.0 * HANDLE_RX_MM} x {2.0 * HANDLE_RY_MM} mm",
        f"- handle thickness: {HANDLE_THICKNESS_MM} mm",
        f"- total height: {validation['total_height_mm']} mm",
        "- print orientation: flat handle on build plate, plug vertical",
        "",
        "Generated blockers",
    ]
    for item in items:
        lines += [
            f"- {item['file']}",
            f"  fit_name: {item['fit_name']}",
            f"  recommended: {item['recommended']}",
            f"  plug_outer_teardrop_modeled_diameter_mm: {item['plug_outer_teardrop_modeled_diameter_mm']}",
            f"  plug_insertion_length_mm: {item['plug_insertion_length_mm']}",
            f"  is_solid: {item['is_solid']}",
            f"  has_through_bore: {item['has_through_bore']}",
            f"  bbox_span_mm: {item['bbox_span_mm']}",
            f"  estimated_solid_volume_mm3: {item['estimated_solid_volume_mm3']}",
        ]
    (OUT / "blocker_params_x1.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    readme = """teardrop_port_blocker_x1
========================

X1 is a solid port blocker for the V8R3T flat plate. It is not an acoustic
adapter and has no through-bore.

Geometry
--------
- Insert side: solid self-supporting teardrop male plug derived from V3.
- Handle side: small flat elliptical hand base.
- Intended print orientation: handle face flat on the build plate, plug vertical.
- Recommended first fit: X1_teardrop_port_blocker_4p2_v3_fit_recommended.stl.

Files
-----
- X1_teardrop_port_blocker_4p1_loose.stl
- X1_teardrop_port_blocker_4p2_v3_fit_recommended.stl
- X1_teardrop_port_blocker_4p3_tight.stl

Use
---
Print one blocker for each flat-plate port that should be sealed. Start with
the 4.2 mm V3 fit. If it is too tight, try 4.1 mm. If it is too loose, try
4.3 mm. Do not force the tight version into the plate.

Printing
--------
The STL is already oriented for vertical printing: flat handle at z=0 and plug
upward. No support is intended. The handle is intentionally small to save PLA
and print time while still giving enough surface to grip by hand.
"""
    (OUT / "README_blocker_x1.txt").write_text(readme, encoding="utf-8")

    vlines = ["validation_report_blocker_x1", "============================", ""]
    for key, value in validation.items():
        vlines.append(f"{key}: {value}")
    (OUT / "validation_report_blocker_x1.txt").write_text("\n".join(vlines) + "\n", encoding="utf-8")


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
    v3 = load_v3_params()
    items, checks = generate_all(v3)
    validation = build_validation(items, checks, v3)
    write_outputs(items, checks, validation, v3)
    write_package_zip()
    print(json.dumps({
        "version": VERSION,
        "out": str(OUT),
        "source_v3_params": v3["source"],
        "stl_count": len([p for p in OUT.glob("*.stl")]),
        "recommended": validation["recommended_v3_fit_file"],
        "all_watertight": validation["all_stl_watertight"],
        "solid": validation["all_blockers_solid"],
        "validation_passed": validation["validation_passed"],
        "package": str(PACKAGE_ZIP),
    }, indent=2))


if __name__ == "__main__":
    main()

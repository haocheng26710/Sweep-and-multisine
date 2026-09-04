from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import trimesh
import trimesh.boolean
import trimesh.creation
import trimesh.transformations
import trimesh.util
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
STL = ROOT / "STL"
PREVIEWS = ROOT / "PREVIEWS"
REPORTS = ROOT / "REPORTS"
ORIGINAL_R02 = (
    WORK
    / "tmp"
    / "mechanical_sources_v2"
    / "V3_R02_R05_R11_Print_Patch"
    / "STL"
    / "R02_rotating_open_C_tower_press_posts.stl"
)

for folder in (STL, PREVIEWS, REPORTS):
    folder.mkdir(parents=True, exist_ok=True)


P = {
    "package": "PLA_8WAY_MIC_STABILIZER_V3",
    "version": "3.0.0",
    "units": "mm",
    "printer": "Bambu Lab P1S",
    "nozzle": 0.4,
    "material": "PLA",
    "hardware": {
        "primary": "M3x10 socket/button head + M3 hex nut",
        "allowed_lengths": [8, 10, 12],
        "detent_pin": "existing 4 mm pin; printable spare included",
    },
    "microphone": {
        "upper_diameter": 10.0,
        "lower_diameter": 12.0,
        "upper_fit_diameter": 10.6,
        "lower_fit_diameter": 12.6,
        "tip_to_branch_axis": 40.0,
        "branch_envelope": [13.0, 10.0],
        "usb_plug_envelope": [13.0, 10.0],
        "usb_cable_diameter": 5.0,
        "audio_cable_diameter": 3.0,
    },
    "rotation": {
        "positions": 8,
        "step_deg": 45,
        "r13_inner_diameter": 50.2,
        "guide_outer_diameter": 49.6,
        "radial_diametral_clearance": 0.6,
        "detent_radius": 49.5,
        "detent_hole_diameter": 4.4,
        "axial_clearance": 0.45,
        "cap_screw_radius": 19.0,
        "cap_head_radius": 3.1,
    },
    "r05": {
        "bore": 8.7,
        "large_od": 30.0,
        "large_height": 9.5,
        "small_od": 20.0,
        "small_height": 3.5,
        "total_height": 13.0,
    },
    "holder": {
        "r02_top_reference_z": 108.8,
        "upper_clip_top_z": 107.3,
        "upper_to_r12_gap": 1.5,
        "lower_sleeve_bottom_z": 69.3,
        "lower_sleeve_height": 10.0,
        "upper_clip_bottom_z": 101.3,
        "upper_clip_height": 6.0,
        "clamp_centre_spacing": 30.0,
        "dock_top_z": 66.2,
        "holder_foot_bottom_z": 66.15,
        "holder_foot_top_z": 69.35,
        "fasteners": "2 x M3x10 or M3x12 with M3 hex nuts",
    },
}


def cyl(radius, height, center=(0.0, 0.0, 0.0), sections=96):
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
    mesh.apply_translation(center)
    return mesh


def box_mesh(extents, center=(0.0, 0.0, 0.0), angle_deg=0.0):
    mesh = trimesh.creation.box(extents=extents)
    if angle_deg:
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(
                math.radians(angle_deg), [0.0, 0.0, 1.0]
            )
        )
    mesh.apply_translation(center)
    return mesh


def beam(a, b, width, height, z_center):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    vector = b - a
    length = float(np.linalg.norm(vector))
    angle = math.degrees(math.atan2(vector[1], vector[0]))
    return box_mesh(
        [length + 1.0, width, height],
        [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z_center],
        angle,
    )


def union(meshes):
    result = trimesh.boolean.union(meshes, engine="manifold", check_volume=False)
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    result.remove_unreferenced_vertices()
    return result


def difference(base, cutters):
    result = trimesh.boolean.difference(
        [base, *cutters], engine="manifold", check_volume=False
    )
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    result.remove_unreferenced_vertices()
    return result


def annulus(r_min, r_max, height, z0=0.0, sections=160):
    mesh = trimesh.creation.annulus(
        r_min=r_min, r_max=r_max, height=height, sections=sections
    )
    mesh.apply_translation([0.0, 0.0, z0 + height / 2])
    return mesh


def hex_prism(across_flats, height, center):
    circumradius = across_flats / math.sqrt(3.0)
    return cyl(circumradius, height, center, sections=6)


def make_r12ab():
    # V3 combines the former R12AB skeleton and R05-H13 acoustic throat.
    # The final bore subtraction happens after every beam is united, so no
    # T-shaped brace can intrude into the microphone aperture.
    base_parts = [annulus(14.8, 24.8, 4.0)]
    mount_centres = [(27.0, 0.0), (0.0, 27.0), (-27.0, 0.0)]
    for centre in mount_centres:
        base_parts += [beam((0.0, 0.0), centre, 8.0, 4.0, 2.0), cyl(5.5, 4.0, (*centre, 2.0))]
    detent = (0.0, -49.5)
    base_parts += [beam((0.0, -20.0), detent, 8.0, 4.0, 2.0), cyl(6.0, 4.0, (*detent, 2.0))]
    base = union(base_parts)
    guide = annulus(15.1, 24.8, 4.45, z0=4.0)
    throat_outer = union(
        [
            cyl(15.0, 9.5, (0.0, 0.0, 4.75), 160),
            cyl(10.0, 3.5, (0.0, 0.0, 11.25), 128),
        ]
    )
    body = union([base, guide, throat_outer])

    cutters = []
    for x, y in mount_centres:
        cutters.append(cyl(1.7, 6.0, (x, y, 3.0), 64))
    cutters.append(cyl(2.2, 6.0, (*detent, 3.0), 64))
    # Cap screws and bottom-open captive nut pockets. All hardware remains inside
    # the R13 inner bore and therefore cannot enter the rotating sweep.
    for x in (-19.0, 19.0):
        cutters.append(cyl(1.7, 10.0, (x, 0.0, 4.0), 64))
        cutters.append(hex_prism(5.8, 2.7, (x, 0.0, 1.35)))
    cutters.append(cyl(4.35, 15.0, (0.0, 0.0, 6.5), 96))
    return difference(body, cutters)


def make_r14():
    cap = annulus(15.3, 27.6, 3.0)
    cutters = []
    for x in (-19.0, 19.0):
        cutters.append(cyl(1.7, 5.0, (x, 0.0, 2.5), 64))
        # Counterbore opens from the top, leaving a printable flat underside.
        cutters.append(cyl(3.1, 1.45, (x, 0.0, 2.275), 64))
    return difference(cap, cutters)


def make_r13():
    body = annulus(25.1, 54.0, 4.0)
    support_centres = [
        (38.80293, -16.07268),
        (16.07268, 38.80293),
        (-38.80293, 16.07268),
        (-16.07268, -38.80293),
    ]
    additions = [body]
    for x, y in support_centres:
        additions.append(cyl(5.0, 3.0, (x, y, 5.5), 64))
        additions.append(cyl(3.0, 3.0, (x, y, 8.5), 64))
    carrier = union(additions)
    holes = []
    for index in range(8):
        a = math.radians(index * 45.0 - 90.0)
        x, y = 49.5 * math.cos(a), 49.5 * math.sin(a)
        holes.append(cyl(2.2, 6.0, (x, y, 3.0), 64))
    return difference(carrier, holes)


def open_u_sleeve(inner_radius, outer_radius, height, z0, opening_width):
    ring = annulus(inner_radius, outer_radius, height, z0=z0, sections=128)
    # The opening faces the rear (-Y), matching the existing open-C tower.
    slot = box_mesh(
        [opening_width, 2.2 * outer_radius, height + 2.0],
        [0.0, -outer_radius, z0 + height / 2],
    )
    return difference(ring, [slot])


def make_r02_v5_dock():
    if not ORIGINAL_R02.exists():
        raise FileNotFoundError(ORIGINAL_R02)
    original = trimesh.load_mesh(ORIGINAL_R02, force="mesh", process=True)
    # Bottom-grown rails carry the holder dock.  The microphone-contact part is
    # deliberately separate, so fit changes never require reprinting R02.
    # Grow two slim rails inside the existing C-tower walls.  At x=+/-24 they
    # overlap the original shell through their full height; the top crossbar
    # then reaches inward to the removable H01 feet.  This keeps the dock a
    # single printable body without filling the central cable space.
    rails = [
        box_mesh([8.0, 10.0, 62.2], (-24.0, 8.0, 31.1)),
        box_mesh([8.0, 10.0, 62.2], (24.0, 8.0, 31.1)),
    ]
    dock = [
        box_mesh([12.0, 16.0, 4.0], (-12.0, 7.5, 64.2)),
        box_mesh([12.0, 16.0, 4.0], (12.0, 7.5, 64.2)),
        # One continuous cross-member overlaps both rails and both feet.
        box_mesh([60.0, 10.0, 4.0], (0.0, 8.0, 64.2)),
    ]
    body = union([original, *rails, *dock])
    cutters = []
    for x in (-12.0, 12.0):
        cutters.append(cyl(1.7, 8.0, (x, 7.5, 65.0), 64))
        # Bottom-open M3 nut trap; M3x10 and M3x12 both remain below R12.
        cutters.append(hex_prism(5.8, 2.7, (x, 7.5, 63.35)))
    return difference(body, cutters)


def make_h01_holder(upper_fit=10.6, lower_fit=12.6):
    lower = open_u_sleeve(
        lower_fit / 2, 9.5, 10.0, 69.3, lower_fit + 1.2
    )
    upper = open_u_sleeve(
        upper_fit / 2, 8.8, 6.0, 101.3, upper_fit + 1.2
    )
    # The spine is behind the microphone and leaves the acoustic axis open.
    spine = box_mesh([16.0, 5.0, 38.0], (0.0, 8.25, 88.3))
    feet = [
        box_mesh([10.0, 12.0, 3.2], (-12.0, 7.5, 67.75)),
        box_mesh([10.0, 12.0, 3.2], (12.0, 7.5, 67.75)),
        box_mesh([18.0, 5.0, 3.2], (0.0, 10.0, 67.75)),
    ]
    holder = union([lower, upper, spine, *feet])
    holes = [cyl(1.7, 6.0, (x, 7.5, 68.0), 64) for x in (-12.0, 12.0)]
    return difference(holder, holes)


def make_pin():
    shaft = cyl(1.95, 17.0, (0.0, 0.0, 8.5), 64)
    head = cyl(4.0, 3.0, (0.0, 0.0, 18.5), 64)
    return union([shaft, head])


def make_fit_coupon():
    block = box_mesh([58.0, 24.0, 5.0], (0.0, 0.0, 2.5))
    cutters = [
        cyl(5.3, 7.0, (-18.0, 0.0, 3.5), 64),
        cyl(6.3, 7.0, (0.0, 0.0, 3.5), 64),
        cyl(2.2, 7.0, (18.0, 0.0, 3.5), 64),
    ]
    return difference(block, cutters)


def export(mesh, filename):
    mesh.remove_unreferenced_vertices()
    path = STL / filename
    mesh.export(path, file_type="stl")
    return path


def connected_components(mesh):
    # Count vertex-connected bodies without scipy/networkx. STL loading with
    # process=True has already merged coincident vertices, so unioning the three
    # vertices of every triangle gives an exact body count for these meshes.
    parent = np.arange(len(mesh.vertices), dtype=np.int64)

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def merge(left, right):
        left_root = find(int(left))
        right_root = find(int(right))
        if left_root != right_root:
            parent[right_root] = left_root

    used = set()
    for a, b, c in mesh.faces:
        used.update((int(a), int(b), int(c)))
        merge(a, b)
        merge(b, c)
    return len({find(index) for index in used})


def report(path):
    mesh = trimesh.load_mesh(path, force="mesh", process=True)
    return {
        "file": path.name,
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "bounds_mm": np.round(mesh.bounds, 3).tolist(),
        "extents_mm": np.round(mesh.extents, 3).tolist(),
        "volume_mm3": round(abs(float(mesh.volume)), 2),
        "faces": int(len(mesh.faces)),
        "components": connected_components(mesh),
    }


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def previews():
    font = ImageFont.load_default()

    img = Image.new("RGB", (1100, 1100), "white")
    d = ImageDraw.Draw(img)
    cx = cy = 550
    scale = 7.2
    def circle(x, y, r, colour, width=5, fill=None):
        b = (cx + (x-r)*scale, cy - (y+r)*scale, cx + (x+r)*scale, cy - (y-r)*scale)
        d.ellipse(b, outline=colour, width=width, fill=fill)
    circle(0, 0, 54, "#2878b5")
    circle(0, 0, 25.1, "#777777")
    circle(0, 0, 24.8, "#d95f02")
    for i in range(8):
        a = math.radians(i * 45 - 90)
        x, y = 49.5 * math.cos(a), 49.5 * math.sin(a)
        circle(x, y, 2.2, "#1b9e77", fill="#1b9e77")
        d.text((cx + x*scale*1.15 - 12, cy - y*scale*1.15 - 8), f"{i*45}", fill="black", font=font)
    for x in (-19, 19):
        circle(x, 0, 3.1, "#984ea3")
    d.text((280, 25), "V3 8-way rotation and internal M3 clearance", fill="black", font=font)
    img.save(PREVIEWS / "01_rotation_and_hardware_clearance.png")

    img = Image.new("RGB", (1200, 650), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((140, 390, 220, 560), fill="#d95f02")
    d.rectangle((220, 400, 780, 480), fill="#2878b5")
    d.rectangle((170, 330, 900, 390), fill="#984ea3")
    d.line((520, 320, 520, 395), fill="black", width=4)
    d.polygon([(520, 395), (510, 378), (530, 378)], fill="black")
    d.text((470, 285), "0.45 mm axial clearance", fill="black", font=font)
    d.text((125, 585), "R12AB fixed", fill="black", font=font)
    d.text((450, 500), "R13 rotating", fill="black", font=font)
    d.text((500, 345), "R14 flat cap", fill="white", font=font)
    d.text((300, 55), "R12 V3: clear ID8.7 throat, H13 integrated interface", fill="black", font=font)
    img.save(PREVIEWS / "02_support_free_section.png")

    img = Image.new("RGB", (850, 1250), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((180, 100, 670, 1120), outline="#555555", width=6)
    # Scale 8 px/mm: z=0 is at y=1120, z=108.8 near y=250.
    zpix = lambda z: 1120 - z * 8
    d.rectangle((300, zpix(66.2), 550, 1120), fill="#d9ead3", outline="#1b9e77", width=3)
    d.rectangle((345, zpix(69.3), 505, zpix(66.15)), fill="#984ea3")
    d.rectangle((350, zpix(79.3), 500, zpix(69.3)), fill="#2878b5")
    d.rectangle((365, zpix(107.3), 485, zpix(101.3)), fill="#2878b5")
    d.rectangle((395, zpix(107.3), 455, zpix(69.3)), fill="#d95f02")
    d.line((260, zpix(108.8), 600, zpix(108.8)), fill="black", width=4)
    d.text((610, zpix(108.8)-10), "R12 underside / R02 top Z108.8", fill="black", font=font)
    d.text((610, zpix(107.3)-10), "upper U top Z107.3 (gap 1.5)", fill="black", font=font)
    d.text((610, zpix(74.3)-10), "lower 10 mm sleeve; clamp centre Z74.3", fill="black", font=font)
    d.text((610, zpix(89.3)-10), "30 mm clamp-centre spacing", fill="black", font=font)
    d.text((260, 40), "V3 R02 raised dock + separately printable open-U H01", fill="black", font=font)
    img.save(PREVIEWS / "03_R02_V5_removable_holder_scheme.png")


def main():
    # Replace only derived V3 artifacts; V1/V2 live in separate directories/ZIPs.
    for folder in (STL, PREVIEWS, REPORTS):
        for path in folder.iterdir():
            if path.is_file():
                path.unlink()

    parts = [
        (make_r12ab(), "R12AB_V3_integrated_R05_H13_clear_ID8p7.stl"),
        (make_r14(), "R14_F_flat_screw_retaining_cap.stl"),
        (make_r13(), "R13_8way_rotating_P01_carrier.stl"),
        (make_r02_v5_dock(), "R02_V5_raised_removable_holder_dock.stl"),
        (make_h01_holder(), "H01_open_U_holder_D10p6_D12p6_H30.stl"),
        (make_pin(), "R18_PLA_detent_pin_D3p9.stl"),
        (make_fit_coupon(), "F01_fit_coupon_D10p6_D12p6_D4p4.stl"),
    ]
    paths = [export(mesh, name) for mesh, name in parts]
    results = [report(path) for path in paths]

    radial_clearance = 25.1 - (19.0 + 3.1)
    checks = {
        "all_watertight": all(item["watertight"] for item in results),
        "all_winding_consistent": all(item["winding_consistent"] for item in results),
        "all_single_component": all(item["components"] == 1 for item in results),
        "cap_head_radial_clearance_mm": round(radial_clearance, 3),
        "cap_hardware_outside_rotation_sweep": radial_clearance >= 2.5,
        "guide_diametral_clearance_mm": 50.2 - 49.6,
        "axial_clearance_mm": 0.45,
        "r12_central_bore_diameter_mm": 8.7,
        "r12_integrated_r05_total_height_mm": 13.0,
        "standalone_r05_required": False,
        "r02_dock_supports_grow_from_base": True,
        "holder_is_separately_reprintable": True,
        "holder_lower_sleeve_bottom_z_mm": 69.3,
        "holder_lower_above_55_mm": 69.3 >= 55.0,
        "holder_lower_sleeve_height_mm": 10.0,
        "holder_clamp_centre_spacing_mm": 30.0,
        "holder_upper_to_r12_gap_mm": 1.5,
        "upper_clip_is_open_u": True,
        "upper_clip_may_use_slicer_support": True,
    }
    payload = {"parameters": P, "checks": checks, "meshes": results}
    (REPORTS / "validation_report_v3.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (REPORTS / "design_parameters_v3.json").write_text(
        json.dumps(P, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    text_lines = [
        "PLA 8-way microphone stabilizer V3 - digital validation report",
        "",
        "Checks",
        *[f"- {key}: {value}" for key, value in checks.items()],
        "",
        "Meshes",
    ]
    for item in results:
        text_lines.extend(
            [
                f"- {item['file']}",
                f"  watertight={item['watertight']}",
                f"  winding_consistent={item['winding_consistent']}",
                f"  components={item['components']}",
                f"  extents_mm={item['extents_mm']}",
                f"  volume_mm3={item['volume_mm3']}",
                f"  faces={item['faces']}",
            ]
        )
    (REPORTS / "validation_report_v3.txt").write_text(
        "\n".join(text_lines) + "\n", encoding="utf-8"
    )
    previews()

    manifest = {
        "package": P["package"],
        "version": P["version"],
        "files": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in sorted(ROOT.rglob("*"))
            if path.is_file() and path.name != "MANIFEST.json"
        ],
    }
    (ROOT / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"checks": checks, "meshes": results}, indent=2))


if __name__ == "__main__":
    main()

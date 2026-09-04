from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Polygon, Rectangle, Wedge


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REPORT = ROOT / "docs/progress/COMSOL_3A_P04T0_PRINTABLE_INSERT_PREFLIGHT.md"
RADIUS = 18.0
HEIGHT = 9.2
WIDTH = 13.42333744142368
MIC_WELL_RADIUS = 4.5
EXPECTED_INSERT_VOLUME = 2341.114845455112


def _circle_antiderivative(x: float, radius: float) -> float:
    return 0.5 * (x * math.sqrt(max(0.0, radius * radius - x * x)) + radius * radius * math.asin(x / radius))


def frozen_geometry() -> dict:
    half = WIDTH / 2.0
    xmax = math.sqrt(RADIUS * RADIUS - half * half)
    removed_quadrant_area = (_circle_antiderivative(xmax, RADIUS) - _circle_antiderivative(half, RADIUS)) - half * (xmax - half)
    disk_area = math.pi * RADIUS * RADIUS
    insert_area = 4.0 * removed_quadrant_area
    remaining_area = disk_area - insert_area
    return {
        "radius_mm": RADIUS,
        "height_mm": HEIGHT,
        "corridor_width_mm": WIDTH,
        "disk_area_mm2": disk_area,
        "remaining_air_area_mm2": remaining_area,
        "insert_area_mm2": insert_area,
        "remaining_air_volume_mm3": remaining_area * HEIGHT,
        "insert_volume_mm3": insert_area * HEIGHT,
        "remaining_fraction": remaining_area / disk_area,
        "target_insert_volume_mm3": EXPECTED_INSERT_VOLUME,
    }


def clearance_invariants() -> dict:
    half = WIDTH / 2.0
    return {
        "insert_connected_component_count": 4,
        "insert_intersects_retained_cross": False,
        "insert_intersects_microphone_well": False,
        "insert_intersects_fixed_channel_mouths": False,
        "minimum_planar_clearance_to_mic_well_mm": math.sqrt(2.0) * half - MIC_WELL_RADIUS,
        "cross_margin_beyond_fixed_channel_each_side_mm": half - 4.0,
        "full_cross_margin_beyond_fixed_channel_width_mm": WIDTH - 8.0,
    }


def z_stack() -> dict:
    return {
        "p01_bottom_z_mm": 0.0,
        "air_bottom_z_mm": 3.0,
        "microphone_tip_nominal_z_mm": 7.0,
        "air_top_z_mm": 12.2,
        "p02_underside_z_mm": 12.2,
        "insert_nominal_height_mm": 9.2,
        "unallocated_z_clearance_mm": 0.0,
    }


def _read_binary_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"Invalid STL: {path}")
    count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + count * 50
    if expected != len(data):
        raise ValueError(f"Only audited binary STL is supported: {path}")
    records = np.frombuffer(data, dtype=np.dtype([
        ("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attr", "<u2")
    ]), offset=84, count=count)
    return records["vertices"].astype(np.float64)


def audit_reference_stls(reference_dir: Path) -> list[dict]:
    specs = {
        "P01": "P01_universal_8slot_base.stl",
        "P02": "P02_main_lid_with_captive_nut_traps.stl",
        "P03": "P03_mic_insert_ID9_0_for_Dayton_iMM6C.stl",
    }
    rows = []
    for part, name in specs.items():
        path = reference_dir / name
        triangles = _read_binary_stl(path)
        flat = triangles.reshape(-1, 3)
        lo = flat.min(axis=0)
        hi = flat.max(axis=0)
        ext = hi - lo
        v0, v1, v2 = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1).sum()
        signed_volume = np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0
        expected_z = {"P01": 12.2, "P02": 5.0, "P03": 6.5}[part]
        rows.append({
            "part": part,
            "file": name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "triangle_count": int(len(triangles)),
            "min_x": float(lo[0]), "min_y": float(lo[1]), "min_z": float(lo[2]),
            "max_x": float(hi[0]), "max_y": float(hi[1]), "max_z": float(hi[2]),
            "extent_x": float(ext[0]), "extent_y": float(ext[1]), "extent_z": float(ext[2]),
            "surface_area_mm2": float(area),
            "absolute_signed_volume_mm3": float(abs(signed_volume)),
            "units_inference": "mm" if math.isclose(float(ext[2]), expected_z, abs_tol=1e-5) else "unresolved",
            "units_basis": f"STL is unitless; z extent matches authoritative {part} CAD dimension {expected_z} mm",
        })
    return rows


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows:
        raise ValueError("CSV requires rows")
    names = fieldnames or list(rows[0])
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


def _insert_polygons(samples: int = 181) -> list[np.ndarray]:
    half = WIDTH / 2.0
    theta0 = math.asin(half / RADIUS)
    theta1 = math.acos(half / RADIUS)
    angles = np.linspace(theta0, theta1, samples)
    base = np.vstack([
        np.array([[half, half]]),
        np.c_[RADIUS * np.cos(angles), RADIUS * np.sin(angles)],
        np.array([[half, half]]),
    ])
    shapes = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        shapes.append(base * np.array([sx, sy]))
    return shapes


def _save_figures() -> list[str]:
    names = []
    half = WIDTH / 2.0

    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    for poly in _insert_polygons():
        ax.add_patch(Polygon(poly, facecolor="#d95f02", alpha=0.68, edgecolor="black"))
    ax.add_patch(Circle((0, 0), RADIUS, fill=False, lw=2, color="black"))
    ax.add_patch(Rectangle((-RADIUS, -half), 2 * RADIUS, WIDTH, color="#56B4E9", alpha=.32))
    ax.add_patch(Rectangle((-half, -RADIUS), WIDTH, 2 * RADIUS, color="#56B4E9", alpha=.32))
    ax.add_patch(Circle((0, 0), MIC_WELL_RADIUS, fill=False, lw=2, color="#0072B2"))
    ax.text(0, 0, "mic well\nØ9", ha="center", va="center", fontsize=9)
    ax.set(title="P04E 75% frozen plan geometry — nominal CAD preflight", xlabel="x (mm)", ylabel="y (mm)", aspect="equal", xlim=(-20, 20), ylim=(-20, 20))
    ax.grid(alpha=.2)
    fig.tight_layout(); name = "figure_01_frozen_topology.png"; fig.savefig(HERE / name, dpi=220); plt.close(fig); names.append(name)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.add_patch(Rectangle((-24, 0), 48, 3, color="#777777", alpha=.65, label="P01 floor"))
    ax.add_patch(Rectangle((-24, 12.2), 48, 3.2, color="#444444", alpha=.75, label="P02 plate"))
    ax.add_patch(Rectangle((-10, -3), 20, 3, color="#009E73", alpha=.7, label="P03 flange"))
    ax.add_patch(Rectangle((-10, 0), 20, 3.5, fill=False, edgecolor="#009E73", lw=2, label="P03 neck/ridge, nominal installed"))
    ax.plot([0, 0], [0, 7], color="#CC79A7", lw=7, label="mic front, nominal")
    ax.annotate("no spare Z layer", xy=(20, 12.2), xytext=(8, 9.5), arrowprops=dict(arrowstyle="->"))
    ax.annotate("measure possible 0.5 mm\nP03 floor protrusion", xy=(10, 3.25), xytext=(12, 6.2), arrowprops=dict(arrowstyle="->", color="#009E73"), fontsize=8)
    ax.axhspan(3, 12.2, color="#56B4E9", alpha=.12, label="frozen air height 9.2")
    ax.set(xlim=(-25, 25), ylim=(-3.5, 16), xlabel="section coordinate (mm)", ylabel="global z (mm)", title="P01–P02–P03 Z stack — nominal CAD preflight")
    ax.legend(loc="upper left", ncol=2, fontsize=8); ax.grid(alpha=.2)
    fig.tight_layout(); name = "figure_02_z_stack_section.png"; fig.savefig(HERE / name, dpi=220); plt.close(fig); names.append(name)

    fig, ax = plt.subplots(figsize=(9, 5.3))
    labels = ["A\nsingle carrier", "B\nP02-carried lobes", "C\nfour located pieces"]
    metrics = np.array([[0, 1, 1], [1, 0, 1], [1, 0, 1], [0, 0, 1]], dtype=float)
    im = ax.imshow(metrics, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(3), labels); ax.set_yticks(range(4), ["frozen-air fidelity", "single removable object", "no P01/P02 modification", "zero unresolved fit inputs"])
    for i in range(4):
        for j in range(3): ax.text(j, i, "yes" if metrics[i, j] else "no", ha="center", va="center", weight="bold")
    ax.set_title("Mechanical candidate gate — nominal CAD preflight")
    fig.tight_layout(); name = "figure_03_candidate_trade_study.png"; fig.savefig(HERE / name, dpi=220); plt.close(fig); names.append(name)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axis("off")
    boxes = [(0.03, .68, .25, .20, "1. P01 chamber ID\nactual radial fit"), (0.375, .68, .25, .20, "2. floor → lid underside\nactual clamp height"), (.72, .68, .25, .20, "3. P03/mic protrusion\nactual central clearance"), (.375, .22, .25, .20, "freeze printable tolerance\nand assembly clearance")]
    for x, y, w, h, txt in boxes:
        ax.add_patch(Rectangle((x, y), w, h, facecolor="#E6F2FF", edgecolor="#0072B2", lw=1.7)); ax.text(x+w/2, y+h/2, txt, ha="center", va="center", fontsize=10)
    for x in (.155, .50, .845): ax.annotate("", xy=(.50, .43), xytext=(x, .68), arrowprops=dict(arrowstyle="->", color="#555555"))
    ax.text(.5, .08, "Until all three are known, final STL dimensions cannot be frozen safely.", ha="center", fontsize=11, weight="bold")
    ax.set_title("Minimal physical-measurement dependency — nominal CAD preflight", fontsize=14)
    fig.tight_layout(); name = "figure_04_measurement_dependency.png"; fig.savefig(HERE / name, dpi=220); plt.close(fig); names.append(name)

    fig, ax = plt.subplots(figsize=(9.5, 6))
    ax.add_patch(Circle((0, 0), 18, fill=False, lw=2, color="black"))
    for i, poly in enumerate(_insert_polygons(), start=1):
        ax.add_patch(Polygon(poly, facecolor="#E69F00", alpha=.62, edgecolor="black")); c = poly.mean(axis=0); ax.text(c[0], c[1], f"L{i}", ha="center", va="center", weight="bold")
    for angle in (0, 90, 180, 270):
        a = math.radians(angle); ax.arrow(18*math.cos(a), 18*math.sin(a), 8*math.cos(a), 8*math.sin(a), width=.25, head_width=1.4, color="#0072B2", length_includes_head=True)
    ax.add_patch(Circle((0, 0), 4.5, facecolor="#CC79A7", alpha=.45, edgecolor="black"))
    ax.text(0, 0, "P03/mic", ha="center", va="center", fontsize=8)
    ax.text(0, 29, "P02 removed → four lobes inserted from above → P02 clamps", ha="center", fontsize=10)
    ax.set(xlim=(-31,31), ylim=(-22,32), aspect="equal", title="Recommended C assembly access — nominal CAD preflight", xlabel="x (mm)", ylabel="y (mm)")
    ax.grid(alpha=.2)
    fig.tight_layout(); name = "figure_05_assembly_access.png"; fig.savefig(HERE / name, dpi=220); plt.close(fig); names.append(name)
    return names


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate() -> None:
    HERE.mkdir(parents=True, exist_ok=True)
    geometry = frozen_geometry()
    clearances = clearance_invariants()
    stack = z_stack()
    stls = audit_reference_stls(HERE / "reference_stl")

    audit = {
        "phase_id": "P04T0_PRINTABLE_INSERT_PREFLIGHT",
        "scope": "mechanical CAD preflight only; no COMSOL and no printable insert STL",
        "classification": "P04T0 BLOCKED — PHYSICAL_MEASUREMENTS_REQUIRED",
        "recommended_form": "C — four independent, positively identified pieces clamped between P01 and P02",
        "p04s_correction": "The P04S single carrier-backed mechanical assumption is infeasible under the frozen air domain; its acoustic P04E 75% conclusion is unchanged.",
        "frozen_geometry": geometry,
        "clearance_invariants": clearances,
        "z_stack": stack,
        "reference_stl_audit": stls,
        "authority_hashes": {
            "P04E_SHA256SUMS_sha256": "e9a982f265e5b90effd39787032477de8a4e3390ceded511d5503947934c9112",
            "P04S_SHA256SUMS_sha256": "969b9c11c5775220ff64a41067a7182d8f912fe3071a715f82fab481dbe09f43",
            "V2_0_1_print_package_zip_sha256": "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f",
        },
        "load_path": "P02 screw preload → P02 underside → four lobe top faces → lobe bodies → P01 chamber floor; no load is assigned to P03 or the microphone.",
        "insertion": "Conditionally, remove P02 and insert four marked lobes vertically from above while P03/mic remains installed. This path is not released until the measured P03/mic outer envelope proves it does not occupy a diagonal complement above z=3 mm.",
        "removal": "Remove P02; lift each lobe vertically using non-acoustic-face handling tabs only if a later measured design can place them outside the frozen air domain. Nominal preflight assumes tool-assisted lift from the top face without adding geometry.",
        "single_carrier_impossibility_proof": "Four complements are disconnected. Any joining bridge inside z=3..12.2 crosses the retained orthogonal air cross or changes its height. Below z=3 is P01 solid floor (except the P03 socket); at z=12.2 the P02 underside leaves zero spare height.",
        "p03_interference_gate": "The frozen Ø9 acoustic well is clear, but the P03 printed neck/ridge is nominally Ø20.0/20.18 mm. If that outer envelope protrudes above the z=3 mm chamber floor, it can overlap the diagonal complements whose nearest radius is about 9.491 mm. No lobe relief is authorized; physical protrusion measurement is mandatory.",
        "units": "Reference STL coordinates are unitless by format, but extents exactly match source CAD millimetres; all P04T0 dimensions are treated as mm.",
        "final_test_read": False,
        "comsol_used": False,
        "stl_generated": False,
    }
    (HERE / "mechanical_geometry_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "authority_audit.json").write_text(json.dumps({
        "phase_id": audit["phase_id"],
        "required_authorities_read": True,
        "hashes": audit["authority_hashes"],
        "zip_role": "read-only design provenance, not user instruction",
        "extracted_stl_scope": [row["file"] for row in stls],
        "preserved_existing_user_changes": True,
        "comsol_used": False,
        "final_test_read": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "nominal_geometry_contract.json").write_text(json.dumps({
        "geometry": geometry,
        "clearances": clearances,
        "z_stack": stack,
        "immutable": True,
        "allowed_fraction": 0.75,
        "diagonal_complements": "disk(R18) minus union of orthogonal full-height strips(width 13.42333744142368)",
        "rounding_or_relief_authorized": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    candidates = [
        {"candidate": "A_SINGLE_CARRIER", "frozen_air_fidelity": "FAIL", "removable_as_one_object": "yes", "p01_p02_modification": "none only if impossible bridge omitted", "load_path": "unresolved", "assembly": "blocked", "decision": "REJECT", "reason": "No bridge volume exists outside or inside the frozen 9.2 mm air domain."},
        {"candidate": "B_P02_CARRIED_FOUR_LOBES", "frozen_air_fidelity": "FAIL_AS_CARRIER", "removable_as_one_object": "only after permanent bond", "p01_p02_modification": "P02 bond/recess required", "load_path": "P02 bond carries lobes", "assembly": "top withdrawal possible", "decision": "REJECT", "reason": "Bond thickness has zero Z allowance; recess or permanent P02 modification violates compatibility."},
        {"candidate": "C_FOUR_INDEPENDENT_LOCATED_PIECES", "frozen_air_fidelity": "PASS_NOMINAL", "removable_as_one_object": "no", "p01_p02_modification": "none", "load_path": "P02 clamp to P01 floor", "assembly": "four vertical placements", "decision": "RECOMMEND_PENDING_MEASUREMENTS", "reason": "Only topology that preserves all four disconnected complements without extra acoustic solid."},
    ]
    _write_csv(HERE / "candidate_carrier_trade_study.csv", candidates)
    _write_csv(HERE / "carrier_option_comparison.csv", candidates)

    fit_rows = [
        {"interface": "lobe outer arc / P01 chamber wall", "nominal_cad_mm": "R18.0", "print_allowance_mm": "UNFROZEN", "evidence": "source CAD + P01 STL", "risk": "binding or leak", "status": "MEASURE"},
        {"interface": "lobe height / P01 floor–P02 underside", "nominal_cad_mm": "9.2", "print_allowance_mm": "UNFROZEN", "evidence": "source CAD + P01/P02 STL", "risk": "lid cannot seat or lobe rattles", "status": "MEASURE"},
        {"interface": "lobe inner corner / P03 microphone envelope", "nominal_cad_mm": f"plan clearance {clearances['minimum_planar_clearance_to_mic_well_mm']:.6f}", "print_allowance_mm": "UNFROZEN", "evidence": "P03 STL; microphone itself not in package", "risk": "contact with protruding microphone/seal", "status": "MEASURE"},
        {"interface": "lobe straight edges / retained cross", "nominal_cad_mm": WIDTH, "print_allowance_mm": "must be inward-only after measurements", "evidence": "P04E frozen geometry", "risk": "blocks four fixed channel mouths", "status": "GEOMETRY_PASS"},
        {"interface": "P02 bond layer", "nominal_cad_mm": "0.0 available", "print_allowance_mm": "none", "evidence": "exact Z stack", "risk": "changes acoustic height", "status": "B_REJECT"},
    ]
    _write_csv(HERE / "fit_and_clearance_budget.csv", fit_rows)

    mic_rows = [
        {"item": "central acoustic microphone well", "frozen_keepout": "Ø9.0 mm disk", "nominal_result": "clear against frozen well", "minimum_clearance_mm": f"{clearances['minimum_planar_clearance_to_mic_well_mm']:.9f}", "physical_uncertainty": "does not bound P03 outer neck", "status": "PASS_ACOUSTIC_KEEP_OUT_ONLY"},
        {"item": "P03 printed outer neck/ridge", "frozen_keepout": "nominal Ø20.0/20.18 mm below/at floor", "nominal_result": "possible shallow overlap if protruding above z=3", "minimum_clearance_mm": "nearest lobe radius 9.491 mm vs ridge radius 10.09 mm", "physical_uncertainty": "actual installed protrusion", "status": "BLOCKING_MEASUREMENT"},
        {"item": "0°/90°/180°/270° fixed channel mouths", "frozen_keepout": "8.0 mm channel width", "nominal_result": "clear", "minimum_clearance_mm": f"{clearances['cross_margin_beyond_fixed_channel_each_side_mm']:.9f} each side", "physical_uncertainty": "printed wall/edge deviation", "status": "NOMINAL_PASS"},
        {"item": "nearest screw bosses", "frozen_keepout": "boss centres r26 mm", "nominal_result": "outside r18 chamber", "minimum_clearance_mm": "source topology separates boss field from chamber", "physical_uncertainty": "none relevant inside chamber", "status": "PASS"},
        {"item": "P11 seals and P08B pads", "frozen_keepout": "sector/module solid tops", "nominal_result": "outside central chamber", "minimum_clearance_mm": "not in chamber footprint", "physical_uncertainty": "compression changes lid seating height", "status": "HEIGHT_MEASURE"},
    ]
    _write_csv(HERE / "mic_and_channel_clearance_audit.csv", mic_rows)
    interference_rows = [
        {"part_or_interface": "P01 chamber wall", "nominal_relation": "R18 outer arc shared", "z_range_mm": "3.0..12.2", "interference": "fit-dependent", "action": "measure chamber ID"},
        {"part_or_interface": "P01 chamber floor", "nominal_relation": "four lobes rest at z=3", "z_range_mm": "3.0", "interference": "none nominal", "action": "measure assembled height"},
        {"part_or_interface": "P02 underside", "nominal_relation": "flush at z=12.2; no spare bond layer", "z_range_mm": "12.2", "interference": "height-dependent", "action": "measure floor-to-underside"},
        {"part_or_interface": "P03 outer neck/ridge", "nominal_relation": "Ø20.0/20.18 may exceed nearest-lobe radius 9.491", "z_range_mm": "near chamber floor", "interference": "possible and blocking", "action": "measure installed protrusion; do not relieve lobes"},
        {"part_or_interface": "microphone front", "nominal_relation": "Ø8.8 to z≈7 within retained cross", "z_range_mm": "to about 7.0", "interference": "none with exact complements", "action": "include seal in protrusion measurement"},
        {"part_or_interface": "four fixed channel mouths", "nominal_relation": "8×9.2 inside width-13.423 cross", "z_range_mm": "3.0..12.2", "interference": "none nominal", "action": "preserve exact straight edges"},
        {"part_or_interface": "screw bosses / P11 / P08B", "nominal_relation": "outside central chamber footprint", "z_range_mm": "assembly stack", "interference": "no planar collision; affects clamp height", "action": "retain existing stack"},
    ]
    _write_csv(HERE / "p01_p02_p03_interference_audit.csv", interference_rows)

    measurements = [
        {"priority": 1, "measurement": "P01 printed central-chamber internal diameter", "method": "caliper at two orthogonal axes near floor and near top; report minimum", "needed_for": "radial clearance and removal fit", "blocking": "yes"},
        {"priority": 2, "measurement": "P01 chamber floor to installed P02 underside", "method": "depth gauge or calibrated feeler stack with P11/P08B and normal screw torque", "needed_for": "clamp height without changing 9.2 mm air height", "blocking": "yes"},
        {"priority": 3, "measurement": "maximum installed P03/microphone/seal protrusion into chamber", "method": "depth gauge from P01 chamber floor datum; include removable sealing material", "needed_for": "central keepout and safe insertion", "blocking": "yes"},
    ]
    _write_csv(HERE / "measurement_requirements.csv", measurements)
    _write_csv(HERE / "required_physical_measurements.csv", measurements)

    assembly = """# P04T0 nominal assembly sequence (not a print authorization)\n\n1. Keep P03 and the microphone in the frozen P03 installation; verify its actual protrusion before any insert STL is frozen.\n2. Remove P02 only. Do not modify P01, P02, P03, the four fixed channels, P11 or P08B.\n3. Identify the four eventual pieces L1–L4 outside acoustic faces; match each to its diagonal quadrant.\n4. Lower each piece vertically into the corresponding P04E diagonal complement. Never force it past the microphone or channel mouth.\n5. Confirm all four straight edges remain outside the orthogonal retained-air cross and the central Ø9 mm keepout remains open.\n6. Refit P02; tighten the existing M3 pattern diagonally in three stages. The intended load path is P02 → four top faces → P01 floor.\n7. For removal, release P02 and lift pieces vertically one by one. Do not pry against P03 or fixed-channel edges.\n\nThis sequence is nominal CAD reasoning only. The three physical measurements in `measurement_requirements.csv` are a hard gate before dimensional tolerances or printable geometry are frozen.\n"""
    (HERE / "assembly_sequence.md").write_text(assembly, encoding="utf-8")
    (HERE / "assembly_path_audit.json").write_text(json.dumps({
        "status": "CONDITIONAL_ON_MEASUREMENTS",
        "opening_direction": "remove P02 upward; insert/remove each lobe vertically from above",
        "p03_removal_required": False,
        "p03_collision_gate": "installed outer envelope must not enter diagonal complements above z=3 mm",
        "load_path": audit["load_path"],
        "motion_or_tilt_risk": "controlled by measured clamped height and chamber-wall location; unresolved until measurements",
        "seal_requirement": "no new gasket authorized; any added gasket/bond changes frozen height",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    coupon = """# Fit-coupon specification only\n\nNo coupon STL is generated in P04T0. After the three blocking measurements are recorded, use one small sacrificial coupon that reproduces: (1) a short R18 chamber-wall arc, (2) one straight edge from the width-13.42333744142368 mm cross boundary, and (3) the measured clamped height datum. It must not be treated as an acoustic insert or introduce alternative fractions. Print it in the same orientation, material, nozzle and layer settings intended for the eventual four pieces. The coupon should answer radial sliding fit and clamped-height fit only; it must not be used to relax the frozen P04E air geometry.\n"""
    (HERE / "fit_coupon_spec.md").write_text(coupon, encoding="utf-8")
    (HERE / "printability_checks.json").write_text(json.dumps({
        "status": "NOMINAL_SHAPE_PRINTABLE_BUT_DIMENSIONS_BLOCKED",
        "printer": "Bambu P1S",
        "nozzle_mm": 0.4,
        "material": "PLA",
        "layer_height_mm": 0.2,
        "orientation": "each candidate lobe flat on its z=3 face",
        "bed_fit": "pass; each lobe is contained within an R18 footprint",
        "minimum_load_path_thickness": "greater than 1.6 mm nominal; solid lobe radial depth exceeds 8 mm",
        "unsupported_overhang": "none nominal; walls are vertical when printed flat",
        "sharp_internal_corner": "printable, but compensation cannot be frozen without measurements/coupon",
        "final_stl_authorized": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    figures = _save_figures()
    decision = {
        "classification": "P04T0 BLOCKED — PHYSICAL_MEASUREMENTS_REQUIRED",
        "mechanical_form_if_unblocked": "C_FOUR_INDEPENDENT_LOCATED_PIECES",
        "single_carrier_feasible": False,
        "p02_carried_four_lobes_feasible_without_modification": False,
        "nominal_four_piece_geometry_feasible": "conditional; topology and access pass, P03 outer-neck bottom interference remains unresolved",
        "why_blocked": "Actual chamber ID, clamped height, and P03/microphone protrusion are required to freeze printable clearances and exclude P03 overlap safely.",
        "p04s_acoustic_conclusion_changed": False,
        "p04s_mechanical_assumption_changed": True,
        "final_test_read": False,
        "next_stage_authorized": False,
    }
    (HERE / "terminal_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = f"""# P04T0 — P04E 75% 插入件机械 CAD 预检\n\n## 正式分类\n\n`P04T0 BLOCKED — PHYSICAL_MEASUREMENTS_REQUIRED`\n\n名义 CAD 已证明四件式是唯一可能忠实实现 P04E 75% 的候选拓扑，但 P03 外颈在腔底附近的实际突出量尚未确定，因此尚不能宣告机械通过或冻结打印公差。推荐机械形式为 **C — four independent located pieces**（条件性推荐）。\n\n## 关键结论\n\n- 单一 carrier 不可行：四个补集在平面内互不连通；任何位于 `z=3..12.2 mm` 的桥都会侵入保留的正交空气十字。`z<3 mm` 是 P01 实体底板，`z=12.2 mm` 又与 P02 下表面重合，隐藏桥接层的可用高度为 0。\n- P02-carried four lobes 不应采用：要让四叶随 P02 成为一个部件，必须粘接、开槽或永久改造 P02；真实粘接层也没有 Z 余量。\n- 四件式是唯一候选方向：四叶可从上方装入并由 P02 压紧且不遮挡固定通道；但 P03 外颈/凸环若实际高出腔底，可能与四叶内角发生浅层干涉，必须先测量，不能通过削缺四叶规避。\n- P04S 的声学结论不变；只更正“single carrier-backed insert”的机械假设。\n\n## 冻结几何复核\n\n- 中央腔：R18 mm，空气高度 9.2 mm，`z=3..12.2 mm`。\n- 保留十字宽：13.42333744142368 mm。\n- 剩余空气比例：{geometry['remaining_fraction']:.16f}。\n- 插入体积：{geometry['insert_volume_mm3']:.12f} mm³（目标 {EXPECTED_INSERT_VOLUME:.12f} mm³）。\n- 四个插入叶与 Ø9 mm 中央井的名义最小平面间距：{clearances['minimum_planar_clearance_to_mic_well_mm']:.6f} mm；该数值不代表对 Ø20/20.18 mm P03 外颈的净空。\n- 每侧相对 8 mm 固定通道的十字余量：{clearances['cross_margin_beyond_fixed_channel_each_side_mm']:.6f} mm。\n\n## 装配与载荷路径\n\n条件满足后，载荷路径为 P02 螺钉预紧 → P02 下表面 → 四叶顶面 → 四叶实体 → P01 腔底，P03 和麦克风不承载。拆下 P02 后四叶逐件垂直装入/取出；禁止撬压麦克风或固定通道边缘。\n\n## 实体测量硬门禁\n\n1. P01 打印件中央腔实际内径（两轴、上下位置，取最小值）。\n2. 按正常 P11/P08B 与锁紧状态装配后的 P01 腔底到 P02 下表面高度。\n3. 安装密封材料后 P03/麦克风进入中央腔的最大突出量，并确认 Ø20/20.18 mm 外颈是否高出 `z=3 mm` 腔底。\n\n只有这三项数据齐全后，才能冻结径向间隙、高度压紧量与中心避让；本轮不生成 STL。\n\n## 参考 STL 与单位\n\n仅从冻结 ZIP 提取了 P01/P02/P03 三件至本任务 `reference_stl/`。STL 格式本身无单位；其 Z 包围盒分别精确匹配 12.2、5.0、6.5 的源 CAD 尺寸，因此本审计按 mm 解释。\n\n## 图件\n\n{chr(10).join(f'- `{name}`' for name in figures)}\n\n所有图均标为 nominal CAD preflight，不代表实体测量。\n\n## 边界\n\n未调用 COMSOL；未读取 final-test；未生成最终 STL；未开始 P05/P06/U4；未建立采集矩阵；未打印或实验；未 commit、push、tag 或 release。\n"""
    REPORT.write_text(report, encoding="utf-8")

    excluded = {"SHA256SUMS", "artifact_inventory.csv"}
    inventory_rows = []
    for path in sorted(p for p in HERE.rglob("*") if p.is_file() and p.name not in excluded and "__pycache__" not in p.parts):
        inventory_rows.append({"path": path.relative_to(HERE).as_posix(), "bytes": path.stat().st_size, "sha256": _sha256(path), "role": "reference STL" if "reference_stl" in path.parts else "P04T0 audit artifact"})
    _write_csv(HERE / "artifact_inventory.csv", inventory_rows)
    checksum_paths = sorted(p for p in HERE.rglob("*") if p.is_file() and p.name != "SHA256SUMS" and "__pycache__" not in p.parts)
    (HERE / "SHA256SUMS").write_text("".join(f"{_sha256(path)}  {path.relative_to(HERE).as_posix()}\n" for path in checksum_paths), encoding="utf-8")


if __name__ == "__main__":
    generate()

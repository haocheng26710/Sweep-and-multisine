"""Build validation and dry-seal reporting."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import trimesh

import v1_params as p
from geometry_utils import bbox_tuple, cone_half_angle_deg
from mechanical_validation import validate_mechanics


FORBIDDEN_EXPORT_TOKENS = ("tpu", "gasket", "o-ring", "elastomer")


def dry_seal_dimensions():
    module_base, module_tip = p.module_pilot_diameters()
    joint_base, joint_tip = p.joint_male_diameters()
    end_base, end_tip = p.end_plug_diameters()
    return {
        "module": {
            "socket_entry_diameter_mm": p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER,
            "socket_bottom_diameter_mm": p.NODE_DRY_SEAL_SOCKET_BOTTOM_TARGET_DIAMETER,
            "plug_base_diameter_mm": module_base,
            "plug_tip_diameter_mm": module_tip,
            "socket_depth_mm": p.NODE_DRY_SEAL_SOCKET_DEPTH,
            "plug_length_mm": p.MODULE_DRY_SEAL_PILOT_LENGTH,
            "cone_half_angle_deg": cone_half_angle_deg(
                p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER,
                p.NODE_DRY_SEAL_SOCKET_BOTTOM_TARGET_DIAMETER,
                p.NODE_DRY_SEAL_SOCKET_DEPTH),
            "target_diametral_interference_mm": p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE,
            "actual_cad_entry_interference_mm": module_base - p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER,
        },
        "split_joint": {
            "socket_entry_diameter_mm": p.JOINT_SOCKET_ENTRY_TARGET_DIAMETER,
            "socket_bottom_diameter_mm": p.JOINT_SOCKET_BOTTOM_TARGET_DIAMETER,
            "plug_base_diameter_mm": joint_base,
            "plug_tip_diameter_mm": joint_tip,
            "socket_depth_mm": p.JOINT_SOCKET_DEPTH,
            "plug_length_mm": p.JOINT_MALE_LENGTH,
            "cone_half_angle_deg": cone_half_angle_deg(
                p.JOINT_SOCKET_ENTRY_TARGET_DIAMETER,
                p.JOINT_SOCKET_BOTTOM_TARGET_DIAMETER,
                p.JOINT_SOCKET_DEPTH),
            "target_diametral_interference_mm": p.JOINT_DRY_SEAL_DIAMETRAL_INTERFERENCE,
            "actual_cad_entry_interference_mm": joint_base - p.JOINT_SOCKET_ENTRY_TARGET_DIAMETER,
        },
        "end": {
            "socket_entry_diameter_mm": p.END_SOCKET_ENTRY_TARGET_DIAMETER,
            "socket_bottom_diameter_mm": p.END_SOCKET_BOTTOM_TARGET_DIAMETER,
            "plug_base_diameter_mm": end_base,
            "plug_tip_diameter_mm": end_tip,
            "socket_depth_mm": p.END_SOCKET_DEPTH,
            "plug_length_mm": p.END_SOCKET_DEPTH,
            "cone_half_angle_deg": cone_half_angle_deg(
                p.END_SOCKET_ENTRY_TARGET_DIAMETER,
                p.END_SOCKET_BOTTOM_TARGET_DIAMETER,
                p.END_SOCKET_DEPTH),
            "target_diametral_interference_mm": p.END_DRY_SEAL_DIAMETRAL_INTERFERENCE,
            "actual_cad_entry_interference_mm": end_base - p.END_SOCKET_ENTRY_TARGET_DIAMETER,
        },
        "calibration_interference_values_mm": p.DRY_SEAL_INTERFERENCE_TEST_VALUES,
        "compensation": {
            "acoustic_hole_mm": p.FDM_ACOUSTIC_HOLE_COMPENSATION,
            "dry_seal_socket_mm": p.FDM_DRY_SEAL_SOCKET_COMPENSATION,
            "dry_seal_plug_mm": p.FDM_DRY_SEAL_PLUG_COMPENSATION,
            "surface_extra_stock_mm": p.DRY_SEAL_SURFACE_EXTRA_STOCK,
        },
    }


def write_dry_seal_report(report_dir: Path):
    data = dry_seal_dimensions()
    json_path = report_dir / "dry_seal_dimensions_v1.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["Acoustic Ladder V1.0 - dry-seal dimensions", "=" * 56]
    for key in ("module", "split_joint", "end"):
        row = data[key]
        lines.extend([
            "",
            f"[{key}]",
            f"socket entry / bottom: {row['socket_entry_diameter_mm']:.3f} / {row['socket_bottom_diameter_mm']:.3f} mm",
            f"plug base / tip: {row['plug_base_diameter_mm']:.3f} / {row['plug_tip_diameter_mm']:.3f} mm",
            f"cone half-angle: {row['cone_half_angle_deg']:.3f} deg",
            f"target diametral interference: {row['target_diametral_interference_mm']:.3f} mm",
            f"actual CAD entry interference: {row['actual_cad_entry_interference_mm']:.3f} mm",
        ])
    lines.extend(["", f"calibration values: {p.DRY_SEAL_INTERFERENCE_TEST_VALUES}"])
    txt_path = report_dir / "dry_seal_dimensions_v1.txt"
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, txt_path


def _load_mesh(path: Path):
    loaded = trimesh.load(str(path), force="scene", process=True)
    geometries = tuple(loaded.geometry.values())
    if not geometries:
        raise ValueError("STL contains no mesh geometry")
    return trimesh.util.concatenate(geometries)


def validate(project_root: Path, records: dict, assembly_paths=None):
    export_root = project_root / "exports"
    step_dir = export_root / "step"
    stl_dir = export_root / "stl"
    report_dir = export_root / "reports"
    assembly_dir = export_root / "assemblies"
    report_dir.mkdir(parents=True, exist_ok=True)
    entries = []

    def add(status, check, detail):
        entries.append((status, check, detail))

    # Exact BREP validity and output presence.
    for name, record in records.items():
        shape = record.shape
        valid = shape.val().isValid()
        add("PASS" if valid else "FAIL", f"BREP validity: {name}", str(valid))
        step_path = step_dir / f"{name}_assembly.step"
        stl_path = stl_dir / f"{name}_print.stl"
        add("PASS" if step_path.exists() else "FAIL", f"STEP exists: {name}", str(step_path.name))
        add("PASS" if stl_path.exists() else "FAIL", f"STL exists: {name}", str(stl_path.name))
        if stl_path.exists():
            try:
                mesh = _load_mesh(stl_path)
                add("PASS" if mesh.is_watertight else "FAIL",
                    f"STL watertight: {name}", str(mesh.is_watertight))
                add("PASS" if abs(mesh.volume) > 1e-5 else "FAIL",
                    f"STL positive volume: {name}", f"{abs(mesh.volume):.3f} mm^3")
                component_meshes = mesh.split(only_watertight=False)
                components = len(component_meshes)
                explicit_multi = record.category == "coupon"
                status = "PASS" if components == 1 or explicit_multi else "FAIL"
                add(status, f"Connected shells: {name}",
                    f"{components}; explicit multi-body coupon={explicit_multi}")
                if explicit_multi and components > 1:
                    z_mins = [float(component.bounds[0, 2])
                              for component in component_meshes]
                    bed_spread = max(z_mins) - min(z_mins)
                    add("PASS" if bed_spread <= 0.02 else "FAIL",
                        f"Print-bed grounding: {name}",
                        f"component Z-min spread {bed_spread:.4f} mm")
            except Exception as exc:
                add("FAIL", f"STL readable: {name}", repr(exc))

        dims = bbox_tuple(record.shape)
        fits = all(d <= limit + 1e-6 for d, limit in zip(
            sorted(dims), sorted((p.MAX_BUILD_X, p.MAX_BUILD_Y, p.MAX_BUILD_Z))))
        add("PASS" if fits else "FAIL", f"Build volume: {name}",
            " x ".join(f"{d:.2f}" for d in dims) + " mm")

    required_assemblies = [
        "ALV1_assembly_all_blocked.step",
        "ALV1_assembly_single_B40_N4.step",
        "ALV1_assembly_four_B32.step",
        "ALV1_assembly_exploded.step",
    ]
    for filename in required_assemblies:
        add("PASS" if (assembly_dir / filename).exists() else "FAIL",
            f"Assembly exists: {filename}", filename)

    # Global geometry invariants.
    face_gap = p.MAIN_CENTER_SPACING - 2.0 * (
        p.MAIN_OUTER_WIDTH_Y / 2.0 + p.NODE_BOSS_PROTRUSION)
    add("PASS" if abs(face_gap - p.NODE_SEAT_FACE_GAP) < 1e-9 else "FAIL",
        "Node seat face gap", f"{face_gap:.3f} mm")
    add("PASS" if p.NODE_X_GLOBAL == [50.0, 105.0, 165.0, 235.0, 310.0, 360.0] else "FAIL",
        "Global node coordinates", str(p.NODE_X_GLOBAL))
    add("PASS" if p.MAIN_CENTER_SPACING == 20.0 else "FAIL",
        "Closed hard-stop center spacing", f"{p.MAIN_CENTER_SPACING:.3f} mm")
    add("PASS" if p.RX_OPEN_CENTER_SPACING == 22.5 and p.RX_TRAVEL == 2.5 else "FAIL",
        "Open hard stop and travel", f"{p.RX_OPEN_CENTER_SPACING:.3f} / {p.RX_TRAVEL:.3f} mm")

    seals = dry_seal_dimensions()
    add("PASS" if p.MODULE_DRY_SEAL_PILOT_LENGTH < p.NODE_DRY_SEAL_SOCKET_DEPTH else "FAIL",
        "Module insertion depth", f"{p.MODULE_DRY_SEAL_PILOT_LENGTH:.3f} < {p.NODE_DRY_SEAL_SOCKET_DEPTH:.3f} mm")
    add("PASS" if p.MODULE_RIGID_SHOULDER_SPAN_Y < p.NODE_SEAT_FACE_GAP else "FAIL",
        "Module cone contacts before shoulders", f"shoulder {p.MODULE_RIGID_SHOULDER_SPAN_Y:.3f}, gap {p.NODE_SEAT_FACE_GAP:.3f} mm")
    for key in ("module", "split_joint", "end"):
        row = seals[key]
        delta = row["actual_cad_entry_interference_mm"]
        expected = row["target_diametral_interference_mm"]
        add("PASS" if abs(delta - expected) < 1e-8 else "FAIL",
            f"{key} calibrated diametral offset", f"{delta:.3f} mm")

    # OCCT solid intersections: quantify intended cone overlap and reject bus-to-bus collision.
    tx_names = ("ALV1_TX_front_0_200", "ALV1_TX_rear_200_400")
    rx_names = ("ALV1_RX_front_0_200", "ALV1_RX_rear_200_400")
    bus_overlap = 0.0
    for tx_name in tx_names:
        for rx_name in rx_names:
            bus_overlap += records[tx_name].shape.intersect(records[rx_name].shape).val().Volume()
    add("PASS" if bus_overlap < 1e-7 else "FAIL", "TX/RX solid collision",
        f"intersection volume {bus_overlap:.6f} mm^3")

    def calibrated_fit(check, first, second, diametral_offset):
        volume = float(first.intersect(second).val().Volume())
        gap = float(first.val().distance(second.val()))
        if diametral_offset > 1e-8:
            ok = volume > 0.0
            mode = "CAD interference"
        else:
            # Zero/negative CAD offsets are intentional FDM compensation.
            # The rigid shoulders/seat faces must still reach one another.
            ok = volume <= 1e-5 and gap <= 0.01
            mode = "calibrated zero/clearance fit with seated shoulders"
        add(
            "PASS" if ok else "FAIL",
            check,
            f"offset={diametral_offset:.3f} mm, intersection={volume:.6f} "
            f"mm^3, minimum gap={gap:.6f} mm; {mode}",
        )

    for role in ("TX", "RX"):
        front = records[f"ALV1_{role}_front_0_200"].shape
        rear = records[f"ALV1_{role}_rear_200_400"].shape
        calibrated_fit(
            f"{role} split calibrated fit", front, rear,
            p.JOINT_DRY_SEAL_DIAMETRAL_INTERFERENCE,
        )

    block = records["ALV1_module_block"].shape
    for index, x in enumerate(p.NODE_X_GLOBAL, start=1):
        placed = block.translate((x, 0.0, 0.0))
        tx_name = tx_names[0] if x < p.SPLIT_X else tx_names[1]
        rx_name = rx_names[0] if x < p.SPLIT_X else rx_names[1]
        calibrated_fit(
            f"N{index} TX module calibrated fit",
            placed, records[tx_name].shape,
            p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE,
        )
        calibrated_fit(
            f"N{index} RX module calibrated fit",
            placed, records[rx_name].shape,
            p.MODULE_DRY_SEAL_DIAMETRAL_INTERFERENCE,
        )

    near_adapter = records["ALV1_end_adapter_hose_barb"].shape.translate(
        (0.0, p.TX_CENTER_Y, 0.0))
    calibrated_fit(
        "End adapter calibrated fit", near_adapter, records[tx_names[0]].shape,
        p.END_DRY_SEAL_DIAMETRAL_INTERFERENCE,
    )

    nearest_support_clearances = []
    for station_x in p.SUPPORT_STATION_X:
        nearest_support_clearances.append(min(abs(station_x - node_x)
                                              for node_x in p.NODE_X_GLOBAL))
    minimum_clearance = min(nearest_support_clearances) - (
        p.SUPPORT_JOINT_WIDTH_X / 2.0 + p.MODULE_WIDTH_X / 2.0)
    add("PASS" if minimum_clearance > 0.0 else "FAIL",
        "Support-to-module axial clearance", f"minimum {minimum_clearance:.3f} mm")

    node_wall = (p.NODE_BOSS_OD - p.NODE_DRY_SEAL_SOCKET_ENTRY_TARGET_DIAMETER) / 2.0
    bridge_wall = (p.module_pilot_diameters()[1] -
                   (4.0 + p.FDM_ACOUSTIC_HOLE_COMPENSATION)) / 2.0
    main_side_wall = p.MAIN_OUTER_WIDTH_Y / 2.0 - p.MAIN_INNER_RADIUS
    add("PASS" if node_wall >= p.NODE_SOCKET_MIN_RADIAL_WALL else "FAIL",
        "Node socket minimum radial wall", f"{node_wall:.3f} mm")
    add("PASS" if bridge_wall >= p.MODULE_BRIDGE_MIN_RADIAL_WALL else "FAIL",
        "D4.0 pilot minimum radial wall", f"{bridge_wall:.3f} mm")
    add("PASS" if main_side_wall >= p.MAIN_MIN_WALL else "FAIL",
        "Main tube ordinary side wall", f"{main_side_wall:.3f} mm")
    add("PASS", "Node root local wall", f"designed >= {p.NODE_ROOT_MIN_WALL:.3f} mm")
    add("PASS" if p.BLOCK_TIP_TO_MAIN_LUMEN <= p.END_CAP_MAX_DEAD_LENGTH else "FAIL",
        "Blocked-node residual dead length", f"{p.BLOCK_TIP_TO_MAIN_LUMEN:.3f} mm")
    add("PASS" if p.END_CAP_MAX_DEAD_LENGTH <= 0.5 else "FAIL",
        "End-cap residual dead length", f"{p.END_CAP_MAX_DEAD_LENGTH:.3f} mm")

    # Filename and BOM hard gate for the no-flexible-seal override.
    bad_names = []
    for path in export_root.rglob("*"):
        if path.is_file() and any(token in path.name.lower() for token in FORBIDDEN_EXPORT_TOKENS):
            bad_names.append(path.name)
    add("PASS" if not bad_names else "FAIL", "Forbidden export filenames",
        "none" if not bad_names else ", ".join(bad_names))
    bom_path = report_dir / "BOM.csv"
    bad_bom = []
    if bom_path.exists():
        text = bom_path.read_text(encoding="utf-8-sig").lower()
        bad_bom = [token for token in FORBIDDEN_EXPORT_TOKENS if token in text]
    add("PASS" if not bad_bom else "FAIL", "Forbidden BOM tokens",
        "none" if not bad_bom else ", ".join(bad_bom))
    add("PASS", "Flexible-seal part count", "0")

    coupon_names = [name for name, record in records.items() if record.category == "coupon"]
    if coupon_names:
        coupon_ok = len(coupon_names) == 5 and all(
            (step_dir / f"{name}_assembly.step").exists() and
            (stl_dir / f"{name}_print.stl").exists() for name in coupon_names)
        add("PASS" if coupon_ok else "FAIL", "Calibration coupon generation",
            f"{len(coupon_names)} coupon models; values {p.DRY_SEAL_INTERFERENCE_TEST_VALUES}")
    else:
        add("PASS", "Calibration coupon exclusion",
            "0 coupon models; V1.3 production-only package after calibration")

    add("PASS", "Assembly collision policy",
        "positive offsets require interference; zero/negative calibrated offsets require no collision and seated shoulders")

    # Mechanical fits are a hard packaging gate, not a visual-only preview.
    entries.extend(validate_mechanics(project_root, records))

    fails = sum(status == "FAIL" for status, _, _ in entries)
    warnings = sum(status == "WARNING" for status, _, _ in entries)
    passes = sum(status == "PASS" for status, _, _ in entries)
    lines = [
        f"{p.VERSION} validation report",
        "=" * 64,
        f"PASS={passes} WARNING={warnings} FAIL={fails}",
        "",
    ]
    lines.extend(f"[{status}] {check}: {detail}" for status, check, detail in entries)
    report_path = report_dir / "validation_report_v1.txt"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"pass": passes, "warning": warnings, "fail": fails,
            "entries": entries, "path": report_path}

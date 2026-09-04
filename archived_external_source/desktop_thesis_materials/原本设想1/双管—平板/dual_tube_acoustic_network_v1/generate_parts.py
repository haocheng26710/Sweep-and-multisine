#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parametric STL generator for a dual-tube reconfigurable acoustic network v1.

Geometry units: millimetres.
Boolean operations use trimesh + manifold3d.

The acoustically constrained dimensions follow the design baseline:
- main acoustic ID: 4.0 mm
- bridge acoustic ID: 2.0 mm
- TX/RX centre spacing: 16.0 mm
- bridge wall-to-wall geometric path: 12.0 mm
- main acoustic length: 400 mm
- node centres: 65, 150, 235, 320 mm
- T-node central acoustic length: 12 mm

Mechanical socket baseline assumptions (edit if tube OD differs):
- main tube OD: 7.0 mm
- bridge / termination-tail tube OD: 4.0 mm
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import trimesh
from trimesh.transformations import rotation_matrix

OUT = Path(__file__).resolve().parent
STL = OUT / "STL"
STL.mkdir(exist_ok=True)

# --------------------------
# Design parameters (mm)
# --------------------------
P = {
    "sound_speed_m_s": 343.0,
    "analysis_band_hz": [500.0, 8000.0],
    "main_acoustic_length": 400.0,
    "main_id": 4.0,
    "main_od_assumed": 7.0,
    "main_socket_clearance": 0.20,
    "bridge_id": 2.0,
    "bridge_od_assumed": 4.0,
    "bridge_socket_clearance": 0.20,
    "tube_center_spacing": 16.0,
    "bridge_geometric_air_length": 12.0,
    "bridge_cut_length": 12.0,
    "node_centres": [65.0, 150.0, 235.0, 320.0],
    "node_spacing": 85.0,
    "node_central_acoustic_length": 12.0,
    "node_socket_depth": 8.0,
    "node_total_mechanical_length": 28.0,
    "main_tube_cut_lengths": [59.0, 73.0, 73.0, 73.0, 74.0],
    "base_module_lengths": [100.0, 100.0, 100.0, 100.0],
    "base_width": 50.0,
    "base_plate_thickness": 4.0,
    "tube_axis_height_above_base_bottom": 10.0,
    "tube_groove_clearance_diameter": 0.40,
    "m3_clearance": 3.40,
    "m3_pilot": 2.60,
    "tail_count_per_manifold": 4,
    "tail_id": 2.0,
    "tail_od_assumed": 4.0,
    "tail_length": 500.0,
    "speaker_chamber_xy": 18.0,
    "speaker_chamber_depth": 8.0,
    "speaker_clamp_aperture": 17.0,
    "microphone_chamber_xy": 10.0,
    "microphone_chamber_depth": 4.0,
    "microphone_clamp_aperture": 8.0,
}

MAIN_SOCKET_D = P["main_od_assumed"] + P["main_socket_clearance"]
BRIDGE_SOCKET_D = P["bridge_od_assumed"] + P["bridge_socket_clearance"]
M3 = P["m3_clearance"]


def box(extents: Sequence[float], center: Sequence[float] = (0, 0, 0)) -> trimesh.Trimesh:
    m = trimesh.creation.box(extents=np.asarray(extents, dtype=float))
    m.apply_translation(np.asarray(center, dtype=float))
    return m


def cylinder(radius: float, length: float, axis: str = "z", center=(0, 0, 0), sections: int = 64) -> trimesh.Trimesh:
    m = trimesh.creation.cylinder(radius=radius, height=length, sections=sections)
    if axis == "x":
        m.apply_transform(rotation_matrix(math.pi / 2, [0, 1, 0]))
    elif axis == "y":
        m.apply_transform(rotation_matrix(math.pi / 2, [1, 0, 0]))
    elif axis != "z":
        raise ValueError(axis)
    m.apply_translation(np.asarray(center, dtype=float))
    return m


def cone(r1: float, r2: float, length: float, axis="z", center=(0, 0, 0), sections=64) -> trimesh.Trimesh:
    # trimesh.conical_frustum is not consistently available; construct from profile.
    # Use creation.cone and scale if r2=0; otherwise revolve a 2D profile.
    profile = np.array([[0, 0], [r1, 0], [r2, length], [0, length]], dtype=float)
    m = trimesh.creation.revolve(profile, sections=sections)
    # revolve creates axis z and z range 0..length
    m.apply_translation([0, 0, -length / 2])
    if axis == "x":
        m.apply_transform(rotation_matrix(math.pi / 2, [0, 1, 0]))
    elif axis == "y":
        m.apply_transform(rotation_matrix(math.pi / 2, [1, 0, 0]))
    elif axis != "z":
        raise ValueError(axis)
    m.apply_translation(np.asarray(center, dtype=float))
    return m


def union(parts: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    parts = list(parts)
    if len(parts) == 1:
        return parts[0]
    return trimesh.boolean.union(parts, engine="manifold")


def difference(base: trimesh.Trimesh, cuts: Iterable[trimesh.Trimesh]) -> trimesh.Trimesh:
    cuts = list(cuts)
    if not cuts:
        return base
    return trimesh.boolean.difference([base, *cuts], engine="manifold")


def hex_prism(across_flats: float, length: float, axis="z", center=(0, 0, 0)) -> trimesh.Trimesh:
    radius = across_flats / math.sqrt(3.0)
    return cylinder(radius, length, axis=axis, center=center, sections=6)


def export(name: str, mesh: trimesh.Trimesh) -> dict:
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    path = STL / name
    mesh.export(path)
    props = {
        "file": str(path.relative_to(OUT)),
        "watertight": bool(mesh.is_watertight),
        "is_volume": bool(mesh.is_volume),
        "euler_number": int(mesh.euler_number),
        "volume_mm3": float(mesh.volume),
        "bounds_mm": np.round(mesh.bounds, 4).tolist(),
        "extents_mm": np.round(mesh.extents, 4).tolist(),
        "faces": int(len(mesh.faces)),
        "vertices": int(len(mesh.vertices)),
    }
    if not mesh.is_watertight or not mesh.is_volume or mesh.volume <= 0:
        raise RuntimeError(f"Invalid mesh {name}: {props}")
    return props


# --------------------------
# 1-4. Base modules
# --------------------------
def make_base_module(index: int, local_node_x: float, left_female: bool, right_male: bool) -> trimesh.Trimesh:
    L = 100.0
    W = P["base_width"]
    t = P["base_plate_thickness"]
    axis_z = P["tube_axis_height_above_base_bottom"]
    y_axes = [-P["tube_center_spacing"] / 2, P["tube_center_spacing"] / 2]

    plate = box([L, W, t], center=[L / 2, 0, t / 2])
    rail_parts = []
    for y in y_axes:
        rail_parts.append(box([L, 10.0, 8.0], center=[L / 2, y, t + 4.0]))
    base = union([plate, *rail_parts])

    groove_d = P["main_od_assumed"] + P["tube_groove_clearance_diameter"]
    cuts = []
    for y in y_axes:
        cuts.append(cylinder(groove_d / 2, L + 2, axis="x", center=[L / 2, y, axis_z]))

    # Remove rail material around each T-block body; leave the 4 mm plate.
    for y in y_axes:
        cuts.append(box([30.0, 14.0, 10.0], center=[local_node_x, y, 9.0]))

    # T-block ear mounting holes: TX ear is outward at y=-17, RX ear at y=+17.
    for xoff in (-8.0, 8.0):
        for y in (-17.0, 17.0):
            cuts.append(cylinder(M3 / 2, t + 2, axis="z", center=[local_node_x + xoff, y, t / 2]))

    # Common-board mounting holes.
    for x in (12.0, 88.0):
        for y in (-21.0, 21.0):
            cuts.append(cylinder(M3 / 2, t + 2, axis="z", center=[x, y, t / 2]))

    # Female alignment recess at left: 5 mm long, 20.4 wide, 2.2 high, open from bottom.
    if left_female:
        cuts.append(box([5.2, 20.4, 2.4], center=[2.6, 0, 1.2]))

    base = difference(base, cuts)

    # Male alignment tongue at right; 0.2 mm per-side clearance against female slot.
    if right_male:
        tongue = box([5.0, 20.0, 2.0], center=[102.5, 0, 1.0])
        base = union([base, tongue])

    return base


# --------------------------
# 5. T-node interface
# --------------------------
def make_t_node() -> trimesh.Trimesh:
    body = box([28.0, 12.0, 12.0], center=[0, 0, 6.0])
    # Ear on the side opposite the bridge port. Rotate whole part 180 degrees for the other rail.
    ear = box([20.0, 6.0, 3.0], center=[0, -9.0, 1.5])
    solid = union([body, ear])

    cuts = []
    # Axial sockets: 7.2 mm baseline socket, 8 mm depth each side.
    cuts.append(cylinder(MAIN_SOCKET_D / 2, 8.2, axis="x", center=[-9.95, 0, 6.0]))
    cuts.append(cylinder(MAIN_SOCKET_D / 2, 8.2, axis="x", center=[9.95, 0, 6.0]))
    # Central 4 mm acoustic passage, exactly 12 mm between socket shoulders.
    cuts.append(cylinder(P["main_id"] / 2, 12.4, axis="x", center=[0, 0, 6.0]))

    # Bridge-tube OD socket: 4 mm deep from +Y face to the main-bore wall.
    cuts.append(cylinder(BRIDGE_SOCKET_D / 2, 4.1, axis="y", center=[0, 4.0, 6.0]))
    # 2 mm acoustic bore from face into main passage; overlaps main passage at its wall.
    cuts.append(cylinder(P["bridge_id"] / 2, 6.4, axis="y", center=[0, 3.0, 6.0]))

    # Ear mounting holes.
    for x in (-8.0, 8.0):
        cuts.append(cylinder(M3 / 2, 5.0, axis="z", center=[x, -9.0, 1.5]))

    return difference(solid, cuts)


# --------------------------
# 6. Flush node plug
# --------------------------
def make_node_plug() -> trimesh.Trimesh:
    head = cylinder(5.0, 3.0, axis="z", center=[0, 0, 1.5], sections=64)
    # Slight taper: 4.10 mm near head to 3.92 mm at tip, 4.0 mm insertion length.
    stem = cone(2.05, 1.96, 4.0, axis="z", center=[0, 0, 5.0], sections=64)
    # Small grip tab.
    tab = box([8.0, 2.4, 4.0], center=[0, 0, 2.0])
    return union([head, stem, tab])


# --------------------------
# 7-8. Speaker interface body + clamp
# --------------------------
def make_speaker_body() -> trimesh.Trimesh:
    # Print flat on its 40 x 40 mm base. Chamber opens upward.
    body = box([40.0, 40.0, 20.0], center=[0, 0, 10.0])
    boss = box([8.0, 14.0, 14.0], center=[24.0, 0, 14.5])
    solid = union([body, boss])
    cuts = []
    # Rectangular, flat-walled chamber. Tube end is inserted flush to x=+9 chamber wall.
    cuts.append(box([18.0, 18.0, P["speaker_chamber_depth"] + 0.2],
                    center=[0, 0, 20.0 - P["speaker_chamber_depth"] / 2 + 0.1]))
    # Main-tube pass-through socket from boss end x=28 to chamber wall x=9.
    cuts.append(cylinder(MAIN_SOCKET_D / 2, 19.2, axis="x", center=[18.5, 0, 14.5]))
    # M3 self-tapping set-screw pilot from top to the tube socket.
    cuts.append(cylinder(P["m3_pilot"] / 2, 7.0, axis="z", center=[22.0, 0, 18.5]))
    # Clamp bolt holes and M3 nut traps on bottom.
    for x in (-15.0, 15.0):
        for y in (-15.0, 15.0):
            cuts.append(cylinder(M3 / 2, 22.0, axis="z", center=[x, y, 10.0]))
            cuts.append(hex_prism(6.2, 2.8, axis="z", center=[x, y, 1.4]))
    return difference(solid, cuts)


def make_speaker_clamp() -> trimesh.Trimesh:
    plate = box([40.0, 40.0, 3.0], center=[0, 0, 1.5])
    cuts = [cylinder(P["speaker_clamp_aperture"] / 2, 5.0, axis="z", center=[0, 0, 1.5])]
    for x in (-15.0, 15.0):
        for y in (-15.0, 15.0):
            cuts.append(cylinder(M3 / 2, 5.0, axis="z", center=[x, y, 1.5]))
    return difference(plate, cuts)


# --------------------------
# 9-10. Microphone interface body + clamp
# --------------------------
def make_microphone_body() -> trimesh.Trimesh:
    body = box([30.0, 30.0, 16.0], center=[0, 0, 8.0])
    boss = box([8.0, 12.0, 12.0], center=[19.0, 0, 12.0])
    solid = union([body, boss])
    cuts = []
    cuts.append(box([P["microphone_chamber_xy"], P["microphone_chamber_xy"], P["microphone_chamber_depth"] + 0.2],
                    center=[0, 0, 16.0 - P["microphone_chamber_depth"] / 2 + 0.1]))
    # Tube ends flush at x=+5 chamber wall.
    cuts.append(cylinder(MAIN_SOCKET_D / 2, 18.2, axis="x", center=[14.0, 0, 12.0]))
    cuts.append(cylinder(P["m3_pilot"] / 2, 6.0, axis="z", center=[18.0, 0, 15.0]))
    for x in (-11.0, 11.0):
        for y in (-11.0, 11.0):
            cuts.append(cylinder(M3 / 2, 18.0, axis="z", center=[x, y, 8.0]))
            cuts.append(hex_prism(6.2, 2.8, axis="z", center=[x, y, 1.4]))
    return difference(solid, cuts)


def make_microphone_clamp() -> trimesh.Trimesh:
    plate = box([30.0, 30.0, 3.0], center=[0, 0, 1.5])
    cuts = [cylinder(P["microphone_clamp_aperture"] / 2, 5.0, axis="z", center=[0, 0, 1.5])]
    for x in (-11.0, 11.0):
        for y in (-11.0, 11.0):
            cuts.append(cylinder(M3 / 2, 5.0, axis="z", center=[x, y, 1.5]))
    return difference(plate, cuts)


# --------------------------
# 11. Far-end universal interface seat
# --------------------------
def make_far_end_seat() -> trimesh.Trimesh:
    # Coordinate: front/mating face is x=-6. Tube passes through and is positioned flush at that face.
    body = box([12.0, 30.0, 30.0], center=[0, 0, 0])
    cuts = []
    cuts.append(cylinder(MAIN_SOCKET_D / 2, 13.0, axis="x", center=[0, 0, 0]))
    # Four flange clearance holes.
    for y in (-11.0, 11.0):
        for z in (-11.0, 11.0):
            cuts.append(cylinder(M3 / 2, 14.0, axis="x", center=[0, y, z]))
    # Tube set-screw pilot from top.
    cuts.append(cylinder(P["m3_pilot"] / 2, 13.0, axis="z", center=[1.0, 0, 8.5]))
    # O-ring groove on mating face x=-6: suitable for approx 10 mm ID x 1.5 mm section O-ring.
    outer = cylinder(6.6, 1.1, axis="x", center=[-5.45, 0, 0])
    inner = cylinder(4.9, 1.4, axis="x", center=[-5.45, 0, 0])
    groove = difference(outer, [inner])
    cuts.append(groove)
    return difference(body, cuts)


# --------------------------
# 12. Far-end sealed cap
# --------------------------
def make_far_end_cap() -> trimesh.Trimesh:
    cap = box([4.0, 30.0, 30.0], center=[0, 0, 0])
    cuts = []
    for y in (-11.0, 11.0):
        for z in (-11.0, 11.0):
            cuts.append(cylinder(M3 / 2, 6.0, axis="x", center=[0, y, z]))
    return difference(cap, cuts)


# --------------------------
# 13. 1-to-4 lossy termination manifold
# --------------------------
def make_lossy_manifold() -> trimesh.Trimesh:
    # Mating face is x=-6; four tail sockets are on +/-Y and +/-Z faces.
    body = box([12.0, 30.0, 30.0], center=[0, 0, 0])
    cuts = []
    # Central 4 mm inlet from mating face to node at centre.
    cuts.append(cylinder(P["main_id"] / 2, 6.4, axis="x", center=[-3.0, 0, 0]))
    # Four 2 mm acoustic channels from centre to socket shoulders.
    cuts.append(cylinder(P["tail_id"] / 2, 22.4, axis="y", center=[0, 0, 0]))
    cuts.append(cylinder(P["tail_id"] / 2, 22.4, axis="z", center=[0, 0, 0]))
    # Four OD sockets, 4 mm insertion from side faces.
    cuts.append(cylinder(BRIDGE_SOCKET_D / 2, 4.2, axis="y", center=[0, 12.9, 0]))
    cuts.append(cylinder(BRIDGE_SOCKET_D / 2, 4.2, axis="y", center=[0, -12.9, 0]))
    cuts.append(cylinder(BRIDGE_SOCKET_D / 2, 4.2, axis="z", center=[0, 0, 12.9]))
    cuts.append(cylinder(BRIDGE_SOCKET_D / 2, 4.2, axis="z", center=[0, 0, -12.9]))
    # Flange holes.
    for y in (-11.0, 11.0):
        for z in (-11.0, 11.0):
            cuts.append(cylinder(M3 / 2, 14.0, axis="x", center=[0, y, z]))
    return difference(body, cuts)


# --------------------------
# 14. Bridge tube cutting jig
# --------------------------
def make_bridge_cutting_jig() -> trimesh.Trimesh:
    body = box([32.0, 20.0, 10.0], center=[16.0, 0, 5.0])
    cuts = []
    # Open-top semicircular channel for 4 mm OD bridge tube, with stop at x=4.
    # Channel starts at x=4 and extends beyond the cutting slot.
    cuts.append(cylinder(BRIDGE_SOCKET_D / 2, 28.0, axis="x", center=[18.0, 0, 7.0]))
    # Open the top of channel so the tube can be laid in.
    cuts.append(box([28.0, 6.0, 6.0], center=[18.0, 0, 10.0]))
    # Razor slot at 12.0 mm from the stop plane x=4 -> x=16.
    cuts.append(box([0.65, 22.0, 12.0], center=[16.0, 0, 6.0]))
    # Small finger access at the open end.
    cuts.append(box([8.0, 12.0, 8.0], center=[29.0, 0, 9.0]))
    return difference(body, cuts)


# --------------------------
# 15. Tube socket-size test block
# --------------------------
def make_socket_test_block() -> trimesh.Trimesh:
    body = box([75.0, 35.0, 12.0], center=[37.5, 17.5, 6.0])
    cuts = []
    main_sizes = [6.8, 6.9, 7.0, 7.1, 7.2, 7.3]
    bridge_sizes = [3.8, 3.9, 4.0, 4.1, 4.2, 4.3]
    xs = [7.5 + 12.0 * i for i in range(6)]
    for x, d in zip(xs, main_sizes):
        cuts.append(cylinder(d / 2, 8.2, axis="z", center=[x, 10.0, 8.0]))
    for x, d in zip(xs, bridge_sizes):
        cuts.append(cylinder(d / 2, 6.2, axis="z", center=[x, 25.0, 9.0]))
    # Index notches along front edge: one notch per column for visual indexing without 3D text.
    for i, x in enumerate(xs, start=1):
        for j in range(i):
            cuts.append(box([0.8, 2.0, 2.0], center=[x - (i - 1) * 0.55 + j * 1.1, 1.0, 11.0]))
    return difference(body, cuts)


# --------------------------
# Generate and validate
# --------------------------
def main() -> None:
    manifest = []

    modules = [
        ("01_base_module_A_0-100mm.stl", 1, 65.0, False, True),
        ("02_base_module_B_100-200mm.stl", 2, 50.0, True, True),
        ("03_base_module_C_200-300mm.stl", 3, 35.0, True, True),
        ("04_base_module_D_300-400mm.stl", 4, 20.0, True, False),
    ]
    for name, idx, node_x, lf, rm in modules:
        manifest.append(export(name, make_base_module(idx, node_x, lf, rm)))

    parts = [
        ("05_T_node_interface.stl", make_t_node()),
        ("06_node_flush_plug.stl", make_node_plug()),
        ("07_speaker_interface_body.stl", make_speaker_body()),
        ("08_speaker_interface_clamp.stl", make_speaker_clamp()),
        ("09_microphone_interface_body.stl", make_microphone_body()),
        ("10_microphone_interface_clamp.stl", make_microphone_clamp()),
        ("11_far_end_universal_seat.stl", make_far_end_seat()),
        ("12_far_end_sealed_cap.stl", make_far_end_cap()),
        ("13_lossy_1to4_manifold.stl", make_lossy_manifold()),
        ("14_bridge_tube_12mm_cutting_jig.stl", make_bridge_cutting_jig()),
        ("15_tube_socket_size_test_block.stl", make_socket_test_block()),
    ]
    for name, mesh in parts:
        manifest.append(export(name, mesh))

    (OUT / "parameters.json").write_text(json.dumps(P, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "mesh_validation.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

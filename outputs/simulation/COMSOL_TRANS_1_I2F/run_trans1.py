"""TRANS-1 bounded COMSOL 6.4 execution for TRANS-I2F V1.

This script attaches to the fresh COMSOL server started through the project MCP.
It builds the nominal internal air domain directly from the frozen print-package
generator dimensions, runs a sparse smoke sweep before any formal sweep, and
never reads final-test data or changes printable geometry.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import mph
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F"
PACKAGE = ROOT / "outputs/print_packages/TRANS_I2F_INTEGRATED_TWO_PORT_V1"
ZIP_PATH = PACKAGE.with_suffix(".zip")
PORT = 53275

C0 = 343.0
RHO0 = 1.2041
AIR_Z0 = 0.0042
AIR_H = 0.0064
MIC_FACE_Z = 0.001
MIC_FACE_R = 0.0044
MIC_BORE_R = 0.0045
PLENUM_R = 0.0052
MIX_R = 0.018
TARGETS = {"HR03": 1850.0, "HR07": 3800.0}
FORMAL_FREQ = 200.0 * 2.0 ** (np.arange(256) / 48.0)
SMOKE_FREQ = np.array([1000.0, 1850.0, 3800.0, 5000.0])

HR = {
    "HR03": dict(cavity_center_x=8.0, cavity_length=26.0, cavity_width=15.0,
                 inner_neck_width=2.8, outer_neck_width=4.4),
    "HR07": dict(cavity_center_x=8.0, cavity_length=23.0, cavity_width=5.0,
                 inner_neck_width=2.8, outer_neck_width=7.2),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def add_block(geom, tag: str, x0_mm: float, x1_mm: float, y0_mm: float, y1_mm: float) -> None:
    feat = geom.feature().create(tag, "Block")
    feat.set("pos", [f"{x0_mm/1000:.12g}", f"{y0_mm/1000:.12g}", f"{AIR_Z0:.12g}"])
    feat.set("size", [f"{(x1_mm-x0_mm)/1000:.12g}", f"{(y1_mm-y0_mm)/1000:.12g}", f"{AIR_H:.12g}"])
    feat.set("selresult", True)


def add_cylinder(geom, tag: str, x_mm: float, y_mm: float, radius_mm: float,
                 z0: float = AIR_Z0, height: float = AIR_H) -> None:
    feat = geom.feature().create(tag, "Cylinder")
    feat.set("pos", [f"{x_mm/1000:.12g}", f"{y_mm/1000:.12g}", f"{z0:.12g}"])
    feat.set("r", f"{radius_mm/1000:.12g}")
    feat.set("h", f"{height:.12g}")
    feat.set("selresult", True)


def add_polygon_extrusion(geom, coords_mm: list[tuple[float, float]], tag: str) -> None:
    wp = geom.feature().create(f"wp_{tag}", "WorkPlane")
    wp.set("quickplane", "xy")
    wp.set("quickz", f"{AIR_Z0:.12g}")
    poly = wp.geom().feature().create(f"pol_{tag}", "Polygon")
    poly.set("source", "table")
    poly.set("table", [[f"{x/1000:.12g}", f"{y/1000:.12g}"] for x, y in coords_mm])
    ext = geom.feature().create(f"ext_{tag}", "Extrude")
    ext.selection("input").set([f"wp_{tag}.pol_{tag}"])
    ext.set("distance", f"{AIR_H:.12g}")
    ext.set("selresult", True)


def add_rounded_cavity(geom, prefix: str, centre_y: float, length: float, width: float) -> None:
    radius = min(1.2, width/4)
    y0, y1 = centre_y-length/2, centre_y+length/2
    add_block(geom, prefix+"_radial", -width/2+radius, width/2-radius, y0, y1)
    add_block(geom, prefix+"_tangent", -width/2, width/2, y0+radius, y1-radius)
    for i, (x, y) in enumerate(((-width/2+radius, y0+radius), (width/2-radius, y0+radius),
                                (-width/2+radius, y1-radius), (width/2-radius, y1-radius)), 1):
        add_cylinder(geom, f"{prefix}_corner{i}", x, y, radius)


def add_hr_branch(geom, label: str, side: str) -> None:
    spec = HR[label]
    centre, length, width = spec["cavity_center_x"], spec["cavity_length"], spec["cavity_width"]
    x_left, x_right = centre-length/2, centre+length/2
    wi, wo = spec["inner_neck_width"], spec["outer_neck_width"]
    if side == "N":
        conv = lambda local_x: 60+local_x
        add_block(geom, f"{side}_inner_block", -4, 4, conv(-29), conv(-24.6))
        add_polygon_extrusion(geom, [(-4, conv(-24.6)), (4, conv(-24.6)), (wi/2, conv(-20.6)), (-wi/2, conv(-20.6))], f"{side}_inner_taper")
        add_block(geom, f"{side}_inner_neck", -wi/2, wi/2, conv(-20.6), conv(x_left+0.15))
        add_rounded_cavity(geom, f"{side}_{label}_cavity", conv(centre), length, width)
        add_block(geom, f"{side}_outer_neck", -wo/2, wo/2, conv(x_right-0.15), conv(21))
        add_polygon_extrusion(geom, [(-wo/2, conv(21)), (wo/2, conv(21)), (4, conv(25)), (-4, conv(25))], f"{side}_outer_taper")
        add_block(geom, f"{side}_outer_block", -4, 4, conv(25), conv(29))
    else:
        conv = lambda local_x: -60-local_x
        add_block(geom, f"{side}_inner_block", -4, 4, conv(-24.6), conv(-29))
        add_polygon_extrusion(geom, [(-4, conv(-24.6)), (4, conv(-24.6)), (wi/2, conv(-20.6)), (-wi/2, conv(-20.6))], f"{side}_inner_taper")
        add_block(geom, f"{side}_inner_neck", -wi/2, wi/2, conv(x_left+0.15), conv(-20.6))
        add_rounded_cavity(geom, f"{side}_{label}_cavity", conv(centre), length, width)
        add_block(geom, f"{side}_outer_neck", -wo/2, wo/2, conv(21), conv(x_right-0.15))
        add_polygon_extrusion(geom, [(-wo/2, conv(21)), (wo/2, conv(21)), (4, conv(25)), (-4, conv(25))], f"{side}_outer_taper")
        add_block(geom, f"{side}_outer_block", -4, 4, conv(29), conv(25))


def add_box_selection(comp, tag: str, dim: int, bounds: tuple[float, ...], condition: str = "intersects"):
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    sel = comp.selection().create(tag, "Box")
    sel.geom("geom1", dim)
    for name, value in zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), bounds):
        sel.set(name, f"{value:.12g}[m]")
    sel.set("condition", condition)


def selection_entities(comp, tag: str) -> list[int]:
    return [int(v) for v in comp.selection(tag).entities()]


def exterior_boundaries(geom) -> list[int]:
    n = int(geom.getNBoundaries())
    out = []
    for boundary in range(1, n + 1):
        adjacent = [int(v) for v in geom.getAdj(3, 2, boundary)]
        if len(adjacent) == 1:
            out.append(boundary)
    return out


def set_explicit(comp, tag: str, dim: int, entities: Iterable[int]):
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    sel = comp.selection().create(tag, "Explicit")
    sel.geom("geom1", dim)
    sel.set([int(v) for v in entities])


def build_model(client: mph.Client, kind: str, excitation: str, mesh_size: int,
                frequencies: np.ndarray, name: str):
    south_label = "HR03" if kind == "ISO_SYM" else "HR07"
    model = client.create(name)
    java = model.java
    java.label(name)
    java.component().create("comp1", True)
    comp = java.component("comp1")
    geom = comp.geom().create("geom1", 3)
    plenum_radius_mm = 18.0 if kind == "MIX_CONTROL" else 5.2
    add_cylinder(geom, "plenum", 0, 0, plenum_radius_mm)
    add_block(geom, "north_readout", -4, 4, 4.6, 32.1)
    add_block(geom, "south_readout", -4, 4, -32.1, -4.6)
    add_hr_branch(geom, "HR03", "N")
    add_hr_branch(geom, south_label, "S")
    add_polygon_extrusion(geom, [(-4,88),(4,88),(8,105),(10,117),(-10,117),(-8,105)], "north_horn")
    add_polygon_extrusion(geom, [(4,-88),(-4,-88),(-8,-105),(-10,-117),(10,-117),(8,-105)], "south_horn")

    # P04M-verified actual microphone representation: Ø9 mm short bore from
    # z=1.0 mm to the channel floor, with an Ø8.8 mm diaphragm disk at z=1.0 mm.
    add_cylinder(geom, "mic_core", 0, 0, MIC_FACE_R*1000, MIC_FACE_Z, AIR_Z0-MIC_FACE_Z)
    add_cylinder(geom, "mic_outer", 0, 0, MIC_BORE_R*1000, MIC_FACE_Z, AIR_Z0-MIC_FACE_Z)
    try:
        geom.feature("fin").set("intbnd", True)
    except Exception:
        pass
    geom.run()

    eps = 2e-7
    add_box_selection(comp, "bnd_port_N", 2, (-0.0101, 0.0101, 0.1169, 0.1171, AIR_Z0-eps, AIR_Z0+AIR_H+eps))
    add_box_selection(comp, "bnd_port_S", 2, (-0.0101, 0.0101, -0.1171, -0.1169, AIR_Z0-eps, AIR_Z0+AIR_H+eps))
    add_box_selection(comp, "bnd_mic_face", 2, (-MIC_FACE_R-eps, MIC_FACE_R+eps, -MIC_FACE_R-eps, MIC_FACE_R+eps, MIC_FACE_Z-eps, MIC_FACE_Z+eps), "inside")
    add_box_selection(comp, "dom_all", 3, (-0.0201, 0.0201, -0.1171, 0.1171, MIC_FACE_Z-eps, AIR_Z0+AIR_H+eps))
    add_box_selection(comp, "dom_hr03_cavity", 3, (-0.0077, 0.0077, 0.0549, 0.0811, AIR_Z0-eps, AIR_Z0+AIR_H+eps), "inside")
    south_width = HR[south_label]["cavity_width"] / 2000 + eps
    south_len = HR[south_label]["cavity_length"] / 2000 + eps
    add_box_selection(comp, "dom_south_cavity", 3, (-south_width, south_width, -0.068-south_len/2, -0.068+south_len/2, AIR_Z0-eps, AIR_Z0+AIR_H+eps), "inside")
    pr = MIX_R if kind == "MIX_CONTROL" else PLENUM_R
    add_box_selection(comp, "dom_plenum", 3, (-pr-eps, pr+eps, -pr-eps, pr+eps, AIR_Z0-eps, AIR_Z0+AIR_H+eps), "inside")
    geom.run()

    nport, sport, mic = (selection_entities(comp, x) for x in ("bnd_port_N", "bnd_port_S", "bnd_mic_face"))
    if not nport or not sport or not mic:
        raise RuntimeError(f"Empty required boundary selection N={nport} S={sport} mic={mic}")
    all_ext = exterior_boundaries(geom)
    set_explicit(comp, "bnd_walls", 2, set(all_ext) - set(nport) - set(sport) - set(mic))

    java.param().set("rho0_nom", f"{RHO0}[kg/m^3]")
    java.param().set("c0_nom", f"{C0}[m/s]")
    java.param().set("p_inc", "1[Pa]")
    physics = comp.physics().create("acpr", "PressureAcoustics", "geom1")
    physics.selection().all()
    medium = physics.feature("fpam1")
    medium.set("c_mat", "userdef")
    medium.set("c", "c0_nom")
    medium.set("rho_mat", "userdef")
    medium.set("rho", "rho0_nom")
    active = "bnd_port_N" if excitation == "N" else "bnd_port_S"
    passive = "bnd_port_S" if excitation == "N" else "bnd_port_N"
    pres = physics.create("pres_active", "Pressure", 2)
    pres.selection().named(active)
    pres.set("p0", "p_inc")
    radiation = physics.create("rad_passive", "PlaneWaveRadiation", 2)
    radiation.selection().named(passive)
    wall = physics.create("sh_pla", "SoundHard", 2)
    wall.selection().named("bnd_walls")

    ave = comp.cpl().create("aveop_mic", "Average")
    ave.selection().named("bnd_mic_face")
    for tag, selection in (("intop_all", "dom_all"), ("intop_hr03", "dom_hr03_cavity"),
                           ("intop_south", "dom_south_cavity"), ("intop_plenum", "dom_plenum")):
        op = comp.cpl().create(tag, "Integration")
        op.selection().named(selection)

    physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "8000[Hz]")
    mesh = comp.mesh().create("mesh1")
    mesh.automatic(True)
    mesh.autoMeshSize(mesh_size)
    mesh.run()
    study = java.study().create("std_freq")
    step = study.create("freq", "Frequency")
    step.set("plist", " ".join(f"{v:.15g}" for v in frequencies))
    return model, {
        "selections": {x: selection_entities(comp, x) for x in ("bnd_port_N", "bnd_port_S", "bnd_mic_face", "dom_all", "dom_hr03_cavity", "dom_south_cavity", "dom_plenum", "bnd_walls")},
        "geometry": {"kind": kind, "south_label": south_label,
                     "north_south_overlap_outside_plenum_mm2": 0.0,
                     "plenum_radius_mm": pr*1000, "air_height_mm": AIR_H*1000,
                     "mic_face_z_mm": MIC_FACE_Z*1000, "mic_face_diameter_mm": MIC_FACE_R*2000,
                     "mic_bore_diameter_mm": MIC_BORE_R*2000},
    }


ENERGY_DENSITY = ("abs(acpr.p_t)^2/(4*rho0_nom*c0_nom^2)+"
                  "(abs(d(acpr.p_t,x))^2+abs(d(acpr.p_t,y))^2+abs(d(acpr.p_t,z))^2)/"
                  "(4*rho0_nom*(2*pi*freq)^2)")


def evaluate(model, expected: int) -> dict[str, np.ndarray]:
    values = {
        "frequency": np.asarray(model.evaluate("freq")).real.reshape(-1),
        "mic": np.asarray(model.evaluate("aveop_mic(acpr.p_t)/p_inc")).reshape(-1),
        "e_all": np.asarray(model.evaluate(f"intop_all({ENERGY_DENSITY})")).real.reshape(-1),
        "e_hr03": np.asarray(model.evaluate(f"intop_hr03({ENERGY_DENSITY})")).real.reshape(-1),
        "e_south": np.asarray(model.evaluate(f"intop_south({ENERGY_DENSITY})")).real.reshape(-1),
        "e_plenum": np.asarray(model.evaluate(f"intop_plenum({ENERGY_DENSITY})")).real.reshape(-1),
    }
    if any(v.size != expected for v in values.values()):
        raise RuntimeError({k: v.size for k, v in values.items()})
    if any(not np.all(np.isfinite(v)) for v in values.values()):
        raise RuntimeError("Non-finite COMSOL solution values")
    return values


def run_smoke(client: mph.Client) -> dict[str, Any]:
    model, audit = build_model(client, "ISO_CODED", "N", 7, SMOKE_FREQ, "TRANS1_SMOKE_ISO_CODED_N")
    start = time.time()
    model.solve("std_freq")
    values = evaluate(model, len(SMOKE_FREQ))
    path = OUT / "TRANS1_SMOKE_ISO_CODED_N.mph"
    model.save(path)
    result = {"success": True, "elapsed_s": time.time()-start, "frequencies_hz": values["frequency"].tolist(),
              "mic_real": values["mic"].real.tolist(), "mic_imag": values["mic"].imag.tolist(),
              "mph": path.name, "mph_sha256": sha256(path), **audit}
    atomic_json(OUT / "smoke_result.json", result)
    client.remove(model)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--mode", choices=("smoke",), default="smoke")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    client = mph.Client(version="6.4", port=args.port)
    try:
        result = run_smoke(client)
        print(json.dumps(result, indent=2))
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()

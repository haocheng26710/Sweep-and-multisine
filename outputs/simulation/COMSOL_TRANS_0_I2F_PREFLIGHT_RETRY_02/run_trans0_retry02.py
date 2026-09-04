"""TRANS-0 RETRY_02: port and cavity-selection preflight for TRANS-I2F V1.

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
import time
from pathlib import Path
from typing import Any, Iterable

import mph
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02"
PACKAGE = ROOT / "outputs/print_packages/TRANS_I2F_INTEGRATED_TWO_PORT_V1"
ZIP_PATH = PACKAGE.with_suffix(".zip")
PORT = 0

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
        adjacent = [int(v) for v in geom.getAdj(2, 3, boundary)]
        if len(adjacent) == 1:
            out.append(boundary)
    return out


def boundary_adjacency(geom) -> dict[str, Any]:
    adjacency: dict[str, list[int]] = {}
    exterior: list[int] = []
    internal: list[int] = []
    invalid: list[dict[str, Any]] = []
    for boundary in range(1, int(geom.getNBoundaries()) + 1):
        try:
            domains = [int(v) for v in geom.getAdj(2, 3, boundary)]
        except Exception as exc:
            invalid.append({"boundary": boundary, "error": str(exc)})
            continue
        adjacency[str(boundary)] = domains
        if len(domains) == 1:
            exterior.append(boundary)
        elif len(domains) == 2:
            internal.append(boundary)
    return {"boundary_count": int(geom.getNBoundaries()), "domain_count": int(geom.getNDomains()),
            "boundary_adjacent_domains": adjacency, "exterior_boundaries": exterior,
            "internal_boundaries": internal, "invalid_boundary_queries": invalid}


def connectivity_from_adjacency(adjacency: dict[str, Any]) -> dict[str, Any]:
    domains = set(range(1, int(adjacency["domain_count"]) + 1))
    graph = {domain: set() for domain in domains}
    for boundary in adjacency["internal_boundaries"]:
        linked = adjacency["boundary_adjacent_domains"][str(boundary)]
        if len(linked) == 2:
            graph[linked[0]].add(linked[1])
            graph[linked[1]].add(linked[0])
    seen: set[int] = set()
    components: list[list[int]] = []
    for start in sorted(domains):
        if start in seen:
            continue
        stack = [start]
        component: list[int] = []
        seen.add(start)
        while stack:
            current = stack.pop()
            component.append(current)
            for nxt in graph[current] - seen:
                seen.add(nxt)
                stack.append(nxt)
        components.append(sorted(component))
    return {"component_count": len(components), "components": components,
            "domain_graph": {str(key): sorted(value) for key, value in graph.items()},
            "connected": len(components) == 1}


def entity_area(geom, entities: Iterable[int]) -> float:
    measure = geom.measureFinal()
    measure.selection().geom("geom1", 2)
    measure.selection().set([int(value) for value in entities])
    return float(measure.getArea())


def entity_volume(geom, entities: Iterable[int]) -> float:
    measure = geom.measureFinal()
    measure.selection().geom("geom1", 3)
    measure.selection().set([int(value) for value in entities])
    return float(measure.getVolume())


def boundary_record(geom, boundary: int) -> dict[str, Any]:
    measure = geom.measureFinal()
    measure.selection().geom("geom1", 2)
    measure.selection().set([int(boundary)])
    bounds = [float(value) for value in measure.getBoundingBox()]
    return {
        "boundary": int(boundary),
        "adjacent_domains": [int(value) for value in geom.getAdj(2, 3, boundary)],
        "area_m2": float(measure.getArea()),
        "bounding_box_m": bounds,
        "center_m": [(bounds[0]+bounds[1])/2, (bounds[2]+bounds[3])/2, (bounds[4]+bounds[5])/2],
    }


def resolve_feature_domain_selections(comp, feature_tags: list[str]) -> tuple[list[str], list[str]]:
    actual_tags = [str(tag) for tag in comp.selection().tags()]
    resolved: list[str] = []
    for feature_tag in feature_tags:
        matches = [tag for tag in actual_tags if feature_tag in tag and tag.endswith("_dom")]
        if len(matches) != 1:
            raise RuntimeError(
                f"Cannot uniquely resolve feature-derived domain selection for {feature_tag}; "
                f"matches={matches}; actual selection tags={actual_tags}"
            )
        resolved.append(matches[0])
    return actual_tags, resolved


def add_union_selection(comp, tag: str, input_tags: list[str]) -> None:
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    selection = comp.selection().create(tag, "Union")
    selection.geom("geom1", 3)
    selection.set("input", input_tags)


def rounded_cavity_volume_m3(length_mm: float, width_mm: float) -> float:
    radius_mm = min(1.2, width_mm/4)
    area_mm2 = length_mm*width_mm - (4-np.pi)*radius_mm**2
    return area_mm2*1e-6*AIR_H


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
    # COMSOL's default Form Union retains interior boundaries.  The invalid
    # implicit-finalization intbnd setter is intentionally not used here.
    geom.run()

    eps = 2e-7
    bounds_N = (-0.0101, 0.0101, 0.1169, 0.1171, AIR_Z0-eps, AIR_Z0+AIR_H+eps)
    bounds_S = (-0.0101, 0.0101, -0.1171, -0.1169, AIR_Z0-eps, AIR_Z0+AIR_H+eps)
    add_box_selection(comp, "bnd_port_N", 2, bounds_N, "inside")
    add_box_selection(comp, "bnd_port_S", 2, bounds_S, "inside")
    add_box_selection(comp, "bnd_mic_face", 2, (-MIC_FACE_R-eps, MIC_FACE_R+eps, -MIC_FACE_R-eps, MIC_FACE_R+eps, MIC_FACE_Z-eps, MIC_FACE_Z+eps), "inside")
    add_box_selection(comp, "dom_all", 3, (-0.0201, 0.0201, -0.1171, 0.1171, MIC_FACE_Z-eps, AIR_Z0+AIR_H+eps))
    hr03_features = ["N_HR03_cavity_radial", "N_HR03_cavity_tangent"] + [f"N_HR03_cavity_corner{i}" for i in range(1, 5)]
    south_features = [f"S_{south_label}_cavity_radial", f"S_{south_label}_cavity_tangent"] + [f"S_{south_label}_cavity_corner{i}" for i in range(1, 5)]
    actual_selection_tags, hr03_output_tags = resolve_feature_domain_selections(comp, hr03_features)
    actual_selection_tags_south, south_output_tags = resolve_feature_domain_selections(comp, south_features)
    if actual_selection_tags_south != actual_selection_tags:
        raise RuntimeError("Component selection tags changed during feature-output resolution")
    add_union_selection(comp, "dom_hr03_cavity", hr03_output_tags)
    add_union_selection(comp, "dom_south_cavity", south_output_tags)
    pr = MIX_R if kind == "MIX_CONTROL" else PLENUM_R
    add_box_selection(comp, "dom_plenum", 3, (-pr-eps, pr+eps, -pr-eps, pr+eps, AIR_Z0-eps, AIR_Z0+AIR_H+eps), "inside")
    geom.run()

    nport, sport, mic = (selection_entities(comp, x) for x in ("bnd_port_N", "bnd_port_S", "bnd_mic_face"))
    if not nport or not sport or not mic:
        raise RuntimeError(f"Empty required boundary selection N={nport} S={sport} mic={mic}")
    adjacency = boundary_adjacency(geom)
    if adjacency["invalid_boundary_queries"]:
        raise RuntimeError(f"Invalid boundary adjacency queries: {adjacency['invalid_boundary_queries']}")
    all_ext = adjacency["exterior_boundaries"]
    walls = sorted(set(all_ext) - set(nport) - set(sport) - set(mic))
    set_explicit(comp, "bnd_walls", 2, walls)
    connectivity = connectivity_from_adjacency(adjacency)
    nport_records = [boundary_record(geom, value) for value in nport]
    sport_records = [boundary_record(geom, value) for value in sport]
    expected_port_area = 20.0e-3*AIR_H
    hr03_domains = selection_entities(comp, "dom_hr03_cavity")
    south_domains = selection_entities(comp, "dom_south_cavity")
    plenum_domains = selection_entities(comp, "dom_plenum")
    expected_hr03_volume = rounded_cavity_volume_m3(HR["HR03"]["cavity_length"], HR["HR03"]["cavity_width"])
    expected_south_volume = rounded_cavity_volume_m3(HR[south_label]["cavity_length"], HR[south_label]["cavity_width"])
    actual_hr03_volume = entity_volume(geom, hr03_domains)
    actual_south_volume = entity_volume(geom, south_domains)
    cavity_audit = {
        "actual_component_selection_tags_before_union": actual_selection_tags,
        "feature_primitives": {"hr03": hr03_features, "south": south_features},
        "feature_output_selection_tags": {"hr03": hr03_output_tags, "south": south_output_tags},
        "domains": {"dom_hr03_cavity": hr03_domains, "dom_south_cavity": south_domains, "dom_plenum": plenum_domains},
        "nonempty": bool(hr03_domains and south_domains),
        "mutually_disjoint": set(hr03_domains).isdisjoint(south_domains),
        "plenum_excluded": set(hr03_domains+south_domains).isdisjoint(plenum_domains),
        "volume_m3": {"hr03_actual": actual_hr03_volume, "hr03_analytic": expected_hr03_volume,
                      "south_actual": actual_south_volume, "south_analytic": expected_south_volume},
        "volume_relative_error": {"hr03": actual_hr03_volume/expected_hr03_volume-1,
                                  "south": actual_south_volume/expected_south_volume-1},
    }
    cavity_audit["pass"] = bool(cavity_audit["nonempty"] and cavity_audit["mutually_disjoint"]
                                and cavity_audit["plenum_excluded"]
                                and abs(cavity_audit["volume_relative_error"]["hr03"]) <= 0.01
                                and abs(cavity_audit["volume_relative_error"]["south"]) <= 0.01)
    selection_audit = {
        "bnd_port_N": nport, "bnd_port_S": sport, "bnd_mic_face": mic, "bnd_walls": walls,
        "port_N_area_m2": entity_area(geom, nport), "port_S_area_m2": entity_area(geom, sport),
        "port_boundary_records": {"N": nport_records, "S": sport_records},
        "microphone_area_m2": entity_area(geom, mic),
        "all_required_nonempty": all((nport, sport, mic, walls)),
        "walls_all_exterior": set(walls).issubset(set(all_ext)),
        "internal_boundaries_excluded_from_walls": set(adjacency["internal_boundaries"]).isdisjoint(walls),
        "ports_excluded_from_walls": set(nport + sport).isdisjoint(walls),
        "walls_equal_all_exterior_except_ports_and_mic": set(walls) == set(all_ext)-set(nport)-set(sport)-set(mic),
        "identity_checks": {
            "N_port_expected_y_mm": 117.0, "S_port_expected_y_mm": -117.0,
            "expected_port_area_m2": expected_port_area,
            "port_area_relative_error_max": max(abs(entity_area(geom, nport)/expected_port_area-1), abs(entity_area(geom, sport)/expected_port_area-1)),
            "one_boundary_each": len(nport) == 1 and len(sport) == 1,
            "one_adjacent_domain_each": all(len(record["adjacent_domains"]) == 1 for record in nport_records+sport_records),
            "centres_at_plus_minus_117_mm": (len(nport_records) == 1 and len(sport_records) == 1
                and abs(nport_records[0]["center_m"][1]-0.117) <= 1e-8
                and abs(sport_records[0]["center_m"][1]+0.117) <= 1e-8),
            "microphone_expected_z_mm": 1.0, "microphone_expected_diameter_mm": 8.8,
            "microphone_area_relative_error": entity_area(geom, mic)/(np.pi*MIC_FACE_R**2)-1,
        },
    }
    port_identity_pass = bool(selection_audit["identity_checks"]["one_boundary_each"]
                              and selection_audit["identity_checks"]["one_adjacent_domain_each"]
                              and selection_audit["identity_checks"]["centres_at_plus_minus_117_mm"]
                              and selection_audit["identity_checks"]["port_area_relative_error_max"] <= 0.005)
    selection_audit["port_identity_pass"] = port_identity_pass
    if not (selection_audit["all_required_nonempty"] and selection_audit["walls_all_exterior"]
            and selection_audit["internal_boundaries_excluded_from_walls"]
            and selection_audit["ports_excluded_from_walls"]
            and selection_audit["walls_equal_all_exterior_except_ports_and_mic"]
            and connectivity["connected"] and port_identity_pass and cavity_audit["pass"]):
        raise RuntimeError({"selection_audit": selection_audit, "cavity_audit": cavity_audit, "connectivity": connectivity})

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
    cavity_audit["integration_operators"] = {
        "intop_hr03": {"selection": "dom_hr03_cavity", "domains": selection_entities(comp, "dom_hr03_cavity")},
        "intop_south": {"selection": "dom_south_cavity", "domains": selection_entities(comp, "dom_south_cavity")},
    }
    cavity_audit["integration_binding_pass"] = bool(
        cavity_audit["integration_operators"]["intop_hr03"]["domains"] == hr03_domains
        and cavity_audit["integration_operators"]["intop_south"]["domains"] == south_domains
    )

    physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "8000[Hz]")
    mesh = comp.mesh().create("mesh1")
    mesh.automatic(True)
    mesh.autoMeshSize(mesh_size)
    mesh.run()
    mesh_stats = {"automatic_level": mesh_size, "maximum_frequency_hz": 8000.0,
                  "elements": int(mesh.getNumElem()), "vertices": int(mesh.getNumVertex()),
                  "minimum_quality": float(mesh.getMinQuality()), "mean_quality": float(mesh.getMeanQuality()),
                  "pass": int(mesh.getNumElem()) > 0 and float(mesh.getMinQuality()) > 0}
    study = java.study().create("std_freq")
    step = study.create("freq", "Frequency")
    step.set("plist", " ".join(f"{v:.15g}" for v in frequencies))
    return model, {
        "selections": {x: selection_entities(comp, x) for x in ("bnd_port_N", "bnd_port_S", "bnd_mic_face", "dom_all", "dom_hr03_cavity", "dom_south_cavity", "dom_plenum", "bnd_walls")},
        "selection_audit": selection_audit, "cavity_domain_selection_audit": cavity_audit,
        "boundary_adjacency": adjacency,
        "air_domain_connectivity": connectivity, "mesh": mesh_stats,
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


def write_sparse_csv(path: Path, values: dict[str, np.ndarray]) -> None:
    rows = []
    for index, frequency in enumerate(values["frequency"]):
        pressure = values["mic"][index]
        rows.append({"grid_index": index, "frequency_hz": f"{frequency:.15g}",
                     "mic_real": f"{pressure.real:.17g}", "mic_imag": f"{pressure.imag:.17g}",
                     "mic_magnitude": f"{abs(pressure):.17g}",
                     "mic_phase_deg": f"{np.degrees(np.angle(pressure)):.17g}"})
    atomic_csv(path, rows, ["grid_index", "frequency_hz", "mic_real", "mic_imag", "mic_magnitude", "mic_phase_deg"])


def run_smoke(client: mph.Client) -> dict[str, Any]:
    model, audit = build_model(client, "ISO_CODED", "N", 7, SMOKE_FREQ, "TRANS0_RETRY02_ISO_CODED_N")
    atomic_json(OUT / "geometry_selection_audit.json", audit)
    atomic_json(OUT / "cavity_domain_selection_audit.json", audit["cavity_domain_selection_audit"])
    atomic_json(OUT / "mesh_statistics.json", audit["mesh"])
    study_tags = [str(tag) for tag in model.java.study().tags()]
    if "std_freq" not in study_tags:
        raise RuntimeError(
            f"Java study tag std_freq missing; available tags={study_tags}"
        )

    study = model.java.study("std_freq")
    feature_tags = [str(tag) for tag in study.feature().tags()]
    if "freq" not in feature_tags:
        raise RuntimeError(
            f"Frequency feature tag freq missing; available tags={feature_tags}"
        )
    study_audit = {"java_study_tags": study_tags, "study_tag": "std_freq",
                   "study_label": str(study.label()), "feature_tags": feature_tags,
                   "selected_feature_tag": "freq", "tag_label_mixed": False}
    atomic_json(OUT / "study_tag_label_audit.json", study_audit)
    start = time.time()
    study.run()
    values = evaluate(model, len(SMOKE_FREQ))
    if np.allclose(values["mic"], 0.0):
        raise RuntimeError("Microphone complex response is all zero")
    path = OUT / "TRANS0_RETRY02_ISO_CODED_N.mph"
    model.save(path)
    write_sparse_csv(OUT / "sparse_smoke_results.csv", values)
    energy_rows = []
    for index, frequency in enumerate(values["frequency"]):
        energy_rows.append({"grid_index": index, "frequency_hz": f"{frequency:.15g}",
                            "hr03_energy_j": f"{values['e_hr03'][index]:.17g}",
                            "south_energy_j": f"{values['e_south'][index]:.17g}",
                            "plenum_energy_j": f"{values['e_plenum'][index]:.17g}"})
    atomic_csv(OUT / "cavity_energy_smoke.csv", energy_rows,
               ["grid_index", "frequency_hz", "hr03_energy_j", "south_energy_j", "plenum_energy_j"])
    before = values["mic"].copy()
    client.remove(model)
    loaded = client.load(path)
    after_values = evaluate(loaded, len(SMOKE_FREQ))
    after = after_values["mic"]
    maximum_difference = float(np.max(np.abs(before-after)))
    reload_validation = {"saved_model": path.name, "saved_sha256": sha256(path),
                         "removed_from_memory_before_reload": True, "reloaded_in_comsol_6_4": True,
                         "frequency_axis_equal": bool(np.array_equal(values["frequency"], after_values["frequency"])),
                         "maximum_complex_pressure_difference_pa": maximum_difference,
                         "tolerance_pa": 1e-12, "pass": maximum_difference <= 1e-12}
    atomic_json(OUT / "reload_validation.json", reload_validation)
    client.remove(loaded)
    atomic_json(OUT / "geometry_selection_audit.json", audit)
    atomic_json(OUT / "cavity_domain_selection_audit.json", audit["cavity_domain_selection_audit"])
    atomic_json(OUT / "mesh_statistics.json", audit["mesh"])
    result = {"success": True, "elapsed_s": time.time()-start, "frequencies_hz": values["frequency"].tolist(),
              "mic_real": values["mic"].real.tolist(), "mic_imag": values["mic"].imag.tolist(),
              "finite": bool(np.all(np.isfinite(values["mic"]))), "nonzero": bool(not np.allclose(values["mic"], 0.0)),
              "mph": path.name, "mph_sha256": sha256(path), "reload": reload_validation,
              "study": study_audit, **audit}
    atomic_json(OUT / "preflight_execution_result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
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

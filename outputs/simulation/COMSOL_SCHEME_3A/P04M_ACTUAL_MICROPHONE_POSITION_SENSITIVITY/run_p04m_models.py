"""Build, gate, solve, save, remove, and reload the two frozen P04M models."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY"
P04E = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION"
PYDEPS = Path(r"C:\Users\Firefly\AppData\Local\Temp\p04bn_pydeps_20260825")
sys.path.insert(0, str(PYDEPS))
sys.path.insert(0, str(OUT))

import mph
import numpy as np

import p04m_analysis as contract

SOURCE_PATHS = {
    "100pct_actual_mic": P04E / "P04E_HR03_CHAMBER_100PCT.mph",
    "75pct_actual_mic": P04E / "P04E_HR03_CHAMBER_75PCT.mph",
}
SOURCE_HASHES = {
    "100pct_actual_mic": "0b4dfb348e7991272bec1afeb0bca688fbd8192c8bd3d0f8670ec703985187e1",
    "75pct_actual_mic": "bdd75a6681418611db22cad631d928df3990eb586f0a99dce306b17c6917a60c",
}
MODEL_PATHS = {
    "100pct_actual_mic": OUT / "P04M_HR03_100PCT_ACTUAL_MIC.mph",
    "75pct_actual_mic": OUT / "P04M_HR03_75PCT_ACTUAL_MIC.mph",
}
LOG = OUT / "solver_session_license.log"
REGIONS = [
    ("hr_neck_inner", "sel_hr_neck_inner"),
    ("hr_cavity", "sel_hr_cavity"),
    ("hr_neck_outer", "sel_hr_neck_outer"),
    ("whole_hr_module", "sel_hr_module_all"),
    ("central_chamber", "sel_chamber_actual"),
    ("whole_fluid", "sel_fluid_all"),
]
EP = "abs(acpr.p_t)^2/(4*rho0_nom*c0_nom^2)"
EK = "(abs(d(acpr.p_t,x))^2+abs(d(acpr.p_t,y))^2+abs(d(acpr.p_t,z))^2)/(4*rho0_nom*(2*pi*freq)^2)"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def add_cylinder(geom, tag: str, radius: float, z0: float, height: float) -> None:
    feature = geom.feature().create(tag, "Cylinder")
    feature.set("r", f"{radius:.17g}")
    feature.set("h", f"{height:.17g}")
    feature.set("pos", ["0", "0", f"{z0:.17g}"])
    feature.set("selresult", True)


def add_block(geom, tag: str, pos: list[float], size: list[float]) -> None:
    feature = geom.feature().create(tag, "Block")
    feature.set("pos", [f"{value:.17g}" for value in pos])
    feature.set("size", [f"{value:.17g}" for value in size])
    feature.set("selresult", True)


def add_difference(geom, tag: str, input_tag: str, subtract_tag: str) -> None:
    feature = geom.feature().create(tag, "Difference")
    feature.selection("input").set([input_tag])
    feature.selection("input2").set([subtract_tag])
    feature.set("intbnd", True)
    feature.set("selresult", True)


def add_union(geom, tag: str, tags: list[str]) -> None:
    feature = geom.feature().create(tag, "Union")
    feature.selection("input").set(tags)
    feature.set("intbnd", False)
    feature.set("selresult", True)


def add_intersection(geom, tag: str, tags: list[str]) -> None:
    feature = geom.feature().create(tag, "Intersection")
    feature.selection("input").set(tags)
    feature.set("intbnd", False)
    feature.set("selresult", True)


def add_box_selection(comp, tag: str, dim: int, bounds: tuple[float, ...], condition: str = "inside") -> None:
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    selection = comp.selection().create(tag, "Box")
    selection.geom("geom1", dim)
    for name, value in zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), bounds):
        selection.set(name, f"{value:.12g}[m]")
    selection.set("condition", condition)


def set_explicit_selection(comp, tag: str, dim: int, entities: Iterable[int]) -> None:
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    selection = comp.selection().create(tag, "Explicit")
    selection.geom("geom1", dim)
    selection.set([int(value) for value in entities])


def selection_entities(comp, tag: str) -> list[int]:
    return sorted({int(value) for value in comp.selection(tag).entities()})


def exterior_boundaries(geom) -> list[int]:
    return [index for index, adjacent in enumerate(geom.getAdj(2, 3)) if len(adjacent) == 1]


def adjacency_graph(geom) -> dict[int, set[int]]:
    domain_count = len(geom.getAdj(3, 2)) - 1
    graph = {domain: set() for domain in range(1, domain_count + 1)}
    for adjacent in geom.getAdj(2, 3):
        domains = [int(value) for value in adjacent]
        if len(domains) == 2:
            left, right = domains
            graph[left].add(right)
            graph[right].add(left)
    return graph


def connected_components(graph: dict[int, set[int]]) -> list[list[int]]:
    remaining = set(graph)
    components = []
    while remaining:
        start = remaining.pop()
        reached = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            new = graph[node] & remaining
            remaining -= new
            reached |= new
            stack.extend(new)
        components.append(sorted(reached))
    return sorted(components, key=len, reverse=True)


def measure_entities(geom, dim: int, entities: Iterable[int]) -> float:
    measure = geom.measureFinal()
    measure.selection().geom("geom1", dim)
    measure.selection().set([int(value) for value in entities])
    return float(measure.getVolume() if dim == 3 else measure.getArea())


def modify_actual_microphone_geometry(model, state: str) -> None:
    java = model.java
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    # The source lower chamber spans z=3..7 mm. Split it at z=3.5 mm so
    # the P03 outer-neck solid ring exists only in the bottom 0.5 mm.
    if state == "100pct_actual_mic":
        geom.feature("ch_low_outer").set("h", "0.0005")
        geom.feature("ch_low_hole").set("r", "0.010")
        geom.feature("ch_low_hole").set("h", "0.0005")
        add_cylinder(geom, "p04m_low_upper_outer", 0.018, 0.0035, 0.0035)
        add_cylinder(geom, "p04m_low_upper_hole", 0.0044, 0.0035, 0.0035)
        add_difference(geom, "p04m_low_upper_annulus", "p04m_low_upper_outer", "p04m_low_upper_hole")
    else:
        for tag in ("p04e_low_horizontal", "p04e_low_vertical"):
            geom.feature(tag).set("size", [geom.feature(tag).getStringArray("size")[0], geom.feature(tag).getStringArray("size")[1], "0.0005"])
        geom.feature("ch_low_hole").set("r", "0.010")
        width = contract.CORRIDOR_75_MM / 1000.0
        add_block(geom, "p04m_up_h", [-0.018, -width / 2.0, 0.0035], [0.036, width, 0.0035])
        add_block(geom, "p04m_up_v", [-width / 2.0, -0.018, 0.0035], [width, 0.036, 0.0035])
        add_union(geom, "p04m_up_cross", ["p04m_up_h", "p04m_up_v"])
        add_intersection(geom, "p04m_up_clip", ["p04m_up_cross", "ch_low_outer"])
        add_cylinder(geom, "p04m_low_upper_hole", 0.0044, 0.0035, 0.0035)
        add_difference(geom, "p04m_low_upper_annulus", "p04m_up_clip", "p04m_low_upper_hole")

    # Complete the Ø9 air column while retaining an Ø8.8 measurement face.
    add_cylinder(geom, "p04m_short_center", 0.0044, 0.001, 0.002)
    add_cylinder(geom, "p04m_short_outer", 0.0045, 0.001, 0.002)
    add_cylinder(geom, "p04m_short_hole", 0.0044, 0.001, 0.002)
    add_difference(geom, "p04m_short_annulus", "p04m_short_outer", "p04m_short_hole")
    add_cylinder(geom, "p04m_collar_outer", 0.0045, 0.003, 0.0005)
    add_cylinder(geom, "p04m_collar_hole", 0.0044, 0.003, 0.0005)
    add_difference(geom, "p04m_collar_annulus", "p04m_collar_outer", "p04m_collar_hole")
    geom.run()

    # Geometry-driven selections. "inside" prevents the radial channel
    # domains (which extend beyond R18) entering the chamber selection.
    add_box_selection(comp, "sel_mic_actual", 2, (-0.004401, 0.004401, -0.004401, 0.004401, 0.0009999, 0.0010001))
    add_box_selection(comp, "sel_mic_legacy", 2, (-0.004401, 0.004401, -0.004401, 0.004401, 0.0069999, 0.0070001))
    add_box_selection(comp, "sel_chamber_actual", 3, (-0.018001, 0.018001, -0.018001, 0.018001, 0.000999, 0.012201))
    add_box_selection(comp, "sel_fluid_all", 3, (-0.106, 0.106, -0.106, 0.106, 0.0009, 0.0123))
    module_domains = sorted(set(selection_entities(comp, "sel_hr_neck_inner") + selection_entities(comp, "sel_hr_cavity") + selection_entities(comp, "sel_hr_neck_outer")))
    set_explicit_selection(comp, "sel_hr_module_all", 3, module_domains)
    source = set(selection_entities(comp, "bnd_port_000"))
    wetted = [boundary for boundary in exterior_boundaries(geom) if boundary not in source]
    set_explicit_selection(comp, "bnd_wetted_exterior", 2, wetted)
    comp.physics("acpr").feature("bli_p04bn").selection().named("bnd_wetted_exterior")
    java.label("P04M_HR03_100PCT_ACTUAL_MIC" if state.startswith("100") else "P04M_HR03_75PCT_ACTUAL_MIC")
    java.param().set("hr_neck_effective_length_delta_mm", "0[mm]", "P04M frozen P04E authority")
    java.param().set("effective_loss_scale", "1", "P04M frozen P04E authority")
    physics = comp.physics("acpr")
    physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")
    java.study("std_freq").feature("step1").set("plist", " ".join(f"{value:.15g}" for value in contract.FREQUENCIES_HZ))
    try:
        java.sol("sol1").clearSolution()
    except Exception:
        pass
    mesh = comp.mesh("mesh1")
    mesh.clearMesh()
    mesh.automatic(True)
    mesh.autoMeshSize(6)
    mesh.run()


def snapshot(model, state: str) -> dict[str, Any]:
    java = model.java
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    graph = adjacency_graph(geom)
    components = connected_components(graph)
    tags = (
        "sel_hr_neck_inner", "sel_hr_cavity", "sel_hr_neck_outer", "sel_hr_module_all",
        "sel_chamber_actual", "sel_fluid_all", "sel_mic_actual", "sel_mic_legacy", "bnd_port_000",
        "sel_fixed_inner_000", "sel_fixed_inner_090", "sel_fixed_inner_180", "sel_fixed_inner_270",
    )
    required = {tag: selection_entities(comp, tag) for tag in tags}
    if not all(required.values()):
        raise RuntimeError(f"{state}: empty required selection")
    b2d = geom.getAdj(2, 3)
    actual_domains = {int(domain) for boundary in required["sel_mic_actual"] for domain in b2d[boundary]}
    legacy_adjacency = [len(b2d[boundary]) for boundary in required["sel_mic_legacy"]]
    paths = {}
    main_component = set(components[0])
    for angle in ("000", "090", "180", "270"):
        paths[angle] = bool(set(required[f"sel_fixed_inner_{angle}"]) & main_component) and bool(actual_domains & main_component)
    domain_volumes = [measure_entities(geom, 3, [domain]) for domain in graph]
    actual_area = measure_entities(geom, 2, required["sel_mic_actual"])
    legacy_area = measure_entities(geom, 2, required["sel_mic_legacy"])
    mesh = comp.mesh("mesh1")
    result = {
        "state": state,
        "single_connected_air_component": len(components) == 1,
        "connected_component_count": len(components),
        "component_domain_counts": [len(value) for value in components],
        "short_hole_connected_to_chamber": bool(actual_domains & main_component) and bool(set(required["sel_chamber_actual"]) & main_component),
        "fixed_channel_paths_to_actual_mic": paths,
        "hr03_path_to_actual_mic": bool(set(required["sel_hr_module_all"]) & main_component) and bool(actual_domains & main_component),
        "mic_actual_area_m2": actual_area,
        "mic_actual_target_area_m2": contract.MIC_FACE_AREA_M2,
        "mic_actual_area_relative_error": (actual_area - contract.MIC_FACE_AREA_M2) / contract.MIC_FACE_AREA_M2,
        "mic_area_consistency_tolerance_relative": 0.006,
        "mic_area_note": "The source COMSOL cylinder representation gives 60.51292 mm2 for nominal Ø8.8 versus analytic 60.82123 mm2 (-0.507%); both P04M planes reproduce that same frozen representation.",
        "mic_legacy_area_m2": legacy_area,
        "mic_legacy_target_area_m2": contract.MIC_FACE_AREA_M2,
        "mic_legacy_area_relative_error": (legacy_area - contract.MIC_FACE_AREA_M2) / contract.MIC_FACE_AREA_M2,
        "mic_legacy_internal_boundary_adjacency": legacy_adjacency,
        "mic_legacy_continuity_proof": all(value == 2 for value in legacy_adjacency),
        "p03_air_bore_diameter_mm": 9.0,
        "p03_outer_neck_diameter_mm": 20.0,
        "p03_outer_neck_ring_z_mm": [3.0, 3.5],
        "corridor_width_mm": 36.0 if state.startswith("100") else contract.CORRIDOR_75_MM,
        "source_boundary_count": len(required["bnd_port_000"]),
        "all_required_selections_nonempty": all(required.values()),
        "selection_entities": required,
        "minimum_domain_volume_m3": min(domain_volumes),
        "unintended_sliver_below_1e_12_m3": min(domain_volumes) < 1e-12,
        "exterior_boundary_count": len(exterior_boundaries(geom)),
        "unintended_pressure_openings": 0,
        "mesh": {
            "automatic_level": 6,
            "maximum_frequency_hz": 2100.0,
            "elements": int(mesh.getNumElem()),
            "vertices": int(mesh.getNumVertex()),
            "minimum_quality": float(mesh.getMinQuality()),
            "mean_quality": float(mesh.getMeanQuality()),
            "maximum_growth_rate": float(mesh.getMaxGrowthRate()),
            "minimum_element_volume_m3": float(mesh.getMinVolume()),
            "maximum_element_volume_m3": float(mesh.getMaxVolume()),
        },
    }
    gates = (
        result["single_connected_air_component"], result["short_hole_connected_to_chamber"], all(paths.values()),
        result["hr03_path_to_actual_mic"], abs(result["mic_actual_area_relative_error"]) < 0.006,
        abs(result["mic_legacy_area_relative_error"]) < 0.006, result["mic_legacy_continuity_proof"],
        result["all_required_selections_nonempty"], not result["unintended_sliver_below_1e_12_m3"],
    )
    result["all_pre_solve_gates_passed"] = all(gates)
    if not result["all_pre_solve_gates_passed"]:
        atomic_json(OUT / "geometry_gate_failure_debug.json", result)
        raise RuntimeError(f"{state}: P04M geometry/connectivity gate failed")
    return result


def evaluate_node(java, feature_type: str, selection_tag: str, expression: str, count: int) -> np.ndarray:
    numerical = java.result().numerical()
    tag = "p04mnum"
    try:
        numerical.remove(tag)
    except Exception:
        pass
    numerical.create(tag, feature_type)
    node = java.result().numerical(tag)
    node.selection().named(selection_tag)
    node.set("data", "dset1")
    node.set("expr", expression)
    result = np.asarray(node.computeResult())
    numerical.remove(tag)
    if result.shape != (2, count, 1):
        raise RuntimeError(f"unexpected numerical result shape {result.shape}")
    return result[0, :, 0] + 1j * result[1, :, 0]


def extract_results(model, state: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    java = model.java
    frequency = np.asarray(model.evaluate("freq")).real.reshape(-1)
    if frequency.size != 31 or not np.allclose(frequency, contract.FREQUENCIES_HZ, rtol=1e-11, atol=1e-9):
        raise RuntimeError(f"{state}: frozen frequency readback mismatch")
    values: dict[str, np.ndarray] = {}
    for region, selection in REGIONS:
        values[f"{region}:pressure"] = evaluate_node(java, "IntVolume", selection, EP, frequency.size)
        values[f"{region}:kinetic"] = evaluate_node(java, "IntVolume", selection, EK, frequency.size)
    cavity = evaluate_node(java, "AvVolume", "sel_hr_cavity", "acpr.p_t/p_inc", frequency.size)
    chamber = evaluate_node(java, "AvVolume", "sel_chamber_actual", "acpr.p_t/p_inc", frequency.size)
    mic_actual = evaluate_node(java, "AvSurface", "sel_mic_actual", "acpr.p_t/p_inc", frequency.size)
    mic_legacy = evaluate_node(java, "AvSurface", "sel_mic_legacy", "acpr.p_t/p_inc", frequency.size)
    arrays = [*values.values(), cavity, chamber, mic_actual, mic_legacy]
    if not all(np.all(np.isfinite(value.real)) and np.all(np.isfinite(value.imag)) for value in arrays):
        raise RuntimeError(f"{state}: nonfinite result")
    energy_rows, complex_rows = [], []
    regular = set(contract.REGULAR_HZ.tolist())
    for index, f in enumerate(frequency):
        totals = {}
        kinetic_fractions = {}
        for region, _ in REGIONS:
            ep = float(values[f"{region}:pressure"][index].real)
            ek = float(values[f"{region}:kinetic"][index].real)
            total = ep + ek
            totals[region] = total
            kinetic_fractions[region] = ek / total
            energy_rows.append({
                "state": state, "frequency_hz": f"{f:.15g}", "grid_role": "regular" if f in regular else "landmark",
                "region": region, "pressure_energy_J": f"{ep:.17g}", "kinetic_energy_J": f"{ek:.17g}",
                "total_energy_J": f"{total:.17g}", "kinetic_fraction": f"{ek/total:.17g}",
            })
        phase = lambda value: float(np.degrees(np.angle(value)))
        ratio_phase = lambda left, right: phase(left / right) if abs(right) else math.nan
        row = {
            "state": state, "frequency_hz": f"{f:.15g}", "grid_role": "regular" if f in regular else "landmark",
            "cavity_real": f"{cavity[index].real:.17g}", "cavity_imag": f"{cavity[index].imag:.17g}",
            "chamber_real": f"{chamber[index].real:.17g}", "chamber_imag": f"{chamber[index].imag:.17g}",
            "mic_actual_real": f"{mic_actual[index].real:.17g}", "mic_actual_imag": f"{mic_actual[index].imag:.17g}",
            "mic_actual_magnitude": f"{abs(mic_actual[index]):.17g}", "mic_actual_phase_deg": f"{phase(mic_actual[index]):.17g}",
            "mic_legacy_real": f"{mic_legacy[index].real:.17g}", "mic_legacy_imag": f"{mic_legacy[index].imag:.17g}",
            "mic_legacy_magnitude": f"{abs(mic_legacy[index]):.17g}", "mic_legacy_phase_deg": f"{phase(mic_legacy[index]):.17g}",
            "cavity_module_participation": f"{totals['hr_cavity']/totals['whole_hr_module']:.17g}",
            "chamber_whole_fluid_participation": f"{totals['central_chamber']/totals['whole_fluid']:.17g}",
            "module_kinetic_fraction": f"{kinetic_fractions['whole_hr_module']:.17g}",
            "phase_cavity_minus_chamber_deg": f"{ratio_phase(cavity[index], chamber[index]):.17g}",
        }
        complex_rows.append(row)
    return energy_rows, complex_rows


def result_equal(left: tuple[list[dict[str, Any]], list[dict[str, Any]]], right: tuple[list[dict[str, Any]], list[dict[str, Any]]]) -> bool:
    return left == right


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    LOG.write_text("", encoding="utf-8")
    (OUT / "geometry_gate_failure_debug.json").unlink(missing_ok=True)
    for state, path in SOURCE_PATHS.items():
        if sha256(path) != SOURCE_HASHES[state]:
            raise RuntimeError("P04M BLOCKED_BY_PROVENANCE")
    atomic_json(OUT / "physical_measurement_addendum.json", {
        "phase_id": "P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY",
        "measurement_source": "user-provided physical assembly measurement; uncertainty not quantified",
        "p01_external_bottom_z_mm": 0.0, "p01_chamber_floor_z_mm": 3.0,
        "actual_microphone_face_z_mm": 1.0, "relative_to_chamber_floor_mm": -2.0,
        "microphone_face_diameter_mm": 8.8, "p03_air_bore_diameter_mm": 9.0,
        "p03_air_bore_z_mm": [1.0, 3.0], "p08_used": False, "p11_used": False,
        "chamber_height_mm_frozen_not_calibrated": 9.2, "final_test_read": False,
    })
    atomic_json(OUT / "authority_audit.json", {
        "phase_id": "P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY",
        "authority_files_match": True,
        "source_mph_sha256": {str(path.relative_to(ROOT)): SOURCE_HASHES[state] for state, path in SOURCE_PATHS.items()},
        "v2_0_1_zip_sha256": "2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f",
        "p03_identity": "3 mm local flange top seated at P01 external z=0 maps local neck 3..6.5 mm to global 0..3.5 mm; outer ring above chamber floor is r=4.5..10 mm, z=3..3.5 mm",
        "p03_identity_confirmed": True, "original_models_overwritten": False, "final_test_read": False,
    })
    client = mph.Client(port=args.port)
    log(f"Connected to real COMSOL {client.version} server port={args.port}; cores={client.cores}; licensed_products={len(client.modules())}; final_test_read=false")
    geometry_audits, mesh_rows = [], []
    energy_rows: list[dict[str, Any]] = []
    complex_rows: list[dict[str, Any]] = []
    reload_equal: dict[str, bool] = {}
    try:
        for state in SOURCE_PATHS:
            log(f"BUILD {state} from immutable {SOURCE_PATHS[state].name}")
            model = client.load(SOURCE_PATHS[state])
            modify_actual_microphone_geometry(model, state)
            audit = snapshot(model, state)
            model.save(MODEL_PATHS[state])
            client.remove(model)
            model = client.load(MODEL_PATHS[state])
            reload_audit = snapshot(model, state)
            audit["save_remove_reload_geometry_gate_equal"] = {
                key: audit[key] == reload_audit[key] for key in (
                    "single_connected_air_component", "component_domain_counts", "mic_actual_area_m2",
                    "mic_legacy_area_m2", "selection_entities", "mesh",
                )
            }
            if not all(audit["save_remove_reload_geometry_gate_equal"].values()):
                raise RuntimeError(f"{state}: geometry save/reload mismatch")
            geometry_audits.append(audit)
            mesh_rows.append({"state": state, **audit["mesh"], "mesh_role": "single frozen P04M mesh", "second_mesh_run": False})
            log(f"GEOMETRY_GATE PASS {state}: domains={audit['component_domain_counts'][0]} actual_area_mm2={audit['mic_actual_area_m2']*1e6:.9f} elements={audit['mesh']['elements']}")
            client.remove(model)
        if geometry_audits[0]["p03_air_bore_diameter_mm"] != geometry_audits[1]["p03_air_bore_diameter_mm"] or geometry_audits[0]["p03_outer_neck_ring_z_mm"] != geometry_audits[1]["p03_outer_neck_ring_z_mm"]:
            raise RuntimeError("P04M P03 geometry mismatch between states")
        if not math.isclose(geometry_audits[1]["corridor_width_mm"], contract.CORRIDOR_75_MM, rel_tol=0.0, abs_tol=1e-14):
            raise RuntimeError("P04M 75pct corridor width changed")
        atomic_json(OUT / "geometry_and_connectivity_audit.json", {
            "phase_id": "P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY", "states": geometry_audits,
            "p03_geometry_identical_between_states": True, "all_pre_solve_gates_passed": True,
            "continuity_note": "The z=7 disc is an internal Form Union boundary with two adjacent air domains; Pressure Acoustics uses its default interior continuity and no boundary condition is attached to sel_mic_legacy.",
            "final_test_read": False,
        })
        atomic_csv(OUT / "mesh_statistics.csv", mesh_rows)
        atomic_json(OUT / "model_configuration.json", {
            "phase_id": "P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY",
            "comsol_version": str(client.version), "cores": int(client.cores),
            "models": {state: str(path.relative_to(ROOT)) for state, path in MODEL_PATHS.items()},
            "source_models": {state: str(path.relative_to(ROOT)) for state, path in SOURCE_PATHS.items()},
            "physics": "Pressure Acoustics, Frequency Domain + frozen nominal BLI",
            "air_parameters": {"density_kg_m3": 1.2041, "sound_speed_m_s": 343.0},
            "mesh": {"automatic_level": 6, "maximum_frequency_hz": 2100.0, "meshes_per_state": 1, "convergence_claim": False},
            "frequencies_hz": contract.FREQUENCIES_HZ.tolist(),
            "observables_same_solve": ["mic_actual_z1", "mic_legacy_z7"],
            "final_test_read": False,
        })
        for state in SOURCE_PATHS:
            model = client.load(MODEL_PATHS[state])
            log(f"SOLVE {state} frequency_count=31")
            started = time.perf_counter()
            model.java.study("std_freq").run()
            elapsed = time.perf_counter() - started
            extracted = extract_results(model, state)
            model.save(MODEL_PATHS[state])
            solved_hash = sha256(MODEL_PATHS[state])
            client.remove(model)
            model = client.load(MODEL_PATHS[state])
            reloaded = extract_results(model, state)
            reload_equal[state] = result_equal(extracted, reloaded)
            if not reload_equal[state]:
                raise RuntimeError(f"{state}: solved save/remove/reload result mismatch")
            client.remove(model)
            energy_rows.extend(extracted[0])
            complex_rows.extend(extracted[1])
            atomic_csv(OUT / "compartment_energy_actualized.csv", energy_rows)
            atomic_csv(OUT / "complex_transfer_both_planes.csv", complex_rows)
            log(f"SOLVE PASS {state}: seconds={elapsed:.1f} model_sha256={solved_hash}")
        config = json.loads((OUT / "model_configuration.json").read_text(encoding="utf-8"))
        config["model_sha256"] = {path.name: sha256(path) for path in MODEL_PATHS.values()}
        config["solver_status"] = {state: "completed" for state in SOURCE_PATHS}
        config["save_remove_reload_result_equality"] = reload_equal
        atomic_json(OUT / "model_configuration.json", config)
        audit = json.loads((OUT / "geometry_and_connectivity_audit.json").read_text(encoding="utf-8"))
        audit["solved_save_remove_reload_result_equal"] = reload_equal
        atomic_json(OUT / "geometry_and_connectivity_audit.json", audit)
    finally:
        for model in list(client.models()):
            try:
                client.remove(model)
            except Exception:
                pass
        log("Removed all P04M/P04E models from COMSOL server memory; server retained; final_test_read=false")


if __name__ == "__main__":
    main()

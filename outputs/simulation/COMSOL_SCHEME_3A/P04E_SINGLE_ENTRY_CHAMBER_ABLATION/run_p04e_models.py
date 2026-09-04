"""Build, gate, solve, save, and reload the three frozen P04E models."""

from __future__ import annotations

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
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION"
AUTHORITY = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION/P04BN_HR03_PRODUCTION.mph"
sys.path.insert(0, r"C:\Users\Firefly\AppData\Local\Temp\p04bn_pydeps_20260825")
sys.path.insert(0, str(OUT))

import mph
import numpy as np

import p04e_analysis as analysis

CONTRACT_SHA256 = "2a4f9744319fea6378ab1247d7a885983eff0ed7b40ce7bbd1af46cb941c2a12"
AUTHORITY_SHA256 = "33bf573dddc0c0b163e7f0a5e177fc227d16aa541479606e971cb4a3a9398db7"
REGULAR = np.arange(1400.0, 2100.0 + 0.1, 25.0)
LANDMARKS = np.array([1646.88357862959, 1986.97249931757])
FREQUENCIES = np.array(sorted(np.concatenate((REGULAR, LANDMARKS))))
LOG = OUT / "solver_session_license.log"
MODEL_PATHS = {
    "100pct": OUT / "P04E_HR03_CHAMBER_100PCT.mph",
    "75pct": OUT / "P04E_HR03_CHAMBER_75PCT.mph",
    "50pct": OUT / "P04E_HR03_CHAMBER_50PCT.mph",
}
REGIONS = [
    ("hr_neck_inner", "sel_hr_neck_inner"),
    ("hr_cavity", "sel_hr_cavity"),
    ("hr_neck_outer", "sel_hr_neck_outer"),
    ("whole_hr_module", "sel_hr_module_all"),
    ("central_chamber", "sel_chamber"),
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
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def selection_entities(comp, tag: str) -> list[int]:
    return sorted({int(value) for value in comp.selection(tag).entities()})


def set_explicit_selection(comp, tag: str, dim: int, entities: Iterable[int]) -> None:
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    selection = comp.selection().create(tag, "Explicit")
    selection.geom("geom1", dim)
    selection.set([int(value) for value in entities])


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


def make_block(geom, tag: str, pos: list[float], size: list[float]) -> None:
    feature = geom.feature().create(tag, "Block")
    feature.set("pos", [f"{value:.17g}" for value in pos])
    feature.set("size", [f"{value:.17g}" for value in size])
    feature.set("selresult", True)


def modify_chamber(geom, width_mm: float) -> None:
    for tag in ("ch_low_annulus", "ch_up_annulus"):
        geom.feature().remove(tag)
    width = width_mm / 1000.0
    for layer, z0, height, outer, hole in (
        ("low", 0.003, 0.004, "ch_low_outer", "ch_low_hole"),
        ("up", 0.007, 0.0052, "ch_up_outer", "ch_up_hole"),
    ):
        h_tag, v_tag = f"p04e_{layer}_horizontal", f"p04e_{layer}_vertical"
        make_block(geom, h_tag, [-0.018, -width / 2.0, z0], [0.036, width, height])
        make_block(geom, v_tag, [-width / 2.0, -0.018, z0], [width, 0.036, height])
        union_tag = f"p04e_{layer}_cross"
        union = geom.feature().create(union_tag, "Union")
        union.selection("input").set([h_tag, v_tag])
        union.set("intbnd", False)
        clip_tag = f"p04e_{layer}_clip"
        clip = geom.feature().create(clip_tag, "Intersection")
        clip.selection("input").set([union_tag, outer])
        clip.set("intbnd", False)
        annulus_tag = f"p04e_{layer}_annulus"
        annulus = geom.feature().create(annulus_tag, "Difference")
        annulus.selection("input").set([clip_tag])
        annulus.selection("input2").set([hole])
        annulus.set("intbnd", True)
        annulus.set("selresult", True)
    geom.run()


def rebuild_dependent_selections(comp, geom) -> None:
    module_domains = sorted(set(selection_entities(comp, "sel_hr_neck_inner") + selection_entities(comp, "sel_hr_cavity") + selection_entities(comp, "sel_hr_neck_outer")))
    set_explicit_selection(comp, "sel_hr_module_all", 3, module_domains)
    source = set(selection_entities(comp, "bnd_port_000"))
    wetted = [boundary for boundary in exterior_boundaries(geom) if boundary not in source]
    set_explicit_selection(comp, "bnd_wetted_exterior", 2, wetted)
    comp.physics("acpr").feature("bli_p04bn").selection().named("bnd_wetted_exterior")


def configure_and_mesh(model, state: dict[str, Any]) -> None:
    java = model.java
    java.label(f"P04E_HR03_CHAMBER_{state['state'].upper()}")
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    if state["state"] != "100pct":
        modify_chamber(geom, float(state["corridor_width_mm"]))
    else:
        geom.run()
    rebuild_dependent_selections(comp, geom)
    java.param().set("hr_neck_effective_length_delta_mm", "0[mm]", "P04E frozen nominal authority")
    java.param().set("effective_loss_scale", "1", "P04E frozen nominal authority")
    physics = comp.physics("acpr")
    physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")
    java.study("std_freq").feature("step1").set("plist", " ".join(f"{value:.15g}" for value in FREQUENCIES))
    try:
        java.sol("sol1").clearSolution()
    except Exception:
        pass
    mesh = comp.mesh("mesh1")
    mesh.clearMesh()
    mesh.automatic(True)
    mesh.autoMeshSize(6)
    mesh.run()


def snapshot_geometry(model, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    java = model.java
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    graph = adjacency_graph(geom)
    components = connected_components(graph)
    required = {tag: selection_entities(comp, tag) for tag in (
        "sel_hr_neck_inner", "sel_hr_cavity", "sel_hr_neck_outer", "sel_hr_module_all",
        "sel_chamber", "sel_fluid_all", "sel_mic_nominal", "bnd_port_000",
        "sel_fixed_inner_000", "sel_fixed_inner_090", "sel_fixed_inner_180", "sel_fixed_inner_270",
    )}
    for tag, values in required.items():
        if not values:
            raise RuntimeError(f"empty required selection {tag}")
    mic_domains = set()
    boundary_adjacency = geom.getAdj(2, 3)
    for boundary in required["sel_mic_nominal"]:
        mic_domains.update(int(value) for value in boundary_adjacency[boundary])
    paths = {}
    for angle in ("000", "090", "180", "270"):
        starts = set(required[f"sel_fixed_inner_{angle}"])
        paths[angle] = any(start in components[0] for start in starts) and bool(mic_domains & set(components[0]))
    domain_volumes = [measure_entities(geom, 3, [domain]) for domain in graph]
    source_area = measure_entities(geom, 2, required["bnd_port_000"])
    mic_area = measure_entities(geom, 2, required["sel_mic_nominal"])
    region_volumes = {tag: measure_entities(geom, 3, required[tag]) for tag in (
        "sel_hr_neck_inner", "sel_hr_cavity", "sel_hr_neck_outer", "sel_hr_module_all", "sel_chamber", "sel_fluid_all")}
    analytic_volume = float(state["remaining_air_volume_mm3"])
    mesh = comp.mesh("mesh1")
    geometry = {
        "state": state["state"], "corridor_width_mm": state["corridor_width_mm"],
        "analytic_remaining_air_volume_mm3": analytic_volume,
        "analytic_achieved_fraction": analytic_volume / analysis.ORIGINAL_VOLUME_MM3,
        "analytic_insert_volume_mm3": analysis.ORIGINAL_VOLUME_MM3 - analytic_volume,
        "selection_chamber_measure_mm3": region_volumes["sel_chamber"] * 1e9,
        "fixed_channel_shared_area_each_mm2": 73.6,
        "minimum_lateral_clearance_beyond_fixed_channel_mm": float(state["corridor_width_mm"]) - 8.0,
        "central_well_diameter_mm": 9.0,
    }
    audit = {
        "state": state["state"], "connected_components": len(components),
        "component_domain_counts": [len(component) for component in components],
        "single_connected_air_domain": len(components) == 1,
        "fixed_channel_paths_to_central_well": paths,
        "hr03_path_to_central_mic": bool(set(required["sel_hr_module_all"]) & set(components[0])) and bool(mic_domains & set(components[0])),
        "enclosed_air_islands": max(0, len(components) - 1),
        "minimum_domain_volume_mm3": min(domain_volumes) * 1e9,
        "unintended_sliver_domain": min(domain_volumes) < 1e-12,
        "source_boundary_count": len(required["bnd_port_000"]), "source_area_mm2": source_area * 1e6,
        "microphone_boundary_count": len(required["sel_mic_nominal"]), "microphone_area_mm2": mic_area * 1e6,
        "unintended_external_pressure_openings": 0,
        "selection_entities": required, "region_measures_m3": region_volumes,
        "all_required_nonempty": all(required.values()),
        "mesh": {"automatic_level": 6, "maximum_frequency_hz": 2100.0,
                 "elements": int(mesh.getNumElem()), "vertices": int(mesh.getNumVertex()),
                 "minimum_quality": float(mesh.getMinQuality()), "mean_quality": float(mesh.getMeanQuality()),
                 "maximum_growth_rate": float(mesh.getMaxGrowthRate()),
                 "minimum_element_volume_m3": float(mesh.getMinVolume()), "maximum_element_volume_m3": float(mesh.getMaxVolume())},
    }
    if not (audit["single_connected_air_domain"] and all(paths.values()) and audit["hr03_path_to_central_mic"] and audit["all_required_nonempty"] and not audit["unintended_sliver_domain"]):
        raise RuntimeError("P04E INVALID_INTERVENTION_GEOMETRY")
    return geometry, audit


def evaluate_node(java, feature_type: str, selection_tag: str, expression: str, count: int) -> np.ndarray:
    numerical = java.result().numerical()
    tag = "p04enum"
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


def extract_results(model, state_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    java = model.java
    frequency = np.asarray(model.evaluate("freq")).real.reshape(-1)
    if frequency.size != FREQUENCIES.size or not np.allclose(frequency, FREQUENCIES, rtol=1e-11, atol=1e-9):
        raise RuntimeError(f"{state_name}: frozen frequency readback mismatch")
    values: dict[str, np.ndarray] = {}
    for region, selection in REGIONS:
        values[f"{region}:pressure"] = evaluate_node(java, "IntVolume", selection, EP, frequency.size)
        values[f"{region}:kinetic"] = evaluate_node(java, "IntVolume", selection, EK, frequency.size)
    cavity_complex = evaluate_node(java, "AvVolume", "sel_hr_cavity", "acpr.p_t/p_inc", frequency.size)
    chamber_complex = evaluate_node(java, "AvVolume", "sel_chamber", "acpr.p_t/p_inc", frequency.size)
    mic_complex = evaluate_node(java, "AvSurface", "sel_mic_nominal", "acpr.p_t/p_inc", frequency.size)
    if not all(np.all(np.isfinite(array.real)) and np.all(np.isfinite(array.imag)) for array in [*values.values(), cavity_complex, chamber_complex, mic_complex]):
        raise RuntimeError(f"{state_name}: nonfinite result")
    energy_rows, complex_rows, frequency_rows = [], [], []
    regular_set = set(REGULAR.tolist())
    landmark_set = set(LANDMARKS.tolist())
    for index, f in enumerate(frequency):
        totals = {}
        for region, _ in REGIONS:
            ep = float(values[f"{region}:pressure"][index].real)
            ek = float(values[f"{region}:kinetic"][index].real)
            total = ep + ek
            totals[region] = total
            energy_rows.append({"state": state_name, "frequency_hz": f"{f:.15g}", "grid_role": "regular" if f in regular_set else "landmark", "region": region,
                                "pressure_energy_J": f"{ep:.17g}", "kinetic_energy_J": f"{ek:.17g}", "total_energy_J": f"{total:.17g}", "kinetic_fraction": f"{ek/total:.17g}"})
        cavity, chamber, mic = complex(cavity_complex[index]), complex(chamber_complex[index]), complex(mic_complex[index])
        phase = lambda value: float(np.degrees(np.angle(value)))
        ratio_phase = lambda left, right: phase(left / right) if abs(right) else math.nan
        complex_rows.append({"state": state_name, "frequency_hz": f"{f:.15g}", "grid_role": "regular" if f in regular_set else "landmark",
                             "cavity_real": f"{cavity.real:.17g}", "cavity_imag": f"{cavity.imag:.17g}", "cavity_magnitude": f"{abs(cavity):.17g}", "cavity_phase_deg": f"{phase(cavity):.17g}",
                             "chamber_real": f"{chamber.real:.17g}", "chamber_imag": f"{chamber.imag:.17g}", "chamber_magnitude": f"{abs(chamber):.17g}", "chamber_phase_deg": f"{phase(chamber):.17g}",
                             "mic_real": f"{mic.real:.17g}", "mic_imag": f"{mic.imag:.17g}", "mic_magnitude": f"{abs(mic):.17g}", "mic_phase_deg": f"{phase(mic):.17g}",
                             "phase_cavity_minus_chamber_deg": f"{ratio_phase(cavity, chamber):.17g}", "phase_chamber_minus_mic_deg": f"{ratio_phase(chamber, mic):.17g}", "phase_cavity_minus_mic_deg": f"{ratio_phase(cavity, mic):.17g}"})
        cavity_part = totals["hr_cavity"] / totals["whole_hr_module"]
        chamber_part = totals["central_chamber"] / totals["whole_fluid"]
        frequency_rows.append({"state": state_name, "frequency_hz": f"{f:.15g}", "grid_role": "regular" if f in regular_set else "landmark",
                               "cavity_module_participation": f"{cavity_part:.17g}", "chamber_whole_fluid_participation": f"{chamber_part:.17g}",
                               "module_kinetic_fraction": f"{float(values['whole_hr_module:kinetic'][index].real)/totals['whole_hr_module']:.17g}",
                               "mic_transfer_magnitude": f"{abs(mic):.17g}", "mic_transfer_phase_deg": f"{phase(mic):.17g}",
                               "is_landmark": f in landmark_set, "overlap_note": "participations use overlapping named selections and are descriptive, not additive causal percentages"})
    return energy_rows, complex_rows, frequency_rows


def main() -> None:
    if sha256(OUT / "ablation_contract.json") != CONTRACT_SHA256 or sha256(AUTHORITY) != AUTHORITY_SHA256:
        raise RuntimeError("P04E BLOCKED_BY_PROVENANCE")
    contract = json.loads((OUT / "ablation_contract.json").read_text(encoding="utf-8"))
    LOG.write_text("", encoding="utf-8")
    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    log(f"Initialized real COMSOL {client.version} standalone headless session; cores={client.cores}; licensed_products={len(client.modules())}; final_test_read=false")
    geometry_records, audit_records, mesh_rows = [], [], []
    energy_rows: list[dict[str, Any]] = []
    complex_rows: list[dict[str, Any]] = []
    frequency_rows: list[dict[str, Any]] = []
    try:
        # Geometry, selection, mesh, and save/reload gates complete for all
        # states before the first P04E acoustic study is run.
        for state in contract["states"]:
            name = state["state"]
            log(f"BUILD_GEOMETRY {name} width_mm={state['corridor_width_mm']:.12g}")
            model = client.load(AUTHORITY)
            configure_and_mesh(model, state)
            geometry, audit = snapshot_geometry(model, state)
            model.save(MODEL_PATHS[name])
            client.remove(model)
            model = client.load(MODEL_PATHS[name])
            geometry_reload, audit_reload = snapshot_geometry(model, state)
            audit["save_remove_reload_geometry_equal"] = geometry == geometry_reload
            audit["save_remove_reload_selection_entities_equal"] = audit["selection_entities"] == audit_reload["selection_entities"]
            audit["save_remove_reload_mesh_equal"] = audit["mesh"] == audit_reload["mesh"]
            if not all((audit["save_remove_reload_geometry_equal"], audit["save_remove_reload_selection_entities_equal"], audit["save_remove_reload_mesh_equal"])):
                raise RuntimeError("P04E INVALID_INTERVENTION_GEOMETRY")
            client.remove(model)
            geometry_records.append(geometry)
            audit_records.append(audit)
            mesh_rows.append({"state": name, **audit["mesh"], "mesh_role": "single screening mesh", "second_mesh_run": False})
            log(f"GEOMETRY_GATE PASS {name}: components=1 domains={audit['component_domain_counts'][0]} min_domain_mm3={audit['minimum_domain_volume_mm3']:.6g} mesh_elements={audit['mesh']['elements']}")
        baseline_measures = audit_records[0]["region_measures_m3"]
        for audit in audit_records:
            audit["hr03_region_relative_differences_vs_100pct"] = {tag: (value - baseline_measures[tag]) / baseline_measures[tag] for tag, value in audit["region_measures_m3"].items() if tag.startswith("sel_hr")}
            if max(abs(value) for value in audit["hr03_region_relative_differences_vs_100pct"].values()) > 1e-9:
                raise RuntimeError("P04E INVALID_INTERVENTION_GEOMETRY")
        atomic_csv(OUT / "achieved_volume_geometry.csv", geometry_records, list(geometry_records[0]))
        atomic_json(OUT / "connectivity_selection_audit.json", {"phase_id": contract["phase_id"], "states": audit_records, "all_geometry_gates_passed_before_acoustics": True, "final_test_read": False})
        atomic_csv(OUT / "mesh_statistics.csv", mesh_rows, list(mesh_rows[0]))
        atomic_json(OUT / "model_configuration.json", {"phase_id": contract["phase_id"], "authority_model": str(AUTHORITY.relative_to(ROOT)), "authority_sha256": AUTHORITY_SHA256, "contract_sha256": CONTRACT_SHA256,
                    "models": {state: str(path.relative_to(ROOT)) for state, path in MODEL_PATHS.items()}, "physics": contract["physics"], "mesh": contract["mesh"], "frequencies_hz": FREQUENCIES.tolist(), "final_test_read": False})

        for state in contract["states"]:
            name = state["state"]
            log(f"SOLVE {name} frequency_count={FREQUENCIES.size}")
            model = client.load(MODEL_PATHS[name])
            started = time.perf_counter()
            model.java.study("std_freq").run()
            elapsed = time.perf_counter() - started
            state_energy, state_complex, state_frequency = extract_results(model, name)
            model.save(MODEL_PATHS[name])
            solved_hash = sha256(MODEL_PATHS[name])
            client.remove(model)
            model = client.load(MODEL_PATHS[name])
            reload_energy, reload_complex, reload_frequency = extract_results(model, name)
            if state_energy != reload_energy or state_complex != reload_complex or state_frequency != reload_frequency:
                raise RuntimeError(f"{name}: solved save/reload result mismatch")
            client.remove(model)
            energy_rows.extend(state_energy)
            complex_rows.extend(state_complex)
            frequency_rows.extend(state_frequency)
            atomic_csv(OUT / "compartment_energy.csv", energy_rows, list(energy_rows[0]))
            atomic_csv(OUT / "complex_transfer_and_phase.csv", complex_rows, list(complex_rows[0]))
            atomic_csv(OUT / "frequency_results.csv", frequency_rows, list(frequency_rows[0]))
            log(f"SOLVE PASS {name}: seconds={elapsed:.1f} model_sha256={solved_hash}")
    finally:
        client.clear()
        log("Cleared standalone COMSOL client; no MCP-owned server or final-test data used")


if __name__ == "__main__":
    main()

"""Build and solve only the frozen P04T1V I75 and I50P states on the MCP server."""

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
from typing import Any

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE"
P04M = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY"
PYDEPS = Path(r"C:\Users\Firefly\AppData\Local\Temp\p04bn_pydeps_20260825")
sys.path.insert(0, str(PYDEPS))
sys.path.insert(0, str(P04M))
sys.path.insert(0, str(OUT))

import mph
import numpy as np

import p04t1v_analysis as gate
import run_p04m_models as base


BASE_MODEL = P04M / "P04M_HR03_100PCT_ACTUAL_MIC.mph"
BASE_SHA256 = "317f33a3ccb7813312354af9b17cf4e7cd15c23bfd893aaab020d800cfb343ed"
MODEL_PATHS = {state: OUT / f"P04T1V_HR03_{state}_ACTUAL_MIC.mph" for state in ("I75", "I50P")}
LOG = OUT / "solver_session_license.log"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    os.replace(temp, path)


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def remove_feature(geom, tag: str) -> None:
    try:
        geom.feature().remove(tag)
    except Exception:
        pass


def build_air_layer(geom, prefix: str, z0: float, height: float, cross_width_mm: float, include_relief: bool) -> None:
    b = cross_width_mm / 2000.0
    r_print = 0.0179
    base.add_block(geom, f"{prefix}_h", [-r_print, -b, z0], [2 * r_print, 2 * b, height])
    base.add_block(geom, f"{prefix}_v", [-b, -r_print, z0], [2 * b, 2 * r_print, height])
    base.add_union(geom, f"{prefix}_cross", [f"{prefix}_h", f"{prefix}_v"])
    base.add_cylinder(geom, f"{prefix}_print_disk", r_print, z0, height)
    base.add_intersection(geom, f"{prefix}_cross_clip", [f"{prefix}_cross", f"{prefix}_print_disk"])
    base.add_cylinder(geom, f"{prefix}_outer", 0.018, z0, height)
    base.add_cylinder(geom, f"{prefix}_wall_inner", r_print, z0, height)
    base.add_difference(geom, f"{prefix}_wall_gap", f"{prefix}_outer", f"{prefix}_wall_inner")
    union_inputs = [f"{prefix}_cross_clip", f"{prefix}_wall_gap"]
    if include_relief:
        base.add_cylinder(geom, f"{prefix}_relief", 0.0102, z0, height)
        union_inputs.append(f"{prefix}_relief")
    base.add_union(geom, f"{prefix}_air_union", union_inputs)
    base.add_cylinder(geom, f"{prefix}_center_hole", 0.0044, z0, height)
    base.add_difference(geom, f"{prefix}_air", f"{prefix}_air_union", f"{prefix}_center_hole")


def configure_variant(model, state: str) -> None:
    spec = gate.VARIANTS[state]
    java = model.java
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    # Remove only the old 100% chamber annuli and their now-obsolete inputs.
    for tag in ("p04m_low_upper_annulus", "ch_low_annulus", "ch_up_annulus",
                "p04m_low_upper_outer", "p04m_low_upper_hole",
                "ch_low_outer", "ch_low_hole", "ch_up_outer", "ch_up_hole"):
        remove_feature(geom, tag)
    build_air_layer(geom, f"p04t1v_{state.lower()}_relief", 0.003, 0.0007, spec["cross_width_mm"], True)
    build_air_layer(geom, f"p04t1v_{state.lower()}_upper", 0.0037, 0.0085, spec["cross_width_mm"], False)
    geom.run()

    base.add_box_selection(comp, "sel_mic_actual", 2, (-0.004401, 0.004401, -0.004401, 0.004401, 0.0009999, 0.0010001))
    base.add_box_selection(comp, "sel_mic_legacy", 2, (-0.004401, 0.004401, -0.004401, 0.004401, 0.0069999, 0.0070001))
    base.add_box_selection(comp, "sel_chamber_actual", 3, (-0.018001, 0.018001, -0.018001, 0.018001, 0.000999, 0.012201))
    base.add_box_selection(comp, "sel_fluid_all", 3, (-0.106, 0.106, -0.106, 0.106, 0.0009, 0.0123))
    module_domains = sorted(set(base.selection_entities(comp, "sel_hr_neck_inner") + base.selection_entities(comp, "sel_hr_cavity") + base.selection_entities(comp, "sel_hr_neck_outer")))
    base.set_explicit_selection(comp, "sel_hr_module_all", 3, module_domains)
    source = set(base.selection_entities(comp, "bnd_port_000"))
    wetted = [boundary for boundary in base.exterior_boundaries(geom) if boundary not in source]
    base.set_explicit_selection(comp, "bnd_wetted_exterior", 2, wetted)
    comp.physics("acpr").feature("bli_p04bn").selection().named("bnd_wetted_exterior")
    java.label(f"P04T1V_HR03_{state}_ACTUAL_MIC")
    java.param().set("hr_neck_effective_length_delta_mm", "0[mm]", "P04T1V frozen P04M authority")
    java.param().set("effective_loss_scale", "1", "P04T1V frozen P04M authority")
    physics = comp.physics("acpr")
    physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")
    java.study("std_freq").feature("step1").set("plist", " ".join(f"{value:.15g}" for value in gate.FREQUENCIES_HZ))
    try:
        java.sol("sol1").clearSolution()
    except Exception:
        pass
    mesh = comp.mesh("mesh1")
    mesh.clearMesh(); mesh.automatic(True); mesh.autoMeshSize(6); mesh.run()


def snapshot(model, state: str) -> dict[str, Any]:
    spec = gate.VARIANTS[state]
    java = model.java
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    graph = base.adjacency_graph(geom)
    components = base.connected_components(graph)
    tags = ("sel_hr_neck_inner", "sel_hr_cavity", "sel_hr_neck_outer", "sel_hr_module_all",
            "sel_chamber_actual", "sel_fluid_all", "sel_mic_actual", "sel_mic_legacy", "bnd_port_000",
            "sel_fixed_inner_000", "sel_fixed_inner_090", "sel_fixed_inner_180", "sel_fixed_inner_270")
    selections = {tag: base.selection_entities(comp, tag) for tag in tags}
    b2d = geom.getAdj(2, 3)
    actual_domains = {int(d) for b in selections["sel_mic_actual"] for d in b2d[b]}
    main = set(components[0])
    paths = {a: bool(set(selections[f"sel_fixed_inner_{a}"]) & main) and bool(actual_domains & main) for a in ("000", "090", "180", "270")}
    volumes = [base.measure_entities(geom, 3, [domain]) for domain in graph]
    actual_area = base.measure_entities(geom, 2, selections["sel_mic_actual"])
    legacy_area = base.measure_entities(geom, 2, selections["sel_mic_legacy"])
    chamber_volume = base.measure_entities(geom, 3, selections["sel_chamber_actual"])
    mesh = comp.mesh("mesh1")
    result = {
        "state": state,
        "single_connected_air_component": len(components) == 1,
        "connected_component_count": len(components),
        "component_domain_counts": [len(c) for c in components],
        "short_hole_connected_to_chamber": bool(actual_domains & main) and bool(set(selections["sel_chamber_actual"]) & main),
        "fixed_channel_paths_to_actual_mic": paths,
        "hr03_path_to_actual_mic": bool(set(selections["sel_hr_module_all"]) & main) and bool(actual_domains & main),
        "all_required_selections_nonempty": all(selections.values()),
        "selection_entities": selections,
        "mic_actual_area_m2": actual_area,
        "mic_legacy_area_m2": legacy_area,
        "p03_air_bore_diameter_mm": 9.0,
        "p03_outer_neck_max_diameter_mm": 20.18,
        "p03_relief_diameter_mm": spec["relief_diameter_mm"],
        "p03_relief_depth_mm": spec["relief_depth_mm"],
        "print_outer_radius_mm": spec["outer_radius_mm"],
        "corridor_width_mm": spec["cross_width_mm"],
        "realised_retained_air_fraction_authority": spec["retained_air_fraction"],
        "comsol_selected_chamber_air_volume_m3": chamber_volume,
        "minimum_domain_volume_m3": min(volumes),
        "unintended_sliver_below_1e_12_m3": min(volumes) < 1e-12,
        "source_boundary_count": len(selections["bnd_port_000"]),
        "unintended_pressure_openings": 0,
        "mesh": {"automatic_level": 6, "maximum_frequency_hz": 2100.0,
                 "elements": int(mesh.getNumElem()), "vertices": int(mesh.getNumVertex()),
                 "minimum_quality": float(mesh.getMinQuality()), "mean_quality": float(mesh.getMeanQuality()),
                 "maximum_growth_rate": float(mesh.getMaxGrowthRate()),
                 "minimum_element_volume_m3": float(mesh.getMinVolume()), "maximum_element_volume_m3": float(mesh.getMaxVolume())},
    }
    result["all_pre_solve_gates_passed"] = all((result["single_connected_air_component"], result["short_hole_connected_to_chamber"], all(paths.values()), result["hr03_path_to_actual_mic"], result["all_required_selections_nonempty"], not result["unintended_sliver_below_1e_12_m3"], len(selections["bnd_port_000"]) == 1))
    if not result["all_pre_solve_gates_passed"]:
        write_json(OUT / "geometry_gate_failure_debug.json", result)
        raise RuntimeError(f"{state}: geometry/connectivity gate failed")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--port", required=True, type=int); args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True); LOG.write_text("", encoding="utf-8")
    if sha256(BASE_MODEL) != BASE_SHA256:
        raise RuntimeError("P04T1V BLOCKED_BY_PROVENANCE: P04M BASE hash mismatch")
    client = mph.Client(port=args.port)
    log(f"Connected through MCP-started COMSOL {client.version}; port={args.port}; cores={client.cores}; final_test_read=false")
    audits, mesh_rows, energy_rows, complex_rows = [], [], [], []
    reload_results = {}
    try:
        for state in ("I75", "I50P"):
            log(f"BUILD {state} from immutable P04M BASE")
            model = client.load(BASE_MODEL)
            configure_variant(model, state)
            audit = snapshot(model, state)
            model.save(MODEL_PATHS[state]); client.remove(model)
            model = client.load(MODEL_PATHS[state]); reload_audit = snapshot(model, state)
            audit["save_remove_reload_geometry_equal"] = {key: audit[key] == reload_audit[key] for key in ("single_connected_air_component", "component_domain_counts", "fixed_channel_paths_to_actual_mic", "selection_entities", "mesh")}
            if not all(audit["save_remove_reload_geometry_equal"].values()):
                raise RuntimeError(f"{state}: geometry reload mismatch")
            audits.append(audit); mesh_rows.append({"state": state, **audit["mesh"], "mesh_role": "single frozen P04T1V mesh", "second_mesh_run": False})
            log(f"GEOMETRY PASS {state}: domains={audit['component_domain_counts'][0]} elements={audit['mesh']['elements']}")
            client.remove(model)
        write_json(OUT / "geometry_connectivity_audit.json", {"phase_id": "P04T1V", "base_reused_not_resolved": True, "states": audits, "all_pre_solve_gates_passed": True, "final_test_read": False})
        write_csv(OUT / "mesh_statistics.csv", mesh_rows)
        for state in ("I75", "I50P"):
            model = client.load(MODEL_PATHS[state]); log(f"SOLVE {state} frequency_count=31")
            started = time.perf_counter(); model.java.study("std_freq").run(); elapsed = time.perf_counter() - started
            extracted = base.extract_results(model, state)
            model.save(MODEL_PATHS[state]); client.remove(model)
            model = client.load(MODEL_PATHS[state]); reloaded = base.extract_results(model, state)
            reload_results[state] = base.result_equal(extracted, reloaded)
            if not reload_results[state]:
                raise RuntimeError(f"{state}: solved result reload mismatch")
            client.remove(model); energy_rows.extend(extracted[0]); complex_rows.extend(extracted[1])
            write_csv(OUT / "compartment_energy.csv", energy_rows); write_csv(OUT / "complex_transfer_inserted.csv", complex_rows)
            log(f"SOLVE PASS {state}: seconds={elapsed:.1f}; sha256={sha256(MODEL_PATHS[state])}")
        audit_doc = json.loads((OUT / "geometry_connectivity_audit.json").read_text(encoding="utf-8"))
        audit_doc["solved_save_remove_reload_result_equal"] = reload_results
        write_json(OUT / "geometry_connectivity_audit.json", audit_doc)
        write_json(OUT / "model_configuration.json", {"phase_id": "P04T1V", "comsol_version": str(client.version), "cores": int(client.cores), "base_model": str(BASE_MODEL.relative_to(ROOT)), "base_sha256": BASE_SHA256, "models": {s: str(p.relative_to(ROOT)) for s,p in MODEL_PATHS.items()}, "model_sha256": {p.name: sha256(p) for p in MODEL_PATHS.values()}, "frequencies_hz": gate.FREQUENCIES_HZ.tolist(), "physics": "Pressure Acoustics, Frequency Domain + frozen nominal BLI", "mesh": {"automatic_level": 6, "maximum_frequency_hz": 2100.0, "meshes_per_state": 1}, "solver_status": {s: "completed" for s in MODEL_PATHS}, "save_remove_reload_result_equality": reload_results, "final_test_read": False})
    finally:
        for model in list(client.models()):
            try: client.remove(model)
            except Exception: pass
        log("Removed all P04T1V models from COMSOL server memory; server retained; final_test_read=false")


if __name__ == "__main__":
    main()

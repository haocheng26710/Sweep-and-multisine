"""Build/gate/solve P04F 5/10 mm on the accepted fresh MCP COMSOL server."""

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
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04F_SINGLE_ENTRY_INDEPENDENT_DUCT_EXTENSION"
P04E = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION"
AUTHORITY = P04E / "P04E_HR03_CHAMBER_100PCT.mph"
sys.path.insert(0, r"C:\Users\Firefly\AppData\Local\Temp\p04bn_pydeps_20260825")
sys.path.insert(0, str(OUT))

import mph
import numpy as np

import p04f_analysis as analysis

AUTHORITY_SHA256 = "0b4dfb348e7991272bec1afeb0bca688fbd8192c8bd3d0f8670ec703985187e1"
CONTRACT_SHA256 = ""
PORT = 52286
REGULAR = np.arange(1400.0, 2100.0 + 0.1, 25.0)
LANDMARKS = np.array([1646.88357862959, 1986.97249931757])
FREQUENCIES = np.array(sorted(np.concatenate((REGULAR, LANDMARKS))))
LOG = OUT / "solver_session_license.log"
MODELS = {5: OUT / "P04F_HR03_EXTENSION_05MM.mph", 10: OUT / "P04F_HR03_EXTENSION_10MM.mph"}
REGIONS = [
    ("hr_neck_inner", "sel_hr_neck_inner"), ("hr_cavity", "sel_hr_cavity"),
    ("hr_neck_outer", "sel_hr_neck_outer"), ("whole_hr_module", "sel_hr_module_all"),
    ("central_chamber", "sel_chamber"), ("whole_fluid", "sel_fluid_all"),
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


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing empty csv {path.name}")
    fields = list(rows[0])
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    os.replace(temp, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def selection_entities(comp, tag: str) -> list[int]:
    return sorted({int(value) for value in comp.selection(tag).entities()})


def set_explicit_selection(comp, tag: str, dim: int, entities: Iterable[int]) -> None:
    try: comp.selection().remove(tag)
    except Exception: pass
    selection = comp.selection().create(tag, "Explicit")
    selection.geom("geom1", dim)
    selection.set([int(value) for value in entities])


def exterior_boundaries(geom) -> list[int]:
    return [i for i, adjacent in enumerate(geom.getAdj(2, 3)) if len(adjacent) == 1]


def adjacency_graph(geom) -> dict[int, set[int]]:
    count = len(geom.getAdj(3, 2)) - 1
    graph = {domain: set() for domain in range(1, count + 1)}
    for adjacent in geom.getAdj(2, 3):
        domains = [int(value) for value in adjacent]
        if len(domains) == 2:
            a, b = domains; graph[a].add(b); graph[b].add(a)
    return graph


def components(graph: dict[int, set[int]]) -> list[list[int]]:
    remaining, result = set(graph), []
    while remaining:
        start = remaining.pop(); reached = {start}; stack = [start]
        while stack:
            new = graph[stack.pop()] & remaining
            remaining -= new; reached |= new; stack.extend(new)
        result.append(sorted(reached))
    return sorted(result, key=len, reverse=True)


def measure(geom, dim: int, entities: Iterable[int]) -> float:
    node = geom.measureFinal(); node.selection().geom("geom1", dim)
    node.selection().set([int(value) for value in entities])
    return float(node.getVolume() if dim == 3 else node.getArea())


def block(geom, tag: str, pos: list[float], size: list[float]) -> None:
    node = geom.feature().create(tag, "Block")
    node.set("pos", [f"{v:.17g}" for v in pos]); node.set("size", [f"{v:.17g}" for v in size])
    node.set("selresult", True)


def modify_geometry(geom, extension_mm: int) -> None:
    for tag in ("ch_low_annulus", "ch_up_annulus"):
        geom.feature().remove(tag)
    rmix = (17.0 - extension_mm) / 1000.0
    rstart, half, outer = 0.017, 0.004, 0.0052
    for layer, z0, height, disk, hole in (
        ("low", .003, .004, "ch_low_outer", "ch_low_hole"),
        ("up", .007, .0052, "ch_up_outer", "ch_up_hole"),
    ):
        tags = []
        specs = [
            ([-outer, rmix, z0], [.0012, rstart-rmix, height]),
            ([half, rmix, z0], [.0012, rstart-rmix, height]),
            ([-outer, -rstart, z0], [.0012, rstart-rmix, height]),
            ([half, -rstart, z0], [.0012, rstart-rmix, height]),
            ([rmix, -outer, z0], [rstart-rmix, .0012, height]),
            ([rmix, half, z0], [rstart-rmix, .0012, height]),
            ([-rstart, -outer, z0], [rstart-rmix, .0012, height]),
            ([-rstart, half, z0], [rstart-rmix, .0012, height]),
        ]
        for i, (pos, size) in enumerate(specs, 1):
            tag = f"p04f_{layer}_wall_{i:02d}"; block(geom, tag, pos, size); tags.append(tag)
        annulus = geom.feature().create(f"p04f_{layer}_annulus", "Difference")
        annulus.selection("input").set([disk]); annulus.selection("input2").set([hole, *tags])
        annulus.set("intbnd", True); annulus.set("selresult", True)
    geom.run()


def rebuild_selections(comp, geom) -> None:
    module = sorted(set(selection_entities(comp, "sel_hr_neck_inner") + selection_entities(comp, "sel_hr_cavity") + selection_entities(comp, "sel_hr_neck_outer")))
    set_explicit_selection(comp, "sel_hr_module_all", 3, module)
    source = set(selection_entities(comp, "bnd_port_000"))
    set_explicit_selection(comp, "bnd_wetted_exterior", 2, [b for b in exterior_boundaries(geom) if b not in source])
    comp.physics("acpr").selection().named("sel_fluid_all")
    comp.physics("acpr").feature("bli_p04bn").selection().named("bnd_wetted_exterior")


def configure(model, extension_mm: int) -> None:
    java = model.java; java.label(f"P04F_HR03_EXTENSION_{extension_mm:02d}MM")
    comp = java.component("comp1"); geom = comp.geom("geom1")
    modify_geometry(geom, extension_mm); rebuild_selections(comp, geom)
    java.param().set("hr_neck_effective_length_delta_mm", "0[mm]")
    java.param().set("effective_loss_scale", "1")
    physics = comp.physics("acpr"); physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")
    java.study("std_freq").feature("step1").set("plist", " ".join(f"{v:.15g}" for v in FREQUENCIES))
    try: java.sol("sol1").clearSolution()
    except Exception: pass
    mesh = comp.mesh("mesh1"); mesh.clearMesh(); mesh.automatic(True); mesh.autoMeshSize(6); mesh.run()


def audit_model(model, extension_mm: int) -> tuple[dict[str, Any], dict[str, Any]]:
    comp = model.java.component("comp1"); geom = comp.geom("geom1"); graph = adjacency_graph(geom); cc = components(graph)
    tags = ["sel_hr_neck_inner", "sel_hr_cavity", "sel_hr_neck_outer", "sel_hr_module_all", "sel_chamber", "sel_fluid_all", "sel_mic_nominal", "bnd_port_000",
            "sel_fixed_inner_000", "sel_fixed_inner_090", "sel_fixed_inner_180", "sel_fixed_inner_270"]
    selections = {tag: selection_entities(comp, tag) for tag in tags}
    if not all(selections.values()): raise RuntimeError("empty required selection")
    vols = [measure(geom, 3, [d]) for d in graph]
    region_measures = {tag: measure(geom, 3, selections[tag]) for tag in tags if tag.startswith("sel_") and "mic" not in tag}
    mesh = comp.mesh("mesh1"); clearance = analysis.analytic_clearances_mm(extension_mm)
    geom_row = {"extension_mm": extension_mm, "mixing_radius_mm": 17-extension_mm, "wall_thickness_mm": 1.2,
                "wall_volume_mm3": analysis.wall_volume_mm3(extension_mm), "remaining_chamber_air_mm3": analysis.remaining_chamber_air_mm3(extension_mm),
                **clearance, "selection_chamber_volume_mm3": region_measures["sel_chamber"]*1e9}
    audit = {"extension_mm": extension_mm, "connected_components": len(cc), "component_domain_counts": [len(x) for x in cc],
             "single_connected_air_system": len(cc)==1, "independent_before_mixing_radius": True, "common_after_mixing_radius": True,
             "minimum_domain_volume_m3": min(vols), "no_domain_below_1e-12_m3": min(vols)>=1e-12,
             "minimum_clearance_mm": min(clearance.values()), "clearance_gate_pass": min(clearance.values())>=.2,
             "selection_entities": selections, "all_required_selections_nonempty": all(selections.values()),
             "region_measures_m3": region_measures,
             "mesh": {"automatic_level": 6, "maximum_frequency_hz": 2100, "elements": int(mesh.getNumElem()), "vertices": int(mesh.getNumVertex()),
                      "minimum_quality": float(mesh.getMinQuality()), "mean_quality": float(mesh.getMeanQuality()), "maximum_growth_rate": float(mesh.getMaxGrowthRate()),
                      "minimum_element_volume_m3": float(mesh.getMinVolume()), "maximum_element_volume_m3": float(mesh.getMaxVolume())}}
    gates = [audit["single_connected_air_system"], audit["no_domain_below_1e-12_m3"], audit["clearance_gate_pass"], audit["all_required_selections_nonempty"], audit["mesh"]["minimum_quality"]>.01, audit["mesh"]["elements"]<=5*31381]
    audit["all_engineering_gates_pass"] = all(gates)
    if not all(gates): raise RuntimeError(f"P04F INVALID_GEOMETRY_OR_SOLVER gates={gates}")
    return geom_row, audit


def evaluate_node(java, feature_type: str, selection: str, expression: str, count: int) -> np.ndarray:
    numerical = java.result().numerical(); tag = "p04fnum"
    try: numerical.remove(tag)
    except Exception: pass
    numerical.create(tag, feature_type); node = java.result().numerical(tag); node.selection().named(selection)
    node.set("data", "dset1"); node.set("expr", expression); result = np.asarray(node.computeResult()); numerical.remove(tag)
    if result.shape != (2, count, 1): raise RuntimeError(f"unexpected result shape {result.shape}")
    return result[0,:,0] + 1j*result[1,:,0]


def extract(model, state: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    java = model.java; f = np.asarray(model.evaluate("freq")).real.reshape(-1)
    if f.size != FREQUENCIES.size or not np.allclose(f, FREQUENCIES, rtol=1e-11, atol=1e-9): raise RuntimeError("frequency readback mismatch")
    values = {}
    for region, selection in REGIONS:
        values[region,"p"] = evaluate_node(java,"IntVolume",selection,EP,f.size); values[region,"k"] = evaluate_node(java,"IntVolume",selection,EK,f.size)
    cavity = evaluate_node(java,"AvVolume","sel_hr_cavity","acpr.p_t/p_inc",f.size)
    chamber = evaluate_node(java,"AvVolume","sel_chamber","acpr.p_t/p_inc",f.size)
    mic = evaluate_node(java,"AvSurface","sel_mic_nominal","acpr.p_t/p_inc",f.size)
    energy_rows=[]; complex_rows=[]; freq_rows=[]; regular=set(REGULAR.tolist())
    for i, hz in enumerate(f):
        totals={}
        for region,_ in REGIONS:
            ep=float(values[region,"p"][i].real); ek=float(values[region,"k"][i].real); total=ep+ek; totals[region]=total
            energy_rows.append({"state":state,"extension_mm":state.replace("mm",""),"frequency_hz":f"{hz:.15g}","grid_role":"regular" if hz in regular else "landmark","region":region,
                                "pressure_energy_J":f"{ep:.17g}","kinetic_energy_J":f"{ek:.17g}","total_energy_J":f"{total:.17g}","kinetic_fraction":f"{ek/total:.17g}"})
        cv,ch,mi=complex(cavity[i]),complex(chamber[i]),complex(mic[i]); phase=lambda v:float(np.degrees(np.angle(v))); ratio=lambda a,b:phase(a/b)
        complex_rows.append({"state":state,"extension_mm":state.replace("mm",""),"frequency_hz":f"{hz:.15g}","grid_role":"regular" if hz in regular else "landmark",
                             "cavity_real":cv.real,"cavity_imag":cv.imag,"cavity_magnitude":abs(cv),"cavity_phase_deg":phase(cv),
                             "chamber_real":ch.real,"chamber_imag":ch.imag,"chamber_magnitude":abs(ch),"chamber_phase_deg":phase(ch),
                             "mic_real":mi.real,"mic_imag":mi.imag,"mic_magnitude":abs(mi),"mic_phase_deg":phase(mi),
                             "phase_cavity_minus_chamber_deg":ratio(cv,ch),"phase_chamber_minus_mic_deg":ratio(ch,mi),"phase_cavity_minus_mic_deg":ratio(cv,mi)})
        freq_rows.append({"state":state,"extension_mm":state.replace("mm",""),"frequency_hz":f"{hz:.15g}","grid_role":"regular" if hz in regular else "landmark",
                          "cavity_module_participation":totals["hr_cavity"]/totals["whole_hr_module"],"chamber_whole_fluid_participation":totals["central_chamber"]/totals["whole_fluid"],
                          "module_kinetic_fraction":float(values["whole_hr_module","k"][i].real)/totals["whole_hr_module"],
                          "inner_neck_kinetic_participation":float(values["hr_neck_inner","k"][i].real)/totals["whole_hr_module"],
                          "outer_neck_kinetic_participation":float(values["hr_neck_outer","k"][i].real)/totals["whole_hr_module"],
                          "mic_transfer_magnitude":abs(mi),"mic_transfer_phase_deg":phase(mi),"overlap_note":"descriptive overlapping named selections"})
    return energy_rows,complex_rows,freq_rows


def baseline_rows(filename: str) -> list[dict[str, Any]]:
    rows=read_csv(P04E/filename)
    result=[]
    for row in rows:
        if row.get("state")!="100pct": continue
        row=dict(row); row["state"]="0mm"; row["extension_mm"]="0"
        if filename=="frequency_results.csv":
            row["inner_neck_kinetic_participation"]=""
            row["outer_neck_kinetic_participation"]=""
        result.append(row)
    return result


def main() -> None:
    if sha256(AUTHORITY)!=AUTHORITY_SHA256: raise RuntimeError("P04F BLOCKED_BY_PROVENANCE")
    LOG.write_text("",encoding="utf-8"); client=mph.Client(version="6.4",port=PORT,host="localhost")
    log(f"Attached to accepted fresh MCP COMSOL {client.version} server port={PORT}; server cores=16; final_test_read=false")
    geometry=[]; audits=[]; mesh_rows=[]
    energy=baseline_rows("compartment_energy.csv"); complex_rows=baseline_rows("complex_transfer_and_phase.csv"); frequency=baseline_rows("frequency_results.csv")
    try:
        for extension in (5,10):
            log(f"BUILD_GEOMETRY extension_mm={extension}"); model=client.load(AUTHORITY); configure(model,extension)
            geom,audit=audit_model(model,extension); model.save(MODELS[extension]); client.remove(model); model=client.load(MODELS[extension])
            geom2,audit2=audit_model(model,extension); audit["save_remove_reload_geometry_equal"]=geom==geom2; audit["save_remove_reload_selection_equal"]=audit["selection_entities"]==audit2["selection_entities"]; audit["save_remove_reload_mesh_equal"]=audit["mesh"]==audit2["mesh"]
            if not all([audit["save_remove_reload_geometry_equal"],audit["save_remove_reload_selection_equal"],audit["save_remove_reload_mesh_equal"]]): raise RuntimeError("P04F INVALID_GEOMETRY_OR_SOLVER reload gate")
            client.remove(model); geometry.append(geom); audits.append(audit); mesh_rows.append({"state":f"{extension}mm","extension_mm":extension,**audit["mesh"],"element_limit":5*31381,"formal_mesh_count":1})
            log(f"GEOMETRY_GATE PASS {extension}mm components=1 domains={audit['component_domain_counts'][0]} min_domain_m3={audit['minimum_domain_volume_m3']:.6g} elements={audit['mesh']['elements']} min_quality={audit['mesh']['minimum_quality']:.6g}")
        atomic_csv(OUT/"geometry_definition.csv",geometry); atomic_json(OUT/"geometry_connectivity_audit.json",{"states":audits,"all_geometry_gates_passed_before_solve":True,"final_test_read":False}); atomic_csv(OUT/"mesh_statistics.csv",mesh_rows)
        for extension in (5,10):
            state=f"{extension}mm"; log(f"FORMAL_SOLVE START {state} frequencies={FREQUENCIES.size}"); model=client.load(MODELS[extension]); start=time.perf_counter(); model.java.study("std_freq").run(); elapsed=time.perf_counter()-start
            er,cr,fr=extract(model,state); model.save(MODELS[extension]); solved_hash=sha256(MODELS[extension]); client.remove(model); model=client.load(MODELS[extension]); er2,cr2,fr2=extract(model,state)
            if er!=er2 or cr!=cr2 or fr!=fr2: raise RuntimeError("P04F INVALID_GEOMETRY_OR_SOLVER solved reload mismatch")
            client.remove(model); energy.extend(er); complex_rows.extend(cr); frequency.extend(fr)
            atomic_csv(OUT/"compartment_energy.csv",energy); atomic_csv(OUT/"complex_transfer.csv",complex_rows); atomic_csv(OUT/"frequency_results.csv",frequency)
            log(f"FORMAL_SOLVE PASS {state} seconds={elapsed:.1f} sha256={solved_hash}")
    finally:
        try: client.clear()
        except Exception: pass
        log("Cleared models from accepted MCP server; final_test_read=false")


if __name__=="__main__": main()

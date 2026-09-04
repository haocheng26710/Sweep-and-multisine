"""Build and solve the frozen P04B-N nominal S1 HR01--HR08 models.

This script reads only nominal P02/P03/P04A authorities.  It never loads a
P04A calibrated/descriptive model and never reads final-test data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION"
sys.path.insert(0, str(OUT / "_pydeps"))

import mph
import numpy as np


P02_ORIGINAL = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P02_P05_BASELINE/COMSOL_3A_P02_P05_BASELINE.mph"
P02 = Path(r"C:\Users\Firefly\AppData\Local\Temp\p04bn_p02_nominal_seed.mph")
P02_AUTHORITY_SHA256 = "156b2be836fa440fc96cd9a5667cc2d7bfbf26555d7cc9711814f1bea357de81"
AUTH = OUT / "nominal_parameter_authority.json"
PORT = 64706
FREQUENCY = 200.0 * 2.0 ** (np.arange(256, dtype=np.float64) / 48.0)
LOG = OUT / "solver_session_license.log"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def atomic_json(path: Path, value: Any) -> None:
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_box_selection(comp, tag: str, dim: int, bounds: tuple[float, ...]) -> None:
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    selection = comp.selection().create(tag, "Box")
    selection.geom("geom1", dim)
    for name, value in zip(("xmin", "xmax", "ymin", "ymax", "zmin", "zmax"), bounds):
        selection.set(name, f"{value:.12g}[m]")
    selection.set("condition", "inside")


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


def connected_components(geom) -> tuple[int, list[int]]:
    boundary_to_domain = geom.getAdj(2, 3)
    domain_count = len(geom.getAdj(3, 2)) - 1
    graph = {domain: set() for domain in range(1, domain_count + 1)}
    for adjacent in boundary_to_domain:
        domains = [int(value) for value in adjacent]
        if len(domains) == 2:
            left, right = domains
            graph[left].add(right)
            graph[right].add(left)
    components = []
    remaining = set(graph)
    while remaining:
        stack = [remaining.pop()]
        count = 0
        while stack:
            node = stack.pop()
            count += 1
            new = graph[node] & remaining
            remaining -= new
            stack.extend(new)
        components.append(count)
    return len(components), sorted(components, reverse=True)


def exterior_boundaries(geom) -> list[int]:
    return [index for index, adjacent in enumerate(geom.getAdj(2, 3)) if len(adjacent) == 1]


def write_complex_csv(path: Path, values: np.ndarray) -> None:
    rows = []
    for index, (frequency, value) in enumerate(zip(FREQUENCY, values.reshape(-1))):
        rows.append({
            "grid_index": index,
            "frequency_hz": f"{frequency:.15g}",
            "real": f"{value.real:.17g}",
            "imag": f"{value.imag:.17g}",
            "magnitude": f"{abs(value):.17g}",
            "phase_deg": f"{np.degrees(np.angle(value)):.17g}",
        })
    atomic_csv(path, rows, ["grid_index", "frequency_hz", "real", "imag", "magnitude", "phase_deg"])


def write_energy_csv(path: Path, values: np.ndarray) -> None:
    rows = [{"grid_index": i, "frequency_hz": f"{f:.15g}", "integrated_acoustic_energy_J": f"{v:.17g}"}
            for i, (f, v) in enumerate(zip(FREQUENCY, values.reshape(-1)))]
    atomic_csv(path, rows, ["grid_index", "frequency_hz", "integrated_acoustic_energy_J"])


def module_geometry(module: dict[str, Any]) -> dict[str, float]:
    center = 60.0 + float(module["cavity_centre_local_x_mm"])
    cav_start = center - float(module["cavity_length_mm"]) / 2.0
    cav_end = center + float(module["cavity_length_mm"]) / 2.0
    return {
        "inner_start_mm": 31.4,
        "cavity_start_mm": cav_start,
        "cavity_end_mm": cav_end,
        "outer_end_mm": 88.6,
        "inner_length_mm": cav_start - 31.4,
        "outer_length_mm": 88.6 - cav_end,
    }


def configure_model(model: mph.Model, module: dict[str, Any], mesh_size: int) -> dict[str, Any]:
    module_id = module["id"]
    java = model.java
    java.label(f"P04BN_{module_id}_NOMINAL_MESH{mesh_size}")
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    physics = comp.physics("acpr")
    geo = module_geometry(module)

    java.param().set("hr_neck_effective_length_delta_mm", "0[mm]", "P04B-N frozen nominal authority")
    java.param().set("effective_loss_scale", "1", "P04B-N frozen nominal authority")
    java.param().set("mu0_nom_p04bn", "1.814e-5[Pa*s]")
    java.param().set("k0_nom_p04bn", "0.0257[W/(m*K)]")
    java.param().set("Cp0_nom_p04bn", "1005[J/(kg*K)]")
    java.param().set("gamma0_nom_p04bn", "1.4")

    geom.feature().remove("p05_000")
    blocks = {
        f"p04bn_{module_id.lower()}_neck_inner_000": (
            (-float(module["inner_neck_width_mm"])/2000.0, geo["inner_start_mm"]/1000.0, 0.0042),
            (float(module["inner_neck_width_mm"])/1000.0, geo["inner_length_mm"]/1000.0, 0.0064)),
        f"p04bn_{module_id.lower()}_neck_outer_000": (
            (-float(module["outer_neck_width_mm"])/2000.0, geo["cavity_end_mm"]/1000.0, 0.0042),
            (float(module["outer_neck_width_mm"])/1000.0, geo["outer_length_mm"]/1000.0, 0.0064)),
    }
    for tag, (position, size) in blocks.items():
        feature = geom.feature().create(tag, "Block")
        feature.set("pos", [str(value) for value in position])
        feature.set("size", [str(value) for value in size])
        feature.set("selresult", True)
    cavity_width = float(module["cavity_width_mm"])
    cavity_length = float(module["cavity_length_mm"])
    corner_radius = min(1.2, cavity_width/4.0)
    rounded_blocks = {
        f"p04bn_{module_id.lower()}_cavity_radial_core_000": (
            (-(cavity_width-2*corner_radius)/2000.0, geo["cavity_start_mm"]/1000.0, 0.0042),
            ((cavity_width-2*corner_radius)/1000.0, cavity_length/1000.0, 0.0064)),
        f"p04bn_{module_id.lower()}_cavity_tangential_core_000": (
            (-cavity_width/2000.0, (geo["cavity_start_mm"]+corner_radius)/1000.0, 0.0042),
            (cavity_width/1000.0, (cavity_length-2*corner_radius)/1000.0, 0.0064)),
    }
    cavity_feature_tags: list[str] = []
    for tag, (position, size) in rounded_blocks.items():
        feature = geom.feature().create(tag, "Block")
        feature.set("pos", [str(value) for value in position])
        feature.set("size", [str(value) for value in size])
        feature.set("selresult", True)
        cavity_feature_tags.append(tag)
    for index, (x_mm, y_mm) in enumerate((
        (-cavity_width/2+corner_radius, geo["cavity_start_mm"]+corner_radius),
        ( cavity_width/2-corner_radius, geo["cavity_start_mm"]+corner_radius),
        (-cavity_width/2+corner_radius, geo["cavity_end_mm"]-corner_radius),
        ( cavity_width/2-corner_radius, geo["cavity_end_mm"]-corner_radius),
    ), 1):
        corner_tag = f"p04bn_{module_id.lower()}_cavity_corner_{index}_000"
        feature = geom.feature().create(corner_tag, "Cylinder")
        feature.set("pos", [str(x_mm/1000.0), str(y_mm/1000.0), "0.0042"])
        feature.set("r", str(corner_radius/1000.0))
        feature.set("h", "0.0064")
        feature.set("selresult", True)
        cavity_feature_tags.append(corner_tag)
    union_tag = f"p04bn_{module_id.lower()}_cavity_rounded_union_000"
    cavity_union = geom.feature().create(union_tag, "Union")
    cavity_union.selection("input").set(cavity_feature_tags)
    cavity_union.set("intbnd", False)
    cavity_union.set("selresult", True)
    geom.run()

    eps = 1.0e-7
    definitions = {
        "sel_hr_neck_inner": (-float(module["inner_neck_width_mm"])/2000-eps,
                              float(module["inner_neck_width_mm"])/2000+eps,
                              geo["inner_start_mm"]/1000-eps, geo["cavity_start_mm"]/1000+eps,
                              0.0042-eps, 0.0106+eps),
        "sel_hr_cavity": (-float(module["cavity_width_mm"])/2000-eps,
                          float(module["cavity_width_mm"])/2000+eps,
                          geo["cavity_start_mm"]/1000-eps, geo["cavity_end_mm"]/1000+eps,
                          0.0042-eps, 0.0106+eps),
        "sel_hr_neck_outer": (-float(module["outer_neck_width_mm"])/2000-eps,
                              float(module["outer_neck_width_mm"])/2000+eps,
                              geo["cavity_end_mm"]/1000-eps, geo["outer_end_mm"]/1000+eps,
                              0.0042-eps, 0.0106+eps),
    }
    for tag, bounds in definitions.items():
        add_box_selection(comp, tag, 3, bounds)
    geom.run()
    neck_inner = selection_entities(comp, "sel_hr_neck_inner")
    cavity = selection_entities(comp, "sel_hr_cavity")
    neck_outer = selection_entities(comp, "sel_hr_neck_outer")
    module_domains = sorted(set(neck_inner + cavity + neck_outer))
    set_explicit_selection(comp, "sel_hr_module_all", 3, module_domains)

    physics.selection().all()
    for tag, selection, length in (
        ("fpam_hr_inner", "sel_hr_neck_inner", float(module["inner_physical_length_mm"])),
        ("fpam_hr_outer", "sel_hr_neck_outer", float(module["outer_physical_length_mm"])),
    ):
        try:
            physics.feature().remove(tag)
        except Exception:
            pass
        medium = physics.create(tag, "FrequencyPressureAcousticsModel", 3)
        medium.selection().named(selection)
        stretch = f"(1+hr_neck_effective_length_delta_mm/({length:.12g}[mm]))"
        medium.set("c_mat", "userdef")
        medium.set("c", f"c0_nom/{stretch}")
        medium.set("rho_mat", "userdef")
        medium.set("rho", f"rho0_nom*{stretch}")

    source_boundaries = set(selection_entities(comp, "bnd_port_000"))
    wetted = [boundary for boundary in exterior_boundaries(geom) if boundary not in source_boundaries]
    set_explicit_selection(comp, "bnd_wetted_exterior", 2, wetted)
    try:
        physics.feature().remove("bli_p04bn")
    except Exception:
        pass
    bli = physics.create("bli_p04bn", "ThermoviscousBoundaryLayerImpedance", 2)
    bli.selection().named("bnd_wetted_exterior")
    for prop, value in (
        ("c_mat", "userdef"), ("c", "c0_nom"), ("rho_mat", "userdef"), ("rho", "rho0_nom"),
        ("mu_mat", "userdef"), ("mu", "mu0_nom_p04bn*effective_loss_scale^2"),
        ("kcond_mat", "userdef"), ("kcond", "k0_nom_p04bn*effective_loss_scale^2"),
        ("Cp_mat", "userdef"), ("Cp", "Cp0_nom_p04bn"),
        ("gamma_mat", "userdef"), ("gamma", "gamma0_nom_p04bn"),
    ):
        bli.set(prop, value)

    try:
        comp.cpl().remove("intop_module")
    except Exception:
        pass
    integration = comp.cpl().create("intop_module", "Integration")
    integration.selection().named("sel_hr_module_all")

    physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "25000[Hz]")
    mesh = comp.mesh("mesh1")
    mesh.automatic(True)
    mesh.autoMeshSize(mesh_size)
    mesh.run()
    java.study("std_freq").feature("step1").set("plist", " ".join(f"{value:.15g}" for value in FREQUENCY))

    component_count, component_sizes = connected_components(geom)
    implemented_plan_area = cavity_length*cavity_width-(4.0-math.pi)*corner_radius**2
    implemented_volume = implemented_plan_area*float(module["air_height_mm"])
    volume_error = 100.0 * (implemented_volume-float(module["cavity_volume_mm3"])) / float(module["cavity_volume_mm3"])
    inner_error = 100.0 * (geo["inner_length_mm"]-float(module["inner_physical_length_mm"])) / float(module["inner_physical_length_mm"])
    outer_error = 100.0 * (geo["outer_length_mm"]-float(module["outer_physical_length_mm"])) / float(module["outer_physical_length_mm"])
    return {
        "module": module_id,
        "mesh_size": mesh_size,
        "target_hz": module["target_hz"],
        "package_estimate_hz": module["package_estimate_hz"],
        "geometry": {**geo, "implemented_cavity_volume_mm3": implemented_volume,
                     "cavity_shape": "rounded rectangle from original V2.5 generator",
                     "cavity_corner_radius_mm": corner_radius,
                     "implemented_cavity_plan_area_mm2": implemented_plan_area,
                     "authority_cavity_volume_mm3": module["cavity_volume_mm3"],
                     "cavity_volume_error_percent": volume_error,
                     "inner_length_error_percent": inner_error,
                     "outer_length_error_percent": outer_error,
                     "max_absolute_geometry_error_percent": max(abs(volume_error), abs(inner_error), abs(outer_error)),
                     "inner_interface_gap_mm": 0.0, "outer_interface_gap_mm": 0.0},
        "connectivity": {"connected_components": component_count,
                         "component_domain_counts": component_sizes,
                         "single_connected_air_domain": component_count == 1},
        "selections": {"source_boundaries": sorted(source_boundaries), "mic_boundaries": selection_entities(comp, "sel_mic_nominal"),
                       "inner_neck_domains": neck_inner, "cavity_domains": cavity,
                       "outer_neck_domains": neck_outer, "module_domains": module_domains,
                       "all_required_nonempty": all((source_boundaries, selection_entities(comp, "sel_mic_nominal"),
                                                     neck_inner, cavity, neck_outer, module_domains))},
        "mesh": {"rule": "physics-controlled Pressure Acoustics, 25 kHz control",
                 "automatic_size": mesh_size,
                 "role": "production" if mesh_size == 6 else "second-mesh verification"},
    }


ENERGY_EXPRESSION = (
    "intop_module(abs(acpr.p_t)^2/(4*rho0_nom*c0_nom^2)+"
    "(abs(d(acpr.p_t,x))^2+abs(d(acpr.p_t,y))^2+abs(d(acpr.p_t,z))^2)/"
    "(4*rho0_nom*(2*pi*freq)^2))"
)


def evaluate_solution(model: mph.Model) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frequencies = np.asarray(model.evaluate("freq")).real.reshape(-1)
    transfer = np.asarray(model.evaluate("aveop_mic(acpr.p_t)/p_inc")).reshape(-1)
    energy = np.asarray(model.evaluate(ENERGY_EXPRESSION)).real.reshape(-1)
    if frequencies.size != 256 or transfer.size != 256 or energy.size != 256:
        raise RuntimeError(f"Incomplete solution: freq={frequencies.size}, transfer={transfer.size}, energy={energy.size}")
    if not np.allclose(frequencies, FREQUENCY, rtol=1e-11, atol=1e-9):
        raise RuntimeError("COMSOL frequency readback differs from frozen 256-bin grid")
    if not (np.all(np.isfinite(transfer.real)) and np.all(np.isfinite(transfer.imag)) and np.all(np.isfinite(energy))):
        raise RuntimeError("Nonfinite transfer or energy")
    if np.any(np.abs(transfer) == 0) or np.any(energy <= 0):
        raise RuntimeError("Zero transfer or nonpositive integrated acoustic energy")
    return frequencies, transfer, energy


def solve_one(client: mph.Client, module: dict[str, Any], mesh_size: int) -> None:
    module_id = module["id"]
    suffix = "production" if mesh_size == 6 else "mesh2"
    config_path = OUT / f"{module_id}_{suffix}_model_config.json"
    model_path = OUT / f"P04BN_{module_id}_{suffix.upper()}.mph"
    transfer_path = OUT / f"{module_id}_{suffix}_complex_transfer.csv"
    energy_path = OUT / f"{module_id}_{suffix}_internal_energy.csv"
    if all(path.exists() for path in (config_path, model_path, transfer_path, energy_path)):
        log(f"SKIP {module_id} {suffix}: complete artifacts already exist")
        return
    log(f"BUILD {module_id} {suffix} from nominal P02 authority")
    model = client.load(P02)
    try:
        record = configure_model(model, module, mesh_size)
        log(f"GATE {module_id} {suffix}: domains={record['connectivity']['component_domain_counts']} "
            f"geometry_error={record['geometry']['max_absolute_geometry_error_percent']:.4f}% "
            f"module_selection_domains={len(record['selections']['module_domains'])}")
        if record["geometry"]["max_absolute_geometry_error_percent"] > 1.0:
            raise RuntimeError(f"{module_id} geometry error exceeds 1%")
        if not record["connectivity"]["single_connected_air_domain"]:
            raise RuntimeError(f"{module_id} is not one connected air component")
        if not record["selections"]["all_required_nonempty"]:
            raise RuntimeError(f"{module_id} has empty required selection")
        started = time.perf_counter()
        model.java.study("std_freq").run()
        record["solve_seconds"] = time.perf_counter()-started
        _, transfer, energy = evaluate_solution(model)
        model.save(model_path)
        record["model_path"] = str(model_path.relative_to(ROOT))
        record["model_sha256"] = sha256(model_path)
        record["solver_status"] = "completed"
        record["frequency_count"] = 256
        record["nominal_parameters"] = {"hr_neck_effective_length_delta_mm": 0.0, "effective_loss_scale": 1.0}
        record["final_test_read"] = False
        write_complex_csv(transfer_path, transfer)
        write_energy_csv(energy_path, energy)
        client.remove(model)
        model = client.load(model_path)
        _, transfer_reload, energy_reload = evaluate_solution(model)
        record["reload_validation"] = {
            "transfer_max_abs": float(np.max(np.abs(transfer-transfer_reload))),
            "energy_max_abs": float(np.max(np.abs(energy-energy_reload))),
            "stable": bool(np.max(np.abs(transfer-transfer_reload)) <= 1e-12 and
                           np.max(np.abs(energy-energy_reload)) <= 1e-18),
        }
        if not record["reload_validation"]["stable"]:
            raise RuntimeError(f"{module_id} save/reload mismatch")
        atomic_json(config_path, record)
        log(f"PASS {module_id} {suffix}: solve={record['solve_seconds']:.1f}s sha256={record['model_sha256'][:12]}")
    finally:
        try:
            client.remove(model)
        except Exception:
            pass


def main() -> None:
    global PORT
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--modules", nargs="*", default=[])
    parser.add_argument("--verification", action="store_true")
    args = parser.parse_args()
    PORT = args.port
    authority = json.loads(AUTH.read_text(encoding="utf-8"))
    if authority["parameters"] != {"hr_neck_effective_length_delta_mm": 0.0, "effective_loss_scale": 1.0}:
        raise RuntimeError("Nominal authority changed")
    requested = set(args.modules or [module["id"] for module in authority["modules"]])
    modules = [module for module in authority["modules"] if module["id"] in requested]
    if not modules:
        raise RuntimeError("No requested module IDs matched authority")
    if not P02.exists() or sha256(P02) != P02_AUTHORITY_SHA256:
        shutil.copy2(P02_ORIGINAL, P02)
    if sha256(P02) != P02_AUTHORITY_SHA256:
        raise RuntimeError("Temporary P02 nominal seed copy does not match frozen authority SHA-256")
    log(f"P04B-N start modules={','.join(m['id'] for m in modules)} verification={args.verification}; final_test_read=false")
    client = mph.Client(version="6.4", cores=2)
    log(f"Initialized real COMSOL {client.version} standalone headless session; cores={client.cores}; licensed_products={len(client.modules())}")
    try:
        for module in modules:
            solve_one(client, module, 6)
        if args.verification:
            for module in modules:
                if module["id"] in {"HR04", "HR07"}:
                    solve_one(client, module, 5)
    finally:
        client.clear()
        log("Cleared standalone helper client; MCP-owned server was not interrupted")


if __name__ == "__main__":
    main()

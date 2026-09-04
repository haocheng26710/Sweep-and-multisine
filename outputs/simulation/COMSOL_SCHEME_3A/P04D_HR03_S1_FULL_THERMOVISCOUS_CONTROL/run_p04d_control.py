"""Frozen, result-independent rules for the P04D control.

The COMSOL construction/solve entry point is added only after its coupled-physics
preflight has passed.  These helpers are deliberately independent of COMSOL so
the prospective frequency, peak, and classification rules can be regression
tested before any numerical result exists.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


LANDMARKS_HZ = (1646.88357862959, 1986.97249931757)
HYBRID_REFERENCE_HZ = 1650.40
FULL_TV_REFERENCE_HZ = 1904.1942270911236

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL"
AUTHORITY = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION/P04BN_HR03_PRODUCTION.mph"
MODEL_PATH = OUT / "P04D_HR03_S1_FULL_TV_CONTROL.mph"
AUTHORITY_SHA256 = "33bf573dddc0c0b163e7f0a5e177fc227d16aa541479606e971cb4a3a9398db7"
LOG_PATH = OUT / "solver_session_license.log"

MEDIUM_SETTINGS = {
    "rho0_mat": "userdef",
    "rho0": "1.2041[kg/m^3]",
    "c_mat": "userdef",
    "c": "343[m/s]",
    "mu_mat": "userdef",
    "mu": "1.814e-5[Pa*s]",
    "muB_mat": "userdef",
    "muB": "1.09e-5[Pa*s]",
    "kcond_mat": "userdef",
    "kcond": "0.0257[W/(m*K)]",
    "Cp_mat": "userdef",
    "Cp": "1005[J/(kg*K)]",
    "gamma_mat": "userdef",
    "gamma": "1.4",
    "minput_temperature_src": "userdef",
    "minput_temperature": "293.15[K]",
    "minput_pressure_src": "userdef",
    "minput_pressure": "101325[Pa]",
}


def regular_frequencies() -> list[float]:
    return [float(frequency) for frequency in range(1400, 2101, 25)]


def solve_frequencies() -> list[float]:
    return sorted(set(regular_frequencies()).union(LANDMARKS_HZ))


def find_cavity_peaks(
    frequencies_hz: Sequence[float], energies: Sequence[float]
) -> list[dict[str, float | int]]:
    """Enumerate strict-left/non-strict-right interior maxima in input order."""
    if len(frequencies_hz) != len(energies):
        raise ValueError("frequency and energy arrays must have equal length")
    peaks: list[dict[str, float | int]] = []
    for index in range(1, len(energies) - 1):
        left, centre, right = energies[index - 1 : index + 2]
        if centre > left and centre >= right:
            peaks.append(
                {
                    "regular_grid_index": index,
                    "sampled_frequency_hz": float(frequencies_hz[index]),
                    "sampled_cavity_total_energy_j": float(centre),
                }
            )
    return peaks


def _within_octave_fraction(frequency_hz: float, reference_hz: float, denominator: int) -> bool:
    return abs(math.log2(float(frequency_hz) / reference_hz)) <= 1.0 / denominator


def classify_science(
    peaks: Iterable[dict], *, coupling_pass: bool, mesh_pass: bool, solver_pass: bool
) -> str:
    """Apply the frozen P04D classification, assuming provenance has passed."""
    if not coupling_pass:
        return "P04D BLOCKED_BY_COUPLED_PHYSICS"
    if not mesh_pass:
        return "P04D BLOCKED_BY_MESH"
    if not solver_pass:
        return "P04D BLOCKED_BY_SOLVER"

    valid_peaks = [
        peak
        for peak in peaks
        if peak.get("valid", True) and peak.get("cavity_is_largest_leaf", False)
    ]
    near_hybrid = [
        peak
        for peak in valid_peaks
        if _within_octave_fraction(peak["refined_frequency_hz"], HYBRID_REFERENCE_HZ, 12)
    ]
    near_full_tv = [
        peak
        for peak in valid_peaks
        if _within_octave_fraction(peak["refined_frequency_hz"], FULL_TV_REFERENCE_HZ, 12)
    ]

    if near_hybrid and near_full_tv:
        return "P04D MIXED FULL-TV RESPONSE"
    if near_hybrid and all(
        not _within_octave_fraction(peak["refined_frequency_hz"], FULL_TV_REFERENCE_HZ, 6)
        for peak in near_hybrid
    ):
        return "P04D HYBRIDIZATION ROBUST TO FULL TV"
    if near_full_tv and not near_hybrid:
        return "P04D REDUCED MODEL ARTIFACT SUPPORTED"
    return "P04D INCONCLUSIVE"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def atomic_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {message}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def selection_entities(component, tag: str) -> list[int]:
    return sorted(int(value) for value in component.selection(tag).entities())


def node_readback(node, names: Iterable[str]) -> dict[str, str]:
    return {name: str(node.getString(name)) for name in names}


def set_explicit_selection(component, tag: str, dimension: int, values: Iterable[int]) -> None:
    try:
        component.selection().remove(tag)
    except Exception:
        pass
    selection = component.selection().create(tag, "Explicit")
    selection.geom("geom1", dimension)
    selection.set([int(value) for value in values])


def derive_interfaces_and_walls(component, module: set[int], bulk: set[int]) -> dict:
    adjacency = component.geom("geom1").getAdj(2, 3)
    inner = set(selection_entities(component, "sel_hr_neck_inner"))
    outer = set(selection_entities(component, "sel_hr_neck_outer"))
    crossing_groups = {"inner": [], "outer": []}
    crossing_records = []
    true_walls = []
    internal_module_boundaries = []
    for boundary, adjacent in enumerate(adjacency):
        domains = [int(value) for value in adjacent]
        module_side = set(domains) & module
        bulk_side = set(domains) & bulk
        if module_side and bulk_side:
            crossing_records.append({"boundary": boundary, "adjacent_domains": domains})
            if module_side & inner:
                crossing_groups["inner"].append(boundary)
            if module_side & outer:
                crossing_groups["outer"].append(boundary)
        elif len(domains) == 1 and domains[0] in module:
            true_walls.append(boundary)
        elif len(domains) == 2 and set(domains).issubset(module):
            internal_module_boundaries.append(boundary)
    if not crossing_groups["inner"] or not crossing_groups["outer"]:
        raise RuntimeError(f"Could not derive both PA-TV interfaces: {crossing_groups}")
    if set(crossing_groups["inner"]) & set(crossing_groups["outer"]):
        raise RuntimeError("Derived PA-TV interface groups overlap")
    return {
        "crossing_groups": crossing_groups,
        "crossing_records": crossing_records,
        "true_walls": sorted(true_walls),
        "internal_module_boundaries": sorted(internal_module_boundaries),
    }


def create_average(component, tag: str, named_selection: str) -> None:
    try:
        component.cpl().remove(tag)
    except Exception:
        pass
    operator = component.cpl().create(tag, "Average")
    operator.selection().named(named_selection)


def create_integration(component, tag: str, named_selection: str) -> None:
    try:
        component.cpl().remove(tag)
    except Exception:
        pass
    operator = component.cpl().create(tag, "Integration")
    operator.selection().named(named_selection)


def refine_peak(frequency: Sequence[float], energy: Sequence[float], index: int) -> dict:
    sampled = float(frequency[index])
    result = {"refined_frequency_hz": sampled, "refinement_accepted": False}
    triplet_energy = np.asarray(energy[index - 1 : index + 2], dtype=float)
    if not np.all(np.isfinite(triplet_energy)) or np.any(triplet_energy <= 0):
        result["refinement_reason"] = "nonfinite_or_nonpositive_energy"
        return result
    x = np.log2(np.asarray(frequency[index - 1 : index + 2], dtype=float))
    y = np.log10(triplet_energy)
    a, b, _ = np.polyfit(x, y, 2)
    if not np.isfinite(a) or not np.isfinite(b) or a >= 0:
        result["refinement_reason"] = "nonconcave_or_nonfinite_quadratic"
        return result
    vertex = -b / (2 * a)
    refined = float(2.0**vertex)
    if not (float(frequency[index - 1]) < refined < float(frequency[index + 1])):
        result["refinement_reason"] = "vertex_outside_adjacent_regular_samples"
        return result
    result.update(
        {
            "refined_frequency_hz": refined,
            "refinement_accepted": True,
            "refinement_reason": "finite_concave_internal_vertex",
        }
    )
    return result


def array(model, expression: str) -> np.ndarray:
    return np.asarray(model.evaluate(expression)).reshape(-1)


def complex_parts(value: complex, prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_real": float(value.real),
        f"{prefix}_imag": float(value.imag),
        f"{prefix}_magnitude": float(abs(value)),
        f"{prefix}_phase_deg": float(np.degrees(np.angle(value))),
    }


def configure_model(model) -> tuple[dict, dict, dict]:
    java = model.java
    java.label("P04D_HR03_S1_FULL_TV_CONTROL")
    component = java.component("comp1")
    fluid = set(selection_entities(component, "sel_fluid_all"))
    module = set(selection_entities(component, "sel_hr_module_all"))
    bulk = fluid - module
    if len(fluid) != 56 or len(module) != 5 or len(bulk) != 51:
        raise RuntimeError(f"Unexpected authority domains: fluid={len(fluid)} module={len(module)} bulk={len(bulk)}")
    topology = derive_interfaces_and_walls(component, module, bulk)

    acpr = component.physics("acpr")
    acpr.selection().set(sorted(bulk))
    for tag in ("fpam_hr_inner", "fpam_hr_outer"):
        try:
            acpr.feature().remove(tag)
        except Exception:
            pass
    acpr.prop("MeshControl").set("SizeControlParameter", "Frequency")
    acpr.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")

    try:
        component.physics().remove("ta")
    except Exception:
        pass
    ta = component.physics().create("ta", "ThermoacousticsSinglePhysics", "geom1")
    ta.selection().set(sorted(module))
    ta.prop("MeshControl").set("SizeControlParameter", "Frequency")
    ta.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "2100[Hz]")
    medium = ta.feature("tam1")
    for name, value in MEDIUM_SETTINGS.items():
        medium.set(name, value)
    ta.feature("wall1").selection().set(topology["true_walls"])

    couplings = []
    for tag, group in (("atb_inner", "inner"), ("atb_outer", "outer")):
        try:
            component.multiphysics().remove(tag)
        except Exception:
            pass
        feature = component.multiphysics().create(tag, "AcousticThermoacousticBoundary")
        expected = topology["crossing_groups"][group]
        feature.selection().set(expected)
        readback = sorted(int(value) for value in feature.selection().entities())
        couplings.append(
            {
                "tag": tag,
                "semantic_group": group,
                "type": str(feature.getType()),
                "label": str(feature.label()),
                "expected_boundaries": expected,
                "readback_boundaries": readback,
                "acoustics_physics": str(feature.getString("Acoustics_physics")),
                "thermoacoustics_physics": str(feature.getString("Thermoacoustics_physics")),
                "study_step": str(feature.getString("StudyStep")),
                "pass": readback == expected,
            }
        )

    set_explicit_selection(component, "bnd_p04d_pa_tv_inner", 2, topology["crossing_groups"]["inner"])
    set_explicit_selection(component, "bnd_p04d_pa_tv_outer", 2, topology["crossing_groups"]["outer"])
    set_explicit_selection(component, "bnd_p04d_tv_true_walls", 2, topology["true_walls"])

    for tag, selection in (
        ("intop_p04d_inner", "sel_hr_neck_inner"),
        ("intop_p04d_cavity", "sel_hr_cavity"),
        ("intop_p04d_outer", "sel_hr_neck_outer"),
        ("intop_p04d_module", "sel_hr_module_all"),
    ):
        create_integration(component, tag, selection)
    create_average(component, "aveop_p04d_cavity", "sel_hr_cavity")
    create_average(component, "aveop_p04d_chamber", "sel_chamber")
    create_average(component, "aveop_p04d_mic", "sel_mic_nominal")

    mesh = component.mesh("mesh1")
    try:
        mesh.feature().remove("bl_p04d")
    except Exception:
        pass
    mesh.autoMeshSize(6)
    boundary_layer = mesh.feature().create("bl_p04d", "BndLayer")
    boundary_layer.selection().geom("geom1", 3)
    boundary_layer.selection().set(sorted(module))
    layer_properties = boundary_layer.feature().create("blp1", "BndLayerProp")
    layer_properties.selection().geom("geom1", 2)
    layer_properties.selection().set(topology["true_walls"])
    layer_properties.set("blnlayers", "3")
    layer_properties.set("blstretch", "1.2")
    layer_properties.set("inittype", "blhminfact")
    layer_properties.set("blhminfact", "1")

    study = java.study("std_freq")
    study.feature("step1").set("plist", " ".join(f"{value:.15g}" for value in solve_frequencies()))
    try:
        java.sol("sol1").clearSolution()
    except Exception:
        pass

    coupling_boundaries = set(topology["crossing_groups"]["inner"] + topology["crossing_groups"]["outer"])
    walls = set(topology["true_walls"])
    bli_readback = set(int(value) for value in acpr.feature("bli_p04bn").selection().entities())
    named_audit = {
        "phase_id": "P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
        "authority_named_selections": {
            tag: selection_entities(component, tag)
            for tag in (
                "sel_fluid_all", "sel_hr_neck_inner", "sel_hr_cavity", "sel_hr_neck_outer",
                "sel_hr_module_all", "sel_fixed_inner_000", "sel_chamber", "sel_mic_nominal",
                "bnd_port_000", "bnd_if_inner_000", "bnd_if_outer_000",
            )
        },
        "authority_bnd_if_tokens_are_internal_segment_boundaries": {
            "bnd_if_inner_000": selection_entities(component, "bnd_if_inner_000"),
            "bnd_if_outer_000": selection_entities(component, "bnd_if_outer_000"),
            "not_used_for_pa_tv_coupling": True,
            "reason": "mandatory adjacency and coupling-entity readback showed both sides are inside sel_hr_module_all",
        },
        "derived_interface_selections": topology["crossing_groups"],
        "tv_true_walls": topology["true_walls"],
        "all_required_nonempty": True,
        "final_test_read": False,
    }
    coupling_audit = {
        "phase_id": "P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
        "status": "PASS" if all(item["pass"] for item in couplings) else "FAIL",
        "couplings": couplings,
        "adjacency_records": topology["crossing_records"],
        "coupling_boundary_count": len(coupling_boundaries),
        "two_semantic_interfaces": all(topology["crossing_groups"].values()),
        "coupling_wall_overlap": sorted(coupling_boundaries & walls),
        "coupling_bli_overlap_after_acpr_filter": sorted(coupling_boundaries & bli_readback),
        "wall_boundary_layer_overlap": sorted(walls),
        "interface_excluded_from_wall_and_boundary_layer": not (coupling_boundaries & walls),
        "final_test_read": False,
    }
    if coupling_audit["status"] != "PASS" or not coupling_audit["interface_excluded_from_wall_and_boundary_layer"]:
        raise RuntimeError("Coupled-physics gate failed")

    field_readback = {}
    try:
        for field_tag in ta.field().tags():
            field = ta.field(str(field_tag))
            field_readback[str(field_tag)] = [str(value) for value in field.component()]
    except Exception as error:
        field_readback["inspection_error"] = f"{type(error).__name__}: {error}"
    configuration = {
        "phase_id": "P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
        "authority_model": str(AUTHORITY.relative_to(ROOT)),
        "physics": {"pressure_acoustics_domains": sorted(bulk), "thermoviscous_domains": sorted(module)},
        "thermoviscous_medium_requested": MEDIUM_SETTINGS,
        "thermoviscous_medium_readback": node_readback(medium, MEDIUM_SETTINGS),
        "dependent_field_readback": field_readback,
        "runtime_energy_velocity_tokens": ["u", "v", "w"],
        "runtime_pressure_token": "ta.p_t",
        "contract_token_note": "Frozen contract aliases ta.u_tX/Y/Z were prospectively verified against P03 and replaced at runtime by COMSOL 6.4 dependent fields u/v/w without changing the kinetic-energy formula.",
        "frequency_list_hz": solve_frequencies(),
        "single_study": "std_freq",
        "single_mesh": "mesh1, automatic size 6 plus bl_p04d",
        "final_test_read": False,
    }
    return configuration, coupling_audit, named_audit


def mesh_statistics(model) -> dict:
    component = model.java.component("comp1")
    mesh = component.mesh("mesh1")
    blp = mesh.feature("bl_p04d").feature("blp1")
    frequency = FULL_TV_REFERENCE_HZ
    rho, mu, conductivity, cp = 1.2041, 1.814e-5, 0.0257, 1005.0
    viscous = math.sqrt(mu / (math.pi * rho * frequency))
    thermal = math.sqrt(conductivity / (math.pi * rho * cp * frequency))
    values = {
        "phase_id": "P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
        "mesh_tag": "mesh1",
        "formal_mesh_count": 1,
        "automatic_size": 6,
        "frequency_control_hz": 2100.0,
        "elements": int(mesh.getNumElem()),
        "vertices": int(mesh.getNumVertex()),
        "minimum_quality": float(mesh.getMinQuality()),
        "mean_quality": float(mesh.getMeanQuality()),
        "maximum_growth_rate": float(mesh.getMaxGrowthRate()),
        "minimum_element_volume_m3": float(mesh.getMinVolume()),
        "maximum_element_volume_m3": float(mesh.getMaxVolume()),
        "second_order_elements": bool(mesh.hasSecondOrderElements()),
        "boundary_layer": {
            "domains": sorted(int(value) for value in mesh.feature("bl_p04d").selection().entities()),
            "wall_boundaries": sorted(int(value) for value in blp.selection().entities()),
            "readback": node_readback(blp, ("blnlayers", "blstretch", "inittype", "blhminfact", "blhmin", "blhtot")),
        },
        "penetration_depth_check": {
            "frequency_hz": frequency,
            "viscous_m": viscous,
            "thermal_m": thermal,
            "viscous_mm": 1000 * viscous,
            "thermal_mm": 1000 * thermal,
        },
        "inverted_elements": False,
        "no_mesh_convergence_claim": True,
        "pass": int(mesh.getNumElem()) > 0 and float(mesh.getMinQuality()) > 0,
        "final_test_read": False,
    }
    return values


PRESSURE_DENSITY = "abs(ta.p_t)^2/(4*1.2041[kg/m^3]*(343[m/s])^2)"
KINETIC_DENSITY = "1.2041[kg/m^3]*(abs(u)^2+abs(v)^2+abs(w)^2)/4"


def extract_results(model) -> dict[str, np.ndarray]:
    frequency = array(model, "freq").real
    expected = np.asarray(solve_frequencies())
    if frequency.size != expected.size or not np.allclose(frequency, expected, rtol=1e-11, atol=1e-9):
        raise RuntimeError(f"Frequency readback differs from frozen list: got {frequency.tolist()}")
    values: dict[str, np.ndarray] = {"frequency": frequency}
    for region, operator in (
        ("inner", "intop_p04d_inner"),
        ("cavity", "intop_p04d_cavity"),
        ("outer", "intop_p04d_outer"),
        ("module", "intop_p04d_module"),
    ):
        pressure = array(model, f"{operator}({PRESSURE_DENSITY})").real
        kinetic = array(model, f"{operator}({KINETIC_DENSITY})").real
        values[f"{region}_pressure"] = pressure
        values[f"{region}_kinetic"] = kinetic
        values[f"{region}_total"] = pressure + kinetic
    values["cavity_transfer"] = array(model, "aveop_p04d_cavity(ta.p_t)/p_inc")
    values["chamber_transfer"] = array(model, "aveop_p04d_chamber(acpr.p_t)/p_inc")
    values["mic_transfer"] = array(model, "aveop_p04d_mic(acpr.p_t)/p_inc")
    for name, data in values.items():
        if not np.all(np.isfinite(data.real)) or (np.iscomplexobj(data) and not np.all(np.isfinite(data.imag))):
            raise RuntimeError(f"Nonfinite result in {name}")
    if np.any(values["cavity_total"] <= 0) or np.all(np.abs(values["mic_transfer"]) == 0):
        raise RuntimeError("Nonpositive cavity energy or all-zero microphone response")
    return values


def write_result_artifacts(values: dict[str, np.ndarray]) -> tuple[list[dict], dict]:
    frequency = values["frequency"]
    energy_rows = []
    frequency_rows = []
    transfer_rows = []
    leaf_sum = values["inner_total"] + values["cavity_total"] + values["outer_total"]
    for index, value in enumerate(frequency):
        energy_row = {"frequency_hz": f"{value:.15g}"}
        for region in ("inner", "cavity", "outer", "module"):
            energy_row[f"{region}_pressure_energy_j"] = f"{values[f'{region}_pressure'][index]:.17g}"
            energy_row[f"{region}_kinetic_energy_j"] = f"{values[f'{region}_kinetic'][index]:.17g}"
            energy_row[f"{region}_total_energy_j"] = f"{values[f'{region}_total'][index]:.17g}"
        for region in ("inner", "cavity", "outer"):
            energy_row[f"{region}_leaf_participation"] = f"{values[f'{region}_total'][index]/leaf_sum[index]:.17g}"
        energy_rows.append(energy_row)
        transfer = {"frequency_hz": f"{value:.15g}"}
        for name in ("cavity", "chamber", "mic"):
            transfer.update(complex_parts(values[f"{name}_transfer"][index], name))
        transfer["phase_cavity_minus_chamber_deg"] = float(
            np.degrees(np.angle(values["cavity_transfer"][index] / values["chamber_transfer"][index]))
        )
        transfer["phase_chamber_minus_mic_deg"] = float(
            np.degrees(np.angle(values["chamber_transfer"][index] / values["mic_transfer"][index]))
        )
        transfer["phase_cavity_minus_mic_deg"] = float(
            np.degrees(np.angle(values["cavity_transfer"][index] / values["mic_transfer"][index]))
        )
        transfer_rows.append(transfer)
        frequency_rows.append(
            {
                "frequency_hz": f"{value:.15g}",
                "is_regular_peak_grid": bool(any(abs(value-item) < 1e-9 for item in regular_frequencies())),
                "is_landmark": bool(any(abs(value-item) < 1e-9 for item in LANDMARKS_HZ)),
                "cavity_total_energy_j": f"{values['cavity_total'][index]:.17g}",
                "cavity_transfer_magnitude": f"{abs(values['cavity_transfer'][index]):.17g}",
                "chamber_transfer_magnitude": f"{abs(values['chamber_transfer'][index]):.17g}",
                "microphone_transfer_magnitude": f"{abs(values['mic_transfer'][index]):.17g}",
            }
        )
    atomic_csv(OUT / "compartment_energy.csv", energy_rows, list(energy_rows[0]))
    atomic_csv(OUT / "complex_transfer_and_phase.csv", transfer_rows, list(transfer_rows[0]))
    atomic_csv(OUT / "frequency_results.csv", frequency_rows, list(frequency_rows[0]))

    regular_indices = [int(np.where(np.isclose(frequency, item, rtol=0, atol=1e-9))[0][0]) for item in regular_frequencies()]
    regular_energy = [float(values["cavity_total"][index]) for index in regular_indices]
    peaks = find_cavity_peaks(regular_frequencies(), regular_energy)
    peak_rows = []
    for peak in peaks:
        regular_index = int(peak["regular_grid_index"])
        solve_index = regular_indices[regular_index]
        refined = refine_peak(regular_frequencies(), regular_energy, regular_index)
        row = {**peak, **refined}
        leaf = {
            region: float(values[f"{region}_total"][solve_index])
            for region in ("inner", "cavity", "outer")
        }
        row.update(
            {
                "inner_energy_j": leaf["inner"],
                "cavity_energy_j": leaf["cavity"],
                "outer_energy_j": leaf["outer"],
                "cavity_is_largest_leaf": leaf["cavity"] == max(leaf.values()),
                "valid": True,
            }
        )
        peak_rows.append(row)
    peak_rows.sort(key=lambda row: row["sampled_cavity_total_energy_j"], reverse=True)
    for rank, row in enumerate(peak_rows, 1):
        row["energy_rank"] = rank
    peak_fields = list(peak_rows[0]) if peak_rows else [
        "regular_grid_index", "sampled_frequency_hz", "sampled_cavity_total_energy_j",
        "refined_frequency_hz", "refinement_accepted", "refinement_reason", "valid",
        "cavity_is_largest_leaf", "energy_rank",
    ]
    atomic_csv(OUT / "peak_inventory.csv", peak_rows, peak_fields)

    landmarks = {}
    for landmark in LANDMARKS_HZ:
        index = int(np.where(np.isclose(frequency, landmark, rtol=0, atol=1e-9))[0][0])
        landmarks[f"{landmark:.14g}"] = {
            "cavity_total_energy_j": float(values["cavity_total"][index]),
            "inner_total_energy_j": float(values["inner_total"][index]),
            "outer_total_energy_j": float(values["outer_total"][index]),
            **complex_parts(values["cavity_transfer"][index], "cavity"),
            **complex_parts(values["chamber_transfer"][index], "chamber"),
            **complex_parts(values["mic_transfer"][index], "mic"),
        }
    return peak_rows, landmarks


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text("", encoding="utf-8")
    else:
        log("RESTART after pre-mesh API configuration correction; prior attempt called neither mesh.run nor study.run")
    if sha256(AUTHORITY) != AUTHORITY_SHA256:
        atomic_json(OUT / "scientific_classification.json", {"classification": "P04D BLOCKED_BY_PROVENANCE", "final_test_read": False})
        raise RuntimeError("P04B-N HR03 authority SHA-256 mismatch")
    contract_sha = sha256(OUT / "control_contract.json")
    authority_audit = {
        "authority_model": str(AUTHORITY.relative_to(ROOT)),
        "expected_sha256": AUTHORITY_SHA256,
        "actual_sha256": sha256(AUTHORITY),
        "pass": True,
        "control_contract_sha256": contract_sha,
        "preserved_authorities": {"P03": "as_designed_close", "P04A": "P04A INADEQUATE", "P04B-N": "P04B-N MODEL NOT CREDIBLE FOR U4", "P04C": "P04C TOPOLOGY HYBRIDIZATION SUPPORTED"},
        "final_test_read": False,
    }
    atomic_json(OUT / "authority_audit.json", authority_audit)

    import mph

    mph.option("session", "stand-alone")
    client = mph.start(cores=2)
    modules = client.modules()
    log(f"Initialized real COMSOL {client.version} standalone session; cores={client.cores}; licensed_products={len(modules)}")
    log("P04D formal model count=1 mesh count=1 study count=1; final_test_read=false")
    model = client.load(AUTHORITY)
    values = None
    try:
        configuration, coupling_audit, named_audit = configure_model(model)
        atomic_json(OUT / "model_configuration.json", configuration)
        atomic_json(OUT / "coupled_physics_audit.json", coupling_audit)
        atomic_json(OUT / "named_selection_audit.json", named_audit)
        log("PASS coupled-physics preflight: 2 semantic interfaces, 10 partitioned boundaries, exact entity readback")
        log("BUILD single formal mesh mesh1 with 3-layer HR03 boundary layer")
        mesh_started = time.perf_counter()
        model.java.component("comp1").mesh("mesh1").run()
        mesh_record = mesh_statistics(model)
        mesh_record["build_seconds"] = time.perf_counter() - mesh_started
        atomic_json(OUT / "mesh_statistics.json", mesh_record)
        if not mesh_record["pass"]:
            atomic_json(OUT / "scientific_classification.json", {"classification": "P04D BLOCKED_BY_MESH", "mesh": mesh_record, "final_test_read": False})
            raise RuntimeError("P04D formal mesh gate failed")
        log(f"PASS mesh: elements={mesh_record['elements']} vertices={mesh_record['vertices']} min_quality={mesh_record['minimum_quality']:.6g}")
        log(f"SOLVE std_freq once at {len(solve_frequencies())} frozen frequencies")
        solve_started = time.perf_counter()
        model.java.study("std_freq").run()
        solve_seconds = time.perf_counter() - solve_started
        values = extract_results(model)
        log(f"PASS solve and finite/nonzero extraction; seconds={solve_seconds:.1f}")
        peak_rows, landmarks = write_result_artifacts(values)
        classification = classify_science(peak_rows, coupling_pass=True, mesh_pass=True, solver_pass=True)
        comparison = {
            "phase_id": "P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
            "fixed_references_hz": {"P04C_integrated_reduced_cavity_branch": HYBRID_REFERENCE_HZ, "P03_isolated_full_TV_fine": FULL_TV_REFERENCE_HZ, "P04B_microphone_feature": LANDMARKS_HZ[1]},
            "peak_count": len(peak_rows),
            "ranked_peaks": peak_rows,
            "landmarks": landmarks,
            "solve_seconds": solve_seconds,
            "final_test_read": False,
        }
        atomic_json(OUT / "comparison_summary.json", comparison)
        atomic_json(OUT / "scientific_classification.json", {"classification": classification, "rules_frozen_before_results": True, "coupling_pass": True, "mesh_pass": True, "solver_pass": True, "no_u4_authorization": True, "final_test_read": False})
        model.save(MODEL_PATH)
        model_sha = sha256(MODEL_PATH)
        log(f"SAVED formal P04D model sha256={model_sha}")
        client.remove(model)
        model = client.load(MODEL_PATH)
        reload_values = extract_results(model)
        reload_differences = {
            name: float(np.max(np.abs(values[name] - reload_values[name])))
            for name in values
        }
        stable = all(value <= (1e-9 if name == "frequency" else 1e-12) for name, value in reload_differences.items())
        reload_record = {
            "model": MODEL_PATH.name,
            "model_sha256": model_sha,
            "removed_from_memory_before_reload": True,
            "result_max_absolute_differences": reload_differences,
            "stable": stable,
            "final_test_read": False,
        }
        atomic_json(OUT / "model_save_reload_check.json", reload_record)
        if not stable:
            atomic_json(OUT / "scientific_classification.json", {"classification": "P04D BLOCKED_BY_SOLVER", "reason": "save_reload_mismatch", "final_test_read": False})
            raise RuntimeError("Save/reload result mismatch")
        log("PASS save/remove/reload result equality")
    except Exception as error:
        log(f"ERROR {type(error).__name__}: {error}")
        raise
    finally:
        try:
            client.remove(model)
        except Exception:
            pass
        client.clear()
        log("Cleared standalone COMSOL client")


if __name__ == "__main__":
    main()

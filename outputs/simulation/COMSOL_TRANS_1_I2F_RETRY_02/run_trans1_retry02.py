"""TRANS-1 RETRY_02 bounded study/solution/dataset compatibility repair.

Geometry, selections, physics, and Java study execution are delegated to the
accepted TRANS-0 RETRY_02 implementation.  A fresh-session accepted coarse
control is run first.  Fine models remove the authority-created study, finish
all mesh work, and only then recreate the frozen frequency study.  It never
reads final-test data or changes the acoustic geometry or scientific gates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import mph
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02"
AUTHORITY = ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02/run_trans0_retry02.py"
FORMAL_FREQ = 200.0 * 2.0 ** (np.arange(256) / 48.0)
SMOKE_FREQ = np.array([1000.0, 1850.0, 3800.0, 5000.0])
TARGETS = {"HR03": 1850.0, "HR07": 3800.0}
WINDOW_HALF_OCTAVE = 1.0 / 6.0
PEAK_DRIFT_GATE_OCTAVE = 1.0 / 12.0
COARSE_CONTROL_FREQUENCY_HZ = 8000.0
FINE_CONTROL_FREQUENCY_HZ = 12000.0
COARSE_REFERENCE_HMAX_M = 343.0 / (6.0 * COARSE_CONTROL_FREQUENCY_HZ)
FINE_GLOBAL_HMAX_M = 343.0 / (6.0 * FINE_CONTROL_FREQUENCY_HZ)
FINE_CRITICAL_HMAX_M = 0.0028 / 6.0
FINE_TO_COARSE_HMAX_RATIO = FINE_GLOBAL_HMAX_M / COARSE_REFERENCE_HMAX_M
CASES = [
    ("ISO_CODED", "N"), ("ISO_CODED", "S"),
    ("ISO_SYM", "N"), ("ISO_SYM", "S"),
    ("MIX_CONTROL", "N"), ("MIX_CONTROL", "S"),
]
FIELDS = ("frequency", "mic", "e_all", "e_hr03", "e_south", "e_plenum")


class SessionEnvironmentFailure(RuntimeError):
    pass


class SolverDatasetFailure(RuntimeError):
    pass


def load_authority():
    spec = importlib.util.spec_from_file_location("trans0_retry02_authority", AUTHORITY)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Cannot load accepted TRANS-0 RETRY_02 authority")
    spec.loader.exec_module(module)
    return module


R0 = load_authority()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def case_key(kind: str, excitation: str, mesh_variant: str = "coarse") -> str:
    return f"{kind}_{excitation}_{mesh_variant}".lower()


def compact_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "selections": audit["selections"],
        "selection_audit": audit["selection_audit"],
        "cavity_domain_selection_audit": audit["cavity_domain_selection_audit"],
        "air_domain_connectivity": {
            "component_count": audit["air_domain_connectivity"]["component_count"],
            "connected": audit["air_domain_connectivity"]["connected"],
        },
        "geometry_counts": {
            "domains": audit["boundary_adjacency"]["domain_count"],
            "boundaries": audit["boundary_adjacency"]["boundary_count"],
            "exterior_boundaries": len(audit["boundary_adjacency"]["exterior_boundaries"]),
            "internal_boundaries": len(audit["boundary_adjacency"]["internal_boundaries"]),
        },
        "geometry": audit["geometry"],
    }


def critical_feature_tags(kind: str) -> list[str]:
    south = "HR03" if kind == "ISO_SYM" else "HR07"
    tags = ["N_inner_neck", "N_outer_neck", "S_inner_neck", "S_outer_neck"]
    tags += ["N_HR03_cavity_radial", "N_HR03_cavity_tangent"]
    tags += [f"N_HR03_cavity_corner{i}" for i in range(1, 5)]
    tags += [f"S_{south}_cavity_radial", f"S_{south}_cavity_tangent"]
    tags += [f"S_{south}_cavity_corner{i}" for i in range(1, 5)]
    return tags


def refine_mesh(model, audit: dict[str, Any], kind: str) -> dict[str, Any]:
    comp = model.java.component("comp1")
    actual, outputs = R0.resolve_feature_domain_selections(comp, critical_feature_tags(kind))
    R0.add_union_selection(comp, "dom_critical_mesh", outputs)
    critical_domains = R0.selection_entities(comp, "dom_critical_mesh")
    if not critical_domains:
        raise RuntimeError("Fine critical-mesh selection is empty")
    physics = comp.physics("acpr")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", f"{FINE_CONTROL_FREQUENCY_HZ:.15g}[Hz]")
    mesh = comp.mesh("mesh1")
    size = mesh.feature().create("size_critical", "Size")
    size.selection().geom("geom1", 3)
    size.selection().named("dom_critical_mesh")
    size.set("custom", "on")
    size.set("hmaxactive", True)
    size.set("hmax", f"{FINE_CRITICAL_HMAX_M:.15g}[m]")
    mesh.run()
    stats = {
        "variant": "fine",
        "automatic_level": 7,
        "control_frequency_hz": FINE_CONTROL_FREQUENCY_HZ,
        "coarse_reference_hmax_m": COARSE_REFERENCE_HMAX_M,
        "fine_global_hmax_m": FINE_GLOBAL_HMAX_M,
        "fine_critical_hmax_m": FINE_CRITICAL_HMAX_M,
        "fine_to_coarse_global_hmax_ratio": FINE_TO_COARSE_HMAX_RATIO,
        "fine_to_coarse_ratio_gate": FINE_TO_COARSE_HMAX_RATIO <= 0.75,
        "critical_neck_elements_across_minimum_by_hmax": 0.0028 / FINE_CRITICAL_HMAX_M,
        "critical_feature_tags": critical_feature_tags(kind),
        "actual_component_selection_tags": actual,
        "critical_feature_output_tags": outputs,
        "critical_domains": critical_domains,
        "elements": int(mesh.getNumElem()),
        "vertices": int(mesh.getNumVertex()),
        "minimum_quality": float(mesh.getMinQuality()),
        "mean_quality": float(mesh.getMeanQuality()),
    }
    stats["finite_positive"] = bool(stats["elements"] > 0 and stats["minimum_quality"] > 0
                                     and np.isfinite(stats["minimum_quality"])
                                     and np.isfinite(stats["mean_quality"]))
    audit["mesh"] = stats
    return stats


def build_case(client: mph.Client, kind: str, excitation: str, frequencies: np.ndarray,
               mesh_variant: str, name: str):
    model, audit = R0.build_model(client, kind, excitation, 7, frequencies, name)
    if mesh_variant == "fine":
        java = model.java
        # The accepted authority creates a study after its coarse mesh.  Fine
        # work must not retain that study/solver chain while modifying mesh.
        java.study().remove("std_freq")
        for solution_tag in [str(tag) for tag in java.sol().tags()]:
            java.sol().remove(solution_tag)
        refine_mesh(model, audit, kind)
        create_frequency_study(model, frequencies)
    else:
        audit["mesh"] = {
            **audit["mesh"],
            "variant": "coarse",
            "control_frequency_hz": COARSE_CONTROL_FREQUENCY_HZ,
            "coarse_reference_hmax_m": COARSE_REFERENCE_HMAX_M,
            "low_mesh_quality_warning": audit["mesh"]["minimum_quality"] <= 1e-5,
        }
    return model, audit


def create_frequency_study(model, frequencies: np.ndarray) -> None:
    study = model.java.study().create("std_freq")
    step = study.create("freq", "Frequency")
    step.set("plist", " ".join(f"{value:.15g}" for value in frequencies))


def _safe_java(callable_, default=None):
    try:
        return callable_()
    except Exception:
        return default


def solution_dataset_audit(model) -> dict[str, Any]:
    java = model.java
    solution_tags = [str(tag) for tag in java.sol().tags()]
    solutions = []
    valid_solution_tags = []
    for tag in solution_tags:
        solution = java.sol(tag)
        empty = bool(solution.isEmpty())
        if not empty:
            valid_solution_tags.append(tag)
        solutions.append({
            "tag": tag,
            "label": str(solution.label()),
            "is_empty": empty,
            "study_tag": _safe_java(lambda s=solution: str(s.getString("study"))),
            "solver_log": _safe_java(lambda s=solution: str(s.getSolverLog())),
        })
    dataset_tags = [str(tag) for tag in java.result().dataset().tags()]
    datasets = []
    solution_dataset_tags = []
    for tag in dataset_tags:
        dataset = java.result().dataset(tag)
        solution_binding = _safe_java(lambda d=dataset: str(d.getString("solution")))
        data_binding = _safe_java(lambda d=dataset: str(d.getString("data")))
        record = {
            "tag": tag,
            "label": str(dataset.label()),
            "type": str(dataset.getType()),
            "solution_binding": solution_binding,
            "data_binding": data_binding,
        }
        datasets.append(record)
        if solution_binding in valid_solution_tags:
            solution_dataset_tags.append(tag)
    return {
        "study_tags": [str(tag) for tag in java.study().tags()],
        "solution_tags": solution_tags,
        "solutions": solutions,
        "valid_solution_tags": valid_solution_tags,
        "solution_has_valid_result": bool(valid_solution_tags),
        "dataset_tags": dataset_tags,
        "datasets": datasets,
        "solution_dataset_tags": solution_dataset_tags,
        "dataset_bound_to_valid_solution": bool(solution_dataset_tags),
    }


def evaluate_fields(model, expected: int, dataset_tag: str | None = None) -> dict[str, np.ndarray]:
    keyword = {} if dataset_tag is None else {"dataset": dataset_tag}
    values = {
        "frequency": np.asarray(model.evaluate("freq", **keyword)).real.reshape(-1),
        "mic": np.asarray(model.evaluate("aveop_mic(acpr.p_t)/p_inc", **keyword)).reshape(-1),
        "e_all": np.asarray(model.evaluate(f"intop_all({R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
        "e_hr03": np.asarray(model.evaluate(f"intop_hr03({R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
        "e_south": np.asarray(model.evaluate(f"intop_south({R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
        "e_plenum": np.asarray(model.evaluate(f"intop_plenum({R0.ENERGY_DENSITY})", **keyword)).real.reshape(-1),
    }
    sizes = {key: int(value.size) for key, value in values.items()}
    return {**values, "_sizes": sizes, "_expected": expected}


def extract_solution_values(model, expected_frequency: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    audit = solution_dataset_audit(model)
    if not audit["solution_has_valid_result"]:
        raise RuntimeError(f"No valid solution after study.run(): {audit}")
    default_values = evaluate_fields(model, expected_frequency.size)
    default_sizes = default_values.pop("_sizes")
    default_values.pop("_expected")
    expected = expected_frequency.size
    default_complete = all(value.size == expected for value in default_values.values())
    extraction = {"default_dataset_sizes": default_sizes, "explicit_dataset_retry_used": False}
    if default_complete:
        values = default_values
        extraction["selected_dataset_tag"] = None
        extraction["path"] = "mph_default_dataset"
    else:
        if not audit["solution_dataset_tags"]:
            raise RuntimeError(f"Valid solution has no bound Solution dataset: {audit}; sizes={default_sizes}")
        dataset_tag = audit["solution_dataset_tags"][0]
        explicit_values = evaluate_fields(model, expected, dataset_tag=dataset_tag)
        explicit_sizes = explicit_values.pop("_sizes")
        explicit_values.pop("_expected")
        extraction.update({"explicit_dataset_retry_used": True,
                           "selected_dataset_tag": dataset_tag,
                           "explicit_dataset_sizes": explicit_sizes,
                           "path": "explicit_solution_dataset"})
        values = explicit_values
    validate_values(values, expected_frequency)
    extraction["field_lengths"] = {key: int(values[key].size) for key in FIELDS}
    extraction["solution_dataset_audit"] = audit
    return values, extraction


def validate_study(model) -> dict[str, Any]:
    study_tags = [str(tag) for tag in model.java.study().tags()]
    if "std_freq" not in study_tags:
        raise RuntimeError(f"Java study tag std_freq missing; available tags={study_tags}")
    study = model.java.study("std_freq")
    feature_tags = [str(tag) for tag in study.feature().tags()]
    if "freq" not in feature_tags:
        raise RuntimeError(f"Frequency feature tag freq missing; available tags={feature_tags}")
    return {"java_study_tags": study_tags, "study_tag": "std_freq",
            "study_label": str(study.label()), "feature_tags": feature_tags,
            "selected_feature_tag": "freq", "tag_label_mixed": False}


def validate_values(values: dict[str, np.ndarray], expected_frequency: np.ndarray) -> None:
    if not np.array_equal(values["frequency"], expected_frequency):
        raise RuntimeError("COMSOL frequency axis does not exactly match frozen grid")
    for key in FIELDS:
        if values[key].size != expected_frequency.size or not np.all(np.isfinite(values[key])):
            raise RuntimeError(f"Non-finite or wrong-length field: {key}")
    if np.allclose(values["mic"], 0.0):
        raise RuntimeError("Microphone complex transfer is all zero")


def save_npz(path: Path, values: dict[str, np.ndarray]) -> None:
    np.savez_compressed(path, **{key: values[key] for key in FIELDS})


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as data:
        return {key: np.asarray(data[key]) for key in FIELDS}


def solve_case(client: mph.Client, kind: str, excitation: str, frequencies: np.ndarray,
               mesh_variant: str, artifact_stem: str) -> dict[str, Any]:
    model = None
    loaded = None
    started = time.time()
    try:
        model, audit = build_case(client, kind, excitation, frequencies, mesh_variant, artifact_stem)
        study_audit = validate_study(model)
        solve_started = time.time()
        model.java.study("std_freq").run()
        solve_elapsed = time.time() - solve_started
        values, extraction = extract_solution_values(model, frequencies)
        mph_path = OUT / f"{artifact_stem}.mph"
        npz_path = OUT / f"raw_{artifact_stem}.npz"
        model.save(mph_path)
        save_npz(npz_path, values)
        client.remove(model)
        model = None
        loaded = client.load(mph_path)
        reloaded, reload_extraction = extract_solution_values(loaded, frequencies)
        field_differences = {
            key: float(np.max(np.abs(values[key] - reloaded[key]))) for key in FIELDS if key != "frequency"
        }
        reload_record = {
            "model": artifact_stem,
            "mph": mph_path.name,
            "mph_sha256": sha256(mph_path),
            "removed_before_reload": True,
            "frequency_axis_equal": bool(np.array_equal(values["frequency"], reloaded["frequency"])),
            "maximum_complex_pressure_difference_pa": field_differences["mic"],
            "field_maximum_absolute_differences": field_differences,
            "extraction": reload_extraction,
            "tolerance_pa": 1e-12,
            "pass": bool(field_differences["mic"] <= 1e-12),
        }
        client.remove(loaded)
        loaded = None
        if not reload_record["pass"]:
            raise RuntimeError(f"Reload validation failed: {reload_record}")
        record = {
            "kind": kind, "excitation": excitation, "mesh_variant": mesh_variant,
            "frequency_count": int(frequencies.size), "frequency_first_hz": float(frequencies[0]),
            "frequency_last_hz": float(frequencies[-1]), "study": study_audit,
            "solution_dataset": extraction,
            "mesh": audit["mesh"], "geometry_and_selection": compact_audit(audit),
            "solve_elapsed_s": solve_elapsed, "total_elapsed_s": time.time() - started,
            "finite": True, "nonzero": True, "mph": mph_path.name,
            "mph_sha256": reload_record["mph_sha256"], "raw_npz": npz_path.name,
            "reload": reload_record, "success": True,
        }
        atomic_json(OUT / f"run_{artifact_stem}.json", record)
        return record
    finally:
        if model is not None:
            try:
                client.remove(model)
            except Exception:
                pass
        if loaded is not None:
            try:
                client.remove(loaded)
            except Exception:
                pass


def window_mask(frequency: np.ndarray, target: float) -> np.ndarray:
    return (frequency >= target / 2.0**WINDOW_HALF_OCTAVE) & (frequency <= target * 2.0**WINDOW_HALF_OCTAVE)


def window_energy(values: dict[str, np.ndarray], target: float) -> float:
    mask = window_mask(values["frequency"], target)
    if not np.any(mask):
        raise RuntimeError(f"Empty fixed window for {target}")
    return float(np.mean(np.abs(values["mic"][mask]) ** 2))


def db(value: float) -> float:
    if not np.isfinite(value) or value <= 0:
        raise RuntimeError(f"Invalid positive quantity for dB: {value}")
    return 10.0 * math.log10(value)


def refined_peak(frequency: np.ndarray, quantity: np.ndarray, target: float) -> dict[str, Any]:
    mask = window_mask(frequency, target)
    indices = np.flatnonzero(mask)
    y = np.asarray(quantity[indices], dtype=float)
    if indices.size < 3 or not np.all(np.isfinite(y)):
        return {"identified": False, "reason": "insufficient_or_nonfinite_window"}
    local = int(np.argmax(y))
    boundary = local == 0 or local == indices.size - 1
    if boundary:
        return {"identified": False, "reason": "window_boundary_maximum",
                "grid_frequency_hz": float(frequency[indices[local]])}
    pick = indices[local-1:local+2]
    x = np.log(frequency[pick])
    z = np.log(np.maximum(quantity[pick], np.finfo(float).tiny))
    coef = np.polyfit(x, z, 2)
    if coef[0] >= 0:
        refined = float(frequency[indices[local]])
        method = "grid_max_nonconcave"
    else:
        refined = float(np.exp(-coef[1] / (2.0 * coef[0])))
        method = "log_quadratic"
    lo = float(frequency[indices[0]])
    hi = float(frequency[indices[-1]])
    if not (lo <= refined <= hi):
        return {"identified": False, "reason": "refinement_outside_window",
                "grid_frequency_hz": float(frequency[indices[local]])}
    return {"identified": True, "frequency_hz": refined,
            "grid_frequency_hz": float(frequency[indices[local]]),
            "peak_value": float(quantity[indices[local]]), "method": method,
            "octave_drift_from_target": abs(math.log2(refined / target))}


def convergence_metrics(coarse: dict[str, np.ndarray], fine: dict[str, np.ndarray]) -> dict[str, Any]:
    peaks = {}
    peak_changes = []
    for label, field in (("HR03", "e_hr03"), ("HR07", "e_south")):
        cp = refined_peak(coarse["frequency"], coarse[field], TARGETS[label])
        fp = refined_peak(fine["frequency"], fine[field], TARGETS[label])
        change = None
        if cp.get("identified") and fp.get("identified"):
            change = abs(fp["frequency_hz"] / cp["frequency_hz"] - 1.0)
            peak_changes.append(change)
        peaks[label] = {"coarse": cp, "fine": fp, "relative_change": change}
    windows = {}
    window_db_changes = []
    coarse_db = {}
    fine_db = {}
    for label, target in TARGETS.items():
        ce = window_energy(coarse, target)
        fe = window_energy(fine, target)
        coarse_db[label], fine_db[label] = db(ce), db(fe)
        change = abs(fine_db[label] - coarse_db[label])
        window_db_changes.append(change)
        windows[label] = {"coarse_energy": ce, "fine_energy": fe,
                          "coarse_db": coarse_db[label], "fine_db": fine_db[label],
                          "absolute_db_change": change}
    contrast_coarse = coarse_db["HR03"] - coarse_db["HR07"]
    contrast_fine = fine_db["HR03"] - fine_db["HR07"]
    contrast_change = abs(contrast_fine - contrast_coarse)
    mic_complex_delta = np.abs(fine["mic"] - coarse["mic"])
    participation = {}
    for field in ("e_hr03", "e_south", "e_plenum"):
        cp = coarse[field] / coarse["e_all"]
        fp = fine[field] / fine["e_all"]
        participation[field] = {"maximum_absolute_change": float(np.max(np.abs(fp-cp))),
                                "rms_change": float(np.sqrt(np.mean((fp-cp)**2)))}
    gates = {
        "all_peaks_identified": all(item["coarse"].get("identified") and item["fine"].get("identified") for item in peaks.values()),
        "maximum_peak_center_relative_change_below_1pct": bool(peak_changes and max(peak_changes) < 0.01),
        "maximum_fixed_window_db_change_below_0p5": max(window_db_changes) < 0.5,
        "fixed_window_contrast_change_below_0p5": contrast_change < 0.5,
        "all_results_finite": all(np.all(np.isfinite(coarse[key])) and np.all(np.isfinite(fine[key])) for key in FIELDS),
        "fine_global_hmax_ratio_at_most_0p75": FINE_TO_COARSE_HMAX_RATIO <= 0.75,
    }
    return {
        "peaks": peaks, "fixed_windows": windows,
        "fixed_window_contrast": {"coarse_db": contrast_coarse, "fine_db": contrast_fine,
                                  "absolute_change_db": contrast_change},
        "microphone_complex_transfer": {
            "maximum_absolute_difference": float(np.max(mic_complex_delta)),
            "rms_absolute_difference": float(np.sqrt(np.mean(mic_complex_delta**2))),
            "relative_l2_difference": float(np.linalg.norm(fine["mic"]-coarse["mic"]) / np.linalg.norm(coarse["mic"])),
        },
        "participation_changes": participation,
        "gates": gates, "pass": all(gates.values()),
        "thresholds": {"peak_center_relative_change_strict_less_than": 0.01,
                       "fixed_window_db_change_strict_less_than": 0.5,
                       "fine_to_coarse_hmax_ratio_maximum": 0.75},
        "low_mesh_quality_warning_retained": True,
    }


def write_combined_csvs(formal_records: list[dict[str, Any]]) -> None:
    transfer_rows: list[dict[str, Any]] = []
    participation_rows: list[dict[str, Any]] = []
    for record in formal_records:
        values = load_npz(OUT / record["raw_npz"])
        for index, frequency in enumerate(values["frequency"]):
            pressure = values["mic"][index]
            common = {"model": record["kind"], "excitation": record["excitation"],
                      "mesh": record["mesh_variant"], "grid_index": index,
                      "frequency_hz": f"{frequency:.15g}"}
            transfer_rows.append({**common, "real": f"{pressure.real:.17g}",
                                  "imag": f"{pressure.imag:.17g}",
                                  "magnitude": f"{abs(pressure):.17g}",
                                  "phase_deg": f"{np.degrees(np.angle(pressure)):.17g}"})
            total = float(values["e_all"][index])
            p03 = float(values["e_hr03"][index] / total)
            psouth = float(values["e_south"][index] / total)
            pplenum = float(values["e_plenum"][index] / total)
            participation_rows.append({**common,
                "total_energy_j": f"{total:.17g}", "hr03_energy_j": f"{values['e_hr03'][index]:.17g}",
                "south_energy_j": f"{values['e_south'][index]:.17g}",
                "plenum_energy_j": f"{values['e_plenum'][index]:.17g}",
                "hr03_participation": f"{p03:.17g}", "south_participation": f"{psouth:.17g}",
                "plenum_participation": f"{pplenum:.17g}",
                "remainder_participation": f"{1.0-p03-psouth-pplenum:.17g}"})
    atomic_csv(OUT / "complex_transfer.csv", transfer_rows,
               ["model", "excitation", "mesh", "grid_index", "frequency_hz", "real", "imag", "magnitude", "phase_deg"])
    atomic_csv(OUT / "cavity_and_plenum_participation.csv", participation_rows,
               ["model", "excitation", "mesh", "grid_index", "frequency_hz", "total_energy_j",
                "hr03_energy_j", "south_energy_j", "plenum_energy_j", "hr03_participation",
                "south_participation", "plenum_participation", "remainder_participation"])


def run_gate(client: mph.Client) -> tuple[bool, list[dict[str, Any]]]:
    records = []
    try:
        coarse_control = solve_case(client, "ISO_CODED", "N", SMOKE_FREQ, "coarse", "SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE")
    except Exception as exc:
        raise SessionEnvironmentFailure(str(exc)) from exc
    records.append(coarse_control)
    try:
        fine_smoke = solve_case(client, "ISO_CODED", "N", SMOKE_FREQ, "fine", "GATE_ISO_CODED_N_FINE_SMOKE")
    except Exception as exc:
        raise SolverDatasetFailure(str(exc)) from exc
    records.append(fine_smoke)
    coarse = solve_case(client, "ISO_CODED", "N", FORMAL_FREQ, "coarse", "ISO_CODED_N_COARSE")
    records.append(coarse)
    fine = solve_case(client, "ISO_CODED", "N", FORMAL_FREQ, "fine", "GATE_ISO_CODED_N_FINE")
    records.append(fine)
    convergence = convergence_metrics(load_npz(OUT / coarse["raw_npz"]), load_npz(OUT / fine["raw_npz"]))
    convergence["coarse_control_run"] = coarse_control["mph"]
    convergence["coarse_run"] = coarse["mph"]
    convergence["fine_run"] = fine["mph"]
    convergence["fine_smoke_run"] = fine_smoke["mph"]
    atomic_json(OUT / "numerical_convergence.json", convergence)
    return bool(convergence["pass"]), records


def run_all(client: mph.Client, server_port: int) -> dict[str, Any]:
    started = datetime.now().astimezone().isoformat()
    session_log: dict[str, Any] = {
        "started_at": started, "COMSOL_version": str(client.version), "server_port": server_port,
        "cores": 4, "initial_model_count": len(client.models()),
        "pressure_acoustics_license_evidence": "real Pressure Acoustics frequency solves completed",
        "runs": [], "final_test_read": False,
    }
    atomic_json(OUT / "solver_session_license_log.json", session_log)
    all_records: list[dict[str, Any]] = []
    try:
        gate_pass, gate_records = run_gate(client)
        all_records.extend(gate_records)
        session_log["runs"] = all_records
        session_log["numerical_gate_pass"] = gate_pass
        atomic_json(OUT / "solver_session_license_log.json", session_log)
        if not gate_pass:
            atomic_json(OUT / "execution_state.json", {
                "technical_status": "TRANS1_RETRY_01_BLOCKED_BY_NUMERICAL_GATE",
                "numerical_gate_pass": False, "formal_six_completed": False,
                "completed_runs": [record["mph"] for record in all_records],
                "final_test_read": False,
            })
            return {"gate_pass": False, "records": all_records}
        formal_records = [gate_records[2]]
        for kind, excitation in CASES[1:]:
            stem = f"{kind}_{excitation}_COARSE"
            record = solve_case(client, kind, excitation, FORMAL_FREQ, "coarse", stem)
            formal_records.append(record)
            all_records.append(record)
            session_log["runs"] = all_records
            atomic_json(OUT / "solver_session_license_log.json", session_log)
        write_combined_csvs(formal_records)
        reload_records = [record["reload"] for record in all_records]
        atomic_json(OUT / "mph_reload_validation.json", {
            "runs": reload_records, "all_pass": all(item["pass"] for item in reload_records),
            "maximum_pressure_difference_pa": max(item["maximum_complex_pressure_difference_pa"] for item in reload_records),
        })
        atomic_json(OUT / "geometry_and_selection_audit.json", {
            "authority": AUTHORITY.relative_to(ROOT).as_posix(),
            "runs": [{"model": record["kind"], "excitation": record["excitation"],
                      "mesh": record["mesh_variant"], **record["geometry_and_selection"]}
                     for record in formal_records],
            "all_port_and_cavity_gates_pass": all(
                record["geometry_and_selection"]["selection_audit"]["port_identity_pass"]
                and record["geometry_and_selection"]["cavity_domain_selection_audit"]["pass"]
                and record["geometry_and_selection"]["cavity_domain_selection_audit"]["integration_binding_pass"]
                for record in formal_records),
        })
        mesh_rows = [{"model": record["kind"], "excitation": record["excitation"],
                      "mesh": record["mesh_variant"], "elements": record["mesh"]["elements"],
                      "vertices": record["mesh"]["vertices"],
                      "minimum_quality": record["mesh"]["minimum_quality"],
                      "mean_quality": record["mesh"]["mean_quality"],
                      "solve_elapsed_s": record["solve_elapsed_s"]} for record in all_records]
        atomic_csv(OUT / "mesh_statistics.csv", mesh_rows,
                   ["model", "excitation", "mesh", "elements", "vertices", "minimum_quality", "mean_quality", "solve_elapsed_s"])
        atomic_json(OUT / "mesh_statistics.json", {
            "warning": "LOW_MESH_QUALITY_WARNING", "runs": mesh_rows,
            "fine_hmax": {"coarse_reference_m": COARSE_REFERENCE_HMAX_M,
                          "fine_global_m": FINE_GLOBAL_HMAX_M,
                          "fine_critical_m": FINE_CRITICAL_HMAX_M,
                          "ratio": FINE_TO_COARSE_HMAX_RATIO, "gate_pass": FINE_TO_COARSE_HMAX_RATIO <= 0.75},
        })
        atomic_json(OUT / "execution_state.json", {
            "technical_status": "EXECUTION_ACCEPTED", "numerical_gate_pass": True,
            "formal_six_completed": True, "completed_runs": [record["mph"] for record in all_records],
            "formal_runs": [record["mph"] for record in formal_records], "final_test_read": False,
        })
        session_log["completed_at"] = datetime.now().astimezone().isoformat()
        session_log["formal_six_completed"] = True
        atomic_json(OUT / "solver_session_license_log.json", session_log)
        return {"gate_pass": True, "records": all_records, "formal_records": formal_records}
    except Exception as exc:
        if isinstance(exc, SessionEnvironmentFailure):
            terminal = "TRANS1_RETRY_02_BLOCKED_BY_SESSION_OR_ENVIRONMENT"
        elif isinstance(exc, SolverDatasetFailure):
            terminal = "TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET"
        else:
            terminal = "TRANS1_RETRY_02_BLOCKED_BY_SOLVER_DATASET"
        failure = {"created_at": datetime.now().astimezone().isoformat(),
                   "error_type": type(exc).__name__, "error": str(exc),
                   "traceback": traceback.format_exc(), "completed_runs": [record.get("mph") for record in all_records],
                   "final_test_read": False}
        atomic_json(OUT / "solver_failure.json", failure)
        session_log["failure"] = failure
        atomic_json(OUT / "solver_session_license_log.json", session_log)
        atomic_json(OUT / "execution_state.json", {
            "technical_status": terminal,
            "numerical_gate_pass": False, "formal_six_completed": False,
            "completed_runs": failure["completed_runs"], "final_test_read": False,
        })
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    client = mph.Client(version="6.4", port=args.port)
    try:
        if client.models():
            raise RuntimeError(f"Fresh-session gate failed; initial models={client.models()}")
        result = run_all(client, args.port)
        print(json.dumps({"success": True, "gate_pass": result["gate_pass"],
                          "record_count": len(result["records"])}, indent=2))
    finally:
        for model in list(client.models()):
            try:
                client.remove(model)
            except Exception:
                pass
        client.disconnect()


if __name__ == "__main__":
    main()

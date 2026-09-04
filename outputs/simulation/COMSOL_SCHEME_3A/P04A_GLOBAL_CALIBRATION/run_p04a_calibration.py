"""Execute the frozen P04A calibration against the active COMSOL 6.4 server.

The script is deliberately restartable.  Nominal model construction, response
cache entries, and the search checkpoint are committed with atomic file replaces.
It never reads any final-test path and never inspects HR modules other than HR03.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import mph
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04A_GLOBAL_CALIBRATION"
P02 = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P02_P05_BASELINE/COMSOL_3A_P02_P05_BASELINE.mph"
P03_DIR = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01"
P04A0 = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04A0_CALIBRATION_PREFLIGHT"
EXPERIMENT_NPZ = ROOT / "outputs/supplemental/V25-S1_S2_S3_JOINT_ANALYSIS/preprocessed_spectra.npz"
PORT = 64706
FREQUENCY = 200.0 * 2.0 ** (np.arange(256, dtype=np.float64) / 48.0)
CAL = np.arange(147, 163)
PRIMARY_BAND = np.arange(0, 208)
SECONDARY_BAND = np.arange(208, 256)
P05_NOMINAL = OUT / "P04A_P05_NOMINAL.mph"
HR03_NOMINAL = OUT / "P04A_HR03_NOMINAL.mph"
P05_SELECTED = OUT / "P04A_P05_CALIBRATED.mph"
HR03_SELECTED = OUT / "P04A_HR03_CALIBRATED.mph"
CHECKPOINT = OUT / "calibration_checkpoint.json"
SEARCH_CSV = OUT / "calibration_search_table.csv"
LOG = OUT / "solver_session_license.log"

PRIMARY_IDS = {
    "P05": [
        "V25S1-BASE-B01-R01", "V25S1-BASE-B01-R03",
        "V25S1-BASE-B02-R01", "V25S1-BASE-B02-R02",
        "V25S1-BASE-B02-R03",
    ],
    "HR03": [
        "V25S1-HR03-B01-R01", "V25S1-HR03-B01-R03",
        "V25S1-HR03-B02-R01", "V25S1-HR03-B02-R02",
        "V25S1-HR03-B02-R03",
    ],
}
ALL_IDS = {
    "P05": [
        "V25S1-BASE-B01-R01", "V25S1-BASE-B01-R02", "V25S1-BASE-B01-R03",
        "V25S1-BASE-B02-R01", "V25S1-BASE-B02-R02", "V25S1-BASE-B02-R03",
    ],
    "HR03": [
        "V25S1-HR03-B01-R01", "V25S1-HR03-B01-R02", "V25S1-HR03-B01-R03",
        "V25S1-HR03-B02-R01", "V25S1-HR03-B02-R02", "V25S1-HR03-B02-R03",
    ],
}


def log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = f"{stamp} {message}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
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


def serial_complex(values: np.ndarray) -> list[dict[str, float]]:
    return [
        {"real": float(v.real), "imag": float(v.imag), "magnitude": float(abs(v)),
         "phase_deg": float(np.degrees(np.angle(v)))}
        for v in np.asarray(values).reshape(-1)
    ]


def write_complex_csv(path: Path, values: np.ndarray) -> None:
    rows = []
    for index, (frequency, value) in enumerate(zip(FREQUENCY, np.asarray(values).reshape(-1))):
        rows.append({
            "grid_index": index, "frequency_hz": f"{frequency:.15g}",
            "real": f"{value.real:.17g}", "imag": f"{value.imag:.17g}",
            "magnitude": f"{abs(value):.17g}",
            "phase_deg": f"{np.degrees(np.angle(value)):.17g}",
        })
    atomic_csv(path, rows, ["grid_index", "frequency_hz", "real", "imag", "magnitude", "phase_deg"])


def read_complex_csv(path: Path) -> np.ndarray:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if len(rows) != 256:
        raise RuntimeError(f"Expected 256 rows in {path}, found {len(rows)}")
    return np.asarray([complex(float(row["real"]), float(row["imag"])) for row in rows])


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
    return [int(value) for value in comp.selection(tag).entities()]


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


def set_explicit_selection(comp, tag: str, dim: int, entities: Iterable[int]) -> None:
    try:
        comp.selection().remove(tag)
    except Exception:
        pass
    selection = comp.selection().create(tag, "Explicit")
    selection.geom("geom1", dim)
    selection.set([int(value) for value in entities])


def configure_common_model(model: mph.Model, kind: str) -> dict[str, Any]:
    java = model.java
    name = f"P04A_{kind}_REDUCED"
    java.label(name)
    comp = java.component("comp1")
    geom = comp.geom("geom1")
    physics = comp.physics("acpr")

    java.param().set("hr_neck_effective_length_delta_mm", "0[mm]",
                     "P04A frozen feature-class effective neck-length correction")
    java.param().set("effective_loss_scale", "1",
                     "P04A frozen effective boundary-layer loss scale")
    java.param().set("mu0_cal", "1.814e-5[Pa*s]")
    java.param().set("k0_cal", "0.0257[W/(m*K)]")
    java.param().set("Cp0_cal", "1005[J/(kg*K)]")
    java.param().set("gamma0_cal", "1.4")

    if kind == "HR03":
        geom.feature().remove("p05_000")
        features = {
            "hr03_neck_inner_000": ((-0.0014, 0.0314, 0.0042), (0.0028, 0.0236, 0.0064)),
            "hr03_cavity_000": ((-0.0075, 0.0550, 0.0042), (0.0150, 0.0260, 0.0064)),
            "hr03_neck_outer_000": ((-0.0022, 0.0810, 0.0042), (0.0044, 0.0076, 0.0064)),
        }
        for tag, (position, size) in features.items():
            feature = geom.feature().create(tag, "Block")
            feature.set("pos", [str(value) for value in position])
            feature.set("size", [str(value) for value in size])
            feature.set("selresult", True)
        geom.run()
        eps = 1.0e-7
        add_box_selection(comp, "sel_hr03_neck_inner", 3,
                          (-0.0014-eps, 0.0014+eps, 0.0314-eps, 0.0550+eps, 0.0042-eps, 0.0106+eps))
        add_box_selection(comp, "sel_hr03_cavity", 3,
                          (-0.0075-eps, 0.0075+eps, 0.0550-eps, 0.0810+eps, 0.0042-eps, 0.0106+eps))
        add_box_selection(comp, "sel_hr03_neck_outer", 3,
                          (-0.0022-eps, 0.0022+eps, 0.0810-eps, 0.0886+eps, 0.0042-eps, 0.0106+eps))
        geom.run()
    else:
        geom.run()

    # Physics always acts on every connected fluid domain.  Domain-specific
    # HR features below encode effective acoustic length without changing CAD.
    physics.selection().all()
    all_domains = selection_entities(comp, "sel_fluid_all")
    neck_inner: list[int] = []
    neck_outer: list[int] = []
    if kind == "HR03":
        neck_inner = selection_entities(comp, "sel_hr03_neck_inner")
        neck_outer = selection_entities(comp, "sel_hr03_neck_outer")
        for tag, selection, length in (
            ("fpam_hr_inner", "sel_hr03_neck_inner", "23.6[mm]"),
            ("fpam_hr_outer", "sel_hr03_neck_outer", "7.6[mm]"),
        ):
            try:
                physics.feature().remove(tag)
            except Exception:
                pass
            medium = physics.create(tag, "FrequencyPressureAcousticsModel", 3)
            medium.selection().named(selection)
            stretch = f"(1+hr_neck_effective_length_delta_mm/({length}))"
            medium.set("c_mat", "userdef")
            medium.set("c", f"c0_nom/{stretch}")
            medium.set("rho_mat", "userdef")
            medium.set("rho", f"rho0_nom*{stretch}")
            medium.label(f"Effective-length medium {selection}")
    else:
        pass

    # Select true exterior walls using adjacency, excluding the driven pressure
    # face.  This avoids applying the BLI feature to retained internal partitions.
    source_boundaries = set(selection_entities(comp, "bnd_port_000"))
    wetted = [boundary for boundary in exterior_boundaries(geom) if boundary not in source_boundaries]
    set_explicit_selection(comp, "bnd_wetted_exterior", 2, wetted)
    try:
        physics.feature().remove("bli_cal")
    except Exception:
        pass
    bli = physics.create("bli_cal", "ThermoviscousBoundaryLayerImpedance", 2)
    bli.selection().named("bnd_wetted_exterior")
    bli.set("c_mat", "userdef")
    bli.set("c", "c0_nom")
    bli.set("rho_mat", "userdef")
    bli.set("rho", "rho0_nom")
    bli.set("mu_mat", "userdef")
    bli.set("mu", "mu0_cal*effective_loss_scale^2")
    bli.set("kcond_mat", "userdef")
    bli.set("kcond", "k0_cal*effective_loss_scale^2")
    bli.set("Cp_mat", "userdef")
    bli.set("Cp", "Cp0_cal")
    bli.set("gamma_mat", "userdef")
    bli.set("gamma", "gamma0_cal")
    bli.label("P04A identical effective-loss formulation on exterior wetted walls")

    physics.prop("MeshControl").set("SizeControlParameter", "Frequency")
    physics.prop("MeshControl").set("PhysicsControlledMeshMaximumFrequency", "25000[Hz]")
    mesh = comp.mesh("mesh1")
    mesh.automatic(True)
    mesh.autoMeshSize(6)
    mesh.run()

    frequency_list = " ".join(f"{value:.15g}" for value in FREQUENCY)
    java.study("std_freq").feature("step1").set("plist", frequency_list)
    component_count, component_sizes = connected_components(geom)
    return {
        "model_name": name,
        "kind": kind,
        "domain_count": len(all_domains),
        "connected_components": component_count,
        "connected_component_domain_counts": component_sizes,
        "source_boundaries": sorted(source_boundaries),
        "wetted_exterior_boundaries": wetted,
        "mic_boundaries": selection_entities(comp, "sel_mic_nominal"),
        "module_domains": selection_entities(comp, "sel_module_000"),
        "hr03_neck_inner_domains": neck_inner,
        "hr03_neck_outer_domains": neck_outer,
        "frequency_count": len(FREQUENCY),
        "mesh_strategy": "P02 physics-controlled Pressure Acoustics mesh, 25 kHz control, automatic size 6",
        "loss_implementation": {
            "feature": "bli_cal/ThermoviscousBoundaryLayerImpedance",
            "selection": "bnd_wetted_exterior",
            "mu": "mu0_cal*effective_loss_scale^2",
            "kcond": "k0_cal*effective_loss_scale^2",
            "reason": "viscous and thermal penetration depths, hence the effective BLI loss thickness, scale linearly with effective_loss_scale",
        },
        "effective_length_implementation": (
            "Neck-domain transformation-equivalent c=c0/s, rho=rho0*s with s=1+delta/L; "
            "characteristic impedance remains rho*c and the axial acoustic phase length becomes L+delta."
            if kind == "HR03" else "empty HR-neck feature-class selection"
        ),
    }


def solve_response(model: mph.Model, delta_mm: float, loss_scale: float) -> tuple[np.ndarray, float]:
    java = model.java
    java.param().set("hr_neck_effective_length_delta_mm", f"{delta_mm:.12g}[mm]")
    java.param().set("effective_loss_scale", f"{loss_scale:.12g}")
    started = time.perf_counter()
    java.study("std_freq").run()
    elapsed = time.perf_counter() - started
    frequencies = np.asarray(model.evaluate("freq")).real.reshape(-1)
    values = np.asarray(model.evaluate("aveop_mic(acpr.p_t)/p_inc")).reshape(-1)
    if frequencies.size != 256 or values.size != 256:
        raise RuntimeError(f"Expected 256 values, got freq={frequencies.size}, response={values.size}")
    if not np.allclose(frequencies, FREQUENCY, rtol=1e-11, atol=1e-9):
        raise RuntimeError("COMSOL frequency readback does not match frozen exact grid")
    return values, elapsed


def build_nominal(client: mph.Client) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    preflight: dict[str, Any] = {
        "phase_id": "P04A_GLOBAL_CALIBRATION",
        "comsol_version": client.version,
        "server_port": PORT,
        "models": {},
        "nominal": {"hr_neck_effective_length_delta_mm": 0.0, "effective_loss_scale": 1.0},
    }
    for kind, path in (("P05", P05_NOMINAL), ("HR03", HR03_NOMINAL)):
        log(f"Building {kind} nominal comparable model from P02 authority")
        model = client.load(P02)
        structure = configure_common_model(model, kind)
        response, elapsed = solve_response(model, 0.0, 1.0)
        if not np.all(np.isfinite(response.real)) or not np.all(np.isfinite(response.imag)):
            raise RuntimeError(f"{kind} nominal response is nonfinite")
        if np.any(np.abs(response) == 0.0):
            raise RuntimeError(f"{kind} nominal response contains zero magnitude")
        model.save(path)
        before = response.copy()
        client.remove(model)
        reloaded = client.load(path)
        after = np.asarray(reloaded.evaluate("aveop_mic(acpr.p_t)/p_inc")).reshape(-1)
        reload_max_abs = float(np.max(np.abs(before - after)))
        if reload_max_abs > 1e-12:
            raise RuntimeError(f"{kind} save/reload mismatch {reload_max_abs}")
        structure.update({
            "solve_seconds": elapsed,
            "response_finite": True,
            "response_nonzero": True,
            "response_magnitude_min": float(np.min(np.abs(response))),
            "response_magnitude_max": float(np.max(np.abs(response))),
            "save_reload_max_abs": reload_max_abs,
            "saved_model": str(path.relative_to(ROOT)),
            "saved_model_sha256": sha256(path),
        })
        preflight["models"][kind] = structure
        write_complex_csv(OUT / f"nominal_{kind.lower()}_complex_transfer.csv", response)
        client.remove(reloaded)

    p05 = read_complex_csv(OUT / "nominal_p05_complex_transfer.csv")
    hr03 = read_complex_csv(OUT / "nominal_hr03_complex_transfer.csv")
    relative = 20.0 * np.log10(np.abs(hr03 / p05))
    feature = extract_feature(smooth_db(relative))
    p03_center = 1904.1942270911236
    preflight["nominal_relative_feature"] = feature
    preflight["p03_thermoviscous_fine_center_hz"] = p03_center
    preflight["nominal_feature_vs_p03_percent"] = 100.0 * (feature["centre_hz"] - p03_center) / p03_center
    preflight["physical_consistency_gate"] = {
        "rule": "interior relative feature within the prospectively frozen HR03 CAD +/-1/6-octave window",
        "pass": bool(not feature["at_window_boundary"]),
    }
    atomic_json(OUT / "nominal_model_preflight.json", preflight)
    if preflight["models"]["P05"]["connected_components"] != 1 or preflight["models"]["HR03"]["connected_components"] != 1:
        raise RuntimeError("Nominal geometry is not one connected component")
    if feature["at_window_boundary"]:
        raise RuntimeError("Nominal HR03-minus-P05 feature is boundary-only")
    log(f"Nominal preflight complete; relative feature {feature['centre_hz']:.3f} Hz")


def load_experiment() -> dict[str, np.ndarray]:
    payload = np.load(EXPERIMENT_NPZ, allow_pickle=False)
    sample_ids = [str(value) for value in payload["sample_ids"]]
    curves = {sample_id: payload["magnitude_db"][index] for index, sample_id in enumerate(sample_ids)}
    def representative(ids: list[str]) -> np.ndarray:
        return np.median(np.vstack([curves[sample_id] for sample_id in ids]), axis=0)
    primary = representative(PRIMARY_IDS["HR03"]) - representative(PRIMARY_IDS["P05"])
    all_six = representative(ALL_IDS["HR03"]) - representative(ALL_IDS["P05"])
    if not np.all(np.isfinite(primary[CAL])) or not np.all(np.isfinite(all_six[CAL])):
        raise RuntimeError("Frozen experimental calibration window is incomplete")
    return {
        "primary_relative_db": primary,
        "all_six_relative_db": all_six,
        "primary_demeaned": primary - float(np.mean(primary[CAL])),
        "all_six_demeaned": all_six - float(np.mean(all_six[CAL])),
        "curves": curves,
    }


def smooth_db(values: np.ndarray) -> np.ndarray:
    result = np.full_like(np.asarray(values, dtype=np.float64), np.nan)
    log_frequency = np.log2(FREQUENCY)
    half_width = 1.0 / 24.0
    valid = np.isfinite(values)
    for index, center in enumerate(log_frequency):
        window = valid & (log_frequency >= center-half_width-1e-12) & (log_frequency <= center+half_width+1e-12)
        if np.any(window):
            result[index] = float(np.mean(values[window]))
    return result


def local_residual(values: np.ndarray) -> np.ndarray:
    x = np.log2(FREQUENCY[CAL])
    local = np.asarray(values)[CAL]
    edge_count = max(1, int(math.ceil(local.size * 0.15)))
    edge_indices = np.r_[0:edge_count, local.size-edge_count:local.size]
    coefficients = np.polyfit(x[edge_indices], local[edge_indices], 1)
    return local - np.polyval(coefficients, x)


def extract_feature(values: np.ndarray) -> dict[str, Any]:
    residual = local_residual(values)
    peak = int(np.argmax(np.abs(residual)))
    signed = float(residual[peak])
    threshold = abs(signed) / math.sqrt(2.0)
    above = np.flatnonzero(np.abs(residual) >= threshold)
    bandwidth = float(FREQUENCY[CAL][above[-1]] - FREQUENCY[CAL][above[0]]) if above.size > 1 else 0.0
    return {
        "centre_hz": float(FREQUENCY[CAL][peak]),
        "signed_contrast_db": signed,
        "absolute_contrast_db": abs(signed),
        "bandwidth_hz": bandwidth,
        "Q": float(FREQUENCY[CAL][peak] / bandwidth) if bandwidth > 0 else None,
        "at_window_boundary": bool(peak in (0, CAL.size-1)),
    }


def rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def diagnostics(p05: np.ndarray, hr03: np.ndarray, experiment: dict[str, np.ndarray]) -> dict[str, Any]:
    if (not np.all(np.isfinite(p05.real)) or not np.all(np.isfinite(p05.imag)) or
            not np.all(np.isfinite(hr03.real)) or not np.all(np.isfinite(hr03.imag)) or
            np.any(np.abs(p05) == 0.0) or np.any(np.abs(hr03) == 0.0)):
        return {"finite": False, "J5_db": math.inf, "failure": "nonfinite_or_zero_complex_transfer"}
    raw = 20.0 * np.log10(np.abs(hr03 / p05))
    smoothed = smooth_db(raw)
    simulated = smoothed - float(np.mean(smoothed[CAL]))
    feature = extract_feature(smoothed)
    if feature["at_window_boundary"]:
        return {"finite": False, "J5_db": math.inf, "failure": "boundary_only_feature", "feature": feature}
    j5 = rms((simulated - experiment["primary_demeaned"])[CAL])
    j6 = rms((simulated - experiment["all_six_demeaned"])[CAL])
    primary_valid = np.isfinite(experiment["primary_relative_db"][PRIMARY_BAND])
    secondary_valid = np.isfinite(experiment["primary_relative_db"][SECONDARY_BAND])
    def band_shape(indices: np.ndarray, valid: np.ndarray) -> float:
        exp = experiment["primary_relative_db"][indices][valid]
        sim = smoothed[indices][valid]
        return rms((sim-np.mean(sim))-(exp-np.mean(exp)))
    return {
        "finite": True,
        "J5_db": j5,
        "J6_db": j6,
        "feature": feature,
        "p05_peak_magnitude": float(np.max(np.abs(p05[CAL]))),
        "hr03_peak_magnitude": float(np.max(np.abs(hr03[CAL]))),
        "p05_phase_at_hr_feature_deg": float(np.degrees(np.angle(p05[CAL][np.argmax(np.abs(local_residual(smoothed)))]))),
        "hr03_phase_at_hr_feature_deg": float(np.degrees(np.angle(hr03[CAL][np.argmax(np.abs(local_residual(smoothed)))]))),
        "primary_band_shape_rms_db": band_shape(PRIMARY_BAND, primary_valid),
        "secondary_band_shape_rms_db": band_shape(SECONDARY_BAND, secondary_valid),
        "primary_band_coverage": int(np.sum(primary_valid)),
        "secondary_band_coverage": int(np.sum(secondary_valid)),
        "simulated_relative_raw_db": raw,
        "simulated_relative_smoothed_db": smoothed,
        "simulated_relative_demeaned_db": simulated,
    }


def candidate_key(delta: float, loss: float) -> str:
    return f"d{delta:+.3f}_l{loss:.4f}".replace("+", "p").replace("-", "m").replace(".", "p")


def checkpoint_rows(checkpoint: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in checkpoint["order"]:
        item = checkpoint["candidates"][key]
        rows.append({field: item.get(field, "") for field in checkpoint["csv_fields"]})
    return rows


def write_checkpoint(checkpoint: dict[str, Any]) -> None:
    atomic_json(CHECKPOINT, checkpoint)
    atomic_csv(SEARCH_CSV, checkpoint_rows(checkpoint), checkpoint["csv_fields"])


def choose_best(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    finite = [item for item in items if math.isfinite(float(item["J5_db"]))]
    if not finite:
        raise RuntimeError("No finite candidate in completed stage")
    minimum = min(float(item["J5_db"]) for item in finite)
    tied = [item for item in finite if float(item["J5_db"]) <= minimum + 0.01]
    return min(tied, key=lambda item: (
        (float(item["delta_mm"])/0.4)**2 + ((float(item["loss_scale"])-1.0)/1.5)**2,
        abs(float(item["delta_mm"])), abs(float(item["loss_scale"])-1.0),
        float(item["delta_mm"]), float(item["loss_scale"]),
    ))


def load_or_create_checkpoint() -> dict[str, Any]:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    value = {
        "schema_version": "p04a_checkpoint_v1",
        "contract_sha256": sha256(P04A0 / "calibration_contract_addendum.json"),
        "search_plan_sha256": sha256(P04A0 / "search_plan.json"),
        "model_seed_sha256": {"P05": sha256(P05_NOMINAL), "HR03": sha256(HR03_NOMINAL)},
        "status": "in_progress", "current_stage": "coarse",
        "order": [], "candidates": {}, "stage_centres": {},
        "p05_cache": {}, "solve_counts": {"P05": 0, "HR03": 0, "total": 0},
        "csv_fields": [
            "sequence", "stage", "candidate_id", "delta_mm", "loss_scale",
            "p05_model_sha256", "hr03_model_sha256", "configuration_sha256",
            "p05_solver_status", "hr03_solver_status", "finite", "coverage_256",
            "J5_db", "J6_db", "feature_centre_hz", "feature_contrast_db",
            "bandwidth_hz", "Q", "primary_band_shape_rms_db",
            "secondary_band_shape_rms_db", "p05_solve_seconds", "hr03_solve_seconds",
            "p05_response_path", "hr03_response_path", "solver_message",
            "last_successful_frequency_hz",
        ],
    }
    write_checkpoint(value)
    return value


def evaluate_candidate(
    checkpoint: dict[str, Any], stage: str, delta: float, loss: float,
    p05_model: mph.Model, hr_model: mph.Model, experiment: dict[str, np.ndarray],
) -> None:
    key = candidate_key(delta, loss)
    if key in checkpoint["candidates"]:
        log(f"Resume skip atomically recorded candidate {key}")
        return
    config = {
        "candidate_id": key, "stage": stage, "delta_mm": delta, "loss_scale": loss,
        "p05_seed_sha256": checkpoint["model_seed_sha256"]["P05"],
        "hr03_seed_sha256": checkpoint["model_seed_sha256"]["HR03"],
        "frequency_grid_sha256": hashlib.sha256(FREQUENCY.tobytes()).hexdigest(),
    }
    config_path = OUT / "candidate_configs" / f"{key}.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(config_path, config)
    p05_cache_key = f"{loss:.6f}"
    p05_path = OUT / "responses" / f"p05_loss_{loss:.6f}.csv"
    p05_seconds = 0.0
    p05_status = "cached"
    try:
        if p05_cache_key in checkpoint["p05_cache"] and p05_path.exists():
            p05 = read_complex_csv(p05_path)
        else:
            p05, p05_seconds = solve_response(p05_model, 0.0, loss)
            p05_path.parent.mkdir(parents=True, exist_ok=True)
            write_complex_csv(p05_path, p05)
            checkpoint["p05_cache"][p05_cache_key] = {
                "path": str(p05_path.relative_to(ROOT)), "sha256": sha256(p05_path),
            }
            checkpoint["solve_counts"]["P05"] += 1
            checkpoint["solve_counts"]["total"] += 1
            p05_status = "completed"
            write_checkpoint(checkpoint)
        hr_path = OUT / "responses" / f"hr03_{key}.csv"
        hr03, hr_seconds = solve_response(hr_model, delta, loss)
        write_complex_csv(hr_path, hr03)
        checkpoint["solve_counts"]["HR03"] += 1
        checkpoint["solve_counts"]["total"] += 1
        result = diagnostics(p05, hr03, experiment)
        item = {
            "sequence": len(checkpoint["order"]) + 1, "stage": stage, "candidate_id": key,
            "delta_mm": delta, "loss_scale": loss,
            "p05_model_sha256": checkpoint["model_seed_sha256"]["P05"],
            "hr03_model_sha256": checkpoint["model_seed_sha256"]["HR03"],
            "configuration_sha256": sha256(config_path),
            "p05_solver_status": p05_status, "hr03_solver_status": "completed",
            "finite": result["finite"], "coverage_256": 256,
            "J5_db": result["J5_db"], "J6_db": result.get("J6_db", math.inf),
            "feature_centre_hz": result.get("feature", {}).get("centre_hz", ""),
            "feature_contrast_db": result.get("feature", {}).get("signed_contrast_db", ""),
            "bandwidth_hz": result.get("feature", {}).get("bandwidth_hz", ""),
            "Q": result.get("feature", {}).get("Q", ""),
            "primary_band_shape_rms_db": result.get("primary_band_shape_rms_db", ""),
            "secondary_band_shape_rms_db": result.get("secondary_band_shape_rms_db", ""),
            "p05_solve_seconds": p05_seconds, "hr03_solve_seconds": hr_seconds,
            "p05_response_path": str(p05_path.relative_to(ROOT)),
            "hr03_response_path": str(hr_path.relative_to(ROOT)),
            "solver_message": result.get("failure", "completed"),
            "last_successful_frequency_hz": float(FREQUENCY[-1]),
        }
    except Exception as exc:
        item = {
            "sequence": len(checkpoint["order"]) + 1, "stage": stage, "candidate_id": key,
            "delta_mm": delta, "loss_scale": loss,
            "p05_model_sha256": checkpoint["model_seed_sha256"]["P05"],
            "hr03_model_sha256": checkpoint["model_seed_sha256"]["HR03"],
            "configuration_sha256": sha256(config_path),
            "p05_solver_status": p05_status, "hr03_solver_status": "failed",
            "finite": False, "coverage_256": 0, "J5_db": math.inf, "J6_db": math.inf,
            "p05_response_path": str(p05_path.relative_to(ROOT)), "hr03_response_path": "",
            "solver_message": repr(exc),
            "last_successful_frequency_hz": "",
        }
        log(f"Candidate {key} failed: {exc!r}")
    checkpoint["order"].append(key)
    checkpoint["candidates"][key] = item
    write_checkpoint(checkpoint)
    log(f"Candidate {item['sequence']}/53 {key}: J5={item['J5_db']} status={item['hr03_solver_status']}")


def stage_grid(stage: str, checkpoint: dict[str, Any]) -> list[tuple[float, float]]:
    if stage == "coarse":
        return [(d, l) for d in (-0.2, -0.1, 0.0, 0.1, 0.2)
                for l in (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)]
    eligible_stages = {"coarse"} if stage == "refinement_1" else {"coarse", "refinement_1"}
    previous_items = [item for item in checkpoint["candidates"].values() if item["stage"] in eligible_stages]
    best = choose_best(previous_items)
    checkpoint["stage_centres"][stage] = {"delta_mm": best["delta_mm"], "loss_scale": best["loss_scale"]}
    dstep, lstep = ((0.05, 0.125) if stage == "refinement_1" else (0.025, 0.0625))
    values = []
    for delta in (float(best["delta_mm"])-dstep, float(best["delta_mm"]), float(best["delta_mm"])+dstep):
        for loss in (float(best["loss_scale"])-lstep, float(best["loss_scale"]), float(best["loss_scale"])+lstep):
            values.append((round(min(0.2, max(-0.2, delta)), 6), round(min(2.0, max(0.5, loss)), 6)))
    return list(dict.fromkeys(values))


def run_search(client: mph.Client) -> None:
    if not P05_NOMINAL.exists() or not HR03_NOMINAL.exists():
        raise RuntimeError("Nominal model preflight must complete first")
    experiment = load_experiment()
    checkpoint = load_or_create_checkpoint()
    p05_model = client.load(P05_NOMINAL)
    hr_model = client.load(HR03_NOMINAL)
    try:
        for stage in ("coarse", "refinement_1", "refinement_2"):
            checkpoint["current_stage"] = stage
            write_checkpoint(checkpoint)
            grid = stage_grid(stage, checkpoint)
            log(f"Starting {stage} with {len(grid)} frozen/deduplicated grid positions")
            for delta, loss in grid:
                evaluate_candidate(checkpoint, stage, delta, loss, p05_model, hr_model, experiment)
            completed_stages = {"coarse"} if stage == "coarse" else (
                {"coarse", "refinement_1"} if stage == "refinement_1" else
                {"coarse", "refinement_1", "refinement_2"}
            )
            cumulative_items = [item for item in checkpoint["candidates"].values()
                                if item["stage"] in completed_stages]
            best = choose_best(cumulative_items)
            checkpoint["stage_centres"][stage + "_best"] = {
                "candidate_id": best["candidate_id"], "delta_mm": best["delta_mm"],
                "loss_scale": best["loss_scale"], "J5_db": best["J5_db"],
            }
            write_checkpoint(checkpoint)
            log(f"Completed {stage}; tie-broken best={best['candidate_id']} J5={best['J5_db']}")
        if len(checkpoint["candidates"]) > 53 or checkpoint["solve_counts"]["total"] > 106:
            raise RuntimeError("Frozen search budget exceeded")
        final = choose_best(checkpoint["candidates"].values())
        checkpoint["status"] = "search_complete"
        checkpoint["selected_candidate_id"] = final["candidate_id"]
        checkpoint["current_stage"] = "complete"
        write_checkpoint(checkpoint)
        log(f"Search complete: {final['candidate_id']} delta={final['delta_mm']} loss={final['loss_scale']} J5={final['J5_db']}")
    finally:
        client.remove(p05_model)
        client.remove(hr_model)


def improvement_class(improvement: float) -> str:
    if improvement > 0.01:
        return "improved"
    if improvement < -0.01:
        return "worsened"
    return "indistinguishable"


def candidate_simulated_curve(item: dict[str, Any]) -> np.ndarray:
    p05 = read_complex_csv(ROOT / item["p05_response_path"])
    hr03 = read_complex_csv(ROOT / item["hr03_response_path"])
    raw = 20.0 * np.log10(np.abs(hr03 / p05))
    smoothed = smooth_db(raw)
    return smoothed - float(np.mean(smoothed[CAL]))


def analyze_and_freeze(client: mph.Client) -> None:
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if checkpoint.get("status") != "search_complete":
        raise RuntimeError("Search is not complete")
    items = list(checkpoint["candidates"].values())
    selected = choose_best(items)
    nominal = next(item for item in items if float(item["delta_mm"]) == 0.0 and float(item["loss_scale"]) == 1.0)
    experiment = load_experiment()
    simulated = {item["candidate_id"]: candidate_simulated_curve(item) for item in items if math.isfinite(float(item["J5_db"]))}

    # Repeat bootstrap: HR03 draw first, then P05, and select only among solved candidates.
    rng = np.random.default_rng(250825)
    curves = experiment["curves"]
    boot_rows = []
    finite_items = [item for item in items if item["candidate_id"] in simulated]
    for iteration in range(2000):
        hr_ids = rng.choice(PRIMARY_IDS["HR03"], size=5, replace=True)
        p05_ids = rng.choice(PRIMARY_IDS["P05"], size=5, replace=True)
        target = np.median(np.vstack([curves[str(value)] for value in hr_ids]), axis=0) - np.median(
            np.vstack([curves[str(value)] for value in p05_ids]), axis=0)
        target = target - float(np.mean(target[CAL]))
        bootstrap_items = []
        for item in finite_items:
            copy = dict(item)
            copy["J5_db"] = rms((simulated[item["candidate_id"]] - target)[CAL])
            bootstrap_items.append(copy)
        best = choose_best(bootstrap_items)
        boot_rows.append({
            "iteration": iteration + 1, "delta_mm": best["delta_mm"],
            "loss_scale": best["loss_scale"], "J_boot_db": best["J5_db"],
            "candidate_id": best["candidate_id"],
        })
    atomic_csv(OUT / "bootstrap_parameter_estimates.csv", boot_rows,
               ["iteration", "delta_mm", "loss_scale", "J_boot_db", "candidate_id"])
    deltas = np.asarray([float(row["delta_mm"]) for row in boot_rows])
    losses = np.asarray([float(row["loss_scale"]) for row in boot_rows])
    correlation = float(np.corrcoef(deltas, losses)[0, 1]) if np.std(deltas) > 0 and np.std(losses) > 0 else None
    delta_ci = np.percentile(deltas, [2.5, 97.5])
    loss_ci = np.percentile(losses, [2.5, 97.5])

    # Frozen profile and boundary diagnostics.
    jmin = min(float(item["J5_db"]) for item in finite_items)
    profile_summary = {}
    flat_flags = {}
    for parameter, bound_width in (("delta_mm", 0.4), ("loss_scale", 1.5)):
        profile = {}
        for value in sorted(set(float(item[parameter]) for item in finite_items)):
            profile[str(value)] = min(float(item["J5_db"]) for item in finite_items if float(item[parameter]) == value)
        near = [float(value) for value, objective in profile.items() if objective <= jmin + 0.05]
        span = max(near)-min(near) if len(near) >= 2 else 0.0
        flat = bool(span >= 0.5 * bound_width or len(near) < 2)
        profile_summary[parameter] = {"profile": profile, "near_optimal_values": near, "span": span,
                                      "bound_width": bound_width, "flat": flat}
        flat_flags[parameter] = flat
    selected_delta = float(selected["delta_mm"])
    selected_loss = float(selected["loss_scale"])
    boundary = {
        "delta_mm": bool(selected_delta <= -0.2+0.025 or selected_delta >= 0.2-0.025),
        "loss_scale": bool(selected_loss <= 0.5+0.0625 or selected_loss >= 2.0-0.0625),
    }
    interval_touches_bound = {
        "delta_mm": bool(delta_ci[0] <= -0.2 or delta_ci[1] >= 0.2),
        "loss_scale": bool(loss_ci[0] <= 0.5 or loss_ci[1] >= 2.0),
    }
    weak = {
        "delta_mm": bool(delta_ci[1]-delta_ci[0] >= 0.2),
        "loss_scale": bool(loss_ci[1]-loss_ci[0] >= 0.75),
    }
    primary_improvement = float(nominal["J5_db"])-float(selected["J5_db"])
    all6_improvement = float(nominal["J6_db"])-float(selected["J6_db"])
    primary_class = improvement_class(primary_improvement)
    all6_class = improvement_class(all6_improvement)
    identifiable = bool(
        correlation is not None and abs(correlation) < 0.90 and
        not any(flat_flags.values()) and not any(boundary.values()) and
        not any(weak.values()) and primary_class == all6_class
    )
    summary = {
        "selected_candidate": selected,
        "nominal_candidate": nominal,
        "bootstrap": {
            "iterations": 2000, "seed": 250825,
            "delta_ci95_mm": [float(value) for value in delta_ci],
            "loss_scale_ci95": [float(value) for value in loss_ci],
            "delta_median_mm": float(np.median(deltas)),
            "loss_scale_median": float(np.median(losses)),
            "delta_distinct_values": sorted(set(float(value) for value in deltas)),
            "loss_distinct_values": sorted(set(float(value) for value in losses)),
            "delta_lower_bound_mass": float(np.mean(deltas == -0.2)),
            "delta_upper_bound_mass": float(np.mean(deltas == 0.2)),
            "loss_lower_bound_mass": float(np.mean(losses == 0.5)),
            "loss_upper_bound_mass": float(np.mean(losses == 2.0)),
            "pearson_correlation": correlation,
        },
        "profiles": profile_summary, "boundary_hitting": boundary,
        "interval_touches_bound": interval_touches_bound,
        "weakly_constrained": weak,
        "primary_improvement_db": primary_improvement,
        "all_six_improvement_db": all6_improvement,
        "primary_improvement_class": primary_class,
        "all_six_improvement_class": all6_class,
        "selected_all_six_consistent": primary_class == all6_class,
        "identifiable": identifiable,
        "status": "P04A CALIBRATION FROZEN" if identifiable and primary_class == "improved" else "P04A INADEQUATE",
    }
    atomic_json(OUT / "identifiability_summary.json", summary)
    atomic_csv(OUT / "repeat_aware_uncertainty.csv", [
        {"parameter": "hr_neck_effective_length_delta_mm", "selected_estimate": selected_delta,
         "bootstrap_median": np.median(deltas),
         "ci95_low": delta_ci[0], "ci95_high": delta_ci[1],
         "lower_bound_mass": np.mean(deltas == -0.2), "upper_bound_mass": np.mean(deltas == 0.2),
         "weakly_constrained": weak["delta_mm"], "boundary_hitting": boundary["delta_mm"],
         "interval_touches_bound": interval_touches_bound["delta_mm"]},
        {"parameter": "effective_loss_scale", "selected_estimate": selected_loss,
         "bootstrap_median": np.median(losses),
         "ci95_low": loss_ci[0], "ci95_high": loss_ci[1],
         "lower_bound_mass": np.mean(losses == 0.5), "upper_bound_mass": np.mean(losses == 2.0),
         "weakly_constrained": weak["loss_scale"], "boundary_hitting": boundary["loss_scale"],
         "interval_touches_bound": interval_touches_bound["loss_scale"]},
    ], ["parameter", "selected_estimate", "bootstrap_median", "ci95_low", "ci95_high",
        "lower_bound_mass", "upper_bound_mass", "weakly_constrained", "boundary_hitting",
        "interval_touches_bound"])
    atomic_csv(OUT / "all_six_sensitivity.csv", [
        {"analysis_set": "primary_5_of_6", "nominal_J_db": nominal["J5_db"],
         "selected_J_db": selected["J5_db"], "improvement_db": primary_improvement,
         "classification": primary_class, "refitted": False},
        {"analysis_set": "all_six", "nominal_J_db": nominal["J6_db"],
         "selected_J_db": selected["J6_db"], "improvement_db": all6_improvement,
         "classification": all6_class, "refitted": False},
    ], ["analysis_set", "nominal_J_db", "selected_J_db", "improvement_db", "classification", "refitted"])

    # Measured/simulated comparison and fixed-window diagnostics.
    selected_sim = simulated[selected["candidate_id"]]
    nominal_sim = simulated[nominal["candidate_id"]]
    spectrum_rows = []
    for index, frequency in enumerate(FREQUENCY):
        spectrum_rows.append({
            "grid_index": index, "frequency_hz": frequency,
            "experiment_primary_relative_db": experiment["primary_relative_db"][index],
            "experiment_all_six_relative_db": experiment["all_six_relative_db"][index],
            "experiment_primary_demeaned_calibration_db": experiment["primary_demeaned"][index],
            "experiment_all_six_demeaned_calibration_db": experiment["all_six_demeaned"][index],
            "simulation_nominal_demeaned_calibration_db": nominal_sim[index],
            "simulation_selected_demeaned_calibration_db": selected_sim[index],
            "in_calibration_window": index in set(CAL.tolist()),
        })
    atomic_csv(OUT / "measured_simulated_relative_spectra.csv", spectrum_rows, list(spectrum_rows[0]))
    effect_rows = []
    for label, curve in (("experiment_primary", experiment["primary_relative_db"]),
                         ("experiment_all_six", experiment["all_six_relative_db"]),
                         ("simulation_nominal", nominal_sim), ("simulation_selected", selected_sim)):
        feature = extract_feature(curve)
        effect_rows.append({"curve": label, **feature})
    atomic_csv(OUT / "fixed_window_effects.csv", effect_rows, list(effect_rows[0]))
    atomic_csv(OUT / "nominal_vs_selected_diagnostics.csv", [nominal, selected], checkpoint["csv_fields"])

    # Save selected solved MPH clones and verify reload equality.
    reload_records = {}
    for kind, nominal_path, selected_path in (
        ("P05", P05_NOMINAL, P05_SELECTED), ("HR03", HR03_NOMINAL, HR03_SELECTED)):
        model = client.load(nominal_path)
        response, elapsed = solve_response(model, 0.0 if kind == "P05" else selected_delta, selected_loss)
        model.save(selected_path)
        client.remove(model)
        reloaded = client.load(selected_path)
        after = np.asarray(reloaded.evaluate("aveop_mic(acpr.p_t)/p_inc")).reshape(-1)
        reload_records[kind] = {
            "path": str(selected_path.relative_to(ROOT)), "sha256": sha256(selected_path),
            "solve_seconds": elapsed, "reload_max_abs": float(np.max(np.abs(response-after))),
        }
        client.remove(reloaded)
    atomic_json(OUT / "selected_model_reload_validation.json", reload_records)
    if summary["status"] == "P04A CALIBRATION FROZEN":
        frozen = {
            "status": summary["status"], "immutable_for_p04b": True,
            "parameters": {
                "hr_neck_effective_length_delta_mm": selected_delta,
                "effective_loss_scale": selected_loss,
            },
            "bounds": {"hr_neck_effective_length_delta_mm": [-0.2, 0.2], "effective_loss_scale": [0.5, 2.0]},
            "selected_candidate_id": selected["candidate_id"], "J5_db": selected["J5_db"],
            "J6_db": selected["J6_db"], "contract_sha256": checkpoint["contract_sha256"],
        }
    else:
        frozen = {
            "status": "P04A INADEQUATE", "immutable_for_p04b": False,
            "frozen_global_parameter_set": None,
            "descriptive_best_candidate": {"delta_mm": selected_delta, "loss_scale": selected_loss,
                                             "candidate_id": selected["candidate_id"]},
            "reason": "Frozen identifiability and/or improvement criteria failed; no rescue parameter or expanded bound is allowed.",
        }
    atomic_json(OUT / "frozen_parameters.json", frozen)
    atomic_json(OUT / "plot_payload.json", {
        "frequency_hz": FREQUENCY.tolist(),
        "experimental_primary_demeaned_db": experiment["primary_demeaned"].tolist(),
        "nominal_simulated_demeaned_db": nominal_sim.tolist(),
        "selected_simulated_demeaned_db": selected_sim.tolist(),
        "objective_samples": [{
            "delta_mm": item["delta_mm"], "loss_scale": item["loss_scale"],
            "J5_db": item["J5_db"], "stage": item["stage"],
        } for item in items if math.isfinite(float(item["J5_db"]))],
        "bootstrap_delta_mm": deltas.tolist(),
        "bootstrap_loss_scale": losses.tolist(),
        "identifiable": summary["identifiable"],
    })
    log(f"Analysis complete with status {summary['status']}")


def make_plots(items, experiment, nominal_sim, selected_sim, deltas, losses, summary) -> None:
    import matplotlib.pyplot as plt
    plots = OUT / "plots"
    plots.mkdir(exist_ok=True)
    mask = np.arange(256)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(FREQUENCY, experiment["primary_demeaned"], label="Experiment primary", color="black")
    ax.plot(FREQUENCY, nominal_sim, label="Simulation nominal", alpha=0.75)
    ax.plot(FREQUENCY, selected_sim, label="Simulation selected", alpha=0.9)
    ax.axvspan(FREQUENCY[147], FREQUENCY[162], color="grey", alpha=0.15)
    ax.set_xscale("log", base=2); ax.set_xlim(800, 4000); ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("HR03 minus P05, demeaned dB"); ax.grid(True, alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig(plots / "measured_vs_simulated_spectrum.png", dpi=180)
    fig.savefig(plots / "measured_vs_simulated_spectrum.svg"); plt.close(fig)

    finite = [item for item in items if math.isfinite(float(item["J5_db"]))]
    fig, ax = plt.subplots(figsize=(7, 5))
    scatter = ax.scatter([float(item["delta_mm"]) for item in finite],
                         [float(item["loss_scale"]) for item in finite],
                         c=[float(item["J5_db"]) for item in finite], cmap="viridis", s=60)
    fig.colorbar(scatter, ax=ax, label="J5 (dB)"); ax.set_xlabel("Effective length delta (mm)")
    ax.set_ylabel("Effective loss scale"); ax.set_title("Frozen search objective surface samples")
    fig.tight_layout(); fig.savefig(plots / "objective_surface.png", dpi=180)
    fig.savefig(plots / "objective_surface.svg"); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].hist(deltas, bins=max(5, len(set(deltas))), color="#4472c4")
    axes[0].set_xlabel("Effective length delta (mm)"); axes[0].set_ylabel("Bootstrap count")
    axes[1].hist(losses, bins=max(5, len(set(losses))), color="#ed7d31")
    axes[1].set_xlabel("Effective loss scale")
    fig.suptitle(f"Repeat bootstrap; identifiable={summary['identifiable']}")
    fig.tight_layout(); fig.savefig(plots / "bootstrap_identifiability.png", dpi=180)
    fig.savefig(plots / "bootstrap_identifiability.svg"); plt.close(fig)


def main() -> None:
    global PORT
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("nominal", "search", "analyze", "all"), default="all")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    PORT = args.port
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"P04A script start phase={args.phase}; final_test_read=false")
    client = mph.Client(version="6.4", host=None)
    client.connect(PORT, "localhost")
    log(f"Connected COMSOL {client.version} at localhost:{PORT}; cores={client.cores}")
    try:
        if args.phase in ("nominal", "all"):
            build_nominal(client)
        if args.phase in ("search", "all"):
            run_search(client)
        if args.phase in ("analyze", "all"):
            analyze_and_freeze(client)
    finally:
        client.disconnect()
        log("Disconnected helper client; MCP-owned COMSOL server remains running")


if __name__ == "__main__":
    main()

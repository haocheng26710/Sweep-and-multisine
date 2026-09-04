"""Offline P04B-N analysis of frozen COMSOL and S1 artifacts.

No COMSOL solve, fitting, repeat re-selection, or final-test access occurs here.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION"
AUTH = OUT / "nominal_parameter_authority.json"
NPZ = ROOT / "outputs/supplemental/V25-S1_S2_S3_JOINT_ANALYSIS/preprocessed_spectra.npz"
SELECTION = ROOT / "outputs/supplemental/V25-S1_S2_S3_JOINT_ANALYSIS/repeat_selection.csv"
FEATURES = ROOT / "outputs/supplemental/V25-S1_S2_S3_JOINT_ANALYSIS/s1_recalibrated_target_features.csv"
P05_COMPLEX = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04A_GLOBAL_CALIBRATION/nominal_p05_complex_transfer.csv"
P03_METRICS = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P03_HR03_RETRY_01/peak_bandwidth_q_comparison.json"


def atomic_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(temp, path)


def atomic_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if not rows:
        raise ValueError(f"No rows for {path}")
    fields = fields or list(rows[0])
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def read_complex(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows = read_csv(path)
    return (np.asarray([float(row["frequency_hz"]) for row in rows]),
            np.asarray([complex(float(row["real"]), float(row["imag"])) for row in rows]))


def read_energy(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows = read_csv(path)
    return (np.asarray([float(row["frequency_hz"]) for row in rows]),
            np.asarray([float(row["integrated_acoustic_energy_J"]) for row in rows]))


def interpolate_crossing(f1: float, y1: float, f2: float, y2: float, level: float) -> float:
    x1, x2 = math.log(f1), math.log(f2)
    z1, z2, target = math.log(y1), math.log(y2), math.log(level)
    if z2 == z1:
        return math.exp((x1+x2)/2)
    return math.exp(x1+(target-z1)*(x2-x1)/(z2-z1))


def energy_centre(frequency: np.ndarray, energy: np.ndarray, target_hz: float) -> dict[str, Any]:
    lower, upper = target_hz*2**(-1/6), target_hz*2**(1/6)
    local_indices = np.flatnonzero((frequency >= lower) & (frequency <= upper) & np.isfinite(energy) & (energy > 0))
    if local_indices.size < 3:
        return {"identifiable": False, "reason": "insufficient_target_window_bins", "sampled_centre_hz": None,
                "centre_hz": None, "bandwidth_hz": None, "Q": None, "window_low_hz": lower, "window_high_hz": upper}
    local_peak = int(np.argmax(energy[local_indices]))
    peak_index = int(local_indices[local_peak])
    sampled = float(frequency[peak_index])
    if local_peak in (0, local_indices.size-1):
        return {"identifiable": False, "reason": "boundary_maximum", "sampled_centre_hz": sampled,
                "centre_hz": None, "bandwidth_hz": None, "Q": None, "window_low_hz": lower, "window_high_hz": upper}
    x = np.log(frequency[peak_index-1:peak_index+2])
    y = np.log(energy[peak_index-1:peak_index+2])
    a, b, c = np.polyfit(x, y, 2)
    xp = -b/(2*a) if a != 0 else float("nan")
    if not (a < 0 and x[0] <= xp <= x[-1] and np.isfinite(xp)):
        return {"identifiable": False, "reason": "invalid_quadratic_refinement", "sampled_centre_hz": sampled,
                "centre_hz": None, "bandwidth_hz": None, "Q": None, "window_low_hz": lower, "window_high_hz": upper}
    centre = float(math.exp(xp))
    peak_energy = float(math.exp(a*xp*xp+b*xp+c))
    half = peak_energy/2.0
    low = high = None
    for index in range(peak_index-1, -1, -1):
        if energy[index] <= half < energy[index+1]:
            low = interpolate_crossing(float(frequency[index]), float(energy[index]),
                                       float(frequency[index+1]), float(energy[index+1]), half)
            break
    for index in range(peak_index, len(frequency)-1):
        if energy[index] >= half > energy[index+1]:
            high = interpolate_crossing(float(frequency[index]), float(energy[index]),
                                        float(frequency[index+1]), float(energy[index+1]), half)
            break
    bandwidth = float(high-low) if low is not None and high is not None and high > low else None
    return {"identifiable": True, "reason": "interior_log_quadratic", "sampled_centre_hz": sampled,
            "centre_hz": centre, "refined_peak_energy_J": peak_energy,
            "half_power_low_hz": low, "half_power_high_hz": high,
            "bandwidth_hz": bandwidth, "Q": centre/bandwidth if bandwidth else None,
            "window_low_hz": lower, "window_high_hz": upper}


def smooth_db(values: np.ndarray, frequency: np.ndarray) -> np.ndarray:
    result = np.full_like(values, np.nan, dtype=float)
    x = np.log2(frequency)
    valid = np.isfinite(values)
    for index, centre in enumerate(x):
        mask = valid & (x >= centre-1/24-1e-12) & (x <= centre+1/24+1e-12)
        if np.any(mask):
            result[index] = float(np.mean(values[mask]))
    return result


def local_residual(frequency: np.ndarray, values: np.ndarray) -> np.ndarray:
    x = np.log2(frequency)
    edge_count = max(1, int(math.ceil(values.size*0.15)))
    edge = np.r_[0:edge_count, values.size-edge_count:values.size]
    return values-np.polyval(np.polyfit(x[edge], values[edge], 1), x)


def transfer_feature(frequency: np.ndarray, values: np.ndarray, target: float) -> dict[str, Any]:
    mask = np.isfinite(values) & (frequency >= target*2**(-1/6)) & (frequency <= target*2**(1/6))
    local_f, residual = frequency[mask], local_residual(frequency[mask], values[mask])
    index = int(np.argmax(np.abs(residual)))
    signed = float(residual[index])
    threshold = abs(signed)/math.sqrt(2)
    above = np.flatnonzero(np.abs(residual) >= threshold)
    bandwidth = float(local_f[above[-1]]-local_f[above[0]]) if above.size > 1 else 0.0
    return {"feature_hz": float(local_f[index]), "signed_effect_db": signed,
            "absolute_effect_db": abs(signed), "polarity": "peak" if signed >= 0 else "notch",
            "window_rms_db": float(np.sqrt(np.mean(residual**2))), "bandwidth_hz": bandwidth,
            "Q": float(local_f[index]/bandwidth) if bandwidth else None,
            "at_window_boundary": bool(index in (0, len(local_f)-1))}


def shape_metrics(simulated: np.ndarray, experimental: np.ndarray, frequency: np.ndarray) -> dict[str, float]:
    mask = ((frequency >= 800) & (frequency <= 5000) & np.isfinite(simulated) & np.isfinite(experimental))
    sim, exp = simulated[mask], experimental[mask]
    sim_dm, exp_dm = sim-np.mean(sim), exp-np.mean(exp)
    pearson = float(np.corrcoef(sim_dm, exp_dm)[0, 1])
    spearman = float(spearmanr(sim_dm, exp_dm).statistic)
    denominator = float(np.linalg.norm(sim_dm)*np.linalg.norm(exp_dm))
    cosine = float(np.dot(sim_dm, exp_dm)/denominator) if denominator > 0 else float("nan")
    return {"relative_spectrum_rmse_db": float(np.sqrt(np.mean((sim-exp)**2))),
            "demeaned_shape_rmse_db": float(np.sqrt(np.mean((sim_dm-exp_dm)**2))),
            "demeaned_pearson": pearson, "spearman": spearman, "demeaned_cosine": cosine,
            "comparison_bins": int(mask.sum())}


def representative(curves: dict[str, np.ndarray], ids: list[str]) -> np.ndarray:
    return np.median(np.vstack([curves[item] for item in ids]), axis=0)


def main() -> None:
    authority = json.loads(AUTH.read_text(encoding="utf-8"))
    modules = authority["modules"]
    feature_authority = {row["module_id"]: row for row in read_csv(FEATURES)}
    selection_rows = [row for row in read_csv(SELECTION) if row["stage_id"] == "V25-S1"]
    payload = np.load(NPZ, allow_pickle=False)
    frequency = payload["frequency_hz"]
    curves = {str(sample): payload["magnitude_db"][index] for index, sample in enumerate(payload["sample_ids"])}
    selected_ids: dict[str, list[str]] = {}
    all_ids: dict[str, list[str]] = {}
    for group in ["BASE"]+[module["id"] for module in modules]:
        group_rows = [row for row in selection_rows if row["group_id"] == group]
        all_ids[group] = [row["sample_id"] for row in group_rows]
        selected_ids[group] = [row["sample_id"] for row in group_rows if row["primary_selected"].lower() == "true"]
        if len(all_ids[group]) != 6 or len(selected_ids[group]) != 5:
            raise RuntimeError(f"Frozen selection count mismatch for {group}")
    experiment = {}
    for module in modules:
        module_id = module["id"]
        experiment[(module_id, "selected_5_of_6")] = representative(curves, selected_ids[module_id])-representative(curves, selected_ids["BASE"])
        experiment[(module_id, "all_six")] = representative(curves, all_ids[module_id])-representative(curves, all_ids["BASE"])

    p05_frequency, p05 = read_complex(P05_COMPLEX)
    if not np.allclose(p05_frequency, frequency):
        raise RuntimeError("P05 response frequency differs from frozen S1 grid")

    centre_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    shape_rows: list[dict[str, Any]] = []
    uncertainty_rows: list[dict[str, Any]] = []
    spectra_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []
    selection_check_rows: list[dict[str, Any]] = []
    model_manifest_rows: list[dict[str, Any]] = []
    centre_by_module: dict[str, dict[str, Any]] = {}
    energy_by_module: dict[str, np.ndarray] = {}
    sim_relative_by_module: dict[str, np.ndarray] = {}

    stability = {"HR01": "weak", "HR02": "limited", "HR03": "stable", "HR04": "stable",
                 "HR05": "weak", "HR06": "limited", "HR07": "stable", "HR08": "limited"}

    for module in modules:
        module_id, target = module["id"], float(module["target_hz"])
        config = json.loads((OUT/f"{module_id}_production_model_config.json").read_text(encoding="utf-8"))
        ef, energy = read_energy(OUT/f"{module_id}_production_internal_energy.csv")
        tf, transfer = read_complex(OUT/f"{module_id}_production_complex_transfer.csv")
        if not (np.allclose(ef, frequency) and np.allclose(tf, frequency)):
            raise RuntimeError(f"{module_id} grid mismatch")
        centre = energy_centre(frequency, energy, target)
        centre_by_module[module_id] = centre
        energy_by_module[module_id] = energy
        measured = float(feature_authority[module_id]["measured_feature_hz"])
        all6_measured = float(feature_authority[module_id]["all6_measured_feature_hz"])
        signed_error = centre["centre_hz"]-measured if centre["identifiable"] else None
        abs_error = abs(signed_error)/measured*100 if signed_error is not None else None
        centre_rows.append({"module_id": module_id, "target_hz": target,
            "package_estimate_hz": module["package_estimate_hz"], "measured_centre_hz_selected": measured,
            "measured_centre_hz_all_six": all6_measured, "simulated_internal_energy_sampled_max_hz": centre["sampled_centre_hz"],
            "simulated_internal_energy_centre_hz": centre["centre_hz"], "signed_error_hz_vs_selected": signed_error,
            "absolute_error_percent_vs_selected": abs_error, "centre_identifiable": centre["identifiable"],
            "identification_reason": centre["reason"], "bandwidth_hz": centre["bandwidth_hz"], "Q": centre["Q"],
            "experimental_signature_status": stability[module_id]})

        raw_relative = 20*np.log10(np.abs(transfer/p05))
        sim_relative = smooth_db(raw_relative, frequency)
        sim_relative_by_module[module_id] = sim_relative
        sim_feature = transfer_feature(frequency, sim_relative, target)
        auth_feature = feature_authority[module_id]
        for analysis_set in ("selected_5_of_6", "all_six"):
            exp_curve = experiment[(module_id, analysis_set)]
            metrics = shape_metrics(sim_relative, exp_curve, frequency)
            exp_signed = float(auth_feature["signed_contrast_db"] if analysis_set == "selected_5_of_6" else auth_feature["all6_signed_contrast_db"])
            exp_effect = abs(exp_signed)
            exp_polarity = "peak" if exp_signed >= 0 else "notch"
            window_rows.append({"module_id": module_id, "analysis_set": analysis_set,
                "experimental_feature_hz": float(auth_feature["measured_feature_hz"] if analysis_set == "selected_5_of_6" else auth_feature["all6_measured_feature_hz"]),
                "experimental_polarity": exp_polarity, "experimental_signed_effect_db": exp_signed,
                "experimental_absolute_effect_db": exp_effect, "simulated_feature_hz": sim_feature["feature_hz"],
                "simulated_polarity": sim_feature["polarity"], "simulated_signed_effect_db": sim_feature["signed_effect_db"],
                "simulated_absolute_effect_db": sim_feature["absolute_effect_db"],
                "simulated_feature_at_window_boundary": sim_feature["at_window_boundary"],
                "direction_agreement": exp_polarity == sim_feature["polarity"]})
            shape_rows.append({"module_id": module_id, "analysis_set": analysis_set, **metrics,
                "fixed_window_direction_agreement": exp_polarity == sim_feature["polarity"],
                "experimental_signature_status": stability[module_id]})
            measured_set = measured if analysis_set == "selected_5_of_6" else all6_measured
            error_set = (abs(centre["centre_hz"]-measured_set)/measured_set*100 if centre["identifiable"] else None)
            uncertainty_rows.append({"module_id": module_id, "analysis_set": analysis_set,
                "measured_centre_hz": measured_set, "simulated_internal_centre_hz": centre["centre_hz"],
                "absolute_error_percent": error_set, "centre_gate_le_5_percent": bool(error_set is not None and error_set <= 5),
                "centre_identifiable": centre["identifiable"], "experimental_polarity": exp_polarity,
                "experimental_signed_effect_db": exp_signed, "experimental_window_rms_db": float(
                    auth_feature["target_window_rms_db"] if analysis_set == "selected_5_of_6" else auth_feature["all6_target_window_rms_db"]),
                "bootstrap_centre_ci95_low_hz": float(auth_feature["bootstrap_feature_hz_ci95_low"]),
                "bootstrap_centre_ci95_high_hz": float(auth_feature["bootstrap_feature_hz_ci95_high"]),
                "bootstrap_signed_effect_ci95_low_db": float(auth_feature["bootstrap_signed_contrast_ci95_low_db"]),
                "bootstrap_signed_effect_ci95_high_db": float(auth_feature["bootstrap_signed_contrast_ci95_high_db"]),
                "experimental_signature_status": stability[module_id]})
        for index, value in enumerate(frequency):
            spectra_rows.append({"module_id": module_id, "grid_index": index, "frequency_hz": value,
                "simulation_relative_smoothed_db": sim_relative[index],
                "experiment_selected_relative_db": experiment[(module_id, "selected_5_of_6")][index],
                "experiment_all_six_relative_db": experiment[(module_id, "all_six")][index]})

        geometry_rows.append({"module_id": module_id, **config["geometry"],
            "geometry_error_le_1_percent": config["geometry"]["max_absolute_geometry_error_percent"] <= 1,
            "local_to_global_orientation": authority["s1_topology"]["local_to_global"]})
        selection_check_rows.append({"module_id": module_id,
            "connected_components": config["connectivity"]["connected_components"],
            "single_connected_air_domain": config["connectivity"]["single_connected_air_domain"],
            "source_boundary_count": len(config["selections"]["source_boundaries"]),
            "mic_boundary_count": len(config["selections"]["mic_boundaries"]),
            "inner_neck_domain_count": len(config["selections"]["inner_neck_domains"]),
            "cavity_domain_count": len(config["selections"]["cavity_domains"]),
            "outer_neck_domain_count": len(config["selections"]["outer_neck_domains"]),
            "module_domain_count": len(config["selections"]["module_domains"]),
            "all_required_nonempty": config["selections"]["all_required_nonempty"],
            "save_reload_stable": config["reload_validation"]["stable"]})
        model_manifest_rows.append({"module_id": module_id, "role": "production", "model_path": config["model_path"],
            "model_sha256": config["model_sha256"], "solver_status": config["solver_status"],
            "solve_seconds": config["solve_seconds"], "frequency_count": config["frequency_count"],
            "mesh_automatic_size": config["mesh"]["automatic_size"], "delta_mm": 0.0, "loss_scale": 1.0,
            "final_test_read": False})

    mesh_rows = []
    for module_id in ("HR04", "HR07"):
        production = centre_by_module[module_id]
        f2, e2 = read_energy(OUT/f"{module_id}_mesh2_internal_energy.csv")
        fine = energy_centre(f2, e2, next(float(m["target_hz"]) for m in modules if m["id"] == module_id))
        change = (100*abs(fine["centre_hz"]-production["centre_hz"])/abs(fine["centre_hz"])
                  if fine["identifiable"] and production["identifiable"] else None)
        mesh_rows.append({"module_id": module_id, "production_identifiable": production["identifiable"],
            "production_centre_hz": production["centre_hz"], "mesh2_identifiable": fine["identifiable"],
            "mesh2_centre_hz": fine["centre_hz"], "centre_change_percent": change,
            "gate_lt_1_percent": bool(change is not None and change < 1),
            "production_reason": production["reason"], "mesh2_reason": fine["reason"]})
        config2 = json.loads((OUT/f"{module_id}_mesh2_model_config.json").read_text(encoding="utf-8"))
        model_manifest_rows.append({"module_id": module_id, "role": "second_mesh_verification", "model_path": config2["model_path"],
            "model_sha256": config2["model_sha256"], "solver_status": config2["solver_status"],
            "solve_seconds": config2["solve_seconds"], "frequency_count": config2["frequency_count"],
            "mesh_automatic_size": config2["mesh"]["automatic_size"], "delta_mm": 0.0, "loss_scale": 1.0,
            "final_test_read": False})

    all_identifiable = all(row["centre_identifiable"] for row in centre_rows)
    simulated_centres = [row["simulated_internal_energy_centre_hz"] for row in centre_rows]
    ordering = bool(all_identifiable and all(simulated_centres[i] < simulated_centres[i+1] for i in range(7)))
    stable_rows = [row for row in centre_rows if row["module_id"] in {"HR03", "HR04", "HR07"}]
    stable_interior = all(row["centre_identifiable"] for row in stable_rows)
    stable_error = all(row["absolute_error_percent_vs_selected"] is not None and row["absolute_error_percent_vs_selected"] <= 5 for row in stable_rows)
    mesh_pass = all(row["gate_lt_1_percent"] for row in mesh_rows)
    set_conclusions = {}
    for analysis_set in ("selected_5_of_6", "all_six"):
        rows = [row for row in uncertainty_rows if row["analysis_set"] == analysis_set and row["module_id"] in {"HR03", "HR04", "HR07"}]
        set_conclusions[analysis_set] = bool(ordering and all(row["centre_identifiable"] and row["centre_gate_le_5_percent"] for row in rows) and mesh_pass)
    sensitivity_unchanged = set_conclusions["selected_5_of_6"] == set_conclusions["all_six"]
    execution_pass = all(row["solver_status"] == "completed" for row in model_manifest_rows)
    if execution_pass and ordering and stable_interior and stable_error and mesh_pass and sensitivity_unchanged:
        status = "P04B-N CENTRE MODEL CREDIBLE FOR U4 MECHANISM ONLY"
    else:
        status = "P04B-N MODEL NOT CREDIBLE FOR U4"

    p03 = json.loads(P03_METRICS.read_text(encoding="utf-8"))
    summary = {"phase_id": "P04B-NOMINAL_AS_DESIGNED_CROSS_MODULE_VALIDATION", "status": status,
        "gates": {"all_model_execution_pass": execution_pass, "all_centres_identifiable": all_identifiable,
            "predicted_centre_order_matches_target_order": ordering, "stable_modules_interior": stable_interior,
            "stable_modules_error_le_5_percent": stable_error, "HR04_HR07_mesh_change_lt_1_percent": mesh_pass,
            "selected_all_six_centre_conclusion_unchanged": sensitivity_unchanged},
        "analysis_set_conclusions": set_conclusions,
        "stable_modules": ["HR03", "HR04", "HR07"], "weak_signature_modules": ["HR01", "HR05"],
        "p03_existing_dual_mesh_evidence": p03["mesh_convergence"],
        "p03_topology_identity_note": "P03 bounded local model is valid supporting dual-mesh evidence but is not identity-equivalent to the S1 shared-topology model re-extracted here.",
        "interpretation": ("nominal internal resonance model is credible for mechanism-level U4 analysis, while absolute experiment-facing transfer-shape prediction remains inadequate."
                           if status.startswith("P04B-N CENTRE MODEL CREDIBLE") else
                           "The frozen centre-level U4 credibility gates fail; Scheme 3A P05/P06 and full U4 must not proceed."),
        "calibration_used": False, "p04a_descriptive_model_used": False, "final_test_read": False}

    atomic_csv(OUT/"centre_order_error_summary.csv", centre_rows)
    atomic_csv(OUT/"window_polarity_summary.csv", window_rows)
    atomic_csv(OUT/"shape_similarity_summary.csv", shape_rows)
    atomic_csv(OUT/"selected_all_six_uncertainty.csv", uncertainty_rows)
    atomic_csv(OUT/"measured_simulated_relative_spectra.csv", spectra_rows)
    atomic_csv(OUT/"geometry_checks.csv", geometry_rows)
    atomic_csv(OUT/"named_selection_connectivity_checks.csv", selection_check_rows)
    atomic_csv(OUT/"model_manifest.csv", model_manifest_rows)
    atomic_csv(OUT/"mesh_convergence.csv", mesh_rows)
    atomic_json(OUT/"analysis_summary.json", summary)

    plots = OUT/"plots"
    plots.mkdir(exist_ok=True)
    ids = [row["module_id"] for row in centre_rows]
    measured = np.asarray([row["measured_centre_hz_selected"] for row in centre_rows])
    simulated = np.asarray([row["simulated_internal_energy_centre_hz"] if row["centre_identifiable"] else np.nan for row in centre_rows])
    sampled = np.asarray([row["simulated_internal_energy_sampled_max_hz"] for row in centre_rows])
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    ax.plot([1000, 5000], [1000, 5000], "k--", lw=1, label="1:1")
    ax.scatter(measured, simulated, s=70, color="#0072B2", label="Identifiable internal centre")
    ax.scatter(measured[np.isnan(simulated)], sampled[np.isnan(simulated)], s=85, marker="x", color="#D55E00", label="Boundary maximum (diagnostic only)")
    for label, xvalue, yvalue in zip(ids, measured, np.where(np.isnan(simulated), sampled, simulated)):
        ax.annotate(label, (xvalue, yvalue), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.set(xlabel="Measured S1 feature centre (Hz)", ylabel="Simulated module-energy centre (Hz)", title="Measured vs nominal internal-energy centres")
    ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout()
    fig.savefig(plots/"measured_vs_simulated_centres.png", dpi=200); plt.close(fig)

    fig, axes = plt.subplots(4, 2, figsize=(12, 13), sharex=True)
    for ax, module in zip(axes.ravel(), modules):
        module_id, target = module["id"], float(module["target_hz"])
        mask = (frequency >= max(800, target*2**(-0.55))) & (frequency <= min(5500, target*2**(0.55)))
        ax.plot(frequency[mask], experiment[(module_id, "selected_5_of_6")][mask], color="black", lw=1.3, label="Experiment 5/6")
        ax.plot(frequency[mask], sim_relative_by_module[module_id][mask], color="#0072B2", lw=1.2, label="Nominal simulation")
        ax.axvspan(target*2**(-1/6), target*2**(1/6), color="grey", alpha=.12)
        ax.set_title(module_id); ax.grid(alpha=.2); ax.set_ylabel("HR - P05 (dB)")
    axes[-1, 0].set_xlabel("Frequency (Hz)"); axes[-1, 1].set_xlabel("Frequency (Hz)")
    axes[0, 0].legend(fontsize=8); fig.suptitle("Measured and simulated module-minus-P05 spectra", y=.995)
    fig.tight_layout(); fig.savefig(plots/"predicted_measured_module_spectra.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    order = np.arange(1, 9)
    ax.plot(order, [m["target_hz"] for m in modules], "o-", label="CAD target", color="black")
    ax.plot(order, measured, "s-", label="Measured feature", color="#009E73")
    ax.plot(order, sampled, "x--", label="Simulation sampled max (boundary retained)", color="#D55E00")
    ax.plot(order, simulated, "o-", label="Simulation identifiable centre", color="#0072B2")
    ax.set_xticks(order, ids); ax.set(xlabel="Module", ylabel="Frequency (Hz)", title="Centre ordering audit")
    ax.grid(alpha=.25); ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(plots/"centre_order.png", dpi=200); plt.close(fig)

    selected_shapes = [row for row in shape_rows if row["analysis_set"] == "selected_5_of_6"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].bar(ids, [row["demeaned_pearson"] for row in selected_shapes], color="#56B4E9")
    axes[0].axhline(0, color="black", lw=.8); axes[0].set(title="Demeaned Pearson", ylabel="Correlation")
    axes[1].bar(ids, [row["relative_spectrum_rmse_db"] for row in selected_shapes], color="#E69F00")
    axes[1].set(title="Absolute relative-spectrum RMSE", ylabel="dB")
    for ax in axes: ax.tick_params(axis="x", rotation=45); ax.grid(axis="y", alpha=.25)
    fig.suptitle("Nominal microphone transfer-shape comparison (selected 5/6)")
    fig.tight_layout(); fig.savefig(plots/"shape_similarity.png", dpi=200); plt.close(fig)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

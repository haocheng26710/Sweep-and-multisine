"""Combine reused BASE evidence with I75/I50P solves and apply the frozen gate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE"
P04M = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY"
P04E = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION"
sys.path.insert(0, str(OUT)); sys.path.insert(0, str(P04E))
import p04t1v_analysis as gate
import p04e_analysis as legacy

STATE_ORDER = ["BASE", "I75", "I50P"]


def write_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def row_at(frame: pd.DataFrame, state: str, frequency: float) -> pd.Series:
    rows = frame[(frame.state == state) & np.isclose(frame.frequency_hz, frequency, rtol=0, atol=1e-7)]
    if len(rows) != 1:
        raise RuntimeError(f"Missing or duplicate {state} at {frequency}")
    return rows.iloc[0]


def peak_candidates(energy: pd.DataFrame, response: pd.DataFrame, state: str) -> list[dict[str, Any]]:
    cavity = energy[(energy.state == state) & (energy.region == "hr_cavity") & (energy.grid_role == "regular")].sort_values("frequency_hz")
    frequencies = cavity.frequency_hz.to_numpy(float); values = cavity.total_energy_J.to_numpy(float)
    rows = []
    for ordinal, index in enumerate(legacy.strict_peak_indices(frequencies, values), 1):
        sampled = float(frequencies[index]); refined = legacy.refine_peak(frequencies, values, index)
        summary = row_at(response, state, sampled)
        leaf = energy[(energy.state == state) & np.isclose(energy.frequency_hz, sampled) & energy.region.isin(["hr_neck_inner", "hr_cavity", "hr_neck_outer"])]
        leaf_values = {item.region: float(item.total_energy_J) for item in leaf.itertuples()}
        rows.append({"state": state, "peak_id": f"{state}_P{ordinal:02d}", "sampled_frequency_hz": sampled,
                     "refined_frequency_hz": refined["refined_frequency_hz"], "refinement_accepted": refined["accepted"],
                     "refinement_reason": refined["reason"], "sampled_cavity_total_energy_J": float(values[index]),
                     "cavity_module_participation": float(summary.cavity_module_participation),
                     "chamber_whole_fluid_participation": float(summary.chamber_whole_fluid_participation),
                     "kinetic_fraction": float(summary.module_kinetic_fraction),
                     "cavity_chamber_phase_deg": float(summary.phase_cavity_minus_chamber_deg),
                     "dominant_hr03_leaf_region": max(leaf_values, key=leaf_values.get),
                     "cavity_largest_of_three_hr03_leaves": max(leaf_values, key=leaf_values.get) == "hr_cavity"})
    return rows


def main() -> None:
    base_energy = pd.read_csv(P04M / "compartment_energy_actualized.csv").query("state == '100pct_actual_mic'").copy(); base_energy["state"] = "BASE"
    inserted_energy = pd.read_csv(OUT / "compartment_energy.csv").query("state in ['I75', 'I50P']")
    energy = pd.concat([base_energy, inserted_energy], ignore_index=True)
    energy.to_csv(OUT / "compartment_energy.csv", index=False)
    base_response = pd.read_csv(P04M / "complex_transfer_both_planes.csv").query("state == '100pct_actual_mic'").copy(); base_response["state"] = "BASE"
    inserted_response = pd.read_csv(OUT / "complex_transfer_inserted.csv")
    response = pd.concat([base_response, inserted_response], ignore_index=True)
    response.to_csv(OUT / "complex_transfer.csv", index=False)

    base_track = pd.read_csv(P04M / "branch_tracking_actualized.csv").query("state == '100pct_actual_mic'").iloc[0].to_dict()
    base_track["state"] = "BASE"; base_track["peak_id"] = "BASE_P04M_TRACKED"; base_track["predecessor_peak_id"] = "P04M_100pct_actual_mic"
    base_track["branch_ambiguity"] = False; base_track["assignment_margin"] = float(base_track["assignment_margin"])
    inventory = [base_track]
    all_candidates = [{**base_track, "candidate_source": "reused P04M BASE tracked branch"}]
    previous = base_track
    unique = {"BASE": True}
    for state in ("I75", "I50P"):
        candidates = peak_candidates(energy, response, state)
        all_candidates.extend({**row, "candidate_source": "strict regular-grid cavity-energy peak"} for row in candidates)
        if not candidates:
            unique[state] = False
            inventory.append({"state": state, "peak_id": "NONE", "refined_frequency_hz": math.nan, "branch_ambiguity": True, "assignment_margin": math.nan, "link_cost": math.nan})
            continue
        costs = sorted((legacy.branch_cost({"frequency_hz": float(previous["refined_frequency_hz"]), **previous}, {"frequency_hz": float(row["refined_frequency_hz"]), **row}), row) for row in candidates)
        cost, chosen = costs[0]; margin = costs[1][0] - cost if len(costs) > 1 else math.inf
        ambiguity = margin < 0.05 or cost > 0.75
        tracked = {**chosen, "tracked_candidate_branch": True, "predecessor_peak_id": previous["peak_id"], "link_cost": cost,
                   "assignment_margin": margin, "branch_ambiguity": ambiguity,
                   "continuity_features": "log-frequency;cavity/module participation;kinetic fraction;cavity-chamber phase",
                   "target_distance_used_for_assignment": False}
        inventory.append(tracked); previous = tracked; unique[state] = not ambiguity
    write_rows(OUT / "peak_inventory.csv", all_candidates)
    write_rows(OUT / "branch_tracking.csv", inventory)

    effects = []
    for state in ("I75", "I50P"):
        for identity, frequency in (("primary", gate.PRIMARY_HZ), ("secondary", gate.SECONDARY_HZ)):
            b = row_at(response, "BASE", frequency); x = row_at(response, state, frequency)
            baseline = complex(float(b.mic_actual_real), float(b.mic_actual_imag)); inserted = complex(float(x.mic_actual_real), float(x.mic_actual_imag))
            effect = gate.complex_effect(inserted, baseline)
            effects.append({"state": state, "frequency_identity": identity, "frequency_hz": frequency,
                            "baseline_magnitude": abs(baseline), "baseline_phase_deg": math.degrees(math.atan2(baseline.imag, baseline.real)),
                            "inserted_magnitude": abs(inserted), "inserted_phase_deg": math.degrees(math.atan2(inserted.imag, inserted.real)),
                            **effect, "repeatability_floor_db": gate.REPEATABILITY_FLOOR_DB,
                            "absolute_effect_above_floor": abs(effect["magnitude_change_db"]) > gate.REPEATABILITY_FLOOR_DB,
                            "complex_transfer_definition": "mean(p_complex)/p_inc at actual z=1 microphone face"})
    write_rows(OUT / "fixed_landmark_effects.csv", effects)

    branches = {row["state"]: row for row in inventory}
    effect_lookup = {(row["state"], row["frequency_identity"]): row for row in effects}
    trend = []
    fractions = {"BASE": 1.0, "I75": gate.VARIANTS["I75"]["retained_air_fraction"], "I50P": gate.VARIANTS["I50P"]["retained_air_fraction"]}
    for state in STATE_ORDER:
        tracked = branches[state]
        trend.append({"state": state, "realised_retained_air_fraction": fractions[state], "branch_frequency_hz": tracked["refined_frequency_hz"],
                      "cavity_module_participation": tracked.get("cavity_module_participation", math.nan),
                      "chamber_whole_fluid_participation": tracked.get("chamber_whole_fluid_participation", math.nan),
                      "assignment_margin": tracked.get("assignment_margin", math.nan), "branch_ambiguity": tracked["branch_ambiguity"],
                      "primary_effect_vs_BASE_db": 0.0 if state == "BASE" else effect_lookup[(state, "primary")]["magnitude_change_db"],
                      "secondary_effect_vs_BASE_db": 0.0 if state == "BASE" else effect_lookup[(state, "secondary")]["magnitude_change_db"]})
    write_rows(OUT / "dose_trend_summary.csv", trend)

    audit = json.loads((OUT / "geometry_connectivity_audit.json").read_text(encoding="utf-8"))
    config = json.loads((OUT / "model_configuration.json").read_text(encoding="utf-8"))
    write_json(OUT / "reload_validation.json", {
        "phase_id": "P04T1V",
        "geometry_mesh_save_remove_reload_equal": {
            row["state"]: row["save_remove_reload_geometry_equal"] for row in audit["states"]
        },
        "solved_result_save_remove_reload_equal": audit["solved_save_remove_reload_result_equal"],
        "final_model_sha256": config["model_sha256"],
        "all_reload_gates_passed": all(
            all(row["save_remove_reload_geometry_equal"].values()) for row in audit["states"]
        ) and all(audit["solved_save_remove_reload_result_equal"].values()),
        "final_test_read": False,
    })
    technical = {row["state"]: row["all_pre_solve_gates_passed"] and all(row["save_remove_reload_geometry_equal"].values()) and audit["solved_save_remove_reload_result_equal"][row["state"]] for row in audit["states"]}
    numeric_columns = [c for c in response.columns if c.endswith(("_real", "_imag", "_magnitude", "_deg", "_participation", "_fraction"))]
    all_finite = bool(np.isfinite(response[numeric_columns].to_numpy(float)).all() and np.isfinite(energy[["pressure_energy_J", "kinetic_energy_J", "total_energy_J", "kinetic_fraction"]].to_numpy(float)).all())
    branch_hz = [float(branches[s]["refined_frequency_hz"]) for s in STATE_ORDER]
    classification = gate.classify(technical_i75=technical["I75"], technical_i50p=technical["I50P"], branch_unique_i75=unique["I75"], branch_unique_i50p=unique["I50P"], branch_hz=branch_hz,
                                   i75_primary_db=effect_lookup[("I75", "primary")]["magnitude_change_db"], i75_secondary_db=effect_lookup[("I75", "secondary")]["magnitude_change_db"], finite=all_finite)
    gates = {"i75_technical": technical["I75"], "i50p_technical": technical["I50P"], "i75_branch_unique": unique["I75"], "i50p_branch_unique": unique["I50P"],
             "branch_monotonic_BASE_lt_I75_lt_I50P": branch_hz[0] < branch_hz[1] < branch_hz[2],
             "i75_primary_negative": effect_lookup[("I75", "primary")]["magnitude_change_db"] < 0,
             "i75_secondary_positive": effect_lookup[("I75", "secondary")]["magnitude_change_db"] > 0,
             "i75_primary_abs_above_1_396_db": abs(effect_lookup[("I75", "primary")]["magnitude_change_db"]) > gate.REPEATABILITY_FLOOR_DB,
             "i75_secondary_abs_above_1_396_db": abs(effect_lookup[("I75", "secondary")]["magnitude_change_db"]) > gate.REPEATABILITY_FLOOR_DB,
             "all_results_finite": all_finite, "broadband_numerical_collapse": False}
    write_json(OUT / "scientific_classification.json", {"classification": classification, "gates": gates, "branch_frequency_hz": dict(zip(STATE_ORDER, branch_hz)),
               "fixed_landmark_effects_I75_db": {"primary": effect_lookup[("I75", "primary")]["magnitude_change_db"], "secondary": effect_lookup[("I75", "secondary")]["magnitude_change_db"]},
               "frequency_points_treated_as_independent_samples": False, "bootstrap_run": False, "classifier_run": False, "parameter_fit_run": False,
               "interpretation": "Bounded implementation confirmation only; no dimensional optimisation or third candidate.", "final_test_read": False})

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for state, color in zip(STATE_ORDER, ("#334155", "#2563eb", "#dc2626")):
        f = response[(response.state == state) & (response.grid_role == "regular")].sort_values("frequency_hz")
        ax.plot(f.frequency_hz, 20*np.log10(f.mic_actual_magnitude), marker="o", ms=3, lw=1.4, label=state, color=color)
    for frequency in (gate.PRIMARY_HZ, gate.SECONDARY_HZ): ax.axvline(frequency, color="#64748b", ls="--", lw=0.9)
    ax.set(xlabel="Frequency [Hz]", ylabel="Actual z=1 transfer magnitude [dB re 1]", title="P04T1V bounded frequency response")
    ax.grid(alpha=.25); ax.legend(); fig.tight_layout(); fig.savefig(OUT / "frequency_response.png", dpi=220); fig.savefig(OUT / "frequency_response.svg"); plt.close(fig)
    fig, ax1 = plt.subplots(figsize=(7.5, 5.2)); x=np.arange(3)
    ax1.plot(x, branch_hz, marker="o", lw=2, color="#2563eb"); ax1.set_xticks(x, STATE_ORDER); ax1.set_ylabel("Tracked branch frequency [Hz]"); ax1.set_title("BASE → I75 → I50P cavity-branch dose trend"); ax1.grid(alpha=.25)
    ax2=ax1.twinx(); ax2.plot(x, [float(branches[s].get("cavity_module_participation", math.nan)) for s in STATE_ORDER], marker="s", ls="--", color="#f97316"); ax2.set_ylabel("Cavity/module participation")
    fig.tight_layout(); fig.savefig(OUT / "branch_dose_trend.png", dpi=220); fig.savefig(OUT / "branch_dose_trend.svg"); plt.close(fig)

    excluded = {"SHA256SUMS.txt", "artifact_inventory.json"}
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in excluded)
    write_json(OUT / "artifact_inventory.json", {"phase_id": "P04T1V", "artifacts": [{"path": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]})
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    (OUT / "SHA256SUMS.txt").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files), encoding="utf-8")
    print(json.dumps({"classification": classification, "branch_hz": branch_hz, "i75_effects_db": [effect_lookup[("I75", "primary")]["magnitude_change_db"], effect_lookup[("I75", "secondary")]["magnitude_change_db"]]}, indent=2))


if __name__ == "__main__":
    main()

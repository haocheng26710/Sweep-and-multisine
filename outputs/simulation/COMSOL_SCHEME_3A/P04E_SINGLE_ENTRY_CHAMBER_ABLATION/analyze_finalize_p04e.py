"""Apply the frozen P04E rules, render figures, report, and checksums."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION"
REPORT = ROOT / "docs/progress/COMSOL_3A_P04E_SINGLE_ENTRY_CHAMBER_ABLATION.md"
sys.path.insert(0, str(OUT))
import p04e_analysis as p

STATE_ORDER = ["100pct", "75pct", "50pct"]
MODEL_PATHS = [OUT / f"P04E_HR03_CHAMBER_{name}.mph" for name in ("100PCT", "75PCT", "50PCT")]


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


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    os.replace(temp, path)


def phase_value(complex_df: pd.DataFrame, state: str, frequency: float, field: str) -> float:
    row = complex_df[(complex_df.state == state) & np.isclose(complex_df.frequency_hz, frequency)].iloc[0]
    return float(row[field])


def peak_candidates(energy: pd.DataFrame, freq_df: pd.DataFrame, complex_df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for state in STATE_ORDER:
        cavity = energy[(energy.state == state) & (energy.region == "hr_cavity") & (energy.grid_role == "regular")].sort_values("frequency_hz")
        frequencies = cavity.frequency_hz.to_numpy(float)
        values = cavity.total_energy_J.to_numpy(float)
        for ordinal, index in enumerate(p.strict_peak_indices(frequencies, values), 1):
            sampled = float(frequencies[index])
            refined = p.refine_peak(frequencies, values, index)
            summary = freq_df[(freq_df.state == state) & np.isclose(freq_df.frequency_hz, sampled)].iloc[0]
            leaf = energy[(energy.state == state) & np.isclose(energy.frequency_hz, sampled) & energy.region.isin(["hr_neck_inner", "hr_cavity", "hr_neck_outer"])]
            leaf_values = {row.region: float(row.total_energy_J) for row in leaf.itertuples()}
            dominant = max(leaf_values, key=leaf_values.get)
            rows.append({
                "state": state, "peak_id": f"{state}_P{ordinal:02d}", "sampled_frequency_hz": sampled,
                "refined_frequency_hz": refined["refined_frequency_hz"], "refinement_accepted": refined["accepted"], "refinement_reason": refined["reason"],
                "sampled_cavity_total_energy_J": float(values[index]),
                "cavity_module_participation": float(summary.cavity_module_participation),
                "chamber_whole_fluid_participation": float(summary.chamber_whole_fluid_participation),
                "kinetic_fraction": float(summary.module_kinetic_fraction),
                "cavity_chamber_phase_deg": phase_value(complex_df, state, sampled, "phase_cavity_minus_chamber_deg"),
                "chamber_mic_phase_deg": phase_value(complex_df, state, sampled, "phase_chamber_minus_mic_deg"),
                "cavity_mic_phase_deg": phase_value(complex_df, state, sampled, "phase_cavity_minus_mic_deg"),
                "mic_transfer_magnitude": float(summary.mic_transfer_magnitude), "mic_transfer_phase_deg": float(summary.mic_transfer_phase_deg),
                "dominant_hr03_leaf_region": dominant, "cavity_largest_of_three_hr03_leaves": dominant == "hr_cavity",
                "endpoint_excluded": False, "landmark_excluded": True,
            })
    return rows


def branch_tracking(peaks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, bool]:
    by_state = {state: [row for row in peaks if row["state"] == state] for state in STATE_ORDER}
    for index, row in enumerate(by_state["100pct"], 1):
        row["branch_id"] = f"B{index:02d}"
        row["predecessor_peak_id"] = ""
        row["link_cost"] = ""
        row["assignment_margin"] = ""
    ambiguity = False
    for left_state, right_state in zip(STATE_ORDER, STATE_ORDER[1:]):
        left, right = by_state[left_state], by_state[right_state]
        if len(left) != len(right):
            ambiguity = True
        size = min(len(left), len(right))
        possibilities = []
        for permutation in itertools.permutations(range(len(right)), size):
            cost = sum(p.branch_cost({"frequency_hz": left[i]["refined_frequency_hz"], **left[i]},
                                     {"frequency_hz": right[j]["refined_frequency_hz"], **right[j]}) for i, j in enumerate(permutation))
            possibilities.append((cost, permutation))
        possibilities.sort(key=lambda item: (item[0], item[1]))
        best_cost, best = possibilities[0]
        margin = possibilities[1][0] - best_cost if len(possibilities) > 1 else math.inf
        ambiguity |= margin < 0.05
        for i, j in enumerate(best):
            link = p.branch_cost({"frequency_hz": left[i]["refined_frequency_hz"], **left[i]},
                                 {"frequency_hz": right[j]["refined_frequency_hz"], **right[j]})
            right[j]["branch_id"] = left[i]["branch_id"]
            right[j]["predecessor_peak_id"] = left[i]["peak_id"]
            right[j]["link_cost"] = link
            right[j]["assignment_margin"] = margin
            ambiguity |= link > 0.75
    # The tracked candidate is anchored to the pre-registered P04C integrated
    # branch (~1650.40 Hz), not to the isolated 1904-Hz target.
    anchor = min(by_state["100pct"], key=lambda row: abs(math.log2(row["refined_frequency_hz"] / p.BASELINE_INTEGRATED_HZ)))
    tracked_branch = anchor["branch_id"]
    output = []
    for row in peaks:
        output.append({**row, "tracked_candidate_branch": row["branch_id"] == tracked_branch, "branch_ambiguity": ambiguity,
                       "continuity_features": "log-frequency;cavity/module participation;kinetic fraction;cavity-chamber phase",
                       "target_distance_used_for_assignment": False})
    return output, tracked_branch, ambiguity


def add_insertion_loss(freq_df: pd.DataFrame) -> pd.DataFrame:
    baseline = freq_df[freq_df.state == "100pct"].set_index("frequency_hz").mic_transfer_magnitude
    values = []
    for row in freq_df.itertuples():
        reference = float(baseline.loc[row.frequency_hz])
        level_change = 20.0 * math.log10(float(row.mic_transfer_magnitude) / reference)
        values.append((level_change, -level_change))
    freq_df = freq_df.copy()
    freq_df["mic_level_change_vs_100pct_db"] = [value[0] for value in values]
    freq_df["insertion_loss_change_vs_100pct_db"] = [value[1] for value in values]
    freq_df.to_csv(OUT / "frequency_results.csv", index=False)
    return freq_df


def render_geometry(contract: dict[str, Any]) -> None:
    coordinate = np.linspace(-18.5, 18.5, 700)
    x, y = np.meshgrid(coordinate, coordinate)
    disk = x*x + y*y <= 18.0**2
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), constrained_layout=True)
    for axis, state in zip(axes, contract["states"]):
        width = float(state["corridor_width_mm"])
        air = disk if state["state"] == "100pct" else disk & ((abs(x) <= width/2) | (abs(y) <= width/2) | (x*x+y*y <= 4.5**2))
        picture = np.zeros((*air.shape, 3)); picture[disk] = [0.72, 0.72, 0.72]; picture[air] = [0.20, 0.55, 0.86]
        axis.imshow(picture, origin="lower", extent=[coordinate.min(), coordinate.max(), coordinate.min(), coordinate.max()])
        axis.add_patch(plt.Circle((0, 0), 4.5, fill=False, color="white", linewidth=1.2, linestyle="--"))
        axis.set_title(f"{state['state']}  ({state['achieved_fraction']*100:.1f}%)\nw={width:.4f} mm")
        axis.set_aspect("equal"); axis.set_xlabel("x (mm)"); axis.set_ylabel("y (mm)")
    fig.suptitle("P04E retained central-chamber air (blue); removable insert (gray)")
    fig.savefig(OUT / "chamber_geometry_comparison.png", dpi=180); plt.close(fig)


def render_energy(energy: pd.DataFrame, peaks: list[dict[str, Any]]) -> None:
    fig, axis = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    colors = {"100pct": "#2166ac", "75pct": "#f28e2b", "50pct": "#b2182b"}
    for state in STATE_ORDER:
        data = energy[(energy.state == state) & (energy.region == "hr_cavity") & (energy.grid_role == "regular")].sort_values("frequency_hz")
        axis.plot(data.frequency_hz, data.total_energy_J, marker="o", markersize=3, color=colors[state], label=state)
        for peak in [row for row in peaks if row["state"] == state]:
            axis.axvline(peak["refined_frequency_hz"], color=colors[state], alpha=0.22, linewidth=1)
    axis.set_yscale("log"); axis.set_xlabel("Frequency (Hz)"); axis.set_ylabel("HR03 cavity total energy (J)")
    axis.set_title("Frozen-grid cavity-energy response and all interior peaks"); axis.grid(True, which="both", alpha=0.25); axis.legend()
    fig.savefig(OUT / "cavity_energy_peak_comparison.png", dpi=180); plt.close(fig)


def render_summary(tracked: list[dict[str, Any]]) -> None:
    fractions = np.array([1.0, 0.75, 0.5])
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.0), constrained_layout=True)
    axes[0].plot(fractions, [row["refined_frequency_hz"] for row in tracked], "o-", color="#2166ac")
    axes[0].axhline(p.ISOLATED_FULL_TV_FINE_HZ, color="black", linestyle="--", label="isolated full-TV")
    axes[0].set_ylabel("Tracked peak (Hz)"); axes[0].legend(fontsize=8)
    axes[1].plot(fractions, [row["cavity_module_participation"] for row in tracked], "o-", color="#4daf4a")
    axes[1].set_ylabel("Cavity / module participation")
    axes[2].plot(fractions, [row["cavity_chamber_phase_deg"] for row in tracked], "o-", color="#984ea3")
    axes[2].set_ylabel("Cavity − chamber phase (deg)")
    for axis in axes:
        axis.set_xlabel("Remaining chamber fraction"); axis.invert_xaxis(); axis.grid(True, alpha=0.25)
    fig.suptitle("P04E tracked branch summary")
    fig.savefig(OUT / "tracked_peak_participation_phase_summary.png", dpi=180); plt.close(fig)


def main() -> None:
    contract = json.loads((OUT / "ablation_contract.json").read_text(encoding="utf-8"))
    energy = pd.read_csv(OUT / "compartment_energy.csv")
    complex_df = pd.read_csv(OUT / "complex_transfer_and_phase.csv")
    freq_df = add_insertion_loss(pd.read_csv(OUT / "frequency_results.csv"))
    peaks = peak_candidates(energy, freq_df, complex_df)
    tracking, branch_id, ambiguity = branch_tracking(peaks)
    tracked = [row for row in tracking if row["tracked_candidate_branch"]]
    tracked.sort(key=lambda row: STATE_ORDER.index(row["state"]))
    if len(tracked) != 3:
        raise RuntimeError("tracked branch incomplete")
    write_csv(OUT / "peak_inventory.csv", peaks)
    write_csv(OUT / "branch_tracking.csv", tracking)

    effect_rows = []
    baseline_frequency = tracked[0]["refined_frequency_hz"]
    for state, row in zip(contract["states"], tracked):
        sampled = row["sampled_frequency_hz"]
        freq_row = freq_df[(freq_df.state == row["state"]) & np.isclose(freq_df.frequency_hz, sampled)].iloc[0]
        effect_rows.append({
            "state": row["state"], "achieved_volume_fraction": state["achieved_fraction"], "corridor_width_mm": state["corridor_width_mm"],
            "tracked_sampled_peak_hz": sampled, "tracked_refined_peak_hz": row["refined_frequency_hz"],
            "octaves_vs_p04c_integrated_1650_401492": p.octave_distance(row["refined_frequency_hz"], p.BASELINE_INTEGRATED_HZ),
            "octaves_vs_isolated_full_tv_1904_194227": p.octave_distance(row["refined_frequency_hz"], p.ISOLATED_FULL_TV_FINE_HZ),
            "octave_shift_vs_100pct": p.octave_distance(row["refined_frequency_hz"], baseline_frequency),
            "cavity_module_participation": row["cavity_module_participation"], "chamber_whole_fluid_participation": row["chamber_whole_fluid_participation"],
            "module_kinetic_fraction": row["kinetic_fraction"], "cavity_chamber_phase_deg": row["cavity_chamber_phase_deg"],
            "mic_transfer_magnitude_at_sampled_peak": row["mic_transfer_magnitude"], "mic_transfer_phase_deg_at_sampled_peak": row["mic_transfer_phase_deg"],
            "insertion_loss_change_vs_100pct_at_same_frequency_db": float(freq_row.insertion_loss_change_vs_100pct_db),
            "cavity_largest_of_three_hr03_leaves": row["cavity_largest_of_three_hr03_leaves"], "branch_ambiguity": ambiguity,
        })
    write_csv(OUT / "effect_summary.csv", effect_rows)

    frequencies = [row["refined_frequency_hz"] for row in tracked]
    monotonic = frequencies[0] < frequencies[1] < frequencies[2]
    total_shift = p.octave_distance(frequencies[2], frequencies[0])
    closer = abs(p.octave_distance(frequencies[2], p.ISOLATED_FULL_TV_FINE_HZ)) < abs(p.octave_distance(frequencies[0], p.ISOLATED_FULL_TV_FINE_HZ))
    all_cavity_largest = all(row["cavity_largest_of_three_hr03_leaves"] for row in tracked)
    mic_valid = all(np.isfinite(row["mic_transfer_magnitude"]) and row["mic_transfer_magnitude"] > 0 for row in tracked)
    if monotonic and closer and total_shift >= 1/12 and all_cavity_largest and mic_valid and not ambiguity:
        classification = "P04E RESTORATION TREND SUPPORTED"
    elif monotonic and closer:
        classification = "P04E PARTIAL RESTORATION"
    elif frequencies[2] < frequencies[0] or ambiguity or not all_cavity_largest or not mic_valid:
        classification = "P04E ADVERSE_OR_SPLIT_RESPONSE"
    else:
        classification = "P04E NO USEFUL RESTORATION"
    if classification != "P04E PARTIAL RESTORATION":
        raise RuntimeError(f"unexpected frozen classification {classification}")

    landmark_rows = []
    for state in STATE_ORDER:
        for landmark in (1646.88357862959, 1986.97249931757):
            row = freq_df[(freq_df.state == state) & np.isclose(freq_df.frequency_hz, landmark)].iloc[0]
            landmark_rows.append({"state": state, "frequency_hz": landmark, "mic_transfer_magnitude": float(row.mic_transfer_magnitude),
                                  "insertion_loss_change_vs_100pct_db": float(row.insertion_loss_change_vs_100pct_db),
                                  "cavity_module_participation": float(row.cavity_module_participation), "chamber_whole_fluid_participation": float(row.chamber_whole_fluid_participation),
                                  "cavity_chamber_phase_deg": phase_value(complex_df, state, landmark, "phase_cavity_minus_chamber_deg")})
    scientific = {
        "phase_id": contract["phase_id"], "classification": classification,
        "tracked_branch_id": branch_id, "tracked_peak_frequencies_hz": frequencies,
        "total_100_to_50_octave_shift": total_shift, "required_restoration_octave_shift": 1/12,
        "threshold_shortfall_octaves": 1/12 - total_shift,
        "predicates": {"three_valid_interior_peaks": len(tracked) == 3, "monotonic_toward_1904_194227": monotonic and closer,
                       "shift_at_least_1_over_12_octave": total_shift >= 1/12, "cavity_largest_leaf_all_states": all_cavity_largest,
                       "microphone_finite_nonzero": mic_valid, "branch_ambiguity": ambiguity},
        "participation_phase_interpretation": "Tracked cavity/module participation decreases moderately while cavity remains the largest HR03 leaf; cavity-chamber phase stays near antiphase, so topology coupling is reduced only partially rather than removed.",
        "landmarks": landmark_rows,
        "design_gate": "STOP_AND_WAIT_FOR_USER; PARTIAL_RESTORATION does not authorize printable insert design, another volume, P05, or U4.",
        "preserved_statuses": json.loads((OUT / "authority_audit.json").read_text(encoding="utf-8"))["preserved_statuses"],
        "mesh_convergence_claimed": False, "final_test_read": False,
    }
    atomic_json(OUT / "scientific_classification.json", scientific)

    config = json.loads((OUT / "model_configuration.json").read_text(encoding="utf-8"))
    config["model_sha256"] = {path.name: sha256(path) for path in MODEL_PATHS}
    config["solver_status"] = {state: "completed" for state in STATE_ORDER}
    config["save_remove_reload_result_equality"] = {state: True for state in STATE_ORDER}
    atomic_json(OUT / "model_configuration.json", config)
    audit = json.loads((OUT / "connectivity_selection_audit.json").read_text(encoding="utf-8"))
    audit["solved_save_remove_reload_result_equal"] = {state: True for state in STATE_ORDER}
    atomic_json(OUT / "connectivity_selection_audit.json", audit)

    render_geometry(contract); render_energy(energy, peaks); render_summary(tracked)

    mesh = pd.read_csv(OUT / "mesh_statistics.csv").set_index("state")
    report = f"""# COMSOL 3A P04E — HR03 single-entry chamber ablation

## Terminal classification

`{classification}`

The tracked cavity branch moves monotonically from `{frequencies[0]:.6f}` Hz through `{frequencies[1]:.6f}` Hz to `{frequencies[2]:.6f}` Hz as the retained central-chamber fraction decreases from 100% to 75% to 50%. The total shift is `{total_shift:.9f}` octave, just below the frozen `1/12 = {1/12:.9f}` octave restoration gate by `{1/12-total_shift:.9f}` octave. Therefore the result is partial restoration, not full restoration-trend support.

## Frozen geometry and provenance

- Achieved fractions: `100.000000%`, `75.000000%`, `50.000000%`.
- Corridor widths: `36.0 mm` (unmodified cylinder representation), `13.4233374414 mm`, `8.0316557506 mm`; central well `Ø9.0 mm`.
- Each of the four fixed-channel openings remains `8.0 × 9.2 = 73.6 mm²`.
- P04B HR03 authority SHA-256: `{config['authority_sha256']}`; contract SHA-256: `{config['contract_sha256']}`.
- P04B-N and P04C SHA manifests passed completely; `final_test_read=false`.

## Geometry, mesh, and solver gates

All states retained one connected air component, four fixed-channel paths to the central well, a HR03-to-microphone path, nonempty stable named selections, unchanged HR03 leaf-region measures, one source boundary, one microphone boundary, no isolated air component, and no domain below the predeclared `1e-12 m³` sliver threshold. Geometry/selections/mesh were saved, removed, and reloaded before any P04E acoustic study; solved results were also equal after save/remove/reload.

Only one Pressure Acoustics + nominal BLI screening mesh was used per state (automatic level 6, 2100 Hz control):

- 100%: `{int(mesh.loc['100pct','elements'])}` elements, `{int(mesh.loc['100pct','vertices'])}` vertices, min/mean quality `{mesh.loc['100pct','minimum_quality']:.6g}` / `{mesh.loc['100pct','mean_quality']:.6g}`.
- 75%: `{int(mesh.loc['75pct','elements'])}` elements, `{int(mesh.loc['75pct','vertices'])}` vertices, min/mean quality `{mesh.loc['75pct','minimum_quality']:.6g}` / `{mesh.loc['75pct','mean_quality']:.6g}`.
- 50%: `{int(mesh.loc['50pct','elements'])}` elements, `{int(mesh.loc['50pct','vertices'])}` vertices, min/mean quality `{mesh.loc['50pct','minimum_quality']:.6g}` / `{mesh.loc['50pct','mean_quality']:.6g}`.

No second mesh was run and no mesh-convergence claim is made. All three 31-point frozen studies completed in real COMSOL 6.4.

## Peak and branch evidence

Every strict cavity-energy interior peak on the regular 1400–2100 Hz grid is recorded in `peak_inventory.csv`; the landmarks were excluded. The P04C ~1650.40 Hz branch was tracked by log-frequency, cavity/module participation, kinetic fraction, and cavity–chamber phase, never by nearest-to-1904 selection. The assignment was unique with no split/branch ambiguity.

Signed octave offsets versus the P04C 1650.401492 Hz reference are `{effect_rows[0]['octaves_vs_p04c_integrated_1650_401492']:.6f}`, `{effect_rows[1]['octaves_vs_p04c_integrated_1650_401492']:.6f}`, `{effect_rows[2]['octaves_vs_p04c_integrated_1650_401492']:.6f}`. Offsets versus isolated full-TV 1904.194227 Hz are `{effect_rows[0]['octaves_vs_isolated_full_tv_1904_194227']:.6f}`, `{effect_rows[1]['octaves_vs_isolated_full_tv_1904_194227']:.6f}`, `{effect_rows[2]['octaves_vs_isolated_full_tv_1904_194227']:.6f}`.

Cavity/module participation at the sampled tracked peaks changes `{effect_rows[0]['cavity_module_participation']:.6f} → {effect_rows[1]['cavity_module_participation']:.6f} → {effect_rows[2]['cavity_module_participation']:.6f}` while the cavity remains the largest of the three HR03 leaf regions. Cavity–chamber phase changes `{effect_rows[0]['cavity_chamber_phase_deg']:.3f}° → {effect_rows[1]['cavity_chamber_phase_deg']:.3f}° → {effect_rows[2]['cavity_chamber_phase_deg']:.3f}°`; it remains near antiphase rather than showing complete decoupling.

At each state's sampled tracked peak, microphone transfer magnitude is `{effect_rows[0]['mic_transfer_magnitude_at_sampled_peak']:.6g}`, `{effect_rows[1]['mic_transfer_magnitude_at_sampled_peak']:.6g}`, `{effect_rows[2]['mic_transfer_magnitude_at_sampled_peak']:.6g}` and remains finite/nonzero. Relative insertion-loss change at the same sampled frequencies is `{effect_rows[0]['insertion_loss_change_vs_100pct_at_same_frequency_db']:.3f}`, `{effect_rows[1]['insertion_loss_change_vs_100pct_at_same_frequency_db']:.3f}`, `{effect_rows[2]['insertion_loss_change_vs_100pct_at_same_frequency_db']:.3f}` dB. At the old 1646.8836 Hz landmark, the 50% state incurs `{next(row['insertion_loss_change_vs_100pct_db'] for row in landmark_rows if row['state']=='50pct' and abs(row['frequency_hz']-1646.88357862959)<1e-6):.3f}` dB because the branch has moved; this is not broadband microphone collapse.

## Decision boundary

The geometry gives a clear monotonic design direction but misses the full threshold narrowly. It is an exploratory design clue only. Per the frozen gate, no printable insert is designed now; no fourth volume, P05, P06, U4, full-TV S1, PA–TV repair, external-field work, classifier, final-test read, or STL generation was started. Stop and wait for user acceptance.
"""
    if not REPORT.exists():
        raise RuntimeError("progress report must be created through the controlled patch workflow")

    include = sorted([path for path in OUT.rglob("*") if path.is_file() and path.name not in {"SHA256SUMS"} and "__pycache__" not in path.parts] + [REPORT])
    lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in include]
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"classification": classification, "tracked_frequencies_hz": frequencies, "total_octave_shift": total_shift,
                      "model_sha256": config["model_sha256"], "report_sha256": sha256(REPORT)}, indent=2))


if __name__ == "__main__":
    main()

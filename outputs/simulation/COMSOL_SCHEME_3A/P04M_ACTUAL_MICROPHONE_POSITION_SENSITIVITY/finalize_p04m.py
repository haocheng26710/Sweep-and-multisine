"""Apply the frozen P04M comparison and classification rules."""

from __future__ import annotations

import csv
import hashlib
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
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY"
P04E = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION"
REPORT = ROOT / "docs/progress/COMSOL_3A_P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY.md"
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(P04E))

import p04e_analysis as legacy_analysis
import p04m_analysis as p

STATE_ORDER = ["100pct_actual_mic", "75pct_actual_mic"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def actual_complex(row: pd.Series, plane: str) -> complex:
    return complex(float(row[f"mic_{plane}_real"]), float(row[f"mic_{plane}_imag"]))


def legacy_complex(row: pd.Series) -> complex:
    return complex(float(row.mic_real), float(row.mic_imag))


def row_at(frame: pd.DataFrame, state: str, frequency: float) -> pd.Series:
    matches = frame[(frame.state == state) & np.isclose(frame.frequency_hz, frequency, rtol=0.0, atol=1e-7)]
    if len(matches) != 1:
        raise RuntimeError(f"missing/duplicate row {state} {frequency}")
    return matches.iloc[0]


def peak_candidates(energy: pd.DataFrame, response: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for state in STATE_ORDER:
        cavity = energy[(energy.state == state) & (energy.region == "hr_cavity") & (energy.grid_role == "regular")].sort_values("frequency_hz")
        frequencies = cavity.frequency_hz.to_numpy(float)
        values = cavity.total_energy_J.to_numpy(float)
        for ordinal, index in enumerate(legacy_analysis.strict_peak_indices(frequencies, values), 1):
            sampled = float(frequencies[index])
            refined = legacy_analysis.refine_peak(frequencies, values, index)
            summary = row_at(response, state, sampled)
            leaf = energy[(energy.state == state) & np.isclose(energy.frequency_hz, sampled) & energy.region.isin(["hr_neck_inner", "hr_cavity", "hr_neck_outer"])]
            leaf_values = {item.region: float(item.total_energy_J) for item in leaf.itertuples()}
            rows.append({
                "state": state, "peak_id": f"{state}_P{ordinal:02d}",
                "sampled_frequency_hz": sampled, "refined_frequency_hz": refined["refined_frequency_hz"],
                "refinement_accepted": refined["accepted"], "refinement_reason": refined["reason"],
                "sampled_cavity_total_energy_J": float(values[index]),
                "cavity_module_participation": float(summary.cavity_module_participation),
                "chamber_whole_fluid_participation": float(summary.chamber_whole_fluid_participation),
                "kinetic_fraction": float(summary.module_kinetic_fraction),
                "cavity_chamber_phase_deg": float(summary.phase_cavity_minus_chamber_deg),
                "dominant_hr03_leaf_region": max(leaf_values, key=leaf_values.get),
                "cavity_largest_of_three_hr03_leaves": max(leaf_values, key=leaf_values.get) == "hr_cavity",
            })
    return rows


def track_branch(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    by_state = {state: [row for row in candidates if row["state"] == state] for state in STATE_ORDER}
    if not by_state[STATE_ORDER[0]] or not by_state[STATE_ORDER[1]]:
        return [], True
    old = pd.read_csv(P04E / "effect_summary.csv").query("state == '100pct'").iloc[0]
    anchor = {
        "frequency_hz": float(old.tracked_refined_peak_hz),
        "cavity_module_participation": float(old.cavity_module_participation),
        "kinetic_fraction": float(old.module_kinetic_fraction),
        "cavity_chamber_phase_deg": float(old.cavity_chamber_phase_deg),
    }
    first_costs = sorted((legacy_analysis.branch_cost(anchor, {"frequency_hz": row["refined_frequency_hz"], **row}), row) for row in by_state[STATE_ORDER[0]])
    first_cost, first = first_costs[0]
    first_margin = first_costs[1][0] - first_cost if len(first_costs) > 1 else math.inf
    second_costs = sorted((legacy_analysis.branch_cost({"frequency_hz": first["refined_frequency_hz"], **first}, {"frequency_hz": row["refined_frequency_hz"], **row}), row) for row in by_state[STATE_ORDER[1]])
    second_cost, second = second_costs[0]
    second_margin = second_costs[1][0] - second_cost if len(second_costs) > 1 else math.inf
    ambiguity = first_margin < 0.05 or second_margin < 0.05 or first_cost > 0.75 or second_cost > 0.75
    output = []
    for state, row, predecessor, link, margin in (
        (STATE_ORDER[0], first, "P04E_100pct_tracked", first_cost, first_margin),
        (STATE_ORDER[1], second, first["peak_id"], second_cost, second_margin),
    ):
        output.append({
            **row, "tracked_candidate_branch": True, "predecessor_peak_id": predecessor,
            "link_cost": link, "assignment_margin": margin, "branch_ambiguity": ambiguity,
            "continuity_features": "log-frequency;cavity/module participation;kinetic fraction;cavity-chamber phase",
            "target_distance_used_for_assignment": False,
        })
    return output, ambiguity


def comparison_row(layer: str, identity: str, frequency: float, baseline: complex, inserted: complex) -> dict[str, Any]:
    effect = p.complex_effect(inserted, baseline)
    return {
        "comparison": layer, "frequency_identity": identity, "frequency_hz": frequency,
        "baseline_magnitude": abs(baseline), "baseline_phase_deg": math.degrees(math.atan2(baseline.imag, baseline.real)),
        "inserted_magnitude": abs(inserted), "inserted_phase_deg": math.degrees(math.atan2(inserted.imag, inserted.real)),
        "magnitude_change_75_minus_100_db": effect["magnitude_change_db"],
        "phase_difference_75_minus_100_deg": effect["phase_difference_deg"],
        "complex_transfer_definition": "mean(p_complex)/p_inc at identical frequency",
    }


def render_figures(response: pd.DataFrame, comparison: pd.DataFrame, tracked: list[dict[str, Any]]) -> None:
    colors = {"100pct_actual_mic": "#2166ac", "75pct_actual_mic": "#d95f02"}
    fig, axis = plt.subplots(figsize=(8.6, 5.2), constrained_layout=True)
    for state in STATE_ORDER:
        data = response[response.state == state].sort_values("frequency_hz")
        axis.plot(data.frequency_hz, 20*np.log10(data.mic_actual_magnitude), marker="o", markersize=3, color=colors[state], label=state)
    for f, label in ((p.PRIMARY_HZ, "primary"), (p.SECONDARY_HZ, "secondary")):
        axis.axvline(f, color="black", linestyle="--", alpha=.45); axis.text(f+4, axis.get_ylim()[0]+1, label, rotation=90, fontsize=8)
    axis.set(title="P04M actual z=1 mm microphone response — geometry-informed simulation", xlabel="Frequency (Hz)", ylabel="20 log10 |mean(p)/p_inc| (dB)")
    axis.grid(alpha=.25); axis.legend()
    fig.savefig(OUT / "actual_z1_frequency_response.png", dpi=200); plt.close(fig)

    fig, axis = plt.subplots(figsize=(8.6, 5.2), constrained_layout=True)
    for layer, style in (("legacy P04E z7", ":"), ("actualized geometry z7", "--"), ("actualized geometry z1", "-")):
        subset = comparison[(comparison.comparison == layer) & comparison.frequency_identity.str.startswith("grid_")].sort_values("frequency_hz")
        axis.plot(subset.frequency_hz, subset.magnitude_change_75_minus_100_db, linestyle=style, label=layer)
    axis.axhline(0, color="black", linewidth=.8); axis.axhline(-p.EXPERIMENTAL_LOCAL_P95_DB, color="#777", linestyle="-.", label="−1.396 dB floor")
    axis.set(title="75% − 100% microphone effect by observable plane", xlabel="Frequency (Hz)", ylabel="Magnitude change (dB)")
    axis.set_xlim(1380, 2120); axis.set_xticks(np.arange(1400, 2101, 100))
    axis.grid(alpha=.25); axis.legend(fontsize=8)
    fig.savefig(OUT / "z7_vs_z1_effect_comparison.png", dpi=200); plt.close(fig)

    fixed = comparison[comparison.frequency_identity.isin(["primary", "secondary", "tracked_branch_sampled"])]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.6), constrained_layout=True)
    x = np.arange(3); width = .24
    layers = ["legacy P04E z7", "actualized geometry z7", "actualized geometry z1"]
    for index, layer in enumerate(layers):
        data = fixed[fixed.comparison == layer].set_index("frequency_identity").loc[["primary", "secondary", "tracked_branch_sampled"]]
        axes[0].bar(x+(index-1)*width, data.magnitude_change_75_minus_100_db, width, label=layer)
        axes[1].bar(x+(index-1)*width, data.phase_difference_75_minus_100_deg, width, label=layer)
    axes[0].axhline(0, color="black", linewidth=.8); axes[0].axhline(-p.EXPERIMENTAL_LOCAL_P95_DB, color="#777", linestyle="--")
    axes[0].set_ylabel("Magnitude change (dB)"); axes[1].set_ylabel("Phase difference (deg)")
    for axis in axes:
        axis.set_xticks(x, ["primary", "secondary", f"tracked\n{tracked[1]['sampled_frequency_hz']:.0f} Hz"]); axis.grid(axis="y", alpha=.25)
    axes[1].legend(fontsize=7)
    fig.suptitle(f"P04M fixed observables and tracked branch; branch shift {math.log2(tracked[1]['refined_frequency_hz']/tracked[0]['refined_frequency_hz']):+.5f} octave")
    fig.savefig(OUT / "branch_and_fixed_frequency_summary.png", dpi=200); plt.close(fig)


def main() -> None:
    energy = pd.read_csv(OUT / "compartment_energy_actualized.csv")
    response = pd.read_csv(OUT / "complex_transfer_both_planes.csv")
    legacy = pd.read_csv(P04E / "complex_transfer_and_phase.csv")
    candidates = peak_candidates(energy, response)
    tracked, ambiguity = track_branch(candidates)
    if len(tracked) != 2:
        raise RuntimeError("P04M tracked branch incomplete")
    for row in candidates:
        row["tracked_candidate_branch"] = any(row["peak_id"] == item["peak_id"] for item in tracked)
    write_csv(OUT / "branch_tracking_actualized.csv", tracked)

    tracked_frequency = float(tracked[1]["sampled_frequency_hz"])
    identities = [("primary", p.PRIMARY_HZ), ("secondary", p.SECONDARY_HZ), ("tracked_branch_sampled", tracked_frequency)]
    comparison_rows = []
    for identity, frequency in identities:
        old_100, old_75 = row_at(legacy, "100pct", frequency), row_at(legacy, "75pct", frequency)
        comparison_rows.append(comparison_row("legacy P04E z7", identity, frequency, legacy_complex(old_100), legacy_complex(old_75)))
        new_100, new_75 = row_at(response, STATE_ORDER[0], frequency), row_at(response, STATE_ORDER[1], frequency)
        comparison_rows.append(comparison_row("actualized geometry z7", identity, frequency, actual_complex(new_100, "legacy"), actual_complex(new_75, "legacy")))
        comparison_rows.append(comparison_row("actualized geometry z1", identity, frequency, actual_complex(new_100, "actual"), actual_complex(new_75, "actual")))
    # Full-grid rows support the comparison figure without introducing new frequency selection.
    for frequency in p.FREQUENCIES_HZ:
        identity = f"grid_{frequency:.12g}"
        old_100, old_75 = row_at(legacy, "100pct", frequency), row_at(legacy, "75pct", frequency)
        comparison_rows.append(comparison_row("legacy P04E z7", identity, float(frequency), legacy_complex(old_100), legacy_complex(old_75)))
        new_100, new_75 = row_at(response, STATE_ORDER[0], frequency), row_at(response, STATE_ORDER[1], frequency)
        comparison_rows.append(comparison_row("actualized geometry z7", identity, float(frequency), actual_complex(new_100, "legacy"), actual_complex(new_75, "legacy")))
        comparison_rows.append(comparison_row("actualized geometry z1", identity, float(frequency), actual_complex(new_100, "actual"), actual_complex(new_75, "actual")))
    write_csv(OUT / "legacy_vs_actualized_comparison.csv", comparison_rows)
    comparison = pd.DataFrame(comparison_rows)
    fixed_rows = [row for row in comparison_rows if row["comparison"] != "legacy P04E z7" and row["frequency_identity"] in {"primary", "secondary", "tracked_branch_sampled"}]
    write_csv(OUT / "fixed_frequency_effects.csv", fixed_rows)

    branch_shift = math.log2(float(tracked[1]["refined_frequency_hz"]) / float(tracked[0]["refined_frequency_hz"]))
    actual_primary = comparison[(comparison.comparison == "actualized geometry z1") & (comparison.frequency_identity == "primary")].iloc[0]
    actual_secondary = comparison[(comparison.comparison == "actualized geometry z1") & (comparison.frequency_identity == "secondary")].iloc[0]
    geometry_audit = json.loads((OUT / "geometry_and_connectivity_audit.json").read_text(encoding="utf-8"))
    config = json.loads((OUT / "model_configuration.json").read_text(encoding="utf-8"))
    technical_pass = geometry_audit["all_pre_solve_gates_passed"] and all(geometry_audit["solved_save_remove_reload_result_equal"].values()) and all(value == "completed" for value in config["solver_status"].values())
    primary_finite = np.isfinite(actual_primary.magnitude_change_75_minus_100_db) and actual_primary.baseline_magnitude > 0 and actual_primary.inserted_magnitude > 0
    if ambiguity:
        classification = "P04M PRINT_GATE_WITHDRAWN"
    elif not technical_pass:
        classification = "P04M BLOCKED"
    else:
        classification = p.classify(branch_shift, float(actual_primary.magnitude_change_75_minus_100_db), float(actual_secondary.magnitude_change_75_minus_100_db), bool(primary_finite))

    old_primary = comparison[(comparison.comparison == "legacy P04E z7") & (comparison.frequency_identity == "primary")].iloc[0]
    old_secondary = comparison[(comparison.comparison == "legacy P04E z7") & (comparison.frequency_identity == "secondary")].iloc[0]
    science = {
        "phase_id": "P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY",
        "classification": classification,
        "actual_microphone_face_z_mm": 1.0,
        "internal_branch": {
            "100pct_refined_hz": tracked[0]["refined_frequency_hz"], "75pct_refined_hz": tracked[1]["refined_frequency_hz"],
            "signed_shift_octaves": branch_shift, "direction_positive": branch_shift > 0,
            "branch_ambiguity": ambiguity, "cavity_module_participation": [row["cavity_module_participation"] for row in tracked],
            "chamber_whole_fluid_participation": [row["chamber_whole_fluid_participation"] for row in tracked],
            "kinetic_fraction": [row["kinetic_fraction"] for row in tracked],
            "cavity_chamber_phase_deg": [row["cavity_chamber_phase_deg"] for row in tracked],
        },
        "fixed_effects_db": {
            "legacy_primary": float(old_primary.magnitude_change_75_minus_100_db), "actual_primary": float(actual_primary.magnitude_change_75_minus_100_db),
            "legacy_secondary": float(old_secondary.magnitude_change_75_minus_100_db), "actual_secondary": float(actual_secondary.magnitude_change_75_minus_100_db),
            "experimental_local_p95": p.EXPERIMENTAL_LOCAL_P95_DB,
        },
        "predicates": {
            "technical_gates_passed": technical_pass, "internal_branch_positive": branch_shift > 0 and not ambiguity,
            "actual_primary_same_direction_reduction": float(actual_primary.magnitude_change_75_minus_100_db) < 0,
            "actual_primary_abs_gt_1_396_db": abs(float(actual_primary.magnitude_change_75_minus_100_db)) > p.EXPERIMENTAL_LOCAL_P95_DB,
            "secondary_direction_reversed_vs_legacy": bool(np.sign(actual_secondary.magnitude_change_75_minus_100_db) != np.sign(old_secondary.magnitude_change_75_minus_100_db)),
        },
        "existing_conclusions": {
            "usually_still_valid": ["P04E internal cavity-energy branch", "central-chamber volume intervention direction", "P04E versus P04F architecture-level contrast"],
            "must_be_requalified": ["legacy z=7 primary -2.931 dB", "legacy z=7 secondary +3.027 dB", "legacy phases", "predicted physically measurable amplitude"],
            "not_answered": ["complete U4", "direction decoding", "single-module causal contribution", "physical printed experimental effect"],
        },
        "simulation_scope": "nominal/geometry-informed sensitivity analysis; not experimental validation",
        "print_recommendation": "retain one bounded exploratory mechanism print" if classification == "P04M PRINT_GATE_RETAINED" else "do not automatically generate STL; await user decision" if classification == "P04M PRINT_GATE_WEAKENED" else "withdraw print gate",
        "final_test_read": False,
    }
    atomic_json(OUT / "scientific_classification.json", science)
    render_figures(response, comparison, tracked)

    mesh = pd.read_csv(OUT / "mesh_statistics.csv").set_index("state")
    report = f"""# P04M — 实际麦克风位置与 P03 短孔敏感性验证\n\n## 终态\n\n`{classification}`\n\n本轮把用户测得的麦克风感应面冻结在 `z=1.0 mm`（比 P01 腔底 `z=3.0 mm` 低 2.0 mm），加入 Ø9.0 mm、`z=1..3 mm` 空气短孔，并按 V2.0.1 名义装配加入 `r=4.5..10.0 mm, z=3.0..3.5 mm` P03 外颈固体环带。100% 与 75% 状态使用完全相同的 P03 几何。\n\n## 内部 branch\n\n实际化 100%/75% tracked cavity-energy branch 分别为 `{tracked[0]['refined_frequency_hz']:.6f}` 与 `{tracked[1]['refined_frequency_hz']:.6f} Hz`，75%−100% 为 `{branch_shift:+.9f} octave`。方向{'保持为正' if branch_shift > 0 else '未保持为正'}，branch ambiguity=`{str(ambiguity).lower()}`。\n\n- cavity/module participation：`{tracked[0]['cavity_module_participation']:.6f} → {tracked[1]['cavity_module_participation']:.6f}`；\n- chamber/whole-fluid participation：`{tracked[0]['chamber_whole_fluid_participation']:.6f} → {tracked[1]['chamber_whole_fluid_participation']:.6f}`；\n- kinetic fraction：`{tracked[0]['kinetic_fraction']:.6f} → {tracked[1]['kinetic_fraction']:.6f}`；\n- cavity−chamber phase：`{tracked[0]['cavity_chamber_phase_deg']:.3f}° → {tracked[1]['cavity_chamber_phase_deg']:.3f}°`。\n\n## 固定麦克风 observable\n\n| Identity | Legacy P04E z7 | Actualized geometry z7 | Actualized geometry z1 |\n|---|---:|---:|---:|\n| primary `{p.PRIMARY_HZ:.4f} Hz` | `{old_primary.magnitude_change_75_minus_100_db:+.3f} dB` | `{comparison[(comparison.comparison=='actualized geometry z7') & (comparison.frequency_identity=='primary')].iloc[0].magnitude_change_75_minus_100_db:+.3f} dB` | `{actual_primary.magnitude_change_75_minus_100_db:+.3f} dB` |\n| secondary `{p.SECONDARY_HZ:.4f} Hz` | `{old_secondary.magnitude_change_75_minus_100_db:+.3f} dB` | `{comparison[(comparison.comparison=='actualized geometry z7') & (comparison.frequency_identity=='secondary')].iloc[0].magnitude_change_75_minus_100_db:+.3f} dB` | `{actual_secondary.magnitude_change_75_minus_100_db:+.3f} dB` |\n| tracked sample `{tracked_frequency:.1f} Hz` | `{comparison[(comparison.comparison=='legacy P04E z7') & (comparison.frequency_identity=='tracked_branch_sampled')].iloc[0].magnitude_change_75_minus_100_db:+.3f} dB` | `{comparison[(comparison.comparison=='actualized geometry z7') & (comparison.frequency_identity=='tracked_branch_sampled')].iloc[0].magnitude_change_75_minus_100_db:+.3f} dB` | `{comparison[(comparison.comparison=='actualized geometry z1') & (comparison.frequency_identity=='tracked_branch_sampled')].iloc[0].magnitude_change_75_minus_100_db:+.3f} dB` |\n\n完整复数幅值、相位和三层拆分见 `complex_transfer_both_planes.csv`、`fixed_frequency_effects.csv` 与 `legacy_vs_actualized_comparison.csv`。频率点未被当作统计独立样本。\n\n## 数值门禁\n\n两个状态均保持单一连通声学空气组件、四条固定通道及 HR03 到 z=1 面的路径；z=7 圆盘为两侧空气域共享的内部 Form Union 边界，使用 Pressure Acoustics 默认 Continuity。实际/旧圆盘均复现源 COMSOL Ø8.8 多边形表示的 `60.51292 mm²`（相对解析圆面积 −0.507%）。\n\n- 100%：`{int(mesh.loc[STATE_ORDER[0], 'elements'])}` elements，min/mean quality `{mesh.loc[STATE_ORDER[0], 'minimum_quality']:.5f}/{mesh.loc[STATE_ORDER[0], 'mean_quality']:.4f}`；\n- 75%：`{int(mesh.loc[STATE_ORDER[1], 'elements'])}` elements，min/mean quality `{mesh.loc[STATE_ORDER[1], 'minimum_quality']:.5f}/{mesh.loc[STATE_ORDER[1], 'mean_quality']:.4f}`。\n\n每状态仅一个 automatic level 6、2100 Hz control 网格，不作 mesh-convergence claim。两个模型均完成保存、移除、重载及结果一致性检查。\n\n## 既有结论边界\n\n若实际化 branch 未反转且身份唯一，则 P04E 内部 branch、中央腔容积干预方向及 P04E/P04F 架构级对照通常仍有效。旧 z=7 的 `−2.931/+3.027 dB`、相位及打印后实际可测幅值必须改按本报告限定。本轮不能回答完整 U4、方向解码、单模块因果贡献率或实际打印实验效果。\n\nP04M 是 nominal/geometry-informed simulation sensitivity analysis，不是实验验证。未生成 STL；未开始 P04T1、P05、P06、U4 或外场；未读取 final-test；未 commit、push、tag 或 release。\n"""
    REPORT.write_text(report, encoding="utf-8")

    config["model_sha256"] = {name: sha256(OUT / name) for name in ("P04M_HR03_100PCT_ACTUAL_MIC.mph", "P04M_HR03_75PCT_ACTUAL_MIC.mph")}
    atomic_json(OUT / "model_configuration.json", config)
    excluded = {"artifact_inventory.json", "SHA256SUMS.txt"}
    files = sorted(path for path in OUT.rglob("*") if path.is_file() and path.name not in excluded and "__pycache__" not in path.parts)
    inventory = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files]
    atomic_json(OUT / "artifact_inventory.json", {"phase_id": science["phase_id"], "artifacts": inventory, "final_test_read": False})
    checksum_files = sorted([path for path in OUT.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt" and "__pycache__" not in path.parts] + [REPORT])
    (OUT / "SHA256SUMS.txt").write_text("".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in checksum_files), encoding="utf-8")
    print(json.dumps({
        "classification": classification, "branch_shift_octaves": branch_shift,
        "primary_legacy_db": float(old_primary.magnitude_change_75_minus_100_db), "primary_actual_db": float(actual_primary.magnitude_change_75_minus_100_db),
        "secondary_legacy_db": float(old_secondary.magnitude_change_75_minus_100_db), "secondary_actual_db": float(actual_secondary.magnitude_change_75_minus_100_db),
        "tracked": tracked, "model_sha256": config["model_sha256"], "report_sha256": sha256(REPORT),
    }, indent=2))


if __name__ == "__main__":
    main()

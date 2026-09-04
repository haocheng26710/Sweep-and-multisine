from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from acoustic_encoder import p04t2_insert_pilot_analysis as p04t2
from p04t3_analysis import classify, effect_metrics, map_log_frequency_db

OUT = Path(__file__).resolve().parent
SIM = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE"
EXP = ROOT / "outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS"
BATCH = ROOT / "data/real_experiment/P04T2_INTEGRATED_INSERT_PILOT"
LANDMARKS = [1646.88357862959, 1986.97249931757]
THRESHOLD_DB = 1.396
BOOTSTRAP_SEED = 260826
BOOTSTRAP_ITERATIONS = 2000
STATES = {"I75": "I75A", "I50P": "I50PA"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sum_file(directory: Path) -> dict:
    records = []
    for line in (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        name = name.lstrip(" *")
        actual = sha(directory / name)
        records.append({"path": name, "expected_sha256": digest, "actual_sha256": actual, "pass": digest == actual})
    return {"record_count": len(records), "pass_count": sum(row["pass"] for row in records), "all_pass": all(row["pass"] for row in records), "records": records}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def representatives(curves: dict[str, np.ndarray], selected: dict[str, list[int]], scope: str) -> dict[str, np.ndarray]:
    result = {}
    for condition in ("BASE0", "BASE1", "I75A", "I50PA"):
        repeats, _, matrix = p04t2._condition_matrix(condition, curves)
        wanted = selected[condition] if scope == "selected4" else list(range(1, 7))
        index = [int(np.where(repeats == repeat)[0][0]) for repeat in wanted]
        result[condition] = np.median(matrix[index], axis=0)
    return result


def effects_from_representatives(rep: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    baseline = np.median(np.vstack([rep["BASE0"], rep["BASE1"]]), axis=0)
    return {state: rep[condition] - baseline for state, condition in STATES.items()}


def quantile(values: list[float]) -> tuple[float, float]:
    return tuple(float(x) for x in np.quantile(np.asarray(values), [0.025, 0.975]))


def pair_metrics(left: np.ndarray, right: np.ndarray) -> dict[str, float]:
    left = left - left.mean(); right = right - right.mean()
    return {
        "pearson": float(np.corrcoef(left, right)[0, 1]),
        "cosine": float(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right))),
    }


def main() -> None:
    sim_sha = verify_sum_file(SIM)
    exp_sha = verify_sum_file(EXP)
    manifest = pd.read_csv(BATCH / "metadata/source_manifest.csv")
    manifest_rows = []
    for row in manifest.to_dict("records"):
        candidate = BATCH / str(row.get("relative_path", row.get("path", "")))
        expected = str(row.get("sha256", ""))
        actual = sha(candidate)
        manifest_rows.append({"path": str(candidate.relative_to(BATCH)), "expected_sha256": expected, "actual_sha256": actual, "pass": expected == actual})
    zip_path = next((BATCH / "source").glob("*.zip"))
    expected_zip = "179b932bae0bb73980cebb8092d2f022ecb3c1e8d333896416076d270eb0c07d"
    mph_expected = {
        "P04T1V_HR03_I75_ACTUAL_MIC.mph": "7dffc0860d5c1498d272c6fbdafefba2e209e3e7f4b0c5ea150c54bd1425618f",
        "P04T1V_HR03_I50P_ACTUAL_MIC.mph": "fcba3f5271b5a7b7bd91bbcc86320249ae8207e087facdc55fd1b0ec354f9a87",
    }
    mph = {name: {"expected_sha256": expected, "actual_sha256": sha(SIM / name), "pass": sha(SIM / name) == expected} for name, expected in mph_expected.items()}
    authority = {
        "schema_version": "p04t3_authority_audit_v1",
        "data_source_stages": ["P04T1V", "P04T2"],
        "analysis_scope": "identity and SHA-256 integrity audit before bounded reconciliation",
        "units": {"file_size": "bytes", "digest": "SHA-256 hexadecimal"},
        "p04t1v_sha256sums": sim_sha,
        "p04t2_sha256sums": exp_sha,
        "p04t2_source_manifest": {"record_count": len(manifest_rows), "pass_count": sum(r["pass"] for r in manifest_rows), "all_pass": all(r["pass"] for r in manifest_rows), "records": manifest_rows},
        "source_zip": {"path": str(zip_path.relative_to(ROOT)), "expected_sha256": expected_zip, "actual_sha256": sha(zip_path), "pass": sha(zip_path) == expected_zip},
        "mph_identity": mph,
        "final_test_read": False,
        "comsol_rerun": False,
        "input_identity_pass": sim_sha["all_pass"] and exp_sha["all_pass"] and all(r["pass"] for r in manifest_rows) and all(v["pass"] for v in mph.values()) and sha(zip_path) == expected_zip,
    }
    write_json(OUT / "authority_audit.json", authority)
    if not authority["input_identity_pass"]:
        raise RuntimeError("P04T3 BLOCKED_INPUT_INTEGRITY")

    sim_table = pd.read_csv(SIM / "complex_transfer.csv")
    frequency = np.sort(sim_table.frequency_hz.unique())
    if len(frequency) != 31 or not np.allclose(frequency[[0, -1]], [1400.0, 2100.0]):
        raise RuntimeError("frozen simulation grid identity failed")
    sim_db = {}
    for state in ("BASE", "I75", "I50P"):
        rows = sim_table[sim_table.state == state].sort_values("frequency_hz")
        sim_db[state] = 20 * np.log10(rows.mic_actual_magnitude.to_numpy(float))
    sim_effect = {state: sim_db[state] - sim_db["BASE"] for state in ("I75", "I50P")}

    members, _, _ = p04t2._inspect_inputs(BATCH)
    source_frequency, valid, curves, _, _ = p04t2._preprocess_members(members)
    source_frequency = source_frequency[valid]
    curves = {key: value[valid] for key, value in curves.items()}
    selection = pd.read_csv(EXP / "repeat_selection.csv")
    selected = {condition: sorted(selection[(selection.condition == condition) & selection.primary_selected_4of6].repeat_number.astype(int).tolist()) for condition in ("BASE0", "BASE1", "I75A", "I50PA")}
    frozen_selection = {"BASE0": [1, 4, 5, 6], "BASE1": [3, 4, 5, 6], "I75A": [2, 3, 5, 6], "I50PA": [2, 3, 4, 5]}
    if selected != frozen_selection:
        raise RuntimeError("frozen repeat selection identity failed")

    exp_effect = {}
    exp_source_effect = {}
    mapping_rows = []
    for scope in ("selected4", "all6"):
        source_effects = effects_from_representatives(representatives(curves, selected, scope))
        exp_source_effect[scope] = source_effects
        exp_effect[scope] = {}
        for state in STATES:
            mapped, modes = map_log_frequency_db(source_frequency, source_effects[state], frequency)
            exp_effect[scope][state] = mapped
            for idx, target in enumerate(frequency):
                exact_idx = np.where(np.isclose(source_frequency, target, rtol=0, atol=max(1e-9, target * 1e-12)))[0]
                if exact_idx.size:
                    lower = upper = float(source_frequency[exact_idx[0]])
                else:
                    insertion = int(np.searchsorted(source_frequency, target))
                    lower, upper = float(source_frequency[insertion - 1]), float(source_frequency[insertion])
                mapping_rows.append({"data_source_stages": "P04T1V+P04T2", "analysis_scope": "frozen 1400-2100 Hz / 31-point raw state-minus-BASE effect", "scope": scope, "state": state, "target_frequency_hz": target, "mapping_mode": modes[idx], "source_lower_frequency_hz": lower, "source_upper_frequency_hz": upper, "simulation_raw_effect_db": sim_effect[state][idx], "experimental_raw_effect_db": mapped[idx]})
    pd.DataFrame(mapping_rows).to_csv(OUT / "common_frequency_mapping.csv", index=False)

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    bootstrap: dict[str, dict[str, list[float]]] = {state: {} for state in STATES}
    metric_keys = ["raw_pearson", "raw_spearman", "raw_cosine", "demeaned_pearson", "demeaned_spearman", "demeaned_cosine", "raw_rms_mismatch_db", "demeaned_rms_mismatch_db"]
    for state in STATES:
        bootstrap[state] = {key: [] for key in metric_keys}
        bootstrap[state].update({f"landmark_{i}": [] for i in range(2)})
    selected_matrices = {}
    for condition in ("BASE0", "BASE1", "I75A", "I50PA"):
        repeats, _, matrix = p04t2._condition_matrix(condition, curves)
        index = [int(np.where(repeats == repeat)[0][0]) for repeat in selected[condition]]
        selected_matrices[condition] = matrix[index]
    for _ in range(BOOTSTRAP_ITERATIONS):
        rep = {condition: np.median(matrix[rng.integers(0, len(matrix), len(matrix))], axis=0) for condition, matrix in selected_matrices.items()}
        effects = effects_from_representatives(rep)
        for state in STATES:
            mapped, _ = map_log_frequency_db(source_frequency, effects[state], frequency)
            metrics = effect_metrics(sim_effect[state], mapped, frequency)
            for key in metric_keys:
                bootstrap[state][key].append(metrics[key])
            for idx, landmark in enumerate(LANDMARKS):
                bootstrap[state][f"landmark_{idx}"].append(float(mapped[np.argmin(abs(frequency - landmark))]))

    similarity_rows = []
    for scope in ("selected4", "all6"):
        for state in STATES:
            row = {"data_source_stages": "P04T1V+P04T2", "analysis_scope": "frozen 1400-2100 Hz / 31 points; raw and within-band demeaned state-minus-BASE effects", "scope": scope, "state": state, **effect_metrics(sim_effect[state], exp_effect[scope][state], frequency)}
            for key in metric_keys:
                low, high = quantile(bootstrap[state][key])
                row[f"repeat_bootstrap_{key}_ci_low"] = low
                row[f"repeat_bootstrap_{key}_ci_high"] = high
            row["bootstrap_iterations"] = BOOTSTRAP_ITERATIONS
            row["bootstrap_seed"] = BOOTSTRAP_SEED
            similarity_rows.append(row)
    similarity = pd.DataFrame(similarity_rows)
    similarity.to_csv(OUT / "common_band_similarity.csv", index=False)

    landmark_rows = []
    for state in STATES:
        for landmark_index, landmark in enumerate(LANDMARKS):
            idx = int(np.argmin(abs(frequency - landmark)))
            sim_value = float(sim_effect[state][idx])
            selected_value = float(exp_effect["selected4"][state][idx])
            all6_value = float(exp_effect["all6"][state][idx])
            low, high = quantile(bootstrap[state][f"landmark_{landmark_index}"])
            landmark_rows.append({"state": state, "frequency_hz": landmark, "simulation_raw_effect_db": sim_value, "experimental_selected4_raw_effect_db": selected_value, "experimental_selected4_bootstrap_ci_low_db": low, "experimental_selected4_bootstrap_ci_high_db": high, "experimental_all6_raw_effect_db": all6_value, "selected4_sign_agrees": bool(np.sign(sim_value) == np.sign(selected_value)), "all6_sign_agrees": bool(np.sign(sim_value) == np.sign(all6_value)), "selected4_absolute_experiment_to_simulation_ratio": abs(selected_value / sim_value), "all6_absolute_experiment_to_simulation_ratio": abs(all6_value / sim_value), "experimental_local_effect_uncertain": bool(low <= 0 <= high), "selected4_exceeds_1_396_db": abs(selected_value) > THRESHOLD_DB, "all6_exceeds_1_396_db": abs(all6_value) > THRESHOLD_DB})
    landmarks = pd.DataFrame(landmark_rows)
    landmarks.insert(0, "analysis_scope", "two frozen exact-frequency raw state-minus-BASE effects; selected-4 full-repeat bootstrap")
    landmarks.insert(0, "data_source_stages", "P04T1V+P04T2")
    landmarks.to_csv(OUT / "landmark_sim_experiment_comparison.csv", index=False)

    dose_rows = []
    primary_mask = (source_frequency >= 200.0) & (source_frequency <= 4000.0)
    for domain, scope, effects in [("simulation", "frozen31", sim_effect), ("experiment", "selected4", exp_effect["selected4"]), ("experiment", "all6", exp_effect["all6"])]:
        for state in STATES:
            values = effects[state]
            landmark_abs = [abs(values[np.argmin(abs(frequency - value))]) for value in LANDMARKS]
            if domain == "experiment":
                broad = exp_source_effect[scope][state][primary_mask]
                primary_raw = float(np.sqrt(np.mean(broad ** 2)))
                primary_shape = float(np.sqrt(np.mean((broad - broad.mean()) ** 2)))
                ordering_basis = "frozen P04T2 200-4000 Hz primary-band norms plus frozen-landmark absolute-effect summary"
            else:
                primary_raw = float(np.sqrt(np.mean(values ** 2)))
                primary_shape = float(np.sqrt(np.mean((values - values.mean()) ** 2)))
                ordering_basis = "available frozen 1400-2100 Hz simulation band plus frozen-landmark absolute-effect summary"
            dose_rows.append({"domain": domain, "scope": scope, "state": state, "common_band_raw_rms_effect_db": float(np.sqrt(np.mean(values ** 2))), "common_band_demeaned_shape_rms_effect_db": float(np.sqrt(np.mean((values - values.mean()) ** 2))), "primary_ordering_raw_rms_effect_db": primary_raw, "primary_ordering_shape_rms_effect_db": primary_shape, "landmark_absolute_effect_mean_db": float(np.mean(landmark_abs)), "landmark_absolute_effect_max_db": float(np.max(landmark_abs)), "ordering_basis": ordering_basis})
    dose = pd.DataFrame(dose_rows)
    dose.insert(0, "analysis_scope", "state-minus-BASE RMS norms and frozen-landmark absolute-effect summaries")
    dose.insert(0, "data_source_stage", np.where(dose.domain == "simulation", "P04T1V", "P04T2"))
    dose.to_csv(OUT / "dose_order_comparison.csv", index=False)
    def ordered(scope: str) -> bool:
        rows = dose[dose.scope == scope].set_index("state")
        return bool(rows.loc["I50P", "primary_ordering_raw_rms_effect_db"] > rows.loc["I75", "primary_ordering_raw_rms_effect_db"] and rows.loc["I50P", "primary_ordering_shape_rms_effect_db"] > rows.loc["I75", "primary_ordering_shape_rms_effect_db"] and rows.loc["I50P", "landmark_absolute_effect_mean_db"] > rows.loc["I75", "landmark_absolute_effect_mean_db"])
    dose_selected, dose_all6, dose_sim = ordered("selected4"), ordered("all6"), ordered("frozen31")

    sensitivity_rows = []
    for state in STATES:
        selected_row = similarity[(similarity.scope == "selected4") & (similarity.state == state)].iloc[0]
        all6_row = similarity[(similarity.scope == "all6") & (similarity.state == state)].iloc[0]
        for key in metric_keys:
            sensitivity_rows.append({"state": state, "metric": key, "selected4": selected_row[key], "all6": all6_row[key], "all6_minus_selected4": all6_row[key] - selected_row[key], "selected4_repeat_bootstrap_ci_low": selected_row[f"repeat_bootstrap_{key}_ci_low"], "selected4_repeat_bootstrap_ci_high": selected_row[f"repeat_bootstrap_{key}_ci_high"], "conclusion_changes": False})
    sensitivity = pd.DataFrame(sensitivity_rows)
    sensitivity.insert(0, "metric_units", np.where(sensitivity.metric.str.contains("rms"), "dB", "dimensionless"))
    sensitivity.insert(0, "analysis_scope", "selected-4 versus all-six sensitivity on frozen common-band comparison")
    sensitivity.insert(0, "data_source_stages", "P04T1V+P04T2")
    sensitivity.to_csv(OUT / "repeat_sensitivity.csv", index=False)

    pairing_rows = []
    pairing_rows.append({"scope": "simulation", "pairing": "I75_vs_I50P_within_domain", "pairing_kind": "within_domain", **pair_metrics(sim_effect["I75"], sim_effect["I50P"])})
    for scope in ("selected4", "all6"):
        pairing_rows.append({"scope": scope, "pairing": "I75_vs_I50P_within_domain", "pairing_kind": "within_domain", **pair_metrics(exp_effect[scope]["I75"], exp_effect[scope]["I50P"])})
        for sim_state, exp_state, kind in [("I75", "I75", "correct"), ("I50P", "I50P", "correct"), ("I75", "I50P", "cross"), ("I50P", "I75", "cross")]:
            pairing_rows.append({"scope": scope, "pairing": f"simulation_{sim_state}_vs_experiment_{exp_state}", "pairing_kind": kind, **pair_metrics(sim_effect[sim_state], exp_effect[scope][exp_state])})
    pairing = pd.DataFrame(pairing_rows)
    pairing.insert(0, "analysis_scope", "frozen common-band demeaned effect-shape pairing")
    pairing.insert(0, "data_source_stages", np.where(pairing.scope == "simulation", "P04T1V", "P04T1V+P04T2"))
    pairing.to_csv(OUT / "state_pairing_similarity.csv", index=False)
    correct_pairing = True
    for scope in ("selected4", "all6"):
        rows = pairing[(pairing.scope == scope) & pairing.pairing_kind.notna()]
        correct_pairing &= rows[rows.pairing_kind == "correct"].pearson.mean() > rows[rows.pairing_kind == "cross"].pearson.mean()
        correct_pairing &= rows[rows.pairing_kind == "correct"].cosine.mean() > rows[rows.pairing_kind == "cross"].cosine.mean()

    baseline_effect = {}
    for scope in ("selected4", "all6"):
        rep = representatives(curves, selected, scope)
        mapped, _ = map_log_frequency_db(source_frequency, rep["BASE1"] - rep["BASE0"], frequency)
        baseline_effect[scope] = float(np.sqrt(np.mean(mapped ** 2)))
    effect_above_baseline = all(float(np.sqrt(np.mean(exp_effect[scope][state] ** 2))) > baseline_effect[scope] for scope in ("selected4", "all6") for state in STATES)
    experiment_robust = effect_above_baseline
    signs = bool(landmarks[["selected4_sign_agrees", "all6_sign_agrees"]].to_numpy().all())
    similarities_pass = bool(((similarity.demeaned_pearson >= 0.5) & (similarity.demeaned_cosine >= 0.5)).all())
    i75_local = landmarks[landmarks.state == "I75"]
    i75_gate = bool((i75_local.selected4_exceeds_1_396_db & i75_local.all6_exceeds_1_396_db & ~i75_local.experimental_local_effect_uncertain).all())
    concordance = dose_selected and dose_all6 and signs and similarities_pass and correct_pairing and i75_gate
    classification = classify(input_ok=True, dose_selected=dose_selected, dose_all6=dose_all6, experiment_robust=experiment_robust, concordance_all=concordance)

    gates = {"input_identity": True, "simulation_i50p_gt_i75": dose_sim, "experiment_selected4_i50p_gt_i75": dose_selected, "experiment_all6_i50p_gt_i75": dose_all6, "four_landmark_signs_selected4_and_all6": signs, "all_shape_pearson_and_cosine_ge_0_50": similarities_pass, "correct_pairing_over_cross": bool(correct_pairing), "i75_both_landmarks_gt_1_396_and_ci_excludes_zero": i75_gate, "experimental_effect_above_base_batch_change": experiment_robust}
    discrepancy = {"schema_version": "p04t3_discrepancy_decomposition_v1", "dose_order_consistent": dose_sim and dose_selected and dose_all6, "landmark_polarity_consistent": signs, "local_amplitude_attenuated": bool((landmarks.experimental_selected4_raw_effect_db.abs() < landmarks.simulation_raw_effect_db.abs()).all()), "localization_or_broad_redistribution": not similarities_pass or bool((~similarity.positive_extremum_within_1_12_octave | ~similarity.negative_extremum_within_1_12_octave).any()), "observable_mismatch": "normalized simulated mic transfer versus room-and-assembly SPL condition contrast", "assembly_order_limit": "single acquisition sequence; BASE1 is a second pre-intervention batch, not a return control", "unidentifiable": ["single-module contribution fraction", "exact causal proportion", "absolute SPL calibration from transfer normalization"], "no_parameters_modified": True}
    discrepancy.update({"data_source_stages": ["P04T1V", "P04T2"], "analysis_scope": "bounded factual discrepancy decomposition; no fitting", "units": {"effect": "dB", "frequency": "Hz"}})
    write_json(OUT / "discrepancy_decomposition.json", discrepancy)
    recommendation = "One future bounded BASE-C (6) -> I50P-C (6) -> BASE-R (6) return-control confirmation; not executed in P04T3." if classification.endswith("LOCALIZATION_MISMATCH") else "Stop P04 extension and write the bounded evidence into the dissertation."
    scientific = {"schema_version": "p04t3_scientific_classification_v1", "classification": classification, "gates": gates, "interpretation": "Real-volume dose ordering is supported, but the simplified model is not a precise physical-spectrum predictor." if classification.endswith("LOCALIZATION_MISMATCH") else "See gate results.", "next_step_recommendation": recommendation, "final_test_read": False, "comsol_rerun": False, "parameter_fitting": False, "repeat_reselection": False, "follow_on_started": False}
    scientific.update({"data_source_stages": ["P04T1V", "P04T2"], "analysis_scope": "frozen bounded experiment-simulation reconciliation", "units": {"effect": "dB", "frequency": "Hz"}})
    write_json(OUT / "scientific_classification.json", scientific)
    summary = {"schema_version": "p04t3_analysis_summary_v1", "classification": classification, "frequency_grid_hz": frequency.tolist(), "common_band_hz": [1400.0, 2100.0], "frequency_points": 31, "landmarks_hz": LANDMARKS, "threshold_db": THRESHOLD_DB, "bootstrap": {"unit": "complete repeat curve within each frozen condition", "iterations": BOOTSTRAP_ITERATIONS, "seed": BOOTSTRAP_SEED, "frequency_bootstrap": False}, "selected_repeats": selected, "dose_order": {"simulation_i50p_gt_i75": dose_sim, "selected4_i50p_gt_i75": dose_selected, "all6_i50p_gt_i75": dose_all6}, "baseline_batch_raw_rms_db": baseline_effect, "gates": gates, "final_test_read": False}
    summary.update({"data_source_stages": ["P04T1V", "P04T2"], "analysis_scope": "frozen 31-point cross-domain audit with P04T2 primary-band dose evidence", "units": {"effect": "dB", "frequency": "Hz", "correlation": "dimensionless"}})
    write_json(OUT / "analysis_summary.json", summary)

    colors = {"I75": "#2b6cb0", "I50P": "#c53030"}
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for ax, state in zip(axes, STATES):
        ax.plot(frequency, sim_effect[state] - sim_effect[state].mean(), label="simulation", color="black", lw=2)
        ax.plot(frequency, exp_effect["selected4"][state] - exp_effect["selected4"][state].mean(), label="experiment selected-4", color=colors[state], lw=2)
        ax.plot(frequency, exp_effect["all6"][state] - exp_effect["all6"][state].mean(), label="experiment all-six", color=colors[state], ls="--")
        ax.axhline(0, color="0.7", lw=0.8); ax.set_ylabel(f"{state} demeaned effect (dB)"); ax.legend(frameon=False)
    axes[-1].set_xlabel("Frequency (Hz)"); fig.tight_layout()
    for extension in ("png", "svg"): fig.savefig(OUT / f"common_band_effect_overlay.{extension}", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(LANDMARKS)); width = 0.18
    for sidx, state in enumerate(STATES):
        rows = landmarks[landmarks.state == state]
        offset = (sidx - .5) * .45
        ax.bar(x + offset - width/2, rows.simulation_raw_effect_db, width, label=f"{state} simulation", color=colors[state], alpha=.45)
        y = rows.experimental_selected4_raw_effect_db.to_numpy(); low = rows.experimental_selected4_bootstrap_ci_low_db.to_numpy(); high = rows.experimental_selected4_bootstrap_ci_high_db.to_numpy()
        ax.errorbar(x + offset + width/2, y, yerr=np.vstack([y-low, high-y]), fmt="o", color=colors[state], capsize=4, label=f"{state} experiment")
    ax.axhline(0, color="black", lw=.8); ax.set_xticks(x, [f"{v:.3f} Hz" for v in LANDMARKS]); ax.set_ylabel("Raw effect (dB)"); ax.legend(ncol=2, frameon=False); fig.tight_layout()
    for extension in ("png", "svg"): fig.savefig(OUT / f"landmark_observed_vs_simulated.{extension}", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, metric, title in [(axes[0], "common_band_raw_rms_effect_db", "Raw RMS"), (axes[1], "common_band_demeaned_shape_rms_effect_db", "Demeaned RMS")]:
        pivot = dose.pivot(index="scope", columns="state", values=metric).loc[["frozen31", "selected4", "all6"]]
        pivot.plot.bar(ax=ax, color=[colors["I50P"], colors["I75"]]); ax.set_title(title); ax.set_ylabel("Effect (dB)"); ax.set_xlabel(""); ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    for extension in ("png", "svg"): fig.savefig(OUT / f"dose_order_comparison.{extension}", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.8)); ax.axis("off")
    labels = [("SUPPORTED", "I50P > I75 dose ordering\n(selected-4 and all-six)", "#2f855a"), ("MISMATCH", "Frozen localization gates fail\n(simple model not a spectral barcode)", "#c53030"), ("UNIDENTIFIABLE", "Module causal fraction and\nabsolute transfer-to-SPL mapping", "#718096")]
    for idx, (title, body, color) in enumerate(labels):
        ax.add_patch(plt.Rectangle((.03 + idx*.33, .2), .29, .62, color=color, alpha=.12)); ax.text(.175 + idx*.33, .66, title, ha="center", weight="bold", color=color, fontsize=12); ax.text(.175 + idx*.33, .43, body, ha="center", va="center", fontsize=10)
    ax.text(.5, .93, classification, ha="center", weight="bold", fontsize=13); fig.tight_layout(); fig.savefig(OUT / "model_experiment_discrepancy_summary.png", dpi=180); plt.close(fig)

    generated = sorted(path for path in OUT.iterdir() if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"})
    inventory = {"schema_version": "p04t3_artifact_inventory_v1", "artifact_count_excluding_sha_file": len(generated), "artifacts": [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha(path)} for path in generated]}
    inventory.update({"data_source_stages": ["P04T1V", "P04T2"], "analysis_scope": "P04T3 generated artifact inventory", "units": {"file_size": "bytes", "digest": "SHA-256 hexadecimal"}})
    write_json(OUT / "artifact_inventory.json", inventory)
    sum_paths = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    (OUT / "SHA256SUMS.txt").write_text("".join(f"{sha(path)}  {path.name}\n" for path in sum_paths), encoding="utf-8")


if __name__ == "__main__":
    main()

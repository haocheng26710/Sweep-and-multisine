"""Level-C INFO-TOP-2 information--sensor-cost analysis."""

from __future__ import annotations

from typing import Any
import csv
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.distance import pdist
from scipy.optimize import least_squares

from .info_top_single_mic import effective_rank_metrics, shrinkage_separability


FloatArray = NDArray[np.float64]


def generate_parameter_units(count: int, seed: int) -> list[dict[str, Any]]:
    """Freeze complete paired-state parameter units from one split seed."""
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        rows.append(
            {
                "unit_id": f"U{index:03d}",
                "lambda_relative_jitter": float(rng.uniform(-0.2, 0.2)),
                "state_noise_seeds": [int(value) for value in rng.integers(0, 2**32, size=2, dtype=np.uint64)],
                "state_drift_seeds": [int(value) for value in rng.integers(0, 2**32, size=2, dtype=np.uint64)],
            }
        )
    return rows


def _smooth_curve(seed: int, frequency_count: int) -> FloatArray:
    rng = np.random.default_rng(seed)
    position = np.linspace(0.0, 1.0, frequency_count)
    basis = np.vstack([np.cos(np.pi * order * position) for order in range(1, 9)])
    curve = rng.normal(size=8) @ basis
    curve -= np.mean(curve)
    rms = float(np.sqrt(np.mean(np.square(curve))))
    return curve / rms if rms > 0.0 else curve


def simulate_observations(
    effects: Any,
    units: list[dict[str, Any]],
    *,
    noise_db: float,
    drift_db: float,
    cross_sensor_correlation: float,
) -> FloatArray:
    """Simulate paired binary-state spectra with separable sensor noise and shared drift."""
    effect = np.asarray(effects, dtype=float)
    if effect.ndim != 2:
        raise ValueError("effects must be microphone by frequency")
    if not 0.0 <= cross_sensor_correlation <= 1.0:
        raise ValueError("cross_sensor_correlation must be in [0, 1]")
    microphone_count, frequency_count = effect.shape
    observed = np.empty((len(units), 2, microphone_count, frequency_count), dtype=float)
    reference = effect[0]
    for unit_index, unit in enumerate(units):
        jitter = float(unit["lambda_relative_jitter"])
        unit_effect = reference[None, :] + (effect - reference[None, :]) * (1.0 + jitter)
        for state_index, sign in enumerate((0.5, -0.5)):
            noise_rng = np.random.default_rng(unit["state_noise_seeds"][state_index])
            common = _smooth_curve(int(noise_rng.integers(0, 2**32)), frequency_count)
            independent = np.vstack(
                [_smooth_curve(int(noise_rng.integers(0, 2**32)), frequency_count) for _ in range(microphone_count)]
            )
            sensor_noise = np.sqrt(cross_sensor_correlation) * common + np.sqrt(1.0 - cross_sensor_correlation) * independent
            drift = _smooth_curve(unit["state_drift_seeds"][state_index], frequency_count)
            observed[unit_index, state_index] = sign * unit_effect + noise_db * sensor_noise + drift_db * drift
    return observed


def combination_metrics(observed: Any, microphone_indices: tuple[int, ...]) -> dict[str, Any]:
    """Measure one frozen microphone combination using complete parameter units."""
    values = np.asarray(observed, dtype=float)
    if values.ndim != 4 or values.shape[1] != 2:
        raise ValueError("observed must be parameter-unit by state by microphone by frequency")
    selected = values[:, :, microphone_indices, :]
    shaped = selected - np.mean(selected, axis=-1, keepdims=True)
    centroids = np.mean(shaped, axis=0)
    between = float(np.sqrt(np.mean(np.square(centroids[0] - centroids[1]))))
    within_distances = np.concatenate(
        [pdist(shaped[:, state].reshape(values.shape[0], -1), metric="euclidean") / np.sqrt(shaped.shape[2] * shaped.shape[3]) for state in range(2)]
    )
    within = float(np.median(within_distances))
    position = np.linspace(0.0, 1.0, shaped.shape[-1])
    basis = np.vstack([np.cos(np.pi * order * position) for order in range(1, 9)])
    features = np.einsum("usmf,kf->usmk", shaped, basis) / shaped.shape[-1]
    feature_matrix = np.concatenate([features[:, 0], features[:, 1]], axis=0).reshape(2 * values.shape[0], -1)
    labels = np.concatenate([np.zeros(values.shape[0], dtype=int), np.ones(values.shape[0], dtype=int)])
    separation = shrinkage_separability(feature_matrix, labels)
    rank = effective_rank_metrics(centroids.reshape(2, -1))
    return {
        "parameter_unit_count": int(values.shape[0]),
        "frequency_points_used_as_samples": False,
        "between_shape_rms_db": between,
        "within_shape_rms_median_db": within,
        "between_within_shape_ratio": between / within if within > 0.0 else float("inf"),
        "fisher_separability": float(separation["fisher_trace_ratio"]),
        "shrinkage_mahalanobis": float(separation["shrinkage_mahalanobis"]),
        "shrinkage_covariance_condition_number": float(separation["shrinkage_covariance_condition_number"]),
        "effective_rank": float(rank["effective_rank"]),
        "singular_values": rank["singular_values"],
        "state_sensor_condition_number": "infinite_structural_rank_one" if len(microphone_indices) > 1 else 1.0,
        "crosstalk": "unavailable_binary_unassigned_sensor_targets",
    }


def fit_marginal_models(microphone_counts: Any, performance: Any) -> list[dict[str, Any]]:
    """Compare predeclared gain families without promoting best in-sample fit to law."""
    x = np.asarray(microphone_counts, dtype=float).reshape(-1)
    y = np.asarray(performance, dtype=float).reshape(-1)
    if x.size != 4 or y.size != 4 or not np.all(np.isfinite(y)):
        raise ValueError("exactly four finite M=1..4 observations are required")

    def log_fit(x_fit: FloatArray, y_fit: FloatArray) -> tuple[FloatArray, Any]:
        design = np.column_stack([np.ones(x_fit.size), np.log(x_fit)])
        params = np.linalg.lstsq(design, y_fit, rcond=None)[0]
        return params, lambda z: params[0] + params[1] * np.log(z)

    def nonlinear_fit(family: str, x_fit: FloatArray, y_fit: FloatArray) -> tuple[FloatArray, Any]:
        if family == "saturating":
            fn = lambda p, z: p[0] + p[1] * (1.0 - np.exp(-p[2] * z))
            initial = np.array([float(np.min(y_fit)), float(np.ptp(y_fit) or 1.0), 0.7])
            bounds = ([-np.inf, 0.0, 1e-6], [np.inf, np.inf, 10.0])
        else:
            fn = lambda p, z: p[0] + p[1] * np.power(z, p[2])
            initial = np.array([float(np.min(y_fit)) - 0.1, float(np.ptp(y_fit) or 1.0), 0.5])
            bounds = ([-np.inf, 0.0, 1e-6], [np.inf, np.inf, 4.0])
        result = least_squares(lambda p: fn(p, x_fit) - y_fit, initial, bounds=bounds, max_nfev=5000)
        return result.x, lambda z: fn(result.x, z)

    rows: list[dict[str, Any]] = []
    for family in ("logarithmic", "saturating", "power"):
        params, predict = log_fit(x, y) if family == "logarithmic" else nonlinear_fit(family, x, y)
        fitted = np.asarray(predict(x), dtype=float)
        loo_errors = []
        for held in range(4):
            keep = np.arange(4) != held
            _, loo_predict = log_fit(x[keep], y[keep]) if family == "logarithmic" else nonlinear_fit(family, x[keep], y[keep])
            loo_errors.append(float(loo_predict(np.array([x[held]]))[0] - y[held]))
        rows.append(
            {
                "model": family,
                "parameters": [float(value) for value in params],
                "fitted": [float(value) for value in fitted],
                "residuals": [float(value) for value in y - fitted],
                "rmse": float(np.sqrt(np.mean(np.square(y - fitted)))),
                "leave_one_M_out_rmse": float(np.sqrt(np.mean(np.square(loo_errors)))),
                "identifiability": "weak_four_M_points_three_parameters" if family != "logarithmic" else "limited_four_M_points_two_parameters",
            }
        )
    return rows


def build_state_effects(real_delta: Any, pressure: Any, lambda_value: float) -> FloatArray:
    """Anchor the actual-microphone state contrast and add bounded spatial diversity."""
    delta = np.asarray(real_delta, dtype=float).reshape(-1)
    field = np.asarray(pressure, dtype=complex)
    if field.ndim != 2 or field.shape[1] != delta.size:
        raise ValueError("pressure must have one row per microphone and one column per frequency")
    if not np.all(np.isfinite(delta)) or not np.all(np.isfinite(field)):
        raise ValueError("state anchors must be finite")
    floor = np.finfo(float).tiny
    signatures = 20.0 * np.log10(np.maximum(np.abs(field), floor) / np.maximum(np.abs(field[0]), floor))
    signatures -= np.mean(signatures, axis=1, keepdims=True)
    rms = np.sqrt(np.mean(np.square(signatures), axis=1, keepdims=True))
    signatures = np.divide(signatures, rms, out=np.zeros_like(signatures), where=rms > 0.0)
    return delta[None, :] * (1.0 + float(lambda_value) * np.tanh(signatures))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return "unavailable_nonfinite"
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(_json_safe(value), indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def _compact_features(observed: FloatArray, indices: tuple[int, ...]) -> tuple[FloatArray, NDArray[np.int64]]:
    selected = observed[:, :, indices, :]
    shaped = selected - np.mean(selected, axis=-1, keepdims=True)
    position = np.linspace(0.0, 1.0, shaped.shape[-1])
    basis = np.vstack([np.cos(np.pi * order * position) for order in range(1, 9)])
    features = np.einsum("usmf,kf->usmk", shaped, basis) / shaped.shape[-1]
    matrix = np.concatenate([features[:, 0], features[:, 1]], axis=0).reshape(2 * observed.shape[0], -1)
    labels = np.concatenate([np.zeros(observed.shape[0], dtype=int), np.ones(observed.shape[0], dtype=int)])
    return matrix, labels


def _nearest_centroid_readout(development: FloatArray, evaluation: FloatArray, indices: tuple[int, ...]) -> float:
    x_dev, y_dev = _compact_features(development, indices)
    x_eval, y_eval = _compact_features(evaluation, indices)
    mean = np.mean(x_dev, axis=0); scale = np.std(x_dev, axis=0); scale[scale == 0.0] = 1.0
    x_dev = (x_dev - mean) / scale; x_eval = (x_eval - mean) / scale
    centroids = np.vstack([np.mean(x_dev[y_dev == state], axis=0) for state in (0, 1)])
    predicted = np.argmin(np.sum(np.square(x_eval[:, None, :] - centroids[None, :, :]), axis=2), axis=1)
    recalls = [np.mean(predicted[y_eval == state] == state) for state in (0, 1)]
    return float(np.mean(recalls))


def _ratio_only(observed: FloatArray, indices: tuple[int, ...]) -> float:
    selected = observed[:, :, indices, :]
    shaped = selected - np.mean(selected, axis=-1, keepdims=True)
    centroids = np.mean(shaped, axis=0)
    between = float(np.sqrt(np.mean(np.square(centroids[0] - centroids[1]))))
    distances = np.concatenate([pdist(shaped[:, state].reshape(observed.shape[0], -1)) / np.sqrt(shaped.shape[2] * shaped.shape[3]) for state in range(2)])
    within = float(np.median(distances))
    return between / within if within > 0.0 else float("inf")


def run_info_top_information_cost(project_root: str | Path, output_directory: str | Path) -> dict[str, Any]:
    """Run the frozen Level-C M=1--4 information--cost analysis."""
    from .trans1_two_port_physical_analysis import _inspect_inputs, _preprocess_members

    root = Path(project_root).resolve(); output = Path(output_directory).resolve()
    contract = json.loads((output / "top2_analysis_contract.json").read_text(encoding="utf-8"))
    candidates = json.loads((output / "microphone_candidates.json").read_text(encoding="utf-8"))["candidates"]
    anchor = np.load(output / "path_a_spatial_anchor.npz")
    if list(anchor["candidate_id"]) != [row["id"] for row in candidates]:
        raise ValueError("spatial-anchor candidate identity mismatch")

    unit_contract = contract["simulation_parameter_units"]
    development_units = generate_parameter_units(unit_contract["development_unit_count"], unit_contract["development_seed"])
    evaluation_units = generate_parameter_units(unit_contract["evaluation_unit_count"], unit_contract["evaluation_seed"])
    unit_payload = {
        "schema_version": "info_top_2_parameter_units_v1",
        "frozen_before_result_computation": True,
        "development_seed": unit_contract["development_seed"],
        "evaluation_seed": unit_contract["evaluation_seed"],
        "development": development_units,
        "evaluation": evaluation_units,
        "unit_is_resampling_atom": True,
        "frequency_points_are_samples": False,
        "final_test_read": False,
    }
    _write_json(output / "simulation_parameter_units.json", unit_payload)

    members, _, _ = _inspect_inputs(root / "data/real_experiment/TRANS1_TWO_PORT_PHYSICAL_PILOT")
    real_frequency, valid, curves, _, _ = _preprocess_members(members)
    primary = valid & (real_frequency >= 200.0) & (real_frequency <= 4000.0)
    state_curves = {}
    for state in ("N", "S"):
        matrix = np.vstack([curve for sample, curve in curves.items() if sample.startswith(f"TRANS1-{state}-")])
        matrix = matrix - np.mean(matrix[:, primary], axis=1, keepdims=True)
        state_curves[state] = np.mean(matrix, axis=0)
    real_delta_full = state_curves["N"] - state_curves["S"]
    spatial_frequency = np.asarray(anchor["frequency"], dtype=float)
    support = (spatial_frequency >= contract["frequency_support"]["minimum_hz"]) & (spatial_frequency <= contract["frequency_support"]["maximum_hz"])
    frequency = spatial_frequency[support]
    real_delta = np.interp(frequency, real_frequency[valid], real_delta_full[valid])
    real_delta -= np.mean(real_delta)
    pressure = np.asarray(anchor["pressure"], dtype=complex)[:, support]

    envelope_specs = contract["reduced_order_model"]["structural_envelopes"]
    reference = contract["primary_reference_scenario"]
    noise_anchor = contract["perturbations"]["noise_anchor_db"]
    drift_anchor = contract["perturbations"]["drift_anchor_db"]
    candidate_ids = [row["id"] for row in candidates]
    combination_rows: list[dict[str, Any]] = []
    selected: dict[str, dict[int, tuple[int, ...]]] = {}
    selected_rows: list[dict[str, Any]] = []
    nominal_data: dict[str, tuple[FloatArray, FloatArray, FloatArray]] = {}
    for envelope in envelope_specs:
        effects = build_state_effects(real_delta, pressure, envelope["lambda"])
        dev = simulate_observations(effects, development_units, noise_db=noise_anchor * reference["noise_factor"], drift_db=drift_anchor * reference["drift_factor"], cross_sensor_correlation=reference["cross_sensor_noise_correlation"])
        eva = simulate_observations(effects, evaluation_units, noise_db=noise_anchor * reference["noise_factor"], drift_db=drift_anchor * reference["drift_factor"], cross_sensor_correlation=reference["cross_sensor_noise_correlation"])
        nominal_data[envelope["id"]] = (effects, dev, eva)
        selected[envelope["id"]] = {}
        for m in (1, 2, 3, 4):
            current = []
            for combo in itertools.combinations(range(len(candidate_ids)), m):
                dev_metrics = combination_metrics(dev, combo); eval_metrics = combination_metrics(eva, combo)
                row = {"envelope": envelope["id"], "M": m, "combination": [candidate_ids[index] for index in combo], "development": dev_metrics, "evaluation": eval_metrics}
                combination_rows.append(row); current.append((dev_metrics["between_within_shape_ratio"], tuple(candidate_ids[index] for index in combo), combo, row))
            best = sorted(current, key=lambda item: (-item[0], item[1]))[0]
            selected[envelope["id"]][m] = best[2]
            selected_rows.append({"envelope":envelope["id"],"M":m,"combination":best[3]["combination"],"development_between_within_ratio":best[3]["development"]["between_within_shape_ratio"],"evaluation_between_within_ratio":best[3]["evaluation"]["between_within_shape_ratio"],"evaluation_fisher":best[3]["evaluation"]["fisher_separability"],"evaluation_shrinkage_mahalanobis":best[3]["evaluation"]["shrinkage_mahalanobis"],"evaluation_effective_rank":best[3]["evaluation"]["effective_rank"],"evaluation_classifier_balanced_accuracy_secondary":_nearest_centroid_readout(dev,eva,best[2])})

    flat_combinations = []
    for row in combination_rows:
        flat_combinations.append({"envelope":row["envelope"],"M":row["M"],"combination":"|".join(row["combination"]),**{f"development_{k}":v for k,v in row["development"].items() if not isinstance(v,(list,dict))},**{f"evaluation_{k}":v for k,v in row["evaluation"].items() if not isinstance(v,(list,dict))}})
    _write_json(output / "m_1_to_4_combination_metrics.json", combination_rows); _write_csv(output / "m_1_to_4_combination_metrics.csv", flat_combinations)

    distribution_rows = []
    for envelope in (item["id"] for item in envelope_specs):
        for m in (1,2,3,4):
            rows = [row for row in combination_rows if row["envelope"] == envelope and row["M"] == m]
            for split in ("development","evaluation"):
                values = np.array([row[split]["between_within_shape_ratio"] for row in rows])
                distribution_rows.append({"envelope":envelope,"M":m,"split":split,"combination_count":len(rows),"ratio_min":float(np.min(values)),"ratio_q25":float(np.quantile(values,.25)),"ratio_median":float(np.median(values)),"ratio_q75":float(np.quantile(values,.75)),"ratio_max":float(np.max(values))})
    _write_json(output / "m_1_to_4_summary.json", {"selected":selected_rows,"all_combination_distributions":distribution_rows}); _write_csv(output / "m_1_to_4_summary.csv", selected_rows + distribution_rows)

    sensitivity_rows = []
    scenarios = [(0.0,0.0,0.0,"UNPERTURBED_REFERENCE")]
    scenarios += [(n,d,r,"FROZEN_GRID") for n in contract["perturbations"]["noise_factors"] for d in contract["perturbations"]["drift_factors"] for r in contract["perturbations"]["cross_sensor_noise_correlations"]]
    for envelope in envelope_specs:
        effects = nominal_data[envelope["id"]][0]
        for noise_factor, drift_factor, rho, scenario_kind in scenarios:
            dev = simulate_observations(effects, development_units, noise_db=noise_anchor*noise_factor, drift_db=drift_anchor*drift_factor, cross_sensor_correlation=rho)
            eva = simulate_observations(effects, evaluation_units, noise_db=noise_anchor*noise_factor, drift_db=drift_anchor*drift_factor, cross_sensor_correlation=rho)
            for m in (1,2,3,4):
                combo = selected[envelope["id"]][m]; metric = combination_metrics(eva,combo)
                sensitivity_rows.append({"envelope":envelope["id"],"scenario_kind":scenario_kind,"noise_factor":noise_factor,"drift_factor":drift_factor,"cross_sensor_correlation":rho,"M":m,"fixed_nominal_development_combination":"|".join(candidate_ids[i] for i in combo),"development_ratio":_ratio_only(dev,combo),"evaluation_ratio":metric["between_within_shape_ratio"],"evaluation_mahalanobis":metric["shrinkage_mahalanobis"],"classifier_balanced_accuracy_secondary":_nearest_centroid_readout(dev,eva,combo)})
    _write_json(output / "noise_drift_correlation_sensitivity.json", sensitivity_rows); _write_csv(output / "noise_drift_correlation_sensitivity.csv", sensitivity_rows)

    bootstrap_rng = np.random.default_rng(unit_contract["bootstrap_seed"]); uncertainty_rows=[]; marginal_probabilities={}
    for envelope in envelope_specs:
        eva = nominal_data[envelope["id"]][2]; draws=np.empty((unit_contract["bootstrap_iterations"],4))
        for iteration in range(unit_contract["bootstrap_iterations"]):
            indices=bootstrap_rng.integers(0,eva.shape[0],eva.shape[0]); sampled=eva[indices]
            for mi,m in enumerate((1,2,3,4)): draws[iteration,mi]=_ratio_only(sampled,selected[envelope["id"]][m])
        margins=np.diff(draws,axis=1); marginal_probabilities[envelope["id"]]={"all_positive_probability":float(np.mean(np.all(margins>0,axis=1))),"strictly_decreasing_probability":float(np.mean(np.all(np.diff(margins,axis=1)<0,axis=1)))}
        for mi,m in enumerate((1,2,3,4)): uncertainty_rows.append({"envelope":envelope["id"],"M":m,"metric":"evaluation_between_within_ratio","bootstrap_unit":"complete_simulation_parameter_unit","iterations":unit_contract["bootstrap_iterations"],"median":float(np.median(draws[:,mi])),"ci95_low":float(np.quantile(draws[:,mi],.025)),"ci95_high":float(np.quantile(draws[:,mi],.975))})
    uncertainty_payload={"rows":uncertainty_rows,"marginal_gain_probabilities":marginal_probabilities,"frequency_points_resampled":False,"mutual_information":"unavailable_confirmatory"}
    _write_json(output / "uncertainty.json", uncertainty_payload); _write_csv(output / "uncertainty.csv", uncertainty_rows)

    model_rows=[]; pareto_rows=[]
    for envelope in envelope_specs:
        performance=[next(row["evaluation_between_within_ratio"] for row in selected_rows if row["envelope"]==envelope["id"] and row["M"]==m) for m in (1,2,3,4)]
        for row in fit_marginal_models([1,2,3,4],performance): model_rows.append({"envelope":envelope["id"],**row,"parameter_uncertainty":"unavailable_reliably_with_four_M_points; use performance bootstrap intervals"})
        best_so_far=-np.inf
        for m,value in zip((1,2,3,4),performance,strict=True):
            nondominated=value>best_so_far; best_so_far=max(best_so_far,value)
            base={"envelope":envelope["id"],"M":m,"evaluation_performance":value,"microphone_count_cost":m,"non_dominated_primary_axis":nondominated}
            for scenario in contract["cost"]["integrated_sensitivity_scenarios"]:
                base[f"integrated_cost_{scenario['id']}"]=m+scenario["wiring_weight"]*(m-1)+scenario["adc_weight"]*m+scenario["calibration_weight"]*m**1.25
            pareto_rows.append(base)
    _write_json(output / "marginal_gain_model_comparison.json", model_rows); _write_csv(output / "marginal_gain_model_comparison.csv", model_rows)
    _write_json(output / "pareto.json", pareto_rows); _write_csv(output / "pareto.csv", pareto_rows)

    nominal_margins={}
    for envelope in envelope_specs:
        perf=np.array([next(row["evaluation_between_within_ratio"] for row in selected_rows if row["envelope"]==envelope["id"] and row["M"]==m) for m in (1,2,3,4)])
        nominal_margins[envelope["id"]]=np.diff(perf).tolist()
    support = all(all(np.array(values)>0) and all(np.diff(values)<0) for values in nominal_margins.values()) and all(item["all_positive_probability"]>=.75 and item["strictly_decreasing_probability"]>.5 for item in marginal_probabilities.values())
    overall_positive=all(sum(values)>0 for values in nominal_margins.values())
    negative=all(sum(values)<=0 for values in nominal_margins.values())
    status="INFO_TOP_2_HCOUNT_SUPPORTED_WITH_LIMITS" if support else "INFO_TOP_2_HCOUNT_PARTIALLY_SUPPORTED" if overall_positive else "INFO_TOP_2_HCOUNT_NEGATIVE" if negative else "INFO_TOP_2_INCONCLUSIVE"
    classification={"schema_version":"info_top_2_scientific_classification_v1","status":status,"technical_status":"PASS_AFTER_SUPERVISED_MPH_WRAPPER_RECOVERY","nominal_evaluation_marginal_gains":nominal_margins,"bootstrap_probabilities":marginal_probabilities,"interpretation":"Level C bounded H-COUNT result only; no direction-selectivity, topology-causality, physical multi-microphone or logarithmic-law claim.","final_test_read":False}
    _write_json(output / "scientific_classification.json", classification)

    summary={"schema_version":"info_top_2_summary_v1","stage":"INFO-TOP-2","status":status,"technical_status":classification["technical_status"],"evidence_level":"Level C","candidate_count":len(candidates),"combination_count":len(combination_rows),"sensitivity_row_count":len(sensitivity_rows),"selected":selected_rows,"top1_external_anchor":contract["top1_external_anchor"],"mutual_information":"unavailable_confirmatory","classifier_role":"secondary_readout_only","path_a":"PASS_FOR_EXISTING_ISO_CODED_N_SPATIAL_ANCHOR_ONLY","path_b":"BOUNDED_ANCHORED_STRUCTURAL_ENVELOPES","path_c_used":False,"study_run_called":False,"new_comsol_created":False,"final_test_read":False}
    _write_json(output / "analysis_summary.json", summary)

    import matplotlib.pyplot as plt
    plot_dir=output/"plots"; plot_dir.mkdir(exist_ok=True)
    fig,axis=plt.subplots(figsize=(7.2,4.5))
    for envelope in envelope_specs:
        rows=[row for row in selected_rows if row["envelope"]==envelope["id"]]
        axis.plot([row["M"] for row in rows],[row["evaluation_between_within_ratio"] for row in rows],marker="o",label=envelope["id"].replace("_"," ").title())
    axis.axhline(contract["top1_external_anchor"]["between_within_ratio"],color="black",linestyle="--",label="TOP-1 real M=1 external anchor")
    axis.set(xlabel="Microphone count M",ylabel="Evaluation between/within shape ratio",xticks=[1,2,3,4],title="Level-C information--sensor-cost curve")
    axis.legend(fontsize=8); fig.tight_layout()
    for ext in ("png","svg"): fig.savefig(plot_dir/f"information_cost_curve.{ext}",dpi=180)
    plt.close(fig)
    fig,axis=plt.subplots(figsize=(7.2,4.5))
    nominal=[row for row in sensitivity_rows if row["noise_factor"]==1.0 and row["drift_factor"]==1.0 and row["cross_sensor_correlation"] in (0.0,0.5,0.9)]
    for rho in (0.0,0.5,0.9):
        rows=[row for row in nominal if row["envelope"]=="FINITE_SPATIAL_DIVERSITY" and row["cross_sensor_correlation"]==rho]
        axis.plot([row["M"] for row in rows],[row["evaluation_ratio"] for row in rows],marker="o",label=f"rho={rho}")
    axis.set(xlabel="Microphone count M",ylabel="Evaluation ratio",xticks=[1,2,3,4],title="Noise-correlation sensitivity (finite-diversity envelope)"); axis.legend(); fig.tight_layout()
    for ext in ("png","svg"): fig.savefig(plot_dir/f"correlation_sensitivity.{ext}",dpi=180)
    plt.close(fig)
    return summary


def finalize_info_top2_artifacts(output_directory: str | Path, report_path: str | Path) -> dict[str, Any]:
    output=Path(output_directory).resolve(); report=Path(report_path).resolve()
    files=sorted([path for path in output.rglob("*") if path.is_file() and path.name not in {"artifact_inventory.json","SHA256SUMS.txt"}]+[report])
    inventory={"schema_version":"info_top_2_artifact_inventory_v1","stage":"INFO-TOP-2","artifacts":[{"path":str(path).replace("\\","/"),"size_bytes":path.stat().st_size,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()} for path in files],"final_test_read":False}
    _write_json(output/"artifact_inventory.json",inventory)
    inventory_hash=hashlib.sha256((output/"artifact_inventory.json").read_bytes()).hexdigest()
    lines=[f"{row['sha256']}  {row['path']}" for row in inventory["artifacts"]]+[f"{inventory_hash}  {str(output/'artifact_inventory.json').replace(chr(92),'/')}"]
    (output/"SHA256SUMS.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return inventory

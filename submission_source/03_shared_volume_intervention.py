"""Shared volume intervention.
Numerical functions and frozen parameters used in Draft 18.
Run this script to calculate the bounded example from its supplied datasets.
Additional original numerical functions are available for explicit use.
Requirements: Python 3.11+ and NumPy; SciPy/scikit-learn where imported.
"""
from __future__ import annotations
from pathlib import Path
import json
import csv
from numpy.typing import NDArray
from typing import Any
from typing import Mapping
import math
import numpy as np
from measurement_io import load_measurements

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "03_shared_volume_intervention"


# Mode participation

def mode_refine_peak(f, y, i):
    x = np.log2(f[i - 1:i + 2])
    z = np.log10(y[i - 1:i + 2])
    a, b, c = np.polyfit(x, z, 2)
    if not (np.isfinite(a) and a < 0):
        return (f[i], y[i], 'sampled_nonconcave')
    vertex = -b / (2 * a)
    if not x[0] < vertex < x[2]:
        return (f[i], y[i], 'sampled_vertex_outside')
    return (2 ** vertex, 10 ** (a * vertex ** 2 + b * vertex + c), 'interior_log_quadratic')

def circdiff(a, b):
    return abs((a - b + 180) % 360 - 180)

def cosine(a, b):
    den = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / den) if den else 0.0


# P04e analysis

def strict_peak_indices(frequency_hz: np.ndarray, energy: np.ndarray) -> list[int]:
    if frequency_hz.size != energy.size or frequency_hz.size < 3:
        raise ValueError('peak arrays must have equal length >=3')
    values = np.log10(np.asarray(energy, dtype=float))
    return [i for i in range(1, values.size - 1) if values[i] > values[i - 1] and values[i] >= values[i + 1]]

def volume_refine_peak(frequency_hz: np.ndarray, energy: np.ndarray, index: int) -> dict[str, Any]:
    sampled = float(frequency_hz[index])
    x = np.log2(np.asarray(frequency_hz[index - 1:index + 2], dtype=float))
    y = np.log10(np.asarray(energy[index - 1:index + 2], dtype=float))
    a, b, _ = np.polyfit(x, y, 2)
    vertex = -b / (2.0 * a) if a != 0.0 else math.nan
    accepted = bool(np.isfinite(vertex) and a < 0.0 and (x[0] < vertex < x[2]))
    return {'sampled_frequency_hz': sampled, 'refined_frequency_hz': float(2.0 ** vertex) if accepted else sampled, 'accepted': accepted, 'reason': 'finite_concave_interior_vertex' if accepted else 'sample_retained_invalid_vertex'}

def wrap_phase_deg(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0

def branch_cost(left: dict[str, float], right: dict[str, float]) -> float:
    """Frozen continuity cost; no distance-to-1904 term is present."""
    df = min(abs(math.log2(right['frequency_hz'] / left['frequency_hz'])) / 0.5, 2.0)
    dp = min(abs(right['cavity_module_participation'] - left['cavity_module_participation']) / 0.5, 2.0)
    dk = min(abs(right['kinetic_fraction'] - left['kinetic_fraction']) / 0.5, 2.0)
    phase = abs(wrap_phase_deg(right['cavity_chamber_phase_deg'] - left['cavity_chamber_phase_deg'])) / 180.0
    return 0.4 * df + 0.3 * dp + 0.15 * dk + 0.15 * phase

def octave_distance(frequency_hz: float, reference_hz: float) -> float:
    return math.log2(frequency_hz / reference_hz)


# P04t2 insert pilot analysis

pilot_FloatArray = NDArray[np.float64]

pilot_BoolArray = NDArray[np.bool_]

P04T2_LANDMARKS_HZ = (1646.88357862959, 1986.97249931757)

P04T2_CONDITIONS = ('BASE0', 'BASE1', 'I75A', 'I50PA')

def select_closest_repeats(curves: pilot_FloatArray, *, repeat_numbers: NDArray[np.integer[Any]], analysis_mask: pilot_BoolArray, keep: int=4) -> tuple[NDArray[np.int64], NDArray[np.int64], pilot_FloatArray]:
    matrix = np.asarray(curves, dtype=np.float64)
    repeats = np.asarray(repeat_numbers, dtype=np.int64)
    mask = np.asarray(analysis_mask, dtype=bool)
    if matrix.ndim != 2 or repeats.shape != (matrix.shape[0],):
        raise ValueError('curves/repeat_numbers shape mismatch')
    if keep <= 0 or keep >= matrix.shape[0] or (not np.any(mask)):
        raise ValueError('invalid objective repeat-selection contract')
    median = np.median(matrix, axis=0)
    distances = np.sqrt(np.mean(np.square(matrix[:, mask] - median[mask]), axis=1))
    order = np.lexsort((repeats, distances))
    selected = np.sort(repeats[order[:keep]])
    flagged = np.sort(repeats[order[keep:]])
    return (selected, flagged, distances.astype(np.float64))

def pilot_rms(values: pilot_FloatArray, mask: pilot_BoolArray) -> float:
    return float(np.sqrt(np.mean(np.square(values[mask]))))

def pilot_demean(values: pilot_FloatArray, mask: pilot_BoolArray) -> pilot_FloatArray:
    return values - float(np.mean(values[mask]))

def _window_mask(frequency: pilot_FloatArray, valid: pilot_BoolArray, center_hz: float) -> pilot_BoolArray:
    return valid & (frequency >= center_hz * 2.0 ** (-1.0 / 24.0)) & (frequency <= center_hz * 2.0 ** (1.0 / 24.0))

def _bootstrap_effects(matrices: Mapping[str, pilot_FloatArray], selected_indices: Mapping[str, NDArray[np.int64]], frequency: pilot_FloatArray, valid: pilot_BoolArray, primary: pilot_BoolArray, *, iterations: int=2000, seed: int=260826) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    output: dict[str, Any] = {}
    for condition in ('I75A', 'I50PA'):
        shape_rms = np.empty(iterations)
        raw_windows = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        shape_windows = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        raw_points = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        shape_points = {center: np.empty(iterations) for center in P04T2_LANDMARKS_HZ}
        for index in range(iterations):
            reps: dict[str, FloatArray] = {}
            for key in P04T2_CONDITIONS:
                subset = matrices[key][selected_indices[key]]
                draw = rng.integers(0, subset.shape[0], subset.shape[0])
                reps[key] = np.median(subset[draw], axis=0)
            baseline = np.median(np.vstack([reps['BASE0'], reps['BASE1']]), axis=0)
            raw = reps[condition] - baseline
            shape = pilot_demean(raw, primary)
            shape_rms[index] = pilot_rms(shape, primary)
            for center in P04T2_LANDMARKS_HZ:
                mask = _window_mask(frequency, valid, center)
                point_index = int(np.argmin(np.abs(frequency - center)))
                raw_windows[center][index] = float(np.mean(raw[mask]))
                shape_windows[center][index] = float(np.mean(shape[mask]))
                raw_points[center][index] = float(raw[point_index])
                shape_points[center][index] = float(shape[point_index])
        output[condition] = {'iterations': iterations, 'seed': seed, 'shape_primary_rms_db_ci95': np.percentile(shape_rms, [2.5, 97.5]).tolist(), 'landmarks': {str(center): {'raw_db_ci95': np.percentile(raw_windows[center], [2.5, 97.5]).tolist(), 'shape_db_ci95': np.percentile(shape_windows[center], [2.5, 97.5]).tolist(), 'point_raw_db_ci95': np.percentile(raw_points[center], [2.5, 97.5]).tolist(), 'point_shape_db_ci95': np.percentile(shape_points[center], [2.5, 97.5]).tolist(), 'raw_positive_probability': float(np.mean(raw_windows[center] > 0.0)), 'shape_positive_probability': float(np.mean(shape_windows[center] > 0.0))} for center in P04T2_LANDMARKS_HZ}}
    return output


# P04t4 return control analysis

return_control_FloatArray = NDArray[np.float64]

return_control_BoolArray = NDArray[np.bool_]

P04T4_CONDITIONS = ('BASEC', 'I50PC', 'BASER')

SUP0_HISTORICAL_CONT_P95_DB = 0.8793

P04_LOCAL_REFERENCE_DB = 1.396

MIN_EFFECT_TO_RETURN_RATIO = 2.0

BOOTSTRAP_ITERATIONS = 2000

BOOTSTRAP_SEED = 260826

def return_control_rms(values: return_control_FloatArray, mask: return_control_BoolArray) -> float:
    return float(np.sqrt(np.mean(np.square(values[mask]))))

def return_control_demean(values: return_control_FloatArray, mask: return_control_BoolArray) -> return_control_FloatArray:
    return values - float(np.mean(values[mask]))

def _correlation(left: return_control_FloatArray, right: return_control_FloatArray) -> float:
    if np.std(left) <= 1e-12 or np.std(right) <= 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])

def _cosine(left: return_control_FloatArray, right: return_control_FloatArray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return 0.0 if denominator <= 1e-12 else float(np.dot(left, right) / denominator)

def compute_return_control_metrics(representatives: Mapping[str, return_control_FloatArray], primary_mask: return_control_BoolArray) -> dict[str, float]:
    base_c = np.asarray(representatives['BASEC'], dtype=np.float64)
    intervention = np.asarray(representatives['I50PC'], dtype=np.float64)
    base_r = np.asarray(representatives['BASER'], dtype=np.float64)
    mask = np.asarray(primary_mask, dtype=bool)
    if base_c.shape != intervention.shape or base_c.shape != base_r.shape or base_c.shape != mask.shape:
        raise ValueError('representative curve shapes differ')
    bracket = 0.5 * (base_c + base_r)
    return_raw = base_r - base_c
    return_shape = return_control_demean(return_raw, mask)
    pre_raw = intervention - base_c
    post_raw = intervention - base_r
    bracket_raw = intervention - bracket
    pre_shape = return_control_demean(pre_raw, mask)
    post_shape = return_control_demean(post_raw, mask)
    bracket_shape = return_control_demean(bracket_raw, mask)
    return_shape_rms = return_control_rms(return_shape, mask)
    intervention_shape_rms = return_control_rms(bracket_shape, mask)
    return {'base_return_raw_rms_db': return_control_rms(return_raw, mask), 'base_return_shape_rms_db': return_shape_rms, 'i50p_vs_precursor_raw_rms_db': return_control_rms(pre_raw, mask), 'i50p_vs_precursor_shape_rms_db': return_control_rms(pre_shape, mask), 'i50p_vs_return_raw_rms_db': return_control_rms(post_raw, mask), 'i50p_vs_return_shape_rms_db': return_control_rms(post_shape, mask), 'i50p_bracket_raw_rms_db': return_control_rms(bracket_raw, mask), 'i50p_bracket_shape_rms_db': intervention_shape_rms, 'effect_to_return_shape_ratio': intervention_shape_rms / return_shape_rms if return_shape_rms > 1e-12 else float('inf'), 'pre_post_effect_pearson': _correlation(pre_shape[mask], post_shape[mask]), 'pre_post_effect_cosine': _cosine(pre_shape[mask], post_shape[mask]), 'base_return_below_historical_sup0_cont_p95': float(return_shape_rms <= SUP0_HISTORICAL_CONT_P95_DB), 'i50p_effect_above_p04_local_reference': float(intervention_shape_rms >= P04_LOCAL_REFERENCE_DB)}

def _bootstrap_metrics(matrices: Mapping[str, return_control_FloatArray], selected_indices: Mapping[str, NDArray[np.int64]], primary: return_control_BoolArray, *, iterations: int=BOOTSTRAP_ITERATIONS, seed: int=BOOTSTRAP_SEED) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    keys = ['base_return_raw_rms_db', 'base_return_shape_rms_db', 'i50p_bracket_raw_rms_db', 'i50p_bracket_shape_rms_db', 'effect_to_return_shape_ratio', 'pre_post_effect_pearson', 'pre_post_effect_cosine']
    values = {key: np.empty(iterations, dtype=np.float64) for key in keys}
    for index in range(iterations):
        representatives: dict[str, FloatArray] = {}
        for condition in P04T4_CONDITIONS:
            subset = matrices[condition][selected_indices[condition]]
            draw = rng.integers(0, subset.shape[0], subset.shape[0])
            representatives[condition] = np.median(subset[draw], axis=0)
        metrics = compute_return_control_metrics(representatives, primary)
        for key in keys:
            value = metrics[key]
            values[key][index] = 1000000000.0 if not np.isfinite(value) else value
    return {'iterations': iterations, 'seed': seed, 'unit': 'complete repeat curve within frozen condition', 'frequency_bootstrap': False, 'ci95': {key: np.percentile(value, [2.5, 97.5]).tolist() for key, value in values.items()}, 'effect_gt_return_probability': float(np.mean(values['i50p_bracket_shape_rms_db'] > values['base_return_shape_rms_db'])), 'effect_gt_2x_return_probability': float(np.mean(values['effect_to_return_shape_ratio'] >= MIN_EFFECT_TO_RETURN_RATIO))}


def paper_example():
    """Recompute insert distances and return control using archived selected flags.

    BASE0/BASE1 bracket the pilot; I75A/I50PA identify its moderate/strong inserts.
    BASEC/I50PC/BASER are the later return sequence.
    All 42 recordings remain available; four of six per condition were selected
    in the archived analysis. The functions above preserve its original seeds.
    """
    frequency, valid, curves, rows = load_measurements(DATA_DIR)
    primary = valid & (frequency >= 200) & (frequency <= 4000)
    selected = [r for r in rows if r['analysis_included'] == 'true']
    reps = {condition: np.median(np.stack([curves[r['sample_id']] for r in selected if r['condition'] == condition]), axis=0) for condition in sorted({r['condition'] for r in selected})}
    baseline = (reps['BASE0'] + reps['BASE1']) / 2.0
    pilot = {condition: pilot_rms(pilot_demean(reps[condition] - baseline, primary), primary) for condition in ('I75A', 'I50PA')}
    with (DATA_DIR / 'simulated_volume_intervention/branch_tracking.csv').open(encoding='utf-8-sig', newline='') as handle:
        branches = [r for r in csv.DictReader(handle) if r['tracked_candidate_branch'].lower() == 'true']
    return {'recorded_curves': len(curves), 'pilot_shape_distances_db': pilot,
            'return_control': compute_return_control_metrics(reps, primary),
            'archived_simulated_branch_centres_hz': {r['state']: float(r['refined_frequency_hz']) for r in branches}}

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))


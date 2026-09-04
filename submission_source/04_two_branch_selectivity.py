"""Two branch selectivity.
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
import numpy as np
from measurement_io import load_measurements

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "04_two_branch_selectivity"


# Trans1 two port physical analysis

FloatArray = NDArray[np.float64]

BoolArray = NDArray[np.bool_]

CONDITIONS = ('N', 'S', 'NRETURN')

WINDOW_PAIRS = {'frozen_module_targets': (1850.0, 3800.0)}

def directional_contrast(north: FloatArray, south: FloatArray, low_mask: BoolArray, high_mask: BoolArray) -> float:
    """Return (N_low-N_high) - (S_low-S_high), in dB."""
    return float(np.mean(north[low_mask]) - np.mean(north[high_mask]) - (np.mean(south[low_mask]) - np.mean(south[high_mask])))

def _demean(values: FloatArray, mask: BoolArray) -> FloatArray:
    return values - float(np.mean(values[mask]))

def _rms(values: FloatArray, mask: BoolArray) -> float:
    return float(np.sqrt(np.mean(np.square(values[mask]))))

def _window_mask(frequency: FloatArray, valid: BoolArray, center_hz: float) -> BoolArray:
    return valid & (frequency >= center_hz * 2 ** (-1 / 6)) & (frequency <= center_hz * 2 ** (1 / 6))

def _correlation(a: FloatArray, b: FloatArray) -> float:
    if np.std(a) == 0.0 or np.std(b) == 0.0:
        return float('nan')
    return float(np.corrcoef(a, b)[0, 1])

def _bootstrap(matrices: Mapping[str, FloatArray], frequency: FloatArray, valid: BoolArray, primary: BoolArray, *, iterations: int=2000, seed: int=270827) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    direction_rms = np.empty(iterations)
    return_direction_rms = np.empty(iterations)
    drift_rms = np.empty(iterations)
    effect_corr = np.empty(iterations)
    window_values: dict[str, dict[str, NDArray[np.float64]]] = {}
    for pair_name, (low, high) in WINDOW_PAIRS.items():
        window_values[pair_name] = {'contrast': np.empty(iterations), 'return_contrast': np.empty(iterations), 'low_n_minus_s': np.empty(iterations), 'high_n_minus_s': np.empty(iterations)}
    for index in range(iterations):
        reps: dict[str, FloatArray] = {}
        for condition in CONDITIONS:
            matrix = matrices[condition]
            draw = rng.integers(0, matrix.shape[0], matrix.shape[0])
            reps[condition] = np.median(matrix[draw], axis=0)
        direction = _demean(reps['N'] - reps['S'], primary)
        return_direction = _demean(reps['NRETURN'] - reps['S'], primary)
        drift = _demean(reps['NRETURN'] - reps['N'], primary)
        direction_rms[index] = _rms(direction, primary)
        return_direction_rms[index] = _rms(return_direction, primary)
        drift_rms[index] = _rms(drift, primary)
        effect_corr[index] = _correlation(direction[primary], return_direction[primary])
        for pair_name, (low, high) in WINDOW_PAIRS.items():
            low_mask = _window_mask(frequency, valid, low)
            high_mask = _window_mask(frequency, valid, high)
            values = window_values[pair_name]
            values['contrast'][index] = directional_contrast(reps['N'], reps['S'], low_mask, high_mask)
            values['return_contrast'][index] = directional_contrast(reps['NRETURN'], reps['S'], low_mask, high_mask)
            values['low_n_minus_s'][index] = float(np.mean((reps['N'] - reps['S'])[low_mask]))
            values['high_n_minus_s'][index] = float(np.mean((reps['N'] - reps['S'])[high_mask]))
    return {'iterations': iterations, 'seed': seed, 'direction_effect_rms_db_ci95': np.percentile(direction_rms, [2.5, 97.5]).tolist(), 'return_direction_effect_rms_db_ci95': np.percentile(return_direction_rms, [2.5, 97.5]).tolist(), 'return_drift_rms_db_ci95': np.percentile(drift_rms, [2.5, 97.5]).tolist(), 'return_effect_correlation_ci95': np.nanpercentile(effect_corr, [2.5, 97.5]).tolist(), 'window_pairs': {pair_name: {key + '_ci95': np.percentile(array, [2.5, 97.5]).tolist() for key, array in values.items()} for pair_name, values in window_values.items()}}


def paper_example():
    """Recompute N/S/NRETURN contrast from all 15 curves, with frozen bootstrap.

    N and S each have six technical repeats; NRETURN has three. Intervals resample
    complete curves within these groups, conditional on the one closed assembly.
    """
    frequency, valid, curves, rows = load_measurements(DATA_DIR)
    primary = valid & (frequency >= 200) & (frequency <= 4000)
    matrices = {condition: np.stack([curves[r['sample_id']] for r in rows if r['condition'] == condition]) for condition in CONDITIONS}
    reps = {key: np.median(value, axis=0) for key, value in matrices.items()}
    north_south = _demean(reps['N'] - reps['S'], primary)
    returned = _demean(reps['NRETURN'] - reps['S'], primary)
    drift = _demean(reps['NRETURN'] - reps['N'], primary)
    pairwise = [_rms(_demean(a - b, primary), primary) for matrix in matrices.values() for i, a in enumerate(matrix) for b in matrix[i + 1:]]
    floor = float(np.percentile(pairwise, 95))
    low, high = (_window_mask(frequency, valid, f) for f in WINDOW_PAIRS['frozen_module_targets'])
    return {'recorded_curves': len(curves), 'north_south_db': _rms(north_south, primary), 'within_state_p95_db': floor,
            'readability_ratio': _rms(north_south, primary) / floor, 'return_drift_db': _rms(drift, primary),
            'returned_north_south_db': _rms(returned, primary), 'return_correlation': _correlation(north_south[primary], returned[primary]),
            'low_high_contrast_db': directional_contrast(reps['N'], reps['S'], low, high),
            'bootstrap': _bootstrap(matrices, frequency, valid, primary)}

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))


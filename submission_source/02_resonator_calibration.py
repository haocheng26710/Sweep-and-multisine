"""Resonator calibration.
Numerical functions and frozen parameters used in Draft 18.
Run this script to calculate the bounded example from its supplied datasets.
Additional original numerical functions are available for explicit use.
Requirements: Python 3.11+ and NumPy; SciPy/scikit-learn where imported.
"""
from __future__ import annotations
from pathlib import Path
import json
import csv
from dataclasses import dataclass
from numpy.typing import NDArray
from scipy.stats import spearmanr
from typing import Any
from typing import Mapping
from typing import Sequence
import itertools
import math
import numpy as np
from measurement_io import load_measurements

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "02_resonator_calibration"


# Cross module

def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding='utf-8-sig')))

def read_complex(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows = read_csv(path)
    return (np.asarray([float(row['frequency_hz']) for row in rows]), np.asarray([complex(float(row['real']), float(row['imag'])) for row in rows]))

def interpolate_crossing(f1: float, y1: float, f2: float, y2: float, level: float) -> float:
    x1, x2 = (math.log(f1), math.log(f2))
    z1, z2, target = (math.log(y1), math.log(y2), math.log(level))
    if z2 == z1:
        return math.exp((x1 + x2) / 2)
    return math.exp(x1 + (target - z1) * (x2 - x1) / (z2 - z1))

def energy_centre(frequency: np.ndarray, energy: np.ndarray, target_hz: float) -> dict[str, Any]:
    lower, upper = (target_hz * 2 ** (-1 / 6), target_hz * 2 ** (1 / 6))
    local_indices = np.flatnonzero((frequency >= lower) & (frequency <= upper) & np.isfinite(energy) & (energy > 0))
    if local_indices.size < 3:
        return {'identifiable': False, 'reason': 'insufficient_target_window_bins', 'sampled_centre_hz': None, 'centre_hz': None, 'bandwidth_hz': None, 'Q': None, 'window_low_hz': lower, 'window_high_hz': upper}
    local_peak = int(np.argmax(energy[local_indices]))
    peak_index = int(local_indices[local_peak])
    sampled = float(frequency[peak_index])
    if local_peak in (0, local_indices.size - 1):
        return {'identifiable': False, 'reason': 'boundary_maximum', 'sampled_centre_hz': sampled, 'centre_hz': None, 'bandwidth_hz': None, 'Q': None, 'window_low_hz': lower, 'window_high_hz': upper}
    x = np.log(frequency[peak_index - 1:peak_index + 2])
    y = np.log(energy[peak_index - 1:peak_index + 2])
    a, b, c = np.polyfit(x, y, 2)
    xp = -b / (2 * a) if a != 0 else float('nan')
    if not (a < 0 and x[0] <= xp <= x[-1] and np.isfinite(xp)):
        return {'identifiable': False, 'reason': 'invalid_quadratic_refinement', 'sampled_centre_hz': sampled, 'centre_hz': None, 'bandwidth_hz': None, 'Q': None, 'window_low_hz': lower, 'window_high_hz': upper}
    centre = float(math.exp(xp))
    peak_energy = float(math.exp(a * xp * xp + b * xp + c))
    half = peak_energy / 2.0
    low = high = None
    for index in range(peak_index - 1, -1, -1):
        if energy[index] <= half < energy[index + 1]:
            low = interpolate_crossing(float(frequency[index]), float(energy[index]), float(frequency[index + 1]), float(energy[index + 1]), half)
            break
    for index in range(peak_index, len(frequency) - 1):
        if energy[index] >= half > energy[index + 1]:
            high = interpolate_crossing(float(frequency[index]), float(energy[index]), float(frequency[index + 1]), float(energy[index + 1]), half)
            break
    bandwidth = float(high - low) if low is not None and high is not None and (high > low) else None
    return {'identifiable': True, 'reason': 'interior_log_quadratic', 'sampled_centre_hz': sampled, 'centre_hz': centre, 'refined_peak_energy_J': peak_energy, 'half_power_low_hz': low, 'half_power_high_hz': high, 'bandwidth_hz': bandwidth, 'Q': centre / bandwidth if bandwidth else None, 'window_low_hz': lower, 'window_high_hz': upper}

def local_residual(frequency: np.ndarray, values: np.ndarray) -> np.ndarray:
    x = np.log2(frequency)
    edge_count = max(1, int(math.ceil(values.size * 0.15)))
    edge = np.r_[0:edge_count, values.size - edge_count:values.size]
    return values - np.polyval(np.polyfit(x[edge], values[edge], 1), x)

def transfer_feature(frequency: np.ndarray, values: np.ndarray, target: float) -> dict[str, Any]:
    mask = np.isfinite(values) & (frequency >= target * 2 ** (-1 / 6)) & (frequency <= target * 2 ** (1 / 6))
    local_f, residual = (frequency[mask], local_residual(frequency[mask], values[mask]))
    index = int(np.argmax(np.abs(residual)))
    signed = float(residual[index])
    threshold = abs(signed) / math.sqrt(2)
    above = np.flatnonzero(np.abs(residual) >= threshold)
    bandwidth = float(local_f[above[-1]] - local_f[above[0]]) if above.size > 1 else 0.0
    return {'feature_hz': float(local_f[index]), 'signed_effect_db': signed, 'absolute_effect_db': abs(signed), 'polarity': 'peak' if signed >= 0 else 'notch', 'window_rms_db': float(np.sqrt(np.mean(residual ** 2))), 'bandwidth_hz': bandwidth, 'Q': float(local_f[index] / bandwidth) if bandwidth else None, 'at_window_boundary': bool(index in (0, len(local_f) - 1))}

def shape_metrics(simulated: np.ndarray, experimental: np.ndarray, frequency: np.ndarray) -> dict[str, float]:
    mask = (frequency >= 800) & (frequency <= 5000) & np.isfinite(simulated) & np.isfinite(experimental)
    sim, exp = (simulated[mask], experimental[mask])
    sim_dm, exp_dm = (sim - np.mean(sim), exp - np.mean(exp))
    pearson = float(np.corrcoef(sim_dm, exp_dm)[0, 1])
    spearman = float(spearmanr(sim_dm, exp_dm).statistic)
    denominator = float(np.linalg.norm(sim_dm) * np.linalg.norm(exp_dm))
    cosine = float(np.dot(sim_dm, exp_dm) / denominator) if denominator > 0 else float('nan')
    return {'relative_spectrum_rmse_db': float(np.sqrt(np.mean((sim - exp) ** 2))), 'demeaned_shape_rmse_db': float(np.sqrt(np.mean((sim_dm - exp_dm) ** 2))), 'demeaned_pearson': pearson, 'spearman': spearman, 'demeaned_cosine': cosine, 'comparison_bins': int(mask.sum())}


# Isolated resonator

def refined_peak(f: np.ndarray, z: np.ndarray) -> dict[str, float]:
    mag = np.abs(z)
    i = int(np.argmax(mag))
    if i == 0 or i == len(f) - 1:
        raise RuntimeError('Peak at sweep boundary')
    x = np.log(f[i - 1:i + 2])
    y = np.log(mag[i - 1:i + 2])
    a, b, c = np.polyfit(x, y, 2)
    xp = -b / (2 * a)
    fp = float(np.exp(xp))
    mp = float(np.exp(a * xp * xp + b * xp + c))
    phase = np.unwrap(np.angle(z))
    pp = float(np.degrees(np.interp(fp, f, phase)))
    target = mp / math.sqrt(2)
    left = None
    for j in range(i - 1, -1, -1):
        if mag[j] <= target <= mag[j + 1]:
            left = float(np.interp(target, [mag[j], mag[j + 1]], [f[j], f[j + 1]]))
            break
    right = None
    for j in range(i, len(f) - 1):
        if mag[j] >= target >= mag[j + 1]:
            right = float(np.interp(target, [mag[j + 1], mag[j]], [f[j + 1], f[j]]))
            break
    if left is None or right is None:
        raise RuntimeError('Half-power crossings not bracketed')
    bw = right - left
    return {'centre_hz': fp, 'peak_magnitude_pa_per_pa': mp, 'peak_phase_deg': pp, 'half_power_low_hz': left, 'half_power_high_hz': right, 'bandwidth_hz': bw, 'Q': fp / bw}


# V25 single module analysis

single_resonator_FloatArray = NDArray[np.float64]

_CONDITIONS = ('base', *(f'HR{index:02d}' for index in range(1, 9)))

_MODULES = tuple((condition for condition in _CONDITIONS if condition != 'base'))

_TARGETS_HZ = {'HR01': 1200.0, 'HR02': 1500.0, 'HR03': 1850.0, 'HR04': 2250.0, 'HR05': 2700.0, 'HR06': 3200.0, 'HR07': 3800.0, 'HR08': 4500.0}

_PREDICTED_HZ = {'HR01': 1201.7, 'HR02': 1501.7, 'HR03': 1853.1, 'HR04': 2254.5, 'HR05': 2708.0, 'HR06': 3212.9, 'HR07': 3820.7, 'HR08': 4527.3}

class V25S1InputError(ValueError):
    """Raised when V2.5 S1 identity, provenance or analysis contracts fail."""

def single_resonator_rms(values: single_resonator_FloatArray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))

def _local_residual(frequency: single_resonator_FloatArray, values: single_resonator_FloatArray) -> single_resonator_FloatArray:
    x = np.log2(frequency)
    if values.size < 3:
        return values - float(np.mean(values))
    edge_count = max(1, int(math.ceil(values.size * 0.15)))
    edge_indices = np.r_[0:edge_count, values.size - edge_count:values.size]
    coefficients = np.polyfit(x[edge_indices], values[edge_indices], deg=1)
    return values - np.polyval(coefficients, x)

def extract_target_feature(frequency_hz: single_resonator_FloatArray, block_deltas: Mapping[str, single_resonator_FloatArray], *, target_hz: float, local_floor_db: float) -> dict[str, Any]:
    """Extract a target-driven local peak/notch after edge-linear detrending."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    lower = target_hz * 2.0 ** (-1.0 / 6.0)
    upper = target_hz * 2.0 ** (1.0 / 6.0)
    mask = (frequency >= lower) & (frequency <= upper)
    if np.count_nonzero(mask) < 5:
        raise V25S1InputError(f'insufficient target-window bins around {target_hz} Hz')
    local_frequency = frequency[mask]
    residuals = {block: _local_residual(local_frequency, np.asarray(delta)[mask]) for block, delta in block_deltas.items()}
    combined = np.mean(np.vstack(list(residuals.values())), axis=0)
    peak_index = int(np.argmax(np.abs(combined)))
    contrast = float(combined[peak_index])
    polarity = 'peak' if contrast >= 0.0 else 'notch'
    orientation = 1.0 if contrast >= 0.0 else -1.0
    oriented = orientation * combined
    threshold = abs(contrast) / 2.0
    left = peak_index
    right = peak_index
    while left > 0 and oriented[left - 1] >= threshold:
        left -= 1
    while right + 1 < oriented.size and oriented[right + 1] >= threshold:
        right += 1
    bandwidth = float(local_frequency[right] - local_frequency[left])
    effective_q = float(local_frequency[peak_index] / bandwidth) if bandwidth > 0.0 else float('nan')
    block_frequency: dict[str, float] = {}
    block_contrast: dict[str, float] = {}
    block_effect: dict[str, float] = {}
    for block, residual in residuals.items():
        index = int(np.argmax(np.abs(residual)))
        block_frequency[block] = float(local_frequency[index])
        block_contrast[block] = float(residual[index])
        block_effect[block] = single_resonator_rms(residual)
    signs = [int(np.sign(value)) for value in block_contrast.values() if value != 0.0]
    sign_consistent = len(signs) == len(block_contrast) and len(set(signs)) == 1
    frequencies = list(block_frequency.values())
    frequency_consistent = max(frequencies) / min(frequencies) <= 2.0 ** (1.0 / 12.0)
    measured = float(local_frequency[peak_index])
    return {'target_window_low_hz': lower, 'target_window_high_hz': upper, 'measured_feature_hz': measured, 'frequency_error_hz': measured - target_hz, 'frequency_error_percent': 100.0 * (measured / target_hz - 1.0), 'frequency_error_octaves': math.log2(measured / target_hz), 'polarity': polarity, 'signed_contrast_db': contrast, 'absolute_contrast_db': abs(contrast), 'contrast_bandwidth_hz': bandwidth, 'effective_q': effective_q, 'at_search_boundary': peak_index in {0, 1, combined.size - 2, combined.size - 1}, 'block1_feature_hz': block_frequency.get('B01', float('nan')), 'block2_feature_hz': block_frequency.get('B02', float('nan')), 'block1_signed_contrast_db': block_contrast.get('B01', float('nan')), 'block2_signed_contrast_db': block_contrast.get('B02', float('nan')), 'block1_window_rms_db': block_effect.get('B01', float('nan')), 'block2_window_rms_db': block_effect.get('B02', float('nan')), 'local_base_technical_p95_db': local_floor_db, 'block_sign_consistent': sign_consistent, 'block_frequency_consistent': frequency_consistent, 'both_blocks_effect_above_floor': all((value > local_floor_db for value in block_effect.values()))}


# V25 three stage analysis

calibration_FloatArray = NDArray[np.float64]

BoolArray = NDArray[np.bool_]

ANGLES = (0, 90, 180, 270)

ARRAY_CONFIGURATIONS = ('U4SYM', 'U4HR')

S3_MODULE_BY_ANGLE = {0: 'HR01', 90: 'HR03', 180: 'HR05', 270: 'HR07'}

S3_MODULES = tuple((S3_MODULE_BY_ANGLE[angle] for angle in ANGLES))

class V25JointInputError(ValueError):
    """Raised when joint V2.5 identity, provenance, or analysis rules fail."""

@dataclass(frozen=True, slots=True)
class RepeatSelection:
    selected_sample_ids: tuple[str, ...]
    dropped_sample_id: str
    distances_db: Mapping[str, float]

def _finite_mask(curves: Mapping[str, calibration_FloatArray], frequency: calibration_FloatArray, lower: float, upper: float) -> BoolArray:
    finite = np.logical_and.reduce([np.isfinite(curve) for curve in curves.values()])
    return finite & (frequency >= lower) & (frequency <= upper)

def calibration_rms(values: calibration_FloatArray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))

def _demean(values: calibration_FloatArray) -> calibration_FloatArray:
    return values - float(np.mean(values))

def select_farthest_repeat(curves: Mapping[str, calibration_FloatArray], frequency: calibration_FloatArray, *, keep_count: int) -> RepeatSelection:
    if len(curves) != keep_count + 1:
        raise V25JointInputError(f'selection requires exactly keep_count+1 curves; got {len(curves)}')
    mask = _finite_mask(curves, frequency, 200.0, 4000.0)
    center = np.median(np.vstack(list(curves.values())), axis=0)
    distances = {sample_id: calibration_rms((curve - center)[mask]) for sample_id, curve in curves.items()}
    dropped = max(sorted(distances), key=lambda sample_id: distances[sample_id])
    selected = tuple(sorted((sample_id for sample_id in curves if sample_id != dropped)))
    return RepeatSelection(selected, dropped, distances)

def direction_code_score(matrix: calibration_FloatArray) -> dict[str, Any]:
    values = np.asarray(matrix, dtype=np.float64)
    if values.shape != (4, 4):
        raise V25JointInputError('direction code matrix must be 4x4')
    diagonal = np.diag(values)
    off = values[~np.eye(4, dtype=bool)]
    score = float(np.mean(diagonal) - np.mean(off))
    top1 = sum((int(np.argmax(values[:, column])) == column for column in range(4)))
    top2 = sum((column in np.argsort(values[:, column])[-2:] for column in range(4)))
    permutation_scores: list[float] = []
    for permutation in itertools.permutations(range(4)):
        selected = np.asarray([values[permutation[column], column] for column in range(4)])
        remainder = np.asarray([values[row, column] for column in range(4) for row in range(4) if row != permutation[column]])
        permutation_scores.append(float(np.mean(selected) - np.mean(remainder)))
    p_value = sum((value >= score - 1e-12 for value in permutation_scores)) / 24.0
    return {'score_db': score, 'diagonal_mean_db': float(np.mean(diagonal)), 'off_diagonal_mean_db': float(np.mean(off)), 'correct_direction_top1_count': int(top1), 'correct_direction_top2_count': int(top2), 'exact_mapping_permutation_p': float(p_value)}

def _extract_local_feature(frequency: calibration_FloatArray, delta: calibration_FloatArray, *, target_hz: float) -> dict[str, Any]:
    mask = np.isfinite(delta) & (frequency >= target_hz * 2.0 ** (-1.0 / 6.0)) & (frequency <= target_hz * 2.0 ** (1.0 / 6.0))
    local_frequency = frequency[mask]
    residual = _local_residual(local_frequency, delta[mask])
    peak_index = int(np.argmax(np.abs(residual)))
    signed = float(residual[peak_index])
    threshold = abs(signed) / math.sqrt(2.0)
    above = np.flatnonzero(np.abs(residual) >= threshold)
    bandwidth = float(local_frequency[above[-1]] - local_frequency[above[0]]) if above.size > 1 else 0.0
    return {'measured_feature_hz': float(local_frequency[peak_index]), 'signed_contrast_db': signed, 'absolute_contrast_db': abs(signed), 'polarity': 'peak' if signed >= 0.0 else 'notch', 'target_window_rms_db': calibration_rms(residual), 'contrast_bandwidth_hz': bandwidth, 'effective_q': float(local_frequency[peak_index] / bandwidth) if bandwidth > 0.0 else None, 'at_search_boundary': peak_index in (0, residual.size - 1)}

def _local_pair_floor(curves: Mapping[str, calibration_FloatArray], sample_ids: Sequence[str], frequency: calibration_FloatArray, target_hz: float) -> float:
    mask = (frequency >= target_hz * 2.0 ** (-1.0 / 6.0)) & (frequency <= target_hz * 2.0 ** (1.0 / 6.0))
    values = [calibration_rms(_local_residual(frequency[mask], (curves[left] - curves[right])[mask])) for left, right in itertools.combinations(sample_ids, 2)]
    return float(np.quantile(values, 0.95))

def _s1_analysis(curves: Mapping[str, calibration_FloatArray], frequency: calibration_FloatArray, member_ids: Mapping[str, Sequence[str]], selections: Mapping[str, RepeatSelection], *, random_state: int, bootstrap_iterations: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, calibration_FloatArray], dict[str, float], dict[str, int]]:
    selected_representatives = {condition: np.median(np.vstack([curves[sample_id] for sample_id in selections[condition].selected_sample_ids]), axis=0) for condition in _CONDITIONS}
    all_representatives = {condition: np.median(np.vstack([curves[sample_id] for sample_id in member_ids[condition]]), axis=0) for condition in _CONDITIONS}
    signatures = {module: selected_representatives[module] - selected_representatives['base'] for module in _MODULES}
    feature_rows: list[dict[str, Any]] = []
    centers: dict[str, float] = {}
    polarity_signs: dict[str, int] = {}
    for module_index, module in enumerate(_MODULES):
        target = float(_TARGETS_HZ[module])
        selected_ids = selections[module].selected_sample_ids
        base_ids = selections['base'].selected_sample_ids
        delta = signatures[module]
        point = _extract_local_feature(frequency, delta, target_hz=target)
        all_delta = all_representatives[module] - all_representatives['base']
        all_point = _extract_local_feature(frequency, all_delta, target_hz=target)
        local_floor = _local_pair_floor(curves, base_ids, frequency, target)
        all_local_floor = _local_pair_floor(curves, member_ids['base'], frequency, target)
        rng = np.random.default_rng(random_state + module_index * 100)
        boot_frequency: list[float] = []
        boot_contrast: list[float] = []
        boot_rms: list[float] = []
        for _ in range(bootstrap_iterations):
            module_sample = rng.choice(selected_ids, size=len(selected_ids), replace=True)
            base_sample = rng.choice(base_ids, size=len(base_ids), replace=True)
            bootstrap_delta = np.median(np.vstack([curves[str(item)] for item in module_sample]), axis=0) - np.median(np.vstack([curves[str(item)] for item in base_sample]), axis=0)
            value = _extract_local_feature(frequency, bootstrap_delta, target_hz=target)
            boot_frequency.append(float(value['measured_feature_hz']))
            boot_contrast.append(float(value['signed_contrast_db']))
            boot_rms.append(float(value['target_window_rms_db']))
        frequency_ci = np.percentile(boot_frequency, [2.5, 97.5])
        contrast_ci = np.percentile(boot_contrast, [2.5, 97.5])
        rms_ci = np.percentile(boot_rms, [2.5, 97.5])
        point_sign = 1 if float(point['signed_contrast_db']) >= 0.0 else -1
        polarity_consistency = float(np.mean(np.sign(np.asarray(boot_contrast)) == point_sign))
        contrast_ci_excludes_zero = bool(float(contrast_ci[0]) > 0.0 or float(contrast_ci[1]) < 0.0)
        stable = bool(float(point['target_window_rms_db']) > local_floor and contrast_ci_excludes_zero and (polarity_consistency >= 0.8) and (not bool(point['at_search_boundary'])))
        centers[module] = float(point['measured_feature_hz'])
        polarity_signs[module] = point_sign
        feature_rows.append({'module_id': module, 'target_hz': target, 'package_predicted_hz': float(_PREDICTED_HZ[module]), **point, 'frequency_error_percent': (float(point['measured_feature_hz']) / target - 1.0) * 100.0, 'selected_base_local_p95_db': local_floor, 'effect_to_selected_local_floor_ratio': float(point['target_window_rms_db']) / local_floor, 'bootstrap_feature_hz_ci95_low': float(frequency_ci[0]), 'bootstrap_feature_hz_ci95_high': float(frequency_ci[1]), 'bootstrap_signed_contrast_ci95_low_db': float(contrast_ci[0]), 'bootstrap_signed_contrast_ci95_high_db': float(contrast_ci[1]), 'bootstrap_target_window_rms_ci95_low_db': float(rms_ci[0]), 'bootstrap_target_window_rms_ci95_high_db': float(rms_ci[1]), 'bootstrap_polarity_consistency': polarity_consistency, 'bootstrap_iterations': bootstrap_iterations, 'stable_single_campaign_signature': stable, 'all6_measured_feature_hz': all_point['measured_feature_hz'], 'all6_signed_contrast_db': all_point['signed_contrast_db'], 'all6_target_window_rms_db': all_point['target_window_rms_db'], 'all6_base_local_p95_db': all_local_floor, 'selection_sensitivity_feature_shift_hz': float(point['measured_feature_hz']) - float(all_point['measured_feature_hz']), 'selection_sensitivity_contrast_shift_db': float(point['signed_contrast_db']) - float(all_point['signed_contrast_db']), 'claim_scope': 'single_campaign_repeat_bootstrap_no_independent_block'})
    channel_rows: list[dict[str, Any]] = []
    for module in _MODULES:
        effects: list[tuple[str, float]] = []
        pending: list[dict[str, Any]] = []
        for channel in _MODULES:
            target = float(_TARGETS_HZ[channel])
            mask = (frequency >= target * 2.0 ** (-1.0 / 6.0)) & (frequency <= target * 2.0 ** (1.0 / 6.0))
            effect = calibration_rms(_local_residual(frequency[mask], signatures[module][mask]))
            floor = _local_pair_floor(curves, selections['base'].selected_sample_ids, frequency, target)
            effects.append((channel, effect))
            pending.append({'module_id': module, 'target_channel': channel, 'target_hz': target, 'window_rms_contrast_db': effect, 'selected_base_local_p95_db': floor, 'effect_to_local_floor_ratio': effect / floor, 'own_target_channel': module == channel})
        ranks = {channel: index + 1 for index, (channel, _) in enumerate(sorted(effects, key=lambda item: item[1], reverse=True))}
        for row in pending:
            row['within_module_effect_rank'] = ranks[str(row['target_channel'])]
            channel_rows.append(row)
    similarity_rows: list[dict[str, Any]] = []
    mask = _finite_mask(signatures, frequency, 800.0, 5000.0)
    for left, right in itertools.combinations(_MODULES, 2):
        a, b = (_demean(signatures[left][mask]), _demean(signatures[right][mask]))
        similarity_rows.append({'module_a': left, 'module_b': right, 'pearson_800_5000hz': float(np.corrcoef(a, b)[0, 1]), 'cosine_800_5000hz': float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))})
    return (feature_rows, channel_rows, similarity_rows, signatures, centers, polarity_signs)

def _representatives(curves: Mapping[str, calibration_FloatArray], groups: Mapping[int, Sequence[str]]) -> dict[int, calibration_FloatArray]:
    return {angle: np.median(np.vstack([curves[sample_id] for sample_id in sample_ids]), axis=0) for angle, sample_ids in groups.items()}

def direction_discriminability_spectrum(curves: Mapping[str, calibration_FloatArray], groups: Mapping[int, Sequence[str]]) -> dict[str, calibration_FloatArray]:
    """Return exploratory between/within direction contrast at each frequency.

    The measurement repeat is the sampling unit.  Frequency bins are only a
    visualization axis and are not treated as independent observations.
    """
    if len(groups) < 2 or any((len(sample_ids) < 2 for sample_ids in groups.values())):
        raise V25JointInputError('direction discriminability requires at least two directions and repeats')
    representatives = _representatives(curves, groups)
    direction_stack = np.vstack([representatives[angle] for angle in sorted(groups)])
    grand_mean = np.mean(direction_stack, axis=0)
    between = np.sqrt(np.mean((direction_stack - grand_mean) ** 2, axis=0))
    residuals = np.vstack([curves[sample_id] - representatives[angle] for angle in sorted(groups) for sample_id in groups[angle]])
    within = np.sqrt(np.mean(residuals ** 2, axis=0))
    ratio = np.divide(between, within, out=np.full_like(between, np.nan), where=within > np.finfo(np.float64).eps)
    return {'between_direction_rms_db': between, 'within_direction_rms_db': within, 'between_to_within_ratio': ratio}

def _technical_repeatability(curves: Mapping[str, calibration_FloatArray], frequency: calibration_FloatArray, groups: Mapping[int, Sequence[str]], *, configuration: str, analysis_set: str) -> tuple[list[dict[str, Any]], dict[str, float]]:
    primary = _finite_mask(curves, frequency, 200.0, 4000.0)
    secondary = _finite_mask(curves, frequency, 4000.0, 8000.0)
    rows: list[dict[str, Any]] = []
    pooled_raw: list[float] = []
    pooled_shape: list[float] = []
    pooled_secondary_shape: list[float] = []
    for angle in ANGLES:
        raw_values: list[float] = []
        shape_values: list[float] = []
        secondary_values: list[float] = []
        for left, right in itertools.combinations(groups[angle], 2):
            difference = curves[left] - curves[right]
            raw_values.append(calibration_rms(difference[primary]))
            shape_values.append(calibration_rms(_demean(difference[primary])))
            secondary_values.append(calibration_rms(_demean(difference[secondary])))
        pooled_raw.extend(raw_values)
        pooled_shape.extend(shape_values)
        pooled_secondary_shape.extend(secondary_values)
        rows.append({'configuration': configuration, 'analysis_set': analysis_set, 'direction_deg': angle, 'pair_count': len(raw_values), 'primary_raw_pair_rms_median_db': float(np.median(raw_values)), 'primary_raw_pair_rms_p95_db': float(np.quantile(raw_values, 0.95)), 'primary_raw_pair_rms_max_db': float(np.max(raw_values)), 'primary_shape_pair_rms_median_db': float(np.median(shape_values)), 'primary_shape_pair_rms_p95_db': float(np.quantile(shape_values, 0.95)), 'primary_shape_pair_rms_max_db': float(np.max(shape_values)), 'secondary_shape_pair_rms_median_db': float(np.median(secondary_values)), 'secondary_shape_pair_rms_p95_db': float(np.quantile(secondary_values, 0.95)), 'secondary_shape_pair_rms_max_db': float(np.max(secondary_values))})
    summary = {'primary_raw_p95_db': float(np.quantile(pooled_raw, 0.95)), 'primary_shape_p95_db': float(np.quantile(pooled_shape, 0.95)), 'primary_shape_median_db': float(np.median(pooled_shape)), 'secondary_shape_p95_db': float(np.quantile(pooled_secondary_shape, 0.95)), 'pair_count': len(pooled_shape)}
    return (rows, summary)

def _direction_statistic(curves: Mapping[str, calibration_FloatArray], frequency: calibration_FloatArray, groups: Mapping[int, Sequence[str]]) -> float:
    mask = _finite_mask(curves, frequency, 200.0, 4000.0)
    representatives = _representatives(curves, groups)
    values = [calibration_rms(_demean((representatives[left] - representatives[right])[mask])) for left, right in itertools.combinations(ANGLES, 2)]
    return float(np.median(values))

def _direction_permutation_p(curves: Mapping[str, calibration_FloatArray], frequency: calibration_FloatArray, groups: Mapping[int, Sequence[str]], *, random_state: int, iterations: int) -> float:
    observed = _direction_statistic(curves, frequency, groups)
    sample_ids = [sample_id for angle in ANGLES for sample_id in groups[angle]]
    group_size = len(groups[ANGLES[0]])
    rng = np.random.default_rng(random_state)
    exceeding = 0
    for _ in range(iterations):
        shuffled = list(rng.permutation(sample_ids))
        permuted = {angle: shuffled[index * group_size:(index + 1) * group_size] for index, angle in enumerate(ANGLES)}
        if _direction_statistic(curves, frequency, permuted) >= observed - 1e-12:
            exceeding += 1
    return float((exceeding + 1) / (iterations + 1))

def _direction_channel_matrix(curves: Mapping[str, calibration_FloatArray], frequency: calibration_FloatArray, groups: Mapping[int, Sequence[str]], centers: Mapping[str, float], polarity_signs: Mapping[str, int]) -> calibration_FloatArray:
    representatives = _representatives(curves, groups)
    grand = np.mean(np.vstack([representatives[angle] for angle in ANGLES]), axis=0)
    matrix = np.zeros((4, 4), dtype=np.float64)
    for angle_index, angle in enumerate(ANGLES):
        direction_delta = representatives[angle] - grand
        for module_index, module in enumerate(S3_MODULES):
            center = centers[module]
            mask = (frequency >= center * 2.0 ** (-1.0 / 12.0)) & (frequency <= center * 2.0 ** (1.0 / 12.0))
            signed_shift = float(np.mean(direction_delta[mask]))
            matrix[angle_index, module_index] = polarity_signs[module] * signed_shift
    return matrix

def _bootstrap_code_scores(curves_by_configuration: Mapping[str, Mapping[str, calibration_FloatArray]], frequency: calibration_FloatArray, groups_by_configuration: Mapping[str, Mapping[int, Sequence[str]]], centers: Mapping[str, float], polarity_signs: Mapping[str, int], *, random_state: int, iterations: int) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(random_state)
    scores = {configuration: [] for configuration in ARRAY_CONFIGURATIONS}
    deltas: list[float] = []
    for _ in range(iterations):
        values: dict[str, float] = {}
        for configuration in ARRAY_CONFIGURATIONS:
            groups = groups_by_configuration[configuration]
            sampled = {angle: list(rng.choice(groups[angle], size=len(groups[angle]), replace=True)) for angle in ANGLES}
            matrix = _direction_channel_matrix(curves_by_configuration[configuration], frequency, sampled, centers, polarity_signs)
            value = float(direction_code_score(matrix)['score_db'])
            scores[configuration].append(value)
            values[configuration] = value
        deltas.append(values['U4HR'] - values['U4SYM'])
    return {'U4SYM': tuple((float(item) for item in np.percentile(scores['U4SYM'], [2.5, 97.5]))), 'U4HR': tuple((float(item) for item in np.percentile(scores['U4HR'], [2.5, 97.5]))), 'delta': tuple((float(item) for item in np.percentile(deltas, [2.5, 97.5])))}


def paper_example():
    """Recompute the frozen selected-curve centres and four-direction frequency map.

    All 86 recordings remain available, including curves retained for sensitivity
    analysis. The selected flags are loaded from the archived sample mapping.
    The original _s1_analysis function provides the full 2000-replicate signature
    rule with random_state=250824; this example calculates its point markers.
    """
    frequency, valid, curves, rows = load_measurements(DATA_DIR)
    selected = [r for r in rows if r['analysis_included'] == 'true']
    base = np.median(np.stack([curves[r['sample_id']] for r in selected if r['condition'] == 'BASE']), axis=0)
    centers = {}; signs = {}; features = []
    for module in _MODULES:
        spectrum = np.median(np.stack([curves[r['sample_id']] for r in selected if r['condition'] == module]), axis=0)
        feature = _extract_local_feature(frequency, spectrum - base, target_hz=_TARGETS_HZ[module])
        centers[module] = feature['measured_feature_hz']
        signs[module] = 1 if feature['signed_contrast_db'] >= 0 else -1
        features.append({'module': module, **feature})
    arrays = {}
    for config in ARRAY_CONFIGURATIONS:
        groups = {angle: tuple(r['sample_id'] for r in selected if r['condition'] == config and int(r['direction_deg']) == angle) for angle in ANGLES}
        matrix = _direction_channel_matrix(curves, frequency, groups, centers, signs)
        arrays[config] = {'direction_effect_db': _direction_statistic(curves, frequency, groups), **direction_code_score(matrix)}
    sim_frequency, sim_pressure = read_complex(DATA_DIR / 'isolated_resonator_simulation/thermoviscous_fine_transfer_phase.csv')
    return {'recorded_curves': len(curves), 'selected_curves': len(selected), 'single_resonators': features, 'four_direction_mapping': arrays,
            'isolated_thermoviscous_reference': refined_peak(sim_frequency, sim_pressure)}

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))


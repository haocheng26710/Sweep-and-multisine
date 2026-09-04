"""Four state shared cavity.
Numerical functions and frozen parameters used in Draft 18.
Run this script to calculate the bounded example from its supplied datasets.
Additional original numerical functions are available for explicit use.
Requirements: Python 3.11+ and NumPy; SciPy/scikit-learn where imported.
"""
from __future__ import annotations
from pathlib import Path
import json
import csv
from collections import defaultdict
from dataclasses import dataclass
from numpy.typing import NDArray
from sklearn.metrics import balanced_accuracy_score
from sklearn.metrics import confusion_matrix
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler
from typing import Any
from typing import Mapping
from typing import Sequence
import itertools
import numpy as np
from measurement_io import load_measurements

DATA_DIR = Path(__file__).resolve().parent.parent / "datasets" / "01_four_state_shared_cavity"


# Direction models

class DirectionModelError(ValueError):
    """Raised when a direction model cannot be fitted, trusted, or applied."""

def _rank(scores: NDArray[np.float64], labels: NDArray[np.float64], direction_order: tuple[float, ...], *, higher_better: bool) -> tuple[float, float | None, float, float | None, float | None]:
    order_index = {angle: index for index, angle in enumerate(direction_order)}
    indices = sorted(range(len(labels)), key=lambda i: (-scores[i] if higher_better else scores[i], order_index[float(labels[i])]))
    first, second = (indices[0], indices[1] if len(indices) > 1 else None)
    second_score = None if second is None else float(scores[second])
    margin = None if second is None else float(scores[first] - scores[second] if higher_better else scores[second] - scores[first])
    return (float(labels[first]), None if second is None else float(labels[second]), float(scores[first]), second_score, margin)

def predict_direction_arrays(model_id: str, x_train: NDArray[np.float64], y_train: NDArray[np.float64], x_test: NDArray[np.float64], direction_order: tuple[float, ...], random_state: int) -> list[tuple[float, float | None, float, float | None]]:
    """Apply the authoritative P5 fold-local semantics to numeric arrays."""
    train = np.asarray(x_train, dtype=np.float64)
    labels_train = np.asarray(y_train, dtype=np.float64)
    test = np.asarray(x_test, dtype=np.float64)
    labels = np.asarray([angle for angle in direction_order if angle in set(labels_train)], dtype=float)
    scaler = StandardScaler().fit(train)
    transformed_train = scaler.transform(train)
    transformed_test = scaler.transform(test)
    if model_id == 'nearest_centroid':
        centroids = np.vstack([np.mean(transformed_train[labels_train == label], axis=0) for label in labels])
        output = []
        for row in transformed_test:
            ranked = _rank(np.linalg.norm(centroids - row, axis=1), labels, direction_order, higher_better=False)
            output.append((ranked[0], ranked[1], ranked[2], ranked[4]))
        return output
    raise DirectionModelError('Only the paper nearest_centroid classifier is included')


# Formal core analysis

_DIRECTIONS = (0, 90, 180, 270)

_BLOCKS: dict[str, tuple[str, str, str, str]] = {'B01': ('U4SYM', 'AS01', 'RP01', 'S01'), 'B02': ('U4SYM', 'AS01', 'RP02', 'S01'), 'B03': ('U4ENC', 'AS01', 'RP01', 'S02'), 'B04': ('U4ENC', 'AS01', 'RP02', 'S02'), 'B05': ('U4ENC', 'AS02', 'RP01', 'S03'), 'B07': ('U4SYM', 'AS02', 'RP01', 'S04')}

_AS01_BLOCKS = {'U4SYM': ('B01', 'B02'), 'U4ENC': ('B03', 'B04')}

_AS02_BLOCKS = {'U4SYM': ('B07',), 'U4ENC': ('B05',)}

class Formal4InputError(ValueError):
    """Raised when an input/output authority or frozen analysis invariant fails."""

@dataclass(frozen=True, slots=True)
class Formal4Sample:
    sample_id: str
    block_id: str
    configuration: str
    assembly_id: str
    reposition_round_id: str
    session_id: str
    direction_deg: int
    repeat_id: str
    values: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    frequency_hz: NDArray[np.float64]
    outlier_flag: bool
    feature_npz_sha256: str
    feature_json_sha256: str

def band_masks(frequency_hz: NDArray[np.float64], valid_mask: NDArray[np.bool_]) -> dict[str, NDArray[np.bool_]]:
    """Return frozen bands on actual valid bins; never extrapolate the 200-Hz edge."""
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    valid = np.asarray(valid_mask, dtype=np.bool_)
    if frequency.ndim != 1 or valid.shape != frequency.shape:
        raise Formal4InputError('frequency and valid mask must be aligned 1-D arrays')
    return {'primary': valid & (frequency >= 200.0) & (frequency <= 4000.0), 'secondary': valid & (frequency >= 4000.0) & (frequency <= 8000.0), 'full': valid & (frequency >= 200.0) & (frequency <= 8000.0)}

def _normalize(vector: NDArray[np.float64], method: str) -> NDArray[np.float64]:
    values = np.asarray(vector, dtype=np.float64)
    if method == 'raw':
        return values
    centered = values - np.mean(values)
    if method == 'demeaned':
        return centered
    if method == 'zscore':
        scale = float(np.std(centered))
        return centered / scale if scale > 0 else np.zeros_like(centered)
    raise Formal4InputError(f'unsupported normalization: {method}')

def _rms(left: NDArray[np.float64], right: NDArray[np.float64], method: str) -> float:
    delta = _normalize(left, method) - _normalize(right, method)
    return float(np.sqrt(np.mean(np.square(delta))))

def _cell_samples(samples: Sequence[Formal4Sample], *, include_flagged: bool) -> dict[tuple[str, int], tuple[Formal4Sample, ...]]:
    grouped: dict[tuple[str, int], list[Formal4Sample]] = defaultdict(list)
    for sample in samples:
        if include_flagged or not sample.outlier_flag:
            grouped[sample.block_id, sample.direction_deg].append(sample)
    result: dict[tuple[str, int], tuple[Formal4Sample, ...]] = {}
    for key in sorted(grouped):
        ordered = tuple(sorted(grouped[key], key=lambda item: item.sample_id))
        if len(ordered) < 2:
            raise Formal4InputError(f'outlier sensitivity leaves fewer than two curves in cell {key}')
        result[key] = ordered
    if set(result) != {(block, direction) for block in _BLOCKS for direction in _DIRECTIONS}:
        raise Formal4InputError('analysis variant does not retain all frozen block/direction cells')
    return result

def _cell_medians(cells: Mapping[tuple[str, int], Sequence[Formal4Sample]]) -> dict[tuple[str, int], NDArray[np.float64]]:
    return {key: np.median(np.vstack([sample.values for sample in group]), axis=0) for key, group in cells.items()}

def _repeatability(cells: Mapping[tuple[str, int], Sequence[Formal4Sample]], frequency: NDArray[np.float64], masks: Mapping[str, NDArray[np.bool_]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, float]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    frequency_rows: list[dict[str, Any]] = []
    pair_values: dict[str, list[float]] = defaultdict(list)
    for (block, direction), group in sorted(cells.items()):
        for band, mask in masks.items():
            matrix = np.vstack([sample.values[mask] for sample in group])
            pairs = list(itertools.combinations(range(len(group)), 2))
            pair_rms = [float(np.sqrt(np.mean(np.square(matrix[left] - matrix[right])))) for left, right in pairs]
            pair_values[band].extend(pair_rms)
            absolute = np.concatenate([np.abs(matrix[left] - matrix[right]) for left, right in pairs])
            point_median = np.median(matrix, axis=0)
            point_mad = np.median(np.abs(matrix - point_median), axis=0)
            point_sd = np.std(matrix, axis=0, ddof=1)
            rows.append({'block_id': block, 'configuration': _BLOCKS[block][0], 'assembly_id': _BLOCKS[block][1], 'reposition_round_id': _BLOCKS[block][2], 'direction_deg': direction, 'band_id': band, 'frequency_point_count': int(np.count_nonzero(mask)), 'sample_count': len(group), 'sample_ids': [sample.sample_id for sample in group], 'pair_count': len(pairs), 'pair_ids': [f'{group[left].sample_id}|{group[right].sample_id}' for left, right in pairs], 'pairwise_rms_db': pair_rms, 'pairwise_rms_median_db': float(np.median(pair_rms)), 'median_absolute_difference_db': float(np.median(absolute)), 'p95_absolute_difference_db': float(np.percentile(absolute, 95)), 'pointwise_mad_median_db': float(np.median(point_mad)), 'pointwise_mad_p95_db': float(np.percentile(point_mad, 95)), 'pointwise_sd_median_db': float(np.median(point_sd)), 'pointwise_sd_p95_db': float(np.percentile(point_sd, 95))})
        full_matrix = np.vstack([sample.values[masks['full']] for sample in group])
        full_center = np.median(full_matrix, axis=0)
        full_mad = np.median(np.abs(full_matrix - full_center), axis=0)
        full_sd = np.std(full_matrix, axis=0, ddof=1)
        for frequency_value, mad, sd in zip(frequency[masks['full']], full_mad, full_sd, strict=True):
            frequency_rows.append({'block_id': block, 'configuration': _BLOCKS[block][0], 'assembly_id': _BLOCKS[block][1], 'direction_deg': direction, 'frequency_hz': float(frequency_value), 'frequency_band': 'primary' if frequency_value <= 4000.0 else 'secondary', 'sample_count': len(group), 'pointwise_mad_db': float(mad), 'pointwise_sd_db': float(sd)})
    summaries: list[dict[str, Any]] = []
    floor: dict[str, dict[str, float]] = {}
    for band in ('primary', 'secondary', 'full'):
        values = np.asarray(pair_values[band], dtype=np.float64)
        q25, q75 = np.percentile(values, [25, 75])
        summary = {'band_id': band, 'cell_count': len(cells), 'pair_count': int(values.size), 'median_pairwise_rms_db': float(np.median(values)), 'iqr_pairwise_rms_db': float(q75 - q25), 'p95_pairwise_rms_db': float(np.percentile(values, 95)), 'minimum_pairwise_rms_db': float(np.min(values)), 'maximum_pairwise_rms_db': float(np.max(values)), 'interpretation': 'CONT technical-repeat measurement-error floor'}
        summaries.append(summary)
        floor[band] = {'median_db': summary['median_pairwise_rms_db'], 'iqr_db': summary['iqr_pairwise_rms_db'], 'p95_db': summary['p95_pairwise_rms_db']}
    return (rows, summaries, floor, frequency_rows)

def _direction_effects(medians: Mapping[tuple[str, int], NDArray[np.float64]], masks: Mapping[str, NDArray[np.bool_]], floor: Mapping[str, Mapping[str, float]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in _BLOCKS:
        for left, right in itertools.combinations(_DIRECTIONS, 2):
            for band, mask in masks.items():
                values = {method: _rms(medians[block, left][mask], medians[block, right][mask], method) for method in ('raw', 'demeaned', 'zscore')}
                threshold = float(floor[band]['p95_db'])
                rows.append({'block_id': block, 'configuration': _BLOCKS[block][0], 'assembly_id': _BLOCKS[block][1], 'reposition_round_id': _BLOCKS[block][2], 'direction_a_deg': left, 'direction_b_deg': right, 'band_id': band, 'raw_rms_db': values['raw'], 'demeaned_rms_db': values['demeaned'], 'zscore_rms': values['zscore'], 'cont_repeatability_p95_db': threshold, 'effect_to_repeatability_ratio': values['demeaned'] / threshold if threshold > 0 else None, 'clearly_exceeds_measurement_floor': values['demeaned'] > threshold, 'decision_rule': 'demeaned_rms_gt_global_CONT_pairwise_rms_p95_same_band'})
    return rows

def _direction_effect_summaries(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for block in _BLOCKS:
        for band in ('primary', 'secondary', 'full'):
            selected = [row for row in rows if row['block_id'] == block and row['band_id'] == band]
            values = {'raw': np.asarray([row['raw_rms_db'] for row in selected], dtype=np.float64), 'demeaned': np.asarray([row['demeaned_rms_db'] for row in selected], dtype=np.float64), 'zscore': np.asarray([row['zscore_rms'] for row in selected], dtype=np.float64)}
            output.append({'block_id': block, 'configuration': _BLOCKS[block][0], 'assembly_id': _BLOCKS[block][1], 'band_id': band, 'direction_pair_count': len(selected), 'raw_minimum_rms_db': float(np.min(values['raw'])), 'raw_median_rms_db': float(np.median(values['raw'])), 'raw_maximum_rms_db': float(np.max(values['raw'])), 'demeaned_minimum_rms_db': float(np.min(values['demeaned'])), 'demeaned_median_rms_db': float(np.median(values['demeaned'])), 'demeaned_maximum_rms_db': float(np.max(values['demeaned'])), 'zscore_minimum_rms': float(np.min(values['zscore'])), 'zscore_median_rms': float(np.median(values['zscore'])), 'zscore_maximum_rms': float(np.max(values['zscore'])), 'clearly_exceeding_floor_pair_count': sum((bool(row['clearly_exceeds_measurement_floor']) for row in selected))})
    return output

def _gain_components(medians: Mapping[tuple[str, int], NDArray[np.float64]], masks: Mapping[str, NDArray[np.bool_]], *, configuration: str, method: str, band: str) -> tuple[dict[str, list[float]], list[float]]:
    blocks = _AS01_BLOCKS[configuration]
    mask = masks[band]
    between: dict[str, list[float]] = {}
    for block in blocks:
        between[block] = [_rms(medians[block, left][mask], medians[block, right][mask], method) for left, right in itertools.combinations(_DIRECTIONS, 2)]
    repos = [_rms(medians[blocks[0], direction][mask], medians[blocks[1], direction][mask], method) for direction in _DIRECTIONS]
    return (between, repos)

def _gain_bootstrap(between: Mapping[str, Sequence[float]], repos: Sequence[float], *, rng: np.random.Generator, iterations: int) -> tuple[float, float]:
    blocks = tuple(sorted(between))
    values: list[float] = []
    repos_array = np.asarray(repos, dtype=np.float64)
    for _ in range(iterations):
        selected_blocks = rng.choice(blocks, size=len(blocks), replace=True)
        numerator_values = np.concatenate([np.asarray(between[str(block)], dtype=np.float64) for block in selected_blocks])
        denominator_values = rng.choice(repos_array, size=repos_array.size, replace=True)
        denominator = float(np.median(denominator_values))
        if denominator > 0:
            values.append(float(np.median(numerator_values)) / denominator)
    if not values:
        return (float('nan'), float('nan'))
    return tuple((float(value) for value in np.percentile(values, [2.5, 97.5])))

def _gain_rows(medians: Mapping[tuple[str, int], NDArray[np.float64]], masks: Mapping[str, NDArray[np.bool_]], *, random_state: int, bootstrap_iterations: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for config_index, configuration in enumerate(('U4SYM', 'U4ENC')):
        for band_index, band in enumerate(('primary', 'secondary', 'full')):
            for method_index, method in enumerate(('raw', 'demeaned', 'zscore')):
                between, repos = _gain_components(medians, masks, configuration=configuration, method=method, band=band)
                numerator = float(np.median(np.concatenate([between[key] for key in sorted(between)])))
                denominator = float(np.median(repos))
                gain = numerator / denominator if denominator > 0 else None
                rng = np.random.default_rng(random_state + config_index * 100 + band_index * 10 + method_index)
                ci_low, ci_high = _gain_bootstrap(between, repos, rng=rng, iterations=bootstrap_iterations)
                rows.append({'configuration': configuration, 'assembly_scope': 'AS01', 'band_id': band, 'normalization': method, 'between_direction_pair_count': sum((len(value) for value in between.values())), 'reposition_pair_count': len(repos), 'between_direction_median_rms': numerator, 'within_direction_REPOS_median_rms': denominator, 'gain': gain, 'bootstrap_ci95_low': ci_low, 'bootstrap_ci95_high': ci_high, 'bootstrap_iterations': bootstrap_iterations, 'bootstrap_method': 'block_cluster_and_direction_REPOS_resampling', 'status': 'estimable_limited_two_REPOS_blocks', 'threshold': 1.0 if method == 'demeaned' else ''})
        for band in ('primary', 'secondary', 'full'):
            for method in ('raw', 'demeaned', 'zscore'):
                rows.append({'configuration': configuration, 'assembly_scope': 'AS02', 'band_id': band, 'normalization': method, 'between_direction_pair_count': 6, 'reposition_pair_count': 0, 'between_direction_median_rms': '', 'within_direction_REPOS_median_rms': '', 'gain': '', 'bootstrap_ci95_low': '', 'bootstrap_ci95_high': '', 'bootstrap_iterations': 0, 'bootstrap_method': 'not_applicable', 'status': 'not_estimable_single_block_no_REPOS_denominator', 'threshold': 1.0 if method == 'demeaned' else ''})
    return rows

def _gain_contrast_rows(medians: Mapping[tuple[str, int], NDArray[np.float64]], masks: Mapping[str, NDArray[np.bool_]], *, random_state: int, bootstrap_iterations: int) -> list[dict[str, Any]]:
    """Bootstrap the preregistered U4ENC minus U4SYM gain contrast."""
    rows: list[dict[str, Any]] = []
    for band_index, band in enumerate(('primary', 'secondary', 'full')):
        for method_index, method in enumerate(('raw', 'demeaned', 'zscore')):
            components = {configuration: _gain_components(medians, masks, configuration=configuration, method=method, band=band) for configuration in ('U4SYM', 'U4ENC')}
            point: dict[str, float] = {}
            for configuration, (between, repos) in components.items():
                point[configuration] = float(np.median(np.concatenate([between[key] for key in sorted(between)])) / np.median(repos))
            rng = np.random.default_rng(random_state + 5000 + band_index * 10 + method_index)
            bootstrap_delta: list[float] = []
            for _ in range(bootstrap_iterations):
                gains: dict[str, float] = {}
                for configuration, (between, repos) in components.items():
                    blocks = tuple(sorted(between))
                    selected_blocks = rng.choice(blocks, size=len(blocks), replace=True)
                    numerator = float(np.median(np.concatenate([np.asarray(between[str(block)], dtype=np.float64) for block in selected_blocks])))
                    denominator = float(np.median(rng.choice(np.asarray(repos, dtype=np.float64), size=len(repos), replace=True)))
                    gains[configuration] = numerator / denominator
                bootstrap_delta.append(gains['U4ENC'] - gains['U4SYM'])
            ci_low, ci_high = np.percentile(bootstrap_delta, [2.5, 97.5])
            delta = point['U4ENC'] - point['U4SYM']
            rows.append({'assembly_scope': 'AS01', 'band_id': band, 'normalization': method, 'u4sym_gain': point['U4SYM'], 'u4enc_gain': point['U4ENC'], 'u4enc_minus_u4sym_gain': delta, 'bootstrap_ci95_low': float(ci_low), 'bootstrap_ci95_high': float(ci_high), 'bootstrap_iterations': bootstrap_iterations, 'bootstrap_method': 'independent_configuration_block_cluster_and_direction_REPOS_resampling', 'frozen_threshold': 0.0 if method == 'demeaned' else '', 'point_threshold_pass': delta > 0 if method == 'demeaned' else '', 'ci_lower_threshold_pass': float(ci_low) > 0 if method == 'demeaned' else '', 'status': 'estimable_limited_two_REPOS_blocks_per_configuration'})
    return rows

def _classification_scopes() -> tuple[tuple[str, str, tuple[str, ...], str], ...]:
    return (('U4SYM_AS01', 'U4SYM', _AS01_BLOCKS['U4SYM'], 'estimable_limited'), ('U4ENC_AS01', 'U4ENC', _AS01_BLOCKS['U4ENC'], 'estimable_limited'), ('U4SYM_AS02', 'U4SYM', _AS02_BLOCKS['U4SYM'], 'not_estimable'), ('U4ENC_AS02', 'U4ENC', _AS02_BLOCKS['U4ENC'], 'not_estimable'), ('U4SYM_ALL_ASSEMBLIES', 'U4SYM', (*_AS01_BLOCKS['U4SYM'], *_AS02_BLOCKS['U4SYM']), 'exploratory'), ('U4ENC_ALL_ASSEMBLIES', 'U4ENC', (*_AS01_BLOCKS['U4ENC'], *_AS02_BLOCKS['U4ENC']), 'exploratory'))

def _classification_once(medians: Mapping[tuple[str, int], NDArray[np.float64]], mask: NDArray[np.bool_], blocks: Sequence[str], *, random_state: int, labels_by_block: Mapping[str, Sequence[int]] | None=None) -> tuple[list[dict[str, Any]], NDArray[np.int64], NDArray[np.int64]]:
    predictions: list[dict[str, Any]] = []
    all_true: list[int] = []
    all_predicted: list[int] = []
    for fold_index, test_block in enumerate(blocks, start=1):
        train_blocks = tuple((block for block in blocks if block != test_block))
        x_train: list[NDArray[np.float64]] = []
        y_train: list[int] = []
        x_test: list[NDArray[np.float64]] = []
        y_test: list[int] = []
        for block in train_blocks:
            labels = labels_by_block[block] if labels_by_block is not None else _DIRECTIONS
            for direction, label in zip(_DIRECTIONS, labels, strict=True):
                x_train.append(_normalize(medians[block, direction][mask], 'demeaned'))
                y_train.append(int(label))
        test_labels = labels_by_block[test_block] if labels_by_block is not None else _DIRECTIONS
        for direction, label in zip(_DIRECTIONS, test_labels, strict=True):
            x_test.append(_normalize(medians[test_block, direction][mask], 'demeaned'))
            y_test.append(int(label))
        outcomes = predict_direction_arrays('nearest_centroid', np.vstack(x_train), np.asarray(y_train, dtype=float), np.vstack(x_test), tuple((float(item) for item in _DIRECTIONS)), random_state + fold_index)
        for direction, truth, outcome in zip(_DIRECTIONS, y_test, outcomes, strict=True):
            predicted = int(outcome[0])
            all_true.append(truth)
            all_predicted.append(predicted)
            predictions.append({'fold_id': f'fold-{fold_index:02d}', 'test_block_id': test_block, 'train_block_ids': train_blocks, 'physical_direction_deg': direction, 'true_direction_deg': truth, 'predicted_direction_deg': predicted, 'correct': truth == predicted, 'continuous_repeat_aggregation': 'block_direction_median_curve'})
    return (predictions, np.asarray(all_true), np.asarray(all_predicted))

def _classification(medians: Mapping[tuple[str, int], NDArray[np.float64]], primary_mask: NDArray[np.bool_], *, random_state: int, permutation_iterations: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, NDArray[np.int64]]]:
    metrics: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    matrices: dict[str, NDArray[np.int64]] = {}
    for scope_index, (scope, configuration, blocks, status) in enumerate(_classification_scopes()):
        if len(blocks) < 2:
            metrics.append({'scope_id': scope, 'configuration': configuration, 'assembly_scope': 'AS02', 'protocol': 'leave_one_block_out', 'model_id': 'nearest_centroid', 'status': 'not_estimable', 'reason': 'single_block_cannot_support_grouped_validation', 'group_count': len(blocks), 'fold_count': 0, 'prediction_count': 0, 'fold_coverage': 0.0, 'balanced_accuracy': '', 'macro_f1': '', 'chance_level': 0.25, 'permutation_iterations': 0, 'permutation_balanced_accuracy_mean': '', 'permutation_balanced_accuracy_p95': '', 'permutation_p_value': '', 'exploratory': True})
            continue
        observed, truth, predicted = _classification_once(medians, primary_mask, blocks, random_state=random_state)
        balanced = float(balanced_accuracy_score(truth, predicted))
        macro = float(f1_score(truth, predicted, labels=list(_DIRECTIONS), average='macro', zero_division=0))
        matrix = confusion_matrix(truth, predicted, labels=list(_DIRECTIONS)).astype(np.int64)
        matrices[scope] = matrix
        for row in observed:
            predictions.append({**row, 'scope_id': scope, 'configuration': configuration})
        rng = np.random.default_rng(random_state + scope_index * 1000)
        permutation_scores: list[float] = []
        for iteration in range(permutation_iterations):
            labels_by_block = {block: tuple((int(value) for value in rng.permutation(_DIRECTIONS))) for block in blocks}
            _, perm_truth, perm_predicted = _classification_once(medians, primary_mask, blocks, random_state=random_state + iteration + 1, labels_by_block=labels_by_block)
            permutation_scores.append(float(balanced_accuracy_score(perm_truth, perm_predicted)))
        perm = np.asarray(permutation_scores, dtype=np.float64)
        p_value = float((1 + np.count_nonzero(perm >= balanced)) / (1 + perm.size))
        metrics.append({'scope_id': scope, 'configuration': configuration, 'assembly_scope': 'AS01' if scope.endswith('AS01') else 'all_assemblies', 'protocol': 'leave_one_block_out', 'model_id': 'nearest_centroid', 'status': status, 'reason': 'limited_independent_blocks' if status == 'estimable_limited' else 'assembly_time_generalization_exploratory', 'group_count': len(blocks), 'fold_count': len(blocks), 'prediction_count': int(truth.size), 'fold_coverage': 1.0, 'balanced_accuracy': balanced, 'macro_f1': macro, 'chance_level': 0.25, 'permutation_iterations': permutation_iterations, 'permutation_balanced_accuracy_mean': float(np.mean(perm)), 'permutation_balanced_accuracy_p95': float(np.percentile(perm, 95)), 'permutation_p_value': p_value, 'exploratory': status != 'estimable_limited'})
    return (metrics, predictions, matrices)


def paper_example():
    """Recompute the primary-band floor, gains and grouped recognition from 72 curves.

    U4SYM is the straight-path reference; U4ENC is the heterogeneous-path device.
    The 19 excluded identities remain in samples.csv, with no curve re-selection.
    The original bootstrap functions above resample distance summaries, with
    fixed spectral medians; their intervals are conditional descriptive intervals.
    """
    frequency, valid, curves, rows = load_measurements(DATA_DIR)
    primary = valid & (frequency >= 200.0) & (frequency <= 4000.0)
    cells = defaultdict(list)
    for row in rows:
        if row['analysis_included'] == 'true':
            cells[row['block_id'], int(row['direction_deg'])].append(curves[row['sample_id']])
    medians = {key: np.median(np.stack(value), axis=0) for key, value in cells.items()}
    distances = [_rms(a[primary], b[primary], 'raw') for matrix in cells.values() for a, b in itertools.combinations(matrix, 2)]
    result = {'included_curves': len(curves), 'excluded_records': sum(row['selection_status'] == 'EXCLUDED' for row in rows),
              'technical_median_db': float(np.median(distances)), 'technical_p95_db': float(np.percentile(distances, 95)), 'configurations': {}}
    for ci, (config, blocks) in enumerate(_AS01_BLOCKS.items()):
        between, repos = _gain_components(medians, {'primary': primary}, configuration=config, method='demeaned', band='primary')
        gain = float(np.median(np.concatenate(list(between.values()))) / np.median(repos))
        interval = _gain_bootstrap(between, repos, rng=np.random.default_rng(20260820 + ci * 100 + 1), iterations=2000)
        _, truth, predicted = _classification_once(medians, primary, blocks, random_state=20260820)
        result['configurations'][config] = {'gain': gain, 'gain_ci95': interval, 'balanced_accuracy': float(balanced_accuracy_score(truth, predicted))}
    return result

if __name__ == '__main__':
    print(json.dumps(paper_example(), indent=2))


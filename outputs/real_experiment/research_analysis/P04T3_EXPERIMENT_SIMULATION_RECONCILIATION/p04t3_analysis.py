"""Pure helpers for the frozen P04T3 experiment–simulation audit."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import spearmanr


def map_log_frequency_db(source_frequency_hz: np.ndarray, source_db: np.ndarray,
                         target_frequency_hz: np.ndarray) -> tuple[np.ndarray, list[str]]:
    source_f = np.asarray(source_frequency_hz, dtype=float)
    values = np.asarray(source_db, dtype=float)
    target = np.asarray(target_frequency_hz, dtype=float)
    if source_f.ndim != 1 or values.shape != source_f.shape or target.ndim != 1:
        raise ValueError("frequency/value shapes are invalid")
    if np.any(np.diff(source_f) <= 0) or target.min() < source_f.min() or target.max() > source_f.max():
        raise ValueError("mapping would require extrapolation or non-monotonic input")
    mapped = np.interp(np.log(target), np.log(source_f), values)
    modes = []
    for value in target:
        exact = np.any(np.isclose(source_f, value, rtol=0.0, atol=max(1e-9, abs(value) * 1e-12)))
        modes.append("exact" if exact else "interpolated")
    return mapped, modes


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else math.nan


def effect_metrics(simulation: np.ndarray, experiment: np.ndarray,
                   frequency_hz: np.ndarray) -> dict[str, float]:
    sim = np.asarray(simulation, dtype=float)
    exp = np.asarray(experiment, dtype=float)
    frequency = np.asarray(frequency_hz, dtype=float)
    if sim.shape != exp.shape or sim.shape != frequency.shape or sim.size < 3:
        raise ValueError("effect arrays must have equal length >=3")
    sim_shape = sim - sim.mean(); exp_shape = exp - exp.mean()
    sim_max, sim_min = int(np.argmax(sim)), int(np.argmin(sim))
    exp_max, exp_min = int(np.argmax(exp)), int(np.argmin(exp))
    positive_hz = abs(float(frequency[sim_max] - frequency[exp_max]))
    negative_hz = abs(float(frequency[sim_min] - frequency[exp_min]))
    return {
        "raw_pearson": float(np.corrcoef(sim, exp)[0, 1]),
        "raw_spearman": float(spearmanr(sim, exp).statistic),
        "raw_cosine": _cosine(sim, exp),
        "demeaned_pearson": float(np.corrcoef(sim_shape, exp_shape)[0, 1]),
        "demeaned_spearman": float(spearmanr(sim_shape, exp_shape).statistic),
        "demeaned_cosine": _cosine(sim_shape, exp_shape),
        "raw_rms_mismatch_db": float(np.sqrt(np.mean((sim - exp) ** 2))),
        "demeaned_rms_mismatch_db": float(np.sqrt(np.mean((sim_shape - exp_shape) ** 2))),
        "polarity_agreement_fraction": float(np.mean(np.sign(sim) == np.sign(exp))),
        "simulation_max_positive_frequency_hz": float(frequency[sim_max]),
        "experiment_max_positive_frequency_hz": float(frequency[exp_max]),
        "positive_extremum_distance_hz": positive_hz,
        "positive_extremum_distance_octave": abs(math.log2(float(frequency[exp_max] / frequency[sim_max]))),
        "positive_extremum_within_1_12_octave": abs(math.log2(float(frequency[exp_max] / frequency[sim_max]))) < 1 / 12,
        "simulation_max_negative_frequency_hz": float(frequency[sim_min]),
        "experiment_max_negative_frequency_hz": float(frequency[exp_min]),
        "negative_extremum_distance_hz": negative_hz,
        "negative_extremum_distance_octave": abs(math.log2(float(frequency[exp_min] / frequency[sim_min]))),
        "negative_extremum_within_1_12_octave": abs(math.log2(float(frequency[exp_min] / frequency[sim_min]))) < 1 / 12,
        "simulation_raw_rms_db": float(np.sqrt(np.mean(sim ** 2))),
        "experiment_raw_rms_db": float(np.sqrt(np.mean(exp ** 2))),
        "simulation_demeaned_rms_db": float(np.sqrt(np.mean(sim_shape ** 2))),
        "experiment_demeaned_rms_db": float(np.sqrt(np.mean(exp_shape ** 2))),
    }


def classify(*, input_ok: bool, dose_selected: bool, dose_all6: bool,
             experiment_robust: bool, concordance_all: bool) -> str:
    if not input_ok:
        return "P04T3 BLOCKED_INPUT_INTEGRITY"
    if not experiment_robust or not (dose_selected and dose_all6):
        return "P04T3 EXPERIMENTAL_EFFECT_NOT_ROBUST"
    if concordance_all:
        return "P04T3 MODEL_CONCORDANT_WITH_LIMITS"
    return "P04T3 REAL_VOLUME_EFFECT_MODEL_LOCALIZATION_MISMATCH"

import importlib.util
from pathlib import Path

import numpy as np
import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("p04t3_analysis", HERE / "p04t3_analysis.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def test_log_frequency_interpolation_and_identity_flags():
    source_f = np.array([100.0, 200.0, 400.0])
    source_db = np.array([0.0, 10.0, 20.0])
    target = np.array([100.0, np.sqrt(100.0 * 200.0), 400.0])
    values, modes = p.map_log_frequency_db(source_f, source_db, target)
    assert values == pytest.approx([0.0, 5.0, 20.0])
    assert modes == ["exact", "interpolated", "exact"]


def test_mapping_refuses_extrapolation():
    with pytest.raises(ValueError):
        p.map_log_frequency_db(np.array([100.0, 200.0]), np.array([1.0, 2.0]), np.array([99.0]))


def test_similarity_metrics_are_self_consistent():
    metrics = p.effect_metrics(np.array([-1.0, 0.0, 2.0]), np.array([-1.0, 0.0, 2.0]), np.array([1000.0, 1100.0, 1200.0]))
    assert metrics["raw_pearson"] == pytest.approx(1.0)
    assert metrics["demeaned_cosine"] == pytest.approx(1.0)
    assert metrics["raw_rms_mismatch_db"] == pytest.approx(0.0)
    assert metrics["polarity_agreement_fraction"] == pytest.approx(1.0)


def test_frozen_scientific_classification_states():
    assert p.classify(input_ok=True, dose_selected=True, dose_all6=True, experiment_robust=True, concordance_all=True) == "P04T3 MODEL_CONCORDANT_WITH_LIMITS"
    assert p.classify(input_ok=True, dose_selected=True, dose_all6=True, experiment_robust=True, concordance_all=False) == "P04T3 REAL_VOLUME_EFFECT_MODEL_LOCALIZATION_MISMATCH"
    assert p.classify(input_ok=True, dose_selected=False, dose_all6=True, experiment_robust=False, concordance_all=False) == "P04T3 EXPERIMENTAL_EFFECT_NOT_ROBUST"
    assert p.classify(input_ok=False, dose_selected=True, dose_all6=True, experiment_robust=True, concordance_all=True) == "P04T3 BLOCKED_INPUT_INTEGRITY"

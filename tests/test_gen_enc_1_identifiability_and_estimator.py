from __future__ import annotations

import inspect

import numpy as np
import pytest

from acoustic_encoder.gen_enc.bridge import FROZEN_ANGLES_DEGREES, evaluate_sampled_bridge
from acoustic_encoder.gen_enc.decisions import (
    REQUIRED_FAMILIES,
    CandidateDecision,
    FamilyDecision,
    GlobalDecision,
)
from acoustic_encoder.gen_enc.estimator import (
    CandidateResult,
    WhitenerResult,
    embed_complex_responses,
    evaluate_candidate,
    fit_whitener,
    project_modes,
    projection_matrices,
    trapezoidal_weights,
    weighted_empirical_quantile,
)
from acoustic_encoder.gen_enc.identifiability import (
    gauge_transform,
    observable_operator,
    shared_differential_rank_ceiling,
)


def _identity_whitener(dimension: int = 3) -> WhitenerResult:
    identity = np.eye(dimension)
    return WhitenerResult("AVAILABLE", None, identity, identity, identity, 0.0, np.finfo(float).eps, 8.0)


def _rank_three_response(third: float = 1.5) -> np.ndarray:
    rows = np.array(
        [
            [1.0, -1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, -1.0],
            [0.5, 0.5, -0.5, -0.5],
        ]
    )
    rows[0] *= 2.0 / np.linalg.norm(rows[0])
    rows[1] *= 1.75 / np.linalg.norm(rows[1])
    rows[2] *= third / np.linalg.norm(rows[2])
    return rows


def _repeat_cell(scale: float, repeats: int = 2, features: int = 3) -> np.ndarray:
    pattern = np.zeros((features, 4), dtype=float)
    pattern[0] = [1.0, -1.0, 0.0, 0.0]
    if features > 1:
        pattern[1] = [0.0, 1.0, -1.0, 0.0]
    values = np.stack([pattern * scale * sign for sign in np.resize([-1.0, 1.0], repeats)])
    return values


def _circle(radius: float = 2.0) -> np.ndarray:
    radians = np.deg2rad(FROZEN_ANGLES_DEGREES)
    return radius * np.vstack((np.cos(radians), np.sin(radians)))


def test_gauge_transform_preserves_observable_operator() -> None:
    a = np.array([[1 + 1j, 2], [0.5, -1j]])
    c = np.array([[2, 0.25j], [1, 3]])
    b = np.array([[1, 2], [-0.5j, 1]])
    q = np.array([[2, 1], [0, 1]], dtype=complex)
    r = np.array([[1, 0.5j], [0.25, 2]], dtype=complex)

    transformed = gauge_transform(a, c, b, q, r)

    np.testing.assert_allclose(observable_operator(*transformed), observable_operator(a, c, b))


def test_shared_projection_removes_common_state_component() -> None:
    y = _rank_three_response() + np.array([[4.0], [-2.0], [7.0]])
    shared, differential = project_modes(y)

    np.testing.assert_allclose(differential.sum(axis=1), 0.0, atol=1e-14)
    np.testing.assert_allclose(shared, np.repeat(y.mean(axis=1, keepdims=True), 4, axis=1))


def test_four_state_differential_rank_ceiling_is_three() -> None:
    _, p_diff = projection_matrices(4)
    assert np.linalg.matrix_rank(p_diff) == 3
    assert shared_differential_rank_ceiling(4) == 3


def test_complex_real_embedding_uses_shared_trapezoidal_weights() -> None:
    frequency = np.array([100.0, 200.0, 400.0])
    weights = trapezoidal_weights(frequency)
    response = np.ones((3, 1, 1, 4), dtype=complex) * (2.0 + 3.0j)

    embedded = embed_complex_responses(response, weights)

    np.testing.assert_allclose(weights, [1 / 6, 1 / 2, 1 / 3])
    np.testing.assert_allclose(embedded[:3, 0], 2.0 * np.sqrt(weights))
    np.testing.assert_allclose(embedded[3:, 0], 3.0 * np.sqrt(weights))


@pytest.mark.parametrize(
    ("third", "expected_status", "expected_rank"),
    [(1.5, "PASS", 3), (0.75, "NEGATIVE", 2)],
)
def test_candidate_endpoint_pass_and_fail(third: float, expected_status: str, expected_rank: int) -> None:
    y = _rank_three_response(third)
    result = evaluate_candidate({"cell": [y] * 20}, ["cell"], _identity_whitener())

    assert result.scientific_status == expected_status
    assert result.stable_rank == expected_rank


def test_threshold_equality_is_failure() -> None:
    result = evaluate_candidate({"cell": [_rank_three_response(1.0)] * 20}, ["cell"], _identity_whitener())

    assert result.primary_endpoint == pytest.approx(1.0, abs=1e-14)
    assert result.scientific_status == "NEGATIVE"
    assert result.stable_rank == 2


def test_less_than_twenty_equal_weight_units_quantile_is_conservative_minimum() -> None:
    values = np.arange(19.0, 0.0, -1.0)
    assert weighted_empirical_quantile(values, np.ones(19), 0.05) == 1.0

    result = evaluate_candidate({"cell": [_rank_three_response(1.5)] * 19}, ["cell"], _identity_whitener())
    assert result.small_sample_disclosure == "CONSERVATIVE_AND_SINGLE_UNIT_DOMINATED_Q_0.05_EQUALS_MINIMUM"


def test_missing_nuisance_cell_is_unavailable() -> None:
    result = evaluate_candidate({"a": [_rank_three_response()]}, ["a", "b"], _identity_whitener())
    assert result.technical_status == "UNAVAILABLE"
    assert result.scientific_status == "NOT_TESTED"
    assert result.reason == "MISSING_PREREGISTERED_NUISANCE_CELL"


def test_nonfinite_evaluation_unit_is_unavailable() -> None:
    y = _rank_three_response()
    y[0, 0] = np.nan
    result = evaluate_candidate({"cell": [y]}, ["cell"], _identity_whitener())
    assert result.technical_status == "UNAVAILABLE"
    assert result.reason == "NONFINITE_EVALUATION_UNIT"


def test_w_unavailable_propagates_without_scientific_rejection() -> None:
    unavailable = WhitenerResult("UNAVAILABLE", "fixture", None, None, None, None, None, None)
    result = evaluate_candidate({"cell": [_rank_three_response()]}, ["cell"], unavailable)
    assert (result.technical_status, result.scientific_status) == ("UNAVAILABLE", "NOT_TESTED")


def test_fit_whitener_has_no_validation_input_and_is_deterministic() -> None:
    assert "validation" not in " ".join(inspect.signature(fit_whitener).parameters).lower()
    train = {"a": _repeat_cell(1.0), "b": _repeat_cell(4.0)}
    development = {"a": _repeat_cell(1.5), "b": _repeat_cell(3.5)}

    first = fit_whitener(train, development, ["a", "b"])
    second = fit_whitener(train, development, ["a", "b"])

    assert first.status == "AVAILABLE"
    np.testing.assert_array_equal(first.operator, second.operator)


def test_nuisance_cells_receive_equal_covariance_weight() -> None:
    train = {"small": _repeat_cell(1.0, repeats=2), "large": _repeat_cell(4.0, repeats=8)}
    development = {"small": _repeat_cell(1.0, repeats=2), "large": _repeat_cell(4.0, repeats=8)}
    result = fit_whitener(train, development, ["small", "large"])

    small_rows = np.concatenate([_manual_residual_rows(train["small"]), _manual_residual_rows(development["small"])])
    large_rows = np.concatenate([_manual_residual_rows(train["large"]), _manual_residual_rows(development["large"])])
    expected = 0.5 * (small_rows.T @ small_rows / len(small_rows)) + 0.5 * (
        large_rows.T @ large_rows / len(large_rows)
    )
    np.testing.assert_allclose(result.empirical_covariance, expected)


def _manual_residual_rows(repeats: np.ndarray) -> np.ndarray:
    p_diff = projection_matrices(4)[1]
    projected = repeats @ p_diff
    residual = projected - projected.mean(axis=0, keepdims=True)
    return residual.transpose(0, 2, 1).reshape((-1, repeats.shape[1]))


def test_oas_and_eigen_floor_handle_rank_deficient_covariance() -> None:
    result = fit_whitener(
        {"cell": _repeat_cell(1.0, features=4)},
        {"cell": _repeat_cell(2.0, features=4)},
        ["cell"],
    )

    assert result.status == "AVAILABLE"
    assert result.shrinkage is not None and 0.0 <= result.shrinkage <= 1.0
    assert result.eigenvalue_floor is not None and result.eigenvalue_floor > 0.0
    assert np.linalg.matrix_rank(result.empirical_covariance) < 4
    assert np.all(np.isfinite(result.operator))


def test_zero_or_nonfinite_residuals_make_w_unavailable() -> None:
    zeros = np.zeros((2, 3, 4))
    zero_result = fit_whitener({"cell": zeros}, {"cell": zeros}, ["cell"])
    assert zero_result.status == "UNAVAILABLE"
    assert zero_result.reason == "NONPOSITIVE_COVARIANCE"

    bad = _repeat_cell(1.0)
    bad[0, 0, 0] = np.nan
    nonfinite_result = fit_whitener({"cell": bad}, {"cell": _repeat_cell(1.0)}, ["cell"])
    assert nonfinite_result.status == "UNAVAILABLE"


def test_equal_cell_weight_can_dominate_quantile_independent_of_cell_size() -> None:
    low = _rank_three_response(0.5)
    high = _rank_three_response(2.0)
    result = evaluate_candidate({"small": [low], "large": [high] * 19}, ["small", "large"], _identity_whitener())

    assert result.primary_endpoint == pytest.approx(0.5)
    assert result.scientific_status == "NEGATIVE"


def test_candidate_family_global_decision_types_do_not_collapse() -> None:
    candidate_result = evaluate_candidate({"cell": [_rank_three_response()] * 20}, ["cell"], _identity_whitener())
    candidate = CandidateDecision("CANDIDATE", candidate_result)
    family = FamilyDecision.from_candidates("HAND_DESIGNED", [candidate.result])
    incomplete_global = GlobalDecision.from_families({"HAND_DESIGNED": family})
    complete_global = GlobalDecision.from_families(
        {family_id: FamilyDecision.from_candidates(family_id, [candidate.result]) for family_id in REQUIRED_FAMILIES}
    )

    assert candidate.level == "CANDIDATE"
    assert family.level == "FAMILY" and family.claim_limit == "PREREGISTERED_ENSEMBLE_ONLY"
    assert incomplete_global.outcome == "UNAVAILABLE"
    assert complete_global.level == "GLOBAL"
    assert complete_global.scalar_global_pass is None


def test_sampled_bridge_passes_exact_circle_fixture() -> None:
    result = evaluate_sampled_bridge(_circle())
    assert result.technical_status == "PASS"
    assert result.scientific_status == "PASS"
    assert result.mathematical_continuum_proof is False
    assert result.physical_entity_generalization is False


def test_sampled_bridge_detects_angular_fold() -> None:
    z = _circle()
    z[:, [3, 9]] = z[:, [9, 3]]
    result = evaluate_sampled_bridge(z)
    assert result.angular_order_pass is False
    assert result.scientific_status == "BRIDGE_FAIL"


def test_sampled_bridge_detects_wrong_derivative_orientation() -> None:
    z = _circle()
    z[:, 14:17] = z[:, 14:17][:, ::-1]
    result = evaluate_sampled_bridge(z)
    assert result.derivative_orientation_pass is False
    assert result.scientific_status == "BRIDGE_FAIL"


def test_sampled_bridge_detects_margin_failure_at_engineering_threshold() -> None:
    result = evaluate_sampled_bridge(_circle(radius=1.0))
    assert result.differential_margin_pass is False
    assert result.scientific_status == "BRIDGE_FAIL"


def test_sampled_bridge_detects_wrap_failure() -> None:
    z = _circle()
    z[:, -1] += np.array([8.0, -8.0])
    result = evaluate_sampled_bridge(z)
    assert result.circular_continuity_pass is False
    assert result.scientific_status == "BRIDGE_FAIL"


def test_sampled_bridge_singular_gram_is_unavailable() -> None:
    radians = np.deg2rad(FROZEN_ANGLES_DEGREES)
    z = np.vstack((2.0 * np.cos(radians), np.zeros_like(radians)))
    result = evaluate_sampled_bridge(z)
    assert (result.technical_status, result.scientific_status) == ("UNAVAILABLE", "NOT_TESTED")
    assert result.reason == "GRAM_A_B_NOT_INVERTIBLE"


def test_sampled_bridge_missing_angle_and_nonfinite_are_unavailable() -> None:
    missing = evaluate_sampled_bridge(_circle()[:, :-1], FROZEN_ANGLES_DEGREES[:-1])
    assert missing.technical_status == "UNAVAILABLE"
    bad = _circle()
    bad[0, 0] = np.nan
    assert evaluate_sampled_bridge(bad).technical_status == "UNAVAILABLE"

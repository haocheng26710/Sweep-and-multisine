from __future__ import annotations

import json
from pathlib import Path
import ast

import numpy as np
import pytest

from scripts.gen_enc_3a_robust_geometry_formal import (
    FORMAL_ROOT,
    PREFLIGHT_ROOT,
    FormalError,
    assert_not_preflight,
    deterministic_audit_units,
    source_manifest,
)
from scripts.gen_enc_3a_robust_geometry_independent_verifier import independent_inference

from acoustic_encoder.gen_enc.e2_rc03_stats import feature_matrix
from acoustic_encoder.gen_enc.estimator import projection_matrices
from acoustic_encoder.gen_enc.robust_encoding_geometry import (
    COMPLEX_FEATURE_DIMENSION,
    FAMILY_CONTRAST_ORDER,
    FAMILY_ORDER,
    PAIR_ORDER,
    STATE_ORDER_DEGREES,
    RobustGeometryError,
    batch_geometry_from_raw,
    complex_unembed_real,
    development_reference_gram,
    evaluation_unit_weights,
    frobenius_gram_drift,
    hermitian_gram,
    identity_level_family_inference,
    pair_anisotropy,
    pair_distances,
    primary_complex_differential,
    real_embed_complex,
    summarize_candidate_geometry,
    trace_normalized_gram,
    weakest_pair_index,
    weighted_lower_tail_expected_shortfall,
    weighted_upper_tail_expected_shortfall,
    whitened_complex_differential,
)


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/gen_enc_3a_robust_geometry/synthetic_geometry_fixture.json").read_text(
        encoding="utf-8"
    )
)
INFERENCE_FIXTURE = json.loads(
    (
        Path(__file__).parent
        / "fixtures/gen_enc_3a_robust_geometry/synthetic_identity_inference_fixture.json"
    ).read_text(encoding="utf-8")
)


def _fixture_z() -> np.ndarray:
    return np.asarray(FIXTURE["z_real"], dtype=float) + 1j * np.asarray(FIXTURE["z_imag"], dtype=float)


def test_frozen_state_and_pair_order_matches_fixture() -> None:
    assert list(STATE_ORDER_DEGREES) == FIXTURE["state_order_degrees"]
    assert [list(pair) for pair in PAIR_ORDER] == FIXTURE["pair_order"]


def test_pair_distance_weakest_pair_and_anisotropy_fixture() -> None:
    distances = pair_distances(_fixture_z())

    np.testing.assert_allclose(distances, FIXTURE["expected_pair_distances"], rtol=1e-15, atol=1e-15)
    assert float(np.min(distances)) == pytest.approx(FIXTURE["expected_d_min"])
    assert int(weakest_pair_index(distances)) == FIXTURE["expected_weakest_pair_index"]
    assert float(pair_anisotropy(distances)) == pytest.approx(FIXTURE["expected_pair_anisotropy"])


def test_gram_uses_complex_conjugate_and_is_hermitian() -> None:
    z = _fixture_z()
    gram = hermitian_gram(z)

    expected = complex(*FIXTURE["expected_gram_0_1"])
    assert gram[0, 1] == pytest.approx(expected)
    assert gram[0, 1] != pytest.approx((z.T @ z)[0, 1])
    np.testing.assert_allclose(gram, gram.conj().T, rtol=0.0, atol=0.0)


def test_trace_normalization_and_development_reference_are_unique() -> None:
    first = trace_normalized_gram(hermitian_gram(_fixture_z()))
    second = trace_normalized_gram(hermitian_gram(2.0 * _fixture_z()))
    reference = development_reference_gram(np.stack((first, second)), np.asarray([0.25, 0.75]))

    np.testing.assert_allclose(first, second, rtol=1e-15, atol=1e-15)
    np.testing.assert_allclose(reference, first, rtol=1e-15, atol=1e-15)
    assert np.trace(reference).real == pytest.approx(1.0)
    np.testing.assert_allclose(frobenius_gram_drift(np.stack((first, second)), reference), 0.0, atol=1e-15)


def test_weighted_expected_shortfall_uses_fractional_boundary_mass() -> None:
    tail = FIXTURE["tail_fixture"]

    assert weighted_lower_tail_expected_shortfall(tail["values"], tail["weights"], tail["tail_mass"]) == pytest.approx(
        tail["expected_lower"]
    )
    assert weighted_upper_tail_expected_shortfall(tail["values"], tail["weights"], tail["tail_mass"]) == pytest.approx(
        tail["expected_upper"]
    )
    assert -weighted_upper_tail_expected_shortfall(
        -np.asarray(tail["values"]), tail["weights"], tail["tail_mass"]
    ) == pytest.approx(tail["expected_lower"])


def test_frozen_complex_embedding_round_trip_is_isometric() -> None:
    rng = np.random.default_rng(2026090301)
    value = rng.normal(size=(COMPLEX_FEATURE_DIMENSION, 4)) + 1j * rng.normal(
        size=(COMPLEX_FEATURE_DIMENSION, 4)
    )
    embedded = real_embed_complex(value)
    restored = complex_unembed_real(embedded)

    np.testing.assert_array_equal(restored, value)
    np.testing.assert_allclose(np.linalg.norm(restored[:, 0] - restored[:, 1]), np.linalg.norm(embedded[:, 0] - embedded[:, 1]))


def test_primary_complex_direction_matches_e2_real_feature_direction() -> None:
    rng = np.random.default_rng(2026090302)
    response = rng.normal(size=(4, 4, 256)) + 1j * rng.normal(size=(4, 4, 256))
    y_diff = primary_complex_differential(response)
    e2_y = feature_matrix(response, range(4)) @ projection_matrices(4)[1]

    np.testing.assert_allclose(real_embed_complex(y_diff), e2_y, rtol=1e-15, atol=1e-15)


def test_whitener_direction_is_left_multiplication_before_complex_reassembly() -> None:
    rng = np.random.default_rng(2026090303)
    response = rng.normal(size=(4, 4, 256)) + 1j * rng.normal(size=(4, 4, 256))
    diagonal = np.linspace(0.5, 1.5, 2 * COMPLEX_FEATURE_DIMENSION)
    whitener = np.diag(diagonal)

    y_diff, z_complex, z_real = whitened_complex_differential(response, whitener)

    np.testing.assert_allclose(z_real, whitener @ real_embed_complex(y_diff), rtol=0.0, atol=0.0)
    np.testing.assert_allclose(complex_unembed_real(z_real), z_complex, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(pair_distances(z_complex)[0], np.linalg.norm(z_real[:, 0] - z_real[:, 1]))


def test_batch_geometry_matches_scalar_units() -> None:
    rng = np.random.default_rng(2026090304)
    raw = rng.normal(size=(4, 2, 2, 4, 256)) + 1j * rng.normal(size=(4, 2, 2, 4, 256))
    diagonal = np.linspace(0.5, 1.5, 2 * COMPLEX_FEATURE_DIMENSION)
    whitener = np.diag(diagonal)
    distances, grams, y_diff = batch_geometry_from_raw(raw, whitener)

    for cell in range(2):
        for repeat in range(2):
            scalar_y, scalar_z, _ = whitened_complex_differential(raw[:, cell, repeat], whitener)
            np.testing.assert_allclose(y_diff[cell, repeat], scalar_y, rtol=1e-15, atol=1e-15)
            np.testing.assert_allclose(distances[cell, repeat], pair_distances(scalar_z), rtol=1e-15, atol=1e-15)
            np.testing.assert_allclose(
                grams[cell, repeat], trace_normalized_gram(hermitian_gram(scalar_z)), rtol=1e-15, atol=1e-15
            )


def _clear_separation_inputs() -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    fixture = INFERENCE_FIXTURE["clear_separation"]
    pattern = np.asarray(fixture["within_family_pattern"], dtype=float)
    margin = {
        family: pattern + fixture["margin_offsets"][index]
        for index, family in enumerate(FAMILY_ORDER)
    }
    drift = {
        family: pattern + fixture["drift_offsets"][index] + 10.0
        for index, family in enumerate(FAMILY_ORDER)
    }
    return margin, drift


def _fixture_inference() -> dict[str, object]:
    margin, drift = _clear_separation_inputs()
    return identity_level_family_inference(
        margin,
        drift,
        bootstrap_replicates=INFERENCE_FIXTURE["test_bootstrap_replicates"],
        permutation_replicates=INFERENCE_FIXTURE["test_permutation_replicates"],
        bootstrap_seed=INFERENCE_FIXTURE["bootstrap_seed"],
        permutation_seed=INFERENCE_FIXTURE["permutation_seed"],
    )


def test_identity_inference_fixes_contrast_direction_and_twelve_statistics() -> None:
    result = _fixture_inference()

    assert list(FAMILY_ORDER) == INFERENCE_FIXTURE["family_order"]
    assert len(FAMILY_CONTRAST_ORDER) == 6
    assert result["status"] == "AVAILABLE"
    np.testing.assert_allclose(
        result["observed"]["margin"]["contrasts"],
        INFERENCE_FIXTURE["clear_separation"]["expected_margin_contrasts"],
    )
    np.testing.assert_allclose(
        result["observed"]["drift"]["contrasts"],
        INFERENCE_FIXTURE["clear_separation"]["expected_drift_contrasts"],
    )
    assert result["permutation"]["statistic_count"] == 12
    assert result["permutation"]["max_abs_t"].shape == (
        INFERENCE_FIXTURE["test_permutation_replicates"],
    )
    assert np.all(result["permutation"]["adjusted_p"] < 0.05)


def test_identity_inference_zero_difference_has_no_false_direction() -> None:
    pattern = np.asarray(INFERENCE_FIXTURE["clear_separation"]["within_family_pattern"], dtype=float)
    margin = {family: pattern.copy() for family in FAMILY_ORDER}
    drift = {family: pattern.copy() + 10.0 for family in FAMILY_ORDER}
    result = identity_level_family_inference(
        margin,
        drift,
        bootstrap_replicates=100,
        permutation_replicates=199,
    )

    assert result["status"] == "AVAILABLE"
    np.testing.assert_allclose(result["observed"]["margin"]["contrasts"], 0.0, atol=1e-15)
    np.testing.assert_allclose(result["observed"]["drift"]["contrasts"], 0.0, atol=1e-15)
    np.testing.assert_allclose(result["permutation"]["adjusted_p"], 1.0, atol=0.0)


@pytest.mark.parametrize("constant_endpoint", ("margin", "drift"))
def test_identity_inference_zero_variance_is_inconclusive(constant_endpoint: str) -> None:
    margin, drift = _clear_separation_inputs()
    target = margin if constant_endpoint == "margin" else drift
    for family in FAMILY_ORDER:
        target[family] = np.ones(20)
    result = identity_level_family_inference(
        margin,
        drift,
        bootstrap_replicates=20,
        permutation_replicates=20,
    )

    assert result["status"] == "INCONCLUSIVE"
    assert result["observed"][constant_endpoint]["status"] == "INCONCLUSIVE"
    assert result["permutation"] is None


def test_identity_inference_fixed_seeds_are_byte_repeatable() -> None:
    first = _fixture_inference()
    second = _fixture_inference()

    for endpoint in ("margin_contrasts", "drift_contrasts", "margin_percentile_95_ci", "drift_percentile_95_ci"):
        np.testing.assert_array_equal(first["bootstrap"][endpoint], second["bootstrap"][endpoint])
    for key in ("observed_twelve", "max_abs_t", "adjusted_p"):
        np.testing.assert_array_equal(first["permutation"][key], second["permutation"][key])


def test_identity_inference_rejects_non_exact20_and_non_identity_shapes() -> None:
    margin, drift = _clear_separation_inputs()
    margin[FAMILY_ORDER[0]] = np.ones((20, 2))

    with pytest.raises(RobustGeometryError, match="EXACT20_FINITE_IDENTITY_VALUES_PER_FAMILY_REQUIRED"):
        identity_level_family_inference(margin, drift, bootstrap_replicates=2, permutation_replicates=2)


def test_candidate_summary_uses_finest_units_and_frozen_tail_directions() -> None:
    distances = np.asarray(
        [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0], [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]], dtype=float
    )
    drift = np.asarray([0.1, 0.3], dtype=float)
    result = summarize_candidate_geometry(distances, drift, np.asarray([0.5, 0.5]))

    assert result["d_min_lower_tail_es_0p05"] == pytest.approx(1.0)
    assert result["gram_frobenius_drift_upper_tail_es_0p05"] == pytest.approx(0.3)
    assert result["weakest_pair_probability"] == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_fail_closed_on_zero_dmin_for_anisotropy() -> None:
    with pytest.raises(RobustGeometryError, match="STRICTLY_POSITIVE_D_MIN"):
        pair_anisotropy(np.asarray([0.0, 1.0, 1.0, 1.0, 1.0, 1.0]))


def test_evaluation_unit_weights_freeze_cell_and_repeat_mass() -> None:
    weights = evaluation_unit_weights()
    assert weights.shape == (7350,)
    assert weights.sum() == pytest.approx(1.0)
    np.testing.assert_array_equal(weights, np.full(7350, 1.0 / 7350.0))


def test_formal_root_is_independent_and_preflight_payload_is_rejected() -> None:
    assert FORMAL_ROOT.resolve() != PREFLIGHT_ROOT.resolve()
    with pytest.raises(FormalError, match="PREFLIGHT_PAYLOAD_READ_OR_PROMOTION_FORBIDDEN"):
        assert_not_preflight(PREFLIGHT_ROOT / "candidate/compact/distances.npy")


def test_hand_01_formal_audits_are_partition_bound_and_deterministic() -> None:
    first = deterministic_audit_units("development", "HAND_01")
    second = deterministic_audit_units("development", "HAND_01")
    validation = deterministic_audit_units("single_use_validation", "HAND_01")

    assert first == second
    assert len(first) == 2
    assert first != validation


def test_source_manifest_binds_executable_evidence_but_not_mutable_results_sidecar() -> None:
    entries = source_manifest()["entries"]

    assert "formal_driver" in entries
    assert "independent_verifier" in entries
    assert "formula_module" in entries
    assert "results_sidecar" not in entries
    assert source_manifest()["preflight_payload_source"] is False


def test_independent_verifier_has_no_production_formula_or_driver_import() -> None:
    verifier = Path(__file__).parents[1] / "scripts/gen_enc_3a_robust_geometry_independent_verifier.py"
    tree = ast.parse(verifier.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    assert "acoustic_encoder.gen_enc.robust_encoding_geometry" not in imported
    assert "scripts.gen_enc_3a_robust_geometry_formal" not in imported


def test_independent_inference_fail_closes_on_zero_variance() -> None:
    constant = np.ones((4, 20), dtype=float)
    result = independent_inference(constant, constant)

    assert result["status"] == "INCONCLUSIVE"
    assert result["reason"] == "AT_LEAST_ONE_ENDPOINT_WELCH_DENOMINATOR_UNAVAILABLE"
    assert result["permutation_maxima"] is None

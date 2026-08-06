from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from acoustic_encoder.cross_mode_bridge import (
    analyze_cross_mode_bridge,
    CalibrationStatus,
    CrossModeBridgeInputError,
    CrossModeFoldDefinition,
    MatchedModePair,
    P9CrossModeBridgeScope,
    apply_tone_calibration,
    compare_tone_values,
    fit_tone_calibration,
)
from acoustic_encoder.dataset_quality_control import feature_set_content_sha256
from acoustic_encoder.mock_data import generate_directional_feature_set_mock
from acoustic_encoder.schemas import FeatureKind, MeasurementMode, Representation, SourceFormat


HASH = "sha256:" + "1" * 64


def _fit_config() -> dict:
    return {
        "minimum_pairs_per_tone": 3,
        "minimum_input_variance_db2": 1.0e-8,
        "slope_bounds": [0.5, 1.5],
        "residual_policy": {
            "warning_above_rms_db": 0.05,
            "unavailable_above_rms_db": 0.25,
        },
    }


def test_bias_only_recovers_known_training_bias_without_mutating_inputs() -> None:
    multisine = np.asarray([-4.0, -2.0, 1.0, 3.0])
    sweep = multisine + 1.75
    before = multisine.copy()

    fit = fit_tone_calibration(
        tone_id="tone-a",
        frequency_hz=1000.0,
        method="bias_only",
        multisine_db=multisine,
        sweep_db=sweep,
        training_pair_ids=("p1", "p2", "p3", "p4"),
        config=_fit_config(),
    )

    assert fit.status is CalibrationStatus.VALID
    assert fit.slope == pytest.approx(1.0)
    assert fit.intercept_db == pytest.approx(1.75)
    assert fit.training_residual_rms_db == pytest.approx(0.0, abs=1.0e-12)
    assert np.array_equal(multisine, before)
    assert not apply_tone_calibration(multisine, fit).flags.writeable


def test_per_tone_affine_recovers_known_slope_and_intercept() -> None:
    multisine = np.asarray([-3.0, -1.0, 2.0, 5.0, 8.0])
    sweep = 1.2 * multisine - 0.7

    fit = fit_tone_calibration(
        tone_id="tone-b",
        frequency_hz=2000.0,
        method="per_tone_affine",
        multisine_db=multisine,
        sweep_db=sweep,
        training_pair_ids=("p1", "p2", "p3", "p4", "p5"),
        config=_fit_config(),
    )

    assert fit.status is CalibrationStatus.VALID
    assert fit.slope == pytest.approx(1.2, abs=1.0e-12)
    assert fit.intercept_db == pytest.approx(-0.7, abs=1.0e-12)
    assert apply_tone_calibration(multisine, fit) == pytest.approx(sweep)


@pytest.mark.parametrize(
    ("multisine", "sweep", "reason"),
    [
        ([-1.0, 0.0], [0.0, 1.0], "insufficient_training_pairs"),
        ([1.0, 1.0, 1.0], [0.0, 1.0, 2.0], "input_variance_below_minimum"),
        ([-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], "slope_out_of_bounds"),
    ],
)
def test_affine_fit_is_unavailable_when_training_evidence_is_invalid(
    multisine, sweep, reason
) -> None:
    fit = fit_tone_calibration(
        tone_id="tone-c",
        frequency_hz=3000.0,
        method="per_tone_affine",
        multisine_db=np.asarray(multisine),
        sweep_db=np.asarray(sweep),
        training_pair_ids=tuple(f"p{i}" for i in range(len(multisine))),
        config=_fit_config(),
    )

    assert fit.status is CalibrationStatus.UNAVAILABLE
    assert reason in fit.reason_codes
    assert fit.slope is None


def test_raw_bias_and_calibrated_residual_signs_are_fixed() -> None:
    fit = fit_tone_calibration(
        tone_id="tone-a",
        frequency_hz=1000.0,
        method="bias_only",
        multisine_db=np.asarray([2.0, 3.0, 4.0]),
        sweep_db=np.asarray([1.0, 2.0, 3.0]),
        training_pair_ids=("p1", "p2", "p3"),
        config=_fit_config(),
    )
    comparison = compare_tone_values(
        outer_fold_id="outer-1",
        evaluation_pair_ids=("e1", "e2"),
        fit=fit,
        multisine_db=np.asarray([5.0, 7.0]),
        sweep_db=np.asarray([4.0, 6.0]),
    )

    assert comparison.raw_mean_bias_db == pytest.approx(1.0)
    assert comparison.raw_rms_difference_db == pytest.approx(1.0)
    assert comparison.calibrated_mean_residual_db == pytest.approx(0.0)
    assert comparison.calibrated_rms_difference_db == pytest.approx(0.0)
    assert comparison.evaluation_pair_ids == ("e1", "e2")


def test_identity_baseline_remains_auditable_when_residual_is_large() -> None:
    fit = fit_tone_calibration(
        tone_id="tone-identity",
        frequency_hz=1000.0,
        method="identity",
        multisine_db=np.asarray([-5.0, 0.0, 5.0]),
        sweep_db=np.asarray([0.0, 5.0, 10.0]),
        training_pair_ids=("p1", "p2", "p3"),
        config=_fit_config(),
    )

    assert fit.status is CalibrationStatus.WARNING
    assert fit.slope == 1.0
    assert fit.intercept_db == 0.0
    assert "identity_baseline_residual_above_threshold" in fit.reason_codes


def _pair(pair_id: str, state: str, role: str = "development") -> MatchedModePair:
    return MatchedModePair(
        match_pair_id=pair_id,
        cross_mode_group_id=f"group-{pair_id}",
        physical_state_id=state,
        sweep_artifact_id=f"sweep-{pair_id}",
        multisine_artifact_id=f"multi-{pair_id}",
        direction_id="D000",
        direction_angle_deg=0.0,
        configuration_id="U4ENC",
        session_id="S1" if pair_id == "p1" else "S2",
        repeat_type="CONT",
        repeat_id="R1",
        reposition_round_id=None,
        assembly_id="A1",
        acquisition_block_id="B1",
        cohort_role=role,
        selection_reason="explicit fixture",
    )


def _fold() -> CrossModeFoldDefinition:
    return CrossModeFoldDefinition(
        outer_fold_id="outer-1",
        split_protocol="leave_one_session_out",
        training_pair_ids=("p1",),
        test_pair_ids=("p2",),
        held_out_cross_mode_group_ids=("group-p2",),
        held_out_physical_state_ids=("state-2",),
        training_membership_sha256=HASH,
        ordered_tone_ids=("tone-a", "tone-b"),
        selected_subset_sha256=HASH,
        candidate_universe_sha256=HASH,
        p9a_selection_scope_sha256=HASH,
        p9a_selection_artifact_sha256=HASH,
        p9a_manifest_sha256=HASH,
        p9b_result_sha256=HASH,
        p9b_manifest_sha256=HASH,
        p2b_result_sha256=HASH,
        p4b_result_sha256=HASH,
    )


def _scope() -> P9CrossModeBridgeScope:
    return P9CrossModeBridgeScope(
        schema_version="1.0.0",
        analysis_scope_id="DEV-C14-fixture",
        data_origin="simulated",
        run_purpose="software_validation",
        dataset_role="software_validation",
        calibration_lifecycle="software_validation_only",
        approval_status="not_approved",
        scientifically_eligible=False,
        deployment_eligible=False,
        canonical_analysis=False,
        mapping_direction="multisine_db_to_sweep_projection_db",
        calibration_methods=("identity", "bias_only", "per_tone_affine"),
        pairs=(_pair("p1", "state-1"), _pair("p2", "state-2")),
        outer_folds=(_fold(),),
        sealed_final_test_sample_ids=("final-1",),
        sealed_final_test_sha256=HASH,
        random_state=20260806,
    )


def test_scope_round_trip_hash_is_stable_and_held_state_is_excluded() -> None:
    scope = _scope()
    restored = P9CrossModeBridgeScope.from_dict(scope.to_dict())

    assert restored == scope
    assert restored.sha256 == scope.sha256
    assert set(restored.outer_folds[0].training_pair_ids).isdisjoint(
        restored.outer_folds[0].test_pair_ids
    )


def test_scope_rejects_held_state_in_calibration_training() -> None:
    scope = _scope()
    bad_fold = replace(scope.outer_folds[0], training_pair_ids=("p1", "p2"))

    with pytest.raises(CrossModeBridgeInputError, match="training and test pairs"):
        replace(scope, outer_folds=(bad_fold,))


def test_scope_rejects_global_or_unapproved_authority_and_final_test_inputs() -> None:
    with pytest.raises(CrossModeBridgeInputError, match="software_validation_only"):
        replace(_scope(), calibration_lifecycle="approved_real_calibration")
    with pytest.raises(CrossModeBridgeInputError, match="final_test"):
        replace(
            _scope(),
            pairs=(_pair("p1", "state-1"), _pair("p2", "state-2", "final_test")),
        )


def test_scope_rejects_one_to_many_pairing() -> None:
    scope = _scope()
    duplicate = replace(_pair("p3", "state-3"), multisine_artifact_id="multi-p2")

    with pytest.raises(CrossModeBridgeInputError, match="one-to-one"):
        replace(scope, pairs=(*scope.pairs, duplicate))


def test_scope_rejects_incomplete_loso_physical_state_group() -> None:
    pairs = (
        replace(_pair("p1", "state-1"), session_id="S1"),
        replace(_pair("p2", "state-2"), session_id="S2"),
        replace(_pair("p3", "state-3"), session_id="S2"),
    )
    fold = replace(
        _fold(),
        training_pair_ids=("p1", "p3"),
        test_pair_ids=("p2",),
        held_out_cross_mode_group_ids=("group-p2",),
        held_out_physical_state_ids=("state-2",),
    )

    with pytest.raises(CrossModeBridgeInputError, match="complete physical-state group"):
        replace(_scope(), pairs=pairs, outer_folds=(fold,))


def _analysis_fixture():
    sweep_source = generate_directional_feature_set_mock(
        feature_count=3,
        direction_order_deg=(0.0, 90.0),
        included_repeat_types=("CONT",),
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        repeat_noise_scale=0.0,
        random_state=7,
    )
    sweep = tuple(
        replace(
            item,
            normalization_method="none",
            source_magnitude_reference="reference://shared-transfer",
        )
        for item in sweep_source
    )
    slope_by_tone = np.asarray([1.1, 0.9, 1.2])
    intercept_by_tone = np.asarray([0.5, -0.25, 1.0])
    multisine = tuple(
        replace(
            item,
            sample_id=item.sample_id + "-MS",
            feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
            source_measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
            source_representation=Representation.SPARSE_TONES,
            values=(item.values - intercept_by_tone) / slope_by_tone,
            normalization_method="none",
            source_magnitude_reference="reference://shared-transfer",
            meta=replace(
                item.meta,
                sample_id=item.sample_id + "-MS",
                measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
                source_format=SourceFormat.MOCK_AUDIO,
                source_path=item.meta.source_path + "-MS",
                stimulus_id="P9C-STIMULUS",
                stimulus_hash="a" * 64,
                tone_set_id=item.tone_set_id,
                sidecar_path=item.meta.source_path + "-MS.json",
                audio_channel=0,
            ),
        )
        for item in sweep
    )
    artifacts = {}
    pairs = []
    for index, (left, right) in enumerate(zip(sweep, multisine, strict=True)):
        pair_id = f"pair-{index:03d}"
        sweep_id, multi_id = f"sweep-{index:03d}", f"multi-{index:03d}"
        artifacts[sweep_id], artifacts[multi_id] = left, right
        pairs.append(
            MatchedModePair(
                pair_id,
                f"group-{index:03d}",
                f"state-{index:03d}",
                sweep_id,
                multi_id,
                f"D{int(left.meta.angle_deg):03d}",
                float(left.meta.angle_deg),
                str(left.meta.configuration),
                left.meta.session_id,
                left.meta.repeat_type,
                left.meta.repeat_id,
                left.meta.reposition_round_id,
                left.meta.assembly_id,
                left.meta.acquisition_block_id,
                "development",
                "explicit analysis fixture",
            )
        )
    sessions = sorted({str(item.session_id) for item in pairs})
    folds = []
    feature_names = sweep[0].feature_names
    for session in sessions:
        test = tuple(item for item in pairs if item.session_id == session)
        train = tuple(item for item in pairs if item.session_id != session)
        folds.append(
            CrossModeFoldDefinition(
                outer_fold_id=f"outer-{session}",
                split_protocol="leave_one_session_out",
                training_pair_ids=tuple(item.match_pair_id for item in train),
                test_pair_ids=tuple(item.match_pair_id for item in test),
                held_out_cross_mode_group_ids=tuple(item.cross_mode_group_id for item in test),
                held_out_physical_state_ids=tuple(item.physical_state_id for item in test),
                training_membership_sha256=HASH,
                ordered_tone_ids=("tone-a", "tone-b", "tone-c"),
                selected_subset_sha256=HASH,
                candidate_universe_sha256=HASH,
                p9a_selection_scope_sha256=HASH,
                p9a_selection_artifact_sha256=HASH,
                p9a_manifest_sha256=HASH,
                p9b_result_sha256=HASH,
                p9b_manifest_sha256=HASH,
                p2b_result_sha256=HASH,
                p4b_result_sha256=HASH,
                ordered_tone_feature_names=feature_names,
                ordered_tone_frequencies_hz=(1000.0, 1010.0, 1020.0),
                ordered_tone_source_indices=(0, 1, 2),
            )
        )
    scope = P9CrossModeBridgeScope(
        "1.0.0", "analysis-fixture", "simulated", "software_validation",
        "software_validation", "software_validation_only", "not_approved",
        False, False, False, "multisine_db_to_sweep_projection_db",
        ("identity", "bias_only", "per_tone_affine"), tuple(pairs), tuple(folds),
        ("final-sealed",), HASH, 7,
        direction_order_deg=(0.0, 90.0),
        classification_models=("nearest_centroid",),
    )
    return artifacts, scope, slope_by_tone, intercept_by_tone


def test_outer_fold_bridge_recovers_affine_and_reuses_same_held_cohort() -> None:
    artifacts, scope, slopes, intercepts = _analysis_fixture()
    before = {key: feature_set_content_sha256(value) for key, value in artifacts.items()}

    result = analyze_cross_mode_bridge(
        artifacts,
        scope,
        {
            "fit": _fit_config(),
            "evaluation": {"minimum_common_tones": 2, "minimum_pair_coverage": 1.0},
            "direction_templates": {"minimum_common_tones": 2},
            "classification": {
                "minimum_training_features": 2,
                "minimum_prediction_coverage": 1.0,
            },
        },
    )

    affine = [model for model in result.calibration_models if model.method == "per_tone_affine"]
    assert len(affine) == len(scope.outer_folds)
    for model in affine:
        assert [fit.slope for fit in model.tone_fits] == pytest.approx(slopes, abs=1.0e-10)
        assert [fit.intercept_db for fit in model.tone_fits] == pytest.approx(intercepts, abs=1.0e-10)
        assert set(model.training_pair_ids).isdisjoint(model.held_out_pair_ids)
    calibrated = [
        item for item in result.tone_comparisons
        if item.method == "per_tone_affine"
    ]
    assert max(item.calibrated_rms_difference_db for item in calibrated) < 1.0e-10
    assert all(item.evaluation_pair_ids for item in calibrated)
    assert all(item.nearest_direction_matches for item in result.direction_template_comparisons if item.method == "per_tone_affine")
    assert {
        item.protocol for item in result.predictions
    } == {
        "sweep_to_multisine_uncalibrated",
        "sweep_to_multisine_calibrated",
        "sweep_to_sweep",
        "multisine_to_multisine",
    }
    assert before == {key: feature_set_content_sha256(value) for key, value in artifacts.items()}


def test_absolute_incompatibility_keeps_identity_but_blocks_fitted_calibration() -> None:
    artifacts, scope, _, _ = _analysis_fixture()
    first_multi = next(pair.multisine_artifact_id for pair in scope.pairs)
    artifacts[first_multi] = replace(
        artifacts[first_multi], source_magnitude_reference="reference://different"
    )

    result = analyze_cross_mode_bridge(
        artifacts,
        scope,
        {
            "fit": _fit_config(),
            "evaluation": {"minimum_common_tones": 2, "minimum_pair_coverage": 1.0},
            "direction_templates": {"minimum_common_tones": 2},
            "classification": {"minimum_training_features": 2, "minimum_prediction_coverage": 1.0},
        },
    )

    assert any(
        fit.status is CalibrationStatus.UNAVAILABLE
        and "absolute_comparison_unavailable" in fit.reason_codes
        for model in result.calibration_models
        if model.method != "identity"
        for fit in model.tone_fits
    )


def test_fold_evaluation_enforces_tone_and_pair_coverage_thresholds() -> None:
    artifacts, scope, _, _ = _analysis_fixture()
    test_ids = set(scope.outer_folds[0].test_pair_ids)
    for pair in scope.pairs:
        if pair.match_pair_id not in test_ids:
            continue
        feature = artifacts[pair.multisine_artifact_id]
        values = feature.values.copy()
        values[0] = np.nan
        valid = feature.valid_mask.copy()
        valid[0] = False
        artifacts[pair.multisine_artifact_id] = replace(
            feature, values=values, valid_mask=valid
        )

    result = analyze_cross_mode_bridge(
        artifacts,
        scope,
        {
            "fit": _fit_config(),
            "evaluation": {"minimum_common_tones": 3, "minimum_pair_coverage": 1.0},
            "direction_templates": {"minimum_common_tones": 2},
            "classification": {"minimum_training_features": 2, "minimum_prediction_coverage": 1.0},
        },
    )

    affected = [row for row in result.fold_evaluations if row.outer_fold_id == scope.outer_folds[0].outer_fold_id]
    assert affected
    assert all(row.status is CalibrationStatus.UNAVAILABLE for row in affected)
    assert all("common_tone_count_below_minimum" in row.reason_codes for row in affected)
    assert all("pair_coverage_below_minimum" in row.reason_codes for row in affected)

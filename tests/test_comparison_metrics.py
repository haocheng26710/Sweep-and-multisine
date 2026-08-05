from __future__ import annotations

from dataclasses import replace

import json
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.comparison_metrics import (
    ComparisonAnalysisScope,
    ScopedFeatureReference,
    ScopedMeasurementContext,
    CrossModePairSpec,
    FrequencyBand,
    compute_band_metrics,
    compare_configuration_band_metrics,
    analyze_comparison_feature_sets,
    compute_cross_mode_metrics,
    compute_tone_reliability,
    compute_weighted_distances,
    feature_frequencies_hz,
    frequency_band_mask,
)
from acoustic_encoder.dataset_quality_control import (
    DatasetQCReference,
    dataset_qc_sha256,
)
from acoustic_encoder.dataset_quality_validation import (
    run_simulated_dataset_quality_validation,
)
from acoustic_encoder.metrics import (
    AnalysisScope,
    QCInclusionPolicy,
    ScopeRole,
    SelectionPolicy,
    analyze_direction_feature_sets,
)
from acoustic_encoder.mock_data import generate_directional_feature_set_mock
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.schemas import FeatureKind, QCStatus, load_feature_set


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_frequency_band_boundaries_are_explicit() -> None:
    frequencies = np.asarray([1000.0, 2000.0, 3000.0], dtype=np.float64)

    expected = {
        "closed": [True, True, False],
        "left_closed_right_open": [True, False, False],
        "left_open_right_closed": [False, True, False],
        "open": [False, False, False],
    }
    for boundary, mask in expected.items():
        band = FrequencyBand(
            band_id=f"test-{boundary}",
            f_min_hz=1000.0,
            f_max_hz=2000.0,
            boundary=boundary,
            minimum_feature_count=1,
        )
        assert frequency_band_mask(frequencies, band).tolist() == mask


def test_dense_and_tone_feature_names_have_one_strict_frequency_parser() -> None:
    assert feature_frequencies_hz(("f_1000_hz", "f_1010.5_hz")).tolist() == [
        1000.0,
        1010.5,
    ]
    assert feature_frequencies_hz(
        ("tone_000000_1000_hz", "tone_000001_1010.5_hz")
    ).tolist() == [1000.0, 1010.5]


def _scope(features) -> AnalysisScope:
    return AnalysisScope(
        schema_version="1.1.0",
        analysis_scope_id="DEV-C7:test-scope",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=tuple(item.sample_id for item in features),
        partition=None,
        direction_order_deg=(0.0, 90.0),
        selection_policy=SelectionPolicy("test-selection"),
        qc_inclusion_policy=QCInclusionPolicy(
            "valid-warning",
            (QCStatus.VALID, QCStatus.WARNING),
        ),
    )


def _direction_config() -> dict:
    return {
        "schema_version": "1.0.0",
        "provisional": True,
        "minimum_common_valid_features": 1,
        "minimum_common_valid_fraction": 0.1,
        "minimum_direction_count": 2,
        "center_direction_matrix": False,
        "repeatability_distance_metric": "rms",
        "morphology_gain": {
            "distance_metric": "rms",
            "minimum_denominator": 1.0e-12,
        },
    }


def test_band_metrics_use_one_scope_common_mask_and_keep_unavailable_bands() -> None:
    features = list(
        generate_directional_feature_set_mock(
            direction_order_deg=(0.0, 90.0),
            feature_count=4,
            repeat_noise_scale=0.0,
        )
    )
    first = features[0]
    mask = first.valid_mask.copy()
    values = first.values.copy()
    mask[1] = False
    values[1] = np.nan
    features[0] = replace(first, valid_mask=mask, values=values)
    bands = (
        FrequencyBand("all", 1000.0, 1030.0, "closed", 2),
        FrequencyBand("empty", 9000.0, 10000.0, "closed", 1),
    )

    results = compute_band_metrics(
        tuple(features),
        _scope(features),
        bands,
        _direction_config(),
    )

    assert [item.band_id for item in results] == ["all", "empty"]
    assert results[0].feature_count == 3
    assert results[0].available
    assert results[1].feature_count == 0
    assert not results[1].available
    assert results[1].unavailable_reason == "minimum_feature_count_not_met"


def test_explicit_cross_mode_pair_uses_fixed_mask_and_multisine_minus_sweep_bias() -> None:
    sweep = generate_directional_feature_set_mock(
        direction_order_deg=(0.0,),
        feature_count=4,
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        included_repeat_types=("REPOS",),
        repeat_noise_scale=0.0,
    )[0]
    multisine = generate_directional_feature_set_mock(
        direction_order_deg=(0.0,),
        feature_count=4,
        feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        included_repeat_types=("REPOS",),
        repeat_noise_scale=0.0,
    )[0]
    multisine_meta = replace(
        multisine.meta,
        sample_id=f"{multisine.sample_id}-MS",
        source_path=f"{multisine.meta.source_path}-MS",
    )
    sweep = replace(
        sweep,
        values=np.asarray([0.0, 1.0, 2.0, 3.0]),
        normalization_method="none",
        source_magnitude_reference="reference://shared-db",
    )
    multisine = replace(
        multisine,
        sample_id=multisine_meta.sample_id,
        meta=multisine_meta,
        values=np.asarray([1.0, 2.0, np.nan, 4.0]),
        valid_mask=np.asarray([True, True, False, True]),
        normalization_method="none",
        source_magnitude_reference="reference://shared-db",
    )
    pair = CrossModePairSpec(
        match_pair_id="pair-001",
        sweep_artifact_id="sweep-001",
        multisine_artifact_id="multisine-001",
        direction_id="A000",
        direction_angle_deg=0.0,
        configuration_id="U4ENC",
        physical_state_id="state-001",
        session_id=sweep.meta.session_id,
        repeat_type=sweep.meta.repeat_type,
        repeat_id=sweep.meta.repeat_id,
        reposition_round_id=sweep.meta.reposition_round_id,
        assembly_id=sweep.meta.assembly_id,
        acquisition_block_id=sweep.meta.acquisition_block_id,
        cohort_role="development",
    )

    result = compute_cross_mode_metrics(
        {"sweep-001": sweep, "multisine-001": multisine},
        (pair,),
        minimum_common_tones=2,
        allow_centered_shape_comparison=True,
    )

    assert result.common_valid_mask.tolist() == [True, True, False, True]
    assert result.common_tone_count == 3
    assert result.missing_tone_count == 1
    assert result.pairs[0].absolute_comparison_available
    assert result.pairs[0].mean_bias_db == 1.0
    assert result.pairs[0].rms_difference_db == 1.0
    assert np.isclose(result.pairs[0].centered_rms_db, 0.0, atol=1.0e-15)
    assert [item.frequency_hz for item in result.per_tone_bias] == [
        1000.0,
        1010.0,
        1020.0,
        1030.0,
    ]
    assert result.per_tone_bias[0].mean_bias_db == 1.0
    assert result.per_tone_bias[0].pair_count == 1
    assert result.per_tone_bias[2].mean_bias_db is None
    assert result.per_tone_bias[2].missing_count == 1


def _cross_fixture():
    sweep = generate_directional_feature_set_mock(
        direction_order_deg=(0.0,), feature_count=5,
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        included_repeat_types=("REPOS",), repeat_noise_scale=0.0,
    )[0]
    multisine = generate_directional_feature_set_mock(
        direction_order_deg=(0.0,), feature_count=5,
        feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        included_repeat_types=("REPOS",), repeat_noise_scale=0.0,
    )[0]
    multisine_meta = replace(
        multisine.meta,
        sample_id=f"{multisine.sample_id}-MS",
        source_path=f"{multisine.meta.source_path}-MS",
    )
    multisine = replace(multisine, sample_id=multisine_meta.sample_id, meta=multisine_meta)
    pair = CrossModePairSpec(
        "pair", "sweep", "multisine", "A000", 0.0, "U4ENC", "state",
        sweep.meta.session_id, sweep.meta.repeat_type, sweep.meta.repeat_id,
        sweep.meta.reposition_round_id, sweep.meta.assembly_id,
        sweep.meta.acquisition_block_id, "development",
    )
    return sweep, multisine, pair


@pytest.mark.parametrize(
    ("pair_change", "message"),
    [
        ({"configuration_id": "U4SYM"}, "configuration_id"),
        ({"direction_angle_deg": 90.0}, "direction_angle_deg"),
        ({"session_id": "wrong"}, "session_id"),
        ({"repeat_type": "CONT"}, "repeat_type"),
        ({"assembly_id": "wrong"}, "assembly_id"),
    ],
)
def test_cross_mode_pair_rejects_metadata_mismatch(pair_change, message) -> None:
    sweep, multisine, pair = _cross_fixture()
    with pytest.raises(ValueError, match=message):
        compute_cross_mode_metrics(
            {"sweep": sweep, "multisine": multisine},
            (replace(pair, **pair_change),),
            minimum_common_tones=2,
            allow_centered_shape_comparison=True,
        )


def test_cross_mode_pairing_rejects_duplicate_and_one_to_many_pairs() -> None:
    sweep, multisine, pair = _cross_fixture()
    with pytest.raises(ValueError, match="duplicate"):
        compute_cross_mode_metrics(
            {"sweep": sweep, "multisine": multisine},
            (pair, pair), minimum_common_tones=2,
            allow_centered_shape_comparison=True,
        )
    with pytest.raises(ValueError, match="one-to-one"):
        compute_cross_mode_metrics(
            {"sweep": sweep, "multisine": multisine},
            (pair, replace(pair, match_pair_id="pair-2")),
            minimum_common_tones=2,
            allow_centered_shape_comparison=True,
        )


def test_cross_mode_rejects_tone_set_mismatch_without_interpolation() -> None:
    sweep, multisine, pair = _cross_fixture()
    multisine = replace(multisine, tone_set_id="different-tone-set")
    with pytest.raises(ValueError, match="tone_set_id"):
        compute_cross_mode_metrics(
            {"sweep": sweep, "multisine": multisine}, (pair,),
            minimum_common_tones=2, allow_centered_shape_comparison=True,
        )


def test_incompatible_absolute_reference_preserves_explicit_shape_only_metrics() -> None:
    sweep, multisine, pair = _cross_fixture()
    result = compute_cross_mode_metrics(
        {"sweep": sweep, "multisine": multisine}, (pair,),
        minimum_common_tones=2, allow_centered_shape_comparison=True,
    )
    row = result.pairs[0]
    assert not row.absolute_comparison_available
    assert row.absolute_unavailable_reason == "normalization_not_absolute"
    assert row.rms_difference_db is None
    assert row.mean_bias_db is None
    assert row.shape_comparison_available
    assert row.centered_rms_db is not None


def test_reliability_rejects_final_test_leakage() -> None:
    _, multisine, _ = _cross_fixture()
    with pytest.raises(ValueError, match="final_test"):
        compute_tone_reliability(
            (multisine,), {multisine.sample_id: "final_test"},
            repeat_type="REPOS", floor_db=0.1, maximum_raw_weight=100.0,
            minimum_pairs_per_tone=1, minimum_available_tones=1,
        )


def test_reliability_does_not_substitute_cont_for_missing_repos() -> None:
    features = generate_directional_feature_set_mock(
        direction_order_deg=(0.0,), feature_count=5,
        feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        included_repeat_types=("CONT",), repeat_noise_scale=0.0,
    )
    result = compute_tone_reliability(
        features, {item.sample_id: "development" for item in features},
        repeat_type="REPOS", floor_db=0.1, maximum_raw_weight=100.0,
        minimum_pairs_per_tone=1, minimum_available_tones=1,
    )
    assert not result.available
    assert result.unavailable_reason == "insufficient_reliable_tones"
    assert result.pair_counts.tolist() == [0] * 5


def test_reliability_uses_repos_floor_clip_and_mean_one_normalization() -> None:
    features = list(
        generate_directional_feature_set_mock(
            direction_order_deg=(0.0,),
            feature_count=4,
            feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
            included_repeat_types=("REPOS",),
            repeat_noise_scale=0.0,
        )
    )
    features[0] = replace(features[0], values=np.zeros(4, dtype=np.float64))
    features[1] = replace(
        features[1],
        values=np.asarray([0.05, 0.2, 0.4, 0.8], dtype=np.float64),
    )

    result = compute_tone_reliability(
        tuple(features),
        {item.sample_id: "development" for item in features},
        repeat_type="REPOS",
        floor_db=0.1,
        maximum_raw_weight=50.0,
        minimum_pairs_per_tone=1,
        minimum_available_tones=2,
    )

    assert result.available
    assert np.allclose(result.stability_db, [0.05, 0.2, 0.4, 0.8])
    assert np.isclose(result.raw_weights[0], 100.0)
    assert result.clipped_weights[0] == 50.0
    assert np.isclose(np.mean(result.normalized_weights[result.available_mask]), 1.0)
    assert result.pair_counts.tolist() == [1, 1, 1, 1]


def test_weighted_distance_has_one_auditable_formula() -> None:
    result = compute_weighted_distances(
        np.asarray([0.0, 0.0]),
        np.asarray([1.0, 3.0]),
        np.asarray([1.0, 3.0]),
    )

    assert np.isclose(result.weighted_rms, np.sqrt(7.0))
    assert np.isclose(result.weighted_euclidean, np.sqrt(28.0))


def test_configuration_comparison_uses_u4enc_minus_u4sym_and_safe_ratio() -> None:
    features = generate_directional_feature_set_mock(
        configuration="U4SYM",
        direction_order_deg=(0.0, 90.0),
        feature_count=4,
        repeat_noise_scale=0.0,
    )
    baseline = compute_band_metrics(
        features,
        _scope(features),
        (FrequencyBand("full", 1000.0, 1030.0, "closed", 2),),
        _direction_config(),
    )[0]
    baseline = replace(baseline, morphology_gain=2.0)
    candidate = replace(
        baseline,
        configuration_id="U4ENC",
        morphology_gain=5.0,
    )

    rows = compare_configuration_band_metrics(
        (baseline,),
        (candidate,),
        baseline_configuration="U4SYM",
        candidate_configuration="U4ENC",
        ratio_minimum_denominator=1.0e-12,
    )
    gain = next(item for item in rows if item.metric_id == "morphology_gain")
    assert gain.delta == 3.0
    assert gain.ratio == 2.5

    zero_rows = compare_configuration_band_metrics(
        (replace(baseline, morphology_gain=0.0),),
        (candidate,),
        baseline_configuration="U4SYM",
        candidate_configuration="U4ENC",
        ratio_minimum_denominator=1.0e-12,
    )
    zero_gain = next(item for item in zero_rows if item.metric_id == "morphology_gain")
    assert zero_gain.ratio is None
    assert zero_gain.ratio_unavailable_reason == "baseline_below_ratio_minimum"


def test_band_effective_rank_and_morphology_gain_reuse_p4a_definitions() -> None:
    features = generate_directional_feature_set_mock(
        configuration="U4ENC", direction_order_deg=(0.0, 90.0),
        feature_count=7, included_repeat_types=("REPOS",), random_state=17,
    )
    scope = _scope(features)
    p4a = analyze_direction_feature_sets(features, scope, _direction_config())
    p4b = compute_band_metrics(
        features, scope,
        (FrequencyBand("full", 1000.0, 1060.0, "closed", 2),),
        _direction_config(),
    )[0]
    assert np.isclose(p4b.effective_rank, p4a.effective_rank.value)
    assert np.isclose(p4b.morphology_gain, p4a.morphology_gain.value)


def test_configuration_comparison_rejects_preprocessing_or_mask_mismatch() -> None:
    features = generate_directional_feature_set_mock(
        configuration="U4SYM", direction_order_deg=(0.0, 90.0),
        feature_count=4, repeat_noise_scale=0.0,
    )
    baseline = compute_band_metrics(
        features, _scope(features),
        (FrequencyBand("full", 1000.0, 1030.0, "closed", 2),),
        _direction_config(),
    )[0]
    with pytest.raises(ValueError, match="scope/mask/preprocessing"):
        compare_configuration_band_metrics(
            (baseline,),
            (replace(baseline, configuration_id="U4ENC", preprocessing_id="other"),),
            baseline_configuration="U4SYM", candidate_configuration="U4ENC",
            ratio_minimum_denominator=1.0e-12,
        )


def test_top_level_u4_comparison_rejects_mismatched_experimental_design() -> None:
    sym = generate_directional_feature_set_mock(
        configuration="U4SYM", direction_order_deg=(0.0, 90.0), feature_count=7,
    )
    enc = generate_directional_feature_set_mock(
        configuration="U4ENC", direction_order_deg=(0.0, 90.0), feature_count=7,
    )[:-1]
    features = (*sym, *enc)
    artifacts = {f"f-{index:03d}": item for index, item in enumerate(features)}
    base = AnalysisScope(
        schema_version="1.1.0", analysis_scope_id="DEV-C7:u4-mismatch",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=tuple(item.sample_id for item in features), partition=None,
        direction_order_deg=(0.0, 90.0),
        selection_policy=SelectionPolicy("explicit"),
        qc_inclusion_policy=QCInclusionPolicy(
            "valid-warning", (QCStatus.VALID, QCStatus.WARNING)
        ),
    )
    comparison_scope = ComparisonAnalysisScope(
        "1.0.0", base,
        tuple(
            ScopedMeasurementContext(
                item.sample_id, "development", f"A{int(item.meta.angle_deg):03d}",
                f"state:{item.sample_id}", "explicit mismatch test",
            )
            for item in features
        ),
        tuple(
            ScopedFeatureReference.from_feature_set(key, item, primary_for_dataset_qc=False)
            for key, item in artifacts.items()
        ),
        (),
    )
    with pytest.raises(ValueError, match="experimental design/scope mismatch"):
        analyze_comparison_feature_sets(
            artifacts, comparison_scope, _direction_config(),
            {
                "frequency_bands": [
                    {"band_id": "full", "f_min_hz": 1000.0, "f_max_hz": 1060.0,
                     "boundary": "closed", "minimum_feature_count": 2}
                ],
                "configuration_comparison": {
                    "baseline_configuration": "U4SYM",
                    "candidate_configuration": "U4ENC",
                    "ratio_minimum_denominator": 1.0e-12,
                },
                "cross_mode": {"minimum_common_tones": 2,
                               "allow_centered_shape_comparison": True},
            },
        )


def test_top_level_cross_mode_pair_rejects_scope_physical_state_mismatch() -> None:
    sweep, multisine, pair = _cross_fixture()
    artifacts = {"sweep": sweep, "multisine": multisine}
    base = AnalysisScope(
        schema_version="1.1.0", analysis_scope_id="DEV-C7:state-mismatch",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=(sweep.sample_id, multisine.sample_id), partition=None,
        direction_order_deg=(0.0,), selection_policy=SelectionPolicy("explicit"),
        qc_inclusion_policy=QCInclusionPolicy(
            "valid-warning", (QCStatus.VALID, QCStatus.WARNING)
        ),
    )
    scope = ComparisonAnalysisScope(
        "1.0.0", base,
        (
            ScopedMeasurementContext(sweep.sample_id, "development", "A000", "state", "explicit"),
            ScopedMeasurementContext(multisine.sample_id, "development", "A000", "wrong-state", "explicit"),
        ),
        tuple(
            ScopedFeatureReference.from_feature_set(key, item, primary_for_dataset_qc=False)
            for key, item in artifacts.items()
        ),
        (pair,),
    )
    with pytest.raises(ValueError, match="direction/state/role mismatch"):
        analyze_comparison_feature_sets(
            artifacts, scope, _direction_config(),
            {
                "frequency_bands": [
                    {"band_id": "full", "f_min_hz": 1000.0, "f_max_hz": 1040.0,
                     "boundary": "closed", "minimum_feature_count": 2}
                ],
                "configuration_comparison": {
                    "baseline_configuration": "U4SYM", "candidate_configuration": "U4ENC",
                    "ratio_minimum_denominator": 1.0e-12,
                },
                "cross_mode": {"minimum_common_tones": 2,
                               "allow_centered_shape_comparison": True},
                "reliability": {
                    "source_feature_kind": "tone_measurement_from_multisine",
                    "repeat_type": "REPOS", "floor_db": 0.1,
                    "maximum_raw_weight": 100.0, "minimum_pairs_per_tone": 1,
                    "minimum_available_tones": 2,
                },
            },
        )


def test_current_noncanonical_p2b_fixture_is_rejected_by_canonical_p4b(
    tmp_path: Path,
) -> None:
    validation = run_simulated_dataset_quality_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c6_dataset_qc.yaml",
        output_root=tmp_path / "outputs",
        run_id="DEV-C7-P2B-REJECT",
        feature_count=7,
    )
    assert not validation.result.canonical_ready
    payload = json.loads(validation.input_manifest_path.read_text(encoding="utf-8"))
    features = tuple(
        load_feature_set(Path(item["feature_base_path"]))
        for item in payload["measurements"]
    )
    base_scope = AnalysisScope(
        schema_version="1.1.0",
        analysis_scope_id=validation.result.analysis_scope_id,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=validation.result.scoped_sample_ids,
        partition=None,
        direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        selection_policy=SelectionPolicy("canonical-test"),
        qc_inclusion_policy=QCInclusionPolicy(
            "valid-warning",
            (QCStatus.VALID, QCStatus.WARNING),
        ),
        analysis_tier="canonical_cohort",
        dataset_qc_reference=DatasetQCReference(
            validation.result.analysis_scope_id,
            dataset_qc_sha256(validation.result),
        ),
    )
    comparison_scope = ComparisonAnalysisScope(
        schema_version="1.0.0",
        analysis_scope=base_scope,
        measurements=tuple(
            ScopedMeasurementContext(
                sample_id=item.sample_id,
                cohort_role="development",
                direction_id=f"A{int(item.meta.angle_deg):03d}",
                physical_state_id=f"state:{item.sample_id}",
                selection_reason="explicit canonical rejection fixture",
            )
            for item in features
        ),
        feature_references=tuple(
            ScopedFeatureReference.from_feature_set(
                f"feature-{index:03d}", item, primary_for_dataset_qc=True
            )
            for index, item in enumerate(features)
        ),
        cross_mode_pairs=(),
    )

    with np.testing.assert_raises_regex(ValueError, "not canonical-ready"):
        analyze_comparison_feature_sets(
            {f"feature-{index:03d}": item for index, item in enumerate(features)},
            comparison_scope,
            _direction_config(),
            {
                "frequency_bands": [
                    {
                        "band_id": "full",
                        "f_min_hz": 1000.0,
                        "f_max_hz": 1060.0,
                        "boundary": "closed",
                        "minimum_feature_count": 2,
                    }
                ],
                "configuration_comparison": {
                    "baseline_configuration": "U4SYM",
                    "candidate_configuration": "U4ENC",
                    "ratio_minimum_denominator": 1.0e-12,
                },
                "cross_mode": {
                    "minimum_common_tones": 2,
                    "allow_centered_shape_comparison": True,
                },
            },
            dataset_qc_result=validation.result,
        )


def test_canonical_ready_simulated_fixture_exercises_canonical_p4b_without_science_claim(
    tmp_path: Path,
) -> None:
    validation = run_simulated_dataset_quality_validation(
        project_root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "validation_dev_c6_dataset_qc.yaml",
        output_root=tmp_path / "outputs",
        run_id="DEV-C7-P2B-PASS",
        feature_count=7,
        canonical_ready_fixture=True,
    )
    payload = json.loads(validation.input_manifest_path.read_text(encoding="utf-8"))
    features = tuple(
        load_feature_set(Path(item["feature_base_path"]))
        for item in payload["measurements"]
    )
    base_scope = AnalysisScope(
        schema_version="1.1.0",
        analysis_scope_id=validation.result.analysis_scope_id,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=validation.result.scoped_sample_ids,
        partition=None,
        direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        selection_policy=SelectionPolicy("canonical-pass"),
        qc_inclusion_policy=QCInclusionPolicy(
            "valid-warning",
            (QCStatus.VALID, QCStatus.WARNING),
        ),
        analysis_tier="canonical_cohort",
        dataset_qc_reference=DatasetQCReference(
            validation.result.analysis_scope_id,
            dataset_qc_sha256(validation.result),
        ),
    )
    comparison_scope = ComparisonAnalysisScope(
        schema_version="1.0.0",
        analysis_scope=base_scope,
        measurements=tuple(
            ScopedMeasurementContext(
                item.sample_id,
                "development",
                f"A{int(item.meta.angle_deg):03d}",
                f"state:{item.sample_id}",
                "explicit canonical pass fixture",
            )
            for item in features
        ),
        feature_references=tuple(
            ScopedFeatureReference.from_feature_set(
                f"feature-{index:03d}", item, primary_for_dataset_qc=True
            )
            for index, item in enumerate(features)
        ),
        cross_mode_pairs=(),
    )

    result = analyze_comparison_feature_sets(
        {f"feature-{index:03d}": item for index, item in enumerate(features)},
        comparison_scope,
        _direction_config(),
        {
            "frequency_bands": [
                {
                    "band_id": "full",
                    "f_min_hz": 1000.0,
                    "f_max_hz": 1060.0,
                    "boundary": "closed",
                    "minimum_feature_count": 2,
                }
            ],
            "configuration_comparison": {
                "baseline_configuration": "U4SYM",
                "candidate_configuration": "U4ENC",
                "ratio_minimum_denominator": 1.0e-12,
            },
            "cross_mode": {
                "minimum_common_tones": 2,
                "allow_centered_shape_comparison": True,
            },
        },
        dataset_qc_result=validation.result,
    )

    assert result.processing_status == "completed"
    assert result.canonical_analysis
    assert result.p2b_canonical_ready is True
    assert result.scientifically_eligible is False

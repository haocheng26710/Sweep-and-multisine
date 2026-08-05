from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import hashlib
from pathlib import Path

import numpy as np
import pytest

from acoustic_encoder.metrics import (
    AnalysisTier,
    AnalysisScope,
    QCInclusionPolicy,
    ScopeRole,
    SelectionPolicy,
    analyze_direction_feature_sets,
    compute_effective_rank,
    feature_set_content_sha256,
    frozen_partition_sha256,
    FrozenPartition,
)
from acoustic_encoder.dataset_quality_control import (
    CohortRole,
    DatasetQCReference,
    DatasetQCScope,
    DatasetScopeMember,
    ExpectedCondition,
    dataset_qc_sha256,
    evaluate_dataset_quality,
)
from acoustic_encoder.config import load_config
from acoustic_encoder.quality_control import (
    MeasurementQCResult,
    UnavailablePolicy,
    measurement_qc_sha256,
)
from acoustic_encoder.research_gate import ResearchGateError, RunPurpose
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    QCStatus,
    Representation,
    SourceFormat,
    SpectrumData,
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _source_hash(sample_id: str) -> str:
    return hashlib.sha256(sample_id.encode("utf-8")).hexdigest()


def _feature(
    sample_id: str,
    angle_deg: float,
    values: tuple[float, ...],
    *,
    valid_mask: tuple[bool, ...] | None = None,
    repeat_type: str = "CONT",
    repeat_id: str = "R01",
    session_id: str = "S01",
    reposition_round_id: str | None = None,
    assembly_id: str | None = None,
    acquisition_block_id: str | None = "B01",
    source_qc_status: QCStatus | None = QCStatus.VALID,
    human_valid: bool = True,
    manual_review_reasons: tuple[str, ...] = (),
) -> FeatureSet:
    meta = MeasurementMeta(
        sample_id=sample_id,
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration="U4ENC",
        angle_deg=angle_deg,
        session_id=session_id,
        repeat_type=repeat_type,
        repeat_id=repeat_id,
        reposition_round_id=reposition_round_id,
        assembly_id=assembly_id,
        acquisition_block_id=acquisition_block_id,
        experiment_step="DEV_C5",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path=f"mock://{sample_id}",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=_source_hash(sample_id),
        provenance_uri="mock://dev-c5",
        eligible_for_scientific_analysis=False,
        valid=human_valid,
        exclusion_reason=None if human_valid else "human exclusion fixture",
        manual_review_reasons=manual_review_reasons,
    )
    mask = (
        np.ones(len(values), dtype=bool)
        if valid_mask is None
        else np.asarray(valid_mask, dtype=bool)
    )
    return FeatureSet(
        sample_id=sample_id,
        feature_schema_version=SCHEMA_VERSION_QUARTET["feature_schema_version"],
        feature_kind=FeatureKind.DENSE_DEMEANED_DB,
        feature_names=tuple(f"f_{1000 + 10 * index}_hz" for index in range(len(values))),
        values=np.asarray(values, dtype=np.float64),
        valid_mask=mask,
        units=("dB",) * len(values),
        source_measurement_mode=MeasurementMode.REW_SWEEP,
        source_representation=Representation.DENSE_SPECTRUM,
        preprocessing_id="sha256:" + "a" * 64,
        meta=meta,
        source_qc_status=source_qc_status,
        source_qc_sha256="sha256:" + "b" * 64,
        source_qc_eligible_for_downstream=True,
    )


def _scope(sample_ids: tuple[str, ...]) -> AnalysisScope:
    return AnalysisScope(
        schema_version="1.0.0",
        analysis_scope_id="dev-c5-four-direction",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        scope_role=ScopeRole.DEVELOPMENT,
        included_sample_ids=sample_ids,
        partition=None,
        direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        selection_policy=SelectionPolicy(
            policy_id="explicit-human-valid-no-review",
            require_human_valid=True,
            exclude_manual_review=True,
        ),
        qc_inclusion_policy=QCInclusionPolicy(
            policy_id="valid-and-warning",
            included_statuses=(QCStatus.VALID, QCStatus.WARNING),
            missing_status="exclude",
            allow_exclude_candidate=False,
        ),
    )


def _metrics_config() -> dict:
    return {
        "schema_version": "1.0.0",
        "provisional": True,
        "minimum_common_valid_features": 2,
        "minimum_common_valid_fraction": 0.5,
        "minimum_direction_count": 2,
        "center_direction_matrix": False,
        "repeatability_distance_metric": "rms",
        "morphology_gain": {
            "distance_metric": "rms",
            "minimum_denominator": 1.0e-12,
        },
    }


def test_feature_set_only_four_direction_tracer_builds_dictionary() -> None:
    features = tuple(
        _feature(f"A{angle:03d}", float(angle), (index, index + 1, index + 2))
        for index, angle in enumerate((0, 90, 180, 270))
    )

    result = analyze_direction_feature_sets(
        features,
        _scope(tuple(feature.sample_id for feature in features)),
        _metrics_config(),
    )

    assert result.processing_status == "completed"
    assert result.selected_sample_ids == ("A000", "A090", "A180", "A270")
    np.testing.assert_array_equal(result.common_valid_mask, [True, True, True])
    assert result.direction_order_deg == (0.0, 90.0, 180.0, 270.0)
    assert tuple(template.sample_count for template in result.direction_templates) == (
        1,
        1,
        1,
        1,
    )
    np.testing.assert_allclose(result.direction_templates[2].mean_values, [2, 3, 4])
    assert result.effective_rank.matrix_shape == (4, 3)
    assert not result.effective_rank.centered


def test_canonical_p4_requires_matching_dataset_qc_result() -> None:
    features = tuple(
        _feature(f"A{angle:03d}", float(angle), (index, index + 1, index + 2))
        for index, angle in enumerate((0, 90, 180, 270))
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        schema_version="1.1.0",
        analysis_tier=AnalysisTier.CANONICAL_COHORT,
        dataset_qc_reference=DatasetQCReference(
            analysis_scope_id="dev-c5-four-direction",
            dataset_qc_result_sha256="sha256:" + "0" * 64,
        ),
    )

    with pytest.raises(ValueError, match="canonical.*DatasetQCResult"):
        analyze_direction_feature_sets(features, scope, _metrics_config())


def test_canonical_p4_accepts_exact_scope_and_dataset_qc_hash() -> None:
    original = tuple(
        _feature(f"A{angle:03d}", float(angle), (index, index + 1, index + 2))
        for index, angle in enumerate((0, 90, 180, 270))
    )
    qcs = tuple(
        MeasurementQCResult(
            qc_schema_version="1.0.0",
            sample_id=feature.sample_id,
            measurement_mode=feature.source_measurement_mode,
            data_origin=feature.meta.data_origin,
            dataset_role=feature.meta.dataset_role,
            run_purpose=RunPurpose.SOFTWARE_VALIDATION,
            checks=(),
            unavailable_required_policy=UnavailablePolicy.PRESERVE,
            manual_review_reasons=(),
            human_valid=True,
            human_exclusion_reason=None,
            scientifically_eligible=False,
        )
        for feature in original
    )
    features = tuple(
        replace(
            feature,
            source_qc_sha256=measurement_qc_sha256(qc),
            source_qc_eligible_for_downstream=True,
        )
        for feature, qc in zip(original, qcs, strict=True)
    )
    scope_id = "canonical-four-direction"
    dataset_scope = DatasetQCScope(
        schema_version="1.0.0",
        analysis_scope_id=scope_id,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        members=tuple(
            DatasetScopeMember(
                feature.sample_id,
                CohortRole.DEVELOPMENT,
                f"condition-{feature.sample_id}",
                "explicit canonical fixture",
            )
            for feature in features
        ),
        expected_conditions=tuple(
            ExpectedCondition(
                condition_id=f"condition-{feature.sample_id}",
                cohort_role=CohortRole.DEVELOPMENT,
                measurement_mode=feature.source_measurement_mode,
                configuration_id="U4ENC",
                direction_id=feature.sample_id,
                direction_angle_deg=float(feature.meta.angle_deg),
                session_id="S01",
                repeat_type="CONT",
                reposition_round_id=None,
                assembly_id=None,
                acquisition_block_id="B01",
                expected_count=1,
            )
            for feature in features
        ),
    )
    dataset_config = deepcopy(
        load_config(Path(__file__).resolve().parents[1] / "config" / "default.yaml")[
            "dataset_quality_control"
        ]
    )
    dataset_config["aggregation"]["required_unavailable_policy"] = "preserve"
    dataset_config["aggregation"]["canonical_block_on_required_unavailable"] = False
    dataset_result = evaluate_dataset_quality(
        features,
        qcs,
        dataset_scope,
        dataset_config,
    )
    assert dataset_result.canonical_ready is True
    analysis_scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        schema_version="1.1.0",
        analysis_scope_id=scope_id,
        analysis_tier=AnalysisTier.CANONICAL_COHORT,
        dataset_qc_reference=DatasetQCReference(
            analysis_scope_id=scope_id,
            dataset_qc_result_sha256=dataset_qc_sha256(dataset_result),
        ),
    )

    metrics = analyze_direction_feature_sets(
        features,
        analysis_scope,
        _metrics_config(),
        dataset_result,
    )

    assert metrics.processing_status == "completed"


def test_p4_rejects_spectrum_data_instead_of_reading_pre_feature_input() -> None:
    feature = _feature("A000", 0.0, (1.0, 2.0, 3.0))
    spectrum = SpectrumData(
        frequency_hz=np.asarray([1000.0, 1010.0, 1020.0]),
        magnitude_db=np.asarray([1.0, 2.0, 3.0]),
        valid_mask=np.ones(3, dtype=bool),
        representation=Representation.DENSE_SPECTRUM,
        phase_status=PhaseStatus.UNAVAILABLE,
        quality_metrics={},
        meta=feature.meta,
    )

    with pytest.raises(TypeError, match="FeatureSet objects only"):
        analyze_direction_feature_sets(
            [spectrum],  # type: ignore[list-item]
            _scope((feature.sample_id,)),
            _metrics_config(),
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("configuration", "configurations"),
        ("feature_kind", "feature_kind"),
        ("preprocessing", "preprocessing_id"),
        ("feature_schema", "schema versions"),
        ("feature_names", "feature_names/order"),
        ("units", "units mismatch"),
        ("representation", "source representations"),
    ],
)
def test_metric_group_rejects_any_feature_identity_mismatch(
    case: str,
    message: str,
) -> None:
    first = _feature("A000-R01", 0.0, (1.0, 2.0, 3.0))
    second = _feature("A090-R01", 90.0, (2.0, 3.0, 4.0))
    if case == "configuration":
        second = replace(second, meta=replace(second.meta, configuration="U4SYM"))
    elif case == "feature_kind":
        second = replace(second, feature_kind=FeatureKind.DENSE_ZSCORE)
    elif case == "preprocessing":
        second = replace(second, preprocessing_id="sha256:" + "c" * 64)
    elif case == "feature_schema":
        second = replace(second, feature_schema_version="999.0.0")
    elif case == "feature_names":
        second = replace(
            second,
            feature_names=tuple(reversed(second.feature_names)),
        )
    elif case == "units":
        second = replace(second, units=("dimensionless",) * 3)
    elif case == "representation":
        second = replace(second, source_representation=Representation.SPARSE_TONES)

    with pytest.raises(ValueError, match=message):
        analyze_direction_feature_sets(
            [first, second],
            _scope((first.sample_id, second.sample_id)),
            _metrics_config(),
        )


@pytest.mark.parametrize(
    ("feature_kind", "source_representation", "message"),
    [
        (
            FeatureKind.DENSE_DEMEANED_DB,
            Representation.SPARSE_TONES,
            "combination is invalid",
        ),
        (
            FeatureKind.HR_BAND_ENERGY,
            Representation.DENSE_SPECTRUM,
            "unsupported feature_kind",
        ),
    ],
)
def test_p4a_rejects_semantically_invalid_or_out_of_scope_feature_kinds(
    feature_kind: FeatureKind,
    source_representation: Representation,
    message: str,
) -> None:
    feature = replace(
        _feature("A000", 0.0, (1.0, 2.0, 3.0)),
        feature_kind=feature_kind,
        source_representation=source_representation,
    )

    with pytest.raises(ValueError, match=message):
        analyze_direction_feature_sets(
            (feature,),
            _scope((feature.sample_id,)),
            _metrics_config(),
        )


def _as_tone_feature(feature: FeatureSet, *, tone_set_id: str) -> FeatureSet:
    return replace(
        feature,
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        feature_names=(
            "tone_000000_1000_hz",
            "tone_000001_1010_hz",
            "tone_000002_1020_hz",
        ),
        tone_set_id=tone_set_id,
        tone_set_sha256="c" * 64,
        tone_schema_id="sha256:" + "d" * 64,
        normalization_method="subtract_mean_db",
        source_magnitude_quantity="spl",
        source_phase_status=PhaseStatus.UNAVAILABLE,
    )


def test_tone_metric_group_rejects_tone_set_identity_mismatch() -> None:
    first = _as_tone_feature(
        _feature("A000-R01", 0.0, (1.0, 2.0, 3.0)),
        tone_set_id="tones-a",
    )
    second = _as_tone_feature(
        _feature("A090-R01", 90.0, (2.0, 3.0, 4.0)),
        tone_set_id="tones-b",
    )

    with pytest.raises(ValueError, match="tone-set identity"):
        analyze_direction_feature_sets(
            [first, second],
            _scope((first.sample_id, second.sample_id)),
            _metrics_config(),
        )


def test_direction_template_distance_matrices_match_hand_calculations() -> None:
    x = np.asarray([1.0, 2.0, 3.0])
    y = np.asarray([1.0, 2.0, 5.0])
    features = (
        _feature("A000", 0.0, tuple(x)),
        _feature("A090", 90.0, tuple(y)),
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        direction_order_deg=(0.0, 90.0),
    )

    result = analyze_direction_feature_sets(features, scope, _metrics_config())

    pearson = result.matrices["pearson"]
    cosine = result.matrices["cosine"]
    euclidean = result.matrices["euclidean"]
    rms = result.matrices["rms"]
    median_absolute = result.matrices["median_absolute_difference"]
    assert pearson.values[0, 1] == pytest.approx(np.corrcoef(x, y)[0, 1])
    assert cosine.values[0, 1] == pytest.approx(
        float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y)))
    )
    assert euclidean.values[0, 1] == pytest.approx(2.0)
    assert rms.values[0, 1] == pytest.approx(2.0 / np.sqrt(3.0))
    assert median_absolute.values[0, 1] == pytest.approx(0.0)
    for matrix in result.matrices.values():
        np.testing.assert_array_equal(matrix.values, matrix.values.T)
        assert matrix.feature_count == 3
    np.testing.assert_allclose(np.diag(pearson.values), 1.0)
    np.testing.assert_allclose(np.diag(cosine.values), 1.0)
    np.testing.assert_allclose(np.diag(euclidean.values), 0.0)
    np.testing.assert_allclose(np.diag(rms.values), 0.0)
    np.testing.assert_allclose(np.diag(median_absolute.values), 0.0)


def test_constant_pearson_and_zero_norm_cosine_are_unavailable_not_zero() -> None:
    features = (
        _feature("A000", 0.0, (1.0, 1.0, 1.0)),
        _feature("A090", 90.0, (0.0, 0.0, 0.0)),
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        direction_order_deg=(0.0, 90.0),
    )

    result = analyze_direction_feature_sets(features, scope, _metrics_config())

    pearson = result.matrices["pearson"]
    cosine = result.matrices["cosine"]
    assert not np.any(pearson.available)
    assert np.all(np.isnan(pearson.values))
    assert pearson.unavailable_reasons[0][1] == "constant_vector"
    assert not cosine.available[0, 1]
    assert np.isnan(cosine.values[0, 1])
    assert cosine.unavailable_reasons[0][1] == "zero_norm_vector"


def test_effective_rank_uses_singular_values_not_squared_variance() -> None:
    rank_one = compute_effective_rank(
        np.asarray([[1.0, 2.0], [2.0, 4.0]]),
        center_directions=False,
    )
    orthogonal = compute_effective_rank(
        np.eye(3, dtype=np.float64),
        center_directions=False,
    )
    zero = compute_effective_rank(
        np.zeros((2, 3), dtype=np.float64),
        center_directions=False,
    )

    assert rank_one.available
    assert rank_one.value == pytest.approx(1.0, abs=1.0e-12)
    assert orthogonal.value == pytest.approx(3.0)
    np.testing.assert_allclose(orthogonal.proportions, [1 / 3, 1 / 3, 1 / 3])
    assert not zero.available
    assert zero.value is None
    assert zero.unavailable_reason == "all_singular_values_zero"
    assert rank_one.matrix_shape == (2, 2)
    assert not rank_one.centered


def test_effective_rank_centering_is_explicit_and_recorded() -> None:
    matrix = np.eye(2, dtype=np.float64)

    uncentered = compute_effective_rank(matrix, center_directions=False)
    centered = compute_effective_rank(matrix, center_directions=True)

    assert uncentered.value == pytest.approx(2.0)
    assert centered.value == pytest.approx(1.0)
    assert not uncentered.centered
    assert centered.centered


def test_selection_policy_audits_warning_exclude_human_and_unrequested_samples() -> None:
    valid = _feature("valid", 0.0, (1.0, 2.0, 3.0))
    warning = _feature(
        "warning",
        90.0,
        (2.0, 3.0, 4.0),
        source_qc_status=QCStatus.WARNING,
    )
    warning = replace(
        warning,
        source_qc_warning_reasons=("phase unavailable",),
        source_qc_unavailable_checks=("rew_headroom",),
    )
    exclude = _feature(
        "exclude",
        180.0,
        (3.0, 4.0, 5.0),
        source_qc_status=QCStatus.EXCLUDE_CANDIDATE,
    )
    exclude = replace(
        exclude,
        source_qc_exclude_candidate_reasons=("frequency coverage",),
    )
    human_invalid = _feature(
        "human-invalid",
        270.0,
        (4.0, 5.0, 6.0),
        human_valid=False,
    )
    unrequested = _feature("unrequested", 0.0, (5.0, 6.0, 7.0))
    scope = _scope(("valid", "warning", "exclude", "human-invalid"))

    result = analyze_direction_feature_sets(
        [valid, warning, exclude, human_invalid, unrequested],
        scope,
        _metrics_config(),
    )

    assert result.selected_sample_ids == ("valid", "warning")
    audit = {record.sample_id: record for record in result.selection_audit}
    assert audit["warning"].selected
    assert audit["warning"].source_qc_warning_reasons == ("phase unavailable",)
    assert audit["warning"].source_qc_unavailable_checks == ("rew_headroom",)
    assert audit["exclude"].reasons == (
        "qc_status_not_included:exclude_candidate",
    )
    assert audit["exclude"].source_qc_exclude_candidate_reasons == (
        "frequency coverage",
    )
    assert "human_valid_false" in audit["human-invalid"].reasons
    assert audit["unrequested"].reasons == ("not_requested_by_scope",)

    valid_only_scope = replace(
        scope,
        qc_inclusion_policy=QCInclusionPolicy(
            policy_id="valid-only",
            included_statuses=(QCStatus.VALID,),
            missing_status="exclude",
            allow_exclude_candidate=False,
        ),
    )
    valid_only = analyze_direction_feature_sets(
        [valid, warning, exclude, human_invalid],
        valid_only_scope,
        _metrics_config(),
    )
    assert valid_only.selected_sample_ids == ("valid",)


def test_common_valid_features_are_intersection_without_mutating_inputs() -> None:
    first = _feature(
        "A000",
        0.0,
        (1.0, 2.0, 3.0),
        valid_mask=(True, True, False),
    )
    second = _feature(
        "A090",
        90.0,
        (2.0, 3.0, 4.0),
        valid_mask=(True, False, True),
    )
    original_masks = (first.valid_mask.copy(), second.valid_mask.copy())
    scope = replace(
        _scope((first.sample_id, second.sample_id)),
        direction_order_deg=(0.0, 90.0),
    )

    result = analyze_direction_feature_sets(
        [first, second],
        scope,
        _metrics_config(),
    )

    np.testing.assert_array_equal(result.common_valid_mask, [True, False, False])
    assert result.processing_status == "failed"
    assert result.common_valid_feature_count == 1
    assert result.per_sample_missing_count == {"A000": 1, "A090": 1}
    np.testing.assert_array_equal(first.valid_mask, original_masks[0])
    np.testing.assert_array_equal(second.valid_mask, original_masks[1])


def test_simulated_features_are_rejected_from_research_analysis() -> None:
    feature = _feature("A000", 0.0, (1.0, 2.0, 3.0))
    scope = replace(
        _scope((feature.sample_id,)),
        run_purpose=RunPurpose.RESEARCH_ANALYSIS,
        direction_order_deg=(0.0,),
    )

    with pytest.raises(ResearchGateError, match="eligible real_experiment"):
        analyze_direction_feature_sets([feature], scope, _metrics_config())


def test_repos_pairs_and_sample_pair_morphology_gain_match_hand_calculation() -> None:
    features = (
        _feature(
            "A000-P1",
            0.0,
            (0.0, 0.0),
            repeat_type="REPOS",
            repeat_id="R01",
            reposition_round_id="P01",
            assembly_id="AS01",
        ),
        _feature(
            "A000-P2",
            0.0,
            (1.0, 1.0),
            repeat_type="REPOS",
            repeat_id="R02",
            reposition_round_id="P02",
            assembly_id="AS01",
        ),
        _feature(
            "A090-P1",
            90.0,
            (10.0, 10.0),
            repeat_type="REPOS",
            repeat_id="R01",
            reposition_round_id="P01",
            assembly_id="AS01",
        ),
        _feature(
            "A090-P2",
            90.0,
            (11.0, 11.0),
            repeat_type="REPOS",
            repeat_id="R02",
            reposition_round_id="P02",
            assembly_id="AS01",
        ),
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        direction_order_deg=(0.0, 90.0),
    )

    result = analyze_direction_feature_sets(features, scope, _metrics_config())

    repos_pairs = [
        pair
        for pair in result.repeatability_pairs
        if pair.repeat_type == "REPOS" and pair.constructed
    ]
    assert len(repos_pairs) == 2
    assert {pair.pair_id for pair in repos_pairs} == {
        "A000-P1__A000-P2",
        "A090-P1__A090-P2",
    }
    assert all(pair.distances["rms"] == pytest.approx(1.0) for pair in repos_pairs)
    assert len(result.between_direction_pairs) == 4
    assert result.morphology_gain.available
    assert result.morphology_gain.numerator == pytest.approx(10.0)
    assert result.morphology_gain.denominator == pytest.approx(1.0)
    assert result.morphology_gain.value == pytest.approx(10.0)
    assert result.morphology_gain.between_pair_count == 4
    assert result.morphology_gain.reposition_pair_count == 2


def test_repeat_pair_rules_are_unique_and_missing_group_ids_are_not_guessed() -> None:
    features = (
        _feature("C1", 0.0, (0.0, 0.0), repeat_id="R01"),
        _feature("C2", 0.0, (0.1, 0.1), repeat_id="R02"),
        _feature("C3", 0.0, (0.2, 0.2), repeat_id="R03"),
        _feature(
            "P1",
            0.0,
            (0.0, 0.0),
            repeat_type="REPOS",
            repeat_id="R01",
            reposition_round_id="P01",
            assembly_id=None,
        ),
        _feature(
            "P2",
            0.0,
            (1.0, 1.0),
            repeat_type="REPOS",
            repeat_id="R02",
            reposition_round_id="P02",
            assembly_id=None,
        ),
        _feature(
            "M1",
            0.0,
            (0.0, 0.0),
            repeat_type="REASM",
            repeat_id="R01",
            assembly_id="AS01",
        ),
        _feature(
            "M2",
            0.0,
            (2.0, 2.0),
            repeat_type="REASM",
            repeat_id="R02",
            assembly_id="AS02",
        ),
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        direction_order_deg=(0.0,),
    )

    result = analyze_direction_feature_sets(features, scope, _metrics_config())

    cont = [pair for pair in result.repeatability_pairs if pair.repeat_type == "CONT"]
    repos = [pair for pair in result.repeatability_pairs if pair.repeat_type == "REPOS"]
    reasm = [pair for pair in result.repeatability_pairs if pair.repeat_type == "REASM"]
    assert len(cont) == 3
    assert len({pair.pair_id for pair in cont}) == 3
    assert all(pair.left_sample_id != pair.right_sample_id for pair in cont)
    assert len(repos) == 1 and not repos[0].constructed
    assert repos[0].unavailable_reason == "missing_assembly_id"
    assert len(reasm) == 1 and reasm[0].constructed
    summaries = {item.repeat_type: item for item in result.repeatability_summaries}
    assert summaries["CONT"].pair_count == 3
    assert summaries["REPOS"].pair_count == 0
    assert summaries["REPOS"].unavailable_candidate_count == 1
    assert summaries["REASM"].pair_count == 1


def test_morphology_gain_is_unavailable_without_repos_or_with_zero_denominator() -> None:
    no_repos = (
        _feature("A000-C1", 0.0, (0.0, 0.0), repeat_id="R01"),
        _feature("A090-C1", 90.0, (10.0, 10.0), repeat_id="R01"),
    )
    no_repos_scope = replace(
        _scope(tuple(feature.sample_id for feature in no_repos)),
        direction_order_deg=(0.0, 90.0),
    )
    unavailable = analyze_direction_feature_sets(
        no_repos,
        no_repos_scope,
        _metrics_config(),
    )
    assert not unavailable.morphology_gain.available
    assert unavailable.morphology_gain.unavailable_reason == (
        "reposition_pairs_unavailable"
    )

    zero_repos = (
        _feature(
            "A000-P1",
            0.0,
            (0.0, 0.0),
            repeat_type="REPOS",
            repeat_id="R01",
            reposition_round_id="P01",
            assembly_id="AS01",
        ),
        _feature(
            "A000-P2",
            0.0,
            (0.0, 0.0),
            repeat_type="REPOS",
            repeat_id="R02",
            reposition_round_id="P02",
            assembly_id="AS01",
        ),
        _feature(
            "A090-P1",
            90.0,
            (10.0, 10.0),
            repeat_type="REPOS",
            repeat_id="R01",
            reposition_round_id="P01",
            assembly_id="AS01",
        ),
        _feature(
            "A090-P2",
            90.0,
            (10.0, 10.0),
            repeat_type="REPOS",
            repeat_id="R02",
            reposition_round_id="P02",
            assembly_id="AS01",
        ),
    )
    zero_scope = replace(
        _scope(tuple(feature.sample_id for feature in zero_repos)),
        direction_order_deg=(0.0, 90.0),
    )
    zero = analyze_direction_feature_sets(zero_repos, zero_scope, _metrics_config())
    assert not zero.morphology_gain.available
    assert zero.morphology_gain.denominator == pytest.approx(0.0)
    assert zero.morphology_gain.unavailable_reason == (
        "reposition_denominator_below_minimum"
    )


def test_summary_names_highest_pearson_and_lowest_rms_pairs_explicitly() -> None:
    features = (
        _feature("A000", 0.0, (1.0, 2.0, 3.0)),
        _feature("A090", 90.0, (1.0, 2.0, 4.0)),
        _feature("A180", 180.0, (3.0, 2.0, 1.0)),
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        direction_order_deg=(0.0, 90.0, 180.0),
    )

    result = analyze_direction_feature_sets(features, scope, _metrics_config())

    assert result.summary.maximum_off_diagonal_pearson == pytest.approx(
        np.corrcoef(features[0].values, features[1].values)[0, 1]
    )
    assert result.summary.most_similar_highest_pearson_pair == (0.0, 90.0)
    assert result.summary.most_difficult_lowest_rms_pair == (0.0, 90.0)
    assert result.summary.minimum_direction_rms == pytest.approx(1.0 / np.sqrt(3.0))
    assert result.summary.direction_count == 3
    assert result.summary.sample_count == 3
    assert result.summary.feature_count == 3


def test_direction_mean_sample_std_and_incomplete_direction_warning() -> None:
    features = (
        _feature("A000-R1", 0.0, (1.0, 2.0), repeat_id="R01"),
        _feature("A000-R2", 0.0, (3.0, 4.0), repeat_id="R02"),
        _feature("A090-R1", 90.0, (5.0, 6.0), repeat_id="R01"),
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        direction_order_deg=(0.0, 90.0, 180.0),
    )

    result = analyze_direction_feature_sets(features, scope, _metrics_config())

    zero, ninety = result.direction_templates
    np.testing.assert_allclose(zero.mean_values, [2.0, 3.0])
    np.testing.assert_allclose(zero.standard_deviation, [np.sqrt(2), np.sqrt(2)])
    np.testing.assert_array_equal(zero.valid_sample_count, [2, 2])
    assert zero.standard_deviation_available
    assert not ninety.standard_deviation_available
    assert np.all(np.isnan(ninety.standard_deviation))
    assert result.warnings == ("direction 180 deg is missing",)


def test_provenance_is_single_origin_and_feature_hashes_are_auditable() -> None:
    simulated = _feature("A000", 0.0, (1.0, 2.0))
    another = _feature("A090", 90.0, (2.0, 3.0))
    scope = replace(
        _scope((simulated.sample_id, another.sample_id)),
        direction_order_deg=(0.0, 90.0),
    )

    result = analyze_direction_feature_sets(
        [simulated, another],
        scope,
        _metrics_config(),
    )

    assert result.data_origin == DataOrigin.SIMULATED.value
    assert result.dataset_role == DatasetRole.SOFTWARE_VALIDATION.value
    assert not result.scientifically_eligible
    audit = result.selection_audit[0]
    assert audit.feature_content_sha256.startswith("sha256:")
    assert audit.source_qc_sha256 == "sha256:" + "b" * 64

    real_meta = replace(
        another.meta,
        data_origin=DataOrigin.REAL_EXPERIMENT,
        dataset_role=DatasetRole.RESEARCH_INPUT,
        source_format=SourceFormat.REW_TXT,
        eligible_for_scientific_analysis=True,
    )
    mixed = replace(another, meta=real_meta)
    with pytest.raises(ValueError, match="data origins"):
        analyze_direction_feature_sets(
            [simulated, mixed],
            scope,
            _metrics_config(),
        )


def test_feature_content_hash_covers_upstream_qc_detail_and_eligibility() -> None:
    feature = _feature("A000", 0.0, (1.0, 2.0))
    changed_reason = replace(
        feature,
        source_qc_warning_reasons=("new warning",),
    )
    changed_eligibility = replace(
        feature,
        source_qc_eligible_for_downstream=False,
    )

    assert feature_set_content_sha256(feature) != feature_set_content_sha256(
        changed_reason
    )
    assert feature_set_content_sha256(feature) != feature_set_content_sha256(
        changed_eligibility
    )

def test_unsupported_feature_schema_is_rejected_even_when_all_inputs_match() -> None:
    features = (
        replace(_feature("A000", 0.0, (1.0, 2.0)), feature_schema_version="999.0"),
        replace(_feature("A090", 90.0, (2.0, 3.0)), feature_schema_version="999.0"),
    )
    scope = replace(
        _scope(tuple(feature.sample_id for feature in features)),
        direction_order_deg=(0.0, 90.0),
    )

    with pytest.raises(ValueError, match="unsupported feature schema"):
        analyze_direction_feature_sets(features, scope, _metrics_config())


def test_named_partition_is_hash_frozen_and_never_discovers_extra_samples() -> None:
    requested_ids = ("A000", "A090")
    partition = FrozenPartition(
        partition_id="training-fold-01",
        sample_ids=requested_ids,
        partition_sha256=frozen_partition_sha256("training-fold-01", requested_ids),
    )
    scope = replace(
        _scope(requested_ids),
        included_sample_ids=None,
        partition=partition,
        direction_order_deg=(0.0, 90.0),
    )
    features = (
        _feature("A000", 0.0, (1.0, 2.0)),
        _feature("A090", 90.0, (2.0, 3.0)),
        _feature("EXTRA", 0.0, (9.0, 9.0)),
    )

    result = analyze_direction_feature_sets(features, scope, _metrics_config())

    assert result.selected_sample_ids == requested_ids
    assert result.selection_audit[-1].reasons == ("not_requested_by_scope",)

    with pytest.raises(ValueError, match="partition SHA-256 mismatch"):
        FrozenPartition(
            partition_id="training-fold-01",
            sample_ids=requested_ids,
            partition_sha256="0" * 64,
        )


def test_p4_direction_templates_are_descriptive_even_for_test_scope() -> None:
    feature = _feature("A000", 0.0, (1.0, 2.0))
    scope = replace(
        _scope((feature.sample_id,)),
        scope_role=ScopeRole.TEST,
        direction_order_deg=(0.0,),
    )

    result = analyze_direction_feature_sets([feature], scope, _metrics_config())

    assert result.template_usage == "descriptive_only"
    assert not result.eligible_for_training_dictionary
    assert not result.tone_selection_allowed

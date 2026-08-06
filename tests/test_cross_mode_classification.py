from __future__ import annotations

from acoustic_encoder.cross_mode_classification import (
    analyze_cross_mode_classification,
    ComparisonMetricsReference,
    CrossModeClassificationScope,
    CrossModeFeatureReference,
    CrossModeGroupSpec,
    OuterFoldSpec,
)
from acoustic_encoder.dataset_quality_control import DatasetQCReference, dataset_qc_sha256, feature_set_content_sha256
from acoustic_encoder.mock_data import generate_directional_feature_set_mock
from acoustic_encoder.schemas import FeatureKind
from dataclasses import replace
import numpy as np
import pytest

from acoustic_encoder.cross_mode_classification import CrossModeClassificationInputError

from test_classification import _p2b


def _fixture(*, repeat_type="CONT", split_protocol="leave_one_session_out"):
    sweep = generate_directional_feature_set_mock(
        feature_count=11, direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        included_repeat_types=(repeat_type,), feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        random_state=20260806,
    )
    multisine_base = generate_directional_feature_set_mock(
        feature_count=11, direction_order_deg=(0.0, 90.0, 180.0, 270.0),
        included_repeat_types=(repeat_type,), feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        random_state=20260806,
    )
    multisine = tuple(
        replace(item, sample_id=item.sample_id + "-MS", meta=replace(item.meta, sample_id=item.sample_id + "-MS", source_path=item.meta.source_path + "-MS"))
        for item in multisine_base
    )
    features = (*sweep, *multisine)
    roles = {item.sample_id: "development" for item in features}
    dataset_id = "DEV-C9-dataset"
    p2b = _p2b(dataset_id, features, roles)
    refs = []
    for index, item in enumerate(sweep):
        refs.append(CrossModeFeatureReference(f"sweep-{index:03d}", item.sample_id, item.source_measurement_mode, item.feature_kind, feature_set_content_sha256(item)))
    for index, item in enumerate(multisine):
        refs.append(CrossModeFeatureReference(f"multi-{index:03d}", item.sample_id, item.source_measurement_mode, item.feature_kind, feature_set_content_sha256(item)))
    groups = []
    for index, (left, right) in enumerate(zip(sweep, multisine, strict=True)):
        groups.append(CrossModeGroupSpec(
            f"group-{index:03d}", f"state-{index:03d}", "development", "U4ENC",
            f"A{int(left.meta.angle_deg):03d}", float(left.meta.angle_deg), left.meta.session_id,
            left.meta.repeat_type, left.meta.repeat_id, left.meta.reposition_round_id,
            left.meta.assembly_id, left.meta.acquisition_block_id, (f"sweep-{index:03d}",),
            (f"multi-{index:03d}",), (f"pair-{index:03d}",), "explicit paired fixture",
        ))
    if split_protocol == "leave_one_session_out":
        keyed = {group.session_id for group in groups}
        key_for = lambda group: group.session_id
        prefix = "loso"
    elif split_protocol == "leave_one_reposition_round_out":
        keyed = {(group.session_id, group.reposition_round_id) for group in groups}
        key_for = lambda group: (group.session_id, group.reposition_round_id)
        prefix = "loro"
    else:
        keyed = {(group.session_id, group.assembly_id) for group in groups}
        key_for = lambda group: (group.session_id, group.assembly_id)
        prefix = "loao"
    folds = tuple(
        OuterFoldSpec(
            (f"{prefix}-{key}" if split_protocol == "leave_one_session_out" else f"{prefix}-{index:02d}"), split_protocol,
            tuple(group.cross_mode_group_id for group in groups if key_for(group) == key),
        )
        for index, key in enumerate(sorted(keyed, key=str))
    )
    comparison_scope_hash = "sha256:" + "4" * 64
    comparison_result_hash = "sha256:" + "5" * 64
    manifest_hash = "sha256:" + "6" * 64
    scope = CrossModeClassificationScope(
        "1.0.0", "DEV-C9-classification", dataset_id, "software_validation", "canonical_cohort",
        "software_validation", "development", "U4ENC", (0.0, 90.0, 180.0, 270.0), sweep[0].feature_names,
        sweep[0].units, sweep[0].tone_set_id, sweep[0].tone_set_sha256,
        sweep[0].tone_schema_id, sweep[0].normalization_method, sweep[0].preprocessing_id,
        multisine[0].preprocessing_id, tuple(refs), tuple(groups), folds,
        ("sweep_to_sweep", "multisine_to_multisine", "sweep_to_multisine", "sweep_plus_multisine_to_multisine"),
        ("nearest_centroid",), ("full",), 20260806,
        DatasetQCReference(dataset_id, dataset_qc_sha256(p2b)),
        ComparisonMetricsReference(dataset_id, comparison_scope_hash, comparison_result_hash, manifest_hash),
    )
    artifacts = {ref.artifact_id: item for ref, item in zip(refs, features, strict=True)}
    comparison = {
        "manifest_sha256": manifest_hash,
        "result_sha256": comparison_result_hash,
        "scope": {"sha256": comparison_scope_hash},
        "result": {
            "analysis_scope_id": dataset_id, "comparison_scope_sha256": comparison_scope_hash,
            "canonical_analysis": True, "p2b_canonical_ready": True,
            "cross_mode_metrics": {"pairs": [
                {"match_pair_id": f"pair-{index:03d}", "sweep_artifact_id": f"sweep-{index:03d}",
                 "multisine_artifact_id": f"multi-{index:03d}", "absolute_comparison_available": False,
                 "shape_comparison_available": True, "mean_bias_db": None}
                for index in range(len(groups))
            ]},
        },
    }
    config = {
        "frequency_bands": [{"band_id": "full", "f_min_hz": 1000.0, "f_max_hz": 1100.0, "boundary": "closed", "minimum_feature_count": 5}],
        "minimum_training_features": 5, "minimum_training_samples_per_direction": 1,
        "minimum_prediction_coverage": 1.0,
        "cross_mode": {"allowed_shape_normalizations": ["subtract_mean_db", "zscore_spectrum"], "pooling_policy": "sample_pooled", "sample_weighting": "uniform", "class_weighting": "balanced"},
    }
    return artifacts, scope, p2b, comparison, config


def _refresh_scope_and_p2b(artifacts, scope):
    references = tuple(
        replace(reference, feature_content_sha256=feature_set_content_sha256(artifacts[reference.artifact_id]))
        for reference in scope.feature_references
    )
    ordered = tuple(artifacts[reference.artifact_id] for reference in references)
    roles = {
        artifacts[artifact_id].sample_id: group.cohort_role.value
        for group in scope.groups
        for artifact_id in (*group.sweep_artifact_ids, *group.multisine_artifact_ids)
    }
    p2b = _p2b(scope.dataset_analysis_scope_id, ordered, roles)
    return replace(
        scope,
        feature_references=references,
        dataset_qc_reference=DatasetQCReference(scope.dataset_analysis_scope_id, dataset_qc_sha256(p2b)),
    ), p2b


def test_cross_mode_scope_round_trip_and_hash_are_stable() -> None:
    digest = "sha256:" + "1" * 64
    scope = CrossModeClassificationScope(
        schema_version="1.0.0",
        classification_scope_id="DEV-C9-scope",
        dataset_analysis_scope_id="DEV-C9-dataset",
        run_purpose="software_validation",
        analysis_tier="canonical_cohort",
        dataset_role="software_validation",
        cross_validation_role="development",
        configuration_id="U4ENC",
        direction_order_deg=(0.0, 90.0),
        feature_names=("tone_000000_1000_hz", "tone_000001_1010_hz"),
        units=("dB", "dB"),
        tone_set_id="tones-v1",
        tone_set_sha256="1" * 64,
        tone_schema_id=digest,
        normalization_method="subtract_mean_db",
        sweep_preprocessing_id=digest,
        multisine_preprocessing_id="sha256:" + "2" * 64,
        feature_references=(
            CrossModeFeatureReference("sweep-0", "sweep-sample", "rew_sweep", "tone_projection_from_sweep", digest),
            CrossModeFeatureReference("multi-0", "multi-sample", "schroeder_multisine", "tone_measurement_from_multisine", "sha256:" + "3" * 64),
        ),
        groups=(
            CrossModeGroupSpec(
                cross_mode_group_id="group-0", physical_state_id="state-0",
                cohort_role="development", configuration_id="U4ENC",
                direction_id="A000", direction_angle_deg=0.0,
                session_id="S01", repeat_type="CONT", repeat_id="R01",
                reposition_round_id="P01", assembly_id="AS01",
                acquisition_block_id="B01", sweep_artifact_ids=("sweep-0",),
                multisine_artifact_ids=("multi-0",), p4b_match_pair_ids=("pair-0",),
                selection_reason="explicit fixture",
            ),
        ),
        outer_folds=(OuterFoldSpec("loso-S01", "leave_one_session_out", ("group-0",)),),
        transfer_protocols=(
            "sweep_to_sweep", "multisine_to_multisine", "sweep_to_multisine",
            "sweep_plus_multisine_to_multisine",
        ),
        models=("nearest_centroid",), band_ids=("full",), random_state=20260806,
        dataset_qc_reference=DatasetQCReference("DEV-C9-dataset", digest),
        comparison_metrics_reference=ComparisonMetricsReference("DEV-C9-dataset", digest, digest, digest),
    )

    restored = CrossModeClassificationScope.from_dict(scope.to_dict())

    assert restored == scope
    assert restored.sha256 == scope.sha256
    assert restored.groups[0].cross_mode_group_id == "group-0"


def test_loso_four_protocols_share_outer_groups_without_held_group_leakage() -> None:
    artifacts, scope, p2b, comparison, config = _fixture()

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    assert result.processing_status == "completed"
    assert {item.transfer_protocol for item in result.fold_audit} == set(scope.transfer_protocols)
    for audit in result.fold_audit:
        held_artifacts = {
            artifact
            for group in scope.groups
            if group.cross_mode_group_id in audit.held_out_cross_mode_group_ids
            for artifact in (*group.sweep_artifact_ids, *group.multisine_artifact_ids)
        }
        assert held_artifacts.isdisjoint(audit.train_artifact_ids)
        assert set(audit.test_artifact_ids) <= {ref.artifact_id for ref in scope.feature_references}
    by_fold = {}
    for audit in result.fold_audit:
        by_fold.setdefault(audit.outer_fold_id, set()).add(audit.held_out_cross_mode_group_ids)
    assert all(len(groups) == 1 for groups in by_fold.values())


def test_all_protocols_predict_with_training_only_masks_and_audited_pooling() -> None:
    artifacts, scope, p2b, comparison, config = _fixture()

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    assert len(result.fold_metrics) == len(scope.outer_folds) * 4
    assert all(item.available for item in result.fold_metrics)
    assert all(item.mask_source == "training_samples_only" for item in result.feature_mask_audit)
    assert {item.common_tone_count for item in result.feature_mask_audit} == {11}
    assert {item.pooling_policy for item in result.training_composition} == {"sample_pooled"}
    mixed = [
        item for item in result.training_composition
        if item.transfer_protocol == "sweep_plus_multisine_to_multisine"
    ]
    assert {item.measurement_mode for item in mixed} == {"rew_sweep", "schroeder_multisine"}
    assert all(not item.p4b_bias_applied and not item.calibration_fitted for item in result.compatibility_audit)
    assert result.scientifically_eligible is False


def test_missing_test_tone_is_unavailable_without_shrinking_training_mask() -> None:
    artifacts, scope, _, comparison, config = _fixture()
    held_multisine = "multi-002"
    original = artifacts[held_multisine]
    mask = np.array(original.valid_mask, copy=True)
    mask[4] = False
    artifacts[held_multisine] = replace(original, valid_mask=mask)
    scope, p2b = _refresh_scope_and_p2b(artifacts, scope)

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    rows = [
        item for item in result.predictions
        if item.artifact_id == held_multisine and item.outer_fold_id == "loso-S02"
    ]
    assert rows
    assert all(not item.available for item in rows)
    assert {item.unavailable_reason for item in rows} == {"test_missing_training_mask_tone"}
    masks = [
        item for item in result.feature_mask_audit
        if item.outer_fold_id == "loso-S02" and item.transfer_protocol.endswith("to_multisine")
    ]
    assert {item.common_tone_count for item in masks} == {11}


def test_raw_absolute_incompatibility_blocks_distance_models_but_not_same_mode() -> None:
    artifacts, scope, _, comparison, config = _fixture()
    artifacts = {
        artifact_id: replace(feature, normalization_method="none")
        for artifact_id, feature in artifacts.items()
    }
    scope = replace(scope, normalization_method="none")
    scope, p2b = _refresh_scope_and_p2b(artifacts, scope)

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    by_protocol = {}
    for metric in result.fold_metrics:
        by_protocol.setdefault(metric.transfer_protocol, []).append(metric)
    assert all(item.available for item in by_protocol["sweep_to_sweep"])
    assert all(item.available for item in by_protocol["multisine_to_multisine"])
    for protocol in ("sweep_to_multisine", "sweep_plus_multisine_to_multisine"):
        assert all(not item.available for item in by_protocol[protocol])
        assert {item.compatibility_status for item in by_protocol[protocol]} == {"absolute_incompatible"}


def test_p2b_and_p4b_hash_mismatches_fail_closed() -> None:
    artifacts, scope, p2b, comparison, config = _fixture()
    bad_p2 = replace(
        scope,
        dataset_qc_reference=DatasetQCReference(
            scope.dataset_analysis_scope_id, "sha256:" + "0" * 64
        ),
    )
    with pytest.raises(ValueError, match="dataset QC result hash mismatch"):
        analyze_cross_mode_classification(
            artifacts, bad_p2, config,
            dataset_qc_result=p2b, comparison_bundle=comparison,
        )

    bad_comparison = {**comparison, "manifest_sha256": "sha256:" + "0" * 64}
    with pytest.raises(CrossModeClassificationInputError, match="P4-B comparison reference mismatch"):
        analyze_cross_mode_classification(
            artifacts, scope, config,
            dataset_qc_result=p2b, comparison_bundle=bad_comparison,
        )


def test_noncanonical_p2b_result_is_rejected_even_when_hash_matches() -> None:
    artifacts, scope, p2b, comparison, config = _fixture()
    p2b = replace(p2b, canonical_allowed_statuses=())
    scope = replace(
        scope,
        dataset_qc_reference=DatasetQCReference(
            scope.dataset_analysis_scope_id, dataset_qc_sha256(p2b)
        ),
    )

    with pytest.raises(ValueError, match="not canonical-ready"):
        analyze_cross_mode_classification(
            artifacts, scope, config,
            dataset_qc_result=p2b, comparison_bundle=comparison,
        )


def test_transfer_gaps_use_identical_multisine_test_cohorts() -> None:
    artifacts, scope, p2b, comparison, config = _fixture()
    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    assert len(result.transfer_gaps) == len(scope.outer_folds) * 2
    assert all(item.available for item in result.transfer_gaps)
    expected_test = {
        fold.outer_fold_id: tuple(sorted(
            artifact
            for group in scope.groups
            if group.cross_mode_group_id in fold.held_out_cross_mode_group_ids
            for artifact in group.multisine_artifact_ids
        ))
        for fold in scope.outer_folds
    }
    assert all(item.test_artifact_ids == expected_test[item.outer_fold_id] for item in result.transfer_gaps)


@pytest.mark.parametrize(
    ("repeat_type", "split_protocol"),
    [
        ("REPOS", "leave_one_reposition_round_out"),
        ("REASM", "leave_one_assembly_out"),
    ],
)
def test_repeat_specific_outer_folds_keep_four_protocols_atomic(
    repeat_type, split_protocol
) -> None:
    artifacts, scope, p2b, comparison, config = _fixture(
        repeat_type=repeat_type, split_protocol=split_protocol
    )

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    assert result.fold_audit
    assert {item.split_protocol for item in result.fold_audit} == {split_protocol}
    assert all(
        set(item.held_out_cross_mode_group_ids).isdisjoint(
            {group.cross_mode_group_id for group in scope.groups for artifact in item.train_artifact_ids if artifact in (*group.sweep_artifact_ids, *group.multisine_artifact_ids)}
        )
        for item in result.fold_audit
    )


def test_final_test_groups_remain_sealed_from_train_and_cross_validation_test() -> None:
    artifacts, scope, _, comparison, config = _fixture()
    final_group = replace(scope.groups[-1], cohort_role="final_test")
    groups = (*scope.groups[:-1], final_group)
    folds = tuple(
        OuterFoldSpec(
            f"loso-{session}", "leave_one_session_out",
            tuple(
                group.cross_mode_group_id for group in groups
                if group.cohort_role.value == "development" and group.session_id == session
            ),
        )
        for session in ("S01", "S02")
    )
    scope = replace(scope, groups=groups, outer_folds=folds)
    scope, p2b = _refresh_scope_and_p2b(artifacts, scope)

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    sealed = set((*final_group.sweep_artifact_ids, *final_group.multisine_artifact_ids))
    assert sealed
    assert all(sealed == set(item.sealed_final_test_artifact_ids) for item in result.fold_audit)
    assert all(sealed.isdisjoint((*item.train_artifact_ids, *item.test_artifact_ids)) for item in result.fold_audit)


def test_three_fixed_p5a_predictors_are_reused_for_all_four_protocols() -> None:
    artifacts, scope, p2b, comparison, config = _fixture()
    scope = replace(
        scope,
        models=("nearest_template_correlation", "nearest_centroid", "logistic_regression"),
    )

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    assert {item.model_id for item in result.fold_metrics} == set(scope.models)
    assert {item.transfer_protocol for item in result.fold_metrics} == set(scope.transfer_protocols)
    assert all(item.available for item in result.fold_metrics)


def test_raw_shape_only_contract_allows_correlation_without_applying_bias() -> None:
    artifacts, scope, _, comparison, config = _fixture()
    artifacts = {
        artifact_id: replace(feature, normalization_method="none")
        for artifact_id, feature in artifacts.items()
    }
    scope = replace(
        scope, normalization_method="none", models=("nearest_template_correlation",)
    )
    scope, p2b = _refresh_scope_and_p2b(artifacts, scope)

    result = analyze_cross_mode_classification(
        artifacts, scope, config, dataset_qc_result=p2b, comparison_bundle=comparison
    )

    cross = [
        item for item in result.compatibility_audit
        if item.transfer_protocol in {"sweep_to_multisine", "sweep_plus_multisine_to_multisine"}
    ]
    assert cross and all(item.available for item in cross)
    assert {item.status for item in cross} == {"correlation_shape_only"}
    assert all(not item.p4b_bias_applied and not item.calibration_fitted for item in cross)


def test_duplicate_physical_state_mapping_is_rejected_before_folding() -> None:
    _, scope, _, _, _ = _fixture()
    groups = (
        scope.groups[0],
        replace(scope.groups[1], physical_state_id=scope.groups[0].physical_state_id),
        *scope.groups[2:],
    )

    with pytest.raises(CrossModeClassificationInputError, match="physical_state_id"):
        replace(scope, groups=groups)


def test_dev_c9_scope_rejects_research_analysis_before_final_test_release() -> None:
    _, scope, _, _, _ = _fixture()

    with pytest.raises(CrossModeClassificationInputError, match="limited to software_validation"):
        replace(scope, run_purpose="research_analysis", dataset_role="research_input")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("tone_set_id", "wrong-tone-set", "matched-tone contract"),
        ("normalization_method", "zscore_spectrum", "matched-tone contract"),
    ],
)
def test_cross_mode_tone_and_normalization_contract_mismatches_fail_closed(
    field, value, message
) -> None:
    artifacts, scope, _, comparison, config = _fixture()
    artifact_id = "multi-000"
    artifacts[artifact_id] = replace(artifacts[artifact_id], **{field: value})
    scope, p2b = _refresh_scope_and_p2b(artifacts, scope)

    with pytest.raises(CrossModeClassificationInputError, match=message):
        analyze_cross_mode_classification(
            artifacts, scope, config,
            dataset_qc_result=p2b, comparison_bundle=comparison,
        )

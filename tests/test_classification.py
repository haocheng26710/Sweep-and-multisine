from __future__ import annotations

from acoustic_encoder.classification import (
    analyze_classification_feature_sets,
    ClassificationFeatureReference,
    ClassificationScope,
    ClassificationScopeMember,
    summarize_direction_predictions,
)
from acoustic_encoder.dataset_quality_control import (
    CohortRole,
    DatasetInputAuditRecord,
    DatasetQCReference,
    DatasetQCResult,
    dataset_qc_sha256,
    feature_contract_sha256,
    feature_set_content_sha256,
)
from acoustic_encoder.mock_data import generate_directional_feature_set_mock
from acoustic_encoder.schemas import FeatureKind, MeasurementMode
from acoustic_encoder.schemas import DataOrigin, DatasetRole
from acoustic_encoder.research_gate import RunPurpose
from dataclasses import replace
import numpy as np
import pytest


def _p2b(scope_id, features, roles) -> DatasetQCResult:
    return DatasetQCResult(
        schema_version="1.0.0",
        analysis_scope_id=scope_id,
        scope_sha256="sha256:" + "2" * 64,
        config_sha256="sha256:" + "3" * 64,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        scoped_sample_ids=tuple(item.sample_id for item in features),
        condition_results=(),
        input_audit=tuple(
            DatasetInputAuditRecord(
                item.sample_id,
                CohortRole(roles[item.sample_id]),
                feature_contract_sha256(item),
                feature_set_content_sha256(item),
                item.source_qc_sha256,
                item.meta.source_sha256,
                "explicit classification fixture",
            )
            for item in features
        ),
    )


def _classification_fixture(*, final_test_sample_id=None, included_repeat_types=("CONT",)):
    features = generate_directional_feature_set_mock(
        feature_count=21,
        included_repeat_types=included_repeat_types,
        random_state=20260806,
    )
    roles = {
        item.sample_id: ("final_test" if item.sample_id == final_test_sample_id else "development")
        for item in features
    }
    scope_id = "DEV-C8-classification"
    p2b = _p2b(scope_id, features, roles)
    scope = ClassificationScope(
        "1.0.0", scope_id, "software_validation", "provisional_validation",
        "software_validation", "rew_sweep", "U4ENC",
        FeatureKind.DENSE_DEMEANED_DB.value, features[0].preprocessing_id, None,
        (0.0, 90.0, 180.0, 270.0),
        tuple(
            ClassificationScopeMember.from_feature_set(
                item, cohort_role=roles[item.sample_id],
                direction_id=f"A{int(item.meta.angle_deg):03d}",
                selection_reason="explicit classification fixture",
            )
            for item in features
        ),
        tuple(
            ClassificationFeatureReference(
                f"feature-{index:03d}", item.sample_id, feature_set_content_sha256(item)
            )
            for index, item in enumerate(features)
        ),
        ("leave_one_session_out",),
        ("nearest_template_correlation", "nearest_centroid", "logistic_regression"),
        ("full",), 20260806,
        DatasetQCReference(scope_id, dataset_qc_sha256(p2b)),
    )
    artifacts = {f"feature-{index:03d}": item for index, item in enumerate(features)}
    config = {
        "frequency_bands": [{
            "band_id": "full", "f_min_hz": 1000.0, "f_max_hz": 1200.0,
            "boundary": "closed", "minimum_feature_count": 5,
        }],
        "minimum_training_features": 5,
        "minimum_prediction_coverage": 1.0,
    }
    return artifacts, scope, p2b, config


def test_classification_scope_round_trip_has_stable_hash_and_explicit_inputs() -> None:
    feature = generate_directional_feature_set_mock(
        feature_count=7,
        direction_order_deg=(0.0,),
        included_repeat_types=("CONT",),
    )[0]
    scope = ClassificationScope(
        schema_version="1.0.0",
        classification_scope_id="DEV-C8-scope",
        run_purpose="software_validation",
        analysis_tier="provisional_validation",
        dataset_role="software_validation",
        measurement_mode="rew_sweep",
        configuration_id="U4ENC",
        feature_kind=FeatureKind.DENSE_DEMEANED_DB.value,
        preprocessing_id=feature.preprocessing_id,
        tone_set_id=None,
        direction_order_deg=(0.0,),
        members=(
            ClassificationScopeMember.from_feature_set(
                feature,
                cohort_role="development",
                direction_id="A000",
                selection_reason="explicit unit fixture",
            ),
        ),
        feature_references=(
            ClassificationFeatureReference(
                artifact_id="feature-000",
                sample_id=feature.sample_id,
                feature_content_sha256=feature_set_content_sha256(feature),
            ),
        ),
        protocols=("leave_one_session_out",),
        models=("nearest_centroid",),
        band_ids=("full",),
        random_state=20260806,
        dataset_qc_reference=DatasetQCReference(
            analysis_scope_id="DEV-C8-scope",
            dataset_qc_result_sha256="sha256:" + "1" * 64,
        ),
    )

    restored = ClassificationScope.from_dict(scope.to_dict())

    assert restored == scope
    assert restored.sha256 == scope.sha256
    assert restored.members[0].sample_id == feature.sample_id
    assert restored.feature_references[0].feature_content_sha256 == feature_set_content_sha256(feature)


def test_loso_models_use_disjoint_groups_and_seal_final_test() -> None:
    preliminary = generate_directional_feature_set_mock(
        feature_count=21, included_repeat_types=("CONT",), random_state=20260806
    )
    final_test_id = preliminary[0].sample_id
    artifacts, scope, p2b, config = _classification_fixture(
        final_test_sample_id=final_test_id
    )

    result = analyze_classification_feature_sets(
        artifacts, scope, config, dataset_qc_result=p2b
    )

    assert result.processing_status == "completed"
    assert result.scientifically_eligible is False
    assert {item.model_id for item in result.fold_metrics} == {
        "nearest_template_correlation", "nearest_centroid", "logistic_regression"
    }
    assert all(set(split.train_sample_ids).isdisjoint(split.test_sample_ids) for split in result.split_audit)
    assert all(final_test_id in split.excluded_final_test_sample_ids for split in result.split_audit)
    assert all(final_test_id not in (*split.train_sample_ids, *split.test_sample_ids) for split in result.split_audit)
    assert all(item.available for item in result.predictions)


def test_all_three_protocols_hold_out_only_their_authoritative_repeat_group() -> None:
    artifacts, scope, p2b, config = _classification_fixture(
        included_repeat_types=("CONT", "REPOS", "REASM")
    )
    scope = replace(
        scope,
        protocols=(
            "leave_one_session_out",
            "leave_one_reposition_round_out",
            "leave_one_assembly_out",
        ),
        models=("nearest_centroid",),
    )

    result = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)

    by_id = {member.sample_id: member for member in scope.members}
    assert all(item.valid for item in result.split_audit)
    for split in result.split_audit:
        repeats = {by_id[sample_id].repeat_type for sample_id in (*split.train_sample_ids, *split.test_sample_ids)}
        if split.protocol == "leave_one_reposition_round_out":
            assert repeats == {"REPOS"}
        elif split.protocol == "leave_one_assembly_out":
            assert repeats == {"REASM"}
        else:
            assert repeats == {"CONT", "REPOS", "REASM"}


def test_test_only_missing_feature_does_not_shrink_fold_mask_or_fill_value() -> None:
    artifacts, scope, _, config = _classification_fixture()
    target_reference = next(
        reference
        for reference in scope.feature_references
        if next(member for member in scope.members if member.sample_id == reference.sample_id).session_id == "S01"
    )
    target = artifacts[target_reference.artifact_id]
    values = target.values.copy(); mask = target.valid_mask.copy()
    values[3] = np.nan; mask[3] = False
    changed = replace(target, values=values, valid_mask=mask)
    artifacts = dict(artifacts); artifacts[target_reference.artifact_id] = changed
    references = tuple(
        replace(item, feature_content_sha256=feature_set_content_sha256(changed))
        if item.artifact_id == target_reference.artifact_id else item
        for item in scope.feature_references
    )
    scope = replace(scope, feature_references=references, models=("nearest_centroid",))
    roles = {member.sample_id: member.cohort_role.value for member in scope.members}
    ordered = tuple(artifacts[item.artifact_id] for item in references)
    p2b = _p2b(scope.classification_scope_id, ordered, roles)
    scope = replace(scope, dataset_qc_reference=DatasetQCReference(scope.classification_scope_id, dataset_qc_sha256(p2b)))

    result = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)

    s01_fold = next(item for item in result.split_audit if item.held_out_group == "S01")
    audit = next(item for item in result.feature_mask_audit if item.fold_id == s01_fold.fold_id)
    assert 3 in audit.selected_feature_indices
    unavailable = next(item for item in result.predictions if item.sample_id == changed.sample_id and item.fold_id == s01_fold.fold_id)
    assert unavailable.available is False
    assert unavailable.unavailable_reason == "test_missing_fold_feature"


def test_training_missing_feature_shrinks_only_that_fold_training_mask() -> None:
    artifacts, scope, _, config = _classification_fixture()
    target_reference = next(
        reference
        for reference in scope.feature_references
        if next(member for member in scope.members if member.sample_id == reference.sample_id).session_id == "S02"
    )
    target = artifacts[target_reference.artifact_id]
    values = target.values.copy(); mask = target.valid_mask.copy(); values[4] = np.nan; mask[4] = False
    changed = replace(target, values=values, valid_mask=mask)
    artifacts = dict(artifacts); artifacts[target_reference.artifact_id] = changed
    refs = tuple(replace(item, feature_content_sha256=feature_set_content_sha256(changed)) if item.artifact_id == target_reference.artifact_id else item for item in scope.feature_references)
    scope = replace(scope, feature_references=refs, models=("nearest_centroid",))
    roles = {member.sample_id: member.cohort_role.value for member in scope.members}; ordered = tuple(artifacts[item.artifact_id] for item in refs)
    p2b = _p2b(scope.classification_scope_id, ordered, roles)
    scope = replace(scope, dataset_qc_reference=DatasetQCReference(scope.classification_scope_id, dataset_qc_sha256(p2b)))
    result = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)

    held_s01 = next(item for item in result.feature_mask_audit if item.fold_id.endswith(":S01"))
    held_s02 = next(item for item in result.feature_mask_audit if item.fold_id.endswith(":S02"))
    assert 4 not in held_s01.selected_feature_indices
    assert 4 in held_s02.selected_feature_indices


def test_dataset_qc_hash_mismatch_is_a_hard_gate() -> None:
    artifacts, scope, p2b, config = _classification_fixture()
    scope = replace(scope, dataset_qc_reference=DatasetQCReference(scope.classification_scope_id, "sha256:" + "0" * 64))
    with pytest.raises(ValueError, match="result hash mismatch"):
        analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)


def test_cross_mode_feature_is_rejected_before_training() -> None:
    artifacts, scope, p2b, config = _classification_fixture()
    key = next(iter(artifacts)); feature = artifacts[key]
    changed = replace(feature, source_measurement_mode=MeasurementMode.SCHROEDER_MULTISINE)
    artifacts = dict(artifacts); artifacts[key] = changed
    scope = replace(
        scope,
        feature_references=tuple(
            replace(item, feature_content_sha256=feature_set_content_sha256(changed))
            if item.artifact_id == key else item
            for item in scope.feature_references
        ),
    )
    with pytest.raises(ValueError, match="measurement_mode mismatch"):
        analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)


def test_insufficient_protocol_groups_are_unavailable_not_fabricated() -> None:
    artifacts, scope, p2b, config = _classification_fixture()
    scope = replace(scope, protocols=("leave_one_reposition_round_out",), models=("nearest_centroid",))
    result = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)
    assert result.processing_status == "completed_with_unavailable"
    assert result.split_audit[0].unavailable_reason == "insufficient_groups"
    assert result.predictions == ()


def test_logistic_regression_is_deterministic_for_fixed_scope_seed() -> None:
    artifacts, scope, p2b, config = _classification_fixture()
    scope = replace(scope, models=("logistic_regression",))
    first = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)
    second = analyze_classification_feature_sets(artifacts, scope, config, dataset_qc_result=p2b)
    assert first.to_dict() == second.to_dict()


def test_shared_prediction_summary_fixes_direction_order_macro_f1_and_confusion() -> None:
    summary = summarize_direction_predictions(
        (0.0, 0.0, 90.0, 90.0),
        (0.0, 90.0, 90.0, 90.0),
        (0.0, 90.0),
        total_prediction_count=5,
    )

    assert summary.balanced_accuracy == pytest.approx(0.75)
    assert summary.macro_f1 == pytest.approx((2 / 3 + 0.8) / 2)
    assert summary.prediction_coverage == pytest.approx(0.8)
    assert summary.confusion_matrix == ((1, 1), (0, 2))

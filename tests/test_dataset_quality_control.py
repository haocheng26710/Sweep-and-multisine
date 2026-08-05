from __future__ import annotations

from dataclasses import replace
import hashlib

import numpy as np
import pytest

from acoustic_encoder.dataset_quality_control import (
    CohortRole,
    DatasetQCResult,
    DatasetQCScope,
    DatasetScopeMember,
    ExpectedCondition,
    ManualReviewRecord,
    dataset_qc_sha256,
    evaluate_dataset_quality,
)
from acoustic_encoder.quality_control import (
    MeasurementQCResult,
    UnavailablePolicy,
    measurement_qc_sha256,
)
from acoustic_encoder.research_gate import RunPurpose
from acoustic_encoder.research_gate import ResearchGateError
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
)
from acoustic_encoder.version import SCHEMA_VERSION_QUARTET


def _measurement(
    sample_id: str,
    *,
    repeat_id: str,
    repeat_type: str = "CONT",
    session_id: str = "S01",
    angle_deg: float = 0.0,
    configuration: str = "U4ENC",
    reposition_round_id: str | None = "P01",
    assembly_id: str | None = "AS01",
    acquisition_block_id: str | None = "B01",
    values: tuple[float, ...] = (0.0, 1.0, 2.0, 3.0, 4.0),
    cohort_manual_review: tuple[str, ...] = (),
    human_valid: bool = True,
) -> tuple[FeatureSet, MeasurementQCResult]:
    source_hash = hashlib.sha256(sample_id.encode("utf-8")).hexdigest()
    meta = MeasurementMeta(
        sample_id=sample_id,
        **SCHEMA_VERSION_QUARTET,
        device_version="V2",
        configuration=configuration,
        angle_deg=angle_deg,
        session_id=session_id,
        repeat_type=repeat_type,
        repeat_id=repeat_id,
        experiment_step="DEV_C6_P2B_TEST",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path=f"mock://{sample_id}",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256=source_hash,
        provenance_uri="mock://DEV-C6-P2B",
        eligible_for_scientific_analysis=False,
        reposition_round_id=reposition_round_id,
        assembly_id=assembly_id,
        acquisition_block_id=acquisition_block_id,
        manual_review_reasons=cohort_manual_review,
        valid=human_valid,
        exclusion_reason=None if human_valid else "human_excluded_fixture",
    )
    qc = MeasurementQCResult(
        qc_schema_version="1.0.0",
        sample_id=sample_id,
        measurement_mode=MeasurementMode.REW_SWEEP,
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        checks=(),
        unavailable_required_policy=UnavailablePolicy.PRESERVE,
        manual_review_reasons=cohort_manual_review,
        human_valid=human_valid,
        human_exclusion_reason=None if human_valid else "human_excluded_fixture",
        scientifically_eligible=False,
    )
    feature = FeatureSet(
        sample_id=sample_id,
        feature_schema_version=SCHEMA_VERSION_QUARTET["feature_schema_version"],
        feature_kind=FeatureKind.DENSE_DEMEANED_DB,
        feature_names=tuple(f"f_{index}" for index in range(len(values))),
        values=np.asarray(values, dtype=np.float64),
        valid_mask=np.ones(len(values), dtype=bool),
        units=("dB",) * len(values),
        source_measurement_mode=MeasurementMode.REW_SWEEP,
        source_representation=Representation.DENSE_SPECTRUM,
        preprocessing_id="sha256:" + "1" * 64,
        meta=meta,
        source_qc_status=qc.aggregate_status,
        source_qc_sha256=measurement_qc_sha256(qc),
        source_qc_eligible_for_downstream=qc.eligible_for_downstream,
    )
    return feature, qc


def _condition(
    *,
    condition_id: str = "dev-u4enc-a000-cont-s01-p01-as01-b01",
    expected_count: int = 2,
    repeat_type: str = "CONT",
    session_id: str = "S01",
    reposition_round_id: str | None = "P01",
    assembly_id: str | None = "AS01",
    acquisition_block_id: str | None = "B01",
) -> ExpectedCondition:
    return ExpectedCondition(
        condition_id=condition_id,
        cohort_role=CohortRole.DEVELOPMENT,
        measurement_mode=MeasurementMode.REW_SWEEP,
        configuration_id="U4ENC",
        direction_id="A000",
        direction_angle_deg=0.0,
        session_id=session_id,
        repeat_type=repeat_type,
        reposition_round_id=reposition_round_id,
        assembly_id=assembly_id,
        acquisition_block_id=acquisition_block_id,
        expected_count=expected_count,
    )


def _scope(
    sample_ids: tuple[str, ...],
    *,
    conditions: tuple[ExpectedCondition, ...] | None = None,
) -> DatasetQCScope:
    conditions = conditions or (_condition(expected_count=len(sample_ids)),)
    return DatasetQCScope(
        schema_version="1.0.0",
        analysis_scope_id="DEV-C6:test-scope",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        members=tuple(
            DatasetScopeMember(
                sample_id=sample_id,
                cohort_role=CohortRole.DEVELOPMENT,
                expected_condition_id=conditions[0].condition_id,
                selection_reason="deterministic software-validation fixture",
            )
            for sample_id in sample_ids
        ),
        expected_conditions=conditions,
        manual_review_records=(),
    )


def _config() -> dict:
    return {
        "schema_version": "1.0.0",
        "provisional": True,
        "condition_completeness": {
            "direction_match_tolerance_deg": 1.0e-9,
            "missing_status": "exclude_candidate",
            "duplicate_status": "exclude_candidate",
            "unexpected_status": "exclude_candidate",
        },
        "same_condition_outliers": {
            "method": "coordinate_median_mad_rms",
            "center": "coordinate_median",
            "distance": "rms",
            "scale": "median_absolute_deviation",
            "mad_scale_factor": 1.4826,
            "minimum_reference_samples": 3,
            "minimum_common_valid_features": 5,
            "minimum_common_valid_fraction": 0.8,
            "minimum_scale": 1.0e-9,
            "warning_robust_z": 3.5,
            "exclude_candidate_robust_z": 6.0,
            "incompatible_contract_status": "exclude_candidate",
            "reference_role_by_evaluation_role": {
                "development": "development",
                "training": "development",
                "final_test": "training",
            },
        },
        "repeatability": {
            "distance": "rms",
            "minimum_common_valid_features": 5,
            "minimum_common_valid_fraction": 0.8,
            "minimum_qualified_pairs": 1,
            "thresholds_by_feature_kind": {
                "dense_demeaned_db": {
                    "units": "dB",
                    "CONT": {"warning_above": 0.5, "exclude_candidate_above": 1.0},
                    "REPOS": {"warning_above": 1.0, "exclude_candidate_above": 2.0},
                    "REASM": {"warning_above": 2.0, "exclude_candidate_above": 4.0},
                },
                "tone_measurement_from_multisine": {
                    "units": "dB",
                    "CONT": {"warning_above": 0.5, "exclude_candidate_above": 1.0},
                    "REPOS": {"warning_above": 1.0, "exclude_candidate_above": 2.0},
                    "REASM": {"warning_above": 2.0, "exclude_candidate_above": 4.0},
                }
            },
        },
        "aggregation": {
            "required_unavailable_policy": "warning",
            "canonical_allowed_statuses": ["valid", "warning"],
            "canonical_block_on_required_unavailable": True,
            "canonical_block_on_manual_review": True,
        },
    }


def test_complete_explicit_condition_matrix_is_valid() -> None:
    pairs = (
        _measurement("dev-cont-01", repeat_id="R01"),
        _measurement("dev-cont-02", repeat_id="R02"),
    )

    result = evaluate_dataset_quality(
        tuple(pair[0] for pair in pairs),
        tuple(pair[1] for pair in pairs),
        _scope(("dev-cont-01", "dev-cont-02")),
        _config(),
    )

    completeness = result.condition_results[0]
    assert completeness.expected_count == 2
    assert completeness.observed_count == 2
    assert completeness.missing_count == 0
    assert completeness.duplicate_count == 0
    assert completeness.unexpected_count == 0
    assert completeness.status.value == "valid"
    assert completeness.reason_codes == ()


def test_missing_expected_repeat_is_reported_without_inferring_a_smaller_design() -> None:
    feature, qc = _measurement("dev-cont-01", repeat_id="R01")

    result = evaluate_dataset_quality(
        (feature,),
        (qc,),
        _scope(("dev-cont-01",), conditions=(_condition(expected_count=2),)),
        _config(),
    )

    completeness = result.condition_results[0]
    assert completeness.expected_count == 2
    assert completeness.observed_count == 1
    assert completeness.missing_count == 1
    assert completeness.status.value == "exclude_candidate"
    assert "expected_measurements_missing" in completeness.reason_codes


def test_known_severe_same_condition_outlier_is_exclude_candidate() -> None:
    pairs = (
        _measurement("dev-cont-01", repeat_id="R01", values=(0, 1, 2, 3, 4)),
        _measurement("dev-cont-02", repeat_id="R02", values=(0, 1, 2, 3, 4.01)),
        _measurement("dev-cont-03", repeat_id="R03", values=(0, 1, 2, 3, 3.99)),
        _measurement("dev-cont-04", repeat_id="R04", values=(20, 21, 22, 23, 24)),
    )
    sample_ids = tuple(pair[0].sample_id for pair in pairs)

    result = evaluate_dataset_quality(
        tuple(pair[0] for pair in pairs),
        tuple(pair[1] for pair in pairs),
        _scope(sample_ids, conditions=(_condition(expected_count=4),)),
        _config(),
    )

    by_id = {item.sample_id: item for item in result.outlier_results}
    assert by_id["dev-cont-04"].status.value == "exclude_candidate"
    assert by_id["dev-cont-04"].available is True
    assert by_id["dev-cont-04"].robust_z >= 6.0
    assert by_id["dev-cont-04"].reason_code == "same_condition_severe_outlier"


def test_cont_repeatability_uses_configured_warning_boundary() -> None:
    pairs = (
        _measurement("dev-cont-01", repeat_id="R01", values=(0, 1, 2, 3, 4)),
        _measurement("dev-cont-02", repeat_id="R02", values=(0.5, 1.5, 2.5, 3.5, 4.5)),
    )

    result = evaluate_dataset_quality(
        tuple(pair[0] for pair in pairs),
        tuple(pair[1] for pair in pairs),
        _scope(("dev-cont-01", "dev-cont-02")),
        _config(),
    )

    group = result.repeatability_results[0]
    assert group.repeat_type == "CONT"
    assert group.qualified_pair_count == 1
    assert group.status.value == "warning"
    assert group.pairs[0].distance == pytest.approx(0.5)
    assert group.pairs[0].reason_code == "repeatability_warning_threshold_reached"


def test_same_condition_outlier_is_unavailable_for_small_reference_group() -> None:
    pairs = (
        _measurement("dev-cont-01", repeat_id="R01"),
        _measurement("dev-cont-02", repeat_id="R02"),
        _measurement("dev-cont-03", repeat_id="R03"),
    )

    result = evaluate_dataset_quality(
        tuple(pair[0] for pair in pairs),
        tuple(pair[1] for pair in pairs),
        _scope(tuple(pair[0].sample_id for pair in pairs)),
        _config(),
    )

    assert all(item.available is False for item in result.outlier_results)
    assert {item.reason_code for item in result.outlier_results} == {
        "insufficient_reference_samples"
    }
    assert all(item.status.value == "unavailable" for item in result.outlier_results)


def test_measurement_rollup_preserves_human_invalid_and_manual_review() -> None:
    first = _measurement(
        "dev-cont-01",
        repeat_id="R01",
        human_valid=False,
    )
    second = _measurement(
        "dev-cont-02",
        repeat_id="R02",
        cohort_manual_review=("verify_microphone_position",),
    )

    result = evaluate_dataset_quality(
        (first[0], second[0]),
        (first[1], second[1]),
        _scope(("dev-cont-01", "dev-cont-02")),
        _config(),
    )

    rollups = {item.sample_id: item for item in result.measurement_rollups}
    assert rollups["dev-cont-01"].human_valid is False
    assert rollups["dev-cont-01"].human_exclusion_reason == "human_excluded_fixture"
    assert rollups["dev-cont-01"].eligible_for_downstream is False
    assert rollups["dev-cont-02"].human_valid is True
    assert rollups["dev-cont-02"].manual_review_reasons == (
        "verify_microphone_position",
    )
    assert rollups["dev-cont-02"].eligible_for_downstream is False
    assert first[0].meta.valid is False
    assert second[0].meta.valid is True


def test_dataset_qc_json_round_trip_recomputes_derived_fields_and_hash() -> None:
    pairs = (
        _measurement("dev-cont-01", repeat_id="R01"),
        _measurement("dev-cont-02", repeat_id="R02"),
    )
    result = evaluate_dataset_quality(
        tuple(pair[0] for pair in pairs),
        tuple(pair[1] for pair in pairs),
        _scope(("dev-cont-01", "dev-cont-02")),
        _config(),
    )

    restored = DatasetQCResult.from_dict(result.to_dict())

    assert restored.to_dict() == result.to_dict()
    assert dataset_qc_sha256(restored) == dataset_qc_sha256(result)
    assert dataset_qc_sha256(result).startswith("sha256:")


def test_scope_mismatch_and_source_qc_hash_mismatch_fail_closed() -> None:
    feature, qc = _measurement("dev-cont-01", repeat_id="R01")
    with pytest.raises(ValueError, match="scope/input sample mismatch"):
        evaluate_dataset_quality(
            (feature,),
            (qc,),
            _scope(("dev-cont-01", "missing-sample")),
            _config(),
        )

    corrupted = replace(feature, source_qc_sha256="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="source QC hash mismatch"):
        evaluate_dataset_quality(
            (corrupted,),
            (qc,),
            _scope(("dev-cont-01",)),
            _config(),
        )


def test_duplicate_and_unexpected_conditions_remain_distinct() -> None:
    duplicate_pairs = (
        _measurement("duplicate-01", repeat_id="R01"),
        _measurement("duplicate-02", repeat_id="R02"),
    )
    duplicate_result = evaluate_dataset_quality(
        tuple(item[0] for item in duplicate_pairs),
        tuple(item[1] for item in duplicate_pairs),
        _scope(
            ("duplicate-01", "duplicate-02"),
            conditions=(_condition(expected_count=1),),
        ),
        _config(),
    )
    assert duplicate_result.condition_results[0].duplicate_count == 1
    assert duplicate_result.condition_results[0].unexpected_count == 0

    unexpected_pairs = (
        _measurement("expected-01", repeat_id="R01"),
        _measurement("wrong-session", repeat_id="R02", session_id="S02"),
    )
    unexpected_result = evaluate_dataset_quality(
        tuple(item[0] for item in unexpected_pairs),
        tuple(item[1] for item in unexpected_pairs),
        _scope(
            ("expected-01", "wrong-session"),
            conditions=(_condition(expected_count=1),),
        ),
        _config(),
    )
    condition = unexpected_result.condition_results[0]
    assert condition.duplicate_count == 0
    assert condition.unexpected_count == 1
    assert condition.unexpected_sample_ids == ("wrong-session",)
    assert any(reason.endswith(":session_id") for reason in condition.reason_codes)


def test_final_test_never_contributes_to_outlier_reference_statistics() -> None:
    dev = tuple(
        _measurement(f"dev-{index}", repeat_id=f"R{index}")
        for index in range(1, 4)
    )
    training = tuple(
        _measurement(f"train-{index}", repeat_id=f"R{index}")
        for index in range(1, 4)
    )
    final = (_measurement("final-1", repeat_id="R1", values=(20, 21, 22, 23, 24)),)
    pairs = (*dev, *training, *final)
    dev_condition = _condition(condition_id="condition-dev", expected_count=3)
    training_condition = replace(
        dev_condition,
        condition_id="condition-training",
        cohort_role=CohortRole.TRAINING,
    )
    final_condition = replace(
        dev_condition,
        condition_id="condition-final",
        cohort_role=CohortRole.FINAL_TEST,
        expected_count=1,
    )
    members = (
        *(
            DatasetScopeMember(item[0].sample_id, CohortRole.DEVELOPMENT, "condition-dev", "development fixture")
            for item in dev
        ),
        *(
            DatasetScopeMember(item[0].sample_id, CohortRole.TRAINING, "condition-training", "training fixture")
            for item in training
        ),
        DatasetScopeMember("final-1", CohortRole.FINAL_TEST, "condition-final", "held-out fixture"),
    )
    scope = DatasetQCScope(
        schema_version="1.0.0",
        analysis_scope_id="DEV-C6:role-separated",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        members=members,
        expected_conditions=(dev_condition, training_condition, final_condition),
    )

    result = evaluate_dataset_quality(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        scope,
        _config(),
    )

    final_result = next(item for item in result.outlier_results if item.sample_id == "final-1")
    assert final_result.reference_role is CohortRole.TRAINING
    assert final_result.reference_sample_ids == ("train-1", "train-2", "train-3")
    assert not any(sample_id.startswith("final-") for sample_id in final_result.reference_sample_ids)
    assert final_result.status.value == "exclude_candidate"


def test_incompatible_feature_contract_is_not_compared() -> None:
    pairs = [
        _measurement(f"dev-{index}", repeat_id=f"R{index}")
        for index in range(1, 5)
    ]
    pairs[-1] = (
        replace(pairs[-1][0], preprocessing_id="sha256:" + "2" * 64),
        pairs[-1][1],
    )
    result = evaluate_dataset_quality(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        _scope(tuple(item[0].sample_id for item in pairs)),
        _config(),
    )

    incompatible = next(item for item in result.outlier_results if item.sample_id == "dev-4")
    assert incompatible.available is False
    assert incompatible.reason_code == "incompatible_feature_contract"
    assert incompatible.status.value == "exclude_candidate"
    assert any(
        pair.reason_code == "incompatible_feature_contract"
        for group in result.repeatability_results
        for pair in group.pairs
    )


def test_cont_repos_reasm_are_strictly_separate() -> None:
    pairs = (
        _measurement("cont-1", repeat_id="R01"),
        _measurement("cont-2", repeat_id="R02"),
        _measurement("repos-1", repeat_id="R01", repeat_type="REPOS", reposition_round_id="P01", acquisition_block_id="B02"),
        _measurement("repos-2", repeat_id="R02", repeat_type="REPOS", reposition_round_id="P02", acquisition_block_id="B03"),
        _measurement("reasm-1", repeat_id="R01", repeat_type="REASM", assembly_id="AS01", acquisition_block_id="B04"),
        _measurement("reasm-2", repeat_id="R02", repeat_type="REASM", assembly_id="AS02", acquisition_block_id="B05"),
    )
    conditions = (
        _condition(condition_id="cont", expected_count=2),
        _condition(condition_id="repos-1", expected_count=1, repeat_type="REPOS", reposition_round_id="P01", acquisition_block_id="B02"),
        _condition(condition_id="repos-2", expected_count=1, repeat_type="REPOS", reposition_round_id="P02", acquisition_block_id="B03"),
        _condition(condition_id="reasm-1", expected_count=1, repeat_type="REASM", assembly_id="AS01", acquisition_block_id="B04"),
        _condition(condition_id="reasm-2", expected_count=1, repeat_type="REASM", assembly_id="AS02", acquisition_block_id="B05"),
    )
    condition_by_sample = {
        "cont-1": "cont",
        "cont-2": "cont",
        "repos-1": "repos-1",
        "repos-2": "repos-2",
        "reasm-1": "reasm-1",
        "reasm-2": "reasm-2",
    }
    scope = DatasetQCScope(
        schema_version="1.0.0",
        analysis_scope_id="DEV-C6:repeat-types",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        members=tuple(
            DatasetScopeMember(sample_id, CohortRole.DEVELOPMENT, condition_id, "repeat-type fixture")
            for sample_id, condition_id in condition_by_sample.items()
        ),
        expected_conditions=conditions,
    )

    result = evaluate_dataset_quality(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        scope,
        _config(),
    )

    groups = {item.repeat_type: item for item in result.repeatability_results}
    assert set(groups) == {"CONT", "REPOS", "REASM"}
    assert groups["CONT"].qualified_pair_count == 1
    assert groups["REPOS"].qualified_pair_count == 1
    assert groups["REASM"].qualified_pair_count == 1
    for repeat_type, group in groups.items():
        assert all(pair.left_sample_id.lower().startswith(repeat_type.lower()) for pair in group.pairs)
        assert all(pair.right_sample_id.lower().startswith(repeat_type.lower()) for pair in group.pairs)


def test_simulated_dataset_is_rejected_for_research_analysis() -> None:
    feature, qc = _measurement("research-denied", repeat_id="R01")
    qc = replace(qc, run_purpose=RunPurpose.RESEARCH_ANALYSIS)
    feature = replace(
        feature,
        source_qc_sha256=measurement_qc_sha256(qc),
    )
    scope = replace(
        _scope(("research-denied",)),
        run_purpose=RunPurpose.RESEARCH_ANALYSIS,
    )

    with pytest.raises(ResearchGateError):
        evaluate_dataset_quality((feature,), (qc,), scope, _config())


def test_missing_direction_session_and_repeat_conditions_are_all_reported() -> None:
    pair = _measurement("observed", repeat_id="R01")
    conditions = (
        _condition(condition_id="observed-condition", expected_count=1),
        replace(
            _condition(condition_id="missing-direction", expected_count=1),
            direction_id="A090",
            direction_angle_deg=90.0,
        ),
        _condition(
            condition_id="missing-session",
            expected_count=1,
            session_id="S02",
        ),
        _condition(
            condition_id="missing-repeat-type",
            expected_count=1,
            repeat_type="REPOS",
        ),
    )
    scope = DatasetQCScope(
        schema_version="1.0.0",
        analysis_scope_id="DEV-C6:missing-matrix",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        members=(
            DatasetScopeMember(
                "observed",
                CohortRole.DEVELOPMENT,
                "observed-condition",
                "explicit observed fixture",
            ),
        ),
        expected_conditions=conditions,
    )

    result = evaluate_dataset_quality((pair[0],), (pair[1],), scope, _config())

    by_id = {item.condition_id: item for item in result.condition_results}
    assert by_id["observed-condition"].status.value == "valid"
    assert by_id["missing-direction"].missing_count == 1
    assert by_id["missing-session"].missing_count == 1
    assert by_id["missing-repeat-type"].missing_count == 1
    assert result.canonical_ready is False
    assert "condition_matrix_incomplete" in result.canonical_ready_reasons


def test_measurement_modes_never_share_outlier_or_repeatability_group() -> None:
    rew_feature, rew_qc = _measurement("rew-mode", repeat_id="R01")
    ms_feature, ms_qc = _measurement("multisine-mode", repeat_id="R02")
    ms_qc = replace(ms_qc, measurement_mode=MeasurementMode.SCHROEDER_MULTISINE)
    ms_meta = replace(
        ms_feature.meta,
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        source_format=SourceFormat.MOCK_AUDIO,
        stimulus_id="DEV-C6-STIMULUS",
        stimulus_hash="a" * 64,
        tone_set_id="DEV-C6-TONES",
        sidecar_path="mock://multisine-mode.json",
        audio_channel=0,
    )
    ms_feature = replace(
        ms_feature,
        feature_kind=FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE,
        source_measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
        source_representation=Representation.SPARSE_TONES,
        meta=ms_meta,
        tone_set_id="DEV-C6-TONES",
        tone_set_sha256="b" * 64,
        tone_schema_id="sha256:" + "c" * 64,
        normalization_method="subtract_mean_db",
        source_magnitude_quantity="transfer_gain",
        source_phase_status=PhaseStatus.RELATIVE_UNRELIABLE,
        source_qc_sha256=measurement_qc_sha256(ms_qc),
    )
    rew_condition = _condition(condition_id="rew", expected_count=1)
    ms_condition = replace(
        rew_condition,
        condition_id="multisine",
        measurement_mode=MeasurementMode.SCHROEDER_MULTISINE,
    )
    scope = DatasetQCScope(
        schema_version="1.0.0",
        analysis_scope_id="DEV-C6:modes",
        run_purpose=RunPurpose.SOFTWARE_VALIDATION,
        members=(
            DatasetScopeMember("rew-mode", CohortRole.DEVELOPMENT, "rew", "REW fixture"),
            DatasetScopeMember(
                "multisine-mode",
                CohortRole.DEVELOPMENT,
                "multisine",
                "multisine fixture",
            ),
        ),
        expected_conditions=(rew_condition, ms_condition),
    )

    result = evaluate_dataset_quality(
        (rew_feature, ms_feature),
        (rew_qc, ms_qc),
        scope,
        _config(),
    )

    assert len(result.repeatability_results) == 2
    assert all(group.sample_count == 1 for group in result.repeatability_results)
    assert all(group.candidate_pair_count == 0 for group in result.repeatability_results)
    assert len({item.group_id for item in result.outlier_results}) == 2


def test_scope_manual_review_record_is_a_separate_audit_and_blocks_canonical() -> None:
    pair = _measurement("manual-scope", repeat_id="R01")
    scope = replace(
        _scope(("manual-scope",)),
        manual_review_records=(
            ManualReviewRecord(
                review_id="review-001",
                sample_ids=("manual-scope",),
                reason_code="confirm_condition_assignment",
            ),
        ),
    )

    result = evaluate_dataset_quality((pair[0],), (pair[1],), scope, _config())

    assert result.manual_review_records[0].status == "pending"
    assert result.measurement_rollups[0].human_valid is True
    assert result.measurement_rollups[0].manual_review_reasons == (
        "confirm_condition_assignment",
    )
    assert result.canonical_ready is False
    assert "manual_review_pending" in result.canonical_ready_reasons


def test_repeatability_exclude_boundary_and_all_reasons_are_preserved() -> None:
    pairs = (
        _measurement("repeat-01", repeat_id="R01", values=(0, 1, 2, 3, 4)),
        _measurement("repeat-02", repeat_id="R02", values=(1, 2, 3, 4, 5)),
    )
    result = evaluate_dataset_quality(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        _scope(("repeat-01", "repeat-02")),
        _config(),
    )

    group = result.repeatability_results[0]
    assert group.pairs[0].distance == pytest.approx(1.0)
    assert group.status.value == "exclude_candidate"
    assert group.pairs[0].reason_code == (
        "repeatability_exclude_candidate_threshold_reached"
    )
    assert all(
        any("repeatability_exclude_candidate_threshold_reached" in reason for reason in rollup.exclude_candidate_reasons)
        for rollup in result.measurement_rollups
    )


def test_outlier_warning_threshold_is_inclusive() -> None:
    pairs = (
        _measurement("boundary-01", repeat_id="R01", values=(0, 1, 2, 3, 4)),
        _measurement("boundary-02", repeat_id="R02", values=(0, 1, 2, 3, 4.01)),
        _measurement("boundary-03", repeat_id="R03", values=(0, 1, 2, 3, 3.99)),
        _measurement("boundary-04", repeat_id="R04", values=(1, 2, 3, 4, 5)),
    )
    scope = _scope(tuple(item[0].sample_id for item in pairs))
    baseline = evaluate_dataset_quality(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        scope,
        _config(),
    )
    score = next(
        item.robust_z for item in baseline.outlier_results if item.sample_id == "boundary-04"
    )
    assert score is not None
    config = _config()
    config["same_condition_outliers"]["warning_robust_z"] = score
    config["same_condition_outliers"]["exclude_candidate_robust_z"] = score + 1.0

    boundary = evaluate_dataset_quality(
        tuple(item[0] for item in pairs),
        tuple(item[1] for item in pairs),
        scope,
        config,
    )

    target = next(
        item for item in boundary.outlier_results if item.sample_id == "boundary-04"
    )
    assert target.status.value == "warning"
    assert target.reason_code == "same_condition_possible_outlier"

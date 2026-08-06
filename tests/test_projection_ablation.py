from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest

from acoustic_encoder.dataset_quality_control import feature_contract_sha256, feature_set_content_sha256
from acoustic_encoder.projection_ablation import (
    AblationStatus,
    FoldSelectionAuthority,
    FoldSelectionReference,
    OuterFoldDefinition,
    ProjectionAblationInputError,
    build_tone_subset_definitions,
    decide_minimum_tone_count,
    derive_tone_projection_feature_set,
    evaluate_classification_stability,
    evaluate_p4_metric_preservation,
    validate_fold_selection_scope,
    validate_fold_selection_authority,
)
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
from acoustic_encoder.sweep_multisine_bridge import (
    CandidateTone,
    CandidateToneUniverse,
    SelectedToneRecord,
    SelectedToneSetArtifact,
    ToneSelectionFeatureReference,
    ToneSelectionMember,
    ToneSelectionScope,
)


def _selection_scope(*, fold: bool = True) -> ToneSelectionScope:
    member = ToneSelectionMember(
        "train-1", "state-train-1", "training" if fold else "development",
        "U4ENC", "D000", 0.0, "S1", "CONT", "R1", None, "A1", "B1",
    )
    reference = ToneSelectionFeatureReference(
        "train-1:discriminability", "train-1", "discriminability",
        "sha256:" + "1" * 64, "sha256:" + "2" * 64,
    )
    return ToneSelectionScope(
        "1.0.0", "selection-scope", "fold_training_selection" if fold else "development_selection",
        "software_validation", "simulated", "software_validation",
        "universe", "sha256:" + "3" * 64, "tone-set", "4" * 64,
        (member,), (reference,), ("training",) if fold else ("development",),
        1, 100.0, 1, False,
        "outer-1" if fold else None, ("train-1",) if fold else (),
        ("state-test-1",) if fold else (), (), None,
        "p2-scope", "sha256:" + "5" * 64, None, 20260806, "fixture",
    )


def test_outer_fold_validation_rejects_global_development_selection() -> None:
    scope = _selection_scope(fold=False)

    with pytest.raises(ProjectionAblationInputError, match="fold_training_selection"):
        validate_fold_selection_scope(
            scope,
            outer_fold_id="outer-1",
            ordered_training_sample_ids=("train-1",),
            held_out_physical_state_ids=("state-test-1",),
        )


def test_fold_authority_binds_training_universe_p2_and_manifest_hashes() -> None:
    universe, selected = _universe_and_selection()
    feature = _feature()
    selection_scope = replace(
        _selection_scope(),
        feature_references=(ToneSelectionFeatureReference(
            "train-1:discriminability", "train-1", "discriminability",
            feature_set_content_sha256(feature), feature_contract_sha256(feature),
        ),),
    )
    selected = replace(
        selected, selection_scope_sha256=selection_scope.sha256,
        input_feature_content_hashes={"train-1:discriminability": feature_set_content_sha256(feature)},
    )
    authority = FoldSelectionAuthority(selection_scope, selected, "f" * 64)
    fold = OuterFoldDefinition("outer-1", "test", ("train-1",), ("test-1",), ("state-test-1",), ())
    reference = FoldSelectionReference(
        "outer-1", selection_scope.sha256, selected.sha256,
        selection_scope.training_sample_sha256, universe.sha256,
        selection_scope.dataset_qc_result_sha256, None,
        "sha256:" + "0" * 64, "f" * 64,
    )
    reference = replace(reference, training_feature_content_sha256="sha256:" + __import__("hashlib").sha256(
        json.dumps({"ordered_training_features": [{"sample_id": "train-1", "feature_content_sha256": feature_set_content_sha256(feature)}]}, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest())
    validate_fold_selection_authority(authority, reference, fold, universe, {"train-1": feature, "test-1": feature})
    with pytest.raises(ProjectionAblationInputError, match="authority hash mismatch"):
        validate_fold_selection_authority(
            authority, replace(reference, training_sample_sha256="sha256:" + "0" * 64),
            fold, universe, {"train-1": feature, "test-1": feature},
        )


def _universe_and_selection() -> tuple[CandidateToneUniverse, SelectedToneSetArtifact]:
    universe = CandidateToneUniverse(
        "1.0.0", "universe", "tone-set", "4" * 64, 48_000, 4_800,
        (1_000.0, 4_000.0),
        (
            CandidateTone("a", 0, 1_000.0, 100),
            CandidateTone("b", 1, 2_000.0, 200),
            CandidateTone("c", 2, 3_000.0, 300),
        ),
    )
    selected = SelectedToneSetArtifact(
        "1.0.0", "sha256:" + "6" * 64, "software_validation_only", True,
        "selection-scope", "sha256:" + "7" * 64, "sha256:" + "8" * 64,
        universe.candidate_universe_id, universe.sha256,
        universe.source_tone_set_id, universe.source_tone_set_sha256,
        universe.sample_rate_hz, universe.period_samples,
        (
            SelectedToneRecord(0, 2, "a", 0, 1_000.0, 100, 0.8),
            SelectedToneRecord(1, 1, "b", 1, 2_000.0, 200, 0.9),
            SelectedToneRecord(2, 3, "c", 2, 3_000.0, 300, 0.7),
        ),
        3, 500.0, 50, ("train-1",), _selection_scope().training_sample_sha256,
        "outer-1", (), None, "sha256:" + "5" * 64, None,
        "simulated", "software_validation", False, False, False,
    )
    return universe, selected


def _feature() -> FeatureSet:
    meta = MeasurementMeta(
        "train-1", "test", "2.18.0", "2.4.0", "2.3.0", "fixture",
        "U4ENC", 0.0, "S1", "CONT", "R1", "P9B_FIXTURE",
        MeasurementMode.REW_SWEEP, SourceFormat.MOCK_DENSE, "synthetic://train-1",
        DataOrigin.SIMULATED, DatasetRole.SOFTWARE_VALIDATION, "9" * 64,
        "synthetic://p9b", False, assembly_id="A1", acquisition_block_id="B1",
    )
    return FeatureSet(
        "train-1", "2.3.0", FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        ("tone_000000_1000_hz", "tone_000001_2000_hz", "tone_000002_3000_hz"),
        np.asarray((1.0, 2.0, 3.0)), np.ones(3, dtype=bool), ("dB",) * 3,
        MeasurementMode.REW_SWEEP, Representation.DENSE_SPECTRUM,
        "sha256:" + "a" * 64, meta, "tone-set", "4" * 64,
        "sha256:" + "b" * 64, "subtract_mean_db", "spl_db", None,
        PhaseStatus.UNAVAILABLE,
    )


def test_subsets_are_selection_rank_prefixes_and_policy_is_not_relaxed() -> None:
    universe, selected = _universe_and_selection()

    subsets = build_tone_subset_definitions(
        "outer-1", selected, universe, (1, 2, 3),
        band_quotas=(
            {"band_id": "low", "f_min_hz": 900.0, "f_max_hz": 1_500.0, "minimum_count": 1, "maximum_count": 2},
            {"band_id": "high", "f_min_hz": 1_500.0, "f_max_hz": 3_500.0, "minimum_count": 1, "maximum_count": 2},
        ),
    )

    assert subsets[0].selection_order_candidate_ids == ("b",)
    assert subsets[0].status == "policy_ineligible"
    assert "band_minimum_not_met:low" in subsets[0].reason_codes
    assert subsets[1].selection_order_candidate_ids == ("b", "a")
    assert subsets[1].feature_order_candidate_ids == ("a", "b")
    assert subsets[1].status == "valid"


def test_projection_selects_existing_columns_and_keeps_source_immutable() -> None:
    universe, selected = _universe_and_selection()
    subset = build_tone_subset_definitions("outer-1", selected, universe, (2,), band_quotas=())[0]
    source = _feature()
    before_values = np.array(source.values, copy=True)
    before_mask = np.array(source.valid_mask, copy=True)

    derived = derive_tone_projection_feature_set(source, subset, selection_artifact_sha256=selected.sha256)

    assert derived.feature_set.feature_names == ("tone_000000_1000_hz", "tone_000001_2000_hz")
    assert derived.feature_set.values.tolist() == [1.0, 2.0]
    assert derived.source_feature_content_sha256.startswith("sha256:")
    assert derived.selection_artifact_sha256 == selected.sha256
    assert np.array_equal(source.values, before_values)
    assert np.array_equal(source.valid_mask, before_mask)
    assert not source.values.flags.writeable


def test_minimum_tone_count_uses_inner_results_only_and_selects_smallest_passing() -> None:
    evaluations = (
        {"subset_size": 2, "status": "valid", "p4_retention": 0.89, "balanced_accuracy_drop": 0.01, "macro_f1_drop": 0.01, "coverage": 1.0, "valid_fold_count": 2},
        {"subset_size": 3, "status": "valid", "p4_retention": 0.96, "balanced_accuracy_drop": 0.02, "macro_f1_drop": 0.03, "coverage": 1.0, "valid_fold_count": 2},
        {"subset_size": 4, "status": "valid", "p4_retention": 0.99, "balanced_accuracy_drop": 0.00, "macro_f1_drop": 0.00, "coverage": 1.0, "valid_fold_count": 2},
    )
    decision = decide_minimum_tone_count(
        "outer-1", evaluations,
        minimum_p4_retention=0.95,
        maximum_balanced_accuracy_drop=0.05,
        maximum_macro_f1_drop=0.05,
        minimum_coverage=1.0,
        minimum_valid_inner_folds=2,
    )

    assert decision.status is AblationStatus.VALID
    assert decision.selected_subset_size == 3
    assert decision.evidence_stage == "inner_validation_only"


def test_minimum_tone_count_is_unavailable_without_enough_inner_folds() -> None:
    decision = decide_minimum_tone_count(
        "outer-1",
        ({"subset_size": 3, "status": "valid", "p4_retention": 1.0, "balanced_accuracy_drop": 0.0, "macro_f1_drop": 0.0, "coverage": 1.0, "valid_fold_count": 1},),
        minimum_p4_retention=0.95,
        maximum_balanced_accuracy_drop=0.05,
        maximum_macro_f1_drop=0.05,
        minimum_coverage=1.0,
        minimum_valid_inner_folds=2,
    )
    assert decision.status is AblationStatus.UNAVAILABLE
    assert decision.selected_subset_size is None


def test_same_mode_classifier_uses_identical_cohort_for_broad_and_sparse() -> None:
    features = {
        "a0": replace(_feature(), sample_id="a0", values=np.asarray((0.0, 0.0, 0.0)), meta=replace(_feature().meta, sample_id="a0", angle_deg=0.0)),
        "a1": replace(_feature(), sample_id="a1", values=np.asarray((0.1, 0.0, 0.1)), meta=replace(_feature().meta, sample_id="a1", angle_deg=0.0)),
        "b0": replace(_feature(), sample_id="b0", values=np.asarray((2.0, 2.0, 2.0)), meta=replace(_feature().meta, sample_id="b0", angle_deg=90.0)),
        "b1": replace(_feature(), sample_id="b1", values=np.asarray((2.1, 2.0, 2.1)), meta=replace(_feature().meta, sample_id="b1", angle_deg=90.0)),
    }
    result = evaluate_classification_stability(
        broad_features=features,
        sparse_features=features,
        train_sample_ids=("a0", "b0"),
        test_sample_ids=("a1", "b1"),
        direction_order=(0.0, 90.0),
        model_id="nearest_centroid",
        minimum_training_features=2,
        minimum_prediction_coverage=1.0,
        random_state=7,
        outer_fold_id="outer-1",
        evaluation_stage="inner_validation",
        fold_id="inner-1",
        subset_size=3,
    )
    assert result.status is AblationStatus.VALID
    assert result.broad_sample_ids == result.sparse_sample_ids
    assert result.broad_balanced_accuracy == pytest.approx(1.0)
    assert result.sparse_balanced_accuracy == pytest.approx(1.0)


def test_p4_preservation_reuses_authoritative_metrics_on_same_cohort() -> None:
    features = {}
    for angle_index, angle in enumerate((0.0, 90.0, 180.0, 270.0)):
        for repeat_index, (repeat_id, reposition_id) in enumerate((("P1", "RP1"), ("P2", "RP2"))):
            sample_id = f"s-{int(angle)}-{repeat_id}"
            source = _feature()
            features[sample_id] = replace(
                source,
                sample_id=sample_id,
                values=np.asarray((angle_index * 2.0, angle_index * 1.0, angle_index * 0.5)) + repeat_index * 0.1,
                source_qc_status=QCStatus.VALID,
                meta=replace(
                    source.meta, sample_id=sample_id, angle_deg=angle,
                    repeat_type="REPOS", repeat_id=repeat_id,
                    reposition_round_id=reposition_id, session_id="S1",
                ),
            )
    rows = evaluate_p4_metric_preservation(
        broad_features=features, sparse_features=features,
        sample_ids=tuple(features), direction_order=(0.0, 90.0, 180.0, 270.0),
        metrics_config={
            "schema_version": "1.0.0", "provisional": True,
            "minimum_common_valid_features": 2, "minimum_common_valid_fraction": 1.0,
            "minimum_direction_count": 2, "center_direction_matrix": False,
            "repeatability_distance_metric": "rms",
            "morphology_gain": {"distance_metric": "rms", "minimum_denominator": 1e-12},
        },
        reliability_config={"floor_db": 0.1, "maximum_raw_weight": 100.0, "minimum_pairs_per_tone": 1, "minimum_available_tones": 2},
        cohort_roles={item: "training" for item in features},
        retention_modes={"effective_rank": "higher_is_better", "morphology_gain": "higher_is_better", "repos_reliability_median_db": "lower_is_better"},
        denominator_floor=1e-12, outer_fold_id="outer-1",
        evaluation_stage="inner_validation", fold_id="inner-1", subset_size=3,
    )
    assert all(item.status is AblationStatus.VALID for item in rows)
    assert all(item.absolute_delta == pytest.approx(0.0) for item in rows)
    assert all(item.retention == pytest.approx(1.0) for item in rows)

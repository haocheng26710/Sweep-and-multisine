from __future__ import annotations

from dataclasses import replace
import numpy as np
import pytest

from acoustic_encoder.dataset_quality_control import (
    feature_contract_sha256,
    feature_set_content_sha256,
)
from acoustic_encoder.schemas import (
    DataOrigin,
    DatasetRole,
    FeatureKind,
    FeatureSet,
    MeasurementMeta,
    MeasurementMode,
    PhaseStatus,
    Representation,
    SourceFormat,
)
from acoustic_encoder.sweep_multisine_bridge import (
    CandidateTone,
    CandidateToneUniverse,
    CandidateScoreResult,
    ToneSelectionFeatureReference,
    ToneSelectionInputError,
    ToneSelectionMember,
    ToneSelectionScope,
    ToneReliabilityEvidence,
    analyze_tone_selection,
    score_tone_candidates,
    select_tones_greedy,
)


def _feature(
    sample_id: str,
    direction: float,
    repeat_id: str,
    values: tuple[float, ...],
    *,
    configuration: str = "U4ENC",
) -> FeatureSet:
    meta = MeasurementMeta(
        sample_id=sample_id,
        pipeline_version="test",
        config_schema_version="2.16.0",
        measurement_schema_version="2.4.0",
        feature_schema_version="2.3.0",
        device_version="fixture",
        configuration=configuration,
        angle_deg=direction,
        session_id="S1",
        repeat_type="CONT",
        repeat_id=repeat_id,
        experiment_step="tone-selection-fixture",
        measurement_mode=MeasurementMode.REW_SWEEP,
        source_format=SourceFormat.MOCK_DENSE,
        source_path=f"fixture/{sample_id}.json",
        data_origin=DataOrigin.SIMULATED,
        dataset_role=DatasetRole.SOFTWARE_VALIDATION,
        source_sha256="9" * 64,
        provenance_uri="synthetic://tone-selection",
        eligible_for_scientific_analysis=False,
        assembly_id="A1",
        acquisition_block_id="B1",
    )
    return FeatureSet(
        sample_id=sample_id,
        feature_schema_version="2.3.0",
        feature_kind=FeatureKind.TONE_PROJECTION_FROM_SWEEP,
        feature_names=(
            "tone_000000_1000_hz",
            "tone_000001_2000_hz",
            "tone_000002_3000_hz",
        ),
        values=np.asarray(values, dtype=np.float64),
        valid_mask=np.ones(3, dtype=bool),
        units=("dB", "dB", "dB"),
        source_measurement_mode=MeasurementMode.REW_SWEEP,
        source_representation=Representation.DENSE_SPECTRUM,
        preprocessing_id="sha256:" + "7" * 64,
        meta=meta,
        tone_set_id="broadband-source",
        tone_set_sha256="f" * 64,
        tone_schema_id="sha256:" + "8" * 64,
        normalization_method="subtract_mean_db",
        source_magnitude_quantity="spl_db",
        source_phase_status=PhaseStatus.UNAVAILABLE,
    )


def _scoring_fixture() -> tuple[CandidateToneUniverse, ToneSelectionScope, dict[str, FeatureSet]]:
    universe = CandidateToneUniverse(
        schema_version="1.0.0",
        candidate_universe_id="broadband-48k-4800",
        source_tone_set_id="broadband-source",
        source_tone_set_sha256="f" * 64,
        sample_rate_hz=48_000,
        period_samples=4_800,
        analysis_band_hz=(1_000.0, 8_000.0),
        candidates=(
            CandidateTone("tone-a", 0, 1_000.0, 100),
            CandidateTone("tone-b", 1, 2_000.0, 200),
            CandidateTone("tone-c", 2, 3_000.0, 300),
        ),
    )
    features: dict[str, FeatureSet] = {}
    members: list[ToneSelectionMember] = []
    references: list[ToneSelectionFeatureReference] = []
    for direction_index, direction in enumerate((0.0, 90.0, 180.0, 270.0)):
        for repeat_index, repeat_id in enumerate(("R1", "R2")):
            sample_id = f"d{direction_index}-r{repeat_index}"
            # tone-a has strong direction structure and tiny repeat error;
            # tone-b has no direction structure; tone-c is repeat-unstable.
            values = (
                direction_index * 3.0 + repeat_index * 0.1,
                1.0 + repeat_index * 0.1,
                direction_index * 2.0 + repeat_index * 4.0,
            )
            feature = _feature(sample_id, direction, repeat_id, values)
            artifact_id = f"{sample_id}-disc"
            features[artifact_id] = feature
            members.append(
                ToneSelectionMember(
                    sample_id,
                    f"state-{direction_index}",
                    "development",
                    "U4ENC",
                    f"D{direction_index}",
                    direction,
                    "S1",
                    "CONT",
                    repeat_id,
                    None,
                    "A1",
                    "B1",
                )
            )
            references.append(
                ToneSelectionFeatureReference(
                    artifact_id,
                    sample_id,
                    "discriminability",
                    feature_set_content_sha256(feature),
                    feature_contract_sha256(feature),
                )
            )
    scope = ToneSelectionScope(
        "1.0.0",
        "scope-dev",
        "development_selection",
        "software_validation",
        "simulated",
        "software_validation",
        universe.candidate_universe_id,
        universe.sha256,
        "broadband-source",
        "f" * 64,
        tuple(members),
        tuple(references),
        ("development",),
        1,
        0.0,
        1,
        False,
        None,
        (),
        (),
        (),
        None,
        "p2b-scope",
        "sha256:" + "2" * 64,
        None,
        20260806,
        "component verification",
    )
    return universe, scope, features


def test_candidate_universe_round_trip_preserves_exact_dft_contract() -> None:
    universe = CandidateToneUniverse(
        schema_version="1.0.0",
        candidate_universe_id="broadband-48k-4800",
        source_tone_set_id="broadband-source",
        source_tone_set_sha256="a" * 64,
        sample_rate_hz=48_000,
        period_samples=4_800,
        analysis_band_hz=(1_000.0, 8_000.0),
        candidates=(
            CandidateTone("tone-100", 0, 1_000.0, 100),
            CandidateTone("tone-200", 1, 2_000.0, 200),
        ),
    )

    restored = CandidateToneUniverse.from_dict(universe.to_dict())

    assert restored == universe
    assert restored.sha256.startswith("sha256:")


def test_candidate_universe_rejects_frequency_that_is_not_the_exact_dft_bin() -> None:
    with pytest.raises(ToneSelectionInputError, match="DFT-bin equation"):
        CandidateToneUniverse(
            schema_version="1.0.0",
            candidate_universe_id="bad-grid",
            source_tone_set_id="broadband-source",
            source_tone_set_sha256="b" * 64,
            sample_rate_hz=48_000,
            period_samples=4_800,
            analysis_band_hz=(1_000.0, 8_000.0),
            candidates=(CandidateTone("bad", 0, 1_001.0, 100),),
        )


def test_selection_scope_keeps_final_test_sealed_and_out_of_feature_inputs() -> None:
    member = ToneSelectionMember(
        sample_id="final-01",
        physical_state_id="state-final",
        cohort_role="final_test",
        configuration_id="U4ENC",
        direction_id="D0",
        direction_angle_deg=0.0,
        session_id="S9",
        repeat_type="CONT",
        repeat_id="R1",
        reposition_round_id=None,
        assembly_id="A9",
        acquisition_block_id="B9",
    )
    reference = ToneSelectionFeatureReference(
        artifact_id="final-01-discriminability",
        sample_id="final-01",
        view_role="discriminability",
        feature_content_sha256="sha256:" + "c" * 64,
        feature_contract_sha256="sha256:" + "d" * 64,
    )

    with pytest.raises(ToneSelectionInputError, match="final_test.*sealed"):
        ToneSelectionScope(
            schema_version="1.0.0",
            selection_scope_id="scope-dev",
            selection_mode="development_selection",
            run_purpose="software_validation",
            data_origin="simulated",
            dataset_role="software_validation",
            candidate_universe_id="broadband-48k-4800",
            candidate_universe_sha256="sha256:" + "e" * 64,
            tone_set_id="broadband-source",
            tone_set_sha256="f" * 64,
            members=(member,),
            feature_references=(reference,),
            selection_roles=("development", "training"),
            target_count=1,
            minimum_spacing_hz=0.0,
            minimum_spacing_bins=1,
            allow_partial=False,
            outer_fold_id=None,
            fold_training_sample_ids=(),
            held_out_physical_state_ids=(),
            sealed_final_test_sample_ids=("final-01",),
            sealed_final_test_sha256="sha256:" + "1" * 64,
            dataset_qc_analysis_scope_id="p2b-scope",
            dataset_qc_result_sha256="sha256:" + "2" * 64,
            comparison_metrics_result_sha256=None,
            random_state=20260806,
            selection_reason="development-only tone selection",
        )


def test_variance_ratio_scores_directional_stable_tone_above_uninformative_tone() -> None:
    universe, scope, features = _scoring_fixture()
    config = {
        "eligibility": {
            "minimum_valid_sample_fraction": 1.0,
            "minimum_direction_count": 4,
            "minimum_cont_pairs": 4,
            "minimum_repos_pairs": 0,
        },
        "scoring": {
            "method": "variance_ratio",
            "epsilon_db_squared": 1.0e-12,
            "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0},
        },
    }

    scores = score_tone_candidates(features, scope, universe, config)

    by_id = {item.candidate_id: item for item in scores}
    assert by_id["tone-a"].eligible
    assert by_id["tone-a"].final_score > by_id["tone-b"].final_score
    assert by_id["tone-c"].components["within_cont_variance"].value > 1.0


def test_weighted_rank_sum_is_deterministic_and_contributions_recompute_score() -> None:
    universe, scope, features = _scoring_fixture()
    config = {
        "eligibility": {
            "minimum_valid_sample_fraction": 1.0,
            "minimum_direction_count": 4,
            "minimum_cont_pairs": 4,
            "minimum_repos_pairs": 0,
        },
        "scoring": {
            "method": "weighted_rank_sum",
            "epsilon_db_squared": 1.0e-12,
            "optional_missing_policy": "renormalize_available_weights_with_warning",
            "tie_method": "average",
            "components": {
                "between_direction_variance": {"required": True, "direction": "higher", "weight": 2.0},
                "within_cont_variance": {"required": True, "direction": "lower", "weight": 1.0},
                "within_repos_variance": {"required": False, "direction": "lower", "weight": 1.0},
            },
        },
    }

    first = score_tone_candidates(features, scope, universe, config)
    second = score_tone_candidates(features, scope, universe, config)

    assert [item.to_dict() for item in first] == [item.to_dict() for item in second]
    for candidate in first:
        if candidate.eligible:
            assert candidate.final_score == pytest.approx(
                sum((candidate.weighted_contributions or {}).values()) / 3.0
            )
    assert first[0].final_score is not None
    assert first[0].final_score > first[1].final_score
    assert first[0].normalization_details["between_direction_variance"]["rank_denominator"] == 2
    assert first[0].normalization_details["between_direction_variance"]["reference_candidate_sha256"].startswith("sha256:")
    assert "within_repos_variance_optional_unavailable" in first[0].warnings


def test_constrained_greedy_records_spacing_blocker_without_silently_lowering_target() -> None:
    universe, original_scope, features = _scoring_fixture()
    scope = replace(original_scope, target_count=2, minimum_spacing_hz=1_500.0)
    config = {
        "eligibility": {
            "minimum_valid_sample_fraction": 1.0,
            "minimum_direction_count": 4,
            "minimum_cont_pairs": 4,
            "minimum_repos_pairs": 0,
        },
        "scoring": {
            "method": "variance_ratio",
            "epsilon_db_squared": 1.0e-12,
            "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0},
        },
        "selection": {"band_quotas": []},
    }
    raw = score_tone_candidates(features, scope, universe, config)
    scores = tuple(
        replace(item, eligible=True, eligibility_reasons=(), final_score=score)
        for item, score in zip(raw, (1.0, 0.9, 0.8), strict=True)
    )

    result = select_tones_greedy(scores, scope, universe, config)

    assert result.processing_status == "completed"
    assert result.selected_candidate_ids == ("tone-a", "tone-c")
    blocked = next(item for item in result.trace if item.candidate_id == "tone-b")
    assert blocked.decision == "skipped"
    assert blocked.reason == "minimum_spacing_hz"
    assert blocked.blocking_candidate_id == "tone-a"


def test_preconfigured_excluded_band_keeps_candidate_with_all_reasons() -> None:
    universe, scope, features = _scoring_fixture()
    config = {
        "eligibility": {
            "minimum_valid_sample_fraction": 1.0,
            "minimum_direction_count": 4,
            "minimum_cont_pairs": 4,
            "minimum_repos_pairs": 0,
            "analysis_band_hz": [1_000.0, 8_000.0],
            "edge_guard_hz": 0.0,
            "excluded_bands_hz": [[1_900.0, 2_100.0]],
            "excluded_band_safety_distance_hz": 100.0,
        },
        "scoring": {
            "method": "variance_ratio",
            "epsilon_db_squared": 1.0e-12,
            "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0},
        },
    }

    scores = score_tone_candidates(features, scope, universe, config)

    excluded = scores[1]
    assert not excluded.eligible
    assert "excluded_frequency_band" in excluded.eligibility_reasons
    assert excluded.components["excluded_band_proximity"].value == 1.0


def test_effective_energy_uses_only_explicit_unnormalized_view_and_enforces_range() -> None:
    universe, original_scope, discriminability = _scoring_fixture()
    artifacts = dict(discriminability)
    references = list(original_scope.feature_references)
    for reference in original_scope.feature_references:
        source = discriminability[reference.artifact_id]
        raw = replace(
            source,
            values=np.asarray((70.0, -150.0, 80.0)),
            normalization_method="none",
            preprocessing_id="sha256:" + "6" * 64,
        )
        artifact_id = reference.artifact_id.replace("-disc", "-raw")
        artifacts[artifact_id] = raw
        references.append(
            ToneSelectionFeatureReference(
                artifact_id,
                raw.sample_id,
                "effective_energy",
                feature_set_content_sha256(raw),
                feature_contract_sha256(raw),
            )
        )
    scope = replace(original_scope, feature_references=tuple(references))
    config = {
        "eligibility": {
            "minimum_valid_sample_fraction": 1.0,
            "minimum_direction_count": 4,
            "minimum_cont_pairs": 4,
            "minimum_repos_pairs": 0,
            "effective_energy_range_db": [-120.0, 120.0],
        },
        "scoring": {
            "method": "variance_ratio",
            "epsilon_db_squared": 1.0e-12,
            "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0},
        },
    }

    scores = score_tone_candidates(artifacts, scope, universe, config)

    assert scores[0].components["effective_energy"].value == 70.0
    assert scores[0].components["effective_energy_margin"].value == 50.0
    assert "effective_energy_out_of_range" in scores[1].eligibility_reasons


def test_band_minimum_quota_is_satisfied_before_global_greedy_fill() -> None:
    universe, original_scope, features = _scoring_fixture()
    scope = replace(original_scope, target_count=2)
    config = {
        "selection": {
            "band_quotas": [
                {"band_id": "low", "f_min_hz": 900.0, "f_max_hz": 2_500.0, "minimum_count": 1, "maximum_count": 1},
                {"band_id": "high", "f_min_hz": 2_500.0, "f_max_hz": 3_500.0, "minimum_count": 1, "maximum_count": 1},
            ]
        }
    }
    components = {
        "stub": next(iter(score_tone_candidates(
            features,
            original_scope,
            universe,
            {
                "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
                "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}},
            },
        )[0].components.values()))
    }
    scores = tuple(
        CandidateScoreResult(candidate.candidate_id, candidate.tone_index, candidate.frequency_hz, candidate.dft_bin, True, (), components, score, "fixture")
        for candidate, score in zip(universe.candidates, (1.0, 0.9, 0.8), strict=True)
    )

    result = select_tones_greedy(scores, scope, universe, config)

    assert result.selected_candidate_ids == ("tone-a", "tone-c")
    assert {item.phase for item in result.trace if item.decision == "selected"} == {"band_minimum"}


def test_analysis_refuses_to_run_without_exact_p2b_result() -> None:
    universe, scope, features = _scoring_fixture()

    with pytest.raises(ToneSelectionInputError, match="P2-B result is required"):
        analyze_tone_selection(
            features,
            scope,
            universe,
            {
                "schema_version": "1.0.0",
                "provisional": True,
                "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
                "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}},
                "selection": {"band_quotas": []},
            },
            dataset_qc_result=None,
        )


def test_configuration_gain_uses_matched_baseline_and_candidate_direction_variance() -> None:
    universe, original_scope, artifacts = _scoring_fixture()
    members = list(original_scope.members)
    references = list(original_scope.feature_references)
    for direction_index, direction in enumerate((0.0, 90.0, 180.0, 270.0)):
        for repeat_index, repeat_id in enumerate(("R1", "R2")):
            sample_id = f"sym-d{direction_index}-r{repeat_index}"
            feature = _feature(
                sample_id,
                direction,
                repeat_id,
                (direction_index + repeat_index * 0.1, 1.0, 1.0),
                configuration="U4SYM",
            )
            artifact_id = sample_id + "-disc"
            artifacts[artifact_id] = feature
            members.append(ToneSelectionMember(sample_id, "sym-state-" + str(direction_index), "development", "U4SYM", f"D{direction_index}", direction, "S1", "CONT", repeat_id, None, "A1", "B1"))
            references.append(ToneSelectionFeatureReference(artifact_id, sample_id, "discriminability", feature_set_content_sha256(feature), feature_contract_sha256(feature)))
    scope = replace(original_scope, members=tuple(members), feature_references=tuple(references))
    config = {
        "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
        "configuration_gain": {"baseline_configuration": "U4SYM", "candidate_configuration": "U4ENC", "epsilon_db_squared": 1e-12},
        "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}},
    }

    scores = score_tone_candidates(artifacts, scope, universe, config)

    assert scores[0].components["configuration_gain"].available
    assert scores[0].components["configuration_gain"].value == pytest.approx(9.0)


def test_noise_component_is_unavailable_when_no_authoritative_snr_evidence_exists() -> None:
    universe, scope, features = _scoring_fixture()
    config = {
        "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
        "reliability": {"minimum_pairs_per_tone": 1, "snr_target_db": 30.0, "stability_scale_db": 1.0, "noise_scale_db": 10.0},
        "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}},
    }

    scores = score_tone_candidates(features, scope, universe, config)

    assert not scores[0].components["instability_noise_penalty"].available
    assert scores[0].components["instability_noise_penalty"].value is None
    assert scores[0].components["instability_noise_penalty"].reason == "authoritative_snr_or_noise_evidence_unavailable"


def test_p4b_repeatability_is_used_only_with_exact_scope_and_feature_hashes() -> None:
    universe, original_scope, features = _scoring_fixture()
    comparison_hash = "sha256:" + "4" * 64
    scope = replace(original_scope, comparison_metrics_result_sha256=comparison_hash)
    evidence = ToneReliabilityEvidence(
        "1.0.0",
        comparison_hash,
        {feature.sample_id: feature_set_content_sha256(feature) for feature in features.values()},
        "broadband-source",
        "f" * 64,
        (1_000.0, 2_000.0, 3_000.0),
        (0.2, 0.3, 0.4),
        (4, 4, 4),
        (("p1",), ("p2",), ("p3",)),
    )
    config = {
        "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
        "reliability": {"minimum_pairs_per_tone": 1, "snr_target_db": 30.0, "stability_scale_db": 1.0, "noise_scale_db": 10.0},
        "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}},
    }

    scores = score_tone_candidates(features, scope, universe, config, reliability_evidence=evidence)

    assert scores[0].components["sweep_repeatability"].value == 0.2
    with pytest.raises(ToneSelectionInputError, match="P4-B.*hash"):
        score_tone_candidates(
            features,
            scope,
            universe,
            config,
            reliability_evidence=replace(evidence, comparison_metrics_result_sha256="sha256:" + "5" * 64),
        )


@pytest.mark.parametrize(
    ("candidates", "analysis_band", "message"),
    [
        ((CandidateTone("a", 0, 1_000.0, 100), CandidateTone("a", 1, 2_000.0, 200)), (1_000.0, 8_000.0), "IDs must be unique"),
        ((CandidateTone("a", 0, 1_000.0, 100), CandidateTone("b", 1, 1_000.0, 100)), (1_000.0, 8_000.0), "frequencies must be unique"),
        ((CandidateTone("a", 1, 1_000.0, 100),), (1_000.0, 8_000.0), "indices must be contiguous"),
        ((CandidateTone("a", 0, 25_000.0, 2_500),), (1_000.0, 30_000.0), "below Nyquist"),
        ((CandidateTone("a", 0, 9_000.0, 900),), (1_000.0, 8_000.0), "outside the analysis band"),
    ],
)
def test_candidate_universe_rejects_ambiguous_or_physics_incompatible_candidates(candidates, analysis_band, message) -> None:
    with pytest.raises(ToneSelectionInputError, match=message):
        CandidateToneUniverse("1.0.0", "bad", "source", "a" * 64, 48_000, 4_800, analysis_band, candidates)


def test_fold_selection_binds_exact_training_ids_and_rejects_held_physical_state() -> None:
    _universe, original, _features = _scoring_fixture()
    training_members = tuple(replace(item, cohort_role="training") for item in original.members)
    training_ids = tuple(item.sample_id for item in training_members)
    valid = replace(
        original,
        selection_mode="fold_training_selection",
        members=training_members,
        selection_roles=("training",),
        outer_fold_id="outer-01",
        fold_training_sample_ids=training_ids,
        held_out_physical_state_ids=("held-state",),
    )

    assert ToneSelectionScope.from_dict(valid.to_dict()) == valid
    with pytest.raises(ToneSelectionInputError, match="held-out physical state leaked"):
        replace(valid, held_out_physical_state_ids=(training_members[0].physical_state_id,))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"outer_fold_id": None}, "requires outer_fold_id"),
        ({"fold_training_sample_ids": ("wrong",)}, "training IDs must exactly match"),
        ({"selection_mode": "development_selection"}, "development selection cannot carry fold-only"),
    ],
)
def test_fold_scope_rejects_incomplete_or_cross_mode_partition_contract(changes, message) -> None:
    _universe, original, _features = _scoring_fixture()
    members = tuple(replace(item, cohort_role="training") for item in original.members)
    valid = replace(
        original,
        selection_mode="fold_training_selection",
        members=members,
        selection_roles=("training",),
        outer_fold_id="outer-01",
        fold_training_sample_ids=tuple(item.sample_id for item in members),
        held_out_physical_state_ids=("held-state",),
    )
    with pytest.raises(ToneSelectionInputError, match=message):
        replace(valid, **changes)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda config: config["scoring"].update(method="result_informed"), "unsupported"),
        (lambda config: config["scoring"].update(tie_method="first"), "tie_method"),
        (lambda config: config["scoring"].update(optional_missing_policy="fill_average"), "missing policy"),
        (lambda config: config["scoring"]["components"]["between_direction_variance"].update(weight=-1.0), "non-negative"),
        (lambda config: [item.update(weight=0.0) for item in config["scoring"]["components"].values()], "sum to more than zero"),
    ],
)
def test_weighted_scoring_rejects_ambiguous_or_leakage_prone_policies(mutator, message) -> None:
    universe, scope, features = _scoring_fixture()
    config = {
        "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
        "scoring": {
            "method": "weighted_rank_sum", "epsilon_db_squared": 1e-12,
            "optional_missing_policy": "renormalize_available_weights_with_warning", "tie_method": "average",
            "components": {
                "between_direction_variance": {"required": True, "direction": "higher", "weight": 1.0},
                "within_cont_variance": {"required": True, "direction": "lower", "weight": 1.0},
            },
        },
    }
    mutator(config)
    with pytest.raises(ToneSelectionInputError, match=message):
        score_tone_candidates(features, scope, universe, config)


@pytest.mark.parametrize(
    ("allow_partial", "expected_status", "expected_selected", "expected_lifecycle"),
    [
        (False, "unavailable", (), "draft"),
        (True, "partial", ("tone-a",), "draft"),
    ],
)
def test_insufficient_target_never_silently_lowers_count(allow_partial, expected_status, expected_selected, expected_lifecycle) -> None:
    universe, original_scope, features = _scoring_fixture()
    scope = replace(original_scope, target_count=3, minimum_spacing_hz=10_000.0, allow_partial=allow_partial)
    base = score_tone_candidates(
        features,
        original_scope,
        universe,
        {
            "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
            "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}},
        },
    )
    scores = tuple(replace(item, eligible=True, eligibility_reasons=(), final_score=float(3 - index)) for index, item in enumerate(base))

    result = select_tones_greedy(scores, scope, universe, {"selection": {"band_quotas": []}})

    assert result.processing_status == expected_status
    assert result.selected_candidate_ids == expected_selected
    assert result.lifecycle == expected_lifecycle
    assert result.failures


def test_spacing_threshold_boundaries_are_inclusive_and_do_not_overreject() -> None:
    universe, scope, features = _scoring_fixture()
    scope = replace(scope, target_count=3, minimum_spacing_hz=1_000.0, minimum_spacing_bins=100)
    base = score_tone_candidates(
        features, scope, universe,
        {"eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0}, "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}}},
    )
    scores = tuple(replace(item, eligible=True, eligibility_reasons=(), final_score=float(3 - index)) for index, item in enumerate(base))

    result = select_tones_greedy(scores, scope, universe, {"selection": {"band_quotas": []}})

    assert result.processing_status == "completed"
    assert result.selected_candidate_ids == ("tone-a", "tone-b", "tone-c")


def test_repos_requirement_is_unavailable_and_never_substituted_with_cont_pairs() -> None:
    universe, scope, features = _scoring_fixture()
    scores = score_tone_candidates(
        features, scope, universe,
        {"eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 1}, "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 0.0, "within_repos_weight": 1.0}}},
    )

    assert all(not item.eligible for item in scores)
    assert all("within_repos_variance_unavailable" in item.eligibility_reasons for item in scores)
    assert all(item.components["within_repos_variance"].source_pair_count == 0 for item in scores)


def test_average_rank_ties_are_deterministic_and_frequency_breaks_final_selection_tie() -> None:
    universe, scope, features = _scoring_fixture()
    tied_features = {}
    tied_references = []
    references = {item.artifact_id: item for item in scope.feature_references}
    for artifact_id, feature in features.items():
        values = np.array(feature.values, copy=True)
        values[1] = values[0]
        tied = replace(feature, values=values)
        tied_features[artifact_id] = tied
        tied_references.append(
            replace(
                references[artifact_id],
                feature_content_sha256=feature_set_content_sha256(tied),
                feature_contract_sha256=feature_contract_sha256(tied),
            )
        )
    scope = replace(scope, feature_references=tuple(tied_references))
    config = {
        "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
        "scoring": {
            "method": "weighted_rank_sum", "epsilon_db_squared": 1e-12,
            "optional_missing_policy": "renormalize_available_weights_with_warning", "tie_method": "average",
            "components": {"within_cont_variance": {"required": True, "direction": "lower", "weight": 1.0}},
        },
    }
    scores = score_tone_candidates(tied_features, scope, universe, config)
    assert scores[0].final_score == scores[1].final_score
    assert "within_repos_variance_optional_unavailable" not in scores[0].warnings
    selected = select_tones_greedy(scores, replace(scope, target_count=1), universe, {"selection": {"band_quotas": []}})
    assert selected.selected_candidate_ids == ("tone-a",)


def test_greedy_tie_break_counts_required_component_availability_not_optional_evidence() -> None:
    universe, original_scope, features = _scoring_fixture()
    base = score_tone_candidates(
        features,
        original_scope,
        universe,
        {
            "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
            "scoring": {"method": "variance_ratio", "epsilon_db_squared": 1e-12, "variance_ratio": {"within_cont_weight": 1.0, "within_repos_weight": 0.0}},
        },
    )
    high_components = dict(base[1].components)
    high_components["sweep_repeatability"] = replace(
        high_components["sweep_repeatability"], available=True, value=0.1, status="available", reason=None
    )
    scores = (
        replace(base[0], eligible=True, eligibility_reasons=(), final_score=1.0),
        replace(base[1], eligible=True, eligibility_reasons=(), final_score=1.0, components=high_components),
        replace(base[2], eligible=False, eligibility_reasons=("fixture_ineligible",), final_score=None),
    )
    config = {
        "scoring": {
            "components": {
                "between_direction_variance": {"required": True, "direction": "higher", "weight": 1.0},
                "within_cont_variance": {"required": True, "direction": "lower", "weight": 1.0},
                "sweep_repeatability": {"required": False, "direction": "lower", "weight": 1.0},
            }
        },
        "selection": {"band_quotas": []},
    }

    result = select_tones_greedy(scores, replace(original_scope, target_count=1), universe, config)

    assert result.selected_candidate_ids == ("tone-a",)


def test_required_unavailable_component_makes_candidate_ineligible_without_imputation() -> None:
    universe, scope, features = _scoring_fixture()
    scores = score_tone_candidates(
        features, scope, universe,
        {
            "eligibility": {"minimum_valid_sample_fraction": 1.0, "minimum_direction_count": 4, "minimum_cont_pairs": 4, "minimum_repos_pairs": 0},
            "scoring": {
                "method": "weighted_rank_sum", "epsilon_db_squared": 1e-12,
                "optional_missing_policy": "renormalize_available_weights_with_warning", "tie_method": "average",
                "components": {"within_repos_variance": {"required": True, "direction": "lower", "weight": 1.0}},
            },
        },
    )

    assert all(not item.eligible and item.final_score is None for item in scores)
    assert all("within_repos_variance_required_unavailable" in item.eligibility_reasons for item in scores)

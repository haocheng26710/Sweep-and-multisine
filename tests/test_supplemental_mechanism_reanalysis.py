from __future__ import annotations

import numpy as np
import pytest

from acoustic_encoder.supplemental_mechanism_reanalysis import (
    SupplementalMechanismInputError,
    bootstrap_array_window_effect,
    bootstrap_window_pattern_correspondence,
    bootstrap_signature_window_effect,
    validate_v2_physical_mapping,
)


def test_v2_physical_mapping_accepts_only_explicit_user_authority() -> None:
    mapping = validate_v2_physical_mapping(
        {0: "ENC-A", 90: "ENC-B", 180: "ENC-D", 270: "ENC-F"},
        authority="user_V2_incremental_spec_2026-08-24",
    )

    assert mapping == {0: "ENC-A", 90: "ENC-B", 180: "ENC-D", 270: "ENC-F"}

    with pytest.raises(SupplementalMechanismInputError, match="explicit user V2"):
        validate_v2_physical_mapping(
            {0: "ENC-A", 90: "ENC-B", 180: "ENC-D", 270: "ENC-F"},
            authority="inferred_from_filenames",
        )

    with pytest.raises(SupplementalMechanismInputError, match="explicit user V2"):
        validate_v2_physical_mapping(
            {0: "ENC-A", 90: "ENC-B", 180: "ENC-D", 270: "ENC-G"},
            authority="user_V2_incremental_spec_2026-08-24",
        )


def test_module_window_effect_bootstraps_whole_repeat_curves() -> None:
    reference = np.zeros((3, 4), dtype=float)
    candidate = np.tile(np.asarray([1.0, 1.0, -1.0, -1.0]), (3, 1))

    result = bootstrap_signature_window_effect(
        candidate,
        reference,
        parent_mask=np.asarray([True, True, True, True]),
        window_mask=np.asarray([True, True, False, False]),
        bootstrap_iterations=100,
        random_state=7,
    )

    assert result["signed_mean_db"] == 1.0
    assert result["rms_db"] == 1.0
    assert result["signed_mean_ci95"] == (1.0, 1.0)
    assert result["resampling_unit"] == "whole_repeat_curve"


def test_array_window_effect_resamples_blocks_then_whole_repeats() -> None:
    hom = {
        "B01": np.zeros((3, 4), dtype=float),
        "B02": np.zeros((3, 4), dtype=float),
    }
    het_curve = np.tile(np.asarray([2.0, 2.0, -2.0, -2.0]), (3, 1))
    het = {"B03": het_curve, "B04": het_curve.copy()}

    result = bootstrap_array_window_effect(
        hom,
        het,
        parent_mask=np.asarray([True, True, True, True]),
        window_mask=np.asarray([True, True, False, False]),
        bootstrap_iterations=100,
        random_state=11,
    )

    assert result["signed_mean_db"] == 2.0
    assert result["rms_db"] == 2.0
    assert result["rms_ci95"] == (2.0, 2.0)
    assert result["resampling_unit"] == "configuration_block_then_whole_repeat_curve"


def test_pattern_correspondence_uses_fixed_windows_and_cluster_bootstrap() -> None:
    zero = np.zeros((3, 6), dtype=float)
    pattern = np.tile(np.asarray([1.0, 1.0, 0.0, 0.0, -1.0, -1.0]), (3, 1))
    hom = {"B01": zero, "B02": zero.copy()}
    het = {"B03": pattern, "B04": pattern.copy()}
    parent = np.ones(6, dtype=bool)
    windows = [
        ("W1", parent, np.asarray([1, 1, 0, 0, 0, 0], dtype=bool)),
        ("W2", parent, np.asarray([0, 0, 1, 1, 0, 0], dtype=bool)),
        ("W3", parent, np.asarray([0, 0, 0, 0, 1, 1], dtype=bool)),
    ]

    result = bootstrap_window_pattern_correspondence(
        pattern,
        zero,
        hom,
        het,
        windows=windows,
        bootstrap_iterations=100,
        random_state=13,
    )

    assert result["pearson_r"] == 1.0
    assert result["spearman_r"] == 1.0
    assert result["cosine_similarity"] == 1.0
    assert result["window_sign_agreement_fraction"] == 1.0
    assert result["evidence_status"] == "stable_positive_pattern_correspondence"

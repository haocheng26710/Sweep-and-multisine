from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from acoustic_encoder.formal_final_synthesis import (
    Formal5InputError,
    evaluate_frozen_evidence,
    validate_formal4_numeric_trace,
    verify_formal5_output_hashes,
    write_formal5_bundle,
)


def _frozen_summary() -> dict[str, object]:
    return {
        "ready_for_formal_synthesis": True,
        "final_test_read": False,
        "selection": {
            "active_count": 72,
            "excluded_count": 19,
            "active_or_excluded_decision_changed": False,
            "excluded_entered_analysis": False,
        },
        "input_authority": {
            "zip_sha256": (
                "cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb"
            ),
            "input_artifacts_verified": 225,
        },
        "repeatability_floor": {
            "primary_band": {
                "median_db": 0.3782942415603068,
                "iqr_db": 0.2190678991596497,
                "p95_db": 0.8792543414488713,
            }
        },
        "direction_effect": {
            "G_demeaned_AS01_primary": {
                "U4ENC": 1.2805414340255579,
                "U4ENC_ci95": [0.829727543676017, 1.766654301499613],
                "U4SYM": 0.6823847630714056,
                "U4SYM_ci95": [0.6105373373858028, 1.2699369797033497],
                "U4ENC_minus_U4SYM": 0.5981566709541523,
                "U4ENC_minus_U4SYM_ci95": [
                    -0.11310886268350098,
                    1.0842695384282073,
                ],
            },
            "reliable_primary_pairs_exceed_CONT_p95_in_both_AS01_REPOS_blocks": {
                "U4ENC": ["0-90", "0-180", "0-270", "90-180", "90-270", "180-270"],
                "U4SYM": ["0-90", "90-270", "180-270"],
            },
        },
        "configuration_effect": {
            "AS01_median_demeaned_to_floor_ratio": 1.5687667558448029,
        },
        "classification": {
            "practical_target": 0.5,
            "U4SYM_AS01": {"balanced_accuracy": 0.375, "macro_f1": 0.25},
            "U4ENC_AS01": {
                "balanced_accuracy": 0.25,
                "macro_f1": 0.18333333333333335,
            },
        },
        "assembly_set_effect": {
            "status": "exploratory_block_time_assembly_confounded",
            "strong_causal_conclusion_allowed": False,
        },
        "outlier_policy": {
            "flagged_active_count": 10,
            "active_manifest_modified": False,
            "any_frozen_threshold_conclusion_changed": False,
        },
        "provenance": {
            "data_origin": "real_experiment",
            "dataset_role": "research_analysis",
            "run_purpose": "research_analysis",
            "scientifically_eligible": False,
        },
    }


def test_frozen_evidence_yields_supported_with_limits_without_confirming_h1() -> None:
    decision = evaluate_frozen_evidence(_frozen_summary())

    assert decision["disposition"] == "supported_with_limits"
    assert decision["hypothesis_decisions"]["H1"] == "not_confirmed"
    assert decision["question_decisions"]["RQ1"] == "supported"
    assert decision["question_decisions"]["RQ2"] == "partially_supported"
    assert decision["question_decisions"]["RQ4"] == "not_supported"
    assert decision["scientifically_eligible"] is False
    assert decision["final_test_read"] is False


def test_frozen_evidence_rejects_a_changed_authoritative_number() -> None:
    changed = copy.deepcopy(_frozen_summary())
    changed["direction_effect"]["G_demeaned_AS01_primary"]["U4ENC"] = 1.4  # type: ignore[index]

    with pytest.raises(Formal5InputError, match="U4ENC G_demeaned"):
        evaluate_frozen_evidence(changed)


def test_final_bundle_is_complete_hash_audited_and_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "FORMAL-5_FINAL_SYNTHESIS"
    result = write_formal5_bundle(
        _frozen_summary(),
        output,
        source_commit="1" * 40,
        created_at="2026-08-20T18:00:00+01:00",
        input_artifacts={
            "formal3_run_manifest": {
                "path": "authority/FORMAL-3/run_manifest.json",
                "sha256": "2" * 64,
            },
            "formal4_analysis_summary": {
                "path": "authority/FORMAL-4/analysis_summary.json",
                "sha256": "3" * 64,
            },
        },
        acquisition_evidence={
            "calibration_input_binding": "verified",
            "ready_for_B01": False,
            "unresolved_blockers": ["external_backup_not_configured"],
        },
    )

    assert result.disposition == "supported_with_limits"
    assert result.artifact_count == 6
    assert (output / "final_evidence_summary.md").is_file()
    assert (output / "hypothesis_decision_table.csv").is_file()
    assert (output / "dissertation_results_draft.md").is_file()
    assert (output / "dissertation_figure_index.csv").is_file()
    claim = json.loads((output / "final_claim_boundary.json").read_text(encoding="utf-8"))
    manifest = json.loads((output / "final_analysis_manifest.json").read_text(encoding="utf-8"))
    assert claim["scientifically_eligible"] is False
    assert claim["final_test_read"] is False
    assert manifest["selection"]["active_count"] == 72
    assert manifest["selection"]["selection_changed"] is False
    assert manifest["raw_directory_scanned"] is False
    assert verify_formal5_output_hashes(output)["all_match"] is True

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_formal5_bundle(
            _frozen_summary(), output, source_commit="1" * 40,
            created_at="2026-08-20T18:00:00+01:00",
            input_artifacts={}, acquisition_evidence={},
        )


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        (None, "final_test_read", True, "final_test_read"),
        ("selection", "active_count", 71, "ACTIVE count"),
        ("selection", "active_or_excluded_decision_changed", True, "selection changed"),
    ],
)
def test_final_gate_rejects_final_test_or_selection_mutation(
    section: str | None, field: str, value: object, message: str
) -> None:
    changed = copy.deepcopy(_frozen_summary())
    target = changed if section is None else changed[section]  # type: ignore[index]
    target[field] = value  # type: ignore[index]

    with pytest.raises(Formal5InputError, match=message):
        evaluate_frozen_evidence(changed)


def test_output_hash_verification_detects_report_tampering(tmp_path: Path) -> None:
    output = tmp_path / "FORMAL-5"
    write_formal5_bundle(
        _frozen_summary(), output, source_commit="1" * 40,
        created_at="2026-08-20T18:00:00+01:00",
        input_artifacts={"authority": {"path": "fixed", "sha256": "2" * 64}},
        acquisition_evidence={},
    )
    (output / "final_evidence_summary.md").write_text("tampered", encoding="utf-8")

    with pytest.raises(Formal5InputError, match="hash mismatch"):
        verify_formal5_output_hashes(output)


def test_report_numbers_must_trace_to_authoritative_formal4_tables() -> None:
    tables = {
        "repeatability_summary.csv": [{
            "band_id": "primary", "median_pairwise_rms_db": "0.3782942415603068",
            "iqr_pairwise_rms_db": "0.2190678991596497",
            "p95_pairwise_rms_db": "0.8792543414488713",
        }],
        "direction_gain_summary.csv": [
            {"configuration": "U4SYM", "assembly_scope": "AS01", "band_id": "primary",
             "normalization": "demeaned", "gain": "0.6823847630714056",
             "bootstrap_ci95_low": "0.6105373373858028", "bootstrap_ci95_high": "1.2699369797033497"},
            {"configuration": "U4ENC", "assembly_scope": "AS01", "band_id": "primary",
             "normalization": "demeaned", "gain": "1.2805414340255579",
             "bootstrap_ci95_low": "0.829727543676017", "bootstrap_ci95_high": "1.766654301499613"},
        ],
        "direction_gain_contrasts.csv": [{
            "assembly_scope": "AS01", "band_id": "primary", "normalization": "demeaned",
            "u4enc_minus_u4sym_gain": "0.5981566709541523",
            "bootstrap_ci95_low": "-0.11310886268350098",
            "bootstrap_ci95_high": "1.0842695384282073",
        }],
        "configuration_effects.csv": [
            {"assembly_id": "AS01", "direction_deg": value,
             "band_id": "primary", "configuration_to_repeatability_ratio": ratio}
            for value, ratio in zip(
                ("0", "90", "180", "270"),
                ("1.3381141893603399", "1.916902365598791", "1.7529587562831503", "1.3845747554064556"),
                strict=True,
            )
        ],
        "grouped_validation_metrics.csv": [
            {"scope_id": "U4SYM_AS01", "balanced_accuracy": "0.375", "macro_f1": "0.25"},
            {"scope_id": "U4ENC_AS01", "balanced_accuracy": "0.25", "macro_f1": "0.18333333333333335"},
        ],
        "outlier_sensitivity.csv": [{
            "flagged_curve_count": "10", "conclusion_changed_between_variants": "false",
            "selection_manifest_changed": "false",
        }],
    }
    validate_formal4_numeric_trace(_frozen_summary(), tables)

    tables["grouped_validation_metrics.csv"][1]["balanced_accuracy"] = "0.75"
    with pytest.raises(Formal5InputError, match="U4ENC balanced accuracy CSV"):
        validate_formal4_numeric_trace(_frozen_summary(), tables)

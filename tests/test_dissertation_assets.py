from __future__ import annotations

import csv
import json
from pathlib import Path

from acoustic_encoder.dissertation_assets import verify_dissertation_assets


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "dissertation"


def _rows(name: str) -> list[dict[str, str]]:
    with (DOCS / "tables" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_write2_assets_match_manifest_and_publication_constraints() -> None:
    result = verify_dissertation_assets(DOCS)

    assert result == {
        "all_match": True,
        "figure_count": 7,
        "figure_file_count": 14,
        "table_count": 4,
        "table_file_count": 8,
        "minimum_png_dpi": 300,
    }


def test_write2_manifest_preserves_frozen_claim_and_selection_boundary() -> None:
    manifest = json.loads(
        (DOCS / "FIGURE_AND_TABLE_MANIFEST.json").read_text(encoding="utf-8")
    )

    assert manifest["disposition"] == "supported_with_limits"
    assert manifest["hypothesis_decisions"] == {
        "H0": "not_rejected",
        "H1": "not_confirmed",
    }
    assert manifest["selection"] == {
        "active_count": 72,
        "excluded_count": 19,
        "outlier_flag_count": 10,
        "selection_changed": False,
    }
    assert manifest["final_test_read"] is False
    assert manifest["provenance"] == {
        "data_origin": "real_experiment",
        "dataset_role": "research_analysis",
        "run_purpose": "research_analysis",
        "scientifically_eligible": False,
    }


def test_write2_tables_reproduce_frozen_values_without_reestimation() -> None:
    repeatability = _rows("table_01_repeatability_floor.csv")
    direction_gain = _rows("table_02_direction_gain.csv")
    classification = _rows("table_03_grouped_classification.csv")

    primary = next(row for row in repeatability if row["band"].startswith("Primary"))
    assert float(primary["median_rms_db"]) == 0.3783
    assert float(primary["iqr_db"]) == 0.2191
    assert float(primary["p95_rms_db"]) == 0.8793

    enc = next(row for row in direction_gain if row["configuration_or_contrast"] == "U4ENC")
    sym = next(row for row in direction_gain if row["configuration_or_contrast"] == "U4SYM")
    delta = next(row for row in direction_gain if row["configuration_or_contrast"] == "U4ENC − U4SYM")
    assert float(enc["G_demeaned_or_delta"]) == 1.2805
    assert float(enc["ci95_low"]) == 0.8297
    assert float(sym["G_demeaned_or_delta"]) == 0.6824
    assert float(delta["G_demeaned_or_delta"]) == 0.5982
    assert float(delta["ci95_low"]) < 0.0 < float(delta["ci95_high"])

    as01 = {row["scope"]: row for row in classification}
    assert float(as01["U4SYM_AS01"]["balanced_accuracy"]) == 0.375
    assert float(as01["U4ENC_AS01"]["balanced_accuracy"]) == 0.25
    assert all(float(row["practical_target"]) == 0.5 for row in as01.values())

    sensitivity = _rows("table_04_outlier_sensitivity.csv")
    config = next(row for row in sensitivity if row["metric"] == "AS01 configuration/floor")
    assert float(config["all_72_active"]) == 1.5688


def test_write2_results_and_checklist_reference_the_frozen_asset_set() -> None:
    results = (DOCS / "RESULTS_DRAFT.md").read_text(encoding="utf-8")
    checklist = (DOCS / "RESULTS_CLAIM_CHECKLIST.md").read_text(encoding="utf-8")

    for number in range(1, 8):
        assert f"figure_{number:02d}_" in results
    for number in range(1, 5):
        assert f"table_{number:02d}_" in results
    assert "supported_with_limits" in checklist
    assert "H0 remains `not_rejected`" in checklist
    assert "H1 remains `not_confirmed`" in checklist
    assert "`final_test_read=false`" in checklist
    assert "U4ENC was proved superior to U4SYM" in checklist

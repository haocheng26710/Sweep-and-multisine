from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from acoustic_encoder.dissertation_assets import verify_dissertation_assets


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "dissertation"
FINAL = DOCS / "EXPERIMENTAL_CHAPTERS_FINAL.md"
CITATIONS = DOCS / "FINAL_CITATION_REQUIREMENTS.md"
AUDIT = DOCS / "FINAL_CONSISTENCY_AUDIT.md"
MANIFEST = DOCS / "FINAL_DELIVERY_MANIFEST.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown_targets(text: str) -> list[str]:
    return re.findall(r"!?(?:\[[^\]]*\])\(([^)]+)\)", text)


def _prose_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped:
            continue
        lines = stripped.splitlines()
        if all(
            line.startswith(("#", "- ", "|", ">", "![", "*Figure", "*Table"))
            or re.match(r"^\d+\. ", line)
            for line in lines
        ):
            continue
        paragraphs.append(" ".join(line.strip() for line in lines))
    return paragraphs


def test_write4_final_documents_exist_and_preserve_frozen_state() -> None:
    for path in (FINAL, CITATIONS, AUDIT, MANIFEST):
        assert path.is_file()

    text = FINAL.read_text(encoding="utf-8")
    for token in (
        "72 ACTIVE",
        "19 EXCLUDED",
        "0.3783 dB",
        "0.2191 dB",
        "0.8793 dB",
        "1.2805",
        "0.8297–1.7667",
        "0.6824",
        "0.6105–1.2699",
        "0.5982",
        "-0.1131–1.0843",
        "6/6",
        "3/6",
        "1.5688",
        "0.375",
        "0.250",
        "0.183",
        "0.50",
        "200–4000 Hz",
        "4000–8000 Hz",
        "48 points per octave",
        "1/12-octave",
        "200 Hz boundary point remained invalid",
        "supported_with_limits",
        "H0=not_rejected",
        "H1=not_confirmed",
        "scientifically_eligible=false",
        "final_test_read=false",
        "final-test remained sealed",
    ):
        assert token in text

    assert all(len(paragraph) <= 240 for paragraph in _prose_paragraphs(text))


def test_write4_figure_table_links_and_write2_assets_are_complete() -> None:
    text = FINAL.read_text(encoding="utf-8")
    for number in range(1, 8):
        assert f"Figure {number}" in text
    for number in range(1, 5):
        assert f"Table {number}" in text

    for target in _markdown_targets(text):
        if "://" not in target and not target.startswith("#"):
            assert (FINAL.parent / target).resolve().is_file(), target

    assert verify_dissertation_assets(DOCS) == {
        "all_match": True,
        "figure_count": 7,
        "figure_file_count": 14,
        "table_count": 4,
        "table_file_count": 8,
        "minimum_png_dpi": 300,
    }


def test_write4_citation_register_matches_every_marker() -> None:
    final_ids = re.findall(r"\[CITATION NEEDED: (C\d{2}) — [^\]]+\]", FINAL.read_text(encoding="utf-8"))
    register = CITATIONS.read_text(encoding="utf-8")
    register_ids = re.findall(r"^\| (C\d{2}) \|", register, flags=re.MULTILINE)

    assert final_ids == [f"C{number:02d}" for number in range(1, 14)]
    assert register_ids == final_ids
    assert register.count("[CITATION NEEDED:") == 0
    assert "DOI" not in register


def test_write4_claim_boundary_contains_no_forbidden_positive_claims() -> None:
    text = FINAL.read_text(encoding="utf-8").lower()
    forbidden = (
        "h1 was confirmed",
        "u4enc was proved superior",
        "u4enc was proven superior",
        "reliable four-direction classification was achieved",
        "as01/as02 difference has a causal",
        "absolute spl calibration was established",
        "experiment was conducted in an anechoic",
        "experiment was conducted in a semi-anechoic",
        "h1 已确认",
        "u4enc 已被证明优于",
        "已实现可靠四方向分类",
    )
    assert not any(phrase in text for phrase in forbidden)


def test_write4_delivery_manifest_hashes_and_gates_are_valid() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["disposition"] == "supported_with_limits"
    assert manifest["hypothesis_decisions"] == {"H0": "not_rejected", "H1": "not_confirmed"}
    assert manifest["selection"] == {
        "active_count": 72,
        "excluded_count": 19,
        "outlier_flag_count": 10,
        "selection_changed": False,
    }
    assert manifest["scientifically_eligible"] is False
    assert manifest["final_test_read"] is False
    assert manifest["final_test_status"] == "sealed"
    assert manifest["analysis_recomputed"] is False
    assert manifest["figures_regenerated"] is False
    assert manifest["manifest_self_hash_excluded"] is True

    listed = {item["path"] for item in manifest["files"]}
    required = {
        "docs/dissertation/EXPERIMENTAL_CHAPTERS_FINAL.md",
        "docs/dissertation/FINAL_CITATION_REQUIREMENTS.md",
        "docs/dissertation/FINAL_CONSISTENCY_AUDIT.md",
        "docs/progress/WRITE-4_FINAL_DELIVERY.md",
        "docs/progress/INDEX.md",
    }
    assert required <= listed
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        assert _sha256(path) == item["sha256"], item["path"]

    assert manifest["write2_asset_verification"] == {
        "all_match": True,
        "figure_count": 7,
        "figure_file_count": 14,
        "table_count": 4,
        "table_file_count": 8,
        "minimum_png_dpi": 300,
    }

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from acoustic_encoder.dissertation_assets import verify_dissertation_assets


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "dissertation"
WRITE3_FILES = (
    DOCS / "METHODS_DRAFT.md",
    DOCS / "DISCUSSION_DRAFT.md",
    DOCS / "LIMITATIONS_AND_FUTURE_WORK.md",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prose_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    in_fence = False
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if "```" in stripped:
            in_fence = not in_fence
            continue
        if not stripped or in_fence:
            continue
        lines = stripped.splitlines()
        if all(
            line.startswith(("#", "- ", "|", ">", "$$", "\\[", "\\]"))
            or re.match(r"^\d+\. ", line)
            for line in lines
        ):
            continue
        paragraphs.append(" ".join(line.strip() for line in lines))
    return paragraphs


def test_write3_documents_preserve_frozen_authority_and_claim_boundary() -> None:
    texts = {path.name: path.read_text(encoding="utf-8") for path in WRITE3_FILES}
    combined = "\n".join(texts.values())
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
    assert manifest["provenance"]["scientifically_eligible"] is False

    for token in (
        "supported_with_limits",
        "H0=not_rejected",
        "H1=not_confirmed",
        "scientifically_eligible=false",
        "final_test_read=false",
        "72 ACTIVE",
        "19 EXCLUDED",
        "0.3783 dB",
        "0.8793 dB",
        "1.2805",
        "0.6824",
        "0.5982",
        "-0.1131–1.0843",
        "1.5688",
        "0.375",
        "0.250",
        "0.50",
    ):
        assert token in combined

    prohibited = (
        "proved superior",
        "confirmed superior",
        "reliable four-direction classification",
        "significant causal effect",
        "证明",
        "确认优于",
        "可靠分类",
        "显著因果效应",
    )
    assert not any(phrase.lower() in combined.lower() for phrase in prohibited)


def test_write3_methods_match_frozen_protocol_and_realized_design() -> None:
    methods = WRITE3_FILES[0].read_text(encoding="utf-8")

    for token in (
        "REW V5.31.3",
        "48 kHz",
        "256k",
        "No timing reference",
        "IR peak",
        "200–8000 Hz",
        "-30 dBFS",
        "Windows output volume 50",
        "iMM-6C input volume 100",
        "CMM29939.txt",
        "48 points per octave",
        "1/12-octave",
        "200–4000 Hz",
        "4000–8000 Hz",
        "2,000",
        "999",
    ):
        assert token in methods
    assert "absolute sound-pressure-level calibration" in methods
    assert "not available" in methods


def test_write3_discussion_references_only_the_frozen_figure_set() -> None:
    discussion = WRITE3_FILES[1].read_text(encoding="utf-8")

    for number in range(1, 8):
        assert f"Figure {number}" in discussion
    for number in range(1, 5):
        assert f"Table {number}" in discussion
    assert "exploratory" in discussion
    assert "block/time" in discussion


def test_write3_citations_paragraphs_and_asset_hashes_are_auditable() -> None:
    texts = [path.read_text(encoding="utf-8") for path in WRITE3_FILES]
    citation_count = sum(text.count("[CITATION NEEDED:") for text in texts)

    assert citation_count >= 5
    for text in texts:
        assert all(len(paragraph) <= 240 for paragraph in _prose_paragraphs(text))
    assert verify_dissertation_assets(DOCS) == {
        "all_match": True,
        "figure_count": 7,
        "figure_file_count": 14,
        "table_count": 4,
        "table_file_count": 8,
        "minimum_png_dpi": 300,
    }
    assert all(len(_sha256(path)) == 64 for path in WRITE3_FILES)

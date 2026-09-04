"""Read-only manuscript checks; optional additive packaging after visual review.

No scientific pipeline, model, or experimental dataset is evaluated here.
Inputs are restricted to this article package and its Draft-17 source package.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "THESIS_DRAFT_17_ENGLISH_FIRST_IEEE_RELEASE"
NAME = "THESIS_DRAFT_18_METHODS_CLARITY_IEEE"
SECTIONS = ["01_introduction.tex", "02_research_methodology.tex", "03_results.tex", "04_discussion_conclusions.tex"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(lang, base=ROOT):
    paths = [base / lang / "main.tex"] + [base / lang / "sections" / n for n in SECTIONS]
    return "\n".join(p.read_text(encoding="utf-8") for p in paths)


def commands(text, cmd):
    return re.findall(r"\\" + cmd + r"(?:\[[^\]]*\])?\{([^}]+)\}", text)


def equations(text):
    result = []
    for eq in re.findall(r"\\begin\{equation\}([\s\S]*?)\\end\{equation\}", text):
        eq = re.sub(r"\\(?:begin|end)\{aligned\}|\\label\{[^}]+\}", "", eq)
        eq = eq.replace("\\\\", "").replace("&", "").replace("{}", "")
        result.append(re.sub(r"\s+", "", eq))
    return result


def prose(text):
    # Remove layout-only lines, never the prose following an inline reference.
    return "\n".join(line for line in text.splitlines() if not re.match(
        r"\s*\\(?:input|includegraphics|graphicspath|setlength|newcolumntype|begin\{tabular)", line))


def check():
    texts = {lang: read(lang) for lang in ("english", "chinese")}
    old = read("english", BASE)
    en, zh = texts["english"], texts["chinese"]
    checks = {}
    checks["equations_unchanged_from_draft17"] = equations(old) == equations(en)
    checks["bilingual_equations_identical"] = equations(en) == equations(zh)
    checks["citation_inventory_unchanged"] = Counter(commands(old, "cite")) == Counter(commands(en, "cite"))
    checks["bilingual_citation_sequence_identical"] = commands(en, "cite") == commands(zh, "cite")
    checks["single_source_per_citation"] = all("," not in key for key in commands(en, "cite"))
    checks["no_repeated_citation_keys"] = all(v == 1 for v in Counter(commands(en, "cite")).values())
    checks["labels_preserved"] = set(commands(old, "label")).issubset(set(commands(en, "label")))
    checks["bilingual_labels_identical"] = commands(en, "label") == commands(zh, "label")
    # Chinese adjacency and an English full stop must not hide a numeric token.
    decimal = lambda t: set(re.findall(r"(?<![A-Za-z0-9_.])\d+\.\d+(?![A-Za-z0-9_]|\.\d)", prose(t)))
    missing = sorted(decimal(old) - decimal(en))
    checks["all_original_decimal_values_preserved"] = not missing
    checks["bilingual_decimal_values_identical"] = decimal(en) == decimal(zh)
    checks["no_suspended_hyphens"] = not re.search(r"\w-\s+(?:and|or)\b|\d-\s*,|\w-/", en)
    checks["ascii_punctuation_in_english_source"] = not re.search("[\u2010-\u2015\u2212\uff0c\uff1b\uff1a]", en)
    checks["negative_results_preserved"] = all(s in en for s in ("0.250", "0.25", "$-0.1131$", "$-0.239$", "0.7075", "0.0901", "80/80"))
    integer_values = ("72", "86", "15", "80", "20", "3675", "1216", "1510", "1849", "2198", "2652", "3200", "3917", "4397", "974", "964", "954", "944", "932", "1152", "1058", "860", "756", "1150", "1050", "950", "850", "750", "1120", "1192", "1020", "1094", "928", "976", "836", "880", "736", "780", "26", "44", "48", "56")
    checks["key_counts_and_frequency_values_preserved"] = all(re.search(r"(?<!\d)" + x + r"(?!\d)", t) for t in (en, zh) for x in integer_values)
    checks["three_evidence_boundaries_preserved"] = all(s in en for s in ("one return sequence", "sealed five-node reduced-order model", "not establish experimental validity"))
    checks["no_legacy_device_names"] = not re.search(r"microplenum|opposed device|acoustic tray|common-head|compact apparatus|heterogeneous device|straight array|four-band array", en, re.I)
    checks["reference_databases_match"] = sha(ROOT / "english/references.bib") == sha(ROOT / "chinese/references.bib")
    checks["new_model_reference_resolves"] = "sec:model-diagnosis" in commands(en, "label")
    checks["obsolete_single_entry_isolation_wording_removed"] = all(x not in en for x in (
        "Eight isolated two-neck", "Measurements of eight such resonator modules in isolation", "did not remove directional sensitivity"))
    checks["file_exclusion_sentence_removed_from_both_bodies"] = "19 incomplete" not in en and "19个不完整" not in zh
    checks["new_definitions_present"] = all(x in en for x in ("small network of pressure nodes", "six distinct unordered pairs", "polarity consistency of at least 0.8", "fixed-seed random/disordered", "four local cavities and one common readout cavity"))
    checks["eight_design_targets_present"] = "1.20, 1.50, 1.85, 2.25, 2.70, 3.20, 3.80, and 4.50" in en
    checks["nominal_volume_precedes_realised_geometry"] = en.index("initial design targets were 75") < en.index("75.826")
    checks["chinese_unicode_intact"] = "\ufffd" not in zh and all(x in zh for x in ("单入口标定", "五个声压节点", "结论"))
    build = {}
    for lang, text in texts.items():
        labels = set(commands(text, "label"))
        checks[f"{lang}_references_resolve"] = all(x in labels for cmd in ("ref", "eqref") for x in commands(text, cmd))
        figures = commands(text, "includegraphics")
        checks[f"{lang}_figure_paths_exist"] = all((ROOT / lang / "figures" / f).is_file() for f in figures)
        log = (ROOT / lang / "main.log").read_text(encoding="utf-8", errors="replace")
        defects = re.findall(r"(?m)^.*(?:Overfull \\[hv]box|LaTeX Error|Missing character|LaTeX Warning: (?:Reference|Citation).*undefined|There were undefined references).*$", log)
        checks[f"{lang}_build_clean"] = not defects
        pdf = PdfReader(ROOT / lang / "main.pdf")
        page_text = [p.extract_text() or "" for p in pdf.pages]
        reference_pages = [i+1 for i, t in enumerate(page_text) if re.search(r"(?im)^\s*r\s*e\s*f\s*e\s*r\s*e\s*n\s*c\s*e\s*s\s*$|参考文献", t)]
        build[lang] = {"pages": len(pdf.pages), "references_start_page": reference_pages[0] if reference_pages else None, "figures": len(figures), "tables": len(re.findall(r"\\begin\{table\*?\}", text)), "equations": len(equations(text)), "unique_cited_references": len(set(commands(text, "cite"))), "defects": defects}
    baseline_hashes = {
        "THESIS_DRAFT_17_ENGLISH_FIRST_IEEE_EN.pdf": "0b1e28fa2592d17f74bcd0882648534a4aa285ac20aa939e2399d518d26e3dcf",
        "THESIS_DRAFT_17_ENGLISH_FIRST_IEEE_ZH.pdf": "77e8272b7d5e2a61e8a2af5cf4428664e5fbbaf380ead4a6e5bb6c2afb3c7ae8",
    }
    checks["prior_release_pdfs_unchanged"] = all(sha(BASE / p) == h for p, h in baseline_hashes.items())
    for folder in ("evidence", "figure_sources", "source_photos", "supplementary"):
        checks[f"{folder}_unchanged"] = all(sha(p) == sha(BASE / p.relative_to(ROOT)) for p in (ROOT / folder).rglob("*") if p.is_file())
    for lang in texts:
        charts = ("physical_workflow_and_architectures.pdf", "four_state_physical_validation.png", "two_state_physical_response.png", "five_level_bounded_tracking.png", "fullwave_model_and_field.pdf")
        checks[f"{lang}_scientific_graphics_unchanged"] = all(sha(ROOT / lang / "figures" / f) == sha(BASE / lang / "figures" / f) for f in charts)
    abstract = re.search(r"\\begin\{abstract\}([\s\S]*?)\\end\{abstract\}", en).group(1)
    result = {"english_first": True, "final_test_read": False, "new_scientific_runs": False, "checks": checks, "build": build, "missing_original_decimal_values": missing, "abstract_word_count_approx": len(re.findall(r"\b[A-Za-z]+(?:[-'][A-Za-z]+)*\b|\b\d+(?:\.\d+)?\b", abstract)), "bilingual_decimal_differences": {"english_only": sorted(decimal(en)-decimal(zh)), "chinese_only": sorted(decimal(zh)-decimal(en))}}
    (ROOT / "validation_checks.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit("Failed checks: " + ", ".join(k for k,v in checks.items() if not v))
    return texts


def package(texts):
    for lang, suffix in (("english", "EN"), ("chinese", "ZH")):
        target_pdf = ROOT / f"{NAME}_{suffix}.pdf"
        target_pdf.write_bytes((ROOT / lang / "main.pdf").read_bytes())
        selected = [ROOT / lang / n for n in ("main.tex", "references.bib", "latexmkrc", "README.md")]
        selected += [ROOT / lang / "sections" / n for n in SECTIONS]
        selected += [ROOT / lang / "figures" / n for n in commands(texts[lang], "includegraphics")]
        with zipfile.ZipFile(ROOT / f"{NAME}_{suffix}_OVERLEAF.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for p in selected:
                archive.write(p, p.relative_to(ROOT / lang).as_posix())
        with zipfile.ZipFile(ROOT / f"{NAME}_{suffix}_OVERLEAF.zip") as archive:
            assert archive.testzip() is None
            assert all(not n.startswith("/") and ".." not in n.split("/") for n in archive.namelist())
    excluded = {"artifact_inventory.json", "SHA256SUMS.txt"}
    generated_extensions = {".aux", ".log", ".out", ".blg", ".bbl", ".pyc"}
    paths = sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name not in excluded and "__pycache__" not in p.parts and not (p.parent.name in ("english", "chinese") and (p.suffix in generated_extensions or p.name == "main.pdf")))
    records = [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in paths]
    (ROOT / "artifact_inventory.json").write_text(json.dumps({"package": NAME, "final_test_read": False, "artifacts": records}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = records + [{"path": "artifact_inventory.json", "sha256": sha(ROOT / "artifact_inventory.json")}]
    (ROOT / "SHA256SUMS.txt").write_text("".join(f"{r['sha256']}  {r['path']}\n" for r in manifest), encoding="utf-8")
    assert all(sha(ROOT / r["path"]) == r["sha256"] for r in manifest)
    print(f"Packaged {len(records)} files; SHA-256 verification passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    texts = check()
    if args.package:
        package(texts)

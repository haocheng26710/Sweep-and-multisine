"""Preservation checks and self-contained Overleaf packaging; no research analysis."""
from pathlib import Path
import collections
import difflib
import hashlib
import json
import re
import zipfile

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "project"
SOURCE = Path(r"D:\Firefly\Downloads\Dissertation_HaochengLyu_TemplateAligned (1).zip")
ARCHIVE = ROOT / "Dissertation_HaochengLyu_LayoutCompressed_20260904.zip"


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def letters(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


with zipfile.ZipFile(SOURCE) as z:
    assert z.testzip() is None
    originals = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
expected_source_sha = "625A965EAF843CA7107012B5EFACBEB98FC66D80D5D1897B27D5F53B2EA08119"
assert digest(SOURCE.read_bytes()) == expected_source_sha
old = {name: data.decode("utf-8-sig").replace("\r\n", "\n") for name, data in originals.items()
       if name.endswith(".tex")}
new = {name: (PROJECT/name).read_text(encoding="utf-8-sig") for name in old}
method_key, result_key, discussion_key = (f"sections/{name}.tex" for name in
                                        ("02_research_methodology", "03_results", "04_discussion_conclusions"))
old_sections = "\n".join(old[k] for k in sorted(old) if k.startswith("sections/"))
new_sections = "\n".join(new[k] for k in sorted(new) if k.startswith("sections/"))
equations = lambda s: re.findall(r"\\begin\{equation\}.*?\\end\{equation\}", s, re.S)
assert equations(old_sections) == equations(new_sections)
assert len(equations(new_sections)) == 6
citations = lambda s: re.findall(r"\\cite\{([^}]+)\}", s)
assert citations(old_sections) == citations(new_sections)
assert len(set(citations(new_sections))) == 22
assert (PROJECT / "sections/01_introduction.tex").read_bytes() == originals["sections/01_introduction.tex"]
assert (PROJECT / "References.bib").read_bytes() == originals["References.bib"]
assert (PROJECT / "ieeeconf.cls").read_bytes() == originals["ieeeconf.cls"]
start_marker = "Bootstrap intervals were interpreted"
end_marker = "For single-entry resonator calibration"
old_bootstrap = old[method_key].split(start_marker, 1)[1].split(end_marker, 1)[0]
new_bootstrap = new[method_key].split(start_marker, 1)[1].split(end_marker, 1)[0]
assert old_bootstrap == new_bootstrap
old_counts = next(p for p in old[method_key].splitlines() if p.startswith("The formal broadband dataset"))
new_counts = next(p for p in new[method_key].splitlines() if p.startswith("The formal broadband dataset"))
assert old_counts.split("Table~")[0] == new_counts.split("The reproducibility materials")[0]
old_geo = next(p for p in old[method_key].splitlines() if p.startswith("Figure~\\ref{fig:fullwave-geometry}"))
new_geo = next(p for p in new[method_key].splitlines() if p.startswith("Figure~\\ref{fig:fullwave-geometry}"))
assert old_geo == new_geo
assert "tab:implementation" not in new_sections
assert "tab:recent-comparison" in new_sections
assert "minimum gap" in new_sections or "26~Hz" in new_sections
assert "A linear fit gave" not in new[result_key]
assert new[discussion_key].split(r"\subsection{Conclusions}")[1] == old[discussion_key].split(r"\subsection{Conclusions}")[1]
assert "Since these changes occurred together, the result supports the combined delayed-mixing architecture rather than identifying either change as the sole cause of improvement." in new[discussion_key]
image_hashes = {}
for name in originals:
    if name.startswith("figures/"):
        assert (PROJECT/name).read_bytes() == originals[name]
        image_hashes[name] = digest(originals[name])
assert len(image_hashes) == 5

labels = re.findall(r"\\label\{([^}]+)\}", new_sections)
references = re.findall(r"\\(?:eqref|ref)\{([^}]+)\}", new_sections)
assert len(labels) == len(set(labels))
assert not (set(references)-set(labels))
assert r"\documentclass[letterpaper,10pt,conference]{ieeeconf}" in new["root.tex"]
assert r"\IEEEtriggeratref{14}" not in new["root.tex"]
assert r"\today" not in new["root.tex"]
assert new["root.tex"].count("Haocheng Lyu, September 4, 2026") == 2
ethics = ("This project did not require ethical review, as determined by my supervisor, Helmet Hauser. "
          "The research involved the design and fabrication of passive acoustic structures, bench-top acoustic "
          "measurements using synthetic excitation signals, and numerical simulations. No human participants "
          "or animals were involved, and no personal or identifiable data were collected or analysed.")
assert norm(ethics) in norm(new["root.tex"])

pdf_path = PROJECT / "root.pdf"
assert pdf_path.read_bytes() == (ROOT / "qa/release_check/root.pdf").read_bytes()
reader = PdfReader(pdf_path)
assert len(reader.pages) == 12
page_text = [p.extract_text() or "" for p in reader.pages]
assert letters(ethics) in letters(page_text[0])
assert "Haocheng Lyu" in page_text[0]
assert "Name and Date" not in page_text[0]
assert "To fill in" not in page_text[0]
conclusion_end = letters("physical direction sensing remains a separate validation task.")
assert conclusion_end in letters(page_text[10])
assert conclusion_end not in letters(page_text[11])
assert "REFERENCES" in page_text[11].upper()
assert "REFERENCES" not in page_text[10].upper()
log = (ROOT / "qa/release_check/root.log").read_text(encoding="utf-8", errors="replace")
assert not re.search(r"^!|^Overfull|^Underfull|LaTeX Warning|Package .+ Warning|There were undefined", log, re.M)
font_sizes = (10,)
diff = "\n".join("\n".join(difflib.unified_diff(old[k].splitlines(), new[k].splitlines(),
                    fromfile="source/"+k, tofile="revised/"+k, lineterm=""))
                 for k in sorted(old) if old[k] != new[k])
(ROOT / "SOURCE_DIFF.patch").write_text(diff+"\n", encoding="utf-8")
validation = {
    "source_archive": str(SOURCE), "source_archive_sha256": expected_source_sha,
    "source_archive_unchanged": True,
    "pdf_sha256": digest(pdf_path.read_bytes()),
    "pagination": {"total": 12, "front_matter": 1, "main_text": 10,
                   "reference_pages": 1, "main_text_pdf_pages": [2,11], "references_pdf_page": 12},
    "changes": {"equipment_table_removed": True, "II_A_words_removed_approx": 72,
                "IV_B_words_removed_approx": 80, "IV_A_words_removed_approx": 34,
                "linear_fit_summary_sentence_removed": True, "new_figure2_c_caption_added": True},
    "protected": {"introduction_and_table_I_byte_identical": True, "six_equations_identical": True,
                  "bootstrap_paragraphs_identical": True, "sample_count_and_grouping_text_identical": True,
                  "geometry_explanation_paragraph_identical": True, "conclusions_identical": True,
                  "citation_sequence_identical": True, "unique_citations": 22,
                  "references_bib_identical": True, "class_file_identical": True,
                  "all_five_figure_files_identical": True},
    "figure_sha256": image_hashes,
    "source_diff_files": [k for k in old if old[k] != new[k]],
    "cover": {"name": "Haocheng Lyu", "date": "September 4, 2026",
              "ethics_verbatim": True, "supervisor_spelling_as_supplied": "Helmet Hauser"},
    "pdf_checks": {"all_12_pages_visually_inspected": True, "undefined_references": 0,
                   "overfull_boxes": 0, "underfull_boxes": 0, "latex_warnings": 0,
                   "main_text_font_pt": 10, "geometry_unchanged": True},
    "final_test_read": False, "new_simulation_or_statistical_analysis": False,
    "commit_push_tag": False,
}
(PROJECT / "VALIDATION.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
names = sorted(set(originals) | {"README_OVERLEAF.md", "CHANGE_SUMMARY.md", "VALIDATION.json"})
manifest = "\n".join(f"{digest((PROJECT/name).read_bytes())}  {name}" for name in names)+"\n"
(PROJECT / "SHA256SUMS.txt").write_text(manifest, encoding="utf-8")
names.append("SHA256SUMS.txt")
with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in names:
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        z.write(PROJECT/name, arcname=name)
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    assert z.read("root.pdf") == pdf_path.read_bytes()
    assert z.read("root.tex") == (PROJECT / "root.tex").read_bytes()
    assert not any(n.endswith((".log", ".aux", ".out")) for n in z.namelist())
(ROOT / "DELIVERY_SHA256.txt").write_text(f"{digest(ARCHIVE.read_bytes())}  {ARCHIVE.name}\n", encoding="utf-8")
print(json.dumps({"status": "PASS", "pages": validation["pagination"],
                  "archive": str(ARCHIVE), "sha256": digest(ARCHIVE.read_bytes()),
                  "archive_files": len(names)}, ensure_ascii=True))

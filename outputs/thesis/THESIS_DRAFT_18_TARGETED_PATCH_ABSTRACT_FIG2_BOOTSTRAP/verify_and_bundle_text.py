"""Read-only source checks; write only derived documentation inside this patch."""
from pathlib import Path
import csv
import hashlib
import json
import re

from PIL import Image

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
PAPER = ROOT.parent / "THESIS_DRAFT_18_METHODS_CLARITY_IEEE_RELEASE"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def text(path):
    return path.read_text(encoding="utf-8-sig")


sources = [
    REPO / "scripts/gen_enc_24_print_comp/GenEnc24PrintComp.java",
    REPO / "src/acoustic_encoder/formal_core_analysis.py",
    REPO / "src/acoustic_encoder/trans1_two_port_physical_analysis.py",
    REPO / "outputs/formal/FORMAL-4_CORE_ANALYSIS/direction_gain_summary.csv",
    REPO / "outputs/formal/FORMAL-4_CORE_ANALYSIS/direction_gain_contrasts.csv",
    REPO / "outputs/real_experiment/research_analysis/TRANS1_TWO_PORT_PHYSICAL_PILOT/analysis_summary.json",
    REPO / "outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B/FC_L0900_A05_size2.mph",
    PAPER / "figure_sources/stored_fullwave_geometry.png",
    PAPER / "figure_sources/stored_pressure_field_954hz.png",
    PAPER / "figure_sources/ExportExistingFullWaveFigures.java",
    PAPER / "FIGURE_SOURCE_AUDIT.md",
]
for language in ("english", "chinese"):
    sources.extend([PAPER / language / "main.tex",
                    PAPER / language / "sections/02_research_methodology.tex",
                    PAPER / language / "sections/03_results.tex"])
before = {str(path.relative_to(REPO)).replace("\\", "/"): sha(path) for path in sources}
assert before["outputs/gen_enc/GEN_ENC_26_PRINT_CONV_B/FC_L0900_A05_size2.mph"] == "1FBE0A42B644CC6B1129CE61A9BE820AB4D910899D4C830812C2466E1E219089"
assert before["outputs/formal/FORMAL-4_CORE_ANALYSIS/direction_gain_summary.csv"] == "8D7791041CCD55067ED4ABE3F4F5D1BF6E4A7CE0167887E9D2B31FF3C02F7DBF"
assert before["outputs/formal/FORMAL-4_CORE_ANALYSIS/direction_gain_contrasts.csv"] == "8F77DB86D1E9EB7DE8A6ADAE6215461CFE9318D1A815637E7A07E463B6827B52"

with sources[3].open(encoding="utf-8-sig", newline="") as file:
    rows = list(csv.DictReader(file))
gains = [row for row in rows if row["assembly_scope"] == "AS01" and
         row["band_id"] == "primary" and row["normalization"] == "demeaned"]
assert len(gains) == 2
for row in gains:
    assert row["bootstrap_iterations"] == "2000"
    assert row["bootstrap_method"] == "block_cluster_and_direction_REPOS_resampling"
    assert row["between_direction_pair_count"] == "12"
    assert row["reposition_pair_count"] == "4"
with sources[4].open(encoding="utf-8-sig", newline="") as file:
    contrasts = list(csv.DictReader(file))
contrast = next(row for row in contrasts if row["band_id"] == "primary" and row["normalization"] == "demeaned")
assert contrast["bootstrap_method"] == "independent_configuration_block_cluster_and_direction_REPOS_resampling"
binary = json.loads(text(sources[5]))
assert binary["counts"]["N"] == 6 and binary["counts"]["S"] == 6 and binary["counts"]["NRETURN"] == 3
assert binary["bootstrap"]["iterations"] == 2000
assert binary["final_test_read"] is False

old_bootstrap_en = r"Bootstrap intervals resampled complete curves within their physical groups, following the principle that clustered observations require resampling at the independent-unit level \cite{FieldWelsh2007}."
old_bootstrap_zh = r"Bootstrap区间在实体分组内重采样完整曲线，遵循聚类观测应在独立单元层级进行重采样的原则 \cite{FieldWelsh2007}。"
old_geo_en = "Four boundary excitations provide the inputs, and a central point supplies the readout."
old_geo_zh = "四个边界激励提供输入，中央点提供读出。"
old_binary_en = r"The distance between the north and south spectral centres was \SI{2.069}{\decibel}, with a complete-curve bootstrap interval of \SIrange{2.056}{2.188}{\decibel}."
old_binary_zh = r"紧凑型双支路装置的15条记录曲线全部进入分析，南北频谱中心距离为\SI{2.069}{\decibel}，完整曲线Bootstrap区间为\SIrange{2.056}{2.188}{\decibel}。"


def replace_once(body, old, new):
    assert body.count(old) == 1, old
    return body.replace(old, new, 1)


def balanced(body):
    # Unescaped braces only; all fragments use conventional LaTeX grouping.
    stack = 0
    for symbol in re.findall(r"(?<!\\)[{}]", body):
        stack += 1 if symbol == "{" else -1
        assert stack >= 0
    assert stack == 0


checks = {}
fragments = ["abstract", "bootstrap_methods", "geometry_clarification", "figure2",
             "figure3_caption", "binary_result_sentence"]
for lang, full in (("en", "english"), ("zh", "chinese")):
    main = text(PAPER / full / "main.tex")
    methods = text(PAPER / full / "sections/02_research_methodology.tex")
    results = text(PAPER / full / "sections/03_results.tex")
    combined_before = main + methods + results
    frag = {stem: text(ROOT / f"{stem}_{lang}.tex").strip() for stem in fragments}
    for body in frag.values():
        balanced(body)
        assert "\ufffd" not in body
    old_abstract = re.search(r"\\begin\{abstract\}.*?\\end\{abstract\}", main, re.S).group()
    new_main = replace_once(main, old_abstract, frag["abstract"])
    new_methods = replace_once(methods, old_bootstrap_en if lang == "en" else old_bootstrap_zh,
                               "\n\n" + frag["bootstrap_methods"])
    new_methods = replace_once(new_methods, old_geo_en if lang == "en" else old_geo_zh,
                               frag["geometry_clarification"])
    environments = re.findall(r"\\begin\{figure\*\}.*?\\end\{figure\*\}", new_methods, re.S)
    old_fig2 = next(block for block in environments if r"\label{fig:fullwave-geometry}" in block)
    new_methods = replace_once(new_methods, old_fig2, frag["figure2"])
    old_fig3_caption = next(line.strip() for line in results.splitlines()
                            if line.strip().startswith(r"\caption{") and
                            ("Physical four-state result" in line or "实体四状态结果" in line))
    new_results = replace_once(results, old_fig3_caption, frag["figure3_caption"])
    new_results = replace_once(new_results, old_binary_en if lang == "en" else old_binary_zh,
                               frag["binary_result_sentence"])
    combined_after = new_main + new_methods + new_results
    assert combined_after.count(r"\cite{FieldWelsh2007}") == 1
    labels_before = re.findall(r"\\label\{([^}]+)\}", combined_before)
    labels_after = re.findall(r"\\label\{([^}]+)\}", combined_after)
    assert labels_before == labels_after
    for required in ("0.8297", "1.7667", "0.1131", "1.0843", "2.069", "2.056", "2.188"):
        assert required in new_results
    for body in (new_main, new_methods, new_results):
        balanced(body)
    figure_path = ROOT / f"fullwave_model_and_field_annotated_{lang}.png"
    with Image.open(figure_path) as img:
        assert img.size == (4296, 2616)
        assert abs(img.info["dpi"][0] - 600) < .1
    checks[lang] = {"replacement_anchors_unique": True, "balanced_latex_braces": True,
                    "labels_preserved": True, "existing_statistical_values_preserved": True,
                    "bootstrap_reference_count": 1, "png_pixels": [4296, 2616],
                    "new_annotations_nominal_font_pt": 9,
                    "complete_manuscript_written_or_compiled": False}
    heading = "# English copy-and-paste replacements" if lang == "en" else "# 中文对照：逐处替换内容"
    output = [heading, "", "See README.md for exact replacement locations. / 具体位置见README.md。", ""]
    for index, stem in enumerate(fragments, 1):
        output.extend([f"## {index}. {stem}", "", "```latex", frag[stem], "```", ""])
    (ROOT / f"COPY_PASTE_{lang.upper()}.md").write_text("\n".join(output), encoding="utf-8")
    if lang == "en":
        original_words = re.findall(r"\b[\w]+(?:[-'][\w]+)*\b", old_abstract.split("\n", 1)[1].split(r"\end")[0])
        replacement_body = frag["abstract"].split("\n", 1)[1].split(r"\end")[0]
        replacement_words = re.findall(r"\b[\w]+(?:[-'][\w]+)*\b", replacement_body)
        checks[lang]["abstract_word_count_regex_including_latex_tokens"] = len(replacement_words)
        checks[lang]["abstract_numeric_result_metrics"] = ["25% balanced accuracy", "10 Hz maximum target error", "26 Hz minimum bounded gap"]

after = {str(path.relative_to(REPO)).replace("\\", "/"): sha(path) for path in sources}
assert before == after
audit = {
    "scope": "Draft 18 targeted text and figure patch; originals unchanged",
    "source_sha256": before,
    "source_hashes_unchanged_after_checks": True,
    "final_test_read": False,
    "new_simulation_or_statistics": False,
    "geometry_identity": {"design": "five-level resonant encoding; four-corner compensation",
                          "alpha": .05, "physical_neck_length_mm": 9,
                          "neck_cross_section_mm": [2, 4], "side_cavity_footprint_mm": [17, 17],
                          "junction_side_mm": 36.2053299278368, "junction_height_mm": 9.2,
                          "readout_xyz_mm": [0, 0, 4.6], "field_frequency_hz": 954,
                          "active_source_state": 3, "active_port_deg": 270,
                          "corner_solids": "4 full-height Boolean subtraction regions",
                          "panel_c": "code-derived local geometry only, no new acoustic solution"},
    "four_state_primary_records": gains,
    "four_state_gain_contrast_record": contrast,
    "four_state_scope": "AS01: 2 repositioning blocks per configuration; medians fixed; separate block-cluster numerator and direction-distance denominator draws; no nested curve stage",
    "two_state_scope": "whole curves drawn within N/S/NRETURN (6/6/3); no assembly-level resampling",
    "two_state_interval_archived": binary["bootstrap"]["direction_effect_rms_db_ci95"],
    "checks": checks,
    "visual_review": "English and Chinese previews inspected; callouts and colour-bar clipping corrected",
    "limitation": "Static snippet checks only. Complete manuscript pagination after application has not been tested.",
}
audit_path = ROOT / "SOURCE_AND_VALIDATION_AUDIT.json"
audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert json.loads(audit_path.read_text(encoding="utf-8"))["source_hashes_unchanged_after_checks"]
entries = [f"{sha(path)}  {path.name}" for path in sorted(ROOT.iterdir())
           if path.is_file() and path.name != "SHA256SUMS.txt"]
(ROOT / "SHA256SUMS.txt").write_text("\n".join(entries) + "\n", encoding="utf-8")
print(json.dumps({"status": "PASS", "checks": checks, "files_hashed": len(entries)}, ensure_ascii=True))

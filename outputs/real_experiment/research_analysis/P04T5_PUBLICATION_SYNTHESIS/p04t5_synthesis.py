"""Frozen P04T5 publication synthesis and P05 gate decision."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def decide_terminal_state(*, inputs_ok: bool, p04b_credible_for_u4: bool,
                          new_verifiable_model_repair: bool) -> str:
    if not inputs_ok:
        return "P04T5 BLOCKED_INPUT_INTEGRITY"
    if new_verifiable_model_repair:
        return "P04T5 AUTHORIZE_REBUILT_MODEL_CONTRACT_BEFORE_P05"
    if not p04b_credible_for_u4:
        return "P04T5 CLOSE_SCHEME_3A_WITH_PUBLISHABLE_MECHANISM_RESULT"
    return "P04T5 CLOSE_SCHEME_3A_WITH_PUBLISHABLE_MECHANISM_RESULT"


def validate_evidence_chain(rows: list[dict[str, Any]]) -> None:
    required = {"P04T1V", "P04T2", "P04T3", "P04T4_REV01"}
    present = {str(row.get("stage")) for row in rows}
    if not required.issubset(present):
        raise ValueError(f"missing frozen evidence stages: {sorted(required - present)}")
    for row in rows:
        if not row.get("supports") or not row.get("does_not_support"):
            raise ValueError("every evidence row requires positive and negative boundaries")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_manifest(manifest: Path, base: Path, root_relative: bool) -> dict[str, Any]:
    records = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        name = name.lstrip(" *")
        target = (ROOT / name) if root_relative else (base / name)
        actual = _sha256(target)
        records.append({"path": name, "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    return {"manifest": str(manifest.relative_to(ROOT)), "passed": sum(row["pass"] for row in records), "total": len(records), "all_pass": all(row["pass"] for row in records)}


def _write_csv(name: str, rows: list[dict[str, Any]]) -> None:
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(name: str, value: dict[str, Any]) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _make_figure(classification: str) -> None:
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    ax.set_xlim(0, 13.5); ax.set_ylim(0, 7.2); ax.axis("off")
    ax.text(6.75, 6.82, "Scheme 3A bounded mechanism evidence and P05 gate", ha="center", fontsize=17, weight="bold")

    top = [
        (0.35, "P04T1V\nSIMULATION", "Volume dose order\nand local landmarks", "#dbeafe", "#2563eb"),
        (3.0, "P04T2\nREAL EXPERIMENT", "BASE < I75 < I50P\n1.480 / 2.141 dB", "#dcfce7", "#16a34a"),
        (5.65, "P04T3\nRECONCILIATION", "Dose direction agrees;\nlocal shape mismatches", "#fef3c7", "#d97706"),
        (8.3, "P04T4 REV01\nRETURN CONTROL", "2.367 dB effect; 2.174× drift\nρ = 0.906 / cross-batch 0.786", "#dcfce7", "#16a34a"),
        (10.95, "P04T5\nSYNTHESIS", "Publish bounded mechanism;\nclose old route", "#ede9fe", "#7c3aed"),
    ]
    for idx, (x, title, body, fill, edge) in enumerate(top):
        box = FancyBboxPatch((x, 3.95), 2.2, 1.8, boxstyle="round,pad=0.04,rounding_size=0.08", facecolor=fill, edgecolor=edge, linewidth=1.8)
        ax.add_patch(box); ax.text(x + 1.1, 5.32, title, ha="center", va="center", weight="bold", color=edge, fontsize=10)
        ax.text(x + 1.1, 4.48, body, ha="center", va="center", fontsize=9.2)
        if idx < len(top) - 1:
            ax.annotate("", xy=(top[idx + 1][0] - .08, 4.85), xytext=(x + 2.28, 4.85), arrowprops=dict(arrowstyle="->", lw=1.7, color="#475569"))

    ax.text(.45, 3.25, "U4 MODEL-CREDIBILITY GATE", color="#991b1b", fontsize=11, weight="bold")
    lower = [
        (1.0, "P04B-N", "MODEL NOT CREDIBLE\nFOR U4"),
        (4.4, "P04C", "Topology hybridization\ndiagnosed; gate not repaired"),
        (7.8, "P04T3", "Precise physical-spectrum\nprediction not supported"),
        (11.15, "P05", "BLOCKED\n0 new solves"),
    ]
    for idx, (x, title, body) in enumerate(lower):
        box = FancyBboxPatch((x, 1.2), 2.0, 1.35, boxstyle="round,pad=0.04", facecolor="#fee2e2", edgecolor="#dc2626", linewidth=1.6)
        ax.add_patch(box); ax.text(x + 1, 2.18, title, ha="center", weight="bold", color="#991b1b")
        ax.text(x + 1, 1.62, body, ha="center", va="center", fontsize=9)
        if idx < len(lower) - 1:
            ax.annotate("", xy=(lower[idx + 1][0] - .08, 1.88), xytext=(x + 2.08, 1.88), arrowprops=dict(arrowstyle="->", lw=1.7, color="#b91c1c"))

    ax.text(6.75, .55, classification, ha="center", fontsize=12, weight="bold", color="#581c87")
    fig.tight_layout()
    fig.savefig(OUT / "mechanism_evidence_chain.png", dpi=220, bbox_inches="tight")
    fig.savefig(OUT / "mechanism_evidence_chain.svg", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    manifests = [
        _verify_manifest(ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION/SHA256SUMS", ROOT, True),
        _verify_manifest(ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC/SHA256SUMS", ROOT, True),
        _verify_manifest(ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/SHA256SUMS.txt", ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE", False),
        _verify_manifest(ROOT / "outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/SHA256SUMS.txt", ROOT / "outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS", False),
        _verify_manifest(ROOT / "outputs/real_experiment/research_analysis/P04T3_EXPERIMENT_SIMULATION_RECONCILIATION/SHA256SUMS.txt", ROOT / "outputs/real_experiment/research_analysis/P04T3_EXPERIMENT_SIMULATION_RECONCILIATION", False),
        _verify_manifest(ROOT / "outputs/real_experiment/research_analysis/P04T4_RETURN_CONTROL_CONFIRMATION_REV01/SHA256SUMS.txt", ROOT / "outputs/real_experiment/research_analysis/P04T4_RETURN_CONTROL_CONFIRMATION_REV01", False),
    ]
    inputs_ok = all(item["all_pass"] for item in manifests)
    classification = decide_terminal_state(inputs_ok=inputs_ok, p04b_credible_for_u4=False, new_verifiable_model_repair=False)

    evidence = [
        {"stage": "P04B-N", "evidence_type": "simulation", "frozen_status": "MODEL NOT CREDIBLE FOR U4", "key_quantitative_evidence": "HR02-HR05 boundary maxima; HR03/HR04 stable-module centers non-identifiable; HR04 mesh center undefined", "supports": "The nominal single-module model lacks the frozen credibility required for full-U4 prediction.", "does_not_support": "Entry to old P05 or any precise U4 prediction.", "publication_role": "model limitation and hard P05 prerequisite"},
        {"stage": "P04C", "evidence_type": "simulation_saved_solution_diagnostic", "frozen_status": "TOPOLOGY HYBRIDIZATION SUPPORTED", "key_quantitative_evidence": "HR03 isolated 1904.19 Hz to integrated ~1650.40 Hz; -0.209 octave; shared compressed branches", "supports": "Connection to fixed passages/shared chamber is associated with modal reorganization and hybridized shared branches.", "does_not_support": "A repaired U4 model, direction recognition, or unique component-level causality.", "publication_role": "mechanism diagnosis"},
        {"stage": "P04T1V", "evidence_type": "simulation", "frozen_status": "PASS FOR PRINT AND P04T2", "key_quantitative_evidence": "branch 1651.323 -> 1679.908 -> 1729.028 Hz; I75 landmarks -2.443/+2.669 dB; I50P -6.524/+6.326 dB", "supports": "Reducing central-cavity air volume produces an ordered control trend in the bounded model.", "does_not_support": "Physical local-peak accuracy, full-U4 credibility, or direction performance.", "publication_role": "prospective intervention prediction"},
        {"stage": "P04T2", "evidence_type": "real_experiment", "frozen_status": "USEFUL BOUNDED MECHANISM EVIDENCE WITH LIMITS", "key_quantitative_evidence": "BASE batch shape RMS 0.4279 dB; I75 1.4799 dB (3.46x); I50P 2.1407 dB (5.00x); I75/I50P shape r=0.720", "supports": "BASE<I75<I50P dose-ordered broadband redistribution from the central-cavity volume intervention.", "does_not_support": "Return control, independent reassembly, precise landmarks, direction identification, or component contribution fraction.", "publication_role": "real pilot dose response"},
        {"stage": "P04T3", "evidence_type": "simulation_real_experiment_reconciliation", "frozen_status": "REAL VOLUME EFFECT MODEL LOCALIZATION MISMATCH", "key_quantitative_evidence": "1400-2100 Hz demeaned r: I75 -0.429, I50P +0.118 selected-4; all below 0.50; I75 local gate failed", "supports": "The simulated and physical systems agree on the control direction but not on local spectral localization/amplitude.", "does_not_support": "Precise COMSOL validation or a retention-ratio spectral barcode.", "publication_role": "bounded model-to-experiment audit"},
        {"stage": "P04T4_REV01", "evidence_type": "real_experiment", "frozen_status": "RETURN CONTROL SUPPORTS EFFECT WITH ASSEMBLY SENSITIVITY", "key_quantitative_evidence": "I50P bracketed shape RMS 2.3672 dB [2.3409,2.4127]; return drift 1.0887 dB; ratio 2.174 [1.997,2.286]; pre/post r=0.906; cross-batch r=0.786", "supports": "I50P exceeds return drift, remains stable across bracketing BASE definitions, and replicates across P04T2/P04T4 batches.", "does_not_support": "Full reversibility, isolation of assembly from time/environment, independent-day generalization, or exact landmarks.", "publication_role": "return-control and cross-batch confirmation"},
    ]
    validate_evidence_chain(evidence)
    _write_csv("evidence_chain.csv", evidence)

    claims = [
        {"claim_id": "C1", "boundary": "SUPPORTED", "claim": "中央共享腔有效空气体积是可操作的形态学频谱控制参数。", "evidence": "P04T1V+P04T2+P04T4_REV01", "allowed_wording": "减小有效空气体积引发剂量有序的宽频谱重分配。", "prohibited_upgrade": "不得称为方向识别或精确模型验证。"},
        {"claim_id": "C2", "boundary": "SUPPORTED", "claim": "I50P真实效应大于本批回程漂移。", "evidence": "2.3672 dB vs 1.0887 dB; ratio 2.174; P(effect>return)=1.000", "allowed_wording": "效应在前后BASE定义下保持并超过观测漂移。", "prohibited_upgrade": "不得称为完全可逆或无装配敏感性。"},
        {"claim_id": "C3", "boundary": "SUPPORTED_WITH_LIMITS", "claim": "主要I50P谱形跨P04T2/P04T4批次复现。", "evidence": "cross-batch Pearson/cosine 0.786", "allowed_wording": "跨两个采集批次的同类谱形复现。", "prohibited_upgrade": "不得推广到跨日期、多操作者或量产装置。"},
        {"claim_id": "C4", "boundary": "SUPPORTED", "claim": "装配/时间/环境共同形成重要基线变量。", "evidence": "BASE return shape RMS 1.0887 dB exceeds 0.6168 dB within-condition ceiling", "allowed_wording": "基线非平稳性不可忽略，来源在当前协议中不可分离。", "prohibited_upgrade": "不得唯一归因于装配。"},
        {"claim_id": "C5", "boundary": "NOT_SUPPORTED", "claim": "当前简化COMSOL可精确预测实体局部峰谷。", "evidence": "P04B-N failed; P04T3 all shape similarities <0.50; frozen local gates failed", "allowed_wording": "模型只能预测控制趋势。", "prohibited_upgrade": "不得宣称P04T1V已构成实体精确验证。"},
        {"claim_id": "C6", "boundary": "NOT_SUPPORTED", "claim": "装置已实现可靠方向识别或U4HR优于U4SYM。", "evidence": "outside P04 intervention scope; prior frozen direction-code gate failed", "allowed_wording": "P04结果是机制证据。", "prohibited_upgrade": "不得报告方向识别成功、H1确认或分类能力。"},
        {"claim_id": "C7", "boundary": "NOT_SUPPORTED", "claim": "可以估计单模块独立因果贡献率。", "evidence": "shared topology and overlapping observables", "allowed_wording": "报告共享腔体积干预的整体效应。", "prohibited_upgrade": "不得给出单部件贡献百分比。"},
    ]
    _write_csv("claim_boundary.csv", claims)

    decision = {
        "schema_version": "p04t5_publication_synthesis_v1",
        "terminal_state": classification,
        "authority_hash_audit": manifests,
        "p04t2_classification_location": "analysis_summary.json (this accepted stage has no separate scientific_classification.json)",
        "publication_mechanism_statement": "中央共享腔有效空气体积是一个可操作的形态学频谱控制参数；减小体积会引发剂量有序、跨批次可重复的宽频谱重分配。装配状态也是重要变量，而当前简化COMSOL模型只能预测控制趋势，不能精确预测实体局部峰谷。",
        "old_p05_prerequisite": "P04B must establish model credibility for U4",
        "p04b_status": "P04B-N MODEL NOT CREDIBLE FOR U4",
        "new_verifiable_model_repair_basis_present": False,
        "why_rebuild_not_authorized": "P04C diagnoses topology hybridization without repairing the gate; P04T1V is a bounded insert trend model; P04T3 confirms physical localization mismatch.",
        "p05_gate": "BLOCKED",
        "p05_to_p10_old_route": "BLOCKED_AND_CLOSED_UNDER_CURRENT_CONTRACT",
        "p05_started": False,
        "new_comsol_solves": 0,
        "new_data_analyzed": False,
        "new_frequency_selection": False,
        "parameter_fitting": False,
        "final_test_read": False,
    }
    _write_json("stage_decision.json", decision)

    summary = f"""# P04T5 paper result summary

终态：`{classification}`

## 最强可发表机制陈述

中央共享腔有效空气体积是一个可操作的形态学频谱控制参数；减小体积会引发剂量有序、跨批次可重复的宽频谱重分配。装配状态也是重要变量，而当前简化COMSOL模型只能预测控制趋势，不能精确预测实体局部峰谷。

## 关键证据

- P04T2：BASE批间去均值RMS 0.4279 dB；I75 1.4799 dB、I50P 2.1407 dB，分别为3.46倍和5.00倍；I75/I50P效应谱相关0.720。
- P04T3：共同频带demeaned相关仅I75 -0.429、I50P +0.118（selected-4），精确局部模型门禁失败。
- P04T4 REV01：I50P bracketed效应2.3672 dB，回程漂移1.0887 dB，效应/漂移比2.174（95% CI 1.997–2.286）；前后BASE效应相关0.906，跨P04T2/P04T4批次相关0.786。

## 论文边界与P05决策

这些结果支持体积控制、跨批次宽频谱复现和装配/基线敏感性；不支持方向识别成功、精确COMSOL实体预测、完全可逆性或单部件贡献率。旧P05要求P04B先证明模型对U4可信；该前提仍失败，且没有新的可验证模型修复依据。因此旧P05–P10保持blocked，本轮没有启动P05。

`final_test_read=false`；新COMSOL求解次数0。
"""
    (OUT / "paper_result_summary.md").write_text(summary, encoding="utf-8")
    _make_figure(classification)

    generated = sorted(path for path in OUT.iterdir() if path.is_file() and path.name not in {"SHA256SUMS.txt", "artifact_inventory.json"})
    inventory = {
        "schema_version": "p04t5_artifact_inventory_v1",
        "artifact_count_excluding_inventory_and_sha": len(generated),
        "artifacts": [{"path": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in generated],
        "final_test_read": False,
        "new_comsol_solves": 0,
    }
    _write_json("artifact_inventory.json", inventory)
    hashed = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt")
    (OUT / "SHA256SUMS.txt").write_text("".join(f"{_sha256(path)}  {path.name}\n" for path in hashed), encoding="utf-8")


if __name__ == "__main__":
    main()

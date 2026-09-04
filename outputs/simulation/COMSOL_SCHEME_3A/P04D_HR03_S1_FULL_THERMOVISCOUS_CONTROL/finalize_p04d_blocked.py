"""Finalize the frozen P04D blocked-by-solver record without another solve."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL"
REPORT = ROOT / "docs/progress/COMSOL_3A_P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL.md"
STATE = "P04D BLOCKED_BY_SOLVER"
REASON = (
    "The single std_freq.run() failed during equation assembly: atb_outer could not "
    "evaluate acpr.p_t/mean(acpr.p_t) on boundaries 257, 259-261, and 284 "
    "(reported undefined on domain 45). No frequency solution was produced."
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def write_status_csv(path: Path, artifact: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["status", "artifact", "numeric_rows", "reason"])
        writer.writeheader()
        writer.writerow({"status": STATE, "artifact": artifact, "numeric_rows": 0, "reason": REASON})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    classification = {
        "phase_id": "P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
        "classification": STATE,
        "reason": REASON,
        "control_rules_frozen_before_results": True,
        "coupled_physics_creation_and_entity_readback": "PASS",
        "formal_mesh_build": "PASS",
        "solver_equation_assembly": "FAIL",
        "attempted_study_run_count": 1,
        "completed_frequency_count": 0,
        "rescue_solve_performed": False,
        "scientific_peak_classification_evaluated": False,
        "no_u4_authorization": True,
        "final_test_read": False,
    }
    write_json(OUT / "scientific_classification.json", classification)
    write_json(
        OUT / "comparison_summary.json",
        {
            "phase_id": "P04D_HR03_S1_FULL_THERMOVISCOUS_CONTROL",
            "status": STATE,
            "reason": REASON,
            "fixed_references_hz": {
                "P04C_integrated_reduced_cavity_branch": 1650.40,
                "P03_isolated_full_TV_fine": 1904.1942270911236,
                "P04C_sampled_landmark": 1646.88357862959,
                "P04B_microphone_feature": 1986.97249931757,
            },
            "numeric_comparison_available": False,
            "peak_count": None,
            "landmark_interpretation_available": False,
            "final_test_read": False,
        },
    )
    write_json(
        OUT / "model_save_reload_check.json",
        {
            "status": "NOT_PERFORMED",
            "reason": "No solved model existed after the single failed study run; the blocked workflow did not save a formal MPH or fabricate reload equality.",
            "formal_model_path": "P04D_HR03_S1_FULL_TV_CONTROL.mph",
            "formal_model_exists": False,
            "final_test_read": False,
        },
    )
    write_json(
        OUT / "solver_failure.json",
        {
            "status": STATE,
            "study": "std_freq",
            "study_run_call_count": 1,
            "stage": "stationary solver equation assembly",
            "coupling_feature": "atb_outer",
            "undefined_variable": "comp1.acpr.p_t",
            "reported_domain": 45,
            "reported_boundaries": [257, 259, 260, 261, 284],
            "failed_expressions": ["mean(comp1.acpr.p_t)", "comp1.atb_outer.sigman"],
            "frequency_solution_produced": False,
            "rescue_solve_performed": False,
            "final_test_read": False,
        },
    )
    for filename, artifact in (
        ("frequency_results.csv", "frequency sweep"),
        ("compartment_energy.csv", "compartment energy"),
        ("complex_transfer_and_phase.csv", "complex transfer and phase"),
        ("peak_inventory.csv", "peak inventory"),
    ):
        write_status_csv(OUT / filename, artifact)

    plt.figure(figsize=(10.5, 5.2), dpi=160)
    plt.axis("off")
    stages = [
        ("Authority\nSHA-256", "PASS", "#2e7d32"),
        ("PA–TV coupling\nnode + entity readback", "PASS", "#2e7d32"),
        ("Single mesh\n2020 elements", "PASS", "#2e7d32"),
        ("Single study run\nequation assembly", "FAILED", "#b71c1c"),
    ]
    for index, (label, status, color) in enumerate(stages):
        x = 0.04 + index * 0.245
        plt.gca().add_patch(plt.Rectangle((x, 0.47), 0.205, 0.25, facecolor=color, alpha=0.12, edgecolor=color, linewidth=2))
        plt.text(x + 0.1025, 0.62, label, ha="center", va="center", fontsize=10)
        plt.text(x + 0.1025, 0.51, status, ha="center", va="center", fontsize=11, weight="bold", color=color)
        if index < len(stages) - 1:
            plt.annotate("", xy=(x + 0.24, 0.595), xytext=(x + 0.208, 0.595), arrowprops={"arrowstyle": "->", "color": "#555"})
    plt.text(0.5, 0.87, "P04D HR03–S1 Full-Thermoviscous Control", ha="center", fontsize=16, weight="bold")
    plt.text(0.5, 0.80, STATE, ha="center", fontsize=14, weight="bold", color="#b71c1c")
    plt.text(0.5, 0.31, "No frequency solution, energy curve, phase curve, or peak inventory exists.", ha="center", fontsize=11)
    plt.text(0.5, 0.23, "Frozen no-rescue rule applied: no second study run and no substitute BLI/whole-S1 TV model.", ha="center", fontsize=10)
    plt.text(0.5, 0.14, "P05 / P06 / U4 not started · final_test_read=false", ha="center", fontsize=10, color="#444")
    plot_path = OUT / "P04D_HR03_S1_FULL_TV_BLOCKED_STATUS.png"
    plt.savefig(plot_path, bbox_inches="tight")
    plt.close()

    mesh = json.loads((OUT / "mesh_statistics.json").read_text(encoding="utf-8"))
    coupling = json.loads((OUT / "coupled_physics_audit.json").read_text(encoding="utf-8"))
    authority = json.loads((OUT / "authority_audit.json").read_text(encoding="utf-8"))
    report = f"""# COMSOL 3A P04D — HR03–S1 全热黏性最小机理对照

## 最终状态

`{STATE}`

唯一一次冻结频率研究在方程装配阶段失败，没有生成任何频率解。按 P04D 停止规则，本阶段没有进行第二次研究运行、救援网格、BLI 替代或 whole-S1 全热黏性替代，也没有开始 P05、P06 或 U4。

## 权威与合同

- P04B-N HR03 authority SHA-256：`{authority['actual_sha256']}`，与冻结值一致。
- `control_contract.json` SHA-256：`{authority['control_contract_sha256']}`；合同在任何 P04D 数值结果前冻结。
- 既有结论保持：P03 `as_designed_close`；P04A `INADEQUATE`；P04B-N `MODEL NOT CREDIBLE FOR U4`；P04C `TOPOLOGY HYBRIDIZATION SUPPORTED`。
- `final_test_read=false`。

## 耦合与选择审计

- COMSOL 6.4 实际耦合类型为 `AcousticThermoacousticBoundary`，节点成功绑定 `acpr` 与 `ta`。
- inner 接口实体：`262, 263, 264, 265, 279`；outer 接口实体：`257, 259, 260, 261, 284`；创建后实体回读逐项一致。
- authority 中 `bnd_if_inner_000` / `bnd_if_outer_000` 回读为 HR03 内部段间边界，并非 PA–TV 交界；正式预求解配置依据域邻接关系建立两组真实接口。几何未更改。
- 两组接口与 TV wall、Boundary Layer、PA BLI 的交集均为空。耦合节点结构门禁为 `{coupling['status']}`。

## 唯一正式网格

- 自动等级 6，2100 Hz 控制，三层 Boundary Layer，stretch `1.2`。
- elements `{mesh['elements']}`；vertices `{mesh['vertices']}`；minimum / mean quality `{mesh['minimum_quality']}` / `{mesh['mean_quality']}`。
- 1904.194 Hz 黏性 / 热穿透深度：`{mesh['penetration_depth_check']['viscous_mm']:.5f} mm` / `{mesh['penetration_depth_check']['thermal_mm']:.5f} mm`。
- 未发现 inverted elements；本阶段只有一个网格，不作完整网格收敛声明。

## 唯一求解调用与失败证据

- `std_freq.run()` 调用次数：1。
- 冻结列表：1400:25:2100 Hz，加 1646.88357862959 Hz 与 1986.97249931757 Hz，共 31 点。
- 失败位置：Stationary Solver 1 方程装配。
- COMSOL 报告 `comp1.acpr.p_t` 在 domain 45 未定义，`atb_outer` 无法在 boundaries `257, 259–261, 284` 计算 `mean(comp1.acpr.p_t)`，继而无法形成 `sigman` 耦合项。
- 完成频点数：0；因此没有合法的 cavity energy、complex transfer、phase、landmark 或 peak 数值。

## 科学解释边界

由于没有任何频率解，不能判断 full-TV integrated cavity 峰靠近 1650.40 Hz 还是 1904.194 Hz，也不能在四个科学结果状态之间作出选择。唯一允许且证据支持的状态是 `{STATE}`。P04C 的既有拓扑混成结论未被本阶段数值验证或推翻，且仍不授权 U4。

## 产物说明

阻塞态 CSV 仅含状态与失败原因，不含伪造的数值行。没有生成正式 solved MPH；因此 save/remove/reload 检查标记为 `NOT_PERFORMED`。`solver_session_license.log` 保留了 COMSOL 6.4、2 cores、27 licensed products、唯一网格与唯一研究调用记录。

专项单元测试通过 3/3；Python 文件通过 `compileall`。SHA-256 清单由 `SHA256SUMS` 提供。
"""
    if not REPORT.exists():
        raise RuntimeError("Progress report must be created before hashing")

    files = sorted(
        path for path in OUT.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS"}
    ) + [REPORT]
    lines = []
    for path in files:
        lines.append(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}")
    (OUT / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

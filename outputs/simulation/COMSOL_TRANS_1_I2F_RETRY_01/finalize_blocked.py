"""Finalize the bounded solver-blocked TRANS-1 RETRY_01 attempt."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_01"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_1_I2F_RETRY_01.md"
R0 = ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02"
CLASSIFICATION = "TRANS1_RETRY_01_BLOCKED_BY_SOLVER"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_blocked_figure(stem: str, title: str, detail: str, kind: str) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    if kind == "mesh":
        ax.bar([0], [64406], width=0.55, color="#4c78a8")
        ax.text(0, 64406, "64,406", ha="center", va="bottom")
        ax.text(1, 32000, "N/A\nnot persisted", ha="center", va="center", color="#b22222")
        ax.set_xticks([0, 1], ["RETRY_02 coarse", "RETRY_01 fine"])
        ax.set_ylabel("Elements")
        ax.set_xlim(-0.6, 1.6)
        ax.set_ylim(0, 72000)
    elif kind == "matrix":
        image = ax.imshow(np.zeros((2, 2)), vmin=0, vmax=1, cmap="Greys", alpha=0.25)
        del image
        ax.set_xticks([0, 1], ["HR03 window", "HR07 window"])
        ax.set_yticks([0, 1], ["N excitation", "S excitation"])
        for row in range(2):
            for col in range(2):
                ax.text(col, row, "N/A", ha="center", va="center", color="#b22222", fontsize=14)
    elif kind == "gates":
        labels = ["fine smoke", "coarse/fine 256", "six formal runs", "science gates"]
        ax.barh(labels, [0, 0, 0, 0], color="#b22222")
        for index, label in enumerate(["BLOCKED", "NOT RUN", "0/6", "NOT EVALUATED"]):
            ax.text(0.02, index, label, va="center", color="#b22222", fontsize=12)
        ax.set_xlim(0, 1)
        ax.set_xlabel("Completion")
    else:
        ax.set_xscale("log")
        ax.set_xlim(200, 8000)
        ax.set_ylim(-1, 1)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Not computed")
        ax.grid(True, alpha=0.25)
        ax.text(0.5, 0.52, "NOT COMPUTED", transform=ax.transAxes,
                ha="center", va="center", fontsize=18, color="#b22222")
    ax.set_title(title)
    ax.text(0.5, -0.18, detail, transform=ax.transAxes, ha="center", va="top",
            fontsize=9, wrap=True, color="#555555")
    for suffix in ("png", "svg"):
        fig.savefig(OUT / f"{stem}.{suffix}", dpi=180 if suffix == "png" else None)
    plt.close(fig)


def main() -> None:
    now = datetime.now().astimezone().isoformat()
    failure = read_json(OUT / "solver_failure.json")
    state = read_json(OUT / "execution_state.json")
    coarse_mesh = read_json(R0 / "mesh_statistics.json")
    retry02_class = read_json(R0 / "scientific_classification.json")

    contract = {
        "schema_version": "comsol_trans1_i2f_retry01_contract_v1.0.0",
        "phase": "TRANS-1 RETRY_01", "created_at": now,
        "authority_runner": "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02/run_trans0_retry02.py",
        "frequency_grid": "200*2^(n/48), n=0..255", "frequency_count": 256,
        "primary_band_hz": [1000, 5000], "secondary_bands_hz": [[200, 1000], [5000, 8000]],
        "targets_hz": {"HR03": 1850, "HR07": 3800}, "window_half_width_octave": 1/6,
        "models": ["ISO-CODED", "ISO-SYM", "MIX-CONTROL"], "excitations": ["N", "S"],
        "numerical_gates": {"peak_center_relative_change_strict_less_than": 0.01,
                            "fixed_window_contrast_change_db_strict_less_than": 0.5,
                            "fine_to_coarse_hmax_ratio_maximum": 0.75},
        "scientific_gates": {"unique_expected_top1": "2/2", "diagonal_advantage_db_minimum": 3.0,
                             "normalized_off_diagonal_energy_maximum": 0.5,
                             "peak_drift_octave_strict_less_than": 1/12,
                             "iso_sym_ns_difference_db_maximum": 0.2},
        "final_test_read": False, "external_field_started": False, "thresholds_changed": False,
    }
    write_json(OUT / "simulation_contract.json", contract)

    configuration = {
        "COMSOL_version": "6.4", "cores": 4, "server_port": 63197,
        "fresh_session_initial_model_count": 0, "air": {"c_m_per_s": 343.0, "rho_kg_per_m3": 1.2041},
        "active_excitation": "1 Pa complex pressure", "passive_port": "PlaneWaveRadiation",
        "walls": "Sound Hard on all exterior boundaries except ports and microphone",
        "microphone": "complex area-average, diameter 8.8 mm, z=1.0 mm",
        "coarse": {**coarse_mesh, "source": "accepted TRANS-0 RETRY_02"},
        "fine_requested": {"automatic_level": 7, "control_frequency_hz": 12000.0,
                           "global_hmax_ratio_to_coarse_reference": 2/3,
                           "critical_hmax_m": 0.0028/6,
                           "critical_neck_elements_across_by_hmax": 6.0},
        "fine_actual_mesh_statistics": None,
        "fine_actual_mesh_statistics_reason": "not persisted before post-solve field extraction failure",
        "study_path": "model.java.study('std_freq').run()", "final_test_read": False,
    }
    write_json(OUT / "model_configuration.json", configuration)

    geometry = {
        "authority": "TRANS-0 RETRY_02", "authority_status": retry02_class["classification"],
        "authority_manifest_verified_this_run": True,
        "authority_geometry_selection_audit_sha256": sha256(R0 / "geometry_selection_audit.json"),
        "preserved_gates": {"quickz": True, "getAdj_2_3": True, "ports_inside": True,
                            "one_boundary_per_port": True, "ports_excluded_from_walls": True,
                            "feature_derived_cavity_unions": True, "cavities_nonempty_disjoint_plenum_excluded": True},
        "fine_smoke_model_build_reached": True, "fine_mesh_run_returned_without_exception": True,
        "post_solve_field_extraction_pass": False,
        "note": "The model was removed by fail-safe cleanup; no entity IDs are invented for this failed attempt.",
    }
    write_json(OUT / "geometry_and_selection_audit.json", geometry)

    mesh_json = {
        "warning": "LOW_MESH_QUALITY_WARNING", "coarse": coarse_mesh,
        "fine_configuration": configuration["fine_requested"], "fine_actual_statistics": None,
        "fine_smoke_study_run_returned": True, "field_extraction_pass": False,
        "numerical_convergence_reached": False,
    }
    write_json(OUT / "mesh_statistics.json", mesh_json)
    write_csv(OUT / "mesh_statistics.csv", [
        {"run": "accepted_retry02_coarse", "status": "reference", "elements": coarse_mesh["elements"],
         "vertices": coarse_mesh["vertices"], "minimum_quality": coarse_mesh["minimum_quality"],
         "mean_quality": coarse_mesh["mean_quality"], "note": "LOW_MESH_QUALITY_WARNING"},
        {"run": "retry01_fine_smoke", "status": "not_persisted", "elements": "", "vertices": "",
         "minimum_quality": "", "mean_quality": "", "note": "field extraction failed after study.run"},
    ], ["run", "status", "elements", "vertices", "minimum_quality", "mean_quality", "note"])

    blocked_row = {"status": "not_computed_blocked_by_solver", "reason": failure["error"]}
    write_csv(OUT / "complex_transfer.csv", [blocked_row], ["status", "reason"])
    write_csv(OUT / "cavity_and_plenum_participation.csv", [blocked_row], ["status", "reason"])
    write_csv(OUT / "fixed_window_matrix.csv", [blocked_row], ["status", "reason"])

    convergence = {
        "pass": False, "reached": False, "classification": CLASSIFICATION,
        "fine_smoke": {"study_run_returned_without_exception": True, "frequency_axis_length": 4,
                       "field_lengths": {"mic": 0, "e_all": 0, "e_hr03": 0, "e_south": 0, "e_plenum": 0},
                       "error": failure["error"]},
        "coarse_256_run_started": False, "fine_256_run_started": False,
        "third_mesh_attempted": False, "geometry_modified": False,
    }
    write_json(OUT / "numerical_convergence.json", convergence)
    write_json(OUT / "mph_reload_validation.json", {
        "runs": [], "all_pass": False, "not_applicable_reason": "No MPH reached save stage before solver/result extraction block"
    })
    classification = {
        "classification": CLASSIFICATION, "created_at": now,
        "technical_execution": {"fresh_session": True, "fine_smoke_model_built": True,
                                "study_run_returned_without_exception": True,
                                "field_extraction": "failed_empty_arrays", "numerical_gate_pass": False,
                                "formal_six_completed": False, "formal_solve_count": 0},
        "scientific_evaluation": {"ISO_CODED_fixed_window_gate": "not_evaluated",
                                  "ISO_SYM_control": "not_run", "MIX_CONTROL": "not_run",
                                  "evidence_supports_TRANS2": False},
        "low_mesh_quality_warning": True, "final_test_read": False,
        "trans1b_started": False, "later_stages_started": False, "print_authorized": False,
    }
    write_json(OUT / "scientific_classification.json", classification)

    log = read_json(OUT / "solver_session_license_log.json")
    log["pressure_acoustics_license_evidence"] = (
        "COMSOL accepted model.java.study('std_freq').run() without a license exception; "
        "however solved pressure/energy fields were unavailable to MPh evaluation, so no successful solve is claimed."
    )
    log["terminal_classification"] = CLASSIFICATION
    write_json(OUT / "solver_session_license_log.json", log)
    (OUT / "execution_log.txt").write_text(
        "TRANS-1 RETRY_01 bounded execution\n"
        f"created_at={now}\nclassification={CLASSIFICATION}\n"
        "RETRY_02 manifest: 17/17 matched. Fresh COMSOL 6.4 session initial model count: 0.\n"
        "Fine ISO-CODED/N smoke was the first and only attempted run. model.java.study('std_freq').run() returned.\n"
        "Frequency evaluation returned 4 points; mic/e_all/e_hr03/e_south/e_plenum each returned length 0.\n"
        "No MPH or raw complex results reached the save stage. No coarse/fine 256 comparison or formal combination was started.\n"
        "No repair, third mesh, geometry change, external field, TRANS-1B, TRANS-2/3, P05-P10, or final-test read.\n",
        encoding="utf-8",
    )

    error_detail = "fine smoke: frequency=4, all pressure/energy fields=0 length"
    save_blocked_figure("coarse_fine_mesh_comparison", "Coarse/fine mesh gate", error_detail, "mesh")
    save_blocked_figure("six_combination_transfer_spectra", "Six-combination transfer spectra", error_detail, "spectrum")
    save_blocked_figure("fixed_window_matrix", "ISO-CODED fixed-window matrix", error_detail, "matrix")
    save_blocked_figure("cavity_participation", "Cavity and plenum participation", error_detail, "spectrum")
    save_blocked_figure("model_control_comparison", "ISO-CODED / ISO-SYM / MIX-CONTROL", error_detail, "spectrum")
    save_blocked_figure("scientific_gate_summary", "Scientific gate summary", error_detail, "gates")

    report = f"""# COMSOL TRANS-1 RETRY_01 — 一体化双入口固定窗口选择性仿真

日期：{now}  
终态：`{CLASSIFICATION}`

## 首页结论

本轮技术执行在规定的第一项 fine smoke 阶段阻塞。全新 COMSOL 6.4 会话初始模型为空；模型以已验收 TRANS-0 RETRY_02 runner 为唯一几何/selection/study 权威，保留 `quickz`、`getAdj(2,3,boundary)`、单端面 `inside` ports、feature-derived cavity Unions、Java study tag 和 P04M 麦克风表述。

`model.java.study("std_freq").run()` 未抛许可证或求解异常，随后频率表达式返回严格 4 点，但麦克风复压力及 `e_all/e_hr03/e_south/e_plenum` 五个求解场均返回长度 0。因而 fine smoke 未通过，按冻结停止规则分类 `{CLASSIFICATION}`。没有进行兼容修复、第二次 smoke、第三网格或几何修改。

`LOW_MESH_QUALITY_WARNING` 继续保留：已验收 coarse minimum quality 为 `{coarse_mesh['minimum_quality']}`。本轮 fine 实际网格统计在失败前未持久化，不能据配置推定实际单元数或质量。

## 输入与 provenance

- TRANS-0 RETRY_02 的 `SHA256SUMS.txt` 17/17 重新计算匹配；状态仍为 `TRANS0_PASS_FOR_TRANS1_RETRY`。
- 原 TRANS-0、TRANS-0 RETRY_01、原 TRANS-1 的 BLOCKED provenance 均保持原位，未覆盖或重新分类。
- 当前分支与既有脏工作树被保留；未清理、重置、提交或发布。

## 实际执行路径

1. 全新 COMSOL 6.4、4 核会话，端口 `63197`，初始模型数 0。
2. 仅建立 `ISO-CODED / N / fine smoke`，频率 `[1000,1850,3800,5000] Hz`。
3. fine 配置：全局波长 hmax 比 coarse reference 为 `2/3`；关键颈部/腔体 `hmax=0.4666667 mm`。
4. Java study tag `std_freq` 与 feature `freq` 预检查由 runner 强制执行；study run 返回。
5. 结果提取失败：`frequency=4`，`mic/e_all/e_hr03/e_south/e_plenum=0/0/0/0/0`。
6. fail-safe 清理移除模型并断开会话；没有 MPH 达到保存阶段。

完整原始异常与 traceback 保存在 `solver_failure.json`，没有把空数组转换成零值、模拟值或图形曲线。

## 数值与科学门禁

- coarse/fine 256 点比较：未开始；峰中心 `<1%`、固定窗 `<0.5 dB` 和复数传递收敛均未评估。
- 六组合：`0/6` 完成。
- ISO-CODED 2×2 固定窗口矩阵、top-1、diagonal advantage、off-diagonal energy 与峰漂移：未评估。
- ISO-SYM 与 MIX-CONTROL：未运行，不能提供正面或负面对照。
- 当前没有新的声学科学结果，不能声称选择性得到支持、部分支持或否定。
- 当前证据不值得进入 TRANS-2；首先需要用户另行决定是否授权新的、独立诊断阶段。本轮不会自动 RETRY_02。

## 产物说明

由于无求解场，`complex_transfer.csv`、`cavity_and_plenum_participation.csv` 与 `fixed_window_matrix.csv` 只包含明确的 blocked 状态行。六组要求图均为非空诊断图，明确标注 `NOT COMPUTED/BLOCKED`；它们不是数据图。`mph_reload_validation.json` 记录没有 MPH 到达保存/重载阶段。

## 范围边界

未读取 final-test（`final_test_read=false`）；未修改 STL、打印包、冻结设计、实验数据、MPh 安装包或 COMSOL MCP 源码；未授权打印；未运行外场、房间模型、分类器、TRANS-1B、TRANS-2、TRANS-3 或旧 P05–P10；未 commit、push、tag 或 release。
"""
    REPORT.write_text(report, encoding="utf-8")

    inventory_paths = [path for path in sorted(OUT.iterdir())
                       if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"}
                       and path.suffix != ".pyc"] + [REPORT]
    write_json(OUT / "artifact_inventory.json", {
        "classification": CLASSIFICATION, "created_at": now,
        "artifacts": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                       "sha256": sha256(path)} for path in inventory_paths],
    })
    manifest_paths = [path for path in sorted(OUT.iterdir())
                      if path.is_file() and path.name != "SHA256SUMS.txt" and path.suffix != ".pyc"] + [REPORT]
    (OUT / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in manifest_paths),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

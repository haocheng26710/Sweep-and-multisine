from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_1_I2F_RETRY_03.md"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows, fields) -> None:
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


def verify_manifest(path: Path) -> dict:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = ROOT / relative.strip()
        actual = sha256(target) if target.is_file() else None
        rows.append({"path": relative.strip(), "expected": expected, "actual": actual,
                     "match": actual == expected})
    return {"manifest": path.relative_to(ROOT).as_posix(), "entries": len(rows),
            "all_match": all(row["match"] for row in rows), "rows": rows}


def main() -> None:
    feedback = read_json(OUT / "existing_mph_node_feedback.json")
    failure = read_json(OUT / "retry03_failure.json")
    coarse = read_json(OUT / "run_SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.json")
    with np.load(OUT / "raw_SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.npz") as data:
        values = {key: np.asarray(data[key]) for key in data.files}

    smoke_rows = []
    energy_rows = []
    for index, frequency in enumerate(values["frequency"]):
        pressure = values["mic"][index]
        smoke_rows.append({"grid_index": index, "frequency_hz": f"{frequency:.15g}",
                           "mic_real_pa": f"{pressure.real:.17g}",
                           "mic_imag_pa": f"{pressure.imag:.17g}",
                           "mic_magnitude_pa": f"{abs(pressure):.17g}"})
        energy_rows.append({"grid_index": index, "frequency_hz": f"{frequency:.15g}",
                            "e_all_j": f"{values['e_all'][index]:.17g}",
                            "e_hr03_j": f"{values['e_hr03'][index]:.17g}",
                            "e_south_j": f"{values['e_south'][index]:.17g}",
                            "e_plenum_j": f"{values['e_plenum'][index]:.17g}"})
    write_csv(OUT / "sparse_smoke_results.csv", smoke_rows,
              ["grid_index", "frequency_hz", "mic_real_pa", "mic_imag_pa", "mic_magnitude_pa"])
    write_csv(OUT / "cavity_energy_smoke.csv", energy_rows,
              ["grid_index", "frequency_hz", "e_all_j", "e_hr03_j", "e_south_j", "e_plenum_j"])

    provenance = {
        "trans0_retry02": verify_manifest(ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02/SHA256SUMS.txt"),
        "trans1_retry01": verify_manifest(ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_01/SHA256SUMS.txt"),
        "trans1_retry02": verify_manifest(ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_02/SHA256SUMS.txt"),
    }
    if not all(item["all_match"] for item in provenance.values()):
        raise RuntimeError("An authority manifest no longer matches")
    write_json(OUT / "provenance_hash_verification.json", provenance)

    write_json(OUT / "study_solution_dataset_audit.json", {
        "existing_mph_feedback": feedback,
        "fresh_fine_smoke": {
            "study_run_returned": True,
            "valid_solution_and_bound_dataset_prerequisites_passed_by_control_flow": True,
            "dataset_node_resolution_fix_used": True,
            "field_extraction_complete": False,
            "first_failing_field": "mic",
            "error": failure["error"],
            "detailed_field_lengths_not_persisted_before_bounded_stop": True,
        },
        "interpretation": "Java-tag-to-Node compatibility was fixed; the fresh fine solution still did not expose a four-value microphone field through the accepted extraction path.",
        "final_test_read": False,
    })
    write_json(OUT / "mesh_statistics.json", {
        "warning": "LOW_MESH_QUALITY_WARNING",
        "coarse_control": coarse["mesh"],
        "fine_configuration": {"control_frequency_hz": 12000.0,
                               "critical_hmax_m": 0.0028 / 6.0,
                               "study_created_after_complete_mesh": True},
        "fine_actual_statistics": "not persisted before the bounded extraction stop",
        "formal_256_mesh_gate": "not_started",
    })
    write_json(OUT / "numerical_convergence.json", {
        "status": "not_started",
        "reason": "fine four-point microphone field length invalid after successful Node resolution",
        "peak_center_change_lt_1pct": "not_evaluated",
        "fixed_window_change_lt_0p5_db": "not_evaluated",
        "six_combinations_completed": 0,
    })
    write_json(OUT / "simulation_contract.json", {
        "phase": "TRANS-1 RETRY_03",
        "repair_scope": "MPh Java-tag-to-dataset-Node resolution only",
        "existing_mph_feedback_required": True,
        "frequency_grid": "200*2^(n/48), n=0..255",
        "smoke_frequencies_hz": [1000, 1850, 3800, 5000],
        "geometry_modified": False,
        "mesh_rule_modified": False,
        "thresholds_modified": False,
        "MPh_installation_modified": False,
        "retry04_allowed": False,
        "final_test_read": False,
    })
    classification = {
        "terminal_classification": "TRANS1_RETRY_03_BLOCKED_AFTER_NODE_FIX",
        "dataset_node_unit_tests_passed": True,
        "existing_mph_node_feedback_pass": feedback["pass"],
        "existing_mph_maximum_microphone_difference_pa": feedback["maximum_complex_microphone_difference_pa"],
        "fresh_coarse_control_pass": True,
        "fresh_fine_smoke_pass": False,
        "fine_failure": failure["error"],
        "formal_256_gate_started": False,
        "six_combinations_completed": 0,
        "acoustic_scientific_status": "no new positive or negative selectivity conclusion",
        "print_recommendation": "DO_NOT_AUTHORIZE_PRINT_FROM_THIS_STAGE",
        "trans2_recommendation": "DO_NOT_ENTER_TRANS2_FROM_THIS_STAGE",
        "compact_mechanical_option": "deferred; no STL or acoustic-domain change",
        "final_test_read": False,
    }
    write_json(OUT / "scientific_classification.json", classification)

    figure, axis = plt.subplots(figsize=(10.5, 3.4))
    labels = ["Saved coarse MPH\nNode extraction", "Fresh coarse\n4-point control",
              "Fresh fine\n4-point extraction", "256-point gate", "Six combinations"]
    states = ["PASS\n0 Pa", "PASS", "BLOCKED\nmic wrong length", "NOT STARTED", "0/6"]
    colors = ["#2ca25f", "#2ca25f", "#de2d26", "#bdbdbd", "#bdbdbd"]
    for index, (label, state, color) in enumerate(zip(labels, states, colors)):
        axis.add_patch(plt.Rectangle((index * 2.0, 0.35), 1.55, 0.9, color=color, alpha=0.9))
        axis.text(index * 2.0 + 0.775, 0.80, state, ha="center", va="center", color="white", weight="bold")
        axis.text(index * 2.0 + 0.775, 0.18, label, ha="center", va="top", fontsize=9)
        if index < 4:
            axis.annotate("", xy=(index * 2.0 + 1.95, 0.8), xytext=(index * 2.0 + 1.58, 0.8),
                          arrowprops={"arrowstyle": "->", "color": "#555555"})
    axis.set_xlim(-0.2, 9.7)
    axis.set_ylim(-0.45, 1.55)
    axis.axis("off")
    axis.set_title("TRANS-1 RETRY_03 bounded diagnostic chain", weight="bold")
    figure.tight_layout()
    figure.savefig(OUT / "retry03_diagnostic_chain.png", dpi=180)
    figure.savefig(OUT / "retry03_diagnostic_chain.svg")
    plt.close(figure)

    REPORT.write_text(f"""# COMSOL TRANS-1 RETRY_03 — MPh dataset Node 精确寻址修复

日期：{datetime.now().astimezone().isoformat()}  
终态：`TRANS1_RETRY_03_BLOCKED_AFTER_NODE_FIX`

## 结论

Java dataset tag 到 MPh dataset Node 的兼容问题已经确定性修复，但 fresh fine smoke 在使用真实 Node 提取后仍未返回四点麦克风场，因此按冻结停止规则终止。本轮没有进入256点网格门禁或六组合，也没有新的声学选择性正面或负面结论。

## Node 修复证据

- 最小回归测试：3/3通过；覆盖显示名称含 `/` 且 Java tag=`dset1`。
- 未修改安装的 MPh 库。
- 加载 RETRY_02 已保存 coarse MPH 后，按 Java tag 找到 Node name=`{feedback['mph_dataset_node_name']}`、tag=`{feedback['mph_dataset_node_tag']}`。
- 六字段均返回4点；麦克风与冻结结果最大差 `{feedback['maximum_complex_microphone_difference_pa']:.1f} Pa`。

这证明 RETRY_02 的 `Dataset \"dset1\" does not exist` 已解决，不是本轮继续阻塞的原因。

## Fresh COMSOL 执行

- fresh coarse ISO-CODED/N 四频点再次通过：{coarse['mesh']['elements']:,} elements、{coarse['mesh']['vertices']:,} vertices，minimum/mean quality `{coarse['mesh']['minimum_quality']:.4g}/{coarse['mesh']['mean_quality']:.4f}`，求解 `{coarse['solve_elapsed_s']:.3f} s`；MPH 重载麦克风差 `0 Pa`。
- `LOW_MESH_QUALITY_WARNING` 保留。
- fresh fine study 在完整网格之后创建；有效 solution/dataset 的前置审计通过，Node resolver 已实际使用。
- fine 提取在 `mic` 长度门禁失败：`{failure['error']}`。
- 按契约未尝试 Java numerical evaluation、另一 dataset、第三网格或 RETRY_04。

## 数值与科学边界

- coarse/fine 256点门禁：未开始；`<1%`和`<0.5 dB`均未评估。
- 六组合：0/6。
- 2×2固定窗口矩阵、diagonal advantage、off-diagonal energy、ISO-SYM和MIX-CONTROL：未评估。
- 不授权打印，不进入TRANS-2/TRANS-3。
- 紧凑底盘只保留为未来机械选项；本轮未修改STL或内部空气域。
- `final_test_read=false`。

## Provenance 与验证

- TRANS-0 RETRY_02：{provenance['trans0_retry02']['entries']}/{provenance['trans0_retry02']['entries']}匹配。
- TRANS-1 RETRY_01：{provenance['trans1_retry01']['entries']}/{provenance['trans1_retry01']['entries']}匹配。
- TRANS-1 RETRY_02：{provenance['trans1_retry02']['entries']}/{provenance['trans1_retry02']['entries']}匹配。
- 既有失败状态均未覆盖或重新分类；未commit、push、tag或release。
""", encoding="utf-8")

    inventory_candidates = sorted(
        [path for path in OUT.iterdir() if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"}]
        + [REPORT]
    )
    inventory = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                  "sha256": sha256(path)} for path in inventory_candidates]
    write_json(OUT / "artifact_inventory.json", {
        "terminal_classification": classification["terminal_classification"],
        "artifact_count_excluding_manifest": len(inventory),
        "artifacts": inventory,
        "final_test_read": False,
    })
    manifest_files = sorted(
        [path for path in OUT.iterdir() if path.is_file() and path.name != "SHA256SUMS.txt"] + [REPORT]
    )
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in manifest_files) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

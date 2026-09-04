"""Finalize the bounded RETRY_04 fine-field root-cause diagnostic."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_04"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_1_I2F_RETRY_04.md"


def read_json(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    mesh = read_json("fine_mesh_statistics_before_extraction.json")
    live = read_json("fine_live_raw_extraction_diagnostic.json")
    reload = read_json("fine_reload_raw_extraction_diagnostic.json")
    execution = read_json("retry04_execution_result.json")
    provenance = read_json("retry03_provenance_verification.json")
    study = read_json("study_solution_dataset_audit.json")

    fields = ("mic", "mic_numerator", "mic_operator_unity", "e_all", "e_hr03", "e_south", "e_plenum")
    spatial_shapes = {key: live["mph_evaluate"][key]["shape"] for key in fields}
    java_errors = {
        key: live["java_eval_global"][key].get("error")
        for key in fields
        if live["java_eval_global"][key]["status"] == "exception"
    }
    classification = {
        "technical_status": "TRANS1_RETRY_04_ROOT_CAUSE_IDENTIFIED_EMPTY_FINE_MESH",
        "root_cause": "fine mesh sequence contained zero volume elements before the study run",
        "evidence": {
            "fine_elements": mesh["elements"],
            "fine_vertices": mesh["vertices"],
            "fine_minimum_quality": mesh["minimum_quality"],
            "fine_mean_quality": mesh["mean_quality"],
            "inner_frequency_values_hz": live["solution_axes"]["inner"]["values"],
            "frequency_shape": live["mph_evaluate"]["frequency"]["shape"],
            "incident_pressure_shape": live["mph_evaluate"]["incident_pressure"]["shape"],
            "spatial_result_shapes": spatial_shapes,
            "java_source_selection_not_meshed": all("未进行网格划分" in error for error in java_errors.values()),
            "operator_entity_counts": {
                key: value["entity_count"] for key, value in live["operators"].items()
            },
            "reload_reproduced": reload["mph_evaluate"]["mic"]["shape"] == [4, 0],
        },
        "hypotheses": {
            "array_normalization_problem": "rejected",
            "dataset_node_resolution_problem": "rejected",
            "missing_inner_frequency_solutions": "rejected",
            "empty_geometry_selections": "rejected",
            "empty_spatial_mesh_and_spatial_dofs": "supported",
        },
        "interpretation": (
            "The non-empty sol1 and four frequency values are not evidence of a valid acoustic field; "
            "only global/parameter values were available because the spatial source selections were unmeshed."
        ),
        "recommended_next_technical_action": (
            "If separately authorized, repair the fine mesh sequence by retaining a complete automatic "
            "volume mesh or adding an explicit FreeTet operation, and fail before study.run() unless "
            "elements and vertices are positive."
        ),
        "fresh_comsol_solve_count": execution["fresh_comsol_solve_count"],
        "formal_256_gate_started": False,
        "six_combinations_completed": 0,
        "trans2_started": False,
        "print_authorized": False,
        "scientific_conclusion": "none; technical root-cause diagnostic only",
        "final_test_read": False,
    }
    write_json(OUT / "root_cause_classification.json", classification)

    report = f"""# COMSOL TRANS-1 RETRY_04 — 有界 fine 结果提取根因诊断

日期：{datetime.now().astimezone().isoformat()}  
终态：`TRANS1_RETRY_04_ROOT_CAUSE_IDENTIFIED_EMPTY_FINE_MESH`

## 结论

本轮一次授权求解已经把 RETRY_03 的模糊“结果场提取不完整”定位为明确的上游技术根因：fine 网格在 study 运行前实际为 **0 elements、0 vertices**。因此 `sol1` 虽非空且具有4个频率索引，但没有可供麦克风平均或域积分使用的空间网格自由度。

这不是 MPh dataset Node 寻址问题，也不是复数数组整形、麦克风位置或声学选择性本身的失败。

## 决定性证据

- 唯一一次 fresh COMSOL fine 四频点求解完成；总求解次数：1。
- 网格在结果提取前持久化：elements `{mesh['elements']}`、vertices `{mesh['vertices']}`、minimum/mean quality `{mesh['minimum_quality']}/{mesh['mean_quality']}`。
- dataset `dset1` 绑定非空 `sol1`；inner solution 为 `{live['solution_axes']['inner']['values']}` Hz。
- `freq` 与 `p_inc` 均返回4点，因为它们是解轴/全局参数。
- `aveop_mic(acpr.p_t)`、`aveop_mic(1)`及四个能量积分均返回 `[4,0]`。
- Java EvalGlobal 对边界67及域1–78明确报告“源选择未进行网格划分”。
- `aveop_mic`和各积分算子的几何实体数分别为 `{classification['evidence']['operator_entity_counts']}`，所以不是空 selection。
- MPH 保存、移除、重载后同样返回 `[4,0]`，排除仅存在于实时会话的偶发提取问题。

## 对既有阶段的修正解释

RETRY_02/03 中“非空 sol1 + 绑定 dataset”只证明了 study/solution 容器存在，不能证明空间声场有效。RETRY_04 表明 fine 构建链生成了频率轴和全局参数，但没有有效体网格；因此不得将该结果称作完整 COMSOL 声学求解。

最可能的代码层原因是：`refine_mesh()`在已有 physics-controlled mesh 上加入局部 `Size` 后，没有确保保留或建立完整体网格操作。后续修复必须显式保留完整自动体网格或建立 `FreeTet`，并在 `study.run()` 前以 elements>0、vertices>0 和 positive quality 作为硬门禁。

## 范围与决策

- 未运行256点 coarse/fine 门禁；六组合0/6。
- 未进入TRANS-2/TRANS-3；未授权打印。
- 未修改几何、物理、频率、窗口、阈值或STL。
- 未读取final-test；`final_test_read=false`。
- 未commit、push、tag或release。
- RETRY_03 provenance `{provenance['entries']}/{provenance['entries']}` 匹配。

本轮授权仅覆盖诊断，现已停止。是否执行独立的 fine mesh 修复阶段，需要用户另行授权。
"""
    REPORT.write_text(report, encoding="utf-8")

    excluded = {"SHA256SUMS.txt", "artifact_inventory.json"}
    artifacts = [REPORT] + sorted(
        path for path in OUT.iterdir()
        if path.is_file() and path.name not in excluded
    )
    inventory = {
        "technical_status": classification["technical_status"],
        "artifact_count_excluding_inventory_and_manifest": len(artifacts),
        "artifacts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in artifacts
        ],
        "final_test_read": False,
    }
    write_json(OUT / "artifact_inventory.json", inventory)
    manifest_paths = artifacts + [OUT / "artifact_inventory.json"]
    lines = [f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in manifest_paths]
    (OUT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

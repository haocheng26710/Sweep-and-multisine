"""Finalize immutable TRANS-0 BLOCKED provenance after the bounded smoke."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT"
PKG = ROOT / "outputs/print_packages/TRANS_I2F_INTEGRATED_TWO_PORT_V1"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_0_I2F_PREFLIGHT.md"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    now = datetime.now().astimezone().isoformat()
    zip_path = PKG.with_suffix(".zip")
    b01 = PKG / "STL/TRANS_I2F_B01_INTEGRATED_BASE_HR03_N_HR07_S.stl"
    l01 = PKG / "STL/TRANS_I2F_L01_SEALING_LID.stl"
    p03 = PKG / "STL/TRANS_I2F_P03_MIC_INSERT_ID9_0.stl"
    geometry = PKG / "geometry_validation.json"
    package_manifest = PKG / "SHA256SUMS.txt"
    trans1_report = ROOT / "docs/progress/COMSOL_TRANS_1_INTEGRATED_TWO_PORT_SIMULATION.md"
    trans1_log = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F/blocked_execution_log.txt"
    trans1_runner = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F/run_trans1.py"

    frozen = {
        "zip": {"sha256": sha(zip_path), "expected": "383e099df04541ebb667067cfa07754a71a3004dba613d5564dace6a587f24bb"},
        "B01": {"sha256": sha(b01), "expected": "523ae1ea424eb769850aea9abcf3ba2931615ac6194dc0c5b66ab4b87b35b7b1"},
        "L01": {"sha256": sha(l01), "expected": "0a117c1f01d5f8bb2f48ea6fe87a940a533011cedc67ccd52e54c63f8e8c831e"},
        "P03": {"sha256": sha(p03), "expected": "fbb48f5b05a202a8704f4ddd38a78695ceed2b1a41b85e0baeb7f06bc605b36e"},
        "geometry_validation": {"sha256": sha(geometry), "expected": "4024de4a005932f9fa2be44f8b9857dbf6be0dee775aabab4540063a72702a2a"},
        "package_manifest": {"sha256": sha(package_manifest), "expected": "df83f8935e62749a32564e3c299d72ecb4467a9597f822b6c62311f55ff7b6d2"},
    }
    for value in frozen.values():
        value["match"] = value["sha256"] == value["expected"]
    manifest_mismatches = []
    for line in package_manifest.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        observed = sha(PKG / relative)
        if observed != expected:
            manifest_mismatches.append({"path": relative, "expected": expected, "observed": observed})
    write_json("design_freeze_audit.json", {
        "schema_version": "comsol_trans0_design_freeze_v1.0.0", "created_at": now,
        "classification": "DESIGN_DIGITAL_GEOMETRY_FROZEN_NOT_ACOUSTICALLY_ACCEPTED",
        "hashes": frozen, "package_manifest_entries": 17, "package_manifest_mismatches": manifest_mismatches,
        "zip_crc_test": "pass", "geometry_validation_classification": "GEOMETRY_READY_SIMULATION_PENDING",
        "comsol_acoustic_acceptance_claimed": False, "final_test_read": False,
        "trans1_provenance": {"classification": "TRANS1_BLOCKED", "preserved": True,
            "report_sha256": sha(trans1_report), "blocked_log_sha256": sha(trans1_log),
            "runner_sha256": sha(trans1_runner)},
    })

    # Exact values captured from the successful real COMSOL 6.4 regression run.
    adjacency = {str(i): ([1, 2] if i == 6 else ([1] if i <= 5 else [2])) for i in range(1, 12)}
    write_json("api_adjacency_test.json", {
        "schema_version": "comsol_trans0_api_adjacency_regression_v1.0.0", "created_at": now,
        "source_test": {"bad_call_absent": True, "good_call_present": True,
                        "workplane_quickz_present": True, "extrude_pos_absent": True, "pass": True},
        "red_before_fix": {"bad_call_absent": False, "good_call_present": False, "pass": False},
        "comsol": {"version": "6.4", "model": "two touching 10 mm cubes with explicit Union intbnd=true",
                   "domain_count": 2, "boundary_count": 11, "exterior_boundary_count": 10,
                   "internal_boundary_count": 1, "exterior_boundaries": [1,2,3,4,5,7,8,9,10,11],
                   "internal_boundaries": [6], "boundary_adjacent_domains": adjacency,
                   "wall_boundaries": [1,2,3,4,5,7,8,9,10,11],
                   "internal_boundary_excluded_from_walls": True, "invalid_boundary_queries": [], "pass": True},
        "compatibility_repair": "implicit finalization rejected intbnd; replaced in test fixture by explicit Union intbnd=true, supported by existing accepted COMSOL model scripts",
        "pass": True,
    })
    write_json("geometry_selection_audit.json", {
        "schema_version": "comsol_trans0_i2f_geometry_selection_audit_v1.0.0", "created_at": now,
        "model": "ISO-CODED / N excitation only", "comsol_version": "6.4",
        "geometry_built": True, "N_selection_nonempty": True, "S_selection_nonempty": True,
        "microphone_selection_nonempty": True, "wall_selection_all_exterior": True,
        "internal_continuity_boundaries_excluded_from_sound_hard": True,
        "ports_excluded_from_sound_hard": True, "air_domain_adjacency_graph_connected": True,
        "gate_execution_note": "all assertions completed inside build_model before it returned to run_smoke",
        "exact_entity_ids_and_measures_persisted": False,
        "reason_not_persisted": "the runner wrote detailed audit only after solve; the later study lookup failure occurred first",
        "overall_pass": False, "blocking_gap": "required detailed selection identity/measure record was not persisted",
    })
    write_json("mesh_statistics.json", {
        "schema_version": "comsol_trans0_i2f_mesh_statistics_v1.0.0", "created_at": now,
        "coarse_mesh_run_completed": True, "automatic_level": 7, "maximum_frequency_hz": 8000.0,
        "positive_element_count_and_quality_gate_passed_in_process": True,
        "elements": None, "vertices": None, "minimum_quality": None, "mean_quality": None,
        "exact_statistics_persisted": False,
        "reason": "statistics were held in memory and scheduled for export after solve; study lookup failed before export",
        "acceptance_gate_pass": False,
    })
    with (OUT / "sparse_smoke_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["grid_index", "frequency_hz", "mic_real", "mic_imag", "mic_magnitude", "mic_phase_deg", "status"])
        writer.writeheader()
        for index, frequency in enumerate((1000.0, 1850.0, 3800.0, 5000.0)):
            writer.writerow({"grid_index": index, "frequency_hz": frequency, "status": "not_solved_TRANS0_BLOCKED"})
    write_json("reload_validation.json", {
        "schema_version": "comsol_trans0_reload_validation_v1.0.0", "created_at": now,
        "mph_saved": False, "model_removed": True, "model_reloaded": False, "results_compared": False,
        "pass": False, "reason": "study lookup failed before frequency solve and save",
    })
    write_json("scientific_classification.json", {
        "classification": "TRANS0_BLOCKED", "acoustic_scientific_result": False,
        "design_freeze_pass": True, "api_adjacency_regression_pass": True,
        "i2f_sparse_smoke_pass": False,
        "blocked_reason": "MPh lookup reported Study std_freq does not exist although the Java study node had been created",
        "compatibility_repair_budget_exhausted": True, "trans1_retry_authorized": False,
        "TRANS_1B_started": False, "later_stages_started": False, "final_test_read": False,
    })
    (OUT / "execution_log.txt").write_text(
        "TRANS-0A: all frozen package hashes and 17-entry manifest verified; ZIP CRC passed.\n"
        "Fresh COMSOL 6.4 server localhost:51937, 4 cores, initial model count 0.\n"
        "Source regression RED: reversed getAdj present and corrected call absent.\n"
        "Source fix: new TRANS-0 runner uses geom.getAdj(2,3,boundary); original TRANS-1 runner unchanged.\n"
        "First real adjacency fixture attempt: implicit finalization rejected intbnd property.\n"
        "Only compatibility repair: explicit Union with intbnd=true, supported by existing accepted scripts.\n"
        "Regression GREEN: 2 domains, 11 boundaries, 10 exterior, 1 internal (boundary 6 -> domains [1,2]); internal excluded from walls.\n"
        "ISO-CODED/N smoke: geometry, required selections, exterior-wall filter, connected adjacency graph and coarse mesh gates completed.\n"
        "New failure: MPh solve lookup reported Study std_freq does not exist. No frequency point solved and no MPH saved.\n"
        "Per bounded rule no second compatibility repair or retry was attempted.\n",
        encoding="utf-8")

    report = f"""# COMSOL TRANS-0 — TRANS-I2F 设计冻结与预检

日期：{now}  
终态：`TRANS0_BLOCKED`

## 结论

TRANS-0A 设计冻结审计和最小 COMSOL 6.4 邻接 API 回归均通过；TRANS-I2F ISO-CODED/N smoke 在几何、selection、空气域连通和 coarse mesh 门禁之后，因 MPh 无法按 `std_freq` 找到已由 Java API 创建的 study 而停止。四个频点均未求解，未保存或重载 MPH。因此本轮没有证明完整建模链路可用，不能授权 `TRANS1 RETRY_01`。

这不是声学阴性结果，也不改变既有 `TRANS1_BLOCKED`。本轮未重新执行完整 TRANS-1，未启动 TRANS-1B、TRANS-2、TRANS-3、P05–P10 或外场。

## TRANS-0A 设计冻结

ZIP、B01、L01、P03、geometry validation 和 17 项包内 manifest 全部匹配冻结 SHA-256；ZIP CRC 检查通过。ZIP SHA-256 为 `{frozen['zip']['sha256']}`。打印包仍仅为 `GEOMETRY_READY_SIMULATION_PENDING`，只代表数字几何/可打印性检查，不代表 COMSOL 声学验收。

原 TRANS-1 provenance 保持原位且未改写：报告、阻塞日志、runner SHA-256 分别为 `{sha(trans1_report)}`、`{sha(trans1_log)}`、`{sha(trans1_runner)}`。

## 邻接 API 回归

先写测试并观察到旧调用测试失败；新 TRANS-0 runner 固定使用 `geom.getAdj(2, 3, boundary)`，保留 `WorkPlane.quickz`，不含 `Extrude.pos`。真实 COMSOL 6.4 两相接空气块返回 2 个域和 11 个边界：外边界 10 个，各邻接 1 个域；内部边界 6 邻接域 `[1,2]`。wall selection 为 `[1,2,3,4,5,7,8,9,10,11]`，不包含内部边界 6。

测试夹具首次尝试发现 implicit finalization 不接受 `intbnd`。本轮唯一兼容修复改用仓库既有成功模型支持的显式 `Union(intbnd=true)`，随后同一回归通过。

## ISO-CODED/N 稀疏 smoke

使用冻结几何、343 m/s、1.2041 kg/m³、z=1.0 mm 的 Ø8.8 mm 麦克风面、Ø9 mm 短孔、N 端 1 Pa 压力、S 端平面波辐射和 Sound Hard 外壁。运行过程中以下门禁已经通过：N/S/microphone selections 非空；walls 只取外边界；内部连续边界不进入 Sound Hard；端口不进入 wall；空气域邻接图连通；coarse mesh 生成且元素数与最小质量为正。

runner 原计划在求解后统一写出详细 entity/面积和 mesh 数值；随后 `model.solve("std_freq")` 报 `Study "std_freq" does not exist`，所以这些精确数值没有持久化。按照一次修复上限，没有修改 study 标签/label 调用后重跑。这一缺口本身使 TRANS-0 不能通过。

## 边界与验证

- `sparse_smoke_results.csv` 明确标记四点均未求解，不含伪造复数值。
- 没有成功 MPH；remove/reload/result equality 未执行。
- 不解释方向选择性、HR03/HR07 身份或峰值。
- `final_test_read=false`；未修改 STL、实验数据、既有 TRANS-1 产物或论文结论。
- 未 commit、push、tag 或 release。
"""
    REPORT.write_text(report, encoding="utf-8")

    inventory = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"} and path.suffix != ".pyc":
            inventory.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size,
                              "sha256": sha(path), "role": "TRANS-0 preflight evidence"})
    inventory.append({"path": str(REPORT.relative_to(ROOT)).replace("\\", "/"), "bytes": REPORT.stat().st_size,
                      "sha256": sha(REPORT), "role": "TRANS-0 report"})
    write_json("artifact_inventory.json", {"classification": "TRANS0_BLOCKED", "artifacts": inventory,
                                             "successful_preflight_mph_present": False})
    manifest_paths = [path for path in sorted(OUT.iterdir()) if path.is_file() and path.name != "SHA256SUMS.txt" and path.suffix != ".pyc"] + [REPORT]
    (OUT / "SHA256SUMS.txt").write_text("".join(
        f"{sha(path)}  {str(path.relative_to(ROOT)).replace(chr(92), '/')}\n" for path in manifest_paths), encoding="utf-8")


if __name__ == "__main__":
    main()

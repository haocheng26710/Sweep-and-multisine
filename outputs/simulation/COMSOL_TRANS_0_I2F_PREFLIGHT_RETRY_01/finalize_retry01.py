"""Finalize TRANS-0 RETRY_01 evidence without changing either prior phase."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_01"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_01.md"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    now = datetime.now().astimezone().isoformat()
    result = load("preflight_execution_result.json")
    geometry = load("geometry_selection_audit.json")
    mesh = load("mesh_statistics.json")
    reload = load("reload_validation.json")
    selection = geometry["selection_audit"]
    identity = selection["identity_checks"]
    expected_port_area = float(identity["expected_port_area_m2"])
    observed_port_area = float(selection["port_N_area_m2"])
    port_identity_pass = (
        len(selection["bnd_port_N"]) == 1
        and len(selection["bnd_port_S"]) == 1
        and abs(observed_port_area / expected_port_area - 1.0) <= 1e-6
        and abs(float(selection["port_S_area_m2"]) / expected_port_area - 1.0) <= 1e-6
    )

    write("study_tag_label_audit.json", {
        "schema_version": "comsol_trans0_retry01_study_tag_label_audit_v1.0.0", "created_at": now,
        "source_regression": {"legacy_literal_absent": True, "java_study_tags_checked": True,
                              "std_freq_tag_resolved": True, "frequency_feature_tags_checked": True,
                              "direct_java_run_present": True, "pass": True},
        "legacy_failure_reproduced_in_live_comsol": True,
        "legacy_error": "LookupError: Study \"std_freq\" does not exist.",
        "probe": {"java_study_tags": ["std_freq"], "study_tag": "std_freq",
                  "study_label": "Retry 01 Display Label Probe", "feature_tags": ["freq"],
                  "tag_and_label_distinct": True, "pass": True},
        "actual_smoke": {"java_study_tags": ["std_freq"], "study_tag": "std_freq",
                         "study_label": result["study"]["study_label"], "feature_tags": ["freq"],
                         "direct_java_study_run_completed": True, "tag_label_mixed": False},
        "pass": True,
    })
    write("scientific_classification.json", {
        "classification": "TRANS0_RETRY_01_BLOCKED", "created_at": now,
        "study_tag_label_fix_pass": True, "direct_java_frequency_solve_pass": True,
        "four_frequency_results_finite_nonzero": True, "mph_save_remove_reload_pass": bool(reload["pass"]),
        "port_boundary_identity_pass": port_identity_pass,
        "blocked_reason": "N and S port Box selections each contain five exterior boundaries and area is 8.654052x the intended inlet end-face area",
        "acoustic_scientific_interpretation_allowed": False, "trans1_retry_authorized": False,
        "final_test_read": False, "later_stages_started": False,
    })
    (OUT / "execution_log.txt").write_text(
        "Fresh COMSOL 6.4 server localhost:60733, 4 cores, initial model count 0.\n"
        "Source regression RED before fix: legacy model.solve literal present; Java tag checks/run absent.\n"
        "Authorized retry fix only: validate Java study tag std_freq and feature tag freq, then call study.run().\n"
        "Live lookup probe: Java tag std_freq, display label 'Retry 01 Display Label Probe', feature tag freq; legacy MPh lookup reproduced Study std_freq does not exist.\n"
        "Actual smoke study tag std_freq, display label 研究, feature tag freq; direct Java run completed.\n"
        "Geometry: 78 domains, 353 boundaries, one connected adjacency component; internal boundaries excluded from Sound Hard walls.\n"
        "Mesh: 62356 elements, 13158 vertices, minimum quality 1.251e-06, mean quality 0.547.\n"
        "Solve: four frequencies completed in 19.6923084259 s; complex microphone response finite and nonzero.\n"
        "MPH saved, removed, reloaded; maximum complex pressure difference 0 Pa.\n"
        "Blocking audit: N selection [5,6,7,8,353], S selection [1,2,3,4,352]; each area 0.001107718716661341 m2 versus intended end face 0.000128 m2 (+765.405%).\n"
        "Because pressure was applied to five faces per port rather than only the inlet end face, the solved response is diagnostic-only and the preflight cannot pass.\n"
        "No selection repair or rerun performed; TRANS-1 RETRY_01 and all later stages not started. final_test_read=false.\n",
        encoding="utf-8")

    values = list(zip(result["frequencies_hz"], result["mic_real"], result["mic_imag"]))
    value_rows = "\n".join(f"| {f:.0f} | {r:.12g} | {i:.12g} |" for f, r, i in values)
    original_trans0 = ROOT / "docs/progress/COMSOL_TRANS_0_I2F_PREFLIGHT.md"
    original_trans1 = ROOT / "docs/progress/COMSOL_TRANS_1_INTEGRATED_TWO_PORT_SIMULATION.md"
    report = f"""# COMSOL TRANS-0 RETRY_01 — study tag/label 修复

日期：{now}  
终态：`TRANS0_RETRY_01_BLOCKED`

## 结论

授权的 study tag/label 修复成功：旧 MPh lookup 失败被真实复现，retry runner 在求解前确认 Java study tag `std_freq`、显示 label `研究`、feature tag `freq`，并通过 `model.java.study("std_freq").run()` 完成四频点真实 Pressure Acoustics 求解。MPH 保存、移除、重载后最大复数压力差为 `0 Pa`。

但是详细 selection 身份审计显示 N/S 入口各包含 5 个边界，而不是单一入口端面。每侧选择面积为 `{observed_port_area:.15g} m²`，冻结端面面积应为 `{expected_port_area:.15g} m²`，相对偏差 `+{100*(observed_port_area/expected_port_area-1):.3f}%`。因此 1 Pa 压力被施加到入口附近多张外表面；本轮求解不能证明冻结边界条件链路正确。唯一授权修复仅限 study 调用，未修改 selection 或重跑，终态必须保持 BLOCKED，且不授权 TRANS-1 RETRY_01。

## study tag/label 回归

- 修复前静态门禁按预期失败；修复后确认 runner 不含 `model.solve("std_freq")`。
- live probe：Java tags=`[std_freq]`，label=`Retry 01 Display Label Probe`，features=`[freq]`；旧 MPh 路径稳定报 `Study "std_freq" does not exist`。
- 正式 smoke：tag=`std_freq`，label=`研究`，feature=`freq`，直接 Java run 完成。

## 几何、selection 与网格

- 78 个空气子域、353 个边界；邻接图 1 个连通分量。
- N selection：`{selection['bnd_port_N']}`；S selection：`{selection['bnd_port_S']}`；microphone：`{selection['bnd_mic_face']}`。
- wall selection 仅来自外边界，内部连续边界和两个 port selections 均未进入 Sound Hard。
- microphone 面积 `{selection['microphone_area_m2']:.15g} m²`，相对 Ø8.8 mm 解析圆面积偏差 `{100*identity['microphone_area_relative_error']:.4f}%`。
- coarse mesh：{mesh['elements']} elements、{mesh['vertices']} vertices；minimum/mean quality `{mesh['minimum_quality']}` / `{mesh['mean_quality']}`。

## 四频点结果（仅技术诊断，不作声学解释）

| Hz | microphone real | microphone imag |
|---:|---:|---:|
{value_rows}

频率轴严格为 `[1000,1850,3800,5000] Hz`；结果 finite 且非全零；direct Java 求解耗时 `{result['elapsed_s']:.6f} s`。由于端口 selection 身份失败，不得据此解释方向选择性、HR03/HR07 标签或打印适用性。

## 保存、重载与 provenance

`TRANS0_RETRY01_ISO_CODED_N.mph` SHA-256 为 `{reload['saved_sha256']}`。模型从内存移除并在 COMSOL 6.4 重载，频率轴一致，复数结果最大差 `{reload['maximum_complex_pressure_difference_pa']} Pa`，通过 `1e-12 Pa` 技术门槛。

原 TRANS-0 与 TRANS-1 报告保持原位且未重新分类；当前 SHA-256 为 `{sha(original_trans0)}` 与 `{sha(original_trans1)}`。本轮未开始 TRANS-1 RETRY_01、TRANS-1B 或后续阶段；未读取 final-test；未修改 STL、MPh/MCP 安装源码、实验数据或论文结论；未 commit、push、tag 或 release。
"""
    REPORT.write_text(report, encoding="utf-8")

    inventory = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"} and path.suffix != ".pyc":
            inventory.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                              "bytes": path.stat().st_size, "sha256": sha(path),
                              "role": "TRANS-0 RETRY_01 evidence"})
    inventory.append({"path": str(REPORT.relative_to(ROOT)).replace("\\", "/"),
                      "bytes": REPORT.stat().st_size, "sha256": sha(REPORT), "role": "phase report"})
    write("artifact_inventory.json", {"classification": "TRANS0_RETRY_01_BLOCKED",
                                       "artifacts": inventory, "mph_present": True,
                                       "mph_scientific_use_allowed": False})
    paths = [p for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "SHA256SUMS.txt" and p.suffix != ".pyc"] + [REPORT]
    (OUT / "SHA256SUMS.txt").write_text("".join(
        f"{sha(path)}  {str(path.relative_to(ROOT)).replace(chr(92), '/')}\n" for path in paths), encoding="utf-8")


if __name__ == "__main__":
    main()

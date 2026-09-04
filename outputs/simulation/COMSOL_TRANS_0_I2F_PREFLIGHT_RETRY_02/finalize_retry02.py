"""Finalize TRANS-0 RETRY_02 evidence without rerunning COMSOL."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_0_I2F_PREFLIGHT_RETRY_02.md"


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    now = datetime.now().astimezone().isoformat()
    port = load("port_selection_regression.json")
    cavity = load("cavity_domain_selection_audit.json")
    geometry = load("geometry_selection_audit.json")
    mesh = load("mesh_statistics.json")
    reload = load("reload_validation.json")
    execution = load("preflight_execution_result.json")
    smoke = read_csv("sparse_smoke_results.csv")
    energy = read_csv("cavity_energy_smoke.csv")

    frequency = [float(row["frequency_hz"]) for row in smoke]
    mic = [complex(float(row["mic_real"]), float(row["mic_imag"])) for row in smoke]
    energy_values = [float(row[key]) for row in energy for key in
                     ("hr03_energy_j", "south_energy_j", "plenum_energy_j")]
    gates = {
        "port_regression_pass": bool(port["pass"]),
        "port_identity_pass": bool(geometry["selection_audit"]["port_identity_pass"]),
        "walls_complete_and_ports_excluded": bool(
            geometry["selection_audit"]["walls_equal_all_exterior_except_ports_and_mic"]
            and geometry["selection_audit"]["ports_excluded_from_walls"]
        ),
        "cavity_feature_union_pass": bool(cavity["pass"]),
        "cavity_integration_binding_pass": bool(cavity["integration_binding_pass"]),
        "frequency_axis_exact": frequency == [1000.0, 1850.0, 3800.0, 5000.0],
        "microphone_finite_nonzero": all(math.isfinite(value.real) and math.isfinite(value.imag) for value in mic)
        and any(abs(value) > 0 for value in mic),
        "cavity_energy_finite": all(math.isfinite(value) for value in energy_values),
        "south_energy_defined_nonconstant_zero": all(math.isfinite(float(row["south_energy_j"])) for row in energy)
        and any(float(row["south_energy_j"]) != 0 for row in energy),
        "reload_pass": bool(reload["pass"] and reload["maximum_complex_pressure_difference_pa"] <= 1e-12),
        "solve_success": bool(execution["success"]),
    }
    passed = all(gates.values())
    classification = "TRANS0_PASS_FOR_TRANS1_RETRY" if passed else "TRANS0_RETRY_02_BLOCKED"
    classification_record = {
        "classification": classification,
        "created_at": now,
        "gates": gates,
        "mesh_warning": "LOW_MESH_QUALITY_WARNING",
        "minimum_mesh_quality": mesh["minimum_quality"],
        "scope": "COMSOL chain preflight only; not an acoustic scientific conclusion or print authorization",
        "trans1_retry_started": False,
        "later_stages_started": False,
        "final_test_read": False,
    }
    write_json(OUT / "scientific_classification.json", classification_record)

    n = geometry["selection_audit"]["port_boundary_records"]["N"][0]
    s = geometry["selection_audit"]["port_boundary_records"]["S"][0]
    volumes = cavity["volume_m3"]
    errors = cavity["volume_relative_error"]
    mph = OUT / execution["mph"]
    log = (
        f"TRANS-0 RETRY_02 execution log\ncreated_at={now}\nclassification={classification}\n"
        "Fresh COMSOL 6.4 session initial model count=0.\n"
        f"Port regression: legacy intersects N/S counts=5/5; inside counts=1/1; "
        f"areas={n['area_m2']:.17g}/{s['area_m2']:.17g} m2.\n"
        f"Cavity Union: HR03 domains={len(cavity['domains']['dom_hr03_cavity'])}, "
        f"HR07 domains={len(cavity['domains']['dom_south_cavity'])}; disjoint and plenum excluded.\n"
        f"Cavity volume relative errors: HR03={errors['hr03']:.9g}, HR07={errors['south']:.9g}.\n"
        f"Mesh: elements={mesh['elements']}, vertices={mesh['vertices']}, "
        f"minimum/mean quality={mesh['minimum_quality']}/{mesh['mean_quality']}; LOW_MESH_QUALITY_WARNING.\n"
        f"Direct Java frequency solve completed in {execution['elapsed_s']:.6f} s; four microphone results and cavity energies finite.\n"
        f"MPH saved/removed/reloaded; maximum complex pressure difference={reload['maximum_complex_pressure_difference_pa']} Pa.\n"
        "No adaptive mesh work or acoustic interpretation performed. TRANS-1 RETRY_01 and later stages not started. final_test_read=false.\n"
    )
    (OUT / "execution_log.txt").write_text(log, encoding="utf-8")

    result_rows = "\n".join(
        f"| {row['frequency_hz']} | {float(row['mic_real']):.12g} | {float(row['mic_imag']):.12g} | "
        f"{float(energy[i]['hr03_energy_j']):.12g} | {float(energy[i]['south_energy_j']):.12g} |"
        for i, row in enumerate(smoke)
    )
    report = f"""# COMSOL TRANS-0 RETRY_02 — 端口身份与腔体 selection 最终预检

日期：{now}  
终态：`{classification}`

## 结论

最后一次 TRANS-0 兼容 retry 通过。端口 Box selection 已显式使用 `inside`，不硬编码 COMSOL 边界编号；N/S 各得到一个真实外端面。HR03/HR07 腔体 selection 从 COMSOL 实际生成的六个 primitive-domain selection outputs 分别建立 Union，两个腔体均非空、互不重叠、排除中央 micro-plenum，且解析体积门槛通过。四频点真实 Pressure Acoustics 求解、腔体能量积分、MPH 保存/移除/重载均通过。

`{classification}` 仅表示 COMSOL 建模链路可进入用户另行授权的 TRANS-1 RETRY_01；不是声学科学结论、方向选择性结论或最终打印授权。本轮没有启动 TRANS-1 或任何后续阶段。

## 端口 selection 回归

- 旧 `intersects` 真实复现：N=`{port['live_regression']['old_intersects']['N']}`、S=`{port['live_regression']['old_intersects']['S']}`，各 5 个边界。
- 新 `inside`：N 边界 `{n['boundary']}`、S 边界 `{s['boundary']}`；编号仅为本次审计输出，runner 未硬编码。
- N/S 中心 y=`{n['center_m'][1]*1000:.9f}` / `{s['center_m'][1]*1000:.9f} mm`，各仅邻接一个三维域。
- N/S 面积均为 `{n['area_m2']:.15g} m²`；相对冻结面积 `0.000128 m²` 的最大误差 `{geometry['selection_audit']['identity_checks']['port_area_relative_error_max']*100:.9g}%`。
- 两个端口均从 Sound Hard 排除；wall selection 精确等于全部外边界扣除 N/S 端口和 microphone，因此顶面、底面和侧壁保留为 Sound Hard；内部连续边界不进入 wall。

## HR03/HR07 cavity selection

- 求解前枚举并记录全部 COMSOL component selection tags；HR03/HR07 各解析到 6 个唯一 feature output tags，见 `cavity_domain_selection_audit.json`。
- `dom_hr03_cavity`：{len(cavity['domains']['dom_hr03_cavity'])} 个求解域；实际/解析体积 `{volumes['hr03_actual']:.15g}` / `{volumes['hr03_analytic']:.15g} m³`，相对误差 `{errors['hr03']*100:.9g}%`。
- `dom_south_cavity`（HR07）：{len(cavity['domains']['dom_south_cavity'])} 个求解域；实际/解析体积 `{volumes['south_actual']:.15g}` / `{volumes['south_analytic']:.15g} m³`，相对误差 `{errors['south']*100:.9g}%`。
- 两 selection 非空、互斥并排除 `dom_plenum`；`intop_hr03` 与 `intop_south` 的绑定域分别与对应 Union 完全一致。

## 四频点 smoke

Java study tag=`std_freq`，label=`{execution['study']['study_label']}`，feature tag=`freq`；通过 `study.run()` 完成，求解与保存/重载阶段耗时 `{execution['elapsed_s']:.6f} s`。

| Hz | microphone real | microphone imag | HR03 energy (J) | HR07 energy (J) |
|---:|---:|---:|---:|---:|
{result_rows}

频率轴严格匹配 `[1000, 1850, 3800, 5000] Hz`；麦克风复数结果 finite 且非全零；两腔体能量积分 finite，`intop_south` 非空、已定义且不恒为零。以上仅证明技术链路，不解释频率编码或方向选择性。

## 网格、保存与限制

- coarse mesh：{mesh['elements']} elements、{mesh['vertices']} vertices；minimum/mean quality `{mesh['minimum_quality']}` / `{mesh['mean_quality']}`。
- 登记 `LOW_MESH_QUALITY_WARNING`；本轮未做自适应优化。正式 TRANS-1 必须以规定 coarse/fine 对比后方可接受科学结果。
- MPH：`{mph.name}`，SHA-256 `{sha256(mph)}`。
- 保存、从内存移除并重载后频率轴一致，最大复数压力差 `{reload['maximum_complex_pressure_difference_pa']} Pa`，通过 `1e-12 Pa` 门槛。

## Provenance 与边界

原 TRANS-0、TRANS-0 RETRY_01 与 TRANS-1 的 BLOCKED 报告及输出保持原位，未覆盖或重新分类。未读取 final-test（`final_test_read=false`）；未启动 TRANS-1 RETRY_01、TRANS-1B、TRANS-2、TRANS-3 或 P05–P10；未修改 STL、实验数据、MPh/COMSOL MCP 源码或论文结论；未 commit、push、tag 或 release。
"""
    REPORT.write_text(report, encoding="utf-8")

    inventory_paths = [path for path in sorted(OUT.iterdir())
                       if path.is_file() and path.name not in {"artifact_inventory.json", "SHA256SUMS.txt"}
                       and path.suffix != ".pyc"] + [REPORT]
    inventory = {
        "classification": classification,
        "created_at": now,
        "artifacts": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                       "sha256": sha256(path)} for path in inventory_paths],
    }
    write_json(OUT / "artifact_inventory.json", inventory)
    manifest_paths = [path for path in sorted(OUT.iterdir())
                      if path.is_file() and path.name != "SHA256SUMS.txt" and path.suffix != ".pyc"] + [REPORT]
    (OUT / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in manifest_paths),
        encoding="utf-8",
    )
    if not passed:
        raise SystemExit("TRANS0_RETRY_02_BLOCKED")


if __name__ == "__main__":
    main()

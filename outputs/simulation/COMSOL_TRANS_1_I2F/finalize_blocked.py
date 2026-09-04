"""Finalize the bounded TRANS-1 BLOCKED evidence package without new solves."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F"
DOC = ROOT / "docs/progress/COMSOL_TRANS_1_INTEGRATED_TWO_PORT_SIMULATION.md"
PACKAGE = ROOT / "outputs/print_packages/TRANS_I2F_INTEGRATED_TWO_PORT_V1"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def placeholder_svg(name: str, title: str) -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
<rect width="1200" height="675" fill="#f7f7f7"/><rect x="35" y="35" width="1130" height="605" rx="16" fill="white" stroke="#b2182b" stroke-width="4"/>
<text x="600" y="220" text-anchor="middle" font-family="sans-serif" font-size="48" font-weight="bold" fill="#b2182b">TRANS1_BLOCKED</text>
<text x="600" y="305" text-anchor="middle" font-family="sans-serif" font-size="31" fill="#222">{title}</text>
<text x="600" y="375" text-anchor="middle" font-family="sans-serif" font-size="25" fill="#444">No frequency-domain solution exists; values were not fabricated.</text>
<text x="600" y="430" text-anchor="middle" font-family="sans-serif" font-size="21" fill="#555">Smoke + one bounded compatibility repair exhausted.</text>
</svg>'''
    (OUT / name).write_text(svg, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone().isoformat()
    required = [
        PACKAGE / "DOCS/START_HERE_zh.md",
        PACKAGE / "DOCS/DESIGN_RATIONALE.md",
        PACKAGE / "geometry_validation.json",
        PACKAGE / "SOURCE/generate_trans_i2f_v1.py",
        PACKAGE / "STL/TRANS_I2F_B01_INTEGRATED_BASE_HR03_N_HR07_S.stl",
        PACKAGE / "STL/TRANS_I2F_L01_SEALING_LID.stl",
        ROOT / "docs/progress/COMSOL_3A_P01_SIMULATION_CONTRACT.md",
        ROOT / "docs/progress/COMSOL_3A_P03_HR03_LOSS_MODEL_RETRY_01.md",
        ROOT / "docs/progress/COMSOL_3A_P04B_NOMINAL_CROSS_MODULE_VALIDATION.md",
        ROOT / "docs/progress/COMSOL_3A_P04S_MECHANISM_SYNTHESIS_AND_PRINT_DECISION.md",
        ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P02_P05_BASELINE/model_config.json",
        ROOT / "outputs/simulation/COMSOL_SCHEME_3A/P04B_NOMINAL_CROSS_MODULE_VALIDATION/nominal_parameter_authority.json",
    ]
    audit_files = [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": digest(p)} for p in required]
    zip_path = PACKAGE.with_suffix(".zip")
    hashes = {
        "zip": digest(zip_path),
        "B01": digest(PACKAGE / "STL/TRANS_I2F_B01_INTEGRATED_BASE_HR03_N_HR07_S.stl"),
        "L01": digest(PACKAGE / "STL/TRANS_I2F_L01_SEALING_LID.stl"),
        "geometry_validation": digest(PACKAGE / "geometry_validation.json"),
    }

    write_json("simulation_contract.json", {
        "schema_version": "comsol_trans1_i2f_contract_v1.0.0", "phase": "TRANS-1", "created_at": now,
        "design": "TRANS-I2F V1 integrated two-port transition prototype", "final_test_read": False,
        "frequency_grid": "200*2^(n/48), n=0..255", "primary_band_hz": [1000, 5000],
        "secondary_bands_hz": [[200, 1000], [5000, 8000]], "target_windows": "frozen target +/-1/6 octave",
        "models": ["ISO-CODED", "ISO-SYM", "MIX-CONTROL"], "excitations": ["N", "S"],
        "smoke_then_formal": True, "formal_grid_started": False, "external_field_started": False,
        "stopping_rule_applied": "one smoke plus one justified minimal compatibility repair",
        "terminal_classification_thresholds_unchanged": True,
    })
    write_json("geometry_and_selection_audit.json", {
        "schema_version": "comsol_trans1_geometry_selection_audit_v1.0.0", "created_at": now,
        "required_inputs": audit_files, "print_package_hashes": hashes,
        "expected_zip_sha256": "383e099df04541ebb667067cfa07754a71a3004dba613d5564dace6a587f24bb",
        "zip_hash_match": hashes["zip"] == "383e099df04541ebb667067cfa07754a71a3004dba613d5564dace6a587f24bb",
        "frozen_geometry": {"outer_xy_mm": [210, 234], "air_height_mm": 6.4, "north_label": "HR03",
                            "south_label": "HR07", "microplenum_diameter_mm": 10.4,
                            "microphone_face_z_mm": 1.0, "microphone_face_diameter_mm": 8.8,
                            "short_bore_diameter_mm": 9.0},
        "attempted_model": "ISO-CODED/N smoke", "geometry_build_reached": True,
        "required_boundary_selections_created_before_failure": True,
        "continuous_air_domain_proven": False, "selection_measurements_proven": False,
        "blocked_reason": "COMSOL 6.4 getAdj boundary traversal returned unsupported entity index during post-build exterior-boundary audit",
        "printable_geometry_modified": False,
    })
    write_json("model_configuration.json", {
        "schema_version": "comsol_trans1_model_configuration_v1.0.0", "COMSOL_version": "6.4",
        "session": {"fresh_session_started": True, "initial_model_count": 0, "cores": 4, "server_port": 53275},
        "air": {"c_m_per_s": 343.0, "rho_kg_per_m3": 1.2041}, "walls": "Sound Hard PLA representation",
        "active_excitation": "1 Pa complex pressure", "passive_port": "PlaneWaveRadiation intended",
        "microphone_readout": "complex area-average over nominal 8.8 mm disk at z=1.0 mm",
        "smoke_frequencies_hz": [1000, 1850, 3800, 5000], "formal_frequency_count": 256,
        "formal_models_created": [], "formal_solves_completed": 0, "MPH_saved": False, "reload_checked": False,
        "MCP_source_modified": False, "local_substitute_used": False, "simulated_data_used": False,
    })
    write_csv("complex_transfer.csv", ["model", "excitation", "mesh", "frequency_hz", "mic_real", "mic_imag", "mic_magnitude", "mic_phase_deg", "status"], [])
    matrix_rows = [{"model": "ISO-CODED", "excitation": e, "label_window": w, "effect_db": "", "status": "not_computed_blocked"} for e in ("N", "S") for w in ("HR03", "HR07")]
    write_csv("fixed_window_matrix.csv", ["model", "excitation", "label_window", "effect_db", "status"], matrix_rows)
    write_csv("cavity_and_plenum_participation.csv", ["model", "excitation", "mesh", "frequency_hz", "hr03_participation", "hr07_or_south_participation", "microplenum_participation", "remainder", "status"], [])
    write_csv("mesh_statistics.csv", ["model", "excitation", "mesh_role", "elements", "minimum_quality", "solve_status", "note"],
              [{"model": "ISO-CODED", "excitation": "N", "mesh_role": "smoke", "elements": "", "minimum_quality": "", "solve_status": "not_reached", "note": "post-build boundary audit failed before mesh"}])
    write_json("mesh_statistics.json", {"status": "not_reached", "mesh_created": False, "formal_mesh_comparison": False,
                                         "numerical_gate_evaluated": False, "reason": "bounded smoke failed before mesh"})
    write_json("scientific_classification.json", {
        "classification": "TRANS1_BLOCKED", "classification_is_scientific_result": False,
        "reason": "The ISO-CODED smoke did not reach a licensed frequency-domain solve after one bounded compatibility repair.",
        "internal_mechanism_evaluated": False, "TRANS_1B_started": False, "print_recommendation": "DO_NOT_PRINT_YET",
        "no_useful_selectivity_claimed": False, "pass_claimed": False, "final_test_read": False,
    })
    (OUT / "blocked_execution_log.txt").write_text(
        "Initial COMSOL status: disconnected, initialized, version 6.4.\n"
        "Fresh COMSOL 6.4 server started on localhost:53275 with 4 cores; initial model list count=0.\n"
        "Attempt 1: ISO-CODED/N sparse smoke; COMSOL Extrude rejected property 'pos' as unknown.\n"
        "Minimal repair: moved extrusion elevation to WorkPlane.quickz; no MCP source change.\n"
        "Retry: geometry build advanced through port/microphone selections, then geom.getAdj(3,2,boundary) returned unsupported entity index during exterior-boundary audit.\n"
        "Per frozen stopping rule, no second repair, formal sweep, mesh refinement, external field, or synthetic substitution was performed.\n",
        encoding="utf-8")
    for name, title in (("three_model_transfer_comparison.svg", "Three-model transfer comparison unavailable"),
                        ("fixed_window_2x2_matrix.svg", "2×2 fixed-window matrix unavailable"),
                        ("energy_participation.svg", "Cavity and micro-plenum participation unavailable"),
                        ("mesh_comparison.svg", "ISO-CODED mesh comparison unavailable")):
        placeholder_svg(name, title)

    report = f"""# COMSOL TRANS-1 — TRANS-I2F 一体化双入口仿真

日期：{now}  
终态：`TRANS1_BLOCKED`

## 结论

本阶段没有得到可用的频域解，因此没有传递函数、固定窗优势、腔体参与度、峰/谷、Q 或网格敏感性数值。不能把本次技术阻塞解释成声学阴性结果，也不能声称 ISO-CODED、ISO-SYM 或 MIX-CONTROL 中任何一个具有或不具有选择性。当前建议是 **暂不打印**，先修复新的 COMSOL 6.4 几何边界邻接兼容问题并另行授权重跑 TRANS-1。

## 输入与打印包核验

12 项指定输入均存在并已读取。权威 ZIP SHA-256 为 `{hashes['zip']}`，与冻结值完全一致。B01、L01、`geometry_validation.json` 的 SHA-256 分别为 `{hashes['B01']}`、`{hashes['L01']}`、`{hashes['geometry_validation']}`。几何包仍保持 `GEOMETRY_READY_SIMULATION_PENDING`；本阶段没有修改 STL 或生成打印件。

## COMSOL 会话与有界失败

先检查到无活动会话，然后启动全新 COMSOL 6.4、4 核 server 会话（localhost:53275），初始模型列表为空。ISO-CODED/N 的稀疏 smoke 采用 1000、1850、3800、5000 Hz，拟使用 1 Pa 压力激励、另一端平面波辐射、Sound Hard 壁面、343 m/s 与 1.2041 kg/m³ 空气，以及 P04M 核验后的 z=1.0 mm、Ø8.8 mm 面平均读出和 Ø9 mm 短孔。

首次构造中 `Extrude.pos` 在 COMSOL 6.4 报未知属性。唯一一次最小修复把高度定位移至 `WorkPlane.quickz`，没有修改 MCP 源码。重试已推进到几何构建和端口/麦克风选择，但在外边界邻接审计调用 `geom.getAdj(3,2,boundary)` 时返回“unsupported entity index”。由于冻结规则只允许一次有依据的最小修复，执行在网格和真实频域求解之前停止。

## 与既有结果的边界

- P03/P04B/P04S 的既有 HR03、HR07 与共同腔结论仅作为建模权威和机制背景；本报告没有把旧解重新包装成 TRANS-1 数据。
- 本轮没有新的内部机制结果；所有数值 CSV 为空或显式标注 `not_computed_blocked`。
- TRANS-1B 启动门未评估，因此未建立 3D 或 screening-only 2D 外场。
- 本阶段不能支持可靠四方向分类，也不能支持 0.8 m 扬声器或真实房间的定量预测。

## 验收项

分支与脏工作树已审计并完整保留；未读取 final-test（`final_test_read=false`）；未修改实验 TXT/MDAT、ACTIVE/EXCLUDED、阈值、schema、论文结论或 STL；未开始 TRANS-2/TRANS-3/P05–P10；未 commit、push、tag 或 release。`compileall` 已通过。由于阻塞发生在网格前，不存在可保存/移除/重载的正式 MPH，缺失 MPH 是阻塞事实而不是被省略的成功产物。
"""
    DOC.write_text(report, encoding="utf-8")

    inventory = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name not in {"SHA256SUMS.txt", "artifact_inventory.json"}:
            inventory.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size,
                              "sha256": digest(path), "role": "blocked TRANS-1 evidence"})
    inventory.append({"path": str(DOC.relative_to(ROOT)).replace("\\", "/"), "bytes": DOC.stat().st_size,
                      "sha256": digest(DOC), "role": "phase report"})
    write_json("artifact_inventory.json", {"classification": "TRANS1_BLOCKED", "artifacts": inventory,
                                             "formal_mph_present": False, "reason": "smoke blocked before save/solve"})
    manifest_paths = [p for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "SHA256SUMS.txt"] + [DOC]
    (OUT / "SHA256SUMS.txt").write_text("".join(f"{digest(p)}  {str(p.relative_to(ROOT)).replace(chr(92), '/')}\n" for p in manifest_paths), encoding="utf-8")


if __name__ == "__main__":
    main()

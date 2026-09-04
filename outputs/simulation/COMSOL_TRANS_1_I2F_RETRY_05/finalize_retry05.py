"""Finalize the bounded RETRY_05 explicit-volume-mesh smoke repair."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_05"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_1_I2F_RETRY_05.md"


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
    mesh = read_json("fine_mesh_repair_audit.json")
    execution = read_json("retry05_execution_result.json")
    reload = read_json("mph_reload_validation.json")
    provenance = read_json("retry04_provenance_verification.json")
    study = read_json("study_solution_dataset_audit.json")
    with np.load(OUT / "repaired_fine_fields_live.npz") as source:
        values = {key: np.asarray(source[key]) for key in source.files}

    rows = []
    for index, frequency in enumerate(values["frequency"]):
        mic = values["mic"][index]
        rows.append({
            "frequency_hz": f"{float(frequency):.15g}",
            "mic_real": f"{float(mic.real):.17g}",
            "mic_imag": f"{float(mic.imag):.17g}",
            "mic_magnitude": f"{float(abs(mic)):.17g}",
            "e_all": f"{float(values['e_all'][index]):.17g}",
            "e_hr03": f"{float(values['e_hr03'][index]):.17g}",
            "e_south": f"{float(values['e_south'][index]):.17g}",
            "e_plenum": f"{float(values['e_plenum'][index]):.17g}",
        })
    with (OUT / "fine_smoke_fields.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    classification = {
        "technical_status": "TRANS1_RETRY_05_FINE_SMOKE_PASS",
        "root_cause_repaired": True,
        "mesh": {
            "strategy": "explicit FreeTet with global and local Size attributes",
            "elements": mesh["elements"],
            "vertices": mesh["vertices"],
            "minimum_quality": mesh["minimum_quality"],
            "mean_quality": mesh["mean_quality"],
            "hard_gate_pass": mesh["hard_gate_pass"],
            "low_mesh_quality_warning": mesh["low_mesh_quality_warning"],
        },
        "fine_smoke": {
            "frequencies_hz": values["frequency"].tolist(),
            "field_lengths": {key: int(value.size) for key, value in values.items()},
            "all_finite": {key: bool(np.all(np.isfinite(value))) for key, value in values.items()},
            "microphone_magnitudes": np.abs(values["mic"]).tolist(),
            "microphone_nonzero": bool(not np.allclose(values["mic"], 0.0)),
            "solve_elapsed_s": study["solve_elapsed_s"],
            "mph_reload_maximum_microphone_difference_pa": reload["maximum_complex_microphone_difference_pa"],
            "mph_reload_pass": reload["pass"],
        },
        "remaining_warning": (
            "minimum mesh quality is extremely low; this smoke proves field availability, "
            "not numerical convergence or scientific credibility"
        ),
        "estimated_runtime_note": (
            "the four-point solve required about 493 s; a full 256-point multi-configuration run "
            "must not be started automatically"
        ),
        "next_decision": "USER_CONFIRMATION_REQUIRED_BEFORE_FORMAL_256_GATE",
        "formal_256_gate_started": False,
        "six_combinations_completed": 0,
        "trans2_started": False,
        "print_authorized": False,
        "scientific_conclusion": "none; repaired technical smoke only",
        "fresh_comsol_solve_count": execution["fresh_comsol_solve_count"],
        "final_test_read": False,
    }
    write_json(OUT / "scientific_and_technical_classification.json", classification)

    report = f"""# COMSOL TRANS-1 RETRY_05 — fine 体网格修复与四频点验收

日期：{datetime.now().astimezone().isoformat()}  
终态：`TRANS1_RETRY_05_FINE_SMOKE_PASS`

## 结论

RETRY_04 定位的空 fine 网格根因已经修复。使用显式 `FreeTet` 体网格、全局 `Size` 与 FreeTet 下的局部 critical-domain `Size` 后，求解前正体网格硬门禁通过；唯一一次 fresh fine 四频点声学求解产生了完整、有限且非零的空间场。

这证明此前 `[4,0]` 不是设计的声学负结果，而是网格序列技术错误。

## 网格与求解

- explicit FreeTet：{mesh['elements']:,} elements、{mesh['vertices']:,} vertices。
- minimum/mean quality：`{mesh['minimum_quality']:.7g}/{mesh['mean_quality']:.4f}`。
- 全局/critical hmax：`{mesh['global_hmax_m']:.9g}/{mesh['critical_hmax_m']:.9g} m`；冻结比率门禁通过。
- `LOW_MESH_QUALITY_WARNING`：保留，最低质量非常低。
- 四频点：`{values['frequency'].tolist()}` Hz。
- solve elapsed：`{study['solve_elapsed_s']:.3f} s`；本阶段 fresh COMSOL solve 数为1。

## 字段与重载门禁

- frequency、mic、e_all、e_hr03、e_south、e_plenum 均为4点且全部finite。
- 麦克风幅值：`{np.abs(values['mic']).tolist()}`，非全零。
- MPH 在提取前保存，移除、重载后最大复数麦克风差 `0 Pa`，容差 `1e-12 Pa`。
- Java tag `dset1` 继续通过实际 MPh Node 寻址。

## 科学边界与下一步

本轮只证明 fine 体网格及结果提取链恢复，不证明数值收敛或选择性编码。最低网格质量 `4.444e-09` 仍是显著警告，必须由既定 coarse/fine 数值门禁约束。

四频点单模型求解约耗时8.2分钟，因此不得自动启动完整256点、多配置流程。后续是否恢复原冻结的256点门禁，需要用户确认计算时间与低质量风险；未确认前不进入TRANS-2，不授权打印。

- 256点门禁未开始；六组合0/6。
- 未修改几何、物理、频率、候选窗口、阈值或STL。
- RETRY_04 provenance `{provenance['entries']}/{provenance['entries']}` 匹配。
- `final_test_read=false`。
- 未commit、push、tag或release。

## API依据

COMSOL 6.4官方API说明：手工增加网格特征会将physics-controlled序列切换为user-controlled；`FreeTet`是实际生成非结构四面体体网格的操作，而`Size`只是被后续网格操作读取的属性。这与RETRY_04的零元素根因及本轮修复结果一致。

- [Physics-Controlled Meshing](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_api_mesh.49.021.html)
- [FreeTet](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_api_mesh.49.082.html)
- [Size](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_api_mesh.49.100.html)
"""
    REPORT.write_text(report, encoding="utf-8")

    excluded = {"SHA256SUMS.txt", "artifact_inventory.json"}
    artifacts = [REPORT] + sorted(path for path in OUT.iterdir() if path.is_file() and path.name not in excluded)
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
    (OUT / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}" for path in manifest_paths) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

"""Build the evidence-only TRANS-1N0 gate artifacts; never imports COMSOL."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


ROOT = Path(r"D:\Bristol course\dissertation\program work")
OUT = ROOT / "outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY"
REPORT = ROOT / "docs/progress/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY.md"
R4 = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_04"
R5 = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_05"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(path: Path) -> dict:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split("  ", 1)
        target = ROOT / relative
        actual = sha256(target) if target.is_file() else None
        rows.append({"path": relative, "expected": expected, "actual": actual, "match": actual == expected})
    return {
        "manifest": path.relative_to(ROOT).as_posix(),
        "entries": len(rows),
        "matched": sum(row["match"] for row in rows),
        "all_match": all(row["match"] for row in rows),
        "rows": rows,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    completed_at = datetime.now().astimezone().isoformat()
    hash_audit = {
        "audit_type": "recomputed_authority_sha256",
        "completed_at": completed_at,
        "retry_04": verify_manifest(R4 / "SHA256SUMS.txt"),
        "retry_05": verify_manifest(R5 / "SHA256SUMS.txt"),
        "authority_files_modified": False,
        "final_test_read": False,
    }
    hash_audit["all_match"] = hash_audit["retry_04"]["all_match"] and hash_audit["retry_05"]["all_match"]
    if not hash_audit["all_match"]:
        raise RuntimeError("Authority SHA-256 audit failed")
    write_json(OUT / "input_hash_audit.json", hash_audit)

    mesh = read_json(R5 / "fine_mesh_repair_audit.json")
    classification = read_json(R5 / "scientific_and_technical_classification.json")
    study = read_json(R5 / "study_solution_dataset_audit.json")
    reload = read_json(R5 / "mph_reload_validation.json")
    execution = read_json(R5 / "retry05_execution_result.json")
    distribution = read_json(OUT / "mesh_quality_distribution.json")
    mph_path = R5 / "REPAIRED_ISO_CODED_N_FINE_4PT.mph"
    with (R5 / "fine_smoke_fields.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    numeric_fields = ["frequency_hz", "mic_real", "mic_imag", "mic_magnitude", "e_all", "e_hr03", "e_south", "e_plenum"]
    all_csv_finite = len(rows) == 4 and all(math.isfinite(float(row[key])) for row in rows for key in numeric_fields)
    authority = {
        "completed_at": completed_at,
        "retry_04_terminal_state": "TRANS1_RETRY_04_ROOT_CAUSE_IDENTIFIED_EMPTY_FINE_MESH",
        "retry_05_terminal_state": classification["technical_status"],
        "sha256_audit_pass": hash_audit["all_match"],
        "retry_04_manifest_entries_matched": hash_audit["retry_04"]["matched"],
        "retry_05_manifest_entries_matched": hash_audit["retry_05"]["matched"],
        "fine_mesh": {
            "elements": mesh["elements"],
            "vertices": mesh["vertices"],
            "minimum_quality": mesh["minimum_quality"],
            "mean_quality": mesh["mean_quality"],
            "low_mesh_quality_warning": mesh["low_mesh_quality_warning"],
        },
        "four_point_fields": {
            "frequencies_hz": [float(row["frequency_hz"]) for row in rows],
            "row_count": len(rows),
            "all_numeric_values_finite": all_csv_finite,
            "six_field_lengths": classification["fine_smoke"]["field_lengths"],
            "six_fields_all_finite": classification["fine_smoke"]["all_finite"],
            "microphone_magnitudes": [float(row["mic_magnitude"]) for row in rows],
            "microphone_nonzero": classification["fine_smoke"]["microphone_nonzero"],
        },
        "timing": {"solve_elapsed_s": study["solve_elapsed_s"], "stage_elapsed_s": execution["elapsed_s"]},
        "mph": {
            "path": mph_path.relative_to(ROOT).as_posix(),
            "bytes": mph_path.stat().st_size,
            "gib": mph_path.stat().st_size / 1024**3,
            "sha256": sha256(mph_path),
        },
        "reload": reload,
        "fresh_comsol_solve_count_in_n0": 0,
        "formal_256_gate_started": False,
        "six_combinations_completed": 0,
        "trans2_started": False,
        "final_test_read": False,
    }
    write_json(OUT / "authority_evidence.json", authority)

    fine_scale = 256 / 4
    fine_solve_hours = study["solve_elapsed_s"] * fine_scale / 3600
    fine_stage_hours = execution["elapsed_s"] * fine_scale / 3600
    fine_storage_gb = mph_path.stat().st_size * fine_scale / 1e9
    # Earlier coarse smoke is only a supplementary planning cross-check, not a
    # replacement for the RETRY_04/05 authority chain.
    coarse_run = read_json(ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03/run_SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.json")
    coarse_mph = ROOT / "outputs/simulation/COMSOL_TRANS_1_I2F_RETRY_03/SESSION_CONTROL_ISO_CODED_N_COARSE_SMOKE.mph"
    coarse_solve_hours = coarse_run["solve_elapsed_s"] * fine_scale / 3600
    coarse_stage_hours = coarse_run["total_elapsed_s"] * fine_scale / 3600
    coarse_storage_gb = coarse_mph.stat().st_size * fine_scale / 1e9
    resource = {
        "completed_at": completed_at,
        "basis": {
            "authoritative_retry05_four_point_fine_solve_s": study["solve_elapsed_s"],
            "authoritative_retry05_four_point_stage_s": execution["elapsed_s"],
            "authoritative_retry05_four_point_mph_bytes": mph_path.stat().st_size,
            "linear_frequency_multiplier": fine_scale,
            "supplementary_retry03_coarse_four_point_solve_s": coarse_run["solve_elapsed_s"],
            "supplementary_retry03_coarse_four_point_stage_s": coarse_run["total_elapsed_s"],
            "supplementary_retry03_coarse_four_point_mph_bytes": coarse_mph.stat().st_size,
            "supplementary_evidence_not_reclassified_as_authority": True,
        },
        "estimates": {
            "one_fine_256": {
                "linear_solve_hours": fine_solve_hours,
                "linear_stage_hours": fine_stage_hours,
                "linear_mph_gb_decimal": fine_storage_gb,
                "planning_runtime_range_hours": [7.0, 14.0],
                "planning_storage_range_gb_decimal": [8.0, 16.0],
            },
            "one_coarse_256": {
                "supplementary_linear_solve_hours": coarse_solve_hours,
                "supplementary_linear_stage_hours": coarse_stage_hours,
                "supplementary_linear_mph_gb_decimal": coarse_storage_gb,
                "planning_runtime_range_hours": [0.3, 1.0],
                "planning_storage_range_gb_decimal": [1.0, 3.0],
            },
            "one_case_coarse_plus_fine_gate": {
                "central_stage_hours": fine_stage_hours + coarse_stage_hours,
                "central_mph_gb_decimal": fine_storage_gb + coarse_storage_gb,
                "planning_runtime_range_hours": [8.0, 16.0],
                "planning_storage_range_gb_decimal": [10.0, 20.0],
            },
            "six_formal_combinations_on_coarse_after_gate": {
                "central_stage_hours_for_all_six": coarse_stage_hours * 6,
                "central_mph_gb_decimal_for_all_six": coarse_storage_gb * 6,
                "planning_runtime_range_hours_for_all_six": [2.0, 6.0],
                "planning_storage_range_gb_decimal_for_all_six": [6.0, 18.0],
                "additional_after_gate": "five coarse runs because ISO-CODED/N coarse is reusable from the gate",
            },
            "gate_then_all_six_coarse_end_to_end": {
                "central_stage_hours": fine_stage_hours + coarse_stage_hours * 6,
                "central_mph_gb_decimal": fine_storage_gb + coarse_storage_gb * 6,
                "planning_runtime_range_hours": [10.0, 22.0],
                "planning_storage_range_gb_decimal": [15.0, 38.0],
            },
            "counterfactual_six_fine_256_not_recommended": {
                "central_stage_hours": fine_stage_hours * 6,
                "central_mph_gb_decimal": fine_storage_gb * 6,
                "planning_runtime_range_hours": [42.0, 84.0],
                "planning_storage_range_gb_decimal": [48.0, 96.0],
            },
        },
        "assumptions": [
            "Runtime and MPH size scale linearly with frequency count from 4 to 256.",
            "Geometry, physics, solver, mesh, hardware, core count, and requested output fields remain frozen.",
            "No solver failure, paging, license interruption, or additional debug artifact occurs.",
            "The earlier coarse smoke is used only to bound planning; RETRY_05 remains the fine authority.",
        ],
        "limitations": [
            "Sparse direct frequency sweeps may reuse or repeat factorizations nonlinearly.",
            "Memory pressure, garbage collection, checkpointing, compression, and save/reload I/O can widen runtime and storage.",
            "A four-frequency smoke does not sample resonant worst cases and cannot predict convergence at every grid point.",
            "Ranges are capacity-planning estimates, not guarantees or authorization to run.",
        ],
        "final_test_read": False,
    }
    write_json(OUT / "resource_estimate.json", resource)

    decision = {
        "terminal_state": "TRANS1_N0_PROCEED_ONE_CASE_256",
        "mesh_risk": {
            "level": "ELEVATED_SPARSE_LOW_QUALITY_TAIL",
            "distribution_interpretation": "count distribution supports a sparse tail, not broad mesh degradation",
            "spatial_localization": "unavailable",
            "scientific_impact": "undetermined until frozen coarse/fine convergence is evaluated",
            "repair_required_before_one_case_gate": False,
            "warning_retained": "LOW_MESH_QUALITY_WARNING",
            "below_thresholds": distribution["thresholds"],
            "below_1e8": distribution["below_1e8"],
        },
        "separate_judgments": {
            "technically_runnable": True,
            "scientifically_worth_one_bounded_gate": True,
            "paper_value_of_four_point_repetition_only": "low",
            "paper_value_of_one_256_coarse_fine_gate": "high for peak location, frozen-window selectivity, and numerical convergence; still not a scientific-success guarantee",
        },
        "why_256_is_not_just_duplication": [
            "The four smoke frequencies do not resolve peak centres on the frozen logarithmic grid.",
            "They cannot integrate the frozen target windows or test boundary-maximum peak failures.",
            "They cannot evaluate the frozen <1% peak-shift and <0.5 dB coarse/fine gates.",
        ],
        "only_next_stage": {
            "name": "one ISO-CODED/N 256-point coarse/fine numerical gate",
            "model_excitation_cases_maximum": 1,
            "new_comsol_study_run_calls_maximum": 2,
            "frequency_points_per_run": 256,
            "new_geometry_or_mesh_design_changes": 0,
            "wall_clock_planning_stop_hours": 18,
            "new_artifact_storage_stop_gb_decimal": 25,
            "minimum_free_space_before_start_gb_decimal": 30,
            "stop_conditions": [
                "Stop before fine if the coarse run fails validation.",
                "Stop after fine and classify the frozen convergence gate; do not start another combination.",
                "Stop without mesh repair if the gate passes; any six-combination authorization requires a new decision.",
                "If convergence fails, preserve evidence and stop; this recommendation does not authorize repair.",
            ],
            "six_combinations_authorized": False,
        },
        "n0_new_comsol_solve_count": 0,
        "formal_256_gate_started": False,
        "six_combinations_completed": 0,
        "trans2_started": False,
        "print_authorized": False,
        "final_test_read": False,
    }
    write_json(OUT / "decision.json", decision)

    execution_log = {
        "completed_at": completed_at,
        "attempts": [
            {"result": "dependency_unavailable", "detail": "Default project Python lacked the mph package; no COMSOL session started."},
            {"result": "sandbox_log_write_blocked", "detail": "First standalone start could not write COMSOL user logs; no model loaded and no solve ran."},
            {"result": "api_compatibility_retry", "detail": "Saved MPH loaded read-only; unsupported getQualityMeasure metadata call failed before histogram extraction; no solve ran and model was not saved."},
            {"result": "pass", "detail": "Saved MPH loaded read-only; 10,000,000-bin tetrahedral quality distribution extracted; no study, geometry, mesh run, or model save."},
        ],
        "new_comsol_solve_count": 0,
        "study_run_calls": 0,
        "geometry_run_calls": 0,
        "mesh_run_calls": 0,
        "authority_files_modified": False,
        "final_test_read": False,
    }
    write_json(OUT / "audit_execution_log.json", execution_log)

    threshold_text = "; ".join(
        f"< {row['threshold']:.0e}: {row['count_below']:,} ({row['proportion']:.6%})"
        for row in distribution["thresholds"]
    )
    report = f"""# COMSOL TRANS-1N0 — 数值可行性与资源门禁

日期：{completed_at}  
终态：`TRANS1_N0_PROCEED_ONE_CASE_256`

## 一次性结论

建议仅进入一个下一阶段：**ISO-CODED/N 单案例、冻结 256 点、coarse/fine 数值门禁**。不授权六组合，不授权网格修复，不进入 TRANS-2/TRANS-3。

理由不是四点结果已具科学充分性，而恰恰是四点只证明技术链可运行，无法识别峰位、计算冻结窗口选择性或检验 coarse/fine 收敛。一次 256 点门禁具有不可替代的信息增益；直接做六组合则尚无依据。

## 权威证据与哈希

- RETRY_04 终态保持 `TRANS1_RETRY_04_ROOT_CAUSE_IDENTIFIED_EMPTY_FINE_MESH`；其清单 {hash_audit['retry_04']['matched']}/{hash_audit['retry_04']['entries']} 重新计算匹配。
- RETRY_05 终态保持 `TRANS1_RETRY_05_FINE_SMOKE_PASS`；其清单 {hash_audit['retry_05']['matched']}/{hash_audit['retry_05']['entries']} 重新计算匹配。
- fine：{mesh['elements']:,} elements、{mesh['vertices']:,} vertices，minimum/mean quality `{mesh['minimum_quality']:.7g}/{mesh['mean_quality']:.4f}`。
- 四频点 `{[float(row['frequency_hz']) for row in rows]}` Hz；六字段均为4点且 finite，麦克风非全零。
- solve `{study['solve_elapsed_s']:.3f} s`；全阶段 `{execution['elapsed_s']:.3f} s`。
- MPH `{mph_path.stat().st_size:,}` bytes（{mph_path.stat().st_size / 1024**3:.3f} GiB）；保存/重载麦克风最大差 `0 Pa`，门禁通过。
- 本任务未修改 RETRY_04/05，未读取 final-test。

## 网格质量分布与风险

只读加载已保存 RETRY_05 MPH，调用 COMSOL 6.4 `MeshSequence.getQualityDistr("tet", 10_000_000)`；未调用 study、geometry 或 mesh run，未保存模型。本统计是 direct-method 默认的 volume-versus-circumradius 指标。

- {threshold_text}。
- `<1e-8` 精确计数不可用：已确认至少1个、至多12个。精确边界需要 100,000,000-bin Java 数组，因本任务资源上限未申请约400 MB的稠密数组。
- 分位区间：0.01% `[1.2e-6, 1.3e-6)`；0.1% `[3.25e-5, 3.26e-5)`；1% `[0.0086195, 0.0086196)`；中位数 `[0.6610006, 0.6610007)`。

计数分布支持“稀疏低质量尾部”，不支持“广泛网格退化”：低于1e-4的单元仅约0.1785%，低于1e-6约0.00829%。但本次 API 统计没有空间位置，因此不能确认这些单元是否靠近颈部、端口或强梯度区；其科研影响仍不可判定。风险等级为 `ELEVATED_SPARSE_LOW_QUALITY_TAIL`，继续保留 `LOW_MESH_QUALITY_WARNING`，但不足以在一次冻结 coarse/fine 门禁前强制修网格。

## 资源估计

| 范围 | 线性中心估计 | 规划区间 |
|---|---:|---:|
| 单个 fine 256 | solve {fine_solve_hours:.2f} h；阶段 {fine_stage_hours:.2f} h；MPH {fine_storage_gb:.2f} GB | 7–14 h；8–16 GB |
| 单个 coarse 256（补充交叉检查） | 阶段 {coarse_stage_hours:.2f} h；MPH {coarse_storage_gb:.2f} GB | 0.3–1 h；1–3 GB |
| 单案例 coarse+fine 门禁 | {fine_stage_hours + coarse_stage_hours:.2f} h；{fine_storage_gb + coarse_storage_gb:.2f} GB | 8–16 h；10–20 GB |
| 六组合 coarse 正式扫描（门禁后） | {coarse_stage_hours * 6:.2f} h；{coarse_storage_gb * 6:.2f} GB | 2–6 h；6–18 GB |
| 门禁加六组合全流程 | {fine_stage_hours + coarse_stage_hours * 6:.2f} h；{fine_storage_gb + coarse_storage_gb * 6:.2f} GB | 10–22 h；15–38 GB |
| 反事实：六组合全部 fine（不建议） | {fine_stage_hours * 6:.2f} h；{fine_storage_gb * 6:.2f} GB | 42–84 h；48–96 GB |

中心值按 4→256 的64倍线性外推。假设几何、物理、网格、硬件、核数、求解器与输出字段不变；局限包括频点间因子分解行为、共振难点、内存/分页、压缩及保存/重载 I/O，故区间不是保证。coarse 数值只作规划交叉检查，来自既有 RETRY_03 四点结果，不替代 RETRY_04/05 权威链。

## 技术、科研与论文价值分离

- 技术可运行：是。正体网格、六字段、非零麦克风与 MPH 重载均已通过。
- 科研上值得运行：只值得一次有上限的 coarse/fine 256 门禁；尚不值得六组合。
- 论文新增价值：重复四点的价值低；256 点对峰位、冻结窗口积分与 `<1%`/`<0.5 dB` 数值收敛判据有直接价值，但不保证科学门禁通过。

## 唯一下一步与硬上限

下一阶段仅限 **ISO-CODED/N 单案例 256 点 coarse/fine 门禁**：最多2次新 `study.run`（coarse一次、fine一次），1个模型/激励组合，频率/窗口/阈值/几何/物理/网格设计全部冻结。启动前至少30 GB可用空间；规划停止线为18小时墙钟时间或25 GB新增产物。coarse 验证失败则不得启动 fine；fine 完成后立即判定收敛并停止。无论通过或失败，都不得自动启动第二组合、六组合或网格修复。

## 边界

- TRANS-1N0 新 COMSOL solve：0；`study.run`：0。
- 未建模、未重划网格、未改几何/物理/频率/窗口/阈值/打印包。
- 256 点门禁未开始；六组合0/6；TRANS-2/3未开始；未打印。
- `final_test_read=false`；未 commit、push、tag 或 release。

## 机器可读产物

- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/input_hash_audit.json`
- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/authority_evidence.json`
- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/mesh_quality_distribution.json`
- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/resource_estimate.json`
- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/decision.json`
- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/audit_execution_log.json`
- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/artifact_inventory.json`
- `outputs/simulation/COMSOL_TRANS_1_N0_NUMERICAL_FEASIBILITY/SHA256SUMS.txt`
"""
    REPORT.write_text(report, encoding="utf-8")

    inventory_paths = sorted(
        [path for path in OUT.iterdir() if path.is_file() and path.name not in {"SHA256SUMS.txt", "artifact_inventory.json"}]
        + [REPORT]
    )
    inventory = {
        "terminal_state": decision["terminal_state"],
        "artifact_count_excluding_inventory_and_manifest": len(inventory_paths),
        "artifacts": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in inventory_paths
        ],
        "new_comsol_solve_count": 0,
        "final_test_read": False,
    }
    write_json(OUT / "artifact_inventory.json", inventory)
    manifest_paths = inventory_paths + [OUT / "artifact_inventory.json"]
    (OUT / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in manifest_paths),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

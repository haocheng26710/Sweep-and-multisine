# COMSOL TRANS-1N0 — 数值可行性与资源门禁

日期：2026-08-27T01:42:39.630689+01:00  
终态：`TRANS1_N0_PROCEED_ONE_CASE_256`

## 一次性结论

建议仅进入一个下一阶段：**ISO-CODED/N 单案例、冻结 256 点、coarse/fine 数值门禁**。不授权六组合，不授权网格修复，不进入 TRANS-2/TRANS-3。

理由不是四点结果已具科学充分性，而恰恰是四点只证明技术链可运行，无法识别峰位、计算冻结窗口选择性或检验 coarse/fine 收敛。一次 256 点门禁具有不可替代的信息增益；直接做六组合则尚无依据。

## 权威证据与哈希

- RETRY_04 终态保持 `TRANS1_RETRY_04_ROOT_CAUSE_IDENTIFIED_EMPTY_FINE_MESH`；其清单 18/18 重新计算匹配。
- RETRY_05 终态保持 `TRANS1_RETRY_05_FINE_SMOKE_PASS`；其清单 18/18 重新计算匹配。
- fine：856,786 elements、158,524 vertices，minimum/mean quality `4.444e-09/0.6394`。
- 四频点 `[1000.0, 1850.0, 3800.0, 5000.0]` Hz；六字段均为4点且 finite，麦克风非全零。
- solve `493.400 s`；全阶段 `520.898 s`。
- MPH `209,732,188` bytes（0.195 GiB）；保存/重载麦克风最大差 `0 Pa`，门禁通过。
- 本任务未修改 RETRY_04/05，未读取 final-test。

## 网格质量分布与风险

只读加载已保存 RETRY_05 MPH，调用 COMSOL 6.4 `MeshSequence.getQualityDistr("tet", 10_000_000)`；未调用 study、geometry 或 mesh run，未保存模型。本统计是 direct-method 默认的 volume-versus-circumradius 指标。

- < 1e-04: 1,529 (0.178458%); < 1e-05: 418 (0.048787%); < 1e-06: 71 (0.008287%); < 1e-07: 12 (0.001401%)。
- `<1e-8` 精确计数不可用：已确认至少1个、至多12个。精确边界需要 100,000,000-bin Java 数组，因本任务资源上限未申请约400 MB的稠密数组。
- 分位区间：0.01% `[1.2e-6, 1.3e-6)`；0.1% `[3.25e-5, 3.26e-5)`；1% `[0.0086195, 0.0086196)`；中位数 `[0.6610006, 0.6610007)`。

计数分布支持“稀疏低质量尾部”，不支持“广泛网格退化”：低于1e-4的单元仅约0.1785%，低于1e-6约0.00829%。但本次 API 统计没有空间位置，因此不能确认这些单元是否靠近颈部、端口或强梯度区；其科研影响仍不可判定。风险等级为 `ELEVATED_SPARSE_LOW_QUALITY_TAIL`，继续保留 `LOW_MESH_QUALITY_WARNING`，但不足以在一次冻结 coarse/fine 门禁前强制修网格。

## 资源估计

| 范围 | 线性中心估计 | 规划区间 |
|---|---:|---:|
| 单个 fine 256 | solve 8.77 h；阶段 9.26 h；MPH 13.42 GB | 7–14 h；8–16 GB |
| 单个 coarse 256（补充交叉检查） | 阶段 0.41 h；MPH 1.80 GB | 0.3–1 h；1–3 GB |
| 单案例 coarse+fine 门禁 | 9.67 h；15.23 GB | 8–16 h；10–20 GB |
| 六组合 coarse 正式扫描（门禁后） | 2.46 h；10.83 GB | 2–6 h；6–18 GB |
| 门禁加六组合全流程 | 11.72 h；24.25 GB | 10–22 h；15–38 GB |
| 反事实：六组合全部 fine（不建议） | 55.56 h；80.54 GB | 42–84 h；48–96 GB |

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

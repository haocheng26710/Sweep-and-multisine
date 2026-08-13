# 有边界的压力模拟方案

方案版本：`SIM-0 rev-001`

基准研究协议：[`RESEARCH_QUESTION_AND_DECISION_RULES.md`](./RESEARCH_QUESTION_AND_DECISION_RULES.md)，固定版本 `rev-001`

冻结日期：2026-08-13

状态：方案已冻结；`SIM-1` 尚未开始，未生成或运行任何压力模拟

## 1. 目的、资格与不可越过的边界

压力模拟只用于检查：

- 已冻结的研究判定规则能否恢复已知注入效应；
- 是否会把无方向效应或纯响度效应误判为方向信息；
- 当前 32 样本计划面对 `REPOS`、`REASM`、噪声和数据损坏时是否稳定；
- 是否有必要在真实 pilot 前调整样本设计。

所有 SIM-1 结果必须固定标记为：

- `data_origin=simulated`
- `run_purpose=software_validation`
- `scientifically_eligible=false`

这些结果不代表真实装置可行，不得用于论文科学结论，不得用于支持 H1，也不得根据模拟结果修改主研究问题、主指标或放宽成功阈值。模拟只能揭示实现错误、判定规则明显失灵或预先声明的样本设计风险。`final-test` 在 SIM-0、SIM-1 以及任何可能的协议修订中均保持 `sealed`，不得读取。

## 2. 固定研究设计

| 项目 | 冻结定义 |
|---|---|
| 结构 | `U4ENC`、`U4SYM` |
| 方向 | `0°`、`90°`、`180°`、`270°` |
| 重复来源 | `CONT`、`REPOS`、`REASM`；三类不得互换或混合 |
| 主指标 | `G_demeaned` |
| 辅助指标 | `G_raw`、`G_zscore`、同方向 `REASM` 变化、balanced accuracy、macro-F1 |
| 分类验证 | grouped validation；禁止随机拆分同一批技术重复 |
| 默认计划 | 32 个样本 |
| 唯一备用计划 | 64 个样本 |

32 样本是所有六个场景的默认且唯一首轮计划。只有 32 样本计划通过 S0、S1、S2 和 S5 控制要求，而 S3 恢复率落入 `50%–79%`，或预先定义的 S3 `REPOS`/`REASM` 稳定性检查失败时，才允许对 **S3 单独**追加一次 64 样本评估。该评估复用同一组 50 个种子，不允许引入新种子、第三种样本量或第二轮 64 样本评估。

`CONT` 只作为技术重复，不能增加独立科学样本数。独立性与分组边界必须由 session、`REPOS` 和 `REASM` 身份维持。

## 3. 冻结参数语义

下列量是 SIM-1 的软件压力注入参数，不是对真实装置误差的估计，也不是科研阈值：

- `direction_shape_scale_enc/sym`：分别缩放当前已知的 U4ENC/U4SYM 方向相关谱形；`0` 表示没有方向相关谱形。
- `direction_level_offsets_db`：按 `[0°, 90°, 180°, 270°]` 顺序施加、对所有频率相同的标量声级偏移。
- `waveform_noise_std_fs`：相对于满刻度的时域加性高斯噪声标准差。
- `sample_gain_sd_db`：样本级零均值标量增益扰动标准差。
- `repos_shape_sd_db`、`reasm_shape_sd_db`：分别针对同方向 REPOS/REASM 的零均值、平滑谱形扰动标准差；两者必须独立生成和记录。
- 缺 tone 通过 manifest tone 索引指定；drift 使用 signed ppm；clipping 使用明确的连续样本数。不得从最终结果反推注入参数。

SIM-1 如发现当前底层模拟器的单位转换需要修正，只能使实现忠实表达本表，不能改变本表的场景排序、方向效应关系、异常类别、种子或验收阈值。任何无法忠实实现的参数必须使该场景失败并进入人工审计，不得静默替代。

## 4. 固定六场景

所有场景使用第 5 节的固定种子集合。参数中的“低/中/高”均由本节给出的数值定义，不得在运行中调整。

| 场景 | 方向谱形 ENC/SYM | 方向声级偏移 dB | waveform noise std FS | sample gain SD dB | REPOS / REASM shape SD dB | 数据损坏 | 预期结果 |
|---|---:|---|---:|---:|---:|---|---|
| `S0_NULL` | `0 / 0` | `[0, 0, 0, 0]` | `0.00002` | `0.05` | `0.10 / 0.15` | 无 | 不应通过方向效应判定；用于估计假阳性 |
| `S1_LEVEL_ONLY` | `0 / 0` | `[-1.5, -0.5, 0.5, 1.5]` | `0.00002` | `0.05` | `0.10 / 0.15` | 无 | `G_raw` 可变化；demean/z-score 后必须拒绝方向结论 |
| `S2_POSITIVE_CONTROL` | `1.0 / 1.0` | `[0, 0, 0, 0]` | `0.00002` | `0.05` | `0.10 / 0.15` | 无 | 应恢复当前已知的强 U4ENC、弱 U4SYM 方向效应 |
| `S3_MODERATE_REALISTIC` | `0.35 / 1.0` | `[0, 0, 0, 0]` | `0.00050` | `0.35` | `0.50 / 0.75` | 无 | 主要压力场景；评估 32 样本恢复率和重复稳定性 |
| `S4_REASSEMBLY_STRESS` | `0.35 / 1.0` | `[0, 0, 0, 0]` | `0.00050` | `0.35` | `0.50 / 2.00` | 无 | 若 REASM 覆盖方向效应，必须安全判为调整或重新设计 |
| `S5_DATA_QUALITY_STRESS` | `1.0 / 1.0` | `[0, 0, 0, 0]` | `0.00002`（正常样本） | `0.05` | `0.10 / 0.15` | 每个 32 样本 cohort 固定 8 个异常样本，见下文 | QC 应检测或安全降级异常；不得产生科学通过结果 |

`direction_shape_scale_sym=1.0` 使用当前模拟器本来就很弱的 U4SYM 方向项，并不把 U4SYM 设置成与 U4ENC 等强。场景参数只是确定性软件压力定义，“moderate realistic”是场景名称，不表示其数值已经由真实设备校准。

### 4.1 S5 固定异常分配

按 `expected_sample_matrix` 的稳定排序给样本编号 `0–31`，身份来自显式计划而非文件名。每个种子固定使用以下异常槽位：

| 样本索引 | 注入 |
|---:|---|
| 0、1 | 各缺失一个 tone；分别使用 manifest 的首个 tone 和中位 tone |
| 2、3 | `waveform_noise_std_fs=0.015` |
| 4、5 | signed drift 分别为 `+120 ppm`、`-120 ppm`，校正关闭 |
| 6、7 | 连续 clipping 分别为 `16`、`32` 个样本 |

其余 24 个样本采用 S2 的正常设置。检测率分母只包含这 8 个已注入异常样本；每个异常都必须在输入 manifest 中预先登记类型、目标样本、参数和 hash。不得按观察到的输出替换异常样本。

### 4.2 每场景的实际判定规则

每个 scenario-seed run 都先执行 provenance、身份、hash、完整性和 QC 门禁，再计算冻结指标；任何门禁失败都不能被后续指标覆盖。

- `S0_NULL`：若无注入方向效应却被判为“继续原设计”，计为一次错误通过。
- `S1_LEVEL_ONLY`：允许 `G_raw` 显示差异；若 `G_demeaned`/`G_zscore` 仍促成方向效应通过，计为一次错误通过。
- `S2_POSITIVE_CONTROL`：QC/完整性通过，且 `G_demeaned(U4ENC)>1`、高于 U4SYM、normalization 后效应仍保留、方向差异大于 REASM、grouped balanced accuracy 至少 50%，才计为恢复。
- `S3_MODERATE_REALISTIC`：采用与 S2 相同的逐 run 判定，汇总 50 个种子的恢复率；它是决定是否触发唯一 64 样本评估的场景。
- `S4_REASSEMBLY_STRESS`：报告方向差异相对 REASM 的比例及三类决策。当 REASM 大于方向效应时，不得判为“继续原设计”。S4 是诊断性压力场景，不单独替代第 6 节的五项总体验收率。
- `S5_DATA_QUALITY_STRESS`：每个注入异常若被正确识别为 warning/exclude candidate，或因证据不足被明确安全降级且不进入科学通过，计为检测/安全降级；任何异常绕过 QC 并促成科学通过均为失败。

模拟的 50-seed 汇总可以报告 bootstrap 或精确二项式 95% 区间作为软件稳定性描述，但不得冒充真实 pilot 的 95% 科学置信区间，也不得借此改变 rev-001 门槛。物理方向差异指标始终优先于分类准确率。

## 5. 种子、次数和停止规则

固定 seed set ID 为 `sim0-seeds-rev001`。六个场景都使用相同的 50 个整数种子，以便做配对的软件比较：

`2026090101` 至 `2026090150`（含首尾，逐一递增 1）。

SIM-1 在第一次运行任何场景前，必须把上述 50 个值完整写入不可变 `seed_manifest.json`，并由所有 `scenario_manifest.json` 引用其 ID 和 SHA-256。禁止中途挑选、删除、替换或追加种子。

- 基础运行量：`6 × 50 = 300` 个 scenario-seed runs。
- 基础样本处理上限：`300 × 32 = 9,600` 个 measurement instances。
- 唯一可选追加：仅 S3、64 样本、同一组 50 seeds，即额外 `50` runs 和 `3,200` instances。
- 最大总运行量：`350` 个 scenario-seed runs，最多 `12,800` 个 measurement instances。

不得增加场景、种子数量、重复轮次或第三种样本量。触发 64 样本评估后也不得再次调整场景强度或重跑挑选有利结果。

## 6. 模拟验收标准与决策

### 6.1 固定总体标准

- S2 正控制恢复率至少 `90%`；
- S3 中等现实场景通过率至少 `80%`；
- S0 无效场景错误通过率不高于 `10%`；
- S1 纯响度场景在 `G_demeaned` 判定上的错误通过率不高于 `10%`；
- S5 异常样本检测或安全降级率至少 `95%`；
- `final_test_read=false`；
- 每次运行保留配置、seed、输入 hash、输出 hash 和判定结果。

边界值按包含关系执行：90%、80% 和 95% 均算通过；10% 均算通过；S3 的 50% 与 79% 均属于“调整后继续”区间，80% 属于“继续原设计”。

### 6.2 三类结论

**继续原设计**：第 6.1 节所有标准全部通过，且 S4 未暴露出与 rev-001 冲突的 REASM 支配问题。模拟通过只表示可以继续准备真实 pilot，不授予科研资格。

**调整后继续**：S2 正控制通过，但 S3 恢复率为 `50%–79%`，或者 32 样本对 `REPOS`/`REASM` 不稳定。此时只允许运行第 2、5 节预先声明的 S3 64 样本评估，并可提出协议 `rev-002`；不能放宽成功阈值。

**重新检查实现或设计**：出现任一情况即进入该类：

- S2 正控制恢复率低于 90%；
- S0 或 S1 错误通过率超过 10%；
- QC 不能可靠识别或安全降级 S5 异常；
- 结果依赖种子选择；
- S3 恢复率低于 50%；
- 出现数据来源混淆、hash/身份失效或 final-test 泄漏。

若原因是软件实现错误，应修复并建立新的、有记录的软件验证轮次；不得把实现错误解释为结构失败。若原因属于设计，任何 rev-002 都必须遵守基准协议的一次性修订窗口。

## 7. 现有实现能力矩阵

本矩阵来自 SIM-0 对现有模拟器、P8 QC、P2-B、P4、P5 和 UI 32 样本计划能力的只读检查；它不表示场景已运行。

| 能力/场景 | 状态 | 现有证据与 SIM-1 边界 |
|---|---|---|
| 确定性种子与已知 H(f) | 已支持 | `mock_data.py` 已使用 `random_state` 并提供固定 U4ENC/U4SYM transfer |
| 32 样本 CONT/REPOS/REASM 身份计划 | 已支持 | UI 计划与批量模拟流程已有显式 32 样本矩阵及 hash 状态 |
| `G_raw/G_demeaned/G_zscore` 与 REPOS 主比值 | 已支持 | P4 指标核心已有 morphology gain；输入仍须通过显式 scope/P2-B 门禁 |
| grouped balanced accuracy / macro-F1 | 已支持 | P5 支持按 session、REPOS、REASM 留组验证；禁止随机拆分仍须由 SIM-1 固定 scope 强制 |
| `S0_NULL` | 可由现有 FeatureSet 参数表达 | `rank_mode=identical/zero` 可做 FeatureSet 级 null；完整原始 Sweep/Multisine E2E 需要 SIM-1 最小场景注入层把方向谱形缩放为 0 |
| `S1_LEVEL_ONLY` | SIM-1 需要最小新增实现 | 现有 global intercept 不能清晰表达按方向变化、全频恒定的 level-only 效应；需加入显式 direction-level injection，不改分析算法 |
| `S2_POSITIVE_CONTROL` | 已支持 | 当前已知 transfer 已形成强 U4ENC、弱 U4SYM 效应；SIM-1 只需冻结 32 样本编排、50 seeds 和 manifest |
| `S3_MODERATE_REALISTIC` | 可通过部分现有参数实现 | 已有 waveform noise、gain jitter 和 repeat noise；SIM-1 需最小场景层分别记录样本 gain 与 REPOS/REASM 谱形强度 |
| `S4_REASSEMBLY_STRESS` | SIM-1 需要最小新增实现 | 当前 FeatureSet mock 只有全局 repeat-noise scale，CONT/REPOS/REASM 比例固定；需独立配置 REASM 强度 |
| `S5_DATA_QUALITY_STRESS` | 已支持底层注入与 QC | 已有 missing tone、noise、signed drift、clipping、interference 及 P8 QC；SIM-1 需批量异常分配和不可变场景 manifest |
| provenance、hash、不可覆盖输出 | 已支持 | 现有 pipeline/validation bundle 可复用；SIM-1 必须建立专用 scenario/seed/result manifest，不得扫描目录认领输入 |
| 超出冻结边界的自适应搜索 | 不应支持/超出范围 | 禁止增加场景、挑 seed、自动调阈值、第三种样本量、读取 real/final-test 或授予科研/canonical/freeze/deployment 资格 |

SIM-1 的允许新增实现仅限：确定性场景编排器、显式注入参数适配、独立 REPOS/REASM 生成、冻结 manifest/结果汇总与图表。不得修改 P1–P9 数学定义、QC 判定语义、研究协议阈值或 provenance hard gate。

## 8. SIM-1 输出契约

SIM-1 至少生成：

- `scenario_manifest.json`：场景版本、完整参数、32/64 计划、触发条件和基准协议 hash；
- `seed_manifest.json`：50 个预先声明种子及自身 hash；
- 每场景汇总 CSV；
- 每次 scenario-seed run 的结果记录；
- recovery、false-pass、QC detection 汇总；
- 图表；
- 所有输入和输出的 SHA-256 清单；
- 最终中文 Markdown 报告；
- 明确且唯一的“继续原设计、调整后继续或重新检查实现/设计”结论。

每个 run 记录 scenario ID、seed、sample-plan ID、配置/hash、输入清单/hash、输出清单/hash、QC、主辅指标、分类 protocol、判定结果和原因。输出必须稳定排序、拒绝覆盖、可 round-trip，并能从 manifest 重新验证。

目录必须硬隔离，例如：

- 模拟压力验证：`outputs/simulated/software_validation/SIM-1/<run-id>/`
- 未来真实实验：`outputs/real_experiment/<approved-run-id>/`

不得把模拟 artifact 复制、软链接或重新标记到真实实验目录。真实数据替换需要独立的 `real_experiment` provenance、显式批准和新的运行，绝不能复用本计划的科学资格。

## 9. SIM-1 进入门槛

SIM-1 开始前必须同时满足：

1. 本方案和基准协议 rev-001 的文件 hash 已记录；
2. 六场景 schema、50-seed manifest 和 32 样本 identity matrix 已在运行前写定；
3. 场景注入层的最小缺口有测试，且未改变分析算法或门禁；
4. 输出根目录为全新、明确的 simulated/software_validation 目录；
5. final-test 读取路径保持不可达并有审计；
6. 运行计划明确基础 300 runs，以及唯一可能追加的 S3 50 runs。

在这些门槛满足并单独批准前，SIM-1 不得开始。

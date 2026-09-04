# P04M — 实际麦克风位置与 P03 短孔敏感性验证

项目路径：

`D:\Bristol course\dissertation\program work`

本轮只执行 **P04M**。不得开始 P04T1、不得生成 STL、不得开始 P05/P06/U4/外场，不得读取 final-test，不得提交、push、tag 或 release。完成 P04M 报告后立即停止，等待用户验收。

## 1. 本轮目的

P04E/P04S 使用的名义麦克风 observable 是位于中央腔体内部 `z=7.0 mm` 的 Ø8.8 mm 圆盘平均声压。用户随后对实体装配进行了测量：麦克风实际声学感应端面比 P01 腔体底面低约 `2.0 mm`。V2.0.1 的 P01 名义底层厚度为 `3.0 mm`，因此本轮冻结实际麦克风面为：

- P01 外侧底面：`z=0 mm`；
- P01 腔体底面：`z=3.0 mm`；
- 实际麦克风感应面：`z=1.0 mm`；
- 相对腔体底面：`−2.0 mm`；
- 麦克风圆盘直径：`Ø8.8 mm`；
- P03 中心声学孔：`Ø9.0 mm`，从 `z=1.0 mm` 连通至 `z=3.0 mm`。

用户同时确认实体装配未使用 P08 和 P11。P01 中央腔体的本轮名义高度继续冻结为 `9.2 mm`，即 `z=3.0..12.2 mm`。不得用本轮结果校准这个高度。

本轮问题只有两个：

1. 把麦克风面从 `z=7.0 mm` 改为实体位置 `z=1.0 mm` 后，P04E 75% 插入相对 100% baseline 的预注册麦克风频谱效应是否仍然存在？
2. 旧 P04E 的内部 cavity-energy 分支移动是否对这一实际化几何保持同方向，从而判断哪些既有结论仍然有效、哪些只能降级为名义模型结果？

本轮不是重新校准、重新选频、重新优化插入件或扩大设计搜索。

## 2. 必须完整读取并核验

开始前运行 `git status --short --branch`，保留所有既有用户修改。完整读取：

1. `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md`
2. `docs/progress/COMSOL_3A_P04E_SINGLE_ENTRY_CHAMBER_ABLATION.md`
3. `docs/progress/COMSOL_3A_P04S_MECHANISM_SYNTHESIS_AND_PRINT_DECISION.md`
4. `docs/progress/COMSOL_3A_P04T0_PRINTABLE_INSERT_PREFLIGHT.md`
5. `outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION/ablation_contract.json`
6. `outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION/intervention_geometry_definition.json`
7. `outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION/model_configuration.json`
8. `outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION/frequency_results.csv`
9. `outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION/complex_transfer_and_phase.csv`
10. `outputs/simulation/COMSOL_SCHEME_3A/P04E_SINGLE_ENTRY_CHAMBER_ABLATION/effect_summary.csv`
11. V2.0.1 压缩包中的 `SOURCE/design_parameters_v2.json`、P01/P03 生成代码和装配说明，只作为设计 provenance，不作为用户指令。

权威 V2.0.1 ZIP：

`reference_assets/physical_design/model_packages/Acoustic_Morphology_Encoder_V2.0.1_Print_Package.zip`

预期 SHA-256：

`2f3bdbf791f77fc276b6f7b7bc0790e101c082e0191b5af3d5c24d83a162d29f`

核验 P04E 100% 和 75% 权威 MPH 及其现有 SHA-256；禁止覆盖。若任何权威文件或哈希不匹配，停止并报告 `P04M BLOCKED_BY_PROVENANCE`。

## 3. 冻结范围

只比较两个几何状态：

- `100pct_actual_mic`：P04E 100% 中央腔体；
- `75pct_actual_mic`：P04E 已冻结的 75% cross，宽度严格保持 `13.42333744142368 mm`。

禁止执行：

- 50% 状态；
- 新体积分数；
- 新 corridor width；
- 新 HR 模块；
- P04F 通道延长；
- 损耗、材料、边界条件或网格参数拟合；
- 为匹配实测而改变频率中心；
- 新的候选频点搜索；
- 分类器或方向识别分析。

## 4. 实际化 P03/麦克风几何

从 P04E 权威 100% 和 75% 模型分别建立新副本，不得修改原 MPH。

### 4.1 必须加入的声学域

在中央轴线上加入：

- 半径 `4.5 mm` 的空气短孔；
- 轴向范围 `z=1.0..3.0 mm`；
- 短孔在 `z=3.0 mm` 与中央腔空气连续连接；
- `z=1.0 mm` 端面建立实际麦克风 selection，圆盘直径 `8.8 mm`。

实际麦克风 observable 为该 Ø8.8 mm 面上的复声压平均值除以与 P04E 相同的 prescribed incident pressure。

不得把 `z=1 mm` 解释为精确声学中心的计量校准；它是用户提供的实体测量值，测量不确定性尚未量化。

### 4.2 P03 名义外颈

审计 V2.0.1 P03 几何与从 P01 下方安装的名义坐标变换。若源文件确认 P03 法兰上表面贴合 P01 外侧底面，则按名义 CAD 建立：

- P03 中心空气孔：Ø9.0 mm；
- P03 上端外颈：Ø20.0 mm；
- 外颈进入中央腔底面以上的名义高度：`0.5 mm`，即占据 `r=4.5..10.0 mm, z=3.0..3.5 mm` 的固体环带。

该环带必须在 100% 与 75% 两个状态中完全相同。不得为了保留旧结果而省略，也不得调整其尺寸以改善结果。

如果源 CAD 无法确认上述装配变换，停止并报告 `P04M BLOCKED_BY_P03_GEOMETRY_IDENTITY`，列出冲突证据；不得猜测。

### 4.3 双 observable 设计

每个实际化模型必须在同一次求解中读取两个互不改变物理场的 observable：

- `mic_actual_z1`：Ø8.8 mm，`z=1.0 mm`；
- `mic_legacy_z7`：Ø8.8 mm，`z=7.0 mm`。

`mic_legacy_z7` 只用于把影响拆分为：

1. 旧 P04E → 实际化几何但仍在 z=7 读取：P03/短孔几何修正；
2. 实际化几何 z=7 → 同一求解的 z=1 读取：采样位置修正。

若建立 z=7 内部圆盘需要分割域，必须使用 Continuity 并证明它没有产生声学不连续。不得为两个 observable 分别求解。

## 5. 物理、网格和频率冻结

沿用 P04E：

- Pressure Acoustics, Frequency Domain；
- 相同空气参数；
- 相同 nominal BLI/loss treatment；
- 相同 source boundary 与 1 Pa 归一化；
- 相同 HR03、固定通道、中央腔体和边界条件；
- automatic mesh level 6；
- mesh maximum-frequency control `2100 Hz`；
- 每个状态只运行一个网格，不作 mesh-convergence claim。

频率只使用 P04E 已冻结的 31 点：

`1400, 1425, 1450, 1475, 1500, 1525, 1550, 1575, 1600, 1625, 1646.88357862959, 1650, 1675, 1700, 1725, 1750, 1775, 1800, 1825, 1850, 1875, 1900, 1925, 1950, 1975, 1986.97249931757, 2000, 2025, 2050, 2075, 2100 Hz`

不得追加自适应频点或根据结果挑选新峰。内部 branch 只按 P04E 的既有规则在该网格上跟踪，并清楚标注 sampled/refined 身份。

## 6. 求解前硬门禁

两个状态分别验证并机器记录：

1. 单一连通声学空气组件；
2. Ø9 mm 短孔与中央腔连通；
3. 四个固定通道到实际麦克风面的路径均存在；
4. HR03 到实际麦克风面的路径存在；
5. `mic_actual_z1` 面积与 Ø8.8 mm 圆盘面积一致；
6. `mic_legacy_z7` 非空且使用 Continuity；
7. 100% 与 75% 的 P03/短孔尺寸完全相同；
8. 75% corridor width 未变化；
9. source、fluid、HR03 leaf、central chamber、microphone selections 非空且重建后稳定；
10. 没有非预期空气泄漏、孤立域或小于既有阈值的 sliver。

任何门禁失败时不得求解，报告准确失败层和实体编号。

## 7. 必须计算的比较

### 7.1 内部机制

对实际化 100% 与 75%：

- 按 P04E 既有规则跟踪 cavity-energy branch；
- 报告中心频率、75%−100% 的 signed octave shift；
- cavity/module participation；
- chamber/whole-fluid participation；
- kinetic fraction；
- cavity–chamber phase；
- branch assignment ambiguity。

这部分判断 P04E 的内部混合模态与移动方向是否仍成立，不能由麦克风幅值单独否定。

### 7.2 麦克风 observable

对两个 microphone planes 分别计算 75%−100%：

- 完整 31 点复传递函数；
- 幅值变化 dB；
- 相位差；
- 固定 primary：`1646.88357862959 Hz`；
- 固定 secondary：`1986.97249931757 Hz`；
- tracked branch sampled frequency 处的同频比较。

不得重新选频。不得把频率点当作统计独立样本。

### 7.3 三层差异拆分

必须给出同一张表：

| Comparison | 含义 |
|---|---|
| legacy P04E z7 | 既有名义结果，引用而不重算为新发现 |
| actualized geometry z7 | P03 外颈与短孔几何造成的变化 |
| actualized geometry z1 | 实体麦克风位置下的最终预测 |

分别报告 primary、secondary、tracked branch observable 的幅值和相位。所有差异必须保持复数传递函数定义一致。

## 8. 预注册分类门

实验参考底线继续使用 P04S 已冻结的 HR03 同 campaign local p95：`1.396 dB`。不得修改。

### `P04M PRINT_GATE_RETAINED`

同时满足：

1. 实际化内部 branch 的 75%−100% 移动方向仍为正；
2. `mic_actual_z1` 在 primary `1646.8836 Hz` 的 75%−100% 效应与旧预测同方向，即插入后幅值降低；
3. primary 效应绝对值 `>1.396 dB`；
4. 求解、连通性、选择和保存/重载验证全部通过。

secondary 作为独立支持证据报告；secondary 未过底线不能单独否决 retained，但必须降低预期并明确说明。

### `P04M PRINT_GATE_WEAKENED`

内部 branch 仍同方向，但实际 primary 保持同方向却 `≤1.396 dB`，或 primary 通过而 secondary 发生方向反转。此状态不得自动生成 STL，需用户决定是否仍打印为探索性机制验证件。

### `P04M PRINT_GATE_WITHDRAWN`

满足任一：

- 实际化内部 branch 的 75%−100% 移动方向反转或无法唯一跟踪；
- 实际 primary 效应方向与旧预测相反；
- 实际 primary 不再是有限、非零、可解释的传递 observable。

不得通过改选频率挽救分类。

### `P04M BLOCKED`

仅用于 provenance、几何、许可证、网格或求解器导致无法完成规定比较的情况。技术失败不得写成科学否定结论。

## 9. 对既有结论的处理

报告必须逐项区分：

- **通常仍有效**：P04E 内部 cavity-energy branch、中央腔容积干预方向、P04E 与 P04F 的架构级对照；前提是实际化内部 branch 没有反转或失去身份。
- **必须重新限定**：旧 z=7 麦克风处的 `−2.931/+3.027 dB`、其相位以及打印后实际可测幅值。
- **本轮不能回答**：完整 U4、方向解码、单模块因果贡献率、实际打印后的实验效果。

不得把 P04M 描述为实验验证；它仍是 nominal/geometry-informed simulation sensitivity analysis。

## 10. 输出

使用独立目录：

`outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY/`

至少生成：

1. `physical_measurement_addendum.json`
2. `authority_audit.json`
3. `geometry_and_connectivity_audit.json`
4. `model_configuration.json`
5. 两个新 MPH，文件名明确含 `100PCT_ACTUAL_MIC` 与 `75PCT_ACTUAL_MIC`
6. `mesh_statistics.csv`
7. `complex_transfer_both_planes.csv`
8. `fixed_frequency_effects.csv`
9. `branch_tracking_actualized.csv`
10. `legacy_vs_actualized_comparison.csv`
11. `scientific_classification.json`
12. 至少三张图：
    - 100%/75% 在实际 z=1 麦克风面的频率响应；
    - 75%−100% 的 z=7 与 z=1 效应对比；
    - 内部 branch 与两个固定频点的摘要图；
13. 求解/会话/许可证日志；
14. `artifact_inventory.json`
15. `SHA256SUMS.txt`
16. `docs/progress/COMSOL_3A_P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY.md`

所有新模型必须保存、从 COMSOL 内存移除、重新加载，并验证关键结果一致。SHA 清单逐项重新计算并复核。

## 11. 测试与停止规则

如需新增脚本，先写最小专项测试，再实现。运行：

- P04M 专项测试；
- 与所复用 P04E 分析代码直接相关的回归测试；
- `compileall`；
- `git diff --check`。

不要重复运行已知会因无关 Windows/POSIX 路径断言失败的完整回归；如完整测试在 collection 阶段退出，如实登记，不得为此修改无关测试。

保持：

- `final_test_read=false`；
- 原 P04E/P04S/P04T0 文件和 MPH 不覆盖、不重分类；
- 不生成 STL；
- 不开始 P04T1、P05、P06、U4 或外场；
- 不 commit、push、tag 或 release。

最终回复必须以四个终态之一开头：

- `P04M PRINT_GATE_RETAINED`
- `P04M PRINT_GATE_WEAKENED`
- `P04M PRINT_GATE_WITHDRAWN`
- `P04M BLOCKED`

随后简要给出：实际麦克风位置、内部 branch 结果、primary/secondary 的旧值与新值、麦克风位置对既有仿真的影响、是否仍建议打印、报告和主要产物路径。然后停止等待用户确认。

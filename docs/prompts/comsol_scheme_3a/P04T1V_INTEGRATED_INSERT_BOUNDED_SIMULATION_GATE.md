# P04T1V — 集成式 I75/I50P 打印几何有界仿真确认

项目路径：

`D:\Bristol course\dissertation\program work`

本轮只执行 **P04T1V**。目标是在打印或正式实测前，用 P04M 已验证的实际麦克风几何，对 P04T1R 最终实现的 I75 和 I50P 中央腔几何做一次有界确认。不得重新优化尺寸，不得产生第三个候选，不得开始 P04T2 实测分析、P05、P06、完整U4、外场或分类器。

## 1. 首先读取并核验

完整读取：

1. `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md`
2. `docs/progress/COMSOL_3A_P04E_SINGLE_ENTRY_CHAMBER_ABLATION.md`
3. `docs/progress/COMSOL_3A_P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY.md`
4. `docs/progress/COMSOL_3A_P04T1R_INTEGRATED_P09_INSERT_RELEASE.md`
5. `outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY/model_configuration.json`
6. `outputs/simulation/COMSOL_SCHEME_3A/P04M_ACTUAL_MICROPHONE_POSITION_SENSITIVITY/geometry_and_connectivity_audit.json`
7. `outputs/simulation/COMSOL_SCHEME_3A/P04T1R_INTEGRATED_P09_INSERT_RELEASE/design_contract.json`
8. `outputs/simulation/COMSOL_SCHEME_3A/P04T1R_INTEGRATED_P09_INSERT_RELEASE/geometry_and_acoustic_fidelity_audit.json`
9. `outputs/simulation/COMSOL_SCHEME_3A/P04T1R_INTEGRATED_P09_INSERT_RELEASE/mesh_reload_validation.json`
10. `outputs/simulation/COMSOL_SCHEME_3A/P04T1R_INTEGRATED_P09_INSERT_RELEASE/SHA256SUMS.txt`

运行 `git status --short --branch`，保留全部用户修改。逐项复核上述SHA和权威文件。P04T1原松散四叶必须保留为旧provenance，不能覆盖或重新分类。

如果COMSOL MCP不可用，分类为 `P04T1V PRESTART BLOCKED_BY_MCP` 并停止；不得改成本地批处理或伪造结果。

## 2. 冻结的三种状态

使用 P04M 的实际化 S1/HR03 模型：实际麦克风感应面 `z=1.0 mm`、Ø9短孔、P03外颈/凸环、相同空气和BLI参数、相同边界、源、探针及复数传递定义。

- BASE：P04M `100pct_actual_mic` 权威状态；优先复用其已验证结果，不重复求解。
- I75：打印半径17.90 mm，中央十字宽13.52333744142368 mm，P03底部避让 `Ø20.40 × 0.70 mm`，实现空气比例75.8260419817217%。
- I50P：打印半径17.90 mm，中央十字宽8.600000 mm，相同P03避让，实现空气比例54.0587057876302%。

P09集成连接段位于原本已排除的实心对角通道内，不应作为新增空气域。四个0°/90°/180°/270°固定通道必须保持完全开放。不得导入塑料STL替代连通空气域重建。

## 3. 唯一允许的求解

只新建并求解 I75、I50P 两个状态。复用 P04M `model_configuration.json` 中完全相同的频率列表：1400–2100 Hz规则网格和两个冻结landmark `1646.88357862959`、`1986.97249931757 Hz`。不得添加频率、事后加密、改变网格等级、改变损耗或校准参数。

每状态只运行一个 P04M 同级 automatic level 6、2100 Hz control 网格。保存、从内存移除、重新加载并复核几何、网格、结果。若I50P网格或求解失败，记录准确失败层并停止，不进行救援网格或第二套尺寸。

## 4. 必须输出的量

对 BASE、I75、I50P 输出：

- 连通空气域、四条开放固定通道、P03/麦克风路径和named selections审计；
- 网格单元、顶点、最小/平均质量；
- 1400–2100 Hz完整复数传递；
- HR03 neck/cavity、中央腔及whole-fluid能量；
- 通过与P04E/P04M相同的特征和分支链接规则跟踪 cavity branch；
- branch频率、唯一性、assignment margin和ambiguity；
- 1646.88357862959与1986.97249931757 Hz处相对BASE的幅值及相位变化；
- BASE→I75→I50P的branch频率和参与度趋势。

频率点不是统计独立样本，不运行bootstrap、分类器或参数拟合。

## 5. 冻结判断门

### `P04T1V PASS_FOR_PRINT_AND_P04T2`

仅当全部满足：

1. I75/I50P几何、连通、网格、求解、保存重载全部通过；
2. 两状态branch身份唯一且无ambiguity；
3. branch中心满足 `f(BASE) < f(I75) < f(I50P)`；
4. I75在1646.88357862959 Hz仍为负变化、在1986.97249931757 Hz仍为正变化；
5. I75两个冻结landmark的绝对效应均高于1.396 dB实体重复性底线；
6. 没有宽带数值崩溃或非有限结果。

I50P固定landmark的符号不要求与I75相同，因为分支穿越会产生频率重分配；I50P的主要剂量证据是branch中心继续上移，而不是两个固定点幅值单调。

### `P04T1V I75_PASS_I50P_NOT_AUTHORIZED`

I75通过，但I50P求解、网格、branch身份或单调方向失败。此时只允许打印/实测I75，I50P STL保留为未授权探索件，不得用于正式采集。

### `P04T1V PRINT_GATE_FAILED`

I75不满足主要门禁。停止P04T2，不得调参救援。

## 6. 产物

独立目录：

`outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/`

至少生成：

- 两个最终MPH及重载验证；
- `geometry_connectivity_audit.json`；
- `mesh_statistics.csv`；
- `complex_transfer.csv`；
- `branch_tracking.csv`；
- `fixed_landmark_effects.csv`；
- `dose_trend_summary.csv`；
- `scientific_classification.json`；
- 频率响应和branch趋势图；
- `artifact_inventory.json`；
- `SHA256SUMS.txt`；
- `docs/progress/COMSOL_3A_P04T1V_INTEGRATED_INSERT_BOUNDED_GATE.md`。

新增代码时先写最小专项测试。完成后运行专项测试、直接相关回归、`compileall`和`git diff --check`。不要运行无关完整回归，不commit、不push、不创建tag/release。

必须保持 `final_test_read=false`。完成分类后立即停止，等待用户确认；不得自动开始P04T2。


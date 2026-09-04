# P04T3 — P04T1V 仿真与 P04T2 实测的有界对应审计

项目路径：

`D:\Bristol course\dissertation\program work`

## 任务授权

P04T1V 已验收通过，P04T2 实体先导实验也已完成。现在仅执行 **P04T3：既有仿真与既有实测的频谱对应审计**。

本阶段的目标不是继续优化模型，而是回答：

1. 75% 与 50% 中央腔体保留体积在仿真和实测中是否呈现一致的剂量顺序；
2. 仿真预测的局部频谱极性、形状和强度，有多少能在实测中重现；
3. 哪些结果可作为“中央腔体体积调控频谱”的机理证据；
4. 哪些差异说明简化模型不能精确预测实体频谱；
5. 是否值得只进行一次最小回程对照测量，而不是继续扩展仿真或打印新设计。

严格执行本提示词。本轮完成 P04T3 报告后停止，等待用户确认。

## 一、必须首先读取的文件

完整读取：

1. `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md`
2. `docs/progress/COMSOL_3A_P04T1V_INTEGRATED_INSERT_BOUNDED_GATE.md`
3. `docs/progress/P04T2_INTEGRATED_INSERT_PILOT_RESULTS.md`
4. `outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/scientific_classification.json`
5. `outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/model_configuration.json`
6. `outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/complex_transfer.csv`
7. `outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/fixed_landmark_effects.csv`
8. `outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/dose_trend_summary.csv`
9. `outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/branch_tracking.csv`
10. `outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/SHA256SUMS.txt`
11. `outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/analysis_summary.json`
12. `outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/representative_spectra.csv`
13. `outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/fixed_window_effects.csv`
14. `outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/condition_effects.csv`
15. `outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/repeatability.csv`
16. `outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/repeat_selection.csv`
17. `outputs/real_experiment/research_analysis/P04T2_INTEGRATED_INSERT_PILOT_ANALYSIS/SHA256SUMS.txt`
18. `data/real_experiment/P04T2_INTEGRATED_INSERT_PILOT/metadata/source_manifest.csv`

若以上路径因文件名的轻微差异而无法定位，可在相应的既有阶段目录内只读查找，但不得用其他阶段的数据替代。

## 二、开始前审计

1. 检查当前分支、`git status --short` 和既有用户修改。
2. 不覆盖、不撤销、不重新格式化无关修改。
3. 逐项复核 P04T1V 与 P04T2 的 SHA-256 清单。
4. 确认 P04T2 原始 ZIP 的 SHA-256 为：
   `179b932bae0bb73980cebb8092d2f022ecb3c1e8d333896416076d270eb0c07d`
5. 确认 P04T1V 两个正式模型哈希：
   - I75：`7dffc0860d5c1498d272c6fbdafefba2e209e3e7f4b0c5ea150c54bd1425618f`
   - I50P：`fcba3f5271b5a7b7bd91bbcc86320249ae8207e087facdc55fd1b0ec354f9a87`
6. 如果必要输入缺失、哈希不符、schema 无法可靠解析或状态身份冲突，立即分类为 `P04T3 BLOCKED_INPUT_INTEGRITY`，列出准确问题并停止，不得猜测或重建输入。

## 三、严格边界

本轮必须满足：

- 新 COMSOL 求解次数为 **0**；
- 不启动或修改 COMSOL 模型；
- 不要求 COMSOL MCP 在线；MCP 不可用不构成本阶段阻塞；
- 不重新运行 P04T1V；
- 不修改 P04T1V 或 P04T2 的正式输出；
- 不校准、不拟合、不缩放仿真幅值以贴合实验；
- 不修改几何、材料、损耗、麦克风位置或边界条件；
- 不扩展仿真频带；
- 不做自适应选频、事后追峰或重新定义窗口；
- 不运行分类器；
- 不开始 P04T4、P05、P06、U4、外场或其他阶段；
- 不读取 final-test，始终记录 `final_test_read=false`；
- 不 commit、push、tag 或 release。

本阶段是一次有界的后处理审计，不是新的仿真优化阶段。

## 四、冻结的输入身份

### 4.1 仿真输入

只使用 P04T1V 已冻结的三种状态：

- BASE：中央腔体 100% 保留；
- I75：中央腔体约 75% 保留；
- I50P：中央腔体约 50% 保留。

P04T1V 的正式频率集合为：

- 1400–2100 Hz、规则 25 Hz 网格；
- 加入两个冻结精确频点：
  - `1646.88357862959 Hz`
  - `1986.97249931757 Hz`
- 合计 31 个频率点。

P04T1V 已有内部 branch centre：

- BASE：`1651.3226207504606 Hz`
- I75：`1679.907901564445 Hz`
- I50P：`1729.028012706307 Hz`

这些 branch centre 是仿真内部量，实体麦克风测量并未直接观测该内部模态中心。不得给实验虚构对应 branch centre。

### 4.2 实测输入

只使用 P04T2 的四种已登记条件：

- BASE0 × 6；
- BASE1 × 6；
- I75A × 6；
- I50PA × 6。

主分析沿用 P04T2 已冻结的 4-of-6 选择；同时保留 all-six 敏感性分析。不得重新选择“更符合仿真”的曲线。

BASE0 与 BASE1 是干预前连续获得的两批基线，不得写成干预后的 return control，也不得写成两次独立重新装配。

## 五、频率与量纲对应规则

### 5.1 共同频带

跨域的正式比较仅限仿真已经覆盖的 **1400–2100 Hz** 和 P04T1V 的 31 个冻结频率点。

- 从 P04T2 的冻结处理曲线映射到这 31 个点；
- 优先使用已有完全相同的频点；
- 如需插值，只允许在对数频率坐标上对 dB 值做线性插值；
- 必须在输出中记录每个点是 exact 还是 interpolated；
- 禁止外推；
- 200–4000 Hz 的 P04T2 效应只作为“实验自身的宽频背景”，不得与不存在的仿真数据计算相关性；
- 4000–8000 Hz 本轮不作为跨域证据。

### 5.2 比较量

必须分别分析：

1. **raw effect**：状态减 BASE 的 dB 差；
2. **demeaned shape effect**：在共同 1400–2100 Hz 网格内，对每条状态减 BASE 曲线去除其共同频带均值；
3. 两个冻结精确频点的局部效应；
4. 效应曲线的整体强度范数。

仿真是归一化传递响应，实验包含声源、房间和实体装配的共同响应。因此：

- raw effect 用于固定频点和物理效应大小的直接诊断；
- demeaned shape effect 作为跨域形状对应的主要量；
- 不得通过自由增益、偏移、频率平移、DTW、滤波器拟合或任何参数优化使两者看起来更相似；
- 不得把相关性解释为绝对幅值校准或单部件因果贡献率。

## 六、必须计算的结果

### 6.1 冻结精确频点

对 I75 与 I50P 分别在以下频点比较仿真和实验：

- `1646.88357862959 Hz`
- `1986.97249931757 Hz`

至少输出：

- simulation raw effect dB；
- experimental raw effect dB；
- experimental selected-4 repeat bootstrap 95% CI；
- all-six 点估计；
- 符号是否一致；
- 实验/仿真绝对幅值比；
- 若实验 CI 跨 0，明确标为 `experimental_local_effect_uncertain`，不得称为确认；
- 是否超过 P04T1V 冻结的 `1.396 dB` 绝对效应门槛。

### 6.2 共同频带形状对应

在 31 个共同频率点，对 I75 与 I50P 分别计算：

- raw-effect Pearson；
- raw-effect Spearman；
- raw-effect cosine similarity；
- demeaned-shape Pearson；
- demeaned-shape Spearman；
- demeaned-shape cosine similarity；
- raw RMS mismatch；
- demeaned-shape RMS mismatch；
- 逐点效应极性一致比例；
- 最大正效应与最大负效应的频率位置；
- 仿真与实验的极值频率距离（Hz 和 octave）；
- 频率位置差是否小于 1/12 octave。

频率点只是曲线采样位置，不能当作 31 个独立实验样本。不得对频率点做显著性检验或把频率点作为 bootstrap 单元。

### 6.3 重复与不确定性

不确定性必须以完整重复曲线为单位，并尊重条件结构：

- 复用 P04T2 的 selected-4 规则和固定随机种子；
- 如需重新 bootstrap，只能对完整 repeat 曲线重采样，不能对频率点重采样；
- 至少给出 2000 次 repeat-level bootstrap；
- 对主要相似度和 RMS mismatch 给出 95% CI；
- 进行 selected-4 与 all-six 敏感性比较；
- 不得因某个 repeat 降低仿真相关性而重新排除它；
- 现有技术异常 flag 保留，不改变源数据资格。

### 6.4 剂量顺序

分别在仿真和实验中计算 I75、I50P 相对于 BASE 的：

- common-band raw RMS effect；
- common-band demeaned-shape RMS effect；
- 两个冻结窗口的绝对效应摘要。

回答：

- 仿真是否为 I50P > I75；
- 实验是否为 I50P > I75；
- selected-4 与 all-six 是否给出相同顺序；
- 剂量顺序一致是否只支持“中央腔体体积是有效控制参数”，而不等于精确模型验证。

### 6.5 状态间相似性

分别计算：

- 仿真中 I75 与 I50P effect shape 的 Pearson/cosine；
- 实验中 I75 与 I50P effect shape 的 Pearson/cosine；
- I75 仿真对 I75 实验；
- I50P 仿真对 I50P 实验；
- 交叉错误配对 I75 仿真对 I50P 实验、I50P 仿真对 I75 实验，仅作为辨别性诊断。

如果正确配对并不明显优于错误配对，必须写明模型能解释共享的体积变化趋势，但不能可靠识别具体保留比例的完整频谱条形码。

### 6.6 差异分解

用事实证据区分并记录：

- 剂量顺序一致；
- 固定频点极性一致或不一致；
- 实验局部幅值相对仿真是否被削弱；
- 仿真局部特征是否在实验中变宽或重新分配到相邻/更宽频带；
- 仿真 `mic transfer` 与房间内实体 SPL 测量之间的 observable mismatch；
- 单次装配顺序、无 return control 带来的限制；
- 不能识别的单模块贡献率或精确因果比例。

以上是诊断分类，不允许在本轮通过修改参数消除差异。

## 七、冻结科学分类

必须从以下状态中选择且只能选择一个：

### 7.1 `P04T3 MODEL_CONCORDANT_WITH_LIMITS`

仅当全部满足：

1. 输入身份和哈希审计通过；
2. 实验 selected-4 与 all-six 均保持 I50P > I75 的效应强度顺序；
3. I75 与 I50P 在两个冻结精确频点的实验点估计均与仿真同号；
4. I75 与 I50P 的 common-band demeaned Pearson 和 cosine 均不低于 0.50；
5. 正确状态配对的相似度总体高于两个错误交叉配对；
6. I75 在两个冻结频点的实验绝对效应均超过 1.396 dB，且相应 repeat bootstrap CI 不跨 0；
7. selected-4 与 all-six 不改变以上判断。

### 7.2 `P04T3 REAL_VOLUME_EFFECT_MODEL_LOCALIZATION_MISMATCH`

当真实实验仍支持中央腔体体积的剂量有序效应，但 7.1 任一关键模型对应门槛未通过，例如：

- 局部实验幅值显著低于仿真；
- 固定频点 CI 跨 0；
- common-band shape similarity 不足；
- 极值漂移不小于 1/12 octave；
- 正确状态配对不优于错误配对；
- 仿真局部效应在实验中表现为更宽的频谱重分配。

该分类仍是有价值的科学结果：它表示真实体积控制效应存在，但简化模型不能作为精确实体频谱预测器。

### 7.3 `P04T3 EXPERIMENTAL_EFFECT_NOT_ROBUST`

仅当实验的 I50P > I75 顺序在 selected-4/all-six 间反转，或主要效应不再明显高于 BASE 批次变化，或结论依赖重新挑选 repeat。

### 7.4 `P04T3 BLOCKED_INPUT_INTEGRITY`

仅用于必要文件缺失、哈希不匹配、身份冲突或 schema 无法可靠解析。

不得发明更积极的分类，也不得把 P04T1V 的仿真通过状态直接继承为 P04T3 的模型验证结论。

## 八、P04T3 后续决策规则

本轮只提出决策，不执行新测量。

若分类为 `MODEL_CONCORDANT_WITH_LIMITS`，建议停止 P04 扩展，不再打印，不再补测；把现有证据写入论文。

若分类为 `REAL_VOLUME_EFFECT_MODEL_LOCALIZATION_MISMATCH`，只允许建议以下一次最小实体确认：

1. BASE-C，保持装配，连续测 6 次；
2. I50P-C，仅更换中央插入件，连续测 6 次；
3. BASE-R，恢复 BASE 后连续测 6 次。

共 18 条曲线。其目的仅是建立干预前后 return control，区分插入件效应与时间漂移/装配漂移。

- 不新增 I75；
- 不打印新件；
- 不增加距离、方向或 block 矩阵；
- 不在 P04T3 内实施。

若分类为 `EXPERIMENTAL_EFFECT_NOT_ROBUST`，停止继续以 P04 插入件强化结论，不追加仿真精细化。

## 九、必须生成的产物

创建独立目录：

`outputs/real_experiment/research_analysis/P04T3_EXPERIMENT_SIMULATION_RECONCILIATION/`

至少生成：

1. `authority_audit.json`
2. `common_frequency_mapping.csv`
3. `landmark_sim_experiment_comparison.csv`
4. `common_band_similarity.csv`
5. `dose_order_comparison.csv`
6. `repeat_sensitivity.csv`
7. `state_pairing_similarity.csv`
8. `discrepancy_decomposition.json`
9. `scientific_classification.json`
10. `analysis_summary.json`
11. `artifact_inventory.json`
12. `SHA256SUMS.txt`

生成必要但有限的图：

1. `common_band_effect_overlay.png` 和同名 SVG：I75、I50P 的仿真与实验 demeaned effect 对照；
2. `landmark_observed_vs_simulated.png` 和同名 SVG：两个冻结频点的仿真值、实验值与 repeat bootstrap CI；
3. `dose_order_comparison.png` 和同名 SVG：仿真与实验的 I75/I50P 效应范数顺序；
4. `model_experiment_discrepancy_summary.png`：一张简洁的结论图，区分“支持”“失配”“不可识别”。

不得为了美化结果增加大量重复图。

生成正式报告：

`docs/progress/COMSOL_3A_P04T3_EXPERIMENT_SIMULATION_RECONCILIATION.md`

并只更新：

`docs/progress/INDEX.md`

## 十、报告必须明确回答

1. 中央腔体体积从 100% → 75% → 50% 的效应顺序在仿真和实测中是否一致？
2. 1646.8836 Hz 与 1986.9725 Hz 的局部效应极性和幅值是否一致？
3. 1400–2100 Hz 的频谱形状对应有多强？
4. 正确状态配对是否优于错误状态配对？
5. P04T1V 能解释的是“控制参数方向/剂量趋势”，还是“实体局部频谱的精确位置与幅值”？
6. 当前结果是否已经足以形成论文中的有界机理结论？
7. 是否值得只做一次 BASE-C → I50P-C → BASE-R 的 18 条曲线最小确认？
8. 哪些内容仍不可识别，尤其是：
   - 方向分类；
   - 完整 U4 行为；
   - 单模块因果贡献率；
   - 精确实体模态中心；
   - 房间与装配效应的独立贡献。

报告必须同时说明：

- P04T1V 是既有仿真，不是本轮新求解；
- P04T2 是既有真实实验，不是本轮重测；
- P04T3 新增的是二者之间的冻结频带、冻结频点和剂量顺序对应；
- 本轮不属于参数校准或模型拟合；
- 相关性不等于单部件因果贡献；
- final-test 保持 sealed。

## 十一、实现与验证

若需要新增分析代码：

1. 先写最小专项测试，再实现；
2. 固定所有随机种子并记录；
3. 机器可读输出不得含 NaN/Infinity；
4. CSV/JSON 中必须包含单位、数据来源阶段和分析口径；
5. 对关键数值执行有限性和重算一致性检查；
6. 运行 P04T3 专项测试；
7. 运行与 P04T1V/P04T2 相关的必要回归检查，但不要执行无关完整回归；
8. 运行 `compileall`；
9. 运行 `git diff --check`；
10. 重新计算并复核最终 `SHA256SUMS.txt`。

不得改写 P04T1V、P04T2 的历史报告或重新分类既有阶段。若需解释，只在 P04T3 新报告中交叉引用。

## 十二、停止条件与最终回复

完成全部 P04T3 产物、测试和哈希复核后立即停止。不得自动开始最小实体确认或下一仿真阶段。

最终回复必须简洁给出：

- P04T3 最终科学分类；
- 仿真与实验剂量顺序是否一致；
- 两个冻结频点的关键对应结果；
- I75、I50P 的主要 common-band 相似度与不确定性；
- 最大的模型—实验失配；
- 是否建议 18 条曲线的最小 return-control 测量；
- 报告、CSV、JSON 和图的路径；
- `final_test_read=false`；
- 新 COMSOL 求解次数 `0`；
- 未 commit、push、tag 或 release。


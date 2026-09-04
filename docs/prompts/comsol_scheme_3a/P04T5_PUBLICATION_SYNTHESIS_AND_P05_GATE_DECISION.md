# P04T5 — P04实体机制证据综合与P05门禁决策

项目路径：

`D:\Bristol course\dissertation\program work`

## 任务授权

仅执行P04T5。目标是把P04T2、P04T3和P04T4冻结为一个论文可用的机制证据链，并正式判断旧P05–P10路线是否仍有科研资格。

本轮是一次轻量closeout：不运行COMSOL、不分析新数据、不重新选频、不拟合参数、不打印、不采集、不读取final-test。完成后停止等待用户确认。

## 必须读取

1. `docs/prompts/comsol_scheme_3a/SHARED_CONTEXT.md`
2. `docs/progress/COMSOL_3A_P04B_NOMINAL_CROSS_MODULE_VALIDATION.md`
3. `docs/progress/COMSOL_3A_P04C_SINGLE_ENTRY_TOPOLOGY_MODE_DIAGNOSTIC.md`
4. `docs/progress/COMSOL_3A_P04T1V_INTEGRATED_INSERT_BOUNDED_GATE.md`
5. `docs/progress/P04T2_INTEGRATED_INSERT_PILOT_RESULTS.md`
6. `docs/progress/COMSOL_3A_P04T3_EXPERIMENT_SIMULATION_RECONCILIATION.md`
7. `docs/progress/P04T4_RETURN_CONTROL_CONFIRMATION_RESULTS.md`
8. P04T2、P04T3和P04T4 REV01的`analysis_summary.json`、`scientific_classification.json`、关键CSV、图和SHA清单
9. `docs/prompts/comsol_scheme_3a/P05_U4SYM_NUMERICAL_CONTROL.md`
10. `docs/progress/V25_CONTINGENCY_SIMULATION_ROADMAP.md`

## 审计边界

- 先检查分支、工作树和现有用户修改；不覆盖无关内容。
- 复核全部权威输入哈希。
- P04T4权威目录是`P04T4_RETURN_CONTROL_CONFIRMATION_REV01`；无REV01目录只作为阈值解释修正前的provenance，不得作为最终结论来源。
- SUP-0的`0.8793 dB`只是旧P06/正式实验活动的历史参考，不得提升为V2.5通用门槛。
- `final_test_read=false`。

## 必须完成的综合

生成一张证据链表，至少包含：

1. P04T1V仿真预测：体积剂量顺序与局部landmark；
2. P04T2实体pilot：BASE<I75<I50P、效应强度、缺少return control；
3. P04T3对应审计：剂量方向一致但局部谱形定位失配；
4. P04T4回程确认：I50P效应大于回程漂移、跨前后BASE稳定、跨批次相关，同时存在装配敏感性；
5. 每条证据支持什么、不能支持什么、属于simulation还是real_experiment。

形成最终机制陈述，必须保持有界：

> 中央共享腔有效空气体积是一个可操作的形态学频谱控制参数；减小体积会引发剂量有序、跨批次可重复的宽频谱重分配。装配状态也是重要变量，而当前简化COMSOL模型只能预测控制趋势，不能精确预测实体局部峰谷。

不得改写为方向识别成功、精确模型验证或单部件贡献率。

## P05门禁

严格复核旧P05的先决条件：P04B必须证明模型对U4可信。

只能选择一个终态：

1. `P04T5 CLOSE_SCHEME_3A_WITH_PUBLISHABLE_MECHANISM_RESULT`
   - P04机制证据已足够；
   - P04B/P04T3仍不支持精确U4预测；
   - 旧P05–P10保持blocked，不继续消耗计算和实验资源。

2. `P04T5 AUTHORIZE_REBUILT_MODEL_CONTRACT_BEFORE_P05`
   - 仅当现有材料中出现新的、可验证的模型修复依据；
   - 必须先另行冻结全新的模型契约，不能直接运行旧P05。

3. `P04T5 BLOCKED_INPUT_INTEGRITY`
   - 仅用于必要输入或哈希缺失/冲突。

不得因为希望继续P00–P10编号而绕过P04B门禁。现有证据下预期最保守终态是第1项，但必须按权威文件审计后决定。

## 产物

至少生成：

1. `docs/progress/COMSOL_3A_P04T5_PUBLICATION_SYNTHESIS_AND_P05_GATE_DECISION.md`
2. `outputs/real_experiment/research_analysis/P04T5_PUBLICATION_SYNTHESIS/evidence_chain.csv`
3. `outputs/real_experiment/research_analysis/P04T5_PUBLICATION_SYNTHESIS/claim_boundary.csv`
4. `outputs/real_experiment/research_analysis/P04T5_PUBLICATION_SYNTHESIS/stage_decision.json`
5. `outputs/real_experiment/research_analysis/P04T5_PUBLICATION_SYNTHESIS/paper_result_summary.md`
6. 一张论文可用的机制证据链PNG/SVG；不得生成大量重复图
7. `artifact_inventory.json`和`SHA256SUMS.txt`

仅更新`docs/progress/INDEX.md`和必要的Scheme 3A roadmap状态。不得改写既有阶段报告。

## 验证与停止

- 若新增代码，先写最小专项测试；
- 运行专项检查、`compileall`和`git diff --check`；
- 不运行无关完整回归；
- 不commit、push、tag或release；
- 完成P04T5后停止，不开始P05。

最终回复给出：终态、最强论文结论、关键数字、P05是否仍blocked、报告和图表路径、`final_test_read=false`、新COMSOL求解次数0。


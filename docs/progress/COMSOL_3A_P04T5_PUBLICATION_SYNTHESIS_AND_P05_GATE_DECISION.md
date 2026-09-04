# P04T5 — P04实体机制证据综合与P05门禁决策

日期：2026-08-26  
终态：`P04T5 CLOSE_SCHEME_3A_WITH_PUBLISHABLE_MECHANISM_RESULT`

## 1. 决策先行

P04机制证据链已经足够形成有界、可发表的论文结果；旧P05–P10路线继续保持blocked并在当前模型契约下关闭。P04B-N仍为`MODEL NOT CREDIBLE FOR U4`，P04C只诊断出拓扑混合而未修复可信度门禁，P04T1V只验证中央插入件的有界控制趋势，P04T3又确认实体局部谱形定位失配。现有材料没有出现新的、可验证的模型修复依据，因此不得直接运行旧P05，也不授权未经另行冻结的新模型契约。

本轮没有运行COMSOL、分析新数据、重新选频、拟合参数、打印或采集；没有读取final-test，也没有启动P05。

## 2. 权威输入与完整性

工作分支为`feature/v2-dual-input`。工作树已有大量用户阶段产物和文档修改，本轮只新增P04T5产物、报告，并最小更新INDEX与Scheme 3A路线状态；没有覆盖既有阶段报告。

| 权威阶段 | SHA复核 |
|---|---:|
| P04B-N | 94/94 PASS |
| P04C | 26/26 PASS |
| P04T1V | 24/24 PASS |
| P04T2 | 12/12 PASS |
| P04T3 | 21/21 PASS |
| P04T4 REV01 | 19/19 PASS |

P04T4的最终权威目录严格使用`P04T4_RETURN_CONTROL_CONFIRMATION_REV01`；未修订目录只保留provenance，不参与本报告的最终数值身份。P04T2既有schema把分类存放在`analysis_summary.json`，没有单独的`scientific_classification.json`；其12/12 SHA清单、已验收报告和summary内分类一致，因此这属于阶段schema差异，不构成身份冲突。

SUP-0的`0.8793 dB`只保留为旧P06/正式实验活动的历史参照，没有被提升为V2.5通用阈值。P04T4 REV01的回程解释使用本批all-six最大组内pairwise RMS `0.6168 dB`。

## 3. 冻结证据链

| 阶段 | 类型 | 关键结果 | 支持什么 | 不能支持什么 |
|---|---|---|---|---|
| P04B-N | simulation | HR02–HR05为边界最大值；HR03/HR04稳定模块中心不可识别；HR04网格中心变化无定义 | nominal模型未取得完整U4预测资格 | 旧P05入口、精确U4预测 |
| P04C | saved-solution simulation diagnostic | HR03由孤立约1904.19 Hz重组到集成约1650.40 Hz，漂移−0.209 octave；存在压缩共享分支 | 固定通道/共享腔连接与模态重组、混合分支相关 | 模型修复、方向识别、唯一部件因果性 |
| P04T1V | simulation | branch `1651.323→1679.908→1729.028 Hz`；I75 landmark −2.443/+2.669 dB，I50P −6.524/+6.326 dB | 减小中央腔有效空气体积产生有序控制趋势 | 实体局部峰谷精度、U4可信度、方向性能 |
| P04T2 | real_experiment | BASE批间0.4279 dB；I75 1.4799 dB（3.46×）；I50P 2.1407 dB（5.00×）；两效应谱相关0.720 | `BASE<I75<I50P`的剂量有序宽频重分配 | return control、独立重装、精确landmark、方向识别、贡献率 |
| P04T3 | reconciliation | 1400–2100 Hz selected-4 demeaned Pearson：I75 −0.429、I50P +0.118，均低于0.50门槛 | 仿真与实体在体积控制方向上相符 | 精确COMSOL实体预测、保留比例频谱条形码 |
| P04T4 REV01 | real_experiment | bracketed I50P 2.3672 dB `[2.3409,2.4127]`；回程1.0887 dB；比值2.174 `[1.997,2.286]`；前后BASE效应相关0.906；跨批次相关0.786 | I50P效应大于回程漂移、跨前后BASE保持且在P04T2/P04T4跨批次复现 | 完全可逆、装配/时间/环境分离、跨日期普适性、精确landmark |

第三批BASE跟踪进一步限定：装配、时间和环境/收音状态的贡献在当前协议内不可分离，但I50P相对不同BASE定义仍保持约2.280–2.569 dB且最低效应谱相关0.906。这加强主张边界，不改变REV01的中央腔体积效应结论。

## 4. 最终论文机制陈述

> 中央共享腔有效空气体积是一个可操作的形态学频谱控制参数；减小体积会引发剂量有序、跨批次可重复的宽频谱重分配。装配状态也是重要变量，而当前简化COMSOL模型只能预测控制趋势，不能精确预测实体局部峰谷。

该陈述把simulation与real_experiment证据分开：P04T1V提供前瞻性的控制趋势预测；P04T2/P04T4提供实体剂量和回程/跨批次证据；P04T3给出模型—实验边界；P04B/P04C解释为何该模型不能升级为完整U4预测器。

可以声称：中央腔体积控制、剂量有序宽频谱重分配、I50P效应超过回程漂移、跨两个采集批次的同类谱形复现，以及基线/装配状态的重要性。

不可以声称：方向识别成功、U4HR已被证明优于U4SYM、H1确认、精确COMSOL实体模型验证、完全可逆、跨日期/多操作者/量产泛化，或单部件独立贡献率。

## 5. P05门禁

旧`P05_U4SYM_NUMERICAL_CONTROL.md`的显式先决条件是：用户先验收P04B对U4建模可信。该条件没有满足。

| 门禁问题 | 结果 |
|---|---|
| P04机制证据是否已足够形成论文结果 | PASS |
| P04B是否证明模型对U4可信 | FAIL |
| P04T3是否支持精确实体局部预测 | FAIL |
| 是否存在新的、可验证的模型修复依据 | NO |
| 是否应冻结全新模型契约后再议P05 | 当前不授权；若未来确有新依据，必须另行立项和冻结 |
| 旧P05–P10 | `BLOCKED_AND_CLOSED_UNDER_CURRENT_CONTRACT` |
| 本轮是否启动P05 | NO |

因此唯一适用终态为`P04T5 CLOSE_SCHEME_3A_WITH_PUBLISHABLE_MECHANISM_RESULT`，而不是为了保持P00–P10编号连续而绕过P04B。

## 6. 产物

目录：`outputs/real_experiment/research_analysis/P04T5_PUBLICATION_SYNTHESIS/`

- `evidence_chain.csv`：simulation/real_experiment证据、支持范围与禁止升级；
- `claim_boundary.csv`：论文主张边界；
- `stage_decision.json`：哈希审计、终态与P05门禁；
- `paper_result_summary.md`：论文结果段落摘要；
- `mechanism_evidence_chain.png/.svg`：唯一机制证据链图；
- `artifact_inventory.json`与`SHA256SUMS.txt`；
- 最小专项实现与测试。

## 7. 验证与停止

- P04T5专项测试：4 passed；
- 机器可读CSV/JSON有限性、必需字段和终态一致性：PASS；
- `compileall`：PASS；
- `git diff --check`：PASS；
- 最终SHA-256逐项复核：PASS。

`final_test_read=false`；新COMSOL求解次数0；P05未启动；未commit、push、tag或release。本轮在P04T5结束。

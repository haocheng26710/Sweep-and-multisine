# 开发进度索引

本目录记录可由 Git 提交、测试输出和项目文档复核的增量步骤。状态“完成”仅表示该软件切片及其验证完成，不表示已获得真实实验结果或可以形成科研结论。

| 步骤 | 日期 | 状态 | 报告 | Git commit |
|---|---|---|---|---|
| DEV-C16 — T0–T3 实验前 dry-run、V2 总验收与 DEV-D 接入清单 | 2026-08-06 | 完成（提交后 clean-tree bundle 为最终权威；非科研/非部署） | [DEV-C16_PRE_EXPERIMENT_ACCEPTANCE.md](./DEV-C16_PRE_EXPERIMENT_ACCEPTANCE.md) | 本报告与实现同一提交：`chore(validation): complete pre-experiment acceptance` |
| DEV-C15 — P9-D 冻结模型包驱动的离线单次快速读取 | 2026-08-06 | 完成（simulated software validation only） | [DEV-C15_P9D_OFFLINE_FAST_READOUT.md](./DEV-C15_P9D_OFFLINE_FAST_READOUT.md) | 本报告与实现同一提交：`feat(readout): add frozen offline direction inference` |
| DEV-C14 — P9-C Sweep–Multisine cross-mode bridge calibration | 2026-08-06 | 完成（simulated software validation only） | [DEV-C14_P9C_CROSS_MODE_BRIDGE_CALIBRATION.md](./DEV-C14_P9C_CROSS_MODE_BRIDGE_CALIBRATION.md) | 本报告与实现同一提交：`feat(bridge): add leakage-safe cross-mode calibration` |
| DEV-C13 — P9-B Sweep projection ablation、P4 保真与 P5 稳定性 | 2026-08-06 | 完成 | [DEV-C13_P9B_SWEEP_PROJECTION_ABLATION.md](./DEV-C13_P9B_SWEEP_PROJECTION_ABLATION.md) | 本报告与实现同一提交（`feat(bridge): evaluate selected-tone projection fidelity`） |
| DEV-B0 — 数据来源 schema 与 research hard gate | 2026-08-04 | 完成 | [DEV-B0_PROVENANCE_RESEARCH_GATE.md](./DEV-B0_PROVENANCE_RESEARCH_GATE.md) | `163ab40` |
| DEV-B1 — P1 REW Frequency Response TXT 导入 | 2026-08-04 | 完成 | [DEV-B1_P1_REW_TXT_IMPORT.md](./DEV-B1_P1_REW_TXT_IMPORT.md) | `45719bf` |
| DEV-B2 — P8-A 模拟同步与 tone 幅值恢复 | 2026-08-04 | 完成 | [DEV-B2_P8A_SYNC_AND_MAGNITUDE_RECOVERY.md](./DEV-B2_P8A_SYNC_AND_MAGNITUDE_RECOVERY.md) | `b2b8b05` |
| DEV-B3 — P8-B1 clock drift 检测、阈值决策与可审计校正 | 2026-08-05 | 完成 | [DEV-B3_P8B1_CLOCK_DRIFT.md](./DEV-B3_P8B1_CLOCK_DRIFT.md) | `8d94398` |
| DEV-B4 — P8-B2 数字完整性、per-tone 质量指标与 P8 QC 汇总 | 2026-08-05 | 完成 | [DEV-B4_P8B2_TONE_AND_AUDIO_QC.md](./DEV-B4_P8B2_TONE_AND_AUDIO_QC.md) | `039df4e` |
| DEV-B5 — P1 multisine adapter、统一双入口调度及 P7→S3→P8 E2E | 2026-08-05 | 完成 | [DEV-B5_DUAL_INPUT_ADAPTER_AND_E2E.md](./DEV-B5_DUAL_INPUT_ADAPTER_AND_E2E.md) | `b471463` |
| DEV-C1 — P2-A 双入口共享单测量 QC 核心 | 2026-08-05 | 完成 | [DEV-C1_P2A_SHARED_QC_CORE.md](./DEV-C1_P2A_SHARED_QC_CORE.md) | `3621ecf` |
| DEV-C2 — P3-A dense sweep 公共频率网格与基础 FeatureSet | 2026-08-05 | 完成 | [DEV-C2_P3A_DENSE_FEATURE_CORE.md](./DEV-C2_P3A_DENSE_FEATURE_CORE.md) | `c82ac65` |
| DEV-C3 — P3-B 明确、可审计的 dense-spectrum smoothing | 2026-08-05 | 完成 | [DEV-C3_P3B_DENSE_SMOOTHING.md](./DEV-C3_P3B_DENSE_SMOOTHING.md) | `5d54938` |
| DEV-C4 — P3-C 严格匹配的 sweep projection 与 multisine tone FeatureSet | 2026-08-05 | 完成 | [DEV-C4_P3C_MATCHED_TONE_FEATURES.md](./DEV-C4_P3C_MATCHED_TONE_FEATURES.md) | `a750116` |
| DEV-C5 — P4-A FeatureSet-only 方向指标核心 | 2026-08-05 | 完成 | [DEV-C5_P4A_DIRECTION_METRICS_CORE.md](./DEV-C5_P4A_DIRECTION_METRICS_CORE.md) | `9ec8cfe` |
| DEV-C6 — P2-B 跨测量 QC、重复稳定性与条件完整性门禁 | 2026-08-05 | 完成 | [DEV-C6_P2B_CROSS_MEASUREMENT_QC.md](./DEV-C6_P2B_CROSS_MEASUREMENT_QC.md) | 本报告与实现同一提交（`feat(qc): add cross-measurement dataset quality gate`） |
| DEV-C7 — P4-B 频带、配置与跨测量模式通用指标 | 2026-08-05 | 完成 | [DEV-C7_P4B_BAND_CONFIG_AND_CROSS_MODE_METRICS.md](./DEV-C7_P4B_BAND_CONFIG_AND_CROSS_MODE_METRICS.md) | 本报告与实现同一提交（`feat(metrics): add band and cross-mode comparison metrics`） |
| DEV-C8 — P5-A 防数据泄漏的分组方向分类核心 | 2026-08-06 | 完成 | [DEV-C8_P5A_GROUPED_CLASSIFICATION_CORE.md](./DEV-C8_P5A_GROUPED_CLASSIFICATION_CORE.md) | 本报告与实现同一提交（`feat(classification): add leakage-safe grouped classification core`） |
| DEV-C9 — P5-B 严格防泄漏的四协议跨模式分类验证 | 2026-08-06 | 完成 | [DEV-C9_P5B_CROSS_MODE_CLASSIFICATION.md](./DEV-C9_P5B_CROSS_MODE_CLASSIFICATION.md) | 本报告与实现同一提交（`feat(classification): add leakage-safe cross-mode validation`） |
| DEV-C10 — P6-A Sweep HR 峰值检测与可审计校准框架 | 2026-08-06 | 完成 | [DEV-C10_P6A_SWEEP_HR_CALIBRATION.md](./DEV-C10_P6A_SWEEP_HR_CALIBRATION.md) | 本报告与实现同一提交（`feat(hr): add auditable sweep resonance calibration`） |
| DEV-C11 — P6-B 冻结校准约束下的 Multisine HR readout | 2026-08-06 | 完成 | [DEV-C11_P6B_MULTISINE_HR_READOUT.md](./DEV-C11_P6B_MULTISINE_HR_READOUT.md) | 本报告与实现同一提交（`feat(hr): add calibrated multisine HR readout`） |
| DEV-C12 — P9-A 严格防数据泄漏的 tone 候选评分与选择冻结框架 | 2026-08-06 | 完成 | [DEV-C12_P9A_LEAKAGE_SAFE_TONE_SELECTION.md](./DEV-C12_P9A_LEAKAGE_SAFE_TONE_SELECTION.md) | 本报告与实现同一提交（`feat(bridge): add leakage-safe tone selection`） |

当前科研资格边界：截至 DEV-C16，使用的数据只有 `simulated` 和 `external_reference`。两者均不得用于科研结论；只有通过 provenance schema、research hard gate、显式 P2-B canonical dataset gate 及后续独立批准的合格 `real_experiment` 才能进入 canonical `research_analysis`。DEV-C16 的 ready 只允许进入少量、受控、诊断性 DEV-D 设备实验准备。P2–P9-D 参数与模型仍为 provisional；final-test 保持封存；P9-A selection、P9-B minimum-tone candidate、P9-C calibration 和 P9-D readout package 均不可部署。真实 HR 数据、批准校准、真实阈值/tone/model 冻结、科学资格和部署批准尚未完成，因此不能声明科研结论。

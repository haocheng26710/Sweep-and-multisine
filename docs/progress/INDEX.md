# 开发进度索引

本目录记录可由 Git 提交、测试输出和项目文档复核的增量步骤。状态“完成”仅表示该软件切片及其验证完成，不表示已获得真实实验结果或可以形成科研结论。

| 步骤 | 日期 | 状态 | 报告 | Git commit |
|---|---|---|---|---|
| DEV-B0 — 数据来源 schema 与 research hard gate | 2026-08-04 | 完成 | [DEV-B0_PROVENANCE_RESEARCH_GATE.md](./DEV-B0_PROVENANCE_RESEARCH_GATE.md) | `163ab40` |
| DEV-B1 — P1 REW Frequency Response TXT 导入 | 2026-08-04 | 完成 | [DEV-B1_P1_REW_TXT_IMPORT.md](./DEV-B1_P1_REW_TXT_IMPORT.md) | `45719bf` |
| DEV-B2 — P8-A 模拟同步与 tone 幅值恢复 | 2026-08-04 | 完成 | [DEV-B2_P8A_SYNC_AND_MAGNITUDE_RECOVERY.md](./DEV-B2_P8A_SYNC_AND_MAGNITUDE_RECOVERY.md) | `b2b8b05` |
| DEV-B3 — P8-B1 clock drift 检测、阈值决策与可审计校正 | 2026-08-05 | 完成 | [DEV-B3_P8B1_CLOCK_DRIFT.md](./DEV-B3_P8B1_CLOCK_DRIFT.md) | `8d94398` |
| DEV-B4 — P8-B2 数字完整性、per-tone 质量指标与 P8 QC 汇总 | 2026-08-05 | 完成 | [DEV-B4_P8B2_TONE_AND_AUDIO_QC.md](./DEV-B4_P8B2_TONE_AND_AUDIO_QC.md) | `039df4e` |
| DEV-B5 — P1 multisine adapter、统一双入口调度及 P7→S3→P8 E2E | 2026-08-05 | 完成 | [DEV-B5_DUAL_INPUT_ADAPTER_AND_E2E.md](./DEV-B5_DUAL_INPUT_ADAPTER_AND_E2E.md) | `b471463` |
| DEV-C1 — P2-A 双入口共享单测量 QC 核心 | 2026-08-05 | 完成 | [DEV-C1_P2A_SHARED_QC_CORE.md](./DEV-C1_P2A_SHARED_QC_CORE.md) | `3621ecf` |
| DEV-C2 — P3-A dense sweep 公共频率网格与基础 FeatureSet | 2026-08-05 | 完成 | [DEV-C2_P3A_DENSE_FEATURE_CORE.md](./DEV-C2_P3A_DENSE_FEATURE_CORE.md) | 本报告与实现同一提交 |

当前科研资格边界：截至 DEV-C2，使用的数据只有 `simulated` 和 `external_reference`。两者均不得用于科研结论；只有通过 provenance schema 和 research hard gate 的合格 `real_experiment` 才能进入 `research_analysis`。P2-A 与 P3-A 阈值仍为 provisional；P2-B、P3-B、sparse-tone FeatureSet、P4–P6 和 P9 尚未实现，因此不能声明科研结论。

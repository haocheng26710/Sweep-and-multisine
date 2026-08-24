# SUP-1：ENC-A～H 单入口模块特征库

状态：完成；在既有 SUP-1 真实数据上形成固定窗口模块签名库

日期：2026-08-24

分支：`feature/v2-dual-input`

## 1. 本轮范围与数据身份

本报告是既有 SUP-1 的增量整理，不是新采集。输入为 `ENC-A-H.zip` 中 29 份真实 REW TXT 经 SUP-1 已固化的 29 个 FORMAL-1 FeatureSet：A/B/C 各 3 次，D/E/F/G/H 各 4 次；主签名使用每模块已冻结的 3 次重复，共 24 条，另外 5 条只保留为第四次敏感性记录。原始 TXT、原始 ZIP、主三次选择、4 个 outlier flags 和 provenance 均未修改。

输入 SUP-1 权威目录的 100/100 项业务 artifact hash 通过；artifact manifest SHA-256 为 `76ed64aac0674244fb20d66390f1bf3c1b538f2ed0ed5fa115129479c35a85dc`。数据继续登记为 `data_origin=real_experiment`、`dataset_role=supplemental_research_analysis`、`scientifically_eligible=false`。没有读取 final-test，没有使用模拟数据，也没有运行分类器。

HOM-A 与 HET-ABDF 没有重新采集。它们的身份与阵列再分析见 [SUP-2R 报告](./SUP_2R_EXISTING_DATA_MECHANISM_REANALYSIS.md)。

## 2. 固定方法

- 预处理只复用 FORMAL-1：200–8000 Hz、48 points/octave 对数网格、1/12-octave dB smoothing。
- 200–4000 Hz 为主频带，4000–8000 Hz 仅为次要证据。
- 只使用 SUP-0 已冻结的 9 个主窗口和 3 个次要窗口；未重新选频、改阈值或改变 schema。
- 每条重复曲线先在所属父频带内去均值。模块绝对签名是三条重复曲线的代表谱；模块间窗口效应以 ENC-A 为共同描述性参考，报告 signed mean、RMS、同窗 SUP-0 CONT p95 比值和 whole-repeat bootstrap 95% CI。
- bootstrap 单位是整条重复曲线，频率点从未被当成独立样本。
- ENC-A 相对自身的差为零，因此 A 的窗口排序只能使用它的绝对去均值签名，不能当成 A 的“模块效应”。

## 3. 模块内重复性与异常保留

主频带 FORMAL CONT p95 为 0.8793 dB。A、C 有部分重复对超过该底线；其余六个模块的主三次均在底线内。A-R01 flag 保留在主分析；D-R03、F-R04、G-R04 是既有第四次敏感性记录中的 flags，并未因此改变正式选择。

| 模块 | 主频带配对 RMS median / max（dB） | 状态 | 已保留 flag |
|---|---:|---|---|
| ENC-A | 0.9966 / 1.0975 | 部分重复对超过底线，谨慎解释 | A-R01 |
| ENC-B | 0.2855 / 0.2988 | 底线内 | — |
| ENC-C | 0.9119 / 0.9900 | 部分重复对超过底线，谨慎解释 | — |
| ENC-D | 0.8184 / 0.8208 | 主三次底线内 | D-R03（第四次记录） |
| ENC-E | 0.2044 / 0.2693 | 底线内 | — |
| ENC-F | 0.2832 / 0.2998 | 主三次底线内 | F-R04（第四次记录） |
| ENC-G | 0.2820 / 0.3327 | 主三次底线内 | G-R04（第四次记录） |
| ENC-H | 0.2254 / 0.2849 | 底线内 | — |

没有发现文件损坏、身份错误、数字削波或已记录的明确技术事故。A 和 C 的较弱重复性被如实标记，但数据仍足以形成带不确定性的模块签名；因此本轮不建议重测任何 SUP-1 文件。

## 4. 固定窗口模块签名

下表给出各模块最显著的主频带固定窗口。B～H 的数值是相对 ENC-A 的窗口 RMS / 同窗 SUP-0 CONT p95；A 的数值是绝对去均值 signed mean 的绝对值，二者不可横向当作同一效应量。

| 模块 | 主要固定窗口 | 解释 |
|---|---|---|
| ENC-A | P13 12.286 dB；P01 8.106 dB；P12 7.868 dB | 绝对谱形锚点，不是 A−A 效应 |
| ENC-B | P01 15.89×；P02 5.94×；P13 4.87× | 低频 P01/P02 最强，并有 P13 特征 |
| ENC-C | P02 3.61×；P01 3.38×；P09 1.74× | 效应相对较弱，且组内重复性需谨慎 |
| ENC-D | P02 11.62×；P01 10.08×；P12 3.26× | P01/P02 强，P12 提供中高频差异 |
| ENC-E | P02 6.46×；P01 4.95×；P09 2.40× | P01/P02 主导，整体与 F/G 相对接近 |
| ENC-F | P01 13.54×；P02 4.78×；P12 3.48× | P01 强，P12 可用于阵列对应解释 |
| ENC-G | P12 4.00×；P02 3.99×；P01 3.51× | P12 相对突出，和 E/F 较接近 |
| ENC-H | P01 14.38×；P02 6.65×；P13 3.58× | P01/P02 强，并有 P13 特征 |

完整 96 行模块×窗口结果，包括 signed mean、RMS、同窗底线、bootstrap CI、敏感性视图和重复性字段，见 `module_window_features.csv`。次要窗口 S01–S03 已计算并保留，但不提升为主结论。

## 5. 相似、难区分与可重复边界

在完整 200–4000 Hz 去均值代表谱上，28/28 个模块对仍超过 FORMAL CONT p95，且每对 9/9 个跨重复组合超过底线。这支持“不同模块产生可重复频谱差异”，但不是分类性能证明。

相对最接近的三对是 E–G（1.5724× floor）、E–F（1.6064×）和 F–G（1.6295×）；之后为 A–C（1.8020×）和 D–H（1.8617×）。这些对是“相对更难区分”，不是“不可区分”。固定窗口向量的高相关也只说明共享谱形结构，不能替代绝对效应或分类验证。

A、B、D、F 中，B 的 P01/P02/P13、D 的 P01/P02/P12、F 的 P01/P02/P12 可作为 HET-ABDF 的预先固定解释特征；A 是 HOM-A 参考锚点。实际阵列对应是否成立必须由 SUP-2R 的方向分层比较判断，不能只凭单入口效应量推断。

## 6. 产物与结论边界

权威输出目录：

```text
outputs/supplemental/SUP-1_SUP-2R_MECHANISM_REANALYSIS/
```

本报告对应的主要产物为 `module_window_features.csv`、`module_similarity.csv`、`plots/single_entry_module_signatures.png/.svg` 和 `analysis_summary.json`。本轮新增的是模块签名的统一窗口化、不确定性和后续阵列对应接口；既有 SUP-1 的 29/29 清点、QC、主三次选择和总体模块对结论没有被重新包装成新实验。

结果不把模块字母解释为方向，不确认 H1，不证明 U4ENC 优于 U4SYM，也不支持可靠四方向分类或任何单模块因果贡献率。`final_test_read=false`。

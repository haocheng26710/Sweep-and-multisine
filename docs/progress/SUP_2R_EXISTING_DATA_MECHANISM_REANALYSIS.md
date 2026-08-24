# SUP-2R：既有 HOM-A / HET-ABDF 数据机理再分析

状态：完成；仅复用既有真实数据进行频率定位与机理对应

日期：2026-08-24

分支：`feature/v2-dual-input`

## 1. V2 身份纠正与数据审计

HOM-A 与正式实验 `U4SYM AS01` 完全相同，权威 ACTIVE 数据为 B01/B02；HET-ABDF 与正式实验 `U4ENC AS01` 完全相同，权威 ACTIVE 数据为 B03/B04。因此本轮没有重新采集 HOM-A 或 HET-ABDF，也没有生成或使用模拟替代数据。

| 阵列身份 | 正式身份 | block | ACTIVE 数 | 每方向结构 |
|---|---|---|---:|---|
| HOM-A | U4SYM AS01 | B01、B02 | 24 | 每 block×方向 3 次 |
| HET-ABDF | U4ENC AS01 | B03、B04 | 24 | 每 block×方向 3 次 |

FORMAL-3 共 72 ACTIVE、19 EXCLUDED；本轮只取 B01–B04 的 48 条 AS01 ACTIVE。四个 block 各 12 条，0°/90°/180°/270°各有完整的 block×3 重复结构。身份、configuration、assembly、direction、block、重复编号与 FeatureSet hash 均经正式 manifest 验证。

物理装配对应使用 2026-08-24 用户 V2 增量规格作为明确权威：`0°=ENC-A`、`90°=ENC-B`、`180°=ENC-D`、`270°=ENC-F`。该对应关系没有从文件名推断；旧正式 manifest 只足以确认 U4SYM/U4ENC 和 block 身份，不能替代这份装配映射。

输入闭包验证：FORMAL-3 225/225、FORMAL-4 28/28、FORMAL-5 6/6、SUP-0 9/9、SUP-1 100/100 artifact hash 全部通过。没有缺失必要文件，`selection_changed=false`、`simulated_data_used=false`、`final_test_read=false`。

## 2. 与 FORMAL-4/5 的区别

以下全部是 FORMAL-4/5 已有总体结果，本轮只引用，不声称为新发现：

- 主频带 CONT p95 重复性底线 0.8793 dB；
- U4ENC `G_demeaned=1.2805`，95% CI 0.8297–1.7667；U4SYM `G_demeaned=0.6824`，95% CI 0.6105–1.2699；
- ΔG=0.5982，95% CI −0.1131–1.0843；AS01 configuration/floor=1.5688；
- grouped classification：U4ENC balanced accuracy 0.25、macro-F1 0.1833；U4SYM 0.375、0.25，均未达到 0.50 实用目标；
- 冻结结论仍为 `supported_with_limits`、`H0=not_rejected`、`H1=not_confirmed`、`scientifically_eligible=false`。

本轮新增的只有：HET−HOM 在 SUP-0 固定窗口中的方向/频率定位、block/repeat 不确定性，以及它与 SUP-1 单入口 A/B/D/F 签名的描述性对应分析。

## 3. 固定分析方法

- 主频带 200–4000 Hz；4000–8000 Hz 只作 secondary。
- 使用 SUP-0 冻结的 P01/P02/P03/P04/P07/P09/P11/P12/P13 和 S01/S02/S03，不自适应选频。
- 每条曲线在父频带内去均值。对每个方向分别计算 B03/B04 HET 与 B01/B02 HOM 的代表差、窗口 signed mean、RMS、同窗 SUP-0 CONT p95 比值和 95% CI。
- bootstrap 先对 configuration block 分层，再重采样整条重复曲线；相关分析同时重采样 SUP-1 模块重复和正式 block/repeat cluster。频率点从未作为独立样本。
- 主分析保留既有 ACTIVE outlier flags；敏感性视图仅临时略去 flags，不改变正式 ACTIVE/EXCLUDED。
- 未运行分类器，未修改阈值、算法门槛、既有 schema 或 FORMAL-5 结论。

## 4. HOM-A 与 HET-ABDF 哪里不同

48 个方向×窗口点估计中，41 个 RMS 超过同窗 SUP-0 floor；23 个的 bootstrap RMS 95% CI 下界也超过 floor。主频带中满足后者的窗口如下：

| 方向 | 映射模块 | 稳定主窗口：signed HET−HOM；RMS/floor |
|---:|---|---|
| 0° | ENC-A | P01 −0.425 dB、2.40×；P11 +1.661 dB、1.92×；P12 +0.062 dB、2.13× |
| 90° | ENC-B | P01 −0.979 dB、4.19×；P11 +0.692 dB、2.08×；P12 −1.338 dB、2.93×；P13 +2.557 dB、2.35× |
| 180° | ENC-D | P11 +1.299 dB、2.12×；P12 −0.949 dB、2.37×；P13 +1.109 dB、1.86× |
| 270° | ENC-F | P01 −0.062 dB、2.07×；P11 +1.053 dB、1.53×；P12 −2.256 dB、3.10× |

因此主差异集中在约 203–252 Hz（P01）以及约 2.05–3.97 kHz（P11–P13），其中 90° 的 P01 最强，270° 的 P12 最强。signed mean 接近零但 RMS 较大（例如 0° P12、270° P01）表示窗内有正负谱形结构，不能解释为“没有差异”。

次要频带 S02（5.08–6.31 kHz）四方向均较强，RMS/floor 分别约 3.17×、4.40×、2.96×、2.48×；但该频带重复性底线更高，只作为次要证据。

## 5. 方向模式是否一致

四方向并非完全一致。主窗口模式的 cluster-bootstrap Pearson 比较中，90°–180°（r=0.835，CI 0.577–0.913）、90°–270°（r=0.574，CI 0.356–0.662）、180°–270°（r=0.780，CI 0.503–0.826）和 0°–180°（r=0.626，CI 0.282–0.732）呈稳定正对应；0°–90°与0°–270°的 CI 包含零。

这表明非零三个方向之间共享较明显的窗口结构，但 0° 模式并不稳定地跟随所有其他方向。不能把“部分方向模式一致”升级为可靠四方向可分类。

## 6. 与单入口 A/B/D/F 签名的对应

主频带固定窗口的物理映射对应结果如下。稳定状态要求 Pearson、Spearman 和 cosine 的 cluster-bootstrap 95% CI 下界均大于零，并在保留 flags 的主分析和去 flags 敏感性中一致。

| 方向 / 映射 | Pearson r（95% CI） | Spearman r（95% CI） | Cosine（95% CI） | 结论 |
|---|---:|---:|---:|---|
| 0° / ENC-A | — | — | — | A−A 为零，不能估计替换签名 |
| 90° / ENC-B | 0.692（0.390–0.815） | 0.133（−0.267–0.633） | 0.692（0.389–0.813） | Pearson/cosine 一致，但排序不稳定；探索性 |
| 180° / ENC-D | 0.201（−0.074–0.380） | 0.067（−0.217–0.483） | 0.177（−0.085–0.348） | 对应不确定；探索性 |
| 270° / ENC-F | 0.725（0.502–0.786） | 0.567（0.083–0.717） | 0.717（0.508–0.761） | 主分析与敏感性均稳定正对应 |

稳定结论只有 270°–ENC-F。90°–ENC-B 是有方向性的线索，但不能稳定通过所有相似性指标；180°–ENC-D 没有稳定对应。全表还显示部分非物理映射模块也能与某方向取得正相关，例如 90°与 F、180°与 F，这说明共享频谱形状会产生非唯一匹配，进一步限制了因果解释。

因此现有数据足以回答“HET 与 HOM 在哪些冻结频带不同”，也能提供“某些阵列差异与单入口签名一致”的受限证据；不足以分离四个位置的独立贡献。HET-ABDF 相对 HOM-A 同时改变 B/D/F 三个位置，模块效应、位置耦合和阵列相互作用不可识别。相关性不得解释为单模块贡献率，也不得给出贡献百分比。

## 7. 是否需要最小 SUP-3

若研究目标止于频率定位，本轮数据已经足够，不需要新的重复采集。若必须估计单个模块的因果增量，则需要一个最小消融；建议只比较 HET-ABDF 与“90°位置 ENC-B 替换为 ENC-A、其余位置不变”，目标方向 90°、目标窗口 P01。未来若获授权，可同一时段每条件连续 3 次，共 6 次；不扩展为完整正反向、拆装或全位置矩阵。

这个 SUP-3 只是建议，不是本轮采集计划，本轮未实施，也未安排任何新采集。

## 8. 权威产物、验证与结论边界

权威输出目录：

```text
outputs/supplemental/SUP-1_SUP-2R_MECHANISM_REANALYSIS/
```

主要机器可读产物：`data_audit.csv`、`module_window_features.csv`、`het_hom_direction_window_effects.csv`、`het_hom_direction_frequency_curves.csv`、`single_entry_array_correspondence.csv`、`direction_pattern_consistency.csv`、`analysis_summary.json`、`input_audit.json`。四组图均提供 PNG/SVG：单入口签名、方向 HET−HOM、映射签名比较、固定窗口效应及不确定性。18/18 业务 artifact hash 通过；artifact manifest SHA-256 为 `cc83f4a7260b4f76b9c1c5342b1660705096cc69b4d4f6de08d3be2d437d3bdf`。

结论边界不变：不确认 H1，不证明 U4ENC 优于 U4SYM，不声称可靠四方向分类，不把相关性解释为单模块因果贡献，不修改科研资格。`final_test_read=false`。

实现采用最小 red–green 切片：先为 V2 映射权威、整条模块重复 bootstrap、block→整条重复 bootstrap 和固定窗口 cluster 对应写失败测试，再实现分析核心。最终相关回归 50 passed；映射 fail-closed 断言增强后的专项测试 4 passed；`compileall` 与 `git diff --check` 均通过。本轮只创建本地提交，不 push、不 tag、不 release。

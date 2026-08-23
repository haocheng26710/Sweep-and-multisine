# SUP-0：已有 ACTIVE 数据频率定位与补充实验分析冻结

状态：完成；SUP-1～SUP-4 的候选频带、统计量与排除规则已冻结

日期：2026-08-23

分支：`feature/v2-dual-input`

## 1. 边界与只读核对

本步只读取 FORMAL-3 的 72 份 ACTIVE FeatureSet，并核验 FORMAL-4 的权威产物；19 份 EXCLUDED 没有进入计算，10 条 ACTIVE outlier flags 在主分析中全部保留。没有扫描原始目录、重新导入 TXT、改变 ACTIVE/EXCLUDED、读取 final-test、采集新数据或修改 FORMAL-5 结论。

执行前核对了研究协议、FORMAL-4/5、WRITE/论文整合稿和原始实验指导 DOCX。DOCX 的正文与表格已结构化读取；本机未安装 LibreOffice，因此未完成页面 PNG 视觉版式核验。原指导书中 E13/E14 的共同频率轴、统一处理、去均值谱形、G 和分组验证原则与当前冻结边界一致；其中旧的 1–8 kHz 建议已被后续 FORMAL-1 的 200–4000 Hz 主频带和 4000–8000 Hz 次要频带正式替代。

仓库核对时工作树干净，当前分支相对本地记录的 `origin/feature/v2-dual-input` 为 ahead 1、behind 0；本步未 fetch、push、tag 或 release。

## 2. 已回答、未回答与补充步骤

| 问题 | 已有正式实验 | 仍缺少的证据 | 补充步骤 |
|---|---|---|---|
| 是否存在超过技术重复底线的频谱差异 | 已回答：AS01 中存在，且 U4ENC 方向点估计较大 | 差异具体集中在哪些频率 | SUP-0 固定窗口定位 |
| 八种 ENC 单模块分别改变什么 | 未回答 | 同一位置、同一参考状态下的 A～H 比较 | SUP-1 |
| 同质与异质阵列有何差异 | 仅有 U4SYM/U4ENC 配置观察，不能等同于严格 HOM/HET 对照 | 同一冻结装置下的 HOM/HET 四方向增量 | SUP-2 |
| 四个位置各自贡献多少 | 未回答 | 固定异质基线上的单位置替换 | SUP-3 |
| 是否可更新论文结论 | FORMAL-5 为 `supported_with_limits` | 需等待 SUP-1～SUP-3 全部采集后统一 QC/分析 | SUP-4 |

## 3. SUP-0 冻结方法

### 3.1 预处理与窗口

- 频率网格：FORMAL-1 对数网格，48 points/octave；256 点中 255 点有效。
- smoothing：FORMAL-1 已完成的 1/12-octave dB smoothing；SUP-0 不再次平滑。
- 父频带：主频带 200–4000 Hz；次要频带 4000–8000 Hz。无插值支撑的 200 Hz 点继续 invalid，不外推。
- 定位窗口：每个父频带从首个有效点开始，按固定 16 个网格点分窗，约 1/3 octave；末窗至少 8 点。共 13 个主频带窗口、3 个次要窗口。全部窗口均评估，不做 top-N、峰值搜索或逐频点未校正显著性检验。
- 归一化：每条 block×direction 稳健中位曲线先在所属父频带内去均值，再在固定窗口内计算 RMS dB 差。该定义定位的是对父频带去均值效应的局部贡献。

### 3.2 同窗重复性底线与通过规则

- 同窗 CONT floor：在相同 block×direction cell 内形成全部 CONT 配对，计算该窗口的 raw RMS dB 差；以所有配对的 p95 作为保守底线。
- U4ENC 方向窗口通过：AS01 的两个 REPOS block 中，每个 block 至少 4/6 方向对超过同窗 CONT p95，且每个 block 的六方向对效应中位数也超过底线。
- AS01 配置窗口通过：四个方向中至少 3/4 的 U4ENC–U4SYM 代表曲线差超过同窗 CONT p95，且四方向效应中位数超过底线。
- 敏感性门禁：上述规则必须在“全部 72 ACTIVE”与“临时略去已 flag ACTIVE 曲线”两种视图中同时通过。
- 冻结候选集合：`U4ENC 方向通过 OR AS01 配置通过` 的并集；不按效应大小事后只保留若干最优窗口。

## 4. 父频带结果

| 父频带 | CONT median / IQR / p95 | U4ENC 稳健方向效应 / floor | U4SYM 残余方向效应 / floor | AS01 配置效应 / floor | 解释 |
|---|---:|---:|---:|---:|---|
| 200–4000 Hz | 0.3783 / 0.2191 / 0.8793 dB | 1.8303 | 1.0662 | 1.5688 | 主结果；复现 FORMAL-4 floor，U4ENC 与配置效应超过底线 |
| 4000–8000 Hz | 0.7687 / 0.3357 / 1.3452 dB | 2.8964 | 1.0268 | 2.8602 | 效应比高，但重复误差也更高，继续作为 secondary/sensitivity |

这里的“稳健方向效应 / floor”是两个 AS01 REPOS block 的方向对中位 RMS 与同频带 CONT p95 比值中的较小值，不是 `G_demeaned`，不能替代 G/CI 判定。FORMAL-4 两段 p95 均由 SUP-0 精确复现，28/28 FORMAL-4 artifact hash 通过。

## 5. 冻结候选频带

候选表中的 `D` 表示 U4ENC 方向规则通过，`C` 表示 AS01 配置规则通过。冻结的是以下 12 个离散网格窗口；相邻窗口可在绘图中连续展示，但统计仍按原窗口 ID 报告。

| ID | 频率范围（Hz） | 父频带 | 规则 |
|---|---:|---|---|
| P01 | 202.909–251.984 | primary | D+C |
| P02 | 255.649–317.480 | primary | D+C |
| P03 | 322.098–400.000 | primary | D |
| P04 | 405.818–503.968 | primary | C |
| P07 | 811.636–1007.937 | primary | D+C |
| P09 | 1288.392–1600.000 | primary | D+C |
| P11 | 2045.195–2539.842 | primary | D+C |
| P12 | 2576.785–3200.000 | primary | D+C |
| P13 | 3246.545–3973.945 | primary | D+C |
| S01 | 4031.747–5006.857 | secondary | D+C |
| S02 | 5079.683–6308.244 | secondary | D+C |
| S03 | 6400.000–7947.890 | secondary | D+C |

未冻结的窗口为 P05（511.299–634.960 Hz）、P06（644.196–800.000 Hz）、P08（1022.598–1269.921 Hz）和 P10（1623.273–2015.874 Hz）。P08 虽有比值略高于 1 的汇总量，但未满足预先固定的方向对/方向数门禁，因此不进入候选集合。

## 6. SUP-1～SUP-4 统计量与排除规则冻结

后续统一报告三层结果：完整主频带、完整次要频带、上述 12 个候选窗口。候选窗口只用于提高解释性，不取代完整父频带结果。

冻结统计量：

- 条件内三次连续重复的逐频点中位曲线；
- 条件内 repeat dispersion（配对 RMS、median/IQR/p95）；
- 相对共同参考或 BASE 的 raw 与父频带-demeaned ΔdB/RMS；
- effect/floor ratio，分母使用同一父频带/窗口和同一批补充实验 CONT 的 p95；同时保留 SUP-0 floor 作为历史参照；
- SUP-3 条件边际效应的 block/condition-aware bootstrap 95% CI；不把四次单位置替换解释为 Shapley 或独立因果贡献。

冻结排除规则：

1. 只有无法读取、频率/采样率或条件身份错误、数字削波、严重中断、文件损坏、文件名与记录条件不一致的样本可直接 EXCLUDED，并必须记录理由。
2. 普通曲线 outlier 使用“到同条件点位中位曲线的父频带 RMS > median + 3 × 1.4826 × MAD”只加 flag，不自动删除或重测。
3. 只有上述 outlier 同时对应预先记录的技术事故，才可按 `gross_outlier_with_logged_technical_incident` 排除；否则保留在主分析并做敏感性视图。
4. 不因效应小、方向不理想、模块排序不连续或结论变差而排除/重测。
5. SUP-0 冻结后不得根据 SUP-1～SUP-3 的结果改变网格、smoothing、父频带、窗口、统计量或门禁。

## 7. 输出与结论边界

权威输出目录：

```text
outputs/supplemental/SUP-0_FREQUENCY_LOCALIZATION/
```

主要产物：`candidate_bands.csv`、`frequency_window_metrics.csv`、`parent_band_metrics.csv`、方向/配置明细 CSV、`analysis_summary.json`、`run_manifest.json`、频率定位 PNG/SVG 和 SHA-256 manifest。9/9 业务 artifact hash 已核验。

SUP-0 只冻结后续补充实验的描述性频带和统计口径，不改变 FORMAL-5：`supported_with_limits`、`H0=not_rejected`、`H1=not_confirmed`、`scientifically_eligible=false`、`final_test_read=false`。候选窗口本身不是新的确认性证据。

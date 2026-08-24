# SUP-1：ENC-A～H 单入口模块频谱扫描

状态：完成；数据、预处理、QC、模块内重复性和模块间差异均已固化

日期：2026-08-23

分支：`feature/v2-dual-input`

## 1. 执行边界与结论

本步仅分析同一单入口位置下的 ENC-A～H 八个单独模块，目的为判断“模块几何形态改变是否产生可重复、可定位的频谱变化”。模块字母没有被解释为方向，没有进行四方向或八方向分类，也没有执行 SUP-2、SUP-3、分类器优化或 final-test。

在冻结的 200–4000 Hz 主频带内，28/28 个模块对的代表性去均值谱形差及 9/9 个跨重复组合均超过 FORMAL CONT p95 = 0.8793 dB。模块对 effect/floor 比值的中位数为 2.4352，范围 1.5724～3.7052。因此，本批数据支持“固定位置下，不同模块几何形态产生可重复且可定位的频谱差异”，但不支持把 A～H 解释成方向，也不改变 FORMAL-5 的结论边界。

4000–8000 Hz 的 28/28 个模块对也超过该频带的 CONT p95 = 1.3452 dB，中位 effect/floor 为 2.4019；由于这一频带的技术重复底线更高，结果仅作为次要证据。

## 2. 只读清点、命名与原始数据保护

源压缩包：`ENC-A-H.zip`

源压缩包 SHA-256：`ed3eccbfa574c6b83d74fedce2bab80d3895eb77293ddc340f92c8fa00879875`

压缩包中正好有 29 份 TXT，命名均能由末尾的模块字母和两位重复号唯一解析；没有不明确映射，因此未触发停止条件。

| 模块 | 只读清点命名 | 数量 | 结果 |
|---|---|---:|---|
| ENC-A | `R C03_U4ENC_A01.txt`～`A03.txt` | 3 | 符合 |
| ENC-B | `R C03_U4ENC_B01.txt`～`B03.txt` | 3 | 符合 |
| ENC-C | `R C03_U4ENC_C01.txt`～`C03.txt` | 3 | 符合 |
| ENC-D | `R C03_U4ENC_D01.txt`～`D04.txt` | 4 | 符合 |
| ENC-E | `R C03_U4ENC_E01.txt`～`E04.txt` | 4 | 符合 |
| ENC-F | `R C03_U4ENC_F01.txt`～`F04.txt` | 4 | 符合 |
| ENC-G | `R C03_U4ENC_G01.txt`～`G04.txt` | 4 | 符合 |
| ENC-H | `R C03_U4ENC_H01.txt`～`H04.txt` | 4 | 符合 |

逐文件完整命名、sample ID、模块、重复号、大小和 SHA-256 见 `data_inventory.csv`；原始 ZIP 和 29 份 TXT 均未覆盖或修改，工作副本逐文件 hash 已核验。数据以 `data_origin=real_experiment`、`dataset_role=supplemental_research_analysis`、`experiment_step=SUP-1` 单独登记，不与原正式实验或 SUP-0 输入混合。

## 3. 固定预处理与 QC

预处理严格复用 FORMAL-1：200–8000 Hz、48 points/octave 对数网格、1/12-octave dB smoothing；主分析 200–4000 Hz，4000–8000 Hz 只作 secondary。SUP-0 的 12 个候选窗口原样读取，没有改变频带、平滑、窗口或阈值。

29/29 份文件结构有效，0 fail、29 warning。TXT header 可核验 REW V5.31.3、256k、1 repetition、-30 dBFS、No timing reference、raw smoothing=None、48 kHz 推断、iMM-6C 来源和固定测量备注。29 条 warning 仅因为频响 TXT 本身不记录 `CMM29939.txt` 的输入绑定、`Set t=0 at IR peak` 和时域削波证据；这些条件只按本轮外部声明登记，未伪装成 header 验证。

## 4. 四重复取三规则与异常 flag

D～H 的主三重复由预先固定的客观规则选择：在 200–4000 Hz 内枚举四选三，先最小化所选三条中的最大配对 RMS，再最小化配对 RMS 中位数。未入选的第四次仍保留在清单、QC 和敏感性记录中，角色为 `EXTRA_REPEAT_SENSITIVITY`；它们不是删除或自动 EXCLUDED。

| 模块 | 主分析三次 | 第四次敏感性记录 | 曲线异常 flag |
|---|---|---|---|
| A | R01, R02, R03 | — | R01 |
| B | R01, R02, R03 | — | — |
| C | R01, R02, R03 | — | — |
| D | R01, R02, R04 | R03 | R03 |
| E | R01, R02, R03 | R04 | — |
| F | R01, R02, R03 | R04 | R04 |
| G | R01, R02, R03 | R04 | R04 |
| H | R02, R03, R04 | R01 | — |

异常规则为“到同模块中位曲线的主频带 RMS > median + 3 × 1.4826 × MAD”，只 flag、不自动删除。共 4 条 flag：`SUP1-ENC-A-R01`、`SUP1-ENC-D-R03`、`SUP1-ENC-F-R04`、`SUP1-ENC-G-R04`。其中 D/F/G 的 flag 恰为第四次敏感性记录；A-R01 因 A 只有三次而保留在主分析。没有文件损坏、条件身份错误或已记录技术事故，因此不建议只重测任何文件；若未来出现独立技术事故记录，应再单独复核，而不能按谱形结果倒推排除。

## 5. 模块内重复性

| 模块 | 主频带配对 RMS median / max（dB） | median / 0.8793 | 判定 |
|---|---:|---:|---|
| A | 0.9966 / 1.0975 | 1.1334 | 有配对超过底线；保留 A-R01 flag |
| B | 0.2855 / 0.2988 | 0.3247 | 底线内 |
| C | 0.9119 / 0.9900 | 1.0371 | 有配对超过底线；谨慎解释 |
| D | 0.8184 / 0.8208 | 0.9307 | 底线内 |
| E | 0.2044 / 0.2693 | 0.2324 | 底线内 |
| F | 0.2832 / 0.2998 | 0.3221 | 底线内 |
| G | 0.2820 / 0.3327 | 0.3207 | 底线内 |
| H | 0.2254 / 0.2849 | 0.2563 | 底线内 |

六个模块的所选三重复完全位于 FORMAL CONT p95 内；A、C 的模块内离散略高于底线。因此结论依据的不只是代表曲线效应，而是同时要求跨重复组合稳定通过。

## 6. A～H 模块差异

主频带稳定门禁要求：模块对代表性效应超过 0.8793 dB，且 9 个三乘三跨重复组合至少 7 个超过底线。结果为 28/28 个模块对通过，且每一对实际均为 9/9 通过。

最接近的模块对为 E–G（1.5724× floor）、E–F（1.6064×）和 F–G（1.6295×）；差异最大的模块对为 B–D（3.7052×）、A–H（3.3270×）和 A–D（3.2500×）。完整 28 对主/次频带结果见 `module_pair_parent_band_effects.csv`。

## 7. SUP-0 候选频窗

候选窗口稳定门禁沿用同窗 SUP-0 CONT p95：代表曲线效应超过底线，且 9 个跨重复组合至少 7 个超过底线。“单次敏感”表示代表效应超过底线但跨重复门禁未通过，不能当作稳定模块差异。

| 窗口 | Hz | 证据层级 | 稳定 / 单次敏感 / 低于底线（共 28 对） | 判定 |
|---|---:|---|---:|---|
| P01 | 202.909–251.984 | primary | 28 / 0 / 0 | 广泛稳定 |
| P02 | 255.649–317.480 | primary | 28 / 0 / 0 | 广泛稳定 |
| P03 | 322.098–400.000 | primary | 23 / 2 / 3 | 广泛稳定，但非全模块对 |
| P04 | 405.818–503.968 | primary | 18 / 5 / 5 | 仅部分区分；最弱窗口 |
| P07 | 811.636–1007.937 | primary | 24 / 3 / 1 | 广泛稳定，但有重复敏感对 |
| P09 | 1288.392–1600.000 | primary | 27 / 1 / 0 | 广泛稳定 |
| P11 | 2045.195–2539.842 | primary | 26 / 1 / 1 | 广泛稳定 |
| P12 | 2576.785–3200.000 | primary | 28 / 0 / 0 | 广泛稳定 |
| P13 | 3246.545–3973.945 | primary | 25 / 3 / 0 | 广泛稳定，但有重复敏感对 |
| S01 | 4031.747–5006.857 | secondary | 25 / 1 / 2 | 次要证据 |
| S02 | 5079.683–6308.244 | secondary | 23 / 3 / 2 | 次要证据 |
| S03 | 6400.000–7947.890 | secondary | 27 / 0 / 1 | 次要证据 |

P01、P02、P12 对全部 28 个模块对均稳定，最适合作为“可定位差异”的主频带证据；P04 只能部分区分，5 个单次敏感模块对不得解释为稳定差异。完整逐模块对、逐窗口结果见 `module_pair_candidate_window_effects.csv`。

## 8. SUP-2R V2 身份更正

本报告原先把 SUP-2 描述为新的 HOM/HET 采集，这一点已被 2026-08-24 V2 增量规格取代。HOM-A 与 `U4SYM AS01 B01/B02` 完全相同，HET-ABDF 与 `U4ENC AS01 B03/B04` 完全相同；不得重新要求采集。28/28 模块对和固定窗口结果只说明值得复用既有数据开展 SUP-2R 频率/机理再分析，不授权分类器优化、final-test 或扩大采集。SUP-2R 结果见 [SUP_2R_EXISTING_DATA_MECHANISM_REANALYSIS.md](./SUP_2R_EXISTING_DATA_MECHANISM_REANALYSIS.md)。

## 9. 权威产物与验证

权威输出目录：

```text
outputs/supplemental/SUP-1_ENC_MODULE_SCAN/
```

主要表格：`data_inventory.csv`、`file_qc.csv`、`module_repeatability.csv`、`module_pair_parent_band_effects.csv`、`candidate_window_summary.csv`、`module_pair_candidate_window_effects.csv`。主要图：`plots/module_spectra.png`、`plots/module_repeatability.png`、`plots/module_pair_effect_heatmap.png`、`plots/candidate_window_separation.png`。

100 项业务 artifact 的 SHA-256 manifest 已核验；manifest SHA-256 为 `76ed64aac0674244fb20d66390f1bf3c1b538f2ed0ed5fa115129479c35a85dc`。实现调试时产生的两个非权威目录 `_superseded_SUP-1_invalid_200hz_nan` 和 `_superseded_SUP-1_median_tie_rule` 已明确移出权威路径并保留审计痕迹，不得引用为结果。

本轮新增可复现 runner、分析模块和专项测试；最终回归结果与本地提交记录见本报告所在提交和进度索引。没有 push。

# Figure and Table Manifest

Status: frozen WRITE-2 dissertation assets

中文状态：WRITE-2 论文图表已冻结。

- Source commit: `94a26947e6604c1ed25fce71778883bf6e176618`
- Disposition: `supported_with_limits`
- H0: `not_rejected`
- H1: `not_confirmed`
- ACTIVE/EXCLUDED: `72/19`
- final-test: sealed and unread

## Figures

| No. | English / 中文 title | PNG | SVG | Sources | Boundary |
|---|---|---|---|---|---|
| Figure 1 | Continuous-repeat measurement floor / 连续重复测量误差底线 | `figures/figure_01_repeatability_floor.png`<br>`e3199a77798b52a7b1c3c0dacf19d0fd6a4ddaa21d5b4ad23e36e952294e6d63` | `figures/figure_01_repeatability_floor.svg`<br>`e7e36cfdbac781d1aee306f16d0bd476617cc7c268629636259c1ff73753b8e5` | repeatability_frequency.csv; repeatability_summary.csv | supported_with_limits; no superiority or reliable-classification claim |

**Caption EN:** Frequency-dependent pointwise MAD and frozen all-CONT pairwise RMS summaries. CONT repeats are technical repeats, not independent scientific samples.

**图注中文：** 逐频点 MAD 与全部 CONT 配对 RMS 的冻结摘要；CONT 是技术重复，不是独立科学样本。

| Figure 2 | AS01 direction spectra by acquisition block / AS01 各采集 block 的方向频谱 | `figures/figure_02_as01_direction_spectra.png`<br>`4a8ece334b4620224b7d0721b090f994e5eb7d364dde259bf4995593f2861194` | `figures/figure_02_as01_direction_spectra.svg`<br>`215113397cb99ea16023fdf24fea2aca663f7dcaf0ff6174f79f005afb4148d2` | plots/block_direction_B01.png; plots/block_direction_B02.png; plots/block_direction_B03.png; plots/block_direction_B04.png | supported_with_limits; no superiority or reliable-classification claim |

**Caption EN:** Frozen block panels for two U4SYM and two U4ENC REPOS blocks. Visible separation is descriptive until assessed against floor and CI criteria.

**图注中文：** 两组 U4SYM 与两组 U4ENC REPOS block 的冻结面板；可见分离须结合底线和 CI 判定。

| Figure 3 | Primary-band pairwise direction effects / 主频带方向两两效应 | `figures/figure_03_pairwise_direction_effects.png`<br>`ce0a2729e4239c85afd9577b91c4cb2a5294aaff24857928c77b4bb348abfd39` | `figures/figure_03_pairwise_direction_effects.svg`<br>`f83fcea74aa9afb657ab0d36cf8ba2bcf11bd6905a98c9dfbe54e9bb338b4048` | direction_pairwise_effects.csv | supported_with_limits; no superiority or reliable-classification claim |

**Caption EN:** Frozen demeaned effect-to-CONT-p95 ratios. U4ENC had 6/6 and U4SYM 3/6 stable AS01 pairs above the floor; this does not imply classification success.

**图注中文：** 冻结的 demeaned effect/CONT-p95 比值；U4ENC 6/6、U4SYM 3/6 稳定方向对超过底线，但不等于分类成功。

| Figure 4 | Direction-effect gain and confidence intervals / 方向效应增益及置信区间 | `figures/figure_04_direction_gain_and_ci.png`<br>`81f6faaf476e025bc36f47ac99bedb48b991a9c613346a29c9cc63737b0408f5` | `figures/figure_04_direction_gain_and_ci.svg`<br>`9c70fe50b77507ee1ba93c99d16be56d3f4874ecd6a854dbb62b4e230a2d8ae7` | direction_gain_summary.csv; direction_gain_contrasts.csv | supported_with_limits; no superiority or reliable-classification claim |

**Caption EN:** Frozen AS01 G values, 95% CIs, ΔG and normalization views. U4ENC and ΔG confidence intervals cross their confirmatory references.

**图注中文：** 冻结的 AS01 G、95% CI、ΔG 与归一化视图；U4ENC 和 ΔG 的区间跨越确认性参考线。

| Figure 5 | U4ENC–U4SYM configuration-difference curves / U4ENC–U4SYM 配置差值曲线 | `figures/figure_05_configuration_difference.png`<br>`7862e42728f1c075848a1a0fb7958aa9c5fe313260dbe396222138bb13968bcc` | `figures/figure_05_configuration_difference.svg`<br>`58402cbf521620217b2c5ff7cde9e18924a375638f58d6f99d0ecac26ec35e24` | configuration_difference_curves.csv; configuration_effects.csv | supported_with_limits; no superiority or reliable-classification claim |

**Caption EN:** Frozen differences across frequency. AS01 is bounded evidence; AS02 is exploratory because assembly, block and time are confounded.

**图注中文：** 冻结的频率差值；AS01 为有边界证据，AS02 因 assembly、block 与 time 混杂而仅为探索性。

| Figure 6 | Outlier-flag sensitivity / Outlier flag 敏感性 | `figures/figure_06_outlier_sensitivity.png`<br>`58b841bd2a609ec0486fa4da94d6047ce752d5c9f46ab16e16c5274583f7ac60` | `figures/figure_06_outlier_sensitivity.svg`<br>`a1f26b9e2ff0b7b9bdbe13861400879de177c5633fd5732db81c9833d83996aa` | outlier_sensitivity.csv | supported_with_limits; no superiority or reliable-classification claim |

**Caption EN:** All 72 ACTIVE results versus temporary omission of 10 flags. No frozen threshold conclusion or selection changed.

**图注中文：** 全部 72 条 ACTIVE 与临时省略 10 个 flags 的比较；冻结门槛结论和样本选择均未改变。

| Figure 7 | Grouped four-direction classification / 四方向分组分类 | `figures/figure_07_grouped_classification.png`<br>`2dd5cb77718437e12236a3122e89cfa943b4386f8aad793b59493476ac1139b0` | `figures/figure_07_grouped_classification.svg`<br>`dfcb69047c39b03a971d310801586896d97e9372faa976a3162ae9ce25f24113` | plots/grouped_validation_confusion_matrix.png; grouped_validation_metrics.csv | supported_with_limits; no superiority or reliable-classification claim |

**Caption EN:** Frozen leave-one-block-out confusion matrices and scores. Both AS01 balanced accuracies were below the 0.50 practical target.

**图注中文：** 冻结的留一 block 混淆矩阵与分数；两项 AS01 balanced accuracy 均低于 0.50 实用目标。

## Tables

| No. | English / 中文 title | CSV | Markdown | Sources |
|---|---|---|---|---|
| Table 1 | Table 1. Continuous-repeat measurement floor / 表1：全部 CONT 配对 RMS 差的冻结重复性底线。 | `tables/table_01_repeatability_floor.csv`<br>`47d65543388c5280ae5155ceb60f70cbec3c03c5d1ba8ebc8ecc1784d7fb41aa` | `tables/table_01_repeatability_floor.md`<br>`5a42c9ab13ebc704eda9d21e80bc7bc44bb1d6578ba34337916974be10d4e3b0` | repeatability_summary.csv |
| Table 2 | Table 2. Frozen direction-effect gains and confidence intervals / 表2：AS01 方向效应增益及 95% 置信区间；ΔG 为 U4ENC 减 U4SYM。 | `tables/table_02_direction_gain.csv`<br>`65576617fbc0fe7791a1c9d3af84059124b578c6cdd70e21776950cfadd2f200` | `tables/table_02_direction_gain.md`<br>`3498c04aec4bc2e7430dc7759c9b18c35d89f588941851cd24bc823299279226` | direction_gain_summary.csv; direction_gain_contrasts.csv |
| Table 3 | Table 3. AS01 grouped direction-classification performance / 表3：AS01 留一 block 分组分类；CONT 重复在划分前聚合。 | `tables/table_03_grouped_classification.csv`<br>`1eb16795a5c5c4e8d3fd29047a85f1e8aaad81da7a8047f5a76d3f4089434e1a` | `tables/table_03_grouped_classification.md`<br>`6ab2d37efcf3a4af41232c973bd5fd38a98728fdf88acf003dbe1a559e2a60ac` | grouped_validation_metrics.csv |
| Table 4 | Table 4. Outlier-flag sensitivity / 表4：主分析保留全部 72 条 ACTIVE；临时省略 flags 未改变冻结结论。 | `tables/table_04_outlier_sensitivity.csv`<br>`c5a4c78fe568330d16ce34c3c430d2a7bc541533758ddd7a00f0e0e29012bc4a` | `tables/table_04_outlier_sensitivity.md`<br>`8fae9fc0445af025f786930bb4f8d4e3378238a722cfdc31ee8a2f28c3fe7761` | outlier_sensitivity.csv |

## Reproduction

All assets were generated by `scripts/build_dissertation_results_assets.py` (SHA-256 `01bd5cdbd687f0fd617cfa8a2081013b4894ac4a045e7976b1a5a99f600152ab`).

```powershell
python scripts/build_dissertation_results_assets.py
```

The generator refuses existing output paths. It reads explicit frozen artifacts only and does not scan raw measurements.

## Scientific boundary

The figures and tables preserve `supported_with_limits`, H0 `not_rejected`, and H1 `not_confirmed`. AS02 and all-assembly content is exploratory. `scientifically_eligible=false` and `final_test_read=false` remain unchanged.

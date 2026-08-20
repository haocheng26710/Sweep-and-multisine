# FORMAL-4：精简正式实验核心定量分析

状态：完成；核心产物可进入 FORMAL-5 综合审查，但本步不授予科研结论资格

日期：2026-08-20

分支：`feature/v2-dual-input`

## 目标、边界和权威入口

本步仅从 FORMAL-3 权威输出读取冻结的 72 份 ACTIVE FeatureSet，执行 CONT 重复性、方向差异、配置差异、组装集差异、outlier 敏感性和严格分组的方向分类。没有重扫原始 ZIP/目录，没有根据文件名重新确定身份，没有修改 ACTIVE/EXCLUDED，没有采集新数据，没有执行逐频点未校正显著性检验，也没有读取 final-test。

唯一输入目录：

```text
outputs/formal/FORMAL-3_REAL_IMPORT_QC/
```

输入代码提交为：

```text
34f7c61fd04b6fcf5708335997deffc990a98504
```

入口在分析前 fail closed 核验：

- `ready_for_formal_analysis=true`；
- ACTIVE `72`、EXCLUDED `19`，两者身份无交叉；
- REV003 ZIP SHA-256：`cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb`；
- FORMAL-3 run manifest SHA-256：`1ecf1179d66f654f1dadd0fc58eba60cdb956f92ca9c74983d7d6fb00c27afe9`；
- FORMAL-3 artifact manifest SHA-256：`9aa329a730066f4487ac4a77f8700dca40862fec71a46d53817a7dc4d8d9e850`；
- FORMAL-3 受管 artifact：`225/225` hash 匹配；
- 72 份 `dense_raw_spl` FeatureSet 使用同一 preprocessing ID、同一 256 点 FORMAL-1 对数网格和同一 valid mask；
- 每份 FeatureSet 为 `255/256` 有效点，唯一无效点是禁止外推的 200 Hz 边界点；
- EXCLUDED 进入分析、特征、训练或结果的数量为 `0`；
- `final_test_read=false`。

## 冻结分组与实际频带

| Block | Configuration | Assembly | REPOS | Session | 曲线数 |
|---|---|---|---|---|---:|
| B01 | U4SYM | AS01 | RP01 | S01 | 12 |
| B02 | U4SYM | AS01 | RP02 | S01 | 12 |
| B03 | U4ENC | AS01 | RP01 | S02 | 12 |
| B04 | U4ENC | AS01 | RP02 | S02 | 12 |
| B05 | U4ENC | AS02 | RP01 | S03 | 12 |
| B07 | U4SYM | AS02 | RP01 | S04 | 12 |

每个 block 有 0°、90°、180°、270°，每方向三次 CONT。主分析先在每个 `block × direction` 内计算三条 ACTIVE 曲线的逐频点中位数，三次 CONT 从未被当作三个独立科学样本。

实际有效网格边界为：

| 频带 | 有效点 | 实际首末点 |
|---|---:|---|
| 主频带 | 207 | 202.909066988–3973.94499864 Hz |
| 次要频带 | 48 | 4031.74735966–7947.88999727 Hz |
| 全频带 | 255 | 202.909066988–7947.88999727 Hz |

200 Hz 没有可用插值支撑，因此保持 invalid；未外推、补零或回退到线性网格。主/次频带均使用 FORMAL-1 已完成的 1/12-octave dB smoothing。

## 分析方法

### CONT 重复性底线

每个 block×direction 的三条曲线构成三组配对。每个频带计算：

- 每一配对的 RMS dB 差；
- 所有配对×频点绝对差的 median 与 95th percentile；
- 逐频点 MAD 与 sample SD；
- 24 个 cell、72 个配对总体分布的 median、IQR 和 95th percentile。

重复性底线使用全部重复，不选择最优配对。

### 方向效应和 `G`

每个 block 内对四条方向中位数曲线构造全部 6 个方向对，分别计算 raw、sample-demeaned 和 sample-zscore RMS 距离。方向对若在同一频带的 demeaned RMS 高于全部 CONT 配对 RMS 的 95th percentile，则记为“明显超过测量底线”。只有在 AS01 的两个 REPOS block 均超过时，才列入稳定方向对。

协议主指标使用：

```text
G = median(within-block between-direction RMS)
    / median(matched-direction cross-REPOS RMS)
```

AS01 每种 configuration 有两个 REPOS block，因此可估计；AS02 只有一个 block，G 的 REPOS 分母为 `not_estimable`。95% CI 使用预先固定的 2000 次 block-cluster + direction-REPOS resampling；`ΔG=G(U4ENC)-G(U4SYM)` 另行做配置间 bootstrap，不能由两个单独 CI 猜测。

### 配置与组装集

- AS01：B01/B02 对 B03/B04；先形成 block×direction 稳健曲线，再保留 2×2 block 配对和 configuration 代表曲线。
- AS02：B07 对 B05；每种 configuration 只有一个 block，始终标为 exploratory。
- AS01 对 AS02：按 configuration 和 direction 比较，但 AS02 单 block 且采集时间不同，因此 `block/time/assembly` 混杂；只输出观察差异，禁止强因果解释。

### 分组分类

分类使用既有权威 `nearest_centroid` 数值语义，输入为主频带、demeaned 的 block×direction 中位数曲线。验证协议固定为 leave-one-block-out；一个 block×direction 的全部 CONT 先聚合，绝不跨训练/测试边界。

- AS01 每 configuration 两个 block：2 folds、8 predictions，状态 `estimable_limited`；
- AS02 单 block：`not_estimable`；
- 合并 AS01/AS02 的三 block 结果仅标记 exploratory；
- 每个可估计 scope 执行 999 次确定性、block 内标签置换基线；
- 机会水平 25%，冻结实用目标 50%。

## 数值结果

### 1. 重复性底线

| 频带 | median RMS | IQR | 95th percentile | min–max |
|---|---:|---:|---:|---:|
| 主频带 | 0.3783 dB | 0.2191 dB | 0.8793 dB | 0.2082–1.2569 dB |
| 次要频带 | 0.7687 dB | 0.3357 dB | 1.3452 dB | 0.3257–1.6590 dB |
| 全频带 | 0.5057 dB | 0.2274 dB | 0.9162 dB | 0.2626–1.2015 dB |

主频带的稳健 CONT 测量误差底线为 median `0.3783 dB`，保守 95th percentile 为 `0.8793 dB`。次要频带重复误差明显更高，因此 4–8 kHz 结果保持次要/敏感性定位。

### 2. 方向效应

AS01 主频带：

| Configuration | G_raw | G_demeaned | 95% CI | G_zscore |
|---|---:|---:|---:|---:|
| U4SYM | 0.6925 | 0.6824 | 0.6105–1.2699 | 0.7034 |
| U4ENC | 1.2619 | 1.2805 | 0.8297–1.7667 | 1.3292 |

点估计满足 `G_demeaned(U4ENC)>1` 且高于 U4SYM；`ΔG_demeaned=0.5982`。但是：

- U4ENC 的 95% CI 下限为 `0.8297`，未高于 1；
- `ΔG_demeaned` 95% CI 为 `-0.1131–1.0843`，下限未高于 0；
- 因此冻结的 CI 成功门槛没有通过，不能判定 H1 已获得充分支持。

相对 CONT 95th-percentile 底线，AS01 两个 REPOS block 均稳定超过底线的主频带方向对为：

- U4ENC：6/6（全部方向对）；
- U4SYM：3/6（0–90、90–270、180–270）。

这说明曲线中存在超过技术重复误差的方向差异，但跨 REPOS 的总体主指标不确定性和分类结果仍限制强结论。

### 3. U4SYM 与 U4ENC 配置差异

AS01 四方向的代表曲线 demeaned RMS 差及相对 CONT p95 底线比为：

| 方向 | Demeaned RMS | 相对底线比 |
|---|---:|---:|
| 0° | 1.1765 dB | 1.3381 |
| 90° | 1.6854 dB | 1.9169 |
| 180° | 1.5413 dB | 1.7530 |
| 270° | 1.2174 dB | 1.3846 |

四方向均超过 CONT p95 底线，四方向比值中位数为 `1.5688`。这支持“两个配置的观察频谱不同”，但不能替代方向信息的 G/CI 与 grouped classification 判定。

AS02 的四方向配置差也都超过 CONT p95，但每种 configuration 仅一个 block，结果标为 `exploratory_single_block`。

### 4. AS01 与 AS02

主频带 AS01–AS02 demeaned 距离均超过 CONT p95：

- U4SYM 四方向比值范围 `1.6675–1.9703`，中位数 `1.9354`；
- U4ENC 四方向比值范围 `1.4144–1.7737`，中位数 `1.7412`。

差异大小超过技术重复底线，但 AS02 每种 configuration 只有一个 block，且 assembly set 与 block/time 同时变化，所以只能说“观察到稳健幅度差异”；不能把差异唯一归因于 assembly set。

### 5. Outlier 敏感性

FORMAL-3 的 10 条 flag 在 primary analysis 中全部保留；sensitivity analysis 只在临时计算视图中略去 flag，不修改 ACTIVE/EXCLUDED manifest。

| 指标 | 全部 ACTIVE | 略去 flag |
|---|---:|---:|
| 主频带 CONT floor median | 0.3783 dB | 0.3739 dB |
| U4SYM G_demeaned | 0.6824 | 0.7051 |
| U4ENC G_demeaned | 1.2805 | 1.2790 |
| ΔG_demeaned | 0.5982 | 0.5739 |
| AS01 configuration/floor ratio | 1.5688 | 1.4423 |
| U4SYM grouped BA | 0.375 | 0.375 |
| U4ENC grouped BA | 0.250 | 0.250 |

所有冻结阈值结论均未改变。U4SYM 稳定方向对数量由 3 降至 2，但“至少存在超过底线的方向对”这一描述性状态不变。敏感性排除没有写回任何 selection 文件。

### 6. Grouped validation

| Scope | 状态 | BA | Macro-F1 | permutation p |
|---|---|---:|---:|---:|
| U4SYM AS01 | estimable_limited | 0.375 | 0.250 | 0.317 |
| U4ENC AS01 | estimable_limited | 0.250 | 0.183 | 0.760 |
| U4SYM AS02 | not_estimable | — | — | — |
| U4ENC AS02 | not_estimable | — | — | — |
| U4SYM all assemblies | exploratory | 0.250 | 0.162 | 0.696 |
| U4ENC all assemblies | exploratory | 0.500 | 0.435 | 0.049 |

确认性 AS01 的两项 grouped BA 均未达到 50% 实用目标；U4ENC AS01 等于 25% 机会水平。合并 assembly 的 U4ENC 结果达到 50%，但它混合 assembly/time 且只有三个 blocks，因此只可作为 exploratory，不得用来覆盖 AS01 的确认性不足。

## 回答 FORMAL-4 七个问题

1. 重复性底线：主频带 CONT pairwise RMS median `0.3783 dB`、IQR `0.2191 dB`、p95 `0.8793 dB`；次要频带更差。
2. 方向差异：U4ENC 在 AS01 两个 REPOS blocks 的全部 6 个方向对均超过 CONT p95；U4SYM 为 3 个。但 U4ENC G 的 CI 跨 1，不能给出确认性通过结论。
3. U4SYM/U4ENC：AS01 四方向配置差均超过 CONT p95；U4ENC G 点估计高于 U4SYM，但 ΔG CI 跨 0。
4. AS01/AS02：差异幅度超过 CONT 底线，但与 block/time 混杂，只能 exploratory。
5. Outlier：略去 10 条 flag 不改变冻结阈值结论；ACTIVE/EXCLUDED 未改变。
6. 可进入后续综合的结果：AS01 block-aware 重复性、方向距离、G/CI、配置差和 grouped validation 可进入 FORMAL-5 审查；AS02 配置差、AS01/AS02 比较、合并 assembly 分类和 4–8 kHz 只可标为 exploratory/secondary。
7. `ready_for_formal_synthesis=true`：表示产物完整、hash 审计通过，可以进入 FORMAL-5 综合审查；不表示 H1 通过或获得科研资格。

## 输出

权威输出目录：

```text
outputs/formal/FORMAL-4_CORE_ANALYSIS/
```

结构化输出：

- `repeatability_by_cell.csv`
- `repeatability_frequency.csv`
- `repeatability_summary.csv`
- `direction_pairwise_effects.csv`
- `direction_effect_summary.csv`
- `direction_gain_summary.csv`
- `direction_gain_contrasts.csv`
- `configuration_effects.csv`
- `configuration_difference_curves.csv`
- `assembly_set_effects.csv`
- `assembly_set_difference_curves.csv`
- `outlier_sensitivity.csv`
- `grouped_validation_metrics.csv`
- `grouped_validation_predictions.csv`
- `analysis_summary.json`
- `run_manifest.json`
- `artifact_manifest.json`
- `SHA256SUMS`

图表：

- `plots/block_direction_B01.png` 至 `B07.png`（6 个实际 ACTIVE blocks）；
- `plots/repeatability_frequency.png`；
- `plots/direction_pairwise_heatmap.png`（六图共享同一色标）；
- `plots/configuration_difference.png`；
- `plots/effect_to_repeatability_ratio.png`；
- `plots/outlier_sensitivity.png`；
- `plots/grouped_validation_confusion_matrix.png`。

最终 hash：

- 受管业务 artifact：`28/28` 匹配；
- `artifact_manifest.json` SHA-256：`6744b7142480a20a631ff6a33f763329e852b4086ba5f05d53301beb6853d4ef`；
- `run_manifest.json` SHA-256：`f023c703907032df6dc2956cdf698767eb834f96f2aa1d7e612021f17990efdb`；
- `analysis_summary.json` SHA-256：`676bbb71a5860c633edadb68ff34da6c3a8e51b3d8438003be8bd2e489edb71f`；
- `SHA256SUMS` SHA-256：`e8f6cc41bb688fa110c9b73ac5c1f7c621631bfe98deaaa6bca1956776cd259b`。

开发过程中产生的非最终受控输出被移入 ignored 的 `outputs/formal/_superseded_formal4_pre_delta_ci/`，没有覆盖或删除；它们不是权威结果。

## 修改文件

- `src/acoustic_encoder/formal_core_analysis.py`
- `scripts/run_formal4_core_analysis.py`
- `tests/test_formal_core_analysis.py`
- `docs/progress/FORMAL_4_CORE_ANALYSIS.md`
- `docs/progress/INDEX.md`

未修改算法协议、FORMAL-1/FORMAL-3 schema、配置、ACTIVE/EXCLUDED 或 final-test。

## 验证命令和准确结果

专项测试（红—绿：最初因模块不存在而 collection failed，完成实现后）：

```powershell
python -m pytest -q tests/test_formal_core_analysis.py
```

最终结果：`5 passed in 21.58s`。

专项与相关回归：

```powershell
python -m pytest -q tests/test_formal_core_analysis.py tests/test_formal_real_import_qc.py tests/test_formal_preprocessing.py tests/test_metrics.py tests/test_classification.py tests/test_direction_models.py tests/test_schemas.py
```

最终结果：`87 passed in 17.32s`。

全量：

```powershell
python -m pytest -q
```

最终结果：`897 passed in 272.65s (0:04:32)`。

字节码和差异检查：

```powershell
python -m compileall -q src scripts
git diff --check
```

结果：两条命令均无输出、退出码 0。

## Provenance、限制与下一步

本步固定：

```text
data_origin=real_experiment
dataset_role=research_analysis
run_purpose=research_analysis
scientifically_eligible=false
final_test_read=false
```

主要限制为：精简数据只有 72/96；AS02 缺 RP02（B06/B08），不能形成 AS02 的 REPOS 分母；AS01 每 configuration 也只有两个独立 blocks；TXT header 的 calibration filename 仍 unavailable；10 条 outlier 只能 flag；分类预测数量少；bootstrap CI 反映当前有限 block 结构，不可被解释为大样本精确区间。

下一步只能进入 FORMAL-5 综合审查，结合 QC、物理指标优先级、置信区间、分类不足和 exploratory 边界决定论文可报告范围。FORMAL-5 之前 `scientifically_eligible` 保持 false；final-test 继续 sealed。

对应 Git 提交：本报告、实现和测试位于同一提交 `feat(formal): analyse streamlined real measurements`。

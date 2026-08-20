# FORMAL-5：正式实验最终综合审查与结论冻结

状态：完成；最终 disposition 为 `supported_with_limits`

日期：2026-08-20

分支：`feature/v2-dual-input`

## 目标与严格边界

本轮仅综合 FORMAL-0/2/2A、FORMAL-3 与 FORMAL-4 已冻结的 manifest、CSV/JSON 和证据。没有重新导入 REW TXT、扫描原始目录、改变 72 ACTIVE/19 EXCLUDED、事后删除 10 条 outlier flags、调整阈值、增加显著性检验、搜索模型、采集新数据或读取 final-test。

FORMAL-5 入口先执行以下 fail-closed 核验：

- FORMAL-3 `ready_for_formal_analysis=true`、ACTIVE/EXCLUDED=`72/19`；
- 输入 ZIP SHA-256 为 `cfbaa7a3c300b8443d934462386e9a5faad74d2b2cf0a50292d8c08423f7b4cb`；
- FORMAL-3 的 `225/225` artifact hash 通过；
- FORMAL-4 `ready_for_formal_synthesis=true`、72 份 FeatureSet、每份 255 个共同有效点；
- FORMAL-4 的 `28/28` artifact hash 通过；
- FORMAL-4 引用的 FORMAL-3 run/artifact manifest hash 与当前权威产物完全一致；
- headline 数字与 `repeatability_summary.csv`、`direction_gain_summary.csv`、`direction_gain_contrasts.csv`、`configuration_effects.csv`、`grouped_validation_metrics.csv` 和 `outlier_sensitivity.csv` 逐项一致；
- FORMAL-2A-FIX 的 iMM-6C 输入校准绑定为 `verified`，校准文件及截图 hash 匹配；
- FORMAL-3/4、采集状态和校准证据均为 `final_test_read=false`。

代码入口只读取以上显式文件。最终 manifest 明确记录 `raw_directory_scanned=false`、`raw_txt_reimported=false`、`sample_selection_changed=false`、`thresholds_changed=false`、`model_search_performed=false` 和 `new_statistical_tests_performed=false`。

## 冻结证据

### 重复性底线

主频带 CONT 两两 RMS dB 差：

| 统计量 | 结果 |
|---|---:|
| median | 0.3783 dB |
| IQR | 0.2191 dB |
| p95 | 0.8793 dB |

该分布包括所有 CONT 配对，不挑选最佳重复；CONT 仍只是技术重复，未被当成独立科学样本。

### 方向主指标与配置差异

| 指标 | 点估计 | 95% CI | 冻结门槛裁决 |
|---|---:|---:|---|
| U4ENC `G_demeaned` | 1.2805 | 0.8297–1.7667 | 点估计 >1；CI 下限未 >1 |
| U4SYM `G_demeaned` | 0.6824 | 0.6105–1.2699 | CI 未完全位于门槛一侧 |
| `ΔG_demeaned` | 0.5982 | -0.1131–1.0843 | 点估计 >0；CI 包含 0 |

- U4ENC：6/6 方向对在两个 AS01 REPOS blocks 中超过 CONT p95；
- U4SYM：3/6 方向对满足同一稳健条件；
- AS01 U4ENC−U4SYM 配置差异的 median effect/floor ratio 为 `1.5688`，四个方向均超过 CONT p95；
- 以上支持“存在可测差异”，但 `ΔG` CI 包含 0，因此不能写成“U4ENC 已被证明更优”。

### Grouped validation 与 outlier 敏感性

| AS01 scope | Balanced accuracy | Macro-F1 | 冻结 50% 实用目标 |
|---|---:|---:|---|
| U4SYM | 0.375 | 0.250 | 未达到 |
| U4ENC | 0.250 | 0.183 | 未达到 |

当前数据不支持稳定方向分类。10 条 FORMAL-3 outlier flags 全部留在 primary analysis；仅 sensitivity view 暂时略去。敏感性结果没有改变任何冻结阈值结论，ACTIVE/EXCLUDED 仍为 72/19。

## 研究问题与假设裁决

| 项目 | 裁决 | 允许解释 |
|---|---|---|
| H0 | `not_rejected` | 存在可测方向差异，但完整 H0 仍不能拒绝 |
| H1 | `not_confirmed` | 点估计方向符合 H1，确认性 CI 门槛未全部通过 |
| 方向变化超过误差底线 | `supported` | U4ENC 6/6、U4SYM 3/6 稳定方向对超过底线 |
| U4ENC 方向性强于 U4SYM | `partially_supported` | 仅可写“点估计更高”，不可写“已证明更高” |
| 两配置存在可测差异 | `supported_with_limits` | AS01 block-aware 差异超过 CONT 底线 |
| 可靠方向分类 | `not_supported` | AS01 grouped BA 均低于 0.50 |
| AS01/AS02 无混杂比较 | `exploratory_only` | AS02 单 block，assembly 与 block/time 混杂 |

最终三选一 disposition：`supported_with_limits`。这表示可在严格边界下继续论文 Results/Discussion，而非确认 H1、获得部署能力或证明稳定方向分类。不要求为完成当前受限论文强制补测或重设计；增加独立 AS02 blocks/sessions 仅为 `optional` 后续验证。

## 论文可用与禁止表述

可以写入 Results：

- 主频带重复性底线及其稳健分布；
- AS01 中超过底线的方向相关频谱差异；
- U4ENC/U4SYM 的 G 点估计、95% CI 和 `ΔG` CI；
- AS01 的可测配置差异；
- grouped classification 未达到预设实用目标这一负结果；
- outlier 敏感性没有改变冻结裁决。

只能标为 exploratory：AS02、AS01/AS02 组装集比较、合并 assemblies 的分类以及次要 4–8 kHz 结果。

禁止声称：H1 已确认、U4ENC 已证明优于 U4SYM、四方向可稳定识别、AS01/AS02 差异具有无混杂因果解释、final-test 泛化、真实 Multisine/P8 或部署资格已经获得。

摘要建议句：

> 在本研究的普通房间与有限重复条件下，编码结构产生了超过测量重复性底线的方向相关频谱变化，其方向性效应点估计高于对称结构，但组间差异和方向分类性能未达到预设的确认性标准。

## 生成物与 hash

权威输出目录：

```text
outputs/formal/FORMAL-5_FINAL_SYNTHESIS/
```

| 文件 | SHA-256 |
|---|---|
| `final_evidence_summary.md` | `cbaa8ecb5445a88b477ee975eb3df793ee56aec50da7143581e01b1ec92fd095` |
| `hypothesis_decision_table.csv` | `93f9ebc02cc3cbc6cca14e0d1e90b7c95e95394bdc59e0f76a94b0c738329ae7` |
| `dissertation_results_draft.md` | `eea4df38e8b65162aa27c949be084a43af33e20001272b5e9a1d32d2c3c0bd55` |
| `dissertation_figure_index.csv` | `09218da6db038bfc3ad7325fcfb7aba6c6069691f71e4ed610f919ffd026e58f` |
| `final_claim_boundary.json` | `ff2f4e97edb841e48e6db246f8ec64a2115fd900437e1e88af3f446ac2e8384f` |
| `final_analysis_manifest.json` | `1541ba6b238f37eb69e6ed5012e949206b7ccd5be22558f4dad31b0d45f8e374` |
| `artifact_manifest.json` | `2134cd1d42de0ac136dd41d1a30b71f049835a822a17b9f88ed41d8fd76bc907` |
| `SHA256SUMS` | `89f24f26dd76a1282524ba3527c9fa926acfd5767118b97032b7b4d338aa5de6` |

六项业务产物 `6/6` hash 匹配；artifact manifest 与 `SHA256SUMS` 复核通过。输出目录不可覆盖。

## 修改文件

- `src/acoustic_encoder/formal_final_synthesis.py`
- `scripts/run_formal5_final_synthesis.py`
- `tests/test_formal_final_synthesis.py`
- `docs/progress/FORMAL_5_FINAL_SYNTHESIS.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

没有修改研究协议、算法阈值、schema/config、FORMAL-3/4 权威结果、ACTIVE/EXCLUDED、原始 ZIP/TXT、final-test 或实验数据。

## 实际验证命令与结果

TDD 首个红灯是 `ModuleNotFoundError: acoustic_encoder.formal_final_synthesis`；随后按冻结数值校验、immutable bundle、selection/final-test 门禁、hash 篡改检测和 CSV 数字追溯逐条实现。

```powershell
python -m pytest -q tests/test_formal_final_synthesis.py
```

结果：`8 passed in 0.65s`。

```powershell
python -m pytest -q tests/test_formal_final_synthesis.py tests/test_formal_core_analysis.py tests/test_formal_real_import_qc.py tests/test_formal_preprocessing.py tests/test_formal_acquisition.py tests/test_formal_calibration_registration.py tests/test_formal_calibration_input_evidence_fix.py
```

结果：`53 passed in 18.11s`。

```powershell
python -m pytest -q
```

结果：`905 passed in 263.54s (0:04:23)`。

```powershell
python -m compileall -q src scripts
git diff --check
```

结果：两条命令均无输出、退出码 0。

## 科研资格、限制与结束状态

```text
data_origin=real_experiment
dataset_role=research_analysis
run_purpose=research_analysis
scientifically_eligible=false
final_test_read=false
final_test_status=sealed
```

`scientifically_eligible=false` 是冻结门禁的诚实结果：上游 artifact 未被追溯性升级，确认性 CI/分类门槛未全部通过，FORMAL-2 仍保存外置备份、几何/环境、签署、人工预检和授权等治理限制。它表示论文证据必须标为 `supported_with_limits`/exploratory，而不是软件失败。本轮是正式实验流程的最后一轮；若撰写论文，必须继续遵守本报告和 `final_claim_boundary.json`。

对应本地提交：`docs(formal): freeze final experimental conclusions`（本报告、实现、测试与文档同一提交；未 push）。

# DEV-C7 / P4-B：频带、配置与跨测量模式通用指标

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 单一提交边界：P4-B 类型化核心、显式 scope/input CLI、稳定输出、配置迁移、模拟验证、测试和文档位于同一提交 `feat(metrics): add band and cross-mode comparison metrics`
- push：本步只创建本地提交，不 push

## 目标与验收标准

本步只消费已经持久化的 `FeatureSet`、显式 `ComparisonAnalysisScope`、可选且严格核验的 `DatasetQCReference/DatasetQCResult` 和已解析配置。它不读取 TXT/WAV、不重跑 P8、不扫描目录找样本，也不在 P4-B 内重建 P3 变换。验收目标是完整报告预定义频带、U4SYM/U4ENC 描述性比较、matched-tone 跨模式指标、逐 tone bias、REPOS reliability、weighted 补充指标和 effective rank/morphology gain，同时维持 P2-B canonical 门禁和 P9 边界。

## 完成范围

1. 新增 `ComparisonAnalysisScope` 1.0：显式列出有序 measurement、角色、方向、受控 physical state、选择理由、每个 FeatureSet artifact/content hash 和显式 `match_pair_id`；支持 JSON round-trip 和 canonical scope hash。
2. 新增固定的四种频带边界语义：`closed`、`left_closed_right_open`、`left_open_right_closed`、`open`。每个配置频带均保留输出；空频带或特征数不足为 `unavailable`，不会自动改选频带。
3. 每个 configuration/FeatureKind/preprocessing contract 使用 scope 级固定公共 mask。频带实现仅创建该 mask 的只读切片视图；不插值、不填零、不外推、不逐 pair 改变 tone 集。
4. 复用 P4-A 的 direction pair、CONT/REPOS/REASM、effective-rank 和 morphology-gain 实现；共享的 vector metric 与 repeat-pair 规则没有第二套定义。
5. U4 比较固定为 `delta = U4ENC - U4SYM`。只有定义为非负且分母大于配置下限的指标才给 ratio；否则保留明确 unavailable reason。
6. 跨模式只接受显式一对一配对。重复 pair、一对多、mode/kind、direction/configuration/state、session/repeat/assembly/block、tone identity/schema 和 scope-role 不一致均明确拒绝。
7. bias 符号固定为 `multisine_db - sweep_projection_db`。绝对量要求 dB units、`normalization=none`、相同 magnitude quantity，以及共享 calibration ID 或 magnitude reference；不满足时绝对 bias/RMS 为 unavailable，只有 shape contract 合格时保留 centered 指标。
8. reliability 只使用 development/training 中合格的 REPOS pair；final_test 被拒绝，CONT/REASM 不会替代。primary unweighted 指标始终保留，weighted RMS/Euclidean 仅作补充。
9. 新增显式 input-manifest 1.0、CLI 和失败 manifest。每个 NPZ/JSON 路径及 SHA-256 必须列明并逐项复核，输入顺序必须与 scope 完全一致；不进行目录发现。
10. 写出 12 个稳定 CSV、权威 JSON、manifest 和 manifest SHA-256；loader 复核所有 artifact hash、result hash 和 scope round-trip；已有输出目录拒绝覆盖。
11. 保留原有 `canonical_ready=false` 模拟 fixture 的拒绝测试，并新增同条件至少四个 reference 的 96-measurement 模拟 fixture，使 P2-B `canonical_ready=true`，验证 canonical P4-B 正向代码路径；其科研资格仍为 false。

## 明确未完成和非范围

- 不做 tone 候选评分、tone selection、自动寻找最佳频带或任何 P9 编排。
- 不学习或应用 affine/bias calibration；本步只报告 bias。
- 不做 P5/P6、跨模式分类、快速部署接口或科研结论。
- 不更改 P4-A 数学定义，不修改 P2-B 判定，不自动排除 measurement/tone。
- 不冻结真实实验频带、reliability floor/clip 或 ratio 阈值。
- 本步未生成可选 PNG；结构化 CSV/JSON 是权威、可复核输出。

## 数学定义与兼容规则

全 scope 公共特征集合为：

```text
J = intersection_i(valid_mask_i) ∩ predefined_band
```

所有距离和相关性只在固定 `J` 上计算。频带 slice 以 `J` 为自身向量域调用 P4-A，因此 P4-A 的 `minimum_common_valid_fraction` 分母是声明频带，而不是完整原向量；该过程没有改变数值或制造有效点。

对向量 `x,y`：

```text
rms       = sqrt(mean((y-x)^2))
euclidean = sqrt(sum((y-x)^2))
mad       = median(abs(y-x))
bias      = y_multisine - x_sweep
centered_rms = rms((y-mean(y)) - (x-mean(x)))
```

Pearson 和 cosine 复用 P4-A 的 degenerate-vector unavailable 规则。逐 tone 输出 mean/median bias、sample standard deviation、MAD、IQR、pair/direction/missing count；unavailable 不写成零。

P4-A effective rank 原样复用：

```text
p_i = sigma_i / sum(sigma)
effective_rank = exp(-sum(p_i * log(p_i)))
```

没有使用奇异值平方。Morphology gain 原样复用：

```text
G = median(between-direction sample-pair distance)
    / median(within-direction REPOS distance)
```

REPOS 缺失或分母低于 P4-A 下限时 unavailable。Reliability 为：

```text
s_j   = median(abs(x_a,j - x_b,j))  over qualified REPOS pairs
raw_j = 1 / max(s_j, floor_db)^2
clip_j = min(raw_j, maximum_raw_weight)
w_j   = clip_j / mean(clip over available tones)
```

因此有效 tone 上 `mean(w)=1`。Weighted RMS 为 `sqrt(sum(w*(y-x)^2)/sum(w))`，weighted Euclidean 为 `sqrt(sum(w*(y-x)^2))`。

## P2-B、P4-A、P4-B 与 P9 边界

- P2-B 是 dataset completeness/outlier/repeatability 与 canonical readiness 的权威。
- P4-A 是 direction metric、repeat-pair、effective-rank 和 G 数学定义的权威。
- P4-B 只做预定义频带、configuration 和显式 matched-mode 的通用描述性比较及持久化。
- P9 仍负责未来 tone 候选/选择、bridge/calibration workflow；P4-B 没有产生 candidate score 或 selection decision。

`provisional_software_validation` 可在没有 P2-B reference 时运行，但明确 `canonical_analysis=false`。`canonical_cohort` 必须精确匹配 P2-B scope ID、ordered sample IDs、FeatureSet/P2-A/result hashes 且 `canonical_ready=true`；额外未被 P2-B 审计的 FeatureSet 也会被拒绝。

## Schema、配置、API 与迁移

| 项目 | DEV-C6 | DEV-C7 |
|---|---:|---:|
| pipeline | `2.0.0-dev.12` | `2.0.0-dev.13` |
| config schema | `2.11.0` | `2.12.0` |
| measurement schema | `2.4.0` | 不变 |
| feature schema | `2.2.0` | 不变 |
| single-run manifest | `1.6.0` | `1.7.0` |
| ComparisonAnalysisScope/Input/Result/manifest | 不存在 | `1.0.0` |

配置新增 strict `comparison_metrics`：预定义频带、U4 baseline/candidate 与 ratio denominator、cross-mode minimum tones/shape policy/bias sign、REPOS reliability source role/floor/clip/count/mean-one normalization。全部标记 `provisional: true`。2.11/2.4/2.2 配置只在内存迁移到 2.12，产生 warning，不重写源 YAML；方法专用字段、枚举、范围、唯一 band ID、baseline/candidate 差异及 final_test 防泄漏均验证。

主要 API：

```python
analyze_comparison_feature_sets(...) -> ComparisonMetricsResult
compute_band_metrics(...)
compute_cross_mode_metrics(...)
compute_tone_reliability(...)
write_comparison_metrics_outputs(...)
load_comparison_metrics_bundle(...)
run_comparison_metrics_cli(...)
```

## 修改文件

核心：

- `src/acoustic_encoder/comparison_metrics.py`
- `src/acoustic_encoder/comparison_metrics_outputs.py`
- `src/acoustic_encoder/comparison_metrics_cli.py`
- `src/acoustic_encoder/comparison_validation.py`
- `src/acoustic_encoder/metrics.py`
- `src/acoustic_encoder/dataset_quality_control.py`
- `src/acoustic_encoder/dataset_quality_validation.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `src/acoustic_encoder/version.py`
- `scripts/run_comparison_metrics.py`
- `scripts/run_comparison_metrics_validation.py`

配置：`config/default.yaml`、`config/schema_versions.yaml`、`config/validation_dev_c5_direction_metrics.yaml`、`config/validation_dev_c6_dataset_qc.yaml`、`config/validation_dev_c7_comparison_metrics.yaml`。

测试：`tests/test_comparison_metrics.py`、`tests/test_comparison_metrics_outputs.py`、`tests/test_comparison_metrics_cli.py`、`tests/test_comparison_validation.py`，以及配置、P2-B、P4-A、pipeline 回归测试。

文档：本报告、`docs/progress/INDEX.md`、`README.md`、`MIGRATION_V1_TO_V2.md`、`CHANGELOG.md`。

`schemas.py` 未修改；`FeatureSet`、`MeasurementMeta` 和 `SpectrumData` 的现有权威 schema 不变。

## 输出 artifacts 与可复现性

成功 bundle 包含：

- `band_metrics.csv`
- `band_direction_pairs.csv`
- `configuration_comparison.csv`
- `morphology_gain_comparison.csv`
- `matched_pair_audit.csv`
- `cross_mode_pair_metrics.csv`
- `cross_mode_summary.csv`
- `per_tone_bias.csv`
- `tone_reliability.csv`
- `weighted_metrics.csv`
- `matched_effective_rank.csv`
- `comparison_status.csv`
- `comparison_metrics.json`
- `metrics_manifest.json`
- `metrics_manifest.sha256`

manifest 记录 version quartet、Git commit、UTC、random state、scope/config/result hash、P2-B link 状态、provenance、226 个显式输入文件/清单记录和 13 个权威非-manifest 输出 hash。CSV 稳定排序，JSON 是嵌套权威视图；loader 已逐项复核。原 FeatureSet 文件只读，输出目录存在即拒绝覆盖。

## 数据来源、provenance 与科研资格

所有新测试只使用 synthetic arrays 或 deterministic S3-style `FeatureSet` mock。最终验证包含 U4SYM/U4ENC、0°/90°、dense raw/demeaned/zscore、sweep projection/multisine measurement、REPOS pair 和人为注入的线性 `-0.25…+0.75 dB` bias；没有读取真实研究 TXT/WAV，也没有使用 external reference 调整参数。

固定状态：

- `data_origin=simulated`
- `run_purpose=software_validation`
- `scientifically_eligible=false`
- `canonical_analysis=false`（最终通用验证为 provisional tier）

canonical pass fixture 只验证软件门禁正向路径；即使 P2-B `canonical_ready=true`，模拟来源仍然 `scientifically_eligible=false`。本步不能支持科研结论。

## 测试优先过程与实际验证

实现先观察到缺少 module/API/config/output/CLI 的预期红灯，然后逐个最小实现变绿。重点覆盖四种频带边界、完整/空频带、固定 mask、P4-A rank/G 一致性、U4 delta/ratio 与零分母、显式 pair、一对多/metadata/tone-set/state mismatch、missing tone 不插值、bias 符号、absolute/shape contract、逐 tone bias、REPOS-only reliability、final_test 拒绝、floor/clip/mean-one、weighted 已知值、canonical fail/pass、config 迁移、CSV/JSON/hash/CLI 和全 pipeline 回归。

已实际执行的专项命令：

```powershell
python -m pytest -q tests/test_comparison_metrics.py tests/test_comparison_metrics_outputs.py tests/test_comparison_metrics_cli.py tests/test_comparison_validation.py tests/test_config.py tests/test_metrics.py tests/test_dataset_quality_control.py tests/test_dataset_quality_e2e.py tests/test_pipeline_cli.py tests/test_pipeline_e2e.py
```

准确结果：退出码 `0`，`207 passed in 19.31s`。

最终全量回归：

```powershell
python -m pytest -q
```

准确结果：退出码 `0`，`431 passed in 48.23s`。

编译与 whitespace 检查：

```powershell
python -m compileall -q src scripts tests
git diff --check
```

准确结果：两条命令退出码均为 `0`，均无标准输出。以上数字均来自本步实际运行，不沿用 DEV-C6 报告。

## 最终模拟验证输出

命令：

```powershell
python scripts/run_comparison_metrics_validation.py --output-root outputs --run-id DEV-C7-P4B-FINAL
```

输出：`outputs/simulated/software_validation/DEV-C7-P4B-FINAL/comparison_metrics/`。

准确结果：`processing_status=completed`、40 band rows、160 configuration-comparison rows、8 explicit cross-mode pairs、701/701 common tones、8 weighted rows、reliability available 且有效权重均值为 1。逐 tone bias 第一项为 `-0.25 dB`、最后一项为 `+0.75 dB`，与注入值一致。manifest 记录 226 个输入记录和 13 个权威非-manifest artifact；loader/hash 复核通过。该运行 `canonical_analysis=false`、`scientifically_eligible=false`。

## 已知限制与 provisional 参数

- 默认 1–2/2–4/4–8/1–8 kHz 频带、minimum feature count、minimum common tones、ratio denominator、0.1 dB reliability floor 和 raw-weight clip 100 都是 software-validation provisional 值。
- absolute cross-mode 指标只在明确共享 reference/calibration 时可用；本步不推断、不拟合、不校正 reference。
- 当前 canonical gate pass fixture 是构造的重复样本，只证明代码路径，不证明真实实验 condition completeness 或统计充分性。
- P4-B 的 per-tone reliability 是补充权重，不是 tone selection，不写回 `FeatureSet.reliability_weights`，也不替换 unweighted primary metrics。
- 当前输出没有 PNG；后续报告层可从固定 CSV/JSON 确定性生成图，但不能成为第二权威结果。

## 下一步及进入门槛

P4-B 完成后仍不得跳过 P9/P5/P6 门禁。进入下一切片前至少需要：明确批准下一模块；保持 P2-B canonical reference 规则；若进入 P9，单独定义候选/选择、calibration 和 final_test 防泄漏协议；若进入真实研究，先冻结真实实验 tone set、频带与 QC/reliability 阈值，并仅使用 provenance 合格且 research hard gate/P2-B 均通过的 `real_experiment`。在此之前不得生成科研结论。

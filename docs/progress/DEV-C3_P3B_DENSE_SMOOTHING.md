# DEV-C3 / P3-B：明确、可审计的 dense-spectrum smoothing

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 单一提交边界：实现、测试、配置、迁移说明、README、本报告和进度索引位于同一提交 `feat(features): add auditable dense smoothing`
- push 状态：本步只创建本地提交，不 push

## 目标与验收标准

本步在 P3-A 已建立的公共线性频率网格上实现可复现、可审计的 dense smoothing。验收要求是固定处理顺序、固定 dB 计算域、四种明确方法、三种段内边界策略、禁止跨越无效缺口、requested/effective 参数进入 manifest 和 `preprocessing_id`、平滑后再进行样本内归一化，以及保持 P1/P2/P7/P8 与旧 sweep 入口回归。

## 完成内容

1. 新增公开核心 `smooth_dense_grid(frequency_hz, values_db, valid_mask, preprocessing_config) -> DenseSmoothingResult`；它只接收已经插值的公共网格，不读取 TXT/WAV，也不重算 P1/P2/P8。
2. 实现 `none`、`moving_average_linear_hz`、`gaussian_linear_hz` 和 `fractional_octave`。
3. 固定 `smoothing_domain=db`。dB 数值的加权算术平均等价于相应幅值的加权几何平均；本步不暗中切换到线性幅值或功率域。
4. 将输入 `valid_mask` 分解为最大连续有效段。每个段独立平滑，invalid 点保持 `NaN/false`，不填零，任一核均不得从缺口另一侧取样。
5. 支持 `reflect`、`nearest` 和 `truncate`。coverage 在任何边界扩展之前根据段内真实存在的理论核权重计算；低于配置门槛时输出 invalid。
6. 公共处理顺序固定为：分析频带目标选择 → 公共网格插值 → 连续有效段内 smoothing → 样本内 normalization → `FeatureSet`。
7. `dense_raw_spl` 的 `raw` 明确定义为“平滑后但未归一化”，不是“未平滑”。三种 dense FeatureSet 共用平滑后的频率网格和 `valid_mask`。
8. preprocessing manifest 1.1 记录处理顺序、插值前/平滑后有效比例、完整 smoothing 定义、feature 语义和 normalization 输入阶段。
9. `preprocessing_id` 的规范化输入包含 method、domain、boundary、coverage、requested/effective 参数及算法定义；YAML 键顺序和数值排版不影响哈希。
10. canonical executor 的 run-manifest 1.3 对 dense `none` 记录 `P3_B=not_requested`，对成功 non-none 记录 `P3_B=completed`，对 sparse tones 记录 `not_applicable_sparse`。

## 明确未完成和非范围

- sweep tone projection、multisine tone-measurement FeatureSet、sparse-to-dense 插值；
- training-set standardization；
- smoothing 参数自动选择、批量参数扫描或根据分类结果选择参数；
- P2-B、P3-C matched-tone、P4、P5、P6、P9；
- 真实实验 smoothing 参数或 QC 阈值冻结；
- 科研结论。

## 数学定义

所有方法在公共线性网格 `f_i = f_0 + iΔf` 的 dB 值上计算。核权重均先规范化为和 1。

### none

`y_i = x_i`，并逐点原样保留 `valid_mask`。该方法用于 P3-A 数值兼容和明确的“未请求 smoothing”路径。

### moving_average_linear_hz

给定请求宽度 `W`：

```text
n0 = max(1, ceil(W / Δf))
n  = n0              if n0 is odd
     n0 + 1          if n0 is even
r  = (n - 1) / 2
w_k = 1 / n,  k = -r, ..., r
```

`effective_window_hz = nΔf`；首尾样点之间的实际 support span 为 `(n-1)Δf`。例如 `Δf=10 Hz` 时，请求 `50 Hz` 得到 5 点/50 Hz effective window/40 Hz support；请求 `100 Hz` 先得到 10 点，再居中为 11 点/110 Hz effective window/100 Hz support。

### gaussian_linear_hz

给定 `sigma_hz=σ_f` 与 `truncate_sigma=T`：

```text
σ_grid = σ_f / Δf
r = ceil(T σ_grid)
w_k ∝ exp(-0.5 (k / σ_grid)^2),  k = -r, ..., r
```

有限核重新规范化为和 1；effective span 为 `2rΔf`。`sigma_hz` 只表示 Gaussian 标准差，不再用含义模糊的 `window_hz` 代替。

### fractional_octave

对正中心频率 `f_c` 和正整数 `N=fraction_denominator`：

```text
f_lower = f_c · 2^(-1/(2N))
f_upper = f_c · 2^( 1/(2N))
```

`N=3` 表示 1/3 octave。在线性公共网格上取落入闭区间的样点，当前权重固定为 `rectangular_uniform_linear_grid_db`，即所有入选 dB 样点等权并归一化。带宽随 `f_c` 成比例增长；manifest 记录公式、低/高端解析边界和 snapped kernel sample-count 范围。octave fraction 不解释为 Hz 窗口。

## boundary、coverage 与 invalid-gap 规则

对目标点 `i`，先计算理论规范化核。令 `P_i` 为核落在同一连续有效段内的偏移集合：

```text
coverage_i = Σ(k in P_i) w_k
```

若 `coverage_i + 1e-12 < minimum_kernel_coverage`，输出 `NaN/false`。该数值容差只处理浮点求和误差，不改变配置阈值语义。

- `truncate`：丢弃段外权重，并将剩余权重除以 `coverage_i`；
- `nearest`：段外索引钳制到同一段最近端点；
- `reflect`：只在同一段内镜像，不重复端点；单点段退化为该唯一点。

三点序列 `[1, 2, 3]`、三点均值核、coverage 门槛 `2/3` 的边界真值为：

| boundary | 输出 |
|---|---|
| `reflect` | `[5/3, 2, 7/3]` |
| `nearest` | `[4/3, 2, 8/3]` |
| `truncate` | `[1.5, 2, 2.5]` |

门槛等于 `2/3` 时端点有效；提高到 `0.67` 时端点 invalid。一个 smoothing pass 的输出 invalid 不会递归改变同一 pass 的输入分段。

## 配置、迁移、schema 与 API 变化

版本变化：

| 项目 | 之前 | 本步 |
|---|---:|---:|
| pipeline | `2.0.0-dev.8` | `2.0.0-dev.9` |
| config schema | `2.7.0` | `2.8.0` |
| preprocessing schema | `1.0.0` | `1.1.0` |
| preprocessing manifest | `1.0.0` | `1.1.0` |
| run manifest | `1.2.0` | `1.3.0` |
| measurement schema | `2.4.0` | 不变 |
| feature schema | `2.1.0` | 不变 |

配置方法采用严格字段集合：

```yaml
preprocessing:
  schema_version: 1.1.0
  smoothing_domain: db
  smoothing:
    method: fractional_octave
    fraction_denominator: 3
    boundary: truncate
    minimum_kernel_coverage: 0.4
    weighting_definition: rectangular_uniform_linear_grid_db
```

验证拒绝非有限/非正 `window_hz`、`sigma_hz`、`truncate_sigma`，非正整数 `fraction_denominator`，不在 `(0,1]` 的 coverage、未知 boundary/domain/weighting，以及方法专用字段混用。根级 `smoothing_hz`、Gaussian `window_hz` 和 fractional `fraction` 不静默接受。

旧 config 2.7/preprocessing 1.0 的 `method=none` 可在内存迁移到 2.8/1.1，增加 `smoothing_domain=db` 和 migration warning，源 YAML 不改写。旧 non-none 配置因为此前没有可保留语义的实现而明确拒绝。

## preprocessing manifest 与 ID

manifest 的新增/固定字段包括：

- `processing_order`；
- `grid.interpolated_valid_grid_fraction` 与 `smoothed_valid_grid_fraction`；
- `smoothing.algorithm_version/domain/method/boundary/minimum_kernel_coverage`；
- `smoothing.requested` 与 `smoothing.effective`；
- fractional-octave `formula` 与 `weighting_definition`；
- `normalization.input_stage=smoothed_common_grid`；
- `feature_semantics.dense_raw_spl=smoothed_but_not_normalized`。

一次 resolved config 只对应一个 smoothing 方法和参数集。比较 `none`、50 Hz、100 Hz 或不同 octave fraction 必须使用不同 `preprocessing_id`/独立运行；本步不在一个 FeatureSet 内混合参数。

## 修改文件

实现与配置：

- `src/acoustic_encoder/preprocessing.py`
- `src/acoustic_encoder/features.py`
- `src/acoustic_encoder/feature_outputs.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `config/default.yaml`
- `config/experiment_v2_u4.yaml`
- `config/schema_versions.yaml`
- `config/validation_dev_c3_fractional_octave.yaml`

测试和 immutable validation metadata：

- `tests/test_dense_smoothing.py`
- `tests/test_preprocessing.py`
- `tests/test_features.py`
- `tests/test_feature_outputs.py`
- `tests/test_config.py`
- `tests/test_pipeline_e2e.py`
- `tests/test_pipeline_cli.py`
- `tests/fixtures/rew/external_reference/BW M1.metadata.json`

文档：

- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-C3_P3B_DENSE_SMOOTHING.md`

`schemas.py` 未修改：measurement/feature 字段布局没有变化；新增语义位于 preprocessing result/manifest 和 run-manifest。

## 数据来源、provenance 与科研资格

单元测试只使用代码内构造的 synthetic arrays，属于 `simulated/software_validation`。端到端回归继续使用既有 P7/S3 simulated 数据和三份 immutable REW 官方样例。

持久化 DEV-C3 验证使用 immutable `tests/fixtures/rew/external_reference/BW M1.txt`，SHA-256 为 `cc863c23f0f4ebf3cc4d875f9a511b76b1d3e20a391ffc7a47745d8f53365447`。配套 `BW M1.metadata.json` 只记录当前软件版本、来源/hash 与 `external_reference/parser_fixture`；`device_version`、`configuration`、`angle_deg`、`session_id`、repeat 与 experiment metadata 仍全部为 null，没有伪造。

该数据的 `run_purpose=software_validation`、`eligible_for_scientific_analysis=false`。本步没有读取或分析任何 `real_experiment`，不能形成科研结论。

## 测试优先过程与实际验证

实现按 red-green-refactor 小步推进。实际观察到的代表性 RED 包括：缺少 `smooth_dense_grid` 的 import error、moving/Gaussian/fractional 方法的 `NotImplementedError`、`nearest` boundary 未实现、invalid gap 产生 `NaN`/跨段污染，以及 boolean `window_hz` 被错误接受。每个失败先由单一测试固定，再做最小实现并重跑。

最终验证命令和准确结果：

```powershell
python -m pytest tests/test_dense_smoothing.py tests/test_preprocessing.py tests/test_features.py tests/test_feature_outputs.py tests/test_config.py -q
```

准确结果：退出码 `0`，`111 passed in 1.05s`。

```powershell
python -m pytest tests/test_pipeline_cli.py tests/test_pipeline_e2e.py -q
```

准确结果：退出码 `0`，`27 passed in 25.41s`。

```powershell
python -m pytest -q
```

准确结果：退出码 `0`，`270 passed in 57.17s`。

```powershell
python -m compileall -q src scripts tests
```

准确结果：退出码 `0`，无标准输出。

## 生成输出

验证配置：`config/validation_dev_c3_fractional_octave.yaml`。

最终输出目录：

```text
outputs/external_reference/software_validation/DEV-C3_P3B_FINAL/
```

执行命令：

```powershell
python scripts/run_pipeline.py --config config/validation_dev_c3_fractional_octave.yaml --input "tests/fixtures/rew/external_reference/BW M1.txt" --metadata "tests/fixtures/rew/external_reference/BW M1.metadata.json" --output-root outputs --run-id DEV-C3_P3B_FINAL
```

准确结果：退出码 `0`；`processing_status=completed`；`qc_status=valid`；`success=true`；`P3_A=completed`；`P3_B=completed`；`P4_P6=not_implemented`。

哈希/round-trip 复核结果：run manifest 中 19 个 artifact SHA-256 全部重新计算一致；`run_manifest.sha256` 一致；三个 FeatureSet 均为 701/701 有效点；method 为 `fractional_octave`；`preprocessing_id=sha256:f6f9c45e41dada800441141829af8b156ed5b63c919ed6cb9624c205f5e44d9d`。

生成物包括 run/config/input/QC 视图、`spectrum_data.npz/json`、`processed/feature_index.csv`、`feature_schema.json`、`preprocessing_manifest.json/.sha256`、失败索引，以及三个 FeatureSet 的 NPZ/JSON。输出目录不可覆盖。

一次审计探针曾复用 DEV-C2 sidecar；其 dev.8/config-2.7 version quartet 被当前 P2 正确识别为 `unsupported_schema_or_pipeline_version`，聚合为 `exclude_candidate`，CLI 没有给出成功标记。该临时目录已删除，并用上述不伪造实验字段的 DEV-C3 external-reference sidecar 重新生成最终输出。

## 已知限制和 provisional 参数

- `smoothing_domain=db` 和 fractional rectangular weighting 是当前冻结的软件语义，但 smoothing 参数数值仍为 provisional，不是实测最优值。
- reflect/nearest 可在短 segment 内重复使用少量实测点；coverage 只表示理论核的物理支持比例，不表示统计独立样本数。
- fractional-octave 在固定线性网格上 snap 到离散点，低频可能只有很少样点；解析与 snapped 信息均记录，但本步不建立感知加权或不确定度传播。
- 插值仍沿用 P3-A 规则：分析频带定义目标网格，目标端点可由紧邻频带外源点括住；manifest 的处理顺序不表示先删除这些 bracketing source points。
- 本步不传播 REW measurement uncertainty，不执行 training-set normalization，也不确定哪种 smoothing 最适合分类。
- warning/exclude/human-invalid 数据仍不会由 P3 自动删除；selection policy 仍属于后续步骤。

## 下一步及 matched-tone P3-C 进入门槛

P3-C 开始前至少需要：

1. 固定 sweep tone projection 与 multisine measured-tone FeatureSet 的共同频点契约；
2. 明确 measured tones、projected sweep tones 与 dense display curve 的不同物理语义，继续禁止 sparse-to-dense 伪频响；
3. 将 tone-set identity、projection误差/可用性和 P8 per-tone QC 进入 FeatureSet provenance；
4. 对 P3-C 的缺 tone、频点不匹配、valid-mask 和 round-trip 做 synthetic TDD；
5. 保持 P2/P8 权威状态、research hard gate 与 `MeasurementMeta.valid` 不被覆盖；
6. 在进入 P4/P5 前冻结训练/验证数据泄漏边界；不得根据最终分类结果反向选择 smoothing。

## 对应 Git commit

提交主题：`feat(features): add auditable dense smoothing`。本报告与实现、测试、配置和迁移文档位于同一个本地提交；未 push。最终 commit hash 由提交后 Git 输出和最终回复给出。

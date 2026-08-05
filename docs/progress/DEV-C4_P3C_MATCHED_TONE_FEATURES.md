# DEV-C4 / P3-C：严格匹配的 sweep projection 与 multisine tone FeatureSet

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 单一提交边界：实现、配置、迁移、测试、README、本报告和进度索引位于同一提交 `feat(features): add matched tone feature sets`
- push 状态：本步只创建本地提交，不 push

## 目标与验收标准

本步在同一份经 hash 验证的 tone set 下，为 dense sweep 和 sparse multisine 构造长度、名称、顺序、单位与样本内归一化规则完全一致的 `FeatureSet`。验收重点是：固定唯一 tone 顺序；禁止从 P8 sparse tones 合成 dense 频响；使 sweep 提取、P8 直接对齐、缺失 tone、来源参考、QC、公共有效 mask 和所有输出均可审计；通过已知 `H(f)` 的 P7→S3→P8→P3-C 模拟端到端验证。

## 完成内容

1. 新增 `ToneSetDefinition`/`ToneDefinition` 及 `load_tone_set()`，联合校验 `stimulus_manifest.json`、`tones.csv`、`tone_set_id`、tone count、频率、DFT bin、采样率、周期长度、resolved stimulus config、`tones_sha256` 与规范化 `tone_set_sha256`。
2. 唯一权威顺序固定为 `manifest_tone_index`。`tones.csv` 的物理行顺序必须已经是连续的 `0..N-1`，频率必须在该顺序下严格递增；构造 FeatureSet 时不排序、不重排。
3. 新增 sweep `FeatureKind.TONE_PROJECTION_FROM_SWEEP`。它必须先调用既有 P3-A/P3-B dense 路径，然后从 `dense_raw_spl`（含已配置 smoothing、未做 dense normalization）提取 tone。
4. 新增 multisine `FeatureKind.TONE_MEASUREMENT_FROM_MULTISINE`。它直接使用 P8 `sparse_tones SpectrumData`，校验 P8 的 tone-set hash 和 per-tone QC 顺序；不插值、不 densify、不用 0 或均值填充缺失 tone。
5. 两条路径共享同一 `normalize_tone_values()`，支持 `none`、`subtract_mean_db` 和 `zscore_within_sample`；只用当前样本的有限有效 tone。
6. 新增 `assert_matched_tone_schema()`，严格比较 tone-set ID/hash、`tone_schema_id`、feature names、units、normalization 和长度；不静默 reindex。
7. 新增 `build_matched_tone_view()`，返回公共有效 mask、两侧缺失/无效计数、最小共同 tone 门槛、来源参考状态、比较状态及 `cross_mode_absolute_comparable`。
8. 扩展 `FeatureSet` 2.2，序列化 tone-set hash/schema、normalization、magnitude quantity/reference、phase status 和可选 reliability weight 来源；NPZ 继续 `allow_pickle=False`。
9. P7 stimulus manifest 升至 1.1，新增 `tones_sha256` 与 `tone_set_sha256`；正式 P8 adapter 使用同一 `ToneSetDefinition`，不再从配置复制一份 tone 权威定义。
10. 新增不可覆盖的 paired output writer、CLI validation runner 和 `config/validation_dev_c4_matched_tones.yaml`。
11. 单测量 canonical run manifest 升至 1.4，并明确显示 `P3_C=paired_run_required`；真正的 P3-C 构造由显式 paired runner 执行。

## 明确未完成和非范围

- tone 选择评分、P9 和真实 tone-set 冻结；
- affine calibration 拟合或跨模式 reference 转换；
- training-set standardization；
- P4 metrics、P5 classification、P6 HR；
- sparse-to-dense 物理插值；
- 用模拟结果冻结真实实验阈值或校准参数；
- 真实研究数据分析和科研结论。

## Tone ordering 与 canonical feature names

`manifest_tone_index` 是唯一顺序来源。对第 `i` 个 tone，名称为：

```text
tone_{tone_index:06d}_{canonical_decimal_frequency}_hz
```

例如 index 0、1000 Hz 为 `tone_000000_1000_hz`。频率使用 locale-independent、非指数、去除无意义尾零的 Decimal 文本；名称不依赖 YAML 排版或 measurement mode。`tone_index` 非连续、频率重复/非递增、DFT bin 重复、文件 hash 不符或 DFT 关系 `f_k = bin_k · fs / N` 不成立均明确失败。

## Sweep extraction 数学定义

固定处理顺序为：

```text
SpectrumData → P3 common grid → P3 smoothing → tone extraction
→ sample-local tone normalization → FeatureSet
```

### `single_point_linear`

若 `f_k` 与有效公共网格点完全重合，直接取该点。若 `f_i < f_k < f_{i+1}` 且两个紧邻点均有效：

```text
α = (f_k - f_i) / (f_{i+1} - f_i)
L_k = (1 - α)L_i + αL_{i+1}
```

计算域是 dB。审计记录左右索引、频率与权重。频带外不 extrapolate；任一紧邻点无效时视为跨 invalid gap，tone 输出 `NaN/false`。

### `narrowband_integration`

配置的 `full_bandwidth_hz=B` 定义完整矩形频带 `[f_k-B/2, f_k+B/2]`。先把 dB 转为线性功率比：

```text
P(f_i) = 10^(L_i/10)
```

仅对两端都有效的相邻网格区间做分段线性功率插值和梯形积分。令实际覆盖宽度为 `B_c`：

```text
coverage = B_c / B
P̄_k = (1 / B_c) ∫covered P(f) df
L_k = 10 log10(P̄_k)
```

输出记录请求/实际带宽、上下界、有效源点数、边界插值数和 coverage。`B_c=0`、coverage 低于 `minimum_band_coverage` 或积分功率非正/非有限时为 invalid。当前 `overlap_policy=reject`：相邻 tone 带宽出现正宽度重叠即明确失败，不能形成未记录的共享能量。

## Tone normalization

共享 API：

```python
normalize_tone_values(values_db, valid_mask, config) -> ToneNormalizationResult
```

- `none`：有效 tone 原值，单位 `dB`；
- `subtract_mean_db`：`z_i=L_i-mean(L_valid)`，单位 `dB`；
- `zscore_within_sample`：`z_i=(L_i-mean(L_valid))/std_population(L_valid)`，单位 `dimensionless`。

缺失/无效 tone 始终保留原位置且为 `NaN/false`，不参与 mean/std。有效 tone 少于 `minimum_valid_tones`，或 z-score 的总体标准差低于 `minimum_std_db` 时，整个样本的 tone FeatureSet 构造明确失败。training-set statistics 不在此 API 中。

## Matched schema、common valid mask 与 reference compatibility

共同 tone schema 的身份包含 schema version、tone-set ID/hash、完整 feature names/units 与 normalization config；两种 FeatureSet 可以有不同的 source-specific `preprocessing_id`，但必须共享同一 `tone_schema_id`。

```text
common_valid_mask = sweep.valid_mask AND multisine.valid_mask
```

该辅助视图不修改任一原始 mask，也不删除 tone。共同有效数低于 `minimum_common_valid_tones` 时 paired view 失败，并保留两侧缺失/无效计数。

来源可比状态固定为：

- magnitude quantity 不同：`quantity_mismatch`；
- 同一非空 `calibration_id`：`shared_calibration`；
- quantity 相同且 reference 相同：`compatible_reference`；
- 其余：不兼容/未知 reference。

只有 `normalization=none` 且 reference 为 `shared_calibration` 或 `compatible_reference` 时，`cross_mode_absolute_comparable=true`。样本内去均值/z-score 只允许 `normalized_shape_only_candidate`，仍记录原始 quantity/reference 不一致；本步不宣称绝对 dB 一致。最终模拟 run 的 sweep 是 `spl`、multisine 是 `transfer_ratio`，所以状态为 `quantity_mismatch`、absolute comparable 为 false。

## 配置、schema 和 API 变化

版本变化：

| 项目 | DEV-C3 | DEV-C4 |
|---|---:|---:|
| pipeline | `2.0.0-dev.9` | `2.0.0-dev.10` |
| config schema | `2.8.0` | `2.9.0` |
| feature schema | `2.1.0` | `2.2.0` |
| measurement schema | `2.4.0` | 不变 |
| stimulus manifest | `1.0.0` | `1.1.0` |
| run manifest | `1.3.0` | `1.4.0` |
| matched-tone manifest/audit | 不存在 | `1.0.0` |

核心配置：

```yaml
matched_tone_features:
  schema_version: 1.0.0
  provisional: true
  tone_ordering: manifest_tone_index
  sweep_extraction:
    method: single_point_linear
  normalization:
    method: subtract_mean_db
    minimum_valid_tones: 5
    minimum_std_db: 1.0e-9
  matching:
    minimum_common_valid_tones: 5
```

`narrowband_integration` 另要求 `full_bandwidth_hz>0`、`0<minimum_band_coverage<=1`、`integration_domain=linear_power_ratio` 和 `overlap_policy=reject`。方法专用字段严格验证。DEV-C3 config 2.8 可显式迁移到 2.9，补入默认 matched-tone block 并记录 warning；源 YAML 不回写。所有参数仍标记 `provisional`，不是实际实验冻结值。

## 修改文件

实现与配置：

- `src/acoustic_encoder/tone_sets.py`
- `src/acoustic_encoder/tone_features.py`
- `src/acoustic_encoder/matched_tone_outputs.py`
- `src/acoustic_encoder/matched_tone_validation.py`
- `src/acoustic_encoder/stimulus_multisine.py`
- `src/acoustic_encoder/multisine_estimation.py`
- `src/acoustic_encoder/io_multisine.py`
- `src/acoustic_encoder/schemas.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/mock_data.py`
- `src/acoustic_encoder/version.py`
- `scripts/run_matched_tone_validation.py`
- `config/default.yaml`
- `config/experiment_v2_u4.yaml`
- `config/experiment_v2_u4_multisine.yaml`
- `config/schema_versions.yaml`
- `config/validation_dev_c4_matched_tones.yaml`

测试与 immutable validation metadata：

- `tests/test_tone_sets.py`
- `tests/test_tone_features.py`
- `tests/test_matched_tone_outputs.py`
- `tests/test_matched_tone_e2e.py`
- `tests/test_config.py`
- `tests/test_io_multisine.py`
- `tests/test_pipeline_e2e.py`
- `tests/test_schemas.py`
- `tests/test_stimulus_multisine.py`
- `tests/fixtures/rew/external_reference/BW M1.metadata.json`

文档：

- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-C4_P3C_MATCHED_TONE_FEATURES.md`

## 数据来源、provenance 与科研资格

单元测试使用代码内 synthetic arrays/临时 P7 artifacts。最终 E2E 使用 `generate_dual_mode_mock()` 产生同一个已知 `H(f)` 的 mock dense REW sweep 与 S3 delayed multisine recording，再走正式 P1/P2/P3-A/P3-B/P7/P8/P3-C 路径。

全部 DEV-C4 验证数据为：

- `data_origin=simulated`
- `run_purpose=software_validation`
- `dataset_role=software_validation`
- `eligible_for_scientific_analysis=false`

没有使用任何 `real_experiment`，也没有将 `external_reference` 伪装为实验数据。输出硬隔离于 `outputs/simulated/software_validation/`，不得用于科研结论。

## 测试优先过程与实际验证

实现遵循 red-green-refactor：先为 tone authority/hash、两种 sweep extraction、缺失 sparse tone、三种 normalization、schema mismatch、reference state、不可覆盖输出和 known-H E2E 写失败测试，再做最小实现并回归。最终实际命令与准确结果如下。

```powershell
python -m pytest tests/test_tone_sets.py tests/test_tone_features.py tests/test_matched_tone_outputs.py tests/test_matched_tone_e2e.py -q
```

结果：退出码 `0`，`32 passed in 2.92s`。

```powershell
python -m pytest tests/test_config.py::test_dev_c3_explicit_smoothing_migrates_without_reinterpretation tests/test_config.py::test_legacy_non_none_smoothing_is_rejected_instead_of_reinterpreted -q
```

结果：退出码 `0`，`2 passed in 0.15s`；DEV-C3 config 2.8 的明确 smoothing 原样迁移，2.7 的旧模糊 non-none 定义继续拒绝。

```powershell
python -m pytest -q --junitxml=outputs/DEV-C4_P3C_pytest_final_20260805.xml
```

结果：退出码 `0`，`313 passed in 35.56s`；JUnit XML 记录 313 tests、0 failures、0 errors、0 skipped。

```powershell
python -m compileall -q src scripts tests
```

结果：退出码 `0`，无标准输出。

```powershell
python scripts/run_matched_tone_validation.py --run-id DEV-C4_P3C_FINAL
```

结果：退出码 `0`；`common_valid_tones=71`；`maximum_matched_error_db=0.0111702949429`；`scientific_use=prohibited_simulated_software_validation`。

对最终输出重新计算 SHA-256 并通过 `load_feature_set()` round-trip：manifest 列出的 artifact 为 `8/8` 一致，manifest 自身 hash 一致；两个 FeatureSet 均成功加载，sweep 与 multisine 都是 `71/71` 有效 tone，`tone_schema_match=true`。

## 生成输出

最终验证目录：

```text
outputs/simulated/software_validation/DEV-C4_P3C_FINAL/
```

关键生成物：

- `inputs/mock_manifest.json`
- `inputs/rew/V2_U4ENC_A000_S01_CONT_R01.txt`
- `inputs/multisine/V2_U4ENC_A000_S01_CONT_R01_MS.wav` 及 sidecar
- `inputs/stimuli/ms_broadband_1k_8k_100hz_v1/stimulus_manifest.json`
- `inputs/stimuli/ms_broadband_1k_8k_100hz_v1/tones.csv`
- `inputs/truth/V2_U4ENC_A000_S01_CONT_R01_known_H.csv`
- `processed/features/tone_projection_from_sweep/*.npz|*.json`
- `processed/features/tone_measurement_from_multisine/*.npz|*.json`
- `processed/tone_feature_index.csv`
- `processed/matched_tone_schema.json`
- `processed/matched_tone_audit.csv`
- `processed/preprocessing_failures.csv`
- `processed/preprocessing_manifest.json` 及 `.sha256`

输出目录已存在时拒绝覆盖；failed sample 仍进入 index/audit/failure CSV。manifest 记录权威 tone hashes、处理顺序、两条 preprocessing ID、来源 quantity/reference、公共有效计数、comparison state、provenance 和每个 artifact hash。

## 已知限制与 provisional 参数

- `single_point_linear` 在 dB 域插值；`narrowband_integration` 在功率域按公共网格的分段线性模型积分。这是已固定、可审计的软件定义，不代表已经由真实实验选择了最优方法。
- 当前 narrowband overlap 策略只有明确拒绝；没有实现能量分摊或自适应带宽。
- P8 当前没有经验证的 reliability-weight 公式，因此 `reliability_weights=None`、source 为 null；未伪造全 1 权重。
- phase 只保留 P8/P1 权威 `source_phase_status`，不进入本阶段 feature values。
- 当前 E2E 使用去均值后的 shape 比较；0.0111702949429 dB 是 deterministic simulation validation error，不是仪器不确定度或真实校准误差。
- QC warning/exclude、manual valid 和 provenance 均被保留；P3-C 不自动删除 tone，也不改变 `MeasurementMeta.valid`。

## 下一步及 P4/P9 进入门槛

进入 P4 前至少需要：

1. 指标只在显式 `common_valid_mask` 上计算，并设定不足 tone 的失败策略；
2. 区分 `absolute_comparable`、`normalized_shape_only_candidate` 和 `independent_mode_only`，不得跨不兼容 reference 计算绝对差；
3. 冻结每项 P4 指标所需 normalization/preprocessing ID、QC eligibility 和缺失值策略；
4. 在 sklearn Pipeline/fold 内实现任何 training-set standardization，防止数据泄漏；
5. 用 synthetic/software-validation 先验证数学实现，真实阈值必须等真实实验设计与校准完成后另行冻结。

进入 P9 前至少需要：

1. 明确 tone selection 的候选全集仍由本步 hash-verified tone set 提供；
2. 固定评分目标、训练/验证隔离、稳定性与最小间隔约束；
3. 禁止根据最终测试集或方向标签回调本步 extraction/QC 阈值；
4. 任何新 tone set 都必须重新生成并验证 P7 manifest/`tones.csv`/hash，不能在 FeatureSet 阶段静默改序。

P2-B、P4–P6、P9、真实校准和研究分析仍未实现，因此本步不能声明科研结论。

## 对应 Git commit

提交主题：`feat(features): add matched tone feature sets`。本报告与实现、测试、配置和迁移说明位于同一个本地提交；未 push。最终 commit hash 由提交后的 Git 输出和最终回复给出。

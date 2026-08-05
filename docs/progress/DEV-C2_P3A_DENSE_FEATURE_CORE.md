# DEV-C2 / P3-A：dense sweep 公共频率网格、基础归一化与 FeatureSet

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 单一提交边界：实现、测试、配置、迁移说明、README、本报告和进度索引位于同一提交 `feat(features): add dense sweep feature core`
- push 状态：本步只创建本地提交，不 push

## 目标与验收标准

本步在 P1/P8 产生的权威 `SpectrumData` 和 P2-A 产生的对应 `MeasurementQCResult` 之后，建立只面向 `Representation.DENSE_SPECTRUM` 的共享 P3-A 核心。P3 不读取 REW TXT 或 multisine WAV，不重算 P1/P2/P8，不根据 QC 自动删除样本，并对每一种请求的 dense feature 产生成功 artifact 或结构化失败记录。

验收内容包括：确定性的公共频率网格、受 invalid/gap 约束的线性插值、三个样本内 FeatureSet、magnitude 语义门禁、稳定 preprocessing hash、可回读且可复核哈希的输出束、统一执行器的 dense/sparse 阶段分流，以及 P1/P2/P7/P8/DEV-B5 全量回归。

## 完成内容

1. 新增精确十进制公共网格：默认闭区间 1000–8000 Hz、步长 10 Hz、共 701 点；分析带宽必须是步长的整数倍。
2. 线性插值只使用目标频率两侧紧邻的原始点；禁止外推，禁止使用 invalid 点，禁止跨越超过最大间隙的缺口。
3. 输出无效位置保持 `valid_mask=false` 和 `NaN`；不足的覆盖率按配置产生显式 preprocessing failure，部分但合格的覆盖率产生 warning。
4. 生成 `dense_raw_spl`、`dense_demeaned_db`、`dense_zscore` 三种 FeatureSet；名称、长度和网格跨样本一致。
5. 只有 `magnitude_quantity=spl` 可生成 `dense_raw_spl`。`transfer_ratio` 不会被改名为物理 SPL，但可以生成明确的样本内 de-mean/z-score 表示。
6. P2 warning、exclude-candidate、unavailable、manual review、human valid 和 downstream eligibility 作为来源快照保留；P3 不修改 `MeasurementMeta.valid`，也不丢弃 feature 值。
7. P3 校验 P2 对象的 sample、mode、origin、dataset role 和人工状态确实与输入 spectrum 对应，并再次执行 run-purpose research gate。
8. `preprocessing_id` 是规范化语义配置的 SHA-256，不受映射键顺序或 YAML 排版影响。
9. 新增不可覆盖的 processed bundle、成功/失败共同索引、FeatureSet round trip 和 artifact SHA-256 复核。
10. canonical executor 对 dense 输入运行 P3-A；sparse multisine 明确记录 `P3_A=not_applicable_sparse`，不做 sparse-to-dense 插值。

## 明确未完成和非范围

- moving-average、Gaussian 和 fractional-octave smoothing（P3-B）；
- sparse tone FeatureSet、sweep tone projection 和 multisine tone-measurement FeatureSet；
- training-set standardization；任何未来标准化必须位于训练 fold 内的 sklearn Pipeline；
- P2-B 跨测量 QC、P4 指标、P5 分类、P6 HR、P9 tone 选择；
- 跨样本离群、重复稳定性统计、真实实验阈值冻结和科研结论。

## 网格、插值与缺口定义

设配置端点和步长以十进制数解析为 `f_low`、`f_high`、`Δf`。仅当

```text
N_interval = (f_high - f_low) / Δf
```

为整数时接受配置，并逐项构造 `f_i = f_low + i·Δf`，`i=0,...,N_interval`。因此两端均包含，feature name 直接由十进制值生成，例如 `f_1000_hz`；schema 名称不依赖二进制浮点累积或 `np.arange`。

对目标点 `f`：若它精确命中原始点，仅在该原始点 valid 时复制；否则只考虑 `searchsorted` 得到的紧邻左、右原始点。两点都必须 valid，且 `f_right-f_left <= maximum_interpolation_gap_hz`。满足后使用

```text
h(f) = h_left + (f-f_left)/(f_right-f_left) · (h_right-h_left)
```

边界等于最大 gap 时允许；大于阈值时拒绝。原始频率范围外不外推，invalid 点也不能被跨越。

## normalization 数学定义

只使用 `normalization_band_hz` 内且 `valid_mask=true` 的当前样本点集合 `B`：

```text
μ = mean({h_i | i ∈ B})
dense_demeaned_db_i = h_i - μ
σ = sqrt(mean({(h_i-μ)^2 | i ∈ B}))      # population std, ddof=0
dense_zscore_i = (h_i - μ) / σ
```

有效 normalization 点少于 `minimum_normalization_points` 时，两种归一化 FeatureSet 明确失败；`σ < minimum_zscore_std_db` 时 z-score 明确失败。无效点不进入统计，也不由全数据或其他 sample 填补。该 z-score 是 sample-local shape representation，不是训练集标准化。

## magnitude 语义决策

- `spl`：允许 raw SPL、de-meaned dB、z-score。
- `transfer_ratio` 或其他非 SPL dB quantity：raw SPL 产生 `raw_spl_requires_spl_quantity` 失败；de-meaned dB 和 z-score 仍保留其来源 quantity/reference 和 validation provenance。
- 本步未增加模糊的 “raw dB” feature kind，也没有为方便测试把 transfer ratio 重命名为 SPL。

## API、schema、config 与 manifest

公共构造 API：

```python
build_dense_feature_sets(
    spectrum: SpectrumData,
    measurement_qc: MeasurementQCResult,
    preprocessing_config: Mapping[str, object],
) -> DenseFeatureProcessingResult
```

输出 API：

```python
write_dense_feature_outputs(
    result: DenseFeatureProcessingResult,
    processed_directory: str | Path,
) -> dict[str, Path]
```

版本变化：pipeline `2.0.0-dev.7 → 2.0.0-dev.8`；config `2.6.0 → 2.7.0`；measurement 保持 `2.4.0`；feature `2.0.0 → 2.1.0`；run manifest `1.1.0 → 1.2.0`；preprocessing manifest 为 `1.0.0`。

Feature schema 2.1 新增可选、向后兼容的 P2 来源快照字段：aggregate status、canonical QC hash、warning/exclude/unavailable reasons、downstream eligibility。旧 artifact 缺少这些字段时仍可加载为 unavailable，不会伪造值。

`preprocessing` YAML schema 1.0 包含 `provisional`、analysis band、grid step、linear interpolation、maximum gap、minimum valid fraction、normalization band、minimum normalization points、minimum z-score std 和 smoothing method。配置验证检查类型、有限性、正值、范围包含关系和精确网格整除。旧 config/feature 2.0 marker 只在内存迁移，源 YAML 不改写。

`preprocessing_manifest.json` 记录版本 quartet、canonical preprocessing config/ID、输入 sample/path/hash、来源 magnitude quantity/reference、origin/role/purpose/scientific eligibility、P2 快照及哈希、网格定义、归一化公式、warning/failure 和全部子 artifact 哈希。外部 `.sha256` 文件封存 manifest 自身哈希。

## 输出 schema 与生成物

每个成功 dense run 至少包含：

```text
processed/
  feature_index.csv
  feature_schema.json
  preprocessing_manifest.json
  preprocessing_manifest.sha256
  preprocessing_failures.csv
  features/dense_raw_spl/<sample_id>.npz + .json
  features/dense_demeaned_db/<sample_id>.npz + .json
  features/dense_zscore/<sample_id>.npz + .json
```

`feature_index.csv` 对三种 feature 各保留一行；失败行保留 reason/message 且不伪造 NPZ/JSON 路径。FeatureSet 数组使用 `numpy.load(..., allow_pickle=False)` 回读。processed 目录已存在时立即拒绝覆盖。

完成本地提交后，用同一 canonical executor 生成持续保留但不纳入 Git 的 external-reference software-validation bundle：

```text
outputs/external_reference/software_validation/DEV-C2_P3A_FINAL/
```

输入为 immutable 官方 REW `BW M1.txt` fixture；它仅验证软件格式和 dense P3-A，不是项目真实实验。

## 修改文件

核心实现与入口：

- `src/acoustic_encoder/preprocessing.py`
- `src/acoustic_encoder/features.py`
- `src/acoustic_encoder/feature_outputs.py`
- `src/acoustic_encoder/schemas.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `src/acoustic_encoder/version.py`

配置、测试与文档：

- `config/default.yaml`
- `config/experiment_v2_u4.yaml`
- `config/schema_versions.yaml`
- `tests/test_preprocessing.py`
- `tests/test_features.py`
- `tests/test_feature_outputs.py`
- `tests/test_schemas.py`
- `tests/test_config.py`
- `tests/test_pipeline_e2e.py`
- `tests/test_pipeline_cli.py`
- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-C2_P3A_DENSE_FEATURE_CORE.md`

## 数据来源、provenance 与科研资格

实现和测试只使用：

1. 代码内构造的 `simulated/software_validation` dense spectra；
2. 既有 P7/S3 `simulated/software_validation` multisine 回归；
3. immutable 官方 REW 样例 `external_reference/parser_fixture`。

这些数据均为 `eligible_for_scientific_analysis=false`。测试确认 simulated/external-reference 进入 `research_analysis` 时被 hard gate 拒绝。本步没有导入、分析或推断任何 `real_experiment` 数据，不得据此形成科研结论。

## 实际验证命令和准确结果

以下均为本步提交前实际执行结果：

```powershell
python -m pytest tests/test_preprocessing.py tests/test_features.py tests/test_feature_outputs.py tests/test_schemas.py tests/test_config.py -q
```

准确结果：退出码 `0`，`84 passed in 0.58s`。

```powershell
python -m pytest tests/test_pipeline_cli.py tests/test_pipeline_e2e.py -q
```

准确结果：退出码 `0`，`26 passed in 14.80s`。

```powershell
python -m pytest -q
```

准确结果：退出码 `0`，`234 passed in 34.52s`。

```powershell
python -m compileall -q src scripts tests
```

准确结果：退出码 `0`，无标准输出。

## 已知限制与 provisional 参数

- 默认 1000–8000/10 Hz、100 Hz maximum gap、0.95 minimum valid fraction、2 个 normalization 点和 `1e-9 dB` minimum std 都是软件验证 provisional 值，不是实测冻结门槛。
- 线性插值不传播测量不确定度，也不代替真实的采样密度评估。
- raw SPL 语义依赖 P1 已明确标注的 `magnitude_quantity=spl`；本步不执行 SPL calibration。
- P3-A 不平滑；任何 non-none smoothing 都产生明确 `smoothing_not_implemented` 失败。
- warning/exclude/human-invalid feature 仍可被构造；这不代表它已获准进入 P4/P5。
- 单 measurement executor 不是跨样本选择器，尚未实现 P2-B 或 dataset completeness gate。

## 下一步及 P3-B 进入门槛

P3-B 开始前至少需要：

1. 分别冻结 moving-average、Gaussian、fractional-octave 的数学定义、频率域单位和边界处理；
2. 明确 smoothing 对 invalid/gap 的传播规则，禁止填平未经支持的缺口；
3. 把所有 smoothing 参数纳入 canonical preprocessing hash 和 manifest；
4. 对 synthetic curves 验证幅值偏差、边界行为和可重复性；
5. 保持 raw/processed feature kind、magnitude 语义、P2 provenance 和 research hard gate；
6. sparse-tone FeatureSet 继续单独设计，禁止借 P3-B 插值成 dense 物理频响。

## 对应 Git commit

提交主题：`feat(features): add dense sweep feature core`。本报告与实现、测试、配置及迁移文档位于同一个本地提交；不 push。

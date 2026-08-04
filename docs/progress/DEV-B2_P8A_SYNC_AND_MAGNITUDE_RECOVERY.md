# DEV-B2 / P8-A：模拟 multisine 同步与 tone 传递幅值恢复

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-04
- 分支：`feature/v2-dual-input`
- 提交边界：本报告与实现位于同一个 `feat(multisine): recover simulated tone transfer magnitudes` 提交；最终 SHA 由该提交的 Git 记录给出。

“完成”只表示模拟软件验证切片通过，不表示真实 multisine 数据、最终 QC、可靠 phase 或科研结论已经完成。

## 目标与验收标准

目标是使用现有 P7 `stimulus.wav` 和 `stimulus_manifest.json`，从 S3 known-`H(f)` 模拟录音中定位 preamble、按 manifest 丢弃瞬态周期、截取整数稳定周期，并在刺激 tones 上恢复传递幅值。

验收标准：

- 支持可配置前置延迟和非周期对齐；测试延迟为 1379 samples，周期为 4800 samples。
- 通过已知 preamble 互相关定位有效信号。
- 每周期独立 FFT，并计算 `H_p(f_k)=Y_p(f_k)/X(f_k)`。
- 支持复数谱平均和功率平均。
- 返回只含 manifest tones 的 sparse `SpectrumData`。
- 每个 tone 的模拟幅值恢复绝对误差不超过 provisional `0.05 dB`。
- 无共同采样时钟证明时 `phase_status=relative_unreliable`。
- hash、tone set、采样率、周期或 manifest layout 不一致时明确失败。
- 仅接受 `simulated` / `software_validation`，不允许进入科研分析。

## 完成内容

- S3 `generate_dual_mode_mock` 新增 `recording_delay_samples`；录音前补零并把 delay、period、nominal sample rate 和 `common_sampling_clock=false` 写入 sidecar/mock manifest。
- `make_mock_data.py` 新增 `--recording-delay-samples` CLI 参数。
- 新增公共入口 `load_multisine_measurement(...)`，返回 canonical sparse-tone `SpectrumData`。
- 使用按滑动窗能量归一化的 preamble 互相关；这避免高能量 discard periods 劫持同步峰。
- manifest 是 discard/stable period 数量与 period layout 的权威来源；录音不足完整 stable periods 时失败，不补零、不截取半周期。
- 每周期执行 `rfft`，仅抽取 manifest resolved stimulus tones 对应的整数 DFT bins。
- `complex_spectrum` 计算每周期复数 `H_p` 的平均；`power` 计算 `sqrt(mean(abs(H_p)^2))`。
- 输出 `magnitude_quantity=transfer_ratio`、`representation=sparse_tones`；没有生成 dense 物理频响。
- stimulus/recording 的实际 SHA-256 与 metadata、sidecar、manifest 形成一致性链；同时校验 stimulus ID、tone set、nominal sample rate、period length 和 manifest period layout。
- P8-B 的 clock drift、missing tones、clipping 和 leakage 指标显式记录为 `unavailable`。

## 未完成和明确非范围

- 不实现 clock drift 估计或校正。
- 不实现 missing-tone 检测、per-tone SNR、完整 clipping/leakage QC 或 period-variance 阈值。
- 不把 phase 提升为 `drift_corrected` 或 `common_clock`，也不让 phase 进入最终分析。
- 不实现真实 multisine adapter 资格开放；P8-A 主动拒绝 `research_analysis`。
- 不实现 P4、P5、P9、FeatureSet、分类或科研报告。
- 不把 sparse tones 插值成 dense physical frequency response。
- 不把 P8-A 接入仍为配置门的完整 `run_pipeline.py` 执行链。

## 关键设计决策

| 决策 | 结果 |
|---|---|
| 公共接口保持单一 | `load_multisine_measurement` 隐藏 WAV/JSON 校验、同步、FFT 和聚合细节。 |
| 归一化互相关 | 原始 tracer 后的污染测试发现未归一化相关会被高能量周期劫持；按滑动窗能量归一化后可稳定定位 preamble。 |
| manifest 决定周期边界 | discard/stable count 和 period layout 不从录音猜测，也不由 estimator config 覆盖。 |
| 整周期矩形帧 | tone 已位于整数 DFT bins；不加窗，避免改变 `Y/X` 幅值标定。 |
| 保留 per-period 复数传递内部层 | P8-B 可在聚合前增加 drift/QC，而不改变 P8-A 公共返回类型。 |
| 两种平均语义显式 | `complex_spectrum` 保留相干复数平均；`power` 返回 RMS 幅值且不输出 phase 数组。 |
| phase 从严 | 即使模拟数据零 drift，也没有共同采样时钟证据，因此状态始终为 `relative_unreliable`。 |
| P8-A maturity gate | 本切片只允许 simulated software validation；P8-B/真实验证完成前不开放科研入口。 |

## 修改文件

功能、配置和脚本：

- `src/acoustic_encoder/io_multisine.py`
- `src/acoustic_encoder/multisine_estimation.py`
- `src/acoustic_encoder/mock_data.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `scripts/make_mock_data.py`
- `config/experiment_v2_u4_multisine.yaml`
- `config/default.yaml`
- `config/schema_versions.yaml`

测试：

- `tests/test_io_multisine.py`
- `tests/test_mock_data.py`
- `tests/test_config.py`

文档：

- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `CHANGELOG.md`
- `docs/DEV_A_TEST_AND_MOCK_PLAN.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-B2_P8A_SYNC_AND_MAGNITUDE_RECOVERY.md`

## Schema/config/API 变化

| 项目 | DEV-B1 | DEV-B2 |
|---|---:|---:|
| `pipeline_version` | `2.0.0-dev.2` | `2.0.0-dev.3` |
| `config_schema_version` | `2.1.0` | `2.2.0` |
| `measurement_schema_version` | `2.2.0` | `2.2.0`（不变） |
| `feature_schema_version` | `2.0.0` | `2.0.0`（不变） |
| P7 manifest schema | `1.0.0` | `1.0.0`（不变） |

Configuration schema 2.2 要求 multisine estimator 使用 `synchronization_method: preamble_cross_correlation`，并显式选择 `period_averaging: complex_spectrum` 或 `power`。

新增 API：

```python
load_multisine_measurement(
    recording_path,
    stimulus_manifest_path,
    meta,
    *,
    run_purpose,
    period_averaging,
) -> SpectrumData
```

新增领域错误：`MultisineImportError`、`MultisineConsistencyError`、`MultisineSynchronizationError`。

## 数据来源、provenance 和科研资格

本步骤只使用 P7/S3 生成的确定性 synthetic artifacts：

- P7 stimulus WAV/manifest：由当前配置生成，WAV SHA-256 写入 manifest。
- S3 recording：通过 `known_transfer_db` 对 stimulus 施加已知幅值传递，再加入固定随机种子的微量噪声和可配置前置延迟。
- truth：S3 `known_H.csv` / `known_transfer_db`，只用于软件恢复误差测试。
- metadata：`data_origin=simulated`、`dataset_role=software_validation`、`eligible_for_scientific_analysis=false`。
- sidecar：记录 source/stimulus hashes、tone set、sample rate、period、delay 和 `common_sampling_clock=false`。

没有读取或分析任何项目 `real_experiment` 数据。所有输出均禁止用于声学结构科研结论。

## 验证命令及准确结果

实现前基线：

```powershell
python -m pytest -q
```

```text
44 passed in 2.10s
```

最终完整工作树执行：

```powershell
python -m pytest -q
```

```text
64 passed in 7.01s
```

```powershell
python -m compileall -q src scripts
```

准确结果：退出码 0，无标准输出。

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4_multisine.yaml --validate-only
```

准确结果：退出码 0；解析得到 pipeline `2.0.0-dev.3`、config schema `2.2.0`、`preamble_cross_correlation`、`complex_spectrum` 和 `software_validation`。

```powershell
python scripts/make_mock_data.py --output-root work/dev_b2_mock --recording-delay-samples 1379 --overwrite
```

准确结果：退出码 0，输出：

```text
Generated mock manifest: work\dev_b2_mock\mock_manifest.json
MOCK ONLY: these files must not be used as research results.
```

TDD 过程中每项行为按单测试 RED→GREEN 推进。特别是 discard-period 污染回归首次暴露未归一化互相关的错误同步，改用 normalized cross-correlation 后通过。

## 生成输出

- 公共 API 返回内存中的 sparse-tone `SpectrumData`；broadband 配置包含 1000–8000 Hz、100 Hz 间隔的 71 个 tones。
- `complex_spectrum` 输出 transfer magnitude、相对复数 phase 和 `relative_unreliable` 状态。
- `power` 输出 RMS transfer magnitude、`phase_rad=None` 和 `relative_unreliable` 状态。
- 本地验证生成 `work/dev_b2_mock/`，包括 P7 stimulus artifacts、8 份模拟 multisine WAV/sidecar、对应 sweep/truth 和 mock manifest；`work/` 不进入提交。
- 本切片不写 processed scientific artifact，也不生成科研图表或结论。

## 已知限制和 provisional 参数

- 幅值恢复容差 `0.05 dB` 只适用于 deterministic S3 software validation，不是实测 QC 阈值。
- 容差制定前的只读探查覆盖 8 个现有 S3 条件和 1379-sample delay；观察到最坏误差为 complex `0.011935825 dB`、power `0.011881277 dB`。该探查不是 pytest 验收结果。
- normalized correlation 当前记录定位结果但没有冻结真实录音的 correlation-peak acceptance threshold。
- nominal sample rate 必须相同；实际 drift 未估计、未校正。
- 所有 tones 当前视为有效；missing-tone、SNR、clipping、leakage 与 period variance 留给 P8-B。
- complex averaging 的 phase 仅是相对诊断量，不可作为最终 phase 证据。
- 只验证 mono WAV；多通道选择仍由未来 adapter/QC 切片处理。

## 下一步及进入门槛

下一步为 P8-B。进入门槛：

- 保持本步骤的 artifact consistency、normalized preamble sync、manifest period boundaries 和 sparse output 不变量。
- 在 per-period complex `H_p(f_k)` 聚合前实现并测试 clock drift 诊断/校正。
- 为 clipping、leakage、SNR、missing tones 和 period variance 建立 synthetic fault-injection fixtures 与明确 QC 状态。
- 只有 drift/common-clock 证据通过后才允许提升 `phase_status` 或把 phase 交给下游。
- 冻结真实阈值前必须使用模拟 sweep、少量诊断录音和明确 calibration 方案；不得用最终 test data 调阈值。
- P8-B 完成仍不自动授权科研分析；真实数据还必须满足 provenance hard gate 和独立实验 metadata 要求。

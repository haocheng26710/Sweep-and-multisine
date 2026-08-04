# DEV-B3 / P8-B1：clock drift 检测、阈值决策与可审计校正

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 提交边界：本报告、实现、测试和相关文档位于同一个 `feat(multisine): detect and correct sampling clock drift` 提交；最终 SHA 由该提交的 Git 记录给出。

“完成”只表示模拟软件验证切片通过，不表示真实 multisine 数据、完整 tone QC、`common_clock` 证明或科研结论已经完成。

## 目标与验收标准

本步在 DEV-B2/P8-A 的 preamble 同步和逐周期复数传递谱之上，实现常量 signed sampling-clock drift 的检测、配置阈值决策和可审计时间轴校正。

验收标准：

- S3 分别模拟正、负 ppm 采样时钟偏差；固定前置 delay 与累计 time warp 是两个独立参数。
- 从跨周期变化估计 signed ppm，不把单一全局延迟解释成 clock drift。
- `warning_ppm`、`exclude_candidate_ppm` 和 `correction` 全部来自配置并接受一致性校验。
- `correction=disabled` 时按阈值产生 `valid`、`warning` 或 `exclude_candidate`，但 phase 保持 `relative_unreliable`。
- `correction=enabled` 时校正录音时间轴，并重新执行 preamble 定位、周期切分、FFT 和 tone transfer 估计。
- 记录估计 drift、校正比率、方法、残余 drift、拟合误差和校正前后 magnitude 变化。
- 只有校正实际执行、残余 drift decision 为 `valid` 且输出有 complex phase 时才设置 `phase_status=drift_corrected`。
- 本步任何路径都不产生 `phase_status=common_clock`。
- 估计数据不足或无可观测 tone 能量时明确失败，不返回虚假 `0 ppm`。
- 保持 P8-A 未启用 drift 的路径、artifact linkage 门禁和 sparse-tone 输出兼容。
- 全部输入继续是 `simulated` / `software_validation` / `eligible_for_scientific_analysis=false`。

## 完成内容

- 新增独立 `clock_drift` 模块，提供 signed drift estimate、inclusive threshold decision 和录音时间轴校正。
- 估计器使用相邻稳定周期的复数 transfer 交叉相位，并保留 period/tone 数量与相位拟合 RMSE。
- S3 新增 `sampling_clock_drift_ppm`；正 ppm 产生更多录音 samples，负 ppm 产生更少 samples，随后才添加独立 `recording_delay_samples`。
- S3 sidecar/mock manifest 记录 requested signed ppm、模拟方法、固定 delay 和 `common_sampling_clock=false`；mock schema 升至 `1.1.0`。
- `make_mock_data.py` 新增 `--sampling-clock-drift-ppm`。
- `load_multisine_measurement` 新增可选 `clock_drift_config`；`None` 保留 P8-A 的 `clock_drift="unavailable"` 行为。
- disabled 路径只估计和分类，不改写 recording，不提升 phase。
- enabled 路径对 recording 做时间轴重采样，并从校正后的 audio 重新同步和估计，不复用校正前的周期边界或 transfer。
- `SpectrumData.quality_metrics.clock_drift` 成为结构化 QC 视图，包含配置阈值、校正前后 estimate、decision、ratio、方法、sample counts、拟合误差、magnitude change 和 phase decision。
- 配置层拒绝非有限、非正或倒置 ppm 阈值，以及未知 correction mode。
- pipeline/config/measurement 版本分别提升到 `2.0.0-dev.4`、`2.3.0`、`2.3.0`。
- P8-A 的 hash、tone set、sample rate、period length、manifest layout、完整周期和 research-scope 门禁全部继续通过回归。

## 未完成和明确非范围

- 不实现数字削波 QC。
- 不实现 per-tone SNR、tone leakage、missing tone、非激励频率异常能量或完整 `tone_quality.csv`。
- 不实现随时间变化的非线性 drift、分段 drift 或更高阶时钟模型；S3 和 estimator 当前目标是录音内常量 ppm。
- 不证明物理 `common_clock`，也不把 `drift_corrected` 等同于 `common_clock`。
- 不开放真实 multisine `research_analysis`；P8-B1 仍由 maturity gate 限制为模拟软件验证。
- 不把 sparse tones 插值成 dense 物理频响。
- 不实现 P4、P5、P9、FeatureSet、分类或科研报告。
- 不生成完整 tone-level QC 输出；这些属于 DEV-B4/P8-B2。

## Drift 算法及可识别性

DEV-B2 保留每个稳定周期、每个 tone 的复数传递：

```text
H_p(f_k) = Y_p(f_k) / X(f_k)
```

对相邻周期计算：

```text
C_k = sum_p H_(p+1)(f_k) * conj(H_p(f_k))
delta_phi_k = angle(C_k)
```

令 `k` 为该 tone 在一个 stimulus period 内的 DFT bin，使用观测到的相邻周期乘积幅值作为权重，对 `delta_phi_k = beta * k` 做过原点的加权最小二乘拟合。若输出/输入采样时钟比为 `r`：

```text
beta = 2*pi*(1/r - 1)
r_hat = 1 / (1 + beta/(2*pi))
signed_drift_ppm = (r_hat - 1) * 1e6
```

signed convention：正 ppm 表示输出采样时钟更快，同一物理 stimulus period 在 recording 中占用更多 samples；负 ppm 相反。

该方法可识别的原因：

- 静态声学传递函数的复数相位在相邻周期共轭乘积中抵消。
- 固定前置延迟对所有稳定周期提供共同相位偏置，也在相邻周期差分中抵消。
- sampling-clock drift 随周期持续累积，产生与 tone bin 成比例的相邻周期相位步进。
- estimator 只读取当前 recording、P7 manifest 和逐周期 transfer；它不读取 S3 requested ppm、known-`H(f)`、angle、configuration 或任何方向标签。

校正使用：

```text
correction_ratio = 1 / (1 + estimated_ppm * 1e-6)
```

录音通过 quintic-spline time-axis resampling 回到 stimulus clock，再完整重跑 preamble 同步、manifest period segmentation 和 tone estimation。S3 模拟端使用独立的 cubic-spline time warp，避免模拟与校正使用完全相同的数值算子。

## 阈值和 phase_status 决策

阈值边界为 inclusive：

```text
abs(ppm) >= exclude_candidate_ppm  -> exclude_candidate
abs(ppm) >= warning_ppm            -> warning
otherwise                          -> valid
```

phase 状态机：

| 条件 | `phase_status` |
|---|---|
| correction disabled | `relative_unreliable` |
| correction enabled，但 residual 为 warning/exclude | `relative_unreliable` |
| correction enabled 且通过，但 period averaging 为 power、无 phase 输出 | `relative_unreliable` |
| correction enabled、实际执行、residual valid、complex output | `drift_corrected` |
| 任意 P8-B1 路径 | 永不设置 `common_clock` |

校正前 decision 保留在 `pre_correction` 中；校正后的 residual decision 是 `final_decision`。因此一个校正前的 warning/exclude candidate 可以在成功校正后形成 final `valid`，但完整审计记录不会丢失。

## 关键设计决策

| 决策 | 结果 |
|---|---|
| 相邻周期交叉相位 | 将固定系统 phase 和全局 delay 与持续累计 drift 分离。 |
| signed exact ratio 公式 | 不用小量近似决定正负号；ppm 从拟合 slope 显式换算。 |
| 原始 recording 上校正 | 校正后重新同步和切周期，不用已受 drift 污染的旧 boundaries。 |
| 模拟/校正使用不同 spline order | 降低使用同一个逆算子造成过于乐观验证的风险。 |
| residual gate 决定 phase 升级 | correction mode 本身不能授权 phase；必须有成功记录和 residual valid。 |
| power averaging 不升级 phase | 即使 clock correction 通过，`phase_rad=None` 时也不声称 phase 可用。 |
| 失败不伪装成 0 ppm | 少于两个周期或没有可观测 tone energy 时抛出 `MultisineClockDriftError`。 |
| truth 不进入 production QC | known-`H(f)` 误差只由 S3 测试/审计命令计算；运行时只记录可观测拟合误差和 magnitude change。 |
| P8-A optional API | `clock_drift_config=None` 保持现有调用和 `unavailable` QC 完全兼容。 |

## 修改文件

功能、配置和脚本：

- `src/acoustic_encoder/clock_drift.py`
- `src/acoustic_encoder/io_multisine.py`
- `src/acoustic_encoder/mock_data.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `scripts/make_mock_data.py`
- `config/default.yaml`
- `config/schema_versions.yaml`

测试：

- `tests/test_clock_drift.py`
- `tests/test_io_multisine.py`
- `tests/test_mock_data.py`
- `tests/test_config.py`
- `tests/test_schemas.py`

文档：

- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-B3_P8B1_CLOCK_DRIFT.md`

## Schema/config/API 变化

| 项目 | DEV-B2 | DEV-B3 |
|---|---:|---:|
| `pipeline_version` | `2.0.0-dev.3` | `2.0.0-dev.4` |
| `config_schema_version` | `2.2.0` | `2.3.0` |
| `measurement_schema_version` | `2.2.0` | `2.3.0` |
| `feature_schema_version` | `2.0.0` | `2.0.0`（不变） |
| P7 manifest schema | `1.0.0` | `1.0.0`（不变） |
| S3 mock schema | `1.0.0` | `1.1.0` |
| clock drift QC schema | 不可用 | `1.0.0` |

配置契约：

```yaml
multisine_estimation:
  clock_drift:
    warning_ppm: 20
    exclude_candidate_ppm: 100
    correction: disabled  # disabled | enabled
```

要求 `0 < warning_ppm < exclude_candidate_ppm`，两者必须有限。`correction` 只能是 `disabled` 或 `enabled`。

P8 API 增量：

```python
load_multisine_measurement(
    recording_path,
    stimulus_manifest_path,
    meta,
    *,
    run_purpose,
    period_averaging,
    clock_drift_config=None,
) -> SpectrumData
```

S3 API 增量：

```python
generate_dual_mode_mock(
    ...,
    recording_delay_samples=0,
    sampling_clock_drift_ppm=0.0,
)
```

新领域错误：`ClockDriftEstimationError` 和 `MultisineClockDriftError`。

## `quality_metrics.clock_drift` 输出

结构化视图包含：

- `qc_schema_version`
- `estimator_method`
- `thresholds.warning_ppm`、`exclude_candidate_ppm` 和 inclusive boundary policy
- `pre_correction.signed_drift_ppm`、absolute drift、period timing error、fit RMSE、period/tone count 和 decision
- `correction.mode`、applied、successful、method、ratio、input/output sample counts 和 failure reason
- `post_correction.signed_residual_drift_ppm`、absolute residual、period timing error、fit RMSE、decision 和 magnitude change max/RMS
- `final_decision`
- `phase_status`

P8-B1 仍将 `missing_tones`、`clipping` 和 `leakage` 明确保持为 `unavailable`。

## 数据来源、provenance 和科研资格

本步只使用 P7/S3 deterministic simulated artifacts：

- P7 `stimulus.wav` / `stimulus_manifest.json` 由当前 stimulus config 生成，WAV SHA-256 写入 manifest。
- S3 先通过 `known_transfer_db` 施加已知 magnitude-only `H(f)`，加入固定随机种子噪声，再施加 signed cubic-spline clock time warp，最后增加独立的 1379-sample delay。
- S3 requested ppm 和 known `H(f)` 只供软件验证测试/审计命令比较；production estimator 不读取它们。
- metadata 始终为 `data_origin=simulated`、`dataset_role=software_validation`、`eligible_for_scientific_analysis=false`。
- sidecar 保留 source/stimulus SHA-256、tone set、sample rate、period、delay、requested ppm、simulation method 和 `common_sampling_clock=false`。
- `run_purpose` 始终为 `software_validation`；P8 maturity gate 继续拒绝 `research_analysis`。

没有读取或分析任何项目 `real_experiment` 数据。上述模拟输出不能用于声学结构科研结论。

## TDD 与验证命令及准确结果

只读基线复跑：

```powershell
python -m pytest -q
```

```text
64 passed in 8.42s
```

TDD 中已实际观察到的 RED 包括：

- 首个 estimator 测试因 `ModuleNotFoundError: No module named 'acoustic_encoder.clock_drift'` collection failure。
- enabled 路径最初以 `Unsupported clock drift correction mode: 'enabled'` 失败。
- 非法 correction mode 和 ppm threshold tests 最初因 `DID NOT RAISE ConfigError` 失败。
- zero-observation 测试最初暴露 zero-weight division；改为明确 `ClockDriftEstimationError` 后通过。

受影响模块回归：

```powershell
python -m pytest -q tests/test_clock_drift.py tests/test_io_multisine.py tests/test_mock_data.py tests/test_config.py
```

```text
54 passed in 9.58s
```

首次完整工作树回归：

```powershell
python -m pytest -q
```

```text
93 passed in 10.82s
```

文档同步后的最终完整工作树回归：

```powershell
python -m pytest -q
```

```text
93 passed in 10.47s
```

字节码编译：

```powershell
python -m compileall -q src tests scripts
```

准确结果：退出码 0，无标准输出。

配置验证：

```powershell
python scripts/run_pipeline.py --config config/experiment_v2_u4_multisine.yaml --validate-only
```

准确结果：退出码 0；解析得到 pipeline `2.0.0-dev.4`、config schema `2.3.0`、measurement schema `2.3.0`、`warning_ppm=20`、`exclude_candidate_ppm=100`、`correction=disabled` 和 `run_purpose=software_validation`。

## 校正前后误差审计

使用 broadband 71-tone P7 stimulus、8 个稳定周期、1379-sample delay、S3 seed 123 和 U4ENC/A000 条件，在临时目录分别生成 `+80 ppm` 与 `-80 ppm` recording。命令通过 public S3 和 `load_multisine_measurement` API 分别运行 disabled/enabled，并由测试侧 `known_transfer_db` 计算 truth error；临时目录在命令结束时删除。

| requested ppm | estimated ppm | correction ratio | residual ppm | pre max abs error dB | post max abs error dB | post RMS error dB | phase |
|---:|---:|---:|---:|---:|---:|---:|---|
| +80 | +79.975531742 | 0.999920030864 | +0.002277023 | 4.063162775 | 0.019509646 | 0.007576794 | `drift_corrected` |
| -80 | -79.983415843 | 1.000079989814 | -0.010772371 | 4.238873713 | 0.019249274 | 0.007530865 | `drift_corrected` |

对应 pre/post phase-fit RMSE：

- `+80 ppm`：`0.000656149253 rad` → `0.000670237708 rad`
- `-80 ppm`：`0.001427597963 rad` → `0.000665673246 rad`

truth magnitude error 没有写入 production `quality_metrics`；这是避免 estimator 使用方向标签或模拟 truth 的有意边界。运行时记录的是可观测的 phase-fit error 和校正前后 magnitude change。

## 生成输出

- public API 返回 canonical `Representation.SPARSE_TONES` `SpectrumData`；不生成 dense physical response。
- disabled 路径返回未经校正的 tone estimate 和完整 pre-correction QC。
- enabled 路径返回从校正 recording 重新估计的 tone magnitude/phase 和完整 pre/post clock QC。
- S3 sidecar/mock manifest 新增 signed ppm 和模拟方法字段。
- 审计命令只在系统临时目录生成模拟 artifacts，命令结束后删除；没有把验证数据提交到仓库。
- 本切片不生成 `tone_quality.csv`、processed scientific artifact、科研图表或科研结论。

## 已知限制和 provisional 参数

- `warning_ppm=20`、`exclude_candidate_ppm=100` 是配置中的 provisional 软件验证参数，不是实测硬件冻结阈值。
- signed ppm test tolerance 为 `±1 ppm`；校正后 known-`H(f)` 最大幅值误差 tolerance 保持 DEV-B2 的 `0.05 dB`。它们只适用于当前 S3 software validation。
- adjacent-period phase estimator 存在 phase-wrap 可识别范围；当前最高 tone bin 为 800，对常量 drift 的近似无歧义范围为 `±625 ppm`。当前 exclude threshold 100 ppm 位于该范围内。
- quintic-spline correction 是可审计的 provisional 时间轴方法，尚未用真实 ADC/DAC 时钟或标定信号验证。
- estimator 当前假定一个 recording 内 drift 为常量；不处理 drift rate 随时间变化或 discontinuity。
- fit RMSE 被记录但本步没有另设独立 fit-RMSE 阈值；低 SNR、missing tone 和 leakage 对 drift 可靠性的进一步限制属于 P8-B2。
- `drift_corrected` 只表示该软件 clock correction gate 通过，不表示 shared/common clock，也不自动授权最终 phase 科研使用。
- `power` averaging 即使 correction 通过也保持 `phase_rad=None` 和 `relative_unreliable`。
- P8-B1 仍只验证 mono WAV；真实多通道选择和 adapter maturity 未开放。

## P8-B2 接口边界、下一步及进入门槛

下一步为 DEV-B4 / P8-B2。P8-B1 已把校正后的 recording 重新变换为逐周期复数 `H_p(f_k)`，P8-B2 应在最终 period aggregation 前消费该内部层，并保持 `clock_drift` 审计视图不变。

P8-B2 负责：

- 数字 clipping QC；
- per-tone SNR；
- tone leakage；
- missing tone；
- 非激励频率异常能量；
- tone-level `valid_mask` 和完整 `tone_quality.csv`。

进入门槛：

- 保持 P8-A artifact linkage、preamble sync、manifest period boundaries、sparse output 和 research maturity gate 不变。
- P8-B2 fault injection 必须在 drift correction 后的逐周期数据上运行，并覆盖 clock QC 与 tone QC 的组合优先级。
- tone thresholds 必须配置化，并使用模拟/诊断数据冻结；不得使用未来最终 test data、angle 或 configuration 标签调参。
- tone QC 可以降低总体 QC 或屏蔽 tones，但不能把 phase 提升为 `common_clock`，也不能覆盖 P8-B1 的 pre/post drift 审计记录。
- 真实数据进入仍需 provenance hard gate、合格 `real_experiment` metadata 和独立 adapter/QC 验证；P8-B2 完成本身不自动授予科研资格。

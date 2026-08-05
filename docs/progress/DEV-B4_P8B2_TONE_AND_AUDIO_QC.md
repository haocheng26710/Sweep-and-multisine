# DEV-B4 / P8-B2：数字完整性、per-tone 质量指标与 P8 QC 汇总

## 状态、日期和分支

- 状态：完成（模拟软件验证切片）
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 提交边界：本报告、实现、测试、配置和迁移说明位于同一个 `feat(multisine): add tone and audio quality control` 本地提交；最终 SHA 由该提交的 Git 记录给出。

“完成”不表示真实实验阈值已经冻结，也不表示模拟数据可以用于科研结论。P8 当前仍只接受 `simulated`、`software_validation`、`eligible_for_scientific_analysis=false`。

## 目标与验收标准

本步在 P8-A 的同步/逐周期 FFT 和 P8-B1 的 clock-drift 状态机之上，增加不删除数据、不修改人工有效性的 P8-B2 QC：

- 统计 integer PCM 和 float WAV 的数字削波样本、比例、channel 和最长连续区段；
- 对每个 manifest tone 估计局部非激励 bin SNR、邻近泄漏、周期稳定性和 missing-tone 状态；
- 估计稳定分析周期内的非激励频率能量，不把 preamble 纳入；
- 对不可估计的项目返回 `unavailable`，不伪造数值；
- 以 `valid < warning < exclude_candidate` 聚合 measurement QC，保留所有原因；
- 不修改 `MeasurementMeta.valid`，不删除 bad tone，不改变 P8-B1 `phase_status`；
- 在 `SpectrumData.quality_metrics` 中保存结构化证据，并生成规定 CSV、序列化 spectrum 和诊断图；
- 所有阈值和 FFT 邻域集中在 YAML，并验证有限性、范围及 warning/exclude 顺序；
- S3 能确定性注入 clipping、missing tone、白噪声、非激励 tone 和逐周期 gain/phase 扰动；
- P8-A、P8-B1、manifest/hash/sample-rate/tone-set 门禁全部保持回归兼容。

## 完成内容

- P8 period estimate 现在保留每周期完整 `rfft`、稳定周期波形、tone bin 和完整 normalized-correlation trace；最终输出仍只包含 manifest tones，不把 off-tone bins 暴露为 dense 频响。
- 新增 P8-B2 QC 模块，返回 `ToneQualityRecord`、measurement QC、tone-level `valid_mask` 和原始 clipping 证据。
- WAV adapter 支持 float 和 signed/unsigned integer PCM 的 full-scale 归一化，并按 metadata 选择 channel；channel 不存在时明确失败。
- clipping 检查扫描全部所选 channel samples，而不是只看单个最大值；QC 不改写录音或 spectrum 数值。
- SNR、leakage、period variance、missing tone 和非激励能量均有明确 `unavailable` 路径。
- tone QC 保留 `snr_method`、实际 noise-bin 数、leakage 方法/guard/radius/bin 数、period 方法/周期数、辅助 magnitude variance 和 circular phase variance。
- `valid_tone` 只屏蔽 `exclude_candidate` tone；warning 和 unavailable tone 仍保留。所有 71 个 tone 行及 transfer 值始终写出。
- measurement QC 汇总 clipping、missing counts、tone 状态计数、非激励能量、unavailable 列表和聚合策略；不翻转 `MeasurementMeta.valid`。
- 新增 output writer 和命令行入口，生成四个结构化 CSV、`SpectrumData` NPZ/JSON 以及两个诊断 PNG。
- S3 mock schema 升到 `1.2.0`，sidecar/manifest 记录所有注入参数；默认仍是 clean simulated validation。
- pipeline/config/measurement 版本分别升到 `2.0.0-dev.5`、`2.4.0`、`2.4.0`。

## 未完成和明确非范围

- 不实现 P3 `FeatureSet`、P4/P5、P9 tone 选择、分类或科研结论。
- 不冻结真实实验阈值；本步 YAML 数值仅用于模拟软件验证。
- 不把数字 clipping 等同于模拟前端、ADC 或模拟链路所有失真；这里只检测 WAV 中的数字 full-scale-like samples。
- 不定位非激励能量的物理来源，只报告能量异常及其 QC 状态。
- 不实现时变/非线性 clock drift；P8-B1 的常量 ppm 模型保持不变。
- 不将 `drift_corrected` 提升为 `common_clock`，也不改变 P8-B1 phase 状态机。
- 不插值 sparse tones，不生成 dense 物理频响。
- 不把 diagnostic PNG 当作科研图表或实验结论。

## 数学定义、邻域和 guard 规则

令稳定周期编号为 `p`，FFT bin 为 `j`，tone bin 为 `k`，每周期复数 transfer 为 `H_p(k)=Y_p(k)/X(k)`，跨周期平均 bin 功率为：

```text
P(j) = mean_p |Y_p(j)|^2
```

当前配置使用 `tone_guard_bins=g=1`。对所有合法激励 tone 建立并集 guard；任何合法 tone 及其 `±g` bins 都不能被当作 noise、leakage 或全局 off-tone energy。

### 数字削波

```text
clipped[n] = |x[n]| >= 0.999 full scale
sample_count = sum_n clipped[n]
fraction = sample_count / N
```

同时记录最长连续 `true` run、selected channel 和原始 WAV dtype。warning/exclusion 使用 clipping fraction 的 inclusive `>=` 边界。检查只读，不修改样本。

### Per-tone SNR

对于 tone `k`，候选 noise bins 满足 `4 <= |j-k| <= 8`，排除 DC 和所有合法 tone guard。至少需要 4 个候选 bins：

```text
P_noise(k) = median_j P(j)
SNR(k) = 10 log10(P(k) / P_noise(k))
```

`P(k)<=0`、noise power 非正/非有限或候选 bins 不足时为 `unavailable`。

### Tone leakage

候选 leakage bins 满足 `1 < |j-k| <= 3`，并排除其他合法 tone 及其 guard：

```text
leakage_ratio(k) = sum_j P(j) / P(k)
```

至少需要 2 个合法 leakage bins；tone power 非正/非有限或 bins 不足时为 `unavailable`。相邻合法激励 tone 有独立单元测试证明不会被计为 leakage。

### Missing tone

若 transfer magnitude `<= -80 dB`，直接标记 missing。否则只在 SNR 可用时以 `SNR <= 20 dB` 判断。magnitude 未触发 missing 且 SNR 不可用时，missing 状态为 `unavailable`，不猜测 true/false。

### 周期间稳定性

默认 `complex_relative_variance`：

```text
V_complex(k) = mean_p |H_p(k) - mean_p H_p(k)|^2 / mean_p |H_p(k)|^2
```

可配置 `power_relative_variance`：

```text
V_power(k) = var_p(|H_p(k)|^2) / mean_p(|H_p(k)|^2)^2
```

另行输出 period magnitude 的 sample variance（dB²）和 phase circular variance。少于 3 个周期或 transfer power 非正/非有限时为 `unavailable`。

### 非激励频率异常能量

只使用 preamble 同步后截取的整数个稳定周期。排除 DC、所有 tone bins 和 `±1` guards：

```text
R_off = sum_(j in off bins) P(j) / sum_(j > 0) P(j)
```

候选 off bins 少于 16、总非 DC 能量非正或非有限时为 `unavailable`。S3 测试覆盖 50 Hz、60 Hz 和 600 Hz 非激励/谐波式注入。

## Unavailable 条件

| 项目 | `unavailable` 条件 |
|---|---|
| SNR | tone power 无效；局部 noise power 无效；合法 noise bins 少于配置值 |
| leakage | tone power 无效；合法 leakage bins 少于配置值 |
| period variance | 稳定周期少于配置值；transfer power 无效 |
| missing tone | magnitude 未直接判 missing，且 SNR unavailable |
| non-excited energy | 合法 off bins 不足；总非 DC 能量无效 |
| clock drift | 调用方未提供 P8-B1 drift 配置；原有 P8-A 行为保持兼容 |

`unavailable` 不伪造 `0`、`false`、`+inf` 或其他替代数值。若 measurement 没有更严重问题，任一 unavailable 会把总体状态从 valid 提升为 warning。

## QC 聚合和 phase 决策

聚合优先级：

```text
exclude_candidate > warning > valid
```

- 任一 missing tone 或任一 per-tone exclude 状态产生 measurement `exclude_candidate`。
- clipping、非激励能量和 P8-B1 final clock decision 参与 measurement 聚合。
- unavailable 不覆盖已有 exclude/warning；若其他项目均 valid，则总体为 warning。
- 每个 tone 的所有非 valid 原因都写入 `qc_reasons`，多项失败不会互相覆盖。
- `SpectrumData.valid_mask=false` 只用于 tone-level exclude candidate；tone 行和值不删除。
- `MeasurementMeta.valid` 完全保留输入值，不由自动 QC 翻转。
- `phase_status` 继续完全由 P8-B1 决定，只可能是当前模拟路径允许的 `relative_unreliable` 或 `drift_corrected`；P8-B2 不产生 `common_clock`。

## 配置、schema 和 API 变化

### YAML 配置

`config/experiment_v2_u4_multisine.yaml` 的 `multisine_estimation.tone_quality` 现在包含：

| 分组 | 当前模拟验证值 |
|---|---|
| neighborhood | guard `1`；leakage radius `3`；noise radius `4..8`；minimum noise/leakage bins `4/2` |
| clipping | sample threshold `0.999`；warning fraction `1e-6`；exclude fraction `1e-3`；记录最长 run |
| SNR | median local non-excited bin power；warning `<30 dB`；exclude `<=20 dB` |
| leakage | warning `>=0.01`；exclude `>=0.05` |
| missing tone | minimum SNR `20 dB`；minimum magnitude `-80 dB` |
| period stability | complex relative variance；minimum periods `3`；warning `>=0.005`；exclude `>=0.02` |
| non-excited energy | minimum bins `16`；warning `>=0.01`；exclude `>=0.05` |

配置验证检查 mapping 完整性、整数/正负范围、有限性、邻域半径顺序、method 枚举和 warning/exclude 顺序。warning/exclude 边界均为 inclusive。

### 版本与迁移

| 项目 | P8-B1 | P8-B2 |
|---|---|---|
| pipeline | `2.0.0-dev.4` | `2.0.0-dev.5` |
| config schema | `2.3.0` | `2.4.0` |
| measurement schema | `2.3.0` | `2.4.0` |
| feature schema | `2.0.0` | `2.0.0` |
| S3 mock schema | `1.1.0` | `1.2.0` |

显式 2.3 config/measurement 版本标记在 load 时只在内存中迁移为 2.4，记录 warning，不改写源 YAML。旧三字段 `tone_quality` 不被静默猜成完整阈值；执行 P8-B2 前仍须提供完整 2.4 配置。

### API

- `load_multisine_measurement(...)` 保持 P8-A/P8-B1 返回 `SpectrumData` 的兼容 API。
- `analyze_multisine_measurement(...)` 新增 `tone_quality_config`，返回 `MultisineQCAnalysis`。
- `PeriodTransferEstimate` 新增 full per-period spectra、analysis periods、tone bins 和 synchronization correlation trace。
- `write_multisine_qc_outputs(...)` 写结构化输出，不过滤 tone。
- `scripts/run_multisine_qc.py` 从 WAV、stimulus manifest、sidecar 和 resolved YAML 运行 P8 QC。

## 修改文件

### 实现和配置

- `src/acoustic_encoder/multisine_estimation.py`
- `src/acoustic_encoder/io_multisine.py`
- `src/acoustic_encoder/multisine_qc.py`
- `src/acoustic_encoder/multisine_outputs.py`
- `src/acoustic_encoder/mock_data.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `scripts/run_multisine_qc.py`
- `config/default.yaml`
- `config/schema_versions.yaml`
- `config/experiment_v2_u4_multisine.yaml`

### 测试和文档

- `tests/test_multisine_qc.py`
- `tests/test_mock_data.py`
- `tests/test_config.py`
- `tests/test_schemas.py`
- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-B4_P8B2_TONE_AND_AUDIO_QC.md`

## 数据来源、provenance 和科研资格

本步没有使用真实研究数据，也没有使用 REW external-reference curves。全部分析输入由 S3 使用现有 P7 `stimulus.wav` / `stimulus_manifest.json` 和已知 `H(f)` 生成，并保留：

- `data_origin=simulated`
- `dataset_role=software_validation`
- `run_purpose=software_validation`
- `eligible_for_scientific_analysis=false`
- `common_sampling_clock=false`

S3 注入选项包括 float32/PCM16 输出、additive white noise、missing tone、非激励正弦、逐周期 gain、逐周期 circular shift、数字 clipping run 和既有 signed ppm drift。参数写入 mock manifest/sidecar。测试标签或未来实验结果不参与阈值设定。

本地持久化 clean fixture 位于 `data/mock/DEV-B4_P8B2/`，仅用于软件验证且由 `.gitignore` 排除。它不能支持科研结论。

## 测试矩阵

- clean delayed recording：全部 tone/measurement valid；
- float32 clipping 和 PCM16 clipping：count、fraction、channel、longest run、boundary status；
- 单 missing tone、多 missing tones；
- white noise 导致低 SNR；
- 邻近非激励 bin leakage；
- 相邻合法激励 tone 不计为 leakage；
- 逐周期 gain/phase shift 抖动；
- complex relative variance 和配置化 power relative variance；
- 50 Hz、60 Hz 和 600 Hz 非激励/谐波式能量；
- warning/exclude inclusive 边界；
- noise/leakage/period/off-tone evidence 不足时 unavailable；
- 多项同时失败时原因完整保留；
- QC 不删除数据、不翻转 `MeasurementMeta.valid`；
- 输出 CSV/NPZ/JSON/PNG 结构和 spectrum round trip；
- 2.3→2.4 内存迁移和全部配置范围/顺序验证；
- P8-A/P8-B1 drift、hash、manifest、sample-rate、tone-set 和 phase 状态机完整回归。

## 实际执行命令及准确结果

### 全部测试

```powershell
python -m pytest -q
```

准确结果（最终提交前复验）：退出码 `0`；`122 passed in 15.42s`。

### Bytecode 编译

```powershell
python -m compileall -q src scripts tests
```

准确结果：退出码 `0`；无标准输出。

### 持久化 clean software-validation bundle

首先以 S3 生成 `U4ENC / 0°`、random state `20260805`、prefix delay `1379`、0 ppm、默认 clean QC fault 参数的模拟输入，然后执行：

```powershell
python scripts/run_multisine_qc.py --recording data/mock/DEV-B4_P8B2/multisine/V2_U4ENC_A000_S01_CONT_R01_MS.wav --stimulus-manifest data/mock/DEV-B4_P8B2/stimuli/ms_broadband_1k_8k_100hz_v1/stimulus_manifest.json --sidecar data/mock/DEV-B4_P8B2/multisine/V2_U4ENC_A000_S01_CONT_R01_MS.json --output-directory outputs/DEV-B4_P8B2_SOFTWARE_VALIDATION
```

准确结果：退出码 `0`；sample `mock_V2_U4ENC_A000_S01_CONT_R01_MS`；measurement QC `valid`；origin `simulated`；run purpose `software_validation`；scientific eligibility `false`。

该 bundle 的准确 clean 指标：

- tone count：71；tone status：全部 `valid`；
- minimum/maximum SNR：`47.61126921483373 / 68.58003054003927 dB`；
- maximum leakage ratio：`7.010733848367605e-05`；
- maximum complex period variance：`1.532937383683775e-05`；
- clipping count/fraction：`0 / 0.0`；
- missing-tone count：`0`；
- non-excited energy ratio：`4.4677209888470766e-05`；
- estimated drift：`-0.011711646208389936 ppm`，final clock decision `valid`；
- phase status：`relative_unreliable`，没有误标 `common_clock`。

## 生成输出

持久化 software-validation 输出目录：`outputs/DEV-B4_P8B2_SOFTWARE_VALIDATION/`。该目录由 `.gitignore` 排除，不属于代码提交；文件在本地保留以供审计。

| 文件 | 作用 | 本次大小 |
|---|---|---:|
| `transfer_tones.csv` | 71 个 sparse transfer tone 及 phase/valid view | 6864 bytes |
| `tone_quality.csv` | per-tone 指标、状态、方法和原因 | 19774 bytes |
| `clock_drift_qc.csv` | P8-B1 clock view | 352 bytes |
| `measurement_qc.csv` | clipping/missing/off-tone/总体状态/provenance | 480 bytes |
| `spectrum_data.npz` | authoritative arrays | 2985 bytes |
| `spectrum_data.json` | authoritative metadata/quality metrics/hash | 71062 bytes |
| `synchronization_diagnostic.png` | preamble correlation 与 analysis start | 65336 bytes |
| `period_consistency.png` | 每稳定周期 tone transfer magnitude | 78914 bytes |

两个 PNG 已实际打开检查：同步峰、preamble/analysis 边界和 8 个稳定周期曲线均可辨识，标题明确标记 simulated validation。

## 已知限制和 provisional 参数

- 所有 P8-B2 阈值是 simulation-only provisional values；不得直接冻结为真实实验 exclusion 规则。
- 固定 bin 邻域依赖 P7 integer-bin periodic stimulus；若未来 stimulus tone spacing 变密，配置验证不能代替 dataset-specific 可用-bin检查，后者会返回 unavailable。
- local median SNR 是谱 bin QC，不是校准声学 SPL SNR，也不替代独立噪声录音。
- leakage ratio 是邻近 bin 指标；远离 tone 的异常由 measurement-level non-excited energy 捕获。
- missing magnitude 使用 transfer ratio dB 的 provisional threshold；真实硬件的 noise/calibration floor 尚未建立。
- period circular shift 是 S3 phase-jitter fault model，不代表所有真实 phase instability。
- clipping 识别数字 full-scale-like samples；没有原始 ADC/模拟前端证据时不能诊断模拟削波。
- `valid_mask` 表示自动 tone-level exclusion candidate，不修改人工 `MeasurementMeta.valid`；下游必须同时保留原因。
- P8 仍由 research maturity gate 限制为模拟软件验证。

## 下一步及进入门槛

下一实现切片可进入 DEV-C/P3 `FeatureSet` 适配，但必须先满足：

- 继续把 `SpectrumData` 作为权威输入，CSV 只作为 view；
- P3 明确保留 sparse tone identity、tone QC、phase status 和 measurement provenance；
- warning/exclude tone 不得静默删除，任何训练/统计过滤必须生成审计记录；
- P8-B2 provisional thresholds 不得借 P3 固化为真实研究阈值；
- P4/P5/P9、真实实验 threshold freeze 和科研结论仍需各自独立门禁；
- 若要开放真实 multisine，必须先有合格 `real_experiment` sidecar/provenance、明确 common-clock/drift policy、校准/噪声证据和预先批准的 QC threshold-freeze 方案。

## 对应 Git commit

提交主题：`feat(multisine): add tone and audio quality control`。本报告、代码、配置、测试、README、迁移说明和 INDEX 在同一个本地提交中；未执行 push。

# DEV-C10 / P6-A — Sweep HR 峰值检测与可审计校准框架

## 状态、日期和分支

- 状态：完成（simulated software-validation 实现）
- 日期：2026-08-06
- 分支：`feature/v2-dual-input`
- 提交边界：本报告、实现、测试、配置和迁移位于同一提交 `feat(hr): add auditable sweep resonance calibration`
- 科研资格：`software_validation_only`、`frozen_for_research=false`、`scientifically_eligible=false`

## 目标与验收标准

本步从显式列出的、已持久化的 dense sweep `FeatureSet` 建立 P6-A：数据驱动峰检测、prominence、half-power crossing、bandwidth、Q、跨重复 drift、实测频带 overlap、线性功率积分、`q_i` 和 versioned/hash-audited `hr_calibration.json`。

验收边界是：P6-A 不读取 REW TXT/WAV/`SpectrumData`，不重跑 P1/P3，不扫描目录，不接收 multisine/sparse/tone/normalized/final-test 数据，不使用文件名或 design target 代替实测峰；所有结果必须链接精确 P2-B、输入/输出 hash 和 provenance。

## 完成内容

- 新增 version-1.0 `HRCalibrationScope`、scope member、显式 group、resonator search spec、final-test seal 和 approval record。
- 新增 version-1.0 input manifest；CLI 只读取其按序列出的 FeatureSet NPZ/JSON，并复核文件 hash、FeatureSet content/contract hash 和 scope 镜像字段。
- 只接受 `dense_raw_spl`、`rew_sweep`、`dense_spectrum`、normalization none、known `spl` quantity 和全 `dB` units。`dense_demeaned_db` 在本 API 中直接拒绝，不作为正式或补充 calibration 输入。
- 将 P3 dense writer 已存在但此前未填充的 `source_magnitude_quantity`、`source_magnitude_reference` 和 `source_phase_status` 写入新 FeatureSet。旧缺字段 artifact 不静默补义。
- 抽取共用权威 FeatureSet frequency-name parser；P4-B 保留原异常类型兼容。
- 对每个 sample/resonator 输出全部候选、阈值/距离资格和唯一 selected candidate。
- 实现 invalid-gap-safe crossing、BW/Q、固定或实测带宽积分、完整/partial energy fraction、repeat-separated drift、pairwise overlap 和 group/resonator 聚合。
- 实现 `draft`、`software_validation_only`、`approved_real_calibration`、`superseded` 类型化状态及不变量。当前模拟路径只能产生 `software_validation_only`。
- 实现稳定 CSV、typed JSON、外部 exact-file SHA-256、manifest self-hash、round-trip loader、拒绝覆盖和失败-only manifest。
- 单测量 stage gate 拆为 `P6_A=hr_calibration_scope_required`、`P6_B=not_implemented`。
- 新增 deterministic validation runner，包含三 resonators 和 CONT/REPOS/REASM 各两个重复。

## 未完成和明确非范围

- P6-B multisine readout、`hr_band_energy` FeatureSet 和快速读取未实现。
- P9 tone selection、cross-mode calibration 和分类结果驱动参数选择未实现。
- 不读取、生成或伪装真实 V2.5 HR 实验数据。
- 不解封 final-test，不冻结真实 search bands/prominence/积分/完整性阈值。
- 不生成科研结论，模拟 peak/Q/energy 恢复不代表真实装置性能。
- 不提供旧 dense artifact 的物理量自动迁移；缺失 `source_magnitude_quantity` 时要求从权威 P3 输入重新生成。

## 数据流与职责边界

```text
HRCalibrationScope + explicit input manifest + persisted dense_raw_spl FeatureSets
        + exact DatasetQCReference/Result + validated hr_calibration config
  -> path/file/content/contract/P2-B/provenance/final-test gates
  -> per-sample/per-resonator candidate detection and deterministic selection
  -> crossing/BW/Q + linear-power integration
  -> explicit energy-fraction groups
  -> calibration_group × resonator × CONT/REPOS/REASM drift
  -> measured-band pair overlap + resonator summaries
  -> typed HRCalibrationResult
  -> stable CSV/JSON/PNG/hash bundle
```

P1/P3 权威负责原始输入和 dense preprocessing；P2-A/P2-B 权威负责 measurement/dataset QC；P6-A 只验证精确引用并计算 HR 派生量，不重新实现这些阶段。

## 数学定义

### 峰与 prominence

候选必须是同一连续 `valid_mask=true` 且有限 segment 内的局部峰。标准 topographic prominence 在 search band/segment/更高峰限定的左右区间内取得左右最低基底 `b_L,b_R`：

```text
b = max(b_L, b_R)
prominence_db = peak_magnitude_db - b
```

minimum prominence 为包含等号的门槛。Hz 最小峰距采用按 prominence 降序、magnitude 降序、frequency 升序的确定性抑制；距离恰等于门槛可共存。最终固定 selection：最大 prominence，再最大 magnitude，再最低 frequency。design target 只写审计，文件名不参与。

### Half-power crossing、bandwidth 与 Q

默认配置使用精确 half-power drop：

```text
bandwidth_drop_db = 10 * log10(2) = 3.010299956639812
crossing_level_db = peak_magnitude_db - bandwidth_drop_db
```

从峰向左右寻找同一 valid segment 内最近的首次 crossing。若相邻点 `(f_1,y_1)`、`(f_2,y_2)` bracket crossing level `L`：

```text
f_cross = f_1 + (L-y_1)*(f_2-f_1)/(y_2-y_1)
bandwidth_hz = f_right - f_left
Q = f_peak / bandwidth_hz
```

任一 crossing 缺失、跨 gap、BW 非有限或非正时，BW/Q 保留为 unavailable；search boundary 不被当作 crossing。candidate search 受 search band 约束，但 crossing 可继续到其连续 valid segment 边缘，因此 measured intervals 可以真实重叠。

### Drift

drift 始终按 `(calibration_group_id,resonator_id,repeat_type)` 分开，`CONT/REPOS/REASM` 不混用。输出 mean、median、sample SD (`ddof=1`)、raw MAD、IQR、min/max 和：

```text
peak_to_peak_hz = f_max - f_min
signed_deviation_ppm_i = 1e6*(f_i-median_f)/median_f
peak_to_peak_ppm = 1e6*peak_to_peak_hz/median_f
```

少于配置的 valid peaks 时为 unavailable，不返回虚假零漂移。

### Overlap

对同一样本两个 resonator 的实测 half-power intervals：

```text
overlap_hz = max(0, min(high_i,high_j)-max(low_i,low_j))
overlap_fraction = overlap_hz/min(bandwidth_i,bandwidth_j)
```

任一 bandwidth unavailable 时 overlap unavailable，不写成零。

### 线性积分和 energy fraction

积分窗只能是 `measured_3db_band` 或围绕实测峰的 `fixed_half_width_around_measured_peak`。边界先在 dB-frequency 平面插值，再转换：

```text
power_ratio(f) = 10**(magnitude_db(f)/10)
A_i = trapezoid(power_ratio, frequency_hz)
q_i = A_i/sum(A_j)
```

每个 valid segment 独立积分，不连接 gap；coverage 是实际积分长度/请求窗口长度。低于配置门槛时 unavailable。`A_i` 单位是 relative-power-ratio·Hz，不声称为 Joule。`require_all` 缺任一 resonator 时整组 unavailable；`allow_partial` 明确列出 missing resonators，不将缺失能量填零。所有可用 `q_i` 在配置容差内求和为 1。

## Calibration 状态机

| 状态 | frozen_for_research | scientifically_eligible | 必需条件 |
|---|---:|---:|---|
| `draft` | false | false | 未批准/未完成生命周期状态 |
| `software_validation_only` | false | false | simulated + software_validation |
| `approved_real_calibration` | true | true | eligible real_experiment、research gate、canonical P2-B、calibration/training role、final-test seal、frozen thresholds、完整 hash、人工审批 |
| `superseded` | false | false | 显式 `superseded_by` |

模拟数据请求 real approval 会被明确拒绝，不能靠 requested status 突破 research hard gate。`calibration_usability=complete/partial/unavailable` 与 lifecycle/provenance 状态分开。

## Schema、配置和 API 变化

- pipeline：`2.0.0-dev.16`
- config：`2.15.0`
- measurement：`2.4.0`（不变）
- FeatureSet：`2.2.0`（不变，填充已有 source semantics 字段）
- single-measurement run manifest：`1.10.0`
- HR scope/input/result/calibration/manifest：`1.0.0`

2.14 配置只在内存中迁移为 2.15，新增 disabled、空 resonator 的安全默认块并产生 warning；不修改源 YAML。`enabled=true` 必须具有完整、互不重叠的 per-resonator search/integration 定义。当前 `config/validation_dev_c10_hr_calibration.yaml` 中的全部参数均为 synthetic/provisional，不是实测冻结阈值。

公开入口：

```python
analyze_sweep_hr_calibration(feature_sets, scope, dataset_qc_result, config)
load_explicit_hr_calibration_inputs(input_manifest_path, scope)
write_hr_calibration_outputs(result, scope, config, output_directory, ...)
load_hr_calibration_bundle(output_directory)
```

## 修改文件

核心：

- `src/acoustic_encoder/hr_analysis.py`
- `src/acoustic_encoder/hr_cli.py`
- `src/acoustic_encoder/hr_outputs.py`
- `src/acoustic_encoder/hr_validation.py`
- `src/acoustic_encoder/feature_axis.py`
- `src/acoustic_encoder/features.py`
- `src/acoustic_encoder/comparison_metrics.py`

配置/入口/版本：

- `config/default.yaml`
- `config/schema_versions.yaml`
- `config/validation_dev_c10_hr_calibration.yaml`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `scripts/run_hr_calibration.py`
- `scripts/run_hr_calibration_validation.py`

测试与文档：

- `tests/test_hr_analysis.py`
- `tests/test_hr_outputs.py`
- `tests/test_hr_cli.py`
- `tests/test_hr_validation.py`
- `tests/test_config.py`
- `tests/test_pipeline_e2e.py`
- `README.md`、`MIGRATION_V1_TO_V2.md`、`CHANGELOG.md`
- `docs/progress/INDEX.md` 和本报告

## 数据来源、provenance 和科研资格

DEV-C10 validation 由代码确定性构造 6 个 dense sweep FeatureSet：CONT、REPOS、REASM 各两个，每个含 R1/R2/R3 三个已知峰。文件名路径故意包含误导性 design-target 文本；检测仍严格恢复数值峰。

- `data_origin=simulated`
- `dataset_role=software_validation`
- `run_purpose=software_validation`
- `calibration_status=software_validation_only`
- `frozen_for_research=false`
- `scientifically_eligible=false`

没有读取真实研究数据或 external-reference REW 文件；模拟 calibration 不得用于科研结论。

## 验证命令和准确结果

- 开始前未修改基线：`pytest -q` → `477 passed in 54.39s`。
- 首个 scope/contract/peak tracer：`pytest -q tests/test_hr_analysis.py` → 从预期 import error 转为 `3 passed in 0.44s`。
- P6-A 最终专项：`pytest -q tests/test_hr_analysis.py tests/test_hr_outputs.py tests/test_hr_cli.py tests/test_hr_validation.py` → `20 passed in 1.51s`。
- P6-A CLI + validation + 旧 pipeline CLI/E2E：`pytest -q tests/test_hr_cli.py tests/test_hr_validation.py tests/test_pipeline_cli.py tests/test_pipeline_e2e.py` → `30 passed in 15.35s`。
- P3/P4/Pipeline 定向回归：`pytest -q tests/test_pipeline_e2e.py tests/test_pipeline_cli.py tests/test_features.py tests/test_feature_outputs.py tests/test_comparison_metrics.py` → `73 passed in 16.26s`。
- 最终全量：`pytest -q` → `504 passed in 55.65s`。
- `python -m compileall -q src scripts tests` → exit code 0，无输出。
- `git diff --check` → exit code 0，无输出。
- `python scripts/run_hr_calibration_validation.py --output-root outputs --run-id DEV-C10_P6A_FINAL` → exit code 0，输出 `outputs/simulated/software_validation/DEV-C10_P6A_FINAL/hr_calibration`。

运行环境的 pytest launcher 还报告一个不影响结果的 `PytestRemovedIn10Warning`：`pytest.console_main()` 将在 pytest 10 移除。

## 模拟已知值恢复

- 18 个 selected peaks 均命中已知 1 Hz 网格峰；最大 peak-frequency 误差 `0 Hz`。
- R1/R2/R3 的 CONT peak-to-peak drift 均恢复 `2 Hz`；REPOS 均为 `10 Hz`；REASM 均为 `20 Hz`。
- 每个 sample 的三 resonator fixed-window linear energy fractions 恢复为 `4/7`、`2/7`、`1/7`；最大绝对误差小于 `3e-17`，和为 1。
- 手工线性 dB 三角峰单测验证左右 crossing、`BW=2*10*3.010299956639812 Hz` 和 `Q=f_peak/BW`；pytest 断言通过。
- invalid gap、单侧 crossing 缺失、无峰、prominence 等号边界、多峰 tie-break、complete/partial energy、overlap unavailable 均有回归。

这些误差仅说明 deterministic numerical fixture 按定义恢复，不是实际测量精度。

## 生成输出

验证目录：

`outputs/simulated/software_validation/DEV-C10_P6A_FINAL/hr_calibration/`

包含：

- `peak_candidates.csv`
- `detected_peaks.csv`
- `peak_bandwidths.csv`
- `peak_drift.csv`
- `peak_overlap.csv`
- `integrated_energy.csv`
- `hr_energy_fractions.csv`
- `calibration_scope_audit.csv`
- `calibration_input_audit.csv`
- `hr_calibration.json` / `hr_calibration.sha256`
- `hr_calibration_manifest.json` / `hr_calibration_manifest.sha256`
- `peak_detection_diagnostic.png`

本次验证文件 hash：

- `hr_calibration.json`: `0ef6973f423b068a38054bbfb4963be5b15059554e941c25e62c5bbea0ac7625`
- `hr_calibration_manifest.json`: `e7d32d308ec3956cf5918b5e536534e9253e88db2906077a74aa43adba3da525`
- semantic `calibration_id`: `sha256:b0db4aa1c92b003bffa03754e989b4a3455c60672d6c507d0f3df0c401f2673a`

Manifest self-hash 由相邻 `.sha256` 文件保存，以避免递归自哈希。CSV 由 typed result 重建复核；PNG 做 exact-file hash 复核。

## 已知限制和 provisional 参数

- topographic prominence 和 search bands 尚未用真实装置噪声、峰密度或 smoothing 参数校准。
- peak frequency 当前取局部峰网格点，不做抛物线或模型拟合的 sub-bin refinement。
- search bands 在 P6-A 要求互不重叠；measured bandwidth 可越过 search band 并发生 overlap。
- fixed-window `A_i` 是 relative power-ratio·Hz，不是绝对声能；真实研究前必须冻结 SPL reference/校准链。
- 当前 diagnostic PNG 显示候选峰审计，不重绘完整原始频响，因为 P6-A result 不复制 FeatureSet 数组。
- 生命周期模型支持 real approval 门禁，但本步未产生或测试一个成功的真实批准 artifact；仅测试 simulated 无法突破门禁。
- scope 中的人工审批是类型化审计记录，不是外部身份、电子签名或审批系统。

## P6-B 进入门槛

进入 P6-B 前至少必须：

1. 获取并审计真实 V2.5 sweep calibration 数据，全部 provenance/P2-A/P2-B/human review 通过；
2. 在不接触 final-test 的 calibration/training 数据上冻结真实 search bands、prominence、bandwidth、integration 和 completeness 阈值；
3. 生成经人工审批的 `approved_real_calibration`，验证全部 source/config/preprocessing/hash 和 final-test seal；
4. 定义 multisine `hr_band_energy` 的 tone coverage、校准邻域、missing-tone、phase 和 uncertainty 规则；
5. P6-B 只能引用冻结 calibration ID/hash，不得从 multisine/final-test 反向修改 P6-A 参数；
6. P9 仍保持关闭，直到 tone selection 与 final-test 防泄漏方案独立确认。

## 对应 Git commit

本报告所在的单一提交：`feat(hr): add auditable sweep resonance calibration`。最终 commit hash 由提交完成后的 Git 输出和交付回复提供；未 push。

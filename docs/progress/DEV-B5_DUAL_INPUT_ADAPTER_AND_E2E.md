# DEV-B5：P1 multisine adapter、统一双入口调度及端到端验证

## 状态、日期和分支

- 状态：完成（DEV-B 软件验证入口闭环）
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 提交边界：本报告、实现、测试、配置、README、迁移说明和进度索引位于同一个本地提交 `feat(pipeline): close dual-input validation loop`
- 科研声明：本步没有使用 `real_experiment`，没有实现 P2–P6/P9，不能形成科研结论

## 目标与验收标准

本步把已经独立验证的 P1 REW、P7、S3 和 P8-A/B1/B2 接入一个可审计的 DEV-B 程序入口：

- P1 multisine adapter 从 WAV、sidecar、canonical stimulus manifest 和 resolved config 构造权威 sparse-tone `SpectrumData`；
- `run_pipeline.py` 按规范化的 `measurement_mode` 调用 REW 或 multisine adapter，两个入口返回相同的 `SpectrumData` 接口；
- `analyze_multisine.py` 和 `run_pipeline.py` 复用同一个 dispatcher、executor 和 P8 实现；
- 成功、QC 非 valid、manual review、research gate 和 artifact failure 都写出可复核状态，不静默配对、不伪造成功；
- multisine validation run 输出配置快照、run manifest、索引、全部 P8 CSV、序列化 spectrum 和诊断图；
- 输入只读，输出按 provenance/purpose 隔离，已有 run 目录拒绝覆盖；
- P2–P6 明确为 `not_implemented`，不假装执行。

## 完成内容

### P1 multisine adapter

公共 API：

```python
load_multisine_measurement(
    recording_wav,
    sidecar_metadata,
    stimulus_manifest,
    resolved_config,
) -> SpectrumData
```

adapter 执行以下入口检查，然后只调用现有 `analyze_multisine_measurement(...)`，不复制同步、drift、FFT、transfer 或 tone-QC 算法：

1. WAV 和 sidecar 必须存在，sidecar 必须是 JSON object；
2. `MeasurementMeta` 使用与 REW 相同的 schema；
3. 必须显式提供 `stimulus_id`、stimulus hash、tone set、sample rate、period、stable/discard count、audio channel 和 source format；
4. 从 `paths.stimuli/<stimulus_id>/stimulus_manifest.json` 定位 canonical manifest；显式路径或 sidecar pointer 不一致时拒绝；
5. 比较 sidecar、manifest 和 config 中的 stimulus/tone/sample/period 信息；
6. 验证 recording、sidecar 和 stimulus SHA-256，验证 WAV 实际 sample rate/channel；
7. `audio_channel` 必须是真正的非负整数，损坏或缺字段的 manifest 转为明确的 P1 domain error；
8. manual-review reasons 在 P8 前停止；不从 WAV 文件名推断任何 stimulus 参数；
9. 返回 `representation=sparse_tones`，不插值为 dense 物理频响；
10. `phase_status` 只采用 P8 的权威 `SpectrumData.phase_status`，CSV 仅派生该值。

### Dispatcher 和命令行流程

```text
config load + alias normalization
              |
              v
read MeasurementMeta ---- mode mismatch --> audited failure
              |
       +------+------+
       |             |
   rew_sweep   schroeder_multisine
       |             |
 load_rew       P1 multisine adapter
       |             |
 dense SpectrumData  P8 analysis + sparse SpectrumData
       +-------------+
              |
       shared run executor
              |
 isolation + hashes + artifacts + explicit P2_P6 gate
```

- `rew_sweep` 继续调用 `load_rew_measurement`；
- `schroeder_multisine` 调用 P1 multisine adapter；
- UI alias `schroeder_chirp` 只在 config load 时规范化，artifact 内只允许 `schroeder_multisine`；
- `scripts/run_pipeline.py` 是统一入口；
- `scripts/analyze_multisine.py` 是 mode-locked 薄入口；
- 旧 sweep 无输入命令仍只验证配置并以退出码 0 到达 stage gate；
- 两个 multisine 命令调用同一 `pipeline_main → execute_measurement_run → dispatch_measurement` 路径。

## 输出目录和 run manifest

成功或已解析 metadata 的失败按以下路径隔离：

```text
<output_root>/<data_origin>/<run_purpose>/<run_id>/
```

metadata 无法解析时进入：

```text
<output_root>/quarantine/<run_id>/
```

`run_id` 必须是非空单一路径分量，`.`、`..`、正反斜杠均拒绝。目录已存在时在任何覆盖前抛出 `FileExistsError`。

multisine 完整 bundle 包含：

- `config_snapshot.yaml`
- `run_manifest.json`
- `run_manifest.sha256`
- `measurements.csv`
- `transfer_tones.csv`
- `tone_quality.csv`
- `clock_drift_qc.csv`
- `measurement_qc.csv`
- `spectrum_data.npz`
- `spectrum_data.json`
- `synchronization_diagnostic.png`
- `period_consistency.png`

`run_manifest` schema `1.0.0` 记录：

| 分组 | 字段 |
|---|---|
| identity | `run_id`、created/finished UTC、processing status、success |
| versions | pipeline/config/measurement/feature quartet、run-manifest version |
| code | Git commit 和 dirty 状态 |
| mode/provenance | mode、purpose、origin、dataset role、scientific eligibility、sample ID |
| stimulus/input | stimulus ID/hash、tone set、recording/sidecar/config hash、输入路径/存在状态/SHA-256 |
| decisions | `phase_status`、measurement QC status |
| reproducibility | random state、每个生成 artifact 的相对路径和 SHA-256 |
| maturity | P1/P7/P8/P2–P6 stage gate |
| failure | category、exception type、message、manual-review reasons |

`run_manifest.sha256` 是 manifest 的外部 hash root；manifest 不尝试包含自身 hash。原始 TXT/WAV/sidecar/manifest 的 hash 和 mtime 回归证明执行过程不修改输入。

## 成功、失败与 manual-review 状态

| 条件 | processing status | success | 输出/动作 |
|---|---|---:|---|
| adapter 和 QC 均 valid | `completed` | true | 完整 bundle |
| QC warning/exclude | `completed` | false | 保留完整 spectrum/QC/artifacts，不删除 tone |
| metadata 明确 manual review | `manual_review_required` | false | import/QC failure views、input inventory、manifest；P8 不运行 |
| simulated/reference 请求 research | `blocked_research_gate` | false | 隔离的失败 bundle；无成功标记 |
| metadata 缺失/损坏 | `failed` | false | `quarantine` failure bundle |
| source/stimulus hash mismatch | `failed` | false | `integrity_mismatch`，不产生误导性 spectrum |
| tone/sample/manifest/config mismatch | `failed` | false | `artifact_mismatch`，不静默配对 |
| channel/source-format/schema 错误 | `failed` | false | `validation_error` |
| 已有目标目录 | 抛出异常 | false | 不覆盖、不修改原 bundle |

## 未完成和明确非范围

- 未实现 P2、P3 `FeatureSet`、P4 指标、P5 分类、P6 HR、P9 tone 选择；
- 未实现完整 S2 科研报告；
- 未冻结真实 multisine 的 QC threshold；
- 未开放真实 multisine P8；当前 P8 maturity gate 仍只接受 simulated software validation；
- 未分析任何项目真实测量，也未产生科学结论；
- 未把 sparse tones 插值成 dense response；
- 未把 `drift_corrected` 表示为 `common_clock`；
- 本步 run executor 是单 measurement run，不是 batch scheduler；
- 进程在文件写入中途被操作系统终止时仍可能留下不完整目录；因为目录不可覆盖，需使用新 run ID 或经人工审计后处理残留目录。

## 关键设计决策

- `SpectrumData` 是两个入口的统一权威接口；CSV 是 view；
- `MeasurementMeta` 是 provenance 和人工 valid 的权威来源，自动 QC 不翻转 `meta.valid`；
- adapter 只负责 linkage 和 dispatch，P8 保持唯一信号处理实现；
- canonical manifest 由 config root 和 sidecar 的显式 `stimulus_id` 确定，不使用长文件名；
- sidecar/manifest/config 交叉检查在 P8 前完成，WAV/hash/实际采样率由 P8 再验证；
- failure bundle 和 success bundle 使用同一个 run-manifest contract；
- `success` 与 `processing_status` 分开：QC warning/exclude 是“处理完成但验证不成功”；
- phase state 从 `SpectrumData` 单向派生到 CSV/manifest，避免第二权威状态；
- external-reference REW 和 simulated multisine 按 origin/purpose 硬隔离；research gate 独立于 parser 成功与否。

## schema、config 和 API 变化

| 项目 | DEV-B4 | DEV-B5 |
|---|---|---|
| pipeline | `2.0.0-dev.5` | `2.0.0-dev.6` |
| config schema | `2.4.0` | `2.5.0` |
| measurement schema | `2.4.0` | `2.4.0`（无字段变化） |
| feature schema | `2.0.0` | `2.0.0` |
| S3 mock schema | `1.2.0` | `1.3.0` |
| run manifest | 不存在 | `1.0.0` |

- `config/default.yaml` 新增 canonical `paths.stimuli`；
- config 2.3/measurement 2.3 和 config 2.4/measurement 2.4 均可只在内存中迁移到 config 2.5/measurement 2.4，源 YAML 不改写；
- S3 sidecar 新增/固定 `stable_period_count` 和 `discard_initial_period_count`；
- 新增 `p1_adapters.load_multisine_measurement(...)`；
- 新增 `pipeline_dispatch.dispatch_measurement(...)`；
- 新增 `run_execution.execute_measurement_run(...)` 和 `RunResult`；
- 新增共享 `pipeline_cli.pipeline_main(...)`；
- 为 mono WAV 明确拒绝非 0 channel，避免错误选择被静默接受。

## 修改文件

### 实现和配置

- `src/acoustic_encoder/p1_adapters.py`
- `src/acoustic_encoder/pipeline_dispatch.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `src/acoustic_encoder/io_multisine.py`
- `src/acoustic_encoder/mock_data.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `scripts/run_pipeline.py`
- `scripts/analyze_multisine.py`
- `config/default.yaml`
- `config/schema_versions.yaml`

### 测试和文档

- `tests/test_p1_multisine_adapter.py`
- `tests/test_pipeline_dispatch.py`
- `tests/test_pipeline_e2e.py`
- `tests/test_pipeline_cli.py`
- `tests/test_config.py`
- `tests/test_mock_data.py`
- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-B5_DUAL_INPUT_ADAPTER_AND_E2E.md`

## 数据来源、provenance 和科研资格

本步只使用两类数据：

1. S3 由 P7 stimulus 和已知 `H(f)` 生成的 multisine recording：`data_origin=simulated`、`dataset_role=software_validation`、`run_purpose=software_validation`、`eligible_for_scientific_analysis=false`；
2. REW 官方样例导出的三个 immutable TXT fixture：`data_origin=external_reference`、`dataset_role=parser_fixture`、只用于 `software_validation`、不含伪造的 device/configuration/angle/session/repeat metadata。

测试验证 simulated 和 external-reference 均不能进入 `research_analysis`，也不能伪装为可科研分析的 `real_experiment`。本步没有读取或分析任何真实研究测量。

## 测试矩阵

- clean P7→S3 delayed recording→P1→P8→serialization→isolated output；
- non-period-aligned prefix delay；
- +80 ppm correction enabled、residual 低于 warning threshold、phase 为 `drift_corrected`；
- warning 和 exclude-candidate 都完成处理但 `success=false`，完整 QC bundle 保留；
- missing sidecar、missing canonical manifest、malformed manifest；
- stimulus/recording hash mismatch；
- sidecar/config 的 tone set、sample rate、period、stable/discard count mismatch；
- invalid/null/fractional/negative audio channel；
- unsupported source format；
- stale/non-canonical manifest pointer；
- explicit manual review；
- simulated 和 external-reference research gate；
- external-reference 不能伪装为 research input；
- output directory overwrite refusal 和 run-ID traversal refusal；
- input hash/mtime 不变；
- spectrum NPZ/JSON round trip；
- run-manifest input/artifact/hash 可重算；
- official REW dispatcher 和 external-reference output partition；
- legacy sweep config-only command；
- `analyze_multisine.py` 与 `run_pipeline.py` 结果逐数组/phase/QC 一致；
- 全部 P8-A/P8-B1/P8-B2、schema、config、mock 和 REW 回归。

## 实际执行命令和准确结果

### DEV-B5 adapter/dispatcher/E2E/CLI 集合

```powershell
python -m pytest tests/test_p1_multisine_adapter.py tests/test_pipeline_dispatch.py tests/test_pipeline_e2e.py tests/test_pipeline_cli.py -q
```

准确结果：退出码 `0`，`46 passed in 19.18s`。

### REW 官方格式回归

```powershell
python -m pytest tests/test_io_rew.py -q
```

准确结果：退出码 `0`，`23 passed in 0.31s`。

### 全部 pytest

```powershell
python -m pytest -q
```

准确结果（最终提交前复验）：退出码 `0`，`169 passed in 39.74s`。

### Bytecode 编译

```powershell
python -m compileall -q src scripts tests
```

准确结果：退出码 `0`，无标准输出。

## 生成输出

端到端测试为每个用例在 pytest 临时目录中实际生成并验证完整/失败 bundle。提交后还使用同一代码路径生成本地持久化 clean smoke bundle：

```text
outputs/simulated/software_validation/DEV-B5_E2E_FINAL/
```

输入和辅助 config 位于被 `.gitignore` 排除的：

```text
data/mock/DEV-B5_E2E_FINAL/
```

持久化输出包含本报告“输出目录和 run manifest”列出的 12 个文件。该 bundle 仅为 simulated software validation，不属于 Git 提交，也不得作为科研证据。

## DEV-B 完成检查表

| 门槛 | 结果 | 证据 |
|---|---|---|
| P1 sweep 真实 REW 格式测试 | 通过 | 3 个 immutable external-reference export；`tests/test_io_rew.py` 23 passed |
| P1 multisine mock adapter | 完成 | canonical sidecar/manifest/config linkage 和 sparse `SpectrumData` tests |
| P7 deterministic stimulus | 回归通过 | 全量 stimulus tests |
| P8 delay/drift/magnitude/QC | 回归通过 | P8-A/B1/B2 和 DEV-B5 E2E tests |
| 两入口统一 `SpectrumData` | 完成 | dispatcher dense/sparse tests，shared executor |
| provenance/research gate | 生效 | simulated/reference research rejection 和 masquerade tests |
| 旧 sweep 命令/配置 | 通过 | CLI config-only compatibility test |
| 未使用真实研究数据 | 确认 | provenance 仅 simulated/external-reference |
| 可以声明科研结论 | 否 | P2–P6/P9 未实现，真实 multisine gate 未开放 |

## 已知限制和 provisional 参数

- P8-B2 thresholds 仍是 simulation-only provisional values；
- multisine adapter 虽允许 schema 表达真实 `multisine_wav`，P8 maturity gate 仍明确拒绝非 simulated 输入；
- `drift_corrected` 只表示通过当前 drift correction/QC，不表示 common clock；
- run manifest 记录 Git dirty 状态；只有提交后生成的持久化 smoke bundle 才记录 clean final commit；
- output bundle 是单 measurement；尚无 batch resume/aggregation；
- CSV `phase_status` 和 QC 是 view，使用者必须以序列化 `SpectrumData` 为权威；
- failure categorization 是入口审计类别，不替代更高层实验异常分类；
- 进程级崩溃不保证事务性回滚，残留目录受 refuse-overwrite 保护并需人工审计。

## DEV-C 下一步和进入门槛

建议下一最小切片是 DEV-C / P3 `FeatureSet` adapter，但进入前必须：

- 继续以 `SpectrumData` 为唯一 P3 输入；
- 对 dense REW 与 sparse multisine 明确不同的 feature contract，不把 sparse tones 伪造为 dense response；
- 保留 tone set、valid mask、QC reasons、phase status、measurement provenance 和 run-manifest linkage；
- 明确 P3 不修改人工 `MeasurementMeta.valid`，也不自动删除 warning/exclude tone；
- 训练/拟合相关参数只能由训练分区决定；
- 不把 simulation threshold 固化成真实实验门槛；
- P4/P5/P6/P9、真实 multisine threshold freeze 和科研结论继续使用独立门禁。

## 对应 Git commit

提交主题：`feat(pipeline): close dual-input validation loop`。本报告与本步代码、测试、配置和文档位于同一个本地提交；未执行 push。

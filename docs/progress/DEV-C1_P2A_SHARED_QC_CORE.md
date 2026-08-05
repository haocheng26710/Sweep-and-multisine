# DEV-C1 / P2-A：双入口共享的单测量 QC 核心

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 提交边界：实现、测试、配置、迁移说明、README、本报告和进度索引位于同一个本地提交 `feat(qc): add shared single-measurement QC core`
- push 状态：本步不 push

## 目标与验收标准

本步在 P1 adapter 之后、P3 之前建立一个不读取原始 TXT/WAV 的共享 P2 核心。输入是权威 `SpectrumData` 及 P1/P8 已有证据；输出是可序列化、可追溯且不与 `SpectrumData`/`MeasurementMeta` 争夺权威性的单测量 QC 结果。

验收范围包括：类型化 check/result、固定聚合状态机、双模式共用检查、REW unavailable 证据、P8 measurement/per-tone 证据映射、provenance/research gate、provisional YAML 阈值、四个统一输出、run-manifest/stage-gate 集成、拒绝覆盖和全部既有回归。

## 完成内容

1. 新增冻结的 `QCCheckResult` 和 `MeasurementQCResult`，并提供 JSON 字典 round trip。
2. 新增规范枚举：check status、scope、source stage 和 required-unavailable policy。
3. 固定自动聚合优先级 `exclude_candidate > warning > valid`；顺序不影响结果，多项原因全部保留。
4. `unavailable` 始终保留原状态；仅当该 check 为必需且 mode policy 为 `warning` 时，measurement aggregate 才升级为 warning。
5. 人工 `MeasurementMeta.valid`、人工排除原因和 manual-review reasons 与自动 QC 分离；P2 不修改它们，也不自动删除点或 tone。
6. 共用检查覆盖 schema/version、metadata/mode 字段、provenance、valid point、频率覆盖、magnitude 极值/动态范围、phase 状态/数组一致性及有效 phase 有限性。
7. REW 将缺少 headroom、noise floor、raw waveform、impulse response 和 window 的事实记录为 P1 `unavailable`，不伪造 clipping/SNR。
8. multisine 将 P8 aggregate、clipping、clock drift、non-excited energy 及每个 tone 的 SNR、leakage、period variance、missing-tone 证据转换为 P2 check；不读取 WAV、不重算 FFT。
9. P1 adapter 已报告的 `MeasurementMeta.qc_status` 被保存为 `p1.adapter.aggregate`；P8 的 per-tone reasons 保存在每条 check details 中。
10. 新增四个同源视图：`quality_control.csv`、`qc_checks.csv`、`measurement_qc.csv`、`quality_control.json`，并验证 CSV/JSON 一致性和 JSON round trip。
11. canonical multisine run 把 P8 summary 写为 `p8_measurement_qc.csv`，让 P2 独占统一的 `measurement_qc.csv`；低层 P8 writer 的默认文件名保持兼容。
12. run-manifest schema 升至 `1.1.0`，新增 `qc_schema_version=1.0.0`，成功 import 路径记录 `P2=completed`，后续门为 `P3_P6=not_implemented`。

## 明确未完成和非范围

- 跨测量同条件离群、重复稳定性和缺失实验条件矩阵（P2-B）；
- 频率插值、平滑和任何 sparse-to-dense 物理频响转换；
- P3 `FeatureSet`、P4 指标、P5 分类、P6 HR、P9 tone 选择；
- 自动删除、自动人工排除或自动翻转 `MeasurementMeta.valid`；
- 真实实验 QC 阈值冻结、真实 multisine maturity gate 和科研结论；
- P1 在无法构造 `SpectrumData` 前发生的 hard failure 仍由 run failure manifest 处理，P2 不伪造 spectrum 或成功状态。

## QC 模型和状态机

### `QCCheckResult`

| 字段 | 含义 |
|---|---|
| `check_id` | 稳定检查标识；per-tone 可重复并由频率区分 |
| `scope` | `metadata` / `measurement` / `spectrum` / `tone` |
| `status` | `valid` / `warning` / `exclude_candidate` / `unavailable` |
| `source_stage`, `source_module` | P1/P2/P8 来源与实现模块 |
| `measured_value`, `threshold`, `units` | 数值、配置门槛和单位 |
| `available`, `required`, `reason` | 可用性、必需性和可审计原因 |
| `frequency_hz` | per-tone check 的 tone 频率 |
| `details` | 方法、bin 数、P8 reasons 等结构化证据 |

### `MeasurementQCResult`

保存 sample/mode/provenance/purpose、全部 checks、unavailable policy、manual-review、人工 valid 和科研资格；以下字段全部从上述权威内容派生：aggregate、warning/exclude reasons、unavailable checks 和 downstream eligibility。

聚合真值表：

| 已有最严重自动状态 | 新 check | aggregate |
|---|---|---|
| valid | valid | valid |
| valid | warning | warning |
| valid/warning | exclude_candidate | exclude_candidate |
| 任意 | unavailable optional | 不改变 |
| valid | unavailable required + `warning` policy | warning |
| 任意 | unavailable required + `preserve` policy | 不改变 |

`exclude_candidate` 只是自动候选排除；不是人工 `valid=false`。warning 仍可进入下游；自动 exclude、manual review 或人工 invalid 会使 `eligible_for_downstream=false`。

## P1、P8 和 P2 职责边界

| 阶段 | 权威职责 | P2 行为 |
|---|---|---|
| P1 | 解析输入、构造/验证 metadata、hash、manual review、生成 `SpectrumData` | 只引用 adapter status 和 REW unavailable 证据 |
| P8 | 同步、drift、FFT/transfer、clipping、tone/off-tone QC、phase state | 只映射 `quality_metrics`；不重算信号指标 |
| P2 | 共享科学意义检查、统一聚合、统一序列化 | 不读 TXT/WAV，不修改 spectrum/meta，不建立第二 phase/valid 权威 |

## schema、config 和 API 变化

| 项目 | DEV-B5 | DEV-C1 |
|---|---|---|
| pipeline | `2.0.0-dev.6` | `2.0.0-dev.7` |
| config schema | `2.5.0` | `2.6.0` |
| measurement schema | `2.4.0` | `2.4.0`（无字段变化） |
| feature schema | `2.0.0` | `2.0.0` |
| QC schema | 不存在 | `1.0.0` |
| run manifest | `1.0.0` | `1.1.0` |

公共 API：

```python
evaluate_measurement_quality(
    spectrum: SpectrumData,
    config: Mapping[str, Any],
    *,
    run_purpose: str | RunPurpose,
    upstream_checks: Iterable[QCCheckResult] = (),
) -> MeasurementQCResult

write_quality_control_outputs(
    result: MeasurementQCResult,
    output_directory: str | Path,
) -> dict[str, Path]
```

`quality_control` YAML 为 schema `1.0.0` 且 `provisional: true`。两个 mode 均配置 minimum points、required frequency range、required-unavailable policy、phase policy、phase inconsistency status、magnitude warning/exclude bounds/dynamic range 和 required upstream check IDs。配置验证检查类型、有限性、正值、范围及 warning/exclude 顺序。

配置 2.3/2.3、2.4/2.4 和 2.5/2.4 marker 只在内存迁移到 2.6/2.4；源 YAML 不被改写。当前数值仅为 software-validation provisional 参数，不是 `real_experiment` 冻结门槛。

## 输出 schema

- `quality_control.csv`：V1 最低兼容视图，含 sample、mode、aggregate status、人工 valid 和 downstream eligibility。
- `qc_checks.csv`：long-form，一行一个 check；包含 provenance、scope/status/source、frequency、measurement、threshold、reason 和 details。
- `measurement_qc.csv`：一行一个 measurement，保存 aggregate、全部原因列表、unavailable/manual review、人工/科研/downstream 状态和 check count。
- `quality_control.json`：完整嵌套结果；载入时重新计算并核对派生字段，防止 aggregate/reason view 与 checks 不一致。

canonical multisine bundle 还保留 P8 的 `transfer_tones.csv`、`tone_quality.csv`、`clock_drift_qc.csv` 和 `p8_measurement_qc.csv`。所有 CSV 都是 view；`SpectrumData`、`MeasurementMeta` 和 typed QC result 是对应权威对象。

## 修改文件

### 核心实现、配置与入口

- `src/acoustic_encoder/quality_control.py`
- `src/acoustic_encoder/quality_control_outputs.py`
- `src/acoustic_encoder/schemas.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `src/acoustic_encoder/io_rew.py`
- `src/acoustic_encoder/multisine_outputs.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `config/default.yaml`
- `config/schema_versions.yaml`
- `scripts/run_pipeline.py`
- `scripts/analyze_multisine.py`

### 测试与文档

- `tests/test_quality_control.py`
- `tests/test_quality_control_outputs.py`
- `tests/test_config.py`
- `tests/test_io_rew.py`
- `tests/test_multisine_qc.py`
- `tests/test_pipeline_e2e.py`
- `tests/test_pipeline_cli.py`
- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-C1_P2A_SHARED_QC_CORE.md`

## 数据来源、provenance 和科研资格

实现和测试只使用：

1. 代码内构造及 S3/P7 生成的 `simulated` 数据，`dataset_role=software_validation`、`run_purpose=software_validation`、`eligible_for_scientific_analysis=false`；
2. 三个官方 REW 导出 immutable fixture，`data_origin=external_reference`、`dataset_role=parser_fixture`，只允许 `software_validation`，不伪造 angle/configuration/session/repeat metadata。

测试继续验证 simulated 在 `research_analysis` 被拒绝，external reference 不能进入 research partition。没有读取或分析任何 `real_experiment` 项目数据；本步不能形成科研结论。

## 测试矩阵

- clean REW 和 clean multisine valid；
- REW headroom/noise/waveform/IR/window unavailable；
- phase optional、required-warning、状态/数组不一致和非有限 phase；
- 频率覆盖不足、有效点不足、magnitude warning/exclude；
- warning + exclude 顺序无关聚合及多原因保留；
- required unavailable 的 preserve/warning 两种 policy；
- P1 adapter status、P8 measurement status 和 per-tone reasons 追溯；
- manual review、人工 valid=false 和自动 QC 分离；
- simulated/external-reference research hard gate；
- CSV/JSON 同源一致性、JSON round trip、派生字段复核及输出拒绝覆盖；
- config policy、有限值、正值及 warning/exclude 顺序；
- P1/P7/P8、DEV-B5 E2E、REW 和旧 CLI 全量回归。

## 实际执行命令和准确结果

### P2-A、输出和 config 专项

```powershell
python -m pytest tests/test_quality_control.py tests/test_quality_control_outputs.py tests/test_config.py -q
```

准确结果：退出码 `0`，`55 passed in 0.42s`。

### 全部 pytest

```powershell
python -m pytest -q
```

准确结果：退出码 `0`，`196 passed in 35.22s`。

### Bytecode 编译

```powershell
python -m compileall -q src scripts tests
```

准确结果：退出码 `0`，无标准输出。

## 生成输出

pytest 实际生成并核对了 clean multisine、warning、exclude、REW、manual-review 和 failure bundle；这些测试输出位于 pytest 临时目录，不作为长期科研 artifact。

提交完成后使用同一 canonical executor 生成本地持久化 software-validation smoke bundle：

```text
outputs/simulated/software_validation/DEV-C1_P2A_FINAL/
```

该目录不纳入 Git，包含 P8 artifacts、四个 P2 统一视图、序列化 `SpectrumData`、config snapshot、输入/artifact hashes 和 run manifest。其 provenance 仍为 simulated/software_validation/scientifically-ineligible。

## 已知限制和 provisional 参数

- P2 threshold 全部是模拟/格式验证用 provisional 值，未用真实实验冻结；
- REW TXT 没有原始波形、headroom、noise floor、IR/window 时只能报告 unavailable，不能推断 clipping/SNR；
- P2 只处理已经存在的 `SpectrumData`；adapter hard failure 没有伪造的 QC result；
- P8 per-tone details 复用既有字典 contract，后续若升级 P8 QC schema 必须显式迁移；
- 当前是单测量 QC，不提供跨重复、跨角度或条件矩阵判断；
- warning 可进入下游是当前明确 policy；P3 必须继续携带 QC reasons，而不是默默丢弃 warning；
- `exclude_candidate` 不是人工排除；最终排除仍需独立的人工作业和审计记录；
- run bundle 为单 measurement，进程中断不提供事务回滚，已有目录由 refuse-overwrite 保护。

## 下一步及 P3 进入门槛

建议下一切片先明确 P2-B 与 P3 的顺序。进入 P3 前至少需要：

1. `FeatureSet` 只接受 canonical `SpectrumData` 和本步 `MeasurementQCResult`；
2. dense REW 与 sparse multisine 使用显式不同的 feature contract，不把 sparse tone 插值成 dense response；
3. 保留 tone set、valid mask、phase status、全部 QC reasons、manual-review 和 provenance；
4. 明确 warning 是否允许进入 feature 计算，以及 exclude-candidate 的人工审批接口；
5. 所有拟合/归一化参数只能由训练分区决定；
6. 真实实验阈值冻结、P4/P5/P6/P9 和科研结论继续使用独立门禁。

## 对应 Git commit

提交主题：`feat(qc): add shared single-measurement QC core`。本报告与实现、测试、配置和其他文档位于同一个本地提交；未 push。

# DEV-UI3 — P2-B～P6 后端能力矩阵

## 审计结论

- 日期：2026-08-10
- 分支：`feature/v2-dual-input`
- 审计范围：P2-B、P3-C、P4、P5-A、P5-B、P6-A、P6-B 的现有正式脚本、CLI application service、scope/input schema、前置门禁和输出 bundle。
- 原则：UI 只编排已有正式入口；验证 fixture runner 不会变成真实分析按钮；UI 不复制或改变科研算法。
- 科研资格：本矩阵描述软件能力，不授予数据或结果科研资格。DEV-UI3 E2E 仅为 `simulated/software_validation/scientifically_ineligible`。

## 能力矩阵

| 阶段 | 正式入口 | 必需输入 | 显式 scope / authority | 前置 QC | 支持模式 | 权威输出 | DEV-UI3 状态 |
|---|---|---|---|---|---|---|---|
| P2-B dataset QC | `scripts/run_dataset_qc.py` / `run_dataset_quality_cli` | persisted `FeatureSet`、P2-A `MeasurementQCResult` | `DatasetQCScope`、`DatasetQCInputManifest`、预期条件矩阵 | P2-A 完成 | sweep、multisine | `dataset_qc/` bundle | 正式开放；由 UI 根据已确认计划与显式登记样本生成 scope/input 预览 |
| P3-C matched-tone | 无通用正式脚本 | dense sweep、P8 sparse tones、tone authority | paired matched-tone scope | P2-A/P8 | sweep + multisine | matched-tone `FeatureSet` | **unavailable**；仓库只有核心 API 和模拟 validation runner，UI 不包装 fixture runner |
| P4 direction/config comparison | `scripts/run_comparison_metrics.py` / `run_comparison_metrics_cli` | persisted FeatureSets、P2-B bundle | `ComparisonAnalysisScope`、`ComparisonInputManifest` | exact canonical-ready P2-B | sweep、multisine | `comparison_metrics/` | 有条件正式开放；必须选择已有显式 scope/input 和 exact P2-B authority |
| P5-A grouped classification | `scripts/run_classification.py` / `run_classification_cli` | 单模式 FeatureSets、P2-B bundle | `ClassificationScope`、`ClassificationInputManifest` | exact canonical-ready P2-B | sweep、multisine | `classification/` | 有条件正式开放；training/development 仍由正式 scope 门禁隔离 |
| P5-B cross-mode classification | `scripts/run_cross_mode_classification.py` / `run_cross_mode_classification_cli` | P3-C matched FeatureSets、P2-B、P4-B | `CrossModeClassificationScope`、input manifest | canonical-ready P2-B + verified P4-B | sweep + multisine | `cross_mode_classification/` | 仅当预先存在合格 P3-C/P4-B authority 时开放；真实 Multisine 依赖路径 blocked |
| P6-A sweep HR calibration | `scripts/run_hr_calibration.py` / `hr_cli.main` | dense raw sweep FeatureSets、P2-B | `HRCalibrationScope`、`HRCalibrationInputManifest` | canonical-ready P2-B | sweep only | `hr_calibration/` | 有条件正式开放；仅 sweep，参数仍 provisional |
| P6-B multisine HR readout | `scripts/run_hr_readout.py` / `hr_readout_cli.main` | P3-C multisine FeatureSets、exact P6-A authority、P2-B | `HRReadoutScope`、`HRReadoutInputManifest` | canonical-ready P2-B + exact P6-A authority | multisine only | `hr_readout/` | 仅模拟/已有合格 authority 可用；真实 Multisine/P8 及其 FeatureSet 路径 blocked |

## UI 调用与前置检查

`BatchWorkflowService` 是薄 application-service 层。它只完成以下工作：

1. 接收用户明确选择的计划 revision、UI2 session/output、scope、input manifest、config 和 authority 目录；
2. 在读取正式输入前阻止 `final_test_sealed/final_test`；
3. 检查 exact P2-B reference、数据来源分区、必要 P3-C/P4-B/P6-A authority 和真实 Multisine 门禁；
4. 将 program 与 arguments 分开交给 `QProcess`；
5. 保存 UI scope/input snapshot、hash、技术日志和步骤报告；
6. 保留正式 backend bundle 为结果权威。

它不读取原始 WAV/TXT，不重算 P1～P9，不将 validation runner 当作正式入口，也不从目录或文件名推断样本。

## 不适用、不可用与失败

- `not_applicable`：模式不匹配，例如 sweep-only 计划中的 P6-B；不是失败。
- `unavailable`：仓库没有通用正式入口或缺少必须 authority，例如 P3-C；不是成功，也不会生成成功标记。
- `blocked`：违反 final-test、P2-B、provenance 或真实 Multisine 硬门禁；必须人工处理。
- `failed`：正式进程已经启动但以失败退出，技术日志与步骤报告保留。
- `warning/cancelled`：不提升为成功；保留已生成证据和原始 QC。

## final-test 与真实 Multisine

`final_test_sealed` 行只显示密封状态，不显示配置、角度、session、repeat、FeatureSet 或标签。若用户误选，`SampleRegistry` 在读取 manifest 内容前写入 `final_test_incidents.jsonl`，记录 `content_read=false`、`scope_valid=false`、`manual_review_required=true`，并停止当前 scope。

真实 Multisine 可以沿用 DEV-UI2 的只读登记，但 P8 和所有依赖新 P8 FeatureSet 的 P5-B/P6-B 路径保持硬阻塞。DEV-C16 ready 和 DEV-UI3 能力表都不代表真实 Multisine 已获准分析。

## 验证

实际运行的正式入口受控回归：

```text
python -m pytest tests/test_comparison_metrics_cli.py tests/test_classification_validation.py tests/test_cross_mode_classification_cli.py tests/test_hr_cli.py tests/test_hr_readout_cli.py -q
......... [100%]
9 passed in 7.22s
```

实际运行的泄漏/模式门禁：

```text
python -m pytest tests/test_ui3_sample_registry.py::test_final_test_binding_is_blocked_before_manifest_content_is_read tests/test_ui3_sample_registry.py::test_real_multisine_registration_remains_blocked tests/test_ui3_batch_workflow.py::test_formal_stage_blocks_final_test_before_input_manifest_read_and_real_multisine -q
... [100%]
3 passed in 0.22s
```

上述结果验证入口和门禁，不是科研结果，也不证明真实设备性能。

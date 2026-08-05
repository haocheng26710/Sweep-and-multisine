# DEV-C8 / P5-A — 防数据泄漏的分组方向分类核心

## 状态、日期和分支

- 状态：完成（software-validation 实现切片）
- 日期：2026-08-06
- 分支：`feature/v2-dual-input`
- 提交边界：本报告、实现、测试、配置和迁移说明位于同一提交，标题为 `feat(classification): add leakage-safe grouped classification core`

## 目标与验收标准

P5-A 只接收持久化 `FeatureSet`、显式 `ClassificationScope`、显式输入 manifest、匹配的 P2-B result/hash 和 resolved config。它不读取 TXT/WAV/`SpectrumData`，不扫描目录，不重跑 P1/P3/P8，也不复用 P4 全数据方向模板。验收要求是：单一 measurement mode 内执行 LOSO/LORO/LOAO 分组验证；每折仅用训练样本确定 mask、变换和模型；封存 `final_test`；保留 unavailable；输出可复核的预测、指标、折分和 hash manifest。

## 完成内容

- 新增 schema-1.0 `ClassificationScope`、成员、FeatureSet 内容引用和稳定 SHA-256；成员顺序必须与显式 artifact 顺序完全一致。
- 新增 `leave_one_session_out`、`leave_one_reposition_round_out`、`leave_one_assembly_out`。LORO 只使用 REPOS，LOAO 只使用 REASM；少于两个可用组时返回 `unavailable`，不伪造折。
- `final_test` 保存在 scope/audit 中，但不会进入任何训练或测试折；P2-B cohort role 必须逐样本一致。
- 每个 fold/band 的 feature mask 是 band mask 与全部训练样本 `valid_mask` 的交集。测试样本缺少该固定 mask 中任一特征时，该预测为 `test_missing_fold_feature`；不缩 mask、不填零、不插值。
- 实现三个固定基线：训练类均值的 Pearson nearest-template、训练折 `StandardScaler` 后的 Euclidean nearest-centroid、训练折 `StandardScaler` 后固定 `lbfgs/C=1/class_weight=balanced/max_iter=1000` logistic regression。无 PCA、无调参、无从 final_test 选择模型/频带。
- 输出 fold accuracy、balanced accuracy、prediction coverage，聚合 mean/median/sample-std/min/max，per-class precision/recall/F1/support、confusion matrix 和 difficult-direction pairs。未定义项保持 unavailable/空值。
- 对 scope、NPZ/JSON、FeatureSet 内容、P2-B result、P2-A link、provenance 和全部输出执行 SHA-256 门禁；输出目录存在时拒绝覆盖；失败路径只写失败 manifest，不写成功标志。
- pipeline/config/run-manifest 版本更新，并将单测量阶段门拆为 `P5_A=classification_scope_required`、`P5_B=not_implemented`、`P6=not_implemented`。

## 明确未完成和非范围

- 不实现跨 measurement-mode 训练、sweep/multisine calibration 或 bias correction。
- 不实现随机森林、PCA、超参数搜索、nested model selection、部署模型或 final-test evaluation/release ceremony。
- 不实现 P5-B、P6、P9、tone reliability/selection，也不修改 P4 数学定义。
- 不冻结真实实验频带、阈值或模型，不生成科研结论。

## 分类数据流与泄漏控制

```text
explicit ClassificationScope + explicit input manifest
        + matching P2-B result/hash + resolved classification config
                              |
                identity / contract / provenance gates
                              |
                  exactly one measurement_mode
                              |
       final_test sealed; protocol-specific grouped folds
                              |
  training-only band mask -> scaler/template/model -> fixed-mask test
                              |
 predictions + fold/per-class/aggregate metrics + audit/hash manifest
```

LOSO 的 group key 为 `session_id`；LORO 为 REPOS 的 `(session_id, reposition_round_id)`；LOAO 为 REASM 的 `(session_id, assembly_id)`。训练/测试 ID 集必须不相交，训练折必须含至少两个方向并覆盖 scope 的方向集合。方向得分相等时只按 scope 中预先声明的 `direction_order_deg` 破同分，不读取测试标签。

## 修改文件

- 核心与入口：`src/acoustic_encoder/classification.py`、`classification_cli.py`、`classification_outputs.py`、`classification_validation.py`
- 配置/版本/阶段门：`config/default.yaml`、`config/schema_versions.yaml`、`config/validation_dev_c8_classification.yaml`、`src/acoustic_encoder/config.py`、`version.py`、`run_execution.py`、`pipeline_cli.py`
- mock 验证扩展：`src/acoustic_encoder/dataset_quality_validation.py`
- 脚本：`scripts/run_classification.py`、`scripts/run_classification_validation.py`
- 测试：`tests/test_classification.py`、`test_classification_outputs.py`、`test_classification_validation.py`，以及版本/阶段门回归测试
- 文档：本报告、`docs/progress/INDEX.md`、`README.md`、`MIGRATION_V1_TO_V2.md`、`CHANGELOG.md`

## Schema、配置和 API 变化

- pipeline `2.0.0-dev.14`；config schema `2.13.0`；measurement `2.4.0`、FeatureSet `2.2.0` 不变。
- 单测量 run-manifest 从 1.7 升至 1.8；classification scope/input/result/manifest 均为 1.0。
- `classification` YAML 固定 `frequency_bands`、三个 protocols、三个 models、`minimum_training_features`、`minimum_training_samples_per_direction`、`minimum_prediction_coverage`、`standardization: training_fold_only`、`pca: disabled`、`final_test_policy: sealed`。所有参数仍为 provisional。
- 旧 `classification.validation` 仅通过显式内存迁移成为 `classification.protocols`，生成 warning，源 YAML 不重写；额外含糊字段拒绝。
- 公开核心 API：`analyze_classification_feature_sets(features, scope, config, dataset_qc_result=...) -> ClassificationResult`。

## 数据来源、provenance 和科研资格

形式验证使用 `generate_directional_feature_set_mock` 产生的模拟 dense sweep 和 sparse-tone multisine `FeatureSet`，分别建立独立 P2-B canonical-ready software-validation cohort。两种模式不混合训练。两次运行均为：

- `data_origin=simulated`
- `run_purpose=software_validation`
- `canonical_analysis=true`（只表示软件层 P2-B/scope 门禁完整）
- `scientifically_eligible=false`

没有使用 `real_experiment`，没有读取用户真实测量，不能形成科研结论。`research_analysis` 仍通过 provenance hard gate，仅允许明确合格的 `real_experiment`。

## 验证命令及准确结果

- `pytest -q tests/test_classification.py tests/test_classification_outputs.py tests/test_classification_validation.py tests/test_config.py tests/test_pipeline_e2e.py tests/test_pipeline_cli.py` → `152 passed in 21.35s`。
- `pytest -q` → `453 passed in 48.59s`（最终提交前全量回归）。
- `python -m compileall -q src scripts tests` → exit code `0`，无输出。
- `$env:PYTHONPATH='src'; python scripts/run_classification_validation.py` → sweep 和 multisine 两个 P2-B bundle 均 `aggregate_status=valid`、`canonical_ready=true`；两个 classification bundle 均 `processing_status=completed`、`success=true`、`scientifically_eligible=false`。随后脚本增加与仓库其他入口一致的 `src/` bootstrap；`python scripts/run_classification_validation.py --help` 验证直接入口可加载。

## 生成输出

- `outputs/simulated/software_validation/DEV-C8-P5A-FINAL-SWEEP/classification/`
- `outputs/simulated/software_validation/DEV-C8-P5A-FINAL-MULTISINE/classification/`

每个目录均含 18 条 fold metric（3 protocols × 2 folds × 3 models）、480 条预测和 12 个受 manifest 管理的结果 artifacts：

- `split_audit.csv`、`fold_assignments.csv`、`predictions.csv`
- `fold_metrics.csv`、`aggregate_metrics.csv`、`per_class_metrics.csv`
- `confusion_matrix.csv`、`difficult_direction_pairs.csv`
- `feature_mask_audit.csv`、`training_transform_audit.csv`、`model_parameters.csv`
- `classification_result.json`

此外各目录含 `classification_manifest.json` 及其 self-hash；manifest 本身不计入它管理的 12 个结果 artifact。

## 已知限制和 provisional 参数

- 形式验证的 1–1.2 kHz band、最少 5 个训练特征和 100% prediction coverage 是模拟软件测试参数，不是实验冻结值。
- nearest-template 对常数模板/测试向量不可用；logistic/centroid 只支持完整固定 fold mask；这是显式失败策略。
- 当前结果提供交叉验证审计，不提供可部署模型文件，也不执行封存 final_test 的最终一次性评估。
- mock dense/tone 两条验证路径使用同一已知方向函数，不能证明真实设备跨入口等价。

## 下一步及进入门槛

下一步不得以本模拟准确率选择频带、阈值或模型。进入 P5-B/P6/P9 前至少需要：真实实验 provenance/metadata 合格；P2-B scope/hash 与条件完整性通过；训练/development/final_test 分区在采集前冻结；P5-A 配置和 band 选择不引用 final_test；人工审核记录完成；真实阈值冻结形成独立审计提交。

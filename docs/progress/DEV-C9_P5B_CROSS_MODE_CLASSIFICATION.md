# DEV-C9 / P5-B — 严格防泄漏的四协议跨模式分类验证

## 状态、日期和分支

- 状态：完成（software-validation 实现切片）
- 日期：2026-08-06
- 分支：`feature/v2-dual-input`
- 提交边界：本报告、实现、测试、配置、版本和迁移说明位于同一提交，标题为 `feat(classification): add leakage-safe cross-mode validation`

## 目标与验收标准

P5-B 只接收已持久化的 P3-C matched-tone `FeatureSet`、显式 `CrossModeClassificationScope`、显式 FeatureSet input manifest、精确 P2-B result/reference、精确 P4-B result/reference 和已验证配置。它不读取 TXT/WAV/`SpectrumData`，不扫描目录，不重跑 P3/P8，不按文件名猜配对，也不使用 P4 全数据模板。

验收目标是以同一组预先冻结的 outer groups 执行四个协议：

1. `sweep_to_sweep`；
2. `multisine_to_multisine`；
3. `sweep_to_multisine`；
4. `sweep_plus_multisine_to_multisine`。

所有 fold 内 mask、标准化和模型拟合仅使用训练样本；held-out physical state 的两个 mode 均不得进入训练；`final_test` 只进入审计而不进入交叉验证；P4-B bias 不得应用；模拟输出必须保持 scientifically ineligible。

## 完成内容

- 新增 schema-1.0 `CrossModeClassificationScope`，显式记录 FeatureSet 内容 hash、双 mode preprocessing ID、tone set/schema、normalization、方向顺序、配置、cross-mode group、outer folds、P2-B/P4-B references、band/model 和 random state。
- `cross_mode_group_id` 是不可拆分的 physical-state 原子。一个 artifact 只能属于一个 group，一个 `physical_state_id` 不能跨 group；scope 不从文件名、目录或时间戳推断配对。
- 四协议共享同一 `OuterFoldSpec`。LOSO 必须完整 hold out 一个 session；LORO 仅适用于 REPOS 的 `(session_id, reposition_round_id)`；LOAO 仅适用于 REASM 的 `(session_id, assembly_id)`。
- 复用 P5-A 暴露的 `predict_direction_fold(...)`，没有复制第二套 nearest-template、nearest-centroid 或 logistic 实现。nearest-centroid/logistic 的 `StandardScaler`、模板、质心和 logistic 参数全部在每个 training fold 内拟合。
- training mask 定义为预设 band mask 与全部训练 FeatureSet `valid_mask` 的交集。测试样本缺失任一固定 tone 时该 prediction 为 `test_missing_training_mask_tone`；不缩小 mask、不填零、不插值、不外推。
- 实现显式 mixed-mode training composition：默认 `sample_pooled`、uniform sample weighting、logistic balanced class weighting；按 fold/mode/direction/group 记录样本数。
- 实现兼容性状态：同 mode、absolute compatible、shape compatible、correlation shape-only、absolute/shape incompatible。P4-B bias 仅审计，`p4b_bias_applied=false`；`calibration_fitted=false`。
- 输出 fold accuracy、balanced accuracy、macro precision/recall/F1、prediction coverage、top/second candidate、score/margin、per-class 指标、confusion matrix 和 difficult-direction pairs。
- transfer gap 只在相同 outer fold、相同 multisine test artifacts、相同 band/model/contract 下比较 `sweep_to_multisine` 或 mixed protocol 与 `multisine_to_multisine`；否则保留 unavailable reason。
- 显式 CLI 校验 scope/input/P2-B/P4-B/NPZ/JSON hash，并按 `data_origin/run_purpose/run_id` 隔离写出；已存在输出目录拒绝覆盖；失败路径仅写失败 manifest。
- 单测量 run-manifest 的 P5-B 门禁改为 `cross_mode_classification_scope_required`，并未在单测量 pipeline 中伪装执行 P5-B。

## 未完成和明确非范围

- 不解封或评估 `final_test`，不生成 deployment model。
- 不做 PCA、随机森林、超参数搜索、nested model selection、自动 band/model 选择。
- 不做 sweep-to-multisine affine calibration，不应用 P4-B global/per-tone bias。
- 不做 tone selection、P9 bridge/快速读取、P6 HR。
- 不冻结真实实验 band、阈值、模型或 calibration，不生成科研显著性或真实性能结论。

## 数据流与职责边界

```text
persisted P3-C sweep projection + persisted P3-C multisine tone measurement
                         + explicit input manifest
                         + exact P2-B result/hash
                         + exact P4-B result/hash
                         + CrossModeClassificationScope
                                      |
                 identity / provenance / matched-tone / role gates
                                      |
                    frozen physical-state outer groups
                                      |
      training-only mask -> shared P5-A predictor -> fixed-mask test
                                      |
 predictions + fold/per-class/confusion/gap/audit CSV + typed JSON + hashes
```

- P3-C 权威负责 tone identity/order/schema 和 normalization；P5-B 不重排或重建 tones。
- P2-B 权威负责 dataset scope、cohort role、canonical readiness 和 provenance；P5-B 只验证精确引用。
- P4-B 权威负责跨 mode absolute/shape compatibility evidence 和 bias 审计；P5-B 不重算 P4 指标，也不应用 bias。
- P5-A 权威负责三个固定 predictor、tie-break 和 training-fold-only transformation；P5-B 只定义跨 mode fold/composition/compatibility。
- P9 未来可消费审计结果进行预先批准的 tone workflow，但不得把本步 transfer gap 反向用于 tone/model 选择。

## 防泄漏规则

- outer test groups 在 scope 中预先声明，四协议不根据结果改 fold。
- 对任一 held-out `cross_mode_group_id`，对应 sweep、multisine 和同 group 的所有 artifacts 都不得进入任何协议的训练集合。
- `cross_validation_role` 每次只能是 `development` 或 `training`；P2-B cohort role 必须逐 artifact 一致。
- `final_test` artifacts 记录在 `sealed_final_test_artifact_ids`，不进入 training、CV test、compatibility fitting、mask、normalization、calibration、模型或参数选择。
- test `valid_mask` 不参与训练 mask；测试缺 tone 只使该 prediction unavailable。
- mixed training 不按 test 表现调整 mode 权重；默认策略固定并写入配置和输出。

## FeatureSet 与兼容性规则

两个入口必须具有相同 `feature_names` 及顺序、units、tone-set ID/hash、tone-schema ID、normalization 和 feature count。sweep 必须为 `tone_projection_from_sweep`，multisine 必须为 `tone_measurement_from_multisine`；每个 mode 具有 scope 固定的 preprocessing ID。禁止 dense/sparse 直接混用、重排、不匹配 tone 插值、填零或扩展为 dense response。

- `subtract_mean_db`、`zscore_spectrum` 仅在配置明示且 P4-B shape comparison available 时允许 shape transfer。
- raw absolute contract 仅在 P4-B absolute comparison available 时允许 centroid/logistic。
- raw absolute 不兼容但 shape available 时，仅 Pearson nearest-template 可标记 `correlation_shape_only`；centroid/logistic 为 unavailable。
- P4-B bias 与 calibration state 只影响兼容性审计；数值永不用于变换 FeatureSet。

## Schema、配置和 API 变化

- pipeline：`2.0.0-dev.15`
- config schema：`2.14.0`
- measurement schema：`2.4.0`（不变）
- FeatureSet schema：`2.2.0`（不变）
- single-measurement run-manifest：`1.9.0`
- P5-B scope/input/result/manifest：`1.0.0`

`classification.cross_mode` 固定字段：

- 四个 `transfer_protocols`；
- `allowed_shape_normalizations: [subtract_mean_db, zscore_spectrum]`；
- `pooling_policy: sample_pooled`；
- `sample_weighting: uniform`；
- `class_weighting: balanced`；
- `p4b_bias_policy: audit_only`；
- `calibration_policy: disabled`。

配置 2.13 可在内存中迁移到 2.14，产生 warning 且不重写源 YAML。公开入口为：

```python
analyze_cross_mode_classification(
    artifacts,
    scope,
    config,
    dataset_qc_result=...,
    comparison_bundle=...,
) -> CrossModeClassificationResult
```

## 修改文件

- 核心：`src/acoustic_encoder/cross_mode_classification.py`
- P5-A 共享 predictor：`src/acoustic_encoder/classification.py`
- CLI/输出：`src/acoustic_encoder/cross_mode_classification_cli.py`、`cross_mode_classification_outputs.py`
- 脚本：`scripts/run_cross_mode_classification.py`
- 配置/版本/阶段门：`src/acoustic_encoder/config.py`、`version.py`、`run_execution.py`、`pipeline_cli.py`、`config/default.yaml`、`schema_versions.yaml`、`validation_dev_c8_classification.yaml`、`validation_dev_c9_cross_mode_classification.yaml`
- 测试：`tests/test_cross_mode_classification.py`、`test_cross_mode_classification_outputs.py`、`test_cross_mode_classification_cli.py`，以及配置和 pipeline E2E 回归
- 文档：本报告、`docs/progress/INDEX.md`、`README.md`、`MIGRATION_V1_TO_V2.md`、`CHANGELOG.md`

## 数据来源、provenance 和科研资格

DEV-C9 使用 `generate_directional_feature_set_mock` 生成四个方向、两个 session、严格 matched-tone 的 sweep/multisine FeatureSet。核心测试另覆盖 REPOS/LORO、REASM/LOAO、raw absolute-incompatible、shape-compatible、测试 tone 缺失、同 physical-state 泄漏陷阱、不平衡 mixed training 组成和封存 final_test。

- `data_origin=simulated`
- `run_purpose=software_validation`
- `canonical_analysis=true` 仅表示软件层 scope/P2-B/P4-B 门禁完整
- `scientifically_eligible=false`

没有读取真实实验数据，没有解封 final_test。模拟 accuracy 和 transfer gap 只验证软件行为，不能代表真实跨入口性能或支持科研结论。

## 验证命令和准确结果

- 开始前基线：`pytest -q` → `453 passed in 54.14s`。
- TDD scope/fold 起始切片：`pytest -q tests/test_cross_mode_classification.py` → 从预期 import failure 转为 `2 passed in 0.88s`。
- 输出/核心中间回归：`pytest -q tests/test_cross_mode_classification_outputs.py tests/test_cross_mode_classification.py` → `6 passed in 2.37s`。
- 首次实现后全量回归：`pytest -q` → `466 passed in 48.74s`。
- 四方向 P5-B 专项：`pytest -q tests/test_cross_mode_classification.py tests/test_cross_mode_classification_outputs.py tests/test_cross_mode_classification_cli.py` → `19 passed in 1.70s`。
- 固定验证产物：`pytest -q tests/test_cross_mode_classification_cli.py --basetemp=outputs/simulated/software_validation/DEV-C9_P5B_FINAL4_VALIDATION` → `1 passed in 1.18s`。
- P5-A/P5-B、CLI/E2E、配置和 pipeline 专项：`pytest -q tests/test_cross_mode_classification.py tests/test_cross_mode_classification_outputs.py tests/test_cross_mode_classification_cli.py tests/test_classification.py tests/test_classification_outputs.py tests/test_classification_validation.py tests/test_config.py tests/test_pipeline_e2e.py tests/test_pipeline_cli.py` → `176 passed in 23.17s`。
- 最终全量：`pytest -q` → `477 passed in 54.29s`。
- `python -m compileall -q src scripts tests` → exit code `0`，无输出。
- `git diff --check` → exit code `0`，无输出。

## 生成输出

四方向 E2E bundle：

`outputs/simulated/software_validation/DEV-C9_P5B_FINAL4_VALIDATION/test_cross_mode_cli_runs_from_0/outputs/simulated/software_validation/DEV-C9-cli/cross_mode_classification/`

该 bundle 为 `processing_status=completed`、`success=true`、`scientifically_eligible=false`，包含 8 个可用 fold metrics（4 protocols × 2 LOSO folds）、64 条 predictions、4 条 transfer gaps；四协议模拟 accuracy/balanced accuracy 均为 1.0。此已知结果仅验证确定性 mock 行为。

输出文件：

- `protocol_scope_audit.csv`、`cross_mode_group_audit.csv`、`fold_assignments.csv`
- `training_composition.csv`、`compatibility_audit.csv`
- `cross_mode_predictions.csv`、`protocol_fold_metrics.csv`、`protocol_summary.csv`
- `transfer_gap.csv`、`per_class_metrics.csv`、`confusion_matrices.csv`、`difficult_direction_pairs.csv`
- `feature_mask_audit.csv`、`training_transform_audit.csv`
- `classification_result.json`、`classification_manifest.json`、`classification_manifest.sha256`

manifest 管理 15 个结果 artifacts，并记录 68 个显式输入 artifacts/references；loader 已验证 artifact hashes 和 typed result round-trip。

## 已知限制与 provisional 参数

- 1.0–1.1 kHz、minimum 5 tones 和 100% prediction coverage 是模拟验证参数，不是冻结的真实实验阈值。
- 当前 mixed training 只支持 sample-pooled/uniform sample weighting；没有 equal-mode weighting model ID。
- cross-mode compatibility 依赖 P4-B 已声明的 reference/shape evidence；本步不解决真实设备校准。
- transfer gap 只提供匹配 fold/test cohort 的描述性差值，不做置信区间、显著性或模型选择。
- 输出没有可部署模型；logistic/centroid scaler 不持久化为 deployment artifact。
- `canonical_analysis=true` 不等于 scientifically eligible；模拟数据硬门禁保持 false。

## 对应 Git commit

本报告与代码使用单一提交：`feat(classification): add leakage-safe cross-mode validation`。最终 commit hash 在提交完成后的交付回复中报告。

## 下一步及进入门槛

DEV-C9 后仍不得自动进入 P6/P9 或 final-test evaluation。下一步至少需要：

- 真实实验 acquisition plan、training/development/final_test 和 physical-state groups 在采集前冻结；
- real-experiment provenance/metadata/P2-A/P2-B 全部通过，人工审核完成；
- P3-C tone identity 与真实 calibration/reference contract 审计通过；
- P4-B absolute/shape compatibility 和真实阈值形成独立冻结提交；
- band/model/tone 选择不得引用 final_test 或本步 mock 的最好结果；
- 如进入 P9，必须保持 tone selection 与本步 prediction/transfer-gap 结果的防泄漏边界。

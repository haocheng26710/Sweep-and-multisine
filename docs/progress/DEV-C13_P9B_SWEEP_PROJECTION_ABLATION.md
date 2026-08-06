# DEV-C13 / P9-B — Sweep projection ablation

## 状态、日期与分支

- 状态：完成（本地实现与验证；仅 `software_validation_candidate`）
- 日期：2026-08-06
- 分支：`feature/v2-dual-input`
- 计划提交：`feat(bridge): evaluate selected-tone projection fidelity`
- 数据资格：`simulated / software_validation / scientifically_eligible=false / deployment_eligible=false / canonical_analysis=false`

## 目标与验收标准

验证 fold-specific P9-A 选出的 sweep tone projection 嵌套前缀能否保留既有 P4 指标和 P5-A 同模式分类能力，并仅用 outer-training 内 grouped inner CV 选择最小 tone 数。outer held-out group 只在决策后评估一次；final-test 始终封存。

验收要求包括：精确绑定 P9-A outer fold/training membership/CandidateToneUniverse/P2-B/P4-B/FeatureSet/manifest hash；拒绝 global selection；复用 P3-C、P4-A/P4-B、P5-A；只生成 P9-A selection-rank 的 prefix；输出 typed schema、CSV/JSON/FeatureSet 与 SHA-256；不读取 TXT/WAV、multisine、P6 或 final-test。

## 完成范围

- 新增 `P9ProjectionAblationScope`、fold/inner-fold、selection authority、tone subset、derived FeatureSet、P4 preservation、P5 stability、inner evaluation、minimum decision、outer evaluation 和总结果 typed objects。
- P9-A authority 校验 outer fold、有序 training IDs、training hash、held states、candidate universe、P2-B、P4-B（允许明确 `None`）、selected artifact 和 manifest hash。global/development selection 不能进入 outer-fold ablation。
- subset sizes 由 resolved config 预注册；每个子集严格为 `selection_rank` prefix。特征列按 P3-C source tone index 排序，不枚举替代组合；spacing/band quota 失败为 `policy_ineligible`。
- 派生 FeatureSet 仅切取已有 `tone_projection_from_sweep` 列，不重做插值、smoothing 或 projection。记录 source/derived content+contract hash、candidate IDs、selection/subset hash 和 provenance；源数组保持只读。
- P4 直接调用 `analyze_direction_feature_sets` 和 `compute_tone_reliability`，报告 effective rank、morphology gain、direction correlation/RMS、REPOS repeatability/reliability、absolute delta、ratio、retention 和 unavailable reason。
- P5 直接调用 `predict_direction_fold`；共享 `summarize_direction_predictions` 固定 label order。broad/sparse 使用同一 fold、样本、标签和 training-only valid mask。
- 最小 tone 决策只读取 inner validation 聚合，使用配置化 P4 retention、balanced-accuracy drop、macro-F1 drop、coverage、有效 fold 数和 policy eligibility。outer test 不进入决策。
- CLI 只读取显式 scope/input manifest 列出的 P3-C FeatureSet 与 fold-specific P9-A bundle；不扫描目录，输出目录存在即拒绝覆盖。
- pipeline/config/run-manifest 更新为 `2.0.0-dev.19 / 2.18.0 / 1.13.0`；measurement/FeatureSet 保持 `2.4.0 / 2.3.0`。旧 2.17 配置仅内存迁移且 P9-B disabled。

## 明确非范围

- 不读取/重解析 REW TXT、WAV、SpectrumData；不重做 P1、P3、P4 或 P5 算法。
- 不做 multisine、cross-mode calibration/transfer、P6 HR、P9-C/P9-D 或部署模型。
- 不读取 final-test，不用 outer-test/P4/P5/P6 结果修改 P9-A score、weight、ranking 或阈值。
- 不冻结真实实验阈值，不引入真实研究数据，不生成科研结论。

## 数据流与状态机

1. 显式加载 hash-verified P3-C sweep FeatureSet、CandidateToneUniverse 和每个 outer fold 的 P9-A bundle。
2. P9-A authority 与 outer-training 不完全一致即 hard fail。
3. 按 frozen rank 构造预注册 prefix；spacing/quota 不合格为 `policy_ineligible`。
4. 仅对 outer-training 做 grouped inner CV，比较 broad universe 与 sparse prefix 的 P4/P5。
5. frozen thresholds 选择最小合格 prefix；inner evidence 不足为 `unavailable`，不能回退 outer test。
6. 完整 outer-training 拟合分类器，outer held-out 仅评估一次。
7. 状态固定为 `valid / warning / unavailable / policy_ineligible / excluded`；原因全部保留。

## 配置、schema 与 API

`tone_projection_ablation` schema 1.0 为 disabled-by-default provisional 配置，固定输入 kind/mode、subset sizes、rank prefix、outer/inner protocol、inner group/fold 下限、P5 model/features/coverage、P4 retention/denominator、决策阈值、spacing/quota requirement、`final_test_policy=sealed` 与 `cross_mode=disabled`。

```text
analyze_projection_ablation(
  features, scope, universe, fold_specific_authorities, frozen_config,
  direction_metrics_config, reliability_config, band_quotas
) -> P9ProjectionAblationResult
```

P4 retention：相等（denominator floor 内）为 1；higher-is-better 为 `clip(sparse/max(|broad|,floor),0,1)`；lower-is-better 为 `clip(broad/max(|sparse|,floor),0,1)`；absolute-fidelity 为 `max(0,1-|sparse-broad|/max(|broad|,floor))`。absolute delta 始终单独报告。

## 修改文件

- 核心：`projection_ablation.py`、`classification.py`
- I/O：`projection_ablation_cli.py`、`projection_ablation_outputs.py`
- 验证：`projection_ablation_validation.py`、两个 run scripts、DEV-C13 validation YAML
- 配置/版本：`config.py`、`version.py`、`run_execution.py`、default/schema/DEV-C12 YAML
- 测试：projection-ablation core/output/E2E 与 classification/config/pipeline regression
- 文档：本报告、INDEX、README、CHANGELOG、MIGRATION

## 数据来源、provenance 与科研资格

持久化 E2E 使用确定性模拟 sweep tone FeatureSet：3 sessions × 4 directions × CONT/REPOS repeats。每个 outer fold 的 P9-A 只读取另外两个 sessions。final-test 只有 ID/hash seal，没有加载 final-test FeatureSet。

全部输出固定为 `simulated / software_validation / software_validation`，并且 `scientifically_eligible=false`、`deployment_eligible=false`、`canonical_analysis=false`。最小 tone 决策 lifecycle 为 `software_validation_candidate`，不能视为真实实验或部署批准。

## 输出与结果

验证目录：`outputs/simulated/software_validation/dev-c13-p9b-validation-20260806-v2/projection_ablation/`

输出包含 `ablation_scope.json`、`fold_selection_references.csv`、`tone_subset_definitions.csv`、`derived_feature_index.csv`、派生 FeatureSet NPZ/JSON/derivation、`p4_metric_preservation.csv`、`inner_classification_metrics.csv`、`minimum_tone_decisions.csv`、`outer_fold_predictions.csv`、`outer_fold_metrics.csv`、`projection_fidelity_summary.json`、`ablation_manifest.json/.sha256`。

三个 outer folds (`outer-S1/S2/S3`) 均仅根据 inner validation 选择 3 tones；所有 `[3,4,5,6,8]` prefix 通过 frozen validation policy。outer test broad 与 3-tone sparse 的 balanced accuracy 和 macro F1 都为 1.0，drop 0，coverage 1.0，每 fold 16 predictions。outer-test P4 最低 retention 为 `0.9285727399492533`；全部 231 个 available P4 rows 最低/平均 retention 为 `0.928572739949253 / 0.997972679260752`。改善项的 clipped retention 仍配套 absolute delta，不能只看 retention。

manifest file SHA-256：`ed8ffe7c3a8b70542cfcb6f75bde6b8dcee73cbc534594657b53157e9f51c637`；semantic hash：`sha256:85370c6030f2afbc07e38719befa8adb6c0e38c05b1ea8b4c9dd3d1d81d12375`；result hash：`sha256:9fe6cdf1f1d212e2fb9064eb6c5dd935d2337c7934a09feb228eee30cf4893bd`。loader 已重算 manifest、全部 artifact 与派生 FeatureSet file/content/contract hash；每个 fold 还记录 ordered P3-C training content aggregate hash。manifest 如实记录验证时 HEAD `91187468e3da043adf8bc201442815d17bbbe760`、`git_dirty=true`（提交前验证）。

## 实际验证命令与准确结果

- `pytest -q tests/test_projection_ablation.py tests/test_projection_ablation_outputs.py tests/test_projection_ablation_validation.py tests/test_tone_selection.py tests/test_tone_selection_cli.py tests/test_tone_selection_outputs.py tests/test_tone_selection_validation.py tests/test_metrics.py tests/test_comparison_metrics.py tests/test_classification.py tests/test_config.py tests/test_pipeline_e2e.py`：最终复跑 `282 passed in 46.82s`。
- `pytest -q`：最终全量 `612 passed in 106.52s (0:01:46)`。
- `python scripts/run_projection_ablation_validation.py --project-root . --config config/validation_dev_c13_p9b.yaml --output-root outputs --run-id dev-c13-p9b-validation-20260806-v2`：成功；3 outer folds；均选 3 tones；2172 files；artifact hashes verified；final-test sealed；scientific/deployment eligibility false。
- `$env:PYTHONPATH='src'; python -c "...load_projection_ablation_bundle(...)..."`：bundle 复核打印 semantic/result hashes `sha256:85370c6030f2afbc07e38719befa8adb6c0e38c05b1ea8b4c9dd3d1d81d12375` / `sha256:9fe6cdf1f1d212e2fb9064eb6c5dd935d2337c7934a09feb228eee30cf4893bd`。
- `python -m compileall -q src scripts tests`：通过，exit code 0，无错误输出。
- `git diff --check`：通过，exit code 0，无输出。

开发中的失败测试是 TDD red 证据，不被冒充为成功验证；本报告只将实际成功命令声明为通过。

## 已知限制

- 这是低噪声模拟 fixture；classification=1.0 不代表真实泛化。
- 仅 3 sessions、4 directions、单一 sweep configuration；阈值均 provisional。
- 3 tones 只适用于此模拟 scope，不是跨数据集/真实实验/部署结论。
- P4 改善项 retention 截断为 1，必须与 absolute delta/ratio 联读。
- 不含 cross-mode/multisine bias、真实仪器噪声、P6 HR 或真实 final-test。

## 下一步及进入门槛

P9-C 前必须具备明确授权的 calibration/training scope、canonical-ready P2-B、冻结且独立批准的跨模式校准协议、持续 final-test seal、精确 P3-C/P4/P5/P9-A/P9-B hashes，以及明确适用范围/残差/不确定度。不得把本模拟 3-tone candidate 直接升级为真实或部署配置。

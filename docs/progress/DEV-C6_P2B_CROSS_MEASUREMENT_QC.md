# DEV-C6 / P2-B：跨测量 QC、重复稳定性与实验条件完整性门禁

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 单一提交边界：P2-B 类型化核心、显式 scope/输入 CLI、输出 bundle、P4 canonical 门禁、配置/迁移、测试、README、本报告和索引位于同一提交 `feat(qc): add cross-measurement dataset quality gate`
- push 状态：本步只创建本地提交，不 push

## 目标和验收标准

本步在 P2-A 单测量 QC 之上建立 dataset/cohort 级质量门禁。P2-B 只接收显式列出的 `FeatureSet` 与其对应 `MeasurementQCResult`，不读取 TXT/WAV、不重做 P1/P8，也不把 P4 描述性指标当作 QC。验收要求是：预期条件必须由 scope 先验声明；development/training/final_test 角色可审计且 final_test 不参与阈值/参考中心；同条件离群和 CONT/REPOS/REASM 稳定性具有固定数学定义；全部异常、unavailable、人工状态和 hash 保留；canonical cohort P4 必须精确引用可用的 P2-B 结果。

## 完成范围

1. 新增 `DatasetQCScope` schema 1.0：逐项列出 sample ID、cohort role、选择理由、目标 condition ID、完整预期条件矩阵和独立人工审核记录，并以 canonical JSON 计算 scope SHA-256。
2. 新增显式 input-manifest schema 1.0：逐项列出 FeatureSet NPZ/JSON 与 P2-A JSON 路径、文件 SHA-256、P2-A result hash；不扫描目录，不补入未列出的测量。
3. 新增 `DatasetQCResult` 及 condition completeness、same-condition outlier、repeatability pair/group、measurement rollup、input audit 类型化对象；全部可 JSON round-trip。
4. 预期条件固定包含 cohort role、measurement mode、configuration、direction ID/angle、session、repeat type、reposition round、assembly、acquisition block 和 expected count；缺失、重复、意外测量分别计数并给出 reason code。
5. 同条件离群只比较 feature contract 完全相同的对象；sweep 与 multisine、不同 grid/tone schema/preprocessing identity 不会混入同一统计中心。不兼容 contract 按配置成为 `exclude_candidate`，证据不足保留 `unavailable`。
6. development 以 development 为参考且对当前样本 leave-one-out；training 仅引用 development；final_test 仅引用 training。配置验证禁止把 final_test 设置为任何角色的参考，防止最终测试泄漏。
7. CONT、REPOS、REASM 使用不同配对约束、不同 group key 和独立阈值；缺一种重复时不以其他类型替代。pair ID、样本 ID、共同有效特征数、距离、状态和失败原因完整保存。
8. measurement rollup 合并 P2-A 与 P2-B 证据，优先级固定为 `exclude_candidate > warning > valid`。`unavailable` 保留，并按 provisional 配置升级 aggregate warning；不会删除数据、改变 `MeasurementMeta.valid` 或把候选排除变成人工排除。
9. 新增不可覆盖的稳定排序 CSV/JSON bundle、manifest 自 hash、输入/输出 SHA-256 复核与 round-trip loader。输入 hash 失败时仅写失败 manifest，不写成功结果。
10. P4-A 数学实现不变；`AnalysisScope` schema 1.1 增加 `analysis_tier` 与 P2-B reference。`canonical_cohort` 必须匹配 scope ID、result hash、有序 sample IDs、FeatureSet content hash、P2-A hash及 canonical-ready 状态；旧 schema 1.0 只作为 provisional software-validation 路径。
11. 单测量 pipeline 只声明 `P2_A=completed`、`P2_B=dataset_scope_required`、`P4_A=p2_b_dataset_qc_required`；P4-B/P5/P6/P9 继续为关闭的阶段门。

## 明确未完成和非范围

- 不修改 P4-A 的方向模板、距离、repeat summary、effective rank 或 morphology gain 数学定义；
- 不实现 P4-B、跨入口 bias/calibration、tone reliability 或 P9 tone selection；
- 不实现 P5 分类、P6 HR、真实实验阈值冻结或科研报告；
- 不重新读取原始 TXT/WAV，不重跑 P8，不把 sparse tone 插值成 dense；
- 不自动删除测量、不自动修改人工 valid、不自动批准 `exclude_candidate`；
- 不以当前目录内容反推预期条件，也不生成真实实验完整性的虚假声明。

## 数据流与职责边界

```text
explicit DatasetQCScope + explicit input manifest
                         |
FeatureSet artifacts ----+---- P2-A MeasurementQCResult artifacts
                         |
             file/result/contract/provenance gates
                         |
       expected-condition completeness + robust outlier + repeatability
                         |
                  typed DatasetQCResult
                         |
      stable CSV/JSON bundle + hash-audited manifest
                         |
canonical P4 only with exact DatasetQCReference and canonical_ready=true
```

P1/P8 是原始输入和 multisine 质量证据的权威；P2-A 是单测量 QC 的权威；P2-B 只聚合 P2-A、FeatureSet contract 和跨测量证据；P4 只消费 FeatureSet 和已验证的 P2-B reference。`MeasurementMeta.valid`、P8 `phase_status`、P2-A 状态及 P2-B 状态各自只有一个权威来源。

## Scope、条件矩阵和状态机

每个 scope member 显式给出 `sample_id`、`cohort_role`、`expected_condition_id` 和 `selection_reason`。每个 expected condition 的全部字段都必须出现，包括允许为 null 的 reposition/assembly/block 字段。输入 sample 的集合和顺序必须与 scope 完全一致；重复/遗漏 ID、未知 condition、scope mismatch 或来源不一致均明确失败。

条件匹配比较 MeasurementMeta 中实际存在的 mode、configuration、angle、session、repeat/reposition/assembly/block 字段以及 scope cohort role；角度只使用配置化容差。`direction_id` 是 scope 中的显式实验设计标签，当前 MeasurementMeta 没有同名字段，因此以 angle 做数据侧一致性验证而不从文件名猜 ID。对每个 condition：

```text
missing_count   = max(expected_count - observed_count, 0)
duplicate_count = max(observed_count - expected_count, 0)
unexpected      = scope member 未指向预期 condition，或其 metadata 与预期字段不一致
```

默认 missing/duplicate/unexpected 均为 `exclude_candidate`。聚合真值顺序固定为：

| 证据集合 | 自动 aggregate |
|---|---|
| 任一 `exclude_candidate` | `exclude_candidate` |
| 否则任一 `warning` | `warning` |
| 否则只有 `valid` | `valid` |
| required check 为 `unavailable` | 值仍保留；当前 provisional policy 将 aggregate 升为 `warning` |

`exclude_candidate` 不是人工最终排除。pending/decided manual review 及 reviewer、时间、decision、notes 是独立审计记录。人工 `valid=false` 原样保留，并阻止该测量的 downstream eligibility。

## 同条件离群数学定义和防泄漏

对目标向量 `x` 和角色映射后、contract 相同的参考向量 `r_i`，先在共同有效特征集合 `J` 上取逐坐标中位数：

```text
c[j]       = median_i r_i[j]
d_i        = sqrt(mean_{j in J} (r_i[j] - c[j])^2)
d_x        = sqrt(mean_{j in J} (x[j]   - c[j])^2)
d_center   = median_i d_i
scale      = max(1.4826 * median_i |d_i - d_center|, minimum_scale)
robust_z   = (d_x - d_center) / scale
```

边界使用包含比较：`robust_z >= 6.0` 为 exclude candidate，`robust_z >= 3.5` 为 warning，否则 valid。至少需要 3 个参考样本、5 个共同有效特征且有效比例至少 0.8；不足时是 `unavailable`，不返回虚假距离或 0。feature contract hash 覆盖 feature schema/kind/names/order/units、入口 representation、preprocessing ID、tone identity/schema、normalization 和 magnitude semantics。

development 对自身 role 计算时排除被测样本；training 使用 development 参考；final_test 使用 training 参考。任何 `reference_role_by_evaluation_role` 指向 final_test 的配置都会被拒绝，因此 final_test 不参与中心、scale 或阈值选择。

## 重复稳定性定义

合格 pair 在共同有效特征 `J` 上计算：

```text
rms(x, y) = sqrt(mean_{j in J} (x[j] - y[j])^2)
```

- CONT：相同 role/mode/configuration/direction/session/repeat type/acquisition block；repeat ID 不同；reposition/assembly 两侧必须同时缺失或相同。
- REPOS：相同 role/mode/configuration/direction/session/repeat type/assembly；不同且非空 reposition round 和 repeat ID。
- REASM：相同 role/mode/configuration/direction/session/repeat type；不同且非空 assembly 和 repeat ID。

每组记录 sample count、candidate/qualified pair count、median/mean/sample std/IQR/min/max，以及每个 pair 的状态和 reason。至少需要 1 个合格 pair、5 个共同有效特征且有效比例至少 0.8。阈值按 `FeatureKind` 和 CONT/REPOS/REASM 分开，边界使用 `distance >= threshold`。缺少 ID、contract 不兼容、共同有效特征不足或 pair 不足为 unavailable；不借用其他 repeat type。

## Canonical P4 下游门禁

`AnalysisTier.PROVISIONAL_SOFTWARE_VALIDATION` 保留既有 P4-A 单元与模拟验证。`AnalysisTier.CANONICAL_COHORT` 必须传入 `DatasetQCReference(analysis_scope_id, dataset_qc_result_sha256)` 和实际 `DatasetQCResult`，并验证：scope ID、hash、有序 sample IDs、run purpose、input audit、FeatureSet content SHA-256、P2-A result SHA-256 及 `canonical_ready` 全部一致。

canonical-ready 会因条件矩阵不完整、配置不允许的 aggregate、required unavailable、pending manual review、人工 invalid 或 measurement downstream-ineligible 而失败。缺少 P2-B、scope mismatch 或 hash mismatch 都明确抛错，不能标记 canonical 成功。P4-A 核心仍保持 FeatureSet-only，且本步没有修改其数学公式。

## 配置、schema、API 与迁移

| 项目 | DEV-C5 | DEV-C6 |
|---|---:|---:|
| pipeline | `2.0.0-dev.11` | `2.0.0-dev.12` |
| config schema | `2.10.0` | `2.11.0` |
| measurement schema | `2.4.0` | 不变 |
| feature schema | `2.2.0` | 不变 |
| single-run manifest | `1.5.0` | `1.6.0` |
| DatasetQCScope/Input/Result/manifest | 不存在 | `1.0.0` |
| AnalysisScope | `1.0.0` | `1.1.0`；1.0 仅 provisional |
| metrics manifest | `1.0.0` | `1.1.0` |

配置新增 strict `dataset_quality_control` block，包含 condition statuses、direction tolerance、outlier method/role mapping/样本与特征门槛/robust-z 阈值、按 FeatureKind 和 repeat type 的 RMS 阈值，以及 unavailable/canonical/manual-review 聚合策略。所有默认值均标记 `provisional: true`；config 2.10 + measurement 2.4 + feature 2.2 只在内存中迁移到 2.11并产生 warning，不回写旧 YAML。字段集合、枚举、数值有限性、正值/比例范围和 warning < exclude 顺序均验证。

主要 API：

```python
evaluate_dataset_quality(feature_sets, measurement_qc_results, scope, config) -> DatasetQCResult
write_dataset_quality_outputs(result, scope, config, output_dir, ...) -> Path
load_dataset_quality_outputs(output_dir) -> DatasetQCResult
analyze_direction_feature_sets(..., dataset_qc_result=...)  # canonical tier only
```

## 统一输出和可复现性

每个成功 bundle 包含：

- `dataset_qc_summary.csv`
- `condition_completeness.csv`
- `same_condition_outliers.csv`
- `repeatability_qc.csv`
- `measurement_qc_rollup.csv`
- `manual_review_queue.csv`
- `dataset_qc.json`
- `dataset_qc_manifest.json`
- `dataset_qc_manifest.sha256`

CSV 稳定排序，JSON 使用固定字段和 canonical result hash。loader 先核对 manifest self-hash、全部 artifact hash 和 typed JSON round-trip，再从 JSON 重生成所有 CSV 并逐字节比对。manifest 记录 schema/config/version quartet、Git commit、random state、UTC 时间、scope/config/result hash、provenance、每个显式输入和输出 hash。目标目录已存在时拒绝覆盖。原 FeatureSet、P2-A JSON 和 scope/manifest 均只读。

## 修改文件

核心实现：

- `src/acoustic_encoder/dataset_quality_control.py`
- `src/acoustic_encoder/dataset_quality_outputs.py`
- `src/acoustic_encoder/dataset_quality_cli.py`
- `src/acoustic_encoder/dataset_quality_validation.py`
- `src/acoustic_encoder/quality_control.py`
- `src/acoustic_encoder/features.py`
- `src/acoustic_encoder/tone_features.py`
- `src/acoustic_encoder/metrics.py`
- `src/acoustic_encoder/metrics_outputs.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `src/acoustic_encoder/version.py`
- `scripts/run_dataset_qc.py`
- `scripts/run_dataset_qc_validation.py`

配置：

- `config/default.yaml`
- `config/schema_versions.yaml`
- `config/validation_dev_c5_direction_metrics.yaml`
- `config/validation_dev_c6_dataset_qc.yaml`

测试：

- `tests/test_dataset_quality_control.py`
- `tests/test_dataset_quality_outputs.py`
- `tests/test_dataset_quality_cli.py`
- `tests/test_dataset_quality_e2e.py`
- `tests/test_quality_control.py`
- `tests/test_config.py`
- `tests/test_metrics.py`
- `tests/test_metrics_outputs.py`
- `tests/test_pipeline_cli.py`
- `tests/test_pipeline_e2e.py`

文档：

- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `CHANGELOG.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-C6_P2B_CROSS_MEASUREMENT_QC.md`

`schemas.py` 未修改：MeasurementMeta、SpectrumData 和 FeatureSet schema 保持既有权威定义。

## 数据来源、provenance 和科研资格

所有新单元测试均使用 synthetic arrays 或 deterministic S3 FeatureSet mock。最终 DEV-C6 验证使用 32 个模拟 dense raw-SPL FeatureSet、24 个显式 expected conditions，覆盖 2 个 configuration、4 个方向、2 个 session，以及严格分离的 CONT/REPOS/REASM。没有读取或处理真实研究 TXT/WAV，也没有用 external reference 校准阈值。

固定 provenance：

- `data_origin=simulated`
- `dataset_role=software_validation`
- `run_purpose=software_validation`
- `scientifically_eligible=false`
- `scientific_use=prohibited_simulated_software_validation`

research gate 对 simulated `research_analysis` 和 external-reference 冒充 real experiment 的拒绝继续自动测试。DEV-C6 输出只证明软件门禁和审计路径，不构成实验完整性证明、设备性能结论或科研结论。

## 测试优先过程与实际验证

首次加入 canonical P2-A result hash 测试时得到预期 import 红灯；实现单一 hash 函数并让 dense/tone FeatureSet 共用后，相关测试变绿。P2-B 的 condition、outlier、repeatability、scope/role、round-trip 和 P4 canonical gate 均先以 focused tests 固定行为，再实现最小逻辑。成功 CLI 测试随后扩展为输入 artifact hash 被篡改的失败路径测试，确认只保存失败 manifest。

最终专项回归：

```powershell
python -m pytest -q tests/test_dataset_quality_control.py tests/test_dataset_quality_outputs.py tests/test_dataset_quality_cli.py tests/test_dataset_quality_e2e.py tests/test_quality_control.py tests/test_config.py tests/test_metrics.py tests/test_metrics_outputs.py tests/test_pipeline_cli.py tests/test_pipeline_e2e.py
```

准确结果：退出码 `0`；`185 passed in 22.32s`。

全量回归：

```powershell
python -m pytest -q
```

准确结果：退出码 `0`；`387 passed in 58.34s`。

编译检查与空白错误检查：

```powershell
python -m compileall -q src scripts tests
git diff --check
```

准确结果：两条命令退出码均为 `0`，均无标准输出。

## 最终模拟验证输出

命令：

```powershell
python scripts/run_dataset_qc_validation.py --config config/validation_dev_c6_dataset_qc.yaml --output-root outputs --run-id DEV-C6_P2B_FINAL --feature-count 71
```

验证目录：

```text
outputs/simulated/software_validation/DEV-C6_P2B_FINAL/dataset_qc/
```

已执行验证得到：32 measurements、24 expected conditions、32 outlier checks、16 repeatability groups；所有 condition completeness 为 valid（missing/duplicate/unexpected 均为 0）；16/16 候选 repeat pairs 合格且 16 组均 valid。result hash 为 `sha256:90013109f63382e8a7c495f2d78130f0c526e791c95f135131a3155d192bf269`，scope hash 为 `sha256:56ae7c9d4d59dafe0caa095fcc3751f02ed95d2b9fa21153fe1569927d81c0c1`。7 个权威 artifact hash 与 manifest self-hash 均已独立复核且无 mismatch。

该模拟设计的每个同条件 reference group 小于 provisional `minimum_reference_samples=3`，因此 outlier evidence 是诚实的 unavailable；按 policy 聚合为 warning，`canonical_ready=false`，唯一 gate reason 为 `required_dataset_check_unavailable`。这不是失败的条件矩阵，也没有被伪装成 canonical 成功。

## 已知限制和 provisional 参数

- 默认 3/5/0.8 样本与特征门槛、MAD factor 1.4826、robust-z 3.5/6.0、RMS repeatability 阈值均只用于 software validation，尚未由真实实验冻结。
- 离群方法是全局 FeatureSet RMS，不做 frequency-band/tone-specific 可靠性加权；不同 feature contract 直接隔离。
- 条件矩阵目前要求 caller 准确声明 direction ID 和 angle；MeasurementMeta 只有 angle，没有 direction ID，因此 ID 作为 scope 审计标签、angle 作为数据侧门禁。不提供文件名猜测、同义 ID 或近似 session 自动归并。
- repeat group 的样本标准差在只有一个合格 pair 时为 null/unavailable 数值，但 group 状态仍可由该 pair 判定。
- manual review 只保存审计记录，不包含用户身份系统、电子签名或外部审批工作流。
- 当前最终模拟验证故意没有足够的同条件 reference 样本，故不能作为 canonical cohort 门禁成功样例。

## 下一步及进入门槛

P2-B 完成后仍不得直接实施未定义的科研分析。进入 canonical P4/P4-B 前必须提供预注册或批准的真实 dataset scope、显式条件矩阵、独立 development/training/final_test 角色、足够的同条件参考样本、冻结的真实实验阈值，以及所有 `real_experiment` 输入的 provenance/research eligibility；P2-B result 必须 `canonical_ready=true` 且 P4 scope/hash 完全一致。

进入 P5/P6/P9 前还需分别固定 train-fold 内处理、防泄漏标准化/字典、HR schema、tone reliability/selection 规则和 final-test 隔离。P4-B/P5/P6/P9 在此提交中继续为 `not_implemented`，没有科研结论资格。

## 对应 Git commit

提交主题：`feat(qc): add cross-measurement dataset quality gate`。本报告与实现、配置、测试、迁移和索引位于同一个本地提交；未 push。最终 commit hash 由提交完成后的 Git 输出和最终回复给出。

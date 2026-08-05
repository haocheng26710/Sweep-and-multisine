# DEV-C5 / P4-A：FeatureSet-only 方向指标核心

## 状态、日期和分支

- 状态：完成
- 日期：2026-08-05
- 分支：`feature/v2-dual-input`
- 单一提交边界：实现、配置、迁移、测试、验证输出定义、README、本报告和进度索引位于同一提交 `feat(metrics): add FeatureSet-only direction metrics`
- push 状态：本步只创建本地提交，不 push

## 目标和验收标准

本步建立只消费既有 `FeatureSet` 的 P4-A 核心。调用者必须显式给出 analysis scope；核心按单一 configuration、feature kind 和 preprocessing identity 构造描述性方向模板，计算五种方向矩阵、CONT/REPOS/REASM 重复性、between-direction sample-pair 距离、morphology gain 和 effective rank，并写出可复核的数值与选择审计。P4-A 不读 TXT/WAV/`SpectrumData`，不执行 P1/P2/P3/P8，不训练分类器，也不选择 tone。

验收边界包括：不兼容身份明确失败；selection/QC 策略显式；所有指标只用共同有效特征；固定方向顺序；未定义相关/相似度保留 unavailable；pair 不自配、不重复、不猜分组 ID；G 不用 CONT/REASM 替代 REPOS；全部输入和输出可由 SHA-256 复核；模拟数据永远不具科研资格。

## 完成范围

1. 新增类型化 `AnalysisScope`、`FrozenPartition`、`SelectionPolicy`、`QCInclusionPolicy`、选择审计、方向模板、矩阵、pair、repeat summary、effective-rank、G 和汇总结果对象。
2. 入口 `analyze_direction_feature_sets(feature_sets, analysis_scope, metrics_config)` 只接受 `FeatureSet`；传入 `SpectrumData` 或其他对象立即失败。
3. 严格验证 configuration、feature kind、preprocessing ID、feature schema、names/order、units、source representation、data origin、dataset role；tone 特征还验证 tone-set ID/hash、tone schema 和 normalization。dense、sweep-tone projection 与 multisine-tone measurement 的 feature-kind/representation 组合固定，HR 特征仍在非范围。
4. 显式 sample ID 或 hash-frozen partition 是仅有的选择入口；未请求、人工无效、manual review、缺失 QC、策略未包含的 QC 状态均写入 selection audit。默认验证策略包含 `valid` 与 `warning`，不包含 `exclude_candidate`；P2 warning/exclude/unavailable 原因也原样内嵌，内容哈希覆盖这些原因与 downstream eligibility。
5. 计算全体入选样本 `valid_mask` 的逻辑交集；记录共同有效数量、比例、索引、名称和每样本 missing count。低于 YAML 门槛时结果为 failed；不填 0/均值/插值且不修改原 mask。
6. 按 scope 固定角度顺序生成方向均值、样本标准差、每特征有效计数和 session/repeat/reposition/assembly/acquisition-block 计数。方向缺失为 warning；方向只有一个样本时标准差 unavailable。
7. 生成 Pearson、cosine、Euclidean、RMS、median absolute difference 五个对称长表矩阵，保留原始数值、availability、原因和 feature count。
8. CONT、REPOS、REASM 使用不同且可审计的 pair 规则；输出候选 pair、构造状态、不可用原因、元数据和三种距离，并分别汇总 pair count、median、mean、样本 std、IQR、minimum、maximum。
9. between-direction 的所有无序 sample pairs 单独输出，不与 centroid/template 矩阵混淆。G 使用该 sample-pair 集合，记录 numerator、denominator、pair counts、metric 和最小分母。
10. effective rank 使用方向模板矩阵和 singular values 直接计算；默认不中心化，配置可显式启用列中心化；输出全部 singular values、比例、矩阵 shape 与状态。
11. 方向模板固定为 `descriptive_only`，`eligible_for_training_dictionary=false`、`tone_selection_allowed=false`；test scope 也不能改变该规则。
12. 扩展 S3 FeatureSet mock：四方向、多 CONT、两个 REPOS round、两个 assembly、多个 session/block；可控制 repeat noise、缺方向/缺 REPOS、directional/rank-one/orthogonal/identical/zero 模式，以及 dense 或 tone FeatureSet 的 missing feature/tone。
13. 新增不可覆盖的结构化输出 writer、受控 validation runner 和 CLI；单测量 canonical run manifest 1.5 显式给出 `P4_A=analysis_scope_required`，而不是假装 P4-A 自动发现 scope。

## 明确未完成和非范围

- cross-mode bias/correlation、cross-mode morphology gain；
- tone reliability weighting 和 P9 tone selection；
- frequency-band discrimination；
- U4ENC/U4SYM 总结比较；
- P4-B、P5 classification、P6 HR；
- 训练 fold 内的分类字典重建；
- 统计显著性检验；
- Matplotlib 热图/奇异值图（本步 CSV 是权威数值输出；可选图留给独立报告层）；
- 真实实验阈值冻结、真实研究数据处理或科研结论。

## Analysis scope 与 selection/QC policy

`AnalysisScope` schema 1.0 包含：`analysis_scope_id`、`run_purpose`、`scope_role`、固定 `direction_order_deg`、selection policy、QC inclusion policy，以及二选一的 `included_sample_ids` 或 `FrozenPartition(partition_id, sample_ids, partition_sha256)`。partition hash 对 canonical JSON 中的 partition ID 和有序 sample IDs 计算；不匹配即拒绝，也不会扫描目录补入其他样本。

selection policy 当前显式控制 `require_human_valid` 与 `exclude_manual_review`。QC policy 记录 policy ID、允许的规范 `QCStatus`、缺失状态处理和是否明确允许 `exclude_candidate`。缺失 QC 当前只能配置为 exclude；只有 `allow_exclude_candidate=true` 且状态列表包含它时才可纳入。warning 是否纳入完全由状态列表决定。所有提供的 FeatureSet（包括未请求者）都有 audit row；人工 `valid=false` 不进入默认指标，但其 human state 和 manual-review 原因保留。

`run_purpose=research_analysis` 仍调用既有 research hard gate，只有逐样本满足 `data_origin=real_experiment` 且 scientifically eligible 才可能继续。development/test/descriptive 等 scope role 不绕过 provenance gate。

## 共同有效特征与方向字典

对入选样本 `s=1..N` 和特征 `j=1..p`：

```text
common_valid[j] = AND_s valid_mask_s[j]
```

后续所有数值指标仅在 `J={j | common_valid[j]}` 上计算。对方向 `d` 的样本集合 `S_d`：

```text
mu_d[j] = mean_{s in S_d}(x_s[j])
sd_d[j] = sqrt(sum_{s in S_d}(x_s[j]-mu_d[j])^2 / (|S_d|-1))
```

`sd_d` 仅在 `|S_d|>=2` 时 available。模板顺序严格等于 scope 的 `direction_order_deg`；未列入 scope 的意外角度明确失败，列入但无样本的角度产生 warning。

## 距离和相似度定义

设共同有效特征数为 `m=|J|`，两个方向模板向量为 `x,y`：

```text
Pearson(x,y) = dot(x-mean(x), y-mean(y)) /
               (||x-mean(x)||_2 ||y-mean(y)||_2)
cosine(x,y)  = dot(x,y) / (||x||_2 ||y||_2)
Euclidean    = sqrt(sum_j (x_j-y_j)^2)
RMS          = sqrt((1/m) sum_j (x_j-y_j)^2)
MAD          = median_j |x_j-y_j|
```

constant vector 使 Pearson unavailable；零范数使 cosine unavailable。此时保存 `NaN` 与结构化原因，不转为 0。距离对角线为 0；定义良好的 Pearson/cosine 自相似为 1；所有矩阵对称并记录 `m`。

## Repeat pair、between pair 与 morphology gain

所有 pair 先按 sample ID 字典序规范化，限定 `left_id < right_id`，无 self pair、无重复计数：

- CONT：同 angle/type/session/acquisition block，不同 repeat ID；assembly/reposition ID 若两侧存在则必须一致，若均缺失则不猜测。
- REPOS：同 angle/type/session/assembly，不同且非空 reposition-round ID，不同 repeat ID。
- REASM：同 angle/type/session，不同且非空 assembly ID，不同 repeat ID。

缺少 required ID 或不满足关系的候选仍保留为 `constructed=false` 和明确原因。CONT、REPOS、REASM 各自汇总，不合并成一个 within-distance。

between-direction sample pairs 是全部 `angle_left != angle_right` 的入选无序样本对；centroid/template distances 则是方向均值矩阵，两者分别输出。对配置距离 `d`：

```text
G = median(d(x_i,x_j) for all constructed between-direction sample pairs)
    / median(d(x_i,x_j) for constructed within-direction REPOS pairs)
```

没有 REPOS、没有 between pair、或 REPOS median 小于配置 `minimum_denominator` 时 G unavailable；不使用 CONT/REASM 代替，不输出误导性无穷大。

## Effective rank

矩阵 `D in R^(n_directions x n_common_features)` 的每行是一个方向均值。默认直接对 `D` 做 SVD；只有 `center_direction_matrix=true` 时才先按列减去方向均值。设奇异值为 `sigma_i`：

```text
p_i = sigma_i / sum_i sigma_i
effective_rank = exp(-sum_{i:p_i>0} p_i log(p_i))
```

没有使用平方奇异值或 PCA explained variance。全零奇异值时 unavailable；输出完整 `sigma_i`、`p_i`、shape 和 centered 标志。

## 配置、schema、API 与阶段门变化

版本变化：

| 项目 | DEV-C4 | DEV-C5 |
|---|---:|---:|
| pipeline | `2.0.0-dev.10` | `2.0.0-dev.11` |
| config schema | `2.9.0` | `2.10.0` |
| measurement schema | `2.4.0` | 不变 |
| feature schema | `2.2.0` | 不变 |
| canonical run manifest | `1.4.0` | `1.5.0` |
| analysis scope | 不存在 | `1.0.0` |
| metrics manifest | 不存在 | `1.0.0` |

核心 YAML（全部 provisional）：

```yaml
direction_metrics:
  schema_version: 1.0.0
  provisional: true
  minimum_common_valid_features: 5
  minimum_common_valid_fraction: 0.8
  minimum_direction_count: 2
  center_direction_matrix: false
  repeatability_distance_metric: rms
  morphology_gain:
    distance_metric: rms
    minimum_denominator: 1.0e-12
```

字段集合、类型、有限值、正值、比例范围和距离枚举均严格验证。DEV-C4 config 2.9 可原样保留显式 smoothing/matched-tone 定义并在内存中迁移到 2.10；源 YAML 不回写。canonical 单测量 run 的成功阶段门变为 `P4_A=analysis_scope_required`、`P4_B=not_implemented`、`P5_P6=not_implemented`；失败路径为 `P4_A=not_run`。

## 输出 schema

最终目录 `metrics/` 包含：

- `direction_statistics.csv`：每方向 sample IDs/count、std availability、五类分组计数和共同有效统计；
- `direction_templates.csv`：每方向×每特征的 name/unit/common-valid/mean/std/valid count；
- 五个矩阵 CSV：长表 row/column direction index/angle、value、available、reason、feature count；
- `repeatability_pairs.csv` 与 `between_direction_pairs.csv`：pair identity/scope/metadata、构造状态/原因和三种距离；
- `repeatability_summary.csv`：每 repeat type 的 metric、availability、pair counts 和七项摘要；
- `singular_values.csv`：singular index/value、proportion、effective-rank state、centering 和 matrix shape；
- `metrics_summary.csv`：scope/identity/counts、effective rank、Pearson/RMS 汇总、两个有明确定义的困难方向对和 G；
- `selection_audit.csv`：requested/selected/reasons、source/QC/content hashes、QC/human/manual-review 状态；
- `metrics_manifest.json` 与 `.sha256`：scope/policies、完整身份、公式、pair 定义、共同 mask、全部输入 sample/hash、provenance、结果状态及 13 个 CSV 的 SHA-256。

writer 拒绝任何已存在的目标目录。CSV 是 manifest 所列的权威数值视图；可选图未在本切片生成。

## 修改文件

实现与配置：

- `src/acoustic_encoder/metrics.py`
- `src/acoustic_encoder/metrics_outputs.py`
- `src/acoustic_encoder/metrics_validation.py`
- `src/acoustic_encoder/mock_data.py`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`
- `src/acoustic_encoder/version.py`
- `scripts/run_direction_metrics_validation.py`
- `config/default.yaml`
- `config/schema_versions.yaml`
- `config/validation_dev_c5_direction_metrics.yaml`

测试：

- `tests/test_metrics.py`
- `tests/test_metrics_outputs.py`
- `tests/test_metrics_e2e.py`
- `tests/test_mock_data.py`
- `tests/test_config.py`
- `tests/test_pipeline_e2e.py`
- `tests/test_pipeline_cli.py`

文档：

- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `docs/progress/INDEX.md`
- `docs/progress/DEV-C5_P4A_DIRECTION_METRICS_CORE.md`

## 数据来源、provenance 与科研资格

单元测试使用代码内 synthetic arrays 和 S3 直接生成的 `FeatureSet`；最终验证使用 4 个方向、每方向 8 个样本、共 32 个 deterministic mock FeatureSet。没有读取真实 REW TXT、WAV、`SpectrumData` 或真实研究数据。

最终验证固定为：

- `data_origin=simulated`
- `dataset_role=software_validation`
- `run_purpose=software_validation`
- `eligible_for_scientific_analysis=false`
- `scientific_use=prohibited_simulated_software_validation`

`research_analysis` 对 simulated 输入的拒绝已有自动测试。最终 effective rank 和 G 仅验证软件数学路径，不代表设备方向可辨识性、形态增益或任何科研结论。

## 测试优先过程与实际验证结果

版本/阶段门测试先修改后运行，得到预期红灯：`10 failed, 101 passed in 15.06s`；实现版本迁移和阶段门后为 `111 passed in 13.86s`。扩展 S3 rank/tone fixture 时先得到 `2 failed, 1 passed, 3 deselected in 0.84s`，实现后对应 focused tests 通过。

最终专项命令：

```powershell
pytest -q tests/test_metrics.py tests/test_metrics_outputs.py tests/test_metrics_e2e.py tests/test_mock_data.py tests/test_config.py
```

准确结果：退出码 `0`；`123 passed in 3.41s`。

全量回归：

```powershell
pytest -q
```

准确结果：退出码 `0`；`359 passed in 36.56s`。

编译检查：

```powershell
python -m compileall -q src scripts tests
```

准确结果：退出码 `0`；无标准输出。

最终模拟验证：

```powershell
python scripts/run_direction_metrics_validation.py --config config/validation_dev_c5_direction_metrics.yaml --output-root outputs --run-id DEV-C5_P4A_FINAL --feature-count 71
```

准确结果：退出码 `0`；`processing_status=completed`；4 directions；32 samples；71 common valid features；`effective_rank=1.60023820932`；`morphology_gain=17.8376777824`；科研使用状态为 prohibited。

独立 hash 复核：manifest 列出 13 个 CSV，`artifact_hash_mismatches=[]`；manifest 自身 SHA-256 一致。selection audit 为 32/32 selected；repeat pair CSV 32 行，其中 16 个 constructed；between-direction sample-pair CSV 384 行。G 的 numerator=`0.9564141618482149`、REPOS denominator=`0.05361763865877697`、between pair count=384、REPOS pair count=4。

## 生成输出

最终验证目录：

```text
outputs/simulated/software_validation/DEV-C5_P4A_FINAL/metrics/
```

目录包含 13 个 hash-audited CSV、`metrics_manifest.json` 和 `metrics_manifest.sha256`。输出目录已存在时拒绝覆盖；原输入 FeatureSet 为内存对象且从不被 writer 修改。

## 已知限制和 provisional 参数

- 当前默认共同有效门槛、方向数、距离选择和 G 最小分母只用于 software validation，未由真实实验冻结。
- 方向 std 只描述当前 scope；它不是不确定度模型，也没有显著性推断。
- sample-pair G 对 scope 和 repeat design 敏感；本步只固定算法和审计字段，不解释物理意义。
- 全数据方向模板不得直接进入 P5。P5 必须在每个 training fold 内按该 fold 的选择/QC 策略重建，test scope 不得参与。
- 本步不做 reliability weighting、bandwise metrics、cross-mode calibration 或跨 configuration 汇总。
- 可选 Matplotlib 图未生成；没有损失权威数值，因为矩阵和 singular values 已完整写入 CSV。

## P4-B/P5 进入门槛

进入 P4-B 前应先固定 cross-mode comparable state、band definitions、可靠性权重来源与缺失权重策略，并用独立 preprocessing/tone identities 分组；不得把 sparse tone 扩成 dense 物理响应。

进入 P5 前必须：冻结 train/calibration/test partition 及 hash；在每个 fold 内重做 selection、共同有效特征与方向模板；明确禁止 test scope 参与字典、标准化、参数/threshold/tone 选择；保存 fold-level sample/hash 和失败审计；继续通过 provenance/research gate。真实阈值、分类性能和科研结论必须等真实实验方案与数据资格批准后另行验证。

## 对应 Git commit

提交主题：`feat(metrics): add FeatureSet-only direction metrics`。本报告与实现、测试、配置、迁移和索引位于同一个本地提交；未 push。最终 commit hash 由提交完成后的 Git 输出和最终回复给出。

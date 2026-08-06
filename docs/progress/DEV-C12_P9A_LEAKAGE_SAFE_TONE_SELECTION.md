# DEV-C12 / P9-A — 严格防数据泄漏的 tone 候选评分与选择冻结框架

## 状态、日期和分支

- 状态：完成（provisional simulated software-validation 实现与验证）
- 日期：2026-08-06
- 分支：`feature/v2-dual-input`
- 起始提交：`006ea689ccb5759a44acf900cdc941b47ebad0df`
- 单一提交边界：实现、测试、配置/版本迁移、验证 runner、README/MIGRATION/CHANGELOG、INDEX 与本报告同一提交，标题为 `feat(bridge): add leakage-safe tone selection`
- 科研资格：`data_origin=simulated`、`run_purpose=software_validation`、`scientifically_eligible=false`、`deployment_allowed=false`

## 目标与验收标准

本步只完成 P9-A：从显式限定的 training/development sweep tone-projection FeatureSet 对预先定义的 broad DFT candidate universe 计算可审计 component、评分、资格和确定性受约束选择，生成不可变 selected-tone-set artifact。正式路径不得读取 TXT/WAV/`SpectrumData`，不得扫描目录发现样本，不得重跑 P1/P3/P8，不得使用 P5/P6 或 final-test 结果，也不得生成 P7 WAV。

验收要求包括：candidate DFT/Nyquist/tone-order 门禁；多视图严格对齐；development/fold scope 防泄漏；P2-B 精确引用和可选 P4-B 精确引用；variance-ratio 与 weighted-rank 两种评分；required/optional unavailable 语义；Hz/bin spacing 与 band quota；完整 selection trace；typed JSON/CSV/hash round-trip；模拟生命周期 fail-closed；CLI/E2E、全量 pytest、compileall 与 diff check 通过。

## 完成范围

- 新增 schema-1.0 `CandidateToneUniverse`、`ToneSelectionScope`、scope member、FeatureSet reference、component/score/reliability/trace/selection/result 和 selected-tone-set 类型；全部支持确定性 canonical hash 与 typed round-trip。
- candidate 固定 `candidate_id/tone_index/frequency_hz/dft_bin`，验证 `f_k=k f_s/N`、正频率、Nyquist、严格递增、频率/bin/ID 唯一、连续 tone index、analysis band 和 source tone-set hash。
- 输入只接受 manifest 明确列出的 persisted `tone_projection_from_sweep` FeatureSet；逐文件验证 NPZ/JSON SHA-256、FeatureSet content/contract hash、sample/metadata/view/tone set/feature order。没有目录发现或文件名推断。
- `development_selection` 只允许 training/development；`fold_training_selection` 固定 outer fold、精确 training IDs/hash 和 held physical states。final-test 只作为 sealed ID/hash 审计信息，不能成为 FeatureSet 输入。
- 支持 discriminability、raw effective-energy 和 quality/reliability 多视图；sample、tone、configuration/direction/session/repeat/reposition/assembly/block identity 必须完全匹配。raw energy view 必须 `normalization_method=none` 且单位为 dB。
- 计算 direction、CONT、REPOS、configuration gain、P4-B repeatability、raw energy、authoritative SNR/noise 与 excluded-band proximity component；每项保留 available/status/reason、方向、单位、sample/pair IDs 与计数。
- 支持 `variance_ratio` 和 `weighted_rank_sum`；后者保留 normalization reference IDs/hash/count、average-tie rank、denominator、weight 和 contribution，可从输出逐项复算。
- candidate eligibility 集中保留所有失败原因；required unavailable 不插补，optional unavailable 按唯一允许策略重新归一化并 warning。失败 candidate 不删除。
- stable greedy 先满足 band minimum，再全局填充，同时执行 target、band maximum、Hz/bin spacing、tone/bin uniqueness 和 eligible 门禁。排序固定为 final score、required-component availability、frequency、candidate ID；算法明确不是全局最优。
- selection trace 对每个候选记录 rank、score、selected/skipped、phase、blocking tone、spacing、quota/band 和 reason。target 不足时只能返回 unavailable，或在显式 `allow_partial=true` 时返回 partial；不静默降低数量。
- 新增显式 CLI、确定性 simulated E2E runner、隔离输出路径和 stable JSON/CSV/hash bundle；既存输出目录拒绝覆盖。
- single-measurement run manifest 增加 `P9_A=tone_selection_scope_required`，不把单测量流程伪装成已执行 P9-A。

## 明确未完成和非范围

- 未实现 P9-B sweep projection ablation、最少 tone 数分类回测或 P5 重训练。
- 未实现 P9-C sweep↔multisine affine calibration。
- 未实现 P9-D 快速 readout、部署模型、实时监听或 GUI。
- 未生成 P7 WAV；只验证 selected tones 是否兼容 source DFT/grid/P7 约束。
- 未解封 final-test，未使用 P5 accuracy/balanced accuracy/confusion/transfer gap 或 P6 HR performance。
- 未冻结真实实验 component 权重、阈值、spacing、tone count 或 tone set；未生成科研结论。

## 数据流、职责与防泄漏边界

```text
explicit ToneSelectionScope
  + explicit FeatureSet input manifest
  + persisted sweep tone_projection_from_sweep views
  + exact broad CandidateToneUniverse / source ToneSet hash
  + exact canonical-ready P2-B result
  + optional exact-scope P4-B reliability evidence
  + validated P9-A config
    -> scope/role/fold/final-test/provenance/hash gates
    -> candidate physics + FeatureSet tone-order gates
    -> raw components and eligibility
    -> variance ratio OR training-scope weighted ranks
    -> deterministic constrained greedy selection
    -> typed result + software-validation-only ToneSet artifact
    -> stable CSV/JSON/SHA-256 bundle
```

P3-C 是 persisted sweep tone projection 的权威；P2-B 是 dataset/canonical gate 的权威；P4-B 只在精确 scope/result/source-feature/tone-set hash 全匹配时提供 repeatability；P9-A 不建立冲突的 QC 或 provenance 权威。P5/P6 参数和结果不在 CLI 输入中。fold 的 normalization reference 与 selected artifact 绑定 `outer_fold_id` 和 `training_sample_sha256`，不得跨 fold 复用。

## 数学定义

对候选 tone `k`：

- 方向中心：`c_d(k) = median_{i in direction d}(x_i(k))`。
- between-direction：`B(k) = Var_sample({c_d(k)})`，`ddof=1`，高值优先。
- 同重复类型 pair 估计：`v_ij(k) = (x_i(k)-x_j(k))^2 / 2`。
- CONT：`W_CONT(k) = median(v_ij(k))`，只用合法 CONT pairs，低值优先。
- REPOS：`W_REPOS(k) = median(v_ij(k))`，只用合法 REPOS pairs，低值优先；CONT/REASM 不能替代。
- configuration gain：`G(k) = (B_candidate(k)+epsilon_gain)/(B_baseline(k)+epsilon_gain)`；baseline/candidate configuration 来自配置。
- raw effective energy：`E(k) = median_i(x_raw,i(k))`；允许范围 `[L,U]` 的 margin 为 `min(E-L, U-E)`。不以 zscore/demeaned 值代替能量。
- authoritative noise penalty：`P_noise(k)=max(0, SNR_target-median(SNR_k))/noise_scale`；无 authoritative `FeatureQualityRecord` 时 unavailable，不写 0。
- excluded-band proximity：band 内为 1；安全距离内为 `max(0,1-distance/safety_distance)`；否则为 0。band 内 candidate 同时失去 eligibility。
- sweep repeatability：直接读取完全匹配的 P4-B per-tone stability 和 pair evidence；不重新配对。

Variance ratio：

```text
J(k) = B(k) / (w_CONT W_CONT(k) + w_REPOS W_REPOS(k) + epsilon)
```

Weighted rank sum 对 selection-training scope 内、当前 component 可用的 eligible reference candidates 进行 higher/lower 方向排序。ties 使用 average rank；若 reference 数为 `n>1`：

```text
r_c(k) = 1 - (average_rank_c(k) - 1) / (n - 1)
score(k) = sum_c(w_c r_c(k)) / sum_{available c}(w_c)
```

`n=1` 时 rank value 固定为 1。required component unavailable 使 candidate ineligible；optional unavailable 只按显式 missing policy 移除其权重并记录 warning。

## Selection、spacing、quota 与生命周期

- 排序：`final_score` 降序、required component availability 降序、`frequency_hz` 升序、`candidate_id` 稳定升序。
- spacing：新 tone 与全部已选 tone 必须同时满足 `abs(delta_hz) >= minimum_spacing_hz` 和 `abs(delta_bin) >= minimum_spacing_bins`；等于阈值可通过。
- quota：按固定 band order 先满足每 band minimum，再 global fill；maximum、target 与 non-overlap config 门禁持续生效。
- `completed` 才生成 selected-tone-set；不足且不允许 partial 为 `unavailable/draft`，显式 partial 也是 `draft`。
- 当前 simulated 结果强制 `software_validation_only`、`scientifically_eligible=false`、`deployment_allowed=false`、`final_test_evaluation_allowed=false`。
- `approved_deployment_tone_set` 的真实审批路径只实现拒绝规则：模拟 provenance、缺 research gate/canonical P2-B/frozen config/final-test seal/人工批准、已 superseded 等均不能批准。本步不生成 approved artifact。

## Schema、配置和 API 变化

- pipeline：`2.0.0-dev.18`
- config：`2.17.0`
- measurement：`2.4.0`（不变）
- FeatureSet：`2.3.0`（不变）
- single-measurement run manifest：`1.12.0`
- candidate/scope/result/selected-tone-set/output manifest：`1.0.0`

`tone_selection` YAML 集中定义 eligibility、configuration gain、reliability、scoring components/weights/missing/tie policy、variance-ratio weights、target/spacing/partial 与 band quotas。validator 检查完整字段、有限值、范围、正负值、枚举、非负权重与正总权重、唯一/non-overlap band。2.16 配置只在内存迁移到 2.17，补入 `enabled=false` 并 warning，不修改源 YAML，不静默启用 P9-A。

主要 API/CLI：

```python
score_tone_candidates(feature_artifacts, scope, universe, config, reliability_evidence=None)
select_tones_greedy(scores, scope, universe, config)
analyze_tone_selection(feature_artifacts, scope, universe, config, dataset_qc_result=..., reliability_evidence=None)
validate_selected_tone_set_for_p7(artifact, universe)
write_tone_selection_outputs(...)
load_tone_selection_bundle(output_directory)
```

```powershell
python scripts/select_tones.py --config <config> --scope <scope> --inputs <manifest> --candidate-universe <universe> --dataset-qc-dir <dir> --output-root outputs --run-id <id>
python scripts/run_tone_selection_validation.py --config config/validation_dev_c12_tone_selection.yaml --output-root outputs --run-id <id>
```

## 修改文件

核心、输出与入口：

- `src/acoustic_encoder/sweep_multisine_bridge.py`
- `src/acoustic_encoder/tone_selection_outputs.py`
- `src/acoustic_encoder/tone_selection_cli.py`
- `src/acoustic_encoder/tone_selection_validation.py`
- `scripts/select_tones.py`
- `scripts/run_tone_selection_validation.py`

配置、版本和 stage gate：

- `config/default.yaml`
- `config/schema_versions.yaml`
- `config/validation_dev_c12_tone_selection.yaml`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `src/acoustic_encoder/run_execution.py`
- `src/acoustic_encoder/pipeline_cli.py`

测试和文档：

- `tests/test_tone_selection.py`
- `tests/test_tone_selection_outputs.py`
- `tests/test_tone_selection_cli.py`
- `tests/test_tone_selection_validation.py`
- `tests/test_config.py`
- `tests/test_pipeline_e2e.py`
- `README.md`
- `MIGRATION_V1_TO_V2.md`
- `CHANGELOG.md`
- `docs/progress/INDEX.md`
- 本报告

## 数据来源、provenance 与科研资格

正式验证 runner 确定性构造 15-tone broad DFT universe、四个方向、U4SYM/U4ENC、多个 session、CONT/REPOS、development inputs 和 sealed final-test audit IDs。fixture 包含高方向/低 within、低方向、高 within、低能量、excluded/noise band、spacing conflict、band quota 和 unavailable evidence 情形。final-test 没有生成或载入 FeatureSet，分类准确率也不参与期望选择。

- `data_origin=simulated`
- `run_purpose=software_validation`
- `scientifically_eligible=false`
- `deployment_allowed=false`
- `final_test_read=false`
- selected artifact lifecycle：`software_validation_only`

本步未读取真实研究数据或 external-reference REW 文件。模拟 fixture 只验证软件定义和防泄漏门禁，不能形成科研结论、硬件性能声明或真实 tone set 冻结。

## 实际验证命令与准确结果

- 修改前基线：`python -m pytest -q` → `543 passed in 81.94s`。
- P9-A core/output/CLI/E2E：`python -m pytest -q tests/test_tone_selection.py tests/test_tone_selection_outputs.py tests/test_tone_selection_cli.py tests/test_tone_selection_validation.py` → `45 passed in 2.57s`。
- P9-A + config + pipeline E2E：`python -m pytest -q tests/test_tone_selection.py tests/test_tone_selection_outputs.py tests/test_tone_selection_cli.py tests/test_tone_selection_validation.py tests/test_config.py tests/test_pipeline_e2e.py` → `205 passed in 18.03s`。
- 最终全量：`python -m pytest -q` → `598 passed in 60.04s (0:01:00)`。
- `python -m compileall -q src scripts tests` → exit code 0，输出 `compileall passed`。
- `git diff --check` → exit code 0，无输出。
- `python scripts/run_tone_selection_validation.py --config config/validation_dev_c12_tone_selection.yaml --output-root outputs --run-id DEV-C12_P9A_FINAL` → exit code 0；15 candidates、5 selected、14 tone-selection artifacts、`processing_status=completed`、`final_test_read=false`。
- `load_tone_selection_bundle(...)` 对正式输出重新验证 manifest/file/content hashes、typed JSON 与 CSV 一致性成功；selection ID 为 `sha256:89aa69248df62b9c89588453791562aba57f965cbcb02cd05ea3c9bb09cf860e`。

## 生成输出和已知模拟选择

验证根目录：`outputs/simulated/software_validation/DEV-C12_P9A_FINAL/`

正式 P9-A bundle：`outputs/simulated/software_validation/DEV-C12_P9A_FINAL/tone_selection/`

包含：

- `candidate_universe_audit.csv`
- `sample_scope_audit.csv`
- `component_raw_values.csv`
- `component_normalization.csv`
- `candidate_scores.csv`
- `candidate_eligibility.csv`
- `selection_trace.csv`
- `selected_tones.csv`
- `selection_summary.csv`
- `selected_tone_set.json` / `.sha256`
- `tone_selection_result.json`
- `tone_selection_manifest.json` / `.sha256`

确定性选择为 candidate `000/002/006/008/010`，对应 `1000/2000/4000/5000/6000 Hz` 和 DFT bins `100/200/400/500/600`。target=5 已满足；final-test 未读取。`selected_tone_set.json` 文件 SHA-256 为 `a0abee810213764204bf21ff56d18a3b5693ad641251c5a6def16a250731a038`；manifest 文件 SHA-256 为 `d1c5fe55fcc9b306e1ad713134d305d02e0adba9357f3d0ebb84887ead1d1fee`。这些是 synthetic fixture 的已知选择，不是科研或部署建议。

## 已知限制与 provisional 参数

- 当前 validation 使用 variance ratio；weighted rank、tie、normalization、missing policy 和 contribution 可复算由专项测试覆盖，但没有以另一正式 run 形成独立推荐 tone set。
- stable greedy 可解释且确定性，但不保证组合约束下的全局最优。
- P4-B repeatability 与 authoritative SNR 为可选 evidence；缺失时严格 unavailable。当前正式 synthetic run 不伪造这些 evidence。
- effective-energy 仍是 sweep raw-view 的相对 dB 证据，不等于经过批准的跨入口绝对能量校准。
- 所有 eligibility、weights、epsilon、spacing、band、quota 和 target 参数均为 provisional software-validation 值。
- approved deployment lifecycle 只有 fail-closed validator；没有真实 approval workflow 或 approved artifact。
- 输出图是可选项，本步没有生成 score/selection PNG；全部必需结构化 CSV/JSON/hash 输出已生成。

## P9-B 进入门槛

进入 P9-B 前至少需要：冻结一个明确版本的 P9-A configuration/scope/candidate universe；为每个 outer fold 分别生成且只在 fold training 内归一化/选择的 artifact；保留 sealed final-test；定义 sweep projection ablation 和最少 tone 数回测的 training-only protocol；明确不允许用 P5/P6/final-test 指标回写当前选择权重；继续引用 exact P2-B/P4-B/FeatureSet hashes；保持 simulated software validation 与真实研究数据硬隔离。满足这些门槛之前不得声称 selected tones 已验证分类性能、已批准用于 P7 部署或可形成科研结论。

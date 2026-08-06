# DEV-C11 / P6-B — 基于冻结 HR 校准的 Multisine readout 与 HR FeatureSet

## 状态、日期和分支

- 状态：完成（simulated software-validation 实现与验证）
- 日期：2026-08-06
- 分支：`feature/v2-dual-input`
- 单一提交边界：实现、测试、配置/版本迁移、README/MIGRATION/CHANGELOG、INDEX 与本报告同一提交，标题 `feat(hr): add calibrated multisine HR readout`
- 科研资格：`data_origin=simulated`、`run_purpose=software_validation`、`scientifically_eligible=false`、`deployment_allowed=false`

## 目标与验收标准

本步从已持久化的 P3-C `tone_measurement_from_multisine` FeatureSet 离线读取 P6-A 已测 resonance 定义，在不重读 WAV、不重跑 P8、不重新检测 sweep 峰、不插值 sparse tones 的前提下，输出可审计 HR band energy 和 energy fraction。

正式入口只接受：显式 `HRReadoutScope`、显式输入 manifest、精确 P6-A calibration JSON/manifest/digest 及其文件 SHA-256、精确 P2-B result/reference、验证后的 `hr_readout` 配置。验收还要求生命周期、provenance、final-test seal、tone/stimulus/metadata/FeatureSet contract 全部匹配；输出可 round-trip 并验证所有 artifact hash；失败路径不得写成功标记。

## 完成内容

- 新增 version-1.0 `HRReadoutScope`、scope member、P6-A exact-file reference、input manifest、calibration authority、mapping/coverage/energy/fraction/sample/result 类型。
- scope 固定输入顺序、FeatureSet 文件/content/contract hashes、configuration/direction/session/repeat、tone set/stimulus、magnitude semantics、cohort role、P2-B reference、final-test seal、mapping/integration 方法和 provenance。
- 新增 P6-A bundle authority loader；先复核 manifest self-hash、全部 artifact hashes、CSV/JSON 一致性，再返回 typed result/scope/config 与 calibration JSON/manifest 精确 hash。
- draft 和 superseded calibration 明确拒绝；`software_validation_only` 只能授权 simulated/software-validation；`approved_real_calibration` 必须继续满足 P6-A frozen/eligible/approval/complete、真实 provenance、research purpose、P2-B/final-test/hash 门禁。
- 新增 nearest-tone 与 calibrated-window 两个互斥 readout 方法；一个 resolved config 只允许一个 method/energy pair。
- 保留 P8/P3-C 的 per-tone available/missing/invalid、reason codes 和完整 details；P6-B 不重算 QC，不将缺失值写成零。
- 新增 `hr_band_energy` 与 `hr_energy_fraction` 两类 FeatureSet；每个输出带 source FeatureSet content hash、readout scope/result、calibration semantic/exact-file hashes、P2-B hash 及科学/部署/绝对可比性标志。
- 新增稳定 CSV、typed JSON、FeatureSet NPZ/JSON、诊断 PNG、artifact hashes、manifest self-hash、round-trip loader、拒绝覆盖和 failure-only manifest。
- 新增显式 CLI 和 deterministic P6-A→P6-B validation runner；单测量 stage gate 更新为 `P6_B=hr_readout_scope_required`。

## 明确未完成和非范围

- 不读取 WAV/TXT、`SpectrumData` 或原始 P8 period/FFT；不重跑 P1/P8/P3-C。
- 不扫描目录发现 measurement；不从文件名推断 calibration、tone、stimulus 或实验 metadata。
- 不将 sparse tones 插值成 dense response，不跨 missing/invalid tone gap 积分。
- 不学习或应用 sweep↔multisine amplitude bias/calibration；`absolute_energy_comparable=false`。
- 不使用 phase 形成最终 HR 特征；`phase_policy=magnitude_only`。
- 没有权威不确定度输入，因此 `uncertainty_status=unavailable`，不伪造误差条。
- 不实现 P9 tone selection、真实 HR 阈值冻结、final-test 解封、deployment model 或科研结论。

## 数据流与职责边界

```text
explicit HRReadoutScope + explicit FeatureSet input manifest
  + persisted P3-C multisine tone FeatureSets with P8 quality evidence
  + exact verified P6-A calibration bundle/lifecycle/hash
  + exact P2-B result/reference + final-test seal + validated config
    -> contract/provenance/lifecycle/hash gates
    -> nearest-tone OR calibrated-window mapping
    -> coverage/missing/invalid/collision/detuning audit
    -> relative linear-power energy + q_i
    -> typed HRReadoutResult
    -> HR band-energy/fraction FeatureSets
    -> stable CSV/JSON/NPZ/PNG/hash bundle
```

P8 是 per-tone QC 和 phase status 的权威；P3-C 只持久化其证据；P6-A 是 resonance peak/window 和 calibration lifecycle 的权威；P2-B 是 dataset gate 的权威；P6-B 只验证这些精确引用并计算派生 readout，不建立冲突的第二权威状态。

## 数学定义、mapping 与 coverage

对 magnitude dB 值固定使用线性功率比：

```text
p_k = 10 ** (magnitude_db_k / 10)
```

### nearest_tone

对 P6-A group/resonator 的实测中位峰 `f_peak`，从有效 excitation tones 中按 `(|f_k-f_peak|, f_k)` 确定唯一最近 tone。若

```text
|f_k - f_peak| > maximum_detuning_hz
```

则 unavailable；否则 `A_i=p_k`，单位 `relative_tone_power`。同时输出 signed/absolute detuning。多个 resonator 选择同一 tone 时，默认 `allow_shared_tones=false` 使冲突项 unavailable；显式开启时保留 shared-assignment 审计。

### calibrated_window

窗口来自 P6-A 的实测 peak：固定半宽模式为 `[f_peak-w, f_peak+w]`；measured-3dB 模式使用 calibration group 内可用 crossing 的中位数。只在窗口内、按 authoritative tone order 相邻、有效且相邻间隔不超过 `maximum_tone_gap_hz` 的连续 segment 内计算：

```text
A_i = Σ_segments Σ_k 0.5 * (p_k + p_(k+1)) * (f_(k+1)-f_k)
```

单位为 `relative_power_ratio_hz`。coverage 记录 requested/covered span、fraction、首末 tone、最大 gap、有效/观测 tone 数、missing/invalid IDs 和 integration segments。点数、coverage、gap、endpoint 任一硬门槛不满足时 energy unavailable；missing policy 可配置为 warning 或 unavailable，但绝不填零或跨 gap。

### Energy fraction

```text
q_i = A_i / Σ_j A_j
```

`require_all` 在任一 resonator 不可用时使整组 fraction unavailable；`allow_partial` 只在明确列出 missing resonators 后对可用集合归一化，并将状态写为 partial。可用 `q_i` 必须在配置容差内求和为 1。

## Calibration 生命周期和状态决策

| calibration 状态 | P6-B 决策 |
|---|---|
| `draft` | 拒绝 |
| `superseded` | 拒绝并报告 `superseded_by` |
| `software_validation_only` | 仅 simulated + software_validation；科学资格与部署均 false |
| `approved_real_calibration` | 仅在 P6-A frozen/approved/eligible/complete、real/research、exact P2-B/final-test/hash 全通过时可进入真实 readout |

P6-B sample aggregate 保留 `valid/warning/unavailable/exclude_candidate` 的最严重证据；P8 upstream warning/exclude 原因向下传递，但数据和人工 valid 不被删除或翻转。即使值可计算，exclude-candidate 值仍保留并带原因。

## Schema、配置和 API 变化

- pipeline：`2.0.0-dev.17`
- config：`2.16.0`
- measurement：`2.4.0`（不变）
- FeatureSet：`2.3.0`
- single-measurement run manifest：`1.11.0`
- HR readout scope/input/result/manifest：`1.0.0`

FeatureSet 2.3 新增可选 typed `FeatureQualityRecord` 和 `FeatureDerivation`。2.2 artifact 继续可加载为空证据；但正式 P6-B 对 multisine tone 输入要求逐 tone 权威质量证据，旧 artifact 缺失时明确拒绝并要求从权威 P3-C 重新生成，绝不静默补义。

`hr_readout` YAML 集中定义 input contract、phase policy、mapping/detuning/sharing、coverage/count/span/gap/endpoint/missing policy、energy conversion、fraction completeness/tolerance 和 uncertainty。所有当前参数均为 provisional，不是冻结真实实验阈值。2.15/measurement-2.4/feature-2.2 配置只在内存迁移到 2.16/2.4/2.3，加入 disabled P6-B block 和 warning，不改源 YAML。

公开 API/入口：

```python
analyze_multisine_hr_readout(feature_sets, scope, dataset_qc_result, calibration, config)
readout_multisine_feature(feature, resonator_windows, config)
load_explicit_hr_readout_inputs(input_manifest_path, scope)
write_hr_readout_outputs(analysis, scope, config, output_directory, ...)
load_hr_readout_bundle(output_directory)
load_hr_calibration_authority(calibration_directory)
```

```powershell
python scripts/run_hr_readout.py --config <config> --scope <scope> --inputs <manifest> --dataset-qc-dir <dir> --output-root outputs --run-id <id>
python scripts/run_hr_readout_validation.py --output-root outputs --run-id <id> --project-root .
```

## 修改文件

核心与输出：

- `src/acoustic_encoder/hr_readout.py`
- `src/acoustic_encoder/hr_readout_cli.py`
- `src/acoustic_encoder/hr_readout_outputs.py`
- `src/acoustic_encoder/hr_readout_validation.py`
- `src/acoustic_encoder/hr_outputs.py`
- `src/acoustic_encoder/schemas.py`
- `src/acoustic_encoder/tone_features.py`
- `src/acoustic_encoder/dataset_quality_control.py`

配置、版本和入口：

- `config/default.yaml`
- `config/schema_versions.yaml`
- `config/validation_dev_c10_hr_calibration.yaml`
- `config/validation_dev_c11_hr_readout.yaml`
- `src/acoustic_encoder/config.py`
- `src/acoustic_encoder/version.py`
- `src/acoustic_encoder/run_execution.py`
- `scripts/run_hr_readout.py`
- `scripts/run_hr_readout_validation.py`

测试与文档：

- `tests/test_hr_readout.py`
- `tests/test_hr_readout_cli.py`
- `tests/test_hr_readout_outputs.py`
- `tests/test_hr_readout_validation.py`
- `tests/test_hr_outputs.py`
- `tests/test_schemas.py`
- `tests/test_tone_features.py`
- `tests/test_config.py`
- `tests/test_hr_cli.py`
- `tests/test_pipeline_e2e.py`
- `tests/fixtures/rew/external_reference/BW M1.metadata.json`
- `README.md`、`MIGRATION_V1_TO_V2.md`、`CHANGELOG.md`
- `docs/progress/INDEX.md` 与本报告

## 数据来源、provenance 和科研资格

DEV-C11 validation 首先通过现有 DEV-C10 runner 生成 simulated P6-A calibration authority，再确定性构造两个 persisted sparse multisine tone FeatureSet。每个样本有 R1/R2/R3 三个校准窗口、每窗三个 excitation tones、已知线性功率比 4:2:1；tone quality 全部是模拟 P8/P3-C 权威结构。文件名、direction 标签、final-test 或分类结果不参与 mapping 或阈值选择。

- `data_origin=simulated`
- `dataset_role=software_validation`
- `run_purpose=software_validation`
- calibration：`software_validation_only`、`frozen_for_research=false`
- readout：`scientifically_eligible=false`
- `deployment_allowed=false`
- `absolute_energy_comparable=false`

本步未读取真实研究数据或 external-reference REW 数据。模拟恢复只验证软件定义，不得用于科研结论、装置性能声明或部署。

## 实际验证命令和准确结果

- 修改前基线：`pytest -q` → `504 passed in 51.35s`。
- P6-B 核心/配置/lifecycle 初轮定向回归：`pytest -q tests/test_hr_readout.py tests/test_hr_readout_validation.py tests/test_config.py` → `138 passed in 3.96s`。
- 完成全部硬门禁/coverage/FeatureSet-2.2 迁移/`allow_pickle=False` 回归后的最终专项：`pytest -q tests/test_hr_readout.py tests/test_hr_readout_cli.py tests/test_hr_readout_outputs.py tests/test_hr_readout_validation.py tests/test_hr_outputs.py tests/test_tone_features.py tests/test_schemas.py tests/test_config.py` → `195 passed in 8.92s`；exit code 0。
- 最终全量：`pytest -q` → `543 passed in 82.32s`；exit code 0。运行器另报告一个不影响结果的 `PytestRemovedIn10Warning`（`pytest.console_main()` 将在 pytest 10 移除）。
- `python -m compileall -q src scripts tests` → `COMPILEALL_EXIT=0`。
- `git diff --check` → `DIFF_CHECK_EXIT=0`。
- `python scripts/run_hr_readout_validation.py --output-root outputs --run-id DEV-C11_P6B_FINAL --project-root .` → exit code 0，输出 `outputs/simulated/software_validation/DEV-C11_P6B_FINAL/hr_readout`。
- `load_hr_readout_bundle(...)` 对正式验证目录复核 18 个 manifest artifacts、typed result 和 FeatureSet derivation 成功。

## 已知值恢复结果

- 两个样本均恢复 `q=[4/7, 2/7, 1/7]`。
- 最大绝对 energy-fraction 误差：`5.551115123125783e-17`。
- R1/R2/R3 最近 tone signed detuning 分别为 `+2 Hz`、`-5 Hz`、`+8 Hz`。
- typed semantic `readout_id`：`sha256:830e9141f6fea9333bcf34981327dcdfb8b77b577491f400a51ac32198236085`。
- `hr_readout_result.json` SHA-256：`f906b1cf6eeae6b9bbe446c13fb975e33abfb76081ef4e91e6a6766bbed44a22`。
- `hr_readout_manifest.json` SHA-256：`6c683816cb8746fa83cadff618fece0025e936114a9101c64f95100f443db545`。

以上仅是 deterministic synthetic numerical fixture 的软件恢复精度，不是实际测量精度。

## 生成输出

P6-B 验证目录：

`outputs/simulated/software_validation/DEV-C11_P6B_FINAL/hr_readout/`

包含：

- `calibration_reference_audit.csv`
- `tone_mapping.csv`
- `tone_coverage.csv`
- `hr_band_energy.csv`
- `hr_energy_fractions.csv`
- `hr_readout_qc.csv`
- `uncertainty_audit.csv`
- `feature_index.csv`
- `hr_readout_result.json`
- `hr_readout_manifest.json` / `hr_readout_manifest.sha256`
- `hr_readout_diagnostic.png`
- `processed/features/hr_band_energy/*.npz|*.json`
- `processed/features/hr_energy_fraction/*.npz|*.json`

同一 run base 还保存显式 readout scope/input manifest、P2-B bundle、源 P3-C FeatureSets 和 `validation_summary.json`。精确 P6-A authority 位于：

`outputs/simulated/software_validation/DEV-C11_P6B_FINAL-P6A-AUTHORITY/hr_calibration/`

## 已知限制和 provisional 参数

- 当前 calibration 和 readout 均为 simulated；没有 approved real calibration 正例或真实 multisine threshold freeze。
- nearest detuning、window tone count/coverage/gap/endpoint、missing policy 和 fraction policy 均为 provisional validation 参数。
- dB→power 的 readout 是相对量；没有跨入口幅值参考，不能把数值解释为 Joule 或绝对声功率。
- P8 没有权威 per-tone uncertainty 字段，所以不确定度只能 unavailable。
- `allow_shared_tones=true` 仅保留共享审计，不构成 P9 tone-design 认可。
- FeatureSet 2.2 向后可读但无 per-tone evidence；P6-B 会安全拒绝，而非猜测可用性。

## 对应 Git commit

本报告与代码位于同一个本地提交，提交标题为：

`feat(hr): add calibrated multisine HR readout`

最终 commit SHA 在提交完成后的终端回执和任务最终回复中给出；报告不通过 amend 自引用一个会随报告内容改变的 commit hash。

## 下一步及 P9/真实 readout 进入门槛

下一步不是自动把 DEV-C11 结果用于科研。进入真实 P6-B 或后续 P9 前至少需要：

1. 收集并锁定合格 `real_experiment` sweep calibration/training 数据及 multisine readout 数据，完成 metadata/provenance 与 canonical P2-B。
2. 在 development/training 内冻结 P6-A search/prominence/window 和 P6-B detuning/coverage/gap/missing/fraction 阈值；不得查看 sealed final-test 调参。
3. 建立并审批 `approved_real_calibration`：complete、frozen、eligible、approval record、exact hashes 和 final-test seal 全部有效。
4. 若要比较绝对 sweep/multisine energy，单独建立可审计 cross-mode amplitude calibration；在此之前保持 `absolute_energy_comparable=false`。
5. 增加权威 per-tone uncertainty 来源后，才能改变 uncertainty unavailable 状态。
6. P9 必须独立定义 tone reliability/selection scope、训练/测试防泄漏、选择冻结和输出审计；不得把本步共享或覆盖结果冒充 tone selection。

上述门槛完成前，本项目仍不能声明真实 HR readout 的科研结果、分类提升或部署能力。

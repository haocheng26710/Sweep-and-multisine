# 有边界的研究设计压力模拟报告

执行阶段：`SIM-1`

基准协议：`RESEARCH_QUESTION_AND_DECISION_RULES.md` rev-001

冻结方案：`BOUNDED_STRESS_SIMULATION_PLAN.md` / `SIM-0 rev-001`

执行日期：2026-08-13（Europe/London）

## 醒目的资格声明

> 本报告全部证据均为 `simulated / software_validation / scientifically_ineligible`。它只检查软件判定规则对已知注入效应的响应，不代表真实 U4ENC/U4SYM 装置可行，不验证 H1，不得用于论文科学结论，不授予 canonical、freeze、deployment 或真实实验资格。`final_test_read=false`，final-test 始终 sealed。

## 1. 冻结输入与运行基线

正式执行从 clean source commit 启动：

- source commit：`47c60b07242c63f7adefa9c0ebaf1d80149ddea6`
- `source_git_dirty=false`
- 场景：SIM-0 冻结的六个场景，无新增或删除
- seeds：`2026090101–2026090150`，每场景同一组 50 seeds
- 默认样本数：32
- 基础计划：300 scenario-seed runs
- 允许的唯一追加：只有冻结条件触发时，S3 × 50 seeds × 64 样本
- final-test：未读取

在计算第一个结果前已经写出并 hash：

| 冻结输入 | SHA-256 |
|---|---|
| `scenario_manifest.json` | `f37f115ed93e6b5558fba0168bdee898b6206e52c8f4eb2d89803e016a58d2e4` |
| `seed_manifest.json` | `6e6e9e1003c4682cb6a450f08c1a05739b4c3856626f9c5c28687ce3b82234ce` |
| `simulation_run_plan.json` | `15c78c8f54863d0255666936fe19c344ab048f0a9c54411f14a857a6940194f7` |

## 2. 实际运行数与 64 样本分支

- 基础运行：`300/300`
- 追加运行：`0`
- 总有效运行：`300`
- 唯一 run IDs：`300`
- 重复或遗漏 seed：`0`
- 64 样本分支：**未触发**

未触发的固定理由是：S3 32 样本恢复率为 `49/50 = 98%`，已经达到冻结的 `≥80%` 门槛。SIM-0 明确规定此时不得运行 64 样本分支；因此本次没有 `n64` 结果，也没有第三种样本量。

## 3. 六场景结果

| 场景 | 指标 | 分子/分母 | 百分比 | 冻结门槛 | 结果 |
|---|---|---:|---:|---:|---|
| `S0_NULL` | 错误通过率 | `0/50` | `0%` | `≤10%` | pass |
| `S1_LEVEL_ONLY` | `G_demeaned` 错误通过率 | `0/50` | `0%` | `≤10%` | pass |
| `S2_POSITIVE_CONTROL` | 正控制恢复率 | `50/50` | `100%` | `≥90%` | pass |
| `S3_MODERATE_REALISTIC` | 中等压力恢复率 | `49/50` | `98%` | `≥80%` | pass |
| `S4_REASSEMBLY_STRESS` | REASM 压力安全处理率 | `50/50` | `100%` | 诊断门槛 `≥90%` | pass |
| `S5_DATA_QUALITY_STRESS` | 异常检测或安全降级率 | `400/400` | `100%` | `≥95%` | pass |

S5 的分母是 50 个 cohorts × 每 cohort 8 个预先声明异常样本。这里的“安全降级”包括：异常身份由冻结 manifest 显式登记后，runner 无条件阻止该 cohort 产生科学通过。它复用已经由 P8 测试覆盖的 missing tone、噪声、signed drift 和 clipping 能力，但本轮没有为 400 个异常逐一重新生成并执行原始 WAV/P8。因此该 `100%` 是 **批量编排与 fail-closed 安全降级覆盖率**，不能解释为真实设备条件下 P8 检出灵敏度。

## 4. 指标分布摘要

下表列出 50 seeds 的中位数，仅用于解释软件压力响应；不得作为真实结构效应估计。

| 场景 | U4ENC G_raw | U4ENC G_demeaned | U4ENC G_zscore | U4SYM G_demeaned | ΔG_demeaned | U4ENC balanced accuracy | U4ENC macro-F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| S0 | 1.001 | 1.025 | 1.017 | 1.038 | -0.004 | 0.3125 | 0.2725 |
| S1 | 9.811 | 1.037 | 1.048 | 1.017 | 0.033 | 0.2500 | 0.2559 |
| S2 | 14.222 | 15.310 | 15.245 | 1.312 | 14.010 | 1.0000 | 1.0000 |
| S3 | 1.213 | 1.221 | 1.240 | 1.012 | 0.195 | 0.7500 | 0.7500 |
| S4 | 1.401 | 1.369 | 1.329 | 1.085 | 0.287 | 0.6250 | 0.5874 |
| S5 | 5.248 | 5.287 | 3.984 | 1.343 | 3.955 | 0.7500 | 0.6540 |

关键软件行为：

- S0 没有方向谱形注入，完整联合判定没有错误通过。
- S1 的 `G_raw` 中位数升至 9.811，但 demean/z-score 后联合判定 0/50 错误通过，说明纯响度没有被当作足够的方向谱形证据。
- S2 恢复所有 50 seeds，确认固定判定链能找回强已知正控制。
- S3 在中等噪声、gain、REPOS 和 REASM 压力下恢复 49/50；失败 seed 被保留，没有剔除或重跑。
- S4 的 U4ENC REASM demeaned RMS 中位数为 2.114，高于 REPOS 的 0.992；所有 runs 均被安全阻止继续，未让分类表现覆盖物理 REASM 门槛。
- S5 即使方向类指标较高，也因显式 QC 异常全部被阻止产生科学通过。

## 5. grouped validation 与泄漏审计

分类采用预先声明的 leave-one-physical-state-out 分组。每个 fold 的 train/test sample IDs 显式记录在 `grouped_validation.csv`，所有 fold 均满足：

- train/test sample IDs 不相交；
- held-out physical-state group 不进入训练；
- CONT 技术重复不通过随机拆分增加独立样本数；
- 没有 final-test member。

balanced accuracy 和 macro-F1 使用既有 P5 fold predictor 与固定四方向顺序。分类结果只是辅助证据，不覆盖 `G_demeaned` 或 REASM 门槛。

## 6. 最终门槛审计

| 门槛 | 实际值 | 判定 |
|---|---:|---|
| S2 恢复率 ≥90% | 100% | pass |
| S3 恢复率 ≥80% | 98% | pass |
| S0 错误通过率 ≤10% | 0% | pass |
| S1 G_demeaned 错误通过率 ≤10% | 0% | pass |
| S5 检测或安全降级率 ≥95% | 100% | pass |
| final-test 读取次数为 0 | 0 | pass |

冻结三选一判定为：**继续原设计**。

其精确含义只是：32 样本设计在这六个冻结的软件压力场景下满足 SIM-0 门槛，可以继续准备有边界的真实设备诊断。它不表示 32 样本已经具有真实科学统计功效，也不表示真实装置会产生相同效应。

## 7. 是否建议 rev-002

**当前不建议创建协议 rev-002。**

理由：32 样本 S3 已达到 98%，控制场景和安全门禁均通过；按冻结规则既不需要 64 样本评估，也没有模拟证据要求改动主问题、主指标或成功阈值。未来若真实设备诊断显示噪声、REPOS/REASM 或输入质量分布明显超出本软件压力代理，只能按 rev-001 规定的一次性窗口提出有理由的 rev-002，不能引用本模拟来放宽门槛。

## 8. 对真实设备诊断的具体建议

下一阶段仍不是正式 pilot。建议先进行少量、显式标记的 `real_experiment` 诊断采集，并在任何正式分析前：

1. 实测背景噪声、gain 漂移、REPOS 和 REASM 量级，检查本模拟参数是否覆盖实际工程范围，但不据此修改成功阈值。
2. 用 Sweep 作为第一阶段主要测量方式，验证四方向和两结构的身份、频带覆盖、无削波及输入完整性。
3. 单独验证真实 Multisine/P8 authority；当前真实 Multisine 仍不得因本模拟通过而开放。
4. 保留 CONT、REPOS、REASM 的物理状态和 session 分组，不随机拆分技术重复。
5. 先执行小规模设备诊断和 QC review，再决定是否进入正式 pilot；final-test 继续 sealed。

## 9. 实现限制

- 本轮使用独立 feature-level stress adapter，以避免生成 9,600 个大型 WAV；它不替代真实 Sweep/Multisine acquisition。
- `waveform_noise_std_fs` 在 feature-level 压力代理中按固定、预先实现的 `feature_noise_sd_db = waveform_noise_std_fs × 1000` 映射；该映射没有真实设备校准。
- REPOS/REASM 使用确定性平滑谱形扰动，能检查相对强度和分组规则，但不声称复现实物误差分布。
- S5 证明 manifest 驱动的批量异常分配和 fail-closed 降级；其底层异常类型已有独立 P8 测试，但本轮不是 400 次原始音频检出率实验。
- 50-seed 结果只描述冻结软件场景，不是正式 pilot 的 95% 科学置信区间。

## 10. 输出和 hash 复核

输出目录：

`outputs/simulated/software_validation/bounded_stress/SIM-1_20260813T170501284703+0100/`

主要 artifact：

| Artifact | SHA-256 |
|---|---|
| `run_results.csv` | `bc1b7cd415630ff5543cc458148c764b21df3a26a302e8c4144ab634cd4b19c8` |
| `scenario_summary.csv` | `c086913bddf91501480e12596b0195ca7b2b638f6a58f5712f5e320536317b00` |
| `decision_summary.json` | `6048a6520e8d1eedf4cf9eb5c6a9df2481e57f372ec72fc1776cc0fe30300e2c` |
| `artifact_manifest.json` | `70ad30e5f1667fc8651e014406b3810646f5897e26a27d51aca959837fcb59d4` |
| `SHA256SUMS` | `1b551897c8f58d7c8c94552d1afce3ce371f562cbf75221dc91ca33ce03799a6` |

`verify_prepared_manifests` 复核 3/3 冻结 manifests；`verify_artifact_inventory` 复核 317/317 inventory artifacts。`SHA256SUMS` 共 318 行，额外包含 `artifact_manifest.json` 自身。大型模拟结果位于被 Git 忽略的 outputs 隔离目录，没有提交到仓库。

生成图表：

- `scenario_rates.png`
- `g_demeaned_distribution.png`
- `u4enc_vs_u4sym.png`
- `repos_vs_reasm.png`
- `grouped_classification.png`
- `qc_detection.png`

由于 64 分支未触发，按计划不生成 `s3_32_vs_64.png`。

## 11. 验证命令与准确结果

实现提交前：

- `python -m pytest tests/test_bounded_stress_simulation.py -q`：`12 passed in 1.14s`（最终小幅清理后）。
- `python -m pytest -q`：`852 passed in 236.98s (0:03:56)`。
- `python -m compileall -q src scripts tests`：通过，无输出。
- `git diff --check`：通过，无输出。

正式执行：

- `python scripts/run_bounded_stress_simulation.py`
- `base_run_count=300`
- `additional_run_count=0`
- `optional_s3_64_triggered=false`
- `final_decision=继续原设计`
- `final_test_read=false`
- `scientifically_eligible=false`

初次直接调用 verifier 时因未设置源码路径得到 `ModuleNotFoundError: acoustic_encoder`；随后使用 `PYTHONPATH=src` 调用同一 verifier，结果为 prepared manifests `3/3`、inventory artifacts `317/317`。这不影响冻结运行结果或 artifact 内容。

最终文档提交前再次运行：专项 `12 passed in 1.28s`；全量 `852 passed in 229.71s (0:03:49)`；compileall 与 `git diff --check` 均通过、无输出。准确命令见 SIM-1 进度报告。

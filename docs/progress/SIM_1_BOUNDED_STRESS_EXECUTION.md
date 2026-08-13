# SIM-1：有边界的研究设计压力模拟执行记录

状态：完成

日期：2026-08-13

分支：`feature/v2-dual-input`

科研资格：`simulated / software_validation / scientifically_ineligible`

final-test：`final_test_read=false`

## 目标与验收标准

严格执行 SIM-0 rev-001 冻结的六场景、50-seed、32 样本默认计划和唯一 S3-64 条件分支，检查研究判定规则对 null、纯响度、正控制、中等压力、REASM 压力和质量异常的响应。不得调参、挑 seed、增加场景或读取 final-test。

冻结门槛为：S2 ≥90%、S3 ≥80%、S0 ≤10%、S1 ≤10%、S5 ≥95%，且 final-test 读取次数为 0。

## TDD 实现内容

新增独立 `acoustic_encoder.simulation` 命名空间和 CLI，完成：

- 六场景不可变定义和显式 50-seed 列表；
- 32/64 样本身份矩阵；
- 纯响度、方向谱形、gain、noise、REPOS/REASM 独立扰动和 S5 异常编排；
- grouped leave-one-physical-state-out validation；
- clean Git、provenance 和 final-test fail-closed 门禁；
- 首结果前写出 scenario/seed/run-plan manifests；
- per-run hash checkpoint 和可恢复执行；
- 固定 64 分支真值条件；
- CSV、JSON、图表、artifact manifest 与 SHA256SUMS。

实现没有修改 P1–P9、scientific schema、YAML config、UI、真实数据入口或 final-test 定义。

## 修改文件

第一个实现提交：

- `src/acoustic_encoder/simulation/__init__.py`
- `src/acoustic_encoder/simulation/bounded_stress.py`
- `scripts/run_bounded_stress_simulation.py`
- `tests/test_bounded_stress_simulation.py`

第二个报告提交：

- `docs/experiment/BOUNDED_STRESS_SIMULATION_REPORT.md`
- `docs/progress/SIM_1_BOUNDED_STRESS_EXECUTION.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

## 测试优先记录

专项测试按纵向 red-green 循环建立，先后覆盖：

- 冻结场景/seed；
- 32/64 身份；
- 同 seed 重建、不同 seed 身份；
- S0/S1 注入语义；
- S2–S5 场景语义；
- 参数越界拒绝；
- grouped validation 无泄漏；
- 64 分支阈值边界；
- clean-tree 与 final-test 门禁；
- 结果前 manifest 冻结；
- checkpoint 恢复且不重复成功 seed；
- artifact hash 复核与篡改检测。

提交前结果：专项 `12 passed`；全量 `852 passed`；compileall 和 `git diff --check` 通过。

## 两个提交边界

1. Runner 实现提交：`47c60b07242c63f7adefa9c0ebaf1d80149ddea6`，标题 `feat(simulation): implement bounded stress simulation runner`。
2. 本报告、正式结果报告和入口更新使用单独 docs-only 提交，标题 `docs(simulation): report bounded stress simulation results`。

正式模拟从第一个 clean commit 执行，manifests 中的 source commit 与 HEAD 一致，`source_git_dirty=false`。

## 实际运行与结果

- 基础：300/300 runs，全部固定为 32 样本。
- 追加：0 runs。
- S3-64：未触发，因为 S3 32 样本恢复率为 98% ≥80%。
- S0：0/50 错误通过。
- S1：0/50 错误通过。
- S2：50/50 恢复。
- S3：49/50 恢复。
- S4：50/50 安全不继续。
- S5：400/400 异常检测或安全降级。
- 最终三选一：`继续原设计`。
- 建议 rev-002：否。

完整解释和数值分布见 [`BOUNDED_STRESS_SIMULATION_REPORT.md`](../experiment/BOUNDED_STRESS_SIMULATION_REPORT.md)。

## 输出与复核

输出目录：

`outputs/simulated/software_validation/bounded_stress/SIM-1_20260813T170501284703+0100/`

- 300 个 per-run JSON，300 个唯一 run IDs，无 n64 结果。
- 3/3 prepared manifests hash 通过。
- 317/317 inventory artifacts hash 通过。
- SHA256SUMS 318 行，包含 artifact manifest 自身。
- 六张要求图表已生成；未触发的 32/64 比较图按规则不生成。
- outputs 由 Git 忽略，没有纳入提交。

关键 hash 和所有 artifact 名称见正式报告及输出目录中的 `artifact_manifest.json`、`SHA256SUMS`。

## 已知限制

- 压力模拟使用 feature-level adapter，未生成 9,600 个 WAV。
- waveform noise 到 feature noise 使用固定软件代理映射，未经真实设备校准。
- S5 的 100% 包含 manifest 驱动的 fail-closed 安全降级，不是新的真实音频 P8 灵敏度估计。
- 模拟通过不证明真实装置有效，也不证明 32 样本具有科学统计功效。

## 最终验证

报告提交前实际执行：

- `python -m pytest tests/test_bounded_stress_simulation.py -q`：`12 passed in 1.28s`。
- `python -m pytest -q`：`852 passed in 229.71s (0:03:49)`。
- `python -m compileall -q src scripts tests`：通过，无输出。
- `git diff --check`：通过，无输出。
- `verify_prepared_manifests`：`3/3`。
- `verify_artifact_inventory`：`317/317`。
- `run_results.csv`：300 rows、300 unique run IDs、0 n64 rows。
- `git status --short`：只列出本轮 5 个文档文件；大型模拟 outputs 未被 Git 跟踪。

## 下一阶段

可以继续准备少量真实设备诊断，但正式 pilot 尚未开始。真实 Multisine/P8 authority、科研资格和 final-test 均未开放。设备诊断必须使用新的 real_experiment provenance 和独立目录，不能复用或升级本模拟 artifacts。

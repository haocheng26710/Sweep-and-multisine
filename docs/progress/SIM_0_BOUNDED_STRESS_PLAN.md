# SIM-0：有边界的压力模拟方案冻结

状态：完成（仅方案冻结；SIM-1 尚未开始）

日期：2026-08-13

分支：`feature/v2-dual-input`

## 本轮目标

在研究协议 `rev-001` 下冻结一项范围有限、不可按结果扩张的压力模拟方案，并只读核对现有模拟能力能否表达六个预定场景。本轮不实现缺失功能、不生成模拟数据、不运行压力模拟、不读取 final-test。

## 完成内容

- 冻结 `S0_NULL`、`S1_LEVEL_ONLY`、`S2_POSITIVE_CONTROL`、`S3_MODERATE_REALISTIC`、`S4_REASSEMBLY_STRESS`、`S5_DATA_QUALITY_STRESS` 六个场景。
- 冻结结构、四方向、CONT/REPOS/REASM、主辅指标和 grouped validation 边界。
- 冻结 50 个种子：`2026090101–2026090150`；所有场景复用同一 seed set。
- 冻结默认 32 样本和唯一备用 64 样本方案。
- 将可选 64 样本评估限制为：控制场景通过且 S3 32 样本结果满足预定触发条件时，只对 S3 追加一次、复用同一 50 seeds。
- 冻结软件模拟验收率、边界包含规则和三类决策。
- 定义 SIM-1 的 manifest、hash、逐 run、汇总和中文报告输出要求。
- 完成现有能力矩阵，明确哪些可复用、哪些需要 SIM-1 的最小场景层、哪些不应支持。

## 明确未完成与非范围

- 未运行 SIM-1 或任何压力模拟。
- 未生成 simulated WAV、FeatureSet、QC、图表或结果目录。
- 未增加场景编排器、direction-level injection 或独立 REPOS/REASM 参数。
- 未修改算法、schema、配置、UI、测试或数据。
- 未读取 final-test。
- 未评估真实装置可行性，未产生科学结论，未冻结真实实验阈值。
- 未授予 scientific、canonical、freeze 或 deployment 资格。

## 关键设计决策

1. 六个场景和 50 个 seeds 在结果出现前固定，禁止挑 seed 或追加轮次。
2. 同一 seed set 用于六个场景，支持配对的软件稳定性比较。
3. 基础运行是 300 个 scenario-seed runs；备用评估只扩展 S3，因此绝对上限是 350 runs，而不是对六场景做第二轮扫描。
4. S1 明确分离总体声级与频谱形状：`G_raw` 可响应声级，但 demean/z-score 不得把它判为方向谱形。
5. S4 用于暴露 REASM 支配，不把高压失败误写成正效应。
6. S5 异常槽位基于显式 sample-matrix 排序，不依赖文件名或观察到的结果。
7. 所有参数是软件压力定义，不声称来自真实设备分布。

## 只读能力矩阵摘要

| 类别 | 结论 |
|---|---|
| 已支持 | 确定性 seed、已知 H(f)、32 样本身份矩阵、P8 missing tone/noise/drift/clipping QC、P4 morphology gain、P5 grouped metrics、provenance/hash 门禁 |
| 可通过现有参数实现 | S2；S5 的底层异常；S0 的 FeatureSet-only null；S3 的部分噪声/gain/repeat 扰动 |
| SIM-1 最小新增 | 六场景/50-seed 编排与 manifest；完整 E2E null；按方向的纯 level injection；独立 REPOS/REASM 强度；稳定汇总与图表 |
| 不应支持 | 第七场景、自适应挑 seed、第三样本量、重复 64 轮次、自动调门槛、real/final-test 混用、科研或部署资格提升 |

## 运行边界

- 场景数：6。
- 每场景 seeds：50。
- 基础运行数：300。
- 默认每 run：32 样本，总计最多 9,600 个 measurement instances。
- 唯一可选追加：S3 × 50 seeds × 64 样本。
- 最大运行数：350 个 scenario-seed runs；最多 12,800 个 measurement instances。

## 数据来源、provenance 与科研资格

本轮没有生成或使用新的模拟结果。计划中的未来 SIM-1 数据固定为：

- `data_origin=simulated`
- `run_purpose=software_validation`
- `scientifically_eligible=false`

它们不得进入真实研究数据目录、不得用于论文结论或反向放宽 rev-001 门槛。`final_test` 保持 sealed，且本轮未读取。

## 修改文件

- `docs/experiment/BOUNDED_STRESS_SIMULATION_PLAN.md`
- `docs/progress/SIM_0_BOUNDED_STRESS_PLAN.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

没有修改 Python 代码、schema、YAML 配置、UI、测试或数据文件。

## 验证

本轮只允许文档验证。提交前实际执行并记录：

- `git diff --check`
- `git diff --name-only` 和 `git status --short`，确认差异仅为上述文档

准确结果在提交前回填；本轮不运行 pytest、compileall 或模拟命令，也不声称这些验证已运行。

实际结果：

- `git diff --check`：通过，无输出。
- `git status --short`：仅列出 `CHANGELOG.md`、`README.md`、`docs/progress/INDEX.md` 以及两个本轮新增 Markdown 文件。
- 分支核对：`feature/v2-dual-input`。
- 提交前基线 HEAD：`372addf6aa1854e4e0adf07fce8b9c6c8441b9dc`。

## Git commit

本报告与方案、索引、README、CHANGELOG 放在同一个 docs-only 本地提交：

`docs(simulation): freeze bounded stress simulation plan`

提交哈希在提交完成后由 Git 提供；不在文档内预填可能失真的哈希。本轮不 push。

## 已知限制

- 当前低层 transfer 的方向效应强度固定，完整 S0/S1 需要 SIM-1 的小型注入适配层。
- 当前 FeatureSet mock 的 CONT/REPOS/REASM 噪声比例固定，S4 需要独立 REASM 控制。
- “moderate realistic”尚未由真实设备校准，只是冻结的软件压力标签。
- 本方案不证明 32 或 64 样本具有科学统计功效。

## 下一步及进入门槛

下一阶段是 SIM-1，但尚未开始。进入前必须先实现并测试最小场景适配器，预写完整 seed/scenario manifests，锁定 32 样本 identity matrix，确认新的 simulated 输出目录、不可覆盖和 final-test sealed 审计；随后需要用户单独批准运行。

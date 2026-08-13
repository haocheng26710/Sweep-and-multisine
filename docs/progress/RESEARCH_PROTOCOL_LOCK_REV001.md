# 研究问题与判定标准锁定 rev-001

状态：完成（仅研究文档冻结；未开始下一阶段）

日期：2026-08-13

分支：`feature/v2-dual-input`

受验基线提交：`60f08a79705ae41f2139ab41d10f5fdf450575f2`

## 本轮完成内容

创建正式研究协议 [RESEARCH_QUESTION_AND_DECISION_RULES.md](../experiment/RESEARCH_QUESTION_AND_DECISION_RULES.md)，将以下内容冻结为 `rev-001`：

- `U4ENC` 对 `U4SYM`、单麦克风、四个正交方向的确认性研究范围；
- Sweep 主测量与 Multisine 快速/跨模式验证的职责；
- `CONT`、`REPOS`、`REASM` 的独立误差角色；
- H0/H1；
- 以 `G_demeaned` 为主指标，并同时报告 `G_raw`、`G_zscore`、`REASM` 变化、结构差值和 grouped classification；
- 数据完整性、QC、物理效应、分类、95% 置信区间和分组独立性门槛；
- “继续原设计 / 调整后继续 / 重新设计”三类决策；
- 正式 pilot 前最多一次 `rev-002` 的修订窗口，以及 pilot 后禁止结果驱动修改的规则；
- 模拟数据、科研资格和 sealed final-test 的边界。

同时更新进度索引、README 协议入口和 CHANGELOG。没有修改程序代码、算法、schema、配置、UI、测试或数据。

## 采用的默认方案

- 主比较：`U4ENC` 与 `U4SYM`。
- 主方向：`0°/90°/180°/270°`。
- 主要测量方式：Sweep；Multisine 只用于快速测量和跨模式验证。
- 主指标：

  `G_demeaned = median(between-direction distance) / median(within-direction REPOS distance)`

- 主物理门槛：`G_demeaned(U4ENC) > 1` 且高于 `U4SYM`；正式 pilot 目标为相应 95% 置信区间下限分别高于 `1` 和 `0`。
- 分类辅助目标：四方向机会水平 `25%`，grouped balanced accuracy 至少 `50%`；不允许随机拆分同批 `CONT`。
- 物理方向差异指标优先于分类准确率。
- 八方向、V2.5 和最少 tone 数只标记为探索性。

## 尚未完成与下一阶段

本轮未执行压力模拟、未运行任何实验、未分析真实数据、未读取 final-test，也未根据既有模拟结果调整成功门槛。

下一阶段为“有边界的压力模拟”。该阶段尚未开始。它只能检查方案对预先声明扰动和失败模式的稳健性，不能使用 final-test，也不能把模拟结果作为科学证据或反向调整本协议的成功阈值。压力模拟及少量真实设备诊断完成后，如确有必要，正式 pilot 前最多允许一次完整记录的 `rev-002`。

## 修改文件

- `docs/experiment/RESEARCH_QUESTION_AND_DECISION_RULES.md`
- `docs/progress/RESEARCH_PROTOCOL_LOCK_REV001.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

## 数据资格与 final-test

当前数据资格保持：`simulated / software_validation / scientifically_ineligible`。现有软件验收数据不能用于科研结论，不能作为阈值校准依据。`final_test_read=false`，final-test 继续 `sealed`。

## 验证与 Git

- 仅上述五份 Markdown 文档属于本轮修改范围。
- 实际执行 `git diff --check`，准确结果在提交前复核并在最终回复报告。
- 本报告与正式协议位于同一 docs-only 提交，提交标题：`docs(experiment): freeze research questions and decision rules`。
- 协议锁定 Git commit：本文件所在提交；最终完整 hash 在提交完成后的交付回复中记录。
- 本轮不 push，不创建 tag/release，不合并分支。

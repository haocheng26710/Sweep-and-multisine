# FORMAL-0：正式实验协议与采集计划冻结

状态：完成（仅文档冻结；未执行真实测量）

日期：2026-08-19

分支：`feature/v2-dual-input`

## 本轮目标

使用 rev-001 允许的唯一修订窗口，把确认性真实 Sweep 研究范围、REW 参数、分析频带、96 样本身份、采集顺序、停止条件和数据管理规则冻结为 rev-002 与正式采集计划 rev-001。

## 完成内容

- 新增唯一 `RESEARCH_PROTOCOL_REV002.md`，保留主研究问题、`G_demeaned` 和成功门槛不变。
- 固定 U4SYM/U4ENC、四正交方向、Sweep 主测量；八方向仅探索，真实 Multisine/P8 仍未开放。
- 固定 REW V5.31.3、48 kHz、256k、repetitions=1、No timing reference、IR peak、200–8000 Hz、-30 dBFS 和 Windows/iMM-6C 音量。
- 固定完整 200–8000 Hz 保存、200–4000 Hz 主频带、4000–8000 Hz 敏感性频带、48 点/octave 公共对数网格和 1/12 octave smoothing。
- 固定两个 configurations × 四方向 × 三 CONT × 两 REPOS × 两 REASM = 96 个 Sweep。
- 逐行预注册 96 个 sample IDs、configuration、direction、CONT、REPOS、REASM、session、block、role 和顺序。
- 固定文件命名、外置正式数据目录、hash、校准、照片、环境记录、双备份、停止与恢复规则。
- 明确现有预实验全部为 diagnostic pilot，不能并入正式数据。

## 未完成与明确非范围

- 未执行任何真实测量、REW 启动、设备操作或文件导入。
- 未读取或解封 final-test。
- 未修改程序、算法、schema、配置、UI 或测试。
- 未批准真实 Multisine/P8。
- 未把 real_experiment 数据自动标记为科研合格；本轮没有产生 real_experiment 数据。
- 未创建 tag、release，未 push。

## 软件兼容性进入门槛

只读核对显示，现有 P3 dense preprocessing 使用均匀线性 Hz 网格；rev-002 冻结的是 48 点/octave 公共对数网格。现有 fractional-octave smoothing 不等于已经满足该网格契约。本轮按范围不修改代码/config/tests，也不声称该路径已经实现。正式数据进入确认性分析前必须先完成独立实现、迁移、测试和 preprocessing manifest/hash 验证；否则分析必须 fail closed。

该工程门禁不能在看过 formal-pilot 结果后用来选择更有利的网格或 smoothing 参数。

## 唯一 rev-002 的边界

rev-002 只补充正式实施细节：REW 参数、主/次频带、网格/smoothing、最小样本设计、工程解释分档和停止/数据管理规则。rev-001 的主研究问题、H0/H1、`G_demeaned` 定义、`G_demeaned>1`、U4ENC>U4SYM、`ΔG_demeaned>0`、REASM/95% CI/grouped classification 门槛均未放宽。

首次正式样本开始后不允许通过 rev-003 改善结果；偏差必须追加记录。

## 采集顺序摘要

- S01：U4SYM AS01，B01 RP01、B02 RP02。
- S02：U4ENC AS01，B03 RP01、B04 RP02。
- S03：U4ENC AS02，B05 RP01、B06 RP02。
- S04：U4SYM AS02，B07 RP01、B08 RP02。
- 每个 block 使用预注册的平衡方向顺序；每个方向的三次 CONT 连续测量。

顺序不能根据现场频谱结果改变。中断只按计划的停止/恢复规则处理。

## 数据资格和 final-test

正式采集发生后才允许 `data_origin=real_experiment`。本批 schema role 为 `development`、protocol role 为 `formal_pilot`，初始 `eligible_for_scientific_analysis=false`，只有通过 provenance、hash、QC、P2-B 和人工 gate 后才可能取得后续资格。所有现有 pilot 数据保持 diagnostic 隔离。

`final_test_read=false`；本批 96 个样本无一分配为 final-test。

## 修改文件

- `docs/experiment/RESEARCH_PROTOCOL_REV002.md`
- `docs/experiment/FORMAL_ACQUISITION_PLAN_REV001.md`
- `docs/progress/FORMAL_0_PROTOCOL_AND_ACQUISITION_FREEZE.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

## 验证与 Git

开始前确认：

- branch：`feature/v2-dual-input`
- baseline HEAD：`583b3c6234ba3348503e5a1217a879cfa1579713`
- 工作树：clean
- fetch 后本地/远程：`0 ahead / 0 behind`

提交前实际验证：

- `git diff --cached --check`：通过，无输出。
- staged 文件：仅本节列出的 6 份 `.md` 文档；无代码、schema、配置、测试或数据。
- 矩阵：96 rows、96 unique sample IDs、sequence 001–096 连续。
- 完整交叉组合：96 groups，重复/缺失 group 为 0。
- configuration：U4SYM 48、U4ENC 48。
- direction：0°/90°/180°/270° 各 24。
- CONT：C01/C02/C03 各 32；REPOS：RP01/RP02 各 48；REASM：AS01/AS02 各 48。
- block：B01–B08 各 12。
- 本轮未运行 pytest 或 compileall，因为没有修改程序、配置、schema 或测试，也不声称运行了这些命令。

本轮本地提交标题：`docs(experiment): freeze formal protocol and acquisition plan`。不 push。

## 下一步进入门槛

真实采集尚未开始。开始 B01 前必须完成 rev-002 和采集计划的全部人工签署，实测约 0.8 m 距离，记录设备/旋钮/通道/麦克风深度/结构高度，验证 `CMM29939.txt` hash 和实际加载证据，建立两个备份位置并完成 restore drill，确认 diagnostic pilot 与 final-test 隔离。

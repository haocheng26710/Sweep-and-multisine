# COMSOL TRANS-1 RETRY_01 — 一体化双入口固定窗口选择性仿真

日期：2026-08-27T00:18:28.861368+01:00  
终态：`TRANS1_RETRY_01_BLOCKED_BY_SOLVER`

## 首页结论

本轮技术执行在规定的第一项 fine smoke 阶段阻塞。全新 COMSOL 6.4 会话初始模型为空；模型以已验收 TRANS-0 RETRY_02 runner 为唯一几何/selection/study 权威，保留 `quickz`、`getAdj(2,3,boundary)`、单端面 `inside` ports、feature-derived cavity Unions、Java study tag 和 P04M 麦克风表述。

`model.java.study("std_freq").run()` 未抛许可证或求解异常，随后频率表达式返回严格 4 点，但麦克风复压力及 `e_all/e_hr03/e_south/e_plenum` 五个求解场均返回长度 0。因而 fine smoke 未通过，按冻结停止规则分类 `TRANS1_RETRY_01_BLOCKED_BY_SOLVER`。没有进行兼容修复、第二次 smoke、第三网格或几何修改。

`LOW_MESH_QUALITY_WARNING` 继续保留：已验收 coarse minimum quality 为 `1.251e-06`。本轮 fine 实际网格统计在失败前未持久化，不能据配置推定实际单元数或质量。

## 输入与 provenance

- TRANS-0 RETRY_02 的 `SHA256SUMS.txt` 17/17 重新计算匹配；状态仍为 `TRANS0_PASS_FOR_TRANS1_RETRY`。
- 原 TRANS-0、TRANS-0 RETRY_01、原 TRANS-1 的 BLOCKED provenance 均保持原位，未覆盖或重新分类。
- 当前分支与既有脏工作树被保留；未清理、重置、提交或发布。

## 实际执行路径

1. 全新 COMSOL 6.4、4 核会话，端口 `63197`，初始模型数 0。
2. 仅建立 `ISO-CODED / N / fine smoke`，频率 `[1000,1850,3800,5000] Hz`。
3. fine 配置：全局波长 hmax 比 coarse reference 为 `2/3`；关键颈部/腔体 `hmax=0.4666667 mm`。
4. Java study tag `std_freq` 与 feature `freq` 预检查由 runner 强制执行；study run 返回。
5. 结果提取失败：`frequency=4`，`mic/e_all/e_hr03/e_south/e_plenum=0/0/0/0/0`。
6. fail-safe 清理移除模型并断开会话；没有 MPH 达到保存阶段。

完整原始异常与 traceback 保存在 `solver_failure.json`，没有把空数组转换成零值、模拟值或图形曲线。

## 数值与科学门禁

- coarse/fine 256 点比较：未开始；峰中心 `<1%`、固定窗 `<0.5 dB` 和复数传递收敛均未评估。
- 六组合：`0/6` 完成。
- ISO-CODED 2×2 固定窗口矩阵、top-1、diagonal advantage、off-diagonal energy 与峰漂移：未评估。
- ISO-SYM 与 MIX-CONTROL：未运行，不能提供正面或负面对照。
- 当前没有新的声学科学结果，不能声称选择性得到支持、部分支持或否定。
- 当前证据不值得进入 TRANS-2；首先需要用户另行决定是否授权新的、独立诊断阶段。本轮不会自动 RETRY_02。

## 产物说明

由于无求解场，`complex_transfer.csv`、`cavity_and_plenum_participation.csv` 与 `fixed_window_matrix.csv` 只包含明确的 blocked 状态行。六组要求图均为非空诊断图，明确标注 `NOT COMPUTED/BLOCKED`；它们不是数据图。`mph_reload_validation.json` 记录没有 MPH 到达保存/重载阶段。

## 范围边界

未读取 final-test（`final_test_read=false`）；未修改 STL、打印包、冻结设计、实验数据、MPh 安装包或 COMSOL MCP 源码；未授权打印；未运行外场、房间模型、分类器、TRANS-1B、TRANS-2、TRANS-3 或旧 P05–P10；未 commit、push、tag 或 release。

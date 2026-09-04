# COMSOL TRANS-1 RETRY_04 — 有界 fine 结果提取根因诊断

日期：2026-08-27T01:09:02.541206+01:00  
终态：`TRANS1_RETRY_04_ROOT_CAUSE_IDENTIFIED_EMPTY_FINE_MESH`

## 结论

本轮一次授权求解已经把 RETRY_03 的模糊“结果场提取不完整”定位为明确的上游技术根因：fine 网格在 study 运行前实际为 **0 elements、0 vertices**。因此 `sol1` 虽非空且具有4个频率索引，但没有可供麦克风平均或域积分使用的空间网格自由度。

这不是 MPh dataset Node 寻址问题，也不是复数数组整形、麦克风位置或声学选择性本身的失败。

## 决定性证据

- 唯一一次 fresh COMSOL fine 四频点求解完成；总求解次数：1。
- 网格在结果提取前持久化：elements `0`、vertices `0`、minimum/mean quality `0.0/0.0`。
- dataset `dset1` 绑定非空 `sol1`；inner solution 为 `[1000.0, 1850.0, 3800.0, 5000.0]` Hz。
- `freq` 与 `p_inc` 均返回4点，因为它们是解轴/全局参数。
- `aveop_mic(acpr.p_t)`、`aveop_mic(1)`及四个能量积分均返回 `[4,0]`。
- Java EvalGlobal 对边界67及域1–78明确报告“源选择未进行网格划分”。
- `aveop_mic`和各积分算子的几何实体数分别为 `{'aveop_mic': 1, 'intop_all': 78, 'intop_hr03': 23, 'intop_south': 31, 'intop_plenum': 3}`，所以不是空 selection。
- MPH 保存、移除、重载后同样返回 `[4,0]`，排除仅存在于实时会话的偶发提取问题。

## 对既有阶段的修正解释

RETRY_02/03 中“非空 sol1 + 绑定 dataset”只证明了 study/solution 容器存在，不能证明空间声场有效。RETRY_04 表明 fine 构建链生成了频率轴和全局参数，但没有有效体网格；因此不得将该结果称作完整 COMSOL 声学求解。

最可能的代码层原因是：`refine_mesh()`在已有 physics-controlled mesh 上加入局部 `Size` 后，没有确保保留或建立完整体网格操作。后续修复必须显式保留完整自动体网格或建立 `FreeTet`，并在 `study.run()` 前以 elements>0、vertices>0 和 positive quality 作为硬门禁。

## 范围与决策

- 未运行256点 coarse/fine 门禁；六组合0/6。
- 未进入TRANS-2/TRANS-3；未授权打印。
- 未修改几何、物理、频率、窗口、阈值或STL。
- 未读取final-test；`final_test_read=false`。
- 未commit、push、tag或release。
- RETRY_03 provenance `24/24` 匹配。

本轮授权仅覆盖诊断，现已停止。是否执行独立的 fine mesh 修复阶段，需要用户另行授权。

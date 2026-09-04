# COMSOL TRANS-1 RETRY_03 — MPh dataset Node 精确寻址修复

日期：2026-08-27T00:54:24.947594+01:00  
终态：`TRANS1_RETRY_03_BLOCKED_AFTER_NODE_FIX`

## 结论

Java dataset tag 到 MPh dataset Node 的兼容问题已经确定性修复，但 fresh fine smoke 在使用真实 Node 提取后仍未返回四点麦克风场，因此按冻结停止规则终止。本轮没有进入256点网格门禁或六组合，也没有新的声学选择性正面或负面结论。

## Node 修复证据

- 最小回归测试：3/3通过；覆盖显示名称含 `/` 且 Java tag=`dset1`。
- 未修改安装的 MPh 库。
- 加载 RETRY_02 已保存 coarse MPH 后，按 Java tag 找到 Node name=`研究//解 1`、tag=`dset1`。
- 六字段均返回4点；麦克风与冻结结果最大差 `0.0 Pa`。

这证明 RETRY_02 的 `Dataset "dset1" does not exist` 已解决，不是本轮继续阻塞的原因。

## Fresh COMSOL 执行

- fresh coarse ISO-CODED/N 四频点再次通过：62,356 elements、13,158 vertices，minimum/mean quality `1.251e-06/0.5470`，求解 `13.174 s`；MPH 重载麦克风差 `0 Pa`。
- `LOW_MESH_QUALITY_WARNING` 保留。
- fresh fine study 在完整网格之后创建；有效 solution/dataset 的前置审计通过，Node resolver 已实际使用。
- fine 提取在 `mic` 长度门禁失败：`Non-finite or wrong-length field: mic`。
- 按契约未尝试 Java numerical evaluation、另一 dataset、第三网格或 RETRY_04。

## 数值与科学边界

- coarse/fine 256点门禁：未开始；`<1%`和`<0.5 dB`均未评估。
- 六组合：0/6。
- 2×2固定窗口矩阵、diagonal advantage、off-diagonal energy、ISO-SYM和MIX-CONTROL：未评估。
- 不授权打印，不进入TRANS-2/TRANS-3。
- 紧凑底盘只保留为未来机械选项；本轮未修改STL或内部空气域。
- `final_test_read=false`。

## Provenance 与验证

- TRANS-0 RETRY_02：17/17匹配。
- TRANS-1 RETRY_01：32/32匹配。
- TRANS-1 RETRY_02：21/21匹配。
- 既有失败状态均未覆盖或重新分类；未commit、push、tag或release。

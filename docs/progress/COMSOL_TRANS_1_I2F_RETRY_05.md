# COMSOL TRANS-1 RETRY_05 — fine 体网格修复与四频点验收

日期：2026-08-27T01:27:16.561584+01:00  
终态：`TRANS1_RETRY_05_FINE_SMOKE_PASS`

## 结论

RETRY_04 定位的空 fine 网格根因已经修复。使用显式 `FreeTet` 体网格、全局 `Size` 与 FreeTet 下的局部 critical-domain `Size` 后，求解前正体网格硬门禁通过；唯一一次 fresh fine 四频点声学求解产生了完整、有限且非零的空间场。

这证明此前 `[4,0]` 不是设计的声学负结果，而是网格序列技术错误。

## 网格与求解

- explicit FreeTet：856,786 elements、158,524 vertices。
- minimum/mean quality：`4.444e-09/0.6394`。
- 全局/critical hmax：`0.00476388889/0.000466666667 m`；冻结比率门禁通过。
- `LOW_MESH_QUALITY_WARNING`：保留，最低质量非常低。
- 四频点：`[1000.0, 1850.0, 3800.0, 5000.0]` Hz。
- solve elapsed：`493.400 s`；本阶段 fresh COMSOL solve 数为1。

## 字段与重载门禁

- frequency、mic、e_all、e_hr03、e_south、e_plenum 均为4点且全部finite。
- 麦克风幅值：`[1.2906583748633689, 0.3848688899969032, 0.7847086843284014, 0.4273293512669817]`，非全零。
- MPH 在提取前保存，移除、重载后最大复数麦克风差 `0 Pa`，容差 `1e-12 Pa`。
- Java tag `dset1` 继续通过实际 MPh Node 寻址。

## 科学边界与下一步

本轮只证明 fine 体网格及结果提取链恢复，不证明数值收敛或选择性编码。最低网格质量 `4.444e-09` 仍是显著警告，必须由既定 coarse/fine 数值门禁约束。

四频点单模型求解约耗时8.2分钟，因此不得自动启动完整256点、多配置流程。后续是否恢复原冻结的256点门禁，需要用户确认计算时间与低质量风险；未确认前不进入TRANS-2，不授权打印。

- 256点门禁未开始；六组合0/6。
- 未修改几何、物理、频率、候选窗口、阈值或STL。
- RETRY_04 provenance `18/18` 匹配。
- `final_test_read=false`。
- 未commit、push、tag或release。

## API依据

COMSOL 6.4官方API说明：手工增加网格特征会将physics-controlled序列切换为user-controlled；`FreeTet`是实际生成非结构四面体体网格的操作，而`Size`只是被后续网格操作读取的属性。这与RETRY_04的零元素根因及本轮修复结果一致。

- [Physics-Controlled Meshing](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_api_mesh.49.021.html)
- [FreeTet](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_api_mesh.49.082.html)
- [Size](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_api_mesh.49.100.html)

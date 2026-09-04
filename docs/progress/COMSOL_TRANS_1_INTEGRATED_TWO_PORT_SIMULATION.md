# COMSOL TRANS-1 — TRANS-I2F 一体化双入口仿真

日期：2026-08-26T23:06:49.090271+01:00  
终态：`TRANS1_BLOCKED`

## 结论

本阶段没有得到可用的频域解，因此没有传递函数、固定窗优势、腔体参与度、峰/谷、Q 或网格敏感性数值。不能把本次技术阻塞解释成声学阴性结果，也不能声称 ISO-CODED、ISO-SYM 或 MIX-CONTROL 中任何一个具有或不具有选择性。当前建议是 **暂不打印**，先修复新的 COMSOL 6.4 几何边界邻接兼容问题并另行授权重跑 TRANS-1。

## 输入与打印包核验

12 项指定输入均存在并已读取。权威 ZIP SHA-256 为 `383e099df04541ebb667067cfa07754a71a3004dba613d5564dace6a587f24bb`，与冻结值完全一致。B01、L01、`geometry_validation.json` 的 SHA-256 分别为 `523ae1ea424eb769850aea9abcf3ba2931615ac6194dc0c5b66ab4b87b35b7b1`、`0a117c1f01d5f8bb2f48ea6fe87a940a533011cedc67ccd52e54c63f8e8c831e`、`4024de4a005932f9fa2be44f8b9857dbf6be0dee775aabab4540063a72702a2a`。几何包仍保持 `GEOMETRY_READY_SIMULATION_PENDING`；本阶段没有修改 STL 或生成打印件。

## COMSOL 会话与有界失败

先检查到无活动会话，然后启动全新 COMSOL 6.4、4 核 server 会话（localhost:53275），初始模型列表为空。ISO-CODED/N 的稀疏 smoke 采用 1000、1850、3800、5000 Hz，拟使用 1 Pa 压力激励、另一端平面波辐射、Sound Hard 壁面、343 m/s 与 1.2041 kg/m³ 空气，以及 P04M 核验后的 z=1.0 mm、Ø8.8 mm 面平均读出和 Ø9 mm 短孔。

首次构造中 `Extrude.pos` 在 COMSOL 6.4 报未知属性。唯一一次最小修复把高度定位移至 `WorkPlane.quickz`，没有修改 MCP 源码。重试已推进到几何构建和端口/麦克风选择，但在外边界邻接审计调用 `geom.getAdj(3,2,boundary)` 时返回“unsupported entity index”。由于冻结规则只允许一次有依据的最小修复，执行在网格和真实频域求解之前停止。

## 与既有结果的边界

- P03/P04B/P04S 的既有 HR03、HR07 与共同腔结论仅作为建模权威和机制背景；本报告没有把旧解重新包装成 TRANS-1 数据。
- 本轮没有新的内部机制结果；所有数值 CSV 为空或显式标注 `not_computed_blocked`。
- TRANS-1B 启动门未评估，因此未建立 3D 或 screening-only 2D 外场。
- 本阶段不能支持可靠四方向分类，也不能支持 0.8 m 扬声器或真实房间的定量预测。

## 验收项

分支与脏工作树已审计并完整保留；未读取 final-test（`final_test_read=false`）；未修改实验 TXT/MDAT、ACTIVE/EXCLUDED、阈值、schema、论文结论或 STL；未开始 TRANS-2/TRANS-3/P05–P10；未 commit、push、tag 或 release。`compileall` 已通过。由于阻塞发生在网格前，不存在可保存/移除/重载的正式 MPH，缺失 MPH 是阻塞事实而不是被省略的成功产物。

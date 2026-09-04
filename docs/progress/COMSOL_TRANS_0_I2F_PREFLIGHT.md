# COMSOL TRANS-0 — TRANS-I2F 设计冻结与预检

日期：2026-08-26T23:24:28.359449+01:00  
终态：`TRANS0_BLOCKED`

## 结论

TRANS-0A 设计冻结审计和最小 COMSOL 6.4 邻接 API 回归均通过；TRANS-I2F ISO-CODED/N smoke 在几何、selection、空气域连通和 coarse mesh 门禁之后，因 MPh 无法按 `std_freq` 找到已由 Java API 创建的 study 而停止。四个频点均未求解，未保存或重载 MPH。因此本轮没有证明完整建模链路可用，不能授权 `TRANS1 RETRY_01`。

这不是声学阴性结果，也不改变既有 `TRANS1_BLOCKED`。本轮未重新执行完整 TRANS-1，未启动 TRANS-1B、TRANS-2、TRANS-3、P05–P10 或外场。

## TRANS-0A 设计冻结

ZIP、B01、L01、P03、geometry validation 和 17 项包内 manifest 全部匹配冻结 SHA-256；ZIP CRC 检查通过。ZIP SHA-256 为 `383e099df04541ebb667067cfa07754a71a3004dba613d5564dace6a587f24bb`。打印包仍仅为 `GEOMETRY_READY_SIMULATION_PENDING`，只代表数字几何/可打印性检查，不代表 COMSOL 声学验收。

原 TRANS-1 provenance 保持原位且未改写：报告、阻塞日志、runner SHA-256 分别为 `1ddbb4b63ecd1c1d2d65abc292d3d116caa4c98de606352638c83e228faff231`、`2f15d97d36b27671edde50bf775864cd62ee5fc5cd485cfb8b678dafe7e34855`、`9992e2c18e7c80410ffc6b1f3c93cd01c2e9d1a8d1555265323627e2990fd65c`。

## 邻接 API 回归

先写测试并观察到旧调用测试失败；新 TRANS-0 runner 固定使用 `geom.getAdj(2, 3, boundary)`，保留 `WorkPlane.quickz`，不含 `Extrude.pos`。真实 COMSOL 6.4 两相接空气块返回 2 个域和 11 个边界：外边界 10 个，各邻接 1 个域；内部边界 6 邻接域 `[1,2]`。wall selection 为 `[1,2,3,4,5,7,8,9,10,11]`，不包含内部边界 6。

测试夹具首次尝试发现 implicit finalization 不接受 `intbnd`。本轮唯一兼容修复改用仓库既有成功模型支持的显式 `Union(intbnd=true)`，随后同一回归通过。

## ISO-CODED/N 稀疏 smoke

使用冻结几何、343 m/s、1.2041 kg/m³、z=1.0 mm 的 Ø8.8 mm 麦克风面、Ø9 mm 短孔、N 端 1 Pa 压力、S 端平面波辐射和 Sound Hard 外壁。运行过程中以下门禁已经通过：N/S/microphone selections 非空；walls 只取外边界；内部连续边界不进入 Sound Hard；端口不进入 wall；空气域邻接图连通；coarse mesh 生成且元素数与最小质量为正。

runner 原计划在求解后统一写出详细 entity/面积和 mesh 数值；随后 `model.solve("std_freq")` 报 `Study "std_freq" does not exist`，所以这些精确数值没有持久化。按照一次修复上限，没有修改 study 标签/label 调用后重跑。这一缺口本身使 TRANS-0 不能通过。

## 边界与验证

- `sparse_smoke_results.csv` 明确标记四点均未求解，不含伪造复数值。
- 没有成功 MPH；remove/reload/result equality 未执行。
- 不解释方向选择性、HR03/HR07 身份或峰值。
- `final_test_read=false`；未修改 STL、实验数据、既有 TRANS-1 产物或论文结论。
- 未 commit、push、tag 或 release。

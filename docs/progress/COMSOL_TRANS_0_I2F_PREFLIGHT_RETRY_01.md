# COMSOL TRANS-0 RETRY_01 — study tag/label 修复

日期：2026-08-26T23:38:21.467658+01:00  
终态：`TRANS0_RETRY_01_BLOCKED`

## 结论

授权的 study tag/label 修复成功：旧 MPh lookup 失败被真实复现，retry runner 在求解前确认 Java study tag `std_freq`、显示 label `研究`、feature tag `freq`，并通过 `model.java.study("std_freq").run()` 完成四频点真实 Pressure Acoustics 求解。MPH 保存、移除、重载后最大复数压力差为 `0 Pa`。

但是详细 selection 身份审计显示 N/S 入口各包含 5 个边界，而不是单一入口端面。每侧选择面积为 `0.00110771871666134 m²`，冻结端面面积应为 `0.000128 m²`，相对偏差 `+765.405%`。因此 1 Pa 压力被施加到入口附近多张外表面；本轮求解不能证明冻结边界条件链路正确。唯一授权修复仅限 study 调用，未修改 selection 或重跑，终态必须保持 BLOCKED，且不授权 TRANS-1 RETRY_01。

## study tag/label 回归

- 修复前静态门禁按预期失败；修复后确认 runner 不含 `model.solve("std_freq")`。
- live probe：Java tags=`[std_freq]`，label=`Retry 01 Display Label Probe`，features=`[freq]`；旧 MPh 路径稳定报 `Study "std_freq" does not exist`。
- 正式 smoke：tag=`std_freq`，label=`研究`，feature=`freq`，直接 Java run 完成。

## 几何、selection 与网格

- 78 个空气子域、353 个边界；邻接图 1 个连通分量。
- N selection：`[5, 6, 7, 8, 353]`；S selection：`[1, 2, 3, 4, 352]`；microphone：`[67]`。
- wall selection 仅来自外边界，内部连续边界和两个 port selections 均未进入 Sound Hard。
- microphone 面积 `6.04311765836526e-05 m²`，相对 Ø8.8 mm 解析圆面积偏差 `-0.6413%`。
- coarse mesh：62356 elements、13158 vertices；minimum/mean quality `1.251e-06` / `0.547`。

## 四频点结果（仅技术诊断，不作声学解释）

| Hz | microphone real | microphone imag |
|---:|---:|---:|
| 1000 | -1.4793644376 | -0.0273650500476 |
| 1850 | -1.46565978774 | 0.00311358363974 |
| 3800 | 0.221004798408 | 0.0205248128094 |
| 5000 | -0.18038087566 | -0.0151222644783 |

频率轴严格为 `[1000,1850,3800,5000] Hz`；结果 finite 且非全零；direct Java 求解耗时 `19.692308 s`。由于端口 selection 身份失败，不得据此解释方向选择性、HR03/HR07 标签或打印适用性。

## 保存、重载与 provenance

`TRANS0_RETRY01_ISO_CODED_N.mph` SHA-256 为 `e89c6743067b15af4c0408e1cb7ec9fda0c4b3634f70747aba605362b6865f77`。模型从内存移除并在 COMSOL 6.4 重载，频率轴一致，复数结果最大差 `0.0 Pa`，通过 `1e-12 Pa` 技术门槛。

原 TRANS-0 与 TRANS-1 报告保持原位且未重新分类；当前 SHA-256 为 `f484df1563f1b43782a0390156fcc8374f4f31c4757ca3143eb4bc810f6cf1ee` 与 `1ddbb4b63ecd1c1d2d65abc292d3d116caa4c98de606352638c83e228faff231`。本轮未开始 TRANS-1 RETRY_01、TRANS-1B 或后续阶段；未读取 final-test；未修改 STL、MPh/MCP 安装源码、实验数据或论文结论；未 commit、push、tag 或 release。

# COMSOL TRANS-0 RETRY_02 — 端口身份与腔体 selection 最终预检

日期：2026-08-26T23:59:11.560858+01:00  
终态：`TRANS0_PASS_FOR_TRANS1_RETRY`

## 结论

最后一次 TRANS-0 兼容 retry 通过。端口 Box selection 已显式使用 `inside`，不硬编码 COMSOL 边界编号；N/S 各得到一个真实外端面。HR03/HR07 腔体 selection 从 COMSOL 实际生成的六个 primitive-domain selection outputs 分别建立 Union，两个腔体均非空、互不重叠、排除中央 micro-plenum，且解析体积门槛通过。四频点真实 Pressure Acoustics 求解、腔体能量积分、MPH 保存/移除/重载均通过。

`TRANS0_PASS_FOR_TRANS1_RETRY` 仅表示 COMSOL 建模链路可进入用户另行授权的 TRANS-1 RETRY_01；不是声学科学结论、方向选择性结论或最终打印授权。本轮没有启动 TRANS-1 或任何后续阶段。

## 端口 selection 回归

- 旧 `intersects` 真实复现：N=`[5, 6, 7, 8, 353]`、S=`[1, 2, 3, 4, 352]`，各 5 个边界。
- 新 `inside`：N 边界 `6`、S 边界 `2`；编号仅为本次审计输出，runner 未硬编码。
- N/S 中心 y=`116.999998689` / `-116.999998689 mm`，各仅邻接一个三维域。
- N/S 面积均为 `0.000127999993905425 m²`；相对冻结面积 `0.000128 m²` 的最大误差 `4.76138662e-06%`。
- 两个端口均从 Sound Hard 排除；wall selection 精确等于全部外边界扣除 N/S 端口和 microphone，因此顶面、底面和侧壁保留为 Sound Hard；内部连续边界不进入 wall。

## HR03/HR07 cavity selection

- 求解前枚举并记录全部 COMSOL component selection tags；HR03/HR07 各解析到 6 个唯一 feature output tags，见 `cavity_domain_selection_audit.json`。
- `dom_hr03_cavity`：23 个求解域；实际/解析体积 `2.48790314679785e-06` / `2.48808891789548e-06 m³`，相对误差 `-0.00746641715%`。
- `dom_south_cavity`（HR07）：31 个求解域；实际/解析体积 `7.27935614524203e-07` / `7.28088917895484e-07 m³`，相对误差 `-0.0210555837%`。
- 两 selection 非空、互斥并排除 `dom_plenum`；`intop_hr03` 与 `intop_south` 的绑定域分别与对应 Union 完全一致。

## 四频点 smoke

Java study tag=`std_freq`，label=`研究`，feature tag=`freq`；通过 `study.run()` 完成，求解与保存/重载阶段耗时 `16.396484 s`。

| Hz | microphone real | microphone imag | HR03 energy (J) | HR07 energy (J) |
|---:|---:|---:|---:|---:|
| 1000 | -1.27321745657 | -0.222632211182 | 4.19374265378e-12 | 2.06597176521e-12 |
| 1850 | 0.357263113047 | 0.146475287382 | 1.64721476316e-11 | 1.22097984261e-12 |
| 3800 | 0.7416406024 | -0.254397663534 | 1.8997923969e-11 | 8.9597737919e-13 |
| 5000 | 0.421062044812 | 0.0753010908429 | 7.58675998568e-12 | 1.45169744981e-13 |

频率轴严格匹配 `[1000, 1850, 3800, 5000] Hz`；麦克风复数结果 finite 且非全零；两腔体能量积分 finite，`intop_south` 非空、已定义且不恒为零。以上仅证明技术链路，不解释频率编码或方向选择性。

## 网格、保存与限制

- coarse mesh：64406 elements、13604 vertices；minimum/mean quality `1.251e-06` / `0.5471`。
- 登记 `LOW_MESH_QUALITY_WARNING`；本轮未做自适应优化。正式 TRANS-1 必须以规定 coarse/fine 对比后方可接受科学结果。
- MPH：`TRANS0_RETRY02_ISO_CODED_N.mph`，SHA-256 `c0fb652483030c3cec848b720875a318f9a0f792a57f791eb53935fa841f6dd9`。
- 保存、从内存移除并重载后频率轴一致，最大复数压力差 `0.0 Pa`，通过 `1e-12 Pa` 门槛。

## Provenance 与边界

原 TRANS-0、TRANS-0 RETRY_01 与 TRANS-1 的 BLOCKED 报告及输出保持原位，未覆盖或重新分类。未读取 final-test（`final_test_read=false`）；未启动 TRANS-1 RETRY_01、TRANS-1B、TRANS-2、TRANS-3 或 P05–P10；未修改 STL、实验数据、MPh/COMSOL MCP 源码或论文结论；未 commit、push、tag 或 release。

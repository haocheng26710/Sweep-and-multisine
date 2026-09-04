# P04T1V — 集成式 I75/I50P 打印几何有界仿真确认

终态：`P04T1V PASS_FOR_PRINT_AND_P04T2`

日期：2026-08-26

## 范围

本轮只对 P04T1R 已验收的 I75 与 I50P 集成式 P09 插入件做打印前有界确认。BASE 直接复用 P04M `100pct_actual_mic` 权威结果；只新建并求解 I75、I50P。没有优化尺寸、增加候选、运行第二网格、追加频点、bootstrap、参数拟合或分类器，也没有开始 P04T2/P05/P06/U4/外场。

`final_test_read=false`。未 commit、push、tag 或 release。

## 溯源与冻结契约

- P04M SHA 清单：23/23 通过；P04T1R SHA 清单：15/15 通过。
- BASE MPH SHA-256：`317f33a3ccb7813312354af9b17cf4e7cd15c23bfd893aaab020d800cfb343ed`。
- I75：R17.90 mm、十字宽 13.52333744142368 mm、Ø20.40 × 0.70 mm relief、实现空气比例 75.8260419817217%。
- I50P：R17.90 mm、十字宽 8.600000 mm、相同 relief、实现空气比例 54.0587057876302%。
- 实际麦克风面 z=1.0 mm、Ø9 短孔、P03 外颈/凸环、空气参数、BLI、边界、源、探针和复数传递定义均继承 P04M。
- 频率严格为 1400–2100 Hz 的 25 Hz 规则网格，加 1646.88357862959 与 1986.97249931757 Hz 两个冻结 landmark，共 31 点。

P09 集成连接段位于原实心对角通道内，不作为新增空气域；未导入塑料 STL 重建流体域。旧 P04T1 松散四叶只保留为 provenance，未覆盖或重新分类。

## 几何、连通、网格与重载

I75/I50P 均为单一连通空气组件，各 59 个域；0°/90°/180°/270° 固定通道、HR03、中央腔、P03 短孔和实际麦克风路径全部连通。所有 required named selections 非空，无小于 `1e-12 m³` 的非预期 sliver。几何、selection、mesh 及求解结果的保存—移除—重载检查全部一致。

| 状态 | Elements | Vertices | Min quality | Mean quality |
|---|---:|---:|---:|---:|
| I75 | 191,352 | 52,350 | 0.08153 | 0.5954 |
| I50P | 190,827 | 51,794 | 0.03644 | 0.6013 |

每状态仅一个 automatic level 6、2100 Hz control mesh，不作 mesh-convergence claim。

## 分支追踪

使用与 P04E/P04M 相同的严格 cavity-energy 峰值、对数频率、cavity/module participation、kinetic fraction 和 cavity−chamber phase 链接规则；未使用到目标频率的距离。

| 状态 | Refined branch Hz | Cavity/module participation | Assignment margin | Ambiguity |
|---|---:|---:|---:|---|
| BASE | 1651.322621 | 0.593789 | 0.351645 | false |
| I75 | 1679.907902 | 0.581324 | 0.298366 | false |
| I50P | 1729.028013 | 0.560913 | 0.305318 | false |

因此 `f(BASE) < f(I75) < f(I50P)` 成立，两个新增状态分支身份均唯一。

## 冻结 landmark 效应

相对 BASE、实际 z=1 mm 麦克风复数传递：

| 状态 | 1646.88357862959 Hz | Phase | 1986.97249931757 Hz | Phase |
|---|---:|---:|---:|---:|
| I75 | −2.443325 dB | +47.6296° | +2.668542 dB | +0.5712° |
| I50P | −6.524484 dB | +66.2913° | +6.325587 dB | +1.4256° |

I75 保持冻结的负/正符号，且两点绝对效应均大于 1.396 dB 实体重复性底线。I50P 的主要剂量证据仍是 branch 中心继续上移。全部复数传递和能量值有限，未出现宽带数值崩溃；频率点未被视为统计独立样本。

## 终态门禁

| 门禁 | 结果 |
|---|---|
| I75/I50P 几何、连通、网格、求解、保存重载 | PASS |
| 两状态 branch 唯一、无 ambiguity | PASS |
| BASE < I75 < I50P | PASS |
| I75 primary 负、secondary 正 | PASS |
| I75 两 landmark 绝对效应 > 1.396 dB | PASS |
| 无非有限结果或宽带崩溃 | PASS |

据此终态为 `P04T1V PASS_FOR_PRINT_AND_P04T2`。该分类授权打印并允许用户另行授权 P04T2，不表示本轮已经打印、实测或自动开始 P04T2。

## 产物

目录：`outputs/simulation/COMSOL_SCHEME_3A/P04T1V_INTEGRATED_INSERT_BOUNDED_GATE/`

- `P04T1V_HR03_I75_ACTUAL_MIC.mph` — SHA-256 `7dffc0860d5c1498d272c6fbdafefba2e209e3e7f4b0c5ea150c54bd1425618f`
- `P04T1V_HR03_I50P_ACTUAL_MIC.mph` — SHA-256 `fcba3f5271b5a7b7bd91bbcc86320249ae8207e087facdc55fd1b0ec354f9a87`
- `geometry_connectivity_audit.json`、`mesh_statistics.csv`、`reload_validation.json`
- `complex_transfer.csv`、`compartment_energy.csv`、`peak_inventory.csv`
- `branch_tracking.csv`、`fixed_landmark_effects.csv`、`dose_trend_summary.csv`
- `scientific_classification.json`、频率响应图和 branch 趋势图
- `artifact_inventory.json`、`SHA256SUMS.txt`、参数化/分析代码及专项测试。

本轮完成终态分类后停止；未自动开始 P04T2 或任何后续阶段。

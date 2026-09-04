# P04M — 实际麦克风位置与 P03 短孔敏感性验证

## 终态

`P04M PRINT_GATE_RETAINED`

本轮把用户测得的麦克风感应面冻结在 `z=1.0 mm`（比 P01 腔底 `z=3.0 mm` 低 2.0 mm），加入 Ø9.0 mm、`z=1..3 mm` 空气短孔，并按 V2.0.1 名义装配加入 `r=4.5..10.0 mm, z=3.0..3.5 mm` P03 外颈固体环带。100% 与 75% 状态使用完全相同的 P03 几何。

## 内部 branch

实际化 100%/75% tracked cavity-energy branch 分别为 `1651.322621` 与 `1683.341173 Hz`，75%−100% 为 `+0.027705597 octave`。方向保持为正，branch ambiguity=`false`。

- cavity/module participation：`0.593789 → 0.578741`；
- chamber/whole-fluid participation：`0.064213 → 0.093652`；
- kinetic fraction：`0.441170 → 0.455677`；
- cavity−chamber phase：`174.316° → 172.305°`。

## 固定麦克风 observable

| Identity | Legacy P04E z7 | Actualized geometry z7 | Actualized geometry z1 |
|---|---:|---:|---:|
| primary `1646.8836 Hz` | `-2.931 dB` | `-2.826 dB` | `-2.826 dB` |
| secondary `1986.9725 Hz` | `+3.027 dB` | `+2.950 dB` | `+2.950 dB` |
| tracked sample `1675.0 Hz` | `+5.858 dB` | `+5.951 dB` | `+5.951 dB` |

完整复数幅值、相位和三层拆分见 `complex_transfer_both_planes.csv`、`fixed_frequency_effects.csv` 与 `legacy_vs_actualized_comparison.csv`。频率点未被当作统计独立样本。

## 数值门禁

两个状态均保持单一连通声学空气组件、四条固定通道及 HR03 到 z=1 面的路径；z=7 圆盘为两侧空气域共享的内部 Form Union 边界，使用 Pressure Acoustics 默认 Continuity。实际/旧圆盘均复现源 COMSOL Ø8.8 多边形表示的 `60.51292 mm²`（相对解析圆面积 −0.507%）。

- 100%：`71341` elements，min/mean quality `0.08886/0.5993`；
- 75%：`84001` elements，min/mean quality `0.00019/0.5990`。

每状态仅一个 automatic level 6、2100 Hz control 网格，不作 mesh-convergence claim。两个模型均完成保存、移除、重载及结果一致性检查。

## 既有结论边界

若实际化 branch 未反转且身份唯一，则 P04E 内部 branch、中央腔容积干预方向及 P04E/P04F 架构级对照通常仍有效。旧 z=7 的 `−2.931/+3.027 dB`、相位及打印后实际可测幅值必须改按本报告限定。本轮不能回答完整 U4、方向解码、单模块因果贡献率或实际打印实验效果。

P04M 是 nominal/geometry-informed simulation sensitivity analysis，不是实验验证。未生成 STL；未开始 P04T1、P05、P06、U4 或外场；未读取 final-test；未 commit、push、tag 或 release。

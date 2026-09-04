# GEN-ENC-4 M2-B SPINE/WINDOW 机制预飞

终态：`M2B_SPINE_WINDOW_MECHANISM_OBSERVABLE`。

首轮使用四个预固定代表、八个 hash-selected development nuisance cell、两个 repeat 和 208 点主频带，共 64 个成对比较。baseline 与 spine-only 的所有 sector 都通过体积恢复，最大残差 `8.47e-22 m3`；全部求解被动、互易、有限。

| 代表 | 中位相对响应变化 | 中位 state-Gram shift | 门槛 |
|---|---:|---:|---|
| HAND_01 | 1.4780% | 0.0011905 | PASS |
| NEAR_01 | 0 | 0 | FAIL（`shared_alpha=0.03` 恰映射为固定 2 mm SPINE 宽度） |
| RANDOM_01 | 3.8772% | 0.0007044 | PASS |
| PHYSICS_01 | 4.8755% | 0.0009788 | PASS |

预注册要求至少两个代表达到 1% 且高于同 case 传感器噪声；实际 3/4 通过。NEAR_01 是参数域下界的结构性零效应阴性对照，不是数值失败。

因此已冻结 exact80 development-only M2-B 合同；尚未执行 exact80，不读取 validation/final-test，不授权 M3。未执行 commit、push、tag 或 release。

# COMSOL 3A P04D — HR03–S1 全热黏性最小机理对照

## 最终状态

`P04D BLOCKED_BY_SOLVER`

唯一一次冻结频率研究在方程装配阶段失败，没有生成任何频率解。按 P04D 停止规则，本阶段没有进行第二次研究运行、救援网格、BLI 替代或 whole-S1 全热黏性替代，也没有开始 P05、P06 或 U4。

## 权威与合同

- P04B-N HR03 authority SHA-256：`33bf573dddc0c0b163e7f0a5e177fc227d16aa541479606e971cb4a3a9398db7`，与冻结值一致。
- `control_contract.json` SHA-256：`84591f3535db8a57b9339cc97c0a3ad02d55a215aeed85a2072b71812f5984a1`；合同在任何 P04D 数值结果前冻结。
- 既有结论保持：P03 `as_designed_close`；P04A `INADEQUATE`；P04B-N `MODEL NOT CREDIBLE FOR U4`；P04C `TOPOLOGY HYBRIDIZATION SUPPORTED`。
- `final_test_read=false`。

## 耦合与选择审计

- COMSOL 6.4 实际耦合类型为 `AcousticThermoacousticBoundary`，节点成功绑定 `acpr` 与 `ta`。
- inner 接口实体：`262, 263, 264, 265, 279`；outer 接口实体：`257, 259, 260, 261, 284`；创建后实体回读逐项一致。
- authority 中 `bnd_if_inner_000` / `bnd_if_outer_000` 回读为 HR03 内部段间边界，并非 PA–TV 交界；正式预求解配置依据域邻接关系建立两组真实接口。几何未更改。
- 两组接口与 TV wall、Boundary Layer、PA BLI 的交集均为空。耦合节点结构门禁为 `PASS`。

## 唯一正式网格

- 自动等级 6，2100 Hz 控制，三层 Boundary Layer，stretch `1.2`。
- elements `2020`；vertices `813`；minimum / mean quality `0.01064` / `0.2496`。
- 1904.194 Hz 黏性 / 热穿透深度：`0.05018 mm` / `0.05958 mm`。
- 未发现 inverted elements；本阶段只有一个网格，不作完整网格收敛声明。

## 唯一求解调用与失败证据

- `std_freq.run()` 调用次数：1。
- 冻结列表：1400:25:2100 Hz，加 1646.88357862959 Hz 与 1986.97249931757 Hz，共 31 点。
- 失败位置：Stationary Solver 1 方程装配。
- COMSOL 报告 `comp1.acpr.p_t` 在 domain 45 未定义，`atb_outer` 无法在 boundaries `257, 259–261, 284` 计算 `mean(comp1.acpr.p_t)`，继而无法形成 `sigman` 耦合项。
- 完成频点数：0；因此没有合法的 cavity energy、complex transfer、phase、landmark 或 peak 数值。

## 科学解释边界

由于没有任何频率解，不能判断 full-TV integrated cavity 峰靠近 1650.40 Hz 还是 1904.194 Hz，也不能在四个科学结果状态之间作出选择。唯一允许且证据支持的状态是 `P04D BLOCKED_BY_SOLVER`。P04C 的既有拓扑混成结论未被本阶段数值验证或推翻，且仍不授权 U4。

## 产物说明

阻塞态 CSV 仅含状态与失败原因，不含伪造的数值行。没有生成正式 solved MPH；因此 save/remove/reload 检查标记为 `NOT_PERFORMED`。`solver_session_license.log` 保留了 COMSOL 6.4、2 cores、27 licensed products、唯一网格与唯一研究调用记录。

专项单元测试通过 3/3；Python 文件通过 `compileall`；`git diff --check` 通过。SHA-256 清单由 `SHA256SUMS` 提供。

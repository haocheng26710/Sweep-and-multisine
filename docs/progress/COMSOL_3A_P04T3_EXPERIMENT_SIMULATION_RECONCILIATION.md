# P04T3 — P04T1V 仿真与 P04T2 实测的有界对应审计

日期：2026-08-26  
终态：`P04T3 REAL_VOLUME_EFFECT_MODEL_LOCALIZATION_MISMATCH`

## 结论

P04T2 继续支持中央腔体体积是有效控制参数，但 P04T1V 的简化模型不能作为实体频谱的精确预测器。冻结的 P04T2 200–4000 Hz 主频带范数和两个 landmark 的绝对效应摘要，在 selected-4 与 all-six 中均保持 I50P > I75；然而，严格限定到仿真覆盖的 1400–2100 Hz 后，两种状态的实验谱形均未达到 Pearson/cosine ≥ 0.50，I75 的两个固定频点也未同时超过 1.396 dB 且排除零效应。因此模型通过的是“体积控制方向”层面的有限证据，不是局部频谱条形码验证。

本轮没有运行 COMSOL，没有拟合、平移或修改参数，没有扩频追峰，没有重选重复曲线，也没有读取 final-test。

## 权威输入与边界

- P04T1V `SHA256SUMS.txt`：24/24 通过。
- P04T2 `SHA256SUMS.txt`：12/12 通过。
- P04T2 源 manifest：49/49 通过。
- 源 ZIP SHA-256：`179b932bae0bb73980cebb8092d2f022ecb3c1e8d333896416076d270eb0c07d`，通过。
- I75 MPH SHA-256：`7dffc0860d5c1498d272c6fbdafefba2e209e3e7f4b0c5ea150c54bd1425618f`，通过。
- I50P MPH SHA-256：`fcba3f5271b5a7b7bd91bbcc86320249ae8207e087facdc55fd1b0ec354f9a87`，通过。
- 正式跨域比较仅使用 P04T1V 冻结的 31 点、1400–2100 Hz 网格；12 条状态/作用域记录为 exact，112 条为对数频率坐标上的 dB 线性插值；无外推。
- selected-4 身份原样复用：BASE0 1/4/5/6，BASE1 3/4/5/6，I75A 2/3/5/6，I50PA 2/3/4/5；flagged repeat 保留在 all-six，不作删除。
- bootstrap 以完整重复曲线为单位，按四个冻结条件分别重采样，2000 次，固定种子 `260826`；频率点从未作为 bootstrap 单元。

## 冻结频点比较

| 状态 | 频率 (Hz) | 仿真 raw (dB) | 实验 selected-4 (dB) | repeat bootstrap 95% CI (dB) | all-six (dB) | 判断 |
|---|---:|---:|---:|---:|---:|---|
| I75 | 1646.883579 | -2.443 | -0.713 | [-0.966, -0.547] | -0.659 | 同号；实验绝对值未越过 1.396 dB |
| I75 | 1986.972499 | +2.669 | +0.233 | [-0.231, +0.341] | +0.169 | 同号；CI 跨 0，局部效应不确定 |
| I50P | 1646.883579 | -6.524 | -1.842 | [-2.069, -1.328] | -1.719 | 同号；selected-4/all-six 均越过 1.396 dB |
| I50P | 1986.972499 | +6.326 | +0.065 | [-0.318, +0.252] | +0.025 | 同号；CI 跨 0，局部效应不确定 |

四个实验点估计与仿真同号，但局部实验幅值均弱于仿真。符号一致只支持效应方向，不能替代幅值和定位门禁。

## 共同频带对应

| 作用域 | 状态 | demeaned Pearson/cosine | raw RMS mismatch (dB) | demeaned RMS mismatch (dB) |
|---|---|---:|---:|---:|
| selected-4 | I75 | -0.429 / -0.429 | 4.440 | 3.396 |
| selected-4 | I50P | +0.118 / +0.118 | 7.625 | 5.549 |
| all-six | I75 | -0.430 / -0.430 | 4.371 | 3.366 |
| all-six | I50P | +0.100 / +0.100 | 7.605 | 5.569 |

selected-4 与 all-six 不改变结论。所有主要形状相似度均低于 0.50；I75 甚至为负相关。正确状态配对的平均 Pearson/cosine 高于错误交叉配对，但优势不足以抵消绝对形状门禁失败。仿真内部 I75/I50P 谱形相似度为 0.829，实验内部为 0.489（selected-4）和 0.536（all-six）：模型能表达共享的体积变化趋势，却不能可靠识别具体保留比例的完整频谱条形码。

## 剂量顺序与差异分解

冻结 P04T2 200–4000 Hz 主频带 raw/shape RMS 在 selected-4 中为 I75 1.592/1.480 dB、I50P 2.177/2.141 dB；all-six 亦保持 I50P > I75。两个 landmark 的绝对效应均值也保持 I50P > I75。因此真实实验的整体剂量有序效应稳健，且主效应明显高于 BASE 批间变化。

但 1400–2100 Hz 共同带的 raw/shape RMS 在 selected-4 中为 I75 1.378/1.245 dB、I50P 1.201/1.013 dB；all-six 同样反向。这一“宽频总体剂量增强、仿真窄带内重新分配”的事实正是定位失配，而不能通过重新选点、移频或拟合消除。可能的 observable mismatch 包含：归一化模拟 mic transfer 与真实房间、声源、实体装配共同形成的 SPL 条件差；同时 BASE1 是第二个干预前批次，不是 post-intervention return control。单模块贡献率、精确因果比例及绝对传递量到 SPL 的校准均不可识别。

## 冻结门禁

| 门禁 | 结果 |
|---|---|
| 输入身份与哈希 | PASS |
| 仿真 I50P > I75 | PASS |
| 实验总体剂量顺序 selected-4 / all-six | PASS / PASS |
| 四个固定频点点估计同号 | PASS |
| 两状态、两作用域 demeaned Pearson 与 cosine ≥ 0.50 | FAIL |
| 正确配对总体优于错误配对 | PASS |
| I75 两点均 > 1.396 dB 且 CI 不跨 0 | FAIL |
| 主要实验效应高于 BASE 批间变化 | PASS |

故唯一允许的终态为 `P04T3 REAL_VOLUME_EFFECT_MODEL_LOCALIZATION_MISMATCH`。

## 产物与验证

机器可读结果、频率映射、landmark 对照、相似度、剂量顺序、repeat 敏感性、状态配对、差异分解、四组图形、实现与专项测试均位于：

`outputs/real_experiment/research_analysis/P04T3_EXPERIMENT_SIMULATION_RECONCILIATION/`

验证结果：

- P04T3 专项测试：4 passed；P04T1V/P04T2 必要相关回归：14 passed；合计 18 passed；
- `compileall`：通过；
- 机器可读 JSON/CSV 非有限值检查：通过；
- 最终 `SHA256SUMS.txt` 重算与逐项复核：通过。

## 后续决策（本轮不执行）

按冻结规则，只允许建议一次最小实体确认：BASE-C 连续 6 次 → I50P-C 连续 6 次 → BASE-R 连续 6 次，共 18 条曲线。目的仅是建立 return control、区分插入件效应与时间/装配漂移；不新增 I75、不打印新件。本轮未实施该建议，也未开始任何后续阶段。

`final_test_read=false`；未 commit、push、tag 或 release。

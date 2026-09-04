# GEN-ENC-8 小规模 COMSOL 全波桥接结果

## 范围与模型

本轮只使用预先固定的四个 development 代表：`HAND_01 / NEAR_01 / RANDOM_01 / PHYSICS_01`，没有按结果换样。COMSOL 6.4 中建立的是 **M2-B 有效星型流体几何的二维等效面积 Pressure Acoustics 全波模型**：中央方形腔体保留平面空间场；四条支路的每段长度不变，二维宽度取 `段面积 / 9.2 mm`；所有非端口边界为刚性壁。它不是原始抽象图的实体 CAD，也不是三维制造件验证。

四个外端口依次施加 `1 m/s` 法向速度，其余三个端口为零法向速度；读出为中央腔域平均复声压。频率在既有冻结 256 点网格的前 208 点内，结果盲固定索引 `[0,19,38,56,75,94,113,132,151,169,188,207]`，即 200–3973.945 Hz。四个代表 × 四个端口 × 十二频点共 192 个解全部成功且有限。

## 数值门禁

`HAND_01` 在 COMSOL automatic size 3 与更细的 size 2 上重算同一 48 个响应：

- 全响应相对 L2 变化：`0.2190%`（门限 `2%`）；
- 状态签名距离：`0.001291`（门限 `0.05`）。

因此本轮稀疏频点结果通过小规模网格稳定性门禁。五个 `.mph` 文件均已保存并由独立脚本按 SHA-256 复核。

## 主要观察

全波模型没有把四个端口响应全部抹平：在约 346 Hz、1.02 kHz 和 1.35 kHz 附近，端口方向差异明显，说明中央腔的空间传播、干涉和支路反射确实能改变读出。另一方面，四个固定代表的签名距离显示：

| 模型 | 最小代表距离 | 平均代表距离 | 最接近代表对 |
|---|---:|---:|---|
| COMSOL 二维全波 | 0.01894 | 0.42226 | HAND_01–NEAR_01 |
| M2-B 一维分布支路，lossless | 0.02840 | 0.26997 | RANDOM_01–PHYSICS_01 |
| M2-B 一维分布支路，原有 loss | 0.44417 | 0.69806 | HAND_01–NEAR_01 |

这说明两件事同时成立：

1. 五节点/一维支路模型与二维全波的代表关系有实质差异，不能把五节点结果直接当成真实全波结果；
2. 全波并没有自动解决重叠。`HAND_01–NEAR_01` 在本轮全波签名里仍极接近，因此此前 OBS-B 指出的有效几何重叠风险仍然存在。

换句话说，问题不只是“中央腔被压成一个节点”。平面全波空间场能恢复部分差异，却仍保留一组很强的代表重叠；更可能的风险是 **家族参数经过当前 family-to-star 编译后仍产生相近的有效流体几何**，再叠加低阶模型对损耗和空间效应的近似。

## 不能据此声称的内容

- COMSOL 主批次为无损 Pressure Acoustics，而 M2-B 原模型含经验损耗；两者的量化差异包含损耗模型不匹配。
- 二维等效面积模型不包含 9.2 mm 厚度方向、真实窗口排布、壁面热黏损耗、打印圆角或传感器实体。
- 只有四个固定代表和十二个稀疏频点，不能推断四家族总体分离、exact80、validation 或 final-test 性能。
- 采用方向权重重建后的单成员 state-contrast fraction 由该线性构造固定为 `sqrt(3)/2`，不是可用于比较家族的证据；本结果只使用签名距离与网格门禁作解释。

## 终态与下一门禁

终态：`COMSOL_PILOT_NUMERICALLY_STABLE_MODEL_DISCREPANCY_OBSERVED`。

在论文中可将它作为“模型敏感性/局限性”的 development-side 证据，不宜作为装置有效性的确认。若继续，最小且信息量最高的下一步是：只对 `HAND_01` 与 `NEAR_01` 做 **有损二维密集局部频扫 + 3D 三频点 spot-check**，先判断二者接近是否在加入热黏/阻抗损耗与厚度方向后仍存在；在此之前不扩到 exact80，也不进入 M3。

## 产物

- `outputs/gen_enc/GEN_ENC_8_COMSOL_FULLWAVE_PILOT/raw_response_compact.json`
- `outputs/gen_enc/GEN_ENC_8_COMSOL_FULLWAVE_PILOT/result_summary.json`
- `outputs/gen_enc/GEN_ENC_8_COMSOL_FULLWAVE_PILOT/independent_verification.json`
- `outputs/gen_enc/GEN_ENC_8_COMSOL_FULLWAVE_PILOT/*_area2d_fullwave*.mph`
- `scripts/gen_enc_8_comsol_fullwave_pilot_analysis.py`
- `scripts/gen_enc_8_comsol_fullwave_pilot_verifier.py`

未运行 validation/final-test，未提交、未 push。

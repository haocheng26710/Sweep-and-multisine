+# GEN-ENC-4 拓扑保真 M0/M1 比较结果

日期：2026-09-02  
终态：`GEN_ENC_4_M1_NO_MEANINGFUL_GAIN_OVER_M0`  
证据上限：`TOPOLOGY_FAITHFUL_FIVE_NODE_LUMPED_PARAMETER_REDUCED_MODEL_ONLY`  
正式样本：exact80（四家族各 20）× development/validation  
`final_test_read=false`

## 1. 结论

M0 已复现/核验，GEN-ENC-3A 的冻结五节点核心、exact80、nuisance、seed、共同 W 及 D/V 终态哈希均匹配；原 3A 独立 verifier 对 development 和 single-use validation 的重算再次通过。未修改、覆盖、融合或重新分类任何 GEN-ENC-3A 产物。

M1 确实保留显式拓扑：RANDOM 的六个无向槽逐边进入系统矩阵，零边保持缺失；PHYSICS 只保留四条有序环边；NEAR 是由冻结 `alpha` 控制的弱完全图；HAND 不虚构横向边，继续使用冻结的 replicated central-mix 星形语义。每条横向边以 `Y_e(ω)=1/(R_e+jωM_e)` 进入局部节点 Laplacian。系统仍为五节点、集中参数、无传播延迟、无路径相位、无新增谐振节点。

恢复显式边后，汇总响应/状态几何的家族间—家族内比值在 D/V 可重复提高，但绝对比值仍远小于 1；identity 内离散仍明显大于家族质心间距离。M1 的 exact-20 family inference 在 validation 的最小 12-stat max-|T| FWER-adjusted p 值为 `0.0901191`，没有预注册 family contrast 通过 0.05。故不能称为稳定或部分统计分离，也不能把未显著解释为家族等价。

## 2. M0 与 M1 边界

M0 固定为 `PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1`，核心文件 SHA-256 为 `606ee97ef940e4810059ea13eb5f55c31ff23bd64ed66f157e175664607afa0e`。M0 development/validation terminal SHA-256 分别为 `02ca458cad71c37b2d3301f6bc95593c1d80c4924092019680f502b054d71143` 与 `4d674273a89c823060c9c0960616f4872a254d221790cbed491847894491c1e7`。

M1 唯一科学升级是显式局部—局部频率相关集中导纳。为隔离因果变量，以下内容与 M0 保持一致：

- `f[n]=200*2^(n/48)` 的 256 点 solver 网格，3A primary 仍为前 208 点；
- 四主状态 `(0°,90°,180°,270°)`、相同方向权重和共同中心单麦克风读出；
- 3,675 nuisance cells、每 partition 两个 repeat、冻结 D/V seed；
- exact80 身份、顺序、成本资格和四家族各 20 的抽样单位；
- 同一个 M0 development common W，M1 不 refit；V 不更新 W 或 D reference；
- 3A 的六状态对、`S_min`、Gram、`U_drift`、weakest pair、anisotropy、bootstrap 与 max-|T| permutation 公式。

当前四主方向仍近似 one-hot，四状态差分结构的代数秩最多为 3；该秩天花板未被 M1 改变。

## 3. 结果盲横向预算合同

横向总通道面积上限固定为一个中值参考通道 `A_ref=4.6e-5 m²`，增加边数不会增加总预算。

| 家族 | 显式横向语义 | exact20 活跃边数范围 | 总预算占比范围 |
|---|---|---:|---:|
| HAND | 无局部横向边；保留 central-mix 星形 | 0 | 0 |
| NEAR | 六条等权弱边，`A_total/A_ref=alpha` | 6 | 0.03–0.07 |
| RANDOM | 六个固定槽，真实零边缺失 | 0–5 | 0–0.540773 |
| PHYSICS | 固定四边环 | 4 | 0.465625–0.821875 |

RANDOM/PHYSICS 的每边面积为 `A_ref * coordinate / (固定槽数 * 0.8)`；因此所有可能槽同时取上界时，总面积也不超过 `A_ref`。此合同在查看 M1 科研输出前冻结，未按结果调参或重选成员。

## 4. 家族间/家族内响应—状态几何

比较签名由六个按 identity 自身尺度归一的 pair LTES、pair anisotropy 均值/上尾和 Gram drift 均值/上尾组成；对 exact80 各维作共同标准化后，计算家族质心距离相对于两家族 pooled within-family RMS dispersion 的比值。

| Partition | 指标 | M0 | M1 | 绝对增益 | 相对增益 |
|---|---|---:|---:|---:|---:|
| D | 最小 between/within ratio | 0.073488 | 0.138441 | +0.064953 | +88.39% |
| D | 六家族对平均 ratio | 0.216399 | 0.256178 | +0.039779 | +18.38% |
| V | 最小 between/within ratio | 0.074093 | 0.138887 | +0.064795 | +87.45% |
| V | 六家族对平均 ratio | 0.217105 | 0.256132 | +0.039027 | +17.98% |

提升在 D/V 数值上高度重复，但所有 ratio 仍小于 `0.26`，远低于家族间距离超过家族内离散所对应的 1。它是小的模型内几何增益，不足以单独构成 family separation 证据。

## 5. M0→M1 endpoint 效应（validation）

正的 margin effect 表示 M1 提高 `S_min`；正的 drift effect 表示 M1 降低 `U_drift`。CI 是按 identity 配对、20,000 次 bootstrap 的 percentile 95% CI。

| 家族 | M0 margin mean | M1 margin mean | 相对变化 | margin effect 95% CI | M0 drift mean | M1 drift mean | drift favorable effect 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| HAND | 3,663,898.943 | 3,663,898.943 | 0 | [-9.31e-11, 2.10e-10] | 0.02548447016 | 0.02548447016 | [3.52e-17, 2.68e-16] |
| NEAR | 3,663,890.061 | 3,663,916.844 | +0.000731% | [-14.10, 73.62] | 0.02548448957 | 0.02548461101 | [-3.66e-7, 6.94e-9] |
| RANDOM | 3,664,046.337 | 3,664,224.463 | +0.004861% | [-98.76, 508.25] | 0.02548446104 | 0.02548458814 | [-2.24e-7, -4.57e-8] |
| PHYSICS | 3,663,895.253 | 3,664,151.393 | +0.006991% | [-137.66, 694.87] | 0.02548445670 | 0.02548461749 | [-3.77e-7, -2.35e-8] |

RANDOM/PHYSICS 的平均 margin 略增，但配对 CI 跨 0；二者 drift 则小幅恶化。HAND 的零效应是预期的内置负控制，因为 HAND 没有新增横向边且其 M1 方程与 M0 相同。D 的效应方向与 V 一致。

## 6. exact-20 family inference 与领导关系

M1 的 D/V inference 均为 `AVAILABLE`，使用 20,000 次 identity bootstrap 与 100,000 次联合 12-stat max-|T| permutation；cell、repeat、frequency 均未作为独立 family 样本。

- 最小 FWER-adjusted p：D `0.0891391`，V `0.0901191`。
- validation 中最接近阈值的是 drift 的 HAND–RANDOM contrast；其普通 percentile bootstrap CI 排除 0，但 max-|T| multiplicity-adjusted p 仍为 `0.0901191`，所以预注册联合门未通过。
- D/V 的 exact-20 worst-member margin leader 与 drift leader 均为 HAND。
- 但 mean margin 最高的是 RANDOM，而 HAND 对其他家族的 margin contrasts 没有稳定 bootstrap/adjusted support。因此“同一 worst-member leader”不能提升为稳定 family separation。

Validation 的 M1 family 汇总如下：

| 家族 | margin mean | margin worst-member | drift mean | drift worst-member |
|---|---:|---:|---:|---:|
| HAND | 3,663,898.943 | 3,662,930.530 | 0.02548447016 | 0.02548461982 |
| NEAR | 3,663,916.844 | 3,662,684.509 | 0.02548461101 | 0.02548678303 |
| RANDOM | 3,664,224.463 | 3,662,718.313 | 0.02548458814 | 0.02548511233 |
| PHYSICS | 3,664,151.393 | 3,662,014.290 | 0.02548461749 | 0.02548627663 |

## 7. weakest pair、anisotropy 与 feasibility

M0 的四家族在 D/V 均由 `(0°,270°)` 以概率 1 固定为最弱对。M1 后：

- HAND 与 NEAR 仍为 `(0°,270°)`，概率 1；
- RANDOM 的主导最弱对仍是 `(0°,270°)`，V 平均概率 `0.971014`，另有 `0.028986` 转为 `(0°,90°)`；
- PHYSICS 的 `(0°,270°)` 概率降到 `0.892857`，`0.107143` 转为 `(0°,90°)`，且不再对全部 identities 固定。

因此最弱对不再全局固定，但主要仍被 `(0°,270°)` 主导。validation 的 family mean anisotropy 分别为 RANDOM `1.026458`、HAND `1.026461`、NEAR `1.026484`、PHYSICS `1.026706`；变化很小。

M1 的 D/V 均为 80/80 feasible、80/80 `r_stable=3`。所以 3A 的 feasibility/rank 饱和没有被显式拓扑边解除。

## 8. 验证与技术披露

- 专项公式测试：11 passed；覆盖家族图、零边、预算上限、频率相关导纳、局部 Laplacian 守恒、被动性、互易性、五节点、无路径相位/新增节点、HAND=M0 负控制、直接 5×5 solve 和 3A geometry 公式一致性。
- science-blind preflight：四家族固定首成员，有限值/可解/被动/互易/预算均通过；未输出科研指标或排序，未复用为正式结果。
- M0 独立 verifier：D/V 两 partition 均 `INDEPENDENT_PASS`。
- M1 独立 verifier：D/V 各复核 80 candidates、各 160 个确定性 audit units；独立重算 candidate tails、奇异值、20,000 bootstrap 与 100,000 max-|T| permutation，均 `INDEPENDENT_PASS`。
- 有限值：160/160 正式 candidate summaries 标记 finite，全部 compact hashes 通过。
- 唯一技术修复：`NEAR_20 alpha=0.07` 线性映射因浮点舍入略高于 1；按 M0 已冻结的同义规则夹到 `[0,1]` 后继续。没有改变样本、方程语义、阈值或结果。
- 未读取 final-test；未 commit、push、tag 或 release。

## 9. 后续建议与停止点

建议下一步只考虑一个独立预注册的 M2：加入有预算约束的路径相位/分布参数，检验当前集中参数、共同中心读出与近 one-hot 激励是否才是剩余压缩源。理由是 M1 已证明显式邻接能让 weakest-pair 发生可重复的小变化，却没有解除 `r_stable=3` 饱和或形成 multiplicity-adjusted family separation。

暂不建议直接进入 M3。新增谐振节点同时改变状态维数与局部动力学，因果增量大于 M2；应只在 M2 仍无增益且研究问题明确需要额外局部动态自由度时再单独立项。

本阶段到此停止，不启动 M2/M3，等待主控验收与用户决策。

## 10. 论文图包

在不重算 M0/M1、不改变科研终态的前提下，补充了论文可直接使用的 PNG（300 dpi）与 SVG 图包：同尺度拓扑、映射流程、代表性 M1 频率响应，以及 M0→M1 分离度/`S_min`/`U_drift`/weakest-pair 综合比较。每张图均明确标注证据仅来自五节点集中参数降阶模型，并非 COMSOL 空间场、实体或测量结果。

图包索引与建议图注：`outputs/gen_enc/GEN_ENC_4_TOPOLOGY_PRESERVING_M0_M1/figures/README.md`。输入与输出文件哈希记录于同目录的 `figure_manifest.json`。

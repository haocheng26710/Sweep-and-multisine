# GEN-ENC-3A Robust Encoding Geometry Extension 预执行合同

版本：`GEN-ENC-3A-PREEXECUTION-v1`  
状态：`PREEXECUTION_ONLY_GUARDIAN_REVIEW_REQUIRED`  
证据上限：`E2_REDUCED_MODEL`  
`final_test=sealed`，`final_test_read=false`

## 1. 科研问题、增量与边界

GEN-ENC-3A 在不改变被动互易五节点降阶方程、候选身份、状态标签、频率、nuisance、共同白化或成本资格规则的前提下，回答：在 E2 已确认四状态三维差分结构可行之后，哪个预注册设计家族的最弱状态对距离和状态编码几何在冻结扰动中更稳定。

3A 新增的是六个固定状态对的白化距离、最弱状态对 lower-tail expected shortfall、复 Hermitian Gram 几何及其 development-reference 漂移，以及以 identity 为抽样单位的 family inference。`E_primary>1` 与 `r_stable=3` 只保留为 E2 可行性门禁，不参与 3A 新排序。

3A 不训练 decoder，不进入 3B，不做参数搜索、全波、COMSOL、打印、实测或 final-test，不建立实体因果或完全等成本主张。普通技术预飞产物不得作为正式成员结果复用。

## 2. 冻结输入与权威链

以下内容只读并保持原 SHA-256 身份：

- E2-R 权威报告：`outputs/gen_enc/GEN_ENC_2_FORWARD_RESPONSE/e2_r_scientific_synthesis_01/REPORT.md`。
- GEN-ENC-0R 合同/结果与 GEN-ENC-1 estimator 合同/结果。
- E2 preexecution Freeze-01、Freeze-01 CORR01、Freeze-02 与 Freeze02-RC-B-FINAL。
- 正式 E2 driver 链：`gen_enc_2_e2_formal_driver_rc_b_final.py` 覆盖 `gen_enc_2_e2_formal_driver_rc03.py`，调用冻结的 `forward_acoustic_network.py` 优化 solver。
- exact80 manifest：固定顺序 `HAND_01..20 → NEAR_01..20 → RANDOM_01..20 → PHYSICS_01..20`；四家族各 20，禁止替换、重抽、删成员或按性能重选。
- nuisance：`N0001..N3675`，每 cell 质量 `1/3675`，每 cell 内 development/validation 两个 repeat 各占 `1/2`。
- development terminal、single-use validation terminal，以及 development 估计并封存的共同 `W`。3A 不重估 W；validation 不 refit、不更新 development decision/reference。
- 频率：完整 solver 仍计算 256 点；3A 确认指标仅使用 `n=0..207` 的 208 点 primary。256 点只保留 E2 既有 secondary 语义，不替代 primary。
- 状态顺序固定为 `(0°,90°,180°,270°)`。状态列、物理邻接和六对顺序均不得置换。

五节点方程、`R+jωM`、`C=V/(ρc²)`、端口角映射、SplitMix64 seed routing、complex128、E2 solver 与全部 80 identity 参数均不变。

## 3. 矩阵方向、复嵌入、共轭与单位

对一个 candidate、partition、nuisance cell `c` 和 repeat `r`，E2 raw 响应的实际数组方向为

`P[状态, 端口, 频率] ∈ C^(4×4×256)`。

截取 primary 208 点，按“频率升序，其内端口升序”展平，并乘冻结的归一化复合梯形权重平方根。所得复状态矩阵为

`Y_C(c,r) ∈ C^(832×4)`，其中 `832=208×4 ports`，四列依次为 `0°,90°,180°,270°`。

右乘

`P_diff = I_4 - 1_4 1_4^T/4`

得到 `Y_diff,C = Y_C P_diff`。E2 共同 W 并不是另行假设的 proper-complex 算子，而是 development repeat residual 上拟合的实嵌入算子：

`E(Y_diff,C) = [Re(Y_diff,C); Im(Y_diff,C)] ∈ R^(1664×4)`，

`Z_R(c,r) = W_(1664×1664) E(Y_diff,C(c,r)) ∈ R^(1664×4)`。

为按合同形成复 Hermitian Gram，采用唯一的等距逆嵌入，不做新拟合：

`Z_C = Z_R[0:832,:] + i Z_R[832:1664,:] ∈ C^(832×4)`。

因此每个状态对的欧氏距离在两种表示中严格相同。raw response 是冻结源归一化下的中心复压力/传递响应；频率权重无量纲；W 具有相应响应单位的逆单位。因此 `Z` 和 `d_ab` 以“白化噪声单位”解释，为无量纲；Gram 元素为白化噪声单位平方，trace 归一化后无量纲。

复 Hermitian Gram 只表示上述冻结 canonical reassembly 下的 state geometry。由于实 W 可混合原始 Re/Im 行，3A 不把该 Gram 的虚部解释为新的物理相位、传播机制或 proper-complex covariance。

## 4. 六对距离与主指标

六对顺序唯一冻结为：

1. `(0°,90°)`
2. `(0°,180°)`
3. `(0°,270°)`
4. `(90°,180°)`
5. `(90°,270°)`
6. `(180°,270°)`

令 `z_a` 为 `Z_C` 的状态列，则

`d_ab(c,r) = ||z_a(c,r)-z_b(c,r)||_2`。

这里复范数包含共轭：`||v||_2=sqrt(v^H v)`。主单位量为

`d_min(c,r)=min_(a<b) d_ab(c,r)`。

主 candidate 指标是冻结 nuisance/repeat 权重下最低 5% 概率质量的 expected shortfall：

`LTES_0.05(X) = (1/0.05) ∫_0^0.05 F_X^(-1)(u) du`。

离散实现将单位按值稳定升序排列，依次累积归一化权重；跨过 0.05 的边界单位只取恰好补足尾部质量的分数权重，不插值数值。因为共有 7,350 个等权单位，最低尾部包含 367 个完整单位和第 368 个单位的一半质量。主分数为

`S_min = LTES_0.05(d_min)`，越大越好。

如采用标准 loss-CVaR 记号，令 `L=-d_min`，则本指标严格为

`S_min = -CVaR_0.95(L)`，

其中 `CVaR_0.95` 表示 loss 最高 5% 尾部均值；符号不得反转。

同时保存并报告：六个 `LTES_0.05(d_ab)`；每单位最弱 pair identity；按权重汇总的六类最弱 pair 分布；以及

`A_pair(c,r)=max_ab d_ab(c,r)/d_min(c,r)`。

`A_pair=1` 表示六对等距，越大表示 pair margin 越不均匀。若 `d_min<=0`，anisotropy 为 `UNAVAILABLE`，不得加 epsilon。精确并列按上述六对顺序取第一个最小值，并另保留原始六距离以便审计。

## 5. Gram、development reference 与漂移

固定状态顺序下，单位 Gram 必须使用复共轭：

`G(c,r)=Z_C(c,r)^H Z_C(c,r) ∈ C^(4×4)`。

禁止写成无共轭的 `Z^T Z`。唯一归一化为：先作数值 Hermitian 对称化 `(G+G^H)/2`，再除以严格为正的实 trace；不作 PSD 投影、不加 ridge、不按 family 或 partition 重新缩放：

`G_hat(c,r)=Herm(G(c,r))/Re tr(Herm(G(c,r)))`。

每个 identity 的参考 Gram 只由其完整 development 7,350 单位构造：

`G_ref,D = Normalize_Hermitian( Σ_c (1/3675) Σ_r (1/2) G_hat_D(c,r) )`。

全部 80 个 development reference、共同 W 绑定和 development 指标封存后，validation 才可读取。validation 对每个 identity 复用自己的 `G_ref,D`，不得更新、重估或反馈 development。

唯一主漂移度量冻结为 Frobenius 距离：

`δ_F(c,r)=||G_hat(c,r)-G_ref,D||_F`，越小越好。

candidate 同时报告加权均值与最高 5% 概率质量的 `UTES_0.05(δ_F)`；后者是 worst-tail drift，离散分数边界规则与 lower tail 相同但按值降序累积。不得改用 CKA、谱角或事后选出的其他距离替代主漂移。

## 6. family estimand 与 identity-level inference

cell/repeat 只用于每个 identity 内计算冻结 endpoint。family 推断的唯一抽样单位是 identity；禁止把 cell、repeat、state pair 或 frequency 当独立 family 样本。

对每家族 exact-20：

- margin worst-member 为 20 个 `S_min` 的最小值，越大越好；
- drift worst-member 为 20 个 `UTES_0.05(δ_F)` 的最大值，越小越好；
- 完整报告全部 20 点、median、IQR 和 ECDF，不用单成员替代 family；
- margin contrast 唯一定义为 `ΔS(A,B)=mean(S_A)-mean(S_B)`；drift contrast 唯一定义为 `ΔD(A,B)=mean(U_B)-mean(U_A)`，其中 `U` 是 candidate 的 upper-tail 5% Gram drift。两个 contrast 的正值都表示有利于排在 pair `(A,B)` 左侧的 family；
- pair 顺序按冻结 family 顺序 `HAND, NEAR, RANDOM, PHYSICS` 的字典组合：`H-N,H-R,H-P,N-R,N-P,R-P`；
- 每个 contrast 的 studentized statistic 为 `T=Δ/sqrt(s_A²/20+s_B²/20)`，`s²` 是 identity 值的 `ddof=1` 样本方差。零或非有限 denominator 使该 endpoint 为 `INCONCLUSIVE`，不得换统计量；
- identity bootstrap：初始化 `PCG64(2026090301)`；按 family 冻结顺序各生成一个 `20000×20` 的 identity-index 矩阵，同一重采样 index 同时用于该 identity 的 margin/drift。每行在 family 内对 20 identities 有放回抽 20，pairwise Δ 保持上述方向。percentile 95% CI 固定为 NumPy `quantile([0.025,0.975], method="linear")`；
- identity permutation：初始化 `PCG64(2026090302)`；每次对按冻结 family/member 顺序拼接的全部 80 个 paired identity records 调用一次 `permutation(80)`，再连续分为四组各 20。每次重新计算 group mean、`ddof=1` variance、全部 12 个 T，并保存该次 `max(abs(T_1..T_12))`；共 100,000 次；
- 每个 observed statistic 的 two-sided FWER-adjusted p-value 固定为 `(1 + #{100000 permutation maxima >= |T_obs|}) / 100001`，阈值 `0.05`。任一 permutation 出现零或非有限 denominator 时推断 `INCONCLUSIVE`，不得丢弃 permutation 或换统计量。

若方差为零导致 studentization 不可定义，推断为 `INCONCLUSIVE`，不得换统计量。bootstrap/permutation 不重采样 cell 或 frequency。

## 7. 终态与 3B 门禁

技术有效性与科研裁决分开。任一输入/hash/shape/dtype/solver/checkpoint/完整性失败先进入普通技术修复；无法在既定合同内修复时为 `GEN_ENC_3A_TECHNICALLY_BLOCKED`，不得写成科学否定。

在 80/80 D、reference seal、80/80 single-use V 与独立复核均完成后：

- `GEN_ENC_3A_STABLE_FAMILY_SEPARATION_SUPPORTED`：四家族 exact-20 的 E2 可行性门均成立；同一个唯一 family 在 D 与 V 同时取得最佳 margin worst-member 和最佳 drift worst-member；该 family 对另外三家族的 identity-level mean contrast 在 D/V 方向一致，V 的 bootstrap 95% CI 均排除 0，且 12-contrast max-|T| permutation 调整后 `p<=0.05`。
- `GEN_ENC_3A_ROBUST_GEOMETRY_DIFFERENCES_PARTIAL`：完整、技术有效的 V 在 margin 或 drift 至少一个端点上存在调整后 family difference，但未满足同一家族、双端点、D/V 方向与 exact-20 worst-member 的全部联合条件。
- `GEN_ENC_3A_NO_STABLE_FAMILY_SEPARATION`：完整、技术有效，但 family effect 在 V 不显著、E2 ceiling/saturation 仍支配、D/V leader/方向不稳定，或任一 exact-20 feasibility gate 科学失败。
- `GEN_ENC_3A_INCONCLUSIVE`：输入完整且 solver 技术有效，但预注册推断数学上不可定义或无法给出唯一裁决；不得用替代阈值或事后统计量补救。

只有 `GEN_ENC_3A_STABLE_FAMILY_SEPARATION_SUPPORTED` 才建议进入 3B。其他终态停止于 3A。

## 8. 存储、分块、审计与恢复

禁止持久保存约 251 GiB 的全量 raw `Y_diff`。正式处理采用 candidate/partition 内 25 cells/chunk，共 147 chunks；只保留：

- `distances[cell,repeat,6]` float64；
- `gram_drift[cell,repeat]` float64；
- `weakest_pair_index[cell,repeat]` uint8；
- `pair_anisotropy[cell,repeat]` float64；
- development reference Gram、candidate summary、family inference inputs；
- 每 identity/partition 两个在响应生成前按 SHA-256 规则选定的完整 primary complex `Y_diff[832,4]` 审计单位；
- chunk receipts、payload hashes、checkpoint、reference/partition seals 和独立复核记录。

审计抽样规则为对全部 `(cell,repeat)` 按

`SHA256("GEN_ENC_3A_YD_AUDIT_V1|partition|identity_id|cell|repeat")`

升序取前两个。development 为形成 reference 可暂存 compact normalized Gram chunk；reference 与 drift hash 持久化后立即删除该临时 Gram。raw solver chunk 在 compact payload 与 receipt 持久化后删除。所有临时目录必须位于项目内的 3A output root；禁止写 D 盘根目录。

checkpoint 以完整 chunk 为恢复单位；仅在 receipt 与全部 payload hash 精确匹配时跳过。部分 chunk 不复用。验证失败停止当前 partition，保留失败证据，不把 V 反馈到 D。

正式执行根唯一为 `outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY/formal/`。正式入口拒绝任何位于 `preflight/` 的 input、reference、compact payload 或 candidate terminal，且 `HAND_01` 必须和其余 79 identities 一样从冻结 identity/nuisance/seed/solver/W 强制重算。development 必须达到 80/80、封存 80 个 identity references、共同 W hash、candidate/family/inference 与 partition terminal 后才可打开 validation。

最终独立复核不得只信生产汇总：它至少从冻结 identity、nuisance、partition seed、solver 和 W 独立重算每个 identity/partition 的两个确定性 audit units，独立计算六距离、canonical complex Gram 与 reference drift；并从 compact arrays 独立重算 candidate tails、exact-20 reductions 和 identity-level bootstrap/permutation。生产公式模块不得作为 verifier 的公式实现来源。

## 9. science-blind preflight

监管前只允许：合同冻结、公式单测、synthetic fixture，以及 exact80 全局 ordinal 1 的 `HAND_01` development 完整单成员预飞。该身份沿用 E2 timing proxy，选择与 3A 性能无关。

预飞可核验 3,675 cells×2 repeats、147 chunks、封存 W、compact arrays、两个 sparse `Y_diff` audits、E2 retained raw audit byte reproduction、chunk hashes 和 resume；不得输出实际距离、expected shortfall、Gram 元素、family 排序或科研 terminal。预飞产物标记 `formal_eligible=false`，正式 D 必须重算。

完成上述材料后送交独立监管任务 `01a061f9-64fc-7e51-a9e6-659dd7ffe2ae` 一次审查；获批前不得启动 80-member 正式运行。

监管于 2026-09-02 返回 `APPROVE_WITH_CORRECTIONS`。本节所述唯一 inference 公式、identity-level synthetic inference fixture/test、正式/preflight 根隔离及独立复核要求为该普通修正的闭合；不改变方程、identity、阈值、拆分或证据等级。修正通过后可直接进入正式 D，无需第二次预执行审查。

## 10. 成本措辞、停止项与允许终态

成本只可表述为：80 identities 具有相同 `volume_m3=3.014899604922098e-5`、`minimum_feature_m=0.002`、`solid_load_path_m=0.002`，且落入 `DOF 12–15` 的冻结包络。不得写成完全等成本。

立即停止并升级的科研变化包括：新方程、新 identity/样本、阈值、状态/频率/nuisance 拆分、W/refit 语义、主 metric、推断单位或证据等级变化。禁止 decoder/3B、full-wave/COMSOL、打印/实测、参数搜索、final-test、commit/push/tag/release。

允许终态仅为：

- `GEN_ENC_3A_STABLE_FAMILY_SEPARATION_SUPPORTED`
- `GEN_ENC_3A_ROBUST_GEOMETRY_DIFFERENCES_PARTIAL`
- `GEN_ENC_3A_NO_STABLE_FAMILY_SEPARATION`
- `GEN_ENC_3A_INCONCLUSIVE`
- `GEN_ENC_3A_TECHNICALLY_BLOCKED`

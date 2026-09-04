# GEN-ENC-2A 数值合同提案 REV01

版本：`GEN-ENC-2A-NUMERIC-REV01-v1`

日期：2026-08-28

终态建议：`GEN_ENC_2A_REV01_READY_FOR_GUARDIAN_REVIEW`

状态：`E0_REVISION_EXECUTION_NOT_AUTHORIZED`

`execution_authorized=false`，`gen_enc_2_authorized=false`，`preflight_authorized=false`，`final_test=sealed`，`final_test_read=false`

## 增量 metadata

- **新增**：落实用户“接受推荐修订”的 primary/secondary 层级、volume terminology、descriptive throughput、20-member worst-member rule、3675-cell joint nuisance design、完整 family identities 和重算资源工作量。
- **关联**：原 GEN-ENC-2A proposal、`GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_REVIEW.json`、GEN-ENC-0R/1、active ledger 与只读设备/几何/频带权威。
- **未改变**：原 proposal 文件、旧报告/机器产物、旧科学结论、旧 P04B/R256 资格、RQ 状态和 final-test 封存。
- **证据等级**：`E0_CONTRACT_REVISION`。
- **覆盖**：`overrides=false`；本 REV01 是独立 addendum，不回写旧包。

## 1. 用户决定与 common observable

用户已接受守门建议。推荐 profile 改为 `GEN-ENC-2A-REV01-U4-COMPLEX-208P-256S-M1-v1`：四个基数端口、四设计状态、一个中央复数 disk-average 麦克风，端口顺序 `0/90/180/270°`，观察量仍为 `T_mi(f)=pbar_mic(f)/p_i_plus(f)`。

primary 固定为

`f[n]=200*2^(n/48) Hz, n=0..207`

共 208 点，精确 `200–3973.94499863515 Hz`。`E_primary` 与 `r_stable` 只用 primary。

完整 `n=0..255`、256 点、`200–7947.8899972702975 Hz` 是预注册 secondary sensitivity。primary 和 secondary 必须分别报告；secondary 不能替代、合并或改变 primary。全部网格点保留，禁止事后选频。

held-out `45/135/225/315°` 和 `0:15:345°` sampled bridge 不变；仍不是数学连续性证明。

## 2. 修订 matched-cost

P02 connected acoustic volume 改称 nominal target：

`V_target=3.014899604922098e-5 m³`。

matched target interval 为闭区间：

`[2.984750608872877e-5, 3.0450486009713192e-5] m³`。

它不是一侧 cap。U4 `x/y/z = 0.227302/0.227302/0.0122 m` 则分别是独立 upper envelope caps。

每个 family 必须使用相同确定性 mapping：三个独立 volume logits 和一个派生 logit 定义四个 local shares，总 local share 为 0.60，central share 为 0.40；各 share 乘 nominal target。每个 local budget 包含固定外端口、assigned passage 和 cavity，central budget 包含 central plenum/sensor-bore partition。未来 CAD generator 用固定 sector、确定性 bisection 和 Boolean-union audit 达到目标；无几何 root 或违反 interval/envelope/interface/minimum feature 时保留 member 并标 `COST_INELIGIBLE`，禁止重抽。

因此 normalized reduced coordinate 绝不直接称作等物理体积；只有通过上述 connected-volume/CAD mapping 和 audit 后才能进入比较。

throughput

`g(f)=||H_candidate(f)||_F²/||H_through-reference(f)||_F²`

保留为 mandatory descriptive diagnostic。原 `median>=0.1` 和 `all>=0.01` 已删除，不能决定 eligibility。中性有效性只要求 reference 在所有 required points finite、nonzero、接口和归一化相同，且 candidate diagnostic finite。不得查看响应后设 threshold。E3/E4 另行 qualification。

其余共同轴保留：`ports/states/sensors=4/4/1`；minimum feature `2.0 mm`、solid load path `1.6 mm`、quantization/tolerance `0.2 mm`、`DOF<=16`。

## 3. 用户授权的 3675-cell joint nuisance design

完整 Cartesian reference 有七轴：

| 轴 | levels |
|---|---|
| A SNR | `40,30,20 dB` |
| B common gain | `-1,-0.5,0,0.5,1 dB` |
| C sensor-independent gain | `-1,-0.5,0,0.5,1 dB` |
| D common frequency shift | `-0.5,-0.25,0,0.25,0.5%` |
| E independent manufacturing | `-2,-1,-0.5,0,0.5,1,2%` |
| F batch-correlated manufacturing | 同上 |
| G angle offset | `-5,-3,-1,0,1,3,5°` |

完整组合为 `3*5*5*5*7*7*7=128625` cells。用户授权 reduced factorial，但不授权声称等价。

REV01 使用确定性 mixed-level strength-2 设计：交叉 `u3`、`OA(25,3,5,2)=[u5,v5,u5+v5 mod5]` 和 `OA(49,3,7,2)=[u7,v7,u7+v7 mod7]`，按五个 latent indices 词典序形成 `3*25*49=3675` rows。没有设计 seed；完整表为 `nuisance_design_table.csv`。

所有边际完全平衡：3-level 每 level 1225 次；5-level 每 level 735 次；7-level 每 level 525 次。任意两轴的每个 level pair 出现次数均为 `3675/(L_i L_j)`。每 cell 权重 `1/3675`，两 repeats 各占 cell mass 的一半；缺 cell 或 repeat 即 candidate `UNAVAILABLE`。

主效应 A–G 全部预声明。二因子 estimands 是三个组 `[A]`、`[B,C,D]`、`[E,F,G]` 之间的全部 15 个 cross-group interactions。reference-coded design matrix 含 intercept 共 309 columns，静态验证 rank `309/309`。

未识别：`B:C/B:D/C:D`、`E:F/E:G/F:G` 和全部三阶以上 interactions。相对 full Cartesian 只保留 `1/35` cells，省略 124950 cells，relative cell loss `34/35≈97.143%`。未来结论只属于此用户授权 joint design，不能写成 full Cartesian robustness。

development nuisance seeds 为 `2026091001/2026091002`，validation 为 `2026092001/2026092002`，不重叠。每 partition 每 cell 两 repeats，即每 candidate/partition 7350 complete units。`W` 只用 development；validation 在全部 hashes 锁定后 single-use。本阶段只生成合同表，未生成 response。

## 4. 完整 family identities

四家族各 20 members，全部 `DOF<=16`，禁止 performance rejection/redraw/replacement。

### HAND_DESIGNED

12 DOF：三个 volume logits、四 external aperture fractions、一个 central mix aperture fraction、四 loss fractions。实际 20 行参数已写入 `family_design_tables_rev01.json`，每行唯一；generator 只能按存储顺序读取、验证并做共同 CAD mapping。

### NEAR_INDEPENDENT

12 DOF：三个 volume logits、四 external apertures、四 losses、一个 `alpha`。实际 20 行表已冻结；`alpha_r=0.03+(r-1)*0.04/19`，不得选 best alpha。reduced coupling 仍为 row-normalized `K0=(1-alpha)I+alpha*11^T/4`。

### FIXED_SEED_RANDOM_DISORDERED

13 DOF：三个 volume logits、六个 reciprocal undirected edge aperture coordinates、四 losses。20 个固定 seeds 不变。每参数用明示 SplitMix64 产生一个 open-interval uniform，随后按 frozen inverse CDF：logit `-0.12+0.24u`；edge 若 `u<0.5` 为 0，否则 `0.2+0.6(2u-1)`；loss `0.02+0.06u`。六边镜像保持 reciprocity。每 seed 只生成一次；零边、断连或弱样本不得因性能重抽。

### PHYSICS_METAMATERIAL_INSPIRED

15 DOF：三个 volume logits、四 external aperture fractions、四 reciprocal cardinal-ring aperture fractions、四 losses。所有参数名称、单位和 bounds 已冻结。master seed `2026090200` 通过 SplitMix64 驱动 parameter-specific Fisher–Yates permutations；20-stratum LHS 使用 midpoint `L+(U-L)*(perm[r]+0.5)/20`，不再添加 jitter。它明确代表 four local resonant cells + reciprocal ring interference，不得换成无结构随机矩阵。

HAND/NEAR 实际数值表和 RANDOM/PHYSICS canonical algorithms 足以在未来无科学判断实现。但本阶段不得生成 generator source 或实例，因此 `generator_source_sha256` 和四份 `instance_manifest_sha256` 仍为 null/pending-by-design；它们是 timing preflight 与 GEN-ENC-2 的硬 blocker。

## 5. 判定层级

candidate endpoint 不变：在 208-point primary 和 3675-cell user-authorized nuisance weights 下计算非插值 `Q_0.05[sigma_3(WY_diff)]`；严格 `>1.0` 且 `r_stable=3` 才 PASS。

family statistic 正式命名为：

`MINIMUM/WORST_MEMBER_ROBUSTNESS_OF_FROZEN_20_MEMBER_ENSEMBLE`。

即 20 个完整 candidate endpoints 的 minimum。只允许对这 20 个 hash-frozen members 作限定结论；不得称 population Q0.05。缺任何 member、cell 或 repeat 即 `UNAVAILABLE`。

global 仍无 scalar PASS，只允许 `BOUNDED_COMPARATIVE_RESULT / MIXED / MATCHED_COST_BLOCKED / UNAVAILABLE`。一个 candidate PASS 不建立 topology-general law。

## 6. 修订资源工作量

硬 cap 暂定保持 `20 core-hour / 10 h wall / 8 GiB aggregate peak`，但不是可行性结论。3675 cells、2 repeats 使每 candidate/partition 为 7350 units，是原 735-cell proposal 的 5 倍。

四家族完整 development+validation 为：

`4*20*2 partitions*3675*2 repeats = 1,176,000 complete units`。

若每 response 一次计算完整 256 点、development 四设计角、validation 24 sampled angles，则总约 `4,214,784,000` complex values，必须 streaming，不能整体物化。

未来单 candidate development-only timing preflight 仍未授权。它只有在全部 source/instance/interface/nuisance hashes 冻结、另获用户/guardian 授权后才能运行；只观察 wall/CPU/peak-memory/completion/numerical validity，不看 endpoint 或性能。投影或实测超过 hard cap 必须停止，不得删 family/member/axis/level/repeat/state/angle 或改变频带层级。

## 7. 治理与停止

GEN-ENC-2、timing preflight、topology/nuisance response generation、endpoint、development/validation response read、search、optimization、COMSOL、full-wave 和实体实验全部未授权。SUP-3 与 TRANS reclosure 非依赖；旧 P04B/R256 不升级；active RQ 关闭数 0；`bidirectional_discovery_established=false`。

执行计数全部为 0：topology generation、nuisance response generation、endpoint、simulation、search、optimization、training、development response read、validation read、timing preflight、COMSOL、physical experiment、legacy recomputation、final-test read。

本 REV01 完成后停止，提交 guardian review；不联系或触发守门任务。

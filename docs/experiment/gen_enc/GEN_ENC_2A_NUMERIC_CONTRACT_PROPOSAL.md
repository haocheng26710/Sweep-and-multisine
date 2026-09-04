# GEN-ENC-2A 数值合同冻结提案

版本：`GEN-ENC-2A-NUMERIC-PROPOSAL-v1`

日期：2026-08-27

终态建议：`GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_READY_FOR_USER_AND_GUARDIAN_REVIEW`

状态：`PROPOSAL_ONLY_EXECUTION_NOT_AUTHORIZED`

证据等级：`E0_CONTRACT_PROPOSAL`

`final_test=sealed`，`final_test_read=false`

## 增量 metadata

- **新增**：一套推荐数值合同、一个明确标为 sensitivity-only 的备选、逐值 authority trace、matched-cost、四家族身份、seed 分离、资源预算和判定/停止规则。
- **关联**：GEN-ENC-0R/1、其三份指定 guardian review、active research ledger、future-stage review protocol，以及只读的 U4、TRANS、INFO-TOP、Scheme 3A 权威设备/几何/频带/资源记录。
- **未改变**：所有旧报告、旧机器产物、旧设备/数据身份、旧资格、active-RQ 状态和既有科学结论。
- **证据等级**：`E0_CONTRACT_PROPOSAL`；不是 E2 性能、E3 全波或 E4 实体证据。
- **覆盖**：`overrides=false`；旧 P04B/R256 不升级，`bidirectional_discovery_established=false`。

## 1. 推荐方案

推荐 `GEN-ENC-2A-REC-U4-COMPLEX-256-M1-v1`。其目的不是复制旧 U4 性能，而是借用仓库中最完整、可追溯的 U4 接口和频带身份，为四类降阶拓扑提供同一观察合同。

| 轴 | 推荐值 | 依据/边界 |
|---|---:|---|
| 输入端口 `p` | 4 | `000/090/180/270` 基数端口；P01 已冻结次序 |
| 设计状态 | 4 | `0/90/180/270°` |
| 传感器 `m` | 1 | 中央单麦；Ø8.8 mm 复声压圆盘平均，Ø9.0 mm bore |
| 观察量 | `T_mi(f)=pbar_mic(f)/p_i_plus(f)` | 同一冻结激励参考；复数、无逐候选归一化 |
| 频率网格 | 256 点 | `f[n]=200*2^(n/48) Hz, n=0..255`；精确末点 `7947.8899972702975 Hz` |
| 复数表示 | 加权 `Re` 后 `Im` | GEN-ENC-1 的 normalized composite-trapezoidal `sqrt(w)` 嵌入 |
| held-out | `45/135/225/315°` | 不参与设计、阈值、特征或 family 选择 |
| sampled bridge | `0:15:345°` | 排除四设计角作 bridge evaluation；不是数学连续性证明 |

预处理严格为 unsmoothed complex transfer、全 256 点保留、`P_shared/P_diff` 在白化前、共同 input reference、无逐状态/候选/family 范数归一化。旧实测 magnitude 合同中的 1/12-octave dB smoothing 仅是物理比较 provenance，不能用于本推荐复数 endpoint，也不能产生相位。

唯一 sensitivity-only 备选为相同 M1 合同下的 200–3973.94499863515 Hz、208 点主频带视图。它只能检查 secondary band 依赖，不得替换 256 点 primary 结果。

## 2. matched-cost 数值轴

### 2.1 体积、包络与接口

- `V_eff cap = 3.014899604922098e-5 m³`，由 P02 `30148.99604922098 mm³ × 10^-9` 得到。
- 允许相对偏差 `±1%`，即 `[2.984750608872877e-5, 3.045048600971319e-5] m³`。超出或无法映射到未来 CAD 连通声学体积即 `COST_INELIGIBLE`。
- 包络 cap：`x=0.227302 m, y=0.227302 m, z=0.0122 m`；每轴只允许小于等于 cap。`z=(3.0+9.2) mm` 是 base bottom 到 nominal air top。
- 几何审计容差 `0.0002 m`，不允许用容差把超过 cap 的设计判成合格。
- 接口身份 `U4_CARDINAL_4PORT_CENTRAL_M1_v1`：四个 `16.0 × 9.2 mm` 外端口，顺序 `000/090/180/270`；中央 Ø9.0 mm bore；观察圆盘 Ø8.8 mm。端口/角色次序必须完全相同，尺寸制造容差 `±0.2 mm`。

这里的体积是推荐的 **未来物理映射 cap**，不是声学性能证据。降阶候选必须先给出从参数到连通声学体积/CAD 的显式映射；不能只写一个 normalized 标量后声称实体等成本。

### 2.2 频带、counts 与 throughput

- ports/states/sensors 固定 `4/4/1`，计数容差为 0。
- 频率、点数、次序、权重和预处理必须逐项相同；频率数值相对容差 `1e-12`。
- 仓库没有可用于四家族的测得 insertion-loss authority，因此不得填造测得插损。推荐仅用 E2 eligibility proxy：

`g(f)=||H_candidate(f)||_F² / ||H_through-reference(f)||_F²`。

要求全频带 median `g>=0.1` 且每个网格点 `g>=0.01`。等价的 **proxy** loss `L_proxy=-10log10(g)` 分别不超过 10 dB 和 20 dB。它不是 insertion loss 测量，也不是 passivity/部署资格；用户和 guardian 未接受前是 blocker。未来 E3/E4 只能用完全相同接口和归一化的 qualified full-wave/physical reference 映射，并须重新 preflight。

### 2.3 制造复杂度与计算成本

- 任意设计特征不得小于 `2.0 mm`（对应既有 HR 最小 neck width）；solid load path 不小于 `1.6 mm`；参数尺寸量化 `0.2 mm`；名义尺寸 tolerance `±0.2 mm`。
- 可调与 latent generator 参数全部计数，`DOF<=16`，容差 0。
- 每 family：20 个 development candidate-stage evaluations + 20 个 single-use validation evaluations，总 cap 40。
- 四 baseline families：160 次 candidate-stage evaluations；一次 evaluation 必须包含该实例全部状态、sampled angles 和完整 nuisance cells，不能按删项拆分计数。
- 每 comparison subject `4 core-hour / 2 h wall`；四 baseline 合计 `16 core-hour / 8 h serial wall`；preflight/packaging reserve `4 core-hour / 2 h`；总硬 cap `20 core-hour / 10 h wall / 8 GiB aggregate peak memory`。

未来 inverse design 不在 GEN-ENC-2 执行，但预留完全相同的 `DOF<=16`、20 个 locked validation instances 和每主体 40 次 candidate-stage evaluation cap。若真正优化需要更多预算，必须先形成新的用户决定；不能借 inverse design 身份获得更高成本。

## 3. 四家族身份与公平单位

每个家族统一为 20-member 完整 ensemble；family-level 是这 20 个成员的整体，而不是最好样本。全部版本、共同接口、matched-cost、generator source 与 instance manifest 必须在生成/读取 response 前用 canonical UTF-8 sorted-key JSON 的 lowercase SHA-256 冻结。

1. `HAND_DESIGNED`：以预声明的 HR01/HR03/HR05/HR07 四基数 motif 为起点，使用 20 行 performance-blind balanced deterministic table；12 DOF；不能用旧 U4HR 结果代替新 ensemble 成员。
2. `NEAR_INDEPENDENT`：`K0(alpha)=(1-alpha)I+alpha*11^T/4` 后 row-L2 normalization；20 个 `alpha` 等距覆盖 `[0.03,0.07]`；9 DOF。该区间来自 INFO-TOP-3 Level C structural representative，不是测得 coupling coefficient。
3. `FIXED_SEED_RANDOM_DISORDERED`：20 个固定 seed；四节点 reciprocal graph，六条无向边各由一个 spike-and-slab 坐标通过冻结 inverse CDF 生成（0 的概率为 0.5，否则 `Uniform[-0.15,0.15]`），另有四个 detuning `Uniform[-0.10,0.10]` 和四个非负 loss `Uniform[0.02,0.08]`，共 14 DOF。每 seed 只抽一次；断连、弱或难看的样本只要数值有效且成本合格就必须保留。
4. `PHYSICS_METAMATERIAL_INSPIRED`：四局部谐振器 reciprocal ring/interference network，保留 HR01/03/05/07 目标顺序；每个固定 seed 使用一行未优化 Latin-hypercube；四 resonance scales、四 external couplings、四 ring couplings、四 losses，共 16 DOF；禁止用无结构随机矩阵代称。

20-member family 的非插值 `Q_0.05` 等于最小成员。因此 family 判定保守且由单一最差成员支配，必须随结果披露；不得事后改插值、删掉技术困难成员或把一个 candidate PASS 写成 family/全局规律。

## 4. E2 nuisance 与 validation 拆分提案

development/training seeds 为 `2026091001/2026091002`；single-use validation seeds 为 `2026092001/2026092002`，互不重叠，且与 topology seeds 全局不重叠。本阶段只冻结身份，不生成数据。

为把 GEN-ENC-0R 的 nuisance 幅值显式数值化，提议每候选 735 cells：`3 SNR × 5 signed drift profiles × 7 signed manufacturing profiles × 7 angle offsets`。每个 manufacturing profile 内同时实例化 independent 与 batch-correlated component；每个非零 drift profile 内同时实例化 common 与 sensor-independent gain，并用 partition seed 决定 component realization。development 和 validation 各 2 repeats/cell，即各 1470 complete units/candidate。

这一 profile bundling 需要 guardian 明确确认它保持 GEN-ENC-0R 的 Cartesian 语义；若 guardian 认为 common/independent 或 batch/independent 必须成为额外独立轴，则本推荐资源算术失效，状态必须是 `MATCHED_COST_BLOCKED`，不能静默缩减。

validation 在全部候选、阈值、变换、family/instance manifests 和 hashes 锁定后只读一次。validation 不允许选择频率、family、topology、hyperparameter、停止轮次或成本权重；失败后不能回到 development 再把同一 validation 称为独立验证。

## 5. 资源可行性与 preflight

仓库观察到 GEN-ENC-1 的 24 个确定性 fixture 为 `0.812418 s wall / 1.90625 s CPU / 71.469 MiB peak working set`，但它只提供下尺度。TRANS 的 fine 四频点记录约 `493.4 s solve` 且单 MPH 约 `209.7 MB`，说明 full-wave 远超本地降阶任务且不属于本阶段。

因此未来执行前必须只对 **一个完整 development candidate** 做计时/内存 preflight，再按 160 次 baseline evaluation 投影。投影或实测超过任一 cap 就停止；不得删除 family、state、nuisance、angle、held-out 或 sensor 解围。实现必须按 frequency/angle/nuisance block streaming，禁止一次物化全部 candidate-cell tensor。

## 6. scientific decision hierarchy

- candidate：`PASS / NEGATIVE / UNAVAILABLE / COST_INELIGIBLE`；PASS 要求 `E_primary>1.0` 且 `r_stable=3`，仅限该实例。
- family：完整 20-member ensemble 的非插值 equal-instance `Q_0.05`；缺一个成员即 `UNAVAILABLE`，不准丢弃。
- global：只有四家族都在同一 matched-cost hash 下完整时，才可给 `BOUNDED_COMPARATIVE_RESULT / MIXED / MATCHED_COST_BLOCKED / UNAVAILABLE`；没有单一 global scalar PASS。
- bridge：`PASS / BRIDGE_FAIL / UNAVAILABLE`；只适用于冻结 15° sampled grid，不是连续数学证明。
- technical validity 与 scientific hypothesis 分轴。资源/API/hash/identity 失败不能写成科学阴性；允许如 `TECHNICAL_INVALID/NOT_TESTED`、`PASS/NEGATIVE`、`PASS/MIXED`。

任一 candidate 通过不建立 topology-general law；一个 baseline family 阴性也不自动否定 GEN-ENC。inverse design 将来若没有在 single-use validation 上严格超过最佳合格 baseline，必须保留 `NO_IMPROVEMENT`。

## 7. 直接冻结、用户确认与未来 preflight

可从既有权威直接承接：四状态/四基数端口次序、M1 中央观察角色、精确 256 点网格、复数传递和 GEN-ENC-1 embedding、held-out 与 15° bridge、1% volume comparison tolerance、final-test/authorization 边界。

最小用户确认问题为：

1. 是否接受推荐的 U4 4-port/M1/256-complex 主合同，以及 P02 connected volume/U4 envelope 的成本映射？
2. 是否接受没有实测 IL 时的 `g(f)` reduced-model proxy 和 0.1/0.01 门槛，并保持“非测得插损、非资格”的标签？
3. 是否接受 20 members/family、16 DOF、40 evaluations/subject 和 `20 core-hour/10 h/8 GiB` 总 cap，并由 guardian 审查 735-cell bundling？

未来 stage-specific 项：批准后生成 canonical hashes；单候选资源 preflight；through-reference 数值条件；未来 E3 的 mesh/passivity/reciprocity/save-reload；未来 E4 的实际打印尺寸、粗糙度、泄漏和插损测量。这些不能通过 metadata 获得资格。

## 8. 明确排除与停止

本提案不依赖 SUP-3 或 TRANS reclosure；full-wave、实体、旧 P04B/R256 重跑/升级都不在本阶段。GEN-ENC-2 未授权。final-test 保持 `sealed/read=false`。任何身份/hash 不一致、validation 泄漏、成本失败、资源超限、缺 cell/member、performance rejection、或 endpoint/state/nuisance/family/angle 变化都立即停止并上报。

执行计数：topology generation `0`、endpoint `0`、simulation `0`、search `0`、optimization `0`、training `0`、validation read `0`、COMSOL `0`、physical experiment `0`、legacy recomputation `0`、final-test read `0`。

机器权威为 `outputs/gen_enc/GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL/`。本文件完成后停止，等待用户与独立守门审查；不得自行启动 GEN-ENC-2。

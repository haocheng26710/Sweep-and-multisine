# GEN-ENC-0R 增量恢复合同

版本：`GEN-ENC-0R-CONTRACT-v1`
冻结日期：2026-08-27
合同状态：`FROZEN_CONTRACT_ONLY_EXECUTION_NOT_AUTHORIZED`
证据等级：`E0_CONTRACT_AND_PROVENANCE`
覆盖旧结论：`false`
`final_test=sealed`，`final_test_read=false`

## 0. 增量声明

- **新增内容**：一般 `H=A C B` 编码模型、共享/差分模态、稳定编码秩、四类同成本拓扑、独立验证反向设计、四状态—连续方向桥接、有限全波资格与反证门的冻结合同。
- **关联旧文件**：`docs/progress/RESEARCH_SCOPE_CONTRACTION_AUDIT.md`、`docs/governance/RESEARCH_SCOPE_GUARDIAN_CHARTER.md`、`docs/progress/TRANS1_TWO_PORT_PHYSICAL_PILOT_RESULTS.md`、`docs/experiment/INFO_TOP_RESEARCH_CONTRACT.md`、`docs/progress/INFO_TOP_4_INDEPENDENT_SYNTHESIS_AND_PHYSICAL_GATE.md` 及其权威机器摘要。
- **未改变内容**：FORMAL、SUP、V2.5、Scheme 3A、TRANS、INFO-TOP 的报告、数据、机器产物、状态和结论；旧 TRANS-2/3 映射仅为 provenance。
- **证据边界**：本文件只属于 E0 合同/治理证据，不是模拟、实验、全波或实体科学结果。
- **旧结论覆盖**：否。任何 `superseded`、`fulfilled_by`、`closed` 或 `core thesis ready` 标签均不自动关闭 active ledger 问题。

## 1. 研究问题与 primary endpoint

GEN-ENC 恢复的问题是：在相同资源成本下，编码器拓扑能否在噪声、漂移、制造误差以及状态/角度扰动下保持四状态的三维差分编码，并对未参与设计的方向保持连续、可观察的桥接；反向设计能否在独立验证上优于手工、近独立、固定种子随机/无序和物理/超材料启发基线。

冻结 primary endpoint 为

`E_primary = Q_0.05[ sigma_3(W Y_diff) ]`，

其中 `Y_diff = Y (I_4 - 1_4 1_4^T / 4)`，`W` 是只由 train/development 数据估计并冻结的噪声白化算子，`sigma_3` 是四状态差分响应的第三奇异值，`Q_0.05` 在完整预声明 nuisance 单元与独立 validation 单元上取 5% 分位数。阈值固定为 `E_primary > 1.0`（一单位白化噪声）。稳定编码秩定义为 `r_stable = #{i: Q_0.05[sigma_i(WY_diff)] > 1.0}`；四状态成功要求 `r_stable=3`。等于阈值按失败处理，不允许事后改阈值。

若数据不足以合法估计 `W`、第三奇异值或 5% 分位数，结果为 `UNAVAILABLE`，不得以分类精度、频谱差异或二状态成功替代 primary endpoint。

## 2. 一般编码模型、维度和可识别性

对每个冻结频率单元 `f`：

- `x(f) in C^p`：物理入射/端口激励；`p` 为冻结输入端口维度。
- `B(f) in C^(q x p)`：输入耦合算子，把端口激励映射为 `q` 个局部编码通道的激励。
- `C(f) in C^(q x q)`：拓扑内部传播/共享耦合算子，包含局部谐振、互耦、损耗和共享模态混合。
- `A(f) in C^(m x q)`：观测算子，把内部通道映射到 `m` 个冻结传感器读出。
- `H(f)=A(f) C(f) B(f) in C^(m x p)`，`y(f)=H(f)x(f)+epsilon(f)`。

跨频率只允许按预冻结频率网格堆叠，不得为改善结果事后选频。若只有幅度谱可见，绝对相位不可识别；若做频带去均值或增益归一化，整体增益/共同偏置也不可识别。

仅观测 `H` 时，`A/B/C` 的分解不唯一。对任意可逆内部基变换 `Q,R`，`A'=A Q^-1`、`C'=Q C R^-1`、`B'=R B` 给出相同 `H`。尺度、符号/复相位、内部基、内部通道置换均属于 gauge 等价；没有额外物理探针时不得对单个因子作唯一因果解释。状态标签的任意置换只在抽象离散任务中等价；一旦状态绑定到物理角度，循环顺序、邻接和角距离必须保持，不能任意置换。报告必须同时给出可观察量、等价类和不可识别量。

## 3. shared / differential modes

对 `K` 个状态的响应矩阵 `Y=[y_1,...,y_K]`：

- shared mode：`Y_shared = Y P_shared`，`P_shared=1_K 1_K^T/K`；
- differential modes：`Y_diff = Y P_diff`，`P_diff=I_K-P_shared`；
- 四状态的最大差分秩为 `K-1=3`。

共同增益、共同腔响应或公共漂移只能进入 shared 模态；只有在白化后的 differential 子空间中稳定存在的维度才计入编码秩。二状态最大差分秩为 1，只能作为管线/符号/投影 sanity check，绝不承接四状态或连续方向问题。

## 4. 冻结 nuisance 集与失败定义

所有家族和反向设计使用相同 nuisance 笛卡尔积；随机单元使用预登记固定种子，validation 种子在开发结束前不可见。

| nuisance | 冻结级别 | 作用边界 |
|---|---|---|
| 加性传感噪声 | SNR 40/30/20 dB | 在原始观测上施加；白化仅由 train/development 拟合 |
| 漂移 | 共同与传感器独立增益 `0/±0.5/±1.0 dB`；共同频率轴偏移 `0/±0.25/±0.5%` | 不得用 validation 重估校准 |
| 制造误差 | 连续几何/材料参数的独立及批次相关 `0/±0.5/±1/±2%` | 所有家族按同一相对规则；不可实现参数记技术失败 |
| 状态/角度扰动 | 设计角附近 `0/±1/±3/±5°` | 抽象非角状态用归一化状态坐标 `0/±0.01/±0.03/±0.05` |

科学失败包括：`E_primary<=1.0`、`r_stable<3`、任一冻结 family 的结果无法在 validation 重现、held-out 方向桥接失败、或 inverse design 不优于冻结基线。技术失败包括：求解器、网格、API、数据身份、预算或资格失败。技术失败不得写成科学假设被否定；科学失败不得通过放宽 nuisance、换频带、换阈值或 metadata 提升资格来消除。

## 5. 四状态与连续方向桥接

- 冻结设计状态：`0°/90°/180°/270°`，只允许进入 train/development。
- 冻结 held-out intermediate angles：`45°/135°/225°/315°`，不可参与特征、阈值、拓扑或超参数选择。
- 冻结 continuous-direction bridge：`0°:15°:345°` 中排除四个设计角；上述四个 45° 中间角是报告的强制子集。
- 桥接合格要求：validation 上角度邻接顺序无折叠、每个象限的局部方向导数符号与开发期冻结约定一致、环首尾连续，并报告最坏角误差/差分响应；任一强制中间角失败即 `BRIDGE_FAIL`。
- 四标签上的成功不得写成连续方向规律；二状态结果仅可验证实现管线。

## 6. 四类 topology family

每类至少一个预登记实例/ensemble，全部通过共同 `H=A C B` 接口：

1. `HAND_DESIGNED`：基于既有物理直觉的人工拓扑，参数和版本在运行前冻结。
2. `NEAR_INDEPENDENT`：交叉耦合受限、局部通道近独立的参考家族；它是参考上界候选，不预设为真值。
3. `FIXED_SEED_RANDOM_DISORDERED`：生成分布、ensemble 大小和种子在运行前冻结；不得筛选“好看的随机样本”。
4. `PHYSICS_METAMATERIAL_INSPIRED`：由明确的局部谐振、带隙/干涉或阻抗网络构造；不得以无结构随机矩阵代称。

任何家族无法满足共同成本即标记 `COST_INELIGIBLE`，不能删掉后重定义比较集。

## 7. matched-cost 合同

所有候选必须共享一份在 GEN-ENC-1 之前另行哈希冻结的 `matched_cost_manifest`。以下轴缺一或数值 cap 未填实即阻塞执行：

- 材料/有效声学体积（共同 cap；比较误差容限不超过 1%）；
- 物理端口数、设计状态数和传感器数（必须完全相同）；
- 频率带宽、采样网格与预处理（必须完全相同）；
- 几何包络与接口面（包络各维不超过共同 cap，接口完全相同）；
- 插入损耗/传输预算（共同 passband 中位数和最坏值 cap；不得只对优胜者豁免）；
- 计算预算（候选评估数、并行核时、内存和 wall-clock cap）；
- 制造分辨率与参数自由度（共同 cap，防止以隐藏复杂度换性能）。

未知货币/功耗不得伪造。没有共同可观测量或任何上述轴无法匹配时，比较停止为 `MATCHED_COST_BLOCKED`。

## 8. inverse design 与独立验证

- train/development 只含四个设计状态和 development nuisance seeds；允许拟合 `W`、选超参数和早停。
- validation 包含未见 nuisance seeds、全部 held-out intermediate angles、连续桥接网格及未参与设计的制造批次单元；在设计锁定后一次性读取。
- 禁止 validation 泄漏：不得用 validation 选择频率、阈值、family、拓扑、超参数、停止轮次或成本权重；失败后不得回到设计阶段再报告同一 validation 为独立验证。
- inverse design 与每个基线共享相同 matched-cost cap 和总计算预算。主比较使用 `E_primary`；并列时依次比较最坏中间角差分裕度、插入损耗、几何复杂度，顺序不得更改。
- 允许且必须保留 `NO_IMPROVEMENT`：若 inverse design 未在 validation 上严格超过最佳合格基线，结论就是无改善；不得换分类器或事后子集挽救。

## 9. 有限全波资格与 anchors

旧 P04B/R256 只能证明当前模型资格受限，不能直接或通过 metadata 升级为新全波资格。未来全波必须在新冻结合同下依次通过：输入/几何身份、解析或简单参考解、网格收敛、能量/被动性/互易性残差、保存—重载一致性、共同可观察量与资源预算。任一项失败均为 `TECHNICAL_INVALID`，不裁决科学假设。

全部资格门通过并取得未来明确批准后，才允许 2–3 个判别性 anchors。anchor 身份必须在求解前根据冻结规则确定：覆盖最佳非优化基线、固定随机/无序基线，以及仅在设计已锁定时覆盖 inverse-design 候选；若 inverse design 为 `NO_IMPROVEMENT`，第三 anchor 改为物理启发家族。最多 3 个，不准扩成扫描；不得重跑旧 P04B/R256 精确预测。

## 10. 证据、主张与反证

证据等级：`E0` 合同/provenance；`E1` 解析可识别性；`E2` 降阶/合成；`E3` 经资格门的有限全波；`E4` 独立实体。低等级不能提升为高等级事实。每个结论同时记录 `technical_validity` 与 `scientific_hypothesis`，允许组合如 `TECHNICAL_INVALID / NOT_TESTED`、`PASS / NEGATIVE`。

核心反证门见机器文件 `falsification_gates.json`。任何 family 顺序、稳定秩、连续桥接或 inverse-design 优势若失败，必须原样保留。分类器只允许作预声明的次要读出，不能替代 primary endpoint；禁止事后选频、调阈值或优化分类器。

## 11. 阶段依赖、停止与资源边界

GEN-ENC-0R 只冻结合同。后继阶段必须按 `dependency_and_parallelism.json` 获取单独授权；本合同不启动 GEN-ENC-1。数学可识别性与成本清单准备可并行，四类 family 的实现可在共同接口冻结后并行；validation 封存、inverse design 锁定、全波资格和 anchors 必须串行。

立即停止条件：需要 final-test；身份/hash 不一致；共同成本不可建立；validation 泄漏；需要扩大搜索或修改 primary endpoint；需要超过已批准计算/内存/wall-clock；技术资格失败；或结果需要用户决定才能改变科学范围。资源不足上报主控，不得静默删除 family、nuisance、状态或 bridge。

SUP-3 和 TRANS 独立重闭合不属于执行依赖；仅在未来出现明确判别需求并另行批准时考虑。

## 12. Active ledger 承接与明确排除

本合同直接承接 RQ-01、RQ-02、RQ-04、RQ-05、RQ-08、RQ-09、RQ-10、RQ-11；对 RQ-03、RQ-06、RQ-07、RQ-12 仅记录边界，不宣称关闭。任何阶段结果都不得静默关闭其他 active question；关闭只能按 ledger 指定证据或明确用户决定。

明确排除：旧 P04B/R256 精确预测重跑、完整旧 P05–P10、更多 P04 体积重复、FORMAL 24 份缺失补采、事后选频/调阈值/优化分类器、解封 final-test、SUP-3、TRANS 独立重闭合，以及任何未批准仿真/参数搜索/训练/实验/COMSOL。

## 13. 发现入口与不可侵入性

机器关系入口为 `outputs/gen_enc/GEN_ENC_0R_RESTORATION_CONTRACT/relates_to.json`。本轮没有向旧 TRANS/INFO-TOP 目录写回 sidecar：授权要求只写新 GEN-ENC/补充路径，且共享工作树已有并发未提交产物；为避免侵入旧权威目录，采用统一、机器可读的单向补充索引。此限制不改变旧文件，也不制造双向发现已建立的假象。

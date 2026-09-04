# GEN-ENC-1 可识别性与估计器预执行合同

版本：`GEN-ENC-1-PHASE-A-v1`
冻结日期：2026-08-27
终态：`GEN_ENC_1_PHASE_A_CONTRACT_READY_FOR_GUARDIAN_REVIEW`
`execution_authorized=false`，证据等级：`E0_CONTRACT_AND_E1_METHOD_SPEC_ONLY`
覆盖旧结论：`false`；`final_test=sealed`，`final_test_read=false`

## 1. 增量、边界与承接

- **新增内容**：仅冻结 `H=A C B` 的可观察等价类、gauge/invariance、可识别/不可识别命题；稳定编码秩估计器与确定性合成单元测试规范；continuous bridge 的可计算规范；numeric matched-cost manifest 与 family identity schema。
- **关联旧文件**：GEN-ENC-0R 合同、两次守门审查、范围章程/账本/协议，以及 `relates_to.json` 中的 TRANS 与 INFO-TOP 权威摘要。
- **未改变内容**：FORMAL、SUP、V2.5、Scheme 3A、TRANS、INFO-TOP 和 GEN-ENC-0R 的报告、机器产物、状态与结论。
- **证据边界**：本阶段没有 E2 拓扑性能结论；没有数值 endpoint、模拟、参数搜索、优化、分类器训练、实验、COMSOL、旧结果重算或实例生成。
- **旧结论覆盖**：否。`bidirectional_discovery_established=false`；旧报告只读，采用新 GEN-ENC 增量路径。

GEN-ENC-0R 守门者的七项 binding disclosures 全部按本合同和同目录机器规范继续生效。任何未填 numeric cap、family identity 或 bridge 阈值均阻塞 GEN-ENC-2，不得猜测或以 metadata 提升资格。

## 2. E1 可识别性 claim boundary

每个冻结频率点上，`H(f)=A(f)C(f)B(f)`，`y(f)=H(f)x(f)+epsilon(f)`。在冻结输入与输出坐标、预处理和观测协议下，两个实现当且仅当对全部冻结输入有相同 `H(f)` 时属于同一可观察等价类。对任意可逆 `Q,R`：

`A'=A Q^-1, C'=Q C R^-1, B'=R B`

保持 `H` 不变。内部尺度、符号/复相位、基变换和通道置换属于 gauge；无额外内部探针时，`A/B/C` 唯一分解、单模块因果增量和指派的降阶耦合系数不可识别。可识别对象仅限冻结观测协议下的 `H`、由 `H` 构造的 shared/differential 响应、其 Gram/奇异值/稳定秩及预注册 bridge 函数。抽象标签可置换；物理角度必须保持循环顺序、邻接与角距离。

这些是 E1 数学/方法命题，不允许写成 E2 性能、E3 全波机制、E4 实体效果或拓扑普遍规律。

## 3. `Y` 的冻结构造

频域约定为 `z(f)=sum_t z(t) exp(-i 2 pi f t)`；相位只相对于同一冻结激励时钟。每个候选、nuisance 单元和重复单位产生四列状态响应，列顺序固定为 `0,90,180,270` 度。特征顺序固定为频率升序，其内按端口、传感器升序。

实际频带端点、步长和点数必须来自 `matched_cost_manifest.json`；当前缺乏无争议科学依据，均标记 `REQUIRES_USER_OR_STAGE_SPECIFIC_VALUE`，因此任何数值执行被阻塞。填实后必须在读取 development/validation 前哈希冻结，所有点完整保留，禁止事后选频。权重固定为频率网格的归一化复合梯形权重，非均匀网格亦不得重选；权重和为 1。

复数响应采用实嵌入：对每个加权复特征 `sqrt(w_j) z_j`，依次堆叠 `Re` 后 `Im`。不采用幅值/相位嵌入，不作逐状态、逐候选或逐 family 范数归一化；只允许共同输入参考形成冻结的传递函数。任何 train-derived calibration 只可作为对全部划分相同的固定线性变换，并记入 manifest/hash。

`P_shared=1_4 1_4^T/4`，`P_diff=I_4-P_shared`；`Y_shared=Y P_shared`，`Y_diff=Y P_diff`。投影在白化前执行。四状态差分秩上限为 3；二状态最多秩 1，仅作实现 sanity check。

## 4. `W`、稳定秩与分位数

`W` 只由 train/development 中预注册的独立重复残差构造，validation 不得参与。共同 `W` 跨候选和 family 使用：每个完整 nuisance cell 先在同一 candidate/state/cell 内去除重复均值，再按 nuisance cell 等权、cell 内残差等权汇总实嵌入协方差。同步作用于四状态的共同漂移先由 `P_diff` 消去；传感器独立漂移和未消去噪声保留在残差中。

协方差估计固定为 OAS 向同性 shrinkage target `tau I`，shrinkage 系数按 OAS 闭式规则确定并裁剪到 `[0,1]`。特征尺度、样本顺序和浮点精度固定；特征不足、非有限值、无法形成至少两个独立残差或协方差/特征身份不一致时为 `UNAVAILABLE`。秩亏不删除特征；对特征分解后的特征值使用纯数值 floor `max(lambda_i, eps_machine*d*lambda_max)`，再取对称逆平方根。复数白化只通过上述实嵌入的实对称正定协方差完成，不混用未声明的 proper-complex 假设。

候选每个完整 evaluation unit 计算 `sigma_i(W Y_diff)`。nuisance cells 等权，每 cell 内 evaluation units 等权。`Q_0.05` 固定为加权经验逆 CDF：最小的 `t` 使累计权重 `>=0.05`，不插值；因此总有效单位少于 20 时自然退化为最小观测值。缺失任何预注册 cell、unit 不完整、`W` 不可得、第三奇异值不可得或权重不能归一时，endpoint 为 `UNAVAILABLE`，不得补值或替代。

`E_primary=Q_0.05[sigma_3(WY_diff)]`；`r_stable=#{i:Q_0.05[sigma_i(WY_diff)]>1.0}`。四状态通过要求 `E_primary>1.0` 且 `r_stable=3`；等于 1.0 为失败。`1.0` 是白化噪声单位的工程门槛，不是显著性、分类准确率或部署性能。

## 5. 判定层级

- candidate-level：只裁决一个冻结实例；可为 `PASS/NEGATIVE/UNAVAILABLE/COST_INELIGIBLE`。
- family-level：只按冻结 ensemble 聚合规则裁决该 family；单一候选通过或失败都不能替代 family 判定。
- global-level：只有四个强制 family 均满足 matched-cost 且按预注册 ensemble 规则完成后，才能作限定于这些实例/ensemble 的比较；任一 baseline 失败不自动否定 GEN-ENC，单一候选通过不建立拓扑普遍规律。

技术状态与科学状态独立记录。技术失败只产生 `TECHNICAL_INVALID / NOT_TESTED` 等组合，不得写成科学否定。

## 6. continuous bridge

只冻结定义和合成单测，不读取未来 development/validation。对连续网格的白化差分列 `z(theta)`，用冻结物理角标签构造第一圆谐波基 `a=sum z(theta)cos(theta)`、`b=sum z(theta)sin(theta)`；以其 2x2 Gram 矩阵的逆得到每点双坐标并用 `atan2` 得到响应角。Gram 不可逆即 `UNAVAILABLE`。

angular-order folding：按物理角递增解缠后，每个相邻角增量（含 345 到 0 的环回）必须严格为正且小于 180 度。local derivative orientation：中心差分与冻结理想切向量的 Gram 内积必须严格为正。differential margin：每点相对 shared centroid 的白化范数必须严格大于 1.0。circular continuity：345 到 0 的白化弦长不得大于所有非环回相邻 15 度弦长的最大值。四个强制中间角必须全部通过；任一不可估计为 `UNAVAILABLE`，任一条件失败为 `BRIDGE_FAIL`。

这些量只依赖冻结观测响应、物理角标签和白化 Gram 几何，对内部 `A/C/B` gauge 不变。确定性合成测试及预期结果见 `continuous_bridge_spec.json`，本阶段不执行测试。

## 7. matched cost 与 family identity

`matched_cost_manifest.json` 冻结材料/有效声学体积、端口/状态/传感器、频带/网格、几何包络/接口、插损/传输、计算预算、制造分辨率/自由度的单位、cap、容差和阻塞状态。仅四个设计状态、15 度连续网格、四个 held-out 强制角和体积相对比较容差 1% 可由旧合同直接填实；其余真实数值不得猜测。

四 family 的 instance/ensemble identity schema 冻结 counts、生成分布、固定 seeds、参数自由度、版本与哈希字段。本阶段不生成实例；未填字段使 GEN-ENC-2 保持阻塞。

## 8. 依赖、资源、反证与停止

本阶段不依赖 SUP-3 或 TRANS 重闭合；全波和物理工作不在范围内。GEN-ENC-2 仅在本合同经独立守门批准、所有 numeric caps 与 family identities 填实并哈希冻结、validation 仍封存后方可另行授权。不得自行启动。

立即停止：final-test 请求/读取、身份/hash 不一致、validation 泄漏、成本不可匹配、任何 endpoint/四状态/nuisance/family/held-out/evidence 边界变化、资源 cap 缺失或超出、或需要用户改变科学范围。

本阶段数值端点计算、模拟、搜索、训练、实验、COMSOL、旧结果重算和 topology instance 生成均为 0。合同完成即停止，等待上级主控提交 guardian review。

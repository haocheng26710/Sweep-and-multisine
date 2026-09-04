# GEN-ENC-2A 数值合同冻结提案进展

日期：2026-08-27

终态建议：`GEN_ENC_2A_NUMERIC_CONTRACT_PROPOSAL_READY_FOR_USER_AND_GUARDIAN_REVIEW`

状态：`PROPOSAL_ONLY_EXECUTION_NOT_AUTHORIZED`

证据：`E0_CONTRACT_PROPOSAL`

## 增量 metadata

- **新增**：完成数值合同建议及机器提案包，供用户和 guardian 决策。
- **关联**：GEN-ENC-0R/1、ledger/protocol/reviews、U4/TRANS/INFO-TOP/Scheme 3A 只读权威记录。
- **未改变**：旧文件、旧结论、旧资格和数据状态。
- **证据等级**：`E0_CONTRACT_PROPOSAL`。
- **覆盖**：`overrides=false`。

## 推荐核心

推荐同一 `4 ports / 4 states / 1 central sensor` 复传递合同，使用 `f[n]=200*2^(n/48), n=0..255` 的 256 点网格。held-out 保持 `45/135/225/315°`，bridge 保持 `0:15:345°` sampled grid。

matched-cost 推荐：`V_eff<=3.014899604922098e-5 m³` 且相对匹配 `±1%`；包络 `0.227302 × 0.227302 × 0.0122 m`；四个 `16×9.2 mm` 基数端口、中央 Ø9.0 mm bore/Ø8.8 mm observable；minimum feature `2.0 mm`、load path `1.6 mm`、quantization/tolerance `0.2 mm`、`DOF<=16`。

仓库没有可用的四家族测得插损，因此只提议 through-reference normalized proxy `g(f)`：median `>=0.1`、每点 `>=0.01`；它不是测得 insertion loss。

四强制 family 均为 20-member ensemble。random/disordered 用 20 个预登记 seeds，一次抽样、禁止 performance rejection；其他家族也以完整 20 members 作公平判定单位。family 非插值 5% 分位在 `n=20` 等于 minimum，必须披露为 conservative/single-instance dominated。

资源 cap：每 family/subject 40 candidate-stage evaluations、4 core-hour、2 h wall；四 baseline 合计 160 evaluations、16 core-hour、8 h serial；含 reserve 的硬上限为 20 core-hour、10 h wall、8 GiB aggregate peak memory。未来先做一个完整 candidate preflight；超限即停止，不能删 family/state/nuisance/angle。

## 尚需确认

用户最小决定为：接受 U4-M1-256 主合同及体积/包络映射；接受明确非测量的 throughput proxy；接受 20-member/16-DOF/资源 cap。guardian 另需确认 735 nuisance-cell profile bundling 是否保持 GEN-ENC-0R Cartesian 语义。

generator/instance hashes、through-reference conditioning、未来 full-wave qualification 和实体尺寸/泄漏/插损都属于后续 preflight，不在本阶段制造证据。

## 边界与零计数

旧 P04B/R256 不升级；SUP-3/TRANS reclosure 非依赖；full-wave/实体不在范围；GEN-ENC-2 未授权；`bidirectional_discovery_established=false`；`final_test=sealed`、`final_test_read=false`。

topology generation、endpoint、simulation、search、optimization、training、validation read、COMSOL、physical experiment、legacy recomputation、final-test read 全部为 `0`。本阶段在提交用户/guardian review 后停止。

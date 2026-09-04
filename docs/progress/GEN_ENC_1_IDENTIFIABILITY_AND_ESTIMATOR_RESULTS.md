# GEN-ENC-1 可识别性与估计器 PHASE B 结果

日期：2026-08-27
终态：`GEN_ENC_1_E1_IMPLEMENTATION_PASS`
证据等级：`E1_IMPLEMENTATION_CONSISTENCY_ONLY`
覆盖旧结论：`false`
`gen_enc_2_authorized=false`，`final_test=sealed`，`final_test_read=false`

## 增量声明

- **新增内容**：完成 `H=A C B` 可观察等价、gauge、不变量、shared/differential 秩上限与不可识别性的 E1 推导；实现冻结的 `Y/W`、OAS、eigenvalue floor、非插值 `Q_0.05`、stable rank、三层判定和 sampled bridge；运行 24 项普通本地确定性合成技术单测。
- **关联旧文件**：PHASE A 合同包及 `GEN_ENC_1_PHASE_A_CONTRACT_REVIEW.json`。
- **未改变内容**：所有旧报告、旧机器产物、真实/旧数据、matched-cost 未知 caps、family identities、active RQ 状态与既有科学结论。
- **证据边界**：合成计算只验证冻结 E1 实现的一致性，不是 E2 topology performance、科学验证、模拟、全波或实体证据。
- **覆盖旧结论**：否；`bidirectional_discovery_established=false`。

## E1 推导结论

在冻结输入/输出坐标和观测协议下，两个实现对所有输入具有相同输出，当且仅当其可观察算子 `H` 相同。若 `Q,R` 可逆，则

`(A Q^-1)(Q C R^-1)(R B)=A C B=H`。

因此内部尺度、相位/符号、基与通道置换至少形成一族不可区分的 gauge orbit。没有额外内部 probes、已知稀疏性、规范化、结构方程或参数约束时，仅由 `H` 不能唯一恢复 `A/C/B`，也不能唯一归因单模块增量或把降阶参数解释成物理耦合常数。

`P_shared=11^T/K` 与 `P_diff=I-P_shared` 均为对称幂等投影；`ker(P_diff)=span{1}`，所以 `rank(P_diff)=K-1`，且 `rank(Y P_diff)<=K-1`。四状态差分秩上限为 3。任何共同状态分量 `d 1^T` 满足 `(d 1^T)P_diff=0`，故不会贡献 differential rank。

这些结论只属于 E1 数学与实现边界，不是 topology 性能或物理机制结果。

## 实现与测试

新模块位于 `src/acoustic_encoder/gen_enc/`，无项目数据加载器、拓扑生成器、搜索或模拟入口。`fit_whitener` 的函数签名仅接受 train、development 与 required nuisance cells，不接受 validation 参数。

复现命令：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests/test_gen_enc_1_identifiability_and_estimator.py -q
```

结果：24/24 passed。最后一次资源记录：pytest 内部测试耗时 0.22 s；端到端 wall-clock 0.812418 s；进程 CPU 1.90625 s；轮询观测峰值 working set 71.469 MiB。资源属于普通本地确定性 fixture 量级，没有 topology instance 或性能扫描。

覆盖项包括 gauge 等价、shared removal、四状态秩 3 上限、endpoint pass/fail/equality failure、少于 20 个等权单位的保守最小值、missing/nonfinite/W unavailable、validation exclusion、nuisance-cell 等权、OAS/eigen floor、candidate/family/global 类型边界，以及 bridge 的 pass/fold/derivative/margin/wrap/Gram singular。

少于 20 个等权 evaluation units 时，冻结的 `Q_0.05` 等于样本最小值；实现原样保留，并明确标记 `CONSERVATIVE_AND_SINGLE_UNIT_DOMINATED_Q_0.05_EQUALS_MINIMUM`。

## sampled bridge 边界

bridge 只是在固定 `0:15:345` 网格上的预注册 sampled bridge，包含 45/135/225/315 度四个 mandatory held-out angles。测试通过不构成数学连续区间上的证明，也不构成对未见物理实体或部署场景的泛化。

## 未执行与后继阻塞

真实/旧数据 endpoint、development/validation/final-test 读取、topology instance/ensemble 生成、family 比较、参数搜索、优化、分类器、模拟、COMSOL、全波、实验及旧结果重算均未执行。

GEN-ENC-2 继续阻塞：numeric matched-cost caps 与四 family identities 仍为 `REQUIRES_USER_OR_STAGE_SPECIFIC_VALUE`，不得猜测。本阶段完成后停止，等待 RESULT_SEAL_REVIEW；不自行启动 GEN-ENC-2。

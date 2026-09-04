# GEN-ENC-2 development-only timing-preflight 合同冻结 01

版本：`GEN-ENC-2-TIMING-PREFLIGHT-CONTRACT-FREEZE-01-v1`  
日期：2026-08-29  
终态：`DRAFT_FAIL_CLOSED_REPRESENTATIVE_AND_COMMAND_AUTHORITY_GAPS`  
证据：`E0_TIMING_PREFLIGHT_CONTRACT_ONLY`

`execution_authorized=false`，`timing_preflight_authorized=false`，`gen_enc_2_e2_authorized=false`，`run_id=null`，`final_test_read=false`。

## 1. 增量边界

本包只新增 GEN-ENC-2 timing-preflight 的合同、输入/来源/schema/命令绑定、未来结果 schema 和 DRAFT zero state。它不修改旧报告，不执行 timing、solver 或科学 forward response，不读取或保存 response/endpoint，不生成 run-id，不启动 GEN-ENC-2 E2。

强制绑定：Final92 guardian terminal review `a3d7d428...30e7e`、Final92 result `SHA256SUMS.txt` `47a65f02...20a2`、Final92 independent report `d721df6...b77d8`、minimum governance override `31a0dac1...f835`。完整路径与哈希见 `source_manifest.json`。

## 2. 权威缺口与 fail-closed 冻结

权威资源合同只规定未来 preflight 为“one development-side candidate only”，但没有唯一指定 family/member/path/hash，也没有给出不依赖结果的唯一选择规则。因此本包没有自行从 Final92 80 members 中挑代表：`representative_set.frozen=false`，缺口为 `TP-GAP-01`。

现有冻结材料也没有 GEN-ENC-2 response/timing solver 的 exact entrypoint、命令、输入向量和 runtime binding。2C 命令只生成/验证静态 identity，明确没有 timing/response 能力，不能冒充 GEN-ENC-2 forward command。因此 `timing_preflight=null`、`solver_entrypoint=null`，缺口为 `TP-GAP-02`。

两个缺口必须由新的 additive、guardian-approved authority record 关闭。此前只允许 no-run JSON/schema/hash 校验。

## 3. science-blind 可观测量

未来另获批准后，只能记录：wall time、CPU time/利用率、aggregate peak memory、completion status、numerical validity、convergence、NaN/Inf、solver exit code、license availability。

严禁读取、记录、比较或派生：endpoint 值、frequency/candidate response、family performance、跨家族比较、ranking/selection、matched-cost 结果、held-out/validation/final-test response。不得据 preflight 重选 family/member、删状态/角度/频率/轴/level/cell/repeat、改阈值或频带。preflight 过程中不得保留科学 forward-response payload。

## 4. 冻结 workload、资源判定与投影

未来单代表 development work unit 固定为：3675 nuisance cells × 2 repeats、四设计状态 `0/90/180/270°`、一次计算完整 `n=0..255` 256 点；primary `n=0..207` 只作为未读取的合同层级。validation、held-out `45/135/225/315°` 与 `0:15:345°` sampled bridge 保持封存且不访问。

hard stops 原样为：`20 core-hour / 10 wall-hour / 8 GiB aggregate peak`，只表示停止线，不是可行性结论。单 development candidate 有 7,526,400 complex-value locations；完整冻结 future workload 为 4,214,784,000，对应保守 multiplier `560`。CPU 与 serial wall 投影使用 560；single-process 固定 block 下的 aggregate peak memory 使用实测 peak。任一实测或投影超线、或 license unavailable，结果为 `RESOURCE_BLOCKED`；nonzero solver exit（非 license）、不收敛、数值无效或 NaN/Inf 为 `NUMERICALLY_BLOCKED`；只有全 work unit 完成、全部数值门通过、实测与投影均未超线，才可为 `FEASIBLE`。

`FEASIBLE` 只说明资源/数值 preflight，不授权 GEN-ENC-2 E2。其后仍须单独提交 GEN-ENC-2 preexecution 合同并取得 guardian 批准。

## 5. 分块与断点续跑

分块只改变调度。顺序固定为 family → member `01..20` → development before validation → frozen angle → nuisance cell `0000..3674` → repeat `1..2` → state `0/90/180/270` → ascending contiguous frequency block。当前 preflight 只触及获批代表的 development 子序列。

checkpoint 只允许保存 bound hashes、最后完成的 canonical key、完成计数、资源计数、numerical/convergence/NaN-Inf/solver-exit/license 状态；禁止 response、endpoint、metric、score、ranking、selection 或 family performance。恢复时要求输入/命令/schema hash 完全相同，从精确下一个 canonical key 继续；不得 skip、replace、redraw 或 reorder。

任何分块策略都不能改变未来完整四家族 80 members、development+single-use validation、四状态、held-out 与 sampled bridge、3675 cells、2 repeats、256 computed points、208 primary points、指标或证据义务。

## 6. 停止与审查顺序

当前顺序固定为：本合同 freeze → 中间主控验收 → Advisor B → guardian preexecution review → 两个 authority gap 关闭并重新 hash-bind → 另行明确 timing execution release → science-blind preflight/result seal → 单独 GEN-ENC-2 preexecution contract/guardian approval。任何一步不得由 preflight PASS 跳过。

本轮已停止于合同 zero state；未 commit/push/tag。

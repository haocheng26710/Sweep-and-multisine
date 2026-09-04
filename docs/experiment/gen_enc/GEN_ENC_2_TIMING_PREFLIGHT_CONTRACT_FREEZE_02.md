# GEN-ENC-2 development-only timing-preflight CONTRACT-FREEZE-02

状态：`READY_FOR_ADVISOR_AND_GUARDIAN_REVIEW`；不是执行许可。`timing=false`、`solver=false`、`E2=false`、`run_id=null`、`final_test_read=false`。

## 权威冲突与拟议绑定

较早 guardian review（SHA-256 `30a482adaafb2215396414207d4a3534fe344bb3baaa109d32d65e937f8db20e`）按 max static DOF 选择 `PHYSICS_01`。后到顶层裁决拟以 Final92 全局冻结顺序第一项 `HAND_01` supersede：global ordinal `1`，file SHA-256 `313c55e1517b9ef62c7e98918b7544cd6ad45836a21e82cddf59b4b571100857`，member SHA-256 `8180161b8f8611050a57adce28fca45fdb0e0fd70050d73c8ceb1798b6bb62a0`。

本包只把后到规则冻结为拟议 additive authority；guardian 必须复审并以独立授权记录绑定本包四个 exact hash 后才能执行。HAND_01 仅是 development resource proxy，不代表典型、极值、科学表现或全 80；失败后禁止换样。

## 冻结 compute core

模型 `PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1` 位于 `src/acoustic_encoder/gen_enc/forward_acoustic_network.py`。固定四个局部腔与一个中央共享腔/麦克风、四条局部到中央支路、四端口单位体积速度源。`C=V/(rho*c^2)`，`rho=1.2041 kg/m3`，`c=343 m/s`；`Z=R+jωM`。中央复压力只在内存中存在，由 timing harness 立即丢弃，只保留 finite/passive/reciprocal/solvable/NaN-Inf flags。

既有 authority 没有唯一给出 branch loss/section 数值映射，因此 `reduced_model_assumptions.json` 冻结一个未拟合、dimensionally valid、family-common、response-blind 的唯一公式。它是新增 E2 reduced-model assumption，不是科学验证；不得调参、增删边、重排或耦合优化。

## 输入、命令与资源规则

CLI 为 `scripts/run_gen_enc_2_timing_preflight.py timing-preflight`，exact argv 在 `command_manifest.json`。它逐项绑定 HAND_01、Final92、2A profile/matched-cost/frequency/nuisance CSV/nuisance contract/seed split、contract/source/command/schema、guardian authorization、output root、checkpoint/resume。运行时冻结为 `D:/Anaconda3/python.exe`（Python 3.12.4、SHA-256 `4e5a83fdcd12bcb9ae4dc98c5405effe35dc5ac10d89982c6a6a3646493f88a`）、numpy 1.26.4、psutil 5.9.0。

工作量不变：3675 cells × 2 repeats = 7350 units；states `0/90/180/270`；`f[n]=200*2^(n/48)`、n=0..255；每 unit 八个连续 32-frequency blocks；每 25 units checkpoint。分块和 resume 只改调度，不改成员、cell、repeat、state、frequency、metric 或证据。

投影为 observed CPU/wall × 560；hard stops 为 20 CPU core-hours、10 serial wall-hours、8 GiB aggregate peak memory。只允许 `FEASIBLE`、`RESOURCE_BLOCKED` 或 `NUMERICALLY_BLOCKED`。FEASIBLE 仅说明 HAND_01 proxy 的 560× serial projection 在阈值内，不保证全 80/四家族，也不授权 E2；之后仍需单独 GEN-ENC-2 preexecution contract。

## Science-blind 边界与当前停止点

可持久化项仅为 wall/CPU/utilization/aggregate peak memory、completion/checkpoint、numerical validity/convergence/NaN-Inf/solver exit、license、hash、verdict。pressure、H/A/B/C、frequency response、endpoint、score、family performance、ranking、matched-cost result、validation、held-out、final-test 禁止持久化、打印、返回或检查；response artifacts 必须为零。

本轮仅做 TDD unit/CLI/schema/fail-close 测试，未执行 formal timing 或 solver，未生成 run-id。停止于 Advisor B 与 guardian 复审。

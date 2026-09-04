# GEN-ENC-2 development-only timing-preflight CONTRACT-FREEZE-03

状态：`READY_FOR_ADVISOR_AND_ONE_FINAL_GUARDIAN_REVIEW`，不是执行授权。绑定 guardian REVISE review SHA-256 `a29fea41c5fde155be0898dc0d8e552d5d2f2942e081a77c19adf59c10dd4835`。HAND_01/global-first 已正式 supersede PHYSICS_01/max-DOF，不再是开放冲突；HAND_01 失败后不得换样。

## 四家族 common core

同一 `PASSIVE_RECIPROCAL_5_NODE_LUMPED_ACOUSTIC_NETWORK_V1` 现在确定性支持 `HAND_DESIGNED`、`NEAR_INDEPENDENT`、`FIXED_SEED_RANDOM_DISORDERED`、`PHYSICS_METAMATERIAL_INSPIRED`。节点数仍为 5，支路仍为四个 local-to-central branches，`C/M/R/Z` 方程与 solve 不变。

四家族都先将冻结 family coupling coordinates 映射成四个 branch shared-aperture coordinates，再走同一 element mapping。HAND 使用 `central_mix`；NEAR 使用冻结的 normalized `shared_alpha`；RANDOM 每个 local 使用三个 incident undirected edges 的均值，exact zero 精确贡献零；PHYSICS 使用两个 incident reciprocal ring coordinates 的均值。全部输入仅来自 Final92 identity 与冻结 2A parameter/CAD authority；缺字段或越界时精确 fail-close，无 fallback、调参、结果读取或成员替换。

## 完整 port workload 与 560×

代表工作量是 `7350 units × 4 states × 4 ports × 256 frequencies = 30,105,600` central complex values。formal obligations 是 `4 families × 20 members × (4 development + 24 validation angles) × 7350 × 4 ports × 256 = 16,859,136,000` values。因此：

`16,859,136,000 / 30,105,600 = (4×20×28×4)/(1×4×4) = 560`。

port=4 同时乘在分子与分母，所以只在 ratio 中相消，不能从绝对 workload 删除。hard stops 保持 20 CPU core-hours、10 serial wall-hours、8 GiB aggregate peak memory；32-frequency blocks 与 resume 只改调度。

## Import closure 与 publication gate

core 的 transitive project dependency `src/acoustic_encoder/gen_enc/generator/prng.py` 已以 path/hash/bytes 加入 source/runtime manifests。import closure 同时覆盖 CLI→core→prng，未解析 project imports 必须为零。

正式终态在原子写入前必须由冻结的 Draft 2020-12 schema 实际验证；validator 为 `jsonschema 4.19.2`。required/type/enum/additionalProperties 与 FEASIBLE conditional 任一失败都不得写终态。

## 永久 inference ceiling

HAND_01 preflight 最多判断“该代理在该冻结 runtime/hard-stops 下的 development-side timing/numerical feasibility”。它不证明其它家族、全部 80、worst-case 或 full E2 feasibility。其它 family branch 在未来 E2 中仍受相同 hard stops 约束并可返回 `RESOURCE_BLOCKED`。即使 HAND_01=`FEASIBLE` 也不授权 E2，仍需独立 GEN-ENC-2 preexecution contract。

本轮仅运行 10 项 synthetic/CLI/schema no-run tests。timing=0、solver=0、formal units=0、run-id=0、`final_test_read=false`。

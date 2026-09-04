# GEN-ENC-3A Robust Encoding Geometry Extension 结果

日期：2026-09-02  
当前状态：`GEN_ENC_3A_NO_STABLE_FAMILY_SEPARATION`  
证据等级：`E2_REDUCED_MODEL`  
正式 D/V：`80/80 DEVELOPMENT SEALED + 80/80 SINGLE-USE VALIDATION SEALED`  
`final_test_read=false`

## 1. 结论先行

GEN-ENC-3A 已完成预注册的 exact80 development、每 identity reference 封存、single-use validation 与独立复核。允许终态为 `GEN_ENC_3A_NO_STABLE_FAMILY_SEPARATION`，`recommend_3b=false`。

原因不是技术失败。D/V 的全部 80 identities、E2 feasibility gate、20,000 次 identity bootstrap 与 100,000 次 12-stat max-|T| permutation 均有效；独立 verifier 对 D/V 各 80 candidates、各 160 个固定 audit units、candidate tails、exact-20 reductions 和两套推断全部复算通过。科学上，margin 的 D/V exact-20 worst-member leader 均为 `FIXED_SEED_RANDOM_DISORDERED`，drift 的 D/V leader 均为 `PHYSICS_METAMATERIAL_INSPIRED`，没有同一个联合 leader。validation 的 12 个 FWER-adjusted p-value 全部大于 0.05（最小值 `0.7074729252707473`），全部 bootstrap 95% CI 跨 0。

因此数据不支持稳定家族分离，不进入 decoder/3B。该结论仅限冻结五节点降阶模型与既定 nuisance 分布；不外推为实体、全波或实验结论。

## 2. 冻结公式摘要

E2 raw 单位方向为 `state×port×frequency = 4×4×256`。primary 取前 208 点，按 frequency-major/port-minor 展平为 `Y_C∈C^(832×4)`，右乘 `P_diff`。冻结 E2 development common W 的实际方向为

`Z_R = W_(1664×1664) [Re(Y_diff,C);Im(Y_diff,C)]_(1664×4)`。

随后仅作等距逆嵌入 `Z_C=Z_R[:832]+i Z_R[832:]`，不拟合新的 complex W。六对按 `(0,90),(0,180),(0,270),(90,180),(90,270),(180,270)` 固定；`d_ab=||z_a-z_b||_2`，`d_min` 为六对最小值。

主指标是 `LTES_0.05(d_min)`：对冻结 cell/repeat 权重下最低 5% 概率质量求均值，并对边界单位使用分数质量。等价 loss 记号为 `-CVaR_0.95(L=-d_min)`。六对各自 LTES、最弱 pair 分布和 `max(d_ab)/min(d_ab)` anisotropy 单独保留。

Gram 唯一写为 `G=Z_C^H Z_C`，即 `Z_C.conj().T @ Z_C`。每单位 Hermitian 对称化后按正实 trace 归一；每 identity reference 仅由 development 的 7,350 个等权单位构造。主漂移为 normalized Gram 到冻结 reference 的 Frobenius 距离，并报告其 upper-tail 5% expected shortfall。validation 不更新 reference 或 W。

family inference 只以 20 identities/family 为抽样单位；冻结 exact-20 worst-member、全 20 分布、20,000 次 identity bootstrap 和 100,000 次 identity-label max-|T| permutation。cell、repeat 与 frequency 均不充当 family 独立样本。

## 3. 权威输入核验

- 已读取 E2-R REPORT、GEN-ENC-0R、GEN-ENC-1 estimator、E2 Freeze-01/CORR01/Freeze-02/RC-B-FINAL、正式 driver/core、共同 W、D/V terminals 和 exact80 manifest 指向的全部 80 identity payload。
- exact80 顺序、payload identity、文件 SHA-256 与四家族×20 全部匹配；manifest SHA-256 为 `e460eb09a05b5c8fb491250a6fe5d9046d0a1ebe7d70246f45ca117571779a08`。
- nuisance 表为 `N0001..N3675`，每行权重等于 `1/3675`；development seeds 为 `2026091001/2026091002`。
- 共同 W 为 `1664×1664 float64`，SHA-256 `3ba1ec8926dcbd60f9b670bbcf3079426d54c93330427089fa4b8ade5a44bc04`；D/V terminal 都绑定同一 hash，`validation_refit=false`。
- D terminal SHA-256 `c90dec4278f8a88d2cbd117c6959e93587434ec3cad72a4a21f7a30ed7857678`；V terminal SHA-256 `fa3e10c46703534e97518bb9e15e5f00e0906fb17a822ab8873f158626e8630e`。预飞只读 V terminal 作 seal binding，没有读取 validation response。
- 成本措辞限定为：相同 volume/minimum-feature/solid-load-path，DOF 12–15 包络匹配；不称完全等成本。

机器核验位于 `identity_manifest_audit.json` 与 `e2_seal_binding.json`。

## 4. 公式单测与回归

新增 synthetic fixture 明确给出复数 `Z`、六距离、最弱 pair、anisotropy、带非零虚部的 Gram 元素，以及 expected-shortfall 分数边界样例。

3A 单测：`23 passed in 0.66 s`（同一目标回归中的单文件计数）。除固定状态/状态对顺序、复共轭 Hermitian Gram、trace normalization、development reference、Frobenius drift、lower/upper expected shortfall、实/复嵌入等距性、W 左乘方向、E2 feature 方向一致性、batch/scalar 一致性和 candidate summary 外，还覆盖 exact-20 identity inference、12-stat max-|T|、contrast 方向、固定 seed byte-repeatability、零差异、零方差 `INCONCLUSIVE`、正式/预飞根隔离、partition-bound audit 和独立 verifier import 隔离。

最终目标回归命令：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:/Anaconda3/python.exe -B -m pytest tests/test_gen_enc_3a_robust_encoding_geometry.py tests/test_gen_enc_2_e2_d_execution_repair_freeze_01.py tests/test_gen_enc_2_e2_rc_b_final.py tests/test_gen_enc_2_e2_rc03_final_closure.py -q --basetemp=.pytest_gen_enc_3a_final
```

结果：`43 passed in 1.27 s`。一次早期使用系统 temp 的回归尝试因既有 Windows temp 权限报错；按合同改用项目内 `--basetemp` 后全部通过，属于环境路径问题，不是科学或实现失败。

## 5. science-blind development member preflight

预飞身份固定为 exact80 global ordinal 1 的 `HAND_01`，沿用 E2 timing proxy，未按 3A 性能选择。执行结果：

- 3,675/3,675 cells、7,350/7,350 repeats、147/147 phase-1 chunks、147/147 phase-2 chunks 完整；
- 每 chunk 保存 `distance[25,2,6]`、`gram_drift[25,2]`、`weakest_pair[25,2]`、`pair_anisotropy[25,2]` 与两阶段 receipts；
- development reference Gram 已按 7,350 单位加权构造并 hash-seal；
- 确定性 sparse audit 保存 2 个 `Y_diff[832,4] complex128`；没有保存全量 raw `Y_diff`；
- E2 retained raw audit 的 2 个 chunks 均 byte-identical reproduction；
- raw chunk 残留 0，临时 normalized-Gram chunk 残留 0；
- checkpoint 完成态重入返回 `resumed_complete=true`；
- 全包 `SHA256SUMS.txt` 复核 0 mismatch；
- 最终重算 wall `27.4402709 s`，process CPU `22.609375 s`；3A preflight output 当前总量约 `1.234 MB`，远低于 raw 全量方案。

science-blind terminal SHA-256 为 `039605d28f55767e1d135504dfa467dc67cb69d5c6dc1022332d20dbd144a5da`。该 terminal 只记录完整性、形状、hash、资源和是否复用/读取，不含科研 metric 值；`SHA256SUMS.txt` 独立复核 mismatch 为 0，完成态重入返回 `resumed_complete=true`。

## 6. 新增实现与冻结 hash

| 对象 | SHA-256 |
|---|---|
| `robust_encoding_geometry.py` | `b60d95ba0397fc8bf5bb1b06c09f73bd9bd161478300249ea50c19a7ed0dfb55` |
| `gen_enc_3a_robust_geometry_preflight.py` | `22904f8945c830c67a45ae862210bd1e38d4b01b25eb75f9126c7086694d7527` |
| `gen_enc_3a_robust_geometry_formal.py` | `ecde50efcc03bc8ce4f3cbc2cab1248fd506256f637ae4035986a9644998933b` |
| `gen_enc_3a_robust_geometry_independent_verifier.py` | `0c650f729663096b5e1dc2a5ea68912d044cbe97134031a60bd9e9c3307167cb` |
| formula/inference/isolation tests | `f7ceaace782c37ad5a302d4262cbe2fd49c17c5545ce1a0c87cb35db2e9631c1` |
| synthetic fixture | `82f662be927ed1f01ab86f7accfbbfda633fc10d84b8da59146abc860a603def` |
| identity-inference fixture | `6c4da16e0897d420022dcf2459551cae87a9f8e60836ac248c192e5fe55c6283` |
| human contract | `ec99270fdcd8e4e4860319d5fd80cf1454cf3e20b88ec577c56c20a910ce6a16` |
| machine contract | `ab75dceda9b79d4f9b056cbada6661afb0a68bbdd39f390ab44450aeef67d213` |
| output SHA256SUMS | `136b4b8190c2f218df2b227db4f583b95b1509603b53cb427ce54ddde5577bd4` |

## 7. 正式 D/V family 结果

`S_min` 为 candidate 的 `LTES_0.05(d_min)`，越大越好；`U_drift` 为 Gram Frobenius drift 的 upper-tail 5% expected shortfall，越小越好。下表报告每家族 exact-20 的 worst member；完整 20 点、median 与 IQR 在两个 `family_summary.json` 中。ECDF 唯一由所列完整 20 点定义为 `F_20(x)=#{value_i<=x}/20`，没有平滑、删点或替代样本。

| Family | D `S_min` worst | V `S_min` worst | D `U_drift` worst | V `U_drift` worst |
|---|---:|---:|---:|---:|
| HAND | `3662930.546995` (`HAND_05`) | `3662930.530356` (`HAND_05`) | `0.025484620365` (`HAND_11`) | `0.025484619818` (`HAND_11`) |
| NEAR | `3662791.041598` (`NEAR_04`) | `3662791.020956` (`NEAR_04`) | `0.025484718092` (`NEAR_16`) | `0.025484721659` (`NEAR_16`) |
| RANDOM | `3663251.783367` (`RANDOM_03`) | `3663251.813626` (`RANDOM_03`) | `0.025484567606` (`RANDOM_16`) | `0.025484567726` (`RANDOM_16`) |
| PHYSICS | `3662915.310845` (`PHYSICS_02`) | `3662915.279881` (`PHYSICS_02`) | `0.025484553085` (`PHYSICS_12`) | `0.025484553176` (`PHYSICS_12`) |

D/V inference 均为 `AVAILABLE`。validation margin contrasts 的 adjusted p 范围为 `0.90470095299047..1.0`，drift contrasts 为 `0.7074729252707473..0.999960000399996`；12 个 CI 均跨 0。故不存在预注册意义上的 adjusted validation family difference，也未满足“同一家族同时领导 margin/drift”的联合门禁。

成本仅表述为相同 `volume_m3=3.014899604922098e-5`、`minimum_feature_m=0.002`、`solid_load_path_m=0.002`，且处于 DOF 12–15 包络；不是完全等成本。

## 8. 完整性、独立复核与终端 hash

- D：80 candidate terminals、80 reference seals、80 reference Gram、160 sparse `Y_diff` audits、临时 Gram 残留 0；wall `1299.2298141 s`，process CPU `1103.265625 s`。
- V：80 candidate terminals、80 development-reference bindings、160 sparse `Y_diff` audits、临时 Gram 残留 0；wall `1356.4434666 s`，process CPU `1163.84375 s`；`single_use_consumed=true`、`validation_refit=false`、`validation_feedback_to_development=false`。
- 独立复核：两个 partition 均为 `INDEPENDENT_PASS`；生产公式模块与正式驱动均未被 verifier import。共复算 160 candidates 的 tails 和 320 个 solver audit units，并逐字节匹配 bootstrap/permutation arrays。
- 正式源码清单在完成后重新计算仍与 seal 相同；`preflight_reused=false`、`HAND_01` 已正式重算、`final_test_read=false`。

| 终端 | SHA-256 |
|---|---|
| D partition | `02ca458cad71c37b2d3301f6bc95593c1d80c4924092019680f502b054d71143` |
| V partition | `4d674273a89c823060c9c0960616f4872a254d221790cbed491847894491c1e7` |
| independent verification | `8c9bd39e5412f0846b6aeaf23f110c48bff37e1170696024f6702368fe35596a` |
| final scientific terminal | `bf6efa5cf79821a9985785a9411e2e6b75a668e85457941bdfef152b2451974c` |

## 9. 监管入口与停止点

权威合同：`docs/experiment/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY_CONTRACT.md`。  
独立输出根：`outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY/`。  
监管任务：`01a061f9-64fc-7e51-a9e6-659dd7ffe2ae`。

监管已完成一次预执行审查并授权修正闭合后直接进入正式 D。正式根独立为 `outputs/gen_enc/GEN_ENC_3A_ROBUST_ENCODING_GEOMETRY/formal/`，拒绝预飞 payload，且 `HAND_01` 未提升复用。80/80 D、reference/W seal、80/80 single-use V 与独立复核均完成；当前停止于允许终态 `GEN_ENC_3A_NO_STABLE_FAMILY_SEPARATION`，不启动 3B、COMSOL/full-wave、打印、实测、参数搜索、final-test、commit 或 push。

最终结果已回传监管任务 `01a061f9-64fc-7e51-a9e6-659dd7ffe2ae`。监管的最终 claim-boundary review 为通过：确认该终态表示“未发现稳定家族分离证据”，不表示四家族等价；证据上限保持 `E2_REDUCED_MODEL`；canonical complex Gram 仅表示冻结坐标约定下的状态几何，不支持物理相位机制主张；成本只可采用上述共同几何指标与 DOF 包络措辞。

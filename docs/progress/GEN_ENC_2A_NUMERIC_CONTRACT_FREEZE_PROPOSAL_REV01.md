# GEN-ENC-2A 数值合同冻结提案 REV01 进展

日期：2026-08-28

终态建议：`GEN_ENC_2A_REV01_READY_FOR_GUARDIAN_REVIEW`

证据等级：`E0_CONTRACT_REVISION`

## 增量 metadata

- **新增**：用户接受修订的独立 REV01 包。
- **关联**：原 GEN-ENC-2A proposal 与 guardian review。
- **未改变**：原包、旧合同、旧结论、旧资格、RQ 与 final-test 状态。
- **证据等级**：`E0_CONTRACT_REVISION`。
- **覆盖**：`overrides=false`。

## 已落实

- primary 改为 208 点 `200–3973.94499863515 Hz`；256 点 full band 仅 secondary sensitivity，分别报告。
- volume 改为 nominal target `3.014899604922098e-5 m³` 和 matched interval `[2.984750608872877e-5,3.0450486009713192e-5] m³`；U4 x/y/z 单独作为 upper caps。
- `g(f)` 仅 mandatory descriptive；删除 0.1/0.01 eligibility gates。
- family `n=20` statistic 改名 worst-member/minimum robustness，不作 population Q0.05 声称。
- 用 3675-row mixed-level strength-2 joint nuisance design 替代 735 diagonal bundling；七轴所有 levels、边际和两两 level pairs 完全平衡。
- 预声明七主效应和 15 个 cross-group interactions；309-column 矩阵 rank 309。明确六个 within-group pair interactions 与全部高阶 interactions 不识别；不声称 full Cartesian 等价。
- HAND/NEAR 各 20 行实际表完整；RANDOM inverse-CDF 与 PHYSICS 15-parameter midpoint-LHS 算法完整。
- workload 重算为 1,176,000 complete units、约 4.215 billion streamed complex values。硬 cap 保持但可行性未建立。

## 继续阻塞

generator source SHA-256 与各 family instance-manifest SHA-256 因本阶段禁止生成而 pending-by-design。任何 null 都阻塞 timing preflight 和 GEN-ENC-2。

`execution_authorized=false`、`gen_enc_2_authorized=false`、`preflight_authorized=false`。所有科学执行计数为 0；`final_test_read=false`、RQ 关闭 0、`bidirectional_discovery_established=false`。完成后停止，等待上级提交 guardian review。

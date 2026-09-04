# GEN-ENC-29 A04-S1-PHASE-MESH-B

日期：2026-09-03  
终态：`A04_S1_PHASE_MESH_STOP`

对 PRINT-BLIND-C 唯一失败路径 alpha=0.04/source 1 使用与 GEN-ENC-27 相同的 G1/F32/F26 序列。G1→F32 原始复 L2 为 1.800%，通过；F32→F26 为 **3.107%**，比 3% 门槛高 0.107 个百分点，因此本轮停止。频率始终 1036 Hz，末级深度变化 +0.042 dB；北侧参考归一化末级 L2 为 0.617%，表明差异仍主要表现为传播相位，但未用归一化结果替代正式门禁。G1 独立重跑 L2 为 1.12e-13。

授权下一轮只增加 F20，不改几何、读出器或阈值。正式入口：`scripts/gen_enc_29_a04_s1_phase_mesh/GenEnc29A04S1PhaseMesh.java` 与对应分析脚本。未提交，未 push。

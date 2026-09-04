# COMSOL TRANS-1R256 — 可恢复256点 coarse/fine 数值门禁

更新时间：2026-08-27T11:02:54.294866+00:00  
状态：`TRANS1_R256_NUMERICAL_GATE_FAIL`

## 检查点

- coarse：4/4
- fine：16/16
- 下一待运行块：无
- actual study.run submissions：20/20
- successfully solved：20
- atomically committed chunks：20
- 块累计实际时间：28898.733 s
- 当前阶段产物：7.026 GiB
- 剩余空间：154.176 GiB
- 停止原因：正常完成全部20块；数值门禁FAIL：HR03 coarse/fine峰均未识别。
- 检查点完整性：每次入口及每块提交后均校验冻结契约、目录文件、频率轴和 SHA-256。

## 数值门禁

coarse/fine 门禁：FAIL。阈值保持共振中心变化 <1%，固定窗口关键对比变化 <0.5 dB。

## 恢复

唯一命令见 `outputs/simulation/COMSOL_TRANS_1_R256_RESUMABLE_GATE/RESUME_INSTRUCTIONS_zh.md`。恢复只继续下一未提交块；不会重跑可信 completed 块。

## 边界

仅 ISO-CODED/N；未启动第二组合、TRANS-2/3、外场、分类器或实体分析。`final_test_read=false`。未 commit、push、tag 或 release。

# INFO-TOP 共享上下文

权威入口为 `docs/experiment/INFO_TOP_RESEARCH_CONTRACT.md` 和 `outputs/info_top/INFO_TOP_0_RESEARCH_CONTRACT/analysis_summary.json`。

- TOP-0：`PASS`；只完成合同和资产审计。
- Level A：TRANS N×6、S×6、NRETURN×3，真实单麦克风，单次闭合。
- Level B：旧 U4 AS01 B01–B04 ACTIVE，真实单麦克风，受 block/assembly/方向限制。
- Level C：仿真/降阶模型，必须和真实证据分开。
- R256：20/20 块完成但 `TRANS1_R256_NUMERICAL_GATE_FAIL`。stitched NPZ/CSV 不能新增点；保存 MPH 含完整解块，条件性支持既有 ISO-CODED/N 的无求解点后处理，TOP-2 必须先做 `study.run()` 禁止的只读预检。
- TOP-1 只做 Level A/B 分开的真实单麦基线；不做多麦、COMSOL、分类器主结果或新实验。
- H-COUNT 不预设对数关系；比较对数、饱和、幂律和非参数 Pareto。
- 频率点不是独立样本；所有验证按完整重复/block/assembly 或仿真参数单元分组。
- TOP-0/1 无 heartbeat；TOP-2/3 建议 heartbeat，但不得由监督器改变科研设计或资源预算。
- `final_test_read=false`。


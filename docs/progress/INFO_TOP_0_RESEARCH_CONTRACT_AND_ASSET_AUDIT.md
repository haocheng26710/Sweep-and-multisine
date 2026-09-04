# INFO-TOP-0 研究合同与资产审计

日期：2026-08-27  
终态：`PASS`  
分支：`feature/v2-dual-input`  
`final_test_read=false`

## 1. 决策摘要

INFO-TOP-0 已完成且通过。研究问题、假设、数据层级、指标、验证单位、成本轴、TOP-1–4 有界执行矩阵和监督边界均已冻结。本轮没有运行 COMSOL、分类器、参数搜索、后续 INFO-TOP 分析或实体实验。

当前值得进入 INFO-TOP-1。理由是 Level A 已有一个效应超过本批重复性底线并有 NRETURN 支持的二状态单麦克风基线，Level B 又提供受限但真实的四状态/高共享参照；TOP-1 可以在不依赖 R256 精确预测资格的情况下回答“现有单麦克风能分辨多少”。

## 2. 权威输入复核

复核了任务指定的 13 项报告/机器产物及直接必要资产。关键一致性如下：

- TRANS 实体：15 TXT+15 MDAT，N×6、S×6、NRETURN×3；主频带 N−S 去均值谱形 RMS `2.0694586689 dB`，bootstrap 95% CI `2.0556914771–2.1876296379 dB`；本批组内 p95 `0.9557515451 dB`，比值 `2.1652684524`；NRETURN−S `2.0791517516 dB`，效应相关 `0.8512576982`；1850/3800 Hz 联合对比 `2.7528439470 dB`。分类保持 `TWO_PORT_SELECTIVE_ENCODING_SUPPORTED_WITH_LIMITS`。
- 原 U4：FORMAL-5 保持 `supported_with_limits`；U4ENC `G_demeaned=1.2805`、U4SYM `0.6824`，但 ΔG CI 包含 0；AS01 grouped balanced accuracy 为 0.25/0.375，均低于 0.50。不能确认可靠四方向分类。
- V2.5/SUP：共享腔/多端口混合会重组预定频率码；单入口中心可调不等于组合后的独立通道。SUP-2R 只有 270°–ENC-F 映射稳定，相关性不允许升级为单模块独立贡献。
- R256：4/4 coarse、16/16 fine、20/20 实际 `study.run` 均完成并保存；门禁因 HR03 coarse/fine 峰均未识别而 `FAIL`。固定窗口收敛不改变总门禁失败，也不授权精确实体峰位预测。
- P04T5：现有机制证据支持共享腔体积的有界控制趋势和实体宽频重分配，但简化 COMSOL 不能精确预测实体局部峰谷；旧 P05–P10 在原合同下关闭。

所有复核均为现有文件的只读检查。未读取 final-test，未改变任何 TRANS、FORMAL、SUP、P04 或实验权威产物。

## 3. TRANS 阶段关闭与 provenance

| 阶段 | 历史事实 | INFO-TOP-0 建议关闭映射 |
|---|---|---|
| TRANS-0 | 初始 BLOCKED、RETRY_01 BLOCKED；RETRY_02 最终 `TRANS0_PASS_FOR_TRANS1_RETRY` | `TECHNICAL_PREFLIGHT_COMPLETED_FOR_TRANS1_RETRY` |
| TRANS-1 仿真 | 早期 BLOCKED；fine smoke 修复通过；R256 20/20 完成但最终门禁失败 | `TRANS1_R256_NUMERICAL_GATE_FAIL` |
| TRANS-1 实体 | 二状态实体 pilot 完成 | `TWO_PORT_SELECTIVE_ENCODING_SUPPORTED_WITH_LIMITS` |
| TRANS-2 | 没有按原编号正式执行 | `SUPERSEDED_BY_AS_BUILT_TWO_PORT_DEVICE` |
| TRANS-3 | 没有按原编号正式执行 | `FULFILLED_BY_TRANS1_TWO_PORT_PHYSICAL_PILOT` |
| TRANS-4 | 没有按原编号正式执行 | `DEFERRED_PENDING_INFO_TOP4` |

后三项是本轮的项目关闭映射，不改写历史报告，也不把 TRANS-2/3 伪造为 PASS。

## 4. 资产与多麦克风审计

现有真实测量全部是单麦克风观测。Level A、Level B 和 V2.5/SUP 的 TXT/FeatureSet/预处理谱可以用于单麦基线或降阶模型锚定，但不能生成新的真实空间通道。

R256 的 stitched coarse/fine NPZ 均只含 6 个长度 256 的数组：`frequency`、复数 `mic`、`e_all`、`e_hr03`、`e_south`、`e_plenum`。它们没有空间坐标或节点压力场，因此 **NPZ/CSV 本身不支持新增虚拟麦克风**。

对一个 coarse 和一个 fine 代表 MPH 只读检查 ZIP 目录，未载入 COMSOL：两者均包含模型、mesh/xmesh、solution/solutionstatic 和逐频 solutionblock。保存脚本也明确在求解后 `model.save(...)`，再重载同一 MPH 提取字段。这构成足够的结构证据，说明 **已保存 MPH 对既有 ISO-CODED/N 案例条件性支持不重新求解的派生点读取**。但本轮没有实际打开 COMSOL 节点，因此 TOP-2 路径 A 仍必须先做一个禁止 `study.run()` 的代表文件预检，确认：

1. 正确 solution/dataset tag；
2. 声压变量和复数值语义；
3. 候选坐标落在有效声学域；
4. 提取频率数与 chunk 契约一致；
5. 重复加载结果一致。

这个“条件性 YES”仅覆盖已有 ISO-CODED/N 解。R256 没有第二状态和三类拓扑，且数值门禁失败，因此不能独自支持 TOP-2 完整状态比较或 TOP-3 拓扑结论。

三档路径已冻结为：A 复用保存解加有限点探针；B 使用真实数据/COMSOL 锚定的降阶传递或耦合模型；C 仅在 A/B 有文档化不足后，由后续阶段另行批准有限新 COMSOL。

## 5. 冻结统计与解释边界

- 主指标优先使用组间/组内谱形距离、Fisher/收缩 Mahalanobis、有效秩/奇异值、条件数/串扰及扰动鲁棒性。
- 互信息下界必须声明估计器、状态先验、偏差和小样本界；不能稳定估计时报告 unavailable/exploratory。
- Pareto 成本轴至少含麦克风数；布线、ADC 和校准复杂度只作为分项/权重敏感性，不声称掌握真实价格或功耗。
- 分类器只作次要 readout；采用 group/block/assembly-aware 分割。
- 频率点不作为独立样本；重采样单位是完整重复、block、状态内 block 或完整仿真参数单元。
- 支持、部分支持、阴性和不确定分开；相关性、谱形相似与有效秩均不等于独立因果贡献。

## 6. TOP-1 精确输入与边界

TOP-1 的输入仅为：

1. Level A：TRANS N×6、S×6、NRETURN×3 的 15 条真实 TXT 完整重复、manifest/QC 和冻结预处理；NRETURN 仅用于回程/漂移敏感性。
2. Level B：FORMAL-3/4 的 AS01 B01–B04 共 48 条 ACTIVE 单麦克风曲线，B01/B02=U4SYM、B03/B04=U4ENC；保留既有 flags 和 block/assembly 身份，不读取 EXCLUDED/final-test。
3. `metric_definitions.json` 和本研究合同。

TOP-1 只输出 Level A/B 分开的可解释单麦分辨基线与不确定性。禁止虚拟多麦、COMSOL、分类器主结果、新采集、随机频点划分、改变 selection/threshold 或把两层合成一个总体效应。

## 7. 产物与验证

权威目录：`outputs/info_top/INFO_TOP_0_RESEARCH_CONTRACT/`

- `analysis_summary.json`
- `asset_inventory.csv/.json`
- `trans_stage_closure_mapping.json`
- `metric_definitions.json`
- `stage_matrix.csv/.json`
- `multimicrophone_asset_feasibility.json`
- `supervisor_boundary.json`
- `artifact_inventory.json`
- `SHA256SUMS.txt`

研究合同：`docs/experiment/INFO_TOP_RESEARCH_CONTRACT.md`。共享上下文：`docs/prompts/info_top/SHARED_CONTEXT.md`。

验证包括 JSON/CSV 全量解析、核心跨文件断言、SHA-256 复核、必要 compileall 和 `git diff --check`；不运行完整回归。新增内容只有文档和机器合同，因此没有新增辅助分析代码，也无需引入测试模块。


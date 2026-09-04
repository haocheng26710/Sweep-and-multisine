# GEN-ENC-0R 增量恢复合同与反证门报告

日期：2026-08-27
终态：`GEN_ENC_0R_CONTRACT_FROZEN_NO_EXECUTION`
技术状态：`PASS_CONTRACT_ARTIFACTS_ONLY`
证据等级：`E0_CONTRACT_AND_PROVENANCE`
覆盖旧结论：`false`
`final_test=sealed`，`final_test_read=false`

## 增量声明

- **新增内容**：形成 GEN-ENC-0R 人类合同、机器合同、反证门、依赖/并行边界、active question 映射、证据/主张边界、旧主线关系索引和确定性清单。
- **关联旧文件**：范围审计与章程、TRANS 实体 pilot、INFO-TOP-0 合同与 TRANS 关闭映射、INFO-TOP-4 独立综合，以及 TRANS/INFO-TOP-0–4 权威 `analysis_summary.json`。
- **未改变内容**：未修改、融合或重写 FORMAL、SUP、V2.5、Scheme 3A、TRANS、INFO-TOP 的任何旧报告或权威机器产物。
- **证据等级**：E0；本报告没有新科学结果。
- **覆盖旧结论**：否；旧结论仍按原证据等级和限制成立。

## 合同冻结结果

primary endpoint 冻结为四状态差分响应在独立 validation 与完整 nuisance 集上的白化第三奇异值 5% 分位数，阈值严格大于 1.0；由此导出的稳定秩目标为 3。`A/B/C` 的物理语义、维度、gauge 等价与不可识别性均已写明。共享模态与差分模态明确投影，二状态只作秩 1 sanity check。

冻结设计状态为 0/90/180/270°；45/135/225/315°及排除设计点的 15°连续网格保持 held-out。拓扑比较至少含手工、近独立、固定种子随机/无序、物理/超材料启发四类；材料/有效体积、端口/状态/传感器、带宽、包络、插损/传输、计算和制造复杂度均为强制 matched-cost 轴，任何数值 cap 未在后继执行前单独哈希冻结即阻塞。

反向设计要求 train/development 与 validation 严格分离，允许 `NO_IMPROVEMENT`。全波必须新建资格合同并通过解析参考、网格、守恒/被动性/互易性、保存重载和预算门后，才可运行最多 2–3 个预先确定的判别 anchors；旧 P04B/R256 不具直接升级资格。

## 反证门摘要

- `FG-01`：primary endpoint 不超过 1.0 或稳定秩小于 3即反证四状态稳定编码。
- `FG-02`：任一强制中间角折叠、导数符号失败或环不连续即桥接失败。
- `FG-03`：拓扑 family 无法满足同成本即阻塞共同科学比较，不可删除该 family。
- `FG-04`：inverse design validation 未严格优于最佳合格基线即 `NO_IMPROVEMENT`。
- `FG-05`：技术资格失败只产生 `TECHNICAL_INVALID / NOT_TESTED`，不得产生科学否定。
- `FG-06`：validation 泄漏、事后选频/阈值/分类器优化使该验证永久失去独立资格。
- `FG-07`：低等级证据不得提升实体/全波主张。
- `FG-08`：final-test 任何读取请求立即停止；metadata 不能改变资格。

## Active ledger 与非关闭声明

直接承接：RQ-01、RQ-02、RQ-04、RQ-05、RQ-08、RQ-09、RQ-10、RQ-11。仅保留 provenance、不宣称关闭：RQ-03、RQ-06、RQ-07、RQ-12。本合同不静默关闭任何其他问题；旧 TRANS-2/3 等价映射仅为推荐 closure provenance，不冒充 GEN-ENC 科学结果。

## 未执行项

未运行仿真、参数搜索、分类器训练、实验、COMSOL、旧结果重算、GEN-ENC-1、SUP-3 或 TRANS 独立重闭合；未补采 FORMAL；未执行 P04/P05–P10；未访问 final-test；未 commit/push/tag/release。

## 增量发现方式

由于授权只允许写新 GEN-ENC/补充路径，且旧目录处于共享脏工作树，本轮未向旧权威目录写 sidecar。统一机器入口 `outputs/gen_enc/GEN_ENC_0R_RESTORATION_CONTRACT/relates_to.json` 明确记录全部旧关联、哈希和“双向发现未建立”的原因。

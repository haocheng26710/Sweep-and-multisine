# WRITE-3：研究方法、讨论与局限性整合

状态：完成；仅整合冻结证据和论文措辞，不重新分析、筛选或生成图表

日期：2026-08-20

分支：`feature/v2-dual-input`

## 目标与边界

本轮创建 Methods、Discussion、Limitations and Future Work 三份英文论文初稿，并把入口加入 README 和进度索引。

文档只使用冻结协议、FORMAL-2A/3/4/5、WRITE-1/2 文档和 hash-audited artifacts。没有重新读取原始 TXT、扫描数据目录、运行新统计、修改 ACTIVE/EXCLUDED、改图或读取 final-test。

冻结状态保持：

```text
disposition=supported_with_limits
H0=not_rejected
H1=not_confirmed
scientifically_eligible=false
final_test_read=false
```

## 章节组织

`edit-article` 技能要求按信息依赖组织章节并将普通段落控制在 240 字符以内。本轮按该规则排列内容：

- Methods：研究问题 → 设计与设备 → 选择/QC → 预处理 → 指标/验证 → 判定和 provenance；
- Discussion：重复性底线 → 方向和配置效应 → 不确定性 → 分类负结果 → 工程意义；
- Limitations：环境/设备 → 独立性和混杂 → selection → 分类 → final-test/科研资格 → future work。

自动测试逐段检查三份文档的普通段落长度，没有改变表格、公式或术语含义。

## 权威输入与 hash 复核

本轮重新调用既有 authority verifier：

- FORMAL-3：72 ACTIVE、19 EXCLUDED、72 FeatureSets、255 共同有效点、10 flags，`225/225` artifacts 匹配；manifest SHA-256 `9aa329a730066f4487ac4a77f8700dca40862fec71a46d53817a7dc4d8d9e850`；
- FORMAL-4：`28/28` artifacts 匹配；manifest SHA-256 `6744b7142480a20a631ff6a33f763329e852b4086ba5f05d53301beb6853d4ef`；
- FORMAL-5：`6/6` business artifacts 匹配；manifest SHA-256 `2134cd1d42de0ac136dd41d1a30b71f049835a822a17b9f88ed41d8fd76bc907`；
- WRITE-2：7 figure groups/14 files、4 table groups/8 files 全部匹配，PNG minimum dpi=`300`。

没有重新生成 WRITE-2 图表。三份新文档只引用已冻结的 Figure 1–7 和 Table 1–4。

## Methods 完成范围

`METHODS_DRAFT.md` 记录：

- U4SYM/U4ENC、AS01/AS02、四方向、CONT/REPOS/REASM 的角色；
- 96 Sweep 预注册计划与实际 72 ACTIVE/19 EXCLUDED 精简分析集的区别；
- 单 iMM-6C、普通房间、约 0.8 m 目标几何及未完成几何证据边界；
- `CMM29939.txt` 输入绑定已验证，但逐 TXT calibration filename unavailable；
- REW V5.31.3、48 kHz、256k、1 repeat、No timing reference、IR peak、200–8000 Hz、-30 dBFS、输出 50、输入 100；
- 48 PPO 对数网格、分段插值、1/12-octave dB smoothing 和 255 个实际有效点；
- CONT floor、G、ΔG、2,000 次 cluster bootstrap、effect/floor、nearest-centroid grouped validation 和 999 次置换；
- 冻结判定规则、hash/provenance、数据隔离和 final-test 门禁。

文档没有声称绝对 SPL 校准、消声室、独立外置备份、完整几何记录或未使用设备。

## Discussion 完成范围

`DISCUSSION_DRAFT.md` 保留以下解释：

- 方向频谱变化超过 CONT 底线是物理距离证据，不等于未见 block 的预测能力；
- U4ENC 点估计高于 U4SYM，但 U4ENC CI 跨 1、ΔG CI 跨 0，因此 H1 未确认；
- 描述性方向效应与 H0 未拒绝可同时成立，因为冻结 H0/H1 涵盖更完整门槛；
- AS01 configuration effect/floor=`1.5688` 可报告，但 AS02 与 block/time/assembly 混杂；
- grouped BA `0.375/0.250` 均低于 0.50；
- 10 flags 的临时敏感性视图未改变阈值裁决或 selection；
- 工程意义限于“可测形态相关频谱结构”，不扩大为结构优越性或稳定方向预测。

Discussion 引用 Figure 1–7 和 Table 1–4，编号与 WRITE-2 manifest 一致。

## Limitations 完成范围

`LIMITATIONS_AND_FUTURE_WORK.md` 记录普通房间、消费级声源链、有限声压校准、单麦克风/单空间、72/96、四方向、AS02 缺 RP02、block/time 混杂、10 flags 保留和分类未达目标。

文档说明 final-test 仍 sealed，`scientifically_eligible=false` 表示完整确认性和治理门槛未满足，而不是软件执行失败。

Future work 优先增加独立 REPOS/REASM、房间/麦克风覆盖、固定几何、完整环境与 source monitoring、外置备份和 group-preserving evaluation；不会反向改变本次冻结结论。

## Citation-needed 清单

三份初稿共有 `13` 个 `[CITATION NEEDED: ...]` 标记，覆盖：

- 普通房间反射、standing waves 和 room–object interaction；
- microphone calibration 与 absolute SPL traceability；
- fractional-octave smoothing 和 logarithmic sampling；
- hierarchical cluster bootstrap；
- balanced accuracy、macro-F1 和 grouped cross-validation；
- repeated-measure assembly design；
- passive acoustic morphology；
- consumer audio chain uncertainty；
- grouped multiclass validation 的 sample-size 支持。

本轮没有捏造作者、论文、标准或参考文献。引用补全必须在后续文献轮次使用可核验来源。

## Claim-boundary 审计

自动检查逐项对照 `RESULTS_CLAIM_CHECKLIST.md` 的冻结状态：

- 72 ACTIVE/19 EXCLUDED/10 flags 保持不变；
- 主数值 0.3783、0.8793、1.2805、0.6824、0.5982、CI、1.5688、0.375/0.250 和 0.50 均存在且一致；
- `supported_with_limits`、H0/H1、科研资格和 final-test 状态一致；
- Figure 1–7、Table 1–4 引用完整；
- 越界措辞扫描为 0；
- 普通段落长度门禁通过；
- WRITE-2 输出 hash 全部通过。

## 输出与 SHA-256

| 文件 | SHA-256 |
|---|---|
| `docs/dissertation/METHODS_DRAFT.md` | `ae02e7844706287d2a62392b6c1095859d5ae436a0de8b750e91a0d54c192521` |
| `docs/dissertation/DISCUSSION_DRAFT.md` | `31cb5acc540efb9ddd4867be81a1737a31d3a1301f8fb747b45aeab8da84d165` |
| `docs/dissertation/LIMITATIONS_AND_FUTURE_WORK.md` | `5d10221efa6bf1c7053ddd704433a0745db9e51d0b310e2265f1e48aa07f1478` |

## 修改文件

- 新增：`docs/dissertation/METHODS_DRAFT.md`；
- 新增：`docs/dissertation/DISCUSSION_DRAFT.md`；
- 新增：`docs/dissertation/LIMITATIONS_AND_FUTURE_WORK.md`；
- 新增：`tests/test_dissertation_write3.py`；
- 新增：本报告；
- 更新：`docs/progress/INDEX.md`；
- 更新：`README.md`，仅增加论文文档入口。

没有修改科研算法、schema、配置、正式数据、ACTIVE/EXCLUDED、FORMAL 权威输出、WRITE-2 图表或 final-test。

## 实际验证

初始红灯：三份目标文档尚不存在，WRITE-3 专项为 `4 failed`；文档完成并修正字段/段落门禁后为 `4 passed in 0.95s`。

相关联合回归：

```powershell
python -m pytest -q tests/test_dissertation_write3.py tests/test_dissertation_assets.py tests/test_formal_final_synthesis.py tests/test_formal_core_analysis.py tests/test_formal_real_import_qc.py
```

最终结果：`30 passed in 23.57s`。

`python -m compileall -q src scripts` 无输出、退出码 0；`git diff --check` 无输出、退出码 0。FORMAL-3/4/5 和 WRITE-2 verifier 结果如“权威输入与 hash 复核”所列，citation count=`13`。

## 已知限制与下一步

本轮是章节初稿，不包含外部文献搜索、正式引用格式、全文 Introduction/Literature Review、最终排版或人工语言润色。

下一步应先为 13 个 citation-needed 项补入可核验文献，再做全文交叉引用、术语统一和最终排版。任何编辑仍不得重新打开分析、改变数值或读取 final-test。

对应本地提交：`docs(dissertation): integrate methods discussion and limitations`。本轮不 push、不创建 tag/release、不合并分支。

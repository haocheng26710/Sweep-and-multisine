# WRITE-4 — 论文实验部分最终整合与交付验收

## 状态

- 日期：2026-08-20
- 分支：`feature/v2-dual-input`
- 状态：完成，等待本地提交
- 范围：论文实验章节整合、引用需求登记、最终一致性审计与 hash 交付清单

## 完成内容

Methods、Results、Discussion、Limitations 已按依赖顺序整合为一个最终实验章节。术语、缩写、图表编号、频带、单位、精度和 ACTIVE/EXCLUDED/outlier 表述已统一。

新增 13 项显式待补引用登记。未虚构作者、出处或文献标识，也未在本轮补做检索。

完成 7 图、4 表、22 个图表文件的存在性、格式和 WRITE-2 hash 追溯检查，并为 WRITE-4 最终文件生成 SHA-256 交付清单。

## 权威输入与数据边界

唯一实验权威为 FORMAL-3、FORMAL-4、FORMAL-5 及 WRITE-1/2/3 冻结产物。本轮未重新扫描原始目录、导入数据、计算统计量、筛选样本或生成图表。

72 ACTIVE、19 EXCLUDED 和 10 个 outlier flags 保持不变。数据来源仍为真实实验，但最终资格保持 `scientifically_eligible=false`。

`final_test_read=false`，final-test 保持 sealed。本轮没有读取、引用或提交任何 final-test 内容。

## 结论边界

最终 disposition 保持 `supported_with_limits`，H0 保持 `not_rejected`，H1 保持 `not_confirmed`。

允许报告超过 CONT 重复性底线的方向相关频响变化、U4ENC 更高的点估计、AS01 可测配置差异和分类未达到 0.50 目标。

不得宣称 H1 已确认、U4ENC 已证明优于 U4SYM、方向可可靠分类、AS01/AS02 具有因果差异、绝对 SPL 校准或消声环境。

## 修改文件

- `docs/dissertation/EXPERIMENTAL_CHAPTERS_FINAL.md`
- `docs/dissertation/FINAL_CITATION_REQUIREMENTS.md`
- `docs/dissertation/FINAL_CONSISTENCY_AUDIT.md`
- `docs/dissertation/FINAL_DELIVERY_MANIFEST.json`
- `docs/progress/WRITE-4_FINAL_DELIVERY.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`
- `tests/test_dissertation_write4.py`

## 验证

- 初始 TDD 红灯：5 failed，缺少 WRITE-4 交付文件，符合预期。
- 相关回归：30 passed。
- WRITE-4 专项：5 passed。
- 全量 pytest：918 passed。
- `python -m compileall -q src scripts`：passed。
- `git diff --check`：passed。
- WRITE-2 资产：7 个图组、14 个 PNG/SVG；4 个表组、8 个 CSV/Markdown；全部 hash 匹配，PNG 至少 300 dpi。

## 已知限制

13 个外部方法或背景主张仍需后续人工检索和核验文献。添加引用不得改动冻结数值、样本边界或 claim boundary。

本文档是 Markdown 交付，不包含最终学校模板排版、参考文献库或语言润色签核。本轮不增加新的分析轮次。

## Git

本报告、最终章节、审计、manifest 和专项检查将在同一提交中保存，提交标题为 `docs(dissertation): finalize experimental chapters delivery`。不 push，不创建 tag/release，不合并分支。

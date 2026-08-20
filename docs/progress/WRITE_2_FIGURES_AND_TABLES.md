# WRITE-2：论文正式图表与结果表格

状态：完成；由冻结 FORMAL-3/4/5 产物生成论文图表，不重新估计统计量

日期：2026-08-20

分支：`feature/v2-dual-input`

## 目标与验收边界

本轮把 WRITE-1 的图表计划落实为有限的论文资产集：7 张图、4 张表；每张图提供 PNG（300 dpi）和 SVG，每张表提供 CSV 和 Markdown。`RESULTS_DRAFT.md` 已引用实际产物，图表编号、双语标题/图注、冻结来源、可复现脚本和输出 SHA-256 由统一 manifest 记录。

未重新导入 TXT、重新扫描原始数据、修改 72 ACTIVE/19 EXCLUDED、移除 10 条 outlier flags、重新估计冻结统计量、搜索模型、调整阈值或读取 final-test。冻结裁决保持：

```text
disposition=supported_with_limits
H0=not_rejected
H1=not_confirmed
scientifically_eligible=false
final_test_read=false
```

## 权威输入与 hash

生成器只接受 FORMAL-3、FORMAL-4、FORMAL-5 权威目录，并在作图前调用既有 authority/hash verifier。冻结 manifest SHA-256：

- FORMAL-3：`9aa329a730066f4487ac4a77f8700dca40862fec71a46d53817a7dc4d8d9e850`；
- FORMAL-4：`6744b7142480a20a631ff6a33f763329e852b4086ba5f05d53301beb6853d4ef`；
- FORMAL-5：`2134cd1d42de0ac136dd41d1a30b71f049835a822a17b9f88ed41d8fd76bc907`。

输入 provenance 为 `real_experiment/research_analysis/research_analysis`。`scientifically_eligible=false` 是 FORMAL-5 的冻结结论边界，不表示程序失败，也未被本轮提升。

## 生成方法与设计约束

新增 `acoustic_encoder.dissertation_assets` 作为只读论文资产生成边界，CLI 为：

```powershell
python scripts/build_dissertation_results_assets.py
```

生成器执行以下门禁：

- 固定源 artifact SHA-256 和 FORMAL-3/4/5 manifest verifier；
- 核对 72 ACTIVE、19 EXCLUDED、10 flags，禁止 selection change；
- 核对核心冻结数值与 FORMAL-5 claim boundary；
- 拒绝覆盖既有图表或 manifest；
- 以临时 staging 完成输出，验证后再移动到目标目录；
- PNG 至少 300 dpi 且不少于 1200 × 900 pixels；SVG 必须可解析；
- 每项输出记录 SHA-256、大小、源 artifact 和 reproduction script。

坐标轴从零或物理合理的完整范围开始；置信区间和参考线完整显示。AS02、AS01–AS02 与 all-assembly 信息保持 `exploratory`；0.50 分类目标和 0.25 chance 同时显示。图形没有通过截断坐标夸大差异。

## 实际生成物

图目录：`docs/dissertation/figures/`

1. Figure 1：CONT 重复性底线；
2. Figure 2：AS01 各 block 的方向频谱；
3. Figure 3：方向对相对 CONT p95 的效应；
4. Figure 4：U4SYM/U4ENC G、95% CI 与 ΔG；
5. Figure 5：配置差值曲线，AS02 明确标为 exploratory；
6. Figure 6：10 个 outlier flags 的敏感性；
7. Figure 7：grouped classification、chance 与 0.50 目标。

表目录：`docs/dissertation/tables/`

1. Table 1：主/次/全频带重复性底线；
2. Table 2：G_raw、G_demeaned、G_zscore、95% CI 与 ΔG；
3. Table 3：AS01 grouped classification；
4. Table 4：outlier-flag sensitivity，包括 AS01 effect/floor=`1.5688`。

生成总数为 14 个图文件和 8 个表文件。完整逐文件 hash 位于：

- `docs/dissertation/FIGURE_AND_TABLE_MANIFEST.json`：`a2c67184bd0c5065bbb848a36fd3d9edec8e4d7ba8883351f8b7d7331d02bbee`；
- `docs/dissertation/FIGURE_AND_TABLE_MANIFEST.md`：`db9f33be421edf44c8bcf884bf3997bd53f10bc9de9fdded6584b5c9deaf2ab6`。

## 冻结数值与图表覆盖

- 主频带 CONT floor：median `0.3783 dB`、IQR `0.2191 dB`、p95 `0.8793 dB`；
- U4ENC `G_demeaned=1.2805`，95% CI `0.8297–1.7667`；
- U4SYM `G_demeaned=0.6824`，95% CI `0.6105–1.2699`；
- `ΔG=0.5982`，95% CI `-0.1131–1.0843`，区间跨 0；
- U4ENC 6/6、U4SYM 3/6 AS01 方向对在两个 REPOS blocks 中超过 CONT p95；
- AS01 configuration effect/floor ratio=`1.5688`；
- U4SYM/U4ENC AS01 balanced accuracy=`0.375/0.250`，均未达到 `0.500`。

这些数字由冻结 CSV 直接读取并格式化，没有重新估计。图表不支持“U4ENC 已证明优于 U4SYM”或“可可靠分类四个方向”的表述。

## 修改文件

- 新增：`src/acoustic_encoder/dissertation_assets.py`；
- 新增：`scripts/build_dissertation_results_assets.py`；
- 新增：`tests/test_dissertation_assets.py`；
- 更新：`.gitattributes`，固定 SVG 为 UTF-8/LF 文本以保持跨平台 hash；
- 新增：`docs/dissertation/figures/` 下 14 个图文件；
- 新增：`docs/dissertation/tables/` 下 8 个表文件；
- 新增：`docs/dissertation/FIGURE_AND_TABLE_MANIFEST.md/.json`；
- 更新：`docs/dissertation/RESULTS_DRAFT.md`；
- 更新：`docs/dissertation/RESULTS_CLAIM_CHECKLIST.md`；
- 新增：本报告；
- 更新：`docs/progress/INDEX.md`。

没有修改 schema、分析配置、ACTIVE/EXCLUDED manifest 或 FORMAL-3/4/5 权威输出。

## 实际验证

WRITE-2 专项：

```powershell
python -m pytest -q tests/test_dissertation_assets.py
```

最终代码状态结果：`4 passed in 0.84s`。

FORMAL-3/4/5 相关回归（含 WRITE-2）：

```powershell
python -m pytest -q tests/test_dissertation_assets.py tests/test_formal_final_synthesis.py tests/test_formal_core_analysis.py tests/test_formal_real_import_qc.py
```

结果：`26 passed in 22.91s`。

全量回归：

```powershell
python -m pytest -q
```

最终代码状态结果：`909 passed in 274.33s (0:04:34)`。（此前同轮完整运行亦均为 909 passed。）

其余验证：

```powershell
python -m compileall -q src scripts
python -c "... verify_dissertation_assets(Path('docs/dissertation'))"
git diff --check
```

结果：compileall 无错误；asset verifier 返回 `all_match=True`、7 figure groups/14 files、4 table groups/8 files、minimum PNG dpi=300；`git diff --check` 无输出、退出码 0。七张 PNG 均完成目视检查；热图色条、单位、标签、边界、参考线和 exploratory 标记可读且无遮挡。

## 已知限制与下一步

- Figure 2 是对 FORMAL-4 冻结 block panels 的受控组合，未重新绘制或改变其统计内容；
- 图中英文标题以英文排版为主，manifest 同时提供中英文标题/图注，最终论文可选择其中一种；
- `RESULTS_CLAIM_CHECKLIST.md` 的 WRITE-2 自动检查已完成，但最终排版后的人工数字、交叉引用和摘要边界检查仍保持未勾选；
- `scientifically_eligible=false`、final-test sealed、H0/H1 与 `supported_with_limits` 均未改变。

下一阶段只能进行论文排版、语言编辑和人工交叉引用检查；若图表内容或冻结数值发生变化，必须重新通过 manifest/hash 和 claim checklist，不得在写作阶段重启分析选择。

对应本地提交：`docs(dissertation): add formal results figures and tables`。本轮不 push、不创建 tag/release。

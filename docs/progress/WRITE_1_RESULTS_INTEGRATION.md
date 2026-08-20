# WRITE-1：论文 Results 章节整合

状态：完成；文档整合，不改变冻结分析或结论

日期：2026-08-20

分支：`feature/v2-dual-input`

## 目标与边界

本轮把 FORMAL-3、FORMAL-4 和 FORMAL-5 的冻结结果整理为论文 Results 初稿、图表安排和 claim 检查表。

没有重新导入 TXT、扫描原始目录、运行新分析、修改 72 ACTIVE/19 EXCLUDED、删除 10 条 outlier flags、调整阈值、搜索模型或读取 final-test。

冻结裁决保持不变：

```text
disposition=supported_with_limits
H0=not_rejected
H1=not_confirmed
scientifically_eligible=false
final_test_read=false
```

## 权威输入核验

WRITE-1 开始前重新核验：

- FORMAL-3：72 ACTIVE、19 EXCLUDED、72 FeatureSets、255 个共同有效点、10 flags；`225/225` artifact hash 匹配；
- FORMAL-4：`ready_for_formal_synthesis=true`；`28/28` artifact hash 匹配；
- FORMAL-5：`supported_with_limits`；六项业务产物 `6/6` hash 匹配；
- final-test 在 FORMAL-3/4/5 中均为 unread/sealed。

权威 manifest SHA-256：

- FORMAL-3 artifact manifest：`9aa329a730066f4487ac4a77f8700dca40862fec71a46d53817a7dc4d8d9e850`；
- FORMAL-4 artifact manifest：`6744b7142480a20a631ff6a33f763329e852b4086ba5f05d53301beb6853d4ef`；
- FORMAL-5 artifact manifest：`2134cd1d42de0ac136dd41d1a30b71f049835a822a17b9f88ed41d8fd76bc907`。

## Results 结构

章节按证据依赖顺序编排：

1. 样本、频带和报告边界；
2. CONT 重复性底线；
3. 方向相关频谱差异；
4. U4ENC–U4SYM 配置差异；
5. AS01/AS02 探索性观察；
6. grouped direction classification；
7. outlier-flag 敏感性；
8. 冻结综合裁决。

该顺序先建立测量误差基线，再解释方向和配置效应。确认性不足、分类负结果和探索性边界均与描述性结果分开。

## 冻结核心结果

- 主频带 CONT floor：median `0.3783 dB`、IQR `0.2191 dB`、p95 `0.8793 dB`；
- U4ENC `G_demeaned=1.2805`，95% CI `0.8297–1.7667`；
- U4SYM `G_demeaned=0.6824`，95% CI `0.6105–1.2699`；
- `ΔG_demeaned=0.5982`，95% CI `-0.1131–1.0843`；
- U4ENC 6/6、U4SYM 3/6 方向对稳定超过 CONT p95；
- AS01 median configuration effect/floor ratio=`1.5688`；
- AS01 U4SYM/U4ENC balanced accuracy=`0.375/0.250`，均低于 `0.500`；
- 10 flags 的 sensitivity analysis 未改变冻结裁决或样本选择。

每项数字均在 `RESULTS_DRAFT.md` 中使用证据 key 连接到具体 FORMAL-3/4/5 文件及 SHA-256。

## 输出文件

- `docs/dissertation/RESULTS_DRAFT.md`
  - SHA-256：`963ca993bc59aa062024feca9a8fcd948826f097395718ebef7ebf8c09645ef1`
- `docs/dissertation/FIGURE_PLAN.md`
  - SHA-256：`f67345947006f2aa6539a0dc915c35e4586eac8dc20af839a744439ee5d05ef9`
- `docs/dissertation/RESULTS_CLAIM_CHECKLIST.md`
  - SHA-256：`5f3d206dc6dad1db0618dbc3ac5df3b698d1890e64afcaccd7db9bbeab6fc714`
- `docs/progress/WRITE_1_RESULTS_INTEGRATION.md`
- `docs/progress/INDEX.md`

没有复制或重新生成 FORMAL-4 图。图表计划只安排现有七类图，并记录每个源图的 SHA-256、用途、放置位置和禁止解释。

## Claim 边界

允许写入论文：存在超过技术重复底线的方向相关频谱变化；U4ENC 的方向性点估计较高；AS01 有可测配置差异；分类未达目标是正式负结果。

禁止写入：U4ENC 已证明优于 U4SYM、四方向可可靠分类、AS01/AS02 存在无混杂因果差异、flags 已被删除、final-test 或部署泛化已验证。

AS02、AS01/AS02 比较、all-assembly classification 和 4–8 kHz 均保持 exploratory/secondary 标签。

## 实际验证

权威 artifact 复核：

```powershell
python -c "... verify_formal3_authority(...); verify_formal4_output_hashes(...); verify_formal5_output_hashes(...)"
```

结果：FORMAL-3 `225/225`、FORMAL-4 `28/28`、FORMAL-5 `6/6` 均匹配。

相关回归：

```powershell
python -m pytest -q tests/test_formal_final_synthesis.py tests/test_formal_core_analysis.py tests/test_formal_real_import_qc.py
```

结果：`22 passed in 31.01s`。

文档段落检查确认 Results/figure/checklist 的普通段落不超过 240 字符。`git diff --check` 无输出、退出码 0。

## 已知限制与后续使用

本轮是章节初稿，不是最终排版稿。图号、交叉引用和术语可在论文整体编辑时统一，但任何编辑都不得改变数字、CI、sample boundary、disposition 或 claim class。

最终排版前应再次执行 `RESULTS_CLAIM_CHECKLIST.md` 中未勾选的人工检查，并复核已排版图文件的 SHA-256。

对应本地提交：`docs(dissertation): integrate frozen formal results`。本轮不 push、不创建 tag/release。

# DEV-UI4-FIX7：Sparse Multisine 路线安全收尾与报告出口

状态：实现与提交前验证完成；等待从本步 clean commit 重建 Windows one-folder

日期：2026-08-13

分支：`feature/v2-dual-input`

科研资格：`data_origin=simulated`、`dataset_role=software_validation`、`run_purpose=software_validation`、`scientifically_eligible=false`。本步未读取 final-test，未开放真实 Multisine/P8，不能用于科研结论、canonical analysis、deployment 或真实 freeze。

## 目标与验收范围

FIX6 已把显式 32 样本计划运行到步骤 07，并得到 `32/32 expected_and_present`、`P2-B=not_applicable_sparse` 和 `downstream_route=tone_p8_dataset_quality`。FIX7 对该 sparse-only 软件验证路线做安全收尾：步骤 08/09 不再误导为待运行，步骤 10/11 保持冻结/封存，步骤 12 可以从唯一 hashed workflow state 的显式引用链生成非科研总结。

本步不增加科研算法，不构造 dense FeatureSet，不伪造 P2-B/P4/P5 pass，不更改 P1～P9、QC、provenance、canonical 或 final-test 门禁。

## 完成内容

### 下游状态与页面

| 步骤 | FIX7 状态 | 安全含义 |
|---|---|---|
| 01～07 | `passed` | 仅表示模拟练习链和显式完整性审计通过 |
| 08 | `not_applicable` | sparse 路线没有 canonical P4/P5/P6 authority；FeatureSet-only 控件禁用 |
| 09 | `not_applicable` | 不获得分类、选频或校准资格 |
| 10 | `blocked` | 没有批准的 P9-D/freeze authority |
| 11 | `sealed` | `final_test_read=false`，无读取、解封或执行入口 |
| 12 | `ready` | 只允许导出 software-validation 总结 |

UI-owned `StepStatus` 增加 `not_applicable` 和 `sealed`，不修改科研 schema。侧边栏分别显示“不适用（安全跳过）”和“已封存（未读取）”，状态不只依靠颜色。步骤 08 页面显示 32/32、P2-B applicability、下游 route 和 authority 缺失，并只提供打开当前显式审计 manifest 的按钮。步骤 09～11 的不适用/阻塞控件保持禁用。

### 软件验证总结

步骤 12 新增“生成并导出软件验证总结”。服务只读取：

`workflow_state.json + workflow_state.sha256 -> plan manifest -> stimulus hash index/manifest -> acquisition manifest -> processing manifest -> dataset audit`

所有路径都来自 state 或被引用 manifest；每次读取复核 SHA-256，不递归扫描 `outputs`，不按文件名猜测身份。输出拒绝覆盖，位于：

- `outputs/ui_simulated_flow/closeout_reports/<unique-report-id>/software_validation_summary.md`
- `outputs/ui_simulated_flow/closeout_reports/<unique-report-id>/software_validation_summary.json`
- `outputs/ui_simulated_flow/closeout_reports/<unique-report-id>/software_validation_summary.sha256`

Markdown/JSON 同时记录步骤 01～12、32/32、warning=0、failed=0、实际 plan revision（验收覆盖 `rev-002`）、四级显式 manifest/hash、`simulated/software_validation`、`scientifically_eligible=false`、`final_test_read=false` 以及“不可用于科研结论”。

### 状态恢复和 UAT 修复

- 重启只读取唯一 `workflow_state.json` 及其 SHA-256，并按显式 pointers 恢复步骤 01～12、plan revision 和步骤 04～07 artifacts；测试放置了未引用 decoy manifest，未被认领。
- 新 plan revision 自动绑定步骤 04，清空旧 revision 的下游 UI pointers/status；旧原始产物不移动、不复制、不删除。
- 相同 P7 契约的新 revision 可复核并复用已有不可变刺激；原始 creation binding 不改写，每个刺激 artifact hash 必须完整匹配。
- 缺少 `revision_reason` 时显示准确的修订理由提示。
- P7 契约不一致提示首个具体 `field`、`expected` 和 `actual`。
- 模拟步骤失败后，下一步建议要求修复当前错误，不再提示继续外部采集。

## 修改文件

- `src/acoustic_encoder/ui/state.py`
- `src/acoustic_encoder/ui/main_window.py`
- `src/acoustic_encoder/ui/sparse_closeout_page.py`
- `src/acoustic_encoder/ui/simulated_flow.py`
- `src/acoustic_encoder/ui/services.py`
- `tests/test_ui4_fix7_sparse_route_closeout.py`
- `docs/progress/DEV-UI4_FIX7_SPARSE_ROUTE_CLOSEOUT.md`
- `docs/progress/INDEX.md`
- `README.md`
- `CHANGELOG.md`

## Schema、API 与数据权威

科研 schema、config schema、`MeasurementMeta`、`SpectrumData`、`FeatureSet`、P2-B 和 P1～P9 API 均未改变。仅扩展 UI presentation enum，并增加 UI application-service API：

- `SimulatedFlowService.apply_sparse_closeout(...)`
- `SimulatedFlowService.export_software_validation_summary(...)`
- `SoftwareValidationSummary`

总结 JSON schema 为 UI-owned `1.0.0`，只引用后端权威 artifacts，不成为第二套 QC、phase、provenance 或科研资格权威。

## TDD 与实际验证

RED 阶段依次复现：缺少 `not_applicable/sealed` 状态、缺少 sparse route 应用、缺少安全页面、缺少总结 exporter、总结按钮未接线、新 revision 保留 stale failed、revision/P7 错误过度泛化，以及同一不可变刺激无法安全复核。每项先有失败测试，再做最小实现。

实际执行结果：

- `python -m pytest tests/test_ui4_fix7_sparse_route_closeout.py -q`：`8 passed in 19.98s`。
- `python -m pytest tests/test_ui4_fix6_simulated_flow.py -q`：`11 passed in 75.66s (0:01:15)`。
- `python -m pytest -q`：`840 passed in 220.57s (0:03:40)`。
- `python -m compileall -q src scripts tests`：exit 0，无输出。
- 源码 offscreen smoke：`python scripts/run_gui.py --smoke-test --workspace "build/fix7 source smoke 中文"`，exit 0。
- `git diff --check`：提交前最终复核要求 exit 0、无 whitespace error。

以上不包含尚未执行的 clean-commit Windows 构建结果。正式 one-folder 只能在本报告所在提交创建且工作树 clean 后构建；EXE 路径、SHA-256 和 dist smoke 在最终交付回复中报告，不在此预先声称。

## 已知边界与真实数据替换方法

- FIX7 只收尾 clean 的 32 样本 sparse simulated route；warning、failed、缺失、重复、hash 不一致或 route 不匹配不能进入该状态。
- P2-B 仍要求兼容 dense FeatureSet cohort；`not_applicable_sparse` 不是 pass。
- 真实数据替换必须创建 `data_origin=real_experiment` 的新显式计划、完成批准的设备/采集/provenance/QC 门禁，并在 DEV-D 独立批准真实 Multisine/P8；不得修改本模拟 state、复制模拟 sidecar 或把 software-validation 总结改名冒充科研报告。
- 真实 P9-D/freeze authority、canonical P4/P5/P6、final-test approval 和科研资格仍未获得。
- 本轮是最终 UI 收尾轮次；后续只能进行获批的 DEV-D 真实诊断准备或缺陷修复，不得借 UI 扩展绕过既有研究门禁。

## Git 与构建边界

本报告和实现置于同一个本地提交，建议标题：`fix(ui): close sparse validation route safely`。正式构建必须证明 `source_git_dirty=false`、`software_integration_ready=true` 和 `final_test_read=false`。不 push，不创建 tag/release。

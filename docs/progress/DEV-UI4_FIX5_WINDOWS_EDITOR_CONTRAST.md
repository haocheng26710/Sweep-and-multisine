# DEV-UI4-FIX5：Windows 表格编辑器与安全状态对比度修复

状态：实现与提交前验证完成；正式 Windows 包须从本报告所在 clean commit 重建

日期：2026-08-13

分支：`feature/v2-dual-input`

科研资格：无变化；本轮仅修复 Qt 显示样式，`scientifically_eligible=false`、真实 Multisine/P8 blocked、final-test sealed

## 缺陷与目标

Windows 11 人工验收确认 Qt `windows11` 样式存在控件级调色板异常：应用和 `QTableWidget` 为白底黑字，但表格内 `QComboBox`、其 popup view 和动态 `QLineEdit` 编辑器可得到 `Base=#000000`、`Text=#000000`。步骤 03 安全清单因而无法读出当前 status；其他表格单元格进入编辑状态时同样不可读。该缺陷使人工安全声明不可验证，不能依靠 DPI、Windows 缩放或专业模式规避。

目标是在创建 `MainWindow` 及任何页面之前建立一个一致、集中且可测试的可读 Qt 样式，同时覆盖 combo 闭合态、popup、表格动态编辑器，以及正常、焦点、选中和禁用状态。修复不得改变实验计划字段、安全声明语义、算法、schema、provenance 或科研门禁。

## 实现

- 在公开桌面窗口创建边界增加 `apply_readable_application_style(QApplication)`。
- Windows 且当前 Qt 样式名为 `windows11` 时，在创建 `MainWindow` 前切换到 `Fusion`；其他平台和其他显式样式保持不变。
- 在 Fusion 上集中设置应用级浅色调色板，而不是为安全清单 status 写局部 stylesheet。
- Active/Inactive 的 Window、Base、Text、Button、ButtonText、Highlight、HighlightedText 和 tooltip roles 使用明确前景/背景。
- Disabled 使用独立的深灰文字、浅灰背景及深灰选中背景，回归测试要求至少 `3.0:1`；正常文字要求至少 `4.5:1`，选中态至少 `3.0:1`。
- 因调色板在应用级设置，新建的 `QComboBox`、popup view 和 delegate 动态 `QLineEdit` 编辑器均继承同一策略。
- status 的四个既有值保持不变：`not_recorded`、`declared_pass`、`declared_unavailable`、`declared_fail`。

## TDD 证据

第一个 RED：将真实 `QApplication` 设为 `windows11` 后，通过 `create_main_window` 创建页面，样式仍是 `windows11`；测试以 `AssertionError: 'windows11' != 'fusion'` 失败。最小实现是在窗口构造前切换 Fusion，随后该测试 GREEN。

第二个 RED：Fusion 已消除黑底黑字，但默认 disabled `ButtonText/Button` 对比度只有 `1.6164:1`，低于本步定义的 `3.0:1`。随后增加集中式 disabled palette，完整控件测试 GREEN。

确定性诊断测试使用 object name 为 `windows11` 的代理样式，先证明 combo 与动态 editor 的 Base/Text 同为 `#000000`，再调用公开窗口入口，确认页面创建前切换为 Fusion 且实际安全清单控件恢复明确对比。该测试不依赖机器主题恰好触发原生缺陷。

## 覆盖行为

- Windows `windows11` 样式在页面创建前切换 Fusion。
- 黑底黑字 combo 与动态 editor 缺陷可确定性复现并被入口修复。
- combo 闭合态 Button/ButtonText 可读。
- popup Base/Text 与 Highlight/HighlightedText 可读。
- 动态 `QLineEdit` Base/Text 与选中态可读。
- Active、Inactive、Disabled 的前景/背景满足测试阈值。
- popup 四项均存在且同时可见。
- 鼠标点击、键盘 Down 和鼠标滚轮依次选择后，`currentText` 正确且持续可读。
- DEV-UI4-FIX4 的 1280×720、1920×1080、100%/125%/150% 布局回归继续通过。

## 修改文件

- `src/acoustic_encoder/ui/app.py`
- `tests/test_ui4_fix5_windows_editor_contrast.py`
- `docs/progress/DEV-UI4_FIX5_WINDOWS_EDITOR_CONTRAST.md`
- `docs/progress/INDEX.md`
- `CHANGELOG.md`

## schema、API 与科研边界

新增的 UI application helper 只接收现有 `QApplication` 并返回最终 style name。没有修改 P1～P9、配置 schema、实验计划 schema、安全清单 check/status 定义、保存逻辑、MeasurementMeta、QC、provenance、research gate 或 final-test gate。真实 Multisine/P8 仍 blocked，模拟验收仍为 `simulated/software_validation/scientifically_ineligible`。

## 实际提交前验证

- FIX5 专项：`3 passed in 0.51s`。
- FIX5 + FIX4 + UI3 页面 + UI 启动/主窗口：`23 passed in 1.30s`。
- UI 专项（100%）：`173 passed, 648 deselected in 21.81s`。
- FIX4 + FIX5（125%）：`6 passed in 0.67s`。
- FIX4 + FIX5（150%）：`6 passed in 0.72s`。
- 全量 pytest：`821 passed in 127.28s (0:02:07)`。
- `python -m compileall -q src scripts tests`：exit 0，无输出。
- `git diff --check`：exit 0，无 whitespace error。
- 源码 offscreen GUI smoke：exit 0。

以上均为实际运行结果。正式 clean-provenance EXE 只能在本步提交后构建，因此本报告不预先填写 EXE hash 或打包验收结果；最终交付回复引用实际 dist 和 acceptance artifacts。

## 正式构建后验收门槛

从本报告所在 clean commit 运行 `scripts/build_windows_gui.ps1`。要求构建前后 Git clean，发布 manifest 与 acceptance 指向同一 commit，`source_git_dirty=false`；新 EXE 在源码目录外和含空格/中文工作区 smoke 通过；打包版模拟验收 T0～T3 pass、V2 14/14、`software_integration_ready=true`、`ready_for_dev_d_diagnostic_experiment=true`、`final_test_read=false`、`scientifically_eligible=false`。

## 已知限制

本轮修复 Windows 11 Qt 编辑器绘制，不改变操作系统高对比度主题或提供用户主题选择。回归以颜色角色和 WCAG 对比度公式验证控件语义状态，并以 offscreen 覆盖布局/DPI；最终 one-folder 仍须在 clean commit 后实际启动。本轮不授予真实实验、部署、科研结论或 final-test 权限，不创建 tag/release，也不 push。

对应 Git commit：本报告与 FIX5 实现放入同一提交，正式 EXE 必须由该 clean commit 构建。

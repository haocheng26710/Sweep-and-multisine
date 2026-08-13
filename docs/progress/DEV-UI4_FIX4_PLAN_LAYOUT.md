# DEV-UI4-FIX4：步骤 03 实验计划布局与可访问性修复

状态：实现与提交前验证完成；正式 Windows 包须从本报告所在 clean commit 重建

日期：2026-08-13

分支：`feature/v2-dual-input`

科研资格：无变化；本轮仅 UI 布局，`scientifically_eligible=false`、真实 Multisine/P8 blocked、final-test sealed

## 缺陷与目标

Windows 人工验收在 1920×1080 全屏、简易模式下发现步骤 03 的基本信息、条件 blocks 和安全清单被主窗口纵向布局压缩。页面有可用空间，但 `QStackedWidget` 未获得明确伸展权重，页面自身没有滚动容器，底部执行结果和末尾 stretch 共同挤占关键编辑区域。

目标是在简易模式直接完成实验计划：基本信息标签/字段完整存在且可通过页面滚动访问；条件表同时容纳表头和至少三行，横向/纵向按像素滚动；增删按钮位于表格外独立操作行；安全清单同时容纳表头和至少三行并可滚动；底部结果缩小但仍可滚动阅读。

## 完成内容

- 为 `ExperimentPlanPage` 增加 `QScrollArea` 主滚动区，内容超高时整页滚动，不再压扁内部控件。
- 将基本信息、条件 blocks、安全清单保存为明确页面组件；`QFormLayout` 允许输入字段横向扩展。
- 两个表格固定为三行可编辑视口高度，并预留支持 150% 字体/DPI 的样式余量。
- 表格使用 `ScrollPerPixel`，水平/垂直滚动条按需显示；条件达到第四行后出现垂直滚动。
- “增加条件 block”“删除选中 block”保留在独立按钮行，几何区域不与表格/滚动条重叠。
- 主窗口将 `action_stack` 设为主要伸展区域；移除吞噬空间的末尾 stretch。
- “执行结果”限制为较小高度并放入独立滚动区，内容仍可选取和查看。
- 简易/专业模式、现有工作区解析、计划字段、保存 revision、状态机和后端调用均未改变。

## 修改文件

- `src/acoustic_encoder/ui/plan_page.py`
- `src/acoustic_encoder/ui/main_window.py`
- `tests/test_ui4_fix4_plan_layout.py`
- `docs/progress/DEV-UI4_FIX4_PLAN_LAYOUT.md`
- `docs/progress/INDEX.md`
- `CHANGELOG.md`

## schema、API 与科研边界

没有算法、科研 schema、配置、计划字段、实验语义、QC 或 provenance 变化。没有新增绕过按钮；真实 Multisine/P8 与 final-test 门禁完全不变。窗口仍通过现有 `RuntimeContext` 使用用户工作区，因此换用新 EXE 后可继续指定 `D:\Bristol course\dissertation\UI_acceptance_workspace`，不会移动或改写既有数据。

## TDD 与布局测试

RED：新的公开界面行为测试首先因页面没有 `plan_scroll_area` 失败；随后通过真实几何检查发现条件表四行时没有垂直滚动，以及 150% 字体下表格最小高度少 2 个逻辑像素。逐项修正后 GREEN。

offscreen 回归覆盖：

- 1280×720 / 100% 字体比例；
- 1280×720 / 125% 字体比例；
- 1920×1080 / 150% 字体比例；
- 基本信息全部字段及对应标签可见；
- 两表最小高度不少于表头、三行、水平滚动条和 frame；
- 条件表水平滚动、安全表垂直滚动、第四个条件 block 的垂直滚动；
- 增删按钮不与表格重叠；
- 简易模式下 plan 主区大于结果区，结果区可滚动。

## 实际验证结果

- FIX4 + UI3 页面 + 主窗口：`19 passed in 0.97s`。
- UI 专项（100%）：`170 passed, 648 deselected in 20.13s`。
- FIX4 125%：`3 passed in 0.46s`。
- FIX4 150%：`3 passed in 0.45s`。
- 全量：`818 passed in 198.21s (0:03:18)`。
- `python -m compileall -q src scripts tests`：exit 0，无输出。
- `git diff --check`：exit 0，无 whitespace error。
- 源码 offscreen GUI smoke：exit 0。

以上均为提交前实际运行结果。clean provenance Windows EXE 必须在本步提交后生成，因此不在提交前伪造其 hash、commit 或 acceptance 结果；最终回复将引用实际 dist/build/acceptance artifact。

## 正式构建后验收门槛

从本报告所在 clean commit 运行 `scripts/build_windows_gui.ps1`，并验证：构建前后工作树 clean；EXE provenance 指向该 commit；在全新工作区及既有 `UI_acceptance_workspace` 启动成功；environment passed；T0～T3 pass；V2 14/14；`software_integration_ready=true`；`ready_for_dev_d_diagnostic_experiment=true`；`final_test_read=false`；`scientifically_eligible=false`。

## 已知限制

Qt offscreen 测试以逻辑分辨率和字体倍率覆盖 100%/125%/150% 布局约束；最终 Windows one-folder 仍需实际启动 smoke。此修复不代表真实实验数据、科研结论、部署批准或 final-test 授权。未创建 tag/release，且按要求不 push。

对应 Git commit：本报告与 FIX4 实现放入同一提交，正式 EXE 必须由该 clean commit 构建。

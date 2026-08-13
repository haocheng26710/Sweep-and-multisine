# DEV-UI4-FIX3：Windows clean-build provenance 与最终软件验收

状态：实现与提交前验证完成；正式发布包必须在本报告所在 clean commit 创建后构建

日期：2026-08-13

分支：`feature/v2-dual-input`

科研资格：仅 `simulated` / `external_reference` + `software_validation`；`scientifically_eligible=false`；final-test sealed

## 目标与验收标准

修复 FIX2 发布包把 dirty worktree 的旧 commit 写入 `build_verification.json`，导致 T0～T3 与 V2 虽通过但 `software_integration_ready=false` 的发布流程缺陷。正式构建必须先证明 source clean，在构建期间保持同一 HEAD，把动态验证文件只写入忽略的 staging/build/dist，并使 build verification、build manifest 和打包版 acceptance 共享同一 source commit、`git_dirty=false`。

本轮不修改 P1～P9 科研算法、核心 schema、QC、provenance hard gate、`scientifically_eligible` 判定、真实 Multisine/P8 阻塞或 final-test seal。

## 完成内容与设计

正式入口 `scripts/build_windows_gui.ps1` 的第一项可失败操作是 `git status --porcelain`。非 clean source 立即以中文错误终止，尚未创建 staging 或启动 PyInstaller。clean source 的 commit、branch 在此时固定；验证完成后和 PyInstaller 完成后再次检查工作树与 HEAD，任一变化均失败。

`build_verification.json` 和运行时 `assets_manifest.json` 不再是源码树中的受跟踪动态文件。构建验证、日志、配置/文档副本和 manifest 生成到忽略的 `build/release_staging`。`SweepMultisineUI.spec` 只通过 `SWEEP_MULTISINE_RELEASE_STAGING` 获取动态验证资源；未通过正式脚本提供 staging 时拒绝构建。静态官方 REW TXT 保留为显式 validation assets，复制时不改字节并按原 manifest 校验。

新增 `release_build` application boundary，提供 clean source 捕获、构建结束复核、build-verification payload 和跨 build/acceptance provenance 审计。需要一致的字段为：构建开始 HEAD、`source_commit`、build manifest `source_commit/git_commit`、acceptance `git_commit`；所有 dirty 字段必须为 false。`final_test_read` 和 `scientifically_eligible` 必须继续为 false。

打包验证不在终端用户机器重新运行 pytest 或依赖 Git/source tests；它消费该 clean commit 构建期间实际执行且带 hash 的验证记录。窗口 worker 顶层异常边界、技术日志、环境/验收状态分离、长路径支持均保留。

## 修改文件

- `scripts/build_windows_gui.ps1`
- `scripts/build_acceptance_verification.py`
- `scripts/build_acceptance_assets.py`
- `SweepMultisineUI.spec`
- `src/acoustic_encoder/ui/release_build.py`
- `src/acoustic_encoder/pre_experiment_acceptance_runner.py`
- `tests/test_ui4_fix3_release_build.py`
- `tests/test_ui4_fix2_acceptance.py`
- `tests/test_ui4_packaging.py`
- `validation_assets/pre_experiment_acceptance/{assets_manifest.json,build_verification.json}`（从 Git 删除，改为 staging 动态产物）
- 本报告、`docs/progress/INDEX.md`、`CHANGELOG.md`

## schema、配置与 API

科研 schema/config 无变化。build/validation manifest schema 仍为 `1.0.0`。新增的 build-only API 不进入 SpectrumData、MeasurementMeta、FeatureSet 或 QC 权威对象。PyInstaller 新增环境输入 `SWEEP_MULTISINE_RELEASE_STAGING`，只由正式 PowerShell 构建入口设置。

## TDD 与提交前验证

实际 RED 证据包括：缺少 `release_build` 模块、缺少 source 稳定性复核、旧 asset builder 忽略 staging 参数、缺少 provenance audit，以及 PowerShell UTF-8 中文解析问题。逐项最小实现后转绿。

实际执行：

- FIX3/FIX2/UI 状态/final-test 专项：`21 passed in 2.72s`。
- 全量：`815 passed in 122.82s (0:02:02)`。
- `python -m compileall -q src scripts tests`：exit 0，无输出。
- `git diff --check`：exit 0，仅显示 Windows line-ending warning，无 whitespace error。
- source offscreen smoke：exit 0。
- dirty-source 正式构建实测：在当前未提交修改状态下立即输出“正式发布构建已中止：Git 工作树不干净……”，未启动验证或 PyInstaller。

这些结果是在提交前实际执行的结果；本报告不预先声称尚未进行的 post-commit 正式构建结果。

## 正式发布与权威输出

本轮后段必须从本实现的 clean commit 执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows_gui.ps1
```

权威发布证据为：

- `dist/SweepMultisineUI/build_manifest.json`
- `dist/SweepMultisineUI/SHA256SUMS.txt`
- `dist/SweepMultisineUI/_internal/validation_assets/pre_experiment_acceptance/build_verification.json`
- 全新工作区的 `acceptance/acceptance_manifest.json`
- 全新工作区的 `acceptance/experiment_readiness.json`

它们必须共同证明 T0～T3 pass、V2 14/14、`software_integration_ready=true`、`ready_for_dev_d_diagnostic_experiment=true`、所有 dirty 字段 false、`final_test_read=false`、`scientifically_eligible=false`。准确 EXE hash 和验收目录只有在 clean commit 后才能真实产生，因此不在提交前伪造，将在最终交付回复中按上述 artifact 报告。

## 已知限制与下一步

clean 软件集成 ready 只允许进入受控 DEV-D diagnostic preparation，不是科研资格、部署批准、真实 calibration 或 final-test 授权。真实 Multisine/P8 仍 blocked；final-test 仍 sealed。未创建 installer、代码签名、tag、release 或 push。

对应主要 Git commit：本报告与 FIX3 源码放入同一提交，正式 EXE 必须绑定该 clean commit。

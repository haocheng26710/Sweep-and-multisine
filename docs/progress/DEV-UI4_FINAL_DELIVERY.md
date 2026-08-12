# DEV-UI4：冻结流程、final-test 安全入口、离线读取与 Windows 交付

状态：完成（本地软件验证；真实科研路径仍阻塞）

日期：2026-08-10

FIX1 更新：2026-08-12

分支：`feature/v2-dual-input`
提交：与本报告同一提交，标题 `feat(ui): complete frozen workflow and Windows delivery`

FIX1 提交：与本次修复同一提交，标题 `fix(ui): allow users to change workspace`

## 目标与完成范围

完成预定最后一轮 UI：正式 P9-A～P9-D adapter、冻结确认与 evidence、默认密封 final-test 状态机、frozen package 离线读取、source/frozen 共用 worker、只读资源/可写工作区分离、Windows PyInstaller one-folder、导航/进度/日志/关于页和中文用户文档。未复制或修改 P1～P9 数学算法、阈值、核心 schema 或研究 gate。

## 架构与调用映射

`RuntimeContext` 将 `resource_root` 与 `workspace_root` 分离；开发态 worker 为 `python scripts/run_gui.py --worker <task> -- ...`，打包态为 `SweepMultisineUI.exe --worker <task> -- ...`。QProcess 始终分离 program/argument，不拼 shell。dispatcher 直接调用现有 application service：P1/P8、P2-B、P4、P5-A/B、P6-A/B、P9-A/B/C、P9-D package、offline readout 和 DEV-C16 acceptance。

P9 页面要求显式 config/scope/input/candidate/P2-B/P4/P3-C/P9-A authority；不按文件名、最近修改时间或目录顺序配对。P9-A preview 可从显式用户选择写出 scope/input/candidate snapshot、SHA-256 和未确认 audit，拒绝 final-test。P9-B 缺 P9-A fold authority 即锁定；P9-C 缺正式 pairing authority 或涉及真实 Multisine 即锁定。

### DEV-UI4-FIX1 工作区修复

窗口顶部在简易/专业模式均显示“更换工作区”。`QFileDialog.getExistingDirectory` 的选择先通过“可创建目录并实际创建临时文件”的写入检查，再原子写入用户设置；取消或失败不改变当前选择。优先级固定为命令行 `--workspace` > 用户保存值 > `%LOCALAPPDATA%\SweepMultisineUI\workspace`。

切换采用重启生效策略：当前标签、所有页面、service 和 worker 在进程生命周期内继续绑定同一个旧 `RuntimeContext`；新路径只显示为“下次启动生效”。“立即重启”通过分离的 executable/arguments 传入 `--workspace`。任一任务运行时，选择和重启均被阻止并解释原因。程序不移动、复制或删除旧工作区数据，设置文件也不属于科研 artifact。

## 冻结与离线读取

P9-D 调用正式 `build_readout_package_from_manifest`，拒绝覆盖和 final-test training。成功后权威 loader 复核 package manifest、semantic hash、model、preprocessing、QC 和 artifact hash；UI 再写 `freeze_approval_record.json`、`package_validation.json`、`step_report.md/html`、`technical_log.txt` 与 `ui_freeze_artifacts.sha256`。任何变更必须创建新 package revision。

离线读取调用正式 `execute_offline_readout_from_manifest`。blocked/invalid/unavailable 不显示预测；warning 保留。界面解释 nearest-centroid score 越小越匹配，margin 是第二名与第一名的距离差而非概率。

## final-test 状态机

状态固定为 `sealed → approved_once → running → completed`，无返回或二次评估路径。解封前同时检查冻结计划/package、自检、scope、training/development 完成、保管人/独立批准/含时区时间、批准文件、plan ID、package hash 片段、一次性确认、空输出、版本、真实科研 authority、未处理 incident 和真实 Multisine 后端批准。缺任一条件时在读取内容/metadata/hash 前阻止，并写 attempted-access incident。当前 UI 不具备真实 authority，解封按钮保持禁用。

## 修改文件与 schema/API

新增 UI runtime/worker、P9、offline、final-test 和 final-delivery page 模块；更新 app/window、UI1～UI3 worker/path 边界和三个 P9-D source scripts；新增 `.spec`、PowerShell build recipe、build requirement、18 个 UI4 测试及五份文档。核心 pipeline/config/Measurement/FeatureSet schema 无变化。新增 UI-owned manifest/evidence schema 均为 `1.0.0`，不成为第二科学权威。

## Windows 构建

- 命令：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows_gui.ps1`
- EXE：`dist/SweepMultisineUI/SweepMultisineUI.exe`
- EXE SHA-256：`5cf8786bcfecdec3add4c3ff784b134ec84293b0cca914290e940223c238276f`
- Python `3.12.4`；PyInstaller `6.22.0`；PySide6 `6.8.3`
- SHA 清单：2533 项，复核失败 0；分发目录共 2534 个文件、945986004 bytes。

构建产物约 946 MB，来自功能完整的 Anaconda 构建环境；one-folder 较大但可诊断。`build/`、`dist/` 受 `.gitignore` 管理，不提交。FIX1 manifest 记录构建时 parent commit `49973abb...` 且 `git_dirty=true`，因为代码、测试、文档和重建证据在同一个本地提交边界内；这不提升科研资格。

## 验证结果

FIX1 专项 `8 passed in 2.48s`；UI 全集 `157 passed, 648 deselected in 20.06s`；全量 `805 passed in 136.80s`。compileall、diff-check、源码 smoke、最终 dist offscreen smoke、保存值恢复、CLI 覆盖保存值和 2533 项 checksum 均通过。完整 T-UI0～T-UI10 见 [最终 UAT](DEV-UI4_FINAL_UAT.md)。

## 数据来源、资格与限制

实际 P9/UAT 数据全部为 `simulated/software_validation`；官方 REW 路径为 `external_reference/software_validation`。没有读取真实研究数据或真实 final-test。模拟 package 为 `software_validation_only`，`final_test_evaluated=false`、`scientifically_eligible=false`、`deployment_allowed=false`。

已知限制：真实 Multisine/P8 未开放；真实 calibration/tone/model/package 未冻结；final-test 无真实 authority；P3-C 仍无通用正式生产入口；打包产物较大；未创建 installer、签名、tag、release 或 push。后续只由硬件和真实数据触发 DEV-D，不再新增常规 DEV-UI 轮次。

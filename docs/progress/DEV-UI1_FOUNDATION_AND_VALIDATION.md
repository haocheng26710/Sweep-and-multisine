# DEV-UI1 — PySide6 UI 基础框架与软件验证入口

## 状态、日期、分支与提交

- 日期：2026-08-10
- 分支：`feature/v2-dual-input`
- 状态：实现完成，等待本地提交后的 clean-tree smoke/状态复核
- 单一提交边界：本报告、UI 代码、测试、依赖与文档同一提交 `feat(ui): add guided desktop validation foundation`
- Git commit：本报告与实现位于同一提交；精确 SHA 由最终交付回复给出，避免在提交内容中制造自引用哈希

## 目标与完成内容

本轮按照 `DEV-UI0_UI_DESIGN.md` 建立 PySide6 本地向导骨架，仅开放三个低风险软件操作：只读环境检查、Sweep/Multisine 配置验证、异步 DEV-C16 模拟软件验收。P1–P9 科研算法、schema、provenance、QC、final-test 与不可覆盖门禁均未修改。

主界面按用户指定顺序固定显示十二步，并在每个按钮中直接显示 `not_started`、`ready`、`waiting_external`、`running`、`passed`、`warning`、`manual_review`、`blocked` 或 `failed`，不以颜色作为唯一表达。默认简易模式显示当前步骤、准备事项、操作、结果和下一步；专业模式增加配置路径、Git commit/dirty、实际 program/arguments、stdout、stderr、输出目录和技术错误。

DEV-UI2～DEV-UI4 的步骤只有说明入口，显示实现轮次、当前准备事项和暂时不能执行的原因。界面没有播放、录音、数据导入、P1–P9 分析、final-test 解封或 provenance/科研资格编辑按钮。

## 界面入口与结构

安装依赖后运行：

```powershell
python scripts/run_gui.py
```

受控 headless smoke 使用：

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python scripts/run_gui.py --smoke-test
```

界面结构为：顶部模式与 provenance 边界说明；左侧十二步轨道及文字状态；中央当前步骤、主要操作、结果与下一步建议；专业模式只读技术面板；软件验收区提供实时日志、取消、结果文件夹和报告入口。未制作像素级截图，本报告以该稳定结构说明作为 DEV-UI1 界面证据；视觉完善、HiDPI 与打包属于 DEV-UI4。

## 按钮与现有后端映射

| UI 操作 | 调用边界 | 输出/行为 |
|---|---|---|
| 检查软件环境 | `ApplicationServices.check_environment()` | 只读检查 Python、根目录、Git commit/dirty、核心依赖、PySide6、三份配置和 outputs 可写性 |
| 验证 Sweep 配置 | `config.load_config(..., default_path=config/default.yaml)` | 要求 resolved `measurement_mode=rew_sweep`，显示版本、purpose、provisional 与错误 |
| 验证 Multisine 配置 | 同一 `config.load_config` | 要求 resolved `measurement_mode=schroeder_multisine`；不复制 schema |
| 运行模拟软件验收 | `QProcess.start(sys.executable, [run_pre_experiment_acceptance.py, ...])` | program/arguments 分离、实时日志、短唯一 run-id、拒绝覆盖、解析 hash-verified bundle |
| 取消当前验收 | `QProcess.terminate()`，超时后 `kill()` | `ProcessOutcome.CANCELLED`，UI 明确记录 `cancelled`；不删除已有 evidence |
| 打开结果文件夹/查看报告 | verified `AcceptanceSummary` 路径 | 只有目录/报告存在并经 loader 解析后启用 |

环境检查不会创建测试文件或修改 Git。outputs 可写性使用只读权限检查。配置按钮直接调用现有加载/验证逻辑。验收复用现有脚本与 `load_acceptance_bundle`，退出码不是成功权威；UI 只有在 loader/hash 复核后才显示 T0～T3、V2 和总测试状态，失败进程若留下有效 bundle 也会显示失败证据。

## 状态机与安全门禁

合法执行路径为 `ready -> running -> passed|warning|manual_review|blocked|failed`；terminal 状态必须先回到 `ready` 才可重试。非法跳转抛出 `InvalidStepTransition`。外部未知状态一律映射为 `blocked`。界面模式切换不改变任何步骤状态或 gate。

用途选择仅是 UI 上下文，不写入 artifact。界面不提供 `eligible_for_scientific_analysis` 编辑器。`real_experiment + schroeder_multisine` 固定把单次导入步骤设为 `blocked`，禁用运行按钮并显示：

> 当前 P8-A 后端仅允许 simulated/software_validation。<br>
> DEV-C16 ready 表示可以进入 DEV-D 准备，不代表真实 Multisine 已获准分析。

切换界面模式、run purpose 或其他显示字段均不能绕过该门禁。final-test 只有封存说明，无执行或解封入口。

## 架构、修改文件与 API/依赖变化

- `src/acoustic_encoder/ui/state.py`：纯 Python UI 状态、十二步定义、失败关闭门禁。
- `src/acoustic_encoder/ui/services.py`：环境、配置和 acceptance loader 的应用服务边界。
- `src/acoustic_encoder/ui/workers.py`：通用 `ProcessTask` 与 DEV-C16 `AcceptanceWorker`。
- `src/acoustic_encoder/ui/main_window.py`：窗口、导航、简易/专业模式和结果视图。
- `src/acoustic_encoder/ui/app.py`、`dialogs.py`、`__init__.py`：应用入口与人类说明。
- `scripts/run_gui.py`：统一启动脚本和缺依赖提示。
- `tests/conftest.py`、`test_ui_state.py`、`test_ui_services.py`、`test_ui_workers.py`、`test_ui_main_window.py`、`test_ui_app.py`：offscreen 测试。
- `requirements.txt`：新增 `PySide6>=6.7,<6.9` 与 `pytest-qt>=4.4,<5`。6.11.1 在当前 Windows/Anaconda 环境出现 QtCore DLL load failure，实际验证版本为 6.8.3。
- README、CHANGELOG、迁移文档、进度索引和本报告。

没有 pipeline/config/Measurement/FeatureSet/run-manifest schema 或 YAML 字段变化。科研后端不 import PySide6。新增 UI API 只消费现有配置和 acceptance authority，不成为第二权威数据源。

## 数据来源、provenance 与科研资格

本轮窗口测试使用临时文件、fake services 和短 Python 子进程；集成验收使用现有 DEV-C16 `simulated/software_validation` 链。没有读取或生成 `real_experiment` 研究输入。既有三份 REW `external_reference` 仅由 DEV-C16 软件验收复核格式。所有本轮 evidence 均 `scientifically_eligible=false`、非 canonical、非 deployment，不得用于科研结论。

## TDD 与实际验证结果

TDD 依次观察到并修复以下 red：UI package/state 缺失、service 缺失、worker 缺失、窗口缺失、启动入口缺失；Qt 6.11.1 DLL 加载失败后固定到已验证 6.8.3；首次手工长 run-id 使 T3 深层路径达到 271 字符并失败，随后增加 15 字符上限测试，改为 `u1-` 加 12 个十六进制字符及碰撞/覆盖检查。

已实际执行并获得：

- DEV-UI1 专项：`python -m pytest tests/test_ui_app.py tests/test_ui_main_window.py tests/test_ui_workers.py tests/test_ui_services.py tests/test_ui_state.py -q` → `33 passed in 2.79s`。
- 最终全量：`python -m pytest -q` → `716 passed in 108.76s (0:01:48)`。
- 实际启动：`QT_QPA_PLATFORM=offscreen python scripts/run_gui.py --smoke-test` → exit 0，无 stdout/stderr。
- `python -m compileall -q src scripts tests` → exit 0，无输出。
- `git diff --check` → exit 0；仅输出 Git 的 `requirements.txt` LF→CRLF 工作副本提示，无 whitespace error。
- 既有 bundle loader 集成：`c16b/acceptance` → T0/T1/T2/T3 全 `pass`，V2 `14/14`，记录的全量 `683 passed`，`software_integration_ready=true`，`scientifically_eligible=false`。
- 本轮短 ID 验收：`python scripts/run_pre_experiment_acceptance.py ... --run-id u1-prec0810` → T0/T1/T2/T3 全 `pass`，V2 `14/14`，overall `pass`，内嵌全量 `716 passed in 108.44s (0:01:48)`；按设计因提交前 `git_dirty=true`，`software_integration_ready=false`、`ready_for_dev_d_diagnostic_experiment=false`，进程返回非零。UI loader 成功解析该 bundle。
- 首次长 ID 探索 run `DEV-UI1_PRECOMMIT_20260810T120000Z` 不是通过证据：T3 因 Windows 深层路径长度失败、V2 `11/14`；该结果推动了短 run-id 修复，未被描述为验收通过。

提交后的 clean-tree smoke/Git 状态将在最终本地提交后复核；未执行前不预先声称结果。

## 生成输出

- 短 ID 受控验收：`outputs/simulated/software_validation/u1-prec0810/acceptance/`
- 首次长 ID 失败证据：`outputs/simulated/software_validation/DEV-UI1_PRECOMMIT_20260810T120000Z/acceptance/`
- UI 日常运行：`outputs/simulated/software_validation/<short-ui-run-id>/acceptance/`

这些目录由现有 acceptance writer 创建、拒绝覆盖并带 artifact/manifest SHA-256。运行日志在 UI 中实时显示，验收命令日志由 DEV-C16 bundle 持久化。取消状态在 worker result 和 UI 步骤结果中保留；完整 UI 会话恢复/日志导出留给 DEV-UI4。

## 已知限制

- DEV-UI1 不执行实验计划、刺激生成、播放/录音、文件导入、P1–P9 分析、数据集 QC、冻结或 final-test。
- 没有 PyInstaller 安装包、HiDPI/键盘完整验收、崩溃恢复或完整 UI 审计日志导出；这些属于 DEV-UI4。
- 环境检查只判断 outputs 路径权限，不通过写临时文件探测，以满足只读检查约束。
- QProcess 取消尽力终止子进程；已经由后端写出的失败/evidence 文件保留，不自动清理。
- 当前真实 Multisine/P8 未批准；DEV-C16 ready 也不改变这一点。

## DEV-UI2 进入条件

DEV-UI2 只能在本提交的 33 项专项、全量回归、compileall、diff check、offscreen smoke 和 clean-tree Git 状态复核完成后进入。下一轮可实现实验计划/metadata/sidecar 表单、外部 REW/播放/录音说明、显式文件选择、P7 生成、真实 Sweep 单测量入口和 simulated Multisine 单测量入口；仍必须保持 core 与 UI 双重真实 P8 hard block、不可覆盖、final-test 封存和 provenance 不可伪造。

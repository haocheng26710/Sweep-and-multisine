# DEV-UI2 — 文件导入、metadata 助手与单次测量处理

## 状态、日期、分支与提交边界

- 日期：2026-08-10
- 分支：`feature/v2-dual-input`
- 状态：实现与验证完成，等待本报告同代码一起本地提交
- 单一提交：`feat(ui): add guided import and single-run workflow`
- Git commit：精确 SHA 在提交完成后的交付回复中给出；报告不伪造自引用 commit
- 科研资格：本轮只使用 `external_reference/parser_fixture/software_validation` 和 `simulated/software_validation`；全部 `eligible_for_scientific_analysis=false`

本轮没有修改 P1–P9 数学定义、QC 阈值、核心 schema 版本、final-test 门禁或 research hard gate，也没有 push。

## 目标与完成的用户流程

DEV-UI2 激活十二步向导中的“选择使用方式”和“导入并检查单次数据”，完成四条互不混用的路线：

1. 官方 REW TXT：固定为 `external_reference / parser_fixture / software_validation`，只用于格式和软件验证；
2. 真实 REW 诊断：固定为 `real_experiment / research_input / software_validation`，科研资格保持 false；
3. 模拟 Multisine：固定为 `simulated / software_validation`，可调用现有 P8；
4. 真实 Multisine 登记：可预检 WAV/manifest、生成 sidecar、计算 hash 并保存诊断记录，但在 QProcess 启动前硬阻塞 P8。

路线选择后，窗口顶部始终以文字显示 route、`data_origin`、`dataset_role`、`run_purpose` 和“科研资格=false”，不只依赖颜色。切换路线且表单已有内容时要求明确确认；确认后清空输入路径、metadata 草稿、ID 和旧运行上下文。官方参考路线自动锁定实验身份字段并强制保存为 null。

## 表单、自动填写与 ID 规则

用户通过表单填写或选择：

- `device_version`、`configuration`、`angle_deg`、`session_id`；
- `repeat_type`、`repeat_id`、`reposition_round_id`；
- `assembly_id`、`acquisition_block_id`、`experiment_step`；
- `date_time`（若填写则由 `MeasurementMeta` 要求明确时区）；
- `audio_channel`、`provenance_uri`。

UI 不允许直接编辑 JSON。下列字段由 route、预检、config 和 schema 自动生成或锁定：版本 quartet、measurement/source format、source path/hash、origin、role、purpose、stimulus ID/hash、tone set、sidecar path、Git commit 和 scientific eligibility。表单提交最终仍构造并 round-trip 现有 `MeasurementMeta`，UI 没有复制 schema 规则，也不存在 `eligible_for_scientific_analysis` 编辑器。

`sample_id` 与 `run_id` 是验证后表单、源文件 hash、route、mode、stimulus/tone 信息的 canonical JSON SHA-256 派生值；同一内容可重复生成同一预览，字符只包含安全路径组件。界面提供 sample/run ID 复制按钮。关键表单变化会使旧草稿失效并要求重新预检。metadata 修订需要人工填写原因，写入新的 `rev-NNN`，并为后续运行使用带 revision 后缀的新 run ID；旧登记和旧运行从不覆盖。

## 文件预检、保存策略与硬门禁

REW 预检复用公开的 `inspect_rew_frequency_response()`，其底层仍是现有 P1 parser/data-type 判定：检查文件存在、`.txt`、非空、两/三列 SPL、至少 5 点、有限且严格递增，并明确拒绝阻抗。预检返回点数、phase 可用性、频带和小写 SHA-256，不修改源字节。

Multisine 预检读取指定 recording WAV 和指定 `stimulus_manifest.json`，检查扩展名、非空、可读 channel、sample rate、stimulus WAV/hash、stimulus ID、tone set、period 和 stable/discard counts，并计算 recording/manifest hash。它不扫描目录、不从文件名猜参数、不修改 WAV/manifest。

UI 草稿保存在 Git 忽略的：

`outputs/ui_sessions/<sample-id>/rev-NNN/`

每个 revision 包含 metadata/sidecar、`resolved_config.yaml`、`ui_session_manifest.json`、`revision_record.json`、`input_hashes.json`、`technical_log.txt`、`step_report.md` 和 `step_report.html`。Multisine config 快照将 `paths.stimuli` 明确绑定到用户选择 manifest 的 canonical stimulus 根，并同步已验证的 stimulus/tone/sample-rate/period counts。运行前 worker 再读取 hash 清单并复核所有输入；任一字节变化即停止。运行输出继续由现有 executor 按 origin/purpose/run-id 隔离，已有目录立即拒绝。

真实 Multisine 在 metadata 保存后仍显示并执行以下硬阻塞：

> 当前 P8-A 后端只接受 simulated/software_validation。
> 本录音已登记但尚未分析。请保留原始 WAV、manifest、sidecar
> 和 hash，等待 DEV-D 真实 Multisine 门禁实现与批准。

该路线没有 P8 绕过按钮；`SingleMeasurementWorker.prepare()` 也独立拒绝启动，不能通过更改 UI 显示、source format、role 或 eligible 绕过。

## 按钮到现有后端的映射

| UI 操作 | Application service / 后端 | 行为与权威 |
|---|---|---|
| 选择 REW TXT / WAV | `QFileDialog.getOpenFileName` | 只选择明确文件，不扫描目录 |
| 选择 stimulus manifest | `QFileDialog.getOpenFileName` | 必须明确选择 `stimulus_manifest.json` |
| 只读预检并生成草稿 | `MeasurementDraftService.preflight_rew/preflight_multisine`、`build_draft` | 复用 P1 parser、WAV reader、config loader 和 `MeasurementMeta` |
| 保存登记与 metadata | `MeasurementDraftService.save_draft` | 创建 immutable `rev-NNN`、快照、hash、Markdown/HTML 报告 |
| 建立 metadata 修订 | 同一 service，显式 `revision_reason` | 保留旧 revision，生成新 run ID，不原地修改 |
| 运行单次软件验证 | `SingleMeasurementWorker` → `run_pipeline.py` 或 `analyze_multisine.py` | `QProcess` program/arguments 分离；不复制 P1/P2/P3/P8 |
| 取消 | `QProcess.terminate()`，必要时 `kill()` | 映射 `cancelled`，保留已经写出的证据 |
| 查看/打开结果 | verified session/run paths | 报告按钮与实际存在的路径绑定 |

运行前弹窗显示 sample/run ID、origin、mode、科研资格和源路径并要求确认。退出码固定映射：0→`completed`，1/未知→`failed`，2→`manual_review`，3→`blocked_research_gate`，4→`warning`，取消→`cancelled`。UI 状态是派生视图；最终 success、QC、phase 和 stage gate 仍来自后端 `run_manifest.json`。manifest 自带 SHA-256 时先复核，再生成 `run_result.json`、stdout/stderr、output hash 清单及 Markdown/HTML run report。

## 界面结构说明

界面仍为顶部 route/provenance 横幅、左侧十二步文字状态、中央当前步骤和底部专业日志。单次测量页由四区组成：只读输入选择；schema-backed metadata 表单；自动 sample/run ID 和复制按钮；保存/修订/运行/取消及报告按钮。简易模式显示预检结论、阻塞原因和下一步；专业模式额外显示实际 program/arguments、config、Git、stdout、stderr、输出路径与技术异常。本轮没有制作像素截图；offscreen smoke 和 widget 测试验证了结构与控件状态。

## 修改文件与 API/schema 变化

- `src/acoustic_encoder/io_rew.py`：新增只读 `REWPreflightResult` 与公开 preflight adapter；解析算法未改变。
- `src/acoustic_encoder/ui/measurement_workflow.py`：route policy、preflight、metadata draft、revision/session evidence、hash 验证和 run-result loader。
- `src/acoustic_encoder/ui/workers.py`：单测量 invocation、退出码状态机及异步 QProcess worker。
- `src/acoustic_encoder/ui/main_window.py`：route、文件选择、metadata、ID、运行确认、日志、报告和硬阻塞界面。
- `src/acoustic_encoder/ui/services.py`：导入/完整性/schema/manual-review/research-gate 的人类可读错误映射。
- `src/acoustic_encoder/ui/state.py`：真实 Multisine 的 DEV-UI2 精确阻塞文本。
- `tests/test_ui_measurement_workflow.py`、`test_ui2_main_window.py`、`test_ui2_e2e.py`、`test_ui_services.py`：TDD 与 E2E。
- README、CHANGELOG、迁移文档、进度索引及本报告。

核心 pipeline/config/measurement/feature schema quartet 没有变化。新增的 `ui_session_schema_version=1.0.0` 和 `ui_run_result_schema_version=1.0.0` 只描述 UI staging evidence，不替代任何科研 artifact schema。YAML 阈值和 P1–P9 API 均未修改。

## 数据来源、provenance 与科研资格

- 官方 E2E 使用仓库中不可变的 `tests/fixtures/rew/external_reference/BW M1.txt`，固定为 external reference/parser fixture/software validation；
- Multisine E2E 使用 S3 `generate_dual_mode_mock()` 生成的确定性模拟 WAV 和 P7 manifest，固定为 simulated/software validation；
- metadata/schema 测试使用 pytest 临时目录中的 synthetic TXT/WAV/manifest；
- 没有导入、分析或据此声称任何真实研究结果；真实 REW 仅完成可用路径的 schema 测试，真实 Multisine 只验证登记和阻塞。

因此本轮所有输出 scientifically ineligible，不能用于科研结论、真实阈值冻结、模型部署或 final-test。

## 实际验证命令与准确结果

已实际执行：

- 最终 UI 专项：`python -m pytest tests/test_ui_state.py tests/test_ui_services.py tests/test_ui_workers.py tests/test_ui_main_window.py tests/test_ui_app.py tests/test_ui_measurement_workflow.py tests/test_ui2_main_window.py tests/test_ui2_e2e.py -q` → `65 passed in 11.80s`。
- 最终全量：`python -m pytest -q` → `748 passed in 127.22s (0:02:07)`。
- 持久化 E2E：首次直接指定不存在的 `--basetemp outputs/ui2_validation/e2e_20260810` → `2 errors in 0.91s`，原因是 pytest 要求父目录先存在；创建父目录后原命令重跑 → `2 passed in 3.27s`。该失败是验证目录准备问题，不是 pipeline/import 失败，未被描述为通过。
- `python -m compileall -q src scripts tests` → exit 0，无输出。
- `git diff --check` → exit 0，无 whitespace error。
- `$env:QT_QPA_PLATFORM='offscreen'; python scripts/run_gui.py --smoke-test` → exit 0，无 stdout/stderr。

上述结果均为本提交前的最终实际执行结果；没有把未运行的命令写成通过。

## 生成输出

持久化、非科研 E2E evidence 位于：

- 官方 REW：`outputs/ui2_validation/e2e_20260810/test_official_rew_ui_registrat0/outputs/external_reference/software_validation/u2-af10f0f5fff0/`
- 模拟 Multisine/P8：`outputs/ui2_validation/e2e_20260810/test_simulated_multisine_ui_re0/outputs/simulated/software_validation/u2-44e1c5cac56f/`
- 对应 UI session：同一测试目录下 `sessions/ref-rew-073d6cb6c449/rev-001/` 和 `sessions/sim-ms-af8cff40bca7/rev-001/`

这些目录位于 ignored `outputs/`，不会污染 Git。原始 TXT/WAV/manifest 没有被复制、覆盖或改写。真实 Multisine 测试只在 pytest 临时目录生成 registration evidence，并验证 worker 抛出 `PermissionError`；没有真实 P8 输出目录或成功标记。

## 已知限制与明确非范围

- 未实现 DEV-UI3 dataset scope、P2-B/P3/P4/P5/P6/P9 编排，也不扫描目录自动组成数据集；
- 未实现 DEV-UI4 freeze/final-test、完整报告浏览、安装包、崩溃恢复或主题/HiDPI 完善；
- 未实现 UI 内 P7 刺激生成、外部播放/录音控制或真实 Multisine P8；
- real REW 仍只能以 software validation 诊断运行，不能由 UI 创建 research analysis；
- 当前 metadata revision 是 immutable session revision，不是多人数据库或签名审批系统；
- `QProcess` 取消尽力终止进程并保留已写 evidence，不回滚或删除后端输出；
- 当前 Windows 长路径兼容依赖 Python/Qt 和系统长路径设置，测试覆盖中文与空格路径，但未制造超过系统限制的路径。

## DEV-UI3 进入条件

DEV-UI3 只有在本提交的专项、全量 pytest、compileall、diff check、offscreen smoke、两条 E2E、真实 Multisine 双层阻塞和 clean worktree 复核完成后进入。下一轮只能编排显式 dataset/analysis scopes、P2-B authority 和现有 P3–P9 后端；不得扫描目录隐式选样，不得解封 final-test，不得把本轮 simulated/external-reference evidence、provisional 阈值或模型重新标记为真实科研 authority。

# DEV-UI3 — 实验计划、样本管理与批量分析向导

## 状态、日期、分支与提交边界

- 日期：2026-08-10
- 分支：`feature/v2-dual-input`
- 状态：实现与验证完成，等待本报告同代码一起本地提交
- 单一提交：`feat(ui): add experiment planning and batch analysis workflow`
- Git commit：精确 SHA 在提交后的交付回复中给出；报告不伪造自引用 commit
- 科研资格：本轮验证仅使用 synthetic/simulated software-validation 数据；全部 `eligible_for_scientific_analysis=false`

本轮没有修改 P1～P9 数学定义、核心 schema quartet、科研 QC 阈值、provenance hard gate 或 final-test 权威。没有读取真实 final-test，没有运行真实 Multisine/P8，没有 push。

## 目标和完成范围

DEV-UI3 激活十二步向导中的“制定实验计划”“检查完整实验数据集”“比较方向、配置和重复性”“分类、选频和校准”页面，完成：

1. 表单化实验计划、显式条件 blocks、CONT/REPOS/REASM 矩阵和稳定 sample ID；
2. 十二项 DEV-D 安全/采集清单和不可变 plan revision；
3. 用户明确选择的 UI2 session/output 登记，不扫描目录；
4. metadata identity、hash、duplicate、missing、unexpected、blocked 和 final-test sealed 匹配；
5. append-only 人工审核记录，原 QC/metadata 不变；
6. 自动生成并只读预览 P2-B scope、input manifest、条件矩阵和 hashes；
7. `QProcess` 后台执行、实时日志、取消、结果摘要、输出/报告入口；
8. P3-C～P6 正式后端能力审计和有条件批量启动；
9. P2-B 未 canonical-ready 时锁定 canonical P4/P5/P6；
10. final-test 读前阻断和真实 Multisine/P8 依赖阻断。

明确未实现：P9 tone/model 冻结、final-test 解封/读取、PyInstaller、新科研算法、真实 Multisine/P8、真实实验阈值冻结和科研结论。P3-C 当前没有通用正式入口，因此显示 unavailable。

## 实验计划和样本矩阵

`ExperimentPlan` 保存基本信息、设备/校准/provenance 路径和一个或多个 `PlanConditionBlock`。实验角色固定为 `calibration/training/development/final_test_sealed`，只存在于计划和 analysis scope；它们没有写入 `MeasurementMeta.dataset_role`。后者仍只接受现有 schema 的 `parser_fixture/software_validation/research_input`。

矩阵遍历顺序固定为 block、mode、configuration、angle、session、acquisition block，再按 CONT、REPOS round/repeat、REASM assembly/repeat。每个 sample ID 由路径安全 plan slug 与完整实验身份 canonical JSON 的 SHA-256 前缀组成：

- 非身份字段（研究问题文字、计划版本）变化不改变 sample ID；
- 身份字段变化产生新 sample ID；
- 重排表单输入不改变排序或 ID；
- ID 只含小写字母、数字和连字符；
- 不从文件名、邻近样本或目录推断字段。

生成前显示预计样本数；超过配置在 UI service 中的 500 条大计划阈值时要求再次确认。保存目录为 ignored `outputs/ui_plans/<plan-slug>-<digest>/rev-NNN/`，至少包含：

- `acquisition_plan.json`
- `acquisition_plan.md`
- `expected_sample_matrix.csv`
- `safety_checklist.json`
- `plan_manifest.json`
- `hashes.json`

第二个及后续 revision 必须提供修订理由；旧 revision 不覆盖。计划、清单和 UI manifest schema 均为 UI-owned `1.0.0`，不替代后端科研 schema。

## 安全和采集准备门禁

清单固定记录 device chain、channel/polarity、sample rate/bit depth、DSP/AGC/EQ、安全 SPL/功率、stimulus manifest、原始数据只读、SHA-256/备份、operator、calibration、final-test custodian 和 stop conditions。每项含状态、操作人、带时区时间、备注与证据路径。

所有 required 项人工声明通过才派生 `ready_for_acquisition=true`；该字段始终伴随 `scientific_eligibility_granted=false`。未完成时仍能保存草稿并执行 simulated software validation，但不能标为 acquisition-ready，也不能绕过后端 research gate。

## 样本登记、匹配和人工审核

`SampleRegistry` 只接收一个明确 UI2 `ui_session_manifest.json`、一个明确计划样本和可选的明确 output directory。模块没有递归扫描 API。登记会复核 UI2 manifest digest、metadata round-trip、source hash、run manifest identity、artifact hash 和 FeatureSet/SpectrumData 可用性。

样本表显示 plan/source sample ID、origin、mode、configuration、angle、session、repeat、实验角色、单测量 QC、manual review、eligible、source hash、FeatureSet、SpectrumData 和 match status。匹配只使用显式 metadata identity，状态固定为：`expected_and_present`、`expected_but_missing`、`unexpected_sample`、`duplicate_identity`、`metadata_mismatch`、`hash_mismatch`、`blocked`、`final_test_sealed`。

人工决定要求操作人、带时区时间、理由和决定，并追加到 `outputs/ui3_registry/manual_review_audit.jsonl`。它不删除样本、不改自动 QC、不改原始 metadata；若要更正身份，必须回到 UI2 创建新 revision/hash。

## P2-B 流程和状态机

用户确认训练/开发样本后，`BatchWorkflowService.prepare_p2b()` 生成：

- `dataset_scope.json`
- `dataset_inputs.json`
- `expected_condition_matrix.csv`
- `selected_sample_audit.csv`
- `ui_scope_snapshot.json`
- `artifact_hashes.json`

它仅引用 persisted FeatureSet 和 P2-A QC，不读取 WAV/TXT、不重跑 P8。P2-B 使用正式 `scripts/run_dataset_qc.py`，输出仍是 backend `dataset_qc/` 权威 bundle；UI preview 额外保存 `technical_log.txt`、`step_report.md/html`。输出和 preview 目录存在时拒绝覆盖。

批量状态机覆盖 `plan_draft → plan_ready/acquisition_waiting → samples_partial/samples_complete → dataset_qc_running → dataset_qc_warning/dataset_qc_passed → analysis_ready/running/warning/completed`，另有 `final_test_sealed` 和 `blocked`。草稿允许模拟验证，但不会变成 acquisition-ready。P2-B 的 `canonical_ready=false` 保持 warning/locked；只有权威输出明确 canonical-ready 时才解锁正式分析。

## P3-C～P6 实际开放状态

详见 [DEV-UI3_BACKEND_CAPABILITY_MATRIX.md](./DEV-UI3_BACKEND_CAPABILITY_MATRIX.md)。摘要：

- P3-C：unavailable；没有通用正式入口，绝不包装 validation fixture。
- P4：有条件开放；明确 scope/input + exact canonical-ready P2-B。
- P5-A：有条件开放；单模式 scope/input + exact canonical-ready P2-B。
- P5-B：形式入口存在；还必须有 P3-C matched FeatureSets、P4-B 和 P2-B；真实 Multisine blocked。
- P6-A：有条件开放；仅 sweep dense FeatureSets + P2-B。
- P6-B：形式入口存在；还必须有 P3-C、exact P6-A、P2-B；真实 Multisine blocked。

UI 显示正式脚本、前置条件、支持模式、输出和可用性。用户通过文件选择器明确选择 scope/input/config/authority；UI 生成只读 snapshot 后才允许 QProcess 启动。模式不适用不是失败，缺入口是 unavailable，门禁违反是 blocked。

## final-test 与 provenance 隔离

`final_test_sealed` 表格行不显示 configuration、angle、session、repeat 或结果。误选时在解析 manifest 内容前立即写 `final_test_incidents.jsonl`，其中 `content_read=false`、`scope_valid=false`、`manual_review_required=true`，并使当前 scope 无效。UI3 不提供解封、标签查看、阈值调整、tone 选择或模型冻结入口。

真实 REW 可作为 `real_experiment/software_validation` 诊断样本登记，但 UI 不自动设置 eligible、research_analysis 或 canonical-ready。真实 Multisine 只登记；P8 和依赖其新 FeatureSet 的正式分析继续 blocked。所有 simulated/external-reference 结果持续标记 scientifically ineligible，分类 accuracy 不被描述为装置性能。

## 修改文件与 schema/API 变化

- `ui/experiment_plan.py`、`plan_page.py`：计划 schema、样本矩阵、清单、revision/hash 和表单。
- `ui/sample_registry.py`、`dataset_page.py`：显式登记、匹配、人工审核、P2-B 页面和摘要。
- `ui/batch_workflow.py`、`analysis_page.py`：批量状态机、能力矩阵、scope/input preview、正式 CLI 编排和步骤报告。
- `ui/workers.py`：通用、可取消的 batch `QProcess` worker。
- `ui/main_window.py`、`state.py`、`services.py`：十二步路由、UI3 状态联动和人类可读错误。
- `tests/test_ui3_*.py` 及既有 UI 路由回归：TDD、GUI、门禁和 E2E。
- README、CHANGELOG、迁移文档、进度索引和两份 DEV-UI3 报告。

核心 pipeline/config/measurement/feature schema quartet 和 YAML 科研阈值没有变化。新增 UI-owned plan/checklist/manifest/snapshot schema `1.0.0`；它们只记录编排证据，不建立第二科研权威。

## 实际验证命令和准确结果

本报告收尾前已实际运行：

- DEV-UI3 专项：`python -m pytest tests/test_ui3_experiment_plan.py tests/test_ui3_sample_registry.py tests/test_ui3_batch_workflow.py tests/test_ui3_workers.py tests/test_ui3_pages.py tests/test_ui3_e2e.py -q` → `31 passed in 2.98s`。
- 最终全量回归：`QT_QPA_PLATFORM=offscreen python -m pytest -q` → `779 passed in 123.26s (0:02:03)`。
- 正式 P4/P5/P6 受控 CLI：对应五个 CLI/validation 测试文件 → `9 passed in 7.22s`。
- final-test/真实 Multisine 门禁：3 个指定测试 → `3 passed in 0.22s`。
- 持久化完整模拟 plan→registration→P2-B：`python -m pytest tests/test_ui3_e2e.py -q --basetemp outputs/ui3_validation/dev-ui3-20260810T143453` → `1 passed in 0.30s`。该路径也验证 non-canonical P2-B 无法解锁正式 P4。

- `python -m compileall -q src scripts tests` → exit 0，无输出。
- `git diff --check` → exit 0，无 whitespace error。
- `$env:QT_QPA_PLATFORM='offscreen'; python scripts/run_gui.py --smoke-test` → exit 0，无 stdout/stderr。

以上均为实际执行结果；没有把未运行的命令或真实实验结果写成通过。

## 生成输出

持久化 E2E 根目录：

`outputs/ui3_validation/dev-ui3-20260810T143453/test_simulated_plan_registrati0/`

其中包含：不可变计划 `plans/.../rev-001/`、两个显式 UI2 sessions、P2-B preview/hashes/step report，以及正式 P2-B 输出：

`outputs/simulated/software_validation/ui3-plan-registration-p2b/dataset_qc/`

所有输入都是测试生成的模拟数据，输出位于 Git ignored `outputs/`。无真实研究数据、final-test 内容或科研结论。

## 已知限制和 DEV-UI4 进入条件

- P3-C 缺通用正式入口；P5-B/P6-B 只能消费事先存在、精确匹配的权威 artifact。
- 批量 P4～P6 页面是薄正式入口：复杂 scope/input 仍需由已批准的后端工作流生成后通过文件选择器明确选择；UI3 不虚构通用 schema builder。
- 当前 registry 是本地 append-only 文件证据，不是多人数据库、电子签名或权限系统。
- 大计划阈值 500 是 UI 防误操作参数，不是科研阈值。
- QProcess 取消保留已写 evidence，不删除或回滚后端输出。
- 未实现跨会话恢复运行队列、PyInstaller、完整报告浏览/导出、P9 冻结或 final-test 解封。

DEV-UI4 只能在最终 UI3 专项、全量 pytest、compileall、diff check、offscreen smoke、E2E、clean worktree 和本地提交全部复核后进入。下一轮仍不得改变科研算法、绕过 P2-B/provenance、解封 final-test 或开放真实 Multisine/P8。

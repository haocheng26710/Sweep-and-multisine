# DEV-C16 — T0–T3 实验前 dry-run 与 V2 总验收

## 状态、日期、分支与资格

- 日期：2026-08-06
- 分支：`feature/v2-dual-input`
- 状态：实现与提交前验证完成；最终权威状态由提交后的 clean-tree acceptance bundle 给出
- 单一提交边界：`chore(validation): complete pre-experiment acceptance`
- 数据：`simulated` 与三份 `external_reference` REW 格式样例
- 用途：`software_validation`
- 固定边界：`scientifically_eligible=false`、`canonical_analysis=false`、`deployment_eligible=false`、`approved_real_calibration=false`、`final_tone_set_frozen=false`、`final_test_read=false`

“通过”只表示软件集成已具备进入 DEV-D 少量、受控、诊断性真实设备实验的条件，不表示科研结论、真实分类性能、正式快速读取性能、部署批准或 release。

## 目标与验收标准

本步一次性编排既有 validation runner 与 artifact loader，完成 T0 数学一致性、T1 时域鲁棒性、T2 分类/tone 选择和 T3 持久化端到端链路，并逐条审计 14 项 V2 最低要求。任何 required gate 失败、证据缺失、final-test 被读取或工作树不干净，都不得把最终 bundle 标为 ready。

## 完成范围

- 新增显式 `config/validation_dev_c16_acceptance.yaml` 与 `scripts/run_pre_experiment_acceptance.py`；不扫描目录推断输入，接受明确的 `run-id`、`output-root` 和 config。
- 新增 schema 1.0 的 acceptance check/result、固定 `pass/fail/unavailable` 状态、T0–T3 聚合和 14 项 V2 requirement 聚合。
- T0 实际运行 P7 → S3 → P8 → P3-C identity 链；核对 tone identity、quantity/unit/reference、FeatureSet names/order/tone hash、逐 tone 误差及 lineage/hash。
- T1 预注册九个场景：基线、固定延迟、非周期起点、小噪声、可校正 drift、超政策 drift、clipping、missing tone、phase 不可靠但 magnitude 可用。场景的预期拒绝也只有在 actual status 精确匹配时才算验收通过。
- T2 复用 DEV-C13 的 P9-A/P9-B formal validation 与 loader，核对四方向、outer/inner folds、训练成员、selected tones、authority hashes、P4 保真度、P5 指标、泄漏审计及 final-test seal。
- T3 复用 DEV-C14/P9-C 与 DEV-C15/P9-D formal runner 和 loader，验证 P7 → S3 → P8 → P3-C → P4 → P5 → P9-C → P9-D 的持久化链、重复确定性与篡改输入的 blocked failure bundle。
- 直接导入三份 REW external-reference fixture；metadata 不伪造 angle/configuration/session/repeat，且科研资格保持 false。
- 验证旧 sweep CLI 与旧配置内存迁移；源 YAML 的 SHA-256 在加载前后保持一致。
- 输出人类可读 Markdown 与 JSON/CSV/manifest/hash 机器可读 bundle；输出目录存在即拒绝覆盖，loader 复核所有 artifact 和 manifest self-hash。
- 修复 DEV-C15 validation authority snapshot 中硬编码旧 commit 的真实复现缺陷：改为记录运行时 Git commit/dirty；未改变 P9-D 数学或运行时产品契约。

## 明确非范围

没有新增研究算法、分类器、tone 选择法、参数优化、置信度校准、GUI、实时读取、声卡控制、自动实验调度、云服务或 release tag。没有执行 DEV-D、没有读取真实 final-test、没有冻结真实阈值/校准/tone set，也没有生成科研结论。

## 验收状态机与证据

- `pass`：检查执行并有非空证据文件，且内容校验通过。
- `fail`：执行结果或实际证据不满足预注册条件；不能由 warning 覆盖。
- `unavailable`：缺少可判断证据；required gate 仍不能 ready。
- 场景级预期 QC 拒绝与验收失败分离。例如超 drift、clipping 或 missing tone 的实际 QC 精确拒绝可证明门禁正常，因此该“场景验收”可 pass。
- T0–T3 聚合及 14 项 V2 requirement 必须全部 pass；此外 `git_dirty=false` 且 `final_test_read=false` 才能设置 `software_integration_ready=true` 和 `ready_for_dev_d_diagnostic_experiment=true`。

## Schema、配置与 API

- 保持 pipeline `2.0.0-dev.21`、config `2.20.0`、Measurement `2.4.0`、FeatureSet `2.3.0`、单测量 run-manifest `1.15.0`；验收不改变运行时契约。
- 新增独立 acceptance scope/result/manifest schema `1.0.0`。
- 入口：`run_pre_experiment_acceptance(project_root, config_path, output_root, run_id)`；CLI 是其薄封装。
- acceptance manifest 记录 Git commit/dirty/branch、版本组、Python/依赖版本、输入/证据/输出 SHA-256、T0–T3、V2 requirements、final-test seal、资格和 self-hash。

## 修改文件

- 验收核心/输出/编排：`pre_experiment_acceptance.py`、`pre_experiment_acceptance_outputs.py`、`pre_experiment_acceptance_runner.py`
- CLI/config：`scripts/run_pre_experiment_acceptance.py`、`config/validation_dev_c16_acceptance.yaml`
- 回归修复：`offline_readout_validation.py`
- 测试：`test_pre_experiment_acceptance.py`、`test_pre_experiment_acceptance_outputs.py`、`test_pre_experiment_acceptance_e2e.py`
- 文档：本报告、进度索引、README、迁移文档、changelog 和三份 DEV-D 接入文档

## 数据来源、provenance 与科研资格

T0–T3 全部使用固定 seed 的模拟数据，T0/T1/T3 从实际 P7/S3/P8 链产生；T2/T3 只使用明确 config 和显式 manifest。REW 检查使用 `tests/fixtures/rew/external_reference/manifest.json` 中三份官方样例，仅验证导入格式。没有 `real_experiment` 输入，所有模拟/参考数据均为 software validation 且科学不合格；final-test 保持封存。

## 实际验证命令与准确结果

- 修改前基线：`python -m pytest -q --disable-warnings` → `673 passed in 83.70s`。
- DEV-C16 聚焦：`python -m pytest -q --disable-warnings tests/test_pre_experiment_acceptance.py tests/test_pre_experiment_acceptance_outputs.py tests/test_pre_experiment_acceptance_e2e.py` → `9 passed in 26.48s`。
- 修复临时验收发现的 writer/provenance/hash-audit 缺陷后，DEV-C16 聚焦复跑 → `10 passed in 26.98s`。
- 兼容与泄漏回归 → `255 passed in 8.23s`。
- DEV-B 至 DEV-C15 关键 E2E → `12 passed in 17.59s`。
- 全量：`python -m pytest -q --disable-warnings` → `683 passed in 107.89s (0:01:47)`。
- `python -m compileall -q src scripts tests` → exit 0，无输出。
- `git diff --check` → exit 0，无输出。
- 临时验收：`python scripts/run_pre_experiment_acceptance.py --config config/validation_dev_c16_acceptance.yaml --output-root outputs --run-id c16tmp3` → T0/T1/T2/T3 均 `pass`，V2 `14/14`，overall `pass`；按设计因提交前 `git_dirty=true` 而 `software_integration_ready=false`、`ready_for_dev_d_diagnostic_experiment=false`。
- 临时 T0：71 个公共 tone，容差 0.05 dB，最大/平均/RMS 绝对误差分别为 `0.011740057787161362`、`0.0021727270573911593`、`0.003274916824154142` dB。
- 临时 T1：9/9 场景实际状态精确匹配预注册期望；所有场景 artifact hash 通过。
- 临时 T2：4 directions、3 outer folds、6 inner folds；最低 P4 retention `0.9285727399492533`，最低 sparse balanced accuracy/macro F1/coverage 均为 `1.0`；final-test 未读。
- 临时 T3：持久化链 `P7->S3->P8->P3-C->P4->P5->P9-C->P9-D->acceptance_report`；top-1 `90.0°`、top-2 `0.0°`、margin `2.977634245550838`；重复结果一致，篡改输入路径为 `blocked` 且无 prediction。
- TDD 中先观察到缺少核心模型、输出层、T0/T1/T2/T3 runner 与 final-test gate 的预期失败，再逐项实现；这些 red 不是通过结果。
- 提交后的 clean-tree Git 状态、commit 与最终 readiness 以最终生成的 `acceptance_manifest.json`、`pre_experiment_acceptance_report.md` 与命令日志为权威；文档不预先声称尚未执行的 clean-tree 结果。

## 生成物

最终 bundle 位于 `outputs/simulated/software_validation/<run-id>/acceptance/`，包含 scope、acceptance matrix、T0/T1/T2/T3 JSON/CSV、14 项 V2 audit、leakage/provenance audit、artifact hash audit、readiness、Markdown report 及 self-hashed manifest。T0–T3 原始验证证据和命令日志保存在同一 run 根目录并由 manifest 记录 hash。

## 已知限制与 provisional 参数

- 所有阈值、模型、tone set、校准和 simulated 性能仍是 provisional software-validation 证据。
- T1 是受控场景矩阵，不代表真实声卡、麦克风、扬声器、房间、长时漂移或实时性能。
- T2/T3 的四/三方向与小样本模拟集合不是性能估计；readout margin 不是概率或 confidence。
- 验收只能证明软件契约、门禁和持久化链在当前环境通过，不能替代真实设备校准、acquisition protocol 审批和真实训练/development 复跑。

## 下一步及进入门槛

仅当提交后的 clean-tree bundle 明确给出 T0–T3 全 pass、V2 `14/14`、`git_dirty=false`、`final_test_read=false`，才可进入 DEV-D 真实设备诊断实验准备。DEV-D 必须先批准 acquisition plan、设备链、时钟/sample-rate、metadata/provenance、角色隔离、备份和停止条件；仍不得读取 final-test 或把本验收 artifact 晋升为科研/部署 authority。

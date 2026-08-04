# DEV-B0：数据来源 schema 与 research hard gate

## 状态与日期

- 状态：完成
- 日期：2026-08-04
- 分支：`feature/v2-dual-input`
- 对应提交：`163ab40821be1bfa447812e7912b0d8547feff85`

“完成”表示 provenance schema、配置入口、hard gate 和对应测试已经落地，不表示已有真实实验数据或科研结论。

## 本步目标

在扩大 P1/P8 处理能力之前，先建立不可绕过的数据来源声明和研究用途门禁，使模拟数据、外部参考数据与未来真实实验数据在 schema 层硬隔离；只有明确合格的 `real_experiment` 可以进入 `research_analysis`。

## 完成范围

- 新增 `DataOrigin`：`external_reference`、`simulated`、`real_experiment`。
- 新增 `DatasetRole`：`parser_fixture`、`software_validation`、`research_input`。
- `MeasurementMeta` 强制记录 `source_sha256`、`provenance_uri` 和 `eligible_for_scientific_analysis`。
- 校验 data origin、dataset role、source format 和 scientific eligibility 的组合；非 `real_experiment` 不能标为科研可用。
- 新增 `RunPurpose`：`software_validation` 与 `research_analysis`；旧配置缺失该字段时安全默认到 `software_validation`。
- 新增 research hard gate：研究运行必须至少有一个输入，且每个输入都必须同时满足 `data_origin=real_experiment` 和 `eligible_for_scientific_analysis=true`。
- mock sweep TXT 与 mock multisine WAV 使用实际文件 SHA-256，并明确标记为 `simulated` / `software_validation`。
- 增加 schema、配置、mock 和 research-gate 回归测试，并同步 README、迁移说明、测试计划和 changelog。

## 明确未完成范围

- 本提交没有实现 REW TXT 解析；该能力在 DEV-B1 完成。
- measurement schema 2.1 仍要求实验身份字段，因此尚不能在不填占位值的情况下表达官方 external reference；该限制在 DEV-B1 的 schema 2.2 修复。
- 没有导入项目自己的 `real_experiment` 文件，也没有验证任何声学结构结论。
- 没有实现完整 pipeline 的 P1–P6 路由、P8、P9、T0–T3 或独立 validation/research 输出目录。
- hard gate 只判断已提供 metadata 的一致性与资格，不证明 provenance 声明本身真实；真实实验仍需要不可变原始文件和可审计实验记录。

## 关键设计决策

| 决策 | 结果 |
|---|---|
| 来源与用途分开表达 | `data_origin` 描述数据来自哪里；`dataset_role` 和 `run_purpose` 描述数据可被怎样使用。 |
| 默认用途从严 | 缺失 `run_purpose` 时解析为 `software_validation`，研究用途必须显式选择。 |
| 科研资格采用双条件 | 仅 `real_experiment` 不够；还必须显式设置 `eligible_for_scientific_analysis=true`。 |
| 全输入门禁 | `research_analysis` 拒绝空输入，也拒绝任何一个不合格输入，避免混合数据污染。 |
| provenance 不静默推断 | 不从文件名、扩展名或相邻记录猜测来源；必须提供 SHA-256 和 provenance URI。 |
| mock 保留旧标记但增加结构化来源 | `mock_only` 继续兼容，同时 schema 明确记录 `simulated` 与 `software_validation`。 |

## 修改文件

提交 `163ab40` 修改 16 个文件：

- 文档：`README.md`、`MIGRATION_V1_TO_V2.md`、`CHANGELOG.md`、`docs/DEV_A_TEST_AND_MOCK_PLAN.md`
- 配置与 metadata 模板：`config/default.yaml`、`config/schema_versions.yaml`、`data/metadata/measurements.csv`
- 功能实现：`src/acoustic_encoder/config.py`、`src/acoustic_encoder/mock_data.py`、`src/acoustic_encoder/research_gate.py`、`src/acoustic_encoder/schemas.py`、`src/acoustic_encoder/version.py`
- 测试：`tests/test_config.py`、`tests/test_mock_data.py`、`tests/test_research_gate.py`、`tests/test_schemas.py`

## Schema/config 变化

| 项目 | 变更前 | DEV-B0 |
|---|---:|---:|
| `pipeline_version` | `2.0.0-dev.0` | `2.0.0-dev.1` |
| `config_schema_version` | `2.0.0` | `2.1.0` |
| `measurement_schema_version` | `2.0.0` | `2.1.0` |
| `feature_schema_version` | `2.0.0` | `2.0.0`（不变） |
| `run_purpose` | 无 | `software_validation` / `research_analysis`；缺失时安全默认前者 |

Measurement schema 2.1 新增必填字段：`data_origin`、`dataset_role`、`source_sha256`、`provenance_uri`、`eligible_for_scientific_analysis`。旧 2.0 artifact 必须从原始来源记录重新分类和计算哈希，不能自动升级为科研输入。

## 使用的数据来源及科研资格

| 数据 | 声明 | 用途 | 科研资格 |
|---|---|---|---|
| DEV-A 确定性双入口 mock 与测试构造数据 | `simulated` / `software_validation` | schema、序列化、mock 和 gate 软件验证 | 不合格；不得支持声学结论 |
| 测试中构造的 external-reference metadata | `external_reference` / `parser_fixture` | 验证 hard gate 拒绝路径；本提交没有加入官方测量文件 | 不合格 |
| 测试中构造的 real-experiment metadata | 仅为单元测试中的资格组合 | 验证 gate 接受/拒绝逻辑，不是一次真实测量 | 不是科研证据 |

本步骤没有使用项目真实实验数据。

## 执行的验证命令和准确结果

实现完成时的记录给出完整 pytest 套件结果为：

```text
19 passed
```

原始记录没有保留 pytest 的具体命令参数和耗时，因此本报告不补写这些信息，也不声称本步骤执行过未留有结果的额外测试。

本次 docs-only 审核执行了以下只读 Git 命令：

```powershell
git show --stat --oneline 163ab40
git diff-tree --no-commit-id --name-status -r 163ab40
```

复核结果：提交存在，标题为 `feat(provenance): enforce research data hard gate`；提交统计为 16 files changed、359 insertions、23 deletions，文件集合与上文一致。

## 已知限制

- schema 2.1 尚不能无占位值表达 external reference 的未知实验身份。
- hard gate 尚未连接到一个完整的端到端研究分析 pipeline；当时 `run_pipeline.py` 仍只负责配置解析和阶段门。
- SHA-256 能检测内容变化，但不能单独证明文件采集过程或 metadata 的真实性。
- 尚无项目 `real_experiment` fixture，因此没有验证真实 REW 格式、实验命名或实验分组。

## 对应 Git commit

```text
163ab40821be1bfa447812e7912b0d8547feff85
feat(provenance): enforce research data hard gate
```

## 下一步及进入门槛

下一步是 DEV-B1 P1 REW Frequency Response TXT 导入。进入门槛为：

- parser 必须测试优先开发，并返回 canonical dense `SpectrumData`；
- 使用 synthetic fixtures 覆盖分隔符、缺相位和失败路径；
- 官方样例只能登记为 `external_reference` / `parser_fixture`，不能填造实验身份；
- import 必须调用 research hard gate，并对未知数据类型或 metadata 停止自动处理。

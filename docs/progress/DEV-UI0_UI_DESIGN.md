# DEV-UI0 — PySide6 本地桌面向导设计

## 1. 状态、日期、分支与本轮边界

- 日期：2026-08-10
- 分支：`feature/v2-dual-input`
- 状态：设计完成，尚未实现 UI
- 本轮产物：本设计文档与进度索引更新
- 代码变化：无
- 算法/schema/config 变化：无
- 数据与科研资格变化：无

本设计面向不熟悉 P1–P9、YAML、CLI 和声学术语的本地用户。UI 是现有程序的受控编排层，不是第二套 pipeline。它必须调用现有 API、读取现有 manifest/typed result，并原样保留 provenance、QC、人工 valid、不可覆盖、scope/hash、training/development/final-test 隔离和 research hard gate。

DEV-UI0 不实现 PySide6，不修改科研算法，不执行真实实验，不开放真实 Multisine/P8，不生成科研结论，也不改变 DEV-C16 的资格结论。

## 2. 设计原则

1. **真实实验顺序优先**：按钮按照“软件检查 → 计划 → Sweep 采集/导入 → 单测量 QC → 数据集 QC → Sweep 分析 → Multisine 准备/外部采集 → P8 → 双入口分析 → 冻结读取 → 报告归档”排列，而不是按源码模块顺序堆叠。
2. **UI 不拥有科学真相**：`MeasurementMeta`、`SpectrumData`、`FeatureSet`、QC result 和各级 manifest 仍是权威对象。UI badge、表格和图表仅为派生视图。
3. **fail closed**：锁定、blocked、manual review、unavailable、warning 和 exclude candidate 都有独立状态；任何未知状态按 blocked 显示，绝不默认成功。
4. **不覆盖**：UI 不提供 “Overwrite” 快捷按钮。已有 run-id 时建议新 run-id，用户不能通过 UI 覆盖原目录。
5. **显式输入**：不扫描目录推断样本、scope、配对、刺激或 final-test。所有输入由文件选择器或明确 manifest 列出。
6. **默认安全**：默认 `software_validation`、默认简易模式、默认 `eligible_for_scientific_analysis=false`、默认 final-test sealed。
7. **外部设备步骤不伪装成自动化**：REW、播放、声卡录音和物理摆位都显示为“外部操作”，UI 只给说明、检查表、表单和文件选择器。
8. **原因先于堆栈**：简易模式先显示人类可读原因和下一步；专业模式同时提供 exception、raw log、hash、resolved config 和可复现 CLI。

## 3. 用户模式

### 3.1 简易模式（默认）

- 每页只有一个推荐主操作和最多两个辅助操作。
- 使用“导入 Sweep”“检查这次测量”“检查整组实验”等用户语言；P 编号作为副标题。
- YAML、schema、hash、feature kind、authority ID 默认折叠，但重要门禁结果始终可见。
- 表单按已选实验计划预填；任何推断禁止项仍要求人工确认。
- warning/exclude/manual review 不用颜色单独传意：同时显示图标、文字状态和原因。
- 不显示 final-test 内容或“临时解封”按钮。

### 3.2 专业模式

在相同状态机和服务层上增加：

- resolved config 与 config migration warning；
- schema/version quartet、Git commit/dirty、文件/manifest SHA-256；
- source/API、等价 CLI、输入 manifest 和输出目录预览；
- P8 per-tone QC、clock drift、phase status、P2/P2-B long-form checks；
- FeatureSet contract、scope/authority hash 和阶段门详情；
- raw structured log 和 Python exception；
- 只读打开 artifact 所在目录。

专业模式不能放宽门禁、编辑权威结果、覆盖输出、改写 source artifact 或解封 final-test。切换模式不改变任何运行状态。

## 4. 主界面

### 4.1 顶部栏

- 项目名称和当前工作区；
- 当前 Git commit/dirty（只读）；
- 模式切换：`简易 / 专业`；
- 当前数据来源 badge：`模拟数据 / 外部参考 / 真实实验`；
- 当前用途：`软件验证 / 科研分析`；
- final-test seal：固定显示“封存”，未经将来独立审批不提供解封动作。

数据来源使用文字、图标和固定颜色共同区分：

| data_origin | UI 文案 | 允许用途 | 固定提示 |
|---|---|---|---|
| `simulated` | 模拟数据 | `software_validation` | 不能形成科研结论 |
| `external_reference` | 外部参考样例 | parser/software validation | 不属于本项目实验，不填写 angle/config/session/repeat |
| `real_experiment` | 真实实验 | diagnostic 或经 gate 批准的 research | 真实不等于自动科学合格 |

### 4.2 左侧步骤轨道

纵向显示 13 个按真实实验顺序排列的步骤按钮。每个按钮有状态 icon、短标题、P 阶段副标题和最近输出时间。用户可以返回查看已完成报告，但不能跳过未满足的 required prerequisite。

### 4.3 中央工作区

中央页固定为四段：

1. “这一步做什么”：非专业说明；
2. “开始前需要”：输入和前置 gate；
3. 主操作区：表单、文件选择、检查清单或运行按钮；
4. “本步结果”：状态、关键数字、原因、输出链接与下一步。

### 4.4 右侧安全检查器

始终显示：data origin、dataset role、run purpose、scientific eligibility、human valid、QC、manual review、phase status、final-test seal、输入 hash、输出不可覆盖状态。任何冲突置顶，并禁用主运行按钮。

### 4.5 底部运行抽屉

默认一行显示当前任务、耗时和取消可用性；展开后显示结构化事件。UI 关闭窗口前若有任务运行，必须要求用户确认；取消只停止 UI worker，不删除已写 evidence。

## 5. 逐步向导：真实实验顺序

### Step 0 — 软件与安全检查

按钮：**检查软件状态**。

- 读取 config、schema versions、Git 状态和 DEV-C16 acceptance bundle。
- 显示 `ready_for_dev_d_diagnostic_experiment` 的准确含义。
- 检查 DEV-D 进入清单是否已由用户确认；UI 不替代人工签字。
- 不自动重跑耗时 DEV-C16；专业模式提供显式“运行软件验证”入口，仅使用 simulated/external-reference。

### Step 1 — 新建实验计划

按钮：**创建实验计划**。

表单选择目的、data origin、measurement mode、设备/配置、方向、session、CONT/REPOS/REASM、reposition/assembly/block、预期次数和 calibration/training/development/final-test 角色。简易模式通过逐页问题生成草稿；专业模式可导入显式 plan/scope。

`final_test` 一经分配即进入 seal 视图，后续调参页面只显示数量/hash，不显示内容。

### Step 2 — 准备 Sweep 采集

按钮：**查看 REW 采集说明**。

这是外部步骤。弹出说明窗口，列出连接、安全、sample rate、REW 导出类型、文件命名不作为 metadata、每次采集后 hash/备份等检查项。UI 不控制 REW、声卡或扬声器。

### Step 3 — 导入 Sweep 文件

按钮：**选择 REW TXT**。

- 打开文件选择窗口，仅作为路径选择，不凭扩展名决定数据语义。
- 随后打开 MeasurementMeta 表单；显示将自动填写和必须人工填写的字段。
- external-reference 模式隐藏并禁止实验身份字段。
- 预检通过后运行统一单测量入口；失败仍保留 run manifest/QC 证据。

### Step 4 — 查看单测量检查

按钮：**查看本次 QC**。

显示 P1、P2-A、P3-A/P3-B 阶段门，frequency coverage、valid points、phase、unavailable 项目、human valid、manual review 和 QC 原因。REW 没有 waveform/headroom/noise-floor/IR/window 时明确显示“数据源未提供”，不伪造 pass。

### Step 5 — 完成 Sweep 条件矩阵

按钮：**检查整组实验**。

用户通过显式 scope/inputs 文件选择或由已批准实验计划生成“待确认草稿”；最终 scope 必须逐项确认，不扫描输出目录。运行 P2-B，显示 missing、duplicate、unexpected、同条件 outlier 和 CONT/REPOS/REASM 稳定性。

### Step 6 — Sweep 特征与分析

按钮组按 gate 依次解锁：

- **生成/查看 Sweep 特征**（P3-A/P3-B，通常已由单测量 run 产生）；
- **方向差异指标**（P4-A）；
- **频带/配置比较**（P4-B）；
- **方向分类验证**（P5-A）；
- **Sweep HR 校准**（P6-A）；
- **训练内 tone 选择与最小数验证**（P9-A/P9-B）。

所有训练、标准化、阈值、tone 选择和模型拟合只允许 training/development scope；final-test 保持不可见。当前参数继续标为 provisional。

### Step 7 — 准备 Multisine 刺激

按钮：**生成诊断刺激**。

- simulated/software-validation 可调用现有 P7。
- real-experiment 可以查看刺激计划、manifest 要求和外部播放说明，但在真实 P8 未开放前，不得把随后真实录音送入分析。
- UI 不提供 overwrite；已有 stimulus ID 时要求新 ID 或选择已有 immutable manifest。

### Step 8 — 外部播放与录音

按钮：**查看播放/录音步骤**、**登记录音文件**。

这是外部步骤。说明窗口要求确认通道、sample rate、时钟、系统 DSP、增益、安全电平、preamble、stable/discard periods。完成后依次弹出 WAV 文件选择、sidecar 表单、stimulus manifest 选择和 hash 复核。UI 不播放、不录音、不声称控制真实设备。

### Step 9 — 导入 Multisine / P8

按钮：**分析 Multisine 录音**。

状态规则：

- `simulated + software_validation`：可运行现有 P1 Multisine adapter/P8。
- `external_reference`：schema 不允许 Multisine external-reference，按钮 blocked。
- `real_experiment`：当前硬 blocked，原因固定为：

> 当前 P8 实现只接受 simulated/software_validation；真实 Multisine 的阈值、设备时钟和采集资格尚未批准。请先完成后续真实设备诊断与独立门禁，UI 不能绕过此限制。

实现依据是现有 `io_multisine.py` 的 `_validate_software_validation_provenance` 门禁；UI 不复制或软化判断。blocked 页面仍允许查看所选文件、hash、缺失字段和未来进入条件，但运行按钮不可用。

### Step 10 — 双入口特征、比较与分类

按钮组：**匹配 tone 特征**（P3-C）、**跨模式指标**（P4-B）、**四协议分类**（P5-B）、**Multisine HR readout**（P6-B）、**跨模式比较/可选校准**（P9-C）。

只有兼容的 persisted FeatureSet、精确 P2-B/P4/P9 authority 和 sealed final-test 才解锁。real-experiment 当前因 Step 9 blocked 而连锁 locked；不允许用 simulated multisine 替代真实缺口。

### Step 11 — 冻结包与单次离线读取

按钮：**构建冻结读取包**、**运行一次离线读取**（P9-D）。

只接受显式 training manifest、已有 authority 和 persisted P8/P2/P7 输入。当前 simulated package 必须显示“仅软件验证，不可部署”；真实 package 在独立批准前 locked。top-1/top-2/margin 显示为描述值，禁止称为置信度。

### Step 12 — 报告、人工决定与归档

按钮：**打开本步报告**、**导出审计索引**、**记录人工决定**。

- 聚合链接而不改写原 manifest；
- 人工决定独立记录，不回写自动 QC，不自动删除样本；
- 显示所有 warning/exclude/unavailable/manual-review 原因；
- 显示输入、配置、Git、schema 和 artifact hash；
- final-test 仍保持 sealed；
- 报告页明确区分 software validation、diagnostic acquisition 和 scientifically eligible canonical analysis。

## 6. 状态机

### 6.1 每个步骤的统一状态

| 状态 | 含义 | 是否可进入下一 required 步 |
|---|---|---|
| `locked` | 上游 gate 未满足 | 否 |
| `ready` | 输入完整，可运行 | 尚未 |
| `external_action` | 等待 REW/播放/录音/物理操作 | 否 |
| `running` | worker 正在调用现有 API | 否 |
| `valid` | 完成且通过 | 是 |
| `warning` | 完成并保留警告 | 由下游现有 gate 决定，UI 不自行升级 |
| `exclude_candidate` | 自动 QC 候选排除 | 否，等待人工/既有策略；不等于删除 |
| `manual_review` | 缺失或不确定 metadata/配对 | 否 |
| `unavailable` | 证据不足，未伪造数值 | 由既有 required policy 决定 |
| `blocked` | provenance/final-test/未实现功能/契约硬失败 | 否 |
| `failed` | 执行或完整性失败 | 否 |
| `stale` | 上游文件/config/scope hash 已改变 | 否，旧输出保留只读 |

状态聚合不能采用“最后一项覆盖前面”。自动 QC 继续遵循既有 `exclude_candidate > warning > valid`；`unavailable`、manual review 和 hard block 分开显示。

### 6.2 会话状态转移

```text
NO_PROJECT
  -> PREFLIGHT_READY
  -> PLAN_DRAFT
  -> PLAN_CONFIRMED
  -> WAITING_EXTERNAL_SWEEP
  -> SWEEP_INPUT_SELECTED
  -> SWEEP_IMPORTED / MANUAL_REVIEW / BLOCKED / FAILED
  -> SINGLE_QC_REVIEWED
  -> DATASET_SCOPE_CONFIRMED
  -> DATASET_QC_READY
  -> SWEEP_ANALYSIS_READY
  -> MULTISINE_PLAN_READY
  -> WAITING_EXTERNAL_RECORDING
  -> MULTISINE_INPUT_SELECTED
       -> BLOCKED_REAL_P8              (real_experiment, current)
       -> MULTISINE_QC_READY           (simulated/software_validation only)
  -> CROSS_MODE_READY
  -> FROZEN_READOUT_READY
  -> REPORT_ARCHIVED
```

任何上游 source/config/manifest/scope/authority hash 变化，会把所有依赖步骤设为 `stale`，但不会删除旧 artifact。用户必须使用新 run-id 重跑。

## 7. 字段自动填写规则

### 7.1 可以确定性自动填写

| 字段 | 来源 | UI 行为 |
|---|---|---|
| pipeline/config/Measurement/FeatureSet version | `version.py` 与 resolved config | 只读 |
| `measurement_mode` | 用户选择的入口 + resolved config | 必须与 metadata 一致；UI alias 仅入口规范化 |
| `source_path` | 文件选择器结果 | 只读显示绝对路径 |
| `source_sha256` | 对所选原文件计算 | 只读，变更即使下游 stale |
| `source_format` | 用户确认的入口类型 | 文件过滤器只辅助，不凭文件名静默决定 |
| `dataset_role` | data-origin schema 固定映射 | external→parser fixture；simulated→software validation；real→research input |
| config snapshot / config hash | resolved config | 只读 |
| stimulus/tone/sample-rate/period 字段 | 选定的 P7 manifest | 只读；sidecar 必须一致 |
| Git commit/dirty | 仓库状态 | 只读 |
| run output root | config + data origin + purpose + run-id | 运行前预览 |
| phase/QC/stage status | 权威 result/manifest | 运行后只读派生 |

### 7.2 可以从计划复制，但必须逐次确认

`device_version`、`configuration`、`angle_deg`、`session_id`、`repeat_type`、`repeat_id`、`experiment_step`、`reposition_round_id`、`assembly_id`、`acquisition_block_id`、`audio_channel`。复制来源必须是已确认 plan/context，不得来自文件名、目录顺序或邻近样本。

### 7.3 永远不得静默自动填写

- `data_origin`；
- `eligible_for_scientific_analysis`；
- human `valid` 与 exclusion reason；
- calibration/training/development/final-test role；
- manual-review 结论；
- angle/config/session/repeat 等实验身份；
- source data type 的科学语义；
- missing condition、pair、tone 或 FeatureSet；
- common clock、approved calibration、final tone set、canonical/deployment 状态。

`eligible_for_scientific_analysis` 默认 false。只有 real experiment、完整 provenance、人工审批和现有 research gate 全部满足时才允许提交 true；UI 仍把最终判断交给 schema/gate。

### 7.4 run-id

UI 可建议 `<plan-id>-<sample-id>-<UTC>`，但显示为可编辑字段并检查单路径组件规则。目标已存在时只提供“生成新 run-id”或“取消”；不提供 overwrite。

## 8. 人类可读错误映射

映射层只翻译，不吞掉原 exception。专业模式始终可展开原始类型和消息。

| 原始类型/状态 | 简易标题 | 用户说明 | 推荐动作 |
|---|---|---|---|
| `ConfigError` | 配置文件不能使用 | 配置缺字段、版本不兼容或值不合法 | 打开配置详情；不要自动改阈值 |
| `P1AdapterError` | 测量文件与说明不一致 | 入口、metadata、sidecar 或文件不匹配 | 重新选择文件或修正 metadata 草稿 |
| `REWManualReviewRequired` / `P1ManualReviewRequired` | 需要人工确认 | 程序不能可靠判断数据类型或 metadata | 查看原因并提交独立人工记录 |
| `UnsupportedREWDataTypeError` | 这不是可用的声学频响 | 可能为阻抗或其他 REW 数据 | 选择 Frequency Response/SPL 导出；不得送入 SPL 路径 |
| `ResearchGateError` / `blocked_research_gate` | 科研资格门禁拒绝 | 输入不是全部合格 real experiment | 改为 software validation 或补齐真实 provenance；不能绕过 |
| `MultisineImportError` 且 real origin | 真实 Multisine 尚未开放 | 当前 P8 只接受模拟软件验证 | 停止分析，保留文件/hash，等待独立真实 P8 门禁 |
| `MultisineConsistencyError` | 录音与刺激不一致 | hash/tone/sample-rate/period/channel 等不一致 | 选择精确 sidecar/manifest，不按文件名猜 |
| `MultisineSynchronizationError` | 找不到有效刺激 | preamble/长度/对齐证据不足 | 检查录音完整性；不返回虚假结果 |
| `MultisineClockDriftError` | 时钟漂移无法可靠处理 | 数据过短、周期不足或校正失败 | 查看 drift 报告并重新诊断采集链 |
| `ToneSetValidationError` / `ToneFeatureConstructionError` | Tone 契约不匹配 | tone 顺序/hash/频率/有效性不一致 | 选择同一 P7 authority；不插值或填零 |
| `DatasetQCInputError` | 数据集范围不完整 | scope、预期矩阵、模式或 FeatureSet 不兼容 | 修正显式 scope/inputs，不扫描目录补齐 |
| P2/P2-B `warning` | 已完成，但有警告 | 保留所有原因 | 查看报告；下游是否允许由既有 policy 决定 |
| P2/P2-B `exclude_candidate` | 建议人工排除 | 自动 QC 发现严重问题 | 记录人工决定；不自动删除/翻转 valid |
| check `unavailable` | 无法判断 | 数据源没有足够证据 | 保留 unavailable，不显示 pass 或 0 |
| `MetricsInputError` / `ComparisonMetricsInputError` | 指标输入不兼容 | FeatureSet/scope/P2-B contract 不匹配 | 使用精确 persisted artifacts |
| `ClassificationInputError` / `CrossModeClassificationInputError` | 分类验证被阻止 | 分组、训练角色、final-test 或 contract 不合法 | 修正 scope；不改 fold 以求通过 |
| `HRInputError` / `HRReadoutInputError` | HR 校准或读取不可用 | 缺少批准 authority/coverage/tone | 补齐真实校准或保持 unavailable |
| `ToneSelectionInputError` / `ProjectionAblationInputError` | Tone 选择门禁拒绝 | training authority、候选集或 fold 不匹配 | 仅用 training/development 重建 scope |
| `CrossModeBridgeInputError` | 跨模式校准被阻止 | 配对/authority/final-test/物理语义不满足 | 查看审计；不强制拟合 |
| `DirectionModelError` / `OfflineReadoutError` | 冻结包或读取输入不可信 | 模型、QC、tone、stimulus 或 hash 不一致 | 使用精确批准 package/manifest |
| `FileExistsError` | 输出目录已存在 | 系统禁止覆盖 | 生成新 run-id |
| 未知 exception | 未知错误，已安全停止 | 未写成功标记 | 保留 failure evidence；专业模式查看堆栈 |

## 9. 运行日志与每步报告

### 9.1 运行日志

每个 UI worker 产生结构化事件：`timestamp_utc`、`ui_session_id`、`step_id`、`run_id`、`severity`、`state_before/after`、API 名称、等价 CLI、输入路径/hash、config/scope hash、输出目录、结果状态、exception type/message。敏感路径可在导出副本中脱敏，但原本地审计保留完整路径。

UI 日志不替代现有 run manifest，也不修改其内容。日志中的成功必须来自返回对象和 loader/hash 验证，不能只看进程 exit code。

### 9.2 每步报告卡

每步报告固定包含：

- 状态和是否允许下一步；
- 数据 origin、purpose、科学/canonical/deployment 资格；
- 输入、配置、scope、authority 和输出 hash；
- 关键结果与全部 warning/exclude/unavailable/manual-review 原因；
- phase status（如适用）；
- 原始报告/CSV/JSON/PNG/manifest 链接；
- 人工决定（独立记录）；
- 下一步及阻塞原因。

简易模式显示摘要；专业模式显示文件列表和验证结果。失败步骤也必须有报告卡，且不显示绿色完成标记。

### 9.3 报告来源

UI 优先读取已有 loader 与 manifest：single-measurement `run_manifest.json`、P8 QC CSV/PNG、P2 JSON/CSV、P2-B bundle、FeatureSet manifests、P4/P5/P6/P9 bundles、offline readout bundle 和 DEV-C16 acceptance bundle。若某阶段没有独立 S2 报告，UI 只生成导航/摘要，不新建科学报告框架。

## 10. UI 按钮到现有脚本/API 的完整映射

UI 实现应在 worker 中直接调用 API；脚本列仅用于命令预览和复现，不能通过拼接 shell 字符串绕过参数验证。

| UI 按钮 | 类型 | 首选现有 API | 等价现有脚本 | 输入/门禁 | 主要结果 |
|---|---|---|---|---|---|
| 检查配置 | 内部 | `config.load_config` | `run_pipeline.py --validate-only` | 显式 config | resolved config + warnings |
| 检查软件状态 | 内部只读 | `pre_experiment_acceptance_outputs.load_acceptance_bundle` | `run_pre_experiment_acceptance.py`（仅显式重跑） | acceptance dir；重跑只限 software validation | readiness/hash；不升级科研资格 |
| 创建实验计划 | UI 表单 | 无科研 API；生成待确认 UI draft | 无 | 人工输入 | plan/scope draft，非 authority |
| 选择 REW TXT | 外部文件选择 | Qt file dialog；随后 `pipeline_dispatch.read_measurement_meta` | 无单独脚本 | 显式文件和 metadata | 路径/hash 预检 |
| 导入 Sweep / 检查本次测量 | 内部 | `run_execution.execute_measurement_run` → `pipeline_dispatch.dispatch_measurement` → `io_rew.load_rew_measurement` → `quality_control.evaluate_measurement_quality` → `features.build_dense_feature_sets` | `run_pipeline.py` | config/input/metadata/output/run-id | P1、P2-A、P3-A/B、immutable run bundle |
| 查看本次 QC | 内部只读 | `quality_control_outputs.load_quality_control_json`、manifest/CSV loader | 无 | 单测量输出 | QC、人类 valid、manual review、stage gate |
| 检查整组实验 | 内部 | `dataset_quality_cli.load_explicit_dataset_qc_inputs` + `dataset_quality_control.evaluate_dataset_quality` + `dataset_quality_outputs.write_dataset_quality_outputs` | `run_dataset_qc.py` | config/scope/inputs/output/run-id | P2-B bundle |
| 生成/查看 Sweep 特征 | 内部/只读 | `features.build_dense_feature_sets`、`feature_outputs.write_dense_feature_outputs` | 通常由 `run_pipeline.py` 完成 | dense SpectrumData + P2 | P3-A/B FeatureSets |
| 匹配 tone 特征 | 内部 | `tone_sets.load_tone_set`、`tone_features.build_sweep_tone_feature_set`、`build_multisine_tone_feature_set`、`build_matched_tone_view`、`matched_tone_outputs.write_matched_tone_outputs` | 当前只有 `run_matched_tone_validation.py` 验证入口 | 精确 P7/P8/P3 contracts | P3-C matched FeatureSets；真实路径当前受 P8 阻塞 |
| 方向差异指标 | 内部 | `metrics.analyze_direction_feature_sets` + `metrics_outputs.write_direction_metrics_outputs` | 当前 `run_direction_metrics_validation.py` 为 simulated 验证 | AnalysisScope + FeatureSets + canonical P2-B gate | P4-A metrics |
| 频带/配置/跨模式指标 | 内部 | `comparison_metrics_cli.load_explicit_comparison_inputs` + `comparison_metrics.analyze_comparison_feature_sets` + output writer | `run_comparison_metrics.py` | config/scope/inputs/P2-B | P4-B bundle |
| 方向分类验证 | 内部 | `classification_cli.load_explicit_classification_inputs` + `classification.analyze_classification_feature_sets` + output writer | `run_classification.py` | config/scope/inputs/P2-B；train-only | P5-A bundle |
| 四协议分类 | 内部 | `cross_mode_classification_cli.load_explicit_cross_mode_inputs` + `cross_mode_classification.analyze_cross_mode_classification` + output writer | `run_cross_mode_classification.py` | config/scope/inputs/P2-B/P4-B；final-test sealed | P5-B bundle |
| Sweep HR 校准 | 内部 | `hr_cli.load_explicit_hr_calibration_inputs` + `hr_analysis.analyze_sweep_hr_calibration` + output writer | `run_hr_calibration.py` | config/scope/inputs/P2-B | P6-A bundle |
| Multisine HR readout | 内部 | `hr_readout_cli.load_explicit_hr_readout_inputs` + `hr_readout.analyze_multisine_hr_readout` + output writer | `run_hr_readout.py` | P3-C/P6-A/P2-B；真实 P8 当前 blocked | P6-B bundle |
| 生成诊断刺激 | 内部 | `stimulus_multisine.generate_multisine` | `generate_multisine.py` | explicit multisine config/output；禁止 overwrite | P7 WAV/tones/manifest |
| 查看 REW 采集说明 | 外部说明 | 无 | 无 | 人工设备操作 | checklist 完成记录 |
| 查看播放/录音步骤 | 外部说明 | 无 | 无 | 人工设备操作 | checklist 完成记录 |
| 登记录音文件 | 文件选择+表单 | Qt dialogs；schema 预检 | 无 | WAV/sidecar/P7 manifest | 待分析显式输入 |
| 分析 Multisine 录音 | 内部 | `p1_adapters.analyze_multisine_adapter` / `io_multisine.analyze_multisine_measurement`，canonical 路径优先 `execute_measurement_run` | `analyze_multisine.py`；开发诊断 `run_multisine_qc.py` | **当前仅 simulated/software_validation** | P1/P8 sparse SpectrumData/QC；真实输入 blocked |
| 训练内 tone 选择 | 内部 | `tone_selection_cli.load_explicit_tone_selection_inputs` + `sweep_multisine_bridge.analyze_tone_selection` + output writer | `select_tones.py` | config/scope/inputs/candidate universe/P2-B/P4-B；train-only | P9-A selection authority |
| 最小 tone 数验证 | 内部 | `projection_ablation_cli.load_projection_ablation_inputs` + `projection_ablation.analyze_projection_ablation` + output writer | `run_projection_ablation.py` | fold-specific P9-A + candidate universe | P9-B bundle |
| 跨模式比较/可选校准 | 内部 | `cross_mode_bridge_cli.load_cross_mode_bridge_inputs` + `cross_mode_bridge.analyze_cross_mode_bridge` + output writer | `run_cross_mode_bridge.py` | explicit pairs/authorities；train-only；final-test sealed | P9-C bundle |
| 构建冻结读取包 | 内部 | `offline_readout_cli.build_readout_package_from_manifest` | `build_readout_package.py` | config + training manifest + new output | P9-D package；simulated 不可部署 |
| 运行一次离线读取 | 内部 | `offline_readout_cli.execute_offline_readout_from_manifest` → `offline_readout.run_offline_readout` | `run_offline_readout.py` | frozen package + explicit input manifest + new output | top-1/top-2/margin/QC bundle |
| 打开本步报告 | 内部只读 | 对应 `load_*_bundle`/manifest reader | 无 | 精确输出目录 | hash 复核后的视图 |
| 记录人工决定 | UI 审计表单 | 不改写自动 QC/MeasurementMeta；写独立 UI audit record | 无 | reviewer/reason/time/linked hashes | manual decision record |
| 运行软件总验收 | 内部耗时、专业模式 | `pre_experiment_acceptance_runner.run_pre_experiment_acceptance` | `run_pre_experiment_acceptance.py` | 仅 explicit simulated/external-reference scope，新 run-id | DEV-C16 acceptance bundle |

“当前只有 validation 脚本”的步骤在 UI 实现时必须直接组合公开 core/output API，并新增薄的 UI orchestration adapter；不得调用 validation fixture 冒充真实分析，也不得复制数学。

## 11. 线程、取消与崩溃恢复设计

- PySide6 主线程只渲染；耗时 API 通过 worker 对象在线程池执行。
- 一个 workspace 同时只允许一个写任务；只读报告可并发。
- worker 接收不可变的参数快照；启动后 UI 不允许修改同一 run 的 config/scope。
- 取消只在 API 安全边界生效。已创建的 failure/import/QC evidence 保留，不删除半成品来伪装“未发生”。
- 重启后 UI 只通过显式最近会话索引和 manifest loader 恢复；不扫描整个 outputs 自动认领结果。
- loader/hash 失败的 artifact 显示 blocked/tampered，不尝试修复原文件。

## 12. 可访问性与文案规则

- 状态不只靠红/绿；配合图标、文字、可读原因。
- 键盘可完成步骤导航、表单和文件选择；焦点顺序按视觉顺序。
- 数字同时显示单位；ppm、dB、Hz、samples 不省略。
- 专业术语首次出现附简短解释，例如“exclude candidate（建议人工排除，不是已删除）”。
- 图表提供文本摘要；日志可复制；长 hash 提供复制按钮但默认折叠。
- 任何“成功”文案必须限定层级，例如“文件导入成功”“软件验证通过”，禁止笼统写“实验成功”。

## 13. DEV-UI1 至 DEV-UI4 固定实施计划

后续只允许以下四轮，不再无限拆分。若发现超范围需求，记录 backlog，不能新增 DEV-UI5。

### DEV-UI1 — Shell、导航与安全状态机

- PySide6 应用骨架、主窗口、简易/专业模式；
- 13 步轨道、状态模型、依赖/stale 传播；
- provenance/final-test/真实 P8 hard-block 展示；
- config/acceptance 只读 preflight；
- 结构化日志框架和服务接口；
- 使用 fake service 做 widget/state tests，不接算法写路径。

退出门槛：导航、状态机、模式切换、blocked/unknown fail-closed、键盘基础可访问性测试通过。

### DEV-UI2 — 计划、外部步骤与单测量双入口接入

- 实验计划/metadata/sidecar 表单与自动填充规则；
- REW、WAV、manifest 文件选择；
- 外部 REW/播放/录音说明弹窗；
- P7 生成、Sweep `execute_measurement_run`、simulated P8 接入；
- 单测量报告、failure evidence、不可覆盖和真实 P8 blocked E2E。

退出门槛：真实 Sweep 可按既有门禁运行；simulated Multisine 可运行；real Multisine 必须被 UI 与 core 双重拒绝。

### DEV-UI3 — Dataset 与 P3–P9 专业分析编排

- 显式 scope/input/authority 选择器；
- P2-B、P3-C、P4、P5、P6、P9 adapters；
- training/development/final-test 可视化隔离；
- 每步 report card、CSV/JSON/PNG 浏览与 hash loader；
- 不使用 validation fixture 冒充真实路径。

退出门槛：simulated 全链 UI E2E 与 failure/manual-review/stale 流程通过；算法输出与 CLI/API 基线一致。

### DEV-UI4 — 收尾、可访问性、打包与用户验收

- 人类可读错误映射完整实现；
- 崩溃恢复、取消、长任务体验、日志导出；
- 可访问性、HiDPI、Windows 路径和打包验证；
- 用户操作手册、截图、安装/卸载和验收清单；
- 全量回归与 UI acceptance bundle。

退出门槛：四轮范围验收完成；不增加研究功能，不开放真实 P8，不创建 release/科研/部署声明。之后只允许缺陷修复与 DEV-D 独立决策，不再新增 DEV-UI 功能轮次。

## 14. DEV-UI1 的测试设计入口

DEV-UI1 开始时先写失败测试，至少覆盖：

- 默认简易模式；
- 专业模式不改变 state/gate；
- 三种 data origin 文案和资格不同；
- real Multisine/P8 固定 blocked；
- unknown state fail closed；
- warning、exclude、unavailable、manual review 不互相覆盖；
- 上游 hash 变化使下游 stale；
- 已存在输出没有 overwrite 动作；
- final-test 不显示内容或解封动作；
- 外部步骤只显示说明/表单/文件选择，不调用播放或录音；
- worker 运行时 UI 不冻结，取消不删除 evidence；
- 简易错误文案与专业原始 exception 同源；
- report card 只从 result/manifest 派生。

## 15. 已知限制与进入 DEV-UI1 门槛

- 当前真实 Multisine/P8 由 core 明确拒绝；UI 只能显示并保留这一阻塞。
- 真实设备型号、采样时钟、方向数、样本量、阈值、tone set 和校准均未冻结，表单不得虚构默认值。
- 若某 P 阶段只有 simulated validation CLI，DEV-UI3 需要薄 orchestration adapter 调用现有 core/output API；不能复用 simulated fixture 作为真实路径。
- UI 不提供设备控制、实时处理、自动采集、final-test evaluation 或云服务。
- PySide6 依赖版本、打包工具和最低系统版本在 DEV-UI1 环境核对后固定；DEV-UI0 不提前声明。

进入 DEV-UI1 前必须确认：本设计获批准；当前分支和 DEV-C16 acceptance 可追溯；PySide6/测试依赖方案确定；UI-owned draft/audit 文件位置获批准；四轮边界不变。

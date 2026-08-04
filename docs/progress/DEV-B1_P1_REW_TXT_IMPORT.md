# DEV-B1：P1 REW Frequency Response TXT 导入

## 状态与日期

- 状态：完成
- 日期：2026-08-04
- 分支：`feature/v2-dual-input`
- 对应提交：`45719bf3b9d7f3229eb4c589023ea5ad32902cbc`

“完成”表示 P1 直接导入接口及其格式/门禁回归已经完成，不表示完整 pipeline 已连通，也不表示官方参考曲线可以支持科研结论。

## 本步目标

用测试驱动方式实现安全的 REW Frequency Response TXT adapter：兼容常见文本变体，生成 canonical dense `SpectrumData`，并在导入边界执行来源哈希、人工确认和 research hard gate，防止阻抗、外部参考或不确定数据进入错误分析路径。

## 完成范围

- 支持 `*`、`#` 注释行，以及空格、TAB、逗号、分号分隔。
- 支持 frequency + magnitude 两列和可选 phase 第三列；phase 从 degree 转为 radian。
- 通过数字块和语义 SPL/impedance 标记识别内容，不锁定某一条真实 REW 表头文本。
- 要求至少 5 个点、频率有限且严格递增唯一、数据列数一致。
- 返回 `representation=dense_spectrum` 的 `SpectrumData`，magnitude quantity 为 `spl`。
- 缺 phase 时标为 `phase_status=unavailable`；有 phase 时标为 `relative_unreliable`，不暗示可直接用于后续相位建模。
- 文件缺少 headroom、noise floor 和 raw waveform 时，对应 QC 全部记录为 `unavailable`。
- 明确拒绝 impedance/ohm 数据；无法确认声学 SPL 类型或 metadata 有 unresolved manual-review reasons 时要求人工确认。
- 导入前校验原文件 SHA-256，并调用 DEV-B0 research hard gate。
- 增加 synthetic 成功/失败 fixtures，以及三份用户提供的官方 REW 样例的 byte-immutable 格式回归。
- external reference 的实验身份字段必须全部为空；schema 主动拒绝为其填造设备、配置、角度、session、repeat、grouping 或 experiment-step metadata。

## 明确未完成范围

- `run_pipeline.py` 尚未把 P1 adapter 路由到完整 P2–P6 流程；当前接口是直接、经过测试的模块入口。
- 没有项目自己的 `real_experiment` REW fixture，未进行真实实验分析或声学结论判断。
- 没有实现 P1 multisine adapter、P8 同步/clock drift/传递估计、P3–P6、P9、T0–T3 或 S2 完整报告。
- 没有从文件名自动解析或猜测 angle、configuration、session、repeat 等实验 metadata。
- impedance 当前在声学 SPL adapter 中明确拒绝；尚未实现独立阻抗数据模型或人工审核工作流。
- REW TXT 本身没有的 headroom、noise floor、raw waveform 信息没有被重建或估计。

## 关键设计决策

| 决策 | 结果 |
|---|---|
| 解析数字块，不锁定整行表头 | 容许真实导出表头变化，同时仍要求语义上能够确认 acoustic SPL。 |
| 未知类型不按文件名猜测 | impedance 明确拒绝；无法确认 SPL 时抛出 `REWManualReviewRequired`。 |
| 两列与三列保持同一 canonical 输出 | 缺 phase 使用 `None` + `unavailable`，不生成虚假 phase。 |
| 频率轴在 adapter 边界严格校验 | 非有限、重复、下降或少于 5 点均拒绝，避免无效 dense spectrum 下传。 |
| 来源哈希先于数据使用 | `source_sha256` 不匹配立即失败，官方回归由 manifest 固定。 |
| external reference 不拥有实验身份 | measurement schema 2.2 允许其身份字段为 `None`，并拒绝任何伪造填充。 |
| 缺失 QC 显式不可用 | 不从 frequency-response TXT 猜测 headroom、noise floor 或 raw waveform。 |
| import 内调用 hard gate | 即使 parser 格式通过，external reference 仍不能进入 `research_analysis`。 |

## 修改文件

提交 `45719bf` 修改 30 个文件：

- Git/文档：`.gitattributes`、`README.md`、`MIGRATION_V1_TO_V2.md`、`CHANGELOG.md`、`docs/DEV_A_TEST_AND_MOCK_PLAN.md`
- 配置/版本：`config/default.yaml`、`config/schema_versions.yaml`、`src/acoustic_encoder/version.py`
- 功能/schema：`src/acoustic_encoder/io_rew.py`、`src/acoustic_encoder/schemas.py`
- 测试：`tests/test_io_rew.py`、`tests/test_research_gate.py`、`tests/test_schemas.py`
- 官方回归：`tests/fixtures/rew/external_reference/Artist 3 + Q2070Si.txt`、`BW M1.txt`、`REL Sub, No EQ.txt`、`manifest.json`
- synthetic fixtures：`bad_line.txt`、`comma_with_phase.txt`、`decreasing_frequency.txt`、`duplicate_frequency.txt`、`empty.txt`、`impedance.txt`、`no_phase.txt`、`nonfinite_frequency.txt`、`semicolon_with_phase.txt`、`space_with_phase.txt`、`tab_with_phase.txt`、`too_short.txt`、`unknown_type.txt`

`.gitattributes` 对三份 official external-reference TXT 使用 `-text`，以保留上传文件的原始 CRLF 字节并使 SHA-256 跨 checkout 稳定。

## Schema/config 变化

| 项目 | DEV-B0 | DEV-B1 |
|---|---:|---:|
| `pipeline_version` | `2.0.0-dev.1` | `2.0.0-dev.2` |
| `config_schema_version` | `2.1.0` | `2.1.0`（不变） |
| `measurement_schema_version` | `2.1.0` | `2.2.0` |
| `feature_schema_version` | `2.0.0` | `2.0.0`（不变） |

Measurement schema 2.2 将 `device_version`、`configuration`、`angle_deg`、`session_id`、`repeat_type`、`repeat_id` 和 `experiment_step` 改为可空类型，但只允许 `external_reference` 缺失这些实验身份；同时 external reference 必须不携带上述字段及 `reposition_round_id`、`assembly_id`、`acquisition_block_id`。`simulated` 和 `real_experiment` 继续要求原有实验身份字段和有限角度。

## 使用的数据来源及科研资格

### Synthetic fixtures

`tests/fixtures/rew/synthetic/` 中的文件是为 parser 成功和失败路径人工构造的数据。它们只用于单元测试，不是测量结果，也没有科研资格。测试中的 real-experiment metadata 仅用于验证 admissible schema/gate 组合，不能把 synthetic 文件转化为科研证据。

### 官方 REW 样例

| 文件 | SHA-256 | 点数 | 声明 | 科研资格 |
|---|---|---:|---|---|
| `Artist 3 + Q2070Si.txt` | `f06000bd7bc11923a23dc7d54e9c72d0d6e55c3804755c5cb8583bc13131454d` | 1289 | `external_reference` / `parser_fixture` | 不合格；仅 `software_validation` |
| `REL Sub, No EQ.txt` | `29bcfb447d7c1087df2ef217f324f3a0f86645896f357e5faa7bc1ef618279c9` | 589 | `external_reference` / `parser_fixture` | 不合格；仅 `software_validation` |
| `BW M1.txt` | `cc863c23f0f4ebf3cc4d875f9a511b76b1d3e20a391ffc7a47745d8f53365447` | 1289 | `external_reference` / `parser_fixture` | 不合格；仅 `software_validation` |

这些文件由用户提供并说明为 REW 官方样例导出。仓库不把曲线名称解释为项目设备、configuration、angle、session 或 repeat。DEV-B1 没有使用项目 `real_experiment` 数据。

## 执行的验证命令和准确结果

在提交前的最终工作树上实际执行：

```powershell
python -m pytest -q
```

准确结果：

```text
44 passed in 2.14s
```

```powershell
python -m compileall -q src scripts
```

准确结果：退出码 0，无标准输出。

代码和文档的 staged whitespace 检查：

```powershell
git diff --cached --check -- . ':(exclude)tests/fixtures/rew/external_reference/*.txt'
```

准确结果：退出码 0，无标准输出。三份官方 TXT 因必须保留原始 CRLF 字节而从该文本空白检查中排除；其不可变性由 pytest 中的 manifest SHA-256 回归覆盖。

另外执行：

```powershell
git ls-files --eol -- "tests/fixtures/rew/external_reference/*.txt"
```

准确结果：三份文件均显示 `i/crlf w/crlf attr/-text`。

## 已知限制

- parser 依赖注释或表头中的语义标记确认 acoustic SPL；无法确认时需要人工审核。
- 当前只支持两列或三列 frequency-response 数值块，不支持任意额外列或 mixed column count。
- phase 仅保存为 `relative_unreliable`，没有 common-clock 或 drift-correction 证明。
- 官方样例只冻结格式变体；它们不能验证项目设备的真实命名、频带、导出选项或 metadata 流程。
- 尚无真实两列、无 phase 的项目导出回归。
- P1 尚未成为完整 run pipeline 的端到端入口。

## 对应 Git commit

```text
45719bf3b9d7f3229eb4c589023ea5ad32902cbc
feat(io): import REW frequency-response TXT safely
```

## 下一步及进入门槛

可选的下一最小切片是 DEV-B2：在已知 `H(f)` 的模拟数据上测试驱动实现 P8 同步、delay/drift 检测、tone/transfer recovery 和相应 QC；或先把 P1 安全接入 pipeline 路由。进入门槛为：

- 保持 DEV-B0 hard gate 和 DEV-B1 source-hash/manual-review 边界不可绕过；
- 明确新切片的 canonical 输入/输出及失败报告，不把 placeholder 当作实现；
- 模拟 P8 结果只属于 `software_validation`；
- 任何真实 sweep 科研分析必须先提供未经编辑的项目 REW TXT、明确实验身份、provenance 记录、SHA-256 和 eligibility；如项目实际产生两列无 phase 导出，应保存为不可变真实格式回归；
- 在没有合格 `real_experiment` 前，不进入科研结论阶段。

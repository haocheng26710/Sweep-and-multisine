# GEN-ENC-2C 科学实例身份生成与静态资格合同（PHASE A）

版本：`GEN-ENC-2C-PHASE-A-v1`

日期：2026-08-28

终态：`READY_FOR_GUARDIAN_REVIEW`

证据等级：`E0_IDENTITY_GENERATION_CONTRACT`

`execution_authorized=false`，`phase_b_authorized=false`，`scientific_identity_generation_authorized=false`，`preflight_authorized=false`，`gen_enc_2_authorized=false`，`final_test=sealed`，`final_test_read=false`

## 增量 metadata

- **新增**：正式四家族 80 槽科学实例身份生成、abstract CAD/static eligibility、canonical serialization、路径、状态、失败保槽、hash 与静态验收合同。
- **关联旧文件**：sealed GEN-ENC-2A REV01 数值合同与全部控制产物；sealed GEN-ENC-2B E1 generator source bundle 与两次 guardian review；科研范围账本、监管章程与 TRANS/INFO-TOP 权威报告。
- **未改变**：FORMAL、SUP、V2.5、Scheme 3A、TRANS、INFO-TOP、GEN-ENC-0R/1/2A/2B 的报告、机器产物、证据等级、科学结论、RQ 状态及 final-test 封存。
- **证据等级**：`E0_IDENTITY_GENERATION_CONTRACT`；若另行批准 PHASE B，最高仅为 `E2_SCIENTIFIC_INSTANCE_IDENTITY_AND_STATIC_ELIGIBILITY`。
- **覆盖**：`overrides=false`；本文件是严格增量 addendum，不回写或替代任何旧合同。

## 1. 当前边界与未来证据上限

本 PHASE A 只冻结合同，不运行 generator，不执行任何正式 RANDOM member seed 或 PHYSICS master seed，不从 HAND/NEAR 20 行表派生 CAD/topology payload，不生成、保存、审查或哈希任何正式 scientific instance manifest，也不运行测试性正式输出。

本阶段禁止读取或写入 response，禁止 timing、endpoint、family comparison、search、optimization、classification、training、simulation、COMSOL、full-wave、physical CAD kernel 或实体实验，禁止读取 project/legacy scientific data、development、validation 或 final-test。`scientific_hypothesis_status=NOT_TESTED`。

若 guardian 另行批准 PHASE B，其最高证据只允许是 `E2_SCIENTIFIC_INSTANCE_IDENTITY_AND_STATIC_ELIGIBILITY`：证明 80 个固定槽位具有可复验的数值身份，以及抽象 CAD/接口/成本静态门禁状态。它不是性能、响应、频率端点、family 优劣、可制造性、全波、实体或机理证据。静态资格通过也不表示 scientific hypothesis 通过。

## 2. 不可变源码、运行时与 REV01 绑定

任何未来 PHASE B 必须同时绑定：

- `generator_source_sha256=05e35257a101b2542dc03b2d4f5bea07b1d5548a8d2c43efe08722debc32fc02`
- `source_bundle_sha256=eded165d2c0bd806efe2c618886a6dbf5c874f45bd3191c0128daa23b887916d`
- source bundle 42 个 entry 的 exact path/byte/hash/role；其中 REV01 20 个 controlling artifacts 及 PHASE A 5 个 controlling specs 逐项不变。
- sealed runtime semantics：Python `3.12.4`、pytest `9.1.1`、jsonschema `4.19.2`，以及 IEEE-754 binary64、round-to-nearest ties-to-even 和 Python 标准库数值/JSON 行为。

任何 byte、path、schema、fixture、test、dependency semantic、numeric-runtime semantic、REV01 controlling artifact 或 2B controlling spec 改变，立即使授权与身份失效。必须停止、保留旧 hash、报告精确差异并回到 guardian review；不存在“仅格式化”“仅重构”例外。

永久冻结 RANDOM open-uniform 的 binary64 实现：先直接计算 `u=((z>>11)+0.5)/2^53`；仅当该直接 binary64 结果严格等于 `1.0` 时，返回 `math.nextafter(1.0,0.0)`。禁止任何其他 clamp、epsilon、endpoint repair、redraw 或 distribution 修改。

## 3. 四家族、80 槽与生成身份

正式 family 顺序固定为：

1. `HAND_DESIGNED`
2. `NEAR_INDEPENDENT`
3. `FIXED_SEED_RANDOM_DISORDERED`
4. `PHYSICS_METAMATERIAL_INSPIRED`

每家族恰好 20 个槽，总计 80；不得删除、缩小、换序或补生成替代成员。

- HAND：`HAND_01` 至 `HAND_20`，按 sealed `family_design_tables_rev01.json#/hand_designed/rows` 的存储顺序精确读取；逐行保留 exact keys、数值和 derived q270，一行对应一槽。
- NEAR：`NEAR_01` 至 `NEAR_20`，按 sealed `#/near_independent/rows` 精确读取；不得选择 alpha、排序或修正。
- RANDOM：`RANDOM_01` 至 `RANDOM_20`，依序绑定正式 seeds `2026090101..2026090120`。每 seed 按冻结 13 参数顺序一次抽样；无 redraw；零边、断连或弱样本仍保留原槽。
- PHYSICS：`PHYSICS_01` 至 `PHYSICS_20`，共同绑定 formal master seed `2026090200`，并依序绑定 member identity seeds `2026090201..2026090220`。使用 15 参数、20 strata、parameter-specific Fisher–Yates midpoint LHS；无 jitter、替换或性能分支。

所有 bounds、DOF、参数顺序、inverse CDF、reciprocity、volume partition 与 CAD mapping 由 sealed REV01 控制，2C 不作语义修改。正式 member mapping 详见 `family_member_identity_spec.json`。

## 4. 正式对象、路径和 canonical JSON

未来 PHASE B 只能写入：

`outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/scientific/`

成员文件路径固定为 `instances/<family_id>/<member_id>.identity.json`；四个 family manifest 固定为 `manifests/01_HAND_DESIGNED.manifest.json` 至 `04_PHYSICS_METAMATERIAL_INSPIRED.manifest.json`；总体 index 固定为 `scientific_identity_index.json`。不得写入 tests、fixtures、GEN-ENC-2B 或任何 technical-fixture 路径。

正式对象的 `object_class` 必须是 `SCIENTIFIC_INSTANCE_IDENTITY_AND_STATIC_ELIGIBILITY`，不得带 `TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY` 或任何 technical-fixture 身份。任何 fixture 也不得进入上述 scientific root。

所有正式 JSON 使用 2B 已封存 canonical JSON：UTF-8、无 BOM、Unicode code point 递归 key 排序、array 保序、shortest round-trip number、无无意义空白、无 trailing newline、SHA-256 lowercase hex。每个 member 文件先独立哈希；family manifest 按冻结 member order 记录 20 个 path/hash/status；总体 index 按冻结 family order 记录四个 family manifest path/hash。总体 `identity_index_sha256` 是总体 index exact canonical bytes 的 SHA-256，写入另行 result seal，不自包含于 index。

PHASE A 中四个 family manifest hash、全部 member file hash、总体 index/hash 均必须为 null，生成/写出/复核计数为 0。

## 5. Abstract CAD 与 static eligibility

每个成员的输入字段必须覆盖 family/member/order provenance、正式 seed 或 sealed table row provenance、完整参数向量和顺序、bounds、DOF、source/runtime hashes、matched-cost/interface/frequency/nuisance controlling hashes。不得包含 response 或性能字段。

静态输出必须覆盖：

- nominal connected-volume target `3.014899604922098e-5 m3` 与闭区间 `[2.984750608872877e-5, 3.0450486009713192e-5] m3`；
- U4 x/y/z 独立 envelope caps `0.227302/0.227302/0.0122 m`；
- interface identity `U4_CARDINAL_4PORT_CENTRAL_M1_v1`、ports/states/sensors `4/4/1`、exact counts 与 `0.0002 m` dimension tolerance；
- exactly one connected component；minimum designed feature `0.002 m`；minimum solid load path `0.0016 m`；
- `DOF<=16`、参数 bounds、matched-cost interval 与 deterministic bisection/Boolean-union abstract audit。

允许的 member technical terminal status 只有：

- `STATIC_IDENTITY_ELIGIBLE`
- `COST_INELIGIBLE`
- `GENERATION_TECHNICAL_FAILURE`

`STATIC_IDENTITY_ELIGIBLE` 只表示静态身份与抽象资格通过，不是可制造性或科学正结果。`COST_INELIGIBLE` 是 volume/envelope/interface/connectivity/min-feature/load-path/DOF/bounds 等静态不合格；`GENERATION_TECHNICAL_FAILURE` 是 generator/schema/hash/runtime/serialization/algorithm failure。任何失败都不能重分类为 scientific negative。

## 6. Fail-closed、部分失败和不可替换槽位

失败成员必须保留原 family、member ID、family/member order、seed 或 table row、输入身份与失败原因。禁止修参、重抽、替换、丢弃、改变阈值、扩大 tolerance、缩小 member/family/state 数或在合同冻结后补生成替代成员。

family 始终保留 20 槽。family 终态为：20/20 eligible 时 `FAMILY_STATIC_IDENTITY_COMPLETE`；20 槽均有不可变身份记录但至少一槽 `COST_INELIGIBLE` 时 `FAMILY_COMPLETE_WITH_COST_INELIGIBLE_SLOTS`；至少一槽为 technical failure 时 `FAMILY_TECHNICAL_FAILURE_BLOCKED`。

总体终态为：四家族 80/80 eligible 时 `SCIENTIFIC_IDENTITY_AND_STATIC_ELIGIBILITY_COMPLETE`；存在 cost-ineligible 但无 technical failure 时 `SCIENTIFIC_IDENTITY_COMPLETE_WITH_COST_INELIGIBLE_SLOTS`; 存在任一 technical failure 时 `SCIENTIFIC_IDENTITY_GENERATION_TECHNICAL_FAILURE_BLOCKED`。后两种状态均阻断 timing preflight 和 GEN-ENC-2；不得用替代成员恢复。任何缺槽、重复 ID、hash/schema/path/source/runtime mismatch 也一律技术阻断并要求 guardian result-seal review。

## 7. 禁止字段和零访问保证

scientific member manifests、family manifests 和总体 index 中禁止出现 response、score、metric、frequency response、endpoint、ranking、selection、timing feasibility、development、validation 或 final-test 数据或字段，以及这些概念的大小写/下划线/连字符变体。正式 schema 采用 allow-list 与 `additionalProperties=false`；独立 recursive forbidden-name audit 必须为零命中。

本阶段及未来身份生成阶段均不得读取上述数据。允许携带 frequency/nuisance **contract hash provenance**，但不得携带 frequency response、nuisance response 或任何计算结果。

## 8. 静态验收与复验边界

PHASE A 自检只允许：JSON parse、REV01/2B controlling hash 复验、路径冲突检查、字段覆盖、禁止字段集合、family/member/order/seed/table provenance 静态检查、依赖图/stop rule 一致性和 SHA256SUMS 复核。不得导入或调用 generator APIs，不得执行正式 seed，不得派生 HAND/NEAR payload。

若 PHASE B 获批，独立复验器也只能验证 identity/static eligibility：80 槽、每家族 20、unique IDs、schema/canonical bytes/hash、source/runtime binding、family order、seed/table provenance、bounds/DOF、static CAD/cost audit、零 response 访问和零性能字段。复验器不得计算 endpoint、family statistic、ranking、selection 或 timing feasibility。

## 9. 依赖顺序、资源和停止

唯一依赖顺序为：

`GEN-ENC-2C PHASE A guardian review -> PHASE B formal identity generation/static audit -> PHASE B result seal -> separate timing preflight contract -> separate GEN-ENC-2 execution contract`

SUP-3 与 TRANS reclosure 不是依赖。本合同不恢复、关闭或替换任何 active RQ；`active_questions_closed=0`，`bidirectional_discovery_established=false`。

资源仅限普通本地确定性生成和静态数据审计。若需要 physical CAD kernel、solver、高资源、许可、破坏性操作或改变科学合同，立即停止并报告，不得降级或改写范围。

REV01 nuisance 限制永久保留：3675-cell mixed-level strength-2 joint design，不等价于 128625-cell full Cartesian；遗漏 124950 cells；六个 within-group two-factor interactions 与所有 three-way/higher interactions 未识别。本阶段不得生成 nuisance responses。

所有授权字段初始且持续为 false，所有执行/读取计数为 0，四个 family manifest hashes 与总体 identity index/hash 为 null，final-test 始终 sealed 且 `final_test_read=false`。合同完成后停止，等待中间主控提交 guardian review；不联系守门任务，不 commit、push、tag 或 release。

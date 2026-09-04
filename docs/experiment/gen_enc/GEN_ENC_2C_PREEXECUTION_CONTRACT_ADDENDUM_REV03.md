# GEN-ENC-2C 预执行合同整合增量 REV03

版本：`GEN-ENC-2C-PREEXECUTION-CONTRACT-INTEGRATION-REV03-v1`  
日期：2026-08-28  
终态：`READY_FOR_INTERMEDIATE_ACCEPTANCE_AND_GUARDIAN_PREEXECUTION_REVIEW_EXECUTION_BLOCKED`  
证据等级：`E0_PREEXECUTION_CONTRACT_INTEGRATION`

`execution_authorized=false`，`phase_b_authorized=false`，`scientific_identity_generation_authorized=false`，`static_eligibility_authorized=false`，`preflight_authorized=false`，`timing_preflight_authorized=false`，`gen_enc_2_authorized=false`，`scientific_hypothesis_status=NOT_TESTED`，`final_test_read=false`。

## 增量 metadata

- 新增内容：把 CAD-0 用户批准的 U1/U2/U3 权威、CAD-1 Attempt06 已封印 E1 技术资格和 2C REV02 authority-gap 诊断整合为未来单独 GEN-ENC-2C 执行任务的可审查合同。
- 关联旧文件：完整关系和 SHA-256 见本包 `relates_to.json`、`authority_bindings.json`。
- 未改变内容：FORMAL、SUP、V2.5、Scheme 3A、TRANS、INFO-TOP、GEN-ENC-2A/2B、既有 2C、CAD-0/CAD-1 的任何文件、结论、证据等级与 hash。
- 证据等级：仅 `E0_PREEXECUTION_CONTRACT_INTEGRATION`。
- `overrides=false`。旧 2C REV01 脚本和 schema 仍是被拒绝、禁止 import/执行/原地修补的 provenance。

## 1. 范围与证据边界

primary scope 固定为四家族各 20、共 80 个不可替换槽：`HAND_DESIGNED`、`NEAR_INDEPENDENT`、`FIXED_SEED_RANDOM_DISORDERED`、`PHYSICS_METAMATERIAL_INSPIRED`。不得减少家族、成员、四状态，亦不得取消未来 held-out 45/135/225/315° 和 0:15:345° sampled continuous-angle bridge 义务。

本 REV03 只建立合同；没有生成正式成员或身份，没有执行正式 seed、table row、generator、orchestrator、verifier、mapping compiler 或 static audit。没有 timing、response、endpoint、comparison、search、optimization、simulation、COMSOL、full-wave、physical CAD kernel 或实体实验；没有读取 development、validation 或 final-test。

未来单独获批的 2C 执行最高只能建立 `E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY`：数值身份、权威绑定和抽象静态资格。它不等于性能、响应、endpoint、family 优劣、制造性、计时、全波、物理或科学证据；`scientific_hypothesis_status=NOT_TESTED`。

## 2. 权威链

数值身份绑定 GEN-ENC-2A REV01；generator 绑定 `generator_source_sha256=05e35257a101b2542dc03b2d4f5bea07b1d5548a8d2c43efe08722debc32fc02` 和 `source_bundle_sha256=eded165d2c0bd806efe2c618886a6dbf5c874f45bd3191c0128daa23b887916d`。正式 binary64 open-uniform 只允许直接公式结果等于 1.0 时使用 `math.nextafter(1.0,0.0)`。

CAD-0 U1/U2/U3 的精确选择、语义、路径、JSON pointer 和 hash 见 `authority_bindings.json`。其中 U1 冻结修正 T1 和 exact fixed-interface exception；U2 冻结 RANDOM shared-plenum、reduced graph descriptive-only 与独立 actual-fluid BFS；U3 冻结 exact SPINE/WINDOW_1..3/OUTER_1 slot ledger 和 burden disclosure。

CAD-1 绑定 Attempt06 run ID `c256d5a49c7dfa1e4d59b38a3bef39c0bd6635dca9bfc527a3e306f460c2566d`、技术包 `SHA256SUMS` hash `ac692e043813c419bc3a1a42c650d8c9bd5164208597b262a0108009ebd269c7` 和 seal review hash `2e30d9aba91acb4b95ac5f6a7ced02736e926a8168417747306f3dd77960027a`。dispatch 和 run ID 已消费，禁止作为 2C 标识复用。CAD-1 仅证明 implementation/schema/fixtures/independent-verifier technical conformance，不证明任何 formal member 合格。

永久披露：release UTF-8 字节计数修正；PowerShell throw tokenization 修正；非权威 cache 目录初判后只读确认 exact CAD-mapping cache 缺失；post-package 首次读取错误顶层 `aggregate_hashes` 后在 `complete_run_manifest.aggregate_hashes` 只读复验全部通过。CORR04 根目录及两个空后代目录保留 provenance，不得由本合同清理。

## 3. REV02 gap closure

REV02 的 11 项 CAD/static 语义权威缺口均由已获用户确认的 CAD-0 链闭合，并由 CAD-1 E1 提供技术资格；精确矩阵见 `gap_closure_matrix.json`。这只闭合“未来可实现合同所需权威”，不等于 80 个正式成员已验证。

REV01 A–G 缺陷仍留在被拒绝 bytes 中，安全复用数为 0。A–F 被转化为未来新执行任务的硬性实现/预检要求；G 的科学语义权威已由 CAD-0/CAD-1 链闭合。任何未来实现无法逐项满足时必须 `TECHNICAL_PRECONDITION_REJECTED` 或 `GENERATION_TECHNICAL_FAILURE`，不能补默认值或工程判断。

## 4. 身份、路径与 hash 链

exact 80-slot ordering 见 `slot_ordering_contract.json`。HAND/NEAR 使用 exact row；RANDOM 每 seed 一次抽样；PHYSICS 使用 formal master seed、parameter-specific Fisher–Yates midpoint LHS；一律 no redraw/no repair/no replacement，失败保槽。

未来 85 个 scientific JSON、6 个 result 文件和 1 个 progress report 的路径、9 个 future schema 路径、canonical JSON、member→family→index→result hash 链见 `future_execution_contract.json`。这些 future schema 和执行脚本本阶段未创建、未 import、未运行；必须在单独 2C 执行任务中先冻结并经授权 preflight。

## 5. 静态资格与可证伪状态

正式 member terminal status 仅 `STATIC_IDENTITY_ELIGIBLE`、`COST_INELIGIBLE`、`GENERATION_TECHNICAL_FAILURE`。模板或执行前置状态另为 `TEMPLATE_VALIDITY_REJECTED` 与 `TECHNICAL_PRECONDITION_REJECTED`，不得伪装成 member 科学阴性。

检查必须从权威链推导而不是复制：nominal volume `3.014899604922098e-5 m3`、闭区间 `[2.984750608872877e-5,3.0450486009713192e-5]`、U4 envelope caps `0.227302/0.227302/0.0122 m`、interface `U4_CARDINAL_4PORT_CENTRAL_M1_v1`、ports/states/sensors `4/4/1`、dimension tolerance `0.0002 m`、general minimum feature `0.002 m`、general solid load path `0.0016 m`、`DOF<=16`、parameter bounds、root/Boolean union/ownership 和 actual-fluid exactly-one-component。

RANDOM zero edge 的定义是 sealed edge value 等于 0 时该 reduced scientific edge 缺席，禁止 epsilon；shared plenum/fixed spine 仍可使 actual fluid connected。reduced component count 只描述，不作 eligibility/performance gate；actual fluid component 由 exact fluid union 上 positive-area face adjacency BFS 独立计算，必须恰为 1。

## 6. verifier、orchestrator 与 fail-closed

future verifier 必须只读、独立重算全部 80 参数和 CAD/static/hash/runtime binding，不得 import generator 或 orchestrator。任何异常均须原子生成 schema-valid fail-closed record，记录真实 observed counts，绝不产生科学解释。

orchestrator 在任何 seed 或写入前必须复验自身、verifier、全部 schema/source/authority manifests；确认 exact output roots、92 个允许目标、零 unlisted files、零 collision，并检查 containment、祖先 reparse/symlink/junction、大小写折叠、保留名和 trailing dot/space 边界。

## 7. 依赖与停止

唯一顺序：REV03 中间主控验收 → guardian preexecution review → 用户/阶段明确授权 → 单独 GEN-ENC-2C 执行任务 → 结果 guardian seal → 单独 timing preflight 合同与任务 → timing 结果 seal → 单独正式 GEN-ENC-2 合同与任务。

CAD-1 E1 不是 2C 执行授权。SUP-3 和 TRANS 独立重闭合不是依赖，不得启动。任何科学合同变化、资源明显扩张、权威/hash/runtime/schema/path 缺失均 fail closed 并返回 guardian/user；不得自行补齐。

本 REV03 完成即停止，只交中间主控验收和 guardian review；不 commit、push、tag 或 release。

# GEN-ENC-2C 分阶段执行实现与哈希冻结合同 S1

版本：`GEN-ENC-2C-REV03-S1-IMPLEMENTATION-FREEZE-v1`  
日期：2026-08-28  
终态：`READY_FOR_INTERMEDIATE_ACCEPTANCE_AND_GUARDIAN_IMPLEMENTATION_HASH_FREEZE_REVIEW_FORMAL_EXECUTION_BLOCKED`  
证据等级：`E1_TECHNICAL_IMPLEMENTATION_CONFORMANCE_ONLY`

## 增量 metadata

- 新增：REV03 要求的全新 orchestrator、只读独立 verifier、9 份 schema、92-path allowlist、task-bound S1 authorization、ordinary technical fixtures/tests 和 exact-byte manifests。
- 关联旧文件：`GEN_ENC_2C_PREEXECUTION_CONTRACT_ADDENDUM_REV03.md`、REV03 integration package、guardian REV03 preexecution review、sealed GEN-ENC-2B/CAD-0/CAD-1 authorities；machine-readable 关系见 S1 `relates_to.json`。
- 未改变：旧 2C REV01/REV02、CAD-0/1、GEN-ENC-2A/2B、FORMAL、SUP、V2.5、Scheme 3A、TRANS、INFO-TOP 的任何 bytes、hash、结论或证据等级。
- 证据等级：仅 `E1_TECHNICAL_IMPLEMENTATION_CONFORMANCE_ONLY`。
- `overrides=false`。

## 1. 权限与停止边界

本合同只授权 S1 implementation/schema/hash freeze 与 ordinary technical fixtures。正式 HAND/NEAR rows、RANDOM/PHYSICS seeds、80 个身份、static eligibility、response、endpoint、family comparison、ranking、selection、optimization、timing、simulation、COMSOL、full-wave、development、validation、final-test 和 GEN-ENC-2 均未授权。

旧 2C REV01 A–G 缺陷 bytes 安全复用数固定为 0；本 S1 未打开、import、执行、复制或就地修补其 generator/orchestrator/verifier。CAD-1 Attempt06 dispatch 和 run ID 继续为 `CONSUMED_SUCCESS_DO_NOT_REUSE`，本 S1 使用独立 task/dispatch identity。

## 2. 冻结实现与独立性

- orchestrator：`scripts/gen_enc_2c_s1/orchestrator_rev03_s1.py`。
- read-only verifier：`scripts/gen_enc_2c_s1/independent_verifier_rev03_s1.py`。
- verifier 不 import orchestrator、sealed generator 或旧 2C；SplitMix64、binary64 open uniform、midpoint-LHS、positive-area BFS、canonical/hash 路径在自身 bytes 中独立实现。
- orchestrator 只允许在完整 preflight PASS 且未来新 S2 task-bound dispatch 明确授权后绑定 sealed GEN-ENC-2B API。S1 dispatch 的 generator-bind 分支固定拒绝。
- external `source_hash_manifest.json` 消除 source self-reference；dispatch 精确绑定该 manifest hash。

## 3. 九份 schema

REV03 的九个 exact schema 路径已建立：member identity、family manifest、identity index、analysis/static result、artifact inventory、scientific hash manifest、independent verification report、execution/complete-run record、fail-closed record。全部使用 JSON Schema Draft 2020-12、对象字段 allowlist 与 `additionalProperties=false`；fail-closed schema 强制 honest zero formal counts、formal hashes null、`NOT_TESTED` 和 `final_test_read=false`。

## 4. 92-path allowlist 与文件系统门禁

`path_allowlist_manifest.json` 仅列出未来 85 scientific + 6 result + 1 progress 路径；没有创建其中任何目标。preflight 在任何 formal input open、generator bind 或 output write 前检查：exact count 92、casefold uniqueness、duplicates、reserved names、trailing dot/space、containment、file/directory collision、ancestor reparse、target absence 和 formal roots zero-unlisted。

success 与 FAIL_CLOSED 使用互斥 task-bound roots；先 exclusive-create `.tmp`、flush/fsync，再 `os.replace`。混态、双 marker、已有 terminal root 或缺 marker均拒绝。

## 5. runtime、命令与 authority chain

冻结 runtime 为 Python 3.12.4、jsonschema 4.19.2、pytest 9.1.1。exact commands、输入/输出/failure roots、canonical JSON、atomicity 和 manifest hashes 见 `implementation_contract.json`。authority manifest 绑定 REV03 contract/package/review、2A package、2B source bundle、CAD-0 U1/U2/U3 和 CAD-1 Attempt06 seal；任一 byte/hash/runtime/expiry/revocation 不符均 fail closed。

## 6. ordinary technical fixtures

fixtures 顶层身份固定为 `TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY`，位于 `tests/fixtures/gen_enc_2c_s1/`，与 future scientific roots 隔离。独立 verifier 仅以技术 seed/formula 重构 4×20 synthetic slots，并复验 parameter matrices、bounds/DOF、volume/envelope/interface、minimum feature、load path、RANDOM exact-zero reduced edge 和 actual positive-area BFS。通过不能解释为任何 formal member PASS/eligible。

## 7. 证据上限与下一步

最终 ordinary run 为 28 passed；正式输入读取、正式 generator 调用、正式输出、static eligibility、全部 response/timing/simulation/data-read 计数为 0；formal member/family/index hashes 均 null；`scientific_hypothesis_status=NOT_TESTED`；`final_test_read=false`。

S1 完成后必须停止。下一步只允许中间主控验收并提交 guardian implementation/hash-freeze review；不得自行请求或执行 S2。

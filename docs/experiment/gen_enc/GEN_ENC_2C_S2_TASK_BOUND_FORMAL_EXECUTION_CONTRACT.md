# GEN-ENC-2C S2 task-bound 正式执行合同与入口冻结

版本：`GEN-ENC-2C-S2-PREEXECUTION-BINDING-v1`  
日期：2026-08-28  
task ID：`01a048bd-dc5e-7e93-87e6-72d299ebaa4d`  
终态：`READY_FOR_INTERMEDIATE_ACCEPTANCE_AND_GUARDIAN_S2_PREEXECUTION_REVIEW_FORMAL_EXECUTION_BLOCKED`  
证据等级：`E1_TECHNICAL_PREEXECUTION_BINDING_ONLY`

## 增量 metadata

- 新增：全新 S2 formal driver、只读独立 verifier、唯一 dispatch schema、task-bound authorization DRAFT、exact commands/roots/manifests/hash 绑定和普通技术测试。
- 关联旧文件：REV03、S1 contract/package、S1 guardian review、2A REV01、2B sealed source、CAD-0 U1/U2/U3、CAD-1 Attempt06 seal；机器关系见本包 `relates_to.json`。
- 未改变：全部封印 S1 bytes、旧 2C REV01/REV02 bytes、CAD/GEN-ENC/FORMAL/SUP/V2.5/Scheme3A/TRANS/INFO-TOP 的结论、hash 和 evidence level。
- 证据等级：仅 `E1_TECHNICAL_PREEXECUTION_BINDING_ONLY`；science 为 `NOT_TESTED`。
- `overrides=false`。

## 权限边界

本回合只冻结未来 S2 正式 generation/static-audit 的合同与入口。authorization record 为 DRAFT：`released=false`、`guardian_approved=false`、`formal_execution_authorized=false`。没有 guardian-signed release 时，preflight、formal generation/static audit、formal verifier 和 package-results 全部 fail closed。未伪造 guardian path、签名、approval 或 released bytes。

唯一允许未来置 true 的能力为 `s2_formal_generation_and_static_audit`；timing、response、endpoint、comparison、ranking、selection、optimization、simulation、COMSOL、full-wave、physical experiment、development/validation/final-test read 和 GEN-ENC-2 全为 false。`final_test_read=false`。

## 七类 gap 闭合

机器矩阵见 `gap_closure_matrix.json`：CLI/dispatch/contract task ID 三方相等；唯一 S2 schema；canonical payload/envelope exact bytes 与 payload SHA；source/schema/fixture/authority/allowlist 五 manifest hash；exact command/mode vector；完整 permission vector；preflight → generation/static audit → independent verifier → atomic package-results 的 exact commands 和停止顺序。

record 自引用规避规则为：`record_payload_sha256 = SHA-256(canonical(payload))`；envelope 为 `{payload,record_payload_sha256}` 的 canonical exact bytes；未来 guardian 对最终 released envelope 的 full-file hash 必须写入外部新 review/manifest，不得由本 DRAFT 自行生成或批准。

## 正式语义冻结

80 固定槽为四家族各 20；HAND/NEAR exact rows；RANDOM exact formal seed 仅一次；PHYSICS formal master/member seeds 与 parameter-specific Fisher–Yates midpoint LHS；binary64 仅 direct result 等于 1.0 时 `nextafter(1.0,0.0)`。失败保槽，禁止 redraw/repair/replacement，禁止性能/响应分支。

static audit 绑定 matched volume closed interval、U4 envelope/interface、4/4/1、bounds/q270/DOF、volume/Boolean union/ownership、minimum feature、solid load path、RANDOM exact-zero reduced edge 和 actual-fluid positive-area face-adjacency BFS exactly one。reduced connectivity 只作描述，不作 eligibility/performance gate。

独立 verifier 不 import driver/orchestrator/generator/CAD API；独立实现 SplitMix64/open-uniform、midpoint LHS、positive-area BFS、canonical/hash 复算表面。当前只用 technical fixtures 检查入口拒绝与算法能力，未读取正式输入。

## 92-path 与原子终态

S2 直接绑定 S1 已封印的 exact 92-path allowlist（85 scientific + 6 result + 1 progress），其 manifest SHA-256 为 `7a62b0508e253d7740e08e396f3164e3b66b6745c7d42e93f8444f2a244a5ab1`。casefold/duplicate/reserved/containment/reparse/collision/zero-unlisted 和 target absence 均为前置硬门。temporary 与目标同目录、assigned root only；SUCCESS 与 FAIL_CLOSED 互斥，任何前序失败停止，observed counts 必须真实。

## 永久披露与后续义务

S1 首次 pytest 因 ACL 发生 5 setup errors；随后 AST FunctionDef 漏扫被修正并重冻；六个 S1 basetemp roots 的 44 files/58 dirs 为 disclosure-only，未清理。S1 4×20 仅 `TECHNICAL_FIXTURE`。CAD-0 E0 与 CAD-1 E1 不等于 formal eligibility。CAD-1 signing/cache/aggregate/CORR04 残留披露继续有效。

四状态、held-out 45/135/225/315°、0:15:345° continuous-angle、independent inverse-design validation、`NO_IMPROVEMENT` 和 limited full-wave qualification 均为后续义务；本 S2 freeze 未测试、完成或替代它们。

本合同完成即停止，只交中间主控验收及 guardian S2 preexecution review；不得请求 release，不得执行正式输入，不 commit/push/tag/release。

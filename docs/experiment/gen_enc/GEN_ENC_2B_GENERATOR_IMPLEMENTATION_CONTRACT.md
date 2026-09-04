# GEN-ENC-2B 生成器实现与源码哈希冻结合同（PHASE A）

版本：`GEN-ENC-2B-PHASE-A-v1`

日期：2026-08-28

终态：`GEN_ENC_2B_PHASE_A_CONTRACT_READY_FOR_GUARDIAN_REVIEW`

状态：`E0_IMPLEMENTATION_CONTRACT_EXECUTION_NOT_AUTHORIZED`

`execution_authorized=false`，`phase_b_authorized=false`，`scientific_identity_generation_authorized=false`，`preflight_authorized=false`，`gen_enc_2_authorized=false`，`final_test=sealed`，`final_test_read=false`

## 增量 metadata

- **新增**：冻结 REV01 的语义不变生成器模块/API、技术 conformance fixture、源码 bundle 与 SHA-256 失效规则。
- **关联**：GEN-ENC-0R/1 合同、结果和 guardian disclosures；sealed GEN-ENC-2A REV01 包及其 guardian review；active ledger 与 future-stage review protocol。
- **未改变**：旧报告、旧机器产物、旧科学结论、四家族、20 行表、bounds、DOF、nuisance、频带、matched-cost、RQ 状态和 final-test 封存。
- **证据等级**：`E0_IMPLEMENTATION_CONTRACT`。
- **覆盖**：`overrides=false`；只写新 GEN-ENC-2B 增量路径。

## 1. 证据与执行边界

本 PHASE A 只产生 E0 implementation contract。它不实现或执行生成器，不生成任何 CAD/topology 或正式 20-member family manifests，不生成或读取 nuisance responses，不运行 timing preflight、endpoint、family comparison、search、optimization、simulation、COMSOL、full-wave 或 physical experiment。

若 guardian 另行批准 PHASE B，PHASE B 的最高证据仅为 `E1_TECHNICAL_CONFORMANCE_AND_SOURCE_IDENTITY`：证明源码对 REV01 算法的逐字段一致性、确定性、fail-closed 行为和源码身份。任何技术 fixture 通过都不是 E2 topology evidence、科学 family identity、性能、可制造性或物理机制证据。

GEN-ENC-1 的 candidate estimator、严格 `E_primary>1.0` 与 `r_stable=3` 公式不变；但未来 nuisance evaluation domain 与权重按用户授权改为准确的 3675-cell strength-2 joint design。该设计不等价于 full Cartesian：永久保留 124950 omitted cells、`34/35` cell loss、六个未识别 within-group two-factor interactions 和全部未识别 higher-order interactions 的披露。

## 2. 两类对象必须隔离

`technical conformance fixture` 是 PHASE B 可构造的小型或完整 literal expected-output 测试对象，只能验证算法一致性。每份必须带顶层标签 `TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY`，存放在 tests 或 future `phase_b/technical_fixtures/`，禁止进入任何 scientific identity path。

`scientific family instance` 是 REV01 规定的每家族正式 20-member manifest。PHASE B 禁止生成、保存、审查或响应检查。HAND/NEAR 为验证精确 20 行表读取，只能读取已封存的 `family_design_tables_rev01.json` 并核对其 SHA-256、row count/order/identity/bounds/DOF；不得将派生 CAD payload 或拓扑 manifest 封存为科学实例。

任何 PHASE B 临时或 literal 完整输出若具有 manifest 形状，也必须标记 `TECHNICAL_FIXTURE_ONLY_NOT_SCIENTIFIC_IDENTITY`，且 `instance_manifest_sha256_by_family` 在所有合同和结果中继续为 null/pending。

## 3. 语义不变模块与 API

PHASE B 只能实现 `source_bundle_spec.json` 列出的文件。公共 API 只接受显式 REV01 静态输入和纯数据对象，不含 response/data loader、development/validation/final-test loader、solver、timing、endpoint、search 或 optimization 入口。

- HAND/NEAR：严格读取封存 JSON pointer 对应的 20 行，保留存储顺序；验证 exact keys、member IDs、唯一性、bounds、派生 q270 和 DOF；禁止排序、补值、选择 alpha 或重排。
- RANDOM：按冻结 parameter order，对每 seed/parameter 只调用一次冻结的 SplitMix64 和 open-interval uniform，再使用冻结 inverse CDF；edge 镜像互易，零边/断连/弱样本不得重抽。
- PHYSICS：master seed `2026090200`；parameter-specific Fisher–Yates；20 strata midpoint LHS；每参数每 stratum 恰好一次；无 jitter、无替换、无性能分支。
- common mapping：`q270=-(q0+q90+q180)/3`；四 local shares 合计 0.60，central share 0.40；乘 nominal target。固定 sector 的抽象 CAD mapping 采用 deterministic bisection，exact tie 取 lower endpoint，最多 80 iterations，残差阈值 `1e-12 m3`；随后 Boolean-union abstract audit。
- fail closed：no root、iteration exhaustion、nonfinite、target interval、x/y/z envelope、interface identity、one-connected-component、minimum feature、solid load path、null/pending hash 或 schema failure 均返回显式技术状态并保留 member；禁止修参、重抽或用性能结果分支。
- canonical JSON：UTF-8 无 BOM、Unicode code point 递归排序 keys、arrays 保序、shortest round-trip numbers、无无意义空白、无 trailing newline、SHA-256 lowercase hex。

`api_and_schema_spec.json` 是函数签名和负能力的唯一 PHASE A 入口。任何 API 暴露 response/data loader、validation/final-test、正式 scientific manifest 写出或 performance-dependent branch 均使 conformance 失败。

## 4. 源码 bundle 与 SHA-256 冻结

未来 canonical source bundle 包含：列明的实现源文件、公开 API、schema、conformance tests 与 literal fixtures、sealed REV01 controlling artifacts、PHASE A controlling specs。PHASE B 通过全部测试后才可生成 source entry hashes、canonical `source_bundle_manifest.json` bytes 和 bundle SHA-256。

冻结后任一 byte 改变，包括源码、test、schema、table、REV01 artifact 或 controlling spec，立即使 PHASE B authorization 和 source identity 失效；必须停止、保留旧 hash、生成差异说明并回到 guardian review。不得以“只重构”“只格式化”绕过重审。

PHASE B 可产出 `generator_source_sha256` 和 bundle hashes；但正式 `instance_manifest_sha256_by_family` 四项必须继续 null/pending，直到另行批准的 scientific identity generation contract。

## 5. 最低 conformance test 集

必须覆盖：HAND/NEAR row count/order/unique/bounds/DOF；q270、volume shares sum、target interval；CAD bisection determinism、lower tie、80-iteration cap 与 failure cases；interface/envelope/min-feature/load-path；RANDOM SplitMix64 known-answer vectors、`0<u<1`、spike/slab 边界、reciprocity、no redraw；PHYSICS permutation、每 stratum 一次、bounds、repeatability；canonical JSON exact bytes/hash；null/pending hashes fail closed；无 performance-dependent branch；无 response/data loader；validation/final-test API 不可达。

测试对象和预期值必须在执行测试前固定；不得从被测实现动态生成 expected output。允许普通本地确定性 fixture 测试，不允许实体 CAD、求解器或高资源工作。出现这类依赖立即停止，不得改变 family、table、bounds、DOF、nuisance 或频带。

## 6. 依赖顺序与停止

唯一顺序为：`PHASE A guardian review -> PHASE B implementation+tests+source hash -> result seal -> separate scientific identity generation contract -> separate timing preflight contract -> GEN-ENC-2 contract`。不得跳步；SUP-3 与 TRANS reclosure 不是依赖。

本回合不联系或触发范围守门任务。合同完成后停止，等待上级主控完成 guardian review 并另行授权 PHASE B。不 commit、push、tag 或 release。

Active RQ 关闭数为 0；`bidirectional_discovery_established=false`；旧报告只读；`final_test_read=false`。所有 topology generation、scientific instance generation、nuisance response generation、endpoint、family comparison、simulation、search、optimization、training、development/validation response read、timing preflight、COMSOL、full-wave、physical experiment、legacy recomputation 与 final-test read 计数均为 0。

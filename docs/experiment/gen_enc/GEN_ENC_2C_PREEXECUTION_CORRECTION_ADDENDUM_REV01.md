# GEN-ENC-2C 预执行修订增量 REV01

版本：`GEN-ENC-2C-PREEXECUTION-CORRECTION-REV01-v1`

日期：2026-08-28

终态：`READY_FOR_GUARDIAN_CORRECTION_REVIEW`

`execution_authorized=false`，`phase_b_authorized=false`，`scientific_identity_generation_authorized=false`，`preflight_authorized=false`，`gen_enc_2_authorized=false`，`final_test=sealed`，`final_test_read=false`

## 增量 metadata

- **新增**：落实 guardian `CR-01..CR-07` 的证据命名、可执行 schema、tracked orchestrator/verifier、精确写 allowlist、原子写入、独立复验和 set-level 状态修订。
- **关联旧文件**：初版 GEN-ENC-2C PHASE A 合同包及 `GEN_ENC_2C_PHASE_A_CONTRACT_REVIEW.json`；sealed GEN-ENC-2B source bundle；sealed GEN-ENC-2A REV01。
- **未改变**：初版 2C 文件、2B bundle、REV01 family/table/seed/algorithm/bounds/DOF/cost/nuisance、85 scientific paths、binary64 规则、旧科学结论、active RQ 和 final-test。
- **证据等级**：`E0_PREEXECUTION_CORRECTION_CONTRACT`；未来 Phase B 最高标签修正为 `E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY`。
- **覆盖**：`overrides=false`；本 REV01 是只向前关联的 delta，不覆盖初版。

## 1. CR-01：证据边界修正

未来 Phase B 唯一允许证据标签为 `E1B_SCIENTIFIC_IDENTITY_PROVENANCE_AND_STATIC_ELIGIBILITY`。同时每个 scientific identity、family manifest、identity index 和 result artifact 必须写 `scientific_evidence_level=NOT_ESTABLISHED`、`scientific_hypothesis_status=NOT_TESTED`。初版中未限定的 E2 表述不得作为未来输出标签或科学证据引用。

该阶段只建立 immutable identity provenance 和 abstract static eligibility；不建立 response、direction readability、family advantage、robustness、manufacturability、full-wave validity、physical mechanism 或科学正/负结果。

## 2. CR-02：精确运行期写集合

未来 Phase B 运行期 write allowlist 精确为 92 个文件：初版冻结的 80 member JSON、4 family manifests、1 identity index，共 85 个 scientific JSON；加 7 个非 scientific result artifacts：

1. `docs/progress/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION_RESULTS.md`
2. `outputs/gen_enc/GEN_ENC_2C_SCIENTIFIC_IDENTITY_GENERATION/phase_b/result/analysis_summary.json`
3. 同目录 `artifact_inventory.json`
4. 同目录 `scientific_hash_manifest.json`
5. 同目录 `independent_verification_report.json`
6. 同目录 `execution_record.json`
7. 同目录 `SHA256SUMS.txt`

精确 92 路径逐项列在 `write_allowlist_and_result_package_spec.json`。`SHA256SUMS.txt` 必须包含其自身之外的全部 91 个运行期产物。任何未列路径写入、预存目标、重复路径或额外临时输出均停止。

## 3. CR-03/CR-06：tracked orchestrator 与独立 verifier

修订期新建并逐字冻结：

- `scripts/gen_enc_2c_generate_scientific_identities.py`
- `scripts/gen_enc_2c_verify_scientific_identities.py`

二者在 import 时不得执行，正式运行命令和顺序固定为：

1. `python -B scripts/gen_enc_2c_generate_scientific_identities.py preflight`
2. `python -B scripts/gen_enc_2c_generate_scientific_identities.py generate`
3. `python -B scripts/gen_enc_2c_verify_scientific_identities.py verify`
4. `python -B scripts/gen_enc_2c_generate_scientific_identities.py package-results`

working directory 固定为 `D:\Bristol course\dissertation\program work`，Python 固定 `3.12.4`。orchestrator 只可调用 sealed 2B public API，不得修改 2B bytes；verifier 不导入 generator 或 orchestrator，不读取 orchestrator summary，而从 sealed table/seed、可执行 schemas 和 85 个 scientific files 独立重算 exact paths、canonical bytes、schema、80 slot/status counts 和 hash chain。

本修订回合没有 import、运行上述脚本或 generator，没有执行正式 seed。

## 4. CR-04：可执行 schemas

修订期新建并 hash-freeze 8 个 Draft 2020-12 JSON Schemas，位于 `schemas/gen_enc/gen_enc_2c/`：member、family manifest、identity index，以及五类 machine result JSON。全部 object schemas 使用 `additionalProperties=false`，冻结 evidence/source/runtime/status，禁止额外 response/performance/timing 等字段并 fail closed。旧 2B schemas 与 source bundle 不变。

## 5. CR-05：路径、collision、atomic write 和部分失败

repo root 必须精确匹配；所有输出先做 path containment、no symlink escape、92-path cardinality/uniqueness 和 collision preflight。不得覆盖任何既有目标。

临时文件只能与目标同目录且位于获准 Phase B root，使用 exclusive create、flush、`fsync`、`os.replace`。拥有的临时文件在异常后按精确列表清理；已原子提交的正式文件不删除、不覆盖，保留作 failure audit，并使集合进入 technical-blocked。任何残留 temp/unlisted file 必须由 verifier 报错，不得静默遗留。

## 6. CR-07：set-level 状态

member 状态仍为 `STATIC_IDENTITY_ELIGIBLE`、`COST_INELIGIBLE`、`GENERATION_TECHNICAL_FAILURE`。

- 全 80 eligible：`SCIENTIFIC_IDENTITY_AND_STATIC_ELIGIBILITY_COMPLETE`
- 任一 `COST_INELIGIBLE` 且无 technical failure：`IDENTITY_SET_STATIC_ELIGIBILITY_BLOCKED`
- 任一 technical failure、缺槽、重复、schema/hash/path/source/runtime failure：`IDENTITY_SET_TECHNICAL_FAILURE_BLOCKED`

后两者均阻断 timing/GEN-ENC-2；失败槽保留且禁止 repair/redraw/replace/drop。禁止 bare `NO_ELIGIBLE_IDENTITY`，禁止科学阴性化。

## 7. 不变约束与停止

binary64 仍只允许冻结公式直接结果等于 `1.0` 时使用 `math.nextafter(1.0,0.0)`；不得有其他 clamp/epsilon/repair。四家族、80 槽、85 scientific paths、正式 seeds/tables、no-redraw、matched-cost 和 REV01 3675-cell strength-2 nuisance 限制全部不变：不等价 full Cartesian，遗漏 124950 cells，六个 within-group two-factor 与所有 higher interactions 未识别。

运行顺序固定为 `guardian correction review -> preflight hash+collision -> orchestrator -> independent verifier -> result package -> result seal -> separate timing contract -> separate GEN-ENC-2 contract`。任何 failure 停止且保槽。

本修订只做静态 JSON parse、schema meta-validation、AST parse、negative-capability、path/hash 检查；不 import/run scripts 或 generator，不生成 85 scientific JSON，不读写 response/timing/endpoint。所有执行计数 0、identity hashes null、授权 false。完成后停止，等待 guardian correction review；不联系 guardian，不 commit/push/tag/release。

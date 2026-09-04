# GEN-ENC-CAD-1 implementation-contract proposal REV03-CORR02

Version: `GEN-ENC-CAD-1-PHASE-A-PROPOSAL-REV03-CORR02-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_CORR02_CONTRACT_REVIEW`

Evidence label: `E0_TASK_DISPATCH_ROLLOVER_CONTRACT_ONLY`

Current state: `corr02_task_reservation_authorized=false`; `corr02_authorization_record_creation_authorized=false`; `corr02_patch_authorized=false`; `corr02_static_checks_authorized=false`; `corr02_ordinary_tests_authorized=false`; `execution_task_reservation_authorized=false`; `new_execution_dispatch_authorized=false`; `new_run_id_derivation_authorized=false`; `technical_conformance_preflight_authorized=false`; `timing_preflight_authorized=false`; `gate_a_authorized=false`; `gate_b_authorized=false`; `literal_fixture_execution_authorized=false`; `independent_verifier_authorized=false`; `phase_b_retry_authorized=false`; every formal/scientific authorization is false; `formal_instance_count=0`; `final_test_read=false`.

## Increment metadata

- **New content:** bounded task/dispatch-rollover correction required by `GEN_ENC_CAD_1_REV03_RECOVERY_POST_CORRECTION_REVIEW.json`.
- **Relates to:** immutable REV03-CORR01 contract package, sealed seven-file recovery evidence, Attempt01 70-path baseline, REV02 dispatch/run-id authority and CAD-0 authority chain.
- **Unchanged:** current compiler, verifier and existing test bytes; the seven-file evidence package; the other 67 retained paths; 42 fixture bytes/order/cardinality; all CAD/scientific semantics, output roots and formal prohibitions.
- **Evidence:** E0 contract/governance only; no CORR02 implementation, static result, ordinary-test result or E1 conformance evidence.
- **Override:** `overrides=false`; this forward-only addendum does not rewrite any prior conclusion.

## 1. Closed technical finding and exact future edit boundary

The sealed Windows long-path recovery is technically valid, but both command scripts still treat the consumed Attempt01 task and dispatch as live constants. This makes the required future new task/dispatch pair impossible and leaves verifier authority validation incomplete. This is an implementation-validity defect only, never a fixture, eligibility or scientific result.

Only these paths may change after a separately approved CORR02 correction authorization:

1. `scripts/gen_enc_cad_1_compile_fixture.py`, current SHA-256 `11064f2a30d5a8d92068da7834f5d6432e3da473163b2a0a6adce2ab67645814`;
2. `scripts/gen_enc_cad_1_verify_fixture.py`, current SHA-256 `1e5048759db8bc139b806b76e4398faa0c6d3970798cdd88af28b734ba844a08`;
3. `tests/test_gen_enc_cad_1_contract_conformance.py`, current SHA-256 `510433721843e484668fea5cca69001023deffec07ff33429b58497898f8ebc3`.

No schema, fixture, shared helper or additional source path may be created or changed. Any fourth path change, missing path, before-hash mismatch or boundary expansion stops without self-repair.

## 2. Future CORR02 correction authorization

This contract does not reserve a task or create a record. After guardian approval only, the intermediate controller may reserve one idle lowest-level CORR02 correction task and issue one canonical record at:

`outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/authorizations/GEN_ENC_CAD_1_CORR02/GEN_ENC_CAD_1_REV03_CORR02_TASK_<task-id>.authorization.json`

The future schema path is `schemas/governance/gen_enc_cad_1_rev03_corr02_authorization.schema.json`. Issuer is exactly `GEN_ENC_INTERMEDIATE_CONTROLLER`. The record binds the real idle correction task ID, this contract/progress/manifest and approving review, the post-correction review hash `3f801f246b51873bfd26d9e837cc99f23ce0dc0fa9d5d516bc0e0718fe5dbcab`, the immutable seven-file evidence manifest hash `2b6ac9da9c73013496b2e6d0517070988fa1e95fe150cac9d47eb73277f77b1e`, all seven evidence file hashes, the three current before hashes, exact three-path boundary, exact incremental evidence root, allowed modes, runtime, expiry and revocation.

Only `corr02_patch_authorized`, `corr02_static_checks_authorized`, `corr02_ordinary_tests_authorized` and `corr02_evidence_packaging_authorized` may be true. Execution-task reservation, execution dispatch, run-id derivation, preflight, Gate A/B, 42 fixtures, independent verifier, retry and every formal/scientific authorization remain false. Canonical bytes are the existing canonical JSON form; identity is lowercase SHA-256 of those exact bytes. Any byte, task, path, schema, hash-chain, mode, runtime, expiry or revocation mismatch invalidates the record before writes.

The CORR02 correction authorization is not a Phase B execution dispatch and cannot be supplied to compiler/verifier execution CLI modes.

## 3. Removing stale execution authority

The future patch must remove module-level `DISPATCH` and `TASK` values as acceptance or run-addressing authority from both scripts. The consumed task `01a04695-2076-72f1-a118-2f9e4a402f90`, dispatch SHA-256 `963174135167f125391f27109d5519636dd46345d202997772b1ffe059a40fc9` and run ID `ae70d9d6c84c2fb9b9723ee9833f266601a9e89c38ef18aa3652bf719a87febe` remain immutable denied provenance. They may occur only in ordinary negative-test literals or disclosures and must never select, authorize or derive a run.

For every execution mode, the compiler accepts only CLI `--authorization-record <exact-relative-path>` and `--task-id <canonical-task-id>`. Before fixture-manifest parsing, subject access, staging lookup or any persistent write, it must:

1. validate canonical UUID syntax for the CLI task ID;
2. require the exact governance root `outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/` and exact filename `GEN_ENC_CAD_1_PHASE_B_TASK_<task-id>.dispatch_authorization.json`, with byte-equal filename task and CLI task;
3. apply exact-relative, containment, no-alias/no-glob and per-operation reparse/identity rules;
4. read the exact record, enforce UTF-8/no-BOM canonical JSON round-trip, exact schema path and schema hash, required-property set, types and `additionalProperties=false` using stdlib-only validation;
5. require record type, issuer, `allowed_task_id`, record ID, requested mode and exact task/path agreement;
6. reject expired or revoked records and validate UTC timestamps;
7. require guardian decision `GUARDIAN_APPROVE` or `GUARDIAN_APPROVE_WITH_REQUIRED_DISCLOSURES` and `guardian_implementation_execution_authorized=true`;
8. rehash every exact authority-chain path and require role/path/hash equality, including the guardian review and corrected contract/progress/manifest;
9. require exact source/schema/test/42-fixture/output/staging/failure boundaries, working directory, runtime and all authorization booleans;
10. require `implementation_execution_authorized=true`, `technical_conformance_preflight_authorized=true`, `timing_preflight_authorized=false` and all scientific/formal fields false.

No opaque environment secret, fallback path, default task, source constant, alternate root or partially validated record is accepted.

## 4. Independent verifier

The verifier must independently implement the same dispatch path, task, canonical/schema, issuer, mode, time, decision/boolean, hash-chain, exact-boundary, runtime and authorization checks before reading staged compiler subjects. It remains one stdlib-only source at `scripts/gen_enc_cad_1_verify_fixture.py` and may import only the existing frozen stdlib allowlist.

It must not import the compiler, `acoustic_encoder.gen_enc.cad_mapping`, generator code, tests, a new shared helper, compiler outputs as authority or any third-party schema/numeric/path library. Its schema/canonical/hash-chain and boundary algorithms live inside the verifier itself. Unavailable validation causes a fail-closed technical stop; it cannot relax checks or add a dependency.

Compiler and verifier separately compute their validated dispatch canonical bytes and task ID. Agreement of their derived run ID is an observed technical equality, not mutual authority.

## 5. Unchanged run-id formula

Let `A` be lowercase SHA-256 of exact canonical bytes of the newly validated execution dispatch, `T` the exact validated CLI task ID encoded UTF-8, and `F` lowercase SHA-256 of exact canonical bytes of the unchanged 42-record complete fixture manifest. The ASCII preimage remains exactly:

`GEN_ENC_CAD_1_RUN_ID_V1\n{A}\n{T}\n{F}`

with no final newline. `run_id` remains lowercase SHA-256 of that preimage. Every process independently derives it, requires exact equality with explicit `--run-id`, and only then computes fixed staging paths. No run ID is derived in this contract phase.

## 6. Ordinary technical falsifiers

The existing ordinary test source may add exactly five rollover cases, without changing the 42-fixture manifest:

1. a canonical syntactically valid new task-bound synthetic dispatch is accepted independently by compiler and verifier validation paths;
2. dispatch filename/path task unequal to CLI/record task fails closed;
3. the consumed Attempt01 task/dispatch pair fails closed;
4. one changed authority-chain hash fails closed before subject access;
5. compiler and verifier derive the same run ID from the same newly validated synthetic pair.

These tests use an isolated temporary repository with the exact logical governance subtree and a fixed test-only UUID. They create no real Codex task, no persistent governance record and no Phase B run. Expected positive tests pass only on acceptance/equality; expected negative rejection is `PASS_EXPECTATION_MATCH`. None emits member/static/scientific status or becomes fixture 43.

## 7. Incremental CORR02 evidence

The existing root `outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/recovery_rev03/post_correction_evidence/` is immutable at seven files and manifest SHA-256 `2b6ac9da9c73013496b2e6d0517070988fa1e95fe150cac9d47eb73277f77b1e`.

The sole future incremental root is:

`outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/recovery_rev03/corr02_incremental_evidence/`

It must contain exactly seven files and no subdirectories:

1. `corr02_three_file_before_after_manifest.json` — exactly three current-before/new-after hashes and byte lengths;
2. `corr02_unchanged_67_hash_verification.json` — exactly 67 path/hash records and zero mismatch;
3. `corr02_retained_70_path_set_verification.json` — exactly 70 unique paths, three changed and 67 unchanged, with the unchanged fixture-manifest hash;
4. `corr02_static_check_report.json` — syntax/import/negative-capability/schema/rollover/path/cardinality/zero-unlisted results;
5. `corr02_ordinary_test_report.json` — exact five rollover test IDs, counts/outcomes and zero fixture/formal execution;
6. `artifact_inventory.json` — exact seven-path inventory;
7. `SHA256SUMS.txt` — exactly six non-self entries, Unicode path order, lowercase digest, two spaces and LF; self excluded.

Any collision or pre-existing incremental root/file produces zero writes and preserves it. The package is governance/technical correction evidence, not implementation, executable schema, fixture or scientific evidence.

## 8. Strict future sequence and current stop

The only future sequence is: guardian approves this exact CORR02 contract; controller reserves an idle correction task and issues its correction authorization; task validates authorization and all current baseline hashes before writes; patch only three files; run bounded static checks; run only the five ordinary rollover tests plus unchanged ordinary recovery tests as explicitly authorized; freeze three new hashes, verify 67 unchanged and seal the incremental evidence; stop without Gate A/B, 42 fixtures or verifier execution; guardian reviews exact corrected bytes and evidence. Only after a separate approving guardian review may the controller reserve a new idle execution task, issue a new task-bound execution dispatch and authorize subsequent Gate A.

This phase creates none of those future objects. No current file, seven-file evidence item, baseline, schema, fixture, implementation or test is modified or executed. Do not contact guardian or commit/push/tag/release. Stop at `READY_FOR_GUARDIAN_CORR02_CONTRACT_REVIEW`.

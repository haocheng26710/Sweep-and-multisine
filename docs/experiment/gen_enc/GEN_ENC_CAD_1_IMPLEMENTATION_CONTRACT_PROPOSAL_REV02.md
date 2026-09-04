# GEN-ENC-CAD-1 implementation-contract proposal REV02

Version: `GEN-ENC-CAD-1-PHASE-A-PROPOSAL-REV02-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_CONTRACT_PREEXECUTION_REVIEW_REV02`

Evidence label: `E0_IMPLEMENTATION_CONTRACT_PROPOSAL_REVISION`

Current state: `implementation_task_creation_authorized=false`; `dispatch_authorization_record_creation_authorized=false`; `implementation_source_creation_authorized=false`; `executable_schema_creation_authorized=false`; `literal_fixture_creation_authorized=false`; `literal_fixture_execution_authorized=false`; `implementation_execution_authorized=false`; `technical_conformance_preflight_authorized=false`; `timing_preflight_authorized=false`; `phase_b_started=false`; `formal_generator_invoked=false`; `formal_seed_consumed=false`; `formal_instance_count=0`; `static_eligibility_authorized=false`; `gen_enc_2_authorized=false`; `final_test_read=false`.

## Increment metadata

- **New content:** closed technical execution-orchestration correction for the REV01 guardian review: official guardian decision vocabulary, distinct implementation boolean, two preflight fields, unique dispatch governance path and task sequence, deterministic complete 42-fixture aggregation, run ID/staging identity, non-destructive collision behavior and Gate A/Gate B sequence.
- **Relates to:** unchanged initial and REV01 CAD-1 packages and the REV01 guardian review; approved CAD-0 REV02/U1-U3; sealed GEN-ENC-2B identity.
- **Unchanged:** all initial and REV01 bytes; the REV01 verifier/import/predicate/zero-area/two-axis/42-fixture closures; CAD-0 U1/U2/U3, 20 exception IDs, exact root proof, shared-plenum semantics, four families/80 slots/no repair and every formal/scientific prohibition.
- **Evidence:** `E0_IMPLEMENTATION_CONTRACT_PROPOSAL_REVISION`; no technical execution or scientific evidence.
- **Override:** `overrides=false`; this is a forward-only REV02 addendum.

## 1. Official guardian decision and split preflight vocabulary

`guardian_decision` accepts exactly four official values: `GUARDIAN_APPROVE`, `GUARDIAN_APPROVE_WITH_REQUIRED_DISCLOSURES`, `GUARDIAN_ESCALATE_USER_DECISION`, or `GUARDIAN_REJECT_UNAUTHORIZED_CONTRACTION`. No fifth decision exists.

A future guardian review authorizes implementation only when its official decision is `GUARDIAN_APPROVE` or `GUARDIAN_APPROVE_WITH_REQUIRED_DISCLOSURES` **and** its separate `guardian_implementation_execution_authorized=true`. Both conditions are mandatory. For either other decision, the boolean must be false.

All future records, schemas, reports and matrices use two different fields: `technical_conformance_preflight_authorized`, which may be true only after corrected-contract approval and dispatch; and `timing_preflight_authorized`, which remains false throughout CAD-1. Bare `preflight_authorized` is forbidden. In this REV02 both named fields are false.

## 2. Exact task and dispatch sequence

The sole future dispatch governance root is `outputs/governance/RESEARCH_SCOPE_CONTRACTION_AUDIT/dispatch/GEN_ENC_CAD_1/`. The sole filename pattern is `GEN_ENC_CAD_1_PHASE_B_TASK_<task-id>.dispatch_authorization.json`, where `<task-id>` is the exact lowercase canonical Codex UUID `8-4-4-4-12` form stored in the record. No alias, glob, alternate root or logical ID is allowed.

Sequence is fixed:

1. Guardian reviews the exact corrected contract and records an allowed official decision plus `guardian_implementation_execution_authorized=true`.
2. The intermediate controller creates/reserves the lowest-level task identity. That task remains idle and performs no read, write, import or execution.
3. The intermediate controller, as `GEN_ENC_INTERMEDIATE_CONTROLLER`, issues the canonical dispatch record at the exact path above, binding the guardian review path/hash/decision/boolean, actual task ID, corrected contract/hash chain, exact modes/boundaries/runtime and split preflight fields. Guardian authority is supplied only by the hashed review; the guardian does not issue an unofficial decision.
4. The task validates the record and Gate A before creating any implementation file.

Any dispatch, guardian review, contract, manifest or bound authority byte change; revocation; expiry; task/mode/path/runtime mismatch; or boundary addition/removal/rename invalidates the chain. No opaque secret or environment substitution is allowed. This REV02 creates neither task nor dispatch record.

## 3. Complete 42-fixture run and aggregate files

Future `complete_fixture_manifest.json` is an input manifest under `tests/fixtures/gen_enc_cad_1/`, serialized canonically and containing exactly 42 records in the frozen REV01 order. Every record contains ordinal, fixture ID/path/hash, expected `fixture_run_status`, expected `observed_subject_status`, ordered reason codes, and expected subject-output-presence flags.

The future technical success root remains `outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/technical/` but now contains exactly 11 files: the prior ten plus `complete_run_manifest.json`. `compiled_mapping.json`, `static_audit.json`, and `verification_report.json` are objects whose `records` fields are ordered arrays of exactly 42 entries, never single-fixture overwrites. `complete_run_manifest.json` also has exactly 42 ordered records and binds all three aggregate hashes.

Each aggregate entry contains the same ordinal/fixture ID. A precondition rejection has `compiled_mapping_subject=null`, `static_audit_subject=null`, presence flags false, and a non-null verification entry that independently confirms the expected rejection. `null` is required; omission is forbidden. Post-parse fixtures use explicit presence rules frozen in `complete_run_manifest_spec.json`. `package-results` accepts only the complete, independently verified run manifest with ordinals 1..42, no missing/duplicate fixture, all `fixture_run_status=PASS_EXPECTATION_MATCH`, and matching aggregate hashes. It cannot consume or overwrite from a single fixture.

## 4. Deterministic run ID and cross-process staging

Let `A` be lowercase SHA-256 of exact canonical authorization-record bytes, `T` the exact task ID UTF-8 bytes, and `F` lowercase SHA-256 of exact canonical `complete_fixture_manifest.json` bytes. The run preimage is the ASCII bytes:

`GEN_ENC_CAD_1_RUN_ID_V1\n` + `A` + `\n` + `T` + `\n` + `F`

with no final newline. `run_id` is lowercase SHA-256 of that preimage. All four CLIs require `--run-id <64-lowercase-hex>` and independently derive and compare it before use.

The unique staging root is `outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/.staging/<run_id>/`. Each staged success filename is exactly `<final-filename>.stage.<run_id>.tmp`. The exact paths are computed from the 11-name list; glob discovery is forbidden. Compiler, verifier and package process the same addressed bytes. A pre-existing staging root or staged filename is a non-destructive collision failure.

## 5. Non-destructive collision and failure cardinality

Gate-A/pre-write failures—including an existing unlisted/colliding success, staging or output path—produce zero persistent files and return only the specified nonzero process status/reason. They never delete, clean, overwrite, rename or replace any pre-existing/unowned object.

After Gate A has proven roots absent/clean and created an owned staging root exclusively, a later clean-owned-run failure removes only exact owned staged temporary paths and writes exactly one immutable record at `outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/failures/<run_id>/fail_closed_record.json`. The failure directory/path must have been absent at Gate A and is exclusively created. It is outside the success root. No success file may coexist for that run. Failure-record collision causes zero additional writes and preserves the existing object.

Thus cardinalities are distinct: pre-write/unowned collision failure = zero persistent writes; clean-owned-run failure = exactly one failure record; success = exactly 11 success files and zero failure records.

## 6. Gate A and Gate B

Gate A occurs before any implementation/source/schema/test/fixture/output/staging creation. It validates dispatch canonical/schema/hash chain, official guardian decision plus boolean, actual task ID, authorization modes, both preflight fields, authority hashes, repository/runtime binding, exact source/schema/test/fixture/output/staging/failure boundaries, containment/reparse rules and absence/collision conditions. Gate-A failure writes nothing.

Only Gate A may release exact allowed source/schema/test/literal-fixture creation. After creation and before any fixture execution, Gate B hashes every expected file, verifies exact path/cardinality, zero unlisted files, schema meta-validity, fixture manifest/order/count/hash, forbidden imports/capabilities, verifier isolation and source/runtime bindings. Only `technical_conformance_preflight_authorized=true` and Gate B pass may release the complete synthetic fixture run. `timing_preflight_authorized=false` always.

## 7. Carried-forward closures and current stop

REV01's single-file stdlib-only verifier, independent robust predicates, zero-area transition, two-axis fixture model and all 42 frozen fixture specifications remain unchanged. CAD-0 U1/U2/U3, the 20-ID exception allowlist, root/shared-plenum/80-slot/no-repair controls and all formal prohibitions remain unchanged.

No task, dispatch record, implementation source, executable schema, test, fixture, staging/output/failure root or run manifest was created. No Gate A/B, technical preflight, compiler, verifier, packaging, formal input, geometry or static eligibility operation ran. Do not contact guardian or commit/push/tag/release. Stop at `READY_FOR_GUARDIAN_CONTRACT_PREEXECUTION_REVIEW_REV02` for intermediate-controller submission.

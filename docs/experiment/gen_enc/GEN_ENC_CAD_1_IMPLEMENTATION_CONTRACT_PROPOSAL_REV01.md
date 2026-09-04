# GEN-ENC-CAD-1 implementation-contract proposal REV01

Version: `GEN-ENC-CAD-1-PHASE-A-PROPOSAL-REV01-v1`

Date: 2026-08-28

Terminal state: `READY_FOR_GUARDIAN_CONTRACT_PREEXECUTION_REVIEW_REV01`

Evidence label: `E0_IMPLEMENTATION_CONTRACT_PROPOSAL_REVISION`

`implementation_source_creation_authorized=false`; `executable_schema_creation_authorized=false`; `literal_fixture_creation_authorized=false`; `literal_fixture_execution_authorized=false`; `implementation_execution_authorized=false`; `phase_b_started=false`; `formal_generator_invoked=false`; `formal_seed_consumed=false`; `formal_instance_count=0`; `static_eligibility_authorized=false`; `preflight_authorized=false`; `gen_enc_2_authorized=false`; `final_test_read=false`.

## Increment metadata

- **New content:** bounded technical closure of guardian `CAD1-RC-01..CAD1-RC-09`: dispatch authorization carrier, exact persistent results, mechanical path containment, stdlib-only independent verifier, independent robust predicates, explicit zero-area transition, two-axis fixture states and twelve additional literal/static fixture specifications.
- **Relates to:** the unchanged initial CAD-1 proposal/package and `GEN_ENC_CAD_1_PHASE_A_CONTRACT_PREEXECUTION_REVIEW.json`; approved CAD-0 REV02/U1-U3; sealed GEN-ENC-2B source identity.
- **Unchanged:** every initial CAD-1 byte and conclusion; CAD-0 U1/U2/U3; twenty exception IDs; constrained root proof; shared-plenum semantics; four families and 80 slots; no repair/redraw/replacement/drop; every formal prohibition and final-test seal.
- **Evidence:** `E0_IMPLEMENTATION_CONTRACT_PROPOSAL_REVISION`; no implementation, schema, test, fixture, technical result, static eligibility or scientific evidence is created.
- **Override:** `overrides=false`; this is a forward-only addendum. Machine-readable relations and exact hashes are in `relates_to.json`.

## 1. CAD1-RC-01: dispatch authorization record and exact CLI

Every future command requires both `--authorization-record <exact-relative-path>` and `--task-id <exact-task-id>`. The record is a plain canonical JSON governance artifact, never an opaque environment secret. Its future schema is defined declaratively in `authorization_dispatch_spec.json`; this REV01 does not create the record or executable schema.

The record must be issued by `GEN_ENC_INTERMEDIATE_CONTROLLER` only after a guardian review of this exact REV01 returns explicit implementation approval. Its future executable schema path is exactly `schemas/gen_enc/gen_enc_cad_1/dispatch_authorization.schema.json`. It binds the revised contract and `SHA256SUMS.txt` hashes, guardian review path/hash, one implementation task ID, allowed modes, working directory, exact source/schema/test/fixture/output boundaries, runtime and expiration/invalidation rules. It alone may set `implementation_execution_authorized=true`; it must keep implementation/schema/fixture creation permissions explicitly scoped and every formal/scientific/static/preflight/GEN-ENC-2 authorization false.

Before fixture parsing, the CLI must resolve and validate: record path is the single exact relative path named at dispatch; canonical/schema validity; issuer role/thread; guardian decision/hash; revised contract/manifest hashes; task-ID equality; requested mode; exact boundaries; unexpired/not revoked state; and unchanged bytes of all bound authorities. Any record byte change, revised-contract change, guardian-record change, task/mode/path mismatch, expiry or revocation invalidates authorization and fails closed. Environment variables cannot substitute for any record field.

Future commands are exactly:

1. `python -B scripts/gen_enc_cad_1_compile_fixture.py preflight --authorization-record <exact-relative-path> --task-id <exact-task-id> --fixture <allowlisted-exact-relative-path>`
2. `python -B scripts/gen_enc_cad_1_compile_fixture.py compile --authorization-record <exact-relative-path> --task-id <exact-task-id> --fixture <allowlisted-exact-relative-path>`
3. `python -B scripts/gen_enc_cad_1_verify_fixture.py verify --authorization-record <exact-relative-path> --task-id <exact-task-id> --fixture <allowlisted-exact-relative-path>`
4. `python -B scripts/gen_enc_cad_1_compile_fixture.py package-results --authorization-record <exact-relative-path> --task-id <exact-task-id> --fixture <allowlisted-exact-relative-path>`

## 2. CAD1-RC-02/03: exact output and mechanical containment

The single future persistent root is `outputs/gen_enc/GEN_ENC_CAD_1_IMPLEMENTATION_CONTRACT/phase_b/technical/`. Successful execution contains exactly ten files and no subdirectories: `compiled_mapping.json`, `static_audit.json`, `verification_report.json`, `audit_log.json`, `source_hash_manifest.json`, `schema_hash_manifest.json`, `fixture_hash_manifest.json`, `result_summary.json`, `artifact_inventory.json`, and `SHA256SUMS.txt`. The nine JSON schemas and exact cardinalities are frozen in `output_and_path_spec.json`. Failure mode contains exactly one persistent file, `fail_closed_record.json`, and none of the ten success files. This is the sole fail-closed artifact.

Before work, resolve the repository and assigned output roots without globbing, aliases or environment expansion. Every supplied path must be normalized exact-relative syntax, have no `.`/`..`, wildcard, alternate data stream, drive-relative or UNC form, and after resolution remain under its assigned root. The path and every existing ancestor must be tested for symlink and Windows junction/reparse-point status. Any such object fails before read/write. Pre-existing output root contents, collision, unlisted path or duplicate path fail closed.

Temporary files use exclusive creation in the same target directory with an implementation-owned exact name derived from the target plus task-bound nonce, followed by flush, `fsync` and `os.replace`. Success JSONs remain temporary through independent verification; only after full verification are the ten final names committed. On error, all owned temporaries are removed by exact list and the one atomic `fail_closed_record.json` is created. A leftover temporary, partial success target or unlisted file is itself a technical failure and cannot be silently cleaned beyond owned exact temporaries.

## 3. CAD1-RC-04/05: independent verifier and predicates

The only verifier source is `scripts/gen_enc_cad_1_verify_fixture.py`; no verifier helper file is authorized. It may import only: `argparse`, `collections`, `dataclasses`, `decimal`, `fractions`, `hashlib`, `itertools`, `json`, `math`, `os`, `pathlib`, `platform`, `stat`, `struct`, `sys`, and `typing`. Dynamic imports and third-party packages are forbidden. It must not import `cad_mapping`, either compiler/orchestrator script, GEN-ENC-2B generator, GEN-ENC-2C scripts, tests, fixtures as executable code, or compiler output as authority. Compiler outputs are untrusted subjects only.

All independent canonicalization, root, ownership, union, graph and clearance algorithms live directly in that exact verifier file. The verifier independently reads approved authority and literal expectations, reconstructs values and compares the untrusted compiler outputs. It cannot call compiler helpers. If the required arrangement cannot be implemented with the permitted stdlib and frozen algorithm, implementation stops and reports `VERIFIER_ALGORITHM_UNAVAILABLE`; no numeric/polyhedral dependency may be introduced silently.

Runtime is bound to CPython 3.12.4 on Windows `win32` AMD64/x86-64, IEEE-754 binary64, round-to-nearest ties-to-even, and the frozen `sys.float_info`/`platform` record. Decimal authority literals are parsed as `Decimal` at context precision 80, converted once to binary64, then converted with `float.as_integer_ratio()` to exact dyadic `Fraction` for predicates. Transcendental softmax uses `math.exp` in frozen evaluation order and must pass future literal binary64 known-answer vectors before any mapping. Nonfinite and negative zero fail.

Orientation, plane-side, polygon signed area, positive-area adjacency, segment intersection and equality/tie predicates use exact `Fraction` arithmetic on dyadic inputs. Exact zero is zero; no epsilon exists. Canonical numbers use an independently implemented shortest round-trip binary64 formatter and literal known answers. Roots independently reproduce endpoint-first lower-tie bisection and the exact authority brackets. Ownership and box unions use exact dyadic plane/cell predicates and lexicographic ordering. Graph BFS uses positive exact face area. Clearance constructs the exact clipped convex arrangement from dyadic planes, consolidates only after degeneracy checks, and sorts ties by exact squared distance, sheet IDs and dyadic endpoints.

## 4. CAD1-RC-06: degenerate boundary transition

The initial phrase `NO_ZERO_AREA_FACE_DISCARD` is narrowed mechanically: after face construction and before consolidation, compute exact signed polygon area using dyadic predicates. Exact zero area emits `DEGENERATE_BOUNDARY_FACE` and stops; the face is neither discarded nor retained for later consolidation/clearance.

For literal/template fixtures, a correctly observed degenerate face has `observed_subject_status=TEMPLATE_VALIDITY_REJECTED`, `fixture_run_status=PASS_EXPECTATION_MATCH`, and zero formal slots. In any separately authorized future formal stage, an implementation-created degenerate face is `GENERATION_TECHNICAL_FAILURE`. It is never `COST_INELIGIBLE`, static eligibility, manufacturability evidence or a scientific negative.

## 5. CAD1-RC-07/08: two-axis fixtures and added falsifiers

Every fixture result contains both `fixture_run_status` and `observed_subject_status`, plus exact reason codes. `fixture_run_status` is one of `PASS_EXPECTATION_MATCH`, `FAIL_EXPECTATION_MISMATCH`, or `TECHNICAL_FIXTURE_HARNESS_FAILURE`. A negative synthetic subject passes conformance when its observed status/reasons equal the frozen expectation. No fixture emits a formal member status, static-eligibility result or scientific result.

The initial thirty fixture specifications are carried forward with two-axis expected outcomes. Twelve additional literal/static specifications cover missing, wrong-contract and wrong-scope authorization records; symlink and junction escape; unlisted output and collision; forbidden verifier import; exact zero-area face; duplicate and missing exception allowlist IDs; and measurement equal to a threshold without derivation/witness. The revised count is 42. Exact paths, subject states and reasons are in `falsification_fixture_inventory_rev01.json`. `fixtures_created=0`; `fixtures_executed=0`.

## 6. CAD1-RC-09 and authorization boundary

CAD-0 REV02/U1-U3, the twenty-ID allowlist, four-family bracket, shared-plenum/reduced-graph separation, 80-slot retention, state meanings and all no-repair/formal prohibitions remain byte-semantically unchanged. The sealed GEN-ENC-2B bundle remains immutable. Initial CAD-1 files are not edited.

This revision defines a possible future execution authorization carrier but is not that carrier. Only a subsequent guardian approval plus a separately issued machine dispatch record can authorize the bounded implementation task. The present values remain: `implementation_source_creation_authorized=false`, `executable_schema_creation_authorized=false`, `literal_fixture_creation_authorized=false`, `literal_fixture_execution_authorized=false`, and `implementation_execution_authorized=false`.

No implementation source, executable schema, test or fixture was created or run; no formal seed, row, identity, geometry or static qualification was evaluated. Do not contact guardian, commit, push, tag or release. Stop at `READY_FOR_GUARDIAN_CONTRACT_PREEXECUTION_REVIEW_REV01` and await intermediate-controller submission.
